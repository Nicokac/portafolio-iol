from django.urls import path

from apps.dashboard.views import (
    AnalisisView,
    DashboardView,
    GenerateSnapshotView,
    MetricasView,
    OpsView,
    PerformanceView,
    ResumenView,
    RunSyncView,
    SetPreferencesView,
)

app_name = 'dashboard'

urlpatterns = [
    path('', ResumenView.as_view(), name='dashboard'),
    path('panel/resumen/', ResumenView.as_view(), name='resumen'),
    path('analisis/', AnalisisView.as_view(), name='analisis'),
    path('analisis/performance/', PerformanceView.as_view(), name='performance'),
    path('analisis/metricas/', MetricasView.as_view(), name='metricas'),
    path('estrategia/', DashboardView.as_view(), name='estrategia'),
    path('ops/', OpsView.as_view(), name='ops'),
    path('preferencias/', SetPreferencesView.as_view(), name='set_preferences'),
    path('acciones/sync/', RunSyncView.as_view(), name='run_sync'),
    path('acciones/snapshot/', GenerateSnapshotView.as_view(), name='generate_snapshot'),
]
