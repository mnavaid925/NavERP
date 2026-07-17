"""SCM 4.1 Procurement Management — PurchaseOrders URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("orders/", views.purchaseorder_list, name="purchaseorder_list"),
    path("orders/add/", views.purchaseorder_create, name="purchaseorder_create"),
    path("orders/<int:pk>/", views.purchaseorder_detail, name="purchaseorder_detail"),
    path("orders/<int:pk>/edit/", views.purchaseorder_edit, name="purchaseorder_edit"),
    path("orders/<int:pk>/delete/", views.purchaseorder_delete, name="purchaseorder_delete"),
    path("orders/<int:pk>/amend/", views.purchaseorder_amend, name="purchaseorder_amend"),
    path("orders/<int:pk>/submit/", views.purchaseorder_submit, name="purchaseorder_submit"),
    path("orders/<int:pk>/approve/", views.purchaseorder_approve, name="purchaseorder_approve"),
    path("orders/<int:pk>/send/", views.purchaseorder_send, name="purchaseorder_send"),
    path("orders/<int:pk>/acknowledge/", views.purchaseorder_acknowledge, name="purchaseorder_acknowledge"),
    path("orders/<int:pk>/cancel/", views.purchaseorder_cancel, name="purchaseorder_cancel"),
    path("orders/<int:pk>/close/", views.purchaseorder_close, name="purchaseorder_close"),
]
