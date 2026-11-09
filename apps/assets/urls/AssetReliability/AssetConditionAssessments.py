from django.urls import path

from apps.assets.views.AssetReliability import AssetConditionAssessments as views

urlpatterns = [
    path("reliability/assessments/", views.asset_condition_assessment_list, name="asset_condition_assessment_list"),
    path("reliability/assessments/create/", views.asset_condition_assessment_create, name="asset_condition_assessment_create"),
    path("reliability/assessments/<int:pk>/", views.asset_condition_assessment_detail, name="asset_condition_assessment_detail"),
    path("reliability/assessments/<int:pk>/edit/", views.asset_condition_assessment_edit, name="asset_condition_assessment_edit"),
    path("reliability/assessments/<int:pk>/delete/", views.asset_condition_assessment_delete, name="asset_condition_assessment_delete"),
    path("reliability/assessments/<int:pk>/complete/", views.asset_condition_assessment_complete, name="asset_condition_assessment_complete"),
    path("reliability/assessments/<int:pk>/review/", views.asset_condition_assessment_review, name="asset_condition_assessment_review"),
    path("reliability/assessments/<int:pk>/trigger-request/", views.asset_condition_assessment_trigger_request, name="asset_condition_assessment_trigger_request"),
]
