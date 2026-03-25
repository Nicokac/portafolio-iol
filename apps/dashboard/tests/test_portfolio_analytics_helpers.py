import pytest
from decimal import Decimal
from types import SimpleNamespace

from apps.dashboard.portfolio_analytics import _process_operaciones


def _make_op(tipo, monto_operado, numero='1', simbolo='SYM', estado='Terminada',
             fecha_operada=None, fecha_orden=None, plazo='', moneda='ARS'):
    return SimpleNamespace(
        numero=numero,
        simbolo=simbolo,
        tipo=tipo,
        estado=estado,
        estado_actual=estado,
        monto_operado=Decimal(str(monto_operado)),
        cantidadOperaciones=None,
        precio=None,
        fecha_operada=fecha_operada,
        fecha_orden=fecha_orden,
        plazo=plazo,
        moneda=moneda,
    )


OBJETIVO = Decimal('100000')


# --- clasificacion y acumulacion ---

def test_process_operaciones_lista_vacia():
    result = _process_operaciones([], OBJETIVO)
    assert result['compras_mes'] == Decimal('0')
    assert result['ventas_mes'] == Decimal('0')
    assert result['operaciones_ejecutadas_count'] == 0
    assert result['recent_operations'] == []
    assert result['aporte_mensual_ejecutado'] == Decimal('0')
    assert result['aporte_pendiente'] == OBJETIVO


def test_process_operaciones_clasifica_compra():
    ops = [_make_op('Compra', 80000)]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['compras_mes'] == Decimal('80000')
    assert result['compras_count'] == 1
    assert result['ventas_mes'] == Decimal('0')
    assert result['ventas_count'] == 0


def test_process_operaciones_clasifica_venta():
    ops = [_make_op('Venta', 30000)]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['ventas_mes'] == Decimal('30000')
    assert result['ventas_count'] == 1


def test_process_operaciones_clasifica_dividendos():
    ops = [_make_op('Pago de Dividendos', '0.50')]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['dividendos_mes'] == Decimal('0.50')
    assert result['dividendos_count'] == 1


def test_process_operaciones_clasifica_suscripcion_fci():
    ops = [_make_op('Suscripcion FCI', '9000')]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['suscripciones_fci_mes'] == Decimal('9000')
    assert result['suscripciones_fci_count'] == 1


def test_process_operaciones_tipo_desconocido_no_suma_a_ninguna_categoria():
    ops = [_make_op('Tipo raro desconocido', 5000)]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['compras_mes'] == Decimal('0')
    assert result['ventas_mes'] == Decimal('0')
    assert result['operaciones_ejecutadas_count'] == 1


# --- aporte y pendiente ---

def test_process_operaciones_aporte_ejecutado_es_compras_menos_ventas():
    ops = [_make_op('Compra', 80000, numero='1'), _make_op('Venta', 20000, numero='2')]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['aporte_mensual_ejecutado'] == Decimal('60000')
    assert result['aporte_pendiente'] == Decimal('40000')


def test_process_operaciones_aporte_pendiente_no_negativo():
    ops = [_make_op('Compra', 150000)]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['aporte_pendiente'] == Decimal('0')


# --- recent_operations ---

def test_process_operaciones_recent_operations_capped_a_5():
    ops = [_make_op('Compra', 1000, numero=str(i)) for i in range(10)]
    result = _process_operaciones(ops, OBJETIVO)
    assert len(result['recent_operations']) == 5


def test_process_operaciones_recent_operation_tiene_campos_esperados():
    ops = [_make_op('Compra', 50000, numero='42', simbolo='AAPL', plazo='a24horas', moneda='USD')]
    result = _process_operaciones(ops, OBJETIVO)
    op = result['recent_operations'][0]
    assert op['numero'] == '42'
    assert op['simbolo'] == 'AAPL'
    assert op['tipo'] == 'Compra'
    assert op['tipo_key'] == 'buy'
    assert op['monto'] == Decimal('50000')
    assert op['plazo'] == 'a24horas'
    assert op['moneda'] == 'USD'
    assert op['fecha_label'] == ''  # fecha_operada=None, fecha_orden=None


def test_process_operaciones_multiples_compras_acumulan():
    ops = [
        _make_op('Compra', 30000, numero='1'),
        _make_op('Compra', 50000, numero='2'),
        _make_op('Compra', 20000, numero='3'),
    ]
    result = _process_operaciones(ops, OBJETIVO)
    assert result['compras_mes'] == Decimal('100000')
    assert result['compras_count'] == 3
    assert result['aporte_pendiente'] == Decimal('0')
