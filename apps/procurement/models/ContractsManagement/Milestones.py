"""Procurement 6.8 Contract Management — ContractMilestone model.

**Obligation & Milestone Management** bullet: "Tracking of deliverables, penalties,
and payment milestones tied to contracts." A milestone is a ONE-SHOT dated event on
an agreement — a deliverable due, a penalty that lands, a payment that falls due —
which is deliberately NOT the same shape as scm 4.12's ``ComplianceRequirement``
(that register tracks RECURRING compliance cycles; this one tracks single events
with amounts). Both point at the same spine contract without overlapping.

Numbered [CMI-] because milestones surface in their own cross-contract register.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class ContractMilestone(TenantNumbered):
    """One deliverable / penalty / payment event tied to a supplier agreement [CMI-]."""

    NUMBER_PREFIX = "CMI"

    KIND_CHOICES = [
        ("deliverable", "Deliverable"),
        ("payment", "Payment milestone"),
        ("penalty", "Penalty"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("waived", "Waived"),
    ]
    OPEN_STATUSES = ("pending", "in_progress")

    contract = models.ForeignKey(
        "scm.SupplierContract", on_delete=models.CASCADE,
        related_name="procurement_milestones")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="deliverable")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Payment value or penalty cap — blank for pure deliverables")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")

    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="procurement_milestones_completed",
        editable=False)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["due_date", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_cmi_tnt_status_idx"),
        ]

    @property
    def is_overdue(self):
        from django.utils import timezone
        return (self.status in self.OPEN_STATUSES
                and self.due_date < timezone.localdate())

    def __str__(self):
        return f"{self.number or 'CMI'} · {self.title}"
