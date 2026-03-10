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
