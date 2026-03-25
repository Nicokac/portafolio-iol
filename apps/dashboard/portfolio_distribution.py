from typing import Dict, List

from apps.parametros.models import ParametroActivo


# --- Helpers puros ---

def _is_technology_sector(sector: str | None) -> bool:
    if not sector:
        return False
    normalized = str(sector).strip().lower()
    return normalized.startswith('tecnolog')


def _normalize_account_currency(moneda: str | None) -> str:
    normalized = str(moneda or '').strip()
    mapping = {
        'ARS': 'ARS',
        'peso_Argentino': 'ARS',
        'USD': 'USD',
        'dolar_Estadounidense': 'USD',
    }
    return mapping.get(normalized, normalized)


def _build_distribution_from_items(items: List[Dict], field: str) -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for item in items:
        key = item.get(field) or 'Sin clasificar'
        if field == 'pais_exposicion' and key in {'Estados Unidos', 'USA'}:
            key = 'USA'
        distribucion[key] = distribucion.get(key, 0) + float(item['activo'].valorizado)
    return distribucion


def _aggregate_sector_labels(distribucion: Dict[str, float]) -> Dict[str, float]:
    aggregated: Dict[str, float] = {}
    for sector, valor in distribucion.items():
        label = 'Tecnologia Total' if _is_technology_sector(sector) else sector
        aggregated[label] = aggregated.get(label, 0) + float(valor)
    return aggregated


# --- Builders con inputs explícitos ---

def build_resumen_cash_distribution_by_country(resumen: list) -> Dict[str, float]:
    """Distribuye el cash disponible por país (USA / Argentina) según la moneda de cada cuenta."""
    distribucion: Dict[str, float] = {}
    for cuenta in resumen:
        monto = float(cuenta.disponible)
        if monto <= 0:
            continue
        pais = 'USA' if _normalize_account_currency(cuenta.moneda) == 'USD' else 'Argentina'
        distribucion[pais] = distribucion.get(pais, 0) + monto
    return distribucion


def build_distribucion_sector(
    *,
    activos_invertidos: List[Dict],
    activos_con_metadata: List[Dict],
    base: str = 'total_activos',
) -> Dict[str, float]:
    """Distribución de activos por sector según la base seleccionada."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(activos_invertidos, 'sector')
    return _build_distribution_from_items(activos_con_metadata, 'sector')


def build_distribucion_pais(
    *,
    activos_invertidos: List[Dict],
    activos_con_metadata: List[Dict],
    resumen_cash_by_country: Dict[str, float],
    base: str = 'portafolio_invertido',
) -> Dict[str, float]:
    """Distribución por país de exposición real. En base total_iol incluye cash disponible."""
    if base == 'total_iol':
        distribucion = _build_distribution_from_items(activos_con_metadata, 'pais_exposicion')
        for pais, monto in resumen_cash_by_country.items():
            distribucion[pais] = distribucion.get(pais, 0) + monto
        return distribucion
    return _build_distribution_from_items(activos_invertidos, 'pais_exposicion')


def build_distribucion_tipo_patrimonial(
    *,
    activos_invertidos: List[Dict],
    activos_con_metadata: List[Dict],
    base: str = 'total_activos',
) -> Dict[str, float]:
    """Distribución por tipo patrimonial según la base seleccionada."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(activos_invertidos, 'tipo_patrimonial')
    return _build_distribution_from_items(activos_con_metadata, 'tipo_patrimonial')


def build_distribucion_moneda(*, portafolio: list, resumen: list) -> Dict[str, float]:
    """Distribución por moneda económica/subyacente (exposición real). Incluye cash disponible."""
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    distribucion: Dict[str, float] = {}

    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            moneda = 'USD'
        elif activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            if parametro and parametro.tipo_patrimonial == 'Hard Assets':
                moneda = 'Hard Assets'
            else:
                moneda = 'ARS'
        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def build_distribucion_moneda_operativa(*, portafolio: list, resumen: list) -> Dict[str, float]:
    """Distribución por moneda operativa (cotización). Incluye cash disponible."""
    distribucion: Dict[str, float] = {}

    for activo in portafolio:
        if activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            moneda = 'ARS'
        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def build_concentracion_from_distribucion(distribucion: Dict[str, float]) -> Dict[str, float]:
    """Convierte una distribución de montos a concentración en porcentajes. Retorna {} si total es 0."""
    total = sum(distribucion.values())
    if total == 0:
        return {}
    return {key: (valor / total * 100) for key, valor in distribucion.items()}


def build_concentracion_patrimonial(*, kpis: Dict) -> Dict[str, float]:
    """Concentración por bloque patrimonial (Liquidez, Cash Management, Invertido) en porcentajes."""
    total_iol = kpis['total_iol']
    if total_iol == 0:
        return {}
    return {
        'Liquidez': (kpis['liquidez_operativa'] / total_iol * 100),
        'Cash Management': (kpis['fci_cash_management'] / total_iol * 100),
        'Invertido': (kpis['portafolio_invertido'] / total_iol * 100),
    }


def build_concentracion_sectorial(*, portafolio_inversion: List[Dict]) -> Dict[str, float]:
    """Concentración por sector económico del portafolio de inversión (excluye liquidez)."""
    distribucion: Dict[str, float] = {}
    for item in portafolio_inversion:
        sector = item['sector']
        if sector and sector != 'N/A':
            distribucion[sector] = distribucion.get(sector, 0) + float(item['activo'].valorizado)
    total = sum(distribucion.values())
    if total == 0:
        return {}
    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}
