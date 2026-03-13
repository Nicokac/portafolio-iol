from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from apps.operaciones_iol.models import OperacionIOL


class OperacionesListView(LoginRequiredMixin, ListView):
    model = OperacionIOL
    template_name = 'operaciones_iol/operaciones_list.html'
    context_object_name = 'operaciones'
    paginate_by = 25
