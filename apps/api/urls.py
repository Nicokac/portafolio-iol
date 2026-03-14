from django.urls import path

from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/kpis/', views.dashboard_kpis, name='dashboard-kpis'),
    path('dashboard/concentracion-pais/', views.dashboard_concentracion_pais, name='dashboard-concentracion-pais'),
    path('dashboard/concentracion-sector/', views.dashboard_concentracion_sector, name='dashboard-concentracion-sector'),
    path('dashboard/senales-rebalanceo/', views.dashboard_senales_rebalanceo, name='dashboard-senales-rebalanceo'),

    # Alertas
    path('alerts/active/', views.alerts_active, name='alerts-active'),
    path('alerts/by-severity/', views.alerts_by_severity, name='alerts-by-severity'),

    # Rebalanceo
    path('rebalance/suggestions/', views.rebalance_suggestions, name='rebalance-suggestions'),
    path('rebalance/critical/', views.rebalance_critical_actions, name='rebalance-critical'),
    path('rebalance/opportunity/', views.rebalance_opportunity_actions, name='rebalance-opportunity'),

    # Métricas temporales
    path('metrics/returns/', views.metrics_returns, name='metrics-returns'),
    path('metrics/volatility/', views.metrics_volatility, name='metrics-volatility'),
    path('metrics/performance/', views.metrics_performance, name='metrics-performance'),
    path('metrics/historical-comparison/', views.metrics_historical_comparison, name='metrics-historical-comparison'),
    path('metrics/macro-comparison/', views.metrics_macro_comparison, name='metrics-macro-comparison'),
    path('metrics/var/', views.metrics_var, name='metrics-var'),
    path('metrics/cvar/', views.metrics_cvar, name='metrics-cvar'),
    path('metrics/stress-test/', views.metrics_stress_test, name='metrics-stress-test'),
    path('metrics/attribution/', views.metrics_attribution, name='metrics-attribution'),
    path('metrics/benchmarking/', views.metrics_benchmarking, name='metrics-benchmarking'),
    path('metrics/benchmark-curve/', views.metrics_benchmark_curve, name='metrics-benchmark-curve'),
    path('metrics/liquidity/', views.metrics_liquidity, name='metrics-liquidity'),
    path('metrics/data-quality/', views.metrics_data_quality, name='metrics-data-quality'),
    path('metrics/snapshot-integrity/', views.metrics_snapshot_integrity, name='metrics-snapshot-integrity'),
    path('metrics/sync-audit/', views.metrics_sync_audit, name='metrics-sync-audit'),
    path('metrics/internal-observability/', views.metrics_internal_observability, name='metrics-internal-observability'),

    # Datos históricos
    path('historical/evolution/', views.historical_portfolio_evolution, name='historical-evolution'),
    path('historical/summary/', views.historical_portfolio_summary, name='historical-summary'),

    # P4 - Strategy & Optimization API
    # Simulation
    path('simulation/purchase/', views.simulation_purchase, name='simulation-purchase'),
    path('simulation/sale/', views.simulation_sale, name='simulation-sale'),
    path('simulation/rebalance/', views.simulation_rebalance, name='simulation-rebalance'),

    # Optimization
    path('optimizer/risk-parity/', views.optimizer_risk_parity, name='optimizer-risk-parity'),
    path('optimizer/markowitz/', views.optimizer_markowitz, name='optimizer-markowitz'),
    path('optimizer/target-allocation/', views.optimizer_target_allocation, name='optimizer-target-allocation'),

    # Recommendations
    path('recommendations/all/', views.recommendations_all, name='recommendations-all'),
    path('recommendations/by-priority/', views.recommendations_by_priority, name='recommendations-by-priority'),

    # Monthly Investment Planner
    path('monthly-plan/basic/', views.monthly_plan_basic, name='monthly-plan-basic'),
    path('monthly-plan/custom/', views.monthly_plan_custom, name='monthly-plan-custom'),

    # Portfolio Parameters
    path('portfolio/parameters/', views.portfolio_parameters_get, name='portfolio-parameters-get'),
    path('portfolio/parameters/update/', views.portfolio_parameters_update, name='portfolio-parameters-update'),
]
