"""Procurement 6.8 Contract Management — url re-exports."""
from .Amendments import urlpatterns as _cm_amendments
from .Clauses import urlpatterns as _cm_clauses
from .Contracts import urlpatterns as _cm_contracts
from .Milestones import urlpatterns as _cm_milestones

urlpatterns = [
    *_cm_clauses,      # 6.8 clause library (authoring & templating)
    *_cm_contracts,    # register + authoring workspace + public token sign page
    *_cm_amendments,   # amendment tracking (file/approve/reject)
    *_cm_milestones,   # obligation milestones + renewal/expiration board + Run
]
