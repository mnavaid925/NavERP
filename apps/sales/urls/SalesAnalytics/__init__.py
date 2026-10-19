"""Sales 8.12 — SalesAnalytics URLs package re-exports."""
from apps.sales.urls.SalesAnalytics.WinLossDebriefs import urlpatterns as _win_loss_debriefs
from apps.sales.urls.SalesAnalytics.StageVelocityAnalyses import urlpatterns as _stage_velocity_analyses

urlpatterns = [
    *_win_loss_debriefs,
    *_stage_velocity_analyses,
]
