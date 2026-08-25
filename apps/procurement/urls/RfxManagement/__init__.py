"""Procurement 6.6 RFx Management URL patterns."""
from .Events import urlpatterns as _rfx_events
from .Responses import urlpatterns as _rfx_responses

urlpatterns = [
    *_rfx_events,      # 6.6 event register/builder/lifecycle + compare + library + scoring
    *_rfx_responses,   # 6.6 response repository + scoring workspace + evaluation lifecycle
]
