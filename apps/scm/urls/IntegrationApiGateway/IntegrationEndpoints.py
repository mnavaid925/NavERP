"""SCM 4.19 Integration & API Gateway — ``IntegrationEndpoint`` routes (``integration-endpoints/``).

The connection register: one row per registered connection to one outside system. It is the ROOT of
the sub-module and the target of FOUR of the five 4.19 sidebar bullets.

--------------------------------------------------------------------------------------------------
FOUR ROUTE NAMES, ONE VIEW, ONE TABLE
--------------------------------------------------------------------------------------------------
"ERP Integration", "E-commerce Integration", "IoT Gateway" and "EDI Management" are four NavERP.md
bullets sharing ONE table (``IntegrationEndpoint``, discriminated by ``category``) — the same
compression ``accounting.IntegrationConfig`` made. They still get **four distinct category-scoped
route names**, each resolving to the same view through Django's extra-options dict, so the EDI person
lands on the trading-partner register rather than on a mixed list. The category therefore arrives as
a VIEW KWARG, not a query-string parameter: it is code-controlled and can only ever be one of the
four literals below.

Every route here is staff-only and ``@login_required``. **4.19 has no client-facing surface** — no
portal route, no token route, no unauthenticated page (L32: a staff bullet may never target a
customer page, and the customer-facing portal is 4.16's).

--------------------------------------------------------------------------------------------------
COLLISION CHECK — run against the WHOLE concatenated urlconf, not just this block
--------------------------------------------------------------------------------------------------
``integration-endpoints`` is a **NEW first segment**: every ``path("…"`` literal under
``apps/scm/urls/`` was collected at build time and **nothing anywhere previously began with
``integration`` or ``webhook``**.

Django matches WHOLE path components and **never splits one at a hyphen**, so
``integration-endpoints`` / ``integration-messages`` / ``integration-exceptions`` are THREE unrelated
components; none is a prefix of another as far as the resolver is concerned, and **none of them may
EVER be "tidied" into an ``integration/<something>/`` parent** — that would turn three independent
segments into one greedy component and change which view answers.

Near neighbours checked rather than assumed: 4.17's ``logistics-clients/`` (4.19 FKs the client and
takes no route beneath it — constraint A), 4.18's ``finance-*``, 4.16's eight ``portal-*``, and
``crm``'s own ``webhooks/`` (a different app, mounted at ``/crm/``, so it cannot collide).

**VIEW-NAME collision check** (the ``scm:`` namespace is flat, so a duplicate ``name=`` silently
rebinds the earlier route): every ``name=`` value in ``apps/scm/urls/**`` was collected and compared.
Nothing containing ``integration``, ``webhook``, ``endpoint``, ``message`` or ``exception`` exists —
``integrationendpoint_*`` collides with nothing.

This module introduces **no greedy ``<str:…>`` converter**. 4.10's ``return-tracking/<str:token>/``
and 4.16's ``portal-documents/<str:token>/`` remain the app's only two.

--------------------------------------------------------------------------------------------------
ORDER IS BEHAVIOUR
--------------------------------------------------------------------------------------------------
``add/`` and the four category literals MUST stay above the ``<int:pk>`` block. Django is
first-match-wins. The ``int`` converter refuses ``"edi"`` **today**, which is exactly why the
ordering looks harmless right up until somebody adds a ``<str:…>`` route here — at which point
``/integration-endpoints/edi/`` would 404 as "endpoint 'edi' not found". Keep the literals first and
that day never arrives.

Both ``delete/`` and ``rotate-credential/`` are POST-only **at the view** (``@require_POST``), so a
GET is a 405 rather than a silent mutation, and both are additionally ``@tenant_admin_required``:
deleting a connection CASCADEs its whole exchange log away, and rotating a credential is a
workspace-configuration write.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # --- literals first (first-match-wins) ------------------------------------------------------
    path("integration-endpoints/", views.integrationendpoint_list, name="integrationendpoint_list"),
    path("integration-endpoints/add/", views.integrationendpoint_create,
         name="integrationendpoint_create"),

    # The four sidebar bullets. Same view, distinct names, category pinned by the extra-options
    # dict — so each bullet is a real page with its own heading and its own header chips, while the
    # rows all live in one table.
    path("integration-endpoints/erp/", views.integrationendpoint_list, {"category": "erp"},
         name="integrationendpoint_erp_list"),
    path("integration-endpoints/ecommerce/", views.integrationendpoint_list,
         {"category": "ecommerce"}, name="integrationendpoint_ecommerce_list"),
    path("integration-endpoints/iot/", views.integrationendpoint_list, {"category": "iot"},
         name="integrationendpoint_iot_list"),
    path("integration-endpoints/edi/", views.integrationendpoint_list, {"category": "edi"},
         name="integrationendpoint_edi_list"),

    # --- pk routes ------------------------------------------------------------------------------
    path("integration-endpoints/<int:pk>/", views.integrationendpoint_detail,
         name="integrationendpoint_detail"),
    path("integration-endpoints/<int:pk>/edit/", views.integrationendpoint_edit,
         name="integrationendpoint_edit"),
    # POST-only and admin-only at the view — CASCADEs the connection's whole exchange log.
    path("integration-endpoints/<int:pk>/delete/", views.integrationendpoint_delete,
         name="integrationendpoint_delete"),
    # POST-only and admin-only at the view. Mints a credential, stores prefix + digest only, shows
    # the plaintext exactly once. There is deliberately NO reveal route and NO test-connection route.
    path("integration-endpoints/<int:pk>/rotate-credential/",
         views.integrationendpoint_rotate_credential, name="integrationendpoint_rotate_credential"),
]
