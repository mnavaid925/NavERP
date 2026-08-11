"""SCM 4.15 Cold Chain Management — ``TemperatureExcursion`` routes (prefix
``temperature-excursions/``).

CRUD plus the five workflow verbs. ``status`` is ``editable=False`` on the model, so the ladder is
the ONLY thing that can move it — which is why every verb gets its own named route rather than a
hidden field on the edit form.

COLLISION CHECK — ``temperature-excursions/`` was checked against the WHOLE concatenated urlconf:
nothing anywhere in ``scm`` starts with ``temperature`` except 4.15's own ``temperature-readings/``,
and Django matches WHOLE path components and never splits one at a hyphen, so the two are unrelated
segments and neither can shadow the other. This module introduces NO greedy ``<str:…>`` converter —
4.10's ``return-tracking/<str:token>/`` remains the app's only one.

ORDER IS BEHAVIOUR: ``add/`` is LITERAL and stays above the ``<int:pk>/`` block, or a later route
with a permissive converter would swallow the create page and 404 as "excursion 'add' not found".

Every verb below is ``@require_POST`` AT THE VIEW, so a GET to one is a 405 rather than a silent
state change, and every one resolves its object with ``tenant=request.tenant`` before any status
guard — a cross-tenant pk must be 404 before any 302 (the 4.12 finding).

Who may press what: ``acknowledge`` is ``@login_required`` (seeing something is not a privileged
act); ``assess``, ``close``, ``dismiss``, ``delete`` and ``raise-work-order`` are all
``@tenant_admin_required`` — the first three because they are terminal or decide product release,
``delete`` because an excursion is an evidence record, and the last because it writes ANOTHER
SUB-MODULE'S table (the ``labor_board_assign`` precedent).
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("temperature-excursions/", views.temperatureexcursion_list,
         name="temperatureexcursion_list"),
    # LITERAL — must stay above the <int:pk> block. The manual, back-dated create: the form takes a
    # monitor and a window, and the VIEW computes every measured figure from the readings inside it.
    path("temperature-excursions/add/", views.temperatureexcursion_create,
         name="temperatureexcursion_create"),

    path("temperature-excursions/<int:pk>/", views.temperatureexcursion_detail,
         name="temperatureexcursion_detail"),
    # The TRIAGE half only — every detector-written column is editable=False on the model and absent
    # from the form.
    path("temperature-excursions/<int:pk>/edit/", views.temperatureexcursion_edit,
         name="temperatureexcursion_edit"),
    path("temperature-excursions/<int:pk>/delete/", views.temperatureexcursion_delete,
         name="temperatureexcursion_delete"),

    # ---- the ladder: open -> investigating -> assessed -> closed, with dismiss as the side exit ---
    path("temperature-excursions/<int:pk>/acknowledge/", views.temperatureexcursion_acknowledge,
         name="temperatureexcursion_acknowledge"),
    # Takes a payload (assessment / cause / corrective_action) — the one hand-rolled verb.
    path("temperature-excursions/<int:pk>/assess/", views.temperatureexcursion_assess,
         name="temperatureexcursion_assess"),
    # Refuses while the episode is still running, checked INSIDE the row lock.
    path("temperature-excursions/<int:pk>/close/", views.temperatureexcursion_close,
         name="temperatureexcursion_close"),
    path("temperature-excursions/<int:pk>/dismiss/", views.temperatureexcursion_dismiss,
         name="temperatureexcursion_dismiss"),

    # The sub-module's ONLY cross-sub-module write: one scm.MaintenanceWorkOrder against the failing
    # unit, with an EXISTING 4.13 SOURCE_CHOICES value and no reciprocal edit to any 4.13 vocabulary.
    # 4.15 adds NO route under assets/, maintenance-plans/ or maintenance-work-orders/.
    path("temperature-excursions/<int:pk>/raise-work-order/",
         views.temperatureexcursion_raise_work_order,
         name="temperatureexcursion_raise_work_order"),
]
