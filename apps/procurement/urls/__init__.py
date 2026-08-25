"""Procurement URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets
``app_name = "procurement"`` once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`, `export/`) precede the
``<int:pk>/`` ones, and every first segment (``, `alerts/`, `quick-requisition/`, `activity/`,
`reports/`, `widgets/`, `requisitions/`, `templates/`, `amendments/`) is a distinct whole
component — no greedy ``<str:…>`` converter exists in this app, so there is no cross-module
shadowing surface to reason about.
"""
from .ApprovalWorkflowEngine import urlpatterns as _awe_approvalengine
from .DashboardPortal.ActivityFeed import urlpatterns as _dp_activity
from .DashboardPortal.Overview import urlpatterns as _dp_overview
from .DashboardPortal.ProcurementAlerts import urlpatterns as _dp_alerts
from .DashboardPortal.QuickRequisitions import urlpatterns as _dp_quickreq
from .DashboardPortal.SelfServiceReports import urlpatterns as _dp_reports
from .RequisitionManagement.Amendments import urlpatterns as _rm_amendments
from .RequisitionManagement.Requisitions import urlpatterns as _rm_requisitions
from .RequisitionManagement.Templates import urlpatterns as _rm_templates


app_name = "procurement"

urlpatterns = [
    *_dp_overview,     # "" landing + widgets/toggle/
    *_dp_alerts,       # Task & Alert Center
    *_dp_quickreq,     # Quick Requisition Entry
    *_dp_activity,     # Recent Activity Feed (+ entry detail)
    *_dp_reports,      # Self-Service Reporting (+ CSV export)
    *_rm_requisitions,  # 6.2 requisition tracking (+ request-amendment)
    *_rm_templates,     # 6.2 requisition templates (+ apply)
    *_rm_amendments,    # 6.2 amendment workflow (list/detail/approve/reject)
    *_awe_approvalengine,  # 6.3 routing rules, queue/history/mine, DOA grants, escalations
]
