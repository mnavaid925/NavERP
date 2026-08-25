"""Inventory 5.16 Alerts & Notifications — alert inbox URL patterns."""
from django.urls import path

from apps.inventory.views.AlertsNotifications.InventoryAlerts import (
    alert_acknowledge,
    alert_detail,
    alert_list,
    alert_resolve,
    alert_run_detection,
)

urlpatterns = [
    path("alerts/", alert_list, name="alert_list"),
    path("alerts/run-detection/", alert_run_detection, name="alert_run_detection"),
    path("alerts/<int:pk>/", alert_detail, name="alert_detail"),
    path("alerts/<int:pk>/acknowledge/", alert_acknowledge, name="alert_acknowledge"),
    path("alerts/<int:pk>/resolve/", alert_resolve, name="alert_resolve"),
]
