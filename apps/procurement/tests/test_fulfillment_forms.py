"""Procurement 6.11 Order Fulfillment & Tracking — form tests.

The forms are the crafted-POST boundary for this sub-module, so this lane asserts three
things over and over:

1. **Nothing system-owned reaches a form field** (L20/L22). ``tenant``, the auto-numbers
   (``ASN-`` / ``DSC-`` / ``BKO-``), ``created_by``, the verb-only workflow ``status`` on the
   ASN and the Backorder, the whole proof-of-delivery block, the derived ``reschedule_count``
   and every system ``*_at`` timestamp stay OFF the form. ``DeliverySchedule.status`` is the
   one deliberate inclusion — that ladder stamps nothing, so there is no verb to protect.
2. **Every FK ``<select>`` is tenant-scoped** — a field offered to tenant A never contains a
   tenant B row.
3. **The narrowed ``<select>`` is UX, not the boundary.** Each cross-tenant case is asserted
   TWICE: once against the narrowed queryset (layer 1, "Select a valid choice") and once with
   the queryset deliberately widened to simulate a hand-edited POST (layer 2, the explicit
   ``_reject_foreign`` / model ``clean()`` rule message).

Dates derive from ``timezone.localdate()`` — never ``date.today()`` — so exact-date
assertions stay stable in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.utils import timezone

from apps.procurement.forms import (
    AdvancedShipmentNoticeForm,
    AsnCancelForm,
    AsnDeliveryConfirmForm,
    AsnLineForm,
    AsnLineFormSet,
    BackorderCloseForm,
    BackorderForm,
    BackorderRescheduleForm,
    DeliveryScheduleForm,
    DeliveryScheduleSplitForm,
)
from apps.procurement.models import AdvancedShipmentNotice, DeliverySchedule
from apps.scm.models import Carrier, PurchaseOrder, PurchaseOrderLine, Shipment

pytestmark = pytest.mark.django_db


# -- local helpers (module-level names are _fulfillment_* so a later sub-module cannot shadow) --

_FULFILLMENT_FOREIGN = "That record belongs to another workspace."


def _fulfillment_day(offset=0):
    """A date derived from the SAME basis the models use (L16)."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _fulfillment_iso(offset=0):
    return _fulfillment_day(offset).strftime("%Y-%m-%d")


def _fulfillment_extra_po(tenant, vendor, status="approved", qty="8",
                          description="Spare coupling 25mm"):
    """A SECOND order in the same workspace — the 'different purchase order' rejection case."""
    po = PurchaseOrder.objects.create(tenant=tenant, vendor=vendor, status=status,
                                      order_date=timezone.localdate())
    PurchaseOrderLine.objects.create(purchase_order=po, item_description=description,
                                     quantity=Decimal(qty), unit_price=Decimal("12.00"),
                                     sku_hint="SPR-25", uom_hint="EA")
    po.recalc_totals()
    return po


def _fulfillment_asn_post(po=None, **overrides):
    data = {"source": "manual", "supplier_reference": "", "carrier_name": "",
            "tracking_number": "", "notes": ""}
    if po is not None:
        data["purchase_order"] = str(po.pk)
    data.update(overrides)
    return data


def _fulfillment_schedule_post(po_line=None, **overrides):
    data = {"sequence": "3", "scheduled_quantity": "2", "need_by_date": _fulfillment_iso(7),
            "status": "planned", "delivery_mode": "standard", "change_reason": "", "notes": ""}
    if po_line is not None:
        data["po_line"] = str(po_line.pk)
    data.update(overrides)
    return data


def _fulfillment_backorder_post(po_line=None, **overrides):
    data = {"quantity_backordered": "2", "reason": "out_of_stock", "reason_note": "",
            "notes": ""}
    if po_line is not None:
        data["po_line"] = str(po_line.pk)
    data.update(overrides)
    return data


def _fulfillment_lines_post(rows, initial=0, prefix="lines"):
    """Management form + row keys for ``AsnLineFormSet`` under the view's ``lines`` prefix."""
    data = {f"{prefix}-TOTAL_FORMS": str(len(rows)),
            f"{prefix}-INITIAL_FORMS": str(initial),
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "50"}
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f"{prefix}-{index}-{key}"] = value
    return data


def _fulfillment_widen(form, name, queryset):
    """Simulate a crafted POST: drop the narrowing so layer 2 (the explicit re-check) is what
    has to refuse the foreign pk."""
    form.fields[name].queryset = queryset
    return form


# =====================================================================================
# 1. Meta.fields contract — the mass-assignment guard (L20/L22)
# =====================================================================================

def test_fulfillment_asn_form_meta_fields_match_contract_exactly():
    assert AdvancedShipmentNoticeForm.Meta.fields == [
        "purchase_order", "supplier_reference", "source", "ship_date",
        "expected_delivery_date", "carrier", "carrier_name", "tracking_number", "shipment",
        "bill_of_lading_ref", "container_ref", "freight_terms", "package_count",
        "pallet_count", "gross_weight_kg", "volume_cbm", "notes",
    ]


def test_fulfillment_asn_form_never_exposes_system_or_pod_fields(tenant_a, fulfillment_po_a):
    """tenant / number / the verb-only status / the WHOLE proof-of-delivery block / created_by
    / every verb stamp / the system timestamps must not be typeable."""
    banned = {"tenant", "number", "status",
              "delivered_at", "arrival_condition", "pod_reference",
              "received_signature_name", "confirmed_by",
              "created_by", "submitted_at", "cancelled_at", "cancellation_reason",
              "created_at", "updated_at"}
    assert not banned & set(AdvancedShipmentNoticeForm.Meta.fields)
    form = AdvancedShipmentNoticeForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(AdvancedShipmentNoticeForm.Meta.fields)


