"""SCM module landing page — URL pattern."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("", views.overview, name="overview"),
]
