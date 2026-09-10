"""Projects 7.7 — ScopeVerification routes (prefix ``scope-verifications/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``scope-verifications/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("scope-verifications/", views.svr_list, name="svr_list"),
    path("scope-verifications/add/", views.svr_create, name="svr_create"),
    path("scope-verifications/<int:pk>/", views.svr_detail, name="svr_detail"),
    path("scope-verifications/<int:pk>/edit/", views.svr_edit, name="svr_edit"),
    path("scope-verifications/<int:pk>/delete/", views.svr_delete, name="svr_delete"),
    path("scope-verifications/<int:pk>/accept/", views.svr_accept, name="svr_accept"),
    path("scope-verifications/<int:pk>/reject/", views.svr_reject, name="svr_reject"),
    path("scope-verifications/<int:pk>/waive/", views.svr_waive, name="svr_waive"),
]
