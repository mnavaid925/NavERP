from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class EnvironmentalMonitoringLog(TenantNumbered):
    NUMBER_PREFIX = "QENV"

    CLEANROOM_CLASS_CHOICES = [
        ("iso_class_3", "ISO Class 3 (Class 1)"),
        ("iso_class_4", "ISO Class 4 (Class 10)"),
        ("iso_class_5", "ISO Class 5 (Class 100 / Grade A/B)"),
        ("iso_class_6", "ISO Class 6 (Class 1,000)"),
        ("iso_class_7", "ISO Class 7 (Class 10,000 / Grade C)"),
        ("iso_class_8", "ISO Class 8 (Class 100,000 / Grade D)"),
        ("iso_class_9", "ISO Class 9 (Room Air)"),
        ("unclassified_controlled", "CNC — Controlled Non-Classified"),
    ]

    OPERATIONAL_STATE_CHOICES = [
        ("at_rest", "At Rest (Unoccupied)"),
        ("in_operation", "In Operation (Active Manufacturing)"),
    ]

    MONITORING_CATEGORY_CHOICES = [
        ("airborne_particles_0_5um", "Airborne Particles (>= 0.5 um)"),
        ("airborne_particles_5_0um", "Airborne Particles (>= 5.0 um)"),
        ("viable_air_microbial", "Active Air Sampler Microbial (CFU/m3)"),
        ("viable_settle_plate", "Passive Settle Plate Microbial (CFU/4hr)"),
        ("viable_surface_contact", "Surface Contact Plate Microbial (CFU/plate)"),
        ("viable_glove_print", "Personnel 5-Finger Glove Print (CFU)"),
        ("differential_pressure", "Differential Room Pressure (Pa)"),
        ("temperature", "Ambient Room Temperature (°C)"),
        ("relative_humidity", "Relative Room Humidity (%RH)"),
    ]

    UNIT_OF_MEASURE_CHOICES = [
        ("particles_m3", "particles/m3"),
        ("particles_ft3", "particles/ft3"),
        ("cfu_m3", "CFU/m3"),
        ("cfu_plate", "CFU/plate"),
        ("pascals", "Pa (Pascals)"),
        ("celsius", "°C"),
        ("percent_rh", "%RH"),
    ]

    EVALUATION_STATUS_CHOICES = [
        ("normal", "Normal Within Limits"),
        ("alert_exceeded", "Alert Limit Exceeded"),
        ("action_exceeded", "Action Limit Exceeded (Excursion)"),
        ("invalid_sample", "Invalid / Void Sample"),
    ]

    EVALUATION_STATUS_CSS = {
        "normal": "badge-green",
        "alert_exceeded": "badge-amber",
        "action_exceeded": "badge-red",
        "invalid_sample": "badge-slate",
    }

    sampling_point_id = models.CharField(max_length=100, db_index=True, help_text="Sampling location ID e.g. CR-ISO7-ZONE-B4")
    sampling_timestamp = models.DateTimeField(db_index=True, default=timezone.now, help_text="Date and time sample or reading was taken")
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="environmental_logs",
        help_text="Facility, laboratory, or cleanroom department",
    )
    cleanroom_class = models.CharField(max_length=35, choices=CLEANROOM_CLASS_CHOICES, default="iso_class_7", db_index=True)
    operational_state = models.CharField(max_length=25, choices=OPERATIONAL_STATE_CHOICES, default="in_operation", db_index=True)
    monitoring_category = models.CharField(max_length=40, choices=MONITORING_CATEGORY_CHOICES, default="airborne_particles_0_5um", db_index=True)

    parameter_name = models.CharField(max_length=255, help_text="Name of monitored parameter e.g. Differential Pressure Zone A-B")
    measured_value = models.DecimalField(max_digits=12, decimal_places=3, help_text="Measured quantitative sample value")
    unit_of_measure = models.CharField(max_length=25, choices=UNIT_OF_MEASURE_CHOICES, default="particles_m3", db_index=True)

    target_nominal_value = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Nominal target operating value")
    lower_alert_limit = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Lower alert limit threshold")
    upper_alert_limit = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Upper alert limit threshold")
    lower_action_limit = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Lower mandatory regulatory action limit")
    upper_action_limit = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Upper mandatory regulatory action limit")

    evaluation_status = models.CharField(max_length=25, choices=EVALUATION_STATUS_CHOICES, default="normal", db_index=True)
    excursion_details = models.TextField(blank=True, help_text="Details and impact of alert or action limit breach")
    immediate_containment_action = models.TextField(blank=True, help_text="Immediate containment (e.g. line pause, air purge, sanitization)")

    sampled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sampled_environmental_logs",
        help_text="QC sampling technician / industrial hygienist",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_environmental_logs",
        help_text="Quality engineer verifying reading and evaluation",
    )
    measurement_instrument = models.ForeignKey(
        "quality.CalibrationGage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="environmental_logs",
        help_text="Calibrated monitoring gage / particle counter",
    )

    process_deviation = models.ForeignKey(
        "quality.ProcessDeviation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="environmental_logs",
        help_text="Linked deviation report if action limit breached",
    )
    non_conformance_report = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="environmental_logs",
        help_text="Linked NCR if product quarantine triggered",
    )
    capa_investigation = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="environmental_logs",
        help_text="Linked CAPA for recurring cleanroom trends",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-sampling_timestamp", "-created_at"]
        verbose_name = "Environmental Monitoring Log"
        verbose_name_plural = "Environmental Monitoring Logs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qenv_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "evaluation_status"], name="idx_qenv_ten_status"),
            models.Index(fields=["tenant", "monitoring_category"], name="idx_qenv_ten_cat"),
            models.Index(fields=["tenant", "cleanroom_class"], name="idx_qenv_ten_class"),
            models.Index(fields=["tenant", "sampling_timestamp"], name="idx_qenv_ten_time"),
            models.Index(fields=["tenant", "sampling_point_id"], name="idx_qenv_ten_pt"),
            models.Index(fields=["tenant", "org_unit"], name="idx_qenv_ten_org"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qenv_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.sampling_point_id} ({self.parameter_name})"

    def calculate_evaluation_status(self):
        if self.evaluation_status == "invalid_sample":
            return "invalid_sample"
        val = self.measured_value
        if val is None:
            return "normal"
        # Check action limits first
        if self.upper_action_limit is not None and val > self.upper_action_limit:
            return "action_exceeded"
        if self.lower_action_limit is not None and val < self.lower_action_limit:
            return "action_exceeded"
        # Check alert limits next
        if self.upper_alert_limit is not None and val > self.upper_alert_limit:
            return "alert_exceeded"
        if self.lower_alert_limit is not None and val < self.lower_alert_limit:
            return "alert_exceeded"
        return "normal"

    def save(self, *args, **kwargs):
        if self.evaluation_status != "invalid_sample":
            self.evaluation_status = self.calculate_evaluation_status()
        super().save(*args, **kwargs)

    @property
    def is_excursion(self):
        return self.evaluation_status in ("alert_exceeded", "action_exceeded")

    @property
    def evaluation_status_css(self):
        return self.EVALUATION_STATUS_CSS.get(self.evaluation_status, "badge-slate")

    @property
    def cleanroom_display(self):
        return f"{self.get_cleanroom_class_display()} ({self.get_operational_state_display()})"
