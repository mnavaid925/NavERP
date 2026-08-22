"""Inventory models package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every model so ``from apps.inventory.models import ItemPrice`` works everywhere
(admin, seeder, tests). Imports inside the entity modules are ABSOLUTE.
"""
from .Catalog.ItemAttributes import ItemAttribute
from .Catalog.ItemPrices import ItemPrice
from .Catalog.ProductFiles import ProductFile
from .PurchaseOrderManagement.ApprovalRules import PurchaseOrderApprovalRule
from .PurchaseOrderManagement.Approvals import PurchaseOrderApproval
from .PurchaseOrderManagement.Dispatches import PurchaseOrderDispatch
from .VendorSupplierManagement.VendorCommunications import VendorCommunication

__all__ = ["ItemAttribute", "ItemPrice", "ProductFile", "VendorCommunication",
           "PurchaseOrderApprovalRule", "PurchaseOrderApproval", "PurchaseOrderDispatch"]
