"""Sales 8.9 — SalesEnablement URLs package."""
from apps.sales.urls.SalesEnablement.CoachingScorecards import (
    urlpatterns as coaching_scorecard_urls,
)
from apps.sales.urls.SalesEnablement.EnablementBoards import (
    urlpatterns as enablement_boards_urls,
)
from apps.sales.urls.SalesEnablement.EnablementContents import (
    urlpatterns as enablement_content_urls,
)
from apps.sales.urls.SalesEnablement.SalesCertifications import (
    urlpatterns as sales_certification_urls,
)
from apps.sales.urls.SalesEnablement.SalesPlaybooks import (
    urlpatterns as sales_playbook_urls,
)

urlpatterns = (
    enablement_boards_urls
    + enablement_content_urls
    + sales_playbook_urls
    + sales_certification_urls
    + coaching_scorecard_urls
)
