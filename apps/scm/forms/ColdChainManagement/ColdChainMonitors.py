"""SCM 4.15 Cold Chain Management — the ``ColdChainMonitor`` deployment form.

**What a human types here is the DEPLOYMENT**: which device, watching which one thing, held to which
band, logged how often, calibrated when. What a human never types is anything the sub-module
*derives* — in range, in the warning band, still reporting, calibration due, the open episode, the
open triage count and the setpoint gap are all recomputed on read, so there is no column for a form
to disagree with (``ColdChainMonitors.py:393-589``).

**``status`` IS on this form, and that is the design rather than an oversight.**
``ColdChainMonitor.status`` has exactly one writer and it is the user: no detector pass touches it
(the ``Asset.status`` ruling — one writer per column, no drift). It is the DELIBERATE opposite of
``TemperatureExcursion.status``, which is ``editable=False`` and absent from its form precisely
because the four triage verbs own it. **Do not "fix" either one to match the other.**

**The three subject FKs are all offered and ``clean()`` enforces exactly one.** They cannot be
collapsed into a single field: they are three typed pointers, never a ``GenericForeignKey``
(``SupplyChainAlerts.py:109-114`` — *"a bare int carries neither a tenant nor a type"*), and the
exactly-one rule is a model invariant that also has to hold against a management command and a
shell. The form offers them; ``ColdChainMonitor.clean()`` is the guard.

**The ``storage_condition`` pre-fill lives HERE and nowhere else.** ``STORAGE_CONDITION_RANGES`` is
documentation of the industry bands, not a policy the model enforces: :meth:`ColdChainMonitorForm.
__init__` copies it into the *initial* limits on an **unbound, unsaved** form only. It never
overwrites a value somebody typed and it never touches a saved row — a model that recomputed its own
limits would have two writers, and the excursion record snapshots whichever one happened to win.

**No ``TenantUniqueMixin``, and that is checked rather than assumed.** The model's only
``unique_together`` is ``("tenant", "number")``, ``number`` is auto-assigned in
``TenantNumbered.save()`` and is off this form, so the mixin's ``validate_unique`` half would have
nothing to check. Its *other* half — stamping ``instance.tenant`` before validation — is load-bearing
here and is done explicitly in ``__init__``; see there. (The one-active-monitor-per-serial rule is
``clean()``'s, not a constraint: MariaDB has no partial indexes and stores a blank ``CharField`` as
``""`` rather than NULL, so a ``(tenant, device_serial)`` constraint would permit exactly one
untagged monitor per workspace and 500 on the second.)

**The two shared helpers below live in this module** because ``ColdChainMonitors.py`` is this
sub-package's root entity — both other 4.15 form modules already point at ``ColdChainMonitor``, so
importing from here adds no dependency edge that did not already exist. That is the 4.13
``AssetManagement/Assets.py`` / 4.14 ``LaborManagement/LaborStandards.py`` precedent exactly. Move
either to ``apps/scm/forms/_common.py`` the day a second SUB-MODULE wants it (Backend Package
Structure rule 5), not before.
"""
from django.core.exceptions import NON_FIELD_ERRORS

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

from apps.scm.models import (
    Asset,
    ColdChainMonitor,
    Location,
    STORAGE_CONDITION_RANGES,
    Shipment,
)


# -------------------------------------------------------------------------------------------------
# Shared helpers for the 4.15 form modules. See the module docstring for why they live here.
# -------------------------------------------------------------------------------------------------

def _scope_to_tenant(form, name, queryset):
    """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant.

    ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but only
    ``if tenant is not None``; a tenant-less caller falls through to the unscoped default manager.
    The CRUD helpers never render these forms that way, but re-filtering from the model rather than
    chaining off the base's result makes the scoping true by CONSTRUCTION instead of true by the
    caller behaving. (4.13's ``AssetManagement/Assets.py`` idiom, verbatim.)
    """
    if name in form.fields:
        form.fields[name].queryset = (
            queryset.filter(tenant=form.tenant) if form.tenant is not None else queryset.none()
        )


