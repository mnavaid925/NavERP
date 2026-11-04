from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit


class BusinessGlossaryTermForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BusinessGlossaryTerm
        fields = [
            "name",
            "code",
            "domain_category",
            "short_definition",
            "full_definition",
            "calculation_rule",
            "synonyms",
            "steward",
            "org_unit",
            "related_terms",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Net Recurring Revenue (NRR)"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. net_recurring_revenue"}),
            "domain_category": forms.Select(attrs={"class": "form-select"}),
            "short_definition": forms.TextInput(attrs={"class": "form-input", "placeholder": "Executive one-line definition"}),
            "full_definition": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Detailed corporate standard definition..."}),
            "calculation_rule": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "Formula narrative, e.g. (Starting ARR + Expansion - Churn) / Starting ARR"}),
            "synonyms": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. NRR, Net Retention Rate"}),
            "steward": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "related_terms": forms.SelectMultiple(attrs={"class": "form-select", "size": "4"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.steward_id:
                steward_filter |= Q(pk=self.instance.steward_id)
            self.fields["steward"].queryset = user_qs.filter(steward_filter).order_by("username")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            term_qs = BusinessGlossaryTerm.objects.filter(tenant=self.tenant).order_by("name")
            if self.instance and self.instance.pk:
                term_qs = term_qs.exclude(pk=self.instance.pk)
            self.fields["related_terms"].queryset = term_qs
        else:
            self.fields["steward"].queryset = get_user_model().objects.none()
            self.fields["org_unit"].queryset = OrgUnit.objects.none()
            self.fields["related_terms"].queryset = BusinessGlossaryTerm.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["org_unit", "related_terms", "steward"])
        return cleaned_data


class BusinessGlossaryTermCertificationForm(forms.Form):
    certification_status = forms.ChoiceField(
        choices=BusinessGlossaryTerm.CERTIFICATION_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    certification_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason or approval notes for status transition..."}
        ),
    )
