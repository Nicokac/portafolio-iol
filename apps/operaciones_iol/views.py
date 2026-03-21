from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView

from apps.core.services.iol_sync_service import IOLSyncService
from apps.core.services.security_audit import record_sensitive_action
from apps.operaciones_iol.models import OperacionIOL


class OperacionesListView(LoginRequiredMixin, ListView):
    model = OperacionIOL
    template_name = 'operaciones_iol/operaciones_list.html'
    context_object_name = 'operaciones'
    paginate_by = 25


class OperacionDetailView(LoginRequiredMixin, DetailView):
    model = OperacionIOL
    template_name = 'operaciones_iol/operacion_detail.html'
    context_object_name = 'operacion'
    slug_field = 'numero'
    slug_url_kwarg = 'numero'
    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs):
        numero = str(kwargs.get(self.slug_url_kwarg) or '').strip()
        service = IOLSyncService()
        success = service.sync_operacion_detalle(numero)
        if success:
            messages.success(request, "Detalle de operación re-sincronizado desde IOL.")
            record_sensitive_action(
                request,
                action='operacion_detail_resync',
                status='success',
                details={'numero': numero},
            )
        else:
            messages.warning(request, "No fue posible re-sincronizar el detalle desde IOL.")
            record_sensitive_action(
                request,
                action='operacion_detail_resync',
                status='failed',
                details={'numero': numero},
            )
        return redirect('operaciones_iol:operacion_detail', numero=numero)

    def get_object(self, queryset=None):
        numero = str(self.kwargs.get(self.slug_url_kwarg) or '').strip()
        if not numero:
            raise Http404("Operacion no encontrada")

        operacion = OperacionIOL.objects.filter(numero=numero).first()
        if operacion is None:
            service = IOLSyncService()
            if not service.sync_operacion_detalle(numero):
                raise Http404("Operacion no encontrada")
            operacion = OperacionIOL.objects.filter(numero=numero).first()
            if operacion is None:
                raise Http404("Operacion no encontrada")
            messages.info(self.request, "Se sincronizó el detalle de la operación desde IOL.")
            return operacion

        if not _has_operation_detail(operacion):
            service = IOLSyncService()
            if service.sync_operacion_detalle(numero):
                operacion = OperacionIOL.objects.filter(numero=numero).first() or operacion
                messages.info(self.request, "Se actualizó el detalle de la operación desde IOL.")
            else:
                messages.warning(self.request, "No fue posible actualizar el detalle desde IOL. Se muestra la información local disponible.")
        return operacion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        operacion = context['operacion']
        context['operation_timeline'] = _build_operation_timeline(operacion.estados_detalle)
        context['operation_fills'] = operacion.operaciones_detalle or []
        context['operation_fees'] = operacion.aranceles_detalle or []
        context['has_operation_detail'] = _has_operation_detail(operacion)
        return context


def _has_operation_detail(operacion: OperacionIOL) -> bool:
    return any(
        [
            bool(operacion.moneda),
            bool(operacion.estado_actual),
            bool(operacion.fecha_alta),
            bool(operacion.validez),
            bool(operacion.estados_detalle),
            bool(operacion.aranceles_detalle),
            bool(operacion.operaciones_detalle),
            operacion.monto_operacion is not None,
            operacion.aranceles_ars is not None,
            operacion.aranceles_usd is not None,
        ]
    )


def _build_operation_timeline(estados_detalle: list[dict] | None) -> list[dict]:
    timeline = []
    for index, estado in enumerate(estados_detalle or []):
        detail = str(estado.get('detalle') or 'Sin detalle')
        normalized = detail.strip().lower()
        if 'termin' in normalized:
            tone = 'success'
        elif 'cancel' in normalized or 'rechaz' in normalized:
            tone = 'danger'
        elif 'proceso' in normalized:
            tone = 'warning'
        else:
            tone = 'secondary'
        timeline.append(
            {
                'step': index + 1,
                'detail': detail,
                'fecha': estado.get('fecha') or '',
                'tone': tone,
            }
        )
    return timeline
