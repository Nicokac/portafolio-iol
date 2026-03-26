from typing import Callable, Dict, List

from django.db.models import Max

from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


def fetch_latest_portafolio_data() -> List[ActivoPortafolioSnapshot]:
    latest_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    if not latest_date:
        return []
    return list(ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date))


def fetch_latest_resumen_data() -> List[ResumenCuentaSnapshot]:
    latest_date = ResumenCuentaSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    if not latest_date:
        return []
    return list(ResumenCuentaSnapshot.objects.filter(fecha_extraccion=latest_date))


def build_current_enriched_portfolio(
    *,
    get_latest_portafolio_data_fn: Callable[[], list],
    build_portafolio_enriquecido_fn: Callable[[list, dict], Dict[str, List[Dict]]],
) -> Dict[str, List[Dict]]:
    portafolio = get_latest_portafolio_data_fn()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    return build_portafolio_enriquecido_fn(portafolio, parametros)


def build_dashboard_kpis_payload(
    *,
    get_latest_portafolio_data_fn: Callable[[], list],
    get_latest_resumen_data_fn: Callable[[], list],
    get_portafolio_enriquecido_actual_fn: Callable[[], Dict[str, List[Dict]]],
    build_dashboard_kpis_fn: Callable[[list, Dict[str, List[Dict]], list], Dict],
) -> Dict:
    portafolio = get_latest_portafolio_data_fn()
    resumen = get_latest_resumen_data_fn()
    portafolio_clasificado = get_portafolio_enriquecido_actual_fn()
    return build_dashboard_kpis_fn(portafolio, portafolio_clasificado, resumen)


def build_macro_local_context_payload(*, total_iol: float | None = None) -> Dict:
    return LocalMacroSeriesService().get_context_summary(total_iol=total_iol)


def build_distribucion_sector_payload(
    *,
    get_activos_invertidos_fn: Callable[[], List[Dict]],
    get_activos_valorizados_con_metadata_fn: Callable[[], List[Dict]],
    base: str,
    build_distribucion_sector_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    return build_distribucion_sector_fn(
        activos_invertidos=get_activos_invertidos_fn(),
        activos_con_metadata=get_activos_valorizados_con_metadata_fn(),
        base=base,
    )


def build_distribucion_pais_payload(
    *,
    get_activos_invertidos_fn: Callable[[], List[Dict]],
    get_activos_valorizados_con_metadata_fn: Callable[[], List[Dict]],
    get_latest_resumen_data_fn: Callable[[], list],
    build_resumen_cash_distribution_by_country_fn: Callable[[list], Dict],
    base: str,
    build_distribucion_pais_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    return build_distribucion_pais_fn(
        activos_invertidos=get_activos_invertidos_fn(),
        activos_con_metadata=get_activos_valorizados_con_metadata_fn(),
        resumen_cash_by_country=build_resumen_cash_distribution_by_country_fn(get_latest_resumen_data_fn()),
        base=base,
    )


def build_distribucion_tipo_patrimonial_payload(
    *,
    get_activos_invertidos_fn: Callable[[], List[Dict]],
    get_activos_valorizados_con_metadata_fn: Callable[[], List[Dict]],
    base: str,
    build_distribucion_tipo_patrimonial_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    return build_distribucion_tipo_patrimonial_fn(
        activos_invertidos=get_activos_invertidos_fn(),
        activos_con_metadata=get_activos_valorizados_con_metadata_fn(),
        base=base,
    )


def build_distribucion_moneda_payload(
    *,
    get_latest_portafolio_data_fn: Callable[[], list],
    get_latest_resumen_data_fn: Callable[[], list],
    build_distribucion_moneda_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    return build_distribucion_moneda_fn(
        portafolio=get_latest_portafolio_data_fn(),
        resumen=get_latest_resumen_data_fn(),
    )


def build_distribucion_moneda_operativa_payload(
    *,
    get_latest_portafolio_data_fn: Callable[[], list],
    get_latest_resumen_data_fn: Callable[[], list],
    build_distribucion_moneda_operativa_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    return build_distribucion_moneda_operativa_fn(
        portafolio=get_latest_portafolio_data_fn(),
        resumen=get_latest_resumen_data_fn(),
    )


def build_riesgo_portafolio_detallado_payload(
    *,
    get_activos_invertidos_fn: Callable[[], List[Dict]],
    get_dashboard_kpis_fn: Callable[[], Dict],
    build_riesgo_portafolio_detallado_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    portafolio = [item["activo"] for item in get_activos_invertidos_fn()]
    kpis = get_dashboard_kpis_fn()
    return build_riesgo_portafolio_detallado_fn(
        portafolio=portafolio,
        total_portafolio=sum(activo.valorizado for activo in portafolio),
        liquidez_operativa=kpis.get("liquidez_operativa", 0),
        total_iol=kpis.get("total_iol", 0),
    )


def build_riesgo_portafolio_payload(
    *,
    get_activos_invertidos_fn: Callable[[], List[Dict]],
    get_dashboard_kpis_fn: Callable[[], Dict],
    build_riesgo_portafolio_fn: Callable[..., Dict[str, float]],
) -> Dict[str, float]:
    portafolio = [item["activo"] for item in get_activos_invertidos_fn()]
    kpis = get_dashboard_kpis_fn()
    return build_riesgo_portafolio_fn(
        portafolio=portafolio,
        total_portafolio=sum(activo.valorizado for activo in portafolio),
        liquidez_operativa=kpis.get("liquidez_operativa", 0),
        total_iol=kpis.get("total_iol", 0),
    )
