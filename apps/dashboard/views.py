import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django_celery_beat.models import PeriodicTask
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView
from django.views import View
from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.core.services.data_quality.daily_snapshot_continuity_service import DailySnapshotContinuityService
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.core.services.iol_sync_service import IOLSyncService
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.observability import record_state
from apps.core.services.pipeline_observability_service import PipelineObservabilityService
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.core.services.benchmark_series_service import BenchmarkSeriesService
from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.core.services.security_audit import record_sensitive_action
from apps.dashboard.selectors import (
    get_analytics_v2_dashboard_summary,
    get_analytics_mensual,
    get_active_alerts,
    get_concentracion_pais,
    get_concentracion_sector,
    get_concentracion_sector_agregado,
    get_concentracion_tipo_patrimonial,
    get_decision_engine_summary,
    get_planeacion_incremental_context,
    get_preferred_incremental_portfolio_proposal,
    get_concentracion_moneda,
    get_concentracion_moneda_operativa,
    get_dashboard_kpis,
    get_distribucion_moneda,
    get_distribucion_moneda_operativa,
    get_distribucion_pais,
    get_distribucion_sector,
    get_distribucion_tipo_patrimonial,
    get_evolucion_historica,
    get_expected_return_detail,
    get_incremental_proposal_history,
    get_macro_local_context,
    get_market_snapshot_feature_context,
    get_market_snapshot_history_feature_context,
    get_portfolio_parking_feature_context,
    get_portafolio_enriquecido_actual,
    get_factor_exposure_detail,
    get_risk_contribution_detail,
    get_scenario_analysis_detail,
    get_stress_fragility_detail,
    get_riesgo_portafolio,
    get_riesgo_portafolio_detallado,
    get_snapshot_coverage_summary,
    get_senales_rebalanceo,
)


ALLOWED_UI_MODES = {'compacto', 'denso'}
ALLOWED_RISK_PROFILES = {'conservador', 'moderado', 'agresivo'}


def _build_planeacion_history_redirect_url(post_data) -> str:
    redirect_url = reverse('dashboard:planeacion')
    query = QueryDict(mutable=True)

    decision_status_filter = str(post_data.get('decision_status_filter', '') or '').strip()
    history_priority_filter = str(post_data.get('history_priority_filter', '') or '').strip()
    history_deferred_fit_filter = str(post_data.get('history_deferred_fit_filter', '') or '').strip()
    history_sort = str(post_data.get('history_sort', '') or '').strip()

    if decision_status_filter:
        query['decision_status_filter'] = decision_status_filter
    if history_priority_filter:
        query['history_priority_filter'] = history_priority_filter
    if history_deferred_fit_filter:
        query['history_deferred_fit_filter'] = history_deferred_fit_filter
    if history_sort:
        query['history_sort'] = history_sort

    encoded = query.urlencode()
    if encoded:
        return f"{redirect_url}?{encoded}#planeacion-aportes"
    return f"{redirect_url}#planeacion-aportes"


