"""SCM 4.13 Asset Management — ``MeterReading`` routes (prefix ``meter-readings/``). List, create
and detail ONLY.

**THE ABSENT EDIT AND DELETE ROUTES ARE A DECISION, NOT AN OMISSION.** There is no
``meter-readings/<int:pk>/edit/`` and no ``…/delete/`` here because there is no
``meterreading_edit`` view, no ``meterreading_delete`` view, no edit form and no delete template
anywhere in the module. ``MeterReading`` is APPEND-ONLY — the ``scm.StockMove`` posture, verbatim: a
wrong reading is corrected by recording a LATER, CORRECT one, exactly the way a wrong stock movement
is corrected by a compensating move and a wrong journal entry by a reversal.

Three things make that the right call rather than a missing feature:

* ``Asset.latest_reading()`` answers with the NEWEST row, so a correction takes effect the moment it
  is posted — nothing has to be edited for the fix to be believed;
* the mistaken row stays visible in the history, which is the *point* of an append-only log. An
  editable meter reading is a number a scheduler already acted on, changed after the fact, with no
  trace that it ever said anything else;
* a meter-based ``MaintenancePlan`` and a ``condition`` trigger both compare a reading against a
  target, so silently rewriting a reading rewrites every due date derived from it, retroactively,
  with no audit row saying which figure the schedule was actually built on.

``admin.py`` registers the model read-only for the same reason. **If a later pass is tempted to add
an edit route here, the answer is a second reading, not a mutable first one.**

COLLISION CHECK — ``meter-readings/`` was checked against the WHOLE concatenated urlconf, not merely
against this block: nothing anywhere in ``scm`` starts with ``meter``. It is one whole path
component, and Django never splits one at a hyphen, so it can neither shadow nor be shadowed by any
other segment. This module introduces NO greedy ``<str:…>`` converter; 4.10's
``return-tracking/<str:token>/`` remains the app's only one.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "reading 'add' not found". The create page accepts
an optional ``?asset=<pk>`` to pre-fill the machine and its declared meter, which is a QUERY STRING
and therefore adds no route of its own.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("meter-readings/", views.meterreading_list, name="meterreading_list"),
    # Literal — must stay above the <int:pk> route below it. Takes an optional ?asset=<pk> pre-fill.
    path("meter-readings/add/", views.meterreading_create, name="meterreading_create"),
    path("meter-readings/<int:pk>/", views.meterreading_detail, name="meterreading_detail"),
    # No edit route. No delete route. See the module docstring — that is the design.
]
