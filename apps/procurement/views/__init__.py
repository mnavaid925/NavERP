"""Procurement views package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every view so the apps/procurement/urls/ package (``views.<name>``) resolves.
Imports inside the entity modules are ABSOLUTE.
"""
from .ApprovalWorkflowEngine import (
    approval_approve,
    approval_decide,
    approval_history,
    approval_mine,
    approval_queue,
    approval_reject,
    delegation_create,
    delegation_delete,
    delegation_detail,
    delegation_edit,
    delegation_list,
    escalation_queue,
    escalation_run,
    routingrule_create,
    routingrule_delete,
    routingrule_detail,
    routingrule_edit,
    routingrule_list,
)
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
    "routingrule_list", "routingrule_detail", "routingrule_create",
    "routingrule_edit", "routingrule_delete",
    "approval_queue", "approval_history", "approval_mine",
    "approval_approve", "approval_reject",
    "delegation_list", "delegation_detail", "delegation_create",
    "delegation_edit", "delegation_delete",
    "escalation_queue", "escalation_run",
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
