import hashlib
import json
from typing import Dict

from apps.core.services.candidate_asset_ranking_service import CandidateAssetRankingService
from apps.core.services.incremental_portfolio_simulator import IncrementalPortfolioSimulator
from apps.core.services.monthly_allocation_service import MonthlyAllocationService
from apps.dashboard.decision_engine import (
    _annotate_preferred_proposal_with_execution_quality,
    _build_decision_operation_execution_signal,
    _build_manual_incremental_execution_readiness,
    _build_manual_incremental_execution_readiness_summary,
)
from apps.dashboard.incremental_comparators import (
    _build_comparable_candidate_blocks,
    _build_incremental_comparator_summary,
    _build_incremental_readiness_filter_metadata,
    _build_incremental_readiness_filter_options,
    _build_manual_incremental_comparison_form_state,
    _build_preferred_incremental_explanation,
    _build_preferred_proposal_context,
    _build_runner_up_purchase_plan,
    _build_split_largest_block_purchase_plan,
    _build_top_candidate_purchase_plan,
    _extract_best_incremental_proposal,
    _format_incremental_readiness_filter_label,
    _normalize_incremental_proposal_item,
    _normalize_incremental_readiness_filter,
    _preferred_source_priority_rank,
    _query_param_value,
    _resolve_manual_incremental_operational_tiebreak,
    _score_incremental_simulation,
)
from apps.dashboard.operation_execution import (
    build_operation_execution_feature_context as _build_operation_execution_feature_context,
)
from apps.dashboard.selector_cache import _get_cached_selector_result, _safe_percentage


