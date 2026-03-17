import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestDashboardFeatureFlows:
    @pytest.fixture
    def auth_client(self):
        user = User.objects.create_user(username="flow-user", password="testpass123")
        client = Client(raise_request_exception=False)
        client.force_login(user)
        return client

    @pytest.mark.parametrize(
        ("route_name", "expected_template", "required_context_keys"),
        [
            ("dashboard:dashboard", "dashboard/resumen.html", ["kpis", "portafolio", "senales_rebalanceo"]),
            ("dashboard:resumen", "dashboard/resumen.html", ["kpis", "alerts"]),
            ("dashboard:analisis", "dashboard/analisis.html", ["concentracion_sector", "riesgo_portafolio_detallado"]),
            ("dashboard:estrategia", "dashboard/estrategia.html", ["kpis", "portafolio", "senales_rebalanceo", "analytics_v2_summary"]),
            ("dashboard:planeacion", "dashboard/planeacion.html", ["kpis", "portafolio", "senales_rebalanceo", "monthly_allocation_plan", "candidate_asset_ranking", "incremental_portfolio_simulation", "incremental_portfolio_simulation_comparison", "candidate_incremental_portfolio_comparison", "manual_incremental_portfolio_simulation_comparison"]),
            ("dashboard:performance", "dashboard/performance.html", ["kpis", "evolucion_historica"]),
            ("dashboard:metricas", "dashboard/metricas.html", ["kpis", "riesgo_portafolio"]),
        ],
    )
    def test_dashboard_routes_have_template_and_context(
        self, auth_client, route_name, expected_template, required_context_keys
    ):
        response = auth_client.get(reverse(route_name))

        assert response.status_code == 200
        assert expected_template in [template.name for template in response.templates]
        for key in required_context_keys:
            assert key in response.context

    def test_strategy_page_excludes_operational_modules(self, auth_client):
        response = auth_client.get(reverse("dashboard:estrategia"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "recommendations-container" not in content
        assert "simulation-activo" not in content
        assert "monthly-plan-result" not in content
        assert "optimization-result" not in content
        assert "Posiciones completas" in content

    def test_planeacion_page_contains_critical_modules(self, auth_client):
        response = auth_client.get(reverse("dashboard:planeacion"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "recommendations-container" in content
        assert "simulation-activo" in content
        assert "monthly-plan-result" in content
        assert "optimization-result" in content
        assert "Candidatos de activos dentro de los bloques recomendados" in content
        assert "Impacto incremental simulado" in content
        assert "Comparador de propuestas incrementales" in content
        assert "Comparador incremental por candidato" in content
        assert "Comparador manual de planes incrementales" in content

    def test_preferences_are_reflected_in_body_class(self, auth_client):
        auth_client.post(
            reverse("dashboard:set_preferences"),
            {"ui_mode": "denso", "risk_profile": "agresivo", "next": reverse("dashboard:estrategia")},
        )
        response = auth_client.get(reverse("dashboard:estrategia"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert 'class="profile-agresivo"' in content
