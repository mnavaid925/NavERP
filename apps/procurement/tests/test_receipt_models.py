"""Procurement 6.12 - Goods Receipt & Inspection model tests.

Load-bearing contracts covered here:

* ``ReceiptTolerancePolicy`` as a CONFIGURATION MASTER - no ``number``, no ``status``, and
  deliberately NO ``unique_together``: overlapping bands are legal and the resolver, not a
  database constraint, decides which one governs a line;
* the three module-level functions the whole sub-module leans on - ``resolve_receipt_tolerance``
  (which rule wins: tier DESC, vendor-pinned first, priority ASC, id ASC),
  ``evaluate_receipt_tolerance`` (what that rule says about these quantities and dates, quantity
  breaches outranking date breaches) and ``resolve_line_item`` (the free-text ``sku_hint`` ->
  ``scm.Item`` bridge) - tested directly rather than re-implemented in a test;
* per-tenant ``RDS-`` / ``RTV-`` auto-numbering (prefix, five-digit padding, sequence, and no
  collision across tenants) plus ``unique_together = ("tenant", "number")``;
* every KIND / SEVERITY / REMEDY / STATUS / ACTION / REASON / VERDICT choice value and the
  colour-only badge maps (a semantic ``badge-success`` renders unstyled in this theme - L33);
* the guarded verb ladders - ``ReceiptDiscrepancy.notify_vendor/resolve/cancel`` and
  ``ReturnToVendor.authorize/mark_shipped/close/cancel`` - each of which re-checks its own guard
  INSIDE the method, returns a bool, and no-ops on a double submit rather than re-stamping a date
  or reassigning who signed;
* and the invariant this sub-module lives or dies on (L29): every quantity and every money figure
  is DERIVED at read time - ``ReturnToVendor.expected_credit_value`` folds its lines on every
  read, cumulative received quantity is an aggregate across live receipts, and none of
  ``scope_key`` / ``specificity_tier`` / ``vendor`` / ``expected_credit`` / ``line_count`` is a
  stored, editable column. An RTV moving through its whole ladder posts ZERO ``scm.StockMove``
  and ZERO ``accounting.JournalEntry`` rows.

Determinism (L16): every date basis here is ``timezone.localdate()`` - the same basis the model
verbs use - and every datetime basis is ``timezone.now()``. ``datetime.date.today()`` never
appears, or the exact-date assertions flake for the hours after local midnight.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.procurement.models import (
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    ReturnToVendor,
    ReturnToVendorLine,
    evaluate_receipt_tolerance,
    resolve_line_item,
    resolve_receipt_tolerance,
)

pytestmark = pytest.mark.django_db


# -- local helpers ------------------------------------------------------------------------------
# Named _receipt_* so a later sub-module appending near this file cannot shadow them. The conftest
# factories of the same shape are private to conftest (the 6.11 precedent), so the extra rows this
# module needs are minted here.

#: theme.css ships exactly these modifier classes. Anything else renders completely unstyled.
_RECEIPT_BADGE_COLOURS = {
    "badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted", "badge-slate",
}

#: The em dash the band helpers print when a rule declares no band on that axis.
_RECEIPT_EMPTY_BAND = "\u2014"

#: The middot the two numbered documents fold into their __str__.
_RECEIPT_DOT = "\u00b7"


def _receipt_today():
    """The SAME basis every verb and every board compares against (L16)."""
    return timezone.localdate()


def _receipt_days(count):
    return datetime.timedelta(days=count)


def _receipt_policy(tenant, name="Local band", **overrides):
    """A saved policy. ``objects.create`` deliberately skips ``clean()``, so resolver cases can
    mint band-less or otherwise unusual rules that the form would never accept."""
    fields = dict(tenant=tenant, name=name, over_receipt_pct=Decimal("5"))
    fields.update(overrides)
    return ReceiptTolerancePolicy.objects.create(**fields)


def _receipt_unsaved_policy(name="Unsaved band", **overrides):
    """An in-memory rule for the pure evaluator cases - no DB round trip, no tenant needed."""
    fields = dict(name=name)
    fields.update(overrides)
    return ReceiptTolerancePolicy(**fields)


def _receipt_discrepancy(tenant, grn, **overrides):
    fields = dict(tenant=tenant, goods_receipt=grn, kind="short_shipment",
                  quantity_affected=Decimal("2"), description="Three cartons short.")
    fields.update(overrides)
    return ReceiptDiscrepancy.objects.create(**fields)


def _receipt_rtv(tenant, vendor, **overrides):
    fields = dict(tenant=tenant, vendor=vendor, reason="damaged")
    fields.update(overrides)
    return ReturnToVendor.objects.create(**fields)


def _receipt_rtv_line(rtv, **overrides):
    fields = dict(return_to_vendor=rtv, quantity_returned=Decimal("3"))
    fields.update(overrides)
    return ReturnToVendorLine.objects.create(**fields)


def _receipt_second_po(tenant, vendor, **overrides):
    """A SECOND approved spine order in the same workspace - the 'different order' cases."""
    from apps.scm.models import PurchaseOrder

    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=_receipt_today(), expected_date=_receipt_today())
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _receipt_second_po_line(po, description="Spare coupling", qty="5", price="12.00", **kw):
    from apps.scm.models import PurchaseOrderLine

    fields = dict(purchase_order=po, item_description=description, quantity=Decimal(qty),
                  unit_price=Decimal(price), sku_hint="CPL-1", uom_hint="EA")
    fields.update(kw)
    return PurchaseOrderLine.objects.create(**fields)


def _receipt_second_grn(tenant, po, reference="DN-9999", **overrides):
    from apps.scm.models import GoodsReceiptNote

    fields = dict(tenant=tenant, purchase_order=po, receipt_date=_receipt_today(),
                  status="draft", delivery_note_ref=reference)
    fields.update(overrides)
    return GoodsReceiptNote.objects.create(**fields)


def _receipt_grn_line(grn, po_line, received="1", **overrides):
    from apps.scm.models import GoodsReceiptLine

    fields = dict(goods_receipt=grn, po_line=po_line, quantity_received=Decimal(received))
    fields.update(overrides)
    return GoodsReceiptLine.objects.create(**fields)


def _receipt_field_names(model):
    return {f.name for f in model._meta.get_fields()}


def _receipt_choice_values(choices):
    return [value for value, _ in choices]


def _receipt_posting_counts(tenant):
    """(stock moves, journal entries) for one workspace - the non-posting invariant's meter."""
    from apps.accounting.models import JournalEntry
    from apps.scm.models import StockMove

    return (StockMove.objects.filter(tenant=tenant).count(),
            JournalEntry.objects.filter(tenant=tenant).count())


# ================================================================================================
# 1. ReceiptTolerancePolicy - shape, defaults, choices, badge maps
# ================================================================================================

def test_receipt_policy_minimal_create_takes_every_documented_default(tenant_a):
    rule = ReceiptTolerancePolicy.objects.create(tenant=tenant_a, name="Workspace 5% band",
                                                 over_receipt_pct=Decimal("5"))

    assert rule.item_id is None
    assert rule.category_id is None
    assert rule.vendor_id is None
    assert rule.under_receipt_pct is None
    assert rule.over_receipt_qty is None
    assert rule.allow_unlimited_over_receipt is False
    assert rule.early_receipt_days is None
    assert rule.late_receipt_days is None
    assert rule.action == "warn"
    assert rule.price_variance_pct is None
    assert rule.priority == 10
    assert rule.is_active is True
    assert rule.notes == ""
    assert rule.created_at is not None and rule.updated_at is not None


def test_receipt_policy_is_a_configuration_master_with_no_number_and_no_status():
    names = _receipt_field_names(ReceiptTolerancePolicy)

    assert "number" not in names, "a tolerance rule is never quoted by reference"
    assert "status" not in names, "a rule is active or it is not; it has no workflow"
    assert not hasattr(ReceiptTolerancePolicy, "NUMBER_PREFIX")
    assert {"tenant", "is_active", "priority"} <= names


def test_receipt_policy_str_folds_name_and_action_label(tenant_a):
    rule = _receipt_policy(tenant_a, name="ACME 5% over-receipt", action="block_flag")
    assert str(rule) == "ACME 5% over-receipt (Flag as Blocking)"


def test_receipt_policy_action_choices_are_the_three_documented_values():
    assert ReceiptTolerancePolicy.ACTION_CHOICES == [
        ("none", "No Action"),
        ("warn", "Warn"),
        ("block_flag", "Flag as Blocking"),
    ]


def test_receipt_policy_scope_choices_are_a_derived_vocabulary_not_a_column():
    assert _receipt_choice_values(ReceiptTolerancePolicy.SCOPE_CHOICES) == [
        "item", "category", "catchall"]
    assert "scope" not in _receipt_field_names(ReceiptTolerancePolicy)


def test_receipt_policy_verdict_choices_are_the_evaluator_vocabulary():
    assert _receipt_choice_values(ReceiptTolerancePolicy.VERDICT_CHOICES) == [
        "ok", "over", "short", "early", "late", "no_rule"]


def test_receipt_policy_badge_maps_use_colour_named_classes_only(tenant_a):
    rule = _receipt_policy(tenant_a)
    assert set(ReceiptTolerancePolicy.VERDICT_CSS.values()) <= _RECEIPT_BADGE_COLOURS
    assert rule.action_css in _RECEIPT_BADGE_COLOURS
    assert rule.scope_css in _RECEIPT_BADGE_COLOURS


def test_receipt_policy_verdict_css_covers_every_verdict_value():
    assert set(ReceiptTolerancePolicy.VERDICT_CSS) == {
        v for v, _ in ReceiptTolerancePolicy.VERDICT_CHOICES}


def test_receipt_policy_action_css_maps_each_action_and_falls_back_to_muted(tenant_a):
    assert _receipt_policy(tenant_a, action="none").action_css == "badge-muted"
    assert _receipt_policy(tenant_a, action="warn").action_css == "badge-amber"
    assert _receipt_policy(tenant_a, action="block_flag").action_css == "badge-red"
    assert _receipt_unsaved_policy(action="not-a-choice").action_css == "badge-muted"


def test_receipt_policy_scope_css_distinguishes_item_category_and_catchall(
        tenant_a, receipt_item_a, receipt_category_a):
    assert _receipt_policy(tenant_a, item=receipt_item_a).scope_css == "badge-info"
    assert _receipt_policy(tenant_a, category=receipt_category_a).scope_css == "badge-slate"
    assert _receipt_policy(tenant_a).scope_css == "badge-muted"


def test_receipt_policy_meta_orders_by_priority_then_id():
    assert ReceiptTolerancePolicy._meta.ordering == ["priority", "id"]
    assert ReceiptTolerancePolicy._meta.verbose_name == "Receipt Tolerance Policy"
    assert ReceiptTolerancePolicy._meta.verbose_name_plural == "Receipt Tolerance Policies"


def test_receipt_policy_has_no_unique_together_because_overlaps_are_legal(tenant_a):
    assert ReceiptTolerancePolicy._meta.unique_together == ()

    _receipt_policy(tenant_a, name="Workspace band", priority=10)
    _receipt_policy(tenant_a, name="Workspace band", priority=10)

    assert ReceiptTolerancePolicy.objects.filter(
        tenant=tenant_a, name="Workspace band").count() == 2


def test_receipt_policy_indexes_back_the_resolver_and_the_register():
    names = {index.name for index in ReceiptTolerancePolicy._meta.indexes}
    assert {"prc_rtp_tnt_act_pri_idx", "prc_rtp_tnt_action_idx"} <= names


def test_receipt_policy_default_ordering_puts_the_lowest_priority_first(tenant_a):
    ten = _receipt_policy(tenant_a, name="Ten", priority=10)
    one = _receipt_policy(tenant_a, name="One", priority=1)
    five = _receipt_policy(tenant_a, name="Five", priority=5)

    assert list(ReceiptTolerancePolicy.objects.filter(tenant=tenant_a)) == [one, five, ten]


def test_receipt_policy_rows_are_scoped_to_their_own_tenant(tenant_a, tenant_b,
                                                            receipt_policy_catchall_a,
                                                            receipt_policy_b):
    assert list(ReceiptTolerancePolicy.objects.filter(tenant=tenant_a)) == [
        receipt_policy_catchall_a]
    assert list(ReceiptTolerancePolicy.objects.filter(tenant=tenant_b)) == [receipt_policy_b]


# ------------------------------------------------------------------ clean() boundaries

def test_receipt_policy_clean_rejects_an_item_and_a_category_at_once(tenant_a, receipt_item_a,
                                                                    receipt_category_a):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Ambiguous", item=receipt_item_a,
                                  category=receipt_category_a, over_receipt_pct=Decimal("5"))
    with pytest.raises(ValidationError) as excinfo:
        rule.full_clean()
    assert "category" in excinfo.value.message_dict


def test_receipt_policy_clean_rejects_a_cross_tenant_item(tenant_a, receipt_item_b):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Foreign item", item=receipt_item_b,
                                  over_receipt_pct=Decimal("5"))
    with pytest.raises(ValidationError) as excinfo:
        rule.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["item"])