class DashboardContextMixin:
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['active_section'] = self.active_section
        context['ui_mode'] = self.request.session.get('ui_mode', 'compacto')
        context['risk_profile'] = self.request.session.get('risk_profile', 'moderado')
        context['current_path'] = self.request.get_full_path()

        context['kpis'] = get_dashboard_kpis()
        context['macro_local'] = get_macro_local_context(context['kpis'].get('total_iol'))
        context['portafolio'] = get_portafolio_enriquecido_actual()
        context['market_snapshot_feature'] = get_market_snapshot_feature_context()
        context['market_snapshot_history_feature'] = get_market_snapshot_history_feature_context()
        context['parking_feature'] = get_portfolio_parking_feature_context()

        def to_json(data):
            return json.dumps(data, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))

        context['distribucion_sector'] = to_json(get_distribucion_sector(base='portafolio_invertido'))
        context['distribucion_pais'] = to_json(get_distribucion_pais(base='portafolio_invertido'))
        context['distribucion_pais_total_iol'] = to_json(get_distribucion_pais(base='total_iol'))
        context['distribucion_tipo'] = to_json(get_distribucion_tipo_patrimonial(base='total_activos'))
        context['distribucion_moneda'] = to_json(get_distribucion_moneda())
        context['distribucion_moneda_operativa'] = to_json(get_distribucion_moneda_operativa())
        context['riesgo_portafolio'] = get_riesgo_portafolio()
        context['riesgo_portafolio_detallado'] = get_riesgo_portafolio_detallado()
        context['concentracion_sector'] = get_concentracion_sector()
        context['concentracion_sector_agregado'] = get_concentracion_sector_agregado()
        context['concentracion_pais'] = get_concentracion_pais(base='portafolio_invertido')
        context['concentracion_pais_total_iol'] = get_concentracion_pais(base='total_iol')
        context['concentracion_tipo'] = get_concentracion_tipo_patrimonial(base='total_activos')
        context['concentracion_sector_json'] = to_json(get_concentracion_sector())
        context['concentracion_sector_agregado_json'] = to_json(get_concentracion_sector_agregado())
        context['concentracion_pais_json'] = to_json(get_concentracion_pais(base='portafolio_invertido'))
        context['concentracion_pais_total_iol_json'] = to_json(get_concentracion_pais(base='total_iol'))
        context['concentracion_tipo_json'] = to_json(get_concentracion_tipo_patrimonial(base='total_activos'))
        context['concentracion_moneda_json'] = to_json(get_concentracion_moneda())
        context['concentracion_moneda_operativa_json'] = to_json(get_concentracion_moneda_operativa())
        context['analytics_mensual'] = get_analytics_mensual()
        context['analytics_v2_summary'] = get_analytics_v2_dashboard_summary()

        evolucion_historica_obj = get_evolucion_historica()
        context['evolucion_historica_obj'] = evolucion_historica_obj
        context['evolucion_historica'] = to_json(evolucion_historica_obj)

        context['senales_rebalanceo'] = get_senales_rebalanceo()
        context['snapshot_integrity'] = SnapshotIntegrityService().run_checks(days=120)
        context['snapshot_coverage'] = get_snapshot_coverage_summary(days=90)
        context['sync_audit'] = IOLSyncAuditService().run_audit(freshness_hours=24)

        alerts = get_active_alerts()
        context['alerts'] = alerts
        context['alerts_critical_count'] = sum(1 for alert in alerts if alert.get('severidad') == 'critical')
        context['alerts_warning_count'] = sum(1 for alert in alerts if alert.get('severidad') == 'warning')
        return context


class DashboardView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/estrategia.html'
    active_section = 'estrategia'


class RiskContributionDetailView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/risk_contribution_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['risk_contribution_detail'] = get_risk_contribution_detail()
        return context


class ScenarioAnalysisDetailView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/scenario_analysis_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['scenario_analysis_detail'] = get_scenario_analysis_detail()
        return context


class FactorExposureDetailView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/factor_exposure_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['factor_exposure_detail'] = get_factor_exposure_detail()
        return context


class StressFragilityDetailView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/stress_fragility_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stress_fragility_detail'] = get_stress_fragility_detail()
        return context


class ExpectedReturnDetailView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/expected_return_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expected_return_detail'] = get_expected_return_detail()
        return context


class PlaneacionView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/planeacion.html'
    active_section = 'planeacion'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            get_planeacion_incremental_context(
                self.request.GET,
                user=self.request.user,
                capital_amount=600000,
                history_limit=5,
            )
        )
        return context


class ResumenView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/resumen.html'
    active_section = 'resumen'


class AnalisisView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/analisis.html'
    active_section = 'analisis'


class PerformanceView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/performance.html'
    active_section = 'analisis'


class MetricasView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/metricas.html'
    active_section = 'analisis'


class OpsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/ops.html'
    active_section = 'analisis'

    def test_func(self):
        return bool(self.request.user and self.request.user.is_staff)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pipeline_observability = PipelineObservabilityService().build_summary(lookback_days=30, integrity_days=120)
        context['pipeline_observability'] = pipeline_observability
        context['benchmark_status'] = pipeline_observability['benchmark_status_rows']
        context['local_macro_status'] = pipeline_observability['local_macro_status_rows']
        context['snapshot_coverage'] = get_snapshot_coverage_summary(days=90)
        context['snapshot_continuity'] = DailySnapshotContinuityService().build_report(lookback_days=14)
        context['periodic_tasks_count'] = PeriodicTask.objects.count()
        return context


