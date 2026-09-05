"""Procurement 6.17 Risk & Compliance Management — PolicyAttestation URL patterns.

One first segment, ``policy-attestations/``, checked as a whole path COMPONENT against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. It is not a prefix of any existing
segment — and Django matches path components rather than strings, so ``policy-attestations`` could
never collide with ``policies`` or with 6.19's ``procurement-policies`` in any case. No route in
this app uses a converter in its FIRST path component, so nothing outside this module can shadow
it. Re-checked against the concurrently built 6.16 / 6.18 / 6.19 segments before wiring (L43).

Django is first-match-wins, so **every literal route is declared before the ``<int:pk>/`` one it
would otherwise fall into** — here that is ``policy-attestations/add/``.

**The two verbs are gated differently on purpose, and the difference IS the sub-module:**

* ``sign/`` is ``@login_required`` + ``@require_POST`` and **OWNER-gated inside the view** — only
  the person named on the row may sign it, an administrator included. It is deliberately not
  ``@tenant_admin_required``, in either direction: ordinary staff must be able to sign what they
  owe, and nobody may sign what somebody else owes.
* ``exempt/`` is ``@tenant_admin_required`` + ``@require_POST`` and demands a written reason. It is
  the honest administrative answer to "this person should not have to sign", and it is a different
  verb with a different word on it precisely so that it can never be mistaken for a signature.

``delete/`` is POST-only AND admin-gated, and is refused outright once a row has settled — the list
and detail pages carry a ``{% csrf_token %}`` form with an ``onsubmit`` confirm rather than a
confirmation template, which is what ``@require_POST`` requires of them.

This ledger has no number of its own (``PolicyAttestation`` extends ``TenantOwned``, not
``TenantNumbered``): an obligation is identified by the pair of things it joins, so every confirm
dialog and every audit entry quotes the POLICY's ``PPOL-`` number rather than inventing a second
one for the join row.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("policy-attestations/", views.policyattestation_list, name="policyattestation_list"),
    # Literal before <int:pk> — first-match-wins IS behaviour.
    path("policy-attestations/add/", views.policyattestation_create,
         name="policyattestation_create"),

    path("policy-attestations/<int:pk>/", views.policyattestation_detail,
         name="policyattestation_detail"),
    path("policy-attestations/<int:pk>/edit/", views.policyattestation_edit,
         name="policyattestation_edit"),
    path("policy-attestations/<int:pk>/delete/", views.policyattestation_delete,
         name="policyattestation_delete"),

    # The two verbs. Same route shape, deliberately different gates — see the module docstring.
    path("policy-attestations/<int:pk>/sign/", views.attestation_sign, name="attestation_sign"),
    path("policy-attestations/<int:pk>/exempt/", views.attestation_exempt,
         name="attestation_exempt"),
]
