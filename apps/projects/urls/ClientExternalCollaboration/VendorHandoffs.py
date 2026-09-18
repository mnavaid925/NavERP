"""Projects 7.14 Client & External Collaboration — VendorHandoff URLs.
"""
from django.urls import path

from apps.projects.views.ClientExternalCollaboration import VendorHandoffs as views

urlpatterns = [
    path("vendor-handoffs/", views.vhd_list, name="vhd_list"),
    path("vendor-handoffs/add/", views.vhd_create, name="vhd_create"),
    path("vendor-handoffs/<int:pk>/", views.vhd_detail, name="vhd_detail"),
    path("vendor-handoffs/<int:pk>/edit/", views.vhd_edit, name="vhd_edit"),
    path("vendor-handoffs/<int:pk>/delete/", views.vhd_delete, name="vhd_delete"),
    path("vendor-handoffs/<int:pk>/accept/", views.vhd_accept, name="vhd_accept"),
    path("vendor-handoffs/<int:pk>/reject/", views.vhd_reject, name="vhd_reject"),
]
