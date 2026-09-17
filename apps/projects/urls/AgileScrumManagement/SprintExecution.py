"""Projects 7.13 Agile & Scrum Management — Sprint Execution URL patterns."""
from django.urls import path

from apps.projects.views.AgileScrumManagement import SprintExecution

urlpatterns = [
    path("agile/execution/", SprintExecution.sprint_execution, name="sprint_execution"),
]
