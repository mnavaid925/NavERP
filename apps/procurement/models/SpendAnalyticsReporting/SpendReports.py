"""Procurement 6.14 Spend Analytics & Reporting — SpendReport [SPR-] + SpendReportSnapshot.

**Custom Report Builder** bullet. A ``SpendReport`` is a SAVED SET OF CHOICES, not a stored
result: a measure, up to two dimensions, a window, an optional filter and a Top-N cut. Every
figure it shows is computed live by ``apps.procurement.analytics.compute_report`` over spend that
already exists — this sub-module writes NOTHING to ``accounting.*`` (no Bill, no JournalEntry, no
Budget, no Payment) and stores no balance of its own (L29).

The builder is **guided**: each axis is picked from a dropdown whose options are the frozen
``*_CHOICES`` lists below. That is deliberate and it is what makes a saved report auditable —
two people opening the same report see the same query, and a reviewer can read what it asks in
one glance.

**Freezing a run.** ``SpendReportSnapshot`` is the only place a result is ever persisted, and it
is minted exclusively by the ``spendreport_snapshot`` POST — there is no snapshot form and no
snapshot create/edit view by design (the crm ``ReportSnapshot`` precedent, shaped field for
field). Because a snapshot is re-rendered AS-IS and never recomputed, every value
``compute_report`` returns must be JSON-serialisable; the analytics layer owns that contract.

**Import direction.** ``analytics.py`` imports these models; this module NEVER imports analytics.
That one-way edge is what keeps the compute layer free to reach across apps without a cycle.

**Ownership (L29/L36).** Nothing here re-declares a spine entity. Suppliers are ``core.Party``
rows carrying a supplier/vendor ``PartyRole``; the taxonomy is ``scm.ItemCategory`` (the only one
in the tree); the department axis is ``core.OrgUnit``; the account axis is
``accounting.GLAccount``. All four are FK'd BY STRING.
"""
from datetime import date
from decimal import InvalidOperation

from apps.procurement.models._base import *  # noqa: F401,F403

#: Magnitude ceiling of the money column this model carries (``DecimalField(18, 2)``). A hand-fed
#: ``1e400`` parses cleanly as a ``Decimal`` and then dies inside the driver, so the magnitude is
#: checked in ``clean()`` BEFORE anything compares or writes it (L35).
_MONEY_CEILING = Decimal(10) ** 16

#: The span a date column can actually carry (L35 for dates: a driver rejects a year outside
#: 1000–9999, and every window derived from a date pair is only meaningful inside it).
_MIN_DATE = date(1900, 1, 1)
_MAX_DATE = date(9999, 12, 31)


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


# -- frozen choice lists -------------------------------------------------------------------------
#
# Declared at module level AND re-exposed as class attributes: the views hand these straight to a
# template as ``basis_choices`` / ``measure_choices`` / … and the sibling computed pages of this
# sub-module read the same lists, so there is exactly ONE definition of each axis.

#: Which side of the buy a report measures. "Invoiced" is recognised spend (what we owe or have
#: paid); "committed" is PO value (what we have promised). They answer different questions and are
#: never mixed into one figure.
BASIS_CHOICES = [
    ("invoiced", "Invoiced (recognised) spend"),
    ("committed", "Committed (PO) spend"),
]

MEASURE_CHOICES = [
    ("net_spend", "Net spend"),
    ("transaction_count", "Transactions"),
    ("avg_transaction", "Average transaction value"),
    ("supplier_count", "Distinct suppliers"),
    ("maverick_spend", "Maverick spend"),
    ("maverick_pct", "Maverick spend %"),
    ("classified_pct", "Classified spend %"),
    ("leakage", "Contract leakage value"),
]

DIMENSION_CHOICES = [
    ("supplier", "Supplier"),
    ("category", "Category"),
    ("department", "Department / cost centre"),
    ("gl_account", "GL account"),
    ("currency", "Currency"),
    ("month", "Month"),
    ("quarter", "Quarter"),
    ("invoice_type", "Invoice type"),
    ("none", "- none -"),
]

DATE_RANGE_CHOICES = [
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("quarter", "This quarter"),
    ("year", "This year"),
    ("all", "All time"),
    ("custom", "Custom range"),
]

CHART_TYPE_CHOICES = [
    ("bar", "Bar"),
    ("line", "Line"),
    ("pie", "Pie"),
    ("table", "Table only"),
]


