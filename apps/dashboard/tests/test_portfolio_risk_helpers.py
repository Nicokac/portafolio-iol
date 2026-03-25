from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apps.dashboard.portfolio_risk import (
    _compute_portfolio_exposures,
    build_riesgo_portafolio,
    build_riesgo_portafolio_detallado,
)


def _make_activo(simbolo, valorizado):
    return SimpleNamespace(simbolo=simbolo, valorizado=Decimal(str(valorizado)))


def _make_param(simbolo, pais='Argentina', sector='', tipo_patrimonial='Equity', bloque='Growth'):
    return SimpleNamespace(
        simbolo=simbolo,
        pais_exposicion=pais,
        sector=sector,
        tipo_patrimonial=tipo_patrimonial,
        bloque_estrategico=bloque,
    )


# --- _compute_portfolio_exposures ---

def test_compute_exposures_portafolio_vacio():
    result = _compute_portfolio_exposures([], {}, 0)
    assert result['pct_usa'] == 0
    assert result['pct_argentina'] == 0
    assert result['pct_tech'] == 0


def test_compute_exposures_clasifica_por_pais():
    portafolio = [_make_activo('AAPL', 600), _make_activo('YPF', 400)]
    parametros = {
        'AAPL': _make_param('AAPL', pais='USA'),
        'YPF': _make_param('YPF', pais='Argentina'),
    }
    result = _compute_portfolio_exposures(portafolio, parametros, 1000)
    assert abs(result['pct_usa'] - 60.0) < 0.01
    assert abs(result['pct_argentina'] - 40.0) < 0.01


def test_compute_exposures_acepta_estados_unidos_como_usa():
    portafolio = [_make_activo('MSFT', 1000)]
    parametros = {'MSFT': _make_param('MSFT', pais='Estados Unidos')}
    result = _compute_portfolio_exposures(portafolio, parametros, 1000)
    assert abs(result['pct_usa'] - 100.0) < 0.01


def test_compute_exposures_tecnologia_agrega_subsectores():
    portafolio = [
        _make_activo('AAPL', 400),
        _make_activo('MELI', 300),
        _make_activo('KO', 300),
    ]
    parametros = {
        'AAPL': _make_param('AAPL', sector='Tecnologia'),
        'MELI': _make_param('MELI', sector='Tecnologia / E-commerce'),
        'KO': _make_param('KO', sector='Consumo'),
    }
    result = _compute_portfolio_exposures(portafolio, parametros, 1000)
    assert abs(result['pct_tech'] - 70.0) < 0.01


def test_compute_exposures_renta_fija_ar_solo_bonos_argentina():
    portafolio = [_make_activo('AL30', 500), _make_activo('LQD', 500)]
    parametros = {
        'AL30': _make_param('AL30', pais='Argentina', tipo_patrimonial='Bond'),
        'LQD': _make_param('LQD', pais='USA', tipo_patrimonial='Bond'),
    }
    result = _compute_portfolio_exposures(portafolio, parametros, 1000)
    assert abs(result['pct_renta_fija_ar'] - 50.0) < 0.01


def test_compute_exposures_activo_sin_parametro_no_cuenta():
    portafolio = [_make_activo('UNKNOWN', 1000)]
    result = _compute_portfolio_exposures(portafolio, {}, 1000)
    assert result['pct_usa'] == 0
    assert result['pct_argentina'] == 0
    assert result['pct_tech'] == 0


def test_compute_exposures_bloque_defensivo_y_growth():
    portafolio = [_make_activo('DEF', 300), _make_activo('GRW', 700)]
    parametros = {
        'DEF': _make_param('DEF', bloque='Defensivo'),
        'GRW': _make_param('GRW', bloque='Growth'),
    }
    result = _compute_portfolio_exposures(portafolio, parametros, 1000)
    assert abs(result['pct_defensivo'] - 30.0) < 0.01
    assert abs(result['pct_growth'] - 70.0) < 0.01


# --- build_riesgo_portafolio_detallado ---

@patch('apps.dashboard.portfolio_risk.ParametroActivo')
def test_build_riesgo_detallado_estructura_completa(MockParam):
    MockParam.objects.filter.return_value = []
    result = build_riesgo_portafolio_detallado(
        portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
    )
    for key in ('pct_usa', 'pct_argentina', 'pct_tech', 'pct_bonos_soberanos',
                'pct_renta_fija_ar', 'pct_defensivo', 'pct_growth', 'pct_liquidez', 'methodology'):
        assert key in result


