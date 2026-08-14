"""SCM 4.17 Third-Party Logistics (3PL) — ``ClientRateCard`` + ``ClientRateCardLine``: the tariff.

A **rate card** is the priced agreement between the 3PL and one ``LogisticsClient`` — the document a
``ClientBillingRun`` reads to turn a month of warehouse activity into money. It is the 4.6
``CarrierRateCard`` vocabulary turned around: there the workspace is the SHIPPER being quoted, here
the workspace is the PROVIDER doing the quoting, so the card hangs off a client rather than a
carrier and carries a status ladder, an effective range and a version, because what a client was
billed last quarter must stay readable after this quarter's prices land.

**BACKEND PACKAGE ``ThirdPartyLogistics/`` vs TEMPLATE FOLDER ``templates/scm/3pl/`` — the asymmetry
is the house rule, not a defect.** All sixteen shipped scm template folders use a short slug while
the Python package uses the NavERP sub-module title in PascalCase (``CustomerPortal/`` ↔
``templates/scm/portal/``, ``ContractCompliance/`` ↔ ``templates/scm/compliance/``). Do not "fix"
``3pl/`` into ``thirdpartylogistics/``; the note is repeated here and in ``SKILL.md`` for exactly
that reason (``CustomerPortal/PortalAccounts.py:45-47`` carries the same one).

--------------------------------------------------------------------------------------------------
THE FOUR DECISIONS A READER SHOULD NOT HAVE TO REDISCOVER
--------------------------------------------------------------------------------------------------
1. **The overlap guard is the whole point of the status ladder.** Two ``active`` cards whose
   effective ranges overlap means the billing run has two prices for the same day and picks one by
   accident. :meth:`ClientRateCard.overlapping_active_card` is therefore consulted from THREE places
   that must not disagree — ``clean()`` (so it holds against a management command and a shell), the
   form (so a user mistake is a field error rather than a 500), and ``clientratecard_activate`` (so
   a card that was drafted while another was live cannot be promoted into a conflict). One
   implementation, three callers. ``effective_to = NULL`` means **open-ended = +infinity**, which is
   why every leg of that query carries its own ``isnull`` term.

2. **The rating model is a CLOSED REGISTRY, deliberately, and it will not grow an expression
   language.** ``charge_basis`` is a fixed vocabulary and tiering is two plain columns
   (``tier_from`` / ``tier_to``) rather than a formula field. That is the ``KpiTarget`` refusal
   verbatim: the moment a rate line can hold an expression, the billing run stops being auditable
   and every price becomes a small program nobody reviewed. A basis this app cannot MEASURE yet
   (``MANUAL_ONLY_BASES`` — per_sqft, per_cbm, per_kg, per_hour, per_carton, pct_of_value) is still
   PRICEABLE here; the run writes those lines with ``quantity=0`` and ``needs_manual_quantity=True``
   and says which measurement is missing. A guessed conversion factor would be a bill nobody could
   defend.

3. **The line has NO tenant column.** It is a pure child reached through ``rate_card.tenant`` (and,
   equivalently, ``rate_card.client.tenant``) — the ``CarrierRateCard`` / ``SalesOrderLine`` /
   ``LaborPlanLine`` convention. A second tenant FK would be a second answer to "whose row is this",
   and the one that drifts is the one nobody checks. Every view that touches a line resolves it
   through the parent, never on its own pk.

4. **Nothing here is a stored balance and nothing here posts to the ledger** (L29). The card holds
   prices; the money is ``ClientBillingRun``'s, and it stops at a DRAFT ``accounting.Invoice``.
   ``active_line_count`` is a query, not a column.

**Nothing writes ``expired``.** The status exists in the vocabulary and is reachable by an edit, but
4.17 ships no scheduler and no date-roll pass, so a card whose ``effective_to`` has gone by stays
``active`` until a human supersedes it. That is stated rather than papered over: a status that
looked automatic and was not would be worse than one that is honestly manual.
"""
from django.core.exceptions import NON_FIELD_ERRORS

