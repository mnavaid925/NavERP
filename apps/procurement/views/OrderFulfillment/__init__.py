"""Procurement 6.11 Order Fulfillment & Tracking views — one module per entity.

Re-exported by the app-level views package so ``views.<name>`` resolves in the URLconf. A view
missing from this block is an ``AttributeError`` raised at URLconf import — i.e. every page in
the app 500s, not just the one that was forgotten.

``FulfillmentBoards.py`` holds the two read-only computed boards (``inbound_tracking``,
``delivery_confirmation``); it has no models or forms of its own by design.
"""
from .AdvancedShipmentNotice import (
    asn_cancel,
    asn_confirm_delivery,
    asn_create,
    asn_delete,
    asn_detail,
    asn_edit,
    asn_list,
    asn_mark_in_transit,
    asn_submit,
)
from .Backorder import (
    backorder_cancel,
    backorder_create,
    backorder_delete,
    backorder_detail,
    backorder_edit,
    backorder_fulfil,
    backorder_list,
    backorder_raise_alert,
    backorder_reschedule,
)
from .DeliverySchedule import (
    deliveryschedule_create,
    deliveryschedule_delete,
    deliveryschedule_detail,
    deliveryschedule_edit,
    deliveryschedule_list,
    deliveryschedule_split,
)
from .FulfillmentBoards import delivery_confirmation, inbound_tracking

__all__ = [
    "asn_list",
    "asn_detail",
    "asn_create",
    "asn_edit",
    "asn_delete",
    "asn_submit",
    "asn_mark_in_transit",
    "asn_confirm_delivery",
    "asn_cancel",
    "deliveryschedule_list",
    "deliveryschedule_detail",
    "deliveryschedule_create",
    "deliveryschedule_edit",
    "deliveryschedule_delete",
    "deliveryschedule_split",
    "backorder_list",
    "backorder_detail",
    "backorder_create",
    "backorder_edit",
    "backorder_delete",
    "backorder_reschedule",
    "backorder_fulfil",
    "backorder_cancel",
    "backorder_raise_alert",
    "inbound_tracking",
    "delivery_confirmation",
]
