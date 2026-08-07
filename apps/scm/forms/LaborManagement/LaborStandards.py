"""SCM 4.14 Labor Management — the ``LaborStandard`` form (the engineered standard, [LST-]).

**``status`` is ABSENT from ``Meta.fields``, and the absence IS the mechanism.** The column is
``editable=False`` and moved only by the two verbs (activate / archive). Activating a standard is
not a cosmetic state change: :func:`apps.scm.models.select_standard` considers ``active`` rows and
nothing else, so flipping the dropdown would silently redefine what every FUTURE ``LaborActivity``
snapshots as earned minutes — and archiving would silently remove the row from the resolver, leaving
every activity in that scope unmeasured with no page saying so. Both belong on a button whose
consequence is printed beside it, not on a select somebody scrolls past while fixing a typo in the
name. A crafted ``status=active`` in a POST body cannot land here, and not because a view checks for
it: there is no path from form data to the column at all.

**An ACTIVE standard is nevertheless still EDITABLE, and that is deliberate** — see
``LaborStandard.EDITABLE_STATUSES``. Every ``LaborActivity`` snapshots the standard's determinants at
booking time, so a re-time changes what future work earns and cannot restate a single minute already
recorded. ``archived`` is the frozen one, for the reason that is easy to miss: the overlap guard in
``LaborStandard.clean()`` deliberately ignores archived rows, so editing an archived standard back
into a live date range would recreate exactly the ambiguity that guard exists to prevent. The view's
edit route is what enforces the ladder; this form has no opinion about it.

**The tenant stamp in :meth:`LaborStandardForm.__init__` is load-bearing, and more so here than on
most forms in this package.** ``crud_create`` assigns the tenant only AFTER ``is_valid()``
(``apps/core/crud.py:119-123``), so without the stamp the instance reaches ``LaborStandard.clean()``
with ``tenant_id`` None — and *three* separate guards in that method open with
``if self.tenant_id is not None``: the cross-tenant FK check, and, crucially, the OVERLAP REFUSAL
that is the only thing keeping ``select_standard()`` deterministic. Unstamped, the overlap check is
dead code on the create path, which is precisely the path that creates overlaps. (Not
``TenantUniqueMixin``: ``LaborStandard``'s only ``unique_together`` is ``(tenant, number)`` and
``number`` is auto-assigned in ``TenantNumbered.save()`` and off the form, so the mixin's
``validate_unique`` half would have nothing to check. Borrowing the mixin for its constructor alone
would misname the intent — the ``KpiTargetForm`` reading of the same situation.)

**Nothing derived has a field, because nothing derived has a column.** ``minutes_for()``,
``cost_for()`` and ``is_effective_on()`` are recomputed on read from the four determinants below, so
there is no stored figure for a form to disagree with — the whole earned-minutes definition lives in
one method and this screen only feeds it.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

from apps.scm.models import ItemCategory, LaborStandard, Location


# -------------------------------------------------------------------------------------------------
# Shared scoping helper for the 4.14 form modules.
#
# This is 4.13's `AssetManagement/Assets.py::_scope_to_tenant`, verbatim, living in THIS sub-package's
# root entity file for the same reason it lives in that one: `LaborStandards.py` is what the other
# three 4.14 form modules already point at (`LaborActivity.standard` and `LaborPlanLine.standard`
# both FK to `LaborStandard`), so importing from here adds no dependency edge that did not exist, and
# the alternative was the same six lines copied four times.
#
# It is NOT imported from 4.13's `Assets.py`: that would make the labor forms depend on the asset
# register for a rule that has nothing to do with assets. The day a THIRD sub-module wants it, it
# moves to `apps/scm/forms/_common.py` beside `_reject_foreign` (Backend Package Structure rule 5) —
# not before.
#
# It is also NOT `apps/scm/views/_helpers.py::_location_qs`, which produces the identical queryset:
# that helper is in the VIEWS layer, and the dependency in this codebase runs views -> forms
# (`views/_helpers.py:11` imports `_supplier_parties` from `forms/_common.py`). Reaching back the
# other way would invert it and drag the whole views toolkit into form import time for two lines of
# `.filter(tenant=...)`.
# -------------------------------------------------------------------------------------------------
def _scope_to_tenant(form, name, queryset):
    """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant.

    ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but only
    ``if tenant is not None``; a tenant-less caller (the superuser, ``request.tenant`` None) falls
    through to the unscoped default manager and the select would list every workspace's rows. The
    CRUD helpers never render these forms that way, but re-filtering from the model rather than
    chaining off the base's result makes the scoping true by construction instead of true by the
    caller behaving.
    """
    if name in form.fields:
        form.fields[name].queryset = (
            queryset.filter(tenant=form.tenant) if form.tenant is not None else queryset.none()
        )


class LaborStandardForm(TenantModelForm):
    """How long one unit of one activity should take, in one scope, over one date range."""

    class Meta:
        model = LaborStandard
        # A WHITELIST, never `Meta.exclude` — a blacklist means the next column added to
        # `LaborStandard` joins this form silently, and on a model whose numbers feed every
        # performance figure in the sub-module that is not a risk worth carrying. A whitelist fails
        # CLOSED (a new column is simply not on the form until somebody puts it there); an exclude
        # list fails OPEN.
        #
        # Deliberately ABSENT, and why:
        #   `status`      — verb-controlled and `editable=False`. See the module docstring; this is
        #                   the whole point of the file.
        #   `tenant`      — stamped by `crud_create`, and in `__init__` below so `clean()` can read it.
        #   `number`      — auto-assigned in `TenantNumbered.save()`.
        #   `created_at` / `updated_at` — automatic.
        # Nothing else is missing: everything reliability-, time- or cost-shaped on this model is
        # DERIVED (`minutes_for` / `cost_for` / `is_effective_on`) and has no column at all.
        fields = [
            # identity — what this standard measures and where the number came from. `source` is
            # user-owned here (contrast `LaborSession.source`, which is provenance a verb stamps):
            # "engineered vs benchmark library" is a claim the person WRITING the standard makes,
            # and a supervisor arguing with a number is entitled to see which it was.
            "name", "activity", "basis", "source",
            # the three determinants + the allowance. Each is capped by a model validator rather
            # than clamped: `minutes_for()` multiplies `minutes_per_unit` by a quantity, so an
            # absurd determinant does not stay local — it lands in earned minutes, in `cost_for()`
            # and in the required-headcount arithmetic of every plan built on this activity.
            "minutes_per_unit", "setup_minutes", "travel_minutes", "allowance_pct",
            # CHARGE-OUT per hour, never a person's wage. `hrm` owns compensation and `apps/scm`
            # carries no pointer into it anywhere — the payroll hand-off is a CSV, not an FK.
            "labour_rate",
            # effectivity. Re-timing an activity means a NEW standard starting today, not an edit;
            # that is what keeps last month's numbers reproducible.
            "effective_from", "effective_to",
            # scope. Both blank = the network-wide default — see `__init__`.
            "location", "item_category",
            "notes",
        ]
        # No entry for `effective_from` / `effective_to` here, and that is not an oversight:
        # `TenantModelForm.__init__` REPLACES the widget of every `forms.DateField` outright with
        # `DateInput(attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d")` and sets the
        # matching `input_formats` (`apps/core/forms/_common.py:37-41`), which is what makes a stored
        # date round-trip into the native picker on the edit page. It runs AFTER `ModelForm` has
        # built the fields from this dict, so anything declared here for a date field would be
        # silently overwritten — dead code that reads like the mechanism.
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. Without it `LaborStandard.clean()` runs with `tenant_id` None and three guards
        # — including the overlap refusal that keeps `select_standard()` deterministic — skip
        # themselves on the create path. See the module docstring for the full argument.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the two scope pointers -----------------------------------------------------------------
        # Both targets carry their own `tenant` column, so the base already scoped them; re-filtering
        # from the model makes it true by construction rather than true by the caller having passed a
        # tenant. Neither `__str__` walks a second FK (`Location` is "code · name" off its own
        # columns, `ItemCategory` is a plain name) — checked, not assumed, so no `select_related` is
        # owed on either dropdown and neither fires a query per rendered <option>.
        #
        # Deliberately NOT narrowed to active/live rows either. A standard is legitimately measured
        # for a zone that has since been deactivated or a category that has been discontinued, and
        # 4.14 reads HISTORY as much as it writes plans — the subject being dormant today is often
        # exactly why somebody is looking at the row. Leaving both blank is the network-wide default
        # and is a first-class answer, which is why the model has them `null=True, blank=True`.
        _scope_to_tenant(self, "location", Location.objects.all())
        _scope_to_tenant(self, "item_category", ItemCategory.objects.all())

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        ``LaborStandard.TENANT_SCOPED_FKS`` is the one table both boundaries read, so adding a
        pointer to the model means adding it there, not remembering to name it in a third place. The
        model's own ``clean()`` carries the same guard and is the one that holds at the database
        boundary; this repeats it at the FORM boundary because a narrowed ``<select>`` is a UI
        convenience and has never held against a crafted POST — every form in this package is
        reachable by any logged-in member of any workspace.

        Everything else this model refuses — the reversed date range, the zero standard, the
        per-task/per-unit basis pairing and the overlap refusal — stays in ``LaborStandard.clean()``,
        which the stamp above is what makes run. One implementation each; a second copy of the
        overlap rule here would be a second definition of "which standard applies".
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, LaborStandard.TENANT_SCOPED_FKS)
        return cleaned
