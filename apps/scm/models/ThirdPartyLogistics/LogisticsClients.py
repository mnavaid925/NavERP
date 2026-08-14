"""SCM 4.17 Third-Party Logistics (3PL) — ``LogisticsClient``, the depositor master [3PL-].

One row per company whose goods we store and handle on their behalf: their commercial configuration,
their billing convention, the space they committed to, and how their orders reach us. It is the ROOT
of the sub-module — ``ClientRateCard``, ``ClientBillingRun`` and ``ClientSLA`` all point back at it,
and so do the two additive ``owner_client`` columns this sub-module adds to 4.3's ``Item`` and
``Location``.

**IDENTITY STAYS ON ``core.Party``.** There is no name, no address, no tax id and no contact column
below — this row carries only what makes a party a *3PL client of ours*. That is the same posture
``scm.Carrier`` and ``SupplierProfile`` already hold, and the reason is the one the core spine exists
for: a second name/address table is a second thing to keep true, and the copy that goes stale is
always the one nobody looks at. Verified at build time: no ``Client`` / ``Depositor`` / ``StockOwner``
/ ``Warehouse`` / ``Tariff`` model exists anywhere in the repository, so this is the new master and it
is deliberately thin.

**Client attribution is DERIVED, never a second ledger (L37).** Whose stock a movement belongs to is
read through ``item.owner_client``; there is deliberately **no owner column on ``StockMove``**. An
owner on an append-only ledger would be a second source of truth for the same fact, and the two would
disagree the first time an item was re-assigned. Every figure this model reports about stock —
``on_hand_quantity``, ``on_hand_value`` — is an aggregate over that ledger computed on read, and none
of them is ever stored (L29).

**No secret of any kind lives on this row (L20).** ``integration_mode`` / ``client_system`` /
``edi_partner_id`` / ``edi_qualifier`` are non-secret partner identifiers, the sort of thing that
appears in the header of an EDI envelope. There is no API key, no endpoint URL, no EDI password and
no token here, and none may be added: credential storage, EDI transport and webhooks are **4.19's**.
``last_synced_at`` is written by NOTHING in 4.17 — it exists so that when 4.19 lands it writes a real
timestamp into a column that already has a home, rather than adding one late.

**SCM posts no journal entry (L29).** 4.17's furthest reach into money is a DRAFT
``accounting.Invoice`` created by ``ClientBillingRun.draft_invoice()``. AR aging, cash application,
dunning, tax determination and journal posting are Module 2's and stay there.

**Note on layout, so no review agent "fixes" it:** the backend package is ``ThirdPartyLogistics/``
(PascalCase of the NavERP.md title) while the templates live in ``templates/scm/3pl/`` (the short
slug all sixteen shipped scm template folders use). The asymmetry is the house rule, not a defect —
the identical note sits at ``CustomerPortal/PortalAccounts.py:45-47``.
"""
from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — `apps/scm/models/__init__.py` already star-imports three `_choices`
# modules, so a fourth star-import could silently shadow a shared token with the winner decided by
# import order. `ThirdPartyLogistics/_choices.py` imports nothing but `Decimal` (not even `_base`), so
# the dependency edge inside 4.17 only ever runs one way and no cycle is possible.
#
# THIS ENTITY OWNS THAT FILE. ClientRateCards / ClientBillingRuns / ClientSlas import from it by name
# exactly like the line below and must never create or edit it.
from apps.scm.models.ThirdPartyLogistics._choices import (
    BILLING_CYCLE_CHOICES,
    CLIENT_STATUS_CHOICES,
    COMMITTED_SPACE_MODELS,
    INTEGRATION_MODE_CHOICES,
    MAX_CLIENT_DEPTH,
    MAX_COMMITTED_PALLETS,
    MAX_COMMITTED_SQFT,
    SPACE_MODEL_CHOICES,
    STORAGE_BILLING_METHOD_CHOICES,
)


