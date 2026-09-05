"""Procurement 6.19 Document & Knowledge Management — KnowledgeResource URL patterns.

One first segment, ``knowledge/``, collision-checked as a whole component against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. No route in this app uses a
converter in its FIRST path component — every first segment is a literal — so no module can
shadow another's namespace. (A ``<str:token>`` converter does exist, at 6.8's
``contract-sign/<str:token>/``, but it sits behind a literal first segment and shadows nothing
outside it. Keeping the first-segment-is-always-a-literal invariant is what makes the guarantee
hold.) The segment is ``knowledge/`` rather than ``templates/`` because ``templates/`` is 6.2's,
where a "template" is a requisition blueprint that actually raises a purchase — the two words
would have collided in the URL space exactly as they collide in conversation.

**Django is first-match-wins, so the order below is behaviour.** The literal route ``add/`` is
declared BEFORE ``<int:pk>/``. Today ``<int:pk>`` would not match ``add`` anyway, but the order is
the rule that stays correct when the next literal — or a future ``<str:…>`` — is added under this
segment, and it costs nothing to keep.

Three verbs sit alongside the CRUD five, all POST-only through their view's ``@require_POST``:

* ``publish/`` and ``archive/`` move a resource on and off the shelf. Neither is
  ``@tenant_admin_required``, unlike ``ppolicy_publish``: publishing a guide adds a how-to to a
  library, while publishing a policy states the workspace's binding rule and retires the version
  it replaces. Different act, different gate.
* ``use/`` records that somebody reached for the resource and increments the counter atomically.
  POST-only is not decoration here — a GET-able counter is incremented by every crawler, every
  link preview and every browser prefetch, which would make the one number this model keeps
  meaningless within a day. It redirects back to the resource's own detail page and never to a
  stored file URL (see the WARNING in the view).

Delete has no confirm template — the list and detail pages carry a ``{% csrf_token %}`` form with
an ``onsubmit`` confirm instead, which is what ``@require_POST`` requires of them.

This module is the LAST of the sub-module's four, so with it in place
``apps/procurement/urls/DocumentKnowledgeManagement/__init__.py`` imports for the first time and
the whole 6.19 url package resolves.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("knowledge/", views.knowledgeresource_list, name="knowledgeresource_list"),
    # Literal BEFORE <int:pk>/ — see the module docstring.
    path("knowledge/add/", views.knowledgeresource_create, name="knowledgeresource_create"),

    path("knowledge/<int:pk>/", views.knowledgeresource_detail, name="knowledgeresource_detail"),
    path("knowledge/<int:pk>/edit/", views.knowledgeresource_edit, name="knowledgeresource_edit"),
    path("knowledge/<int:pk>/delete/", views.knowledgeresource_delete,
         name="knowledgeresource_delete"),

    # Shelf transitions.
    path("knowledge/<int:pk>/publish/", views.knowledgeresource_publish,
         name="knowledgeresource_publish"),
    path("knowledge/<int:pk>/archive/", views.knowledgeresource_archive,
         name="knowledgeresource_archive"),

    # The usage tally — POST-only, atomic, and it redirects to the detail page, never to a file.
    path("knowledge/<int:pk>/use/", views.knowledgeresource_use, name="knowledgeresource_use"),
]
