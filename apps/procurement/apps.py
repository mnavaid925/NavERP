"""NavERP Module 6 — Procurement Management System (app config)."""
from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.procurement"
    verbose_name = "Procurement Management"
