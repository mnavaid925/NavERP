"""Procurement 6.13 - Invoice & Voucher Management MODEL tests.

The invariants this lane owns, across the sub-module's four models:

* ``SupplierInvoice`` as the numbered HEADER - ``SIV-#####`` per tenant, ``unique_together``
  with ``tenant``, every STATUS / INVOICE_TYPE / MATCH_BASIS / MATCH_STATUS / SOURCE /
  DISCOUNT_BASE choice value, and colour-only badge maps (a semantic ``badge-success`` renders
  completely unstyled in this theme - L33);
* the rule the whole sub-module lives on: **nothing is stored that can be derived**.
  ``invoice_number_norm``, ``due_date`` / ``discount_date`` / ``discount_expiry_date``,
  ``subtotal`` / ``tax_total`` / ``total`` / ``amount_paid``, ``line_total``, ``matched_qty``
  and ``variance_abs`` / ``variance_pct`` are all recomputed in ``save()`` and all
  ``editable=False``; ``cumulative_invoiced_qty`` / ``cumulative_received_qty`` are ``Sum()``
  AGGREGATES with no column behind them at all - a stored counter drifts the first time a
  receipt is cancelled or an invoice is reversed;
* the guarded verb ladder on the header and on the dispute - each verb re-checks its own guard
  INSIDE itself, returns a bool, and no-ops on a double submit rather than re-stamping who
  signed. ``approve()`` is the ONLY ledger writer and its ``journal_entry_id`` guard is what
  stops a double-click minting a second bill;
* the absent-prerequisite cases that must be REJECTED rather than fall through (L35):
  ``raise_dispute()`` with no open variance, ``approve()`` with no chart of accounts (which
  raises and posts NOTHING), ``resolve()`` with an unknown resolution;
* ``SupplierInvoiceLine`` as a PLAIN CHILD - no ``tenant`` column and no ``number``, scoped
  through its header;
* ``InvoiceMatchVariance`` as EVIDENCE - its own ``tenant`` column, no ``number``, no
  ``unique_together``, and derived figures rebuilt on every write;
* ``InvoiceDispute`` as the numbered claim record - ``DSP-#####`` per tenant, a denormalised
  ``supplier``, an SLA ``due_date`` stamped ON CREATE ONLY, and an ``age_bucket`` in which
  ``overdue`` outranks every day band.

Determinism (L16): every date basis here is ``timezone.localdate()`` and every datetime basis
is ``timezone.now()`` - the same bases the model code uses. ``datetime.date.today()`` never
appears, or the exact-date assertions flake for the hours after local midnight.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.models import Bill, JournalEntry
from apps.procurement.models import (
    InvoiceDispute,
    InvoiceMatchVariance,
    SupplierInvoice,
    SupplierInvoiceLine,
)
from apps.procurement.models.InvoiceVoucherManagement.InvoiceDisputes import (
    REASON_CODE_CHOICES as _invoice_dispute_reason_choices,
    RESOLUTION_CHOICES as _invoice_dispute_resolution_choices,
    STATUS_CHOICES as _invoice_dispute_status_choices,
)
from apps.procurement.models.InvoiceVoucherManagement.MatchVariances import (
    BASIS_CHOICES as _invoice_basis_choices,
    OUTCOME_CHOICES as _invoice_outcome_choices,
    RESOLUTION_CHOICES as _invoice_variance_resolution_choices,
    VARIANCE_TYPE_CHOICES as _invoice_variance_type_choices,
)
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
    AP_CONTROL_GL_CODES as _invoice_ap_gl_codes,
    DISCOUNT_GL_CODES as _invoice_discount_gl_codes,
    EXPENSE_GL_CODES as _invoice_expense_gl_codes,
    TAX_GL_CODES as _invoice_tax_gl_codes,
    resolve_tolerance as _invoice_resolve_tolerance,
)

pytestmark = pytest.mark.django_db


# -- local helpers --------------------------------------------------------------------------
# Named _invoice_* so the NEXT sub-module appending near this file cannot shadow them and so a
# failure names its own lane. The conftest factories of the same shape are private to conftest
# (the 6.11 / 6.12 / 6.14 precedent), so the extra rows this module needs are minted here.

#: theme.css ships exactly these modifier classes. Anything else renders unstyled (L33).
_INVOICE_BADGE_COLOURS = {
    "badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted", "badge-slate",
}

#: The middot both __str__ implementations fold into their label (escaped, so this module stays
#: pure ASCII whatever the reader console encoding is).
_INVOICE_DOT = "·"
#: The multiplication sign SupplierInvoiceLine.__str__ uses.
_INVOICE_TIMES = "×"


def _invoice_today():
    """The SAME date basis the models use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate()


def _invoice_header(tenant, vendor, **overrides):
    """One SupplierInvoice. Every derived column is left to ``save()``."""
    fields = dict(tenant=tenant, vendor=vendor, invoice_number="SUP-8000",
                  invoice_date=_invoice_today())
    fields.update(overrides)
    return SupplierInvoice.objects.create(**fields)


def _invoice_line_row(invoice, **overrides):
    """One SupplierInvoiceLine. ``line_total`` / ``matched_qty`` are never passed."""
    fields = dict(invoice=invoice, quantity=Decimal("10"), unit_price=Decimal("25.00"))
    fields.update(overrides)
    return SupplierInvoiceLine.objects.create(**fields)


def _invoice_variance_row(invoice, **overrides):
    """One InvoiceMatchVariance. ``variance_abs`` / ``variance_pct`` are derived in save()."""
    fields = dict(tenant=invoice.tenant, invoice=invoice, variance_type="price", basis="po",
                  expected_value=Decimal("25.0000"), actual_value=Decimal("30.0000"),
                  outcome="block", resolution="open", message="Unit price differs.")
    fields.update(overrides)
    return InvoiceMatchVariance.objects.create(**fields)


def _invoice_dispute_row(invoice, **overrides):
    """One InvoiceDispute. ``supplier`` / ``status`` / ``due_date`` are stamped by save()."""
    fields = dict(tenant=invoice.tenant, invoice=invoice, reason_code="price",
                  disputed_amount=Decimal("50.00"), description="Contested unit price.")
    fields.update(overrides)
    return InvoiceDispute.objects.create(**fields)


def _invoice_backdate_raised(dispute, days):
    """Push ``raised_at`` (``auto_now_add``) back so ``days_open`` can be exercised."""
    InvoiceDispute.objects.filter(pk=dispute.pk).update(
        raised_at=timezone.now() - datetime.timedelta(days=days))
    dispute.refresh_from_db()
    return dispute


# =============================================================================================
# resolve_tolerance - the arithmetic every variance in the sub-module is judged by
# =============================================================================================

def test_invoice_resolve_tolerance_auto_accepts_exact_agreement():
    outcome, abs_v, pct_v, tol_pct, tol_abs = _invoice_resolve_tolerance(
        Decimal("25"), Decimal("25"), pct_upper=Decimal("2.00"))
    assert outcome == "auto_accept"
    assert abs_v == Decimal("0.0000")
    assert pct_v == Decimal("0.0000")
    assert tol_pct is None and tol_abs is None


def test_invoice_resolve_tolerance_warns_inside_the_band():
    outcome, abs_v, pct_v, _tp, _ta = _invoice_resolve_tolerance(
        Decimal("100"), Decimal("101"), pct_upper=Decimal("2.00"))
    assert outcome == "warn"
    assert abs_v == Decimal("1.0000")
    assert pct_v == Decimal("1.0000")


def test_invoice_resolve_tolerance_blocks_above_the_upper_band():
    outcome, abs_v, pct_v, tol_pct, _ta = _invoice_resolve_tolerance(
        Decimal("25"), Decimal("30"), pct_upper=Decimal("2.00"))
    assert outcome == "block"
    assert abs_v == Decimal("5.0000")
    assert pct_v == Decimal("20.0000")
    assert tol_pct == Decimal("2.00")


def test_invoice_resolve_tolerance_blocks_below_the_lower_band():
    outcome, abs_v, _pct, tol_pct, _ta = _invoice_resolve_tolerance(
        Decimal("100"), Decimal("80"), pct_lower=Decimal("5.00"))
    assert outcome == "block"
    assert abs_v == Decimal("-20.0000")
    assert tol_pct == Decimal("5.00")


def test_invoice_resolve_tolerance_absolute_band_is_independent():
    """Either band firing is a breach - declaring both can only ever narrow what is accepted."""
    outcome, _abs, _pct, tol_pct, tol_abs = _invoice_resolve_tolerance(
        Decimal("100"), Decimal("101"), pct_upper=Decimal("50.00"), abs_upper=Decimal("0.50"))
    assert outcome == "block"
    assert tol_pct is None
    assert tol_abs == Decimal("0.50")


def test_invoice_resolve_tolerance_none_band_never_breaches():
    outcome, _abs, _pct, _tp, _ta = _invoice_resolve_tolerance(
        Decimal("100"), Decimal("100000"))
    assert outcome == "warn"


def test_invoice_resolve_tolerance_cap_warn_downgrades_a_block():
    """Tax rounding and a duplicate suspicion must never block on their own (research 8.2)."""
    outcome, _abs, _pct, _tp, _ta = _invoice_resolve_tolerance(
        Decimal("10"), Decimal("50"), pct_upper=Decimal("1.00"), cap="warn")
    assert outcome == "warn"


def test_invoice_resolve_tolerance_pct_is_none_when_expected_is_zero():
    outcome, abs_v, pct_v, _tp, _ta = _invoice_resolve_tolerance(
        Decimal("0"), Decimal("12"), pct_upper=Decimal("1.00"))
    assert pct_v is None
    assert abs_v == Decimal("12.0000")
    assert outcome == "warn"


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "abc", None, ""])
def test_invoice_resolve_tolerance_survives_junk_figures(junk):
    """NaN and Infinity both PARSE as Decimals and then raise on the COMPARISON (L11/L35)."""
    outcome, abs_v, pct_v, _tp, _ta = _invoice_resolve_tolerance(
        junk, junk, pct_upper=Decimal("1.00"))
    assert outcome == "auto_accept"
    assert abs_v == Decimal("0.0000")
    assert pct_v is None


def test_invoice_gl_code_constants_are_ordered_tuples():
    for codes in (_invoice_expense_gl_codes, _invoice_ap_gl_codes, _invoice_tax_gl_codes,
                  _invoice_discount_gl_codes):
        assert isinstance(codes, tuple) and codes
        assert all(isinstance(code, str) for code in codes)
    assert "5000" in _invoice_expense_gl_codes
    assert "2000" in _invoice_ap_gl_codes
    assert "1400" in _invoice_tax_gl_codes
    assert "5900" in _invoice_discount_gl_codes


# =============================================================================================
# SupplierInvoice - identity, defaults, choices and the badge maps
# =============================================================================================

def test_invoice_supplier_invoice_defaults(tenant_a, invoice_vendor_a):
    """A minimal header: only vendor / invoice_number / invoice_date are asked for."""
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    assert obj.status == "draft"
    assert obj.invoice_type == "standard"
    assert obj.source == "manual"
    assert obj.match_basis == "none"
    assert obj.match_status == "not_run"
    assert obj.discount_base == "net_of_tax"
    assert obj.discount_grace_days == 0
    assert obj.subtotal == Decimal("0")
    assert obj.tax_total == Decimal("0")
    assert obj.total == Decimal("0")
    assert obj.amount_paid == Decimal("0")
    assert obj.match_notes == ""
    assert obj.notes == ""
    assert obj.external_ref == ""
    assert obj.extraction_raw_text == ""
    assert obj.extraction_confidence is None
    assert obj.fx_rate is None
    assert obj.posting_date is None
    # Every optional spine FK is unset, and none of the system stamps is filled.
    for name in ("purchase_order_id", "goods_receipt_id", "bill_id", "journal_entry_id",
                 "payment_term_id", "currency_id", "tax_code_id", "source_submission_id",
                 "document_id", "duplicate_of_id", "approved_by_id"):
        assert getattr(obj, name) is None
    assert obj.approved_at is None
    assert obj.due_date is None and obj.discount_date is None
    assert obj.discount_expiry_date is None


def test_invoice_supplier_invoice_str(invoice_draft_a):
    assert str(invoice_draft_a) == f"{invoice_draft_a.number} {_INVOICE_DOT} SUP-7001"


def test_invoice_supplier_invoice_str_before_the_number_is_minted(tenant_a, invoice_vendor_a):
    unsaved = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a,
                              invoice_number="SUP-9999", invoice_date=_invoice_today())
    assert str(unsaved) == f"SIV {_INVOICE_DOT} SUP-9999"


