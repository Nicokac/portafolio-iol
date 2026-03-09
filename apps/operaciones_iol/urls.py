from django.urls import path

from apps.operaciones_iol.views import OperacionesListView

app_name = 'operaciones_iol'

urlpatterns = [
    path('', OperacionesListView.as_view(), name='operaciones_list'),
]