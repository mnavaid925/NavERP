"""Projects 7.10 - KnowledgeEntry routes (prefix ``knowledge/``).

``search/`` is a LITERAL route listed before the ``<int:pk>/`` ones (the app-wide rule: Django is
first-match-wins, and an int converter could not capture "search" anyway). ``use/`` and
``publish/`` are POST-only verbs below the pk.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("knowledge/", views.kne_list, name="kne_list"),
    path("knowledge/search/", views.kne_search, name="kne_search"),
    path("knowledge/add/", views.kne_create, name="kne_create"),
    path("knowledge/<int:pk>/", views.kne_detail, name="kne_detail"),
    path("knowledge/<int:pk>/edit/", views.kne_edit, name="kne_edit"),
    path("knowledge/<int:pk>/delete/", views.kne_delete, name="kne_delete"),
    path("knowledge/<int:pk>/use/", views.kne_use, name="kne_use"),
    path("knowledge/<int:pk>/publish/", views.kne_publish, name="kne_publish"),
]
