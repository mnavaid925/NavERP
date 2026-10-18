"""Sales 8.10 — URLs for `CommissionPlan`."""
from django.urls import path

from apps.sales.views.IncentiveCompensation import CommissionPlans as views

urlpatterns = [
    path("compensation/plans/", views.commission_plan_list, name="commission_plan_list"),
    path("compensation/plans/add/", views.commission_plan_create, name="commission_plan_create"),
    path("compensation/plans/<int:pk>/edit/", views.commission_plan_edit, name="commission_plan_edit"),
    path("compensation/plans/<int:pk>/delete/", views.commission_plan_delete, name="commission_plan_delete"),
    path("compensation/plans/<int:pk>/", views.commission_plan_detail, name="commission_plan_detail"),
]
