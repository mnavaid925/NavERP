from apps.ecommerce.views.ReviewUgc.ProductQuestionAnswers import (
    productquestionanswer_create,
    productquestionanswer_delete,
    productquestionanswer_detail,
    productquestionanswer_edit,
    productquestionanswer_list,
    productquestionanswer_respond,
)
from apps.ecommerce.views.ReviewUgc.ProductReviews import (
    productreview_create,
    productreview_delete,
    productreview_detail,
    productreview_edit,
    productreview_list,
    productreview_moderate,
)
from apps.ecommerce.views.ReviewUgc.ReviewSentimentSummaries import (
    reviewsentimentsummary_create,
    reviewsentimentsummary_delete,
    reviewsentimentsummary_detail,
    reviewsentimentsummary_edit,
    reviewsentimentsummary_list,
    reviewsentimentsummary_recalculate,
)
from apps.ecommerce.views.ReviewUgc.VisualUgcMedia import (
    visualugcmedia_create,
    visualugcmedia_delete,
    visualugcmedia_detail,
    visualugcmedia_edit,
    visualugcmedia_list,
)

__all__ = [
    # ProductReviews
    "productreview_list",
    "productreview_detail",
    "productreview_create",
    "productreview_edit",
    "productreview_delete",
    "productreview_moderate",
    # ProductQuestionAnswers
    "productquestionanswer_list",
    "productquestionanswer_detail",
    "productquestionanswer_create",
    "productquestionanswer_edit",
    "productquestionanswer_delete",
    "productquestionanswer_respond",
    # VisualUgcMedia
    "visualugcmedia_list",
    "visualugcmedia_detail",
    "visualugcmedia_create",
    "visualugcmedia_edit",
    "visualugcmedia_delete",
    # ReviewSentimentSummaries
    "reviewsentimentsummary_list",
    "reviewsentimentsummary_detail",
    "reviewsentimentsummary_create",
    "reviewsentimentsummary_edit",
    "reviewsentimentsummary_delete",
    "reviewsentimentsummary_recalculate",
]
