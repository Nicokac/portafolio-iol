from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView

from apps.dashboard.selectors import (
    get_analytics_mensual,
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


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['kpis'] = get_dashboard_kpis()
        context['portafolio'] = get_portafolio_enriquecido_actual()
        context['distribucion_sector'] = get_distribucion_sector()
        context['distribucion_pais'] = get_distribucion_pais()
        context['distribucion_tipo'] = get_distribucion_tipo_patrimonial()
        context['distribucion_moneda'] = get_distribucion_moneda()
        context['distribucion_moneda_operativa'] = get_distribucion_moneda_operativa()
        context['riesgo_portafolio'] = get_riesgo_portafolio()
        context['riesgo_portafolio_detallado'] = get_riesgo_portafolio_detallado()
        context['concentracion_sector'] = get_concentracion_sector()
        context['concentracion_pais'] = get_concentracion_pais()
        context['concentracion_tipo'] = get_concentracion_tipo_patrimonial()
        context['analytics_mensual'] = get_analytics_mensual()
        context['evolucion_historica'] = get_evolucion_historica()
        context['senales_rebalanceo'] = get_senales_rebalanceo()
        return context