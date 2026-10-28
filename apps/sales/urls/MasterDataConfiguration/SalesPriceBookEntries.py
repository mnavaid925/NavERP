"""URL patterns for SalesPriceBookEntry entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration.SalesPriceBookEntries import (
    pbe_create,
    pbe_delete,
    pbe_detail,
    pbe_edit,
    pbe_list,
)

urlpatterns = [
    path("master-data/price-book-entries/", pbe_list, name="pbe_list"),
    path("master-data/price-book-entries/create/", pbe_create, name="pbe_create"),
    path("master-data/price-book-entries/<int:pk>/", pbe_detail, name="pbe_detail"),
    path("master-data/price-book-entries/<int:pk>/edit/", pbe_edit, name="pbe_edit"),
    path("master-data/price-book-entries/<int:pk>/delete/", pbe_delete, name="pbe_delete"),
]