class SetPreferencesView(LoginRequiredMixin, TemplateView):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        ui_mode = request.POST.get('ui_mode')
        risk_profile = request.POST.get('risk_profile')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'

        if ui_mode in ALLOWED_UI_MODES:
            request.session['ui_mode'] = ui_mode
        if risk_profile in ALLOWED_RISK_PROFILES:
            request.session['risk_profile'] = risk_profile

        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = '/'

        return redirect(next_url)


class SavePreferredIncrementalProposalView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        source_query = request.POST.get('source_query', '')
        query_params = QueryDict(source_query, mutable=False)
        detail = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=600000)
        decision = get_decision_engine_summary(request.user, query_params=query_params, capital_amount=600000)
        preferred = detail.get('preferred')
        redirect_url = reverse('dashboard:planeacion')
        if source_query:
            redirect_url = f"{redirect_url}?{source_query}#planeacion-aportes"
        else:
            redirect_url = f"{redirect_url}#planeacion-aportes"

        if not preferred:
            record_sensitive_action(
                request,
                action='save_incremental_proposal',
                status='denied',
                details={'reason': 'missing_preferred_proposal'},
            )
            messages.error(request, "No hay una propuesta incremental preferida construible para guardar.")
            return redirect(redirect_url)

        try:
            saved = IncrementalProposalHistoryService().save_preferred_proposal(
                user=request.user,
                preferred_payload=preferred,
                decision_payload=decision,
                explanation=detail.get('explanation', ''),
                capital_amount=600000,
            )
        except ValueError as exc:
            record_sensitive_action(
                request,
                action='save_incremental_proposal',
                status='failed',
                details={'reason': str(exc)},
            )
            messages.error(request, "No fue posible guardar la propuesta incremental actual.")
            return redirect(redirect_url)

        record_sensitive_action(
            request,
            action='save_incremental_proposal',
            status='success',
            details={
                'proposal_label': saved['proposal_label'],
                'source_key': saved['source_key'],
            },
        )
        messages.success(request, f"Propuesta incremental guardada: {saved['proposal_label']}.")
        return redirect(redirect_url)


class PromoteIncrementalProposalBaselineView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        snapshot_id = request.POST.get('snapshot_id')
        redirect_url = _build_planeacion_history_redirect_url(request.POST)

        try:
            saved = IncrementalProposalHistoryService().promote_to_tracking_baseline(
                user=request.user,
                snapshot_id=snapshot_id,
            )
        except ValueError as exc:
            record_sensitive_action(
                request,
                action='promote_incremental_baseline',
                status='failed',
                details={'reason': str(exc), 'snapshot_id': snapshot_id},
            )
            messages.error(request, "No fue posible promover el snapshot incremental a baseline de seguimiento.")
            return redirect(redirect_url)

        record_sensitive_action(
            request,
            action='promote_incremental_baseline',
            status='success',
            details={'snapshot_id': saved['id'], 'proposal_label': saved['proposal_label']},
        )
        messages.success(request, f"Baseline incremental activo: {saved['proposal_label']}.")
        return redirect(redirect_url)


class PromoteIncrementalBacklogFrontView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        snapshot_id = request.POST.get('snapshot_id')
        redirect_url = _build_planeacion_history_redirect_url(request.POST)

        try:
            promoted = IncrementalProposalHistoryService().promote_to_backlog_front(
                user=request.user,
                snapshot_id=snapshot_id,
            )
        except ValueError as exc:
            record_sensitive_action(
                request,
                action='promote_incremental_backlog_front',
                status='failed',
                details={'reason': str(exc), 'snapshot_id': snapshot_id},
            )
            messages.error(request, "No fue posible promover el snapshot al frente del backlog incremental.")
            return redirect(redirect_url)

        record_sensitive_action(
            request,
            action='promote_incremental_backlog_front',
            status='success',
            details={'snapshot_id': promoted['id'], 'proposal_label': promoted['proposal_label']},
        )
        messages.success(request, f"Snapshot al frente del backlog: {promoted['proposal_label']}.")
        return redirect(redirect_url)


