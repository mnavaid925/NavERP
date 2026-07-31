"""SCM 4.11 Supply Chain Analytics — KpiSnapshot routes (prefix ``kpi-snapshots/``).

COLLISION CHECK — ``kpi-snapshots/`` was checked against the WHOLE concatenated urlconf, not merely
against this block: nothing existing starts with ``kpi``, and it is a distinct whole path component
from 4.11's own ``kpi-targets/`` (Django never splits a component at the hyphen). FREE. The CSV
export is a LITERAL sub-route under this already-claimed segment, so it adds no new first segment and
no new collision surface. NO greedy ``<str:…>`` converter is introduced here.

There is deliberately NO ``add/`` route. ``KpiSnapshot`` is append-only and system-written — the
frozen history every trend line reads — so it ships no ``ModelForm`` (the CRM 1.6 ``ReportSnapshot``
precedent). CRUD here is therefore list + detail + delete, and the CREATE path is the ``capture/``
POST batch. That is a deliberate, documented exception to the CRUD-completeness rule, not an
omission: a hand-typed snapshot would be a fabricated measurement.

Both literals (``capture/``, ``export/``) MUST precede ``<int:pk>/`` — first-match-wins, so a pk
route above them would swallow both and 404 as "snapshot 'capture' not found". The delete verb sits
under its own ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("kpi-snapshots/", views.kpisnapshot_list, name="kpisnapshot_list"),
    # The create path for this model: a tenant-admin POST batch over every active target.
    path("kpi-snapshots/capture/", views.kpisnapshot_capture, name="kpisnapshot_capture"),
    path("kpi-snapshots/export/", views.kpisnapshot_export, name="kpisnapshot_export"),
    path("kpi-snapshots/<int:pk>/", views.kpisnapshot_detail, name="kpisnapshot_detail"),
    path("kpi-snapshots/<int:pk>/delete/", views.kpisnapshot_delete, name="kpisnapshot_delete"),
]
