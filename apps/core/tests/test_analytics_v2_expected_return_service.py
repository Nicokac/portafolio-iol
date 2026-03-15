from types import SimpleNamespace

import pandas as pd

from apps.core.services.analytics_v2.expected_return_service import ExpectedReturnService
from apps.core.services.analytics_v2.schemas import NormalizedPosition


def _make_position(symbol, market_value, *, asset_type, sector="Tecnologia", bucket="Growth", patrimonial_type="Equity"):
    return NormalizedPosition(
        symbol=symbol,
        description=symbol,
        market_value=float(market_value),
        weight_pct=0.0,
        sector=sector,
        country="USA",
        asset_type=asset_type,
        strategic_bucket=bucket,
        patrimonial_type=patrimonial_type,
        currency="ARS",
        gain_pct=0.0,
        gain_money=0.0,
    )


def test_expected_return_service_handles_empty_portfolio():
    service = ExpectedReturnService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: []),
        benchmark_service=SimpleNamespace(
            build_daily_returns=lambda *args, **kwargs: pd.Series(dtype=float),
            build_weekly_returns=lambda *args, **kwargs: pd.Series(dtype=float),
        ),
        macro_service=SimpleNamespace(get_context_summary=lambda: {}),
    )

    result = service.calculate()

    assert result["expected_return_pct"] is None
    assert result["real_expected_return_pct"] is None
    assert result["by_bucket"] == []
    assert "empty_portfolio" in result["metadata"]["warnings"]
    assert result["metadata"]["confidence"] == "low"


def test_expected_return_service_builds_weighted_bucket_baseline_with_fallbacks():
    positions = [
        _make_position("AAPL", 600, asset_type="equity"),
        _make_position("GD30", 300, asset_type="bond", sector="Soberano", bucket="Argentina", patrimonial_type="Bond"),
        _make_position("ADBAICA", 100, asset_type="fci", sector="Cash Mgmt", bucket="Liquidez", patrimonial_type="FCI"),
    ]
    benchmark_service = SimpleNamespace(
        build_daily_returns=lambda key, dates: pd.Series([0.001] * 60) if key == "cedear_usa" else pd.Series(dtype=float),
        build_weekly_returns=lambda key, dates: pd.Series(dtype=float),
    )
    macro_service = SimpleNamespace(
        get_context_summary=lambda: {
            "badlar_privada": 30.0,
            "ipc_nacional_variation_yoy": 20.0,
        }
    )
    service = ExpectedReturnService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions),
        benchmark_service=benchmark_service,
        macro_service=macro_service,
    )

    result = service.calculate()

    buckets = {item["bucket_key"]: item for item in result["by_bucket"]}
    assert set(buckets) == {"equity_beta", "fixed_income_ar", "liquidity_ars"}
    assert buckets["equity_beta"]["weight_pct"] == 60.0
    assert buckets["fixed_income_ar"]["weight_pct"] == 30.0
    assert buckets["liquidity_ars"]["weight_pct"] == 10.0
    assert buckets["equity_beta"]["basis_reference"].startswith("benchmark:cedear_usa")
    assert buckets["fixed_income_ar"]["basis_reference"] == "static:cer_embi_proxy"
    assert buckets["liquidity_ars"]["basis_reference"] == "macro:badlar_privada_latest_annual_rate"
    assert result["expected_return_pct"] is not None
    assert result["real_expected_return_pct"] is not None
    assert result["metadata"]["confidence"] == "medium"
    assert "expected_return_fallback:fixed_income_ar:insufficient_benchmark_history" in result["metadata"]["warnings"]


def test_expected_return_service_warns_when_inflation_reference_is_missing():
    positions = [_make_position("SPY", 1000, asset_type="equity")]
    benchmark_service = SimpleNamespace(
        build_daily_returns=lambda key, dates: pd.Series([0.001] * 40),
        build_weekly_returns=lambda key, dates: pd.Series(dtype=float),
    )
    service = ExpectedReturnService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions),
        benchmark_service=benchmark_service,
        macro_service=SimpleNamespace(get_context_summary=lambda: {}),
    )

    result = service.calculate()

    assert result["expected_return_pct"] is not None
    assert result["real_expected_return_pct"] is None
    assert "missing_inflation_reference" in result["metadata"]["warnings"]
    assert result["metadata"]["confidence"] == "medium"


def test_expected_return_service_build_recommendation_signals_detects_real_weak_and_liquidity_drag():
    service = ExpectedReturnService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: []),
        benchmark_service=SimpleNamespace(
            build_daily_returns=lambda *args, **kwargs: pd.Series(dtype=float),
            build_weekly_returns=lambda *args, **kwargs: pd.Series(dtype=float),
        ),
        macro_service=SimpleNamespace(get_context_summary=lambda: {}),
    )
    service.calculate = lambda: {
        "expected_return_pct": 11.5,
        "real_expected_return_pct": -3.0,
        "by_bucket": [
            {
                "bucket_key": "equity_beta",
                "weight_pct": 45.0,
                "expected_return_pct": 18.0,
                "basis_reference": "benchmark:cedear_usa:daily_trailing_40",
            },
            {
                "bucket_key": "liquidity_ars",
                "weight_pct": 35.0,
                "expected_return_pct": 10.0,
                "basis_reference": "macro:badlar_privada_latest_annual_rate",
            },
        ],
    }

    signal_keys = {signal["signal_key"] for signal in service.build_recommendation_signals()}

    assert "expected_return_real_weak" in signal_keys
    assert "expected_return_liquidity_drag" in signal_keys


def test_expected_return_service_build_recommendation_signals_detects_nominal_weak_when_real_is_missing():
    service = ExpectedReturnService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: []),
        benchmark_service=SimpleNamespace(
            build_daily_returns=lambda *args, **kwargs: pd.Series(dtype=float),
            build_weekly_returns=lambda *args, **kwargs: pd.Series(dtype=float),
        ),
        macro_service=SimpleNamespace(get_context_summary=lambda: {}),
    )
    service.calculate = lambda: {
        "expected_return_pct": 10.0,
        "real_expected_return_pct": None,
        "by_bucket": [
            {
                "bucket_key": "equity_beta",
                "weight_pct": 70.0,
                "expected_return_pct": 10.0,
                "basis_reference": "static:sp500",
            }
        ],
    }

    signal_keys = {signal["signal_key"] for signal in service.build_recommendation_signals()}

    assert "expected_return_nominal_weak" in signal_keys


def test_expected_return_service_build_recommendation_signals_returns_empty_for_empty_buckets():
    service = ExpectedReturnService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: []),
        benchmark_service=SimpleNamespace(
            build_daily_returns=lambda *args, **kwargs: pd.Series(dtype=float),
            build_weekly_returns=lambda *args, **kwargs: pd.Series(dtype=float),
        ),
        macro_service=SimpleNamespace(get_context_summary=lambda: {}),
    )
    service.calculate = lambda: {"by_bucket": []}

    assert service.build_recommendation_signals() == []
