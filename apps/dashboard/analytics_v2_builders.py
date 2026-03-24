from typing import Dict


def resolve_active_risk_contribution_result(
    *,
    base_risk_service,
    covariance_risk_service,
) -> Dict:
    base_risk_result = base_risk_service.calculate()
    covariance_risk_result = covariance_risk_service.calculate()
    active_result = (
        covariance_risk_result
        if covariance_risk_result.get("model_variant") == "covariance_aware"
        else base_risk_result
    )
    return {
        "base_result": base_risk_result,
        "covariance_result": covariance_risk_result,
        "active_result": active_result,
    }


def build_risk_contribution_detail(*, resolved: Dict, explanation_service) -> Dict:
    result = resolved["active_result"]
    covariance_result = resolved["covariance_result"]
    by_sector = [
        {
            "rank": index,
            "key": item.get("key"),
            "weight_pct": item.get("weight_pct"),
            "contribution_pct": item.get("contribution_pct"),
            "risk_vs_weight_delta": round(
                float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                2,
            ),
        }
        for index, item in enumerate(result.get("by_sector", []), start=1)
    ]
    by_country = [
        {
            "rank": index,
            "key": item.get("key"),
            "weight_pct": item.get("weight_pct"),
            "contribution_pct": item.get("contribution_pct"),
            "risk_vs_weight_delta": round(
                float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                2,
            ),
        }
        for index, item in enumerate(result.get("by_country", []), start=1)
    ]

    items = [
        {
            "rank": index,
            "symbol": item.get("symbol"),
            "sector": item.get("sector"),
            "country": item.get("country"),
            "asset_type": item.get("asset_type"),
            "weight_pct": item.get("weight_pct"),
            "volatility_proxy": item.get("volatility_proxy"),
            "risk_score": item.get("risk_score"),
            "contribution_pct": item.get("contribution_pct"),
            "risk_vs_weight_delta": round(
                float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                2,
            ),
            "used_volatility_fallback": item.get("used_volatility_fallback", False),
        }
        for index, item in enumerate(result.get("items", []), start=1)
    ]

    metadata = result.get("metadata", {})
    top_asset = result.get("top_contributors", [{}])[0] if result.get("top_contributors") else None
    top_sector = result.get("by_sector", [{}])[0] if result.get("by_sector") else None

    return {
        "items": items,
        "by_sector": by_sector,
        "by_country": by_country,
        "top_asset": top_asset,
        "top_sector": top_sector,
        "model_variant": covariance_result.get("model_variant", "mvp_proxy"),
        "covariance_observations": int(covariance_result.get("covariance_observations") or 0),
        "coverage_pct": float(covariance_result.get("coverage_pct") or 0.0),
        "portfolio_volatility_proxy": covariance_result.get("portfolio_volatility_proxy"),
        "confidence": metadata.get("confidence", "low"),
        "warnings": metadata.get("warnings", []),
        "methodology": metadata.get("methodology"),
        "limitations": metadata.get("limitations"),
        "covered_symbols": covariance_result.get("covered_symbols", []),
        "excluded_symbols": covariance_result.get("excluded_symbols", []),
        "interpretation": explanation_service.build_risk_contribution_explanation(result),
    }


