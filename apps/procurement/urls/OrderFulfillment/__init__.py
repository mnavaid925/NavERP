"""Procurement 6.11 Order Fulfillment & Tracking URL patterns — one module per entity.

Five NEW first segments, all distinct whole components: ``asn/``, ``delivery-schedules/``,
``backorders/``, ``inbound-tracking/`` and ``delivery-confirmation/``. Django resolves
first-match-wins, and within each module the literal routes (``add/``, ``split/``) are declared
before the ``<int:pk>/`` ones.
"""
from .AdvancedShipmentNotice import urlpatterns as _of_asn
from .Backorder import urlpatterns as _of_backorders
from .DeliverySchedule import urlpatterns as _of_schedules
from .FulfillmentBoards import urlpatterns as _of_boards

urlpatterns = [
    *_of_asn,        # 6.11 ASN register + submit/in-transit/confirm-delivery/cancel verbs
    *_of_schedules,  # 6.11 split-delivery instalments (+ the split console)
    *_of_backorders,  # 6.11 shortfall register + reschedule/fulfil/cancel/raise-alert
    *_of_boards,     # 6.11 computed boards: inbound freight tracking, delivery confirmation
]
