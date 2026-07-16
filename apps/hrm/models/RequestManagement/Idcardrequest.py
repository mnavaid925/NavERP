"""HRM 3.26 Request Management — Idcardrequest models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class IdCardRequest(TenantNumbered):
    """3.26 ID-card request — new / replacement / correction / renewal. HR approves, then issues
    (stamping the card number). Lifecycle draft -> pending -> approved/rejected/cancelled, then
    approved -> issued. `card_number`/`issued_at` are set ONLY by the issue action."""

    NUMBER_PREFIX = "IDREQ"

    REQUEST_TYPE_CHOICES = [
        ("new", "New"),
        ("replacement", "Replacement"),
        ("correction", "Correction"),
        ("renewal", "Renewal"),
    ]
    REASON_TYPE_CHOICES = [
        ("lost", "Lost"),
        ("damaged", "Damaged"),
        ("stolen", "Stolen"),
        ("expired", "Expired"),
        ("name_change", "Name Change"),
        ("designation_change", "Designation Change"),
        ("first_issue", "First Issue"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("issued", "Issued"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="idcard_requests")
    request_type = models.CharField(max_length=15, choices=REQUEST_TYPE_CHOICES, default="new")
    reason_type = models.CharField(max_length=20, choices=REASON_TYPE_CHOICES, default="first_issue")
    reason = models.TextField()
    delivery_location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_idcardrequest_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    card_number = models.CharField(max_length=100, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_idreq_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_idreq_tenant_status_idx"),
        ]

    def __str__(self):
        return (f"{self.number} · {self.employee} · {self.get_request_type_display()}"
                if self.number else self.get_request_type_display())
