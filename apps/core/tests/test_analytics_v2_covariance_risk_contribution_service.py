from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from django.utils import timezone

from apps.core.services.analytics_v2.covariance_risk_contribution_service import (
    CovarianceAwareRiskContributionService,
)
from apps.core.services.analytics_v2.risk_contribution_service import RiskContributionService
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
