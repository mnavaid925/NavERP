"""Procurement models package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every model so ``from apps.procurement.models import ProcurementAlert`` works
everywhere (admin, seeder, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .ApprovalWorkflowEngine import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
    RequisitionApproval,
    escalation_candidates,
    resolve_routing,
    run_escalations,
)
from .DashboardPortal.ProcurementAlerts import ProcurementAlert
from .DashboardPortal.WidgetPreferences import WidgetPreference
from .RequisitionManagement.Amendments import RequisitionAmendment, RequisitionAmendmentLine
from .RequisitionManagement.Templates import RequisitionTemplate, RequisitionTemplateLine
from .EAuctionManagement import EaucBid, EaucInvite, Eauction
from .RfxManagement.Events import RfxEvent, RfxQuestion
from .RfxManagement.Responses import (
    RfxAnswer,
    RfxResponse,
    earned_score_map,
    possible_points_map,
    weighted_percent,
)
from .SourcingTendering import BidScore, EventCriterion, SourcingBid, SourcingEvent
from .VendorManagement import (
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
)
from .ContractsManagement import (
    ContractAmendment,
    ContractClause,
    ContractClauseLink,
    ContractMilestone,
    ContractSigner,
    expiring_contracts,
    run_renewal_alerts,
)
from .CatalogManagement.CatalogItems import CatalogItem
from .CatalogManagement.Tiers import CatalogPriceTier
from .CatalogManagement.PunchOutEndpoints import PunchOutEndpoint
from .CatalogManagement.UploadBatches import CatalogUploadBatch
from .OrderFulfillment import (
    AdvancedShipmentNotice,
    AsnLine,
    Backorder,
    DeliverySchedule,
    split_po_line,
)
from .PurchaseOrderManagement import (
    PurchaseOrderChange,
    PurchaseOrderChangeLine,
    convertible_requisitions,
    generate_po_from_requisition,
)
from .GoodsReceiptInspection import (
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    ReturnToVendor,
    ReturnToVendorLine,
    evaluate_receipt_tolerance,
    resolve_line_item,
    resolve_receipt_tolerance,
)
# 6.13 Invoice & Voucher Management — imported from the entity MODULES (not the sub-package):
# SupplierInvoices.py imports MatchVariances/SupplierInvoiceLines at module level, so importing
# the sub-package's own __init__ from inside it would be a star-import cycle at URLconf import.
from .InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from .InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from .InvoiceVoucherManagement.MatchVariances import InvoiceMatchVariance
from .InvoiceVoucherManagement.InvoiceDisputes import InvoiceDispute
# 6.14 Spend Analytics & Reporting — from the entity MODULES, same reason as 6.13 above.
# ``SpendDashboards.py`` declares no model (three computed pages over rows other sub-modules own,
# no table, no migration) and exports nothing, so there is nothing to import from it.
# The two window helpers come along because they ARE this sub-module's definition of "money that
# counts": ``apps/procurement/analytics.py`` is built on them, and a second copy anywhere would
# let two pages disagree about what spend is. The CHOICES tuples are deliberately NOT re-exported
# here — each is reachable as ``SpendReport.BASIS_CHOICES`` etc., and hoisting names as generic as
# ``BASIS_CHOICES`` into the app-wide model namespace is how the next sub-module collides.
from .SpendAnalyticsReporting.SpendClassificationRules import (
    SpendClassificationRule,
    committed_line_window,
    invoiced_line_window,
)
from .SpendAnalyticsReporting.MaverickFindings import MaverickSpendFinding
from .SpendAnalyticsReporting.SpendReports import SpendReport, SpendReportSnapshot
# 6.15 Budget & Cost Management — from the entity MODULES, same reason as 6.14 above.
# ``BudgetChecks.py``, ``CommitmentRegister.py`` and ``VarianceReport.py`` declare no model
# (three computed pages over rows other sub-modules own), so there is nothing to import from
# them. The commitment vocabulary and the three line-window helpers travel with BudgetMapping
# because they ARE this sub-module's single definition of "what counts as committed /
# requested spend" — a second copy anywhere would let the checker, the register and the
# variance report disagree about the same purchase order. METHOD_CHOICES is deliberately NOT
# re-exported: it is reachable as ``CostForecast.METHOD_CHOICES`` (6.14 precedent).
from .BudgetCostManagement.BudgetMappings import (
    BudgetMapping,
    COMMITTED_PR_STATUSES,
    OPEN_COMMITMENT_PO_STATUSES,
    REQUESTED_PR_STATUSES,
    committed_pr_lines,
    open_po_commitment_lines,
    requested_pr_lines,
)
from .BudgetCostManagement.CostForecasts import CostForecast, compute_forecast_amounts

# 6.19 Document & Knowledge Management. ``normalize_tags`` and every ``*_CHOICES`` tuple stay
# unhoisted (reachable as ``Model.FIELD_CHOICES``) per the 6.14/6.15 rule; the four reminder /
# extraction callables ARE re-exported because the seeder, admin and a future management command
# call them by name. ``extract_document_text`` in particular is the one entry point that knows the
# lazy-pdfplumber fallback contract - a second copy would quietly disagree about what an
# unreadable file means.
from .DocumentKnowledgeManagement.Documents import (
    ProcurementDocument,
    expiring_documents,
    run_document_reminders,
    run_document_reminders_audited,
)
from .DocumentKnowledgeManagement.Revisions import ProcurementDocumentRevision, extract_document_text
from .DocumentKnowledgeManagement.Policies import ProcurementPolicy
from .DocumentKnowledgeManagement.KnowledgeResources import KnowledgeResource
# 6.16 Supplier Performance & Evaluation — from the entity MODULES, same reason as 6.13-6.15.
#
# FOUR MODEL CLASSES AND NOTHING ELSE. The sub-module's CHOICES / CSS vocabularies are
# deliberately NOT re-exported here: ``SupplierFeedback`` and ``SupplierImprovementPlans`` each
# declare a ``STATUS_CHOICES`` and a ``STATUS_CSS`` and they are DIFFERENT enums (the response
# lifecycle vs the plan lifecycle), so one bare name at this level would silently shadow the
# other — and with three sub-modules being built into this file concurrently, generic names like
# CATEGORY_CHOICES are a collision waiting to happen besides. Views and forms already import
# every vocabulary from its entity module by path, and each is aliased onto its own model class
# (``SupplierFeedback.STATUS_CHOICES``), so nothing needs them here. See the sub-package
# __init__ for the full reasoning.
#
# ``generate_scorecard_lines`` — the one writer of ``SupplierKpiScore`` — is NOT here either: it
# lives in ``apps/procurement/performance.py``, a flat app-root service module, and the seeder
# and views import it from there.
from .SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi
from .SupplierPerformanceEvaluation.ScorecardKpiScores import SupplierKpiScore
from .SupplierPerformanceEvaluation.SupplierFeedback import SupplierFeedback
from .SupplierPerformanceEvaluation.SupplierImprovementPlans import SupplierImprovementPlan

__all__ = [
    "EaucBid",
    "EaucInvite",
    "Eauction",
    "ApprovalRoutingRule",
    "RequisitionApproval",
    "ApprovalDelegation",
    "EscalationPolicy",
    "resolve_routing",
    "escalation_candidates",
    "run_escalations",
    "ProcurementAlert",
    "RequisitionAmendment",
    "RequisitionAmendmentLine",
    "RequisitionTemplate",
    "RequisitionTemplateLine",
    "WidgetPreference",
    "RfxAnswer",
    "RfxEvent",
    "RfxQuestion",
    "RfxResponse",
    "earned_score_map",
    "possible_points_map",
    "weighted_percent",
    "SourcingEvent",
    "EventCriterion",
    "SourcingBid",
    "BidScore",
    "VendorPortalAccess",
    "VendorSuspension",
    "VendorInvoiceSubmission",
    "ContractClause",
    "ContractClauseLink",
    "ContractSigner",
    "ContractAmendment",
    "ContractMilestone",
    "expiring_contracts",
    "run_renewal_alerts",
    "CatalogItem",
    "CatalogPriceTier",
    "PunchOutEndpoint",
    "CatalogUploadBatch",
    "AdvancedShipmentNotice",
    "AsnLine",
    "DeliverySchedule",
    "split_po_line",
    "Backorder",
    "PurchaseOrderChange",
    "PurchaseOrderChangeLine",
    "convertible_requisitions",
    "generate_po_from_requisition",
    "ReceiptTolerancePolicy",
    "resolve_receipt_tolerance",
    "evaluate_receipt_tolerance",
    "resolve_line_item",
    "ReceiptDiscrepancy",
    "ReturnToVendor",
    "ReturnToVendorLine",
    "SupplierInvoice",
    "SupplierInvoiceLine",
    "InvoiceMatchVariance",
    "InvoiceDispute",
    "SpendClassificationRule",
    "invoiced_line_window",
    "committed_line_window",
    "MaverickSpendFinding",
    "SpendReport",
    "SpendReportSnapshot",
    "BudgetMapping",
    "OPEN_COMMITMENT_PO_STATUSES",
    "COMMITTED_PR_STATUSES",
    "REQUESTED_PR_STATUSES",
    "open_po_commitment_lines",
    "committed_pr_lines",
    "requested_pr_lines",
    "CostForecast",
    "compute_forecast_amounts",
    "ProcurementDocument",
    "expiring_documents",
    "run_document_reminders",
    "run_document_reminders_audited",
    "ProcurementDocumentRevision",
    "extract_document_text",
    "ProcurementPolicy",
    "KnowledgeResource",
    "SupplierKpi",
    "SupplierKpiScore",
    "SupplierFeedback",
    "SupplierImprovementPlan",
]
