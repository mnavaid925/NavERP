from django.urls import path

from apps.ecommerce.views.SubscriptionCommerce import SubscriptionPortals as views

urlpatterns = [
    path(
        "subscription-portal/",
        views.subscription_portal,
        name="subscription_portal",
    ),
    path(
        "subscription-portal/<int:pk>/skip/",
        views.subscription_portal_skip,
        name="subscription_portal_skip",
    ),
    path(
        "subscription-portal/<int:pk>/pause/",
        views.subscription_portal_pause,
        name="subscription_portal_pause",
    ),
    path(
        "subscription-portal/<int:pk>/resume/",
        views.subscription_portal_resume,
        name="subscription_portal_resume",
    ),
    path(
        "subscription-portal/<int:pk>/deflect/",
        views.subscription_portal_deflect,
        name="subscription_portal_deflect",
    ),
]
