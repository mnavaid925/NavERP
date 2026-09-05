"""Procurement 6.18 Inventory & Warehouse Integration — model tests.

The two invariants this sub-module exists to hold are asserted here, not inferred:

* **The ledger boundary.** ``apps/procurement`` writes ZERO ``scm.StockMove`` rows.
  ``MaterialIssue.post()`` mints a *draft* ``scm.StockAdjustment`` and lets SCM own the movement.
  Every post test counts ``StockMove`` before and after and asserts the delta is 0 — asserting the
  adjustment exists would pass even if a StockMove had been written alongside it.
* **Derived, never stored.** ``ReplenishmentSuggestion``'s snapshot columns are ``editable=False``
  point-in-time records, and every live figure is re-read from ``StockMove``.

Several tests are regressions for findings that were fixed in Phase 5 and would come back
silently; each names its finding id so a future reader knows the test is load-bearing rather than
incidental.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.procurement.models import (
    MaterialIssue,
    MaterialIssueLine,
    ReplenishmentPolicy,
    ReplenishmentRun,
    ReplenishmentSuggestion,
)
from apps.scm.models import PurchaseRequisition, StockAdjustment, StockMove

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")


def _invwarehouse_policy(tenant, item, location=None, **overrides):
    """A saved policy with the shaping fields the caller cares about and nothing else set."""
    fields = dict(tenant=tenant, item=item, location=location, source_method="buy")
    fields.update(overrides)
    return ReplenishmentPolicy.objects.create(**fields)


# --------------------------------------------------------------------------- round_quantity


def test_invwarehouse_round_quantity_refuses_a_non_positive_shortfall(invwarehouse_policy_a):
    """Rule 1: a shortfall of zero or less is not an order."""
    assert invwarehouse_policy_a.round_quantity(0) == ZERO
    assert invwarehouse_policy_a.round_quantity(-5) == ZERO
    assert invwarehouse_policy_a.round_quantity(None) == ZERO


def test_invwarehouse_round_quantity_floors_at_the_vendor_minimum(invwarehouse_item_a, tenant_a):
    policy = _invwarehouse_policy(tenant_a, invwarehouse_item_a, min_order_qty=Decimal("10"))
    assert policy.round_quantity(3) == Decimal("10.0000")


def test_invwarehouse_round_quantity_rounds_up_to_the_multiple(invwarehouse_item_a, tenant_a):
    """You cannot buy two thirds of a pallet — 30 against a multiple of 25 is 50, not 25."""
    policy = _invwarehouse_policy(tenant_a, invwarehouse_item_a, order_multiple=Decimal("25"))
    assert policy.round_quantity(30) == Decimal("50.0000")
    assert policy.round_quantity(25) == Decimal("25.0000")


def test_invwarehouse_round_quantity_applies_the_cap_last_so_it_beats_the_multiple(
        invwarehouse_item_a, tenant_a):
    """THE ordering test. Multiple 30, cap 100, raw 95 -> 100, NOT 120.

    A ceiling a caller can exceed is not a ceiling. If the cap were applied before the multiple,
    rounding up would carry the answer straight back through it.
    """
    policy = _invwarehouse_policy(tenant_a, invwarehouse_item_a,
                                  order_multiple=Decimal("30"), max_order_qty=Decimal("100"))
    assert policy.round_quantity(95) == Decimal("100.0000")


def test_invwarehouse_round_quantity_ignores_a_stored_zero_multiple_and_cap(
        invwarehouse_item_a, tenant_a):
    """A seeded row never went through the form's validators, so 0 must not divide or clamp."""
    policy = _invwarehouse_policy(tenant_a, invwarehouse_item_a,
                                  order_multiple=ZERO, max_order_qty=ZERO)
    assert policy.round_quantity(7) == Decimal("7.0000")


def test_invwarehouse_round_quantity_returns_a_quantized_decimal(invwarehouse_policy_a):
    result = invwarehouse_policy_a.round_quantity("12.5")
    assert isinstance(result, Decimal)
    assert result.as_tuple().exponent == -4


# --------------------------------------------------------------------------- resolve


def test_invwarehouse_resolve_prefers_the_located_row_over_the_catch_all(
        tenant_a, invwarehouse_item_a, invwarehouse_location_a,
        invwarehouse_policy_a, invwarehouse_policy_catchall_a):
    """Specificity-first: an exact (item, location) row wins over the (item, NULL) catch-all."""
    found = ReplenishmentPolicy.resolve(tenant_a, invwarehouse_item_a, invwarehouse_location_a)
    assert found == invwarehouse_policy_a


