from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class MrbDisposition(TenantNumbered):
    NUMBER_PREFIX = "QMRB"

    DISPOSITION_DECISION_CHOICES = (
        ("scrap", "Scrap & Destroy"),
        ("rework", "Rework to Specification"),
        ("repair", "Repair to Usable Condition"),
        ("use_as_is", "Use-As-Is (Concession)"),
        ("return_to_vendor", "Return to Vendor (RTV)"),
        ("regrade", "Downgrade / Re-grade"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("under_review", "Under MRB Review"),
        ("approved", "Disposition Approved"),
        ("rejected", "Disposition Rejected"),
        ("executed", "Executed / Completed"),
    )

    DISPOSITION_DECISION_CSS = {
        "scrap": "badge-red",
        "rework": "badge-amber",
        "repair": "badge-amber",
        "use_as_is": "badge-info",
        "return_to_vendor": "badge-slate",
        "regrade": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_review": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
        "executed": "badge-green",
    }

    ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.CASCADE,
        related_name="mrb_dispositions",
    )
    title = models.CharField(max_length=255)
    disposition_decision = models.CharField(
        max_length=24,
        choices=DISPOSITION_DECISION_CHOICES,
        default="rework",
        db_index=True,
    )
    technical_justification = models.TextField(
        help_text="Engineering and quality rationale for the chosen disposition",
    )
    concession_rationale = models.TextField(
        blank=True,
        help_text="Safety and efficacy rationale if Use-As-Is concession is granted",
    )
    rework_instructions = models.TextField(
        blank=True,
        help_text="Detailed step-by-step rework or repair instructions",
    )
    rework_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_reworks",
    )
    rework_completed_date = models.DateField(null=True, blank=True)
    reinspection_required = models.BooleanField(
        default=True,
        help_text="Requires quality reinspection after rework",
    )
    reinspection_criteria = models.TextField(
        blank=True,
        help_text="Acceptance test criteria for post-rework inspection",
    )
    reinspection_passed = models.BooleanField(
        null=True,
        blank=True,
        help_text="Outcome of reinspection (None=pending, True=passed, False=failed)",
    )
    reinspection_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reinspected_mrb_items",
    )
    scrap_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    rework_labor_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    vendor_chargeback_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_cost_impact = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    mrb_chair = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chaired_mrb_dispositions",
    )
    quality_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_approved_mrbs",
    )
    engineering_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="engineering_approved_mrbs",
    )
    operations_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operations_approved_mrbs",
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="under_review",
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "MRB Disposition"
        verbose_name_plural = "MRB Dispositions"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qmrb_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qmrb_ten_status"),
            models.Index(fields=["tenant", "disposition_decision"], name="idx_qmrb_ten_disp_dec"),
            models.Index(fields=["tenant", "ncr"], name="idx_qmrb_ten_ncr"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qmrb_ten_created"),
        ]

    def __str__(self):
        return f"{self.number or 'Draft'} - {self.title}"

    @property
    def disposition_decision_badge(self):
        return self.DISPOSITION_DECISION_CSS.get(self.disposition_decision, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def is_fully_approved(self):
        return bool(self.quality_approved_by and self.engineering_approved_by and self.operations_approved_by)

    def calculate_total_cost(self):
        return self.scrap_cost + self.rework_labor_cost + self.vendor_chargeback_cost

    def save(self, *args, **kwargs):
        self.total_cost_impact = self.calculate_total_cost()
        super().save(*args, **kwargs)
