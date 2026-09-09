"""Projects 7.3 — ResourceAllocation routes (prefix ``allocations/``).

Literal routes precede the ``<int:pk>/`` ones — Django is first-match-wins (house rule). The
five verbs hang off the pk segment; the staffing verbs are tenant-admin gated in the views.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("allocations/", views.ral_list, name="ral_list"),
    path("allocations/add/", views.ral_create, name="ral_create"),
    path("allocations/<int:pk>/", views.ral_detail, name="ral_detail"),
    path("allocations/<int:pk>/edit/", views.ral_edit, name="ral_edit"),
    path("allocations/<int:pk>/delete/", views.ral_delete, name="ral_delete"),
    path("allocations/<int:pk>/assign/", views.ral_assign, name="ral_assign"),
    path("allocations/<int:pk>/substitute/", views.ral_substitute, name="ral_substitute"),
    path("allocations/<int:pk>/commit/", views.ral_commit, name="ral_commit"),
    path("allocations/<int:pk>/complete/", views.ral_complete, name="ral_complete"),
    path("allocations/<int:pk>/cancel/", views.ral_cancel, name="ral_cancel"),
]
