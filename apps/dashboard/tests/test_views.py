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

    def test_planeacion_explains_total_liquidity_definition(self, auth_client):
        response = auth_client.get(reverse('dashboard:planeacion'))
        body = response.content.decode()
        assert 'Liquidez total = liquidez operativa + cash management' in body
        assert 'Modelo de riesgo:' in body

    def test_planeacion_shows_monthly_allocation_proposal(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_monthly_allocation_plan',
            lambda capital_amount=600000: {
                'capital_total': capital_amount,
                'recommended_blocks_count': 2,
                'criterion': 'rules_based_analytics_v2_mvp',
                'recommended_blocks': [
                    {
                        'label': 'Defensive / resiliente',
                        'suggested_amount': 350000,
                        'suggested_pct': 58.33,
                        'score': 4.5,
                        'reason': 'cubre defensive_gap',
                        'score_breakdown': {
                            'positive_signals': [
                                {'signal': 'factor_defensive_gap', 'impact': '+3.00', 'source': 'factor_exposure'}
                            ],
                            'negative_signals': [],
                            'notes': 'Score explicable MVP',
                        },
                    },
                    {
                        'label': 'Dividend / ingresos pasivos',
                        'suggested_amount': 250000,
                        'suggested_pct': 41.67,
                        'score': 3.0,
                        'reason': 'cubre dividend_gap',
                        'score_breakdown': {
                            'positive_signals': [],
                            'negative_signals': [
                                {'signal': 'scenario_vulnerability_tech', 'impact': '-1.00', 'source': 'scenario_analysis'}
                            ],
                            'notes': 'Score explicable MVP',
                        },
                    },
                ],
                'avoided_blocks': [
                    {'label': 'Tecnología / growth', 'reason': 'ya domina el riesgo'}
                ],
                'explanation': 'Plan incremental MVP',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_candidate_asset_ranking',
            lambda capital_amount=600000: {
                'capital_total': capital_amount,
                'candidate_assets_count': 2,
                'candidate_assets': [
                    {
                        'asset': 'KO',
                        'block': 'defensive',
                        'block_label': 'Defensive / resiliente',
                        'score': 8.4,
                        'rank': 1,
                        'reasons': ['defensive_sector_match'],
                        'main_reason': 'defensive_sector_match',
                    },
                    {
                        'asset': 'SPY',
                        'block': 'global_index',
                        'block_label': 'Indice global',
                        'score': 6.8,
                        'rank': 2,
                        'reasons': ['stable_global_exposure'],
                        'main_reason': 'stable_global_exposure',
                    },
                ],
                'by_block': [],
                'explanation': 'Ranking incremental MVP',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_portfolio_simulation',
            lambda capital_amount=600000: {
                'capital_amount': float(capital_amount),
                'selected_candidates': [
                    {
                        'symbol': 'KO',
                        'block': 'defensive',
                        'block_label': 'Defensive / resiliente',
                        'amount': 350000,
                        'candidate_score': 8.4,
                        'candidate_reason': 'defensive_sector_match',
                    },
                    {
                        'symbol': 'SPY',
                        'block': 'global_index',
                        'block_label': 'Indice global',
                        'amount': 250000,
                        'candidate_score': 6.8,
                        'candidate_reason': 'stable_global_exposure',
                    },
                ],
                'before': {
                    'expected_return_pct': 8.0,
                    'real_expected_return_pct': 1.0,
                    'fragility_score': 64.0,
                    'worst_scenario_loss_pct': -12.0,
                },
                'after': {
                    'expected_return_pct': 8.6,
                    'real_expected_return_pct': 1.3,
                    'fragility_score': 60.5,
                    'worst_scenario_loss_pct': -11.2,
                },
                'delta': {
                    'expected_return_change': 0.6,
                    'real_expected_return_change': 0.3,
                    'fragility_change': -3.5,
                    'scenario_loss_change': 0.8,
                    'risk_concentration_change': -1.1,
                },
                'interpretation': 'La compra reduce la fragilidad del portafolio.',
                'warnings': [],
                'unmapped_blocks': [],
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_portfolio_simulation_comparison',
            lambda capital_amount=600000: {
                'capital_amount': float(capital_amount),
                'best_proposal_key': 'split_largest_block_top_two',
                'best_label': 'Split del bloque más grande',
                'proposals': [
                    {
                        'proposal_key': 'split_largest_block_top_two',
                        'label': 'Split del bloque más grande',
                        'selected_candidates': [
                            {'symbol': 'KO', 'amount': 175000},
                            {'symbol': 'PEP', 'amount': 175000},
                            {'symbol': 'SPY', 'amount': 250000},
                        ],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.7,
                                'fragility_change': -4.0,
                                'scenario_loss_change': 0.9,
                            },
                            'interpretation': 'Mejor equilibrio defensivo.',
                        },
                        'comparison_score': 5.1,
                    },
                    {
                        'proposal_key': 'top_candidate_per_block',
                        'label': 'Top candidato por bloque',
                        'selected_candidates': [
                            {'symbol': 'KO', 'amount': 350000},
                            {'symbol': 'SPY', 'amount': 250000},
                        ],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.6,
                                'fragility_change': -3.5,
                                'scenario_loss_change': 0.8,
                            },
                            'interpretation': 'Alternativa base.',
                        },
                        'comparison_score': 4.3,
                    },
                ],
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_candidate_incremental_portfolio_comparison',
            lambda query_params, capital_amount=600000: {
                'submitted': True,
                'available_blocks': [
                    {'bucket': 'defensive', 'label': 'Defensive / resiliente', 'suggested_amount': 300000},
                    {'bucket': 'global_index', 'label': 'Indice global', 'suggested_amount': 300000},
                ],
                'selected_block': 'defensive',
                'selected_label': 'Defensive / resiliente',
                'block_amount': 300000,
                'best_proposal_key': 'KO',
                'best_label': 'KO',
                'proposals': [
                    {
                        'proposal_key': 'KO',
                        'label': 'KO',
                        'candidate': {'score': 8.4, 'main_reason': 'defensive_sector_match'},
                        'purchase_plan': [{'symbol': 'KO', 'amount': 300000}],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.5,
                                'fragility_change': -2.5,
                                'scenario_loss_change': 0.7,
                            },
                            'interpretation': 'KO mejora más la resiliencia.',
                        },
                        'comparison_score': 4.7,
                    },
                    {
                        'proposal_key': 'MCD',
                        'label': 'MCD',
                        'candidate': {'score': 7.7, 'main_reason': 'dividend_profile'},
                        'purchase_plan': [{'symbol': 'MCD', 'amount': 300000}],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.4,
                                'fragility_change': -1.8,
                                'scenario_loss_change': 0.5,
                            },
                            'interpretation': 'MCD mejora moderadamente.',
                        },
                        'comparison_score': 3.5,
                    },
                ],
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_candidate_split_incremental_portfolio_comparison',
            lambda query_params, capital_amount=600000: {
                'submitted': True,
                'available_blocks': [
                    {'bucket': 'defensive', 'label': 'Defensive / resiliente', 'suggested_amount': 300000},
                ],
                'selected_block': 'defensive',
                'selected_label': 'Defensive / resiliente',
                'block_amount': 300000,
                'best_proposal_key': 'split_top_two',
                'best_label': 'Split KO + MCD',
                'proposals': [
                    {
                        'proposal_key': 'split_top_two',
                        'label': 'Split KO + MCD',
                        'purchase_plan': [
                            {'symbol': 'KO', 'amount': 150000},
                            {'symbol': 'MCD', 'amount': 150000},
                        ],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.5,
                                'fragility_change': -2.1,
                                'scenario_loss_change': 0.7,
                            },
                            'interpretation': 'El split mejora mejor el balance riesgo/retorno.',
                        },
                        'comparison_score': 4.2,
                    },
                    {
                        'proposal_key': 'single_top_candidate',
                        'label': 'Concentrado en KO',
                        'purchase_plan': [
                            {'symbol': 'KO', 'amount': 300000},
                        ],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.3,
                                'fragility_change': -1.2,
                                'scenario_loss_change': 0.3,
                            },
                            'interpretation': 'KO solo mejora de forma acotada.',
                        },
                        'comparison_score': 2.5,
                    },
                ],
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_manual_incremental_portfolio_simulation_comparison',
            lambda query_params, default_capital_amount=600000: {
                'submitted': True,
                'best_proposal_key': 'plan_a',
                'best_label': 'Plan manual A',
                'form_state': {
                    'plans': [
                        {
                            'plan_key': 'plan_a',
                            'label': 'Plan manual A',
                            'capital_raw': '600000',
                            'rows': [
                                {'symbol': 'KO', 'amount_raw': '300000'},
                                {'symbol': 'MCD', 'amount_raw': '300000'},
                                {'symbol': '', 'amount_raw': ''},
                            ],
                            'warnings': [],
                        },
                        {
                            'plan_key': 'plan_b',
                            'label': 'Plan manual B',
                            'capital_raw': '600000',
                            'rows': [
                                {'symbol': 'SPY', 'amount_raw': '600000'},
                                {'symbol': '', 'amount_raw': ''},
                                {'symbol': '', 'amount_raw': ''},
                            ],
                            'warnings': [],
                        },
                    ],
                },
                'proposals': [
                    {
                        'proposal_key': 'plan_a',
                        'label': 'Plan manual A',
                        'purchase_plan': [
                            {'symbol': 'KO', 'amount': 300000},
                            {'symbol': 'MCD', 'amount': 300000},
                        ],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.7,
                                'fragility_change': -3.8,
                                'scenario_loss_change': 0.9,
                            },
                            'interpretation': 'Plan manual A reduce mejor la fragilidad.',
                        },
                        'comparison_score': 5.4,
                    },
                    {
                        'proposal_key': 'plan_b',
                        'label': 'Plan manual B',
                        'purchase_plan': [
                            {'symbol': 'SPY', 'amount': 600000},
                        ],
                        'simulation': {
                            'delta': {
                                'expected_return_change': 0.2,
                                'fragility_change': -1.0,
                                'scenario_loss_change': 0.1,
                            },
                            'interpretation': 'Plan manual B es más acotado.',
                        },
                        'comparison_score': 2.1,
                    },
                ],
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_preferred_incremental_portfolio_proposal',
            lambda query_params, capital_amount=600000: {
                'preferred': {
                    'source_label': 'Comparador por split',
                    'selected_context': 'Defensive / resiliente',
                    'proposal_label': 'Split KO + MCD',
                    'comparison_score': 5.2,
                    'purchase_plan': [
                        {'symbol': 'KO', 'amount': 150000},
                        {'symbol': 'MCD', 'amount': 150000},
                    ],
                    'simulation': {
                        'delta': {
                            'expected_return_change': 0.5,
                            'real_expected_return_change': 0.2,
                            'fragility_change': -2.1,
                            'scenario_loss_change': 0.7,
                            'risk_concentration_change': -0.6,
                        },
                        'interpretation': 'El split mejora mejor el balance riesgo/retorno.',
                    },
                },
                'has_manual_override': False,
                'explanation': 'La propuesta preferida actual surge de Comparador por split para Defensive / resiliente: Split KO + MCD.',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_proposal_history',
            lambda user, limit=5, decision_status=None: {
                'items': [
                    {
                        'proposal_label': 'Plan guardado 1',
                        'source_label': 'Comparador manual',
                        'selected_context': 'Plan manual enviado por el usuario',
                        'purchase_plan': [{'symbol': 'KO', 'amount': 300000}],
                        'simulation_delta': {
                            'expected_return_change': 0.4,
                            'fragility_change': -1.5,
                            'scenario_loss_change': 0.3,
                        },
                        'manual_decision_status_label': 'Aceptada',
                        'created_at': '2026-03-17 11:00',
                    }
                ],
                'count': 1,
                'has_history': True,
                'active_filter': 'all',
                'active_filter_label': 'Todos',
                'decision_counts': {'total': 1, 'pending': 0, 'accepted': 1, 'deferred': 0, 'rejected': 0},
                'available_filters': [
                    {'key': 'all', 'label': 'Todos', 'count': 1, 'selected': True},
                    {'key': 'accepted', 'label': 'Aceptada', 'count': 1, 'selected': False},
                ],
                'headline': 'Se muestran 1 snapshots recientes sobre un total de 1 propuestas guardadas.',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_proposal_tracking_baseline',
            lambda user: {
                'item': {
                    'proposal_label': 'Plan baseline',
                    'source_label': 'Comparador manual',
                    'purchase_plan': [{'symbol': 'KO', 'amount': 300000}],
                    'created_at': '2026-03-17 11:00',
                },
                'has_baseline': True,
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_manual_decision_summary',
            lambda user: {
                'item': {
                    'proposal_label': 'Plan manual A',
                    'manual_decision_status': 'accepted',
                    'manual_decision_note': 'Lista para ejecutar',
                    'manual_decided_at': '2026-03-17 12:00',
                },
                'has_decision': True,
                'status': 'accepted',
                'status_label': 'Aceptada',
                'headline': 'La ultima decision manual registrada es aceptada sobre Plan manual A.',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_followup_executive_summary',
            lambda query_params, user, capital_amount=600000: {
                'status': 'aligned',
                'headline': 'La propuesta actual se mantiene alineada con el baseline activo.',
                'summary_items': [
                    {'label': 'Propuesta actual', 'value': 'Split KO + MCD'},
                    {'label': 'Baseline activo', 'value': 'Plan baseline'},
                    {'label': 'Estado de drift', 'value': 'Drift favorable'},
                    {'label': 'Score actual - baseline', 'value': 0.8},
                ],
                'preferred': {'proposal_label': 'Split KO + MCD'},
                'baseline': {'proposal_label': 'Plan baseline'},
                'drift': {},
                'has_preferred': True,
                'has_baseline': True,
                'has_summary': True,
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_adoption_checklist',
            lambda query_params, user, capital_amount=600000: {
                'status': 'ready',
                'adoption_ready': True,
                'passed_count': 5,
                'total_count': 5,
                'headline': 'La propuesta actual supera el checklist operativo y puede pasar a decision manual.',
                'items': [
                    {'label': 'Existe propuesta incremental preferida', 'passed': True, 'detail': 'Split KO + MCD'},
                    {'label': 'La propuesta tiene compra resumida', 'passed': True, 'detail': 'KO (150000), MCD (150000)'},
                ],
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_baseline_drift',
            lambda query_params, user, capital_amount=600000: {
                'baseline': {'proposal_label': 'Plan baseline'},
                'current_preferred': {'proposal_label': 'Split KO + MCD'},
                'comparison': {
                    'metrics': [
                        {
                            'key': 'expected_return_change',
                            'label': 'Expected return',
                            'saved_value': 0.4,
                            'current_value': 0.5,
                            'difference': 0.1,
                            'direction': 'favorable',
                        },
                        {
                            'key': 'fragility_change',
                            'label': 'Fragility',
                            'saved_value': -1.5,
                            'current_value': -2.1,
                            'difference': -0.6,
                            'direction': 'favorable',
                        },
                    ],
                },
                'summary': {
                    'status': 'favorable',
                    'favorable_count': 2,
                    'unfavorable_count': 0,
                    'changed_count': 2,
                    'material_metrics': [
                        {'key': 'expected_return_change', 'direction': 'favorable'},
                        {'key': 'fragility_change', 'direction': 'favorable'},
                    ],
                },
                'alerts': [
                    {
                        'severity': 'info',
                        'title': 'No hay drift material',
                        'message': 'La propuesta actual se mantiene alineada con el baseline activo.',
                    }
                ],
                'alerts_count': 1,
                'has_alerts': True,
                'has_drift': True,
                'has_baseline': True,
                'explanation': 'La propuesta preferida actual mejora el baseline activo en las metricas incrementales relevantes.',
            },
        )
        monkeypatch.setattr(
            'apps.dashboard.views.get_incremental_snapshot_vs_current_comparison',
            lambda query_params, user, capital_amount=600000: {
                'available_snapshots': [
                    {'id': 1, 'label': 'Plan guardado 1', 'created_at': '2026-03-17 11:00'}
                ],
                'selected_snapshot_id': '1',
                'selected_snapshot': {'proposal_label': 'Plan guardado 1'},
                'current_preferred': {'proposal_label': 'Split KO + MCD'},
                'comparison': {
                    'score_saved': 4.2,
                    'score_current': 5.2,
                    'score_difference': 1.0,
                    'metrics': [
                        {
                            'label': 'Expected return',
                            'saved_value': 0.4,
                            'current_value': 0.5,
                            'difference': 0.1,
                        }
                    ],
                },
                'has_comparison': True,
                'explanation': 'La propuesta preferida actual mejora el score comparativo frente al snapshot guardado.',
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
        assert 'defensive_sector_match' in body
        assert 'Impacto incremental simulado' in body
        assert 'La compra reduce la fragilidad del portafolio.' in body
        assert 'Expected return' in body
        assert 'Fragility' in body
        assert 'Propuesta incremental preferida' in body
        assert 'Guardar propuesta preferida' in body
        assert 'Checklist de adopción de propuesta incremental' in body
        assert 'La propuesta actual supera el checklist operativo y puede pasar a decision manual.' in body
        assert 'Adopcion habilitada' in body
        assert 'Workflow de decisión manual' in body
        assert 'La ultima decision manual registrada es aceptada sobre Plan manual A.' in body
        assert 'Resumen ejecutivo de seguimiento incremental' in body
        assert 'La propuesta actual se mantiene alineada con el baseline activo.' in body
        assert 'Baseline incremental de seguimiento' in body
        assert 'Plan baseline' in body
        assert 'Drift vs propuesta preferida actual' in body
        assert 'Alertas de drift' in body
        assert 'Drift favorable' in body
        assert 'Promover a baseline' in body
        assert 'Historial reciente de propuestas guardadas' in body
        assert 'Filtrar por decisión manual' in body
        assert 'Se muestran 1 snapshots recientes sobre un total de 1 propuestas guardadas.' in body
        assert 'Plan guardado 1' in body
        assert 'Aceptar' in body
        assert 'Diferir' in body
        assert 'Rechazar' in body
        assert 'Reaplicar en comparador manual' in body
        assert 'Snapshot guardado vs propuesta actual' in body
        assert 'Comparar snapshot' in body
        assert 'Comparador por split' in body
        assert 'Split KO + MCD' in body
        assert 'Comparador de propuestas incrementales' in body
        assert 'Split del bloque más grande' in body
        assert 'Mejor balance' in body
        assert 'Comparador incremental por candidato' in body
        assert 'Bloque a comparar' in body
        assert 'KO mejora más la resiliencia.' in body
        assert 'Comparador incremental por split de bloque' in body
        assert 'Bloque a dividir' in body
        assert 'El split mejora mejor el balance riesgo/retorno.' in body
        assert 'Comparador manual de planes incrementales' in body
        assert 'Plan manual A' in body
        assert 'Plan manual B' in body
        assert 'Comparar planes manuales' in body
        assert 'Mejor balance manual' in body

    def test_save_incremental_proposal_requires_authentication(self, client):
        response = client.post(reverse('dashboard:save_incremental_proposal'))
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']

    def test_save_incremental_proposal_persists_snapshot(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_preferred_incremental_portfolio_proposal',
            lambda query_params, capital_amount=600000: {
                'preferred': {
                    'source_key': 'manual_plan',
                    'source_label': 'Comparador manual',
                    'proposal_key': 'plan_a',
                    'proposal_label': 'Plan manual A',
                    'selected_context': 'Plan manual enviado por el usuario',
                    'comparison_score': 5.4,
                    'purchase_plan': [
                        {'symbol': 'KO', 'amount': 300000},
                        {'symbol': 'MCD', 'amount': 300000},
                    ],
                    'simulation': {
                        'delta': {'expected_return_change': 0.7, 'fragility_change': -3.8},
                        'interpretation': 'Plan manual A reduce mejor la fragilidad.',
                    },
                },
                'explanation': 'Sintesis manual.',
            },
        )

        response = auth_client.post(
            reverse('dashboard:save_incremental_proposal'),
            {'source_query': 'manual_compare=1'},
        )

        assert response.status_code == 302
        snapshot = IncrementalProposalSnapshot.objects.get()
        assert snapshot.proposal_label == 'Plan manual A'
        audit = SensitiveActionAudit.objects.get(action='save_incremental_proposal')
        assert audit.status == 'success'
        messages = list(get_messages(response.wsgi_request))
        assert any('Propuesta incremental guardada' in str(message) for message in messages)

    def test_save_incremental_proposal_rejects_missing_preferred(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            'apps.dashboard.views.get_preferred_incremental_portfolio_proposal',
            lambda query_params, capital_amount=600000: {
                'preferred': None,
                'explanation': 'Sin propuesta.',
            },
        )

        response = auth_client.post(reverse('dashboard:save_incremental_proposal'), {'source_query': ''})

        assert response.status_code == 302
        assert IncrementalProposalSnapshot.objects.count() == 0
        audit = SensitiveActionAudit.objects.get(action='save_incremental_proposal')
        assert audit.status == 'denied'

    def test_promote_incremental_baseline_requires_authentication(self, client):
        response = client.post(reverse('dashboard:promote_incremental_baseline'))
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']

    def test_promote_incremental_baseline_marks_snapshot(self, auth_client, user):
        snapshot = IncrementalProposalSnapshot.objects.create(
            user=user,
            source_key='manual_plan',
            source_label='Comparador manual',
            proposal_key='plan_a',
            proposal_label='Plan manual A',
            capital_amount=600000,
            purchase_plan=[{'symbol': 'KO', 'amount': 300000}],
            simulation_delta={},
        )

        response = auth_client.post(reverse('dashboard:promote_incremental_baseline'), {'snapshot_id': snapshot.id})

        assert response.status_code == 302
        snapshot.refresh_from_db()
        assert snapshot.is_tracking_baseline is True
        audit = SensitiveActionAudit.objects.get(action='promote_incremental_baseline')
        assert audit.status == 'success'

    def test_promote_incremental_baseline_rejects_unknown_snapshot(self, auth_client):
        response = auth_client.post(reverse('dashboard:promote_incremental_baseline'), {'snapshot_id': 999999})

        assert response.status_code == 302
        audit = SensitiveActionAudit.objects.get(action='promote_incremental_baseline')
        assert audit.status == 'failed'

    def test_decide_incremental_proposal_requires_authentication(self, client):
        response = client.post(reverse('dashboard:decide_incremental_proposal'))
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']

    def test_decide_incremental_proposal_updates_snapshot(self, auth_client, user):
        snapshot = IncrementalProposalSnapshot.objects.create(
            user=user,
            source_key='manual_plan',
            source_label='Comparador manual',
            proposal_key='plan_a',
            proposal_label='Plan manual A',
            capital_amount=600000,
            purchase_plan=[{'symbol': 'KO', 'amount': 300000}],
            simulation_delta={},
        )

        response = auth_client.post(
            reverse('dashboard:decide_incremental_proposal'),
            {'snapshot_id': snapshot.id, 'decision_status': 'accepted', 'decision_note': 'Lista para ejecutar'},
        )

        assert response.status_code == 302
        snapshot.refresh_from_db()
        assert snapshot.manual_decision_status == 'accepted'
        assert snapshot.manual_decision_note == 'Lista para ejecutar'
        audit = SensitiveActionAudit.objects.get(action='decide_incremental_proposal')
        assert audit.status == 'success'

    def test_decide_incremental_proposal_rejects_invalid_snapshot(self, auth_client):
        response = auth_client.post(
            reverse('dashboard:decide_incremental_proposal'),
            {'snapshot_id': 999999, 'decision_status': 'accepted'},
        )

        assert response.status_code == 302
        audit = SensitiveActionAudit.objects.get(action='decide_incremental_proposal')
        assert audit.status == 'failed'

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







