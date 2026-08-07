"""SCM models package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

This __init__ re-exports EVERY model so ``from apps.scm.models import PurchaseOrder`` works from the
admin, the seeder, the tests and any peer app. Adding a model without adding it here is a bug: it
will ImportError/AttributeError at runtime, not at import time.
"""
from ._base import *  # noqa: F401,F403

# 4.1 Procurement Management
from .ProcurementManagement.PurchaseRequisitions import (  # noqa: F401
    PurchaseRequisition,
    PurchaseRequisitionLine,
)
from .ProcurementManagement.Rfqs import (  # noqa: F401
    RFQ,
    RFQLine,
    RFQVendor,
    RFQQuote,
    RFQQuoteLine,
)
from .ProcurementManagement.PurchaseOrders import (  # noqa: F401
    PurchaseOrder,
    PurchaseOrderLine,
)
from .ProcurementManagement.GoodsReceiptNotes import (  # noqa: F401
    GoodsReceiptNote,
    GoodsReceiptLine,
)

# 4.2 Supplier Relationship Management
from .SupplierRelationshipManagement.SupplierProfiles import (  # noqa: F401
    SupplierProfile,
)
from .SupplierRelationshipManagement.SupplierScorecards import (  # noqa: F401
    SupplierScorecard,
)
from .SupplierRelationshipManagement.SupplierContracts import (  # noqa: F401
    SupplierContract,
)
from .SupplierRelationshipManagement.SupplierCatalogs import (  # noqa: F401
    SupplierCatalog,
    SupplierCatalogItem,
)
from .SupplierRelationshipManagement.SupplierRiskAssessments import (  # noqa: F401
    SupplierRiskAssessment,
)

# 4.3 Inventory Management — the spine (owned here ships-first, L29/L36) + domain tables
from .InventoryManagement.Items import (  # noqa: F401
    ItemCategory,
    UOM,
    Item,
)
from .InventoryManagement.Locations import (  # noqa: F401
    Location,
)
from .InventoryManagement.LotSerials import (  # noqa: F401
    LotSerial,
)
from .InventoryManagement.StockMoves import (  # noqa: F401
    StockMove,
)
from .InventoryManagement.StockTransfers import (  # noqa: F401
    StockTransfer,
    StockTransferLine,
)
from .InventoryManagement.StockAdjustments import (  # noqa: F401
    StockAdjustment,
    StockAdjustmentLine,
)
from .InventoryManagement.ReorderRules import (  # noqa: F401
    ReorderRule,
)

# 4.4 Warehouse Management
from .WarehouseManagement.PutawayTasks import (  # noqa: F401
    PutawayTask,
)
from .WarehouseManagement.PickTasks import (  # noqa: F401
    PickTask,
    PickTaskLine,
)
from .WarehouseManagement.CycleCountTasks import (  # noqa: F401
    CycleCountTask,
    CycleCountTaskLine,
)
from .WarehouseManagement.YardVisits import (  # noqa: F401
    YardVisit,
)

# 4.5 Order Management System (OMS)
from .OrderManagement.SalesOrders import (  # noqa: F401
    SalesOrder,
    SalesOrderLine,
)
from .OrderManagement.SalesOrderAllocations import (  # noqa: F401
    SalesOrderAllocation,
)

# 4.6 Transportation Management System (TMS)
from .TransportationManagement.Carriers import (  # noqa: F401
    Carrier,
    CarrierRateCard,
)
from .TransportationManagement.Loads import (  # noqa: F401
    Load,
    LoadStop,
)
from .TransportationManagement.Shipments import (  # noqa: F401
    Shipment,
    TrackingEvent,
)
from .TransportationManagement.FreightInvoices import (  # noqa: F401
    FreightInvoice,
    FreightInvoiceLine,
)

# 4.7 Demand Planning & Forecasting
# SeasonalityProfiles FIRST — DemandForecast and 4.3's extended ReorderRule both point at it.
from .DemandPlanning.SeasonalityProfiles import (  # noqa: F401
    SeasonalityProfile,
    SeasonalityIndex,
)
from .DemandPlanning.DemandForecasts import (  # noqa: F401
    DemandForecast,
    DemandForecastPeriod,
)
from .DemandPlanning.DemandSignals import (  # noqa: F401
    DemandSignal,
)
from .DemandPlanning.ForecastAdjustments import (  # noqa: F401
    ForecastAdjustment,
)

