from django.urls import path

from apps.quality.views.RiskManagement.RiskAssessments import (
    risk_assessment_create,
    risk_assessment_delete,
    risk_assessment_detail,
    risk_assessment_edit,
    risk_assessment_export,
    risk_assessment_list,
)

urlpatterns = [
    path("risk-assessments/", risk_assessment_list, name="risk_assessment_list"),
    path("risk-assessments/create/", risk_assessment_create, name="risk_assessment_create"),
    path("risk-assessments/export/", risk_assessment_export, name="risk_assessment_export"),
    path("risk-assessments/<int:pk>/", risk_assessment_detail, name="risk_assessment_detail"),
    path("risk-assessments/<int:pk>/edit/", risk_assessment_edit, name="risk_assessment_edit"),
    path("risk-assessments/<int:pk>/delete/", risk_assessment_delete, name="risk_assessment_delete"),
]
