from django.urls import path

from apps.quality.views.RiskManagement.RiskManagementPlans import (
    risk_management_plan_activate,
    risk_management_plan_archive,
    risk_management_plan_create,
    risk_management_plan_delete,
    risk_management_plan_detail,
    risk_management_plan_edit,
    risk_management_plan_export,
    risk_management_plan_list,
)

urlpatterns = [
    path("risk-plans/", risk_management_plan_list, name="risk_management_plan_list"),
    path("risk-plans/create/", risk_management_plan_create, name="risk_management_plan_create"),
    path("risk-plans/export/", risk_management_plan_export, name="risk_management_plan_export"),
    path("risk-plans/<int:pk>/", risk_management_plan_detail, name="risk_management_plan_detail"),
    path("risk-plans/<int:pk>/edit/", risk_management_plan_edit, name="risk_management_plan_edit"),
    path("risk-plans/<int:pk>/delete/", risk_management_plan_delete, name="risk_management_plan_delete"),
    path("risk-plans/<int:pk>/activate/", risk_management_plan_activate, name="risk_management_plan_activate"),
    path("risk-plans/<int:pk>/archive/", risk_management_plan_archive, name="risk_management_plan_archive"),
]
