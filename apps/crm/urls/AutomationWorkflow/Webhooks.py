"""CRM 1.10 Automation & Workflow Engine — Webhooks URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Webhooks + deliveries (1.10)
    path("webhooks/", views.webhook_list, name="webhook_list"),
    path("webhooks/add/", views.webhook_create, name="webhook_create"),
    path("webhooks/<int:pk>/", views.webhook_detail, name="webhook_detail"),
    path("webhooks/<int:pk>/edit/", views.webhook_edit, name="webhook_edit"),
    path("webhooks/<int:pk>/delete/", views.webhook_delete, name="webhook_delete"),
    path("webhooks/<int:pk>/test/", views.webhook_test, name="webhook_test"),
    path("webhook-deliveries/", views.webhookdelivery_list, name="webhookdelivery_list"),
    path("webhook-deliveries/<int:pk>/", views.webhookdelivery_detail, name="webhookdelivery_detail"),
]
