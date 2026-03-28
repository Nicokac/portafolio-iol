from __future__ import annotations

from typing import Any


class FinvizClient:
    """Wrapper minimo para aislar acceso a finvizfinance y sus errores."""

    def __init__(self):
        self.last_error: dict[str, str] = {}

    def get_fundamentals(self, symbol: str) -> dict[str, Any] | None:
        self.last_error = {}
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            self.last_error = {"code": "empty_symbol", "message": "Empty Finviz symbol"}
            return None

        try:
            from finvizfinance.quote import finvizfinance
        except Exception as exc:  # pragma: no cover - depende del entorno
            self.last_error = {"code": "dependency_error", "message": str(exc)}
            return None

        try:
            payload = finvizfinance(normalized_symbol).ticker_fundament()
        except Exception as exc:
            self.last_error = {"code": "fetch_error", "message": str(exc)}
            return None

        if not payload:
            self.last_error = {"code": "empty_payload", "message": "Finviz returned no fundamentals"}
            return None

        return payload

    def get_ratings(self, symbol: str) -> list[dict[str, Any]] | None:
        return self._get_dataframe_records(symbol, "ticker_outer_ratings", "ratings")

    def get_news(self, symbol: str) -> list[dict[str, Any]] | None:
        return self._get_dataframe_records(symbol, "ticker_news", "news")

    def get_insiders(self, symbol: str) -> list[dict[str, Any]] | None:
        return self._get_dataframe_records(symbol, "ticker_inside_trader", "insiders")

    def _get_dataframe_records(self, symbol: str, method_name: str, operation_name: str) -> list[dict[str, Any]] | None:
        self.last_error = {}
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            self.last_error = {"code": "empty_symbol", "message": "Empty Finviz symbol"}
            return None

        try:
            from finvizfinance.quote import finvizfinance
        except Exception as exc:  # pragma: no cover - depende del entorno
            self.last_error = {"code": "dependency_error", "message": str(exc)}
            return None

        try:
            quote = finvizfinance(normalized_symbol)
            data = getattr(quote, method_name)()
        except Exception as exc:
            self.last_error = {"code": f"{operation_name}_error", "message": str(exc)}
            return None

        if data is None:
            self.last_error = {"code": "empty_payload", "message": f"Finviz returned no {operation_name}"}
            return []
        if hasattr(data, "empty") and data.empty:
            return []
        if hasattr(data, "to_dict"):
            return data.to_dict(orient="records")
        return list(data) if isinstance(data, list) else []
