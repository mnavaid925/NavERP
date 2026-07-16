"""HRM 3.40 Workforce Planning — Employeeskill URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("workforce/skills/", views.employeeskill_list, name="employeeskill_list"),
    path("workforce/skills/add/", views.employeeskill_create, name="employeeskill_create"),
    path("workforce/skills/<int:pk>/", views.employeeskill_detail, name="employeeskill_detail"),
    path("workforce/skills/<int:pk>/edit/", views.employeeskill_edit, name="employeeskill_edit"),
    path("workforce/skills/<int:pk>/delete/", views.employeeskill_delete, name="employeeskill_delete"),
]
