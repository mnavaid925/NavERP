"""Accounting 2.6 Fixed Assets — AssetDisposals URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("asset-disposals/", views.asset_disposal_list, name="asset_disposal_list"),
    path("asset-disposals/add/", views.asset_disposal_create, name="asset_disposal_create"),
    path("asset-disposals/<int:pk>/", views.asset_disposal_detail, name="asset_disposal_detail"),
    path("asset-disposals/<int:pk>/edit/", views.asset_disposal_edit, name="asset_disposal_edit"),
    path("asset-disposals/<int:pk>/delete/", views.asset_disposal_delete, name="asset_disposal_delete"),
    path("asset-disposals/<int:pk>/post/", views.asset_disposal_post, name="asset_disposal_post"),
]
