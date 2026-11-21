from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class SystemChangeControl(TenantNumbered):
    NUMBER_PREFIX = "QCCR"

    CHANGE_TYPE_CHOICES = [
        ("software_patch", "Software Patch / Minor Update"),
        ("major_upgrade", "Major Software Version Upgrade"),
        ("cloud_saas_update", "Cloud / SaaS Vendor Release"),
        ("infrastructure_network", "Hardware, OS or Network Infrastructure"),
        ("configuration_rule", "System Configuration / Workflow Rule Change"),
        ("database_schema", "Database Schema / Data Migration"),
        ("security_patch", "Security Vulnerability Patch"),
        ("decommission", "System Retirement / Decommissioning"),
    ]

    GXP_IMPACT_CHOICES = [
        ("direct_gxp", "Direct GxP Impact (Product Quality / Patient Safety)"),
        ("indirect_gxp", "Indirect GxP Impact (Supporting Quality Data)"),
        ("non_gxp", "Non-GxP (Operational / Administrative Only)"),
    ]

    CHANGE_PRIORITY_CHOICES = [
        ("routine", "Routine Planned Change"),
        ("urgent", "Urgent / Business Critical"),
        ("emergency", "Emergency / Break-Fix Fix"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Proposal"),
        ("impact_assessment", "Impact Assessment & Validation Scoping"),
        ("ccb_review", "Change Control Board (CCB) Review"),
        ("approved_for_build", "Approved for Implementation & Testing"),
        ("testing_verification", "Testing & Verification In Progress"),
        ("qa_release_pending", "QA Final Release Authorization"),
        ("implemented_closed", "Implemented & Operational (Closed)"),
        ("rejected", "Change Proposal Rejected"),
        ("cancelled", "Cancelled / Backed Out"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "impact_assessment": "badge-info",
        "ccb_review": "badge-amber",
        "approved_for_build": "badge-info",
        "testing_verification": "badge-amber",
        "qa_release_pending": "badge-amber",
        "implemented_closed": "badge-green",
        "rejected": "badge-red",
        "cancelled": "badge-muted",
    }

    PRIORITY_CSS = {
        "routine": "badge-slate",
        "urgent": "badge-amber",
        "emergency": "badge-red",
    }

    GXP_IMPACT_CSS = {
        "direct_gxp": "badge-red",
        "indirect_gxp": "badge-amber",
        "non_gxp": "badge-slate",
    }

    title = models.CharField(max_length=255)
    system = models.ForeignKey(
        "quality.ComputerSystemValidation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_controls",
    )
    change_type = models.CharField(
        max_length=30, choices=CHANGE_TYPE_CHOICES, default="software_patch"
    )
    change_priority = models.CharField(
        max_length=20, choices=CHANGE_PRIORITY_CHOICES, default="routine", db_index=True
    )
    gxp_impact = models.CharField(
        max_length=20, choices=GXP_IMPACT_CHOICES, default="direct_gxp", db_index=True
    )
    requestor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_change_controls",
    )
    system_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_change_controls",
    )
    qa_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qa_change_controls",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_change_controls",
    )
    description = models.TextField()
    business_justification = models.TextField(blank=True)
    data_integrity_risk = models.TextField(
        blank=True, help_text="Impact on ALCOA+ principles or electronic records"
    )
    validation_deliverables = models.TextField(
        blank=True, help_text="Required test scripts, qualification protocols, or UAT sign-offs"
    )
    rollback_plan = models.TextField(
        blank=True, help_text="Contingency backout instructions if deployment fails"
    )
    target_date = models.DateField(null=True, blank=True)
    actual_implementation_date = models.DateField(null=True, blank=True)
    post_review_due_date = models.DateField(
        null=True, blank=True, help_text="Post-implementation periodic review due date"
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    testing_successful = models.BooleanField(default=False)
    data_backup_verified = models.BooleanField(default=False)
    ccb_approved = models.BooleanField(default=False)
    closure_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "System Change Control"
        verbose_name_plural = "System Change Controls"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qccr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "gxp_impact", "status"], name="idx_qccr_ten_gxp_stat"),
            models.Index(fields=["tenant", "change_priority", "status"], name="idx_qccr_ten_prio_stat"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_closed(self):
        return self.status == "implemented_closed"

    @property
    def is_emergency(self):
        return self.change_priority == "emergency"

    @property
    def is_overdue(self):
        return bool(
            self.target_date
            and self.target_date < timezone.now().date()
            and self.status not in ["implemented_closed", "rejected", "cancelled"]
        )
