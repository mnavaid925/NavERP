from django.urls import include, path

urlpatterns = [
    path("", include("apps.assets.urls.AssetAnalytics.PortfolioDashboards")),
    path("", include("apps.assets.urls.AssetAnalytics.AssetLifecycleCostAnalyses")),
    path("", include("apps.assets.urls.AssetAnalytics.AssetReplacementPlans")),
    path("", include("apps.assets.urls.AssetAnalytics.AssetPortfolioScenarios")),
    path("", include("apps.assets.urls.AssetAnalytics.AssetExecutiveScorecards")),
]
