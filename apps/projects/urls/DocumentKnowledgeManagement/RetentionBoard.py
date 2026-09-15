"""Projects 7.10 - the retention & archiving board routes (a computed page, no table).

``run/`` is a literal leaf; the board itself is the segment root, so nothing here can shadow a
register route.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("document-retention/", views.doc_retention, name="doc_retention"),
    path("document-retention/run/", views.doc_retention_run, name="doc_retention_run"),
]
