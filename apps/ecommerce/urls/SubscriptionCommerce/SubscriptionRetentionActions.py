from django.urls import path

from apps.ecommerce.views.SubscriptionCommerce import SubscriptionRetentionActions as views

urlpatterns = [
    path(
        "subscription-retention/",
        views.subscriptionretentionaction_list,
        name="subscriptionretentionaction_list",
    ),
    path(
        "subscription-retention/new/",
        views.subscriptionretentionaction_create,
        name="subscriptionretentionaction_create",
    ),
    path(
        "subscription-retention/<int:pk>/",
        views.subscriptionretentionaction_detail,
        name="subscriptionretentionaction_detail",
    ),
    path(
        "subscription-retention/<int:pk>/edit/",
        views.subscriptionretentionaction_edit,
        name="subscriptionretentionaction_edit",
    ),
    path(
        "subscription-retention/<int:pk>/delete/",
        views.subscriptionretentionaction_delete,
        name="subscriptionretentionaction_delete",
    ),
]
