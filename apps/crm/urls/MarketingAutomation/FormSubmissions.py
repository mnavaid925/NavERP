"""CRM 1.3 Marketing Automation — FormSubmissions URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Form submissions (1.3 — web-to-lead captures, read-mostly)
    path("form-submissions/", views.formsubmission_list, name="formsubmission_list"),
    path("form-submissions/<int:pk>/", views.formsubmission_detail, name="formsubmission_detail"),
    path("form-submissions/<int:pk>/delete/", views.formsubmission_delete, name="formsubmission_delete"),
    path("form-submissions/<int:pk>/convert/", views.formsubmission_convert, name="formsubmission_convert"),
]