def test_fulfillment_asnline_form_meta_fields_match_contract_exactly():
    assert AsnLineForm.Meta.fields == [
        "po_line", "item_description", "sku_hint", "uom_hint", "quantity_shipped",
        "package_ref", "lot_number", "serial_number", "expiry_date", "country_of_origin",
        "notes",
    ]
    # AsnLine carries no tenant / number / status columns at all — nothing to leak.
    assert not {"tenant", "number", "status", "asn"} & set(AsnLineForm.Meta.fields)


def test_fulfillment_deliveryschedule_form_meta_fields_match_contract_exactly(tenant_a):
    assert DeliveryScheduleForm.Meta.fields == [
        "po_line", "sequence", "scheduled_quantity", "need_by_date",
        "promised_quantity", "promised_date", "status", "ship_to", "delivery_mode",
        "asn", "change_reason", "notes",
    ]
    banned = {"tenant", "number", "created_by", "created_at", "updated_at"}
    form = DeliveryScheduleForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(DeliveryScheduleForm.Meta.fields)


def test_fulfillment_deliveryschedule_status_is_deliberately_a_form_field(tenant_a):
    """Unlike the ASN's and the Backorder's: this ladder hangs no timestamp and no who-stamp
    off its own status, so there is nothing for a verb method to protect."""
    form = DeliveryScheduleForm(tenant=tenant_a)
    assert "status" in form.fields
    assert list(form.fields["status"].choices)[-5:] == DeliverySchedule.STATUS_CHOICES
    # ...and the model agrees: no editable=False on it.
    assert DeliverySchedule._meta.get_field("status").editable is True


def test_fulfillment_backorder_form_meta_fields_match_contract_exactly(tenant_a):
    assert BackorderForm.Meta.fields == [
        "po_line", "delivery_schedule", "asn", "quantity_backordered",
        "reason", "reason_note", "original_promise_date", "revised_promise_date",
        "notes",
    ]
    banned = {"tenant", "number", "status", "reschedule_count", "closed_at", "closure_note",
              "alert", "created_by", "created_at", "updated_at"}
    assert not banned & set(BackorderForm.Meta.fields)
    form = BackorderForm(tenant=tenant_a)
    assert not banned & set(form.fields)


def test_fulfillment_workflow_status_columns_are_not_editable_on_the_verb_models():
    """The model-side half of the same contract — a status a verb owns is editable=False, so
    even a raw ModelForm built elsewhere cannot render it."""
    assert AdvancedShipmentNotice._meta.get_field("status").editable is False
    for name in ("delivered_at", "arrival_condition", "pod_reference",
                 "received_signature_name", "confirmed_by", "submitted_at",
                 "cancelled_at", "cancellation_reason", "created_by", "number"):
        assert AdvancedShipmentNotice._meta.get_field(name).editable is False, name


# =====================================================================================
# 2. AdvancedShipmentNoticeForm
# =====================================================================================

def test_fulfillment_asn_form_requires_a_purchase_order(tenant_a):
    form = AdvancedShipmentNoticeForm(_fulfillment_asn_post(), tenant=tenant_a)
    assert not form.is_valid()
    assert "purchase_order" in form.errors


def test_fulfillment_asn_form_valid_create_stamps_tenant_and_leaves_number_and_status_alone(
        tenant_a, fulfillment_po_a):
    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(fulfillment_po_a, supplier_reference="NW-DN-5555",
                              ship_date=_fulfillment_iso(-1),
                              expected_delivery_date=_fulfillment_iso(4)),
        tenant=tenant_a)
    # TenantUniqueMixin stamped the instance BEFORE full_clean — that is what lets the model's
    # own cross-tenant checks run on CREATE instead of falsely rejecting every row.
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.tenant_id == tenant_a.pk
    assert not obj.number
    assert obj.status == "draft"
    assert obj.delivered_at is None and obj.pod_reference == ""
    obj.save()
    assert obj.number.startswith("ASN-")
    assert obj.ship_date == _fulfillment_day(-1)
    assert obj.expected_delivery_date == _fulfillment_day(4)


def test_fulfillment_asn_form_purchase_order_queryset_is_receivable_and_tenant_scoped(
        tenant_a, fulfillment_po_a, fulfillment_po_b, fulfillment_vendor_a):
    draft_order = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a, status="draft")
    choices = set(AdvancedShipmentNoticeForm(tenant=tenant_a).fields["purchase_order"].queryset)
    assert fulfillment_po_a in choices
    assert draft_order not in choices          # not a RECEIVABLE status
    assert fulfillment_po_b not in choices     # another workspace


def test_fulfillment_asn_form_carrier_and_shipment_querysets_are_tenant_scoped(
        tenant_a, fulfillment_carrier_a, fulfillment_carrier_b,
        fulfillment_shipment_inbound_a, fulfillment_shipment_outbound_a,
        fulfillment_shipment_inbound_b):
    form = AdvancedShipmentNoticeForm(tenant=tenant_a)
    carriers = set(form.fields["carrier"].queryset)
    assert fulfillment_carrier_a in carriers
    assert fulfillment_carrier_b not in carriers

    shipments = set(form.fields["shipment"].queryset)
    assert fulfillment_shipment_inbound_a in shipments
    assert fulfillment_shipment_outbound_a not in shipments   # an ASN tracks INBOUND only
    assert fulfillment_shipment_inbound_b not in shipments    # another workspace


def test_fulfillment_asn_form_tenantless_offers_no_rows_at_all(
        fulfillment_po_a, fulfillment_carrier_a, fulfillment_shipment_inbound_a):
    form = AdvancedShipmentNoticeForm(tenant=None)
    for name in ("purchase_order", "carrier", "shipment"):
        assert not form.fields[name].queryset.exists(), name


