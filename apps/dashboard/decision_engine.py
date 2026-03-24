from __future__ import annotations

from decimal import Decimal
from typing import Dict
from urllib.parse import urlencode
import unicodedata

from apps.parametros.models import ParametroActivo
from apps.core.services.incremental_proposal_contracts import build_incremental_purchase_plan_summary


def _coerce_optional_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_decision_engine_query_stamp(query_params) -> str:
    if query_params is None:
        return "none"
    if isinstance(query_params, dict):
        items = sorted((str(key), str(value)) for key, value in query_params.items())
        return urlencode(items)
    items_method = getattr(query_params, "lists", None)
    if callable(items_method):
        normalized = []
        for key, values in query_params.lists():
            for value in values:
                normalized.append((str(key), str(value)))
        return urlencode(sorted(normalized))
    return str(query_params)


def _build_decision_macro_state(macro_local: Dict | None) -> Dict:
    macro_local = macro_local or {}
    fx_state = str(macro_local.get("fx_signal_state") or "").strip().lower()
    riesgo_pais = _coerce_optional_float(macro_local.get("riesgo_pais_arg"))
    uva_annualized = _coerce_optional_float(macro_local.get("uva_annualized_pct_30d"))

    if fx_state == "divergent" or (riesgo_pais is not None and riesgo_pais >= 900):
        return {
            "key": "crisis",
            "label": "Crisis",
            "score_component": 4,
            "summary": "El contexto local exige maxima cautela antes de sumar riesgo.",
        }
    if fx_state == "tensioned" or (riesgo_pais is not None and riesgo_pais >= 700) or (
        uva_annualized is not None and uva_annualized >= 35
    ):
        return {
            "key": "tension",
            "label": "Tension",
            "score_component": 13,
            "summary": "Hay tension local y conviene evitar decisiones agresivas.",
        }
    if fx_state or riesgo_pais is not None or uva_annualized is not None:
        return {
            "key": "normal",
            "label": "Normal",
            "score_component": 25,
            "summary": "No hay una senal macro dominante que invalide el flujo principal.",
        }
    return {
        "key": "indefinido",
        "label": "Indefinido",
        "score_component": 12,
        "summary": "Falta contexto macro suficiente para una lectura mas firme.",
    }


def _build_decision_portfolio_state(analytics: Dict | None) -> Dict:
    analytics = analytics or {}
    stress = analytics.get("stress_testing") or {}
    expected = analytics.get("expected_return") or {}
    risk = analytics.get("risk_contribution") or {}
    top_asset = risk.get("top_asset") or {}

    fragility_score = _coerce_optional_float(stress.get("fragility_score"))
    total_loss_pct = _coerce_optional_float(stress.get("total_loss_pct"))
    real_expected_return_pct = _coerce_optional_float(expected.get("real_expected_return_pct"))
    top_asset_contribution = _coerce_optional_float(top_asset.get("contribution_pct"))

    if (fragility_score is not None and fragility_score >= 70) or (
        total_loss_pct is not None and total_loss_pct < -20
    ):
        return {
            "key": "riesgo",
            "label": "Riesgo",
            "score_component": 5,
            "summary": "La cartera ya muestra fragilidad relevante y pide prudencia.",
        }
    if (real_expected_return_pct is not None and real_expected_return_pct < 0) or (
        top_asset_contribution is not None and top_asset_contribution > 0.25
    ):
        return {
            "key": "desbalance",
            "label": "Desbalance",
            "score_component": 14,
            "summary": "Hay senales de concentracion o retorno real debil a corregir.",
        }
    if (
        fragility_score is not None
        or total_loss_pct is not None
        or real_expected_return_pct is not None
        or top_asset_contribution is not None
    ):
        return {
            "key": "ok",
            "label": "OK",
            "score_component": 25,
            "summary": "La cartera admite un aporte incremental sin desviar el flujo principal.",
        }
    return {
        "key": "indefinido",
        "label": "Indefinido",
        "score_component": 12,
        "summary": "Falta contexto suficiente sobre el estado actual de la cartera.",
    }


def _normalize_decision_block_label(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_only.replace("/", " ").split())


def _has_block_overlap(target_block: str | None, candidate_blocks: list[Dict] | list[str] | None) -> bool:
    target = _normalize_decision_block_label(target_block)
    if not target:
        return False
    for item in candidate_blocks or []:
        if isinstance(item, dict):
            candidate = _normalize_decision_block_label(item.get("label"))
        else:
            candidate = _normalize_decision_block_label(item)
        if candidate and (candidate == target or candidate in target or target in candidate):
            return True
    return False


def _is_parking_overlap_with_recommendation(recommendation_block: str | None, parking_blocks: list[Dict] | None) -> bool:
    return _has_block_overlap(recommendation_block, parking_blocks)


def _is_market_history_overlap_with_recommendation(
    recommendation_block: str | None,
    weak_blocks: list[Dict] | list[str] | None,
) -> bool:
    return _has_block_overlap(recommendation_block, weak_blocks)


def _should_promote_clean_recommendation_alternative(primary_block: dict, alternative_block: dict) -> bool:
    primary_amount = _coerce_optional_float(primary_block.get("suggested_amount")) or 0.0
    alternative_amount = _coerce_optional_float(alternative_block.get("suggested_amount")) or 0.0
    if primary_amount <= 0:
        return alternative_amount > 0
    return alternative_amount >= (primary_amount * 0.5)


