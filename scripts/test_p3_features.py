#!/usr/bin/env python
"""
Script de ejemplo para probar funcionalidades de P3
Ejecutar con: python scripts/test_p3_features.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.core.services.alerts_engine import AlertsEngine
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.core.services.rebalance_engine import RebalanceEngine
from apps.core.services.temporal_metrics_service import TemporalMetricsService
from apps.dashboard.selectors import get_dashboard_kpis


def run_snapshot_service():
    """Probar servicio de snapshots."""
    print("=== Testing PortfolioSnapshotService ===")

    service = PortfolioSnapshotService()

    # Generar snapshot diario
    print("Generating daily snapshot...")
    result = service.generate_daily_snapshot()
    print(f"Result: {result}")

    # Sincronizar datos IOL
    print("\nSyncing IOL data...")
    result = service.sync_iol_data()
    print(f"Result: {result}")


def run_alerts_engine():
    """Probar motor de alertas."""
    print("\n=== Testing AlertsEngine ===")

    engine = AlertsEngine()

    # Generar alertas
    print("Generating alerts...")
    alerts = engine.generate_alerts()
    print(f"Generated {len(alerts)} alerts:")

    for alert in alerts:
        print(f"  [{alert['severidad'].upper()}] {alert['mensaje']}")

    # Alertas por severidad
    print("\nCritical alerts:")
    critical = engine.get_alerts_by_severity('critical')
    for alert in critical:
        print(f"  {alert['mensaje']}")


def run_rebalance_engine():
    """Probar motor de rebalanceo."""
    print("\n=== Testing RebalanceEngine ===")

    engine = RebalanceEngine()

    # Generar sugerencias
    print("Generating rebalance suggestions...")
    suggestions = engine.generate_rebalance_suggestions()
    print(f"Generated {len(suggestions)} suggestions:")

    for suggestion in suggestions:
        print(f"  {suggestion.get('razon', 'N/A')}: {suggestion}")

    # Acciones críticas
    print("\nCritical actions:")
    critical = engine.get_critical_actions()
    for action in critical:
        print(f"  {action}")


def run_temporal_metrics():
    """Probar métricas temporales."""
    print("\n=== Testing TemporalMetricsService ===")

    service = TemporalMetricsService()

    # Retornos
    print("Calculating returns...")
    returns = service.get_portfolio_returns(days=30)
    print(f"Returns: {returns}")

    # Volatilidad
    print("\nCalculating volatility...")
    volatility = service.get_portfolio_volatility(days=30)
    print(f"Volatility: {volatility}")

    # Métricas completas
    print("\nCalculating comprehensive metrics...")
    metrics = service.get_performance_metrics(days=30)
    print(f"Metrics keys: {list(metrics.keys())}")


def run_dashboard_kpis():
    """Probar KPIs del dashboard."""
    print("\n=== Testing Dashboard KPIs ===")

    kpis = get_dashboard_kpis()
    print(f"KPIs keys: {list(kpis.keys()) if kpis else 'No KPIs available'}")

    if kpis:
        print("Sample KPIs:")
        for key, value in list(kpis.items())[:5]:
            print(f"  {key}: {value}")


def main():
    """Función principal."""
    print("Testing P3 Features - Portafolio IOL")
    print("=" * 50)

    try:
        run_dashboard_kpis()
        run_snapshot_service()
        run_alerts_engine()
        run_rebalance_engine()
        run_temporal_metrics()

        print("\n" + "=" * 50)
        print("All tests completed successfully!")

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