def build_scenario_analysis_detail(*, scenario_service, catalog_service) -> Dict:
    scenario_rows = []
    for scenario in catalog_service.list_scenarios():
        result = scenario_service.analyze(scenario["scenario_key"])
        top_sector = result.get("by_sector", [{}])[0] if result.get("by_sector") else None
        top_country = result.get("by_country", [{}])[0] if result.get("by_country") else None
        scenario_rows.append(
            {
                "scenario_key": scenario["scenario_key"],
                "label": scenario.get("label"),
                "description": scenario.get("description"),
                "category": scenario.get("category"),
                "total_impact_pct": float(result.get("total_impact_pct") or 0.0),
                "total_impact_money": float(result.get("total_impact_money") or 0.0),
                "top_sector": top_sector,
                "top_country": top_country,
                "by_asset": result.get("by_asset", []),
                "by_sector": result.get("by_sector", []),
                "by_country": result.get("by_country", []),
                "top_negative_contributors": result.get("top_negative_contributors", []),
                "metadata": result.get("metadata", {}),
            }
        )

    ranked_rows = [
        {**item, "severity_rank": index}
        for index, item in enumerate(sorted(scenario_rows, key=lambda item: float(item.get("total_impact_pct") or 0.0)), start=1)
    ]
    worst_scenario = ranked_rows[0] if ranked_rows else None

    worst_assets = []
    worst_sectors = []
    worst_countries = []
    if worst_scenario:
        worst_assets = [
            {
                "rank": index,
                "symbol": item.get("symbol"),
                "market_value": item.get("market_value"),
                "estimated_impact_pct": item.get("estimated_impact_pct"),
                "estimated_impact_money": item.get("estimated_impact_money"),
                "transmission_channel": item.get("transmission_channel"),
            }
            for index, item in enumerate(worst_scenario.get("by_asset", []), start=1)
        ]
        worst_sectors = [
            {
                "rank": index,
                "key": item.get("key"),
                "impact_pct": item.get("impact_pct"),
                "impact_money": item.get("impact_money"),
            }
            for index, item in enumerate(worst_scenario.get("by_sector", []), start=1)
        ]
        worst_countries = [
            {
                "rank": index,
                "key": item.get("key"),
                "impact_pct": item.get("impact_pct"),
                "impact_money": item.get("impact_money"),
            }
            for index, item in enumerate(worst_scenario.get("by_country", []), start=1)
        ]

    return {
        "scenarios": ranked_rows,
        "worst_scenario": worst_scenario,
        "worst_assets": worst_assets,
        "worst_sectors": worst_sectors,
        "worst_countries": worst_countries,
        "confidence": (worst_scenario or {}).get("metadata", {}).get("confidence", "low"),
        "warnings": (worst_scenario or {}).get("metadata", {}).get("warnings", []),
        "methodology": (worst_scenario or {}).get("metadata", {}).get("methodology"),
        "limitations": (worst_scenario or {}).get("metadata", {}).get("limitations"),
    }


def build_factor_exposure_detail(*, factor_result: Dict, explanation_service) -> Dict:
    factor_rows = [
        {
            "rank": index,
            "factor": item.get("factor"),
            "exposure_pct": float(item.get("exposure_pct") or 0.0),
            "contribution_relative_pct": float(item.get("exposure_pct") or 0.0),
            "confidence": item.get("confidence", "low"),
        }
        for index, item in enumerate(
            sorted(
                factor_result.get("factors", []),
                key=lambda entry: float(entry.get("exposure_pct") or 0.0),
                reverse=True,
            ),
            start=1,
        )
    ]
    dominant_factor_key = factor_result.get("dominant_factor")
    dominant_factor = next((item for item in factor_rows if item.get("factor") == dominant_factor_key), None)
    unknown_assets = [
        {"rank": index, "symbol": symbol}
        for index, symbol in enumerate(factor_result.get("unknown_assets", []), start=1)
    ]
    metadata = factor_result.get("metadata", {})

    return {
        "factors": factor_rows,
        "dominant_factor": dominant_factor,
        "dominant_factor_key": dominant_factor_key,
        "underrepresented_factors": factor_result.get("underrepresented_factors", []),
        "unknown_assets": unknown_assets,
        "unknown_assets_count": len(unknown_assets),
        "confidence": metadata.get("confidence", "low"),
        "warnings": metadata.get("warnings", []),
        "methodology": metadata.get("methodology"),
        "limitations": metadata.get("limitations"),
        "interpretation": explanation_service.build_factor_exposure_explanation(factor_result),
    }


