from apps.bi.urls.OperationalReporting.ReportDefinitions import (
    urlpatterns as report_definition_urls,
)
from apps.bi.urls.OperationalReporting.ReportDrillPaths import (
    urlpatterns as report_drill_path_urls,
)
from apps.bi.urls.OperationalReporting.ReportExecutions import (
    urlpatterns as report_execution_urls,
)
from apps.bi.urls.OperationalReporting.ReportParameters import (
    urlpatterns as report_parameter_urls,
)

urlpatterns = (
    report_definition_urls
    + report_parameter_urls
    + report_execution_urls
    + report_drill_path_urls
)