def test_receipt_policy_clean_rejects_a_cross_tenant_category(tenant_a, receipt_category_b):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Foreign category",
                                  category=receipt_category_b, over_receipt_pct=Decimal("5"))
    with pytest.raises(ValidationError) as excinfo:
        rule.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["category"])


def test_receipt_policy_clean_rejects_a_cross_tenant_vendor(tenant_a, receipt_vendor_b):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Foreign vendor", vendor=receipt_vendor_b,
                                  over_receipt_pct=Decimal("5"))
    with pytest.raises(ValidationError) as excinfo:
        rule.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["vendor"])


def test_receipt_policy_clean_rejects_a_rule_that_declares_no_band_at_all(tenant_a):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Judges nothing")
    with pytest.raises(ValidationError) as excinfo:
        rule.full_clean()
    assert "at least one band" in " ".join(excinfo.value.message_dict["over_receipt_pct"])


def test_receipt_policy_clean_accepts_the_unlimited_flag_as_a_band_on_its_own(tenant_a):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Never flag an over-receipt",
                                  allow_unlimited_over_receipt=True)
    rule.full_clean()        # must not raise


def test_receipt_policy_clean_accepts_a_date_only_band(tenant_a):
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Dates only", early_receipt_days=2,
                                  late_receipt_days=3)
    rule.full_clean()        # must not raise


def test_receipt_policy_clean_accepts_a_zero_percent_band_as_a_real_band(tenant_a):
    """Zero tolerance is a DECISION, not a missing value - ``is not None`` is the test."""
    rule = ReceiptTolerancePolicy(tenant=tenant_a, name="Strict", over_receipt_pct=Decimal("0"))
    rule.full_clean()        # must not raise


def test_receipt_policy_clean_passes_for_every_shipped_fixture(receipt_policy_catchall_a,
                                                               receipt_policy_item_a,
                                                               receipt_policy_category_a,
                                                               receipt_policy_vendor_a):
    for rule in (receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_category_a,
                 receipt_policy_vendor_a):
        rule.full_clean()


# ------------------------------------------------------------------ derived scope + band text

def test_receipt_policy_scope_is_derived_from_the_pinned_fks(tenant_a, receipt_item_a,
                                                             receipt_category_a):
    item_rule = _receipt_policy(tenant_a, item=receipt_item_a)
    category_rule = _receipt_policy(tenant_a, category=receipt_category_a)
    catchall = _receipt_policy(tenant_a)

    assert (item_rule.scope_key, item_rule.scope_label, item_rule.specificity_tier) == (
        "item", "Item", 3)
    assert (category_rule.scope_key, category_rule.scope_label,
            category_rule.specificity_tier) == ("category", "Category", 2)
    assert (catchall.scope_key, catchall.scope_label, catchall.specificity_tier) == (
        "catchall", "Catch-all", 1)


def test_receipt_policy_scope_follows_the_fk_without_a_save(tenant_a, receipt_item_a):
    """Nothing is cached: clearing the item downgrades the rule to a catch-all immediately."""
    rule = _receipt_policy(tenant_a, item=receipt_item_a)
    assert rule.specificity_tier == 3

    rule.item = None
    assert rule.scope_key == "catchall"
    assert rule.specificity_tier == 1


def test_receipt_policy_over_band_text_renders_a_percentage_with_its_ceiling(tenant_a):
    rule = _receipt_policy(tenant_a, over_receipt_pct=Decimal("5"))
    assert rule.over_band_text == "5% (max 105 on 100)"


def test_receipt_policy_over_band_text_folds_both_bands_when_both_are_set(tenant_a):
    rule = _receipt_policy(tenant_a, over_receipt_pct=Decimal("5"),
                           over_receipt_qty=Decimal("2"))
    assert rule.over_band_text == "5% (max 105 on 100) / 2 units"


def test_receipt_policy_over_band_text_says_unlimited_when_the_escape_flag_is_on(tenant_a):
    rule = _receipt_policy(tenant_a, over_receipt_pct=Decimal("5"),
                           allow_unlimited_over_receipt=True)
    assert rule.over_band_text == "Unlimited"


def test_receipt_policy_over_band_text_is_an_em_dash_when_no_over_band_is_set(tenant_a):
    rule = _receipt_policy(tenant_a, over_receipt_pct=None, late_receipt_days=1)
    assert rule.over_band_text == _RECEIPT_EMPTY_BAND


def test_receipt_policy_band_text_trims_trailing_zeros_after_a_db_round_trip(tenant_a):
    """A DB-loaded ``Decimal("5.00")`` must print as ``5`` - a band label is read, not parsed."""
    saved = _receipt_policy(tenant_a, over_receipt_pct=Decimal("5.00"),
                            under_receipt_pct=Decimal("10.00"))
    reloaded = ReceiptTolerancePolicy.objects.get(pk=saved.pk)

    assert reloaded.over_receipt_pct == Decimal("5.00")     # the column keeps its scale
    assert reloaded.over_band_text == "5% (max 105 on 100)"
    assert reloaded.under_band_text == "10% (min 90 on 100)"


def test_receipt_policy_under_band_text_renders_its_floor_or_an_em_dash(tenant_a):
    assert _receipt_policy(tenant_a, under_receipt_pct=Decimal("10")).under_band_text == (
        "10% (min 90 on 100)")
    assert _receipt_policy(tenant_a).under_band_text == _RECEIPT_EMPTY_BAND


def test_receipt_policy_date_band_text_pluralises_and_folds_both_axes(tenant_a):
    assert _receipt_policy(tenant_a, early_receipt_days=2,
                           late_receipt_days=3).date_band_text == "2 days early / 3 days late"
    assert _receipt_policy(tenant_a, early_receipt_days=1,
                           late_receipt_days=1).date_band_text == "1 day early / 1 day late"
    assert _receipt_policy(tenant_a, late_receipt_days=0).date_band_text == "0 days late"
    assert _receipt_policy(tenant_a).date_band_text == _RECEIPT_EMPTY_BAND


def test_receipt_policy_worked_example_prices_the_catchall_band_on_a_hundred(
        receipt_policy_catchall_a):
    example = receipt_policy_catchall_a.worked_example()

    assert example["ordered"] == Decimal("100")
    assert example["max_accept"] == Decimal("105")
    assert example["min_accept"] == Decimal("90")
    assert example["over_text"] == "5% (max 105 on 100)"
    assert example["under_text"] == "10% (min 90 on 100)"
    assert example["date_text"] == "2 days early / 3 days late"
    assert example["unlimited"] is False


def test_receipt_policy_worked_example_has_no_ceiling_when_over_receipt_is_unlimited(tenant_a):
    example = _receipt_policy(tenant_a, over_receipt_pct=Decimal("5"),
                              allow_unlimited_over_receipt=True).worked_example()

    assert example["max_accept"] is None
    assert example["unlimited"] is True


def test_receipt_policy_worked_example_ceiling_equals_the_order_with_no_over_band(tenant_a):
    """No over band at all is ZERO tolerance, not 'anything goes'."""
    example = _receipt_policy(tenant_a, over_receipt_pct=None,
                              under_receipt_pct=Decimal("10")).worked_example()

    assert example["max_accept"] == Decimal("100")
    assert example["over_text"] == _RECEIPT_EMPTY_BAND


def test_receipt_policy_worked_example_takes_the_more_restrictive_of_the_two_over_bands(tenant_a):
    rule = _receipt_policy(tenant_a, over_receipt_pct=Decimal("50"),
                           over_receipt_qty=Decimal("2"))
    assert rule.worked_example()["max_accept"] == Decimal("102")


def test_receipt_policy_worked_example_accepts_a_different_ordered_quantity(tenant_a):
    rule = _receipt_policy(tenant_a, over_receipt_pct=Decimal("5"),
                           under_receipt_pct=Decimal("10"))
    example = rule.worked_example(ordered=Decimal("200"))

    assert example["ordered"] == Decimal("200")
    assert example["max_accept"] == Decimal("210")
    assert example["min_accept"] == Decimal("180")


def test_receipt_policy_worked_example_leaves_min_accept_unjudged_without_an_under_band(tenant_a):
    assert _receipt_policy(tenant_a).worked_example()["min_accept"] is None


def test_receipt_policy_derived_reads_are_not_stored_columns():
    names = _receipt_field_names(ReceiptTolerancePolicy)
    for derived in ("scope_key", "scope_label", "specificity_tier", "over_band_text",
                    "under_band_text", "date_band_text", "action_css", "scope_css"):
        assert derived not in names


# ================================================================================================
# 2. resolve_receipt_tolerance - which rule governs this line
# ================================================================================================

def test_receipt_resolver_returns_the_catchall_when_it_is_the_only_rule(
        tenant_a, receipt_vendor_a, receipt_item_a, receipt_policy_catchall_a):
    rule, reason = resolve_receipt_tolerance(receipt_item_a, receipt_vendor_a, tenant=tenant_a)

    assert rule == receipt_policy_catchall_a
    assert reason == ("Matched catch-all rule 'Workspace 5% band' (priority 10)")


def test_receipt_resolver_prefers_the_item_rule_over_category_and_catchall(
        tenant_a, receipt_vendor_a, receipt_item_a, receipt_policy_catchall_a,
        receipt_policy_category_a, receipt_policy_item_a):
    rule, reason = resolve_receipt_tolerance(receipt_item_a, receipt_vendor_a, tenant=tenant_a)

    assert rule == receipt_policy_item_a
    assert "item rule" in reason and "BRG-40 strict" in reason


def test_receipt_resolver_prefers_the_category_rule_over_the_catchall(
        tenant_a, receipt_vendor_a, receipt_item_a, receipt_policy_catchall_a,
        receipt_policy_category_a):
    rule, reason = resolve_receipt_tolerance(receipt_item_a, receipt_vendor_a, tenant=tenant_a)

    assert rule == receipt_policy_category_a
    assert "category rule" in reason


def test_receipt_resolver_reads_the_category_off_the_item_when_none_is_passed(
        tenant_a, receipt_vendor_a, receipt_item_a, receipt_policy_category_a):
    """The register omits ``category=`` on purpose - ``item.category_id`` is already loaded."""
    rule, _reason = resolve_receipt_tolerance(receipt_item_a, receipt_vendor_a, tenant=tenant_a)
    assert rule == receipt_policy_category_a


def test_receipt_resolver_matches_a_category_rule_with_no_item_at_all(
        tenant_a, receipt_vendor_a, receipt_category_a, receipt_policy_category_a):
    """PO lines are free text, so a line whose sku resolves to nothing must still be judged."""
    rule, reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a,
                                             category=receipt_category_a)

    assert rule == receipt_policy_category_a
    assert "category rule" in reason


def test_receipt_resolver_prefers_a_vendor_pinned_rule_at_the_same_tier(
        tenant_a, receipt_vendor_a, receipt_policy_catchall_a, receipt_policy_vendor_a):
    rule, reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)

    assert rule == receipt_policy_vendor_a
    assert reason.endswith(", vendor-pinned")


def test_receipt_resolver_never_fires_a_vendor_rule_for_another_supplier(
        tenant_a, receipt_vendor_other_a, receipt_policy_catchall_a, receipt_policy_vendor_a):
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_other_a, tenant=tenant_a)
    assert rule == receipt_policy_catchall_a


def test_receipt_resolver_never_fires_a_vendor_rule_for_an_unknown_supplier(
        tenant_a, receipt_policy_vendor_a):
    rule, reason = resolve_receipt_tolerance(None, None, tenant=tenant_a)

    assert rule is None
    assert reason == ("No Rule Matched — no active tolerance policy covers "
                      "this line.")


def test_receipt_resolver_accepts_a_raw_vendor_pk(tenant_a, receipt_vendor_a,
                                                  receipt_policy_vendor_a):
    """The coverage tile resolves off a ``values()`` row, so the vendor arrives as an id."""
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a.pk, tenant=tenant_a)
    assert rule == receipt_policy_vendor_a


def test_receipt_resolver_skips_an_inactive_rule_however_high_its_priority(
        tenant_a, receipt_vendor_a, receipt_policy_catchall_a, receipt_policy_inactive_a):
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)

    assert receipt_policy_inactive_a.priority < receipt_policy_catchall_a.priority
    assert rule == receipt_policy_catchall_a


def test_receipt_resolver_skips_an_inactive_rule_even_from_a_supplied_list(
        tenant_a, receipt_vendor_a, receipt_policy_catchall_a, receipt_policy_inactive_a):
    supplied = [receipt_policy_inactive_a, receipt_policy_catchall_a]
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a,
                                              rules=supplied)
    assert rule == receipt_policy_catchall_a


def test_receipt_resolver_breaks_a_tier_tie_on_the_lower_priority(tenant_a, receipt_vendor_a):
    _receipt_policy(tenant_a, name="Loose", priority=20)
    tight = _receipt_policy(tenant_a, name="Tight", priority=3)

    rule, reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)

    assert rule == tight
    assert "(priority 3)" in reason


def test_receipt_resolver_breaks_an_equal_priority_tie_on_the_lower_id(tenant_a,
                                                                      receipt_vendor_a):
    first = _receipt_policy(tenant_a, name="First in", priority=10)
    _receipt_policy(tenant_a, name="Second in", priority=10)

    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)
    assert rule == first