def build_stress_fragility_detail(*, stress_rows: list[Dict], explanation_service) -> Dict:
    ranked_rows = [
        {**item, "severity_rank": index}
        for index, item in enumerate(sorted(stress_rows, key=lambda item: float(item.get("total_loss_pct") or 0.0)), start=1)
    ]
    worst_stress = ranked_rows[0] if ranked_rows else None

    worst_assets = []
    worst_sectors = []
    worst_countries = []
    if worst_stress:
        worst_assets = [
            {
                "rank": index,
                "symbol": item.get("symbol"),
                "market_value": item.get("market_value"),
                "estimated_impact_pct": item.get("estimated_impact_pct"),
                "estimated_impact_money": item.get("estimated_impact_money"),
                "transmission_channel": item.get("transmission_channel"),
            }
            for index, item in enumerate(worst_stress.get("vulnerable_assets", []), start=1)
        ]
        worst_sectors = [
            {
                "rank": index,
                "key": item.get("key"),
                "impact_pct": item.get("impact_pct"),
                "impact_money": item.get("impact_money"),
            }
            for index, item in enumerate(worst_stress.get("vulnerable_sectors", []), start=1)
        ]
        worst_countries = [
            {
                "rank": index,
                "key": item.get("key"),
                "impact_pct": item.get("impact_pct"),
                "impact_money": item.get("impact_money"),
            }
            for index, item in enumerate(worst_stress.get("vulnerable_countries", []), start=1)
        ]

    return {
        "stresses": ranked_rows,
        "worst_stress": worst_stress,
        "worst_assets": worst_assets,
        "worst_sectors": worst_sectors,
        "worst_countries": worst_countries,
        "confidence": (worst_stress or {}).get("metadata", {}).get("confidence", "low"),
        "warnings": (worst_stress or {}).get("metadata", {}).get("warnings", []),
        "methodology": (worst_stress or {}).get("metadata", {}).get("methodology"),
        "limitations": (worst_stress or {}).get("metadata", {}).get("limitations"),
        "interpretation": explanation_service.build_stress_fragility_explanation(worst_stress or {}),
    }


def build_expected_return_detail(*, result: Dict, explanation_service) -> Dict:
    bucket_rows = [
        {
            "rank": index,
            "bucket_key": item.get("bucket_key"),
            "label": item.get("label"),
            "weight_pct": item.get("weight_pct"),
            "expected_return_pct": item.get("expected_return_pct"),
            "real_expected_return_pct": None,
            "contribution_relative_pct": (
                round(
                    (float(item.get("weight_pct") or 0.0) / 100.0) * float(item.get("expected_return_pct") or 0.0),
                    2,
                )
                if item.get("expected_return_pct") is not None
                else None
            ),
            "basis_reference": item.get("basis_reference"),
        }
        for index, item in enumerate(
            sorted(
                result.get("by_bucket", []),
                key=lambda entry: float(entry.get("weight_pct") or 0.0),
                reverse=True,
            ),
            start=1,
        )
    ]

    metadata = result.get("metadata", {})
    warnings = metadata.get("warnings", [])
    return {
        "expected_return_pct": result.get("expected_return_pct"),
        "real_expected_return_pct": result.get("real_expected_return_pct"),
        "basis_reference": result.get("basis_reference"),
        "dominant_bucket": bucket_rows[0] if bucket_rows else None,
        "bucket_rows": bucket_rows,
        "asset_rows": [],
        "confidence": metadata.get("confidence", "low"),
        "warnings": warnings,
        "main_warning": warnings[0] if warnings else None,
        "methodology": metadata.get("methodology"),
        "limitations": metadata.get("limitations"),
        "assumptions": [
            "El modelo agrupa posiciones actuales en buckets estructurales.",
            "Las referencias usan SPY, EMB o BADLAR con fallbacks explicitos cuando falta historia suficiente.",
            "El retorno real depende de una referencia de inflacion disponible al momento del calculo.",
        ],
        "interpretation": explanation_service.build_expected_return_explanation(result),
    }


