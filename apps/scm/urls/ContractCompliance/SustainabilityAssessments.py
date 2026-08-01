"""SCM 4.12 Contract & Compliance Management — SustainabilityAssessment routes.

Prefix ``sustainability-assessments/``.

COLLISION CHECK — the segment was checked against the WHOLE concatenated ``apps/scm/urls`` list, not
merely against this block: no existing ``scm`` first segment starts with ``sustainability`` at all,
so it is free. Note that 4.2 owns ``risk-assessments/`` — an unrelated first component, not
``…/assessments``: Django matches WHOLE path components and never splits one at the hyphen, so
neither route can shadow the other and neither should be "tidied" to look like the other.

``add/`` is literal and MUST precede ``<int:pk>/`` — resolution is first-match-wins, so a pk route
placed above it would swallow the create page and 404 as "assessment 'add' not found".

This module introduces NO greedy ``<str:…>`` converter (4.10's ``return-tracking/<str:token>/``
remains the app's only one) and NO verb routes: nothing in 4.12 drives this entity's ``status``, so
there is no submit/approve/void to post to. The carbon report is a separate page under its own
``carbon-footprint/`` segment — this list's header only links to it.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("sustainability-assessments/", views.sustainabilityassessment_list,
         name="sustainabilityassessment_list"),
    path("sustainability-assessments/add/", views.sustainabilityassessment_create,
         name="sustainabilityassessment_create"),
    path("sustainability-assessments/<int:pk>/", views.sustainabilityassessment_detail,
         name="sustainabilityassessment_detail"),
    path("sustainability-assessments/<int:pk>/edit/", views.sustainabilityassessment_edit,
         name="sustainabilityassessment_edit"),
    path("sustainability-assessments/<int:pk>/delete/", views.sustainabilityassessment_delete,
         name="sustainabilityassessment_delete"),
]
