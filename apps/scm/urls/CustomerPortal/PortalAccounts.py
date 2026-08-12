"""SCM 4.16 Customer Portal — ``PortalAccount`` routes (prefix ``portal-accounts/``).

This is the staff **enablement and entitlement console**: one row per customer ``core.Party``,
deciding whether that customer has the portal switched on at all and what they may see when they
do. It is NOT a login — the login binding is ``crm.CustomerPortalAccess`` and 4.16 builds no second
one — so there is deliberately no "create user", "reset password" or "impersonate" route anywhere in
this module. The sidebar bullet **Account Management** points here (L32: a staff bullet may never
target a login-gated customer page).

COLLISION CHECK — ``portal-accounts/`` was checked against the **WHOLE concatenated urlconf**
(``apps/scm/urls/__init__.py``, every module under ``apps/scm/urls/`` re-read at build time,
4.15's Cold Chain block included), not merely against the 4.16 block:

* **The only ``portal`` paths anywhere in ``apps/scm`` before 4.16 are 4.10's ``return-portal/`` and
  ``return-portal/request/``** — verified by grepping every ``path("…")`` literal in the package,
  not taken from the plan. Their first segment is ``return-portal``, which is one whole component
  and is a different component from ``portal-accounts``.
* Django matches **WHOLE path components** and never splits one at a hyphen, so ``portal``,
  ``portal-accounts``, ``portal-inquiries``, ``portal-document-shares``, ``portal-activity``,
  ``portal-order-tracking``, ``portal-catalog-preview`` and ``portal-documents`` are **eight
  unrelated first segments**. None shadows another, none is a prefix of another as far as the
  resolver is concerned, and **none may ever be "tidied" into another's shape.**
* Near neighbours that are NOT collisions, checked rather than assumed: 4.2's ``catalogs/`` (a
  SUPPLIER catalog — a different segment and a different subject from ``portal-catalog-preview``),
  4.12's ``trade-documents/`` and 4.1's ``receipts/`` (neither shares a component with
  ``portal-document-shares``), 4.14's ``labor-activities/`` (a booked work interval — a different
  component and a different subject from ``portal-activity``, which is a customer READ).

**VIEW-NAME collision check** (the ``scm:`` namespace is flat, so a duplicate ``name=`` silently
rebinds the earlier route): every one of the 547 existing ``name=`` values in ``apps/scm/urls/**``
was collected and compared against the five names below. 4.10 owns ``return_portal`` and
``portal_return_create``, and 4.2 owns ``catalog_list``; **``portalaccount_*`` collides with
nothing.** The customer-facing return request still routes to 4.10's existing
``scm:portal_return_create`` — 4.16 declares no route of its own for it.

This module introduces NO greedy ``<str:…>`` converter. 4.16 adds exactly one, in ``Portal.py``.

``add/`` is literal and MUST stay above ``<int:pk>/``: Django is first-match-wins, so a pk route
placed first would swallow the create page and then 404 as "portal account 'add' not found".

``portal-accounts/<int:pk>/delete/`` is POST-only at the view (``@tenant_admin_required`` +
``@require_POST``), so a GET is a 405 rather than a silent deletion. The privilege is not ceremony:
``PortalOrderInquiry.portal_account`` is ``PROTECT``, so the view catches ``ProtectedError`` and
reports it rather than 500-ing, and the UI steers to ``is_active=False`` instead — an inquiry is
evidence and the account it was raised under must not vanish under it in one click.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("portal-accounts/", views.portalaccount_list, name="portalaccount_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("portal-accounts/add/", views.portalaccount_create, name="portalaccount_create"),
    path("portal-accounts/<int:pk>/", views.portalaccount_detail, name="portalaccount_detail"),
    path("portal-accounts/<int:pk>/edit/", views.portalaccount_edit, name="portalaccount_edit"),
    # POST-only + tenant-admin at the view; catches ProtectedError from a PROTECTed inquiry.
    path("portal-accounts/<int:pk>/delete/", views.portalaccount_delete,
         name="portalaccount_delete"),
]
