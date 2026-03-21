from django.urls import path

from apps.operaciones_iol.views import (
    EnrichOperacionesFilteredDetailsView,
    OperacionDetailView,
    OperacionesListView,
    SyncOperacionesFilteredView,
)

app_name = 'operaciones_iol'

urlpatterns = [
    path('', OperacionesListView.as_view(), name='operaciones_list'),
    path('sync/', SyncOperacionesFilteredView.as_view(), name='sync_operaciones_filtered'),
    path('enrich-details/', EnrichOperacionesFilteredDetailsView.as_view(), name='enrich_operaciones_filtered_details'),
    path('<slug:numero>/', OperacionDetailView.as_view(), name='operacion_detail'),
]
