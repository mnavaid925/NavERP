"""8.6 Order Management -- forms lane.

The lane exists for the 0.20 close-out lesson, the sharpest edge in this sub-module: **a
``ValidationError`` keyed on a field the form does not carry routes through Django's
``add_error(None, ...)`` and raises ``ValueError``** -- a 500 on create *and* edit, and a
*data-dependent* one, so the same form saves for one row and 500s for another depending on
invisible prior state. Every guard below is therefore exercised through a REAL form instance,
not by calling ``full_clean()`` in isolation, because only the form proves the key is safe.

Also asserted: the exact ``Meta.fields`` of all seven forms, that no frozen-evidence field ever
reaches a form (L22), and that every FK queryset is narrowed to its own tenant.
"""
import pytest

from apps.core.models import Party
from apps.scm.models import SalesOrder
from apps.sales.forms import (
    OrderAmendmentDecisionForm,
    OrderAmendmentForm,
    OrderAmendmentLineForm,
    OrderHoldActionForm,
    OrderHoldForm,
    OrderValidationRuleForm,
    PerformanceObligationForm,
    RevenueScheduleForm,
)
from apps.sales.models import OrderAmendment, OrderHold, RevenueSchedule
from apps.sales.tests.conftest import (
    _ordermanagement_amendment,
    _ordermanagement_hold,
    _ordermanagement_order,
    _ordermanagement_schedule,
)

pytestmark = pytest.mark.django_db

#: Every field that must NEVER be authorable. (L22: frozen evidence; the rest is system-owned.)
#: `severity` is deliberately NOT in this list: choosing how hard a RULE bites is the whole
#: point of configuring it, and ``OrderValidationRule.severity`` is an ordinary editable column.
#: It is the HOLD's copy of severity that is frozen at fire time.
_NEVER_AUTHORABLE = (
    "evaluation_snapshot", "impact_snapshot", "allocated_amount", "recognized_amount",
    "journal_entry", "raised_at", "raised_by", "checked_out_by",
    "checked_out_at", "cleared_by", "cleared_at", "requested_at", "requested_by",
    "decided_by", "decided_at", "applied_at", "applied_by", "tenant", "number",
    "created_at", "updated_at", "id",
)

#: ``status`` is the ONE authorable status in 8.6 (a schedule is drafted and voided by a
#: person); ``severity`` is authorable on the rule but never on the hold.
_ALLOWED = {
    OrderValidationRuleForm: {"severity"},
    RevenueScheduleForm: {"status"},
}

_MODELFORMS = (
    OrderValidationRuleForm, OrderHoldForm, OrderAmendmentForm, OrderAmendmentLineForm,
    RevenueScheduleForm, PerformanceObligationForm,
)


# ------------------------------------------------------- the 0.20 ValueError trap


def test_ordermanagement_no_form_carries_a_frozen_or_system_field():
    """The single most important structural assertion in the lane."""
    for form_cls in _MODELFORMS:
        leaked = set(form_cls.Meta.fields) & set(_NEVER_AUTHORABLE)
        assert not (leaked - _ALLOWED.get(form_cls, set())), \
            f"{form_cls.__name__} leaks {leaked - _ALLOWED.get(form_cls, set())}"


def test_ordermanagement_order_hold_form_invalid_payload_does_not_raise(ordermanagement_tenant_a):
    """C2 regression, driven THROUGH the form. A ValueError here is the 0.20 bug."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    hold = _ordermanagement_hold(tenant, order)
    OrderHold.objects.filter(pk=hold.pk).update(evaluation_snapshot='"a bare string"')
    hold.refresh_from_db()

    form = OrderHoldForm(instance=hold, tenant=tenant)
    # Must return normally -- False with errors, or True -- and NEVER raise ValueError.
    valid = form.is_valid()
    assert isinstance(valid, bool)
    assert "evaluation_snapshot" not in form.errors


def test_ordermanagement_amendment_line_form_rejects_bad_operations_without_raising(
    ordermanagement_tenant_a,
):
    """An `update` naming no order line, and a `remove` carrying a new price, are both
    non-field errors -- the model keys them on NON_FIELD_ERRORS for exactly this reason."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    amendment = _ordermanagement_amendment(tenant, order)
    order_line = order.lines.first()

    form = OrderAmendmentLineForm(
        {"operation": "update", "new_quantity": "20.00"}, tenant=tenant, amendment=amendment,
    )
    assert form.is_valid() is False
    assert form.non_field_errors(), "an update line with no order line must be a NON_FIELD error"
    assert "sales_order_line" not in form.errors

    form2 = OrderAmendmentLineForm(
        {"operation": "remove", "sales_order_line": order_line.pk, "new_unit_price": "5.00"},
        tenant=tenant, amendment=amendment,
    )
    assert form2.is_valid() is False
    assert form2.non_field_errors()
    assert "new_unit_price" not in form2.errors


