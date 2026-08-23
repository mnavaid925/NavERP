"""Inventory 5.12 Multi-Location Management — view modules.

Re-exports everything the sub-package owns so the app-root ``views/__init__.py``
and any leaf-path importer resolve the same function objects: the five
``locationnetwork_*`` CRUD wrappers live in ``LocationNetworks.py``, the one
computed page (plus its frozen in-flight vocabulary) in ``GlobalStock.py`` —
the WarehouseMap precedent of one entity file per computed view.
"""
from .GlobalStock import IN_FLIGHT_STATUSES, global_stock
from .LocationNetworks import (
    locationnetwork_create,
    locationnetwork_delete,
    locationnetwork_detail,
    locationnetwork_edit,
    locationnetwork_list,
)

__all__ = [
    "IN_FLIGHT_STATUSES",
    "global_stock",
    "locationnetwork_create",
    "locationnetwork_delete",
    "locationnetwork_detail",
    "locationnetwork_edit",
    "locationnetwork_list",
]
