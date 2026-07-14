"""Accounting 2.3 Accounts Payable — VendorProfiles URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.3 AP — Vendor profiles
    path("vendor-profiles/", views.vendor_profile_list, name="vendor_profile_list"),
    path("vendor-profiles/add/", views.vendor_profile_create, name="vendor_profile_create"),
    path("vendor-profiles/<int:pk>/", views.vendor_profile_detail, name="vendor_profile_detail"),
    path("vendor-profiles/<int:pk>/edit/", views.vendor_profile_edit, name="vendor_profile_edit"),
    path("vendor-profiles/<int:pk>/delete/", views.vendor_profile_delete, name="vendor_profile_delete"),
]
