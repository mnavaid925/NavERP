"""Projects 7.3 — ResourceTimeEntry routes (prefix ``time-entries/``).

Literal routes precede the ``<int:pk>/`` ones — Django is first-match-wins (house rule). The
weekly bulk-approve route's ``week/`` literal segment is listed before the ``<int:pk>/`` routes;
``<int:week>`` in the middle position is unique in the app, but the ordering is commented for
the invariant it keeps.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("time-entries/", views.rte_list, name="rte_list"),
    path("time-entries/add/", views.rte_create, name="rte_create"),
    path("time-entries/week/<int:resource>/<int:year>/w<int:week>/approve/",
         views.rte_approve_week, name="rte_approve_week"),
    path("time-entries/<int:pk>/", views.rte_detail, name="rte_detail"),
    path("time-entries/<int:pk>/edit/", views.rte_edit, name="rte_edit"),
    path("time-entries/<int:pk>/delete/", views.rte_delete, name="rte_delete"),
    path("time-entries/<int:pk>/submit/", views.rte_submit, name="rte_submit"),
    path("time-entries/<int:pk>/approve/", views.rte_approve, name="rte_approve"),
    path("time-entries/<int:pk>/reject/", views.rte_reject, name="rte_reject"),
]
