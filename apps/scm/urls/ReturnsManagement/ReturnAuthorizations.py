"""SCM 4.10 Returns Management — ReturnAuthorization routes (prefix ``returns/``).

Seven verb routes, every one under ``<int:pk>/``, so none can be swallowed by a pk route. NONE of
them posts a StockMove — the RMA is a non-posting document. ``draft-credit-note/`` is the only
route here that writes anything outside SCM, and it drafts an ``accounting.Invoice(kind=
"credit_note", status="draft")`` and stops: SCM posts no JournalEntry (L29).

The public token pages are deliberately NOT under this prefix — they live on their own
``return-tracking/`` first segment, which removes the greedy ``<str:token>`` ordering hazard
entirely rather than relying on route order to contain it.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("returns/", views.returnauthorization_list, name="returnauthorization_list"),
    path("returns/add/", views.returnauthorization_create, name="returnauthorization_create"),
    path("returns/<int:pk>/", views.returnauthorization_detail,
         name="returnauthorization_detail"),
    path("returns/<int:pk>/edit/", views.returnauthorization_edit,
         name="returnauthorization_edit"),
    path("returns/<int:pk>/delete/", views.returnauthorization_delete,
         name="returnauthorization_delete"),
    # Lifecycle — no stock effect, no journal entry.
    path("returns/<int:pk>/approve/", views.returnauthorization_approve,
         name="returnauthorization_approve"),
    path("returns/<int:pk>/reject/", views.returnauthorization_reject,
         name="returnauthorization_reject"),
    path("returns/<int:pk>/cancel/", views.returnauthorization_cancel,
         name="returnauthorization_cancel"),
    # Creates `received_pending` bench rows. Posts NOTHING — the bench is off-ledger by design.
    path("returns/<int:pk>/receive-all/", views.returnauthorization_receive_all,
         name="returnauthorization_receive_all"),
    # The accounting hand-off (L29) — a DRAFT credit note, never a journal entry.
    path("returns/<int:pk>/draft-credit-note/", views.returnauthorization_draft_credit_note,
         name="returnauthorization_draft_credit_note"),
    path("returns/<int:pk>/draft-replacement/", views.returnauthorization_draft_replacement,
         name="returnauthorization_draft_replacement"),
    path("returns/<int:pk>/raise-warranty-claim/", views.returnauthorization_raise_warranty_claim,
         name="returnauthorization_raise_warranty_claim"),
]
