"""SCM 4.10 Returns Management — ReturnReason, the reason-code master (no NUMBER_PREFIX).

A reason is POLICY, not a label. What the customer says went wrong decides three things nothing
else can decide: who pays the return freight (``fault_party``), whether the unit may go back into
sellable stock (``blocks_restock``), and which outcomes the shopper may even be offered (the four
``allows_*`` booleans). D365 keeps reason codes and disposition codes as two separate sets for
exactly this reason, and so does this module: the reason is the INPUT, ``ReturnDisposition`` is the
OUTPUT, and collapsing them would mean a returns clerk could never overrule the customer's story.

``blocks_restock`` is EXECUTABLE in two places, not a comment: ``ReturnDispositionDecideForm``
refuses to offer ``restock`` when it is set, and ``returndisposition_post`` re-checks it INSIDE the
``transaction.atomic()`` that posts the ledger row (§7.5 — a gate lives in the view as well as the
button, because the button is not a security control).

This module also owns the shared disposition vocabulary — see :data:`DISPOSITION_CHOICES`.
"""
from apps.scm.models._base import *  # noqa: F401,F403


#: The disposition ladder, defined HERE rather than on ``ReturnDisposition`` because two models
#: need it and the dependency has to run one way to avoid an import cycle:
#: ``ReturnReason.suggested_disposition`` pre-selects a value from this set, and
#: ``ReturnDisposition.disposition`` stores the decision itself. Same shape as 4.6's
#: ``MODE_CHOICES``/``EQUIPMENT_CHOICES`` living in ``Carriers.py`` and being imported by its three
#: siblings. ``ReturnDispositions`` imports this module; this module imports nothing of its own.
#:
#: ``received_pending`` is the row's BIRTH state — goods are on the bench, quantity and grade are
#: recorded, and nothing has been decided or posted. It is deliberately part of the same field
#: rather than a separate `is_decided` boolean: one column, one state machine, one thing to read.
DISPOSITION_CHOICES = [
    ("received_pending", "Received — awaiting decision"),
    ("restock", "Restock (back to sellable)"),
    ("refurbish", "Refurbish"),
    ("repair_return", "Repair and return to customer"),
    ("scrap", "Scrap"),
    ("return_to_vendor", "Return to vendor"),
    ("liquidate", "Liquidate"),
    ("donate", "Donate"),
    ("recycle", "Recycle"),
    ("quarantine", "Quarantine"),
    ("credit_only", "Credit only (no goods)"),
]

#: The DECIDED half — everything a human may choose on the bench. ``received_pending`` is excluded
#: because it is arrived at by receiving, never by deciding, and offering it in the decide dropdown
#: would let somebody "decide" a row back into limbo after it had already posted stock.
DECIDED_DISPOSITION_CHOICES = [choice for choice in DISPOSITION_CHOICES
                               if choice[0] != "received_pending"]

#: Dispositions that make the customer's money OURS to give back. Read by
#: ``ReturnLine.credit_quantity`` and by ``refund_queue``'s SQL, so the queue's filter and the row's
#: badge can never disagree (§7.5).
#:
#: ``repair_return`` is absent ON PURPOSE: the unit goes BACK to the customer repaired, so they keep
#: the goods AND would keep the money. ``received_pending`` is absent because nothing has been
#: decided yet — crediting on arrival would refund a unit that turns out to be somebody else's.
CREDIT_BEARING_DISPOSITIONS = (
    "restock", "refurbish", "scrap", "return_to_vendor", "liquidate", "donate", "recycle",
    "quarantine", "credit_only",
)


class ReturnReason(TenantOwned):
    """Why the customer sent it back — and what that entitles them to."""

    FAULT_PARTY_CHOICES = [
        ("customer", "Customer"),
        ("merchant", "Us (merchant)"),
        ("carrier", "Carrier"),
        ("supplier", "Supplier"),
        ("unknown", "Unknown"),
    ]

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    fault_party = models.CharField(
        max_length=10, choices=FAULT_PARTY_CHOICES, default="customer",
        help_text="Who is at fault — drives who pays the return freight when the policy says "
                  "'by fault', and whether a supplier warranty claim is worth raising")

    # Four booleans rather than an M2M onto an outcome table: they are filterable in one query, they
    # need no migration when a fifth outcome is added to the RMA, and a join table of five rows per
    # reason would be pure ceremony.
    allows_refund = models.BooleanField(default=True)
    allows_store_credit = models.BooleanField(default=True)
    allows_exchange = models.BooleanField(default=True)
    allows_repair = models.BooleanField(default=False)

    waives_return_fee = models.BooleanField(
        default=False,
        help_text="Suppress the policy's restocking fee — our fault, our cost")
    blocks_restock = models.BooleanField(
        default=False,
        help_text="The unit can never go back into sellable stock on this reason (contamination, "
                  "a safety recall, a used consumable). Enforced in the disposition form AND "
                  "re-checked inside the posting transaction")
    suggested_disposition = models.CharField(
        max_length=16, choices=DECIDED_DISPOSITION_CHOICES, blank=True,
        help_text="Pre-selects the bench dropdown. A SUGGESTION — the grader always decides")
    requires_photo = models.BooleanField(
        default=False,
        help_text="A photo must be attached to the return line before approval "
                  "(ReturnLine.photo — CSR-attached; customer upload is deferred)")
    raises_nonconformance = models.BooleanField(
        default=False,
        help_text="Offer the 'Raise NCR' button on a disposition against this reason — makes the "
                  "quality link data-driven instead of a hard-coded reason list")
    follow_up_question = models.CharField(
        max_length=255, blank=True,
        help_text="Asked on the return portal when this reason is picked (e.g. 'Which size did "
                  "you need?')")
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "code"]
        unique_together = ("tenant", "code")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="scm_rtnreason_tnt_act_idx"),
            models.Index(fields=["tenant", "fault_party"], name="scm_rtnreason_tnt_flt_idx"),
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"

    def clean(self):
        super().clean()
        # A reason that offers nothing is a reason nobody can act on: the portal would show it, the
        # shopper would pick it, and every resolution would then be refused with no explanation.
        if not any((self.allows_refund, self.allows_store_credit, self.allows_exchange,
                    self.allows_repair)):
            raise ValidationError(
                {"allows_refund": "This reason offers the customer no outcome at all — allow at "
                                  "least one of refund, store credit, exchange or repair."})
        if self.blocks_restock and self.suggested_disposition == "restock":
            raise ValidationError(
                {"suggested_disposition": "This reason blocks restocking, so it cannot also "
                                          "suggest it."})

    # --- derived (nothing below is stored) -----------------------------------------------------
    @property
    def allowed_resolutions(self):
        """The RMA ``resolution`` values this reason permits, as a tuple.

        Read by ``evaluate_return_eligibility`` and intersected with the policy's own allowances —
        the reason may only ever NARROW what the policy offers, never widen it.
        """
        out = []
        if self.allows_refund:
            out.append("refund")
        if self.allows_store_credit:
            out.append("store_credit")
        if self.allows_exchange:
            out.append("exchange")
        if self.allows_repair:
            out.append("repair")
        return tuple(out)