def test_invoice_supplier_invoice_auto_number_sequence(tenant_a, invoice_vendor_a):
    first = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-1")
    second = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-2")
    third = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-3")
    assert [first.number, second.number, third.number] == ["SIV-00001", "SIV-00002", "SIV-00003"]
    assert SupplierInvoice.NUMBER_PREFIX == "SIV"


def test_invoice_supplier_invoice_number_is_assigned_once(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    minted = obj.number
    obj.notes = "edited"
    obj.save()
    obj.refresh_from_db()
    assert obj.number == minted


def test_invoice_supplier_invoice_auto_number_is_per_tenant(tenant_a, tenant_b,
                                                            invoice_vendor_a, invoice_vendor_b):
    """Two workspaces both start at SIV-00001 - the sequence never collides across tenants."""
    a = _invoice_header(tenant_a, invoice_vendor_a)
    b = _invoice_header(tenant_b, invoice_vendor_b)
    assert a.number == "SIV-00001"
    assert b.number == "SIV-00001"
    assert a.pk != b.pk


def test_invoice_supplier_invoice_number_unique_together_with_tenant(tenant_a, invoice_vendor_a):
    first = _invoice_header(tenant_a, invoice_vendor_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SupplierInvoice.objects.create(
                tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="SUP-DUP",
                invoice_date=_invoice_today(), number=first.number)


def test_invoice_supplier_invoice_meta_contract():
    meta = SupplierInvoice._meta
    assert meta.ordering == ["-invoice_date", "-id"]
    assert meta.unique_together == (("tenant", "number"),)
    assert meta.verbose_name == "supplier invoice"


def test_invoice_supplier_invoice_ordering_is_newest_first(tenant_a, invoice_vendor_a):
    old = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-OLD",
                          invoice_date=_invoice_today() - datetime.timedelta(days=9))
    new = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-NEW",
                          invoice_date=_invoice_today())
    rows = list(SupplierInvoice.objects.filter(tenant=tenant_a))
    assert rows[0].pk == new.pk
    assert rows[-1].pk == old.pk


def test_invoice_supplier_invoice_status_choices_exact():
    assert [value for value, _label in SupplierInvoice.STATUS_CHOICES] == [
        "draft", "parked", "captured", "blocked", "disputed", "pending_approval",
        "approved", "scheduled", "paid", "void", "reversed"]


def test_invoice_supplier_invoice_type_choices_exact():
    assert [value for value, _label in SupplierInvoice.INVOICE_TYPE_CHOICES] == [
        "standard", "credit_memo", "debit_memo", "prepayment", "service"]


def test_invoice_supplier_invoice_match_basis_choices_exact():
    assert [value for value, _label in SupplierInvoice.MATCH_BASIS_CHOICES] == [
        "quantity", "amount", "none"]


def test_invoice_supplier_invoice_match_status_choices_exact():
    assert [value for value, _label in SupplierInvoice.MATCH_STATUS_CHOICES] == [
        "not_run", "matched", "within_tolerance", "price_variance", "quantity_variance",
        "total_variance", "fx_variance", "no_receipt", "over_invoiced", "duplicate_suspect"]


def test_invoice_supplier_invoice_source_choices_exact():
    assert [value for value, _label in SupplierInvoice.SOURCE_CHOICES] == [
        "manual", "pdf_text_layer", "e_invoice_xml", "vis", "ocr"]


def test_invoice_supplier_invoice_discount_base_choices_exact():
    assert [value for value, _label in SupplierInvoice.DISCOUNT_BASE_CHOICES] == [
        "net_of_tax", "gross"]


def test_invoice_supplier_invoice_terminal_and_editable_statuses():
    assert SupplierInvoice.TERMINAL_STATUSES == ("paid", "void", "reversed")
    assert SupplierInvoice.EDITABLE_STATUSES == ("draft", "parked", "captured")
    known = {value for value, _label in SupplierInvoice.STATUS_CHOICES}
    assert set(SupplierInvoice.TERMINAL_STATUSES) <= known
    assert set(SupplierInvoice.EDITABLE_STATUSES) <= known
    assert not set(SupplierInvoice.TERMINAL_STATUSES) & set(SupplierInvoice.EDITABLE_STATUSES)


def test_invoice_supplier_invoice_allowed_transitions_cover_every_status():
    known = {value for value, _label in SupplierInvoice.STATUS_CHOICES}
    assert set(SupplierInvoice.ALLOWED_TRANSITIONS) == known
    for source, targets in SupplierInvoice.ALLOWED_TRANSITIONS.items():
        assert set(targets) <= known, source
        assert source not in targets, source
    # A closed book has nowhere left to go except a reversal off ``paid``.
    assert SupplierInvoice.ALLOWED_TRANSITIONS["void"] == ()
    assert SupplierInvoice.ALLOWED_TRANSITIONS["reversed"] == ()
    assert SupplierInvoice.ALLOWED_TRANSITIONS["paid"] == ("reversed",)


def test_invoice_supplier_invoice_match_status_by_type_is_a_known_vocabulary():
    match_statuses = {value for value, _label in SupplierInvoice.MATCH_STATUS_CHOICES}
    variance_types = {value for value, _label in _invoice_variance_type_choices}
    assert set(SupplierInvoice.MATCH_STATUS_BY_TYPE) <= variance_types
    assert set(SupplierInvoice.MATCH_STATUS_BY_TYPE.values()) <= match_statuses


def test_invoice_supplier_invoice_badge_maps_cover_every_choice():
    """L33 - a semantic badge class renders completely unstyled in this theme."""
    assert set(SupplierInvoice.STATUS_CSS) == {v for v, _l in SupplierInvoice.STATUS_CHOICES}
    assert set(SupplierInvoice.MATCH_STATUS_CSS) == {
        v for v, _l in SupplierInvoice.MATCH_STATUS_CHOICES}
    assert set(SupplierInvoice.SOURCE_CSS) == {v for v, _l in SupplierInvoice.SOURCE_CHOICES}
    for mapping in (SupplierInvoice.STATUS_CSS, SupplierInvoice.MATCH_STATUS_CSS,
                    SupplierInvoice.SOURCE_CSS):
        assert set(mapping.values()) <= _INVOICE_BADGE_COLOURS


def test_invoice_supplier_invoice_badge_properties(invoice_draft_a, invoice_paid_a):
    assert invoice_draft_a.status_css == "badge-muted"
    assert invoice_draft_a.match_status_css == "badge-muted"
    assert invoice_draft_a.source_css == "badge-muted"
    assert invoice_paid_a.status_css == "badge-green"


def test_invoice_supplier_invoice_badges_fall_back_to_slate(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    obj.status = "not-a-status"
    obj.match_status = "not-a-match-status"
    obj.source = "not-a-source"
    assert obj.status_css == "badge-slate"
    assert obj.match_status_css == "badge-slate"
    assert obj.source_css == "badge-slate"


def test_invoice_supplier_invoice_tolerance_constants():
    assert SupplierInvoice.PRICE_TOL_PCT_UPPER == Decimal("2.00")
    assert SupplierInvoice.PRICE_TOL_PCT_LOWER is None
    assert SupplierInvoice.PRICE_TOL_ABS_UPPER is None
    assert SupplierInvoice.QTY_TOL_PCT_UPPER == Decimal("0.00")
    assert SupplierInvoice.QTY_TOL_ABS_UPPER is None
    assert SupplierInvoice.QTY_TOL_PCT_UPPER_NO_GRN == Decimal("5.00")
    assert SupplierInvoice.QTY_TOL_PCT_LOWER == Decimal("5.00")
    assert SupplierInvoice.TOTAL_TOL_PCT == Decimal("1.00")
    assert SupplierInvoice.TOTAL_TOL_ABS is None
    assert SupplierInvoice.FX_TOL_PCT == Decimal("1.00")
    assert SupplierInvoice.TAX_TOL_ABS == Decimal("1.00")
    assert SupplierInvoice.DUPLICATE_WINDOW_DAYS == 90
    assert SupplierInvoice.DUPLICATE_AMOUNT_TOL_PCT == Decimal("1.00")
    assert SupplierInvoice.DISCOUNT_GRACE_DAYS == 0
    assert SupplierInvoice.DISCOUNT_ANNUALISATION_DAYS == 360


@pytest.mark.parametrize("name", [
    "number", "invoice_number_norm", "due_date", "discount_date", "discount_expiry_date",
    "subtotal", "tax_total", "total", "amount_paid", "match_status", "match_notes",
    "bill", "journal_entry", "source_submission", "duplicate_of", "approved_by", "approved_at",
])
def test_invoice_supplier_invoice_derived_fields_are_not_editable(name):
    """L20/L22 - a derived or system column that is editable is a column a form can forge."""
    assert SupplierInvoice._meta.get_field(name).editable is False


@pytest.mark.parametrize("name", ["subtotal", "tax_total", "total", "amount_paid"])
def test_invoice_supplier_invoice_money_columns_default_to_zero(name):
    assert SupplierInvoice._meta.get_field(name).default == Decimal("0")


# -- the normalised duplicate key -------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("INV 100/A", "INV100A"),
    ("inv-100a", "INV100A"),
    ("  sup 7001 ", "SUP7001"),
    ("", ""),
    (None, ""),
    ("///", ""),
])
def test_invoice_normalise_invoice_number(raw, expected):
    assert SupplierInvoice.normalise_invoice_number(raw) == expected


def test_invoice_normalise_invoice_number_is_capped_at_64():
    assert len(SupplierInvoice.normalise_invoice_number("A" * 200)) == 64


def test_invoice_number_norm_is_derived_on_every_save(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="inv-100/a")
    obj.refresh_from_db()
    assert obj.invoice_number_norm == "INV100A"
    obj.invoice_number = "sup 7001"
    obj.save()
    obj.refresh_from_db()
    assert obj.invoice_number_norm == "SUP7001"


def test_invoice_number_norm_matches_the_fixture_contract(invoice_draft_a, invoice_duplicate_a):
    """SUP-7001 and "sup 7001" collide the way a human reading both would say they do."""
    assert invoice_draft_a.invoice_number_norm == "SUP7001"
    assert invoice_duplicate_a.invoice_number_norm == "SUP7001"


# -- dates derived from the payment term --------------------------------------------------------

def test_invoice_dates_are_derived_from_the_payment_term(tenant_a, invoice_vendor_a,
                                                         invoice_term_a):
    today = _invoice_today()
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a,
                          invoice_date=today)
    obj.refresh_from_db()
    assert obj.due_date == today + datetime.timedelta(days=30)
    assert obj.discount_date == today + datetime.timedelta(days=10)
    assert obj.discount_expiry_date == obj.discount_date


def test_invoice_fixture_dates_match_the_contract(invoice_draft_a):
    assert invoice_draft_a.due_date == invoice_draft_a.invoice_date + datetime.timedelta(days=30)
    assert invoice_draft_a.discount_date == (invoice_draft_a.invoice_date
                                             + datetime.timedelta(days=10))
    assert invoice_draft_a.discount_expiry_date == invoice_draft_a.discount_date


def test_invoice_discount_dates_cleared_when_the_term_has_no_discount(tenant_a, invoice_vendor_a,
                                                                      invoice_term_a,
                                                                      invoice_term_net30_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a)
    assert obj.discount_date is not None
    obj.payment_term = invoice_term_net30_a
    obj.save()
    obj.refresh_from_db()
    assert obj.due_date == obj.invoice_date + datetime.timedelta(days=30)
    # A stale discount date from an earlier term must not claim a window that no longer exists.
    assert obj.discount_date is None
    assert obj.discount_expiry_date is None


def test_invoice_dates_cleared_when_the_payment_term_is_removed(tenant_a, invoice_vendor_a,
                                                                invoice_term_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a)
    obj.payment_term = None
    obj.save()
    obj.refresh_from_db()
    assert obj.due_date is None
    assert obj.discount_date is None
    assert obj.discount_expiry_date is None


def test_invoice_discount_grace_days_extend_the_expiry(tenant_a, invoice_vendor_a,
                                                       invoice_term_a):
    today = _invoice_today()
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a,
                          invoice_date=today, discount_grace_days=3)
    obj.refresh_from_db()
    assert obj.discount_date == today + datetime.timedelta(days=10)
    assert obj.discount_expiry_date == today + datetime.timedelta(days=13)


