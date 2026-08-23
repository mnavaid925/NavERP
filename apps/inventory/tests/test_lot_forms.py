"""Inventory 5.8 Lot & Serial Number Tracking — form boundary.

Every tenant-scoped FK is re-checked at the boundary (``_reject_foreign``), the policy
form steers to tracked SKUs and refuses an amber window narrower than its own red
gate, and the mint form's item queryset only ever offers this workspace's tracked SKUs.
"""
import datetime

import pytest
from django.utils import timezone

from apps.inventory.forms import (
    GenerateLotForm,
    LotNumberRuleForm,
    ShelfLifePolicyForm,
)

pytestmark = pytest.mark.django_db


def test_lot_rule_form_fields_whitelist(tenant_a):
    assert LotNumberRuleForm(tenant=tenant_a).fields.keys() >= {
        "name", "item", "kind", "prefix", "include_date",
        "sequence_padding", "is_active", "notes"}
    assert "tenant" not in LotNumberRuleForm(tenant=tenant_a).fields


def test_lot_rule_form_rejects_foreign_item(tenant_a, tracked_item_b):
    form = LotNumberRuleForm(
        {"name": "Foreign", "item": tracked_item_b.pk, "kind": "lot",
         "prefix": "FRN", "include_date": "on", "sequence_padding": 3},
        tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors


def test_lot_rule_form_catches_duplicate_name(db, tenant_a, lot_rule_default_a):
    """A second default rule re-using an existing (tenant, name) pair is refused."""
    form = LotNumberRuleForm(
        {"name": "Default batch numbering", "item": "", "kind": "lot",
         "prefix": "LOT2", "include_date": "", "sequence_padding": 4},
        tenant=tenant_a)
    assert not form.is_valid()          # (tenant, name) unique_together fires…
    # …and lands on __all__, because tenant is not a form field for the error to key on.
    assert "__all__" in form.errors


def test_shelf_policy_form_fields_and_foreign_rejection(tenant_a, tracked_item_b):
    form = ShelfLifePolicyForm(
        {"item": tracked_item_b.pk, "shelf_life_days": "180",
         "min_remaining_days": "14", "warning_days": "45"},
        tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors


def test_shelf_policy_form_window_must_reach_past_gate(
        tenant_a, tracked_item_a, shelf_policy_a):
    form = ShelfLifePolicyForm(
        {"item": shelf_policy_a.item_id, "min_remaining_days": "30",
         "warning_days": "10"}, instance=shelf_policy_a, tenant=tenant_a)
    assert not form.is_valid()


def test_shelf_policy_form_offers_only_tracked_items(
        tenant_a, tracked_item_a, item_a, shelf_policy_a):
    queryset = ShelfLifePolicyForm(tenant=tenant_a).fields["item"].queryset
    values = set(queryset.values_list("pk", flat=True))
    assert tracked_item_a.pk in values
    assert item_a.pk not in values      # tracking="none" — nothing to age


def test_generate_form_scopes_to_tenant_tracked_items(
        client_a, tenant_a, tracked_item_a, item_a):
    response = client_a.get("/inventory/lot-generate/")
    assert response.status_code == 200
    form = GenerateLotForm(tenant=tenant_a)
    values = set(form.fields["item"].queryset.values_list("pk", flat=True))
    assert tracked_item_a.pk in values and item_a.pk not in values


def test_generate_form_future_expiry_accepted(tenant_a, tracked_item_a):
    soon = (timezone.localdate() + datetime.timedelta(days=60)).isoformat()
    form = GenerateLotForm({"item": tracked_item_a.pk, "expiry_date": soon},
                           tenant=tenant_a)
    assert form.is_valid(), form.errors