class DecideIncrementalProposalView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        snapshot_id = request.POST.get('snapshot_id')
        decision_status = request.POST.get('decision_status')
        decision_note = request.POST.get('decision_note', '')
        redirect_url = _build_planeacion_history_redirect_url(request.POST)

        try:
            decided = IncrementalProposalHistoryService().decide_snapshot(
                user=request.user,
                snapshot_id=snapshot_id,
                decision_status=decision_status,
                note=decision_note,
            )
        except ValueError as exc:
            record_sensitive_action(
                request,
                action='decide_incremental_proposal',
                status='failed',
                details={'reason': str(exc), 'snapshot_id': snapshot_id, 'decision_status': decision_status},
            )
            messages.error(request, "No fue posible registrar la decision manual sobre la propuesta incremental.")
            return redirect(redirect_url)

        record_sensitive_action(
            request,
            action='decide_incremental_proposal',
            status='success',
            details={
                'snapshot_id': decided['id'],
                'proposal_label': decided['proposal_label'],
                'decision_status': decided['manual_decision_status'],
            },
        )
        messages.success(
            request,
            f"Decision manual registrada: {decided['proposal_label']} -> {decided['manual_decision_status']}.",
        )
        return redirect(redirect_url)


class BulkDecideIncrementalProposalView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        decision_status = request.POST.get('decision_status')
        decision_status_filter = request.POST.get('decision_status_filter', '')
        priority_filter = request.POST.get('history_priority_filter', '')
        deferred_fit_filter = request.POST.get('history_deferred_fit_filter', '')
        sort_mode = request.POST.get('history_sort', '')
        history = get_incremental_proposal_history(
            user=request.user,
            limit=5,
            decision_status=decision_status_filter or None,
            priority_filter=priority_filter or None,
            deferred_fit_filter=deferred_fit_filter or None,
            sort_mode=sort_mode or None,
        )
        snapshot_ids = [item.get('id') for item in history.get('items', []) if item.get('id') is not None]
        redirect_url = _build_planeacion_history_redirect_url(request.POST)

        try:
            result = IncrementalProposalHistoryService().decide_many_snapshots(
                user=request.user,
                snapshot_ids=snapshot_ids,
                decision_status=decision_status,
            )
        except ValueError as exc:
            record_sensitive_action(
                request,
                action='bulk_decide_incremental_proposal',
                status='failed',
                details={
                    'reason': str(exc),
                    'decision_status': decision_status,
                    'filter': decision_status_filter,
                    'priority_filter': priority_filter or 'all',
                    'deferred_fit_filter': deferred_fit_filter or 'all',
                    'sort_mode': sort_mode or 'newest',
                },
            )
            messages.error(request, "No fue posible registrar la decisión masiva sobre el historial incremental visible.")
            return redirect(redirect_url)

        record_sensitive_action(
            request,
            action='bulk_decide_incremental_proposal',
            status='success',
            details={
                'decision_status': result['decision_status'],
                'updated_count': result['updated_count'],
                'filter': decision_status_filter or 'all',
                'priority_filter': priority_filter or 'all',
                'deferred_fit_filter': deferred_fit_filter or 'all',
                'sort_mode': sort_mode or 'newest',
            },
        )
        messages.success(
            request,
            f"Decisión masiva aplicada a {result['updated_count']} snapshot(s) visibles.",
        )
        return redirect(redirect_url)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return bool(self.request.user and self.request.user.is_staff)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        return UserPassesTestMixin.handle_no_permission(self)


class RunSyncView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        results = IOLSyncService().sync_all()
        success = bool(results.get('estado_cuenta') and results.get('portafolio_argentina'))
        record_sensitive_action(
            request,
            action='manual_sync',
            status='success' if success else 'failed',
            details={'results': results},
        )
        if success:
            snapshot_status = 'ok' if results.get('portfolio_snapshot') else 'sin snapshot'
            messages.success(
                request,
                f"Sincronizacion completada. Snapshot diario: {snapshot_status}."
            )
        else:
            failed = [key for key, value in results.items() if value is False]
            failed_text = ", ".join(failed) if failed else "sync"
            messages.error(request, f"Sincronizacion incompleta. Fallo en: {failed_text}.")
        return redirect('dashboard:resumen')


