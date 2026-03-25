from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from apps.dashboard.portfolio_distribution import (
    _aggregate_sector_labels,
    _build_distribution_from_items,
    _is_technology_sector,
    _normalize_account_currency,
    build_concentracion_from_distribucion,
    build_concentracion_patrimonial,
    build_concentracion_sectorial,
    build_distribucion_moneda,
    build_distribucion_moneda_operativa,
    build_distribucion_pais,
    build_distribucion_sector,
    build_distribucion_tipo_patrimonial,
    build_resumen_cash_distribution_by_country,
)


# --- Helpers puros ---

def test_is_technology_sector_detecta_variantes():
    assert _is_technology_sector('Tecnologia') is True
    assert _is_technology_sector('Tecnología') is True
    assert _is_technology_sector('tecnologia de consumo') is True
    assert _is_technology_sector('Salud') is False
    assert _is_technology_sector(None) is False
    assert _is_technology_sector('') is False


def test_normalize_account_currency_mapea_variantes_conocidas():
    assert _normalize_account_currency('ARS') == 'ARS'
    assert _normalize_account_currency('peso_Argentino') == 'ARS'
    assert _normalize_account_currency('USD') == 'USD'
    assert _normalize_account_currency('dolar_Estadounidense') == 'USD'
    assert _normalize_account_currency(None) == ''
    assert _normalize_account_currency('OTRO') == 'OTRO'


def test_build_distribution_from_items_agrupa_por_campo():
    items = [
        {'activo': SimpleNamespace(valorizado=Decimal('1000')), 'sector': 'Tech'},
        {'activo': SimpleNamespace(valorizado=Decimal('500')), 'sector': 'Tech'},
        {'activo': SimpleNamespace(valorizado=Decimal('800')), 'sector': 'Salud'},
    ]
    result = _build_distribution_from_items(items, 'sector')
    assert result == {'Tech': 1500.0, 'Salud': 800.0}


def test_build_distribution_from_items_normaliza_usa():
    items = [
        {'activo': SimpleNamespace(valorizado=Decimal('1000')), 'pais_exposicion': 'Estados Unidos'},
        {'activo': SimpleNamespace(valorizado=Decimal('500')), 'pais_exposicion': 'USA'},
    ]
    result = _build_distribution_from_items(items, 'pais_exposicion')
    assert result == {'USA': 1500.0}


def test_build_distribution_from_items_sin_clasificar_cuando_campo_vacio():
    items = [
        {'activo': SimpleNamespace(valorizado=Decimal('300')), 'sector': None},
        {'activo': SimpleNamespace(valorizado=Decimal('200')), 'sector': ''},
    ]
    result = _build_distribution_from_items(items, 'sector')
    assert result == {'Sin clasificar': 500.0}


def test_build_distribution_from_items_lista_vacia():
    assert _build_distribution_from_items([], 'sector') == {}


def test_aggregate_sector_labels_agrupa_subsectores_tecnologicos():
    distribucion = {
        'Tecnologia': 1000.0,
        'Tecnologia de Consumo': 500.0,
        'Salud': 800.0,
    }
    result = _aggregate_sector_labels(distribucion)
    assert result == {'Tecnologia Total': 1500.0, 'Salud': 800.0}


def test_aggregate_sector_labels_sin_tech_no_agrupa():
    distribucion = {'Salud': 500.0, 'Energia': 300.0}
    result = _aggregate_sector_labels(distribucion)
    assert result == {'Salud': 500.0, 'Energia': 300.0}


# --- build_resumen_cash_distribution_by_country ---

def _make_cuenta(moneda, disponible):
    return SimpleNamespace(moneda=moneda, disponible=Decimal(str(disponible)))


