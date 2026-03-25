from typing import Dict, List

from apps.core.services.data_quality.metadata_audit import MetadataAuditService
from apps.core.services.liquidity.liquidity_service import LiquidityService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.stress_test_service import StressTestService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.dashboard.portfolio_distribution import _is_technology_sector
from apps.parametros.models import ParametroActivo


def _compute_portfolio_exposures(portafolio: list, parametros: dict, total_portafolio) -> dict:
    """Calcula exposiciones geograficas y tematicas del portafolio invertido."""
    exposicion_usa = 0
    exposicion_argentina = 0
    exposicion_tech = 0
    exposicion_renta_fija_ar = 0
    exposicion_defensivo = 0
    exposicion_growth = 0

    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro:
            if parametro.pais_exposicion in ['USA', 'Estados Unidos']:
                exposicion_usa += activo.valorizado
            if parametro.pais_exposicion == 'Argentina':
                exposicion_argentina += activo.valorizado
            if _is_technology_sector(parametro.sector):
                exposicion_tech += activo.valorizado
            if parametro.tipo_patrimonial == 'Bond' and parametro.pais_exposicion == 'Argentina':
                exposicion_renta_fija_ar += activo.valorizado
            if parametro.bloque_estrategico == 'Defensivo':
                exposicion_defensivo += activo.valorizado
            if parametro.bloque_estrategico == 'Growth':
                exposicion_growth += activo.valorizado

    def pct(val):
        return (float(val) / float(total_portafolio) * 100) if total_portafolio > 0 else 0.0

    return {
        'exposicion_usa': exposicion_usa,
        'exposicion_argentina': exposicion_argentina,
        'pct_usa': pct(exposicion_usa),
        'pct_argentina': pct(exposicion_argentina),
        'pct_tech': pct(exposicion_tech),
        'pct_renta_fija_ar': pct(exposicion_renta_fija_ar),
        'pct_defensivo': pct(exposicion_defensivo),
        'pct_growth': pct(exposicion_growth),
    }


def build_riesgo_portafolio_detallado(
    *,
    portafolio: list,
    total_portafolio,
    liquidez_operativa,
    total_iol,
) -> Dict:
    """Calcula metricas detalladas de exposicion y riesgo del portafolio."""
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    exposures = _compute_portfolio_exposures(portafolio, parametros, total_portafolio)
    pct_liquidez = (float(liquidez_operativa) / float(total_iol) * 100) if total_iol > 0 else 0.0

    return {
        'pct_usa': exposures['pct_usa'],
        'pct_argentina': exposures['pct_argentina'],
        'pct_tech': exposures['pct_tech'],
        'pct_bonos_soberanos': exposures['pct_renta_fija_ar'],
        'pct_renta_fija_ar': exposures['pct_renta_fija_ar'],
        'pct_defensivo': exposures['pct_defensivo'],
        'pct_growth': exposures['pct_growth'],
        'pct_liquidez': pct_liquidez,
        'methodology': {
            'pct_usa': 'exposicion USA / portafolio invertido',
            'pct_argentina': 'exposicion Argentina / portafolio invertido',
            'pct_tech': 'sectores que comienzan con Tecnologia / portafolio invertido',
            'pct_renta_fija_ar': 'Bonos argentinos (soberanos, CER y corporativos) / portafolio invertido',
            'pct_defensivo': 'bloque Defensivo / portafolio invertido',
            'pct_growth': 'bloque Growth / portafolio invertido',
            'pct_liquidez': 'liquidez operativa / total iol',
        },
    }


def build_riesgo_portafolio(
    *,
    portafolio: list,
    total_portafolio,
    liquidez_operativa,
    total_iol,
) -> Dict:
    """Calcula metricas de riesgo completas del portafolio (version para dashboard)."""
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    exposures = _compute_portfolio_exposures(portafolio, parametros, total_portafolio)
    pct_liquidez = (float(liquidez_operativa) / float(total_iol) * 100) if total_iol > 0 else 0.0

    volatility_metrics = VolatilityService().calculate_volatility(days=90)
    var_metrics = VaRService().calculate_var_set(confidence=0.95, lookback_days=252)
    cvar_metrics = CVaRService().calculate_cvar_set(confidence=0.95, lookback_days=252)
    stress_metrics = StressTestService().run_all()
    benchmarking = TrackingErrorService().calculate(days=90)
    liquidity = LiquidityService().analyze_portfolio_liquidity()
    metadata_quality = MetadataAuditService().run_audit()
    volatilidad_pct = volatility_metrics.get('annualized_volatility')

    result = {
        'volatilidad_estimada': volatilidad_pct,
        'volatilidad_status': 'ok' if volatilidad_pct is not None else 'insufficient_history',
        'volatilidad_warning': volatility_metrics.get('warning'),
        'volatilidad_observations': volatility_metrics.get('observations'),
        'volatilidad_required_min_observations': volatility_metrics.get('required_min_observations'),
        'exposicion_usa': exposures['pct_usa'],
        'exposicion_argentina': exposures['pct_argentina'],
        'liquidez': pct_liquidez,
    }
    result.update(var_metrics)
    result.update(cvar_metrics)
    result.update(benchmarking)
    if liquidity:
        result['liquidity_score'] = liquidity.get('portfolio_liquidity_score')
        result['days_to_liquidate'] = liquidity.get('days_to_liquidate')
    if metadata_quality:
        result['metadata_unclassified_count'] = metadata_quality.get('unclassified_assets_count', 0)
        result['metadata_inconsistent_count'] = metadata_quality.get('inconsistent_assets_count', 0)
    if stress_metrics:
        worst_case = min(
            stress_metrics.values(),
            key=lambda scenario: scenario.get('impact_portfolio_pct', 0),
        )
        result['stress_worst_case_label'] = worst_case['label']
        result['stress_worst_case_pct'] = worst_case['impact_portfolio_pct']
    return result
