from django.db import models


class ActivoPortafolioSnapshot(models.Model):
    fecha_extraccion = models.DateTimeField()
    pais_consulta = models.CharField(max_length=50)
    simbolo = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=20, decimal_places=4)
    comprometido = models.DecimalField(max_digits=20, decimal_places=4)
    disponible_inmediato = models.DecimalField(max_digits=20, decimal_places=4)
    puntos_variacion = models.DecimalField(max_digits=20, decimal_places=6)
    variacion_diaria = models.DecimalField(max_digits=12, decimal_places=4)
    ultimo_precio = models.DecimalField(max_digits=20, decimal_places=6)
    ppc = models.DecimalField(max_digits=20, decimal_places=6)
    ganancia_porcentaje = models.DecimalField(max_digits=12, decimal_places=4)
    ganancia_dinero = models.DecimalField(max_digits=20, decimal_places=6)
    valorizado = models.DecimalField(max_digits=20, decimal_places=6)
    pais_titulo = models.CharField(max_length=50)
    mercado = models.CharField(max_length=50)
    tipo = models.CharField(max_length=50)
    plazo = models.CharField(max_length=50, null=True, blank=True)
    moneda = models.CharField(max_length=50)
    parking = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_extraccion', 'simbolo']
        indexes = [
            models.Index(fields=['fecha_extraccion']),
            models.Index(fields=['simbolo']),
            models.Index(fields=['pais_consulta']),
        ]

    def __str__(self):
        return f"{self.simbolo} - {self.fecha_extraccion}"


class PortfolioSnapshot(models.Model):
    """Snapshot diario del estado completo del portafolio."""

    fecha = models.DateField(unique=True)

    # Valores patrimoniales principales
    total_iol = models.DecimalField(max_digits=15, decimal_places=2, help_text="Total IOL (activos + cash)")
    liquidez_operativa = models.DecimalField(max_digits=15, decimal_places=2, help_text="Cash + caución + FCI disponibles")
    cash_management = models.DecimalField(max_digits=15, decimal_places=2, help_text="FCI de cash management")
    portafolio_invertido = models.DecimalField(max_digits=15, decimal_places=2, help_text="Activos de inversión")
    total_patrimonio_modelado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total patrimonial modelado con capas explícitas",
    )
    cash_disponible_broker = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cash broker explícito persistido para snapshots nuevos",
    )
    caucion_colocada = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Caución colocada persistida para snapshots nuevos",
    )

    # Rendimiento
    rendimiento_total = models.FloatField(help_text="Rendimiento total del portafolio (%)")

    # Exposición por país
    exposicion_usa = models.FloatField(help_text="Exposición a USA (%)")
    exposicion_argentina = models.FloatField(help_text="Exposición a Argentina (%)")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['fecha']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(total_iol__gte=0)
                    & models.Q(liquidez_operativa__gte=0)
                    & models.Q(cash_management__gte=0)
                    & models.Q(portafolio_invertido__gte=0)
                    & (
                        models.Q(total_patrimonio_modelado__gte=0)
                        | models.Q(total_patrimonio_modelado__isnull=True)
                    )
                    & (
                        models.Q(cash_disponible_broker__gte=0)
                        | models.Q(cash_disponible_broker__isnull=True)
                    )
                    & (
                        models.Q(caucion_colocada__gte=0)
                        | models.Q(caucion_colocada__isnull=True)
                    )
                ),
                name="portfolio_snapshot_non_negative_amounts",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(exposicion_usa__gte=0)
                    & models.Q(exposicion_usa__lte=100)
                    & models.Q(exposicion_argentina__gte=0)
                    & models.Q(exposicion_argentina__lte=100)
                ),
                name="portfolio_snapshot_exposure_range_valid",
            ),
        ]

    def __str__(self):
        return f"Portfolio Snapshot {self.fecha}"

    @property
    def liquidez_total(self):
        """Liquidez operativa + cash management."""
        if self.cash_disponible_broker is not None or self.caucion_colocada is not None:
            return (
                (self.cash_disponible_broker or 0)
                + (self.caucion_colocada or 0)
                + self.cash_management
            )
        return self.liquidez_operativa + self.cash_management


class PositionSnapshot(models.Model):
    """Snapshot detallado de cada posición en el portafolio."""

    snapshot = models.ForeignKey(
        PortfolioSnapshot,
        on_delete=models.CASCADE,
        related_name="positions"
    )

    simbolo = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=200, blank=True)

    # Valores financieros
    valorizado = models.DecimalField(max_digits=15, decimal_places=2)
    peso = models.FloatField(help_text="Peso en el portafolio total (%)")

    # Clasificación
    sector = models.CharField(max_length=100, blank=True)
    pais = models.CharField(max_length=50, blank=True)
    tipo = models.CharField(max_length=50, blank=True)
    bloque_estrategico = models.CharField(max_length=100, blank=True)

    # Rendimiento
    ganancia_dinero = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ganancia_porcentaje = models.FloatField(default=0)

    class Meta:
        ordering = ['-peso']
        indexes = [
            models.Index(fields=['snapshot', 'simbolo']),
            models.Index(fields=['snapshot', 'sector']),
            models.Index(fields=['snapshot', 'pais']),
        ]
        unique_together = ['snapshot', 'simbolo']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valorizado__gte=0),
                name="position_snapshot_non_negative_valorizado",
            ),
            models.CheckConstraint(
                condition=models.Q(peso__gte=0, peso__lte=100),
                name="position_snapshot_weight_range_valid",
            ),
        ]

    def __str__(self):
        return f"{self.simbolo} - {self.snapshot.fecha}"
