from django.urls import path

from apps.portafolio_iol.views import PortafolioListView

app_name = 'portafolio_iol'

urlpatterns = [
    path('', PortafolioListView.as_view(), name='portafolio_list'),
]