"""SCM 4.14 Labor Management — the vocabularies and bounds shared across the sub-module.

**Why this file exists.** Same rule as ``AssetManagement/_choices.py`` and
``ContractCompliance/_choices.py``: a vocabulary read by exactly one model stays on that model
(``LaborStandard.STATUS_CHOICES``). Everything below is read from **two or more directions at
once** —

* ``ACTIVITY_CHOICES`` / ``DIRECT_ACTIVITIES`` / ``INDIRECT_ACTIVITIES`` — declared on
  ``LaborActivity``, re-declared on ``LaborPlanLine`` (a planned bucket is *per activity*), and
  branched on by every session aggregate, the scorecard and the plan generator. One vocabulary, or
  the generator emits lines for an activity the activity table will not accept.
* ``SESSION_STATUS_CHOICES`` — written by ``LaborSession``'s verbs, read by the payroll export
  (which aggregates ``approved`` and nothing else) and by ``LaborActivity.clean()`` (which refuses
  to write into a session that is no longer ``open``).
* ``PLAN_*`` / ``VOLUME_SOURCE_CHOICES`` — carried by ``LaborPlan`` and consumed by the generate
  verb, which must branch on exactly the values the column can hold.
* The bounds — enforced in ``clean()`` so the form, the seeder and every future verb inherit them,
  and quoted back in the messages the views and templates print.

**Pure data — no queries, no model imports, not even ``_base``.** Nothing here imports a sibling
model, so the dependency edge inside the sub-module can only ever run one way
(``LaborStandards`` / ``LaborSessions`` / ``LaborActivities`` / ``LaborPlans`` -> ``_choices``) and
no import cycle is possible.

**``__all__`` is explicit, and the parent re-exports these BY NAME rather than with ``import *``.**
``apps/scm/models/__init__.py`` already star-imports ``AssetManagement/_choices.py`` (``:274``),
which exports ``MAX_LABOUR_RATE``. A second star-imported ``_choices`` re-declaring that token would
**silently shadow** 4.13's depending on import order — a work-order rate ceiling quietly replaced by
a labor-standard one, with no error anywhere. 4.14's rate ceiling is therefore a distinct token,
``MAX_STANDARD_RATE``, and the re-export block spells every name out so the collision is checked at
the point of import instead of hoped for.

**Why the vocabularies are CLOSED.** ``indirect_reason`` in particular could have been a free-text
box, and then "what is our biggest indirect bucket?" would be a pile of strings nobody can total.
A closed set makes that question a ``GROUP BY`` — which is the entire reason a supervisor files the
reason at all.

**The CSS dicts.** Colour is decided in exactly one place per vocabulary (the ``KpiSnapshot.BAND_CSS``
precedent) so a badge cannot be styled one way on the list page and another on the detail page. Only
the six classes that actually exist in ``static/css/theme.css`` may appear —
``badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate``. There is no
``badge-success`` / ``badge-warning`` / ``badge-danger``; those render completely unstyled (L33).
"""
from decimal import Decimal

__all__ = [
    "ACTIVITY_CHOICES", "DIRECT_ACTIVITIES", "INDIRECT_ACTIVITIES", "ACTIVITY_CSS",
    "INDIRECT_REASON_CHOICES",
    "STANDARD_BASIS_CHOICES", "STANDARD_SOURCE_CHOICES",
    "SESSION_SOURCE_CHOICES", "SESSION_STATUS_CHOICES", "SESSION_STATUS_CSS",
    "PLAN_STATUS_CHOICES", "PLAN_STATUS_CSS", "PLAN_BUCKET_CHOICES",
    "VOLUME_SOURCE_CHOICES", "PLAN_METHOD_CHOICES",
    "MAX_SESSION_MINUTES", "MAX_ACTIVITY_MINUTES", "MAX_ACTIVITIES_PER_SESSION",
    "MAX_HORIZON_PERIODS", "MAX_PLAN_LINES", "MIN_PLAN_YEAR", "MAX_BULK_ASSIGN",
    "MAX_STANDARD_RATE", "MAX_SNAPSHOT_MINUTES", "MAX_ALLOWANCE_PCT", "MAX_PRODUCTIVITY_PCT", "MAX_HOURS_PER_SHIFT",
    "MIN_RANKED_MINUTES", "COACHING_THRESHOLD_PCT",
]


