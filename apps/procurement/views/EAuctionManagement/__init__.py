"""Procurement 6.7 E-Auction Management views."""
from .Auctions import (
    eauc_board,
    eauc_cancel,
    eauc_close,
    eauc_console,
    eauc_create,
    eauc_delete,
    eauc_detail,
    eauc_edit,
    eauc_floor,
    eauc_invite_add,
    eauc_invite_remove,
    eauc_list,
    eauc_publish,
    eauc_rules,
)
from .Bids import eauc_award, eauc_bid, eauc_results

__all__ = [
    "eauc_list",
    "eauc_detail",
    "eauc_create",
    "eauc_edit",
    "eauc_delete",
    "eauc_publish",
    "eauc_cancel",
    "eauc_close",
    "eauc_invite_add",
    "eauc_invite_remove",
    "eauc_floor",
    "eauc_rules",
    "eauc_console",
    "eauc_board",
    "eauc_bid",
    "eauc_results",
    "eauc_award",
]
