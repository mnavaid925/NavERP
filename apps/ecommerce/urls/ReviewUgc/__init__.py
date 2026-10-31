from apps.ecommerce.urls.ReviewUgc.ProductQuestionAnswers import (
    urlpatterns as productquestionanswers_patterns,
)
from apps.ecommerce.urls.ReviewUgc.ProductReviews import (
    urlpatterns as productreviews_patterns,
)
from apps.ecommerce.urls.ReviewUgc.ReviewSentimentSummaries import (
    urlpatterns as reviewsentimentsummaries_patterns,
)
from apps.ecommerce.urls.ReviewUgc.VisualUgcMedia import (
    urlpatterns as visualugcmedia_patterns,
)

urlpatterns = (
    productreviews_patterns
    + productquestionanswers_patterns
    + visualugcmedia_patterns
    + reviewsentimentsummaries_patterns
)
