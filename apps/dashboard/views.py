import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django_celery_beat.models import PeriodicTask
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.contrib.auth.views import redirect_to_login
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView
from django.views import View
from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.core.services.data_quality.daily_snapshot_continuity_service import DailySnapshotContinuityService
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.core.services.iol_sync_service import IOLSyncService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.observability import record_state
from apps.core.services.pipeline_observability_service import PipelineObservabilityService
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.core.services.benchmark_series_service import BenchmarkSeriesService
from apps.core.services.security_audit import record_sensitive_action
from apps.dashboard.selectors import (
    get_analytics_v2_dashboard_summary,
    get_analytics_mensual,
    get_active_alerts,
    get_concentracion_pais,
    get_concentracion_sector,
    get_concentracion_sector_agregado,
    get_concentracion_tipo_patrimonial,
    get_candidate_asset_ranking,
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
    get_macro_local_context,
    get_monthly_allocation_plan,
    get_portafolio_enriquecido_actual,
    get_factor_exposure_detail,
    get_incremental_portfolio_simulation,
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


class DashboardContextMixin:
    active_section = 'estrategia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['active_section'] = self.active_section
        context['ui_mode'] = self.request.session.get('ui_mode', 'compacto')
        context['risk_profile'] = self.request.session.get('risk_profile', 'moderado')

        context['kpis'] = get_dashboard_kpis()
        context['macro_local'] = get_macro_local_context(context['kpis'].get('total_iol'))
        context['portafolio'] = get_portafolio_enriquecido_actual()

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
        context['monthly_allocation_plan'] = get_monthly_allocation_plan(capital_amount=600000)
        context['candidate_asset_ranking'] = get_candidate_asset_ranking(capital_amount=600000)
        context['incremental_portfolio_simulation'] = get_incremental_portfolio_simulation(capital_amount=600000)
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