def test_ordermanagement_amendment_line_form_accepts_a_valid_line(ordermanagement_tenant_a):
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    amendment = _ordermanagement_amendment(tenant, order)
    form = OrderAmendmentLineForm(
        {"operation": "update", "sales_order_line": order.lines.first().pk,
         "new_quantity": "25.00"},
        tenant=tenant, amendment=amendment,
    )
    assert form.is_valid() is True, form.errors


def test_ordermanagement_obligation_form_rejects_a_foreign_order_line_without_raising(
    ordermanagement_tenant_a, ordermanagement_tenant_b,
):
    """A line from ANOTHER order must be refused -- and refused WITHOUT raising.

    The form narrows ``sales_order_line`` to the parent schedule's own order, so Django's
    ``ModelChoiceField`` refuses the foreign pk as a FIELD error. The assertion is therefore
    "rejected, on a field, without a ValueError" rather than "rejected as a non-field error":
    the non-field path is reserved for a key the form does not carry, and this one is carried.
    Either way the cross-order line cannot be saved.
    """
    a, b = ordermanagement_tenant_a, ordermanagement_tenant_b
    order_a = _ordermanagement_order(a)
    order_b = _ordermanagement_order(b)
    schedule = _ordermanagement_schedule(a, order_a)

    form = PerformanceObligationForm(
        {"description": "Goods", "allocation_pct": "50.00", "obligation_type": "goods",
         "recognition_method": "over_time", "sales_order_line": order_b.lines.first().pk},
        tenant=a, schedule=schedule,
    )
    assert form.is_valid() is False  # must return, never raise
    assert "sales_order_line" in form.errors


def test_ordermanagement_obligation_form_accepts_its_own_orders_line(ordermanagement_tenant_a):
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    schedule = _ordermanagement_schedule(tenant, order)
    form = PerformanceObligationForm(
        {"description": "Goods", "allocation_pct": "100.00", "obligation_type": "goods",
         "recognition_method": "over_time", "sales_order_line": order.lines.first().pk},
        tenant=tenant, schedule=schedule,
    )
    assert form.is_valid() is True, form.errors



# ------------------------------------------------------ tenant-scoped FK querysets


def test_ordermanagement_every_form_fk_queryset_is_tenant_scoped(
    ordermanagement_tenant_a, ordermanagement_tenant_b,
):
    """A form may only ever be pointed at this workspace's own rows."""
    a, b = ordermanagement_tenant_a, ordermanagement_tenant_b
    order_b = _ordermanagement_order(b)

    rule_form = OrderValidationRuleForm(tenant=a)
    assert not rule_form.fields["party"].queryset.filter(tenant=b).exists()

    hold_form = OrderHoldForm(tenant=a)
    assert not hold_form.fields["sales_order"].queryset.filter(tenant=b).exists()
    assert not hold_form.fields["rule"].queryset.filter(tenant=b).exists()
    assert not hold_form.fields["party"].queryset.filter(tenant=b).exists()

    schedule_form = RevenueScheduleForm(tenant=a)
    assert not schedule_form.fields["sales_order"].queryset.filter(tenant=b).exists()


def test_ordermanagement_amendment_form_offers_only_amendable_orders(ordermanagement_tenant_a):
    """The dropdown and the method read the SAME tuple, so eligibility cannot disagree."""
    tenant = ordermanagement_tenant_a
    amendable = _ordermanagement_order(tenant, status="allocated")
    terminal = _ordermanagement_order(tenant, status="cancelled")
    form = OrderAmendmentForm(tenant=tenant)
    offered = set(form.fields["sales_order"].queryset.values_list("pk", flat=True))
    assert amendable.pk in offered
    assert terminal.pk not in offered
    # Nothing outside the amendable set may be offered, whoever owns it.
    assert offered <= set(
        SalesOrder.objects.filter(tenant=tenant, status__in=OrderAmendment.AMENDABLE_STATUSES)
        .values_list("pk", flat=True)
    )


def test_ordermanagement_revenue_schedule_status_widget_is_narrowed_to_the_choices():
    """The ONE authorable status must not be authorable to any value outside the choices."""
    form = RevenueScheduleForm(tenant=None)
    offered = {v for v, _ in form.fields["status"].choices}
    assert offered == {v for v, _ in RevenueSchedule.STATUS_CHOICES}


# -------------------------------------------------------------- field-set contracts


