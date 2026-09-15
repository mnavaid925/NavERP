"""Projects 7.10 - the repository OVERVIEW route (a computed page, no table).

Its own first segment (``document-repository/``) so it can never shadow a register route.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("document-repository/", views.doc_repository, name="doc_repository"),
]
