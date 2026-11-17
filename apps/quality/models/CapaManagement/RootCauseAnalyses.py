from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class RootCauseAnalysis(TenantNumbered):
    NUMBER_PREFIX = "QRCA"

    RCA_METHOD_CHOICES = (
        ("5_whys", "5 Whys Root Cause Ladder"),
        ("fishbone_ishikawa", "Ishikawa 6M Fishbone Diagram"),
        ("8d", "8 Disciplines (8D) Problem Solving"),
        ("fault_tree", "Fault Tree Analysis (FTA)"),
        ("barrier_analysis", "Barrier / Escape Point Analysis"),
        ("other", "Other Systematic Methodology"),
    )

    ROOT_CAUSE_CATEGORY_CHOICES = (
        ("design", "Design / Specification Defect"),
        ("process", "Manufacturing / Operational Process"),
        ("supplier", "Supplier / Raw Material Variation"),
        ("equipment", "Equipment / Tooling / Calibration"),
        ("human_error", "Human Performance / Ergonomics"),
        ("documentation", "SOP / Work Instruction Inadequacy"),
        ("training", "Training / Qualification Deficit"),
        ("environmental", "Cleanroom / Environmental Condition"),
        ("software", "Software / Firmware Anomaly"),
        ("other", "Other Root Cause"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft Investigation"),
        ("in_progress", "Analysis In Progress"),
        ("completed", "Analysis Completed"),
        ("verified", "Verified by Quality Engineering"),
        ("rejected", "Rejected / Inconclusive"),
    )

    RCA_METHOD_CSS = {
        "5_whys": "badge-info",
        "fishbone_ishikawa": "badge-purple",
        "8d": "badge-amber",
        "fault_tree": "badge-slate",
        "barrier_analysis": "badge-info",
        "other": "badge-slate",
    }

    ROOT_CAUSE_CATEGORY_CSS = {
        "design": "badge-purple",
        "process": "badge-info",
        "supplier": "badge-amber",
        "equipment": "badge-slate",
        "human_error": "badge-amber",
        "documentation": "badge-slate",
        "training": "badge-info",
        "environmental": "badge-slate",
        "software": "badge-purple",
        "other": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_progress": "badge-info",
        "completed": "badge-amber",
        "verified": "badge-green",
        "rejected": "badge-red",
    }

    capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.CASCADE,
        related_name="root_cause_analyses"
    )
    rca_method = models.CharField(max_length=32, choices=RCA_METHOD_CHOICES, default="5_whys", db_index=True)
    problem_statement = models.TextField(help_text="Concise description of the specific failure mode or defect to investigate")

    why_1 = models.CharField(max_length=500, blank=True)
    why_2 = models.CharField(max_length=500, blank=True)
    why_3 = models.CharField(max_length=500, blank=True)
    why_4 = models.CharField(max_length=500, blank=True)
    why_5 = models.CharField(max_length=500, blank=True)

    fishbone_manpower = models.TextField(blank=True, help_text="Personnel, training, operator ergonomics, human factor contributors")
    fishbone_machine = models.TextField(blank=True, help_text="Equipment, tooling, calibration, maintenance, hardware factors")
    fishbone_material = models.TextField(blank=True, help_text="Raw material, component defect, supplier variation")
    fishbone_method = models.TextField(blank=True, help_text="Procedures, work instructions, process parameters, test methods")
    fishbone_measurement = models.TextField(blank=True, help_text="Gauge error, inspection accuracy, measurement resolution")
    fishbone_environment = models.TextField(blank=True, help_text="Cleanroom conditions, temperature, humidity, ESD, contamination")

    root_cause_category = models.CharField(max_length=32, choices=ROOT_CAUSE_CATEGORY_CHOICES, default="process", db_index=True)
    root_cause_summary = models.TextField(help_text="Defensible synthesis of the primary root cause supported by physical/data evidence")
    escape_point_gap = models.TextField(blank=True, help_text="Analysis of why existing inspection/containment barriers failed to detect the defect")

    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)
    lead_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conducted_rcas"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_rcas"
    )
    verified_date = models.DateField(null=True, blank=True)
    verification_notes = models.TextField(blank=True, help_text="Quality engineering verification of investigation adequacy")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Root Cause Analysis"
        verbose_name_plural = "Root Cause Analyses"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrca_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "capa"], name="idx_qrca_ten_capa"),
            models.Index(fields=["tenant", "rca_method"], name="idx_qrca_ten_method"),
            models.Index(fields=["tenant", "root_cause_category"], name="idx_qrca_ten_rc_cat"),
            models.Index(fields=["tenant", "status"], name="idx_qrca_ten_status"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qrca_ten_created"),
        ]

    def __str__(self):
        return f"{self.number}: {self.get_rca_method_display()} ({self.capa.number})"

    @property
    def method_badge(self):
        return self.RCA_METHOD_CSS.get(self.rca_method, "badge-slate")

    @property
    def category_badge(self):
        return self.ROOT_CAUSE_CATEGORY_CSS.get(self.root_cause_category, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def why_levels_count(self):
        return sum(1 for w in [self.why_1, self.why_2, self.why_3, self.why_4, self.why_5] if w)

    @property
    def is_verified(self):
        return self.status == "verified" and self.verified_by is not None
