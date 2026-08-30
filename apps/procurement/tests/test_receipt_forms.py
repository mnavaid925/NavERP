"""Procurement 6.12 Goods Receipt & Inspection - form tests.

The forms are the crafted-POST boundary for this sub-module, so this lane asserts four
things over and over:

1. **Nothing system-owned reaches a form field** (L20/L22). ``tenant``, the auto-numbers
   (``RDS-`` / ``RTV-``), ``created_by``, the verb-only workflow ``status`` on the
   discrepancy and the return, the whole notification/closure block, every verb stamp and
   every system ``*_at`` timestamp stay OFF the form. ``ReceiptTolerancePolicy`` is the
   deliberate counter-example: it is a configuration master with no number and no status at
   all, so there is nothing there to protect.
2. **Every FK ``<select>`` is tenant-scoped** - a field offered to tenant A never contains a
   tenant B row, and a tenant-less form offers nothing at all.
3. **The narrowed ``<select>`` is UX, not the boundary.** Each cross-tenant case is asserted
   TWICE: once against the narrowed queryset (layer 1, "Select a valid choice") and once
   with the queryset deliberately widened to simulate a hand-edited POST (layer 2, the
   explicit ``_reject_foreign`` / model ``clean()`` rule message).
4. **Every hand-parsed number surface is friendly, never a 500** (L35) - ``NaN``,
   ``Infinity``, garbage, negatives and over-``max_digits`` figures land as field errors.

Dates derive from ``timezone.localdate()`` - never ``date.today()`` - so exact-date
assertions stay stable in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.core.forms import TenantModelForm
from apps.core.models import Party, PartyRole
from apps.inventory.models import QuarantineOrder
from apps.procurement.forms import (
    DiscrepancyCancelForm,
    DiscrepancyNotifyForm,
    DiscrepancyResolveForm,
    ReceiptDiscrepancyForm,
    ReceiptTolerancePolicyForm,
    ReceivingConsoleBookForm,
    ReturnToVendorForm,
    ReturnToVendorLineForm,
    ReturnToVendorLineFormSet,
    RtvCancelForm,
    RtvCloseForm,
    RtvShipForm,
)
from apps.procurement.models import (
    AsnLine,
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    ReturnToVendor,
)
from apps.scm.models import (
    GoodsReceiptLine,
    GoodsReceiptNote,
    Item,
    ItemCategory,
    Location,
    NonConformance,
    PurchaseOrder,
    PurchaseOrderLine,
)

pytestmark = pytest.mark.django_db


# -- local helpers (module-level names are _receipt_* so a later sub-module cannot shadow) -----

_RECEIPT_FOREIGN = "That record belongs to another workspace."


def _receipt_day(offset=0):
    """A date derived from the SAME basis the models use (L16)."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _receipt_iso(offset=0):
    return _receipt_day(offset).strftime("%Y-%m-%d")


def _receipt_widen(form, name, queryset):
    """Simulate a crafted POST: drop the narrowing so layer 2 (the explicit re-check) is what
    has to refuse the foreign pk."""
    form.fields[name].queryset = queryset
    return form


def _receipt_widen_rows(formset, name, queryset):
    for row in formset.forms:
        if name in row.fields:
            row.fields[name].queryset = queryset
    return formset


def _receipt_policy_post(**overrides):
    """The minimum a tolerance policy POST must carry: name + action + priority, plus a band."""
    data = {"name": "Workspace 5% band", "action": "warn", "priority": "10",
            "over_receipt_pct": "5", "under_receipt_pct": "", "over_receipt_qty": "",
            "early_receipt_days": "", "late_receipt_days": "", "price_variance_pct": "",
            "notes": "", "is_active": "on"}
    data.update(overrides)
    return data


def _receipt_discrepancy_post(grn=None, **overrides):
    data = {"kind": "short_shipment", "severity": "major", "quantity_affected": "2",
            "item_description": "", "sku_hint": "", "lot_number": "", "serial_number": "",
            "expiry_date": "", "description": "Three cartons short on the pallet.",
            "evidence_url": "", "remedy": "pending", "vendor_reference": ""}
    if grn is not None:
        data["goods_receipt"] = str(grn.pk)
    data.update(overrides)
    return data


def _receipt_rtv_post(vendor=None, **overrides):
    data = {"reason": "damaged", "reason_note": "", "remedy": "credit",
            "supplier_rma_number": "RMA-77", "carrier_name": "", "tracking_number": "",
            "expected_return_date": "", "credit_note_ref": "", "notes": ""}
    if vendor is not None:
        data["vendor"] = str(vendor.pk)
    data.update(overrides)
    return data


def _receipt_lines_post(rows, initial=0, prefix="lines", total=None, max_num="50"):
    """Management form + row keys for ``ReturnToVendorLineFormSet`` under the view's prefix."""
    data = {f"{prefix}-TOTAL_FORMS": str(len(rows) if total is None else total),
            f"{prefix}-INITIAL_FORMS": str(initial),
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": max_num}
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f"{prefix}-{index}-{key}"] = value
    return data


def _receipt_book_post(**overrides):
    data = {"receipt_date": _receipt_iso(), "notes": ""}
    data.update(overrides)
    return data


def _receipt_extra_po(tenant, vendor, status="approved", qty="8",
                      description="Spare coupling 25mm", sku="SPR-25"):
    """A SECOND order in the same workspace - the 'different purchase order' rejection case."""
    po = PurchaseOrder.objects.create(tenant=tenant, vendor=vendor, status=status,
                                      order_date=timezone.localdate(),
                                      expected_date=timezone.localdate())
    PurchaseOrderLine.objects.create(purchase_order=po, item_description=description,
                                     quantity=Decimal(qty), unit_price=Decimal("12.00"),
                                     sku_hint=sku, uom_hint="EA")
    po.recalc_totals()
    return po


def _receipt_roleless_party(tenant, name="Unroled Holdings"):
    """A Party with NO PartyRole - invisible to every 6.12 vendor dropdown by design."""
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _receipt_upload(name="evidence.pdf", size=None, content=b"%PDF-1.4 evidence"):
    upload = SimpleUploadedFile(name, content, content_type="application/octet-stream")
    if size is not None:
        upload.size = size          # avoid allocating 20 MB just to trip the cap
    return upload


# =====================================================================================
# 1. Meta.fields contract - the mass-assignment guard (L20/L22)
# =====================================================================================

def test_receipt_tolerancepolicy_form_meta_fields_match_contract_exactly():
    assert ReceiptTolerancePolicyForm.Meta.fields == [
        "name", "item", "category", "vendor",
        "over_receipt_pct", "under_receipt_pct", "over_receipt_qty",
        "allow_unlimited_over_receipt", "early_receipt_days", "late_receipt_days",
        "action", "price_variance_pct", "priority", "is_active", "notes",
    ]


def test_receipt_tolerancepolicy_form_never_exposes_tenant_or_system_timestamps(tenant_a):
    banned = {"tenant", "created_at", "updated_at", "id"}
    assert not banned & set(ReceiptTolerancePolicyForm.Meta.fields)
    form = ReceiptTolerancePolicyForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(ReceiptTolerancePolicyForm.Meta.fields)


def test_receipt_tolerancepolicy_has_no_number_and_no_status_to_protect():
    """The deliberate counter-example: a configuration master carries neither, so there is no
    auto-number and no workflow column for the form to leak."""
    names = {f.name for f in ReceiptTolerancePolicy._meta.get_fields()}
    assert "number" not in names
    assert "status" not in names
    assert getattr(ReceiptTolerancePolicy, "NUMBER_PREFIX", "") == ""


def test_receipt_discrepancy_form_meta_fields_match_contract_exactly():
    assert ReceiptDiscrepancyForm.Meta.fields == [
        "goods_receipt", "goods_receipt_line", "kind", "severity", "quantity_affected",
        "item_description", "sku_hint", "lot_number", "serial_number", "expiry_date",
        "description", "evidence", "evidence_url", "remedy", "vendor_reference",
        "nonconformance", "quarantine_order", "return_to_vendor",
    ]


def test_receipt_discrepancy_form_never_exposes_system_or_closure_fields(tenant_a):
    """tenant / the RDS- number / the verb-only status / the notification stamp / the whole
    closure block / created_by / the system timestamps must not be typeable."""
    banned = {"tenant", "number", "status", "vendor_notified_on",
              "resolved_at", "resolved_by", "resolution_notes",
              "created_by", "created_at", "updated_at"}
    assert not banned & set(ReceiptDiscrepancyForm.Meta.fields)
    form = ReceiptDiscrepancyForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(ReceiptDiscrepancyForm.Meta.fields)


