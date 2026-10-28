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
]
