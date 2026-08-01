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
    TradeDocumentLineFormSet,
)
from .ContractCompliance.SustainabilityAssessments import (  # noqa: F401
    SustainabilityAssessmentForm,
)
