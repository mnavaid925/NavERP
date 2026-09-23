"""Projects 7.19 — ProjectTeam and ProjectTeamMember models [PTE-].

Matrix project team structures, corporate organization hierarchy integration (core.OrgUnit),
and cross-functional resource allocation percentages.
"""
from apps.projects.models._base import *


class ProjectTeam(TenantNumbered):
    """Project delivery team supporting matrix structures and corporate OrgUnit alignment."""

    NUMBER_PREFIX = "PTE"

    TEAM_TYPE_CHOICES = [
        ("dedicated", "Dedicated Project Team"),
        ("matrix", "Matrix Shared Team"),
        ("cross_functional", "Cross-Functional Delivery"),
        ("agile_pod", "Agile Pod / Scrum Team"),
        ("vendor_external", "Vendor / Contractor Team"),
    ]

    name = models.CharField(max_length=255, help_text="Team name or pod designation.")
    code = models.CharField(max_length=50, blank=True, help_text="Short team code (e.g. POD-CORE-01).")
    team_type = models.CharField(
        max_length=20,
        choices=TEAM_TYPE_CHOICES,
        default="cross_functional",
        help_text="Organizational structure and commitment model.",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_teams",
        help_text="Corporate organizational unit (department/branch/cost center) in company hierarchy.",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
        help_text="Optional dedicated project assignment (leave blank for shared enterprise resource pools).",
    )
    team_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_project_teams",
        help_text="Lead engineer, scrum master, or delivery lead accountable for this team.",
    )
    description = models.TextField(blank=True, help_text="Remit, focus areas, and operational charter.")
    location = models.CharField(max_length=100, blank=True, help_text="Geographic hub or primary office.")
    is_active = models.BooleanField(default=True, help_text="Active team available for staffing.")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "team_type"], name="pte_tnt_type_idx"),
            models.Index(fields=["tenant", "org_unit"], name="pte_tnt_org_idx"),
            models.Index(fields=["tenant", "project"], name="pte_tnt_prj_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def team_type_badge_class(self):
        mapping = {
            "dedicated": "badge-green",
            "matrix": "badge-info",
            "cross_functional": "badge-amber",
            "agile_pod": "badge-purple" if False else "badge-green",
            "vendor_external": "badge-slate",
        }
        return mapping.get(self.team_type, "badge-slate")


class ProjectTeamMember(TenantOwned):
    """Member allocation to a project team with matrix allocation percentage."""

    ROLE_CHOICES = [
        ("project_manager", "Project Manager"),
        ("scrum_master", "Scrum Master"),
        ("tech_lead", "Technical Lead"),
        ("developer", "Software Engineer / Developer"),
        ("designer", "UI/UX Designer"),
        ("qa_engineer", "QA / Test Engineer"),
        ("business_analyst", "Business Analyst"),
        ("consultant", "Functional Consultant"),
        ("stakeholder", "Team Stakeholder"),
    ]

    team = models.ForeignKey(
        ProjectTeam,
        on_delete=models.CASCADE,
        related_name="members",
        help_text="Parent project team.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_team_memberships",
        help_text="Team member user account.",
    )
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default="developer",
        help_text="Functional role within this team.",
    )
    allocation_percentage = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Matrix allocation commitment percentage (1% to 100%).",
    )
    is_primary_contact = models.BooleanField(
        default=False,
        help_text="Primary liaison contact for this team.",
    )
    joined_date = models.DateField(null=True, blank=True, help_text="Date member joined this team.")
    left_date = models.DateField(null=True, blank=True, help_text="Date member departed or rotated out.")

    class Meta:
        ordering = ["-is_primary_contact", "user__username"]
        unique_together = ("team", "user")

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()} - {self.allocation_percentage}%) in {self.team.name}"

    def clean(self):
        super().clean()
        if self.joined_date and self.left_date and self.joined_date > self.left_date:
            raise ValidationError({"left_date": "Departure date cannot be prior to joined date."})
