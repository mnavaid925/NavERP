from apps.ecommerce.views.Personalization.AudienceSegments import (
    audiencesegment_create,
    audiencesegment_delete,
    audiencesegment_detail,
    audiencesegment_edit,
    audiencesegment_list,
    audiencesegment_recalculate,
    audiencesegment_toggle,
)
from apps.ecommerce.views.Personalization.PersonalizationConsole import (
    personalization_console,
    recommendation_simulate,
)
from apps.ecommerce.views.Personalization.PersonalizedExperiences import (
    personalizedexperience_create,
    personalizedexperience_delete,
    personalizedexperience_detail,
    personalizedexperience_edit,
    personalizedexperience_list,
    personalizedexperience_toggle,
)
from apps.ecommerce.views.Personalization.RecommendationStrategies import (
    recommendationstrategy_create,
    recommendationstrategy_delete,
    recommendationstrategy_detail,
    recommendationstrategy_edit,
    recommendationstrategy_list,
    recommendationstrategy_toggle,
)
from apps.ecommerce.views.Personalization.ShopperBehaviorEvents import (
    shopperbehaviorevent_delete,
    shopperbehaviorevent_detail,
    shopperbehaviorevent_list,
)

__all__ = [
    "audiencesegment_list",
    "audiencesegment_detail",
    "audiencesegment_create",
    "audiencesegment_edit",
    "audiencesegment_delete",
    "audiencesegment_toggle",
    "audiencesegment_recalculate",
    "recommendationstrategy_list",
    "recommendationstrategy_detail",
    "recommendationstrategy_create",
    "recommendationstrategy_edit",
    "recommendationstrategy_delete",
    "recommendationstrategy_toggle",
    "personalizedexperience_list",
    "personalizedexperience_detail",
    "personalizedexperience_create",
    "personalizedexperience_edit",
    "personalizedexperience_delete",
    "personalizedexperience_toggle",
    "shopperbehaviorevent_list",
    "shopperbehaviorevent_detail",
    "shopperbehaviorevent_delete",
    "personalization_console",
    "recommendation_simulate",
]
