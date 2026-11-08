import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.CollaborationStorytelling.BiDataStories import BiDataStory
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.core.forms import TenantModelForm

User = get_user_model()


class BiDataStoryForm(TenantUniqueMixin, TenantModelForm):
    slides_data_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "class": "form-textarea font-mono text-xs"}),
        label="Presentation Slides Data (JSON)",
        help_text='JSON array of slide definitions: [{"slide_num": 1, "title": "Revenue Growth", "narrative": "Q3 performance exceeded plan by 14%", "visual_type": "kpi_card", "filter_state": {"quarter": "Q3"}}]',
    )

    class Meta:
        model = BiDataStory
        fields = [
            "title",
            "slug",
            "summary",
            "workspace",
            "story_type",
            "status",
            "theme",
            "author",
            "allow_live_drilldown",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "summary": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "workspace": forms.Select(attrs={"class": "form-select"}),
            "story_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "theme": forms.Select(attrs={"class": "form-select"}),
            "author": forms.Select(attrs={"class": "form-select"}),
            "allow_live_drilldown": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["workspace"].queryset = BiSharedWorkspace.objects.filter(tenant=self.tenant)
            self.fields["author"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
        else:
            self.fields["workspace"].queryset = BiSharedWorkspace.objects.none()
            self.fields["author"].queryset = User.objects.none()
        if self.instance and self.instance.pk:
            if self.instance.slides_data:
                self.fields["slides_data_raw"].initial = json.dumps(self.instance.slides_data, indent=2)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["workspace", "author"])
        return cleaned

    def clean_slides_data_raw(self):
        raw = self.cleaned_data.get("slides_data_raw", "").strip()
        if not raw:
            return []
        try:
            val = json.loads(raw)
            if not isinstance(val, list):
                raise ValidationError("Slides data must be a JSON array of slide objects.")
            return val
        except (json.JSONDecodeError, ValueError) as err:
            raise ValidationError(f"Invalid JSON format for slides: {err}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "slides_data_raw" in self.cleaned_data:
            instance.slides_data = self.cleaned_data["slides_data_raw"]
        if commit:
            instance.save()
        return instance
