"""SCM 4.18 Finance & Accounting Integration — MODEL invariants.

Four tables, and only two of them are ever typed into: ``DutyTariff`` [DTY-] (the customs master
``accounting.TaxCode`` structurally cannot be — no ``hs_code``, no origin pair, no customs member in
its ``TAX_TYPE_CHOICES``), ``LandedCostVoucher`` [LC-] (the envelope), ``LandedCostCharge`` (one cost
line, and a **tenant-less** child) and ``LandedCostAllocation`` (**every column derived**, written by
``LandedCostVoucher.allocate()`` and by nothing else).

What this lane pins, in the order the sub-module's own docstrings state it:

* **per-tenant auto-numbers** — ``DTY-#####`` and ``LC-#####`` mint in ``TenantNumbered.save()``, run
  in sequence inside a workspace and RESTART in the next one, because ``unique_together
  ("tenant", "number")`` is what makes two workspaces both legitimately hold an ``LC-00001``;
* **defaults, ``__str__`` and every closed vocabulary** — the five voucher statuses, the five
  allocation bases (there is deliberately no ``manual`` sixth) and the eleven charge types;
* **every figure that is DERIVED rather than stored** (L29) — the voucher's five money columns are
  ``editable=False`` with ``recalc_totals()`` as their ONE writer, summed in Python; ``allocated_total``
  is provably the aggregate over the allocation rows; ``DutyTariff.is_current`` is a property, never a
  column; ``LandedCostCharge.allocatable_amount``/``effective_basis``/``capitalises`` are properties;
  and quantity on-hand stays the ``StockMove`` aggregate that ``allocate()`` reads;
* **the effective-dated lookup** — ``DutyTariff.rate_for()``'s resolution order (active, window,
  named origin BEATS the blank any-origin row, newest first) and its never-raises contract;
* **the verb ladder** — ``allocate() → accrue() → draft_bill()`` plus ``cancel()``, each refusal
  sentence asserted where an absent prerequisite must be REJECTED rather than fall through (L35), and
  ``allocate()``'s idempotence, which is the one mistake here that is invisible on every page and
  permanently wrong in the ledger;
* **the accounting boundary** — ``draft_bill()`` stops at a DRAFT ``accounting.Bill``; SCM posts no
  ``JournalEntry``.

THE ONE STRUCTURAL FACT: the allocation base is the STOCK LEDGER, not the receipt's own lines
(``GoodsReceiptLine.po_line`` carries free text and no ``item`` FK — the documented L28 stand-in). So
every receipt a voucher can allocate over is built through ``_helpers.seed_stock`` (i.e. the module's
own ``_post_stock_move`` service), never ``StockMove.objects.create``.

Fixtures come from ``apps/scm/tests/conftest.py`` (the ``finance_`` block) and the ROOT
``conftest.py``. Nothing here writes to either file. Every reference date is derived from
``timezone.localdate()`` / ``timezone.now()`` — the same basis ``is_current``, ``rate_for`` and
``draft_bill``'s ``bill_date`` read — never ``datetime.date.today()`` (L16).

NAMING: every test function is ``test_finance_*`` and every module-level helper ``_finance_*``.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.scm.models import (
    DutyTariff,
    LandedCostAllocation,
    LandedCostCharge,
    LandedCostVoucher,
    StockMove,
)
from apps.scm.models.FinanceIntegration.LandedCostVouchers import (
    MAX_BASIS_VALUE,
    MAX_BILL_TAX_RATE_PCT,
    MAX_UPLIFT,
    MAX_VARIANCE_PCT,
    _BASIS_FALLBACKS,
)

pytestmark = pytest.mark.django_db


# =================================================================================================
# Helpers — every module-level name here is ``_finance_``-prefixed so a neighbouring sub-module's
# file cannot shadow it (the suite-hygiene guard checks the same thing per file).
# =================================================================================================

def _finance_values(choices):
    """Just the stored values of a CHOICES list — labels are prose and may be reworded."""
    return [value for value, _label in choices]


def _finance_field(model, name):
    return model._meta.get_field(name)


def _finance_field_names(model):
    return {field.name for field in model._meta.get_fields()}


def _finance_today():
    """The SAME basis the code reads (L16). Never ``datetime.date.today()``."""
    return timezone.localdate()


def _finance_days(count):
    return datetime.timedelta(days=count)


def _finance_tariff(tenant, **kwargs):
    """A DutyTariff with everything but ``tenant`` defaulted — ``effective_from`` is never nullable."""
    kwargs.setdefault("hs_code", "9999.99")
    kwargs.setdefault("effective_from", _finance_today())
    return DutyTariff.objects.create(tenant=tenant, **kwargs)


def _finance_receipt(tenant, purchase_order, location, moves, status="received"):
    """A GRN plus the inbound stock moves stamped with ITS number — the real allocation base.

    ``moves`` is a list of ``(item, quantity, unit_cost)``. Posted through ``seed_stock`` so
    ``Item.average_cost`` rolls forward exactly as production does; a hand-written ``StockMove`` row
    would leave the cached average disagreeing with the ledger and every costing assertion below
    measuring the wrong thing.
    """
    from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote
    from apps.scm.tests._helpers import seed_stock

    grn = GoodsReceiptNote.objects.create(
        tenant=tenant, purchase_order=purchase_order, location=location,
        receipt_date=_finance_today(), status=status)
    po_line = purchase_order.lines.first()
    GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=po_line,
                                    quantity_received=Decimal("1"))
    for item, quantity, unit_cost in moves:
        seed_stock(tenant, item, location, quantity, unit_cost, reference=grn.number)
    return grn


def _finance_voucher(tenant, goods_receipt, party, **kwargs):
    kwargs.setdefault("cost_date", _finance_today())
    return LandedCostVoucher.objects.create(
        tenant=tenant, goods_receipt=goods_receipt, party=party, **kwargs)


def _finance_charge(voucher, **kwargs):
    """One cost line, then ``recalc_totals()`` — the ONE writer of the voucher's money columns."""
    kwargs.setdefault("charge_type", "freight")
    kwargs.setdefault("estimated_amount", Decimal("100.00"))
    charge = LandedCostCharge.objects.create(voucher=voucher, **kwargs)
    voucher.recalc_totals()
    return charge


def _finance_amounts(voucher):
    """The allocated amounts in row order — the split ``allocate()`` actually wrote."""
    return [row.allocated_amount for row in voucher.allocations.order_by("id")]


# =================================================================================================
# Auto-numbers — minted in TenantNumbered.save(), per tenant, never editable
# =================================================================================================

def test_finance_duty_tariff_mints_the_dty_prefix(tenant_a):
    tariff = _finance_tariff(tenant_a, hs_code="8471.30")
    assert tariff.number == "DTY-00001"


def test_finance_duty_tariff_numbers_run_in_sequence(tenant_a):
    first = _finance_tariff(tenant_a, hs_code="1111.11")
    second = _finance_tariff(tenant_a, hs_code="2222.22")
    third = _finance_tariff(tenant_a, hs_code="3333.33")
    assert [first.number, second.number, third.number] == ["DTY-00001", "DTY-00002", "DTY-00003"]


def test_finance_duty_tariff_numbers_restart_in_the_next_workspace(tenant_a, tenant_b):
    """``unique_together ("tenant", "number")`` — two workspaces both hold a DTY-00001."""
    mine = _finance_tariff(tenant_a, hs_code="1111.11")
    theirs = _finance_tariff(tenant_b, hs_code="1111.11")
    assert mine.number == theirs.number == "DTY-00001"
    assert mine.tenant_id != theirs.tenant_id


