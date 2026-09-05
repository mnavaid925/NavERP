"""Procurement 6.16 Supplier Performance & Evaluation — evaluation + score-line URL patterns.

One first segment, ``supplier-evaluations/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory. It is a LITERAL, like every other first component in
``apps/procurement/urls/`` — this app's standing guarantee is that no route anywhere in it opens
with a converter, and 6.16 does not break it.

**Order is behaviour.** Django resolves first-match-wins, so the four literal
``supplier-evaluations/scores/`` routes are declared BEFORE ``supplier-evaluations/<int:pk>/``.
(``int`` would not swallow ``scores`` anyway — it rejects it and Django falls through — but the
ordering is the rule that keeps that true the day somebody widens the converter to ``<str:...>``
or ``<slug:...>``, at which point ``/supplier-evaluations/scores/`` would resolve to the detail
page with ``pk="scores"`` and the whole score register would disappear behind a 404.)

**Two entity registers, one segment, on purpose.** A score line is only ever read as part of a
period document, so it lives UNDER ``supplier-evaluations/`` rather than claiming a second
top-level component nobody would type.

Gates, restated here because a route table is where a reviewer looks for them:

* ``supplierkpiscore_delete`` is POST-only (``@login_required`` + ``@require_POST``); the list and
  detail pages carry a ``{% csrf_token %}`` form with a confirm handler rather than a link.
* ``supplierevaluation_generate`` is POST-only **and ``@tenant_admin_required``** — it is the
  one-way door that writes the four ``scm.SupplierScorecard`` dimension columns and sets
  ``manual_override``, after which SCM's signal engine skips the scorecard for good
  (``performance.HANDOVER_NOTE``). A GET could otherwise be fired by a prefetching browser.

**There is NO scorecard create route here** (L36, §8). ``scm.SupplierScorecard`` is SCM's model,
FK'd and never re-declared, so the register's "New period" button links straight out to
``scm:scorecard_create``. There is likewise **no ``supplierkpiscore_create``**: lines are written
by ``supplierevaluation_generate``, and a hand-created line would be a measurement with no
computation behind it.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("supplier-evaluations/", views.supplierevaluation_list,
         name="supplierevaluation_list"),

    # ---- The literal `scores/` block. Declared BEFORE `<int:pk>/` — see the docstring. --------
    path("supplier-evaluations/scores/", views.supplierkpiscore_list,
         name="supplierkpiscore_list"),
    path("supplier-evaluations/scores/<int:pk>/", views.supplierkpiscore_detail,
         name="supplierkpiscore_detail"),
    path("supplier-evaluations/scores/<int:pk>/edit/", views.supplierkpiscore_edit,
         name="supplierkpiscore_edit"),
    path("supplier-evaluations/scores/<int:pk>/delete/", views.supplierkpiscore_delete,
         name="supplierkpiscore_delete"),

    # ---- The pk block. Everything below takes a scorecard pk. --------------------------------
    path("supplier-evaluations/<int:pk>/", views.supplierevaluation_detail,
         name="supplierevaluation_detail"),
    path("supplier-evaluations/<int:pk>/generate/", views.supplierevaluation_generate,
         name="supplierevaluation_generate"),
]
