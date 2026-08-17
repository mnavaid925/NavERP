"""SCM 4.19 Integration & API Gateway — ``WebhookDelivery`` routes (prefix ``webhook-deliveries/``).

Three routes: the list, the detail, and one POST-only ``retry`` verb. Nothing else.

--------------------------------------------------------------------------------------------------
THE ABSENT ADD, EDIT AND DELETE ROUTES ARE A DECISION, NOT AN OMISSION
--------------------------------------------------------------------------------------------------
There is no ``webhook-deliveries/add/``, no ``…/<int:pk>/edit/`` and no ``…/<int:pk>/delete/`` here
because there is no ``webhookdelivery_create``, ``_edit`` or ``_delete`` view, no ModelForm
(``apps/scm/forms/IntegrationApiGateway/WebhookDeliveries.py`` deliberately does not exist, and the
forms package ``__init__`` carries a comment saying so rather than an import) and no template for any
of them anywhere in the module. ``WebhookDelivery`` is APPEND-ONLY — the ``scm.StockMove`` /
``scm.MeterReading`` / ``scm.PortalActivity`` posture, verbatim, and the one ``crm.WebhookDelivery``
states in the same words: *"Immutable append-only delivery record … Accessed list+detail only —
never edited."*

Two things make that the right call rather than a missing feature:

* a delivery log is *evidence of what was attempted*, and evidence that can be revised after the
  dispute starts is not evidence. "We pushed it eight times and you 500'd every time" has to rest on
  rows nobody could have quietly retyped or removed;
* somebody has already acted on these rows — a partner was chased, a subscription was switched off,
  a support ticket was closed against them. An editable delivery row is an audit trail that can be
  rewritten after somebody acted on it.

``admin.py`` registers the model read-only for the same reason, and the absence is a *tested* shape
in this app rather than a convention: ``apps/scm/tests/test_security.py``'s
``TestMeterReadingHasNoEditOrDeleteRoute`` asserts exactly this for 4.13's log and 4.19's suite
carries the same assertion for these routes. **If a later pass is tempted to add an edit route here,
the answer is a second attempt row, not a mutable first one.**

The one write this prefix exposes is ``retry``, which moves the row's queue state onto the next
backoff slot (or marks it exhausted). It rewrites no recorded outcome and — since 4.19 ships no
transport — **it sends nothing**. There is deliberately no "test delivery" route anywhere in the
sub-module: that would be an outbound HTTP request from the server to a tenant-supplied URL, i.e.
exactly the SSRF surface ``WebhookSubscription.target_url``'s comment defers.

--------------------------------------------------------------------------------------------------
NO SIDEBAR KEY
--------------------------------------------------------------------------------------------------
``webhookdelivery_list`` takes **no** ``LIVE_LINKS["4.19"]`` bullet. It is reached from a
subscription's detail page, which deep-links ``scm:webhookdelivery_list?subscription=<pk>`` — the
``ClientRateCard`` / ``ReorderRule`` / ``ReturnReason`` / ``MeterReading`` / ``PortalActivity`` rule:
a table reached from the page that uses it does not need a bullet of its own. (``navigation.py`` is a
single-writer file this module never touches either way.)

--------------------------------------------------------------------------------------------------
COLLISION CHECK — against the WHOLE concatenated urlconf, not merely against this block
--------------------------------------------------------------------------------------------------
``apps/scm/urls/__init__.py`` concatenates every entity module's ``urlpatterns`` into ONE flat list
under the ``scm:`` namespace, so a check that reads only this file is not a check at all.

``webhook-deliveries`` is a NEW first segment: **nothing anywhere in ``apps/scm/urls/`` previously
began with ``webhook``** (grepped this session, as was ``integration``). Neighbours checked rather
than assumed:

* this sub-module's own siblings ``webhook-subscriptions/``, ``integration-endpoints/``,
  ``integration-messages/`` and ``integration-exceptions/``. Django matches WHOLE path components and
  **never splits one at a hyphen**, so ``webhook-deliveries`` and ``webhook-subscriptions`` are two
  unrelated components: neither can shadow the other, and **neither may EVER be "tidied" into a
  ``webhooks/<something>/`` parent**, which would turn two independent segments into one segment plus
  a captured value and put them in each other's way for the first time;
* 4.17's ``logistics-clients/``, 4.18's ``finance-*`` and 4.16's eight ``portal-*`` — all different
  first components;
* CRM's own ``webhooks/`` routes live in a DIFFERENT app, mounted under ``/crm/``, and cannot collide
  with anything here regardless of spelling.

**VIEW-NAME check** against the flat ``scm:`` namespace: ``webhookdelivery_list`` / ``_detail`` /
``_retry`` are all new — no shipped scm view is named ``webhook*``.

--------------------------------------------------------------------------------------------------
ORDER IS BEHAVIOUR
--------------------------------------------------------------------------------------------------
The literal ``webhook-deliveries/`` sits above the ``<int:pk>`` routes. Django is first-match-wins,
and while the ``int`` converter refuses a non-numeric segment TODAY, that is exactly what makes a
wrong ordering look harmless right up until somebody adds a ``<str:…>`` route under this prefix. This
module introduces **no greedy ``<str:…>`` converter**; 4.10's ``return-tracking/<str:token>/`` and
4.16's ``portal-documents/<str:token>/`` remain the app's only two.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # Literal — must stay above the <int:pk> routes below it. The subscription detail page deep-links
    # here as ?subscription=<pk>, which is a query param and needs no route of its own.
    path("webhook-deliveries/", views.webhookdelivery_list, name="webhookdelivery_list"),

    path("webhook-deliveries/<int:pk>/", views.webhookdelivery_detail,
         name="webhookdelivery_detail"),

    # POST-only at the view (@require_POST), so a GET is a 405 rather than a silent state change — a
    # retry link a crawler or a prefetching browser could follow would re-queue rows nobody asked
    # about. Moves the row onto the next backoff slot (or marks it exhausted); FIRES NO HTTP REQUEST.
    path("webhook-deliveries/<int:pk>/retry/", views.webhookdelivery_retry,
         name="webhookdelivery_retry"),

    # No add route. No edit route. No delete route. See the module docstring — that is the design.
]
