import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.utils.token_crypto import decrypt_token, encrypt_token, is_encrypted_token


logger = logging.getLogger(__name__)


class IOLToken(models.Model):
    """Modelo para almacenar tokens de acceso a la API de IOL."""

    access_token = models.TextField(help_text="JWT access token")
    refresh_token = models.TextField(blank=True, null=True, help_text="Refresh token")
    expires_at = models.DateTimeField(help_text="Fecha de expiración del access token")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"IOL Token expires {self.expires_at}"

    @property
    def is_expired(self):
        """Verifica si el token ha expirado."""
        return timezone.now() >= self.expires_at

    @classmethod
    def get_latest_valid_token(cls):
        """Obtiene el token más reciente que no haya expirado."""
        return cls.objects.filter(expires_at__gt=timezone.now()).first()

    def get_access_token(self):
        return self._get_and_migrate_token_field("access_token")

    def get_refresh_token(self):
        return self._get_and_migrate_token_field("refresh_token")

    def _get_and_migrate_token_field(self, field_name: str):
        raw_value = getattr(self, field_name)
        if raw_value in (None, ""):
            return raw_value

        plaintext = decrypt_token(raw_value)
        if is_encrypted_token(raw_value):
            return plaintext

        encrypted_value = encrypt_token(plaintext)
        type(self).objects.filter(pk=self.pk).update(**{field_name: encrypted_value})
        setattr(self, field_name, encrypted_value)
        logger.info("Migrated legacy IOL token field to encrypted format", extra={"field_name": field_name})
        return plaintext

    @classmethod
    def save_token(cls, access_token: str, refresh_token: str = None, expires_in: int = 3600):
        """Guarda un nuevo token, eliminando tokens anteriores."""
        # Eliminar tokens anteriores
        cls.objects.all().delete()

        # Crear nuevo token
        expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        return cls.objects.create(
            access_token=encrypt_token(access_token),
            refresh_token=encrypt_token(refresh_token),
            expires_at=expires_at
        )


class PortfolioParameters(models.Model):
    """Modelo para almacenar parámetros de configuración del portafolio."""

    # Pesos objetivo por categoría
    liquidez_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00,
        help_text="Porcentaje objetivo para liquidez (%)"
    )
    usa_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=40.00,
        help_text="Porcentaje objetivo para activos USA (%)"
    )
    argentina_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=30.00,
        help_text="Porcentaje objetivo para activos Argentina (%)"
    )
    emerging_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Porcentaje objetivo para mercados emergentes (%)"
    )

    # Parámetros de riesgo
    max_single_position = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.00,
        help_text="Máximo porcentaje por posición individual (%)"
    )
    risk_free_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=3.50,
        help_text="Tasa libre de riesgo (%)"
    )

    # Parámetros de rebalanceo
    rebalance_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, default=5.00,
        help_text="Umbral para trigger de rebalanceo (%)"
    )

    # Configuración adicional
    is_active = models.BooleanField(default=True, help_text="Si estos parámetros están activos")
    name = models.CharField(max_length=100, default="Parámetros Principales",
                           help_text="Nombre descriptivo de la configuración")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Parámetro de Portafolio"
        verbose_name_plural = "Parámetros de Portafolio"

    def __str__(self):
        return f"{self.name} ({'Activo' if self.is_active else 'Inactivo'})"

    @property
    def total_target_allocation(self):
        """Calcula el total de la asignación objetivo."""
        return (self.liquidez_target + self.usa_target +
                self.argentina_target + self.emerging_target)

    def is_valid_allocation(self):
        """Verifica si la asignación suma 100%."""
        return abs(self.total_target_allocation - 100) < 0.01

    @classmethod
    def get_active_parameters(cls):
        """Obtiene los parámetros activos."""
        return cls.objects.filter(is_active=True).first()

    def get_target_weights_dict(self):
        """Retorna los pesos objetivo como diccionario."""
        return {
            'liquidez': float(self.liquidez_target),
            'usa': float(self.usa_target),
            'argentina': float(self.argentina_target),
            'emerging': float(self.emerging_target)
        }