def test_finance_voucher_mints_the_lc_prefix(tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    assert voucher.number == "LC-00001"


def test_finance_voucher_numbers_run_in_sequence_and_restart_per_tenant(
        tenant_a, tenant_b, finance_receipt_a, finance_receipt_b, supplier_a, supplier_b):
    first = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    second = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    theirs = _finance_voucher(tenant_b, finance_receipt_b, supplier_b)
    assert [first.number, second.number] == ["LC-00001", "LC-00002"]
    assert theirs.number == "LC-00001"


def test_finance_numbers_are_never_form_fields(tenant_a):
    """``editable=False`` — a typed number is a number two rows can share (L22)."""
    assert _finance_field(DutyTariff, "number").editable is False
    assert _finance_field(LandedCostVoucher, "number").editable is False


def test_finance_duplicate_number_inside_one_workspace_is_rejected(tenant_a):
    _finance_tariff(tenant_a, hs_code="1111.11")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DutyTariff.objects.create(tenant=tenant_a, hs_code="2222.22", number="DTY-00001",
                                      effective_from=_finance_today())


def test_finance_children_carry_no_number_of_their_own(tenant_a):
    """The charge and the allocation are reached through their parent, not by a document number."""
    assert "number" not in _finance_field_names(LandedCostCharge)
    assert "number" not in _finance_field_names(LandedCostAllocation)


# =================================================================================================
# DutyTariff — defaults, __str__, the natural key, clean()
# =================================================================================================

def test_finance_duty_tariff_defaults(tenant_a):
    tariff = _finance_tariff(tenant_a, hs_code="8471.30")
    assert tariff.country_of_origin == ""      # blank MEANS "any origin", not "unknown"
    assert tariff.description == ""
    assert tariff.duty_rate_pct == Decimal("0")
    assert tariff.effective_to is None          # open-ended = +infinity
    assert tariff.is_active is True
    assert tariff.tax_code_id is None


def test_finance_duty_tariff_str_names_the_origin(finance_duty_tariff_a):
    assert str(finance_duty_tariff_a) == "8471.30 · Germany · 2.500%"


def test_finance_duty_tariff_str_says_any_for_the_catch_all_row(finance_duty_tariff_any_a):
    assert str(finance_duty_tariff_any_a) == "8471.30 · Any · 5.000%"


def test_finance_duty_tariff_has_no_status_column(tenant_a):
    """The list page's ?status vocabulary is a VIEW literal over the ``is_active`` BOOLEAN."""
    names = _finance_field_names(DutyTariff)
    assert "status" not in names
    assert _finance_field(DutyTariff, "is_active").get_internal_type() == "BooleanField"


def test_finance_duty_tariff_ordering_is_classification_then_newest_first():
    assert DutyTariff._meta.ordering == ["hs_code", "-effective_from"]


def test_finance_duty_tariff_effective_from_is_never_nullable():
    """A NULL member silently disables the unique key in MySQL, and cannot be windowed on."""
    field = _finance_field(DutyTariff, "effective_from")
    assert field.null is False and field.blank is False


def test_finance_duty_tariff_unique_together_is_scoped_by_tenant():
    assert DutyTariff._meta.unique_together == (
        ("tenant", "number"),
        ("tenant", "hs_code", "country_of_origin", "effective_from"),
    )


def test_finance_duty_tariff_duplicate_natural_key_is_rejected(tenant_a, finance_duty_tariff_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DutyTariff.objects.create(
                tenant=tenant_a, hs_code="8471.30", country_of_origin="Germany",
                effective_from=finance_duty_tariff_a.effective_from)


def test_finance_duty_tariff_same_natural_key_is_free_in_another_workspace(
        tenant_b, finance_duty_tariff_a):
    twin = DutyTariff.objects.create(
        tenant=tenant_b, hs_code="8471.30", country_of_origin="Germany",
        effective_from=finance_duty_tariff_a.effective_from)
    assert twin.pk != finance_duty_tariff_a.pk


def test_finance_duty_tariff_clean_normalises_both_free_text_keys(tenant_a):
    """Upper-case + strip in ``clean()``, which runs BEFORE ``validate_unique()``."""
    tariff = DutyTariff(tenant=tenant_a, hs_code="  8471.30ab  ",
                        country_of_origin="  Germany  ", effective_from=_finance_today())
    tariff.full_clean()
    assert tariff.hs_code == "8471.30AB"
    assert tariff.country_of_origin == "Germany"


def test_finance_duty_tariff_normalisation_collides_on_the_unique_key(
        tenant_a, finance_duty_tariff_a):
    """``  8471.30  `` must not quietly become a SECOND row ``rate_for`` then has to choose between."""
    twin = DutyTariff(tenant=tenant_a, hs_code="  8471.30  ", country_of_origin=" Germany ",
                      effective_from=finance_duty_tariff_a.effective_from)
    with pytest.raises(ValidationError):
        twin.full_clean()


def test_finance_duty_tariff_inverted_window_is_rejected(tenant_a):
    today = _finance_today()
    tariff = DutyTariff(tenant=tenant_a, hs_code="8471.30", effective_from=today,
                        effective_to=today - _finance_days(1))
    with pytest.raises(ValidationError) as exc:
        tariff.clean()
    assert "effective_to" in exc.value.message_dict
    assert "would stop applying" in exc.value.message_dict["effective_to"][0]


def test_finance_duty_tariff_single_day_window_is_allowed(tenant_a):
    today = _finance_today()
    tariff = DutyTariff(tenant=tenant_a, hs_code="8471.30", effective_from=today,
                        effective_to=today)
    tariff.clean()  # must not raise — a rate may apply for exactly one day


def test_finance_duty_tariff_rejects_a_foreign_tax_code(tenant_a, finance_tax_code_b):
    tariff = DutyTariff(tenant=tenant_a, hs_code="8471.30", effective_from=_finance_today(),
                        tax_code=finance_tax_code_b)
    with pytest.raises(ValidationError) as exc:
        tariff.clean()
    assert exc.value.message_dict["tax_code"] == ["That record belongs to another workspace."]


def test_finance_duty_tariff_accepts_its_own_tax_code(tenant_a, finance_tax_code_a):
    tariff = DutyTariff(tenant=tenant_a, hs_code="8471.30", effective_from=_finance_today(),
                        tax_code=finance_tax_code_a)
    tariff.clean()  # must not raise


def test_finance_duty_tariff_rate_is_bounded_between_zero_and_one_hundred(tenant_a):
    for bad in (Decimal("-0.001"), Decimal("100.001")):
        tariff = DutyTariff(tenant=tenant_a, hs_code="8471.30", duty_rate_pct=bad,
                            effective_from=_finance_today())
        with pytest.raises(ValidationError) as exc:
            tariff.full_clean()
        assert "duty_rate_pct" in exc.value.message_dict


def test_finance_duty_tariff_rate_keeps_three_decimal_places(tenant_a):
    """Duty schedules are routinely quoted to fractions of a percent."""
    field = _finance_field(DutyTariff, "duty_rate_pct")
    assert (field.max_digits, field.decimal_places) == (6, 3)
    tariff = _finance_tariff(tenant_a, hs_code="8471.30", duty_rate_pct=Decimal("2.125"))
    tariff.refresh_from_db()
    assert tariff.duty_rate_pct == Decimal("2.125")


# =================================================================================================
# DutyTariff.is_current — a PROPERTY, never a stored flag
# =================================================================================================

def test_finance_is_current_is_a_property_not_a_column():
    assert "is_current" not in _finance_field_names(DutyTariff)
    assert isinstance(DutyTariff.__dict__["is_current"], property)


def test_finance_is_current_true_for_an_in_force_open_ended_rate(finance_duty_tariff_a):
    assert finance_duty_tariff_a.effective_to is None
    assert finance_duty_tariff_a.is_current is True


def test_finance_is_current_false_before_the_start_date(tenant_a):
    tariff = _finance_tariff(tenant_a, effective_from=_finance_today() + _finance_days(1))
    assert tariff.is_current is False


def test_finance_is_current_false_once_the_window_has_closed(tenant_a):
    tariff = _finance_tariff(tenant_a, effective_from=_finance_today() - _finance_days(10),
                             effective_to=_finance_today() - _finance_days(1))
    assert tariff.is_current is False


def test_finance_is_current_true_on_both_boundary_days(tenant_a):
    today = _finance_today()
    tariff = _finance_tariff(tenant_a, effective_from=today, effective_to=today)
    assert tariff.is_current is True


def test_finance_is_current_false_for_a_retired_rate(tenant_a):
    """An inactive row is not in force even when today sits inside its dates."""
    tariff = _finance_tariff(tenant_a, effective_from=_finance_today() - _finance_days(1),
                             is_active=False)
    assert tariff.is_current is False


# =================================================================================================
# DutyTariff.rate_for — the effective-dated lookup, and its never-raises contract
# =================================================================================================

def test_finance_rate_for_prefers_a_named_origin_over_the_any_row(
        tenant_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
    match = DutyTariff.rate_for(tenant_a, "8471.30", "Germany", _finance_today())
    assert match == finance_duty_tariff_a
    assert match.duty_rate_pct == Decimal("2.500")


def test_finance_rate_for_falls_back_to_the_any_origin_row(
        tenant_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
    match = DutyTariff.rate_for(tenant_a, "8471.30", "Vietnam", _finance_today())
    assert match == finance_duty_tariff_any_a


def test_finance_rate_for_matches_the_origin_case_insensitively(
        tenant_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
    assert DutyTariff.rate_for(tenant_a, "8471.30", "gErMaNy", _finance_today()) == \
        finance_duty_tariff_a


def test_finance_rate_for_prefers_the_newest_effective_from(tenant_a, finance_duty_tariff_a):
    newer = _finance_tariff(tenant_a, hs_code="8471.30", country_of_origin="Germany",
                            duty_rate_pct=Decimal("3.000"), effective_from=_finance_today())
    assert DutyTariff.rate_for(tenant_a, "8471.30", "Germany", _finance_today()) == newer


def test_finance_rate_for_skips_a_retired_rate(tenant_a, finance_duty_tariff_a):
    finance_duty_tariff_a.is_active = False
    finance_duty_tariff_a.save(update_fields=["is_active"])
    assert DutyTariff.rate_for(tenant_a, "8471.30", "Germany", _finance_today()) is None


def test_finance_rate_for_skips_a_closed_window(tenant_a):
    _finance_tariff(tenant_a, hs_code="8471.30", country_of_origin="Germany",
                    effective_from=_finance_today() - _finance_days(30),
                    effective_to=_finance_today() - _finance_days(1))
    assert DutyTariff.rate_for(tenant_a, "8471.30", "Germany", _finance_today()) is None


def test_finance_rate_for_skips_a_rate_that_has_not_started(tenant_a):
    _finance_tariff(tenant_a, hs_code="8471.30", country_of_origin="Germany",
                    effective_from=_finance_today() + _finance_days(1))
    assert DutyTariff.rate_for(tenant_a, "8471.30", "Germany", _finance_today()) is None


def test_finance_rate_for_keeps_open_ended_rates_in_range(tenant_a, finance_duty_tariff_a):
    """The explicit ``effective_to__isnull`` leg — a NULL comparison in SQL is neither true nor
    false, so without it every open-ended row would silently drop out of the result."""
    far_future = _finance_today() + _finance_days(3650)
    assert DutyTariff.rate_for(tenant_a, "8471.30", "Germany", far_future) == finance_duty_tariff_a


def test_finance_rate_for_normalises_the_hs_code(tenant_a, finance_duty_tariff_a):
    assert DutyTariff.rate_for(tenant_a, "  8471.30  ", "Germany", _finance_today()) == \
        finance_duty_tariff_a


def test_finance_rate_for_matches_an_upper_cased_code(tenant_a):
    tariff = _finance_tariff(tenant_a, hs_code="AB12.34", country_of_origin="")
    assert DutyTariff.rate_for(tenant_a, "ab12.34", "", _finance_today()) == tariff


def test_finance_rate_for_returns_none_and_never_raises(tenant_a, finance_duty_tariff_a):
    """The caller is DEFAULTING a form field: a missing tariff means "type the rate yourself"."""
    today = _finance_today()
    assert DutyTariff.rate_for(None, "8471.30", "Germany", today) is None
    assert DutyTariff.rate_for(tenant_a, "", "Germany", today) is None
    assert DutyTariff.rate_for(tenant_a, None, "Germany", today) is None
    assert DutyTariff.rate_for(tenant_a, "   ", "Germany", today) is None
    assert DutyTariff.rate_for(tenant_a, "8471.30", "Germany", None) is None
    assert DutyTariff.rate_for(tenant_a, "NOPE", "Germany", today) is None


def test_finance_rate_for_never_crosses_the_workspace_boundary(
        tenant_a, tenant_b, finance_duty_tariff_b):
    assert DutyTariff.rate_for(tenant_a, "8528.52", "Canada", _finance_today()) is None
    assert DutyTariff.rate_for(tenant_b, "8528.52", "Canada", _finance_today()) == \
        finance_duty_tariff_b


# =================================================================================================
# LandedCostVoucher — defaults, vocabularies, and what is NOT a stored/typed column
# =================================================================================================

def test_finance_voucher_defaults(tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    assert voucher.status == "draft"
    assert voucher.allocation_basis == "value"
    assert voucher.notes == ""
    assert voucher.shipment_id is None and voucher.trade_document_id is None
    assert voucher.currency_id is None and voucher.bill_id is None
    assert voucher.estimated_total == Decimal("0")
    assert voucher.actual_total == Decimal("0")
    assert voucher.variance_amount == Decimal("0")
    assert voucher.variance_pct is None
    assert voucher.allocated_total == Decimal("0")
    assert voucher.accrued_at is None


def test_finance_voucher_str_is_the_number_and_the_payee(finance_voucher_a, supplier_a):
    assert str(finance_voucher_a) == f"{finance_voucher_a.number} · {supplier_a.name}"


def test_finance_voucher_str_survives_an_unsaved_instance():
    assert str(LandedCostVoucher()) == "LC · ?"


def test_finance_voucher_status_choices_are_the_five_rungs():
    assert _finance_values(LandedCostVoucher.STATUS_CHOICES) == [
        "draft", "allocated", "accrued", "reconciled", "cancelled"]
    assert LandedCostVoucher.EDITABLE_STATUSES == ("draft",)


def test_finance_allocation_basis_choices_have_no_manual_sixth():
    assert _finance_values(LandedCostVoucher.ALLOCATION_BASIS_CHOICES) == [
        "value", "quantity", "weight", "volume", "equal"]


def test_finance_charge_type_choices_are_the_eleven_landed_cost_kinds():
    assert _finance_values(LandedCostCharge.CHARGE_TYPE_CHOICES) == [
        "freight", "duty", "brokerage", "insurance", "handling", "drayage", "port_fees",
        "fuel_surcharge", "inspection", "storage", "other"]


def test_finance_voucher_derived_columns_are_not_editable():
    """Ruling 3 + 4: the money is derived and the status moves only along the verb ladder (L22)."""
    for name in ("status", "bill", "estimated_total", "actual_total", "variance_amount",
                 "variance_pct", "allocated_total", "accrued_at", "number"):
        assert _finance_field(LandedCostVoucher, name).editable is False, name


def test_finance_voucher_typed_columns_stay_editable():
    for name in ("goods_receipt", "party", "shipment", "trade_document", "currency", "cost_date",
                 "allocation_basis", "notes"):
        assert _finance_field(LandedCostVoucher, name).editable is True, name


def test_finance_voucher_unique_together_is_scoped_by_tenant():
    assert LandedCostVoucher._meta.unique_together == (("tenant", "number"),)


def test_finance_voucher_ordering_is_newest_cost_date_first():
    assert LandedCostVoucher._meta.ordering == ["-cost_date", "-id"]


def test_finance_voucher_is_editable_while_draft_and_unbilled(finance_voucher_a):
    assert finance_voucher_a.is_editable is True


def test_finance_voucher_is_not_editable_once_allocated(finance_allocated_voucher_a):
    assert finance_allocated_voucher_a.status == "allocated"
    assert finance_allocated_voucher_a.is_editable is False


def test_finance_voucher_is_not_editable_once_billed(finance_recoverable_voucher_a):
    finance_recoverable_voucher_a.draft_bill()
    assert finance_recoverable_voucher_a.bill_id is not None
    assert finance_recoverable_voucher_a.is_editable is False


# =================================================================================================
# LandedCostVoucher.clean() — the database-boundary guards
# =================================================================================================

def test_finance_voucher_clean_requires_a_cost_date(tenant_a, finance_receipt_a, supplier_a):
    voucher = LandedCostVoucher(tenant=tenant_a, goods_receipt=finance_receipt_a, party=supplier_a)
    with pytest.raises(ValidationError) as exc:
        voucher.clean()
    assert exc.value.message_dict["cost_date"] == [
        "A landed cost voucher needs the date its charges were incurred."]


def test_finance_voucher_clean_rejects_a_cancelled_receipt(tenant_a, finance_receipt_a, supplier_a):
    finance_receipt_a.status = "cancelled"
    finance_receipt_a.save(update_fields=["status"])
    voucher = LandedCostVoucher(tenant=tenant_a, goods_receipt=finance_receipt_a, party=supplier_a,
                                cost_date=_finance_today())
    with pytest.raises(ValidationError) as exc:
        voucher.clean()
    assert "has been cancelled" in exc.value.message_dict["goods_receipt"][0]


def test_finance_voucher_clean_rejects_a_foreign_goods_receipt(
        tenant_a, finance_receipt_b, supplier_a):
    voucher = LandedCostVoucher(tenant=tenant_a, goods_receipt=finance_receipt_b, party=supplier_a,
                                cost_date=_finance_today())
    with pytest.raises(ValidationError) as exc:
        voucher.clean()
    assert exc.value.message_dict["goods_receipt"] == ["That record belongs to another workspace."]


def test_finance_voucher_clean_rejects_a_foreign_shipment(
        tenant_a, finance_receipt_a, supplier_a, shipment_b):
    voucher = LandedCostVoucher(tenant=tenant_a, goods_receipt=finance_receipt_a, party=supplier_a,
                                shipment=shipment_b, cost_date=_finance_today())
    with pytest.raises(ValidationError) as exc:
        voucher.clean()
    assert exc.value.message_dict["shipment"] == ["That record belongs to another workspace."]


def test_finance_voucher_clean_skips_the_cross_tenant_loop_without_a_tenant(
        finance_receipt_b, supplier_a):
    """``crud_create`` stamps ``tenant`` AFTER ``is_valid()`` — the skip is load-bearing, not
    defensive: without it every legitimately chosen receipt would compare unequal to None."""
    voucher = LandedCostVoucher(goods_receipt=finance_receipt_b, party=supplier_a,
                                cost_date=_finance_today())
    voucher.clean()  # must not raise


def test_finance_voucher_tenant_scoped_fks_omit_party():
    """``party`` is guarded at the FORM boundary instead — that is where it renders as a field error."""
    assert LandedCostVoucher.TENANT_SCOPED_FKS == ("goods_receipt", "shipment", "trade_document")


# =================================================================================================
# LandedCostCharge — the tenant-less child and its four derived reads
# =================================================================================================

def test_finance_charge_defaults(finance_voucher_a):
    charge = LandedCostCharge.objects.create(voucher=finance_voucher_a)
    assert charge.charge_type == "freight"
    assert charge.description == ""
    assert charge.party_id is None and charge.freight_invoice_id is None
    assert charge.estimated_amount == Decimal("0")
    assert charge.actual_amount == Decimal("0")
    assert charge.allocation_basis == ""      # blank INHERITS the voucher's
    assert charge.gl_account_id is None and charge.tax_code_id is None
    assert charge.is_recoverable is False
    assert charge.capitalise_to_inventory is True
    assert charge.hs_code == "" and charge.country_of_origin == ""
    assert charge.duty_rate_pct == Decimal("0")


def test_finance_charge_str_is_the_type_and_the_allocatable_amount(finance_charge_a):
    assert str(finance_charge_a) == "Freight · 100.00"


def test_finance_charge_carries_no_tenant_of_its_own(finance_charge_a, tenant_a):
    """The ``BillLine`` / ``GoodsReceiptLine`` / ``ClientBillingRunLine`` convention — a second
    ``tenant`` FK would be a second answer to "whose row is this" and the two would disagree."""
    names = _finance_field_names(LandedCostCharge)
    assert "tenant" not in names
    assert "created_at" not in names and "updated_at" not in names
    assert finance_charge_a.voucher.tenant_id == tenant_a.pk


def test_finance_charge_variance_amount_is_a_property(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, estimated_amount=Decimal("100.00"),
                              actual_amount=Decimal("120.00"))
    assert charge.variance_amount == Decimal("20.00")
    assert "variance_amount" not in _finance_field_names(LandedCostCharge)


def test_finance_charge_allocatable_amount_prefers_the_actual(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, estimated_amount=Decimal("100.00"),
                              actual_amount=Decimal("120.00"))
    assert charge.allocatable_amount == Decimal("120.00")


def test_finance_charge_allocatable_amount_falls_back_to_the_estimate(finance_charge_a):
    assert finance_charge_a.actual_amount == Decimal("0")
    assert finance_charge_a.allocatable_amount == Decimal("100.00")


def test_finance_charge_allocatable_amount_is_neither_a_sum_nor_a_maximum(finance_voucher_a):
    """A LOWER actual replaces the estimate — it is not ignored and the two are never added."""
    charge = LandedCostCharge(voucher=finance_voucher_a, estimated_amount=Decimal("100.00"),
                              actual_amount=Decimal("40.00"))
    assert charge.allocatable_amount == Decimal("40.00")


def test_finance_charge_effective_basis_inherits_the_voucher(finance_voucher_a):
    finance_voucher_a.allocation_basis = "quantity"
    charge = LandedCostCharge(voucher=finance_voucher_a, allocation_basis="")
    assert charge.effective_basis == "quantity"


def test_finance_charge_effective_basis_overrides_the_voucher(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, allocation_basis="equal")
    assert finance_voucher_a.allocation_basis == "value"
    assert charge.effective_basis == "equal"


def test_finance_charge_effective_basis_is_value_when_unparented():
    assert LandedCostCharge().effective_basis == "value"


def test_finance_charge_capitalises_by_default(finance_charge_a):
    assert finance_charge_a.capitalises is True


def test_finance_charge_recoverable_tax_never_capitalises(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, is_recoverable=True,
                              capitalise_to_inventory=True)
    assert charge.capitalises is False


def test_finance_charge_expensed_charge_never_capitalises(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, capitalise_to_inventory=False)
    assert charge.capitalises is False


def test_finance_charge_clean_rejects_a_duty_rate_on_a_non_duty_charge(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, charge_type="freight",
                              duty_rate_pct=Decimal("2.500"))
    with pytest.raises(ValidationError) as exc:
        charge.clean()
    assert "duty_rate_pct" in exc.value.message_dict
    assert "belongs on a Customs Duty charge" in exc.value.message_dict["duty_rate_pct"][0]


def test_finance_charge_clean_allows_a_duty_rate_on_a_duty_charge(finance_voucher_a):
    charge = LandedCostCharge(voucher=finance_voucher_a, charge_type="duty",
                              duty_rate_pct=Decimal("2.500"))
    charge.clean()  # must not raise


def test_finance_charge_customs_fields_are_snapshots_not_a_tariff_fk(finance_voucher_a):
    """A tariff re-rated next quarter must not restate what a shipment cleared customs at."""
    names = _finance_field_names(LandedCostCharge)
    assert {"hs_code", "country_of_origin", "duty_rate_pct"} <= names
    assert "duty_tariff" not in names and "tariff" not in names


def test_finance_charge_cascades_with_its_voucher(tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher)
    voucher.delete()
    assert LandedCostCharge.objects.count() == 0


# =================================================================================================
# recalc_totals() — the ONE writer of the five money columns (ruling 3)
# =================================================================================================

def test_finance_recalc_totals_derives_the_five_money_columns(
        tenant_a, finance_receipt_a, supplier_a, gl_expense):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("100.00"), actual_amount=Decimal("120.00"),
                    gl_account=gl_expense)
    _finance_charge(voucher, charge_type="duty", estimated_amount=Decimal("50.00"),
                    actual_amount=Decimal("30.00"))
    voucher.refresh_from_db()
    assert voucher.estimated_total == Decimal("150.00")
    assert voucher.actual_total == Decimal("150.00")
    assert voucher.variance_amount == Decimal("0.00")
    assert voucher.variance_pct == Decimal("0.00")
    assert voucher.allocated_total == Decimal("0.00")


def test_finance_recalc_totals_matches_the_charge_aggregate(
        tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("12.34"), actual_amount=Decimal("99.99"))
    _finance_charge(voucher, estimated_amount=Decimal("0.66"), actual_amount=Decimal("0.01"))
    voucher.refresh_from_db()
    totals = voucher.charges.aggregate(e=Sum("estimated_amount"), a=Sum("actual_amount"))
    assert voucher.estimated_total == totals["e"]
    assert voucher.actual_total == totals["a"]
    assert voucher.variance_amount == totals["a"] - totals["e"]


def test_finance_variance_pct_is_none_when_nothing_was_estimated(finance_voucher_multi_a):
    """None, never 0: "nothing was estimated" and "the estimate was exact" render differently."""
    assert finance_voucher_multi_a.estimated_total == Decimal("0.00")
    assert finance_voucher_multi_a.actual_total == Decimal("100.00")
    assert finance_voucher_multi_a.variance_pct is None


def test_finance_variance_pct_is_zero_when_the_estimate_was_exact(
        tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("100.00"), actual_amount=Decimal("100.00"))
    voucher.refresh_from_db()
    assert voucher.variance_pct == Decimal("0.00")


def test_finance_variance_pct_is_clamped_to_the_column_width(
        tenant_a, finance_receipt_a, supplier_a):
    """A 0.01 estimate actualised at 999,999.99 is a 9,999,999,800% variance — ``DecimalField(8, 2)``
    cannot hold it, and an unclamped ratio raises ``DataError`` on a page nobody could then load."""
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("0.01"), actual_amount=Decimal("999999.99"))
    voucher.refresh_from_db()
    assert voucher.variance_pct == MAX_VARIANCE_PCT == Decimal("999999.99")
    # The honest figure survives beside the clamped ratio.
    assert voucher.variance_amount == Decimal("999999.98")


def test_finance_variance_pct_is_clamped_at_the_negative_end_too(
        tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("999999.99"), actual_amount=Decimal("0"))
    voucher.refresh_from_db()
    assert voucher.variance_pct == Decimal("-100.00")


def test_finance_allocated_total_is_the_allocation_aggregate(finance_allocated_voucher_a):
    """A stored total that disagrees with its rows is the defect this asserts against."""
    aggregate = (LandedCostAllocation.objects
                 .filter(voucher=finance_allocated_voucher_a)
                 .aggregate(s=Sum("allocated_amount"))["s"])
    assert finance_allocated_voucher_a.allocated_total == aggregate == Decimal("100.00")


def test_finance_recalc_totals_can_be_computed_without_saving(finance_charge_a, finance_voucher_a):
    finance_charge_a.actual_amount = Decimal("250.00")
    finance_charge_a.save(update_fields=["actual_amount"])
    finance_voucher_a.recalc_totals(save=False)
    assert finance_voucher_a.actual_total == Decimal("250.00")
    stored = LandedCostVoucher.objects.get(pk=finance_voucher_a.pk)
    assert stored.actual_total == Decimal("0.00")


# =================================================================================================
# receipt_moves() — ruling 2: the allocation base is the STOCK LEDGER
# =================================================================================================

def test_finance_receipt_moves_read_the_stock_ledger_not_the_receipt_lines(
        finance_voucher_a, finance_receipt_a, item_a):
    moves = list(finance_voucher_a.receipt_moves())
    assert len(moves) == 1
    assert moves[0].item_id == item_a.pk
    assert moves[0].reference == finance_receipt_a.number
    assert moves[0].quantity == Decimal("10.0000")
    # The receipt LINE carries free text and no item FK — the L28 stand-in this design works around.
    line = finance_receipt_a.lines.first()
    assert not hasattr(line.po_line, "item")


def test_finance_receipt_moves_ignore_other_documents(
        tenant_a, finance_voucher_a, item_a, location_a):
    from apps.scm.tests._helpers import seed_stock
    seed_stock(tenant_a, item_a, location_a, "7", "9.0000", reference="SOMETHING-ELSE")
    assert finance_voucher_a.receipt_moves().count() == 1


def test_finance_receipt_moves_exclude_the_cancellation_mirror(
        tenant_a, finance_voucher_a, finance_receipt_a, item_a, location_a):
    """The ledger is append-only: a cancellation leaves the original AND its negative twin, and
    allocating over the pair would land cost on quantities that are no longer there."""
    from apps.scm.views._helpers import _post_stock_move
    _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("-10"),
                     move_type="receipt", unit_cost=Decimal("15.0000"),
                     reference=finance_receipt_a.number, reason="Receipt cancelled")
    assert StockMove.objects.filter(reference=finance_receipt_a.number).count() == 2
    assert finance_voucher_a.receipt_moves().count() == 1


def test_finance_receipt_moves_ignore_non_receipt_move_types(
        tenant_a, finance_voucher_a, finance_receipt_a, item_a, location_a):
    from apps.scm.views._helpers import _post_stock_move
    _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("2"),
                     move_type="adjustment", unit_cost=Decimal("15.0000"),
                     reference=finance_receipt_a.number, reason="Found stock")
    assert finance_voucher_a.receipt_moves().count() == 1


def test_finance_receipt_moves_are_ordered_by_id_not_by_moved_at(
        tenant_a, finance_voucher_a, finance_receipt_a, item_a, location_a):
    """So the row that absorbs the rounding remainder is the same row every time the button is
    pressed — the model's own default ordering is ``-moved_at``."""
    from apps.scm.views._helpers import _post_stock_move
    older = _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("3"),
                             move_type="receipt", unit_cost=Decimal("15.0000"),
                             reference=finance_receipt_a.number,
                             moved_at=timezone.now() - datetime.timedelta(days=5))
    ids = [move.pk for move in finance_voucher_a.receipt_moves()]
    assert ids == sorted(ids)
    assert ids[-1] == older.pk


def test_finance_receipt_moves_are_empty_without_a_receipt():
    assert LandedCostVoucher().receipt_moves().count() == 0


# =================================================================================================
# split_charges() — who this voucher can bill to its OWN payee
# =================================================================================================

def test_finance_split_charges_bills_a_blank_or_matching_vendor(
        finance_voucher_a, supplier_a, gl_expense):
    blank = _finance_charge(finance_voucher_a, gl_account=gl_expense)
    same = _finance_charge(finance_voucher_a, party=supplier_a, gl_account=gl_expense)
    billable, excluded = finance_voucher_a.split_charges()
    assert {row.pk for row in billable} == {blank.pk, same.pk}
    assert excluded == []


def test_finance_split_charges_excludes_a_different_vendor(finance_voucher_a, vendor_a):
    other = _finance_charge(finance_voucher_a, party=vendor_a)
    billable, excluded = finance_voucher_a.split_charges()
    assert billable == []
    assert [row.pk for row in excluded] == [other.pk]


# =================================================================================================
# allocate() — the engine. Idempotent, remainder-exact, and it refuses rather than falls through
# =================================================================================================

def test_finance_allocate_writes_one_row_per_move_and_steps_the_status(
        finance_voucher_a, finance_charge_a, item_a):
    result = finance_voucher_a.allocate()
    finance_voucher_a.refresh_from_db()
    assert finance_voucher_a.status == "allocated"
    assert result == {"rows": 1, "amount": Decimal("100.00"), "charges": 1, "fallbacks": []}
    row = finance_voucher_a.allocations.get()
    assert row.item_id == item_a.pk
    assert row.quantity == Decimal("10.0000")
    assert row.allocated_amount == Decimal("100.00")
    assert row.unit_cost_uplift == Decimal("10.0000")
    assert row.basis_used == "value"


def test_finance_allocate_rolls_the_uplift_into_the_item_average_cost(
        finance_allocated_voucher_a, item_a):
    """15.0000 received + 100.00 spread over 10 on-hand units = 25.0000."""
    item_a.refresh_from_db()
    assert item_a.on_hand() == Decimal("10.0000")
    assert item_a.average_cost == Decimal("25.0000")


def test_finance_allocate_is_idempotent(finance_allocated_voucher_a, item_a):
    """Ruling 5 — ``_unallocate()`` runs FIRST, inside the same transaction. Rolling a cost into
    ``average_cost`` twice is invisible on every page and permanently wrong in the ledger."""
    item_a.refresh_from_db()
    once = item_a.average_cost
    finance_allocated_voucher_a.allocate()
    finance_allocated_voucher_a.refresh_from_db()
    item_a.refresh_from_db()
    assert item_a.average_cost == once == Decimal("25.0000")
    assert finance_allocated_voucher_a.allocations.count() == 1
    assert finance_allocated_voucher_a.allocated_total == Decimal("100.00")


def test_finance_allocate_last_row_absorbs_the_rounding_remainder(finance_voucher_multi_a):
    """A naive three-way split of 100.00 allocates 99.99 and quietly disagrees with the bill."""
    finance_voucher_multi_a.allocate()
    amounts = _finance_amounts(finance_voucher_multi_a)
    assert amounts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(amounts) == Decimal("100.00")


def test_finance_allocate_stamps_the_basis_actually_used(finance_voucher_multi_a):
    finance_voucher_multi_a.allocate()
    assert {row.basis_used for row in finance_voucher_multi_a.allocations.all()} == {"equal"}


def test_finance_allocate_falls_back_from_weight_to_quantity(finance_voucher_multi_a):
    """``Item.weight_kg`` is nullable and an unweighed workspace is the normal case, not an error —
    so the basis falls back and the row RECORDS that it did."""
    charge = finance_voucher_multi_a.charges.get()
    charge.allocation_basis = "weight"
    charge.save(update_fields=["allocation_basis"])
    result = finance_voucher_multi_a.allocate()
    assert result["fallbacks"] == ["By Weight → By Quantity"]
    assert {row.basis_used for row in finance_voucher_multi_a.allocations.all()} == {"quantity"}


def test_finance_allocate_uses_weight_when_the_items_have_been_weighed(
        tenant_a, finance_receipt_a, finance_voucher_a, finance_weighted_item_a, location_a,
        item_a):
    from apps.scm.tests._helpers import seed_stock
    seed_stock(tenant_a, finance_weighted_item_a, location_a, "5", "20.0000",
               reference=finance_receipt_a.number)
    _finance_charge(finance_voucher_a, allocation_basis="weight",
                    estimated_amount=Decimal("100.00"))
    result = finance_voucher_a.allocate()
    assert result["fallbacks"] == []
    rows = {row.item_id: row for row in finance_voucher_a.allocations.all()}
    assert {row.basis_used for row in rows.values()} == {"weight"}
    # item_a has no weight at all, so it carries none of the charge; 5 × 12.5 kg carries all of it.
    assert rows[item_a.pk].allocated_amount == Decimal("0.00")
    assert rows[finance_weighted_item_a.pk].allocated_amount == Decimal("100.00")


def test_finance_allocate_falls_back_from_value_on_a_zero_cost_receipt(
        tenant_a, purchase_order_a, location_a, item_a, supplier_a):
    """A free-of-charge replacement sums to zero value and would otherwise be undividable."""
    grn = _finance_receipt(tenant_a, purchase_order_a, location_a,
                           [(item_a, "4", "0.0000")])
    voucher = _finance_voucher(tenant_a, grn, supplier_a, allocation_basis="value")
    _finance_charge(voucher, estimated_amount=Decimal("40.00"))
    result = voucher.allocate()
    assert result["fallbacks"] == ["By Value → By Quantity"]
    assert voucher.allocations.get().basis_used == "quantity"


def test_finance_allocate_skips_a_recoverable_charge(
        tenant_a, finance_receipt_a, supplier_a, finance_tax_code_a):
    """Recoverable import VAT is reclaimed, not borne — it never lands on the units."""
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    kept = _finance_charge(voucher, estimated_amount=Decimal("60.00"))
    _finance_charge(voucher, charge_type="duty", estimated_amount=Decimal("40.00"),
                    is_recoverable=True, tax_code=finance_tax_code_a)
    result = voucher.allocate()
    assert result["charges"] == 1
    assert {row.charge_id for row in voucher.allocations.all()} == {kept.pk}
    assert voucher.allocated_total == Decimal("60.00")


def test_finance_allocate_skips_a_charge_marked_not_to_capitalise(
        tenant_a, finance_receipt_a, supplier_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("70.00"))
    _finance_charge(voucher, estimated_amount=Decimal("30.00"), capitalise_to_inventory=False)
    voucher.allocate()
    assert voucher.allocated_total == Decimal("70.00")


def test_finance_allocate_refuses_an_unposted_receipt(
        tenant_a, finance_receipt_unposted_a, supplier_a):
    """An absent prerequisite is REJECTED, never fallen through (L35)."""
    voucher = _finance_voucher(tenant_a, finance_receipt_unposted_a, supplier_a)
    _finance_charge(voucher)
    with pytest.raises(ValidationError) as exc:
        voucher.allocate()
    assert "has not been posted to the stock ledger" in str(exc.value)
    assert voucher.status == "draft"
    assert LandedCostAllocation.objects.count() == 0


def test_finance_allocate_refuses_when_nothing_capitalises(finance_recoverable_voucher_a):
    with pytest.raises(ValidationError) as exc:
        finance_recoverable_voucher_a.allocate()
    assert "No charge on this voucher capitalises into inventory" in str(exc.value)
    assert finance_recoverable_voucher_a.status == "draft"


def test_finance_allocate_refuses_a_voucher_with_no_charges_at_all(finance_voucher_a):
    with pytest.raises(ValidationError):
        finance_voucher_a.allocate()


def test_finance_allocate_refuses_a_cancelled_voucher(finance_voucher_a, finance_charge_a):
    finance_voucher_a.cancel()
    with pytest.raises(ValidationError) as exc:
        finance_voucher_a.allocate()
    assert "A cancelled landed cost voucher cannot be allocated." in str(exc.value)


def test_finance_allocate_refuses_a_billed_voucher(finance_allocated_voucher_a):
    bill = finance_allocated_voucher_a.draft_bill()
    with pytest.raises(ValidationError) as exc:
        finance_allocated_voucher_a.allocate()
    assert f"This voucher has been billed as {bill.number}" in str(exc.value)


def test_finance_reallocation_clears_the_accrual_stamp(finance_allocated_voucher_a):
    """The stamp goes back with the rung — an ``accrued_at`` left behind renders an "Accrued" badge
    on a voucher that is no longer accrued."""
    finance_allocated_voucher_a.accrue()
    assert finance_allocated_voucher_a.accrued_at is not None
    finance_allocated_voucher_a.allocate()
    finance_allocated_voucher_a.refresh_from_db()
    assert finance_allocated_voucher_a.status == "allocated"
    assert finance_allocated_voucher_a.accrued_at is None


def test_finance_reallocation_replaces_the_rows_after_an_amount_correction(
        finance_voucher_a, finance_charge_a, item_a):
    finance_voucher_a.allocate()
    finance_charge_a.actual_amount = Decimal("200.00")
    finance_charge_a.save(update_fields=["actual_amount"])
    finance_voucher_a.allocate()
    finance_voucher_a.refresh_from_db()
    item_a.refresh_from_db()
    assert finance_voucher_a.allocations.count() == 1
    assert finance_voucher_a.allocated_total == Decimal("200.00")
    assert item_a.average_cost == Decimal("35.0000")   # 15 + 200/10, NOT 15 + 100/10 + 200/10


# =================================================================================================
# LandedCostAllocation — every column derived, written by allocate() and by nobody else
# =================================================================================================

def test_finance_allocation_columns_are_all_uneditable():
    for name in ("quantity", "basis_value", "basis_used", "allocated_amount", "unit_cost_uplift"):
        assert _finance_field(LandedCostAllocation, name).editable is False, name


def test_finance_allocation_carries_its_own_tenant(finance_allocated_voucher_a, tenant_a):
    """The deliberate exception to the tenant-less-child convention: the valuation and variance
    reports query these rows directly, grouped by ``stock_move_id`` / ``item``."""
    row = finance_allocated_voucher_a.allocations.get()
    assert row.tenant_id == tenant_a.pk
    assert row.voucher.tenant_id == row.tenant_id


def test_finance_allocation_rows_appear_only_when_allocate_runs(finance_voucher_a, finance_charge_a):
    assert LandedCostAllocation.objects.count() == 0
    finance_voucher_a.allocate()
    assert LandedCostAllocation.objects.count() == 1


def test_finance_allocation_str_names_the_sku_and_the_uplift(finance_allocated_voucher_a, item_a):
    row = finance_allocated_voucher_a.allocations.get()
    assert str(row) == f"{item_a.sku} · 100.00 (10.0000/unit)"


def test_finance_allocation_quantity_mirrors_the_stock_move(finance_allocated_voucher_a):
    row = finance_allocated_voucher_a.allocations.select_related("stock_move").get()
    assert row.quantity == row.stock_move.quantity
    assert row.item_id == row.stock_move.item_id


def test_finance_allocation_column_ceilings_are_declared():
    """``bulk_create()`` skips ``full_clean()`` AND the validators, so these constants are the only
    guard between a derived Decimal and the driver."""
    assert MAX_UPLIFT == Decimal("9999999999.9999")
    assert MAX_BASIS_VALUE == Decimal("999999999999.9999")
    uplift = _finance_field(LandedCostAllocation, "unit_cost_uplift")
    basis = _finance_field(LandedCostAllocation, "basis_value")
    assert (uplift.max_digits, uplift.decimal_places) == (14, 4)
    assert (basis.max_digits, basis.decimal_places) == (16, 4)


def test_finance_basis_fallback_chains_all_terminate_at_equal():
    assert _BASIS_FALLBACKS == {
        "value": ("value", "quantity", "equal"),
        "quantity": ("quantity", "equal"),
        "weight": ("weight", "quantity", "equal"),
        "volume": ("volume", "quantity", "equal"),
        "equal": ("equal",),
    }
    for requested, chain in _BASIS_FALLBACKS.items():
        assert chain[0] == requested and chain[-1] == "equal"


# =================================================================================================
# accrue() — allocated → accrued, and nothing else may reach it
# =================================================================================================

def test_finance_accrue_stamps_the_time_it_happened(finance_allocated_voucher_a):
    before = timezone.now()
    finance_allocated_voucher_a.accrue()
    finance_allocated_voucher_a.refresh_from_db()
    assert finance_allocated_voucher_a.status == "accrued"
    assert before <= finance_allocated_voucher_a.accrued_at <= timezone.now()


def test_finance_accrue_refuses_a_draft_voucher(finance_voucher_a):
    with pytest.raises(ValidationError) as exc:
        finance_voucher_a.accrue()
    assert "Only an allocated voucher can be accrued; this one is draft." in str(exc.value)
    assert finance_voucher_a.accrued_at is None


def test_finance_accrue_refuses_a_cancelled_voucher(finance_allocated_voucher_a):
    finance_allocated_voucher_a.cancel()
    with pytest.raises(ValidationError) as exc:
        finance_allocated_voucher_a.accrue()
    assert "this one is cancelled." in str(exc.value)


def test_finance_accrue_refuses_a_second_time(finance_allocated_voucher_a):
    finance_allocated_voucher_a.accrue()
    with pytest.raises(ValidationError) as exc:
        finance_allocated_voucher_a.accrue()
    assert "this one is accrued." in str(exc.value)


# =================================================================================================
# draft_bill() — the AP hand-off. A DRAFT accounting.Bill, and SCM posts NO JournalEntry
# =================================================================================================

def test_finance_draft_bill_creates_a_draft_bill_and_reconciles(
        finance_allocated_voucher_a, supplier_a, usd, gl_expense):
    bill = finance_allocated_voucher_a.draft_bill()
    finance_allocated_voucher_a.refresh_from_db()
    assert bill.status == "draft"
    assert bill.party_id == supplier_a.pk
    assert bill.currency_id == usd.pk
    assert bill.bill_date == _finance_today()
    assert bill.total == Decimal("100.00")
    assert finance_allocated_voucher_a.status == "reconciled"
    assert finance_allocated_voucher_a.bill_id == bill.pk
    line = bill.lines.get()
    assert line.quantity == Decimal("1")            # the real figure rides in unit_price (2dp)
    assert line.unit_price == Decimal("100.00")
    assert line.line_total == Decimal("100.00")
    assert line.gl_account_id == gl_expense.pk


def test_finance_draft_bill_line_names_the_charge_and_the_receipt(
        finance_allocated_voucher_a, finance_receipt_a):
    bill = finance_allocated_voucher_a.draft_bill()
    assert bill.lines.get().description == f"Freight — Ocean freight · {finance_receipt_a.number}"


def test_finance_draft_bill_posts_no_journal_entry(finance_allocated_voucher_a):
    """Ruling 1 — approval, tax, payment and the GL effect are Module 2's."""
    from apps.accounting.models import JournalEntry
    before = JournalEntry.objects.count()
    bill = finance_allocated_voucher_a.draft_bill()
    assert JournalEntry.objects.count() == before
    assert bill.journal_entry_id is None


def test_finance_draft_bill_is_idempotent(finance_allocated_voucher_a):
    """Pressing the button twice is the ordinary mistake; a duplicate vendor bill is the expensive one."""
    from apps.accounting.models import Bill
    first = finance_allocated_voucher_a.draft_bill()
    second = finance_allocated_voucher_a.draft_bill()
    assert first.pk == second.pk
    assert Bill.objects.count() == 1


def test_finance_draft_bill_refuses_un_allocated_capitalising_charges(
        finance_voucher_a, finance_charge_a):
    with pytest.raises(ValidationError) as exc:
        finance_voucher_a.draft_bill()
    assert "Allocate the landed costs before drafting a vendor bill" in str(exc.value)
    assert finance_voucher_a.bill_id is None


def test_finance_draft_bill_bills_a_purely_recoverable_voucher_from_draft(
        finance_recoverable_voucher_a):
    """A voucher that can never be allocated must not be trapped in draft — the vendor still has to
    be paid."""
    bill = finance_recoverable_voucher_a.draft_bill()
    finance_recoverable_voucher_a.refresh_from_db()
    assert bill.status == "draft"
    assert finance_recoverable_voucher_a.status == "reconciled"
    assert bill.lines.get().unit_price == Decimal("50.00")


def test_finance_draft_bill_clamps_a_wide_tax_rate(
        tenant_a, finance_receipt_a, supplier_a, finance_wide_tax_code_a, gl_expense):
    """``TaxCode.rate_pct`` is DECIMAL(6, 3) and ``BillLine.tax_rate_pct`` is DECIMAL(5, 2) — an
    unclamped copy overflows to ``DataError``."""
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, tax_code=finance_wide_tax_code_a, gl_account=gl_expense)
    voucher.allocate()
    bill = voucher.draft_bill()
    assert finance_wide_tax_code_a.rate_pct == Decimal("999.999")
    assert bill.lines.get().tax_rate_pct == MAX_BILL_TAX_RATE_PCT == Decimal("999.99")