def test_receipt_resolver_refuses_without_any_tenant_context(receipt_policy_catchall_a):
    rule, reason = resolve_receipt_tolerance(None, None)

    assert rule is None
    assert reason == "No Rule Matched \u2014 no tenant context available."


def test_receipt_resolver_refuses_a_supplied_list_without_tenant_context(
        receipt_policy_catchall_a):
    """A caller-supplied list is never trusted for tenancy - refusal comes FIRST."""
    rule, reason = resolve_receipt_tolerance(None, None, rules=[receipt_policy_catchall_a])

    assert rule is None
    assert "no tenant context" in reason


def test_receipt_resolver_derives_the_tenant_from_the_item_when_none_is_passed(
        receipt_item_a, receipt_vendor_a, receipt_policy_catchall_a):
    rule, _reason = resolve_receipt_tolerance(receipt_item_a, receipt_vendor_a)
    assert rule == receipt_policy_catchall_a


def test_receipt_resolver_refilters_a_supplied_list_by_tenant(tenant_a, receipt_vendor_a,
                                                              receipt_policy_b):
    """A list is trusted for ORDER, never for TENANCY - B's rule must not judge A's line."""
    rule, reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a,
                                             rules=[receipt_policy_b])

    assert rule is None
    assert "no active tolerance policy" in reason


def test_receipt_resolver_never_reads_another_tenants_rule_from_the_database(
        tenant_a, receipt_vendor_a, receipt_policy_b):
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)
    assert rule is None


def test_receipt_resolver_issues_no_query_when_the_rules_are_supplied(
        tenant_a, receipt_vendor_a, receipt_policy_catchall_a, django_assert_num_queries):
    supplied = list(ReceiptTolerancePolicy.objects.filter(tenant=tenant_a))

    with django_assert_num_queries(0):
        rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a,
                                                  rules=supplied)
    assert rule == receipt_policy_catchall_a


def test_receipt_resolver_accepts_a_tenant_pk_as_well_as_an_instance(tenant_a, receipt_vendor_a,
                                                                     receipt_policy_catchall_a):
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a.pk)
    assert rule == receipt_policy_catchall_a


def test_receipt_resolver_full_hierarchy_falls_back_one_tier_at_a_time(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a, receipt_item_a, receipt_category_a,
        receipt_policy_catchall_a, receipt_policy_category_a, receipt_policy_item_a,
        receipt_policy_vendor_a, receipt_policy_inactive_a):
    item_rule, _r1 = resolve_receipt_tolerance(receipt_item_a, receipt_vendor_a, tenant=tenant_a)
    category_rule, _r2 = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a,
                                                   category=receipt_category_a)
    vendor_rule, _r3 = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)
    catchall, _r4 = resolve_receipt_tolerance(None, receipt_vendor_other_a, tenant=tenant_a)

    assert [item_rule, category_rule, vendor_rule, catchall] == [
        receipt_policy_item_a, receipt_policy_category_a, receipt_policy_vendor_a,
        receipt_policy_catchall_a]


# ================================================================================================
# 3. evaluate_receipt_tolerance - what the governing rule says about these figures
# ================================================================================================

def test_receipt_evaluator_answers_no_rule_without_a_policy():
    verdict, reason = evaluate_receipt_tolerance(None, ordered_quantity=Decimal("10"),
                                                 received_quantity=Decimal("99"))
    assert (verdict, reason) == ("no_rule", "No policy covers this line.")


def test_receipt_evaluator_accepts_a_delivery_inside_every_band():
    rule = _receipt_unsaved_policy(name="Catch", over_receipt_pct=Decimal("5"),
                                   under_receipt_pct=Decimal("10"))
    verdict, reason = evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                                 received_quantity=Decimal("105"))

    assert verdict == "ok"
    assert reason == "Within the bands set by 'Catch'."


def test_receipt_evaluator_flags_an_over_receipt_past_the_percentage_ceiling():
    rule = _receipt_unsaved_policy(name="Catch", over_receipt_pct=Decimal("5"))
    verdict, reason = evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                                 received_quantity=Decimal("106"))

    assert verdict == "over"
    assert "over the 105 ceiling" in reason
    assert "'Catch'" in reason


def test_receipt_evaluator_treats_a_missing_over_band_as_zero_tolerance():
    rule = _receipt_unsaved_policy(name="Zero", under_receipt_pct=Decimal("10"))
    verdict, reason = evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("10"),
                                                 received_quantity=Decimal("10.5"))

    assert verdict == "over"
    assert "over the 10 ceiling" in reason


def test_receipt_evaluator_takes_the_more_restrictive_of_two_over_bands():
    rule = _receipt_unsaved_policy(name="Both", over_receipt_pct=Decimal("50"),
                                   over_receipt_qty=Decimal("2"))

    assert evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("10"),
                                      received_quantity=Decimal("12"))[0] == "ok"
    verdict, reason = evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("10"),
                                                 received_quantity=Decimal("13"))
    assert verdict == "over"
    assert "over the 12 ceiling" in reason


def test_receipt_evaluator_honours_an_absolute_over_band_on_its_own():
    rule = _receipt_unsaved_policy(name="Two spare", over_receipt_qty=Decimal("2"))

    assert evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                      received_quantity=Decimal("102"))[0] == "ok"
    assert evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                      received_quantity=Decimal("103"))[0] == "over"


def test_receipt_evaluator_never_flags_an_over_receipt_under_the_unlimited_flag():
    rule = _receipt_unsaved_policy(name="Unl", over_receipt_pct=Decimal("0"),
                                   allow_unlimited_over_receipt=True)
    verdict, _reason = evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("10"),
                                                  received_quantity=Decimal("9999"))
    assert verdict == "ok"


def test_receipt_evaluator_unlimited_flag_short_circuits_over_receipt_only():
    """The escape flag forgives quantity, never lateness."""
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Unl", allow_unlimited_over_receipt=True,
                                   late_receipt_days=1)
    verdict, reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("10"), received_quantity=Decimal("999"),
        expected_date=today, receipt_date=today + _receipt_days(5))

    assert verdict == "late"
    assert "5 days late" in reason


def test_receipt_evaluator_flags_a_short_shipment_below_the_floor():
    rule = _receipt_unsaved_policy(name="Catch", under_receipt_pct=Decimal("10"))
    verdict, reason = evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                                 received_quantity=Decimal("89"))

    assert verdict == "short"
    assert "below the 90 floor" in reason


def test_receipt_evaluator_accepts_a_shortfall_exactly_on_the_floor():
    rule = _receipt_unsaved_policy(name="Catch", under_receipt_pct=Decimal("10"))
    assert evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                      received_quantity=Decimal("90"))[0] == "ok"


def test_receipt_evaluator_never_judges_a_shortfall_without_an_under_band():
    rule = _receipt_unsaved_policy(name="Over only", over_receipt_pct=Decimal("5"))
    assert evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                      received_quantity=Decimal("1"))[0] == "ok"


def test_receipt_evaluator_flags_an_early_arrival_past_the_allowance():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Catch", early_receipt_days=2)
    verdict, reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("10"), received_quantity=Decimal("10"),
        expected_date=today, receipt_date=today - _receipt_days(3))

    assert verdict == "early"
    assert "Arrived 3 days early" in reason
    assert "allows 2 days" in reason


def test_receipt_evaluator_accepts_an_early_arrival_inside_the_allowance():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Catch", early_receipt_days=2)
    verdict, _reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("10"), received_quantity=Decimal("10"),
        expected_date=today, receipt_date=today - _receipt_days(2))
    assert verdict == "ok"


def test_receipt_evaluator_flags_a_late_arrival_past_the_allowance():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Catch", late_receipt_days=3)
    verdict, reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("10"), received_quantity=Decimal("10"),
        expected_date=today, receipt_date=today + _receipt_days(4))

    assert verdict == "late"
    assert "Arrived 4 days late" in reason


def test_receipt_evaluator_ignores_dates_when_the_rule_sets_no_date_band():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Quantities only", over_receipt_pct=Decimal("5"))
    verdict, _reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("10"), received_quantity=Decimal("10"),
        expected_date=today, receipt_date=today + _receipt_days(40))
    assert verdict == "ok"


def test_receipt_evaluator_ignores_dates_when_either_side_is_missing():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Dates", early_receipt_days=0, late_receipt_days=0)

    assert evaluate_receipt_tolerance(rule, ordered_quantity=1, received_quantity=1,
                                      expected_date=None,
                                      receipt_date=today + _receipt_days(9))[0] == "ok"
    assert evaluate_receipt_tolerance(rule, ordered_quantity=1, received_quantity=1,
                                      expected_date=today, receipt_date=None)[0] == "ok"


def test_receipt_evaluator_lets_a_quantity_breach_outrank_a_date_breach():
    """A short shipment that also arrived late is reported as SHORT - that is the chase."""
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Catch", under_receipt_pct=Decimal("10"),
                                   late_receipt_days=1)
    verdict, reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("100"), received_quantity=Decimal("50"),
        expected_date=today, receipt_date=today + _receipt_days(9))

    assert verdict == "short"
    assert "late" not in reason


def test_receipt_evaluator_still_judges_dates_when_the_quantity_is_inside_its_band():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Catch", over_receipt_pct=Decimal("5"),
                                   late_receipt_days=1)
    verdict, _reason = evaluate_receipt_tolerance(
        rule, ordered_quantity=Decimal("100"), received_quantity=Decimal("104"),
        expected_date=today, receipt_date=today + _receipt_days(4))
    assert verdict == "late"


def test_receipt_evaluator_reads_missing_quantities_as_zero():
    rule = _receipt_unsaved_policy(name="Catch", under_receipt_pct=Decimal("10"))

    assert evaluate_receipt_tolerance(rule, ordered_quantity=Decimal("100"),
                                      received_quantity=None)[0] == "short"
    assert evaluate_receipt_tolerance(rule, ordered_quantity=None,
                                      received_quantity=None)[0] == "ok"


def test_receipt_evaluator_only_ever_returns_the_documented_vocabulary():
    today = _receipt_today()
    rule = _receipt_unsaved_policy(name="Every axis", over_receipt_pct=Decimal("5"),
                                   under_receipt_pct=Decimal("10"), early_receipt_days=1,
                                   late_receipt_days=1)
    seen = {
        evaluate_receipt_tolerance(None, ordered_quantity=1, received_quantity=1)[0],
        evaluate_receipt_tolerance(rule, ordered_quantity=100, received_quantity=100)[0],
        evaluate_receipt_tolerance(rule, ordered_quantity=100, received_quantity=200)[0],
        evaluate_receipt_tolerance(rule, ordered_quantity=100, received_quantity=1)[0],
        evaluate_receipt_tolerance(rule, ordered_quantity=1, received_quantity=1,
                                   expected_date=today,
                                   receipt_date=today - _receipt_days(5))[0],
        evaluate_receipt_tolerance(rule, ordered_quantity=1, received_quantity=1,
                                   expected_date=today,
                                   receipt_date=today + _receipt_days(5))[0],
    }

    assert seen == {v for v, _ in ReceiptTolerancePolicy.VERDICT_CHOICES}


def test_receipt_evaluator_judges_a_saved_rule_the_same_after_a_db_round_trip(
        tenant_a, receipt_policy_catchall_a):
    reloaded = ReceiptTolerancePolicy.objects.get(pk=receipt_policy_catchall_a.pk)
    assert evaluate_receipt_tolerance(reloaded, ordered_quantity=Decimal("10"),
                                      received_quantity=Decimal("12"))[0] == "over"


# ================================================================================================
# 4. resolve_line_item - the free-text sku_hint -> scm.Item bridge
# ================================================================================================

def test_receipt_resolve_line_item_finds_the_item_behind_a_free_text_sku(
        tenant_a, receipt_item_a, receipt_po_line_a):
    assert receipt_po_line_a.sku_hint == "BRG-40"
    assert resolve_line_item(tenant_a, receipt_po_line_a) == receipt_item_a


def test_receipt_resolve_line_item_matches_case_insensitively(tenant_a, receipt_item_a,
                                                              receipt_po_line_a):
    receipt_po_line_a.sku_hint = "brg-40"
    assert resolve_line_item(tenant_a, receipt_po_line_a) == receipt_item_a


def test_receipt_resolve_line_item_trims_surrounding_whitespace(tenant_a, receipt_item_a,
                                                                receipt_po_line_a):
    receipt_po_line_a.sku_hint = "  BRG-40  "
    assert resolve_line_item(tenant_a, receipt_po_line_a) == receipt_item_a


def test_receipt_resolve_line_item_returns_none_without_a_tenant(receipt_item_a,
                                                                 receipt_po_line_a):
    assert resolve_line_item(None, receipt_po_line_a) is None


def test_receipt_resolve_line_item_returns_none_without_a_line(tenant_a, receipt_item_a):
    assert resolve_line_item(tenant_a, None) is None


def test_receipt_resolve_line_item_returns_none_for_a_blank_hint(tenant_a, receipt_item_a,
                                                                 receipt_po_line_a):
    receipt_po_line_a.sku_hint = "   "
    assert resolve_line_item(tenant_a, receipt_po_line_a) is None


