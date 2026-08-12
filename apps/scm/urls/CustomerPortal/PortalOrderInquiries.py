"""SCM 4.16 Customer Portal — ``PortalOrderInquiry`` routes (prefix ``portal-inquiries/``).

The staff **triage queue** for order-context support tickets — WISMO, delivery exceptions, short
shipments, damage, invoice disputes. The sidebar bullet **Support Ticketing** points here.

**These routes drive a WRAPPER, not a second helpdesk.** Every inquiry carries a ``crm.Case``
(``editable=False``, NOT NULL, written server-side by ``PortalOrderInquiry.open_for()``), and the
case owns the thread, the SLA clocks, CSAT, ownership and the public status token. That is why this
module declares:

* **no thread route** — the conversation is ``crm:portal_case_detail`` over
  ``crm.CaseComment(is_public=True)``, and the detail template links out to it;
* **no SLA route and no CSAT route** — 4.16 recomputes neither; ``sla_state`` is derived from
  ``case.first_response_due`` / ``case.resolution_due`` at render time and is not a column;
* **no second RMA route** — ``raise-return/`` links this inquiry to 4.10's EXISTING
  ``ReturnAuthorization``; it does not create a parallel return document.

COLLISION CHECK — ``portal-inquiries/`` was checked against the **WHOLE concatenated urlconf**
(every module under ``apps/scm/urls/`` re-read at build time, 4.15's Cold Chain block included),
not merely against the 4.16 block:

* **Nothing anywhere in ``apps/scm`` starts with ``inquir``**, and the only ``portal`` paths that
  existed before 4.16 are 4.10's ``return-portal/`` and ``return-portal/request/`` — verified by
  grepping every ``path("…")`` literal in the package rather than trusting the plan text.
* Django matches **WHOLE path components** and never splits one at a hyphen, so ``portal``,
  ``portal-accounts``, ``portal-inquiries``, ``portal-document-shares``, ``portal-activity``,
  ``portal-order-tracking``, ``portal-catalog-preview`` and ``portal-documents`` are **eight
  unrelated first segments**; none can shadow another and none may be "tidied" into another's shape.
* Near neighbours that are NOT collisions: 4.1's ``rfqs/`` and ``quotes/`` (a supplier *request for
  quotation* — a different segment and the opposite direction of trade), 4.9's ``inspections/``,
  4.10's ``returns/`` and ``warranty-claims/`` (a warranty claim is 4.10's document; an inquiry of
  type ``return_request`` merely POINTS at one).

**VIEW-NAME collision check** (the ``scm:`` namespace is flat — a duplicate ``name=`` silently
rebinds the earlier route): all 547 existing ``name=`` values under ``apps/scm/urls/**`` were
collected and compared against the eight names below. 4.10 owns ``return_portal`` and
``portal_return_create``; ``returnauthorization_create`` is 4.10's too and is what
``raise-return/`` steers to when no RMA exists yet. **``portalorderinquiry_*`` collides with
nothing.**

This module introduces NO greedy ``<str:…>`` converter; 4.16's only one is in ``Portal.py``.

``add/`` is literal and MUST stay above ``<int:pk>/`` — first-match-wins is behaviour, not style: a
pk route placed first swallows the create page and 404s as "inquiry 'add' not found".

**``resolve/`` · ``reopen/`` · ``raise-return/`` are the ONLY things that can move ``outcome``,
``resolved_at`` and ``return_authorization``** — all three columns are ``editable=False`` on the
model and therefore absent from every ModelForm, so no POST body can reach them through the create
or edit page. Each verb is ``@require_POST`` at the view, so a GET is a 405 rather than a silent
state change, and each writes its own ``write_audit_log`` row because it bypasses the ``crud_*``
helpers that would otherwise have written one. ``resolve()`` refuses an already-resolved inquiry and
``link_return()`` refuses a cross-tenant or cross-customer RMA — the routes are the door, the model
methods are the lock.

``delete/`` is POST-only as well, and is the ONE destructive route here: deleting an inquiry
CASCADEs from the ``crm.Case`` side, never the other way round, so removing the SCM context record
leaves CRM's ticket and its customer-visible thread intact.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("portal-inquiries/", views.portalorderinquiry_list, name="portalorderinquiry_list"),
    # Literal — must stay above every <int:pk> route below it. The create view opens the crm.Case
    # server-side through open_for(); `case`, `source` and `raised_by` are never typeable.
    path("portal-inquiries/add/", views.portalorderinquiry_create,
         name="portalorderinquiry_create"),
    path("portal-inquiries/<int:pk>/", views.portalorderinquiry_detail,
         name="portalorderinquiry_detail"),
    path("portal-inquiries/<int:pk>/edit/", views.portalorderinquiry_edit,
         name="portalorderinquiry_edit"),
    path("portal-inquiries/<int:pk>/delete/", views.portalorderinquiry_delete,
         name="portalorderinquiry_delete"),

    # --- the three workflow verbs: the only writers of outcome / resolved_at /
    # return_authorization. All POST-only at the view; all audited by hand.
    path("portal-inquiries/<int:pk>/resolve/", views.portalorderinquiry_resolve,
         name="portalorderinquiry_resolve"),
    path("portal-inquiries/<int:pk>/reopen/", views.portalorderinquiry_reopen,
         name="portalorderinquiry_reopen"),
    # Links 4.10's EXISTING ReturnAuthorization. It does not create a second RMA document.
    path("portal-inquiries/<int:pk>/raise-return/", views.portalorderinquiry_raise_return,
         name="portalorderinquiry_raise_return"),
]