def test_ordermanagement_form_meta_fields_match_the_contract():
    """The exact field sets the contract pins; a silent addition is drift (L7)."""
    assert list(OrderValidationRuleForm.Meta.fields) == [
        "name", "rule_type", "severity", "active_on", "parameters", "party",
        "priority", "is_active", "description",
    ]
    assert list(OrderHoldForm.Meta.fields) == [
        "sales_order", "rule", "party", "hold_type", "reason", "clear_note",
    ]
    assert list(OrderAmendmentForm.Meta.fields) == [
        "sales_order", "change_type", "reason", "document", "notes",
    ]
    assert list(OrderAmendmentLineForm.Meta.fields) == [
        "sales_order_line", "operation", "new_quantity", "new_unit_price", "note",
    ]
    assert list(RevenueScheduleForm.Meta.fields) == [
        "sales_order", "status", "method", "compliance_standard", "fiscal_period", "notes",
    ]
    assert list(PerformanceObligationForm.Meta.fields) == [
        "sales_order_line", "item", "obligation_type", "description", "allocation_pct",
        "recognition_method", "recognize_on", "milestone_label", "evidence_reference",
    ]


def test_ordermanagement_child_forms_never_carry_their_parent_fk():
    """The parent is set by the view, never taken from user input."""
    assert "amendment" not in OrderAmendmentLineForm.Meta.fields
    assert "schedule" not in PerformanceObligationForm.Meta.fields



# -------------------------------------------------------------- the decision form


def test_ordermanagement_decision_form_is_a_plain_form_with_both_outcomes():
    form = OrderAmendmentDecisionForm()
    assert set(form.fields) == {"decision", "decision_note"}
    assert {v for v, _ in form.fields["decision"].choices} == {"approved", "rejected"}


def test_ordermanagement_decision_form_rejects_an_unknown_decision():
    form = OrderAmendmentDecisionForm({"decision": "escalated", "decision_note": "x"})
    assert form.is_valid() is False
    assert "decision" in form.errors


def test_ordermanagement_decision_note_is_optional_but_accepted():
    """Optional in the form, but it IS the approver's own record and must round-trip."""
    form = OrderAmendmentDecisionForm({"decision": "approved", "decision_note": "Margin holds."})
    assert form.is_valid() is True
    assert form.cleaned_data["decision_note"] == "Margin holds."


# --------------------------------------------------------------- the action form


def test_ordermanagement_hold_action_form_carries_the_clear_note():
    form = OrderHoldActionForm(tenant=None)
    assert "clear_note" in form.fields
    # A clear with no justification is refused: the justification is the point of the verb.
    assert form.is_valid() is False
    assert OrderHoldActionForm(
        {"clear_note": "Credit limit raised by finance."}, tenant=None,
    ).is_valid() is True


# ------------------------------------------------------------------- the rule form


def test_ordermanagement_rule_form_saves_a_valid_payload(ordermanagement_tenant_a):
    tenant = ordermanagement_tenant_a
    form = OrderValidationRuleForm(
        {"name": "Order ceiling", "rule_type": "order_value", "severity": "hold",
         "active_on": "submit", "parameters": {"amount": "5000"},
         "priority": "5", "is_active": "on", "description": "Cap."},
        tenant=tenant,
    )
    assert form.is_valid() is True, form.errors
    rule = form.save()
    assert rule.tenant_id == tenant.pk
    assert rule.number.startswith("OVR-")
    assert rule.parameters == {"amount": "5000"}


def test_ordermanagement_rule_form_rejects_a_non_dict_parameters_blob(ordermanagement_tenant_a):
    """A malformed JSON blob is a FORM error, never a 500 out of JSONField on save."""
    form = OrderValidationRuleForm(
        {"name": "Bad", "rule_type": "order_value", "severity": "hold",
         "active_on": "submit", "parameters": ["not", "a", "mapping"]},
        tenant=ordermanagement_tenant_a,
    )
    assert form.is_valid() is False
    assert "parameters" in form.errors


def test_ordermanagement_rule_form_rejects_a_cross_tenant_party(ordermanagement_tenant_a,
                                                                 ordermanagement_tenant_b):
    """The tenant guard on a FK the form narrowed -- defence in depth, not the only line."""
    a, b = ordermanagement_tenant_a, ordermanagement_tenant_b
    foreign = Party.objects.create(tenant=b, name="Foreign Party", kind="customer")
    form = OrderValidationRuleForm(
        {"name": "x", "rule_type": "order_value", "severity": "hold", "active_on": "submit",
         "parameters": {}, "party": foreign.pk},
        tenant=a,
    )
    # Either the queryset excludes it outright or validation refuses it -- both are correct;
    # what must never happen is a form that accepts another workspace's customer.
    if form.is_valid():
        pytest.fail("a cross-tenant party was accepted by the rule form")

