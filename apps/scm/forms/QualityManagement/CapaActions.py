"""SCM 4.9 Quality Management — CapaAction form, task formset and the verification payload."""
from datetime import date

from django.core.validators import MaxValueValidator, MinValueValidator

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _employee_parties, _supplier_parties
from apps.scm.models import CapaAction, CapaTask

_MIN_DATE = date(2000, 1, 1)
_MAX_DATE = date(2100, 12, 31)


class CapaActionForm(TenantUniqueMixin, TenantModelForm):
    """The CAPA header.

    EXCLUDES `number` (auto), `status`, `implemented_on`, and the whole verification block
    (`effectiveness_result` / `verified_by` / `verified_on` / `verification_notes` / `closed_on`) —
    the implement and verify actions own those.

    `effectiveness_due_date` is the one date in that block that IS editable, and this form is its
    only writer: ``capaaction_implement`` refuses while it is blank instead of filling it in, so
    there is never a second writer to disagree with.
    """

    class Meta:
        model = CapaAction
        fields = ["action_type", "title", "source", "nonconformance", "audit", "item", "supplier",
                  "problem_statement", "containment_action", "root_cause_method", "root_cause",
                  "action_plan", "owner", "priority", "due_date", "effectiveness_due_date",
                  "notes"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "effectiveness_due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "nonconformance" in self.fields:
            # NonConformance.__str__ is number + title — no FK walk — but the list page and the
            # detail both render the item alongside it, so pre-joining costs one join and saves a
            # query per option wherever that happens.
            self.fields["nonconformance"].queryset = (
                self.fields["nonconformance"].queryset.select_related("item"))
        if "supplier" in self.fields:
            self.fields["supplier"].queryset = _supplier_parties(self.tenant)
        if "owner" in self.fields:
            self.fields["owner"].queryset = _employee_parties(self.tenant)


class CapaTaskForm(TenantModelForm):
    """One step of the action plan.

    ``CapaTask`` is TENANT-LESS (reached through its CAPA), so ``TenantModelForm`` cannot scope
    ``owner`` by walking the child's tenant — it scopes by the TARGET's tenant, which is right, but
    "an employee" is a PartyRole question it knows nothing about. Narrowed by hand below.
    """

    class Meta:
        model = CapaTask
        fields = ["sequence", "description", "owner", "due_date", "completed_on", "status"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "completed_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "owner" in self.fields:
            self.fields["owner"].queryset = _employee_parties(self.tenant)


class BaseCapaTaskFormSet(forms.BaseInlineFormSet):
    """Guards the task list — including one rule that READS THE PARENT.

    "A task cannot be due after the CAPA it belongs to" only works because the view assigns
    ``formset.instance = form.instance`` before ``is_valid()``. On create the formset's instance is
    an empty ``CapaAction()`` whose ``due_date`` is None, so without that assignment this silently
    no-ops on exactly the path it exists for — the shipped 4.8 ``BaseBOMLineFormSet`` bug.
    """

    def clean(self):
        super().clean()
        rows = [form for form in self.forms
                if getattr(form, "cleaned_data", None) and not form.cleaned_data.get("DELETE")]
        sequences = [form.cleaned_data.get("sequence") for form in rows]
        if len(set(sequences)) != len(sequences):
            raise ValidationError("Two tasks share a sequence number — the order they run in "
                                  "would be arbitrary.")
        parent_due = getattr(self.instance, "due_date", None)
        if parent_due is None:
            return
        for form in rows:
            due = form.cleaned_data.get("due_date")
            if due and due > parent_due:
                form.add_error("due_date",
                               f"This task is due after the CAPA itself ({parent_due:%d %b %Y}) — "
                               "the plan could never be complete on time.")

    def add_fields(self, form, index):
        """Build the owner option list ONCE for the whole formset.

        ``TenantModelForm`` re-assigns a fresh, uncached queryset per form, and
        ``ModelChoiceField.__deepcopy__`` does ``queryset.all()`` which discards any cache anyway —
        so every rendered row re-ran the identical SELECT. Assigning ``.choices`` short-circuits
        that; ``clean()``/``to_python()`` still go through ``self.queryset``, so POST validation and
        tenant scoping are untouched.
        """
        super().add_fields(form, index)
        if "owner" not in form.fields:
            return
        if not hasattr(self, "_owner_choices"):
            self._owner_choices = list(form.fields["owner"].choices)
        form.fields["owner"].choices = self._owner_choices


CapaTaskFormSet = inlineformset_factory(
    CapaAction, CapaTask, form=CapaTaskForm, formset=BaseCapaTaskFormSet, extra=1,
    can_delete=True, max_num=100, validate_max=True,
)


class CapaVerificationForm(forms.Form):
    """The effectiveness sign-off — QT9 verifies AFTER the action is implemented, not with it.

    ``not_effective`` is not a failure state to be tidied away: it sends the CAPA back to
    ``investigating`` with the notes recorded, which is the whole reason the verification step
    exists rather than closing straight from implemented.
    """

    effectiveness_result = forms.ChoiceField(
        choices=[choice for choice in CapaAction.EFFECTIVENESS_CHOICES if choice[0] != "pending"])
    verified_by = forms.ModelChoiceField(queryset=Party.objects.none(), required=False)
    verified_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        validators=[MinValueValidator(_MIN_DATE), MaxValueValidator(_MAX_DATE)],
        help_text="Defaults to today when left blank")
    verification_notes = forms.CharField(required=False, max_length=4000,
                                         widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields["verified_by"].queryset = _employee_parties(tenant)
