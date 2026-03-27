import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestDashboardUxSimplicityViews:
    @pytest.fixture
    def auth_client(self):
        user = User.objects.create_user(username='ux-simple-user', password='testpass123')
        client = Client(raise_request_exception=False)
        client.force_login(user)
        return client

    def test_cartera_detalle_route_accessible_authenticated(self, auth_client):
        response = auth_client.get(reverse('dashboard:cartera_detalle'))
        assert response.status_code == 200

    def test_estrategia_keeps_executive_reading_without_full_inventory(self, auth_client):
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()

        assert 'Como leer esta hoja:' in body
        assert 'Lectura del portafolio' in body
        assert 'Resumen ejecutivo' in body
        assert 'Cartera detallada y capa operativa' in body
        assert 'Abrir cartera detallada' in body
        assert 'Analytics v2' in body
        assert 'Abrir riesgo avanzado' in body
        assert 'Activo que mas explica el riesgo' in body
        assert 'Escenario mas adverso' in body
        assert 'Factor dominante' in body
        assert 'Fragilidad ante stress' in body
        assert 'Retorno estructural' in body
        assert 'Macro local' in body
        assert 'Estado FX' in body
        assert 'UVA anualizada 30d' in body
        assert 'Senales de Rebalanceo' in body
        assert 'Evolucion Historica' in body
        assert 'Posiciones completas' not in body
        assert 'Portafolio Invertido Completo' not in body
        assert 'FCI / Cash Management' not in body
        assert 'Capa operativa puntual' not in body
        assert 'Ver detalle' not in body

    def test_cartera_detalle_renders_market_snapshot_panel(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_market_snapshot_feature_context',
            lambda: {
                'has_cached_snapshot': True,
                'refreshed_at_label': '2026-03-21 10:00',
                'summary': {
                    'available_count': 3,
                    'total_symbols': 4,
                    'order_book_count': 2,
                    'fallback_count': 0,
                },
                'top_missing_count': 0,
                'alerts': [],
                'top_rows': [
                    {
                        'simbolo': 'GGAL',
                        'descripcion': 'Grupo Financiero Galicia',
                        'peso_porcentual': 8.1,
                        'variacion': 1.2,
                        'spread_pct': 0.25,
                        'cantidad_operaciones': 321,
                        'snapshot_status_label': 'Disponible',
                        'snapshot_source_label': 'CotizacionDetalle',
                    }
                ],
            },
        )
        response = auth_client.get(reverse('dashboard:cartera_detalle'))
        body = response.content.decode()

        assert 'Capa operativa puntual' in body
        assert 'CotizacionDetalle como lectura tactica' in body
        assert 'GGAL' in body
        assert 'Fallbacks' in body
        assert '<th class="text-end">Spread</th>' in body

    def test_cartera_detalle_contains_inventory_sections(self, auth_client):
        response = auth_client.get(reverse('dashboard:cartera_detalle'))
        body = response.content.decode()

        assert 'Liquidez Operativa' in body
        assert 'FCI y Cash Management' in body
        assert 'Top 5 Posiciones' in body
        assert 'Portafolio Invertido Completo' in body
        assert 'Ultimo Precio' in body

    def test_riesgo_avanzado_groups_advanced_analytics(self, auth_client):
        response = auth_client.get(reverse('dashboard:riesgo_avanzado'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'Riesgo avanzado' in body
        assert 'Analitica avanzada en un solo lugar' in body
        assert 'Activo que mas explica el riesgo' in body
        assert 'Escenario mas adverso' in body
        assert 'Factor dominante' in body
        assert 'Fragilidad ante stress' in body
        assert 'Retorno estructural' in body
        assert 'Abrir modulo' in body
