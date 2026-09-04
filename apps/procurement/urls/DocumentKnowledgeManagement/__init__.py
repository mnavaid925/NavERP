"""6.19 Document & Knowledge Management URL patterns — one module per entity.

``app_name`` is set once in ``apps/procurement/urls/__init__.py``; this package only
concatenates its four entity modules' ``urlpatterns``.

Four first segments are claimed by this sub-module, every one of them a new whole component
checked against the inventory in ``apps/procurement/urls/__init__.py``: ``documents/``,
``document-revisions/``, ``procurement-policies/`` and ``knowledge/``. None is a prefix of any
other segment in the app — Django matches path components, not strings — and the names were
chosen around segments already taken: ``templates/`` is 6.2's, and ``contracts/`` /
``clauses/`` / ``milestones/`` / ``renewals/`` are 6.8's.

This app registers no greedy ``<str:…>`` converter anywhere, so there is no cross-module
shadowing surface to reason about. Inside each module the literal routes are declared before
the ``<int:pk>/`` ones, because Django is first-match-wins.

``documents/<int:pk>/revisions/add/`` sits in ``Documents`` rather than ``Revisions``: url
modules own SEGMENTS, and that route is under ``documents/``. Its view lives in the Revisions
views module, which is fine — the URLconf resolves ``views.<name>`` off the app-level views
package, not off a sibling url module.

**There is deliberately no ``pdocrevision_edit``.** A revision is immutable: every column except
``change_note`` is ``editable=False``, the only form is the create-path upload form, and the
only post-create write is the approve verb's stamp. The exemption is the same one
``CostForecast`` and ``SpendReportSnapshot`` carry — a wrong revision is superseded by the next
upload, never amended in place, so the stored file always means what it meant.
"""
from .Documents import urlpatterns as _dkm_documents
from .Revisions import urlpatterns as _dkm_revisions
from .Policies import urlpatterns as _dkm_policies
from .KnowledgeResources import urlpatterns as _dkm_knowledge


urlpatterns = [
    *_dkm_documents,   # documents/ CRUD + lock, status and engine verbs + revision upload
    *_dkm_revisions,   # document-revisions/ chain register, detail, approve, delete (no edit)
    *_dkm_policies,    # procurement-policies/ CRUD + publish / archive
    *_dkm_knowledge,   # knowledge/ CRUD + publish / archive / use
]
