"""Sales 8.12 — SalesAnalytics views package re-exports."""
from apps.sales.views.SalesAnalytics.WinLossDebriefs import (
    win_loss_debrief_create,
    win_loss_debrief_delete,
    win_loss_debrief_detail,
    win_loss_debrief_edit,
    win_loss_debrief_list,
)

__all__ = [
    "win_loss_debrief_list",
    "win_loss_debrief_create",
    "win_loss_debrief_detail",
    "win_loss_debrief_edit",
    "win_loss_debrief_delete",
]
