"""SCM 4.11 Supply Chain Analytics — SupplyChainAlert routes (prefix ``alerts/``).

COLLISION CHECK — ``alerts/`` was checked against the WHOLE concatenated urlconf, not merely against
this block. 4.3 already owns ``reorder-alerts/``, but ``alerts`` and ``reorder-alerts`` are DIFFERENT
whole path components: Django matches whole components and never splits one at the hyphen, so neither
prefix can shadow the other and neither needs renaming. FREE. No other existing segment starts with
``alert`` either. This module introduces NO greedy ``<str:…>`` converter — 4.10's
``return-tracking/<str:token>/`` remains the app's only one.

``add/`` and ``detect/`` are literal and MUST precede ``<int:pk>/`` — Django is first-match-wins, so
a pk route above them would swallow both, and ``detect`` would 404 as "alert 'detect' not found".
All seven verb routes sit under their own ``<int:pk>/``, so none of them can be swallowed either.

Every route here is staff-facing and login-gated; ``detect/`` is the tenant-admin batch that raises
new alerts and re-fires existing ones. None of them posts a ``StockMove`` or a ``JournalEntry`` —
4.11 reads 4.1-4.10 and writes only its own three tables.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("alerts/", views.supplychainalert_list, name="supplychainalert_list"),
    path("alerts/add/", views.supplychainalert_create, name="supplychainalert_create"),
    # The detector batch — raises/re-fires from 4.1-4.10 signals; writes only SupplyChainAlert rows.
    path("alerts/detect/", views.supplychainalert_detect, name="supplychainalert_detect"),
    path("alerts/<int:pk>/", views.supplychainalert_detail, name="supplychainalert_detail"),
    path("alerts/<int:pk>/edit/", views.supplychainalert_edit, name="supplychainalert_edit"),
    path("alerts/<int:pk>/delete/", views.supplychainalert_delete, name="supplychainalert_delete"),
    # Lifecycle — `status` is editable=False and moves ONLY through these five POST actions.
    path("alerts/<int:pk>/acknowledge/", views.supplychainalert_acknowledge,
         name="supplychainalert_acknowledge"),
    path("alerts/<int:pk>/assign/", views.supplychainalert_assign,
         name="supplychainalert_assign"),
    path("alerts/<int:pk>/snooze/", views.supplychainalert_snooze,
         name="supplychainalert_snooze"),
    path("alerts/<int:pk>/resolve/", views.supplychainalert_resolve,
         name="supplychainalert_resolve"),
    path("alerts/<int:pk>/dismiss/", views.supplychainalert_dismiss,
         name="supplychainalert_dismiss"),
]
