"""Projects 7.17 — RecurringTaskSchedule URL patterns."""
from django.urls import path

from apps.projects.views.WorkflowAutomation import RecurringTasks as views

urlpatterns = [
    path("recurring/", views.rts_list, name="rts_list"),
    path("recurring/create/", views.rts_create, name="rts_create"),
    path("recurring/<int:pk>/", views.rts_detail, name="rts_detail"),
    path("recurring/<int:pk>/edit/", views.rts_edit, name="rts_edit"),
    path("recurring/<int:pk>/delete/", views.rts_delete, name="rts_delete"),
    path("recurring/<int:pk>/toggle/", views.rts_toggle_active, name="rts_toggle_active"),
    path("recurring/<int:pk>/generate/", views.rts_generate_task, name="rts_generate_task"),
    path("recurring/<int:pk>/skip/", views.rts_skip_next, name="rts_skip_next"),
]
