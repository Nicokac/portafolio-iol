import numpy as np
import pandas as pd
import pytest
from django.utils import timezone

from apps.core.services.analytics_v2.covariance_risk_contribution_service import (
    CovarianceAwareRiskContributionService,
)
from apps.core.services.analytics_v2.risk_contribution_service import (
    RiskContributionService,
    _VolatilityResolution,
)
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_position(now, symbol, sector, country, patrimonial, value, *, strategic_bucket="Growth", tipo="ACCIONES"):
    ParametroActivo.objects.create(
        simbolo=symbol,
        sector=sector,
        bloque_estrategico=strategic_bucket,
        pais_exposicion=country,
        tipo_patrimonial=patrimonial,
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=now,
        pais_consulta="argentina",
        simbolo=symbol,
        descripcion=symbol,
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=value,
        pais_titulo=country,
        mercado="BCBA",
        tipo=tipo,
        moneda="ARS",
    )


def _build_services(monkeypatch, covariance_matrix, *, observations=30, mvp_volatilities=None):
    base_service = RiskContributionService()
    cov_service = CovarianceAwareRiskContributionService(base_service=base_service)
    returns = pd.DataFrame({
        "AAPL": [0.01] * observations,
        "MSFT": [0.01] * observations,
        "BOND": [0.002] * observations,
    })
    covariance_df = pd.DataFrame(
        covariance_matrix,
        index=["AAPL", "MSFT", "BOND"],
        columns=["AAPL", "MSFT", "BOND"],
    )
    monkeypatch.setattr(
        cov_service.covariance_service,
        "build_model_inputs",
        lambda activos, lookback_days=252: {
            "observations": observations,
            "returns": returns[activos],
            "expected_returns": np.array([0.1] * len(activos)),
            "covariance_matrix": covariance_df.loc[activos, activos].to_numpy(),
        },
    )
    if mvp_volatilities:
        monkeypatch.setattr(
            base_service,
            "_resolve_volatility_proxy",
            lambda position, param, lookback_days=90: _VolatilityResolution(
                value=mvp_volatilities[position.simbolo],
                used_fallback=False,
            ),
        )
    return base_service, cov_service


@pytest.mark.django_db
def test_covariance_aware_highlights_correlated_cluster_more_than_mvp(monkeypatch):
    now = timezone.now()
    _make_position(now, "AAPL", "Tecnologia", "USA", "Equity", 1000)
    _make_position(now, "MSFT", "Tecnologia", "USA", "Equity", 1000)
    _make_position(now, "BOND", "Soberano", "Argentina", "Bond", 1000, strategic_bucket="Argentina", tipo="TitulosPublicos")

    covariance = np.array(
        [
            [0.09, 0.08, 0.00],
            [0.08, 0.09, 0.00],
            [0.00, 0.00, 0.02],
        ]
    )
    mvp_service, cov_service = _build_services(
        monkeypatch,
        covariance,
        mvp_volatilities={"AAPL": 0.30, "MSFT": 0.30, "BOND": 0.30},
    )

    mvp = mvp_service.calculate(top_n=3)
    advanced = cov_service.calculate(top_n=3)

    mvp_by_symbol = {item["symbol"]: item for item in mvp["items"]}
    advanced_by_symbol = {item["symbol"]: item for item in advanced["items"]}

    assert mvp_by_symbol["AAPL"]["contribution_pct"] == pytest.approx(33.33, abs=0.02)
    assert mvp_by_symbol["MSFT"]["contribution_pct"] == pytest.approx(33.33, abs=0.02)
    assert mvp_by_symbol["BOND"]["contribution_pct"] == pytest.approx(33.33, abs=0.02)

    assert advanced["model_variant"] == "covariance_aware"
    assert advanced_by_symbol["AAPL"]["contribution_pct"] > advanced_by_symbol["BOND"]["contribution_pct"]
    assert advanced_by_symbol["MSFT"]["contribution_pct"] > advanced_by_symbol["BOND"]["contribution_pct"]


@pytest.mark.django_db
def test_covariance_aware_stays_close_to_mvp_when_covariance_is_diagonal(monkeypatch):
    now = timezone.now()
    _make_position(now, "AAPL", "Tecnologia", "USA", "Equity", 1000)
    _make_position(now, "MSFT", "Tecnologia", "USA", "Equity", 1000)
    _make_position(now, "BOND", "Soberano", "Argentina", "Bond", 1000, strategic_bucket="Argentina", tipo="TitulosPublicos")

    covariance = np.diag([0.09, 0.09, 0.09])
    mvp_service, cov_service = _build_services(
        monkeypatch,
        covariance,
        mvp_volatilities={"AAPL": 0.30, "MSFT": 0.30, "BOND": 0.30},
    )

    mvp = mvp_service.calculate(top_n=3)
    advanced = cov_service.calculate(top_n=3)

    mvp_by_symbol = {item["symbol"]: item for item in mvp["items"]}
    advanced_by_symbol = {item["symbol"]: item for item in advanced["items"]}

    for symbol in ["AAPL", "MSFT", "BOND"]:
        assert advanced_by_symbol[symbol]["contribution_pct"] == pytest.approx(
            mvp_by_symbol[symbol]["contribution_pct"],
            abs=0.05,
        )
