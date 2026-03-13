from django.template import Context, Template
from django.test import SimpleTestCase


class TestCurrencyFilters(SimpleTestCase):
    def test_currency_filter_uses_default_decimals_on_invalid_input(self):
        rendered = Template("{{ value|currency:'bad' }}").render(Context({"value": 1234.5}))
        assert rendered == "$1.234,50"

    def test_currency_filter_handles_none_value(self):
        rendered = Template("{{ value|currency:2 }}").render(Context({"value": None}))
        assert rendered == "$0,00"
