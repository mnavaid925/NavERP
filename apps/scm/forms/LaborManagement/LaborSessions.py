"""SCM 4.14 Labor Management — the ``LaborSession`` form. One worked shift, typed by a human.

**Seven fields, and everything a verb owns is absent.** ``status`` is moved only by the clock-out /
close / approve / reopen / cancel verbs, each of which validates the transition it is making; a
``status=approved`` in a crafted POST body cannot land here — not because a view screens for it, but
because there is no path from form data to the column at all. ``source`` / ``recorded_by`` /
``login`` / ``closed_at`` / ``approved_at`` / ``approved_by`` are the session's PROVENANCE and are
stamped by whichever code path actually files the record (L20/L22). That is the 4.13 ``MeterReading``
fix applied at the point of design: a ``source`` a member can choose is not a provenance — it would
let a hand-typed shift claim to have come from a badge reader that never saw the worker, on a record
whose minutes end up in a payroll export. ``number`` is auto-assigned in ``TenantNumbered.save()``
and ``tenant`` is stamped by ``crud_create`` (and, before that, in ``__init__`` below — see there for
why that ordering is load-bearing rather than tidy).

**``clock_in`` / ``clock_out`` ARE on the form, and they are the one deliberate exception to L22.**
They are not system stamps: they are the human-entered SUBJECT of the record — a supervisor filing
"Ravi worked 06:00 to 14:15 yesterday" after the fact is the ordinary case, and forcing the pair
through a verb would mean a mis-keyed punch could never be corrected. Contrast ``closed_at`` /
``approved_at`` one paragraph up, which record when the SYSTEM was told something and are exactly
what L22 is about. The widget work in ``__init__`` is what makes that exception safe; the L22
failure was never "a datetime on a form", it was a ``DateInput(type="date")`` silently truncating
the time off one.

**No status gate lives here.** ``LaborSession.EDITABLE_STATUSES`` is ``("open",)`` and the view is
what refuses to render or accept this form for a closed or approved shift, the same way 4.13 gates
its work-order edits. A form that re-decided that would be a second implementation of one rule, and
the two would drift the first time a status was added.

**Every clock rule stays in ``LaborSession.clean()``** — the clock ordering, the two-day length cap,
the ``work_date``-is-the-start-date pin, the year floor, the one-open-session-per-worker rule, the
overlap guard and the employee-role check. One implementation each, at the boundary that also holds
against a management command and a shell. This module's own ``clean()`` adds exactly one thing the
model cannot do as well: a field error keyed on a field the FORM has (see :func:`_reject_foreign`).
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _employee_parties, _reject_foreign
# The two scoping helpers come from DIFFERENT places, and the split is deliberate.
#
# `_scope_to_tenant` has a 4.14-local owner — `LaborStandards.py`, this sub-package's root entity
# module, which the other 4.14 form modules already point at. Taking it from there rather than from
# 4.13's `AssetManagement/Assets.py` keeps the labor forms from depending on the asset register for
# a rule that has nothing to do with assets; see the comment above its definition there.
#
# `_keep_current` has exactly ONE implementation anywhere in the app and it is 4.13's. Copying six
# lines would be cheap; copying the reasoning inside them is not, and the copy is precisely where
# the `Cannot combine a unique query with a non-unique query` fix would go missing — the failure
# fires only on the edit path with a stored party, so a test that never stores one would not see
# it. So it is imported until somebody moves it to `apps/scm/forms/_common.py` beside
# `_reject_foreign` (Backend Package Structure rule 5) — which is now due: `Assets.py` says it
# stays put "until a second sub-module wants it", and this line is that second sub-module.
from apps.scm.forms.AssetManagement.Assets import _keep_current
from apps.scm.forms.LaborManagement.LaborStandards import _scope_to_tenant

from apps.scm.models import LaborSession, Location


class LaborSessionForm(TenantModelForm):
    """One worker's shift at one facility — who, where, which day, and the two clock times."""

    class Meta:
        model = LaborSession
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added later;
        # an exclude list fails open, and the column it would silently admit here is the next
        # provenance stamp somebody adds.
        #
        # Deliberately ABSENT, and why: `status` (verb-driven, `editable=False` — see the module
        # docstring, this is the whole point); `source` / `recorded_by` / `login` / `closed_at` /
        # `approved_at` / `approved_by` (provenance, stamped by the filing verb, L20/L22); `tenant`
        # (stamped by `crud_create`, and in __init__ below so the model's guards can read it);
        # `number` (auto-assigned in `TenantNumbered.save()`); `created_at` / `updated_at`.
        # Every productivity figure — attended, booked, direct, indirect, gap, earned, performance,
        # utilisation, units/hour, accuracy — is DERIVED on read and has no column at all, so there
        # is nothing there for a form to keep off or disagree with.
        fields = ["worker", "location", "work_date", "shift_label",
                  "clock_in", "clock_out", "notes"]
        widgets = {
            # `clock_in` / `clock_out` are NOT declared here on purpose — see __init__.
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP, and on this model it is the difference between a guard and a comment.
        # `crud_create` assigns the tenant only AFTER `is_valid()`, so without this an unsaved
        # session reaches `LaborSession.clean()` with `tenant_id` None — and FOUR of its rules are
        # gated on `tenant_id is not None`: the cross-tenant FK guard, the one-open-session rule and
        # both legs of the overlap guard. On the create path they would all be dead code, which is
        # the exact path a crafted POST takes, and the overlap guard is the one stopping the same
        # minutes being billed twice in the payroll export. (Not `TenantUniqueMixin`: the only
        # `unique_together` is `(tenant, number)` and `number` is auto and off this form, so its
        # `validate_unique` half would have nothing to check.)
        #
        # Safe to stamp BEFORE validation here because every field `LaborSession.clean()` can key an
        # error on — worker, location, work_date, clock_in, clock_out — is on this form. A model
        # error keyed on a column the form does not have raises `ValueError` out of `add_error` (a
        # 500 instead of a field error); that is why 4.13's `MeterReading` stamps its party AFTER
        # `is_valid()` instead. Checked here, not assumed.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- where the shift was worked ---------------------------------------------------------
        # `Location` carries its own tenant column, so `TenantModelForm` already scoped it; re-
        # filtering from the model makes the scoping true by CONSTRUCTION rather than true by the
        # caller having passed a tenant, and points a tenant-less caller at nothing instead of at
        # the unscoped default manager. Deliberately not narrowed by `location_type` or `is_active`:
        # labour is booked in yards, staging lanes and quarantine areas as readily as in a pick
        # face, and a shift worked at a site being wound down is still a shift somebody is owed for.
        # `Location.__str__` is "code · name" off its own columns, so no `select_related` is owed on
        # this dropdown.
        _scope_to_tenant(self, "location", Location.objects.all())

        # --- whose shift it is --------------------------------------------------------------------
        # Narrowed by ROLE, not merely by tenant: `Party` is the spine's one-table-for-every-person
        # model, so an unnarrowed select offers customers and hauliers under a label that reads
        # "worker". `LaborSession.clean()` rule (g) is what REFUSES a non-employee — including one
        # arriving by crafted POST, which a narrowed `<select>` has never stopped.
        #
        # `_keep_current` re-admits the row's ALREADY-STORED worker on the edit path. Without it, a
        # party whose `employee` role was removed after the shift was filed drops out of the
        # `<select>`, and because `worker` is required and PROTECT the supervisor editing an
        # unrelated note gets "Select a valid choice" on a field they never touched, with no option
        # in the list that preserves the truth. With it, the stored worker stays selectable and the
        # refusal they see is rule (g)'s — which names the party and says to add the role back.
        # Both legs of the union are still tenant-scoped, so this cannot re-admit a stranger's
        # party; on a create form `worker_id` is None and the widening is skipped entirely.
        if "worker" in self.fields:
            self.fields["worker"].queryset = _keep_current(
                _employee_parties(self.tenant), self.tenant, self.instance.worker_id)

        # --- the two clock times ------------------------------------------------------------------
        # Set HERE and not in `Meta.widgets`, because `TenantModelForm.__init__` REPLACES the widget
        # of every `DateTimeField` after the Meta widgets have been applied — a Meta declaration for
        # these two is silently discarded, so assigning after `super()` is the only place it
        # survives. Three things have to travel together:
        #
        #   * `type="datetime-local"`, so the browser renders a date AND a time control. A plain
        #     `DateInput(type="date")` here would silently truncate the punch to midnight — that is
        #     the actual L22 failure, and on this model it would collapse every attended figure to
        #     0 or to a whole number of days;
        #   * `format="%Y-%m-%dT%H:%M"`, because a `datetime-local` control cannot parse Django's
        #     default `%Y-%m-%d %H:%M:%S` rendering and shows an EMPTY box for a stored value. The
        #     widget type without the format is a real latent bug, not a cosmetic one: the edit form
        #     for a filed shift renders blank, and saving it re-posts empty clock times.
        #     (4.8's `ProductionTimeLogForm` declares exactly the type-without-format pair in its
        #     `Meta.widgets`; it is only saved by the base class overwriting the whole widget.)
        #   * `class="form-input"`, which the base normally adds — replacing its widget means
        #     carrying the theme class ourselves or the field renders unstyled.
        #
        # `input_formats` is DECLARED rather than inherited, and it names the exact four shapes this
        # control can post — `%Y-%m-%dT%H:%M:%S` included, because a `datetime-local` whose step
        # admits seconds posts it and the base's list carries only the space-separated spelling of
        # that. Today none of the four is strictly load-bearing: `DateTimeField.to_python` runs
        # `parse_datetime` FIRST, which on Django 5.1 is `fromisoformat` and swallows every ISO
        # shape before `input_formats` is consulted at all. That fast path is the framework's
        # business and can narrow; the accepted set belongs written down next to the `format` that
        # renders into this control, because the two have to agree and a base-class list three call
        # levels away is where they drift apart. Minute precision stays FIRST so it is the shape
        # `format` round-trips against.
        for name in ("clock_in", "clock_out"):
            field = self.fields.get(name)
            if field is None:
                continue
            field.widget = forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-input"},
                format="%Y-%m-%dT%H:%M",
            )
            field.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S",
                                   "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        ``LaborSession.TENANT_SCOPED_FKS`` is ``("worker", "location")`` — one table read by both
        boundaries, so a pointer added to the model later is covered here the moment it is named
        there. The model's own ``clean()`` carries the same guard and is the one that holds at the
        database boundary; this repeats it at the FORM boundary because a narrowed dropdown is a UI
        convenience and has never held against a crafted POST. Without it a shift could be filed
        against another workspace's worker at another workspace's warehouse, and it would then be
        counted in that workspace's scorecard and paid out of its payroll export.

        Everything else — the clock ordering, the length cap, the ``work_date`` pin, the year floor,
        the one-open-session rule, the overlap guard and the employee-role check — stays in
        ``LaborSession.clean()``, once.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, LaborSession.TENANT_SCOPED_FKS)
        return cleaned
