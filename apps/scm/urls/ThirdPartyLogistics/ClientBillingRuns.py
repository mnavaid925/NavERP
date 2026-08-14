"""SCM 4.17 Third-Party Logistics (3PL) Management — ``ClientBillingRun`` routes.

Full CRUD plus the four-rung verb ladder (``calculate → approve → draft-invoice``, and ``void``),
plus three routes for the manual charge lines.

COLLISION CHECK — checked against the WHOLE concatenated urlconf rather than against this block
alone: **nothing anywhere in ``apps/scm`` starts with ``client``.** ``client-billing-runs`` and
``client-billing-run-lines`` are two DISTINCT whole path components; Django matches whole components
and never splits one at a hyphen, so neither can shadow the other and neither may ever be "tidied"
to look like the other — one identifies a run, the other identifies a charge on a run. Near
neighbours that are NOT collisions, checked rather than assumed: 4.17's own ``logistics-clients/``,
``client-rate-cards/``, ``client-slas/``, ``client-inventory/`` and ``client-space/``; 4.11's
``logistics-kpis/``; 4.16's ``portal-*``; 4.10's ``return-portal/``; 4.2's ``contracts/``.

This module introduces NO greedy ``<str:…>`` converter — 4.10's ``return-tracking/<str:token>/``
remains the app's only one.

ORDER IS BEHAVIOUR. ``add/`` is LITERAL and stays above the ``<int:pk>/`` block: Django is
first-match-wins, and although the ``int`` converter would refuse to match ``add`` today, the
convention is what keeps a later ``<str:…>`` route from swallowing the create page and 404-ing as
"billing run 'add' not found".

**The line routes are split on purpose, and the split is a security decision, not a style one.**
``client-billing-runs/<int:pk>/lines/add/`` nests under the PARENT because the run has to come from
the ROUTE — a parent pk in a POST body is how a caller grafts a charge onto another workspace's
invoice (the 4.15 ``cold-chain-monitors/<int:pk>/readings/add/`` precedent). ``edit`` and ``delete``
take the LINE's own pk instead, because the child pk already identifies the row and nesting it would
invite a caller to pair a real child with somebody else's parent id (the 4.12 ``compliance-checks/``
rationale). Both are scoped through ``run__tenant=request.tenant`` at the view regardless.

Every verb route is POST-only AT THE VIEW, so a GET to one is a 405 rather than a silent state
change; ``approve/`` and ``draft-invoice/`` are additionally ``@tenant_admin_required`` (L27).
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("client-billing-runs/", views.clientbillingrun_list, name="clientbillingrun_list"),
    # LITERAL — must stay above the <int:pk> block below.
    path("client-billing-runs/add/", views.clientbillingrun_create, name="clientbillingrun_create"),

    path("client-billing-runs/<int:pk>/", views.clientbillingrun_detail,
         name="clientbillingrun_detail"),
    path("client-billing-runs/<int:pk>/edit/", views.clientbillingrun_edit,
         name="clientbillingrun_edit"),
    path("client-billing-runs/<int:pk>/delete/", views.clientbillingrun_delete,
         name="clientbillingrun_delete"),

    # --- the verb ladder: draft → calculated → approved → invoiced (void from the first two) ---
    path("client-billing-runs/<int:pk>/calculate/", views.clientbillingrun_calculate,
         name="clientbillingrun_calculate"),
    path("client-billing-runs/<int:pk>/approve/", views.clientbillingrun_approve,
         name="clientbillingrun_approve"),
    path("client-billing-runs/<int:pk>/draft-invoice/", views.clientbillingrun_draft_invoice,
         name="clientbillingrun_draft_invoice"),
    path("client-billing-runs/<int:pk>/void/", views.clientbillingrun_void,
         name="clientbillingrun_void"),

    # --- manual charge lines ---
    # NESTED: pk is the RUN. The parent comes from the route, never from the POST body.
    path("client-billing-runs/<int:pk>/lines/add/", views.clientbillingrunline_create,
         name="clientbillingrunline_create"),
    # OWN pk: pk is the LINE. A separate first segment, so nothing above can shadow these.
    path("client-billing-run-lines/<int:pk>/edit/", views.clientbillingrunline_edit,
         name="clientbillingrunline_edit"),
    path("client-billing-run-lines/<int:pk>/delete/", views.clientbillingrunline_delete,
         name="clientbillingrunline_delete"),
]
