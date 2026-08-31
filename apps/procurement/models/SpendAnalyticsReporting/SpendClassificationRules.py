"""Procurement 6.14 Spend Analytics & Reporting — SpendClassificationRule.

**What it is.** The explicit, auditable rule table that answers "which category is this line of
spend?" when the line itself cannot say. It is the honest equivalent of the auto-classification
every commercial spend-analytics suite advertises: a buyer writes a rule ("anything from ACME is
Facilities", "GL 6120 is Travel", "SKUs containing 'toner' are Office Supplies"), the rule is read
by a person before it is trusted, and every classification it makes can be traced back to the row
that made it. It is deliberately **NOT** machine learning and must never be labelled "AI" or "ML"
anywhere in this changeset — there is no model, no training set and no probability here.

**Why it has to exist at all.** ``scm.PurchaseOrderLine`` carries NO item FK (verified:
``apps/scm/models/ProcurementManagement/PurchaseOrders.py:172`` — ``item_description`` +
``sku_hint`` + ``gl_account`` only), so on the COMMITTED basis there is no item to read a category
off. And a PO-less service invoice has no order to walk back to. Without this table the category
axis of the whole sub-module would be one enormous "(Unclassified)" bar.

**Configuration master, not a document.** ``TenantOwned``, not ``TenantNumbered`` — nobody quotes
a classification rule by reference in a conversation with a supplier. Same shape as 6.12's
``ReceiptTolerancePolicy`` and 6.3's ``ApprovalRoutingRule``, and for the same reason there is
**no unique_together**: two same-shaped rules at different priorities is a legitimate
configuration (a workspace-wide GL rule PLUS a narrower supplier exception), not a mistake. The
resolver below decides which one wins.

**Zero side effects.** 6.14 is a read-only analytics pass over spend that already exists: this
module writes nothing to ``accounting.*`` — no Bill, no JournalEntry, no Budget, no Payment (L29)
— and nothing to the ``scm`` document spine (L36). The only columns it ever stamps are its OWN
``match_count`` / ``last_matched_at``, and only from the explicit preview verb.

**Derived, never stored (L29).** There is no cached "classified value" column. ``preview()``
aggregates from the source lines every time it is asked; ``match_count`` is a *usage* counter for
the last preview run, not a balance, which is why it is ``editable=False`` and off the form.

**Import discipline.** Every cross-app FK is a STRING. The two sibling model classes this module
reads (``SupplierInvoiceLine``, ``scm.PurchaseOrderLine``) are imported INSIDE the methods that
need them: this sub-package is not wired into ``models/__init__.py`` until the Integrate phase,
and a module-level sibling import that runs while ``apps.procurement.models`` is still
initialising is exactly how an import cycle gets shipped.
"""
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import Coalesce, TruncDate

from apps.procurement.models._base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------------------------
# Vocabulary (module-level constants; also exposed as class attributes below)
# ---------------------------------------------------------------------------------------------

#: How a rule decides whether a line is its business. LOWER ``priority`` wins; ties break on id.
MATCH_TYPE_CHOICES = [
    ("vendor", "Supplier"),
    ("gl_account", "GL Account"),
    ("keyword", "Description / SKU keyword"),
    ("invoice_type", "Invoice Type"),
    ("org_unit", "Department / Cost Centre"),
]

#: Which spend basis a rule governs. ``invoiced`` = recognised supplier invoices,
#: ``committed`` = purchase orders, ``both`` = the default.
APPLIES_TO_CHOICES = [
    ("both", "Invoiced + Committed"),
    ("invoiced", "Invoiced only"),
    ("committed", "Committed (PO) only"),
]

#: The field each ``match_type`` needs before the rule means anything. A ``vendor`` rule with no
#: vendor would match EVERY line, which is why ``clean()`` refuses it (see below).
REQUIRED_FIELD_BY_MATCH_TYPE = {
    "vendor": "vendor",
    "gl_account": "gl_account",
    "keyword": "keyword",
    "invoice_type": "invoice_type",
    "org_unit": "org_unit",
}

