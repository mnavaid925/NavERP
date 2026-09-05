"""Procurement 6.17 Risk & Compliance Management — FraudAlert URL patterns.

One first segment, ``fraud-alerts/``, checked as a whole path COMPONENT against the concatenated
inventory in ``apps/procurement/urls/__init__.py``. It is not a prefix of any existing segment —
Django matches path components, not strings, so ``fraud-alerts`` and ``fraud-alert-anything``
could never collide anyway — and no route in this app uses a converter in its FIRST path
component, so nothing outside this module can shadow it. Re-check it against the concurrently
built 6.16 / 6.18 / 6.19 segments before wiring (L43).

Django is first-match-wins, so **every literal route is declared before the ``<int:pk>/`` one it
would otherwise fall into** — here that is ``fraud-alerts/add/``.

``delete/`` and ``disposition/`` are POST-only AND admin-gated through their view decorators; the
list and detail pages carry ``{% csrf_token %}`` forms with an ``onsubmit`` confirm rather than a
confirmation template. Unlike the risk-signal review verb next door, ``disposition/`` IS
admin-gated: this register holds accusations about named people.

All four disposition transitions share ONE route. The action arrives in the POST body and is
validated against ``FraudDispositionForm``'s whitelist (L11), which keeps the URLconf from
growing a route per verb and keeps the guard in one place.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("fraud-alerts/", views.fraudalert_list, name="fraudalert_list"),
    # Literal before <int:pk> — first-match-wins IS behaviour.
    path("fraud-alerts/add/", views.fraudalert_create, name="fraudalert_create"),
    path("fraud-alerts/<int:pk>/", views.fraudalert_detail, name="fraudalert_detail"),
    path("fraud-alerts/<int:pk>/edit/", views.fraudalert_edit, name="fraudalert_edit"),
    path("fraud-alerts/<int:pk>/delete/", views.fraudalert_delete, name="fraudalert_delete"),
    # The disposition verb — @tenant_admin_required + @require_POST on the view, one route for
    # all four actions, which arrive as the POST's ``action`` and are validated there.
    path("fraud-alerts/<int:pk>/disposition/", views.fraudalert_disposition,
         name="fraudalert_disposition"),
]
