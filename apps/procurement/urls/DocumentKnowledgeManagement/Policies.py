"""Procurement 6.19 Document & Knowledge Management — ProcurementPolicy URL patterns.

One first segment, ``procurement-policies/``, collision-checked as a whole component against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. No route in this app uses a
converter in its FIRST path component — every first segment is a literal — so no module can
shadow another's namespace. (A ``<str:token>`` converter does exist, at 6.8's
``contract-sign/<str:token>/``, but it sits behind a literal first segment and shadows nothing
outside it. Keeping the first-segment-is-always-a-literal invariant is what makes the guarantee
hold.) The segment is spelt out in full rather than as ``policies/`` because ``policy`` is a word
several later modules will want; a module-qualified segment cannot be claimed twice.

**Django is first-match-wins, so the order below is behaviour.** The literal route ``add/`` is
declared BEFORE ``<int:pk>/``. Today ``<int:pk>`` would not match ``add`` anyway, but the order is
the rule that stays correct when the next literal — or a future ``<str:…>`` — is added under this
segment, and it costs nothing to keep.

Two verbs sit alongside the CRUD five, both POST-only through their view's ``@require_POST``:

* ``publish/`` is additionally ``@tenant_admin_required`` (``PermissionDenied`` -> 403, not a
  redirect). It is the action that puts a rule in force AND archives the version it replaces, in
  one transaction.
* ``archive/`` is not administrator-gated: taking a rule out of the library is the safe
  direction, and it destroys nothing.

Delete has no confirm template — the list and detail pages carry a ``{% csrf_token %}`` form with
an ``onsubmit`` confirm instead, which is what ``@require_POST`` requires of them.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("procurement-policies/", views.ppolicy_list, name="ppolicy_list"),
    # Literal BEFORE <int:pk>/ — see the module docstring.
    path("procurement-policies/add/", views.ppolicy_create, name="ppolicy_create"),

    path("procurement-policies/<int:pk>/", views.ppolicy_detail, name="ppolicy_detail"),
    path("procurement-policies/<int:pk>/edit/", views.ppolicy_edit, name="ppolicy_edit"),
    path("procurement-policies/<int:pk>/delete/", views.ppolicy_delete, name="ppolicy_delete"),

    # Status transitions.
    path("procurement-policies/<int:pk>/publish/", views.ppolicy_publish, name="ppolicy_publish"),
    path("procurement-policies/<int:pk>/archive/", views.ppolicy_archive, name="ppolicy_archive"),
]
