"""HRM 3.40 Workforce Planning — Workforcescenario URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("workforce/scenarios/", views.workforcescenario_list, name="workforcescenario_list"),
    path("workforce/scenarios/add/", views.workforcescenario_create, name="workforcescenario_create"),
    path("workforce/scenarios/<int:pk>/", views.workforcescenario_detail, name="workforcescenario_detail"),
    path("workforce/scenarios/<int:pk>/edit/", views.workforcescenario_edit, name="workforcescenario_edit"),
    path("workforce/scenarios/<int:pk>/delete/", views.workforcescenario_delete, name="workforcescenario_delete"),
]
