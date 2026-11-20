from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class QualityTrainingCourse(TenantNumbered):
    NUMBER_PREFIX = "QCRS"

    CATEGORY_CHOICES = (
        ("gxp_compliance", "GxP & Regulatory Compliance"),
        ("safety_ehs", "Safety & Environmental Health (EHS)"),
        ("technical_sop", "Standard Operating Procedure (SOP)"),
        ("equipment_operation", "Equipment Operation & Calibration"),
        ("quality_tools", "Quality Tools & Root Cause Analysis"),
        ("general", "General Quality Orientation"),
    )

    DELIVERY_METHOD_CHOICES = (
        ("read_and_understand", "Read & Understand (Document)"),
        ("classroom_lecture", "Classroom / Instructor-Led"),
        ("on_the_job", "On-the-Job Training (OJT)"),
        ("elearning", "Digital / e-Learning Module"),
        ("vendor_external", "External Vendor Seminar"),
        ("blended", "Blended Learning"),
    )

    ASSESSMENT_METHOD_CHOICES = (
        ("written_exam", "Written Examination / Quiz"),
        ("practical_ojt", "Practical OJT Demonstration"),
        ("attendance_only", "Attendance / Participation Only"),
        ("both_exam_and_ojt", "Combined Exam & OJT Evaluation"),
        ("manager_evaluation", "Manager Direct Evaluation"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("active", "Active"),
        ("under_revision", "Under Revision"),
        ("retired", "Retired"),
    )

    CATEGORY_CSS = {
        "gxp_compliance": "badge-red",
        "safety_ehs": "badge-amber",
        "technical_sop": "badge-info",
        "equipment_operation": "badge-slate",
        "quality_tools": "badge-green",
        "general": "badge-muted",
    }

    DELIVERY_METHOD_CSS = {
        "read_and_understand": "badge-info",
        "classroom_lecture": "badge-slate",
        "on_the_job": "badge-amber",
        "elearning": "badge-green",
        "vendor_external": "badge-slate",
        "blended": "badge-info",
    }

    ASSESSMENT_METHOD_CSS = {
        "written_exam": "badge-info",
        "practical_ojt": "badge-amber",
        "attendance_only": "badge-muted",
        "both_exam_and_ojt": "badge-green",
        "manager_evaluation": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "under_revision": "badge-amber",
        "retired": "badge-muted",
    }

    title = models.CharField(max_length=255, help_text="e.g. SOP-0042 Aseptic Gowning and Cleanroom Entry Protocol")
    competency_matrix = models.ForeignKey(
        "quality.CompetencyMatrix",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )
    course_code = models.CharField(max_length=64, blank=True, help_text="Internal course code or catalog ID")
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default="technical_sop", db_index=True)
    delivery_method = models.CharField(max_length=24, choices=DELIVERY_METHOD_CHOICES, default="read_and_understand", db_index=True)
    assessment_method = models.CharField(max_length=24, choices=ASSESSMENT_METHOD_CHOICES, default="written_exam", db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft", db_index=True)

    controlled_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_training_courses",
    )
    document_revision = models.CharField(max_length=32, blank=True, help_text="Document revision number e.g. Rev C")
    retrain_on_revision = models.BooleanField(
        default=True,
        help_text="Trigger automated retraining assignments when bound SOP document is revised",
    )
    duration_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.00,
        help_text="Course duration in hours e.g. 2.50",
    )
    passing_score = models.PositiveSmallIntegerField(default=80, help_text="Minimum passing percentage e.g. 80")
    ojt_checklist_criteria = models.TextField(blank=True, help_text="Structured practical evaluation checklist for OJT evaluations")
    syllabus_summary = models.TextField(blank=True, help_text="Learning objectives, syllabus topics, and reference materials")

    external_provider = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provided_quality_courses",
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructed_quality_courses",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Quality Training Course"
        verbose_name_plural = "Quality Training Courses"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcrs_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcrs_ten_status"),
            models.Index(fields=["tenant", "category"], name="idx_qcrs_ten_cat"),
            models.Index(fields=["tenant", "delivery_method"], name="idx_qcrs_ten_delivery"),
            models.Index(fields=["tenant", "assessment_method"], name="idx_qcrs_ten_assess"),
            models.Index(fields=["tenant", "competency_matrix"], name="idx_qcrs_ten_matrix"),
            models.Index(fields=["tenant", "controlled_document"], name="idx_qcrs_ten_cdoc"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcrs_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def category_badge(self):
        return self.CATEGORY_CSS.get(self.category, "badge-slate")

    @property
    def delivery_badge(self):
        return self.DELIVERY_METHOD_CSS.get(self.delivery_method, "badge-slate")

    @property
    def assessment_badge(self):
        return self.ASSESSMENT_METHOD_CSS.get(self.assessment_method, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def enrollments_count(self):
        return self.enrollments.count()

    @property
    def active_enrollments_count(self):
        return self.enrollments.filter(status__in=["assigned", "in_progress"]).count()

    @property
    def completed_enrollments_count(self):
        return self.enrollments.filter(status__in=["completed", "verified"]).count()
