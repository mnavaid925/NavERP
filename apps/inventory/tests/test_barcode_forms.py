"""Inventory 5.14 Barcode & RFID Integration — form boundary.

Three surfaces, one rule each:

* ``BarcodeLabelForm`` — the blank payload IS the feature: ``payload`` is OPTIONAL and
  ``model.save()`` derives it from the selected target (item SKU / bin code / lot number /
  free-form ref), so the form never demands it. Tenant-scoped FK dropdowns plus
  ``_reject_foreign`` keep Globex's masters out of Acme's POSTs as field errors.
* ``RfidTagForm`` — status is verb-driven and off the form; ``TenantUniqueMixin`` makes the
  (tenant, epc) unique_together a rendered field error instead of an IntegrityError 500.
* ``ScanSessionForm`` — deliberately tiny (device_label / mode / notes); sessions OPEN at
  create and leave "open" only through close().
"""
import pytest

from apps.inventory.forms import BarcodeLabelForm, RfidTagForm, ScanSessionForm
from apps.inventory.models import BarcodeLabel, RfidTag, ScanSession

pytestmark = pytest.mark.django_db


def _barcode_label_data(item=None, **overrides):
    """A minimal VALID label body; payload left blank — derivation is the feature."""
    data = {
        "label_kind": "product",
        "target_type": "item",
        "item": "" if item is None else str(item.pk),
        "location": "",
        "lot_serial": "",
        "target_ref": "",
        "pallet_ref": "",
        "symbology": "code128",
        "payload": "",
        "copies": "1",
        "notes": "",
    }
    data.update(overrides)
    return data


def _barcode_tag_data(**overrides):
    data = {
        "epc": "E280-689E-0000-00FF",
        "kind": "passive",
        "item": "",
        "location": "",
        "lot_serial": "",
        "target_ref": "",
        "pallet_ref": "",
        "notes": "",
    }
    data.update(overrides)
    return data


def test_barcode_label_form_without_payload_derives_it_on_save(tenant_a, item_a):
    """A valid create with NO payload saves fine and derives the encoded string from the
    item SKU during model save(); the LBL- number is minted too."""
    form = BarcodeLabelForm(data=_barcode_label_data(item_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.instance.tenant_id == tenant_a.pk
    obj = form.save()
    assert obj.payload == item_a.sku
    assert obj.number.startswith("LBL-")
    assert obj.status == "draft"
    assert BarcodeLabel.objects.filter(pk=obj.pk).exists()


def test_barcode_label_form_rejects_a_foreign_item_with_a_field_error(
        tenant_a, item_b):
    """Globex's item pk smuggled into Acme's POST is a rendered 'item' error, never a 500
    or a saved cross-tenant label."""
    form = BarcodeLabelForm(data=_barcode_label_data(item_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors
    assert BarcodeLabel.objects.filter(tenant=tenant_a).count() == 0


def test_barcode_rfid_tag_form_duplicate_epc_invalid_same_tenant_ok_other_tenant(
        tenant_a, tenant_b, rfid_tag_active_a):
    """(tenant, epc) uniqueness validates at the FORM boundary: the same EPC re-registers
    in Acme as an 'epc' field error, while Globex may register its own copy freely."""
    dup = RfidTagForm(data=_barcode_tag_data(epc=rfid_tag_active_a.epc), tenant=tenant_a)
    assert not dup.is_valid()
    # unique_together violations surface as a NON-FIELD error in Django forms
    assert dup.non_field_errors() or "epc" in dup.errors

    foreign = RfidTagForm(
        data=_barcode_tag_data(epc=rfid_tag_active_a.epc.lower()), tenant=tenant_b)
    assert foreign.is_valid(), foreign.errors
    obj = foreign.save()
    assert obj.tenant_id == tenant_b.pk  # same EPC, other workspace — legal


def test_barcode_rfid_tag_form_keeps_status_off_the_fields(tenant_a):
    """Status moves only through activate/retire/mark-lost — it is not a form field, so a
    crafted POST carrying status=active loses it silently."""
    assert "status" not in RfidTagForm.Meta.fields
    form = RfidTagForm(
        data=_barcode_tag_data(status="active", last_seen_at="2026-01-01T00:00"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    for key in ["status", "last_seen_at"]:
        assert key not in form.fields
        assert key not in form.cleaned_data


def test_barcode_scan_session_form_is_minimal_and_opens_the_session(tenant_a):
    """The session form is exactly device_label/mode/notes; saving mints an OPEN SSN-
    numbered session with operator/timestamps system-owned."""
    assert ScanSessionForm.Meta.fields == ["device_label", "mode", "notes"]
    form = ScanSessionForm(
        data={"device_label": "Honeywell CT60 - Door B", "mode": "single", "notes": ""},
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert isinstance(obj, ScanSession)
    assert obj.number.startswith("SSN")
    assert obj.status == "open"
    assert obj.ended_at is None