# --------------------------------------------------------------------------------------------
# Activity vocabulary — the direct / indirect split
# --------------------------------------------------------------------------------------------
#
# The split between productive work and everything else is present in **all ten** surveyed products
# — SAP EWM's indirect labor task, Infios' "direct, indirect and lost time", Easy Metrics' Indirect
# Time Insights, TZA's delays/indirect coding, Softeon's idle time. It is not a reporting nicety: a
# performance figure is earned minutes over *direct* minutes, so an activity landing on the wrong
# side of this line moves every number on the scorecard.
#
# The two halves are declared separately and ``ACTIVITY_CHOICES`` is their concatenation, so the
# partition is **total and disjoint by construction**. A hand-typed frozenset sitting beside a
# hand-typed choices list is one forgotten edit away from an activity that is neither direct nor
# indirect — and that failure is silent: the value validates, saves, and then vanishes out of both
# sides of every aggregate, so utilisation quietly stops adding up and nothing raises.

#: Productive work — minutes that move goods and are measured against a ``LaborStandard``.
_DIRECT_ACTIVITY_CHOICES = [
    ("receive", "Receiving"),
    ("putaway", "Put-away"),
    ("pick", "Picking"),
    ("pack", "Packing"),
    ("load", "Loading / shipping"),
    ("replenish", "Replenishment"),
    ("cycle_count", "Cycle counting"),
    ("vas", "Value-added service"),
]

#: Everything else the shift is paid for. ``equipment_wait`` / ``system_down`` / ``waiting_for_work``
#: are the *lost time* the industry names separately — sanctioned in the sense that the worker is
#: not at fault, but nobody chose to spend it. ``other_indirect`` is the honest escape hatch: a
#: supervisor forced into a wrong code makes every other code untrustworthy.
_INDIRECT_ACTIVITY_CHOICES = [
    ("break", "Break"),
    ("meeting", "Meeting / briefing"),
    ("training", "Training"),
    ("cleaning", "Cleaning / housekeeping"),
    ("equipment_wait", "Waiting for equipment"),
    ("system_down", "System down"),
    ("waiting_for_work", "Waiting for work"),
    ("safety", "Safety / incident"),
    ("other_indirect", "Other indirect"),
]

#: The column's ``choices``. ``max_length=18``: the longest value is ``waiting_for_work`` at 16, and
#: the extra two characters are deliberate headroom — a 19-char value added later is a column widen
#: on three tables, not "a one-line choices change".
ACTIVITY_CHOICES = _DIRECT_ACTIVITY_CHOICES + _INDIRECT_ACTIVITY_CHOICES

#: **The single source of truth for "is this row productive".** Every aggregate — session
#: ``direct_minutes()``/``indirect_minutes()``, the scorecard, the plan generator's "one line per
#: direct standard" scope — branches on these two names and never on a hand-typed tuple, so the
#: definition of productive work exists once and moves once.
DIRECT_ACTIVITIES = frozenset(value for value, _label in _DIRECT_ACTIVITY_CHOICES)
INDIRECT_ACTIVITIES = frozenset(value for value, _label in _INDIRECT_ACTIVITY_CHOICES)

#: Lost time — indirect minutes nobody chose to spend. This is a **colour** distinction only, not a
#: third bucket in the arithmetic: utilisation counts a system outage as booked-but-not-direct
#: exactly like a meeting. It is red because a floor that is standing idle waiting for a conveyor is
#: the one thing on this page worth seeing from across a room, and amber does not carry that.
_LOST_TIME_ACTIVITIES = ("equipment_wait", "system_down", "waiting_for_work")