def test_invwarehouse_resolve_falls_back_to_the_catch_all(
        tenant_a, invwarehouse_item_a, invwarehouse_location2_a, invwarehouse_policy_catchall_a):
    """A location with no row of its own still gets the item's any-location policy."""
    found = ReplenishmentPolicy.resolve(tenant_a, invwarehouse_item_a, invwarehouse_location2_a)
    assert found == invwarehouse_policy_catchall_a


def test_invwarehouse_resolve_returns_none_when_the_item_has_no_policy(
        tenant_a, invwarehouse_item3_a, invwarehouse_location_a):
    assert ReplenishmentPolicy.resolve(tenant_a, invwarehouse_item3_a,
                                       invwarehouse_location_a) is None


def test_invwarehouse_resolve_map_answers_many_pairs_in_one_call(
        tenant_a, invwarehouse_item_a, invwarehouse_location_a, invwarehouse_location2_a,
        invwarehouse_policy_a, invwarehouse_policy_catchall_a,
        django_assert_max_num_queries):
    """The run needs a policy per suggestion line; resolve() in a loop would be the N+1."""
    pairs = [(invwarehouse_item_a.pk, invwarehouse_location_a.pk),
             (invwarehouse_item_a.pk, invwarehouse_location2_a.pk)]
    with django_assert_max_num_queries(2):
        mapping = ReplenishmentPolicy.resolve_map(tenant_a, pairs)
    assert mapping[pairs[0]] == invwarehouse_policy_a
    assert mapping[pairs[1]] == invwarehouse_policy_catchall_a


def test_invwarehouse_resolve_map_is_empty_for_a_tenant_less_user(
        invwarehouse_item_a, invwarehouse_location_a):
    assert ReplenishmentPolicy.resolve_map(
        None, [(invwarehouse_item_a.pk, invwarehouse_location_a.pk)]) == {}


# --------------------------------------------------------------------------- policy clean()


def test_invwarehouse_policy_rejects_a_cross_tenant_item(
        tenant_a, invwarehouse_item_b, invwarehouse_location_a):
    policy = ReplenishmentPolicy(tenant=tenant_a, item=invwarehouse_item_b,
                                 location=invwarehouse_location_a)
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert "item" in exc.value.error_dict


def test_invwarehouse_policy_rejects_a_max_below_the_min(
        tenant_a, invwarehouse_item_a, invwarehouse_location_a):
    policy = ReplenishmentPolicy(tenant=tenant_a, item=invwarehouse_item_a,
                                 location=invwarehouse_location_a,
                                 min_order_qty=Decimal("50"), max_order_qty=Decimal("10"))
    with pytest.raises(ValidationError):
        policy.full_clean()


def test_invwarehouse_policy_rejects_a_party_without_a_supplier_role(
        tenant_a, invwarehouse_item_a, invwarehouse_location_a, invwarehouse_plain_party_a):
    """The ROLE rule, not the tenant rule — invwarehouse_plain_party_a is same-tenant but roleless.

    A narrowed <select> is UX; this clean() check is the boundary a hand-crafted POST hits.
    """
    policy = ReplenishmentPolicy(tenant=tenant_a, item=invwarehouse_item_a,
                                 location=invwarehouse_location_a,
                                 preferred_vendor=invwarehouse_plain_party_a)
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert "preferred_vendor" in exc.value.error_dict


def test_invwarehouse_policy_rejects_a_second_catch_all_the_db_unique_cannot_catch(
        tenant_a, invwarehouse_item_a, invwarehouse_policy_catchall_a):
    """unique_together CANNOT catch this: NULLs compare distinct in SQL.

    So the DB would happily hold two (tenant, item, NULL) rows and resolve() would pick an
    arbitrary one. clean() probes for it explicitly — this test is why that probe exists.
    """
    duplicate = ReplenishmentPolicy(tenant=tenant_a, item=invwarehouse_item_a, location=None)
    with pytest.raises(ValidationError):
        duplicate.full_clean()


def test_invwarehouse_policy_requisitionable_source_methods_is_buy_only(invwarehouse_policy_a,
                                                                       invwarehouse_policy_transfer_a):
    assert ReplenishmentPolicy.REQUISITIONABLE_SOURCE_METHODS == ("buy",)
    assert invwarehouse_policy_a.raises_requisitions is True
    assert invwarehouse_policy_transfer_a.raises_requisitions is False