def test_finance_draft_bill_copies_a_normal_tax_rate_unchanged(
        tenant_a, finance_receipt_a, supplier_a, finance_tax_code_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, tax_code=finance_tax_code_a)
    voucher.allocate()
    bill = voucher.draft_bill()
    assert bill.lines.get().tax_rate_pct == Decimal("20.00")


def test_finance_draft_bill_excludes_a_charge_naming_another_vendor(
        tenant_a, finance_receipt_a, supplier_a, vendor_a):
    """Quietly invoicing the forwarder for the customs broker's fee is the failure this prevents."""
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, estimated_amount=Decimal("60.00"))
    _finance_charge(voucher, estimated_amount=Decimal("40.00"), party=vendor_a,
                    charge_type="brokerage")
    voucher.allocate()
    bill = voucher.draft_bill()
    assert bill.lines.count() == 1
    assert bill.lines.get().unit_price == Decimal("60.00")


def test_finance_draft_bill_refuses_when_every_charge_names_another_vendor(
        tenant_a, finance_receipt_a, supplier_a, vendor_a):
    voucher = _finance_voucher(tenant_a, finance_receipt_a, supplier_a)
    _finance_charge(voucher, party=vendor_a)
    voucher.allocate()
    with pytest.raises(ValidationError) as exc:
        voucher.draft_bill()
    assert "Every charge on this voucher names a different vendor (1 of them)" in str(exc.value)
    assert voucher.bill_id is None


