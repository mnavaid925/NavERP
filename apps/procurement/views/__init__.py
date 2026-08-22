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
from .RequisitionManagement.Amendments import (
    amendment_approve,
    amendment_detail,
    amendment_list,
    amendment_reject,
    req_amendment_create,
)
from .RequisitionManagement.Requisitions import req_detail, req_list
from .RequisitionManagement.Templates import (
    template_apply,
    template_create,
    template_delete,
    template_detail,
    template_edit,
    template_list,
)

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
    "amendment_approve",
    "amendment_detail",
    "amendment_list",
    "amendment_reject",
    "req_amendment_create",
    "req_detail",
    "req_list",
    "template_apply",
    "template_create",
    "template_delete",
    "template_detail",
    "template_edit",
    "template_list",
]
