"""Procurement 6.16 Supplier Performance & Evaluation — SupplierKpi URL patterns.

One first segment, ``supplier-kpis/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory. It is a LITERAL, like every other first component
in ``apps/procurement/urls/`` — this app's standing guarantee is that no route anywhere in it
opens with a converter, and 6.16 does not break it.

Order is behaviour: Django resolves first-match-wins, so the literal ``add/`` is declared BEFORE
``<int:pk>/``. (``int`` would not swallow ``add`` anyway, but the ordering is the rule that keeps
that true when a ``<str:...>`` route is added next to it.)

``delete/`` is POST-only through the view's ``@require_POST`` decorator; the list and detail
pages carry a ``{% csrf_token %}`` form with an ``onclick`` confirm rather than a link.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("supplier-kpis/", views.supplierkpi_list, name="supplierkpi_list"),
    path("supplier-kpis/add/", views.supplierkpi_create, name="supplierkpi_create"),
    path("supplier-kpis/<int:pk>/", views.supplierkpi_detail, name="supplierkpi_detail"),
    path("supplier-kpis/<int:pk>/edit/", views.supplierkpi_edit, name="supplierkpi_edit"),
    path("supplier-kpis/<int:pk>/delete/", views.supplierkpi_delete,
         name="supplierkpi_delete"),
]
