"""Procurement 6.19 Document & Knowledge Management — ProcurementDocumentRevision URL patterns.

One first segment, ``document-revisions/``, collision-checked as a whole component against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. No route in this app uses a
converter in its FIRST path component — every first segment is a literal — so nothing can shadow
it and it shadows nothing. (6.8's ``contract-sign/<str:token>/`` converter sits behind a literal
first segment.) It is a
distinct component from ``documents/`` — Django matches path components, not string prefixes —
so the two registers cannot collide.

**The upload route is NOT here.** ``documents/<int:pk>/revisions/add/`` is declared in
``Documents.py`` because url modules own SEGMENTS and that route sits under ``documents/``. Its
view (``views.pdocument_revision_upload``) lives in
``views/DocumentKnowledgeManagement/Revisions.py``, which is fine: the URLconf resolves
``views.<name>`` off the app-level views package, not off a sibling url module. Declaring it in
both places would give one url name two patterns, and ``reverse()`` would answer with whichever
was concatenated last.

**Django is first-match-wins, so the order below is behaviour.** The register is declared before
``<int:pk>/``, and the two verb routes after it; there is no literal route under
``document-revisions/`` that an ``<int:pk>`` could swallow (``<int:pk>`` will not match a word),
but keeping literals-then-pk is the rule that stays correct when the next route is added.

**There is deliberately no ``pdocrevision_edit``** — the documented exemption
``CostForecast`` and ``SpendReportSnapshot`` carry. A revision is immutable: every column except
``change_note`` is ``editable=False``, the only form is the create-path upload form, and the only
write after creation is the approve verb's three-column stamp. A wrong revision is superseded by
the next upload, never amended in place, so the stored file always means what it meant when it
was approved. An edit route would be a way to make an approved version say something it did not
say at approval time.

``<int:pk>/download/`` is a GET: it is a read, and it is the ONLY way 6.19 hands out stored
bytes. Linking ``file.url`` instead would serve the file straight off MEDIA_ROOT with no login,
no session and no tenant check — which is why no template in this sub-module does.

Both verbs are POST-only through their views' ``@require_POST``; ``approve/`` is additionally
``@tenant_admin_required`` (``PermissionDenied`` → 403). ``delete/`` has no confirm template —
the register and both detail pages carry a ``{% csrf_token %}`` form with an ``onsubmit``
confirm instead.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("document-revisions/", views.pdocrevision_list, name="pdocrevision_list"),

    path("document-revisions/<int:pk>/", views.pdocrevision_detail, name="pdocrevision_detail"),
    # The stored bytes, handed back by an authenticated, tenant-scoped view with
    # Content-Disposition: attachment — never by linking MEDIA_URL. GET, because a download is a
    # read; the tenant scope and the 404 are the whole control.
    path("document-revisions/<int:pk>/download/", views.pdocrevision_download,
         name="pdocrevision_download"),

    # Verbs. No edit route by design — see the module docstring.
    path("document-revisions/<int:pk>/approve/", views.pdocrevision_approve,
         name="pdocrevision_approve"),
    path("document-revisions/<int:pk>/delete/", views.pdocrevision_delete,
         name="pdocrevision_delete"),
]
