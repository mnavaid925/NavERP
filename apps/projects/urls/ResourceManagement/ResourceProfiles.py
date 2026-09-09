"""Projects 7.3 — ResourceProfile routes (prefix ``resource-profiles/``).

Literal routes precede the ``<int:pk>/`` ones — Django is first-match-wins (house rule).
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("resource-profiles/", views.rsp_list, name="rsp_list"),
    path("resource-profiles/add/", views.rsp_create, name="rsp_create"),
    path("resource-profiles/<int:pk>/", views.rsp_detail, name="rsp_detail"),
    path("resource-profiles/<int:pk>/edit/", views.rsp_edit, name="rsp_edit"),
    path("resource-profiles/<int:pk>/delete/", views.rsp_delete, name="rsp_delete"),
]
