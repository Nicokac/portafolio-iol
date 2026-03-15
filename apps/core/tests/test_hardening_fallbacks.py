from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.portfolio.covariance_service import CovarianceService
from apps.core.services.portfolio_optimizer import PortfolioOptimizer
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


@pytest.mark.django_db
class TestHardeningFallbacks:
    def test_risk_services_return_insufficient_history_warning(self):
        today = timezone.now().date()
        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=1000,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0,
            exposicion_usa=50,
            exposicion_argentina=50,
        )

        volatility = VolatilityService().calculate_volatility(days=30)
        var = VaRService().calculate_var_set()
        cvar = CVaRService().calculate_cvar_set()

        assert volatility["warning"] == "insufficient_history"
        assert var["warning"] == "insufficient_history"
        assert cvar["warning"] == "insufficient_history"

    def test_covariance_service_build_model_inputs_warns_when_empty(self):
        result = CovarianceService().build_model_inputs(["SPY", "AAPL"])
        assert result["warning"] == "insufficient_history"
        assert result["observations"] == 0

    def test_covariance_service_build_model_inputs_reports_observations_when_history_exists(self):
        today = timezone.now()
        for i, (spy, aapl) in enumerate([(1000, 1000), (1010, 1020), (1030, 1010)]):
            fecha = today - timedelta(days=2 - i)
            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha,
                pais_consulta="argentina",
                simbolo="SPY",
                descripcion="SPY",
                cantidad=10,
                comprometido=0,
                disponible_inmediato=10,
                puntos_variacion=0,
                variacion_diaria=0,
                ultimo_precio=100,
                ppc=90,
                ganancia_porcentaje=0,
                ganancia_dinero=0,
                valorizado=spy,
                pais_titulo="USA",
                mercado="BCBA",
                tipo="CEDEARS",
                moneda="ARS",
            )
            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha,
                pais_consulta="argentina",
                simbolo="AAPL",
                descripcion="AAPL",
                cantidad=10,
                comprometido=0,
                disponible_inmediato=10,
                puntos_variacion=0,
                variacion_diaria=0,
                ultimo_precio=100,
                ppc=90,
                ganancia_porcentaje=0,
                ganancia_dinero=0,
                valorizado=aapl,
                pais_titulo="USA",
                mercado="BCBA",
                tipo="CEDEARS",
                moneda="ARS",
            )

        result = CovarianceService().build_model_inputs(["SPY", "AAPL"])

        assert "warning" not in result
        assert result["observations"] == 2

    def test_optimizer_fallback_equal_weights_when_no_history(self):
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_markowitz(["SPY", "AAPL"], target_return=0.08)
        assert "warning" in result
        assert result["pesos_optimos"]["SPY"] == result["pesos_optimos"]["AAPL"]
