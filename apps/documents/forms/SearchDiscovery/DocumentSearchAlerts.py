from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert


class DocumentSearchAlertForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentSearchAlert
        fields = [
            "saved_search",
            "frequency",
            "delivery_channel",
            "status",
            "notes",
            "is_active",
        ]
        widgets = {
            "saved_search": forms.Select(attrs={"class": "form-select"}),
            "frequency": forms.Select(attrs={"class": "form-select"}),
            "delivery_channel": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Notification preferences or internal notes"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["saved_search"].queryset = DocumentSavedSearch.objects.filter(
                tenant=self.tenant,
                is_active=True,
            ).order_by("name")
        self.fields["notes"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["saved_search"])
        saved_search = cleaned_data.get("saved_search")
        subscriber = getattr(self.instance, "subscriber", None) or getattr(self, "user", None)
        if self.tenant and saved_search and subscriber:
            dup_qs = DocumentSearchAlert.objects.filter(
                tenant=self.tenant,
                saved_search=saved_search,
                subscriber=subscriber,
            )
            if self.instance.pk:
                dup_qs = dup_qs.exclude(pk=self.instance.pk)
            if dup_qs.exists():
                self.add_error("saved_search", "You already have an active alert subscription for this saved search.")
        return cleaned_data
