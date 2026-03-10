from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class CurrencyFormatter:
    """Centralized currency formatter for AR-style numbers (1.234,56)."""

    @staticmethod
    def _to_decimal(value):
        if value in (None, ""):
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @classmethod
    def format_number(cls, value, decimals=2):
        decimal_value = cls._to_decimal(value)
        if decimal_value is None:
            return str(value)

        decimals = int(decimals)
        quantizer = Decimal("1") if decimals == 0 else Decimal(f"1.{'0' * decimals}")
        quantized = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)

        sign = "-" if quantized < 0 else ""
        quantized = abs(quantized)

        us_style = f"{quantized:,.{decimals}f}"
        ar_style = us_style.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{sign}{ar_style}"

    @classmethod
    def format_currency(cls, value, decimals=2, symbol="$"):
        formatted = cls.format_number(value, decimals=decimals)
        if formatted.startswith("-"):
            return f"-{symbol}{formatted[1:]}"
        return f"{symbol}{formatted}"
