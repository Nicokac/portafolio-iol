import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import SensitiveActionAudit


@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def auth_client(user):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(username='staffuser', password='testpass123', is_staff=True)


@pytest.fixture
def staff_auth_client(staff_user):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def anon_client():
    return APIClient(raise_request_exception=False)


# --- Endpoints GET ---
GET_ENDPOINTS = [
    'dashboard-kpis',
    'dashboard-concentracion-pais',
    'dashboard-concentracion-sector',
    'dashboard-senales-rebalanceo',
    'catalog-fci',
    'alerts-active',
    'alerts-by-severity',
    'rebalance-suggestions',
    'rebalance-critical',
    'rebalance-opportunity',
    'metrics-returns',
    'metrics-volatility',
    'metrics-performance',
    'metrics-historical-comparison',
    'metrics-macro-comparison',
    'metrics-benchmark-curve',
    'metrics-var',
    'metrics-cvar',
    'metrics-stress-test',
    'metrics-attribution',
    'metrics-benchmarking',
    'metrics-liquidity',
    'metrics-data-quality',
    'historical-evolution',
    'historical-summary',
    'recommendations-all',
    'recommendations-by-priority',
    'portfolio-parameters-get',
]

STAFF_ONLY_GET_ENDPOINTS = [
    'metrics-snapshot-integrity',
    'metrics-sync-audit',
    'metrics-internal-observability',
]

POST_ENDPOINTS = [
    'simulation-purchase',
    'simulation-sale',
    'simulation-rebalance',
    'optimizer-risk-parity',
    'optimizer-markowitz',
    'optimizer-target-allocation',
    'monthly-plan-basic',
    'monthly-plan-custom',
    'portfolio-parameters-update',
]


@pytest.mark.django_db
class TestAPIAuthentication:
    """Verifica que todos los endpoints requieren autenticación."""

    @pytest.mark.parametrize('url_name', GET_ENDPOINTS)
    def test_get_endpoints_require_auth(self, anon_client, url_name):
        url = reverse(url_name)
        response = anon_client.get(url)
        assert response.status_code == 403

    @pytest.mark.parametrize('url_name', STAFF_ONLY_GET_ENDPOINTS)
    def test_staff_only_get_endpoints_require_auth(self, anon_client, url_name):
        url = reverse(url_name)
        response = anon_client.get(url)
        assert response.status_code == 403

    @pytest.mark.parametrize('url_name', POST_ENDPOINTS)
    def test_post_endpoints_require_auth(self, anon_client, url_name):
        url = reverse(url_name)
        response = anon_client.post(url, {}, format='json')
        assert response.status_code == 403


@pytest.mark.django_db
class TestAPIResponseFormat:
    """Verifica que los endpoints autenticados retornan JSON válido."""

    @pytest.mark.parametrize('url_name', GET_ENDPOINTS)
    def test_get_endpoints_return_json(self, auth_client, url_name):
        url = reverse(url_name)
        response = auth_client.get(url)
        assert response.status_code in [200, 400, 404, 500]
        if response.status_code != 500:
            assert response['Content-Type'] == 'application/json'

    @pytest.mark.parametrize('url_name', STAFF_ONLY_GET_ENDPOINTS)
    def test_staff_only_endpoints_reject_non_staff_users(self, auth_client, url_name):
        url = reverse(url_name)
        response = auth_client.get(url)
        assert response.status_code == 403

    @pytest.mark.parametrize('url_name', STAFF_ONLY_GET_ENDPOINTS)
    def test_staff_only_endpoints_allow_staff_users(self, staff_auth_client, url_name):
        url = reverse(url_name)
        response = staff_auth_client.get(url)
        assert response.status_code in [200, 400, 500]
        if response.status_code != 500:
            assert response['Content-Type'] == 'application/json'

    @pytest.mark.parametrize('url_name', POST_ENDPOINTS)
    def test_post_endpoints_return_json(self, auth_client, url_name):
        url = reverse(url_name)
        response = auth_client.post(url, {}, format='json')
        assert response.status_code in [200, 400, 403, 404, 500]
        if response.status_code != 500:
            assert response['Content-Type'] == 'application/json'


@pytest.mark.django_db
class TestAPIThrottling:
    def test_rest_framework_throttling_is_enabled_in_settings(self, settings):
        throttle_classes = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES']
        throttle_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']

        assert 'rest_framework.throttling.AnonRateThrottle' in throttle_classes
        assert 'rest_framework.throttling.UserRateThrottle' in throttle_classes
        assert throttle_rates['anon'] == '100/min'
        assert throttle_rates['user'] == '300/min'

