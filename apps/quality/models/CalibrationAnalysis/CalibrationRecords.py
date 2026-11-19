from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CalibrationRecord(TenantNumbered):
    NUMBER_PREFIX = "QCAL"

    CALIBRATION_TYPE_CHOICES = (
        ("internal_metrology", "Internal Metrology Lab"),
        ("external_accredited", "External ISO/IEC 17025 Lab"),
        ("oem_factory", "OEM Factory Calibration"),
        ("on_site_field", "On-Site Field Verification"),
    )

    CONDITION_CHOICES = (
        ("in_tolerance", "In-Tolerance (Conforming)"),
        ("out_of_tolerance", "Out-of-Tolerance (Non-Conforming)"),
        ("damaged_malfunctioning", "Damaged / Malfunctioning"),
        ("not_operational", "Not Operational / Inoperable"),
        ("new_first_calibration", "New / Initial Calibration"),
    )

    OVERALL_RESULT_CHOICES = (
        ("pass", "Pass (Fully Conforming)"),
        ("pass_with_limitations", "Pass with Limited Range / De-rated"),
        ("fail_out_of_tolerance", "Fail (Out-of-Tolerance)"),
        ("fail_unrepairable", "Fail (Scrap / Unrepairable)"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft / Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed / Reviewed"),
        ("rejected", "Rejected / Invalid"),
    )

    OVERALL_RESULT_CSS = {
        "pass": "badge-green",
        "pass_with_limitations": "badge-amber",
        "fail_out_of_tolerance": "badge-red",
        "fail_unrepairable": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-green",
        "rejected": "badge-red",
    }

    CALIBRATION_TYPE_CSS = {
        "internal_metrology": "badge-info",
        "external_accredited": "badge-slate",
        "oem_factory": "badge-slate",
        "on_site_field": "badge-info",
    }

    gage = models.ForeignKey(
        "quality.CalibrationGage", on_delete=models.CASCADE, related_name="calibration_records"
    )
    calibration_date = models.DateField(default=timezone.now, db_index=True)
    calibration_type = models.CharField(
        max_length=24, choices=CALIBRATION_TYPE_CHOICES, default="internal_metrology", db_index=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed", db_index=True)

    service_vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="calibrations_performed"
    )
    certificate_number = models.CharField(max_length=100, blank=True, db_index=True)

    as_found_condition = models.CharField(
        max_length=24, choices=CONDITION_CHOICES, default="in_tolerance", db_index=True
    )
    as_left_condition = models.CharField(
        max_length=24, choices=CONDITION_CHOICES, default="in_tolerance", db_index=True
    )
    overall_result = models.CharField(
        max_length=24, choices=OVERALL_RESULT_CHOICES, default="pass", db_index=True
    )

    ambient_temperature_c = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("20.00"),
        help_text="Lab temperature e.g. 20.0 +/- 1.0 deg C"
    )
    ambient_relative_humidity = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("45.00"),
        help_text="Lab relative humidity %"
    )

    expanded_uncertainty = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0020"),
        help_text="Expanded measurement uncertainty (U, k=2 95% confidence)"
    )
    test_uncertainty_ratio = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("4.00"),
        help_text="TUR ratio (e.g. 4.0:1)"
    )
    max_observed_error = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0050"),
        help_text="Maximum deviation observed across all test points"
    )
    guardband_applied = models.BooleanField(
        default=True,
        help_text="ILAC-G8 / ISO 14253-1 decision rule guardband applied to acceptance"
    )

    test_points_data = models.JSONField(
        default=list, blank=True,
        help_text="Array of calibration points: nominal, as_found, error, as_left, limit"
    )
    standards_used = models.ManyToManyField(
        "quality.CalibrationGage", blank=True, related_name="calibrations_verified"
    )
    standard_traceability_notes = models.TextField(
        blank=True, help_text="Summary of reference standards, certificates, and expiration dates"
    )

    technician_name = models.CharField(
        max_length=120, blank=True, help_text="Name of internal metrologist or vendor cal technician"
    )
    calibrated_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="executed_calibrations"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_calibrations"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-calibration_date", "-created_at"]
        verbose_name = "Calibration Event / Record"
        verbose_name_plural = "Calibration Events & Records"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcal_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "gage"], name="idx_qcal_ten_gage"),
            models.Index(fields=["tenant", "overall_result"], name="idx_qcal_ten_result"),
            models.Index(fields=["tenant", "calibration_date"], name="idx_qcal_ten_date"),
            models.Index(fields=["tenant", "status"], name="idx_qcal_ten_status"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcal_ten_created"),
        ]

    def __str__(self):
        gage_label = self.gage.gage_id if "gage" in getattr(self._state, "fields_cache", {}) else f"Gage #{self.gage_id}"
        return f"{self.number} — {gage_label} ({self.get_overall_result_display()})"

    @property
    def result_css(self):
        return self.OVERALL_RESULT_CSS.get(self.overall_result, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def calibration_type_css(self):
        return self.CALIBRATION_TYPE_CSS.get(self.calibration_type, "badge-slate")
