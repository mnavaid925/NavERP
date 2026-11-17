from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview

User = get_user_model()


class DesignReviewForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DesignReview
        fields = [
            "project",
            "title",
            "review_stage",
            "review_date",
            "status",
            "lead_reviewer",
            "independent_reviewer",
            "agenda",
            "discussion_summary",
            "conclusions",
            "action_items",
            "action_items_resolved",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Design Input Freeze Gate Review"}),
            "review_stage": forms.Select(attrs={"class": "form-select"}),
            "review_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "lead_reviewer": forms.Select(attrs={"class": "form-select"}),
            "independent_reviewer": forms.Select(attrs={"class": "form-select"}),
            "agenda": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Meeting agenda and attendees..."}),
            "discussion_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Key technical findings, trade-offs, and design discussion..."}),
            "conclusions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Stage-gate formal evaluation and clearance decision rationale..."}),
            "action_items": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Action items, assignees, and resolution due dates..."}),
            "action_items_resolved": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["project"].queryset = DesignProject.objects.filter(tenant=self.tenant).order_by("number")
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["lead_reviewer"].queryset = user_qs
            self.fields["independent_reviewer"].queryset = user_qs
        else:
            self.fields["project"].queryset = DesignProject.objects.none()
            self.fields["lead_reviewer"].queryset = User.objects.none()
            self.fields["independent_reviewer"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["project", "lead_reviewer", "independent_reviewer"])

        project = cleaned.get("project")
        if project and project.dhf_locked:
            self.add_error("project", "Cannot create or modify design reviews for a project with a locked Design History File (DHF).")
        elif self.instance.pk and self.instance.project and self.instance.project.dhf_locked:
            self.add_error("project", "Cannot modify records belonging to a project with a locked Design History File (DHF).")

        lead = cleaned.get("lead_reviewer")
        indep = cleaned.get("independent_reviewer")
        if lead and indep and lead.pk == indep.pk:
            self.add_error(
                "independent_reviewer",
                "21 CFR § 820.30(e) requires an independent reviewer who does not have direct responsibility for the design stage being reviewed."
            )

        return cleaned
