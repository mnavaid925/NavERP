"""Projects 7.2 — ScheduleBaseline routes (prefix ``baselines/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("baselines/", views.bsl_list, name="bsl_list"),
    path("baselines/add/", views.bsl_create, name="bsl_create"),
    path("baselines/<int:pk>/", views.bsl_detail, name="bsl_detail"),
    path("baselines/<int:pk>/edit/", views.bsl_edit, name="bsl_edit"),
    path("baselines/<int:pk>/delete/", views.bsl_delete, name="bsl_delete"),
    path("baselines/<int:pk>/activate/", views.bsl_activate, name="bsl_activate"),
    path("baselines/<int:pk>/promote/", views.bsl_promote, name="bsl_promote"),
]
