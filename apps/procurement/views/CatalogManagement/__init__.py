"""Procurement 6.9 Catalog Management views — one module per entity.

Re-exported by the app-level views package so ``views.<name>`` resolves in the URLconf.
"""
from .CatalogItems import (
    catalog_item_approve,
    catalog_item_block,
    catalog_item_create,
    catalog_item_delete,
    catalog_item_detail,
    catalog_item_edit,
    catalog_item_list,
    catalog_item_reject,
    catalog_item_submit,
)
from .PunchOutEndpoints import (
    punchout_endpoint_create,
    punchout_endpoint_delete,
    punchout_endpoint_detail,
    punchout_endpoint_edit,
    punchout_endpoint_list,
    punchout_endpoint_test,
)
from .Tiers import (
    catalog_tier_approve,
    catalog_tier_create,
    catalog_tier_delete,
    catalog_tier_detail,
    catalog_tier_edit,
    catalog_tier_list,
    catalog_tier_retire,
)
from .UploadBatches import (
    catalog_upload_create,
    catalog_upload_delete,
    catalog_upload_detail,
    catalog_upload_edit,
    catalog_upload_list,
    catalog_upload_publish,
    catalog_upload_reject,
    catalog_upload_validate,
)

__all__ = [
    "catalog_item_list", "catalog_item_detail", "catalog_item_create",
    "catalog_item_edit", "catalog_item_delete", "catalog_item_submit",
    "catalog_item_approve", "catalog_item_reject", "catalog_item_block",
    "catalog_tier_list", "catalog_tier_detail", "catalog_tier_create",
    "catalog_tier_edit", "catalog_tier_delete", "catalog_tier_approve",
    "catalog_tier_retire",
    "punchout_endpoint_list", "punchout_endpoint_detail", "punchout_endpoint_create",
    "punchout_endpoint_edit", "punchout_endpoint_delete", "punchout_endpoint_test",
    "catalog_upload_list", "catalog_upload_detail", "catalog_upload_create",
    "catalog_upload_edit", "catalog_upload_delete", "catalog_upload_validate",
    "catalog_upload_publish", "catalog_upload_reject",
]
