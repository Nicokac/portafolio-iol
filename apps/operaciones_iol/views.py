from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView
from django.views import View

from apps.core.services.iol_sync_service import IOLSyncService
from apps.core.services.security_audit import record_sensitive_action
from apps.operaciones_iol.models import OperacionIOL
from apps.operaciones_iol.selectors import (
    apply_operation_filters,
    build_operation_filter_context,
    build_operation_list_context,
    build_operation_universe_coverage_context,
    get_operation_subset_for_country_backfill,
    get_operation_subset_for_detail_enrichment,
    has_operation_detail,
    normalize_operation_filters,
)


class OperacionesListView(LoginRequiredMixin, ListView):
    model = OperacionIOL
    template_name = 'operaciones_iol/operaciones_list.html'
    context_object_name = 'operaciones'
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        self.normalized_filters = normalize_operation_filters(self.request.GET)
        self.filtered_queryset = apply_operation_filters(queryset, self.normalized_filters)
        return self.filtered_queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        list_context = build_operation_list_context(context['operaciones'])
        universe_coverage = build_operation_universe_coverage_context(getattr(self, 'filtered_queryset', OperacionIOL.objects.none()))
        filter_context = build_operation_filter_context(getattr(self, 'normalized_filters', {}))
        context['operation_rows'] = list_context['rows']
        context['operations_summary'] = list_context['summary']
        context['operations_universe_coverage'] = universe_coverage
        context['operation_filters'] = filter_context
        return context


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return bool(self.request.user and self.request.user.is_staff)


class SyncOperacionesFilteredView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs) -> HttpResponse:
        normalized_filters = normalize_operation_filters(request.POST)
        sync_filters = {
            key: value
            for key, value in normalized_filters.items()
            if (
                (key == 'estado' and value != 'todas')
                or (key == 'pais' and value)
                or (key not in {'estado', 'pais'} and value)
            )
        }
        success = IOLSyncService().sync_operaciones(sync_filters or None)
        record_sensitive_action(
            request,
            action='sync_operaciones_filtered',
            status='success' if success else 'failed',
            details={'filters': normalized_filters},
        )
        if success:
            messages.success(request, 'Operaciones sincronizadas desde IOL con los filtros solicitados.')
        else:
            messages.warning(request, 'No fue posible sincronizar operaciones desde IOL con los filtros solicitados.')
        redirect_url = reverse('operaciones_iol:operaciones_list')
        filter_context = build_operation_filter_context(normalized_filters)
        if filter_context['query_string']:
            redirect_url = f"{redirect_url}?{filter_context['query_string']}"
        return redirect(redirect_url)


class EnrichOperacionesFilteredDetailsView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs) -> HttpResponse:
        normalized_filters = normalize_operation_filters(request.POST)
        page_number = request.POST.get('page') or 1
        queryset = apply_operation_filters(OperacionIOL.objects.all(), normalized_filters)
        subset = get_operation_subset_for_detail_enrichment(
            queryset,
            page_number=page_number,
            page_size=OperacionesListView.paginate_by,
        )

        success_count = 0
        failed_numbers: list[str] = []
        service = IOLSyncService()
        for operacion in subset:
            if service.sync_operacion_detalle(operacion.numero):
                success_count += 1
            else:
                failed_numbers.append(str(operacion.numero))

        audit_status = 'failed' if failed_numbers else 'success'
        record_sensitive_action(
            request,
            action='enrich_operaciones_filtered_details',
            status=audit_status,
            details={
                'filters': normalized_filters,
                'page': str(page_number),
                'selected_count': len(subset),
                'success_count': success_count,
                'failed_numbers': failed_numbers,
            },
        )

        if not subset:
            messages.info(request, 'No hay operaciones sin detalle para enriquecer en la pagina filtrada actual.')
        elif failed_numbers:
            messages.warning(
                request,
                f'Detalle IOL enriquecido parcialmente. OK={success_count}, fallidas={len(failed_numbers)}.',
            )
        else:
            messages.success(request, f'Detalle IOL enriquecido para {success_count} operacion(es) de la pagina actual.')

        redirect_url = reverse('operaciones_iol:operaciones_list')
        filter_context = build_operation_filter_context(normalized_filters)
        query_params = filter_context['query_string']
        if page_number:
            page_segment = f"page={page_number}"
            query_params = f"{query_params}&{page_segment}" if query_params else page_segment
        if query_params:
            redirect_url = f"{redirect_url}?{query_params}"
        return redirect(redirect_url)


