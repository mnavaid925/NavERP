"""HRM 3.41 Employee Engagement & Wellbeing — Wellbeingparticipation URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("engagement/wellbeing/programs/<int:program_pk>/participations/add/",
         views.wellbeingparticipation_add, name="wellbeingparticipation_add"),
    path("engagement/wellbeing/programs/<int:program_pk>/participations/<int:pk>/edit/",
         views.wellbeingparticipation_edit, name="wellbeingparticipation_edit"),
    path("engagement/wellbeing/programs/<int:program_pk>/participations/<int:pk>/delete/",
         views.wellbeingparticipation_delete, name="wellbeingparticipation_delete"),
]
