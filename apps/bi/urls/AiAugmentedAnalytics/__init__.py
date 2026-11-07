from apps.bi.urls.AiAugmentedAnalytics.AugmentedInsights import (
    urlpatterns as insight_urls,
)
from apps.bi.urls.AiAugmentedAnalytics.SmartDataPrepSuggestions import (
    urlpatterns as prep_urls,
)
from apps.bi.urls.AiAugmentedAnalytics.TextSentimentAnalyses import (
    urlpatterns as sentiment_urls,
)
from apps.bi.urls.AiAugmentedAnalytics.AnalyticsRecommendations import (
    urlpatterns as recommendation_urls,
)

urlpatterns = insight_urls + prep_urls + sentiment_urls + recommendation_urls
