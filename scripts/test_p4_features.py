#!/usr/bin/env python
"""
Script de validación de P4 - Motor de Estrategia de Inversión
"""

import os
import sys
import django
from decimal import Decimal

# Configurar Django
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portafolio_iol.settings')
django.setup()

from apps.core.services.portfolio_simulator import PortfolioSimulator
from apps.core.services.portfolio_optimizer import PortfolioOptimizer
from apps.core.services.recommendation_engine import RecommendationEngine
from apps.core.services.monthly_investment_planner import MonthlyInvestmentPlanner
from apps.dashboard.selectors import get_dashboard_kpis
from apps.core.models import PortfolioParameters


def run_portfolio_simulator():
    """Test del simulador de portafolio."""
    print("🧪 Testing Portfolio Simulator...")

    simulator = PortfolioSimulator()
    current_portfolio = get_dashboard_kpis()

    # Test compra
    result = simulator.simulate_purchase('SPY', Decimal('100000'), current_portfolio)
    if 'error' in result:
        print(f"❌ Purchase simulation failed: {result['error']}")
        return False

    print(f"✅ Purchase simulation: ${result['capital_invertido']} -> {result['nuevo_peso_activo']:.2f}% weight")
    return True


def run_portfolio_optimizer():
    """Test del optimizador de portafolio."""
    print("🧪 Testing Portfolio Optimizer...")

    optimizer = PortfolioOptimizer()
    activos = ['SPY', 'EEM', 'QQQ']

    # Test Risk Parity
    result = optimizer.optimize_risk_parity(activos)
    if 'error' in result:
        print(f"❌ Risk Parity failed: {result['error']}")
        return False

    print(f"✅ Risk Parity: Sharpe {result['sharpe_ratio']:.2f}")
    return True


def run_recommendation_engine():
    """Test del motor de recomendaciones."""
    print("🧪 Testing Recommendation Engine...")

    engine = RecommendationEngine()
    recommendations = engine.generate_recommendations()

    if isinstance(recommendations, list):
        print(f"✅ Generated {len(recommendations)} recommendations")
        return True
    else:
        print(f"❌ Recommendation engine failed: {recommendations}")
        return False


def run_monthly_planner():
    """Test del planificador mensual."""
    print("🧪 Testing Monthly Investment Planner...")

    planner = MonthlyInvestmentPlanner()
    result = planner.plan_monthly_investment(Decimal('500000'))

    if 'error' in result:
        print(f"❌ Monthly planner failed: {result['error']}")
        return False

    print(f"✅ Monthly plan: ${result['aporte_mensual']} distributed")
    return True


def run_portfolio_parameters():
    """Test del modelo de parámetros."""
    print("🧪 Testing Portfolio Parameters...")

    # Crear parámetros de prueba
    params = PortfolioParameters.objects.create(
        name="Test Parameters P4",
        liquidez_target=25.00,
        usa_target=35.00,
        argentina_target=25.00,
        emerging_target=15.00
    )

    if params.is_valid_allocation():
        print(f"✅ Parameters valid: {params.get_target_weights_dict()}")
        params.delete()  # Limpiar
        return True
    else:
        print("❌ Parameters invalid")
        params.delete()
        return False


def run_api_endpoints():
    """Test básico de endpoints de API."""
    print("🧪 Testing API Endpoints...")

    from django.test import Client
    client = Client()

    # Test recomendaciones
    response = client.get('/api/recommendations/all/')
    if response.status_code == 200:
        print("✅ Recommendations API working")
    else:
        print(f"❌ Recommendations API failed: {response.status_code}")
        return False

    # Test simulación
    response = client.post('/api/simulation/purchase/',
                          {'activo': 'SPY', 'capital': 100000},
                          content_type='application/json')
    if response.status_code == 200:
        print("✅ Simulation API working")
    else:
        print(f"❌ Simulation API failed: {response.status_code}")
        return False

    return True


def main():
    """Función principal de testing."""
    print("🚀 Iniciando validación de P4 - Motor de Estrategia de Inversión")
    print("=" * 60)

    tests = [
        run_portfolio_simulator,
        run_portfolio_optimizer,
        run_recommendation_engine,
        run_monthly_planner,
        run_portfolio_parameters,
        run_api_endpoints
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {str(e)}")
            print()

    print("=" * 60)
    print(f"📊 Resultados: {passed}/{total} tests pasaron")

    if passed == total:
        print("🎉 ¡P4 implementado exitosamente!")
        print("\nFuncionalidades disponibles:")
        print("• Simulación de portafolio")
        print("• Optimización Risk Parity/Markowitz")
        print("• Motor de recomendaciones automáticas")
        print("• Planificador de aportes mensuales")
        print("• API completa para integración")
        print("• Dashboard estratégico interactivo")
    else:
        print("⚠️  Algunos tests fallaron. Revisar implementación.")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
