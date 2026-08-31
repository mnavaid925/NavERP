"""Procurement 6.14 Spend Analytics & Reporting — MaverickSpendFinding [MSF-].

**Maverick Spend Tracking** is one of the five NavERP.md bullets in this sub-module. A finding is
one piece of spend that went around the process we agreed: bought with no contract behind it,
invoiced with no order, ordered with no requisition, bought off-catalogue, bought from a
non-preferred supplier, paid above the contracted price, placed with a blocked supplier, or split
into small orders to duck an approval threshold.

**Ownership (L29/L36).** 6.14 is a READ-ONLY analytics pass over spend that already exists. This
model writes NOTHING to ``accounting.*`` — no Bill, no JournalEntry, no Budget, no Payment. It
points at the documents that already carry the money (``procurement.SupplierInvoice`` /
``SupplierInvoiceLine`` from 6.13, ``scm.PurchaseOrder`` from 4.1) and never re-declares one. A
finding is a LEAF: its evidence lives on the source documents it points at, so there is no child
table here.

**Why the dimensions are STAMPED.** ``vendor`` / ``category`` / ``org_unit`` / ``contract`` /
``catalog_item`` are written at detection time rather than resolved on read. The maverick board
groups by every one of them; resolving them live would mean a four-way join (and, for
``org_unit``, a three-hop nullable ``Coalesce`` chain) on every dashboard render. Stamping them
turns the board into one grouped aggregate per axis.

**Status moves only through the four verb methods at the bottom of this class.** Each re-checks
its own guard INSIDE itself and returns a bool: hiding a button in a template does not stop a
direct POST, and a double-submitted disposition must not be audited twice. ``status`` is
``editable=False`` for the same reason, which is also why it is not on the form.

**Detection is idempotent.** ``scan()`` UPSERTS on ``dedupe_key`` — re-running it over the same
window refreshes the figures on findings that already exist and never mints a second row for the
same fact. It also NEVER re-opens a finding somebody has already disposed of: a justified,
remediated or dismissed row keeps its disposition and only has its amount/detail refreshed.

**Import discipline.** Every cross-entity FK below is a STRING. The sibling MODEL classes that
``scan()`` needs are imported INSIDE the methods that use them, not at module level: this module
is imported while ``apps.procurement.models.__init__`` is still executing, and 6.13's
``SupplierInvoices`` module itself imports ``apps.accounting.models`` plus two of its own
siblings at module level. A deferred import is the same discipline
``SupplierInvoiceLine.cumulative_invoiced_qty`` already uses, one sub-package further out.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Prefetch
from django.db.models.functions import Coalesce, TruncDate

from apps.procurement.models._base import *  # noqa: F401,F403

# -- money / date guards (L35) ---------------------------------------------------------------
# The money columns on THIS model are DecimalField(18, 2) — deliberately wider than the app's
# usual (14, 2), because a maverick figure is a rolled-up window of spend rather than one line.
# ``q2`` from _base clamps to the (14, 2) ceiling, so it must NOT be used here: it would silently
# truncate a legitimately large figure. ``_money`` below is the (18, 2) equivalent.
MAX_MSF_MONEY = Decimal("9999999999999999.99")

#: The span a date column can actually carry — a driver rejects a year outside 1000-9999, and
#: every figure derived from a date (age, a rolling window) is only meaningful inside it.
_MIN_DATE = date(1900, 1, 1)
_MAX_DATE = date(9999, 12, 31)

#: How many dedupe keys one ``IN (...)`` may carry when ``scan()`` pre-loads the existing findings.
#: The whole point is to replace one SELECT per candidate with a handful of SELECTs total, and a
#: scan can legitimately produce tens of thousands of candidates.
_DEDUPE_LOOKUP_CHUNK = 1000


def _finite(value):
    """``value`` as a finite ``Decimal``, or ``None``.

    ``Decimal("nan")`` and ``Decimal("Infinity")`` both PARSE and then raise on the COMPARISON,
    so finiteness is tested before anything else touches the figure.
    """
    try:
        number = Decimal(value if value is not None else ZERO)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    return number if number.is_finite() else None


def _as_decimal(value):
    """``value`` as a usable ``Decimal`` — ``ZERO`` for anything unusable."""
    number = _finite(value)
    return ZERO if number is None else number


def _money(value):
    """Quantize to 2dp AND clamp to what this model's DecimalField(18, 2) columns hold."""
    number = _as_decimal(value)
    return min(max(number, -MAX_MSF_MONEY), MAX_MSF_MONEY).quantize(Decimal("0.01"))


# -- window constants ------------------------------------------------------------------------
# NOTE FOR THE INTEGRATOR / REVIEWER: ``apps/procurement/analytics.py`` owns the CANONICAL copy of
# these two tuples (itself copied verbatim from apps/scm/analytics.py so SCM 4.11 and 6.14 can
# never disagree about what counts as spend). They are re-declared here because the contract's
# dependency direction is one-way — analytics.py imports models, models NEVER import analytics —
# and a model-level import of the analytics module would invert it. If either list is ever
# changed, change it in BOTH places.

#: Invoice statuses that represent RECOGNISED spend. A draft/parked/void invoice is not money
#: that left the building, and flagging it as maverick would be a false positive.
RECOGNISED_INVOICE_STATUSES = ("approved", "scheduled", "paid")

#: PO statuses that represent COMMITTED spend.
SPEND_PO_STATUSES = ("approved", "sent", "acknowledged", "partially_received", "received",
                     "closed")

#: Contract statuses that COVER a purchase. ``expiring`` is still in force — it is a renewal
#: warning, not a lapse — so buying against it is not maverick.
COVERING_CONTRACT_STATUSES = ("active", "expiring")

REASON_CHOICES = [
    ("no_contract", "No active contract"),
    ("po_less_invoice", "Invoice with no purchase order"),
    ("no_requisition", "PO raised with no requisition"),
    ("off_catalog", "Item not on an approved catalogue"),
    ("non_preferred_vendor", "Bought from a non-preferred supplier"),
    ("price_above_contract", "Price above the contracted/catalogue price"),
    ("suspended_vendor", "Supplier was blocked or suspended"),
    ("split_purchase", "Orders split below an approval threshold"),
]

SEVERITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]

STATUS_CHOICES = [
    ("open", "Open"),
    ("acknowledged", "Acknowledged"),
    ("justified", "Justified - accepted"),
    ("remediated", "Remediated"),
    ("dismissed", "Dismissed - false positive"),
]


class MaverickSpendFinding(TenantNumbered):
    """One piece of spend that went around the agreed process [MSF-].

    Lifecycle::

        open -> acknowledged -> justified | remediated | dismissed
          |                         ^
          +-------------------------+

    ``open`` and ``acknowledged`` are live work; the other three are dispositions and are
    terminal. Every arrow is a verb method at the bottom of this class.

    ``amount`` is what the maverick spend was worth. ``benchmark_amount`` is what it SHOULD have
    cost when a benchmark exists (the catalogue/contract price for the same quantity), and
    ``leakage_amount`` is the derived gap between the two — never negative, because buying BELOW
    the contracted price is not leakage.
    """

    NUMBER_PREFIX = "MSF"

    REASON_CHOICES = REASON_CHOICES
    SEVERITY_CHOICES = SEVERITY_CHOICES
    STATUS_CHOICES = STATUS_CHOICES

    #: Live work — the complement of the three dispositions.
    OPEN_STATUSES = ("open", "acknowledged")
    #: A disposition has been recorded; the finding is filed.
    TERMINAL_STATUSES = ("justified", "remediated", "dismissed")

    #: The severity a detector stamps when it raises a finding. It is a DEFAULT, not a verdict —
    #: ``severity`` is on the form so a buyer can re-grade a row the engine over- or under-called.
    SEVERITY_BY_REASON = {
        "no_contract": "medium",
        "po_less_invoice": "medium",
        "no_requisition": "medium",
        "off_catalog": "low",
        "non_preferred_vendor": "low",
        "price_above_contract": "high",
        "suspended_vendor": "high",
        "split_purchase": "high",
    }

    #: How far a unit price may sit above the catalogue/contract price before it is leakage.
    PRICE_TOLERANCE_PCT = Decimal("5.00")

    #: The rolling window and the order count that make a run of small orders look deliberate.
    SPLIT_WINDOW_DAYS = 30
    SPLIT_MIN_ORDERS = 3

    COVERING_CONTRACT_STATUSES = COVERING_CONTRACT_STATUSES
    RECOGNISED_INVOICE_STATUSES = RECOGNISED_INVOICE_STATUSES
    SPEND_PO_STATUSES = SPEND_PO_STATUSES

    #: GL codes whose spend is NOT addressable by sourcing — statutory tax, duty, payroll and
    #: intercompany settlement. They stay findings (the fact is still true) but drop out of the
    #: maverick-rate DENOMINATOR via ``is_addressable``, because a rate that counts payroll as
    #: "spend we could have put on contract" is not a number anybody can act on. A workspace whose
    #: chart of accounts numbers differently tunes this list; an empty match simply means every
    #: finding is addressable, which is the safe direction (it never UNDER-states the rate).
    NON_ADDRESSABLE_GL_CODES = ("2300", "2310", "2320", "6900", "7100", "7200", "8000")

    #: Defensive ceiling on how many invoice lines one scan pass will read into memory. A scan is
    #: an operator-triggered POST, not a background job; past this the honest answer is "narrow
    #: the window", not a request that never returns.
    SCAN_LINE_LIMIT = 20000

    # -- badge maps (L33) ---------------------------------------------------------------------
    # theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    # badge-slate. A semantic ``badge-success`` / ``badge-danger`` renders COMPLETELY UNSTYLED.
    STATUS_CSS = {
        "open": "badge-red",
        "acknowledged": "badge-amber",
        "justified": "badge-info",
        "remediated": "badge-green",
        "dismissed": "badge-muted",
    }
    SEVERITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-amber",
        "high": "badge-red",
    }

    # -- source pointers (clean() requires AT LEAST ONE) ----------------------------------------
    # All SET_NULL: deleting the evidence must not delete the finding that a decision was recorded
    # against — an orphaned finding still has its stamped dimensions and its disposition note.
    supplier_invoice = models.ForeignKey("procurement.SupplierInvoice", on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name="maverick_findings")
    invoice_line = models.ForeignKey("procurement.SupplierInvoiceLine", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="maverick_findings")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name="procurement_maverick_findings")

    # -- dimensions stamped at detection ---------------------------------------------------------
    #: ALWAYS set — every finding is about somebody we bought from. PROTECT, because deleting a
    #: supplier out from under a live finding would erase who the spend went to.
    vendor = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                               related_name="procurement_maverick_findings")
    #: ``scm.ItemCategory`` is the ONLY taxonomy in the tree. NULL on every PO-basis finding —
    #: ``scm.PurchaseOrderLine`` has no item FK, so a committed-basis row has nothing to resolve
    #: a category through, and a faked join would be worse than an honest ``(Unclassified)``.
    category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name="procurement_maverick_findings")
    #: The department axis stand-in: there is no department column on an invoice, so this is the
    #: 3-hop nullable chain requisition.org_unit -> po.ship_to, resolved ONCE at detection. NULL
    #: for every PO-less invoice, which is why every department breakdown must render an explicit
    #: ``(unassigned)`` bucket.
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_maverick_findings")
    contract = models.ForeignKey("scm.SupplierContract", on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name="procurement_maverick_findings")
    catalog_item = models.ForeignKey("procurement.CatalogItem", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="maverick_findings")

    # -- classification + money --------------------------------------------------------------------
    reason = models.CharField(max_length=24, choices=REASON_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium")
    #: The date of the SPEND, not of the detection — a board that ages by detection date would
    #: reset every time somebody re-ran the scan.
    document_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    benchmark_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    #: DERIVED in ``save()`` — never an editable balance (L29).
    leakage_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO,
                                         editable=False)
    #: The maverick-rate DENOMINATOR exclusion — see ``NON_ADDRESSABLE_GL_CODES``.
    is_addressable = models.BooleanField(default=True)

    # -- governance ---------------------------------------------------------------------------------
    #: What makes a re-scan idempotent. Deterministic from the finding's reason + its source
    #: pointer, so the same fact always resolves to the same row.
    dedupe_key = models.CharField(max_length=120, editable=False)
    #: The human-readable "why", written by the detector that raised it.
    detail = models.TextField(blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    #: Moved ONLY by the four verb methods — ``editable=False`` keeps it off every form.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open",
                              editable=False)
    resolution_note = models.TextField(blank=True, editable=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False,
                                    related_name="procurement_maverick_findings_resolved")
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-document_date", "-id"]
        unique_together = (("tenant", "number"), ("tenant", "dedupe_key"))
        indexes = [
            # Backs the register's status filter and every "what is still open" rollup.
            models.Index(fields=["tenant", "status"], name="prc_msf_tnt_status_idx"),
            # Backs the reason filter and the dashboard's by-reason breakdown.
            models.Index(fields=["tenant", "reason"], name="prc_msf_tnt_reason_idx"),
            # Backs the date-window scan and the monthly trend.
            models.Index(fields=["tenant", "document_date"], name="prc_msf_tnt_docdate_idx"),
            # Backs the supplier filter and the by-supplier league.
            models.Index(fields=["tenant", "vendor"], name="prc_msf_tnt_vendor_idx"),
        ]
        verbose_name = "maverick spend finding"

    def __str__(self):
        return f"{self.number or 'MSF'} · {self.get_reason_display()}"

    # -- dedupe -------------------------------------------------------------------------------

    def build_dedupe_key(self):
        """The deterministic identity of the FACT this finding records.

        Keyed off the source pointer the detector used, so re-running the scan over the same
        window resolves to the same row instead of minting a second one. ``split_purchase`` has
        no single source document — it is a pattern across several orders — so it keys off the
        supplier and the window start, which ``document_date`` carries for that reason.
        """
        reason = self.reason or "unknown"
        if reason == "split_purchase" and self.vendor_id and self.document_date:
            return f"split:{self.vendor_id}:{self.document_date:%Y%m%d}"
        if self.invoice_line_id:
            return f"{reason}:line:{self.invoice_line_id}"
        if self.supplier_invoice_id:
            return f"{reason}:inv:{self.supplier_invoice_id}"
        if self.purchase_order_id:
            return f"{reason}:po:{self.purchase_order_id}"
        # No source pointer at all. ``clean()`` refuses this shape, so it can only be reached by
        # a direct ``objects.create()``; a random token keeps it from colliding with the blank
        # key of another such row and turning a data-entry mistake into an IntegrityError 500.
        return f"{reason}:manual:{secrets.token_hex(8)}"

    # -- validation -----------------------------------------------------------------------------

    def clean(self):
        errors = {}
        tenant_id = self.tenant_id

        if not (self.supplier_invoice_id or self.invoice_line_id or self.purchase_order_id):
            errors["supplier_invoice"] = (
                "Point the finding at an invoice, an invoice line or a purchase order — a "
                "finding with no evidence cannot be reviewed.")

        if self.reason not in dict(REASON_CHOICES):
            errors["reason"] = "Choose a known maverick-spend reason."

        # Cross-tenant guard on every FK. Same tenant is not the same subject: a narrowed
        # <select> is UX, and this is the boundary.
        if tenant_id:
            if self.supplier_invoice_id and self.supplier_invoice.tenant_id != tenant_id:
                errors["supplier_invoice"] = "That invoice belongs to another workspace."
            if self.invoice_line_id and self.invoice_line.invoice.tenant_id != tenant_id:
                # SupplierInvoiceLine has NO tenant column — it is scoped through its header.
                errors["invoice_line"] = "That invoice line belongs to another workspace."
            if self.purchase_order_id and self.purchase_order.tenant_id != tenant_id:
                errors["purchase_order"] = "That purchase order belongs to another workspace."
            if self.vendor_id and self.vendor.tenant_id != tenant_id:
                errors["vendor"] = "That supplier belongs to another workspace."
            if self.category_id and self.category.tenant_id != tenant_id:
                errors["category"] = "That category belongs to another workspace."
            if self.org_unit_id and self.org_unit.tenant_id != tenant_id:
                errors["org_unit"] = "That department belongs to another workspace."
            if self.contract_id and self.contract.tenant_id != tenant_id:
                errors["contract"] = "That contract belongs to another workspace."
            if self.catalog_item_id and self.catalog_item.tenant_id != tenant_id:
                errors["catalog_item"] = "That catalogue entry belongs to another workspace."

        if self.invoice_line_id and self.supplier_invoice_id:
            if self.invoice_line.invoice_id != self.supplier_invoice_id:
                errors["invoice_line"] = "That line belongs to a different invoice."

        if self.document_date is not None and not (_MIN_DATE <= self.document_date <= _MAX_DATE):
            errors["document_date"] = "Enter a document date between 1900 and 9999."

        for name in ("amount", "benchmark_amount"):
            raw = getattr(self, name)
            if raw is None:
                continue
            value = _finite(raw)
            if value is None or value.copy_abs() > MAX_MSF_MONEY:
                errors[name] = "Enter an amount below 10,000,000,000,000,000."

        # Pre-check the computed dedupe key against this workspace's rows, so a hand-raised
        # duplicate renders as a friendly field error instead of the unique constraint 500ing
        # the POST. Skipped for the random no-pointer key, which cannot collide by construction.
        has_pointer = bool(self.supplier_invoice_id or self.invoice_line_id
                           or self.purchase_order_id)
        if tenant_id and has_pointer and not errors:
            key = self.dedupe_key or self.build_dedupe_key()
            clash = (type(self).objects.filter(tenant_id=tenant_id, dedupe_key=key)
                     .exclude(pk=self.pk))
            if clash.exists():
                errors["reason"] = (
                    "That finding already exists for this document — open the existing one "
                    "instead of raising a second.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.dedupe_key:
            self.dedupe_key = self.build_dedupe_key()[:120]
        benchmark = self.benchmark_amount
        if benchmark is None:
            self.leakage_amount = ZERO
        else:
            # Never negative: buying BELOW the contracted price is not leakage.
            self.leakage_amount = _money(
                max(ZERO, _as_decimal(self.amount) - _as_decimal(benchmark)))
        # ``update_fields`` callers (the verbs) must still get the derived column written.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            fields = set(update_fields)
            if {"amount", "benchmark_amount"} & fields:
                fields.update({"leakage_amount", "dedupe_key"})
                kwargs["update_fields"] = sorted(fields)
        super().save(*args, **kwargs)

    # -- derived ---------------------------------------------------------------------------------

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def severity_css(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def is_resolved(self):
        return self.status in self.TERMINAL_STATUSES

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def age_days(self):
        """Whole days this finding has been sitting in the queue.

        Measured from DETECTION, not from the document date: the question a workqueue answers is
        "how long has nobody looked at this", and a six-month-old invoice detected yesterday is
        one day of unreviewed work, not a hundred and eighty.
        """
        if self.detected_at is None:
            return 0
        return max(0, (timezone.now() - self.detected_at).days)

    @property
    def variance_pct(self):
        """How far above the benchmark this spend landed, as a percentage. ``None`` with no
        benchmark, and ``None`` on a zero benchmark — dividing by it would be a fabricated
        infinity rather than a variance."""
        benchmark = _finite(self.benchmark_amount) if self.benchmark_amount is not None else None
        if benchmark is None or benchmark == ZERO:
            return None
        gap = _as_decimal(self.amount) - benchmark
        return (gap / benchmark * Decimal("100")).quantize(Decimal("0.01"))

    @classmethod
    def default_severity(cls, reason):
        return cls.SEVERITY_BY_REASON.get(reason, "medium")

    # -- disposition verbs -----------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool, and each writes only its
    # own columns through update_fields. NOTHING ELSE moves ``status``.

    def acknowledge(self, user):
        """Somebody has seen it and taken ownership. ``open`` → ``acknowledged`` only."""
        if self.status != "open":
            return False
        self.status = "acknowledged"
        self.save(update_fields=["status", "updated_at"])
        return True

    def justify(self, user, note=""):
        """The spend was irregular but defensible — an emergency, a sole source, a one-off."""
        return self._dispose("justified", user, note)

    def remediate(self, user, note=""):
        """The gap has been closed — a contract raised, a PO booked, the catalogue corrected."""
        return self._dispose("remediated", user, note)

    def dismiss(self, user, note=""):
        """A false positive — the detector was wrong about this row."""
        return self._dispose("dismissed", user, note)

    def _dispose(self, status, user, note):
        """Shared body of the three terminal verbs: guard, stamp, save."""
        if not self.is_open:
            return False
        self.status = status
        self.resolution_note = note or ""
        self.resolved_by = user if getattr(user, "is_authenticated", False) else None
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at",
                                 "updated_at"])
        return True

    # -- detection ----------------------------------------------------------------------------------

    @classmethod
    def scan(cls, tenant, start, end, reasons=None, user=None):
        """Run the enabled detectors over ``[start, end)`` and return ``{reason: count}``.

        ``count`` is how many findings were NEWLY RAISED for that reason — an existing finding
        that was merely refreshed is not counted, because "we found 40 things" on the second run
        of an unchanged window would be a lie.

        Idempotent by construction: every candidate carries a deterministic ``dedupe_key`` and is
        UPSERTED on it. A finding somebody has already disposed of (justified / remediated /
        dismissed) keeps its disposition — only its amount, benchmark and detail are refreshed,
        so a re-scan can never quietly re-open settled work.

        The whole pass runs inside one ``transaction.atomic()``: a scan that dies half-way must
        not leave a workspace holding half a board.
        """
        if tenant is None or start is None or end is None or end <= start:
            return {}

        # An unknown reason in ``reasons`` is IGNORED rather than raising: the list arrives from a
        # POST checkbox group, and a hand-edited value must narrow the scan, never 500 it (L11).
        selected = None if reasons is None else set(reasons)
        wanted = [r for r, _label in REASON_CHOICES
                  if selected is None or r in selected]
        if not wanted:
            return {}

        ctx = cls._scan_context(tenant, start, end, wanted)
        candidates = []
        for reason in wanted:
            # ``getattr`` on the class binds ``cls`` for us — these are classmethods.
            detector = getattr(cls, f"_detect_{reason}", None)
            if detector is None:
                continue
            candidates.extend(detector(tenant, start, end, ctx))

        counts = {reason: 0 for reason in wanted}
        existing_by_key = cls._existing_by_key(tenant, candidates)
        with transaction.atomic():
            for row in candidates:
                if cls._upsert(tenant, row, existing_by_key):
                    counts[row["reason"]] = counts.get(row["reason"], 0) + 1
        return counts

    @classmethod
    def _existing_by_key(cls, tenant, candidates):
        """``{dedupe_key: finding}`` for every candidate, in a bounded number of queries.

        The three line-level detectors can emit up to ``SCAN_LINE_LIMIT`` candidates each, so
        looking each one up on its own would be tens of thousands of SELECTs — the seeder's hot
        path as well as the board's scan button. Chunked because an ``IN`` list of forty thousand
        strings is its own problem; the ``(tenant, dedupe_key)`` unique_together backs the lookup.
        """
        keys = sorted({row.get("dedupe_key") for row in candidates if row.get("dedupe_key")})
        found = {}
        for offset in range(0, len(keys), _DEDUPE_LOOKUP_CHUNK):
            chunk = keys[offset:offset + _DEDUPE_LOOKUP_CHUNK]
            found.update({obj.dedupe_key: obj for obj in
                          cls.objects.filter(tenant=tenant, dedupe_key__in=chunk)})
        return found

    @classmethod
    def _upsert(cls, tenant, row, existing_by_key=None):
        """Create or refresh ONE finding. Returns True only when a new row was minted.

        ``existing_by_key`` is the pre-loaded ``{dedupe_key: finding}`` map from
        :meth:`_existing_by_key`; without it this falls back to its own SELECT, which is what the
        map exists to avoid inside ``scan()``'s loop.
        """
        key = row.get("dedupe_key") or ""
        if not key:
            existing = None
        elif existing_by_key is not None:
            existing = existing_by_key.get(key)
        else:
            existing = cls.objects.filter(tenant=tenant, dedupe_key=key).first()
        if existing is None:
            obj = cls(tenant=tenant, **row)
            obj.severity = row.get("severity") or cls.default_severity(row["reason"])
            obj.save()
            if key and existing_by_key is not None:
                # Two detectors CAN produce the same key in one pass; the map has to see the row
                # this call just minted or the second one would hit the unique_together.
                existing_by_key[key] = obj
            return True

        # Refresh the FACTS, never the disposition. ``status`` / ``resolution_note`` /
        # ``resolved_by`` / ``resolved_at`` are deliberately absent from this list.
        existing.amount = row.get("amount", existing.amount)
        existing.benchmark_amount = row.get("benchmark_amount")
        existing.detail = row.get("detail", existing.detail)
        existing.document_date = row.get("document_date", existing.document_date)
        existing.is_addressable = row.get("is_addressable", existing.is_addressable)
        for name in ("category_id", "org_unit_id", "contract_id", "catalog_item_id"):
            if name in row:
                setattr(existing, name, row[name])
        existing.save(update_fields=["amount", "benchmark_amount", "leakage_amount", "detail",
                                     "document_date", "is_addressable", "category",
                                     "org_unit", "contract", "catalog_item", "updated_at"])
        return False

    # -- scan context (every prefetch the detectors share) ---------------------------------------

    @classmethod
    def _scan_context(cls, tenant, start, end, wanted):
        """Everything the detectors need, fetched ONCE.

        A detector that resolved its own catalogue / suspension / category lookups would issue a
        query per invoice line; the whole point of this dict is that a scan is a handful of
        queries whose count does not grow with the number of rows.
        """
        # Deferred (see the module docstring): these live in sibling sub-packages that are still
        # being wired, and 6.13's invoice module imports accounting + two of its own siblings at
        # module level.
        from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem
        from apps.procurement.models.CatalogManagement.Tiers import CatalogPriceTier
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import (
            SupplierInvoiceLine)
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
            SupplierInvoice)
        from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension

        ctx = {}
        wanted = set(wanted)

        # CREDIT MEMOS ARE EXCLUDED FROM EVERY HEADER DETECTOR, not just ``po_less_invoice``.
        # A credit memo is money coming BACK: its line totals are already signed negative, so a
        # plain Sum nets it against the invoice it credits. Raising a finding on one would count
        # the same maverick purchase twice — once as the original spend and again as the refund —
        # and, because a candidate's amount is taken as a magnitude, the refund would ADD to the
        # maverick total instead of reducing it. Debit memos stay: they genuinely increase what
        # we owe. The line-level detectors exclude credit memos for the same reason.
        #
        # ``select_related`` covers every hop the candidate builders walk, including the chained
        # ones: ``_org_unit_for_invoice`` goes invoice -> purchase_order -> requisition ->
        # org_unit, which without the chained hop is three queries per invoice.
        invoices = []
        if wanted & {"no_contract", "po_less_invoice", "suspended_vendor"}:
            invoices = list(
                SupplierInvoice.objects
                .filter(tenant=tenant, status__in=RECOGNISED_INVOICE_STATUSES,
                        invoice_date__gte=start, invoice_date__lt=end)
                .exclude(invoice_type="credit_memo")
                .select_related("vendor", "purchase_order", "purchase_order__requisition",
                                "purchase_order__requisition__org_unit",
                                "purchase_order__ship_to")
                .order_by("invoice_date", "id"))
        ctx["invoices"] = invoices
        invoice_ids = [inv.pk for inv in invoices]

        # invoice -> a category, taken from the first line that actually resolves one. ONE query
        # instead of a walk down the lines of every invoice.
        categories = {}
        gl_codes = {}
        if invoice_ids:
            for inv_id, cat_id, code in (
                    SupplierInvoiceLine.objects
                    .filter(invoice_id__in=invoice_ids)
                    .values_list("invoice_id", "item__category_id", "gl_account__code")
                    .order_by("id")):
                if cat_id and inv_id not in categories:
                    categories[inv_id] = cat_id
                if code:
                    gl_codes.setdefault(inv_id, set()).add(code)
        ctx["invoice_category"] = categories
        ctx["invoice_gl_codes"] = gl_codes

        # supplier -> the windows they are blocked for. Only ``active`` blocks count: a requested
        # or rejected suspension never stopped anybody buying.
        suspensions = {}
        for supplier_id, starts_on, ends_on in (
                VendorSuspension.objects.filter(tenant=tenant, status="active")
                .values_list("supplier_id", "starts_on", "ends_on")):
            suspensions.setdefault(supplier_id, []).append((starts_on, ends_on))
        ctx["suspensions"] = suspensions

        # The approved, active catalogue, indexed the three ways the detectors ask for it.
        needs_catalog = bool({"off_catalog", "non_preferred_vendor", "price_above_contract"}
                             & set(wanted))
        approved_item, approved_part = set(), set()
        preferred_item, preferred_part = {}, {}
        entry_by_item, entry_by_part = {}, {}
        if needs_catalog:
            rows = (CatalogItem.objects
                    .filter(tenant=tenant, status="approved", is_active=True)
                    .select_related("item", "supplier")
                    .prefetch_related(Prefetch(
                        "price_tiers",
                        queryset=CatalogPriceTier.objects.filter(
                            tenant=tenant, status=CatalogPriceTier.ACTIVE_STATUS))))
            for entry in rows:
                part = (entry.supplier_part_no or "").strip().lower()
                if entry.supplier_id and entry.item_id:
                    approved_item.add((entry.supplier_id, entry.item_id))
                    entry_by_item.setdefault((entry.supplier_id, entry.item_id), entry)
                if entry.supplier_id and part:
                    approved_part.add((entry.supplier_id, part))
                    entry_by_part.setdefault((entry.supplier_id, part), entry)
                if entry.is_preferred and entry.supplier_id:
                    if entry.item_id:
                        preferred_item.setdefault(entry.item_id, set()).add(entry.supplier_id)
                    if part:
                        preferred_part.setdefault(part, set()).add(entry.supplier_id)
        ctx["approved_item"] = approved_item
        ctx["approved_part"] = approved_part
        ctx["preferred_item"] = preferred_item
        ctx["preferred_part"] = preferred_part
        ctx["entry_by_item"] = entry_by_item
        ctx["entry_by_part"] = entry_by_part

        # The invoice LINES the three line-level detectors share. Credit memos are excluded: a
        # credit is money coming BACK, and flagging it as maverick spend would double-count the
        # original in the opposite direction.
        ctx["lines"] = []
        if {"off_catalog", "non_preferred_vendor", "price_above_contract"} & set(wanted):
            ctx["lines"] = list(
                SupplierInvoiceLine.objects
                .filter(invoice__tenant=tenant,
                        invoice__status__in=RECOGNISED_INVOICE_STATUSES,
                        invoice__invoice_date__gte=start, invoice__invoice_date__lt=end)
                .exclude(invoice__invoice_type="credit_memo")
                .select_related("invoice", "invoice__vendor", "invoice__purchase_order",
                                "invoice__purchase_order__requisition",
                                "invoice__purchase_order__requisition__org_unit",
                                "invoice__purchase_order__ship_to",
                                "item", "item__category", "gl_account")
                .order_by("id")[:cls.SCAN_LINE_LIMIT])

        # The committed side. ``order_date`` is NULLABLE, so an unstamped PO is dated by its
        # creation instead of being silently dropped out of the window.
        #
        # ``TruncDate`` is safe on this project's MySQL: Django only wraps the column in
        # ``CONVERT_TZ`` — which returns NULL unless the server's timezone tables are loaded —
        # when the active timezone differs from the connection's. ``TIME_ZONE = "UTC"`` and no
        # per-database ``TIME_ZONE`` is set, so the two match and Django emits a bare ``DATE()``.
        # If either ever changes, re-check this annotation before trusting the committed basis.
        ctx["orders"] = []
        if {"no_requisition", "split_purchase"} & set(wanted):
            from apps.scm.models.ProcurementManagement.PurchaseOrders import PurchaseOrder

            ctx["orders"] = list(
                PurchaseOrder.objects
                .filter(tenant=tenant, status__in=SPEND_PO_STATUSES)
                .annotate(doc_date=Coalesce("order_date", TruncDate("created_at"),
                                            output_field=models.DateField()))
                .filter(doc_date__gte=start, doc_date__lt=end)
                .select_related("vendor", "requisition", "requisition__org_unit", "ship_to")
                .order_by("doc_date", "id"))

        return ctx

    # -- shared resolvers ------------------------------------------------------------------------

    @staticmethod
    def _org_unit_for_order(order):
        """The department axis for a PO: the requisition's cost centre, else the ship-to."""
        if order is None:
            return None
        requisition = order.requisition if order.requisition_id else None
        if requisition is not None and requisition.org_unit_id:
            return requisition.org_unit_id
        return order.ship_to_id

    @classmethod
    def _org_unit_for_invoice(cls, invoice):
        """The 3-hop nullable chain, resolved once. NULL for every PO-less invoice."""
        if invoice.purchase_order_id is None:
            return None
        return cls._org_unit_for_order(invoice.purchase_order)

    @classmethod
    def _addressable_codes(cls, codes):
        """Addressable unless EVERY GL code on the document is a non-addressable one.

        "Every", not "any": an invoice that carries one line of duty alongside four lines of goods
        is still spend somebody could have sourced.
        """
        if not codes:
            return True
        return not set(codes).issubset(set(cls.NON_ADDRESSABLE_GL_CODES))

    # -- detectors -------------------------------------------------------------------------------
    # Each returns a list of candidate dicts. None of them writes; ``scan()`` owns the writes so
    # the whole pass is one transaction.

    @classmethod
    def _detect_no_contract(cls, tenant, start, end, ctx):
        """Recognised spend with no contract covering the supplier on the invoice date."""
        from apps.scm.models.SupplierRelationshipManagement.SupplierContracts import (
            SupplierContract)

        vendor_ids = {inv.vendor_id for inv in ctx["invoices"] if inv.vendor_id}
        covers = {}
        if vendor_ids:
            for party_id, contract_id, start_date, end_date in (
                    SupplierContract.objects
                    .filter(tenant=tenant, party_id__in=vendor_ids,
                            status__in=COVERING_CONTRACT_STATUSES)
                    .values_list("party_id", "id", "start_date", "end_date")):
                covers.setdefault(party_id, []).append((contract_id, start_date, end_date))

        rows = []
        for inv in ctx["invoices"]:
            if not inv.vendor_id or inv.invoice_date is None:
                continue
            windows = covers.get(inv.vendor_id, ())
            covered = any(
                (s is None or s <= inv.invoice_date) and (e is None or e >= inv.invoice_date)
                for _cid, s, e in windows)
            if covered:
                continue
            rows.append(cls._invoice_candidate(
                inv, ctx, "no_contract",
                detail=(f"No active or expiring contract covered {inv.vendor} on "
                        f"{inv.invoice_date:%Y-%m-%d}.")))
        return rows

    @classmethod
    def _detect_po_less_invoice(cls, tenant, start, end, ctx):
        """Recognised spend invoiced with no purchase order behind it.

        The ``credit_memo`` test is belt-and-braces — ``_scan_context`` already excludes them from
        ``ctx["invoices"]`` — but it is the one exclusion the contract names explicitly, so it
        stays stated at the point it applies rather than only in the fetch.
        """
        rows = []
        for inv in ctx["invoices"]:
            if inv.purchase_order_id is not None or inv.invoice_type == "credit_memo":
                continue
            rows.append(cls._invoice_candidate(
                inv, ctx, "po_less_invoice",
                detail=(f"Invoice {inv.invoice_number} was booked with no purchase order — the "
                        f"commitment was never approved before the spend happened.")))
        return rows

    @classmethod
    def _detect_no_requisition(cls, tenant, start, end, ctx):
        """A purchase order raised straight to a supplier with no requisition behind it."""
        rows = []
        for order in ctx["orders"]:
            if order.requisition_id is not None or not order.vendor_id:
                continue
            doc_date = getattr(order, "doc_date", None) or order.order_date
            if doc_date is None:
                continue
            rows.append({
                "reason": "no_requisition",
                "purchase_order_id": order.pk,
                "vendor_id": order.vendor_id,
                # scm.PurchaseOrderLine has NO item FK, so the committed basis has nothing to
                # resolve a category through (stand-in 5) — the board renders (Unclassified).
                "category_id": None,
                "org_unit_id": cls._org_unit_for_order(order),
                "document_date": doc_date,
                "amount": _money(order.total),
                "benchmark_amount": None,
                "is_addressable": True,
                "detail": (f"Purchase order {order.number} was raised with no requisition — the "
                           f"need was never justified or approved before the order went out."),
                "dedupe_key": f"no_requisition:po:{order.pk}",
            })
        return rows

    @classmethod
    def _detect_off_catalog(cls, tenant, start, end, ctx):
        """An invoiced line with no approved, active catalogue entry at that supplier."""
        rows = []
        for line in ctx["lines"]:
            invoice = line.invoice
            if not invoice.vendor_id:
                continue
            part = (line.sku_hint or "").strip().lower()
            if line.item_id and (invoice.vendor_id, line.item_id) in ctx["approved_item"]:
                continue
            if part and (invoice.vendor_id, part) in ctx["approved_part"]:
                continue
            if not line.item_id and not part:
                # Nothing to look the catalogue up BY. Silence is the honest answer — calling it
                # off-catalogue would flag every free-text service line in the workspace.
                continue
            label = line.description or line.sku_hint or "line"
            rows.append(cls._line_candidate(
                line, ctx, "off_catalog",
                detail=(f"\"{label}\" is not on an approved catalogue for {invoice.vendor} — the "
                        f"price was not pre-agreed.")))
        return rows

    @classmethod
    def _detect_non_preferred_vendor(cls, tenant, start, end, ctx):
        """The same item is on an approved PREFERRED catalogue entry at a different supplier."""
        rows = []
        for line in ctx["lines"]:
            invoice = line.invoice
            if not invoice.vendor_id:
                continue
            part = (line.sku_hint or "").strip().lower()
            preferred = set()
            if line.item_id:
                preferred |= ctx["preferred_item"].get(line.item_id, set())
            if part:
                preferred |= ctx["preferred_part"].get(part, set())
            if not preferred or preferred == {invoice.vendor_id}:
                continue
            if invoice.vendor_id in preferred:
                # We DID buy from a preferred source; that other suppliers are also preferred is
                # not a finding.
                continue
            label = line.description or line.sku_hint or "line"
            rows.append(cls._line_candidate(
                line, ctx, "non_preferred_vendor",
                detail=(f"\"{label}\" was bought from {invoice.vendor}, but a preferred supplier "
                        f"is on the approved catalogue for it.")))
        return rows

    @classmethod
    def _detect_price_above_contract(cls, tenant, start, end, ctx):
        """A unit price more than ``PRICE_TOLERANCE_PCT`` above the catalogue/contract price."""
        rows = []
        tolerance = Decimal("1") + cls.PRICE_TOLERANCE_PCT / Decimal("100")
        for line in ctx["lines"]:
            invoice = line.invoice
            if not invoice.vendor_id:
                continue
            entry = cls._catalog_entry_for(line, ctx)
            if entry is None:
                continue
            expected = cls._expected_unit_price(entry, line, invoice.invoice_date)
            if expected is None or expected <= ZERO:
                continue
            paid = _as_decimal(line.unit_price)
            if paid <= expected * tolerance:
                continue
            quantity = _as_decimal(line.quantity)
            candidate = cls._line_candidate(
                line, ctx, "price_above_contract",
                detail=(f"Paid {paid} against an expected {expected} per unit at "
                        f"{invoice.vendor} — more than {cls.PRICE_TOLERANCE_PCT}% above the "
                        f"agreed price."))
            candidate["benchmark_amount"] = _money(expected * quantity)
            candidate["catalog_item_id"] = entry.pk
            candidate["contract_id"] = entry.contract_id
            rows.append(candidate)
        return rows

    @classmethod
    def _detect_suspended_vendor(cls, tenant, start, end, ctx):
        """Spend booked against a supplier who was blocked on the invoice date."""
        rows = []
        for inv in ctx["invoices"]:
            if not inv.vendor_id or inv.invoice_date is None:
                continue
            windows = ctx["suspensions"].get(inv.vendor_id, ())
            blocked = any(
                (s is None or s <= inv.invoice_date) and (e is None or e >= inv.invoice_date)
                for s, e in windows)
            if not blocked:
                continue
            rows.append(cls._invoice_candidate(
                inv, ctx, "suspended_vendor",
                detail=(f"{inv.vendor} was under an active block on "
                        f"{inv.invoice_date:%Y-%m-%d}, and this invoice was booked anyway.")))
        return rows

    @classmethod
    def _detect_split_purchase(cls, tenant, start, end, ctx):
        """Several small orders to one supplier that together clear an approval threshold.

        THE CUT LINE (stand-in 7). The ``split_purchase`` REASON ships either way so the schema
        never churns; this rolling-window self-join is the part that may be deferred if the build
        overruns. It is implemented here in memory over the window the scan already fetched, so
        it costs no extra query.

        **6.17 boundary.** This detector answers a PROCESS question — "was an approval threshold
        engineered around?" — and stops there. Intent, collusion, restricted-party screening and
        the rest of fraud-pattern analysis belong to 6.17 Risk & Compliance and are deliberately
        NOT inferred here; a split is a control weakness, and calling it fraud from this module
        would be an accusation the evidence does not support.
        """
        from apps.scm.models.ProcurementManagement.PurchaseRequisitions import PurchaseRequisition

        thresholds = sorted(
            (_as_decimal(amount) for amount, _key, _label in PurchaseRequisition.APPROVAL_TIERS
             if amount is not None),
            reverse=True)
        if not thresholds:
            return []

        by_vendor = {}
        for order in ctx["orders"]:
            doc_date = getattr(order, "doc_date", None) or order.order_date
            if not order.vendor_id or doc_date is None:
                continue
            by_vendor.setdefault(order.vendor_id, []).append((doc_date, order))

        window = timedelta(days=cls.SPLIT_WINDOW_DAYS)
        rows = []
        for vendor_id, entries in by_vendor.items():
            entries.sort(key=lambda pair: (pair[0], pair[1].pk))
            index = 0
            while index < len(entries):
                window_start = entries[index][0]
                bucket = [order for doc_date, order in entries[index:]
                          if doc_date - window_start <= window]
                amounts = [_as_decimal(order.total) for order in bucket]
                total = sum(amounts, ZERO)
                # The strongest reading of the pattern: the HIGHEST threshold every single order
                # stayed under while the run as a whole cleared it.
                breached = (next((t for t in thresholds
                                  if total >= t and all(a < t for a in amounts)), None)
                            if len(bucket) >= cls.SPLIT_MIN_ORDERS else None)
                if breached is None:
                    index += 1
                    continue
                # Windows do not OVERLAP: consuming the orders this one matched stops a run of
                # four small orders raising a finding for the window at order 1 AND another for
                # the window at order 2, which is the same run reported twice.
                index += len(bucket)
                first = bucket[0]
                # ``document_date`` carries the WINDOW START, which is what the dedupe key is
                # built from — a split has no single source document to key on.
                key = f"split:{vendor_id}:{window_start:%Y%m%d}"
                rows.append({
                    "reason": "split_purchase",
                    "purchase_order_id": first.pk,
                    "vendor_id": vendor_id,
                    "category_id": None,
                    "org_unit_id": cls._org_unit_for_order(first),
                    "document_date": window_start,
                    "amount": _money(total),
                    "benchmark_amount": None,
                    "is_addressable": True,
                    "detail": (f"{len(bucket)} orders totalling {_money(total)} were placed with "
                               f"this supplier in {cls.SPLIT_WINDOW_DAYS} days from "
                               f"{window_start:%Y-%m-%d}, each below the {breached} approval "
                               f"threshold the run as a whole clears."),
                    "dedupe_key": key,
                })
        return rows

    # -- candidate builders -------------------------------------------------------------------------

    @classmethod
    def _invoice_candidate(cls, invoice, ctx, reason, *, detail=""):
        """One candidate keyed on an invoice HEADER."""
        return {
            "reason": reason,
            "supplier_invoice_id": invoice.pk,
            "vendor_id": invoice.vendor_id,
            "category_id": ctx["invoice_category"].get(invoice.pk),
            "org_unit_id": cls._org_unit_for_invoice(invoice),
            "document_date": invoice.invoice_date,
            "amount": _money(_as_decimal(invoice.total).copy_abs()),
            "benchmark_amount": None,
            "is_addressable": cls._addressable_codes(ctx["invoice_gl_codes"].get(invoice.pk)),
            "detail": detail,
            "dedupe_key": f"{reason}:inv:{invoice.pk}",
        }

    @classmethod
    def _line_candidate(cls, line, ctx, reason, *, detail=""):
        """One candidate keyed on an invoice LINE."""
        invoice = line.invoice
        code = line.gl_account.code if line.gl_account_id else None
        return {
            "reason": reason,
            "supplier_invoice_id": invoice.pk,
            "invoice_line_id": line.pk,
            "vendor_id": invoice.vendor_id,
            "category_id": line.item.category_id if line.item_id else None,
            "org_unit_id": cls._org_unit_for_invoice(invoice),
            "document_date": invoice.invoice_date,
            "amount": _money(_as_decimal(line.line_total).copy_abs()),
            "benchmark_amount": None,
            "is_addressable": cls._addressable_codes({code} if code else None),
            "detail": detail,
            "dedupe_key": f"{reason}:line:{line.pk}",
        }

    # -- pricing ---------------------------------------------------------------------------------------

    @classmethod
    def _catalog_entry_for(cls, line, ctx):
        """The approved catalogue entry this invoiced line should have been priced against."""
        invoice = line.invoice
        if line.item_id:
            entry = ctx["entry_by_item"].get((invoice.vendor_id, line.item_id))
            if entry is not None:
                return entry
        part = (line.sku_hint or "").strip().lower()
        if part:
            return ctx["entry_by_part"].get((invoice.vendor_id, part))
        return None

    @classmethod
    def _expected_unit_price(cls, entry, line, on_date):
        """What one unit SHOULD have cost: the best active volume break the quantity reaches,
        falling back to the catalogue's list price when no break applies."""
        base = _as_decimal(entry.base_price)
        quantity = _as_decimal(line.quantity)
        best = None
        for tier in entry.price_tiers.all():
            if _as_decimal(tier.min_quantity) > quantity:
                continue
            if on_date is not None:
                if tier.valid_from and tier.valid_from > on_date:
                    continue
                if tier.valid_until and tier.valid_until < on_date:
                    continue
            if best is None or _as_decimal(tier.min_quantity) > _as_decimal(best.min_quantity):
                best = tier
        if best is None:
            return base if base > ZERO else None
        return _as_decimal(best.effective_price(base))
