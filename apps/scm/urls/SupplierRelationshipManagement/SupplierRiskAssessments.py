"""SCM 4.2 SRM — SupplierRiskAssessment URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("risk-assessments/", views.riskassessment_list, name="riskassessment_list"),
    path("risk-assessments/add/", views.riskassessment_create, name="riskassessment_create"),
    path("risk-assessments/<int:pk>/", views.riskassessment_detail, name="riskassessment_detail"),
    path("risk-assessments/<int:pk>/edit/", views.riskassessment_edit, name="riskassessment_edit"),
    path("risk-assessments/<int:pk>/delete/", views.riskassessment_delete, name="riskassessment_delete"),
    path("risk-assessments/<int:pk>/submit/", views.riskassessment_submit, name="riskassessment_submit"),
    path("risk-assessments/<int:pk>/review/", views.riskassessment_review, name="riskassessment_review"),
]