class GenerateSnapshotView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        snapshot = PortfolioSnapshotService().generate_daily_snapshot()
        record_sensitive_action(
            request,
            action='generate_snapshot',
            status='success' if snapshot is not None else 'failed',
            details={'snapshot_date': str(snapshot.fecha) if snapshot is not None else None},
        )
        if snapshot is not None:
            action = getattr(snapshot, "_refresh_action", "created")
            if action == "refreshed":
                messages.success(request, f"Snapshot actualizado para {snapshot.fecha}.")
            else:
                messages.success(request, f"Snapshot disponible para {snapshot.fecha}.")
        else:
            messages.error(request, "No fue posible generar el snapshot.")
        return redirect('dashboard:resumen')


class SyncBenchmarksView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            result = BenchmarkSeriesService().sync_all(outputsize='compact')
            has_failures = any(not payload.get('success', True) for payload in result.values())
            record_sensitive_action(
                request,
                action='sync_benchmarks',
                status='failed' if has_failures else 'success',
                details={'result': result},
            )
            completed = ", ".join(
                f"{key}: {payload['rows_received']} rows"
                for key, payload in result.items()
            )
            if has_failures:
                messages.warning(request, f"Benchmarks sincronizados con fallos parciales. {completed}.")
            else:
                messages.success(request, f"Benchmarks sincronizados. {completed}.")
        except Exception as exc:
            record_sensitive_action(
                request,
                action='sync_benchmarks',
                status='failed',
                details={'reason': 'exception', 'message': str(exc)},
            )
            messages.error(request, "No fue posible sincronizar benchmarks historicos.")
        return redirect('dashboard:ops')


class SyncLocalMacroView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            result = LocalMacroSeriesService().sync_all()
            summary = LocalMacroSeriesService.summarize_sync_result(result)
            record_state(summary['metric_name'], summary['state'], summary['extra'])
            has_failures = any(not payload.get('success', True) for payload in result.values())
            record_sensitive_action(
                request,
                action='sync_local_macro',
                status='failed' if has_failures else 'success',
                details={'result': result},
            )
            completed = ", ".join(
                (
                    f"{key}: skipped"
                    if payload.get('skipped')
                    else f"{key}: {payload['rows_received']} rows"
                )
                for key, payload in result.items()
            )
            if has_failures:
                messages.warning(request, f"Macro local sincronizada con fallos parciales. {completed}.")
            else:
                messages.success(request, f"Macro local sincronizada. {completed}.")
        except Exception as exc:
            record_sensitive_action(
                request,
                action='sync_local_macro',
                status='failed',
                details={'reason': 'exception', 'message': str(exc)},
            )
            messages.error(request, "No fue posible sincronizar macro local.")
        return redirect('dashboard:ops')


class SyncIOLHistoricalPricesView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            result = IOLHistoricalPriceService().sync_current_portfolio_symbols_by_status(statuses=('missing',))
            has_failures = any(not payload.get('success', True) for payload in result.get('results', {}).values())
            audit_status = 'failed' if has_failures else 'success'
            record_sensitive_action(
                request,
                action='sync_iol_historical_prices',
                status=audit_status,
                details={'result': result, 'statuses': ['missing']},
            )

            selected_count = int(result.get('selected_count') or 0)
            if selected_count == 0:
                messages.info(request, "No hay símbolos faltantes para sincronizar históricos IOL.")
            else:
                completed = ", ".join(
                    f"{key}: {payload.get('rows_received', 0)} rows"
                    for key, payload in result.get('results', {}).items()
                )
                if has_failures:
                    messages.warning(request, f"Históricos IOL sincronizados con fallos parciales. {completed}.")
                else:
                    messages.success(request, f"Históricos IOL sincronizados para símbolos faltantes. {completed}.")
        except Exception as exc:
            record_sensitive_action(
                request,
                action='sync_iol_historical_prices',
                status='failed',
                details={'reason': 'exception', 'message': str(exc), 'statuses': ['missing']},
            )
            messages.error(request, "No fue posible sincronizar históricos IOL faltantes.")
        return redirect('dashboard:ops')