def test_finance_draft_bill_refuses_a_cancelled_voucher(finance_allocated_voucher_a):
    finance_allocated_voucher_a.cancel()
    with pytest.raises(ValidationError) as exc:
        finance_allocated_voucher_a.draft_bill()
    assert "A cancelled voucher has had its costs reversed" in str(exc.value)


# =================================================================================================
# cancel() — reverses the inventory uplift, and is refused once a bill exists
# =================================================================================================

def test_finance_cancel_reverses_the_allocation(finance_allocated_voucher_a, item_a):
    """A voucher raised in error that were merely MARKED cancelled would leave every affected item
    permanently over-valued."""
    finance_allocated_voucher_a.cancel()
    finance_allocated_voucher_a.refresh_from_db()
    item_a.refresh_from_db()
    assert finance_allocated_voucher_a.status == "cancelled"
    assert finance_allocated_voucher_a.allocations.count() == 0
    assert finance_allocated_voucher_a.allocated_total == Decimal("0.00")
    assert item_a.average_cost == Decimal("15.0000")   # back to the receipt cost
    assert item_a.on_hand() == Decimal("10.0000")      # quantity is never touched


def test_finance_cancel_keeps_the_charge_totals(finance_allocated_voucher_a):
    finance_allocated_voucher_a.cancel()
    finance_allocated_voucher_a.refresh_from_db()
    assert finance_allocated_voucher_a.estimated_total == Decimal("100.00")


def test_finance_cancel_works_straight_from_draft(finance_voucher_a):
    finance_voucher_a.cancel()
    assert finance_voucher_a.status == "cancelled"


def test_finance_cancel_refuses_a_second_time(finance_voucher_a):
    finance_voucher_a.cancel()
    with pytest.raises(ValidationError) as exc:
        finance_voucher_a.cancel()
    assert "This voucher is already cancelled." in str(exc.value)


def test_finance_cancel_refuses_once_a_bill_exists(finance_allocated_voucher_a):
    bill = finance_allocated_voucher_a.draft_bill()
    with pytest.raises(ValidationError) as exc:
        finance_allocated_voucher_a.cancel()
    assert f"This voucher has been billed as {bill.number}" in str(exc.value)
    assert finance_allocated_voucher_a.status == "reconciled"
