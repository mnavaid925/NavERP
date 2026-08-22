"""Inventory forms package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every form so ``from apps.inventory.forms import X`` resolves.
"""
from .Catalog.ItemAttributes import ItemAttributeForm
from .Catalog.ItemPrices import ItemPriceForm
from .Catalog.ProductFiles import ProductFileForm
from .PurchaseOrderManagement.ApprovalRules import PurchaseOrderApprovalRuleForm
from .PurchaseOrderManagement.Dispatches import PurchaseOrderDispatchForm
from .VendorSupplierManagement.VendorCommunications import VendorCommunicationForm
from .WarehousingBinManagement.BinCapacities import BinCapacityForm
from .WarehousingBinManagement.CrossDockOrders import CrossDockOrderForm

__all__ = ["ItemAttributeForm", "ItemPriceForm", "ProductFileForm", "VendorCommunicationForm",
           "PurchaseOrderApprovalRuleForm", "PurchaseOrderDispatchForm",
           "BinCapacityForm", "CrossDockOrderForm"]
