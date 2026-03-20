from datetime import timedelta

import pytest
from unittest.mock import patch
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.temporal_metrics_service import TemporalMetricsService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


@pytest.mark.django_db
class TestTemporalMetricsService:
    def test_returns_empty_without_snapshots(self):
        service = TemporalMetricsService()
        assert service.get_portfolio_returns(days=30) == {}

    def test_portfolio_returns_with_snapshots(self):
        today = timezone.now().date()
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=1),
            total_iol=1000,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )
        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=1100,
            liquidez_operativa=220,
            cash_management=110,
            portafolio_invertido=770,
            rendimiento_total=10.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )

        with patch(
            "apps.core.services.temporal_metrics_service.LocalMacroSeriesService.get_context_summary",
            return_value={
                "portfolio_return_ytd_nominal": 10.0,
                "portfolio_return_ytd_real": 4.0,
                "portfolio_return_ytd_is_partial": False,
                "portfolio_return_ytd_base_date": today - timedelta(days=60),
                "ipc_nacional_variation_ytd": 5.77,
            },
        ), patch(
            "apps.core.services.temporal_metrics_service.LocalMacroSeriesService.get_real_historical_metrics",
            return_value={"max_drawdown_real": -3.25, "real_history_observations": 20},
        ):
            service = TemporalMetricsService()
            returns = service.get_portfolio_returns(days=30)

        assert returns["total_period_return"] == 10.0
        assert returns["daily_return"] == 10.0
        assert "max_drawdown" in returns
        assert returns["portfolio_return_ytd_real"] == 4.0
        assert returns["ipc_ytd"] == 5.77
        assert returns["max_drawdown_real"] == -3.25
        assert returns["portfolio_return_ytd_base_date"] == (today - timedelta(days=60)).isoformat()
        assert returns["robust_history_available"] is False
        assert returns["robust_history_min_days"] == 60

    @patch("apps.dashboard.selectors.get_evolucion_historica")
    def test_returns_fallback_when_single_snapshot(self, mock_evolution):
        today = timezone.now().date()
        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=1000,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )
        mock_evolution.return_value = {
            "tiene_datos": True,
            "fechas": ["2026-03-10", "2026-03-11", "2026-03-12"],
            "total_iol": [1000, 1100, 1210],
            "liquidez_operativa": [200, 210, 220],
            "portafolio_invertido": [700, 780, 860],
            "cash_management": [100, 110, 130],
        }

        service = TemporalMetricsService()
        returns = service.get_portfolio_returns(days=30)

        assert returns["total_period_return"] == 21.0
        assert returns["daily_return"] == 10.0
        assert returns["fallback_source"] == "evolucion_historica"
        assert returns["robust_history_available"] is False

    def test_portfolio_volatility_with_snapshots(self):
        today = timezone.now().date()
        for offset, value in [(4, 1000), (3, 1100), (2, 1050), (1, 1200), (0, 1180)]:
            PortfolioSnapshot.objects.create(
                fecha=today - timedelta(days=offset),
                total_iol=value,
                liquidez_operativa=200,
                cash_management=100,
                portafolio_invertido=700,
                rendimiento_total=0.0,
                exposicion_usa=50.0,
                exposicion_argentina=50.0,
            )

        service = TemporalMetricsService()
        volatility = service.get_portfolio_volatility(days=30)

        assert "daily_volatility" in volatility
        assert "annualized_volatility" in volatility
        assert volatility["daily_volatility"] > 0

    def test_portfolio_volatility_uses_iol_proxy_fallback_when_snapshot_history_is_insufficient(self):
        today = timezone.now().date()
        extraction = timezone.make_aware(timezone.datetime(2026, 3, 20, 10, 0, 0))

        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=1000,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=extraction,
            pais_consulta="argentina",
            simbolo="GGAL",
            descripcion="GGAL",
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100,
            ppc=90,
            ganancia_porcentaje=0,
            ganancia_dinero=0,
            valorizado=1000,
            pais_titulo="Argentina",
            mercado="BCBA",
            tipo="ACCIONES",
            plazo="T0",
            moneda="ARS",
        )
        for offset, close in enumerate([100, 101, 103, 102, 104, 106]):
            IOLHistoricalPriceSnapshot.objects.create(
                simbolo="GGAL",
                mercado="BCBA",
                source="iol",
                fecha=today - timedelta(days=5 - offset),
                close=close,
            )

        service = TemporalMetricsService()
        volatility = service.get_portfolio_volatility(days=30)

        assert volatility["fallback_source"] == "iol_historical_prices_proxy"
        assert "annualized_volatility" in volatility
        assert volatility["proxy_coverage_pct"] == 100.0

    def test_calculate_max_drawdown_uses_running_peak(self):
        service = TemporalMetricsService()
        result = service._calculate_max_drawdown([100, 120, 90, 110])
        assert round(result, 2) == -25.0

    @patch("apps.core.services.temporal_metrics_service.TrackingErrorService.calculate")
    @patch("apps.core.services.temporal_metrics_service.CVaRService.calculate_cvar_set")
    @patch("apps.core.services.temporal_metrics_service.VaRService.calculate_var_set")
    @patch("apps.core.services.temporal_metrics_service.AttributionService.calculate_attribution")
    @patch("apps.core.services.temporal_metrics_service.TemporalMetricsService.get_portfolio_volatility")
    @patch("apps.core.services.temporal_metrics_service.TemporalMetricsService.get_portfolio_returns")
    def test_performance_metrics_collects_fallback_sources(
        self,
        mock_returns,
        mock_volatility,
        mock_attribution,
        mock_var,
        mock_cvar,
        mock_benchmarking,
    ):
        mock_returns.return_value = {"total_period_return": 10.0, "fallback_source": "evolucion_historica"}
        mock_volatility.return_value = {"annualized_volatility": 12.0, "fallback_source": "iol_historical_prices_proxy"}
        mock_var.return_value = {"historical_var_95_1d": 2.0, "fallback_source": "iol_historical_prices_proxy"}
        mock_cvar.return_value = {"historical_cvar_95_1d": 3.0}
        mock_benchmarking.return_value = {"tracking_error_annualized": 5.0, "fallback_source": "iol_historical_prices_proxy"}
        mock_attribution.return_value = {}

        metrics = TemporalMetricsService().get_performance_metrics(days=90)

        assert metrics["fallback_sources"] == {
            "returns": "evolucion_historica",
            "volatility": "iol_historical_prices_proxy",
            "var": "iol_historical_prices_proxy",
            "benchmarking": "iol_historical_prices_proxy",
        }

    @patch("apps.core.services.temporal_metrics_service.TemporalMetricsService.get_portfolio_volatility")
    @patch("apps.core.services.temporal_metrics_service.TemporalMetricsService.get_portfolio_returns")
    @patch("apps.dashboard.selectors.get_evolucion_historica")
    def test_historical_comparison_marks_partial_windows(self, mock_evolution, mock_returns, mock_volatility):
        mock_evolution.return_value = {
            "tiene_datos": True,
            "fechas": ["2026-03-10", "2026-03-11", "2026-03-12"],
            "total_iol": [1000, 1100, 1210],
            "liquidez_operativa": [200, 210, 220],
            "portafolio_invertido": [700, 780, 860],
            "cash_management": [100, 110, 130],
        }
        mock_returns.side_effect = [
            {
                "total_period_return": 21.0,
                "history_span_days": 2,
                "observations": 3,
                "fallback_source": "evolucion_historica",
            },
            {
                "total_period_return": 21.0,
                "history_span_days": 2,
                "observations": 3,
                "fallback_source": "evolucion_historica",
            },
        ]
        mock_volatility.return_value = {
            "annualized_volatility": 12.34,
            "fallback_source": "iol_historical_prices_proxy",
            "proxy_coverage_pct": 80.0,
        }

        service = TemporalMetricsService()
        comparison = service.get_historical_comparison([7, 30])

        assert comparison["7d"]["is_partial_window"] is True
        assert comparison["30d"]["available_history_days"] == 2
        assert comparison["30d"]["volatility"] == 12.34
        assert comparison["30d"]["returns_fallback_source"] == "evolucion_historica"
        assert comparison["30d"]["volatility_fallback_source"] == "iol_historical_prices_proxy"
        assert comparison["30d"]["volatility_proxy_coverage_pct"] == 80.0