def _build_decision_recommendation(
    monthly_plan: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict:
    monthly_plan = monthly_plan or {}
    recommended_blocks = list(monthly_plan.get("recommended_blocks") or [])
    primary_block = next(iter(recommended_blocks), None)
    if not primary_block:
        return {
            "block": None,
            "amount": None,
            "reason": "Todavia no hay un bloque dominante para este mes.",
            "has_recommendation": False,
            "priority_label": "Sin prioridad",
            "priority_tone": "secondary",
            "is_conditioned_by_parking": False,
        }
    block_label = primary_block.get("label")
    reason = str(primary_block.get("reason") or "").strip()
    parking_overlap = _is_parking_overlap_with_recommendation(
        block_label,
        (parking_feature or {}).get("parking_blocks") or [],
    )
    market_history_overlap = _is_market_history_overlap_with_recommendation(
        block_label,
        (market_history_feature or {}).get("weak_blocks") or [],
    )
    if market_history_overlap:
        clean_alternative = next(
            (
                block for block in recommended_blocks[1:]
                if not _is_market_history_overlap_with_recommendation(
                    str(block.get("label") or "").strip(),
                    (market_history_feature or {}).get("weak_blocks") or [],
                )
                and _should_promote_clean_recommendation_alternative(primary_block, block)
            ),
            None,
        )
        if clean_alternative is not None:
            alternative_label = str(clean_alternative.get("label") or "").strip()
            alternative_reason = str(clean_alternative.get("reason") or "").strip()
            return {
                "block": alternative_label,
                "amount": _coerce_optional_float(clean_alternative.get("suggested_amount")),
                "reason": (
                    f"Se prioriza {alternative_label} porque el bloque original {block_label} viene con liquidez reciente debil. "
                    f"{alternative_reason or 'La alternativa limpia conserva una asignacion razonable dentro del mismo plan mensual.'}"
                ).strip(),
                "has_recommendation": True,
                "priority_label": "Repriorizada por liquidez reciente",
                "priority_tone": "warning",
                "is_conditioned_by_parking": False,
                "is_conditioned_by_market_history": False,
                "was_reprioritized_by_market_history": True,
                "original_block_label": block_label,
            }
    if parking_overlap:
        reason = f"{reason} Hay parking visible dentro de este mismo bloque y conviene revisar la restriccion antes de ejecutar."
    elif market_history_overlap:
        reason = f"{reason} La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de tomarlo como prioridad limpia."
    return {
        "block": block_label,
        "amount": _coerce_optional_float(primary_block.get("suggested_amount")),
        "reason": reason,
        "has_recommendation": True,
        "priority_label": "Condicionada" if (parking_overlap or market_history_overlap) else "Prioritaria",
        "priority_tone": "warning" if (parking_overlap or market_history_overlap) else "success",
        "is_conditioned_by_parking": parking_overlap,
        "is_conditioned_by_market_history": market_history_overlap,
        "was_reprioritized_by_market_history": False,
        "original_block_label": block_label,
    }


def _build_decision_suggested_assets(
    ranking: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> list[Dict]:
    ranking = ranking or {}
    assets = []
    for item in (ranking.get("candidate_assets") or []):
        block_label = item.get("block_label")
        conditioned_by_parking = _is_parking_overlap_with_recommendation(
            block_label,
            (parking_feature or {}).get("parking_blocks") or [],
        )
        conditioned_by_market_history = _is_market_history_overlap_with_recommendation(
            block_label,
            (market_history_feature or {}).get("weak_blocks") or [],
        )
        if conditioned_by_parking:
            priority_label = "Condicionado por parking"
        elif conditioned_by_market_history:
            priority_label = "Condicionado por liquidez reciente"
        else:
            priority_label = ""
        assets.append(
            {
                "symbol": item.get("asset"),
                "block": block_label,
                "score": _coerce_optional_float(item.get("score")),
                "reason": item.get("main_reason"),
                "is_conditioned_by_parking": conditioned_by_parking,
                "is_conditioned_by_market_history": conditioned_by_market_history,
                "priority_label": priority_label,
                "market_history_note": (
                    "La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de usarlo como candidato principal."
                    if conditioned_by_market_history
                    else ""
                ),
            }
        )
    assets.sort(
        key=lambda item: (
            1 if item["is_conditioned_by_parking"] else 0,
            1 if item["is_conditioned_by_market_history"] else 0,
            -(item["score"] or 0),
        )
    )
    return assets[:3]


def _build_purchase_plan_blocks(purchase_plan: list[Dict]) -> list[str]:
    symbols = [str(item.get("symbol") or "").strip().upper() for item in purchase_plan if item.get("symbol")]
    if not symbols:
        return []
    parametros = ParametroActivo.objects.filter(simbolo__in=symbols)
    labels: list[str] = []
    for parametro in parametros:
        label = str(getattr(parametro, "bloque_estrategico", "") or "").strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _annotate_decision_proposal_with_market_context(
    proposal: Dict,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict:
    annotated = dict(proposal or {})
    purchase_plan = list(annotated.get("purchase_plan") or [])
    purchase_plan_blocks = _build_purchase_plan_blocks(purchase_plan)
    parking_overlap = any(
        _is_parking_overlap_with_recommendation(block_label, (parking_feature or {}).get("parking_blocks") or [])
        for block_label in purchase_plan_blocks
    )
    market_history_overlap = any(
        _is_market_history_overlap_with_recommendation(block_label, (market_history_feature or {}).get("weak_blocks") or [])
        for block_label in purchase_plan_blocks
    )
    if parking_overlap:
        priority_label = "Condicionada por parking"
        priority_tone = "warning"
        note = "La propuesta preferida cae en un bloque con parking visible y conviene revisarla antes de tomarla como ejecucion directa."
    elif market_history_overlap:
        priority_label = "Condicionada por liquidez reciente"
        priority_tone = "warning"
        note = "La propuesta preferida cae en un bloque con liquidez reciente debil y conviene revisar spread y actividad antes de ejecutarla."
    else:
        priority_label = "Lista"
        priority_tone = "success"
        note = ""
    annotated.update(
        {
            "purchase_plan": purchase_plan,
            "purchase_plan_blocks": purchase_plan_blocks,
            "is_conditioned_by_parking": parking_overlap,
            "is_conditioned_by_market_history": market_history_overlap,
            "priority_label": priority_label,
            "priority_tone": priority_tone,
            "parking_note": note,
            "was_reprioritized_by_parking": False,
            "was_reprioritized_by_market_history": False,
        }
    )
    return annotated


def _should_promote_clean_alternative(conditioned: Dict, clean: Dict) -> bool:
    conditioned_score = _coerce_optional_float(conditioned.get("comparison_score"))
    clean_score = _coerce_optional_float(clean.get("comparison_score"))
    if clean_score is None:
        return False
    if conditioned_score is None:
        return True
    return clean_score >= (conditioned_score - 0.25)


def _build_decision_preferred_proposal(
    preferred_payload: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict | None:
    preferred_payload = preferred_payload or {}
    preferred = preferred_payload.get("preferred")
    if not preferred:
        return None

    def normalize_candidate(item: Dict) -> Dict:
        simulation = item.get("simulation") or {}
        return {
            "proposal_key": item.get("proposal_key"),
            "proposal_label": item.get("proposal_label") or item.get("label"),
            "source_label": item.get("source_label"),
            "comparison_score": _coerce_optional_float(item.get("comparison_score")),
            "purchase_plan": list(item.get("purchase_plan") or []),
            "purchase_summary": item.get("purchase_summary") or build_incremental_purchase_plan_summary(
                list(item.get("purchase_plan") or [])
            ),
            "simulation_delta": dict(simulation.get("delta") or item.get("simulation_delta") or {}),
            "simulation_interpretation": str(simulation.get("interpretation") or item.get("simulation_interpretation") or ""),
            "priority_rank": int(item.get("priority_rank") or 0),
        }

    raw_candidates = [normalize_candidate(item) for item in (preferred_payload.get("candidates") or [])]
    if not raw_candidates:
        raw_candidates = [normalize_candidate(preferred)]

    annotated_candidates = [
        _annotate_decision_proposal_with_market_context(
            item,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        for item in raw_candidates
    ]

    selected = next(
        (
            item for item in annotated_candidates
            if item.get("proposal_key") == preferred.get("proposal_key")
        ),
        annotated_candidates[0],
    )

    if selected.get("is_conditioned_by_parking"):
        clean_candidates = [
            item for item in annotated_candidates
            if not item.get("is_conditioned_by_parking")
            and not item.get("is_conditioned_by_market_history")
            and _should_promote_clean_alternative(selected, item)
        ]
        if clean_candidates:
            selected = sorted(
                clean_candidates,
                key=lambda item: (
                    float(item.get("comparison_score") if item.get("comparison_score") is not None else float("-inf")),
                    int(item.get("priority_rank") or 0),
                ),
                reverse=True,
            )[0]
            selected["was_reprioritized_by_parking"] = True
            selected["priority_label"] = "Repriorizada por parking"
            selected["priority_tone"] = "info"
            selected["parking_note"] = (
                "Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con parking visible."
            )
    elif selected.get("is_conditioned_by_market_history"):
        clean_candidates = [
            item for item in annotated_candidates
            if not item.get("is_conditioned_by_parking")
            and not item.get("is_conditioned_by_market_history")
            and _should_promote_clean_alternative(selected, item)
        ]
        if clean_candidates:
            selected = sorted(
                clean_candidates,
                key=lambda item: (
                    float(item.get("comparison_score") if item.get("comparison_score") is not None else float("-inf")),
                    int(item.get("priority_rank") or 0),
                ),
                reverse=True,
            )[0]
            selected["was_reprioritized_by_market_history"] = True
            selected["priority_label"] = "Repriorizada por liquidez reciente"
            selected["priority_tone"] = "info"
            selected["parking_note"] = (
                "Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con liquidez reciente debil."
            )

    return selected


def _build_decision_expected_impact(simulation: Dict | None) -> Dict:
    simulation = simulation or {}
    delta = dict(simulation.get("delta") or {})
    expected_return = _coerce_optional_float(delta.get("expected_return_change"))
    fragility = _coerce_optional_float(delta.get("fragility_change"))
    worst_case = _coerce_optional_float(delta.get("scenario_loss_change"))
    risk_concentration = _coerce_optional_float(delta.get("risk_concentration_change"))

    favorable = 0
    unfavorable = 0
    if expected_return is not None:
        favorable += 1 if expected_return >= 0 else 0
        unfavorable += 1 if expected_return < 0 else 0
    if fragility is not None:
        favorable += 1 if fragility <= 0 else 0
        unfavorable += 1 if fragility > 0 else 0
    if worst_case is not None:
        favorable += 1 if worst_case >= 0 else 0
        unfavorable += 1 if worst_case < 0 else 0
    if risk_concentration is not None:
        favorable += 1 if risk_concentration <= 0 else 0
        unfavorable += 1 if risk_concentration > 0 else 0

    if favorable and not unfavorable:
        status = "positive"
        score_component = 25
    elif unfavorable and not favorable:
        status = "negative"
        score_component = 5
    elif favorable or unfavorable:
        status = "mixed"
        score_component = 14
    else:
        status = "neutral"
        score_component = 12

    return {
        "return": expected_return,
        "fragility": fragility,
        "worst_case": worst_case,
        "risk_concentration": risk_concentration,
        "status": status,
        "score_component": score_component,
        "summary": str(simulation.get("interpretation") or "Impacto incremental no disponible."),
    }


def _compute_decision_score(
    *,
    macro_state: Dict,
    portfolio_state: Dict,
    recommendation: Dict,
    suggested_assets: list[Dict],
    preferred_proposal: Dict | None,
    expected_impact: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> int:
    recommendation_score = 0
    if recommendation.get("has_recommendation"):
        recommendation_score += 10
    if suggested_assets:
        recommendation_score += 5
    if len(suggested_assets) >= 2:
        recommendation_score += 3
    if preferred_proposal:
        recommendation_score += 7
    recommendation_score = min(recommendation_score, 25)

    total = (
        int(macro_state.get("score_component") or 0)
        + int(portfolio_state.get("score_component") or 0)
        + recommendation_score
        + int(expected_impact.get("score_component") or 0)
    )
    if (parking_signal or {}).get("has_signal"):
        total -= 5
    if (market_history_signal or {}).get("has_signal"):
        total -= 4
    if (operation_execution_signal or {}).get("status") in {"missing", "partial"}:
        total -= 4
    elif (operation_execution_signal or {}).get("status") == "fragmented":
        total -= 2
    elif (operation_execution_signal or {}).get("status") == "costly":
        total -= 3
    elif (operation_execution_signal or {}).get("status") == "watch_cost":
        total -= 1
    return max(0, min(100, total))


def _build_decision_recommendation_context(portfolio_scope: Dict | None) -> str | None:
    portfolio_scope = portfolio_scope or {}
    cash_ratio_total = _coerce_optional_float(portfolio_scope.get("cash_ratio_total")) or 0.0
    invested_ratio_total = _coerce_optional_float(portfolio_scope.get("invested_ratio_total")) or 0.0

    if cash_ratio_total > 0.30:
        return "high_cash"
    if invested_ratio_total > 0.90:
        return "fully_invested"
    return None


def _build_decision_strategy_bias(recommendation_context: str | None) -> str | None:
    if recommendation_context == "high_cash":
        return "deploy_cash"
    if recommendation_context == "fully_invested":
        return "rebalance"
    return None


def _build_decision_parking_signal(parking_feature: Dict | None) -> Dict:
    parking_feature = parking_feature or {}
    summary = parking_feature.get("summary") or {}
    parking_count = int(summary.get("parking_count") or 0)
    parking_value_total = summary.get("parking_value_total") or Decimal("0")

    if not parking_feature.get("has_visible_parking") or parking_count <= 0:
        return {
            "has_signal": False,
            "severity": "info",
            "title": "",
            "summary": "",
            "parking_count": 0,
            "parking_value_total": Decimal("0"),
        }

    return {
        "has_signal": True,
        "severity": "warning",
        "title": "Parking visible antes de reforzar",
        "summary": f"Hay {parking_count} posicion(es) con parking visible por {parking_value_total.quantize(Decimal('0.01'))}.",
        "parking_count": parking_count,
        "parking_value_total": parking_value_total,
    }


def _build_decision_market_history_signal(
    *,
    market_history_feature: Dict | None,
    recommendation: Dict | None,
    preferred_proposal: Dict | None,
) -> Dict:
    market_history_feature = market_history_feature or {}
    weak_blocks = {
        str(item.get("label") or "").strip()
        for item in market_history_feature.get("weak_blocks", [])
        if str(item.get("label") or "").strip()
    }
    overlap_blocks = []
    recommendation_block = str((recommendation or {}).get("block") or "").strip()
    if recommendation_block and recommendation_block in weak_blocks:
        overlap_blocks.append(recommendation_block)
    original_block_label = str((recommendation or {}).get("original_block_label") or "").strip()
    if (
        original_block_label
        and original_block_label in weak_blocks
        and original_block_label not in overlap_blocks
        and (
            (recommendation or {}).get("was_reprioritized_by_market_history")
            or (recommendation or {}).get("is_conditioned_by_market_history")
        )
    ):
        overlap_blocks.append(original_block_label)
    for block in (preferred_proposal or {}).get("purchase_plan_blocks") or []:
        block_label = str(block or "").strip()
        if block_label and block_label in weak_blocks and block_label not in overlap_blocks:
            overlap_blocks.append(block_label)

    if not overlap_blocks:
        return {
            "has_signal": False,
            "title": "",
            "summary": "",
            "overlap_blocks": [],
        }

    overlap_rows = [
        row for row in market_history_feature.get("rows", [])
        if str(row.get("bloque_estrategico") or "").strip() in set(overlap_blocks)
        and row.get("quality_status") == "weak"
    ]
    overlap_symbols = ", ".join(row["simbolo"] for row in overlap_rows[:3])
    summary = (
        f"El bloque sugerido viene con liquidez reciente debil en {', '.join(overlap_blocks)}."
    )
    if overlap_symbols:
        summary += f" Revisar spread y actividad reciente en {overlap_symbols} antes de comprar."

    return {
        "has_signal": True,
        "title": "Liquidez reciente debil en la zona sugerida",
        "summary": summary,
        "overlap_blocks": overlap_blocks,
    }


def _build_decision_operation_execution_signal(
    *,
    operation_execution_feature: Dict | None,
    preferred_proposal: Dict | None,
) -> Dict:
    operation_execution_feature = operation_execution_feature or {}
    preferred_proposal = preferred_proposal or {}
    tracked_symbols = list(operation_execution_feature.get("tracked_symbols") or [])
    matched_symbols_count = int(operation_execution_feature.get("matched_symbols_count") or 0)
    missing_symbols_count = int(operation_execution_feature.get("missing_symbols_count") or 0)
    execution_analytics = operation_execution_feature.get("execution_analytics") or {}
    fragmented_pct = Decimal(str(execution_analytics.get("fragmented_pct") or 0))
    observed_cost_status = str(execution_analytics.get("observed_cost_status") or "missing").strip()
    observed_cost_pct = Decimal(str(execution_analytics.get("fee_over_visible_amount_pct") or 0))
    coverage_pct = Decimal(str(operation_execution_feature.get("coverage_pct") or 0))

    if not preferred_proposal or not tracked_symbols:
        return {
            "has_signal": False,
            "severity": "info",
            "title": "",
            "summary": "",
            "status": "none",
            "tracked_symbols": tracked_symbols,
            "matched_symbols_count": matched_symbols_count,
            "missing_symbols_count": missing_symbols_count,
        }

    if matched_symbols_count == 0:
        return {
            "has_signal": True,
            "severity": "warning",
            "title": "Sin huella operativa comparable",
            "summary": "La propuesta no tiene compras o ventas terminadas recientes para validar costo o forma real de ejecucion.",
            "status": "missing",
            "tracked_symbols": tracked_symbols,
            "matched_symbols_count": matched_symbols_count,
            "missing_symbols_count": missing_symbols_count,
        }

    if missing_symbols_count > 0 or coverage_pct < Decimal("100"):
        return {
            "has_signal": True,
            "severity": "warning",
            "title": "Cobertura operativa parcial",
            "summary": f"Solo {matched_symbols_count} de {len(tracked_symbols)} simbolo(s) sugeridos tienen ejecucion terminada reciente visible.",
            "status": "partial",
            "tracked_symbols": tracked_symbols,
            "matched_symbols_count": matched_symbols_count,
            "missing_symbols_count": missing_symbols_count,
        }

    if fragmented_pct >= Decimal("50"):
        return {
            "has_signal": True,
            "severity": "info",
            "title": "Ejecucion reciente fragmentada",
            "summary": "La propuesta tiene referencia operativa reciente, pero con multiples fills en una parte relevante de las operaciones comparables.",
            "status": "fragmented",
            "tracked_symbols": tracked_symbols,
            "matched_symbols_count": matched_symbols_count,
            "missing_symbols_count": missing_symbols_count,
        }

    if observed_cost_status == "high":
        return {
            "has_signal": True,
            "severity": "warning",
            "title": "Costo observado alto",
            "summary": f"La huella operativa reciente muestra aranceles visibles cercanos a {observed_cost_pct}% del monto comparable.",
            "status": "costly",
            "tracked_symbols": tracked_symbols,
            "matched_symbols_count": matched_symbols_count,
            "missing_symbols_count": missing_symbols_count,
        }

    if observed_cost_status == "watch":
        return {
            "has_signal": True,
            "severity": "info",
            "title": "Costo observado a vigilar",
            "summary": f"La huella operativa reciente muestra aranceles visibles cercanos a {observed_cost_pct}% del monto comparable.",
            "status": "watch_cost",
            "tracked_symbols": tracked_symbols,
            "matched_symbols_count": matched_symbols_count,
            "missing_symbols_count": missing_symbols_count,
        }

    return {
        "has_signal": False,
        "severity": "success",
        "title": "",
        "summary": "",
        "status": "clean",
        "tracked_symbols": tracked_symbols,
        "matched_symbols_count": matched_symbols_count,
        "missing_symbols_count": missing_symbols_count,
    }


def _manual_execution_readiness_rank(status: str) -> int:
    normalized = str(status or "pending").strip()
    if normalized == "ready":
        return 3
    if normalized == "monitor":
        return 2
    if normalized == "review_execution":
        return 1
    return 0


def _build_manual_incremental_execution_readiness(
    *,
    proposal: Dict | None,
    operation_execution_signal: Dict | None = None,
) -> Dict:
    proposal = proposal or {}
    operation_execution_signal = operation_execution_signal or {}
    proposal_label = str(proposal.get("proposal_label") or proposal.get("label") or "este plan").strip()
    execution_quality = proposal.get("execution_quality") or {}
    execution_order_summary = str(execution_quality.get("execution_order_summary") or "").strip()
    signal_status = str(operation_execution_signal.get("status") or "none").strip()

    if signal_status in {"missing", "partial"}:
        return {
            "status": "review_execution",
            "label": "Validar ejecucion",
            "tone": "warning",
            "summary": execution_order_summary or f"{proposal_label} necesita validar mejor su ejecucion real antes de pasar a compra.",
        }
    if signal_status in {"fragmented", "costly", "watch_cost"}:
        return {
            "status": "monitor",
            "label": "Seguir observando",
            "tone": "secondary",
            "summary": (
                operation_execution_signal.get("summary")
                or execution_order_summary
                or f"{proposal_label} tiene referencia operativa, pero conviene cuidar la forma de entrada."
            ),
        }
    if proposal:
        return {
            "status": "ready",
            "label": "Listo para ejecutar",
            "tone": "success",
            "summary": execution_order_summary or f"{proposal_label} ya tiene fit operativo suficiente para ejecutarse como mejor plan manual.",
        }
    return {
        "status": "pending",
        "label": "Sin lectura",
        "tone": "secondary",
        "summary": "",
    }


def _build_manual_incremental_execution_readiness_summary(best_proposal: Dict | None) -> Dict:
    best_proposal = best_proposal or {}
    readiness = dict(best_proposal.get("execution_readiness") or {})
    if not best_proposal or not readiness:
        return {
            "has_summary": False,
            "status": "pending",
            "label": "",
            "tone": "secondary",
            "headline": "",
            "summary": "",
        }
    proposal_label = str(best_proposal.get("proposal_label") or best_proposal.get("label") or "este plan").strip()
    status = str(readiness.get("status") or "pending")
    if status == "ready":
        headline = f"{proposal_label} es el mejor plan manual y hoy queda listo para ejecutar."
    elif status == "review_execution":
        headline = f"{proposal_label} lidera el comparador manual, pero pide validar ejecucion antes de comprar."
    else:
        headline = f"{proposal_label} lidera el comparador manual, pero por ahora conviene seguir observando su forma de entrada."
    return {
        "has_summary": True,
        "status": status,
        "label": readiness.get("label") or "",
        "tone": readiness.get("tone") or "secondary",
        "headline": headline,
        "summary": readiness.get("summary") or "",
    }


def _annotate_preferred_proposal_with_execution_quality(
    preferred_proposal: Dict | None,
    *,
    operation_execution_feature: Dict | None = None,
) -> Dict | None:
    if not preferred_proposal:
        return None

    enriched = dict(preferred_proposal)
    operation_execution_feature = operation_execution_feature or {}
    rows = list(operation_execution_feature.get("rows") or [])
    rows_by_symbol = {
        str(row.get("simbolo") or "").strip().upper(): row
        for row in rows
        if str(row.get("simbolo") or "").strip()
    }

    purchase_rows = []
    for purchase in list(enriched.get("purchase_plan") or []):
        symbol = str((purchase or {}).get("symbol") or "").strip().upper()
        operation_row = rows_by_symbol.get(symbol)
        if operation_row:
            coverage_status = "covered"
            coverage_label = "Con huella real"
            if operation_row.get("is_fragmented"):
                execution_label = "Fragmentada"
                execution_tone = "warning"
            elif str(operation_row.get("cost_status") or "") == "high":
                execution_label = "Costo alto"
                execution_tone = "warning"
            elif str(operation_row.get("cost_status") or "") == "watch":
                execution_label = "Costo a vigilar"
                execution_tone = "secondary"
            elif (operation_row.get("fees_ars") or 0) or (operation_row.get("fees_usd") or 0):
                execution_label = "Costo visible"
                execution_tone = "success"
            else:
                execution_label = "Parcial"
                execution_tone = "secondary"
        else:
            coverage_status = "missing"
            coverage_label = "Sin huella real"
            execution_label = "Sin referencia"
            execution_tone = "warning"

        purchase_rows.append(
            {
                "symbol": symbol,
                "amount": (purchase or {}).get("amount"),
                "has_execution_row": bool(operation_row),
                "coverage_status": coverage_status,
                "coverage_label": coverage_label,
                "execution_label": execution_label,
                "execution_tone": execution_tone,
                "fills_count": int((operation_row or {}).get("fills_count") or 0),
                "fee_over_amount_pct": (operation_row or {}).get("fee_over_amount_pct"),
                "cost_status": (operation_row or {}).get("cost_status") or "",
                "executed_amount": (operation_row or {}).get("executed_amount"),
                "fecha_label": (operation_row or {}).get("fecha_label") or "",
            }
        )

    best_row = next(
        (
            row for row in purchase_rows
            if row["coverage_status"] == "covered" and row["execution_tone"] == "success"
        ),
        None,
    )
    if best_row is None:
        best_row = next((row for row in purchase_rows if row["coverage_status"] == "covered"), None)
    weakest_row = next((row for row in purchase_rows if row["coverage_status"] == "missing"), None)
    if weakest_row is None:
        weakest_row = next((row for row in purchase_rows if row["execution_tone"] == "warning"), None)

    if best_row and weakest_row and best_row["symbol"] != weakest_row["symbol"]:
        execution_summary = (
            f"{best_row['symbol']} hoy tiene la mejor huella operativa visible; "
            f"{weakest_row['symbol']} pide mas validacion antes de ejecutarlo."
        )
        execution_order_label = "Ejecutar primero"
        execution_order_summary = (
            f"Arrancar por {best_row['symbol']} y dejar {weakest_row['symbol']} para una validacion adicional."
        )
    elif best_row:
        execution_summary = f"{best_row['symbol']} es el tramo con mejor referencia operativa visible dentro de la propuesta."
        execution_order_label = "Ejecutar primero"
        execution_order_summary = f"Si avanzas con esta propuesta, conviene empezar por {best_row['symbol']}."
    elif weakest_row:
        execution_summary = f"{weakest_row['symbol']} sigue sin una referencia operativa comparable suficiente."
        execution_order_label = "Validar primero"
        execution_order_summary = f"Antes de ejecutar la propuesta, conviene validar mejor {weakest_row['symbol']}."
    else:
        execution_summary = ""
        execution_order_label = ""
        execution_order_summary = ""

    enriched["execution_quality"] = {
        "has_rows": bool(purchase_rows),
        "rows": purchase_rows,
        "best_symbol": (best_row or {}).get("symbol") or "",
        "weakest_symbol": (weakest_row or {}).get("symbol") or "",
        "summary": execution_summary,
        "execution_order_label": execution_order_label,
        "execution_order_summary": execution_order_summary,
    }
    return enriched


def _build_decision_action_suggestions(
    strategy_bias: str | None,
    *,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> list[Dict]:
    suggestions = []
    if strategy_bias == "deploy_cash":
        suggestions.append(
            {
                "type": "allocation",
                "message": "Tenés capital disponible para invertir",
                "suggestion": "Evaluar asignar entre 20% y 40% del cash.",
            }
        )
    elif strategy_bias == "rebalance":
        suggestions.append(
            {
                "type": "rebalance",
                "message": "Cartera altamente invertida",
                "suggestion": "Evaluar reducción de concentración en top posiciones.",
            }
        )
    if (parking_signal or {}).get("has_signal"):
        suggestions.append(
            {
                "type": "parking",
                "message": "Hay posiciones con parking visible en cartera",
                "suggestion": "Conviene revisar esas restricciones antes de reforzar la misma zona de exposicion.",
            }
        )
    if (market_history_signal or {}).get("has_signal"):
        suggestions.append(
            {
                "type": "market_history",
                "message": "La liquidez reciente del bloque sugerido viene debil",
                "suggestion": "Conviene priorizar compras en zonas con mejor spread y actividad reciente o esperar un punto de entrada mas limpio.",
            }
        )
    if (operation_execution_signal or {}).get("status") in {"missing", "partial"}:
        suggestions.append(
            {
                "type": "operation_execution",
                "message": "La propuesta todavia tiene poca evidencia operativa comparable",
                "suggestion": "Conviene validar costo observado y forma real de ejecucion antes de tomarla como compra prioritaria.",
            }
        )
    elif (operation_execution_signal or {}).get("status") in {"costly", "watch_cost"}:
        suggestions.append(
            {
                "type": "operation_cost",
                "message": "La huella reciente muestra friccion operativa visible",
                "suggestion": "Conviene revisar aranceles observados y tamano de orden antes de priorizar esta compra.",
            }
        )
    return suggestions


def _build_decision_execution_gate(
    *,
    parking_signal: Dict | None,
    operation_execution_signal: Dict | None = None,
    preferred_proposal: Dict | None,
) -> Dict:
    if (parking_signal or {}).get("has_signal") or (preferred_proposal or {}).get("is_conditioned_by_parking"):
        return {
            "has_blocker": True,
            "key": "review_parking",
            "status": "review_parking",
            "title": "Revisar restricciones antes de ejecutar",
            "summary": "La propuesta puede seguir siendo valida, pero conviene revisar primero el parking visible antes de desplegar mas capital.",
            "primary_cta_label": "Revisar antes de ejecutar",
            "primary_cta_tone": "warning",
        }
    if (operation_execution_signal or {}).get("status") in {"missing", "partial"}:
        return {
            "has_blocker": True,
            "key": "review_execution",
            "status": "review_execution",
            "title": "Validar ejecucion real antes de comprar",
            "summary": (operation_execution_signal or {}).get("summary") or "La propuesta no tiene evidencia operativa comparable suficiente todavia.",
            "primary_cta_label": "Validar ejecucion antes de comprar",
            "primary_cta_tone": "warning",
        }
    if preferred_proposal:
        return {
            "has_blocker": False,
            "key": "ready",
            "status": "ready",
            "title": "",
            "summary": "",
            "primary_cta_label": "Ejecutar decisión",
            "primary_cta_tone": "success",
        }
    return {
        "has_blocker": False,
        "status": "pending",
        "title": "",
        "summary": "",
        "primary_cta_label": "Ejecutar decisión",
        "primary_cta_tone": "success",
    }


def _compute_decision_confidence(
    *,
    macro_state: Dict,
    portfolio_state: Dict,
    preferred_proposal: Dict | None,
    expected_impact: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> str:
    if preferred_proposal is None:
        return "Baja"
    if expected_impact.get("status") == "negative":
        return "Baja"
    if macro_state.get("key") == "crisis":
        return "Baja"
    if (
        macro_state.get("key") == "normal"
        and portfolio_state.get("key") != "riesgo"
        and expected_impact.get("status") in {"positive", "neutral"}
    ):
        confidence = "Alta"
    else:
        confidence = "Media"

    if (
        (parking_signal or {}).get("has_signal")
        or (preferred_proposal or {}).get("was_reprioritized_by_parking")
        or (preferred_proposal or {}).get("is_conditioned_by_parking")
        or (market_history_signal or {}).get("has_signal")
        or (preferred_proposal or {}).get("is_conditioned_by_market_history")
        or (operation_execution_signal or {}).get("status") in {"missing", "partial", "fragmented", "costly", "watch_cost"}
    ):
        if confidence == "Alta":
            return "Media"
        return "Baja"
    return confidence


def _build_decision_explanation(
    *,
    macro_state: Dict,
    recommendation: Dict,
    expected_impact: Dict,
    confidence: str,
    preferred_proposal: Dict | None,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> list[str]:
    recommendation_block = recommendation.get("block") or "el bloque sugerido"
    recommendation_reason = recommendation.get("reason") or "es la prioridad mas clara del mes"
    proposal_label = (preferred_proposal or {}).get("proposal_label") or "la mejor propuesta disponible"

    risk_line = "El riesgo no aumenta materialmente con la propuesta actual."
    if expected_impact.get("status") == "negative" or confidence == "Baja":
        risk_line = "El riesgo pide revision adicional antes de ejecutar la decision."
    elif expected_impact.get("status") == "mixed":
        risk_line = "El riesgo queda controlado, pero conviene revisar las senales mixtas."

    bullets = [
        f"Se refuerza {recommendation_block} porque {recommendation_reason}.",
        f"El contexto macro esta en {str(macro_state.get('label') or 'Indefinido').lower()} y {macro_state.get('summary') or 'no invalida la decision principal'}.",
        f"El impacto esperado de {proposal_label} es {expected_impact.get('status') or 'neutral'} en retorno, fragilidad y peor escenario.",
        risk_line,
    ]
    if (parking_signal or {}).get("has_signal"):
        bullets.append("Hay parking visible en cartera y conviene revisar esas restricciones antes de ejecutar la propuesta.")
    if recommendation.get("was_reprioritized_by_parking"):
        bullets.append("La recomendacion principal fue repriorizada porque el bloque original quedaba condicionado por parking visible.")
    elif recommendation.get("is_conditioned_by_parking"):
        bullets.append("La recomendacion principal quedo condicionada por parking visible en el mismo bloque estrategico.")
    if recommendation.get("was_reprioritized_by_market_history"):
        bullets.append("La recomendacion principal fue repriorizada porque el bloque original mostraba liquidez reciente debil.")
    elif recommendation.get("is_conditioned_by_market_history") or (market_history_signal or {}).get("has_signal"):
        bullets.append("La liquidez reciente del bloque sugerido pide validar mejor la ejecucion antes de comprar.")
    if (operation_execution_signal or {}).get("status") == "missing":
        bullets.append("La propuesta no tiene huella operativa comparable reciente y conviene validar costo real de ejecucion antes de comprar.")
    elif (operation_execution_signal or {}).get("status") == "partial":
        bullets.append("La propuesta solo tiene cobertura operativa parcial y pide confirmar la ejecucion real de todos los simbolos sugeridos.")
    elif (operation_execution_signal or {}).get("status") == "fragmented":
        bullets.append("La referencia operativa reciente existe, pero muestra fragmentacion y conviene cuidar la forma de entrada.")
    elif (operation_execution_signal or {}).get("status") == "costly":
        bullets.append("La huella operativa reciente muestra costo observado alto y conviene revisar aranceles reales antes de comprar.")
    elif (operation_execution_signal or {}).get("status") == "watch_cost":
        bullets.append("La huella operativa reciente muestra una friccion moderada y conviene monitorear mejor el costo visible de ejecucion.")
    if (preferred_proposal or {}).get("was_reprioritized_by_parking"):
        bullets.append("La propuesta preferida guardable fue reemplazada por una alternativa mas limpia frente a parking visible.")
    elif (preferred_proposal or {}).get("was_reprioritized_by_market_history"):
        bullets.append("La propuesta preferida guardable fue reemplazada por una alternativa con liquidez reciente mas limpia.")
    return bullets[:8]


def _build_decision_tracking_payload(
    *,
    preferred_proposal: Dict | None,
    recommendation: Dict,
    expected_impact: Dict,
    score: int,
    confidence: str,
    macro_state: Dict,
    portfolio_state: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
    execution_gate: Dict | None = None,
) -> Dict:
    preferred_proposal = preferred_proposal or {}
    parking_signal = parking_signal or {}
    market_history_signal = market_history_signal or {}
    operation_execution_signal = operation_execution_signal or {}
    execution_gate = execution_gate or {}
    return {
        "recommended_block": recommendation.get("block"),
        "recommended_amount": recommendation.get("amount"),
        "preferred_proposal": {
            "proposal_key": preferred_proposal.get("proposal_key"),
            "proposal_label": preferred_proposal.get("proposal_label"),
            "source_label": preferred_proposal.get("source_label"),
        },
        "purchase_plan": list(preferred_proposal.get("purchase_plan") or []),
        "simulation_delta": dict(preferred_proposal.get("simulation_delta") or {}),
        "score": score,
        "confidence": confidence,
        "macro_state": macro_state.get("key"),
        "portfolio_state": portfolio_state.get("key"),
        "expected_impact_status": expected_impact.get("status"),
        "governance": {
            "execution_gate_key": execution_gate.get("key"),
            "parking_signal_active": bool(parking_signal.get("has_signal")),
            "parking_blocks": [
                str(item.get("label") or "").strip()
                for item in (parking_signal.get("parking_blocks") or [])
                if str(item.get("label") or "").strip()
            ],
            "market_history_signal_active": bool(market_history_signal.get("has_signal")),
            "market_history_blocks": [
                str(item.get("label") or "").strip()
                for item in (
                    [{"label": block} for block in (market_history_signal.get("overlap_blocks") or [])]
                )
                if str(item.get("label") or "").strip()
            ],
            "operation_execution_signal_active": bool(operation_execution_signal.get("has_signal")),
            "operation_execution_signal_status": operation_execution_signal.get("status"),
            "operation_execution_tracked_symbols": list(operation_execution_signal.get("tracked_symbols") or []),
            "recommendation": {
                "block": recommendation.get("block"),
                "priority_label": recommendation.get("priority_label"),
                "conditioned_by_parking": bool(recommendation.get("is_conditioned_by_parking")),
                "reprioritized_by_parking": bool(recommendation.get("was_reprioritized_by_parking")),
                "conditioned_by_market_history": bool(recommendation.get("is_conditioned_by_market_history")),
                "reprioritized_by_market_history": bool(recommendation.get("was_reprioritized_by_market_history")),
                "original_block_label": recommendation.get("original_block_label"),
            },
            "preferred_proposal": {
                "proposal_label": preferred_proposal.get("proposal_label"),
                "conditioned_by_parking": bool(preferred_proposal.get("is_conditioned_by_parking")),
                "reprioritized_by_parking": bool(preferred_proposal.get("was_reprioritized_by_parking")),
                "conditioned_by_market_history": bool(preferred_proposal.get("is_conditioned_by_market_history")),
                "reprioritized_by_market_history": bool(preferred_proposal.get("was_reprioritized_by_market_history")),
            },
        },
    }
