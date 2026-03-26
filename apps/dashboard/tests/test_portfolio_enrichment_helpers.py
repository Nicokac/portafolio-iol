from decimal import Decimal
from types import SimpleNamespace

from apps.dashboard.portfolio_enrichment import (
    build_dashboard_kpis,
    build_liquidity_contract_summary,
    build_portfolio_scope_summary,
    build_portafolio_enriquecido,
    extract_resumen_cash_components,
)


# --- extract_resumen_cash_components ---

def _make_cuenta(moneda, disponible, saldos_detalle=None, total_en_pesos=None):
    return SimpleNamespace(
        moneda=moneda,
        disponible=disponible,
        saldos_detalle=saldos_detalle,
        total_en_pesos=total_en_pesos,
    )


def test_extract_resumen_cash_components_vacio():
    result = extract_resumen_cash_components([])
    assert result['cash_immediate_ars'] == Decimal('0')
    assert result['cash_immediate_usd'] == Decimal('0')
    assert result['cash_pending_ars'] == Decimal('0')
    assert result['cash_pending_usd'] == Decimal('0')
    assert result['total_broker_en_pesos'] == Decimal('0')


def test_extract_resumen_cash_components_fallback_cuando_sin_saldos_detalle():
    resumen = [
        _make_cuenta('ARS', 50000),
        _make_cuenta('dolar_Estadounidense', 200),
    ]
    result = extract_resumen_cash_components(resumen)
    assert result['cash_immediate_ars'] == Decimal('50000')
    assert result['cash_immediate_usd'] == Decimal('200')


def test_extract_resumen_cash_components_saldos_detalle_inmediato_y_pendiente():
    saldos = [
        {'liquidacion': 'inmediato', 'disponible': 30000},
        {'liquidacion': 'a24horas', 'disponible': 20000},
    ]
    resumen = [_make_cuenta('ARS', 50000, saldos_detalle=saldos)]
    result = extract_resumen_cash_components(resumen)
    assert result['cash_immediate_ars'] == Decimal('30000')
    assert result['cash_pending_ars'] == Decimal('20000')


def test_extract_resumen_cash_components_total_broker_en_pesos():
    resumen = [_make_cuenta('ARS', 0, total_en_pesos=1000000)]
    result = extract_resumen_cash_components(resumen)
    assert result['total_broker_en_pesos'] == Decimal('1000000')


def test_extract_resumen_cash_components_total_broker_solo_primer_cuenta():
    resumen = [
        _make_cuenta('ARS', 0, total_en_pesos=800000),
        _make_cuenta('USD', 0, total_en_pesos=200000),
    ]
    result = extract_resumen_cash_components(resumen)
    assert result['total_broker_en_pesos'] == Decimal('800000')


# --- build_portafolio_enriquecido ---

def _make_activo(simbolo, valorizado, tipo='CEDEARS', moneda='peso_Argentino', ganancia_dinero=0):
    return SimpleNamespace(
        simbolo=simbolo,
        valorizado=Decimal(str(valorizado)),
        tipo=tipo,
        moneda=moneda,
        ganancia_dinero=Decimal(str(ganancia_dinero)),
    )


def _make_param(simbolo, sector='Tech', bloque='Growth', pais='USA', tipo_patrimonial='Equity', obs=''):
    return SimpleNamespace(
        simbolo=simbolo,
        sector=sector,
        bloque_estrategico=bloque,
        pais_exposicion=pais,
        tipo_patrimonial=tipo_patrimonial,
        observaciones=obs,
    )


def test_build_portafolio_enriquecido_portafolio_vacio():
    result = build_portafolio_enriquecido([], {})
    assert result['liquidez'] == []
    assert result['fci_cash_management'] == []
    assert result['inversion'] == []
    assert result['total_portafolio'] == 0


def test_build_portafolio_enriquecido_clasifica_caucion_como_liquidez():
    portafolio = [_make_activo('CAUC01', 50000, tipo='CAUCIONESPESOS')]
    result = build_portafolio_enriquecido(portafolio, {})
    assert len(result['liquidez']) == 1
    assert result['liquidez'][0]['tipo_traducido'] == 'Caución'
    assert result['inversion'] == []


def test_build_portafolio_enriquecido_clasifica_fci_cash_management():
    portafolio = [_make_activo('ADBAICA', 30000, tipo='FondoComundeInversion')]
    result = build_portafolio_enriquecido(portafolio, {})
    assert len(result['fci_cash_management']) == 1
    assert result['inversion'] == []


