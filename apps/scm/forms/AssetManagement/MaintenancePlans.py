"""SCM 4.13 Asset Management — the ``MaintenancePlan`` form and its job-plan task formset.

A plan is a *definition*: it never executes anything. Everything a planner authors here is an INPUT
— the trigger, the cadence, the call horizon, the schedule the plan currently stands at, and the
priority / work type / crew a generated job will be stamped with. Everything the board reads back
(``due_status``, ``days_until_due``, ``meter_gap``, ``is_due``) is a method that recomputes on every
read, so there is no derived column here for a form to disagree with.

**Two stamps are deliberately off the form and both record that something HAPPENED.**
``last_completed_on`` is written only by the work-order complete verb and ``last_generated_on`` only
by the generate action; both are ``editable=False`` on the model (L22). A planner who could type
``last_completed_on`` could type a service that was never performed, and the PM-compliance figure
would believe it. ``next_due_on`` / ``next_due_reading`` ARE on the form and that is the opposite
case — they are the schedule itself, an input a planner may legitimately shift, and
:meth:`MaintenancePlan.advance` is what rolls them forward afterwards.

**The trigger contract is NOT re-implemented here.** "A calendar plan needs an interval", "a meter
plan needs a cadence AND an asset with a meter defined", "a condition plan needs both halves of its
threshold" all live in ``MaintenancePlan.clean()``, which this form's ``_post_clean`` invokes. The
stamp in :meth:`MaintenancePlanForm.__init__` is what makes that method run at all on the create
path: ``crud_create`` assigns the tenant only AFTER ``is_valid()`` (``apps/core/crud.py:120-123``),
so an unsaved plan otherwise reaches ``clean()`` with ``tenant_id`` None — the exact case its
cross-tenant FK guard skips.

**Not ``TenantUniqueMixin``.** This model's only ``unique_together`` is ``("tenant", "number")`` and
``number`` is auto-assigned and off the form, so the mixin's ``validate_unique`` half would have
nothing to check. Borrowing it for its constructor alone would misname the intent — the
``ComplianceRequirementForm`` / ``KpiTargetForm`` reading of the same situation — so the stamp is
written out instead.

**``MaintenancePlanTaskFormSet`` is the job plan** — Maximo's job plan, SAP's task list, MaintainX's
procedure. ``extra=3`` because a plan with no steps is the ordinary starting point and a formset that
offers no blank row can never gain its first one. The child carries no ``tenant`` column (it is
reached through ``plan__tenant``) and no FK dropdowns at all, so there is nothing to scope on it; it
still subclasses ``TenantModelForm`` for the shared widget classes the templates style against,
which means the view MUST construct the formset with
``form_kwargs={"tenant": request.tenant}`` — the shipped ``StockAdjustmentLineFormSet`` /
``WorkOrderComponentFormSet`` contract.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _employee_parties
from apps.scm.forms.AssetManagement.Assets import (_keep_current, _reject_foreign,
                                                   _scope_to_tenant)

from apps.scm.models import Asset, Location, MaintenancePlan, MaintenancePlanTask


class MaintenancePlanForm(TenantModelForm):
    """One recurring obligation on one asset — its trigger, its cadence and what it hands the job."""

    class Meta:
        model = MaintenancePlan
        # A WHITELIST, never `Meta.exclude`. Deliberately ABSENT: `tenant` (stamped by `crud_create`,
        # and in __init__ below so clean() can read it), `number` (auto-assigned in
        # `TenantNumbered.save()`), `last_completed_on` / `last_generated_on` (system stamps, L22 —
        # see the module docstring), `created_at` / `updated_at` (automatic). Everything else the
        # model declares as editable is here, in declaration order.
        fields = [
            # what the plan IS
            "name", "asset", "instructions", "is_active",
            # how it comes due — the four triggers and their inputs. `MaintenancePlan.clean()`
            # refuses a trigger whose own arithmetic has nothing to read.
            "trigger_type", "schedule_basis", "interval_days", "lead_time_days", "meter_interval",
            # where the schedule currently stands. These are the SCHEDULE, not a derivation.
            "next_due_on", "next_due_reading", "condition_operator", "condition_threshold",
            # what a generated job inherits — one shared vocabulary with MaintenanceWorkOrder, so
            # the generate action cannot stamp a value the target column will not accept.
            "priority", "work_type", "estimated_hours", "assigned_to", "parts_location",
        ]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. See the module docstring: without it `MaintenancePlan.clean()`'s cross-tenant
        # FK guard is skipped on create, which is the one path a crafted POST uses.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- what it maintains, and where the parts come from ---------------------------------------
        # Both carry their own tenant, so TenantModelForm already scoped them; re-filtering from the
        # model makes the scoping true by construction. `Asset.__str__` ("code · name") and
        # `Location.__str__` ("code · name") read their own columns, so no select_related is owed.
        #
        # `asset` is deliberately NOT narrowed to `is_active=True`: a plan is authored against a
        # machine that is `planned` (not yet commissioned) as often as against a running one, and a
        # standing instruction on a temporarily idle asset is still the instruction.
        _scope_to_tenant(self, "asset", Asset.objects.all())
        _scope_to_tenant(self, "parts_location", Location.objects.all())

        # --- the default crew -----------------------------------------------------------------------
        # Narrowed by ROLE, the WorkCenterForm.supervisor precedent — a "technician or crew" dropdown
        # listing the customer book is noise. `_keep_current` stops a party whose employee role was
        # removed from silently NULLing this FK on the next unrelated edit.
        if "assigned_to" in self.fields:
            self.fields["assigned_to"].queryset = _keep_current(
                _employee_parties(self.tenant), self.tenant, self.instance.assigned_to_id)

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        The trigger contract itself is NOT repeated here: ``MaintenancePlan.clean()`` owns it and
        runs from ``_post_clean``. A second copy would be the drift this module's model docstring
        spends a paragraph refusing.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, MaintenancePlan.TENANT_SCOPED_FKS)
        return cleaned


class MaintenancePlanTaskForm(TenantModelForm):
    """One step of the job plan. No FK dropdowns — the parent comes from the inline formset."""

    class Meta:
        model = MaintenancePlanTask
        # A WHITELIST. `plan` is absent because `inlineformset_factory` supplies it from the parent
        # instance — a parent pk in the POST body is how a line lands on somebody else's plan.
        fields = ["sequence", "description", "expected_result", "is_mandatory", "is_safety_step"]


#: ``extra=3`` matches the shipped line formsets (``StockAdjustmentLineFormSet``,
#: ``WorkOrderComponentFormSet``): with ``extra=0`` a step could never be hand-added, or re-added
#: after deletion, and a brand-new plan could never gain its first one.
MaintenancePlanTaskFormSet = inlineformset_factory(
    MaintenancePlan, MaintenancePlanTask, form=MaintenancePlanTaskForm, extra=3, can_delete=True,
)
