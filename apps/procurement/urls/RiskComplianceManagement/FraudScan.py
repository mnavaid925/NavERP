"""Procurement 6.17 Risk & Compliance Management — fraud scan / fraud board URL patterns.

Two first segments, ``fraud-scan/`` and ``fraud-board/``, each checked as a whole path COMPONENT
against the concatenated inventory in ``apps/procurement/urls/__init__.py`` and against
``fraud-alerts/`` next door. None is a prefix of any other segment — Django matches path
components, not strings — and no route in this app uses a converter in its FIRST path component,
so nothing outside these modules can shadow them. Re-check all three against the concurrently
built 6.16 / 6.18 / 6.19 segments before wiring (L43).

Both routes are page-level and take no arguments, so there is no literal-before-``<int:pk>``
ordering question here.

``fraud-scan/`` answers **both GET and POST on the one route**, and the POST leg alone is
admin-gated — inside the view rather than by a decorator, because a decorator would also hide the
read-only thresholds and the not-buildable note from every non-admin, which are exactly the
things everybody should be able to read. The route is therefore NOT ``@require_POST``, and the
view's GET leg writes nothing.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # GET renders the window form + the read-only tuning constants + the not-buildable note;
    # POST runs FraudAlert.scan() and is refused for a non-admin inside the view.
    path("fraud-scan/", views.fraud_scan, name="fraud_scan"),
    path("fraud-board/", views.fraud_board, name="fraud_board"),
]
