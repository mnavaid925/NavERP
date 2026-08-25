from .Approvals import urlpatterns as _awe_approvals
from .Delegations import urlpatterns as _awe_delegations
from .Escalations import urlpatterns as _awe_escalations
from .RoutingRules import urlpatterns as _awe_routingrules

urlpatterns = [
    *_awe_routingrules,
    *_awe_approvals,
    *_awe_delegations,
    *_awe_escalations,
]
