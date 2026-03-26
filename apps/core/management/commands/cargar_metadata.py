from django.core.management.base import BaseCommand

from apps.parametros.models import ParametroActivo


ASSET_METADATA = [
    # CEDEAR tecnologia / growth
    {
        "simbolo": "AAPL",
        "sector": "Tecnología",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "MSFT",
        "sector": "Tecnología",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "GOOGL",
        "sector": "Tecnología",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "NVDA",
        "sector": "Tecnología",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "CRM",
        "sector": "Tecnología",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "AMZN",
        "sector": "Consumo",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "MELI",
        "sector": "Tecnología / E-commerce",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "Latam",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "BABA",
        "sector": "Tecnología / E-commerce",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "China",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "AMD",
        "sector": "Tecnología / Semiconductores",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    # ETFs
    {
        "simbolo": "SPY",
        "sector": "Índice",
        "bloque_estrategico": "Core",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "ETF",
    },
    {
        "simbolo": "EEM",
        "sector": "Índice",
        "bloque_estrategico": "Emergentes",
        "pais_exposicion": "EM",
        "tipo_patrimonial": "ETF",
    },
    {
        "simbolo": "EWZ",
        "sector": "Índice",
        "bloque_estrategico": "Brasil",
        "pais_exposicion": "Brasil",
        "tipo_patrimonial": "ETF",
    },
    {
        "simbolo": "IEUR",
        "sector": "Índice",
        "bloque_estrategico": "Europa",
        "pais_exposicion": "Europa",
        "tipo_patrimonial": "ETF",
    },
    {
        "simbolo": "DIA",
        "sector": "Índice",
        "bloque_estrategico": "Core",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "ETF",
    },
    {
        "simbolo": "XLU",
        "sector": "Utilities",
        "bloque_estrategico": "Defensivo",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "ETF",
    },
    {
        "simbolo": "XLV",
        "sector": "Salud",
        "bloque_estrategico": "Defensivo",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "ETF",
    },
    # Equities / defensivo / dividendos / commodities
    {
        "simbolo": "T",
        "sector": "Telecom",
        "bloque_estrategico": "Dividendos",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "KO",
        "sector": "Consumo defensivo",
        "bloque_estrategico": "Dividendos",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "MCD",
        "sector": "Consumo defensivo",
        "bloque_estrategico": "Dividendos",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "BRKB",
        "sector": "Finanzas / Holding",
        "bloque_estrategico": "Defensivo",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "V",
        "sector": "Finanzas / Payments",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "DISN",
        "sector": "Consumo / Media",
        "bloque_estrategico": "Growth",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "NEM",
        "sector": "Minería",
        "bloque_estrategico": "Commodities",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "Equity",
    },
    # Argentina
    {
        "simbolo": "YPFD",
        "sector": "Energía",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "TECO2",
        "sector": "Telecom",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "LOMA",
        "sector": "Materiales",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Equity",
    },
    {
        "simbolo": "VIST",
        "sector": "Energía",
        "bloque_estrategico": "Commodities",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Equity",
    },
    # Bonos
    {
        "simbolo": "AL30",
        "sector": "Soberano",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Bond",
    },
    {
        "simbolo": "GD30",
        "sector": "Soberano",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Bond",
    },
    {
        "simbolo": "GD35",
        "sector": "Soberano",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Bond",
    },
    {
        "simbolo": "TZX26",
        "sector": "CER",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Bond",
    },
    {
        "simbolo": "TZXM6",
        "sector": "CER",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Bond",
    },
    {
        "simbolo": "BPOC7",
        "sector": "Corporativo",
        "bloque_estrategico": "Argentina",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Bond",
    },
    # FCI / cash management / liquidez
    {
        "simbolo": "ADBAICA",
        "sector": "Cash Mgmt",
        "bloque_estrategico": "Liquidez",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "FCI",
    },
    {
        "simbolo": "IOLPORA",
        "sector": "Cash Mgmt",
        "bloque_estrategico": "Liquidez",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "FCI",
    },
    {
        "simbolo": "PRPEDOB",
        "sector": "Cash Mgmt",
        "bloque_estrategico": "USD",
        "pais_exposicion": "USA",
        "tipo_patrimonial": "FCI",
    },
    {
        "simbolo": "CAUCIÓN",
        "sector": "Liquidez",
        "bloque_estrategico": "Liquidez",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Cash",
    },
    {
        "simbolo": "CAUCIÓN COLOCADORA",
        "sector": "Liquidez",
        "bloque_estrategico": "Liquidez",
        "pais_exposicion": "Argentina",
        "tipo_patrimonial": "Cash",
    },
]


class Command(BaseCommand):
    help = "Carga metadata bootstrap para ParametroActivo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra que registros se crearian o actualizarian sin persistir cambios.",
        )

    @staticmethod
    def _defaults_for(item):
        return {
            "sector": item["sector"],
            "bloque_estrategico": item["bloque_estrategico"],
            "pais_exposicion": item["pais_exposicion"],
            "tipo_patrimonial": item["tipo_patrimonial"],
            "observaciones": item.get("observaciones", "Bootstrap inicial desde cargar_metadata"),
        }

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        created_count = 0
        updated_count = 0

        for item in ASSET_METADATA:
            defaults = self._defaults_for(item)
            existing = ParametroActivo.objects.filter(simbolo=item["simbolo"]).first()
            if existing is None:
                created_count += 1
                action = "Crearia" if dry_run else "Creado"
                if not dry_run:
                    ParametroActivo.objects.create(simbolo=item["simbolo"], **defaults)
            else:
                changed = any(getattr(existing, field) != value for field, value in defaults.items())
                if changed:
                    updated_count += 1
                    action = "Actualizaria" if dry_run else "Actualizado"
                    if not dry_run:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save(update_fields=list(defaults.keys()))
                else:
                    action = "Sin cambios"

            self.stdout.write(f"{action}: {item['simbolo']}")

        mode_label = "Dry run" if dry_run else "Carga completada"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode_label}: {created_count} creados, {updated_count} actualizados"
            )
        )
