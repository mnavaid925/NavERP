from apps.ecommerce.urls.B2bWholesale.B2bCompanyAccounts import (
    urlpatterns as company_urls,
)
from apps.ecommerce.urls.B2bWholesale.B2bCompanyUsers import (
    urlpatterns as user_urls,
)
from apps.ecommerce.urls.B2bWholesale.B2bQuoteRequests import (
    urlpatterns as quote_urls,
)
from apps.ecommerce.urls.B2bWholesale.B2bQuickOrderTemplates import (
    urlpatterns as template_urls,
)
from apps.ecommerce.urls.B2bWholesale.B2bWholesaleHub import (
    urlpatterns as hub_urls,
)

urlpatterns = [
    *hub_urls,
    *company_urls,
    *user_urls,
    *quote_urls,
    *template_urls,
]
