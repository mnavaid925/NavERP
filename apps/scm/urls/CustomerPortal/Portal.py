"""SCM 4.16 Customer Portal — the GATED CUSTOMER SURFACE (``portal/``) and the one PUBLIC bearer
route (``portal-documents/<str:token>/``).

Everything here is read by a **customer**, not by staff. The seven ``portal/`` routes are
``@login_required`` and each resolves identity through the shared
``apps.scm.views._helpers._portal_account`` walk — ``user -> crm.CustomerPortalAccess (active) ->
customer_party -> scm.PortalAccount (active)`` — refusing at each step with a message + redirect
rather than falling through to an unscoped queryset. **Nothing on these pages is scoped by what a
URL, a form or a template said; it is scoped by who the signed-in user resolved to.** A ``party`` of
``None`` would turn "this customer's own orders" into a filter on NULL, which for an OR-composed or
nullable-FK lookup is not "nothing" — it is "everybody's". That is the reason the resolver refuses
instead of returning ``None``, and it is why no route here takes a customer id.

These are **secondary extras, not sidebar destinations** (L32). All five ``LIVE_LINKS["4.16"]``
bullets point at staff pages; a customer reaches ``portal/`` by signing in, and staff reach it from
``portalaccount_detail``.

--------------------------------------------------------------------------------------------------
COLLISION CHECK — checked against the WHOLE concatenated urlconf, not merely against this block
--------------------------------------------------------------------------------------------------
Every module under ``apps/scm/urls/`` was re-read at build time, **4.15's Cold Chain block
included** (it landed after the 4.16 plan was written), and every ``path("…")`` literal in the
package was collected rather than trusted from the plan text. The finding:

* **The only ``portal`` paths anywhere in ``apps/scm`` are 4.10's ``return-portal/`` and
  ``return-portal/request/``** — confirmed, exactly as the plan asserted. Their first segment is
  ``return-portal``, one whole component, and a different component from ``portal``.
* Django matches **WHOLE path components** and never splits one at a hyphen. So ``portal``,
  ``portal-accounts``, ``portal-inquiries``, ``portal-document-shares``, ``portal-activity``,
  ``portal-order-tracking``, ``portal-catalog-preview`` and ``portal-documents`` are **eight
  unrelated first segments**. ``portal/`` does not "contain" ``portal-accounts/``; there is no
  parent-child relationship between them for the resolver to get wrong. None shadows another and
  **none may ever be "tidied" into another's shape** — merging ``portal-documents`` into
  ``portal/documents/`` in particular would file an UNAUTHENTICATED route inside the
  ``@login_required`` area, where the next reader would assume the gate applies to it.
* Near neighbours that are NOT collisions, checked rather than assumed: 4.5's ``sales-orders/``,
  4.1's ``orders/`` and ``receipts/``, 4.8's ``work-orders/``, 4.13's ``maintenance-work-orders/``,
  4.2's ``catalogs/``, 4.3's ``categories/``, 4.12's ``trade-documents/``. Every one is a separate
  whole component; ``portal/orders/`` and ``portal/catalog/`` are SECOND components under
  ``portal/`` and can collide with none of them.
* **``crm``'s ``portal/``, ``portal/orders/``, ``portal/stock/``, ``portal/cases/…`` and
  ``portal-access/`` cannot collide with these.** ``apps.crm.urls`` is mounted at ``/crm/`` and
  ``apps.scm.urls`` at ``/scm/`` (``config/urls.py``), and each carries its own ``app_name``, so
  ``crm:portal_case_detail`` and ``scm:portal_order_detail`` are different URLs in different
  namespaces. The two sets never meet in one resolver list.

**VIEW-NAME collision check** (the ``scm:`` namespace is flat — a duplicate ``name=`` silently
rebinds the earlier route and the first one stops reversing): all 547 existing ``name=`` values
under ``apps/scm/urls/**`` were collected and compared against the eight names below. 4.10 owns
``return_portal`` and **``portal_return_create``** — 4.16 reuses neither, and the customer's return
request links out to 4.10's existing route rather than declaring a second one. 4.2 owns
``catalog_list``. **``portal_home`` / ``portal_order_list`` / ``portal_order_detail`` /
``portal_documents`` / ``portal_document_download`` / ``portal_inquiry_create`` / ``portal_catalog``
/ ``portal_profile`` collide with nothing.**

--------------------------------------------------------------------------------------------------
``portal-documents/<str:token>/`` — the app's SECOND greedy ``<str:…>`` converter
--------------------------------------------------------------------------------------------------
4.10's ``return-tracking/<str:token>/`` (and its literal ``…/label/`` sibling) was the first, and
until now the only one. This is the second, and like 4.10's it **sits alone on its own first
segment**, so it can neither shadow nor be shadowed by anything: to reach it a request must already
have matched the literal component ``portal-documents``, and no other route in the whole app —
4.16's included — claims that component. There is nothing under it but the token, so it cannot
swallow a sibling either. **Any future route added under ``portal-documents/`` must be a literal
sub-path declared ABOVE this one**, exactly as 4.10 handled ``return-tracking/<str:token>/label/``.

**It carries NO decorator, and that is the design.** The unguessable ``public_token`` (32 urlsafe
bytes, minted in ``save()``) is the bearer credential — the ``returnauthorization_public`` /
``case_public`` mechanism. There is no ``LoginRequiredMiddleware`` in this project, so a bare view is
genuinely public. What makes it safe is in the VIEW, not in this file, and is repeated here so the
route is never "tidied" without it: tenant is taken off the OBJECT (``request.tenant`` is ``None``
for an anonymous visitor), ``obj.tenant.is_active`` is re-checked, the state guard lives in the
LOOKUP (``revoked_at__isnull=True`` plus an explicit ``expires_at`` check raising ``Http404``) so an
expired or revoked share is indistinguishable from a wrong token, ``portal_account.is_active`` is
re-checked, and the ownership rule is re-verified against the object rather than trusted from the
form that created it.

**# WARNING (security) — the token protects the VIEW, not the FILE.** ``config/urls.py`` appends
``static(settings.MEDIA_URL, …)`` when ``DEBUG``, so in development the underlying
``/media/documents/...`` path is served directly and bypasses this route entirely. The view
therefore MUST stream with ``django.http.FileResponse(...)`` and must never ``redirect(obj.file.url)``,
never render ``.url`` into a template and never expose ``MEDIA_URL`` for a shared document.

**# WARNING (security) — unauthenticated GET: add per-IP rate limiting** (django-ratelimit) or a WAF
throttle before this is internet-facing, exactly as 4.10's public POST is flagged at
``views/ReturnsManagement/Reports.py:489``. Token enumeration is the attack; 32 urlsafe bytes is the
mitigation and is **not** a substitute for a throttle.

--------------------------------------------------------------------------------------------------
ORDERING, and the route that is deliberately absent
--------------------------------------------------------------------------------------------------
**Every literal route is declared above the module's single ``<int:pk>`` route.** First-match-wins
is behaviour, not style. Here the hazard happens to be nil — ``portal/orders/<int:pk>/`` can only
match a request whose second component is literally ``orders``, so ``portal/documents/``,
``portal/catalog/``, ``portal/profile/`` and ``portal/inquiries/add/`` were never reachable by it —
but the convention is kept visible on purpose, because the next person to add
``portal/orders/export/`` will add it in the literal block and it will work, instead of adding it
below and watching it 404 as "order 'export' not found".

**There is deliberately NO ``portal/inquiries/<int:pk>/``** (§4 of the plan). ``portal/inquiries/add/``
is literal and stands alone: the customer's inquiry CONVERSATION is CRM's already-built
``crm:portal_case_detail`` over ``crm.CaseComment(is_public=True)``, and
:func:`~apps.scm.views.portal_inquiry_create` redirects there on success. A second thread page in
``scm`` would be a second place to leak an internal note. The create page accepts an optional
``?sales_order=&shipment=&inquiry_type=`` pre-fill so a customer arriving from an order does not
retype its context — a QUERY STRING, which adds no route of its own.

Likewise **no return-request route**: ``can_request_returns`` steers to 4.10's existing
``scm:portal_return_create``. And **no write routes beyond the inquiry** — ``portal/profile/`` is
read-only because a customer silently re-pointing their own delivery address is how a compromised
login becomes a diverted pallet, so address maintenance stays a staff action with a human in it.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # --- the gated customer surface. All @login_required; identity resolved by _portal_account().
    path("portal/", views.portal_home, name="portal_home"),
    path("portal/orders/", views.portal_order_list, name="portal_order_list"),
    path("portal/documents/", views.portal_documents, name="portal_documents"),
    path("portal/catalog/", views.portal_catalog, name="portal_catalog"),
    # READ-ONLY on purpose — see the module docstring. There is no portal/profile/edit/.
    path("portal/profile/", views.portal_profile, name="portal_profile"),
    # Literal, and standing alone: there is deliberately NO portal/inquiries/<int:pk>/ — the thread
    # is crm:portal_case_detail. Takes an optional ?sales_order=&shipment=&inquiry_type= pre-fill.
    path("portal/inquiries/add/", views.portal_inquiry_create, name="portal_inquiry_create"),

    # The module's only <int:pk> route, declared below every literal above (see the docstring).
    path("portal/orders/<int:pk>/", views.portal_order_detail, name="portal_order_detail"),

    # --- PUBLIC. No decorator: the unguessable public_token is the bearer credential. Alone on its
    # own first segment, so it shadows nothing and nothing shadows it. Any future literal sub-path
    # under portal-documents/ must be declared ABOVE this line. See the two # WARNINGs above.
    path("portal-documents/<str:token>/", views.portal_document_download,
         name="portal_document_download"),
]