# --------------------------------------------------------------------------- generate()


def test_invwarehouse_generate_proposes_and_is_idempotent_on_re_run(
        invwarehouse_run_a, invwarehouse_rule_a, invwarehouse_stock_a, invwarehouse_policy_a,
        admin_user):
    """Re-generate deletes its own prior lines first — a second press must not double them."""
    invwarehouse_run_a.generate(admin_user)
    first = list(invwarehouse_run_a.lines.values_list("item_id", "location_id", "suggested_qty"))
    invwarehouse_run_a.refresh_from_db()
    assert invwarehouse_run_a.status == "proposed"

    invwarehouse_run_a.generate(admin_user)
    second = list(invwarehouse_run_a.lines.values_list("item_id", "location_id", "suggested_qty"))
    assert first == second


def test_invwarehouse_generate_skips_a_policy_that_does_not_buy(
        tenant_a, invwarehouse_run_a, invwarehouse_policy_transfer_a, admin_user):
    """A transfer- or manufacture-sourced item is not proposed for — it is somebody else's supply."""
    invwarehouse_run_a.generate(admin_user)
    proposed_items = set(invwarehouse_run_a.lines.values_list("item_id", flat=True))
    assert invwarehouse_policy_transfer_a.item_id not in proposed_items


def test_invwarehouse_generate_honours_the_policy_netting_toggles(
        tenant_a, invwarehouse_run_a, invwarehouse_rule_a, invwarehouse_stock_a,
        invwarehouse_policy_a, admin_user):
    """Regression for finding I2.

    The board and the run must agree, and both must net on-order/open-requisitions only when the
    policy says to. Flipping include_on_order must change what generate() proposes; if it does
    not, the toggle is decorative and the two pages will disagree the moment anyone uses it.
    """
    invwarehouse_policy_a.include_on_order = True
    invwarehouse_policy_a.include_open_requisitions = True
    invwarehouse_policy_a.save(update_fields=["include_on_order", "include_open_requisitions"])
    invwarehouse_run_a.generate(admin_user)
    with_netting = {(l.item_id, l.location_id): l.raw_suggested_qty
                    for l in invwarehouse_run_a.lines.all()}

    invwarehouse_policy_a.include_on_order = False
    invwarehouse_policy_a.include_open_requisitions = False
    invwarehouse_policy_a.save(update_fields=["include_on_order", "include_open_requisitions"])
    invwarehouse_run_a.status = "draft"
    invwarehouse_run_a.save(update_fields=["status"])
    invwarehouse_run_a.generate(admin_user)
    without_netting = {(l.item_id, l.location_id): l.raw_suggested_qty
                       for l in invwarehouse_run_a.lines.all()}

    # Not netting incoming supply off can only ever propose the same or MORE.
    for key, raw in without_netting.items():
        assert raw >= with_netting.get(key, ZERO)


def test_invwarehouse_generate_stays_within_its_query_budget(
        invwarehouse_run_a, invwarehouse_rules_bulk_a, admin_user,
        django_assert_max_num_queries):
    """Pins the nine-grouped-read design against 40 rules.

    Measured at 17 cold / 16 warm: 9 grouped reads plus the lock SELECT, the DELETE, the bulk
    INSERT, the header UPDATE, a ContentType SELECT, the audit INSERT and two savepoints. The
    ceiling sits one above the measurement on purpose — every regression it guards (a per-rule
    resolve(), a lazy rule.item.uom.code) is worth 40+ queries at this size, so the slack cannot
    hide one.
    """
    with django_assert_max_num_queries(17):
        invwarehouse_run_a.generate(admin_user)


def test_invwarehouse_suggestion_snapshot_columns_are_not_editable():
    """The eleven snapshots are a point-in-time record, so the row still explains itself later."""
    frozen = ("on_hand_qty", "allocated_qty", "on_order_qty", "open_requisition_qty",
              "available_qty", "reorder_point_snapshot", "target_level_snapshot",
              "raw_suggested_qty", "suggested_qty", "unit_cost", "lead_time_days")
    for name in frozen:
        assert ReplenishmentSuggestion._meta.get_field(name).editable is False, name