class Alert(models.Model):
    """Modelo para almacenar alertas del portafolio."""

    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    ALERT_TYPES = [
        ('concentracion_excesiva', 'Concentración Excesiva'),
        ('liquidez_excesiva', 'Liquidez Excesiva'),
        ('exposicion_pais', 'Exposición País'),
        ('exposicion_sector', 'Exposición Sector'),
        ('perdida_significativa', 'Pérdida Significativa'),
    ]

    tipo = models.CharField(max_length=50, choices=ALERT_TYPES, help_text="Tipo de alerta")
    mensaje = models.TextField(help_text="Mensaje descriptivo de la alerta")
    severidad = models.CharField(max_length=10, choices=SEVERITY_CHOICES, help_text="Severidad de la alerta")
    valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                               help_text="Valor numérico relacionado con la alerta")

    # Campos opcionales para contexto adicional
    simbolo = models.CharField(max_length=20, null=True, blank=True, help_text="Símbolo del activo relacionado")
    sector = models.CharField(max_length=100, null=True, blank=True, help_text="Sector relacionado")
    pais = models.CharField(max_length=100, null=True, blank=True, help_text="País relacionado")

    # Estado de la alerta
    is_active = models.BooleanField(default=True, help_text="Si la alerta está activa")
    is_acknowledged = models.BooleanField(default=False, help_text="Si la alerta ha sido reconocida")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True, help_text="Fecha de reconocimiento")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"

    def __str__(self):
        return f"[{self.severidad.upper()}] {self.tipo}: {self.mensaje[:50]}..."

    def acknowledge(self):
        """Marca la alerta como reconocida."""
        self.is_acknowledged = True
        self.acknowledged_at = timezone.now()
        self.save()

    @classmethod
    def get_active_alerts(cls):
        """Obtiene todas las alertas activas."""
        return cls.objects.filter(is_active=True)

    @classmethod
    def get_alerts_by_severity(cls, severity):
        """Obtiene alertas filtradas por severidad."""
        return cls.objects.filter(severidad=severity, is_active=True)


class SensitiveActionAudit(models.Model):
    """Auditoria persistente de acciones sensibles ejecutadas desde la app."""

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("denied", "Denied"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sensitive_action_audits",
    )
    action = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Sensitive action audit"
        verbose_name_plural = "Sensitive action audits"

    def __str__(self):
        username = self.user.username if self.user else "anonymous"
        return f"{self.action} [{self.status}] by {username}"


class IncrementalProposalSnapshot(models.Model):
    """Snapshot persistente de una propuesta incremental elegida desde Planeacion."""

    DECISION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("deferred", "Deferred"),
        ("rejected", "Rejected"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incremental_proposal_snapshots",
    )
    source_key = models.CharField(max_length=64)
    source_label = models.CharField(max_length=120)
    proposal_key = models.CharField(max_length=64)
    proposal_label = models.CharField(max_length=160)
    selected_context = models.CharField(max_length=160, blank=True, default="")
    capital_amount = models.DecimalField(max_digits=18, decimal_places=2)
    comparison_score = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    purchase_plan = models.JSONField(default=list, blank=True)
    simulation_delta = models.JSONField(default=dict, blank=True)
    simulation_interpretation = models.TextField(blank=True, default="")
    explanation = models.TextField(blank=True, default="")
    is_tracking_baseline = models.BooleanField(default=False)
    manual_decision_status = models.CharField(max_length=16, choices=DECISION_STATUS_CHOICES, default="pending")
    manual_decision_note = models.CharField(max_length=240, blank=True, default="")
    manual_decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["source_key", "created_at"]),
        ]
        verbose_name = "Incremental proposal snapshot"
        verbose_name_plural = "Incremental proposal snapshots"

    def __str__(self):
        return f"{self.user_id}:{self.proposal_label} ({self.source_key})"


class BenchmarkSnapshot(models.Model):
    """Serie historica de benchmarks externos persistida localmente."""

    INTERVAL_CHOICES = [
        ("daily", "Daily"),
        ("weekly_adjusted", "Weekly Adjusted"),
    ]

    benchmark_key = models.CharField(max_length=50)
    symbol = models.CharField(max_length=20)
    source = models.CharField(max_length=32, default="alpha_vantage")
    interval = models.CharField(max_length=24, choices=INTERVAL_CHOICES, default="daily")
    fecha = models.DateField()
    close = models.DecimalField(max_digits=18, decimal_places=6)
    adjusted_close = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "benchmark_key"]
        indexes = [
            models.Index(fields=["benchmark_key", "interval", "fecha"]),
            models.Index(fields=["symbol", "interval", "fecha"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["benchmark_key", "source", "interval", "fecha"],
                name="unique_benchmark_snapshot_per_interval",
            )
        ]

    def __str__(self):
        return f"{self.benchmark_key} {self.interval} {self.fecha} ({self.source})"


class MacroSeriesSnapshot(models.Model):
    """Serie macro local persistida para contexto analitico del portafolio."""

    series_key = models.CharField(max_length=50)
    source = models.CharField(max_length=32)
    external_id = models.CharField(max_length=64)
    frequency = models.CharField(max_length=16)
    fecha = models.DateField()
    value = models.DecimalField(max_digits=18, decimal_places=6)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "series_key"]
        indexes = [
            models.Index(fields=["series_key", "fecha"]),
            models.Index(fields=["source", "external_id", "fecha"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["series_key", "source", "fecha"],
                name="unique_macro_series_snapshot_per_day",
            )
        ]

    def __str__(self):
        return f"{self.series_key} {self.fecha} ({self.source})"
