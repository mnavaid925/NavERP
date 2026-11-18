from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ProcessParameterLog(TenantNumbered):
    NUMBER_PREFIX = "QPAR"

    PARAMETER_CATEGORY_CHOICES = [
        ("temperature", "Thermal / Temperature (°C)"),
        ("pressure", "Hydraulic / Pneumatic Pressure (bar)"),
        ("speed_feed", "Spindle Speed / Feed Rate (RPM / mm/min)"),
        ("torque", "Fastener Torque / Clamping Force (Nm)"),
        ("ph_chemical", "Chemical Concentration / pH"),
        ("humidity", "Cleanroom Humidity / Environmental (%RH)"),
        ("dimensional_thickness", "In-Line Thickness / Dimension (mm)"),
        ("voltage_current", "Electrical Voltage / Current (V / A)"),
        ("cycle_time", "Process Cycle Time (sec)"),
        ("other", "Other Critical Parameter"),
    ]

    EXCURSION_STATUS_CHOICES = [
        ("normal", "Normal (In Control & In Spec)"),
        ("warning_pre_control", "Warning (Pre-Control Zone / Trend)"),
        ("out_of_control", "Out of Control (SPC 3-Sigma Rule Violation)"),
        ("out_of_spec", "Out of Spec (Exceeded USL/LSL Tolerance)"),
    ]

    CONTAINMENT_ACTION_CHOICES = [
        ("none", "None / In Control"),
        ("machine_parameter_adjusted", "Machine Parameter Adjusted"),
        ("machine_paused", "Machine Paused / Maintenance Alerted"),
        ("wip_quarantined", "WIP Material Quarantined"),
        ("supervisor_escalated", "Supervisor / Engineer Escalated"),
        ("ncr_initiated", "Formal NCR Initiated"),
    ]

    PARAMETER_CATEGORY_CSS = {
        "temperature": "badge-red",
        "pressure": "badge-amber",
        "speed_feed": "badge-info",
        "torque": "badge-slate",
        "ph_chemical": "badge-info",
        "humidity": "badge-slate",
        "dimensional_thickness": "badge-info",
        "voltage_current": "badge-amber",
        "cycle_time": "badge-slate",
        "other": "badge-muted",
    }

    EXCURSION_STATUS_CSS = {
        "normal": "badge-green",
        "warning_pre_control": "badge-amber",
        "out_of_control": "badge-amber",
        "out_of_spec": "badge-red",
    }

    CONTAINMENT_ACTION_CSS = {
        "none": "badge-slate",
        "machine_parameter_adjusted": "badge-info",
        "machine_paused": "badge-amber",
        "wip_quarantined": "badge-red",
        "supervisor_escalated": "badge-amber",
        "ncr_initiated": "badge-red",
    }

    parameter_name = models.CharField(max_length=150)
    parameter_category = models.CharField(
        max_length=30,
        choices=PARAMETER_CATEGORY_CHOICES,
        default="temperature",
        db_index=True,
    )
    unit_of_measure = models.CharField(
        max_length=32,
        help_text="e.g. °C, bar, RPM, Nm, mm, V, sec",
    )

    work_center_code = models.CharField(max_length=64, blank=True)
    work_center = models.ForeignKey(
        "scm.WorkCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_parameter_logs",
    )
    production_order_number = models.CharField(max_length=64, blank=True)
    work_order = models.ForeignKey(
        "scm.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_parameter_logs",
    )
    operation_step = models.CharField(max_length=64, blank=True)
    item_code = models.CharField(max_length=100, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)

    target_nominal_value = models.DecimalField(max_digits=12, decimal_places=4)
    upper_spec_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="USL - Engineering upper tolerance limit",
    )
    lower_spec_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="LSL - Engineering lower tolerance limit",
    )
    upper_control_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="UCL - Statistical upper control limit (μ + 3σ)",
    )
    lower_control_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="LCL - Statistical lower control limit (μ - 3σ)",
    )
    recorded_value = models.DecimalField(max_digits=12, decimal_places=4)
    recorded_at = models.DateTimeField(default=timezone.now)

    excursion_status = models.CharField(
        max_length=25,
        choices=EXCURSION_STATUS_CHOICES,
        default="normal",
        db_index=True,
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logged_parameters",
    )

    containment_action = models.CharField(
        max_length=35,
        choices=CONTAINMENT_ACTION_CHOICES,
        default="none",
        db_index=True,
    )
    containment_notes = models.TextField(blank=True)

    non_conformance = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parameter_logs",
        help_text="Linked NCR if excursion caused defective product",
    )
    process_deviation = models.ForeignKey(
        "quality.ProcessDeviation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parameter_logs",
        help_text="Authorized temporary waiver or engineering concession",
    )

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "Process Parameter Log"
        verbose_name_plural = "Process Parameter Logs"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qpar_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "excursion_status"], name="idx_qpar_ten_excurs"),
            models.Index(fields=["tenant", "containment_action"], name="idx_qpar_ten_contain"),
            models.Index(fields=["tenant", "parameter_category"], name="idx_qpar_ten_cat"),
            models.Index(fields=["tenant", "work_center"], name="idx_qpar_ten_wc"),
            models.Index(fields=["tenant", "work_order"], name="idx_qpar_ten_wo"),
            models.Index(fields=["tenant", "recorded_at"], name="idx_qpar_ten_rec_at"),
            models.Index(fields=["tenant", "excursion_status", "-recorded_at"], name="idx_qpar_ten_ex_rec"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qpar_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.parameter_name}: {self.recorded_value} {self.unit_of_measure} ({self.get_excursion_status_display()})"

    @property
    def excursion_css(self):
        return self.EXCURSION_STATUS_CSS.get(self.excursion_status, "badge-slate")

    @property
    def category_css(self):
        return self.PARAMETER_CATEGORY_CSS.get(self.parameter_category, "badge-slate")

    @property
    def containment_css(self):
        return self.CONTAINMENT_ACTION_CSS.get(self.containment_action, "badge-slate")

    @property
    def is_out_of_spec(self):
        return self.excursion_status == "out_of_spec"

    @property
    def is_out_of_control(self):
        return self.excursion_status in ("out_of_control", "out_of_spec")

    @property
    def deviation_from_target(self):
        if self.target_nominal_value is not None and self.recorded_value is not None:
            return round(self.recorded_value - self.target_nominal_value, 4)
        return Decimal("0.0000")
