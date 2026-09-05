"""Procurement 6.17 Risk & Compliance Management — policy-acknowledgment URL patterns.

**Three first segments**, each checked as a whole path COMPONENT against the concatenated inventory
in ``apps/procurement/urls/__init__.py`` (``grep -rn 'path("' apps/procurement/urls/`` over the
whole app, not just this sub-package):

* ``policies/`` — the acknowledgment register, one detail page, and the roster verb
* ``my-policies/`` — the staff page: what I personally still owe
* ``policy-overdue/`` — the chase board

None is a prefix of any existing segment, and none collides with 6.19's ``procurement-policies/``:
Django matches path COMPONENTS, not strings, so ``policies`` and ``procurement-policies`` are two
different components and could never collide even if one were a substring of the other. No route in
this app uses a converter in its FIRST path component — every first segment is a literal — so
nothing outside this module can shadow it. Re-checked against the concurrently built 6.16 / 6.18 /
6.19 segments before wiring (L43).

**These routes deliberately DO NOT include policy authoring** (contract §6a). ``policy_create``,
``policy_edit``, ``policy_delete``, ``policy_publish``, ``policy_archive`` and ``policy_new_version``
are **6.19's**, registered as ``ppolicy_*`` under ``procurement-policies/``, and every page in this
sub-module links to those rather than shipping a second authoring surface for the same table. 6.17
owns the acknowledgement ledger; 6.19 owns the policy.

Django is first-match-wins, so **every literal route is declared before the ``<int:pk>/`` one it
would otherwise fall into**. There is no literal under ``policies/`` today, and the order is stated
anyway because it is the rule that stays correct when the next one is added.

``raise-attestations/`` is POST-only AND administrator-gated through its view decorators
(``@login_required`` → ``@tenant_admin_required`` → ``@require_POST``, in that order, L27); the
detail page carries a ``{% csrf_token %}`` form with an ``onsubmit`` confirm rather than a
confirmation template.

``policy-overdue/`` is deliberately **not** ``@require_POST``, mirroring ``fraud-scan/`` next door:
its GET leg writes nothing and shows who is late, which any member of the workspace should be able
to read, so only the POST leg — which raises an inbox item for each overdue person — is
administrator-gated, inside the view.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("policies/", views.policy_list, name="policy_list"),
    # Literal before <int:pk> — first-match-wins IS behaviour.
    path("policies/<int:pk>/", views.policy_detail, name="policy_detail"),
    # The one verb 6.17 owns on 6.19's table: idempotent, admin-gated, POST-only.
    path("policies/<int:pk>/raise-attestations/", views.policy_raise_attestations,
         name="policy_raise_attestations"),

    # The staff page (L32): reached from the sidebar by ordinary people, never admin-gated.
    path("my-policies/", views.policy_mine, name="policy_mine"),
    # The chase board: GET reads, POST chases (admin-gated inside the view).
    path("policy-overdue/", views.policy_overdue_board, name="policy_overdue_board"),
]
