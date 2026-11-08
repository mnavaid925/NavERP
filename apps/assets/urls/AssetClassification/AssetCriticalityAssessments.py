from django.urls import path

from apps.assets.views.AssetClassification.AssetCriticalityAssessments import (
    asset_criticality_assessment_approve,
    asset_criticality_assessment_create,
    asset_criticality_assessment_delete,
    asset_criticality_assessment_detail,
    asset_criticality_assessment_edit,
    asset_criticality_assessment_list,
)

urlpatterns = [
    path("classification/criticality-assessments/", asset_criticality_assessment_list, name="asset_criticality_assessment_list"),
    path("classification/criticality-assessments/create/", asset_criticality_assessment_create, name="asset_criticality_assessment_create"),
    path("classification/criticality-assessments/<int:pk>/", asset_criticality_assessment_detail, name="asset_criticality_assessment_detail"),
    path("classification/criticality-assessments/<int:pk>/edit/", asset_criticality_assessment_edit, name="asset_criticality_assessment_edit"),
    path("classification/criticality-assessments/<int:pk>/delete/", asset_criticality_assessment_delete, name="asset_criticality_assessment_delete"),
    path("classification/criticality-assessments/<int:pk>/approve/", asset_criticality_assessment_approve, name="asset_criticality_assessment_approve"),
]
