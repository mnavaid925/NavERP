"""Procurement 6.19 Document & Knowledge Management — ProcurementDocument URL patterns.

One first segment, ``documents/``, collision-checked as a whole component against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. No route in this app uses a
converter in its FIRST path component — every first segment is a literal — so nothing can shadow
it. (A ``<str:token>`` converter does exist, at 6.8's ``contract-sign/<str:token>/``, but it sits
behind a literal first segment and shadows nothing outside it.) (``templates/`` belongs to 6.2 and
``contracts/`` to 6.8 — which is why the knowledge library is ``knowledge/`` and the policy
library ``procurement-policies/``.)

**Django is first-match-wins, so the order below is behaviour.** The three literal routes —
``add/``, ``reindex/`` and ``run-reminders/`` — are declared BEFORE ``<int:pk>/``, which would
otherwise swallow nothing at all (``<int:pk>`` will not match ``reindex``) but WOULD leave a
future ``<str:…>`` route ambiguous; keeping literals first is the rule that stays correct when
the next segment is added.

``documents/<int:pk>/revisions/add/`` lives HERE rather than in ``Revisions.py`` because url
modules own SEGMENTS, and this one is under ``documents/``. Its view
(``views.pdocument_revision_upload``) is defined in
``views/DocumentKnowledgeManagement/Revisions.py`` — the upload is an action ON a document, and
the revision it mints has no identity of its own until it exists.

Every route below except the register, the detail page and the upload form is POST-only through
its view's ``@require_POST``; ``reindex/`` is additionally ``@tenant_admin_required``. Delete has
no confirm template — the list and detail pages carry a ``{% csrf_token %}`` form with an
``onsubmit`` confirm instead.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("documents/", views.pdocument_list, name="pdocument_list"),
    # Literals BEFORE <int:pk>/ — see the module docstring.
    path("documents/add/", views.pdocument_create, name="pdocument_create"),
    path("documents/reindex/", views.pdocument_reindex, name="pdocument_reindex"),
    path("documents/run-reminders/", views.pdocument_run_reminders,
         name="pdocument_run_reminders"),

    path("documents/<int:pk>/", views.pdocument_detail, name="pdocument_detail"),
    path("documents/<int:pk>/edit/", views.pdocument_edit, name="pdocument_edit"),
    path("documents/<int:pk>/delete/", views.pdocument_delete, name="pdocument_delete"),

    # Advisory lock.
    path("documents/<int:pk>/checkout/", views.pdocument_checkout, name="pdocument_checkout"),
    path("documents/<int:pk>/release/", views.pdocument_release, name="pdocument_release"),

    # Status transitions.
    path("documents/<int:pk>/activate/", views.pdocument_activate, name="pdocument_activate"),
    path("documents/<int:pk>/supersede/", views.pdocument_supersede, name="pdocument_supersede"),
    path("documents/<int:pk>/archive/", views.pdocument_archive, name="pdocument_archive"),

    # The upload form for the NEXT revision of this document — view lives in the Revisions
    # views module, route lives here because the segment does.
    path("documents/<int:pk>/revisions/add/", views.pdocument_revision_upload,
         name="pdocument_revision_upload"),
]
