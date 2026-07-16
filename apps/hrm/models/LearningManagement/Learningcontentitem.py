"""HRM 3.23 Learning Management (LMS) — Learningcontentitem models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.23 Learning Management (LMS) — the self-paced digital-learning layer that
# BUILDS ON the 3.22 ``TrainingCourse`` catalog (it never re-creates a course
# table). Four models: ``LearningContentItem`` (ordered lessons + a light
# assessment variant, a CASCADE child of a course), ``LearningPath`` (LNP-, a
# role-based journey) + ``LearningPathItem`` (its ordered course refs), and
# ``LearningProgress`` (per-employee×course completion/score/points). Ordinary
# tenant-scoped CRUD — no confidentiality gate (like 3.22).
#
# Reuses: ``hrm.TrainingCourse`` (is_certification/certification_validity_months/
# prerequisite_course already modeled in 3.22), ``hrm.EmployeeProfile`` (learner),
# ``hrm.Designation`` + ``core.OrgUnit`` (kind="department") for path targeting.
# No new core-spine entity; nothing posts to the GL. Gamification leaderboards +
# level tiers are DERIVED queries over ``LearningProgress.points_earned`` — no
# stored leaderboard/badge tables.
#
# Deferred to later passes / 3.24 (do NOT build here): a real question-bank
# assessment engine (Question/Choice/Answer tables + multiple question types),
# the SCORM JS runtime / xAPI LRS (this pass stores the package file only), an LMS
# achievement-badge catalog (distinct from 3.20 ``KudosBadge``), adaptive/
# conditional paths + auto-enrollment, and 3.24 Training Administration
# (nomination, ILT attendance, feedback, certificate issuance, training budget).
# ---------------------------------------------------------------------------
class LearningContentItem(TenantOwned):
    """An ordered lesson/content piece within a ``TrainingCourse`` (3.23 Course Content) — a
    video/document/SCORM/external-link/text item, or a lightweight ``assessment`` (pass-threshold +
    attempts + time-limit, NO stored question bank this pass). A CASCADE child of the course (its
    lessons die with the course), mirroring the ``ClearanceItem``→``SeparationCase`` child pattern."""

    CONTENT_TYPE_CHOICES = [
        ("video", "Video"),
        ("document", "Document"),
        ("scorm", "SCORM Package"),
        ("external_link", "External Link"),
        ("text", "Text / Article"),
        ("assessment", "Assessment"),
    ]

    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.CASCADE, related_name="content_items")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    content_type = models.CharField(max_length=15, choices=CONTENT_TYPE_CHOICES, default="video")
    sequence = models.PositiveIntegerField(default=0, help_text="Ordered lesson position within the course.")
    is_required = models.BooleanField(default=True, help_text="Required for course completion (vs. supplemental).")
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    # Content payload — only the one matching content_type is expected filled (enforced in clean()).
    video_url = models.URLField(blank=True)
    document_file = models.FileField(upload_to="hrm/lms/documents/%Y/%m/", blank=True)
    # WARNING: the SCORM package is stored as an OPAQUE file only this pass — it is never extracted.
    # A future SCORM-extraction handler MUST validate archive member paths (zip-slip / path-traversal
    # guard: reject "../" and absolute paths) before writing extracted files to disk — do not trust
    # package internals. See the deferred note in the 3.23 section header.
    scorm_package = models.FileField(upload_to="hrm/lms/scorm/%Y/%m/", blank=True)
    external_url = models.URLField(blank=True)
    body_text = models.TextField(blank=True)
    # Assessment-only (content_type="assessment"); score/pass outcomes live on LearningProgress.
    pass_threshold_percent = models.PositiveIntegerField(
        default=70, validators=[MinValueValidator(0), MaxValueValidator(100)])
    max_attempts = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["course", "sequence"]
        indexes = [
            models.Index(fields=["tenant", "course"], name="hrm_lci_tenant_course_idx"),
            models.Index(fields=["tenant", "content_type"], name="hrm_lci_tenant_ctype_idx"),
        ]

    def clean(self):
        # Enforce the ONE content field matching content_type is present (never force-blanks the
        # others — an assessment may still carry body_text instructions).
        required = {
            "video": ("video_url", "a video URL"),
            "document": ("document_file", "a document file"),
            "scorm": ("scorm_package", "a SCORM package file"),
            "external_link": ("external_url", "an external URL"),
            "text": ("body_text", "the article text"),
        }.get(self.content_type)
        if required:
            field, label = required
            value = getattr(self, field, None)
            if not (str(value).strip() if value else ""):
                raise ValidationError({field: f"A {self.get_content_type_display()} lesson needs {label}."})

    def __str__(self):
        if self.course_id:
            return f"{self.course.title} · {self.sequence}. {self.title}"
        return self.title
