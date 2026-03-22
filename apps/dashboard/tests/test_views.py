import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.core.models import IncrementalProposalSnapshot, SensitiveActionAudit


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
        assert 'Total patrimonio modelado' in body
        assert 'Capital invertido analizado' in body
        assert 'Liquidez operativa' in body
        assert 'Liquidez estrat' in body
        assert 'Caución colocada' in body or 'Caucion colocada' in body
        assert 'USD oficial mayorista BCRA' in body
        assert 'Riesgo país Argentina' in body
        assert 'Dólar financiero y régimen FX' in body
        assert 'UVA y tasa real local' in body
        assert 'Actividad operativa reciente' in body
        assert 'Real rate BADLAR vs UVA 30d anualizada' in body
        assert 'Fuente: ArgentinaDatos' in body
        assert 'Cambio 30d:' in body

    def test_resumen_renders_market_snapshot_panel(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_market_snapshot_feature_context',
            lambda: {
                'has_cached_snapshot': True,
                'refreshed_at_label': '2026-03-21 10:00',
                'summary': {
                    'available_count': 2,
                    'total_symbols': 3,
                    'order_book_count': 1,
                    'fallback_count': 1,
                },
                'top_missing_count': 1,
                'alerts': [
                    {'tone': 'warning', 'title': 'Cobertura parcial en posiciones relevantes', 'message': '1 posicion relevante sin snapshot.'},
                ],
                'top_rows': [
                    {
                        'simbolo': 'MELI',
                        'descripcion': 'Cedear Mercadolibre Inc.',
                        'peso_porcentual': 12.5,
                        'variacion': -1.66,
                        'spread_pct': 4.29,
                        'cantidad_operaciones': 5341,
                        'snapshot_status_label': 'Disponible',
                        'snapshot_source_label': 'CotizacionDetalle',
                    }
                ],
            },
        )
        response = auth_client.get(reverse('dashboard:resumen'))
        body = response.content.decode()
        assert 'Pulso de mercado puntual' in body
        assert 'CotizacionDetalle' in body
        assert 'Cobertura parcial en posiciones relevantes' in body
        assert 'Fallbacks' not in body
        assert '<th class="text-end">Spread</th>' not in body

    def test_resumen_renders_parking_panel(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_portfolio_parking_feature_context',
            lambda: {
                'has_visible_parking': True,
                'summary': {
                    'total_positions': 3,
                    'parking_count': 1,
                    'parking_pct': 33.33,
                    'parking_value_total': 1500,
                },
                'alerts': [
                    {'tone': 'warning', 'title': 'Parking visible en posiciones actuales', 'message': '1 posicion con parking visible.'},
                ],
                'top_rows': [
                    {
                        'activo': type('Activo', (), {'simbolo': 'AL30', 'descripcion': 'Bono AL30'})(),
                        'parking_tone': 'warning',
                        'parking_label': 'Con parking',
                        'parking_detail_label': 'Cantidad 5 · Fecha 2026-03-25',
                        'disponible_inmediato': 5,
                        'valorizado': 1500,
                    }
                ],
            },
        )
        response = auth_client.get(reverse('dashboard:resumen'))
        body = response.content.decode()
        assert 'Parking visible en cartera' in body
        assert 'Con parking' in body
        assert 'Cantidad 5' in body

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
        assert 'Total patrimonio modelado' in body
        assert 'Liquidez operativa' in body
        assert 'Cash a liquidar' in body
        assert 'Liquidez Estrat' in body
        assert 'Liquidez total combinada' in body
        assert 'Caucion Colocada' in body
        assert 'Navegación rápida' in body
        assert 'Lectura del portafolio' in body
        assert 'Vista analítica' in body
        assert 'Cash real disponible' in body
        assert 'Saldos próximos a liquidar' in body or 'Saldos proximos a liquidar' in body
        assert 'FCI cash management' in body
        assert 'Capital Invertido Analizado' in body
        assert '% Renta fija AR' in body
        assert 'Analytics v2' in body
        assert 'Resumen Analytics v2' in body
        assert 'Señales Analytics v2' in body
        assert 'Macro Local' in body
        assert 'Carry real BADLAR' in body
        assert 'Brecha FX' in body
        assert 'CCL' in body
        assert 'Estado FX' in body
        assert 'Spread MEP / CCL' in body
        assert 'UVA anualizada 30d' in body
        assert 'Tasa real BADLAR vs UVA' in body
        assert 'Riesgo pais' in body
        assert 'Peso soberano local' in body
        assert 'Nombres soberanos' in body
        assert 'Top soberano local' in body
        assert 'Concentración bloque soberano' in body
        assert 'Split hard dollar / CER' in body
        assert 'Ver detalle' in body
        assert 'Último snapshot' in body
        assert 'Gap máximo' in body
        assert 'Flujos y actividad reciente' in body
        assert 'Dividendos cobrados' in body
        assert 'Suscripciones FCI' in body
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

    def test_estrategia_renders_market_snapshot_panel(self, auth_client, monkeypatch):
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
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert 'Capa operativa puntual' in body
        assert 'CotizacionDetalle como lectura táctica' in body or 'CotizacionDetalle como lectura tactica' in body
        assert 'GGAL' in body
        assert 'Fallbacks' in body
        assert '<th class="text-end">Spread</th>' in body

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

    def test_scenario_analysis_detail_route_accessible_authenticated(self, auth_client):
        response = auth_client.get(reverse('dashboard:scenario_analysis_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Scenario Analysis' in body
        assert 'Escenarios evaluados' in body
        assert 'Peor escenario' in body
        assert 'Shock aplicado' in body
        assert 'Agregado por sector del peor escenario' in body
        assert 'Activos del peor escenario' in body

    def test_scenario_analysis_detail_handles_empty_payload(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_scenario_analysis_detail',
            lambda: {
                'scenarios': [],
                'worst_scenario': None,
                'worst_assets': [],
                'worst_sectors': [],
                'worst_countries': [],
                'confidence': 'low',
                'warnings': ['missing_shock'],
                'methodology': None,
                'limitations': None,
            },
        )
        response = auth_client.get(reverse('dashboard:scenario_analysis_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Sin escenarios disponibles.' in body
        assert 'Sin agregados por sector.' in body
        assert 'Sin detalle por activo disponible.' in body

    def test_estrategia_contains_scenario_analysis_detail_link(self, auth_client):
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert response.status_code == 200
        assert reverse('dashboard:scenario_analysis_detail') in body

    def test_factor_exposure_detail_route_accessible_authenticated(self, auth_client):
        response = auth_client.get(reverse('dashboard:factor_exposure_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Factor Exposure' in body
        assert 'Exposición agregada por factor' in body
        assert 'Factor dominante' in body
        assert 'Activos sin clasificación factorial' in body

    def test_factor_exposure_detail_handles_empty_payload(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_factor_exposure_detail',
            lambda: {
                'factors': [],
                'dominant_factor': None,
                'dominant_factor_key': None,
                'underrepresented_factors': [],
                'unknown_assets': [],
                'unknown_assets_count': 0,
                'confidence': 'low',
                'warnings': ['empty_portfolio'],
                'methodology': None,
                'limitations': None,
                'interpretation': '',
            },
        )
        response = auth_client.get(reverse('dashboard:factor_exposure_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Sin factores disponibles.' in body
        assert 'Sin activos sin clasificación.' in body

    def test_estrategia_contains_factor_exposure_detail_link(self, auth_client):
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert response.status_code == 200
        assert reverse('dashboard:factor_exposure_detail') in body

    def test_stress_fragility_detail_route_accessible_authenticated(self, auth_client):
        response = auth_client.get(reverse('dashboard:stress_fragility_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Stress Fragility' in body
        assert 'Stresses evaluados' in body
        assert 'Stress score' in body
        assert 'Breakdown por sector' in body
        assert 'Breakdown por activo' in body

    def test_stress_fragility_detail_handles_empty_payload(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_stress_fragility_detail',
            lambda: {
                'stresses': [],
                'worst_stress': None,
                'worst_assets': [],
                'worst_sectors': [],
                'worst_countries': [],
                'confidence': 'low',
                'warnings': ['empty_portfolio'],
                'methodology': None,
                'limitations': None,
                'interpretation': '',
            },
        )
        response = auth_client.get(reverse('dashboard:stress_fragility_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Sin stress disponible.' in body
        assert 'Sin breakdown por sector.' in body
        assert 'Sin breakdown por activo.' in body

    def test_estrategia_contains_stress_fragility_detail_link(self, auth_client):
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert response.status_code == 200
        assert reverse('dashboard:stress_fragility_detail') in body

    def test_expected_return_detail_route_accessible_authenticated(self, auth_client):
        response = auth_client.get(reverse('dashboard:expected_return_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Expected Return' in body
        assert 'Retorno esperado nominal' in body
        assert 'Breakdown por bucket' in body
        assert 'Supuestos y limitaciones' in body

    def test_expected_return_detail_handles_empty_payload(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_expected_return_detail',
            lambda: {
                'expected_return_pct': None,
                'real_expected_return_pct': None,
                'basis_reference': 'weighted_bucket_baseline_current_positions',
                'dominant_bucket': None,
                'bucket_rows': [],
                'asset_rows': [],
                'confidence': 'low',
                'warnings': [],
                'main_warning': None,
                'methodology': None,
                'limitations': None,
                'assumptions': [],
                'interpretation': '',
            },
        )
        response = auth_client.get(reverse('dashboard:expected_return_detail'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Sin breakdown por bucket disponible.' in body
        assert 'El servicio actual no expone detalle por activo para Expected Return.' in body

    def test_estrategia_contains_expected_return_detail_link(self, auth_client):
        response = auth_client.get(reverse('dashboard:estrategia'))
        body = response.content.decode()
        assert response.status_code == 200
        assert reverse('dashboard:expected_return_detail') in body

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

    def test_planeacion_uses_incremental_context_facade(self, auth_client, monkeypatch):
        captured = {}

        def fake_planeacion_context(query_params, user, capital_amount=600000, history_limit=5):
            captured["decision_status_filter"] = query_params.get("decision_status_filter")
            captured["history_priority_filter"] = query_params.get("history_priority_filter")
            captured["history_sort"] = query_params.get("history_sort")
            captured["backlog_followup_filter"] = query_params.get("backlog_followup_filter")
            captured["user_id"] = user.id
            captured["capital_amount"] = capital_amount
            captured["history_limit"] = history_limit
            return {
                "monthly_allocation_plan": {"recommended_blocks": [], "avoided_blocks": [], "explanation": ""},
                "candidate_asset_ranking": {"candidate_assets": [], "candidate_assets_count": 0, "by_block": {}, "explanation": ""},
                "incremental_portfolio_simulation": {"selected_candidates": [], "before": {}, "after": {}, "delta": {}, "interpretation": "", "unmapped_blocks": []},
                "incremental_portfolio_simulation_comparison": {"proposals": [], "best_label": None},
                "candidate_incremental_portfolio_comparison": {"available_blocks": [], "proposals": [], "best_label": None},
                "candidate_split_incremental_portfolio_comparison": {"available_blocks": [], "proposals": [], "best_label": None},
                "manual_incremental_portfolio_simulation_comparison": {"submitted": False, "proposals": [], "form_state": {"capital_amount": 600000}},
                "preferred_incremental_portfolio_proposal": {"preferred": None, "explanation": "", "has_manual_override": False},
                "incremental_proposal_history": {
                    "items": [],
                    "count": 0,
                    "has_history": False,
                    "active_filter": "pending",
                    "active_filter_label": "Pendientes",
                    "active_priority_filter": "all",
                    "active_priority_filter_label": "Todas las prioridades",
                    "active_sort_mode": "newest",
                    "active_sort_mode_label": "Más recientes",
                    "decision_counts": {"total": 0, "pending": 0, "accepted": 0, "deferred": 0, "rejected": 0},
                    "available_filters": [],
                    "available_priority_filters": [],
                    "available_sort_modes": [],
                    "headline": "",
                },
                "incremental_proposal_tracking_baseline": {"item": None, "has_baseline": False},
                "incremental_manual_decision_summary": {"item": None, "has_decision": False, "status": "pending", "status_label": "Pendiente", "headline": ""},
                "incremental_decision_executive_summary": {"status": "pending", "headline": "", "items": [], "has_summary": False},
            }

        monkeypatch.setattr("apps.dashboard.views.get_planeacion_incremental_context", fake_planeacion_context)

        response = auth_client.get(
            reverse("dashboard:planeacion"),
            {
                "decision_status_filter": "pending",
                "history_priority_filter": "high",
                "history_sort": "priority",
                "backlog_followup_filter": "monitor",
            },
        )

        assert response.status_code == 200
        assert captured == {
            "decision_status_filter": "pending",
            "history_priority_filter": "high",
            "history_sort": "priority",
            "backlog_followup_filter": "monitor",
            "user_id": int(auth_client.session["_auth_user_id"]),
            "capital_amount": 600000,
            "history_limit": 5,
        }

    def test_planeacion_explains_total_liquidity_definition(self, auth_client):
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Liquidez desplegable = cash disponible + caucion colocada + cash management' in body
        assert 'Flujo operativo del mes' in body

    def test_planeacion_renders_market_snapshot_panel(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_market_snapshot_feature_context',
            lambda: {
                'has_cached_snapshot': False,
                'refreshed_at_label': '',
                'summary': {
                    'available_count': 0,
                    'total_symbols': 0,
                    'order_book_count': 0,
                    'fallback_count': 0,
                },
                'top_missing_count': 0,
                'alerts': [
                    {'tone': 'secondary', 'title': 'Snapshot puntual pendiente', 'message': 'Todavia no hay market snapshot IOL cacheado.'},
                ],
                'top_rows': [],
            },
        )
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Chequeo de mercado puntual' in body
        assert 'Snapshot puntual pendiente' in body
        assert 'Sin posiciones relevantes para market snapshot' in body
        assert 'Fallbacks' not in body
        assert 'Modelo de riesgo:' in body

    def test_planeacion_renders_market_snapshot_history_panel(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_market_snapshot_history_feature_context',
            lambda: {
                'lookback_days': 7,
                'summary': {
                    'strong_count': 0,
                    'watch_count': 1,
                    'weak_count': 1,
                    'insufficient_count': 0,
                },
                'alerts': [
                    {
                        'tone': 'warning',
                        'title': 'Liquidez reciente debil en posiciones actuales',
                        'message': '1 simbolo(s) muestran spread o actividad reciente debil para reforzar compras.',
                    },
                ],
                'top_rows': [
                    {
                        'simbolo': 'MELI',
                        'bloque_estrategico': 'Growth USA',
                        'quality_status': 'weak',
                        'quality_status_label': 'Debil',
                        'quality_summary': 'spread medio 1.50%, ops medias 80, libro visible 50.00%.',
                        'avg_spread_pct': Decimal('1.50'),
                        'avg_operations': 80,
                        'last_captured_at_label': '2026-03-21 10:00',
                    }
                ],
                'weak_blocks': [{'label': 'Growth USA', 'value_total': Decimal('900000')}],
                'rows': [],
                'has_history': True,
            },
        )
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Calidad reciente de ejecucion' in body
        assert 'Liquidez reciente debil en posiciones actuales' in body
        assert 'Growth USA' in body
        assert 'Debil' in body

    def test_planeacion_renders_parking_panel(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_portfolio_parking_feature_context',
            lambda: {
                'has_visible_parking': False,
                'summary': {
                    'total_positions': 2,
                    'parking_count': 0,
                    'parking_pct': 0,
                    'parking_value_total': 0,
                },
                'alerts': [],
                'top_rows': [],
            },
        )
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Parking visible antes de decidir' in body
        assert 'Sin parking visible en el portafolio actual' in body

    def test_planeacion_shows_monthly_allocation_proposal(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
                'portfolio_scope_summary': {
                    'portfolio_total_broker': 15863589,
                    'invested_portfolio': 13330704,
                    'cash_management_fci': 2532885,
                    'cash_available_broker': 11039915.47,
                    'cash_available_broker_ars': 11039915.47,
                    'cash_available_broker_usd': 0.56,
                    'cash_settling_broker': 10063847.36,
                    'cash_settling_broker_ars': 10063847.36,
                    'cash_settling_broker_usd': 0.0,
                    'cash_ratio_total': 0.6959,
                    'invested_ratio_total': 0.8403,
                    'fci_ratio_total': 0.1597,
                },
                'monthly_allocation_plan': {
                    'capital_total': capital_amount,
                    'recommended_blocks_count': 1,
                    'criterion': 'signals_first',
                    'explanation': 'Plan incremental MVP',
                    'recommended_blocks': [
                        {
                            'label': 'Tecnología / growth',
                            'suggested_amount': 600000,
                            'suggested_pct': 100.0,
                            'score': 3.4,
                            'reason': 'Se prioriza retorno esperado estructural.',
                            'score_breakdown': {
                                'positive_signals': [{'signal': 'expected_return_bucket_preferred', 'impact': '+1.2', 'source': 'expected_return'}],
                                'negative_signals': [{'signal': 'risk_concentration_tech', 'impact': '-0.4', 'source': 'risk_contribution'}],
                                'notes': 'Bloque simple de ejemplo.',
                            },
                        }
                    ],
                    'avoided_blocks': [],
                },
                'candidate_asset_ranking': {
                    'candidate_assets': [
                        {'asset': 'KO', 'block': 'defensive', 'score': 8.4, 'rank': 1, 'reasons': ['defensive_sector_match'], 'main_reason': 'defensive_sector_match'}
                    ],
                    'candidate_assets_count': 1,
                    'by_block': {},
                    'explanation': 'Ranking incremental MVP',
                },
                'incremental_portfolio_simulation': {
                    'selected_candidates': [{'symbol': 'KO', 'block_label': 'Defensive / resiliente', 'amount': 600000}],
                    'before': {'expected_return_pct': 8.0, 'real_expected_return_pct': 2.0, 'fragility_score': 18.0, 'worst_scenario_loss_pct': -12.0},
                    'after': {'expected_return_pct': 8.5, 'real_expected_return_pct': 2.2, 'fragility_score': 16.0, 'worst_scenario_loss_pct': -11.5},
                    'delta': {'expected_return_change': 0.5, 'real_expected_return_change': 0.2, 'fragility_change': -2.0, 'scenario_loss_change': 0.5, 'risk_concentration_change': -0.3},
                    'interpretation': 'La compra reduce la fragilidad del portafolio.',
                    'unmapped_blocks': [],
                },
                'incremental_portfolio_simulation_comparison': {
                    'best_label': 'Top candidato por bloque',
                    'proposals': [{'proposal_label': 'Split del bloque más grande', 'label': 'Split del bloque más grande', 'comparison_score': 3.1, 'purchase_summary': 'KO · 600000', 'simulation': {'delta': {'expected_return_change': 0.4, 'fragility_change': -1.5, 'scenario_loss_change': 0.3}}}],
                },
                'candidate_incremental_portfolio_comparison': {
                    'selected_block_label': 'Defensive / resiliente',
                    'comparisons': [{'candidate_symbol': 'KO', 'headline': 'KO mejora más la resiliencia.', 'comparison_score': 3.4, 'simulation': {'delta': {'expected_return_change': 0.3, 'fragility_change': -1.4, 'scenario_loss_change': 0.2}}}],
                },
                'candidate_split_incremental_portfolio_comparison': {
                    'selected_block_label': 'Defensive / resiliente',
                    'proposals': [{'proposal_label': 'Split KO + MCD', 'label': 'Split KO + MCD', 'comparison_score': 3.6, 'simulation': {'delta': {'expected_return_change': 0.5, 'fragility_change': -1.8, 'scenario_loss_change': 0.4}}}],
                },
                'manual_incremental_portfolio_simulation_comparison': {
                    'submitted': False,
                    'proposals': [],
                    'form_state': {'capital_amount': history_limit * 120000},
                },
                'preferred_incremental_portfolio_proposal': {
                    'preferred': {
                        'source_label': 'Comparador por split',
                        'selected_context': 'Defensive / resiliente',
                        'proposal_label': 'Split KO + MCD',
                        'comparison_score': 5.2,
                        'purchase_plan': [{'symbol': 'KO', 'amount': 150000}, {'symbol': 'MCD', 'amount': 150000}],
                        'simulation': {'delta': {'expected_return_change': 0.5, 'real_expected_return_change': 0.2, 'fragility_change': -2.1, 'scenario_loss_change': 0.7, 'risk_concentration_change': -0.6}, 'interpretation': 'El split mejora mejor el balance riesgo/retorno.'},
                    },
                    'has_manual_override': False,
                    'explanation': 'La propuesta preferida actual surge de Comparador por split para Defensive / resiliente: Split KO + MCD.',
                },
                'decision_engine_summary': {
                    'portfolio_scope': {
                        'portfolio_total_broker': 15863589,
                        'invested_portfolio': 13330704,
                        'cash_management_fci': 2532885,
                        'cash_available_broker': 11039915.47,
                        'cash_ratio_total': 0.6959,
                        'invested_ratio_total': 0.8403,
                    },
                    'recommendation_context': 'high_cash',
                    'strategy_bias': 'deploy_cash',
                    'execution_gate': {
                        'has_blocker': False,
                        'status': 'ready',
                        'title': '',
                        'summary': '',
                        'primary_cta_label': 'Ejecutar decisión',
                        'primary_cta_tone': 'success',
                    },
                    'action_suggestions': [
                        {
                            'type': 'allocation',
                            'message': 'Tenés capital disponible para invertir',
                            'suggestion': 'Evaluar asignar entre 20% y 40% del cash.',
                        }
                    ],
                    'macro_state': {'key': 'normal', 'label': 'Normal', 'summary': 'No hay una senal macro dominante que invalide el flujo principal.'},
                    'portfolio_state': {'key': 'ok', 'label': 'OK', 'summary': 'La cartera admite un aporte incremental sin desviar el flujo principal.'},
                    'recommendation': {
                        'block': 'Tecnología / growth',
                        'amount': 600000,
                        'reason': 'Se prioriza retorno esperado estructural.',
                        'has_recommendation': True,
                        'priority_label': 'Prioritaria',
                        'priority_tone': 'success',
                        'is_conditioned_by_parking': False,
                    },
                    'suggested_assets': [
                        {'symbol': 'KO', 'block': 'Defensive / resiliente', 'score': 8.4, 'reason': 'defensive_sector_match', 'is_conditioned_by_parking': False, 'priority_label': ''},
                    ],
                    'preferred_proposal': {
                        'proposal_key': 'split',
                        'proposal_label': 'Split KO + MCD',
                        'source_label': 'Comparador por split',
                        'purchase_summary': 'KO · 150000, MCD · 150000',
                        'purchase_plan': [{'symbol': 'KO', 'amount': 150000}, {'symbol': 'MCD', 'amount': 150000}],
                        'simulation_delta': {'expected_return_change': 0.5, 'fragility_change': -2.1, 'scenario_loss_change': 0.7},
                        'purchase_plan_blocks': [],
                        'is_conditioned_by_parking': False,
                        'priority_label': 'Lista',
                        'priority_tone': 'success',
                        'parking_note': '',
                    },
                    'expected_impact': {
                        'return': 0.5,
                        'fragility': -2.1,
                        'worst_case': 0.7,
                        'status': 'positive',
                        'summary': 'La propuesta mejora el perfil sin aumentar la fragilidad.',
                    },
                    'score': 78,
                    'confidence': 'Alta',
                    'explanation': [
                        'Se refuerza Tecnología / growth porque Se prioriza retorno esperado estructural..',
                        'El contexto macro esta en normal y no hay una senal macro dominante que invalide el flujo principal..',
                        'El impacto esperado de Split KO + MCD es positive en retorno, fragilidad y peor escenario.',
                        'El riesgo no aumenta materialmente con la propuesta actual.',
                    ],
                    'tracking_payload': {
                        'recommended_block': 'Tecnología / growth',
                        'purchase_plan': [{'symbol': 'KO', 'amount': 150000}, {'symbol': 'MCD', 'amount': 150000}],
                        'score': 78,
                        'confidence': 'Alta',
                    },
                },
                'incremental_proposal_history': {
                    'items': [{'id': 1, 'proposal_label': 'Plan guardado 1', 'source_label': 'Comparador manual', 'selected_context': 'Plan manual enviado por el usuario', 'purchase_plan': [{'symbol': 'KO', 'amount': 300000}], 'simulation_delta': {'expected_return_change': 0.4, 'fragility_change': -1.5, 'scenario_loss_change': 0.3}, 'decision_score': 78, 'decision_confidence': 'Alta', 'decision_explanation': ['Se reforzó una propuesta defensiva con mejor resiliencia.', 'El contexto macro no contradecía la compra.'], 'history_priority': {'has_priority': True, 'priority': 'high', 'priority_label': 'Alta', 'next_action': 'Revisar primero Plan guardado 1: mejora baseline, cuida fragilidad y mantiene buena ejecutabilidad tactica.'}, 'macro_state': 'normal', 'portfolio_state': 'ok', 'manual_decision_status': 'pending', 'manual_decision_status_label': 'Pendiente', 'is_backlog_front': False, 'is_tracking_baseline': False, 'reapply_querystring': 'manual_capital_amount=300000&manual_a_symbol_1=KO&manual_a_amount_1=300000', 'reapply_truncated': False, 'created_at': '2026-03-17 11:00'}],
                    'count': 1,
                    'has_history': True,
                    'active_filter': 'all',
                    'active_filter_label': 'Todos',
                    'active_priority_filter': 'all',
                    'active_priority_filter_label': 'Todas las prioridades',
                    'active_sort_mode': 'newest',
                    'active_sort_mode_label': 'Más recientes',
                    'decision_counts': {'total': 1, 'pending': 1, 'accepted': 0, 'deferred': 0, 'rejected': 0},
                    'available_filters': [{'key': 'all', 'label': 'Todos', 'count': 1, 'selected': True}],
                    'available_priority_filters': [{'key': 'all', 'label': 'Todas las prioridades', 'count': 1, 'selected': True}],
                    'available_sort_modes': [{'key': 'newest', 'label': 'Más recientes', 'selected': True}, {'key': 'priority', 'label': 'Prioridad operativa', 'selected': False}],
                    'headline': 'Se muestran 1 snapshots recientes sobre un total de 1 propuestas guardadas.',
                },
                'incremental_proposal_tracking_baseline': {
                    'item': {'proposal_label': 'Plan baseline', 'source_label': 'Comparador manual', 'purchase_plan': [{'symbol': 'KO', 'amount': 300000}], 'created_at': '2026-03-17 11:00'},
                    'has_baseline': True,
                },
                'incremental_backlog_prioritization': {
                    'count': 3,
                    'has_priorities': True,
                    'has_focus_split': True,
                    'has_shortlist': True,
                    'active_followup_filter': 'all',
                    'active_followup_filter_label': 'Todas',
                    'available_followup_filters': [
                        {'key': 'all', 'label': 'Todas', 'count': 3, 'selected': True},
                        {'key': 'review_now', 'label': 'Revisar ya', 'count': 0, 'selected': False},
                        {'key': 'monitor', 'label': 'Monitorear', 'count': 2, 'selected': False},
                        {'key': 'hold', 'label': 'En espera', 'count': 1, 'selected': False},
                    ],
                    'followup_counts': {'review_now': 0, 'monitor': 2, 'hold': 1},
                    'manual_review_summary': {
                        'pending_count': 1,
                        'deferred_count': 2,
                        'accepted_count': 1,
                        'rejected_count': 0,
                        'closed_count': 1,
                        'reviewed_count': 3,
                        'headline': 'Todavía hay propuestas vigentes para futuras compras dentro del backlog.',
                        'has_manual_reviews': True,
                    },
                    'deferred_review_summary': {
                        'deferred_count': 2,
                        'reactivable_count': 1,
                        'archivable_count': 1,
                        'top_reactivable_label': 'Plan guardado 2',
                        'top_reactivable_priority_label': 'Recuperable',
                        'has_reactivable': True,
                        'headline': 'Parte de las diferidas todavia conserva fit suficiente para reactivarse como futura compra.',
                    },
                    'counts': {'high': 1, 'medium': 1, 'watch': 1, 'low': 0},
                    'headline': 'Backlog priorizado: 1 alta, 1 media y 0 baja. Primero revisar Plan guardado 1.',
                    'explanation': 'El backlog ya contiene alternativas que superan el baseline activo con mejor retorno esperado, sin deterioro material de fragilidad y con buena ejecutabilidad tactica; Plan guardado 1 queda arriba por prioridad.',
                    'top_item': {
                        'snapshot': {'proposal_label': 'Plan guardado 1'},
                        'priority': 'high',
                        'priority_label': 'Alta',
                        'next_action': 'Revisar primero Plan guardado 1: mejora baseline, cuida fragilidad y mantiene buena ejecutabilidad tactica.',
                    },
                    'economic_leader': {
                        'proposal_label': 'Plan guardado 1',
                        'priority_label': 'Alta',
                        'focus_label': 'Líder económico',
                        'focus_summary': 'Mejora retorno esperado sin deterioro material de fragilidad.',
                        'expected_return_change': 0.4,
                        'fragility_change': -1.5,
                    },
                    'tactical_leader': {
                        'proposal_label': 'Plan guardado 2',
                        'priority_label': 'Recuperable',
                        'focus_label': 'Líder táctico',
                        'focus_summary': 'Conserva la ejecutabilidad más limpia para reconsiderar una compra.',
                        'next_action': 'Revisar luego Plan guardado 2: mejora baseline, pero todavia pide validacion tactica adicional.',
                    },
                    'shortlist': [
                        {
                            'rank': 1,
                            'proposal_label': 'Plan guardado 1',
                            'priority': 'high',
                            'priority_label': 'Alta',
                            'next_action': 'Revisar primero Plan guardado 1: mejora baseline, cuida fragilidad y mantiene buena ejecutabilidad tactica.',
                            'selected_context': 'Plan manual enviado por el usuario',
                            'expected_return_change': 0.4,
                            'fragility_change': -1.5,
                            'scenario_loss_change': 0.3,
                            'is_backlog_front': False,
                            'economic_edge': True,
                            'tactical_edge': False,
                            'conviction': {
                                'level': 'medium',
                                'label': 'Convicción media',
                                'summary': 'Tiene mérito para reabrir la compra, pero no domina ambos frentes al mismo tiempo.',
                            },
                            'followup': {
                                'status': 'monitor',
                                'label': 'Monitorear',
                                'summary': 'Conviene seguirla de cerca y revalidarla antes de mover el próximo aporte.',
                            },
                        },
                        {
                            'rank': 2,
                            'proposal_label': 'Plan guardado 2',
                            'priority': 'medium',
                            'priority_label': 'Recuperable',
                            'next_action': 'Revisar luego Plan guardado 2: mejora baseline, pero todavia pide validacion tactica adicional.',
                            'selected_context': '',
                            'expected_return_change': 0.2,
                            'fragility_change': -0.8,
                            'scenario_loss_change': 0.1,
                            'is_backlog_front': False,
                            'economic_edge': False,
                            'tactical_edge': True,
                            'conviction': {
                                'level': 'medium',
                                'label': 'Convicción media',
                                'summary': 'Tiene mérito para reabrir la compra, pero no domina ambos frentes al mismo tiempo.',
                            },
                            'followup': {
                                'status': 'monitor',
                                'label': 'Monitorear',
                                'summary': 'Conviene seguirla de cerca y revalidarla antes de mover el próximo aporte.',
                            },
                        },
                    ],
                },
                'incremental_manual_decision_summary': {
                    'item': {'proposal_label': 'Plan manual A', 'manual_decision_status': 'accepted', 'manual_decision_note': 'Lista para ejecutar', 'manual_decided_at': '2026-03-17 12:00'},
                    'has_decision': True,
                    'status': 'accepted',
                    'status_label': 'Aceptada',
                    'headline': 'La ultima decision manual registrada es aceptada sobre Plan manual A.',
                },
                'incremental_decision_executive_summary': {
                    'status': 'review_backlog',
                    'headline': 'La propuesta actual requiere validación antes de adoptar el aporte incremental.',
                    'items': [
                        {'label': 'Semáforo operativo', 'value': 'Amarillo'},
                        {'label': 'Checklist de adopción', 'value': '5/5'},
                        {'label': 'Estado ejecutivo actual', 'value': 'review_backlog'},
                        {'label': 'Frente del backlog', 'value': 'Plan guardado 1'},
                    ],
                    'has_summary': True,
                },
            },
        )

        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'resolver primero qué hacer con el aporte mensual' in body
        assert 'arrancá por `Aportes` y no necesitás recorrer el resto de la hoja' in body
        assert '1. Aportes' in body
        assert 'Aportes principal' in body
        assert 'Planeación de aportes: flujo principal' in body
        assert 'Universo patrimonial' in body
        assert 'Patrimonio total broker' in body
        assert 'Cash disponible' in body
        assert 'Cash a liquidar' in body
        assert 'Caucion colocada' in body
        assert 'Capital invertido analizado' in body
        assert 'FCI cash management' in body
        assert 'Diagnóstico previo al aporte' in body
        assert 'Señales de diagnóstico y priorización' in body
        assert 'Backlog priorizado' in body
        assert 'Alta prioridad' in body
        assert 'Recuperables' in body
        assert 'En observación' in body or 'En observaci?n' in body
        assert 'Filtrar shortlist por seguimiento' in body
        assert 'Revisar ya' in body
        assert 'En espera' in body
        assert 'Vigentes' in body
        assert 'Diferidas' in body
        assert 'Cerradas' in body
        assert 'Última revisión' in body or 'Ultima revision' in body
        assert 'Diferidas reactivables' in body
        assert 'Diferidas para archivar' in body
        assert 'Lectura de diferidas' in body
        assert 'Próxima revisión sugerida' in body or 'Pr?xima revisi?n sugerida' in body
        assert 'Revisar primero Plan guardado 1' in body
        assert 'Macro local FX + UVA:' in body
        assert 'Macro local FX/UVA' in body
        assert 'Primera acción sugerida:' in body
        assert 'Propuesta de compra mensual' in body
        assert 'Plan incremental MVP' in body
        assert 'Alta' in body
        assert 'Revisar primero Plan guardado 1' in body
        assert 'Shortlist para futuras compras' in body
        assert 'Líder económico' in body or 'Lider economico' in body
        assert 'Líder táctico' in body or 'Lider tactico' in body
        assert 'Gana por retorno' in body
        assert 'Gana por ejecutabilidad' in body
        assert 'Convicción media' in body or 'Conviccion media' in body
        assert 'Monitorear' in body
        assert 'Plan guardado 2' in body
        assert 'Tecnología / growth' in body
        assert 'Por qué este bloque recibió este score' in body
        assert 'Señales positivas' in body
        assert 'Señales negativas' in body
        assert 'Activos candidatos para construir la propuesta' in body
        assert 'Ranking incremental MVP' in body
        assert 'Modo decisión' in body
        assert 'Contexto rápido' in body
        assert 'Estado de cartera' in body
        assert 'Recomendación principal' in body
        assert 'Opciones sugeridas' in body
        assert 'Impacto estimado' in body
        assert 'Tu decisión este mes' in body
        assert 'Tenés una proporción alta de cash disponible.' in body
        assert 'Tu principal palanca hoy es asignar capital disponible.' in body
        assert 'Tenés capital disponible para invertir' in body
        assert 'Evaluar asignar entre 20% y 40% del cash.' in body
        assert 'Score: 78/100' in body
        assert 'Confianza: Alta' in body
        assert 'Por qué esta decisión' in body
        assert 'Ejecutar decisión' in body
        assert 'Explorar alternativas' in body
        assert 'KO · 150000, MCD · 150000' in body
        assert 'La propuesta mejora el perfil sin aumentar la fragilidad.' in body
        assert 'KO' in body
        assert 'Lectura sugerida del cierre:' in body
        assert 'Decisión sugerida: propuesta incremental preferida' in body
        assert 'Validación before/after del impacto incremental' in body
        assert 'La compra reduce la fragilidad del portafolio.' in body
        assert 'Expected return' in body
        assert 'Fragility' in body
        assert 'Propuesta incremental preferida' not in body
        assert 'Guardar propuesta preferida' in body
        assert 'Exploración y comparación' in body
        assert 'Orden sugerido:' in body
        assert 'Exploración' in body
        assert 'Resumen ejecutivo unificado de decisión incremental' in body
        assert 'La propuesta actual requiere validación antes de adoptar el aporte incremental.' in body
        assert 'Seguimiento y governance' in body
        assert 'Seguimiento operativo incremental' in body
        assert 'Plan baseline' in body
        assert 'La ultima decision manual registrada es aceptada sobre Plan manual A.' in body
        assert 'Historial operativo y acciones manuales' in body
        assert 'No forman parte de la lectura principal del aporte mensual.' in body
        assert 'Historial reciente de propuestas guardadas' in body
        assert 'Filtrar por decisión manual' in body
        assert 'Aceptar visibles' in body
        assert 'Diferir visibles' in body
        assert 'Rechazar visibles' in body
        assert 'Plan guardado 1' in body
        assert 'Por qué se tomó esta decisión' in body
        assert 'Se reforzó una propuesta defensiva con mejor resiliencia.' in body
        assert 'Alta' in body
        assert 'Normal' in body
        assert 'Ok' in body
        assert 'Promover a baseline' in body
        assert 'Reaplicar en comparador manual' in body
        assert 'Comparador por split' in body
        assert 'Split KO + MCD' in body
        assert 'Comparador de propuestas incrementales' in body
        assert 'Split del bloque más grande' in body
        assert 'Comparador incremental por candidato' in body
        assert 'Comparador incremental por split de bloque' in body

    def test_planeacion_mode_decision_handles_missing_preferred_and_assets(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
                'portfolio_scope_summary': {
                    'portfolio_total_broker': 0.0,
                    'invested_portfolio': 0.0,
                    'cash_management_fci': 0.0,
                    'cash_available_broker': 0.0,
                    'cash_available_broker_ars': 0.0,
                    'cash_available_broker_usd': 0.0,
                    'cash_ratio_total': 0.0,
                    'invested_ratio_total': 0.0,
                    'fci_ratio_total': 0.0,
                },
                'monthly_allocation_plan': {'recommended_blocks': [], 'avoided_blocks': [], 'explanation': ''},
                'candidate_asset_ranking': {'candidate_assets': [], 'candidate_assets_count': 0, 'by_block': {}, 'explanation': ''},
                'incremental_portfolio_simulation': {'delta': {}, 'interpretation': ''},
                'incremental_portfolio_simulation_comparison': {'proposals': []},
                'candidate_incremental_portfolio_comparison': {'comparisons': []},
                'candidate_split_incremental_portfolio_comparison': {'proposals': []},
                'manual_incremental_portfolio_simulation_comparison': {'submitted': False, 'proposals': [], 'form_state': {}},
                'preferred_incremental_portfolio_proposal': {'preferred': None, 'has_manual_override': False, 'explanation': ''},
                'decision_engine_summary': {
                    'portfolio_scope': {
                        'portfolio_total_broker': 0.0,
                        'invested_portfolio': 0.0,
                        'cash_management_fci': 0.0,
                        'cash_available_broker': 0.0,
                        'cash_ratio_total': 0.0,
                        'invested_ratio_total': 0.0,
                    },
                    'recommendation_context': None,
                    'strategy_bias': None,
                    'execution_gate': {
                        'has_blocker': False,
                        'status': 'pending',
                        'title': '',
                        'summary': '',
                        'primary_cta_label': 'Ejecutar decisión',
                        'primary_cta_tone': 'success',
                    },
                    'action_suggestions': [],
                    'macro_state': {'key': 'indefinido', 'label': 'Indefinido', 'summary': 'Falta contexto macro suficiente.'},
                    'portfolio_state': {'key': 'indefinido', 'label': 'Indefinido', 'summary': 'Falta contexto suficiente sobre la cartera.'},
                    'recommendation': {'block': None, 'amount': None, 'reason': 'Todavía no hay un bloque dominante para este corte.', 'has_recommendation': False},
                    'suggested_assets': [],
                    'preferred_proposal': None,
                    'expected_impact': {'return': None, 'fragility': None, 'worst_case': None, 'status': 'neutral', 'summary': 'Impacto incremental no disponible.'},
                    'score': 24,
                    'confidence': 'Baja',
                    'explanation': [],
                    'tracking_payload': {'purchase_plan': [], 'score': 24, 'confidence': 'Baja'},
                },
                'incremental_proposal_history': {'items': [], 'count': 0, 'has_history': False, 'active_filter': 'all', 'active_filter_label': 'Todos', 'decision_counts': {'total': 0, 'pending': 0, 'accepted': 0, 'deferred': 0, 'rejected': 0}, 'available_filters': [], 'headline': ''},
                'incremental_proposal_tracking_baseline': {'item': None, 'has_baseline': False},
                'incremental_manual_decision_summary': {'item': None, 'has_decision': False, 'status': 'pending', 'status_label': 'Pendiente', 'headline': ''},
                'incremental_decision_executive_summary': {'status': 'pending', 'headline': '', 'items': [], 'has_summary': False},
            },
        )

        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'Sin candidatos claros.' in body
        assert 'No hay propuesta dominante.' in body
        assert 'Score: 24/100' in body
        assert 'Confianza: Baja' in body
        assert 'Por qué esta decisión' not in body

    def test_planeacion_mode_decision_handles_missing_simulation_values(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
                'portfolio_scope_summary': {
                    'portfolio_total_broker': 15863589,
                    'invested_portfolio': 13330704,
                    'cash_management_fci': 2532885,
                    'cash_available_broker': 11039915.47,
                    'cash_available_broker_ars': 11039915.47,
                    'cash_available_broker_usd': 0.56,
                    'cash_ratio_total': 0.6959,
                    'invested_ratio_total': 0.8403,
                    'fci_ratio_total': 0.1597,
                },
                'monthly_allocation_plan': {'recommended_blocks': [], 'avoided_blocks': [], 'explanation': ''},
                'candidate_asset_ranking': {'candidate_assets': [], 'candidate_assets_count': 0, 'by_block': {}, 'explanation': ''},
                'incremental_portfolio_simulation': {'delta': {}, 'interpretation': ''},
                'incremental_portfolio_simulation_comparison': {'proposals': []},
                'candidate_incremental_portfolio_comparison': {'comparisons': []},
                'candidate_split_incremental_portfolio_comparison': {'proposals': []},
                'manual_incremental_portfolio_simulation_comparison': {'submitted': False, 'proposals': [], 'form_state': {}},
                'preferred_incremental_portfolio_proposal': {'preferred': {'proposal_label': 'Plan A'}, 'has_manual_override': False, 'explanation': ''},
                'decision_engine_summary': {
                    'portfolio_scope': {
                        'portfolio_total_broker': 15863589,
                        'invested_portfolio': 13330704,
                        'cash_management_fci': 2532885,
                        'cash_available_broker': 11039915.47,
                        'cash_ratio_total': 0.6959,
                        'invested_ratio_total': 0.8403,
                    },
                    'recommendation_context': 'high_cash',
                    'strategy_bias': 'deploy_cash',
                    'execution_gate': {
                        'has_blocker': False,
                        'status': 'ready',
                        'title': '',
                        'summary': '',
                        'primary_cta_label': 'Ejecutar decisión',
                        'primary_cta_tone': 'success',
                    },
                    'action_suggestions': [
                        {
                            'type': 'allocation',
                            'message': 'Tenés capital disponible para invertir',
                            'suggestion': 'Evaluar asignar entre 20% y 40% del cash.',
                        }
                    ],
                    'macro_state': {'key': 'normal', 'label': 'Normal', 'summary': 'No hay una señal macro dominante.'},
                    'portfolio_state': {'key': 'ok', 'label': 'OK', 'summary': 'La cartera admite un aporte incremental.'},
                    'recommendation': {'block': 'Defensivos USD', 'amount': 600000, 'reason': 'prioridad simple', 'has_recommendation': True, 'priority_label': 'Prioritaria', 'priority_tone': 'success', 'is_conditioned_by_parking': False},
                    'suggested_assets': [{'symbol': 'KO', 'block': 'Defensivos USD', 'score': 8.2, 'reason': 'defensive_sector_match', 'is_conditioned_by_parking': False, 'priority_label': ''}],
                    'preferred_proposal': {'proposal_label': 'Plan A', 'source_label': 'Comparador automático', 'purchase_summary': 'KO · 600000', 'purchase_plan': [{'symbol': 'KO', 'amount': 600000}], 'simulation_delta': {}, 'purchase_plan_blocks': [], 'is_conditioned_by_parking': False, 'priority_label': 'Lista', 'priority_tone': 'success', 'parking_note': ''},
                    'expected_impact': {'return': None, 'fragility': None, 'worst_case': None, 'status': 'neutral', 'summary': 'Impacto incremental no disponible.'},
                    'score': 61,
                    'confidence': 'Media',
                    'explanation': ['Se refuerza Defensivos USD porque prioridad simple.'],
                    'tracking_payload': {'purchase_plan': [{'symbol': 'KO', 'amount': 600000}], 'score': 61, 'confidence': 'Media'},
                },
                'incremental_proposal_history': {'items': [], 'count': 0, 'has_history': False, 'active_filter': 'all', 'active_filter_label': 'Todos', 'decision_counts': {'total': 0, 'pending': 0, 'accepted': 0, 'deferred': 0, 'rejected': 0}, 'available_filters': [], 'headline': ''},
                'incremental_proposal_tracking_baseline': {'item': None, 'has_baseline': False},
                'incremental_manual_decision_summary': {'item': None, 'has_decision': False, 'status': 'pending', 'status_label': 'Pendiente', 'headline': ''},
                'incremental_decision_executive_summary': {'status': 'pending', 'headline': '', 'items': [], 'has_summary': False},
            },
        )

        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'Impacto incremental no disponible.' in body
        assert 'Score: 61/100' in body
        assert 'Confianza: Media' in body
        assert 'Tenés una proporción alta de cash disponible.' in body
        assert 'Tu principal palanca hoy es asignar capital disponible.' in body
        assert 'Evaluar asignar entre 20% y 40% del cash.' in body
        assert 'KO · 600000' in body

    def test_planeacion_mode_decision_shows_parking_signal_when_present(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
                'portfolio_scope_summary': {
                    'portfolio_total_broker': 15863589,
                    'invested_portfolio': 13330704,
                    'cash_management_fci': 2532885,
                    'cash_available_broker': 11039915.47,
                    'cash_available_broker_ars': 11039915.47,
                    'cash_available_broker_usd': 0.56,
                    'cash_ratio_total': 0.6959,
                    'invested_ratio_total': 0.8403,
                    'fci_ratio_total': 0.1597,
                },
                'monthly_allocation_plan': {'recommended_blocks': [], 'avoided_blocks': [], 'explanation': ''},
                'candidate_asset_ranking': {'candidate_assets': [], 'candidate_assets_count': 0, 'by_block': {}, 'explanation': ''},
                'incremental_portfolio_simulation': {'delta': {}, 'interpretation': ''},
                'incremental_portfolio_simulation_comparison': {'proposals': []},
                'candidate_incremental_portfolio_comparison': {'comparisons': []},
                'candidate_split_incremental_portfolio_comparison': {'proposals': []},
                'manual_incremental_portfolio_simulation_comparison': {'submitted': False, 'proposals': [], 'form_state': {}},
                'preferred_incremental_portfolio_proposal': {'preferred': None, 'has_manual_override': False, 'explanation': ''},
                'decision_engine_summary': {
                    'portfolio_scope': {
                        'portfolio_total_broker': 15863589,
                        'invested_portfolio': 13330704,
                        'cash_management_fci': 2532885,
                        'cash_available_broker': 11039915.47,
                        'cash_ratio_total': 0.6959,
                        'invested_ratio_total': 0.8403,
                    },
                    'recommendation_context': 'high_cash',
                    'strategy_bias': 'deploy_cash',
                    'parking_signal': {
                        'has_signal': True,
                        'title': 'Parking visible antes de reforzar',
                        'summary': 'Hay 2 posicion(es) con parking visible por 450000.00.',
                    },
                    'execution_gate': {
                        'has_blocker': True,
                        'status': 'review_parking',
                        'title': 'Revisar restricciones antes de ejecutar',
                        'summary': 'La propuesta puede seguir siendo valida, pero conviene revisar primero el parking visible antes de desplegar mas capital.',
                        'primary_cta_label': 'Revisar antes de ejecutar',
                        'primary_cta_tone': 'warning',
                    },
                    'action_suggestions': [
                        {
                            'type': 'allocation',
                            'message': 'Tenés capital disponible para invertir',
                            'suggestion': 'Evaluar asignar entre 20% y 40% del cash.',
                        },
                        {
                            'type': 'parking',
                            'message': 'Hay posiciones con parking visible en cartera',
                            'suggestion': 'Conviene revisar esas restricciones antes de reforzar la misma zona de exposicion.',
                        },
                    ],
                    'macro_state': {'key': 'normal', 'label': 'Normal', 'summary': 'No hay una señal macro dominante.'},
                    'portfolio_state': {'key': 'ok', 'label': 'OK', 'summary': 'La cartera admite un aporte incremental.'},
                    'recommendation': {
                        'block': 'Defensive / resiliente',
                        'amount': 600000,
                        'reason': 'Se prioriza resiliencia. Hay parking visible dentro de este mismo bloque y conviene revisar la restriccion antes de ejecutar.',
                        'has_recommendation': True,
                        'priority_label': 'Condicionada',
                        'priority_tone': 'warning',
                        'is_conditioned_by_parking': True,
                    },
                    'suggested_assets': [
                        {
                            'symbol': 'KO',
                            'block': 'Defensive / resiliente',
                            'score': 8.2,
                            'reason': 'defensive_sector_match',
                            'is_conditioned_by_parking': True,
                            'priority_label': 'Condicionado por parking',
                        }
                    ],
                    'preferred_proposal': {
                        'proposal_label': 'Plan SPY',
                        'source_label': 'Comparador por candidato',
                        'purchase_summary': 'SPY · 600000',
                        'purchase_plan': [{'symbol': 'SPY', 'amount': 600000}],
                        'simulation_delta': {},
                        'purchase_plan_blocks': ['Indice global'],
                        'is_conditioned_by_parking': False,
                        'priority_label': 'Repriorizada por parking',
                        'priority_tone': 'info',
                        'parking_note': 'Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con parking visible.',
                        'was_reprioritized_by_parking': True,
                    },
                    'expected_impact': {'return': None, 'fragility': None, 'worst_case': None, 'status': 'neutral', 'summary': 'Impacto incremental no disponible.'},
                    'score': 61,
                    'confidence': 'Media',
                    'explanation': ['Primero revisar restricciones operativas antes de desplegar más capital.'],
                    'tracking_payload': {'purchase_plan': [], 'score': 61, 'confidence': 'Media'},
                },
                'incremental_proposal_history': {'items': [], 'count': 0, 'has_history': False, 'active_filter': 'all', 'active_filter_label': 'Todos', 'decision_counts': {'total': 0, 'pending': 0, 'accepted': 0, 'deferred': 0, 'rejected': 0}, 'available_filters': [], 'headline': ''},
                'incremental_proposal_tracking_baseline': {'item': None, 'has_baseline': False},
                'incremental_manual_decision_summary': {'item': None, 'has_decision': False, 'status': 'pending', 'status_label': 'Pendiente', 'headline': ''},
                'incremental_decision_executive_summary': {'status': 'pending', 'headline': '', 'items': [], 'has_summary': False},
            },
        )

        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'Parking visible antes de reforzar' in body
        assert 'Hay 2 posicion(es) con parking visible por 450000.00.' in body
        assert 'Hay posiciones con parking visible en cartera' in body
        assert 'Conviene revisar esas restricciones antes de reforzar la misma zona de exposicion.' in body
        assert 'Condicionada' in body
        assert 'Defensive / resiliente' in body
        assert 'Hay parking visible dentro de este mismo bloque' in body
        assert 'Condicionado por parking' in body
        assert 'Conviene revisar parking visible en este bloque antes de usarlo como candidato principal.' in body
        assert 'Repriorizada por parking' in body
        assert 'Plan SPY' in body
        assert 'Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con parking visible.' in body
        assert 'Revisar restricciones antes de ejecutar' in body
        assert 'Revisar antes de ejecutar' in body

    def test_planeacion_mode_decision_shows_market_history_conditioning_when_present(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
                'portfolio_scope_summary': {
                    'portfolio_total_broker': 15863589,
                    'invested_portfolio': 13330704,
                    'cash_management_fci': 2532885,
                    'cash_available_broker': 11039915.47,
                    'cash_available_broker_ars': 11039915.47,
                    'cash_available_broker_usd': 0.56,
                    'cash_ratio_total': 0.6959,
                    'invested_ratio_total': 0.8403,
                    'fci_ratio_total': 0.1597,
                },
                'monthly_allocation_plan': {'recommended_blocks': [], 'avoided_blocks': [], 'explanation': ''},
                'candidate_asset_ranking': {'candidate_assets': [], 'candidate_assets_count': 0, 'by_block': {}, 'explanation': ''},
                'incremental_portfolio_simulation': {'delta': {}, 'interpretation': ''},
                'incremental_portfolio_simulation_comparison': {'proposals': []},
                'candidate_incremental_portfolio_comparison': {'comparisons': []},
                'candidate_split_incremental_portfolio_comparison': {'proposals': []},
                'manual_incremental_portfolio_simulation_comparison': {'submitted': False, 'proposals': [], 'form_state': {}},
                'preferred_incremental_portfolio_proposal': {'preferred': None, 'has_manual_override': False, 'explanation': ''},
                'decision_engine_summary': {
                    'portfolio_scope': {
                        'portfolio_total_broker': 15863589,
                        'invested_portfolio': 13330704,
                        'cash_management_fci': 2532885,
                        'cash_available_broker': 11039915.47,
                        'cash_ratio_total': 0.6959,
                        'invested_ratio_total': 0.8403,
                    },
                    'recommendation_context': 'high_cash',
                    'strategy_bias': 'deploy_cash',
                    'parking_signal': {'has_signal': False, 'title': '', 'summary': ''},
                    'market_history_signal': {
                        'has_signal': True,
                        'title': 'Liquidez reciente debil en la zona sugerida',
                        'summary': 'El bloque sugerido viene con liquidez reciente debil en Growth USA. Revisar spread y actividad reciente en MELI antes de comprar.',
                    },
                    'execution_gate': {
                        'has_blocker': False,
                        'status': 'ready',
                        'title': '',
                        'summary': '',
                        'primary_cta_label': 'Ejecutar decisión',
                        'primary_cta_tone': 'success',
                    },
                    'action_suggestions': [
                        {
                            'type': 'allocation',
                            'message': 'Tenés capital disponible para invertir',
                            'suggestion': 'Evaluar asignar entre 20% y 40% del cash.',
                        },
                        {
                            'type': 'market_history',
                            'message': 'La liquidez reciente del bloque sugerido viene debil',
                            'suggestion': 'Conviene priorizar compras en zonas con mejor spread y actividad reciente o esperar un punto de entrada mas limpio.',
                        },
                    ],
                    'macro_state': {'key': 'normal', 'label': 'Normal', 'summary': 'No hay una señal macro dominante.'},
                    'portfolio_state': {'key': 'ok', 'label': 'OK', 'summary': 'La cartera admite un aporte incremental.'},
                    'recommendation': {
                        'block': 'Indice global',
                        'amount': 250000,
                        'reason': 'Se prioriza Indice global porque el bloque original Growth USA viene con liquidez reciente debil. Mantiene beta amplia y liquidez mas limpia.',
                        'has_recommendation': True,
                        'priority_label': 'Repriorizada por liquidez reciente',
                        'priority_tone': 'warning',
                        'is_conditioned_by_parking': False,
                        'is_conditioned_by_market_history': False,
                        'was_reprioritized_by_market_history': True,
                        'original_block_label': 'Growth USA',
                    },
                    'suggested_assets': [
                        {
                            'symbol': 'MELI',
                            'block': 'Growth USA',
                            'score': 8.2,
                            'reason': 'growth_quality',
                            'is_conditioned_by_parking': False,
                            'is_conditioned_by_market_history': True,
                            'priority_label': 'Condicionado por liquidez reciente',
                            'market_history_note': 'La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de usarlo como candidato principal.',
                        }
                    ],
                    'preferred_proposal': {
                        'proposal_label': 'Plan SPY',
                        'source_label': 'Comparador automático',
                        'purchase_summary': 'SPY · 600000',
                        'purchase_plan': [{'symbol': 'SPY', 'amount': 600000}],
                        'simulation_delta': {},
                        'purchase_plan_blocks': ['Indice global'],
                        'is_conditioned_by_parking': False,
                        'is_conditioned_by_market_history': False,
                        'priority_label': 'Repriorizada por liquidez reciente',
                        'priority_tone': 'info',
                        'parking_note': 'Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con liquidez reciente debil.',
                        'was_reprioritized_by_parking': False,
                        'was_reprioritized_by_market_history': True,
                    },
                    'expected_impact': {'return': None, 'fragility': None, 'worst_case': None, 'status': 'neutral', 'summary': 'Impacto incremental no disponible.'},
                    'score': 57,
                    'confidence': 'Baja',
                    'explanation': ['Revisar friccion operativa reciente antes de desplegar mas capital.'],
                    'tracking_payload': {'purchase_plan': [], 'score': 57, 'confidence': 'Baja'},
                },
                'incremental_proposal_history': {'items': [], 'count': 0, 'has_history': False, 'active_filter': 'all', 'active_filter_label': 'Todos', 'decision_counts': {'total': 0, 'pending': 0, 'accepted': 0, 'deferred': 0, 'rejected': 0}, 'available_filters': [], 'headline': ''},
                'incremental_proposal_tracking_baseline': {'item': None, 'has_baseline': False},
                'incremental_manual_decision_summary': {'item': None, 'has_decision': False, 'status': 'pending', 'status_label': 'Pendiente', 'headline': ''},
                'incremental_decision_executive_summary': {'status': 'pending', 'headline': '', 'items': [], 'has_summary': False},
            },
        )

        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'Liquidez reciente debil en la zona sugerida' in body
        assert 'La liquidez reciente del bloque sugerido viene debil' in body
        assert 'Repriorizada por liquidez reciente' in body
        assert 'Growth USA viene con liquidez reciente debil' in body
        assert 'Condicionado por liquidez reciente' in body
        assert 'Plan SPY' in body
        assert 'Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con liquidez reciente debil.' in body
        assert 'Score: 57/100' in body
        assert 'Confianza: Baja' in body

    def test_planeacion_history_supports_old_snapshots_without_decision_fields(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
                'portfolio_scope_summary': {
                    'portfolio_total_broker': 15863589,
                    'invested_portfolio': 13330704,
                    'cash_management_fci': 2532885,
                    'cash_available_broker': 11039915.47,
                    'cash_available_broker_ars': 11039915.47,
                    'cash_available_broker_usd': 0.56,
                    'cash_ratio_total': 0.6959,
                    'invested_ratio_total': 0.8403,
                    'fci_ratio_total': 0.1597,
                },
                'monthly_allocation_plan': {'recommended_blocks': [], 'avoided_blocks': [], 'explanation': ''},
                'candidate_asset_ranking': {'candidate_assets': [], 'candidate_assets_count': 0, 'by_block': {}, 'explanation': ''},
                'incremental_portfolio_simulation': {'delta': {}, 'interpretation': ''},
                'incremental_portfolio_simulation_comparison': {'proposals': []},
                'candidate_incremental_portfolio_comparison': {'comparisons': []},
                'candidate_split_incremental_portfolio_comparison': {'proposals': []},
                'manual_incremental_portfolio_simulation_comparison': {'submitted': False, 'proposals': [], 'form_state': {}},
                'preferred_incremental_portfolio_proposal': {'preferred': None, 'has_manual_override': False, 'explanation': ''},
                'decision_engine_summary': {
                    'portfolio_scope': {
                        'portfolio_total_broker': 15863589,
                        'invested_portfolio': 15000000.0,
                        'cash_management_fci': 300000.0,
                        'cash_available_broker': 100000.0,
                        'cash_ratio_total': 0.006,
                        'invested_ratio_total': 0.945,
                    },
                    'recommendation_context': 'fully_invested',
                    'strategy_bias': 'rebalance',
                    'execution_gate': {
                        'has_blocker': False,
                        'status': 'pending',
                        'title': '',
                        'summary': '',
                        'primary_cta_label': 'Ejecutar decisión',
                        'primary_cta_tone': 'success',
                    },
                    'action_suggestions': [
                        {
                            'type': 'rebalance',
                            'message': 'Cartera altamente invertida',
                            'suggestion': 'Evaluar reducción de concentración en top posiciones.',
                        }
                    ],
                    'macro_state': {'key': 'indefinido', 'label': 'Indefinido', 'summary': 'Falta contexto macro suficiente.'},
                    'portfolio_state': {'key': 'indefinido', 'label': 'Indefinido', 'summary': 'Falta contexto suficiente sobre la cartera.'},
                    'recommendation': {'block': None, 'amount': None, 'reason': 'Todavía no hay un bloque dominante para este corte.', 'has_recommendation': False},
                    'suggested_assets': [],
                    'preferred_proposal': None,
                    'expected_impact': {'return': None, 'fragility': None, 'worst_case': None, 'status': 'neutral', 'summary': 'Impacto incremental no disponible.'},
                    'score': 24,
                    'confidence': 'Baja',
                    'explanation': [],
                    'tracking_payload': {'purchase_plan': [], 'score': 24, 'confidence': 'Baja'},
                },
                'incremental_proposal_history': {
                    'items': [{
                        'id': 1,
                        'proposal_label': 'Plan viejo',
                        'source_label': 'Comparador manual',
                        'selected_context': '',
                        'purchase_plan': [{'symbol': 'KO', 'amount': 300000}],
                        'simulation_delta': {'expected_return_change': 0.4, 'fragility_change': -1.5, 'scenario_loss_change': 0.3},
                        'manual_decision_status': 'pending',
                        'manual_decision_status_label': 'Pendiente',
                        'tactical_trace': {
                            'has_trace': True,
                            'headline': 'Se promovio una alternativa mas limpia por liquidez reciente.',
                            'badges': [
                                {'key': 'market_history', 'label': 'Liquidez reciente', 'tone': 'info'},
                                {'key': 'alternative_promoted', 'label': 'Alternativa promovida', 'tone': 'primary'},
                            ],
                            'reasons': ['La propuesta preferida fue reemplazada por una alternativa con liquidez reciente mas limpia frente a Plan MELI.'],
                        },
                        'baseline_trace': {
                            'has_trace': True,
                            'headline': 'Supera al baseline en rentabilidad esperada y balance global.',
                            'badges': [
                                {'label': 'Mejor que baseline', 'tone': 'success'},
                                {'label': 'Mejor retorno', 'tone': 'success'},
                                {'label': 'Menor fragilidad', 'tone': 'info'},
                                {'label': 'Mas ejecutable tacticamente', 'tone': 'primary'},
                            ],
                            'metrics': [
                                'Mejora retorno esperado vs baseline.',
                                'Reduce fragilidad vs baseline.',
                                'Mejora peor escenario vs baseline.',
                                'La propuesta incorpora gobierno tactico explicito frente a friccion de ejecucion.',
                            ],
                        },
                        'is_backlog_front': False,
                        'is_tracking_baseline': False,
                        'reapply_querystring': 'manual_capital_amount=300000&manual_a_symbol_1=KO&manual_a_amount_1=300000',
                        'reapply_truncated': False,
                        'created_at': '2026-03-17 11:00',
                    }],
                    'count': 1,
                    'has_history': True,
                    'active_filter': 'all',
                    'active_filter_label': 'Todos',
                    'active_priority_filter': 'all',
                    'active_priority_filter_label': 'Todas las prioridades',
                    'active_sort_mode': 'newest',
                    'active_sort_mode_label': 'Más recientes',
                    'decision_counts': {'total': 1, 'pending': 1, 'accepted': 0, 'deferred': 0, 'rejected': 0},
                    'available_filters': [{'key': 'all', 'label': 'Todos', 'count': 1, 'selected': True}],
                    'available_priority_filters': [{'key': 'all', 'label': 'Todas las prioridades', 'count': 1, 'selected': True}],
                    'available_sort_modes': [{'key': 'newest', 'label': 'Más recientes', 'selected': True}, {'key': 'priority', 'label': 'Prioridad operativa', 'selected': False}],
                    'headline': 'Se muestran 1 snapshots recientes sobre un total de 1 propuestas guardadas.',
                },
                'incremental_proposal_tracking_baseline': {'item': None, 'has_baseline': False},
                'incremental_manual_decision_summary': {'item': None, 'has_decision': False, 'status': 'pending', 'status_label': 'Pendiente', 'headline': ''},
                'incremental_decision_executive_summary': {'status': 'pending', 'headline': '', 'items': [], 'has_summary': False},
            },
        )

        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'Plan viejo' in body
        assert 'Tu cartera está altamente invertida.' in body
        assert 'Tu foco está en optimizar una cartera ya desplegada.' in body
        assert 'Cartera altamente invertida' in body
        assert 'Evaluar reducción de concentración en top posiciones.' in body
        assert 'Por qué se tomó esta decisión' not in body
        assert 'Se promovio una alternativa mas limpia por liquidez reciente.' in body
        assert 'Liquidez reciente' in body
        assert 'Alternativa promovida' in body
        assert 'Supera al baseline en rentabilidad esperada y balance global.' in body
        assert 'Mejor que baseline' in body
        assert 'Mejor retorno' in body
        assert 'Reaplicar en comparador manual' in body
        assert 'Comparador manual de planes incrementales' in body
        assert 'Herramienta secundaria: plan mensual por perfil' in body
        assert 'Plan mensual por perfil' in body
        assert 'Generar plan de contraste' in body
        assert 'Simulación táctica' in body
        assert 'Optimización teórica' in body
        assert 'Configuración base' in body
        assert 'Checklist de adopción de propuesta incremental' not in body
        assert 'Workflow de decisión manual' not in body
        assert 'Resumen ejecutivo de seguimiento incremental' not in body
        assert 'Baseline incremental de seguimiento' not in body
        assert 'Semaforización operativa del backlog incremental' not in body
        assert 'Resumen operativo del frente de backlog y baseline' not in body
        assert 'Drift vs propuesta preferida actual' not in body
        assert 'Backlog pendiente vs baseline activo' not in body
        assert 'Priorización operativa del backlog incremental' not in body
        assert 'Alertas de drift' not in body
        assert 'Snapshot guardado vs propuesta actual' not in body

    def test_planeacion_accepts_reapplied_snapshot_query_in_manual_comparator(self, auth_client):
        response = auth_client.get(
            reverse('dashboard:planeacion'),
            {
                'manual_compare': '1',
                'plan_a_capital': '600000',
                'plan_a_symbol_1': 'KO',
                'plan_a_amount_1': '300000',
                'plan_a_symbol_2': 'MCD',
                'plan_a_amount_2': '300000',
            },
        )

        body = response.content.decode()
        assert response.status_code == 200
        assert 'value="KO"' in body
        assert 'value="MCD"' in body
        assert 'value="600000"' in body

    def test_performance_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:performance')
        response = auth_client.get(url)
        assert response.status_code == 200
        body = response.content.decode()
        assert 'performance-fallback-wrap' in body
        assert 'Trazabilidad de fallback activa.' in body
        assert 'Históricos IOL proxy' in body or 'Historicos IOL proxy' in body
        assert 'Obs:' in body
        assert 'Span:' in body
        assert 'Cobertura:' in body
        assert 'formatCoverageNote' in body

    def test_metricas_route_accessible_authenticated(self, auth_client):
        url = reverse('dashboard:metricas')
        response = auth_client.get(url)
        assert response.status_code == 200
        body = response.content.decode()
        assert 'Fallback activo:' in body
        assert 'Fallback retornos' in body
        assert 'Fallback volatilidad' in body
        assert 'Fallback benchmarking' in body

    def test_ops_requires_staff(self, auth_client, staff_client):
        url = reverse('dashboard:ops')
        denied = auth_client.get(url)
        assert denied.status_code == 403
        allowed = staff_client.get(url)
        assert allowed.status_code == 200
        assert 'Estado de benchmarks históricos' in allowed.content.decode()
        assert 'Estado de macro local' in allowed.content.decode()
        assert 'Series macro críticas para decisión' in allowed.content.decode()
        assert 'Estado de fuentes externas' in allowed.content.decode()
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

    def test_ops_shows_unified_pipeline_summary(self, staff_client, monkeypatch):
        class DummyPipelineObservabilityService:
            def build_summary(self, lookback_days=30, integrity_days=120):
                assert lookback_days == 30
                assert integrity_days == 120
                return {
                    'last_successful_iol_sync': '2026-03-17 10:00',
                    'iol_sync_status': 'ok',
                    'latest_asset_snapshot_at': '2026-03-17 10:00',
                    'latest_account_snapshot_at': '2026-03-17 10:00',
                    'latest_portfolio_snapshot_date': '2026-03-17',
                    'days_since_last_portfolio_snapshot': 0,
                    'covariance_readiness': {
                        'status': 'ready',
                        'label': 'Listo para covarianza',
                        'minimum_required': 20,
                    },
                    'usable_observations_count': 21,
                    'available_price_dates_count': 28,
                    'benchmark_status_summary': {
                        'ready_count': 2,
                        'total_series': 3,
                        'overall_status': 'partial',
                    },
                    'iol_historical_price_summary': {
                        'ready_count': 1,
                        'partial_count': 1,
                        'missing_count': 1,
                        'unsupported_count': 2,
                        'unsupported_fci_count': 1,
                        'unsupported_other_count': 1,
                        'total_symbols': 5,
                        'overall_status': 'partial',
                    },
                    'iol_historical_price_symbol_groups': {
                        'ready': ['GGAL (BCBA)'],
                        'partial': ['AAPL (NASDAQ)'],
                        'missing': ['MSFT (NASDAQ)'],
                        'unsupported': ['ADBAICA (BCBA)', 'CAUCION (BCBA)'],
                        'unsupported_fci': ['ADBAICA (BCBA)'],
                        'unsupported_other': ['CAUCION (BCBA)'],
                    },
                    'iol_historical_exclusion_rows': [
                        {
                            'reason_key': 'fci_confirmed_by_iol',
                            'reason_label': 'FCI confirmado por IOL',
                            'reason_text': 'Instrumento confirmado por IOL como FCI; no usa seriehistorica de títulos',
                            'count': 1,
                            'symbols': ['ADBAICA (BCBA)'],
                        },
                        {
                            'reason_key': 'caucion_not_title_series',
                            'reason_label': 'Caución sin serie histórica de título',
                            'reason_text': 'La caución no expone serie histórica de cotización como un título estándar',
                            'count': 1,
                            'symbols': ['CAUCION (BCBA)'],
                        },
                    ],
                    'iol_historical_recent_sync_rows': [
                        {
                            'action_label': 'Sync faltantes',
                            'user_label': 'staffuser',
                            'scope': 'missing',
                            'symbol_key': 'NASDAQ:AAPL',
                            'rows_received': 30,
                            'status': 'success',
                            'created_at': '2026-03-17 10:00',
                            'message': '',
                        },
                        {
                            'action_label': 'Reforzar parciales',
                            'user_label': 'staffuser',
                            'scope': 'partial',
                            'symbol_key': 'BCBA:GGAL',
                            'rows_received': 12,
                            'status': 'success',
                            'created_at': '2026-03-17 10:05',
                            'message': '',
                        },
                        {
                            'action_label': 'Reintentar metadata',
                            'user_label': 'staffuser',
                            'scope': 'metadata',
                            'symbol_key': 'NASDAQ:MSFT',
                            'rows_received': 18,
                            'status': 'success',
                            'created_at': '2026-03-17 10:10',
                            'message': '',
                        },
                        {
                            'action_label': 'Reintentar metadata',
                            'user_label': 'staffuser',
                            'scope': 'metadata',
                            'symbol_key': 'NASDAQ:AAPL',
                            'rows_received': 7,
                            'status': 'success',
                            'created_at': '2026-03-17 10:12',
                            'message': '',
                        },
                        {
                            'action_label': 'Reforzar parciales',
                            'user_label': 'staffuser',
                            'scope': 'partial',
                            'symbol_key': 'NYSE:KO',
                            'rows_received': 0,
                            'status': 'failed',
                            'created_at': '2026-03-17 10:15',
                            'message': 'provider timeout',
                        },
                    ],
                    'iol_historical_recent_sync_by_symbol': [
                        {
                            'symbol_key': 'NYSE:KO',
                            'user_labels': ['staffuser'],
                            'latest_at': '2026-03-17 10:15',
                            'priority_key': 'critical',
                            'priority_label': 'Atención inmediata',
                            'priority_badge': 'danger',
                            'items': [
                                {'scope': 'partial', 'action_label': 'Reforzar parciales', 'rows_received': 0, 'status': 'failed', 'created_at': '2026-03-17 10:15', 'message': 'provider timeout'},
                            ],
                        },
                        {
                            'symbol_key': 'NASDAQ:AAPL',
                            'user_labels': ['staffuser'],
                            'latest_at': '2026-03-17 10:12',
                            'priority_key': 'recoverable',
                            'priority_label': 'Recuperable',
                            'priority_badge': 'warning',
                            'items': [
                                {'scope': 'missing', 'action_label': 'Sync faltantes', 'rows_received': 30, 'status': 'success', 'created_at': '2026-03-17 10:00', 'message': ''},
                                {'scope': 'metadata', 'action_label': 'Reintentar metadata', 'rows_received': 7, 'status': 'success', 'created_at': '2026-03-17 10:12', 'message': ''},
                            ],
                        },
                        {
                            'symbol_key': 'BCBA:GGAL',
                            'user_labels': ['staffuser'],
                            'latest_at': '2026-03-17 10:05',
                            'priority_key': 'stable',
                            'priority_label': 'Estable',
                            'priority_badge': 'success',
                            'items': [
                                {'scope': 'partial', 'action_label': 'Reforzar parciales', 'rows_received': 12, 'status': 'success', 'created_at': '2026-03-17 10:05', 'message': ''},
                            ],
                        },
                    ],
                    'iol_historical_recent_sync_priority_groups': {
                        'critical': [
                            {
                                'symbol_key': 'NYSE:KO',
                                'user_labels': ['staffuser'],
                                'latest_at': '2026-03-17 10:15',
                                'priority_key': 'critical',
                                'priority_label': 'Atención inmediata',
                                'priority_badge': 'danger',
                                'items': [
                                    {'scope': 'partial', 'action_label': 'Reforzar parciales', 'rows_received': 0, 'status': 'failed', 'created_at': '2026-03-17 10:15', 'message': 'provider timeout'},
                                ],
                            },
                        ],
                        'recoverable': [
                            {
                                'symbol_key': 'NASDAQ:AAPL',
                                'user_labels': ['staffuser'],
                                'latest_at': '2026-03-17 10:12',
                                'priority_key': 'recoverable',
                                'priority_label': 'Recuperable',
                                'priority_badge': 'warning',
                                'items': [
                                    {'scope': 'missing', 'action_label': 'Sync faltantes', 'rows_received': 30, 'status': 'success', 'created_at': '2026-03-17 10:00', 'message': ''},
                                    {'scope': 'metadata', 'action_label': 'Reintentar metadata', 'rows_received': 7, 'status': 'success', 'created_at': '2026-03-17 10:12', 'message': ''},
                                ],
                            },
                        ],
                        'stable': [
                            {
                                'symbol_key': 'BCBA:GGAL',
                                'user_labels': ['staffuser'],
                                'latest_at': '2026-03-17 10:05',
                                'priority_key': 'stable',
                                'priority_label': 'Estable',
                                'priority_badge': 'success',
                                'items': [
                                    {'scope': 'partial', 'action_label': 'Reforzar parciales', 'rows_received': 12, 'status': 'success', 'created_at': '2026-03-17 10:05', 'message': ''},
                                ],
                            },
                        ],
                    },
                    'iol_historical_ops_cta': {
                        'level': 'danger',
                        'title': 'Atención inmediata en históricos IOL',
                        'message': 'Hay sincronizaciones fallidas. Conviene revisar el detalle antes de seguir reforzando cobertura.',
                        'action_hint': 'Priorizá revisión manual de los símbolos fallidos y luego reintentá el flujo correspondiente.',
                        'symbol_keys': ['NYSE:KO'],
                    },
                    'local_macro_status_summary': {
                        'ready': 3,
                        'total_series': 4,
                        'stale': 1,
                        'missing': 0,
                        'not_configured': 1,
                        'overall_status': 'warning',
                    },
                    'critical_local_macro_summary': {
                        'ready_count': 4,
                        'total_series': 7,
                        'attention_count': 3,
                        'overall_status': 'warning',
                    },
                    'external_sources_status_summary': {
                        'ready_count': 1,
                        'total_sources': 1,
                        'failed_count': 0,
                        'overall_status': 'ready',
                    },
                    'snapshot_integrity_issues_count': 2,
                    'required_periodic_tasks': [],
                    'benchmark_status_rows': [],
                    'iol_historical_price_rows': [
                        {
                            'simbolo': 'GGAL',
                            'mercado': 'BCBA',
                            'rows_count': 12,
                            'latest_date': '2026-03-17',
                            'status': 'ready',
                            'eligibility_source_key': 'title_metadata',
                            'eligibility_source_label': 'Metadata de título',
                        },
                        {
                            'simbolo': 'AAPL',
                            'mercado': 'NASDAQ',
                            'rows_count': 3,
                            'latest_date': '2026-03-17',
                            'status': 'partial',
                            'eligibility_source_key': 'market_snapshot',
                            'eligibility_source_label': 'Market snapshot',
                        },
                        {
                            'simbolo': 'MSFT',
                            'mercado': 'NASDAQ',
                            'rows_count': 0,
                            'latest_date': None,
                            'status': 'missing',
                            'eligibility_source_key': 'market_snapshot',
                            'eligibility_source_label': 'Market snapshot',
                        },
                        {
                            'simbolo': 'ADBAICA',
                            'mercado': 'BCBA',
                            'rows_count': 0,
                            'latest_date': None,
                            'status': 'unsupported',
                            'eligibility_status': 'unsupported_fci',
                            'eligibility_reason_key': 'fci_confirmed_by_iol',
                            'eligibility_reason': 'Instrumento confirmado por IOL como FCI; no usa seriehistorica de títulos',
                            'eligibility_source_key': 'fci_confirmation',
                            'eligibility_source_label': 'Confirmación FCI',
                        },
                        {
                            'simbolo': 'CAUCION',
                            'mercado': 'BCBA',
                            'rows_count': 0,
                            'latest_date': None,
                            'status': 'unsupported',
                            'eligibility_status': 'unsupported',
                            'eligibility_reason_key': 'caucion_not_title_series',
                            'eligibility_reason': 'La caución no expone serie histórica de cotización como un título estándar',
                            'eligibility_source_key': 'local_classification',
                            'eligibility_source_label': 'Clasificación local',
                        },
                    ],
                    'iol_market_snapshot_summary': {
                        'total_symbols': 3,
                        'available_count': 1,
                        'missing_count': 1,
                        'unsupported_count': 1,
                        'detail_count': 1,
                        'fallback_count': 0,
                        'order_book_count': 1,
                        'overall_status': 'partial',
                    },
                    'iol_market_snapshot_rows': [
                        {
                            'simbolo': 'GGAL',
                            'mercado': 'bcba',
                            'descripcion': 'Grupo Financiero Galicia',
                            'tipo': 'acciones',
                            'snapshot_status': 'available',
                            'snapshot_source_key': 'cotizacion_detalle',
                            'snapshot_source_label': 'CotizacionDetalle',
                            'snapshot_reason': '',
                            'fecha_hora_label': '2026-03-20 16:59',
                            'ultimo_precio': 1000,
                            'variacion': 1.5,
                            'cantidad_operaciones': 321,
                            'puntas_count': 1,
                            'spread_abs': 5,
                        },
                        {
                            'simbolo': 'AAPL',
                            'mercado': 'NASDAQ',
                            'descripcion': 'Apple Inc.',
                            'tipo': 'acciones',
                            'snapshot_status': 'missing',
                            'snapshot_source_key': '',
                            'snapshot_source_label': '',
                            'snapshot_reason': 'IOL no devolvio cotizacion puntual para el instrumento.',
                            'fecha_hora_label': '',
                            'ultimo_precio': None,
                            'variacion': None,
                            'cantidad_operaciones': 0,
                            'puntas_count': 0,
                            'spread_abs': None,
                        },
                        {
                            'simbolo': 'ADBAICA',
                            'mercado': 'BCBA',
                            'descripcion': 'Adcap Cobertura',
                            'tipo': 'FondoComundeInversion',
                            'snapshot_status': 'unsupported',
                            'snapshot_source_key': 'local_classification',
                            'snapshot_source_label': 'Clasificacion local',
                            'snapshot_reason': 'FCI y cash management usan un pipeline distinto al de titulos',
                            'fecha_hora_label': '',
                            'ultimo_precio': None,
                            'variacion': None,
                            'cantidad_operaciones': 0,
                            'puntas_count': 0,
                            'spread_abs': None,
                        },
                    ],
                    'local_macro_status_rows': [],
                    'critical_local_macro_rows': [
                        {
                            'label': 'USDARS MEP',
                            'why': 'referencia financiera local',
                            'source': 'ArgentinaDatos',
                            'rows_count': 180,
                            'latest_date': '2026-03-17',
                            'status': 'ready',
                        },
                        {
                            'label': 'UVA',
                            'why': 'proxy de CER e inflacion indexada',
                            'source': 'ArgentinaDatos',
                            'rows_count': 0,
                            'latest_date': None,
                            'status': 'missing',
                        },
                    ],
                    'external_source_status_rows': [
                        {
                            'label': 'ArgentinaDatos',
                            'endpoint': '/v1/estado',
                            'reported_status': 'ok',
                            'detail': 'healthy',
                            'is_ready': True,
                        }
                    ],
                }

        monkeypatch.setattr(
            'apps.dashboard.views.PipelineObservabilityService',
            lambda: DummyPipelineObservabilityService(),
        )
        response = staff_client.get(reverse('dashboard:ops'))
        body = response.content.decode()
        assert response.status_code == 200
        assert 'Resumen unificado del pipeline' in body
        assert 'Último sync IOL exitoso' in body
        assert '2026-03-17 10:00' in body
        assert 'Último portfolio snapshot' in body
        assert '2026-03-17' in body
        assert 'Covariance readiness' in body
        assert '21/20 obs' in body
        assert 'Resumen benchmarks' in body
        assert '2/3' in body
        assert 'Históricos IOL por símbolo' in body
        assert '1/5 listos' in body
        assert 'Market snapshot IOL' in body
        assert '1/3 disponibles' in body
        assert 'Market snapshot puntual del portfolio' in body
        assert 'CotizacionDetalle' in body
        assert 'IOL no devolvio cotizacion puntual para el instrumento.' in body
        assert 'Símbolos cubiertos y faltantes del proxy IOL' in body or 'Simbolos cubiertos y faltantes del proxy IOL' in body
        assert 'GGAL (BCBA)' in body
        assert 'AAPL (NASDAQ)' in body
        assert 'MSFT (NASDAQ)' in body
        assert 'ADBAICA (BCBA)' in body
        assert 'CAUCION (BCBA)' in body
        assert 'No elegibles' in body
        assert 'FCI: 1 · Otros: 1' in body or 'FCI: 1' in body
        assert 'Historial IOL agrupado por símbolo' in body or 'Historial IOL agrupado por simbolo' in body
        assert 'Atención inmediata en históricos IOL' in body or 'Atencion inmediata en historicos IOL' in body
        assert 'Priorizá revisión manual de los símbolos fallidos' in body or 'Prioriza revision manual de los simbolos fallidos' in body
        assert 'Ordenado por severidad y recuperabilidad' in body
        assert 'Atención inmediata (1)' in body or 'Atencion inmediata (1)' in body
        assert 'Recuperable (1)' in body
        assert 'Estable (1)' in body
        assert 'Última ejecución IOL por símbolo' in body or 'Ultima ejecucion IOL por simbolo' in body
        assert 'Sync faltantes' in body
        assert 'Reforzar parciales' in body
        assert 'Reintentar metadata' in body
        assert 'Atención inmediata' in body or 'Atencion inmediata' in body
        assert 'Recuperable' in body
        assert 'Estable' in body
        assert 'Fallido' in body
        assert 'Exitoso' in body
        assert 'Flujos' in body
        assert 'Filas' in body
        assert 'staffuser' in body
        assert 'NASDAQ:AAPL' in body
        assert 'BCBA:GGAL' in body
        assert 'NASDAQ:MSFT' in body
        assert 'NYSE:KO' in body
        assert '7' in body
        assert 'Cobertura de históricos IOL por símbolo' in body
        assert 'Motivos exactos de exclusión IOL por símbolo' in body or 'Motivos exactos de exclusion IOL por simbolo' in body
        assert 'FCI confirmado por IOL' in body
        assert 'Caución sin serie histórica de título' in body or 'Caucion sin serie historica de titulo' in body
        assert 'GGAL' in body
        assert 'NASDAQ' in body
        assert 'Parcial' in body
        assert 'Sin historia' in body
        assert 'No elegible' in body
        assert 'Clase: FCI confirmado' in body
        assert 'Clase: no elegible por otros motivos' in body
        assert 'Origen: Metadata de título' in body or 'Origen: Metadata de titulo' in body
        assert 'Origen: Market snapshot' in body
        assert 'Origen: Confirmación FCI' in body or 'Origen: Confirmacion FCI' in body
        assert 'Origen: Clasificación local' in body or 'Origen: Clasificacion local' in body
        assert 'sin configurar 1' in body
        assert 'Series macro críticas' in body
        assert '4/7' in body
        assert 'Series macro críticas para decisión' in body
        assert 'USDARS MEP' in body
        assert 'referencia financiera local' in body
        assert 'UVA' in body
        assert 'proxy de CER e inflacion indexada' in body
        assert 'Fuentes externas' in body
        assert '1/1' in body
        assert 'ready' in body
        assert 'Estado de fuentes externas' in body
        assert 'ArgentinaDatos' in body
        assert '/v1/estado' in body

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
    def test_sync_iol_historical_prices_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:sync_iol_historical_prices'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_partial_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:sync_iol_historical_prices_partial'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_retry_metadata_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:sync_iol_historical_prices_retry_metadata'))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_refresh_iol_market_snapshot_forbidden_for_non_staff(self, auth_client):
        response = auth_client.post(reverse('dashboard:refresh_iol_market_snapshot'))
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

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            def sync_current_portfolio_symbols_by_status(self, statuses=('missing',), minimum_ready_rows=5, params=None):
                assert statuses == ('missing',)
                assert minimum_ready_rows == 5
                return {
                    'success': True,
                    'selected_count': 1,
                    'processed': 1,
                    'statuses': ['missing'],
                    'results': {
                        'NASDAQ:AAPL': {
                            'success': True,
                            'rows_received': 30,
                        }
                    },
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_iol_historical_prices'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Históricos IOL sincronizados para símbolos faltantes' in str(message) or 'Historicos IOL sincronizados para simbolos faltantes' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='sync_iol_historical_prices')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_view_handles_empty_selection(self, staff_client, monkeypatch):
        class DummyService:
            def sync_current_portfolio_symbols_by_status(self, statuses=('missing',), minimum_ready_rows=5, params=None):
                return {
                    'success': True,
                    'selected_count': 0,
                    'processed': 0,
                    'statuses': ['missing'],
                    'results': {},
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_iol_historical_prices'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('No hay símbolos faltantes para sincronizar históricos IOL' in str(message) or 'No hay simbolos faltantes para sincronizar historicos IOL' in str(message) for message in messages)

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_partial_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            def sync_current_portfolio_symbols_by_status(self, statuses=('partial',), minimum_ready_rows=5, params=None):
                assert statuses == ('partial',)
                assert minimum_ready_rows == 5
                return {
                    'success': True,
                    'selected_count': 1,
                    'processed': 1,
                    'statuses': ['partial'],
                    'results': {
                        'BCBA:GGAL': {
                            'success': True,
                            'rows_received': 12,
                        }
                    },
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_iol_historical_prices_partial'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Históricos IOL parciales reforzados' in str(message) or 'Historicos IOL parciales reforzados' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='sync_iol_historical_prices_partial')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_partial_view_handles_empty_selection(self, staff_client, monkeypatch):
        class DummyService:
            def sync_current_portfolio_symbols_by_status(self, statuses=('partial',), minimum_ready_rows=5, params=None):
                return {
                    'success': True,
                    'selected_count': 0,
                    'processed': 0,
                    'statuses': ['partial'],
                    'results': {},
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_iol_historical_prices_partial'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('No hay símbolos parciales para reforzar históricos IOL' in str(message) or 'No hay simbolos parciales para reforzar historicos IOL' in str(message) for message in messages)

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_retry_metadata_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            def sync_current_portfolio_symbols_by_status(
                self,
                statuses=('unsupported',),
                minimum_ready_rows=5,
                eligibility_reason_keys=None,
                params=None,
            ):
                assert statuses == ('unsupported',)
                assert minimum_ready_rows == 5
                assert eligibility_reason_keys == ('title_metadata_unresolved',)
                return {
                    'success': True,
                    'selected_count': 1,
                    'processed': 1,
                    'statuses': ['unsupported'],
                    'eligibility_reason_keys': ['title_metadata_unresolved'],
                    'results': {
                        'NASDAQ:MSFT': {
                            'success': True,
                            'rows_received': 18,
                        }
                    },
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_iol_historical_prices_retry_metadata'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('Reintento de metadata IOL ejecutado' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='sync_iol_historical_prices_retry_metadata')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_sync_iol_historical_prices_retry_metadata_view_handles_empty_selection(self, staff_client, monkeypatch):
        class DummyService:
            def sync_current_portfolio_symbols_by_status(
                self,
                statuses=('unsupported',),
                minimum_ready_rows=5,
                eligibility_reason_keys=None,
                params=None,
            ):
                return {
                    'success': True,
                    'selected_count': 0,
                    'processed': 0,
                    'statuses': ['unsupported'],
                    'eligibility_reason_keys': ['title_metadata_unresolved'],
                    'results': {},
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:sync_iol_historical_prices_retry_metadata'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('No hay exclusiones por metadata para reintentar históricos IOL' in str(message) or 'No hay exclusiones por metadata para reintentar historicos IOL' in str(message) for message in messages)

    @pytest.mark.django_db
    def test_refresh_iol_market_snapshot_view_success_message(self, staff_client, monkeypatch):
        class DummyService:
            def refresh_and_persist_current_portfolio_market_snapshot(self, limit=25):
                assert limit == 25
                return {
                    'rows': [
                        {
                            'simbolo': 'GGAL',
                            'mercado': 'bcba',
                            'snapshot_status': 'available',
                            'snapshot_source_key': 'cotizacion_detalle',
                            'puntas_count': 1,
                        },
                        {
                            'simbolo': 'AAPL',
                            'mercado': 'NASDAQ',
                            'snapshot_status': 'missing',
                            'snapshot_source_key': '',
                            'puntas_count': 0,
                        },
                    ],
                    'summary': {
                        'total_symbols': 2,
                        'available_count': 1,
                        'missing_count': 1,
                        'unsupported_count': 0,
                        'detail_count': 1,
                        'fallback_count': 0,
                        'order_book_count': 1,
                        'overall_status': 'partial',
                    },
                    'persistence': {'persisted_count': 1, 'created': 1, 'updated': 0, 'skipped': 1},
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:refresh_iol_market_snapshot'), {'next': reverse('dashboard:resumen')})
        assert response.status_code == 302
        assert response['Location'].endswith(reverse('dashboard:resumen'))
        messages = list(get_messages(response.wsgi_request))
        assert any('Market snapshot IOL refrescado con cobertura parcial' in str(message) for message in messages)
        audit = SensitiveActionAudit.objects.get(action='refresh_iol_market_snapshot')
        assert audit.status == 'success'
        assert audit.user.username == 'staffuser'

    @pytest.mark.django_db
    def test_refresh_iol_market_snapshot_view_handles_empty_selection(self, staff_client, monkeypatch):
        class DummyService:
            def refresh_and_persist_current_portfolio_market_snapshot(self, limit=25):
                return {
                    'rows': [],
                    'summary': {
                        'total_symbols': 0,
                        'available_count': 0,
                        'missing_count': 0,
                        'unsupported_count': 0,
                        'detail_count': 0,
                        'fallback_count': 0,
                        'order_book_count': 0,
                        'overall_status': 'missing',
                    },
                    'persistence': {'persisted_count': 0, 'created': 0, 'updated': 0, 'skipped': 0},
                }

        monkeypatch.setattr('apps.dashboard.views.IOLHistoricalPriceService', lambda: DummyService())
        response = staff_client.post(reverse('dashboard:refresh_iol_market_snapshot'))
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert any('No hay simbolos del portfolio para validar market snapshot IOL' in str(message) for message in messages)

    def test_save_incremental_proposal_passes_decision_payload_to_history_service(self, auth_client, monkeypatch):
        captured = {}

        monkeypatch.setattr(
            'apps.dashboard.views.get_preferred_incremental_portfolio_proposal',
            lambda query_params, capital_amount=600000: {
                'preferred': {
                    'source_key': 'candidate_split',
                    'source_label': 'Comparador por split',
                    'proposal_key': 'split_ko_mcd',
                    'proposal_label': 'Split KO + MCD',
                    'purchase_plan': [{'symbol': 'KO', 'amount': 150000}],
                    'simulation': {'delta': {'expected_return_change': 0.5}, 'interpretation': 'ok'},
                },
                'explanation': 'Sintesis preferida.',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_decision_engine_summary',
            lambda user, query_params=None, capital_amount=600000: {
                'score': 78,
                'confidence': 'Alta',
                'explanation': ['Se refuerza defensivos USD porque mejora la resiliencia.'],
                'macro_state': {'key': 'normal'},
                'portfolio_state': {'key': 'ok'},
                'tracking_payload': {
                    'score': 78,
                    'confidence': 'Alta',
                    'macro_state': 'normal',
                    'portfolio_state': 'ok',
                },
            },
        )

        class DummyHistoryService:
            def save_preferred_proposal(self, **kwargs):
                captured.update(kwargs)
                return {
                    'proposal_label': 'Split KO + MCD',
                    'source_key': 'candidate_split',
                }

        monkeypatch.setattr('apps.dashboard.views.IncrementalProposalHistoryService', lambda: DummyHistoryService())

        response = auth_client.post(
            reverse('dashboard:save_incremental_proposal'),
            {'source_query': 'decision_status_filter=pending'},
        )

        assert response.status_code == 302
        assert captured['decision_payload']['score'] == 78
        assert captured['decision_payload']['confidence'] == 'Alta'
        assert captured['decision_payload']['tracking_payload']['macro_state'] == 'normal'
        assert captured['preferred_payload']['proposal_label'] == 'Split KO + MCD'
        assert captured['capital_amount'] == 600000
        assert captured['user'].is_authenticated is True

    def test_bulk_decide_incremental_proposal_preserves_priority_filter_and_sort(self, auth_client, monkeypatch):
        captured = {}

        def fake_history(**kwargs):
            captured['history_kwargs'] = kwargs
            return {'items': [{'id': 10}], 'count': 1}

        monkeypatch.setattr('apps.dashboard.views.get_incremental_proposal_history', fake_history)

        class DummyHistoryService:
            def decide_many_snapshots(self, **kwargs):
                captured['service_kwargs'] = kwargs
                return {'decision_status': kwargs['decision_status'], 'updated_count': len(kwargs['snapshot_ids'])}

        monkeypatch.setattr('apps.dashboard.views.IncrementalProposalHistoryService', lambda: DummyHistoryService())

        response = auth_client.post(
            reverse('dashboard:bulk_decide_incremental_proposal'),
            {
                'decision_status': 'accepted',
                'decision_status_filter': 'pending',
                'history_priority_filter': 'high',
                'history_sort': 'priority',
            },
        )

        assert response.status_code == 302
        assert response.url.endswith(
            '?decision_status_filter=pending&history_priority_filter=high&history_sort=priority#planeacion-aportes'
        )
        assert captured['history_kwargs']['decision_status'] == 'pending'
        assert captured['history_kwargs']['priority_filter'] == 'high'
        assert captured['history_kwargs']['sort_mode'] == 'priority'
        assert captured['service_kwargs']['snapshot_ids'] == [10]







