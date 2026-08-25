"""Procurement 6.8 Contract Management — ContractAmendment model.

**Contract Amendment Tracking** bullet: "Version control and workflow for modifying
existing contracts." The shape mirrors 6.2's ``RequisitionAmendment`` — a proposed,
gated change to a live document that only an explicit decision writes through — but
aimed at the SCM-owned agreement spine: header terms (end date, value, auto-renewal,
notice window) move onto the contract ONLY inside ``apply()``, under a row lock, with
the decision stamps written in the same transaction.

Clause-level changes ride along as a human-readable digest (``proposed_summary``);
the authoritative wording lives in the clause links, which the next authoring pass
updates once the amendment is applied.

**Ownership (L29/L36):** ``scm.SupplierContract`` keeps its own terminate/renew verbs;
this table never re-states them.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class ContractAmendment(TenantNumbered):
    """One proposed change to a supplier agreement [CAM-]."""

    NUMBER_PREFIX = "CAM"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("applied", "Applied"),
        ("rejected", "Rejected"),
    ]
    #: Only these spine statuses accept a new amendment — terminal agreements are history.
    AMENDABLE_STATUSES = ("draft", "active", "expiring")

    contract = models.ForeignKey(
        "scm.SupplierContract", on_delete=models.PROTECT,
        related_name="procurement_amendments")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    reason = models.TextField(help_text="The documented case for this change")
    proposed_end_date = models.DateField(
        null=True, blank=True, help_text="Blank = leave the current end date standing")
    proposed_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Blank = leave the current contract value standing")
    proposed_auto_renew = models.BooleanField(
        null=True, blank=True, help_text="Blank = leave the current auto-renewal setting")
    proposed_notice_days = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Blank = leave the current renewal-notice window")
    proposed_summary = models.TextField(
        blank=True, help_text="Digest of clause-level changes riding along")

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="procurement_contract_amendments_requested",
        editable=False)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="procurement_contract_amendments_decided",
        editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True)
    applied_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")

    @classmethod
    def has_open_for(cls, contract):
        """One open amendment per agreement — sequential change control."""
        return cls.objects.filter(contract=contract, status="pending").exists()

    @property
    def proposal_digest(self):
        """One-line summary of what this amendment would move (for registers)."""
        bits = []
        if self.proposed_end_date is not None:
            bits.append(f"end → {self.proposed_end_date:%d %b %Y}")
        if self.proposed_value is not None:
            bits.append(f"value → {self.proposed_value}")
        if self.proposed_auto_renew is not None:
            bits.append(f"auto-renew → {'on' if self.proposed_auto_renew else 'off'}")
        if self.proposed_notice_days is not None:
            bits.append(f"notice → {self.proposed_notice_days}d")
        if (self.proposed_summary or "").strip():
            bits.append("clause digest")
        return "; ".join(bits) or "—"

    def apply(self, decider, contract_locked, note=""):
        """Write every proposed term that is actually set onto the spine agreement.

        The single writer of ``applied``: the caller fetches the CONTRACT under
        ``select_for_update()`` inside ``transaction.atomic()`` and passes it in
        locked, so two approvers racing cannot double-write. Blank proposals leave
        the standing term untouched — only provided columns move. Returns True on
        success; False when the state machine disagrees (the view already said why).
        """
        if self.status != "pending":
            return False
        changed = []
        if self.proposed_end_date is not None:
            contract_locked.end_date = self.proposed_end_date
            changed.append("end_date")
        if self.proposed_value is not None:
            contract_locked.contract_value = q2(self.proposed_value)
            changed.append("contract_value")
        if self.proposed_auto_renew is not None:
            contract_locked.auto_renew = self.proposed_auto_renew
            changed.append("auto_renew")
        if self.proposed_notice_days is not None:
            contract_locked.renewal_notice_days = self.proposed_notice_days
            changed.append("renewal_notice_days")
        if changed:
            contract_locked.save(update_fields=changed + ["updated_at"])
        now = timezone.now()
        self.status = "applied"
        self.decided_by = decider
        self.decided_at = now
        self.applied_at = now
        self.decision_note = note or ""
        self.save(update_fields=["status", "decided_by", "decided_at",
                                 "applied_at", "decision_note", "updated_at"])
        return True

    def __str__(self):
        return f"{self.number or 'CAM'} · {self.contract.number}"
