from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_score_finviz_candidates_command_prints_shortlist(monkeypatch):
    class DummyService:
        def build_latest_shortlist(self, **kwargs):
            assert kwargs["limit"] == 3
            return {
                "captured_date": "2026-03-27",
                "count": 1,
                "items": [
                    {
                        "rank": 1,
                        "internal_symbol": "MSFT",
                        "composite_buy_score": 82.1,
                        "interpretation": {"label": "Alta conviccion"},
                        "main_reason": "Buena señal de quality.",
                    }
                ],
            }

        def compare_candidates(self, symbols):
            raise AssertionError("No deberia llamarse compare_candidates en este test")

    monkeypatch.setattr(
        "apps.core.management.commands.score_finviz_candidates.FinvizScoringService",
        lambda: DummyService(),
    )
    stdout = StringIO()

    call_command("score_finviz_candidates", "--limit=3", stdout=stdout)

    output = stdout.getvalue()
    assert "[finviz_shortlist]" in output
    assert "MSFT" in output
    assert "82.1" in output


@pytest.mark.django_db
def test_score_finviz_candidates_command_supports_compare_mode(monkeypatch):
    class DummyService:
        def build_latest_shortlist(self, **kwargs):
            raise AssertionError("No deberia llamarse shortlist en este test")

        def compare_candidates(self, symbols):
            assert symbols == ["MSFT", "AAPL"]
            return {
                "summary": "MSFT queda arriba por 4.0 puntos sobre AAPL.",
                "items": [
                    {
                        "internal_symbol": "MSFT",
                        "composite_buy_score": 80.0,
                        "quality_score": 90.0,
                        "valuation_score": 70.0,
                        "interpretation": {"label": "Alta conviccion"},
                    }
                ],
            }

    monkeypatch.setattr(
        "apps.core.management.commands.score_finviz_candidates.FinvizScoringService",
        lambda: DummyService(),
    )
    stdout = StringIO()

    call_command("score_finviz_candidates", "--symbols=MSFT,AAPL", stdout=stdout)

    output = stdout.getvalue()
    assert "[finviz_compare]" in output
    assert "MSFT queda arriba" in output
