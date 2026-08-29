"""Procurement 6.11 - Order Fulfillment & Tracking model tests.

Load-bearing contracts covered here:

* per-tenant ``ASN-`` / ``DSC-`` / ``BKO-`` auto-numbering (sequence, prefix, no cross-tenant
  collision) and the blank ``number`` on an unsaved instance;
* every STATUS / SOURCE / FREIGHT_TERMS / CONDITION / REASON / MODE / RISK choice value and the
  colour-only badge maps (a semantic ``badge-success`` renders unstyled - L33);
* the guarded verb ladders - ``AdvancedShipmentNotice.submit/mark_in_transit/confirm_delivery/
  cancel`` and ``Backorder.reschedule/fulfil/cancel/raise_alert`` - each of which re-checks its own
  guard inside the method so a double-submit is a no-op that re-stamps nothing;
* ``DeliverySchedule.status`` being a deliberately ORDINARY editable field (it hangs no
  timestamps) while the ASN's and the backorder's are ``editable=False``;
* ``clean()`` boundaries: cross-tenant FKs, duplicate live supplier references, outbound
  shipments, over-commitment of a PO line, and backordering more than was ordered;
* and - the invariant this sub-module lives or dies on - that every quantity/coverage/ageing
  figure is DERIVED by aggregate or arithmetic at read time and is NOT a stored, editable column
  (L29): ``line_scheduled_total``, ``coverage_pct``, ``remaining_quantity``,
  ``outstanding_at_declare``, ``total_quantity_shipped``, ``days_open`` and the risk buckets.

Determinism (L16): every date basis here is ``timezone.localdate()`` - the same basis the model
properties use - and every datetime basis is ``timezone.now()``. ``datetime.date.today()`` never
appears, or the exact-date assertions flake for the hours after local midnight.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    AdvancedShipmentNotice,
    AsnLine,
    Backorder,
    DeliverySchedule,
    ProcurementAlert,
    split_po_line,
)

pytestmark = pytest.mark.django_db


# -- local helpers ------------------------------------------------------------------------------
# Named _fulfillment_* so a later sub-module appending near this file cannot shadow them. The
# conftest factories of the same shape are not importable across test modules, so bulk rows and
# the odd spine document are minted here.

#: theme.css ships exactly these modifier classes. Anything else renders completely unstyled.
_FULFILLMENT_BADGE_COLOURS = {
    "badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted", "badge-slate",
}


def _fulfillment_today():
    """The SAME basis every model property compares against (L16)."""
    return timezone.localdate()


def _fulfillment_days(count):
    return datetime.timedelta(days=count)


def _fulfillment_new_po(tenant, vendor, **overrides):
    """A second approved spine PO in the same tenant - the 'different order' rejection case."""
    from apps.scm.models import PurchaseOrder

    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=_fulfillment_today())
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _fulfillment_new_po_line(po, description="Spare coupling", qty="5", price="12.00", **kw):
    from apps.scm.models import PurchaseOrderLine

    fields = dict(purchase_order=po, item_description=description, quantity=Decimal(qty),
                  unit_price=Decimal(price), sku_hint="CPL-1", uom_hint="EA")
    fields.update(kw)
    return PurchaseOrderLine.objects.create(**fields)


def _fulfillment_receive(tenant, po, po_line, quantity):
    """Book a (non-cancelled) goods receipt against a PO line on the SCM spine.

    6.11 is read-only against that spine; this exists purely so the tests can move
    ``po_line.outstanding_quantity()`` and prove ``AsnLine.outstanding_at_declare`` follows it
    live instead of caching a stored copy.
    """
    from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote

    grn = GoodsReceiptNote.objects.create(tenant=tenant, purchase_order=po,
                                          receipt_date=_fulfillment_today())
    GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=po_line,
                                    quantity_received=Decimal(quantity))
    return grn


def _fulfillment_asn(tenant, po, **overrides):
    fields = dict(tenant=tenant, purchase_order=po)
    fields.update(overrides)
    return AdvancedShipmentNotice.objects.create(**fields)


def _fulfillment_schedule(tenant, po_line, **overrides):
    fields = dict(tenant=tenant, po_line=po_line, scheduled_quantity=Decimal("2"),
                  need_by_date=_fulfillment_today() + _fulfillment_days(5))
    fields.update(overrides)
    return DeliverySchedule.objects.create(**fields)


def _fulfillment_backorder(tenant, po_line, **overrides):
    fields = dict(tenant=tenant, po_line=po_line, quantity_backordered=Decimal("1"))
    fields.update(overrides)
    return Backorder.objects.create(**fields)


def _fulfillment_field(model, name):
    return model._meta.get_field(name)


def _fulfillment_concrete_names(model):
    return {f.name for f in model._meta.get_fields()}


# ================================================================================================
# 1. AdvancedShipmentNotice - defaults, numbering, str, choices
# ================================================================================================

def test_fulfillment_asn_minimal_create_takes_every_documented_default(tenant_a,
                                                                      fulfillment_po_a):
    asn = AdvancedShipmentNotice.objects.create(tenant=tenant_a,
                                                purchase_order=fulfillment_po_a)

    assert asn.status == "draft"
    assert asn.source == "manual"
    assert asn.supplier_reference == ""
    assert asn.carrier_id is None
    assert asn.carrier_name == ""
    assert asn.tracking_number == ""
    assert asn.shipment_id is None
    assert asn.freight_terms == ""
    assert asn.bill_of_lading_ref == ""
    assert asn.container_ref == ""
    assert asn.package_count is None
    assert asn.pallet_count is None
    assert asn.gross_weight_kg is None
    assert asn.volume_cbm is None
    assert asn.ship_date is None
    assert asn.expected_delivery_date is None
    assert asn.notes == ""
    # The verb-written block starts entirely empty.
    assert asn.submitted_at is None
    assert asn.delivered_at is None
    assert asn.arrival_condition == ""
    assert asn.pod_reference == ""
    assert asn.received_signature_name == ""
    assert asn.confirmed_by_id is None
    assert asn.cancelled_at is None
    assert asn.cancellation_reason == ""


def test_fulfillment_asn_number_is_blank_until_saved(tenant_a, fulfillment_po_a):
    unsaved = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a)
    assert unsaved.number == ""
    unsaved.save()
    assert unsaved.number == "ASN-00001"


def test_fulfillment_asn_number_prefix_and_five_digit_padding(tenant_a, fulfillment_po_a):
    assert AdvancedShipmentNotice.NUMBER_PREFIX == "ASN"
    first = _fulfillment_asn(tenant_a, fulfillment_po_a)
    second = _fulfillment_asn(tenant_a, fulfillment_po_a)
    third = _fulfillment_asn(tenant_a, fulfillment_po_a)
    assert [first.number, second.number, third.number] == ["ASN-00001", "ASN-00002", "ASN-00003"]


def test_fulfillment_asn_numbers_do_not_collide_across_tenants(tenant_a, tenant_b,
                                                               fulfillment_po_a,
                                                               fulfillment_po_b):
    a_one = _fulfillment_asn(tenant_a, fulfillment_po_a)
    b_one = _fulfillment_asn(tenant_b, fulfillment_po_b)
    a_two = _fulfillment_asn(tenant_a, fulfillment_po_a)

    assert a_one.number == "ASN-00001"
    assert b_one.number == "ASN-00001"   # tenant B restarts its own sequence
    assert a_two.number == "ASN-00002"
    assert b_one.tenant_id == tenant_b.pk


def test_fulfillment_asn_str_folds_number_and_order_number(fulfillment_asn_draft_a):
    expected = "%s · %s" % (fulfillment_asn_draft_a.number,
                                 fulfillment_asn_draft_a.purchase_order.number)
    assert str(fulfillment_asn_draft_a) == expected


def test_fulfillment_asn_status_choices_are_the_five_documented_values():
    assert AdvancedShipmentNotice.STATUS_CHOICES == [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]


def test_fulfillment_asn_status_tuples_partition_the_lifecycle():
    assert AdvancedShipmentNotice.OPEN_STATUSES == ("draft", "submitted", "in_transit")
    assert AdvancedShipmentNotice.IN_FLIGHT_STATUSES == ("submitted", "in_transit")
    assert AdvancedShipmentNotice.EDITABLE_STATUSES == ("draft", "submitted", "in_transit")
    values = {value for value, _ in AdvancedShipmentNotice.STATUS_CHOICES}
    for group in (AdvancedShipmentNotice.OPEN_STATUSES,
                  AdvancedShipmentNotice.IN_FLIGHT_STATUSES,
                  AdvancedShipmentNotice.EDITABLE_STATUSES):
        assert set(group) <= values


def test_fulfillment_asn_source_choices_cover_portal_email_edi_manual():
    assert [value for value, _ in AdvancedShipmentNotice.SOURCE_CHOICES] == [
        "portal", "email", "edi", "manual"]


def test_fulfillment_asn_freight_terms_choices():
    assert [value for value, _ in AdvancedShipmentNotice.FREIGHT_TERMS_CHOICES] == [
        "prepaid", "collect", "third_party", "prepaid_and_charged"]


def test_fulfillment_asn_condition_choices():
    assert [value for value, _ in AdvancedShipmentNotice.CONDITION_CHOICES] == [
        "good", "damaged", "partial", "refused"]


def test_fulfillment_asn_badge_maps_use_colour_named_classes_only():
    for mapping in (AdvancedShipmentNotice.STATUS_CSS, AdvancedShipmentNotice.CONDITION_CSS,
                    AdvancedShipmentNotice.DISCREPANCY_CSS, AdvancedShipmentNotice.SOURCE_CSS):
        assert set(mapping.values()) <= _FULFILLMENT_BADGE_COLOURS


def test_fulfillment_asn_badge_maps_cover_every_choice_value():
    assert set(AdvancedShipmentNotice.STATUS_CSS) == {
        v for v, _ in AdvancedShipmentNotice.STATUS_CHOICES}
    assert set(AdvancedShipmentNotice.CONDITION_CSS) == {
        v for v, _ in AdvancedShipmentNotice.CONDITION_CHOICES}
    assert set(AdvancedShipmentNotice.SOURCE_CSS) == {
        v for v, _ in AdvancedShipmentNotice.SOURCE_CHOICES}
    assert AdvancedShipmentNotice.DISCREPANCY_CSS == {
        "ok": "badge-green", "short": "badge-amber",
        "over": "badge-info", "mixed": "badge-red"}


def test_fulfillment_asn_meta_ordering_and_unique_together():
    assert AdvancedShipmentNotice._meta.ordering == ["-created_at", "-id"]
    assert AdvancedShipmentNotice._meta.unique_together == (("tenant", "number"),)


def test_fulfillment_asn_unique_together_with_tenant_is_enforced(tenant_a, tenant_b,
                                                                 fulfillment_po_a,
                                                                 fulfillment_po_b):
    first = _fulfillment_asn(tenant_a, fulfillment_po_a)
    # Same number in ANOTHER tenant is fine - the constraint is scoped, not global.
    twin = AdvancedShipmentNotice(tenant=tenant_b, purchase_order=fulfillment_po_b,
                                  number=first.number)
    twin.save()
    assert twin.pk is not None

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AdvancedShipmentNotice.objects.create(
                tenant=tenant_a, purchase_order=fulfillment_po_a, number=first.number)


def test_fulfillment_asn_system_columns_are_not_editable():
    for name in ("number", "status", "delivered_at", "arrival_condition", "pod_reference",
                 "received_signature_name", "confirmed_by", "created_by", "submitted_at",
                 "cancelled_at", "cancellation_reason"):
        assert _fulfillment_field(AdvancedShipmentNotice, name).editable is False, name


def test_fulfillment_asn_buyer_typed_columns_stay_editable():
    for name in ("purchase_order", "supplier_reference", "source", "ship_date",
                 "expected_delivery_date", "carrier", "carrier_name", "tracking_number",
                 "shipment", "freight_terms", "package_count", "pallet_count",
                 "gross_weight_kg", "volume_cbm", "notes"):
        assert _fulfillment_field(AdvancedShipmentNotice, name).editable is True, name


# ================================================================================================
# 2. AdvancedShipmentNotice - computed properties
# ================================================================================================

@pytest.mark.parametrize("status,editable,is_open,in_flight", [
    ("draft", True, True, False),
    ("submitted", True, True, True),
    ("in_transit", True, True, True),
    ("delivered", False, False, False),
    ("cancelled", False, False, False),
])
def test_fulfillment_asn_lifecycle_flags_track_status(tenant_a, fulfillment_po_a, status,
                                                      editable, is_open, in_flight):
    asn = _fulfillment_asn(tenant_a, fulfillment_po_a, status=status)
    assert asn.is_editable is editable
    assert asn.is_open is is_open
    assert asn.is_in_flight is in_flight


def test_fulfillment_asn_is_late_and_days_late_measure_from_localdate(fulfillment_asn_late_a):
    assert fulfillment_asn_late_a.is_late is True
    assert fulfillment_asn_late_a.days_late == 3


def test_fulfillment_asn_future_eta_is_not_late(fulfillment_asn_in_transit_a):
    assert fulfillment_asn_in_transit_a.is_late is False
    assert fulfillment_asn_in_transit_a.days_late == 0


def test_fulfillment_asn_delivered_row_is_never_late(tenant_a, fulfillment_po_a):
    asn = _fulfillment_asn(tenant_a, fulfillment_po_a, status="delivered",
                           expected_delivery_date=_fulfillment_today() - _fulfillment_days(9))
    assert asn.is_late is False
    assert asn.days_late == 0


def test_fulfillment_asn_without_expected_date_is_not_late(tenant_a, fulfillment_po_a):
    asn = _fulfillment_asn(tenant_a, fulfillment_po_a, status="in_transit",
                           expected_delivery_date=None)
    assert asn.is_late is False
    assert asn.days_late == 0


def test_fulfillment_asn_tracking_reads_the_linked_shipment_projections(
        tenant_a, fulfillment_po_a, fulfillment_shipment_inbound_a):
    asn = _fulfillment_asn(tenant_a, fulfillment_po_a, status="in_transit",
                           shipment=fulfillment_shipment_inbound_a,
                           expected_delivery_date=_fulfillment_today() + _fulfillment_days(3))
    assert asn.tracking_status_text == "In Transit"
    assert asn.location_display == "Rotterdam hub"
    assert asn.eta_display == fulfillment_shipment_inbound_a.eta


def test_fulfillment_asn_tracking_falls_back_to_its_own_labels_without_a_shipment(
        fulfillment_asn_draft_a):
    assert fulfillment_asn_draft_a.shipment_id is None
    assert fulfillment_asn_draft_a.tracking_status_text == "Draft"
    assert fulfillment_asn_draft_a.location_display == ""
    assert fulfillment_asn_draft_a.eta_display == fulfillment_asn_draft_a.expected_delivery_date


def test_fulfillment_asn_carrier_display_prefers_the_tms_profile(tenant_a, fulfillment_po_a,
                                                                 fulfillment_carrier_a):
    linked = _fulfillment_asn(tenant_a, fulfillment_po_a, carrier=fulfillment_carrier_a,
                              carrier_name="Ignored courier text")
    assert linked.carrier_display == fulfillment_carrier_a.name == "Acme Road Freight"


def test_fulfillment_asn_carrier_display_falls_back_to_free_text(fulfillment_asn_draft_a):
    assert fulfillment_asn_draft_a.carrier_id is None
    assert fulfillment_asn_draft_a.carrier_display == "Northwind Express"


def test_fulfillment_asn_status_source_condition_css_helpers(fulfillment_asn_delivered_a):
    assert fulfillment_asn_delivered_a.status_css == "badge-green"
    assert fulfillment_asn_delivered_a.source_css == "badge-muted"
    assert fulfillment_asn_delivered_a.condition_css == "badge-green"


def test_fulfillment_asn_css_helpers_fall_back_to_slate_on_an_unknown_value(tenant_a,
                                                                           fulfillment_po_a):
    asn = _fulfillment_asn(tenant_a, fulfillment_po_a)
    asn.status = "zzz"
    asn.source = "zzz"
    asn.arrival_condition = "zzz"
    assert asn.status_css == "badge-slate"
    assert asn.source_css == "badge-slate"
    assert asn.condition_css == "badge-slate"


def test_fulfillment_asn_line_count_prefers_the_list_annotation(fulfillment_asn_draft_a,
                                                                fulfillment_asn_line_a):
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    assert fresh.line_count == 1
    fresh.line_total = 7        # what the list view annotates
    assert fresh.line_count == 7


def test_fulfillment_asn_total_quantity_shipped_folds_the_declared_lines(
        fulfillment_asn_draft_a, fulfillment_asn_line_a, fulfillment_po_line2_a):
    AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line2_a,
                           quantity_shipped=Decimal("4"))
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    assert fresh.total_quantity_shipped == Decimal("14")


def test_fulfillment_asn_total_quantity_shipped_is_zero_with_no_lines(fulfillment_asn_draft_a):
    assert fulfillment_asn_draft_a.total_quantity_shipped == Decimal("0")


def test_fulfillment_asn_line_rows_are_fetched_once_per_instance(
        fulfillment_asn_draft_a, fulfillment_asn_line_a, django_assert_max_num_queries):
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    with django_assert_max_num_queries(1):
        first = fresh.line_rows()
        second = fresh.line_rows()
    assert first is second
    # select_related pre-loaded the FK hops the detail page walks.
    with django_assert_max_num_queries(0):
        assert first[0].po_line.purchase_order.pk == fulfillment_asn_draft_a.purchase_order_id


def test_fulfillment_asn_discrepancy_verdict_ok_when_exactly_on_the_balance(
        fulfillment_asn_draft_a, fulfillment_asn_line_a):
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    assert fresh.discrepancy_verdict == "ok"
    assert fresh.discrepancy_css == "badge-green"


def test_fulfillment_asn_discrepancy_verdict_short(fulfillment_asn_draft_a,
                                                   fulfillment_po_line_a):
    AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                           quantity_shipped=Decimal("6"))
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    assert fresh.discrepancy_verdict == "short"
    assert fresh.discrepancy_css == "badge-amber"


def test_fulfillment_asn_discrepancy_verdict_over(fulfillment_asn_draft_a,
                                                  fulfillment_po_line_a):
    AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                           quantity_shipped=Decimal("12"))
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    assert fresh.discrepancy_verdict == "over"
    assert fresh.discrepancy_css == "badge-info"


def test_fulfillment_asn_discrepancy_verdict_mixed(fulfillment_asn_draft_a,
                                                   fulfillment_po_line_a,
                                                   fulfillment_po_line2_a):
    AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                           quantity_shipped=Decimal("12"))       # over 10
    AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line2_a,
                           quantity_shipped=Decimal("2"))        # short of 4
    fresh = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)
    assert fresh.discrepancy_verdict == "mixed"
    assert fresh.discrepancy_css == "badge-red"


def test_fulfillment_asn_derived_figures_are_not_stored_columns():
    stored = _fulfillment_concrete_names(AdvancedShipmentNotice)
    for derived in ("line_count", "total_quantity_shipped", "discrepancy_verdict", "is_late",
                    "days_late", "carrier_display", "eta_display"):
        assert derived not in stored, derived


# ================================================================================================
# 3. AdvancedShipmentNotice - verbs
# ================================================================================================

def test_fulfillment_asn_submit_moves_draft_and_stamps_the_moment(fulfillment_asn_draft_a):
    assert fulfillment_asn_draft_a.submit() is True
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "submitted"
    assert fulfillment_asn_draft_a.submitted_at is not None


def test_fulfillment_asn_submit_is_a_noop_on_a_second_call(fulfillment_asn_draft_a):
    fulfillment_asn_draft_a.submit()
    stamped = fulfillment_asn_draft_a.submitted_at
    assert fulfillment_asn_draft_a.submit() is False
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.submitted_at == stamped


def test_fulfillment_asn_submit_refused_once_delivered(fulfillment_asn_delivered_a):
    assert fulfillment_asn_delivered_a.submit() is False
    fulfillment_asn_delivered_a.refresh_from_db()
    assert fulfillment_asn_delivered_a.status == "delivered"


def test_fulfillment_asn_mark_in_transit_from_draft_backfills_submitted_at(
        fulfillment_asn_draft_a):
    assert fulfillment_asn_draft_a.submitted_at is None
    assert fulfillment_asn_draft_a.mark_in_transit() is True
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "in_transit"
    assert fulfillment_asn_draft_a.submitted_at is not None


def test_fulfillment_asn_mark_in_transit_keeps_an_existing_submitted_at(
        fulfillment_asn_draft_a):
    fulfillment_asn_draft_a.submit()
    stamped = fulfillment_asn_draft_a.submitted_at
    assert fulfillment_asn_draft_a.mark_in_transit() is True
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "in_transit"
    assert fulfillment_asn_draft_a.submitted_at == stamped


def test_fulfillment_asn_mark_in_transit_refused_from_in_transit_and_delivered(
        fulfillment_asn_in_transit_a, fulfillment_asn_delivered_a):
    assert fulfillment_asn_in_transit_a.mark_in_transit() is False
    assert fulfillment_asn_delivered_a.mark_in_transit() is False


def test_fulfillment_asn_confirm_delivery_stamps_the_whole_pod_block(
        fulfillment_asn_in_transit_a, admin_user):
    moment = timezone.now() - datetime.timedelta(hours=3)
    assert fulfillment_asn_in_transit_a.confirm_delivery(
        admin_user, delivered_at=moment, arrival_condition="damaged",
        pod_reference="POD-9", received_signature_name="J. Dock") is True
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert fulfillment_asn_in_transit_a.status == "delivered"
    assert fulfillment_asn_in_transit_a.delivered_at == moment
    assert fulfillment_asn_in_transit_a.arrival_condition == "damaged"
    assert fulfillment_asn_in_transit_a.pod_reference == "POD-9"
    assert fulfillment_asn_in_transit_a.received_signature_name == "J. Dock"
    assert fulfillment_asn_in_transit_a.confirmed_by_id == admin_user.pk


def test_fulfillment_asn_confirm_delivery_defaults_delivered_at_to_now(
        fulfillment_asn_in_transit_a, admin_user):
    before = timezone.now()
    assert fulfillment_asn_in_transit_a.confirm_delivery(admin_user) is True
    assert before <= fulfillment_asn_in_transit_a.delivered_at <= timezone.now()
    assert fulfillment_asn_in_transit_a.arrival_condition == "good"


def test_fulfillment_asn_confirm_delivery_falls_back_to_good_on_a_junk_condition(
        fulfillment_asn_in_transit_a, admin_user):
    assert fulfillment_asn_in_transit_a.confirm_delivery(
        admin_user, arrival_condition="obliterated") is True
    assert fulfillment_asn_in_transit_a.arrival_condition == "good"


def test_fulfillment_asn_confirm_delivery_truncates_pod_and_signature(
        fulfillment_asn_in_transit_a, admin_user):
    fulfillment_asn_in_transit_a.confirm_delivery(
        admin_user, pod_reference="P" * 200, received_signature_name="S" * 400)
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert len(fulfillment_asn_in_transit_a.pod_reference) == 64
    assert len(fulfillment_asn_in_transit_a.received_signature_name) == 120


def test_fulfillment_asn_confirm_delivery_refused_from_draft(fulfillment_asn_draft_a,
                                                             admin_user):
    assert fulfillment_asn_draft_a.confirm_delivery(admin_user) is False
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "draft"
    assert fulfillment_asn_draft_a.delivered_at is None


def test_fulfillment_asn_double_confirm_does_not_restamp_the_delivery(
        fulfillment_asn_in_transit_a, admin_user, admin_b):
    fulfillment_asn_in_transit_a.confirm_delivery(admin_user, pod_reference="POD-FIRST")
    first_moment = fulfillment_asn_in_transit_a.delivered_at

    assert fulfillment_asn_in_transit_a.confirm_delivery(
        admin_b, pod_reference="POD-SECOND", arrival_condition="refused") is False
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert fulfillment_asn_in_transit_a.delivered_at == first_moment
    assert fulfillment_asn_in_transit_a.pod_reference == "POD-FIRST"
    assert fulfillment_asn_in_transit_a.arrival_condition == "good"
    assert fulfillment_asn_in_transit_a.confirmed_by_id == admin_user.pk


def test_fulfillment_asn_confirm_delivery_tolerates_an_anonymous_actor(
        fulfillment_asn_in_transit_a):
    class _FulfillmentNobody:
        pk = None

    assert fulfillment_asn_in_transit_a.confirm_delivery(_FulfillmentNobody()) is True
    assert fulfillment_asn_in_transit_a.confirmed_by_id is None


def test_fulfillment_asn_cancel_stamps_reason_and_moment(fulfillment_asn_draft_a, admin_user):
    assert fulfillment_asn_draft_a.cancel(admin_user, "  Supplier withdrew the notice  ") is True
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "cancelled"
    assert fulfillment_asn_draft_a.cancelled_at is not None
    assert fulfillment_asn_draft_a.cancellation_reason == "Supplier withdrew the notice"


def test_fulfillment_asn_cancel_truncates_the_reason_at_2000(fulfillment_asn_draft_a,
                                                             admin_user):
    fulfillment_asn_draft_a.cancel(admin_user, "x" * 5000)
    fulfillment_asn_draft_a.refresh_from_db()
    assert len(fulfillment_asn_draft_a.cancellation_reason) == 2000


def test_fulfillment_asn_cancel_refused_once_delivered(fulfillment_asn_delivered_a, admin_user):
    assert fulfillment_asn_delivered_a.cancel(admin_user, "changed my mind") is False
    fulfillment_asn_delivered_a.refresh_from_db()
    assert fulfillment_asn_delivered_a.status == "delivered"
    assert fulfillment_asn_delivered_a.cancelled_at is None


def test_fulfillment_asn_cancel_is_a_noop_on_a_second_call(fulfillment_asn_draft_a, admin_user):
    fulfillment_asn_draft_a.cancel(admin_user, "first reason")
    stamped = fulfillment_asn_draft_a.cancelled_at
    assert fulfillment_asn_draft_a.cancel(admin_user, "second reason") is False
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.cancelled_at == stamped
    assert fulfillment_asn_draft_a.cancellation_reason == "first reason"


def test_fulfillment_asn_cancel_is_reachable_from_in_transit(fulfillment_asn_in_transit_a,
                                                             admin_user):
    assert fulfillment_asn_in_transit_a.cancel(admin_user, "truck turned back") is True
    assert fulfillment_asn_in_transit_a.status == "cancelled"


# ================================================================================================
# 4. AdvancedShipmentNotice - clean()
# ================================================================================================

def test_fulfillment_asn_clean_rejects_a_cross_tenant_purchase_order(tenant_a,
                                                                    fulfillment_po_b):
    asn = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_b)
    with pytest.raises(ValidationError) as excinfo:
        asn.full_clean()
    assert "purchase_order" in excinfo.value.message_dict


def test_fulfillment_asn_clean_rejects_a_duplicate_live_supplier_reference(
        tenant_a, fulfillment_po_a, fulfillment_asn_draft_a):
    twin = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                  supplier_reference="NW-DN-1001")
    with pytest.raises(ValidationError) as excinfo:
        twin.full_clean()
    assert "supplier_reference" in excinfo.value.message_dict


def test_fulfillment_asn_clean_exempts_a_cancelled_row_from_the_reference_check(
        tenant_a, fulfillment_po_a, fulfillment_asn_draft_a, admin_user):
    fulfillment_asn_draft_a.cancel(admin_user, "re-issued")
    reissue = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                     supplier_reference="NW-DN-1001")
    reissue.full_clean()        # must not raise
    reissue.save()
    assert reissue.pk is not None


def test_fulfillment_asn_clean_lets_a_row_keep_its_own_reference_on_edit(
        fulfillment_asn_draft_a):
    fulfillment_asn_draft_a.tracking_number = "TRK-EDITED"
    fulfillment_asn_draft_a.full_clean()        # must not collide with itself
    fulfillment_asn_draft_a.save()
    assert fulfillment_asn_draft_a.tracking_number == "TRK-EDITED"


def test_fulfillment_asn_clean_allows_repeated_blank_supplier_references(tenant_a,
                                                                        fulfillment_po_a):
    _fulfillment_asn(tenant_a, fulfillment_po_a, supplier_reference="")
    second = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                    supplier_reference="   ")
    second.full_clean()         # blank is not a duplicate
    second.save()
    assert second.pk is not None


def test_fulfillment_asn_clean_rejects_delivery_before_dispatch(tenant_a, fulfillment_po_a):
    asn = AdvancedShipmentNotice(
        tenant=tenant_a, purchase_order=fulfillment_po_a,
        ship_date=_fulfillment_today(),
        expected_delivery_date=_fulfillment_today() - _fulfillment_days(1))
    with pytest.raises(ValidationError) as excinfo:
        asn.full_clean()
    assert "expected_delivery_date" in excinfo.value.message_dict


def test_fulfillment_asn_clean_accepts_same_day_ship_and_delivery(tenant_a, fulfillment_po_a):
    today = _fulfillment_today()
    asn = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                 ship_date=today, expected_delivery_date=today)
    asn.full_clean()
    asn.save()
    assert asn.pk is not None


def test_fulfillment_asn_clean_rejects_an_outbound_shipment(tenant_a, fulfillment_po_a,
                                                            fulfillment_shipment_outbound_a):
    asn = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                 shipment=fulfillment_shipment_outbound_a)
    with pytest.raises(ValidationError) as excinfo:
        asn.full_clean()
    assert "INBOUND" in " ".join(excinfo.value.message_dict["shipment"])


def test_fulfillment_asn_clean_rejects_a_cross_tenant_shipment(tenant_a, fulfillment_po_a,
                                                               fulfillment_shipment_inbound_b):
    asn = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                 shipment=fulfillment_shipment_inbound_b)
    with pytest.raises(ValidationError) as excinfo:
        asn.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["shipment"])


def test_fulfillment_asn_clean_rejects_a_cross_tenant_carrier(tenant_a, fulfillment_po_a,
                                                              fulfillment_carrier_b):
    asn = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                 carrier=fulfillment_carrier_b)
    with pytest.raises(ValidationError) as excinfo:
        asn.full_clean()
    assert "carrier" in excinfo.value.message_dict


def test_fulfillment_asn_clean_accepts_a_same_tenant_inbound_shipment(
        tenant_a, fulfillment_po_a, fulfillment_shipment_inbound_a, fulfillment_carrier_a):
    asn = AdvancedShipmentNotice(tenant=tenant_a, purchase_order=fulfillment_po_a,
                                 shipment=fulfillment_shipment_inbound_a,
                                 carrier=fulfillment_carrier_a)
    asn.full_clean()
    asn.save()
    assert asn.pk is not None


# ================================================================================================
# 5. AsnLine
# ================================================================================================

def test_fulfillment_asnline_quantity_shipped_defaults_to_one(fulfillment_asn_draft_a,
                                                              fulfillment_po_line_a):
    line = AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a)
    line.refresh_from_db()
    assert line.quantity_shipped == Decimal("1")
    assert line.package_ref == ""
    assert line.lot_number == ""
    assert line.serial_number == ""
    assert line.expiry_date is None
    assert line.country_of_origin == ""
    assert line.notes == ""


def test_fulfillment_asnline_carries_no_tenant_or_number_column():
    names = _fulfillment_concrete_names(AsnLine)
    assert "tenant" not in names
    assert "number" not in names
    assert "status" not in names
    assert "asn" in names


def test_fulfillment_asnline_save_copies_blank_identity_from_the_po_line(
        fulfillment_asn_draft_a, fulfillment_po_line_a):
    line = AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                                  quantity_shipped=Decimal("3"))
    assert line.item_description == "Bearing housing 40mm"
    assert line.sku_hint == "BRG-40"
    assert line.uom_hint == "EA"


def test_fulfillment_asnline_save_keeps_explicit_identity_text(fulfillment_asn_draft_a,
                                                               fulfillment_po_line_a):
    line = AsnLine.objects.create(
        asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
        item_description="Supplier's own wording", sku_hint="SUP-1", uom_hint="BOX")
    assert line.item_description == "Supplier's own wording"
    assert line.sku_hint == "SUP-1"
    assert line.uom_hint == "BOX"


def test_fulfillment_asnline_str_uses_description_and_quantity(fulfillment_asn_line_a):
    fresh = AsnLine.objects.get(pk=fulfillment_asn_line_a.pk)
    assert str(fresh) == "Bearing housing 40mm ×10.0000"


def test_fulfillment_asnline_str_falls_back_to_the_po_line(fulfillment_asn_draft_a,
                                                           fulfillment_po_line_a):
    orphan = AsnLine(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                     quantity_shipped=Decimal("2"))
    assert str(orphan) == "%s ×2" % (fulfillment_po_line_a,)


def test_fulfillment_asnline_meta_ordering_and_unique_together():
    assert AsnLine._meta.ordering == ["id"]
    assert AsnLine._meta.unique_together == (("asn", "po_line"),)


def test_fulfillment_asnline_one_declaration_per_po_line_is_enforced(fulfillment_asn_draft_a,
                                                                     fulfillment_asn_line_a,
                                                                     fulfillment_po_line_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                                   quantity_shipped=Decimal("2"))


def test_fulfillment_asnline_variance_css_map_is_colour_named():
    assert AsnLine.VARIANCE_CSS == {"over": "badge-info", "short": "badge-amber",
                                    "exact": "badge-green"}
    assert set(AsnLine.VARIANCE_CSS.values()) <= _FULFILLMENT_BADGE_COLOURS


def test_fulfillment_asnline_outstanding_is_derived_live_off_the_spine(
        tenant_a, fulfillment_po_a, fulfillment_po_line_a, fulfillment_asn_draft_a):
    line = AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                                  quantity_shipped=Decimal("10"))
    assert line.outstanding_at_declare == Decimal("10.0000")
    assert line.variance == Decimal("0.0000")

    # Book a receipt on the spine; the SAME declared row must now read short, with nothing
    # written to AsnLine at all.
    _fulfillment_receive(tenant_a, fulfillment_po_a, fulfillment_po_line_a, "4")
    fresh = AsnLine.objects.get(pk=line.pk)
    assert fresh.outstanding_at_declare == Decimal("6.0000")
    assert fresh.variance == Decimal("4.0000")
    assert fresh.is_over is True


def test_fulfillment_asnline_short_shipment_reports_shortfall(fulfillment_asn_draft_a,
                                                              fulfillment_po_line_a):
    line = AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                                  quantity_shipped=Decimal("6"))
    assert line.is_short is True
    assert line.is_over is False
    assert line.shortfall == Decimal("4.0000")
    assert line.variance == Decimal("-4.0000")
    assert line.variance_css == "badge-amber"


def test_fulfillment_asnline_over_shipment_reports_zero_shortfall(fulfillment_asn_draft_a,
                                                                  fulfillment_po_line_a):
    line = AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                                  quantity_shipped=Decimal("13"))
    assert line.is_over is True
    assert line.shortfall == Decimal("0")
    assert line.variance_css == "badge-info"


def test_fulfillment_asnline_exact_shipment_is_green(fulfillment_asn_line_a):
    assert fulfillment_asn_line_a.is_over is False
    assert fulfillment_asn_line_a.is_short is False
    assert fulfillment_asn_line_a.variance_css == "badge-green"


def test_fulfillment_asnline_clean_rejects_a_line_from_another_order(fulfillment_asn_draft_a,
                                                                     fulfillment_po_line_b):
    line = AsnLine(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_b,
                   quantity_shipped=Decimal("1"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "different purchase order" in " ".join(excinfo.value.message_dict["po_line"])


def test_fulfillment_asnline_clean_rejects_a_zero_quantity(fulfillment_asn_draft_a,
                                                           fulfillment_po_line_a):
    line = AsnLine(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                   quantity_shipped=Decimal("0"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "quantity_shipped" in excinfo.value.message_dict


def test_fulfillment_asnline_clean_rejects_a_negative_quantity(fulfillment_asn_draft_a,
                                                               fulfillment_po_line_a):
    line = AsnLine(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                   quantity_shipped=Decimal("-3"))
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "quantity_shipped" in excinfo.value.message_dict


def test_fulfillment_asnline_derived_figures_are_not_stored_columns():
    stored = _fulfillment_concrete_names(AsnLine)
    for derived in ("outstanding_at_declare", "variance", "shortfall", "is_over", "is_short"):
        assert derived not in stored, derived


# ================================================================================================
# 6. DeliverySchedule - defaults, numbering, str, choices
# ================================================================================================

def test_fulfillment_schedule_minimal_create_takes_documented_defaults(tenant_a,
                                                                      fulfillment_po_line_a):
    row = DeliverySchedule.objects.create(
        tenant=tenant_a, po_line=fulfillment_po_line_a, scheduled_quantity=Decimal("4"),
        need_by_date=_fulfillment_today() + _fulfillment_days(7))
    assert row.sequence == 1
    assert row.status == "planned"
    assert row.delivery_mode == ""
    assert row.promised_quantity is None
    assert row.promised_date is None
    assert row.ship_to_id is None
    assert row.asn_id is None
    assert row.change_reason == ""
    assert row.notes == ""
    assert row.created_by_id is None


def test_fulfillment_schedule_number_prefix_and_sequence(tenant_a, fulfillment_po_line_a,
                                                         fulfillment_po_line2_a):
    assert DeliverySchedule.NUMBER_PREFIX == "DSC"
    unsaved = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                               scheduled_quantity=Decimal("1"),
                               need_by_date=_fulfillment_today())
    assert unsaved.number == ""
    unsaved.save()
    second = _fulfillment_schedule(tenant_a, fulfillment_po_line2_a)
    assert unsaved.number == "DSC-00001"
    assert second.number == "DSC-00002"


def test_fulfillment_schedule_numbers_are_per_tenant(tenant_a, tenant_b, fulfillment_po_line_a,
                                                     fulfillment_po_line_b):
    a_one = _fulfillment_schedule(tenant_a, fulfillment_po_line_a)
    b_one = _fulfillment_schedule(tenant_b, fulfillment_po_line_b)
    assert a_one.number == "DSC-00001"
    assert b_one.number == "DSC-00001"


def test_fulfillment_schedule_str_folds_number_and_sequence(fulfillment_schedule_late_a):
    assert str(fulfillment_schedule_late_a) == "%s · seq 2" % (
        fulfillment_schedule_late_a.number,)


def test_fulfillment_schedule_status_choices_are_the_five_documented_values():
    assert DeliverySchedule.STATUS_CHOICES == [
        ("planned", "Planned"),
        ("confirmed", "Confirmed"),
        ("shipped", "Shipped"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]
    assert DeliverySchedule.OPEN_STATUSES == ("planned", "confirmed", "shipped")


def test_fulfillment_schedule_mode_choices_are_local_not_scms_transport_modes():
    assert [value for value, _ in DeliverySchedule.MODE_CHOICES] == [
        "standard", "express", "courier", "freight", "collection", "dropship"]


def test_fulfillment_schedule_max_split_instalments_is_twelve():
    assert DeliverySchedule.MAX_SPLIT_INSTALMENTS == 12


def test_fulfillment_schedule_badge_maps_are_colour_named_and_complete():
    assert set(DeliverySchedule.STATUS_CSS) == {v for v, _ in DeliverySchedule.STATUS_CHOICES}
    assert set(DeliverySchedule.MODE_CSS) == {v for v, _ in DeliverySchedule.MODE_CHOICES}
    assert set(DeliverySchedule.STATUS_CSS.values()) <= _FULFILLMENT_BADGE_COLOURS
    assert set(DeliverySchedule.MODE_CSS.values()) <= _FULFILLMENT_BADGE_COLOURS


def test_fulfillment_schedule_meta_ordering_and_both_unique_togethers():
    assert DeliverySchedule._meta.ordering == ["po_line_id", "sequence", "id"]
    assert DeliverySchedule._meta.unique_together == (
        ("tenant", "number"), ("tenant", "po_line", "sequence"))


def test_fulfillment_schedule_sequence_is_unique_per_tenant_and_line(
        tenant_a, fulfillment_schedule_a, fulfillment_po_line_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DeliverySchedule.objects.create(
                tenant=tenant_a, po_line=fulfillment_po_line_a, sequence=1,
                scheduled_quantity=Decimal("1"),
                need_by_date=_fulfillment_today())


def test_fulfillment_schedule_same_sequence_on_another_line_is_allowed(
        tenant_a, fulfillment_schedule_a, fulfillment_po_line2_a):
    twin = _fulfillment_schedule(tenant_a, fulfillment_po_line2_a, sequence=1)
    assert twin.pk is not None
    assert twin.sequence == fulfillment_schedule_a.sequence


def test_fulfillment_schedule_status_is_deliberately_an_editable_form_field():
    # Unlike the ASN's and the backorder's, this ladder stamps no timestamps, so there is
    # nothing for a verb to protect and the field stays an honest <select>.
    assert _fulfillment_field(DeliverySchedule, "status").editable is True
    assert _fulfillment_field(AdvancedShipmentNotice, "status").editable is False
    assert _fulfillment_field(Backorder, "status").editable is False


def test_fulfillment_schedule_has_no_verb_methods():
    for verb in ("submit", "confirm", "cancel", "receive", "mark_shipped"):
        assert not hasattr(DeliverySchedule, verb), verb


def test_fulfillment_schedule_only_number_and_created_by_are_non_editable():
    # The pk is skipped deliberately: Django keeps AutoField/BigAutoField ``editable=True`` and
    # keeps it off forms through ``formfield()`` returning None instead, so asserting on ``id``
    # here would test Django, not this module's contract.
    non_editable = {f.name for f in DeliverySchedule._meta.fields
                    if not f.editable and not f.primary_key}
    assert non_editable == {"number", "created_at", "updated_at", "created_by"}


# ================================================================================================
# 7. DeliverySchedule - derived coverage / slip
# ================================================================================================

def test_fulfillment_schedule_slip_days_measures_promise_against_need_by(
        fulfillment_schedule_late_a):
    assert fulfillment_schedule_late_a.slip_days == 6
    assert fulfillment_schedule_late_a.has_slip is True


def test_fulfillment_schedule_slip_days_is_zero_without_a_promise(fulfillment_schedule_a):
    assert fulfillment_schedule_a.promised_date is None
    assert fulfillment_schedule_a.slip_days == 0
    assert fulfillment_schedule_a.has_slip is False


def test_fulfillment_schedule_slip_days_goes_negative_when_the_supplier_beats_the_date(
        tenant_a, fulfillment_po_line_a):
    row = _fulfillment_schedule(
        tenant_a, fulfillment_po_line_a,
        need_by_date=_fulfillment_today() + _fulfillment_days(10),
        promised_date=_fulfillment_today() + _fulfillment_days(6))
    assert row.slip_days == -4
    assert row.has_slip is False


def test_fulfillment_schedule_is_late_and_days_late(fulfillment_schedule_late_a):
    assert fulfillment_schedule_late_a.is_late is True
    assert fulfillment_schedule_late_a.days_late == 2


def test_fulfillment_schedule_future_need_by_is_not_late(fulfillment_schedule_a):
    assert fulfillment_schedule_a.is_late is False
    assert fulfillment_schedule_a.days_late == 0


@pytest.mark.parametrize("status", ["received", "cancelled"])
def test_fulfillment_schedule_closed_rows_are_never_late(tenant_a, fulfillment_po_line_a,
                                                         status):
    row = _fulfillment_schedule(tenant_a, fulfillment_po_line_a, status=status, sequence=4,
                                need_by_date=_fulfillment_today() - _fulfillment_days(5))
    assert row.is_late is False
    assert row.days_late == 0


def test_fulfillment_schedule_line_total_is_derived_by_aggregate_over_siblings(
        fulfillment_schedule_a, fulfillment_schedule_late_a):
    fresh = DeliverySchedule.objects.get(pk=fulfillment_schedule_a.pk)
    assert fresh.line_scheduled_total == Decimal("7.0000")   # 4 + 3, including self
    assert fresh.remaining_quantity == Decimal("3.0000")     # of the 10 ordered
    assert fresh.coverage_pct == 70
    assert fresh.is_under_covered is True


def test_fulfillment_schedule_line_total_excludes_cancelled_siblings(
        tenant_a, fulfillment_schedule_a, fulfillment_po_line_a):
    _fulfillment_schedule(tenant_a, fulfillment_po_line_a, sequence=9,
                          scheduled_quantity=Decimal("6"), status="cancelled")
    fresh = DeliverySchedule.objects.get(pk=fulfillment_schedule_a.pk)
    assert fresh.line_scheduled_total == Decimal("4.0000")
    assert fresh.coverage_pct == 40


def test_fulfillment_schedule_line_total_is_memoized_per_instance(
        fulfillment_schedule_a, django_assert_max_num_queries):
    fresh = DeliverySchedule.objects.get(pk=fulfillment_schedule_a.pk)
    with django_assert_max_num_queries(1):
        assert fresh.line_scheduled_total == fresh.line_scheduled_total


def test_fulfillment_schedule_line_total_prefers_the_list_view_annotation(
        fulfillment_schedule_a, django_assert_max_num_queries):
    fresh = DeliverySchedule.objects.get(pk=fulfillment_schedule_a.pk)
    fresh.sched_total_annot = Decimal("9.5000")
    with django_assert_max_num_queries(0):
        assert fresh.line_scheduled_total == Decimal("9.5000")


def test_fulfillment_schedule_unsaved_row_counts_its_own_quantity(tenant_a,
                                                                  fulfillment_schedule_a,
                                                                  fulfillment_po_line_a):
    draft = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a, sequence=2,
                             scheduled_quantity=Decimal("2"),
                             need_by_date=_fulfillment_today())
    assert draft.pk is None
    assert draft.line_scheduled_total == Decimal("6.0000")   # 4 saved + its own 2


def test_fulfillment_schedule_unsaved_cancelled_row_commits_nothing(tenant_a,
                                                                    fulfillment_schedule_a,
                                                                    fulfillment_po_line_a):
    draft = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a, sequence=2,
                             scheduled_quantity=Decimal("2"), status="cancelled",
                             need_by_date=_fulfillment_today())
    assert draft.line_scheduled_total == Decimal("4.0000")


def test_fulfillment_schedule_coverage_rounds_half_up(tenant_a, fulfillment_po_line_a):
    # 1.05 of 10 ordered = 10.5% -> 11 with ROUND_HALF_UP (10 with banker's rounding).
    row = _fulfillment_schedule(tenant_a, fulfillment_po_line_a,
                                scheduled_quantity=Decimal("1.05"))
    assert row.coverage_pct == 11


def test_fulfillment_schedule_coverage_is_clamped_to_a_hundred(tenant_a,
                                                               fulfillment_po_line2_a):
    # Direct create bypasses clean()'s over-commitment block; the display must still cap.
    row = _fulfillment_schedule(tenant_a, fulfillment_po_line2_a,
                                scheduled_quantity=Decimal("10"))
    assert row.coverage_pct == 100
    assert row.is_under_covered is False


def test_fulfillment_schedule_full_coverage_is_not_under_covered(tenant_a,
                                                                 fulfillment_po_line_a):
    row = _fulfillment_schedule(tenant_a, fulfillment_po_line_a,
                                scheduled_quantity=Decimal("10"))
    assert row.coverage_pct == 100
    assert row.is_under_covered is False
    assert row.remaining_quantity == Decimal("0.0000")


def test_fulfillment_schedule_status_and_mode_css(fulfillment_schedule_late_a):
    assert fulfillment_schedule_late_a.status_css == "badge-slate"     # planned
    assert fulfillment_schedule_late_a.mode_css == "badge-amber"       # express


def test_fulfillment_schedule_blank_mode_css_is_muted(fulfillment_schedule_a):
    blank = DeliverySchedule(delivery_mode="")
    assert blank.mode_css == "badge-muted"
    assert fulfillment_schedule_a.mode_css == "badge-slate"            # standard


def test_fulfillment_schedule_derived_figures_are_not_stored_columns():
    stored = _fulfillment_concrete_names(DeliverySchedule)
    for derived in ("line_scheduled_total", "remaining_quantity", "coverage_pct", "slip_days",
                    "days_late", "is_under_covered"):
        assert derived not in stored, derived


# ================================================================================================
# 8. DeliverySchedule - clean()
# ================================================================================================

def test_fulfillment_schedule_clean_hard_blocks_over_commitment(tenant_a,
                                                                fulfillment_schedule_a,
                                                                fulfillment_po_line_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a, sequence=2,
                           scheduled_quantity=Decimal("7"),     # 4 + 7 > 10
                           need_by_date=_fulfillment_today())
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    message = " ".join(excinfo.value.message_dict["scheduled_quantity"])
    assert "over-commit" in message
    assert "of 10.0000" in message


def test_fulfillment_schedule_clean_allows_exactly_covering_the_line(tenant_a,
                                                                     fulfillment_schedule_a,
                                                                     fulfillment_po_line_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a, sequence=2,
                           scheduled_quantity=Decimal("6"),     # 4 + 6 == 10
                           need_by_date=_fulfillment_today())
    row.full_clean()
    row.save()
    assert row.pk is not None


def test_fulfillment_schedule_clean_never_errors_on_under_coverage(tenant_a,
                                                                   fulfillment_po_line_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"),
                           need_by_date=_fulfillment_today())
    row.full_clean()
    row.save()
    assert row.is_under_covered is True      # a warning on the board, not an error


def test_fulfillment_schedule_clean_exempts_a_cancelled_row_from_the_cap(
        tenant_a, fulfillment_schedule_a, fulfillment_po_line_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a, sequence=2,
                           scheduled_quantity=Decimal("99"), status="cancelled",
                           need_by_date=_fulfillment_today())
    row.full_clean()        # a cancelled instalment commits nothing
    row.save()
    assert row.pk is not None


def test_fulfillment_schedule_clean_excludes_self_when_editing(fulfillment_schedule_a):
    fulfillment_schedule_a.scheduled_quantity = Decimal("9")
    fulfillment_schedule_a.full_clean()      # must not count its own old 4 twice
    fulfillment_schedule_a.save()
    assert fulfillment_schedule_a.scheduled_quantity == Decimal("9")


def test_fulfillment_schedule_clean_rejects_a_cross_tenant_po_line(tenant_a,
                                                                   fulfillment_po_line_b):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_b,
                           scheduled_quantity=Decimal("1"),
                           need_by_date=_fulfillment_today())
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["po_line"])


def test_fulfillment_schedule_clean_rejects_a_cross_tenant_ship_to(tenant_a,
                                                                   fulfillment_po_line_a,
                                                                   org_unit_b):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"), ship_to=org_unit_b,
                           need_by_date=_fulfillment_today())
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "ship_to" in excinfo.value.message_dict


def test_fulfillment_schedule_clean_accepts_a_same_tenant_ship_to(tenant_a,
                                                                  fulfillment_po_line_a,
                                                                  org_unit_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"), ship_to=org_unit_a,
                           need_by_date=_fulfillment_today())
    row.full_clean()
    row.save()
    assert row.ship_to_id == org_unit_a.pk


def test_fulfillment_schedule_clean_rejects_an_asn_from_another_order(
        tenant_a, fulfillment_vendor_a, fulfillment_po_line_a):
    other_po = _fulfillment_new_po(tenant_a, fulfillment_vendor_a)
    _fulfillment_new_po_line(other_po)
    foreign_asn = _fulfillment_asn(tenant_a, other_po)

    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"), asn=foreign_asn,
                           need_by_date=_fulfillment_today())
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "asn" in excinfo.value.message_dict


def test_fulfillment_schedule_clean_rejects_a_cross_tenant_asn(tenant_a, fulfillment_po_line_a,
                                                               fulfillment_asn_b):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"), asn=fulfillment_asn_b,
                           need_by_date=_fulfillment_today())
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "asn" in excinfo.value.message_dict


def test_fulfillment_schedule_clean_accepts_an_asn_on_the_same_order(tenant_a,
                                                                     fulfillment_po_line_a,
                                                                     fulfillment_asn_draft_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"), asn=fulfillment_asn_draft_a,
                           need_by_date=_fulfillment_today())
    row.full_clean()
    row.save()
    assert row.asn_id == fulfillment_asn_draft_a.pk


def test_fulfillment_schedule_clean_rejects_a_zero_promised_quantity(tenant_a,
                                                                     fulfillment_po_line_a):
    row = DeliverySchedule(tenant=tenant_a, po_line=fulfillment_po_line_a,
                           scheduled_quantity=Decimal("1"), promised_quantity=Decimal("0"),
                           need_by_date=_fulfillment_today())
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "promised_quantity" in excinfo.value.message_dict


# ================================================================================================
# 9. split_po_line()
# ================================================================================================

def test_fulfillment_split_divides_the_line_and_the_rows_sum_exactly(tenant_a,
                                                                     fulfillment_po_line_a):
    first_date = _fulfillment_today() + _fulfillment_days(7)
    rows = split_po_line(tenant_a, fulfillment_po_line_a, 3, first_date, 14)

    assert len(rows) == 3
    assert sum(r.scheduled_quantity for r in rows) == Decimal("10.0000")
    assert rows[0].scheduled_quantity == Decimal("3.3333")
    assert rows[1].scheduled_quantity == Decimal("3.3333")
    assert rows[2].scheduled_quantity == Decimal("3.3334")   # the last absorbs the remainder


def test_fulfillment_split_spaces_the_need_by_dates_by_the_interval(tenant_a,
                                                                    fulfillment_po_line_a):
    first_date = _fulfillment_today() + _fulfillment_days(3)
    rows = split_po_line(tenant_a, fulfillment_po_line_a, 3, first_date, 10)
    assert [r.need_by_date for r in rows] == [
        first_date, first_date + _fulfillment_days(10), first_date + _fulfillment_days(20)]


def test_fulfillment_split_numbers_every_created_row(tenant_a, fulfillment_po_line_a):
    rows = split_po_line(tenant_a, fulfillment_po_line_a, 2,
                         _fulfillment_today() + _fulfillment_days(2), 7)
    assert [r.number for r in rows] == ["DSC-00001", "DSC-00002"]
    assert [r.sequence for r in rows] == [1, 2]


def test_fulfillment_split_copies_ship_to_and_stamps_the_reason(tenant_a, org_unit_a,
                                                                fulfillment_po_a,
                                                                fulfillment_po_line_a,
                                                                admin_user):
    fulfillment_po_a.ship_to = org_unit_a
    fulfillment_po_a.save(update_fields=["ship_to"])

    rows = split_po_line(tenant_a, fulfillment_po_line_a, 2,
                         _fulfillment_today() + _fulfillment_days(1), 5, user=admin_user)
    for row in rows:
        assert row.ship_to_id == org_unit_a.pk
        assert row.change_reason == "Auto-split into 2 instalments"
        assert row.created_by_id == admin_user.pk
        assert row.status == "planned"


def test_fulfillment_split_divides_only_the_uncommitted_remainder(tenant_a,
                                                                  fulfillment_schedule_a,
                                                                  fulfillment_po_line_a):
    # 4 of the 10 are already committed, so the split shares out 6, not 10.
    rows = split_po_line(tenant_a, fulfillment_po_line_a, 2,
                         _fulfillment_today() + _fulfillment_days(4), 7)
    assert sum(r.scheduled_quantity for r in rows) == Decimal("6.0000")
    fresh = DeliverySchedule.objects.get(pk=fulfillment_schedule_a.pk)
    assert fresh.line_scheduled_total == Decimal("10.0000")
    assert fresh.coverage_pct == 100


def test_fulfillment_split_continues_sequences_past_cancelled_rows(tenant_a,
                                                                   fulfillment_po_line_a):
    _fulfillment_schedule(tenant_a, fulfillment_po_line_a, sequence=5,
                          scheduled_quantity=Decimal("4"), status="cancelled")
    rows = split_po_line(tenant_a, fulfillment_po_line_a, 2,
                         _fulfillment_today() + _fulfillment_days(4), 7)
    assert [r.sequence for r in rows] == [6, 7]
    # The cancelled row commits nothing, so the full 10 was still available to split.
    assert sum(r.scheduled_quantity for r in rows) == Decimal("10.0000")


def test_fulfillment_split_rejects_fewer_than_two_instalments(tenant_a, fulfillment_po_line_a):
    with pytest.raises(ValidationError) as excinfo:
        split_po_line(tenant_a, fulfillment_po_line_a, 1, _fulfillment_today(), 7)
    assert "at least two instalments" in " ".join(excinfo.value.messages)
    assert DeliverySchedule.objects.count() == 0


def test_fulfillment_split_rejects_more_than_the_cap(tenant_a, fulfillment_po_line_a):
    with pytest.raises(ValidationError) as excinfo:
        split_po_line(tenant_a, fulfillment_po_line_a, 13, _fulfillment_today(), 7)
    assert "at most 12" in " ".join(excinfo.value.messages)
    assert DeliverySchedule.objects.count() == 0


def test_fulfillment_split_rejects_a_sub_daily_interval(tenant_a, fulfillment_po_line_a):
    with pytest.raises(ValidationError) as excinfo:
        split_po_line(tenant_a, fulfillment_po_line_a, 2, _fulfillment_today(), 0)
    assert "at least one day" in " ".join(excinfo.value.messages)


def test_fulfillment_split_rejects_a_missing_first_date(tenant_a, fulfillment_po_line_a):
    with pytest.raises(ValidationError) as excinfo:
        split_po_line(tenant_a, fulfillment_po_line_a, 2, None, 7)
    assert "first instalment" in " ".join(excinfo.value.messages)


def test_fulfillment_split_rejects_a_fully_covered_line(tenant_a, fulfillment_po_line_a):
    _fulfillment_schedule(tenant_a, fulfillment_po_line_a, scheduled_quantity=Decimal("10"))
    with pytest.raises(ValidationError) as excinfo:
        split_po_line(tenant_a, fulfillment_po_line_a, 2,
                      _fulfillment_today() + _fulfillment_days(1), 7)
    assert "already fully covered" in " ".join(excinfo.value.messages)
    assert DeliverySchedule.objects.count() == 1


def test_fulfillment_split_rejects_a_remainder_too_small_to_divide(tenant_a,
                                                                   fulfillment_vendor_a):
    po = _fulfillment_new_po(tenant_a, fulfillment_vendor_a)
    tiny = _fulfillment_new_po_line(po, description="Shim", qty="0.0001", price="1.00")
    with pytest.raises(ValidationError) as excinfo:
        split_po_line(tenant_a, tiny, 2, _fulfillment_today() + _fulfillment_days(1), 7)
    assert "too small to divide" in " ".join(excinfo.value.messages)
    assert DeliverySchedule.objects.count() == 0


def test_fulfillment_split_coerces_string_instalment_and_interval_inputs(tenant_a,
                                                                        fulfillment_po_line_a):
    rows = split_po_line(tenant_a, fulfillment_po_line_a, "2",
                         _fulfillment_today() + _fulfillment_days(1), "5")
    assert len(rows) == 2
    assert rows[1].need_by_date - rows[0].need_by_date == _fulfillment_days(5)


def test_fulfillment_split_rows_survive_their_own_models_validation(tenant_a,
                                                                    fulfillment_po_line_a):
    rows = split_po_line(tenant_a, fulfillment_po_line_a, 4,
                         _fulfillment_today() + _fulfillment_days(1), 3)
    for row in rows:
        row.full_clean()        # the helper never produces an over-committing row
    assert DeliverySchedule.objects.filter(tenant=tenant_a).count() == 4


# ================================================================================================
# 10. Backorder - defaults, numbering, str, choices
# ================================================================================================

def test_fulfillment_backorder_minimal_create_takes_documented_defaults(tenant_a,
                                                                       fulfillment_po_line_a):
    row = Backorder.objects.create(tenant=tenant_a, po_line=fulfillment_po_line_a,
                                   quantity_backordered=Decimal("3"))
    assert row.reason == "out_of_stock"
    assert row.reason_note == ""
    assert row.status == "open"
    assert row.reschedule_count == 0
    assert row.original_promise_date is None
    assert row.revised_promise_date is None
    assert row.delivery_schedule_id is None
    assert row.asn_id is None
    assert row.alert_id is None
    assert row.closed_at is None
    assert row.closure_note == ""
    assert row.created_by_id is None
    assert row.notes == ""


def test_fulfillment_backorder_number_prefix_and_sequence(tenant_a, fulfillment_po_line_a):
    assert Backorder.NUMBER_PREFIX == "BKO"
    unsaved = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                        quantity_backordered=Decimal("1"))
    assert unsaved.number == ""
    unsaved.save()
    second = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    assert unsaved.number == "BKO-00001"
    assert second.number == "BKO-00002"


def test_fulfillment_backorder_numbers_are_per_tenant(tenant_a, tenant_b,
                                                      fulfillment_po_line_a,
                                                      fulfillment_po_line_b):
    a_one = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    b_one = _fulfillment_backorder(tenant_b, fulfillment_po_line_b)
    a_two = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    assert [a_one.number, b_one.number, a_two.number] == ["BKO-00001", "BKO-00001", "BKO-00002"]


def test_fulfillment_backorder_str_walks_the_po_line(fulfillment_backorder_open_a):
    expected = "%s · %s" % (fulfillment_backorder_open_a.number,
                                 fulfillment_backorder_open_a.po_line)
    assert str(fulfillment_backorder_open_a) == expected
    assert "Bearing housing 40mm" in expected


def test_fulfillment_backorder_reason_choices():
    assert [value for value, _ in Backorder.REASON_CHOICES] == [
        "out_of_stock", "production_delay", "allocation", "material_shortage",
        "supplier_capacity", "logistics", "other"]


def test_fulfillment_backorder_status_choices_and_open_statuses():
    assert Backorder.STATUS_CHOICES == [
        ("open", "Open"),
        ("rescheduled", "Rescheduled"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    ]
    assert Backorder.OPEN_STATUSES == ("open", "rescheduled")


def test_fulfillment_backorder_risk_choices_are_derived_not_a_column():
    assert [value for value, _ in Backorder.RISK_CHOICES] == [
        "past_due", "at_risk", "no_commitment", "on_track"]
    assert "risk_bucket" not in _fulfillment_concrete_names(Backorder)
    assert "risk" not in _fulfillment_concrete_names(Backorder)


def test_fulfillment_backorder_at_risk_window_is_seven_days():
    assert Backorder.AT_RISK_DAYS == 7


def test_fulfillment_backorder_meta_ordering_and_unique_together():
    assert Backorder._meta.ordering == ["-created_at", "-id"]
    assert Backorder._meta.unique_together == (("tenant", "number"),)


def test_fulfillment_backorder_unique_together_with_tenant_is_enforced(tenant_a,
                                                                       fulfillment_po_line_a):
    first = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Backorder.objects.create(tenant=tenant_a, po_line=fulfillment_po_line_a,
                                     quantity_backordered=Decimal("1"), number=first.number)


def test_fulfillment_backorder_system_columns_are_not_editable():
    for name in ("number", "status", "reschedule_count", "closed_at", "closure_note", "alert",
                 "created_by"):
        assert _fulfillment_field(Backorder, name).editable is False, name


def test_fulfillment_backorder_buyer_typed_columns_stay_editable():
    for name in ("po_line", "delivery_schedule", "asn", "quantity_backordered", "reason",
                 "reason_note", "original_promise_date", "revised_promise_date", "notes"):
        assert _fulfillment_field(Backorder, name).editable is True, name


def test_fulfillment_backorder_badge_maps_are_colour_named(fulfillment_backorder_open_a,
                                                           fulfillment_backorder_past_due_a,
                                                           fulfillment_backorder_closed_a):
    for row in (fulfillment_backorder_open_a, fulfillment_backorder_past_due_a,
                fulfillment_backorder_closed_a):
        assert row.status_css in _FULFILLMENT_BADGE_COLOURS
        assert row.risk_css in _FULFILLMENT_BADGE_COLOURS
        assert row.reason_css in _FULFILLMENT_BADGE_COLOURS
    assert fulfillment_backorder_open_a.status_css == "badge-red"
    assert fulfillment_backorder_open_a.risk_css == "badge-amber"
    assert fulfillment_backorder_past_due_a.risk_css == "badge-red"
    assert fulfillment_backorder_closed_a.status_css == "badge-green"


# ================================================================================================
# 11. Backorder - derived properties
# ================================================================================================

@pytest.mark.parametrize("status,expected", [
    ("open", True), ("rescheduled", True), ("fulfilled", False), ("cancelled", False)])
def test_fulfillment_backorder_is_open_tracks_status(tenant_a, fulfillment_po_line_a, status,
                                                     expected):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a, status=status)
    assert row.is_open is expected


def test_fulfillment_backorder_effective_promise_prefers_the_revised_date(
        fulfillment_backorder_past_due_a):
    assert fulfillment_backorder_past_due_a.effective_promise_date == \
        fulfillment_backorder_past_due_a.revised_promise_date


def test_fulfillment_backorder_effective_promise_falls_back_to_the_original(
        tenant_a, fulfillment_po_line_a):
    original = _fulfillment_today() + _fulfillment_days(4)
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a, revised_promise_date=None,
                                 original_promise_date=original)
    assert row.effective_promise_date == original


def test_fulfillment_backorder_effective_promise_is_none_without_dates(tenant_a,
                                                                       fulfillment_po_line_a):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a, revised_promise_date=None)
    assert row.effective_promise_date is None


def test_fulfillment_backorder_days_open_counts_from_created_at(tenant_a,
                                                                fulfillment_po_line_a):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    Backorder.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=5))
    row.refresh_from_db()
    assert row.days_open == 5


def test_fulfillment_backorder_days_open_freezes_at_closure(tenant_a, fulfillment_po_line_a):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    Backorder.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=12),
        closed_at=timezone.now() - datetime.timedelta(days=4),
        status="fulfilled")
    row.refresh_from_db()
    assert row.days_open == 8       # frozen at closed_at, not still ageing to 12


def test_fulfillment_backorder_days_open_is_never_negative(tenant_a, fulfillment_po_line_a):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a)
    Backorder.objects.filter(pk=row.pk).update(
        closed_at=timezone.now() - datetime.timedelta(days=30), status="cancelled")
    row.refresh_from_db()
    assert row.days_open == 0


def test_fulfillment_backorder_is_late_and_days_late(fulfillment_backorder_past_due_a):
    assert fulfillment_backorder_past_due_a.is_late is True
    assert fulfillment_backorder_past_due_a.days_late == 2


def test_fulfillment_backorder_future_promise_is_not_late(fulfillment_backorder_open_a):
    assert fulfillment_backorder_open_a.is_late is False
    assert fulfillment_backorder_open_a.days_late == 0


def test_fulfillment_backorder_closed_row_is_never_late(tenant_a, fulfillment_po_line_a):
    row = _fulfillment_backorder(
        tenant_a, fulfillment_po_line_a, status="fulfilled", closed_at=timezone.now(),
        revised_promise_date=_fulfillment_today() - _fulfillment_days(30))
    assert row.is_late is False
    assert row.days_late == 0


def test_fulfillment_backorder_risk_bucket_past_due_on_a_revised_date(
        fulfillment_backorder_past_due_a):
    assert fulfillment_backorder_past_due_a.risk_bucket == "past_due"


def test_fulfillment_backorder_risk_bucket_at_risk_inside_the_window(
        fulfillment_backorder_open_a):
    assert fulfillment_backorder_open_a.risk_bucket == "at_risk"


def test_fulfillment_backorder_risk_bucket_at_risk_on_the_boundary(tenant_a,
                                                                   fulfillment_po_line_a):
    row = _fulfillment_backorder(
        tenant_a, fulfillment_po_line_a,
        revised_promise_date=_fulfillment_today() + _fulfillment_days(7))
    assert row.risk_bucket == "at_risk"


def test_fulfillment_backorder_risk_bucket_on_track_past_the_window(tenant_a,
                                                                    fulfillment_po_line_a):
    row = _fulfillment_backorder(
        tenant_a, fulfillment_po_line_a,
        revised_promise_date=_fulfillment_today() + _fulfillment_days(8))
    assert row.risk_bucket == "on_track"


def test_fulfillment_backorder_risk_bucket_past_due_on_an_original_only_date(
        tenant_a, fulfillment_po_line_a):
    row = _fulfillment_backorder(
        tenant_a, fulfillment_po_line_a, revised_promise_date=None,
        original_promise_date=_fulfillment_today() - _fulfillment_days(1))
    assert row.risk_bucket == "past_due"


def test_fulfillment_backorder_risk_bucket_on_track_on_a_future_original_only_date(
        tenant_a, fulfillment_po_line_a):
    row = _fulfillment_backorder(
        tenant_a, fulfillment_po_line_a, revised_promise_date=None,
        original_promise_date=_fulfillment_today() + _fulfillment_days(20))
    assert row.risk_bucket == "on_track"


def test_fulfillment_backorder_risk_bucket_no_commitment_without_any_date(
        tenant_a, fulfillment_po_line_a):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a, revised_promise_date=None)
    assert row.risk_bucket == "no_commitment"
    assert row.risk_css == "badge-slate"


def test_fulfillment_backorder_risk_bucket_of_a_closed_row_is_on_track(
        fulfillment_backorder_closed_a):
    assert fulfillment_backorder_closed_a.risk_bucket == "on_track"
    assert fulfillment_backorder_closed_a.risk_css == "badge-green"


def test_fulfillment_backorder_derived_figures_are_not_stored_columns():
    stored = _fulfillment_concrete_names(Backorder)
    for derived in ("days_open", "days_late", "is_late", "effective_promise_date",
                    "risk_bucket", "is_open"):
        assert derived not in stored, derived


# ================================================================================================
# 12. Backorder - verbs
# ================================================================================================

def test_fulfillment_backorder_reschedule_backfills_the_original_promise(
        fulfillment_backorder_open_a, admin_user):
    was_promised = fulfillment_backorder_open_a.revised_promise_date
    new_date = _fulfillment_today() + _fulfillment_days(10)

    assert fulfillment_backorder_open_a.reschedule(admin_user, new_date, "Foundry slipped") \
        is True
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.original_promise_date == was_promised
    assert fulfillment_backorder_open_a.revised_promise_date == new_date
    assert fulfillment_backorder_open_a.status == "rescheduled"
    assert fulfillment_backorder_open_a.reschedule_count == 1
    assert fulfillment_backorder_open_a.reason_note == "Foundry slipped"


def test_fulfillment_backorder_second_reschedule_keeps_the_first_commitment(
        fulfillment_backorder_open_a, admin_user):
    first_promise = fulfillment_backorder_open_a.revised_promise_date
    fulfillment_backorder_open_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(10), "slip one")
    fulfillment_backorder_open_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(20), "slip two")
    fulfillment_backorder_open_a.refresh_from_db()

    assert fulfillment_backorder_open_a.original_promise_date == first_promise
    assert fulfillment_backorder_open_a.revised_promise_date == \
        _fulfillment_today() + _fulfillment_days(20)
    assert fulfillment_backorder_open_a.reschedule_count == 2
    assert fulfillment_backorder_open_a.reason_note == "slip two"


def test_fulfillment_backorder_reschedule_truncates_the_note_at_255(
        fulfillment_backorder_open_a, admin_user):
    fulfillment_backorder_open_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(2), "n" * 900)
    fulfillment_backorder_open_a.refresh_from_db()
    assert len(fulfillment_backorder_open_a.reason_note) == 255


def test_fulfillment_backorder_reschedule_refused_once_closed(fulfillment_backorder_closed_a,
                                                              admin_user):
    assert fulfillment_backorder_closed_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(3), "too late") is False
    fulfillment_backorder_closed_a.refresh_from_db()
    assert fulfillment_backorder_closed_a.status == "fulfilled"
    assert fulfillment_backorder_closed_a.reschedule_count == 0


def test_fulfillment_backorder_reschedule_works_from_the_rescheduled_state(
        fulfillment_backorder_open_a, admin_user):
    fulfillment_backorder_open_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(4), "one")
    assert fulfillment_backorder_open_a.status == "rescheduled"
    assert fulfillment_backorder_open_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(9), "two") is True


def test_fulfillment_backorder_fulfil_closes_and_stamps(fulfillment_backorder_open_a,
                                                        admin_user):
    assert fulfillment_backorder_open_a.fulfil(admin_user, "Arrived on the second truck") is True
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "fulfilled"
    assert fulfillment_backorder_open_a.closed_at is not None
    assert fulfillment_backorder_open_a.closure_note == "Arrived on the second truck"
    assert fulfillment_backorder_open_a.is_open is False


def test_fulfillment_backorder_fulfil_accepts_a_blank_note(fulfillment_backorder_open_a,
                                                           admin_user):
    assert fulfillment_backorder_open_a.fulfil(admin_user) is True
    assert fulfillment_backorder_open_a.closure_note == ""


def test_fulfillment_backorder_fulfil_truncates_the_note_at_255(fulfillment_backorder_open_a,
                                                                admin_user):
    fulfillment_backorder_open_a.fulfil(admin_user, "z" * 900)
    fulfillment_backorder_open_a.refresh_from_db()
    assert len(fulfillment_backorder_open_a.closure_note) == 255


def test_fulfillment_backorder_double_fulfil_does_not_restamp(fulfillment_backorder_open_a,
                                                              admin_user):
    fulfillment_backorder_open_a.fulfil(admin_user, "first close")
    stamped = fulfillment_backorder_open_a.closed_at
    assert fulfillment_backorder_open_a.fulfil(admin_user, "second close") is False
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.closed_at == stamped
    assert fulfillment_backorder_open_a.closure_note == "first close"


def test_fulfillment_backorder_cancel_closes_and_stamps(fulfillment_backorder_open_a,
                                                        admin_user):
    assert fulfillment_backorder_open_a.cancel(admin_user, "Sourced elsewhere") is True
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "cancelled"
    assert fulfillment_backorder_open_a.closed_at is not None
    assert fulfillment_backorder_open_a.closure_note == "Sourced elsewhere"


def test_fulfillment_backorder_cancel_refused_on_an_already_closed_row(
        fulfillment_backorder_closed_a, admin_user):
    stamped = fulfillment_backorder_closed_a.closed_at
    assert fulfillment_backorder_closed_a.cancel(admin_user, "nope") is False
    fulfillment_backorder_closed_a.refresh_from_db()
    assert fulfillment_backorder_closed_a.status == "fulfilled"
    assert fulfillment_backorder_closed_a.closed_at == stamped
    assert fulfillment_backorder_closed_a.closure_note == "Arrived on the 14th."


def test_fulfillment_backorder_verbs_never_touch_the_spine(fulfillment_backorder_open_a,
                                                           fulfillment_po_line_a, admin_user):
    before = (fulfillment_po_line_a.quantity, fulfillment_po_line_a.unit_price)
    order_before = fulfillment_po_line_a.purchase_order.status

    fulfillment_backorder_open_a.reschedule(
        admin_user, _fulfillment_today() + _fulfillment_days(5), "slip")
    fulfillment_backorder_open_a.fulfil(admin_user, "done")

    fulfillment_po_line_a.refresh_from_db()
    assert (fulfillment_po_line_a.quantity, fulfillment_po_line_a.unit_price) == before
    fulfillment_po_line_a.purchase_order.refresh_from_db()
    assert fulfillment_po_line_a.purchase_order.status == order_before


# ================================================================================================
# 13. Backorder.raise_alert()
# ================================================================================================

def test_fulfillment_backorder_raise_alert_creates_a_delivery_alert(
        fulfillment_backorder_open_a, admin_user):
    alert = fulfillment_backorder_open_a.raise_alert(admin_user)

    assert isinstance(alert, ProcurementAlert)
    assert alert.tenant_id == fulfillment_backorder_open_a.tenant_id
    assert alert.kind == "delivery"
    assert alert.status == "open"
    assert alert.severity == "warning"          # at_risk, not past_due
    assert alert.title == "Backorder %s — Out of Stock" % (
        fulfillment_backorder_open_a.number,)
    assert alert.link_url == reverse("procurement:backorder_detail",
                                     args=[fulfillment_backorder_open_a.pk])
    assert alert.created_by_id == admin_user.pk
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.alert_id == alert.pk


def test_fulfillment_backorder_raise_alert_is_critical_when_past_due(
        fulfillment_backorder_past_due_a, admin_user):
    alert = fulfillment_backorder_past_due_a.raise_alert(admin_user)
    assert alert.severity == "critical"
    assert "Production Delay" in alert.title


def test_fulfillment_backorder_raise_alert_due_at_is_end_of_the_promised_day(
        fulfillment_backorder_open_a, admin_user):
    alert = fulfillment_backorder_open_a.raise_alert(admin_user)
    local_due = timezone.localtime(alert.due_at)
    assert local_due.date() == fulfillment_backorder_open_a.revised_promise_date
    assert (local_due.hour, local_due.minute) == (23, 59)


def test_fulfillment_backorder_raise_alert_without_a_promise_has_no_due_date(
        tenant_a, fulfillment_po_line_a, admin_user):
    row = _fulfillment_backorder(tenant_a, fulfillment_po_line_a, revised_promise_date=None)
    alert = row.raise_alert(admin_user)
    assert alert.due_at is None
    assert "No delivery date has been committed yet." in alert.message


def test_fulfillment_backorder_raise_alert_message_quotes_quantity_and_order(
        fulfillment_backorder_open_a, admin_user):
    alert = fulfillment_backorder_open_a.raise_alert(admin_user)
    assert "Bearing housing 40mm" in alert.message
    assert fulfillment_backorder_open_a.po_line.purchase_order.number in alert.message
    assert str(fulfillment_backorder_open_a.quantity_backordered) in alert.message


def test_fulfillment_backorder_raise_alert_is_idempotent_while_the_alert_is_open(
        fulfillment_backorder_open_a, admin_user):
    first = fulfillment_backorder_open_a.raise_alert(admin_user)
    second = fulfillment_backorder_open_a.raise_alert(admin_user)
    assert first.pk == second.pk
    assert ProcurementAlert.objects.filter(tenant=fulfillment_backorder_open_a.tenant).count() \
        == 1


def test_fulfillment_backorder_raise_alert_re_raises_after_the_first_is_resolved(
        fulfillment_backorder_open_a, admin_user):
    first = fulfillment_backorder_open_a.raise_alert(admin_user)
    ProcurementAlert.objects.filter(pk=first.pk).update(status="resolved")
    fulfillment_backorder_open_a.refresh_from_db()

    second = fulfillment_backorder_open_a.raise_alert(admin_user)
    assert second.pk != first.pk
    assert ProcurementAlert.objects.filter(tenant=fulfillment_backorder_open_a.tenant).count() \
        == 2


def test_fulfillment_backorder_raise_alert_link_url_is_an_internal_path(
        fulfillment_backorder_open_a, admin_user):
    alert = fulfillment_backorder_open_a.raise_alert(admin_user)
    assert alert.link_url.startswith("/")
    assert not alert.link_url.startswith("//")
    assert "\\" not in alert.link_url


# ================================================================================================
# 14. Backorder - clean()
# ================================================================================================

def test_fulfillment_backorder_clean_rejects_more_than_the_ordered_quantity(
        tenant_a, fulfillment_po_line_a):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("11"))
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "Cannot backorder more than" in " ".join(
        excinfo.value.message_dict["quantity_backordered"])


def test_fulfillment_backorder_clean_allows_the_whole_ordered_quantity(tenant_a,
                                                                       fulfillment_po_line_a):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("10"))
    row.full_clean()
    row.save()
    assert row.pk is not None


def test_fulfillment_backorder_clean_rejects_a_cross_tenant_po_line(tenant_a,
                                                                    fulfillment_po_line_b):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_b,
                    quantity_backordered=Decimal("1"))
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["po_line"])


def test_fulfillment_backorder_clean_requires_a_note_when_the_reason_is_other(
        tenant_a, fulfillment_po_line_a):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"), reason="other", reason_note="   ")
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "reason_note" in excinfo.value.message_dict

    row.reason_note = "Supplier gave no explanation"
    row.full_clean()
    row.save()
    assert row.pk is not None


def test_fulfillment_backorder_clean_rejects_a_cross_tenant_delivery_schedule(
        tenant_a, fulfillment_po_line_a, fulfillment_schedule_b):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"),
                    delivery_schedule=fulfillment_schedule_b)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["delivery_schedule"])


def test_fulfillment_backorder_clean_rejects_a_schedule_from_another_order(
        tenant_a, fulfillment_vendor_a, fulfillment_po_line_a):
    other_po = _fulfillment_new_po(tenant_a, fulfillment_vendor_a)
    other_line = _fulfillment_new_po_line(other_po)
    other_schedule = _fulfillment_schedule(tenant_a, other_line)

    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"), delivery_schedule=other_schedule)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "different purchase order" in " ".join(
        excinfo.value.message_dict["delivery_schedule"])


def test_fulfillment_backorder_clean_accepts_a_schedule_on_the_same_order(
        tenant_a, fulfillment_po_line_a, fulfillment_schedule_a):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"),
                    delivery_schedule=fulfillment_schedule_a)
    row.full_clean()
    row.save()
    assert row.delivery_schedule_id == fulfillment_schedule_a.pk


def test_fulfillment_backorder_clean_rejects_a_cross_tenant_asn(tenant_a,
                                                                fulfillment_po_line_a,
                                                                fulfillment_asn_b):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"), asn=fulfillment_asn_b)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "another workspace" in " ".join(excinfo.value.message_dict["asn"])


def test_fulfillment_backorder_clean_rejects_an_asn_from_another_order(
        tenant_a, fulfillment_vendor_a, fulfillment_po_line_a):
    other_po = _fulfillment_new_po(tenant_a, fulfillment_vendor_a)
    _fulfillment_new_po_line(other_po)
    other_asn = _fulfillment_asn(tenant_a, other_po)

    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"), asn=other_asn)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "different purchase order" in " ".join(excinfo.value.message_dict["asn"])


def test_fulfillment_backorder_clean_accepts_an_asn_on_the_same_order(
        tenant_a, fulfillment_po_line_a, fulfillment_asn_draft_a):
    row = Backorder(tenant=tenant_a, po_line=fulfillment_po_line_a,
                    quantity_backordered=Decimal("1"), asn=fulfillment_asn_draft_a)
    row.full_clean()
    row.save()
    assert row.asn_id == fulfillment_asn_draft_a.pk