def test_invoice_is_locked_only_on_terminal_statuses(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    for status, _label in SupplierInvoice.STATUS_CHOICES:
        obj.status = status
        assert obj.is_locked is (status in SupplierInvoice.TERMINAL_STATUSES), status


def test_invoice_paid_fixture_is_locked(invoice_paid_a, invoice_draft_a):
    assert invoice_paid_a.is_locked is True
    assert invoice_draft_a.is_locked is False


# =============================================================================================
# SupplierInvoice - derived money, the discount, duplicates and the cumulative aggregates
# =============================================================================================

def test_invoice_recalc_totals_derives_the_money_from_the_lines(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    _invoice_line_row(obj, quantity=Decimal("10"), unit_price=Decimal("25.00"),
                      tax_rate_pct=Decimal("20.00"))
    obj.refresh_from_db()
    assert obj.subtotal == Decimal("250.00")
    assert obj.tax_total == Decimal("50.00")
    assert obj.total == Decimal("300.00")


def test_invoice_totals_follow_a_line_edit(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    line = _invoice_line_row(obj)
    obj.refresh_from_db()
    assert obj.total == Decimal("250.00")
    line.unit_price = Decimal("30.00")
    line.save()
    obj.refresh_from_db()
    assert obj.subtotal == Decimal("300.00")
    assert obj.total == Decimal("300.00")


def test_invoice_totals_are_re_derived_after_a_line_is_removed(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    line = _invoice_line_row(obj)
    line.delete()
    obj.recalc_totals()
    obj.refresh_from_db()
    assert obj.subtotal == Decimal("0.00")
    assert obj.tax_total == Decimal("0.00")
    assert obj.total == Decimal("0.00")


def test_invoice_recalc_totals_can_be_computed_without_saving(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    _invoice_line_row(obj)
    stored = SupplierInvoice.objects.get(pk=obj.pk)
    stored.subtotal = Decimal("0.00")
    stored.recalc_totals(save=False)
    assert stored.subtotal == Decimal("250.00")
    assert SupplierInvoice.objects.get(pk=obj.pk).subtotal == Decimal("250.00")


def test_invoice_amount_paid_is_zero_without_a_bill(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    _invoice_line_row(obj)
    obj.refresh_from_db()
    assert obj.bill_id is None
    assert obj.amount_paid == Decimal("0.00")


def test_invoice_fixture_totals_match_the_contract(invoice_draft_a, invoice_line_a):
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.total == Decimal("250.00")


def test_invoice_credit_memo_total_is_negative(invoice_credit_memo_a):
    assert invoice_credit_memo_a.total == Decimal("-50.00")


# -- the early-payment discount -----------------------------------------------------------------

def test_invoice_discount_amount_on_the_net_of_tax_base(tenant_a, invoice_vendor_a,
                                                        invoice_term_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a)
    _invoice_line_row(obj, tax_rate_pct=Decimal("20.00"))
    obj.refresh_from_db()
    assert obj.subtotal == Decimal("250.00") and obj.total == Decimal("300.00")
    assert obj.discount_base == "net_of_tax"
    assert obj.discount_amount() == Decimal("5.00")


def test_invoice_discount_amount_on_the_gross_base(tenant_a, invoice_vendor_a, invoice_term_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a,
                          discount_base="gross")
    _invoice_line_row(obj, tax_rate_pct=Decimal("20.00"))
    obj.refresh_from_db()
    assert obj.discount_amount() == Decimal("6.00")


def test_invoice_discount_amount_is_zero_without_a_term(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    _invoice_line_row(obj)
    obj.refresh_from_db()
    assert obj.discount_amount() == Decimal("0")


def test_invoice_discount_amount_is_zero_on_a_term_without_a_discount(tenant_a, invoice_vendor_a,
                                                                      invoice_term_net30_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_net30_a)
    _invoice_line_row(obj)
    obj.refresh_from_db()
    assert obj.discount_amount() == Decimal("0")


def test_invoice_discount_amount_uses_the_size_of_a_credit_memo(tenant_a, invoice_vendor_a,
                                                                invoice_term_a):
    memo = _invoice_header(tenant_a, invoice_vendor_a, invoice_type="credit_memo",
                           payment_term=invoice_term_a)
    _invoice_line_row(memo, quantity=Decimal("1"), unit_price=Decimal("-50.00"))
    memo.refresh_from_db()
    assert memo.subtotal == Decimal("-50.00")
    assert memo.discount_amount() == Decimal("1.00")


def test_invoice_annualised_pct_of_2_10_net_30(tenant_a, invoice_vendor_a, invoice_term_a):
    """What "2/10 Net 30" is really worth as an annual rate."""
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a)
    assert obj.annualised_pct() == Decimal("36.73")


def test_invoice_annualised_pct_is_zero_without_a_term(tenant_a, invoice_vendor_a):
    assert _invoice_header(tenant_a, invoice_vendor_a).annualised_pct() == Decimal("0")


def test_invoice_annualised_pct_is_zero_without_a_discount(tenant_a, invoice_vendor_a,
                                                           invoice_term_net30_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_net30_a)
    assert obj.annualised_pct() == Decimal("0")


def test_invoice_annualised_pct_is_zero_when_the_window_is_not_shorter(tenant_a,
                                                                       invoice_vendor_a,
                                                                       invoice_term_a):
    """A "2/10 Net 10" is a straight price cut, not credit - so it annualises to nothing."""
    invoice_term_a.days_due = 10
    invoice_term_a.save()
    obj = _invoice_header(tenant_a, invoice_vendor_a, payment_term=invoice_term_a)
    assert obj.annualised_pct() == Decimal("0")


# -- duplicate detection --------------------------------------------------------------------------

def test_invoice_duplicate_candidates_report_the_twin_with_four_reasons(invoice_draft_a,
                                                                        invoice_line_a,
                                                                        invoice_duplicate_a):
    candidates = invoice_draft_a.duplicate_candidates()
    assert [row.pk for row, _reasons in candidates] == [invoice_duplicate_a.pk]
    reasons = candidates[0][1]
    assert reasons[0] == "normalised invoice number matches"
    assert "same vendor" in reasons
    assert "amount within 1%" in reasons
    assert f"invoice date within {SupplierInvoice.DUPLICATE_WINDOW_DAYS} days" in reasons
    assert len(reasons) == 4


def test_invoice_duplicate_candidates_never_include_self(invoice_draft_a, invoice_line_a,
                                                         invoice_duplicate_a):
    assert invoice_draft_a.pk not in [row.pk for row, _r in invoice_draft_a.duplicate_candidates()]


def test_invoice_duplicate_candidates_are_empty_without_a_normalised_number(tenant_a,
                                                                            invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="///")
    obj.refresh_from_db()
    assert obj.invoice_number_norm == ""
    assert obj.duplicate_candidates() == []


def test_invoice_duplicate_candidates_are_empty_without_a_tenant(invoice_vendor_a):
    orphan = SupplierInvoice(vendor=invoice_vendor_a, invoice_number="SUP-1",
                             invoice_date=_invoice_today())
    orphan.invoice_number_norm = "SUP1"
    assert orphan.duplicate_candidates() == []


def test_invoice_duplicate_candidates_never_cross_a_tenant_boundary(tenant_a, tenant_b,
                                                                    invoice_vendor_a,
                                                                    invoice_vendor_b):
    mine = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SHARED-1")
    _invoice_line_row(mine)
    mine.refresh_from_db()
    theirs = _invoice_header(tenant_b, invoice_vendor_b, invoice_number="shared 1")
    _invoice_line_row(theirs)
    theirs.refresh_from_db()
    assert mine.invoice_number_norm == theirs.invoice_number_norm == "SHARED1"
    assert mine.duplicate_candidates() == []


def test_invoice_duplicate_candidates_need_three_reasons(tenant_a, invoice_vendor_a,
                                                         invoice_vendor_other_a):
    """A coincidental number match alone is silent - a suspicion needs corroboration."""
    mine = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="COINCIDENCE-1")
    _invoice_line_row(mine)
    mine.refresh_from_db()
    far = _invoice_header(tenant_a, invoice_vendor_other_a, invoice_number="coincidence 1",
                          invoice_date=_invoice_today() - datetime.timedelta(days=200))
    _invoice_line_row(far, quantity=Decimal("40"), unit_price=Decimal("25.00"))
    far.refresh_from_db()
    assert far.total != mine.total
    assert mine.duplicate_candidates() == []


def test_invoice_duplicate_candidates_accept_a_prefetched_bucket(invoice_draft_a,
                                                                 invoice_line_a,
                                                                 invoice_duplicate_a,
                                                                 django_assert_num_queries):
    """The batch escape hatch the duplicate board uses - scoring without a database hit."""
    bucket = list(SupplierInvoice.objects.filter(
        tenant=invoice_draft_a.tenant_id,
        invoice_number_norm=invoice_draft_a.invoice_number_norm).order_by("-invoice_date", "-id"))
    with django_assert_num_queries(0):
        candidates = invoice_draft_a.duplicate_candidates(candidates=bucket)
    assert [row.pk for row, _r in candidates] == [invoice_duplicate_a.pk]


# -- the cumulative aggregates (derived, never stored) ---------------------------------------------

@pytest.mark.parametrize("name", ["cumulative_invoiced_qty", "cumulative_received_qty"])
def test_invoice_cumulative_quantities_are_not_columns(name):
    """L29 - a stored counter drifts the first time a receipt is cancelled."""
    with pytest.raises(FieldDoesNotExist):
        SupplierInvoice._meta.get_field(name)
    with pytest.raises(FieldDoesNotExist):
        SupplierInvoiceLine._meta.get_field(name)


def test_invoice_cumulative_invoiced_qty_sums_every_live_invoice(tenant_a, invoice_vendor_a,
                                                                 invoice_po_a,
                                                                 invoice_po_line_a):
    assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("0")
    first = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                            invoice_number="CUM-1")
    _invoice_line_row(first, po_line=invoice_po_line_a, quantity=Decimal("6"))
    assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("6")
    second = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                             invoice_number="CUM-2")
    _invoice_line_row(second, po_line=invoice_po_line_a, quantity=Decimal("4"))
    assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("10")


def test_invoice_cumulative_invoiced_qty_excludes_terminal_invoices(tenant_a, invoice_vendor_a,
                                                                    invoice_po_a,
                                                                    invoice_po_line_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                          invoice_number="CUM-3")
    _invoice_line_row(obj, po_line=invoice_po_line_a, quantity=Decimal("7"))
    assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("7")
    for status in SupplierInvoice.TERMINAL_STATUSES:
        SupplierInvoice.objects.filter(pk=obj.pk).update(status=status)
        assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("0"), status


def test_invoice_cumulative_invoiced_qty_excludes_credit_memos(tenant_a, invoice_vendor_a,
                                                               invoice_po_a, invoice_po_line_a):
    """A memo reduces what is owed; it does not un-invoice a delivery."""
    memo = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                           invoice_number="CUM-CM", invoice_type="credit_memo")
    _invoice_line_row(memo, po_line=invoice_po_line_a, quantity=Decimal("2"),
                      unit_price=Decimal("-25.00"))
    assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("0")


def test_invoice_cumulative_invoiced_qty_is_scoped_to_the_orders_tenant(tenant_a, tenant_b,
                                                                        invoice_vendor_a,
                                                                        invoice_vendor_b,
                                                                        invoice_po_a,
                                                                        invoice_po_line_a):
    """The control that stops a supplier billing twice must never read across a tenant line."""
    mine = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                           invoice_number="CUM-A")
    _invoice_line_row(mine, po_line=invoice_po_line_a, quantity=Decimal("3"))
    crafted = _invoice_header(tenant_b, invoice_vendor_b, invoice_number="CUM-B")
    _invoice_line_row(crafted, po_line=invoice_po_line_a, quantity=Decimal("99"))
    assert SupplierInvoice.cumulative_invoiced_qty(invoice_po_line_a) == Decimal("3")


def test_invoice_cumulative_received_qty_sums_the_receipt_lines(invoice_po_line_a,
                                                                invoice_grn_line_a):
    assert SupplierInvoice.cumulative_received_qty(invoice_po_line_a) == Decimal("10")


def test_invoice_cumulative_received_qty_excludes_cancelled_receipts(invoice_grn_a,
                                                                     invoice_po_line_a,
                                                                     invoice_grn_line_a):
    type(invoice_grn_a).objects.filter(pk=invoice_grn_a.pk).update(status="cancelled")
    assert SupplierInvoice.cumulative_received_qty(invoice_po_line_a) == Decimal("0")


def test_invoice_cumulative_quantities_are_zero_without_a_po_line():
    assert SupplierInvoice.cumulative_invoiced_qty(None) == Decimal("0")
    assert SupplierInvoice.cumulative_received_qty(None) == Decimal("0")


# =============================================================================================
# SupplierInvoice.clean() - the header's own guards
# =============================================================================================

def test_invoice_clean_rejects_a_cross_tenant_vendor(tenant_a, invoice_vendor_b):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_b, invoice_number="X-1",
                          invoice_date=_invoice_today())
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "vendor" in excinfo.value.message_dict