#: Built from the rule rather than typed out seventeen times, so it is **total by construction** —
#: an activity added to either half above cannot end up without a badge class and render unstyled,
#: which is exactly the L33 failure this dict exists to prevent. Order of the three assignments is
#: the precedence: lost time overrides the indirect default.
ACTIVITY_CSS = {value: "badge-green" for value, _label in _DIRECT_ACTIVITY_CHOICES}
ACTIVITY_CSS.update({value: "badge-amber" for value, _label in _INDIRECT_ACTIVITY_CHOICES})
ACTIVITY_CSS.update({value: "badge-red" for value in _LOST_TIME_ACTIVITIES})


#: Why the indirect minutes were spent. SAP EWM's **indirect labor task requires a reason**, and
#: Infios and TZA both code delays the same way. ``LaborActivity.clean()`` enforces the pairing in
#: both directions (indirect requires a reason, direct forbids one) exactly as
#: ``ProductionTimeLog.downtime_reason`` does. Longest value is ``supervisor_directed`` at 19, so
#: the column is ``max_length=20``.
#:
#: This is deliberately a *reason*, not a second activity list: ``equipment_wait`` says the worker
#: was waiting, ``equipment_failure`` vs ``no_work_available`` says whose problem it was. The first
#: sizes the loss, the second is what a supervisor can act on.
INDIRECT_REASON_CHOICES = [
    ("scheduled_break", "Scheduled break"),
    ("sanctioned_meeting", "Sanctioned meeting"),
    ("training", "Training"),
    ("housekeeping", "Housekeeping"),
    ("equipment_failure", "Equipment failure"),
    ("system_outage", "System outage"),
    ("no_work_available", "No work available"),
    ("safety_incident", "Safety incident"),
    ("supervisor_directed", "Supervisor directed"),
    ("other", "Other"),
]


# --------------------------------------------------------------------------------------------
# Labor standard vocabulary
# --------------------------------------------------------------------------------------------

#: What one "unit" of the standard counts. TZA publishes single- vs multi-determinant standards and
#: SAP EWM's engineered labor standards do the same: picking is measured per line, receiving per
#: case, a truck seal per task. The basis is what makes ``minutes_per_unit`` mean something —
#: 0.4 minutes is fast per pallet and absurd per case. Longest value is ``per_pallet`` at 10.
STANDARD_BASIS_CHOICES = [
    ("per_unit", "Per unit"),
    ("per_line", "Per order line"),
    ("per_task", "Per task (fixed)"),
    ("per_case", "Per case"),
    ("per_pallet", "Per pallet"),
]

#: Where the number came from, and it is a real difference a supervisor must be able to see before
#: arguing with it: Softeon is honest that its expectancies are "team-defined reasonable
#: expectancies", Blue Yonder derives physics-based ones, Lucas and Easy Metrics derive them from
#: history with ML. A standard nobody can trace the provenance of is a standard nobody accepts.
#:
#: ``learned`` is written by **nothing in this pass** — it is the seam left open for an ML-derived
#: standard, declared now so that feed arrives as a new *row source* rather than a schema change,
#: exactly as ``METER_SOURCE_CHOICES`` reserves ``sensor`` for 11.7.
STANDARD_SOURCE_CHOICES = [
    ("engineered", "Engineered"),
    ("observed", "Time-studied / observed"),
    ("benchmark", "Benchmark library"),
    ("learned", "Learned from history"),
]


# --------------------------------------------------------------------------------------------
# Session vocabulary
# --------------------------------------------------------------------------------------------

#: How the punch reached the system — the provenance Infios, Made4net and Easy Metrics all record.
#: It is stamped by whichever code path files the session and is never a form field, for the same
#: reason 4.13's ``MeterReading.source`` stopped being one: a provenance a user can type is not a
#: provenance. ``badge``, ``mobile`` and ``biometric`` are hardware seams that nothing writes this
#: pass; HRM already owns geofenced and biometric punches on ``AttendanceRecord``, and 4.14 is the
#: warehouse-shift execution layer, not a second attendance system.
SESSION_SOURCE_CHOICES = [
    ("web", "Web self-service"),
    ("badge", "Badge reader"),
    ("mobile", "Mobile device"),
    ("biometric", "Biometric terminal"),
    ("supervisor", "Supervisor entry"),
]

