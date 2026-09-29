"""Shared record factories and fixtures for the 8.6 Order Management lanes.

Owned by the test-contract step alone; no later lane may edit this file. Following the 8.5
precedent, only fixtures and record factories live here -- no test bodies.

Every helper is ``_ordermanagement_*`` and every fixture ``ordermanagement_*`` so 8.1-8.5 in
this package cannot be shadowed.
"""
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Party, Tenant
from apps.scm.models import SalesOrder, SalesOrderLine
from apps.sales.models import (
    OrderAmendment,
    OrderAmendmentLine,
    OrderHold,
    OrderValidationRule,
    PerformanceObligation,
    RevenueSchedule,
)


# --------------------------------------------------------------------- the 8.6 records


def _ordermanagement_party(tenant, name="Order Test Customer", kind="customer"):
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _ordermanagement_order(tenant, status="submitted", unit_price="100.00", **over):
    """A real SCM 4.5 order to hang 8.6 rows off. 8.6 never creates one itself."""
    party = over.pop("customer", None) or _ordermanagement_party(tenant)
    order = SalesOrder.objects.create(
        tenant=tenant, customer=party, status=status, order_date=timezone.localdate(), **over,
    )
    # 4.5 recomputes totals from its lines, so a line is what makes `total` meaningful.
    SalesOrderLine.objects.create(
        sales_order=order, description="Widget", quantity_ordered=Decimal("10.00"),
        unit_price=Decimal(unit_price), discount_pct=Decimal("0.00"), tax_pct=Decimal("0.00"),
    )
    order.recalc_totals()
    order.refresh_from_db()
    return order


def _ordermanagement_order_line(order, item=None, quantity="10.00", price="100.00"):
    return SalesOrderLine.objects.create(
        sales_order=order, item=item, description="Widget",
        quantity_ordered=Decimal(quantity), unit_price=Decimal(price),
        discount_pct=Decimal("0.00"), tax_pct=Decimal("0.00"),
    )


def _ordermanagement_rule(tenant, name="Credit ceiling", rule_type="order_value",
                          severity="hold", active_on="submit", parameters=None,
                          is_active=True, party=None, priority=10):
    rule = OrderValidationRule(
        tenant=tenant, name=name, rule_type=rule_type, severity=severity,
        active_on=active_on, parameters=parameters if parameters is not None else {},
        is_active=is_active, party=party, priority=priority,
    )
    rule.save()
    return rule


def _ordermanagement_hold(tenant, order, rule=None, hold_type="credit", status="open",
                          severity="hold", reason="Customer is over their credit limit.",
                          snapshot=None, **over):
    hold = OrderHold(
        tenant=tenant, sales_order=order, rule=rule,
        party=over.pop("party", None) or order.customer,
        hold_type=hold_type, status=status, severity=severity, reason=reason,
        evaluation_snapshot=snapshot if snapshot is not None else {
            "rule": rule.number if rule else "manual",
            "rule_type": rule.rule_type if rule else "manual",
            "severity": severity,
            "message": "Seeded evaluation",
            "observed": "1000.00",
            "threshold": "500.00",
        },
        **over,
    )
    hold.save()
    return hold


def _ordermanagement_amendment(tenant, order=None, change_type="quantity", status="draft",
                               reason="Customer doubled the quantity.", **over):
    """An amendment against an SCM order. A default order is created when none is given, so a
    test about the amendment's own state does not have to build an order first."""
    order = order or _ordermanagement_order(tenant, status="submitted")
    amendment = OrderAmendment(
        tenant=tenant, sales_order=order, change_type=change_type, status=status,
        reason=reason, **over,
    )
    amendment.save()
    return amendment


def _ordermanagement_amendment_line(amendment, order_line, operation="update",
                                    new_quantity="20.00", new_unit_price=None):
    line = OrderAmendmentLine(
        amendment=amendment, sales_order_line=order_line, operation=operation,
        new_quantity=Decimal(new_quantity) if new_quantity else None,
        new_unit_price=Decimal(new_unit_price) if new_unit_price else None,
    )
    line.full_clean()
    line.save()
    return line


def _ordermanagement_schedule(tenant, order, status="active", method="over_time",
                              standard="asc606", fiscal_period=None):
    schedule = RevenueSchedule(
        tenant=tenant, sales_order=order, status=status, method=method,
        compliance_standard=standard, fiscal_period=fiscal_period,
    )
    schedule.save()
    return schedule


def _ordermanagement_obligation(tenant, schedule, order_line=None, item=None,
                                 allocation_pct="50.00", recognize_on=None,
                                 obligation_type="goods", description="Goods delivered"):
    obligation = PerformanceObligation(
        schedule=schedule, sales_order_line=order_line, item=item,
        obligation_type=obligation_type, description=description,
        allocation_pct=Decimal(allocation_pct), recognize_on=recognize_on,
    )
    obligation.full_clean()
    obligation.save()
    return obligation


