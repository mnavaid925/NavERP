"""Procurement forms package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every form so ``from apps.procurement.forms import ProcurementAlertForm`` works
everywhere (views, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .DashboardPortal.ProcurementAlerts import ProcurementAlertForm
from .DashboardPortal.QuickRequisitions import QuickRequisitionForm
from .DashboardPortal.WidgetPreferences import WidgetToggleForm

__all__ = ["ProcurementAlertForm", "QuickRequisitionForm", "WidgetToggleForm"]
