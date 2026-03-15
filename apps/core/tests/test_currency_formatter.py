from django.template import Context, Template
from django.test import SimpleTestCase

from apps.core.templatetags.currency_filters import currency, pct
from apps.core.utils.currency_formatter import CurrencyFormatter


class TestCurrencyFormatter(SimpleTestCase):
    def test_format_number_with_thousands_and_decimals(self):
        assert CurrencyFormatter.format_number(1234567.89, 2) == "1.234.567,89"

    def test_format_currency_with_zero_decimals(self):
        assert CurrencyFormatter.format_currency(1234567.89, 0) == "$1.234.568"

    def test_format_currency_negative(self):
        assert CurrencyFormatter.format_currency(-1234.5, 2) == "-$1.234,50"

    def test_currency_template_filter_is_available_globally(self):
        rendered = Template("{{ value|currency:2 }}").render(Context({"value": 9876543.2}))
        assert rendered == "$9.876.543,20"

    def test_currency_filter_falls_back_to_two_decimals_for_invalid_precision(self):
        assert currency(1234.5, "invalid") == "$1.234,50"

    def test_pct_filter_formats_small_positive_values(self):
        assert pct(0.004, 2) == "< 0,01%"

    def test_pct_filter_formats_small_negative_values(self):
        assert pct(-0.004, 2) == "> -0,01%"
