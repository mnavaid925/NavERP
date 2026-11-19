from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class CalibrationGage(TenantNumbered):
    NUMBER_PREFIX = "QGAG"

    GAGE_TYPE_CHOICES = (
        ("caliper_micrometer", "Caliper / Micrometer / Depth Gage"),
        ("pressure_vacuum", "Pressure / Vacuum Gage / Transducer"),
        ("temperature_humidity", "Temperature Sensor / RTD / Hygrometer"),
        ("electrical_multimeter", "Multimeter / Oscilloscope / Power Meter"),
        ("torque_force", "Torque Wrench / Load Cell / Force Gage"),
        ("optical_comparator", "Optical Comparator / Vision System"),
        ("cmm_coordinate", "CMM Coordinate Measuring Machine"),
        ("gauge_block_pin", "Gage Blocks / Pin & Plug Gages"),
        ("mass_balance", "Mass Standard / Precision Analytical Balance"),
        ("flow_level", "Flow Meter / Level Transmitter"),
        ("other_instrument", "Other Specialized Test Equipment"),
    )

    CRITICALITY_CHOICES = (
        ("critical", "Critical (Direct Product / CTQ)"),
        ("major", "Major (Process Control)"),
        ("minor", "Minor (Reference / General)"),
    )

    STATUS_CHOICES = (
        ("active_in_service", "Active / In-Service"),
        ("in_calibration", "In Calibration"),
        ("pending_calibration", "Pending Calibration"),
        ("past_due", "Past Due / Overdue"),
        ("quarantined_oot", "Quarantined (Out-of-Tolerance)"),
        ("out_of_service", "Out of Service / Maintenance"),
        ("retired", "Retired / Decommissioned"),
    )

    GAGE_TYPE_CSS = {
        "caliper_micrometer": "badge-info",
        "pressure_vacuum": "badge-slate",
        "temperature_humidity": "badge-amber",
        "electrical_multimeter": "badge-info",
        "torque_force": "badge-slate",
        "optical_comparator": "badge-slate",
        "cmm_coordinate": "badge-info",
        "gauge_block_pin": "badge-slate",
        "mass_balance": "badge-info",
        "flow_level": "badge-slate",
        "other_instrument": "badge-muted",
    }

    CRITICALITY_CSS = {
        "critical": "badge-red",
        "major": "badge-amber",
        "minor": "badge-muted",
    }

    STATUS_CSS = {
        "active_in_service": "badge-green",
        "in_calibration": "badge-info",
        "pending_calibration": "badge-amber",
        "past_due": "badge-red",
        "quarantined_oot": "badge-red",
        "out_of_service": "badge-muted",
        "retired": "badge-slate",
    }

    gage_id = models.CharField(max_length=64, db_index=True, help_text="Plant tool tag / barcode ID")
    name = models.CharField(max_length=150, help_text="Descriptive gage name e.g. 0-150mm Digital Caliper")
    gage_type = models.CharField(max_length=32, choices=GAGE_TYPE_CHOICES, default="caliper_micrometer", db_index=True)
    criticality = models.CharField(max_length=20, choices=CRITICALITY_CHOICES, default="major", db_index=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="active_in_service", db_index=True)

    manufacturer = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, db_index=True)

    measurement_range = models.CharField(max_length=100, blank=True, help_text="e.g. 0 to 150 mm / 0 to 100 psi")
    resolution = models.CharField(max_length=64, blank=True, help_text="e.g. 0.01 mm / 0.0005 in")
    accuracy_spec = models.CharField(max_length=120, blank=True, help_text="e.g. +/- 0.02 mm / Class 1")
    max_permissible_error = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0200"),
        help_text="Maximum Permissible Error (MPE) in primary engineering units"
    )
    engineering_unit = models.CharField(max_length=32, default="mm", help_text="mm, inch, psi, bar, deg_c, v, a, nm")

    is_reference_standard = models.BooleanField(
        default=False,
        help_text="Designated primary/secondary calibration standard used to calibrate other working gages"
    )
    nist_traceability_number = models.CharField(
        max_length=100, blank=True,
        help_text="NIST / National metrology institute test report reference"
    )
    reference_standard_parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subordinate_gages"
    )

    asset_link = models.ForeignKey(
        "scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="calibration_gages"
    )
    work_center = models.ForeignKey(
        "scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_gages"
    )
    department = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_gages"
    )
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_gages"
    )
    storage_location = models.CharField(
        max_length=120, blank=True, help_text="Crib room, drawer, cabinet, or bench coordinate"
    )

    calibration_interval_days = models.PositiveIntegerField(
        default=365, help_text="Scheduled interval between routine recalibrations in days"
    )
    last_calibration_date = models.DateField(null=True, blank=True)
    next_calibration_due = models.DateField(null=True, blank=True, db_index=True)
    last_calibration_result = models.CharField(max_length=32, blank=True, default="")

    sop_document = models.ForeignKey(
        "quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="calibrated_gages"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Calibration Gage / Instrument"
        verbose_name_plural = "Calibration Gages & Instruments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qgag_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "gage_id"], name="quality_qgag_ten_gid_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qgag_ten_status"),
            models.Index(fields=["tenant", "gage_type"], name="idx_qgag_ten_type"),
            models.Index(fields=["tenant", "next_calibration_due"], name="idx_qgag_ten_due"),
            models.Index(fields=["tenant", "is_reference_standard"], name="idx_qgag_ten_std"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qgag_ten_created"),
        ]

    def __str__(self):
        return f"{self.gage_id} — {self.name} ({self.get_status_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def criticality_css(self):
        return self.CRITICALITY_CSS.get(self.criticality, "badge-slate")

    @property
    def gage_type_css(self):
        return self.GAGE_TYPE_CSS.get(self.gage_type, "badge-info")
