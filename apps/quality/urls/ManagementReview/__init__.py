from apps.quality.urls.ManagementReview.ManagementReviewActions import (
    urlpatterns as management_review_actions_urls,
)
from apps.quality.urls.ManagementReview.ManagementReviewInputs import (
    urlpatterns as management_review_inputs_urls,
)
from apps.quality.urls.ManagementReview.ManagementReviews import (
    urlpatterns as management_reviews_urls,
)
from apps.quality.urls.ManagementReview.QualityObjectives import (
    urlpatterns as quality_objectives_urls,
)
from apps.quality.urls.ManagementReview.QualityPlanningDashboard import (
    urlpatterns as quality_planning_dashboard_urls,
)

urlpatterns = (
    quality_planning_dashboard_urls
    + quality_objectives_urls
    + management_reviews_urls
    + management_review_inputs_urls
    + management_review_actions_urls
)
