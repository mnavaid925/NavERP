"""SCM 4.3 Inventory Management — StockTransfer URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("transfers/", views.stocktransfer_list, name="stocktransfer_list"),
    path("transfers/add/", views.stocktransfer_create, name="stocktransfer_create"),
    path("transfers/<int:pk>/", views.stocktransfer_detail, name="stocktransfer_detail"),
    path("transfers/<int:pk>/edit/", views.stocktransfer_edit, name="stocktransfer_edit"),
    path("transfers/<int:pk>/delete/", views.stocktransfer_delete, name="stocktransfer_delete"),
    path("transfers/<int:pk>/complete/", views.stocktransfer_complete, name="stocktransfer_complete"),
    path("transfers/<int:pk>/cancel/", views.stocktransfer_cancel, name="stocktransfer_cancel"),
]
