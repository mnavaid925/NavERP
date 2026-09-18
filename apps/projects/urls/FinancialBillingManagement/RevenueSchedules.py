"""Projects 7.15 Financial & Billing Management — ProjectRevenueSchedule URLs.
"""
from django.urls import path

from apps.projects.views.FinancialBillingManagement import RevenueSchedules as views

urlpatterns = [
    path("financial/revenue-schedules/", views.prs_list, name="prs_list"),
    path("financial/revenue-schedules/create/", views.prs_create, name="prs_create"),
    path("financial/revenue-schedules/<int:pk>/", views.prs_detail, name="prs_detail"),
    path("financial/revenue-schedules/<int:pk>/edit/", views.prs_edit, name="prs_edit"),
    path("financial/revenue-schedules/<int:pk>/delete/", views.prs_delete, name="prs_delete"),
    path("financial/revenue-schedules/<int:pk>/approve/", views.prs_approve, name="prs_approve"),
    path("financial/revenue-schedules/<int:pk>/recognize/", views.prs_recognize, name="prs_recognize"),
    path("financial/revenue-schedules/<int:pk>/lock/", views.prs_lock, name="prs_lock"),
]