# ---------------------------------------------------------------------------------------------
# Spend windows
# ---------------------------------------------------------------------------------------------
# These two tuples are the sub-module's definition of "money that counts", and they are also
# declared in ``apps/procurement/analytics.py`` as this sub-module's single source. A MODEL may
# never import analytics (analytics imports models — the reverse edge is the cycle), so this is
# the model-layer mirror. **They must be changed together**, and analytics.py should import them
# FROM HERE rather than re-declare them, so 6.14 can never hold two answers to "what is spend?".
#
# ``SPEND_PO_STATUSES`` is copied VERBATIM from ``apps/scm/analytics.py:200`` so SCM 4.11's
# committed-spend cube and this one can never disagree about the same purchase orders.

#: Invoice statuses that represent recognised (invoiced) spend. Draft/parked/captured are not
#: recognised yet; void and reversed never were.
RECOGNISED_INVOICE_STATUSES = ("approved", "scheduled", "paid")

#: PO statuses that represent committed money.
SPEND_PO_STATUSES = ("approved", "sent", "acknowledged", "partially_received", "received", "closed")

#: The window ``preview()`` and the rule register report over when the caller names none.
DEFAULT_PREVIEW_DAYS = 90

#: How many recent matched lines a detail page is willing to render.
RECENT_MATCH_LIMIT = 10


def money(value):
    """Quantize a REPORTED money figure to 2dp — deliberately NOT ``q2``.

    ``q2`` clamps to ``MAX_Q2`` (the ceiling of the ``DecimalField(14, 2)`` columns this app
    *writes*). Nothing here is written to a column: these are aggregates over
    ``DecimalField(18, 2)`` line totals, and clamping one would silently understate a large
    workspace's spend on the page rather than protect a column that does not exist.
    """
    return Decimal(value or ZERO).quantize(Decimal("0.01"))


def default_preview_window():
    """``(start, end)`` for the last :data:`DEFAULT_PREVIEW_DAYS`, ``end`` EXCLUSIVE.

    Same contract as ``analytics.range_bounds`` and built on ``timezone.localdate()`` rather than
    ``date.today()`` (L16) so the window follows the workspace's timezone, not the server's.
    ``end`` is tomorrow, so *today's* invoices are inside the window rather than always missing.
    """
    end = timezone.localdate() + timedelta(days=1)
    return end - timedelta(days=DEFAULT_PREVIEW_DAYS), end


def invoiced_line_window(tenant, start, end):
    """Recognised invoice lines for one tenant inside ``[start, end)``.

    The model-layer twin of ``analytics.invoiced_lines`` — defined ONCE here and reused by
    ``preview()``, the register's value stat and the detail page's recent-match list, so those
    three can never describe different populations.

    Credit memos are ALREADY signed negative on ``SupplierInvoiceLine`` (6.13), so a plain
    ``Sum("line_total")`` nets. Nothing here special-cases them.
    """
    from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import (
        SupplierInvoiceLine,
    )

    if tenant is None:
        return SupplierInvoiceLine.objects.none()
    return SupplierInvoiceLine.objects.filter(
        invoice__tenant=tenant,
        invoice__status__in=RECOGNISED_INVOICE_STATUSES,
        invoice__invoice_date__gte=start,
        invoice__invoice_date__lt=end,
    )


def committed_line_window(tenant, start, end):
    """Committed (PO) lines for one tenant inside ``[start, end)``.

    ``PurchaseOrder.order_date`` is NULLABLE (verified: PurchaseOrders.py:47), so the window is
    taken over ``Coalesce(order_date, TruncDate(created_at))``. Dropping the un-stamped orders
    instead would silently shrink committed spend and make the two bases disagree for no reason a
    buyer could see.
    """
    from apps.scm.models import PurchaseOrderLine

    if tenant is None:
        return PurchaseOrderLine.objects.none()
    return (
        PurchaseOrderLine.objects
        .filter(purchase_order__tenant=tenant, purchase_order__status__in=SPEND_PO_STATUSES)
        .annotate(doc_date=Coalesce(
            "purchase_order__order_date",
            TruncDate("purchase_order__created_at"),
            output_field=models.DateField(),
        ))
        .filter(doc_date__gte=start, doc_date__lt=end)
    )


