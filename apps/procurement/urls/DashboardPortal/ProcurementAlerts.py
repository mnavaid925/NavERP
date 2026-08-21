"""Procurement 6.1 User Dashboard & Portal — ProcurementAlert routes (prefix ``alerts/``)."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("alerts/", views.alert_list, name="alert_list"),
    path("alerts/add/", views.alert_create, name="alert_create"),
    path("alerts/<int:pk>/", views.alert_detail, name="alert_detail"),
    path("alerts/<int:pk>/edit/", views.alert_edit, name="alert_edit"),
    path("alerts/<int:pk>/delete/", views.alert_delete, name="alert_delete"),
    path("alerts/<int:pk>/acknowledge/", views.alert_acknowledge, name="alert_acknowledge"),
    path("alerts/<int:pk>/resolve/", views.alert_resolve, name="alert_resolve"),
]