def test_receipt_resolve_line_item_returns_none_when_nothing_matches(tenant_a, receipt_item_a,
                                                                     receipt_po_line2_a):
    assert receipt_po_line2_a.sku_hint == "BLT-1200"
    assert resolve_line_item(tenant_a, receipt_po_line2_a) is None


def test_receipt_resolve_line_item_never_crosses_a_tenant_boundary(tenant_a, tenant_b,
                                                                   receipt_item_b,
                                                                   receipt_po_line_b):
    from apps.scm.models import Item

    twin = Item.objects.create(tenant=tenant_a, sku="GBX-SPN", name="Acme lookalike",
                               item_type="stock")

    # The same free-text hint resolves to a DIFFERENT item in each workspace, never across.
    assert resolve_line_item(tenant_a, receipt_po_line_b) == twin
    assert resolve_line_item(tenant_b, receipt_po_line_b) == receipt_item_b


# ================================================================================================
# 5. ReceiptDiscrepancy - defaults, numbering, choices
# ================================================================================================

def test_receipt_discrepancy_minimal_create_takes_every_documented_default(tenant_a,
                                                                          receipt_grn_a):
    finding = ReceiptDiscrepancy.objects.create(
        tenant=tenant_a, goods_receipt=receipt_grn_a, kind="short_shipment",
        description="Three cartons short.", quantity_affected=Decimal("2"))

    assert finding.status == "open"
    assert finding.severity == "minor"
    assert finding.remedy == "pending"
    assert finding.goods_receipt_line_id is None
    assert finding.item_description == ""
    assert finding.sku_hint == ""
    assert finding.lot_number == "" and finding.serial_number == ""
    assert finding.expiry_date is None
    assert not finding.evidence
    assert finding.evidence_url == ""
    assert finding.vendor_notified_on is None
    assert finding.vendor_reference == ""
    assert finding.resolved_at is None
    assert finding.resolved_by_id is None
    assert finding.resolution_notes == ""
    assert finding.nonconformance_id is None
    assert finding.quarantine_order_id is None
    assert finding.return_to_vendor_id is None
    assert finding.created_by_id is None


def test_receipt_discrepancy_number_is_blank_until_saved(tenant_a, receipt_grn_a):
    unsaved = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 kind="documentation", description="No packing list.")
    assert unsaved.number == ""

    unsaved.save()
    assert unsaved.number == "RDS-00001"


def test_receipt_discrepancy_number_uses_the_rds_prefix_and_five_digit_padding(tenant_a,
                                                                              receipt_grn_a):
    assert ReceiptDiscrepancy.NUMBER_PREFIX == "RDS"
    numbers = [_receipt_discrepancy(tenant_a, receipt_grn_a).number for _ in range(3)]
    assert numbers == ["RDS-00001", "RDS-00002", "RDS-00003"]


def test_receipt_discrepancy_numbers_do_not_collide_across_tenants(tenant_a, tenant_b,
                                                                   receipt_grn_a, receipt_grn_b):
    a_one = _receipt_discrepancy(tenant_a, receipt_grn_a)
    b_one = _receipt_discrepancy(tenant_b, receipt_grn_b)
    a_two = _receipt_discrepancy(tenant_a, receipt_grn_a)

    assert a_one.number == "RDS-00001"
    assert b_one.number == "RDS-00001"      # tenant B restarts its own sequence
    assert a_two.number == "RDS-00002"
    assert b_one.tenant_id == tenant_b.pk


def test_receipt_discrepancy_number_is_assigned_once_and_never_reminted(
        receipt_discrepancy_open_a):
    first = receipt_discrepancy_open_a.number
    receipt_discrepancy_open_a.description = "Edited."
    receipt_discrepancy_open_a.save()

    assert receipt_discrepancy_open_a.number == first


def test_receipt_discrepancy_str_folds_its_number_and_the_receipt(receipt_discrepancy_open_a):
    expected = "%s %s %s" % (receipt_discrepancy_open_a.number, _RECEIPT_DOT,
                             receipt_discrepancy_open_a.goods_receipt.number)
    assert str(receipt_discrepancy_open_a) == expected


def test_receipt_discrepancy_kind_choices_are_the_seven_documented_values():
    assert _receipt_choice_values(ReceiptDiscrepancy.KIND_CHOICES) == [
        "over_shipment", "short_shipment", "damaged", "wrong_item", "quality_failure",
        "documentation", "late_delivery"]


def test_receipt_discrepancy_severity_remedy_and_status_choices():
    assert _receipt_choice_values(ReceiptDiscrepancy.SEVERITY_CHOICES) == [
        "minor", "major", "critical"]
    assert _receipt_choice_values(ReceiptDiscrepancy.REMEDY_CHOICES) == [
        "pending", "replacement", "credit", "rtv", "accept_as_is", "scrap"]
    assert _receipt_choice_values(ReceiptDiscrepancy.STATUS_CHOICES) == [
        "open", "vendor_notified", "resolved", "cancelled"]


def test_receipt_discrepancy_status_and_quantity_kind_tuples_are_subsets_of_the_choices():
    values = {v for v, _ in ReceiptDiscrepancy.STATUS_CHOICES}
    kinds = {v for v, _ in ReceiptDiscrepancy.KIND_CHOICES}

    assert ReceiptDiscrepancy.OPEN_STATUSES == ("open", "vendor_notified")
    assert set(ReceiptDiscrepancy.OPEN_STATUSES) <= values
    assert ReceiptDiscrepancy.QUANTITY_KINDS == (
        "over_shipment", "short_shipment", "damaged", "wrong_item")
    assert set(ReceiptDiscrepancy.QUANTITY_KINDS) <= kinds
    assert ReceiptDiscrepancy.IMAGE_SUFFIXES == (".png", ".jpg", ".jpeg", ".gif", ".webp")


def test_receipt_discrepancy_badge_maps_use_colour_named_classes_only():
    for mapping in (ReceiptDiscrepancy.STATUS_CSS, ReceiptDiscrepancy.SEVERITY_CSS,
                    ReceiptDiscrepancy.KIND_CSS, ReceiptDiscrepancy.REMEDY_CSS):
        assert set(mapping.values()) <= _RECEIPT_BADGE_COLOURS


def test_receipt_discrepancy_badge_maps_cover_every_choice_value():
    assert set(ReceiptDiscrepancy.STATUS_CSS) == {
        v for v, _ in ReceiptDiscrepancy.STATUS_CHOICES}
    assert set(ReceiptDiscrepancy.SEVERITY_CSS) == {
        v for v, _ in ReceiptDiscrepancy.SEVERITY_CHOICES}
    assert set(ReceiptDiscrepancy.KIND_CSS) == {v for v, _ in ReceiptDiscrepancy.KIND_CHOICES}
    assert set(ReceiptDiscrepancy.REMEDY_CSS) == {
        v for v, _ in ReceiptDiscrepancy.REMEDY_CHOICES}


def test_receipt_discrepancy_workflow_columns_are_not_editable():
    """A crafted POST must not be able to jump a finding straight to resolved (L22)."""
    for name in ("number", "status", "vendor_notified_on", "resolved_at", "resolved_by",
                 "resolution_notes"):
        assert ReceiptDiscrepancy._meta.get_field(name).editable is False


def test_receipt_discrepancy_meta_ordering_unique_together_and_indexes():
    assert ReceiptDiscrepancy._meta.ordering == ["-created_at", "-id"]
    assert ReceiptDiscrepancy._meta.unique_together == (("tenant", "number"),)
    names = {index.name for index in ReceiptDiscrepancy._meta.indexes}
    assert {"prc_rds_tnt_status_idx", "prc_rds_tnt_kind_idx", "prc_rds_tnt_grn_idx"} <= names


def test_receipt_discrepancy_unique_together_with_tenant_is_enforced(tenant_a, receipt_grn_a,
                                                                    receipt_discrepancy_open_a):
    twin = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                              number=receipt_discrepancy_open_a.number, kind="documentation",
                              description="Duplicate number.")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            twin.save()


def test_receipt_discrepancy_the_same_number_is_free_in_another_tenant(
        tenant_b, receipt_grn_b, receipt_discrepancy_open_a):
    twin = ReceiptDiscrepancy.objects.create(
        tenant=tenant_b, goods_receipt=receipt_grn_b,
        number=receipt_discrepancy_open_a.number, kind="documentation",
        description="Same number, different workspace.")

    assert twin.number == receipt_discrepancy_open_a.number
    assert twin.pk != receipt_discrepancy_open_a.pk


def test_receipt_discrepancy_protects_the_receipt_it_points_at(receipt_discrepancy_open_a):
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        with transaction.atomic():
            receipt_discrepancy_open_a.goods_receipt.delete()


# ------------------------------------------------------------------ discrepancy clean()

def test_receipt_discrepancy_clean_rejects_a_cross_tenant_receipt(tenant_a, receipt_grn_b):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_b,
                                 kind="documentation", description="Not ours.")
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["goods_receipt"])


def test_receipt_discrepancy_clean_rejects_a_line_from_a_different_receipt(
        tenant_a, receipt_grn_a, receipt_grn_line_b):
    """``scm.GoodsReceiptLine`` has no tenant column - the guard is 'must belong to THIS receipt'."""
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 goods_receipt_line=receipt_grn_line_b, kind="documentation",
                                 description="Crafted line pk.")
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "different receipt" in " ".join(excinfo.value.message_dict["goods_receipt_line"])


def test_receipt_discrepancy_clean_rejects_a_same_tenant_line_from_another_receipt(
        tenant_a, receipt_grn_a, receipt_grn_early_a):
    stray = receipt_grn_early_a.lines.first()
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 goods_receipt_line=stray, kind="documentation",
                                 description="Wrong receipt.")
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "goods_receipt_line" in excinfo.value.message_dict


def test_receipt_discrepancy_clean_rejects_a_cross_tenant_nonconformance(
        tenant_a, receipt_grn_a, receipt_nonconformance_b):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 kind="quality_failure", description="Escalated.",
                                 nonconformance=receipt_nonconformance_b)
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["nonconformance"])


def test_receipt_discrepancy_clean_rejects_a_cross_tenant_quarantine_order(
        tenant_a, receipt_grn_a, receipt_quarantine_b):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 kind="quality_failure", description="Held.",
                                 quarantine_order=receipt_quarantine_b)
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["quarantine_order"])


def test_receipt_discrepancy_clean_rejects_a_cross_tenant_return_to_vendor(
        tenant_a, receipt_grn_a, receipt_rtv_b):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 kind="damaged", quantity_affected=Decimal("1"),
                                 description="Going back.", return_to_vendor=receipt_rtv_b)
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["return_to_vendor"])


@pytest.mark.parametrize("kind", ["over_shipment", "short_shipment", "damaged", "wrong_item"])
def test_receipt_discrepancy_clean_demands_a_figure_for_every_quantity_kind(
        tenant_a, receipt_grn_a, kind):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a, kind=kind,
                                 quantity_affected=Decimal("0"), description="How many?")
    with pytest.raises(ValidationError) as excinfo:
        finding.full_clean()
    assert "quantity_affected" in excinfo.value.message_dict


@pytest.mark.parametrize("kind", ["quality_failure", "documentation", "late_delivery"])
def test_receipt_discrepancy_clean_allows_a_zero_figure_for_a_non_quantity_kind(
        tenant_a, receipt_grn_a, kind):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a, kind=kind,
                                 quantity_affected=Decimal("0"),
                                 description="Nothing to count here.")
    finding.full_clean()        # must not raise


def test_receipt_discrepancy_clean_accepts_a_header_level_finding(tenant_a, receipt_grn_a):
    finding = ReceiptDiscrepancy(tenant=tenant_a, goods_receipt=receipt_grn_a,
                                 kind="documentation",
                                 description="No packing list with the delivery.")
    finding.full_clean()        # must not raise
    assert finding.goods_receipt_line_id is None


# ------------------------------------------------------------------ discrepancy save() mirroring

def test_receipt_discrepancy_save_mirrors_the_free_text_off_the_receipt_line(
        tenant_a, receipt_grn_a, receipt_grn_line_a, receipt_po_line_a):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a,
                                   goods_receipt_line=receipt_grn_line_a, kind="damaged",
                                   quantity_affected=Decimal("1"))

    assert finding.item_description == receipt_po_line_a.item_description
    assert finding.sku_hint == receipt_po_line_a.sku_hint == "BRG-40"


def test_receipt_discrepancy_save_never_overwrites_text_the_buyer_typed(
        tenant_a, receipt_grn_a, receipt_grn_line_a):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a,
                                   goods_receipt_line=receipt_grn_line_a, kind="damaged",
                                   quantity_affected=Decimal("1"),
                                   item_description="Bearing, the SMALL one",
                                   sku_hint="BRG-40-ALT")

    assert finding.item_description == "Bearing, the SMALL one"
    assert finding.sku_hint == "BRG-40-ALT"


def test_receipt_discrepancy_save_leaves_a_header_level_finding_blank(receipt_discrepancy_header_a):
    assert receipt_discrepancy_header_a.goods_receipt_line_id is None
    assert receipt_discrepancy_header_a.item_description == ""
    assert receipt_discrepancy_header_a.sku_hint == ""


