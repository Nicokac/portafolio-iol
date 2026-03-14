class ParametrosMacroLocal:
    """Series macro locales priorizadas para analitica del portafolio."""

    SERIES = {
        "usdars_oficial": {
            "title": "USDARS mayorista BCRA",
            "source": "bcra",
            "external_id": "5",
            "frequency": "daily",
        },
        "ipc_nacional": {
            "title": "IPC nacional mensual",
            "source": "datos_gob_ar",
            "external_id": "145.3_INGNACNAL_DICI_M_15",
            "frequency": "monthly",
        },
    }
