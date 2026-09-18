"""Projects 7.14 Client & External Collaboration — StatementOfWork [SOW-] and SOWAmendment [SWA-].

Statement of work authoring, milestone/T&M/fixed-fee billing linkage,
scope terms, and amendment tracking.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.projects.models._base import TenantNumbered, q2


class StatementOfWork(TenantNumbered):
    NUMBER_PREFIX = "SOW"

    BILLING_TYPE_CHOICES = [
        ("fixed_fee", "Fixed Fee"),
        ("time_and_materials", "Time & Materials"),
        ("milestone_based", "Milestone-Based"),
        ("retainer", "Retainer"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("active", "Active"),
        ("amended", "Amended"),
        ("completed", "Completed"),
        ("terminated", "Terminated"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="statements_of_work",
    )
    client = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="client_sows",
    )
    title = models.CharField(max_length=255)
    sow_code = models.CharField(max_length=64, blank=True)
    billing_type = models.CharField(
        max_length=25, choices=BILLING_TYPE_CHOICES, default="fixed_fee"
    )
    contract_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    scope_summary = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    activated_at = models.DateTimeField(null=True, blank=True, editable=False)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="sow_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="sow_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.project.name})"

    @property
    def total_amendments(self):
        return self.amendments.filter(status="approved").count()

    @property
    def effective_value(self):
        base = self.contract_value or Decimal("0.00")
        approved_delta = sum(
            (a.value_change for a in self.amendments.filter(status="approved")),
            Decimal("0.00"),
        )
        return q2(base + approved_delta)


class SOWAmendment(TenantNumbered):
    NUMBER_PREFIX = "SWA"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    sow = models.ForeignKey(
        StatementOfWork,
        on_delete=models.CASCADE,
        related_name="amendments",
    )
    amendment_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=255)
    effective_date = models.DateField()
    value_change = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    revised_scope = models.TextField(blank=True)
    justification = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["amendment_number", "id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "sow"], name="swa_tnt_sow_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.sow.number} #{self.amendment_number}: {self.title}"
