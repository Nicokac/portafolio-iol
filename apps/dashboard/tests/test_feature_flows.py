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
            ("dashboard:resumen", "dashboard/resumen.html", ["kpis", "alerts", "macro_local"]),
            ("dashboard:analisis", "dashboard/analisis.html", ["concentracion_sector", "riesgo_portafolio_detallado"]),
            ("dashboard:estrategia", "dashboard/estrategia.html", ["kpis", "portafolio", "senales_rebalanceo", "analytics_v2_summary"]),
            ("dashboard:planeacion", "dashboard/planeacion.html", ["kpis", "portafolio", "senales_rebalanceo", "monthly_allocation_plan", "candidate_asset_ranking", "incremental_portfolio_simulation", "preferred_incremental_portfolio_proposal", "incremental_proposal_history", "incremental_proposal_tracking_baseline", "incremental_manual_decision_summary", "incremental_decision_executive_summary", "incremental_portfolio_simulation_comparison", "candidate_incremental_portfolio_comparison", "candidate_split_incremental_portfolio_comparison", "manual_incremental_portfolio_simulation_comparison"]),
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
        assert "resolver primero qu\u00e9 hacer con el aporte mensual" in content
        assert "Diagn\u00f3stico previo al aporte" in content
        assert "Se\u00f1ales de diagn\u00f3stico y priorizaci\u00f3n" in content
        assert "recommendations-container" in content
        assert "simulation-activo" in content
        assert "monthly-plan-result" in content
        assert "optimization-result" in content
        assert "Activos candidatos para construir la propuesta" in content
        assert "N\u00facleo de decisi\u00f3n" in content
        assert "La decisión sugerida consolidada queda en el bloque siguiente." in content
        assert "Lectura sugerida del cierre:" in content
        assert "Decisi\u00f3n sugerida: propuesta incremental preferida" in content
        assert "Validaci\u00f3n before/after del impacto incremental" in content
        assert "Exploraci\u00f3n y comparaci\u00f3n" in content
        assert "Orden sugerido:" in content
        assert "Resumen ejecutivo unificado" in content
        assert "Seguimiento y governance" in content
        assert "Seguimiento operativo incremental" in content
        assert "Historial operativo y acciones manuales" in content
        assert "Historial reciente de propuestas guardadas" in content
        assert "Checklist de adopciÃ³n de propuesta incremental" not in content
        assert "Workflow de decisiÃ³n manual" not in content
        assert "Resumen ejecutivo de seguimiento incremental" not in content
        assert "Baseline incremental de seguimiento" not in content
        assert "SemaforizaciÃ³n operativa del backlog incremental" not in content
        assert "Resumen operativo del frente de backlog y baseline" not in content
        assert "Drift vs propuesta preferida actual" not in content
        assert "Backlog pendiente vs baseline activo" not in content
        assert "PriorizaciÃ³n operativa" not in content
        assert "Alertas de drift" not in content
        assert "Snapshot guardado vs propuesta actual" not in content
        assert "Aceptar visibles" in content or "Todav\u00eda no guardaste propuestas incrementales preferidas." in content
        assert "Comparador de propuestas incrementales" in content
        assert "Comparador incremental por candidato" in content
        assert "Comparador incremental por split de bloque" in content
        assert "Comparador manual de planes incrementales" in content
        assert "Herramienta secundaria: plan mensual por perfil" in content
        assert "Plan mensual por perfil" in content
        assert "Simulaci\u00f3n t\u00e1ctica" in content
        assert "Optimizaci\u00f3n te\u00f3rica" in content
        assert "Configuraci\u00f3n base" in content

    def test_preferences_are_reflected_in_body_class(self, auth_client):
        auth_client.post(
            reverse("dashboard:set_preferences"),
            {"ui_mode": "denso", "risk_profile": "agresivo", "next": reverse("dashboard:estrategia")},
        )
        response = auth_client.get(reverse("dashboard:estrategia"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert 'class="profile-agresivo"' in content


