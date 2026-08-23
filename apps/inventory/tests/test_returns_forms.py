"""Inventory 5.10 Returns Management — form unit tests."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.inventory.forms import (
    DispositionRoutingRuleForm,
    ReturnInspectionChecklistForm,
    ReturnInspectionForm,
)
from apps.inventory.models import DispositionRoutingRule, ReturnInspection

pytestmark = pytest.mark.django_db


def test_return_inspection_form_valid(tenant_a, rma_a, rma_line_a, item_a):
    """ReturnInspectionForm accepts valid data and auto-scopes to tenant."""
    form_data = {
        "return_authorization": rma_a.pk,
        "return_line": rma_line_a.pk,
        "item": item_a.pk,
        "quantity": "2.0000",
        "inspected_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "packaging_condition": "intact",
        "completeness": "complete",
        "functional_status": "pass",
        "cosmetic_condition": "new",
        "condition_grade": "a",
        "serial_verified": True,
        "is_restock_eligible": True,
        "suggested_restock_fee_pct": "0.00",
        "status": "passed",
    }
    form = ReturnInspectionForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    inspection = form.save(commit=False)
    inspection.tenant = tenant_a
    inspection.save()
    assert inspection.pk is not None


def test_return_inspection_form_rejects_foreign_fk(tenant_a, tenant_b, rma_a, item_b):
    """ReturnInspectionForm rejects cross-tenant item via _reject_foreign."""
    form_data = {
        "return_authorization": rma_a.pk,
        "item": item_b.pk,  # Foreign tenant B
        "quantity": "1.0000",
        "packaging_condition": "intact",
        "completeness": "complete",
        "functional_status": "pass",
        "cosmetic_condition": "new",
        "condition_grade": "a",
        "status": "passed",
    }
    form = ReturnInspectionForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors


def test_disposition_routing_rule_form_valid(tenant_a, item_a, location_a):
    """DispositionRoutingRuleForm validates and saves rule."""
    form_data = {
        "name": "Test Restock Rule",
        "item": item_a.pk,
        "condition_grade": "a",
        "suggested_disposition": "restock",
        "destination_location": location_a.pk,
        "priority": 15,
        "is_active": True,
        "requires_supervisor_approval": False,
        "notes": "Test notes",
    }
    form = DispositionRoutingRuleForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rule = form.save(commit=False)
    rule.tenant = tenant_a
    rule.save()
    assert rule.pk is not None
