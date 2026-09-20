"""Projects 7.16 Reporting & Business Intelligence — DashboardWidgets URLs (four routes).

Two prefixes, because the child is mounted BOTH ways (B1.5): the create rides under its PARENT
(``reporting/dashboards/<int:pk>/widgets/add/``, where the pk is a ``ProjectDashboard``) while the three
verbs ride on the tile's own pk (``reporting/widgets/<int:pk>/{edit,delete,move}/``). That split is why
``wdg_create`` is listed HERE and not in ``ProjectDashboards.py`` — this is the module whose views take a
tile, and its create is the one route whose pk does not: the two prefixes therefore have different
referents on purpose, which is safe only because they are different route shapes (B1.5).

Order inside the module is the ``add/``-before-``<int:pk>`` house rule (B1.6's "bare list → ``add/`` →
``<int:pk>/`` → ``<int:pk>/<verb>/``) and it costs nothing, since no two routes here share a prefix
shape. The dependency that IS behaviour lives one level up: ``_rbi_dashboards`` must be concatenated
before ``_rbi_widgets`` so ``reporting/dashboards/<int:pk>/`` is claimed by ``pdb_detail`` first (B1.6).
Longer patterns cannot shadow shorter ones in Django's resolver, so this module's ``widgets/add/`` wins
its own shape either way — the ordering is for legibility, and B5.3's smoke sweep asserts all five
literal shapes in this family anyway.

``wdg_delete`` and ``wdg_move`` are POST-only at the view (``@require_POST``, B1.7); a GET is a 405.
``wdg_create`` and ``wdg_edit`` are form views and take GET + POST with no verb gate — B1.7's rule that
``@require_POST`` never wraps a form view. Every tile page links into these routes from
``pdb_detail``/``_widget_grid.html``, and there is no list or detail page for a tile at all (B4.1's
documented exemption), so this module owns no bare register route.
"""
from django.urls import path

from apps.projects.views.ReportingBusinessIntelligence import DashboardWidgets as views

urlpatterns = [
    path("reporting/dashboards/<int:pk>/widgets/add/", views.wdg_create, name="wdg_create"),
    path("reporting/widgets/<int:pk>/edit/", views.wdg_edit, name="wdg_edit"),
    path("reporting/widgets/<int:pk>/delete/", views.wdg_delete, name="wdg_delete"),
    path("reporting/widgets/<int:pk>/move/", views.wdg_move, name="wdg_move"),
]
