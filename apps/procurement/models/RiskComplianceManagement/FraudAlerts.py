"""Procurement 6.17 Risk & Compliance Management — FraudAlert [FRD-].

**Fraud Detection Rules** is NavERP.md bullet 4 of this sub-module. An alert is one fact about
procurement INTEGRITY that a deterministic rule found and a human has to adjudicate: a supplier
that shares an identity attribute with an employee, a requisition signed off by the person who
raised it, two supplier records that look like the same company, a purchase order raised after
the invoice it is supposed to authorise, new spend against a supplier whose sanctions match was
never resolved, or a brand-new supplier taking high-value spend immediately.

**These are RULES, not AI.** Every one of them is deterministic SQL plus arithmetic over rows
this workspace already holds. Nothing here learns, scores by model, or predicts. The six
thresholds that tune them are constants in this module and are rendered READ-ONLY on the scan
page, so a number that decides whether somebody gets accused is visible rather than folkloric.

**Boundary against 6.14 (L29/L36/L37).** ``MaverickSpendFinding`` answers a PROCESS question —
spend that went around the agreed route — and 6.17 answers an INTEGRITY one. The SHAPE of
``scan`` / ``build_dedupe_key`` / ``_existing_by_key`` / ``_upsert`` / ``_scan_context`` is
copied from it deliberately, because idempotent detection is a solved problem here. **None of its
eight reasons is copied.** In particular ``split_purchase`` stays 6.14's: a run of small orders
is a control weakness, and calling it fraud from here would be an accusation the evidence does
not support. The one thing the two modules share by IMPORT rather than by copy is what counts as
spend — ``RECOGNISED_INVOICE_STATUSES`` and ``SPEND_PO_STATUSES`` are imported from
``MaverickFindings`` inside the methods that use them, so two pages can never disagree about it.

**The scan writes NOTHING to the spine.** It reads ``core.*``, ``scm.*`` and this app's own
tables and writes ``FraudAlert`` rows only. It raises no suspension, blocks no invoice, holds no
purchase order and never edits, deactivates or merges a ``core.Party`` — the duplicate-vendor
rule FLAGS a pair and links to both, and merging supplier records stays with 6.4 / ``core.Party``.
Park, do not block: an alert is an accusation waiting for a person, and a rule that acted on its
own would be a rule that punishes on a false positive.

**Detection is idempotent.** Every candidate carries a deterministic ``dedupe_key`` and is
UPSERTED on it, so re-running the scan over the same window refreshes the figures on alerts that
already exist and never mints a second row for the same fact. ``_upsert`` deliberately does not
touch ``status`` / ``resolution_note`` / ``resolved_by`` / ``resolved_at``: a re-scan can never
re-open settled work. The pair rules key off ``min(a, b)``/``max(a, b)`` so the same overlap is
one row whichever party the detector happened to walk first.

**Not buildable, and the page says so.** The vendor bank-detail-change rule that every commercial
product in this space ships has nothing to read here: ``accounting.VendorProfile`` carries no bank
columns and ``accounting.BankAccount`` is the tenant's OWN account, not the supplier's. It is
stated plainly on the scan page rather than silently omitted, because a fraud page that quietly
drops a rule reads as a page that ran it and found nothing.

**Import discipline.** Every cross-entity FK below is a STRING, and the sibling MODEL classes
``scan()`` needs are imported INSIDE the methods that use them: this module is imported while
``apps.procurement.models.__init__`` is still executing, and 6.13's ``SupplierInvoices`` module
itself imports ``apps.accounting.models`` plus two of its own siblings at module level.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models.functions import Coalesce, TruncDate

from apps.procurement.models._base import *  # noqa: F401,F403

# -- money / date guards (L35) ---------------------------------------------------------------
# ``amount`` here is DecimalField(18, 2) — a fraud figure can be a rolled-up run of spend, so it
# is deliberately wider than the app's usual (14, 2). ``q2`` from _base clamps to the (14, 2)
# ceiling and must NOT be used: it would silently truncate a legitimately large figure.
MAX_FRD_MONEY = Decimal("9999999999999999.99")

#: The span a date column can actually carry — a driver rejects a year outside 1000-9999.
_MIN_DATE = date(1900, 1, 1)
_MAX_DATE = date(9999, 12, 31)


def _finite(value):
    """``value`` as a finite ``Decimal``, or ``None``.

    L35, the whole of it: ``Decimal("NaN")`` PARSES without complaint and then raises
    ``InvalidOperation`` on the first ``<`` — an unhandled 500 from a number that looked fine
    going in. ``Decimal("Infinity")`` compares fine and then blows the column width. Both are
    refused HERE, before any comparison or arithmetic happens, so every caller downstream can
    assume ordering is safe.
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
    """Quantize to 2dp AND clamp to what this model's DecimalField(18, 2) column holds."""
    number = _as_decimal(value)
    return min(max(number, -MAX_FRD_MONEY), MAX_FRD_MONEY).quantize(Decimal("0.01"))


def _window_bounds(start, end):
    """``[start, end)`` as aware datetimes, for filtering a DateTimeField against DATE inputs.

    ``TIME_ZONE = "UTC"`` and ``USE_TZ = True``, so the connection and the application agree and
    a day boundary means the same thing in both — re-check this if that ever changes. Filtering a
    ``DateTimeField`` against a bare ``date`` would otherwise compare against midnight-naive and
    emit a RuntimeWarning on every scan.
    """
    return (timezone.make_aware(datetime.combine(start, time.min)),
            timezone.make_aware(datetime.combine(end, time.min)))


# -- rules ------------------------------------------------------------------------------------

RULE_CHOICES = [
    ("vendor_employee_match", "Vendor and employee share an identity attribute"),
    ("self_approval", "Requisition approved by its own requester"),
    ("duplicate_vendor", "Duplicate / shell supplier record"),
    ("backdated_po", "Purchase order raised after the invoice it authorises"),
    ("screening_unresolved", "New spend against an unresolved screening match"),
    ("new_vendor_rush", "New supplier with immediate high-value spend"),
]

SEVERITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]

#: The severity a rule stamps when it raises an alert. A DEFAULT, not a verdict — ``severity``
#: stays on the form so a reviewer can re-grade a row the engine over-called, and ``_upsert``
#: never restamps it on a re-scan.
SEVERITY_BY_RULE = {
    "vendor_employee_match": "high",
    "self_approval": "high",
    "duplicate_vendor": "medium",
    "backdated_po": "medium",
    "screening_unresolved": "high",
    "new_vendor_rush": "medium",
}

STATUS_CHOICES = [
    ("open", "Open"),
    ("investigating", "Under investigation"),
    ("substantiated", "Substantiated"),
    ("unsubstantiated", "Unsubstantiated - false positive"),
    ("referred", "Referred for external action"),
]

#: Live work — the complement of the three dispositions.
OPEN_STATUSES = ("open", "investigating")
#: A disposition has been recorded; the alert is filed.
TERMINAL_STATUSES = ("substantiated", "unsubstantiated", "referred")