def test_fulfillment_asn_edit_form_drops_purchase_order_entirely(
        tenant_a, fulfillment_asn_draft_a):
    create_form = AdvancedShipmentNoticeForm(tenant=tenant_a)
    assert "purchase_order" in create_form.fields

    edit_form = AdvancedShipmentNoticeForm(instance=fulfillment_asn_draft_a, tenant=tenant_a)
    # Re-pointing a saved ASN would orphan every AsnLine's po_line — the field is not hidden,
    # it is gone, so a crafted POST has nothing to bind to.
    assert "purchase_order" not in edit_form.fields


def test_fulfillment_asn_edit_form_ignores_a_posted_purchase_order(
        tenant_a, fulfillment_asn_draft_a, fulfillment_vendor_a):
    other = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a)
    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(other, supplier_reference="NW-DN-1001"),
        instance=fulfillment_asn_draft_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.purchase_order_id != other.pk     # the posted pk was never bound


def test_fulfillment_asn_form_rejects_foreign_purchase_order_both_layers(
        tenant_a, fulfillment_po_b):
    data = _fulfillment_asn_post(fulfillment_po_b)

    scoped = AdvancedShipmentNoticeForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "purchase_order" in scoped.errors                     # layer 1: narrowed <select>

    loose = _fulfillment_widen(AdvancedShipmentNoticeForm(data, tenant=tenant_a),
                               "purchase_order", PurchaseOrder.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["purchase_order"]  # layer 2: _reject_foreign


def test_fulfillment_asn_form_rejects_foreign_carrier_both_layers(
        tenant_a, fulfillment_po_a, fulfillment_carrier_b):
    data = _fulfillment_asn_post(fulfillment_po_a, carrier=str(fulfillment_carrier_b.pk),
                                 supplier_reference="NW-DN-6001")

    scoped = AdvancedShipmentNoticeForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "carrier" in scoped.errors

    loose = _fulfillment_widen(AdvancedShipmentNoticeForm(data, tenant=tenant_a),
                               "carrier", Carrier.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["carrier"]


def test_fulfillment_asn_form_rejects_foreign_shipment_both_layers(
        tenant_a, fulfillment_po_a, fulfillment_shipment_inbound_b):
    data = _fulfillment_asn_post(fulfillment_po_a,
                                 shipment=str(fulfillment_shipment_inbound_b.pk),
                                 supplier_reference="NW-DN-6002")

    scoped = AdvancedShipmentNoticeForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "shipment" in scoped.errors

    loose = _fulfillment_widen(AdvancedShipmentNoticeForm(data, tenant=tenant_a),
                               "shipment", Shipment.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["shipment"]


def test_fulfillment_asn_form_rejects_an_outbound_shipment(
        tenant_a, fulfillment_po_a, fulfillment_shipment_outbound_a):
    data = _fulfillment_asn_post(fulfillment_po_a,
                                 shipment=str(fulfillment_shipment_outbound_a.pk),
                                 supplier_reference="NW-DN-6003")

    scoped = AdvancedShipmentNoticeForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "shipment" in scoped.errors            # layer 1: outbound is not in the <select>

    loose = _fulfillment_widen(AdvancedShipmentNoticeForm(data, tenant=tenant_a),
                               "shipment", Shipment.objects.all())
    assert not loose.is_valid()
    assert "An ASN tracks an INBOUND shipment from a supplier." in loose.errors["shipment"]


def test_fulfillment_asn_form_rejects_a_duplicate_live_supplier_reference(
        tenant_a, fulfillment_po_a, fulfillment_asn_draft_a):
    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(fulfillment_po_a, supplier_reference="NW-DN-1001"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier_reference" in form.errors
    assert any("already carries that supplier reference" in message
               for message in form.errors["supplier_reference"])


def test_fulfillment_asn_form_allows_reusing_a_cancelled_notices_reference(
        tenant_a, admin_user, fulfillment_po_a):
    dead = AdvancedShipmentNotice.objects.create(
        tenant=tenant_a, purchase_order=fulfillment_po_a, supplier_reference="NW-DN-7007")
    assert dead.cancel(admin_user, "Supplier re-issued the note.") is True

    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(fulfillment_po_a, supplier_reference="NW-DN-7007"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_fulfillment_asn_form_rejects_a_delivery_expected_before_it_ships(
        tenant_a, fulfillment_po_a):
    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(fulfillment_po_a, supplier_reference="NW-DN-6004",
                              ship_date=_fulfillment_iso(5),
                              expected_delivery_date=_fulfillment_iso(2)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "Delivery cannot be expected before it ships." in \
        form.errors["expected_delivery_date"]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "abc", "-4.00",
                                 "12345678901234567.89"])
def test_fulfillment_asn_form_gross_weight_garbage_is_a_field_error_never_an_exception(
        tenant_a, fulfillment_po_a, bad):
    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(fulfillment_po_a, supplier_reference=f"NW-{bad[:8]}",
                              gross_weight_kg=bad),
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "gross_weight_kg" in form.errors


def test_fulfillment_asn_form_edit_remaps_a_model_error_on_the_dropped_field(
        tenant_a, fulfillment_asn_draft_a, fulfillment_po_b):
    """Regression for the ``add_error`` override.

    ``purchase_order`` is popped on EDIT, but ``Model.clean()`` still validates it and
    ``_post_clean`` funnels that error dict into ``add_error(None, …)`` — where stock Django
    raises ``ValueError`` for a key with no matching field, i.e. a 500 on POST. Corrupt the
    stored FK past ``clean()`` (``queryset.update``) to reproduce the exact condition.
    """
    AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_draft_a.pk).update(
        purchase_order=fulfillment_po_b)
    stale = AdvancedShipmentNotice.objects.get(pk=fulfillment_asn_draft_a.pk)

    form = AdvancedShipmentNoticeForm(
        _fulfillment_asn_post(supplier_reference="NW-DN-1001"),
        instance=stale, tenant=tenant_a)
    assert "purchase_order" not in form.fields
    assert form.is_valid() is False                       # renders, never raises ValueError
    assert "purchase_order" not in form.errors
    assert "That purchase order belongs to another workspace." in \
        form.errors[NON_FIELD_ERRORS]


def test_fulfillment_asn_form_add_error_on_a_dropped_field_lands_as_non_field(
        tenant_a, fulfillment_asn_draft_a):
    form = AdvancedShipmentNoticeForm(_fulfillment_asn_post(), instance=fulfillment_asn_draft_a,
                                      tenant=tenant_a)
    form.is_valid()
    form.add_error("purchase_order", "Dropped-field message.")
    assert "Dropped-field message." in form.errors[NON_FIELD_ERRORS]

    form.add_error(None, ValidationError({"purchase_order": ["From the model."],
                                          "supplier_reference": ["Stays on its field."]}))
    assert "From the model." in form.errors[NON_FIELD_ERRORS]
    assert "Stays on its field." in form.errors["supplier_reference"]


# =====================================================================================
# 3. AsnLineForm / AsnLineFormSet
# =====================================================================================

def test_fulfillment_asnline_form_is_a_plain_modelform_with_relaxed_description():
    assert issubclass(AsnLineForm, forms.ModelForm)
    form = AsnLineForm()                      # no tenant kwarg — AsnLine has no tenant column
    assert form.fields["item_description"].required is False
    assert form.fields["expiry_date"].input_formats == ["%Y-%m-%d"]
    assert form.fields["quantity_shipped"].required is True


def test_fulfillment_asnlineformset_factory_contract():
    assert AsnLineFormSet.extra == 1
    assert AsnLineFormSet.can_delete is True
    assert AsnLineFormSet.max_num == 50
    assert AsnLineFormSet.validate_max is True
    assert issubclass(AsnLineFormSet.form, AsnLineForm)


def test_fulfillment_asnlineformset_narrows_po_line_to_the_parent_order(
        fulfillment_asn_draft_a, fulfillment_po_line_a, fulfillment_po_line2_a,
        fulfillment_po_line_b, tenant_a, fulfillment_vendor_a):
    other_line = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a).lines.first()
    formset = AsnLineFormSet(instance=fulfillment_asn_draft_a, prefix="lines")
    offered = set(formset.forms[0].fields["po_line"].queryset)
    assert offered == {fulfillment_po_line_a, fulfillment_po_line2_a}
    assert other_line not in offered
    assert fulfillment_po_line_b not in offered


def test_fulfillment_asnlineformset_saves_a_row_and_copies_the_blank_item_text(
        fulfillment_asn_draft_a, fulfillment_po_line2_a):
    data = _fulfillment_lines_post([
        {"po_line": str(fulfillment_po_line2_a.pk), "quantity_shipped": "2",
         "item_description": "", "sku_hint": "", "uom_hint": ""},
    ])
    formset = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    rows = formset.save()
    assert len(rows) == 1
    assert rows[0].item_description == "Drive belt 1200mm"     # copied in AsnLine.save()
    assert rows[0].sku_hint == "BLT-1200"
    assert rows[0].quantity_shipped == Decimal("2")


def test_fulfillment_asnlineformset_rejects_a_line_from_another_order_both_layers(
        fulfillment_asn_draft_a, tenant_a, fulfillment_vendor_a):
    other_line = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a).lines.first()
    data = _fulfillment_lines_post([
        {"po_line": str(other_line.pk), "quantity_shipped": "1"},
    ])

    scoped = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    assert not scoped.is_valid()
    assert "po_line" in scoped.forms[0].errors           # layer 1: narrowed <select>

    loose = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    for form in loose.forms:
        _fulfillment_widen(form, "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert "That line belongs to a different purchase order." in \
        loose.forms[0].errors["po_line"]


def test_fulfillment_asnlineformset_rejects_a_cross_tenant_line(
        fulfillment_asn_draft_a, fulfillment_po_line_b):
    data = _fulfillment_lines_post([
        {"po_line": str(fulfillment_po_line_b.pk), "quantity_shipped": "1"},
    ])
    loose = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    for form in loose.forms:
        _fulfillment_widen(form, "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert "That line belongs to a different purchase order." in \
        loose.forms[0].errors["po_line"]


def test_fulfillment_asnlineformset_rejects_the_same_line_declared_twice(
        fulfillment_asn_draft_a, fulfillment_po_line_a):
    data = _fulfillment_lines_post([
        {"po_line": str(fulfillment_po_line_a.pk), "quantity_shipped": "4"},
        {"po_line": str(fulfillment_po_line_a.pk), "quantity_shipped": "6"},
    ])
    formset = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    assert not formset.is_valid()
    assert "This PO line is declared by more than one row." in \
        formset.forms[1].errors["po_line"]


def test_fulfillment_asnlineformset_deleted_row_does_not_block_its_replacement(
        fulfillment_asn_draft_a, fulfillment_asn_line_a, fulfillment_po_line_a):
    """Drop a line and re-declare the same PO line in ONE submit.

    The replacement is a NEW instance, so Django's per-form ``instance.validate_unique()`` used
    to find the row this very submit is deleting and refuse it. The formset owns that uniqueness
    now — and the save must genuinely go through, because ``save_existing_objects()`` runs the
    deletion before the insert.
    """
    data = _fulfillment_lines_post([
        {"id": str(fulfillment_asn_line_a.pk), "po_line": str(fulfillment_po_line_a.pk),
         "quantity_shipped": "10", "DELETE": "on"},
        {"po_line": str(fulfillment_po_line_a.pk), "quantity_shipped": "7"},
    ], initial=1)
    formset = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    formset.save()                                   # no IntegrityError on the UNIQUE index
    rows = list(fulfillment_asn_draft_a.lines.all())
    assert len(rows) == 1
    assert rows[0].po_line_id == fulfillment_po_line_a.pk
    assert rows[0].quantity_shipped == Decimal("7")
    assert rows[0].pk != fulfillment_asn_line_a.pk   # the old row really went away


def test_fulfillment_asnlineformset_rejects_a_line_the_notice_already_stores(
        fulfillment_asn_draft_a, fulfillment_asn_line_a, fulfillment_po_line_a):
    """The other half of the same contract: the formset took the model-level unique check off
    the form, so IT has to refuse a new row that collides with a stored row nobody is deleting —
    otherwise the UNIQUE index surfaces as an IntegrityError (a 500) at save."""
    data = _fulfillment_lines_post([
        {"po_line": str(fulfillment_po_line_a.pk), "quantity_shipped": "7"},
    ])
    formset = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    assert not formset.is_valid()
    assert "This notice already declares that PO line." in formset.forms[0].errors["po_line"]


@pytest.mark.parametrize("bad", ["0", "-3", "NaN", "Infinity", "abc"])
def test_fulfillment_asnlineformset_rejects_non_positive_or_garbage_quantity(
        fulfillment_asn_draft_a, fulfillment_po_line_a, bad):
    data = _fulfillment_lines_post([
        {"po_line": str(fulfillment_po_line_a.pk), "quantity_shipped": bad},
    ])
    formset = AsnLineFormSet(data, instance=fulfillment_asn_draft_a, prefix="lines")
    assert formset.is_valid() is False
    assert "quantity_shipped" in formset.forms[0].errors


def test_fulfillment_asnlineformset_empty_extra_row_is_permitted(fulfillment_asn_draft_a):
    formset = AsnLineFormSet(_fulfillment_lines_post([{}]),
                             instance=fulfillment_asn_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    assert formset.save() == []


# =====================================================================================
# 4. DeliveryScheduleForm
# =====================================================================================

def test_fulfillment_schedule_form_querysets_are_tenant_scoped(
        tenant_a, fulfillment_po_line_a, fulfillment_po_line_b, org_unit_a, org_unit_b,
        fulfillment_asn_draft_a, fulfillment_asn_b):
    form = DeliveryScheduleForm(tenant=tenant_a)
    lines = set(form.fields["po_line"].queryset)
    assert fulfillment_po_line_a in lines
    assert fulfillment_po_line_b not in lines
    assert org_unit_a in set(form.fields["ship_to"].queryset)
    assert org_unit_b not in set(form.fields["ship_to"].queryset)
    assert fulfillment_asn_draft_a in set(form.fields["asn"].queryset)
    assert fulfillment_asn_b not in set(form.fields["asn"].queryset)


def test_fulfillment_schedule_form_tenantless_offers_no_rows(
        fulfillment_po_line_a, org_unit_a, fulfillment_asn_draft_a):
    form = DeliveryScheduleForm(tenant=None)
    for name in ("po_line", "ship_to", "asn"):
        assert not form.fields[name].queryset.exists(), name


def test_fulfillment_schedule_form_requires_line_quantity_and_need_by_date(tenant_a):
    form = DeliveryScheduleForm({"status": "planned"}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("po_line", "scheduled_quantity", "need_by_date"):
        assert name in form.errors, name


def test_fulfillment_schedule_form_valid_create_stamps_tenant_and_auto_numbers(
        tenant_a, fulfillment_po_line_a, org_unit_a):
    form = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, sequence="1",
                                   scheduled_quantity="6", ship_to=str(org_unit_a.pk)),
        tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert not obj.number
    assert obj.created_by_id is None
    obj.save()
    assert obj.number.startswith("DSC-")
    assert obj.need_by_date == _fulfillment_day(7)


def test_fulfillment_schedule_form_hard_blocks_over_commitment(
        tenant_a, fulfillment_po_line_a, fulfillment_schedule_a, fulfillment_schedule_late_a):
    """4 + 3 already live against a line of 10 — a fourth instalment of 5 would over-commit."""
    form = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, sequence="3",
                                   scheduled_quantity="5"), tenant=tenant_a)
    assert not form.is_valid()
    assert "scheduled_quantity" in form.errors
    assert any("over-commit" in message for message in form.errors["scheduled_quantity"])


def test_fulfillment_schedule_form_allows_the_exact_remainder(
        tenant_a, fulfillment_po_line_a, fulfillment_schedule_a, fulfillment_schedule_late_a):
    """Positive control: 3 of the 3 still uncommitted is fine — the block is over-commitment,
    not scheduling."""
    form = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, sequence="3",
                                   scheduled_quantity="3"), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_fulfillment_schedule_form_under_coverage_is_never_an_error(
        tenant_a, fulfillment_po_line_a):
    form = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, sequence="1",
                                   scheduled_quantity="1"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.is_under_covered is True          # an amber warning, never a validation error


def test_fulfillment_schedule_form_cancelled_row_is_exempt_from_the_over_commit_block(
        tenant_a, fulfillment_po_line_a, fulfillment_schedule_a, fulfillment_schedule_late_a):
    form = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, sequence="3",
                                   scheduled_quantity="50", status="cancelled"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors          # a cancelled instalment commits nothing


def test_fulfillment_schedule_form_rejects_a_non_positive_promised_quantity(
        tenant_a, fulfillment_po_line_a):
    zero = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, promised_quantity="0"),
        tenant=tenant_a)
    assert not zero.is_valid()
    assert "A promised quantity must be greater than zero." in zero.errors["promised_quantity"]

    negative = DeliveryScheduleForm(
        _fulfillment_schedule_post(fulfillment_po_line_a, promised_quantity="-2"),
        tenant=tenant_a)
    assert not negative.is_valid()
    assert "promised_quantity" in negative.errors


