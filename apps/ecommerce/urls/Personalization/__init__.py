from apps.ecommerce.urls.Personalization.AudienceSegments import (
    urlpatterns as audience_segment_urls,
)
from apps.ecommerce.urls.Personalization.PersonalizationConsole import (
    urlpatterns as personalization_console_urls,
)
from apps.ecommerce.urls.Personalization.PersonalizedExperiences import (
    urlpatterns as personalized_experience_urls,
)
from apps.ecommerce.urls.Personalization.RecommendationStrategies import (
    urlpatterns as recommendation_strategy_urls,
)
from apps.ecommerce.urls.Personalization.ShopperBehaviorEvents import (
    urlpatterns as shopper_behavior_event_urls,
)

urlpatterns = (
    audience_segment_urls
    + recommendation_strategy_urls
    + personalized_experience_urls
    + shopper_behavior_event_urls
    + personalization_console_urls
)
