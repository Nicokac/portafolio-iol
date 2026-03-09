from django.db import models


class OperacionIOL(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    fecha_orden = models.DateTimeField()
    tipo = models.CharField(max_length=50)
    estado = models.CharField(max_length=50)
    mercado = models.CharField(max_length=50)
    simbolo = models.CharField(max_length=20)
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    monto = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    modalidad = models.CharField(max_length=50)
    precio = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fecha_operada = models.DateTimeField(null=True, blank=True)
    cantidad_operada = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    precio_operado = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    monto_operado = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    plazo = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ['-fecha_orden']
        indexes = [
            models.Index(fields=['fecha_orden']),
            models.Index(fields=['simbolo']),
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"{self.numero} - {self.simbolo} - {self.fecha_orden}"