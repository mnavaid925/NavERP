"""SCM 4.19 Integration & API Gateway — ``WebhookSubscription`` routes (prefix ``webhook-subscriptions/``).

Full CRUD — list / create / detail / edit / delete — plus one privileged verb,
``rotate-secret``. Both mutating non-form routes are POST-only **at the view** (``@require_POST``),
so a GET to either is a 405 rather than a silent state change, and both are additionally
``@tenant_admin_required`` (L27: a webhook target is an egress path out of the workspace, so who may
remove or re-credential one is workspace configuration).

This list is the 4.19 sidebar's **Webhooks** bullet (``scm:webhooksubscription_list``). The
``LIVE_LINKS`` entry itself belongs to ``apps/core/navigation.py`` — a single-writer file this module
never touches.

--------------------------------------------------------------------------------------------------
ORDER IS BEHAVIOUR
--------------------------------------------------------------------------------------------------
``webhook-subscriptions/add/`` **MUST stay above the ``<int:pk>/`` block.** Django is first-match-wins
and matches WHOLE path components, so a ``<int:pk>`` route placed first would be offered ``add`` —
the ``int`` converter refuses it TODAY, which is precisely why the ordering looks harmless right up
until somebody adds a ``<str:…>`` route under this prefix and the create page starts 404ing as
*"subscription 'add' not found"*.

This module introduces **no greedy ``<str:…>`` converter**. 4.10's ``return-tracking/<str:token>/``
and 4.16's ``portal-documents/<str:token>/`` remain the app's only two, and a third under this prefix
is exactly what the ordering note above is guarding against.

--------------------------------------------------------------------------------------------------
COLLISION CHECK — against the WHOLE concatenated urlconf, not merely against this block
--------------------------------------------------------------------------------------------------
``apps/scm/urls/__init__.py`` concatenates every entity module's ``urlpatterns`` into ONE flat list
under the ``scm:`` namespace, so a collision check that reads only this file is not a check at all.

``webhook-subscriptions`` is a NEW first segment: **nothing anywhere in ``apps/scm/urls/`` previously
began with ``webhook``** (grepped this session, as was ``integration``). Neighbours checked rather
than assumed:

* this sub-module's own siblings ``webhook-deliveries/``, ``integration-endpoints/``,
  ``integration-messages/`` and ``integration-exceptions/``. Django **never splits a path component
  at a hyphen**, so ``webhook-subscriptions`` and ``webhook-deliveries`` are two unrelated WHOLE
  components — neither can shadow the other, and neither may EVER be "tidied" into a
  ``webhooks/<something>/`` parent, which would turn two independent segments into one segment plus a
  captured value and put them in each other's way for the first time.
* CRM's own ``webhooks/`` routes live in a DIFFERENT app, mounted under ``/crm/``, and cannot collide
  with anything here regardless of spelling.

**VIEW-NAME check** against the flat ``scm:`` namespace: ``webhooksubscription_list`` / ``_create`` /
``_detail`` / ``_edit`` / ``_delete`` / ``_rotate_secret`` are all new — no shipped scm view is named
``webhook*``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("webhook-subscriptions/", views.webhooksubscription_list, name="webhooksubscription_list"),

    # LITERAL — must stay above the <int:pk> block below. See the ordering note in the docstring.
    path("webhook-subscriptions/add/", views.webhooksubscription_create,
         name="webhooksubscription_create"),

    path("webhook-subscriptions/<int:pk>/", views.webhooksubscription_detail,
         name="webhooksubscription_detail"),
    path("webhook-subscriptions/<int:pk>/edit/", views.webhooksubscription_edit,
         name="webhooksubscription_edit"),

    # POST-only at the view (@require_POST) and tenant-admin only — a GET is a 405, never a deletion.
    # CASCADE takes the subscription's whole delivery log with it; the view counts the rows first so
    # the confirmation says how much went.
    path("webhook-subscriptions/<int:pk>/delete/", views.webhooksubscription_delete,
         name="webhooksubscription_delete"),

    # POST-only, tenant-admin only. Mints a new signing secret and stores prefix + hash; the
    # plaintext is revealed exactly once on the detail page and then gone. Fires no HTTP request —
    # there is deliberately no "test delivery" route here (that would be an outbound call to a
    # tenant-supplied URL, i.e. the SSRF surface 4.19 defers).
    path("webhook-subscriptions/<int:pk>/rotate-secret/", views.webhooksubscription_rotate_secret,
         name="webhooksubscription_rotate_secret"),
]
