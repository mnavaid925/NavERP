"""Sales 8.17 — SalesAlertTrigger URL patterns."""
from django.urls import path

from apps.sales.views.WorkflowProcessAutomation import SalesAlertTriggers as views

urlpatterns = [
    path("alert-triggers/", views.sales_alert_trigger_list, name="sales_alert_trigger_list"),
    path("alert-triggers/create/", views.sales_alert_trigger_create, name="sales_alert_trigger_create"),
    path("alert-triggers/<int:pk>/edit/", views.sales_alert_trigger_edit, name="sales_alert_trigger_edit"),
    path("alert-triggers/<int:pk>/delete/", views.sales_alert_trigger_delete, name="sales_alert_trigger_delete"),
    path("alert-triggers/<int:pk>/", views.sales_alert_trigger_detail, name="sales_alert_trigger_detail"),
]
