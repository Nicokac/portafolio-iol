from django.urls import path

from apps.dashboard.views import (
    AnalisisView,
    DashboardView,
    GenerateSnapshotView,
    MetricasView,
    OpsView,
    PlaneacionView,
    PerformanceView,
    FactorExposureDetailView,
    RiskContributionDetailView,
    ScenarioAnalysisDetailView,
    ResumenView,
    RunSyncView,
    SetPreferencesView,
    SyncLocalMacroView,
    SyncBenchmarksView,
)

app_name = 'dashboard'

urlpatterns = [
    path('', ResumenView.as_view(), name='dashboard'),
    path('panel/resumen/', ResumenView.as_view(), name='resumen'),
    path('analisis/', AnalisisView.as_view(), name='analisis'),
    path('analisis/performance/', PerformanceView.as_view(), name='performance'),
    path('analisis/metricas/', MetricasView.as_view(), name='metricas'),
    path('estrategia/', DashboardView.as_view(), name='estrategia'),
    path('estrategia/risk-contribution/', RiskContributionDetailView.as_view(), name='risk_contribution_detail'),
    path('estrategia/scenario-analysis/', ScenarioAnalysisDetailView.as_view(), name='scenario_analysis_detail'),
    path('estrategia/factor-exposure/', FactorExposureDetailView.as_view(), name='factor_exposure_detail'),
    path('planeacion/', PlaneacionView.as_view(), name='planeacion'),
    path('ops/', OpsView.as_view(), name='ops'),
    path('preferencias/', SetPreferencesView.as_view(), name='set_preferences'),
    path('acciones/sync/', RunSyncView.as_view(), name='run_sync'),
    path('acciones/snapshot/', GenerateSnapshotView.as_view(), name='generate_snapshot'),
    path('acciones/benchmarks/', SyncBenchmarksView.as_view(), name='sync_benchmarks'),
    path('acciones/macro-local/', SyncLocalMacroView.as_view(), name='sync_local_macro'),
]