def get_monthly_allocation_plan(capital_amount: int | float = 600000) -> Dict:
    """Devuelve la propuesta mvp de asignacion mensual incremental."""
    cache_key = f"monthly_allocation_plan:{int(capital_amount)}"

    def build():
        service = MonthlyAllocationService()
        return service.build_plan(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_candidate_asset_ranking(capital_amount: int | float = 600000) -> Dict:
    """Devuelve el ranking de activos candidatos dentro de los bloques recomendados."""
    cache_key = f"candidate_asset_ranking:{int(capital_amount)}"

    def build():
        service = CandidateAssetRankingService()
        return service.build_ranking(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_operation_execution_feature_context(
    *,
    purchase_plan: list[dict] | None = None,
    lookback_days: int = 180,
    symbol_limit: int = 3,
) -> Dict:
    plan = list(purchase_plan or [])
    tracked_symbols = []
    for item in plan:
        symbol = str((item or {}).get("symbol") or "").strip().upper()
        if symbol and symbol not in tracked_symbols:
            tracked_symbols.append(symbol)
    cache_key = "operation_execution_feature:no_symbols"
    if tracked_symbols:
        cache_key = f"operation_execution_feature:{','.join(tracked_symbols)}:{int(lookback_days)}:{int(symbol_limit)}"

    def build():
        return _build_operation_execution_feature_context(
            purchase_plan=plan,
            lookback_days=lookback_days,
            symbol_limit=symbol_limit,
            safe_percentage=_safe_percentage,
        )

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation(capital_amount: int | float = 600000) -> Dict:
    """Construye una simulacion incremental default usando top candidato por bloque recomendado."""
    cache_key = f"incremental_portfolio_simulation:{int(capital_amount)}"

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        proposal = _build_top_candidate_purchase_plan(monthly_plan, candidate_ranking)
        if not proposal["purchase_plan"]:
            return {
                "capital_amount": float(capital_amount),
                "purchase_plan": [],
                "selected_candidates": [],
                "unmapped_blocks": proposal["unmapped_blocks"],
                "before": {},
                "after": {},
                "delta": {},
                "interpretation": "Todavia no hay candidatos suficientes para construir una simulacion incremental base.",
                "warnings": [],
                "selection_basis": "top_candidate_per_recommended_block",
            }

        simulator = IncrementalPortfolioSimulator()
        simulation = simulator.simulate(
            {
                "capital_amount": capital_amount,
                "purchase_plan": proposal["purchase_plan"],
            }
        )
        return {
            "capital_amount": float(capital_amount),
            "purchase_plan": proposal["purchase_plan"],
            "selected_candidates": proposal["selected_candidates"],
            "unmapped_blocks": proposal["unmapped_blocks"],
            "before": simulation["before"],
            "after": simulation["after"],
            "delta": simulation["delta"],
            "interpretation": simulation["interpretation"],
            "warnings": simulation.get("warnings", []),
            "selection_basis": "top_candidate_per_recommended_block",
        }

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation_comparison(
    query_params=None,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara variantes simples de propuestas incrementales sobre el mismo capital mensual."""
    cache_key = f"incremental_portfolio_simulation_comparison:{int(capital_amount)}"
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "comparison_readiness_filter")
    )

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        simulator = IncrementalPortfolioSimulator()

        proposals = []
        for proposal_key, label, builder in (
            ("top_candidate_per_block", "Top candidato por bloque", _build_top_candidate_purchase_plan),
            ("runner_up_when_available", "Segundo candidato si existe", _build_runner_up_purchase_plan),
            ("split_largest_block_top_two", "Split del bloque mas grande", _build_split_largest_block_purchase_plan),
        ):
            proposal = builder(monthly_plan, candidate_ranking)
            if not proposal["purchase_plan"]:
                proposals.append(
                    _normalize_incremental_proposal_item(
                        {
                            "proposal_key": proposal_key,
                            "label": label,
                            "purchase_plan": [],
                            "selected_candidates": [],
                            "unmapped_blocks": proposal["unmapped_blocks"],
                            "simulation": {
                                "before": {},
                                "after": {},
                                "delta": {
                                    "expected_return_change": None,
                                    "real_expected_return_change": None,
                                    "fragility_change": None,
                                    "scenario_loss_change": None,
                                    "risk_concentration_change": None,
                                },
                                "interpretation": "No hay candidatos suficientes para construir esta variante.",
                            },
                            "comparison_score": None,
                        }
                    )
                )
                continue

            simulation = simulator.simulate(
                {
                    "capital_amount": capital_amount,
                    "purchase_plan": proposal["purchase_plan"],
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=proposal["purchase_plan"],
                lookback_days=180,
                symbol_limit=3,
            )
            enriched = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": proposal_key,
                        "label": label,
                        "purchase_plan": proposal["purchase_plan"],
                        "selected_candidates": proposal["selected_candidates"],
                        "unmapped_blocks": proposal["unmapped_blocks"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=enriched,
            )
            enriched["operation_execution_signal"] = operation_execution_signal
            enriched["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=enriched,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(enriched)

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        operational_tiebreak = {"has_tiebreak": False, "used_operational_tiebreak": False, "headline": "", "summary": ""}
        return {
            "capital_amount": float(capital_amount),
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor balance actual",
                best_label=best["label"] if best else None,
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_manual_incremental_portfolio_simulation_comparison(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    """Compara planes incrementales definidos manualmente desde Planeacion."""
    form_state = _build_manual_incremental_comparison_form_state(
        query_params,
        default_capital_amount=default_capital_amount,
    )
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "manual_compare_readiness_filter")
    )
    normalized_plans = form_state["normalized_plans"]
    if not normalized_plans:
        empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
        empty_tiebreak = {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
            "best_execution_readiness": empty_readiness,
            "operational_tiebreak": empty_tiebreak,
            "active_readiness_filter": readiness_filter,
            "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
            "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
            "visible_count": 0,
            "total_count": 0,
            "has_active_readiness_filter": readiness_filter != "all",
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor balance manual",
                best_label=None,
                best_execution_readiness=empty_readiness,
                operational_tiebreak=empty_tiebreak,
            ),
        }

    signature = hashlib.md5(
        json.dumps(
            [
                {
                    "proposal_key": plan["proposal_key"],
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
                for plan in normalized_plans
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"manual_incremental_portfolio_simulation_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for plan in normalized_plans:
            simulation = simulator.simulate(
                {
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=plan["purchase_plan"],
                lookback_days=180,
                symbol_limit=3,
            )
            proposal = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": plan["proposal_key"],
                        "label": plan["label"],
                        "purchase_plan": plan["purchase_plan"],
                        "capital_amount": plan["capital_amount"],
                        "input_warnings": plan["warnings"],
                        "execution_order_label": plan.get("execution_order_label") or "",
                        "execution_order_summary": plan.get("execution_order_summary") or "",
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=proposal,
            )
            proposal["operation_execution_signal"] = operation_execution_signal
            proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=proposal,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(proposal)

        ranked, best, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        if filter_metadata["has_active_readiness_filter"]:
            operational_tiebreak = {
                "has_tiebreak": False,
                "used_operational_tiebreak": False,
                "headline": "",
                "summary": "",
            }
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor balance manual",
                best_label=best["label"] if best else None,
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara candidatos individuales dentro de un bloque recomendado."""
    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    requested_block = str(_query_param_value(query_params, "candidate_compare_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_compare", "")).strip() == "1"
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "candidate_compare_readiness_filter")
    )

    selected_block = requested_block if requested_block in {item["bucket"] for item in comparable_blocks} else None
    if selected_block is None and comparable_blocks:
        selected_block = comparable_blocks[0]["bucket"]

    if selected_block is None:
        empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
        empty_tiebreak = {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
            "best_execution_readiness": empty_readiness,
            "operational_tiebreak": empty_tiebreak,
            "active_readiness_filter": readiness_filter,
            "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
            "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
            "visible_count": 0,
            "total_count": 0,
            "has_active_readiness_filter": readiness_filter != "all",
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor candidato actual",
                best_label=None,
                best_execution_readiness=empty_readiness,
                operational_tiebreak=empty_tiebreak,
            ),
        }

    selected_block_data = next(item for item in comparable_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for candidate in selected_block_data["candidates"][:3]:
            purchase_plan = [
                {
                    "symbol": candidate["asset"],
                    "amount": round(float(selected_block_data["suggested_amount"]), 2),
                }
            ]
            simulation = simulator.simulate(
                {
                    "capital_amount": float(selected_block_data["suggested_amount"]),
                    "purchase_plan": purchase_plan,
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=purchase_plan,
                lookback_days=180,
                symbol_limit=3,
            )
            proposal = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": candidate["asset"],
                        "label": candidate["asset"],
                        "candidate": candidate,
                        "purchase_plan": purchase_plan,
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=proposal,
            )
            proposal["operation_execution_signal"] = operation_execution_signal
            proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=proposal,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(proposal)

        ranked, best, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        if filter_metadata["has_active_readiness_filter"]:
            operational_tiebreak = {
                "has_tiebreak": False,
                "used_operational_tiebreak": False,
                "headline": "",
                "summary": "",
            }
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": selected_block_data["suggested_amount"],
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor candidato actual",
                best_label=best["label"] if best else None,
                selected_label=selected_block_data["label"],
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_split_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara concentrar el bloque en un candidato vs repartirlo entre top 2."""
    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    split_blocks = [block for block in comparable_blocks if len(block["candidates"]) >= 2]
    requested_block = str(_query_param_value(query_params, "candidate_split_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_split_compare", "")).strip() == "1"
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "candidate_split_readiness_filter")
    )

    selected_block = requested_block if requested_block in {item["bucket"] for item in split_blocks} else None
    if selected_block is None and split_blocks:
        selected_block = split_blocks[0]["bucket"]

    if selected_block is None:
        empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
        empty_tiebreak = {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
            "best_execution_readiness": empty_readiness,
            "operational_tiebreak": empty_tiebreak,
            "active_readiness_filter": readiness_filter,
            "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
            "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
            "visible_count": 0,
            "total_count": 0,
            "has_active_readiness_filter": readiness_filter != "all",
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor construccion actual",
                best_label=None,
                best_execution_readiness=empty_readiness,
                operational_tiebreak=empty_tiebreak,
            ),
        }

    selected_block_data = next(item for item in split_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"][:2],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_split_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        top_candidate = selected_block_data["candidates"][0]
        runner_up = selected_block_data["candidates"][1]
        total_amount = round(float(selected_block_data["suggested_amount"]), 2)
        half_amount = round(total_amount / 2.0, 2)
        remainder_amount = round(total_amount - half_amount, 2)

        variants = [
            {
                "proposal_key": "single_top_candidate",
                "label": f"Concentrado en {top_candidate['asset']}",
                "purchase_plan": [{"symbol": top_candidate["asset"], "amount": total_amount}],
                "composition": [top_candidate["asset"]],
            },
            {
                "proposal_key": "split_top_two",
                "label": f"Split {top_candidate['asset']} + {runner_up['asset']}",
                "purchase_plan": [
                    {"symbol": top_candidate["asset"], "amount": half_amount},
                    {"symbol": runner_up["asset"], "amount": remainder_amount},
                ],
                "composition": [top_candidate["asset"], runner_up["asset"]],
            },
        ]

        proposals = []
        for variant in variants:
            simulation = simulator.simulate(
                {
                    "capital_amount": total_amount,
                    "purchase_plan": variant["purchase_plan"],
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=variant["purchase_plan"],
                lookback_days=180,
                symbol_limit=3,
            )
            proposal = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": variant["proposal_key"],
                        "label": variant["label"],
                        "purchase_plan": variant["purchase_plan"],
                        "composition": variant["composition"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=proposal,
            )
            proposal["operation_execution_signal"] = operation_execution_signal
            proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=proposal,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(proposal)

        ranked, best, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        if filter_metadata["has_active_readiness_filter"]:
            operational_tiebreak = {
                "has_tiebreak": False,
                "used_operational_tiebreak": False,
                "headline": "",
                "summary": "",
            }
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": total_amount,
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor construccion actual",
                best_label=best["label"] if best else None,
                selected_label=selected_block_data["label"],
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_preferred_incremental_portfolio_proposal(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza la mejor propuesta incremental disponible entre los comparadores activos."""
    auto = get_incremental_portfolio_simulation_comparison(capital_amount=capital_amount)
    candidate = get_candidate_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    split = get_candidate_split_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    manual = get_manual_incremental_portfolio_simulation_comparison(
        query_params,
        default_capital_amount=capital_amount,
    )

    candidates = []
    for source_key, label, payload in (
        ("automatic_variants", "Comparador automatico", auto),
        ("candidate_block", "Comparador por candidato", candidate),
        ("candidate_split", "Comparador por split", split),
        ("manual_plan", "Comparador manual", manual),
    ):
        best_item = _extract_best_incremental_proposal(payload)
        if best_item is None:
            continue
        candidates.append(
            _normalize_incremental_proposal_item(
                {
                    "source_key": source_key,
                    "source_label": label,
                    "proposal_key": best_item["proposal_key"],
                    "proposal_label": best_item.get("proposal_label") or best_item.get("label"),
                    "purchase_plan": best_item.get("purchase_plan", []),
                    "comparison_score": best_item.get("comparison_score"),
                    "simulation": best_item.get("simulation", {}),
                    "selected_context": _build_preferred_proposal_context(source_key, payload),
                    "priority_rank": _preferred_source_priority_rank(source_key, payload),
                }
            )
        )

    best = None
    if candidates:
        best = sorted(
            candidates,
            key=lambda item: (
                float(item["comparison_score"] if item["comparison_score"] is not None else float("-inf")),
                item["priority_rank"],
            ),
            reverse=True,
        )[0]

    return {
        "candidates": candidates,
        "preferred": best,
        "has_manual_override": bool(manual.get("submitted") and manual.get("proposals")),
        "explanation": _build_preferred_incremental_explanation(best, manual),
    }
