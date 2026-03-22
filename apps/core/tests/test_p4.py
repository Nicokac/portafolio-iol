import pytest
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.core.models import PortfolioParameters
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.core.services.portfolio_simulator import PortfolioSimulator
from apps.core.services.portfolio_optimizer import PortfolioOptimizer
from apps.core.services.recommendation_engine import RecommendationEngine
from apps.core.services.monthly_investment_planner import MonthlyInvestmentPlanner


class P4ServicesTestCase(TestCase):
    """Tests para servicios de P4."""
    def setUp(self):
        """Configuración inicial para tests."""
        from django.utils import timezone
        self.portfolio_params = PortfolioParameters.objects.create(
            name="Test Parameters",
            liquidez_target=20.00,
            usa_target=40.00,
            argentina_target=30.00,
            emerging_target=10.00
        )
        fecha = timezone.now()
        for simbolo in ['SPY', 'EEM', 'GGAL']:
            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha,
                pais_consulta='argentina',
                simbolo=simbolo,
                descripcion=simbolo,
                cantidad='10',
                comprometido='0',
                disponible_inmediato='10',
                puntos_variacion='0',
                variacion_diaria='0',
                ultimo_precio='100',
                ppc='90',
                ganancia_porcentaje='10',
                ganancia_dinero='100',
                valorizado='1000',
                pais_titulo='USA',
                mercado='BCBA',
                tipo='CEDEARS',
                moneda='ARS',
            )

    def test_portfolio_simulator_purchase(self):
        """Test simulación de compra."""
        simulator = PortfolioSimulator()
        current_portfolio = {'total_iol': 1000000}

        result = simulator.simulate_purchase('SPY', Decimal('100000'), current_portfolio)

        self.assertIn('nuevo_peso_activo', result)
        self.assertIn('capital_invertido', result)
        self.assertEqual(result['accion'], 'compra')

    def test_portfolio_simulator_sale(self):
        """Test simulación de venta."""
        simulator = PortfolioSimulator()
        current_portfolio = {'total_iol': 1000000}

        result = simulator.simulate_sale('SPY', Decimal('100'), current_portfolio)

        self.assertIn('capital_recuperado', result)
        self.assertEqual(result['accion'], 'venta')

    def test_portfolio_optimizer_risk_parity(self):
        """Test optimización Risk Parity."""
        optimizer = PortfolioOptimizer()
        activos = ['SPY', 'EEM', 'GGAL']

        result = optimizer.optimize_risk_parity(activos)

        self.assertIn('metodo', result)
        self.assertEqual(result['metodo'], 'risk_parity')
        self.assertIn('pesos_optimos', result)

    def test_portfolio_optimizer_markowitz(self):
        """Test optimización Markowitz."""
        optimizer = PortfolioOptimizer()
        activos = ['SPY', 'EEM']

        result = optimizer.optimize_markowitz(activos, 0.08)

        self.assertIn('metodo', result)
        self.assertEqual(result['metodo'], 'markowitz')
        self.assertIn('pesos_optimos', result)

    def test_recommendation_engine(self):
        """Test motor de recomendaciones."""
        engine = RecommendationEngine()
        current_portfolio = {'total_iol': 1000000}

        recommendations = engine.generate_recommendations(current_portfolio)

        self.assertIsInstance(recommendations, list)
        # Verificar estructura de recomendaciones
        if recommendations:
            rec = recommendations[0]
            self.assertIn('tipo', rec)
            self.assertIn('prioridad', rec)

    def test_monthly_investment_planner(self):
        """Test planificador de aportes mensuales."""
        planner = MonthlyInvestmentPlanner()
        monthly_amount = Decimal('500000')

        result = planner.plan_monthly_investment(monthly_amount)

        self.assertIn('distribucion', result)
        self.assertIn('aporte_mensual', result)
        self.assertEqual(float(result['aporte_mensual']), 500000)

    @patch('apps.core.services.monthly_investment_planner.get_concentracion_pais')
    def test_custom_plan_uses_real_portfolio_state(self, mock_concentracion_pais):
        """El plan custom debe ajustarse por estado actual, no quedar fijo por perfil."""
        mock_concentracion_pais.return_value = {
            'USA': 10.0,
            'Argentina': 80.0,
            'EM': 0.0,
        }
        planner = MonthlyInvestmentPlanner()
        monthly_amount = Decimal('600000')
        current_portfolio = {
            'total_iol': 1000000,
            'liquidez_operativa': 500000,
            'fci_cash_management': 100000,
        }

        result = planner.create_custom_plan(
            monthly_amount=monthly_amount,
            risk_profile='moderado',
            investment_horizon='medio',
            current_portfolio=current_portfolio,
        )

        distrib = result['distribucion']
        # Base moderada fija era LIQUIDEZ=15/SPY=35; esperamos ajuste state-aware.
        self.assertLess(distrib['LIQUIDEZ']['porcentaje'], 15)
        self.assertGreater(distrib['SPY']['porcentaje'], 35)

    def test_portfolio_parameters_model(self):
        """Test modelo PortfolioParameters."""
        params = self.portfolio_params

        # Test validación de asignación
        self.assertTrue(params.is_valid_allocation())

        # Test pesos objetivo
        weights = params.get_target_weights_dict()
        self.assertEqual(weights['liquidez'], 20.0)
        self.assertEqual(weights['usa'], 40.0)

        # Test total
        self.assertEqual(float(params.total_target_allocation), 100.0)

    def test_portfolio_parameters_rejects_invalid_total_on_clean(self):
        params = PortfolioParameters(
            name="Invalid Total",
            liquidez_target=Decimal('30.00'),
            usa_target=Decimal('40.00'),
            argentina_target=Decimal('20.00'),
            emerging_target=Decimal('20.00'),
        )

        with self.assertRaises(ValidationError) as exc:
            params.full_clean()

        self.assertIn('__all__', exc.exception.message_dict)

    def test_portfolio_parameters_rejects_invalid_range_on_clean(self):
        params = PortfolioParameters(
            name="Invalid Range",
            liquidez_target=Decimal('20.00'),
            usa_target=Decimal('40.00'),
            argentina_target=Decimal('30.00'),
            emerging_target=Decimal('10.00'),
            max_single_position=Decimal('120.00'),
        )

        with self.assertRaises(ValidationError) as exc:
            params.full_clean()

        self.assertIn('max_single_position', exc.exception.message_dict)

    def test_portfolio_parameters_enforces_total_allocation_constraint_in_db(self):
        with self.assertRaises(IntegrityError):
            PortfolioParameters.objects.create(
                name="Invalid DB Total",
                liquidez_target=Decimal('30.00'),
                usa_target=Decimal('40.00'),
                argentina_target=Decimal('20.00'),
                emerging_target=Decimal('20.00'),
            )


