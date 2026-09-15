"""Projects 7.10 - ProjectDocumentRevision routes (prefix ``document-revisions/``).

``compare/`` is a LITERAL route listed before the ``<int:pk>/`` ones (the app-wide rule), and the
upload route is nested under the DOCUMENT's pk because an upload is always an upload ONTO a
specific document - the form carries no document chooser of its own.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("document-revisions/", views.pdv_list, name="pdv_list"),
    path("document-revisions/compare/", views.pdv_compare, name="pdv_compare"),
    path("document-revisions/<int:document_pk>/upload/", views.pdv_upload, name="pdv_upload"),
    path("document-revisions/<int:pk>/approve/", views.pdv_approve, name="pdv_approve"),
    path("document-revisions/<int:pk>/restore/", views.pdv_restore, name="pdv_restore"),
    path("document-revisions/<int:pk>/delete/", views.pdv_delete, name="pdv_delete"),
]
