"""Procurement forms package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every form so ``from apps.procurement.forms import ProcurementAlertForm`` works
everywhere (views, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .ApprovalWorkflowEngine import (
    ApprovalDecisionForm,
    ApprovalDelegationForm,
    ApprovalRoutingRuleForm,
    EscalationPolicyForm,
)
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
from .EAuctionManagement import EaucBidForm, EaucInviteForm, EauctionForm
from .RfxManagement.Events import (
    RfxEventForm,
    RfxQuestionForm,
    RfxQuestionFormSet,
)
from .RfxManagement.Responses import (
    RfxAnswerForm,
    RfxAnswerFormSet,
    RfxResponseForm,
)
from .SourcingTendering import (
    EventCriterionForm,
    EventCriterionFormSet,
    SourcingBidForm,
    SourcingEventForm,
)
from .VendorManagement import (
    SubmissionReviewForm,
    SuspensionDecisionForm,
    SuspensionLiftForm,
    VendorBidForm,
    VendorInvoiceSubmissionForm,
    VendorPortalAccessForm,
    VendorSuspensionForm,
)
from .ContractsManagement import (
    ClauseLinkFormSet,
    ContractAmendmentDecisionForm,
    ContractAmendmentForm,
    ContractAuthoringForm,
    ContractClauseForm,
    ContractMilestoneForm,
    ContractSignerForm,
    amendable_contracts,
)
from .CatalogManagement.CatalogItems import CatalogItemForm
from .CatalogManagement.Tiers import CatalogPriceTierForm
from .CatalogManagement.PunchOutEndpoints import PunchOutEndpointForm
from .CatalogManagement.UploadBatches import CatalogUploadBatchForm
from .OrderFulfillment import (
    AdvancedShipmentNoticeForm,
    AsnCancelForm,
    AsnDeliveryConfirmForm,
    AsnLineForm,
    AsnLineFormSet,
    BackorderCloseForm,
    BackorderForm,
    BackorderRescheduleForm,
    DeliveryScheduleForm,
    DeliveryScheduleSplitForm,
)
from .PurchaseOrderManagement.PurchaseOrderChanges import (
    ChangeOrderDecisionForm,
    GeneratePOForm,
    PurchaseOrderChangeForm,
    PurchaseOrderChangeLineFormSet,
)
# 6.12 Goods Receipt & Inspection. NOTE: ALLOWED_DOC_EXTENSIONS / MAX_UPLOAD_BYTES are
# deliberately NOT re-exported from this sub-package — CatalogManagement.UploadBatches carries a
# different local MAX_UPLOAD_BYTES (2 MB vs core's 20 MB) and a package-level re-export would make
# which cap applies depend on import order.
from .GoodsReceiptInspection import (
    DiscrepancyCancelForm,
    DiscrepancyNotifyForm,
    DiscrepancyResolveForm,
    ReceiptDiscrepancyForm,
    ReceiptTolerancePolicyForm,
    ReceivingConsoleBookForm,
    ReturnToVendorForm,
    ReturnToVendorLineForm,
    ReturnToVendorLineFormSet,
    RtvCancelForm,
    RtvCloseForm,
    RtvShipForm,
)
# 6.13 Invoice & Voucher Management — from the entity MODULES, same reason as models/__init__.
from .InvoiceVoucherManagement.SupplierInvoices import (
    CaptureUploadForm,
    SupplierInvoiceForm,
    SupplierInvoiceLineFormSet,
)
from .InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLineForm
from .InvoiceVoucherManagement.MatchVariances import InvoiceVarianceAcceptForm
from .InvoiceVoucherManagement.InvoiceDisputes import InvoiceDisputeForm
# 6.14 Spend Analytics & Reporting — from the entity MODULES, same reason as 6.13 above.
# Three forms, not five: ``SpendDashboards.py`` declares none (its three pages are GET-driven
# reports whose filter bar is sanitised against a whitelist in the view — stricter than a Form,
# and a junk parameter degrades to "filter ignored" rather than a page of red text), and
# ``SpendReportSnapshot`` has none by design (a snapshot freezes a computed result; a hand-typed
# one would be a figure with no run behind it).
from .SpendAnalyticsReporting.SpendClassificationRules import SpendClassificationRuleForm
from .SpendAnalyticsReporting.MaverickFindings import MaverickSpendFindingForm
from .SpendAnalyticsReporting.SpendReports import SpendReportForm
# 6.15 Budget & Cost Management — from the entity MODULES, same reason as 6.14 above.
# Two forms, not five: the three computed pages (checker, register, variance) are GET-driven
# reports sanitised in the view, and ``CostForecast`` has no EDIT form by design — a frozen
# projection is deleted and re-frozen, never amended (its create form carries the inputs only;
# the amounts are stamped by the view).
from .BudgetCostManagement.BudgetMappings import BudgetMappingForm
from .BudgetCostManagement.CostForecasts import CostForecastForm

# 6.19 Document & Knowledge Management. Four form classes; the revision upload form is named
# for the ACTION rather than the model because a revision is only ever created through the parent
# document's upload route - there is no create-or-edit pair for it.
from .DocumentKnowledgeManagement.Documents import ProcurementDocumentForm
from .DocumentKnowledgeManagement.Revisions import ProcurementDocumentRevisionUploadForm
from .DocumentKnowledgeManagement.Policies import ProcurementPolicyForm
from .DocumentKnowledgeManagement.KnowledgeResources import KnowledgeResourceForm

# 6.16 Supplier Performance & Evaluation - from the entity MODULES, same reason as 6.13-6.15.
# Four form classes over five view modules, and the two gaps are deliberate:
#   * SupplierKpiScoreEditForm is EDIT-only. A score line is written by
#     performance.generate_scorecard_lines; a hand-created one would be a measurement with no
#     computation behind it. The edit path exists for source="manual" KPIs, where the figure is
#     a human's by definition.
#   * PerformanceBoards.py declares none - its three pages are GET-driven reports whose filter
#     bar is sanitised against a whitelist in the view (the 6.14 SpendDashboards posture), so a
#     junk parameter degrades to "filter ignored" rather than a page of red text.
from .SupplierPerformanceEvaluation.SupplierKpis import SupplierKpiForm
from .SupplierPerformanceEvaluation.ScorecardKpiScores import SupplierKpiScoreEditForm
from .SupplierPerformanceEvaluation.SupplierFeedback import SupplierFeedbackForm
from .SupplierPerformanceEvaluation.SupplierImprovementPlans import SupplierImprovementPlanForm
# 6.18 Inventory & Warehouse Integration
from .InventoryWarehouseIntegration.Policies import ReplenishmentPolicyForm
from .InventoryWarehouseIntegration.Runs import (
    ReplenishmentRunForm,
    ReplenishmentSuggestionDecisionForm,
)
from .InventoryWarehouseIntegration.MaterialIssues import (
    MaterialIssueForm,
    MaterialIssueLineForm,
)

# 6.17 Risk & Compliance Management. The plain ``forms.Form`` classes here (FraudScanForm,
# FraudDispositionForm, ScreeningHitDispositionForm) are decision inputs, not ModelForms: every
# disposition, review and scan is a VERB with its own audit row, so the fields those verbs set
# are deliberately absent from the ModelForms beside them (L20/L22 — a workflow-controlled
# status, a derived score/band/trend and a system ``*_by``/``*_at`` stamp never appear on a form).
from .RiskComplianceManagement.Screenings import (
    ComplianceScreeningForm,
    ScreeningHitForm,
    ScreeningHitDispositionForm,
)
from .RiskComplianceManagement.RiskSignals import SupplierRiskSignalForm
from .RiskComplianceManagement.FraudAlerts import (
    FraudAlertForm,
    FraudScanForm,
    FraudDispositionForm,
)
from .RiskComplianceManagement.Policies import PolicyAttestationForm
from .RiskComplianceManagement.AuditSeals import AuditSealForm

__all__ = [
    "EaucBidForm",
    "EaucInviteForm",
    "EauctionForm",
    "ApprovalDecisionForm",
    "ApprovalDelegationForm",
    "ApprovalRoutingRuleForm",
    "EscalationPolicyForm",
    "AmendmentDecisionForm",
    "ProcurementAlertForm",
    "QuickRequisitionForm",
    "RequisitionAmendmentForm",
    "RequisitionAmendmentLineFormSet",
    "RequisitionTemplateForm",
    "RequisitionTemplateLineFormSet",
    "WidgetToggleForm",
    "RfxAnswerForm",
    "RfxAnswerFormSet",
    "RfxEventForm",
    "RfxQuestionForm",
    "RfxQuestionFormSet",
    "RfxResponseForm",
    "SourcingEventForm",
    "EventCriterionForm",
    "EventCriterionFormSet",
    "SourcingBidForm",
    "VendorPortalAccessForm",
    "VendorBidForm",
    "VendorSuspensionForm",
    "SuspensionDecisionForm",
    "SuspensionLiftForm",
    "VendorInvoiceSubmissionForm",
    "SubmissionReviewForm",
    "ContractClauseForm",
    "ContractAuthoringForm",
    "ClauseLinkFormSet",
    "ContractSignerForm",
    "ContractAmendmentForm",
    "ContractAmendmentDecisionForm",
    "CatalogItemForm",
    "CatalogPriceTierForm",
    "PunchOutEndpointForm",
    "CatalogUploadBatchForm",
    "AdvancedShipmentNoticeForm",
    "AsnLineForm",
    "AsnLineFormSet",
    "AsnDeliveryConfirmForm",
    "AsnCancelForm",
    "DeliveryScheduleForm",
    "DeliveryScheduleSplitForm",
    "BackorderForm",
    "BackorderRescheduleForm",
    "BackorderCloseForm",
    "PurchaseOrderChangeForm",
    "PurchaseOrderChangeLineFormSet",
    "ChangeOrderDecisionForm",
    "GeneratePOForm",
    "ReceiptTolerancePolicyForm",
    "ReceiptDiscrepancyForm",
    "DiscrepancyNotifyForm",
    "DiscrepancyResolveForm",
    "DiscrepancyCancelForm",
    "ReturnToVendorForm",
    "ReturnToVendorLineForm",
    "ReturnToVendorLineFormSet",
    "RtvShipForm",
    "RtvCloseForm",
    "RtvCancelForm",
    "ReceivingConsoleBookForm",
    "SupplierInvoiceForm",
    "CaptureUploadForm",
    "SupplierInvoiceLineForm",
    "SupplierInvoiceLineFormSet",
    "InvoiceVarianceAcceptForm",
    "InvoiceDisputeForm",
    "SpendClassificationRuleForm",
    "MaverickSpendFindingForm",
    "SpendReportForm",
    "BudgetMappingForm",
    "CostForecastForm",
    "ProcurementDocumentForm",
    "ProcurementDocumentRevisionUploadForm",
    "ProcurementPolicyForm",
    "KnowledgeResourceForm",
    "SupplierKpiForm",
    "SupplierKpiScoreEditForm",
    "SupplierFeedbackForm",
    "SupplierImprovementPlanForm",
    # 6.18 Inventory & Warehouse Integration
    "ReplenishmentPolicyForm",
    "ReplenishmentRunForm",
    "ReplenishmentSuggestionDecisionForm",
    "MaterialIssueForm",
    "MaterialIssueLineForm",
    # 6.17 Risk & Compliance Management
    "ComplianceScreeningForm",
    "ScreeningHitForm",
    "ScreeningHitDispositionForm",
    "SupplierRiskSignalForm",
    "FraudAlertForm",
    "FraudScanForm",
    "FraudDispositionForm",
    "PolicyAttestationForm",
    "AuditSealForm",
]
