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
    get_implicit_fx_summary,
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
from apps.dashboard.dashboard_incremental_actions import (
    handle_bulk_decide_incremental_proposal,
    handle_decide_incremental_proposal,
    handle_promote_incremental_backlog_front,
    handle_promote_incremental_baseline,
    handle_reactivate_deferred_incremental_proposal,
    handle_save_preferred_incremental_proposal,
)


ALLOWED_UI_MODES = {'compacto', 'denso'}
ALLOWED_RISK_PROFILES = {'conservador', 'moderado', 'agresivo'}


def _build_planeacion_history_redirect_url(post_data) -> str:
    redirect_url = reverse('dashboard:planeacion')
    query = QueryDict(mutable=True)

    decision_status_filter = str(post_data.get('decision_status_filter', '') or '').strip()
    history_priority_filter = str(post_data.get('history_priority_filter', '') or '').strip()
    history_deferred_fit_filter = str(post_data.get('history_deferred_fit_filter', '') or '').strip()
    history_future_purchase_source_filter = str(post_data.get('history_future_purchase_source_filter', '') or '').strip()
    history_sort = str(post_data.get('history_sort', '') or '').strip()

    if decision_status_filter:
        query['decision_status_filter'] = decision_status_filter
    if history_priority_filter:
        query['history_priority_filter'] = history_priority_filter
    if history_deferred_fit_filter:
        query['history_deferred_fit_filter'] = history_deferred_fit_filter
    if history_future_purchase_source_filter:
        query['history_future_purchase_source_filter'] = history_future_purchase_source_filter
    if history_sort:
        query['history_sort'] = history_sort

    encoded = query.urlencode()
    if encoded:
        return f"{redirect_url}?{encoded}#planeacion-aportes"
    return f"{redirect_url}#planeacion-aportes"


class DashboardBaseContextMixin:
    active_section = 'estrategia'

    @staticmethod
    def serialize_chart_data(data):
        return json.dumps(data, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))

    @staticmethod
    def _ensure_context_value(context, key, factory):
        if key not in context:
            context[key] = factory()
        return context[key]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['active_section'] = self.active_section
        context['ui_mode'] = self.request.session.get('ui_mode', 'compacto')
        context['risk_profile'] = self.request.session.get('risk_profile', 'moderado')
        context['current_path'] = self.request.get_full_path()
        return context


