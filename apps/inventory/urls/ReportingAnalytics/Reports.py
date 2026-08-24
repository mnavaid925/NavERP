"""Inventory 5.17 Reporting & Analytics — the four computed report pages.

Literal routes only; nothing greedy, nothing parameterised (the reports read
their windows/filters from GET). Snapshot CRUD lives in its own module.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("reports/valuation/", views.report_valuation, name="report_valuation"),
    path("reports/turnover/", views.report_turnover, name="report_turnover"),
    path("reports/aging/", views.report_aging, name="report_aging"),
    path("reports/abc/", views.report_abc, name="report_abc"),
]
