from django.urls import path

from apps.documents import views

urlpatterns = [
    path("bpm/webhooks/", views.webhook_trigger_list, name="webhook_trigger_list"),
    path("bpm/webhooks/create/", views.webhook_trigger_create, name="webhook_trigger_create"),
    path("bpm/webhooks/<int:pk>/", views.webhook_trigger_detail, name="webhook_trigger_detail"),
    path("bpm/webhooks/<int:pk>/edit/", views.webhook_trigger_edit, name="webhook_trigger_edit"),
    path("bpm/webhooks/<int:pk>/delete/", views.webhook_trigger_delete, name="webhook_trigger_delete"),
    path("bpm/webhooks/<int:pk>/rotate-secret/", views.webhook_trigger_rotate_secret, name="webhook_trigger_rotate_secret"),
    path("bpm/webhooks/<int:pk>/test-ping/", views.webhook_trigger_test_ping, name="webhook_trigger_test_ping"),
    path("bpm/webhooks/<int:pk>/simulate-inbound/", views.webhook_trigger_simulate_inbound, name="webhook_trigger_simulate_inbound"),
]
