"""Inventory AlertsNotifications URL patterns package (Sub-module 5.16).

Literal segments (`run-detection/`, `rules/`, `deliveries/`) precede the `<int:pk>`
routes inside each module, so first-match-wins is safe; the app introduces no greedy
`<str:…>` converter.
"""
from .AlertRules import urlpatterns as _an_rules
from .InventoryAlerts import urlpatterns as _an_alerts
from .NotificationDeliveries import urlpatterns as _an_deliveries

urlpatterns = [
    *_an_alerts,      # inventory alerts (inbox + triage verbs + run detection)
    *_an_rules,       # watch-rule catalog CRUD
    *_an_deliveries,  # append-only dispatch log
]
