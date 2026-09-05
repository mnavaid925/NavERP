"""Procurement URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets
``app_name = "procurement"`` once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`, `export/`) precede the
``<int:pk>/`` ones, and every first segment (`""` — the root, i.e. the module landing
page `procurement:dashboard` — then `alerts/`, `quick-requisition/`, `activity/`,
`reports/`, `widgets/`, `requisitions/`, `templates/`, `amendments/`, `approvals/`, `escalations/`,
`rfx/`, `events/`, `bids/`, `awards/`, `analytics/`, `portal-access/`, `suspensions/`,
`submissions/`, `vendor-portal/`, `auctions/`, `clauses/`, `contracts/`, `contract-sign/`,
`contract-amendments/`, `milestones/`, `renewals/`, `catalog-items/`, `catalog-tiers/`,
`punchout/`, `catalog-uploads/`, `asn/`, `delivery-schedules/`,
`backorders/`, `inbound-tracking/`, `delivery-confirmation/`, `receipt-tolerances/`,
`receipt-discrepancies/`, `returns-to-vendor/`, `receiving-console/`, `tolerance-exceptions/`,
`receipt-audit/`, `supplier-invoices/`, `capture/`, `invoice-vouchers/`,
`supplier-invoice-lines/`, `payment-schedule/`, `match-variances/`, `match-board/`,
`invoice-disputes/`, `spend/`, `spend-rules/`, `maverick-findings/`, `spend-reports/`,
`spend-report-snapshots/`, `budget-mappings/`, `budget-availability/`, `commitments/`,
`budget-variance/`, `cost-forecasts/`, `delegations/`, `eauc/`, `po-changes/`,
`po-generation/`, `po-tracking/`, `documents/`, `document-revisions/`,
`procurement-policies/`, `knowledge/`) is a distinct whole component.

No route in this app uses a converter in its FIRST path component — every first segment is a
literal — so no module can shadow another's namespace. (A ``<str:token>`` converter DOES exist,
at 6.8's ``contract-sign/<str:token>/``, but it sits behind a literal first segment and shadows
nothing outside it. The earlier wording here claimed the app had no ``<str:…>`` converter at
all, which was false and was being copy-pasted forward into each new sub-module. Keeping the
first-segment-is-always-a-literal invariant is what actually makes the guarantee hold.)
"""
from .ApprovalWorkflowEngine import urlpatterns as _awe_approvalengine
from .BudgetCostManagement import urlpatterns as _bcm_budgetcost
from .DocumentKnowledgeManagement import urlpatterns as _dkm_documentknowledge
from .CatalogManagement import urlpatterns as _cat_catalogmanagement
from .OrderFulfillment import urlpatterns as _of_orderfulfillment
from .DashboardPortal.ActivityFeed import urlpatterns as _dp_activity
from .DashboardPortal.Overview import urlpatterns as _dp_overview
from .DashboardPortal.ProcurementAlerts import urlpatterns as _dp_alerts
from .DashboardPortal.QuickRequisitions import urlpatterns as _dp_quickreq
from .DashboardPortal.SelfServiceReports import urlpatterns as _dp_reports
from .EAuctionManagement import urlpatterns as _eauc_eauctionmanagement
from .GoodsReceiptInspection import urlpatterns as _gri_goodsreceiptinspection
from .InvoiceVoucherManagement.SupplierInvoices import urlpatterns as _ivm_supplierinvoices
from .InvoiceVoucherManagement.SupplierInvoiceLines import urlpatterns as _ivm_supplierinvoicelines
from .InvoiceVoucherManagement.MatchVariances import urlpatterns as _ivm_matchvariances
from .InvoiceVoucherManagement.InvoiceDisputes import urlpatterns as _ivm_invoicedisputes
from .RequisitionManagement.Amendments import urlpatterns as _rm_amendments
from .RequisitionManagement.Requisitions import urlpatterns as _rm_requisitions
from .RequisitionManagement.Templates import urlpatterns as _rm_templates
from .RfxManagement import urlpatterns as _rfx_management
from .SpendAnalyticsReporting import urlpatterns as _sar_spendanalytics
from .SourcingTendering import urlpatterns as _st_sourcingtendering
from .VendorManagement import urlpatterns as _vm_vendormanagement
from .ContractsManagement import urlpatterns as _cm_contractsmanagement
from .PurchaseOrderManagement import urlpatterns as _pom_purchaseordermanagement


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
    *_pom_purchaseordermanagement,  # 6.10 change orders, requisition->PO generation, line tracking
    *_of_orderfulfillment,  # 6.11 ASN register + lifecycle verbs, split-delivery instalments
                            #      (+ split console), backorders, and the two computed boards:
                            #      inbound freight tracking and delivery confirmation
    *_gri_goodsreceiptinspection,  # 6.12 receipt tolerance policies, discrepancy register,
                                   #      returns to vendor, and the three computed pages:
                                   #      receiving console, tolerance exceptions, receipt audit
    # 6.13 LAST, so it cannot shadow an earlier module: every first segment here is new
    # (``supplier-invoices/``, ``capture/``, ``invoice-vouchers/``, ``supplier-invoice-lines/``,
    # ``payment-schedule/``, ``match-variances/``, ``match-board/``, ``invoice-disputes/``) and
    # no route in this app uses a converter in its FIRST path component, so appended-last is
    # belt-and-braces against a future module claiming one of them.
    *_ivm_supplierinvoices,     # 6.13 invoice register + capture, duplicates, match/approval verbs
    *_ivm_supplierinvoicelines,  # 6.13 invoice line register + the payment schedule board
    *_ivm_matchvariances,       # 6.13 match exceptions + the three-way match board
    *_ivm_invoicedisputes,      # 6.13 dispute register + workflow verbs + the aging board
    # 6.14 LAST for the same reason 6.13 was: every first segment it claims is new
    # (``spend/`` with its six literal children, ``spend-rules/``, ``maverick-findings/``,
    # ``spend-reports/``, ``spend-report-snapshots/``), and appended-last is belt-and-braces
    # against a future module claiming one of them. Note ``spend-rules/`` and ``spend-reports/``
    # are NOT prefixes of ``spend/`` — Django matches whole path components, not strings.
    *_sar_spendanalytics,       # 6.14 spend dashboard/category/classification/export + maverick
                                #      board & scan, classification rules, maverick findings,
                                #      saved report builder + snapshots
    # 6.15 LAST for the same reason 6.13 and 6.14 were: every first segment it claims is new
    # (``budget-mappings/``, ``budget-availability/``, ``commitments/``, ``budget-variance/``,
    # ``cost-forecasts/``), and appended-last is belt-and-braces against a future module
    # claiming one of them.
    *_bcm_budgetcost,           # 6.15 budget mappings CRUD, availability checker, commitment
                                #      register, variance report (+ CSV), frozen cost forecasts
    # 6.19 LAST for the same reason 6.13-6.15 were: all four first segments it claims are new
    # (``documents/``, ``document-revisions/``, ``procurement-policies/``, ``knowledge/``), and
    # appended-last is belt-and-braces against a future module claiming one of them. The names
    # dodge segments already taken: ``templates/`` is 6.2's and the whole contract family
    # (``contracts/``, ``clauses/``, ``contract-sign/``, ``contract-amendments/``) is 6.8's —
    # which is why the policy library is ``procurement-policies/`` and not ``policies/``.
    *_dkm_documentknowledge,    # 6.19 document register + revision chain, policy library,
                                #      knowledge resources (32 routes, 32 distinct names)
]
