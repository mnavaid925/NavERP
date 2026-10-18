"""Sales 8.10 — URLs for `CommissionAdjustment`."""
from django.urls import path

from apps.sales.views.IncentiveCompensation import CommissionAdjustments as views

urlpatterns = [
    path("compensation/adjustments/", views.commission_adjustment_list, name="commission_adjustment_list"),
    path("compensation/adjustments/add/", views.commission_adjustment_create, name="commission_adjustment_create"),
    path("compensation/adjustments/<int:pk>/edit/", views.commission_adjustment_edit, name="commission_adjustment_edit"),
    path("compensation/adjustments/<int:pk>/delete/", views.commission_adjustment_delete, name="commission_adjustment_delete"),
    path("compensation/adjustments/<int:pk>/resolve-dispute/", views.commission_adjustment_resolve_dispute, name="commission_adjustment_resolve_dispute"),
    path("compensation/adjustments/<int:pk>/", views.commission_adjustment_detail, name="commission_adjustment_detail"),
]
