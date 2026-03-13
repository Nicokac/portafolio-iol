import logging
from datetime import datetime

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"
    FUNCTION = "TIME_SERIES_DAILY"

    def __init__(self):
        self.api_key = settings.ALPHA_VANTAGE_API_KEY

    def fetch_daily_adjusted(self, symbol: str, outputsize: str = "compact") -> list[dict]:
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is required")

        response = requests.get(
            self.BASE_URL,
            params={
                "function": self.FUNCTION,
                "symbol": symbol,
                "outputsize": outputsize,
                "apikey": self.api_key,
            },
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

        raw_series = payload.get("Time Series (Daily)", {})
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