def _invoice_type_choices():
    """``SupplierInvoice.INVOICE_TYPE_CHOICES``, fetched lazily.

    Deferred on purpose: 6.13's entity module must not be imported while THIS sub-package is still
    being initialised by ``models/__init__.py``.
    """
    from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice

    return list(SupplierInvoice.INVOICE_TYPE_CHOICES)


class SpendClassificationRule(TenantOwned):
    """One explicit rule mapping a slice of spend onto an ``scm.ItemCategory``."""

    # Exposed as class attributes as well as module constants so a view, a template, the admin and
    # a test all reach the same vocabulary through the model. (A class body's name lookup falls
    # through to module scope, so these bind the lists defined above — one source, two names.)
    MATCH_TYPE_CHOICES = MATCH_TYPE_CHOICES
    APPLIES_TO_CHOICES = APPLIES_TO_CHOICES
    REQUIRED_FIELD_BY_MATCH_TYPE = REQUIRED_FIELD_BY_MATCH_TYPE
    RECOGNISED_INVOICE_STATUSES = RECOGNISED_INVOICE_STATUSES
    SPEND_PO_STATUSES = SPEND_PO_STATUSES

    #: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    #: badge-slate (L33). A semantic ``badge-success`` renders COMPLETELY UNSTYLED.
    ACTIVE_CSS = {True: "badge-green", False: "badge-muted"}

    name = models.CharField(
        max_length=120,
        help_text="What this rule is for, e.g. 'ACME → Facilities' or 'GL 6120 → Travel'")
    match_type = models.CharField(
        max_length=20, choices=MATCH_TYPE_CHOICES, default="vendor",
        help_text="Which attribute of a spend line this rule reads")

    # -- the five possible subjects; exactly one is required, per match_type ---------------------
    # SET_NULL, deliberately NOT CASCADE: a deleted supplier must not silently take its rule with
    # it, because a rule whose subject vanished still has to be VISIBLE (and refused by clean())
    # rather than disappear from the register the buyer is auditing.
    vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_spend_rules",
        help_text="Supplier whose spend this rule classifies")
    gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_spend_rules",
        help_text="GL account coded on the line")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_spend_rules",
        help_text="Requesting department / cost centre behind the order")
    keyword = models.CharField(
        max_length=120, blank=True,
        help_text="Case-insensitive fragment matched against the line description and SKU hint")
    invoice_type = models.CharField(
        max_length=20, blank=True,
        help_text="Supplier-invoice type (standard, credit memo, service …). Invoiced basis only "
                  "— a purchase order has no invoice type.")

    # -- the taxonomy target --------------------------------------------------------------------
    # PROTECT: deleting a category that a rule still points at would silently re-classify every
    # line the rule governs. The category must be un-wired here first.
    category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.PROTECT,
        related_name="procurement_spend_rules",
        help_text="Category every matching line is classified into")

    priority = models.PositiveSmallIntegerField(
        default=100, help_text="Lower numbers win. Ties break on the rule's id.")
    applies_to = models.CharField(
        max_length=10, choices=APPLIES_TO_CHOICES, default="both",
        help_text="Which spend basis this rule governs")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # -- usage stamps: written ONLY by the preview verb, never by the form ----------------------
    match_count = models.PositiveIntegerField(
        default=0, editable=False,
        help_text="Lines matched by the most recent preview run — a usage counter, not a balance")
    last_matched_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            # Backs the resolver's hot query (tenant + is_active, read in priority order) and the
            # register's default ORDER BY.
            models.Index(fields=["tenant", "is_active"], name="prc_scr_tnt_active_idx"),
            models.Index(fields=["tenant", "match_type"], name="prc_scr_tnt_mtype_idx"),
        ]
        verbose_name = "Spend Classification Rule"
        verbose_name_plural = "Spend Classification Rules"

    def __str__(self):
        # ``category`` is non-nullable, so on an UNSAVED instance (a ModelForm rendering its own
        # errors, the admin's change list on a failed add) ``self.category`` raises
        # RelatedObjectDoesNotExist. Guarded on the id so a validation error page never 500s.
        if not self.category_id:
            return self.name
        return f"{self.name} -> {self.category}"

    # -- validation ----------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        match_type = self.match_type or ""
        if match_type and match_type not in dict(MATCH_TYPE_CHOICES):
            errors["match_type"] = "Unknown match type."
        else:
            # (a) The field this match_type reads MUST be set. A `vendor` rule with no vendor
            #     would match EVERY line on both bases and quietly swallow the whole cube into one
            #     category — the single most damaging thing this table can do.
            required = REQUIRED_FIELD_BY_MATCH_TYPE.get(match_type)
            if required:
                value = getattr(self, f"{required}_id", None) if required in (
                    "vendor", "gl_account", "org_unit") else (getattr(self, required, "") or "").strip()
                if not value:
                    label = dict(MATCH_TYPE_CHOICES)[match_type]
                    errors[required] = f"A '{label}' rule needs this field set."

        # (b) invoice_type must be a real supplier-invoice type, and it only means something on
        #     the invoiced basis — a purchase order has no invoice type at all.
        if match_type == "invoice_type":
            chosen = (self.invoice_type or "").strip()
            if chosen and chosen not in dict(_invoice_type_choices()):
                errors["invoice_type"] = "Unknown invoice type."
            if self.applies_to == "committed":
                errors["applies_to"] = (
                    "An invoice-type rule cannot govern committed (PO) spend — a purchase order "
                    "has no invoice type.")

        # (c) Cross-tenant guard. Same tenant is not the same subject: a narrowed <select> is UX,
        #     and this is the model-level backstop behind the form's own re-check.
        if tenant_id:
            for field in ("vendor", "gl_account", "org_unit", "category"):
                fk_id = getattr(self, f"{field}_id", None)
                if not fk_id:
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    # -- badge helpers (L33: colour-named theme classes only) -----------------------------------

    @property
    def status_css(self):
        return self.ACTIVE_CSS.get(bool(self.is_active), "badge-muted")

    @property
    def status_label(self):
        return "Active" if self.is_active else "Inactive"

    @property
    def subject_label(self):
        """What this rule actually reads, as one readable phrase for a list row."""
        if self.match_type == "vendor":
            return str(self.vendor) if self.vendor_id else "—"
        if self.match_type == "gl_account":
            return str(self.gl_account) if self.gl_account_id else "—"
        if self.match_type == "org_unit":
            return str(self.org_unit) if self.org_unit_id else "—"
        if self.match_type == "keyword":
            return self.keyword or "—"
        if self.match_type == "invoice_type":
            return dict(_invoice_type_choices()).get(self.invoice_type, self.invoice_type or "—")
        return "—"

    # -- row-level matching (PURE; unit-testable) ------------------------------------------------

    @staticmethod
    def _line_order(line):
        """The ``scm.PurchaseOrder`` behind a line of either shape, or ``None``.

        Callers that loop should ``select_related`` the chain
        (``invoice__purchase_order__requisition`` / ``purchase_order__requisition``) — every hop
        walked here is a query when it has not been fetched.
        """
        if hasattr(line, "invoice_id"):
            invoice = getattr(line, "invoice", None)
            return getattr(invoice, "purchase_order", None) if invoice is not None else None
        return getattr(line, "purchase_order", None)

    @classmethod
    def _line_vendor_id(cls, line):
        if hasattr(line, "invoice_id"):
            invoice = getattr(line, "invoice", None)
            return getattr(invoice, "vendor_id", None) if invoice is not None else None
        order = getattr(line, "purchase_order", None)
        return getattr(order, "vendor_id", None) if order is not None else None

    @classmethod
    def _line_org_unit_id(cls, line):
        """The department axis: the 3-hop nullable Coalesce chain, in Python.

        ``requisition.org_unit`` first, then the order's ``ship_to``. NULL for every PO-less
        invoice — which is why every department breakdown in this sub-module has to render an
        explicit "(unassigned)" bucket rather than dropping the rows.
        """
        order = cls._line_order(line)
        if order is None:
            return None
        requisition = getattr(order, "requisition", None)
        org_unit_id = getattr(requisition, "org_unit_id", None) if requisition is not None else None
        return org_unit_id or getattr(order, "ship_to_id", None)

    @classmethod
    def _line_tenant_id(cls, line):
        """Whose workspace a line of either shape belongs to, or ``None``."""
        if line is None:
            return None
        if hasattr(line, "invoice_id"):
            invoice = getattr(line, "invoice", None)
            return getattr(invoice, "tenant_id", None) if invoice is not None else None
        order = getattr(line, "purchase_order", None)
        return getattr(order, "tenant_id", None) if order is not None else None

    def _governs(self, basis):
        """Whether this rule is eligible to judge ``basis`` at all (active + applies_to)."""
        if not self.is_active or basis not in ("invoiced", "committed"):
            return False
        return self.applies_to == "both" or self.applies_to == basis

    def matches(self, line, basis):
        """Does this rule classify ``line`` on ``basis``? PURE — no queries of its own.

        Works on BOTH a ``procurement.SupplierInvoiceLine`` (``basis="invoiced"``) and an
        ``scm.PurchaseOrderLine`` (``basis="committed"``); the two shapes are told apart by the
        presence of ``invoice_id``, never by an isinstance import.

        This is the ROW-LEVEL authority. :meth:`line_filter` is its SQL mirror — the two encode
        the same five rules and **must be changed together**.
        """
        if line is None or not self._governs(basis):
            return False
        is_invoice_line = hasattr(line, "invoice_id")

        if self.match_type == "vendor":
            return bool(self.vendor_id) and self._line_vendor_id(line) == self.vendor_id

        if self.match_type == "gl_account":
            return bool(self.gl_account_id) and getattr(line, "gl_account_id", None) == self.gl_account_id

        if self.match_type == "org_unit":
            return bool(self.org_unit_id) and self._line_org_unit_id(line) == self.org_unit_id

        if self.match_type == "keyword":
            needle = (self.keyword or "").strip().lower()
            if not needle:
                return False
            # Invoice lines carry ``description``; PO lines carry ``item_description``. Both carry
            # ``sku_hint``, which is the only handle a keyed-from-paper line has.
            haystack = " ".join(str(part or "") for part in (
                getattr(line, "description", ""),
                getattr(line, "item_description", ""),
                getattr(line, "sku_hint", ""),
            )).lower()
            return needle in haystack

        if self.match_type == "invoice_type":
            # NEVER matches a PO line: a purchase order has no invoice type, and pretending
            # otherwise would classify committed spend off a field that does not exist.
            if not is_invoice_line or basis != "invoiced" or not self.invoice_type:
                return False
            invoice = getattr(line, "invoice", None)
            return getattr(invoice, "invoice_type", None) == self.invoice_type

        return False

    def line_filter(self, basis):
        """The SQL mirror of :meth:`matches` — a ``Q`` for this basis, or ``None``.

        ``None`` means "this rule can match nothing on this basis" (inactive, wrong
        ``applies_to``, an invoice-type rule against purchase orders, or a rule whose subject was
        never set), and every caller treats that as an empty result rather than as "no filter" —
        an un-filtered queryset here would report the WHOLE workspace's spend as matched.
        """
        if not self._governs(basis):
            return None
        invoiced = basis == "invoiced"

        if self.match_type == "vendor":
            if not self.vendor_id:
                return None
            return Q(invoice__vendor_id=self.vendor_id) if invoiced else \
                Q(purchase_order__vendor_id=self.vendor_id)

        if self.match_type == "gl_account":
            if not self.gl_account_id:
                return None
            return Q(gl_account_id=self.gl_account_id)

        if self.match_type == "keyword":
            needle = (self.keyword or "").strip()
            if not needle:
                return None
            text_field = "description" if invoiced else "item_description"
            return Q(**{f"{text_field}__icontains": needle}) | Q(sku_hint__icontains=needle)

        if self.match_type == "invoice_type":
            if not invoiced or not self.invoice_type:
                return None
            return Q(invoice__invoice_type=self.invoice_type)

        if self.match_type == "org_unit":
            if not self.org_unit_id:
                return None
            prefix = "invoice__purchase_order" if invoiced else "purchase_order"
            # Coalesce(requisition.org_unit, ship_to) as a predicate: the requisition's unit when
            # there is one, otherwise the order's ship-to. A null requisition falls through the
            # isnull leg exactly as the Python walk above does.
            return (
                Q(**{f"{prefix}__requisition__org_unit_id": self.org_unit_id})
                | (Q(**{f"{prefix}__requisition__org_unit_id__isnull": True})
                   & Q(**{f"{prefix}__ship_to_id": self.org_unit_id}))
            )

        return None

    def matching_lines(self, start, end, basis="invoiced"):
        """The spend lines this rule matches inside ``[start, end)``, or ``None``.

        ``None`` (rather than an empty queryset) so a caller can tell "this rule does not govern
        this basis" apart from "it governs it and found nothing".
        """
        predicate = self.line_filter(basis)
        if predicate is None or self.tenant_id is None or start is None or end is None or end <= start:
            return None
        window = (invoiced_line_window(self.tenant, start, end) if basis == "invoiced"
                  else committed_line_window(self.tenant, start, end))
        return window.filter(predicate)

    def preview(self, start, end):
        """``{"count": int, "value": Decimal}`` — what this rule would classify in a window.

        Aggregated from the source lines on every call; nothing here is cached in a column (L29).
        Both bases are summed when ``applies_to`` is ``both``, which is the same population the
        cube would classify.
        """
        count = 0
        value = ZERO
        for basis in ("invoiced", "committed"):
            lines = self.matching_lines(start, end, basis)
            if lines is None:
                continue
            agg = lines.aggregate(n=Count("id"), v=Sum("line_total"))
            count += agg["n"] or 0
            value += agg["v"] or ZERO
        return {"count": count, "value": money(value)}

    # -- the resolver the cube calls ---------------------------------------------------------

    @classmethod
    def resolve(cls, line, basis, rules=None):
        """The ``scm.ItemCategory`` this workspace's rules give ``line``, or ``None``.

        ``rules`` is the caller's PRE-FETCHED active-rule list, in ``(priority, id)`` order — a
        cube pass fetches it ONCE and passes it for every line, so classifying ten thousand lines
        costs one query, never one per line. The list is trusted for ORDER, never for TENANCY: it
        is re-filtered here against the line's own workspace, because trusting a caller's list is
        exactly how one workspace's rules would end up classifying another's spend.

        Returns ``None`` when nothing matches; the caller renders "(Unclassified)".
        """
        if line is None:
            return None
        tenant_id = cls._line_tenant_id(line)
        if tenant_id is None:
            return None
        if rules is None:
            rules = list(
                cls.objects.filter(tenant_id=tenant_id, is_active=True)
                .select_related("category")
                .order_by("priority", "id")
            )
        else:
            rules = [rule for rule in rules if rule.tenant_id == tenant_id]
        for rule in rules:
            if rule.matches(line, basis):
                return rule.category
        return None
