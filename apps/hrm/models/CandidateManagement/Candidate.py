"""HRM 3.6 Candidate Management — Candidate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.CandidateManagement.HEX_COLOR_VALIDATORs import HEX_COLOR_VALIDATOR
from apps.hrm.models.CandidateManagement.QUALIFICATION_CHOICESs import QUALIFICATION_CHOICES
from apps.hrm.models.CandidateManagement.SKILL_PROFICIENCY_CHOICESs import SKILL_PROFICIENCY_CHOICES
from apps.hrm.models.CandidateManagement.SKILL_SOURCE_CHOICESs import SKILL_SOURCE_CHOICES
from apps.hrm.models.CandidateManagement.HEX_COLOR_VALIDATORs import HEX_COLOR_VALIDATOR
from apps.hrm.models.CandidateManagement.QUALIFICATION_CHOICESs import QUALIFICATION_CHOICES
from apps.hrm.models.CandidateManagement.SKILL_PROFICIENCY_CHOICESs import SKILL_PROFICIENCY_CHOICES
from apps.hrm.models.CandidateManagement.SKILL_SOURCE_CHOICESs import SKILL_SOURCE_CHOICES


CANDIDATE_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("hired", "Hired"),
    ("blacklisted", "Blacklisted"),
    ("do_not_contact", "Do Not Contact"),
]


CANDIDATE_GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("non_binary", "Non-Binary"),
    ("prefer_not_to_say", "Prefer Not to Say"),
]


CANDIDATE_SOURCE_CHOICES = [
    ("careers_page", "Company Careers Page"),
    ("referral", "Employee Referral"),
    ("linkedin", "LinkedIn"),
    ("indeed", "Indeed"),
    ("glassdoor", "Glassdoor"),
    ("job_board", "Other Job Board"),
    ("agency", "Recruitment Agency"),
    ("direct_approach", "Direct / Sourced"),
    ("walk_in", "Walk-in"),
    ("other", "Other"),
]


class CandidateTag(TenantOwned):
    """Reusable talent-pool / segmentation label (3.6). A simple tenant catalog (name + color)
    M2M'd onto ``CandidateProfile`` — mirrors the Greenhouse/Ashby/Workable profile-tag pattern.
    No detail page (too few fields); list/create/edit/delete only."""

    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#6B7280", validators=[HEX_COLOR_VALIDATOR],
                             help_text="Hex color for the tag badge, e.g. #3B82F6.")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "name"], name="hrm_ctag_tenant_name_idx"),
        ]

    def __str__(self):
        return self.name


class CandidateProfile(TenantNumbered):
    """The ATS candidate record (3.6) — a 1:1 extension of ``core.Party`` (with a
    ``PartyRole(role="candidate")`` marker), exactly mirroring ``EmployeeProfile``. Carries the
    talent-acquisition fields (contact, resume, skills, sourcing, GDPR consent). ``status`` is the
    candidate-level lifecycle state (distinct from a per-application ``stage``) and is workflow-owned."""

    NUMBER_PREFIX = "CAND"

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="candidate_profile")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(help_text="Unique per tenant — the duplicate-detection anchor.")
    phone = models.CharField(max_length=30, blank=True)
    linkedin_url = models.URLField(blank=True)
    current_job_title = models.CharField(max_length=255, blank=True)
    current_employer = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2 country code.")
    years_of_experience = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    highest_qualification = models.CharField(max_length=20, choices=QUALIFICATION_CHOICES, blank=True)
    skill_set = models.TextField(blank=True,
        help_text="Comma-delimited free-text skills. Structured skills live in CandidateSkill.")
    resume_file = models.FileField(upload_to="hrm/candidates/resumes/%Y/%m/", null=True, blank=True)
    resume_text = models.TextField(blank=True,
        help_text="Raw text extracted from the resume — powers keyword search (NLP parsing deferred).")
    photo = models.ImageField(upload_to="hrm/candidates/photos/%Y/%m/", null=True, blank=True)
    gender = models.CharField(max_length=20, choices=CANDIDATE_GENDER_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=CANDIDATE_STATUS_CHOICES, default="active",
                              editable=False)
    source = models.CharField(max_length=20, choices=CANDIDATE_SOURCE_CHOICES, blank=True)
    do_not_contact = models.BooleanField(default=False,
        help_text="Suppresses all automated candidate emails.")
    gdpr_consent = models.BooleanField(default=False)
    gdpr_consent_date = models.DateTimeField(null=True, blank=True, editable=False)
    gdpr_consent_expires = models.DateField(null=True, blank=True,
        help_text="Data-retention window; after this date the record is eligible for anonymization.")
    notes = models.TextField(blank=True)
    sourced_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="sourced_candidates")
    expected_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True)
    tags = models.ManyToManyField("hrm.CandidateTag", blank=True, related_name="candidates")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        constraints = [
            models.UniqueConstraint(fields=["tenant", "email"], name="hrm_cand_tenant_email_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_cand_tenant_status_idx"),
            models.Index(fields=["tenant", "source"], name="hrm_cand_tenant_source_idx"),
            models.Index(fields=["tenant", "do_not_contact"], name="hrm_cand_tenant_dnc_idx"),
            # Supports the default ``-created_at`` ordering of the candidate list under the tenant filter.
            models.Index(fields=["tenant", "created_at"], name="hrm_cand_tenant_created_idx"),
        ]

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name


class CandidateSkill(TenantOwned):
    """A structured skill on a candidate (3.6). Child of ``CandidateProfile`` — rows are added/removed
    via POST actions on the candidate detail hub (no standalone form), mirroring the
    ``RequisitionApproval`` / ``ClearanceItem`` inline-child pattern. Powers filter-by-skill search."""

    candidate = models.ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="skills")
    skill_name = models.CharField(max_length=100)
    proficiency = models.CharField(max_length=20, choices=SKILL_PROFICIENCY_CHOICES, blank=True)
    source = models.CharField(max_length=20, choices=SKILL_SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["skill_name"]
        unique_together = ("candidate", "skill_name")
        indexes = [
            models.Index(fields=["tenant", "skill_name"], name="hrm_cskill_tenant_name_idx"),
        ]

    def __str__(self):
        label = self.get_proficiency_display() if self.proficiency else "—"
        return f"{self.skill_name} ({label})"