def test_receipt_discrepancy_model_workflow_columns_are_not_editable():
    """The model-side half of the same contract - a column a verb owns is editable=False, so
    even a raw ModelForm built elsewhere cannot render it."""
    for name in ("number", "status", "vendor_notified_on", "resolved_at", "resolved_by",
                 "resolution_notes", "created_by"):
        assert ReceiptDiscrepancy._meta.get_field(name).editable is False, name


def test_receipt_rtv_form_meta_fields_match_contract_exactly():
    assert ReturnToVendorForm.Meta.fields == [
        "vendor", "purchase_order", "goods_receipt", "discrepancy", "reason", "reason_note",
        "remedy", "supplier_rma_number", "carrier_name", "tracking_number",
        "expected_return_date", "credit_note_ref", "notes",
    ]


def test_receipt_rtv_form_never_exposes_system_or_verb_stamp_fields(tenant_a):
    banned = {"tenant", "number", "status", "shipped_on", "authorized_by", "authorized_at",
              "closed_at", "cancelled_at", "cancellation_reason", "created_by",
              "created_at", "updated_at"}
    assert not banned & set(ReturnToVendorForm.Meta.fields)
    form = ReturnToVendorForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(ReturnToVendorForm.Meta.fields)


def test_receipt_rtv_model_workflow_columns_are_not_editable():
    for name in ("number", "status", "shipped_on", "authorized_by", "authorized_at",
                 "closed_at", "cancelled_at", "cancellation_reason", "created_by"):
        assert ReturnToVendor._meta.get_field(name).editable is False, name


def test_receipt_rtvline_form_meta_fields_match_contract_exactly():
    assert ReturnToVendorLineForm.Meta.fields == [
        "goods_receipt_line", "po_line", "item_description", "sku_hint", "uom_hint",
        "quantity_returned", "lot_number", "serial_number", "condition_note",
    ]
    # The parent FK comes from the inline formset, never from a posted pk.
    assert "return_to_vendor" not in ReturnToVendorLineForm.Meta.fields
    # This child carries no tenant, no number and no status at all - nothing to leak.
    assert not {"tenant", "number", "status"} & set(ReturnToVendorLineForm.Meta.fields)


def test_receipt_verb_forms_declare_only_their_own_fields():
    """Each status-moving dialog carries the note or reference it needs and nothing else -
    never the status column, never a verb timestamp."""
    assert set(DiscrepancyNotifyForm().fields) == {"vendor_reference", "vendor_notified_on"}
    assert set(DiscrepancyResolveForm().fields) == {"remedy", "resolution_notes"}
    assert set(DiscrepancyCancelForm().fields) == {"resolution_notes"}
    assert set(RtvShipForm().fields) == {"carrier_name", "tracking_number", "shipped_on"}
    assert set(RtvCloseForm().fields) == {"credit_note_ref"}
    assert set(RtvCancelForm().fields) == {"cancellation_reason"}
    for form_class in (DiscrepancyNotifyForm, DiscrepancyResolveForm, DiscrepancyCancelForm,
                       RtvShipForm, RtvCloseForm, RtvCancelForm):
        assert "status" not in form_class().fields, form_class.__name__


def test_receipt_console_book_form_declares_no_grn_system_fields(tenant_a, receipt_asn_a):
    """Deliberately NOT a ModelForm over scm.GoodsReceiptNote (L36) - the number, the status,
    the delivery-note key, the order and who received it are all the view's."""
    form = ReceivingConsoleBookForm(asn=receipt_asn_a, tenant=tenant_a)
    assert not isinstance(form, forms.ModelForm)
    banned = {"number", "status", "delivery_note_ref", "purchase_order", "received_by",
              "tenant"}
    assert not banned & set(form.fields)
    assert set(form.fields) == {"receipt_date", "location", "notes"}


# =====================================================================================
# 2. ReceiptTolerancePolicyForm
# =====================================================================================

