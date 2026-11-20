from django.urls import path

from apps.quality.views.ManagementReview import ManagementReviewInputs as views

urlpatterns = [
    path("inputs/", views.management_review_input_list, name="management_review_input_list"),
    path("inputs/create/", views.management_review_input_create, name="management_review_input_create"),
    path("inputs/export/csv/", views.management_review_input_export_csv, name="management_review_input_export_csv"),
    path("inputs/<int:pk>/", views.management_review_input_detail, name="management_review_input_detail"),
    path("inputs/<int:pk>/edit/", views.management_review_input_edit, name="management_review_input_edit"),
    path("inputs/<int:pk>/delete/", views.management_review_input_delete, name="management_review_input_delete"),
    path("inputs/<int:pk>/present/", views.management_review_input_present, name="management_review_input_present"),
    path("inputs/<int:pk>/accept/", views.management_review_input_accept, name="management_review_input_accept"),
]