#: The session lifecycle, and the reason it has four states rather than "open/closed" is the
#: approve-then-export lock every LMS ships (Infios, TZA, Made4net; the ``Timesheet`` and
#: ``FreightInvoice`` approval precedents here). ``approved`` freezes the session **and its
#: activities**, and it is the only status the payroll export reads — so a shift still being
#: corrected on the floor cannot leak into a pay period.
SESSION_STATUS_CHOICES = [
    ("open", "Open"),
    ("closed", "Closed"),
    ("approved", "Approved"),
    ("cancelled", "Cancelled"),
]

#: ``open`` is informational rather than green: a session still running is not an achievement, and
#: reserving green for ``approved`` is what lets a supervisor scan a day's list for the ones that
#: still need signing off.
SESSION_STATUS_CSS = {
    "open": "badge-info",
    "closed": "badge-amber",
    "approved": "badge-green",
    "cancelled": "badge-muted",
}


# --------------------------------------------------------------------------------------------
# Labor plan vocabulary
# --------------------------------------------------------------------------------------------

#: A plan is a persisted artefact with a lifecycle — SAP EWM's **planned workload document**, not an
#: ad-hoc screen — so last week's staffing decision is still readable after the volumes it was built
#: from have moved on. ``planned`` is "the generator has run"; ``approved`` is "this is the roster
#: we are staffing to".
PLAN_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("planned", "Planned"),
    ("approved", "Approved"),
    ("archived", "Archived"),
]

PLAN_STATUS_CSS = {
    "draft": "badge-muted",
    "planned": "badge-info",
    "approved": "badge-green",
    "archived": "badge-slate",
}

#: The grain of one plan line. Day is the staffing decision a shift manager actually makes; week is
#: for the seasonal look-ahead Blue Yonder and Easy Metrics both sell. There is deliberately no
#: ``hour`` — an hourly grid over a quarter is a row count nobody reviews, and the intra-day
#: smoothing that would justify it is a later pass, not a bucket value.
PLAN_BUCKET_CHOICES = [
    ("day", "Daily"),
    ("week", "Weekly"),
]

#: Where the generator reads volume from. Made4net's verbatim promise is "forecast labor needs based
#: on inbound/outbound volume", and each value below names a table 4.1-4.7 already keeps: the plan
#: derives its history **at generate time and never stores a history table** (the 4.7 rule), so a
#: regenerate always reflects what actually happened rather than a stale copy of it.
#: ``demand_forecast`` consumes 4.7's forecast — 4.14 must not re-derive seasonality, that is 4.7's
#: job. ``manual`` means zero derived volume and a planner typing ``planned_headcount`` directly,
#: which is the honest answer for a brand-new site with no history at all.
#: Longest value is ``demand_forecast`` at 15, so the column is ``max_length=16``.
VOLUME_SOURCE_CHOICES = [
    ("stock_moves", "Stock movement history"),
    ("pick_tasks", "Pick task history"),
    ("goods_receipts", "Goods receipt history"),
    ("demand_forecast", "Demand forecast (4.7)"),
    ("manual", "Manual entry"),
]

#: How that history becomes a per-bucket volume. Kept to the three arithmetic methods a planner can
#: explain out loud plus ``manual`` — the statistical machinery (exponential smoothing, seasonality
#: decomposition) lives in 4.7 and is reached through ``volume_source="demand_forecast"``, not
#: reimplemented here. Longest value is ``same_period_last_year`` at 21, so ``max_length=24``.
PLAN_METHOD_CHOICES = [
    ("naive", "Last period repeated"),
    ("moving_average", "Moving average"),
    ("same_period_last_year", "Same period last year"),
    ("manual", "Manual"),
]


