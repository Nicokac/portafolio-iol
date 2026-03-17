from typing import Dict, List
from datetime import timedelta
import hashlib
import json
from urllib.parse import urlencode
from django.core.cache import cache
from django.db.models import Max, Sum
from django.utils import timezone

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot
from apps.core.models import Alert
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.stress_test_service import StressTestService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.liquidity.liquidity_service import LiquidityService
from apps.core.services.data_quality.metadata_audit import MetadataAuditService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.candidate_asset_ranking_service import CandidateAssetRankingService
from apps.core.services.incremental_portfolio_simulator import IncrementalPortfolioSimulator
from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.core.services.monthly_allocation_service import MonthlyAllocationService
from apps.core.services.analytics_v2 import (
    AnalyticsExplanationService,
    CovarianceAwareRiskContributionService,
    ExpectedReturnService,
    FactorExposureService,
    LocalMacroSignalsService,
    RiskContributionService,
    ScenarioCatalogService,
    ScenarioAnalysisService,
    StressCatalogService,
    StressFragilityService,
)


SELECTOR_CACHE_TTL_SECONDS = 60


def _get_data_stamp() -> str:
    latest_portafolio = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_resumen = ResumenCuentaSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_parametro_id = ParametroActivo.objects.aggregate(latest=Max("id"))["latest"] or 0
    return f"{latest_portafolio}|{latest_resumen}|{latest_parametro_id}"


def _get_cached_selector_result(cache_key_prefix: str, builder):
    stamp = _get_data_stamp()
    stamp_hash = hashlib.md5(stamp.encode("utf-8")).hexdigest()
    cache_key = f"dashboard_selector:{cache_key_prefix}:{stamp_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    value = builder()
    cache.set(cache_key, value, timeout=SELECTOR_CACHE_TTL_SECONDS)
    return value


def get_latest_portafolio_data() -> List[ActivoPortafolioSnapshot]:
    """Obtiene los datos más recientes del portafolio."""
    latest_date = ActivoPortafolioSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_latest_resumen_data() -> List[ResumenCuentaSnapshot]:
    """Obtiene los datos más recientes del resumen de cuenta."""
    latest_date = ResumenCuentaSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ResumenCuentaSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_portafolio_enriquecido_actual() -> Dict[str, List[Dict]]:
    """Obtiene el portafolio actual enriquecido con metadata, separado en liquidez e inversión."""
    def build():
        portafolio = get_latest_portafolio_data()
        simbolos = [activo.simbolo for activo in portafolio]
        parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

        # Calcular total del portafolio para pesos porcentuales
        total_portafolio = sum(activo.valorizado for activo in portafolio)

        # Traducciones de tipos
        tipo_traducciones = {
            'CEDEARS': 'CEDEAR',
            'ACCIONES': 'Acción',
            'TitulosPublicos': 'Título Público',
            'FondoComundeInversion': 'FCI',
            'CAUCIONESPESOS': 'Caución',
        }

        # Traducciones de monedas
        moneda_traducciones = {
            'peso_Argentino': 'ARS',
            'dolar_Estadounidense': 'USD',
        }

        liquidez = []
        inversion = []
        fci_cash_management = []  # Categoría intermedia para FCI de cash management

        for activo in portafolio:
            param = parametros.get(activo.simbolo)
            tipo_traducido = tipo_traducciones.get(activo.tipo, activo.tipo)
            moneda_traducida = moneda_traducciones.get(activo.moneda, activo.moneda)

            # Calcular peso porcentual
            peso_porcentual = (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0

            item = {
                'activo': activo,
                'sector': param.sector if param else 'N/A',
                'bloque_estrategico': param.bloque_estrategico if param else 'N/A',
                'pais_exposicion': param.pais_exposicion if param else 'N/A',
                'tipo_patrimonial': param.tipo_patrimonial if param else 'N/A',
                'observaciones': param.observaciones if param else '',
                'tipo_traducido': tipo_traducido,
                'moneda_traducida': moneda_traducida,
                'peso_porcentual': peso_porcentual,
            }

            # Clasificación refinada
            simbolo_upper = activo.simbolo.upper()
            if activo.tipo == 'CAUCIONESPESOS' or 'CAUCIÓN' in simbolo_upper:
                # Caución como liquidez operativa
                liquidez.append(item)
            elif simbolo_upper in ['ADBAICA', 'IOLPORA', 'PRPEDOB']:
                # FCI de cash management como categoría intermedia
                fci_cash_management.append(item)
            elif activo.tipo == 'FondoComundeInversion':
                # Otros FCI van al portafolio invertido
                inversion.append(item)
            elif activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in simbolo_upper:
                # Activos tradicionales van al portafolio invertido
                inversion.append(item)
            else:
                # Resto va al portafolio invertido por defecto
                inversion.append(item)

        # Ordenar inversión por valorizado descendente
        inversion.sort(key=lambda x: x['activo'].valorizado, reverse=True)
        fci_cash_management.sort(key=lambda x: x['activo'].valorizado, reverse=True)

        return {
            'liquidez': liquidez,
            'fci_cash_management': fci_cash_management,
            'inversion': inversion,
            'total_portafolio': total_portafolio,
        }

    return _get_cached_selector_result("portafolio_enriquecido_actual", build)


def _get_activos_invertidos() -> List[Dict]:
    return get_portafolio_enriquecido_actual()['inversion']


def _get_activos_valorizados_con_metadata() -> List[Dict]:
    portafolio = get_portafolio_enriquecido_actual()
    return portafolio['liquidez'] + portafolio['fci_cash_management'] + portafolio['inversion']


def _build_distribution_from_items(items: List[Dict], field: str) -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for item in items:
        key = item.get(field) or 'Sin clasificar'
        if field == 'pais_exposicion' and key in {'Estados Unidos', 'USA'}:
            key = 'USA'
        distribucion[key] = distribucion.get(key, 0) + float(item['activo'].valorizado)
    return distribucion


def _is_technology_sector(sector: str | None) -> bool:
    if not sector:
        return False
    normalized = str(sector).strip().lower()
    return normalized.startswith('tecnolog')




def _aggregate_sector_labels(distribucion: Dict[str, float]) -> Dict[str, float]:
    aggregated: Dict[str, float] = {}
    for sector, valor in distribucion.items():
        label = 'Tecnologia Total' if _is_technology_sector(sector) else sector
        aggregated[label] = aggregated.get(label, 0) + float(valor)
    return aggregated


def _get_resumen_cash_distribution_by_country() -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for cuenta in get_latest_resumen_data():
        monto = float(cuenta.disponible)
        if monto <= 0:
            continue
        pais = 'USA' if cuenta.moneda == 'USD' else 'Argentina'
        distribucion[pais] = distribucion.get(pais, 0) + monto
    return distribucion


def get_dashboard_kpis() -> Dict:
    """Calcula los KPIs principales del dashboard con métricas separadas por categoría."""
    def build():
        portafolio = get_latest_portafolio_data()
        resumen = get_latest_resumen_data()

        # Obtener clasificación del portafolio
        portafolio_clasificado = get_portafolio_enriquecido_actual()

        # Cash disponible
        cash_ars = sum(cuenta.disponible for cuenta in resumen if cuenta.moneda == 'ARS')
        cash_usd = sum(cuenta.disponible for cuenta in resumen if cuenta.moneda == 'USD')

        # 1. Total IOL = SUM(valorizado de todos los activos) + cash ARS + cash USD
        total_activos_valorizados = sum(activo.valorizado for activo in portafolio)
        total_iol = total_activos_valorizados + cash_ars + cash_usd

        # KPIs separados por categoría
        # 2. Liquidez Operativa = caución + saldo ARS disponible + saldo USD disponible
        caucion_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['liquidez'] if item['tipo_traducido'] == 'Caución')
        liquidez_operativa = caucion_valor + cash_ars + cash_usd

        # 3. FCI Cash Management = suma de FCI de cash management
        fci_cash_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['fci_cash_management'])

        # 4. Portafolio Invertido = activos de inversión (CEDEAR, acciones, bonos, ETF, otros FCI)
        portafolio_invertido = sum(item['activo'].valorizado for item in portafolio_clasificado['inversion'])

        # KPIs heredados para compatibilidad
        titulos_valorizados = sum(
            activo.valorizado for activo in portafolio
            if activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in activo.simbolo.upper()
        )
        capital_invertido_real = total_iol - liquidez_operativa - fci_cash_valor

        # Rendimiento simple sobre costo estimado del capital realmente invertido.
        inversion = portafolio_clasificado['inversion']
        rendimiento_total_dinero = sum(item['activo'].ganancia_dinero for item in inversion)
        costo_estimado_invertido = portafolio_invertido - rendimiento_total_dinero
        rendimiento_total_porcentaje = (
            rendimiento_total_dinero / costo_estimado_invertido * 100
        ) if costo_estimado_invertido > 0 else 0

        # Concentraci?n de posiciones sobre portafolio invertido.
        portafolio_ordenado = sorted(
            (item['activo'] for item in inversion),
            key=lambda activo: activo.valorizado,
            reverse=True,
        )
        top_5_valor = sum(activo.valorizado for activo in portafolio_ordenado[:5])
        top_5_concentracion = (top_5_valor / portafolio_invertido * 100) if portafolio_invertido else 0

        # Top 10 concentraci?n
        top_10_valor = sum(activo.valorizado for activo in portafolio_ordenado[:10])
        top_10_concentracion = (top_10_valor / portafolio_invertido * 100) if portafolio_invertido else 0

        # Porcentajes de los bloques patrimoniales
        pct_fci_cash_management = (fci_cash_valor / total_iol * 100) if total_iol else 0
        pct_portafolio_invertido = (portafolio_invertido / total_iol * 100) if total_iol else 0
        pct_liquidez_total = ((liquidez_operativa + fci_cash_valor) / total_iol * 100) if total_iol else 0

        return {
            'total_iol': total_iol,
            'titulos_valorizados': titulos_valorizados,
            'cash_ars': cash_ars,
            'cash_usd': cash_usd,
            'liquidez_operativa': liquidez_operativa,
            'fci_cash_management': fci_cash_valor,
            'portafolio_invertido': portafolio_invertido,
            'capital_invertido_real': capital_invertido_real,
            'rendimiento_total_porcentaje': rendimiento_total_porcentaje,
            'rendimiento_total_dinero': rendimiento_total_dinero,
            'rendimiento_total_cost_basis': costo_estimado_invertido,
            'top_5_concentracion': top_5_concentracion,
            'top_10_concentracion': top_10_concentracion,
            'pct_fci_cash_management': pct_fci_cash_management,
            'pct_portafolio_invertido': pct_portafolio_invertido,
            'pct_liquidez_total': pct_liquidez_total,
            'methodology': {
                'top_5_concentracion': 'sum(top_5 valorizado del portafolio invertido) / portafolio invertido',
                'top_10_concentracion': 'sum(top_10 valorizado del portafolio invertido) / portafolio invertido',
                'top_positions_basis': 'portafolio_invertido',
                'rendimiento_total_porcentaje': 'ganancia acumulada / costo estimado del portafolio invertido',
                'rendimiento_total_basis': 'portafolio_invertido_costo_estimado',
                'pct_liquidez_total': '(liquidez operativa + cash management) / total iol',
                'pct_portafolio_invertido': 'portafolio invertido / total iol',
            },
        }

    return _get_cached_selector_result("dashboard_kpis", build)


