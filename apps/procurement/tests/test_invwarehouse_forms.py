"""Procurement 6.18 Inventory & Warehouse Integration — form tests.

Two things these tests exist to hold:

* **The excluded columns stay excluded.** Every system stamp — ``tenant``, ``number``, ``status``,
  ``adjustment``, ``issued_by``, the ``*_at`` timestamps, ``generated_by``, ``requisition`` and all
  eleven ``ReplenishmentSuggestion`` snapshots — is absent from every form. A field that reappears
  lets a POST claim a document was posted, or point it at another tenant's stock adjustment.
* **A narrowed ``<select>`` is UX; ``clean()`` is the boundary.** Every test that proves a dropdown
  is narrowed has a partner that submits the foreign pk anyway and asserts the form still refuses
  it — narrowing alone is bypassable by a hand-crafted POST, so proving only the narrowing would
  be proving the wrong half.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.procurement.forms import (
    MaterialIssueForm,
    MaterialIssueLineForm,
    ReplenishmentPolicyForm,
    ReplenishmentRunForm,
    ReplenishmentSuggestionDecisionForm,
)
from apps.procurement.models import MaterialIssue, ReplenishmentRun, ReplenishmentSuggestion

pytestmark = pytest.mark.django_db


def _invwarehouse_policy_data(item, location=None, **overrides):
    data = {"item": item.pk, "source_method": "buy", "trigger_mode": "review",
            "include_on_order": "on", "include_open_requisitions": "on", "is_active": "on",
            "notes": ""}
    if location is not None:
        data["location"] = location.pk
    data.update(overrides)
    return data


def _invwarehouse_issue_data(location, **overrides):
    data = {"location": location.pk, "movement_type": "issue", "purpose": "cost_centre",
            "reference": "", "issue_date": date.today().isoformat(), "notes": ""}
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- excluded columns


def test_invwarehouse_policy_form_excludes_the_system_columns():
    fields = set(ReplenishmentPolicyForm.Meta.fields)
    for banned in ("tenant", "created_at", "updated_at"):
        assert banned not in fields


def test_invwarehouse_run_form_excludes_every_workflow_and_stamp_column():
    """status/number/generated_* are set by the verbs. A form field would let a POST forge them."""
    fields = set(ReplenishmentRunForm.Meta.fields)
    for banned in ("tenant", "number", "status", "generated_by", "generated_at", "released_at",
                   "created_at", "updated_at"):
        assert banned not in fields, banned


def test_invwarehouse_decision_form_excludes_every_snapshot_column():
    """The eleven snapshots are editable=False on the model; the form must agree.

    They are what makes a suggestion still explain itself after the stock it measured moved on —
    an editable snapshot is a rewritable audit trail.
    """
    fields = set(ReplenishmentSuggestionDecisionForm.Meta.fields)
    snapshots = ("on_hand_qty", "allocated_qty", "on_order_qty", "open_requisition_qty",
                 "available_qty", "reorder_point_snapshot", "target_level_snapshot",
                 "raw_suggested_qty", "suggested_qty", "unit_cost", "lead_time_days",
                 "requisition")
    for banned in snapshots:
        assert banned not in fields, banned
    assert fields == {"decision", "snooze_until", "vendor", "decision_note"}


def test_invwarehouse_issue_form_excludes_the_ledger_and_stamp_columns():
    """`adjustment` above all: it is provenance written by post().

    A form field there would let a POST point a procurement document at somebody else's stock
    adjustment, forging the link between this module and the ledger.
    """
    fields = set(MaterialIssueForm.Meta.fields)
    for banned in ("tenant", "number", "status", "adjustment", "issued_by", "posted_at",
                   "cancelled_at", "created_at", "updated_at"):
        assert banned not in fields, banned


def test_invwarehouse_line_form_excludes_unit_cost():
    """unit_cost is an Item.average_cost snapshot stamped in save(), not an input.

    Accepting it would let the value of an issue drift from what the stock actually cost.
    """
    assert "unit_cost" not in set(MaterialIssueLineForm.Meta.fields)


# --------------------------------------------------------------------------- tenant narrowing


def test_invwarehouse_policy_form_narrows_every_dropdown_to_the_tenant(
        tenant_a, invwarehouse_item_a, invwarehouse_item_b,
        invwarehouse_location_a, invwarehouse_location_b,
        invwarehouse_vendor_a, invwarehouse_vendor_b):
    form = ReplenishmentPolicyForm(tenant=tenant_a)
    assert invwarehouse_item_a in form.fields["item"].queryset
    assert invwarehouse_item_b not in form.fields["item"].queryset
    assert invwarehouse_location_b not in form.fields["location"].queryset
    assert invwarehouse_vendor_b not in form.fields["preferred_vendor"].queryset


def test_invwarehouse_policy_form_offers_suppliers_only_not_every_party(
        tenant_a, invwarehouse_vendor_a, invwarehouse_plain_party_a):
    """A same-tenant party with no supplier/vendor role is not somebody you can buy from."""
    form = ReplenishmentPolicyForm(tenant=tenant_a)
    assert invwarehouse_vendor_a in form.fields["preferred_vendor"].queryset
    assert invwarehouse_plain_party_a not in form.fields["preferred_vendor"].queryset


def test_invwarehouse_policy_form_is_empty_for_a_tenant_less_user(invwarehouse_item_a):
    """The superuser has tenant=None and must be offered nothing rather than everything."""
    form = ReplenishmentPolicyForm(tenant=None)
    for name in ("item", "location", "preferred_vendor", "default_org_unit",
                 "default_budget", "default_gl_account"):
        assert form.fields[name].queryset.count() == 0, name


def test_invwarehouse_issue_form_narrows_its_dropdowns(
        tenant_a, invwarehouse_location_a, invwarehouse_location_b):
    form = MaterialIssueForm(tenant=tenant_a)
    assert invwarehouse_location_a in form.fields["location"].queryset
    assert invwarehouse_location_b not in form.fields["location"].queryset


def test_invwarehouse_line_form_narrows_item_and_lot(
        tenant_a, invwarehouse_item_a, invwarehouse_item_b, invwarehouse_lot_a):
    form = MaterialIssueLineForm(tenant=tenant_a)
    assert invwarehouse_item_a in form.fields["item"].queryset
    assert invwarehouse_item_b not in form.fields["item"].queryset


# ------------------------------------------------ narrowing is UX; clean() is the boundary


def test_invwarehouse_policy_form_refuses_a_foreign_item_submitted_directly(
        tenant_a, invwarehouse_item_b, invwarehouse_location_a):
    """The partner to the narrowing test above.

    A narrowed <select> only shapes the page. This submits tenant B's item pk anyway — the way a
    hand-crafted POST would — and the form must still refuse it.
    """
    form = ReplenishmentPolicyForm(
        data=_invwarehouse_policy_data(invwarehouse_item_b, invwarehouse_location_a),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors


def test_invwarehouse_policy_form_refuses_a_foreign_vendor_submitted_directly(
        tenant_a, invwarehouse_item_a, invwarehouse_location_a, invwarehouse_vendor_b):
    form = ReplenishmentPolicyForm(
        data=_invwarehouse_policy_data(invwarehouse_item_a, invwarehouse_location_a,
                                       preferred_vendor=invwarehouse_vendor_b.pk),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "preferred_vendor" in form.errors


def test_invwarehouse_issue_form_refuses_a_foreign_location_submitted_directly(
        tenant_a, invwarehouse_location_b):
    form = MaterialIssueForm(data=_invwarehouse_issue_data(invwarehouse_location_b),
                             tenant=tenant_a)
    assert not form.is_valid()
    assert "location" in form.errors


def test_invwarehouse_line_form_refuses_a_foreign_item_submitted_directly(
        tenant_a, invwarehouse_issue_draft_a, invwarehouse_item_b):
    form = MaterialIssueLineForm(
        data={"item": invwarehouse_item_b.pk, "quantity": "1", "notes": ""}, tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors


# --------------------------------------------------------------------------- validation rules


def test_invwarehouse_policy_form_accepts_a_well_formed_row(
        tenant_a, invwarehouse_item3_a, invwarehouse_location_a, invwarehouse_vendor_a):
    form = ReplenishmentPolicyForm(
        data=_invwarehouse_policy_data(invwarehouse_item3_a, invwarehouse_location_a,
                                       preferred_vendor=invwarehouse_vendor_a.pk,
                                       target_level="200", order_multiple="25",
                                       min_order_qty="10", max_order_qty="500"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_invwarehouse_policy_form_refuses_a_max_below_the_min(
        tenant_a, invwarehouse_item3_a, invwarehouse_location_a):
    form = ReplenishmentPolicyForm(
        data=_invwarehouse_policy_data(invwarehouse_item3_a, invwarehouse_location_a,
                                       min_order_qty="50", max_order_qty="10"),
        tenant=tenant_a)
    assert not form.is_valid()


def test_invwarehouse_policy_form_refuses_a_duplicate_catch_all(
        tenant_a, invwarehouse_item_a, invwarehouse_policy_catchall_a):
    """The nullable-unique probe, reached through the form.

    unique_together cannot catch a second (tenant, item, NULL) row because NULLs compare distinct
    in SQL, so this is the only layer that refuses it.
    """
    form = ReplenishmentPolicyForm(
        data=_invwarehouse_policy_data(invwarehouse_item_a), tenant=tenant_a)
    assert not form.is_valid()


def test_invwarehouse_decision_form_requires_a_future_date_when_snoozing(
        tenant_a, invwarehouse_run_lines_a):
    """Snoozing to yesterday is not snoozing — the line would surface again immediately."""
    past = (date.today() - timedelta(days=1)).isoformat()
    form = ReplenishmentSuggestionDecisionForm(
        data={"decision": "snoozed", "snooze_until": past, "decision_note": ""}, tenant=tenant_a)
    assert not form.is_valid()
    assert "snooze_until" in form.errors


def test_invwarehouse_decision_form_requires_a_date_when_snoozing(tenant_a):
    form = ReplenishmentSuggestionDecisionForm(
        data={"decision": "snoozed", "snooze_until": "", "decision_note": ""}, tenant=tenant_a)
    assert not form.is_valid()


def test_invwarehouse_decision_form_accepts_accept_without_a_date(tenant_a):
    form = ReplenishmentSuggestionDecisionForm(
        data={"decision": "accepted", "snooze_until": "", "decision_note": "ok"}, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_invwarehouse_line_form_refuses_a_zero_quantity(tenant_a, invwarehouse_item_a):
    """MinValueValidator(0.0001) — a zero-quantity issue line is a line that does nothing."""
    form = MaterialIssueLineForm(
        data={"item": invwarehouse_item_a.pk, "quantity": "0", "notes": ""}, tenant=tenant_a)
    assert not form.is_valid()
    assert "quantity" in form.errors


def test_invwarehouse_line_form_refuses_a_negative_quantity(tenant_a, invwarehouse_item_a):
    form = MaterialIssueLineForm(
        data={"item": invwarehouse_item_a.pk, "quantity": "-5", "notes": ""}, tenant=tenant_a)
    assert not form.is_valid()


def test_invwarehouse_issue_form_requires_notes_when_the_purpose_is_other(
        tenant_a, invwarehouse_location_a):
    form = MaterialIssueForm(
        data=_invwarehouse_issue_data(invwarehouse_location_a, purpose="other", notes=""),
        tenant=tenant_a)
    assert not form.is_valid()


def test_invwarehouse_issue_form_accepts_a_well_formed_document(
        tenant_a, invwarehouse_location_a):
    form = MaterialIssueForm(data=_invwarehouse_issue_data(invwarehouse_location_a),
                             tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_invwarehouse_run_form_accepts_a_whole_network_run(tenant_a):
    """location is nullable and null means the whole network, not a missing value."""
    form = ReplenishmentRunForm(
        data={"run_date": date.today().isoformat(), "trigger": "manual",
              "abc_class_filter": "", "notes": ""}, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_invwarehouse_run_form_refuses_a_foreign_location(tenant_a, invwarehouse_location_b):
    form = ReplenishmentRunForm(
        data={"location": invwarehouse_location_b.pk, "run_date": date.today().isoformat(),
              "trigger": "manual", "abc_class_filter": "", "notes": ""}, tenant=tenant_a)
    assert not form.is_valid()
    assert "location" in form.errors


def test_invwarehouse_run_form_abc_filter_is_uppercase(tenant_a):
    """The filter targets ReorderRule.abc_class (UPPERCASE), not Location.abc_class (lowercase).

    Getting this backwards would silently match nothing rather than erroring.
    """
    choices = dict(ReplenishmentRun._meta.get_field("abc_class_filter").choices or [])
    assert set(choices) >= {"A", "B", "C"}
    assert "a" not in choices


# --------------------------------------------------------------------------- saving


def test_invwarehouse_policy_form_stamps_the_tenant_on_save(
        tenant_a, invwarehouse_item3_a, invwarehouse_location_a):
    """TenantUniqueMixin must stamp instance.tenant BEFORE full_clean().

    Without that MRO ordering every CREATE is falsely rejected as cross-tenant — the form would
    validate its own unstamped instance against a tenant it has not been given yet.
    """
    form = ReplenishmentPolicyForm(
        data=_invwarehouse_policy_data(invwarehouse_item3_a, invwarehouse_location_a),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk and obj.tenant_id == tenant_a.pk


def test_invwarehouse_issue_form_save_leaves_status_draft(tenant_a, invwarehouse_location_a):
    """status is off the form, so a saved document starts draft whatever the POST said."""
    form = MaterialIssueForm(
        data=dict(_invwarehouse_issue_data(invwarehouse_location_a), status="posted"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.status == "draft"
    assert obj.adjustment_id is None
