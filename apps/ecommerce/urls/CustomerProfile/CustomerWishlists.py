from django.urls import path

from apps.ecommerce.views.CustomerProfile import CustomerWishlists as views

urlpatterns = [
    path(
        "wishlists/",
        views.customerwishlist_list,
        name="customerwishlist_list",
    ),
    path(
        "wishlists/create/",
        views.customerwishlist_create,
        name="customerwishlist_create",
    ),
    path(
        "wishlists/items/<int:item_pk>/delete/",
        views.customerwishlist_item_delete,
        name="customerwishlist_item_delete",
    ),
    path(
        "wishlists/<int:pk>/",
        views.customerwishlist_detail,
        name="customerwishlist_detail",
    ),
    path(
        "wishlists/<int:pk>/edit/",
        views.customerwishlist_edit,
        name="customerwishlist_edit",
    ),
    path(
        "wishlists/<int:pk>/delete/",
        views.customerwishlist_delete,
        name="customerwishlist_delete",
    ),
    path(
        "wishlists/<int:pk>/items/add/",
        views.customerwishlist_item_add,
        name="customerwishlist_item_add",
    ),
]
