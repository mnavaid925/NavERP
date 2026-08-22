"""Inventory views package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every view so the URLconf's ``views.<name>`` resolves.
"""
from .Catalog.ItemAttributes import (
    itemattribute_create,
    itemattribute_delete,
    itemattribute_detail,
    itemattribute_edit,
    itemattribute_list,
)
from .Catalog.ItemPrices import (
    itemprice_create,
    itemprice_delete,
    itemprice_detail,
    itemprice_edit,
    itemprice_list,
)
from .Catalog.Overview import overview
from .Catalog.ProductFiles import (
    productfile_create,
    productfile_delete,
    productfile_detail,
    productfile_edit,
    productfile_list,
)
from .PurchaseOrderManagement.ApprovalRules import (
    approvalrule_create,
    approvalrule_delete,
    approvalrule_detail,
    approvalrule_edit,
    approvalrule_list,
)
from .PurchaseOrderManagement.Approvals import (
    approval_queue,
    approval_tier_approve,
    approval_tier_reject,
)
from .PurchaseOrderManagement.Dispatches import (
    dispatch_create,
    dispatch_delete,
    dispatch_detail,
    dispatch_list,
)
from .PurchaseOrderManagement.ReorderDrafts import reorderdraft
from .VendorSupplierManagement.VendorCommunications import (
    vendorcommunication_create,
    vendorcommunication_delete,
    vendorcommunication_detail,
    vendorcommunication_edit,
    vendorcommunication_list,
)
from .WarehousingBinManagement.BinCapacities import (
    bincapacity_create,
    bincapacity_delete,
    bincapacity_detail,
    bincapacity_edit,
    bincapacity_list,
)
from .WarehousingBinManagement.CrossDockOrders import (
    crossdockorder_cancel,
    crossdockorder_create,
    crossdockorder_delete,
    crossdockorder_detail,
    crossdockorder_edit,
    crossdockorder_list,
    crossdockorder_receive,
    crossdockorder_ship,
)
from .WarehousingBinManagement.WarehouseMap import warehousemap

__all__ = [
    "overview",
    "itemattribute_list", "itemattribute_detail", "itemattribute_create",
    "itemattribute_edit", "itemattribute_delete",
    "itemprice_list", "itemprice_detail", "itemprice_create",
    "itemprice_edit", "itemprice_delete",
    "productfile_list", "productfile_detail", "productfile_create",
    "productfile_edit", "productfile_delete",
    "vendorcommunication_list", "vendorcommunication_detail", "vendorcommunication_create",
    "vendorcommunication_edit", "vendorcommunication_delete",
    "approvalrule_list", "approvalrule_detail", "approvalrule_create",
    "approvalrule_edit", "approvalrule_delete",
    "approval_queue", "approval_tier_approve", "approval_tier_reject",
    "dispatch_list", "dispatch_detail", "dispatch_create", "dispatch_delete",
    "reorderdraft",
    "bincapacity_list", "bincapacity_detail", "bincapacity_create",
    "bincapacity_edit", "bincapacity_delete",
    "crossdockorder_list", "crossdockorder_detail", "crossdockorder_create",
    "crossdockorder_edit", "crossdockorder_delete",
    "crossdockorder_receive", "crossdockorder_ship", "crossdockorder_cancel",
    "warehousemap",
]
