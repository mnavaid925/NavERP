"""Sales 8.12 — SalesAnalytics URLs package re-exports."""
from apps.sales.urls.SalesAnalytics.AnalyticsConsoles import urlpatterns as _analytics_consoles
from apps.sales.urls.SalesAnalytics.WinLossDebriefs import urlpatterns as _win_loss_debriefs
from apps.sales.urls.SalesAnalytics.StageVelocityAnalyses import urlpatterns as _stage_velocity_analyses
from apps.sales.urls.SalesAnalytics.FunnelConversionRecords import urlpatterns as _funnel_conversion_records
from apps.sales.urls.SalesAnalytics.RepPerformanceScorecards import urlpatterns as _rep_performance_scorecards

urlpatterns = [
    *_analytics_consoles,
    *_win_loss_debriefs,
    *_stage_velocity_analyses,
    *_funnel_conversion_records,
    *_rep_performance_scorecards,
]
