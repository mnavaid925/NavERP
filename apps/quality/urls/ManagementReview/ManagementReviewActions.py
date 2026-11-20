from django.urls import path

from apps.quality.views.ManagementReview import ManagementReviewActions as views

urlpatterns = [
    path("actions/", views.management_review_action_list, name="management_review_action_list"),
    path("actions/create/", views.management_review_action_create, name="management_review_action_create"),
    path("actions/export/csv/", views.management_review_action_export_csv, name="management_review_action_export_csv"),
    path("actions/<int:pk>/", views.management_review_action_detail, name="management_review_action_detail"),
    path("actions/<int:pk>/edit/", views.management_review_action_edit, name="management_review_action_edit"),
    path("actions/<int:pk>/delete/", views.management_review_action_delete, name="management_review_action_delete"),
    path("actions/<int:pk>/start/", views.management_review_action_start, name="management_review_action_start"),
    path("actions/<int:pk>/complete/", views.management_review_action_complete, name="management_review_action_complete"),
    path("actions/<int:pk>/verify/", views.management_review_action_verify, name="management_review_action_verify"),
    path("actions/<int:pk>/escalate-capa/", views.management_review_action_escalate_capa, name="management_review_action_escalate_capa"),
]
