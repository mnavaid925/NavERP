"""Sales 8.10 — URLs for Incentive Compensation Boards."""
from django.urls import path

from apps.sales.views.IncentiveCompensation import CommissionBoards as views

urlpatterns = [
    path("compensation/plan-hub/", views.sales_commission_plan_hub, name="sales_commission_plan_hub"),
    path("compensation/earnings-dashboard/", views.sales_commission_earnings_dashboard, name="sales_commission_earnings_dashboard"),
    path("compensation/adjustment-workbench/", views.sales_commission_adjustment_workbench, name="sales_commission_adjustment_workbench"),
    path("compensation/global-matrix/", views.sales_global_compensation_matrix, name="sales_global_compensation_matrix"),
    path("compensation/payout-processing/", views.sales_commission_payout_processing, name="sales_commission_payout_processing"),
    path("compensation/what-if/", views.sales_commission_what_if_calc, name="sales_commission_what_if_calc"),
]