# ------------------------------------------------------------------------- the tenants


@pytest.fixture
def ordermanagement_tenant_a(db):
    return Tenant.objects.create(name="Order Mgmt A", slug="order-mgmt-a")


@pytest.fixture
def ordermanagement_tenant_b(db):
    return Tenant.objects.create(name="Order Mgmt B", slug="order-mgmt-b")


def _ordermanagement_admin(tenant, username):
    return User.objects.create(
        username=username, tenant=tenant, is_tenant_admin=True, is_active=True,
        is_staff=True, password="password",
    )


@pytest.fixture
def ordermanagement_admin_a(ordermanagement_tenant_a):
    return _ordermanagement_admin(ordermanagement_tenant_a, "om_admin_a")


@pytest.fixture
def ordermanagement_admin_b(ordermanagement_tenant_b):
    return _ordermanagement_admin(ordermanagement_tenant_b, "om_admin_b")


@pytest.fixture
def ordermanagement_client_a(db, ordermanagement_admin_a):
    c = Client()
    assert c.login(username=ordermanagement_admin_a.username, password="password")
    return c


@pytest.fixture
def ordermanagement_client_b(db, ordermanagement_admin_b):
    c = Client()
    assert c.login(username=ordermanagement_admin_b.username, password="password")
    return c


# --------------------------------------------------------- 8.6 route names, pinned (L7)


ORDERMANAGEMENT_URL_NAMES = (
    "order_capture_board", "order_fulfillment_board", "order_history_board",
    "order_timeline", "reorder_customers_board", "renewals_due_board",
    "revenue_recognition_board", "order_validate", "order_repeat",
    "order_backorder_resolve",
    "order_validation_rule_list", "order_validation_rule_create",
    "order_validation_rule_detail", "order_validation_rule_edit",
    "order_validation_rule_delete",
    "order_hold_list", "order_hold_create", "order_hold_bulk_raise",
    "order_hold_bulk_clear", "order_hold_raise", "order_hold_detail",
    "order_hold_edit", "order_hold_delete", "order_hold_checkout",
    "order_hold_release_checkout", "order_hold_clear",
    "order_hold_clear_and_submit",
    "order_amendment_list", "order_amendment_create", "order_amendment_open_queue",
    "order_amendment_detail", "order_amendment_edit", "order_amendment_delete",
    "order_amendment_impact", "order_amendment_decide", "order_amendment_apply",
    "order_amendment_withdraw", "order_amendment_line_add",
    "order_amendment_line_edit", "order_amendment_line_delete",
    "revenue_schedule_list", "revenue_schedule_create", "revenue_schedule_detail",
    "revenue_schedule_edit", "revenue_schedule_delete",
    "revenue_schedule_obligation_add", "revenue_schedule_obligation_edit",
    "revenue_schedule_obligation_delete", "revenue_schedule_recognize",
)

#: kwargs needed to reverse a name that takes an argument. The bulk verbs take none.
ORDERMANAGEMENT_URL_KWARGS = {
    "order_timeline": {"pk": 1},
    "order_validate": {"order_pk": 1},
    "order_repeat": {"pk": 1},
    "order_backorder_resolve": {"allocation_pk": 1},
    "order_hold_raise": {"order_id": 1},
    "order_validation_rule_detail": {"pk": 1},
    "order_validation_rule_edit": {"pk": 1},
    "order_validation_rule_delete": {"pk": 1},
    "order_hold_detail": {"pk": 1},
    "order_hold_edit": {"pk": 1},
    "order_hold_delete": {"pk": 1},
    "order_hold_checkout": {"pk": 1},
    "order_hold_release_checkout": {"pk": 1},
    "order_hold_clear": {"pk": 1},
    "order_hold_clear_and_submit": {"pk": 1},
    "order_amendment_detail": {"pk": 1},
    "order_amendment_edit": {"pk": 1},
    "order_amendment_delete": {"pk": 1},
    "order_amendment_impact": {"pk": 1},
    "order_amendment_decide": {"pk": 1},
    "order_amendment_apply": {"pk": 1},
    "order_amendment_withdraw": {"pk": 1},
    "order_amendment_line_add": {"pk": 1},
    "order_amendment_line_edit": {"pk": 1, "line_pk": 1},
    "order_amendment_line_delete": {"pk": 1, "line_pk": 1},
    "revenue_schedule_detail": {"pk": 1},
    "revenue_schedule_edit": {"pk": 1},
    "revenue_schedule_delete": {"pk": 1},
    "revenue_schedule_obligation_add": {"pk": 1},
    "revenue_schedule_obligation_edit": {"pk": 1, "obligation_pk": 1},
    "revenue_schedule_obligation_delete": {"pk": 1, "obligation_pk": 1},
    "revenue_schedule_recognize": {"pk": 1},
}


