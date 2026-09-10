"""Projects 7.7 — Requirement routes (prefix ``requirements/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``requirements/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("requirements/", views.req_list, name="req_list"),
    path("requirements/add/", views.req_create, name="req_create"),
    path("requirements/<int:pk>/", views.req_detail, name="req_detail"),
    path("requirements/<int:pk>/edit/", views.req_edit, name="req_edit"),
    path("requirements/<int:pk>/delete/", views.req_delete, name="req_delete"),
    path("requirements/<int:pk>/submit/", views.req_submit, name="req_submit"),
    path("requirements/<int:pk>/approve/", views.req_approve, name="req_approve"),
    path("requirements/<int:pk>/reject/", views.req_reject, name="req_reject"),
    path("requirements/<int:pk>/implement/", views.req_implement, name="req_implement"),
    path("requirements/<int:pk>/verify/", views.req_verify, name="req_verify"),
]
