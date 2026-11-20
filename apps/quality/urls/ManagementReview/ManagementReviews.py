from django.urls import path

from apps.quality.views.ManagementReview import ManagementReviews as views

urlpatterns = [
    path("reviews/", views.management_review_list, name="management_review_list"),
    path("reviews/create/", views.management_review_create, name="management_review_create"),
    path("reviews/export/csv/", views.management_review_export_csv, name="management_review_export_csv"),
    path("reviews/<int:pk>/", views.management_review_detail, name="management_review_detail"),
    path("reviews/<int:pk>/edit/", views.management_review_edit, name="management_review_edit"),
    path("reviews/<int:pk>/delete/", views.management_review_delete, name="management_review_delete"),
    path("reviews/<int:pk>/start/", views.management_review_start, name="management_review_start"),
    path("reviews/<int:pk>/draft-minutes/", views.management_review_draft_minutes, name="management_review_draft_minutes"),
    path("reviews/<int:pk>/approve/", views.management_review_approve, name="management_review_approve"),
    path("reviews/<int:pk>/cancel/", views.management_review_cancel, name="management_review_cancel"),
    path("reviews/<int:pk>/export/pdf/", views.management_review_export_pdf, name="management_review_export_pdf"),
]
