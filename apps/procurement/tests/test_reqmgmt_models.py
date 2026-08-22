"""Procurement 6.2 Requisition Management — model unit tests.

Covers the RequisitionTemplates (RQT-) and RequisitionAmendments (RAM-) contracts:
per-tenant auto-numbering, derived estimated_total / line_total, amendment gating
(AMENDABLE_STATUSES, has_open_for), cancel/amend clean() rules, and the deterministic
apply()/apply_to_requisition() writers onto the scm.PurchaseRequisition spine.
"""
import datetime
import re
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError

from apps.procurement.models import (
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionTemplate,
    RequisitionTemplateLine,
)
from apps.scm.models import PurchaseRequisition


# ------------------------------------------------------------------ helpers
def _reqmgmt_template(tenant, name="Template", **overrides):
    fields = dict(tenant=tenant, name=name)
    fields.update(overrides)
    return RequisitionTemplate.objects.create(**fields)


def _reqmgmt_template_line(template, description="A4 printer paper",
                           quantity=Decimal("4"), price=Decimal("22.50"), **overrides):
    fields = dict(template=template, item_description=description,
                  quantity=quantity, estimated_unit_price=price)
    fields.update(overrides)
    return RequisitionTemplateLine.objects.create(**fields)


def _reqmgmt_amendment(requisition, amendment_type="cancel", status="pending", **overrides):
    fields = dict(
        tenant=requisition.tenant,
        requisition=requisition,
        amendment_type=amendment_type,
        status=status,
        reason="No longer needed.",
    )
    fields.update(overrides)
    return RequisitionAmendment.objects.create(**fields)


# ------------------------------------------------------------------ templates
def test_reqmgmt_template_number_auto_per_tenant(db, tenant_a, tenant_b):
    t1 = _reqmgmt_template(tenant_a)
    t2 = _reqmgmt_template(tenant_a)
    tb = _reqmgmt_template(tenant_b)
    assert re.fullmatch(r"RQT-\d{5}", t1.number)
    assert re.fullmatch(r"RQT-\d{5}", t2.number)
    assert t1.number != t2.number
    # per-tenant sequences are independent: tenant_b's first template restarts at 00001
    assert tb.number == "RQT-00001"


def test_reqmgmt_template_defaults_and_unique_together(db, tenant_a):
    template = _reqmgmt_template(tenant_a)
    assert template.is_active is True
    assert ("tenant", "number") in RequisitionTemplate._meta.unique_together


def test_reqmgmt_template_estimated_total_sums_lines(template_with_lines_a):
    assert template_with_lines_a.estimated_total == Decimal("102.60")


def test_reqmgmt_template_empty_total_is_zero_and_str(db, tenant_a):
    template = _reqmgmt_template(tenant_a, name="Empty blueprint")
    assert template.estimated_total == Decimal("0.00")
    text = str(template)
    assert template.number in text
    assert "Empty blueprint" in text


def test_reqmgmt_template_line_total_quantized_and_ordering(db, tenant_a):
    template = _reqmgmt_template(tenant_a)
    first = _reqmgmt_template_line(template, "A4 printer paper")
    second = _reqmgmt_template_line(template, "Sticky notes assorted",
                                    quantity=Decimal("3"), price=Decimal("4.20"))
    assert first.line_total == Decimal("90.00")
    assert second.line_total == Decimal("12.60")
    assert list(template.lines.all()) == [first, second]  # Meta.ordering == ["id"]


# ------------------------------------------------------------------ amendments: gating & numbering
def test_reqmgmt_amendment_amendable_statuses_constant():
    assert RequisitionAmendment.AMENDABLE_STATUSES == ("pending_approval", "approved")


def test_reqmgmt_amendment_number_auto_assigned(db, requisition_approved_a):
    amendment = _reqmgmt_amendment(requisition_approved_a, amendment_type="amend")
    assert re.fullmatch(r"RAM-\d{5}", amendment.number)
    assert amendment.is_pending and not amendment.is_cancel


def test_reqmgmt_has_open_for_pending_vs_decided(amendment_pending_a, requisition_approved_a):
    assert RequisitionAmendment.has_open_for(requisition_approved_a) is True
    amendment_pending_a.status = "rejected"
    amendment_pending_a.save(update_fields=["status"])
    assert RequisitionAmendment.has_open_for(requisition_approved_a) is False


# ------------------------------------------------------------------ amendments: clean()
def test_reqmgmt_cancel_clean_rejects_proposed_changes(tenant_a, requisition_approved_a):
    amendment = RequisitionAmendment(
        tenant=tenant_a, requisition=requisition_approved_a, amendment_type="cancel",
        reason="Project shelved.",
        new_required_by=datetime.date.today() + datetime.timedelta(days=5))
    with pytest.raises(ValidationError) as exc:
        amendment.clean()
    assert "new_required_by" in exc.value.message_dict

    amendment.new_required_by = None
    amendment.new_justification = "Different wording"
    with pytest.raises(ValidationError) as exc:
        amendment.clean()
    assert "new_justification" in exc.value.message_dict


