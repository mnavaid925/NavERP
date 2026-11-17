from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class DesignProject(TenantNumbered):
    NUMBER_PREFIX = "QDPL"

    DEVICE_CLASS_CHOICES = [
        ("class_i", "Class I (Low Risk)"),
        ("class_ii", "Class II (Moderate Risk - 510k)"),
        ("class_iii", "Class III (High Risk - PMA)"),
        ("class_a", "Class A (IVD Low Risk)"),
        ("class_b", "Class B (IVD Moderate Risk)"),
        ("class_c", "Class C (IVD High Risk)"),
        ("class_d", "Class D (High Public/Individual Risk)"),
        ("unclassified", "General Regulated / Unclassified"),
    ]

    REGULATORY_PATHWAY_CHOICES = [
        ("510k", "FDA 510(k) Premarket Notification"),
        ("pma", "FDA Premarket Approval (PMA)"),
        ("de_novo", "FDA De Novo Classification"),
        ("ce_mdr", "EU CE Mark (MDR 2017/745)"),
        ("ce_ivdr", "EU CE Mark (IVDR 2017/746)"),
        ("health_canada", "Health Canada MDEL / License"),
        ("exempt", "Exempt / Self-Declaration"),
        ("other", "Other Regulatory Pathway"),
    ]

    CURRENT_PHASE_CHOICES = [
        ("planning", "Phase 1: Design Planning"),
        ("input", "Phase 2: Design Inputs"),
        ("output_verification", "Phase 3: Design Output & Verification"),
        ("validation", "Phase 4: Design Validation & Transfer"),
        ("commercial_closure", "Phase 5: Commercial DHF Maintenance"),
        ("closed", "Closed / Transferred"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Scoping"),
        ("active", "Active Development"),
        ("gate_review", "Under Gate Review"),
        ("on_hold", "On Hold"),
        ("completed", "Completed / DHF Locked"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-info",
        "gate_review": "badge-amber",
        "on_hold": "badge-muted",
        "completed": "badge-green",
        "cancelled": "badge-red",
    }

    PHASE_CSS = {
        "planning": "badge-slate",
        "input": "badge-info",
        "output_verification": "badge-amber",
        "validation": "badge-info",
        "commercial_closure": "badge-green",
        "closed": "badge-muted",
    }

    DEVICE_CLASS_CSS = {
        "class_i": "badge-slate",
        "class_ii": "badge-info",
        "class_iii": "badge-red",
        "class_a": "badge-slate",
        "class_b": "badge-info",
        "class_c": "badge-amber",
        "class_d": "badge-red",
        "unclassified": "badge-muted",
    }

    title = models.CharField(max_length=255)
    device_name = models.CharField(max_length=200, help_text="Commercial or code name of the medical device / product")
    device_class = models.CharField(max_length=24, choices=DEVICE_CLASS_CHOICES, default="class_ii")
    regulatory_pathway = models.CharField(max_length=24, choices=REGULATORY_PATHWAY_CHOICES, default="510k")
    intended_use = models.TextField(help_text="Clinical intended use and indications for use per 21 CFR § 820.30(c)")
    current_phase = models.CharField(max_length=28, choices=CURRENT_PHASE_CHOICES, default="planning", db_index=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)
    project_lead = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="led_design_projects")
    quality_lead = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quality_design_projects")
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="design_projects")
    target_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    dhf_location = models.CharField(max_length=255, blank=True, help_text="DHF physical or digital repository path")
    dhf_locked = models.BooleanField(default=False, help_text="DHF frozen upon design transfer / commercial release")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Design Project"
        verbose_name_plural = "Design Projects"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qdpl_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qdpl_ten_status"),
            models.Index(fields=["tenant", "current_phase"], name="idx_qdpl_ten_phase"),
            models.Index(fields=["tenant", "device_class"], name="idx_qdpl_ten_dclass"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def phase_css(self):
        return self.PHASE_CSS.get(self.current_phase, "badge-slate")

    @property
    def device_class_css(self):
        return self.DEVICE_CLASS_CSS.get(self.device_class, "badge-slate")

    @property
    def is_locked(self):
        return self.dhf_locked or self.status in ("completed", "cancelled")
