"""Sales 8.15 — CustomerSubscription URL patterns."""
from django.urls import path

from apps.sales.views.ContractSubscriptionManagement import CustomerSubscriptions as views

urlpatterns = [
    path("subscriptions/", views.customer_subscription_list, name="customer_subscription_list"),
    path("subscriptions/create/", views.customer_subscription_create, name="customer_subscription_create"),
    path("subscriptions/<int:pk>/", views.customer_subscription_detail, name="customer_subscription_detail"),
    path("subscriptions/<int:pk>/edit/", views.customer_subscription_edit, name="customer_subscription_edit"),
    path("subscriptions/<int:pk>/delete/", views.customer_subscription_delete, name="customer_subscription_delete"),
    path("subscriptions/<int:pk>/pause/", views.customer_subscription_pause, name="customer_subscription_pause"),
    path("subscriptions/<int:pk>/resume/", views.customer_subscription_resume, name="customer_subscription_resume"),
    path("subscriptions/<int:pk>/cancel/", views.customer_subscription_cancel, name="customer_subscription_cancel"),
    path("subscriptions/<int:pk>/upgrade/", views.customer_subscription_upgrade, name="customer_subscription_upgrade"),
]
