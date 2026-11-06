from apps.bi.urls.PerformanceScorecards.KpiDefinitions import urlpatterns as kpi_urls
from apps.bi.urls.PerformanceScorecards.PerformanceScorecards import urlpatterns as scorecard_urls
from apps.bi.urls.PerformanceScorecards.ScorecardKpiAssignments import urlpatterns as assignment_urls
from apps.bi.urls.PerformanceScorecards.StrategicObjectives import urlpatterns as objective_urls

urlpatterns = [
    *kpi_urls,
    *scorecard_urls,
    *assignment_urls,
    *objective_urls,
]