def test_receipt_discrepancy_save_skips_mirroring_on_a_targeted_update_fields_write(
        tenant_a, receipt_grn_a, receipt_grn_line_a, admin_user):
    """Every verb writes ``update_fields``; recomputing the mirror there would cost a query to
    persist nothing."""
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a,
                                   goods_receipt_line=receipt_grn_line_a, kind="damaged",
                                   quantity_affected=Decimal("1"))
    mirrored = finding.item_description
    assert mirrored

    finding.item_description = ""
    assert finding.notify_vendor(admin_user, reference="SUP-1") is True

    assert finding.item_description == ""                       # not recomputed in memory
    reloaded = ReceiptDiscrepancy.objects.get(pk=finding.pk)
    assert reloaded.item_description == mirrored                # and not written away either


# ------------------------------------------------------------------ discrepancy verbs

def test_receipt_discrepancy_notify_vendor_stamps_the_supplier_conversation(
        receipt_discrepancy_open_a, admin_user):
    assert receipt_discrepancy_open_a.notify_vendor(admin_user, reference="SUP-CASE-9") is True

    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "vendor_notified"
    assert receipt_discrepancy_open_a.vendor_reference == "SUP-CASE-9"
    assert receipt_discrepancy_open_a.vendor_notified_on == _receipt_today()


def test_receipt_discrepancy_notify_vendor_accepts_an_explicit_date(receipt_discrepancy_open_a,
                                                                    admin_user):
    yesterday = _receipt_today() - _receipt_days(1)
    assert receipt_discrepancy_open_a.notify_vendor(admin_user, notified_on=yesterday) is True
    assert receipt_discrepancy_open_a.vendor_notified_on == yesterday


def test_receipt_discrepancy_notify_vendor_is_a_no_op_on_a_double_submit(
        receipt_discrepancy_notified_a, admin_user):
    stamped = receipt_discrepancy_notified_a.vendor_notified_on
    reference = receipt_discrepancy_notified_a.vendor_reference

    assert receipt_discrepancy_notified_a.notify_vendor(admin_user, reference="SECOND") is False

    receipt_discrepancy_notified_a.refresh_from_db()
    assert receipt_discrepancy_notified_a.vendor_notified_on == stamped
    assert receipt_discrepancy_notified_a.vendor_reference == reference


def test_receipt_discrepancy_notify_vendor_keeps_a_reference_the_buyer_already_typed(
        tenant_a, receipt_grn_a, admin_user):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a, vendor_reference="TYPED-1")

    assert finding.notify_vendor(admin_user, reference="") is True
    assert finding.vendor_reference == "TYPED-1"


def test_receipt_discrepancy_notify_vendor_truncates_an_over_long_reference(
        receipt_discrepancy_open_a, admin_user):
    receipt_discrepancy_open_a.notify_vendor(admin_user, reference="R" * 200)
    assert len(receipt_discrepancy_open_a.vendor_reference) == 64


def test_receipt_discrepancy_notify_vendor_is_refused_once_resolved(
        receipt_discrepancy_resolved_a, admin_user):
    assert receipt_discrepancy_resolved_a.notify_vendor(admin_user, reference="LATE") is False
    assert receipt_discrepancy_resolved_a.status == "resolved"
    assert receipt_discrepancy_resolved_a.vendor_notified_on is None


def test_receipt_discrepancy_resolve_closes_an_open_finding_with_a_remedy(
        receipt_discrepancy_open_a, admin_user):
    before = timezone.now()
    assert receipt_discrepancy_open_a.resolve(admin_user, "credit", "Credit agreed.") is True

    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "resolved"
    assert receipt_discrepancy_open_a.remedy == "credit"
    assert receipt_discrepancy_open_a.resolution_notes == "Credit agreed."
    assert receipt_discrepancy_open_a.resolved_by_id == admin_user.pk
    assert receipt_discrepancy_open_a.resolved_at >= before


def test_receipt_discrepancy_resolve_works_from_vendor_notified(
        receipt_discrepancy_notified_a, admin_user):
    assert receipt_discrepancy_notified_a.status == "vendor_notified"
    assert receipt_discrepancy_notified_a.resolve(admin_user, "replacement", "Re-shipped.") is True
    assert receipt_discrepancy_notified_a.status == "resolved"


def test_receipt_discrepancy_resolve_ignores_a_remedy_outside_the_vocabulary(
        receipt_discrepancy_open_a, admin_user):
    """A crafted POST must not store a remedy that renders as a blank badge."""
    assert receipt_discrepancy_open_a.remedy == "pending"
    assert receipt_discrepancy_open_a.resolve(admin_user, "free-beer", "Odd remedy.") is True

    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.remedy == "pending"
    assert receipt_discrepancy_open_a.status == "resolved"


def test_receipt_discrepancy_resolve_truncates_the_notes_to_two_thousand_characters(
        receipt_discrepancy_open_a, admin_user):
    receipt_discrepancy_open_a.resolve(admin_user, "credit", "n" * 5000)
    assert len(receipt_discrepancy_open_a.resolution_notes) == 2000


def test_receipt_discrepancy_resolve_accepts_a_missing_actor(receipt_discrepancy_open_a):
    assert receipt_discrepancy_open_a.resolve(None, "scrap", "Scrapped on the dock.") is True
    assert receipt_discrepancy_open_a.resolved_by_id is None


def test_receipt_discrepancy_resolve_is_a_no_op_on_a_double_submit(
        receipt_discrepancy_resolved_a, member_user):
    stamped = receipt_discrepancy_resolved_a.resolved_at
    remedy = receipt_discrepancy_resolved_a.remedy

    assert receipt_discrepancy_resolved_a.resolve(member_user, "scrap", "Second try.") is False

    receipt_discrepancy_resolved_a.refresh_from_db()
    assert receipt_discrepancy_resolved_a.resolved_at == stamped
    assert receipt_discrepancy_resolved_a.remedy == remedy


def test_receipt_discrepancy_cancel_withdraws_an_open_finding(receipt_discrepancy_open_a,
                                                              admin_user):
    assert receipt_discrepancy_open_a.cancel(admin_user, "Mis-count on the dock.") is True

    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "cancelled"
    assert receipt_discrepancy_open_a.resolution_notes == "Mis-count on the dock."
    assert receipt_discrepancy_open_a.resolved_by_id == admin_user.pk


def test_receipt_discrepancy_cancel_needs_no_essay(receipt_discrepancy_open_a, admin_user):
    assert receipt_discrepancy_open_a.cancel(admin_user) is True
    assert receipt_discrepancy_open_a.resolution_notes == ""


def test_receipt_discrepancy_cancel_works_from_vendor_notified(receipt_discrepancy_notified_a,
                                                               admin_user):
    assert receipt_discrepancy_notified_a.cancel(admin_user, "Folded into RDS-2.") is True
    assert receipt_discrepancy_notified_a.status == "cancelled"


def test_receipt_discrepancy_cancel_is_refused_once_resolved(receipt_discrepancy_resolved_a,
                                                             admin_user):
    """A resolved finding is a record of what was agreed, not a decision to take back."""
    assert receipt_discrepancy_resolved_a.cancel(admin_user, "Changed my mind.") is False
    assert receipt_discrepancy_resolved_a.status == "resolved"


def test_receipt_discrepancy_every_verb_is_refused_once_cancelled(receipt_discrepancy_open_a,
                                                                  admin_user):
    receipt_discrepancy_open_a.cancel(admin_user, "Mis-count.")

    assert receipt_discrepancy_open_a.notify_vendor(admin_user, reference="X") is False
    assert receipt_discrepancy_open_a.resolve(admin_user, "credit", "X") is False
    assert receipt_discrepancy_open_a.cancel(admin_user, "X") is False
    assert receipt_discrepancy_open_a.status == "cancelled"


# ------------------------------------------------------------------ discrepancy derived reads

def test_receipt_discrepancy_order_and_vendor_are_read_through_the_receipt(
        receipt_discrepancy_open_a, receipt_po_a, receipt_vendor_a):
    assert receipt_discrepancy_open_a.order == receipt_po_a
    assert receipt_discrepancy_open_a.vendor == receipt_vendor_a


def test_receipt_discrepancy_vendor_is_never_a_stored_copy():
    names = _receipt_field_names(ReceiptDiscrepancy)
    for derived in ("order", "vendor", "is_open", "has_evidence", "evidence_is_image",
                    "status_css", "severity_css", "kind_css", "remedy_css"):
        assert derived not in names


def test_receipt_discrepancy_vendor_follows_the_order_without_a_save(
        receipt_discrepancy_open_a, receipt_vendor_other_a):
    order = receipt_discrepancy_open_a.order
    order.vendor = receipt_vendor_other_a
    order.save(update_fields=["vendor"])

    reloaded = ReceiptDiscrepancy.objects.get(pk=receipt_discrepancy_open_a.pk)
    assert reloaded.vendor == receipt_vendor_other_a


def test_receipt_discrepancy_is_open_tracks_the_two_live_statuses(
        receipt_discrepancy_open_a, receipt_discrepancy_notified_a,
        receipt_discrepancy_resolved_a, admin_user):
    assert receipt_discrepancy_open_a.is_open is True
    assert receipt_discrepancy_notified_a.is_open is True
    assert receipt_discrepancy_resolved_a.is_open is False

    receipt_discrepancy_open_a.cancel(admin_user)
    assert receipt_discrepancy_open_a.is_open is False


def test_receipt_discrepancy_has_evidence_counts_a_link_as_well_as_a_file(
        tenant_a, receipt_grn_a):
    bare = _receipt_discrepancy(tenant_a, receipt_grn_a)
    linked = _receipt_discrepancy(tenant_a, receipt_grn_a,
                                  evidence_url="https://example.test/photo.jpg")
    filed = _receipt_discrepancy(tenant_a, receipt_grn_a,
                                 evidence="procurement/receipt_evidence/2026/08/pallet.pdf")

    assert bare.has_evidence is False
    assert linked.has_evidence is True
    assert filed.has_evidence is True


def test_receipt_discrepancy_has_evidence_ignores_a_whitespace_only_link(tenant_a,
                                                                        receipt_grn_a):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a, evidence_url="   ")
    assert finding.has_evidence is False


@pytest.mark.parametrize("name,expected", [
    ("procurement/receipt_evidence/2026/08/pallet.png", True),
    ("procurement/receipt_evidence/2026/08/pallet.JPG", True),
    ("procurement/receipt_evidence/2026/08/pallet.jpeg", True),
    ("procurement/receipt_evidence/2026/08/pallet.gif", True),
    ("procurement/receipt_evidence/2026/08/pallet.webp", True),
    ("procurement/receipt_evidence/2026/08/pallet.pdf", False),
])
def test_receipt_discrepancy_evidence_is_image_only_for_the_documented_suffixes(
        tenant_a, receipt_grn_a, name, expected):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a, evidence=name)
    assert finding.evidence_is_image is expected


def test_receipt_discrepancy_evidence_is_image_is_false_without_a_file(tenant_a, receipt_grn_a):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a,
                                   evidence_url="https://example.test/x.png")
    assert finding.evidence_is_image is False


def test_receipt_discrepancy_badge_properties_read_the_maps(tenant_a, receipt_grn_a, admin_user):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a, severity="critical", kind="damaged",
                                   quantity_affected=Decimal("1"), remedy="rtv")

    assert finding.status_css == "badge-amber"
    assert finding.severity_css == "badge-red"
    assert finding.kind_css == "badge-red"
    assert finding.remedy_css == "badge-amber"

    finding.resolve(admin_user, "credit", "Done.")
    assert finding.status_css == "badge-green"
    assert finding.remedy_css == "badge-info"


def test_receipt_discrepancy_badge_properties_fall_back_to_slate_on_junk(tenant_a,
                                                                        receipt_grn_a):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a)
    finding.status = "not-a-status"
    finding.severity = "not-a-severity"
    finding.kind = "not-a-kind"
    finding.remedy = "not-a-remedy"

    assert finding.status_css == "badge-slate"
    assert finding.severity_css == "badge-slate"
    assert finding.kind_css == "badge-slate"
    assert finding.remedy_css == "badge-slate"


# ================================================================================================
# 6. ReturnToVendor - defaults, numbering, choices
# ================================================================================================

def test_receipt_rtv_minimal_create_takes_every_documented_default(tenant_a, receipt_vendor_a):
    rtv = ReturnToVendor.objects.create(tenant=tenant_a, vendor=receipt_vendor_a,
                                        reason="damaged")

    assert rtv.status == "draft"
    assert rtv.remedy == "credit"
    assert rtv.purchase_order_id is None
    assert rtv.goods_receipt_id is None
    assert rtv.discrepancy_id is None
    assert rtv.reason_note == ""
    assert rtv.supplier_rma_number == ""
    assert rtv.carrier_name == "" and rtv.tracking_number == ""
    assert rtv.shipped_on is None
    assert rtv.expected_return_date is None
    assert rtv.credit_note_ref == ""
    assert rtv.authorized_by_id is None and rtv.authorized_at is None
    assert rtv.closed_at is None and rtv.cancelled_at is None
    assert rtv.cancellation_reason == ""
    assert rtv.created_by_id is None
    assert rtv.notes == ""