def build_analytics_v2_dashboard_summary(
    *,
    resolved_risk: Dict,
    base_risk_service,
    scenario_service,
    factor_service,
    explanation_service,
    stress_service,
    expected_return_service,
    local_macro_service,
) -> Dict:
    covariance_risk_result = resolved_risk["covariance_result"]
    risk_result = resolved_risk["active_result"]
    argentina_stress = scenario_service.analyze("argentina_stress")
    tech_shock = scenario_service.analyze("tech_shock")
    fragility = stress_service.calculate("local_crisis_severe")
    factor_result = factor_service.calculate()
    expected_return_result = expected_return_service.calculate()
    local_macro_result = local_macro_service.calculate()

    combined_signals = (
        base_risk_service.build_recommendation_signals(top_n=5)
        + scenario_service.build_recommendation_signals()
        + factor_service.build_recommendation_signals()
        + stress_service.build_recommendation_signals()
        + expected_return_service.build_recommendation_signals()
        + local_macro_service.build_recommendation_signals()
    )
    combined_signals = sorted(
        combined_signals,
        key=lambda signal: {"high": 0, "medium": 1, "low": 2}.get(signal.get("severity"), 3),
    )

    top_risk_asset = risk_result["top_contributors"][0] if risk_result.get("top_contributors") else None
    top_risk_sector = risk_result["by_sector"][0] if risk_result.get("by_sector") else None
    dominant_factor_key = factor_result.get("dominant_factor")
    dominant_factor = next(
        (item for item in factor_result.get("factors", []) if item.get("factor") == dominant_factor_key),
        None,
    )
    covariance_variant = covariance_risk_result.get("model_variant", "mvp_proxy")
    covariance_observations = int(covariance_risk_result.get("covariance_observations") or 0)
    covariance_coverage_pct = float(covariance_risk_result.get("coverage_pct") or 0.0)
    covariance_warning = next(iter(covariance_risk_result.get("metadata", {}).get("warnings", [])), None)
    worst_scenario = (
        {"label": "Argentina Stress", **argentina_stress}
        if (argentina_stress.get("total_impact_pct") or 0) <= (tech_shock.get("total_impact_pct") or 0)
        else {"label": "Tech Shock", **tech_shock}
    )

    return {
        "risk_contribution": {
            "top_asset": top_risk_asset,
            "top_sector": top_risk_sector,
            "confidence": risk_result["metadata"]["confidence"],
            "warnings_count": len(risk_result["metadata"].get("warnings", [])),
            "model_variant": covariance_variant,
            "covariance_observations": covariance_observations,
            "coverage_pct": covariance_coverage_pct,
            "covariance_warning": covariance_warning,
            "interpretation": explanation_service.build_risk_contribution_explanation(risk_result),
        },
        "scenario_analysis": {
            "argentina_stress_pct": argentina_stress.get("total_impact_pct"),
            "tech_shock_pct": tech_shock.get("total_impact_pct"),
            "confidence": min(
                argentina_stress["metadata"]["confidence"],
                tech_shock["metadata"]["confidence"],
                key=lambda level: {"high": 3, "medium": 2, "low": 1}.get(level, 0),
            ),
            "worst_label": worst_scenario["label"],
            "interpretation": explanation_service.build_scenario_analysis_explanation({"worst_scenario": worst_scenario}),
        },
        "factor_exposure": {
            "dominant_factor": dominant_factor_key,
            "dominant_factor_exposure_pct": dominant_factor.get("exposure_pct") if dominant_factor else None,
            "unknown_assets_count": len(factor_result.get("unknown_assets", [])),
            "confidence": factor_result["metadata"]["confidence"],
            "interpretation": explanation_service.build_factor_exposure_explanation(factor_result),
        },
        "stress_testing": {
            "scenario_key": fragility.get("scenario_key"),
            "fragility_score": fragility.get("fragility_score"),
            "total_loss_pct": fragility.get("total_loss_pct"),
            "confidence": fragility["metadata"]["confidence"],
            "interpretation": explanation_service.build_stress_fragility_explanation(fragility),
        },
        "expected_return": {
            "expected_return_pct": expected_return_result.get("expected_return_pct"),
            "real_expected_return_pct": expected_return_result.get("real_expected_return_pct"),
            "confidence": expected_return_result["metadata"]["confidence"],
            "warnings_count": len(expected_return_result["metadata"].get("warnings", [])),
            "interpretation": explanation_service.build_expected_return_explanation(expected_return_result),
        },
        "local_macro": {
            **(local_macro_result.get("summary", {})),
            "confidence": local_macro_result.get("metadata", {}).get("confidence"),
            "warnings_count": len(local_macro_result.get("metadata", {}).get("warnings", [])),
        },
        "signals": combined_signals[:6],
    }