def test_fulfillment_schedule_form_rejects_a_foreign_po_line_both_layers(
        tenant_a, fulfillment_po_line_b):
    data = _fulfillment_schedule_post(fulfillment_po_line_b)

    scoped = DeliveryScheduleForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "po_line" in scoped.errors

    loose = _fulfillment_widen(DeliveryScheduleForm(data, tenant=tenant_a),
                               "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["po_line"]


def test_fulfillment_schedule_form_rejects_a_foreign_ship_to_both_layers(
        tenant_a, fulfillment_po_line_a, org_unit_b):
    from apps.core.models import OrgUnit
    data = _fulfillment_schedule_post(fulfillment_po_line_a, ship_to=str(org_unit_b.pk))

    scoped = DeliveryScheduleForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "ship_to" in scoped.errors

    loose = _fulfillment_widen(DeliveryScheduleForm(data, tenant=tenant_a),
                               "ship_to", OrgUnit.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["ship_to"]


def test_fulfillment_schedule_form_rejects_a_foreign_asn_both_layers(
        tenant_a, fulfillment_po_line_a, fulfillment_asn_b):
    data = _fulfillment_schedule_post(fulfillment_po_line_a, asn=str(fulfillment_asn_b.pk))

    scoped = DeliveryScheduleForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "asn" in scoped.errors

    loose = _fulfillment_widen(DeliveryScheduleForm(data, tenant=tenant_a),
                               "asn", AdvancedShipmentNotice.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["asn"]


def test_fulfillment_schedule_form_rejects_an_asn_from_a_different_order(
        tenant_a, fulfillment_vendor_a, fulfillment_asn_draft_a):
    other_line = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a).lines.first()
    form = DeliveryScheduleForm(
        _fulfillment_schedule_post(other_line, sequence="1", scheduled_quantity="2",
                                   asn=str(fulfillment_asn_draft_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That ASN belongs to another workspace or another order." in form.errors["asn"]


def test_fulfillment_schedule_form_date_fields_parse_the_widget_format(tenant_a):
    form = DeliveryScheduleForm(tenant=tenant_a)
    for name in ("need_by_date", "promised_date"):
        assert form.fields[name].input_formats == ["%Y-%m-%d"]
        # Django 5 Input.__init__ pops "type" out of attrs into widget.input_type, so the
        # rendered <input type="date"> is asserted there — never in widget.attrs.
        assert form.fields[name].widget.input_type == "date"
        assert 'type="date"' in str(form[name])


# =====================================================================================
# 5. DeliveryScheduleSplitForm
# =====================================================================================

def test_fulfillment_split_form_asks_only_the_four_facts_a_split_needs(tenant_a):
    form = DeliveryScheduleSplitForm(tenant=tenant_a)
    assert set(form.fields) == {"po_line", "instalments", "first_date", "interval_days"}
    # Quantities are COMPUTED by split_po_line(), never typed.
    assert not {"scheduled_quantity", "quantity", "promised_quantity"} & set(form.fields)


def test_fulfillment_split_form_po_line_queryset_is_tenant_scoped(
        tenant_a, fulfillment_po_line_a, fulfillment_po_line_b):
    offered = set(DeliveryScheduleSplitForm(tenant=tenant_a).fields["po_line"].queryset)
    assert fulfillment_po_line_a in offered
    assert fulfillment_po_line_b not in offered
    assert not DeliveryScheduleSplitForm(tenant=None).fields["po_line"].queryset.exists()


def test_fulfillment_split_form_requires_line_and_first_date(tenant_a):
    form = DeliveryScheduleSplitForm({"instalments": "3", "interval_days": "14"},
                                     tenant=tenant_a)
    assert not form.is_valid()
    assert "po_line" in form.errors
    assert "first_date" in form.errors


@pytest.mark.parametrize("instalments,valid", [("1", False), ("2", True), ("12", True),
                                               ("13", False), ("abc", False)])
def test_fulfillment_split_form_enforces_the_instalment_bounds(
        tenant_a, fulfillment_po_line_a, instalments, valid):
    form = DeliveryScheduleSplitForm(
        {"po_line": str(fulfillment_po_line_a.pk), "instalments": instalments,
         "first_date": _fulfillment_iso(3), "interval_days": "7"}, tenant=tenant_a)
    assert form.is_valid() is valid, form.errors
    if not valid:
        assert "instalments" in form.errors
    assert DeliverySchedule.MAX_SPLIT_INSTALMENTS == 12


@pytest.mark.parametrize("interval,valid", [("0", False), ("1", True), ("365", True),
                                            ("366", False), ("NaN", False)])
def test_fulfillment_split_form_enforces_the_interval_bounds(
        tenant_a, fulfillment_po_line_a, interval, valid):
    form = DeliveryScheduleSplitForm(
        {"po_line": str(fulfillment_po_line_a.pk), "instalments": "3",
         "first_date": _fulfillment_iso(3), "interval_days": interval}, tenant=tenant_a)
    assert form.is_valid() is valid, form.errors
    if not valid:
        assert "interval_days" in form.errors


def test_fulfillment_split_form_rejects_a_foreign_po_line(tenant_a, fulfillment_po_line_b):
    form = DeliveryScheduleSplitForm(
        {"po_line": str(fulfillment_po_line_b.pk), "instalments": "3",
         "first_date": _fulfillment_iso(3), "interval_days": "7"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "po_line" in form.errors


def test_fulfillment_split_form_first_date_parses_the_widget_format(tenant_a,
                                                                    fulfillment_po_line_a):
    form = DeliveryScheduleSplitForm(
        {"po_line": str(fulfillment_po_line_a.pk), "instalments": "2",
         "first_date": _fulfillment_iso(3), "interval_days": "7"}, tenant=tenant_a)
    assert form.fields["first_date"].input_formats == ["%Y-%m-%d"]
    assert form.is_valid(), form.errors
    assert form.cleaned_data["first_date"] == _fulfillment_day(3)


# =====================================================================================
# 6. BackorderForm
# =====================================================================================

def test_fulfillment_backorder_form_querysets_are_tenant_scoped(
        tenant_a, fulfillment_po_line_a, fulfillment_po_line_b, fulfillment_schedule_a,
        fulfillment_schedule_b, fulfillment_asn_draft_a, fulfillment_asn_b):
    form = BackorderForm(tenant=tenant_a)
    assert fulfillment_po_line_a in set(form.fields["po_line"].queryset)
    assert fulfillment_po_line_b not in set(form.fields["po_line"].queryset)
    assert fulfillment_schedule_a in set(form.fields["delivery_schedule"].queryset)
    assert fulfillment_schedule_b not in set(form.fields["delivery_schedule"].queryset)
    assert fulfillment_asn_draft_a in set(form.fields["asn"].queryset)
    assert fulfillment_asn_b not in set(form.fields["asn"].queryset)


def test_fulfillment_backorder_form_tenantless_offers_no_rows(
        fulfillment_po_line_a, fulfillment_schedule_a, fulfillment_asn_draft_a):
    form = BackorderForm(tenant=None)
    for name in ("po_line", "delivery_schedule", "asn"):
        assert not form.fields[name].queryset.exists(), name


def test_fulfillment_backorder_form_requires_line_and_quantity(tenant_a):
    form = BackorderForm({"reason": "out_of_stock"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "po_line" in form.errors
    assert "quantity_backordered" in form.errors


def test_fulfillment_backorder_form_valid_create_leaves_the_verb_state_alone(
        tenant_a, fulfillment_po_line_a):
    form = BackorderForm(
        _fulfillment_backorder_post(fulfillment_po_line_a, quantity_backordered="3",
                                    original_promise_date=_fulfillment_iso(-4),
                                    revised_promise_date=_fulfillment_iso(6)),
        tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.status == "open"                 # status is not a form field
    assert obj.reschedule_count == 0            # the slip counter is verb-owned
    assert obj.closed_at is None and obj.closure_note == ""
    assert obj.alert_id is None
    assert not obj.number
    obj.save()
    assert obj.number.startswith("BKO-")
    assert obj.revised_promise_date == _fulfillment_day(6)


def test_fulfillment_backorder_edit_form_drops_revised_promise_date(
        tenant_a, fulfillment_backorder_open_a):
    create_form = BackorderForm(tenant=tenant_a)
    assert "revised_promise_date" in create_form.fields

    edit_form = BackorderForm(instance=fulfillment_backorder_open_a, tenant=tenant_a)
    # The promise may only move through reschedule(), which counts the slip.
    assert "revised_promise_date" not in edit_form.fields


def test_fulfillment_backorder_edit_form_ignores_a_posted_revised_promise_date(
        tenant_a, fulfillment_backorder_open_a, fulfillment_po_line_a):
    before = fulfillment_backorder_open_a.revised_promise_date
    form = BackorderForm(
        _fulfillment_backorder_post(fulfillment_po_line_a, quantity_backordered="3",
                                    revised_promise_date=_fulfillment_iso(90)),
        instance=fulfillment_backorder_open_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.revised_promise_date == before
    assert obj.reschedule_count == 0


def test_fulfillment_backorder_form_rejects_more_than_the_ordered_quantity(
        tenant_a, fulfillment_po_line_a):
    form = BackorderForm(
        _fulfillment_backorder_post(fulfillment_po_line_a, quantity_backordered="11"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert any("Cannot backorder more than" in message
               for message in form.errors["quantity_backordered"])


@pytest.mark.parametrize("bad", ["0", "-2", "NaN", "Infinity", "abc",
                                 "123456789012345.6789"])
def test_fulfillment_backorder_form_quantity_garbage_is_a_field_error_never_an_exception(
        tenant_a, fulfillment_po_line_a, bad):
    form = BackorderForm(
        _fulfillment_backorder_post(fulfillment_po_line_a, quantity_backordered=bad),
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "quantity_backordered" in form.errors


def test_fulfillment_backorder_form_reason_other_demands_a_note(
        tenant_a, fulfillment_po_line_a):
    blank = BackorderForm(
        _fulfillment_backorder_post(fulfillment_po_line_a, reason="other", reason_note="   "),
        tenant=tenant_a)
    assert not blank.is_valid()
    assert "Describe the reason when choosing Other." in blank.errors["reason_note"]

    filled = BackorderForm(
        _fulfillment_backorder_post(fulfillment_po_line_a, reason="other",
                                    reason_note="Vendor changed the spec."),
        tenant=tenant_a)
    assert filled.is_valid(), filled.errors


def test_fulfillment_backorder_form_rejects_a_foreign_po_line_both_layers(
        tenant_a, fulfillment_po_line_b):
    data = _fulfillment_backorder_post(fulfillment_po_line_b)

    scoped = BackorderForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "po_line" in scoped.errors

    loose = _fulfillment_widen(BackorderForm(data, tenant=tenant_a),
                               "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["po_line"]


def test_fulfillment_backorder_form_rejects_a_foreign_delivery_schedule_both_layers(
        tenant_a, fulfillment_po_line_a, fulfillment_schedule_b):
    data = _fulfillment_backorder_post(
        fulfillment_po_line_a, delivery_schedule=str(fulfillment_schedule_b.pk))

    scoped = BackorderForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "delivery_schedule" in scoped.errors

    loose = _fulfillment_widen(BackorderForm(data, tenant=tenant_a),
                               "delivery_schedule", DeliverySchedule.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["delivery_schedule"]


def test_fulfillment_backorder_form_rejects_a_foreign_asn_both_layers(
        tenant_a, fulfillment_po_line_a, fulfillment_asn_b):
    data = _fulfillment_backorder_post(fulfillment_po_line_a, asn=str(fulfillment_asn_b.pk))

    scoped = BackorderForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "asn" in scoped.errors

    loose = _fulfillment_widen(BackorderForm(data, tenant=tenant_a),
                               "asn", AdvancedShipmentNotice.objects.all())
    assert not loose.is_valid()
    assert _FULFILLMENT_FOREIGN in loose.errors["asn"]


def test_fulfillment_backorder_form_rejects_an_asn_from_a_different_order(
        tenant_a, fulfillment_vendor_a, fulfillment_asn_draft_a):
    other_line = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a).lines.first()
    form = BackorderForm(
        _fulfillment_backorder_post(other_line, asn=str(fulfillment_asn_draft_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That shipment notice belongs to a different purchase order." in form.errors["asn"]


def test_fulfillment_backorder_form_rejects_a_schedule_from_a_different_order(
        tenant_a, fulfillment_vendor_a, fulfillment_schedule_a):
    other_line = _fulfillment_extra_po(tenant_a, fulfillment_vendor_a).lines.first()
    form = BackorderForm(
        _fulfillment_backorder_post(other_line,
                                    delivery_schedule=str(fulfillment_schedule_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That delivery schedule belongs to a different purchase order." in \
        form.errors["delivery_schedule"]


# =====================================================================================
# 7. The small action forms (the only writers of the verb-owned columns)
# =====================================================================================

def test_fulfillment_confirm_form_is_the_only_writer_of_the_pod_block():
    assert not issubclass(AsnDeliveryConfirmForm, forms.ModelForm)
    form = AsnDeliveryConfirmForm()
    assert set(form.fields) == {"delivered_at", "arrival_condition", "pod_reference",
                                "received_signature_name"}
    assert form.fields["delivered_at"].required is False
    assert form.fields["arrival_condition"].required is True
    assert form.fields["arrival_condition"].initial == "good"
    assert list(form.fields["arrival_condition"].choices) == \
        AdvancedShipmentNotice.CONDITION_CHOICES
    assert form.fields["pod_reference"].max_length == 64
    assert form.fields["received_signature_name"].max_length == 120
    assert form.fields["delivered_at"].input_formats == [
        "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    # ...and none of them is reachable through the header form.
    assert not set(form.fields) & set(AdvancedShipmentNoticeForm.Meta.fields)


def test_fulfillment_confirm_form_blank_delivered_at_means_now(fulfillment_asn_in_transit_a,
                                                               admin_user):
    form = AsnDeliveryConfirmForm({"arrival_condition": "good", "pod_reference": "POD-1"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["delivered_at"] is None
    assert fulfillment_asn_in_transit_a.confirm_delivery(
        admin_user, delivered_at=form.cleaned_data["delivered_at"]) is True
    assert fulfillment_asn_in_transit_a.delivered_at is not None


def test_fulfillment_confirm_form_requires_a_known_arrival_condition():
    missing = AsnDeliveryConfirmForm({})
    assert not missing.is_valid()
    assert "arrival_condition" in missing.errors

    unknown = AsnDeliveryConfirmForm({"arrival_condition": "exploded"})
    assert not unknown.is_valid()
    assert "arrival_condition" in unknown.errors


def test_fulfillment_confirm_form_parses_the_datetime_local_format():
    stamp = "2026-03-04T09:30"
    form = AsnDeliveryConfirmForm({"delivered_at": stamp, "arrival_condition": "damaged"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["delivered_at"].strftime("%Y-%m-%dT%H:%M") == stamp


def test_fulfillment_cancel_form_demands_a_reason():
    blank = AsnCancelForm({"cancellation_reason": "   "})
    assert not blank.is_valid()
    assert "cancellation_reason" in blank.errors

    assert AsnCancelForm({}).is_valid() is False

    over = AsnCancelForm({"cancellation_reason": "x" * 2001})
    assert not over.is_valid()
    assert "cancellation_reason" in over.errors

    ok = AsnCancelForm({"cancellation_reason": "Supplier withdrew the shipment."})
    assert ok.is_valid(), ok.errors
    assert set(ok.fields) == {"cancellation_reason"}


def test_fulfillment_reschedule_form_demands_both_the_date_and_the_reason():
    assert set(BackorderRescheduleForm().fields) == {"revised_promise_date", "reason_note"}
    empty = BackorderRescheduleForm({})
    assert not empty.is_valid()
    assert "revised_promise_date" in empty.errors
    assert "reason_note" in empty.errors

    date_only = BackorderRescheduleForm({"revised_promise_date": _fulfillment_iso(10)})
    assert not date_only.is_valid()
    assert "reason_note" in date_only.errors

    note_only = BackorderRescheduleForm({"reason_note": "Freight strike."})
    assert not note_only.is_valid()
    assert "revised_promise_date" in note_only.errors


def test_fulfillment_reschedule_form_valid_body_parses_the_widget_date_format():
    form = BackorderRescheduleForm({"revised_promise_date": _fulfillment_iso(10),
                                    "reason_note": "Freight strike at the port."})
    assert form.fields["revised_promise_date"].input_formats == ["%Y-%m-%d"]
    assert form.is_valid(), form.errors
    assert form.cleaned_data["revised_promise_date"] == _fulfillment_day(10)
    assert form.fields["reason_note"].max_length == 255


def test_fulfillment_close_form_note_is_optional_so_an_empty_post_still_closes():
    empty = BackorderCloseForm({})
    assert empty.is_valid(), empty.errors
    assert empty.cleaned_data["closure_note"] == ""
    assert set(empty.fields) == {"closure_note"}

    over = BackorderCloseForm({"closure_note": "n" * 256})
    assert not over.is_valid()
    assert "closure_note" in over.errors