class DashboardKpiContextMixin(DashboardBaseContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self._ensure_context_value(context, 'kpis', get_dashboard_kpis)
        return context


class DashboardPortfolioContextMixin(DashboardKpiContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self._ensure_context_value(context, 'portafolio', get_portafolio_enriquecido_actual)
        return context


class DashboardMacroContextMixin(DashboardKpiContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_iol = context['kpis'].get('total_iol')
        self._ensure_context_value(context, 'macro_local', lambda: get_macro_local_context(total_iol))
        return context


class DashboardMarketSupportContextMixin(DashboardBaseContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['market_snapshot_feature'] = get_market_snapshot_feature_context()
        context['market_snapshot_history_feature'] = get_market_snapshot_history_feature_context()
        context['parking_feature'] = get_portfolio_parking_feature_context()
        context['analytics_mensual'] = get_analytics_mensual()
        return context


class DashboardRiskSignalsContextMixin(DashboardBaseContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['senales_rebalanceo'] = get_senales_rebalanceo()
        context['riesgo_portafolio'] = get_riesgo_portafolio()
        context['riesgo_portafolio_detallado'] = get_riesgo_portafolio_detallado()
        context['snapshot_coverage'] = get_snapshot_coverage_summary(days=90)
        return context


class DashboardAnalyticsContextMixin(DashboardBaseContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        to_json = self.serialize_chart_data
        context['distribucion_sector'] = to_json(get_distribucion_sector(base='portafolio_invertido'))
        context['distribucion_pais'] = to_json(get_distribucion_pais(base='portafolio_invertido'))
        context['distribucion_pais_total_iol'] = to_json(get_distribucion_pais(base='total_iol'))
        context['distribucion_tipo'] = to_json(get_distribucion_tipo_patrimonial(base='total_activos'))
        context['distribucion_moneda'] = to_json(get_distribucion_moneda())
        context['distribucion_moneda_operativa'] = to_json(get_distribucion_moneda_operativa())
        context['implicit_fx_summary'] = get_implicit_fx_summary()
        context['concentracion_sector'] = get_concentracion_sector()
        context['concentracion_sector_agregado'] = get_concentracion_sector_agregado()
        context['concentracion_pais'] = get_concentracion_pais(base='portafolio_invertido')
        context['concentracion_pais_total_iol'] = get_concentracion_pais(base='total_iol')
        context['concentracion_tipo'] = get_concentracion_tipo_patrimonial(base='total_activos')
        context['concentracion_sector_json'] = to_json(context['concentracion_sector'])
        context['concentracion_sector_agregado_json'] = to_json(context['concentracion_sector_agregado'])
        context['concentracion_pais_json'] = to_json(context['concentracion_pais'])
        context['concentracion_pais_total_iol_json'] = to_json(context['concentracion_pais_total_iol'])
        context['concentracion_tipo_json'] = to_json(context['concentracion_tipo'])
        context['concentracion_moneda_json'] = to_json(get_concentracion_moneda())
        context['concentracion_moneda_operativa_json'] = to_json(get_concentracion_moneda_operativa())
        context['analytics_v2_summary'] = get_analytics_v2_dashboard_summary()
        return context


class DashboardEvolutionContextMixin(DashboardBaseContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        to_json = self.serialize_chart_data
        evolucion_historica_obj = get_evolucion_historica()
        context['evolucion_historica_obj'] = evolucion_historica_obj
        context['evolucion_historica'] = to_json(evolucion_historica_obj)
        return context


class DashboardAlertsContextMixin(DashboardBaseContextMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        alerts = get_active_alerts()
        context['alerts'] = alerts
        context['alerts_critical_count'] = sum(1 for alert in alerts if alert.get('severidad') == 'critical')
        context['alerts_warning_count'] = sum(1 for alert in alerts if alert.get('severidad') == 'warning')
        return context


class DashboardView(
    LoginRequiredMixin,
    DashboardKpiContextMixin,
    DashboardRiskSignalsContextMixin,
    DashboardAnalyticsContextMixin,
    DashboardEvolutionContextMixin,
    TemplateView,
):
    template_name = 'dashboard/estrategia.html'
    active_section = 'estrategia'


class CarteraDetalleView(
    LoginRequiredMixin,
    DashboardPortfolioContextMixin,
    DashboardMarketSupportContextMixin,
    TemplateView,
):
    template_name = 'dashboard/cartera_detalle.html'
    active_section = 'estrategia'


class RiesgoAvanzadoView(
    LoginRequiredMixin,
    DashboardKpiContextMixin,
    DashboardRiskSignalsContextMixin,
    DashboardAnalyticsContextMixin,
    TemplateView,
):
    template_name = 'dashboard/riesgo_avanzado.html'
    active_section = 'estrategia'


class RiskContributionDetailView(LoginRequiredMixin, DashboardBaseContextMixin, TemplateView):
    template_name = 'dashboard/risk_contribution_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['risk_contribution_detail'] = get_risk_contribution_detail()
        return context


class ScenarioAnalysisDetailView(LoginRequiredMixin, DashboardBaseContextMixin, TemplateView):
    template_name = 'dashboard/scenario_analysis_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['scenario_analysis_detail'] = get_scenario_analysis_detail()
        return context


class FactorExposureDetailView(LoginRequiredMixin, DashboardBaseContextMixin, TemplateView):
    template_name = 'dashboard/factor_exposure_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['factor_exposure_detail'] = get_factor_exposure_detail()
        return context


class StressFragilityDetailView(LoginRequiredMixin, DashboardBaseContextMixin, TemplateView):
    template_name = 'dashboard/stress_fragility_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stress_fragility_detail'] = get_stress_fragility_detail()
        return context


class ExpectedReturnDetailView(LoginRequiredMixin, DashboardBaseContextMixin, TemplateView):
    template_name = 'dashboard/expected_return_detail.html'
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expected_return_detail'] = get_expected_return_detail()
        return context


class PlaneacionView(
    LoginRequiredMixin,
    DashboardPortfolioContextMixin,
    DashboardRiskSignalsContextMixin,
    DashboardMarketSupportContextMixin,
    TemplateView,
):
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


class LaboratorioView(PlaneacionView):
    template_name = 'dashboard/laboratorio.html'
    active_section = 'planeacion'


class ResumenView(
    LoginRequiredMixin,
    DashboardMacroContextMixin,
    DashboardRiskSignalsContextMixin,
    DashboardMarketSupportContextMixin,
    DashboardEvolutionContextMixin,
    DashboardAlertsContextMixin,
    TemplateView,
):
    template_name = 'dashboard/resumen.html'
    active_section = 'resumen'


class AnalisisView(
    LoginRequiredMixin,
    DashboardKpiContextMixin,
    DashboardRiskSignalsContextMixin,
    DashboardAnalyticsContextMixin,
    TemplateView,
):
    template_name = 'dashboard/analisis.html'
    active_section = 'analisis'


class AnalysisSectionRedirectView(LoginRequiredMixin, View):
    section_anchor = ''
    active_section = 'analisis'

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        target = reverse('dashboard:analisis')
        if self.section_anchor:
            target = f"{target}#{self.section_anchor}"
        return redirect(target)


class PerformanceView(AnalysisSectionRedirectView):
    section_anchor = 'analisis-performance'


class MetricasView(AnalysisSectionRedirectView):
    section_anchor = 'analisis-metricas'


class OpsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/ops.html'
    active_section = 'analisis'

    def test_func(self):
        return bool(self.request.user and self.request.user.is_staff)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pipeline_observability = PipelineObservabilityService().build_ops_lite_summary(
            lookback_days=30,
            integrity_days=120,
        )
        context['pipeline_observability'] = pipeline_observability
        context['snapshot_coverage'] = get_snapshot_coverage_summary(days=90)
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
        return handle_save_preferred_incremental_proposal(
            request=request,
            get_preferred_incremental_portfolio_proposal=get_preferred_incremental_portfolio_proposal,
            get_decision_engine_summary=get_decision_engine_summary,
            history_service_factory=IncrementalProposalHistoryService,
            record_sensitive_action=record_sensitive_action,
        )


class PromoteIncrementalProposalBaselineView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return handle_promote_incremental_baseline(
            request=request,
            history_service_factory=IncrementalProposalHistoryService,
            record_sensitive_action=record_sensitive_action,
            build_redirect_url=_build_planeacion_history_redirect_url,
        )


class PromoteIncrementalBacklogFrontView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return handle_promote_incremental_backlog_front(
            request=request,
            history_service_factory=IncrementalProposalHistoryService,
            record_sensitive_action=record_sensitive_action,
            build_redirect_url=_build_planeacion_history_redirect_url,
        )


class ReactivateDeferredIncrementalProposalView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return handle_reactivate_deferred_incremental_proposal(
            request=request,
            history_service_factory=IncrementalProposalHistoryService,
            record_sensitive_action=record_sensitive_action,
            build_redirect_url=_build_planeacion_history_redirect_url,
        )


class DecideIncrementalProposalView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return handle_decide_incremental_proposal(
            request=request,
            history_service_factory=IncrementalProposalHistoryService,
            record_sensitive_action=record_sensitive_action,
            build_redirect_url=_build_planeacion_history_redirect_url,
        )


class BulkDecideIncrementalProposalView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return handle_bulk_decide_incremental_proposal(
            request=request,
            history_service_factory=IncrementalProposalHistoryService,
            get_incremental_proposal_history=get_incremental_proposal_history,
            record_sensitive_action=record_sensitive_action,
            build_redirect_url=_build_planeacion_history_redirect_url,
        )


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
        return redirect('dashboard:dashboard')


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
        return redirect('dashboard:dashboard')


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

