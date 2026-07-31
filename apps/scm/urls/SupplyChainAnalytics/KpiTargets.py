"""SCM 4.11 Supply Chain Analytics — KpiTarget routes (prefix ``kpi-targets/``).

COLLISION CHECK — ``kpi-targets/`` was checked against the WHOLE concatenated urlconf, not merely
against this block: no existing ``scm`` first segment starts with ``kpi`` at all, so the segment is
free. It is also a distinct whole path component from 4.11's own ``kpi-snapshots/`` — Django matches
whole path components and never splits one at the hyphen, so neither can shadow the other.

``add/`` is literal and MUST precede ``<int:pk>/`` — Django is first-match-wins, so a pk route above
it would swallow the create page and 404 as "target 'add' not found". The one verb route sits under
its own ``<int:pk>/``. This module introduces NO greedy ``<str:…>`` converter: 4.10's
``return-tracking/<str:token>/`` remains the app's only one.

``<int:pk>/snapshot/`` captures THIS target now and writes a ``KpiSnapshot`` and nothing else — like
every 4.11 route it posts no ``StockMove`` and no ``JournalEntry`` (4.11 is read-only over 4.1-4.10).
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("kpi-targets/", views.kpitarget_list, name="kpitarget_list"),
    path("kpi-targets/add/", views.kpitarget_create, name="kpitarget_create"),
    path("kpi-targets/<int:pk>/", views.kpitarget_detail, name="kpitarget_detail"),
    path("kpi-targets/<int:pk>/edit/", views.kpitarget_edit, name="kpitarget_edit"),
    path("kpi-targets/<int:pk>/delete/", views.kpitarget_delete, name="kpitarget_delete"),
    # Capture just this target now — the single-target sibling of `kpi-snapshots/capture/`.
    path("kpi-targets/<int:pk>/snapshot/", views.kpitarget_snapshot, name="kpitarget_snapshot"),
]
