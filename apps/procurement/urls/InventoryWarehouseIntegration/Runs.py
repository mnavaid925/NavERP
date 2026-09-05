"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentRun URL patterns.

One first segment, ``replenishment-runs/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory. It is not a prefix of any other segment in the app —
Django matches path COMPONENTS, not strings, so ``replenishment-runs/`` and
``replenishment-policies/`` cannot reach each other however similar they read.

Django is first-match-wins, so the literal route (``add/``) is declared BEFORE the ``<int:pk>/``
one it would otherwise fall into — ``add`` is not a decimal string, so ``<int:pk>`` would in fact
refuse it, but relying on the converter's strictness for correct routing is a rule that stops
holding the moment somebody adds a ``<str:…>`` route.

**The four verbs are POST-only** through their views' ``@require_POST`` decorators; ``release`` is
additionally ``@tenant_admin_required``, because raising requisitions is the step that starts
spending money. Each page carries a ``{% csrf_token %}`` form with an ``onsubmit`` confirm rather
than a confirmation template — the same shape every other verb in this app uses.

``lines/<int:line_id>/decide/`` nests the suggestion under its run ON PURPOSE. The line is the
only model in this sub-module with no tenant column of its own, so the view loads it as
``pk=line_id, run__pk=pk, run__tenant=request.tenant`` and that compound lookup is the IDOR
boundary. A flat ``suggestions/<int:pk>/decide/`` route would let a caller omit the run entirely
and leave the boundary resting on one id.

**Import shape.** The view functions are imported from their ENTITY MODULE, not through
``from apps.procurement import views``. The app-level ``views/__init__.py`` re-export does not
exist until the Integrator lands it, and going through the package would be a star-import cycle at
URLconf import time — the same rule the models and forms layers of this sub-module follow. The
alias keeps the ``views.<name>`` reference idiom of every other urls module in this app, and
resolves to the identical function object once the re-export does land.
"""
from django.urls import path

from apps.procurement.views.InventoryWarehouseIntegration import Runs as views


urlpatterns = [
    path("replenishment-runs/", views.replenishmentrun_list,
         name="replenishmentrun_list"),
    path("replenishment-runs/add/", views.replenishmentrun_create,
         name="replenishmentrun_create"),
    path("replenishment-runs/<int:pk>/", views.replenishmentrun_detail,
         name="replenishmentrun_detail"),
    path("replenishment-runs/<int:pk>/edit/", views.replenishmentrun_edit,
         name="replenishmentrun_edit"),
    path("replenishment-runs/<int:pk>/delete/", views.replenishmentrun_delete,
         name="replenishmentrun_delete"),
    path("replenishment-runs/<int:pk>/generate/", views.replenishmentrun_generate,
         name="replenishmentrun_generate"),
    path("replenishment-runs/<int:pk>/release/", views.replenishmentrun_release,
         name="replenishmentrun_release"),
    path("replenishment-runs/<int:pk>/cancel/", views.replenishmentrun_cancel,
         name="replenishmentrun_cancel"),
    path("replenishment-runs/<int:pk>/lines/<int:line_id>/decide/",
         views.replenishmentsuggestion_decide, name="replenishmentsuggestion_decide"),
]
