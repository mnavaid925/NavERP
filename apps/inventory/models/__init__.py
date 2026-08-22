"""Inventory models package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every model so ``from apps.inventory.models import ItemPrice`` works everywhere
(admin, seeder, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .Catalog.ItemAttributes import ItemAttribute
from .Catalog.ItemPrices import ItemPrice
from .Catalog.ProductFiles import ProductFile
from .InventoryTrackingControl.InventoryReservations import InventoryReservation
from .InventoryTrackingControl.StockStatuses import StockStatus
from .PurchaseOrderManagement.ApprovalRules import PurchaseOrderApprovalRule
from .PurchaseOrderManagement.Approvals import PurchaseOrderApproval
from .PurchaseOrderManagement.Dispatches import PurchaseOrderDispatch
from .ReceivingPutaway.PutawayRules import PutawayRule, resolve_putaway_suggestion
from .VendorSupplierManagement.VendorCommunications import VendorCommunication
from .WarehousingBinManagement.BinCapacities import BinCapacity
from .WarehousingBinManagement.CrossDockOrders import CrossDockOrder

__all__ = ["ItemAttribute", "ItemPrice", "ProductFile", "VendorCommunication",
           "PurchaseOrderApprovalRule", "PurchaseOrderApproval", "PurchaseOrderDispatch",
           "PutawayRule", "resolve_putaway_suggestion",
           "BinCapacity", "CrossDockOrder",
           "StockStatus", "InventoryReservation"]
