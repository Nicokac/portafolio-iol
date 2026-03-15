from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from django.utils import timezone

from apps.core.services.analytics_v2.covariance_risk_contribution_service import (
    CovarianceAwareRiskContributionService,
)
from apps.core.services.analytics_v2.risk_contribution_service import RiskContributionService
from apps.core.services.portfolio.covariance_service import CovarianceService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_asset_snapshot(fecha, simbolo, valorizado, *, tipo="ACCIONES", moneda="peso_Argentino"):
    return ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=fecha,
        pais_consulta="argentina",
        simbolo=simbolo,
        descripcion=f"Activo {simbolo}",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo=tipo,
        moneda=moneda,
    )


def _seed_position(
    now,
    symbol,
    sector,
    country,
    patrimonial,
    *,
    value,
    strategic_bucket="Growth",
    tipo="ACCIONES",
):
    ParametroActivo.objects.create(
        simbolo=symbol,
        sector=sector,
        bloque_estrategico=strategic_bucket,
        pais_exposicion=country,
        tipo_patrimonial=patrimonial,
    )
    _make_asset_snapshot(now, symbol, value, tipo=tipo, moneda="dolar_Estadounidense")


@pytest.mark.django_db
def test_covariance_aware_risk_contribution_falls_back_when_covariance_history_is_insufficient(monkeypatch):
    now = timezone.now()
    _seed_position(now, "AAPL", "Tecnologia", "USA", "Equity", value=1000)
    _seed_position(now, "SPY", "Indice", "USA", "Equity", value=900, strategic_bucket="Core", tipo="CEDEARS")
    _seed_position(now, "GD30", "Soberano", "Argentina", "Bond", value=800, strategic_bucket="Argentina", tipo="TitulosPublicos")

    service = CovarianceAwareRiskContributionService()
    monkeypatch.setattr(
        service.covariance_service,
        "build_model_inputs",
        lambda activos, lookback_days=252: {
            "warning": "insufficient_history",
            "observations": 5,
            "returns": pd.DataFrame(),
            "expected_returns": np.array([]),
            "covariance_matrix": np.array([[]]),
        },
    )

    result = service.calculate()

    assert result["model_variant"] == "mvp_proxy"
    assert result["covariance_observations"] == 5
    assert "insufficient_covariance_history" in result["metadata"]["warnings"]


@pytest.mark.django_db
def test_covariance_aware_risk_contribution_uses_covariance_when_inputs_are_usable(monkeypatch):
    now = timezone.now()
    _seed_position(now, "AAPL", "Tecnologia", "USA", "Equity", value=1000)
    _seed_position(now, "SPY", "Indice", "USA", "Equity", value=900, strategic_bucket="Core", tipo="CEDEARS")
    _seed_position(now, "GD30", "Soberano", "Argentina", "Bond", value=800, strategic_bucket="Argentina", tipo="TitulosPublicos")

    service = CovarianceAwareRiskContributionService()
    returns = pd.DataFrame(
        {
            "AAPL": [0.01] * 25,
            "SPY": [0.008] * 25,
            "GD30": [0.002] * 25,
        }
    )
    covariance = np.array(
        [
            [0.09, 0.03, 0.01],
            [0.03, 0.04, 0.01],
            [0.01, 0.01, 0.02],
        ]
    )
    monkeypatch.setattr(
        service.covariance_service,
        "build_model_inputs",
        lambda activos, lookback_days=252: {
            "observations": 25,
            "returns": returns,
            "expected_returns": np.array([0.1, 0.08, 0.03]),
            "covariance_matrix": covariance,
        },
    )

    result = service.calculate(top_n=3)

    assert result["model_variant"] == "covariance_aware"
    assert result["covariance_observations"] == 25
    assert result["portfolio_volatility_proxy"] is not None
    assert round(sum(item["contribution_pct"] for item in result["items"]), 2) == 100.0
    assert len(result["top_contributors"]) == 3
    assert result["metadata"]["confidence"] == "high" or result["metadata"]["confidence"] == "medium"


@pytest.mark.django_db
def test_covariance_aware_risk_contribution_falls_back_when_coverage_is_too_low(monkeypatch):
    now = timezone.now()
    _seed_position(now, "AAPL", "Tecnologia", "USA", "Equity", value=1000)
    _seed_position(now, "SPY", "Indice", "USA", "Equity", value=900, strategic_bucket="Core", tipo="CEDEARS")
    _seed_position(now, "GD30", "Soberano", "Argentina", "Bond", value=800, strategic_bucket="Argentina", tipo="TitulosPublicos")
    _seed_position(now, "MELI", "Tecnologia / E-commerce", "Latam", "Equity", value=1500)

    service = CovarianceAwareRiskContributionService()
    returns = pd.DataFrame(
        {
            "AAPL": [0.01] * 25,
            "SPY": [0.008] * 25,
            "GD30": [0.002] * 25,
        }
    )
    covariance = np.eye(3) * 0.04
    monkeypatch.setattr(
        service.covariance_service,
        "build_model_inputs",
        lambda activos, lookback_days=252: {
            "observations": 25,
            "returns": returns,
            "expected_returns": np.array([0.1, 0.08, 0.03]),
            "covariance_matrix": covariance,
        },
    )

    result = service.calculate()

    assert result["model_variant"] == "mvp_proxy"
    assert "insufficient_covariance_coverage" in result["metadata"]["warnings"]
    assert "MELI" in result["excluded_symbols"]


