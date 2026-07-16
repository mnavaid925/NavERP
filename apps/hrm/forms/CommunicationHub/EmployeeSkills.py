"""HRM 3.27 Communication Hub — EmployeeSkills forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeSkill,
)


class EmployeeSkillForm(TenantModelForm):
    # employee is resolved server-side by the create view (own-vs-admin self-service).
    class Meta:
        model = EmployeeSkill
        fields = ["skill_name", "skill_category", "proficiency_level", "years_experience",
                  "is_certified", "certification_name", "last_assessed_date", "is_critical_skill", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, employee, skill_name). The form excludes `employee`, but the view seeds
        # the unsaved instance with it (on ADD and EDIT), so both paths can be guarded here.
        skill = cleaned.get("skill_name")
        if skill and self.instance.employee_id and self.tenant is not None:
            dupe = EmployeeSkill.objects.filter(
                tenant=self.tenant, employee_id=self.instance.employee_id, skill_name=skill)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("skill_name", "This skill is already on the employee's profile.")
        return cleaned
