from __future__ import annotations

from datetime import date, datetime

import requests
from django.conf import settings


class OptionalSourceUnavailableError(ValueError):
    """Raised when an optional external source is not configured."""


class FXJSONClient:
    def __init__(self):
        self.mep_url = settings.USDARS_MEP_API_URL
        self.mep_value_path = settings.USDARS_MEP_API_VALUE_PATH
        self.mep_date_path = settings.USDARS_MEP_API_DATE_PATH

    def fetch_usdars_mep(self) -> list[dict]:
        if not self.mep_url:
            raise OptionalSourceUnavailableError("USDARS_MEP_API_URL is required")

        response = requests.get(self.mep_url, timeout=30)
        response.raise_for_status()
        payload = response.json()

        value = self._extract_path(payload, self.mep_value_path)
        if value is None:
            raise ValueError(f"Missing configured value path for USDARS MEP: {self.mep_value_path}")

        raw_date = self._extract_path(payload, self.mep_date_path) if self.mep_date_path else None
        return [
            {
                "fecha": self._parse_date(raw_date),
                "value": float(value),
            }
        ]

    @staticmethod
    def _extract_path(payload, path: str):
        current = payload
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @staticmethod
    def _parse_date(raw_date) -> date:
        if not raw_date:
            return date.today()
        if isinstance(raw_date, date):
            return raw_date
        normalized = str(raw_date).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            try:
                return datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError(f"Unsupported USDARS MEP date format: {raw_date}") from exc
