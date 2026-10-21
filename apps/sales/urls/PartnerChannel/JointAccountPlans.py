"""Sales 8.14 — URLs for `JointAccountPlan`."""
from django.urls import path

from apps.sales.views.PartnerChannel import JointAccountPlans as views

urlpatterns = [
    path("partner-channel/joint-plans/", views.joint_account_plan_list, name="joint_account_plan_list"),
    path("partner-channel/joint-plans/new/", views.joint_account_plan_create, name="joint_account_plan_create"),
    path("partner-channel/joint-plans/create/", views.joint_account_plan_create),
    path("partner-channel/joint-plans/<int:pk>/", views.joint_account_plan_detail, name="joint_account_plan_detail"),
    path("partner-channel/joint-plans/<int:pk>/edit/", views.joint_account_plan_edit, name="joint_account_plan_edit"),
    path("partner-channel/joint-plans/<int:pk>/delete/", views.joint_account_plan_delete, name="joint_account_plan_delete"),
]
