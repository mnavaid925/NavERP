from django.urls import path

from apps.ecommerce.views.SubscriptionCommerce import SubscriptionBoxCurations as views

urlpatterns = [
    path(
        "subscription-curations/",
        views.subscriptionboxcuration_list,
        name="subscriptionboxcuration_list",
    ),
    path(
        "subscription-curations/new/",
        views.subscriptionboxcuration_create,
        name="subscriptionboxcuration_create",
    ),
    path(
        "subscription-curations/<int:pk>/",
        views.subscriptionboxcuration_detail,
        name="subscriptionboxcuration_detail",
    ),
    path(
        "subscription-curations/<int:pk>/edit/",
        views.subscriptionboxcuration_edit,
        name="subscriptionboxcuration_edit",
    ),
    path(
        "subscription-curations/<int:pk>/delete/",
        views.subscriptionboxcuration_delete,
        name="subscriptionboxcuration_delete",
    ),
]