@pytest.mark.django_db
class TestAPIErrorHandling:
    """Verifica que los endpoints manejan excepciones y retornan 500."""

    @pytest.mark.parametrize('url_name,selector_path', [
        ('dashboard-kpis', 'apps.api.views.get_dashboard_kpis'),
        ('dashboard-concentracion-pais', 'apps.api.views.get_concentracion_pais'),
        ('dashboard-concentracion-sector', 'apps.api.views.get_concentracion_sector'),
        ('dashboard-senales-rebalanceo', 'apps.api.views.get_senales_rebalanceo'),
        ('alerts-active', 'apps.api.views.AlertsEngine'),
        ('rebalance-suggestions', 'apps.api.views.RebalanceEngine'),
    ])
    def test_get_endpoint_returns_500_on_exception(self, auth_client, url_name, selector_path):
        from unittest.mock import patch, MagicMock
        with patch(selector_path, side_effect=Exception('forced error')):
            url = reverse(url_name)
            response = auth_client.get(url)
            assert response.status_code == 500
            assert 'error' in response.json()
            assert response.json()['error'] == 'Internal server error'
            assert 'forced error' not in response.json()['error']

    def test_portfolio_parameters_update_does_not_expose_internal_errors(self, staff_auth_client):
        url = reverse('portfolio-parameters-update')
        with patch('apps.core.models.PortfolioParameters.get_active_parameters', side_effect=Exception('forced error')):
            response = staff_auth_client.post(url, {}, format='json')
            assert response.status_code == 500
            assert response.json()['error'] == 'Internal server error'

    @pytest.mark.parametrize('url_name,patch_target,patch_method', [
        ('alerts-by-severity', 'apps.api.views.AlertsEngine', 'get_alerts_by_severity'),
        ('rebalance-critical', 'apps.api.views.RebalanceEngine', 'get_critical_actions'),
        ('rebalance-opportunity', 'apps.api.views.RebalanceEngine', 'get_opportunity_actions'),
        ('metrics-returns', 'apps.api.views.TemporalMetricsService', 'get_portfolio_returns'),
        ('metrics-volatility', 'apps.api.views.TemporalMetricsService', 'get_portfolio_volatility'),
        ('metrics-performance', 'apps.api.views.TemporalMetricsService', 'get_performance_metrics'),
        ('metrics-historical-comparison', 'apps.api.views.TemporalMetricsService', 'get_historical_comparison'),
        ('metrics-macro-comparison', 'apps.api.views.LocalMacroSeriesService', 'build_macro_comparison'),
        ('metrics-benchmark-curve', 'apps.api.views.TrackingErrorService', 'build_comparison_curve'),
        ('metrics-var', 'apps.api.views.VaRService', 'calculate_var_set'),
        ('metrics-cvar', 'apps.api.views.CVaRService', 'calculate_cvar_set'),
        ('metrics-stress-test', 'apps.api.views.StressTestService', 'run_all'),
        ('metrics-attribution', 'apps.api.views.AttributionService', 'calculate_attribution'),
        ('metrics-benchmarking', 'apps.api.views.TrackingErrorService', 'calculate'),
        ('metrics-liquidity', 'apps.api.views.LiquidityService', 'analyze_portfolio_liquidity'),
        ('metrics-data-quality', 'apps.api.views.MetadataAuditService', 'run_audit'),
        ('metrics-snapshot-integrity', 'apps.api.views.SnapshotIntegrityService', 'run_checks'),
        ('metrics-sync-audit', 'apps.api.views.IOLSyncAuditService', 'run_audit'),
    ])
    def test_metric_endpoints_sanitize_internal_errors(
        self, auth_client, staff_auth_client, url_name, patch_target, patch_method
    ):
        client = staff_auth_client if url_name in STAFF_ONLY_GET_ENDPOINTS else auth_client
        with patch(f'{patch_target}.{patch_method}', side_effect=Exception('forced error')):
            response = client.get(reverse(url_name))
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'

    @patch('apps.api.views.PortfolioSnapshot.objects')
    def test_historical_summary_sanitizes_internal_errors(self, mock_objects, auth_client):
        mock_objects.order_by.side_effect = Exception('forced error')
        response = auth_client.get(reverse('historical-summary'))
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'

    @patch('apps.api.views.PortfolioSnapshot.objects')
    def test_historical_evolution_sanitizes_internal_errors(self, mock_objects, auth_client):
        mock_objects.filter.side_effect = Exception('forced error')
        response = auth_client.get(reverse('historical-evolution'))
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'

