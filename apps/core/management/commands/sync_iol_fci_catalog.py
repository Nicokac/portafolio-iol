from django.core.management.base import BaseCommand

from apps.core.services.iol_fci_catalog_service import IOLFCICatalogService


class Command(BaseCommand):
    help = "Sincroniza el catalogo diario de FCI desde IOL"

    def handle(self, *args, **options):
        self.stdout.write("Sincronizando catalogo FCI...")
        result = IOLFCICatalogService().sync_catalog()

        if result.get("success"):
            self.stdout.write(
                self.style.SUCCESS(
                    "Catalogo FCI sincronizado: "
                    f"created={result.get('created', 0)} "
                    f"updated={result.get('updated', 0)} "
                    f"rows={result.get('rows_received', 0)} "
                    f"captured_date={result.get('captured_date')}"
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "Catalogo FCI con fallo: "
                f"rows={result.get('rows_received', 0)} "
                f"error={result.get('error', 'unknown')}"
            )
        )
