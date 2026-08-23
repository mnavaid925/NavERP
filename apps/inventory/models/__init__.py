"""Inventory models package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every model so ``from apps.inventory.models import ItemPrice`` works everywhere
(admin, seeder, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .Catalog.ItemAttributes import ItemAttribute
from .Catalog.ItemPrices import ItemPrice
from .Catalog.ProductFiles import ProductFile
from .InventoryTrackingControl.InventoryReservations import InventoryReservation
from .InventoryTrackingControl.StockStatuses import StockStatus
from .LotSerialTracking.LotNumberRules import LotNumberRule
from .LotSerialTracking.ShelfLifePolicies import FLAG_CSS, ShelfLifePolicy, classify_lot
from .PurchaseOrderManagement.ApprovalRules import PurchaseOrderApprovalRule
from .PurchaseOrderManagement.Approvals import PurchaseOrderApproval
from .PurchaseOrderManagement.Dispatches import PurchaseOrderDispatch
from .ReceivingPutaway.PutawayRules import PutawayRule, resolve_putaway_suggestion
from .StockMovementTransfers import (
    APPLIES_TO_CHOICES,
    SCOPE_ALL,
    SCOPE_INTER,
    SCOPE_INTRA,
    TransferApproval,
    TransferApprovalRule,
    TransferRoute,
)
from .VendorSupplierManagement.VendorCommunications import VendorCommunication
from .WarehousingBinManagement.BinCapacities import BinCapacity
from .WarehousingBinManagement.CrossDockOrders import CrossDockOrder

__all__ = ["ItemAttribute", "ItemPrice", "ProductFile", "VendorCommunication",
           "PurchaseOrderApprovalRule", "PurchaseOrderApproval", "PurchaseOrderDispatch",
           "PutawayRule", "resolve_putaway_suggestion",
           "BinCapacity", "CrossDockOrder",
           "StockStatus", "InventoryReservation",
           "LotNumberRule", "ShelfLifePolicy", "classify_lot", "FLAG_CSS",
           "TransferRoute", "TransferApprovalRule", "TransferApproval",
           "APPLIES_TO_CHOICES", "SCOPE_ALL", "SCOPE_INTER", "SCOPE_INTRA"]