def test_receipt_tolerancepolicy_form_requires_a_name(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(name=""), tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


def test_receipt_tolerancepolicy_form_valid_create_stamps_tenant_before_full_clean(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(), tenant=tenant_a)
    # TenantUniqueMixin stamped the instance BEFORE full_clean - that is what lets the model's
    # own cross-tenant checks run on CREATE instead of falsely rejecting every row.
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.action == "warn"
    assert obj.over_receipt_pct == Decimal("5")
    assert obj.scope_key == "catchall"
    assert obj.specificity_tier == 1


def test_receipt_tolerancepolicy_form_demands_at_least_one_band(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(over_receipt_pct=""),
                                      tenant=tenant_a)
    assert not form.is_valid()
    assert "over_receipt_pct" in form.errors
    assert "at least one band" in " ".join(form.errors["over_receipt_pct"])


def test_receipt_tolerancepolicy_form_unlimited_flag_counts_as_a_band(tenant_a):
    form = ReceiptTolerancePolicyForm(
        _receipt_policy_post(over_receipt_pct="", allow_unlimited_over_receipt="on"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.allow_unlimited_over_receipt is True
    assert obj.over_band_text == "Unlimited"


def test_receipt_tolerancepolicy_form_date_only_band_is_enough(tenant_a):
    form = ReceiptTolerancePolicyForm(
        _receipt_policy_post(over_receipt_pct="", late_receipt_days="3"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().late_receipt_days == 3


def test_receipt_tolerancepolicy_form_rejects_item_and_category_together(
        tenant_a, receipt_item_a, receipt_category_a):
    form = ReceiptTolerancePolicyForm(
        _receipt_policy_post(item=str(receipt_item_a.pk),
                             category=str(receipt_category_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "Pin the rule to an item OR a category, not both." in form.errors["category"]


def test_receipt_tolerancepolicy_form_item_queryset_is_tenant_scoped(
        tenant_a, receipt_item_a, receipt_item_b):
    offered = set(ReceiptTolerancePolicyForm(tenant=tenant_a).fields["item"].queryset)
    assert receipt_item_a in offered
    assert receipt_item_b not in offered


def test_receipt_tolerancepolicy_form_category_queryset_is_tenant_scoped(
        tenant_a, receipt_category_a, receipt_category_b):
    offered = set(ReceiptTolerancePolicyForm(tenant=tenant_a).fields["category"].queryset)
    assert receipt_category_a in offered
    assert receipt_category_b not in offered


def test_receipt_tolerancepolicy_form_vendor_queryset_is_supplier_role_and_tenant_scoped(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a, receipt_vendor_b):
    roleless = _receipt_roleless_party(tenant_a)
    offered = set(ReceiptTolerancePolicyForm(tenant=tenant_a).fields["vendor"].queryset)
    assert receipt_vendor_a in offered
    assert receipt_vendor_other_a in offered
    assert receipt_vendor_b not in offered      # another workspace
    assert roleless not in offered              # no supplier/vendor PartyRole


def test_receipt_tolerancepolicy_form_vendor_queryset_accepts_the_vendor_role_too(tenant_a):
    party = Party.objects.create(tenant=tenant_a, name="Zenith Tooling", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="vendor", status="active")
    assert party in set(ReceiptTolerancePolicyForm(tenant=tenant_a).fields["vendor"].queryset)


def test_receipt_tolerancepolicy_form_tenantless_offers_no_rows_at_all(
        receipt_item_a, receipt_category_a, receipt_vendor_a):
    form = ReceiptTolerancePolicyForm(tenant=None)
    for name in ("item", "category", "vendor"):
        assert not form.fields[name].queryset.exists(), name
        assert form.fields[name].required is False, name


def test_receipt_tolerancepolicy_form_rejects_foreign_item_both_layers(tenant_a,
                                                                      receipt_item_b):
    data = _receipt_policy_post(item=str(receipt_item_b.pk))

    scoped = ReceiptTolerancePolicyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "item" in scoped.errors                                  # layer 1

    loose = _receipt_widen(ReceiptTolerancePolicyForm(data, tenant=tenant_a),
                           "item", Item.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["item"]                 # layer 2


def test_receipt_tolerancepolicy_form_rejects_foreign_category_both_layers(
        tenant_a, receipt_category_b):
    data = _receipt_policy_post(category=str(receipt_category_b.pk))

    scoped = ReceiptTolerancePolicyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "category" in scoped.errors

    loose = _receipt_widen(ReceiptTolerancePolicyForm(data, tenant=tenant_a),
                           "category", ItemCategory.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["category"]


def test_receipt_tolerancepolicy_form_rejects_foreign_vendor_both_layers(tenant_a,
                                                                        receipt_vendor_b):
    data = _receipt_policy_post(vendor=str(receipt_vendor_b.pk))

    scoped = ReceiptTolerancePolicyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "vendor" in scoped.errors

    loose = _receipt_widen(ReceiptTolerancePolicyForm(data, tenant=tenant_a),
                           "vendor", Party.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["vendor"]


def test_receipt_tolerancepolicy_form_accepts_an_own_tenant_item(tenant_a, receipt_item_a):
    form = ReceiptTolerancePolicyForm(
        _receipt_policy_post(name="BRG-40 strict", item=str(receipt_item_a.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.item_id == receipt_item_a.pk
    assert obj.scope_key == "item" and obj.specificity_tier == 3


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "abc", "", " "])
def test_receipt_tolerancepolicy_form_rejects_junk_percentages_without_500(tenant_a, junk):
    """L35: every hand-typed decimal is a friendly field error, never a crash. A blank falls
    through to the 'give me a band' rule, which is still an error on the same field."""
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(over_receipt_pct=junk),
                                      tenant=tenant_a)
    assert not form.is_valid()
    assert "over_receipt_pct" in form.errors


def test_receipt_tolerancepolicy_form_rejects_a_negative_percentage(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(over_receipt_pct="-5"),
                                      tenant=tenant_a)
    assert not form.is_valid()
    assert "greater than or equal to 0" in " ".join(form.errors["over_receipt_pct"])


def test_receipt_tolerancepolicy_form_rejects_an_over_max_digits_percentage(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(over_receipt_pct="1e400"),
                                      tenant=tenant_a)
    assert not form.is_valid()
    assert "6 digits" in " ".join(form.errors["over_receipt_pct"])


def test_receipt_tolerancepolicy_form_caps_under_receipt_at_a_hundred_percent(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(under_receipt_pct="150"),
                                      tenant=tenant_a)
    assert not form.is_valid()
    assert "less than or equal to 100" in " ".join(form.errors["under_receipt_pct"])


def test_receipt_tolerancepolicy_form_rejects_a_negative_priority(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(priority="-1"), tenant=tenant_a)
    assert not form.is_valid()
    assert "priority" in form.errors


def test_receipt_tolerancepolicy_form_rejects_an_unknown_action(tenant_a):
    form = ReceiptTolerancePolicyForm(_receipt_policy_post(action="explode"), tenant=tenant_a)
    assert not form.is_valid()
    assert "action" in form.errors


def test_receipt_tolerancepolicy_form_action_choices_match_the_model(tenant_a):
    offered = [value for value, _ in
               ReceiptTolerancePolicyForm(tenant=tenant_a).fields["action"].choices if value]
    assert offered == [value for value, _ in ReceiptTolerancePolicy.ACTION_CHOICES]


def test_receipt_tolerancepolicy_form_edits_without_disturbing_the_scope(
        tenant_a, receipt_policy_item_a):
    form = ReceiptTolerancePolicyForm(
        _receipt_policy_post(name="BRG-40 strict v2",
                             item=str(receipt_policy_item_a.item_id),
                             over_receipt_pct="0", action="block_flag", priority="5"),
        instance=receipt_policy_item_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.name == "BRG-40 strict v2"
    assert obj.tenant_id == tenant_a.pk
    assert obj.scope_key == "item"


def test_receipt_tolerancepolicy_form_overlapping_rules_are_legal_by_design(
        tenant_a, receipt_policy_catchall_a):
    """No unique_together on this model - a workspace-wide band PLUS a vendor exception is the
    normal configuration, and the resolver decides which one wins."""
    form = ReceiptTolerancePolicyForm(
        _receipt_policy_post(name=receipt_policy_catchall_a.name), tenant=tenant_a)
    assert form.is_valid(), form.errors
    form.save()
    assert ReceiptTolerancePolicy.objects.filter(
        tenant=tenant_a, name=receipt_policy_catchall_a.name).count() == 2


# =====================================================================================
# 3. ReceiptDiscrepancyForm
# =====================================================================================

def test_receipt_discrepancy_form_requires_receipt_kind_and_description(tenant_a):
    form = ReceiptDiscrepancyForm(_receipt_discrepancy_post(kind="", description=""),
                                  tenant=tenant_a)
    assert not form.is_valid()
    for name in ("goods_receipt", "kind", "description"):
        assert name in form.errors, name


def test_receipt_discrepancy_form_item_description_is_optional(tenant_a):
    assert ReceiptDiscrepancyForm(tenant=tenant_a).fields["item_description"].required is False


def test_receipt_discrepancy_form_valid_create_leaves_number_and_status_alone(
        tenant_a, receipt_grn_a):
    form = ReceiptDiscrepancyForm(_receipt_discrepancy_post(receipt_grn_a), tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.tenant_id == tenant_a.pk
    assert not obj.number
    assert obj.status == "open"
    assert obj.vendor_notified_on is None and obj.resolved_at is None
    assert obj.resolved_by_id is None and obj.resolution_notes == ""
    obj.save()
    assert obj.number.startswith("RDS-")
    assert obj.created_by_id is None            # the view stamps it, never the form


def test_receipt_discrepancy_form_quantity_kinds_demand_a_figure(tenant_a, receipt_grn_a):
    for kind in ReceiptDiscrepancy.QUANTITY_KINDS:
        form = ReceiptDiscrepancyForm(
            _receipt_discrepancy_post(receipt_grn_a, kind=kind, quantity_affected="0"),
            tenant=tenant_a)
        assert not form.is_valid(), kind
        assert "quantity_affected" in form.errors, kind
        assert "Give the quantity affected" in " ".join(form.errors["quantity_affected"])


def test_receipt_discrepancy_form_non_quantity_kind_accepts_zero(tenant_a, receipt_grn_a):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a, kind="documentation", severity="minor",
                                  quantity_affected="0",
                                  description="No packing list with the delivery."),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().quantity_affected == Decimal("0")


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "abc", "-4", "1" * 32])
def test_receipt_discrepancy_form_rejects_junk_quantities_without_500(
        tenant_a, receipt_grn_a, junk):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a, quantity_affected=junk), tenant=tenant_a)
    assert not form.is_valid()
    assert "quantity_affected" in form.errors


def test_receipt_discrepancy_form_mirrors_the_receipt_lines_item_text_on_save(
        tenant_a, receipt_grn_a, receipt_grn_line_a):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a, kind="damaged", quantity_affected="1",
                                  goods_receipt_line=str(receipt_grn_line_a.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.item_description == "Bearing housing 40mm"
    assert obj.sku_hint == "BRG-40"


def test_receipt_discrepancy_form_receipt_queryset_excludes_cancelled_and_other_tenants(
        tenant_a, receipt_grn_a, receipt_grn_cancelled_a, receipt_grn_b):
    offered = set(ReceiptDiscrepancyForm(tenant=tenant_a).fields["goods_receipt"].queryset)
    assert receipt_grn_a in offered
    assert receipt_grn_cancelled_a not in offered
    assert receipt_grn_b not in offered


def test_receipt_discrepancy_form_line_queryset_is_scoped_through_its_header(
        tenant_a, receipt_grn_line_a, receipt_grn_line2_a, receipt_grn_line_b):
    """scm.GoodsReceiptLine has NO tenant column, so TenantModelForm cannot auto-scope it -
    an unnarrowed field would both display and ACCEPT another workspace's line."""
    offered = set(ReceiptDiscrepancyForm(tenant=tenant_a).fields["goods_receipt_line"].queryset)
    assert {receipt_grn_line_a, receipt_grn_line2_a} <= offered
    assert receipt_grn_line_b not in offered


def test_receipt_discrepancy_form_related_registers_are_tenant_scoped(
        tenant_a, receipt_nonconformance_a, receipt_nonconformance_b,
        receipt_quarantine_a, receipt_quarantine_b, receipt_rtv_draft_a, receipt_rtv_b):
    form = ReceiptDiscrepancyForm(tenant=tenant_a)
    assert receipt_nonconformance_a in set(form.fields["nonconformance"].queryset)
    assert receipt_nonconformance_b not in set(form.fields["nonconformance"].queryset)
    assert receipt_quarantine_a in set(form.fields["quarantine_order"].queryset)
    assert receipt_quarantine_b not in set(form.fields["quarantine_order"].queryset)
    assert receipt_rtv_draft_a in set(form.fields["return_to_vendor"].queryset)
    assert receipt_rtv_b not in set(form.fields["return_to_vendor"].queryset)


def test_receipt_discrepancy_form_tenantless_offers_no_rows_at_all(
        receipt_grn_a, receipt_grn_line_a, receipt_nonconformance_a, receipt_quarantine_a,
        receipt_rtv_draft_a):
    form = ReceiptDiscrepancyForm(tenant=None)
    for name in ("goods_receipt", "goods_receipt_line", "nonconformance",
                 "quarantine_order", "return_to_vendor"):
        assert not form.fields[name].queryset.exists(), name


def test_receipt_discrepancy_form_rejects_foreign_receipt_both_layers(tenant_a,
                                                                     receipt_grn_b):
    data = _receipt_discrepancy_post(receipt_grn_b)

    scoped = ReceiptDiscrepancyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "goods_receipt" in scoped.errors

    loose = _receipt_widen(ReceiptDiscrepancyForm(data, tenant=tenant_a),
                           "goods_receipt", GoodsReceiptNote.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["goods_receipt"]


def test_receipt_discrepancy_form_rejects_foreign_receipt_line_both_layers(
        tenant_a, receipt_grn_a, receipt_grn_line_b):
    data = _receipt_discrepancy_post(receipt_grn_a,
                                     goods_receipt_line=str(receipt_grn_line_b.pk))

    scoped = ReceiptDiscrepancyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "goods_receipt_line" in scoped.errors

    loose = _receipt_widen(ReceiptDiscrepancyForm(data, tenant=tenant_a),
                           "goods_receipt_line", GoodsReceiptLine.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["goods_receipt_line"]


def test_receipt_discrepancy_form_rejects_a_line_from_another_receipt(
        tenant_a, receipt_grn_a, receipt_grn_early_a):
    other_line = receipt_grn_early_a.lines.first()
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a, goods_receipt_line=str(other_line.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That line belongs to a different receipt." in form.errors["goods_receipt_line"]


def test_receipt_discrepancy_form_rejects_a_cancelled_receipts_line(
        tenant_a, receipt_grn_a, receipt_grn_cancelled_a):
    """The cancelled receipt itself is not offerable, so stapling one of its lines onto a live
    receipt is refused by the model's own header check."""
    cancelled_line = receipt_grn_cancelled_a.lines.first()
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a, goods_receipt_line=str(cancelled_line.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That line belongs to a different receipt." in form.errors["goods_receipt_line"]


def test_receipt_discrepancy_form_rejects_foreign_nonconformance_both_layers(
        tenant_a, receipt_grn_a, receipt_nonconformance_b):
    data = _receipt_discrepancy_post(receipt_grn_a,
                                     nonconformance=str(receipt_nonconformance_b.pk))

    scoped = ReceiptDiscrepancyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "nonconformance" in scoped.errors

    loose = _receipt_widen(ReceiptDiscrepancyForm(data, tenant=tenant_a),
                           "nonconformance", NonConformance.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["nonconformance"]


def test_receipt_discrepancy_form_rejects_foreign_quarantine_order_both_layers(
        tenant_a, receipt_grn_a, receipt_quarantine_b):
    data = _receipt_discrepancy_post(receipt_grn_a,
                                     quarantine_order=str(receipt_quarantine_b.pk))

    scoped = ReceiptDiscrepancyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "quarantine_order" in scoped.errors

    loose = _receipt_widen(ReceiptDiscrepancyForm(data, tenant=tenant_a),
                           "quarantine_order", QuarantineOrder.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["quarantine_order"]


def test_receipt_discrepancy_form_rejects_foreign_return_to_vendor_both_layers(
        tenant_a, receipt_grn_a, receipt_rtv_b):
    data = _receipt_discrepancy_post(receipt_grn_a, return_to_vendor=str(receipt_rtv_b.pk))

    scoped = ReceiptDiscrepancyForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "return_to_vendor" in scoped.errors

    loose = _receipt_widen(ReceiptDiscrepancyForm(data, tenant=tenant_a),
                           "return_to_vendor", ReturnToVendor.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["return_to_vendor"]


def test_receipt_discrepancy_edit_form_drops_goods_receipt_entirely(
        tenant_a, receipt_discrepancy_open_a):
    create_form = ReceiptDiscrepancyForm(tenant=tenant_a)
    assert "goods_receipt" in create_form.fields

    edit_form = ReceiptDiscrepancyForm(instance=receipt_discrepancy_open_a, tenant=tenant_a)
    # Re-pointing a saved finding would orphan its goods_receipt_line - the field is not
    # hidden, it is gone, so a crafted POST has nothing to bind to.
    assert "goods_receipt" not in edit_form.fields


def test_receipt_discrepancy_edit_form_ignores_a_posted_goods_receipt(
        tenant_a, receipt_discrepancy_header_a, receipt_grn_early_a):
    original = receipt_discrepancy_header_a.goods_receipt_id
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_early_a, kind="documentation",
                                  quantity_affected="0",
                                  description="Still no packing list."),
        instance=receipt_discrepancy_header_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.goods_receipt_id == original          # the posted pk was never bound


def test_receipt_discrepancy_edit_form_narrows_lines_to_its_own_receipt(
        tenant_a, receipt_discrepancy_open_a, receipt_grn_line_a, receipt_grn_line2_a,
        receipt_grn_early_a):
    other_line = receipt_grn_early_a.lines.first()
    offered = set(ReceiptDiscrepancyForm(
        instance=receipt_discrepancy_open_a, tenant=tenant_a
    ).fields["goods_receipt_line"].queryset)
    assert offered == {receipt_grn_line_a, receipt_grn_line2_a}
    assert other_line not in offered


def test_receipt_discrepancy_edit_form_rekeys_a_dropped_field_error_instead_of_500ing(
        tenant_a, receipt_grn_b):
    """A row whose goods_receipt points at another workspace can only be reached by a bad
    write, but the model still errors on a field the EDIT form has popped. Without the
    add_error override that is a ValueError - i.e. a 500 - not a rendered message."""
    broken = ReceiptDiscrepancy.objects.create(
        tenant=tenant_a, goods_receipt=receipt_grn_b, kind="documentation",
        quantity_affected=Decimal("0"), description="Cross-wired row.")
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(kind="documentation", quantity_affected="0",
                                  description="Cross-wired row."),
        instance=broken, tenant=tenant_a)
    assert not form.is_valid()
    assert "That receipt belongs to another workspace." in form.errors[NON_FIELD_ERRORS]


def test_receipt_discrepancy_form_add_error_remaps_a_dropped_field_key(
        tenant_a, receipt_discrepancy_open_a):
    form = ReceiptDiscrepancyForm(instance=receipt_discrepancy_open_a, tenant=tenant_a)
    form.cleaned_data = {}
    form.add_error("goods_receipt", "Dropped field message.")
    assert "Dropped field message." in form.errors[NON_FIELD_ERRORS]


def test_receipt_discrepancy_form_add_error_keeps_live_field_keys_intact(
        tenant_a, receipt_discrepancy_open_a):
    form = ReceiptDiscrepancyForm(instance=receipt_discrepancy_open_a, tenant=tenant_a)
    form.cleaned_data = {}
    form.add_error(None, ValidationError({"goods_receipt": "Gone.", "kind": "Stays."}))
    assert "Gone." in form.errors[NON_FIELD_ERRORS]
    assert "Stays." in form.errors["kind"]


def test_receipt_discrepancy_form_rejects_a_disallowed_evidence_extension(
        tenant_a, receipt_grn_a):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a), tenant=tenant_a,
        files={"evidence": _receipt_upload("payload.exe", content=b"MZ")})
    assert not form.is_valid()
    assert "File type '.exe' is not allowed." in form.errors["evidence"]


def test_receipt_discrepancy_form_rejects_an_oversized_evidence_upload(
        tenant_a, receipt_grn_a):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a), tenant=tenant_a,
        files={"evidence": _receipt_upload("huge.pdf", size=21 * 1024 * 1024)})
    assert not form.is_valid()
    assert "File exceeds the 20 MB limit." in form.errors["evidence"]


def test_receipt_discrepancy_form_accepts_an_allowed_evidence_extension(
        tenant_a, receipt_grn_a):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a), tenant=tenant_a,
        files={"evidence": _receipt_upload("dock-photo.jpg", content=b"\xff\xd8\xff")})
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)               # never write the file to MEDIA_ROOT here
    assert obj.evidence.name.endswith(".jpg")


def test_receipt_discrepancy_form_rejects_an_unknown_kind_or_severity(tenant_a,
                                                                     receipt_grn_a):
    form = ReceiptDiscrepancyForm(
        _receipt_discrepancy_post(receipt_grn_a, kind="alien", severity="apocalyptic"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "kind" in form.errors and "severity" in form.errors


def test_receipt_discrepancy_form_expiry_date_uses_the_shared_iso_widget(tenant_a):
    """TenantModelForm owns the date widgets - never re-declared per form (L22)."""
    field = ReceiptDiscrepancyForm(tenant=tenant_a).fields["expiry_date"]
    assert field.input_formats == ["%Y-%m-%d"]
    # Django's Input.__init__ pops "type" out of attrs onto input_type, so that is where the
    # native date picker actually lives.
    assert field.widget.input_type == "date"
    assert field.widget.attrs.get("class") == "form-input"


# =====================================================================================
# 4. The discrepancy verb dialogs
# =====================================================================================

def test_receipt_notify_form_accepts_an_empty_post():
    """The common case is a buyer clicking the button the moment they send the email."""
    form = DiscrepancyNotifyForm({})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["vendor_reference"] == ""
    assert form.cleaned_data["vendor_notified_on"] is None


def test_receipt_notify_form_parses_an_iso_date():
    form = DiscrepancyNotifyForm({"vendor_notified_on": _receipt_iso(-1),
                                  "vendor_reference": "SUP-CASE-11"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["vendor_notified_on"] == _receipt_day(-1)
    assert form.cleaned_data["vendor_reference"] == "SUP-CASE-11"


def test_receipt_notify_form_rejects_a_junk_date():
    form = DiscrepancyNotifyForm({"vendor_notified_on": "not-a-date"})
    assert not form.is_valid()
    assert "vendor_notified_on" in form.errors


def test_receipt_notify_form_caps_the_supplier_reference_length():
    form = DiscrepancyNotifyForm({"vendor_reference": "X" * 65})
    assert not form.is_valid()
    assert "vendor_reference" in form.errors


def test_receipt_resolve_form_requires_both_a_remedy_and_notes():
    form = DiscrepancyResolveForm({})
    assert not form.is_valid()
    assert set(form.errors) == {"remedy", "resolution_notes"}


def test_receipt_resolve_form_rejects_a_remedy_outside_the_vocabulary():
    form = DiscrepancyResolveForm({"remedy": "haggle", "resolution_notes": "Agreed."})
    assert not form.is_valid()
    assert "remedy" in form.errors


def test_receipt_resolve_form_offers_exactly_the_model_remedies():
    offered = [value for value, _ in DiscrepancyResolveForm().fields["remedy"].choices]
    assert offered == [value for value, _ in ReceiptDiscrepancy.REMEDY_CHOICES]


def test_receipt_resolve_form_accepts_a_complete_closure():
    form = DiscrepancyResolveForm({"remedy": "credit",
                                   "resolution_notes": "Credit note agreed."})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["remedy"] == "credit"


def test_receipt_resolve_form_caps_the_notes_at_two_thousand_characters():
    form = DiscrepancyResolveForm({"remedy": "credit", "resolution_notes": "x" * 2001})
    assert not form.is_valid()
    assert "resolution_notes" in form.errors


def test_receipt_cancel_form_accepts_an_empty_post():
    """A mis-count needs no essay - withdrawing a finding must not demand one."""
    form = DiscrepancyCancelForm({})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["resolution_notes"] == ""
    assert form.fields["resolution_notes"].required is False


def test_receipt_cancel_form_caps_the_reason_at_two_thousand_characters():
    form = DiscrepancyCancelForm({"resolution_notes": "y" * 2001})
    assert not form.is_valid()


# =====================================================================================
# 5. ReturnToVendorForm
# =====================================================================================

def test_receipt_rtv_form_requires_a_vendor_and_a_reason(tenant_a):
    form = ReturnToVendorForm(_receipt_rtv_post(reason=""), tenant=tenant_a)
    assert not form.is_valid()
    assert "vendor" in form.errors and "reason" in form.errors


def test_receipt_rtv_form_valid_create_leaves_number_status_and_stamps_alone(
        tenant_a, receipt_vendor_a):
    form = ReturnToVendorForm(_receipt_rtv_post(receipt_vendor_a), tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.tenant_id == tenant_a.pk
    assert not obj.number
    assert obj.status == "draft"
    assert obj.shipped_on is None and obj.authorized_at is None
    assert obj.authorized_by_id is None and obj.closed_at is None
    assert obj.cancelled_at is None and obj.cancellation_reason == ""
    obj.save()
    assert obj.number.startswith("RTV-")
    assert obj.created_by_id is None            # the view stamps it, never the form


def test_receipt_rtv_form_reason_other_demands_a_note(tenant_a, receipt_vendor_a):
    form = ReturnToVendorForm(_receipt_rtv_post(receipt_vendor_a, reason="other"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert "Say what the reason is when choosing 'Other'." in form.errors["reason_note"]


def test_receipt_rtv_form_reason_other_passes_with_a_note(tenant_a, receipt_vendor_a):
    form = ReturnToVendorForm(
        _receipt_rtv_post(receipt_vendor_a, reason="other",
                          reason_note="Supplier consolidation."),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().reason_note == "Supplier consolidation."


def test_receipt_rtv_form_vendor_queryset_is_supplier_role_and_tenant_scoped(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a, receipt_vendor_b):
    roleless = _receipt_roleless_party(tenant_a, "Nameless Trading")
    offered = set(ReturnToVendorForm(tenant=tenant_a).fields["vendor"].queryset)
    assert {receipt_vendor_a, receipt_vendor_other_a} <= offered
    assert receipt_vendor_b not in offered
    assert roleless not in offered


def test_receipt_rtv_form_origin_querysets_are_tenant_scoped(
        tenant_a, receipt_po_a, receipt_po_b, receipt_grn_a, receipt_grn_b,
        receipt_discrepancy_open_a, receipt_discrepancy_b):
    form = ReturnToVendorForm(tenant=tenant_a)
    assert receipt_po_a in set(form.fields["purchase_order"].queryset)
    assert receipt_po_b not in set(form.fields["purchase_order"].queryset)
    assert receipt_grn_a in set(form.fields["goods_receipt"].queryset)
    assert receipt_grn_b not in set(form.fields["goods_receipt"].queryset)
    assert receipt_discrepancy_open_a in set(form.fields["discrepancy"].queryset)
    assert receipt_discrepancy_b not in set(form.fields["discrepancy"].queryset)


def test_receipt_rtv_form_receipt_queryset_excludes_cancelled_receipts(
        tenant_a, receipt_grn_a, receipt_grn_cancelled_a):
    offered = set(ReturnToVendorForm(tenant=tenant_a).fields["goods_receipt"].queryset)
    assert receipt_grn_a in offered
    assert receipt_grn_cancelled_a not in offered


def test_receipt_rtv_edit_form_keeps_its_own_cancelled_receipt_offerable(
        tenant_a, receipt_vendor_a, receipt_po_a, receipt_grn_cancelled_a):
    """Dropping a stored value from the queryset would silently NULL the origin link on the
    next edit, because the field is null=True/blank=True."""
    rtv = ReturnToVendor.objects.create(tenant=tenant_a, vendor=receipt_vendor_a,
                                        reason="damaged", purchase_order=receipt_po_a,
                                        goods_receipt=receipt_grn_cancelled_a)
    offered = set(ReturnToVendorForm(instance=rtv,
                                     tenant=tenant_a).fields["goods_receipt"].queryset)
    assert receipt_grn_cancelled_a in offered


def test_receipt_rtv_form_tenantless_offers_no_rows_at_all(
        receipt_vendor_a, receipt_po_a, receipt_grn_a, receipt_discrepancy_open_a):
    form = ReturnToVendorForm(tenant=None)
    for name in ("vendor", "purchase_order", "goods_receipt", "discrepancy"):
        assert not form.fields[name].queryset.exists(), name


def test_receipt_rtv_form_rejects_foreign_vendor_both_layers(tenant_a, receipt_vendor_b):
    data = _receipt_rtv_post(receipt_vendor_b)

    scoped = ReturnToVendorForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "vendor" in scoped.errors

    loose = _receipt_widen(ReturnToVendorForm(data, tenant=tenant_a),
                           "vendor", Party.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["vendor"]


def test_receipt_rtv_form_rejects_foreign_purchase_order_both_layers(
        tenant_a, receipt_vendor_a, receipt_po_b):
    data = _receipt_rtv_post(receipt_vendor_a, purchase_order=str(receipt_po_b.pk))

    scoped = ReturnToVendorForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "purchase_order" in scoped.errors

    loose = _receipt_widen(ReturnToVendorForm(data, tenant=tenant_a),
                           "purchase_order", PurchaseOrder.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["purchase_order"]


def test_receipt_rtv_form_rejects_foreign_goods_receipt_both_layers(
        tenant_a, receipt_vendor_a, receipt_grn_b):
    data = _receipt_rtv_post(receipt_vendor_a, goods_receipt=str(receipt_grn_b.pk))

    scoped = ReturnToVendorForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "goods_receipt" in scoped.errors

    loose = _receipt_widen(ReturnToVendorForm(data, tenant=tenant_a),
                           "goods_receipt", GoodsReceiptNote.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["goods_receipt"]


def test_receipt_rtv_form_rejects_foreign_discrepancy_both_layers(
        tenant_a, receipt_vendor_a, receipt_discrepancy_b):
    data = _receipt_rtv_post(receipt_vendor_a, discrepancy=str(receipt_discrepancy_b.pk))

    scoped = ReturnToVendorForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "discrepancy" in scoped.errors

    loose = _receipt_widen(ReturnToVendorForm(data, tenant=tenant_a),
                           "discrepancy", ReceiptDiscrepancy.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.errors["discrepancy"]


def test_receipt_rtv_form_rejects_an_order_placed_with_a_different_supplier(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a):
    """Both rows live in this workspace - tenancy is not the only counterparty rule."""
    other_order = _receipt_extra_po(tenant_a, receipt_vendor_other_a)
    form = ReturnToVendorForm(
        _receipt_rtv_post(receipt_vendor_a, purchase_order=str(other_order.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That order was placed with a different supplier." in form.errors["purchase_order"]


def test_receipt_rtv_form_rejects_a_receipt_against_a_different_order(
        tenant_a, receipt_vendor_a, receipt_grn_a):
    other_order = _receipt_extra_po(tenant_a, receipt_vendor_a)
    form = ReturnToVendorForm(
        _receipt_rtv_post(receipt_vendor_a, purchase_order=str(other_order.pk),
                          goods_receipt=str(receipt_grn_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "That receipt is against a different purchase order." in \
        form.errors["goods_receipt"]


def test_receipt_rtv_form_accepts_a_matched_order_and_receipt(
        tenant_a, receipt_vendor_a, receipt_po_a, receipt_grn_a):
    form = ReturnToVendorForm(
        _receipt_rtv_post(receipt_vendor_a, purchase_order=str(receipt_po_a.pk),
                          goods_receipt=str(receipt_grn_a.pk),
                          expected_return_date=_receipt_iso(10)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.purchase_order_id == receipt_po_a.pk
    assert obj.goods_receipt_id == receipt_grn_a.pk
    assert obj.expected_return_date == _receipt_day(10)


def test_receipt_rtv_form_date_widget_comes_from_tenantmodelform(tenant_a):
    field = ReturnToVendorForm(tenant=tenant_a).fields["expected_return_date"]
    assert field.input_formats == ["%Y-%m-%d"]
    assert field.widget.input_type == "date"
    assert field.widget.attrs.get("class") == "form-input"


def test_receipt_rtv_form_rejects_an_unknown_reason_or_remedy(tenant_a, receipt_vendor_a):
    form = ReturnToVendorForm(
        _receipt_rtv_post(receipt_vendor_a, reason="vibes", remedy="barter"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "reason" in form.errors and "remedy" in form.errors


def test_receipt_rtv_form_edit_keeps_the_status_and_stamps_untouched(
        tenant_a, receipt_rtv_draft_a):
    form = ReturnToVendorForm(
        _receipt_rtv_post(receipt_rtv_draft_a.vendor, supplier_rma_number="RMA-77-B",
                          purchase_order=str(receipt_rtv_draft_a.purchase_order_id),
                          goods_receipt=str(receipt_rtv_draft_a.goods_receipt_id)),
        instance=receipt_rtv_draft_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.supplier_rma_number == "RMA-77-B"
    assert obj.status == "draft"
    assert obj.number.startswith("RTV-")


# =====================================================================================
# 6. ReturnToVendorLineForm / ReturnToVendorLineFormSet
# =====================================================================================

def test_receipt_rtvline_form_is_a_plain_modelform_with_a_blank_quantity_initial():
    assert issubclass(ReturnToVendorLineForm, forms.ModelForm)
    # ReturnToVendorLine carries no tenant of its own, so there is nothing for
    # TenantModelForm to narrow - both FK querysets are scoped through their headers instead.
    assert not issubclass(ReturnToVendorLineForm, TenantModelForm)
    form = ReturnToVendorLineForm()          # no tenant kwarg
    assert form.fields["item_description"].required is False
    assert form.fields["quantity_returned"].required is True
    # The model default of 1 is cleared so a blank trailing extra row stays blank.
    assert form.fields["quantity_returned"].initial is None


def test_receipt_rtvline_form_tenantless_offers_no_line_rows(receipt_grn_line_a,
                                                             receipt_po_line_a):
    form = ReturnToVendorLineForm()
    assert not form.fields["goods_receipt_line"].queryset.exists()
    assert not form.fields["po_line"].queryset.exists()


def test_receipt_rtvlineformset_factory_contract():
    assert ReturnToVendorLineFormSet.extra == 2
    assert ReturnToVendorLineFormSet.can_delete is True
    assert ReturnToVendorLineFormSet.max_num == 50
    assert ReturnToVendorLineFormSet.validate_max is True
    assert issubclass(ReturnToVendorLineFormSet.form, ReturnToVendorLineForm)


def test_receipt_rtvlineformset_narrows_receipt_lines_to_the_headers_receipt(
        receipt_rtv_draft_a, receipt_grn_line_a, receipt_grn_line2_a, receipt_grn_early_a,
        receipt_grn_line_b):
    other_line = receipt_grn_early_a.lines.first()
    formset = ReturnToVendorLineFormSet(instance=receipt_rtv_draft_a, prefix="lines")
    offered = set(formset.forms[0].fields["goods_receipt_line"].queryset)
    assert offered == {receipt_grn_line_a, receipt_grn_line2_a}
    assert other_line not in offered
    assert receipt_grn_line_b not in offered


def test_receipt_rtvlineformset_narrows_po_lines_to_the_headers_order(
        receipt_rtv_draft_a, receipt_po_line_a, receipt_po_line2_a, receipt_po_line_b,
        tenant_a, receipt_vendor_a):
    other_line = _receipt_extra_po(tenant_a, receipt_vendor_a).lines.first()
    formset = ReturnToVendorLineFormSet(instance=receipt_rtv_draft_a, prefix="lines")
    offered = set(formset.forms[0].fields["po_line"].queryset)
    assert offered == {receipt_po_line_a, receipt_po_line2_a}
    assert other_line not in offered
    assert receipt_po_line_b not in offered


def test_receipt_rtvlineformset_falls_back_to_the_suppliers_lines_when_no_order_is_named(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a, receipt_po_line_a):
    """No order pinned yet, but the supplier is - another supplier's ordered lines would price
    this return off the wrong unit price."""
    rtv = ReturnToVendor.objects.create(tenant=tenant_a, vendor=receipt_vendor_a,
                                        reason="damaged")
    rival_line = _receipt_extra_po(tenant_a, receipt_vendor_other_a).lines.first()
    formset = ReturnToVendorLineFormSet(instance=rtv, prefix="lines")
    offered = set(formset.forms[0].fields["po_line"].queryset)
    assert receipt_po_line_a in offered
    assert rival_line not in offered


def test_receipt_rtvlineformset_saves_a_row_and_copies_the_blank_item_text(
        receipt_rtv_draft_a, receipt_po_line2_a):
    data = _receipt_lines_post([
        {"po_line": str(receipt_po_line2_a.pk), "quantity_returned": "2",
         "item_description": "", "sku_hint": "", "uom_hint": ""},
    ])
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    rows = formset.save()
    assert len(rows) == 1
    assert rows[0].item_description == "Drive belt 1200mm"   # copied in the model's save()
    assert rows[0].sku_hint == "BLT-1200"
    assert rows[0].uom_hint == "EA"
    assert rows[0].quantity_returned == Decimal("2")
    assert rows[0].expected_credit == Decimal("120.00")      # DERIVED: 2 x 60.00


def test_receipt_rtvlineformset_leaves_a_blank_extra_row_alone(receipt_rtv_draft_a):
    """The cleared quantity initial is what stops an untouched trailing row being validated."""
    data = _receipt_lines_post([{}, {}])
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    assert formset.save() == []


def test_receipt_rtvlineformset_rejects_a_zero_quantity(receipt_rtv_draft_a,
                                                        receipt_po_line_a):
    data = _receipt_lines_post([
        {"po_line": str(receipt_po_line_a.pk), "quantity_returned": "0"},
    ])
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert not formset.is_valid()
    assert "quantity_returned" in formset.forms[0].errors


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "abc", "-3"])
def test_receipt_rtvlineformset_rejects_junk_quantities_without_500(
        receipt_rtv_draft_a, receipt_po_line_a, junk):
    data = _receipt_lines_post([
        {"po_line": str(receipt_po_line_a.pk), "quantity_returned": junk},
    ])
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert not formset.is_valid()
    assert "quantity_returned" in formset.forms[0].errors


def test_receipt_rtvlineformset_rejects_a_cross_tenant_receipt_line_both_layers(
        receipt_rtv_draft_a, receipt_grn_line_b):
    data = _receipt_lines_post([
        {"goods_receipt_line": str(receipt_grn_line_b.pk), "quantity_returned": "1"},
    ])

    scoped = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert not scoped.is_valid()
    assert "goods_receipt_line" in scoped.forms[0].errors        # layer 1

    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines"),
        "goods_receipt_line", GoodsReceiptLine.objects.all())
    assert not loose.is_valid()
    # Layer 2: this header names its OWN receipt, so ReturnToVendorLine.clean()'s header
    # check fires first (and strips the field from cleaned_data, which is why the formset's
    # workspace message never gets a turn here). Either way the row is refused, never saved.
    assert "That line belongs to a different goods receipt." in \
        loose.forms[0].errors["goods_receipt_line"]
    assert receipt_rtv_draft_a.lines.count() == 0


def test_receipt_rtvlineformset_rejects_a_cross_tenant_receipt_line_on_a_headerless_return(
        tenant_a, receipt_vendor_a, receipt_grn_line_b):
    """With no receipt pinned on the header the model's own header check cannot fire, so the
    FORMSET's tenancy re-check is the only thing between a crafted pk and a saved row - and
    it is what names the workspace."""
    rtv = ReturnToVendor.objects.create(tenant=tenant_a, vendor=receipt_vendor_a,
                                        reason="damaged")
    data = _receipt_lines_post([
        {"goods_receipt_line": str(receipt_grn_line_b.pk), "quantity_returned": "1"},
    ])

    scoped = ReturnToVendorLineFormSet(data, instance=rtv, prefix="lines")
    assert not scoped.is_valid()
    assert "goods_receipt_line" in scoped.forms[0].errors        # layer 1

    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=rtv, prefix="lines"),
        "goods_receipt_line", GoodsReceiptLine.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.forms[0].errors["goods_receipt_line"]   # layer 2
    assert rtv.lines.count() == 0


def test_receipt_rtvlineformset_rejects_a_line_from_another_receipt(
        receipt_rtv_draft_a, receipt_grn_early_a):
    other_line = receipt_grn_early_a.lines.first()
    data = _receipt_lines_post([
        {"goods_receipt_line": str(other_line.pk), "quantity_returned": "1"},
    ])
    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines"),
        "goods_receipt_line", GoodsReceiptLine.objects.all())
    assert not loose.is_valid()
    assert "That line belongs to a different goods receipt." in \
        loose.forms[0].errors["goods_receipt_line"]


def test_receipt_rtvlineformset_rejects_a_receipt_line_from_another_supplier(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a):
    """No header receipt to pin it to, so the SUPPLIER is what has to match - a foreign
    receipt line quotes the credit off the wrong supplier's price."""
    rtv = ReturnToVendor.objects.create(tenant=tenant_a, vendor=receipt_vendor_a,
                                        reason="damaged")
    rival_order = _receipt_extra_po(tenant_a, receipt_vendor_other_a)
    rival_grn = GoodsReceiptNote.objects.create(
        tenant=tenant_a, purchase_order=rival_order, receipt_date=timezone.localdate(),
        status="draft", delivery_note_ref="DN-RIVAL")
    rival_line = GoodsReceiptLine.objects.create(
        goods_receipt=rival_grn, po_line=rival_order.lines.first(),
        quantity_received=Decimal("3"))

    data = _receipt_lines_post([
        {"goods_receipt_line": str(rival_line.pk), "quantity_returned": "1"},
    ])
    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=rtv, prefix="lines"),
        "goods_receipt_line", GoodsReceiptLine.objects.all())
    assert not loose.is_valid()
    assert "That receipt is from a different supplier." in \
        loose.forms[0].errors["goods_receipt_line"]


def test_receipt_rtvlineformset_rejects_a_cross_tenant_po_line_both_layers(
        receipt_rtv_draft_a, receipt_po_line_b):
    data = _receipt_lines_post([
        {"po_line": str(receipt_po_line_b.pk), "quantity_returned": "1"},
    ])

    scoped = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert not scoped.is_valid()
    assert "po_line" in scoped.forms[0].errors

    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines"),
        "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert _RECEIPT_FOREIGN in loose.forms[0].errors["po_line"]


def test_receipt_rtvlineformset_rejects_a_po_line_from_another_order(
        receipt_rtv_draft_a, tenant_a, receipt_vendor_a):
    other_line = _receipt_extra_po(tenant_a, receipt_vendor_a).lines.first()
    data = _receipt_lines_post([
        {"po_line": str(other_line.pk), "quantity_returned": "1"},
    ])
    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines"),
        "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert "That line belongs to a different purchase order." in \
        loose.forms[0].errors["po_line"]


def test_receipt_rtvlineformset_rejects_a_po_line_from_another_supplier(
        tenant_a, receipt_vendor_a, receipt_vendor_other_a):
    rtv = ReturnToVendor.objects.create(tenant=tenant_a, vendor=receipt_vendor_a,
                                        reason="damaged")
    rival_line = _receipt_extra_po(tenant_a, receipt_vendor_other_a).lines.first()
    data = _receipt_lines_post([
        {"po_line": str(rival_line.pk), "quantity_returned": "1"},
    ])
    loose = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=rtv, prefix="lines"),
        "po_line", PurchaseOrderLine.objects.all())
    assert not loose.is_valid()
    assert "That order was placed with a different supplier." in \
        loose.forms[0].errors["po_line"]


def test_receipt_rtvlineformset_skips_a_row_marked_for_deletion(receipt_rtv_draft_a,
                                                                receipt_po_line_b):
    """A row being dropped declares nothing - it neither collides nor blocks."""
    data = _receipt_lines_post([
        {"po_line": str(receipt_po_line_b.pk), "quantity_returned": "1", "DELETE": "on"},
    ])
    formset = _receipt_widen_rows(
        ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines"),
        "po_line", PurchaseOrderLine.objects.all())
    assert formset.is_valid(), formset.errors


def test_receipt_rtvlineformset_deletes_an_existing_row(
        receipt_rtv_draft_a, receipt_rtv_line_a, receipt_po_line_a):
    data = _receipt_lines_post([
        {"id": str(receipt_rtv_line_a.pk), "po_line": str(receipt_po_line_a.pk),
         "quantity_returned": "3", "DELETE": "on"},
    ], initial=1)
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    formset.save()
    assert receipt_rtv_draft_a.lines.count() == 0


def test_receipt_rtvlineformset_refuses_more_than_fifty_rows(receipt_rtv_draft_a,
                                                             receipt_po_line_a):
    rows = [{"po_line": str(receipt_po_line_a.pk), "quantity_returned": "1"}
            for _ in range(51)]
    formset = ReturnToVendorLineFormSet(_receipt_lines_post(rows),
                                        instance=receipt_rtv_draft_a, prefix="lines")
    assert not formset.is_valid()
    assert any("50" in message for message in formset.non_form_errors())
    assert receipt_rtv_draft_a.lines.count() == 0


def test_receipt_rtvlineformset_accepts_a_matched_receipt_and_order_line(
        receipt_rtv_draft_a, receipt_grn_line_a, receipt_po_line_a):
    data = _receipt_lines_post([
        {"goods_receipt_line": str(receipt_grn_line_a.pk),
         "po_line": str(receipt_po_line_a.pk), "quantity_returned": "3",
         "condition_note": "Crushed carton"},
    ])
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert formset.is_valid(), formset.errors
    row = formset.save()[0]
    assert row.unit_price == Decimal("25.00")
    assert row.expected_credit == Decimal("75.00")


def test_receipt_rtvlineformset_rejects_a_mismatched_receipt_and_order_line(
        receipt_rtv_draft_a, receipt_grn_line_a, receipt_po_line2_a):
    """Stapling an unrelated ordered line onto a received one is how a return gets priced off
    somebody else's unit price."""
    data = _receipt_lines_post([
        {"goods_receipt_line": str(receipt_grn_line_a.pk),
         "po_line": str(receipt_po_line2_a.pk), "quantity_returned": "1"},
    ])
    formset = ReturnToVendorLineFormSet(data, instance=receipt_rtv_draft_a, prefix="lines")
    assert not formset.is_valid()
    assert "That ordered line is not the one this receipt line received." in \
        formset.forms[0].errors["po_line"]


# =====================================================================================
# 7. The RTV verb dialogs
# =====================================================================================

def test_receipt_ship_form_accepts_an_empty_post():
    """Blank means UNCHANGED, never erase - the header may already carry what was arranged
    when the RMA was issued."""
    form = RtvShipForm({})
    assert form.is_valid(), form.errors
    assert form.cleaned_data == {"carrier_name": "", "tracking_number": "",
                                 "shipped_on": None}


def test_receipt_ship_form_parses_an_iso_shipped_on():
    form = RtvShipForm({"carrier_name": "DHL", "tracking_number": "TRK-RTV-1",
                        "shipped_on": _receipt_iso(-1)})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["shipped_on"] == _receipt_day(-1)


def test_receipt_ship_form_rejects_a_junk_date():
    form = RtvShipForm({"shipped_on": "yesterday"})
    assert not form.is_valid()
    assert "shipped_on" in form.errors


def test_receipt_ship_form_caps_carrier_and_tracking_lengths():
    form = RtvShipForm({"carrier_name": "C" * 121, "tracking_number": "T" * 65})
    assert not form.is_valid()
    assert set(form.errors) == {"carrier_name", "tracking_number"}


def test_receipt_close_form_accepts_an_empty_post():
    form = RtvCloseForm({})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["credit_note_ref"] == ""


def test_receipt_close_form_caps_the_credit_note_reference():
    form = RtvCloseForm({"credit_note_ref": "R" * 65})
    assert not form.is_valid()
    assert "credit_note_ref" in form.errors


def test_receipt_cancel_rtv_form_requires_a_reason():
    """A cancelled RTV with no reason reads as a data error rather than a decision."""
    form = RtvCancelForm({})
    assert not form.is_valid()
    assert "cancellation_reason" in form.errors
    assert RtvCancelForm().fields["cancellation_reason"].required is True


def test_receipt_cancel_rtv_form_accepts_a_reason():
    form = RtvCancelForm({"cancellation_reason": "Supplier collected on site."})
    assert form.is_valid(), form.errors


def test_receipt_cancel_rtv_form_caps_the_reason_at_two_thousand_characters():
    form = RtvCancelForm({"cancellation_reason": "z" * 2001})
    assert not form.is_valid()


# =====================================================================================
# 8. ReceivingConsoleBookForm
# =====================================================================================

def test_receipt_book_form_requires_a_receipt_date(tenant_a, receipt_asn_a,
                                                   receipt_asn_line_a):
    form = ReceivingConsoleBookForm(
        _receipt_book_post(receipt_date="", **{f"qty_{receipt_asn_line_a.pk}": "5"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "receipt_date" in form.errors


def test_receipt_book_form_declares_one_quantity_field_per_declared_line(
        tenant_a, receipt_asn_a, receipt_asn_line_a, receipt_po_line2_a):
    second = AsnLine.objects.create(asn=receipt_asn_a, po_line=receipt_po_line2_a,
                                    quantity_shipped=Decimal("2"), sku_hint="BLT-1200")
    form = ReceivingConsoleBookForm(asn=receipt_asn_a, tenant=tenant_a)
    assert form.line_field_names == [f"qty_{receipt_asn_line_a.pk}", f"qty_{second.pk}"]
    assert [line.pk for line in form.asn_lines] == [receipt_asn_line_a.pk, second.pk]
    for name in form.line_field_names:
        assert isinstance(form.fields[name], forms.DecimalField)
        assert form.fields[name].required is False
        assert form.fields[name].max_digits == 14
        assert form.fields[name].decimal_places == 4


def test_receipt_book_form_valid_post_reads_back_the_line_quantity(
        tenant_a, receipt_asn_a, receipt_asn_line_a, receipt_location_a):
    form = ReceivingConsoleBookForm(
        _receipt_book_post(location=str(receipt_location_a.pk), notes="Two pallets.",
                           **{f"qty_{receipt_asn_line_a.pk}": "5"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["receipt_date"] == _receipt_day()
    assert form.cleaned_data["location"] == receipt_location_a
    assert form.quantity_for(receipt_asn_line_a) == Decimal("5")


def test_receipt_book_form_refuses_a_zero_total(tenant_a, receipt_asn_a,
                                                receipt_asn_line_a):
    """A stray double-click on an empty row must never mint an empty draft GRN (and burn a
    GRN number)."""
    form = ReceivingConsoleBookForm(
        _receipt_book_post(**{f"qty_{receipt_asn_line_a.pk}": "0"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "Enter a received quantity on at least one line." in form.errors[NON_FIELD_ERRORS]


def test_receipt_book_form_refuses_an_entirely_empty_post(tenant_a, receipt_asn_a,
                                                          receipt_asn_line_a):
    form = ReceivingConsoleBookForm(_receipt_book_post(), asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "Enter a received quantity on at least one line." in form.errors[NON_FIELD_ERRORS]


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "abc"])
def test_receipt_book_form_rejects_junk_quantities_without_500(
        tenant_a, receipt_asn_a, receipt_asn_line_a, junk):
    name = f"qty_{receipt_asn_line_a.pk}"
    form = ReceivingConsoleBookForm(_receipt_book_post(**{name: junk}),
                                    asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert name in form.errors
    assert "Enter a number." in form.errors[name]


def test_receipt_book_form_rejects_a_negative_quantity(tenant_a, receipt_asn_a,
                                                       receipt_asn_line_a):
    name = f"qty_{receipt_asn_line_a.pk}"
    form = ReceivingConsoleBookForm(_receipt_book_post(**{name: "-5"}),
                                    asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "greater than or equal to 0" in " ".join(form.errors[name])


def test_receipt_book_form_rejects_an_over_max_digits_quantity(tenant_a, receipt_asn_a,
                                                               receipt_asn_line_a):
    name = f"qty_{receipt_asn_line_a.pk}"
    form = ReceivingConsoleBookForm(_receipt_book_post(**{name: "1" * 15}),
                                    asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "14 digits" in " ".join(form.errors[name])


def test_receipt_book_form_clean_recheck_catches_a_negative_that_slipped_the_field(
        tenant_a, receipt_asn_a, receipt_asn_line_a):
    """Layer 2: with the field's own min_value relaxed (a hand-posted inline form is the
    console's only writer), clean() is what has to refuse the sign."""
    name = f"qty_{receipt_asn_line_a.pk}"
    form = ReceivingConsoleBookForm(_receipt_book_post(**{name: "-5"}),
                                    asn=receipt_asn_a, tenant=tenant_a)
    form.fields[name].validators = []
    form.fields[name].min_value = None
    assert not form.is_valid()
    assert "Enter a quantity of zero or more." in form.errors[name]


def test_receipt_book_form_drops_a_crafted_quantity_for_another_asns_line(
        tenant_a, receipt_asn_a, receipt_asn_line_a, receipt_asn_no_reference_a):
    """A qty_<pk> for a line that is not on THIS asn is a field the form does not declare, so
    the quantity is dropped rather than applied."""
    foreign_line = receipt_asn_no_reference_a.lines.first()
    foreign_name = f"qty_{foreign_line.pk}"
    form = ReceivingConsoleBookForm(
        _receipt_book_post(**{f"qty_{receipt_asn_line_a.pk}": "5", foreign_name: "999"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert foreign_name not in form.fields
    assert form.is_valid(), form.errors
    assert foreign_name not in form.cleaned_data
    assert form.quantity_for(foreign_line) is None


def test_receipt_book_form_location_queryset_is_tenant_scoped_and_active_only(
        tenant_a, receipt_asn_a, receipt_location_a, receipt_location_b):
    closed = Location.objects.create(tenant=tenant_a, code="DOCK-Z", name="Closed dock",
                                     location_type="staging", is_active=False)
    offered = set(ReceivingConsoleBookForm(asn=receipt_asn_a,
                                           tenant=tenant_a).fields["location"].queryset)
    assert receipt_location_a in offered
    assert closed not in offered
    assert receipt_location_b not in offered


def test_receipt_book_form_rejects_a_cross_tenant_location(
        tenant_a, receipt_asn_a, receipt_asn_line_a, receipt_location_b):
    """For a ModelChoiceField the queryset IS the authorization boundary - a crafted POST
    cannot land this receipt in another tenant's warehouse."""
    form = ReceivingConsoleBookForm(
        _receipt_book_post(location=str(receipt_location_b.pk),
                           **{f"qty_{receipt_asn_line_a.pk}": "5"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "location" in form.errors
    assert GoodsReceiptNote.objects.filter(tenant=tenant_a,
                                           location=receipt_location_b).count() == 0


def test_receipt_book_form_location_is_optional(tenant_a, receipt_asn_a,
                                                receipt_asn_line_a):
    form = ReceivingConsoleBookForm(
        _receipt_book_post(**{f"qty_{receipt_asn_line_a.pk}": "5"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert form.fields["location"].required is False
    assert form.is_valid(), form.errors
    assert form.cleaned_data["location"] is None


def test_receipt_book_form_tenantless_offers_no_locations(receipt_asn_a,
                                                          receipt_location_a):
    form = ReceivingConsoleBookForm(asn=receipt_asn_a, tenant=None)
    assert not form.fields["location"].queryset.exists()


def test_receipt_book_form_without_an_asn_declares_no_line_fields(tenant_a):
    form = ReceivingConsoleBookForm(asn=None, tenant=tenant_a)
    assert form.asn_lines == []
    assert form.line_field_names == []
    assert set(form.fields) == {"receipt_date", "location", "notes"}


def test_receipt_book_form_caps_the_notes_at_two_thousand_characters(
        tenant_a, receipt_asn_a, receipt_asn_line_a):
    form = ReceivingConsoleBookForm(
        _receipt_book_post(notes="n" * 2001, **{f"qty_{receipt_asn_line_a.pk}": "5"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "notes" in form.errors


def test_receipt_book_form_rejects_a_junk_receipt_date(tenant_a, receipt_asn_a,
                                                       receipt_asn_line_a):
    form = ReceivingConsoleBookForm(
        _receipt_book_post(receipt_date="31/02/2026",
                           **{f"qty_{receipt_asn_line_a.pk}": "5"}),
        asn=receipt_asn_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "receipt_date" in form.errors