class SyncIOLHistoricalPricesPartialView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            result = IOLHistoricalPriceService().sync_current_portfolio_symbols_by_status(statuses=('partial',))
            has_failures = any(not payload.get('success', True) for payload in result.get('results', {}).values())
            audit_status = 'failed' if has_failures else 'success'
            record_sensitive_action(
                request,
                action='sync_iol_historical_prices_partial',
                status=audit_status,
                details={'result': result, 'statuses': ['partial']},
            )

            selected_count = int(result.get('selected_count') or 0)
            if selected_count == 0:
                messages.info(request, "No hay simbolos parciales para reforzar historicos IOL.")
            else:
                completed = ", ".join(
                    f"{key}: {payload.get('rows_received', 0)} rows"
                    for key, payload in result.get('results', {}).items()
                )
                if has_failures:
                    messages.warning(request, f"Historicos IOL parciales sincronizados con fallos. {completed}.")
                else:
                    messages.success(request, f"Historicos IOL parciales reforzados. {completed}.")
        except Exception as exc:
            record_sensitive_action(
                request,
                action='sync_iol_historical_prices_partial',
                status='failed',
                details={'reason': 'exception', 'message': str(exc), 'statuses': ['partial']},
            )
            messages.error(request, "No fue posible reforzar historicos IOL parciales.")
        return redirect('dashboard:ops')


class SyncIOLHistoricalPricesRetryMetadataView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            result = IOLHistoricalPriceService().sync_current_portfolio_symbols_by_status(
                statuses=('unsupported',),
                eligibility_reason_keys=('title_metadata_unresolved',),
            )
            has_failures = any(not payload.get('success', True) for payload in result.get('results', {}).values())
            audit_status = 'failed' if has_failures else 'success'
            record_sensitive_action(
                request,
                action='sync_iol_historical_prices_retry_metadata',
                status=audit_status,
                details={
                    'result': result,
                    'statuses': ['unsupported'],
                    'eligibility_reason_keys': ['title_metadata_unresolved'],
                },
            )

            selected_count = int(result.get('selected_count') or 0)
            if selected_count == 0:
                messages.info(request, "No hay exclusiones por metadata para reintentar históricos IOL.")
            else:
                completed = ", ".join(
                    f"{key}: {payload.get('rows_received', 0)} rows"
                    for key, payload in result.get('results', {}).items()
                )
                if has_failures:
                    messages.warning(request, f"Reintento de metadata IOL completado con fallos. {completed}.")
                else:
                    messages.success(request, f"Reintento de metadata IOL ejecutado. {completed}.")
        except Exception as exc:
            record_sensitive_action(
                request,
                action='sync_iol_historical_prices_retry_metadata',
                status='failed',
                details={
                    'reason': 'exception',
                    'message': str(exc),
                    'statuses': ['unsupported'],
                    'eligibility_reason_keys': ['title_metadata_unresolved'],
                },
            )
            messages.error(request, "No fue posible reintentar exclusiones por metadata IOL.")
        return redirect('dashboard:ops')


class RefreshIOLMarketSnapshotView(StaffRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        service = IOLHistoricalPriceService()
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('dashboard:ops')
        if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = reverse('dashboard:ops')
        try:
            payload = service.refresh_and_persist_current_portfolio_market_snapshot(limit=25)
            rows = payload["rows"]
            summary = payload["summary"]
            persistence = payload.get("persistence") or {}
            has_available = int(summary.get('available_count') or 0) > 0
            record_sensitive_action(
                request,
                action='refresh_iol_market_snapshot',
                status='success',
                details={'summary': summary, 'rows': rows, 'persistence': persistence},
            )

            if int(summary.get('total_symbols') or 0) == 0:
                messages.info(request, "No hay simbolos del portfolio para validar market snapshot IOL.")
            elif has_available and int(summary.get('missing_count') or 0) == 0:
                messages.success(
                    request,
                    (
                        "Market snapshot IOL validado. "
                        f"{summary['available_count']} simbolo(s) disponibles, "
                        f"detalle {summary['detail_count']}, fallback {summary['fallback_count']}."
                    ),
                )
            else:
                messages.warning(
                    request,
                    (
                        "Market snapshot IOL refrescado con cobertura parcial. "
                        f"Disponibles {summary['available_count']}, "
                        f"missing {summary['missing_count']}, "
                        f"no elegibles {summary['unsupported_count']}. "
                        f"Persistidos {persistence.get('persisted_count', 0)}."
                    ),
                )
        except Exception as exc:
            record_sensitive_action(
                request,
                action='refresh_iol_market_snapshot',
                status='failed',
                details={'reason': 'exception', 'message': str(exc)},
            )
            messages.error(request, "No fue posible refrescar el market snapshot IOL.")
        return redirect(next_url)

