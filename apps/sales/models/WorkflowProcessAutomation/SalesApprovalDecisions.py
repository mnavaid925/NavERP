"""Sales 8.17 — SalesApprovalDecision model (multi-tier immutable approval chain)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

#: The three targets an approval chain can hang off. Kept as a module-level constant
#: (not a class attribute) because the action form and the deciding view both need it
#: and the contract pins it here — it does not collide with 8.16's ``ALERT_TYPE_CHOICES``.
TARGET_KIND_CHOICES = [
    ("quote", "Quote"),
    ("order_hold", "Order Hold"),
    ("contract", "Contract"),
]


class SalesApprovalDecision(TenantNumbered):
    """One immutable tier sign-off on one sales record [SAD-].

    Pattern source: ``apps/procurement/models/ApprovalWorkflowEngine/Approvals.py``
    ``RequisitionApproval`` — one decision row per tier, written ONLY when a decision
    actually happens (no draft/pending row to edit), snapshotted ``tier_count``, and
    mirrored to ``core.AuditLog`` by the deciding view. The register IS the history:
    "pending" is the ABSENCE of a row at the current tier, never a stored status.

    Procurement can key ``(tenant, requisition, tier)`` with ``unique_together``
    because it has ONE target FK. This entity has THREE nullable target FKs, so the
    contract pins a computed ``target_key`` CharField (``"<kind>:<pk>"``) plus an
    explicit ``UniqueConstraint`` on ``(tenant, target_key, tier)`` to give the chain
    the same idempotency guarantee across all three kinds.
    """

    NUMBER_PREFIX = "SAD"

    APPROVAL_KIND_CHOICES = [
        ("discount", "Discount"),
        ("credit", "Credit"),
        ("exception", "Exception"),
        ("contract", "Contract"),
    ]
    DECISION_CHOICES = [("approved", "Approved"), ("rejected", "Rejected")]

    approval_kind = models.CharField(max_length=10, choices=APPROVAL_KIND_CHOICES)
    quote = models.ForeignKey(
        "sales.CPQQuote",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_wpa_quote_decisions",
    )
    order_hold = models.ForeignKey(
        "sales.OrderHold",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_wpa_order_hold_decisions",
    )
    contract = models.ForeignKey(
        "sales.CustomerContract",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_wpa_contract_decisions",
    )
    target_key = models.CharField(max_length=40, editable=False, blank=True, default="")
    record_label = models.CharField(max_length=200, blank=True)
    approval_rule = models.ForeignKey(
        "sales.QuoteApprovalRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_decisions",
    )
    tier = models.PositiveSmallIntegerField()
    tier_count = models.PositiveSmallIntegerField()
    approver_role = models.ForeignKey(
        "accounts.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_role_decisions",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_decided",
    )
    decision = models.CharField(max_length=8, choices=DECISION_CHOICES)
    comment = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_requested",
    )
    requested_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(auto_now_add=True, editable=False)

    #: The (field name, raw-id attribute) pairs scanned by BOTH ``compute_target_key()``
    #: and ``clean()`` — one ordered source of truth so the two can never disagree (L49
    #: family: the same transformation, in the same place).
    TARGET_FIELDS = (("quote", "quote_id"), ("order_hold", "order_hold_id"), ("contract", "contract_id"))

    class Meta:
        ordering = ["target_key", "tier", "id"]  # deterministic — L61
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "target_key", "tier"], name="sales_sad_tnt_tgt_tier_uniq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "decision"], name="sales_sad_tnt_decision_idx"),
        ]

    def compute_target_key(self):
        """``"<kind>:<pk>"`` for whichever single target is set, else ``""``.

        Reads the raw ``*_id`` attributes so the key is available before the related
        object is ever fetched — a chain row created from a form ``commit=False``
        instance and one created by ``record()`` both land on the identical string,
        which is what makes the UniqueConstraint actually protect the chain.
        """
        for kind, attr in self.TARGET_FIELDS:
            pk = getattr(self, attr, None)
            if pk:
                return f"{kind}:{pk}"
        return ""

    def save(self, *args, **kwargs):
        self.target_key = self.compute_target_key()
        super().save(*args, **kwargs)

    @property
    def is_final_tier(self):
        """True when this row closes the chain. NEVER annotate an alias of this name (L57)."""
        return self.tier >= self.tier_count

    def clean(self):
        """Tenant-INDEPENDENT shape guard only.

        Tenant membership of the targets cannot be checked reliably here — on the form
        path ``self.tenant_id`` is still ``None`` while the instance is validated
        (L49). Those checks live in ``SalesApprovalDecisionForm.clean()`` / the
        narrowed form querysets and in the deciding view's tenant-scoped
        ``get_object_or_404``.
        """
        super().clean()
        targets = sum(1 for _, attr in self.TARGET_FIELDS if getattr(self, attr, None))
        if targets != 1:
            raise ValidationError("Set exactly one approval target (quote, order hold, or contract).")
        if self.tier_count and self.tier > self.tier_count:
            raise ValidationError({"tier": "A tier cannot exceed the chain length."})

    @classmethod
    def record(cls, tenant, *, quote=None, order_hold=None, contract=None, approval_kind,
               tier, tier_count, decision, approver=None, approver_role=None, approval_rule=None,
               requested_by=None, requested_at=None, due_at=None, record_label="", comment=""):
        """Append one decision row — called INSIDE the deciding view's atomic block (procurement pattern).

        ``save()`` recomputes ``target_key`` from the target FK set here, so this path and the
        form path cannot diverge. Bounds mirror procurement: label 200, comment 2000.
        """
        return cls.objects.create(
            tenant=tenant, quote=quote, order_hold=order_hold, contract=contract,
            approval_kind=approval_kind, tier=tier, tier_count=tier_count, decision=decision,
            approver=approver, approver_role=approver_role, approval_rule=approval_rule,
            requested_by=requested_by, requested_at=requested_at, due_at=due_at,
            record_label=(record_label or "")[:200], comment=(comment or "")[:2000])

    def __str__(self):
        return f"{self.number or 'SAD'} · {self.target_key} tier {self.tier}/{self.tier_count} {self.decision}"
