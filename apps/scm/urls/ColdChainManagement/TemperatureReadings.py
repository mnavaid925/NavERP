"""SCM 4.15 Cold Chain Management — ``TemperatureReading`` routes. List, detail, create and import.

**THE ABSENT EDIT AND DELETE ROUTES ARE A DECISION, NOT AN OMISSION.** There is no
``temperature-readings/<int:pk>/edit/`` and no ``…/delete/`` here because there is no
``temperaturereading_edit`` view, no ``temperaturereading_delete`` view, no edit form and no delete
template anywhere in the sub-module. ``TemperatureReading`` is APPEND-ONLY — the ``scm.StockMove`` /
``scm.MeterReading`` posture, verbatim: a wrong reading is corrected by filing a LATER, CORRECT one,
exactly the way a wrong stock movement is corrected by a compensating move and a wrong journal entry
by a reversal.

Four things make that the right call rather than a missing feature:

* ``ColdChainMonitor.latest_reading()`` answers with the NEWEST row, so a correction takes effect the
  moment it is filed — nothing has to be edited for the fix to be believed;
* the mistaken row stays visible, which is the *point* of an append-only log;
* every compliance figure in the sub-module is derived from these rows, so silently rewriting one
  retroactively restates all of them with no audit row saying which figure the record was built on;
* it is the only posture that survives an ALCOA+ review, where a silently editable measurement IS
  the finding.

``admin.py`` registers the model read-only for the same reason. **If a later pass is tempted to add
an edit route here, the answer is a second reading, not a mutable first one.**

COLLISION CHECK — ``temperature-readings/`` was checked against the WHOLE concatenated urlconf:
nothing anywhere in ``scm`` starts with ``temperature`` except 4.15's own
``temperature-excursions/``, which is a SEPARATE whole path component. Django never splits a
component at the hyphen, so neither can shadow the other, and neither may be "tidied" to look like
the other — they are different things: one is a raw interval summary, the other is an episode with a
judgement attached. This module introduces NO greedy ``<str:…>`` converter.

**A reading is reached by its OWN pk, not nested under its monitor.** The child pk already identifies
the row, and nesting invites a caller to pair a real child with somebody else's parent id (the 4.12
``compliance-checks/`` rationale). The view scopes on ``tenant`` AND ``monitor__tenant`` regardless.

**The two CREATE routes ARE nested**, and that is the opposite decision for the opposite reason: the
parent has to come from the ROUTE rather than from a POST body, because a parent pk in a body is how
a caller grafts a reading onto somebody else's cold room — and this child's rows ARE that workspace's
compliance figures. They live in THIS module rather than in ``ColdChainMonitors.py`` because they
create a ``TemperatureReading``: the 4.14 ``laborsession_add_activity`` precedent, where the nested
child-create route sits beside the thing it creates.

Both nested routes carry more path segments than ``cold-chain-monitors/<int:pk>/``, so their position
after that module in the concatenated list cannot shadow them.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # The whole-workspace ledger. ALWAYS windowed — with no monitor and no dates the view applies a
    # default window and says so on the page. Every option is a QUERY STRING
    # (?q=&monitor=&source=&band=&date_from=&date_to=), so it adds no route of its own.
    path("temperature-readings/", views.temperaturereading_list, name="temperaturereading_list"),
    path("temperature-readings/<int:pk>/", views.temperaturereading_detail,
         name="temperaturereading_detail"),
    # No edit route. No delete route. See the module docstring — that is the design.

    # Nested under the PARENT so the monitor comes from the route and never from the POST body.
    path("cold-chain-monitors/<int:pk>/readings/add/", views.coldchainmonitor_add_reading,
         name="coldchainmonitor_add_reading"),
    # The logger / gateway CSV import. Tenant-admin only at the view: one press writes up to
    # MAX_BATCH_READINGS rows into the record a regulator reads.
    path("cold-chain-monitors/<int:pk>/readings/import/", views.coldchainmonitor_import_readings,
         name="coldchainmonitor_import_readings"),
]