# --------------------------------------------------------------------------------------------
# Bounds
# --------------------------------------------------------------------------------------------
#
# Every one of these is a CONSTANT. None is computed from the set it bounds — a limit derived from
# the collection the new row is joining is not a limit at all, it just moves with the data (L40).

#: Longest single session — two days. This bounds the session's **LENGTH**, not merely the order of
#: its two ends, for the ``ProductionTimeLog.MAX_LOG_MINUTES`` reason: attended minutes are derived
#: rather than typed, so they never see form validation, and they feed cost per unit, required
#: headcount and the payroll export. A ``1000-01-01 -> 9999-12-31`` clock pair derives ~4.7e9
#: minutes — past what the derived column holds, i.e. a 500 rather than a rejection. A warehouse
#: shift is at most a day; two days covers an overnight shift closed out late the following morning.
MAX_SESSION_MINUTES = 60 * 24 * 2

#: Longest single booked activity — one day. **Deliberately a constant, and deliberately NOT "the
#: session's remaining minutes" or "attended minus booked so far".** A bound derived from the set
#: the new row is joining is not a bound (L40), and while a session is still ``open`` there is no
#: ``clock_out`` to derive one from at all — the check would simply not exist for exactly the rows
#: that are still being written. Over-booking a session past its attended minutes is a real and
#: expected condition (two people, one badge; a forgotten stop), and it is *reported* as
#: ``over_booked_minutes()`` on the exception queue rather than refused at the door.
MAX_ACTIVITY_MINUTES = 60 * 24

#: Buckets one plan may span — a year of days, or seven years of weeks. The plan grid is one DB row
#: per (bucket x in-scope standard), so an unbounded span is an unbounded ``bulk_create`` any
#: logged-in planner can fire (``DemandForecast.MAX_HORIZON_PERIODS``, same reasoning).
#: **The span is computed by integer arithmetic on the two dates** —
#: ``(period_end - period_start).days // (1 if bucket == "day" else 7) + 1`` — never by building the
#: range and taking its ``len()``, which would allocate the very list the bound exists to prevent.
MAX_HORIZON_PERIODS = 366

#: Ceiling on the generated grid, checked as ``periods * standards.count()`` **before anything is
#: allocated**. That is one ``COUNT(*)`` against the standards library, not a built grid measured
#: after the fact — the check has to be cheaper than the thing it is protecting against or it is
#: just the same problem with an extra step.
MAX_PLAN_LINES = 2000

#: Floor on any planning date. Guards the history-window arithmetic: a ``period_start`` in year 1
#: minus ``history_days`` underflows ``datetime.date``, which is an ``OverflowError`` (a 500), not a
#: validation error. ``DemandForecast.MIN_HORIZON_YEAR`` exists for the same reason.
MIN_PLAN_YEAR = 1900

#: Ids accepted by one labor-board bulk-assign POST. Measured as ``len(request.POST.getlist(...))``
#: **before any DB work** — an unbounded id list is an unbounded per-row fetch-check-update loop that
#: any logged-in planner can fire from a hand-built form, and counting after the first query has
#: already lost.
MAX_BULK_ASSIGN = 200

#: Ceiling on ``LaborStandard.labour_rate``, applied as a ``MaxValueValidator`` **on the way in**
#: rather than a clamp on the way out. Same reasoning as ``AssetManagement/_choices.py:160-166``:
#: ``q4()`` clamps rather than raising, and editing a standard is only ``@login_required``, so an
#: absurd rate does not stay local — it flows through ``cost_for()`` into every cost-per-unit figure
#: on the scorecard and every plan built on that activity.
#:
#: **This is a CHARGE-OUT rate carried by a standard, never a person's wage.** ``hrm`` owns
#: compensation (``SalaryStructureTemplate``) and SCM neither reads it nor duplicates it; naming the
#: token ``MAX_STANDARD_RATE`` rather than reusing 4.13's ``MAX_LABOUR_RATE`` keeps that distinction
#: visible *and* keeps the two re-exports from shadowing each other in ``apps.scm.models``.
MAX_STANDARD_RATE = Decimal("100000")

