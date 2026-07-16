"""HRM 3.40 Workforce Planning — Employeeskill models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class EmployeeSkill(TenantOwned):
    """One skill on an employee's profile — the skills inventory behind Supply Analysis. Mirrors the
    existing ``CandidateSkill`` shape (3.6), just anchored to EmployeeProfile. Own-vs-admin: an employee
    curates their own skills; HR sees the whole inventory."""

    SKILL_CATEGORY_CHOICES = [
        ("technical", "Technical"),
        ("functional", "Functional"),
        ("leadership", "Leadership"),
        ("soft_skill", "Soft Skill"),
        ("certification", "Certification"),
    ]
    PROFICIENCY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
        ("expert", "Expert"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="skills")
    skill_name = models.CharField(max_length=120)
    skill_category = models.CharField(max_length=15, choices=SKILL_CATEGORY_CHOICES, default="technical")
    proficiency_level = models.CharField(max_length=15, choices=PROFICIENCY_CHOICES, default="intermediate")
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    is_certified = models.BooleanField(default=False)
    certification_name = models.CharField(max_length=150, blank=True)
    last_assessed_date = models.DateField(null=True, blank=True)
    is_critical_skill = models.BooleanField(default=False,
                                            help_text="Flags a skill critical to future workforce needs.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["skill_name", "id"]
        unique_together = ("tenant", "employee", "skill_name")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_eskill_tnt_emp_idx"),
            models.Index(fields=["tenant", "skill_category"], name="hrm_eskill_tnt_cat_idx"),
            models.Index(fields=["tenant", "proficiency_level"], name="hrm_eskill_tnt_prof_idx"),
            models.Index(fields=["tenant", "is_critical_skill"], name="hrm_eskill_tnt_crit_idx"),
        ]

    def __str__(self):
        return f"{self.skill_name} ({self.get_proficiency_level_display()})"
