"""HRM 3.41 Employee Engagement & Wellbeing — Surveyactionplan URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.41 Employee Engagement & Wellbeing ----------------------------------------------------
    # Literal routes before <int:pk> ones (first-match-wins).
    path("engagement/action-plans/", views.surveyactionplan_list, name="surveyactionplan_list"),
    path("engagement/action-plans/add/", views.surveyactionplan_create, name="surveyactionplan_create"),
    path("engagement/action-plans/<int:pk>/", views.surveyactionplan_detail, name="surveyactionplan_detail"),
    path("engagement/action-plans/<int:pk>/edit/", views.surveyactionplan_edit, name="surveyactionplan_edit"),
    path("engagement/action-plans/<int:pk>/delete/", views.surveyactionplan_delete, name="surveyactionplan_delete"),
]
