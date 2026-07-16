"""HRM 3.19 Performance Review — Reviewtemplate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Review templates (form definition per review_type)
    path("review-templates/", views.reviewtemplate_list, name="reviewtemplate_list"),
    path("review-templates/add/", views.reviewtemplate_create, name="reviewtemplate_create"),
    path("review-templates/<int:pk>/", views.reviewtemplate_detail, name="reviewtemplate_detail"),
    path("review-templates/<int:pk>/edit/", views.reviewtemplate_edit, name="reviewtemplate_edit"),
    path("review-templates/<int:pk>/delete/", views.reviewtemplate_delete, name="reviewtemplate_delete"),
]
