from django.urls import path

from apps.resumen_iol.views import ResumenListView

app_name = 'resumen_iol'

urlpatterns = [
    path('', ResumenListView.as_view(), name='resumen_list'),
]