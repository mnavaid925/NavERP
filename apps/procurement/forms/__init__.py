"""Procurement forms package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every form so ``from apps.procurement.forms import ProcurementAlertForm`` works
everywhere (views, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .DashboardPortal.ProcurementAlerts import ProcurementAlertForm
from .DashboardPortal.QuickRequisitions import QuickRequisitionForm
from .DashboardPortal.WidgetPreferences import WidgetToggleForm
from .RequisitionManagement.Amendments import (
    AmendmentDecisionForm,
    RequisitionAmendmentForm,
    RequisitionAmendmentLineFormSet,
)
from .RequisitionManagement.Templates import (
    RequisitionTemplateForm,
    RequisitionTemplateLineFormSet,
)

__all__ = [
    "AmendmentDecisionForm",
    "ProcurementAlertForm",
    "QuickRequisitionForm",
    "RequisitionAmendmentForm",
    "RequisitionAmendmentLineFormSet",
    "RequisitionTemplateForm",
    "RequisitionTemplateLineFormSet",
    "WidgetToggleForm",
]
