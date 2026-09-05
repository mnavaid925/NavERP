"""Procurement 6.17 Risk & Compliance Management — SupplierRiskSignal URL patterns.

Two first segments, both collision-checked as whole components against the concatenated
inventory in ``apps/procurement/urls/__init__.py``: ``risk-signals/`` and ``risk-refresh-due/``.
Neither is a prefix of any existing segment — Django matches path components, not strings — and
this app registers no greedy ``<str:…>`` converter anywhere, so there is nothing that could
shadow either. Re-check both against the concurrently-built 6.16 / 6.18 / 6.19 segments before
wiring (L43).

Django is first-match-wins, so **every literal route is declared before the ``<int:pk>/`` one it
would otherwise fall into** — here that is ``risk-signals/add/``.

``risk-signals/<int:pk>/`` MUST stay in step with
``apps.procurement.models.RiskComplianceManagement.RiskSignals.alert_link``, which builds the
``ProcurementAlert.link_url`` a raised deterioration points at. It reverses this name and falls
back to the literal path only while this URLconf is unwired, so the two agree in both directions
— but a rename here needs the fallback string changed with it.

``delete/`` and ``review/`` are POST-only through their view decorators; the list and detail
pages carry ``{% csrf_token %}`` forms with an ``onsubmit`` confirm rather than a confirmation
template. ``review/`` is deliberately NOT admin-gated (see the view).
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("risk-signals/", views.risksignal_list, name="risksignal_list"),
    # Literal before <int:pk> — first-match-wins IS behaviour.
    path("risk-signals/add/", views.risksignal_create, name="risksignal_create"),
    path("risk-signals/<int:pk>/", views.risksignal_detail, name="risksignal_detail"),
    path("risk-signals/<int:pk>/edit/", views.risksignal_edit, name="risksignal_edit"),
    path("risk-signals/<int:pk>/delete/", views.risksignal_delete, name="risksignal_delete"),
    # The review verb — @require_POST on the view, one route for all three actions, which arrive
    # as the POST's ``action`` and are validated against a whitelist there (L11).
    path("risk-signals/<int:pk>/review/", views.risksignal_review, name="risksignal_review"),
    path("risk-refresh-due/", views.risksignal_refresh_board, name="risksignal_refresh_board"),
]