def test_build_portafolio_enriquecido_clasifica_otros_como_inversion():
    portafolio = [
        _make_activo('AAPL', 100000, tipo='CEDEARS'),
        _make_activo('AL30', 50000, tipo='TitulosPublicos'),
        _make_activo('SCHRINS', 20000, tipo='FondoComundeInversion'),
    ]
    result = build_portafolio_enriquecido(portafolio, {})
    assert len(result['inversion']) == 3
    assert result['liquidez'] == []
    assert result['fci_cash_management'] == []


def test_build_portafolio_enriquecido_enriquece_con_parametros():
    portafolio = [_make_activo('AAPL', 100000)]
    parametros = {'AAPL': _make_param('AAPL', sector='Tecnologia', pais='USA')}
    result = build_portafolio_enriquecido(portafolio, parametros)
    item = result['inversion'][0]
    assert item['sector'] == 'Tecnologia'
    assert item['pais_exposicion'] == 'USA'


def test_build_portafolio_enriquecido_sin_parametro_usa_na():
    portafolio = [_make_activo('UNKNOWN', 10000)]
    result = build_portafolio_enriquecido(portafolio, {})
    item = result['inversion'][0]
    assert item['sector'] == 'N/A'
    assert item['pais_exposicion'] == 'N/A'


def test_build_portafolio_enriquecido_peso_porcentual():
    portafolio = [
        _make_activo('A', 600000),
        _make_activo('B', 400000),
    ]
    result = build_portafolio_enriquecido(portafolio, {})
    pesos = {item['activo'].simbolo: item['peso_porcentual'] for item in result['inversion']}
    assert abs(pesos['A'] - 60.0) < 0.01
    assert abs(pesos['B'] - 40.0) < 0.01


def test_build_portafolio_enriquecido_inversion_ordenada_descendente():
    portafolio = [
        _make_activo('SMALL', 10000),
        _make_activo('BIG', 500000),
        _make_activo('MED', 100000),
    ]
    result = build_portafolio_enriquecido(portafolio, {})
    valores = [item['activo'].valorizado for item in result['inversion']]
    assert valores == sorted(valores, reverse=True)


# --- build_dashboard_kpis ---

def _make_portafolio_clasificado(liquidez=None, fci=None, inversion=None):
    return {
        'liquidez': liquidez or [],
        'fci_cash_management': fci or [],
        'inversion': inversion or [],
    }


def _make_item(valorizado, tipo_traducido='CEDEAR', ganancia_dinero=0, simbolo='SYM'):
    return {
        'activo': SimpleNamespace(
            valorizado=Decimal(str(valorizado)),
            tipo='CEDEARS',
            simbolo=simbolo,
            ganancia_dinero=Decimal(str(ganancia_dinero)),
        ),
        'tipo_traducido': tipo_traducido,
    }


def test_build_dashboard_kpis_portafolio_vacio_sin_resumen():
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(), [])
    assert kpis['total_iol'] == Decimal('0')
    assert kpis['portafolio_invertido'] == Decimal('0')
    assert kpis['liquidez_operativa'] == Decimal('0')
    assert 'methodology' in kpis


def test_build_dashboard_kpis_total_iol_usa_total_broker_en_pesos():
    resumen = [_make_cuenta('ARS', 0, total_en_pesos=1000000)]
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(), resumen)
    assert kpis['total_iol'] == Decimal('1000000')
    assert kpis['total_broker_en_pesos'] == Decimal('1000000')


def test_build_dashboard_kpis_total_iol_fallback_cuando_sin_total_broker():
    portafolio = [_make_activo('AAPL', 700000)]
    resumen = [_make_cuenta('ARS', 100000)]
    kpis = build_dashboard_kpis(portafolio, _make_portafolio_clasificado(), resumen)
    assert kpis['total_iol'] == Decimal('800000')


def test_build_dashboard_kpis_portafolio_invertido_suma_inversion():
    inversion = [_make_item(300000), _make_item(200000)]
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(inversion=inversion), [])
    assert kpis['portafolio_invertido'] == Decimal('500000')


def test_build_dashboard_kpis_caucion_clasifica_como_liquidez():
    liquidez = [_make_item(80000, tipo_traducido='Caución')]
    resumen = [_make_cuenta('ARS', 20000)]
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(liquidez=liquidez), resumen)
    assert kpis['caucion_colocada'] == Decimal('80000')
    assert kpis['cash_disponible_broker'] == Decimal('20000')
    assert kpis['liquidez_operativa'] == Decimal('100000')


