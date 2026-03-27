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
            ("dashboard:dashboard", "dashboard/resumen.html", ["kpis", "alerts", "macro_local", "market_snapshot_feature", "parking_feature", "evolucion_historica"]),
            ("dashboard:analisis", "dashboard/analisis.html", ["concentracion_sector", "riesgo_portafolio_detallado"]),
            ("dashboard:estrategia", "dashboard/estrategia.html", ["kpis", "senales_rebalanceo", "analytics_v2_summary", "evolucion_historica"]),
            ("dashboard:cartera_detalle", "dashboard/cartera_detalle.html", ["kpis", "portafolio", "market_snapshot_feature"]),
            ("dashboard:riesgo_avanzado", "dashboard/riesgo_avanzado.html", ["kpis", "analytics_v2_summary", "riesgo_portafolio"]),
            ("dashboard:planeacion", "dashboard/planeacion.html", ["kpis", "portafolio", "senales_rebalanceo", "portfolio_scope_summary", "monthly_allocation_plan", "candidate_asset_ranking", "incremental_portfolio_simulation", "preferred_incremental_portfolio_proposal", "decision_engine_summary", "incremental_proposal_history", "incremental_proposal_tracking_baseline", "incremental_manual_decision_summary", "incremental_decision_executive_summary", "incremental_portfolio_simulation_comparison", "candidate_incremental_portfolio_comparison", "candidate_split_incremental_portfolio_comparison", "manual_incremental_portfolio_simulation_comparison"]),
            ("dashboard:laboratorio", "dashboard/laboratorio.html", ["kpis", "portafolio", "senales_rebalanceo", "portfolio_scope_summary"]),
            ("dashboard:performance", "dashboard/performance.html", ["kpis"]),
            ("dashboard:metricas", "dashboard/metricas.html", ["kpis"]),
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

    def test_lightweight_centers_do_not_receive_full_dashboard_payload(self, auth_client):
        performance = auth_client.get(reverse("dashboard:performance"))
        metricas = auth_client.get(reverse("dashboard:metricas"))

        for response in (performance, metricas):
            assert response.status_code == 200
            assert "analytics_v2_summary" not in response.context
            assert "market_snapshot_feature" not in response.context
            assert "portafolio" not in response.context
            assert "macro_local" not in response.context

    def test_resumen_and_estrategia_now_load_distinct_context_families(self, auth_client):
        resumen = auth_client.get(reverse("dashboard:dashboard"))
        estrategia = auth_client.get(reverse("dashboard:estrategia"))

        assert resumen.status_code == 200
        assert estrategia.status_code == 200

        assert "alerts" in resumen.context
        assert "macro_local" in resumen.context
        assert "analytics_v2_summary" not in resumen.context
        assert "portafolio" not in resumen.context

        assert "analytics_v2_summary" in estrategia.context
        assert "concentracion_sector" in estrategia.context
        assert "alerts" not in estrategia.context
        assert "macro_local" not in estrategia.context

    def test_legacy_resumen_route_redirects_to_canonical_dashboard(self, auth_client):
        response = auth_client.get(reverse("dashboard:resumen"))

        assert response.status_code == 302
        assert response["Location"].endswith(reverse("dashboard:dashboard"))

    def test_strategy_page_keeps_executive_reading_and_moves_inventory_out(self, auth_client):
        response = auth_client.get(reverse("dashboard:estrategia"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Como leer esta hoja:" in content
        assert "Resumen ejecutivo" in content
        assert "Analytics v2" in content
        assert "Abrir riesgo avanzado" in content
        assert "Senales de Rebalanceo" in content
        assert "Evolucion Historica" in content
        assert "Abrir cartera detallada" in content
        assert "Cartera detallada y capa operativa" in content
        assert "Estado FX" in content
        assert "UVA anualizada 30d" in content
        assert "Activo que mas explica el riesgo" in content
        assert "Escenario mas adverso" in content
        assert "Factor dominante" in content
        assert "Fragilidad ante stress" in content
        assert "Retorno estructural" in content
        assert "Macro local" in content
        assert "Posiciones completas" not in content
        assert "Portafolio Invertido Completo" not in content
        assert "FCI / Cash Management" not in content
        assert "Capa operativa puntual" not in content
        assert "Ver detalle" not in content

    def test_planeacion_page_contains_critical_modules(self, auth_client):
        response = auth_client.get(reverse("dashboard:planeacion"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "resolver primero qu\u00e9 hacer con el aporte mensual" in content
        assert "arranc\u00e1 por `Aportes` y no necesit\u00e1s recorrer el resto de la hoja" in content
        assert "Flujo principal" in content
        assert "Ir a Aportes" in content
        assert "Abrir herramientas complementarias" in content
        assert "Herramientas complementarias" in content
        assert "Planeaci\u00f3n de aportes: flujo principal" in content
        assert "Universo patrimonial" in content
        assert "Patrimonio total broker" in content
        assert "Cash disponible" in content
        assert "Caucion colocada" in content
        assert "Capital invertido analizado" in content
        assert "Si necesit\u00e1s m\u00e1s contexto:" in content
        assert "Diagn\u00f3stico previo al aporte" in content
        assert "Se\u00f1ales de diagn\u00f3stico y priorizaci\u00f3n" in content
        assert "Macro local FX + UVA:" in content
        assert "Macro local FX/UVA" in content
        assert "Primera acci\u00f3n sugerida:" in content
        assert "recommendations-container" in content
        assert "simulation-activo" not in content
        assert "monthly-plan-result" not in content
        assert "optimization-result" not in content
        assert "Activos candidatos para construir la propuesta" in content
        assert "Modo decisi\u00f3n" in content
        assert "Contexto r\u00e1pido" in content
        assert "Estado de cartera" in content
        assert "Recomendaci\u00f3n principal" in content
        assert "Opciones sugeridas" in content
        assert "Impacto estimado" in content
        assert "Tu decisi\u00f3n este mes" in content
        assert "Score:" in content
        assert "Confianza:" in content
        assert "Por qu\u00e9 esta decisi\u00f3n" in content
        assert "Ejecutar decisi\u00f3n" in content
        assert "Explorar alternativas" in content
        assert "Lectura sugerida del cierre:" in content
        assert "Decisi\u00f3n sugerida: propuesta incremental preferida" in content
        assert "Validaci\u00f3n before/after del impacto incremental" in content
        assert "Exploraci\u00f3n y comparaci\u00f3n" in content
        assert "Orden sugerido:" in content
        assert "Exploraci\u00f3n" in content
        assert "Resumen ejecutivo unificado" in content
        assert "Seguimiento y governance" in content
        assert "Seguimiento operativo incremental" in content
        assert "Historial operativo y acciones manuales" in content
        assert "Historial reciente de propuestas guardadas" in content
        assert "Checklist de adopci\u00f3n de propuesta incremental" not in content
        assert "Workflow de decisi\u00f3n manual" not in content
        assert "Resumen ejecutivo de seguimiento incremental" not in content
        assert "Baseline incremental de seguimiento" not in content
        assert "Semaforizaci\u00f3n operativa del backlog incremental" not in content
        assert "Resumen operativo del frente de backlog y baseline" not in content
        assert "Drift vs propuesta preferida actual" not in content
        assert "Backlog pendiente vs baseline activo" not in content
        assert "Priorizaci\u00f3n operativa" not in content
        assert "Alertas de drift" not in content
        assert "Snapshot guardado vs propuesta actual" not in content
        assert "Aceptar visibles" in content or "Todav\u00eda no guardaste propuestas incrementales preferidas." in content
        assert "Comparador de propuestas incrementales" in content
        assert "Comparador incremental por candidato" in content
        assert "Comparador incremental por split de bloque" in content
        assert "Comparador manual de planes incrementales" in content
        assert "Herramienta secundaria: plan mensual por perfil" not in content
        assert "Plan mensual por perfil" not in content
        assert "Simulaci\u00f3n t\u00e1ctica" not in content
        assert "Optimizaci\u00f3n te\u00f3rica" not in content
        assert "Configuraci\u00f3n base" not in content
        assert "Abrir Laboratorio" in content

    def test_laboratorio_page_contains_advanced_modules(self, auth_client):
        response = auth_client.get(reverse("dashboard:laboratorio"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Laboratorio de Planeaci\u00f3n" in content
        assert "simulation-activo" in content
        assert "monthly-plan-result" in content
        assert "optimization-result" in content
        assert "Plan mensual por perfil" in content
        assert "Optimización teórica" in content
        assert "Configuración base" in content
        assert "Guardar parámetros" in content

    def test_cartera_detalle_page_contains_inventory_and_operational_modules(self, auth_client):
        response = auth_client.get(reverse("dashboard:cartera_detalle"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Cartera detallada" in content
        assert "Inventario completo y operabilidad" in content
        assert "Capa operativa puntual" in content
        assert "Liquidez Operativa" in content
        assert "FCI y Cash Management" in content
        assert "Top 5 Posiciones" in content
        assert "Portafolio Invertido Completo" in content

    def test_riesgo_avanzado_page_groups_advanced_modules(self, auth_client):
        response = auth_client.get(reverse("dashboard:riesgo_avanzado"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Riesgo avanzado" in content
        assert "Analitica avanzada en un solo lugar" in content
        assert "Activo que mas explica el riesgo" in content
        assert "Escenario mas adverso" in content
        assert "Factor dominante" in content
        assert "Fragilidad ante stress" in content
        assert "Retorno estructural" in content
        assert "Abrir modulo" in content

    def test_preferences_are_reflected_in_body_class(self, auth_client):
        auth_client.post(
            reverse("dashboard:set_preferences"),
            {"ui_mode": "denso", "risk_profile": "agresivo", "next": reverse("dashboard:estrategia")},
        )
        response = auth_client.get(reverse("dashboard:estrategia"))
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert 'class="profile-agresivo"' in content


