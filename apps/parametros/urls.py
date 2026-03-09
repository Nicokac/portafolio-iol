from django.urls import path

from apps.parametros.views import ParametrosListView

app_name = 'parametros'

urlpatterns = [
    path('', ParametrosListView.as_view(), name='parametros_list'),
]