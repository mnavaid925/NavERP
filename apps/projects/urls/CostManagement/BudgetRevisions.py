"""Projects 7.4 — BudgetRevision routes (prefix ``revisions/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("revisions/", views.bvr_list, name="bvr_list"),
    path("revisions/add/", views.bvr_create, name="bvr_create"),
    path("revisions/<int:pk>/", views.bvr_detail, name="bvr_detail"),
    path("revisions/<int:pk>/edit/", views.bvr_edit, name="bvr_edit"),
    path("revisions/<int:pk>/delete/", views.bvr_delete, name="bvr_delete"),
    path("revisions/<int:pk>/submit/", views.bvr_submit, name="bvr_submit"),
    path("revisions/<int:pk>/approve/", views.bvr_approve, name="bvr_approve"),
    path("revisions/<int:pk>/reject/", views.bvr_reject, name="bvr_reject"),
    path("revisions/<int:pk>/activate/", views.bvr_activate, name="bvr_activate"),
]
