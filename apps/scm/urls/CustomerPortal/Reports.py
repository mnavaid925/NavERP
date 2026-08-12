"""SCM 4.16 Customer Portal — the two COMPUTED STAFF pages: ``portal-order-tracking/`` and
``portal-catalog-preview/``.

They carry NavERP bullets **Order Tracking** and **Catalog Browsing**, and — like ``coa_report``,
``mrp_report``, ``pm_forecast`` and ``labor_board`` before them — **neither owns a table**. 4.5 owns
the sales order, 4.6 owns the shipment and its tracking events, 4.3 owns the item and the
append-only ``StockMove`` ledger; 4.16 owns only the ``PortalAccount`` row that decides how a given
customer sees any of it. There is therefore **no create, edit or delete route in this module and no
``<int:pk>`` anywhere in it** — there is no row to address. Every option each page takes is a QUERY
STRING (``?q=&portal_account=&carrier=&status=&shipment_status=&portal_active=&state=&date_from=
&date_to=`` on the tracking console; ``?account=&customer=&q=&category=`` on the preview), so
neither page adds a route beyond the one below it.

**Both routes are ``@login_required`` STAFF pages (L32).** The five ``LIVE_LINKS["4.16"]`` bullets
all point at staff pages; the login-gated CUSTOMER surface (``scm:portal_home`` and friends, in
``Portal.py``) is a secondary extra reached from them. That is how 4.1's "Vendor Portal" and 4.10's
"Return Portal" resolved the same question.

Why each page exists rather than being a filter on a page that already shipped:

* **``portal-order-tracking/``** puts the order, what is allocated against it, the shipment's live
  status, its ETA, its exception and its POD state **in one row**. 4.5's order list knows nothing
  about shipments and 4.6's shipment list knows nothing about allocation or backorder — the join IS
  the page, and it is why WISMO is 25-40% of inbound support volume today.
* **``portal-catalog-preview/``** answers "what does customer X actually see?". Stock presentation,
  catalog scope and pricing are all per-ACCOUNT, so the only way to check a configuration before a
  customer meets it is to render that customer's projection.

  **# SECURITY: render-as, NEVER authenticate-as.** This route performs no session swap, mints no
  impersonation token, calls no ``login()`` and sets no cookie. The staff user stays exactly who
  they are and the page reads one ``PortalAccount`` row. Impersonation would mean a staff session
  carrying a customer's identity — every write it then made would be attributed to the customer and
  the audit trail would be fiction. **No route may ever be added under this segment that accepts a
  user id, a session key or a token.**

**Neither route writes a ``PortalActivity`` row**, and that is deliberate rather than forgotten: the
log records a read by a CUSTOMER, and a member of staff opening a staff console is not one. A page
that logged itself would put fabricated customer reads into the very trail a document dispute turns
on.

COLLISION CHECK — both first segments were checked against the **WHOLE concatenated urlconf** (every
module under ``apps/scm/urls/`` re-read at build time, 4.15's Cold Chain block included), not merely
against the 4.16 block:

* The only ``portal`` paths that existed anywhere in ``apps/scm`` before 4.16 are 4.10's
  ``return-portal/`` and ``return-portal/request/`` — verified by grepping every ``path("…")``
  literal in the package, not read off the plan.
* Django matches **WHOLE path components** and never splits one at a hyphen, so ``portal``,
  ``portal-accounts``, ``portal-inquiries``, ``portal-document-shares``, ``portal-activity``,
  ``portal-order-tracking``, ``portal-catalog-preview`` and ``portal-documents`` are **eight
  unrelated first segments**; none shadows another and none may be "tidied" into another's shape.
  In particular ``portal-order-tracking`` is NOT a sub-route of ``portal/orders/`` and must never be
  folded into one — the gated customer page and the staff console are different audiences.
* Near neighbours that are NOT collisions, checked rather than assumed: 4.10's ``return-tracking/``
  (a RETURN's public status page — a distinct component, a distinct direction of travel, and the
  app's only other tracking page), 4.1's ``orders/`` (purchase orders), 4.5's ``sales-orders/``,
  4.8's ``work-orders/``, 4.13's ``maintenance-work-orders/``, 4.2's ``catalogs/`` (a SUPPLIER
  catalog) and 4.3's ``categories/``. Every one is a separate whole component.

**VIEW-NAME collision check** (the ``scm:`` namespace is flat — a duplicate ``name=`` silently
rebinds the earlier route): all 547 existing ``name=`` values under ``apps/scm/urls/**`` were
collected and compared against the two names below. 4.2 owns ``catalog_list`` / ``catalog_detail``,
4.10 owns ``return_portal`` and ``portal_return_create``. **``portal_order_tracking`` and
``portal_catalog_preview`` collide with nothing.**

This module introduces NO greedy ``<str:…>`` converter; 4.16's only one is in ``Portal.py``. With no
pk route here at all, there is nothing in this module that could swallow anything.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # 4.16 bullet "Order Tracking" — the order x shipment x allocation join, for portal customers.
    # Reads 4.5 + 4.6 + 4.3 and writes nothing anywhere.
    path("portal-order-tracking/", views.portal_order_tracking, name="portal_order_tracking"),

    # 4.16 bullet "Catalog Browsing" — "as seen by customer X". RENDER-AS, never authenticate-as:
    # no session swap, no impersonation token, no login() call. See the module docstring.
    path("portal-catalog-preview/", views.portal_catalog_preview, name="portal_catalog_preview"),
]
