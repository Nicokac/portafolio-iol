from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_inspect_finviz_opportunity_watchlist_command_runs():
    out = StringIO()

    call_command("inspect_finviz_opportunity_watchlist", stdout=out)

    output = out.getvalue()
    assert "[finviz_opportunity_watchlist]" in output
    assert "shortlist=" in output
