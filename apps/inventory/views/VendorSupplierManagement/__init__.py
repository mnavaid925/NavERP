"""Inventory 5.2 Vendor / Supplier Management views."""
from .VendorCommunications import (
    vendorcommunication_create,
    vendorcommunication_delete,
    vendorcommunication_detail,
    vendorcommunication_edit,
    vendorcommunication_list,
)

__all__ = [
    "vendorcommunication_list", "vendorcommunication_detail", "vendorcommunication_create",
    "vendorcommunication_edit", "vendorcommunication_delete",
]
