"""Projects 7.13 Agile & Scrum Management — Sprint Backlog URL patterns."""
from django.urls import path

from apps.projects.views.AgileScrumManagement import SprintBacklog

urlpatterns = [
    path("agile/backlog/", SprintBacklog.sprint_backlog, name="sprint_backlog"),
]
