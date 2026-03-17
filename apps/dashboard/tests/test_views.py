import pytest
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.core.models import SensitiveActionAudit


@pytest.mark.django_db
class TestDashboardView:

    def setup_method(self):
        cache.clear()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='testpass123')

    @pytest.fixture
    def auth_client(self, user):
        client = Client(raise_request_exception=False)
        client.force_login(user)
        return client

    @pytest.fixture
    def staff_user(self):
        return User.objects.create_user(username='staffuser', password='testpass123', is_staff=True)

    @pytest.fixture
    def staff_client(self, staff_user):
        client = Client(raise_request_exception=False)
        client.force_login(staff_user)
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

    def test_resumen_shows_macro_exposure_and_liquidity_labels(self, auth_client):
        response = auth_client.get(reverse('dashboard:resumen'))
        body = response.content.decode()
        assert 'Exposición USA' in body
        assert 'Exposición Argentina' in body
        assert 'Capital invertido' in body
        assert 'Liquidez total' in body
        assert 'USD oficial mayorista BCRA' in body

    def test_analisis_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:analisis')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_analisis_shows_base_labels_and_aggregated_sector_view(self, auth_client):
        response = auth_client.get(reverse('dashboard:analisis'))
        body = response.content.decode()
        assert 'Análisis de composición y riesgo' in body
        assert 'Vista detallada para entender concentración, exposición y lectura de riesgo.' in body
        assert 'Base: Portafolio Invertido' in body
        assert 'Base: Total IOL' in body
        assert 'Vista agregada opcional de sectores' in body

    def test_estrategia_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:estrategia')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_estrategia_uses_updated_liquidity_and_fixed_income_labels(self, auth_client):
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert 'Bases de Cálculo' in body
        assert 'Navegación rápida' in body
        assert 'Lectura del portafolio' in body
        assert 'Vista analítica' in body
        assert 'Fondos de liquidez / cash management' in body
        assert '% Renta fija AR' in body
        assert 'Analytics v2' in body
        assert 'Resumen Analytics v2' in body
        assert 'Señales Analytics v2' in body
        assert 'Macro Local' in body
        assert 'Carry real BADLAR' in body
        assert 'Brecha FX' in body
        assert 'Riesgo país' in body
        assert 'Peso soberano local' in body
        assert 'Nombres soberanos' in body
        assert 'Top soberano local' in body
        assert 'Concentración bloque soberano' in body
        assert 'Split hard dollar / CER' in body
        assert 'Ver detalle' in body
        assert 'Último snapshot' in body
        assert 'Gap máximo' in body
        assert 'Posiciones completas' in body
        assert 'Proxy MVP' in body or 'Covarianza activa' in body
        assert (
            'El riesgo del portafolio está dominado' in body
            or 'No hay datos suficientes para interpretar la contribución al riesgo del portafolio.' in body
        )
        assert (
            'El escenario más adverso corresponde a' in body
            or 'No hay datos suficientes para interpretar el scenario analysis actual.' in body
        )
        assert (
            'La exposición del portafolio está dominada por el factor' in body
            or 'No hay datos suficientes para interpretar la exposición factorial del portafolio.' in body
        )
        assert (
            'La cartera muestra una fragilidad de' in body
            or 'No hay datos suficientes para interpretar la fragilidad bajo stress del portafolio.' in body
        )
        assert (
            'El retorno esperado estructural del portafolio se ubica en' in body
            or 'No hay datos suficientes para interpretar el retorno esperado estructural.' in body
        )
        assert 'Snapshots:' in body
        assert 'Operaciones:' in body
        assert "const syncReasonText = syncReasons.length" in body

    def test_risk_contribution_detail_route_accessible_authenticated(self, auth_client):
        response = auth_client.get(reverse('dashboard:risk_contribution_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Risk Contribution' in body
        assert 'Detalle por activo' in body
        assert 'Modelo activo' in body
        assert 'Volatilidad proxy' in body
        assert 'Contribucion' in body
        assert 'Delta agregado por sector' in body
        assert 'Delta agregado por pais' in body

    def test_risk_contribution_detail_uses_unlocalized_width_for_progress_bar(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_risk_contribution_detail',
            lambda: {
                'items': [
                    {
                        'rank': 1,
                        'symbol': 'SPY',
                        'sector': 'Indice',
                        'weight_pct': 9.17,
                        'volatility_proxy': 84.74,
                        'risk_score': 0.07773,
                        'contribution_pct': 22.33,
                        'risk_vs_weight_delta': 13.16,
                        'used_volatility_fallback': False,
                    }
                ],
                'by_sector': [],
                'by_country': [],
                'top_asset': {'symbol': 'SPY'},
                'top_sector': {'key': 'Indice'},
                'model_variant': 'mvp_proxy',
                'covariance_observations': 6,
                'coverage_pct': 100.0,
                'portfolio_volatility_proxy': None,
                'confidence': 'high',
                'warnings': [],
                'methodology': 'mvp',
                'limitations': 'mvp',
                'covered_symbols': ['SPY'],
                'excluded_symbols': [],
            },
        )
        response = auth_client.get(reverse('dashboard:risk_contribution_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'style="width: 22.33%"' in body

    def test_estrategia_uses_patrimonial_sync_status_for_main_badge(self, auth_client, monkeypatch):
        class DummySyncAuditService:
            def run_audit(self, freshness_hours=24):
                assert freshness_hours == 24
                return {
                    'status': 'warning',
                    'patrimonial_status': 'ok',
                    'issues_count': 1,
                    'issues': ['operations'],
                    'token': {'status': 'ok'},
                    'snapshots': {'status': 'ok', 'reasons': []},
                    'operations': {'status': 'warning', 'reason': 'stale_operations'},
                }

        monkeypatch.setattr('apps.dashboard.views.IOLSyncAuditService', lambda: DummySyncAuditService())
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'bg-success' in body

    def test_planeacion_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:planeacion')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_planeacion_explains_total_liquidity_definition(self, auth_client):
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Liquidez total = liquidez operativa + cash management' in body
        assert 'Modelo de riesgo:' in body

    def test_performance_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:performance')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_metricas_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:metricas')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_ops_requires_staff(self, auth_client, staff_client):
        url = reverse('dashboard:ops')
        denied = auth_client.get(url)
        assert denied.status_code == 403
        allowed = staff_client.get(url)
        assert allowed.status_code == 200
        assert 'Estado de benchmarks históricos' in allowed.content.decode()
        assert 'Estado de macro local' in allowed.content.decode()
        assert 'Sincronizar Macro Local' in allowed.content.decode()
        assert 'Activación modelo de riesgo' in allowed.content.decode()
        assert 'Continuidad diaria de snapshots' in allowed.content.decode()
        assert 'Observabilidad interna' in allowed.content.decode()

    def test_ops_shows_snapshot_continuity_status(self, staff_client, monkeypatch):
        class DummyContinuityService:
            def build_report(self, lookback_days=14):
                assert lookback_days == 14
                return {
                    'overall_status': 'warning',
                    'rows': [
                        {
                            'date': '2026-03-14',
                            'raw_snapshots_present': True,
                            'raw_assets_count': 33,
                            'account_snapshot_present': True,
                            'account_rows_count': 2,
                            'portfolio_snapshot_present': False,
                            'usable_for_covariance': False,
                            'status': 'warning',
                        }
                    ],
                }

        monkeypatch.setattr('apps.dashboard.views.DailySnapshotContinuityService', lambda: DummyContinuityService())
        response = staff_client.get(reverse('dashboard:ops'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Continuidad diaria de snapshots' in body
        assert '2026-03-14' in body
        assert 'warning' in body

    def test_preferences_persisted_in_session(self, auth_client):
        url = reverse('dashboard:set_preferences')
        response = auth_client.post(url, {'ui_mode': 'denso', 'risk_profile': 'agresivo', 'next': '/'})
        assert response.status_code == 302
        assert auth_client.session['ui_mode'] == 'denso'
        assert auth_client.session['risk_profile'] == 'agresivo'

    def test_preferences_rejects_external_next_url(self, auth_client):
        url = reverse('dashboard:set_preferences')
        response = auth_client.post(
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
    def test_run_sync_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:run_sync'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_generate_snapshot_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:generate_snapshot'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_run_sync_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            def sync_all(self):
                return {
                    'estado_cuenta': True,
                    'portafolio_argentina': True,
                    'operaciones': True,
                    'portfolio_snapshot': True,
                }

        monkeypatch.setattr('apps.dashboard.views.IOLSyncService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:run_sync'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Sincronizacion completada' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='manual_sync')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_generate_snapshot_view_success_message(self, staff_client, monkeypatch):
        class DummySnapshot:
            fecha = '2026-03-12'
            _refresh_action = 'refreshed'

        class DummyService:
            def generate_daily_snapshot(self):
                return DummySnapshot()

        monkeypatch.setattr('apps.dashboard.views.PortfolioSnapshotService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:generate_snapshot'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Snapshot actualizado' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='generate_snapshot')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_sync_benchmarks_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:sync_benchmarks'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_sync_local_macro_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:sync_local_macro'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_sync_benchmarks_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            def sync_all(self, outputsize='compact'):
                assert outputsize == 'compact'
                return {
                    'cedear_usa': {'rows_received': 100},
                    'bonos_ar': {'rows_received': 100},
                    'liquidez': {'rows_received': 100},
                }

        monkeypatch.setattr('apps.dashboard.views.BenchmarkSeriesService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_benchmarks'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Benchmarks sincronizados' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='sync_benchmarks')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_sync_local_macro_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            SYNC_STATE_METRIC = 'analytics_v2.local_macro.sync_status'

            def sync_all(self):
                return {
                    'usdars_oficial': {'rows_received': 1, 'success': True},
                    'usdars_mep': {'rows_received': 0, 'success': True, 'skipped': True},
                    'badlar_privada': {'rows_received': 1, 'success': True},
                    'ipc_nacional': {'rows_received': 1, 'success': True},
                }

            @classmethod
            def summarize_sync_result(cls, result):
                return {
                    'metric_name': cls.SYNC_STATE_METRIC,
                    'state': 'success_with_skips',
                    'extra': {
                        'synced_series': ['usdars_oficial', 'badlar_privada', 'ipc_nacional'],
                        'skipped_series': ['usdars_mep'],
                        'failed_series': [],
                    },
                }

        monkeypatch.setattr('apps.dashboard.views.LocalMacroSeriesService', DummyService)
        response = staff_client.post(reverse('dashboard:sync_local_macro'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Macro local sincronizada' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='sync_local_macro')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'
        from apps.core.services.observability import get_state_summary
        summary = get_state_summary('analytics_v2.local_macro.sync_status')
        assert summary['latest_state'] == 'success_with_skips'







