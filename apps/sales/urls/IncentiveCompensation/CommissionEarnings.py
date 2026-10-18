"""Sales 8.10 — URLs for `CommissionEarning`."""
from django.urls import path

from apps.sales.views.IncentiveCompensation import CommissionEarnings as views

urlpatterns = [
    path("compensation/earnings/", views.commission_earning_list, name="commission_earning_list"),
    path("compensation/earnings/add/", views.commission_earning_create, name="commission_earning_create"),
    path("compensation/earnings/<int:pk>/edit/", views.commission_earning_edit, name="commission_earning_edit"),
    path("compensation/earnings/<int:pk>/delete/", views.commission_earning_delete, name="commission_earning_delete"),
    path("compensation/earnings/<int:pk>/", views.commission_earning_detail, name="commission_earning_detail"),
]
