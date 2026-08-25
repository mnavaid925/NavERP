"""Procurement 6.5 Sourcing & Tendering — url re-exports."""
from .Analytics import urlpatterns as _st_analytics
from .AwardBoard import urlpatterns as _st_awards
from .Bids import urlpatterns as _st_bids
from .SourcingEvents import urlpatterns as _st_events

urlpatterns = [
    *_st_events,      # sourcing events (CRUD + open/close/cancel/award)
    *_st_bids,        # bids (register + scoring matrix + lifecycle verbs)
    *_st_awards,      # computed award-recommendation board
    *_st_analytics,   # computed post-event analytics
]
