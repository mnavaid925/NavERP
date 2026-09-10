"""Projects 7.7 — ScopeChangeRequest routes (prefix ``scope-changes/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``scope-changes/`` is a disjoint literal from every other module's in this app (7.5's own
change-ish nouns are ``risks/``/``responses/``/``issues/``/``escalations/``).
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("scope-changes/", views.scr_list, name="scr_list"),
    path("scope-changes/add/", views.scr_create, name="scr_create"),
    path("scope-changes/<int:pk>/", views.scr_detail, name="scr_detail"),
    path("scope-changes/<int:pk>/edit/", views.scr_edit, name="scr_edit"),
    path("scope-changes/<int:pk>/delete/", views.scr_delete, name="scr_delete"),
    path("scope-changes/<int:pk>/submit/", views.scr_submit, name="scr_submit"),
    path("scope-changes/<int:pk>/review/", views.scr_review, name="scr_review"),
    path("scope-changes/<int:pk>/approve/", views.scr_approve, name="scr_approve"),
    path("scope-changes/<int:pk>/reject/", views.scr_reject, name="scr_reject"),
    path("scope-changes/<int:pk>/implement/", views.scr_implement, name="scr_implement"),
]