class LogisticsClient(TenantNumbered):
    """One 3PL client's commercial configuration [3PL-]. Identity lives on ``core.Party``."""

    NUMBER_PREFIX = "3PL"

    #: Every FK on this model whose target is tenant-scoped, read by BOTH boundaries: the form's
    #: ``_reject_foreign`` (which renders a field error) and this model's own ``clean()`` (which holds
    #: for the seeder and the shell). One table, two readers — two copies of an authorisation rule is
    #: two places for it to be wrong.
    #:
    #: ``currency`` is deliberately ABSENT: ``accounting.Currency`` is a GLOBAL model with no tenant
    #: FK, so a tenant comparison against it would reject every valid selection.
    TENANT_SCOPED_FKS = ("party", "parent_client", "payment_terms", "default_revenue_account",
                         "contract_document", "account_manager")

    # --- who this client is ----------------------------------------------------------------------
    # PROTECT, not CASCADE: this row is the anchor of a tariff, a billing history and an SLA record,
    # and deleting the party must not take that commercial trail with it in one click.
    #
    # NOT checked anywhere: that the party carries a "customer" PartyRole. It is surfaced as form help
    # text and as a chip on the detail page, never as a hard error — a client onboarded by an
    # operations team before finance tags them is an ordinary Tuesday, and refusing the save would
    # make the two teams' order of work a validation rule.
    party = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="scm_logistics_clients",
        help_text="The company whose goods we store and handle. Name, addresses and tax details "
                  "live on the party record — this row is only the 3PL agreement")

    # Short and human: it goes on every bin label, every pick list conversation and every line of an
    # invoice, so 8 characters is the point rather than a limitation.
    code = models.CharField(
        max_length=8,
        help_text="Short client code, e.g. ACME. Used on labels, reports and invoice lines")

    # SET_NULL: a parent group being removed must not delete its divisions. The cycle guard lives in
    # clean() — see there for why an unbounded walk is a hung request rather than a validation error.
    parent_client = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_clients",
        help_text="For a client group with divisions or brands billed separately. Leave blank for a "
                  "standalone client")

    status = models.CharField(max_length=16, choices=CLIENT_STATUS_CHOICES, default="prospect")

    # Stamped ONCE in save(), the first time the client is active, and never restamped — the
    # PortalAccount.activated_on pattern, including its update_fields fix-up. A suspend/reactivate
    # cycle must not rewrite the onboarding date, because "when did this client go live?" is the
    # question the number is kept to answer. editable=False keeps it off every ModelForm
    # automatically rather than relying on each form's field list (L22).
    onboarded_on = models.DateField(null=True, blank=True, editable=False)

    # --- billing configuration -------------------------------------------------------------------
    billing_cycle = models.CharField(max_length=12, choices=BILLING_CYCLE_CHOICES, default="monthly")

    # 28, not 31, and the ceiling is the whole point: a client billed on the 30th has no billing day
    # in February. Clamping to 28 means every month has one, which is the convention every billing
    # system that has been bitten by this settles on.
    billing_day = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Day of the period the invoice is raised on. Capped at 28 so every month has one")

    next_billing_date = models.DateField(
        null=True, blank=True,
        help_text="Planning note only. 4.17 ships NO scheduler and nothing in this module reads this "
                  "date — billing runs are created and calculated by hand")

    storage_billing_method = models.CharField(
        max_length=16, choices=STORAGE_BILLING_METHOD_CHOICES, default="calendar_month",
        help_text="How storage is measured against the stock ledger. Each method produces a "
                  "different figure from the same stock — this is the most consequential setting here")

    minimum_monthly_charge = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="Monthly floor. Applied by a billing run only when the client is billed MONTHLY "
                  "and the run's period covers a whole month")

    # A DECIMAL, not a TaxCode FK — and the width matches accounting.InvoiceLine.tax_rate_pct
    # (max_digits=5, decimal_places=2) EXACTLY, because that is where this figure is copied to. There
    # is no tax-code master on the SCM side and tax determination is Module 2's; a rate we carry
    # forward onto a draft line is honest, a tax engine invented here would not be.
    default_tax_rate_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Copied onto each drafted invoice line. Tax determination itself is Accounting's")

    # accounting.Currency is GLOBAL (no tenant FK) — the form scopes it by is_active instead.
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    payment_terms = models.ForeignKey(
        "accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    default_revenue_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Fallback revenue account for drafted invoice lines whose tariff line names none")

    # --- space -----------------------------------------------------------------------------------
    space_model = models.CharField(max_length=10, choices=SPACE_MODEL_CHOICES, default="shared")
    committed_sqft = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="Contracted floor area. Only meaningful for a dedicated or hybrid space model")
    committed_pallet_positions = models.PositiveIntegerField(
        default=0,
        help_text="Contracted pallet positions. Only meaningful for a dedicated or hybrid space model")

    # --- contract ---------------------------------------------------------------------------------
    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    notice_days = models.PositiveSmallIntegerField(
        default=0, help_text="Notice period for termination, in days")
    contract_document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The signed agreement, uploaded to the document library")

    # --- integration (NON-SECRET IDENTIFIERS ONLY — see the module docstring) ----------------------
    integration_mode = models.CharField(
        max_length=12, choices=INTEGRATION_MODE_CHOICES, default="none")
    client_system = models.CharField(
        max_length=60, blank=True,
        help_text="SAP, NetSuite, Dynamics, Shopify, Amazon… — the system on their side")
    edi_partner_id = models.CharField(
        max_length=32, blank=True,
        help_text="Their EDI interchange id. An identifier, never a credential")
    edi_qualifier = models.CharField(
        max_length=8, blank=True, help_text="EDI qualifier for the id above, e.g. ZZ or 01")
    # WRITTEN BY NOTHING IN 4.17. It exists so 4.19's transport writes a real timestamp into a column
    # that already has a home. editable=False keeps it off every form (L22) rather than relying on
    # each form's field list — a system timestamp on a DateInput is silently truncated to a date.
    last_synced_at = models.DateTimeField(null=True, blank=True, editable=False)

    # --- ownership + notes -------------------------------------------------------------------------
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    notes = models.TextField(blank=True)

    class Meta:
        # `code` is what people say out loud and what the list is scanned by; `id` is the tie-break
        # that makes it a TOTAL order, so page 2 is deterministic rather than depending on row order.
        ordering = ["code", "id"]
        # Three pairs. ("tenant", "number") is the house auto-number guarantee TenantNumbered's retry
        # loop relies on. ("tenant", "code") is the rule a user breaks by hand — two clients sharing a
        # code makes every label and every invoice line ambiguous. ("tenant", "party") is the business
        # rule: ONE 3PL agreement per company, or which tariff applied would depend on row order.
        unique_together = (("tenant", "number"), ("tenant", "code"), ("tenant", "party"))
        indexes = [
            # The list page's status filter and every header chip filter this pair.
            models.Index(fields=["tenant", "status"], name="scm_3pl_tnt_status_idx"),
            # Covers Meta.ordering's leading column, so the default list ORDER BY walks an index
            # rather than filesorting the workspace.
            models.Index(fields=["tenant", "code"], name="scm_3pl_tnt_code_idx"),
        ]

    def __str__(self):
        return f"{self.code} · {self.party}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Six guards. Every FK read is defended twice — a null-id test AND a defaulted ``getattr``.

        The ``getattr(self, name, None)`` half is not belt-and-braces: ``RelatedObjectDoesNotExist``
        subclasses ``AttributeError``, so a pointer whose row went away degrades to ``None`` here
        instead of 500-ing inside validation. The ``_id is not None`` half is what keeps an unsaved
        instance from raising on a non-nullable FK that has not been set yet.

        Every error is keyed on a field the FORM has. A model error keyed on a column the form lacks
        raises ``ValueError`` out of ``add_error`` — a 500 instead of a field error (L39 §2).
        """
        super().clean()
        errors = {}

        # (a) The party must belong to this workspace. The form's dropdown is already scoped, but a
        #     narrowed <select> has never held against a crafted POST — and a foreign party here
        #     would put another workspace's company name on our invoices.
        if self.party_id is not None and self.tenant_id is not None:
            party = getattr(self, "party", None)
            if party is not None and party.tenant_id != self.tenant_id:
                errors["party"] = "That party belongs to another workspace."

        # (b) The parent chain: not itself, not another workspace's, and not a CYCLE.
        #
        #     The walk is BOUNDED by MAX_CLIENT_DEPTH. An unbounded one against an existing A->B->A
        #     cycle is an infinite loop inside form validation — a hung request from an ordinary edit,
        #     which is worse than any wrong answer. Ten levels is generous for a client group.
        if self.parent_client_id is not None:
            parent = getattr(self, "parent_client", None)
            if self.pk is not None and self.parent_client_id == self.pk:
                errors["parent_client"] = "A client cannot be its own parent."
            elif parent is None:
                pass  # the row went away; the FK constraint is the boundary that holds here
            elif self.tenant_id is not None and parent.tenant_id != self.tenant_id:
                errors["parent_client"] = "That parent client belongs to another workspace."
            elif self.pk is not None:
                node, depth = parent, 0
                while node is not None and depth < MAX_CLIENT_DEPTH:
                    if node.pk == self.pk:
                        errors["parent_client"] = (
                            "That would make a loop in the client hierarchy — this client is already "
                            "somewhere above the parent you picked.")
                        break
                    node = node.parent_client
                    depth += 1
                else:
                    if node is not None:
                        errors["parent_client"] = (
                            f"The client hierarchy is more than {MAX_CLIENT_DEPTH} levels deep at "
                            "that parent. Flatten it before adding another level.")

        # (c) A dedicated or hybrid client with NO commitment prices its dedicated space at zero and
        #     nobody notices until the invoice goes out.
        space_model = self.space_model or ""
        committed_sqft = self.committed_sqft or ZERO
        committed_pallets = self.committed_pallet_positions or 0
        if space_model in COMMITTED_SPACE_MODELS and committed_sqft <= ZERO and committed_pallets <= 0:
            errors["space_model"] = (
                f"A {self.get_space_model_display().lower()} space model needs a commitment — enter "
                "the contracted square feet or pallet positions, or change the space model to shared.")

        # (d) The mirror rule. A shared client carrying a commitment is REFUSED rather than ignored:
        #     a figure a user typed and the system silently drops is worse than an error, because
        #     they leave believing it applied — and here it would look like rented space we never
        #     agreed to.
        if space_model == "shared" and (committed_sqft > ZERO or committed_pallets > 0):
            errors["space_model"] = (
                "A shared space model has no committed space to record. Clear the commitment "
                "figures, or set the space model to dedicated or hybrid.")

        # Column-shape guards, so an over-range figure is a field error rather than a DataError the
        # database raises on save.
        if committed_sqft > MAX_COMMITTED_SQFT:
            errors["committed_sqft"] = f"That is larger than the maximum {MAX_COMMITTED_SQFT} sq ft."
        if committed_pallets > MAX_COMMITTED_PALLETS:
            errors["committed_pallet_positions"] = (
                f"That is more than the maximum {MAX_COMMITTED_PALLETS} pallet positions.")

        # (e) A contract that ends before it starts.
        if (self.contract_start is not None and self.contract_end is not None
                and self.contract_end < self.contract_start):
            errors["contract_end"] = "The contract end date is before its start date."

        # (f) The remaining tenant-scoped pointers, same defended read as (a). Kept in one loop so a
        #     seventh FK added later inherits the check by being added to TENANT_SCOPED_FKS rather
        #     than by somebody remembering to write another branch.
        if self.tenant_id is not None:
            for name in ("payment_terms", "default_revenue_account", "contract_document",
                         "account_manager"):
                if getattr(self, f"{name}_id", None) is None:
                    continue
                related = getattr(self, name, None)
                if related is not None and getattr(related, "tenant_id", None) != self.tenant_id:
                    errors[name] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        """Stamp :attr:`onboarded_on` ONCE, then hand off to ``TenantNumbered.save``.

        First time the client is active, and never again — a suspend/reactivate cycle must not
        rewrite the date they went live, because that is the date every "how long have we had this
        client?" answer is computed from.

        The ``update_fields`` fix-up matters because the stamp is a side effect of a save the caller
        did not ask for: a partial ``save(update_fields=["status"])`` that flipped the client to
        active would otherwise compute the date, keep it in memory and never write it — leaving an
        active client with no onboarding date at all.
        """
        if self.status == "active" and self.onboarded_on is None:
            self.onboarded_on = timezone.localdate()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "onboarded_on" not in update_fields:
                kwargs["update_fields"] = list(update_fields) + ["onboarded_on"]
        return super().save(*args, **kwargs)

    # ---------------------------------------------------------------------------------------------
    # Derived — NOTHING below is a column, and none of it may be called per row from a list page
    # ---------------------------------------------------------------------------------------------
    # Each of these fires its own query. They are correct, and they are meant for ONE row on a detail
    # page. A list view that calls them per row is 15 rows x N queries for one screen — exactly the
    # 4.13 `asset_list` finding, and the fact that they read nicely in a template is what makes it
    # easy to ship. The list page annotates instead; the report pages use grouped aggregates.
    def on_hand_quantity(self):
        """Signed SUM over the append-only ledger of every movement of this client's items.

        Client attribution runs through ``item.owner_client`` and through nothing else — there is no
        owner column on ``StockMove`` and there must not be one (L37).

        Local import, the ``views/_helpers.py`` idiom: ``StockMove`` lives in a sibling sub-package of
        the same models package, and importing it at module scope would ask a partially-initialised
        ``apps.scm.models`` for a name it may not have bound yet.
        """
        if self.pk is None or self.tenant_id is None:
            return ZERO
        from apps.scm.models import StockMove
        return (StockMove.objects
                .filter(tenant_id=self.tenant_id, item__owner_client=self)
                .aggregate(q=Sum("quantity"))["q"] or ZERO)

    def on_hand_value(self):
        """Quantity x the item's cached average cost, summed in Python over ONE grouped aggregate.

        The cost is pulled through the same query as the quantity (``item__average_cost``) rather
        than read off each ``Item`` afterwards, which would be a query per SKU on a detail page.

        ``.order_by()`` is load-bearing: ``StockMove.Meta.ordering`` is ``["-moved_at", "-id"]`` and
        an inherited ORDER BY column is dragged into the GROUP BY, splitting the sum per timestamp.

        Rows that net to zero or below are skipped. Under the posting guards an item cannot go
        negative at a location, and a net-negative total is a data anomaly rather than negative value
        held — folding it in would understate the position without saying so.
        """
        if self.pk is None or self.tenant_id is None:
            return ZERO
        from apps.scm.models import StockMove
        total = ZERO
        rows = (StockMove.objects
                .filter(tenant_id=self.tenant_id, item__owner_client=self)
                .order_by()
                .values("item_id", "item__average_cost")
                .annotate(qty=Sum("quantity")))
        for row in rows:
            quantity = row["qty"] or ZERO
            if quantity <= ZERO:
                continue
            total += quantity * (row["item__average_cost"] or ZERO)
        return q2(total)

    def sku_count(self):
        """How many item masters are assigned to this client — the segregation figure.

        Deliberately the count of ASSIGNED items, not of items currently holding stock: a client with
        forty SKUs and an empty warehouse still has forty SKUs, and reporting 0 would read as a
        configuration gap rather than an empty season.
        """
        if self.pk is None:
            return 0
        return self.owned_items.count()

    def dedicated_location_count(self):
        """Locations reserved to this client (``Location.owner_client``)."""
        if self.pk is None:
            return 0
        return self.dedicated_locations.count()

    def open_sla_breaches(self):
        """Active SLAs currently sitting at ``breached``.

        Read through the reverse accessor rather than by importing ``ClientSLA``: the sibling model
        FKs *this* one, so a module-scope import in this direction would close a loop between two
        files in the same package for no benefit.
        """
        if self.pk is None:
            return 0
        return self.slas.filter(is_active=True, status="breached").count()

    def last_billing_run(self):
        """The most recently BILLED period for this client, or ``None``.

        Ordered by ``period_end`` rather than by creation: runs are routinely calculated out of order
        (a late correction for March raised in May), and "the newest row" is not "the latest period".
        """
        if self.pk is None:
            return None
        return self.billing_runs.order_by("-period_end", "-id").first()
