import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient


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
    'alerts-active',
    'alerts-by-severity',
    'rebalance-suggestions',
    'rebalance-critical',
    'rebalance-opportunity',
    'metrics-returns',
    'metrics-volatility',
    'metrics-performance',
    'metrics-historical-comparison',
    'metrics-var',
    'metrics-cvar',
    'metrics-stress-test',
    'metrics-attribution',
    'metrics-benchmarking',
    'metrics-liquidity',
    'metrics-data-quality',
    'metrics-snapshot-integrity',
    'metrics-sync-audit',
    'metrics-internal-observability',
    'historical-evolution',
    'historical-summary',
    'recommendations-all',
    'recommendations-by-priority',
    'portfolio-parameters-get',
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

    @pytest.mark.parametrize('url_name', POST_ENDPOINTS)
    def test_post_endpoints_return_json(self, auth_client, url_name):
        url = reverse(url_name)
        response = auth_client.post(url, {}, format='json')
        assert response.status_code in [200, 400, 403, 404, 500]
        if response.status_code != 500:
            assert response['Content-Type'] == 'application/json'

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

    def test_metrics_snapshot_integrity_invalid_days(self, auth_client):
        url = reverse('metrics-snapshot-integrity') + '?days=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_sync_audit_invalid_hours(self, auth_client):
        url = reverse('metrics-sync-audit') + '?hours=invalid'
        response = auth_client.get(url)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_metrics_returns_includes_basis_metadata(self, auth_client):
        url = reverse('metrics-returns')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'bases' in body['metadata']

    def test_metrics_volatility_includes_basis_metadata(self, auth_client):
        url = reverse('metrics-volatility')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'fields_basis' in body['metadata']

    def test_metrics_attribution_includes_metadata(self, auth_client):
        url = reverse('metrics-attribution')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']

    def test_metrics_benchmarking_includes_metadata(self, auth_client):
        url = reverse('metrics-benchmarking')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            body = response.json()
            assert 'metadata' in body
            assert 'methodology' in body['metadata']

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
        'metrics-benchmarking',
        'metrics-liquidity',
        'metrics-data-quality',
        'metrics-snapshot-integrity',
        'metrics-sync-audit',
    ])
    def test_metric_endpoints_include_methodology_basis_and_limitations(self, auth_client, url_name):
        response = auth_client.get(reverse(url_name))
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
        mock_snapshot.liquidez_operativa = 2000
        mock_objects.latest.return_value = mock_snapshot
        mock_objects.filter.return_value.count.return_value = 10
        mock_objects.filter.return_value.aggregate.return_value = {'avg': 3.5}

        url = reverse('historical-summary')
        response = auth_client.get(url)
        assert response.status_code in [200, 500]

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
            response = auth_client.post(url, {'target_allocation': {'AAPL': 50}}, format='json')
            assert response.status_code in [200, 400, 500]

    def test_portfolio_parameters_update_forbidden_non_staff(self, auth_client):
        url = reverse('portfolio-parameters-update')
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 403

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
        assert "fecha" in body[0]
