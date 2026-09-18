"""Projects 7.15 Financial & Billing Management — FinancialBoards URLs.
"""
from django.urls import path

from apps.projects.views.FinancialBillingManagement import FinancialBoards as views

urlpatterns = [
    path("financial/pnl/", views.financial_pnl, name="financial_pnl"),
    path("financial/variance/", views.financial_variance, name="financial_variance"),
    path("financial/ar-aging/", views.ar_aging, name="ar_aging"),
    path("financial/cash-flow/", views.cash_flow_forecast, name="cash_flow_forecast"),
]
