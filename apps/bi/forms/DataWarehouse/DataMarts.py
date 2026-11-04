from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit


class DataMartForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataMart
        fields = [
            "name",
            "code",
            "subject_area",
            "org_unit",
            "owner",
            "steward",
            "access_tier",
            "certification_status",
            "refresh_cadence",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Finance & Accounting Mart"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. finance"}),
            "subject_area": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "steward": forms.Select(attrs={"class": "form-select"}),
            "access_tier": forms.Select(attrs={"class": "form-select"}),
            "certification_status": forms.Select(attrs={"class": "form-select"}),
            "refresh_cadence": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Purpose, scope, and SLA notes..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            owner_filter = Q(is_active=True)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk:
                if self.instance.owner_id:
                    owner_filter |= Q(pk=self.instance.owner_id)
                if self.instance.steward_id:
                    steward_filter |= Q(pk=self.instance.steward_id)
            self.fields["owner"].queryset = user_qs.filter(owner_filter).order_by("username")
            self.fields["steward"].queryset = user_qs.filter(steward_filter).order_by("username")
        else:
            self.fields["owner"].queryset = get_user_model().objects.none()
            self.fields["steward"].queryset = get_user_model().objects.none()

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().lower()
        if code:
            existing = DataMart.objects.filter(tenant=self.tenant, code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("A data mart with this slug code already exists in your workspace.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["org_unit", "owner", "steward"])
        return cleaned_data
