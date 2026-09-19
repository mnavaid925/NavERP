"""Projects 7.16 Reporting & Business Intelligence — ProjectDashboards URLs (six routes).

Two literal prefixes and one pk family. Within the module the order IS the behaviour, first match
wins (CLAUDE.md backend rule 6): the dashboard home, then the bare register, then ``add/``, and only
then ``<int:pk>/`` and its verbs — so ``reporting/dashboards/add/`` can never be swallowed by the
detail page's converter, which is the exact bug the ``add``-before-pk ordering exists to stop.

``reporting/home/`` (this module's board the caller lands on) and ``reporting/`` (``rbi_home``, the
BI landing page in ``ReportingHome.py``) are two distinct literals and are deliberately not merged
(B1.4). The child tile routes are NOT here even though two of them share the
``reporting/dashboards/<int:pk>/`` prefix: ``wdg_create``'s pk is the *dashboard's* and lives in
``DashboardWidgets.py``, which owns every route whose view takes a tile (B1.5) — this module's pk
always names a ``ProjectDashboard``.

``pdb_delete`` is POST-only at the view (``@require_POST``, B1.7); the other five take GET, and
``pdb_create`` / ``pdb_edit`` take POST through their form without a verb gate.
"""
from django.urls import path

from apps.projects.views.ReportingBusinessIntelligence import ProjectDashboards as views

urlpatterns = [
    path("reporting/home/", views.pdb_home, name="pdb_home"),
    path("reporting/dashboards/", views.pdb_list, name="pdb_list"),
    path("reporting/dashboards/add/", views.pdb_create, name="pdb_create"),
    path("reporting/dashboards/<int:pk>/", views.pdb_detail, name="pdb_detail"),
    path("reporting/dashboards/<int:pk>/edit/", views.pdb_edit, name="pdb_edit"),
    path("reporting/dashboards/<int:pk>/delete/", views.pdb_delete, name="pdb_delete"),
]
