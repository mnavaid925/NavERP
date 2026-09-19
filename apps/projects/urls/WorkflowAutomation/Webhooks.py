"""Projects 7.17 — ProjectWebhookEndpoint and Delivery URL patterns."""
from django.urls import path

from apps.projects.views.WorkflowAutomation import Webhooks as views

urlpatterns = [
    path("webhooks/", views.pwh_list, name="pwh_list"),
    path("webhooks/create/", views.pwh_create, name="pwh_create"),
    path("webhooks/deliveries/", views.pwh_delivery_list, name="pwh_delivery_list"),
    path("webhooks/deliveries/<int:pk>/", views.pwh_delivery_detail, name="pwh_delivery_detail"),
    path("webhooks/<int:pk>/", views.pwh_detail, name="pwh_detail"),
    path("webhooks/<int:pk>/edit/", views.pwh_edit, name="pwh_edit"),
    path("webhooks/<int:pk>/delete/", views.pwh_delete, name="pwh_delete"),
    path("webhooks/<int:pk>/toggle/", views.pwh_toggle_active, name="pwh_toggle_active"),
    path("webhooks/<int:pk>/test-ping/", views.pwh_test_ping, name="pwh_test_ping"),
    path("webhooks/<int:pk>/rotate-secret/", views.pwh_rotate_secret, name="pwh_rotate_secret"),
]