def get_macro_local_context(total_iol: float | None = None) -> Dict:
    """Obtiene contexto macro local persistido para enriquecer el analisis."""

    def build():
        return LocalMacroSeriesService().get_context_summary(total_iol=total_iol)

    total_stamp = round(float(total_iol), 2) if total_iol is not None else "none"
    return _get_cached_selector_result(f"macro_local_context:{total_stamp}", build)


def get_distribucion_sector(base: str = 'total_activos') -> Dict[str, float]:
    """Obtiene la distribuci?n por sector o bloque patrimonial seg?n la base."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(_get_activos_invertidos(), 'sector')
    return _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'sector')


def get_distribucion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    """Obtiene la distribuci?n por pa?s de exposici?n real."""
    if base == 'total_iol':
        distribucion = _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'pais_exposicion')
        for pais, monto in _get_resumen_cash_distribution_by_country().items():
            distribucion[pais] = distribucion.get(pais, 0) + monto
        return distribucion
    return _build_distribution_from_items(_get_activos_invertidos(), 'pais_exposicion')


def get_distribucion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    """Obtiene la distribuci?n por tipo patrimonial."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(_get_activos_invertidos(), 'tipo_patrimonial')
    return _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'tipo_patrimonial')


def get_distribucion_moneda() -> Dict[str, float]:
    """Obtiene la distribución por moneda de exposición real/económica."""
    portafolio = get_latest_portafolio_data()
    resumen = get_latest_resumen_data()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    distribucion = {}
    # Agregar activos del portafolio
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)

        # Moneda económica/subyacente (exposición real)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            moneda = 'USD'
        elif activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            # Para otros casos, intentar inferir de tipo_patrimonial
            if parametro and parametro.tipo_patrimonial == 'Hard Assets':
                moneda = 'Hard Assets'
            else:
                moneda = 'ARS'  # Default a ARS

        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    # Agregar cash disponible
    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def get_distribucion_moneda_operativa() -> Dict[str, float]:
    """Obtiene la distribución por moneda operativa (de cotización)."""
    portafolio = get_latest_portafolio_data()
    resumen = get_latest_resumen_data()
    distribucion = {}

    # Agregar activos del portafolio por moneda de cotización
    for activo in portafolio:
        if activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            moneda = 'ARS'  # Default

        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    # Agregar cash disponible
    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def get_concentracion_patrimonial() -> Dict[str, float]:
    """Obtiene la concentración por bloque patrimonial (Liquidez, Cash Management, Invertido)."""
    kpis = get_dashboard_kpis()
    total_iol = kpis['total_iol']

    if total_iol == 0:
        return {}

    return {
        'Liquidez': (kpis['liquidez_operativa'] / total_iol * 100),
        'Cash Management': (kpis['fci_cash_management'] / total_iol * 100),
        'Invertido': (kpis['portafolio_invertido'] / total_iol * 100),
    }


def get_concentracion_sectorial() -> Dict[str, float]:
    """Obtiene la concentración por sector económico (excluyendo liquidez)."""
    # Solo considerar activos de inversión (excluir liquidez y cash management)
    portafolio_invertido = get_portafolio_enriquecido_actual()['inversion']
    distribucion = {}

    for item in portafolio_invertido:
        sector = item['sector']
        if sector and sector != 'N/A':
            distribucion[sector] = distribucion.get(sector, 0) + float(item['activo'].valorizado)

    total = sum(distribucion.values())
    if total == 0:
        return {}
    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}


def get_concentracion_sector() -> Dict[str, float]:
    """Calcula la concentraci?n sectorial pura del capital invertido."""
    distribucion = get_distribucion_sector(base='portafolio_invertido')
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}




def get_concentracion_sector_agregado() -> Dict[str, float]:
    """Calcula concentracion sectorial agregando subsectores tecnol?gicos."""
    distribucion = _aggregate_sector_labels(get_distribucion_sector(base='portafolio_invertido'))
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}


def get_concentracion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    """Calcula la concentraci?n por pa?s en porcentajes."""
    distribucion = get_distribucion_pais(base=base)
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {pais: (valor / total * 100) for pais, valor in distribucion.items()}


def get_concentracion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    """Calcula la concentraci?n por tipo patrimonial en porcentajes."""
    distribucion = get_distribucion_tipo_patrimonial(base=base)
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {tipo: (valor / total * 100) for tipo, valor in distribucion.items()}


def get_concentracion_moneda() -> Dict[str, float]:
    """Calcula la concentracion por moneda economica en porcentajes."""
    distribucion = get_distribucion_moneda()
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {moneda: (valor / total * 100) for moneda, valor in distribucion.items()}


def get_concentracion_moneda_operativa() -> Dict[str, float]:
    """Calcula la concentracion por moneda operativa en porcentajes."""
    distribucion = get_distribucion_moneda_operativa()
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {moneda: (valor / total * 100) for moneda, valor in distribucion.items()}


