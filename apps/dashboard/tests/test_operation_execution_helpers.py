from decimal import Decimal
from types import SimpleNamespace

from apps.dashboard.operation_execution import (
    classify_observed_operation_cost,
    classify_operation_type,
    get_effective_operation_amount,
)


def test_classify_operation_type_normalizes_accents_and_variants():
    assert classify_operation_type("Compra") == "buy"
    assert classify_operation_type("Venta") == "sell"
    assert classify_operation_type("Suscripcion FCI") == "fci_subscription"
    assert classify_operation_type("Rescate FCI") == "fci_redemption"


def test_get_effective_operation_amount_uses_fallback_quantity_times_price():
    op = SimpleNamespace(
        monto_operado=None,
        monto_operacion=None,
        monto=None,
        cantidad_operada=Decimal("3"),
        precio_operado=Decimal("12.5"),
    )

    assert get_effective_operation_amount(op) == Decimal("37.5")


def test_classify_observed_operation_cost_marks_high_watch_and_missing():
    assert classify_observed_operation_cost(Decimal("1.20"))[0] == "high"
    assert classify_observed_operation_cost(Decimal("0.40"))[0] == "watch"
    assert classify_observed_operation_cost(Decimal("0.10"))[0] == "low"
    assert classify_observed_operation_cost(Decimal("0"))[0] == "missing"
