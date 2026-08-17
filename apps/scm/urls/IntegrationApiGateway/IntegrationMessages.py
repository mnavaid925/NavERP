"""SCM 4.19 Integration & API Gateway — ``IntegrationMessage`` routes (prefix
``integration-messages/``) plus the sub-module's failure cockpit at ``integration-exceptions/``.
List, detail, one ``reprocess`` POST, and the report. Nothing else.

**THE ABSENT ADD, EDIT AND DELETE ROUTES ARE A DECISION, NOT AN OMISSION.** There is no
``integration-messages/add/``, no ``…/<int:pk>/edit/`` and no ``…/<int:pk>/delete/`` here because
there is no ``integrationmessage_create``, ``_edit`` or ``_delete`` view, no ModelForm
(``apps/scm/forms/IntegrationApiGateway/IntegrationMessages.py`` deliberately does not exist) and no
template for any of them anywhere in the module. ``IntegrationMessage`` is APPEND-ONLY — the
``scm.StockMove`` / ``scm.MeterReading`` / ``scm.PortalActivity`` posture, verbatim: a wrong row is
corrected by appending a LATER, CORRECT one, exactly the way a wrong stock movement is corrected by
a compensating move and a wrong journal entry by a reversal.

Three things make that the right call rather than a missing feature:

* an exchange log is *evidence of what crossed the boundary*, and evidence that can be revised after
  the dispute starts is not evidence. "Your 855 said 400 units" has to rest on a row nobody could
  have quietly retyped;
* somebody has already acted on these rows — a receipt was booked, an order released, a 997 chased.
  An editable delivery row is an audit trail that can be rewritten after somebody acted on it;
* ``acknowledges`` chains the 997 to the 850 it answers, so editing the answered row silently
  rewrites what the acknowledgement is an acknowledgement *of*.

``admin.py`` registers the model read-only for the same reason, and the absence is a *tested* shape
in this app rather than a convention: ``apps/scm/tests/test_security.py:6126``'s
``TestMeterReadingHasNoEditOrDeleteRoute`` asserts exactly this for 4.13's log, and 4.19's suite
carries the same assertion for these routes. **If a later pass is tempted to add an edit route here,
the answer is a second message row, not a mutable first one.** The one write this prefix exposes is
``reprocess``, which re-queues a row and clears its error text — it edits no partner-supplied field
and, since 4.19 ships no transport, it sends nothing.

COLLISION CHECK — both prefixes were checked against the WHOLE concatenated urlconf, not merely
against this block. Nothing anywhere in ``apps/scm/urls/`` previously began with ``integration`` or
``webhook``. Django matches WHOLE path components and **never splits one at a hyphen**, so
``integration-endpoints`` (4.19's endpoint register), ``integration-messages`` and
``integration-exceptions`` are THREE unrelated first components: none can shadow another, and
**none may ever be "tidied" into an ``integration/<something>/`` parent**, which would turn three
independent segments into one greedy component. Near neighbours checked rather than assumed: 4.17's
``logistics-clients/`` (4.19 FKs the client and takes no route beneath it), 4.18's ``finance-*``,
4.16's eight ``portal-*``, and CRM's own ``webhooks/`` — a different app, mounted at ``/crm/``, so
it cannot collide. This module introduces NO greedy ``<str:…>`` converter; 4.10's
``return-tracking/<str:token>/`` and 4.16's ``portal-documents/<str:token>/`` remain the app's only
two.

**VIEW-NAME collision check:** ``integration_exceptions`` was compared against every report name
shipped in ``apps/scm/urls/**`` — ``valuation_report``, ``reorder_alerts``, ``cold_storage_report``,
``labor_board``, ``sparepart_list``, ``logistics_kpis``, ``client_inventory_report``,
``client_space_report``, ``finance_payables``, ``finance_receivables``,
``finance_budget_variance``, ``landed_cost_variance`` — and collides with none of them.

ORDER IS BEHAVIOUR. ``integration-messages/`` is literal and sits above the ``<int:pk>`` block;
Django is first-match-wins, and while the ``int`` converter refuses a non-numeric segment TODAY,
that is exactly what makes a wrong ordering look harmless right up until somebody adds a
``<str:…>`` route to this prefix. ``integration-exceptions/`` is a different first component
entirely, so its position is immaterial — it is listed last because it is the report, not because
the ordering matters.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # Literal — must stay above the <int:pk> routes below it.
    path("integration-messages/", views.integrationmessage_list, name="integrationmessage_list"),
    path("integration-messages/<int:pk>/", views.integrationmessage_detail,
         name="integrationmessage_detail"),
    # POST-only at the view (@require_POST). Re-queues the row; sends nothing — 4.19 has no
    # outbound transport.
    path("integration-messages/<int:pk>/reprocess/", views.integrationmessage_reprocess,
         name="integrationmessage_reprocess"),
    # No add route. No edit route. No delete route. See the module docstring — that is the design.

    # The sub-module's failure cockpit: a report over IntegrationMessage rows, so it lives with the
    # entity that owns the data. Its template sits at the sub-module ROOT
    # (templates/scm/integration/exceptions.html), template rule 6 — it is not any one entity's
    # page. Takes no <int:pk>: it is about the whole failure set, and the endpoint arrives as a
    # FILTER (?endpoint=<pk>) so the page keeps its roll-up while narrowing.
    path("integration-exceptions/", views.integration_exceptions, name="integration_exceptions"),
]