@pytest.mark.django_db
class TestAPIInputValidation:
    """Verifica que los endpoints validan correctamente los parámetros de entrada."""

    def test_metrics_returns_invalid_days(self, auth_client):
        url = reverse('metrics-returns') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_volatility_invalid_days(self, auth_client):
        url = reverse('metrics-volatility') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_performance_invalid_days(self, auth_client):
        url = reverse('metrics-performance') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_historical_comparison_invalid_periods(self, auth_client):
        url = reverse('metrics-historical-comparison') + '?periods=7,invalid,90'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_var_invalid_confidence(self, auth_client):
        url = reverse('metrics-var') + '?confidence=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_macro_comparison_invalid_days(self, auth_client):
        url = reverse('metrics-macro-comparison') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_benchmark_curve_invalid_days(self, auth_client):
        url = reverse('metrics-benchmark-curve') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_cvar_invalid_confidence(self, auth_client):
        url = reverse('metrics-cvar') + '?confidence=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_attribution_invalid_days(self, auth_client):
        url = reverse('metrics-attribution') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_benchmarking_invalid_days(self, auth_client):
        url = reverse('metrics-benchmarking') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_snapshot_integrity_invalid_days(self, staff_auth_client):
        url = reverse('metrics-snapshot-integrity') + '?days=invalid'
        response = staff_auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_sync_audit_invalid_hours(self, staff_auth_client):
        url = reverse('metrics-sync-audit') + '?hours=invalid'
        response = staff_auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_historical_evolution_invalid_days(self, auth_client):
        response = auth_client.get(reverse('historical-evolution') + '?days=invalid')
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_returns_includes_basis_metadata(self, auth_client):
        url = reverse('metrics-returns')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'fields_basis' in body['metadata']
            assert body['metadata']['primary_family'] == 'temporal_return_on_total_portfolio'
            assert 'performance_families' in body['metadata']
            assert 'portfolio_return_ytd_real' in body['metadata']['fields_basis']
            assert 'max_drawdown_real' in body['metadata']['fields_basis']
            assert 'badlar_ytd' in body['metadata']['fields_basis']
            assert 'portfolio_excess_ytd_vs_badlar' in body['metadata']['fields_basis']
            assert 'history_guardrails' in body['metadata']
            assert body['metadata']['history_guardrails']['warning_code_for_partial_history'] == 'partial_history'

    @patch('apps.api.views.IOLFCICatalogService.list_latest_catalog')
    def test_catalog_fci_exposes_filtered_catalog(self, mock_list_latest_catalog, auth_client):
        mock_list_latest_catalog.return_value = {
            'captured_date': '2026-03-26',
            'count': 1,
            'items': [
                {
                    'simbolo': 'IOLCAMA',
                    'descripcion': 'IOL Cash Management',
                    'tipo_fondo': 'renta_fija_pesos',
                    'moneda': 'peso_Argentino',
                    'rescate': 't1',
                    'perfil_inversor': 'Conservador',
                    'administradora': 'convexity',
                    'metadata': {},
                }
            ],
        }

        response = auth_client.get(
            reverse('catalog-fci') + '?tipo_fondo=renta_fija_pesos&moneda=peso_Argentino'
        )

        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 1
        assert body['items'][0]['simbolo'] == 'IOLCAMA'
        assert 'metadata' in body
        assert 'available_filters' in body['metadata']

    @patch('apps.api.views.TemporalMetricsService.get_portfolio_returns')
    def test_metrics_returns_exposes_partial_history_guardrails(self, mock_get_returns, auth_client):
        mock_get_returns.return_value = {
            'total_period_return': -0.29,
            'observations': 2,
            'history_span_days': 1,
            'requested_days': 30,
            'robust_history_min_days': 60,
            'robust_history_available': False,
            'partial_window': True,
            'warning': 'partial_history',
            'warning_message': 'Historia parcial: 1 dias reales sobre 30 solicitados.',
            'history_health': {
                'status': 'partial',
                'message': 'Historia parcial: 1 dias reales sobre 30 solicitados.',
                'observations': 2,
                'history_span_days': 1,
                'requested_days': 30,
                'robust_history_min_days': 60,
                'partial_window': True,
                'minimum_observations': 2,
            },
        }

        response = auth_client.get(reverse('metrics-returns') + '?days=30')

        assert response.status_code == 200
        body = response.json()
        assert body['warning'] == 'partial_history'
        assert body['history_health']['status'] == 'partial'
        assert body['history_health']['partial_window'] is True
        assert body['metadata']['history_guardrails']['robust_history_min_days'] == 60

    def test_dashboard_kpis_includes_performance_family_metadata(self, auth_client):
        url = reverse('dashboard-kpis')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert body['metadata']['primary_family'] == 'accumulated_on_invested_cost'
            assert body['metadata']['comparison_family'] == 'temporal_return_on_total_portfolio'
            assert 'performance_families' in body['metadata']
            assert 'rendimiento_total_dinero' in body['metadata']['fields_basis']

    def test_metrics_volatility_includes_basis_metadata(self, auth_client):
        url = reverse('metrics-volatility')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'fields_basis' in body['metadata']
            assert 'sharpe_ratio_badlar' in body['metadata']['fields_basis']

    def test_metrics_attribution_includes_metadata(self, auth_client):
        url = reverse('metrics-attribution')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']

    def test_metrics_macro_comparison_includes_metadata(self, auth_client):
        url = reverse('metrics-macro-comparison')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']

    def test_metrics_benchmark_curve_includes_metadata(self, auth_client):
        url = reverse('metrics-benchmark-curve')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']
            assert 'benchmark_trace' in body

    def test_metrics_benchmarking_includes_metadata(self, auth_client):
        url = reverse('metrics-benchmarking')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']
            assert 'benchmark_trace' in body

    @patch('apps.api.views.TrackingErrorService')
    def test_metrics_benchmarking_sanitizes_non_finite_numbers(self, MockService, auth_client):
        MockService.return_value.calculate.return_value = {
            'tracking_error_annualized': float('nan'),
            'information_ratio': float('inf'),
        }

        response = auth_client.get(reverse('metrics-benchmarking'))

        assert response.status_code == 200
        body = response.json()
        assert body['tracking_error_annualized'] is None
        assert body['information_ratio'] is None

    def test_metrics_liquidity_includes_metadata(self, auth_client):
        url = reverse('metrics-liquidity')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']

    def test_metrics_data_quality_includes_metadata(self, auth_client):
        url = reverse('metrics-data-quality')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']

    @pytest.mark.parametrize('url_name', [
        'metrics-var',
        'metrics-cvar',
        'metrics-attribution',
        'metrics-macro-comparison',
        'metrics-benchmark-curve',
        'metrics-benchmarking',
        'metrics-liquidity',
        'metrics-data-quality',
    ])
    def test_metric_endpoints_include_methodology_basis_and_limitations(self, auth_client, url_name):
        response = auth_client.get(reverse(url_name))
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            metadata = response.json().get('metadata', {})
            assert 'methodology' in metadata
            assert 'data_basis' in metadata
            assert 'limitations' in metadata

    @pytest.mark.parametrize('url_name', [
        'metrics-snapshot-integrity',
        'metrics-sync-audit',
        'metrics-internal-observability',
    ])
    def test_staff_metric_endpoints_include_methodology_basis_and_limitations(
        self, staff_auth_client, url_name
    ):
        response = staff_auth_client.get(reverse(url_name))
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            metadata = response.json().get('metadata', {})
            assert 'methodology' in metadata
            assert 'data_basis' in metadata
            assert 'limitations' in metadata

