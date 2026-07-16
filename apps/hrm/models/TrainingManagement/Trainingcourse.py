"""HRM 3.22 Training Management — Trainingcourse models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.22 Training Management — Instructor-Led Training (ILT) scheduling + catalog.
# A NEW HRM domain (not a Performance-Management continuation): a course catalog
# (``TrainingCourse``) and its scheduled occurrences (``TrainingSession``), unified
# across classroom / virtual / external delivery via ``delivery_mode``. Training data
# is ORDINARY tenant-scoped CRUD — no subject/manager confidentiality gate (unlike the
# 3.18–3.21 performance cluster); every authenticated tenant user may see it, same
# openness as 3.2 Designation/JobGrade.
#
# Reuses (never duplicates): ``hrm.EmployeeProfile`` (internal instructor), ``core.Party``
# (external vendor — a ``PartyRole.role="vendor"`` party, NOT a new HRM vendor table;
# ``accounting.VendorProfile`` already extends Party on the AP side), and
# ``accounting.Currency`` (the GLOBAL currency master — string FK, lazy-imported in the
# form so accounting stays a runtime, not module-load, dependency).
#
# Deferred to sibling sub-modules (do NOT build here): 3.23 Learning Management (LMS)
# owns course content / learning paths / assessments / gamification / progress tracking;
# 3.24 Training Administration owns nomination, per-employee attendance capture, post-
# training feedback, certificate generation, and aggregate training-budget/ROI rollups
# (which will consume the estimated/actual cost captured on ``TrainingSession`` here).
# ---------------------------------------------------------------------------
class TrainingCourse(TenantNumbered):
    """A catalog course (3.22 Training Catalog) — the reusable definition an employee is scheduled
    into via a ``TrainingSession``. HRM-owned master (analogous to ``Designation``/``PayComponent``),
    not a core-spine entity. A course can grant a certification and can require a prerequisite course
    (self-FK) — the actual per-occurrence schedule/venue/instructor lives on ``TrainingSession``."""

    NUMBER_PREFIX = "TRC"

    CATEGORY_CHOICES = [
        ("technical", "Technical"),
        ("compliance", "Compliance"),
        ("leadership", "Leadership"),
        ("soft_skills", "Soft Skills"),
        ("safety", "Safety"),
        ("onboarding", "Onboarding"),
        ("product", "Product"),
        ("other", "Other"),
    ]
    # The course's TYPICAL delivery mode (a default hint); the real per-occurrence mode is on the
    # session and may differ. Wider than the session's set — a course can be marketed as "blended".
    DELIVERY_MODE_CHOICES = [
        ("classroom", "Classroom"),
        ("virtual", "Virtual"),
        ("external", "External"),
        ("blended", "Blended"),
    ]
    PROVIDER_TYPE_CHOICES = [
        ("internal", "Internal"),
        ("external", "External"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="technical")
    delivery_mode = models.CharField(max_length=15, choices=DELIVERY_MODE_CHOICES, default="classroom",
                                     help_text="The course's typical mode; each session sets its own actual mode.")
    provider_type = models.CharField(max_length=10, choices=PROVIDER_TYPE_CHOICES, default="internal",
                                     help_text="Run in-house (internal) or sourced from an external provider.")
    duration_hours = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO,
                                         validators=[MinValueValidator(ZERO)])
    is_certification = models.BooleanField(default=False,
                                           help_text="This course grants (or represents) a certification.")
    certification_name = models.CharField(max_length=255, blank=True)
    certification_validity_months = models.PositiveIntegerField(null=True, blank=True,
                                                                help_text="How long the certification stays valid.")
    prerequisite_course = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="unlocks",
                                            help_text="A course that must be completed first.")
    default_capacity = models.PositiveIntegerField(null=True, blank=True,
                                                   help_text="Default seat limit new sessions inherit.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "category"], name="hrm_trc_tenant_category_idx"),
            models.Index(fields=["tenant", "is_active"], name="hrm_trc_tenant_active_idx"),
            models.Index(fields=["tenant", "delivery_mode"], name="hrm_trc_tenant_mode_idx"),
        ]

    def clean(self):
        if self.is_certification and not self.certification_name.strip():
            raise ValidationError({"certification_name": "Name the certification a certification course grants."})
        if self.prerequisite_course_id and self.pk and self.prerequisite_course_id == self.pk:
            raise ValidationError({"prerequisite_course": "A course can't be its own prerequisite."})

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title
