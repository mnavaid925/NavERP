from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered

STREAM_TO_TELEMETRY_METRIC_MAP = {
    "runtime_hours": ("motor_current_amperage", "amperes"),
    "cycle_count": ("vibration_peak_accel", "g_force"),
    "energy_kwh": ("motor_current_amperage", "amperes"),
}

FALLBACK_11_7_METRIC_DEFAULT_UNIT = {
    "vibration_velocity_rms": "mm_per_s",
    "vibration_peak_accel": "g_force",
    "bearing_temperature": "celsius",
    "acoustic_ultrasound": "decibel_uv",
    "operating_pressure": "psi",
    "oil_dielectric_viscosity": "viscosity_cst",
    "motor_current_amperage": "amperes",
    "ambient_temperature": "celsius",
}

UNIT_FALLBACK_MAP = {
    "hours": "amperes",
    "cycles": "g_force",
    "kwh": "amperes",
}


class AssetTelemetryStream(TenantNumbered):
    """
    IoT, SCADA, OPC-UA, MQTT, and historian tag stream definition bound to an
    Asset Integration Connector and normalized into AssetTelemetryReading (11.7).
    """

    NUMBER_PREFIX = "ATMS"

    STREAM_PROTOCOL_CHOICES = [
        ("opc_ua_node", "OPC-UA Node"),
        ("mqtt_topic", "MQTT Topic"),
        ("modbus_register", "Modbus Register"),
        ("pi_tag", "OSIsoft PI Tag"),
        ("bacnet_object", "BACnet Object"),
        ("rest_webhook_key", "REST Webhook Payload Key"),
    ]

    METRIC_TYPE_CHOICES = [
        ("vibration_velocity_rms", "Vibration Velocity (RMS)"),
        ("vibration_peak_accel", "Vibration Peak Acceleration"),
        ("bearing_temperature", "Bearing Temperature"),
        ("acoustic_ultrasound", "Acoustic Ultrasound"),
        ("operating_pressure", "Operating Pressure"),
        ("oil_dielectric_viscosity", "Oil Dielectric / Viscosity"),
        ("motor_current_amperage", "Motor Current (Amperage)"),
        ("ambient_temperature", "Ambient Temperature"),
        ("runtime_hours", "Operating Runtime Hours"),
        ("cycle_count", "Equipment Cycle Count"),
        ("energy_kwh", "Energy Consumption (kWh)"),
    ]

    METRIC_UNIT_CHOICES = [
        ("mm_per_s", "mm/s"),
        ("g_force", "g"),
        ("celsius", "deg C"),
        ("fahrenheit", "deg F"),
        ("decibel_uv", "dBuV"),
        ("bar", "bar"),
        ("psi", "psi"),
        ("amperes", "A"),
        ("viscosity_cst", "cSt"),
        ("hours", "hrs"),
        ("cycles", "cycles"),
        ("kwh", "kWh"),
    ]

    INGESTION_MODE_CHOICES = [
        ("streaming_pubsub", "Streaming Pub/Sub"),
        ("polling", "Scheduled Polling"),
        ("edge_batch_store", "Edge Store-and-Forward"),
        ("manual_sample", "Manual Sample Capture"),
    ]

    STREAM_STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("faulted", "Faulted"),
        ("decommissioned", "Decommissioned"),
    ]

    STREAM_STATUS_BADGE_MAP = {
        "active": "badge-green",
        "paused": "badge-amber",
        "faulted": "badge-red",
        "decommissioned": "badge-muted",
    }

    connector = models.ForeignKey(
        "assets.AssetIntegrationConnector",
        on_delete=models.PROTECT,
        related_name="telemetry_streams",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_telemetry_streams",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_telemetry_streams",
    )

    tag_address = models.CharField(max_length=160)
    stream_name = models.CharField(max_length=160)
    stream_protocol = models.CharField(
        max_length=24, choices=STREAM_PROTOCOL_CHOICES, default="opc_ua_node"
    )
    metric_type = models.CharField(
        max_length=32, choices=METRIC_TYPE_CHOICES, default="bearing_temperature"
    )
    metric_unit = models.CharField(
        max_length=20, choices=METRIC_UNIT_CHOICES, default="celsius"
    )
    ingestion_mode = models.CharField(
        max_length=24, choices=INGESTION_MODE_CHOICES, default="polling"
    )

    polling_interval_seconds = models.PositiveIntegerField(default=60)
    deadband_delta = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0000")
    )
    scale_factor = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("1.000000")
    )
    offset_value = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("0.0000")
    )
    baseline_value = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    warning_threshold = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    critical_threshold = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    auto_trigger_maintenance = models.BooleanField(default=True)
    stream_status = models.CharField(
        max_length=20, choices=STREAM_STATUS_CHOICES, default="active"
    )

    last_ingested_value = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False
    )
    last_ingested_at = models.DateTimeField(null=True, blank=True, editable=False)
    readings_ingested_count = models.PositiveIntegerField(default=0, editable=False)
    last_telemetry_reading = models.ForeignKey(
        "assets.AssetTelemetryReading",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="source_integration_streams",
    )
    latest_maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="triggered_by_streams",
    )

    steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stewarded_telemetry_streams",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Asset Telemetry Stream"
        verbose_name_plural = "Asset Telemetry Streams"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_atms_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "operational_asset"],
                name="idx_atms_ten_asset",
            ),
            models.Index(
                fields=["tenant", "connector"],
                name="idx_atms_ten_conn",
            ),
            models.Index(
                fields=["tenant", "stream_status"],
                name="idx_atms_ten_stat",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.stream_name}"

    @property
    def status_badge_class(self):
        return self.STREAM_STATUS_BADGE_MAP.get(self.stream_status, "badge-slate")

    def resolve_telemetry_metric_and_unit(self):
        """Map 11.15 stream metric/unit choices cleanly onto 11.7 AssetTelemetryReading choices."""
        if self.metric_type in STREAM_TO_TELEMETRY_METRIC_MAP:
            mapped_type, default_unit = STREAM_TO_TELEMETRY_METRIC_MAP[self.metric_type]
            note = (
                f"Mapped from stream {self.number} tag '{self.tag_address}' "
                f"({self.get_metric_type_display()} / {self.get_metric_unit_display()})."
            )
            return mapped_type, default_unit, note

        mapped_type = (
            self.metric_type
            if self.metric_type in FALLBACK_11_7_METRIC_DEFAULT_UNIT
            else "bearing_temperature"
        )
        if self.metric_unit in UNIT_FALLBACK_MAP:
            mapped_unit = FALLBACK_11_7_METRIC_DEFAULT_UNIT.get(mapped_type, "celsius")
        elif self.metric_unit in {
            "mm_per_s",
            "g_force",
            "celsius",
            "fahrenheit",
            "decibel_uv",
            "bar",
            "psi",
            "amperes",
            "viscosity_cst",
        }:
            mapped_unit = self.metric_unit
        else:
            mapped_unit = FALLBACK_11_7_METRIC_DEFAULT_UNIT.get(mapped_type, "celsius")
        note = (
            f"Ingested via stream {self.number} tag '{self.tag_address}' "
            f"({self.get_stream_protocol_display()})."
        )
        return mapped_type, mapped_unit, note

    def evaluate_reading_status(self, normalized_value):
        """Return AssetTelemetryReading threshold status from stream warning/critical limits."""
        if (
            self.critical_threshold is not None
            and normalized_value >= self.critical_threshold
        ):
            return "critical"
        if (
            self.warning_threshold is not None
            and normalized_value >= self.warning_threshold
        ):
            return "warning"
        return "normal"

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.polling_interval_seconds is not None
            and self.polling_interval_seconds < 1
        ):
            errors["polling_interval_seconds"] = (
                "Polling interval must be at least 1 second."
            )
        if self.scale_factor is not None and self.scale_factor == Decimal("0"):
            errors["scale_factor"] = "Scale factor cannot be zero."
        if self.deadband_delta is not None and self.deadband_delta < Decimal("0"):
            errors["deadband_delta"] = "Deadband delta cannot be negative."
        if (
            self.warning_threshold is not None
            and self.critical_threshold is not None
            and self.critical_threshold < self.warning_threshold
        ):
            errors["critical_threshold"] = (
                "Critical threshold must be greater than or equal to warning threshold."
            )
        if errors:
            raise ValidationError(errors)