class _ModelErrorSafe:
    """Re-key a MODEL error onto a field this form actually has, or onto the form itself.

    **Why this exists.** ``BaseModelForm._post_clean`` runs ``instance.full_clean()`` and hands every
    resulting error straight to ``Form.add_error``, which **raises ``ValueError`` for a key that is
    not a form field** — a 500 instead of a rendered message. 4.13's ``MeterReadingForm`` docstring
    records the same trap from the other side (*"a model error keyed on a column the FORM does not
    have raises ``ValueError`` out of ``Form.add_error``"*), and its answer was to keep the field on
    the form. That answer is not available to two of 4.15's forms:

    * ``TemperatureExcursionForm`` is a **triage-only whitelist** — every measured column is
      ``editable=False`` and must stay off it — while ``TemperatureExcursion.clean()`` legitimately
      keys errors on ``monitor``, ``started_at``, ``ended_at`` and ``limit_max``;
    * ``TemperatureReadingForm`` takes its ``monitor`` from the URL, while
      ``TemperatureReading.clean()`` keys its cross-tenant guard on that same name.

    Every one of those legs is *structurally* unreachable from the form path today (the detector
    cannot write an episode that ends before it starts, and a route-supplied monitor is already
    tenant-verified). "Structurally unreachable" is exactly the argument that turns into a 500 two
    sub-modules later, and the cost of being wrong is a crash on an audit record. So the error is
    RENDERED as a form-level message instead of being lost or raised.

    The remap is applied to the whole ``error_dict`` rather than only to the ``field`` argument
    because ``Form.add_error`` does not recurse: it iterates the dict itself and raises on the first
    unknown key. Keys that DO name form fields are untouched, so an ordinary field error still lands
    on its own field.
    """

    def add_error(self, field, error):
        if hasattr(error, "error_dict"):
            merged = {}
            for name, errors in error.error_dict.items():
                key = name if name in self.fields else NON_FIELD_ERRORS
                merged.setdefault(key, []).extend(errors)
            super().add_error(None, ValidationError(merged))
            return
        if field is not None and field not in self.fields:
            field = None
        super().add_error(field, error)


