"""SCM forms package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

This __init__ re-exports EVERY form + formset so ``from apps.scm.forms import PurchaseOrderForm``
works from the views and the tests. Adding a form without adding it here is a bug.
"""
from ._common import *  # noqa: F401,F403

# 4.1 Procurement Management
from .ProcurementManagement.PurchaseRequisitions import (  # noqa: F401
    PurchaseRequisitionForm,
    PurchaseRequisitionLineForm,
    PurchaseRequisitionLineFormSet,
)
from .ProcurementManagement.Rfqs import (  # noqa: F401
    RFQForm,
    RFQLineForm,
    RFQLineFormSet,
    RFQVendorForm,
    RFQVendorFormSet,
    RFQQuoteForm,
    RFQQuoteLineForm,
    RFQQuoteLineFormSet,
)
from .ProcurementManagement.PurchaseOrders import (  # noqa: F401
    PurchaseOrderForm,
    PurchaseOrderLineForm,
    PurchaseOrderLineFormSet,
    PurchaseOrderAmendForm,
    PurchaseOrderCancelForm,
    PurchaseOrderAcknowledgeForm,
)
from .ProcurementManagement.GoodsReceiptNotes import (  # noqa: F401
    GoodsReceiptNoteForm,
    GoodsReceiptLineForm,
    GoodsReceiptLineFormSet,
)

# 4.2 Supplier Relationship Management
from .SupplierRelationshipManagement.SupplierProfiles import (  # noqa: F401
    SupplierProfileForm,
)
from .SupplierRelationshipManagement.SupplierScorecards import (  # noqa: F401
    SupplierScorecardForm,
)
from .SupplierRelationshipManagement.SupplierContracts import (  # noqa: F401
    SupplierContractForm,
)
from .SupplierRelationshipManagement.SupplierCatalogs import (  # noqa: F401
    SupplierCatalogForm,
    SupplierCatalogItemForm,
    SupplierCatalogItemFormSet,
)
from .SupplierRelationshipManagement.SupplierRiskAssessments import (  # noqa: F401
    SupplierRiskAssessmentForm,
)

# 4.3 Inventory Management
from .InventoryManagement.Items import (  # noqa: F401
    ItemCategoryForm,
    UOMForm,
    ItemForm,
)
from .InventoryManagement.Locations import (  # noqa: F401
    LocationForm,
)
from .InventoryManagement.LotSerials import (  # noqa: F401
    LotSerialForm,
)
from .InventoryManagement.StockTransfers import (  # noqa: F401
    StockTransferForm,
    StockTransferLineForm,
    StockTransferLineFormSet,
)
from .InventoryManagement.StockAdjustments import (  # noqa: F401
    StockAdjustmentForm,
    StockAdjustmentLineForm,
    StockAdjustmentLineFormSet,
)
from .InventoryManagement.ReorderRules import (  # noqa: F401
    ReorderRuleForm,
)

# 4.4 Warehouse Management
from .WarehouseManagement.PutawayTasks import (  # noqa: F401
    PutawayTaskForm,
)
from .WarehouseManagement.PickTasks import (  # noqa: F401
    PickTaskForm,
    PickTaskPackForm,
    PickTaskLineForm,
    PickTaskLineFormSet,
)
from .WarehouseManagement.CycleCountTasks import (  # noqa: F401
    CycleCountTaskForm,
    CycleCountTaskLineForm,
    CycleCountTaskLineFormSet,
)
from .WarehouseManagement.YardVisits import (  # noqa: F401
    YardVisitForm,
)

# 4.5 Order Management System (OMS)
from .OrderManagement.SalesOrders import (  # noqa: F401
    SalesOrderForm,
    SalesOrderLineForm,
    BaseSalesOrderLineFormSet,
    SalesOrderLineFormSet,
)
from .OrderManagement.SalesOrderAllocations import (  # noqa: F401
    SalesOrderAllocationForm,
)

# 4.6 Transportation Management System (TMS)
from .TransportationManagement.Carriers import (  # noqa: F401
    CarrierForm,
    CarrierRateCardForm,
    CarrierRateCardFormSet,
)
from .TransportationManagement.Loads import (  # noqa: F401
    LoadForm,
    LoadStopForm,
    LoadStopFormSet,
)
from .TransportationManagement.Shipments import (  # noqa: F401
    ShipmentForm,
    TrackingEventForm,
)
from .TransportationManagement.FreightInvoices import (  # noqa: F401
    FreightInvoiceForm,
    FreightInvoiceLineForm,
    FreightInvoiceLineFormSet,
)

