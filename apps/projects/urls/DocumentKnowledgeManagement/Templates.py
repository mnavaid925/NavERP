"""Projects 7.10 - DocumentTemplate routes (prefix ``document-templates/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones - Django is first-match-wins. The first
segment ``document-templates/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("document-templates/", views.dtm_list, name="dtm_list"),
    path("document-templates/add/", views.dtm_create, name="dtm_create"),
    path("document-templates/<int:pk>/", views.dtm_detail, name="dtm_detail"),
    path("document-templates/<int:pk>/edit/", views.dtm_edit, name="dtm_edit"),
    path("document-templates/<int:pk>/delete/", views.dtm_delete, name="dtm_delete"),
    path("document-templates/<int:pk>/publish/", views.dtm_publish, name="dtm_publish"),
]