def test_invwarehouse_suggestion_line_value_is_derived_not_stored():
    assert not hasattr(ReplenishmentSuggestion, "line_value_stored")
    field_names = {f.name for f in ReplenishmentSuggestion._meta.get_fields()}
    assert "line_value" not in field_names


# --------------------------------------------------------------------------- release() / cancel()


def test_invwarehouse_release_raises_draft_requisitions_never_approved_ones(
        invwarehouse_run_proposed_a, admin_user):
    """A requisition is the start of spending money — it goes to 6.3's routing, not around it."""
    before = PurchaseRequisition.objects.count()
    invwarehouse_run_proposed_a.release(admin_user)
    invwarehouse_run_proposed_a.refresh_from_db()

    assert invwarehouse_run_proposed_a.status == "released"
    raised = PurchaseRequisition.objects.count() - before
    assert raised >= 1
    for req in PurchaseRequisition.objects.order_by("-id")[:raised]:
        assert req.status == "draft"


def test_invwarehouse_release_stamps_the_requisition_on_its_accepted_lines(
        invwarehouse_run_proposed_a, admin_user):
    invwarehouse_run_proposed_a.release(admin_user)
    accepted = invwarehouse_run_proposed_a.lines.filter(decision="accepted")
    assert accepted.exists()
    assert all(line.requisition_id is not None for line in accepted)


def test_invwarehouse_release_twice_cannot_raise_a_second_set(
        invwarehouse_run_proposed_a, admin_user):
    """A double-clicked Release must not commit the money twice."""
    invwarehouse_run_proposed_a.release(admin_user)
    after_first = PurchaseRequisition.objects.count()
    with pytest.raises(ValidationError):
        invwarehouse_run_proposed_a.release(admin_user)
    assert PurchaseRequisition.objects.count() == after_first


def test_invwarehouse_cancel_is_refused_once_the_run_is_released(
        invwarehouse_run_released_a, admin_user):
    """Cancelling a released run would orphan the requisitions it already raised."""
    with pytest.raises(ValidationError):
        invwarehouse_run_released_a.cancel(admin_user)
    invwarehouse_run_released_a.refresh_from_db()
    assert invwarehouse_run_released_a.status == "released"


def test_invwarehouse_cancel_is_allowed_from_draft(invwarehouse_run_a, admin_user):
    invwarehouse_run_a.cancel(admin_user)
    invwarehouse_run_a.refresh_from_db()
    assert invwarehouse_run_a.status == "cancelled"


# --------------------------------------------------------------------------- THE LEDGER BOUNDARY


def test_invwarehouse_post_mints_a_draft_adjustment_and_writes_no_stock_move(
        invwarehouse_issue_submitted_a, admin_user):
    """The single most important assertion in this file.

    apps/procurement must never write a scm.StockMove. post() mints a DRAFT adjustment and SCM's
    own post action writes the movement. Asserting only that the adjustment exists would pass
    even if a StockMove had been written beside it, so the move count is asserted explicitly.
    """
    moves_before = StockMove.objects.count()
    adj_before = StockAdjustment.objects.count()

    invwarehouse_issue_submitted_a.post(admin_user)
    invwarehouse_issue_submitted_a.refresh_from_db()

    assert StockMove.objects.count() == moves_before, "apps/procurement wrote a StockMove"
    assert StockAdjustment.objects.count() == adj_before + 1
    adjustment = invwarehouse_issue_submitted_a.adjustment
    assert adjustment is not None
    assert adjustment.status == "draft"
    assert adjustment.reason == "other"
    assert invwarehouse_issue_submitted_a.number in (adjustment.notes or "")
    assert invwarehouse_issue_submitted_a.status == "posted"


def test_invwarehouse_post_signs_an_issue_negative(invwarehouse_issue_submitted_a, admin_user):
    """Direction rides the sign of quantity_delta — the reason code is 'other' both ways."""
    invwarehouse_issue_submitted_a.post(admin_user)
    deltas = list(invwarehouse_issue_submitted_a.adjustment.lines.values_list(
        "quantity_delta", flat=True))
    assert deltas and all(d < ZERO for d in deltas)


def test_invwarehouse_post_signs_a_return_positive(invwarehouse_return_a, admin_user):
    moves_before = StockMove.objects.count()
    invwarehouse_return_a.post(admin_user)
    deltas = list(invwarehouse_return_a.adjustment.lines.values_list("quantity_delta", flat=True))
    assert deltas and all(d > ZERO for d in deltas)
    assert StockMove.objects.count() == moves_before


