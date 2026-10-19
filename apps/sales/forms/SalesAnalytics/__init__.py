"""Sales 8.12 — SalesAnalytics forms package re-exports."""
from apps.sales.forms.SalesAnalytics.WinLossDebriefs import WinLossDebriefForm
from apps.sales.forms.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysisForm

__all__ = [
    "WinLossDebriefForm",
    "StageVelocityAnalysisForm",
]
