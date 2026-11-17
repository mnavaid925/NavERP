from django.urls import path

from apps.quality.views.RiskManagement.RiskReviewRecords import (
    risk_review_record_approve,
    risk_review_record_create,
    risk_review_record_delete,
    risk_review_record_detail,
    risk_review_record_edit,
    risk_review_record_export,
    risk_review_record_list,
)

urlpatterns = [
    path("risk-reviews/", risk_review_record_list, name="risk_review_record_list"),
    path("risk-reviews/create/", risk_review_record_create, name="risk_review_record_create"),
    path("risk-reviews/export/", risk_review_record_export, name="risk_review_record_export"),
    path("risk-reviews/<int:pk>/", risk_review_record_detail, name="risk_review_record_detail"),
    path("risk-reviews/<int:pk>/edit/", risk_review_record_edit, name="risk_review_record_edit"),
    path("risk-reviews/<int:pk>/delete/", risk_review_record_delete, name="risk_review_record_delete"),
    path("risk-reviews/<int:pk>/approve/", risk_review_record_approve, name="risk_review_record_approve"),
]