def test_reqmgmt_amend_clean_allows_proposed_changes(amendment_pending_a):
    amendment_pending_a.clean()  # amend type may carry new_required_by/new_justification


# ------------------------------------------------------------------ amendments: apply()
def test_reqmgmt_apply_cancel_cancels_requisition(db, admin_user, requisition_approved_a):
    amendment = _reqmgmt_amendment(requisition_approved_a, amendment_type="cancel")

    summary = amendment.apply(admin_user)

    assert "cancel" in summary.lower()
    pr = PurchaseRequisition.objects.get(pk=requisition_approved_a.pk)
    assert pr.status == "cancelled"
    assert amendment.number in pr.decision_note
    amendment.refresh_from_db()
    assert amendment.status == "approved"
    assert amendment.decided_by == admin_user
    assert amendment.decided_at is not None
    assert amendment.applied_at is not None


def test_reqmgmt_apply_amend_moves_required_by_and_recalculates(db, admin_user, amendment_pending_a):
    pr = amendment_pending_a.requisition
    new_date = amendment_pending_a.new_required_by

    summary = amendment_pending_a.apply(admin_user)

    pr.refresh_from_db()
    amendment_pending_a.refresh_from_db()
    assert pr.required_by == new_date
    assert pr.estimated_total == Decimal("103.60")
    assert f"required-by -> {new_date:%Y-%m-%d}" in summary
    assert amendment_pending_a.status == "approved"
    assert amendment_pending_a.applied_at is not None


def test_reqmgmt_apply_twice_raises_nothing(db, admin_user, amendment_pending_a):
    amendment_pending_a.apply(admin_user)
    amendment_pending_a.apply(admin_user)  # caller contract guards status; model itself does not
    amendment_pending_a.refresh_from_db()
    assert amendment_pending_a.status == "approved"


# ------------------------------------------------------------------ amendment lines: clean()
def _reqmgmt_amline(amendment, **overrides):
    fields = dict(amendment=amendment, action="update")
    fields.update(overrides)
    return RequisitionAmendmentLine(**fields)


def test_reqmgmt_line_clean_update_remove_need_target(amendment_pending_a):
    for action in ("update", "remove"):
        line = _reqmgmt_amline(amendment_pending_a, action=action,
                               target_line=None, item_description="x")
        with pytest.raises(ValidationError) as exc:
            line.clean()
        assert "target_line" in exc.value.message_dict


def test_reqmgmt_line_clean_add_rules(amendment_pending_a, requisition_approved_a):
    target = requisition_approved_a.lines.first()
    line = _reqmgmt_amline(amendment_pending_a, action="add", target_line=target,
                           item_description="New item")
    with pytest.raises(ValidationError) as exc:
        line.clean()
    assert "action" in exc.value.message_dict

    blank = _reqmgmt_amline(amendment_pending_a, action="add", target_line=None,
                            item_description="   ")
    with pytest.raises(ValidationError) as exc:
        blank.clean()
    assert "item_description" in exc.value.message_dict


# ------------------------------------------------------------------ amendment lines: apply_to_requisition()
def test_reqmgmt_line_apply_add_creates_pr_line(amendment_pending_a):
    pr = amendment_pending_a.requisition
    before = pr.lines.count()
    line = _reqmgmt_amline(amendment_pending_a, action="add", target_line=None,
                           item_description="Whiteboard markers",
                           quantity=Decimal("6"), estimated_unit_price=Decimal("3.10"))
    line.save()

    outcome = line.apply_to_requisition()

    assert outcome.startswith("added")
    assert pr.lines.count() == before + 1
    created = pr.lines.order_by("-id").first()
    assert created.item_description == "Whiteboard markers"
    assert created.quantity == Decimal("6")
    assert created.estimated_unit_price == Decimal("3.10")


def test_reqmgmt_line_apply_remove_deletes_target(amendment_pending_a):
    pr = amendment_pending_a.requisition
    target = pr.lines.first()
    line = _reqmgmt_amline(amendment_pending_a, action="remove", target_line=target)
    line.save()

    outcome = line.apply_to_requisition()

    assert outcome.startswith("removed")
    assert not pr.lines.filter(pk=target.pk).exists()


def test_reqmgmt_line_apply_update_changes_quantity(amendment_pending_a):
    target = amendment_pending_a.requisition.lines.first()
    line = _reqmgmt_amline(amendment_pending_a, action="update", target_line=target,
                           quantity=Decimal("9"))
    line.save()

    outcome = line.apply_to_requisition()

    assert "qty" in outcome
    target.refresh_from_db()
    assert target.quantity == Decimal("9")
    assert target.estimated_unit_price == Decimal("22.50")  # blank proposal keeps price


def test_reqmgmt_line_apply_update_lost_target_reported(amendment_pending_a):
    target = amendment_pending_a.requisition.lines.first()
    line = _reqmgmt_amline(amendment_pending_a, action="update", target_line=target,
                           quantity=Decimal("9"))
    line.save()
    line.target_line = None  # the requisition was edited while the amendment pended

    outcome = line.apply_to_requisition()

    assert outcome == "'Update line' not applied — target line no longer exists"