# 4.7 Demand Planning & Forecasting
from .DemandPlanning.SeasonalityProfiles import (  # noqa: F401
    SeasonalityProfileForm,
    SeasonalityIndexForm,
    SeasonalityIndexFormSet,
)
from .DemandPlanning.DemandForecasts import (  # noqa: F401
    DemandForecastForm,
    DemandForecastPeriodForm,
    BaseDemandForecastPeriodFormSet,
    DemandForecastPeriodFormSet,
    DemandForecastGenerateForm,
)
from .DemandPlanning.DemandSignals import (  # noqa: F401
    DemandSignalForm,
    DemandSignalApplyForm,
    DemandSignalDismissForm,
)
from .DemandPlanning.ForecastAdjustments import (  # noqa: F401
    ForecastAdjustmentForm,
    ForecastAdjustmentReviewForm,
)

# 4.8 Manufacturing / Production
from .Manufacturing.WorkCenters import (  # noqa: F401
    WorkCenterForm,
)
from .Manufacturing.BillsOfMaterials import (  # noqa: F401
    BillOfMaterialsForm,
    BOMLineForm,
    BaseBOMLineFormSet,
    BOMLineFormSet,
)
from .Manufacturing.WorkOrders import (  # noqa: F401
    WorkOrderForm,
    WorkOrderComponentForm,
    WorkOrderComponentFormSet,
    WorkOrderScheduleForm,
    WorkOrderReportForm,
)
from .Manufacturing.ProductionTimeLogs import (  # noqa: F401
    ProductionTimeLogForm,
)

# 4.9 Quality Management System (QMS)
from .QualityManagement.InspectionPlans import (  # noqa: F401
    InspectionPlanForm,
    InspectionCharacteristicForm,
    BaseInspectionCharacteristicFormSet,
    InspectionCharacteristicFormSet,
)
from .QualityManagement.QualityInspections import (  # noqa: F401
    QualityInspectionForm,
    InspectionResultForm,
    BaseInspectionResultFormSet,
    InspectionResultFormSet,
    QualityInspectionDecisionForm,
    QualityInspectionCoAIssueForm,
)
from .QualityManagement.QualityAudits import (  # noqa: F401
    QualityAuditForm,
    QualityAuditFindingForm,
)
from .QualityManagement.NonConformances import (  # noqa: F401
    NonConformanceForm,
    NonConformanceDispositionForm,
)
from .QualityManagement.CapaActions import (  # noqa: F401
    CapaActionForm,
    CapaTaskForm,
    BaseCapaTaskFormSet,
    CapaTaskFormSet,
    CapaVerificationForm,
)

# 4.10 Returns Management (Reverse Logistics)
from .ReturnsManagement.ReturnReasons import (  # noqa: F401
    ReturnReasonForm,
)
from .ReturnsManagement.ReturnPolicies import (  # noqa: F401
    ReturnPolicyForm,
)
from .ReturnsManagement.ReturnAuthorizations import (  # noqa: F401
    ReturnAuthorizationForm,
    ReturnLineForm,
    BaseReturnLineFormSet,
    ReturnLineFormSet,
    ReturnApprovalForm,
    ReturnRejectForm,
    ReturnReceiveAllForm,
    PortalReturnRequestForm,
    PublicReturnUpdateForm,
)
from .ReturnsManagement.ReturnDispositions import (  # noqa: F401
    ReturnDispositionForm,
    ReturnDispositionRowForm,
    BaseReturnDispositionFormSet,
    ReturnDispositionFormSet,
    ReturnLinePickerForm,
    ReturnDispositionDecideForm,
    ReturnDispositionSplitForm,
)
from .ReturnsManagement.WarrantyClaims import (  # noqa: F401
    WarrantyClaimForm,
    WarrantyClaimCostForm,
    BaseWarrantyClaimCostFormSet,
    WarrantyClaimCostFormSet,
    WarrantyClaimResponseForm,
    WarrantyClaimCreditForm,
)

# 4.11 Supply Chain Analytics
# There is deliberately NO KpiSnapshots form module: a snapshot is system-written by
# ``analytics.capture_snapshots`` and its create path is the ``kpisnapshot_capture`` POST action, so
# a ModelForm for it would be a way to hand-type a "measured" figure. That is the CRM ReportSnapshot
# rule, and it is a decision rather than an omission (see the model docstring).
from .SupplyChainAnalytics.KpiTargets import (  # noqa: F401
    KpiTargetForm,
)
from .SupplyChainAnalytics.SupplyChainAlerts import (  # noqa: F401
    SupplyChainAlertForm,
    AlertAssignForm,
    AlertSnoozeForm,
    AlertResolveForm,
)

