from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class DesignInput(TenantNumbered):
    NUMBER_PREFIX = "QINP"

    INPUT_TYPE_CHOICES = [
        ("user_need", "User Need / Clinical Need"),
        ("functional", "Functional Specification"),
        ("performance", "Performance Requirement"),
        ("safety", "Safety & Inherent Protection"),
        ("regulatory", "Regulatory Standard Mandate"),
        ("human_factors", "Human Factors & Usability"),
        ("software", "Software Requirement (IEC 62304)"),
        ("interface", "Interface & Physical Fit"),
        ("packaging", "Packaging & Sterility Requirement"),
    ]

    PRIORITY_CHOICES = [
        ("critical", "Critical (Must-Have)"),
        ("major", "Major (Essential)"),
        ("minor", "Minor (Desirable)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_review", "In Review"),
        ("approved", "Approved / Frozen"),
        ("verified", "Verified & Satisfied"),
        ("deferred", "Deferred"),
        ("obsolete", "Obsolete / Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "approved": "badge-info",
        "verified": "badge-green",
        "deferred": "badge-muted",
        "obsolete": "badge-red",
    }

    PRIORITY_CSS = {
        "critical": "badge-red",
        "major": "badge-amber",
        "minor": "badge-slate",
    }

    INPUT_TYPE_CSS = {
        "user_need": "badge-purple",
        "functional": "badge-info",
        "performance": "badge-green",
        "safety": "badge-red",
        "regulatory": "badge-amber",
        "human_factors": "badge-info",
        "software": "badge-blue",
        "interface": "badge-slate",
        "packaging": "badge-slate",
    }

    project = models.ForeignKey("quality.DesignProject", on_delete=models.CASCADE, related_name="inputs")
    identifier = models.CharField(max_length=50, help_text="Engineering item identifier, e.g. UN-001, DI-001")
    title = models.CharField(max_length=255)
    input_type = models.CharField(max_length=24, choices=INPUT_TYPE_CHOICES, default="functional", db_index=True)
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default="major")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    description = models.TextField(help_text="Unambiguous, objective, testable requirement statement")
    acceptance_criteria = models.TextField(help_text="Quantitative or qualitative criteria for verification")
    rationale = models.TextField(blank=True, help_text="Clinical, regulatory, or engineering rationale")
    user_need_parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="derived_inputs", help_text="Parent User Need this requirement derives from")
    controlled_document = models.ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="design_inputs", help_text="Source specification or SOP in Document Control")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_design_inputs")
    version = models.CharField(max_length=20, default="1.0")

    class Meta:
        ordering = ["project", "identifier", "-created_at"]
        verbose_name = "Design Input"
        verbose_name_plural = "Design Inputs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qinp_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "project"], name="idx_qinp_ten_project"),
            models.Index(fields=["tenant", "input_type"], name="idx_qinp_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_qinp_ten_status"),
        ]

    def __str__(self):
        return f"{self.identifier} ({self.number}) — {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def priority_css(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-slate")

    @property
    def input_type_css(self):
        return self.INPUT_TYPE_CSS.get(self.input_type, "badge-slate")

    @property
    def is_verified(self):
        if self.status == "verified":
            return True
        if hasattr(self, "_prefetched_objects_cache") and "verifications" in self._prefetched_objects_cache:
            return any(v.pass_fail_result == "pass" for v in self.verifications.all())
        return self.verifications.filter(pass_fail_result="pass").exists()
