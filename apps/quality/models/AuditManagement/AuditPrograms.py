from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class AuditProgram(TenantNumbered):
    NUMBER_PREFIX = "QPRG"

    PROGRAM_TYPE_CHOICES = (
        ("internal_qms", "Internal QMS Audits"),
        ("supplier_external", "Supplier & External Vendor Audits"),
        ("regulatory_certification", "Regulatory & Notified Body Audits"),
        ("integrated_enterprise", "Integrated Enterprise Quality Program"),
    )

    RISK_BASIS_CHOICES = (
        ("low_risk_annual", "Low Risk (Annual)"),
        ("medium_risk_biennial", "Medium Risk (Biennial)"),
        ("high_risk_semi_annual", "High Risk / Critical (Semi-Annual)"),
        ("for_cause_triggered", "For-Cause / Event Triggered"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("submitted", "Submitted for Approval"),
        ("approved", "Approved"),
        ("active", "Active / In Execution"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    PROGRAM_TYPE_CSS = {
        "internal_qms": "badge-info",
        "supplier_external": "badge-slate",
        "regulatory_certification": "badge-amber",
        "integrated_enterprise": "badge-green",
    }

    RISK_BASIS_CSS = {
        "low_risk_annual": "badge-muted",
        "medium_risk_biennial": "badge-info",
        "high_risk_semi_annual": "badge-red",
        "for_cause_triggered": "badge-amber",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-info",
        "approved": "badge-green",
        "active": "badge-green",
        "completed": "badge-muted",
        "cancelled": "badge-red",
    }

    title = models.CharField(max_length=255, help_text="e.g. FY2026 Enterprise Quality & Regulatory Audit Program")
    program_year = models.PositiveIntegerField(help_text="Operating fiscal year e.g. 2026")
    program_type = models.CharField(max_length=32, choices=PROGRAM_TYPE_CHOICES, default="internal_qms", db_index=True)
    risk_basis = models.CharField(max_length=32, choices=RISK_BASIS_CHOICES, default="low_risk_annual", db_index=True)
    scope_description = models.TextField(help_text="Scope boundaries, audit universe coverage, and strategic objectives")
    start_date = models.DateField(help_text="Program validity start date")
    end_date = models.DateField(help_text="Program validity end date")
    allocated_budget_hours = models.PositiveIntegerField(default=0, help_text="Budgeted auditor person-hours")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)

    program_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_audit_programs",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_audit_programs",
    )
    approval_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-program_year", "-created_at"]
        verbose_name = "Quality Audit Program"
        verbose_name_plural = "Quality Audit Programs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qprg_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qprg_ten_status"),
            models.Index(fields=["tenant", "program_year"], name="idx_qprg_ten_year"),
            models.Index(fields=["tenant", "program_type"], name="idx_qprg_ten_type"),
            models.Index(fields=["tenant", "risk_basis"], name="idx_qprg_ten_risk"),
            models.Index(fields=["tenant", "program_manager"], name="idx_qprg_ten_mgr"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qprg_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.program_year})"

    @property
    def total_audits_count(self):
        if hasattr(self, "annotated_total"):
            return self.annotated_total
        return self.audits.count()

    @property
    def completed_audits_count(self):
        if hasattr(self, "annotated_completed"):
            return self.annotated_completed
        return self.audits.filter(status="closed").count()

    @property
    def open_audits_count(self):
        if hasattr(self, "annotated_open"):
            return self.annotated_open
        return self.audits.exclude(status__in=["closed", "cancelled"]).count()

    @property
    def progress_percentage(self):
        total = self.total_audits_count
        if not total:
            return 0
        return int((self.completed_audits_count / total) * 100)
