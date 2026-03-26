from __future__ import annotations

from typing import Any

from apps.core.services.iol_api_client import IOLAPIClient


class IOLMEPService:
    """Enriquecimiento MEP implicito para CEDEARs y lectura resumida de exposicion USD."""

    def __init__(self, client: IOLAPIClient | None = None):
        self.client = client or IOLAPIClient()

    def get_mep_quotes_by_symbols(self, symbols: list[str] | tuple[str, ...]) -> dict[str, dict[str, Any]]:
        payload: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()

        for raw_symbol in symbols:
            symbol = str(raw_symbol or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)

            mep_price = self.client.get_mep_quote(symbol)
            if mep_price is None or mep_price <= 0:
                continue

            payload[symbol] = {
                "symbol": symbol,
                "mep_price_ars": float(mep_price),
                "source": "iol_mep_endpoint",
            }

        return payload

    def build_implicit_fx_summary(self, *, relevant_positions: list[dict[str, Any]]) -> dict[str, Any]:
        total_positions_count = len(relevant_positions)
        covered_positions_count = 0
        covered_value_ars = 0.0
        implied_usd_value = 0.0

        for item in relevant_positions:
            mep_profile = item.get("mep_profile") or {}
            mep_price = self._as_float(mep_profile.get("mep_price_ars"))
            if mep_price <= 0:
                continue

            ars_value = self._as_float(getattr(item.get("activo"), "valorizado", 0))
            if ars_value <= 0:
                continue

            covered_positions_count += 1
            covered_value_ars += ars_value
            implied_usd_value += ars_value / mep_price

        coverage_pct = (covered_positions_count / total_positions_count * 100.0) if total_positions_count > 0 else 0.0
        weighted_mep = (covered_value_ars / implied_usd_value) if implied_usd_value > 0 else None

        return {
            "total_positions_count": total_positions_count,
            "covered_positions_count": covered_positions_count,
            "coverage_pct": round(coverage_pct, 2),
            "covered_value_ars": round(covered_value_ars, 2),
            "implied_usd_value": round(implied_usd_value, 2),
            "weighted_mep": round(weighted_mep, 2) if weighted_mep is not None else None,
            "methodology": {
                "covered_value_ars": "suma del valorizado ARS de posiciones con MEP implicito disponible",
                "implied_usd_value": "valorizado ARS / precio MEP implicito por simbolo",
                "weighted_mep": "covered_value_ars / implied_usd_value",
                "coverage_pct": "covered_positions_count / total_positions_count",
            },
        }

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
