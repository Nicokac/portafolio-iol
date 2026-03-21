from django.urls import path

from apps.operaciones_iol.views import OperacionDetailView, OperacionesListView

app_name = 'operaciones_iol'

urlpatterns = [
    path('', OperacionesListView.as_view(), name='operaciones_list'),
    path('<slug:numero>/', OperacionDetailView.as_view(), name='operacion_detail'),
]
