from django.urls import path

from apps.ecommerce.views.SubscriptionCommerce import CustomerSubscriptions as views

urlpatterns = [
    path(
        "subscriptions/",
        views.customersubscription_list,
        name="customersubscription_list",
    ),
    path(
        "subscriptions/new/",
        views.customersubscription_create,
        name="customersubscription_create",
    ),
    path(
        "subscriptions/<int:pk>/",
        views.customersubscription_detail,
        name="customersubscription_detail",
    ),
    path(
        "subscriptions/<int:pk>/edit/",
        views.customersubscription_edit,
        name="customersubscription_edit",
    ),
    path(
        "subscriptions/<int:pk>/delete/",
        views.customersubscription_delete,
        name="customersubscription_delete",
    ),
]