@pytest.mark.django_db
class TestAPIPostEndpointsHappyPath:
    """Cubre path feliz de POST endpoints con mocks."""

    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    @patch('apps.api.views.PortfolioSnapshot.objects')
    def test_historical_summary_with_snapshot(self, mock_objects, mock_kpis, auth_client):
        from unittest.mock import MagicMock
        mock_snapshot = MagicMock()
        mock_snapshot.fecha = '2025-01-01'
        mock_snapshot.total_iol = 10000
        mock_snapshot.portafolio_invertido = 7000
        mock_snapshot.rendimiento_total = 5.0
        mock_snapshot.liquidez_operativa = 1000
        mock_snapshot.cash_management = 800
        mock_snapshot.total_patrimonio_modelado = 10000
        mock_snapshot.cash_disponible_broker = 1000
        mock_snapshot.caucion_colocada = 1200
        mock_objects.order_by.return_value.first.return_value = mock_snapshot
        mock_objects.filter.return_value.count.return_value = 10
        mock_objects.filter.return_value.aggregate.return_value = {'avg': 3.5}

        url = reverse('historical-summary')
        response = auth_client.get(url)
        assert response.status_code == 200
        latest = response.json()['latest_snapshot']
        assert latest['liquidity_contract_status'] == 'explicit_layers'
        assert latest['liquidez_desplegable_total'] == 3000
        assert latest['liquidez_estrategica'] == 800

    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_simulation_purchase_missing_params(self, mock_kpis, auth_client):
        url = reverse('simulation-purchase')
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 400

    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_simulation_sale_missing_params(self, mock_kpis, auth_client):
        url = reverse('simulation-sale')
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 400

    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_simulation_rebalance_success(self, mock_kpis, auth_client):
        from unittest.mock import patch as p
        with p('apps.core.services.portfolio_simulator.PortfolioSimulator.simulate_rebalance',
               return_value={'resultado': 'ok'}):
            url = reverse('simulation-rebalance')
            response = auth_client.post(url, {'target_weights': {'AAPL': 50}}, format='json')
            assert response.status_code == 200
            assert response.json() == {'resultado': 'ok'}

    @pytest.mark.parametrize('url_name,payload,error_message', [
        ('simulation-rebalance', {}, 'Se requieren pesos objetivo'),
        ('optimizer-risk-parity', {}, 'Se requieren activos'),
        ('optimizer-markowitz', {'activos': ['SPY']}, 'Se requieren activos y retorno objetivo'),
        ('optimizer-target-allocation', {}, 'Se requieren asignaciones objetivo'),
        ('monthly-plan-basic', {}, 'Se requiere monto mensual'),
        ('monthly-plan-custom', {}, 'Se requiere monto mensual'),
    ])
    def test_post_endpoints_validate_required_payload(self, auth_client, url_name, payload, error_message):
        response = auth_client.post(reverse(url_name), payload, format='json')
        assert response.status_code == 400
        assert response.json()['error'] == error_message

    @pytest.mark.parametrize('url_name,patch_target,method_name,payload,expected_body', [
        (
            'simulation-purchase',
            'apps.core.services.portfolio_simulator.PortfolioSimulator',
            'simulate_purchase',
            {'activo': 'SPY', 'capital': 1000},
            {'ok': 'purchase'},
        ),
        (
            'simulation-sale',
            'apps.core.services.portfolio_simulator.PortfolioSimulator',
            'simulate_sale',
            {'activo': 'SPY', 'cantidad': 2},
            {'ok': 'sale'},
        ),
        (
            'optimizer-risk-parity',
            'apps.core.services.portfolio_optimizer.PortfolioOptimizer',
            'optimize_risk_parity',
            {'activos': ['SPY', 'EEM'], 'target_return': 0.1},
            {'ok': 'risk_parity'},
        ),
        (
            'optimizer-markowitz',
            'apps.core.services.portfolio_optimizer.PortfolioOptimizer',
            'optimize_markowitz',
            {'activos': ['SPY', 'EEM'], 'target_return': 0.1},
            {'ok': 'markowitz'},
        ),
        (
            'optimizer-target-allocation',
            'apps.core.services.portfolio_optimizer.PortfolioOptimizer',
            'optimize_target_allocation',
            {'target_allocations': {'SPY': 60, 'EEM': 40}},
            {'ok': 'target_allocation'},
        ),
        (
            'monthly-plan-basic',
            'apps.core.services.monthly_investment_planner.MonthlyInvestmentPlanner',
            'plan_monthly_investment',
            {'monthly_amount': 100000},
            {'ok': 'basic_plan'},
        ),
        (
            'monthly-plan-custom',
            'apps.core.services.monthly_investment_planner.MonthlyInvestmentPlanner',
            'create_custom_plan',
            {'monthly_amount': 100000, 'risk_profile': 'moderado', 'investment_horizon': 'medio'},
            {'ok': 'custom_plan'},
        ),
    ])
    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_post_endpoints_return_service_payload(
        self, mock_kpis, auth_client, url_name, patch_target, method_name, payload, expected_body
    ):
        with patch.object(__import__(patch_target.rsplit('.', 1)[0], fromlist=[patch_target.rsplit('.', 1)[1]]).__dict__[patch_target.rsplit('.', 1)[1]], method_name, return_value=expected_body):
            response = auth_client.post(reverse(url_name), payload, format='json')
        assert response.status_code == 200
        assert response.json() == expected_body

    @pytest.mark.parametrize('url_name,patch_target,method_name,payload', [
        ('simulation-purchase', 'apps.core.services.portfolio_simulator.PortfolioSimulator', 'simulate_purchase', {'activo': 'SPY', 'capital': 1000}),
        ('simulation-sale', 'apps.core.services.portfolio_simulator.PortfolioSimulator', 'simulate_sale', {'activo': 'SPY', 'cantidad': 2}),
        ('simulation-rebalance', 'apps.core.services.portfolio_simulator.PortfolioSimulator', 'simulate_rebalance', {'target_weights': {'SPY': 100}}),
        ('optimizer-risk-parity', 'apps.core.services.portfolio_optimizer.PortfolioOptimizer', 'optimize_risk_parity', {'activos': ['SPY']}),
        ('optimizer-markowitz', 'apps.core.services.portfolio_optimizer.PortfolioOptimizer', 'optimize_markowitz', {'activos': ['SPY'], 'target_return': 0.1}),
        ('optimizer-target-allocation', 'apps.core.services.portfolio_optimizer.PortfolioOptimizer', 'optimize_target_allocation', {'target_allocations': {'SPY': 100}}),
        ('monthly-plan-basic', 'apps.core.services.monthly_investment_planner.MonthlyInvestmentPlanner', 'plan_monthly_investment', {'monthly_amount': 100000}),
        ('monthly-plan-custom', 'apps.core.services.monthly_investment_planner.MonthlyInvestmentPlanner', 'create_custom_plan', {'monthly_amount': 100000}),
    ])
    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_post_endpoints_sanitize_internal_errors(
        self, mock_kpis, auth_client, url_name, patch_target, method_name, payload
    ):
        with patch.object(__import__(patch_target.rsplit('.', 1)[0], fromlist=[patch_target.rsplit('.', 1)[1]]).__dict__[patch_target.rsplit('.', 1)[1]], method_name, side_effect=Exception('forced error')):
            response = auth_client.post(reverse(url_name), payload, format='json')
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'

    @pytest.mark.parametrize(
        'url_name,payload,expected_error',
        [
            ('simulation-purchase', {'activo': 'SPY', 'capital': 0}, 'capital debe ser mayor a 0'),
            ('simulation-sale', {'activo': 'SPY', 'cantidad': 0}, 'cantidad debe ser mayor a 0'),
            (
                'simulation-rebalance',
                {'target_weights': {f'S{i}': 1 for i in range(51)}},
                'pesos objetivo excede el máximo permitido',
            ),
            (
                'optimizer-risk-parity',
                {'activos': [f'S{i}' for i in range(51)]},
                'activos excede el máximo permitido',
            ),
            (
                'optimizer-markowitz',
                {'activos': ['SPY', 'EEM'], 'target_return': 50},
                'target_return fuera de rango permitido',
            ),
            (
                'optimizer-target-allocation',
                {'target_allocations': {'SPY': 101}},
                'asignaciones objetivo:SPY excede el máximo permitido',
            ),
        ],
    )
    def test_post_endpoints_reject_excessive_or_invalid_payloads(
        self, auth_client, url_name, payload, expected_error
    ):
        response = auth_client.post(reverse(url_name), payload, format='json')
        assert response.status_code == 400
        assert response.json()['error'] == expected_error

    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_simulation_purchase_normalizes_symbol_before_service_call(self, mock_kpis, auth_client):
        with patch('apps.core.services.portfolio_simulator.PortfolioSimulator.simulate_purchase', return_value={'ok': True}) as mock_service:
            response = auth_client.post(
                reverse('simulation-purchase'),
                {'activo': ' spy ', 'capital': 1000},
                format='json',
            )
        assert response.status_code == 200
        assert mock_service.call_args[0][0] == 'SPY'

    @patch('apps.api.views.get_dashboard_kpis', return_value={'total_iol': 10000})
    def test_optimizer_risk_parity_rejects_non_list_activos(self, mock_kpis, auth_client):
        response = auth_client.post(
            reverse('optimizer-risk-parity'),
            {'activos': 'SPY'},
            format='json',
        )
        assert response.status_code == 400
        assert response.json()['error'] == 'activos debe ser una lista'

    def test_portfolio_parameters_update_forbidden_non_staff(self, auth_client):
        url = reverse('portfolio-parameters-update')
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 403
        audit = SensitiveActionAudit.objects.get(action='portfolio_parameters_update')
        assert audit.status == 'denied'
        assert audit.user.username == 'testuser'

    def test_portfolio_parameters_update_missing_params(self, staff_auth_client):
        url = reverse('portfolio-parameters-update')
        response = staff_auth_client.post(url, {}, format='json')
        assert response.status_code in [200, 400, 500]

    def test_portfolio_parameters_update_invalid_allocation(self, staff_auth_client):
        """Verifica que no se permita guardar asignaciones que no sumen 100%."""
        url = reverse('portfolio-parameters-update')
        # Asignación que suma más de 100%
        invalid_data = {
            'liquidez_target': 30,
            'usa_target': 40,
            'argentina_target': 40,
            'emerging_target': 20
        }
        response = staff_auth_client.post(url, invalid_data, format='json')
        assert response.status_code == 400
        assert 'error' in response.json()
        assert '100%' in response.json()['error']
        audit = SensitiveActionAudit.objects.get(action='portfolio_parameters_update')
        assert audit.status == 'failed'

    def test_portfolio_parameters_update_valid_allocation(self, staff_auth_client):
        """Verifica que se permita guardar asignaciones válidas."""
        url = reverse('portfolio-parameters-update')
        # Asignación que suma exactamente 100%
        valid_data = {
            'liquidez_target': 20,
            'usa_target': 40,
            'argentina_target': 30,
            'emerging_target': 10
        }
        response = staff_auth_client.post(url, valid_data, format='json')
        assert response.status_code == 200
        assert 'message' in response.json()
        audit = SensitiveActionAudit.objects.get(action='portfolio_parameters_update')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    def test_portfolio_parameters_update_invalid_range_returns_400(self, staff_auth_client):
        url = reverse('portfolio-parameters-update')
        response = staff_auth_client.post(
            url,
            {
                'liquidez_target': 20,
                'usa_target': 40,
                'argentina_target': 30,
                'emerging_target': 10,
                'max_single_position': 150,
            },
            format='json',
        )

        assert response.status_code == 400
        body = response.json()
        assert body['error'] == 'Debe estar entre 0 y 100.'
        assert 'max_single_position' in body['details']
        audit = SensitiveActionAudit.objects.get(action='portfolio_parameters_update')
        assert audit.status == 'failed'

