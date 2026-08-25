"""Inventory 5.16 Alerts & Notifications — NotificationDelivery URL patterns (append-only)."""
from django.urls import path

from apps.inventory.views.AlertsNotifications.NotificationDeliveries import (
    delivery_detail,
    delivery_list,
)

urlpatterns = [
    path("alerts/deliveries/", delivery_list, name="delivery_list"),
    path("alerts/deliveries/<int:pk>/", delivery_detail, name="delivery_detail"),
]
