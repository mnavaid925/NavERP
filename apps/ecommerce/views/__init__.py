from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope
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
from apps.ecommerce.views.ProductCatalog.BulkOperations import (
    product_export_csv,
    product_import_csv,
)
from apps.ecommerce.views.ProductCatalog.CatalogProducts import (
    catalogproduct_create,
    catalogproduct_delete,
    catalogproduct_detail,
    catalogproduct_edit,
    catalogproduct_list,
    catalogproduct_publish,
)
from apps.ecommerce.views.ProductCatalog.Overview import catalog_overview
from apps.ecommerce.views.ProductCatalog.ProductRelationships import (
    productrelationship_create,
    productrelationship_delete,
    productrelationship_detail,
    productrelationship_edit,
    productrelationship_list,
)
from apps.ecommerce.views.ProductCatalog.ProductVariants import (
    productvariant_create,
    productvariant_delete,
    productvariant_detail,
    productvariant_edit,
    productvariant_list,
)
from apps.ecommerce.views.ProductCatalog.StoreCategories import (
    storecategory_create,
    storecategory_delete,
    storecategory_detail,
    storecategory_edit,
    storecategory_list,
)

__all__ = [
    "ecommerce_scope",
    "ecommerce_object",
    # 9.1 Product Catalog
    "storecategory_list",
    "storecategory_create",
    "storecategory_detail",
    "storecategory_edit",
    "storecategory_delete",
    "catalogproduct_list",
    "catalogproduct_create",
    "catalogproduct_detail",
    "catalogproduct_edit",
    "catalogproduct_delete",
    "catalogproduct_publish",
    "productvariant_list",
    "productvariant_create",
    "productvariant_detail",
    "productvariant_edit",
    "productvariant_delete",
    "productrelationship_list",
    "productrelationship_create",
    "productrelationship_detail",
    "productrelationship_edit",
    "productrelationship_delete",
    "product_import_csv",
    "product_export_csv",
    "catalog_overview",
    # 9.2 Inventory & Stock Management
    "inventory_operations",
    "fulfillmentcenter_list",
    "fulfillmentcenter_detail",
    "fulfillmentcenter_create",
    "fulfillmentcenter_edit",
    "fulfillmentcenter_delete",
    "inventoryallocation_list",
    "inventoryallocation_detail",
    "inventoryallocation_create",
    "inventoryallocation_edit",
    "inventoryallocation_adjust",
    "inventoryallocation_delete",
    "backorderpolicy_list",
    "backorderpolicy_detail",
    "backorderpolicy_create",
    "backorderpolicy_edit",
    "backorderpolicy_delete",
    "channelinventorysync_list",
    "channelinventorysync_detail",
    "channelinventorysync_create",
    "channelinventorysync_edit",
    "channelinventorysync_trigger",
    "channelinventorysync_delete",
]