def test_receipt_rtv_number_is_blank_until_saved(tenant_a, receipt_vendor_a):
    unsaved = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="damaged")
    assert unsaved.number == ""

    unsaved.save()
    assert unsaved.number == "RTV-00001"


def test_receipt_rtv_number_uses_the_rtv_prefix_and_five_digit_padding(tenant_a,
                                                                      receipt_vendor_a):
    assert ReturnToVendor.NUMBER_PREFIX == "RTV"
    numbers = [_receipt_rtv(tenant_a, receipt_vendor_a).number for _ in range(3)]
    assert numbers == ["RTV-00001", "RTV-00002", "RTV-00003"]


def test_receipt_rtv_numbers_do_not_collide_across_tenants(tenant_a, tenant_b, receipt_vendor_a,
                                                           receipt_vendor_b):
    a_one = _receipt_rtv(tenant_a, receipt_vendor_a)
    b_one = _receipt_rtv(tenant_b, receipt_vendor_b)
    a_two = _receipt_rtv(tenant_a, receipt_vendor_a)

    assert [a_one.number, b_one.number, a_two.number] == [
        "RTV-00001", "RTV-00001", "RTV-00002"]


def test_receipt_rtv_str_folds_its_number_and_the_supplier(receipt_rtv_draft_a,
                                                           receipt_vendor_a):
    expected = "%s %s %s" % (receipt_rtv_draft_a.number, _RECEIPT_DOT, receipt_vendor_a)
    assert str(receipt_rtv_draft_a) == expected


def test_receipt_rtv_reason_remedy_and_status_choices():
    assert _receipt_choice_values(ReturnToVendor.REASON_CHOICES) == [
        "damaged", "defective", "wrong_item", "over_shipment", "expired", "not_to_spec", "other"]
    assert _receipt_choice_values(ReturnToVendor.REMEDY_CHOICES) == [
        "credit", "replacement", "repair", "none"]
    assert _receipt_choice_values(ReturnToVendor.STATUS_CHOICES) == [
        "draft", "authorized", "shipped", "closed", "cancelled"]


def test_receipt_rtv_status_tuples_partition_the_lifecycle():
    values = {v for v, _ in ReturnToVendor.STATUS_CHOICES}
    assert ReturnToVendor.EDITABLE_STATUSES == ("draft",)
    assert ReturnToVendor.CANCELLABLE_STATUSES == ("draft", "authorized")
    assert set(ReturnToVendor.EDITABLE_STATUSES) <= values
    assert set(ReturnToVendor.CANCELLABLE_STATUSES) <= values


def test_receipt_rtv_badge_maps_use_colour_named_classes_and_cover_every_choice():
    for mapping in (ReturnToVendor.STATUS_CSS, ReturnToVendor.REASON_CSS,
                    ReturnToVendor.REMEDY_CSS):
        assert set(mapping.values()) <= _RECEIPT_BADGE_COLOURS
    assert set(ReturnToVendor.STATUS_CSS) == {v for v, _ in ReturnToVendor.STATUS_CHOICES}
    assert set(ReturnToVendor.REASON_CSS) == {v for v, _ in ReturnToVendor.REASON_CHOICES}
    assert set(ReturnToVendor.REMEDY_CSS) == {v for v, _ in ReturnToVendor.REMEDY_CHOICES}


def test_receipt_rtv_workflow_columns_are_not_editable():
    for name in ("number", "status", "shipped_on", "authorized_by", "authorized_at",
                 "closed_at", "cancelled_at", "cancellation_reason"):
        assert ReturnToVendor._meta.get_field(name).editable is False


def test_receipt_rtv_meta_ordering_unique_together_and_indexes():
    assert ReturnToVendor._meta.ordering == ["-created_at", "-id"]
    assert ReturnToVendor._meta.unique_together == (("tenant", "number"),)
    names = {index.name for index in ReturnToVendor._meta.indexes}
    assert {"prc_rtv_tnt_status_idx", "prc_rtv_tnt_vendor_idx", "prc_rtv_tnt_reason_idx",
            "prc_rtv_tnt_rma_idx"} <= names


def test_receipt_rtv_unique_together_with_tenant_is_enforced(tenant_a, receipt_vendor_a,
                                                             receipt_rtv_draft_a):
    twin = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="damaged",
                          number=receipt_rtv_draft_a.number)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            twin.save()


# ------------------------------------------------------------------ RTV clean()

def test_receipt_rtv_clean_rejects_a_cross_tenant_supplier(tenant_a, receipt_vendor_b):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_b, reason="damaged")
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["vendor"])


def test_receipt_rtv_clean_rejects_an_order_placed_with_a_different_supplier(
        tenant_a, receipt_vendor_other_a, receipt_po_a):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_other_a, reason="damaged",
                         purchase_order=receipt_po_a)
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "different supplier" in " ".join(excinfo.value.message_dict["purchase_order"])


def test_receipt_rtv_clean_rejects_a_cross_tenant_order(tenant_a, receipt_vendor_a,
                                                        receipt_po_b):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="damaged",
                         purchase_order=receipt_po_b)
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["purchase_order"])


def test_receipt_rtv_clean_rejects_a_receipt_against_a_different_order(
        tenant_a, receipt_vendor_a, receipt_po_a, receipt_grn_a):
    other_order = _receipt_second_po(tenant_a, receipt_vendor_a)
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="damaged",
                         purchase_order=other_order, goods_receipt=receipt_grn_a)
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "different purchase order" in " ".join(excinfo.value.message_dict["goods_receipt"])


def test_receipt_rtv_clean_rejects_a_cross_tenant_receipt(tenant_a, receipt_vendor_a,
                                                          receipt_grn_b):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="damaged",
                         goods_receipt=receipt_grn_b)
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["goods_receipt"])


def test_receipt_rtv_clean_rejects_a_cross_tenant_discrepancy(tenant_a, receipt_vendor_a,
                                                              receipt_discrepancy_b):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="damaged",
                         discrepancy=receipt_discrepancy_b)
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["discrepancy"])


def test_receipt_rtv_clean_demands_a_note_when_the_reason_is_other(tenant_a, receipt_vendor_a):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="other")
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "reason_note" in excinfo.value.message_dict


def test_receipt_rtv_clean_accepts_other_once_the_note_is_given(tenant_a, receipt_vendor_a):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="other",
                         reason_note="Supplier recalled the batch.")
    rtv.full_clean()        # must not raise


def test_receipt_rtv_clean_ignores_a_whitespace_only_reason_note(tenant_a, receipt_vendor_a):
    rtv = ReturnToVendor(tenant=tenant_a, vendor=receipt_vendor_a, reason="other",
                         reason_note="   ")
    with pytest.raises(ValidationError) as excinfo:
        rtv.full_clean()
    assert "reason_note" in excinfo.value.message_dict


def test_receipt_rtv_clean_accepts_the_matching_order_and_receipt(receipt_rtv_draft_a):
    receipt_rtv_draft_a.full_clean()        # must not raise


# ------------------------------------------------------------------ RTV verbs

def test_receipt_rtv_authorize_signs_a_draft(receipt_rtv_draft_a, admin_user):
    before = timezone.now()
    assert receipt_rtv_draft_a.authorize(admin_user) is True

    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "authorized"
    assert receipt_rtv_draft_a.authorized_by_id == admin_user.pk
    assert receipt_rtv_draft_a.authorized_at >= before


def test_receipt_rtv_authorize_is_a_no_op_on_a_double_submit(receipt_rtv_authorized_a,
                                                             member_user):
    signer = receipt_rtv_authorized_a.authorized_by_id
    stamped = receipt_rtv_authorized_a.authorized_at

    assert receipt_rtv_authorized_a.authorize(member_user) is False

    receipt_rtv_authorized_a.refresh_from_db()
    assert receipt_rtv_authorized_a.authorized_by_id == signer
    assert receipt_rtv_authorized_a.authorized_at == stamped


def test_receipt_rtv_authorize_accepts_a_missing_actor(receipt_rtv_draft_a):
    assert receipt_rtv_draft_a.authorize(None) is True
    assert receipt_rtv_draft_a.authorized_by_id is None


def test_receipt_rtv_mark_shipped_stamps_today_by_default(receipt_rtv_authorized_a, admin_user):
    assert receipt_rtv_authorized_a.mark_shipped(admin_user, carrier_name="DPD",
                                                 tracking_number="TRK-1") is True

    receipt_rtv_authorized_a.refresh_from_db()
    assert receipt_rtv_authorized_a.status == "shipped"
    assert receipt_rtv_authorized_a.shipped_on == _receipt_today()
    assert receipt_rtv_authorized_a.carrier_name == "DPD"
    assert receipt_rtv_authorized_a.tracking_number == "TRK-1"


def test_receipt_rtv_mark_shipped_accepts_an_explicit_date(receipt_rtv_authorized_a,
                                                           admin_user):
    yesterday = _receipt_today() - _receipt_days(1)
    receipt_rtv_authorized_a.mark_shipped(admin_user, shipped_on=yesterday)
    assert receipt_rtv_authorized_a.shipped_on == yesterday


def test_receipt_rtv_mark_shipped_never_erases_freight_already_arranged(tenant_a,
                                                                        receipt_vendor_a,
                                                                        admin_user):
    """A blank field in the ship dialog means UNCHANGED, never 'erase it'."""
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, carrier_name="Northwind Express",
                       tracking_number="TRK-EXISTING")
    rtv.authorize(admin_user)

    assert rtv.mark_shipped(admin_user, carrier_name="  ", tracking_number="") is True

    rtv.refresh_from_db()
    assert rtv.carrier_name == "Northwind Express"
    assert rtv.tracking_number == "TRK-EXISTING"


def test_receipt_rtv_mark_shipped_is_refused_from_draft(receipt_rtv_draft_a, admin_user):
    assert receipt_rtv_draft_a.mark_shipped(admin_user, carrier_name="DPD") is False
    assert receipt_rtv_draft_a.status == "draft"
    assert receipt_rtv_draft_a.shipped_on is None


def test_receipt_rtv_mark_shipped_is_a_no_op_on_a_double_submit(receipt_rtv_shipped_a,
                                                                admin_user):
    stamped = receipt_rtv_shipped_a.shipped_on

    assert receipt_rtv_shipped_a.mark_shipped(admin_user, carrier_name="Someone else") is False

    receipt_rtv_shipped_a.refresh_from_db()
    assert receipt_rtv_shipped_a.shipped_on == stamped
    assert receipt_rtv_shipped_a.carrier_name == "DHL"


def test_receipt_rtv_close_records_the_credit_reference(receipt_rtv_shipped_a, admin_user):
    before = timezone.now()
    assert receipt_rtv_shipped_a.close(admin_user, credit_note_ref="CN-4411") is True

    receipt_rtv_shipped_a.refresh_from_db()
    assert receipt_rtv_shipped_a.status == "closed"
    assert receipt_rtv_shipped_a.credit_note_ref == "CN-4411"
    assert receipt_rtv_shipped_a.closed_at >= before


def test_receipt_rtv_close_keeps_a_reference_already_on_the_header(tenant_a, receipt_vendor_a,
                                                                   admin_user):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, credit_note_ref="CN-EXISTING")
    rtv.authorize(admin_user)
    rtv.mark_shipped(admin_user)

    assert rtv.close(admin_user, credit_note_ref="") is True
    assert rtv.credit_note_ref == "CN-EXISTING"


def test_receipt_rtv_close_is_refused_before_the_goods_ship(receipt_rtv_authorized_a,
                                                            admin_user):
    assert receipt_rtv_authorized_a.close(admin_user, credit_note_ref="CN-1") is False
    assert receipt_rtv_authorized_a.status == "authorized"
    assert receipt_rtv_authorized_a.closed_at is None


def test_receipt_rtv_cancel_abandons_a_draft(receipt_rtv_draft_a, admin_user):
    before = timezone.now()
    assert receipt_rtv_draft_a.cancel(admin_user, "Supplier collected instead.") is True

    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "cancelled"
    assert receipt_rtv_draft_a.cancellation_reason == "Supplier collected instead."
    assert receipt_rtv_draft_a.cancelled_at >= before


def test_receipt_rtv_cancel_works_from_authorized(receipt_rtv_authorized_a, admin_user):
    assert receipt_rtv_authorized_a.cancel(admin_user, "RMA withdrawn.") is True
    assert receipt_rtv_authorized_a.status == "cancelled"


def test_receipt_rtv_cancel_is_refused_once_shipped(receipt_rtv_shipped_a, admin_user):
    """The goods are physically gone - un-shipping them would make the register lie."""
    assert receipt_rtv_shipped_a.cancel(admin_user, "Too late.") is False
    assert receipt_rtv_shipped_a.status == "shipped"
    assert receipt_rtv_shipped_a.cancelled_at is None


def test_receipt_rtv_cancel_truncates_an_over_long_reason(receipt_rtv_draft_a, admin_user):
    receipt_rtv_draft_a.cancel(admin_user, "r" * 5000)
    assert len(receipt_rtv_draft_a.cancellation_reason) == 2000


