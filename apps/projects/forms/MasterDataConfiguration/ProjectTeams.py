"""Projects 7.19 — ProjectTeam and ProjectTeamMember forms."""
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms.models import ModelChoiceIterator

from apps.core.models import OrgUnit
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.forms.MasterDataConfiguration.CustomFieldMixin import ProjectCustomFieldFormMixin
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam, ProjectTeamMember
from apps.projects.models.ProjectInitiation.Projects import Project

User = get_user_model()


class _BoundedModelChoiceIterator(ModelChoiceIterator):
    def __iter__(self):
        limit = getattr(self.field, "choice_limit", None)
        if limit is not None:
            self.queryset = self.queryset[:limit]
        yield from super().__iter__()


def _bound_choices(field, limit):
    field.iterator = _BoundedModelChoiceIterator
    field.choice_limit = limit
    field.widget.choices = field.choices


class ProjectTeamForm(ProjectCustomFieldFormMixin, TenantUniqueMixin, TenantModelForm):
    custom_field_target = "team"
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
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is None:
            self.fields["org_unit"].queryset = OrgUnit.objects.none()
            self.fields["project"].queryset = Project.objects.none()
            self.fields["team_lead"].queryset = User.objects.none()
        else:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).only("id", "name", "tenant_id").order_by("name")
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).only("id", "name", "tenant_id", "created_at").order_by("-created_at")
            self.fields["team_lead"].queryset = User.objects.filter(
                Q(tenant=self.tenant) | Q(tenant__isnull=True),
                is_active=True,
            ).only(
                "id", "username", "first_name", "last_name", "email", "tenant_id", "is_active"
            ).order_by("username")
            _bound_choices(self.fields["org_unit"], 500)
            _bound_choices(self.fields["project"], 500)
            _bound_choices(self.fields["team_lead"], 100)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["org_unit", "project"])
        return cleaned


class ProjectTeamMemberForm(TenantUniqueMixin, TenantModelForm):
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
            "is_primary_contact": forms.CheckboxInput(attrs={"class": "form-check"}),
            "joined_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, team=None, **kwargs):
        self.team = team
        super().__init__(*args, **kwargs)
        if self.team is not None and not self.instance.team_id:
            self.instance.team = self.team
        if self.tenant is not None:
            self.fields["user"].queryset = User.objects.filter(
                Q(tenant=self.tenant) | Q(tenant__isnull=True),
                is_active=True,
            ).only(
                "id", "username", "first_name", "last_name", "email", "tenant_id", "is_active"
            ).order_by("username")
            _bound_choices(self.fields["user"], 100)
        else:
            self.fields["user"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        team = self.team
        if team is None and self.instance.team_id:
            team = self.instance.team
        user = cleaned.get("user")
        if team is not None and self.tenant is not None and team.tenant_id != self.tenant.pk:
            raise forms.ValidationError("The selected team belongs to another workspace.")
        if user is not None and self.tenant is not None and user.tenant_id not in (None, self.tenant.pk):
            self.add_error("user", "That user belongs to another workspace.")
        if team is not None and user is not None:
            duplicates = ProjectTeamMember.objects.filter(team=team, user=user)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error("user", "This user is already a member of the team.")
        return cleaned


class ProjectTeamMemberInlineForm(forms.ModelForm):
    class Meta:
        model = ProjectTeamMember
        fields = [
            "user",
            "role",
            "allocation_percentage",
            "is_primary_contact",
            "joined_date",
            "left_date",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "allocation_percentage": forms.NumberInput(
                attrs={"class": "form-input", "min": 1, "max": 100}
            ),
            "is_primary_contact": forms.CheckboxInput(attrs={"class": "form-check"}),
            "joined_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "left_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        team = self.instance.team if self.instance.team_id else None
        tenant = getattr(team, "tenant", None)
        if tenant is None:
            self.fields["user"].queryset = User.objects.none()
        else:
            self.fields["user"].queryset = User.objects.filter(
                Q(tenant=tenant) | Q(tenant__isnull=True), is_active=True
            ).only(
                "id", "username", "first_name", "last_name", "email", "tenant_id", "is_active"
            ).order_by("username")
            _bound_choices(self.fields["user"], 100)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.team_id:
            instance.tenant = instance.team.tenant
        if commit:
            instance.save()
        return instance
