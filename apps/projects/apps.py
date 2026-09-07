"""App config for NavERP Module 7 — Project Management."""
from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"
    verbose_name = "Project Management"