class ColdChainMonitorForm(TenantModelForm):
    """One monitoring point — this device, watching this thing, against these limits."""

    class Meta:
        model = ColdChainMonitor
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added later;
        # an exclude list fails open, and the column it would silently admit here is the next
        # detector-written measurement somebody adds.
        #
        # This is the model's FULL editable set, in declaration order. Deliberately ABSENT, and why:
        # `tenant` (stamped by `crud_create`, and in __init__ below so `clean()` can read it) and
        # `number` (auto-assigned in `TenantNumbered.save()` — nobody types a document number).
        # `created_at` / `updated_at` are automatic. EVERYTHING else IS here, `status` included —
        # see the module docstring.
        fields = ["name", "device_serial", "device_type",
                  "location", "asset", "shipment",
                  "storage_condition", "min_temperature", "max_temperature", "warning_margin_c",
                  "humidity_min", "humidity_max", "setpoint_temperature",
                  "excursion_grace_minutes", "logging_interval_minutes",
                  "calibrated_on", "calibration_due_on", "calibration_reference",
                  "status", "deployed_on", "retired_on", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP, and on this model it is the difference between a guard and a comment.
        # `crud_create` assigns the tenant only AFTER `is_valid()` (`apps/core/crud.py:120-123`), so
        # without this an unsaved monitor reaches `ColdChainMonitor.clean()` with `tenant_id` None —
        # and THREE of its nine rules are gated on `tenant_id is not None`: the cross-tenant FK
        # guard, the subject-freeze check and the one-active-monitor-per-serial rule. On the create
        # path all three would be dead code, which is the exact path a crafted POST takes.
        #
        # Safe to stamp BEFORE validation here because every field `ColdChainMonitor.clean()` can key
        # an error on — the three subjects, both temperature limits, `humidity_max`,
        # `warning_margin_c`, `retired_on`, `calibration_due_on`, `device_serial` — is on this form.
        # A model error keyed on a column the form does not have raises `ValueError` out of
        # `add_error` (a 500 instead of a field error), which is why 4.13's `MeterReading` stamps its
        # party AFTER `is_valid()` instead. Checked here, not assumed — and it is also why this form
        # does not need `_ModelErrorSafe` while the other two 4.15 forms do.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- what this monitor watches: exactly one of the three -----------------------------------
        # All three carry their own tenant column so `TenantModelForm` already scoped them; re-
        # filtering from the model makes the scoping true by construction and points a tenant-less
        # caller at nothing instead of at the unscoped default manager.
        #
        # Deliberately NOT narrowed by `is_active` / `status` / `location_type`: a cold room is a
        # `Location` of any type the workspace models it as (`zone`, `bin`, even `warehouse` for a
        # whole cold store), a reefer being repaired is still the thing being monitored, and a
        # shipment mid-journey is precisely when a logger is riding on it. Narrowing any of them
        # would drop the stored choice out of the `<select>` on an edit and silently NULL the FK —
        # which on this model is not merely annoying: a monitor with no subject instantly violates
        # its own exactly-one rule and could never be saved again.
        _scope_to_tenant(self, "location", Location.objects.all())
        _scope_to_tenant(self, "asset", Asset.objects.all())
        _scope_to_tenant(self, "shipment", Shipment.objects.all())

        self._prefill_limits()

    def _prefill_limits(self):
        """Copy the storage class's industry band into the INITIAL limits — create page only.

        ``STORAGE_CONDITION_RANGES`` is documentation, not policy (see its docstring in
        ``apps/scm/models/_choices.py``): it exists so nobody has to look up "what is chilled?"
        before typing two numbers, and the numbers that actually decide whether something is in range
        stay the explicit per-monitor columns. Three conditions, all of them load-bearing:

        * **unbound only** — on a bound form the user has already answered, and overwriting a posted
          value with a suggestion is how a form silently rejects what somebody typed;
        * **unsaved only** — a stored monitor's limits are the record the excursions were judged
          against, and re-suggesting over them would restate history on an ordinary edit;
        * **blank only** — a caller that pre-seeded a limit through ``initial=`` keeps it.

        ``ambient`` maps to ``(None, None)`` — "no temperature control" has no band to pre-fill, and
        a ``None`` side is simply skipped, exactly as a one-sided band is legitimate everywhere else
        in 4.15.
        """
        if self.is_bound or self.instance.pk is not None:
            return
        condition = self.initial.get("storage_condition") or self.instance.storage_condition
        band = STORAGE_CONDITION_RANGES.get(condition)
        if not band:
            return
        for name, suggested in zip(("min_temperature", "max_temperature"), band):
            if suggested is None:
                continue
            if self.initial.get(name) in (None, ""):
                self.initial[name] = suggested

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        ``ColdChainMonitor.TENANT_SCOPED_FKS`` is ``("location", "asset", "shipment")`` — one tuple
        read by both boundaries, so a pointer added to the model later is covered here the moment it
        is named there. The model's own ``clean()`` carries the same guard and it is the one that
        holds at the database boundary; this repeats it at the FORM boundary because **a narrowed
        ``<select>`` has never held against a crafted POST** (L39 §2). Without it a monitor could be
        pointed at another workspace's cold room, and every compliance figure it produced would be a
        statement about somebody else's freezer.

        Everything else — the exactly-one-subject rule, the subject freeze, the band ordering, the
        active-monitor-needs-a-limit rule, the humidity band, the warning-margin width, both date
        orderings and the one-active-monitor-per-serial rule — stays in ``ColdChainMonitor.clean()``,
        once, where it also holds against a management command and a shell.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ColdChainMonitor.TENANT_SCOPED_FKS)
        return cleaned
