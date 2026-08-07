"""SCM 4.14 Labor Management — the ``LaborPlan`` header form and its plan-line form.

**The asymmetry between these two forms IS the sub-module.** The header is where a human states the
staffing QUESTION — this site, these dates, this grain, this volume source, this productivity
assumption — and the line is where the machine states the ANSWER. So the header form is wide and the
line form has exactly two fields on it: ``planned_headcount``, the roster the planner intends, and a
note explaining it. Every other column on a line (``forecast_volume``, ``standard``,
``standard_minutes_snapshot``, ``required_minutes``, ``required_headcount``) is ``editable=False``
and written by the generate verb. Offering any of them would let a planner close the required-vs-
planned gap by editing the question rather than by rostering somebody, and the gap is the one number
these two pages exist to show.

**``status`` / ``generated_at`` / ``approved_by`` / ``approved_at`` are ABSENT from the header
whitelist, and that absence is the mechanism** (the 4.13 ``MaintenanceWorkOrderForm`` rule, verbatim).
All four are ``editable=False`` and moved only by the generate / approve / archive verbs. A crafted
``status=approved`` in a POST body cannot land — not because a view checks for it, but because there
is no path from form data to the column at all.

**The period contract, the horizon cap and the volume-source pairing are NOT repeated here.** They
live in :meth:`LaborPlan.clean` so the form, the seeder and any future revise action all inherit one
implementation (that method's own docstring says exactly this). What this form owes them is that
every field those rules key an error on — ``period_start``, ``period_end``, ``demand_forecast``,
``location`` — is present on the form: a model error keyed on a column the form does not have raises
``ValueError`` out of ``add_error``, i.e. a 500 instead of a field error.

**Neither form mixes in ``TenantUniqueMixin``, for two different reasons.** ``LaborPlan``'s only
``unique_together`` is ``(tenant, number)`` and ``number`` is auto-assigned in
``TenantNumbered.save()`` and off the form, so the mixin's ``validate_unique`` half would have
nothing to check — but the header still needs the mixin's OTHER half (the tenant stamp), which is
therefore done by hand in :meth:`LaborPlanForm.__init__`. ``LaborPlanLine`` has **no tenant column at
all**, so ``self.instance.tenant = …`` would silently set a stray Python attribute on a model that has
nowhere to put it; its tenant is ``plan.tenant`` and its guard is anchored there.

**Date widgets are not declared in either ``Meta``.** ``TenantModelForm.__init__`` REPLACES the
widget of every ``DateField`` with ``<input type="date">`` at ``format="%Y-%m-%d"`` and sets the
matching ``input_formats``, so a bound value round-trips on edit — and a widget declared here would
be built and then thrown away, which is worse than absent because it reads as if it were in force.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign
# 4.14's shared scoping helper, from THIS sub-package's root entity file — not from 4.13's
# `AssetManagement/Assets.py` (which would make the labor forms depend on the asset register for a
# rule that has nothing to do with assets) and not from `views/_helpers.py::_location_qs`, which
# produces the identical queryset but sits in the VIEWS layer: the dependency in this codebase runs
# views -> forms (`views/_helpers.py:11`) and reaching back the other way would invert it. See the
# block comment above the helper for the whole argument.
from apps.scm.forms.LaborManagement.LaborStandards import _scope_to_tenant

from apps.scm.models import DemandForecast, LaborPlan, LaborPlanLine, Location


class LaborPlanForm(TenantModelForm):
    """The staffing question: which site, which dates, which grain, and where the volume comes from."""

    class Meta:
        model = LaborPlan
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added to the
        # model later — the new field simply is not on the form until somebody names it — where an
        # exclude list fails open and would quietly enrol it.
        #
        # Deliberately ABSENT, and why: `tenant` (stamped by `crud_create` after is_valid(), and in
        # __init__ below so clean() can read it), `number` (auto-assigned in `TenantNumbered.save()`),
        # `status` / `generated_at` / `approved_by` / `approved_at` (editable=False, verb-owned — see
        # the module docstring, this is the whole point), `created_at` / `updated_at` (automatic).
        fields = [
            # what the plan is
            "name", "location", "period_start", "period_end", "bucket",
            # where the volume comes from. `volume_source` and `demand_forecast` are paired BOTH ways
            # in `LaborPlan.clean()` — a forecast-driven plan without a forecast generates an empty
            # grid that reads as a site with no work, and a forecast hung off a stock-moves plan is a
            # pointer nothing consults, which is worse: the header would name a forecast the numbers
            # on the page were never derived from.
            "volume_source", "method", "history_days", "demand_forecast",
            # how volume becomes people. Both are DIVISORS in `headcount_for()` /
            # `required_minutes_for()`, and both carry model validators with a non-zero MINIMUM for
            # that reason — a zero here would be a ZeroDivisionError inside the generate verb (a 500)
            # for every line in the grid, not an aggressive target.
            "hours_per_shift", "productivity_pct",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. `crud_create` assigns the tenant only AFTER `is_valid()`
        # (`apps/core/crud.py:121-122`), so without this an unsaved plan reaches `LaborPlan.clean()`
        # with `tenant_id` None — the exact case its cross-tenant FK guard skips — and that guard
        # would be dead code on the create path, which is the one path a crafted POST exercises.
        # Only when unset: an edit already carries its tenant and must never be repointed.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the site being staffed ---------------------------------------------------------------
        # Not narrowed by `location_type`: a `LaborStandard` is scoped to a "warehouse or zone", so a
        # zone-level plan is a first-class thing and filtering to warehouses would make it
        # unwritable. Not narrowed by `is_active` either, and that one is a live bug rather than a
        # preference — a plan written for a site that is later deactivated would lose its location
        # from the select, render with nothing chosen, and silently NULL the FK the next time
        # somebody edited the plan's notes. `Location.__str__` is "code · name" off its own columns,
        # so no `select_related` is owed on this dropdown (checked, not assumed).
        _scope_to_tenant(self, "location", Location.objects.all())

        # --- 4.7's forecast, consumed and not re-derived -------------------------------------------
        # `select_related("item")` is NOT decoration here: `DemandForecast.__str__` dereferences
        # `self.item.sku`, which is one query per rendered <option> without it — a workspace with a
        # few hundred forecasts turns opening this form into a few hundred queries (the
        # `MaintenanceWorkOrderPartForm.lot_serial` finding).
        #
        # Deliberately NOT narrowed by forecast `status`. A plan is legitimately built against a
        # draft or in-review forecast while a peak is being argued about, and hiding those would hide
        # exactly the rows a planner is working from; `LaborPlan.clean()` is what refuses a forecast
        # belonging to another workspace, which a narrowed dropdown never could.
        _scope_to_tenant(self, "demand_forecast", DemandForecast.objects.select_related("item"))

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        Driven off the model's own ``TENANT_SCOPED_FKS`` (``location``, ``demand_forecast``) so the
        two boundaries read ONE table: a pointer added to that tuple later is covered here the moment
        it is named there, with no second list to remember. ``LaborPlan.clean()`` carries the same
        guard and is the one that holds at the database boundary; this repeats it at the FORM
        boundary because a narrowed ``<select>`` is UX and has never held against a crafted POST.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, LaborPlan.TENANT_SCOPED_FKS)
        return cleaned


class LaborPlanLineForm(TenantModelForm):
    """One generated bucket of the grid. **Two fields: what you will roster, and why.**

    Edit-only by construction — lines are created by ``laborplan_generate``'s ``bulk_create`` and by
    nothing else, so there is no create path through this form. Two consequences a reader should not
    have to rediscover:

    * ``unique_together ("plan", "period_start", "activity")`` is never at risk from this form.
      Django skips a ``unique_together`` whose fields are excluded from validation, and all three of
      those are off the whitelist — but all three are also unchangeable here, so unlike
      ``AssetSparePartForm`` this form owes no ``validate_unique`` repair. Adding any of the three to
      the whitelist later would silently re-open that hole and would need the repair with it.
    * ``crud_update`` **cannot** be used to render it. That helper resolves its object with
      ``get_object_or_404(model, pk=pk, tenant=request.tenant)`` (``apps/core/crud.py:138``) and
      ``LaborPlanLine`` has no ``tenant`` column, so the lookup raises ``FieldError`` — a 500. The
      edit view resolves the line itself with ``plan__tenant=request.tenant`` and hand-rolls the save
      (and therefore owes its own ``write_audit_log`` call).

    Whether the parent plan is still *editable* (``LaborPlan.EDITABLE_STATUSES``) is the VIEW's
    refusal, not this form's: an illegal move must answer with a message and a redirect, which a
    field error cannot do. One implementation each.
    """

    class Meta:
        model = LaborPlanLine
        # A WHITELIST, and the shortest one in the sub-module. Everything else on this row is
        # generated and `editable=False` — see the module docstring for why `required_headcount` in
        # particular must never appear here.
        fields = ["planned_headcount", "notes"]

    def clean(self):
        """The tenant check, anchored on the PARENT — this row has no tenant column of its own.

        ``LaborPlanLine`` is a pure child reached through ``plan__tenant``, so there is nothing on the
        instance to compare against ``self.tenant`` and assuming otherwise would be an
        ``AttributeError`` at best and a check that silently passes at worst. The parent is resolved
        with ``tenant=request.tenant`` by the edit view, so "this form's tenant" and "the plan's
        tenant" are the same set by construction — which is precisely why a DISAGREEMENT between them
        means the form was constructed by something that skipped that resolution, and the only safe
        answer to that is a refusal. An unparented instance refuses for the same reason: an
        unparented line form is itself a refusal, not a pass (the ``AssetSparePartForm.clean``
        posture).

        ``getattr(self.instance, "plan", None)`` is defaulted because
        ``RelatedObjectDoesNotExist`` subclasses ``AttributeError`` — a line whose parent row went
        away degrades to a refusal here instead of 500-ing inside validation.
        """
        cleaned = super().clean()

        plan = getattr(self.instance, "plan", None) if self.instance.plan_id else None
        plan_tenant_id = getattr(plan, "tenant_id", None)
        form_tenant_id = self.tenant.pk if self.tenant is not None else None
        if plan_tenant_id is None or plan_tenant_id != form_tenant_id:
            raise ValidationError("That plan line belongs to another workspace.")

        # A no-op today — `standard` is `editable=False` and off the whitelist, so `cleaned` never
        # carries it — and kept anyway because it is driven off `LaborPlanLine.TENANT_SCOPED_FKS`:
        # the day a scoped pointer joins both that tuple and the whitelist, it is re-checked here
        # without anybody having to remember that this was the file to come back to.
        _reject_foreign(self, cleaned, LaborPlanLine.TENANT_SCOPED_FKS)
        return cleaned