def test_build_resumen_cash_distribution_by_country_clasifica_por_moneda():
    resumen = [
        _make_cuenta('ARS', 100000),
        _make_cuenta('USD', 500),
        _make_cuenta('dolar_Estadounidense', 200),
    ]
    result = build_resumen_cash_distribution_by_country(resumen)
    assert result['Argentina'] == 100000.0
    assert result['USA'] == 700.0


def test_build_resumen_cash_distribution_by_country_ignora_montos_cero():
    resumen = [
        _make_cuenta('ARS', 0),
        _make_cuenta('USD', 0),
    ]
    result = build_resumen_cash_distribution_by_country(resumen)
    assert result == {}


def test_build_resumen_cash_distribution_by_country_lista_vacia():
    assert build_resumen_cash_distribution_by_country([]) == {}


# --- build_distribucion_sector ---

def _make_activo_item(valorizado, sector=None, pais_exposicion=None, tipo_patrimonial=None):
    return {
        'activo': SimpleNamespace(valorizado=Decimal(str(valorizado))),
        'sector': sector,
        'pais_exposicion': pais_exposicion,
        'tipo_patrimonial': tipo_patrimonial,
    }


def test_build_distribucion_sector_base_total_activos():
    activos_invertidos = [_make_activo_item(1000, sector='Tech')]
    activos_con_metadata = [
        _make_activo_item(1000, sector='Tech'),
        _make_activo_item(500, sector='Liquidez'),
    ]
    result = build_distribucion_sector(
        activos_invertidos=activos_invertidos,
        activos_con_metadata=activos_con_metadata,
        base='total_activos',
    )
    assert result == {'Tech': 1000.0, 'Liquidez': 500.0}


def test_build_distribucion_sector_base_portafolio_invertido():
    activos_invertidos = [_make_activo_item(1000, sector='Tech')]
    activos_con_metadata = [
        _make_activo_item(1000, sector='Tech'),
        _make_activo_item(500, sector='Liquidez'),
    ]
    result = build_distribucion_sector(
        activos_invertidos=activos_invertidos,
        activos_con_metadata=activos_con_metadata,
        base='portafolio_invertido',
    )
    assert result == {'Tech': 1000.0}


# --- build_distribucion_pais ---

def test_build_distribucion_pais_base_portafolio_invertido():
    activos_invertidos = [_make_activo_item(2000, pais_exposicion='USA')]
    activos_con_metadata = []
    result = build_distribucion_pais(
        activos_invertidos=activos_invertidos,
        activos_con_metadata=activos_con_metadata,
        resumen_cash_by_country={},
        base='portafolio_invertido',
    )
    assert result == {'USA': 2000.0}


def test_build_distribucion_pais_base_total_iol_incluye_cash():
    activos_con_metadata = [_make_activo_item(2000, pais_exposicion='Argentina')]
    result = build_distribucion_pais(
        activos_invertidos=[],
        activos_con_metadata=activos_con_metadata,
        resumen_cash_by_country={'Argentina': 500.0, 'USA': 200.0},
        base='total_iol',
    )
    assert result == {'Argentina': 2500.0, 'USA': 200.0}


# --- build_distribucion_tipo_patrimonial ---

def test_build_distribucion_tipo_patrimonial_base_total_activos():
    activos_con_metadata = [
        _make_activo_item(1000, tipo_patrimonial='Equity'),
        _make_activo_item(500, tipo_patrimonial='Bond'),
    ]
    result = build_distribucion_tipo_patrimonial(
        activos_invertidos=[],
        activos_con_metadata=activos_con_metadata,
        base='total_activos',
    )
    assert result == {'Equity': 1000.0, 'Bond': 500.0}


# --- build_distribucion_moneda ---

def _make_activo(moneda, valorizado, simbolo='SYM'):
    return SimpleNamespace(moneda=moneda, valorizado=Decimal(str(valorizado)), simbolo=simbolo)