class SpendReport(TenantNumbered):
    """One saved, guided spend report [SPR-].

    The row holds only the QUESTION. ``analytics.compute_report(report)`` turns it into
    ``{summary, columns, rows, chart_type, chart_labels, chart_data}`` on every render, so a
    report can never disagree with the documents it reports on.

    ``last_run_at`` is a system stamp written by the run/snapshot POSTs — never a form field, and
    never touched by simply opening the detail page (opening a page is not a run anybody should
    be able to attribute to a colleague).
    """

    NUMBER_PREFIX = "SPR"

    BASIS_CHOICES = BASIS_CHOICES
    MEASURE_CHOICES = MEASURE_CHOICES
    DIMENSION_CHOICES = DIMENSION_CHOICES
    DATE_RANGE_CHOICES = DATE_RANGE_CHOICES
    CHART_TYPE_CHOICES = CHART_TYPE_CHOICES

    #: theme.css defines ONLY badge-green / -red / -amber / -info / -muted / -slate. A semantic
    #: ``badge-success`` renders COMPLETELY UNSTYLED, which is why this map is colour-named (L33).
    BASIS_CSS = {"invoiced": "badge-info", "committed": "badge-slate"}

    # -- identity -------------------------------------------------------------------------------
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    # -- the question ---------------------------------------------------------------------------
    basis = models.CharField(max_length=12, choices=BASIS_CHOICES, default="invoiced")
    measure = models.CharField(max_length=20, choices=MEASURE_CHOICES, default="net_spend")
    dimension_1 = models.CharField(max_length=16, choices=DIMENSION_CHOICES, default="supplier")
    dimension_2 = models.CharField(max_length=16, choices=DIMENSION_CHOICES, default="none")

    # -- the window -----------------------------------------------------------------------------
    date_range = models.CharField(max_length=10, choices=DATE_RANGE_CHOICES, default="last_90")
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)

    # -- optional narrowing ---------------------------------------------------------------------
    # All four are SET_NULL: deleting a supplier or a cost centre must not silently delete the
    # reports that once looked at it.
    vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="procurement_spend_reports")
    category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="procurement_spend_reports")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_spend_reports")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="procurement_spend_reports")
    min_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    # -- presentation ---------------------------------------------------------------------------
    chart_type = models.CharField(max_length=10, choices=CHART_TYPE_CHOICES, default="bar")
    top_n = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="How many grouped rows to keep (1–100); the rest fall into the tail.")
    is_favorite = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=True)

    # -- system stamps --------------------------------------------------------------------------
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="procurement_spend_reports")
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-is_favorite", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "measure"], name="prc_spr_tnt_measure_idx"),
            models.Index(fields=["tenant", "is_favorite"], name="prc_spr_tnt_fav_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    # -- validation -----------------------------------------------------------------------------
    def clean(self):
        errors = {}
        tenant_id = self.tenant_id

        # Two identical axes would group a table by the same column twice and render each row's
        # label beside itself. "none" twice is the legitimate single-figure report.
        if self.dimension_1 == self.dimension_2 and self.dimension_1 != "none":
            errors["dimension_2"] = (
                "Pick a different second dimension, or set it to none.")

        if self.date_range == "custom":
            if not self.date_from:
                errors["date_from"] = "A custom range needs a start date."
            if not self.date_to:
                errors["date_to"] = "A custom range needs an end date."
        for bound in ("date_from", "date_to"):
            value = getattr(self, bound)
            if value is not None and not (_MIN_DATE <= value <= _MAX_DATE):
                errors[bound] = "Enter a date between 1900 and 9999."
        if (self.date_from and self.date_to and "date_from" not in errors
                and "date_to" not in errors and self.date_from > self.date_to):
            errors["date_from"] = "The start date cannot be after the end date."

        if self.min_amount is not None:
            amount = _finite(self.min_amount)
            if amount is None:
                errors["min_amount"] = "Enter a real minimum amount."
            elif amount.copy_abs() >= _MONEY_CEILING:
                errors["min_amount"] = "Enter a minimum amount below 10,000,000,000,000,000."
            elif amount < ZERO:
                errors["min_amount"] = "A minimum amount cannot be negative."

        # A narrowed <select> is UX, not an authorization boundary — re-check every FK here so a
        # crafted POST cannot point a report at another workspace's supplier or cost centre.
        for field_name, label in (("vendor", "supplier"), ("category", "category"),
                                  ("org_unit", "department"), ("gl_account", "GL account")):
            chosen_id = getattr(self, f"{field_name}_id")
            if chosen_id and tenant_id and getattr(self, field_name).tenant_id != tenant_id:
                errors[field_name] = f"That {label} belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    # -- derived --------------------------------------------------------------------------------
    @property
    def basis_css(self):
        """Colour-named badge class for the basis pill (L33)."""
        return self.BASIS_CSS.get(self.basis, "badge-muted")

    @property
    def uses_department_axis(self):
        """True when either axis is the department one.

        The department axis is a nullable 3-hop chain
        (``purchase_order.requisition.org_unit`` falling back to ``purchase_order.ship_to``), so
        every breakdown that uses it carries an explicit "(unassigned)" bucket and prints the
        caveat. Surfaces ask this rather than re-deriving the test.
        """
        return "department" in (self.dimension_1, self.dimension_2)

    @property
    def is_custom_range(self):
        return self.date_range == "custom"


class SpendReportSnapshot(models.Model):
    """A point-in-time frozen run of a :class:`SpendReport`.

    Deliberately a plain ``models.Model`` (not ``TenantOwned``) — the ``crm.ReportSnapshot`` shape
    verbatim: it carries its own ``tenant`` column so it can be fetched
    ``get_object_or_404(..., tenant=request.tenant)`` without walking the parent, and a
    ``generated_at`` authorship stamp instead of created/updated pair, because a snapshot is
    written once and never edited.

    **No form, no create view, no edit view — by design.** The ONLY way a row appears is the
    ``spendreport_snapshot`` POST, which stores the freshly computed, JSON-serialisable result
    verbatim. ``summary`` is the KPI card list; ``data`` is
    ``{columns, rows, chart_type, chart_labels, chart_data}``. Both are re-rendered AS-IS — a
    snapshot that recomputed itself would not be a snapshot.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+",
                               db_index=True)
    report = models.ForeignKey("procurement.SpendReport", on_delete=models.CASCADE,
                               related_name="snapshots")
    title = models.CharField(max_length=160)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="procurement_spend_report_snapshots")
    generated_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(default=list, blank=True)   # [{label, value}, …] KPI cards
    data = models.JSONField(default=dict, blank=True)      # {columns, rows, chart_*}
    row_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["tenant", "report"], name="prc_sprsnap_tnt_rpt_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.generated_at:%Y-%m-%d %H:%M})"
