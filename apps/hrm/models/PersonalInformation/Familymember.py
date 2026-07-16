"""HRM 3.25 Personal Information — Familymember models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile


class FamilyMember(TenantOwned):
    """3.25 Family Details — dependents/nominees roster feeding benefits eligibility (ADP/greytHR
    parity). ``is_dependent`` drives benefits/insurance eligibility; ``is_minor`` requires a guardian
    (greytHR "required when checked", enforced in clean()); ``is_nominee``/``nominee_percentage`` is a
    SIMPLIFIED single-percentage field this pass — a full per-scheme (EPF/EPS/ESI/Gratuity) nomination
    sub-table and cross-row "sums to 100%" validation are deferred (need 3.15 as the consumer).
    Create/edit route through ``EmployeeInfoChangeRequest`` for an employee; the model's own writes
    are ``@tenant_admin_required``."""

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse"),
        ("child", "Child"),
        ("father", "Father"),
        ("mother", "Mother"),
        ("sibling", "Sibling"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="family_members")
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=10, choices=RELATIONSHIP_CHOICES, default="spouse")
    date_of_birth = models.DateField(null=True, blank=True)
    # Reuses EmployeeProfile.GENDER_CHOICES directly (same module, no duplicate tuple).
    gender = models.CharField(max_length=20, choices=EmployeeProfile.GENDER_CHOICES, blank=True)
    occupation = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_dependent = models.BooleanField(default=False, help_text="Eligible dependent for benefits/insurance.")
    is_minor = models.BooleanField(default=False)
    guardian_name = models.CharField(max_length=255, blank=True)
    guardian_relationship = models.CharField(max_length=100, blank=True)
    is_nominee = models.BooleanField(default=False)
    nominee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["employee", "name"]
        indexes = [models.Index(fields=["tenant", "employee"], name="hrm_fam_tenant_emp_idx")]

    def clean(self):
        if self.is_minor and not self.guardian_name:
            raise ValidationError({"guardian_name": "Guardian name is required for a minor family member."})

    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()}) - {self.employee}"
