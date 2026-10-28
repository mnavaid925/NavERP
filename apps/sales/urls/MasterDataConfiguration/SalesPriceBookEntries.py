"""URL patterns for SalesPriceBookEntry entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration import SalesPriceBookEntries as views

urlpatterns = [
    path("master-data/price-book-entries/", views.pbe_list, name="pbe_list"),
    path("master-data/price-book-entries/create/", views.pbe_create, name="pbe_create"),
    path("master-data/price-book-entries/<int:pk>/", views.pbe_detail, name="pbe_detail"),
    path("master-data/price-book-entries/<int:pk>/edit/", views.pbe_edit, name="pbe_edit"),
    path("master-data/price-book-entries/<int:pk>/delete/", views.pbe_delete, name="pbe_delete"),
]