def test_receipt_rtv_every_verb_is_refused_once_cancelled(receipt_rtv_draft_a, admin_user):
    receipt_rtv_draft_a.cancel(admin_user, "Abandoned.")

    assert receipt_rtv_draft_a.authorize(admin_user) is False
    assert receipt_rtv_draft_a.mark_shipped(admin_user) is False
    assert receipt_rtv_draft_a.close(admin_user) is False
    assert receipt_rtv_draft_a.cancel(admin_user, "Again.") is False
    assert receipt_rtv_draft_a.status == "cancelled"


def test_receipt_rtv_full_ladder_runs_draft_to_closed(tenant_a, receipt_vendor_a, admin_user):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a)
    seen = [rtv.status]

    # Called one at a time on purpose: the status is read BETWEEN the verbs, not after them all.
    assert rtv.authorize(admin_user) is True
    seen.append(rtv.status)
    assert rtv.mark_shipped(admin_user, carrier_name="DHL") is True
    seen.append(rtv.status)
    assert rtv.close(admin_user, credit_note_ref="CN-1") is True
    seen.append(rtv.status)

    assert seen == ["draft", "authorized", "shipped", "closed"]
    rtv.refresh_from_db()
    assert rtv.status == "closed"



def test_receipt_rtv_the_whole_ladder_posts_no_stock_move_and_no_journal_entry(
        tenant_a, receipt_vendor_a, receipt_po_a, receipt_po_line_a, admin_user):
    """The defended non-posting invariant: an RTV is a commercial document, not a movement."""
    before = _receipt_posting_counts(tenant_a)

    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, purchase_order=receipt_po_a)
    _receipt_rtv_line(rtv, po_line=receipt_po_line_a, quantity_returned=Decimal("3"))
    rtv.authorize(admin_user)
    rtv.mark_shipped(admin_user, carrier_name="DHL", tracking_number="TRK-1")
    rtv.close(admin_user, credit_note_ref="CN-1")

    assert _receipt_posting_counts(tenant_a) == before == (0, 0)


def test_receipt_rtv_cancelling_posts_nothing_either(tenant_a, receipt_vendor_a,
                                                     receipt_po_line_a, admin_user):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a)
    _receipt_rtv_line(rtv, po_line=receipt_po_line_a)
    rtv.authorize(admin_user)
    rtv.cancel(admin_user, "Abandoned.")

    assert _receipt_posting_counts(tenant_a) == (0, 0)


# ------------------------------------------------------------------ RTV derived reads

def test_receipt_rtv_is_editable_only_in_draft(receipt_rtv_draft_a, receipt_rtv_authorized_a,
                                               receipt_rtv_shipped_a):
    assert receipt_rtv_draft_a.is_editable is True
    assert receipt_rtv_authorized_a.is_editable is False
    assert receipt_rtv_shipped_a.is_editable is False


def test_receipt_rtv_line_count_and_expected_credit_fold_the_lines(receipt_rtv_draft_a,
                                                                    receipt_rtv_line_a):
    fresh = ReturnToVendor.objects.get(pk=receipt_rtv_draft_a.pk)

    assert fresh.line_count == 1
    assert fresh.expected_credit_value == Decimal("75.00")      # 3 x 25.00


def test_receipt_rtv_expected_credit_is_zero_without_lines(receipt_rtv_authorized_a):
    assert receipt_rtv_authorized_a.line_count == 0
    assert receipt_rtv_authorized_a.expected_credit_value == Decimal("0.00")


def test_receipt_rtv_expected_credit_is_recomputed_on_every_read_never_stored(
        receipt_rtv_draft_a, receipt_rtv_line_a):
    assert "expected_credit_value" not in _receipt_field_names(ReturnToVendor)
    assert "line_count" not in _receipt_field_names(ReturnToVendor)

    receipt_rtv_line_a.quantity_returned = Decimal("4")
    receipt_rtv_line_a.save(update_fields=["quantity_returned"])

    # No save on the HEADER, yet the total moves - it is folded from the lines every read.
    reread = ReturnToVendor.objects.get(pk=receipt_rtv_draft_a.pk)
    assert reread.expected_credit_value == Decimal("100.00")


def test_receipt_rtv_expected_credit_sums_several_lines(tenant_a, receipt_vendor_a,
                                                        receipt_po_a, receipt_po_line_a,
                                                        receipt_po_line2_a):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, purchase_order=receipt_po_a)
    _receipt_rtv_line(rtv, po_line=receipt_po_line_a, quantity_returned=Decimal("2"))
    _receipt_rtv_line(rtv, po_line=receipt_po_line2_a, quantity_returned=Decimal("1"))

    fresh = ReturnToVendor.objects.get(pk=rtv.pk)
    assert fresh.expected_credit_value == Decimal("110.00")     # 2x25.00 + 1x60.00


def test_receipt_rtv_expected_credit_is_clamped_to_what_a_money_column_holds(
        tenant_a, receipt_vendor_a, receipt_po_a):
    """A fat-fingered quantity is a wrong number, never a driver DataError."""
    line = _receipt_second_po_line(receipt_po_a, description="Gold plated", qty="1",
                                   price="9999999.99")
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, purchase_order=receipt_po_a)
    _receipt_rtv_line(rtv, po_line=line, quantity_returned=Decimal("9999999"))

    assert ReturnToVendor.objects.get(pk=rtv.pk).expected_credit_value == Decimal(
        "9999999999.99")


def test_receipt_rtv_line_rows_are_fetched_once_per_instance(receipt_rtv_draft_a,
                                                             receipt_rtv_line_a,
                                                             django_assert_num_queries):
    fresh = ReturnToVendor.objects.get(pk=receipt_rtv_draft_a.pk)

    with django_assert_num_queries(1):
        first = fresh.line_rows()
        second = fresh.line_rows()
        assert fresh.line_count == 1
        assert fresh.expected_credit_value == Decimal("75.00")

    assert first is second


def test_receipt_rtv_line_rows_honour_a_callers_prefetch(receipt_rtv_draft_a,
                                                         receipt_rtv_line_a,
                                                         django_assert_num_queries):
    with django_assert_num_queries(2):      # the page of rows + the one prefetch
        rows = list(ReturnToVendor.objects.filter(pk=receipt_rtv_draft_a.pk)
                    .prefetch_related("lines"))
        assert rows[0].line_rows() == [receipt_rtv_line_a]


def test_receipt_rtv_has_duplicate_rma_spots_a_live_peer(tenant_a, receipt_vendor_a):
    first = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-77")
    second = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-77")

    assert ReturnToVendor.objects.get(pk=first.pk).has_duplicate_rma is True
    assert ReturnToVendor.objects.get(pk=second.pk).has_duplicate_rma is True


def test_receipt_rtv_has_duplicate_rma_is_false_for_a_unique_reference(tenant_a,
                                                                      receipt_vendor_a):
    solo = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-ONLY")
    assert solo.has_duplicate_rma is False


def test_receipt_rtv_has_duplicate_rma_ignores_a_blank_reference(tenant_a, receipt_vendor_a):
    _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="")
    second = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="")

    assert ReturnToVendor.objects.get(pk=second.pk).has_duplicate_rma is False


def test_receipt_rtv_has_duplicate_rma_ignores_a_cancelled_peer(tenant_a, receipt_vendor_a,
                                                                admin_user):
    dead = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-77")
    dead.cancel(admin_user, "Abandoned.")
    live = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-77")

    assert ReturnToVendor.objects.get(pk=live.pk).has_duplicate_rma is False


def test_receipt_rtv_has_duplicate_rma_never_counts_another_tenants_row(
        tenant_a, receipt_vendor_a, receipt_rtv_b):
    receipt_rtv_b.supplier_rma_number = "RMA-SHARED"
    receipt_rtv_b.save(update_fields=["supplier_rma_number"])
    mine = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-SHARED")

    assert ReturnToVendor.objects.get(pk=mine.pk).has_duplicate_rma is False


def test_receipt_rtv_has_duplicate_rma_prefers_the_registers_annotation(tenant_a,
                                                                       receipt_vendor_a,
                                                                       django_assert_num_queries):
    solo = _receipt_rtv(tenant_a, receipt_vendor_a, supplier_rma_number="RMA-ONLY")
    fresh = ReturnToVendor.objects.get(pk=solo.pk)
    fresh.rma_duplicate_flag = True

    with django_assert_num_queries(0):
        assert fresh.has_duplicate_rma is True


# ================================================================================================
# 7. ReturnToVendorLine - tenant-less child, mirrored text, derived money
# ================================================================================================

def test_receipt_rtv_line_is_tenant_less_and_scoped_through_its_header(receipt_rtv_line_a,
                                                                       receipt_rtv_draft_a):
    assert "tenant" not in _receipt_field_names(ReturnToVendorLine)
    assert receipt_rtv_line_a.return_to_vendor_id == receipt_rtv_draft_a.pk
    assert ReturnToVendorLine._meta.ordering == ["id"]


def test_receipt_rtv_line_carries_no_status_and_no_number():
    names = _receipt_field_names(ReturnToVendorLine)
    assert "status" not in names and "number" not in names
    assert not hasattr(ReturnToVendorLine, "NUMBER_PREFIX")


def test_receipt_rtv_line_minimal_create_takes_its_documented_defaults(receipt_rtv_draft_a):
    line = ReturnToVendorLine.objects.create(return_to_vendor=receipt_rtv_draft_a)

    assert line.quantity_returned == 1
    assert line.goods_receipt_line_id is None
    assert line.po_line_id is None
    assert line.item_description == "" and line.sku_hint == "" and line.uom_hint == ""
    assert line.lot_number == "" and line.serial_number == ""
    assert line.condition_note == ""


def test_receipt_rtv_line_str_folds_the_description_and_the_quantity(receipt_rtv_line_a):
    assert str(receipt_rtv_line_a) == "%s \u00d7%s" % (receipt_rtv_line_a.item_description,
                                                       receipt_rtv_line_a.quantity_returned)


def test_receipt_rtv_line_str_falls_back_to_the_po_line_without_a_description(
        receipt_rtv_draft_a, receipt_po_line_a):
    line = ReturnToVendorLine(return_to_vendor=receipt_rtv_draft_a, po_line=receipt_po_line_a,
                              quantity_returned=Decimal("2"))
    assert str(line) == "%s \u00d72" % (receipt_po_line_a,)


def test_receipt_rtv_line_save_mirrors_the_ordered_lines_free_text(receipt_rtv_draft_a,
                                                                    receipt_po_line_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a, po_line=receipt_po_line_a)

    assert line.item_description == receipt_po_line_a.item_description
    assert line.sku_hint == "BRG-40"
    assert line.uom_hint == "EA"


def test_receipt_rtv_line_save_prefers_the_receipt_lines_ordered_line(receipt_rtv_draft_a,
                                                                      receipt_grn_line_a,
                                                                      receipt_po_line_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a, goods_receipt_line=receipt_grn_line_a)

    assert line.po_line_id is None
    assert line.item_description == receipt_po_line_a.item_description
    assert line.sku_hint == "BRG-40"


def test_receipt_rtv_line_save_never_overwrites_text_the_buyer_typed(receipt_rtv_draft_a,
                                                                      receipt_po_line_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a, po_line=receipt_po_line_a,
                             item_description="Bearing (the cracked one)", sku_hint="BRG-40-X",
                             uom_hint="BOX")

    assert line.item_description == "Bearing (the cracked one)"
    assert line.sku_hint == "BRG-40-X"
    assert line.uom_hint == "BOX"


def test_receipt_rtv_line_save_leaves_the_text_blank_with_no_source_line(receipt_rtv_draft_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a)

    assert line.item_description == ""
    assert line.sku_hint == ""
    assert line.uom_hint == ""


def test_receipt_rtv_line_unit_price_is_read_live_off_the_ordered_line(receipt_rtv_draft_a,
                                                                       receipt_po_line_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a, po_line=receipt_po_line_a)

    assert "unit_price" not in _receipt_field_names(ReturnToVendorLine)
    assert line.unit_price == Decimal("25.00")

    receipt_po_line_a.unit_price = Decimal("30.00")
    receipt_po_line_a.save(update_fields=["unit_price"])

    reread = ReturnToVendorLine.objects.get(pk=line.pk)
    assert reread.unit_price == Decimal("30.00")
    assert reread.expected_credit == Decimal("90.00")


def test_receipt_rtv_line_unit_price_falls_back_to_the_receipt_lines_order(receipt_rtv_draft_a,
                                                                           receipt_grn_line_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a, goods_receipt_line=receipt_grn_line_a)
    assert line.unit_price == Decimal("25.00")


def test_receipt_rtv_line_unit_price_honours_a_legitimately_zero_priced_line(
        tenant_a, receipt_vendor_a, receipt_po_a, receipt_grn_a, receipt_grn_line_a):
    """A free replacement must return ZERO, not fall through to the other source (the reason
    the property tests ``po_line_id`` explicitly rather than ``a or b``)."""
    free_line = _receipt_second_po_line(receipt_po_a, description="Free replacement", qty="1",
                                        price="0.00")
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, purchase_order=receipt_po_a,
                       goods_receipt=receipt_grn_a)
    line = _receipt_rtv_line(rtv, po_line=free_line, goods_receipt_line=receipt_grn_line_a)

    assert line.unit_price == Decimal("0")
    assert line.expected_credit == Decimal("0.00")