def test_build_dashboard_kpis_rendimiento_porcentaje():
    # portafolio_invertido=100000, ganancia=20000 → costo=80000 → rendimiento=25%
    inversion = [_make_item(100000, ganancia_dinero=20000)]
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(inversion=inversion), [])
    assert abs(float(kpis['rendimiento_total_porcentaje']) - 25.0) < 0.01


def test_build_dashboard_kpis_includes_performance_family_metadata():
    inversion = [_make_item(100000, ganancia_dinero=20000)]
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(inversion=inversion), [])

    assert 'performance_families' in kpis
    assert kpis['performance_families']['current_dashboard_family'] == 'accumulated_on_invested_cost'
    assert kpis['performance_families']['comparison_family'] == 'temporal_return_on_total_portfolio'
    assert 'rendimiento_total_porcentaje' in kpis['performance_families']['current_dashboard_fields']


def test_build_dashboard_kpis_top5_concentracion():
    inversion = [_make_item(200000, simbolo=f'SYM{i}') for i in range(10)]
    kpis = build_dashboard_kpis([], _make_portafolio_clasificado(inversion=inversion), [])
    # 5 activos de 200000 c/u de 2000000 total = 50%
    assert abs(float(kpis['top_5_concentracion']) - 50.0) < 0.01


# --- build_liquidity_contract_summary ---

def test_build_liquidity_contract_summary_calcula_porcentajes():
    kpis = {
        'total_patrimonio_modelado': 1000000,
        'cash_disponible_broker': 100000,
        'caucion_colocada': 50000,
        'liquidez_estrategica': 200000,
    }
    result = build_liquidity_contract_summary(kpis)
    assert abs(result['pct_cash_operativo'] - 10.0) < 0.01
    assert abs(result['pct_caucion_tactica'] - 5.0) < 0.01
    assert abs(result['pct_fci_estrategico'] - 20.0) < 0.01
    assert abs(result['liquidez_desplegable_total'] - 350000) < 0.01


def test_build_liquidity_contract_summary_total_cero():
    kpis = {'total_patrimonio_modelado': 0, 'cash_disponible_broker': 100000, 'caucion_colocada': 0}
    result = build_liquidity_contract_summary(kpis)
    assert result['pct_cash_operativo'] == 0.0
    assert result['pct_caucion_tactica'] == 0.0


def test_build_liquidity_contract_summary_fallback_liquidez_operativa():
    kpis = {
        'total_patrimonio_modelado': 500000,
        'liquidez_operativa': 80000,
    }
    result = build_liquidity_contract_summary(kpis)
    assert result['cash_operativo'] == 80000.0
    assert result['caucion_tactica'] == 0.0


# --- build_portfolio_scope_summary ---

def test_build_portfolio_scope_summary_estructura_completa():
    kpis = {
        'total_broker_en_pesos': 1000000,
        'portafolio_invertido': 700000,
        'caucion_colocada': 50000,
        'fci_cash_management': 100000,
    }
    cash_components = {
        'cash_immediate_ars': Decimal('150000'),
        'cash_immediate_usd': Decimal('0'),
        'cash_pending_ars': Decimal('0'),
        'cash_pending_usd': Decimal('0'),
    }
    result = build_portfolio_scope_summary(kpis, cash_components)
    assert result['portfolio_total_broker'] == 1000000.0
    assert result['invested_portfolio'] == 700000.0
    assert result['cash_available_broker'] == 150000.0
    assert abs(result['invested_ratio_total'] - 0.7) < 0.001
    assert abs(result['cash_ratio_total'] - 0.15) < 0.001


def test_build_portfolio_scope_summary_total_cero_no_divide():
    kpis = {'total_broker_en_pesos': 0, 'portafolio_invertido': 0, 'caucion_colocada': 0, 'fci_cash_management': 0}
    cash_components = {
        'cash_immediate_ars': Decimal('0'),
        'cash_immediate_usd': Decimal('0'),
        'cash_pending_ars': Decimal('0'),
        'cash_pending_usd': Decimal('0'),
    }
    result = build_portfolio_scope_summary(kpis, cash_components)
    assert result['cash_ratio_total'] == 0.0
    assert result['invested_ratio_total'] == 0.0