#: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33). A semantic badge-success / badge-danger renders COMPLETELY UNSTYLED and
#: still passes every test, so the mapping lives here rather than in template {% if %} ladders.
#:
#: DELIBERATE DEVIATION FROM MaverickSpendFinding, which colours ``open`` red. Here the strongest
#: colour belongs to a SUBSTANTIATED fraud finding, not to an untriaged one. An open alert is a
#: question — a red wall of questions trains people to ignore red, and on this register the row
#: that must never be ignored is the one somebody has already proved.
STATUS_CSS = {
    "open": "badge-amber",
    "investigating": "badge-info",
    "substantiated": "badge-red",
    "unsubstantiated": "badge-muted",
    "referred": "badge-slate",
}
SEVERITY_CSS = {"low": "badge-slate", "medium": "badge-amber", "high": "badge-red"}


# -- tuning constants (rendered READ-ONLY on the scan page) -------------------------------------
# A FraudRule table an operator can edit is a later pass; shipping an editable rule table with no
# scan wired to it would be worse than shipping none. These are what the rules actually use, and
# the scan page renders them so the thresholds behind an accusation are visible.

#: The identity attributes the overlap rule joins vendors to employees on.
OVERLAP_ATTRIBUTES = ("tax_id", "address", "contact")

#: Past this many parties sharing one attribute value, the group is SKIPPED rather than paired.
#: Two hundred suppliers sharing one serviced-office address is a data-quality problem, not
#: 19,900 fraud alerts — and burying a real overlap under them is how a register stops being read.
MAX_GROUP_SIZE = 25

#: Ceiling on how many pairs one attribute may emit in one pass, per rule.
MAX_PAIRS_PER_ATTRIBUTE = 500

#: How new a supplier is, and how long the "rush" window runs for.
NEW_VENDOR_DAYS = 30

#: Spend inside that window at or above which a new supplier is worth a question.
NEW_VENDOR_AMOUNT = Decimal("25000.00")

#: A PO dated a day after its invoice is a clerical lag; a fortnight is a story.
BACKDATE_GRACE_DAYS = 1

#: Defensive ceiling on how many source rows one scan pass reads into memory. A scan is an
#: operator-triggered POST, not a background job; past this the honest answer is "narrow the
#: window", not a request that never returns.
SCAN_ROW_LIMIT = 20000

#: The longest window one scan may cover. Checked ARITHMETICALLY (``(end - start).days``) and
#: never by building the range — materialising 4,000 days to find out that 4,000 is too many IS
#: the payload the cap exists to refuse (L40 §1).
MAX_SCAN_WINDOW_DAYS = 400

#: How many dedupe keys one ``IN (...)`` carries when ``scan()`` pre-loads existing alerts.
_DEDUPE_LOOKUP_CHUNK = 1000

#: Stripped before two supplier names are compared. "Acme Ltd" and "ACME Limited" are one company
#: with two records; the suffix is the noise that hides it.
NAME_SUFFIXES = ("ltd", "limited", "inc", "llc", "plc", "gmbh", "pvt", "co", "company", "corp",
                 "corporation", "sa", "bv", "pte")

#: Party roles that make a party a supplier in this workspace.
_VENDOR_ROLES = ("vendor", "supplier")

#: Dispositions that leave a sanctions hit UNRESOLVED — the whole point of rule 5.
_UNRESOLVED_DISPOSITIONS = ("open", "true_match")

#: Stated on the scan page rather than silently omitted. See the module docstring.
NOT_BUILDABLE_NOTE = (
    "One rule every product in this space ships is NOT implemented here, and this page says so "
    "rather than leaving you to assume it ran: a supplier's bank details changing shortly before "
    "a payment. There is nothing in this system to read it from - accounting.VendorProfile "
    "carries no bank columns, and accounting.BankAccount is this workspace's OWN account rather "
    "than a supplier's. Detecting a change needs a supplier bank-detail field with a change "
    "history behind it, and inventing one that nothing writes to would produce a rule that "
    "always finds nothing and looks like an all-clear."
)


# -- normalisers + maskers -----------------------------------------------------------------------
# The UNMASKED comparison happens inside the scan and is never stored (L20). ``matched_on`` says
# WHICH attribute matched, with enough of the value to recognise it and not enough to leak it.

def _collapse(value):
    """Lower-cased with whitespace runs collapsed to one space."""
    return " ".join((value or "").split()).lower()


def _norm_tax_id(value):
    """A tax id reduced to its comparable core: upper-case, alphanumerics only."""
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def _norm_address(line1, city):
    """``line1|city`` lower-cased with whitespace collapsed."""
    return f"{_collapse(line1)}|{_collapse(city)}"


def _norm_contact(kind, value):
    """A contact value reduced to its comparable core.

    Phone and mobile reduce to digits only, so ``+44 113 496 0000`` and ``01134960000`` are the
    same number. Anything else (email) is trimmed and lower-cased.
    """
    text = (value or "").strip().lower()
    if kind in ("phone", "mobile"):
        return "".join(ch for ch in text if ch.isdigit())
    return text


def _norm_name(value):
    """A company name reduced to its comparable core.

    Lower-cased, whitespace collapsed, the legal-form suffixes stripped, then every
    non-alphanumeric removed — so "Acme Supplies Ltd.", "ACME  SUPPLIES LIMITED" and
    "Acme-Supplies Co" all reduce to ``acmesupplies``.
    """
    words = [word for word in _collapse(value).replace(".", " ").replace(",", " ").split()]
    while words and "".join(ch for ch in words[-1] if ch.isalnum()) in NAME_SUFFIXES:
        words.pop()
    return "".join(ch for ch in "".join(words) if ch.isalnum())


def _mask_tail(value, keep=4):
    """``••••1234`` — the tail of an identifier, enough to recognise and not to reuse."""
    text = "".join((value or "").split())
    if not text:
        return "••••"
    return f"••••{text[-keep:]}" if len(text) > keep else "•" * len(text)


def _mask_email(value):
    """``a••@acme.test`` — the first character of the local part, and the domain."""
    text = (value or "").strip()
    if "@" not in text:
        return _mask_tail(text)
    local, _, domain = text.partition("@")
    head = local[:1] or "•"
    return f"{head}••@{domain}"


def _mask_contact(kind, value):
    return _mask_email(value) if kind == "email" else _mask_tail(value)


def _matched_on(attribute, shown):
    """The ``matched_on`` sentence, clamped to the column width."""
    return f"{attribute} {shown}"[:160]


