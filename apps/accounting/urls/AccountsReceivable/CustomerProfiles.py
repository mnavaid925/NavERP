"""Accounting 2.4 Accounts Receivable — CustomerProfiles URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.4 AR — Customer profiles
    path("customer-profiles/", views.customer_profile_list, name="customer_profile_list"),
    path("customer-profiles/add/", views.customer_profile_create, name="customer_profile_create"),
    path("customer-profiles/<int:pk>/", views.customer_profile_detail, name="customer_profile_detail"),
    path("customer-profiles/<int:pk>/edit/", views.customer_profile_edit, name="customer_profile_edit"),
    path("customer-profiles/<int:pk>/delete/", views.customer_profile_delete, name="customer_profile_delete"),
]
