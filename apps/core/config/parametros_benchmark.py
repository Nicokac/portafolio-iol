class ParametrosBenchmark:
    """
    Parámetros institucionales de benchmark.
    Annual returns esperados usados para series de referencia sintética diaria.
    """

    BENCHMARK_MAPPINGS = {
        "cedear_usa": "sp500",
        "bonos_ar": "cer_embi_proxy",
        "liquidez": "caucion_rate",
    }

    ANNUAL_RETURNS = {
        "sp500": 0.10,
        "cer_embi_proxy": 0.28,
        "caucion_rate": 0.22,
    }

    DEFAULT_WEIGHTS = {
        "cedear_usa": 0.40,
        "bonos_ar": 0.35,
        "liquidez": 0.25,
    }

    HISTORICAL_SERIES = {
        "cedear_usa": {
            "symbol": "SPY",
            "provider": "alpha_vantage",
            "field": "adjusted_close",
        },
    }
