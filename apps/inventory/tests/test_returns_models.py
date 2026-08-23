"""Inventory 5.10 Returns Management — model unit tests."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.inventory.models import (
    DispositionRoutingRule,
    ReturnInspection,
    ReturnInspectionChecklist,
    resolve_disposition_routing,
)

pytestmark = pytest.mark.django_db


def test_return_inspection_auto_number(tenant_a, rma_a, rma_line_a, item_a):
    """ReturnInspection auto-assigns human-readable RMI-##### number in save()."""
    inspection = ReturnInspection.objects.create(
        tenant=tenant_a,
        return_authorization=rma_a,
        return_line=rma_line_a,
        item=item_a,
        quantity=Decimal("1.0000"),
        condition_grade="a",
    )
    assert inspection.number.startswith("RMI-")
    assert str(inspection) == f"{inspection.number} ({item_a.sku} × 1.0000)"


def test_return_inspection_cross_tenant_validation(tenant_a, tenant_b, rma_a, rma_line_a, item_b):
    """ReturnInspection rejects cross-tenant item via clean()."""
    inspection = ReturnInspection(
        tenant=tenant_a,
        return_authorization=rma_a,
        return_line=rma_line_a,
        item=item_b,  # Foreign tenant B item
        quantity=Decimal("1.0000"),
        condition_grade="a",
    )
    with pytest.raises(ValidationError) as excinfo:
        inspection.clean()
    assert "item" in excinfo.value.message_dict


def test_return_inspection_checklist_creation(tenant_a, inspection_a):
    """Checklist items attach to inspection and validate result choices."""
    ck = ReturnInspectionChecklist.objects.create(
        tenant=tenant_a,
        inspection=inspection_a,
        checkpoint="Power-on functional test",
        result="pass",
        notes="Device booted normally",
    )
    assert ck.result == "pass"
    assert str(ck) == "Power-on functional test: Pass"
    assert inspection_a.checklist_items.count() == 1


def test_disposition_routing_rule_resolver_tier_hierarchy(tenant_a, item_a, location_a):
    """Disposition routing resolver gives highest priority to item match over category and catch-all."""
    from apps.scm.models import ItemCategory

    cat = ItemCategory.objects.create(tenant=tenant_a, name="Hardware")
    item_a.category = cat
    item_a.save()

    # Rule 1: Catch-all rule (Priority 10)
    rule_catchall = DispositionRoutingRule.objects.create(
        tenant=tenant_a,
        name="Catch-all Restock",
        condition_grade="a",
        suggested_disposition="restock",
        destination_location=location_a,
        priority=10,
    )

    # Rule 2: Category rule (Priority 20)
    rule_category = DispositionRoutingRule.objects.create(
        tenant=tenant_a,
        name="Hardware Category Refurbish",
        category=cat,
        condition_grade="a",
        suggested_disposition="refurbish",
        destination_location=location_a,
        priority=20,
    )

    # Rule 3: Specific item rule (Priority 30)
    rule_item = DispositionRoutingRule.objects.create(
        tenant=tenant_a,
        name="Item A Special Quarantine",
        item=item_a,
        condition_grade="a",
        suggested_disposition="quarantine",
        destination_location=location_a,
        priority=30,
    )

    # 1. Item match should win (Tier 3) despite higher priority number (30)
    rule, disp, loc, reason = resolve_disposition_routing(item_a, condition_grade="a", tenant=tenant_a)
    assert rule == rule_item
    assert disp == "quarantine"
    assert "item rule" in reason

    # 2. Deleting item rule -> Category rule should win (Tier 2)
    rule_item.delete()
    rule, disp, loc, reason = resolve_disposition_routing(item_a, condition_grade="a", tenant=tenant_a)
    assert rule == rule_category
    assert disp == "refurbish"
    assert "category rule" in reason

    # 3. Deleting category rule -> Catch-all rule should win (Tier 1)
    rule_category.delete()
    rule, disp, loc, reason = resolve_disposition_routing(item_a, condition_grade="a", tenant=tenant_a)
    assert rule == rule_catchall
    assert disp == "restock"
    assert "catch-all rule" in reason
