"""Inventory 5.15 Quality Control — model tests.

The lifecycle documents (QuarantineOrder / DefectReport) post REAL StockMove legs, so
the ledger-integrity battery is the core of this file: refusals must leave the book
untouched, reversals must balance, and shortfalls — including LOT-SCOPED ones — must be
caught before any leg is written.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone as tz

from apps.inventory.models import (
    DefectReport,
    QcChecklist,
    QcChecklistItem,
    QcRoutingRule,
    QuarantineOrder,
    resolve_qc_routing,
)
from apps.scm.models import LotSerial, StockMove


def _on_hand(item, location, lot=None):
    qs = StockMove.objects.filter(tenant_id=item.tenant_id, item=item, location=location)
    if lot is not None:
        qs = qs.filter(lot_serial=lot)
    return qs.aggregate(q=Sum_q())["q"] or Decimal("0")


def Sum_q():
    from django.db.models import Sum
    return Sum("quantity")


def _drain(item, location, quantity, lot=None):
    """External drain so a guarded action hits its shortfall branch."""
    StockMove.objects.create(
        tenant_id=item.tenant_id, item=item, location=location, lot_serial=lot,
        quantity=-Decimal(quantity), unit_cost=Decimal("0"), move_type="adjustment",
        reference="TEST-DRAIN", moved_at=tz.now())


def _legs(order):
    return list(StockMove.objects.filter(tenant_id=order.tenant_id, reference=order.number))


# ---------------------------------------------------------------- quarantine lifecycle


@pytest.mark.django_db
def test_quarantine_twice_refused_and_no_double_posting(qrd_quarantined_a):
    with pytest.raises(ValidationError) as exc:
        qrd_quarantined_a.quarantine(None)
    assert "quarantined" in str(exc.value).lower()
    assert len(_legs(qrd_quarantined_a)) == 2  # still only the original pair


@pytest.mark.django_db
def test_release_from_draft_refused_posts_nothing(qrd_draft_a, item_a, qc_warehouse_a):
    before = _on_hand(item_a, qc_warehouse_a)
    with pytest.raises(ValidationError):
        qrd_draft_a.release(None)
    assert qrd_draft_a.status == "draft"
    assert _legs(qrd_draft_a) == []
    assert _on_hand(item_a, qc_warehouse_a) == before


@pytest.mark.django_db
def test_scrap_from_draft_refused_posts_nothing(qrd_draft_a):
    with pytest.raises(ValidationError):
        qrd_draft_a.scrap(None)
    assert qrd_draft_a.status == "draft"
    assert _legs(qrd_draft_a) == []


@pytest.mark.django_db
def test_cancel_from_draft_is_paper_only(qrd_draft_a, qc_stocked_a):
    obj = qrd_draft_a.cancel(None)
    assert obj.status == "cancelled"
    assert obj.resolved_at is not None
    assert _legs(obj) == []


@pytest.mark.django_db
def test_cancel_from_held_reverses_pair_and_returns_stock(
        qrd_quarantined_a, item_a, qc_warehouse_a):
    # The fixture chain already walked quarantine(): the 2 units are OUT of source now.
    before = _on_hand(item_a, qc_warehouse_a)
    obj = qrd_quarantined_a.cancel(None)
    assert obj.status == "cancelled"
    legs = _legs(obj)
    assert len(legs) == 4  # hold pair + reversal pair
    assert _on_hand(item_a, qc_warehouse_a) == before + obj.quantity


@pytest.mark.django_db
@pytest.mark.parametrize("finish_with", ["release", "scrap"])
def test_cancel_after_terminal_state_refused(qrd_quarantined_a, finish_with, qc_stocked_a):
    getattr(qrd_quarantined_a, finish_with)(None)
    with pytest.raises(ValidationError):
        qrd_quarantined_a.cancel(None)


@pytest.mark.django_db
def test_release_is_value_neutral_at_average_cost(
        qrd_draft_a, qc_stocked_a, item_a, qc_warehouse_a):
    average = item_a.average_cost or Decimal("0")
    qrd_draft_a.quarantine(None)
    qrd_draft_a.release(None)
    back_legs = [m for m in _legs(qrd_draft_a) if m.quantity > 0]
    # legs are newest-first: [0] is the release-back-in leg at the source.
    assert back_legs[0].location_id == qc_warehouse_a.pk
    assert back_legs[0].unit_cost == average
    assert _on_hand(item_a, qc_warehouse_a) >= qrd_draft_a.quantity


@pytest.mark.django_db
def test_shortfall_at_source_blocks_hold(qrd_draft_a, qc_stocked_a, item_a, qc_warehouse_a):
    _drain(item_a, qc_warehouse_a, "9")  # only 1 left; order wants 2
    with pytest.raises(ValidationError):
        qrd_draft_a.quarantine(None)
    assert qrd_draft_a.status == "draft"
    assert _legs(qrd_draft_a) == []


@pytest.mark.django_db
def test_shortfall_at_zone_blocks_release(qrd_quarantined_a, item_a, qc_zone_a):
    _drain(item_a, qc_zone_a, "2")
    with pytest.raises(ValidationError, match="Cannot return from quarantine"):
        qrd_quarantined_a.release(None)
    assert qrd_quarantined_a.status == "quarantined"


@pytest.mark.django_db
def test_shortfall_at_zone_blocks_scrap(qrd_quarantined_a, item_a, qc_zone_a):
    _drain(item_a, qc_zone_a, "2")
    with pytest.raises(ValidationError):
        qrd_quarantined_a.scrap(None)
    assert qrd_quarantined_a.status == "quarantined"


@pytest.mark.django_db
def test_shortfall_at_zone_blocks_cancel_from_held(qrd_quarantined_a, item_a, qc_zone_a):
    _drain(item_a, qc_zone_a, "2")
    with pytest.raises(ValidationError, match="Cannot return from quarantine"):
        qrd_quarantined_a.cancel(None)


@pytest.mark.django_db
def test_lot_scoped_shortfall_location_total_does_not_count(
        tenant_a, item_a, qc_warehouse_a, qc_zone_a):
    """Location holds A=3 + B=7; holding 5 of lot A must refuse despite 10 on site."""
    lot_a = LotSerial.objects.create(tenant=tenant_a, item=item_a, number="LOT-A")
    lot_b = LotSerial.objects.create(tenant=tenant_a, item=item_a, number="LOT-B")
    for lot, qty in [(lot_a, "3"), (lot_b, "7")]:
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=qc_warehouse_a, lot_serial=lot,
            quantity=Decimal(qty), unit_cost=Decimal("4"), move_type="receipt",
            reference="OPENING-QC", moved_at=tz.now())
    order = QuarantineOrder.objects.create(
        tenant=tenant_a, item=item_a, lot_serial=lot_a,
        source_location=qc_warehouse_a, quarantine_location=qc_zone_a,
        quantity=Decimal("5.0000"))
    with pytest.raises(ValidationError):
        order.quarantine(None)
    assert order.status == "draft"


@pytest.mark.django_db
def test_lot_tracked_hold_stamps_lot_on_every_leg(
        tenant_a, item_a, qc_warehouse_a, qc_zone_a, qc_stocked_a):
    lot = LotSerial.objects.create(tenant=tenant_a, item=item_a, number="LOT-X")
    StockMove.objects.create(
        tenant=tenant_a, item=item_a, location=qc_warehouse_a, lot_serial=lot,
        quantity=Decimal("4"), unit_cost=Decimal("4"), move_type="receipt",
        reference="OPENING-QC", moved_at=tz.now())
    order = QuarantineOrder.objects.create(
        tenant=tenant_a, item=item_a, lot_serial=lot,
        source_location=qc_warehouse_a, quarantine_location=qc_zone_a,
        quantity=Decimal("2.0000"))
    order.quarantine(None)
    order.release(None)
    for leg in _legs(order):
        assert leg.lot_serial_id == lot.pk


@pytest.mark.django_db
def test_scrap_posts_single_negative_adjustment(qrd_quarantined_a, item_a, qc_zone_a):
    obj = qrd_quarantined_a.scrap(None)
    assert obj.status == "scrapped"
    assert obj.resolved_at is not None
    legs = _legs(obj)
    assert len(legs) == 3  # hold pair + one write-off
    write_off = [m for m in legs if m.move_type == "adjustment"]
    assert len(write_off) == 1
    assert write_off[0].quantity == -obj.quantity
    assert write_off[0].location_id == qc_zone_a.pk


@pytest.mark.django_db
def test_clean_rejects_same_source_and_zone(tenant_a, item_a, qc_warehouse_a):
    order = QuarantineOrder(tenant=tenant_a, item=item_a,
                            source_location=qc_warehouse_a,
                            quarantine_location=qc_warehouse_a,
                            quantity=Decimal("1.0000"))
    with pytest.raises(ValidationError) as exc:
        order.full_clean()
    assert "quarantine_location" in exc.value.message_dict


@pytest.mark.django_db
def test_clean_rejects_foreign_zone(tenant_a, item_a, qc_warehouse_a, qc_zone_b):
    order = QuarantineOrder(tenant=tenant_a, item=item_a,
                            source_location=qc_warehouse_a,
                            quarantine_location=qc_zone_b, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as exc:
        order.full_clean()
    assert "quarantine_location" in exc.value.message_dict


@pytest.mark.django_db
def test_clean_rejects_foreign_item(tenant_a, item_b, qc_warehouse_a, qc_zone_a):
    order = QuarantineOrder(tenant=tenant_a, item=item_b,
                            source_location=qc_warehouse_a,
                            quarantine_location=qc_zone_a, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as exc:
        order.full_clean()
    assert "item" in exc.value.message_dict


@pytest.mark.django_db
def test_clean_rejects_lot_of_another_item(
        tenant_a, item_a, item_b, qc_warehouse_a, qc_zone_a):
    foreign_lot = LotSerial.objects.create(tenant=tenant_a, item=item_b, number="F-1")
    order = QuarantineOrder(tenant=tenant_a, item=item_a, lot_serial=foreign_lot,
                            source_location=qc_warehouse_a,
                            quarantine_location=qc_zone_a, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as exc:
        order.full_clean()
    assert "lot_serial" in exc.value.message_dict


@pytest.mark.django_db
def test_str_and_status_css_and_editable(qrd_quarantined_a, qrd_draft_a):
    assert str(qrd_quarantined_a).startswith(qrd_quarantined_a.number)
    assert qrd_quarantined_a.item.sku in str(qrd_quarantined_a)
    assert qrd_quarantined_a.status_css == "badge-amber"
    assert {s for s, _ in QuarantineOrder.STATUS_CHOICES} == set(QuarantineOrder.STATUS_CSS)
    assert qrd_draft_a.is_editable is True
    assert qrd_quarantined_a.is_editable is False


# ---------------------------------------------------------------- defect reports


@pytest.mark.django_db
def test_defect_writeoff_twice_second_refused(defect_written_off_a, qc_stocked_a):
    with pytest.raises(ValidationError) as exc:
        defect_written_off_a.writeoff(None)
    assert "written off" in str(exc.value).lower()
    adjustment_legs = [m for m in _legs(defect_written_off_a) if m.move_type == "adjustment"]
    assert len(adjustment_legs) == 1


@pytest.mark.django_db
def test_defect_writeoff_shortfall_keeps_open(defect_open_a, qc_stocked_a, item_a, qc_warehouse_a):
    _drain(item_a, qc_warehouse_a, "10")  # everything gone
    with pytest.raises(ValidationError):
        defect_open_a.writeoff(None)
    assert defect_open_a.status == "open"
    assert _legs(defect_open_a) == []


@pytest.mark.django_db
def test_defect_writeoff_lot_scoped_shortfall(
        tenant_a, item_a, qc_warehouse_a, qc_zone_a, qc_stocked_a):
    other = LotSerial.objects.create(tenant=tenant_a, item=item_a, number="OTHER")
    report = DefectReport.objects.create(
        tenant=tenant_a, item=item_a, location=qc_warehouse_a, lot_serial=other,
        quantity=Decimal("1.0000"))
    # plenty unscoped stock exists, but NONE of it is `other`'s lot
    with pytest.raises(ValidationError):
        report.writeoff(None)
    assert report.status == "open"


@pytest.mark.django_db
def test_defect_close_leaves_no_ledger_trace(defect_open_a, qc_stocked_a):
    moves_before = StockMove.objects.filter(tenant_id=defect_open_a.tenant_id).count()
    obj = defect_open_a.close(None)
    assert obj.status == "closed"
    assert obj.resolved_at is not None
    assert obj.posts_stock is False
    assert StockMove.objects.filter(tenant_id=obj.tenant_id).count() == moves_before


@pytest.mark.django_db
def test_defect_posts_stock_truth_table(defect_open_a, defect_written_off_a):
    assert defect_open_a.posts_stock is False  # open: nothing decided yet
    assert defect_written_off_a.posts_stock is True


@pytest.mark.django_db
def test_defect_photo_href_precedence(tenant_a, item_a, qc_warehouse_a):
    report = DefectReport(tenant=tenant_a, item=item_a, location=qc_warehouse_a,
                          quantity=Decimal("1"), photo_url="https://files.example.com/d.jpg")
    assert report.photo_href == "https://files.example.com/d.jpg"
    empty = DefectReport(tenant=tenant_a, item=item_a, location=qc_warehouse_a,
                         quantity=Decimal("1"))
    assert empty.photo_href == ""


@pytest.mark.django_db
def test_defect_clean_rejects_bad_image_extension(tenant_a, item_a, qc_warehouse_a):
    report = DefectReport(tenant=tenant_a, item=item_a, location=qc_warehouse_a,
                          quantity=Decimal("1"), photo_url="")
    # FileField content isn't opened by clean(); simulate via name check path used by clean()
    class FakeFile(str):
        @property
        def name(self):
            return str(self)
    report.photo = FakeFile("evil.exe")
    with pytest.raises(ValidationError) as exc:
        report.full_clean()
    assert "photo" in exc.value.message_dict


@pytest.mark.django_db
def test_defect_clean_rejects_foreign_ncr(tenant_a, item_a, qc_warehouse_a, tenant_b):
    from apps.scm.models import NonConformance
    foreign_ncr = NonConformance.objects.create(
        tenant=tenant_b, source="internal", title="Foreign", description="x",
        detected_on=tz.now().date())
    report = DefectReport(tenant=tenant_a, item=item_a, location=qc_warehouse_a,
                          quantity=Decimal("1"), ncr=foreign_ncr)
    with pytest.raises(ValidationError) as exc:
        report.full_clean()
    assert "ncr" in exc.value.message_dict


@pytest.mark.django_db
def test_defect_str_and_status_css(defect_open_a):
    assert str(defect_open_a).startswith(defect_open_a.number)
    assert defect_open_a.status_css == "badge-amber"
    assert {s for s, _ in DefectReport.STATUS_CHOICES} == set(DefectReport.STATUS_CSS)


# ---------------------------------------------------------------- resolver determinism


@pytest.mark.django_db
def test_resolver_vendor_pinned_never_fires_blind(
        tenant_a, item_a, qc_zone_a, qc_rule_catchall_a):
    vendor_rule = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Vendor-only", verdict="inspect",
        qc_location=qc_zone_a, priority=1, vendor=_vendor_for(tenant_a))
    # No vendor context: the pinned rule cannot fire — the engine falls to the next tier
    # (here the catch-all) or refuses outright when nothing else matches.
    rule, verdict, zone, blind_reason = resolve_qc_routing(item_a)
    assert rule is None or rule.pk != vendor_rule.pk
    assert blind_reason.startswith("No Rule Matched") or (rule is not None and rule.pk == qc_rule_catchall_a.pk)


def _vendor_for(tenant):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name="Acme Vendor", kind="company")
    PartyRole.objects.create(tenant=tenant, party=party, role="vendor")
    return party


@pytest.mark.django_db
def test_resolver_vendor_specific_beats_vendor_agnostic(
        tenant_a, item_a, qc_zone_a, qc_rule_catchall_a):
    vendor = _vendor_for(tenant_a)
    generic = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Generic inspect", verdict="bypass", priority=5)
    pinned = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Pinned inspect", verdict="inspect",
        qc_location=qc_zone_a, priority=5, vendor=vendor)
    rule, verdict, _, reason = resolve_qc_routing(item_a, vendor=vendor)
    assert rule.pk == pinned.pk
    assert verdict == "inspect"
    assert "vendor-pinned" in reason


@pytest.mark.django_db
def test_resolver_tiering_item_beats_category_beats_catchall(
        tenant_a, item_a, qc_zone_a, qc_rule_catchall_a):
    category_rule = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Category bypass", category=item_a.category,
        verdict="bypass", priority=1)
    item_rule = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Item inspect", item=item_a, verdict="inspect",
        qc_location=qc_zone_a, priority=50)
    rule, verdict, zone, _ = resolve_qc_routing(item_a)
    assert rule.pk == item_rule.pk and verdict == "inspect" and zone.pk == qc_zone_a.pk
    item_rule.is_active = False
    item_rule.save()
    rule, verdict, _, _ = resolve_qc_routing(item_a)
    assert rule.pk == category_rule.pk and verdict == "bypass"
    category_rule.delete()
    rule, verdict, _, _ = resolve_qc_routing(item_a)
    assert rule.pk == qc_rule_catchall_a.pk


@pytest.mark.django_db
def test_resolver_priority_then_id_tiebreak(tenant_a, item_a, qc_zone_a, qc_stocked_a):
    low_priority_first = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Lower priority wins", item=item_a, verdict="inspect",
        qc_location=qc_zone_a, priority=3)
    later_tie = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Same priority later id", item=item_a, verdict="bypass",
        priority=3)
    rule, _, _, _ = resolve_qc_routing(item_a)
    assert rule.pk == low_priority_first.pk
    later_tie.delete()
    low_priority_first.delete()


@pytest.mark.django_db
def test_resolver_inactive_rules_skipped_on_db_path(
        tenant_a, item_a, qc_zone_a, qc_rule_catchall_a):
    qc_rule_catchall_a.is_active = False
    qc_rule_catchall_a.save()
    rule, verdict, zone, reason = resolve_qc_routing(item_a)
    assert rule is None
    assert reason.startswith("No Rule Matched")


@pytest.mark.django_db
def test_resolver_filters_foreign_rows_from_caller_list(
        tenant_a, tenant_b, item_a, qc_zone_a, qc_rule_catchall_a):
    foreign = QcRoutingRule.objects.create(
        tenant=tenant_b, name="Foreign catch-all", verdict="inspect",
        qc_location=qc_zone_a, priority=1)
    rule, _, _, _ = resolve_qc_routing(item_a, rules=[qc_rule_catchall_a, foreign])
    assert rule.pk == qc_rule_catchall_a.pk


@pytest.mark.django_db
def test_resolver_inspect_populates_zone_bypass_none_and_guards(
        tenant_a, item_a, qc_zone_a, qc_warehouse_a):
    inspect_rule = QcRoutingRule.objects.create(
        tenant=tenant_a, name="I", verdict="inspect", qc_location=qc_zone_a, priority=1)
    rule, verdict, zone, _ = resolve_qc_routing(item_a)
    assert zone.pk == qc_zone_a.pk
    inspect_rule.verdict = "bypass"
    inspect_rule.save()
    rule, verdict, zone, _ = resolve_qc_routing(item_a)
    assert verdict == "bypass" and zone is None
    rule, verdict, zone, reason = resolve_qc_routing(None)
    assert rule is None and reason.startswith("No Rule Matched")


# ---------------------------------------------------------------- checklists


@pytest.mark.django_db
def test_checklist_applies_to_matrix(tenant_a, item_a):
    from apps.core.models import Party, PartyRole
    vendor = Party.objects.create(tenant=tenant_a, name="V", kind="company")
    PartyRole.objects.create(tenant=tenant_a, party=vendor, role="vendor")

    neither = QcChecklist.objects.create(tenant=tenant_a, name="Neither")
    assert neither.applies_to == "Workspace-wide"

    vendor_only = QcChecklist.objects.create(tenant=tenant_a, name="VO", vendor=vendor)
    assert vendor_only.applies_to == "Vendor: V"

    both = QcChecklist.objects.create(tenant=tenant_a, name="Both", item=item_a, vendor=vendor)
    assert item_a.sku in both.applies_to
    assert "·" in both.applies_to
    assert vendor.name in both.applies_to


@pytest.mark.django_db
def test_checklist_items_order_by_sequence_then_id(qc_checklist_a):
    labels = [i.label for i in qc_checklist_a.checklist_items.all()]
    assert labels == ["Seal intact", "Count matches"]


@pytest.mark.django_db
def test_checklist_clean_rejects_foreign_vendor(tenant_a, tenant_b):
    from apps.core.models import Party, PartyRole
    foreign = Party.objects.create(tenant=tenant_b, name="Foreign V", kind="company")
    PartyRole.objects.create(tenant=tenant_b, party=foreign, role="vendor")
    checklist = QcChecklist(tenant=tenant_a, name="X", vendor=foreign)
    with pytest.raises(ValidationError) as exc:
        checklist.full_clean()
    assert "vendor" in exc.value.message_dict


@pytest.mark.django_db
def test_checklist_str(qc_checklist_a):
    item = qc_checklist_a.checklist_items.first()
    assert qc_checklist_a.name in str(item)
