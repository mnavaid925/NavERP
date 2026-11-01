from apps.ecommerce.urls.CustomerSupport.CustomerSatisfactionSurveys import (
    urlpatterns as customersatisfactionsurveys_patterns,
)
from apps.ecommerce.urls.CustomerSupport.CustomerSupportTickets import (
    urlpatterns as customersupporttickets_patterns,
)
from apps.ecommerce.urls.CustomerSupport.KnowledgeBaseArticles import (
    urlpatterns as knowledgebasearticles_patterns,
)
from apps.ecommerce.urls.CustomerSupport.OrderIssueClaims import (
    urlpatterns as orderissueclaims_patterns,
)

urlpatterns = (
    customersupporttickets_patterns
    + knowledgebasearticles_patterns
    + orderissueclaims_patterns
    + customersatisfactionsurveys_patterns
)