@pytest.mark.django_db
def test_covariance_aware_risk_contribution_falls_back_on_non_positive_portfolio_volatility(monkeypatch):
    now = timezone.now()
    _seed_position(now, "AAPL", "Tecnologia", "USA", "Equity", value=1000)
    _seed_position(now, "SPY", "Indice", "USA", "Equity", value=900, strategic_bucket="Core", tipo="CEDEARS")
    _seed_position(now, "GD30", "Soberano", "Argentina", "Bond", value=800, strategic_bucket="Argentina", tipo="TitulosPublicos")

    service = CovarianceAwareRiskContributionService()
    returns = pd.DataFrame(
        {
            "AAPL": [0.01] * 25,
            "SPY": [0.008] * 25,
            "GD30": [0.002] * 25,
        }
    )
    covariance = np.zeros((3, 3))
    monkeypatch.setattr(
        service.covariance_service,
        "build_model_inputs",
        lambda activos, lookback_days=252: {
            "observations": 25,
            "returns": returns,
            "expected_returns": np.array([0.1, 0.08, 0.03]),
            "covariance_matrix": covariance,
        },
    )

    result = service.calculate()

    assert result["model_variant"] == "mvp_proxy"
    assert "non_positive_portfolio_volatility" in result["metadata"]["warnings"]


@pytest.mark.django_db
def test_covariance_aware_risk_contribution_builds_signals_from_advanced_result(monkeypatch):
    now = timezone.now()

    fixtures = [
        ("AAPL", "Tecnologia", "USA", "Equity", 1000),
        ("MSFT", "Tecnologia", "USA", "Equity", 1000),
        ("BOND", "Soberano", "Argentina", "Bond", 1000),
    ]

    for symbol, sector, country, patrimonial, _ in fixtures:
        ParametroActivo.objects.create(
            simbolo=symbol,
            sector=sector,
            bloque_estrategico="Test",
            pais_exposicion=country,
            tipo_patrimonial=patrimonial,
        )

    for symbol, _, _, _, value in fixtures:
        _make_asset_snapshot(
            now,
            symbol,
            value,
            tipo="ACCIONES" if symbol != "BOND" else "TitulosPublicos",
            moneda="dolar_Estadounidense" if symbol != "BOND" else "peso_Argentino",
        )

    covariance = pd.DataFrame(
        [[0.09, 0.08, 0.0], [0.08, 0.09, 0.0], [0.0, 0.0, 0.02]],
        index=["AAPL", "MSFT", "BOND"],
        columns=["AAPL", "MSFT", "BOND"],
    )
    returns = pd.DataFrame(
        {
            "AAPL": [0.01] * 30,
            "MSFT": [0.01] * 30,
            "BOND": [0.002] * 30,
        }
    )
    monkeypatch.setattr(
        CovarianceService,
        "build_model_inputs",
        lambda self, activos, lookback_days=252: {
            "returns": returns[activos],
            "covariance_matrix": covariance.loc[activos, activos].to_numpy(),
            "observations": 30,
        },
    )

    service = CovarianceAwareRiskContributionService()
    signals = service.build_recommendation_signals(top_n=3)
    keyed = {signal["signal_key"]: signal for signal in signals}

    assert "risk_concentration_top_assets" in keyed
    assert keyed["risk_concentration_top_assets"]["evidence"]["symbols"][:2] == ["AAPL", "MSFT"]
    assert "risk_concentration_tech" in keyed


@pytest.mark.django_db
def test_covariance_aware_risk_contribution_reuses_mvp_signal_logic_when_falling_back():
    now = timezone.now()

    tech_assets = [
        ("AAPL", [1000, 1120, 1040, 1180, 1210]),
        ("MSFT", [900, 1005, 940, 1060, 1090]),
        ("NVDA", [800, 930, 860, 1020, 1080]),
    ]

    for symbol, _ in tech_assets:
        ParametroActivo.objects.create(
            simbolo=symbol,
            sector="Tecnologia",
            bloque_estrategico="Growth",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )

    for i in range(5):
        fecha = now - timedelta(days=4 - i)
        for symbol, values in tech_assets:
            _make_asset_snapshot(fecha, symbol, values[i], tipo="ACCIONES", moneda="dolar_Estadounidense")

    base_signals = RiskContributionService().build_recommendation_signals(top_n=3)
    advanced_signals = CovarianceAwareRiskContributionService().build_recommendation_signals(top_n=3)

    assert {signal["signal_key"] for signal in advanced_signals} == {signal["signal_key"] for signal in base_signals}
