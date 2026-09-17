"""Projects 7.12 Portfolio & Program Management — ProgramDependency [PDEP-].

Realizes NavERP 7.12 bullet 2 Program Dependency Mapping (cross-project dependency edges).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProgramDependency(TenantNumbered):
    NUMBER_PREFIX = "PDEP"

    DEPENDENCY_TYPE_CHOICES = [
        ("finish_to_start", "Finish to Start (FS)"),
        ("start_to_start", "Start to Start (SS)"),
        ("shared_resource", "Shared Resource"),
        ("deliverable_handover", "Deliverable Handover"),
        ("governance_gate", "Governance Gate"),
    ]

    CRITICALITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("mitigated", "Mitigated"),
        ("cleared", "Cleared"),
        ("waived", "Waived"),
    ]

    source_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="outgoing_program_dependencies",
        help_text="Predecessor project.",
    )
    target_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="incoming_program_dependencies",
        help_text="Successor project that depends on the predecessor.",
    )
    program = models.ForeignKey(
        "projects.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependencies",
    )
    dependency_type = models.CharField(
        max_length=25, choices=DEPENDENCY_TYPE_CHOICES, default="finish_to_start"
    )
    criticality = models.CharField(
        max_length=10, choices=CRITICALITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")
    lead_lag_days = models.IntegerField(default=0, help_text="Lead (negative) or lag (positive) days.")
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    cleared_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "source_project"], name="pdep_tnt_source_idx"),
            models.Index(fields=["tenant", "target_project"], name="pdep_tnt_target_idx"),
            models.Index(fields=["tenant", "status"], name="pdep_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.source_project.name} → {self.target_project.name}"

    def clean(self):
        super().clean()
        if self.source_project_id and self.target_project_id:
            if self.source_project_id == self.target_project_id:
                raise ValidationError("A project cannot have a dependency on itself.")
            if self.tenant_id:
                if self.source_project.tenant_id != self.tenant_id:
                    raise ValidationError("Source project belongs to a different workspace.")
                if self.target_project.tenant_id != self.tenant_id:
                    raise ValidationError("Target project belongs to a different workspace.")
