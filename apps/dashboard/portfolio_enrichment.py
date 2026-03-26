from decimal import Decimal
from typing import Dict, List

from apps.dashboard.portfolio_distribution import _normalize_account_currency
from apps.parametros.models import ParametroActivo


_FCI_CASH_MANAGEMENT_SIMBOLOS = frozenset(['ADBAICA', 'IOLPORA', 'PRPEDOB'])

_TIPO_TRADUCCIONES = {
    'CEDEARS': 'CEDEAR',
    'ACCIONES': 'Acción',
    'TitulosPublicos': 'Título Público',
    'FondoComundeInversion': 'FCI',
    'CAUCIONESPESOS': 'Caución',
}

_MONEDA_TRADUCCIONES = {
    'peso_Argentino': 'ARS',
    'dolar_Estadounidense': 'USD',
}


def build_portafolio_enriquecido(portafolio: list, parametros: dict) -> Dict:
    """Clasifica y enriquece el portafolio con metadata. Funcion pura dado portafolio y parametros."""
    total_portafolio = sum(activo.valorizado for activo in portafolio)

    liquidez: List[Dict] = []
    fci_cash_management: List[Dict] = []
    inversion: List[Dict] = []

    for activo in portafolio:
        param = parametros.get(activo.simbolo)
        tipo_traducido = _TIPO_TRADUCCIONES.get(activo.tipo, activo.tipo)
        moneda_traducida = _MONEDA_TRADUCCIONES.get(activo.moneda, activo.moneda)
        peso_porcentual = (
            float(activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0.0
        )

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

        simbolo_upper = activo.simbolo.upper()
        if activo.tipo == 'CAUCIONESPESOS' or 'CAUCION' in simbolo_upper:
            liquidez.append(item)
        elif simbolo_upper in _FCI_CASH_MANAGEMENT_SIMBOLOS:
            fci_cash_management.append(item)
        else:
            inversion.append(item)

    inversion.sort(key=lambda x: x['activo'].valorizado, reverse=True)
    fci_cash_management.sort(key=lambda x: x['activo'].valorizado, reverse=True)

    return {
        'liquidez': liquidez,
        'fci_cash_management': fci_cash_management,
        'inversion': inversion,
        'total_portafolio': total_portafolio,
    }


def extract_resumen_cash_components(resumen: list) -> Dict[str, Decimal]:
    """Desglosa el cash disponible e inmediato por moneda a partir del resumen de cuentas."""
    cash_immediate_ars = Decimal('0')
    cash_immediate_usd = Decimal('0')
    cash_pending_ars = Decimal('0')
    cash_pending_usd = Decimal('0')
    fallback_cash_ars = Decimal('0')
    fallback_cash_usd = Decimal('0')
    total_broker_en_pesos = None

    for cuenta in resumen:
        currency_code = _normalize_account_currency(cuenta.moneda)
        disponible = Decimal(cuenta.disponible or 0)
        if currency_code == 'ARS':
            fallback_cash_ars += disponible
        elif currency_code == 'USD':
            fallback_cash_usd += disponible

        if total_broker_en_pesos is None and getattr(cuenta, 'total_en_pesos', None) is not None:
            total_broker_en_pesos = Decimal(cuenta.total_en_pesos)

        saldos_detalle = getattr(cuenta, 'saldos_detalle', None) or []
        if not saldos_detalle:
            continue

        immediate_found = False
        for saldo_row in saldos_detalle:
            liquidacion = str(saldo_row.get('liquidacion') or '').strip()
            disponible_row = Decimal(str(saldo_row.get('disponible', 0) or 0))
            if liquidacion == 'inmediato':
                immediate_found = True
                if currency_code == 'ARS':
                    cash_immediate_ars += disponible_row
                elif currency_code == 'USD':
                    cash_immediate_usd += disponible_row
            else:
                if currency_code == 'ARS':
                    cash_pending_ars += disponible_row
                elif currency_code == 'USD':
                    cash_pending_usd += disponible_row

        if not immediate_found:
            if currency_code == 'ARS':
                cash_immediate_ars += disponible
            elif currency_code == 'USD':
                cash_immediate_usd += disponible

    if cash_immediate_ars == 0 and fallback_cash_ars > 0:
        cash_immediate_ars = fallback_cash_ars
    if cash_immediate_usd == 0 and fallback_cash_usd > 0:
        cash_immediate_usd = fallback_cash_usd

    return {
        'cash_immediate_ars': cash_immediate_ars,
        'cash_immediate_usd': cash_immediate_usd,
        'cash_pending_ars': cash_pending_ars,
        'cash_pending_usd': cash_pending_usd,
        'cash_disponible_ars': fallback_cash_ars,
        'cash_disponible_usd': fallback_cash_usd,
        'total_broker_en_pesos': total_broker_en_pesos or Decimal('0'),
    }


def build_dashboard_kpis(portafolio: list, portafolio_clasificado: Dict, resumen: list) -> Dict:
    """Calcula KPIs del dashboard dado el portafolio ya clasificado y el resumen de cuentas."""
    cash_components = extract_resumen_cash_components(resumen)
    cash_ars = cash_components['cash_immediate_ars']
    cash_usd = cash_components['cash_immediate_usd']
    cash_a_liquidar_ars = cash_components['cash_pending_ars']
    cash_a_liquidar_usd = cash_components['cash_pending_usd']
    total_broker_en_pesos = cash_components['total_broker_en_pesos']

    total_activos_valorizados = sum(activo.valorizado for activo in portafolio)
    total_iol_calculado = total_activos_valorizados + cash_ars + cash_usd
    total_iol = total_broker_en_pesos if total_broker_en_pesos > 0 else total_iol_calculado

    caucion_valor = sum(
        item['activo'].valorizado
        for item in portafolio_clasificado['liquidez']
        if item['tipo_traducido'] == 'Caución'
    )
    liquidez_operativa = caucion_valor + cash_ars + cash_usd
    fci_cash_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['fci_cash_management'])
    portafolio_invertido = sum(item['activo'].valorizado for item in portafolio_clasificado['inversion'])

    cash_disponible_broker = cash_ars + cash_usd
    caucion_colocada = caucion_valor
    liquidez_estrategica = fci_cash_valor
    liquidez_total_combinada = cash_disponible_broker + caucion_colocada + liquidez_estrategica
    total_patrimonio_modelado = (
        portafolio_invertido + liquidez_estrategica + cash_disponible_broker + caucion_colocada
    )

    titulos_valorizados = sum(
        activo.valorizado for activo in portafolio
        if activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in activo.simbolo.upper()
    )
    capital_invertido_real = total_iol - liquidez_operativa - fci_cash_valor

    inversion = portafolio_clasificado['inversion']
    rendimiento_total_dinero = sum(item['activo'].ganancia_dinero for item in inversion)
    costo_estimado_invertido = portafolio_invertido - rendimiento_total_dinero
    rendimiento_total_porcentaje = (
        rendimiento_total_dinero / costo_estimado_invertido * 100
    ) if costo_estimado_invertido > 0 else 0

    portafolio_ordenado = sorted(
        (item['activo'] for item in inversion),
        key=lambda activo: activo.valorizado,
        reverse=True,
    )
    top_5_valor = sum(activo.valorizado for activo in portafolio_ordenado[:5])
    top_5_concentracion = (top_5_valor / portafolio_invertido * 100) if portafolio_invertido else 0

    top_10_valor = sum(activo.valorizado for activo in portafolio_ordenado[:10])
    top_10_concentracion = (top_10_valor / portafolio_invertido * 100) if portafolio_invertido else 0

    pct_fci_cash_management = (fci_cash_valor / total_iol * 100) if total_iol else 0
    pct_portafolio_invertido = (portafolio_invertido / total_iol * 100) if total_iol else 0
    pct_liquidez_total = ((liquidez_operativa + fci_cash_valor) / total_iol * 100) if total_iol else 0
    pct_liquidez_operativa = (cash_disponible_broker / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
    pct_caucion_colocada = (caucion_colocada / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
    pct_liquidez_estrategica = (liquidez_estrategica / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
    pct_liquidez_total_combinada = (liquidez_total_combinada / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
    pct_portafolio_invertido_modelado = (portafolio_invertido / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0

    return {
        'total_iol': total_iol,
        'total_iol_legacy_calculated': total_iol_calculado,
        'total_broker_en_pesos': total_broker_en_pesos,
        'total_patrimonio_modelado': total_patrimonio_modelado,
        'titulos_valorizados': titulos_valorizados,
        'cash_ars': cash_ars,
        'cash_usd': cash_usd,
        'cash_a_liquidar_ars': cash_a_liquidar_ars,
        'cash_a_liquidar_usd': cash_a_liquidar_usd,
        'cash_a_liquidar_broker': cash_a_liquidar_ars + cash_a_liquidar_usd,
        'cash_disponible_broker': cash_disponible_broker,
        'caucion_valor': caucion_valor,
        'caucion_colocada': caucion_colocada,
        'liquidez_operativa': liquidez_operativa,
        'liquidez_estrategica': liquidez_estrategica,
        'liquidez_total_combinada': liquidez_total_combinada,
        'fci_cash_management': fci_cash_valor,
        'portafolio_invertido': portafolio_invertido,
        'capital_invertido_real': capital_invertido_real,
        'rendimiento_total_porcentaje': rendimiento_total_porcentaje,
        'rendimiento_total_dinero': rendimiento_total_dinero,
        'rendimiento_total_cost_basis': costo_estimado_invertido,
        'performance_families': {
            'current_dashboard_family': 'accumulated_on_invested_cost',
            'current_dashboard_label': 'Acumulado sobre costo invertido',
            'current_dashboard_fields': [
                'rendimiento_total_porcentaje',
                'rendimiento_total_dinero',
            ],
            'comparison_family': 'temporal_return_on_total_portfolio',
            'comparison_label': 'Retorno temporal sobre patrimonio',
            'comparison_fields': [
                'total_period_return',
                'twr_total_return',
                'daily_return',
                'weekly_return',
                'monthly_return',
            ],
            'comparison_view': 'performance',
            'comparison_view_label': 'Centro de Performance',
        },
        'top_5_concentracion': top_5_concentracion,
        'top_10_concentracion': top_10_concentracion,
        'pct_liquidez_operativa': pct_liquidez_operativa,
        'pct_caucion_colocada': pct_caucion_colocada,
        'pct_liquidez_estrategica': pct_liquidez_estrategica,
        'pct_liquidez_total_combinada': pct_liquidez_total_combinada,
        'pct_fci_cash_management': pct_fci_cash_management,
        'pct_portafolio_invertido': pct_portafolio_invertido,
        'pct_portafolio_invertido_modelado': pct_portafolio_invertido_modelado,
        'pct_liquidez_total': pct_liquidez_total,
        'methodology': {
            'top_5_concentracion': 'sum(top_5 valorizado del portafolio invertido) / portafolio invertido',
            'top_10_concentracion': 'sum(top_10 valorizado del portafolio invertido) / portafolio invertido',
            'top_positions_basis': 'portafolio_invertido',
            'rendimiento_total_porcentaje': 'ganancia acumulada / costo estimado del portafolio invertido',
            'rendimiento_total_basis': 'portafolio_invertido_costo_estimado',
            'performance_family_current': 'acumulado sobre costo estimado del portafolio invertido',
            'performance_family_comparison': 'retorno temporal sobre patrimonio total usando PortfolioSnapshot.total_iol',
            'pct_liquidez_total': '(liquidez operativa + cash management) / total iol',
            'pct_portafolio_invertido': 'portafolio invertido / total iol',
            'total_iol': 'si existe total_en_pesos desde estadocuenta se usa como ancla broker; si no, fallback a activos + cash inmediato',
            'total_patrimonio_modelado': 'portafolio invertido + cash disponible broker + caucion colocada + fci cash management',
            'pct_liquidez_operativa': 'cash disponible broker / total patrimonio modelado',
            'pct_caucion_colocada': 'caucion colocada / total patrimonio modelado',
            'pct_liquidez_estrategica': 'fci cash management / total patrimonio modelado',
            'pct_liquidez_total_combinada': '(cash disponible broker + caucion colocada + fci cash management) / total patrimonio modelado',
            'pct_portafolio_invertido_modelado': 'portafolio invertido / total patrimonio modelado',
        },
    }


def build_liquidity_contract_summary(kpis: Dict) -> Dict:
    """Normaliza el contrato de liquidez a partir de kpis calculados."""
    total = float(kpis.get('total_patrimonio_modelado') or kpis.get('total_iol') or 0.0)
    cash_operativo = float(kpis.get('cash_disponible_broker') or 0.0)
    caucion_tactica = float(kpis.get('caucion_colocada') or 0.0)
    fci_estrategico = float(
        kpis.get('liquidez_estrategica')
        if kpis.get('liquidez_estrategica') is not None
        else (kpis.get('fci_cash_management') or 0.0)
    )

    if (
        'cash_disponible_broker' not in kpis
        and 'caucion_colocada' not in kpis
        and 'liquidez_operativa' in kpis
    ):
        cash_operativo = float(kpis.get('liquidez_operativa') or 0.0)
        caucion_tactica = 0.0

    liquidez_desplegable_total = cash_operativo + caucion_tactica + fci_estrategico

    return {
        'cash_operativo': cash_operativo,
        'caucion_tactica': caucion_tactica,
        'fci_estrategico': fci_estrategico,
        'liquidez_desplegable_total': liquidez_desplegable_total,
        'pct_cash_operativo': (cash_operativo / total * 100) if total > 0 else 0.0,
        'pct_caucion_tactica': (caucion_tactica / total * 100) if total > 0 else 0.0,
        'pct_fci_estrategico': (fci_estrategico / total * 100) if total > 0 else 0.0,
        'pct_liquidez_desplegable_total': (liquidez_desplegable_total / total * 100) if total > 0 else 0.0,
        'total_base': total,
        'methodology': {
            'cash_operativo': 'cash disponible broker',
            'caucion_tactica': 'caucion colocada',
            'fci_estrategico': 'fci cash management',
            'liquidez_desplegable_total': 'cash operativo + caucion tactica + fci estrategico',
            'total_base': 'total patrimonio modelado',
        },
    }


def build_portfolio_scope_summary(kpis: Dict, cash_components: Dict) -> Dict:
    """Explicita el universo broker vs capital invertido para Planeacion."""
    cash_ars = float(cash_components['cash_immediate_ars'])
    cash_usd = float(cash_components['cash_immediate_usd'])
    cash_a_liquidar_ars = float(cash_components['cash_pending_ars'])
    cash_a_liquidar_usd = float(cash_components['cash_pending_usd'])
    portfolio_total_broker = float(kpis.get('total_broker_en_pesos') or kpis.get('total_iol') or 0.0)
    invested_portfolio = float(kpis.get('portafolio_invertido') or 0.0)
    caucion_colocada = float(kpis.get('caucion_colocada') or 0.0)
    cash_management_fci = float(kpis.get('fci_cash_management') or 0.0)
    cash_available_broker = cash_ars

    cash_ratio_total = (cash_available_broker / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    caucion_ratio_total = (caucion_colocada / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    invested_ratio_total = (invested_portfolio / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    fci_ratio_total = (cash_management_fci / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0

    return {
        'portfolio_total_broker': portfolio_total_broker,
        'invested_portfolio': invested_portfolio,
        'caucion_colocada': caucion_colocada,
        'cash_management_fci': cash_management_fci,
        'cash_available_broker': cash_available_broker,
        'cash_available_broker_ars': cash_ars,
        'cash_available_broker_usd': cash_usd,
        'cash_settling_broker': cash_a_liquidar_ars,
        'cash_settling_broker_ars': cash_a_liquidar_ars,
        'cash_settling_broker_usd': cash_a_liquidar_usd,
        'cash_ratio_total': cash_ratio_total,
        'caucion_ratio_total': caucion_ratio_total,
        'invested_ratio_total': invested_ratio_total,
        'fci_ratio_total': fci_ratio_total,
    }
