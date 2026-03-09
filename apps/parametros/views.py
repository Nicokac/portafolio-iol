from django.views.generic import ListView

from apps.parametros.models import ParametroActivo


class ParametrosListView(ListView):
    model = ParametroActivo
    template_name = 'parametros/parametros_list.html'
    context_object_name = 'parametros'
    paginate_by = 25