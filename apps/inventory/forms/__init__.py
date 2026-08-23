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
from .LotSerialTracking.LotNumberRules import (
    GenerateLotForm,
    LotNumberRuleForm,
    ShelfLifePolicyForm,
)
from .PurchaseOrderManagement.ApprovalRules import PurchaseOrderApprovalRuleForm
from .PurchaseOrderManagement.Dispatches import PurchaseOrderDispatchForm
from .ReceivingPutaway.PutawayRules import PutawayRuleForm
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

__all__ = ["ItemAttributeForm", "ItemPriceForm", "ProductFileForm", "VendorCommunicationForm",
           "FulfillmentWaveForm", "FulfillmentWaveOrderForm",
           "PurchaseOrderApprovalRuleForm", "PurchaseOrderDispatchForm",
           "PutawayRuleForm",
           "BinCapacityForm", "CrossDockOrderForm",
           "StockStatusForm", "InventoryReservationForm",
           "LotNumberRuleForm", "ShelfLifePolicyForm", "GenerateLotForm",
           "CountProgramForm", "PhysicalInventoryForm",
           "TransferRouteForm", "TransferApprovalRuleForm",
           "ReturnInspectionForm", "ReturnInspectionChecklistForm",
           "ReturnInspectionChecklistFormSet", "DispositionRoutingRuleForm"]

