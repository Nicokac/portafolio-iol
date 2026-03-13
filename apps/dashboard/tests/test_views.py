import pytest
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestDashboardView:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='testpass123')

    @pytest.fixture
    def auth_client(self, user):
        client = Client(raise_request_exception=False)
        client.force_login(user)
        return client

    def test_dashboard_redirects_anonymous(self, client):
        url = reverse('dashboard:dashboard')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']

    def test_dashboard_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:dashboard')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_resumen_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:resumen')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_analisis_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:analisis')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_estrategia_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:estrategia')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_performance_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:performance')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_metricas_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:metricas')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_ops_requires_expert_profile_or_staff(self, auth_client):
        url = reverse('dashboard:ops')
        denied = auth_client.get(url)
        assert denied.status_code == 403
        auth_client.get(reverse('dashboard:set_preferences'), {'ui_mode': 'denso', 'next': '/'})
        allowed = auth_client.get(url)
        assert allowed.status_code == 200

    def test_preferences_persisted_in_session(self, auth_client):
        url = reverse('dashboard:set_preferences')
        response = auth_client.get(url, {'ui_mode': 'denso', 'risk_profile': 'agresivo', 'next': '/'})
        assert response.status_code == 302
        assert auth_client.session['ui_mode'] == 'denso'
        assert auth_client.session['risk_profile'] == 'agresivo'

    def test_preferences_rejects_external_next_url(self, auth_client):
        url = reverse('dashboard:set_preferences')
        response = auth_client.get(
            url,
            {'ui_mode': 'compacto', 'risk_profile': 'moderado', 'next': 'https://evil.example/phishing'}
        )
        assert response.status_code == 302
        assert response['Location'] == '/'

    def test_dashboard_view_class_is_protected(self):
        from apps.dashboard.views import DashboardView
        from django.contrib.auth.mixins import LoginRequiredMixin
        assert issubclass(DashboardView, LoginRequiredMixin)

    def test_run_sync_requires_authentication(self, client):
        response = client.post(reverse('dashboard:run_sync'))
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']

    def test_generate_snapshot_requires_authentication(self, client):
        response = client.post(reverse('dashboard:generate_snapshot'))
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']

    @pytest.mark.django_db
    @pytest.mark.usefixtures("auth_client")
    def test_run_sync_view_success_message(self, auth_client, monkeypatch):
        class DummyService:
            def sync_all(self):
                return {
                    'estado_cuenta': True,
                    'portafolio_argentina': True,
                    'operaciones': True,
                    'portfolio_snapshot': True,
                }

        monkeypatch.setattr('apps.dashboard.views.IOLSyncService', lambda: DummyService())
        response = auth_client.post(reverse('dashboard:run_sync'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Sincronizacion completada' in str(message) for message in messages)

    @pytest.mark.django_db
    @pytest.mark.usefixtures("auth_client")
    def test_generate_snapshot_view_success_message(self, auth_client, monkeypatch):
        class DummySnapshot:
            fecha = '2026-03-12'

        class DummyService:
            def generate_daily_snapshot(self):
                return DummySnapshot()

        monkeypatch.setattr('apps.dashboard.views.PortfolioSnapshotService', lambda: DummyService())
        response = auth_client.post(reverse('dashboard:generate_snapshot'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Snapshot disponible' in str(message) for message in messages)
