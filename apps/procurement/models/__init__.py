"""Procurement models package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every model so ``from apps.procurement.models import ProcurementAlert`` works
everywhere (admin, seeder, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .DashboardPortal.ProcurementAlerts import ProcurementAlert
from .DashboardPortal.WidgetPreferences import WidgetPreference
from .RequisitionManagement.Amendments import RequisitionAmendment, RequisitionAmendmentLine
from .RequisitionManagement.Templates import RequisitionTemplate, RequisitionTemplateLine

__all__ = [
    "ProcurementAlert",
    "RequisitionAmendment",
    "RequisitionAmendmentLine",
    "RequisitionTemplate",
    "RequisitionTemplateLine",
    "WidgetPreference",
]
