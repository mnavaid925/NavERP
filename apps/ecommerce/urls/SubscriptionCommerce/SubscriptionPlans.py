from django.urls import path

from apps.ecommerce.views.SubscriptionCommerce import SubscriptionPlans as views

urlpatterns = [
    path(
        "subscription-plans/",
        views.subscriptionplan_list,
        name="subscriptionplan_list",
    ),
    path(
        "subscription-plans/new/",
        views.subscriptionplan_create,
        name="subscriptionplan_create",
    ),
    path(
        "subscription-plans/<int:pk>/",
        views.subscriptionplan_detail,
        name="subscriptionplan_detail",
    ),
    path(
        "subscription-plans/<int:pk>/edit/",
        views.subscriptionplan_edit,
        name="subscriptionplan_edit",
    ),
    path(
        "subscription-plans/<int:pk>/delete/",
        views.subscriptionplan_delete,
        name="subscriptionplan_delete",
    ),
]
