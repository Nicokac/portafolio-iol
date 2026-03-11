from django.urls import path

from apps.dashboard.views import AnalisisView, DashboardView, ResumenView, SetPreferencesView

app_name = 'dashboard'

urlpatterns = [
    path('', ResumenView.as_view(), name='dashboard'),
    path('panel/resumen/', ResumenView.as_view(), name='resumen'),
    path('analisis/', AnalisisView.as_view(), name='analisis'),
    path('estrategia/', DashboardView.as_view(), name='estrategia'),
    path('preferencias/', SetPreferencesView.as_view(), name='set_preferences'),
]