class FraudAlert(TenantNumbered):
    """One integrity question a deterministic rule raised, waiting for a person [FRD-].

    Lifecycle::

        open -> investigating -> substantiated | unsubstantiated | referred
          |                            ^
          +----------------------------+

    ``open`` and ``investigating`` are live work; the other three are dispositions and are
    terminal. Every arrow is a verb method at the bottom of this class, each of which re-checks
    its own guard INSIDE itself and returns a bool: hiding a button in a template does not stop a
    direct POST, and a double-submitted disposition must not be audited twice. ``status`` is
    ``editable=False`` for the same reason, which is also why it is not on the form.

    ``amount`` is NULLABLE and that is load-bearing: a conflict-of-interest overlap between a
    supplier and an employee has no amount at all, and writing ``0.00`` for it would put a real
    zero into every by-value rollup and read as "worth nothing".
    """

    NUMBER_PREFIX = "FRD"

    RULE_CHOICES = RULE_CHOICES
    SEVERITY_CHOICES = SEVERITY_CHOICES
    STATUS_CHOICES = STATUS_CHOICES

    OPEN_STATUSES = OPEN_STATUSES
    TERMINAL_STATUSES = TERMINAL_STATUSES
    SEVERITY_BY_RULE = SEVERITY_BY_RULE
    STATUS_CSS = STATUS_CSS
    SEVERITY_CSS = SEVERITY_CSS

    OVERLAP_ATTRIBUTES = OVERLAP_ATTRIBUTES
    MAX_GROUP_SIZE = MAX_GROUP_SIZE
    MAX_PAIRS_PER_ATTRIBUTE = MAX_PAIRS_PER_ATTRIBUTE
    NEW_VENDOR_DAYS = NEW_VENDOR_DAYS
    NEW_VENDOR_AMOUNT = NEW_VENDOR_AMOUNT
    BACKDATE_GRACE_DAYS = BACKDATE_GRACE_DAYS
    SCAN_ROW_LIMIT = SCAN_ROW_LIMIT
    MAX_SCAN_WINDOW_DAYS = MAX_SCAN_WINDOW_DAYS
    NAME_SUFFIXES = NAME_SUFFIXES
    NOT_BUILDABLE_NOTE = NOT_BUILDABLE_NOTE

    # -- source pointers (clean() requires AT LEAST ONE) ------------------------------------------
    # All SET_NULL: deleting the evidence must not delete the alert a decision was recorded
    # against — an orphaned alert still carries its detail, its matched_on and its disposition.
    vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="procurement_fraud_alerts",
                               help_text="The supplier the alert is about")
    #: The employee in a conflict-of-interest overlap, or the SECOND supplier record in a
    #: duplicate pair. Never merged with ``vendor`` — the whole value of a pair rule is that the
    #: page can show both sides and let a person decide which, if either, is wrong.
    related_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True,
                                      blank=True,
                                      related_name="procurement_fraud_alerts_related",
                                      help_text="The employee or the second supplier record")
    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="procurement_fraud_alerts")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="procurement_fraud_alerts")
    supplier_invoice = models.ForeignKey("procurement.SupplierInvoice",
                                         on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="fraud_alerts")
    approval = models.ForeignKey("procurement.RequisitionApproval", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="fraud_alerts")
    screening = models.ForeignKey("procurement.ComplianceScreening", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="fraud_alerts")

    # -- classification + evidence -----------------------------------------------------------------
    rule = models.CharField(max_length=24, choices=RULE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium",
                                help_text="A default from the rule, re-gradable by a reviewer")
    #: The date of the FACT, never the detection date — a board that aged by detection date would
    #: reset every time somebody re-ran the scan.
    document_date = models.DateField(db_index=True)
    #: NULL is legal and meaningful: a conflict-of-interest overlap has no amount.
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    detail = models.TextField(blank=True, help_text="The evidence sentence the rule wrote")
    #: WHICH attribute matched, with the value MASKED — ``tax_id ••••1234``,
    #: ``contact a••@acme.test``. The unmasked comparison happens inside the scan and is never
    #: stored (L20). Free text, auto-escaped in templates and NEVER rendered with |safe.
    matched_on = models.CharField(max_length=160, blank=True)

    # -- governance ---------------------------------------------------------------------------------
    #: What makes a re-scan idempotent. Deterministic from the rule plus its source pointers, and
    #: order-independent for the two pair rules, so the same fact always resolves to the same row.
    dedupe_key = models.CharField(max_length=120, editable=False)
    detected_at = models.DateTimeField(auto_now_add=True)
    #: Moved ONLY by the four verb methods — ``editable=False`` keeps it off every form.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open",
                              editable=False)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="procurement_fraud_alerts",
                                    help_text="Who is looking into it")
    resolution_note = models.TextField(blank=True, editable=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False,
                                    related_name="procurement_fraud_alerts_resolved")
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: Stamped by ``substantiate()`` when the operator links a block they raised in 6.4. The alert
    #: never RAISES one — parking a question and blocking a supplier are different decisions.
    suspension = models.ForeignKey("procurement.VendorSuspension", on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False,
                                   related_name="fraud_alerts")

    class Meta:
        ordering = ["-document_date", "-id"]
        unique_together = (("tenant", "number"), ("tenant", "dedupe_key"))
        indexes = [
            # Backs the register's status filter and every "what is still open" rollup.
            models.Index(fields=["tenant", "status"], name="prc_frd_tnt_status_idx"),
            # Backs the rule filter and the board's by-rule breakdown.
            models.Index(fields=["tenant", "rule"], name="prc_frd_tnt_rule_idx"),
            # Backs the severity filter and the board's by-severity breakdown.
            models.Index(fields=["tenant", "severity"], name="prc_frd_tnt_sev_idx"),
            # Backs the date-window scan and the ageing buckets.
            models.Index(fields=["tenant", "document_date"], name="prc_frd_tnt_docdate_idx"),
            # Backs the supplier filter and the by-supplier view.
            models.Index(fields=["tenant", "vendor"], name="prc_frd_tnt_vendor_idx"),
        ]
        verbose_name = "fraud alert"

    def __str__(self):
        return f"{self.number or 'FRD'} · {self.get_rule_display()}"

    # -- dedupe -------------------------------------------------------------------------------

    def build_dedupe_key(self):
        """The deterministic identity of the FACT this alert records.

        The two PAIR rules key off ``min``/``max`` of the two party ids so the same overlap is
        one row whichever party the detector walked first — without that, re-running the scan
        after a party was re-created would mint the mirror image of a row that already exists.
        """
        rule = self.rule or "unknown"
        if rule == "vendor_employee_match" and self.vendor_id and self.related_party_id:
            low, high = sorted((self.vendor_id, self.related_party_id))
            return f"vem:{low}:{high}:{self._key_attribute()}"
        if rule == "duplicate_vendor" and self.vendor_id and self.related_party_id:
            low, high = sorted((self.vendor_id, self.related_party_id))
            return f"dupven:{low}:{high}:{self._key_attribute()}"
        if rule == "self_approval" and self.approval_id:
            return f"selfapp:{self.approval_id}"
        if rule == "backdated_po" and self.supplier_invoice_id:
            return f"bdpo:{self.supplier_invoice_id}"
        if rule == "screening_unresolved" and self.purchase_order_id:
            return f"scrunres:{self.purchase_order_id}"
        if rule == "new_vendor_rush" and self.vendor_id:
            return f"nvrush:{self.vendor_id}"
        # No usable pointer for this rule. ``clean()`` refuses the pointer-less shape, so this is
        # reachable only by a hand-raised row under a rule whose own key it cannot satisfy; a
        # random token keeps it from colliding with another such row and turning a data-entry
        # mistake into an IntegrityError 500 (the MaverickSpendFinding precedent).
        return f"{rule}:manual:{secrets.token_hex(8)}"

    def _key_attribute(self):
        """Which attribute a pair alert matched on, taken off ``matched_on``'s first word.

        The scan always supplies its own key, so this only runs for a HAND-RAISED pair. Falling
        back to ``manual`` keeps a hand-raised pair from silently colliding with the scan's row
        for the same two parties on a different attribute.
        """
        head = (self.matched_on or "").split(" ", 1)[0].strip().lower()
        return head if head in ("tax_id", "address", "contact", "name") else "manual"

    # -- validation -----------------------------------------------------------------------------

    def clean(self):
        errors = {}
        tenant_id = self.tenant_id

        pointers = (self.vendor_id, self.related_party_id, self.requisition_id,
                    self.purchase_order_id, self.supplier_invoice_id, self.approval_id,
                    self.screening_id)
        if not any(pointers):
            errors["vendor"] = (
                "Point the alert at something — a supplier, a requisition, an order, an invoice, "
                "an approval or a screening. An accusation with no evidence cannot be reviewed.")

        if self.rule not in dict(RULE_CHOICES):
            errors["rule"] = "Choose a known fraud rule."

        if self.severity and self.severity not in dict(SEVERITY_CHOICES):
            errors["severity"] = "Choose a known severity."

        # Cross-tenant guard on EVERY FK, through ``_id`` guards rather than bare ``getattr`` —
        # ``getattr`` on an unset FK raises RelatedObjectDoesNotExist, which is how the
        # VendorSuspension.clean() bug 500ed. Same tenant is not the same subject: a narrowed
        # <select> is UX, and this is the boundary.
        if tenant_id:
            for name in ("vendor", "related_party", "requisition", "purchase_order",
                         "supplier_invoice", "approval", "screening", "suspension"):
                if getattr(self, f"{name}_id") is None:
                    continue
                if getattr(self, name).tenant_id != tenant_id:
                    errors[name] = "That record belongs to another workspace."
            # ``assigned_to`` is the one FK whose tenant may legitimately be NULL: the superuser
            # has no workspace and is still a valid assignee. Only a user belonging to a
            # DIFFERENT workspace is refused.
            if self.assigned_to_id is not None:
                owner = self.assigned_to.tenant_id
                if owner is not None and owner != tenant_id:
                    errors["assigned_to"] = "That user belongs to another workspace."

        if self.vendor_id and self.vendor_id == self.related_party_id:
            errors["related_party"] = (
                "The two sides of an overlap have to be two different parties.")

        if self.document_date is not None and not (_MIN_DATE <= self.document_date <= _MAX_DATE):
            errors["document_date"] = "Enter a document date between 1900 and 9999."

        # L35: finiteness BEFORE the magnitude comparison. Decimal("NaN") parses fine and then
        # raises InvalidOperation on the ``>``, which would be an unhandled 500 on a POST.
        if self.amount is not None:
            value = _finite(self.amount)
            if value is None or value.copy_abs() > MAX_FRD_MONEY:
                errors["amount"] = "Enter an amount below 10,000,000,000,000,000."

        # Pre-check the computed key against this workspace's rows so a hand-raised duplicate
        # renders as a friendly field error instead of the unique constraint 500ing the POST.
        # Skipped for the random no-pointer key, which cannot collide by construction.
        if tenant_id and not errors:
            key = self.dedupe_key or self.build_dedupe_key()
            if ":manual:" not in key:
                clash = (type(self).objects.filter(tenant_id=tenant_id, dedupe_key=key)
                         .exclude(pk=self.pk))
                if clash.exists():
                    errors["rule"] = (
                        "That alert already exists for this evidence — open the existing one "
                        "instead of raising a second.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.dedupe_key:
            self.dedupe_key = self.build_dedupe_key()[:120]
        if self.matched_on:
            self.matched_on = self.matched_on[:160]
        return super().save(*args, **kwargs)

    # -- derived ---------------------------------------------------------------------------------

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-slate")

    @property
    def severity_css(self):
        return SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    @property
    def is_terminal(self):
        return self.status in TERMINAL_STATUSES

    @property
    def is_pair_rule(self):
        """True for the two rules whose finding is about TWO parties rather than a document."""
        return self.rule in ("vendor_employee_match", "duplicate_vendor")

    @property
    def age_days(self):
        """Days since the FACT, not since detection. ``None`` when there is no date."""
        if not self.document_date:
            return None
        return (timezone.localdate() - self.document_date).days

    @classmethod
    def default_severity(cls, rule):
        return SEVERITY_BY_RULE.get(rule, "medium")

    @classmethod
    def scan_limits(cls):
        """The tuning constants, as the scan page renders them READ-ONLY.

        A list of ``{name, value, why}`` dicts — the page states the number AND what it buys, so
        a threshold that decides whether somebody gets accused is visible rather than folkloric.
        """
        return [
            {"name": "Overlap attributes",
             "value": ", ".join(OVERLAP_ATTRIBUTES),
             "why": "The identity attributes a supplier and an employee are joined on."},
            {"name": "Max group size", "value": MAX_GROUP_SIZE,
             "why": "Past this many parties sharing one value the group is skipped, not paired — "
                    "a shared serviced-office address is a data-quality problem, not hundreds of "
                    "accusations."},
            {"name": "Max pairs per attribute", "value": MAX_PAIRS_PER_ATTRIBUTE,
             "why": "Ceiling on how many pairs one attribute emits in one pass."},
            {"name": "New supplier window", "value": f"{NEW_VENDOR_DAYS} days",
             "why": "How long a supplier counts as new, and how long the spend run is measured "
                    "over."},
            {"name": "New supplier spend", "value": NEW_VENDOR_AMOUNT,
             "why": "Spend inside that window at or above which a new supplier is worth a "
                    "question."},
            {"name": "Backdating grace", "value": f"{BACKDATE_GRACE_DAYS} day",
             "why": "A purchase order dated this far after its invoice is clerical lag; further "
                    "is a story."},
            {"name": "Scan row limit", "value": SCAN_ROW_LIMIT,
             "why": "Most source rows one pass reads. A scan is a click, not a background job."},
            {"name": "Max window", "value": f"{MAX_SCAN_WINDOW_DAYS} days",
             "why": "Longest period one scan may cover, checked arithmetically rather than by "
                    "building the range."},
        ]

    # -- disposition verbs -----------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool, and each writes only its
    # own columns through update_fields. NOTHING ELSE moves ``status``.

    def investigate(self, user, note=""):
        """Somebody has picked it up. ``open`` → ``investigating`` only; no note required."""
        if self.status != "open":
            return False
        self.status = "investigating"
        if user is not None and getattr(user, "is_authenticated", False) and not self.assigned_to_id:
            # Picking up an unassigned alert takes ownership of it. An alert already assigned to
            # somebody is NOT silently reassigned by a second person opening it.
            self.assigned_to = user
            self.save(update_fields=["status", "assigned_to", "updated_at"])
            return True
        self.save(update_fields=["status", "updated_at"])
        return True

    def substantiate(self, user, note, suspension=None):
        """The rule was right — this is a real integrity problem.

        ``suspension`` is an OPTIONAL link to a block the operator raised in the 6.4 register.
        The alert never raises one itself: parking a question and blocking a supplier are
        different decisions, made by different people, and this module only records that the
        second one happened.
        """
        return self._dispose("substantiated", user, note, suspension=suspension)

    def unsubstantiate(self, user, note):
        """A false positive — the rule was wrong about this row."""
        return self._dispose("unsubstantiated", user, note)

    def refer(self, user, note):
        """Handed on for external action — audit, legal, law enforcement, the insurer."""
        return self._dispose("referred", user, note)

    def _dispose(self, status, user, note, suspension=None):
        """Shared body of the three terminal verbs: guard, require a note, stamp, save.

        The note is REQUIRED for all three, including ``unsubstantiated``. A dismissal with no
        recorded reasoning is indistinguishable from an alert nobody looked at, which is exactly
        the finding an audit writes up.
        """
        if not self.is_open:
            return False
        note = (note or "").strip()
        if not note:
            return False
        self.status = status
        self.resolution_note = note
        self.resolved_by = user if getattr(user, "is_authenticated", False) else None
        self.resolved_at = timezone.now()
        fields = ["status", "resolution_note", "resolved_by", "resolved_at", "updated_at"]
        if suspension is not None and status == "substantiated":
            self.suspension = suspension
            fields.append("suspension")
        self.save(update_fields=fields)
        return True

    # -- detection ----------------------------------------------------------------------------------

    @classmethod
    def scan(cls, tenant, start, end, rules=None, user=None, diagnostics=None):
        """Run the enabled rules over ``[start, end)`` and return ``{rule: newly_raised_count}``.

        ``count`` is how many alerts were NEWLY RAISED for that rule — an existing alert merely
        refreshed is not counted, because "we found 12 things" on the second run of an unchanged
        window would be a lie.

        Idempotent by construction: every candidate carries a deterministic ``dedupe_key`` and is
        UPSERTED on it. An alert somebody has already disposed of keeps its disposition — only
        its facts are refreshed — so a re-scan can never quietly re-open settled work.

        ``diagnostics``, when a dict is passed in, is filled with the two things the scan page
        has to state rather than hide::

            diagnostics["skipped_groups"] = [{rule, rule_label, attribute, size, limit}, ...]
            diagnostics["capped"]         = [{rule, rule_label, attribute, emitted, limit}, ...]

        It is an OUT parameter rather than a second return value so the return type stays exactly
        the ``{rule: count}`` the contract pins.

        The whole pass runs inside one ``transaction.atomic()``: a scan that dies half-way must
        not leave a workspace holding half a board. **Nothing outside this model is written** —
        no suspension, no invoice block, no PO hold, and no edit to any party.
        """
        if tenant is None or start is None or end is None or end <= start:
            return {}
        # L40 §1 — the guard is O(1) ARITHMETIC. Building the range to measure it would be the
        # very payload the cap exists to refuse.
        if (end - start).days > MAX_SCAN_WINDOW_DAYS:
            return {}

        # An unknown rule name in ``rules`` is IGNORED rather than raising: the list arrives from
        # a POST checkbox group, and a hand-edited value must narrow the scan, never 500 it (L11).
        selected = None if rules is None else set(rules)
        wanted = [name for name, _label in RULE_CHOICES
                  if selected is None or name in selected]
        if not wanted:
            return {}

        report = diagnostics if diagnostics is not None else {}
        report.setdefault("skipped_groups", [])
        report.setdefault("capped", [])

        ctx = cls._scan_context(tenant, start, end, wanted)
        candidates = []
        for rule in wanted:
            # ``getattr`` on the class binds ``cls`` for us — these are classmethods.
            detector = getattr(cls, f"_detect_{rule}", None)
            if detector is None:
                continue
            candidates.extend(detector(tenant, start, end, ctx, report))

        counts = {rule: 0 for rule in wanted}
        existing_by_key = cls._existing_by_key(tenant, candidates)
        with transaction.atomic():
            for row in candidates:
                if cls._upsert(tenant, row, existing_by_key):
                    counts[row["rule"]] = counts.get(row["rule"], 0) + 1
        return counts

    @classmethod
    def _existing_by_key(cls, tenant, candidates):
        """``{dedupe_key: alert}`` for every candidate, in a bounded number of queries.

        Looking each candidate up on its own would be one SELECT per candidate — the scan
        button's hot path. Chunked because an ``IN`` list of tens of thousands of strings is its
        own problem; the ``(tenant, dedupe_key)`` unique_together backs the lookup.
        """
        keys = sorted({row.get("dedupe_key") for row in candidates if row.get("dedupe_key")})
        found = {}
        for offset in range(0, len(keys), _DEDUPE_LOOKUP_CHUNK):
            chunk = keys[offset:offset + _DEDUPE_LOOKUP_CHUNK]
            found.update({obj.dedupe_key: obj for obj in
                          cls.objects.filter(tenant=tenant, dedupe_key__in=chunk)})
        return found

    #: The dimension pointers ``_upsert`` refreshes. ``status`` / ``resolution_note`` /
    #: ``resolved_by`` / ``resolved_at`` / ``severity`` / ``assigned_to`` / ``suspension`` are
    #: deliberately absent: the first four are the disposition and the last three are a person's.
    _REFRESHED_POINTERS = ("vendor_id", "related_party_id", "requisition_id", "purchase_order_id",
                           "supplier_invoice_id", "approval_id", "screening_id")

    @classmethod
    def _upsert(cls, tenant, row, existing_by_key=None):
        """Create or refresh ONE alert. Returns True only when a new row was minted."""
        key = row.get("dedupe_key") or ""
        if not key:
            existing = None
        elif existing_by_key is not None:
            existing = existing_by_key.get(key)
        else:
            existing = cls.objects.filter(tenant=tenant, dedupe_key=key).first()

        if existing is None:
            obj = cls(tenant=tenant, **row)
            obj.severity = row.get("severity") or cls.default_severity(row["rule"])
            obj.save()
            if key and existing_by_key is not None:
                # Two rules CAN produce the same key in one pass; the map has to see the row this
                # call just minted or the second one would hit the unique_together.
                existing_by_key[key] = obj
            return True

        # Refresh the FACTS, never the disposition and never a person's judgement.
        existing.amount = row.get("amount", existing.amount)
        existing.detail = row.get("detail", existing.detail)
        existing.document_date = row.get("document_date", existing.document_date)
        existing.matched_on = (row.get("matched_on", existing.matched_on) or "")[:160]
        for name in cls._REFRESHED_POINTERS:
            if name in row:
                setattr(existing, name, row[name])
        existing.save(update_fields=[
            "amount", "detail", "document_date", "matched_on", "vendor", "related_party",
            "requisition", "purchase_order", "supplier_invoice", "approval", "screening",
            "updated_at"])
        return False

    # -- scan context (every prefetch the rules share) ---------------------------------------------

    @classmethod
    def _scan_context(cls, tenant, start, end, wanted):
        """Everything the rules need, fetched ONCE.

        A rule that resolved its own party / address / contact / screening lookups would issue a
        query per row; the whole point of this dict is that a scan is a handful of queries whose
        count does not grow with the number of rows. Every list is capped at ``SCAN_ROW_LIMIT``.
        """
        # Deferred (see the module docstring): these live in sibling sub-packages that are still
        # being wired, and 6.13's invoice module imports accounting at module level.
        from apps.core.models import Address, ContactMethod, Party, PartyRole
        from apps.procurement.models.ApprovalWorkflowEngine.Approvals import RequisitionApproval
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
            SupplierInvoice)
        from apps.procurement.models.RiskComplianceManagement.Screenings import (
            ComplianceScreening)
        # ONE definition of what counts as spend, imported rather than copied — 6.14 and 6.17
        # must never disagree about it (the module docstring states this).
        from apps.procurement.models.SpendAnalyticsReporting.MaverickFindings import (
            RECOGNISED_INVOICE_STATUSES, SPEND_PO_STATUSES)
        from apps.scm.models.ProcurementManagement.PurchaseOrders import PurchaseOrder

        ctx = {"invoice_statuses": RECOGNISED_INVOICE_STATUSES,
               "po_statuses": SPEND_PO_STATUSES}
        wanted = set(wanted)
        start_dt, end_dt = _window_bounds(start, end)

        # -- party sets ------------------------------------------------------------------------
        needs_parties = bool(wanted & {"vendor_employee_match", "duplicate_vendor",
                                       "new_vendor_rush"})
        vendor_ids, employee_ids = set(), set()
        if needs_parties:
            for party_id, role in (PartyRole.objects
                                   .filter(tenant=tenant, status="active",
                                           role__in=_VENDOR_ROLES + ("employee",))
                                   .values_list("party_id", "role")[:SCAN_ROW_LIMIT]):
                (vendor_ids if role in _VENDOR_ROLES else employee_ids).add(party_id)
        ctx["vendor_ids"] = vendor_ids
        ctx["employee_ids"] = employee_ids

        # party -> (name, tax_id, created-on date). One query, only for the parties in play.
        parties = {}
        if needs_parties:
            in_play = vendor_ids | employee_ids
            if in_play:
                for pk, name, tax_id, created in (
                        Party.objects.filter(tenant=tenant, pk__in=in_play)
                        .values_list("id", "name", "tax_id", "created_at")[:SCAN_ROW_LIMIT]):
                    parties[pk] = {
                        "name": name,
                        "tax_id": tax_id or "",
                        "created_on": timezone.localtime(created).date() if created else None,
                    }
        ctx["parties"] = parties

        # -- overlap attributes ------------------------------------------------------------------
        # Addresses and contacts, indexed party -> [(normalised key, display/mask)]. Fetched only
        # when a rule that joins on them is enabled.
        addresses, contacts = {}, {}
        if wanted & {"vendor_employee_match", "duplicate_vendor"} and parties:
            for party_id, line1, city in (
                    Address.objects.filter(tenant=tenant, party_id__in=list(parties))
                    .exclude(line1="")
                    .values_list("party_id", "line1", "city")[:SCAN_ROW_LIMIT]):
                key = _norm_address(line1, city)
                if not key.strip("|"):
                    continue
                shown = f"{line1}, {city}" if city else line1
                addresses.setdefault(party_id, []).append((key, shown))
        if "vendor_employee_match" in wanted and parties:
            for party_id, kind, value in (
                    ContactMethod.objects.filter(tenant=tenant, party_id__in=list(parties))
                    .exclude(value="")
                    .values_list("party_id", "kind", "value")[:SCAN_ROW_LIMIT]):
                key = _norm_contact(kind, value)
                if not key:
                    continue
                contacts.setdefault(party_id, []).append((key, _mask_contact(kind, value)))
        ctx["addresses"] = addresses
        ctx["contacts"] = contacts

        # -- approvals in the window ---------------------------------------------------------------
        approvals = []
        if "self_approval" in wanted:
            approvals = list(
                RequisitionApproval.objects
                .filter(tenant=tenant, decided_at__gte=start_dt, decided_at__lt=end_dt,
                        approver__isnull=False)
                .select_related("requisition", "approver")
                .order_by("decided_at", "id")[:SCAN_ROW_LIMIT])
        ctx["approvals"] = approvals

        # -- invoices --------------------------------------------------------------------------
        # ``backdated_po`` needs the window; ``new_vendor_rush`` needs a wider one, because a
        # supplier created just before the window can take its rush spend just after it. One
        # query covers both — the widest span either rule asks for.
        invoices = []
        if wanted & {"backdated_po", "new_vendor_rush"}:
            lo = start - timedelta(days=NEW_VENDOR_DAYS) if "new_vendor_rush" in wanted else start
            hi = end + timedelta(days=NEW_VENDOR_DAYS) if "new_vendor_rush" in wanted else end
            invoices = list(
                SupplierInvoice.objects
                .filter(tenant=tenant, status__in=RECOGNISED_INVOICE_STATUSES,
                        invoice_date__gte=lo, invoice_date__lt=hi)
                .exclude(invoice_type="credit_memo")
                .select_related("vendor", "purchase_order")
                .order_by("invoice_date", "id")[:SCAN_ROW_LIMIT])
        ctx["invoices"] = invoices

        # -- purchase orders in the window ---------------------------------------------------------
        # ``doc_date`` = the order date, falling back to the day the row was created. The
        # TruncDate note from MaverickFindings._scan_context applies verbatim: safe because
        # TIME_ZONE = "UTC" matches the connection — re-check if that ever changes.
        orders = []
        if "screening_unresolved" in wanted:
            orders = list(
                PurchaseOrder.objects
                .filter(tenant=tenant, status__in=SPEND_PO_STATUSES)
                .annotate(doc_date=Coalesce("order_date", TruncDate("created_at")))
                .filter(doc_date__gte=start, doc_date__lt=end)
                .select_related("vendor")
                .order_by("doc_date", "id")[:SCAN_ROW_LIMIT])
        ctx["orders"] = orders

        # -- unresolved screenings -----------------------------------------------------------------
        # party -> [screenings carrying at least one hit still open or confirmed a true match],
        # newest first. ONE query with a hit-level EXISTS, rather than a screening lookup per PO.
        unresolved = {}
        if "screening_unresolved" in wanted:
            for screening in (ComplianceScreening.objects
                              .filter(tenant=tenant,
                                      hits__disposition__in=_UNRESOLVED_DISPOSITIONS)
                              .distinct()
                              .select_related("party")
                              .order_by("party_id", "-screened_on", "-id")[:SCAN_ROW_LIMIT]):
                unresolved.setdefault(screening.party_id, []).append(screening)
        ctx["unresolved_screenings"] = unresolved

        return ctx

    # -- shared pair machinery -----------------------------------------------------------------------

    @classmethod
    def _emit_pairs(cls, groups, attribute, rule, report, pair_filter):
        """Turn ``{key: [(party_id, shown)]}`` groups into deduplicated ordered pairs.

        Shared by the two pair rules because the caps, the skip accounting and the ordering rule
        are identical and must stay identical: a pair emitted one way round by one rule and the
        other way round by the other would be two rows for one fact.

        ``pair_filter(a, b)`` returns the ``(vendor_id, related_party_id)`` to stamp, or ``None``
        to reject the pair. Returns ``[(vendor_id, related_id, shown)]``, capped at
        ``MAX_PAIRS_PER_ATTRIBUTE`` with the overflow recorded in ``report["capped"]``.
        """
        label = dict(RULE_CHOICES).get(rule, rule)
        emitted, seen, overflow = [], set(), 0
        for members in groups.values():
            # Distinct parties only — one party with three addresses on the same key is one
            # member of the group, not three.
            by_party = {}
            for party_id, shown in members:
                by_party.setdefault(party_id, shown)
            if len(by_party) < 2:
                continue
            if len(by_party) > MAX_GROUP_SIZE:
                report.setdefault("skipped_groups", []).append({
                    "rule": rule, "rule_label": label, "attribute": attribute,
                    "size": len(by_party), "limit": MAX_GROUP_SIZE})
                continue
            ordered = sorted(by_party)
            for index, first in enumerate(ordered):
                for second in ordered[index + 1:]:
                    stamped = pair_filter(first, second)
                    if stamped is None:
                        continue
                    pair_key = (min(first, second), max(first, second))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    if len(emitted) >= MAX_PAIRS_PER_ATTRIBUTE:
                        overflow += 1
                        continue
                    emitted.append((stamped[0], stamped[1],
                                    by_party.get(stamped[0]) or by_party.get(first)))
        if overflow:
            report.setdefault("capped", []).append({
                "rule": rule, "rule_label": label, "attribute": attribute,
                "emitted": len(emitted), "limit": MAX_PAIRS_PER_ATTRIBUTE})
        return emitted

    @classmethod
    def _attribute_groups(cls, ctx, attribute, party_ids):
        """``{normalised key: [(party_id, shown)]}`` for one attribute over ``party_ids``."""
        groups = {}
        if attribute == "tax_id":
            for party_id in party_ids:
                raw = ctx["parties"].get(party_id, {}).get("tax_id", "")
                key = _norm_tax_id(raw)
                if key:
                    groups.setdefault(key, []).append((party_id, _mask_tail(raw)))
        elif attribute == "address":
            for party_id in party_ids:
                for key, shown in ctx["addresses"].get(party_id, ()):
                    groups.setdefault(key, []).append((party_id, shown))
        elif attribute == "contact":
            for party_id in party_ids:
                for key, shown in ctx["contacts"].get(party_id, ()):
                    groups.setdefault(key, []).append((party_id, shown))
        elif attribute == "name":
            for party_id in party_ids:
                key = _norm_name(ctx["parties"].get(party_id, {}).get("name", ""))
                if key:
                    groups.setdefault(key, []).append((party_id, key))
        return groups

    @classmethod
    def _pair_document_date(cls, ctx, first, second):
        """The LATER of the two parties' creation dates — the date the overlap became true."""
        dates = [ctx["parties"].get(pid, {}).get("created_on") for pid in (first, second)]
        dates = [value for value in dates if value is not None]
        return max(dates) if dates else timezone.localdate()

    @classmethod
    def _party_name(cls, ctx, party_id):
        return ctx["parties"].get(party_id, {}).get("name") or f"party {party_id}"

    # -- rules ---------------------------------------------------------------------------------

    @classmethod
    def _detect_vendor_employee_match(cls, tenant, start, end, ctx, report):
        """R1 — a supplier and an employee share an identity attribute.

        The classic conflict of interest: the same tax id, the same home address, or the same
        phone number or mailbox on both sides of a purchase. It FLAGS the overlap and nothing
        else — a shared address can be a family business the company knows all about, and this
        module raises the question rather than answering it.

        ``document_date`` is the LATER of the two parties' creation dates: the day the overlap
        became true. ``amount`` is NULL, because an overlap is not a transaction.
        """
        vendor_ids, employee_ids = ctx["vendor_ids"], ctx["employee_ids"]
        if not vendor_ids or not employee_ids:
            return []
        in_play = vendor_ids | employee_ids
        rows = []

        def pair_filter(first, second):
            # Exactly one side must be the vendor and the other the employee. A party carrying
            # BOTH roles pairs with nobody through itself — ``first != second`` is guaranteed by
            # the caller, and a self-pair would be meaningless anyway.
            if first in vendor_ids and second in employee_ids:
                return (first, second)
            if second in vendor_ids and first in employee_ids:
                return (second, first)
            return None

        for attribute in OVERLAP_ATTRIBUTES:
            groups = cls._attribute_groups(ctx, attribute, in_play)
            for vendor_id, employee_id, shown in cls._emit_pairs(
                    groups, attribute, "vendor_employee_match", report, pair_filter):
                vendor_name = cls._party_name(ctx, vendor_id)
                employee_name = cls._party_name(ctx, employee_id)
                rows.append({
                    "rule": "vendor_employee_match",
                    "vendor_id": vendor_id,
                    "related_party_id": employee_id,
                    "document_date": cls._pair_document_date(ctx, vendor_id, employee_id),
                    "amount": None,
                    "matched_on": _matched_on(attribute, shown),
                    "detail": (f"Supplier {vendor_name} and employee {employee_name} share the "
                               f"same {attribute}. That is a conflict of interest to explain, "
                               f"not a proven one - a family business the company already knows "
                               f"about looks exactly like this."),
                    "dedupe_key": (f"vem:{min(vendor_id, employee_id)}:"
                                   f"{max(vendor_id, employee_id)}:{attribute}"),
                })
        return rows

    @classmethod
    def _detect_self_approval(cls, tenant, start, end, ctx, report):
        """R2 — a requisition signed off by the person who raised it.

        Segregation of duties, and the rule with ZERO false positives in it: either the approver
        and the requester are the same user id or they are not. Nothing is inferred.
        """
        rows = []
        for approval in ctx["approvals"]:
            requisition = approval.requisition
            if requisition is None or approval.approver_id is None:
                continue
            if approval.approver_id != requisition.requester_id:
                continue
            approver = approval.approver
            who = (approver.get_full_name() or approver.username) if approver else "the requester"
            decided_on = (timezone.localtime(approval.decided_at).date()
                          if approval.decided_at else timezone.localdate())
            rows.append({
                "rule": "self_approval",
                "approval_id": approval.pk,
                "requisition_id": requisition.pk,
                "document_date": decided_on,
                "amount": _money(_as_decimal(requisition.estimated_total)),
                "matched_on": _matched_on("approver", "= requester"),
                "detail": (f"{who} approved requisition {requisition.number} at tier "
                           f"{approval.tier} of {approval.tier_count}, and is also the person "
                           f"who raised it. One signature covering both ends of the request is "
                           f"the segregation-of-duties break, whatever the amount."),
                "dedupe_key": f"selfapp:{approval.pk}",
            })
        return rows

    @classmethod
    def _detect_duplicate_vendor(cls, tenant, start, end, ctx, report):
        """R3 — two supplier records that look like the same company.

        **FLAGS, never merges.** Nothing here deletes, deactivates or rewrites a ``core.Party``:
        supplier-master deduplication belongs to 6.4 and to ``core.Party``, and a rule that
        merged records on a name match would eventually merge two real companies.

        ``vendor`` is deterministically the LOWER pk and ``related_party`` the higher, so the row
        and its dedupe key always agree about which is which.
        """
        vendor_ids = ctx["vendor_ids"]
        if len(vendor_ids) < 2:
            return []
        rows = []

        def pair_filter(first, second):
            # Both sides must be suppliers; order is by pk so the pair is deterministic.
            if first in vendor_ids and second in vendor_ids:
                return (min(first, second), max(first, second))
            return None

        for attribute in ("name", "tax_id", "address"):
            groups = cls._attribute_groups(ctx, attribute, vendor_ids)
            for low, high, shown in cls._emit_pairs(
                    groups, attribute, "duplicate_vendor", report, pair_filter):
                rows.append({
                    "rule": "duplicate_vendor",
                    "vendor_id": low,
                    "related_party_id": high,
                    "document_date": cls._pair_document_date(ctx, low, high),
                    "amount": None,
                    "matched_on": _matched_on(attribute, shown),
                    "detail": (f"{cls._party_name(ctx, low)} and {cls._party_name(ctx, high)} "
                               f"share the same {attribute} and may be one company held twice - "
                               f"which is how a shell supplier hides beside a real one, and also "
                               f"how an ordinary data-entry duplicate looks. FLAGGED ONLY: "
                               f"nothing here merges, deactivates or edits either record."),
                    "dedupe_key": f"dupven:{low}:{high}:{attribute}",
                })
        return rows

    @classmethod
    def _detect_backdated_po(cls, tenant, start, end, ctx, report):
        """R4 — a purchase order raised AFTER the invoice it is supposed to authorise.

        Distinct from 6.14's ``po_less_invoice``, which is "there was no order at all". Here
        there IS one — it was written afterwards to make the spend look authorised, which is the
        paperwork being tidied up after the fact rather than a control that ran.
        """
        rows = []
        for invoice in ctx["invoices"]:
            order = invoice.purchase_order
            if order is None or invoice.invoice_date is None:
                continue
            if not (start <= invoice.invoice_date < end):
                continue  # the wider fetch is for R6; R4 only owns the requested window
            order_date = order.order_date
            if order_date is None:
                order_date = (timezone.localtime(order.created_at).date()
                              if order.created_at else None)
            if order_date is None:
                continue
            gap = (order_date - invoice.invoice_date).days
            if gap <= BACKDATE_GRACE_DAYS:
                continue
            rows.append({
                "rule": "backdated_po",
                "supplier_invoice_id": invoice.pk,
                "purchase_order_id": order.pk,
                "vendor_id": invoice.vendor_id,
                "document_date": invoice.invoice_date,
                "amount": _money(_as_decimal(invoice.total).copy_abs()),
                "matched_on": _matched_on(
                    "order_date", f"{order_date:%Y-%m-%d} after invoice "
                                  f"{invoice.invoice_date:%Y-%m-%d}"),
                "detail": (f"Purchase order {order.number} is dated {order_date:%Y-%m-%d}, "
                           f"{gap} days AFTER invoice {invoice.number} of "
                           f"{invoice.invoice_date:%Y-%m-%d} that it is supposed to authorise. "
                           f"This is not the 6.14 finding for spend with no order at all - here "
                           f"there is an order, and it was written afterwards."),
                "dedupe_key": f"bdpo:{invoice.pk}",
            })
        return rows

    @classmethod
    def _detect_screening_unresolved(cls, tenant, start, end, ctx, report):
        """R5 — new spend committed against a supplier whose screening match was never resolved.

        The cross-link that makes 6.17 one sub-module rather than five pages: a sanctions hit
        sitting at ``open`` or confirmed as a ``true_match`` is not an abstract compliance debt
        once somebody raises an order against that supplier anyway.

        Only a screening dated ON OR BEFORE the order counts — a hit found afterwards is not
        something the buyer could have acted on, and calling it fraud would be hindsight.
        """
        rows = []
        for order in ctx["orders"]:
            if not order.vendor_id:
                continue
            doc_date = getattr(order, "doc_date", None) or order.order_date
            if doc_date is None:
                continue
            candidates = [screening for screening
                          in ctx["unresolved_screenings"].get(order.vendor_id, ())
                          if screening.screened_on and screening.screened_on <= doc_date]
            if not candidates:
                continue
            # Newest first out of _scan_context, so the first survivor is the most recent
            # screening that predates this order.
            screening = candidates[0]
            rows.append({
                "rule": "screening_unresolved",
                "purchase_order_id": order.pk,
                "vendor_id": order.vendor_id,
                "screening_id": screening.pk,
                "document_date": doc_date,
                "amount": _money(_as_decimal(order.total).copy_abs()),
                "matched_on": _matched_on(
                    "screening", f"{screening.number} unresolved on {doc_date:%Y-%m-%d}"),
                "detail": (f"Purchase order {order.number} of {doc_date:%Y-%m-%d} commits spend "
                           f"to this supplier while screening {screening.number} of "
                           f"{screening.screened_on:%Y-%m-%d} still carries a match nobody has "
                           f"adjudicated. Resolve the hit or record why the order stands - the "
                           f"order itself is not held by this alert."),
                "dedupe_key": f"scrunres:{order.pk}",
            })
        return rows

    @classmethod
    def _detect_new_vendor_rush(cls, tenant, start, end, ctx, report):
        """R6 — a brand-new supplier taking high-value spend immediately.

        A supplier created and then invoiced hard inside its first ``NEW_VENDOR_DAYS`` has had no
        time to be a supplier: no second order, no performance history, and often no onboarding
        finished. One alert per supplier, pointing at the LARGEST single invoice in the run so
        the detail page has a document to open.
        """
        vendor_ids = ctx["vendor_ids"]
        if not vendor_ids:
            return []
        window_open = start - timedelta(days=NEW_VENDOR_DAYS)

        # Only suppliers created inside [start - NEW_VENDOR_DAYS, end).
        fresh = {}
        for party_id in vendor_ids:
            created_on = ctx["parties"].get(party_id, {}).get("created_on")
            if created_on is None or not (window_open <= created_on < end):
                continue
            fresh[party_id] = created_on
        if not fresh:
            return []

        runs = {}
        for invoice in ctx["invoices"]:
            created_on = fresh.get(invoice.vendor_id)
            if created_on is None or invoice.invoice_date is None:
                continue
            if not (created_on <= invoice.invoice_date
                    <= created_on + timedelta(days=NEW_VENDOR_DAYS)):
                continue
            total = _as_decimal(invoice.total).copy_abs()
            run = runs.setdefault(invoice.vendor_id, {"total": ZERO, "count": 0, "largest": None,
                                                      "largest_total": ZERO})
            run["total"] += total
            run["count"] += 1
            # ``>`` on two Decimals both produced by _as_decimal, which has already refused
            # NaN — the comparison cannot raise InvalidOperation here (L35).
            if run["largest"] is None or total > run["largest_total"]:
                run["largest"] = invoice
                run["largest_total"] = total

        rows = []
        for party_id, run in runs.items():
            if run["total"] < NEW_VENDOR_AMOUNT:
                continue
            created_on = fresh[party_id]
            largest = run["largest"]
            rows.append({
                "rule": "new_vendor_rush",
                "vendor_id": party_id,
                "supplier_invoice_id": largest.pk if largest is not None else None,
                "document_date": created_on,
                "amount": _money(run["total"]),
                "matched_on": _matched_on(
                    "created", f"{created_on:%Y-%m-%d}, {run['count']} invoices in "
                               f"{NEW_VENDOR_DAYS} days"),
                "detail": (f"{cls._party_name(ctx, party_id)} was added on "
                           f"{created_on:%Y-%m-%d} and took {_money(run['total'])} across "
                           f"{run['count']} invoices within {NEW_VENDOR_DAYS} days - at or above "
                           f"the {NEW_VENDOR_AMOUNT} threshold. A supplier that new has no "
                           f"performance history behind the spend."),
                "dedupe_key": f"nvrush:{party_id}",
            })
        return rows
