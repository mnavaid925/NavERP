"""SCM 4.12 Contract & Compliance — TradeLicense routes (prefix ``trade-licenses/``).

COLLISION CHECK — ``trade-licenses/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: no existing ``scm`` first segment starts with ``trade``. It is a distinct
whole path component from 4.12's own ``trade-documents/`` — Django matches whole path components and
never splits one at the hyphen, so neither can shadow the other, and neither may be "tidied" to look
like the other.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "licence 'add' not found". Every verb route sits
under its own ``<int:pk>/`` and is POST-only at the view, so a GET to one is a 405 rather than a
silent state change. This module introduces NO greedy ``<str:…>`` converter — 4.10's
``return-tracking/<str:token>/`` remains the app's only one.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("trade-licenses/", views.tradelicense_list, name="tradelicense_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("trade-licenses/add/", views.tradelicense_create, name="tradelicense_create"),
    path("trade-licenses/<int:pk>/", views.tradelicense_detail, name="tradelicense_detail"),
    path("trade-licenses/<int:pk>/edit/", views.tradelicense_edit, name="tradelicense_edit"),
    path("trade-licenses/<int:pk>/delete/", views.tradelicense_delete, name="tradelicense_delete"),
    # The application ladder: draft -> submitted -> approved, with revoke reachable from approved.
    path("trade-licenses/<int:pk>/submit/", views.tradelicense_submit, name="tradelicense_submit"),
    path("trade-licenses/<int:pk>/approve/", views.tradelicense_approve,
         name="tradelicense_approve"),
    path("trade-licenses/<int:pk>/revoke/", views.tradelicense_revoke, name="tradelicense_revoke"),
    # Re-derives the consumed balance from the trade documents actually issued under this licence.
    # A POST rather than a GET: it writes, even though it only ever writes a derived figure.
    path("trade-licenses/<int:pk>/recompute/", views.tradelicense_recompute,
         name="tradelicense_recompute"),
]