# --- 4.12 Contract & Compliance Management ---------------------------------------------------
from .ContractCompliance.TradeLicenses import (  # noqa: F401
    TradeLicenseForm,
)
from .ContractCompliance.ComplianceRequirements import (  # noqa: F401
    ComplianceRequirementForm,
    ComplianceCheckForm,
)
from .ContractCompliance.TradeDocuments import (  # noqa: F401
    TradeDocumentForm,
    TradeDocumentLineForm,
    BaseTradeDocumentLineFormSet,
    TradeDocumentLineFormSet,
)
from .ContractCompliance.SustainabilityAssessments import (  # noqa: F401
    SustainabilityAssessmentForm,
)

# --- 4.13 Asset Management -------------------------------------------------------------------
# `Assets` FIRST: it owns the three scoping helpers (`_scope_to_tenant` / `_keep_current` /
# `_reject_foreign`) the other three modules import, so this order keeps the dependency edge running
# one way. There is deliberately NO MeterReading EDIT form — the model is append-only (the
# `scm.StockMove` posture) and a wrong reading is corrected by posting a later, correct one.
from .AssetManagement.Assets import (  # noqa: F401
    AssetForm,
    AssetSparePartForm,
)
from .AssetManagement.MaintenancePlans import (  # noqa: F401
    MaintenancePlanForm,
    MaintenancePlanTaskForm,
    MaintenancePlanTaskFormSet,
)
from .AssetManagement.MaintenanceWorkOrders import (  # noqa: F401
    MaintenanceWorkOrderForm,
    MaintenanceWorkOrderPartForm,
    BaseMaintenanceWorkOrderPartFormSet,
    MaintenanceWorkOrderPartFormSet,
)
from .AssetManagement.MeterReadings import (  # noqa: F401
    MeterReadingForm,
)

# --- 4.14 Labor Management --------------------------------------------------------------------
# Five ModelForms, and what matters about them is mostly what they DON'T carry. Every one is an
# explicit `Meta.fields` whitelist rather than an exclude list, because a whitelist fails CLOSED when
# a column is added later while an exclude list fails open — the new column silently becomes
# postable. Off every form by design: the auto `number`, `status` (verb-controlled on all three
# status-bearing models), LaborSession's whole provenance block (`source` / `recorded_by` / `login` /
# the approval stamps), LaborActivity's `session` (it comes from the parent route — a session pk in
# a POST body would let a caller graft minutes onto somebody else's shift), its derived
# `duration_minutes`, and all four of its `*_snapshot` columns. That last one is the 4.13
# MeterReading fix applied before it could become a bug: a snapshot a user can type is not a record
# of what the standard said, it is a claim.
#
# LaborPlanLineForm exposes `planned_headcount` and `notes` and nothing else — every other column on
# the line is generated by `laborplan_generate` and is editable=False.
from .LaborManagement.LaborStandards import (  # noqa: F401
    LaborStandardForm,
)
from .LaborManagement.LaborSessions import (  # noqa: F401
    LaborSessionForm,
)
from .LaborManagement.LaborActivities import (  # noqa: F401
    LaborActivityForm,
)
from .LaborManagement.LaborPlans import (  # noqa: F401
    LaborPlanForm,
    LaborPlanLineForm,
)

# --- 4.15 Cold Chain Management ---------------------------------------------------------------
# Six form classes, and what matters about them is mostly what they DON'T carry.
#
# `ColdChainMonitors` FIRST: it is this sub-package's root entity module and it owns the two shared
# helpers the other two import (`_scope_to_tenant` and `_ModelErrorSafe`), so this order keeps the
# dependency edge running one way — the 4.13 `AssetManagement/Assets.py` precedent exactly.
#
# Off every form by design: `tenant` (stamped by `crud_create`), the auto `number`, and — on
# `TemperatureExcursion` — EVERY detector-written column (`started_at` / `ended_at` /
# `duration_minutes` / `breach_direction` / `extreme_temperature` / `limit_min` / `limit_max` /
# `reading_count` / `mkt` / `last_detected_at`), its verb-controlled `status`, and its four
# acknowledge/assess stamps. On `TemperatureReading`: `monitor` (it comes from the URL — a parent pk
# in a POST body is how a caller grafts a reading onto somebody else's cold room), the snapshotted
# `interval_minutes`, and the `source` / `recorded_by` provenance pair.
#
# `ColdChainMonitor.status` IS on its form and that is not an inconsistency: the user is its only
# writer, while excursion status is workflow state the four verbs own. Do not "fix" either to match.
#
# There is deliberately NO TemperatureReading EDIT form and no delete form — the model is
# append-only (the `scm.StockMove` / `scm.MeterReading` posture) and a wrong reading is corrected by
# posting a later, correct one. `TemperatureExcursionWindowForm` is the manual back-dated create and
# types NO measured number: the view computes them from the readings in the window through
# `apps/scm/coldchain.py`.
from .ColdChainManagement.ColdChainMonitors import (  # noqa: F401
    ColdChainMonitorForm,
)
from .ColdChainManagement.TemperatureReadings import (  # noqa: F401
    TemperatureReadingForm,
    TemperatureReadingImportForm,
)
from .ColdChainManagement.TemperatureExcursions import (  # noqa: F401
    TemperatureExcursionForm,
    TemperatureExcursionAssessForm,
    TemperatureExcursionWindowForm,
)

