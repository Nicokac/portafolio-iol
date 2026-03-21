from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.portafolio_iol.selectors import build_portafolio_list_context


class PortafolioListView(LoginRequiredMixin, ListView):
    model = ActivoPortafolioSnapshot
    template_name = 'portafolio_iol/portafolio_list.html'
    context_object_name = 'activos'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        portafolio_context = build_portafolio_list_context(context["activos"])
        context["portafolio_rows"] = portafolio_context["rows"]
        context["portafolio_summary"] = portafolio_context["summary"]
        return context
