"""Projects 7.15 Financial & Billing Management — ProjectPaymentRecord [PPR-].

Governs project-level client payment tracking, A/R collections workflow,
dunning stages, promise-to-pay commitments, and dispute tracking over
the canonical accounting.Invoice / PaymentAllocation ledger.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.projects.models._base import TenantNumbered, q2


class ProjectPaymentRecord(TenantNumbered):
    NUMBER_PREFIX = "PPR"

    STAGE_CHOICES = [
        ("current", "Current"),
        ("reminder_sent", "Reminder Sent"),
        ("overdue", "Overdue"),
        ("promise_to_pay", "Promise to Pay"),
        ("in_dispute", "In Dispute"),
        ("settled", "Settled"),
        ("written_off", "Written Off"),
    ]

    DUNNING_LEVEL_CHOICES = [
        ("friendly_reminder", "Friendly Reminder"),
        ("first_notice", "First Formal Notice"),
        ("second_notice", "Second Formal Notice"),
        ("final_demand", "Final Demand"),
        ("legal", "Legal Action"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("escalated", "Escalated"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="payment_records",
    )
    client = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="project_payment_records",
    )
    billing_run = models.ForeignKey(
        "projects.ProjectBillingRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_records",
    )
    accounting_invoice = models.ForeignKey(
        "accounting.Invoice",
        on_delete=models.CASCADE,
        related_name="project_collections",
        help_text="Canonical invoice being tracked for collection.",
    )
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="current",
    )
    dunning_level = models.CharField(
        max_length=20,
        choices=DUNNING_LEVEL_CHOICES,
        default="friendly_reminder",
    )
    last_contact_date = models.DateField(null=True, blank=True)
    next_follow_up_date = models.DateField(null=True, blank=True)
    promised_payment_date = models.DateField(null=True, blank=True)
    promised_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    dispute_reason = models.TextField(blank=True)
    assigned_collector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_project_collections",
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default="open",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="ppr_tnt_prj_idx"),
            models.Index(fields=["tenant", "stage"], name="ppr_tnt_stage_idx"),
            models.Index(fields=["tenant", "status"], name="ppr_tnt_status_idx"),
            models.Index(fields=["tenant", "dunning_level"], name="ppr_tnt_dunning_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.project.name} ({self.accounting_invoice.number}): {self.get_stage_display()}"

    def save(self, *args, **kwargs):
        if self.promised_amount is not None:
            self.promised_amount = q2(self.promised_amount)
        super().save(*args, **kwargs)
