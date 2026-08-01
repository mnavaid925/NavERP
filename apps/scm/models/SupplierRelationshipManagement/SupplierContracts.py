"""SCM 4.2 Supplier Relationship Management — SupplierContract model.

Stores a supplier agreement with its money terms, T&C summary, an optional scanned document, and —
the feature that earns its keep — renewal-alert tracking (``is_expiring_soon`` / ``days_to_expiry``)
so a contract never lapses unnoticed. Money FKs point at ``accounting.*`` by string (Module 2 owns
the ledger, L29).
"""
import datetime

from apps.scm.models._base import *  # noqa: F401,F403


class SupplierContract(TenantNumbered):
    """A contract/agreement with a supplier [SC-]. Status is partly derived from its dates."""

    NUMBER_PREFIX = "SC"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("expiring", "Expiring Soon"),
        ("expired", "Expired"),
        ("terminated", "Terminated"),
        ("renewed", "Renewed"),
    ]
    TYPE_CHOICES = [
        ("master", "Master Agreement"),
        ("purchase", "Purchase Contract"),
        ("service", "Service Agreement"),
        ("nda", "NDA"),
        ("sla", "SLA"),
        ("framework", "Framework"),
        # 4.12 — the Contract Repository bullet names logistics contracts explicitly, and 4.6's
        # Carrier.party FK means the counterparty already resolves. A choice-only change: the
        # migration is an AlterField that touches no row, and contract_type is already
        # max_length=12 against a 9-char value, so there is no column widen hiding in here.
        ("logistics", "Logistics / Carrier Agreement"),
    ]
    # Statuses that a date-driven refresh may move between; terminated/renewed are terminal decisions.
    AUTO_STATUSES = ("active", "expiring", "expired")

    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="scm_supplier_contracts")
    title = models.CharField(max_length=255)
    # --- 4.12 Contract & Compliance additions (additive, nullable, behaviour-neutral) -------------
    # An amendment / SOW / renewal is a separately-signed instrument, so this is SET_NULL rather
    # than CASCADE: deleting the master must orphan the amendment, never destroy it.
    parent_contract = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="amendments",
                                        help_text="The master agreement this amendment / SOW / renewal hangs off")
    # Renewals and 4.12 compliance obligations route to a named person, not to whoever last edited.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="scm_supplier_contracts_owned",
                              help_text="The person renewals and obligations route to")
    # ---------------------------------------------------------------------------------------------
    contract_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default="purchase")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    contract_value = models.DecimalField(max_digits=18, decimal_places=2, default=0,
                                         validators=[MinValueValidator(ZERO)])
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_supplier_contracts")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="scm_supplier_contracts")
    auto_renew = models.BooleanField(default=False)
    renewal_notice_days = models.PositiveIntegerField(default=30,
                                                      help_text="Alert this many days before expiry")
    terms_summary = models.TextField(blank=True, help_text="Key terms & conditions")
    document = models.ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_supplier_contracts", help_text="Signed contract file")
    terminated_at = models.DateTimeField(null=True, blank=True, editable=False)
    termination_reason = models.TextField(blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_sc_tnt_status_idx"),
            models.Index(fields=["tenant", "end_date"], name="scm_sc_tnt_enddate_idx"),
        ]

    def clean(self):
        """Guard the 4.12 amendment hierarchy: no self-parent, no cross-tenant parent, no cycle.

        The cycle check is not defensive padding. 4.12's contract detail page walks
        ``parent_contract`` upward to render the agreement's ancestry, and a cycle anywhere in that
        chain turns the walk into an infinite loop — a hung worker, not a caught error. Cheaper to
        refuse the edge than to bound every reader of it.
        """
        super().clean()
        parent = getattr(self, "parent_contract", None)
        if parent is None:
            return
        if self.pk and parent.pk == self.pk:
            raise ValidationError({"parent_contract": "A contract cannot be its own master agreement."})
        if self.tenant_id and parent.tenant_id != self.tenant_id:
            raise ValidationError({"parent_contract": "The master agreement belongs to another workspace."})
        # Walk upward with BOTH a hop cap and a seen-set: the cap bounds a pre-existing cycle that
        # predates this guard, the seen-set catches one that does not pass through self.
        seen, node, hops = {self.pk} if self.pk else set(), parent, 0
        while node is not None and hops < 10:
            if node.pk in seen:
                raise ValidationError({"parent_contract": "That master agreement is part of a cycle."})
            seen.add(node.pk)
            node = node.parent_contract
            hops += 1

    def days_to_expiry(self, today=None):
        """Days until ``end_date`` (negative if already past). None when no end date is set."""
        if not self.end_date:
            return None
        today = today or datetime.date.today()
        return (self.end_date - today).days

    def is_expiring_soon(self, today=None):
        days = self.days_to_expiry(today)
        return days is not None and 0 <= days <= self.renewal_notice_days

    def refresh_status(self, today=None, save=True):
        """Move active↔expiring↔expired from the dates. Never overrides a terminated/renewed decision."""
        if self.status not in self.AUTO_STATUSES:
            return
        days = self.days_to_expiry(today)
        if days is None:
            new = "active"
        elif days < 0:
            new = "expired"
        elif days <= self.renewal_notice_days:
            new = "expiring"
        else:
            new = "active"
        if new != self.status:
            self.status = new
            if save:
                self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"{self.number or 'SC'} · {self.title}"
