"""SCM 4.5 Order Management System — SalesOrder routes.

**The prefix is `sales-orders/`, NOT `orders/`.** `PurchaseOrder` already owns `orders/`
(urls/ProcurementManagement/PurchaseOrders.py), both share `app_name="scm"` and one concatenated
urlpatterns list, and Django resolves first-match-wins — so reusing it would have let
`purchaseorder_list` permanently shadow `salesorder_list`.

Literal routes come before `<int:pk>/` ones.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("sales-orders/", views.salesorder_list, name="salesorder_list"),
    path("sales-orders/add/", views.salesorder_create, name="salesorder_create"),
    path("sales-orders/from-quote/<int:quote_pk>/", views.salesorder_create_from_quote,
         name="salesorder_create_from_quote"),
    path("sales-orders/<int:pk>/", views.salesorder_detail, name="salesorder_detail"),
    path("sales-orders/<int:pk>/edit/", views.salesorder_edit, name="salesorder_edit"),
    path("sales-orders/<int:pk>/delete/", views.salesorder_delete, name="salesorder_delete"),
    path("sales-orders/<int:pk>/submit/", views.salesorder_submit, name="salesorder_submit"),
    path("sales-orders/<int:pk>/release-hold/", views.salesorder_release_hold,
         name="salesorder_release_hold"),
    path("sales-orders/<int:pk>/fulfill/", views.salesorder_fulfill, name="salesorder_fulfill"),
    path("sales-orders/<int:pk>/mark-delivered/", views.salesorder_mark_delivered,
         name="salesorder_mark_delivered"),
    path("sales-orders/<int:pk>/mark-invoiced/", views.salesorder_mark_invoiced,
         name="salesorder_mark_invoiced"),
    path("sales-orders/<int:pk>/cancel/", views.salesorder_cancel, name="salesorder_cancel"),
    path("sales-orders/<int:pk>/close/", views.salesorder_close, name="salesorder_close"),
]
