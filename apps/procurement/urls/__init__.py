"""Procurement URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets
``app_name = "procurement"`` once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`, `export/`) precede the
``<int:pk>/`` ones, and every first segment (``, `alerts/`, `quick-requisition/`, `activity/`,
`reports/`, `widgets/`, `requisitions/`, `templates/`, `amendments/`, `approvals/`, `escalations/`,
`rfx/`, `events/`, `bids/`, `awards/`, `analytics/`, `portal-access/`, `suspensions/`,
`submissions/`, `vendor-portal/`, `auctions/`, `clauses/`, `contracts/`, `contract-sign/`,
`contract-amendments/`, `milestones/`, `renewals/`, `catalog-items/`, `catalog-tiers/`,
`punchout/`, `catalog-uploads/`, `asn/`, `delivery-schedules/`,
`backorders/`, `inbound-tracking/`, `delivery-confirmation/`) is a distinct whole component — no greedy
``<str:…>`` converter exists in this app, so there is no cross-module shadowing surface to reason
about.
"""
from .ApprovalWorkflowEngine import urlpatterns as _awe_approvalengine
from .CatalogManagement import urlpatterns as _cat_catalogmanagement
from .OrderFulfillment import urlpatterns as _of_orderfulfillment
from .DashboardPortal.ActivityFeed import urlpatterns as _dp_activity
from .DashboardPortal.Overview import urlpatterns as _dp_overview
from .DashboardPortal.ProcurementAlerts import urlpatterns as _dp_alerts
from .DashboardPortal.QuickRequisitions import urlpatterns as _dp_quickreq
from .DashboardPortal.SelfServiceReports import urlpatterns as _dp_reports
from .EAuctionManagement import urlpatterns as _eauc_eauctionmanagement
from .RequisitionManagement.Amendments import urlpatterns as _rm_amendments
from .RequisitionManagement.Requisitions import urlpatterns as _rm_requisitions
from .RequisitionManagement.Templates import urlpatterns as _rm_templates
from .RfxManagement import urlpatterns as _rfx_management
from .SourcingTendering import urlpatterns as _st_sourcingtendering
from .VendorManagement import urlpatterns as _vm_vendormanagement
from .ContractsManagement import urlpatterns as _cm_contractsmanagement


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
    *_eauc_eauctionmanagement,  # 6.7 e-auctions: setup/lifecycle/invites + floor/console/bidding
    *_rfx_management,      # 6.6 RFx events/questionnaires, responses + scoring, library
    *_st_sourcingtendering,  # 6.5 sourcing events, bids + scoring, award board, analytics
    *_vm_vendormanagement,  # 6.4 portal access, suspensions, invoice submissions, vendor portal
    *_cm_contractsmanagement,  # 6.8 clause library, contract register/authoring + token sign page,
                               #    amendments, milestones, renewal board
    *_cat_catalogmanagement,  # 6.9 catalog items + approval, price tiers, punch-out endpoints,
                              #    supplier upload batches
    *_of_orderfulfillment,  # 6.11 ASN register + lifecycle verbs, split-delivery instalments
                            #      (+ split console), backorders, and the two computed boards:
                            #      inbound freight tracking and delivery confirmation
]
