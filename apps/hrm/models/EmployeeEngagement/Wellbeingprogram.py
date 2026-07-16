"""HRM 3.41 Employee Engagement & Wellbeing — Wellbeingprogram models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeEngagement.Wellbeingparticipation import WellbeingParticipation
from apps.hrm.models.EmployeeEngagement.Wellbeingparticipation import WellbeingParticipation


class WellbeingProgram(TenantNumbered):
    """One catalog entry covering Wellbeing Programs / Employee Assistance / Culture & Values / Social
    Connect, discriminated by ``program_type`` (the "one platform, one catalog, a type field" shape every
    researched leader uses). ``is_confidential`` is FORCED true for EAP/counseling in ``save()``."""

    NUMBER_PREFIX = "WBP"

    PROGRAM_TYPE_CHOICES = [
        ("wellness_challenge", "Wellness Challenge"),
        ("mental_health_resource", "Mental Health Resource"),
        ("eap_counseling", "EAP / Counseling"),
        ("culture_assessment", "Culture Assessment"),
        ("team_event", "Team Event"),
        ("interest_group", "Interest Group"),
        ("volunteering", "Volunteering"),
        ("work_life_policy", "Work-Life Policy"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    program_type = models.CharField(max_length=25, choices=PROGRAM_TYPE_CHOICES, default="wellness_challenge")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="hrm_wellbeingprogram_owned")
    target_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                          limit_choices_to={"kind": "department"},
                                          related_name="wellbeing_programs",
                                          help_text="Blank = company-wide.")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True,
                                help_text="Blank for an ongoing resource (e.g. an EAP hotline).")
    points_value = models.PositiveIntegerField(null=True, blank=True,
                                               help_text="Gamification points a participant earns.")
    external_resource_url = models.URLField(blank=True,
                                            help_text="Link out to the provider portal / sign-up page.")
    is_confidential = models.BooleanField(
        default=False,
        help_text="EAP/counseling is ALWAYS confidential (forced on save); its roster is aggregate-only.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    class Meta:
        ordering = ["-start_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "program_type"], name="hrm_wbp_tenant_type_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_wbp_tenant_status_idx"),
            models.Index(fields=["tenant", "target_department"], name="hrm_wbp_tenant_dept_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}" if self.number else self.title

    def save(self, *args, **kwargs):
        # Model-layer confidentiality enforcement: EAP/counseling can never be non-confidential, even if a
        # tampered POST (or a direct .create(is_confidential=False, ...)) says otherwise.
        if self.program_type == "eap_counseling":
            self.is_confidential = True
        return super().save(*args, **kwargs)

    @property
    def participant_count(self):
        """ANNOTATION-AWARE — the list view supplies ``_participant_count`` so rendering N programs doesn't
        fire N COUNTs; falls back to a query for a lone instance."""
        annotated = getattr(self, "_participant_count", None)
        if annotated is not None:
            return annotated
        return self.participations.count()

    def participation_stats(self):
        """Aggregate-only roll-up for the detail page (the ONLY participation view a confidential program
        ever exposes). One GROUP BY + one Sum — no per-employee rows."""
        by_status = {row["status"]: row["n"]
                     for row in self.participations.values("status").annotate(n=models.Count("id"))}
        stats = {key: by_status.get(key, 0)
                 for key, _ in WellbeingParticipation.PARTICIPATION_STATUS_CHOICES}
        stats["total"] = sum(stats.values())
        stats["total_points"] = (self.participations.aggregate(
            v=models.Sum("points_earned"))["v"] or 0)
        return stats
