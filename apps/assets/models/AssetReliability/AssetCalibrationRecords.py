from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetCalibrationRecord(TenantNumbered):
    """
    Metrological calibration and instrument compliance tracking record [ACAL-].
    Monitors NIST/ISO reference standards, As-Found vs. As-Left measurement deviations,
    allowable error tolerances, Pass/Fail certification, and digital certificate archival.
    """

    NUMBER_PREFIX = "ACAL"

    TOLERANCE_UNIT_CHOICES = [
        ("percent_span", "% of Span"),
        ("engineering_units", "Direct Engineering Units"),
        ("celsius", "°C"),
        ("psi", "psi"),
        ("bar", "bar"),
        ("volts", "V"),
        ("milliamps", "mA"),
    ]

    CALIBRATION_RESULT_CHOICES = [
        ("pass", "Pass (Within Tolerance)"),
        ("pass_with_adjustment", "Pass with Adjustment (Re-zeroed / Aligned)"),
        ("fail_out_of_tolerance", "Fail (Out of Tolerance)"),
        ("quarantined", "Quarantined (Unusable / Out of Service)"),
    ]

    STATUS_CHOICES = [
        ("valid", "Valid / Active"),
        ("expiring_soon", "Expiring Within 30 Days"),
        ("expired", "Expired (Overdue for Recalibration)"),
        ("voided", "Voided"),
    ]

    CALIBRATION_RESULT_CSS = {
        "pass": "badge-green",
        "pass_with_adjustment": "badge-info",
        "fail_out_of_tolerance": "badge-red",
        "quarantined": "badge-red",
    }

    STATUS_CSS = {
        "valid": "badge-green",
        "expiring_soon": "badge-amber",
        "expired": "badge-red",
        "voided": "badge-muted",
    }

    TOLERANCE_UNIT_CSS = {
        "percent_span": "badge-info",
        "engineering_units": "badge-slate",
        "celsius": "badge-amber",
        "psi": "badge-info",
        "bar": "badge-info",
        "volts": "badge-amber",
        "milliamps": "badge-amber",
    }

    instrument_tag = models.CharField(
        max_length=100,
        help_text="Gauge tag or instrument loop identifier",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibration_records",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibration_records",
        help_text="Operational equipment record",
    )
    calibrated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_asset_calibrations",
        help_text="Internal metrologist or instrument technician",
    )
    service_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_asset_calibrations",
        help_text="External ISO 17025 accredited calibration lab / OEM",
    )
    calibration_date = models.DateField(
        default=timezone.now,
        help_text="Date calibration was completed",
    )
    calibration_frequency_days = models.PositiveIntegerField(
        default=365,
        help_text="Calibration recurrence cycle in days",
    )
    next_due_date = models.DateField(
        help_text="Next scheduled calibration deadline",
    )
    reference_standard_used = models.CharField(
        max_length=255,
        help_text="Traceable standard instrument, serial number, and cert ID",
    )
    traceability_certificate_no = models.CharField(
        max_length=100,
        blank=True,
        help_text="National metrology traceability standard certificate number",
    )
    setpoint_nominal = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Nominal calibration setpoint / target reference standard",
    )
    allowable_tolerance = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.5000"),
        help_text="Maximum permissible error (+/- threshold)",
    )
    tolerance_unit = models.CharField(
        max_length=20,
        choices=TOLERANCE_UNIT_CHOICES,
        default="percent_span",
    )
    as_found_reading = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Initial measured value prior to any adjustment",
    )
    as_left_reading = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Final measured value following calibration / adjustment",
    )
    as_found_error = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Calculated error: As-Found - Setpoint",
    )
    as_left_error = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Calculated error: As-Left - Setpoint",
    )
    calibration_result = models.CharField(
        max_length=24,
        choices=CALIBRATION_RESULT_CHOICES,
        default="pass",
    )
    certificate_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Calibration report or certificate document identifier",
    )
    certificate_expiry = models.DateField(
        null=True,
        blank=True,
    )
    certificate_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_calibration_records",
        help_text="Digital calibration certificate scan / PDF",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="valid",
    )
    notes = models.TextField(
        blank=True,
        help_text="Calibration procedure, ambient conditions, or repair notes",
    )

    class Meta:
        ordering = ["-calibration_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_acal_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "next_due_date"], name="idx_acal_ten_ndue"),
            models.Index(fields=["tenant", "calibration_result"], name="idx_acal_ten_res"),
            models.Index(fields=["tenant", "status"], name="idx_acal_ten_stat"),
            models.Index(fields=["tenant", "instrument_tag"], name="idx_acal_ten_tag"),
            models.Index(fields=["tenant", "calibration_date"], name="idx_acal_ten_cdate"),
        ]

    def __str__(self):
        return f"{self.number} ({self.instrument_tag}) - {self.get_calibration_result_display()}"

    def calculate_errors(self):
        if self.setpoint_nominal is not None:
            if self.as_found_reading is not None:
                self.as_found_error = self.as_found_reading - self.setpoint_nominal
            if self.as_left_reading is not None:
                self.as_left_error = self.as_left_reading - self.setpoint_nominal

        # Compute next due date if missing
        if not self.next_due_date and self.calibration_date:
            days = self.calibration_frequency_days or 365
            self.next_due_date = self.calibration_date + timedelta(days=days)

        # Status determination based on next_due_date
        today = timezone.now().date()
        if self.status != "voided":
            if self.next_due_date and self.next_due_date < today:
                self.status = "expired"
            elif self.next_due_date and self.next_due_date <= today + timedelta(days=30):
                self.status = "expiring_soon"
            else:
                self.status = "valid"

        # Tolerance validation
        if self.as_left_error is not None and self.allowable_tolerance is not None:
            if abs(self.as_left_error) > self.allowable_tolerance:
                if self.calibration_result != "quarantined":
                    self.calibration_result = "fail_out_of_tolerance"
            elif self.as_found_error is not None and abs(self.as_found_error) > self.allowable_tolerance:
                if self.calibration_result not in ["quarantined", "fail_out_of_tolerance"]:
                    self.calibration_result = "pass_with_adjustment"

    def save(self, *args, **kwargs):
        self.calculate_errors()
        return super().save(*args, **kwargs)

    @property
    def calibration_result_css(self):
        return self.CALIBRATION_RESULT_CSS.get(self.calibration_result, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def tolerance_unit_css(self):
        return self.TOLERANCE_UNIT_CSS.get(self.tolerance_unit, "badge-slate")
