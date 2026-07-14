"""Accounting 2.2 General Ledger — JournalEntries URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.2 GL — Journal entries
    path("journal-entries/", views.journal_entry_list, name="journal_entry_list"),
    path("journal-entries/add/", views.journal_entry_create, name="journal_entry_create"),
    path("journal-entries/<int:pk>/", views.journal_entry_detail, name="journal_entry_detail"),
    path("journal-entries/<int:pk>/edit/", views.journal_entry_edit, name="journal_entry_edit"),
    path("journal-entries/<int:pk>/delete/", views.journal_entry_delete, name="journal_entry_delete"),
    path("journal-entries/<int:pk>/post/", views.journal_entry_post, name="journal_entry_post"),
    path("journal-entries/<int:pk>/void/", views.journal_entry_void, name="journal_entry_void"),
]