def test_invoice_clean_rejects_a_cross_tenant_payment_term(tenant_a, invoice_vendor_a,
                                                           invoice_term_b):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-2",
                          invoice_date=_invoice_today(), payment_term=invoice_term_b)
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "payment_term" in excinfo.value.message_dict


def test_invoice_clean_rejects_an_order_from_a_different_vendor(tenant_a, invoice_vendor_a,
                                                                invoice_po_other_a):
    """An invoice FROM one supplier against another supplier's order is a mis-key at best."""
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-3",
                          invoice_date=_invoice_today(), purchase_order=invoice_po_other_a)
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["purchase_order"] == [
        "That purchase order belongs to a different vendor."]


def test_invoice_clean_rejects_a_receipt_from_a_different_vendor(tenant_a, invoice_vendor_a,
                                                                 invoice_po_other_a):
    from apps.scm.models import GoodsReceiptNote
    grn = GoodsReceiptNote.objects.create(tenant=tenant_a, purchase_order=invoice_po_other_a,
                                          receipt_date=_invoice_today(), status="draft")
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-4",
                          invoice_date=_invoice_today(), goods_receipt=grn)
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["goods_receipt"] == [
        "That goods receipt belongs to a different vendor."]


def test_invoice_clean_accepts_the_matching_vendor(tenant_a, invoice_vendor_a, invoice_po_a,
                                                   invoice_grn_a):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-5",
                          invoice_date=_invoice_today(), purchase_order=invoice_po_a,
                          goods_receipt=invoice_grn_a)
    obj.clean()


def test_invoice_clean_rejects_a_posting_date_before_the_invoice_date(tenant_a,
                                                                      invoice_vendor_a):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-6",
                          invoice_date=_invoice_today(),
                          posting_date=_invoice_today() - datetime.timedelta(days=1))
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "posting_date" in excinfo.value.message_dict


@pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-1.5")])
def test_invoice_clean_rejects_a_non_positive_fx_rate(tenant_a, invoice_vendor_a, rate):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-7",
                          invoice_date=_invoice_today(), fx_rate=rate)
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "fx_rate" in excinfo.value.message_dict


@pytest.mark.parametrize("junk", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_invoice_clean_rejects_a_non_finite_fx_rate(tenant_a, invoice_vendor_a, junk):
    """NaN and Infinity parse cleanly and then die on the comparison - never a 500 (L35)."""
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-8",
                          invoice_date=_invoice_today(), fx_rate=junk)
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "fx_rate" in excinfo.value.message_dict


def test_invoice_clean_rejects_grace_days_above_365(tenant_a, invoice_vendor_a):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="X-9",
                          invoice_date=_invoice_today(), discount_grace_days=400)
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "discount_grace_days" in excinfo.value.message_dict


@pytest.mark.parametrize("blank", ["", "   "])
def test_invoice_clean_rejects_a_blank_supplier_invoice_number(tenant_a, invoice_vendor_a,
                                                               blank):
    obj = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number=blank,
                          invoice_date=_invoice_today())
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "invoice_number" in excinfo.value.message_dict


def test_invoice_clean_rejects_a_self_duplicate_link(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    obj.duplicate_of = obj
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "duplicate_of" in excinfo.value.message_dict


def test_invoice_clean_rejects_a_positive_line_on_a_credit_memo(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a)
    _invoice_line_row(obj)
    obj.invoice_type = "credit_memo"
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "invoice_type" in excinfo.value.message_dict


def test_invoice_clean_rejects_a_negative_line_on_a_standard_invoice(tenant_a, invoice_vendor_a):
    memo = _invoice_header(tenant_a, invoice_vendor_a, invoice_type="credit_memo")
    _invoice_line_row(memo, quantity=Decimal("1"), unit_price=Decimal("-50.00"))
    memo.invoice_type = "standard"
    with pytest.raises(ValidationError) as excinfo:
        memo.clean()
    assert "invoice_type" in excinfo.value.message_dict


# =============================================================================================
# SupplierInvoice - the guarded verb ladder
# =============================================================================================

def test_invoice_park_and_unpark(invoice_draft_a):
    assert invoice_draft_a.park() is True
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "parked"
    # A double submit no-ops rather than re-stamping.
    assert invoice_draft_a.park() is False
    assert invoice_draft_a.unpark() is True
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "draft"
    assert invoice_draft_a.unpark() is False


def test_invoice_capture_from_draft_and_from_parked(tenant_a, invoice_vendor_a):
    drafted = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="V-1")
    assert drafted.capture() is True
    assert drafted.status == "captured"
    # Captured is already past the capture queue.
    assert drafted.capture() is False

    parked = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="V-2", status="parked")
    assert parked.capture() is True
    assert parked.status == "captured"


def test_invoice_block_records_the_reason(invoice_captured_a):
    assert invoice_captured_a.block("Waiting on the delivery note") is True
    invoice_captured_a.refresh_from_db()
    assert invoice_captured_a.status == "blocked"
    assert invoice_captured_a.match_notes == "Waiting on the delivery note"


def test_invoice_block_refuses_from_draft(invoice_draft_a):
    assert invoice_draft_a.block("nope") is False
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "draft"
    assert invoice_draft_a.match_notes == ""


def test_invoice_raise_dispute_is_refused_without_an_open_variance(invoice_blocked_a):
    """L35 - an absent prerequisite is REJECTED, never fallen through: a dispute with nothing
    to point at cannot be answered."""
    assert invoice_blocked_a.variances.count() == 0
    assert invoice_blocked_a.raise_dispute() is False
    invoice_blocked_a.refresh_from_db()
    assert invoice_blocked_a.status == "blocked"


def test_invoice_raise_dispute_is_refused_when_every_variance_is_settled(
        invoice_blocked_a, invoice_variance_accepted_a):
    assert invoice_blocked_a.variances.filter(resolution="open").count() == 0
    assert invoice_blocked_a.raise_dispute() is False
    invoice_blocked_a.refresh_from_db()
    assert invoice_blocked_a.status == "blocked"


def test_invoice_raise_dispute_succeeds_with_an_open_variance(invoice_blocked_a,
                                                              invoice_variance_block_a):
    assert invoice_blocked_a.raise_dispute() is True
    invoice_blocked_a.refresh_from_db()
    assert invoice_blocked_a.status == "disputed"


def test_invoice_raise_dispute_refuses_outside_blocked(invoice_captured_a):
    _invoice_variance_row(invoice_captured_a)
    assert invoice_captured_a.raise_dispute() is False


def test_invoice_submit_for_approval_from_captured_and_disputed(tenant_a, invoice_vendor_a):
    captured = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="V-3",
                               status="captured")
    assert captured.submit_for_approval() is True
    assert captured.status == "pending_approval"
    assert captured.submit_for_approval() is False

    disputed = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="V-4",
                               status="disputed")
    assert disputed.submit_for_approval() is True
    assert disputed.status == "pending_approval"


def test_invoice_submit_for_approval_refuses_a_draft(invoice_draft_a):
    assert invoice_draft_a.submit_for_approval() is False
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "draft"


def test_invoice_send_back_returns_to_blocked_with_the_reason(invoice_pending_a):
    assert invoice_pending_a.send_back("Prices not agreed") is True
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "blocked"
    assert invoice_pending_a.match_notes == "Prices not agreed"
    assert invoice_pending_a.send_back("again") is False


def test_invoice_override_accepts_every_open_blocking_variance(invoice_blocked_a, admin_user,
                                                               invoice_variance_block_a,
                                                               invoice_variance_warn_a,
                                                               invoice_variance_accepted_a):
    assert invoice_blocked_a.override(admin_user) is True
    invoice_blocked_a.refresh_from_db()
    assert invoice_blocked_a.status == "pending_approval"
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "accepted"
    # A warning was never blocking, and an already-settled row is not re-opened.
    invoice_variance_warn_a.refresh_from_db()
    assert invoice_variance_warn_a.resolution == "open"
    invoice_variance_accepted_a.refresh_from_db()
    assert invoice_variance_accepted_a.resolution == "accepted"
    assert "1 blocking variance(s) accepted" in invoice_blocked_a.match_notes
    assert admin_user.username in invoice_blocked_a.match_notes


def test_invoice_override_refuses_outside_blocked(invoice_pending_a, admin_user):
    assert invoice_pending_a.override(admin_user) is False
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "pending_approval"


def test_invoice_schedule_unschedule_and_mark_paid(tenant_a, invoice_vendor_a):
    obj = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="V-5", status="approved")
    assert obj.mark_paid() is False           # not scheduled yet
    assert obj.schedule() is True
    assert obj.status == "scheduled"
    assert obj.schedule() is False
    assert obj.unschedule() is True
    assert obj.status == "approved"
    assert obj.unschedule() is False
    obj.schedule()
    assert obj.mark_paid() is True
    obj.refresh_from_db()
    assert obj.status == "paid"
    assert obj.is_locked is True
    assert obj.mark_paid() is False


def test_invoice_scheduled_fixture_is_the_mark_paid_state(invoice_scheduled_a):
    assert invoice_scheduled_a.status == "scheduled"
    assert invoice_scheduled_a.total == Decimal("240.00")
    assert invoice_scheduled_a.due_date == _invoice_today() + datetime.timedelta(days=5)


def test_invoice_void_records_the_reason(invoice_draft_a):
    assert invoice_draft_a.void(None, reason="Keyed twice") is True
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "void"
    assert invoice_draft_a.notes.startswith("Keyed twice")


def test_invoice_void_refuses_a_locked_invoice(invoice_paid_a):
    assert invoice_paid_a.void(None, reason="too late") is False
    invoice_paid_a.refresh_from_db()
    assert invoice_paid_a.status == "paid"
    assert invoice_paid_a.notes == ""


def test_invoice_void_refuses_a_posted_invoice(invoice_pending_a, invoice_chart_a, admin_user):
    """A posted invoice is undone by reverse() - voiding one would strand the GL liability."""
    assert invoice_pending_a.approve(admin_user) is True
    assert invoice_pending_a.void(admin_user, reason="undo") is False
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "approved"


# =============================================================================================
# SupplierInvoice.run_match() - the three-way match engine
# =============================================================================================

def test_invoice_run_match_on_a_clean_three_way_match(invoice_draft_a, invoice_line_a,
                                                      admin_user):
    status, counts = invoice_draft_a.run_match(admin_user)
    assert status == "pending_approval"
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "pending_approval"
    assert invoice_draft_a.match_status == "matched"
    assert invoice_draft_a.match_basis == "quantity"
    assert counts["block"] == 0
    assert counts["warn"] == 0
    assert counts["auto_accept"] == invoice_draft_a.variances.count() == 5
    assert {v.variance_type for v in invoice_draft_a.variances.all()} == {
        "quantity", "price", "total_amount", "tax"}


def test_invoice_run_match_is_rerunnable(invoice_draft_a, invoice_line_a, admin_user):
    """The previous run's verdicts are stale the moment anything is corrected."""
    invoice_draft_a.run_match(admin_user)
    first = list(invoice_draft_a.variances.values_list("pk", flat=True))
    invoice_draft_a.run_match(admin_user)
    second = list(invoice_draft_a.variances.values_list("pk", flat=True))
    assert len(first) == len(second) == 5
    assert not set(first) & set(second)


def test_invoice_run_match_blocks_a_price_variance(tenant_a, invoice_vendor_a, invoice_po_a,
                                                   invoice_grn_a, invoice_po_line_a,
                                                   invoice_grn_line_a, admin_user):
    obj = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-9100",
                          purchase_order=invoice_po_a, goods_receipt=invoice_grn_a)
    _invoice_line_row(obj, po_line=invoice_po_line_a, receipt_line=invoice_grn_line_a,
                      unit_price=Decimal("30.00"))
    obj.refresh_from_db()
    assert obj.total == Decimal("300.00")
    status, counts = obj.run_match(admin_user)
    assert status == "blocked"
    obj.refresh_from_db()
    assert obj.status == "blocked"
    # The FIRST breach wins: fixing the unit price is what the supplier has to do.
    assert obj.match_status == "price_variance"
    assert obj.match_basis == "quantity"
    assert counts["block"] >= 1
    price = obj.variances.get(variance_type="price")
    assert price.outcome == "block"
    assert price.expected_value == Decimal("25.0000")
    assert price.actual_value == Decimal("30.0000")
    assert price.variance_pct == Decimal("20.0000")


def test_invoice_run_match_stamps_matched_qty(invoice_draft_a, invoice_line_a, admin_user):
    assert invoice_line_a.matched_qty == Decimal("0")
    invoice_draft_a.run_match(admin_user)
    invoice_line_a.refresh_from_db()
    assert invoice_line_a.matched_qty == Decimal("10.0000")


