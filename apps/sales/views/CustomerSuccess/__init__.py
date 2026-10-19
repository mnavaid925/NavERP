"""Sales 8.11 — CustomerSuccess views package re-exports."""
from apps.sales.views.CustomerSuccess.CustomerBusinessReviews import (
    customer_advocacy_hub,
    customer_business_review_create,
    customer_business_review_delete,
    customer_business_review_detail,
    customer_business_review_edit,
    customer_business_review_list,
    customer_qbr_studio,
)
from apps.sales.views.CustomerSuccess.CustomerHealthScores import (
    customer_health_console,
    customer_health_score_create,
    customer_health_score_delete,
    customer_health_score_detail,
    customer_health_score_edit,
    customer_health_score_list,
)
from apps.sales.views.CustomerSuccess.CustomerOnboardings import (
    customer_onboarding_create,
    customer_onboarding_delete,
    customer_onboarding_detail,
    customer_onboarding_edit,
    customer_onboarding_hub,
    customer_onboarding_list,
)
from apps.sales.views.CustomerSuccess.CustomerRenewals import (
    customer_renewal_create,
    customer_renewal_delete,
    customer_renewal_detail,
    customer_renewal_edit,
    customer_renewal_list,
    customer_renewal_pipeline,
)

__all__ = [
    "customer_health_score_list",
    "customer_health_score_create",
    "customer_health_score_detail",
    "customer_health_score_edit",
    "customer_health_score_delete",
    "customer_health_console",
    "customer_renewal_list",
    "customer_renewal_create",
    "customer_renewal_detail",
    "customer_renewal_edit",
    "customer_renewal_delete",
    "customer_renewal_pipeline",
    "customer_onboarding_list",
    "customer_onboarding_create",
    "customer_onboarding_detail",
    "customer_onboarding_edit",
    "customer_onboarding_delete",
    "customer_onboarding_hub",
    "customer_business_review_list",
    "customer_business_review_create",
    "customer_business_review_detail",
    "customer_business_review_edit",
    "customer_business_review_delete",
    "customer_qbr_studio",
    "customer_advocacy_hub",
]
