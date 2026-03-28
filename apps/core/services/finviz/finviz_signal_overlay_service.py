from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.models import FinvizSignalSnapshot
from apps.core.services.finviz.finviz_client import FinvizClient
from apps.core.services.finviz.finviz_mapping_service import FinvizMappingService


class FinvizSignalOverlayService:
    """Sincroniza overlays secundarios de ratings, news e insiders."""

    SOURCE_KEY = "finviz_signal"
    POSITIVE_TOKENS = ("upgrade", "buy", "outperform", "overweight", "positive", "accumulate", "add")
    NEGATIVE_TOKENS = ("downgrade", "sell", "underperform", "underweight", "negative", "reduce")
    NEUTRAL_TOKENS = ("hold", "neutral", "equal", "market perform", "perform")
    BUY_TOKENS = ("buy", "purchase", "acquired")
    SALE_TOKENS = ("sale", "sell", "disposed")

    def __init__(
        self,
        *,
        client: FinvizClient | None = None,
        mapping_service: FinvizMappingService | None = None,
    ):
        self.client = client or FinvizClient()
        self.mapping_service = mapping_service or FinvizMappingService()

    def sync_signals(self, *, scope: str = "metadata", symbols: list[str] | None = None, captured_at=None) -> dict:
        captured_at = captured_at or timezone.now()
        mapped_rows = self._get_mapped_rows(scope=scope, symbols=symbols)
        created = 0
        updated = 0
        ok = 0
        errors = 0

        with transaction.atomic():
            for row in mapped_rows:
                ratings = self.client.get_ratings(row["finviz_symbol"])
                ratings_error = dict(self.client.last_error)
                news = self.client.get_news(row["finviz_symbol"])
                news_error = dict(self.client.last_error)
                insiders = self.client.get_insiders(row["finviz_symbol"])
                insiders_error = dict(self.client.last_error)
                normalized = self._build_snapshot_defaults(
                    row=row,
                    ratings=ratings,
                    news=news,
                    insiders=insiders,
                    errors={
                        "ratings": ratings_error if ratings is None else {},
                        "news": news_error if news is None else {},
                        "insiders": insiders_error if insiders is None else {},
                    },
                    captured_at=captured_at,
                )
                _, was_created = FinvizSignalSnapshot.objects.update_or_create(
                    internal_symbol=row["internal_symbol"],
                    source=self.SOURCE_KEY,
                    captured_date=normalized["captured_date"],
                    defaults=normalized,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
                if normalized["source_status"] == "ok":
                    ok += 1
                else:
                    errors += 1

        return {
            "success": True,
            "scope": scope,
            "mapped_assets": len(mapped_rows),
            "created": created,
            "updated": updated,
            "ok": ok,
            "errors": errors,
            "captured_date": captured_at.date().isoformat(),
        }

    def list_latest_snapshots(self, *, symbols: list[str] | None = None, limit: int | None = None) -> dict:
        latest_date = FinvizSignalSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return {"captured_date": None, "count": 0, "items": []}

        queryset = FinvizSignalSnapshot.objects.filter(captured_date=latest_date).order_by("internal_symbol")
        if symbols:
            normalized_symbols = [str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()]
            queryset = queryset.filter(internal_symbol__in=normalized_symbols)
        if limit:
            queryset = queryset[:limit]

        items = [self._serialize_snapshot(item) for item in queryset]
        return {"captured_date": latest_date.isoformat(), "count": len(items), "items": items}

    def _get_mapped_rows(self, *, scope: str, symbols: list[str] | None) -> list[dict[str, Any]]:
        if scope == "portfolio":
            summary = self.mapping_service.build_current_portfolio_summary()
        else:
            summary = self.mapping_service.build_metadata_universe_summary(symbols=symbols)
        rows = [row for row in summary["rows"] if row["status"] == "mapped"]
        if symbols and scope == "portfolio":
            requested = {str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()}
            rows = [row for row in rows if row["internal_symbol"] in requested]
        return rows

    def _build_snapshot_defaults(
        self,
        *,
        row: dict[str, Any],
        ratings: list[dict[str, Any]] | None,
        news: list[dict[str, Any]] | None,
        insiders: list[dict[str, Any]] | None,
        errors: dict[str, dict[str, str]],
        captured_at,
    ) -> dict[str, Any]:
        ratings_rows = ratings or []
        news_rows = news or []
        insider_rows = insiders or []
        positive, negative, neutral = self._summarize_ratings(ratings_rows)
        insider_buy_count, insider_sale_count = self._summarize_insiders(insider_rows)
        analyst_score = self._compute_analyst_score(positive=positive, negative=negative, neutral=neutral)
        analyst_label = self._classify_analyst_signal(analyst_score)
        has_any_payload = ratings is not None or news is not None or insiders is not None

        return {
            "internal_symbol": row["internal_symbol"],
            "finviz_symbol": row["finviz_symbol"] or "",
            "source": self.SOURCE_KEY,
            "captured_at": captured_at,
            "captured_date": captured_at.date(),
            "source_status": "ok" if has_any_payload else "error",
            "mapped_reason": row["reason"] or "",
            "ratings_count": len(ratings_rows),
            "ratings_positive_count": positive,
            "ratings_negative_count": negative,
            "ratings_neutral_count": neutral,
            "analyst_score": analyst_score,
            "analyst_signal_label": analyst_label,
            "news_count": len(news_rows),
            "insider_buy_count": insider_buy_count,
            "insider_sale_count": insider_sale_count,
            "raw_payload": {
                "ratings": self._make_json_safe(ratings_rows),
                "news": self._make_json_safe(news_rows),
                "insiders": self._make_json_safe(insider_rows),
            },
            "metadata": {
                "mapping_scope_source": row.get("source") or "",
                "errors": errors,
            },
        }

    def _summarize_ratings(self, rows: list[dict[str, Any]]) -> tuple[int, int, int]:
        positive = 0
        negative = 0
        neutral = 0
        for row in rows:
            signal = " ".join(
                str(row.get(key) or "")
                for key in ("Action", "action", "Rating", "rating", "Status", "status")
            ).strip().lower()
            if any(token in signal for token in self.POSITIVE_TOKENS):
                positive += 1
            elif any(token in signal for token in self.NEGATIVE_TOKENS):
                negative += 1
            else:
                neutral += 1
        return positive, negative, neutral

    def _summarize_insiders(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        buys = 0
        sales = 0
        for row in rows:
            signal = " ".join(
                str(row.get(key) or "")
                for key in ("Transaction", "transaction", "Type", "type", "Action", "action", "Option", "option type")
            ).strip().lower()
            if any(token in signal for token in self.BUY_TOKENS):
                buys += 1
            elif any(token in signal for token in self.SALE_TOKENS):
                sales += 1
        return buys, sales

    @staticmethod
    def _compute_analyst_score(*, positive: int, negative: int, neutral: int) -> Decimal | None:
        total = positive + negative + neutral
        if total <= 0:
            return None
        raw = 50 + ((positive - negative) / total) * 40
        bounded = max(0.0, min(100.0, raw))
        return Decimal(str(round(bounded, 2)))

    @staticmethod
    def _classify_analyst_signal(score: Decimal | None) -> str:
        if score is None:
            return ""
        numeric = float(score)
        if numeric >= 70:
            return "positive"
        if numeric <= 35:
            return "negative"
        if numeric <= 50:
            return "cautious"
        return "mixed"

    @staticmethod
    def _serialize_snapshot(snapshot: FinvizSignalSnapshot) -> dict:
        return {
            "internal_symbol": snapshot.internal_symbol,
            "finviz_symbol": snapshot.finviz_symbol,
            "source_status": snapshot.source_status,
            "ratings_count": snapshot.ratings_count,
            "ratings_positive_count": snapshot.ratings_positive_count,
            "ratings_negative_count": snapshot.ratings_negative_count,
            "ratings_neutral_count": snapshot.ratings_neutral_count,
            "analyst_score": float(snapshot.analyst_score) if snapshot.analyst_score is not None else None,
            "analyst_signal_label": snapshot.analyst_signal_label,
            "news_count": snapshot.news_count,
            "insider_buy_count": snapshot.insider_buy_count,
            "insider_sale_count": snapshot.insider_sale_count,
            "metadata": snapshot.metadata or {},
        }

    @classmethod
    def _make_json_safe(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._make_json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._make_json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [cls._make_json_safe(item) for item in value]
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)
