"""Accounting 2.10 Multi-Entity & Consolidation — IntercompanyTransactions URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.10 Multi-entity / Intercompany
    path("intercompany/", views.intercompany_list, name="intercompany_list"),
    path("intercompany/add/", views.intercompany_create, name="intercompany_create"),
    path("intercompany/<int:pk>/", views.intercompany_detail, name="intercompany_detail"),
    path("intercompany/<int:pk>/edit/", views.intercompany_edit, name="intercompany_edit"),
    path("intercompany/<int:pk>/delete/", views.intercompany_delete, name="intercompany_delete"),
    path("intercompany/<int:pk>/post/", views.intercompany_post, name="intercompany_post"),
    path("intercompany/<int:pk>/toggle-eliminated/", views.intercompany_toggle_eliminated, name="intercompany_toggle_eliminated"),
]
