"""Procurement 6.2 - Requisition Management form boundary.

A narrowed ``<select>`` is UX, not an authorization boundary: the template/amendment forms
re-check every tenant-scoped FK as a FIELD ERROR (``_reject_foreign``), and the two inline
line formsets carry their own base-clean rules - template lines may not charge another
workspace's GL account, amendment lines may only target lines of THE amended requisition,
one live proposal per target line. Both factories default to the ``"lines"`` prefix because
every child FK here declares ``related_name="lines"``.
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.procurement.forms import (
    AmendmentDecisionForm,
    RequisitionAmendmentForm,
    RequisitionAmendmentLineFormSet,
    RequisitionTemplateForm,
    RequisitionTemplateLineFormSet,
)
from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ payload builders
def management_form(total, initial=0):
    """The 4 hidden ``lines-*`` management keys both 6.2 inline formsets POST."""
    return {
        "lines-TOTAL_FORMS": str(total),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }


def template_row(i, description="", qty="1", price="0.00", gl_account=""):
    return {
        f"lines-{i}-item_description": description,
        f"lines-{i}-sku_hint": "",
        f"lines-{i}-uom_hint": "",
        f"lines-{i}-quantity": qty,
        f"lines-{i}-estimated_unit_price": price,
        f"lines-{i}-gl_account": gl_account,
    }


def amendment_row(i, action="update", target_line=""):
    return {
        f"lines-{i}-action": action,
        f"lines-{i}-target_line": target_line,
        f"lines-{i}-item_description": "",
        f"lines-{i}-sku_hint": "",
        f"lines-{i}-uom_hint": "",
        f"lines-{i}-quantity": "",
        f"lines-{i}-estimated_unit_price": "",
        f"lines-{i}-needed_by": "",
    }


def other_requisition_line(tenant_a, admin_user):
    """A second PR (same workspace!) with its own line - the crafted-POST bait."""
    pr = PurchaseRequisition.objects.create(
        tenant=tenant_a, title="Unrelated requisition", requester=admin_user,
        required_by=timezone.localdate() + datetime.timedelta(days=5),
        status="approved", justification="Not the amended one.")
    return PurchaseRequisitionLine.objects.create(
        requisition=pr, item_description="Foreign line",
        quantity=Decimal("1"), estimated_unit_price=Decimal("9.99"))


# ------------------------------------------------------------------ RequisitionTemplateForm
def test_reqmgmt_template_form_fields_and_factory_caps():
    form = RequisitionTemplateForm()
    assert list(form.fields) == ["name", "description", "org_unit", "currency",
                                 "default_lead_days", "justification", "is_active"]
    assert (RequisitionTemplateLineFormSet.max_num,
            RequisitionTemplateLineFormSet.extra,
            RequisitionTemplateLineFormSet.can_delete) == (50, 2, True)


def test_reqmgmt_template_minimal_valid_post_saves(tenant_a):
    form = RequisitionTemplateForm({"name": "Weekly toner restock"}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    # The FORM never stamps tenant - that is the view's job (crud_create parity).
    assert obj.tenant_id is None
    obj.tenant = tenant_a
    obj.save()
    assert obj.number and obj.number.startswith("RQT")


def test_reqmgmt_template_same_tenant_org_unit_accepted(tenant_a, org_unit_a):
    form = RequisitionTemplateForm({"name": "T", "org_unit": str(org_unit_a.pk)},
                                   tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["org_unit"] == org_unit_a


def test_reqmgmt_template_foreign_org_unit_rejected_as_field_error(tenant_a, org_unit_b):
    data = {"name": "T", "org_unit": str(org_unit_b.pk)}
    scoped = RequisitionTemplateForm(data, tenant=tenant_a)
    assert not scoped.is_valid()
    assert "org_unit" in scoped.errors
    # Layer 2 (_reject_foreign): with the queryset NOT pre-narrowing the choices, the
    # hand-posted foreign pk must still land as the exact rule message.
    loose = RequisitionTemplateForm(data)
    assert not loose.is_valid()
    assert loose.errors["org_unit"] == ["That record belongs to another workspace."]


# ------------------------------------------------------------------ template line formset
def test_reqmgmt_template_lines_accepts_three_rows_under_max_num(tenant_a, gl_expense_a):
    from apps.procurement.models import RequisitionTemplate

    template = RequisitionTemplate.objects.create(tenant=tenant_a, name="Fresh blueprint")
    data = management_form(3)
    for i in range(3):
        data.update(template_row(i, f"Bulk item {i}", "2", "5.00", str(gl_expense_a.pk)))
    fs = RequisitionTemplateLineFormSet(data, instance=template,
                                        form_kwargs={"tenant": tenant_a})
    assert fs.is_valid(), fs.errors
    created = fs.save()
    assert len(created) == 3 and template.lines.count() == 3


def test_reqmgmt_template_lines_foreign_gl_account_row_error(
        tenant_a, gl_expense_b, template_with_lines_a):
    lines = list(template_with_lines_a.lines.all())
    data = management_form(3, initial=2)
    for i, line in enumerate(lines):
        data.update(template_row(i, line.item_description, "4", "22.50"))
        data[f"lines-{i}-id"] = str(line.pk)
    data.update(template_row(2, "Ergo mouse pads", "10", "3.75", str(gl_expense_b.pk)))

    scoped = RequisitionTemplateLineFormSet(data, instance=template_with_lines_a,
                                            form_kwargs={"tenant": tenant_a})
    assert not scoped.is_valid()
    assert "gl_account" in scoped.errors[2]
    # Layer 2 (_reject_foreign per row): unscoped choices still cannot charge another
    # workspace's account - the exact rule message renders on the offending row.
    loose = RequisitionTemplateLineFormSet(data, instance=template_with_lines_a)
    assert not loose.is_valid()
    assert loose.errors[2]["gl_account"] == ["That record belongs to another workspace."]


# ------------------------------------------------------------------ RequisitionAmendmentForm
def test_reqmgmt_amendment_form_fields_and_factory_caps():
    form = RequisitionAmendmentForm()
    assert list(form.fields) == ["amendment_type", "reason", "new_required_by",
                                 "new_justification"]
    assert (RequisitionAmendmentLineFormSet.max_num,
            RequisitionAmendmentLineFormSet.extra,
            RequisitionAmendmentLineFormSet.can_delete) == (25, 1, True)


def test_reqmgmt_amendment_reason_required():
    form = RequisitionAmendmentForm({"amendment_type": "amend"})
    assert not form.is_valid()
    assert "reason" in form.errors
    assert "amendment_type" not in form.errors


def test_reqmgmt_amendment_cancel_with_proposed_changes_rejected():
    new_date = (timezone.localdate() + datetime.timedelta(days=21)).isoformat()
    form = RequisitionAmendmentForm({
        "amendment_type": "cancel", "reason": "Duplicate request",
        "new_required_by": new_date})
    assert not form.is_valid()
    assert form.errors["new_required_by"] == \
        ["A cancellation does not carry proposed changes."]


@pytest.mark.parametrize("payload", [
    {"amendment_type": "cancel", "reason": "Duplicate request"},
    {"amendment_type": "amend", "reason": "Push the date out",
     "new_required_by": (timezone.localdate() + datetime.timedelta(days=30)).isoformat()},
])
def test_reqmgmt_amendment_cancel_alone_or_amend_with_date_is_valid(payload):
    form = RequisitionAmendmentForm(payload)
    assert form.is_valid(), form.errors


# ------------------------------------------------------------------ amendment line formset
def test_reqmgmt_amendment_target_queryset_scoped_to_own_requisition(
        tenant_a, admin_user, amendment_pending_a):
    foreign = other_requisition_line(tenant_a, admin_user)
    fs = RequisitionAmendmentLineFormSet(instance=amendment_pending_a)
    qs = fs.forms[0].fields["target_line"].queryset
    assert set(qs) == set(amendment_pending_a.requisition.lines.all())
    assert foreign not in qs


def test_reqmgmt_amendment_target_from_other_requisition_rejected(
        tenant_a, admin_user, amendment_pending_a):
    foreign = other_requisition_line(tenant_a, admin_user)
    data = management_form(1)
    data.update(amendment_row(0, "update", str(foreign.pk)))

    narrowed = RequisitionAmendmentLineFormSet(data, instance=amendment_pending_a,
                                               form_kwargs={"tenant": tenant_a})
    assert not narrowed.is_valid()
    assert "target_line" in narrowed.errors[0]

    # The base-clean re-check beneath the narrowed dropdown: widen the queryset the way
    # any future dropdown-widening path would, and the crafted pk lands on the rule.
    fs = RequisitionAmendmentLineFormSet(data, instance=amendment_pending_a,
                                         form_kwargs={"tenant": tenant_a})
    fs.forms[0].fields["target_line"].queryset = PurchaseRequisitionLine.objects.all()
    assert not fs.is_valid()
    assert fs.errors[0]["target_line"] == \
        ["That line belongs to a different requisition."]


def test_reqmgmt_amendment_duplicate_live_targets_rejected(tenant_a, amendment_pending_a):
    target = amendment_pending_a.requisition.lines.first()
    data = management_form(2)
    data.update(amendment_row(0, "update", str(target.pk)))
    data.update(amendment_row(1, "update", str(target.pk)))
    fs = RequisitionAmendmentLineFormSet(data, instance=amendment_pending_a,
                                         form_kwargs={"tenant": tenant_a})
    assert not fs.is_valid()
    assert fs.errors[0] == {}
    assert fs.errors[1]["target_line"] == \
        ["This line is targeted by more than one row."]


def test_reqmgmt_amendment_duplicate_target_ok_when_twin_deleted(
        tenant_a, amendment_pending_a):
    target = amendment_pending_a.requisition.lines.first()
    data = management_form(2)
    data.update(amendment_row(0, "update", str(target.pk)))
    data.update(amendment_row(1, "update", str(target.pk)))
    data["lines-0-DELETE"] = "on"
    fs = RequisitionAmendmentLineFormSet(data, instance=amendment_pending_a,
                                         form_kwargs={"tenant": tenant_a})
    assert fs.is_valid(), fs.errors
    # Django drops the fully-deleted extra form from `errors`, so the single surviving entry is
    # the row-1 twin — and it must carry NO duplicate-target error.
    assert len(fs.errors) == 1
    assert fs.errors[0] == {}


# ------------------------------------------------------------------ AmendmentDecisionForm
def test_reqmgmt_decision_note_blank_ok():
    form = AmendmentDecisionForm({})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["decision_note"] == ""
