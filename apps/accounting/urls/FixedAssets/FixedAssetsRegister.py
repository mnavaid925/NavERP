"""Accounting 2.6 Fixed Assets — FixedAssetsRegister URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # ===================== Advanced sub-modules 2.6–2.15 =====================
    # 2.6 Fixed Assets
    path("fixed-assets/", views.fixed_asset_list, name="fixed_asset_list"),
    path("fixed-assets/add/", views.fixed_asset_create, name="fixed_asset_create"),
    path("fixed-assets/<int:pk>/", views.fixed_asset_detail, name="fixed_asset_detail"),
    path("fixed-assets/<int:pk>/edit/", views.fixed_asset_edit, name="fixed_asset_edit"),
    path("fixed-assets/<int:pk>/delete/", views.fixed_asset_delete, name="fixed_asset_delete"),
    path("fixed-assets/<int:pk>/depreciate/", views.fixed_asset_depreciate, name="fixed_asset_depreciate"),
]