class P4APITestCase(TestCase):
    """Tests para API de P4."""
    def setUp(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        self.user = User.objects.create_user(username='p4testuser', password='testpass123')
        self.client.force_login(self.user)
        fecha = timezone.now()
        for simbolo in ['SPY', 'EEM', 'GGAL']:
            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha,
                pais_consulta='argentina',
                simbolo=simbolo,
                descripcion=simbolo,
                cantidad='10',
                comprometido='0',
                disponible_inmediato='10',
                puntos_variacion='0',
                variacion_diaria='0',
                ultimo_precio='100',
                ppc='90',
                ganancia_porcentaje='10',
                ganancia_dinero='100',
                valorizado='1000',
                pais_titulo='USA',
                mercado='BCBA',
                tipo='CEDEARS',
                moneda='ARS',
            )

    def test_simulation_purchase_api(self):
        """Test API de simulación de compra."""
        url = reverse('simulation-purchase')
        data = {
            'activo': 'SPY',
            'capital': 100000
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn('nuevo_peso_activo', result)

    def test_optimizer_risk_parity_api(self):
        """Test API de optimización Risk Parity."""
        import json
        url = reverse('optimizer-risk-parity')
        data = {
            'activos': ['SPY', 'EEM', 'GGAL']
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result['metodo'], 'risk_parity')

    def test_recommendations_api(self):
        """Test API de recomendaciones."""
        url = reverse('recommendations-all')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        recommendations = response.json()
        self.assertIsInstance(recommendations, list)

    def test_monthly_plan_api(self):
        """Test API de plan mensual."""
        url = reverse('monthly-plan-basic')
        data = {
            'monthly_amount': 500000
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn('distribucion', result)

    def test_portfolio_parameters_api(self):
        """Test API de parámetros del portafolio."""
        # Crear parámetros de prueba
        PortfolioParameters.objects.create(
            name="API Test Parameters",
            liquidez_target=25.00,
            usa_target=35.00,
            argentina_target=25.00,
            emerging_target=15.00
        )

        url = reverse('portfolio-parameters-get')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('liquidez_target', data)
        self.assertEqual(data['liquidez_target'], 25.0)
