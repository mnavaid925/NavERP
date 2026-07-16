"""HRM 3.6 Candidate Management — RequisitionApprovals models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.JobRequisition.APPROVAL_STEP_STATUS_CHOICESs import APPROVAL_STEP_STATUS_CHOICES
from apps.hrm.models.JobRequisition.APPROVER_ROLE_CHOICESs import APPROVER_ROLE_CHOICES
from apps.hrm.models.JobRequisition.APPROVAL_STEP_STATUS_CHOICESs import APPROVAL_STEP_STATUS_CHOICES
from apps.hrm.models.JobRequisition.APPROVER_ROLE_CHOICESs import APPROVER_ROLE_CHOICES


class RequisitionApproval(TenantOwned):
    """One sequential approval step on a ``JobRequisition`` (3.5). The collection is both the
    approval chain (the current step = the lowest ``step_order`` still ``pending``) and the
    immutable audit trail — rows are never edited via a form: the approve/reject/return POST
    actions stamp ``status``/``decided_at``/``decided_by``. Mirrors the ``ClearanceItem`` child
    pattern from 3.4 Offboarding."""

    requisition = models.ForeignKey("hrm.JobRequisition", on_delete=models.CASCADE,
                                    related_name="approvals")
    step_order = models.PositiveSmallIntegerField(default=1)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="hrm_requisition_approvals")
    approver_role = models.CharField(max_length=20, choices=APPROVER_ROLE_CHOICES, default="hr")
    # Workflow-owned — set only by the approve/reject/return actions.
    status = models.CharField(max_length=20, choices=APPROVAL_STEP_STATUS_CHOICES,
                              default="pending", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="hrm_approval_decisions", editable=False)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["step_order"]
        unique_together = ("requisition", "step_order")
        indexes = [
            models.Index(fields=["requisition", "status"], name="hrm_ra_req_status_idx"),
            models.Index(fields=["approver", "status"], name="hrm_ra_approver_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.step_order is not None and self.step_order < 1:
            raise ValidationError({"step_order": "Step order must be at least 1."})

    def __str__(self):
        return (f"Step {self.step_order} — {self.get_approver_role_display()} "
                f"— {self.get_status_display()}")