@patch('apps.dashboard.portfolio_risk.ParametroActivo')
def test_build_riesgo_detallado_calcula_pct_liquidez(MockParam):
    MockParam.objects.filter.return_value = []
    result = build_riesgo_portafolio_detallado(
        portafolio=[], total_portafolio=0, liquidez_operativa=200000, total_iol=1000000,
    )
    assert abs(result['pct_liquidez'] - 20.0) < 0.01


@patch('apps.dashboard.portfolio_risk.ParametroActivo')
def test_build_riesgo_detallado_pct_liquidez_cero_cuando_total_iol_cero(MockParam):
    MockParam.objects.filter.return_value = []
    result = build_riesgo_portafolio_detallado(
        portafolio=[], total_portafolio=0, liquidez_operativa=500, total_iol=0,
    )
    assert result['pct_liquidez'] == 0.0


@patch('apps.dashboard.portfolio_risk.ParametroActivo')
def test_build_riesgo_detallado_alias_bonos_soberanos(MockParam):
    MockParam.objects.filter.return_value = []
    result = build_riesgo_portafolio_detallado(
        portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
    )
    assert result['pct_bonos_soberanos'] == result['pct_renta_fija_ar']


# --- build_riesgo_portafolio ---

def _patch_all_services(extra=None):
    mocks = {
        'VolatilityService': MagicMock(return_value=MagicMock(
            calculate_volatility=MagicMock(return_value={'annualized_volatility': None})
        )),
        'VaRService': MagicMock(return_value=MagicMock(
            calculate_var_set=MagicMock(return_value={})
        )),
        'CVaRService': MagicMock(return_value=MagicMock(
            calculate_cvar_set=MagicMock(return_value={})
        )),
        'StressTestService': MagicMock(return_value=MagicMock(
            run_all=MagicMock(return_value={})
        )),
        'TrackingErrorService': MagicMock(return_value=MagicMock(
            calculate=MagicMock(return_value={})
        )),
        'LiquidityService': MagicMock(return_value=MagicMock(
            analyze_portfolio_liquidity=MagicMock(return_value=None)
        )),
        'MetadataAuditService': MagicMock(return_value=MagicMock(
            run_audit=MagicMock(return_value=None)
        )),
        'ParametroActivo': MagicMock(**{'objects.filter.return_value': []}),
    }
    if extra:
        mocks.update(extra)
    return mocks


def test_build_riesgo_portafolio_status_insufficient_history():
    with patch.multiple('apps.dashboard.portfolio_risk', **_patch_all_services()):
        result = build_riesgo_portafolio(
            portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
        )
    assert result['volatilidad_estimada'] is None
    assert result['volatilidad_status'] == 'insufficient_history'


def test_build_riesgo_portafolio_status_ok_con_volatilidad():
    overrides = {'VolatilityService': MagicMock(return_value=MagicMock(
        calculate_volatility=MagicMock(return_value={'annualized_volatility': 0.18})
    ))}
    with patch.multiple('apps.dashboard.portfolio_risk', **_patch_all_services(overrides)):
        result = build_riesgo_portafolio(
            portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
        )
    assert result['volatilidad_estimada'] == 0.18
    assert result['volatilidad_status'] == 'ok'


def test_build_riesgo_portafolio_stress_worst_case():
    overrides = {'StressTestService': MagicMock(return_value=MagicMock(
        run_all=MagicMock(return_value={
            'crash_usa': {'label': 'Crash USA', 'impact_portfolio_pct': -0.15},
            'crisis_ar': {'label': 'Crisis AR', 'impact_portfolio_pct': -0.30},
        })
    ))}
    with patch.multiple('apps.dashboard.portfolio_risk', **_patch_all_services(overrides)):
        result = build_riesgo_portafolio(
            portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
        )
    assert result['stress_worst_case_label'] == 'Crisis AR'
    assert result['stress_worst_case_pct'] == -0.30


def test_build_riesgo_portafolio_liquidity_incluida():
    overrides = {'LiquidityService': MagicMock(return_value=MagicMock(
        analyze_portfolio_liquidity=MagicMock(return_value={
            'portfolio_liquidity_score': 0.85,
            'days_to_liquidate': 3,
        })
    ))}
    with patch.multiple('apps.dashboard.portfolio_risk', **_patch_all_services(overrides)):
        result = build_riesgo_portafolio(
            portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
        )
    assert result['liquidity_score'] == 0.85
    assert result['days_to_liquidate'] == 3


def test_build_riesgo_portafolio_stress_vacio_no_rompe():
    with patch.multiple('apps.dashboard.portfolio_risk', **_patch_all_services()):
        result = build_riesgo_portafolio(
            portafolio=[], total_portafolio=0, liquidez_operativa=0, total_iol=0,
        )
    assert 'stress_worst_case_label' not in result
    assert 'stress_worst_case_pct' not in result
