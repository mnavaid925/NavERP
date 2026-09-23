"""Projects 7.19 — ProjectTeam and ProjectTeamMember forms."""
from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam, ProjectTeamMember
from apps.projects.models.ProjectInitiation.Projects import Project

User = get_user_model()


class ProjectTeamForm(TenantUniqueMixin, TenantModelForm):
    """Admin/PM form for creating and updating project teams."""

    class Meta:
        model = ProjectTeam
        fields = [
            "name",
            "code",
            "team_type",
            "org_unit",
            "project",
            "team_lead",
            "description",
            "location",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Core Banking Transformation Pod"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TEAM-FIN-01"}),
            "team_type": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "project": forms.Select(attrs={"class": "form-select"}),
            "team_lead": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "location": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. London HQ / Remote EMEA"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["team_lead"].queryset = User.objects.filter(
                forms.models.Q(tenant=self.tenant) | forms.models.Q(tenant__isnull=True),
                is_active=True,
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["org_unit", "project"])
        return cleaned


class ProjectTeamMemberForm(TenantModelForm):
    """Form to add or edit a member on a project team."""

    class Meta:
        model = ProjectTeamMember
        fields = [
            "user",
            "role",
            "allocation_percentage",
            "is_primary_contact",
            "joined_date",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "allocation_percentage": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 100}),
            "is_primary_contact": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "joined_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["user"].queryset = User.objects.filter(
                forms.models.Q(tenant=self.tenant) | forms.models.Q(tenant__isnull=True),
                is_active=True,
            ).order_by("username")
