"""Procurement 6.3 Approval Workflow Engine — the decision chain log.

**Approval History & Audit Trail** bullet: "Unalterable log of who approved what,
when, and any comments added." One ``RequisitionApproval`` row per sign-off, created
ONLY when a decision happens (no draft state to edit) — the register IS the history.
Every row also lands in ``core.AuditLog`` via the deciding view, so the trail exists
twice by design: here in business shape, there in tamper-evident shape.

Rows are keyed ``(tenant, requisition, tier)`` and that uniqueness is SAFE here
where it bricked inventory 5.3's PO chain: a rejected requisition is terminal on the
spine (its EDITABLE_STATUSES exclude ``rejected``), so a chain can never be
resubmitted and replayed tiers cannot collide with history.
"""
from django.conf import settings

from apps.procurement.models._base import *  # noqa: F401,F403


class RequisitionApproval(TenantNumbered):
    """One sequential sign-off on one requisition [RQA-]."""

    NUMBER_PREFIX = "RQA"

    DECISION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    requisition = models.ForeignKey(
        "scm.PurchaseRequisition", on_delete=models.PROTECT,
        related_name="workflow_approvals",
        help_text="The requisition this signature belongs to")
    tier = models.PositiveSmallIntegerField(help_text="Which sign-off in the chain (1-based)")
    tier_count = models.PositiveSmallIntegerField(
        help_text="Chain length as resolved when this decision was made — a snapshot, so a later "
                  "rule change never rewrites what this approver thought they were signing")
    decision = models.CharField(max_length=8, choices=DECISION_CHOICES)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_approvals_decided")
    via_delegation = models.ForeignKey(
        "procurement.ApprovalDelegation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approvals",
        help_text="Set when the signer held authority through an active DOA grant")
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["requisition_id", "tier", "id"]
        unique_together = ("tenant", "requisition", "tier")
        indexes = [
            models.Index(fields=["tenant", "decision"], name="prc_rqa_tnt_decision_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'RQA'} · {self.requisition_id} tier {self.tier}/{self.tier_count} {self.decision}"

    @property
    def is_final_tier(self):
        return self.tier >= self.tier_count

    def clean(self):
        super().clean()
        if (self.requisition_id
                and self.requisition.tenant_id != self.tenant_id):
            raise ValidationError(
                {"requisition": "That record belongs to another workspace."})

    @classmethod
    def record(cls, tenant, requisition, *, tier, tier_count, decision,
               approver, delegation=None, comment=""):
        """Append one decision row — called INSIDE the deciding view's atomic block,
        which already holds the spine row lock; nothing else may write these rows."""
        return cls.objects.create(
            tenant=tenant, requisition=requisition, tier=tier, tier_count=tier_count,
            decision=decision, approver=approver, via_delegation=delegation,
            comment=(comment or "")[:2000])
