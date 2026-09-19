"""Projects 7.16 Reporting & Business Intelligence — ReportRuns URLs (seven routes, no create).

Every first segment is ``reporting/runs/``, a literal no other sub-module uses, so nothing here can
shadow an earlier route. Within the module the order IS the behaviour (first match wins): the bare
register, then ``<int:pk>/``, then the pk verbs — so no verb can be swallowed by the detail page
above it.

**There is no ``add/`` and no ``edit/``**, which is the documented CRUD exemption for this entity
(A2.2, B4): a run is minted only by ``rep_freeze``, and ``run_detail``'s inline narrative textarea
and issue form are the only writes the frozen answer allows. There is deliberately no ``run_json``
either — ``rep_json`` is the machine-readable face of a LIVE compute, and a frozen run already IS a
stored JSON payload whose ``run_csv`` reads it verbatim. Two JSON exits for one stored answer is
two code paths that can disagree.

``run_narrative`` / ``run_issue`` / ``run_archive`` / ``run_delete`` are POST-only at the view
(``@require_POST``); ``run_delete`` additionally demands a tenant administrator.
"""
from django.urls import path

from apps.projects.views.ReportingBusinessIntelligence import ReportRuns as views

urlpatterns = [
    path("reporting/runs/", views.run_list, name="run_list"),
    path("reporting/runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("reporting/runs/<int:pk>/narrative/", views.run_narrative, name="run_narrative"),
    path("reporting/runs/<int:pk>/issue/", views.run_issue, name="run_issue"),
    path("reporting/runs/<int:pk>/archive/", views.run_archive, name="run_archive"),
    path("reporting/runs/<int:pk>/delete/", views.run_delete, name="run_delete"),
    path("reporting/runs/<int:pk>/csv/", views.run_csv, name="run_csv"),
]
