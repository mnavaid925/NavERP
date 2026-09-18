"""Projects 7.14 Client & External Collaboration — ClientPortalAccess URLs.
"""
from django.urls import path

from apps.projects.views.ClientExternalCollaboration import ClientPortals as views

urlpatterns = [
    path("client-portal-access/", views.cpa_list, name="cpa_list"),
    path("client-portal-access/add/", views.cpa_create, name="cpa_create"),
    path("client-portal-access/<int:pk>/", views.cpa_detail, name="cpa_detail"),
    path("client-portal-access/<int:pk>/edit/", views.cpa_edit, name="cpa_edit"),
    path("client-portal-access/<int:pk>/delete/", views.cpa_delete, name="cpa_delete"),
]
