"""CRM 1.10 Automation & Workflow Engine — Approvals models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class ApprovalRequest(TenantNumbered):
    """A generic approval gate, e.g. a discount lock until a manager approves (1.10)."""

    NUMBER_PREFIX = "APR"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    rule = models.ForeignKey("crm.WorkflowRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="approvals")
    subject = models.CharField(max_length=255)
    record_label = models.CharField(max_length=255, blank=True)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approvals_to_action")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approvals_requested")
    threshold_field = models.CharField(max_length=100, blank=True)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    approved_at = models.DateTimeField(null=True, blank=True)  # system-set
    rejected_at = models.DateTimeField(null=True, blank=True)  # system-set
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_apr_tnt_status_idx"),
            models.Index(fields=["tenant", "approver"], name="crm_apr_tnt_approver_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_apr_tnt_created_idx"),
        ]

    @property
    def is_pending(self):
        return self.status == "pending"

    def __str__(self):
        return f"{self.number} · {self.subject}"
