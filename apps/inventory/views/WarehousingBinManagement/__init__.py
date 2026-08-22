"""Inventory 5.5 Warehousing & Bin Management — views.

CRUD for the two entities plus the computed warehouse-map page. The cross-dock
lifecycle actions (receive / ship / cancel) live beside their CRUD: each is a POST-only
route that delegates to the model's locked action method and surfaces its refusal as a
flash message instead of an unhandled ValidationError.
"""
from .BinCapacities import (
    bincapacity_create,
    bincapacity_delete,
    bincapacity_detail,
    bincapacity_edit,
    bincapacity_list,
)
from .CrossDockOrders import (
    crossdockorder_cancel,
    crossdockorder_create,
    crossdockorder_delete,
    crossdockorder_detail,
    crossdockorder_edit,
    crossdockorder_list,
    crossdockorder_receive,
    crossdockorder_ship,
)
from .WarehouseMap import warehousemap

__all__ = [
    "bincapacity_list", "bincapacity_detail", "bincapacity_create",
    "bincapacity_edit", "bincapacity_delete",
    "crossdockorder_list", "crossdockorder_detail", "crossdockorder_create",
    "crossdockorder_edit", "crossdockorder_delete",
    "crossdockorder_receive", "crossdockorder_ship", "crossdockorder_cancel",
    "warehousemap",
]
