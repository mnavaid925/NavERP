"""Sales 8.10 — IncentiveCompensation URLs package."""
from apps.sales.urls.IncentiveCompensation.CommissionAdjustments import (
    urlpatterns as commission_adjustment_urls,
)
from apps.sales.urls.IncentiveCompensation.CommissionBoards import (
    urlpatterns as commission_boards_urls,
)
from apps.sales.urls.IncentiveCompensation.CommissionEarnings import (
    urlpatterns as commission_earning_urls,
)
from apps.sales.urls.IncentiveCompensation.CommissionPlans import (
    urlpatterns as commission_plan_urls,
)
from apps.sales.urls.IncentiveCompensation.CommissionStatements import (
    urlpatterns as commission_statement_urls,
)

urlpatterns = (
    commission_boards_urls
    + commission_plan_urls
    + commission_earning_urls
    + commission_statement_urls
    + commission_adjustment_urls
)
