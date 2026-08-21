"""Procurement models package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every model so ``from apps.procurement.models import ProcurementAlert`` works
everywhere (admin, seeder, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .DashboardPortal.ProcurementAlerts import ProcurementAlert
from .DashboardPortal.WidgetPreferences import WidgetPreference

__all__ = ["ProcurementAlert", "WidgetPreference"]
