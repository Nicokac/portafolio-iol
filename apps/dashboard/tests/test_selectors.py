from django.test import TestCase
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.selectors import (
    get_analytics_mensual,
    get_analytics_v2_dashboard_summary,
    get_concentracion_pais,
    get_concentracion_moneda,
    get_concentracion_moneda_operativa,
    get_concentracion_sector,
    get_concentracion_sector_agregado,
    get_concentracion_tipo_patrimonial,
    get_dashboard_kpis,
    get_distribucion_moneda,
    get_distribucion_moneda_operativa,
    get_distribucion_pais,
    get_distribucion_sector,
    get_distribucion_tipo_patrimonial,
    get_evolucion_historica,
    get_expected_return_detail,
    get_factor_exposure_detail,
    get_incremental_portfolio_simulation,
    get_candidate_asset_ranking,
    get_monthly_allocation_plan,
    get_portafolio_enriquecido_actual,
    get_risk_contribution_detail,
    get_scenario_analysis_detail,
    get_stress_fragility_detail,
    get_riesgo_portafolio,
    get_snapshot_coverage_summary,
    get_riesgo_portafolio_detallado,
    get_senales_rebalanceo,
)
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


def make_activo(fecha, simbolo, valorizado, tipo='ACCIONES', moneda='ARS', **kwargs):
    """Factory helper para crear ActivoPortafolioSnapshot en tests."""
    defaults = dict(
        fecha_extraccion=fecha,
        pais_consulta='argentina',
        simbolo=simbolo,
        descripcion=f'Descripcion {simbolo}',
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=valorizado,
        ppc=valorizado,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo='Argentina',
        mercado='BCBA',
        tipo=tipo,
        moneda=moneda,
    )
    defaults.update(kwargs)
    return ActivoPortafolioSnapshot.objects.create(**defaults)


def make_resumen(fecha, moneda='ARS', disponible=1000.00, **kwargs):
    """Factory helper para crear ResumenCuentaSnapshot en tests."""
    defaults = dict(
        fecha_extraccion=fecha,
        numero_cuenta='123',
        tipo_cuenta='CA',
        moneda=moneda,
        disponible=disponible,
        comprometido=0,
        saldo=disponible,
        titulos_valorizados=0,
        total=disponible,
        estado='activa',
    )
    defaults.update(kwargs)
    return ResumenCuentaSnapshot.objects.create(**defaults)


