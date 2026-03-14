import logging
from datetime import datetime

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"
    DAILY_FUNCTION = "TIME_SERIES_DAILY"
    WEEKLY_ADJUSTED_FUNCTION = "TIME_SERIES_WEEKLY_ADJUSTED"

    def __init__(self):
        self.api_key = settings.ALPHA_VANTAGE_API_KEY

    def fetch_daily_adjusted(self, symbol: str, outputsize: str = "compact") -> list[dict]:
        return self._fetch_time_series(
            symbol=symbol,
            function=self.DAILY_FUNCTION,
            outputsize=outputsize,
            payload_key="Time Series (Daily)",
        )

    def fetch_weekly_adjusted(self, symbol: str) -> list[dict]:
        return self._fetch_time_series(
            symbol=symbol,
            function=self.WEEKLY_ADJUSTED_FUNCTION,
            payload_key="Weekly Adjusted Time Series",
        )

    def _fetch_time_series(
        self,
        symbol: str,
        function: str,
        payload_key: str,
        outputsize: str | None = None,
    ) -> list[dict]:
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is required")

        params = {
            "function": function,
            "symbol": symbol,
            "apikey": self.api_key,
        }
        if outputsize:
            params["outputsize"] = outputsize

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if "Error Message" in payload:
            raise ValueError(payload["Error Message"])
        if "Note" in payload:
            raise ValueError(payload["Note"])
        if "Information" in payload:
            raise ValueError(payload["Information"])

        raw_series = payload.get(payload_key, {})
        rows = []
        for raw_date, values in raw_series.items():
            rows.append(
                {
                    "fecha": datetime.strptime(raw_date, "%Y-%m-%d").date(),
                    "close": float(values["4. close"]),
                    "adjusted_close": float(values.get("5. adjusted close") or values["4. close"]),
                    "volume": int(values.get("6. volume") or values.get("5. volume", 0) or 0),
                }
            )
        return sorted(rows, key=lambda item: item["fecha"])
