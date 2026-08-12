"""SCM 4.16 Customer Portal — ``PortalDocumentShare`` routes (prefix ``portal-document-shares/``).

The staff **share register**: what a portal account may retrieve, and the proof it did. The sidebar
bullet **Document Retrieval** points here. Every row publishes exactly one of six typed targets
(``core.Document`` · ``accounting.Invoice`` · ``scm.Shipment``'s POD · ``scm.TradeDocument`` ·
``crm.ContractDocument`` · ``scm.QualityInspection``'s CoA) to exactly one account, and the model's
``clean()`` block (d) enforces the authorisation rule of the whole sub-module: **a share is only
ever of the customer's OWN document.**

**THE ROUTES IN THIS MODULE ARE THE STAFF SIDE ONLY. The bearer-token fetch is NOT here** — it is
``portal-documents/<str:token>/`` in ``Portal.py``, deliberately on its own first segment so the
unauthenticated route is impossible to confuse with the authenticated register. Nothing in this
module is public, and **``public_token`` appears in no route, no ``name=``, no query string and no
list column**: it is a credential (the L20 secret-field class), and the only legitimate exposure of
it is the copyable URL on the detail page.

COLLISION CHECK — ``portal-document-shares/`` was checked against the **WHOLE concatenated urlconf**
(every module under ``apps/scm/urls/`` re-read at build time, 4.15's Cold Chain block included),
not merely against the 4.16 block:

* **Nothing anywhere in ``apps/scm`` starts with ``document``**, and the only ``portal`` paths that
  existed before 4.16 are 4.10's ``return-portal/`` and ``return-portal/request/`` — verified by
  grepping every ``path("…")`` literal in the package, not read off the plan.
* Django matches **WHOLE path components** and never splits one at a hyphen, so
  ``portal-document-shares`` and ``portal-documents`` are **two unrelated first segments**, not a
  parent and a child. Neither can shadow the other, and **neither may ever be "tidied" into the
  other's shape** — one is the login-gated register, the other is the anonymous bearer fetch, and
  merging their segments would put a public route underneath an admin one.
* Near neighbours that are NOT collisions, checked rather than assumed: 4.12's ``trade-documents/``
  (one of the six TARGETS a share can point at — a different component and a different table),
  4.1's ``receipts/``, 4.9's ``coa/`` (the CoA report a ``doc_type="coa"`` share surfaces; again a
  separate segment), and 4.2's ``contracts/`` (a SUPPLIER contract — pointedly *not* what a share
  carries: ``contract`` FKs ``crm.ContractDocument``, the customer-side document).

**VIEW-NAME collision check** (the ``scm:`` namespace is flat — a duplicate ``name=`` silently
rebinds the earlier route): all 547 existing ``name=`` values under ``apps/scm/urls/**`` were
collected and compared against the six names below. 4.12 owns ``tradedocument_*``, 4.9 owns
``coa_report``, 4.10 owns ``return_portal`` / ``portal_return_create``. **``portaldocumentshare_*``
collides with nothing.**

This module introduces NO greedy ``<str:…>`` converter — the one 4.16 adds lives in ``Portal.py``.

``add/`` is literal and MUST stay above ``<int:pk>/``: first-match-wins is behaviour, not style, so
a pk route placed first would swallow the create page and 404 as "share 'add' not found".

**``revoke/`` is the only writer of ``revoked_at``** (the column is ``editable=False`` and therefore
absent from every ModelForm), and it is ``@tenant_admin_required`` + ``@require_POST`` so a GET is a
405 rather than a silent kill. It matters more here than on a normal status verb: revocation is the
explicit fix for 4.10's documented residual risk — *"the token never expires, cannot be rotated and
cannot be revoked… a forwarded link is permanent read access"*
(``views/ReturnsManagement/Reports.py:41-42``). The guard lives **in the lookup**
(``revoked_at__isnull=True`` inside ``filter()``, plus an explicit ``expires_at`` check raising
``Http404``), so a revoked or expired share is indistinguishable from a wrong token — pressing this
button is the thing that actually kills a link that has already been forwarded.

``edit/`` and ``delete/`` are ``@tenant_admin_required`` too, for the same reason: editing a share
changes **who may fetch which document**, which is an authorisation change wearing a form's
clothing. ``delete/`` is additionally POST-only. Prefer ``revoke/`` to ``delete/`` in the UI — a
deleted share destroys its own download audit, and the audit is the point.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("portal-document-shares/", views.portaldocumentshare_list,
         name="portaldocumentshare_list"),
    # Literal — must stay above every <int:pk> route below it. The create view stamps `shared_by`
    # and passes a tenant-stamped instance so clean()'s ownership block actually runs.
    path("portal-document-shares/add/", views.portaldocumentshare_create,
         name="portaldocumentshare_create"),
    path("portal-document-shares/<int:pk>/", views.portaldocumentshare_detail,
         name="portaldocumentshare_detail"),
    # Tenant-admin: editing a share changes WHO MAY FETCH WHICH DOCUMENT.
    path("portal-document-shares/<int:pk>/edit/", views.portaldocumentshare_edit,
         name="portaldocumentshare_edit"),
    path("portal-document-shares/<int:pk>/delete/", views.portaldocumentshare_delete,
         name="portaldocumentshare_delete"),

    # The kill switch for a link that has already been forwarded. POST-only + tenant-admin.
    path("portal-document-shares/<int:pk>/revoke/", views.portaldocumentshare_revoke,
         name="portaldocumentshare_revoke"),
]
