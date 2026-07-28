"""SCM 4.9 Quality Management — InspectionPlan form + characteristic formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _supplier_parties
from apps.scm.models import InspectionCharacteristic, InspectionPlan


class InspectionPlanForm(TenantUniqueMixin, TenantModelForm):
    """The criteria master's header.

    `TenantUniqueMixin` is MANDATORY here: the model's ``("tenant", "code", "version")``
    unique_together includes ``tenant``, which is never a form field — without the mixin Django
    skips the whole constraint and a duplicate code sails through ``is_valid()`` and then raises an
    uncaught IntegrityError (a 500) on save.

    `item` and `item_category` carry their own tenant so the base class scopes them; `supplier`
    points at ``core.Party``, whose tenant scoping is not enough — it must also be narrowed to
    parties we actually buy from.
    """

    class Meta:
        model = InspectionPlan
        fields = ["code", "name", "plan_type", "item", "item_category", "supplier",
                  "sampling_method", "sample_percentage", "sample_size", "aql_accept_number",
                  "aql_reject_number", "frequency", "frequency_value", "version",
                  "effective_from", "is_active", "notes"]
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "supplier" in self.fields:
            self.fields["supplier"].queryset = _supplier_parties(self.tenant)


class InspectionCharacteristicForm(TenantModelForm):
    """One check on the plan. ``uom`` carries its own tenant, so the base class scopes it."""

    class Meta:
        model = InspectionCharacteristic
        fields = ["sequence", "name", "characteristic_type", "uom", "target_value",
                  "lower_limit", "upper_limit", "expected_text", "test_method", "is_critical",
                  "is_mandatory", "include_on_coa"]


class BaseInspectionCharacteristicFormSet(forms.BaseInlineFormSet):
    """Guards the plan as a whole — including two rules that READ THE PARENT.

    The parent-reading half only works because the view assigns ``formset.instance =
    form.instance`` before calling ``is_valid()`` (see ``_inspectionplan_form``). On create the
    formset's instance is an empty ``InspectionPlan()`` whose ``plan_type`` is the field default,
    so without that assignment the audit-checklist rule below silently no-ops on exactly the path
    it exists for — the bug 4.8 shipped in ``BaseBOMLineFormSet``.
    """

    def clean(self):
        super().clean()
        rows = [form for form in self.forms
                if getattr(form, "cleaned_data", None) and not form.cleaned_data.get("DELETE")]
        if not rows:
            raise ValidationError("A plan needs at least one characteristic — an empty plan can "
                                  "never produce an inspection result.")
        sequences = [form.cleaned_data.get("sequence") for form in rows]
        if len(set(sequences)) != len(sequences):
            raise ValidationError("Two characteristics share a sequence number — the order they "
                                  "are inspected in would be arbitrary.")
        plan_type = getattr(self.instance, "plan_type", None)
        if plan_type != "audit_checklist":
            return
        for form in rows:
            kind = form.cleaned_data.get("characteristic_type")
            if kind not in ("pass_fail", "visual"):
                form.add_error("characteristic_type",
                               "An audit checklist asks pass/fail or visual questions — there is "
                               "nothing to measure in a process audit.")

    def add_fields(self, form, index):
        """Build the uom option list ONCE for the whole formset.

        ``TenantModelForm`` re-assigns a fresh, uncached queryset per form, and
        ``ModelChoiceField.__deepcopy__`` does ``queryset.all()`` which discards any cache anyway —
        so every rendered row re-ran the identical SELECT. Assigning ``.choices`` short-circuits
        that; ``clean()``/``to_python()`` still go through ``self.queryset``, so POST validation and
        tenant scoping are untouched.
        """
        super().add_fields(form, index)
        if "uom" not in form.fields:
            return
        if not hasattr(self, "_uom_choices"):
            self._uom_choices = list(form.fields["uom"].choices)
        form.fields["uom"].choices = self._uom_choices


# max_num with validate_max: without it Django silently accepts up to absolute_max (2000) rows in
# ONE post and ignores the overflow. Every characteristic becomes an InspectionResult row on every
# inspection run from the plan, so the breadth is a real cost bound, not a tidiness one (the 4.8
# BOMLineFormSet lesson — bound breadth, not just depth).
InspectionCharacteristicFormSet = inlineformset_factory(
    InspectionPlan, InspectionCharacteristic, form=InspectionCharacteristicForm,
    formset=BaseInspectionCharacteristicFormSet, extra=1, can_delete=True, max_num=200,
    validate_max=True,
)
