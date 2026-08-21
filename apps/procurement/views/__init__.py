"""Procurement views package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every view so the apps/procurement/urls/ package (``views.<name>``) resolves.
Imports inside the entity modules are ABSOLUTE.
"""
from .DashboardPortal.ActivityFeed import activity_detail, activity_list
from .DashboardPortal.Overview import dashboard
from .DashboardPortal.ProcurementAlerts import (
    alert_acknowledge,
    alert_create,
    alert_delete,
    alert_detail,
    alert_edit,
    alert_list,
    alert_resolve,
)
from .DashboardPortal.QuickRequisitions import quickreq_create
from .DashboardPortal.SelfServiceReports import report_export, report_index

__all__ = [
    "activity_detail",
    "activity_list",
    "dashboard",
    "alert_acknowledge",
    "alert_create",
    "alert_delete",
    "alert_detail",
    "alert_edit",
    "alert_list",
    "alert_resolve",
    "quickreq_create",
    "report_export",
    "report_index",
]
