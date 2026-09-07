"""Projects — module landing route (``""``, the app root)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("", views.overview, name="overview"),
]
