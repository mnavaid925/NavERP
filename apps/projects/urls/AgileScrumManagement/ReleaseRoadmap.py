"""Projects 7.13 Agile & Scrum Management — Release Roadmap URL patterns."""
from django.urls import path

from apps.projects.views.AgileScrumManagement import ReleaseRoadmap

urlpatterns = [
    path("agile/roadmap/", ReleaseRoadmap.release_roadmap, name="release_roadmap"),
]