# 4.8 Manufacturing / Production
# WorkCenters FIRST — BillOfMaterials.default_work_center and WorkOrder.work_center both point at
# it. BillsOfMaterials before WorkOrders for the same reason (WorkOrder.bom).
from .Manufacturing.WorkCenters import (  # noqa: F401
    WorkCenter,
)
from .Manufacturing.BillsOfMaterials import (  # noqa: F401
    BillOfMaterials,
    BOMLine,
)
from .Manufacturing.WorkOrders import (  # noqa: F401
    WorkOrder,
    WorkOrderComponent,
)
from .Manufacturing.ProductionTimeLogs import (  # noqa: F401
    ProductionTimeLog,
)

# 4.9 Quality Management System (QMS)
# InspectionPlans FIRST — QualityInspection.plan and QualityAudit.checklist_plan both point at it,
# and InspectionResult reuses InspectionCharacteristic's choice tuple for its snapshot column.
# QualityAudits before NonConformances because an audit FINDING *is* a NonConformance row
# (source="audit"), and NonConformances before CapaActions for the same reason one level down.
from .QualityManagement.InspectionPlans import (  # noqa: F401
    InspectionPlan,
    InspectionCharacteristic,
)
from .QualityManagement.QualityInspections import (  # noqa: F401
    QualityInspection,
    InspectionResult,
)
from .QualityManagement.QualityAudits import (  # noqa: F401
    QualityAudit,
)
from .QualityManagement.NonConformances import (  # noqa: F401
    NonConformance,
)
from .QualityManagement.CapaActions import (  # noqa: F401
    CapaAction,
    CapaTask,
)

# 4.10 Returns Management (Reverse Logistics)
# ReturnReasons FIRST — it owns the shared DISPOSITION_CHOICES vocabulary that ReturnDispositions
# imports, and ReturnAuthorizations imports CREDIT_BEARING_DISPOSITIONS from it too. The dependency
# runs one way (ReturnReasons imports none of its siblings), so there is no cycle. ReturnPolicies
# before ReturnAuthorizations for readability — the RMA snapshots a policy verdict — and
# WarrantyClaims last because a claim can point at an RMA.
from .ReturnsManagement.ReturnReasons import (  # noqa: F401
    ReturnReason,
    DISPOSITION_CHOICES,
    DECIDED_DISPOSITION_CHOICES,
    CREDIT_BEARING_DISPOSITIONS,
)
from .ReturnsManagement.ReturnPolicies import (  # noqa: F401
    ReturnPolicy,
    select_policy,
    evaluate_return_eligibility,
)
from .ReturnsManagement.ReturnAuthorizations import (  # noqa: F401
    ReturnAuthorization,
    ReturnLine,
)
from .ReturnsManagement.ReturnDispositions import (  # noqa: F401
    ReturnDisposition,
)
from .ReturnsManagement.WarrantyClaims import (  # noqa: F401
    WarrantyClaim,
    WarrantyClaimCost,
)

# 4.11 Supply Chain Analytics
# _choices FIRST — it owns the closed metric catalog and every shared vocabulary, and all three
# entity modules import from it. It deliberately imports no sibling model, so the edge runs one way
# and there is no cycle (the 4.10 ReturnReasons-first precedent).
#
# It also exists to keep apps/scm/analytics.py importable: that module reads the models to aggregate
# over 4.1-4.10, so KpiTarget.metric cannot take its `choices` from analytics without closing a loop.
# Splitting the vocabulary out is the same fix apps/crm already shipped
# (models/AnalyticsReporting/_choices.py vs apps/crm/analytics.py).
from .SupplyChainAnalytics._choices import (  # noqa: F401
    METRIC_META,
    METRIC_CHOICES,
    METRIC_LABELS,
    METRIC_GROUP_CHOICES,
    METRIC_GROUP_PAGES,
    METRIC_UNIT_CHOICES,
    SCOPE_CHOICES,
    SCOPE_FIELDS,
    DIRECTION_CHOICES,
    PERIOD_GRAIN_CHOICES,
    DATE_RANGE_CHOICES,
    SEVERITY_CHOICES,
    BAND_CHOICES,
    ALERT_TYPE_CHOICES,
    ALERT_STATUS_CHOICES,
    OPEN_ALERT_STATUSES,
)
from .SupplyChainAnalytics.KpiTargets import (  # noqa: F401
    KpiTarget,
)
from .SupplyChainAnalytics.KpiSnapshots import (  # noqa: F401
    KpiSnapshot,
    format_metric_value,
)
from .SupplyChainAnalytics.SupplyChainAlerts import (  # noqa: F401
    SupplyChainAlert,
)

