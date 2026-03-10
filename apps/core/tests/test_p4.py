import pytest
from decimal import Decimal
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
        """ConfiguraciÃ³n inicial para tests."""
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
        self.assertEqual(result['metodo'], 'markowitz_simplified')
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
        """Test API de optimizaciÃ³n Risk Parity."""
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