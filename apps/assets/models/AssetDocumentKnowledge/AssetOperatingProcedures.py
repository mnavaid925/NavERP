"""Asset Operating Procedure (SOP & LOTO Isolation Protocol) model (11.16)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetDocumentKnowledge._validators import (
    add_field_error,
    compute_uploaded_file_metadata,
    validate_dict_list_field,
    validate_supersedes_chain,
    validate_tenant_fks,
)


class AssetOperatingProcedure(TenantNumbered):
    """Controlled Standard Operating Procedure, PM Protocol, and LOTO checklist [ASOP]."""

    NUMBER_PREFIX = "ASOP"

    PROCEDURE_TYPE_CHOICES = [
        ("sop_operation", "Standard Operating Procedure"),
        ("pm_protocol", "Preventive Maintenance Protocol"),
        ("loto_isolation", "Lockout / Tagout (LOTO) Isolation"),
        ("emergency_shutdown", "Emergency Shutdown & E-Stop"),
        ("commissioning", "Commissioning & Startup"),
        ("calibration_protocol", "Calibration Protocol"),
        ("inspection_checklist", "Safety Inspection Checklist"),
    ]

    SAFETY_LEVEL_CHOICES = [
        ("standard", "Standard Operations"),
        ("caution", "Caution — PPE Required"),
        ("high_hazard_loto", "High Hazard — LOTO Mandatory"),
        ("permit_required", "Permit-to-Work Required"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Safety Review"),
        ("active", "Active / Controlled"),
        ("superseded", "Superseded"),
        ("retired", "Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_review": "badge-amber",
        "active": "badge-green",
        "superseded": "badge-muted",
        "retired": "badge-muted",
    }

    SAFETY_CSS = {
        "standard": "badge-slate",
        "caution": "badge-info",
        "high_hazard_loto": "badge-red",
        "permit_required": "badge-amber",
    }

    EDITABLE_STATUSES = {"draft", "under_review"}
    LOCKED_STATUSES = {"active", "superseded", "retired"}

    _TENANT_FK_FIELDS = (
        "supersedes",
        "author",
        "safety_reviewer",
        "approved_by",
        "org_unit",
        "operational_asset",
        "asset_category",
        "asset_model",
        "maintenance_schedule",
        "compliance_framework",
        "primary_document",
    )

    title = models.CharField(max_length=200)
    procedure_type = models.CharField(
        max_length=28, choices=PROCEDURE_TYPE_CHOICES, default="sop_operation"
    )
    safety_level = models.CharField(
        max_length=24, choices=SAFETY_LEVEL_CHOICES, default="standard"
    )
    revision_label = models.CharField(max_length=24, default="Rev 1.0")
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by_procedures",
    )

    purpose_scope = models.TextField(blank=True)
    hazard_warnings = models.TextField(blank=True)
    required_ppe = models.CharField(max_length=255, blank=True)
    loto_required = models.BooleanField(default=False)
    loto_isolation_points = models.JSONField(default=list, blank=True)
    procedure_steps = models.JSONField(default=list, blank=True)
    required_qualification_code = models.CharField(max_length=64, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(default=30)

    attachment = models.FileField(
        upload_to="assets/procedures/%Y/%m/", blank=True, null=True
    )
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    file_checksum = models.CharField(max_length=64, blank=True, editable=False)

    effective_date = models.DateField(null=True, blank=True)
    review_cycle_months = models.PositiveSmallIntegerField(default=12)
    next_review_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", editable=False
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="authored_asset_procedures",
    )
    safety_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_reviewed_asset_procedures",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="approved_asset_procedures",
    )
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_notes = models.TextField(blank=True)

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operating_procedures",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operating_procedures",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operating_procedures",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operating_procedures",
    )
    maintenance_schedule = models.ForeignKey(
        "assets.AssetMaintenanceSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operating_procedures",
    )
    compliance_framework = models.ForeignKey(
        "assets.AssetComplianceFramework",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operating_procedures",
    )
    primary_document = models.ForeignKey(
        "assets.AssetDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operating_procedures",
    )

    class Meta:
        ordering = ["-updated_at", "-number"]
        verbose_name = "Asset Operating Procedure"
        verbose_name_plural = "Asset Operating Procedures"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_asop_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_asop_ten_stat"),
            models.Index(fields=["tenant", "procedure_type"], name="idx_asop_ten_type"),
            models.Index(fields=["tenant", "safety_level"], name="idx_asop_ten_haz"),
            models.Index(fields=["tenant", "next_review_date"], name="idx_asop_ten_rev"),
            models.Index(fields=["tenant", "-updated_at"], name="idx_asop_ten_upd"),
            models.Index(
                fields=["tenant", "status", "next_review_date"],
                name="idx_asop_ten_st_rev",
            ),
            models.Index(
                fields=["tenant", "operational_asset"], name="idx_asop_ten_ast"
            ),
            models.Index(fields=["tenant", "asset_category"], name="idx_asop_ten_cat"),
            models.Index(fields=["tenant", "loto_required"], name="idx_asop_ten_loto"),
        ]

    def __str__(self):
        if self.number:
            return f"{self.number} \u00b7 {self.title} ({self.revision_label})"
        return self.title

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def safety_badge_class(self):
        return self.SAFETY_CSS.get(self.safety_level, "badge-slate")

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def is_review_overdue(self):
        if not self.next_review_date or self.status != "active":
            return False
        return self.next_review_date < timezone.localdate()

    @property
    def step_count(self):
        return len(self.procedure_steps or [])

    @property
    def isolation_point_count(self):
        return len(self.loto_isolation_points or [])

    def sync_attachment_metadata(self):
        """Capture filename and SHA-256 checksum for SOP attachment uploads."""
        if not self.attachment or not getattr(self.attachment, "name", ""):
            self.original_filename = ""
            self.file_checksum = ""
            return
        if not getattr(self.attachment, "_committed", True) or not self.file_checksum:
            orig_name, _, checksum = compute_uploaded_file_metadata(self.attachment)
            if orig_name:
                self.original_filename = orig_name
            if checksum:
                self.file_checksum = checksum

    def clean(self):
        super().clean()
        errors = {}
        validate_supersedes_chain(self, errors, field_name="supersedes")
        if (
            self.estimated_duration_minutes is not None
            and self.estimated_duration_minutes < 1
        ):
            add_field_error(
                errors,
                "estimated_duration_minutes",
                "Estimated duration must be at least 1 minute.",
            )
        if self.review_cycle_months is not None and self.review_cycle_months < 1:
            add_field_error(
                errors,
                "review_cycle_months",
                "Review cycle must be at least 1 month.",
            )
        if (
            self.effective_date
            and self.next_review_date
            and self.next_review_date < self.effective_date
        ):
            add_field_error(
                errors,
                "next_review_date",
                "Next review date cannot precede the effective date.",
            )
        validate_dict_list_field(
            self.procedure_steps,
            errors,
            "procedure_steps",
            max_items=100,
            label="Procedure steps",
        )
        validate_dict_list_field(
            self.loto_isolation_points,
            errors,
            "loto_isolation_points",
            max_items=50,
            label="LOTO isolation points",
        )
        validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.sync_attachment_metadata()
        super().save(*args, **kwargs)