def get_riesgo_portafolio_detallado() -> Dict[str, float]:
    """Calcula métricas detalladas de riesgo del portafolio."""
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    resumen = get_latest_resumen_data()
    portafolio_clasificado = get_portafolio_enriquecido_actual()
    kpis = get_dashboard_kpis()

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    total_iol = kpis.get('total_iol', 0)

    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    # Exposición geográfica
    exposicion_usa = 0
    exposicion_argentina = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            exposicion_usa += activo.valorizado
        elif parametro and parametro.pais_exposicion == 'Argentina':
            exposicion_argentina += activo.valorizado

    # Exposición por tipo
    exposicion_tech = 0
    exposicion_renta_fija_ar = 0
    exposicion_defensivo = 0
    exposicion_growth = 0

    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro:
            if _is_technology_sector(parametro.sector):
                exposicion_tech += activo.valorizado
            if parametro.tipo_patrimonial == 'Bond' and parametro.pais_exposicion == 'Argentina':
                exposicion_renta_fija_ar += activo.valorizado
            if parametro.bloque_estrategico == 'Defensivo':
                exposicion_defensivo += activo.valorizado
            if parametro.bloque_estrategico == 'Growth':
                exposicion_growth += activo.valorizado

    # Liquidez total
    liquidez_total = kpis.get('liquidez_operativa', 0)


    # Calcular porcentajes
    pct_usa = (exposicion_usa / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_argentina = (exposicion_argentina / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_tech = (exposicion_tech / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_renta_fija_ar = (exposicion_renta_fija_ar / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_defensivo = (exposicion_defensivo / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_growth = (exposicion_growth / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_liquidez = (liquidez_total / total_iol * 100) if total_iol > 0 else 0

    return {
        'pct_usa': pct_usa,
        'pct_argentina': pct_argentina,
        'pct_tech': pct_tech,
        'pct_bonos_soberanos': pct_renta_fija_ar,
        'pct_renta_fija_ar': pct_renta_fija_ar,
        'pct_defensivo': pct_defensivo,
        'pct_growth': pct_growth,
        'pct_liquidez': pct_liquidez,
        'methodology': {
            'pct_usa': 'exposicion USA / portafolio invertido',
            'pct_argentina': 'exposicion Argentina / portafolio invertido',
            'pct_tech': 'sectores que comienzan con Tecnología / portafolio invertido',
            'pct_renta_fija_ar': 'Bonos argentinos (soberanos, CER y corporativos) / portafolio invertido',
            'pct_defensivo': 'bloque Defensivo / portafolio invertido',
            'pct_growth': 'bloque Growth / portafolio invertido',
            'pct_liquidez': 'liquidez operativa / total iol',
        },
    }


def get_riesgo_portafolio() -> Dict[str, float]:
    """Calcula métricas de riesgo del portafolio (versión simplificada para compatibilidad)."""
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    resumen = get_latest_resumen_data()
    portafolio_clasificado = get_portafolio_enriquecido_actual()
    kpis = get_dashboard_kpis()

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    total_iol = kpis.get('total_iol', 0)

    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    # Exposición USA
    exposicion_usa = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            exposicion_usa += activo.valorizado
    exposicion_usa_pct = (exposicion_usa / total_portafolio * 100) if total_portafolio > 0 else 0

    # Exposición Argentina
    exposicion_argentina = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion == 'Argentina':
            exposicion_argentina += activo.valorizado
    exposicion_argentina_pct = (exposicion_argentina / total_portafolio * 100) if total_portafolio > 0 else 0

    # Liquidez total
    liquidez_total = kpis.get('liquidez_operativa', 0)

    liquidez_pct = (liquidez_total / total_iol * 100) if total_iol > 0 else 0

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
        'exposicion_usa': exposicion_usa_pct,
        'exposicion_argentina': exposicion_argentina_pct,
        'liquidez': liquidez_pct,
    }
    result.update(var_metrics)
    result.update(cvar_metrics)
    result.update(benchmarking)
    if liquidity:
        result["liquidity_score"] = liquidity.get("portfolio_liquidity_score")
        result["days_to_liquidate"] = liquidity.get("days_to_liquidate")
    if metadata_quality:
        result["metadata_unclassified_count"] = metadata_quality.get("unclassified_assets_count", 0)
        result["metadata_inconsistent_count"] = metadata_quality.get("inconsistent_assets_count", 0)
    if stress_metrics:
        worst_case = min(
            stress_metrics.values(),
            key=lambda scenario: scenario.get("impact_portfolio_pct", 0)
        )
        result["stress_worst_case_label"] = worst_case["label"]
        result["stress_worst_case_pct"] = worst_case["impact_portfolio_pct"]
    return result


def get_analytics_mensual() -> Dict[str, float]:
    """Calcula métricas de operaciones del mes actual."""
    from apps.operaciones_iol.models import OperacionIOL
    from apps.parametros.models import ConfiguracionDashboard
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    # Calcular fechas del mes actual
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fin_mes = (inicio_mes + relativedelta(months=1)) - timezone.timedelta(seconds=1)

    # Filtrar operaciones del mes ejecutadas (usar fecha_operada si existe, sino fecha_orden)
    operaciones_mes = OperacionIOL.objects.filter(
        fecha_operada__gte=inicio_mes,
        fecha_operada__lte=fin_mes,
        estado__in=['terminada', 'Terminada', 'TERMINADA']
    )

    # Si no hay operaciones con fecha_operada, intentar con fecha_orden
    if not operaciones_mes.exists():
        operaciones_mes = OperacionIOL.objects.filter(
            fecha_orden__gte=inicio_mes,
            fecha_orden__lte=fin_mes,
            estado__in=['terminada', 'Terminada', 'TERMINADA']
        )

    # Compras del mes (operaciones de compra ejecutadas)
    compras_mes = operaciones_mes.filter(tipo__in=['Compra', 'COMPRA'])
    monto_compras = sum(
        (op.cantidad_operada or 0) * (op.precio_operado or 0)
        for op in compras_mes
        if op.cantidad_operada and op.precio_operado
    )

    # Ventas del mes (operaciones de venta ejecutadas)
    ventas_mes = operaciones_mes.filter(tipo__in=['Venta', 'VENTA'])
    monto_ventas = sum(
        (op.cantidad_operada or 0) * (op.precio_operado or 0)
        for op in ventas_mes
        if op.cantidad_operada and op.precio_operado
    )

    # Aporte mensual ejecutado (flujo neto de inversiones: compras - ventas)
    aporte_ejecutado = monto_compras - monto_ventas

    # Aporte mensual objetivo (configurable desde la base de datos)
    try:
        config_objetivo = ConfiguracionDashboard.objects.get(clave='contribucion_mensual')
        aporte_mensual_objetivo = float(config_objetivo.valor)
    except (ConfiguracionDashboard.DoesNotExist, ValueError):
        aporte_mensual_objetivo = 50000.0  # Valor por defecto si no existe configuración

    # Convertir a Decimal para compatibilidad con los cálculos de montos
    from decimal import Decimal
    aporte_mensual_objetivo = Decimal(str(aporte_mensual_objetivo))

    # Aporte pendiente
    aporte_pendiente = aporte_mensual_objetivo - aporte_ejecutado

    return {
        'compras_mes': monto_compras,
        'ventas_mes': monto_ventas,
        'aporte_mensual_ejecutado': aporte_ejecutado,
        'aporte_pendiente': max(0, aporte_pendiente),  # No mostrar negativo
    }


def get_portafolio_clasificado_fecha(portafolio_fecha) -> Dict[str, List[Dict]]:
    """Clasifica un portafolio histórico en categorías (versión simplificada para evolución histórica)."""
    simbolos = [activo.simbolo for activo in portafolio_fecha]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    liquidez = []
    fci_cash_management = []
    inversion = []

    for activo in portafolio_fecha:
        parametro = parametros.get(activo.simbolo)

        # Determinar tipo traducido
        tipo_traducido = 'Desconocido'
        if activo.tipo == 'CEDEARS':
            tipo_traducido = 'CEDEAR'
        elif activo.tipo == 'ACCIONES':
            tipo_traducido = 'Acción'
        elif activo.tipo == 'TitulosPublicos':
            tipo_traducido = 'Título Público'
        elif activo.tipo == 'FondoComundeInversion':
            tipo_traducido = 'FCI'
        elif activo.tipo == 'CAUCIONESPESOS':
            tipo_traducido = 'Caución'

        item = {
            'activo': activo,
            'tipo_traducido': tipo_traducido,
            'parametro': parametro
        }

        # Clasificar por bloque estratégico
        if parametro and parametro.bloque_estrategico == 'Liquidez':
            liquidez.append(item)
        elif parametro and parametro.bloque_estrategico == 'FCI Cash Management':
            fci_cash_management.append(item)
        else:
            # Por defecto va a inversión
            inversion.append(item)

    return {
        'liquidez': liquidez,
        'fci_cash_management': fci_cash_management,
        'inversion': inversion,
    }


def get_evolucion_historica(days: int = 30, max_points: int = 14) -> Dict[str, list]:
    """Obtiene evolución histórica consolidada por día calendario."""
    from collections import defaultdict
    from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
    from apps.resumen_iol.models import ResumenCuentaSnapshot
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    fecha_fin = timezone.now()
    fecha_inicio = fecha_fin - relativedelta(days=days)

    portafolio_snapshots = ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion__gte=fecha_inicio,
        fecha_extraccion__lte=fecha_fin,
    ).order_by("fecha_extraccion")
    resumen_snapshots = ResumenCuentaSnapshot.objects.filter(
        fecha_extraccion__gte=fecha_inicio,
        fecha_extraccion__lte=fecha_fin,
    ).order_by("fecha_extraccion")

    portafolio_por_dia = defaultdict(list)
    for activo in portafolio_snapshots:
        portafolio_por_dia[activo.fecha_extraccion.date()].append(activo)

    resumen_por_dia = defaultdict(list)
    for cuenta in resumen_snapshots:
        resumen_por_dia[cuenta.fecha_extraccion.date()].append(cuenta)

    fechas_unicas = sorted(set(portafolio_por_dia.keys()) | set(resumen_por_dia.keys()))
    if len(fechas_unicas) < 2:
        return {
            "tiene_datos": False,
            "mensaje": "Aún no hay historial suficiente para mostrar evolución",
            "fechas": [],
            "total_iol": [],
            "liquidez_operativa": [],
            "portafolio_invertido": [],
            "cash_management": [],
        }

    fechas_a_procesar = fechas_unicas[-max_points:] if max_points and max_points > 0 else fechas_unicas

    fechas_str = []
    total_iol_vals = []
    liquidez_vals = []
    portafolio_vals = []
    cash_vals = []

    for fecha in fechas_a_procesar:
        portafolio_fecha = portafolio_por_dia.get(fecha, [])
        resumen_fecha = resumen_por_dia.get(fecha, [])

        total_portafolio = sum(activo.valorizado for activo in portafolio_fecha)
        total_cash = sum(cuenta.disponible for cuenta in resumen_fecha)
        total_iol = total_portafolio + total_cash

        portafolio_clasificado = get_portafolio_clasificado_fecha(portafolio_fecha)

        caucion_valor = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("liquidez", [])
            if item["tipo_traducido"] == "Caución"
        )
        cash_ars = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "ARS")
        cash_usd = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "USD")
        liquidez_operativa = caucion_valor + cash_ars + cash_usd
        portafolio_invertido = sum(
            item["activo"].valorizado for item in portafolio_clasificado.get("inversion", [])
        )
        cash_management = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("fci_cash_management", [])
        )

        fechas_str.append(fecha.strftime("%Y-%m-%d"))
        total_iol_vals.append(float(total_iol))
        liquidez_vals.append(float(liquidez_operativa))
        portafolio_vals.append(float(portafolio_invertido))
        cash_vals.append(float(cash_management))

    return {
        "tiene_datos": True,
        "fechas": fechas_str,
        "total_iol": total_iol_vals,
        "liquidez_operativa": liquidez_vals,
        "portafolio_invertido": portafolio_vals,
        "cash_management": cash_vals,
    }


def get_objetivos_rebalanceo() -> Dict[str, Dict[str, float]]:
    """Define objetivos de asignación por bloque patrimonial y sectorial."""
    return {
        'patrimonial': {
            'Liquidez': 25.0,        # Objetivo: 20-30%
            'Cash Management': 7.5,  # Objetivo: 5-10%
            'Invertido': 67.5,       # Objetivo: 60-75%
        },
        'sectorial': {
            'Tecnología': 17.5,      # Objetivo: 15-20%
            'ETF core': 22.5,        # Objetivo: 20-25% (Índice, etc.)
            'Argentina': 12.5,       # Objetivo: 10-15%
            'Bonos': 12.5,           # Objetivo: 10-15% (Soberano, Corporativo)
            'Defensivos': 12.5,      # Objetivo: 10-15% (Consumo defensivo, Utilities)
            # Otros sectores se evalúan vs umbral mínimo
        }
    }


