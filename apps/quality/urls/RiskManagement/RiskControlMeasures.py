from django.urls import path

from apps.quality.views.RiskManagement.RiskControlMeasures import (
    risk_control_measure_create,
    risk_control_measure_delete,
    risk_control_measure_detail,
    risk_control_measure_edit,
    risk_control_measure_export,
    risk_control_measure_list,
    risk_control_measure_verify_eff,
    risk_control_measure_verify_impl,
)

urlpatterns = [
    path("risk-controls/", risk_control_measure_list, name="risk_control_measure_list"),
    path("risk-controls/create/", risk_control_measure_create, name="risk_control_measure_create"),
    path("risk-controls/export/", risk_control_measure_export, name="risk_control_measure_export"),
    path("risk-controls/<int:pk>/", risk_control_measure_detail, name="risk_control_measure_detail"),
    path("risk-controls/<int:pk>/edit/", risk_control_measure_edit, name="risk_control_measure_edit"),
    path("risk-controls/<int:pk>/delete/", risk_control_measure_delete, name="risk_control_measure_delete"),
    path(
        "risk-controls/<int:pk>/verify-implementation/",
        risk_control_measure_verify_impl,
        name="risk_control_measure_verify_impl",
    ),
    path(
        "risk-controls/<int:pk>/verify-effectiveness/",
        risk_control_measure_verify_eff,
        name="risk_control_measure_verify_eff",
    ),
]
