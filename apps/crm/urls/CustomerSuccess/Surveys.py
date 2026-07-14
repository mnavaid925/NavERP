"""CRM 1.11 Customer Success & Retention — Surveys URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Surveys (1.11)
    path("surveys/", views.survey_list, name="survey_list"),
    path("surveys/add/", views.survey_create, name="survey_create"),
    path("surveys/results/", views.survey_results, name="survey_results"),
    path("surveys/<int:pk>/", views.survey_detail, name="survey_detail"),
    path("surveys/<int:pk>/send/", views.survey_send, name="survey_send"),
    path("surveys/<int:pk>/edit/", views.survey_edit, name="survey_edit"),
    path("surveys/<int:pk>/delete/", views.survey_delete, name="survey_delete"),
    path("surveys/<str:token>/respond/", views.survey_respond, name="survey_respond"),  # public
]