def test_invoice_run_match_early_returns_when_locked(invoice_paid_a, admin_user):
    status, counts = invoice_paid_a.run_match(admin_user)
    assert status == "paid"
    assert counts == {"auto_accept": 0, "warn": 0, "block": 0}
    invoice_paid_a.refresh_from_db()
    assert invoice_paid_a.match_status == "not_run"
    assert invoice_paid_a.variances.count() == 0


def test_invoice_run_match_early_returns_on_a_credit_memo(invoice_credit_memo_a, admin_user):
    """A memo settles a claim - there is nothing to three-way match it against."""
    status, counts = invoice_credit_memo_a.run_match(admin_user)
    assert status == "captured"
    assert counts == {"auto_accept": 0, "warn": 0, "block": 0}
    invoice_credit_memo_a.refresh_from_db()
    assert invoice_credit_memo_a.status == "captured"
    assert invoice_credit_memo_a.match_status == "not_run"
    assert invoice_credit_memo_a.match_notes == "Credit memos are not three-way matched."
    assert invoice_credit_memo_a.variances.count() == 0


def test_invoice_run_match_early_returns_once_posted(invoice_pending_a, invoice_chart_a,
                                                     admin_user):
    """Re-matching a GL-posted invoice would strand it off ``approved``."""
    assert invoice_pending_a.approve(admin_user) is True
    status, counts = invoice_pending_a.run_match(admin_user)
    assert status == "approved"
    assert counts == {"auto_accept": 0, "warn": 0, "block": 0}
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "approved"
    assert invoice_pending_a.variances.count() == 0


def test_invoice_run_match_blocks_a_non_po_line_without_a_gl_account(invoice_captured_a,
                                                                     admin_user):
    """A non-PO line has nowhere to post to unless someone names the account."""
    _invoice_line_row(invoice_captured_a, quantity=Decimal("2"), unit_price=Decimal("100.00"))
    invoice_captured_a.refresh_from_db()
    status, counts = invoice_captured_a.run_match(admin_user)
    assert status == "blocked"
    invoice_captured_a.refresh_from_db()
    assert invoice_captured_a.match_basis == "none"
    assert counts["block"] == 1
    assert invoice_captured_a.variances.filter(variance_type="missing_po",
                                               outcome="block").exists()


def test_invoice_run_match_passes_a_non_po_line_that_names_its_account(invoice_captured_a,
                                                                       gl_expense_a,
                                                                       admin_user):
    """L44 - the refusal above is paired with the case that must be allowed through."""
    _invoice_line_row(invoice_captured_a, quantity=Decimal("2"), unit_price=Decimal("100.00"),
                      gl_account=gl_expense_a)
    invoice_captured_a.refresh_from_db()
    status, counts = invoice_captured_a.run_match(admin_user)
    assert status == "pending_approval"
    assert counts["block"] == 0
    invoice_captured_a.refresh_from_db()
    assert invoice_captured_a.match_basis == "none"
    assert invoice_captured_a.match_status == "matched"


def test_invoice_run_match_blocks_a_line_with_no_purchase_order_line(tenant_a, invoice_vendor_a,
                                                                     invoice_po_a, admin_user):
    obj = _invoice_header(tenant_a, invoice_vendor_a, invoice_number="SUP-9101",
                          purchase_order=invoice_po_a)
    _invoice_line_row(obj)
    obj.refresh_from_db()
    status, _counts = obj.run_match(admin_user)
    assert status == "blocked"
    assert obj.variances.filter(variance_type="missing_po", basis="po",
                                outcome="block").exists()


def test_invoice_run_match_holds_a_duplicate_suspect(invoice_draft_a, invoice_line_a,
                                                     invoice_duplicate_a, admin_user):
    """A duplicate never blocks a variance (cap="warn") but it does hold the invoice."""
    status, counts = invoice_draft_a.run_match(admin_user)
    assert status == "blocked"
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.match_status == "duplicate_suspect"
    duplicate = invoice_draft_a.variances.get(variance_type="duplicate")
    assert duplicate.outcome != "block"
    assert duplicate.message.startswith(f"Possible duplicate of {invoice_duplicate_a.number}")
    assert counts["block"] == 0


# =============================================================================================
# SupplierInvoice.approve() / reverse() - the ONLY ledger writers
# =============================================================================================

def test_invoice_approve_posts_a_bill_and_a_balanced_journal_entry(invoice_pending_a,
                                                                   invoice_chart_a,
                                                                   admin_user, tenant_a):
    assert invoice_pending_a.approve(admin_user) is True
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "approved"
    assert invoice_pending_a.bill_id is not None
    assert invoice_pending_a.journal_entry_id is not None
    assert invoice_pending_a.approved_by_id == admin_user.pk
    assert invoice_pending_a.approved_at is not None
    assert invoice_pending_a.posting_date == _invoice_today()

    bill = invoice_pending_a.bill
    assert bill.tenant_id == tenant_a.pk
    assert bill.party_id == invoice_pending_a.vendor_id
    assert bill.lines.count() == invoice_pending_a.lines.count() == 1

    entry = invoice_pending_a.journal_entry
    assert entry.entry_type == "invoice"
    assert entry.status == "posted"
    assert entry.is_balanced() is True
    debit, credit = entry.totals()
    assert debit == credit == Decimal("255.00")


def test_invoice_approve_is_idempotent_on_a_double_submit(invoice_pending_a, invoice_chart_a,
                                                          admin_user, tenant_a):
    """The back-button guard (C1): a second submit must not mint a second bill."""
    assert invoice_pending_a.approve(admin_user) is True
    first_entry = invoice_pending_a.journal_entry_id
    assert invoice_pending_a.approve(admin_user) is False        # the status guard
    # Force the status back to prove the journal_entry_id guard is what actually holds.
    SupplierInvoice.objects.filter(pk=invoice_pending_a.pk).update(status="pending_approval")
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.approve(admin_user) is False
    assert invoice_pending_a.journal_entry_id == first_entry
    assert Bill.objects.filter(tenant=tenant_a).count() == 1
    assert JournalEntry.objects.filter(tenant=tenant_a).count() == 1


def test_invoice_approve_refuses_outside_pending_approval(invoice_draft_a, invoice_chart_a,
                                                          admin_user, tenant_a):
    assert invoice_draft_a.approve(admin_user) is False
    invoice_draft_a.refresh_from_db()
    assert invoice_draft_a.status == "draft"
    assert invoice_draft_a.journal_entry_id is None
    assert Bill.objects.filter(tenant=tenant_a).count() == 0


def test_invoice_approve_without_a_chart_of_accounts_posts_nothing(invoice_pending_a,
                                                                   admin_user, tenant_a):
    """L35 - a missing prerequisite raises and rolls back; it never posts a half-entry."""
    with pytest.raises(ValidationError):
        invoice_pending_a.approve(admin_user)
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "pending_approval"
    assert invoice_pending_a.bill_id is None
    assert invoice_pending_a.journal_entry_id is None
    assert Bill.objects.filter(tenant=tenant_a).count() == 0
    assert JournalEntry.objects.filter(tenant=tenant_a).count() == 0


def test_invoice_approve_without_an_ap_account_posts_nothing(invoice_pending_a, gl_expense_a,
                                                             admin_user, tenant_a):
    with pytest.raises(ValidationError):
        invoice_pending_a.approve(admin_user)
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.journal_entry_id is None
    assert Bill.objects.filter(tenant=tenant_a).count() == 0
    assert JournalEntry.objects.filter(tenant=tenant_a).count() == 0


def test_invoice_approve_mirrors_the_lines_onto_the_bill(invoice_pending_a, invoice_chart_a,
                                                         admin_user):
    invoice_pending_a.approve(admin_user)
    source = invoice_pending_a.lines.first()
    bill_line = invoice_pending_a.bill.lines.first()
    assert bill_line.quantity == source.quantity
    assert bill_line.unit_price == source.unit_price
    assert bill_line.tax_rate_pct == source.tax_rate_pct
    assert bill_line.gl_account_id is not None


def test_invoice_reverse_mirrors_the_journal_entry(invoice_pending_a, invoice_chart_a,
                                                   admin_user):
    invoice_pending_a.approve(admin_user)
    original = invoice_pending_a.journal_entry
    assert invoice_pending_a.reverse(admin_user) is True
    invoice_pending_a.refresh_from_db()
    assert invoice_pending_a.status == "reversed"
    reversal = JournalEntry.objects.get(reversal_of=original)
    assert reversal.entry_type == "reversal"
    assert reversal.status == "posted"
    assert reversal.is_balanced() is True
    assert sorted((line.gl_account_id, line.debit, line.credit)
                  for line in original.lines.all()) == sorted(
        (line.gl_account_id, line.credit, line.debit) for line in reversal.lines.all())
    # The original entry is immutable - the correction is a NEW entry.
    original.refresh_from_db()
    assert original.entry_type == "invoice"


def test_invoice_reverse_refuses_without_a_journal_entry(invoice_draft_a, invoice_paid_a,
                                                         admin_user):
    assert invoice_draft_a.reverse(admin_user) is False
    assert invoice_paid_a.reverse(admin_user) is False
    invoice_paid_a.refresh_from_db()
    assert invoice_paid_a.status == "paid"


def test_invoice_reverse_refuses_a_second_time(invoice_pending_a, invoice_chart_a, admin_user):
    invoice_pending_a.approve(admin_user)
    assert invoice_pending_a.reverse(admin_user) is True
    assert invoice_pending_a.reverse(admin_user) is False


# =============================================================================================
# SupplierInvoiceLine - the PLAIN CHILD
# =============================================================================================

