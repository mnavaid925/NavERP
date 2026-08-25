"""Inventory 5.16 Alerts & Notifications — AlertRule URL patterns."""
from django.urls import path

from apps.inventory.views.AlertsNotifications.AlertRules import (
    alertrule_create,
    alertrule_delete,
    alertrule_detail,
    alertrule_edit,
    alertrule_list,
)

urlpatterns = [
    path("alerts/rules/", alertrule_list, name="alertrule_list"),
    path("alerts/rules/add/", alertrule_create, name="alertrule_create"),
    path("alerts/rules/<int:pk>/", alertrule_detail, name="alertrule_detail"),
    path("alerts/rules/<int:pk>/edit/", alertrule_edit, name="alertrule_edit"),
    path("alerts/rules/<int:pk>/delete/", alertrule_delete, name="alertrule_delete"),
]
