import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ValidationProtocol(TenantNumbered):
    NUMBER_PREFIX = "QVAL"

    STAGE_CHOICES = [
        ("dq", "Design Qualification (DQ)"),
        ("iq", "Installation Qualification (IQ)"),
        ("oq", "Operational Qualification (OQ)"),
        ("pq", "Performance Qualification (PQ)"),
        ("ppq", "Process Performance Qualification (PPQ)"),
        ("cpv", "Continued Process Verification (CPV)"),
        ("revalidation", "Periodic / Change Revalidation"),
    ]

    TARGET_TYPE_CHOICES = [
        ("equipment", "Manufacturing / Lab Equipment"),
        ("process", "Manufacturing / Assembly Process"),
        ("facility_utility", "Facility Cleanroom & Utility System"),
        ("cleaning_procedure", "Equipment Cleaning Procedure"),
        ("computerized_system", "Computerized System / Software"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Protocol"),
        ("in_review", "Under Technical Review"),
        ("approved_for_execution", "Approved for Execution"),
        ("in_execution", "Active Execution in Progress"),
        ("deviation_hold", "Execution on Hold (Deviation)"),
        ("execution_completed", "Execution Testing Completed"),
        ("final_approved", "Final Approved & Released"),
        ("rejected", "Protocol Rejected"),
        ("superseded", "Superseded by New Protocol"),
    ]

    REVALIDATION_TRIGGER_CHOICES = [
        ("initial", "Initial Validation"),
        ("periodic_review", "Scheduled Periodic Review"),
        ("change_control", "Engineering / Process Change (DCO)"),
        ("deviation", "CAPA / OOS Deviation Resolution"),
        ("regulatory", "Regulatory Mandate / Inspection"),
    ]

    STAGE_CSS = {
        "dq": "badge-slate",
        "iq": "badge-info",
        "oq": "badge-info",
        "pq": "badge-info",
        "ppq": "badge-amber",
        "cpv": "badge-green",
        "revalidation": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-muted",
        "in_review": "badge-info",
        "approved_for_execution": "badge-info",
        "in_execution": "badge-amber",
        "deviation_hold": "badge-red",
        "execution_completed": "badge-info",
        "final_approved": "badge-green",
        "rejected": "badge-red",
        "superseded": "badge-slate",
    }

    title = models.CharField(max_length=255, help_text="Concise protocol title e.g. Autoclave 04 IQ/OQ Qualification Protocol")
    description = models.TextField(blank=True, help_text="Scope, objectives, and regulatory background of the validation protocol")
    protocol_stage = models.CharField(max_length=24, choices=STAGE_CHOICES, default="iq", db_index=True)
    target_type = models.CharField(max_length=30, choices=TARGET_TYPE_CHOICES, default="equipment", db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="draft", db_index=True)
    revalidation_trigger = models.CharField(max_length=25, choices=REVALIDATION_TRIGGER_CHOICES, default="initial", db_index=True)

    equipment_tag = models.CharField(max_length=100, blank=True, help_text="Target machine, line, or instrument asset identifier")
    process_name = models.CharField(max_length=150, blank=True, help_text="Target manufacturing, packaging, or cleaning process name")
    facility_area = models.CharField(max_length=150, blank=True, help_text="Cleanroom suite, plant area, or building room location")
    item_code = models.CharField(max_length=100, blank=True, help_text="Associated product code or assembly part number stand-in")

    target_completion_date = models.DateField(null=True, blank=True, help_text="Target qualification milestone date")
    actual_completion_date = models.DateField(null=True, blank=True, help_text="Actual formal protocol completion date")
    revalidation_due_date = models.DateField(null=True, blank=True, db_index=True, help_text="Scheduled periodic revalidation deadline")

    test_runs_planned = models.PositiveIntegerField(default=3, help_text="Number of replicate qualification runs planned (e.g. 3 consecutive runs)")
    test_runs_completed = models.PositiveIntegerField(default=0, help_text="Number of successful qualification runs executed")
    acceptance_criteria = models.TextField(blank=True, help_text="Pass/Fail acceptance specifications, tolerances, and statistical criteria")
    summary_conclusions = models.TextField(blank=True, help_text="Validation Summary Report (VSR) conclusions and recommendations")

    deviations_encountered = models.PositiveIntegerField(default=0, help_text="Count of non-conformances or excursions recorded during execution")
    critical_parameters_verified = models.BooleanField(default=False, help_text="Confirmation that all critical process parameters (CPPs) were verified")

    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validation_protocols",
        help_text="Owning department or operational facility",
    )
    lead_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_validation_protocols",
        help_text="Validation engineer authoring protocol",
    )
    qa_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_validation_protocols",
        help_text="Quality Assurance technical reviewer",
    )
    final_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_validation_protocols",
        help_text="Quality Authority granting final validation approval",
    )

    governing_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validation_protocols",
        help_text="Governing Validation Master Plan (VMP) or standard SOP",
    )
    triggering_change = models.ForeignKey(
        "quality.DocumentChangeOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_validation_protocols",
        help_text="Change control order triggering revalidation",
    )
    calibration_gage = models.ForeignKey(
        "quality.CalibrationGage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validation_protocols",
        help_text="Primary calibrated standard or test equipment used",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Validation Protocol"
        verbose_name_plural = "Validation Protocols"
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_qval_ten_created"),
            models.Index(fields=["tenant", "status"], name="idx_qval_ten_status"),
            models.Index(fields=["tenant", "protocol_stage"], name="idx_qval_ten_stage"),
            models.Index(fields=["tenant", "target_type"], name="idx_qval_ten_target"),
            models.Index(fields=["tenant", "target_completion_date"], name="idx_qval_ten_target_due"),
            models.Index(fields=["tenant", "revalidation_due_date"], name="idx_qval_ten_reval_due"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qval_ten_num_uniq"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def is_overdue(self):
        if self.target_completion_date and self.status not in ("final_approved", "rejected", "superseded"):
            return self.target_completion_date < datetime.date.today()
        return False

    @property
    def is_revalidation_overdue(self):
        if self.revalidation_due_date:
            return self.revalidation_due_date < datetime.date.today()
        return False

    @property
    def progress_percentage(self):
        if not self.test_runs_planned:
            return 100 if self.status == "final_approved" else 0
        ratio = (self.test_runs_completed / self.test_runs_planned) * 100
        return min(int(ratio), 100)

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def stage_css(self):
        return self.STAGE_CSS.get(self.protocol_stage, "badge-slate")
