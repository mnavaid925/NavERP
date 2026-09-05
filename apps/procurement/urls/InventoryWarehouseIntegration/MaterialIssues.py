"""Procurement 6.18 Inventory & Warehouse Integration — MaterialIssue URL patterns.

One first segment, ``material-issues/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory. It is not a prefix of any other segment in the app —
Django matches path COMPONENTS, not strings, so ``material-issues/`` cannot reach
``material-requests/`` or anything else however similar it reads.

Django is first-match-wins, so the literal routes (``add/``, and ``lines/add/`` under a pk) are
declared BEFORE the ``<int:…>`` ones they would otherwise fall into. Neither ``add`` nor ``lines``
is a decimal string, so the converters would in fact refuse them — but relying on a converter's
strictness for correct routing is a rule that stops holding the moment somebody adds a ``<str:…>``
route beside it.

**The four verbs are POST-only** through their views' ``@require_POST`` decorators; ``post`` is
additionally ``@tenant_admin_required``, because it mints the stock adjustment that puts a real
movement one SCM click away. Each page carries a ``{% csrf_token %}`` form with an ``onsubmit``
confirm rather than a confirmation template — the same shape every other verb in this app uses.

``lines/<int:line_id>/delete/`` nests the line under its document ON PURPOSE. ``MaterialIssueLine``
is the only model in this entity with no tenant column of its own, so the view loads it as
``pk=line_id, issue__pk=pk, issue__tenant=request.tenant`` and that compound lookup is the IDOR
boundary. A flat ``lines/<int:pk>/delete/`` route would let a caller omit the document entirely and
leave the boundary resting on one id.

**Import shape.** The view functions are imported from their ENTITY MODULE, not through
``from apps.procurement import views``. The app-level ``views/__init__.py`` re-export does not exist
until the Integrator lands it, and going through the package would be a star-import cycle at
URLconf import time — the same rule the models and forms layers of this sub-module follow. The
alias keeps the ``views.<name>`` reference idiom of every other urls module in this app, and
resolves to the identical function object once the re-export does land.
"""
from django.urls import path

from apps.procurement.views.InventoryWarehouseIntegration import MaterialIssues as views


urlpatterns = [
    path("material-issues/", views.materialissue_list,
         name="materialissue_list"),
    path("material-issues/add/", views.materialissue_create,
         name="materialissue_create"),
    path("material-issues/<int:pk>/", views.materialissue_detail,
         name="materialissue_detail"),
    path("material-issues/<int:pk>/edit/", views.materialissue_edit,
         name="materialissue_edit"),
    path("material-issues/<int:pk>/delete/", views.materialissue_delete,
         name="materialissue_delete"),
    path("material-issues/<int:pk>/submit/", views.materialissue_submit,
         name="materialissue_submit"),
    path("material-issues/<int:pk>/post/", views.materialissue_post,
         name="materialissue_post"),
    path("material-issues/<int:pk>/cancel/", views.materialissue_cancel,
         name="materialissue_cancel"),
    path("material-issues/<int:pk>/lines/add/", views.materialissueline_add,
         name="materialissueline_add"),
    path("material-issues/<int:pk>/lines/<int:line_id>/delete/",
         views.materialissueline_delete, name="materialissueline_delete"),
]
