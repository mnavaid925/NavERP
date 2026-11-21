from django.conf import settings
from django.db import models
from django.db.models import Index, UniqueConstraint

from apps.quality.models._base import TenantNumbered


class PostMarketSurveillanceReport(TenantNumbered):
    NUMBER_PREFIX = "QPMS"

    REPORT_TYPE_CHOICES = [
        ("psur", "Periodic Safety Update Report (PSUR)"),
        ("pms_report", "Post-Market Surveillance Report (PMS)"),
        ("pmcf_evaluation", "Post-Market Clinical Follow-up (PMCF) Report"),
        ("vigilance_trend", "Vigilance Trend Assessment"),
        ("annual_safety", "Annual Safety Summary Report"),
    ]

    BENEFIT_RISK_CHOICES = [
        ("favorable", "Favorable — Benefits Outweigh Risks"),
        ("acceptable_monitoring", "Acceptable with Enhanced Monitoring"),
        ("unfavorable_action", "Unfavorable — Corrective Action Required"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / In Preparation"),
        ("in_review", "Under Clinical / QA Review"),
        ("approved", "Approved Internally"),
        ("submitted_to_authority", "Submitted to Notified Body / Authority"),
        ("archived", "Archived / Historical"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "approved": "badge-green",
        "submitted_to_authority": "badge-info",
        "archived": "badge-muted",
    }

    BENEFIT_RISK_CSS = {
        "favorable": "badge-green",
        "acceptable_monitoring": "badge-amber",
        "unfavorable_action": "badge-red",
    }

    report_title = models.CharField(max_length=255)
    report_type = models.CharField(
        max_length=30, choices=REPORT_TYPE_CHOICES, default="psur", db_index=True
    )
    product_registration = models.ForeignKey(
        "quality.ProductRegistration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pms_reports",
    )
    device_model_family = models.CharField(
        max_length=255, help_text="Product line, device model, or UDI family"
    )
    reporting_period_start = models.DateField()
    reporting_period_end = models.DateField(db_index=True)
    units_distributed = models.PositiveIntegerField(
        default=0, help_text="Total units shipped or deployed in period"
    )
    total_complaints_count = models.PositiveIntegerField(default=0)
    serious_incidents_count = models.PositiveIntegerField(default=0)
    field_actions_count = models.PositiveIntegerField(
        default=0, help_text="Number of recalls or FSCAs executed"
    )
    benefit_risk_conclusion = models.CharField(
        max_length=30, choices=BENEFIT_RISK_CHOICES, default="favorable", db_index=True
    )
    benefit_risk_rationale = models.TextField(blank=True)
    pmcf_action_required = models.BooleanField(default=False)
    pmcf_action_summary = models.TextField(blank=True)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_pms_reports",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_pms_reports",
    )
    approval_date = models.DateField(null=True, blank=True)
    next_report_due_date = models.DateField(null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-reporting_period_end", "number"]
        verbose_name = "Post-Market Surveillance Report"
        verbose_name_plural = "Post-Market Surveillance Reports"
        constraints = [
            UniqueConstraint(fields=["tenant", "number"], name="quality_qpms_ten_num_uniq"),
        ]
        indexes = [
            Index(fields=["tenant", "status"], name="idx_qpms_ten_status"),
            Index(fields=["tenant", "report_type"], name="idx_qpms_ten_type"),
            Index(fields=["tenant", "reporting_period_end"], name="idx_qpms_ten_period"),
        ]

    def __str__(self):
        return f"{self.number} — {self.report_title}"

    @property
    def complaint_rate_pct(self):
        if self.units_distributed > 0:
            return round((self.total_complaints_count / self.units_distributed) * 100, 4)
        return 0.0

    @property
    def serious_incident_rate_pct(self):
        if self.units_distributed > 0:
            return round((self.serious_incidents_count / self.units_distributed) * 100, 4)
        return 0.0

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def benefit_risk_css(self):
        return self.BENEFIT_RISK_CSS.get(self.benefit_risk_conclusion, "badge-slate")