class TestDashboardSelectors(TestCase):
    def setUp(self):
        cache.clear()

    def test_get_dashboard_kpis_no_data(self):
        kpis = get_dashboard_kpis()
        assert kpis['total_iol'] == 0
        assert kpis['portafolio_invertido'] == 0
        assert kpis['rendimiento_total_porcentaje'] == 0
        assert kpis['rendimiento_total_cost_basis'] == 0
        assert kpis['top_10_concentracion'] == 0
        assert 'methodology' in kpis

    def test_get_dashboard_kpis_with_data(self):
        # Crear datos de prueba
        fecha = timezone.now()
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            pais_consulta='argentina',
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100.00,
            ppc=90.00,
            ganancia_porcentaje=11.11,
            ganancia_dinero=111.10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            mercado='NASDAQ',
            tipo='ACCIONES',
            moneda='USD',
        )

        kpis = get_dashboard_kpis()
        assert kpis['cash_ars'] == Decimal('1000.00')
        assert kpis['cash_usd'] == Decimal('0.00')
        assert kpis['titulos_valorizados'] == Decimal('1000.00')  # AAPL es ACCIONES
        assert kpis['total_iol'] == Decimal('2000.00')  # 1000 activos + 1000 cash ARS
        assert kpis['liquidez_operativa'] == Decimal('1000.00')  # solo cash ARS
        assert kpis['capital_invertido_real'] == Decimal('1000.00')  # total_iol - liquidez_operativa - fci_cash
        assert kpis['rendimiento_total_dinero'] == Decimal('111.10')  # ganancia_dinero del activo
        assert abs(kpis['rendimiento_total_porcentaje'] - Decimal('12.50')) < Decimal('0.01')

    def test_get_dashboard_kpis_with_percentages(self):
        """Test que los KPIs incluyen los porcentajes de los bloques patrimoniales."""
        fecha = timezone.now()
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            pais_consulta='argentina',
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100.00,
            ppc=90.00,
            ganancia_porcentaje=11.11,
            ganancia_dinero=111.10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            mercado='NASDAQ',
            tipo='ACCIONES',
            moneda='USD',
        )

        kpis = get_dashboard_kpis()

        # Verificar que se incluyen los porcentajes
        assert 'pct_fci_cash_management' in kpis
        assert 'pct_portafolio_invertido' in kpis
        assert 'pct_liquidez_total' in kpis

        # Total IOL = 2000, liquidez operativa = 1000, pct_liquidez ya estaba en riesgo_portafolio
        # pct_fci_cash_management debería ser 0% (no hay FCI cash)
        # pct_portafolio_invertido debería ser 50% (1000/2000)
        assert kpis['pct_fci_cash_management'] == 0.0
        assert kpis['pct_portafolio_invertido'] == 50.0
        assert kpis['pct_liquidez_total'] == 50.0

    def test_pct_liquidez_usa_total_iol_como_base(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(simbolo='AAPL', sector='Tecnología', bloque_estrategico='Growth', pais_exposicion='USA', tipo_patrimonial='Growth')
        ParametroActivo.objects.create(simbolo='CAU1', sector='Liquidez', bloque_estrategico='Liquidez', pais_exposicion='Argentina', tipo_patrimonial='Cash')
        ParametroActivo.objects.create(simbolo='ADBAICA', sector='Cash Mgmt', bloque_estrategico='Liquidez', pais_exposicion='Argentina', tipo_patrimonial='FCI')
        make_activo(fecha, 'AAPL', valorizado=1300.00, tipo='ACCIONES', moneda='USD')
        make_activo(fecha, 'CAU1', valorizado=1000.00, tipo='CAUCIONESPESOS')
        make_activo(fecha, 'ADBAICA', valorizado=500.00, tipo='FondoComundeInversion')
        make_resumen(fecha, disponible=200.00)

        riesgo = get_riesgo_portafolio_detallado()

        assert abs(float(riesgo['pct_liquidez']) - 40.0) < 0.01

    def test_pct_renta_fija_ar_incluye_bonos_argentinos(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(simbolo='GD30', sector='Soberano', bloque_estrategico='Argentina', pais_exposicion='Argentina', tipo_patrimonial='Bond')
        ParametroActivo.objects.create(simbolo='TZX26', sector='CER', bloque_estrategico='Argentina', pais_exposicion='Argentina', tipo_patrimonial='Bond')
        ParametroActivo.objects.create(simbolo='BPOC7', sector='Corporativo', bloque_estrategico='Argentina', pais_exposicion='Argentina', tipo_patrimonial='Bond')
        ParametroActivo.objects.create(simbolo='AAPL', sector='Tecnología', bloque_estrategico='Growth', pais_exposicion='USA', tipo_patrimonial='Growth')
        make_activo(fecha, 'GD30', valorizado=100.00, tipo='TitulosPublicos')
        make_activo(fecha, 'TZX26', valorizado=100.00, tipo='TitulosPublicos')
        make_activo(fecha, 'BPOC7', valorizado=100.00, tipo='TitulosPublicos')
        make_activo(fecha, 'AAPL', valorizado=700.00, tipo='ACCIONES', moneda='USD')

        riesgo = get_riesgo_portafolio_detallado()

        assert abs(float(riesgo['pct_renta_fija_ar']) - 30.0) < 0.01
        assert abs(float(riesgo['pct_bonos_soberanos']) - 30.0) < 0.01

    def test_top_10_concentracion(self):
        """Top 10 debe usar solo portafolio invertido, no liquidez ni cash management."""
        fecha = timezone.now()

        for i in range(12):
            make_activo(fecha, f'ACT{i}', valorizado=1000 - i * 50)

        make_activo(fecha, 'CAU1', valorizado=10000, tipo='CAUCIONESPESOS')
        make_activo(fecha, 'ADBAICA', valorizado=5000, tipo='FondoComundeInversion')

        kpis = get_dashboard_kpis()

        assert abs(float(kpis['top_10_concentracion']) - 89.08) < 0.01

    def test_analytics_v2_dashboard_summary_uses_covariance_model_when_available(self):
        cache.clear()

        covariance_result = {
            "top_contributors": [
                {"symbol": "MSFT", "contribution_pct": 41.2},
            ],
            "by_sector": [
                {"key": "Tecnologia", "contribution_pct": 55.0},
            ],
            "metadata": {"confidence": "medium", "warnings": []},
            "model_variant": "covariance_aware",
            "covariance_observations": 64,
            "coverage_pct": 96.5,
        }
        base_result = {
            "top_contributors": [
                {"symbol": "SPY", "contribution_pct": 25.0},
            ],
            "by_sector": [
                {"key": "Indice", "contribution_pct": 25.0},
            ],
            "metadata": {"confidence": "high", "warnings": []},
        }

        class DummyRiskService:
            def calculate(self):
                return base_result

            def build_recommendation_signals(self, top_n=5):
                return []

        class DummyCovarianceRiskService:
            def __init__(self, base_service=None):
                self.base_service = base_service

            def calculate(self):
                return covariance_result

        class DummyScenarioService:
            def analyze(self, scenario_key):
                return {"total_impact_pct": -5.0, "metadata": {"confidence": "high"}}

            def build_recommendation_signals(self):
                return []

        class DummyFactorService:
            def calculate(self):
                return {
                    "dominant_factor": "growth",
                    "factors": [{"factor": "growth", "exposure_pct": 62.0}],
                    "unknown_assets": [],
                    "metadata": {"confidence": "high"},
                }

            def build_recommendation_signals(self):
                return []

        class DummyStressService:
            def calculate(self, scenario_key):
                return {
                    "scenario_key": scenario_key,
                    "fragility_score": 21.0,
                    "total_loss_pct": -1.2,
                    "metadata": {"confidence": "medium"},
                }

            def build_recommendation_signals(self):
                return []

        class DummyExpectedReturnService:
            def calculate(self):
                return {
                    "expected_return_pct": 8.0,
                    "real_expected_return_pct": 1.0,
                    "metadata": {"confidence": "medium", "warnings": []},
                }

            def build_recommendation_signals(self):
                return []

        with (
            patch("apps.dashboard.selectors.RiskContributionService", DummyRiskService),
            patch("apps.dashboard.selectors.CovarianceAwareRiskContributionService", DummyCovarianceRiskService),
            patch("apps.dashboard.selectors.ScenarioAnalysisService", DummyScenarioService),
            patch("apps.dashboard.selectors.FactorExposureService", DummyFactorService),
            patch("apps.dashboard.selectors.StressFragilityService", DummyStressService),
            patch("apps.dashboard.selectors.ExpectedReturnService", DummyExpectedReturnService),
        ):
            summary = get_analytics_v2_dashboard_summary()

        assert summary["risk_contribution"]["top_asset"]["symbol"] == "MSFT"
        assert summary["risk_contribution"]["top_sector"]["key"] == "Tecnologia"
        assert summary["risk_contribution"]["model_variant"] == "covariance_aware"
        assert summary["risk_contribution"]["covariance_observations"] == 64
        assert summary["risk_contribution"]["coverage_pct"] == 96.5
        assert "MSFT" in summary["risk_contribution"]["interpretation"]
        assert summary["scenario_analysis"]["interpretation"]
        assert "growth" in summary["factor_exposure"]["interpretation"]
        assert "fragilidad" in summary["stress_testing"]["interpretation"].lower()
        assert "retorno esperado estructural" in summary["expected_return"]["interpretation"].lower()

    def test_get_risk_contribution_detail_returns_mvp_proxy_when_covariance_is_not_active(self):
        cache.clear()

        base_result = {
            "items": [
                {
                    "symbol": "SPY",
                    "sector": "Indice",
                    "country": "USA",
                    "asset_type": "etf",
                    "weight_pct": 25.0,
                    "volatility_proxy": 18.5,
                    "risk_score": 0.04625,
                    "contribution_pct": 40.0,
                    "used_volatility_fallback": False,
                }
            ],
            "top_contributors": [{"symbol": "SPY", "contribution_pct": 40.0}],
            "by_sector": [{"key": "Indice", "contribution_pct": 40.0, "weight_pct": 25.0}],
            "by_country": [{"key": "USA", "contribution_pct": 40.0, "weight_pct": 25.0}],
            "metadata": {
                "confidence": "medium",
                "warnings": ["used_fallback:QQQ:insufficient_history"],
                "methodology": "mvp_methodology",
                "limitations": "mvp_limitations",
            },
        }
        covariance_result = {
            "model_variant": "mvp_proxy",
            "covariance_observations": 6,
            "coverage_pct": 72.0,
            "portfolio_volatility_proxy": None,
            "covered_symbols": ["SPY"],
            "excluded_symbols": ["QQQ"],
        }

        class DummyRiskService:
            def calculate(self):
                return base_result

        class DummyCovarianceRiskService:
            def __init__(self, base_service=None):
                self.base_service = base_service

            def calculate(self):
                return covariance_result

        with (
            patch("apps.dashboard.selectors.RiskContributionService", DummyRiskService),
            patch("apps.dashboard.selectors.CovarianceAwareRiskContributionService", DummyCovarianceRiskService),
        ):
            detail = get_risk_contribution_detail()

        assert detail["model_variant"] == "mvp_proxy"
        assert detail["covariance_observations"] == 6
        assert detail["coverage_pct"] == 72.0
        assert detail["portfolio_volatility_proxy"] is None
        assert detail["top_asset"]["symbol"] == "SPY"
        assert detail["top_sector"]["key"] == "Indice"
        assert detail["items"][0]["symbol"] == "SPY"
        assert detail["items"][0]["rank"] == 1
        assert detail["items"][0]["risk_score"] == 0.04625
        assert detail["items"][0]["risk_vs_weight_delta"] == 15.0
        assert detail["by_country"][0]["risk_vs_weight_delta"] == 15.0
        assert detail["warnings"] == ["used_fallback:QQQ:insufficient_history"]

    def test_get_risk_contribution_detail_returns_covariance_variant_when_available(self):
        cache.clear()

        base_result = {
            "items": [],
            "top_contributors": [],
            "by_sector": [],
            "metadata": {"confidence": "low", "warnings": []},
        }
        covariance_result = {
            "items": [
                {
                    "symbol": "MSFT",
                    "sector": "Tecnologia",
                    "country": "USA",
                    "asset_type": "equity",
                    "weight_pct": 18.5,
                    "volatility_proxy": 24.2,
                    "risk_score": 0.081234,
                    "contribution_pct": 44.1,
                    "used_volatility_fallback": False,
                }
            ],
            "top_contributors": [{"symbol": "MSFT", "contribution_pct": 44.1}],
            "by_sector": [{"key": "Tecnologia", "contribution_pct": 44.1, "weight_pct": 18.5}],
            "by_country": [{"key": "USA", "contribution_pct": 44.1, "weight_pct": 18.5}],
            "metadata": {
                "confidence": "high",
                "warnings": [],
                "methodology": "covariance_methodology",
                "limitations": "covariance_limitations",
            },
            "model_variant": "covariance_aware",
            "covariance_observations": 64,
            "coverage_pct": 96.5,
            "portfolio_volatility_proxy": 17.9,
            "covered_symbols": ["MSFT", "SPY", "AAPL"],
            "excluded_symbols": [],
        }

        class DummyRiskService:
            def calculate(self):
                return base_result

        class DummyCovarianceRiskService:
            def __init__(self, base_service=None):
                self.base_service = base_service

            def calculate(self):
                return covariance_result

        with (
            patch("apps.dashboard.selectors.RiskContributionService", DummyRiskService),
            patch("apps.dashboard.selectors.CovarianceAwareRiskContributionService", DummyCovarianceRiskService),
        ):
            detail = get_risk_contribution_detail()

        assert detail["model_variant"] == "covariance_aware"
        assert detail["covariance_observations"] == 64
        assert detail["coverage_pct"] == 96.5
        assert detail["portfolio_volatility_proxy"] == 17.9
        assert detail["top_asset"]["symbol"] == "MSFT"
        assert detail["top_sector"]["key"] == "Tecnologia"
        assert detail["items"][0]["symbol"] == "MSFT"
        assert detail["items"][0]["contribution_pct"] == 44.1
        assert detail["items"][0]["risk_vs_weight_delta"] == 25.6
        assert detail["by_country"][0]["risk_vs_weight_delta"] == 25.6
        assert detail["covered_symbols"] == ["MSFT", "SPY", "AAPL"]

    def test_get_scenario_analysis_detail_returns_ranked_scenarios_and_worst_breakdown(self):
        cache.clear()

        scenario_catalog = [
            {
                "scenario_key": "argentina_stress",
                "label": "Argentina Stress",
                "description": "Shock local severo",
            },
            {
                "scenario_key": "tech_shock",
                "label": "Tech Shock",
                "description": "Caida concentrada en tecnologia",
            },
        ]
        scenario_results = {
            "argentina_stress": {
                "total_impact_pct": -4.3,
                "total_impact_money": -4300.0,
                "by_asset": [
                    {
                        "symbol": "GD30",
                        "market_value": 1000.0,
                        "estimated_impact_pct": -12.0,
                        "estimated_impact_money": -120.0,
                        "transmission_channel": "country",
                    }
                ],
                "by_sector": [{"key": "Soberano", "impact_pct": -7.2, "impact_money": -720.0}],
                "by_country": [{"key": "Argentina", "impact_pct": -9.1, "impact_money": -910.0}],
                "top_negative_contributors": [{"symbol": "GD30"}],
                "metadata": {
                    "confidence": "high",
                    "warnings": [],
                    "methodology": "scenario_methodology",
                    "limitations": "scenario_limitations",
                },
            },
            "tech_shock": {
                "total_impact_pct": -8.1,
                "total_impact_money": -8100.0,
                "by_asset": [
                    {
                        "symbol": "AAPL",
                        "market_value": 1500.0,
                        "estimated_impact_pct": -14.0,
                        "estimated_impact_money": -210.0,
                        "transmission_channel": "sector",
                    }
                ],
                "by_sector": [{"key": "Tecnologia", "impact_pct": -11.5, "impact_money": -1150.0}],
                "by_country": [{"key": "USA", "impact_pct": -8.8, "impact_money": -880.0}],
                "top_negative_contributors": [{"symbol": "AAPL"}],
                "metadata": {
                    "confidence": "medium",
                    "warnings": ["partial_coverage"],
                    "methodology": "scenario_methodology",
                    "limitations": "scenario_limitations",
                },
            },
        }

        class DummyCatalogService:
            def list_scenarios(self):
                return scenario_catalog

        class DummyScenarioService:
            def analyze(self, scenario_key):
                return scenario_results[scenario_key]

        with (
            patch("apps.dashboard.selectors.ScenarioCatalogService", DummyCatalogService),
            patch("apps.dashboard.selectors.ScenarioAnalysisService", DummyScenarioService),
        ):
            detail = get_scenario_analysis_detail()

        assert [row["scenario_key"] for row in detail["scenarios"]] == ["tech_shock", "argentina_stress"]
        assert detail["scenarios"][0]["severity_rank"] == 1
        assert detail["worst_scenario"]["scenario_key"] == "tech_shock"
        assert detail["worst_scenario"]["top_sector"]["key"] == "Tecnologia"
        assert detail["worst_scenario"]["top_country"]["key"] == "USA"
        assert detail["worst_assets"][0]["symbol"] == "AAPL"
        assert detail["worst_assets"][0]["market_value"] == 1500.0
        assert detail["worst_sectors"][0]["key"] == "Tecnologia"
        assert detail["worst_countries"][0]["key"] == "USA"
        assert detail["confidence"] == "medium"
        assert detail["warnings"] == ["partial_coverage"]

    def test_get_scenario_analysis_detail_handles_empty_or_incomplete_results(self):
        cache.clear()

        scenario_catalog = [
            {
                "scenario_key": "flat_scenario",
                "label": "Flat Scenario",
                "description": "",
            }
        ]

        class DummyCatalogService:
            def list_scenarios(self):
                return scenario_catalog

        class DummyScenarioService:
            def analyze(self, scenario_key):
                assert scenario_key == "flat_scenario"
                return {
                    "total_impact_pct": 0,
                    "total_impact_money": 0,
                    "metadata": {"confidence": "low", "warnings": ["missing_shock"]},
                }

        with (
            patch("apps.dashboard.selectors.ScenarioCatalogService", DummyCatalogService),
            patch("apps.dashboard.selectors.ScenarioAnalysisService", DummyScenarioService),
        ):
            detail = get_scenario_analysis_detail()

        assert len(detail["scenarios"]) == 1
        assert detail["scenarios"][0]["severity_rank"] == 1
        assert detail["scenarios"][0]["total_impact_pct"] == 0.0
        assert detail["worst_scenario"]["scenario_key"] == "flat_scenario"
        assert detail["worst_assets"] == []
        assert detail["worst_sectors"] == []
        assert detail["worst_countries"] == []
        assert detail["warnings"] == ["missing_shock"]

    def test_get_factor_exposure_detail_returns_ranked_factors_and_unknown_assets(self):
        cache.clear()

        factor_result = {
            "factors": [
                {"factor": "value", "exposure_pct": 20.0, "confidence": "medium"},
                {"factor": "growth", "exposure_pct": 55.0, "confidence": "high"},
                {"factor": "defensive", "exposure_pct": 0.0, "confidence": "low"},
            ],
            "dominant_factor": "growth",
            "underrepresented_factors": ["defensive", "dividend"],
            "unknown_assets": ["XYZ", "ABC"],
            "metadata": {
                "confidence": "medium",
                "warnings": ["unknown_assets_count:2"],
                "methodology": "factor_methodology",
                "limitations": "factor_limitations",
            },
        }

        class DummyFactorService:
            def calculate(self):
                return factor_result

        class DummyExplanationService:
            def build_factor_exposure_explanation(self, result):
                assert result is factor_result
                return "Interpretacion factorial"

        with (
            patch("apps.dashboard.selectors.FactorExposureService", DummyFactorService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_factor_exposure_detail()

        assert [row["factor"] for row in detail["factors"]] == ["growth", "value", "defensive"]
        assert detail["factors"][0]["rank"] == 1
        assert detail["factors"][0]["contribution_relative_pct"] == 55.0
        assert detail["dominant_factor"]["factor"] == "growth"
        assert detail["underrepresented_factors"] == ["defensive", "dividend"]
        assert detail["unknown_assets_count"] == 2
        assert detail["unknown_assets"][0]["symbol"] == "XYZ"
        assert detail["interpretation"] == "Interpretacion factorial"
        assert detail["warnings"] == ["unknown_assets_count:2"]

    def test_get_factor_exposure_detail_handles_empty_or_partial_result(self):
        cache.clear()

        factor_result = {
            "factors": [],
            "dominant_factor": None,
            "underrepresented_factors": [],
            "unknown_assets": [],
            "metadata": {"confidence": "low", "warnings": ["empty_portfolio"]},
        }

        class DummyFactorService:
            def calculate(self):
                return factor_result

        class DummyExplanationService:
            def build_factor_exposure_explanation(self, result):
                return ""

        with (
            patch("apps.dashboard.selectors.FactorExposureService", DummyFactorService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_factor_exposure_detail()

        assert detail["factors"] == []
        assert detail["dominant_factor"] is None
        assert detail["unknown_assets"] == []
        assert detail["unknown_assets_count"] == 0
        assert detail["confidence"] == "low"
        assert detail["warnings"] == ["empty_portfolio"]

    def test_get_stress_fragility_detail_returns_ranked_stresses_and_breakdowns(self):
        cache.clear()

        stress_catalog = [
            {
                "stress_key": "usa_crash_severe",
                "label": "Crash USA severo",
                "description": "Stress USA",
            },
            {
                "stress_key": "local_crisis_severe",
                "label": "Crisis local severa",
                "description": "Stress local",
            },
        ]
        stress_results = {
            "usa_crash_severe": {
                "scenario_key": "usa_crash_severe",
                "fragility_score": 18.0,
                "total_loss_pct": -5.1,
                "total_loss_money": -5100.0,
                "vulnerable_assets": [
                    {
                        "symbol": "SPY",
                        "market_value": 1000.0,
                        "estimated_impact_pct": -12.0,
                        "estimated_impact_money": -120.0,
                        "transmission_channel": "market",
                    }
                ],
                "vulnerable_sectors": [{"key": "Indice", "impact_pct": -4.8, "impact_money": -480.0}],
                "vulnerable_countries": [{"key": "USA", "impact_pct": -5.1, "impact_money": -510.0}],
                "metadata": {
                    "confidence": "high",
                    "warnings": [],
                    "methodology": "stress_methodology",
                    "limitations": "stress_limitations",
                },
            },
            "local_crisis_severe": {
                "scenario_key": "local_crisis_severe",
                "fragility_score": 42.0,
                "total_loss_pct": -12.4,
                "total_loss_money": -12400.0,
                "vulnerable_assets": [
                    {
                        "symbol": "GD30",
                        "market_value": 900.0,
                        "estimated_impact_pct": -18.0,
                        "estimated_impact_money": -162.0,
                        "transmission_channel": "country+fx",
                    }
                ],
                "vulnerable_sectors": [{"key": "Soberano", "impact_pct": -8.2, "impact_money": -820.0}],
                "vulnerable_countries": [{"key": "Argentina", "impact_pct": -12.4, "impact_money": -1240.0}],
                "metadata": {
                    "confidence": "medium",
                    "warnings": ["legacy_mappings:argentina_crisis"],
                    "methodology": "stress_methodology",
                    "limitations": "stress_limitations",
                },
            },
        }

        class DummyStressCatalogService:
            def list_stresses(self):
                return stress_catalog

        class DummyStressService:
            def calculate(self, stress_key):
                return stress_results[stress_key]

        class DummyExplanationService:
            def build_stress_fragility_explanation(self, result):
                assert result["scenario_key"] == "local_crisis_severe"
                return "Interpretacion stress"

        with (
            patch("apps.dashboard.selectors.StressCatalogService", DummyStressCatalogService),
            patch("apps.dashboard.selectors.StressFragilityService", DummyStressService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_stress_fragility_detail()

        assert [row["stress_key"] for row in detail["stresses"]] == ["local_crisis_severe", "usa_crash_severe"]
        assert detail["stresses"][0]["severity_rank"] == 1
        assert detail["worst_stress"]["stress_key"] == "local_crisis_severe"
        assert detail["worst_stress"]["top_sector"]["key"] == "Soberano"
        assert detail["worst_stress"]["top_country"]["key"] == "Argentina"
        assert detail["worst_assets"][0]["symbol"] == "GD30"
        assert detail["worst_sectors"][0]["key"] == "Soberano"
        assert detail["worst_countries"][0]["key"] == "Argentina"
        assert detail["confidence"] == "medium"
        assert detail["warnings"] == ["legacy_mappings:argentina_crisis"]
        assert detail["interpretation"] == "Interpretacion stress"

    def test_get_stress_fragility_detail_handles_empty_or_partial_result(self):
        cache.clear()

        stress_catalog = [
            {
                "stress_key": "flat_stress",
                "label": "Flat Stress",
                "description": "",
            }
        ]

        class DummyStressCatalogService:
            def list_stresses(self):
                return stress_catalog

        class DummyStressService:
            def calculate(self, stress_key):
                assert stress_key == "flat_stress"
                return {
                    "scenario_key": "flat_stress",
                    "fragility_score": 0,
                    "total_loss_pct": 0,
                    "total_loss_money": 0,
                    "metadata": {"confidence": "low", "warnings": ["empty_portfolio"]},
                }

        class DummyExplanationService:
            def build_stress_fragility_explanation(self, result):
                return ""

        with (
            patch("apps.dashboard.selectors.StressCatalogService", DummyStressCatalogService),
            patch("apps.dashboard.selectors.StressFragilityService", DummyStressService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_stress_fragility_detail()

        assert len(detail["stresses"]) == 1
        assert detail["stresses"][0]["severity_rank"] == 1
        assert detail["stresses"][0]["total_loss_pct"] == 0.0
        assert detail["worst_stress"]["stress_key"] == "flat_stress"
        assert detail["worst_assets"] == []
        assert detail["worst_sectors"] == []
        assert detail["worst_countries"] == []
        assert detail["warnings"] == ["empty_portfolio"]

    def test_get_expected_return_detail_returns_ranked_buckets_and_dominant_bucket(self):
        cache.clear()

        expected_return_result = {
            "expected_return_pct": 18.4,
            "real_expected_return_pct": 2.1,
            "basis_reference": "weighted_bucket_baseline_current_positions",
            "by_bucket": [
                {
                    "bucket_key": "fixed_income_ar",
                    "label": "Renta fija AR",
                    "weight_pct": 30.0,
                    "expected_return_pct": 14.0,
                    "basis_reference": "benchmark:bonos_ar:daily_trailing_100",
                },
                {
                    "bucket_key": "equity_beta",
                    "label": "Equity beta / CEDEAR",
                    "weight_pct": 55.0,
                    "expected_return_pct": 22.0,
                    "basis_reference": "benchmark:cedear_usa:daily_trailing_180",
                },
            ],
            "metadata": {
                "confidence": "high",
                "warnings": ["missing_badlar"],
                "methodology": "expected_return_methodology",
                "limitations": "expected_return_limitations",
            },
        }

        class DummyExpectedReturnService:
            def calculate(self):
                return expected_return_result

        class DummyExplanationService:
            def build_expected_return_explanation(self, result):
                assert result is expected_return_result
                return "Interpretacion expected return"

        with (
            patch("apps.dashboard.selectors.ExpectedReturnService", DummyExpectedReturnService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_expected_return_detail()

        assert detail["expected_return_pct"] == 18.4
        assert detail["real_expected_return_pct"] == 2.1
        assert [row["bucket_key"] for row in detail["bucket_rows"]] == ["equity_beta", "fixed_income_ar"]
        assert detail["bucket_rows"][0]["rank"] == 1
        assert detail["bucket_rows"][0]["contribution_relative_pct"] == 12.1
        assert detail["dominant_bucket"]["bucket_key"] == "equity_beta"
        assert detail["main_warning"] == "missing_badlar"
        assert detail["interpretation"] == "Interpretacion expected return"
        assert detail["asset_rows"] == []

    def test_get_expected_return_detail_handles_empty_or_partial_result(self):
        cache.clear()

        expected_return_result = {
            "expected_return_pct": 0,
            "real_expected_return_pct": None,
            "basis_reference": "weighted_bucket_baseline_current_positions",
            "by_bucket": [],
            "metadata": {"confidence": "low", "warnings": []},
        }

        class DummyExpectedReturnService:
            def calculate(self):
                return expected_return_result

        class DummyExplanationService:
            def build_expected_return_explanation(self, result):
                return ""

        with (
            patch("apps.dashboard.selectors.ExpectedReturnService", DummyExpectedReturnService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_expected_return_detail()

        assert detail["expected_return_pct"] == 0
        assert detail["real_expected_return_pct"] is None
        assert detail["bucket_rows"] == []
        assert detail["dominant_bucket"] is None
        assert detail["main_warning"] is None
        assert detail["warnings"] == []
        assert detail["confidence"] == "low"

    def test_get_monthly_allocation_plan_reuses_service_output(self):
        cache.clear()

        expected_plan = {
            "capital_total": 600000,
            "recommended_blocks_count": 2,
            "criterion": "rules_based_analytics_v2_mvp",
            "recommended_blocks": [
                {
                    "bucket": "defensive",
                    "suggested_amount": 350000,
                    "score_breakdown": {"positive_signals": [], "negative_signals": [], "notes": ""},
                },
                {
                    "bucket": "dividend",
                    "suggested_amount": 250000,
                    "score_breakdown": {"positive_signals": [], "negative_signals": [], "notes": ""},
                },
            ],
            "avoided_blocks": [{"bucket": "tech_growth"}],
            "explanation": "Plan incremental",
        }

        class DummyMonthlyAllocationService:
            def build_plan(self, capital_amount):
                assert capital_amount == 600000
                return expected_plan

        with patch("apps.dashboard.selectors.MonthlyAllocationService", DummyMonthlyAllocationService):
            detail = get_monthly_allocation_plan()

        assert detail["capital_total"] == 600000
        assert detail["recommended_blocks_count"] == 2
        assert detail["recommended_blocks"][0]["bucket"] == "defensive"
        assert "score_breakdown" in detail["recommended_blocks"][0]
        assert detail["avoided_blocks"][0]["bucket"] == "tech_growth"

    def test_get_candidate_asset_ranking_reuses_service_output(self):
        cache.clear()

        expected_ranking = {
            "capital_total": 600000,
            "candidate_assets_count": 2,
            "candidate_assets": [
                {
                    "asset": "KO",
                    "block": "defensive",
                    "block_label": "Defensive / resiliente",
                    "score": 8.4,
                    "rank": 1,
                    "reasons": ["defensive_sector_match"],
                    "main_reason": "defensive_sector_match",
                },
                {
                    "asset": "SPY",
                    "block": "global_index",
                    "block_label": "Indice global",
                    "score": 6.8,
                    "rank": 1,
                    "reasons": ["stable_global_exposure"],
                    "main_reason": "stable_global_exposure",
                },
            ],
            "by_block": [],
            "explanation": "Ranking incremental",
        }

        class DummyCandidateAssetRankingService:
            def build_ranking(self, capital_amount):
                assert capital_amount == 600000
                return expected_ranking

        with patch("apps.dashboard.selectors.CandidateAssetRankingService", DummyCandidateAssetRankingService):
            detail = get_candidate_asset_ranking()

        assert detail["capital_total"] == 600000
        assert detail["candidate_assets_count"] == 2
        assert detail["candidate_assets"][0]["asset"] == "KO"
        assert detail["candidate_assets"][0]["main_reason"] == "defensive_sector_match"

    def test_get_incremental_portfolio_simulation_builds_default_purchase_plan(self):
        cache.clear()

        monthly_plan = {
            "capital_total": 600000,
            "recommended_blocks": [
                {"bucket": "defensive", "label": "Defensive / resiliente", "suggested_amount": 350000},
                {"bucket": "global_index", "label": "Indice global", "suggested_amount": 250000},
            ],
        }
        candidate_ranking = {
            "by_block": [
                {
                    "block": "defensive",
                    "candidates": [{"asset": "KO", "score": 8.4, "main_reason": "defensive_sector_match"}],
                },
                {
                    "block": "global_index",
                    "candidates": [{"asset": "SPY", "score": 6.8, "main_reason": "stable_global_exposure"}],
                },
            ]
        }
        simulator_result = {
            "capital_amount": 600000.0,
            "purchase_plan": [
                {"symbol": "KO", "amount": 350000.0},
                {"symbol": "SPY", "amount": 250000.0},
            ],
            "before": {"expected_return_pct": 8.0},
            "after": {"expected_return_pct": 8.6},
            "delta": {
                "expected_return_change": 0.6,
                "real_expected_return_change": 0.2,
                "fragility_change": -3.0,
                "scenario_loss_change": 0.7,
                "risk_concentration_change": -1.4,
            },
            "interpretation": "La compra reduce la fragilidad del portafolio.",
            "warnings": [],
        }

        class DummyIncrementalPortfolioSimulator:
            def simulate(self, proposal):
                assert proposal["capital_amount"] == 600000
                assert proposal["purchase_plan"] == [
                    {"symbol": "KO", "amount": 350000.0},
                    {"symbol": "SPY", "amount": 250000.0},
                ]
                return simulator_result

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: monthly_plan),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: candidate_ranking),
            patch("apps.dashboard.selectors.IncrementalPortfolioSimulator", DummyIncrementalPortfolioSimulator),
        ):
            detail = get_incremental_portfolio_simulation()

        assert detail["selected_candidates"][0]["symbol"] == "KO"
        assert detail["selected_candidates"][1]["symbol"] == "SPY"
        assert detail["delta"]["fragility_change"] == -3.0
        assert detail["selection_basis"] == "top_candidate_per_recommended_block"

    def test_concentracion_por_pais(self):
        """Debe distinguir base invertida vs base total IOL."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='Estados Unidos',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='YPF',
            sector='Energía',
            bloque_estrategico='Inversión',
            pais_exposicion='Argentina',
            tipo_patrimonial='Equity',
        )
        ParametroActivo.objects.create(
            simbolo='ADBAICA',
            sector='Cash Mgmt',
            bloque_estrategico='Liquidez',
            pais_exposicion='Argentina',
            tipo_patrimonial='FCI',
        )
        ParametroActivo.objects.create(
            simbolo='CAU1',
            sector='Liquidez',
            bloque_estrategico='Liquidez',
            pais_exposicion='Argentina',
            tipo_patrimonial='Cash',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, moneda='USD')
        make_activo(fecha, 'YPF', valorizado=500.00)
        make_activo(fecha, 'ADBAICA', valorizado=200.00, tipo='FondoComundeInversion')
        make_activo(fecha, 'CAU1', valorizado=300.00, tipo='CAUCIONESPESOS')
        make_resumen(fecha, disponible=400.00)

        concentracion = get_concentracion_pais()
        concentracion_total_iol = get_concentracion_pais(base='total_iol')

        assert abs(concentracion['USA'] - 66.67) < 0.01
        assert abs(concentracion['Argentina'] - 33.33) < 0.01
        assert abs(concentracion_total_iol['USA'] - 41.67) < 0.01
        assert abs(concentracion_total_iol['Argentina'] - 58.33) < 0.01

    def test_rendimiento_total_usa_solo_portafolio_invertido_sobre_costo_estimado(self):
        fecha = timezone.now()

        make_activo(fecha, 'AAPL', valorizado=1000.00, ganancia_dinero=200.00, tipo='ACCIONES', moneda='USD')
        make_activo(fecha, 'ADBAICA', valorizado=500.00, ganancia_dinero=50.00, tipo='FondoComundeInversion')
        make_activo(fecha, 'CAU1', valorizado=1500.00, ganancia_dinero=10.00, tipo='CAUCIONESPESOS')

        kpis = get_dashboard_kpis()

        assert abs(float(kpis['rendimiento_total_porcentaje']) - 25.0) < 0.01

    def test_concentracion_por_tipo_patrimonial(self):
        """Test cálculo de concentración por tipo patrimonial."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, moneda='USD')

        concentracion = get_concentracion_tipo_patrimonial()
        assert 'Growth' in concentracion
        assert concentracion['Growth'] == 100.0

    def test_concentracion_sector_agregado_unifica_subsectores_tecnologicos(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='MELI',
            sector='Tecnología / E-commerce',
            bloque_estrategico='Growth',
            pais_exposicion='Latam',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='AMD',
            sector='Tecnología / Semiconductores',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='KO',
            sector='Consumo defensivo',
            bloque_estrategico='Dividendos',
            pais_exposicion='USA',
            tipo_patrimonial='Equity',
        )
        make_activo(fecha, 'AAPL', valorizado=400.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'MELI', valorizado=300.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'AMD', valorizado=100.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'KO', valorizado=200.00, tipo='CEDEARS', moneda='USD')

        concentracion = get_concentracion_sector_agregado()

        assert abs(float(concentracion['Tecnologia Total']) - 80.0) < 0.01
        assert abs(float(concentracion['Consumo defensivo']) - 20.0) < 0.01

    def test_distribucion_moneda_vs_moneda_operativa(self):
        """Test diferencia entre exposición económica vs operativa."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='CEDEARS', moneda='peso_Argentino')

        # Moneda económica (exposición real)
        distribucion_economica = get_distribucion_moneda()
        assert distribucion_economica['USD'] == 1000.00  # Exposición real USD

        # Moneda operativa (cotización)
        distribucion_operativa = get_distribucion_moneda_operativa()
        assert distribucion_operativa['ARS'] == 1000.00  # Cotiza en ARS

        concentracion_economica = get_concentracion_moneda()
        concentracion_operativa = get_concentracion_moneda_operativa()
        assert concentracion_economica['USD'] == 100.0
        assert concentracion_operativa['ARS'] == 100.0

    def test_senales_rebalanceo_objetivos(self):
        """Test señales de rebalanceo basadas en objetivos."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=20000.00, tipo='CEDEARS', moneda='peso_Argentino', cantidad=100)
        make_resumen(fecha, disponible=50000.00)

        senales = get_senales_rebalanceo()

        # Debería haber señales de sobreponderación
        assert len(senales['sectorial_sobreponderado']) > 0 or len(senales['patrimonial_sobreponderado']) > 0

        # Verificar estructura de señales
        for senal in senales['sectorial_sobreponderado'] + senales['sectorial_subponderado']:
            assert 'categoria' in senal or 'sector' in senal
            assert 'porcentaje' in senal
            assert 'objetivo' in senal
            assert 'diferencia' in senal

    def test_evolucion_historica_fallback(self):
        """Test que evolución histórica muestra mensaje cuando no hay datos suficientes."""
        evolucion = get_evolucion_historica()

        # Sin datos históricos, debería mostrar mensaje
        assert not evolucion['tiene_datos']
        assert 'mensaje' in evolucion
        assert 'Aún no hay historial suficiente' in evolucion['mensaje']

    def test_analytics_mensual_calculos(self):
        """Test cálculos de analytics mensual."""
        fecha = timezone.now()

        # Crear datos históricos para analytics
        for i in range(3):
            fecha_mes = fecha.replace(month=fecha.month - i, day=1)
            make_activo(fecha_mes, 'AAPL', valorizado=1000.00 + i * 100, tipo='CEDEARS', moneda='peso_Argentino')

        analytics = get_analytics_mensual()

        # Debería tener datos de analytics
        assert isinstance(analytics, dict)
        assert len(analytics) > 0  # Al menos algún cálculo

    def test_evolucion_historica_con_datos(self):
        """Test evolución histórica cuando hay datos suficientes."""
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta

        now = timezone.now()
        fecha1 = now - relativedelta(days=5)
        fecha2 = now - relativedelta(days=3)

        make_activo(fecha1, 'AAPL', valorizado=1000.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha2, 'AAPL', valorizado=1100.00, tipo='CEDEARS', moneda='USD')
        make_resumen(fecha1, disponible=500.00)
        make_resumen(fecha2, disponible=600.00)

        evolucion = get_evolucion_historica()
        assert evolucion['tiene_datos'] is True
        assert len(evolucion['fechas']) >= 2
        assert len(evolucion['total_iol']) >= 2

    def test_riesgo_portafolio_detallado_con_parametros(self):
        """Test métricas de riesgo con ParametroActivo populado."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='YPF',
            sector='Energía',
            bloque_estrategico='Defensivo',
            pais_exposicion='Argentina',
            tipo_patrimonial='Bond',
        )
        make_activo(fecha, 'AAPL', valorizado=2000.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'YPF', valorizado=1000.00)
        make_resumen(fecha, disponible=500.00)

        riesgo = get_riesgo_portafolio_detallado()
        assert 'pct_usa' in riesgo
        assert 'pct_argentina' in riesgo
        assert 'pct_tech' in riesgo
        assert riesgo['pct_usa'] > 0
        assert riesgo['pct_argentina'] > 0
        assert riesgo['pct_tech'] > 0

    def test_pct_tech_agrega_subsectores_tecnologicos(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='MELI',
            sector='Tecnología / E-commerce',
            bloque_estrategico='Growth',
            pais_exposicion='Latam',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='AMD',
            sector='Tecnología / Semiconductores',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='KO',
            sector='Consumo defensivo',
            bloque_estrategico='Dividendos',
            pais_exposicion='USA',
            tipo_patrimonial='Equity',
        )

        make_activo(fecha, 'AAPL', valorizado=400.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'MELI', valorizado=300.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'AMD', valorizado=100.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'KO', valorizado=200.00, tipo='CEDEARS', moneda='USD')

        riesgo = get_riesgo_portafolio_detallado()

        assert abs(float(riesgo['pct_tech']) - 80.0) < 0.01

    def test_riesgo_portafolio_con_parametros(self):
        """Test métricas de riesgo simplificadas con ParametroActivo."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='CEDEARS', moneda='USD')
        make_resumen(fecha, disponible=200.00)

        riesgo = get_riesgo_portafolio()
        assert 'volatilidad_estimada' in riesgo
        assert 'exposicion_usa' in riesgo
        assert riesgo['exposicion_usa'] > 0
        assert riesgo['volatilidad_status'] == 'insufficient_history'
        assert riesgo['volatilidad_estimada'] is None

    def test_distribucion_sector_con_datos(self):
        """Test distribución por sector con ParametroActivo."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00)

        distribucion = get_distribucion_sector()
        assert 'Tecnología' in distribucion
        assert distribucion['Tecnología'] == 1000.00

    def test_portafolio_enriquecido_con_tipos(self):
        """Test clasificación de portafolio con distintos tipos de activo."""
        fecha = timezone.now()

        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='CEDEARS')
        make_activo(fecha, 'GGAL', valorizado=500.00, tipo='ACCIONES')
        make_activo(fecha, 'AL30', valorizado=300.00, tipo='TitulosPublicos')

        portafolio = get_portafolio_enriquecido_actual()
        assert 'inversion' in portafolio
        assert 'liquidez' in portafolio
        assert 'fci_cash_management' in portafolio
        assert len(portafolio['inversion']) == 3

    def test_distribucion_moneda_ramas_alternativas(self):
        """Cubre ramas de inferencia de moneda (Hard Assets, ARS default)."""
        fecha = timezone.now()

        # Hard Assets — sin pais_exposicion USA, tipo_patrimonial Hard Assets
        pa_hard = ParametroActivo.objects.create(
            simbolo='ORO',
            sector='Commodities',
            bloque_estrategico='Defensivo',
            pais_exposicion='Global',
            tipo_patrimonial='Hard Assets',
        )
        # Activo con moneda ambigua (no dolar ni peso)
        make_activo(fecha, 'ORO', valorizado=500.00, moneda='otro')
        # Activo ARS explícito
        make_activo(fecha, 'GFGC', valorizado=200.00, moneda='peso_Argentino')

        distribucion = get_distribucion_moneda()
        assert 'Hard Assets' in distribucion or 'ARS' in distribucion

    def test_riesgo_portafolio_ramas_volatilidad(self):
        """Sin snapshots suficientes no debe inventar una volatilidad robusta."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='ORO', sector='Commodities', bloque_estrategico='Defensivo',
            pais_exposicion='Global', tipo_patrimonial='Hard Assets',
        )
        ParametroActivo.objects.create(
            simbolo='AL30', sector='Bonos', bloque_estrategico='Renta Fija',
            pais_exposicion='Argentina', tipo_patrimonial='Bond',
        )
        ParametroActivo.objects.create(
            simbolo='CASH', sector='Liquidez', bloque_estrategico='Liquidez',
            pais_exposicion='Argentina', tipo_patrimonial='Cash',
        )
        ParametroActivo.objects.create(
            simbolo='GGAL', sector='Financiero', bloque_estrategico='Growth',
            pais_exposicion='Argentina', tipo_patrimonial='Equity',
        )
        make_activo(fecha, 'ORO', valorizado=1000.00)
        make_activo(fecha, 'AL30', valorizado=1000.00)
        make_activo(fecha, 'CASH', valorizado=500.00)
        make_activo(fecha, 'GGAL', valorizado=500.00)
        make_resumen(fecha, disponible=200.00)

        riesgo = get_riesgo_portafolio()
        assert 'volatilidad_estimada' in riesgo
        assert riesgo['volatilidad_estimada'] is None
        assert riesgo['volatilidad_status'] == 'insufficient_history'

    def test_senales_rebalanceo_sin_metadata(self):
        """Cubre rama de activos sin metadata completa."""
        fecha = timezone.now()

        # Activo con ParametroActivo con valores N/A
        ParametroActivo.objects.create(
            simbolo='UNKNOWN',
            sector='N/A',
            bloque_estrategico='N/A',
            pais_exposicion='N/A',
            tipo_patrimonial='N/A',
        )
        make_activo(fecha, 'UNKNOWN', valorizado=1000.00)
        make_resumen(fecha, disponible=100.00)

        senales = get_senales_rebalanceo()
        assert isinstance(senales, dict)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_dashboard_kpis_uses_cache_on_second_call(self):
        cache.clear()
        fecha = timezone.now()
        make_resumen(fecha, disponible=1000.00)
        make_activo(fecha, 'AAPL', valorizado=2000.00, tipo='ACCIONES', moneda='USD')

        with CaptureQueriesContext(connection) as first_call_queries:
            get_dashboard_kpis()

        with CaptureQueriesContext(connection) as second_call_queries:
            get_dashboard_kpis()

        assert len(first_call_queries) > 0
        assert len(second_call_queries) < len(first_call_queries)

    def test_snapshot_coverage_summary_with_sparse_history(self):
        fecha = timezone.now().date()

        from apps.portafolio_iol.models import PortfolioSnapshot

        for offset, total in [(5, 1000), (1, 1100), (0, 1200)]:
            PortfolioSnapshot.objects.create(
                fecha=fecha - timedelta(days=offset),
                total_iol=total,
                liquidez_operativa=200,
                cash_management=100,
                portafolio_invertido=700,
                rendimiento_total=0,
                exposicion_usa=50,
                exposicion_argentina=50,
            )

        summary = get_snapshot_coverage_summary(days=30)
        assert summary['snapshots_count'] == 3
        assert summary['status'] == 'insufficient_history'
        assert summary['max_gap_days'] >= 1
        assert summary['latest_snapshot_at'] is not None
