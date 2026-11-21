from django.urls import path

from apps.quality.views.DataIntegrity import DataIntegrityAssessments as views

urlpatterns = [
    path("assessments/", views.data_integrity_assessment_list, name="data_integrity_assessment_list"),
    path("assessments/create/", views.data_integrity_assessment_create, name="data_integrity_assessment_create"),
    path("assessments/<int:pk>/", views.data_integrity_assessment_detail, name="data_integrity_assessment_detail"),
    path("assessments/<int:pk>/edit/", views.data_integrity_assessment_edit, name="data_integrity_assessment_edit"),
    path("assessments/<int:pk>/delete/", views.data_integrity_assessment_delete, name="data_integrity_assessment_delete"),
]
