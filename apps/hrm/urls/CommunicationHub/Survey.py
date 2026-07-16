"""HRM 3.27 Communication Hub — Survey URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Surveys
    path("surveys/", views.survey_list, name="survey_list"),
    path("surveys/add/", views.survey_create, name="survey_create"),
    path("surveys/<int:pk>/", views.survey_detail, name="survey_detail"),
    path("surveys/<int:pk>/edit/", views.survey_edit, name="survey_edit"),
    path("surveys/<int:pk>/delete/", views.survey_delete, name="survey_delete"),
    path("surveys/<int:pk>/open/", views.survey_open, name="survey_open"),
    path("surveys/<int:pk>/close/", views.survey_close, name="survey_close"),
    path("surveys/<int:pk>/respond/", views.survey_respond, name="survey_respond"),
    path("surveys/<int:pk>/results/", views.survey_results, name="survey_results"),
]
