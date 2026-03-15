from django import template

from apps.core.utils.currency_formatter import CurrencyFormatter

register = template.Library()


@register.filter(name="currency")
def currency(value, decimals=2):
    try:
        decimals = int(decimals)
    except (TypeError, ValueError):
        decimals = 2
    return CurrencyFormatter.format_currency(value, decimals=decimals)


@register.filter(name="pct")
def pct(value, decimals=1):
    try:
        decimals = int(decimals)
    except (TypeError, ValueError):
        decimals = 1

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "-"

    threshold = 10 ** (-decimals)
    formatted_threshold = f"{threshold:.{decimals}f}".replace(".", ",")

    if 0 < numeric_value < threshold:
        return f"< {formatted_threshold}%"
    if -threshold < numeric_value < 0:
        return f"> -{formatted_threshold}%"

    return f"{numeric_value:.{decimals}f}".replace(".", ",") + "%"
