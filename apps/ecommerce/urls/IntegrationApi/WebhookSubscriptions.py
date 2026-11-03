from django.urls import path
from apps.ecommerce.views.IntegrationApi import WebhookSubscriptions as views

urlpatterns = [
    path("integration-api/webhooks/", views.webhook_subscription_list, name="webhooksubscription_list"),
    path("integration-api/webhooks/create/", views.webhook_subscription_create, name="webhooksubscription_create"),
    path("integration-api/webhooks/<int:pk>/", views.webhook_subscription_detail, name="webhooksubscription_detail"),
    path("integration-api/webhooks/<int:pk>/edit/", views.webhook_subscription_edit, name="webhooksubscription_edit"),
    path("integration-api/webhooks/<int:pk>/delete/", views.webhook_subscription_delete, name="webhooksubscription_delete"),
    path("integration-api/webhooks/<int:pk>/ping/", views.webhook_subscription_ping, name="webhooksubscription_ping"),
]
