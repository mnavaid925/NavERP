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

__all__ = [
    "overview",
    "itemattribute_list", "itemattribute_detail", "itemattribute_create",
    "itemattribute_edit", "itemattribute_delete",
    "itemprice_list", "itemprice_detail", "itemprice_create",
    "itemprice_edit", "itemprice_delete",
    "productfile_list", "productfile_detail", "productfile_create",
    "productfile_edit", "productfile_delete",
]
