"""URL patterns for ProductBundleOption entity."""
from django.urls import path
from apps.sales.views.QuoteProposalCPQ import ProductBundles as views

urlpatterns = [
    path("bundles/", views.product_bundle_list, name="product_bundle_list"),
    path("bundles/create/", views.product_bundle_create, name="product_bundle_create"),
    path("bundles/<int:pk>/", views.product_bundle_detail, name="product_bundle_detail"),
    path("bundles/<int:pk>/edit/", views.product_bundle_edit, name="product_bundle_edit"),
    path("bundles/<int:pk>/delete/", views.product_bundle_delete, name="product_bundle_delete"),
]
