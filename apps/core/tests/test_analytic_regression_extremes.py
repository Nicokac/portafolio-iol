from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.performance.attribution_service import AttributionService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.risk.stress_test_service import StressTestService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


@pytest.mark.django_db
class TestAnalyticRegressionAndExtremes:
    def _seed_snapshots(self):
        today = timezone.now().date()
        values = [1000, 1010, 980, 995, 1020, 1005, 1030]
        for i, value in enumerate(values):
            PortfolioSnapshot.objects.create(
                fecha=today - timedelta(days=len(values) - i),
                total_iol=value,
                liquidez_operativa=200,
                cash_management=100,
                portafolio_invertido=value - 300,
                rendimiento_total=0,
                exposicion_usa=50,
                exposicion_argentina=50,
            )

    def test_var_and_sharpe_are_stable_for_same_input(self):
        self._seed_snapshots()
        var_service = VaRService()
        vol_service = VolatilityService()

        first = var_service.calculate_var_set(confidence=0.95)
        second = var_service.calculate_var_set(confidence=0.95)
        vol = vol_service.calculate_volatility(days=90)

        assert first == second
        assert "annualized_volatility" in vol
        assert "sharpe_ratio" in vol or "warning" in vol

    def test_attribution_and_benchmarking_return_consistent_shape(self):
        now = timezone.now()
        early = now - timedelta(days=2)
        late = now - timedelta(days=1)
        ParametroActivo.objects.create(
            simbolo="SPY",
            sector="Indice",
            bloque_estrategico="Core",
            pais_exposicion="USA",
            tipo_patrimonial="ETF",
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=early,
            pais_consulta="argentina",
            simbolo="SPY",
            descripcion="SPY",
            cantidad=1,
            comprometido=0,
            disponible_inmediato=1,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100,
            ppc=100,
            ganancia_porcentaje=0,
            ganancia_dinero=0,
            valorizado=100,
            pais_titulo="USA",
            mercado="NYSE",
            tipo="CEDEARS",
            plazo="T0",
            moneda="ARS",
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=late,
            pais_consulta="argentina",
            simbolo="SPY",
            descripcion="SPY",
            cantidad=1,
            comprometido=0,
            disponible_inmediato=1,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=105,
            ppc=100,
            ganancia_porcentaje=5,
            ganancia_dinero=5,
            valorizado=105,
            pais_titulo="USA",
            mercado="NYSE",
            tipo="CEDEARS",
            plazo="T0",
            moneda="ARS",
        )
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=late,
            numero_cuenta="1",
            tipo_cuenta="ca",
            moneda="ARS",
            disponible=100,
            comprometido=0,
            saldo=100,
            titulos_valorizados=105,
            total=205,
            margen_descubierto=0,
            estado="activa",
        )
        self._seed_snapshots()

        attribution = AttributionService().calculate_attribution(days=30)
        benchmark = TrackingErrorService().calculate(days=30)

        assert "by_asset" in attribution or attribution == {}
        if attribution:
            assert "by_sector" in attribution
        assert isinstance(benchmark, dict)

    def test_stress_test_handles_extreme_shocks_without_breaking(self):
        now = timezone.now()
        ParametroActivo.objects.create(
            simbolo="GGAL",
            sector="Finanzas",
            bloque_estrategico="Argentina",
            pais_exposicion="Argentina",
            tipo_patrimonial="Equity",
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=now,
            pais_consulta="argentina",
            simbolo="GGAL",
            descripcion="GGAL",
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=-15,
            ultimo_precio=100,
            ppc=120,
            ganancia_porcentaje=-16.6,
            ganancia_dinero=-200,
            valorizado=1000,
            pais_titulo="Argentina",
            mercado="BCBA",
            tipo="ACCIONES",
            plazo="T0",
            moneda="ARS",
        )
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=now,
            numero_cuenta="1",
            tipo_cuenta="ca",
            moneda="ARS",
            disponible=500,
            comprometido=0,
            saldo=500,
            titulos_valorizados=1000,
            total=1500,
            margen_descubierto=0,
            estado="activa",
        )

        result = StressTestService().run_all()
        assert "argentina_crisis" in result
        assert "impact_portfolio_pct" in result["argentina_crisis"]