class BackfillOperacionesFilteredCountryView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs) -> HttpResponse:
        normalized_filters = normalize_operation_filters(request.POST)
        page_number = request.POST.get('page') or 1
        queryset = apply_operation_filters(OperacionIOL.objects.all(), normalized_filters)
        subset = get_operation_subset_for_country_backfill(
            queryset,
            page_number=page_number,
            page_size=OperacionesListView.paginate_by,
        )

        resolved_count = 0
        unresolved_numbers: list[str] = []
        service = IOLSyncService()
        for operacion in subset:
            matched = False
            for pais in ('argentina', 'estados_Unidos'):
                if service.sync_operaciones({'numero': operacion.numero, 'pais': pais}):
                    operacion.refresh_from_db()
                    if str(operacion.pais_consulta or '').strip():
                        resolved_count += 1
                        matched = True
                        break
            if not matched:
                unresolved_numbers.append(str(operacion.numero))

        audit_status = 'failed' if unresolved_numbers else 'success'
        record_sensitive_action(
            request,
            action='backfill_operaciones_filtered_country',
            status=audit_status,
            details={
                'filters': normalized_filters,
                'page': str(page_number),
                'selected_count': len(subset),
                'resolved_count': resolved_count,
                'unresolved_numbers': unresolved_numbers,
            },
        )

        if not subset:
            messages.info(request, 'No hay operaciones sin pais_consulta para backfill en la pagina filtrada actual.')
        elif unresolved_numbers:
            messages.warning(
                request,
                f'Backfill de pais_consulta parcial. OK={resolved_count}, sin resolver={len(unresolved_numbers)}.',
            )
        else:
            messages.success(request, f'pais_consulta resuelto para {resolved_count} operacion(es) de la pagina actual.')

        redirect_url = reverse('operaciones_iol:operaciones_list')
        filter_context = build_operation_filter_context(normalized_filters)
        query_params = filter_context['query_string']
        if page_number:
            page_segment = f"page={page_number}"
            query_params = f"{query_params}&{page_segment}" if query_params else page_segment
        if query_params:
            redirect_url = f"{redirect_url}?{query_params}"
        return redirect(redirect_url)


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
            messages.success(request, 'Detalle de operacion re-sincronizado desde IOL.')
            record_sensitive_action(
                request,
                action='operacion_detail_resync',
                status='success',
                details={'numero': numero},
            )
        else:
            messages.warning(request, 'No fue posible re-sincronizar el detalle desde IOL.')
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
            raise Http404('Operacion no encontrada')

        operacion = OperacionIOL.objects.filter(numero=numero).first()
        if operacion is None:
            service = IOLSyncService()
            if not service.sync_operacion_detalle(numero):
                raise Http404('Operacion no encontrada')
            operacion = OperacionIOL.objects.filter(numero=numero).first()
            if operacion is None:
                raise Http404('Operacion no encontrada')
            messages.info(self.request, 'Se sincronizo el detalle de la operacion desde IOL.')
            return operacion

        if not has_operation_detail(operacion):
            service = IOLSyncService()
            if service.sync_operacion_detalle(numero):
                operacion = OperacionIOL.objects.filter(numero=numero).first() or operacion
                messages.info(self.request, 'Se actualizo el detalle de la operacion desde IOL.')
            else:
                messages.warning(self.request, 'No fue posible actualizar el detalle desde IOL. Se muestra la informacion local disponible.')
        return operacion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        operacion = context['operacion']
        context['operation_timeline'] = _build_operation_timeline(operacion.estados_detalle)
        context['operation_fills'] = operacion.operaciones_detalle or []
        context['operation_fees'] = operacion.aranceles_detalle or []
        context['has_operation_detail'] = has_operation_detail(operacion)
        return context



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