def mapear_sector_a_categoria(sector: str) -> str:
    """Mapea sectores específicos a categorías objetivo."""
    mapeo = {
        # ETF core
        'Índice': 'ETF core',
        'ETF': 'ETF core',
        # Bonos
        'Soberano': 'Bonos',
        'Corporativo': 'Bonos',
        'Título Público': 'Bonos',
        # Defensivos
        'Consumo defensivo': 'Defensivos',
        'Utilities': 'Defensivos',
        'Finanzas': 'Defensivos',
        # Argentina
        'Argentina': 'Argentina',
        # Tecnología (mantener como está)
        'Tecnología': 'Tecnología',
        'Tecnología / E-commerce': 'Tecnología',
        'Tecnología / Semiconductores': 'Tecnología',
    }
    return mapeo.get(sector, sector)


def get_senales_rebalanceo() -> Dict[str, list]:
    """Genera señales de rebalanceo basadas en objetivos definidos."""
    concentracion_patrimonial = get_concentracion_patrimonial()
    concentracion_sectorial = get_concentracion_sectorial()
    objetivos = get_objetivos_rebalanceo()

    # Umbrales para evaluación
    TOLERANCIA_SOBRE = 5.0   # +5% sobre objetivo = sobreponderado
    TOLERANCIA_SUB = 3.0     # -3% bajo objetivo = subponderado
    UMBRAL_MINIMO = 2.0      # Sectores sin objetivo: <2% = subponderado
    UMBRAL_POSICION_ALTA = 10.0  # >10% = posición alta

    # A. Rebalanceo patrimonial (vs objetivos definidos)
    patrimonial_sobreponderado = []
    patrimonial_subponderado = []

    for categoria, actual in concentracion_patrimonial.items():
        objetivo = objetivos['patrimonial'].get(categoria, actual)  # Si no hay objetivo, usar actual como baseline

        if actual > objetivo + TOLERANCIA_SOBRE:
            patrimonial_sobreponderado.append({
                'categoria': categoria,
                'porcentaje': float(actual),
                'objetivo': float(objetivo),
                'diferencia': float(actual) - float(objetivo)
            })
        elif actual < objetivo - TOLERANCIA_SUB:
            patrimonial_subponderado.append({
                'categoria': categoria,
                'porcentaje': float(actual),
                'objetivo': float(objetivo),
                'diferencia': float(objetivo) - float(actual)
            })

    # B. Rebalanceo sectorial (vs objetivos definidos o umbral mínimo)
    # Primero agrupar por categorías objetivo
    concentracion_agrupada = {}
    for sector, actual in concentracion_sectorial.items():
        categoria = mapear_sector_a_categoria(sector)
        concentracion_agrupada[categoria] = concentracion_agrupada.get(categoria, 0) + actual

    sectorial_sobreponderado = []
    sectorial_subponderado = []

    for categoria, actual in concentracion_agrupada.items():
        objetivo = objetivos['sectorial'].get(categoria)

        if objetivo is not None:
            # Categoría con objetivo definido
            if actual > objetivo + TOLERANCIA_SOBRE:
                sectorial_sobreponderado.append({
                    'sector': categoria,
                    'porcentaje': float(actual),
                    'objetivo': float(objetivo),
                    'diferencia': float(actual) - float(objetivo)
                })
            elif actual < objetivo - TOLERANCIA_SUB:
                sectorial_subponderado.append({
                    'sector': categoria,
                    'porcentaje': float(actual),
                    'objetivo': float(objetivo),
                    'diferencia': float(objetivo) - float(actual)
                })
        else:
            # Categoría sin objetivo definido: evaluar vs umbral mínimo
            if actual < UMBRAL_MINIMO:
                sectorial_subponderado.append({
                    'sector': categoria,
                    'porcentaje': actual,
                    'objetivo': None,
                    'diferencia': UMBRAL_MINIMO - actual
                })

    # Activos sin metadata (mantener igual)
    portafolio = get_latest_portafolio_data()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    activos_sin_metadata = []
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if not parametro or not all([
            parametro.sector != 'N/A',
            parametro.bloque_estrategico != 'N/A',
            parametro.pais_exposicion != 'N/A',
            parametro.tipo_patrimonial != 'N/A'
        ]):
            activos_sin_metadata.append({
                'simbolo': activo.simbolo,
                'valorizado': float(activo.valorizado)
            })

    # Posiciones con mayor peso (mantener igual)
    total_portafolio = sum(activo.valorizado for activo in portafolio)
    posiciones_altas = [
        {
            'simbolo': activo.simbolo,
            'peso': (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0,
            'valorizado': float(activo.valorizado)
        }
        for activo in portafolio
        if (activo.valorizado / total_portafolio * 100) > UMBRAL_POSICION_ALTA
    ]
    posiciones_altas.sort(key=lambda x: x['peso'], reverse=True)

    return {
        'patrimonial_sobreponderado': patrimonial_sobreponderado,
        'patrimonial_subponderado': patrimonial_subponderado,
        'sectorial_sobreponderado': sectorial_sobreponderado,
        'sectorial_subponderado': sectorial_subponderado,
        'activos_sin_metadata': activos_sin_metadata,
        'posiciones_mayor_peso': posiciones_altas,
    }


def get_snapshot_coverage_summary(days: int = 90) -> Dict[str, float | int | str | bool | None]:
    """Resume la cobertura reciente de snapshots para diagnosticar metricas temporales."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    snapshots = list(
        PortfolioSnapshot.objects.filter(fecha__range=(start_date, end_date)).order_by("fecha")
    )

    count = len(snapshots)
    if count == 0:
        return {
            "requested_days": days,
            "snapshots_count": 0,
            "latest_snapshot_date": None,
            "history_span_days": 0,
            "missing_days_estimate": days,
            "max_gap_days": None,
            "is_sufficient_for_volatility": False,
            "status": "insufficient_history",
        }

    latest_snapshot = snapshots[-1]
    earliest_snapshot = snapshots[0]
    history_span_days = (latest_snapshot.fecha - earliest_snapshot.fecha).days if count >= 2 else 0

    max_gap_days = 0
    for prev, curr in zip(snapshots, snapshots[1:]):
        gap_days = (curr.fecha - prev.fecha).days
        if gap_days > max_gap_days:
            max_gap_days = gap_days

    missing_days_estimate = max(days - count, 0)
    is_sufficient = count >= 5 and history_span_days >= 7

    return {
        "requested_days": days,
        "snapshots_count": count,
        "latest_snapshot_date": latest_snapshot.fecha.isoformat() if latest_snapshot else None,
        "latest_snapshot_at": (
            timezone.localtime(latest_snapshot.updated_at).strftime("%Y-%m-%d %H:%M")
            if latest_snapshot and latest_snapshot.updated_at
            else None
        ),
        "history_span_days": history_span_days,
        "missing_days_estimate": missing_days_estimate,
        "max_gap_days": max_gap_days if count >= 2 else None,
        "is_sufficient_for_volatility": is_sufficient,
        "status": "ok" if is_sufficient else "insufficient_history",
    }


def get_active_alerts() -> list:
    """Obtiene todas las alertas activas ordenadas por severidad y fecha."""
    from django.db.models import Case, When, IntegerField

    # Ordenar por severidad (critical > warning > info) y luego por fecha
    severity_order = Case(
        When(severidad='critical', then=3),
        When(severidad='warning', then=2),
        When(severidad='info', then=1),
        default=0,
        output_field=IntegerField(),
    )

    alerts = Alert.objects.filter(is_active=True).order_by(
        -severity_order, '-created_at'
    )

    return list(alerts.values(
        'id', 'tipo', 'mensaje', 'severidad', 'valor',
        'simbolo', 'sector', 'pais', 'created_at', 'is_acknowledged'
    ))


def _get_active_risk_contribution_result() -> Dict:
    base_risk_service = RiskContributionService()
    covariance_risk_service = CovarianceAwareRiskContributionService(base_service=base_risk_service)
    base_risk_result = base_risk_service.calculate()
    covariance_risk_result = covariance_risk_service.calculate()
    active_result = (
        covariance_risk_result
        if covariance_risk_result.get("model_variant") == "covariance_aware"
        else base_risk_result
    )
    return {
        "base_result": base_risk_result,
        "covariance_result": covariance_risk_result,
        "active_result": active_result,
    }


def get_risk_contribution_detail() -> Dict:
    """Devuelve el drill-down completo del modelo de risk contribution activo."""

    def build():
        resolved = _get_active_risk_contribution_result()
        result = resolved["active_result"]
        covariance_result = resolved["covariance_result"]
        by_sector = [
            {
                "rank": index,
                "key": item.get("key"),
                "weight_pct": item.get("weight_pct"),
                "contribution_pct": item.get("contribution_pct"),
                "risk_vs_weight_delta": round(
                    float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                    2,
                ),
            }
            for index, item in enumerate(result.get("by_sector", []), start=1)
        ]
        by_country = [
            {
                "rank": index,
                "key": item.get("key"),
                "weight_pct": item.get("weight_pct"),
                "contribution_pct": item.get("contribution_pct"),
                "risk_vs_weight_delta": round(
                    float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                    2,
                ),
            }
            for index, item in enumerate(result.get("by_country", []), start=1)
        ]

        items = [
            {
                "rank": index,
                "symbol": item.get("symbol"),
                "sector": item.get("sector"),
                "country": item.get("country"),
                "asset_type": item.get("asset_type"),
                "weight_pct": item.get("weight_pct"),
                "volatility_proxy": item.get("volatility_proxy"),
                "risk_score": item.get("risk_score"),
                "contribution_pct": item.get("contribution_pct"),
                "risk_vs_weight_delta": round(
                    float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                    2,
                ),
                "used_volatility_fallback": item.get("used_volatility_fallback", False),
            }
            for index, item in enumerate(result.get("items", []), start=1)
        ]

        metadata = result.get("metadata", {})
        top_asset = result.get("top_contributors", [{}])[0] if result.get("top_contributors") else None
        top_sector = result.get("by_sector", [{}])[0] if result.get("by_sector") else None

        return {
            "items": items,
            "by_sector": by_sector,
            "by_country": by_country,
            "top_asset": top_asset,
            "top_sector": top_sector,
            "model_variant": covariance_result.get("model_variant", "mvp_proxy"),
            "covariance_observations": int(covariance_result.get("covariance_observations") or 0),
            "coverage_pct": float(covariance_result.get("coverage_pct") or 0.0),
            "portfolio_volatility_proxy": covariance_result.get("portfolio_volatility_proxy"),
            "confidence": metadata.get("confidence", "low"),
            "warnings": metadata.get("warnings", []),
            "methodology": metadata.get("methodology"),
            "limitations": metadata.get("limitations"),
            "covered_symbols": covariance_result.get("covered_symbols", []),
            "excluded_symbols": covariance_result.get("excluded_symbols", []),
        }

    return _get_cached_selector_result("risk_contribution_detail", build)


def get_scenario_analysis_detail() -> Dict:
    """Devuelve el drill-down analítico completo de scenario analysis."""

    def build():
        scenario_service = ScenarioAnalysisService()
        catalog_service = ScenarioCatalogService()
        scenario_rows = []

        for scenario in catalog_service.list_scenarios():
            result = scenario_service.analyze(scenario["scenario_key"])
            top_sector = result.get("by_sector", [{}])[0] if result.get("by_sector") else None
            top_country = result.get("by_country", [{}])[0] if result.get("by_country") else None
            scenario_rows.append(
                {
                    "scenario_key": scenario["scenario_key"],
                    "label": scenario.get("label"),
                    "description": scenario.get("description"),
                    "category": scenario.get("category"),
                    "total_impact_pct": float(result.get("total_impact_pct") or 0.0),
                    "total_impact_money": float(result.get("total_impact_money") or 0.0),
                    "top_sector": top_sector,
                    "top_country": top_country,
                    "by_asset": result.get("by_asset", []),
                    "by_sector": result.get("by_sector", []),
                    "by_country": result.get("by_country", []),
                    "top_negative_contributors": result.get("top_negative_contributors", []),
                    "metadata": result.get("metadata", {}),
                }
            )

        sorted_rows = sorted(
            scenario_rows,
            key=lambda item: float(item.get("total_impact_pct") or 0.0),
        )
        ranked_rows = [
            {
                **item,
                "severity_rank": index,
            }
            for index, item in enumerate(sorted_rows, start=1)
        ]
        worst_scenario = ranked_rows[0] if ranked_rows else None

        worst_assets = []
        worst_sectors = []
        worst_countries = []
        if worst_scenario:
            worst_assets = [
                {
                    "rank": index,
                    "symbol": item.get("symbol"),
                    "market_value": item.get("market_value"),
                    "estimated_impact_pct": item.get("estimated_impact_pct"),
                    "estimated_impact_money": item.get("estimated_impact_money"),
                    "transmission_channel": item.get("transmission_channel"),
                }
                for index, item in enumerate(worst_scenario.get("by_asset", []), start=1)
            ]
            worst_sectors = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_scenario.get("by_sector", []), start=1)
            ]
            worst_countries = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_scenario.get("by_country", []), start=1)
            ]

        return {
            "scenarios": ranked_rows,
            "worst_scenario": worst_scenario,
            "worst_assets": worst_assets,
            "worst_sectors": worst_sectors,
            "worst_countries": worst_countries,
            "confidence": (worst_scenario or {}).get("metadata", {}).get("confidence", "low"),
            "warnings": (worst_scenario or {}).get("metadata", {}).get("warnings", []),
            "methodology": (worst_scenario or {}).get("metadata", {}).get("methodology"),
            "limitations": (worst_scenario or {}).get("metadata", {}).get("limitations"),
        }

    return _get_cached_selector_result("scenario_analysis_detail", build)


def get_factor_exposure_detail() -> Dict:
    """Devuelve el drill-down analitico completo de factor exposure."""

    def build():
        factor_service = FactorExposureService()
        explanation_service = AnalyticsExplanationService()
        result = factor_service.calculate()

        factor_rows = [
            {
                "rank": index,
                "factor": item.get("factor"),
                "exposure_pct": float(item.get("exposure_pct") or 0.0),
                "contribution_relative_pct": float(item.get("exposure_pct") or 0.0),
                "confidence": item.get("confidence", "low"),
            }
            for index, item in enumerate(
                sorted(
                    result.get("factors", []),
                    key=lambda entry: float(entry.get("exposure_pct") or 0.0),
                    reverse=True,
                ),
                start=1,
            )
        ]
        dominant_factor_key = result.get("dominant_factor")
        dominant_factor = next(
            (item for item in factor_rows if item.get("factor") == dominant_factor_key),
            None,
        )
        unknown_assets = [
            {
                "rank": index,
                "symbol": symbol,
            }
            for index, symbol in enumerate(result.get("unknown_assets", []), start=1)
        ]
        metadata = result.get("metadata", {})

        return {
            "factors": factor_rows,
            "dominant_factor": dominant_factor,
            "dominant_factor_key": dominant_factor_key,
            "underrepresented_factors": result.get("underrepresented_factors", []),
            "unknown_assets": unknown_assets,
            "unknown_assets_count": len(unknown_assets),
            "confidence": metadata.get("confidence", "low"),
            "warnings": metadata.get("warnings", []),
            "methodology": metadata.get("methodology"),
            "limitations": metadata.get("limitations"),
            "interpretation": explanation_service.build_factor_exposure_explanation(result),
        }

    return _get_cached_selector_result("factor_exposure_detail", build)


def get_stress_fragility_detail() -> Dict:
    """Devuelve el drill-down analitico completo de stress fragility."""

    def build():
        stress_service = StressFragilityService()
        stress_catalog_service = StressCatalogService()
        explanation_service = AnalyticsExplanationService()

        stress_rows = []
        for stress in stress_catalog_service.list_stresses():
            result = stress_service.calculate(stress["stress_key"])
            top_sector = result.get("vulnerable_sectors", [{}])[0] if result.get("vulnerable_sectors") else None
            top_country = result.get("vulnerable_countries", [{}])[0] if result.get("vulnerable_countries") else None
            stress_rows.append(
                {
                    "stress_key": stress["stress_key"],
                    "scenario_key": result.get("scenario_key", stress["stress_key"]),
                    "label": stress.get("label"),
                    "description": stress.get("description"),
                    "fragility_score": float(result.get("fragility_score") or 0.0),
                    "total_loss_pct": float(result.get("total_loss_pct") or 0.0),
                    "total_loss_money": float(result.get("total_loss_money") or 0.0),
                    "top_sector": top_sector,
                    "top_country": top_country,
                    "vulnerable_assets": result.get("vulnerable_assets", []),
                    "vulnerable_sectors": result.get("vulnerable_sectors", []),
                    "vulnerable_countries": result.get("vulnerable_countries", []),
                    "metadata": result.get("metadata", {}),
                }
            )

        sorted_rows = sorted(
            stress_rows,
            key=lambda item: float(item.get("total_loss_pct") or 0.0),
        )
        ranked_rows = [
            {
                **item,
                "severity_rank": index,
            }
            for index, item in enumerate(sorted_rows, start=1)
        ]
        worst_stress = ranked_rows[0] if ranked_rows else None

        worst_assets = []
        worst_sectors = []
        worst_countries = []
        if worst_stress:
            worst_assets = [
                {
                    "rank": index,
                    "symbol": item.get("symbol"),
                    "market_value": item.get("market_value"),
                    "estimated_impact_pct": item.get("estimated_impact_pct"),
                    "estimated_impact_money": item.get("estimated_impact_money"),
                    "transmission_channel": item.get("transmission_channel"),
                }
                for index, item in enumerate(worst_stress.get("vulnerable_assets", []), start=1)
            ]
            worst_sectors = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_stress.get("vulnerable_sectors", []), start=1)
            ]
            worst_countries = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_stress.get("vulnerable_countries", []), start=1)
            ]

        return {
            "stresses": ranked_rows,
            "worst_stress": worst_stress,
            "worst_assets": worst_assets,
            "worst_sectors": worst_sectors,
            "worst_countries": worst_countries,
            "confidence": (worst_stress or {}).get("metadata", {}).get("confidence", "low"),
            "warnings": (worst_stress or {}).get("metadata", {}).get("warnings", []),
            "methodology": (worst_stress or {}).get("metadata", {}).get("methodology"),
            "limitations": (worst_stress or {}).get("metadata", {}).get("limitations"),
            "interpretation": explanation_service.build_stress_fragility_explanation(worst_stress or {}),
        }

    return _get_cached_selector_result("stress_fragility_detail", build)


def get_expected_return_detail() -> Dict:
    """Devuelve el drill-down analitico completo de expected return."""

    def build():
        expected_return_service = ExpectedReturnService()
        explanation_service = AnalyticsExplanationService()
        result = expected_return_service.calculate()

        bucket_rows = [
            {
                "rank": index,
                "bucket_key": item.get("bucket_key"),
                "label": item.get("label"),
                "weight_pct": item.get("weight_pct"),
                "expected_return_pct": item.get("expected_return_pct"),
                "real_expected_return_pct": None,
                "contribution_relative_pct": (
                    round(
                        (float(item.get("weight_pct") or 0.0) / 100.0)
                        * float(item.get("expected_return_pct") or 0.0),
                        2,
                    )
                    if item.get("expected_return_pct") is not None
                    else None
                ),
                "basis_reference": item.get("basis_reference"),
            }
            for index, item in enumerate(
                sorted(
                    result.get("by_bucket", []),
                    key=lambda entry: float(entry.get("weight_pct") or 0.0),
                    reverse=True,
                ),
                start=1,
            )
        ]

        dominant_bucket = bucket_rows[0] if bucket_rows else None
        metadata = result.get("metadata", {})
        warnings = metadata.get("warnings", [])

        return {
            "expected_return_pct": result.get("expected_return_pct"),
            "real_expected_return_pct": result.get("real_expected_return_pct"),
            "basis_reference": result.get("basis_reference"),
            "dominant_bucket": dominant_bucket,
            "bucket_rows": bucket_rows,
            "asset_rows": [],
            "confidence": metadata.get("confidence", "low"),
            "warnings": warnings,
            "main_warning": warnings[0] if warnings else None,
            "methodology": metadata.get("methodology"),
            "limitations": metadata.get("limitations"),
            "assumptions": [
                "El modelo agrupa posiciones actuales en buckets estructurales.",
                "Las referencias usan SPY, EMB o BADLAR con fallbacks explícitos cuando falta historia suficiente.",
                "El retorno real depende de una referencia de inflación disponible al momento del cálculo.",
            ],
            "interpretation": explanation_service.build_expected_return_explanation(result),
        }

    return _get_cached_selector_result("expected_return_detail", build)


def get_monthly_allocation_plan(capital_amount: int | float = 600000) -> Dict:
    """Devuelve la propuesta mvp de asignacion mensual incremental."""

    cache_key = f"monthly_allocation_plan:{int(capital_amount)}"

    def build():
        service = MonthlyAllocationService()
        return service.build_plan(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_candidate_asset_ranking(capital_amount: int | float = 600000) -> Dict:
    """Devuelve el ranking de activos candidatos dentro de los bloques recomendados."""

    cache_key = f"candidate_asset_ranking:{int(capital_amount)}"

    def build():
        service = CandidateAssetRankingService()
        return service.build_ranking(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation(capital_amount: int | float = 600000) -> Dict:
    """Construye una simulacion incremental default usando top candidato por bloque recomendado."""

    cache_key = f"incremental_portfolio_simulation:{int(capital_amount)}"

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        proposal = _build_top_candidate_purchase_plan(monthly_plan, candidate_ranking)
        if not proposal["purchase_plan"]:
            return {
                "capital_amount": float(capital_amount),
                "purchase_plan": [],
                "selected_candidates": [],
                "unmapped_blocks": proposal["unmapped_blocks"],
                "before": {},
                "after": {},
                "delta": {
                    "expected_return_change": None,
                    "real_expected_return_change": None,
                    "fragility_change": None,
                    "scenario_loss_change": None,
                    "risk_concentration_change": None,
                },
                "interpretation": "No hay candidatos suficientes para simular una propuesta incremental por defecto.",
                "warnings": ["no_candidate_purchase_plan"],
            }

        result = IncrementalPortfolioSimulator().simulate(
            {
                "capital_amount": capital_amount,
                "purchase_plan": proposal["purchase_plan"],
            }
        )
        result["selected_candidates"] = proposal["selected_candidates"]
        result["unmapped_blocks"] = proposal["unmapped_blocks"]
        result["selection_basis"] = "top_candidate_per_recommended_block"
        return result

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation_comparison(capital_amount: int | float = 600000) -> Dict:
    """Compara variantes simples de propuestas incrementales sobre el mismo capital mensual."""

    cache_key = f"incremental_portfolio_simulation_comparison:{int(capital_amount)}"

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        simulator = IncrementalPortfolioSimulator()

        proposals = []
        for proposal_key, label, builder in (
            ("top_candidate_per_block", "Top candidato por bloque", _build_top_candidate_purchase_plan),
            ("runner_up_when_available", "Segundo candidato si existe", _build_runner_up_purchase_plan),
            ("split_largest_block_top_two", "Split del bloque más grande", _build_split_largest_block_purchase_plan),
        ):
            proposal = builder(monthly_plan, candidate_ranking)
            if not proposal["purchase_plan"]:
                proposals.append(
                    {
                        "proposal_key": proposal_key,
                        "label": label,
                        "purchase_plan": [],
                        "selected_candidates": [],
                        "unmapped_blocks": proposal["unmapped_blocks"],
                        "simulation": {
                            "before": {},
                            "after": {},
                            "delta": {
                                "expected_return_change": None,
                                "real_expected_return_change": None,
                                "fragility_change": None,
                                "scenario_loss_change": None,
                                "risk_concentration_change": None,
                            },
                            "interpretation": "No hay candidatos suficientes para construir esta variante.",
                        },
                        "comparison_score": None,
                    }
                )
                continue

            simulation = simulator.simulate(
                {
                    "capital_amount": capital_amount,
                    "purchase_plan": proposal["purchase_plan"],
                }
            )
            proposals.append(
                {
                    "proposal_key": proposal_key,
                    "label": label,
                    "purchase_plan": proposal["purchase_plan"],
                    "selected_candidates": proposal["selected_candidates"],
                    "unmapped_blocks": proposal["unmapped_blocks"],
                    "simulation": {
                        "before": simulation["before"],
                        "after": simulation["after"],
                        "delta": simulation["delta"],
                        "interpretation": simulation["interpretation"],
                    },
                    "comparison_score": _score_incremental_simulation(simulation),
                }
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "capital_amount": float(capital_amount),
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_manual_incremental_portfolio_simulation_comparison(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    """Compara planes incrementales definidos manualmente desde Planeacion."""

    form_state = _build_manual_incremental_comparison_form_state(
        query_params,
        default_capital_amount=default_capital_amount,
    )
    normalized_plans = form_state["normalized_plans"]
    if not normalized_plans:
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
        }

    signature = hashlib.md5(
        json.dumps(
            [
                {
                    "proposal_key": plan["proposal_key"],
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
                for plan in normalized_plans
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"manual_incremental_portfolio_simulation_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for plan in normalized_plans:
            simulation = simulator.simulate(
                {
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
            )
            proposals.append(
                {
                    "proposal_key": plan["proposal_key"],
                    "label": plan["label"],
                    "purchase_plan": plan["purchase_plan"],
                    "capital_amount": plan["capital_amount"],
                    "input_warnings": plan["warnings"],
                    "simulation": {
                        "before": simulation["before"],
                        "after": simulation["after"],
                        "delta": simulation["delta"],
                        "interpretation": simulation["interpretation"],
                        "warnings": simulation.get("warnings", []),
                    },
                    "comparison_score": _score_incremental_simulation(simulation),
                }
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara candidatos individuales dentro de un bloque recomendado."""

    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    requested_block = str(_query_param_value(query_params, "candidate_compare_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_compare", "")).strip() == "1"

    selected_block = requested_block if requested_block in {item["bucket"] for item in comparable_blocks} else None
    if selected_block is None and comparable_blocks:
        selected_block = comparable_blocks[0]["bucket"]

    if selected_block is None:
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
        }

    selected_block_data = next(item for item in comparable_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for candidate in selected_block_data["candidates"][:3]:
            purchase_plan = [
                {
                    "symbol": candidate["asset"],
                    "amount": round(float(selected_block_data["suggested_amount"]), 2),
                }
            ]
            simulation = simulator.simulate(
                {
                    "capital_amount": float(selected_block_data["suggested_amount"]),
                    "purchase_plan": purchase_plan,
                }
            )
            proposals.append(
                {
                    "proposal_key": candidate["asset"],
                    "label": candidate["asset"],
                    "candidate": candidate,
                    "purchase_plan": purchase_plan,
                    "simulation": {
                        "before": simulation["before"],
                        "after": simulation["after"],
                        "delta": simulation["delta"],
                        "interpretation": simulation["interpretation"],
                        "warnings": simulation.get("warnings", []),
                    },
                    "comparison_score": _score_incremental_simulation(simulation),
                }
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": selected_block_data["suggested_amount"],
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_split_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara concentrar el bloque en un candidato vs repartirlo entre top 2."""

    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    split_blocks = [block for block in comparable_blocks if len(block["candidates"]) >= 2]
    requested_block = str(_query_param_value(query_params, "candidate_split_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_split_compare", "")).strip() == "1"

    selected_block = requested_block if requested_block in {item["bucket"] for item in split_blocks} else None
    if selected_block is None and split_blocks:
        selected_block = split_blocks[0]["bucket"]

    if selected_block is None:
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
        }

    selected_block_data = next(item for item in split_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"][:2],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_split_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        top_candidate = selected_block_data["candidates"][0]
        runner_up = selected_block_data["candidates"][1]
        total_amount = round(float(selected_block_data["suggested_amount"]), 2)
        half_amount = round(total_amount / 2.0, 2)
        remainder_amount = round(total_amount - half_amount, 2)

        variants = [
            {
                "proposal_key": "single_top_candidate",
                "label": f"Concentrado en {top_candidate['asset']}",
                "purchase_plan": [{"symbol": top_candidate["asset"], "amount": total_amount}],
                "composition": [top_candidate["asset"]],
            },
            {
                "proposal_key": "split_top_two",
                "label": f"Split {top_candidate['asset']} + {runner_up['asset']}",
                "purchase_plan": [
                    {"symbol": top_candidate["asset"], "amount": half_amount},
                    {"symbol": runner_up["asset"], "amount": remainder_amount},
                ],
                "composition": [top_candidate["asset"], runner_up["asset"]],
            },
        ]

        proposals = []
        for variant in variants:
            simulation = simulator.simulate(
                {
                    "capital_amount": total_amount,
                    "purchase_plan": variant["purchase_plan"],
                }
            )
            proposals.append(
                {
                    "proposal_key": variant["proposal_key"],
                    "label": variant["label"],
                    "purchase_plan": variant["purchase_plan"],
                    "composition": variant["composition"],
                    "simulation": {
                        "before": simulation["before"],
                        "after": simulation["after"],
                        "delta": simulation["delta"],
                        "interpretation": simulation["interpretation"],
                        "warnings": simulation.get("warnings", []),
                    },
                    "comparison_score": _score_incremental_simulation(simulation),
                }
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": total_amount,
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_preferred_incremental_portfolio_proposal(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza la mejor propuesta incremental disponible entre los comparadores activos."""

    auto = get_incremental_portfolio_simulation_comparison(capital_amount=capital_amount)
    candidate = get_candidate_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    split = get_candidate_split_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    manual = get_manual_incremental_portfolio_simulation_comparison(
        query_params,
        default_capital_amount=capital_amount,
    )

    candidates = []
    for source_key, label, payload in (
        ("automatic_variants", "Comparador automático", auto),
        ("candidate_block", "Comparador por candidato", candidate),
        ("candidate_split", "Comparador por split", split),
        ("manual_plan", "Comparador manual", manual),
    ):
        best_item = _extract_best_incremental_proposal(payload)
        if best_item is None:
            continue
        candidates.append(
            {
                "source_key": source_key,
                "source_label": label,
                "proposal_key": best_item["proposal_key"],
                "proposal_label": best_item["label"],
                "purchase_plan": best_item.get("purchase_plan", []),
                "comparison_score": best_item.get("comparison_score"),
                "simulation": best_item.get("simulation", {}),
                "selected_context": _build_preferred_proposal_context(source_key, payload),
                "priority_rank": _preferred_source_priority_rank(source_key, payload),
            }
        )

    best = None
    if candidates:
        best = sorted(
            candidates,
            key=lambda item: (
                float(item["comparison_score"] if item["comparison_score"] is not None else float("-inf")),
                item["priority_rank"],
            ),
            reverse=True,
        )[0]

    return {
        "candidates": candidates,
        "preferred": best,
        "has_manual_override": bool(manual.get("submitted") and manual.get("proposals")),
        "explanation": _build_preferred_incremental_explanation(best, manual),
    }


def get_incremental_proposal_history(*, user, limit: int = 5) -> Dict:
    """Retorna historial reciente de propuestas incrementales guardadas por el usuario."""

    raw_items = IncrementalProposalHistoryService().list_recent(user=user, limit=limit)
    items = []
    for item in raw_items:
        reapply = _build_incremental_snapshot_reapply_payload(item)
        enriched = dict(item)
        enriched.update(reapply)
        items.append(enriched)
    return {
        "items": items,
        "count": len(items),
        "has_history": bool(items),
    }


def _candidate_blocks_map(candidate_ranking: Dict) -> Dict[str, Dict]:
    return {
        str(item.get("block") or ""): item
        for item in candidate_ranking.get("by_block", [])
    }


def _build_incremental_snapshot_reapply_payload(item: Dict) -> Dict:
    purchase_plan = list(item.get("purchase_plan") or [])
    query_items = [("manual_compare", "1")]
    capital_amount = item.get("capital_amount")
    if capital_amount:
        query_items.append(("plan_a_capital", _stringify_reapply_amount(capital_amount)))

    for index, purchase in enumerate(purchase_plan[:3], start=1):
        query_items.append((f"plan_a_symbol_{index}", str(purchase.get("symbol") or "").strip().upper()))
        query_items.append((f"plan_a_amount_{index}", _stringify_reapply_amount(purchase.get("amount") or 0)))

    return {
        "reapply_querystring": urlencode(query_items),
        "reapply_truncated": len(purchase_plan) > 3,
    }


def _stringify_reapply_amount(value) -> str:
    amount = float(value or 0)
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}"


def _extract_best_incremental_proposal(payload: Dict) -> Dict | None:
    best_key = payload.get("best_proposal_key")
    if not best_key:
        return None
    for proposal in payload.get("proposals", []):
        if proposal.get("proposal_key") == best_key:
            return proposal
    return None


def _preferred_source_priority_rank(source_key: str, payload: Dict) -> int:
    if source_key == "manual_plan" and payload.get("submitted") and payload.get("proposals"):
        return 4
    if source_key == "candidate_split":
        return 3
    if source_key == "candidate_block":
        return 2
    return 1


def _build_preferred_proposal_context(source_key: str, payload: Dict) -> str | None:
    if source_key == "candidate_block":
        return payload.get("selected_label")
    if source_key == "candidate_split":
        return payload.get("selected_label")
    if source_key == "manual_plan":
        return "Plan manual enviado por el usuario" if payload.get("submitted") else None
    return None


def _build_preferred_incremental_explanation(best: Dict | None, manual_payload: Dict) -> str:
    if best is None:
        return "Todavia no hay una propuesta incremental preferida construible con los comparadores actuales."
    if best["source_key"] == "manual_plan" and manual_payload.get("submitted"):
        return (
            f"La propuesta preferida actual sale del comparador manual: {best['proposal_label']}. "
            "Se prioriza porque refleja una intencion explicita del usuario y ademas lidera el score comparativo disponible."
        )
    context = f" para {best['selected_context']}" if best.get("selected_context") else ""
    return (
        f"La propuesta preferida actual surge de {best['source_label']}{context}: {best['proposal_label']}. "
        "Se selecciona por score comparativo y desempate de prioridad entre comparadores."
    )


def _build_comparable_candidate_blocks(monthly_plan: Dict, candidate_ranking: Dict) -> list[Dict]:
    by_block = _candidate_blocks_map(candidate_ranking)
    comparable_blocks = []
    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        candidates = by_block.get(bucket, {}).get("candidates", [])
        if not candidates:
            continue
        comparable_blocks.append(
            {
                "bucket": bucket,
                "label": block.get("label", bucket),
                "suggested_amount": float(block.get("suggested_amount") or 0.0),
                "candidates": [
                    {
                        "asset": candidate.get("asset"),
                        "score": candidate.get("score"),
                        "main_reason": candidate.get("main_reason"),
                    }
                    for candidate in candidates[:3]
                ],
            }
        )
    return comparable_blocks


def _build_purchase_plan_variant(monthly_plan: Dict, candidate_ranking: Dict, *, candidate_index: int) -> Dict:
    by_block = _candidate_blocks_map(candidate_ranking)
    purchase_amounts: Dict[str, float] = {}
    selected_candidates = []
    unmapped_blocks = []

    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        amount = float(block.get("suggested_amount") or 0.0)
        block_candidates = by_block.get(bucket, {}).get("candidates", [])
        if amount <= 0 or not block_candidates:
            unmapped_blocks.append(block.get("label", bucket))
            continue
        idx = candidate_index if len(block_candidates) > candidate_index else 0
        candidate = block_candidates[idx]
        symbol = candidate.get("asset")
        purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + amount
        selected_candidates.append(
            {
                "symbol": symbol,
                "block": bucket,
                "block_label": block.get("label", bucket),
                "amount": amount,
                "candidate_score": candidate.get("score"),
                "candidate_reason": candidate.get("main_reason"),
            }
        )

    purchase_plan = [
        {"symbol": symbol, "amount": round(amount, 2)}
        for symbol, amount in purchase_amounts.items()
    ]
    return {
        "purchase_plan": purchase_plan,
        "selected_candidates": selected_candidates,
        "unmapped_blocks": unmapped_blocks,
    }


def _build_top_candidate_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    return _build_purchase_plan_variant(monthly_plan, candidate_ranking, candidate_index=0)


def _build_runner_up_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    return _build_purchase_plan_variant(monthly_plan, candidate_ranking, candidate_index=1)


def _build_split_largest_block_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    by_block = _candidate_blocks_map(candidate_ranking)
    recommended_blocks = sorted(
        monthly_plan.get("recommended_blocks", []),
        key=lambda item: float(item.get("suggested_amount") or 0.0),
        reverse=True,
    )
    purchase_amounts: Dict[str, float] = {}
    selected_candidates = []
    unmapped_blocks = []

    split_bucket = None
    for block in recommended_blocks:
        bucket = str(block.get("bucket") or "")
        if len(by_block.get(bucket, {}).get("candidates", [])) >= 2:
            split_bucket = bucket
            break

    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        amount = float(block.get("suggested_amount") or 0.0)
        candidates = by_block.get(bucket, {}).get("candidates", [])
        if amount <= 0 or not candidates:
            unmapped_blocks.append(block.get("label", bucket))
            continue

        if bucket == split_bucket:
            first = candidates[0]
            second = candidates[1]
            first_amount = round(amount / 2.0, 2)
            second_amount = round(amount - first_amount, 2)
            for candidate, candidate_amount in ((first, first_amount), (second, second_amount)):
                symbol = candidate.get("asset")
                purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + candidate_amount
                selected_candidates.append(
                    {
                        "symbol": symbol,
                        "block": bucket,
                        "block_label": block.get("label", bucket),
                        "amount": candidate_amount,
                        "candidate_score": candidate.get("score"),
                        "candidate_reason": candidate.get("main_reason"),
                    }
                )
            continue

        candidate = candidates[0]
        symbol = candidate.get("asset")
        purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + amount
        selected_candidates.append(
            {
                "symbol": symbol,
                "block": bucket,
                "block_label": block.get("label", bucket),
                "amount": amount,
                "candidate_score": candidate.get("score"),
                "candidate_reason": candidate.get("main_reason"),
            }
        )

    purchase_plan = [
        {"symbol": symbol, "amount": round(amount, 2)}
        for symbol, amount in purchase_amounts.items()
    ]
    return {
        "purchase_plan": purchase_plan,
        "selected_candidates": selected_candidates,
        "unmapped_blocks": unmapped_blocks,
    }


def _score_incremental_simulation(simulation: Dict) -> float:
    delta = simulation.get("delta", {})
    score = 0.0
    score += float(delta.get("expected_return_change") or 0.0)
    score += float(delta.get("real_expected_return_change") or 0.0) * 0.5
    score += float(delta.get("scenario_loss_change") or 0.0) * 0.75
    score -= float(delta.get("fragility_change") or 0.0)
    score -= float(delta.get("risk_concentration_change") or 0.0) * 0.5
    return round(score, 2)


def _build_manual_incremental_comparison_form_state(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    submitted = str(_query_param_value(query_params, "manual_compare", "")).strip() == "1"
    plans = []
    normalized_plans = []

    for plan_key, label in (("plan_a", "Plan manual A"), ("plan_b", "Plan manual B")):
        capital_raw = str(_query_param_value(query_params, f"{plan_key}_capital", "")).strip()
        rows = []
        for index in range(1, 4):
            rows.append(
                {
                    "symbol": str(_query_param_value(query_params, f"{plan_key}_symbol_{index}", "")).strip().upper(),
                    "amount_raw": str(_query_param_value(query_params, f"{plan_key}_amount_{index}", "")).strip(),
                }
            )

        warnings = []
        purchase_plan = []
        total_amount = 0.0
        touched_rows = 0
        for row in rows:
            symbol = row["symbol"]
            amount = _coerce_manual_amount(row["amount_raw"])
            if symbol or row["amount_raw"]:
                touched_rows += 1
            if not symbol and not row["amount_raw"]:
                continue
            if not symbol:
                warnings.append("missing_symbol")
                continue
            if amount <= 0:
                warnings.append(f"invalid_amount:{symbol}")
                continue
            amount = round(amount, 2)
            purchase_plan.append({"symbol": symbol, "amount": amount})
            total_amount += amount

        capital_amount = _coerce_manual_amount(capital_raw)
        if capital_amount <= 0:
            capital_amount = total_amount if total_amount > 0 else float(default_capital_amount)
        capital_amount = round(capital_amount, 2)

        plan_state = {
            "plan_key": plan_key,
            "label": label,
            "capital_raw": capital_raw or str(int(default_capital_amount)),
            "rows": rows,
            "warnings": warnings,
            "has_input": touched_rows > 0 or bool(capital_raw),
        }
        plans.append(plan_state)

        if purchase_plan:
            normalized_plans.append(
                {
                    "proposal_key": plan_key,
                    "label": label,
                    "capital_amount": capital_amount,
                    "purchase_plan": purchase_plan,
                    "warnings": warnings,
                }
            )

    return {
        "submitted": submitted,
        "plans": plans,
        "normalized_plans": normalized_plans,
    }


def _query_param_value(query_params, key: str, default=""):
    getter = getattr(query_params, "get", None)
    if callable(getter):
        return getter(key, default)
    if isinstance(query_params, dict):
        return query_params.get(key, default)
    return default


def _coerce_manual_amount(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_analytics_v2_dashboard_summary() -> Dict:
    """Resume Analytics v2 para consumo server-rendered en dashboard."""

    def build():
        resolved_risk = _get_active_risk_contribution_result()
        base_risk_service = RiskContributionService()
        covariance_risk_result = resolved_risk["covariance_result"]
        risk_result = resolved_risk["active_result"]
        scenario_service = ScenarioAnalysisService()
        factor_service = FactorExposureService()
        explanation_service = AnalyticsExplanationService()
        stress_service = StressFragilityService()
        expected_return_service = ExpectedReturnService()
        local_macro_service = LocalMacroSignalsService()

        argentina_stress = scenario_service.analyze("argentina_stress")
        tech_shock = scenario_service.analyze("tech_shock")
        fragility = stress_service.calculate("local_crisis_severe")
        factor_result = factor_service.calculate()
        expected_return_result = expected_return_service.calculate()
        local_macro_result = local_macro_service.calculate()

        combined_signals = (
            base_risk_service.build_recommendation_signals(top_n=5)
            + scenario_service.build_recommendation_signals()
            + factor_service.build_recommendation_signals()
            + stress_service.build_recommendation_signals()
            + expected_return_service.build_recommendation_signals()
            + local_macro_service.build_recommendation_signals()
        )
        combined_signals = sorted(
            combined_signals,
            key=lambda signal: {"high": 0, "medium": 1, "low": 2}.get(signal.get("severity"), 3)
        )

        top_risk_asset = risk_result["top_contributors"][0] if risk_result.get("top_contributors") else None
        top_risk_sector = risk_result["by_sector"][0] if risk_result.get("by_sector") else None
        dominant_factor_key = factor_result.get("dominant_factor")
        dominant_factor = next(
            (item for item in factor_result.get("factors", []) if item.get("factor") == dominant_factor_key),
            None,
        )
        covariance_variant = covariance_risk_result.get("model_variant", "mvp_proxy")
        covariance_observations = int(covariance_risk_result.get("covariance_observations") or 0)
        covariance_coverage_pct = float(covariance_risk_result.get("coverage_pct") or 0.0)
        covariance_warning = next(
            iter(covariance_risk_result.get("metadata", {}).get("warnings", [])),
            None,
        )
        worst_scenario = (
            {
                "label": "Argentina Stress",
                **argentina_stress,
            }
            if (argentina_stress.get("total_impact_pct") or 0) <= (tech_shock.get("total_impact_pct") or 0)
            else {
                "label": "Tech Shock",
                **tech_shock,
            }
        )

        return {
            "risk_contribution": {
                "top_asset": top_risk_asset,
                "top_sector": top_risk_sector,
                "confidence": risk_result["metadata"]["confidence"],
                "warnings_count": len(risk_result["metadata"].get("warnings", [])),
                "model_variant": covariance_variant,
                "covariance_observations": covariance_observations,
                "coverage_pct": covariance_coverage_pct,
                "covariance_warning": covariance_warning,
                "interpretation": explanation_service.build_risk_contribution_explanation(risk_result),
            },
            "scenario_analysis": {
                "argentina_stress_pct": argentina_stress.get("total_impact_pct"),
                "tech_shock_pct": tech_shock.get("total_impact_pct"),
                "confidence": min(
                    argentina_stress["metadata"]["confidence"],
                    tech_shock["metadata"]["confidence"],
                    key=lambda level: {"high": 3, "medium": 2, "low": 1}.get(level, 0),
                ),
                "worst_label": worst_scenario["label"],
                "interpretation": explanation_service.build_scenario_analysis_explanation(
                    {
                        "worst_scenario": worst_scenario,
                    }
                ),
            },
            "factor_exposure": {
                "dominant_factor": dominant_factor_key,
                "dominant_factor_exposure_pct": dominant_factor.get("exposure_pct") if dominant_factor else None,
                "unknown_assets_count": len(factor_result.get("unknown_assets", [])),
                "confidence": factor_result["metadata"]["confidence"],
                "interpretation": explanation_service.build_factor_exposure_explanation(factor_result),
            },
            "stress_testing": {
                "scenario_key": fragility.get("scenario_key"),
                "fragility_score": fragility.get("fragility_score"),
                "total_loss_pct": fragility.get("total_loss_pct"),
                "confidence": fragility["metadata"]["confidence"],
                "interpretation": explanation_service.build_stress_fragility_explanation(fragility),
            },
            "expected_return": {
                "expected_return_pct": expected_return_result.get("expected_return_pct"),
                "real_expected_return_pct": expected_return_result.get("real_expected_return_pct"),
                "confidence": expected_return_result["metadata"]["confidence"],
                "warnings_count": len(expected_return_result["metadata"].get("warnings", [])),
                "interpretation": explanation_service.build_expected_return_explanation(expected_return_result),
            },
            "local_macro": {
                "argentina_weight_pct": local_macro_result.get("summary", {}).get("argentina_weight_pct"),
                "ars_liquidity_weight_pct": local_macro_result.get("summary", {}).get("ars_liquidity_weight_pct"),
                "cer_weight_pct": local_macro_result.get("summary", {}).get("cer_weight_pct"),
                "sovereign_bond_weight_pct": local_macro_result.get("summary", {}).get("sovereign_bond_weight_pct"),
                "local_hard_dollar_bond_weight_pct": local_macro_result.get("summary", {}).get("local_hard_dollar_bond_weight_pct"),
                "local_cer_bond_weight_pct": local_macro_result.get("summary", {}).get("local_cer_bond_weight_pct"),
                "local_hard_dollar_share_pct": local_macro_result.get("summary", {}).get("local_hard_dollar_share_pct"),
                "local_cer_share_pct": local_macro_result.get("summary", {}).get("local_cer_share_pct"),
                "top_local_sovereign_symbol": local_macro_result.get("summary", {}).get("top_local_sovereign_symbol"),
                "top_local_sovereign_share_pct": local_macro_result.get("summary", {}).get("top_local_sovereign_share_pct"),
                "local_sovereign_symbols_count": local_macro_result.get("summary", {}).get("local_sovereign_symbols_count"),
                "local_sovereign_concentration_hhi": local_macro_result.get("summary", {}).get("local_sovereign_concentration_hhi"),
                "badlar_real_carry_pct": local_macro_result.get("summary", {}).get("badlar_real_carry_pct"),
                "usdars_mep": local_macro_result.get("summary", {}).get("usdars_mep"),
                "fx_gap_pct": local_macro_result.get("summary", {}).get("fx_gap_pct"),
                "riesgo_pais_arg": local_macro_result.get("summary", {}).get("riesgo_pais_arg"),
                "ipc_yoy_pct": local_macro_result.get("summary", {}).get("ipc_yoy_pct"),
                "confidence": local_macro_result.get("metadata", {}).get("confidence"),
                "warnings_count": len(local_macro_result.get("metadata", {}).get("warnings", [])),
            },
            "signals": combined_signals[:6],
        }

    return _get_cached_selector_result("analytics_v2_dashboard_summary", build)


