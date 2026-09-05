"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentPolicy URL patterns.

One first segment, ``replenishment-policies/``, collision-checked as a whole component against
the concatenated ``urls/__init__.py`` inventory. It is not a prefix of any other segment in the
app — Django matches path COMPONENTS, not strings, so ``replenishment-policies/`` and
``replenishment-runs/`` cannot reach each other however similar they read.

Django is first-match-wins, so the literal route (``add/``) is declared BEFORE the ``<int:pk>/``
one it would otherwise fall into — ``add`` is not a decimal string, so ``<int:pk>`` would in fact
refuse it, but relying on the converter's strictness for correct routing is a rule that stops
holding the moment somebody adds a ``<str:…>`` route. ``delete/`` is POST-only through the view's
decorator — the list and detail pages carry a ``{% csrf_token %}`` form with an ``onsubmit``
confirm instead of a confirm template.

**Import shape.** The view functions are imported from their ENTITY MODULE, not through
``from apps.procurement import views``. The app-level ``views/__init__.py`` re-export does not
exist until the Integrator lands it, and going through the package would be a star-import cycle at
URLconf import time — the same rule the models and forms layers of this sub-module follow. The
alias keeps the ``views.<name>`` reference idiom of every other urls module in this app, and
resolves to the identical function object once the re-export does land.
"""
from django.urls import path

from apps.procurement.views.InventoryWarehouseIntegration import Policies as views


urlpatterns = [
    path("replenishment-policies/", views.replenishmentpolicy_list,
         name="replenishmentpolicy_list"),
    path("replenishment-policies/add/", views.replenishmentpolicy_create,
         name="replenishmentpolicy_create"),
    path("replenishment-policies/<int:pk>/", views.replenishmentpolicy_detail,
         name="replenishmentpolicy_detail"),
    path("replenishment-policies/<int:pk>/edit/", views.replenishmentpolicy_edit,
         name="replenishmentpolicy_edit"),
    path("replenishment-policies/<int:pk>/delete/", views.replenishmentpolicy_delete,
         name="replenishmentpolicy_delete"),
]