def test_invoice_line_defaults(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = SupplierInvoiceLine.objects.create(invoice=header)
    assert line.quantity == Decimal("1")
    assert line.unit_price == Decimal("0")
    assert line.tax_rate_pct == Decimal("0")
    assert line.line_total == Decimal("0.00")
    assert line.matched_qty == Decimal("0")
    assert line.description == "" and line.sku_hint == "" and line.uom_hint == ""
    for name in ("po_line_id", "receipt_line_id", "item_id", "gl_account_id", "tax_code_id"):
        assert getattr(line, name) is None


def test_invoice_line_str(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = SupplierInvoiceLine(invoice=header, description="A4 copy paper 80gsm",
                               quantity=Decimal("10"))
    assert str(line) == f"A4 copy paper 80gsm {_INVOICE_TIMES}10"


def test_invoice_line_str_falls_back_to_the_sku_then_to_a_label(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    sku_only = SupplierInvoiceLine(invoice=header, sku_hint="PPR-A4", quantity=Decimal("2"))
    assert str(sku_only) == f"PPR-A4 {_INVOICE_TIMES}2"
    bare = SupplierInvoiceLine(invoice=header, quantity=Decimal("3"))
    assert str(bare) == f"line {_INVOICE_TIMES}3"


def test_invoice_line_has_no_tenant_and_no_number_column():
    """A plain child is scoped through its header - ``invoice__tenant=``, never ``tenant=``."""
    with pytest.raises(FieldDoesNotExist):
        SupplierInvoiceLine._meta.get_field("tenant")
    with pytest.raises(FieldDoesNotExist):
        SupplierInvoiceLine._meta.get_field("number")


def test_invoice_line_meta_contract():
    meta = SupplierInvoiceLine._meta
    assert meta.ordering == ["id"]
    assert meta.verbose_name == "supplier invoice line"
    assert not meta.unique_together


@pytest.mark.parametrize("name", ["line_total", "matched_qty"])
def test_invoice_line_derived_fields_are_not_editable(name):
    assert SupplierInvoiceLine._meta.get_field(name).editable is False


def test_invoice_line_total_is_derived_on_save(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = _invoice_line_row(header, quantity=Decimal("3"), unit_price=Decimal("12.50"),
                             line_total=Decimal("999999.00"))
    line.refresh_from_db()
    assert line.line_total == Decimal("37.50")


def test_invoice_line_total_is_signed_on_a_credit_memo(invoice_credit_memo_a):
    """A credit memo's line total is negative by design - it is never abs()'d."""
    line = invoice_credit_memo_a.lines.get()
    assert line.line_total == Decimal("-50.00")
    assert invoice_credit_memo_a.total == Decimal("-50.00")


def test_invoice_line_mirrors_the_po_line_when_blank(tenant_a, invoice_vendor_a, invoice_po_a,
                                                     invoice_po_line_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a)
    line = SupplierInvoiceLine.objects.create(invoice=header, po_line=invoice_po_line_a,
                                              quantity=Decimal("1"))
    line.refresh_from_db()
    assert line.description == "A4 copy paper 80gsm"
    assert line.sku_hint == "PPR-A4"
    assert line.uom_hint == "EA"


def test_invoice_line_keeps_the_suppliers_own_wording(tenant_a, invoice_vendor_a, invoice_po_a,
                                                      invoice_po_line_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a)
    line = SupplierInvoiceLine.objects.create(invoice=header, po_line=invoice_po_line_a,
                                              description="COPY PAPER A4 (WHITE)")
    line.refresh_from_db()
    assert line.description == "COPY PAPER A4 (WHITE)"


def test_invoice_line_update_fields_write_skips_mirroring_and_recalc(tenant_a, invoice_vendor_a,
                                                                     invoice_po_a,
                                                                     invoice_po_line_a):
    """The ``update_fields`` guard is what stops run_match()'s partial write recursing."""
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a)
    line = _invoice_line_row(header, po_line=invoice_po_line_a)
    header.refresh_from_db()
    assert header.total == Decimal("250.00")

    line.description = ""
    line.unit_price = Decimal("30.00")
    line.save(update_fields=["description"])
    line.refresh_from_db()
    assert line.description == ""            # mirroring skipped
    assert line.line_total == Decimal("250.00")   # the derived column was not written
    header.refresh_from_db()
    assert header.total == Decimal("250.00")      # the header was not recalculated


def test_invoice_line_tax_amount_and_gross_total(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = _invoice_line_row(header, tax_rate_pct=Decimal("20.00"))
    assert line.line_total == Decimal("250.00")
    assert line.tax_amount == Decimal("50.00")
    assert line.gross_total == Decimal("300.00")


def test_invoice_line_is_matched(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = _invoice_line_row(header)
    assert line.is_matched is False
    line.matched_qty = Decimal("10")
    assert line.is_matched is True


def test_invoice_line_is_editable_reads_the_header_status(invoice_draft_a, invoice_line_a):
    """The register gates its Edit/Delete actions on exactly the rule the views enforce."""
    def _reload():
        return SupplierInvoiceLine.objects.select_related("invoice").get(pk=invoice_line_a.pk)

    assert _reload().is_editable is True
    for status in SupplierInvoice.EDITABLE_STATUSES:
        SupplierInvoice.objects.filter(pk=invoice_draft_a.pk).update(status=status)
        assert _reload().is_editable is True, status
    for status in ("blocked", "pending_approval", "approved", "paid"):
        SupplierInvoice.objects.filter(pk=invoice_draft_a.pk).update(status=status)
        assert _reload().is_editable is False, status


def test_invoice_line_cumulative_properties_are_derived(tenant_a, invoice_vendor_a, invoice_po_a,
                                                        invoice_po_line_a, invoice_grn_line_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a)
    line = _invoice_line_row(header, po_line=invoice_po_line_a, quantity=Decimal("4"))
    assert line.cumulative_invoiced_qty == Decimal("4")
    assert line.cumulative_received_qty == Decimal("10")
    # Add a second live invoice against the same ordered line: the aggregate moves with it.
    other = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                            invoice_number="SUP-CUM")
    _invoice_line_row(other, po_line=invoice_po_line_a, quantity=Decimal("2"))
    assert line.cumulative_invoiced_qty == Decimal("6")


def test_invoice_line_cumulative_properties_are_zero_without_a_po_line(tenant_a,
                                                                       invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = _invoice_line_row(header)
    assert line.cumulative_invoiced_qty == Decimal("0")
    assert line.cumulative_received_qty == Decimal("0")


# -- SupplierInvoiceLine.clean() ---------------------------------------------------------------

def test_invoice_line_clean_accepts_a_matched_line(tenant_a, invoice_vendor_a, invoice_po_a,
                                                   invoice_po_line_a, invoice_grn_line_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                             match_basis="quantity")
    line = _invoice_line_row(header, po_line=invoice_po_line_a,
                             receipt_line=invoice_grn_line_a)
    line.clean()


def test_invoice_line_clean_rejects_a_po_line_from_another_order(tenant_a, invoice_vendor_a,
                                                                 invoice_po_a,
                                                                 invoice_po_other_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                             match_basis="amount")
    other_line = invoice_po_other_a.lines.first()
    line = SupplierInvoiceLine(invoice=header, po_line=other_line, quantity=Decimal("1"),
                               unit_price=Decimal("12.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert excinfo.value.message_dict["po_line"] == [
        "That line belongs to a different purchase order."]


def test_invoice_line_clean_rejects_a_receipt_line_for_another_po_line(tenant_a,
                                                                       invoice_vendor_a,
                                                                       invoice_po_a,
                                                                       invoice_po_line2_a,
                                                                       invoice_grn_line_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, purchase_order=invoice_po_a,
                             match_basis="quantity")
    line = SupplierInvoiceLine(invoice=header, po_line=invoice_po_line2_a,
                               receipt_line=invoice_grn_line_a, quantity=Decimal("1"),
                               unit_price=Decimal("60.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert "receipt_line" in excinfo.value.message_dict


def test_invoice_line_clean_rejects_another_workspaces_receipt(tenant_a, invoice_vendor_a,
                                                               invoice_grn_line_b):
    header = _invoice_header(tenant_a, invoice_vendor_a, match_basis="amount")
    line = SupplierInvoiceLine(invoice=header, receipt_line=invoice_grn_line_b,
                               quantity=Decimal("1"), unit_price=Decimal("80.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert excinfo.value.message_dict["receipt_line"] == [
        "That goods receipt belongs to another workspace."]


@pytest.mark.parametrize("field,fixture_name", [
    ("item", "invoice_item_b"),
    ("gl_account", "gl_expense_b"),
    ("tax_code", "invoice_taxcode_b"),
])
def test_invoice_line_clean_rejects_a_cross_tenant_master(request, tenant_a, invoice_vendor_a,
                                                          field, fixture_name):
    header = _invoice_header(tenant_a, invoice_vendor_a, match_basis="amount")
    line = SupplierInvoiceLine(invoice=header, quantity=Decimal("1"),
                               unit_price=Decimal("10.00"),
                               **{field: request.getfixturevalue(fixture_name)})
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert excinfo.value.message_dict[field] == ["That record belongs to another workspace."]


def test_invoice_line_clean_rejects_an_oversized_quantity(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, match_basis="amount")
    line = SupplierInvoiceLine(invoice=header, quantity=Decimal("10000000000"),
                               unit_price=Decimal("1.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert "quantity" in excinfo.value.message_dict


def test_invoice_line_clean_rejects_an_oversized_unit_price(tenant_a, invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, match_basis="amount")
    line = SupplierInvoiceLine(invoice=header, quantity=Decimal("1"),
                               unit_price=Decimal("1000000000000"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert "unit_price" in excinfo.value.message_dict


@pytest.mark.parametrize("junk", [Decimal("NaN"), Decimal("Infinity")])
def test_invoice_line_clean_rejects_a_non_finite_figure(tenant_a, invoice_vendor_a, junk):
    header = _invoice_header(tenant_a, invoice_vendor_a, match_basis="amount")
    line = SupplierInvoiceLine(invoice=header, quantity=junk, unit_price=junk)
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert "quantity" in excinfo.value.message_dict
    assert "unit_price" in excinfo.value.message_dict


def test_invoice_line_clean_rejects_a_positive_line_on_a_credit_memo(tenant_a,
                                                                     invoice_vendor_a):
    memo = _invoice_header(tenant_a, invoice_vendor_a, invoice_type="credit_memo",
                           match_basis="amount")
    line = SupplierInvoiceLine(invoice=memo, quantity=Decimal("1"), unit_price=Decimal("50.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert excinfo.value.message_dict["unit_price"] == [
        "A credit memo line cannot carry a positive value."]


def test_invoice_line_clean_rejects_a_negative_line_on_a_standard_invoice(tenant_a,
                                                                          invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a, match_basis="amount")
    line = SupplierInvoiceLine(invoice=header, quantity=Decimal("1"),
                               unit_price=Decimal("-50.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert excinfo.value.message_dict["unit_price"] == [
        "Only a credit memo may carry a negative line."]


def test_invoice_line_clean_requires_a_gl_account_on_a_non_po_invoice(tenant_a,
                                                                      invoice_vendor_a):
    header = _invoice_header(tenant_a, invoice_vendor_a)
    assert header.match_basis == "none"
    line = SupplierInvoiceLine(invoice=header, quantity=Decimal("1"), unit_price=Decimal("9.00"))
    with pytest.raises(ValidationError) as excinfo:
        line.clean()
    assert excinfo.value.message_dict["gl_account"] == [
        "A line on a non-PO invoice must name the GL account to post to."]


def test_invoice_line_clean_accepts_a_named_gl_account_on_a_non_po_invoice(tenant_a,
                                                                           invoice_vendor_a,
                                                                           gl_expense_a):
    """L44 - the refusal above is paired with the case that must be allowed through."""
    header = _invoice_header(tenant_a, invoice_vendor_a)
    line = SupplierInvoiceLine(invoice=header, quantity=Decimal("1"),
                               unit_price=Decimal("9.00"), gl_account=gl_expense_a)
    line.clean()


# =============================================================================================
# InvoiceMatchVariance - the exception register (EVIDENCE, not a record)
# =============================================================================================

def test_invoice_variance_defaults(invoice_draft_a):
    row = InvoiceMatchVariance.objects.create(
        tenant=invoice_draft_a.tenant, invoice=invoice_draft_a, variance_type="price",
        basis="po", expected_value=Decimal("25.0000"), actual_value=Decimal("30.0000"))
    assert row.outcome == "auto_accept"
    assert row.resolution == "open"
    assert row.message == ""
    assert row.invoice_line_id is None       # NULL => a header-level check
    assert row.dispute_id is None
    assert row.tolerance_abs_applied is None
    assert row.tolerance_pct_applied is None
    assert row.detected_at is not None


def test_invoice_variance_str_uses_the_invoice_id_only(invoice_variance_block_a,
                                                       invoice_blocked_a,
                                                       django_assert_num_queries):
    """__str__ runs on every register row and must not fan out an FK query."""
    row = InvoiceMatchVariance.objects.get(pk=invoice_variance_block_a.pk)
    with django_assert_num_queries(0):
        label = str(row)
    assert label == f"Unit Price on invoice #{invoice_blocked_a.pk}"


def test_invoice_variance_has_its_own_tenant_and_no_number():
    """Unlike SupplierInvoiceLine, this model IS tenant-scoped in its own right."""
    assert InvoiceMatchVariance._meta.get_field("tenant") is not None
    with pytest.raises(FieldDoesNotExist):
        InvoiceMatchVariance._meta.get_field("number")


def test_invoice_variance_meta_contract():
    meta = InvoiceMatchVariance._meta
    assert meta.ordering == ["-detected_at", "-id"]
    assert not meta.unique_together
    assert meta.verbose_name == "invoice match variance"


def test_invoice_variance_type_choices_exact():
    assert [value for value, _label in _invoice_variance_type_choices] == [
        "price", "quantity", "quantity_no_receipt", "over_invoice", "total_amount",
        "fx_rate", "tax", "duplicate", "missing_po", "missing_receipt"]


def test_invoice_variance_outcome_choices_exact():
    assert [value for value, _label in _invoice_outcome_choices] == [
        "auto_accept", "warn", "block"]


def test_invoice_variance_resolution_choices_exact():
    assert [value for value, _label in _invoice_variance_resolution_choices] == [
        "open", "accepted", "disputed", "credit_memo", "debit_memo", "short_paid", "cancelled"]


def test_invoice_variance_basis_choices_exact():
    assert [value for value, _label in _invoice_basis_choices] == ["po", "receipt", "header"]


def test_invoice_variance_badge_maps_cover_every_choice():
    assert set(InvoiceMatchVariance.OUTCOME_CSS) == {v for v, _l in _invoice_outcome_choices}
    assert set(InvoiceMatchVariance.RESOLUTION_CSS) == {
        v for v, _l in _invoice_variance_resolution_choices}
    for mapping in (InvoiceMatchVariance.OUTCOME_CSS, InvoiceMatchVariance.RESOLUTION_CSS):
        assert set(mapping.values()) <= _INVOICE_BADGE_COLOURS


def test_invoice_variance_badge_properties_fall_back_to_slate(invoice_variance_block_a):
    assert invoice_variance_block_a.outcome_css == "badge-red"
    assert invoice_variance_block_a.resolution_css == "badge-amber"
    invoice_variance_block_a.outcome = "nope"
    invoice_variance_block_a.resolution = "nope"
    assert invoice_variance_block_a.outcome_css == "badge-slate"
    assert invoice_variance_block_a.resolution_css == "badge-slate"


@pytest.mark.parametrize("name", ["variance_abs", "variance_pct"])
def test_invoice_variance_derived_fields_are_not_editable(name):
    assert InvoiceMatchVariance._meta.get_field(name).editable is False


def test_invoice_variance_figures_are_derived_on_every_write(invoice_draft_a):
    row = _invoice_variance_row(invoice_draft_a, variance_abs=Decimal("999.0000"),
                                variance_pct=Decimal("999.0000"))
    row.refresh_from_db()
    assert row.variance_abs == Decimal("5.0000")
    assert row.variance_pct == Decimal("20.0000")
    # Not only on create: the two figures are a pure function of expected/actual.
    row.actual_value = Decimal("20.0000")
    row.save()
    row.refresh_from_db()
    assert row.variance_abs == Decimal("-5.0000")
    assert row.variance_pct == Decimal("-20.0000")


def test_invoice_variance_fixture_figures_match_the_contract(invoice_variance_block_a):
    assert invoice_variance_block_a.variance_abs == Decimal("5.0000")
    assert invoice_variance_block_a.variance_pct == Decimal("20.0000")


def test_invoice_variance_pct_is_null_when_expected_is_zero(invoice_draft_a):
    row = _invoice_variance_row(invoice_draft_a, expected_value=Decimal("0.0000"),
                                actual_value=Decimal("12.0000"))
    row.refresh_from_db()
    assert row.variance_pct is None
    assert row.variance_abs == Decimal("12.0000")


def test_invoice_variance_pct_is_clamped_to_the_column_width(invoice_draft_a):
    """A one-cent variance on a 0.0001 unit price is 999,900% and would die on INSERT."""
    row = _invoice_variance_row(invoice_draft_a, expected_value=Decimal("0.0001"),
                                actual_value=Decimal("1.0000"))
    row.refresh_from_db()
    assert row.variance_pct == Decimal("99999.9999")
    assert row.variance_abs == Decimal("0.9999")


def test_invoice_variance_record_computes_the_outcome(invoice_draft_a):
    row = InvoiceMatchVariance.record(
        invoice=invoice_draft_a, variance_type="price", basis="po",
        expected=Decimal("25"), actual=Decimal("30"), pct_upper=Decimal("2.00"),
        message="Unit price differs from the purchase order.")
    assert row.outcome == "block"
    assert row.tenant_id == invoice_draft_a.tenant_id
    assert row.tolerance_pct_applied == Decimal("2.00")
    assert row.variance_abs == Decimal("5.0000")
    assert row.resolution == "open"


def test_invoice_variance_record_honours_an_outcome_override(invoice_draft_a):
    """A missing PO is wrong whatever the numbers say."""
    row = InvoiceMatchVariance.record(
        invoice=invoice_draft_a, variance_type="missing_po", basis="header",
        expected=Decimal("0"), actual=Decimal("0"), outcome_override="block",
        message="This line has no purchase-order line to match against.")
    assert row.outcome == "block"


def test_invoice_variance_record_cap_warn_downgrades_an_override(invoice_draft_a):
    row = InvoiceMatchVariance.record(
        invoice=invoice_draft_a, variance_type="duplicate", basis="header",
        expected=Decimal("250"), actual=Decimal("250"), outcome_override="block", cap="warn",
        message="Possible duplicate.")
    assert row.outcome == "warn"


def test_invoice_variance_record_truncates_a_long_message(invoice_draft_a):
    row = InvoiceMatchVariance.record(
        invoice=invoice_draft_a, variance_type="duplicate", basis="header",
        expected=Decimal("1"), actual=Decimal("1"), message="x" * 400)
    row.refresh_from_db()
    assert len(row.message) == 255


def test_invoice_variance_is_blocking_and_is_open(invoice_variance_block_a,
                                                  invoice_variance_warn_a,
                                                  invoice_variance_accepted_a):
    assert invoice_variance_block_a.is_blocking is True
    assert invoice_variance_block_a.is_open is True
    assert invoice_variance_warn_a.is_blocking is False
    assert invoice_variance_warn_a.is_open is True
    assert invoice_variance_accepted_a.is_open is False


def test_invoice_variance_can_accept(invoice_variance_block_a, invoice_variance_accepted_a):
    assert invoice_variance_block_a.can_accept is True
    assert invoice_variance_accepted_a.can_accept is False
    invoice_variance_block_a.resolution = "disputed"
    assert invoice_variance_block_a.can_accept is True


def test_invoice_variance_can_accept_is_false_on_a_locked_invoice(invoice_paid_a):
    row = _invoice_variance_row(invoice_paid_a)
    assert row.invoice.is_locked is True
    assert row.can_accept is False


def test_invoice_variance_explain_names_the_band(invoice_variance_block_a):
    text = invoice_variance_block_a.explain()
    assert "Unit Price" in text
    assert "Purchase Order" in text
    assert "25.0000" in text and "30.0000" in text
    assert "20.0000%" in text
    assert "2.0000%" in text


def test_invoice_variance_explain_says_no_band_when_none_applied(invoice_draft_a):
    row = _invoice_variance_row(invoice_draft_a, tolerance_pct_applied=None,
                                tolerance_abs_applied=None)
    assert "no band" in row.explain()


def test_invoice_variance_explain_says_no_percentage_without_one(invoice_draft_a):
    row = _invoice_variance_row(invoice_draft_a, expected_value=Decimal("0.0000"),
                                actual_value=Decimal("5.0000"))
    assert "no percentage" in row.explain()


def test_invoice_variance_accept_moves_the_resolution_once(invoice_variance_block_a,
                                                           admin_user):
    assert invoice_variance_block_a.accept(admin_user) is True
    invoice_variance_block_a.refresh_from_db()
    assert invoice_variance_block_a.resolution == "accepted"
    assert invoice_variance_block_a.outcome == "block"   # the machine's verdict is not rewritten
    assert invoice_variance_block_a.accept(admin_user) is False


def test_invoice_variance_accept_refuses_a_settled_row(invoice_variance_accepted_a, admin_user):
    assert invoice_variance_accepted_a.accept(admin_user) is False
    invoice_variance_accepted_a.refresh_from_db()
    assert invoice_variance_accepted_a.resolution == "accepted"


def test_invoice_variance_accept_allows_a_disputed_row(invoice_variance_block_a, admin_user):
    invoice_variance_block_a.resolution = "disputed"
    invoice_variance_block_a.save(update_fields=["resolution"])
    assert invoice_variance_block_a.accept(admin_user) is True


def test_invoice_variance_clean_rejects_a_cross_tenant_invoice(tenant_a, invoice_b):
    row = InvoiceMatchVariance(tenant=tenant_a, invoice=invoice_b, variance_type="price",
                               basis="po", expected_value=Decimal("1"),
                               actual_value=Decimal("2"))
    with pytest.raises(ValidationError) as excinfo:
        row.clean()
    assert excinfo.value.message_dict["invoice"] == ["That invoice belongs to another workspace."]


def test_invoice_variance_clean_rejects_a_line_from_another_invoice(tenant_a, invoice_draft_a,
                                                                    invoice_line_a,
                                                                    invoice_captured_a):
    row = InvoiceMatchVariance(tenant=tenant_a, invoice=invoice_captured_a,
                               invoice_line=invoice_line_a, variance_type="quantity",
                               basis="receipt", expected_value=Decimal("1"),
                               actual_value=Decimal("2"))
    with pytest.raises(ValidationError) as excinfo:
        row.clean()
    assert "invoice_line" in excinfo.value.message_dict


def test_invoice_variance_clean_accepts_a_line_of_its_own_invoice(tenant_a, invoice_draft_a,
                                                                  invoice_line_a):
    row = InvoiceMatchVariance(tenant=tenant_a, invoice=invoice_draft_a,
                               invoice_line=invoice_line_a, variance_type="quantity",
                               basis="receipt", expected_value=Decimal("10"),
                               actual_value=Decimal("10"))
    row.clean()


def test_invoice_variance_ordering_is_newest_first(invoice_draft_a):
    first = _invoice_variance_row(invoice_draft_a, message="older")
    second = _invoice_variance_row(invoice_draft_a, message="newer")
    rows = list(invoice_draft_a.variances.all())
    assert rows[0].pk == second.pk
    assert rows[-1].pk == first.pk


# =============================================================================================
# InvoiceDispute - the contested part of a claim [DSP-]
# =============================================================================================

def test_invoice_dispute_defaults_and_auto_number(invoice_draft_a):
    obj = _invoice_dispute_row(invoice_draft_a)
    assert obj.number == "DSP-00001"
    assert InvoiceDispute.NUMBER_PREFIX == "DSP"
    assert obj.status == "open"
    assert obj.resolution == ""
    assert obj.resolution_note == ""
    assert obj.resolved_at is None
    assert obj.credit_memo_invoice_id is None
    assert obj.assigned_to_id is None
    assert obj.raised_at is not None


def test_invoice_dispute_str(invoice_dispute_open_a):
    assert str(invoice_dispute_open_a) == (
        f"{invoice_dispute_open_a.number} {_INVOICE_DOT} Price Dispute")


def test_invoice_dispute_number_sequence_is_per_tenant(invoice_draft_a, invoice_b):
    first = _invoice_dispute_row(invoice_draft_a)
    second = _invoice_dispute_row(invoice_draft_a)
    theirs = _invoice_dispute_row(invoice_b, disputed_amount=Decimal("0.00"))
    assert [first.number, second.number] == ["DSP-00001", "DSP-00002"]
    assert theirs.number == "DSP-00001"


def test_invoice_dispute_number_unique_together_with_tenant(tenant_a, invoice_draft_a):
    first = _invoice_dispute_row(invoice_draft_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            InvoiceDispute.objects.create(
                tenant=tenant_a, invoice=invoice_draft_a, reason_code="tax",
                description="Second row, same number.", number=first.number)


def test_invoice_dispute_meta_contract():
    meta = InvoiceDispute._meta
    assert meta.ordering == ["-raised_at", "-id"]
    assert meta.unique_together == (("tenant", "number"),)
    assert meta.verbose_name == "invoice dispute"


def test_invoice_dispute_supplier_is_denormalised_from_the_invoice(invoice_draft_a,
                                                                   invoice_vendor_a):
    obj = _invoice_dispute_row(invoice_draft_a)
    assert obj.supplier_id == invoice_vendor_a.pk == invoice_draft_a.vendor_id


def test_invoice_dispute_due_date_defaults_to_the_sla_on_create_only(invoice_draft_a):
    assert InvoiceDispute.SLA_DAYS == 10
    obj = _invoice_dispute_row(invoice_draft_a)
    assert obj.due_date == _invoice_today() + datetime.timedelta(days=InvoiceDispute.SLA_DAYS)
    # Clearing a typed due date on EDIT is a deliberate act - the SLA is not silently re-armed.
    obj.due_date = None
    obj.save()
    obj.refresh_from_db()
    assert obj.due_date is None


def test_invoice_dispute_due_date_is_honoured_when_given(invoice_draft_a):
    chosen = _invoice_today() + datetime.timedelta(days=3)
    obj = _invoice_dispute_row(invoice_draft_a, due_date=chosen)
    assert obj.due_date == chosen


def test_invoice_dispute_open_fixture_matches_the_sla(invoice_dispute_open_a):
    assert invoice_dispute_open_a.due_date == _invoice_today() + datetime.timedelta(days=10)


@pytest.mark.parametrize("name", ["number", "status", "raised_by", "resolved_at"])
def test_invoice_dispute_system_fields_are_not_editable(name):
    assert InvoiceDispute._meta.get_field(name).editable is False


def test_invoice_dispute_status_choices_exact():
    assert [value for value, _label in _invoice_dispute_status_choices] == [
        "open", "awaiting_supplier", "awaiting_internal", "resolved", "escalated", "closed"]


def test_invoice_dispute_reason_choices_exact():
    assert [value for value, _label in _invoice_dispute_reason_choices] == [
        "price", "quantity", "goods_not_received", "damaged", "duplicate",
        "credit_not_processed", "tax", "freight", "admin", "other"]


def test_invoice_dispute_resolution_choices_exact():
    assert [value for value, _label in _invoice_dispute_resolution_choices] == [
        "credit_memo", "debit_memo", "reinvoice", "short_pay", "withdrawn"]


def test_invoice_dispute_open_statuses_are_the_live_work():
    assert InvoiceDispute.OPEN_STATUSES == (
        "open", "awaiting_supplier", "awaiting_internal", "escalated")
    known = {value for value, _label in _invoice_dispute_status_choices}
    assert set(InvoiceDispute.OPEN_STATUSES) <= known
    assert known - set(InvoiceDispute.OPEN_STATUSES) == {"resolved", "closed"}


def test_invoice_dispute_badge_maps_cover_every_choice():
    assert set(InvoiceDispute.STATUS_CSS) == {v for v, _l in _invoice_dispute_status_choices}
    assert set(InvoiceDispute.REASON_CSS) == {v for v, _l in _invoice_dispute_reason_choices}
    for mapping in (InvoiceDispute.STATUS_CSS, InvoiceDispute.REASON_CSS):
        assert set(mapping.values()) <= _INVOICE_BADGE_COLOURS


def test_invoice_dispute_badge_properties_fall_back_to_slate(invoice_dispute_open_a):
    assert invoice_dispute_open_a.status_css == "badge-amber"
    assert invoice_dispute_open_a.reason_css == "badge-amber"
    invoice_dispute_open_a.status = "nope"
    invoice_dispute_open_a.reason_code = "nope"
    assert invoice_dispute_open_a.status_css == "badge-slate"
    assert invoice_dispute_open_a.reason_css == "badge-slate"


def test_invoice_dispute_is_open_across_every_status(invoice_dispute_open_a):
    for status, _label in _invoice_dispute_status_choices:
        invoice_dispute_open_a.status = status
        assert invoice_dispute_open_a.is_open is (
            status in InvoiceDispute.OPEN_STATUSES), status


def test_invoice_dispute_days_open(invoice_draft_a):
    obj = _invoice_dispute_row(invoice_draft_a)
    assert obj.days_open == 0
    _invoice_backdate_raised(obj, 3)
    assert obj.days_open == 3


def test_invoice_dispute_days_open_is_zero_before_it_is_stamped(invoice_draft_a):
    unsaved = InvoiceDispute(tenant=invoice_draft_a.tenant, invoice=invoice_draft_a,
                             reason_code="price", description="Not yet raised.")
    assert unsaved.raised_at is None
    assert unsaved.days_open == 0


def test_invoice_dispute_is_overdue(invoice_dispute_overdue_a, invoice_dispute_open_a):
    assert invoice_dispute_overdue_a.is_overdue is True
    assert invoice_dispute_open_a.is_overdue is False


def test_invoice_dispute_a_settled_dispute_is_never_overdue(invoice_dispute_overdue_a,
                                                            admin_user):
    invoice_dispute_overdue_a.resolve(admin_user, "short_pay")
    invoice_dispute_overdue_a.refresh_from_db()
    assert invoice_dispute_overdue_a.is_overdue is False


def test_invoice_dispute_age_bucket_overdue_outranks_the_day_bands(invoice_dispute_overdue_a):
    assert invoice_dispute_overdue_a.days_open == 0
    assert invoice_dispute_overdue_a.age_bucket == "overdue"


def test_invoice_dispute_age_bucket_is_none_without_a_due_date(invoice_draft_a):
    obj = _invoice_dispute_row(invoice_draft_a)
    obj.due_date = None
    assert obj.age_bucket == "none"


@pytest.mark.parametrize("days,bucket", [(0, "0-7"), (7, "0-7"), (8, "8-14"), (14, "8-14"),
                                          (15, "15-30"), (30, "15-30"), (31, "31-60"),
                                          (60, "31-60"), (61, "60+")])
def test_invoice_dispute_age_bucket_day_bands(invoice_draft_a, days, bucket):
    obj = _invoice_dispute_row(
        invoice_draft_a, due_date=_invoice_today() + datetime.timedelta(days=365))
    _invoice_backdate_raised(obj, days)
    assert obj.is_overdue is False
    assert obj.age_bucket == bucket


def test_invoice_dispute_undisputed_balance(invoice_draft_a, invoice_line_a):
    invoice_draft_a.refresh_from_db()
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("60.00"))
    assert obj.undisputed_balance == Decimal("190.00")


def test_invoice_dispute_undisputed_balance_is_zero_without_an_invoice(invoice_draft_a):
    orphan = InvoiceDispute(tenant=invoice_draft_a.tenant, reason_code="price",
                            description="No invoice attached.")
    assert orphan.undisputed_balance == Decimal("0")


# -- the dispute verb ladder ---------------------------------------------------------------------

def test_invoice_dispute_await_supplier_and_await_internal(invoice_dispute_open_a, admin_user):
    assert invoice_dispute_open_a.await_supplier(admin_user) is True
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "awaiting_supplier"
    assert invoice_dispute_open_a.await_supplier(admin_user) is False
    assert invoice_dispute_open_a.await_internal(admin_user) is True
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "awaiting_internal"
    assert invoice_dispute_open_a.await_internal(admin_user) is False


def test_invoice_dispute_escalate(invoice_dispute_open_a, admin_user):
    assert invoice_dispute_open_a.escalate(admin_user) is True
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "escalated"
    assert invoice_dispute_open_a.escalate(admin_user) is False


def test_invoice_dispute_escalated_fixture_is_still_open(invoice_dispute_escalated_a,
                                                         admin_user):
    assert invoice_dispute_escalated_a.status == "escalated"
    assert invoice_dispute_escalated_a.is_open is True
    assert invoice_dispute_escalated_a.await_supplier(admin_user) is True


def test_invoice_dispute_resolve_records_the_answer(invoice_dispute_open_a, admin_user):
    assert invoice_dispute_open_a.resolve(admin_user, "credit_memo", "Memo promised.") is True
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "resolved"
    assert invoice_dispute_open_a.resolution == "credit_memo"
    assert invoice_dispute_open_a.resolution_note == "Memo promised."
    assert invoice_dispute_open_a.resolved_at is not None
    assert invoice_dispute_open_a.is_open is False


@pytest.mark.parametrize("junk", ["", "nope", "RESOLVED", None, "open"])
def test_invoice_dispute_resolve_rejects_an_unknown_resolution(invoice_dispute_open_a,
                                                               admin_user, junk):
    """L35 - a free-text outcome is not reportable, so it is refused rather than stored."""
    assert invoice_dispute_open_a.resolve(admin_user, junk) is False
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.status == "open"
    assert invoice_dispute_open_a.resolution == ""
    assert invoice_dispute_open_a.resolved_at is None


def test_invoice_dispute_resolve_refuses_a_settled_dispute(invoice_dispute_resolved_a,
                                                           admin_user):
    assert invoice_dispute_resolved_a.status == "resolved"
    assert invoice_dispute_resolved_a.resolve(admin_user, "debit_memo") is False
    invoice_dispute_resolved_a.refresh_from_db()
    assert invoice_dispute_resolved_a.resolution == "short_pay"


def test_invoice_dispute_close_only_from_resolved(invoice_dispute_open_a,
                                                  invoice_dispute_resolved_a, admin_user):
    assert invoice_dispute_open_a.close(admin_user) is False
    assert invoice_dispute_resolved_a.close(admin_user) is True
    invoice_dispute_resolved_a.refresh_from_db()
    assert invoice_dispute_resolved_a.status == "closed"
    assert invoice_dispute_resolved_a.close(admin_user) is False


def test_invoice_dispute_withdraw_from_an_open_state(invoice_dispute_escalated_a, admin_user):
    """A withdrawn dispute was ABANDONED, not answered - the report has to tell them apart."""
    assert invoice_dispute_escalated_a.withdraw(admin_user, "We were wrong.") is True
    invoice_dispute_escalated_a.refresh_from_db()
    assert invoice_dispute_escalated_a.status == "closed"
    assert invoice_dispute_escalated_a.resolution == "withdrawn"
    assert invoice_dispute_escalated_a.resolution_note == "We were wrong."
    assert invoice_dispute_escalated_a.resolved_at is not None
    assert invoice_dispute_escalated_a.withdraw(admin_user) is False


def test_invoice_dispute_withdraw_refuses_a_settled_dispute(invoice_dispute_resolved_a,
                                                            admin_user):
    assert invoice_dispute_resolved_a.withdraw(admin_user) is False
    invoice_dispute_resolved_a.refresh_from_db()
    assert invoice_dispute_resolved_a.resolution == "short_pay"


def test_invoice_dispute_link_credit_memo(invoice_dispute_open_a, invoice_credit_memo_a):
    assert invoice_dispute_open_a.link_credit_memo(invoice_credit_memo_a) is True
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.credit_memo_invoice_id == invoice_credit_memo_a.pk


def test_invoice_dispute_link_credit_memo_refuses_an_unsaved_row(invoice_dispute_open_a,
                                                                 tenant_a, invoice_vendor_a):
    unsaved = SupplierInvoice(tenant=tenant_a, vendor=invoice_vendor_a, invoice_number="CM-X",
                              invoice_date=_invoice_today(), invoice_type="credit_memo")
    assert invoice_dispute_open_a.link_credit_memo(None) is False
    assert invoice_dispute_open_a.link_credit_memo(unsaved) is False
    invoice_dispute_open_a.refresh_from_db()
    assert invoice_dispute_open_a.credit_memo_invoice_id is None


# -- InvoiceDispute.clean() ------------------------------------------------------------------------

def test_invoice_dispute_clean_accepts_a_well_formed_row(invoice_draft_a, invoice_line_a):
    invoice_draft_a.refresh_from_db()
    obj = _invoice_dispute_row(invoice_draft_a, invoice_line=invoice_line_a)
    obj.clean()


def test_invoice_dispute_clean_rejects_a_cross_tenant_invoice(tenant_a, invoice_vendor_a,
                                                              invoice_b):
    obj = InvoiceDispute(tenant=tenant_a, invoice=invoice_b, supplier=invoice_vendor_a,
                         reason_code="price", description="Crafted.",
                         disputed_amount=Decimal("0.00"))
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["invoice"] == ["That invoice belongs to another workspace."]


def test_invoice_dispute_clean_rejects_a_cross_tenant_supplier(tenant_a, invoice_draft_a,
                                                               invoice_vendor_b):
    obj = InvoiceDispute(tenant=tenant_a, invoice=invoice_draft_a, supplier=invoice_vendor_b,
                         reason_code="price", description="Crafted.",
                         disputed_amount=Decimal("0.00"))
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "supplier" in excinfo.value.message_dict


def test_invoice_dispute_clean_rejects_a_line_from_another_invoice(invoice_captured_a,
                                                                   invoice_line_a):
    obj = _invoice_dispute_row(invoice_captured_a, disputed_amount=Decimal("0.00"))
    obj.invoice_line = invoice_line_a
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["invoice_line"] == [
        "That line belongs to a different invoice."]


def test_invoice_dispute_clean_caps_the_amount_at_the_invoice_total(invoice_draft_a,
                                                                    invoice_line_a):
    invoice_draft_a.refresh_from_db()
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("50.00"))
    obj.disputed_amount = Decimal("300.00")
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["disputed_amount"] == [
        "The disputed amount cannot be more than the invoice total."]


def test_invoice_dispute_clean_uses_the_size_of_a_credit_memo(invoice_credit_memo_a):
    """``abs`` because a credit memo's total is negative by design."""
    obj = _invoice_dispute_row(invoice_credit_memo_a, disputed_amount=Decimal("50.00"))
    obj.clean()
    obj.disputed_amount = Decimal("50.01")
    with pytest.raises(ValidationError):
        obj.clean()


def test_invoice_dispute_clean_rejects_an_oversized_amount(invoice_draft_a):
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    obj.disputed_amount = Decimal("1000000000000")
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["disputed_amount"] == [
        "Enter a disputed amount below 1,000,000,000,000."]


@pytest.mark.parametrize("junk", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_invoice_dispute_clean_rejects_a_non_finite_amount(invoice_draft_a, junk):
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    obj.disputed_amount = junk
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert "disputed_amount" in excinfo.value.message_dict


@pytest.mark.parametrize("bad", [datetime.date(1899, 12, 31), datetime.date(1000, 1, 1)])
def test_invoice_dispute_clean_rejects_a_due_date_outside_the_span(invoice_draft_a, bad):
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    obj.due_date = bad
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["due_date"] == [
        "Enter a due date between 1900 and 9999."]


def test_invoice_dispute_clean_rejects_a_link_that_is_not_a_credit_memo(invoice_draft_a,
                                                                        invoice_captured_a):
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    obj.credit_memo_invoice = invoice_captured_a
    with pytest.raises(ValidationError) as excinfo:
        obj.clean()
    assert excinfo.value.message_dict["credit_memo_invoice"] == [
        "The credit memo link must point at a credit memo."]


def test_invoice_dispute_clean_accepts_a_credit_memo_link(invoice_draft_a,
                                                          invoice_credit_memo_a):
    obj = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    obj.credit_memo_invoice = invoice_credit_memo_a
    obj.clean()


def test_invoice_dispute_ordering_is_newest_first(invoice_draft_a):
    first = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    second = _invoice_dispute_row(invoice_draft_a, disputed_amount=Decimal("0.00"))
    rows = list(InvoiceDispute.objects.filter(tenant=invoice_draft_a.tenant_id))
    assert rows[0].pk == second.pk
    assert rows[-1].pk == first.pk
