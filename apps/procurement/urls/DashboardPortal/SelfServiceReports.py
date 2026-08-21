"""Procurement 6.1 User Dashboard & Portal — Self-Service Reporting routes (prefix ``reports/``)."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("reports/", views.report_index, name="report_index"),
    path("reports/export/", views.report_export, name="report_export"),
]
