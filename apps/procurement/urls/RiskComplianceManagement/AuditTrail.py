"""Procurement 6.17 Risk & Compliance Management - audit trail and audit seal URL patterns.

Two first segments, ``audit-trail/`` and ``audit-seals/``, each checked as a whole path COMPONENT
against the concatenated inventory in ``apps/procurement/urls/__init__.py``. Neither is a prefix of
any existing segment, and neither collides with 6.12's ``receipt-audit/``: Django matches path
components rather than strings, so ``receipt-audit`` and ``audit-trail`` are simply different
components and could not shadow one another even if they shared a substring. No route in this app
uses a converter in its FIRST path component, so nothing outside this module can shadow it.
Re-checked against the concurrently built 6.16 / 6.18 / 6.19 segments before wiring (L43).

Django is first-match-wins, so **every literal route is declared before the ``<int:pk>/`` one it
would otherwise fall into** - here that is ``audit-seals/seal/``, which must precede
``audit-seals/<int:pk>/`` or the seal verb would be resolved as a request for a seal whose primary
key is the string "seal" (a 404 at best, and a confusing one).

**The two verbs are gated differently, and the difference is the design:**

* ``seal/`` is ``@tenant_admin_required`` + ``@require_POST`` (in that order, L27). Sealing is an
  administrative act that writes a record.
* ``<int:pk>/verify/`` is ``@login_required`` + ``@require_POST`` and is deliberately **NOT**
  admin-gated. Verification is read-mostly - its only write is the three verification stamps on
  the seal - and a tamper check that only an administrator can run is a check nobody runs. Anybody
  who can read the trail can prove for themselves that it has not been altered, which is the whole
  point of shipping the control.

**There is no ``auditseal_edit`` and no ``auditseal_delete``, and their absence is deliberate**
(contract 3, ``models/RiskComplianceManagement/AuditSeals.py``): a seal whose digest can be edited
proves nothing, and deleting a seal breaks exactly the chain it exists to protect - it is the first
move somebody covering their tracks would make. This is the sub-module's one documented deviation
from the CRUD-completeness rule, and the register and detail pages both state the reason where a
reader would otherwise look for the buttons.

``audit-trail/export/`` is a GET that returns a CSV rather than a page. It is ``@login_required``
and not admin-gated because it exports exactly the rows the register already shows to the same
person under the same tenant filter; gating the download but not the page would be theatre.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("audit-trail/", views.audit_trail, name="audit_trail"),
    # Literal before any pk route in this segment - and a CSV, not a page.
    path("audit-trail/export/", views.audit_trail_export, name="audit_trail_export"),

    path("audit-seals/", views.auditseal_list, name="auditseal_list"),
    # Literal before <int:pk> - first-match-wins IS behaviour.
    path("audit-seals/seal/", views.auditseal_create, name="auditseal_create"),

    path("audit-seals/<int:pk>/", views.auditseal_detail, name="auditseal_detail"),
    path("audit-seals/<int:pk>/verify/", views.auditseal_verify, name="auditseal_verify"),
]
