"""SCM 4.10 Returns Management — the computed queues and the portal surfaces.

Four first segments, all checked against the WHOLE concatenated urlconf rather than just this
block: ``refund-queue/``, ``return-portal/``, ``returns-bench/`` and ``return-tracking/``.

``return-tracking/<str:token>/`` sits on its OWN first segment rather than under
``returns/track/<str:token>/``. That removes the greedy-converter ordering hazard entirely — no
future ``returns/<something>/`` route can shadow the public page or be shadowed by it — and it is
the reason this block needs no ordering caveat of its own beyond the literal ``label/`` suffix.

``returnauthorization_public`` and ``returnauthorization_label`` are the ONLY unauthenticated
routes in ``apps/scm``. The unguessable ``public_token`` is the bearer credential, the state guard
lives in the object lookup, the tenant is taken off the object rather than the request, and the
tenant's own ``is_active`` flag is re-checked.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # Refund Processing — the computed settlement queue (a sidebar bullet).
    path("refund-queue/", views.refund_queue, name="refund_queue"),
    # The STAFF console the "Return Portal" bullet points at (L32), plus the logged-in CUSTOMER's
    # own request form. Both are login-gated; only the request form binds to CustomerPortalAccess.
    path("return-portal/", views.return_portal, name="return_portal"),
    path("return-portal/request/", views.portal_return_create, name="portal_return_create"),
    # The bench queues.
    path("returns-bench/", views.returns_awaiting_disposition,
         name="returns_awaiting_disposition"),
    path("returns-bench/advance-refunds/", views.advance_refund_exposure,
         name="advance_refund_exposure"),
    # PUBLIC — no decorator. The literal `label/` suffix keeps the two apart with no ambiguity.
    path("return-tracking/<str:token>/", views.returnauthorization_public,
         name="returnauthorization_public"),
    path("return-tracking/<str:token>/label/", views.returnauthorization_label,
         name="returnauthorization_label"),
]
