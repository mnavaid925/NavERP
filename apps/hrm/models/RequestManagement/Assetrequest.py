"""HRM 3.26 Request Management — Assetrequest models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeOnboarding.Assetallocation import AssetAllocation
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES
from apps.hrm.models.EmployeeOnboarding.Assetallocation import AssetAllocation
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES


class AssetRequest(TenantNumbered):
    """3.26 equipment request — an employee asks HR/IT for a laptop, phone, peripheral, etc.
    HR approves, then fulfils by issuing an ``AssetAllocation`` (AST-) — the request `asset_category`
    reuses ``AssetAllocation.ASSET_CATEGORY_CHOICES`` verbatim so the same taxonomy carries through.
    Lifecycle draft -> pending -> approved/rejected/cancelled, then approved -> fulfilled;
    `allocation` is created+linked by the fulfill action inside one atomic txn."""

    NUMBER_PREFIX = "ASSETREQ"

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("fulfilled", "Fulfilled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="asset_requests")
    asset_category = models.CharField(max_length=30, choices=AssetAllocation.ASSET_CATEGORY_CHOICES, default="other")
    asset_name = models.CharField(max_length=255)
    justification = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    needed_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_assetrequest_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    allocation = models.ForeignKey("hrm.AssetAllocation", on_delete=models.SET_NULL, null=True, blank=True,
                                   editable=False, related_name="fulfilled_requests")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_astreq_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_astreq_tenant_status_idx"),
        ]

    def __str__(self):
        return (f"{self.number} · {self.employee} · {self.asset_name}"
                if self.number else self.asset_name)
