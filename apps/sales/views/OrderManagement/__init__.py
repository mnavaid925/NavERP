"""Sales 8.6 Order Management — the four entity view modules plus the board module.

Public view functions only; the private ``_`` helpers stay inside their own module, where the
entity that owns them can read them. Every view is ``@login_required`` +
``@tenant_admin_required`` and every queryset is scoped with
``Model.objects.filter(tenant=request.tenant)`` — never ``.objects.all()``. The tenantless
superuser therefore sees empty lists BY DESIGN.

**The single-writer rule is enforced from here, not just documented.** No view in this package
writes ``SalesOrder.status``. ``order_hold_*`` writes back only ``credit_hold`` / ``hold_reason``;
``order_hold_clear_and_submit`` delegates to 4.5's own ``salesorder_submit``; ``order_amendment_apply``
delegates to ``OrderAmendment.apply()``, which itself calls 4.5's ``recalc_totals()`` and
``recompute_allocation_status()``. 8.6 posts no ``JournalEntry`` (L29).
"""
from .OrderAmendments import (
    order_amendment_apply,
    order_amendment_create,
    order_amendment_decide,
    order_amendment_delete,
    order_amendment_detail,
    order_amendment_edit,
    order_amendment_impact,
    order_amendment_line_add,
    order_amendment_line_delete,
    order_amendment_line_edit,
    order_amendment_list,
    order_amendment_open_queue,
    order_amendment_withdraw,
)
from .OrderHolds import (
    order_hold_bulk_clear,
    order_hold_bulk_raise,
    order_hold_checkout,
    order_hold_clear,
    order_hold_clear_and_submit,
    order_hold_create,
    order_hold_delete,
    order_hold_detail,
    order_hold_edit,
    order_hold_list,
    order_hold_raise,
    order_hold_release_checkout,
)
from .OrderValidationRules import (
    order_validation_rule_create,
    order_validation_rule_delete,
    order_validation_rule_detail,
    order_validation_rule_edit,
    order_validation_rule_list,
)
from .RevenueSchedules import (
    revenue_schedule_create,
    revenue_schedule_delete,
    revenue_schedule_detail,
    revenue_schedule_edit,
    revenue_schedule_list,
    revenue_schedule_obligation_add,
    revenue_schedule_obligation_delete,
    revenue_schedule_obligation_edit,
    revenue_schedule_recognize,
)

__all__ = [
    "order_validation_rule_list",
    "order_validation_rule_create",
    "order_validation_rule_detail",
    "order_validation_rule_edit",
    "order_validation_rule_delete",
    "order_hold_list",
    "order_hold_create",
    "order_hold_detail",
    "order_hold_edit",
    "order_hold_delete",
    "order_hold_checkout",
    "order_hold_release_checkout",
    "order_hold_clear",
    "order_hold_clear_and_submit",
    "order_hold_raise",
    "order_hold_bulk_raise",
    "order_hold_bulk_clear",
    "order_amendment_list",
    "order_amendment_create",
    "order_amendment_detail",
    "order_amendment_edit",
    "order_amendment_delete",
    "order_amendment_line_add",
    "order_amendment_line_edit",
    "order_amendment_line_delete",
    "order_amendment_decide",
    "order_amendment_apply",
    "order_amendment_withdraw",
    "order_amendment_open_queue",
    "order_amendment_impact",
    "revenue_schedule_list",
    "revenue_schedule_create",
    "revenue_schedule_detail",
    "revenue_schedule_edit",
    "revenue_schedule_delete",
    "revenue_schedule_obligation_add",
    "revenue_schedule_obligation_edit",
    "revenue_schedule_obligation_delete",
    "revenue_schedule_recognize",
]
