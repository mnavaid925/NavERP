"""Projects 7.16 Reporting & Business Intelligence — ProjectReports URLs (ten routes, one model).

Every first segment is ``reporting/reports/``, a literal no other sub-module uses, so nothing here
can shadow an earlier route. Within the module the order IS the behaviour (first match wins):
the bare register, then the literal ``add/``, then ``<int:pk>/``, then the pk verbs, then the two
export shapes — so ``add/`` can never be read as a pk and no verb can be swallowed by the detail
page above it.

``rep_delete`` / ``rep_run`` / ``rep_freeze`` / ``rep_favorite`` are POST-only at the view
(``@require_POST``); there is no GET form to reach by typing a URL.
"""
from django.urls import path

from apps.projects.views.ReportingBusinessIntelligence import ProjectReports as views

urlpatterns = [
    path("reporting/reports/", views.rep_list, name="rep_list"),
    path("reporting/reports/add/", views.rep_create, name="rep_create"),
    path("reporting/reports/<int:pk>/", views.rep_detail, name="rep_detail"),
    path("reporting/reports/<int:pk>/edit/", views.rep_edit, name="rep_edit"),
    path("reporting/reports/<int:pk>/delete/", views.rep_delete, name="rep_delete"),
    path("reporting/reports/<int:pk>/run/", views.rep_run, name="rep_run"),
    path("reporting/reports/<int:pk>/freeze/", views.rep_freeze, name="rep_freeze"),
    path("reporting/reports/<int:pk>/favorite/", views.rep_favorite, name="rep_favorite"),
    path("reporting/reports/<int:pk>/csv/", views.rep_csv, name="rep_csv"),
    path("reporting/reports/<int:pk>/json/", views.rep_json, name="rep_json"),
]
