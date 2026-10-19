"""Sales 8.12 — SalesAnalytics URLs package re-exports."""
from apps.sales.urls.SalesAnalytics.WinLossDebriefs import urlpatterns as _win_loss_debriefs

urlpatterns = [
    *_win_loss_debriefs,
]
