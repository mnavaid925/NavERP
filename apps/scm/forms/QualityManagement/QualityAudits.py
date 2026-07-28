"""SCM 4.9 Quality Management — QualityAudit form + the raise-a-finding payload."""
from datetime import date

from django.core.validators import MaxValueValidator, MinValueValidator

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _employee_parties
from apps.scm.models import NonConformance, QualityAudit

_MIN_DATE = date(2000, 1, 1)
_MAX_DATE = date(2100, 12, 31)


class QualityAuditForm(TenantUniqueMixin, TenantModelForm):
    """The audit header.

    EXCLUDES `number` (auto) and `status` / `actual_start` / `actual_end` — the start and complete
    actions are their only writers. `conclusion` IS editable: it is the auditor's narrative, and the
    complete action refuses while it is blank rather than writing it.

    `auditee_org_unit` and `checklist_plan` carry their own tenant so the base class scopes them;
    the two Party fields need narrowing beyond that.
    """

    class Meta:
        model = QualityAudit
        fields = ["audit_type", "title", "standard", "scope", "auditee_party", "auditee_org_unit",
                  "checklist_plan", "lead_auditor", "planned_date", "risk_level", "conclusion",
                  "notes"]
        widgets = {"planned_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "checklist_plan" in self.fields:
            # Only an audit-checklist plan asks audit questions. The model's clean() refuses the
            # rest anyway; narrowing here means the user never gets that far.
            self.fields["checklist_plan"].queryset = self.fields["checklist_plan"].queryset.filter(
                Q(plan_type="audit_checklist", is_active=True)
                | Q(pk=self.instance.checklist_plan_id))
        if "lead_auditor" in self.fields:
            self.fields["lead_auditor"].queryset = _employee_parties(self.tenant)
        # auditee_party is deliberately the FULL tenant party book: a supplier audit, a customer
        # audit and a certification body are three different roles, and _supplier_parties would
        # hide two of them.


class QualityAuditFindingForm(forms.Form):
    """The inline "raise a finding" payload on the audit detail page.

    A plain Form, not a ModelForm, because the view builds the ``NonConformance`` around it —
    ``source="audit"``, the ``audit`` FK, ``detected_by`` from the lead auditor and ``detected_on``
    from today are all decided by the action, not typed. This action is the ONLY creator of
    ``source="audit"`` rows, which is what makes that choice value honest.
    """

    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=4000)
    severity = forms.ChoiceField(choices=NonConformance.SEVERITY_CHOICES, initial="minor")
    defect_category = forms.ChoiceField(choices=NonConformance.DEFECT_CATEGORY_CHOICES,
                                        initial="documentation")
    owner = forms.ModelChoiceField(queryset=Party.objects.none(), required=False,
                                   help_text="Who owns closing this finding")
    due_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        validators=[MinValueValidator(_MIN_DATE), MaxValueValidator(_MAX_DATE)])

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields["owner"].queryset = _employee_parties(tenant)
