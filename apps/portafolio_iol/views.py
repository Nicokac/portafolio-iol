from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class PortafolioListView(LoginRequiredMixin, ListView):
    model = ActivoPortafolioSnapshot
    template_name = 'portafolio_iol/portafolio_list.html'
    context_object_name = 'activos'
    paginate_by = 25