ORDERMANAGEMENT_CHOICES = {
    "OrderValidationRule": {
        "RULE_TYPE_CHOICES": [
            ("credit_limit", "Credit Limit Exceeded"), ("order_value", "Order Value Ceiling"),
            ("margin_floor", "Margin Floor"), ("discount_ceiling", "Line Discount Ceiling"),
            ("unmapped_item", "Unmapped Item Present"),
            ("missing_ship_to", "Missing Ship-To Address"),
            ("expired_quote", "Source Quote Expired"),
            ("inactive_item", "Inactive Item On Order"),
        ],
        "SEVERITY_CHOICES": [
            ("block", "Block Submission"), ("hold", "Place On Hold"), ("warn", "Warn Only"),
        ],
        "ACTIVE_ON_CHOICES": [
            ("submit", "On Submit"), ("amendment", "On Amendment"),
            ("both", "On Submit And Amendment"),
        ],
    },
    "OrderHold": {
        "HOLD_TYPE_CHOICES": [
            ("credit", "Credit Hold"), ("fraud", "Fraud Review"),
            ("validation", "Validation Failure"), ("manual", "Manual Hold"),
        ],
        "STATUS_CHOICES": [
            ("open", "Open"), ("cleared", "Cleared"), ("superseded", "Superseded"),
        ],
    },
    "OrderAmendment": {
        "CHANGE_TYPE_CHOICES": [
            ("quantity", "Quantity Change"), ("price", "Price Change"),
            ("add_line", "Add Line"), ("remove_line", "Remove Line"),
            ("cancel", "Cancel Order"),
        ],
        "STATUS_CHOICES": [
            ("draft", "Draft"), ("pending", "Pending Approval"), ("approved", "Approved"),
            ("rejected", "Rejected"), ("applied", "Applied"), ("withdrawn", "Withdrawn"),
            ("superseded", "Superseded"),
        ],
    },
    "RevenueSchedule": {
        "STATUS_CHOICES": [
            ("draft", "Draft"), ("active", "Active"), ("complete", "Complete"),
            ("void", "Void"),
        ],
        "METHOD_CHOICES": [
            ("point_in_time", "Point In Time"), ("over_time", "Over Time"),
            ("milestone", "Milestone"),
        ],
        "COMPLIANCE_STANDARD_CHOICES": [
            ("asc606", "ASC 606"), ("ifrs15", "IFRS 15"), ("both", "ASC 606 & IFRS 15"),
        ],
    },
    "PerformanceObligation": {
        "OBLIGATION_TYPE_CHOICES": [
            ("goods", "Goods"), ("services", "Services"), ("subscription", "Subscription"),
            ("milestone", "Milestone"), ("warranty", "Warranty"),
        ],
        "RECOGNITION_METHOD_CHOICES": [
            ("point_in_time", "Point In Time"), ("over_time", "Over Time"),
            ("milestone", "Milestone"),
        ],
    },
}

ORDERMANAGEMENT_MODEL_FIELDS = {
    "OrderValidationRule": (
        "id", "tenant", "created_at", "updated_at", "number", "name", "rule_type",
        "severity", "active_on", "parameters", "party", "priority", "is_active",
        "description",
    ),
    "OrderHold": (
        "id", "tenant", "created_at", "updated_at", "number", "sales_order", "rule",
        "party", "hold_type", "reason", "severity", "status", "evaluation_snapshot",
        "raised_at", "raised_by", "checked_out_by", "checked_out_at", "cleared_by",
        "cleared_at", "clear_note", "superseded_by",
    ),
    "OrderAmendment": (
        "id", "tenant", "created_at", "updated_at", "number", "sales_order",
        "change_type", "status", "reason", "document", "impact_snapshot",
        "requested_by", "requested_at", "decided_by", "decided_at", "decision_note",
        "applied_at", "applied_by", "notes",
    ),
    "OrderAmendmentLine": (
        "id", "amendment", "sales_order_line", "operation", "new_quantity",
        "new_unit_price", "note",
    ),
    "RevenueSchedule": (
        "id", "tenant", "created_at", "updated_at", "number", "sales_order", "status",
        "method", "compliance_standard", "fiscal_period", "journal_entry", "notes",
    ),
    "PerformanceObligation": (
        "id", "schedule", "sales_order_line", "item", "obligation_type", "description",
        "allocation_pct", "recognition_method", "recognize_on", "evidence_reference",
        "allocated_amount", "recognized_amount", "milestone_label",
    ),
}
