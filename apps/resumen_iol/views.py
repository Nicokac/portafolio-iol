from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from apps.resumen_iol.models import ResumenCuentaSnapshot


class ResumenListView(LoginRequiredMixin, ListView):
    model = ResumenCuentaSnapshot
    template_name = 'resumen_iol/resumen_list.html'
    context_object_name = 'resumenes'
    paginate_by = 25
