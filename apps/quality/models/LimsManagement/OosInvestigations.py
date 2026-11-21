from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class OosInvestigation(TenantNumbered):
    NUMBER_PREFIX = "QOOS"

    PHASE_CHOICES = [
        ("phase_1_lab", "Phase I: Laboratory Investigation"),
        ("phase_2_manufacturing", "Phase II: Manufacturing Investigation"),
        ("awaiting_capa", "Awaiting CAPA / Disposition"),
        ("closed", "Investigation Closed"),
    ]

    STATUS_CHOICES = [
        ("open", "Open / In Progress"),
        ("retest_authorized", "Retest Authorized"),
        ("root_cause_found", "Root Cause Identified"),
        ("closed", "Closed"),
    ]

    SEVERITY_CHOICES = [
        ("critical", "Critical (Patient Safety / Product Impact)"),
        ("major", "Major (Regulatory / CQA Breach)"),
        ("minor", "Minor (Inconsequential)"),
    ]

    DISPOSITION_CHOICES = [
        ("pending", "Pending Disposition"),
        ("batch_released", "Batch Released"),
        ("batch_rejected", "Batch Rejected"),
        ("batch_reprocessed", "Batch Reprocessed"),
        ("quarantined", "Quarantined / Hold"),
    ]

    PHASE_CSS = {
        "phase_1_lab": "badge-amber",
        "phase_2_manufacturing": "badge-red",
        "awaiting_capa": "badge-info",
        "closed": "badge-green",
    }

    STATUS_CSS = {
        "open": "badge-amber",
        "retest_authorized": "badge-info",
        "root_cause_found": "badge-purple",
        "closed": "badge-green",
    }

    SEVERITY_CSS = {
        "critical": "badge-red",
        "major": "badge-amber",
        "minor": "badge-slate",
    }

    title = models.CharField(max_length=255)
    test_worksheet = models.ForeignKey(
        "quality.LabTestWorksheet",
        on_delete=models.CASCADE,
        related_name="oos_investigations",
    )
    sample = models.ForeignKey(
        "quality.LabSample",
        on_delete=models.CASCADE,
        related_name="oos_investigations",
    )
    investigation_phase = models.CharField(
        max_length=30,
        choices=PHASE_CHOICES,
        default="phase_1_lab",
        db_index=True,
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="open",
        db_index=True,
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="critical",
        db_index=True,
    )

    # Phase I: Laboratory Investigation (Lab Error Check)
    analyst_interview_completed = models.BooleanField(default=False)
    calculation_verification_completed = models.BooleanField(default=False)
    instrument_verification_completed = models.BooleanField(default=False)
    reagent_verification_completed = models.BooleanField(default=False)
    lab_error_identified = models.BooleanField(default=False)
    lab_error_description = models.TextField(
        blank=True,
        help_text="Details of documented lab error",
    )

    # Phase II: Manufacturing & Extended Investigation
    manufacturing_investigation_required = models.BooleanField(default=False)
    process_equipment_checked = models.BooleanField(default=False)
    raw_material_lots_checked = models.BooleanField(default=False)
    environmental_conditions_checked = models.BooleanField(default=False)
    assignable_cause = models.TextField(
        blank=True,
        help_text="Identified assignable root cause for OOS finding",
    )
    hypothesis_testing_summary = models.TextField(
        blank=True,
        help_text="Hypothesis test protocol and outcome",
    )

    # Retest, Disposition & Governance
    retest_plan_authorized = models.BooleanField(default=False)
    retest_results_summary = models.TextField(blank=True)
    final_batch_disposition = models.CharField(
        max_length=30,
        choices=DISPOSITION_CHOICES,
        default="pending",
        db_index=True,
    )
    investigation_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_oos_investigations",
    )
    qa_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_oos_investigations",
    )
    target_completion_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oos_investigations",
    )
    non_conformance = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oos_investigations",
    )
    summary_and_conclusions = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "OOS Investigation"
        verbose_name_plural = "OOS Investigations"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qoos_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "investigation_phase"], name="idx_qoos_ten_phase"),
            models.Index(fields=["tenant", "status"], name="idx_qoos_ten_status"),
            models.Index(fields=["tenant", "severity"], name="idx_qoos_ten_sev"),
            models.Index(fields=["tenant", "final_batch_disposition"], name="idx_qoos_ten_disp"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qoos_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_status_display()})"

    @property
    def phase_1_completed(self):
        return (
            self.analyst_interview_completed
            and self.calculation_verification_completed
            and self.instrument_verification_completed
            and self.reagent_verification_completed
        )

    @property
    def is_overdue(self):
        return (
            self.target_completion_date is not None
            and self.target_completion_date < timezone.now().date()
            and self.status != "closed"
        )

    def get_phase_badge(self):
        return self.PHASE_CSS.get(self.investigation_phase, "badge-slate")

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def get_severity_badge(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")
