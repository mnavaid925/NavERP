"""Inventory forms package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every form so ``from apps.inventory.forms import X`` resolves.
"""
from .Catalog.ItemAttributes import ItemAttributeForm
from .Catalog.ItemPrices import ItemPriceForm
from .Catalog.ProductFiles import ProductFileForm
from .FulfillmentOrchestration.FulfillmentWaves import (
    FulfillmentWaveForm,
    FulfillmentWaveOrderForm,
)
from .InventoryTrackingControl.InventoryReservations import InventoryReservationForm
from .InventoryTrackingControl.StockStatuses import StockStatusForm
from .StocktakingCycleCounting.CountPrograms import (
    CountProgramForm,
    PhysicalInventoryForm,
)
from .ForecastingPlanning.StockLevelPlans import StockLevelPlanForm
from .LotSerialTracking.LotNumberRules import (
    GenerateLotForm,
    LotNumberRuleForm,
    ShelfLifePolicyForm,
)
from .MultiLocationManagement.LocationNetworks import LocationNetworkForm
from .PurchaseOrderManagement.ApprovalRules import PurchaseOrderApprovalRuleForm
from .PurchaseOrderManagement.Dispatches import PurchaseOrderDispatchForm
from .ReceivingPutaway.PutawayRules import PutawayRuleForm
from .BarcodeRfidIntegration import (
    BarcodeLabelForm,
    ScanSessionForm,
    RfidTagForm,
)
from .AlertsNotifications import AlertRuleForm
from .AccountingFinancialIntegration import GLPostRuleForm, TaxRuleForm
from .QualityControl import (
    DefectReportForm,
    QcChecklistForm,
    QcChecklistItemForm,
    QcChecklistItemFormSet,
    QcRoutingRuleForm,
    QuarantineOrderForm,
)
from .ReturnsManagement import (
    DispositionRoutingRuleForm,
    ReturnInspectionChecklistForm,
    ReturnInspectionChecklistFormSet,
    ReturnInspectionForm,
)
from .StockMovementTransfers import TransferApprovalRuleForm, TransferRouteForm
from .VendorSupplierManagement.VendorCommunications import VendorCommunicationForm
from .WarehousingBinManagement.BinCapacities import BinCapacityForm
from .WarehousingBinManagement.CrossDockOrders import CrossDockOrderForm
from .ReportingAnalytics.ReportSnapshots import ReportSnapshotForm
from .ThirdPartyIntegrations import (
    ApiClientForm,
    ChannelListingMapForm,
    IntegrationChannelForm,
)

__all__ = ["ItemAttributeForm", "ItemPriceForm", "ProductFileForm", "VendorCommunicationForm",
           "FulfillmentWaveForm", "FulfillmentWaveOrderForm",
           "PurchaseOrderApprovalRuleForm", "PurchaseOrderDispatchForm",
           "PutawayRuleForm",
           "BinCapacityForm", "CrossDockOrderForm",
           "StockStatusForm", "InventoryReservationForm",
           "LotNumberRuleForm", "ShelfLifePolicyForm", "GenerateLotForm",
           "LocationNetworkForm",
           "StockLevelPlanForm",
           "CountProgramForm", "PhysicalInventoryForm",
           "TransferRouteForm", "TransferApprovalRuleForm",
           "ReturnInspectionForm", "ReturnInspectionChecklistForm",
           "ReturnInspectionChecklistFormSet", "DispositionRoutingRuleForm",
           "BarcodeLabelForm", "ScanSessionForm", "RfidTagForm",
           "AlertRuleForm",
           "TaxRuleForm", "GLPostRuleForm",
           "QcChecklistForm", "QcChecklistItemForm", "QcChecklistItemFormSet",
           "QcRoutingRuleForm", "QuarantineOrderForm", "DefectReportForm",
           "ReportSnapshotForm",
           "IntegrationChannelForm", "ChannelListingMapForm", "ApiClientForm"]