# --- 4.12 Contract & Compliance Management ---------------------------------------------------
# Dependency order, for the reader rather than for Django: every FK below is declared by string,
# so the import order genuinely does not matter to the ORM. TradeLicense comes first because both
# ComplianceRequirement and TradeDocument point at it.
from .ContractCompliance._choices import *  # noqa: F401,F403
from .ContractCompliance.TradeLicenses import (  # noqa: F401
    TradeLicense,
)
from .ContractCompliance.ComplianceRequirements import (  # noqa: F401
    ComplianceRequirement,
    ComplianceCheck,
)
from .ContractCompliance.TradeDocuments import (  # noqa: F401
    TradeDocument,
    TradeDocumentLine,
)
from .ContractCompliance.SustainabilityAssessments import (  # noqa: F401
    SustainabilityAssessment,
)

# --- 4.13 Asset Management --------------------------------------------------------------------
# _choices FIRST — it owns the vocabularies read from more than one direction (criticality,
# priority, work type, the Maximo failure hierarchy, the meter source) and it deliberately imports
# no sibling model, so the edge runs one way and there is no cycle (the 4.10 ReturnReasons-first /
# 4.11 _choices-first precedent).
#
# Assets before the rest, for the reader rather than for Django: every FK below is declared by
# string so the ORM does not care, but MaintenancePlan, MaintenanceWorkOrder and MeterReading all
# point at scm.Asset, and Asset.maintenance_cost_to_date() reaches MaintenanceWorkOrderPart through
# a LOCAL import for exactly this reason.
from .AssetManagement._choices import *  # noqa: F401,F403
from .AssetManagement.Assets import (  # noqa: F401
    Asset,
    AssetSparePart,
)
from .AssetManagement.MaintenancePlans import (  # noqa: F401
    MaintenancePlan,
    MaintenancePlanTask,
)
from .AssetManagement.MaintenanceWorkOrders import (  # noqa: F401
    MaintenanceWorkOrder,
    MaintenanceWorkOrderPart,
    MaintenanceWorkOrderTask,
)
from .AssetManagement.MeterReadings import (  # noqa: F401
    MeterReading,
)

# --- 4.14 Labor Management --------------------------------------------------------------------
# _choices FIRST and BY NAME, not `import *`. 4.13's AssetManagement/_choices is star-imported a few
# lines above and already exports MAX_LABOUR_RATE; a second star-imported _choices re-declaring a
# shared token would silently shadow it, and which one won would depend on import order. Spelling
# every name out makes that collision a visible edit rather than a runtime coin-flip — 4.14's rate
# ceiling is deliberately the distinct token MAX_STANDARD_RATE (a standard's charge-out rate, never a
# person's wage; hrm owns compensation and scm does not read it).
#
# LaborStandard before the rest, for the reader rather than for Django: every FK below is declared by
# string so the ORM does not care, but LaborActivity snapshots a standard's determinants at file time
# and LaborPlanLine records which standard produced its number, so the standard is what the other two
# are measured against.
#
# `select_standard` is exported alongside its model, exactly as `select_policy` is at :191 — the
# resolver IS the public interface (most-specific-wins, and None when nothing matches), and a caller
# that reaches for LaborStandard.objects directly has almost certainly got the precedence wrong.
#
# 4.14 declares NO task table and adds NO column to 4.4's PickTask / PutawayTask / CycleCountTask:
# those already carry an assignee and lifecycle stamps, so Task Assignment is a console over them.
from .LaborManagement._choices import (  # noqa: F401
    ACTIVITY_CHOICES,
    ACTIVITY_CSS,
    COACHING_THRESHOLD_PCT,
    DIRECT_ACTIVITIES,
    INDIRECT_ACTIVITIES,
    INDIRECT_REASON_CHOICES,
    MAX_ACTIVITY_MINUTES,
    MAX_ALLOWANCE_PCT,
    MAX_BULK_ASSIGN,
    MAX_HORIZON_PERIODS,
    MAX_HOURS_PER_SHIFT,
    MAX_PLAN_LINES,
    MAX_PRODUCTIVITY_PCT,
    MAX_SESSION_MINUTES,
    MAX_STANDARD_RATE,
    MIN_PLAN_YEAR,
    MIN_RANKED_MINUTES,
    PLAN_BUCKET_CHOICES,
    PLAN_METHOD_CHOICES,
    PLAN_STATUS_CHOICES,
    PLAN_STATUS_CSS,
    SESSION_SOURCE_CHOICES,
    SESSION_STATUS_CHOICES,
    SESSION_STATUS_CSS,
    STANDARD_BASIS_CHOICES,
    STANDARD_SOURCE_CHOICES,
    VOLUME_SOURCE_CHOICES,
)
from .LaborManagement.LaborStandards import (  # noqa: F401
    LaborStandard,
    select_standard,
)
from .LaborManagement.LaborSessions import (  # noqa: F401
    LaborSession,
)
from .LaborManagement.LaborActivities import (  # noqa: F401
    LaborActivity,
)
from .LaborManagement.LaborPlans import (  # noqa: F401
    LaborPlan,
    LaborPlanLine,
)
