from django.core.management.base import BaseCommand

from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService


class Command(BaseCommand):
    help = "Sincroniza historicos IOL para simbolos actuales o un simbolo puntual"

    def add_arguments(self, parser):
        parser.add_argument("--simbolo", help="Simbolo puntual a sincronizar")
        parser.add_argument("--mercado", help="Mercado del simbolo puntual")

    def handle(self, *args, **options):
        service = IOLHistoricalPriceService()
        simbolo = options.get("simbolo")
        mercado = options.get("mercado")

        self.stdout.write("Sincronizando historicos IOL...")

        if simbolo or mercado:
            if not simbolo or not mercado:
                raise SystemExit("Debe informar ambos parametros: --simbolo y --mercado")
            result = service.sync_symbol_history(mercado=mercado, simbolo=simbolo)
            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {mercado}:{simbolo}: created={result['created']} updated={result['updated']} rows={result['rows_received']}"
                    )
                )
                self.stdout.write(self.style.SUCCESS("Sincronizacion de historicos IOL completada"))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {mercado}:{simbolo}: error={result.get('error', 'unknown')} rows={result.get('rows_received', 0)}"
                    )
                )
                self.stdout.write(self.style.WARNING("Sincronizacion de historicos IOL completada con fallos"))
            return

        result = service.sync_current_portfolio_symbols()
        has_partial_failures = False
        for key, payload in result.get("results", {}).items():
            if payload.get("success"):
                self.stdout.write(
                    f"  {key}: created={payload['created']} updated={payload['updated']} rows={payload['rows_received']}"
                )
            else:
                has_partial_failures = True
                self.stdout.write(
                    self.style.WARNING(
                        f"  {key}: error={payload.get('error', 'unknown')} rows={payload.get('rows_received', 0)}"
                    )
                )

        if result.get("success", True) and not has_partial_failures:
            self.stdout.write(self.style.SUCCESS("Sincronizacion de historicos IOL completada"))
        else:
            self.stdout.write(self.style.WARNING("Sincronizacion de historicos IOL completada con fallos parciales"))
