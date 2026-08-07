"""SCM 4.14 Labor Management — the ``LaborActivity`` form: one booked stretch of a shift.

**``session`` is ABSENT from ``Meta.fields``, and that absence IS the control.** An activity is
created under the PARENT route (``labor-sessions/<pk>/activities/add/``), which resolves the shift
with ``tenant=request.tenant`` and hands this form an instance already bound to it. A ``session``
field here would let any logged-in member post a pk in the body and graft minutes onto somebody
else's shift — minutes that land in that worker's performance figures and, once the shift is
approved, in the payroll export. There is no path from form data to the column at all, which is a
stronger statement than "a view checks for it": the ``MaintenanceWorkOrderForm.status`` posture.

**``standard`` and all four ``*_snapshot`` columns are absent for the reason the model docstring
gives at length.** They are the MEASUREMENT — resolved exactly once, in the create path, by
``select_standard()``, and recomputed only from data already on the row. A standard a user can type
is not a measurement, it is a claim (L22), and a typed ``standard_minutes_snapshot`` would be a
self-awarded performance score on a record that feeds pay. ``duration_minutes`` is derived in
``LaborActivity.save()`` from the interval, so a field for it would be a field for a subtraction.

**``started_at`` / ``ended_at`` ARE on the form, and that is a deliberate, narrow exception to
L22.** They are not system stamps; they are the human-entered SUBJECT of the record — a supervisor
booking "09:40 to 10:25 on picking" after the fact, and correcting it when the mis-typed one is
spotted. L22's real failure was a ``DateInput(type="date")`` silently truncating the time off a
datetime, which is why the widget treatment below is not optional. Every ``*_at`` that IS a stamp
(``created_at`` / ``updated_at``) stays off, as does every column a verb owns.

**The three task dropdowns are narrowed to OPEN tasks but NOT to the chosen activity type.** The
type/task match (``pick_task`` ↔ ``pick``/``pack``, ``putaway_task`` ↔ ``putaway``,
``cycle_count_task`` ↔ ``cycle_count``) lives in ``LaborActivity.clean()``, where it also holds
against a crafted POST — a narrowed ``<select>`` never has. Narrowing by type here as well would
require the type to have been chosen before the task lists could be built, which an unbound create
form cannot do: it would render three permanently empty selects on the screen that matters, the 4.5
``ship_to_address`` failure and the reason ``MaintenanceWorkOrderForm.plan`` is offered unfiltered.

**Nothing in this file re-implements a model rule.** The direct/indirect pairing, the interval
bounds, the inside-the-shift window, the session-must-still-be-``open`` refusal and the
one-task-pointer rule all live in ``LaborActivity.clean()`` and run from here through Django's
``_post_clean``. One implementation each — a second copy on the form is how two implementations of
one rule start disagreeing about which POST is legal.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

from apps.scm.models import CycleCountTask, LaborActivity, PickTask, PutawayTask


# -------------------------------------------------------------------------------------------------
# What "still open" means on each of the three 4.4 task tables.
# -------------------------------------------------------------------------------------------------
#
# ``PutawayTask`` publishes ``OPEN_STATUSES`` and it is read straight off the model, so that table's
# definition of open exists in one place. ``PickTask`` and ``CycleCountTask`` do NOT publish one, and
# **4.14 adds no column, constant or method to a shipped 4.4 model** (the plan's "no change to any
# shipped model file" line) — so the two sets are named HERE rather than grafted onto tables this
# sub-module does not own. Both match the labor board's own reading of open exactly; if 4.4 ever
# grows a real ``OPEN_STATUSES`` on either table, these two names should be deleted in favour of it
# rather than left to drift beside it.
#
# Not ``PickTask.EDITABLE_STATUSES`` and not ``PICKABLE_STATUSES``: the first stops at ``released``
# and the second starts at it, so either alone hides half the tasks somebody is standing in front of
# right now. Their union happens to be the right set, but a union of two constants that mean other
# things is an accident waiting to be "tidied" — the set is spelt out instead.
_OPEN_PICK_STATUSES = ("pending", "released", "picking")

#: ``scheduled`` / ``in_progress`` — a count that has reached ``counted`` or ``reconciled`` is
#: finished, and minutes booked against it are minutes somebody else's variance report will read
#: back as effort spent on work that was already done.
_OPEN_COUNT_STATUSES = ("scheduled", "in_progress")

#: The parse formats accepted for ``started_at`` / ``ended_at``. ``TenantModelForm`` already sets
#: three of these; the ISO-with-seconds spelling is the one it omits. See :meth:`__init__` for why
#: that one matters and why the widget itself is NOT restated here.
_DATETIME_INPUT_FORMATS = [
    "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
]


def _scope_open_tasks(form, name, queryset, open_statuses):
    """Point one task dropdown at this tenant's OPEN tasks, plus the row's own stored choice.

    Three separate narrowings, each of which fails its own way if dropped:

    * **tenant** — re-filtered from the passed queryset rather than chained off whatever
      ``TenantModelForm`` left behind, because the base scopes a ``ModelChoiceField`` only
      ``if tenant is not None``; a tenant-less caller otherwise falls through to the unscoped default
      manager and the select lists every workspace's tasks. Scoping a dropdown is presentation, but
      presentation should not leak (the ``AssetManagement._scope_to_tenant`` idiom, verbatim).
    * **open statuses** — booking minutes against a ``picked`` / ``completed`` / ``reconciled`` task
      is booking them against work that is already finished, and 4.4's board reads "time booked
      against this task" straight back out of these pointers.
    * **the instance's own pk** — a task legitimately closes while its activity is still being
      corrected. Without the ``Q(pk=current_id)`` leg the stored task drops out of the ``<select>``,
      the edit form renders with nothing chosen, and saving an unrelated change silently NULLs the
      pointer: the minutes survive and the record of what they were spent on does not. That is
      ``ProductionTimeLogForm.work_order``'s idiom and ``_keep_current``'s reasoning, applied to a
      status rather than to a ``PartyRole``.

    The pk leg is applied INSIDE the tenant filter, never beside it, so re-admitting a stored choice
    can never re-admit another workspace's task — the widening is over status only.
    """
    if name not in form.fields:
        return
    if form.tenant is None:
        form.fields[name].queryset = queryset.none()
        return
    condition = Q(status__in=open_statuses)
    current_id = getattr(form.instance, f"{name}_id", None)
    if current_id is not None:
        condition |= Q(pk=current_id)
    form.fields[name].queryset = queryset.filter(condition, tenant=form.tenant)


class LaborActivityForm(TenantModelForm):
    """One booked interval inside a shift: what was done, for how long, how much came out of it."""

    class Meta:
        model = LaborActivity
        # A WHITELIST, never `Meta.exclude` — a whitelist fails CLOSED when a column is added later,
        # an exclude list fails open and quietly puts the new column on the form. Deliberately
        # ABSENT: `session` (the parent route owns it — see the module docstring, this is the whole
        # point), `standard` + all four `*_snapshot` columns (the measurement, `editable=False`,
        # stamped by `select_standard()` in the create path), `duration_minutes` (derived in
        # `save()` from the interval), `tenant` (stamped by `crud_create`, and in `__init__` below so
        # the model's own guard can read it), `number` (auto-assigned in `TenantNumbered.save()`),
        # `created_at` / `updated_at`.
        fields = [
            # what kind of work, and — for non-productive work — why. The pairing between these two
            # is enforced in `LaborActivity.clean()` in BOTH directions: indirect requires a reason,
            # direct forbids one. A reason field with no required companion is a bucket nobody can
            # total afterwards, which is the entire point of filing it.
            "activity_type", "indirect_reason",
            # the interval. The legitimate L22 exception — see the module docstring.
            "started_at", "ended_at",
            # the output, and the ONE recorded accuracy input. Accuracy % is derived from the pair
            # and never stored, so correcting a mis-typed quantity corrects the percentage too.
            "quantity", "error_quantity",
            # pointers OUT to 4.4's existing task tables — at most one, and it must match the work.
            # `reference` is the honest fallback for work with no task document at all; without it a
            # supervisor would reach for whichever task pointer was nearest.
            "pick_task", "putaway_task", "cycle_count_task", "reference",
            "notes",
        ]
        # No `started_at` / `ended_at` entry here on purpose — see `__init__`, where the reason is
        # that a Meta widget for either would be silently discarded rather than merely redundant.
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. `crud_create` assigns the tenant only AFTER `is_valid()`, so without this a new
        # activity reaches `LaborActivity.clean()` with `tenant_id` None — the exact case its
        # cross-tenant FK guard skips by design (an unsaved instance's `self.tenant` would raise
        # `RelatedObjectDoesNotExist` rather than return None) — and that guard would be dead code on
        # the create path, which is the only path a crafted task pk can arrive on. (Not
        # `TenantUniqueMixin`: the sole `unique_together` is `(tenant, number)` and `number` is auto
        # and off the form, so its second half would have nothing to check.)
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the interval widgets ---------------------------------------------------------------
        # `TenantModelForm` already replaces every `DateTimeField`'s widget with
        # `DateTimeInput(type="datetime-local", format="%Y-%m-%dT%H:%M")` and sets three matching
        # `input_formats` (`apps/core/forms/_common.py:31-36`). It does that AFTER building the
        # fields from `Meta`, so a `Meta.widgets` entry for either field would be overwritten and
        # discarded — a line a reader would trust and that does nothing. Hence the widget is not
        # restated: the base's `format` is what renders the bound value, and without a format
        # matching the input type a `datetime-local` box renders EMPTY on edit, which is the bug this
        # paragraph exists to stop anybody reintroducing (4.8's `ProductionTimeLogForm:25-28` sets
        # the type without the format and has exactly that symptom).
        #
        # What the base omits is the ISO spelling WITH seconds, and browsers do submit
        # `2026-08-07T09:15:00` from the very picker it renders. Unaccepted, that is "Enter a valid
        # date/time" on a value the user never typed, on the two fields the whole row is built from.
        # `format` decides RENDERING and stays the base's; `input_formats` decides PARSING, and
        # accepting one more spelling of the same instant costs nothing.
        for name in ("started_at", "ended_at"):
            if name in self.fields:
                self.fields[name].input_formats = list(_DATETIME_INPUT_FORMATS)

        # --- the three task pointers ------------------------------------------------------------
        # `select_related` on the two whose `__str__` walks a second FK — `PutawayTask` prints
        # `item.sku` and `to_location.code`, `CycleCountTask` prints `location.code`, so without it
        # each rendered <option> costs one or two extra queries. `PickTask.__str__` is
        # `number · get_strategy_display()` and walks nothing, so it is deliberately left plain:
        # a `select_related` nobody needs is a join nobody needed either. (Checked against the three
        # models, not assumed — the `MaintenanceWorkOrderPartForm.lot_serial` finding.)
        _scope_open_tasks(self, "pick_task", PickTask.objects.all(), _OPEN_PICK_STATUSES)
        _scope_open_tasks(self, "putaway_task",
                          PutawayTask.objects.select_related("item", "to_location"),
                          PutawayTask.OPEN_STATUSES)
        _scope_open_tasks(self, "cycle_count_task",
                          CycleCountTask.objects.select_related("location"),
                          _OPEN_COUNT_STATUSES)

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        The narrowed dropdowns above are UX. This is the check a crafted POST has to get past, and
        it is repeated at the FORM boundary rather than left to the model's identical loop because
        it does not depend on the instance's tenant having been stamped first, and because it keys
        its error on a field the form actually carries — which is what makes it renderable instead
        of a ``ValueError`` out of ``add_error``.

        ``LaborActivity.TENANT_SCOPED_FKS`` is passed WHOLE rather than trimmed to the three task
        pointers, so the two boundaries read one table. Its other two entries, ``session`` and
        ``standard``, are not form fields, so ``cleaned.get()`` returns ``None`` for both and the
        loop skips them — and if a later pass ever does put one on this form, it is covered the
        moment it appears rather than the moment somebody remembers to widen a hand-typed tuple.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, LaborActivity.TENANT_SCOPED_FKS)
        return cleaned
