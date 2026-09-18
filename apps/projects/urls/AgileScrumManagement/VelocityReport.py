"""Projects 7.13 Agile & Scrum Management — Velocity & Health Report URL patterns."""
from django.urls import path

from apps.projects.views.AgileScrumManagement import VelocityReport

urlpatterns = [
    path("agile/velocity/", VelocityReport.velocity_report, name="velocity_report"),
]
