from apps.quality.urls.LimsManagement.LabSamples import (
    urlpatterns as lab_samples_urls,
)
from apps.quality.urls.LimsManagement.LabSpecifications import (
    urlpatterns as lab_specifications_urls,
)
from apps.quality.urls.LimsManagement.LabTestWorksheets import (
    urlpatterns as lab_test_worksheets_urls,
)
from apps.quality.urls.LimsManagement.LimsDashboard import (
    urlpatterns as lims_dashboard_urls,
)
from apps.quality.urls.LimsManagement.OosInvestigations import (
    urlpatterns as oos_investigations_urls,
)

urlpatterns = (
    lims_dashboard_urls
    + lab_samples_urls
    + lab_specifications_urls
    + lab_test_worksheets_urls
    + oos_investigations_urls
)