#: Ceiling on a stored earned-minutes snapshot, and it is the COLUMN's ceiling, not a policy one.
#: ``LaborActivity.standard_minutes_snapshot`` and ``LaborPlanLine.standard_minutes_snapshot`` are
#: both ``DecimalField(max_digits=12, decimal_places=4)``, which holds eight integer digits —
#: 99999999.9999 and not one unit more.
#:
#: The trap this exists to close: ``q4()`` looks like it already bounds the value, and it does, but
#: to the *other* column shape in this app — ``DecimalField(14, 4)``, i.e. TEN integer digits. So a
#: figure that passes ``q4()`` can still be two orders of magnitude too wide for the column it is
#: about to be written into, and the failure is a ``DataError`` raised by the driver inside
#: ``save()`` — an uncaught 500 on the sub-module's primary write path, not a validation message.
#: Reaching it takes only a large ``quantity``, which the form accepts up to ``MAX_Q4``.
#:
#: It lives here rather than beside either writer because there are TWO writers of this column
#: shape — the activity's ``_earned_from_snapshots()`` and the plan generator — and a bound that is
#: re-derived at each site is a bound that eventually disagrees with itself.
MAX_SNAPSHOT_MINUTES = Decimal("99999999.9999")

#: Most booked intervals one shift may hold. A CONSTANT, deliberately not "however many fit
#: in the clock window": ``LaborActivity.clean()`` permits booked > attended on purpose (that
#: is what ``over_booked_minutes`` reports) and applies no overlap rule between activities, so
#: nothing in the model stops ten thousand one-minute rows inside one eight-hour shift.
#: Each costs one POST to write, but every later render of that session — and of any LIST page
#: containing it, which prefetches activities for all fifteen rows — pays for the whole set.
#: A stored amplification rather than a request-time one, which is why the cap sits in front
#: of the INSERT rather than in a paginator.
MAX_ACTIVITIES_PER_SESSION = 200

#: Personal, fatigue and delay allowance, as a percentage added on top of the measured time — SAP
#: EWM's "normal time including travel, personal needs, fatigue and unavoidable delay". Capped at
#: 100 because an allowance may at most *double* the standard; past that the number being allowed
#: for has stopped being the standard.
MAX_ALLOWANCE_PCT = Decimal("100")

#: Ceiling on ``LaborPlan.productivity_pct``, the expected achievement against standard that the
#: generator divides required minutes by. 200% is generous headroom for a genuinely high-performing
#: site; the field's *minimum* matters more and lives on the model (1, never 0 — it is a divisor).
MAX_PRODUCTIVITY_PCT = Decimal("200")

#: Ceiling on ``LaborPlan.hours_per_shift``. A shift longer than a day is not a shift, and the value
#: divides required minutes into headcount, so an inflated one silently understates staffing.
MAX_HOURS_PER_SHIFT = Decimal("24")

#: Minimum booked minutes before a worker is RANKED on the scorecard. A worker with three booked
#: minutes and one lucky pick computes at 900% of standard and would otherwise top the leaderboard —
#: a ratio over a tiny denominator is noise wearing the costume of a result. Below this the row is
#: still shown with its figures; it is only excluded from the ranking.
MIN_RANKED_MINUTES = 60

#: Blue Yonder's threshold: sustained performance below 80% of standard is what prompts on-the-floor
#: coaching. Here it is a **report band only** — the scorecard renders a chip. It deliberately does
#: not raise a row in 4.11's ``SupplyChainAlert``: that registry of alert types is closed on purpose
#: and adding a labor metric to it is 4.11's decision, not 4.14's. It is also a conversation a
#: supervisor has, not an incident a system files against a person.
COACHING_THRESHOLD_PCT = Decimal("80")