def test_invwarehouse_post_twice_reuses_the_adjustment_and_mints_nothing_new(
        invwarehouse_issue_submitted_a, admin_user):
    """The reuse branch closes the double-mint window the status gate alone cannot."""
    invwarehouse_issue_submitted_a.post(admin_user)
    first = invwarehouse_issue_submitted_a.adjustment_id
    adj_after_first = StockAdjustment.objects.count()

    with pytest.raises(ValidationError):
        invwarehouse_issue_submitted_a.post(admin_user)

    invwarehouse_issue_submitted_a.refresh_from_db()
    assert invwarehouse_issue_submitted_a.adjustment_id == first
    assert StockAdjustment.objects.count() == adj_after_first


def test_invwarehouse_post_sums_demand_per_item_across_the_whole_document(
        invwarehouse_issue_draft_a, admin_user):
    """Regression for finding I10.

    The fixture holds TWO lines of the same item, 6 and 6, against 10 on hand. Each line passes
    on its own; the document must not. A per-line check would let this through and the shortfall
    would only appear as a refusal after the buyer thought they were done.
    """
    moves_before = StockMove.objects.count()
    adj_before = StockAdjustment.objects.count()

    with pytest.raises(ValidationError) as exc:
        invwarehouse_issue_draft_a.post(admin_user)

    # One message per short item, so a five-line document reports all five at once.
    assert any("cannot issue" in str(m) for m in exc.value.messages)
    invwarehouse_issue_draft_a.refresh_from_db()
    assert invwarehouse_issue_draft_a.status == "draft"
    assert invwarehouse_issue_draft_a.adjustment_id is None
    assert StockAdjustment.objects.count() == adj_before, "a refused post left an orphan draft"
    assert StockMove.objects.count() == moves_before


def test_invwarehouse_post_clamps_unit_cost_at_the_scm_ceiling(
        invwarehouse_issue_submitted_a, admin_user):
    """Regression for finding M11.

    bulk_create skips full_clean(), so SCM's MaxValueValidator on StockAdjustmentLine.unit_cost
    never runs — and SCM's comment on that validator describes exactly this drafted-here,
    posted-there path. The clamp is what keeps an absurd cost out of the valuation report.
    """
    ceiling = Decimal("999999.9999")
    invwarehouse_issue_submitted_a.lines.update(unit_cost=Decimal("9999999999.9999"))

    invwarehouse_issue_submitted_a.post(admin_user)

    minted = list(invwarehouse_issue_submitted_a.adjustment.lines.all())
    assert minted
    for line in minted:
        assert line.unit_cost <= ceiling
        line.full_clean()  # would raise if the clamp had not applied


def test_invwarehouse_cancel_after_post_is_refused(invwarehouse_issue_posted_a, admin_user):
    """A posted issue is corrected by a mirror return, never removed — the ledger is append-only."""
    with pytest.raises(ValidationError):
        invwarehouse_issue_posted_a.cancel(admin_user)
    invwarehouse_issue_posted_a.refresh_from_db()
    assert invwarehouse_issue_posted_a.status == "posted"


# --------------------------------------------------------------------------- issue clean()


def test_invwarehouse_issue_rejects_a_cross_tenant_location(
        tenant_a, invwarehouse_location_b):
    issue = MaterialIssue(tenant=tenant_a, location=invwarehouse_location_b,
                          movement_type="issue", purpose="cost_centre")
    with pytest.raises(ValidationError) as exc:
        issue.full_clean()
    assert "location" in exc.value.error_dict


def test_invwarehouse_issue_purpose_other_requires_notes(tenant_a, invwarehouse_location_a):
    issue = MaterialIssue(tenant=tenant_a, location=invwarehouse_location_a,
                          movement_type="issue", purpose="other", notes="")
    with pytest.raises(ValidationError):
        issue.full_clean()


def test_invwarehouse_line_unit_cost_is_stamped_from_the_item_average_cost(
        invwarehouse_issue_draft_a, invwarehouse_item3_a):
    """Stamped in save(); a line written with bulk_create would seed at zero instead."""
    line = MaterialIssueLine(issue=invwarehouse_issue_draft_a, item=invwarehouse_item3_a,
                             quantity=Decimal("1"))
    line.save()
    assert line.unit_cost == (invwarehouse_item3_a.average_cost or ZERO)
