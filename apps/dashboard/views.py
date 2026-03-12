import json
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView
from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.dashboard.selectors import (
    get_analytics_mensual,
    get_active_alerts,
    get_concentracion_pais,
    get_concentracion_sector,
    get_concentracion_tipo_patrimonial,
    get_dashboard_kpis,
    get_distribucion_moneda,
    get_distribucion_moneda_operativa,
    get_distribucion_pais,
    get_distribucion_sector,
    get_distribucion_tipo_patrimonial,
    get_evolucion_historica,
    get_portafolio_enriquecido_actual,
    get_riesgo_portafolio,
    get_riesgo_portafolio_detallado,
    get_senales_rebalanceo,
)


ALLOWED_UI_MODES = {'compacto', 'denso'}
ALLOWED_RISK_PROFILES = {'conservador', 'moderado', 'agresivo'}


class DashboardContextMixin:
    active_section = 'estrategia'

    def _save_preferences(self, request: HttpRequest) -> None:
        ui_mode = request.GET.get('ui_mode')
        risk_profile = request.GET.get('risk_profile')

        if ui_mode in ALLOWED_UI_MODES:
            request.session['ui_mode'] = ui_mode
        if risk_profile in ALLOWED_RISK_PROFILES:
            request.session['risk_profile'] = risk_profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self._save_preferences(self.request)

        context['active_section'] = self.active_section
        context['ui_mode'] = self.request.session.get('ui_mode', 'compacto')
        context['risk_profile'] = self.request.session.get('risk_profile', 'moderado')

        context['kpis'] = get_dashboard_kpis()
        context['portafolio'] = get_portafolio_enriquecido_actual()

        def to_json(data):
            return json.dumps(data, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))

        context['distribucion_sector'] = to_json(get_distribucion_sector())
        context['distribucion_pais'] = to_json(get_distribucion_pais())
        context['distribucion_tipo'] = to_json(get_distribucion_tipo_patrimonial())
        context['distribucion_moneda'] = to_json(get_distribucion_moneda())
        context['distribucion_moneda_operativa'] = to_json(get_distribucion_moneda_operativa())
        context['riesgo_portafolio'] = get_riesgo_portafolio()
        context['riesgo_portafolio_detallado'] = get_riesgo_portafolio_detallado()
        context['concentracion_sector'] = get_concentracion_sector()
        context['concentracion_pais'] = get_concentracion_pais()
        context['concentracion_tipo'] = get_concentracion_tipo_patrimonial()
        context['analytics_mensual'] = get_analytics_mensual()

        evolucion_historica_obj = get_evolucion_historica()
        context['evolucion_historica_obj'] = evolucion_historica_obj
        context['evolucion_historica'] = to_json(evolucion_historica_obj)

        context['senales_rebalanceo'] = get_senales_rebalanceo()
        context['snapshot_integrity'] = SnapshotIntegrityService().run_checks(days=120)
        context['sync_audit'] = IOLSyncAuditService().run_audit(freshness_hours=24)

        alerts = get_active_alerts()
        context['alerts'] = alerts
        context['alerts_critical_count'] = sum(1 for alert in alerts if alert.get('severidad') == 'critical')
        context['alerts_warning_count'] = sum(1 for alert in alerts if alert.get('severidad') == 'warning')
        return context


class DashboardView(LoginRequiredMixin, DashboardContextMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'
    active_section = 'estrategia'


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
        # Perfil experto: staff o modo denso.
        return self.request.user.is_staff or self.request.session.get('ui_mode') == 'denso'


class SetPreferencesView(LoginRequiredMixin, TemplateView):
    http_method_names = ['get']

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        ui_mode = request.GET.get('ui_mode')
        risk_profile = request.GET.get('risk_profile')
        next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'

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
