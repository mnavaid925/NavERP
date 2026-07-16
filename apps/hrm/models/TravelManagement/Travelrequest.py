"""HRM 3.35 Travel Management — Travelrequest models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TravelRequest(TenantNumbered):
    """3.35 trip authorization + travel-advance header. Lean single-approver machine (draft -> pending ->
    approved/rejected/cancelled, then approved -> completed) — reuses _hr_request_submit/_cancel/_approve/
    _reject/_edit/_delete VERBATIM. Advance approval/payment and settlement generation are separate bespoke
    actions on top of an approved trip. net_settlement is computed, never stored."""

    NUMBER_PREFIX = "TRV"

    TRIP_TYPE_CHOICES = [
        ("domestic", "Domestic"),
        ("international", "International"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]
    OPEN_STATUSES = ("draft", "pending")  # required by _hr_request_edit/_delete/_cancel

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="travel_requests")
    title = models.CharField(max_length=255)
    trip_type = models.CharField(max_length=15, choices=TRIP_TYPE_CHOICES, default="domestic")
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    purpose = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    policy = models.ForeignKey("hrm.TravelPolicy", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="travel_requests")
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_travel_requests")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_travelrequest_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    advance_requested = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    advance_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    advance_paid_at = models.DateTimeField(null=True, blank=True)
    advance_reference = models.CharField(max_length=100, blank=True)
    settlement_claim = models.ForeignKey("hrm.ExpenseClaim", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="travel_settlements")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_travelreq_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_travelreq_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.destination}" if self.number else f"{self.origin} to {self.destination}"

    @property
    def net_settlement(self):
        """total_amount - (advance_approved or 0); None until a settlement exists. POSITIVE = payable to
        the employee (actual > advance); NEGATIVE = recoverable from the employee (advance > actual)."""
        if not self.settlement_claim_id:
            return None
        return self.settlement_claim.total_amount - (self.advance_approved or Decimal("0"))
