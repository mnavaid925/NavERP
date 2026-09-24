from .LeadManagement.Overview import urlpatterns as _overview
from .LeadManagement.LeadScoreEvents import urlpatterns as _score_events
from .LeadManagement.LeadQualifications import urlpatterns as _qualifications
from .LeadManagement.LeadRoutingRules import urlpatterns as _routing_rules
from .LeadManagement.LeadNurtureEnrollments import urlpatterns as _nurture

app_name = "sales"

urlpatterns = [
    *_overview,
    *_score_events,
    *_qualifications,
    *_routing_rules,
    *_nurture,
]
