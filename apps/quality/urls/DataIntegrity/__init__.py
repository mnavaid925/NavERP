from apps.quality.urls.DataIntegrity.AuditTrailReviews import (
    urlpatterns as audit_trail_reviews_urls,
)
from apps.quality.urls.DataIntegrity.DataIntegrityAssessments import (
    urlpatterns as data_integrity_assessments_urls,
)
from apps.quality.urls.DataIntegrity.DataIntegrityDashboard import (
    urlpatterns as data_integrity_dashboard_urls,
)
from apps.quality.urls.DataIntegrity.ElectronicRecordPolicies import (
    urlpatterns as electronic_record_policies_urls,
)
from apps.quality.urls.DataIntegrity.SystemChangeControls import (
    urlpatterns as system_change_controls_urls,
)

urlpatterns = (
    electronic_record_policies_urls
    + data_integrity_assessments_urls
    + audit_trail_reviews_urls
    + system_change_controls_urls
    + data_integrity_dashboard_urls
)
