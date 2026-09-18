"""Projects 7.14 Client & External Collaboration — StatementOfWork URLs.
"""
from django.urls import path

from apps.projects.views.ClientExternalCollaboration import StatementOfWorks as views

urlpatterns = [
    path("statements-of-work/", views.sow_list, name="sow_list"),
    path("statements-of-work/add/", views.sow_create, name="sow_create"),
    path("statements-of-work/<int:pk>/", views.sow_detail, name="sow_detail"),
    path("statements-of-work/<int:pk>/edit/", views.sow_edit, name="sow_edit"),
    path("statements-of-work/<int:pk>/delete/", views.sow_delete, name="sow_delete"),
    path("statements-of-work/<int:pk>/activate/", views.sow_activate, name="sow_activate"),
    path("statements-of-work/<int:pk>/amendments/add/", views.sow_amendment_create, name="sow_amendment_create"),
]