@patch('apps.dashboard.portfolio_distribution.ParametroActivo')
def test_build_distribucion_moneda_clasifica_por_exposicion_real(MockParam):
    MockParam.objects.filter.return_value = []
    portafolio = [
        _make_activo('peso_Argentino', 1000, 'BONO'),
        _make_activo('dolar_Estadounidense', 500, 'CEDEAR'),
    ]
    resumen = [_make_cuenta('ARS', 200)]
    result = build_distribucion_moneda(portafolio=portafolio, resumen=resumen)
    assert result['ARS'] == 1200.0
    assert result['USD'] == 500.0


@patch('apps.dashboard.portfolio_distribution.ParametroActivo')
def test_build_distribucion_moneda_portafolio_vacio(MockParam):
    MockParam.objects.filter.return_value = []
    result = build_distribucion_moneda(portafolio=[], resumen=[])
    assert result == {}


# --- build_distribucion_moneda_operativa ---

def test_build_distribucion_moneda_operativa_clasifica_por_moneda_cotizacion():
    portafolio = [
        _make_activo('peso_Argentino', 1000),
        _make_activo('dolar_Estadounidense', 300),
        _make_activo('OTRO', 200),  # Default a ARS
    ]
    resumen = [_make_cuenta('USD', 100)]
    result = build_distribucion_moneda_operativa(portafolio=portafolio, resumen=resumen)
    assert result['ARS'] == 1200.0
    assert result['USD'] == 400.0


# --- build_concentracion_from_distribucion ---

def test_build_concentracion_from_distribucion_calcula_porcentajes():
    result = build_concentracion_from_distribucion({'A': 300.0, 'B': 700.0})
    assert abs(result['A'] - 30.0) < 0.01
    assert abs(result['B'] - 70.0) < 0.01


def test_build_concentracion_from_distribucion_retorna_vacio_si_total_cero():
    assert build_concentracion_from_distribucion({'A': 0.0}) == {}
    assert build_concentracion_from_distribucion({}) == {}


# --- build_concentracion_patrimonial ---

def test_build_concentracion_patrimonial_calcula_bloques():
    kpis = {
        'total_iol': 1000000,
        'liquidez_operativa': 200000,
        'fci_cash_management': 150000,
        'portafolio_invertido': 650000,
    }
    result = build_concentracion_patrimonial(kpis=kpis)
    assert abs(result['Liquidez'] - 20.0) < 0.01
    assert abs(result['Cash Management'] - 15.0) < 0.01
    assert abs(result['Invertido'] - 65.0) < 0.01


def test_build_concentracion_patrimonial_retorna_vacio_si_total_iol_cero():
    kpis = {'total_iol': 0, 'liquidez_operativa': 0, 'fci_cash_management': 0, 'portafolio_invertido': 0}
    assert build_concentracion_patrimonial(kpis=kpis) == {}


# --- build_concentracion_sectorial ---

def test_build_concentracion_sectorial_excluye_na():
    portafolio_inversion = [
        {'activo': SimpleNamespace(valorizado=Decimal('600')), 'sector': 'Tech'},
        {'activo': SimpleNamespace(valorizado=Decimal('400')), 'sector': 'Salud'},
        {'activo': SimpleNamespace(valorizado=Decimal('100')), 'sector': 'N/A'},
        {'activo': SimpleNamespace(valorizado=Decimal('100')), 'sector': None},
    ]
    result = build_concentracion_sectorial(portafolio_inversion=portafolio_inversion)
    assert abs(result['Tech'] - 60.0) < 0.01
    assert abs(result['Salud'] - 40.0) < 0.01
    assert 'N/A' not in result
    assert 'Sin clasificar' not in result


def test_build_concentracion_sectorial_retorna_vacio_si_sin_inversion():
    assert build_concentracion_sectorial(portafolio_inversion=[]) == {}
    result = build_concentracion_sectorial(portafolio_inversion=[
        {'activo': SimpleNamespace(valorizado=Decimal('100')), 'sector': 'N/A'},
    ])
    assert result == {}
