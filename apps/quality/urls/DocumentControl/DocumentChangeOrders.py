from django.urls import path

from apps.quality.views.DocumentControl.DocumentChangeOrders import (
    document_change_order_ccb_decision,
    document_change_order_create,
    document_change_order_delete,
    document_change_order_detail,
    document_change_order_edit,
    document_change_order_export,
    document_change_order_list,
    document_change_order_submit,
)

urlpatterns = [
    path("change-orders/", document_change_order_list, name="document_change_order_list"),
    path("change-orders/create/", document_change_order_create, name="document_change_order_create"),
    path("change-orders/export/", document_change_order_export, name="document_change_order_export"),
    path("change-orders/<int:pk>/", document_change_order_detail, name="document_change_order_detail"),
    path("change-orders/<int:pk>/edit/", document_change_order_edit, name="document_change_order_edit"),
    path("change-orders/<int:pk>/delete/", document_change_order_delete, name="document_change_order_delete"),
    path("change-orders/<int:pk>/submit/", document_change_order_submit, name="document_change_order_submit"),
    path("change-orders/<int:pk>/ccb-decision/", document_change_order_ccb_decision, name="document_change_order_ccb_decision"),
]
