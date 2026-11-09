from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetTelemetryReading(TenantNumbered):
    """
    IoT sensor, SCADA historian, and condition telemetry ingestion record [ATEL-].
    Monitors vibration, temperature, ultrasound, pressure, and motor current against baseline
    operating limits, evaluating deviations and automated anomaly detection flags.
    """

    NUMBER_PREFIX = "ATEL"

    SOURCE_CHOICES = [
        ("iot_sensor", "IoT Edge Sensor"),
        ("scada_historian", "SCADA / Historian Ingestion"),
        ("manual_gauge", "Manual Dial / Gauge Reading"),
        ("handheld_tester", "Handheld Condition Tester"),
        ("analyst_entry", "Reliability Analyst Entry"),
    ]

    METRIC_TYPE_CHOICES = [
        ("vibration_velocity_rms", "Vibration Velocity RMS (mm/s)"),
        ("vibration_peak_accel", "Vibration Peak Acceleration (g)"),
        ("bearing_temperature", "Bearing Operating Temperature (°C)"),
        ("acoustic_ultrasound", "Acoustic Ultrasound (dBµV)"),
        ("operating_pressure", "Hydraulic / Line Pressure (bar)"),
        ("oil_dielectric_viscosity", "Oil Dielectric / Kinematic Viscosity (cSt)"),
        ("motor_current_amperage", "Motor Current Amperage (A)"),
        ("ambient_temperature", "Ambient Temperature (°C)"),
    ]

    METRIC_UNIT_CHOICES = [
        ("mm_per_s", "mm/s"),
        ("g_force", "g"),
        ("celsius", "°C"),
        ("fahrenheit", "°F"),
        ("decibel_uv", "dBµV"),
        ("bar", "bar"),
        ("psi", "psi"),
        ("amperes", "A"),
        ("viscosity_cst", "cSt"),
    ]

    THRESHOLD_STATUS_CHOICES = [
        ("normal", "Normal (In Specification)"),
        ("warning", "Warning (Elevated Alarm)"),
        ("critical", "Critical (Exceeds Safety Threshold)"),
        ("anomaly_detected", "Statistical Anomaly Detected"),
    ]

    THRESHOLD_STATUS_CSS = {
        "normal": "badge-green",
        "warning": "badge-amber",
        "critical": "badge-red",
        "anomaly_detected": "badge-red",
    }

    SOURCE_CSS = {
        "iot_sensor": "badge-info",
        "scada_historian": "badge-slate",
        "manual_gauge": "badge-muted",
        "handheld_tester": "badge-info",
        "analyst_entry": "badge-slate",
    }

    METRIC_TYPE_CSS = {
        "vibration_velocity_rms": "badge-amber",
        "vibration_peak_accel": "badge-amber",
        "bearing_temperature": "badge-red",
        "acoustic_ultrasound": "badge-info",
        "operating_pressure": "badge-info",
        "oil_dielectric_viscosity": "badge-slate",
        "motor_current_amperage": "badge-amber",
        "ambient_temperature": "badge-slate",
    }

    sensor_identifier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Unique hardware sensor tag or transmitter serial",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telemetry_readings",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telemetry_readings",
        help_text="Operational machinery or equipment record",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_asset_telemetry_readings",
        help_text="User who recorded or ingested telemetry",
    )
    recorded_at = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp of sensor capture",
    )
    source = models.CharField(
        max_length=24,
        choices=SOURCE_CHOICES,
        default="iot_sensor",
    )
    metric_type = models.CharField(
        max_length=32,
        choices=METRIC_TYPE_CHOICES,
        default="vibration_velocity_rms",
    )
    metric_unit = models.CharField(
        max_length=20,
        choices=METRIC_UNIT_CHOICES,
        default="mm_per_s",
    )
    reading_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        help_text="Measured physical reading value",
    )
    baseline_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Expected baseline operating value",
    )
    deviation_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Calculated percentage deviation from baseline",
    )
    threshold_status = models.CharField(
        max_length=20,
        choices=THRESHOLD_STATUS_CHOICES,
        default="normal",
    )
    is_anomaly = models.BooleanField(
        default=False,
        help_text="Flags reading as a recognized pattern anomaly",
    )
    anomaly_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Anomaly classification confidence percentage (0-100)",
    )
    alert_notes = models.TextField(
        blank=True,
        help_text="Diagnostic commentary or anomaly alarm text",
    )
    triggered_maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggering_telemetry_readings",
        help_text="Corrective maintenance request generated from this reading",
    )

    class Meta:
        ordering = ["-recorded_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_atel_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "recorded_at"], name="idx_atel_ten_time"),
            models.Index(fields=["tenant", "threshold_status"], name="idx_atel_ten_stat"),
            models.Index(fields=["tenant", "metric_type"], name="idx_atel_ten_type"),
            models.Index(fields=["tenant", "is_anomaly"], name="idx_atel_ten_anom"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_metric_type_display()}: {self.reading_value} {self.metric_unit})"

    def calculate_deviation_and_thresholds(self):
        if self.reading_value is not None and self.baseline_value and self.baseline_value != Decimal("0"):
            dev = ((self.reading_value - self.baseline_value) / self.baseline_value) * Decimal("100")
            self.deviation_percentage = round(dev, 2)
            abs_dev = abs(self.deviation_percentage)
            if self.is_anomaly:
                self.threshold_status = "anomaly_detected"
            elif abs_dev >= Decimal("50"):
                self.threshold_status = "critical"
            elif abs_dev >= Decimal("20"):
                self.threshold_status = "warning"
            else:
                self.threshold_status = "normal"
        elif self.is_anomaly:
            self.threshold_status = "anomaly_detected"

    def save(self, *args, **kwargs):
        self.calculate_deviation_and_thresholds()
        return super().save(*args, **kwargs)

    @property
    def threshold_status_css(self):
        return self.THRESHOLD_STATUS_CSS.get(self.threshold_status, "badge-slate")

    @property
    def source_css(self):
        return self.SOURCE_CSS.get(self.source, "badge-slate")

    @property
    def metric_type_css(self):
        return self.METRIC_TYPE_CSS.get(self.metric_type, "badge-slate")
