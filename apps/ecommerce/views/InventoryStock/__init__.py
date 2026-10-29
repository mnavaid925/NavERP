from apps.ecommerce.views.InventoryStock.BackorderPolicies import (
    backorderpolicy_create,
    backorderpolicy_delete,
    backorderpolicy_detail,
    backorderpolicy_edit,
    backorderpolicy_list,
)
from apps.ecommerce.views.InventoryStock.ChannelInventorySyncs import (
    channelinventorysync_create,
    channelinventorysync_delete,
    channelinventorysync_detail,
    channelinventorysync_edit,
    channelinventorysync_list,
    channelinventorysync_trigger,
)
from apps.ecommerce.views.InventoryStock.FulfillmentCenters import (
    fulfillmentcenter_create,
    fulfillmentcenter_delete,
    fulfillmentcenter_detail,
    fulfillmentcenter_edit,
    fulfillmentcenter_list,
)
from apps.ecommerce.views.InventoryStock.InventoryAllocations import (
    inventoryallocation_adjust,
    inventoryallocation_create,
    inventoryallocation_delete,
    inventoryallocation_detail,
    inventoryallocation_edit,
    inventoryallocation_list,
)
from apps.ecommerce.views.InventoryStock.Operations import inventory_operations

__all__ = [
    "inventory_operations",
    # FulfillmentCenter
    "fulfillmentcenter_list",
    "fulfillmentcenter_detail",
    "fulfillmentcenter_create",
    "fulfillmentcenter_edit",
    "fulfillmentcenter_delete",
    # InventoryAllocation
    "inventoryallocation_list",
    "inventoryallocation_detail",
    "inventoryallocation_create",
    "inventoryallocation_edit",
    "inventoryallocation_adjust",
    "inventoryallocation_delete",
    # BackorderPolicy
    "backorderpolicy_list",
    "backorderpolicy_detail",
    "backorderpolicy_create",
    "backorderpolicy_edit",
    "backorderpolicy_delete",
    # ChannelInventorySync
    "channelinventorysync_list",
    "channelinventorysync_detail",
    "channelinventorysync_create",
    "channelinventorysync_edit",
    "channelinventorysync_trigger",
    "channelinventorysync_delete",
]
