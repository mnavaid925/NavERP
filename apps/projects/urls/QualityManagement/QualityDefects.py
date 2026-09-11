"""Projects 7.6 — QualityDefect routes (prefix ``defects/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``defects/`` is a disjoint literal from every other module's in this app (inventory's
warehouse-floor defect log lives behind ``inventory:``'s own namespace, so no cross-app collision
is possible).
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("defects/", views.qdf_list, name="qdf_list"),
    path("defects/add/", views.qdf_create, name="qdf_create"),
    path("defects/<int:pk>/", views.qdf_detail, name="qdf_detail"),
    path("defects/<int:pk>/edit/", views.qdf_edit, name="qdf_edit"),
    path("defects/<int:pk>/delete/", views.qdf_delete, name="qdf_delete"),
    path("defects/<int:pk>/resolve/", views.qdf_resolve, name="qdf_resolve"),
    path("defects/<int:pk>/close/", views.qdf_close, name="qdf_close"),
    path("defects/<int:pk>/raise-issue/", views.qdf_raise_issue, name="qdf_raise_issue"),
]