@pytest.mark.django_db
class TestHistoricalEvolutionFallback:
    @patch("apps.api.views.get_evolucion_historica")
    def test_historical_evolution_uses_operational_fallback(self, mock_evolution, auth_client):
        mock_evolution.return_value = {
            "tiene_datos": True,
            "fechas": ["2026-03-11", "2026-03-12"],
            "total_iol": [1000, 1100],
            "portafolio_invertido": [700, 770],
            "liquidez_operativa": [200, 220],
            "cash_management": [100, 110],
        }

        response = auth_client.get(reverse("historical-evolution") + "?days=365")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["total_iol"] == 1000
        assert body[0]["liquidez_estrategica"] == 100
        assert body[0]["liquidez_desplegable_total"] == 300
        assert body[0]["liquidity_contract_status"] == "legacy_aggregated_fallback"
        assert "fecha" in body[0]

    @patch("apps.api.views.get_evolucion_historica", return_value={"tiene_datos": False})
    @patch("apps.api.views.PortfolioSnapshot.objects")
    def test_historical_evolution_returns_empty_when_no_fallback_data(
        self, mock_objects, mock_evolution, auth_client
    ):
        mock_values = mock_objects.filter.return_value.order_by.return_value.values.return_value
        mock_values.__iter__.return_value = iter([])
        response = auth_client.get(reverse("historical-evolution") + "?days=365")
        assert response.status_code == 200
        assert response.json() == []

    @patch("apps.api.views.PortfolioSnapshot.objects")
    def test_historical_summary_returns_empty_when_no_snapshot(self, mock_objects, auth_client):
        mock_objects.order_by.return_value.first.return_value = None
        response = auth_client.get(reverse("historical-summary"))
        assert response.status_code == 200
        assert response.json() == {}

    @patch("apps.api.views.PortfolioSnapshot.objects")
    def test_historical_evolution_returns_direct_snapshots_when_available(self, mock_objects, auth_client):
        mock_values = mock_objects.filter.return_value.order_by.return_value.values.return_value
        mock_values.__iter__.return_value = iter([
            {
                'fecha': '2026-03-12',
                'total_iol': 1000,
                'portafolio_invertido': 700,
                'rendimiento_total': 1,
                'liquidez_operativa': 120,
                'cash_management': 80,
                'total_patrimonio_modelado': 1000,
                'cash_disponible_broker': 120,
                'caucion_colocada': 100,
            },
            {
                'fecha': '2026-03-13',
                'total_iol': 1100,
                'portafolio_invertido': 750,
                'rendimiento_total': 2,
                'liquidez_operativa': 150,
                'cash_management': 90,
                'total_patrimonio_modelado': 1100,
                'cash_disponible_broker': 150,
                'caucion_colocada': 110,
            },
        ])
        response = auth_client.get(reverse("historical-evolution") + "?days=365")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[1]['total_iol'] == 1100
        assert response.json()[1]['liquidity_contract_status'] == 'explicit_layers'
        assert response.json()[1]['liquidez_desplegable_total'] == 350
        assert response.json()[1]['liquidez_estrategica'] == 90


