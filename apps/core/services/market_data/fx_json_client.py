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
        self.country_risk_url = settings.RIESGO_PAIS_API_URL
        self.country_risk_value_path = settings.RIESGO_PAIS_API_VALUE_PATH
        self.country_risk_date_path = settings.RIESGO_PAIS_API_DATE_PATH
        self.country_risk_api_key = settings.RIESGO_PAIS_API_KEY
        self.country_risk_api_key_header = settings.RIESGO_PAIS_API_KEY_HEADER

    def fetch_usdars_mep(self) -> list[dict]:
        return self._fetch_configured_scalar(
            url=self.mep_url,
            value_path=self.mep_value_path,
            date_path=self.mep_date_path,
            missing_url_error="USDARS_MEP_API_URL is required",
            missing_value_error=f"Missing configured value path for USDARS MEP: {self.mep_value_path}",
        )

    def fetch_riesgo_pais(self) -> list[dict]:
        if not self.country_risk_url:
            raise OptionalSourceUnavailableError("RIESGO_PAIS_API_URL is required")

        headers = {}
        if self.country_risk_api_key:
            headers[self.country_risk_api_key_header] = self.country_risk_api_key
        request_kwargs = {"timeout": 30}
        if headers:
            request_kwargs["headers"] = headers

        response = requests.get(self.country_risk_url, **request_kwargs)
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            rows = []
            for item in payload:
                value = self._extract_path(item, self.country_risk_value_path)
                if value is None:
                    raise ValueError(f"Missing configured value path for riesgo pais: {self.country_risk_value_path}")
                raw_date = self._extract_path(item, self.country_risk_date_path) if self.country_risk_date_path else None
                rows.append(
                    {
                        "fecha": self._parse_date(raw_date),
                        "value": float(value),
                    }
                )
            return rows

        value = self._extract_path(payload, self.country_risk_value_path)
        if value is None:
            raise ValueError(f"Missing configured value path for riesgo pais: {self.country_risk_value_path}")

        raw_date = self._extract_path(payload, self.country_risk_date_path) if self.country_risk_date_path else None
        return [
            {
                "fecha": self._parse_date(raw_date),
                "value": float(value),
            }
        ]

    def _fetch_configured_scalar(
        self,
        *,
        url: str,
        value_path: str,
        date_path: str,
        missing_url_error: str,
        missing_value_error: str,
        headers: dict | None = None,
    ) -> list[dict]:
        if not url:
            raise OptionalSourceUnavailableError(missing_url_error)

        request_kwargs = {"timeout": 30}
        if headers:
            request_kwargs["headers"] = headers
        response = requests.get(url, **request_kwargs)
        response.raise_for_status()
        payload = response.json()

        value = self._extract_path(payload, value_path)
        if value is None:
            raise ValueError(missing_value_error)

        raw_date = self._extract_path(payload, date_path) if date_path else None
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
