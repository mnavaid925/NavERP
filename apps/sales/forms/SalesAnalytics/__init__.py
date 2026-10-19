"""Sales 8.12 — SalesAnalytics forms package re-exports."""
from apps.sales.forms.SalesAnalytics.WinLossDebriefs import WinLossDebriefForm
from apps.sales.forms.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysisForm
from apps.sales.forms.SalesAnalytics.FunnelConversionRecords import FunnelConversionRecordForm
from apps.sales.forms.SalesAnalytics.RepPerformanceScorecards import RepPerformanceScorecardForm

__all__ = [
    "WinLossDebriefForm",
    "StageVelocityAnalysisForm",
    "FunnelConversionRecordForm",
    "RepPerformanceScorecardForm",
]
