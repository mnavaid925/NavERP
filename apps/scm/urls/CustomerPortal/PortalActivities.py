"""SCM 4.16 Customer Portal — ``PortalActivity`` routes (prefix ``portal-activity/``). **List and
detail ONLY.**

**THE ABSENT ADD, EDIT AND DELETE ROUTES ARE A DECISION, NOT AN OMISSION.** There is no
``portal-activity/add/``, no ``…/<int:pk>/edit/`` and no ``…/<int:pk>/delete/`` here because there
is no ``portalactivity_create`` view, no ``portalactivity_edit`` view, no ``portalactivity_delete``
view and **no form module for the model at all** — every field on it is ``editable=False`` and the
single writer is ``PortalActivity.record()``, called from the gated customer views and the token
download. This is the append-only posture ``scm.StockMove``, ``scm.TrackingEvent`` and
``scm.MeterReading`` already ship (``admin.py`` registers all of them read-only, and this model
too), and it is deliberate for one specific reason: **this table is the evidence that makes "we told
you on the 3rd" defensible.** A log a member of staff can edit after a dispute opens is not
evidence, and a log they can add to is worse — it is a place to manufacture a customer read that
never happened.

**Why the log exists at all, rather than reusing ``core.AuditLog``:** that model's
``ACTION_CHOICES`` are ``create/update/delete`` only (``apps/core/models/AuditLog.py:8``). It
records *changes to records by staff*; it cannot express *a read by a customer*. Widening it from an
SCM pass would corrupt an existing audit surface, so 4.16 records customer reads here and leaves
staff CRUD on all four 4.16 models going through ``write_audit_log`` exactly as before.

**No sidebar bullet.** NavERP.md gives 4.16 five bullets and the sidebar mirrors them exactly; this
list is reached from the account it belongs to (``portalaccount_detail``'s recent-activity panel).
That is the shipped ``WorkCenter`` / ``ReorderRule`` / ``ReturnReason`` / ``InspectionPlan`` /
``KpiTarget`` / ``MeterReading`` rule: a child reached from the page that uses it takes no bullet.

COLLISION CHECK — ``portal-activity/`` was checked against the **WHOLE concatenated urlconf** (every
module under ``apps/scm/urls/`` re-read at build time, 4.15's Cold Chain block included), not merely
against the 4.16 block:

* The only ``portal`` paths that existed anywhere in ``apps/scm`` before 4.16 are 4.10's
  ``return-portal/`` and ``return-portal/request/`` — verified by grepping every ``path("…")``
  literal in the package rather than trusting the plan text. ``return-portal`` is one whole
  component and a different component from ``portal-activity``.
* Django matches **WHOLE path components** and never splits one at a hyphen, so ``portal``,
  ``portal-accounts``, ``portal-inquiries``, ``portal-document-shares``, ``portal-activity``,
  ``portal-order-tracking``, ``portal-catalog-preview`` and ``portal-documents`` are **eight
  unrelated first segments**; none shadows another and none may be "tidied" into another's shape.
* **``labor-activities/`` (4.14) is NOT a collision** and must never be aligned with this one. It is
  a distinct whole component, and the two are different subjects entirely: 4.14's ``LaborActivity``
  is a warehouse worker's booked minutes against an engineered standard; ``PortalActivity`` is a
  CUSTOMER's read of their own order, catalog or document. ``scm:laboractivity_list`` and
  ``scm:portalactivity_list`` are two live, unrelated pages.

**VIEW-NAME collision check** (the ``scm:`` namespace is flat — a duplicate ``name=`` silently
rebinds the earlier route): all 547 existing ``name=`` values under ``apps/scm/urls/**`` were
collected and compared against the two names below. 4.14 owns ``laboractivity_list`` /
``_detail`` / ``_edit`` / ``_delete`` and 4.10 owns ``return_portal`` / ``portal_return_create``.
**``portalactivity_list`` and ``portalactivity_detail`` collide with nothing.**

This module introduces NO greedy ``<str:…>`` converter, and — having no literal sub-route under its
own segment — no ordering hazard either: the single ``<int:pk>/`` route below has nothing above or
below it in this module that it could swallow. The list page's options (``?q=&action=&
portal_account=&date_from=&date_to=&page=``) are all QUERY STRINGS and add no route of their own.

**If a later pass is tempted to add a create or edit route here, the answer is that the customer
view which performed the action should call ``PortalActivity.record()`` — not that a person should
be able to type a row into an evidence table.**
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("portal-activity/", views.portalactivity_list, name="portalactivity_list"),
    path("portal-activity/<int:pk>/", views.portalactivity_detail, name="portalactivity_detail"),
    # No add route. No edit route. No delete route. See the module docstring — that is the design.
]
