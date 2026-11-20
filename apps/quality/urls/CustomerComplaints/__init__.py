from apps.quality.urls.CustomerComplaints.ComplaintInvestigations import (
    urlpatterns as complaint_investigation_urls,
)
from apps.quality.urls.CustomerComplaints.ComplaintTrendingDashboard import (
    urlpatterns as complaint_trending_urls,
)
from apps.quality.urls.CustomerComplaints.CustomerComplaints import (
    urlpatterns as customer_complaint_urls,
)
from apps.quality.urls.CustomerComplaints.FieldActions import (
    urlpatterns as field_action_urls,
)
from apps.quality.urls.CustomerComplaints.RegulatoryReports import (
    urlpatterns as regulatory_report_urls,
)

urlpatterns = (
    complaint_trending_urls
    + customer_complaint_urls
    + complaint_investigation_urls
    + regulatory_report_urls
    + field_action_urls
)
