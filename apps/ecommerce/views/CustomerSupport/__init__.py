from apps.ecommerce.views.CustomerSupport.CustomerSatisfactionSurveys import (
    customersatisfactionsurvey_create,
    customersatisfactionsurvey_delete,
    customersatisfactionsurvey_detail,
    customersatisfactionsurvey_edit,
    customersatisfactionsurvey_list,
)
from apps.ecommerce.views.CustomerSupport.CustomerSupportTickets import (
    customersupportticket_create,
    customersupportticket_delete,
    customersupportticket_detail,
    customersupportticket_edit,
    customersupportticket_list,
)
from apps.ecommerce.views.CustomerSupport.KnowledgeBaseArticles import (
    knowledgebasearticle_create,
    knowledgebasearticle_delete,
    knowledgebasearticle_detail,
    knowledgebasearticle_edit,
    knowledgebasearticle_list,
)
from apps.ecommerce.views.CustomerSupport.OrderIssueClaims import (
    orderissueclaim_create,
    orderissueclaim_delete,
    orderissueclaim_detail,
    orderissueclaim_edit,
    orderissueclaim_list,
)

__all__ = [
    # CustomerSupportTickets
    "customersupportticket_list",
    "customersupportticket_detail",
    "customersupportticket_create",
    "customersupportticket_edit",
    "customersupportticket_delete",
    # KnowledgeBaseArticles
    "knowledgebasearticle_list",
    "knowledgebasearticle_detail",
    "knowledgebasearticle_create",
    "knowledgebasearticle_edit",
    "knowledgebasearticle_delete",
    # OrderIssueClaims
    "orderissueclaim_list",
    "orderissueclaim_detail",
    "orderissueclaim_create",
    "orderissueclaim_edit",
    "orderissueclaim_delete",
    # CustomerSatisfactionSurveys
    "customersatisfactionsurvey_list",
    "customersatisfactionsurvey_detail",
    "customersatisfactionsurvey_create",
    "customersatisfactionsurvey_edit",
    "customersatisfactionsurvey_delete",
]
