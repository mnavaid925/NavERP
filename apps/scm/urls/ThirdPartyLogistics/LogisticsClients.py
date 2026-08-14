"""SCM 4.17 Third-Party Logistics (3PL) — ``LogisticsClient`` routes (prefix ``logistics-clients/``).

The depositor master: one row per company whose goods we store and handle. It is the ROOT of the
sub-module — a tariff, a billing run and an SLA all point back at it — and it is the target of the
**Client Integration** sidebar bullet.

**4.17 has NO client-facing surface**, so there is deliberately no portal route, no token route and
no login-gated page anywhere in this module (L32: a staff bullet may never target a customer page,
and the customer-facing portal is 4.16's). Every route below is staff-only and ``@login_required``.

COLLISION CHECK — ``logistics-clients/`` was checked against the **WHOLE concatenated urlconf**
(``apps/scm/urls/__init__.py`` plus every module under ``apps/scm/urls/``, re-read at build time),
not merely against the 4.17 block:

* **Nothing anywhere in ``apps/scm`` starts with ``client``** except this sub-module's own
  ``client-rate-cards`` / ``client-rate-card-lines`` / ``client-billing-runs`` /
  ``client-billing-run-lines`` (siblings in this same block) and the two 4.17 report pages
  ``client-inventory`` / ``client-space``. All of them are DISTINCT whole first segments.
* **``logistics-clients/`` vs 4.11's ``logistics-kpis/``** — two unrelated WHOLE path components.
  Django matches whole components and **never splits one at a hyphen**, so ``logistics-clients`` is
  not a prefix of ``logistics-kpis`` as far as the resolver is concerned and neither can shadow the
  other. **Neither may ever be "tidied" to look like the other**, e.g. into a shared
  ``logistics/<something>/`` parent — that would turn two independent segments into one greedy
  component and change which view answers.
* Near neighbours checked rather than assumed: 4.16's ``portal-*``, 4.10's ``return-portal/``,
  4.2's ``contracts/`` and ``catalogs/``, 4.6's ``carriers/``. None shares a first component with
  anything below.

**VIEW-NAME collision check** (the ``scm:`` namespace is flat, so a duplicate ``name=`` silently
rebinds the earlier route): every ``name=`` value in ``apps/scm/urls/**`` was collected and compared.
The only existing names containing ``client`` are this sub-module's own ``clientratecard_*`` /
``clientbillingrun*`` ones, and 4.11 owns ``logistics_kpis`` / ``logistics_kpis_export``.
**``logisticsclient_*`` collides with nothing.**

This module introduces **no greedy ``<str:…>`` converter**.

``add/`` is literal and MUST stay above ``<int:pk>/``: Django is first-match-wins, so a pk route
placed first would swallow the create page and then 404 as "logistics client 'add' not found".

``logistics-clients/<int:pk>/delete/`` is POST-only at the view (``@require_POST``), so a GET is a
405 rather than a silent deletion. The view also pre-counts the ``PROTECT``-ed rate cards and billing
runs, catches ``ProtectedError`` for the row filed between the check and the delete, and steers to
``status="suspended"`` / ``"terminated"`` — a tariff and a billed period are what an invoice was
calculated from, and they must not vanish under one click.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("logistics-clients/", views.logisticsclient_list, name="logisticsclient_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("logistics-clients/add/", views.logisticsclient_create, name="logisticsclient_create"),
    path("logistics-clients/<int:pk>/", views.logisticsclient_detail,
         name="logisticsclient_detail"),
    path("logistics-clients/<int:pk>/edit/", views.logisticsclient_edit,
         name="logisticsclient_edit"),
    # POST-only at the view; pre-counts the PROTECTed relations and catches ProtectedError.
    path("logistics-clients/<int:pk>/delete/", views.logisticsclient_delete,
         name="logisticsclient_delete"),
]
