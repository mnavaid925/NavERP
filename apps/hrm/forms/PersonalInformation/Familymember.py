"""HRM 3.25 Personal Information — Familymember forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    FamilyMember,
)
from apps.hrm.forms.PersonalInformation._helpers import _ThemedForm


class FamilyMemberForm(TenantModelForm):
    class Meta:
        model = FamilyMember
        fields = ["name", "relationship", "date_of_birth", "gender", "occupation", "phone",
                  "is_dependent", "is_minor", "guardian_name", "guardian_relationship",
                  "is_nominee", "nominee_percentage", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class FamilyMemberChangeForm(_ThemedForm):
    """Employee proposes a new family member, or an edit to one of their existing members."""

    existing_member = forms.ModelChoiceField(
        queryset=FamilyMember.objects.none(), required=False,
        empty_label="-- Propose a new family member --",
        help_text="Leave blank to add a new member; pick one to edit it.")
    name = forms.CharField(max_length=255)
    relationship = forms.ChoiceField(choices=FamilyMember.RELATIONSHIP_CHOICES)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    gender = forms.ChoiceField(required=False, choices=[("", "---------")] + list(EmployeeProfile.GENDER_CHOICES))
    occupation = forms.CharField(max_length=255, required=False)
    phone = forms.CharField(max_length=30, required=False)
    is_dependent = forms.BooleanField(required=False)
    is_minor = forms.BooleanField(required=False)
    guardian_name = forms.CharField(max_length=255, required=False)
    guardian_relationship = forms.CharField(max_length=100, required=False)
    is_nominee = forms.BooleanField(required=False)
    nominee_percentage = forms.DecimalField(max_digits=5, decimal_places=2, required=False,
                                            min_value=0, max_value=100)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, employee=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.fields["existing_member"].queryset = FamilyMember.objects.filter(
                tenant=tenant, employee=employee).order_by("name")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_minor") and not cleaned.get("guardian_name"):
            self.add_error("guardian_name", "Guardian name is required for a minor family member.")
        return cleaned
