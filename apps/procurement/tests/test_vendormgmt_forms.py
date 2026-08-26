"""Procurement 6.4 Vendor Management — form tests."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.procurement.forms import (
    SubmissionReviewForm,
    SuspensionDecisionForm,
    SuspensionLiftForm,
    VendorInvoiceSubmissionForm,
    VendorPortalAccessForm,
    VendorSuspensionForm,
)

pytestmark = pytest.mark.django_db


def _vpa_payload(**over):
    data = {"supplier": "", "portal_user": "", "is_active": "on", "note": ""}
    data.update(over)
    return data


def _sus_payload(**over):
    data = {"kind": "suspension", "reason_category": "delivery",
            "reason": "Late deliveries twice running.", "po_reference": "",
            "starts_on": timezone.localdate(), "ends_on": ""}
    data.update(over)
    return data


def _vis_payload(**over):
    data = {"purchase_order": "", "invoice_ref": "INV-2200",
            "invoice_date": timezone.localdate(), "amount": "120.00", "note": ""}
    data.update(over)
    return data


def _second_po_for_other_vendor(tenant):
    """A same-tenant PO belonging to a DIFFERENT vendor party."""
    from apps.core.models import Party
    from apps.scm.models import PurchaseOrder

    other = Party.objects.create(tenant=tenant, name="Other Vendor Co",
                                 kind="organization")
    return PurchaseOrder.objects.create(tenant=tenant, vendor=other,
                                        status="approved",
                                        order_date=timezone.localdate())


# ------------------------------------------------------------------ VendorPortalAccessForm

def test_vpa_form_valid_saves_without_invited_by(tenant_a, member_user, supplier_a):
    _, party = supplier_a
    form = VendorPortalAccessForm(
        _vpa_payload(supplier=party.pk, portal_user=member_user.pk,
                     note="AP clerk login"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk and obj.number.startswith("VPA")
    assert obj.supplier_id == party.pk and obj.portal_user_id == member_user.pk
    assert obj.is_active and obj.note == "AP clerk login"
    # invited_by is editable=False and NOT a form field — the view stamps it.
    assert obj.invited_by_id is None


def test_vpa_form_rejects_foreign_supplier(tenant_a, supplier_b):
    _, party_b = supplier_b
    form = VendorPortalAccessForm(_vpa_payload(supplier=party_b.pk), tenant=tenant_a)
    assert not form.is_valid() and "supplier" in form.errors


def test_vpa_form_rejects_foreign_portal_user(tenant_a, admin_b, supplier_a):
    _, party = supplier_a
    form = VendorPortalAccessForm(
        _vpa_payload(supplier=party.pk, portal_user=admin_b.pk), tenant=tenant_a)
    assert not form.is_valid() and "portal_user" in form.errors


# ------------------------------------------------------------------ VendorSuspensionForm

def test_suspension_form_valid_and_inverted_dates(tenant_a, supplier_a, po_a):
    _, party = supplier_a
    payload = _sus_payload(supplier=party.pk, po_reference=po_a.pk)
    form = VendorSuspensionForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk and obj.status == "requested"

    form = VendorSuspensionForm({
        **payload,
        "ends_on": timezone.localdate() - timedelta(days=1)},
        tenant=tenant_a)
    # ModelForm._post_clean runs instance.clean(), so the model's date rule surfaces here.
    assert not form.is_valid() and "ends_on" in form.errors


def test_suspension_form_rejects_foreign_supplier_and_po(tenant_a, tenant_b,
                                                         supplier_a, supplier_b):
    _, party_b = supplier_b
    form = VendorSuspensionForm(_sus_payload(supplier=party_b.pk), tenant=tenant_a)
    assert not form.is_valid() and "supplier" in form.errors

    from apps.scm.models import PurchaseOrder
    po_b = PurchaseOrder.objects.create(
        tenant=tenant_b, vendor=party_b, status="approved",
        order_date=timezone.localdate())
    _, party_a = supplier_a
    form = VendorSuspensionForm(
        _sus_payload(supplier=party_a.pk, po_reference=po_b.pk), tenant=tenant_a)
    assert not form.is_valid() and "po_reference" in form.errors


# ------------------------------------------------------------------ decision / lift notes

def test_decision_form_note_boundaries():
    # An UNBOUND form is never valid by definition (is_valid == is_bound and not errors),
    # so the empty-note case is exercised through a bound empty payload.
    assert SuspensionDecisionForm({"note": ""}).is_valid()
    assert not SuspensionDecisionForm().is_bound
    assert SuspensionDecisionForm({"note": "x" * 2000}).is_valid()
    assert not SuspensionDecisionForm({"note": "x" * 2001}).is_valid()


def test_lift_form_requires_note():
    assert not SuspensionLiftForm({"lift_note": ""}).is_valid()
    assert SuspensionLiftForm({"lift_note": "Resolved after CAPA closed."}).is_valid()
    assert not SuspensionLiftForm({"lift_note": "x" * 2001}).is_valid()


# ------------------------------------------------------------------ VendorInvoiceSubmissionForm

def test_vis_form_queryset_narrows_to_suppliers_orders(tenant_a, supplier_a, po_a):
    _, party = supplier_a
    po_other = _second_po_for_other_vendor(tenant_a)

    form = VendorInvoiceSubmissionForm(tenant=tenant_a, supplier=party)
    qs = form.fields["purchase_order"].queryset
    assert po_a in qs
    assert po_other not in qs


def test_vis_form_crafted_po_guard(tenant_a, supplier_a, po_a):
    """Another vendor's PO never passes — even hand-fed past the narrowed dropdown."""
    _, party = supplier_a
    po_other = _second_po_for_other_vendor(tenant_a)
    form = VendorInvoiceSubmissionForm(
        _vis_payload(purchase_order=po_other.pk), tenant=tenant_a, supplier=party)
    assert not form.is_valid() and "purchase_order" in form.errors


def test_vis_form_valid_save_leaves_supplier_to_view(tenant_a, supplier_a, po_a):
    _, party = supplier_a
    form = VendorInvoiceSubmissionForm(
        _vis_payload(purchase_order=po_a.pk), tenant=tenant_a, supplier=party)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    assert instance.purchase_order_id == po_a.pk
    assert instance.tenant_id == tenant_a.pk
    # supplier is excluded from the form — the portal view pins it server-side.
    assert instance.supplier_id is None


def test_vis_form_amount_must_be_positive(tenant_a, supplier_a):
    _, party = supplier_a
    for bad in ("0", "-5.00"):
        form = VendorInvoiceSubmissionForm(
            _vis_payload(amount=bad), tenant=tenant_a, supplier=party)
        # Enforced at MODEL clean, surfaced through the form's full_clean.
        assert not form.is_valid() and "amount" in form.errors


def test_review_form_boundaries():
    assert SubmissionReviewForm({"review_note": ""}).is_valid()
    assert not SubmissionReviewForm().is_bound  # unbound forms are never valid
    assert SubmissionReviewForm({"review_note": "x" * 2000}).is_valid()
    assert not SubmissionReviewForm({"review_note": "x" * 2001}).is_valid()