@pytest.mark.django_db
class TestPortfolioParametersGet:
    def test_portfolio_parameters_get_returns_404_without_active_params(self, auth_client):
        response = auth_client.get(reverse('portfolio-parameters-get'))
        assert response.status_code == 404
        assert response.json()['error'] == 'No hay parámetros activos'

    def test_portfolio_parameters_get_returns_active_params(self, auth_client):
        from apps.core.models import PortfolioParameters

        params = PortfolioParameters.objects.create(
            name='Principal',
            liquidez_target=20,
            usa_target=40,
            argentina_target=30,
            emerging_target=10,
        )
        response = auth_client.get(reverse('portfolio-parameters-get'))
        assert response.status_code == 200
        body = response.json()
        assert body['id'] == params.id
        assert body['is_valid'] is True
        assert body['total_allocation'] == 100.0

    def test_portfolio_parameters_get_sanitizes_internal_errors(self, auth_client):
        with patch('apps.core.models.PortfolioParameters.get_active_parameters', side_effect=Exception('forced error')):
            response = auth_client.get(reverse('portfolio-parameters-get'))
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'


@pytest.mark.django_db
class TestRecommendationsFiltering:
    @patch('apps.core.services.recommendation_engine.RecommendationEngine.generate_recommendations')
    def test_recommendations_all_preserves_prioritized_order(self, mock_generate, auth_client):
        mock_generate.return_value = [
            {
                'tipo': 'analytics_v2_risk_concentration_argentina',
                'prioridad': 'alta',
                'origen': 'analytics_v2',
                'modelo_riesgo': 'covariance_aware',
            },
            {'tipo': 'diversificacion_sectorial', 'prioridad': 'media'},
            {'tipo': 'revision_rendimiento', 'prioridad': 'baja'},
        ]
        response = auth_client.get(reverse('recommendations-all'))
        assert response.status_code == 200
        assert response.json() == [
            {
                'tipo': 'analytics_v2_risk_concentration_argentina',
                'prioridad': 'alta',
                'origen': 'analytics_v2',
                'modelo_riesgo': 'covariance_aware',
            },
            {'tipo': 'diversificacion_sectorial', 'prioridad': 'media'},
            {'tipo': 'revision_rendimiento', 'prioridad': 'baja'},
        ]

    @patch('apps.core.services.recommendation_engine.RecommendationEngine.generate_recommendations')
    def test_recommendations_by_priority_filters_results(self, mock_generate, auth_client):
        mock_generate.return_value = [
            {'tipo': 'a', 'prioridad': 'alta'},
            {'tipo': 'b', 'prioridad': 'media'},
            {'tipo': 'c', 'prioridad': 'alta'},
        ]
        response = auth_client.get(reverse('recommendations-by-priority') + '?priority=alta')
        assert response.status_code == 200
        assert response.json() == [
            {'tipo': 'a', 'prioridad': 'alta'},
            {'tipo': 'c', 'prioridad': 'alta'},
        ]

    @patch('apps.core.services.recommendation_engine.RecommendationEngine.generate_recommendations', side_effect=Exception('forced error'))
    def test_recommendations_all_sanitizes_internal_errors(self, mock_generate, auth_client):
        response = auth_client.get(reverse('recommendations-all'))
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'

    @patch('apps.core.services.recommendation_engine.RecommendationEngine.generate_recommendations', side_effect=Exception('forced error'))
    def test_recommendations_by_priority_sanitizes_internal_errors(self, mock_generate, auth_client):
        response = auth_client.get(reverse('recommendations-by-priority') + '?priority=alta')
        assert response.status_code == 500
        assert response.json()['error'] == 'Internal server error'

    @patch('apps.api.views.get_state_summary')
    @patch('apps.api.views.get_timing_summary')
    def test_metrics_internal_observability_includes_state_metrics(
        self, mock_timing, mock_state, staff_auth_client
    ):
        mock_timing.return_value = {'metric_name': 'metrics.returns.calc_ms', 'count': 3, 'mean_ms': 10.0, 'max_ms': 12.0}
        mock_state.return_value = {
            'metric_name': 'analytics_v2.risk_contribution.model_variant',
            'count': 4,
            'states': {'mvp_proxy': 3, 'covariance_aware': 1},
            'latest_state': 'mvp_proxy',
            'latest_extra': {'observations': 5, 'coverage_pct': 100.0, 'reason': 'insufficient_covariance_history'},
        }

        response = staff_auth_client.get(reverse('metrics-internal-observability'))

        assert response.status_code == 200
        body = response.json()
        assert 'metrics' in body
        assert 'states' in body
        assert body['states'][0]['metric_name'] == 'analytics_v2.risk_contribution.model_variant'
        assert body['states'][0]['states']['mvp_proxy'] == 3

    @patch('apps.api.views.get_state_summary')
    @patch('apps.api.views.get_timing_summary')
    def test_metrics_internal_observability_includes_local_macro_sync_state(
        self, mock_timing, mock_state, staff_auth_client
    ):
        mock_timing.return_value = {'metric_name': 'metrics.returns.calc_ms', 'count': 0}
        mock_state.side_effect = [
            {
                'metric_name': 'analytics_v2.risk_contribution.model_variant',
                'count': 1,
                'states': {'mvp_proxy': 1},
                'latest_state': 'mvp_proxy',
                'latest_extra': {},
            },
            {
                'metric_name': 'analytics_v2.local_macro.sync_status',
                'count': 2,
                'states': {'success_with_skips': 2},
                'latest_state': 'success_with_skips',
                'latest_extra': {'synced_series': ['usdars_oficial'], 'skipped_series': ['usdars_mep'], 'failed_series': []},
            },
        ]

        response = staff_auth_client.get(reverse('metrics-internal-observability'))

        assert response.status_code == 200
        body = response.json()
        assert len(body['states']) == 2
        assert body['states'][1]['metric_name'] == 'analytics_v2.local_macro.sync_status'
        assert body['states'][1]['latest_state'] == 'success_with_skips'
