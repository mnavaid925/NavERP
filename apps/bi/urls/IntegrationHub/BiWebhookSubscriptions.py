from django.urls import path

from apps.bi.views.IntegrationHub import BiWebhookSubscriptions as views

urlpatterns = [
    path("integrations/webhooks/", views.bi_webhook_subscription_list, name="bi_webhook_subscription_list"),
    path("integrations/webhooks/create/", views.bi_webhook_subscription_create, name="bi_webhook_subscription_create"),
    path("integrations/webhooks/<int:pk>/", views.bi_webhook_subscription_detail, name="bi_webhook_subscription_detail"),
    path("integrations/webhooks/<int:pk>/edit/", views.bi_webhook_subscription_edit, name="bi_webhook_subscription_edit"),
    path("integrations/webhooks/<int:pk>/delete/", views.bi_webhook_subscription_delete, name="bi_webhook_subscription_delete"),
    path("integrations/webhooks/<int:pk>/ping/", views.bi_webhook_subscription_ping, name="bi_webhook_subscription_ping"),
]