from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — the 4.17 vocabulary module is owned by the `LogisticsClients` entity
# file and is imported the same way `InventoryManagement/Locations.py` imports the models-root
# `_choices`. It imports nothing itself (not even `_base`), so no cycle is possible.
from apps.scm.models.ThirdPartyLogistics._choices import (
    CHARGE_BASIS_CHOICES,
    CHARGE_CATEGORY_CHOICES,
    CHARGE_CATEGORY_CSS,
    EDITABLE_RATE_CARD_STATUSES,
    MANUAL_ONLY_BASES,
    MAX_RATE_CARD_LINES,
    PERIODIC_BASES,
    RATE_CARD_STATUS_CHOICES,
    RATE_CARD_STATUS_CSS,
    RATE_PERIOD_CHOICES,
)


class ClientRateCard(TenantNumbered):
    """A versioned, effective-dated price list for one 3PL client [TAR-].

    ``client`` is PROTECT: a tariff is the evidence of what a client agreed to pay, so deleting the
    client out from under it would leave a priced document pointing at nobody. The delete view
    counts the protected children first and steers to a status change instead of letting
    ``ProtectedError`` become a 500.
    """

    NUMBER_PREFIX = "TAR"

    #: Read by BOTH boundaries — `ClientRateCard.clean()` here and `ClientRateCardForm.clean()`'s
    #: `_reject_foreign` call — so a pointer added later is covered at the form the moment it is
    #: named here. `currency` is deliberately absent: `accounting.Currency` is GLOBAL (no tenant
    #: column), so a tenant comparison on it would always fail.
    TENANT_SCOPED_FKS = ("client",)

    STATUS_CHOICES = RATE_CARD_STATUS_CHOICES
    STATUS_CSS = RATE_CARD_STATUS_CSS
    EDITABLE_STATUSES = EDITABLE_RATE_CARD_STATUSES

    client = models.ForeignKey("scm.LogisticsClient", on_delete=models.PROTECT,
                               related_name="rate_cards")
    name = models.CharField(max_length=120,
                            help_text="What this tariff is, e.g. 'Standard storage & handling 2026'")
    version = models.PositiveSmallIntegerField(
        default=1,
        help_text="Bump this rather than editing a superseded card — last quarter's bill has to "
                  "stay readable")
    status = models.CharField(max_length=12, choices=RATE_CARD_STATUS_CHOICES, default="draft")
    effective_from = models.DateField(help_text="First day this tariff prices")
    effective_to = models.DateField(
        null=True, blank=True,
        help_text="Last day this tariff prices; blank = open-ended (until it is superseded)")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="+",
                                 help_text="Blank falls back to the client's own currency")
    notes = models.TextField(blank=True)

    class Meta:
        # Newest first: the card somebody wants is almost always the one that just started pricing.
        ordering = ["-effective_from", "-version", "-id"]
        unique_together = (("tenant", "number"), ("tenant", "client", "name", "version"))
        indexes = [
            # Covers both list ORDER-BY-after-filter shapes the pages actually use: the ?client=
            # dropdown, the ?status= dropdown, and the detail page's "which card prices this day"
            # lookup, which always narrows on (tenant, client) first.
            models.Index(fields=["tenant", "client", "status"], name="scm_tar_tnt_cli_st_idx"),
        ]

    # ---------------------------------------------------------------------------------------------
    # Derived — none of these is a column
    # ---------------------------------------------------------------------------------------------
    @property
    def status_css(self):
        """The colour-named theme.css badge class for this status.

        COLOUR-NAMED ONLY (badge-green / -red / -amber / -info / -muted / -slate). A semantic
        ``badge-success`` / ``badge-danger`` does not exist in theme.css and renders UNSTYLED (L33).
        """
        return RATE_CARD_STATUS_CSS.get(self.status, "badge-muted")

    @property
    def is_editable(self):
        """Whether the header and its lines may still be changed.

        Declared ONCE and read by the edit view, both line-write views and the ``can_edit`` /
        ``can_add_line`` flags handed to the template, so a button and the route behind it cannot
        disagree about whether an action is available (the 4.10 "two of three shapes" finding).
        """
        return self.status in EDITABLE_RATE_CARD_STATUSES

    @property
    def active_line_count(self):
        """How many lines would actually price. A QUERY, deliberately — never a stored counter.

        **Do not call this per row from a list page**: it is one COUNT per card. The list annotates
        ``line_count`` on the queryset instead (the 4.13 ``asset_list`` finding).
        """
        return self.lines.filter(is_active=True).count()

    def is_effective_on(self, day=None):
        """Does this card price ``day``? ``effective_to = None`` is +infinity.

        Says nothing about ``status`` on purpose — "is this range live today" and "has anybody
        activated it" are two different questions, and the detail page asks them separately so a
        draft that is dated for today can be told apart from a draft that is dated for next year.
        """
        day = day or timezone.localdate()
        if self.effective_from is None:
            return False
        if day < self.effective_from:
            return False
        return self.effective_to is None or day <= self.effective_to

    def overlapping_active_card(self):
        """Another ACTIVE card of this client whose effective range overlaps this one, or ``None``.

        The single implementation behind the guard in :meth:`clean` and in
        ``clientratecard_activate``. Two active cards over one day is the one mistake that silently
        bills a client at a price nobody chose — the run would pick whichever row the database
        returned first.

        Independent of ``self.status``, so the activate verb can ask "would promoting this collide?"
        BEFORE flipping the column. Ranges are half-open at neither end: ``effective_to IS NULL``
        counts as +infinity on both sides, which is why each leg carries its own ``isnull`` term
        rather than relying on a comparison against NULL (which is neither true nor false in SQL and
        would silently drop the row from the guard).
        """
        if not self.client_id or self.effective_from is None:
            return None
        qs = type(self).objects.filter(client_id=self.client_id, status="active")
        if self.tenant_id:
            qs = qs.filter(tenant_id=self.tenant_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        # The other card must not END before this one starts …
        qs = qs.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from))
        # … and must not START after this one ends (an open-ended self overlaps everything after it).
        if self.effective_to is not None:
            qs = qs.filter(effective_from__lte=self.effective_to)
        return qs.select_related("client").order_by("effective_from", "id").first()

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Three guards. Every error is keyed on a field ``ClientRateCardForm`` actually carries.

        That is not a stylistic point: ``BaseModelForm._post_clean`` hands each key straight to
        ``Form.add_error``, which **raises ``ValueError`` for a key that is not a form field** — a
        500 instead of a rendered message.

        Every FK is read behind an ``_id`` test so an unsaved instance validates instead of raising
        ``RelatedObjectDoesNotExist`` out of the attribute access.
        """
        errors = {}

        if (self.effective_from is not None and self.effective_to is not None
                and self.effective_to < self.effective_from):
            errors["effective_to"] = (
                f"This tariff would stop pricing ({self.effective_to}) before it starts "
                f"({self.effective_from}).")

        if self.client_id and self.tenant_id:
            client = getattr(self, "client", None)
            if client is not None and client.tenant_id != self.tenant_id:
                errors["client"] = "That client belongs to another workspace."

        # Only an ACTIVE card can collide — a draft is a proposal and several may sit side by side
        # while prices are being negotiated. Skipped when the range itself is already wrong, so the
        # user fixes one problem at a time.
        if self.status == "active" and not errors:
            conflict = self.overlapping_active_card()
            if conflict is not None:
                span = conflict.effective_to or "open-ended"
                errors["effective_from"] = (
                    f"{conflict.number} is already the active tariff for this client from "
                    f"{conflict.effective_from} to {span}, and these ranges overlap. Two active "
                    f"cards over one day means the billing run has two prices for it — supersede "
                    f"{conflict.number} first, or narrow this card's dates.")

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        # Guarded: `write_audit_log` calls str() on an instance that may not have its parent loaded,
        # and an unsaved/unparented card must render rather than raise.
        code = self.client.code if self.client_id else "—"
        return f"{self.number or 'TAR'} · {code} v{self.version}"


class ClientRateCardLine(models.Model):
    """One priced charge on a tariff. **No tenant column** — reached through ``rate_card``.

    A line is (category, basis, rate) plus the three narrowing dimensions the run honours: an
    optional tier band, an optional location and an optional item category. ``included_quantity`` is
    the allowance netted off before the rate applies; ``minimum_charge`` is the floor
    ``ClientBillingRunLine.save()`` raises a computed amount to.
    """

    rate_card = models.ForeignKey("scm.ClientRateCard", on_delete=models.CASCADE,
                                 related_name="lines")
    charge_category = models.CharField(max_length=16, choices=CHARGE_CATEGORY_CHOICES)
    charge_basis = models.CharField(max_length=20, choices=CHARGE_BASIS_CHOICES)
    description = models.CharField(max_length=255,
                                   help_text="Printed on the bill — write it as the client reads it")
    # 4dp, matching every other rate in this app: a per-unit handling fee is routinely fractions of
    # a cent. NOTE the drafted invoice cannot carry this precision — `accounting.InvoiceLine.
    # unit_price` is (14,2) — which is why `ClientBillingRun.draft_invoice()` writes the LINE AMOUNT
    # as the unit price and puts the real quantity x rate in the description.
    rate = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                               validators=[MinValueValidator(ZERO)])
    period = models.CharField(
        max_length=6, choices=RATE_PERIOD_CHOICES, blank=True,
        help_text="Required on a periodic basis (storage, dedicated space, flat recurring); must be "
                  "blank on a per-event one")
    included_quantity = models.DecimalField(
        max_digits=16, decimal_places=4, default=0, validators=[MinValueValidator(ZERO)],
        help_text="Allowance netted off before the rate applies")
    minimum_charge = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(ZERO)],
        help_text="Floor for this line's computed amount")
    tier_from = models.DecimalField(max_digits=16, decimal_places=4, default=0,
                                    validators=[MinValueValidator(ZERO)],
                                    help_text="Band start, inclusive")
    tier_to = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True,
                                  validators=[MinValueValidator(ZERO)],
                                  help_text="Band end, EXCLUSIVE; blank = no upper bound")
    applies_to_location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Price only what sits in this location; blank = anywhere")
    applies_to_item_category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Price only this category; blank = every item")
    # Maps 1:1 onto the verified `accounting.InvoiceLine.gl_account`, so the drafted invoice lands on
    # the right revenue account without SCM ever posting a journal (L29). Blank falls back to the
    # client's `default_revenue_account`.
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")
    is_active = models.BooleanField(default=True,
                                    help_text="Switch a charge off without losing what it priced")

    class Meta:
        # Grouped the way the bill reads: storage, then receiving, then outbound … and within a
        # basis, cheapest band first so a tiered ladder renders in order.
        ordering = ["charge_category", "charge_basis", "tier_from", "id"]

    @property
    def category_css(self):
        """Colour-named theme.css badge class for the charge category (L33 — never badge-success)."""
        return CHARGE_CATEGORY_CSS.get(self.charge_category, "badge-muted")

    @property
    def needs_manual_quantity(self):
        """True when this basis is priceable but not yet MEASURABLE by anything in the app.

        ``Item`` carries no weight and no dimensions, ``Location`` has no area column and per-client
        labour is 4.14's, so per_sqft / per_cbm / per_kg / per_hour / per_carton / pct_of_value bill
        at quantity 0 with the missing measurement named on the line. The chip on the detail page
        reads off this, so the card SAYS what the run will do before anybody presses Calculate.
        """
        return self.charge_basis in MANUAL_ONLY_BASES

    def applies_to_quantity(self, quantity):
        """Is ``quantity`` inside this line's tier band? Half-open: ``[tier_from, tier_to)``.

        Half-open so consecutive bands (0–100, 100–500, 500–) tile the number line with no gap and
        no double-count — an inclusive upper bound would price 100 units on two lines.
        """
        if quantity is None:
            return False
        if quantity < (self.tier_from or ZERO):
            return False
        return self.tier_to is None or quantity < self.tier_to

    def clean(self):
        """Five guards plus the line cap. Keys are all on ``ClientRateCardLineForm``.

        ``rate_card`` is NOT a form field (it comes from the route — a parent pk in a POST body is
        how a caller grafts a priced line onto somebody else's tariff), so any error about the
        parent is raised WITHOUT a key and lands on ``__all__``, which ``add_error`` accepts.
        """
        errors = {}
        card = getattr(self, "rate_card", None) if self.rate_card_id else None
        client = getattr(card, "client", None) if card is not None and card.client_id else None
        tenant_id = card.tenant_id if card is not None else None

        # (a) an empty or inverted band can never match anything.
        if self.tier_to is not None and self.tier_to <= (self.tier_from or ZERO):
            errors["tier_to"] = (
                f"The band ends at {self.tier_to} and starts at {self.tier_from or ZERO}, so it "
                "covers no quantity at all. Leave it blank for an open-ended top band.")

        # (b)/(c) the period and the basis have to agree — a per-order fee is not charged "per
        # month", and a storage rate with no period is a number with no meaning.
        periodic = self.charge_basis in PERIODIC_BASES
        if self.period and not periodic:
            errors["period"] = (
                f"{self.get_charge_basis_display()} is charged per event, so it takes no period. "
                "Clear the period, or pick a recurring basis.")
        elif periodic and not self.period:
            errors["period"] = (
                f"{self.get_charge_basis_display()} is a recurring charge, so it needs a period — "
                "per day, per week or per month. Without one the rate prices nothing.")

        # (d) cross-client and cross-tenant contamination on the two narrowing FKs.
        location = getattr(self, "applies_to_location", None)
        if location is not None:
            if tenant_id is not None and location.tenant_id != tenant_id:
                errors["applies_to_location"] = "That location belongs to another workspace."
            elif (client is not None
                  and getattr(location, "owner_client_id", None) not in (None, client.pk)):
                errors["applies_to_location"] = (
                    f"{location.code} is dedicated to another client, so pricing this client's "
                    "storage against it would bill them for somebody else's space.")
        category = getattr(self, "applies_to_item_category", None)
        if category is not None and tenant_id is not None and category.tenant_id != tenant_id:
            errors["applies_to_item_category"] = "That item category belongs to another workspace."
        account = getattr(self, "gl_account", None)
        if account is not None and tenant_id is not None and account.tenant_id != tenant_id:
            errors["gl_account"] = "That GL account belongs to another workspace."

        # (e) dedicated space billed to a client who has none is a charge with no basis in the
        # contract — and it is exactly the line somebody copies from another client's card.
        if (self.charge_basis == "dedicated_space" and client is not None
                and client.space_model == "shared"):
            errors["charge_basis"] = (
                f"{client.code} is on a shared-space model with no committed area or pallet "
                "positions, so there is no dedicated space to bill. Change the client's space "
                "model first, or price this as storage.")

        # The cap. Bounded on the CREATE path only — an existing row being edited does not add one,
        # and refusing to save it would strand a card that somehow exceeded the cap. Keyed on
        # NON_FIELD_ERRORS because it is about the PARENT, and `rate_card` is not a form field:
        # `ModelForm._update_errors` accepts '__all__' and raises ValueError on any other key it
        # does not carry. COLLECTED, never `raise`d on the spot — an early raise here would throw
        # away every field error found above and make the user fix one problem per round trip.
        if self.pk is None and card is not None and card.lines.count() >= MAX_RATE_CARD_LINES:
            errors[NON_FIELD_ERRORS] = (
                f"{card.number} already carries the maximum of {MAX_RATE_CARD_LINES} rate lines. "
                "A tariff that large is almost certainly two tariffs — start a new version "
                "instead.")

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        label = self.description or self.get_charge_basis_display()
        if self.rate_card_id:
            return f"{self.rate_card.number} · {label}"
        return label