def test_receipt_rtv_line_unit_price_is_zero_with_no_source_line_at_all(receipt_rtv_draft_a):
    line = _receipt_rtv_line(receipt_rtv_draft_a)
    assert line.unit_price == Decimal("0")
    assert line.expected_credit == Decimal("0.00")


def test_receipt_rtv_line_expected_credit_is_quantised_to_two_places(receipt_rtv_draft_a,
                                                                      receipt_po_a):
    odd = _receipt_second_po_line(receipt_po_a, description="Odd price", qty="9",
                                  price="3.33")
    line = _receipt_rtv_line(receipt_rtv_draft_a, po_line=odd,
                             quantity_returned=Decimal("1.5"))

    assert line.expected_credit == Decimal("5.00")      # 1.5 x 3.33 = 4.995 -> 5.00


def test_receipt_rtv_line_clean_rejects_a_zero_quantity(receipt_rtv_draft_a,
                                                        receipt_po_line_a):
    line = ReturnToVendorLine(return_to_vendor=receipt_rtv_draft_a, po_line=receipt_po_line_a,
                              quantity_returned=Decimal("0"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "quantity_returned" in excinfo.value.message_dict


def test_receipt_rtv_line_clean_rejects_a_negative_quantity(receipt_rtv_draft_a,
                                                            receipt_po_line_a):
    line = ReturnToVendorLine(return_to_vendor=receipt_rtv_draft_a, po_line=receipt_po_line_a,
                              quantity_returned=Decimal("-3"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "quantity_returned" in excinfo.value.message_dict


def test_receipt_rtv_line_clean_rejects_an_unrelated_ordered_line(receipt_rtv_draft_a,
                                                                  receipt_grn_line_a,
                                                                  receipt_po_line2_a):
    """A crafted POST must not staple somebody else's unit price onto a received line."""
    line = ReturnToVendorLine(return_to_vendor=receipt_rtv_draft_a,
                              goods_receipt_line=receipt_grn_line_a, po_line=receipt_po_line2_a,
                              quantity_returned=Decimal("1"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "not the one this receipt line received" in " ".join(
        excinfo.value.message_dict["po_line"])


def test_receipt_rtv_line_clean_rejects_a_line_from_a_different_receipt(receipt_rtv_draft_a,
                                                                        receipt_grn_early_a):
    stray = receipt_grn_early_a.lines.first()
    line = ReturnToVendorLine(return_to_vendor=receipt_rtv_draft_a, goods_receipt_line=stray,
                              quantity_returned=Decimal("1"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "different goods receipt" in " ".join(
        excinfo.value.message_dict["goods_receipt_line"])


def test_receipt_rtv_line_clean_accepts_a_matching_pair(receipt_rtv_draft_a,
                                                        receipt_grn_line_a,
                                                        receipt_po_line_a):
    line = ReturnToVendorLine(return_to_vendor=receipt_rtv_draft_a,
                              goods_receipt_line=receipt_grn_line_a, po_line=receipt_po_line_a,
                              quantity_returned=Decimal("2"))
    line.full_clean()        # must not raise


# ================================================================================================
# 8. The spine 6.12 hangs off - received quantity is an AGGREGATE, never a stored balance
# ================================================================================================

def _receipt_cumulative_received(po_line):
    """What every 6.12 board computes: quantity accepted across all LIVE receipts of one line."""
    from django.db.models import Sum
    from apps.scm.models import GoodsReceiptLine

    return (GoodsReceiptLine.objects
            .filter(po_line=po_line)
            .exclude(goods_receipt__status="cancelled")
            .aggregate(total=Sum("quantity_received"))["total"] or Decimal("0"))


def test_receipt_spine_keeps_no_stored_received_to_date_column():
    from apps.scm.models import GoodsReceiptLine, PurchaseOrderLine

    line_names = _receipt_field_names(GoodsReceiptLine)
    order_line_names = _receipt_field_names(PurchaseOrderLine)

    for stored in ("cumulative_received", "received_to_date", "quantity_received_total"):
        assert stored not in line_names
        assert stored not in order_line_names
    # ...and no item FK anywhere on the receiving spine - sku_hint free text is the only bridge.
    assert "item" not in line_names
    assert "item" not in order_line_names
    assert "sku_hint" in order_line_names


def test_receipt_cumulative_quantity_is_summed_across_live_receipts(tenant_a, receipt_po_a,
                                                                    receipt_po_line_a,
                                                                    receipt_grn_a,
                                                                    receipt_grn_line_a):
    second = _receipt_second_grn(tenant_a, receipt_po_a, reference="DN-5005")
    _receipt_grn_line(second, receipt_po_line_a, received="3")

    assert _receipt_cumulative_received(receipt_po_line_a) == Decimal("15")


def test_receipt_cumulative_quantity_excludes_a_cancelled_receipt(tenant_a, receipt_po_line_a,
                                                                  receipt_grn_a,
                                                                  receipt_grn_line_a,
                                                                  receipt_grn_cancelled_a):
    """Every 6.12 board excludes ``status="cancelled"`` receipts - including the running total."""
    assert receipt_grn_cancelled_a.status == "cancelled"
    assert _receipt_cumulative_received(receipt_po_line_a) == Decimal("12")


def test_receipt_two_part_deliveries_add_up_to_an_over_receipt(tenant_a, receipt_vendor_a,
                                                               receipt_policy_catchall_a):
    """Two receipts of 60 against an order of 100 IS an over-receipt - the aggregate is judged,
    never a single line."""
    order = _receipt_second_po(tenant_a, receipt_vendor_a)
    line = _receipt_second_po_line(order, qty="100", price="1.00")
    for reference, quantity in (("DN-A", "60"), ("DN-B", "60")):
        grn = _receipt_second_grn(tenant_a, order, reference=reference)
        _receipt_grn_line(grn, line, received=quantity)

    cumulative = _receipt_cumulative_received(line)
    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)
    verdict, _v = evaluate_receipt_tolerance(rule, ordered_quantity=line.quantity,
                                             received_quantity=cumulative)

    assert cumulative == Decimal("120")
    assert verdict == "over"


def test_receipt_a_single_part_delivery_alone_is_not_an_over_receipt(tenant_a,
                                                                     receipt_vendor_a,
                                                                     receipt_policy_catchall_a):
    order = _receipt_second_po(tenant_a, receipt_vendor_a)
    line = _receipt_second_po_line(order, qty="100", price="1.00")
    grn = _receipt_second_grn(tenant_a, order, reference="DN-ONLY")
    _receipt_grn_line(grn, line, received="60")

    rule, _reason = resolve_receipt_tolerance(None, receipt_vendor_a, tenant=tenant_a)
    verdict, _v = evaluate_receipt_tolerance(
        rule, ordered_quantity=line.quantity,
        received_quantity=_receipt_cumulative_received(line))

    assert verdict == "short"       # 60 of 100 is below the 90 floor, not over the ceiling


def test_receipt_shipped_fixture_spine_matches_the_documented_shape(receipt_po_a,
                                                                    receipt_po_line_a,
                                                                    receipt_po_line2_a,
                                                                    receipt_grn_a,
                                                                    receipt_grn_line_a,
                                                                    receipt_grn_line2_a):
    """The four boards are read against these numbers; pin them so a fixture edit is visible."""
    assert receipt_po_a.expected_date == _receipt_today()
    assert (receipt_po_line_a.quantity, receipt_po_line_a.unit_price) == (Decimal("10"),
                                                                          Decimal("25.00"))
    assert (receipt_po_line2_a.quantity, receipt_po_line2_a.unit_price) == (Decimal("4"),
                                                                             Decimal("60.00"))
    assert receipt_grn_a.receipt_date == _receipt_today()
    assert receipt_grn_line_a.quantity_received == Decimal("12")
    assert receipt_grn_line_a.quantity_rejected == Decimal("1")
    assert receipt_grn_line2_a.quantity_received == Decimal("1")


# ================================================================================================
# 9. Cross-cutting - tenancy, the pointer registers, and the derived-never-stored sweep
# ================================================================================================

def test_receipt_every_owned_model_carries_a_tenant_except_the_line_child():
    for model in (ReceiptTolerancePolicy, ReceiptDiscrepancy, ReturnToVendor):
        assert "tenant" in _receipt_field_names(model)
    assert "tenant" not in _receipt_field_names(ReturnToVendorLine)


def test_receipt_querysets_never_leak_across_tenants(tenant_a, tenant_b,
                                                     receipt_discrepancy_open_a,
                                                     receipt_discrepancy_b, receipt_rtv_draft_a,
                                                     receipt_rtv_b, receipt_policy_catchall_a,
                                                     receipt_policy_b):
    assert list(ReceiptDiscrepancy.objects.filter(tenant=tenant_a)) == [
        receipt_discrepancy_open_a]
    assert list(ReceiptDiscrepancy.objects.filter(tenant=tenant_b)) == [receipt_discrepancy_b]
    assert list(ReturnToVendor.objects.filter(tenant=tenant_a)) == [receipt_rtv_draft_a]
    assert list(ReturnToVendor.objects.filter(tenant=tenant_b)) == [receipt_rtv_b]
    assert list(ReceiptTolerancePolicy.objects.filter(tenant=tenant_a)) == [
        receipt_policy_catchall_a]
    assert list(ReceiptTolerancePolicy.objects.filter(tenant=tenant_b)) == [receipt_policy_b]


def test_receipt_a_discrepancy_points_at_the_registers_that_own_the_effect(
        tenant_a, receipt_grn_a, receipt_nonconformance_a, receipt_quarantine_a,
        receipt_rtv_draft_a):
    """6.12 POINTS at scm 4.9 / inventory 5.15 / its own RTV - it never re-declares them (L36)."""
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a, kind="quality_failure",
                                   nonconformance=receipt_nonconformance_a,
                                   quarantine_order=receipt_quarantine_a,
                                   return_to_vendor=receipt_rtv_draft_a)
    finding.full_clean()

    assert finding.nonconformance == receipt_nonconformance_a
    assert finding.quarantine_order == receipt_quarantine_a
    assert finding.return_to_vendor == receipt_rtv_draft_a
    assert list(receipt_rtv_draft_a.source_discrepancies.all()) == [finding]


def test_receipt_clearing_a_pointed_at_record_never_deletes_the_finding(
        tenant_a, receipt_grn_a, receipt_nonconformance_a):
    finding = _receipt_discrepancy(tenant_a, receipt_grn_a, kind="quality_failure",
                                   nonconformance=receipt_nonconformance_a)
    receipt_nonconformance_a.delete()

    finding.refresh_from_db()
    assert finding.pk is not None
    assert finding.nonconformance_id is None        # SET_NULL, never CASCADE


def test_receipt_an_rtv_answers_the_finding_it_was_raised_from(tenant_a, receipt_vendor_a,
                                                               receipt_discrepancy_open_a):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, discrepancy=receipt_discrepancy_open_a)
    rtv.full_clean()

    assert list(receipt_discrepancy_open_a.rtvs.all()) == [rtv]


def test_receipt_no_module_model_stores_a_figure_it_could_derive():
    """L29 sweep: not one of these reads is a column anybody could edit out of step."""
    derived_by_model = {
        ReceiptTolerancePolicy: ("scope_key", "scope_label", "specificity_tier",
                                 "over_band_text", "under_band_text", "date_band_text"),
        ReceiptDiscrepancy: ("order", "vendor", "is_open", "has_evidence"),
        ReturnToVendor: ("line_count", "expected_credit_value", "has_duplicate_rma",
                         "is_editable"),
        ReturnToVendorLine: ("unit_price", "expected_credit"),
    }
    for model, names in derived_by_model.items():
        fields = _receipt_field_names(model)
        for name in names:
            assert name not in fields, "%s.%s must stay derived" % (model.__name__, name)
            assert isinstance(getattr(model, name, None), property) or callable(
                getattr(model, name, None))


def test_receipt_rtv_badge_properties_read_the_maps(tenant_a, receipt_vendor_a, admin_user):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a, reason="wrong_item", remedy="replacement")

    assert rtv.status_css == "badge-muted"
    assert rtv.reason_css == "badge-amber"
    assert rtv.remedy_css == "badge-info"

    rtv.authorize(admin_user)
    assert rtv.status_css == "badge-info"
    rtv.mark_shipped(admin_user)
    assert rtv.status_css == "badge-amber"
    rtv.close(admin_user)
    assert rtv.status_css == "badge-green"


def test_receipt_rtv_badge_properties_fall_back_to_slate_on_junk(tenant_a, receipt_vendor_a):
    rtv = _receipt_rtv(tenant_a, receipt_vendor_a)
    rtv.status = "not-a-status"
    rtv.reason = "not-a-reason"
    rtv.remedy = "not-a-remedy"

    assert rtv.status_css == "badge-slate"
    assert rtv.reason_css == "badge-slate"
    assert rtv.remedy_css == "badge-slate"


def test_receipt_policy_band_text_survives_a_non_finite_decimal():
    """The band helpers are DISPLAY code: a NaN must hand itself back, never 500 a page."""
    rule = _receipt_unsaved_policy(over_receipt_pct=Decimal("NaN"))

    text = rule.over_band_text        # must not raise TypeError

    assert isinstance(text, str)
    assert "NaN" in text
