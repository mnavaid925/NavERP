from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.PerformanceScorecards.StrategicObjectives import StrategicObjective
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


class StrategicObjectiveForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StrategicObjective
        fields = [
            "code",
            "name",
            "slug",
            "perspective",
            "statement_of_intent",
            "parent_objective",
            "target_date",
            "status",
            "owner",
            "org_unit",
            "sort_order",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. STRAT-OBJ-01"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Expand High-Margin SaaS Revenue"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "expand-high-margin-saas-revenue"}),
            "perspective": forms.Select(attrs={"class": "form-select"}),
            "statement_of_intent": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Narrative strategic rationale, hypothesized cause-and-effect outcomes..."}),
            "parent_objective": forms.Select(attrs={"class": "form-select"}),
            "target_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            parent_qs = StrategicObjective.objects.filter(tenant=self.tenant).order_by("perspective", "name")
            if self.instance and self.instance.pk:
                parent_qs = parent_qs.exclude(pk=self.instance.pk)
            self.fields["parent_objective"].queryset = parent_qs
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
        self.fields["slug"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        name = self.cleaned_data.get("name")
        if not slug and name:
            slug = slugify(name)[:120]
        return slug

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["parent_objective", "org_unit", "owner"])

        parent = cleaned.get("parent_objective")
        if parent and self.instance and parent.pk == self.instance.pk:
            self.add_error("parent_objective", "An objective cannot be its own parent.")

        return cleaned
