"""Inventory 5.7 Stock Movement & Transfers — views."""
from .ApprovalRules import (
    transferapprovalrule_create,
    transferapprovalrule_delete,
    transferapprovalrule_detail,
    transferapprovalrule_edit,
    transferapprovalrule_list,
)
from .TransferRoutes import (
    transferroute_create,
    transferroute_delete,
    transferroute_detail,
    transferroute_edit,
    transferroute_list,
)
from .Transfers import (
    transfer_board,
    transfer_detail_panel,
    transfer_queue,
    transfer_submit,
    transfer_tier_approve,
    transfer_tier_reject,
)

__all__ = [
    "transfer_board", "transfer_queue", "transfer_detail_panel",
    "transfer_submit", "transfer_tier_approve", "transfer_tier_reject",
    "transferroute_list", "transferroute_detail", "transferroute_create",
    "transferroute_edit", "transferroute_delete",
    "transferapprovalrule_list", "transferapprovalrule_detail",
    "transferapprovalrule_create", "transferapprovalrule_edit",
    "transferapprovalrule_delete",
]
