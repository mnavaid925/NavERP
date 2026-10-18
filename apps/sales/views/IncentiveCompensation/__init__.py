"""Sales 8.10 — IncentiveCompensation views package re-exports."""
from apps.sales.views.IncentiveCompensation.CommissionAdjustments import (
    commission_adjustment_create,
    commission_adjustment_delete,
    commission_adjustment_detail,
    commission_adjustment_edit,
    commission_adjustment_list,
    commission_adjustment_resolve_dispute,
)
from apps.sales.views.IncentiveCompensation.CommissionBoards import (
    sales_commission_adjustment_workbench,
    sales_commission_earnings_dashboard,
    sales_commission_payout_processing,
    sales_commission_plan_hub,
    sales_commission_what_if_calc,
    sales_global_compensation_matrix,
)
from apps.sales.views.IncentiveCompensation.CommissionEarnings import (
    commission_earning_create,
    commission_earning_delete,
    commission_earning_detail,
    commission_earning_edit,
    commission_earning_list,
)
from apps.sales.views.IncentiveCompensation.CommissionPlans import (
    commission_plan_create,
    commission_plan_delete,
    commission_plan_detail,
    commission_plan_edit,
    commission_plan_list,
)
from apps.sales.views.IncentiveCompensation.CommissionStatements import (
    commission_statement_approve,
    commission_statement_create,
    commission_statement_delete,
    commission_statement_detail,
    commission_statement_edit,
    commission_statement_generate_batch,
    commission_statement_list,
    commission_statement_lock,
)

__all__ = [
    # CommissionPlan
    "commission_plan_list",
    "commission_plan_detail",
    "commission_plan_create",
    "commission_plan_edit",
    "commission_plan_delete",
    # CommissionEarning
    "commission_earning_list",
    "commission_earning_detail",
    "commission_earning_create",
    "commission_earning_edit",
    "commission_earning_delete",
    # CommissionStatement
    "commission_statement_list",
    "commission_statement_detail",
    "commission_statement_create",
    "commission_statement_edit",
    "commission_statement_delete",
    "commission_statement_approve",
    "commission_statement_lock",
    "commission_statement_generate_batch",
    # CommissionAdjustment
    "commission_adjustment_list",
    "commission_adjustment_detail",
    "commission_adjustment_create",
    "commission_adjustment_edit",
    "commission_adjustment_delete",
    "commission_adjustment_resolve_dispute",
    # Boards
    "sales_commission_plan_hub",
    "sales_commission_earnings_dashboard",
    "sales_commission_adjustment_workbench",
    "sales_global_compensation_matrix",
    "sales_commission_payout_processing",
    "sales_commission_what_if_calc",
]
