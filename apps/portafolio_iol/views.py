from django.views.generic import ListView

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class PortafolioListView(ListView):
    model = ActivoPortafolioSnapshot
    template_name = 'portafolio_iol/portafolio_list.html'
    context_object_name = 'activos'
    paginate_by = 25