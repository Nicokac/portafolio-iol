from apps.core.services.analytics_v2.schemas import NormalizedPosition
from apps.core.services.incremental_portfolio_simulator import IncrementalPortfolioSimulator


def make_position(
    symbol,
    *,
    market_value,
    sector,
    country,
    asset_type="equity",
    strategic_bucket="Growth",
    patrimonial_type="Growth",
    currency="USD",
):
    return NormalizedPosition(
        symbol=symbol,
        description=f"Activo {symbol}",
        market_value=market_value,
        weight_pct=0.0,
        sector=sector,
        country=country,
        asset_type=asset_type,
        strategic_bucket=strategic_bucket,
        patrimonial_type=patrimonial_type,
        currency=currency,
        gain_pct=0.0,
        gain_money=0.0,
    )


def build_positions(*positions):
    total = sum(float(position.market_value) for position in positions)
    if total <= 0:
        return list(positions)
    return [
        NormalizedPosition(
            **{
                **position.to_dict(),
                "weight_pct": round((float(position.market_value) / total) * 100.0, 2),
            }
        )
        for position in positions
    ]


def analytics_runner(positions):
    total = sum(float(position.market_value) for position in positions)
    defensive_value = sum(
        float(position.market_value)
        for position in positions
        if "defens" in (position.sector or "").lower() or "utilit" in (position.sector or "").lower()
    )
    dividend_value = sum(
        float(position.market_value)
        for position in positions
        if "dividend" in (position.patrimonial_type or "").lower()
    )
    top_position = max(positions, key=lambda item: float(item.market_value), default=None)
    defensive_pct = round((defensive_value / total) * 100.0, 2) if total else 0.0
    dividend_pct = round((dividend_value / total) * 100.0, 2) if total else 0.0
    expected_return_pct = round(8.0 + (defensive_pct * 0.04), 2) if total else None
    real_expected_return_pct = round(expected_return_pct - 5.0, 2) if expected_return_pct is not None else None
    fragility_score = round(max(0.0, 70.0 - (defensive_pct * 0.4)), 2) if total else None
    worst_scenario_loss_pct = round(-15.0 + (defensive_pct * 0.08), 2) if total else None

    return {
        "expected_return_pct": expected_return_pct,
        "real_expected_return_pct": real_expected_return_pct,
        "fragility_score": fragility_score,
        "dominant_factor": "defensive" if defensive_pct >= 50.0 else "growth",
        "worst_scenario_key": "tech_shock",
        "worst_scenario_loss_pct": worst_scenario_loss_pct,
        "top_risk_contributor": top_position.symbol if top_position else None,
        "top_risk_contribution_pct": round((float(top_position.market_value) / total) * 100.0, 2) if top_position and total else None,
        "risk_model_variant": "mvp_proxy",
        "factor_result": {
            "factors": [
                {"factor": "defensive", "exposure_pct": defensive_pct},
                {"factor": "dividend", "exposure_pct": dividend_pct},
                {"factor": "growth", "exposure_pct": round(max(0.0, 100.0 - defensive_pct), 2)},
            ]
        },
    }


def test_simulate_basic_purchase_builds_before_after_and_delta():
    current_positions = build_positions(
        make_position("AAPL", market_value=400000, sector="Tecnologia", country="USA"),
        make_position("KO", market_value=200000, sector="Consumo defensivo", country="USA", patrimonial_type="Dividend"),
    )
    simulator = IncrementalPortfolioSimulator(
        current_positions_loader=lambda: current_positions,
        asset_metadata_loader=lambda symbol: next((item for item in current_positions if item.symbol == symbol), None),
        analytics_runner=analytics_runner,
    )

    result = simulator.simulate(
        {
            "capital_amount": 600000,
            "purchase_plan": [
                {"symbol": "KO", "amount": 300000},
                {"symbol": "AAPL", "amount": 300000},
            ],
        }
    )

    assert result["before"]["expected_return_pct"] is not None
    assert result["after"]["expected_return_pct"] is not None
    assert result["delta"]["expected_return_change"] is not None
    assert result["delta"]["fragility_change"] is not None
    assert result["interpretation"]
    assert result["applied_capital_amount"] == 600000.0


def test_simulate_handles_single_asset_portfolio():
    current_positions = build_positions(
        make_position("KO", market_value=300000, sector="Consumo defensivo", country="USA", patrimonial_type="Dividend")
    )
    simulator = IncrementalPortfolioSimulator(
        current_positions_loader=lambda: current_positions,
        asset_metadata_loader=lambda symbol: current_positions[0] if symbol == "KO" else None,
        analytics_runner=analytics_runner,
    )

    result = simulator.simulate(
        {
            "capital_amount": 100000,
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
        }
    )

    assert result["before"]["top_risk_contributor"] == "KO"
    assert result["after"]["top_risk_contributor"] == "KO"
    assert result["purchase_plan"][0]["symbol"] == "KO"


def test_simulate_supports_new_asset_when_metadata_is_available():
    current_positions = build_positions(
        make_position("AAPL", market_value=600000, sector="Tecnologia", country="USA")
    )
    metadata_by_symbol = {
        "XLU": make_position(
            "XLU",
            market_value=0,
            sector="Utilities",
            country="USA",
            patrimonial_type="Dividend",
        )
    }
    simulator = IncrementalPortfolioSimulator(
        current_positions_loader=lambda: current_positions,
        asset_metadata_loader=lambda symbol: metadata_by_symbol.get(symbol),
        analytics_runner=analytics_runner,
    )

    result = simulator.simulate(
        {
            "capital_amount": 200000,
            "purchase_plan": [{"symbol": "XLU", "amount": 200000}],
        }
    )

    assert result["after"]["dominant_factor"] in {"growth", "defensive"}
    assert result["purchase_plan"][0]["symbol"] == "XLU"
    assert "La compra" in result["interpretation"]


def test_simulate_returns_empty_result_for_zero_capital():
    simulator = IncrementalPortfolioSimulator(
        current_positions_loader=lambda: [],
        asset_metadata_loader=lambda symbol: None,
        analytics_runner=analytics_runner,
    )

    result = simulator.simulate({"capital_amount": 0, "purchase_plan": [{"symbol": "KO", "amount": 100000}]})

    assert result["warnings"] == ["invalid_capital"]
    assert result["before"] == {}
    assert result["after"] == {}


def test_simulate_handles_empty_portfolio_and_unknown_symbol():
    simulator = IncrementalPortfolioSimulator(
        current_positions_loader=lambda: [],
        asset_metadata_loader=lambda symbol: None,
        analytics_runner=analytics_runner,
    )

    result = simulator.simulate(
        {
            "capital_amount": 100000,
            "purchase_plan": [{"symbol": "ZZZ", "amount": 100000}],
        }
    )

    assert "unknown_purchase_symbol:ZZZ" in result["warnings"]
    assert result["after"]["top_risk_contributor"] is None
