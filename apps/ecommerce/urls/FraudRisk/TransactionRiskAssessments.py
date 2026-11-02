from django.urls import path
from apps.ecommerce.views.FraudRisk import TransactionRiskAssessments as views

urlpatterns = [
    path("fraud-risk/assessments/", views.transaction_risk_assessment_list, name="transaction_risk_assessment_list"),
    path("fraud-risk/assessments/create/", views.transaction_risk_assessment_create, name="transaction_risk_assessment_create"),
    path("fraud-risk/assessments/<int:pk>/", views.transaction_risk_assessment_detail, name="transaction_risk_assessment_detail"),
    path("fraud-risk/assessments/<int:pk>/edit/", views.transaction_risk_assessment_edit, name="transaction_risk_assessment_edit"),
    path("fraud-risk/assessments/<int:pk>/delete/", views.transaction_risk_assessment_delete, name="transaction_risk_assessment_delete"),
]