# --- 4.16 Customer Portal -----------------------------------------------------------------------
# FOUR forms for THREE models, and no form at all for the fourth.
#
# `PortalActivity` has no form module and never will: every one of its fields is `editable=False`
# because the whole row is system-written by `PortalActivity.record()` from the gated customer
# views. A ModelForm over it would have no fields to render. The absence is a decision, not an
# omission — it is why 4.16's views for that model are list + detail only.
#
# `PortalOrderInquiry` has TWO forms because the staff triage form and the customer-facing form
# differ in what they may SET, not merely in what they render. `PortalInquiryCustomerForm` has no
# `portal_account` field at all (the view stamps it from the signed-in user) and scopes every order
# dropdown to that one customer. One form gated by an `is_staff` flag would put an authorisation
# decision inside template-facing code, where the next edit quietly widens it.
from .CustomerPortal.PortalAccounts import (  # noqa: F401
    PortalAccountForm,
)
from .CustomerPortal.PortalOrderInquiries import (  # noqa: F401
    PortalOrderInquiryForm,
    PortalInquiryCustomerForm,
)
from .CustomerPortal.PortalDocumentShares import (  # noqa: F401
    PortalDocumentShareForm,
)

# --- 4.17 Third-Party Logistics (3PL) Management --------------------------------------------------
# SIX forms for FOUR models: the two line models each get their own, and the two computed report
# pages get none at all because they write nothing.
#
# What is NOT on these forms is the load-bearing part — and `ClientRateCard.status` is NOT one of
# them. It IS on the header form deliberately (see the ClientRateCards module docstring, ruling 1):
# `activate` / `supersede` are the PREFERRED path, not the only one, and promoting a card through the
# form is safe because `clientratecard_edit` refuses any card outside EDITABLE_RATE_CARD_STATUSES
# ("draft",) and `ClientRateCard.clean()` re-runs the overlap guard on every write path.
# `ClientBillingRun.status` and every computed total ARE absent, and for the opposite reason: the
# run's numbers are written by `calculate()` off the ledger, and a typed total would be a second
# source of truth for money. `ClientSLA`'s achieved figure, breach flag and credit amount are absent
# because `recompute()` derives them from 4.5/4.6/4.10 rows — a hand-typed achievement is exactly the
# number a customer would dispute.
from .ThirdPartyLogistics.LogisticsClients import (  # noqa: F401
    LogisticsClientForm,
)
from .ThirdPartyLogistics.ClientRateCards import (  # noqa: F401
    ClientRateCardForm,
    ClientRateCardLineForm,
)
from .ThirdPartyLogistics.ClientBillingRuns import (  # noqa: F401
    ClientBillingRunForm,
    ClientBillingRunLineForm,
)
from .ThirdPartyLogistics.ClientSlas import (  # noqa: F401
    ClientSLAForm,
)

# --- 4.18 Finance & Accounting Integration -----------------------------------------------------
# THREE forms, and `LandedCostAllocation` deliberately has none: it is a derived ledger written only
# by `LandedCostVoucher.allocate()`, so a ModelForm over it would be a hand-editable copy of a
# computed number — the exact shape of the money bug this sub-module is built to avoid.
#
# What is ABSENT from these forms is the load-bearing part. `LandedCostVoucherForm` carries no
# `status` (the allocate → accrue → draft-bill ladder owns it), no `bill` (set by `draft_bill()`),
# and none of the five derived totals (`recalc_totals()` owns them) — a typed total would be a
# second source of truth for money. `LandedCostChargeForm` carries no `voucher`: the parent comes
# from the ROUTE, because a parent pk in a POST body is how a charge is grafted onto another
# workspace's voucher.
from .FinanceIntegration.LandedCostVouchers import (  # noqa: F401
    LandedCostVoucherForm,
    LandedCostChargeForm,
)
# `TenantUniqueMixin` here and NOT on the voucher form, and the asymmetry is intentional: a tariff's
# (hs_code, country_of_origin, effective_from) is user-entered and duplicable, whereas the voucher's
# only unique_together is on the auto-assigned `number`.
from .FinanceIntegration.DutyTariffs import (  # noqa: F401
    DutyTariffForm,
)
