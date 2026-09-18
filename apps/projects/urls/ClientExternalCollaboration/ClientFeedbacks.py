"""Projects 7.14 Client & External Collaboration — ClientApprovalRequest URLs.
"""
from django.urls import path

from apps.projects.views.ClientExternalCollaboration import ClientFeedbacks as views

urlpatterns = [
    path("client-approvals/", views.cfb_list, name="cfb_list"),
    path("client-approvals/add/", views.cfb_create, name="cfb_create"),
    path("client-approvals/<int:pk>/", views.cfb_detail, name="cfb_detail"),
    path("client-approvals/<int:pk>/edit/", views.cfb_edit, name="cfb_edit"),
    path("client-approvals/<int:pk>/delete/", views.cfb_delete, name="cfb_delete"),
    path("client-approvals/<int:pk>/approve/", views.cfb_approve, name="cfb_approve"),
    path("client-approvals/<int:pk>/reject/", views.cfb_reject, name="cfb_reject"),
]
