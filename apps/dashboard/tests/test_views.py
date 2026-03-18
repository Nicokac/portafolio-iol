import pytest
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
        assert 'Capital invertido' in body
        assert 'Liquidez total' in body
        assert 'USD oficial mayorista BCRA' in body
        assert 'Riesgo país Argentina' in body
        assert 'Fuente: ArgentinaDatos' in body
        assert 'Cambio 30d:' in body

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
                "incremental_proposal_history": {"items": [], "count": 0, "has_history": False, "active_filter": "pending", "active_filter_label": "Pendientes", "decision_counts": {"total": 0, "pending": 0, "accepted": 0, "deferred": 0, "rejected": 0}, "available_filters": [], "headline": ""},
                "incremental_proposal_tracking_baseline": {"item": None, "has_baseline": False},
                "incremental_manual_decision_summary": {"item": None, "has_decision": False, "status": "pending", "status_label": "Pendiente", "headline": ""},
                "incremental_decision_executive_summary": {"status": "pending", "headline": "", "items": [], "has_summary": False},
            }

        monkeypatch.setattr("apps.dashboard.views.get_planeacion_incremental_context", fake_planeacion_context)

        response = auth_client.get(reverse("dashboard:planeacion"), {"decision_status_filter": "pending"})

        assert response.status_code == 200
        assert captured == {
            "decision_status_filter": "pending",
            "user_id": int(auth_client.session["_auth_user_id"]),
            "capital_amount": 600000,
            "history_limit": 5,
        }

    def test_planeacion_explains_total_liquidity_definition(self, auth_client):
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Liquidez total = liquidez operativa + cash management' in body
        assert 'Modelo de riesgo:' in body

    def test_planeacion_shows_monthly_allocation_proposal(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_planeacion_incremental_context',
            lambda query_params, user, capital_amount=600000, history_limit=5: {
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
                'incremental_proposal_history': {
                    'items': [{'id': 1, 'proposal_label': 'Plan guardado 1', 'source_label': 'Comparador manual', 'selected_context': 'Plan manual enviado por el usuario', 'purchase_plan': [{'symbol': 'KO', 'amount': 300000}], 'simulation_delta': {'expected_return_change': 0.4, 'fragility_change': -1.5, 'scenario_loss_change': 0.3}, 'manual_decision_status': 'pending', 'manual_decision_status_label': 'Pendiente', 'is_backlog_front': False, 'is_tracking_baseline': False, 'reapply_querystring': 'manual_capital_amount=300000&manual_a_symbol_1=KO&manual_a_amount_1=300000', 'reapply_truncated': False, 'created_at': '2026-03-17 11:00'}],
                    'count': 1,
                    'has_history': True,
                    'active_filter': 'all',
                    'active_filter_label': 'Todos',
                    'decision_counts': {'total': 1, 'pending': 1, 'accepted': 0, 'deferred': 0, 'rejected': 0},
                    'available_filters': [{'key': 'all', 'label': 'Todos', 'count': 1, 'selected': True}],
                    'headline': 'Se muestran 1 snapshots recientes sobre un total de 1 propuestas guardadas.',
                },
                'incremental_proposal_tracking_baseline': {
                    'item': {'proposal_label': 'Plan baseline', 'source_label': 'Comparador manual', 'purchase_plan': [{'symbol': 'KO', 'amount': 300000}], 'created_at': '2026-03-17 11:00'},
                    'has_baseline': True,
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
        assert 'Propuesta de compra mensual' in body
        assert 'Plan incremental MVP' in body
        assert 'Tecnología / growth' in body
        assert 'Por qué este bloque recibió este score' in body
        assert 'Señales positivas' in body
        assert 'Señales negativas' in body
        assert 'Candidatos de activos dentro de los bloques recomendados' in body
        assert 'Ranking incremental MVP' in body
        assert 'KO' in body
        assert 'Impacto incremental simulado' in body
        assert 'La compra reduce la fragilidad del portafolio.' in body
        assert 'Expected return' in body
        assert 'Fragility' in body
        assert 'Propuesta incremental preferida' in body
        assert 'Guardar propuesta preferida' in body
        assert 'Resumen ejecutivo unificado de decisión incremental' in body
        assert 'La propuesta actual requiere validación antes de adoptar el aporte incremental.' in body
        assert 'Seguimiento operativo incremental' in body
        assert 'Plan baseline' in body
        assert 'La ultima decision manual registrada es aceptada sobre Plan manual A.' in body
        assert 'Historial reciente de propuestas guardadas' in body
        assert 'Filtrar por decisión manual' in body
        assert 'Aceptar visibles' in body
        assert 'Diferir visibles' in body
        assert 'Rechazar visibles' in body
        assert 'Plan guardado 1' in body
        assert 'Promover a baseline' in body
        assert 'Reaplicar en comparador manual' in body
        assert 'Comparador por split' in body
        assert 'Split KO + MCD' in body
        assert 'Comparador de propuestas incrementales' in body
        assert 'Split del bloque más grande' in body
        assert 'Comparador incremental por candidato' in body
        assert 'Comparador incremental por split de bloque' in body
        assert 'Comparador manual de planes incrementales' in body
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
                    'local_macro_status_summary': {
                        'ready': 3,
                        'total_series': 4,
                        'stale': 1,
                        'missing': 0,
                        'not_configured': 1,
                        'overall_status': 'warning',
                    },
                    'snapshot_integrity_issues_count': 2,
                    'required_periodic_tasks': [],
                    'benchmark_status_rows': [],
                    'local_macro_status_rows': [],
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
        assert 'sin configurar 1' in body

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







