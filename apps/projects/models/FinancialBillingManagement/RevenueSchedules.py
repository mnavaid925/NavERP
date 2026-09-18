"""Projects 7.15 Financial & Billing Management — ProjectRevenueSchedule [PRS-].

Governs formal ASC 606 / IFRS 15 revenue recognition plans, cost center allocations,
and unbilled vs deferred revenue balances. Fulfills Bullet 1 (Project Accounting & Cost Centers).
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.projects.models._base import TenantNumbered, q2


class ProjectRevenueSchedule(TenantNumbered):
    NUMBER_PREFIX = "PRS"

    METHOD_CHOICES = [
        ("percent_complete", "Percentage of Completion"),
        ("milestone", "Milestone-Based"),
        ("as_billed", "As Billed / Invoiced"),
        ("straight_line", "Straight-Line Amortization"),
        ("manual", "Manual Entry"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("recognized", "Recognized"),
        ("locked", "Locked"),
        ("void", "Void"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="revenue_schedules",
    )
    milestone = models.ForeignKey(
        "projects.ProjectMilestone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenue_schedules",
    )
    recognition_date = models.DateField(default=timezone.localdate)
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_revenue_schedules",
    )
    method = models.CharField(
        max_length=24,
        choices=METHOD_CHOICES,
        default="percent_complete",
    )
    contract_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total contractual revenue baseline under recognition.",
    )
    completion_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Project progress percentage driving revenue recognition.",
    )
    recognized_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Revenue earned and recognized in this schedule.",
    )
    deferred_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Invoiced revenue not yet earned (liability).",
    )
    unbilled_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Earned revenue not yet invoiced (WIP asset).",
    )
    cost_center = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_revenue_schedules",
        help_text="Target cost center or division for profit/loss attribution.",
    )
    gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="project_revenue_schedules",
        help_text="Revenue account in the chart of accounts.",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="project_revenue_schedules",
        help_text="Canonical posted journal entry in accounting ledger.",
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default="draft",
    )
    recognized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    recognized_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-recognition_date", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="prs_tnt_prj_idx"),
            models.Index(fields=["tenant", "status"], name="prs_tnt_status_idx"),
            models.Index(fields=["tenant", "recognition_date"], name="prs_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.project.name} ({self.get_method_display()}): {self.recognized_amount}"

    def clean(self):
        super().clean()
        if self.status == "locked" and self.pk:
            orig = ProjectRevenueSchedule.objects.filter(pk=self.pk).values("status").first()
            if orig and orig["status"] == "locked":
                from django.core.exceptions import ValidationError
                raise ValidationError("Locked historical revenue schedules cannot be modified.")

    def save(self, *args, **kwargs):
        self.contract_amount = q2(self.contract_amount)
        self.completion_percent = q2(self.completion_percent)
        if self.method == "percent_complete" and self.completion_percent > Decimal("0.00") and self.contract_amount > Decimal("0.00") and self.recognized_amount == Decimal("0.00"):
            self.recognized_amount = q2(self.contract_amount * (self.completion_percent / Decimal("100.00")))
        else:
            self.recognized_amount = q2(self.recognized_amount)
        self.deferred_amount = q2(self.deferred_amount)
        self.unbilled_amount = q2(self.unbilled_amount)
        super().save(*args, **kwargs)
