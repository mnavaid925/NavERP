"""Procurement 6.9 Catalog Management — CatalogPriceTier URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("catalog-tiers/", views.catalog_tier_list, name="catalog_tier_list"),
    path("catalog-tiers/add/", views.catalog_tier_create, name="catalog_tier_create"),
    path("catalog-tiers/<int:pk>/", views.catalog_tier_detail, name="catalog_tier_detail"),
    path("catalog-tiers/<int:pk>/edit/", views.catalog_tier_edit, name="catalog_tier_edit"),
    path("catalog-tiers/<int:pk>/delete/", views.catalog_tier_delete,
         name="catalog_tier_delete"),
    path("catalog-tiers/<int:pk>/approve/", views.catalog_tier_approve,
         name="catalog_tier_approve"),
    path("catalog-tiers/<int:pk>/retire/", views.catalog_tier_retire,
         name="catalog_tier_retire"),
]
