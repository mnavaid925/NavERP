"""Asset Knowledge Base, Lessons Learned & Failure RCA Article model (11.16)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetDocumentKnowledge._validators import (
    add_field_error,
    compute_uploaded_file_metadata,
    validate_contributing_factors,
    validate_dict_list_field,
    validate_tenant_fks,
)


class AssetKnowledgeArticle(TenantNumbered):
    """Structured failure analysis (5-Why / Fishbone 6M), troubleshooting guide, and lessons learned [AKBA]."""

    NUMBER_PREFIX = "AKBA"

    ARTICLE_TYPE_CHOICES = [
        ("rca_post_incident", "Post-Incident RCA"),
        ("lessons_learned", "Lessons Learned"),
        ("troubleshooting_guide", "Troubleshooting Guide"),
        ("failure_bulletin", "Failure Alert Bulletin"),
        ("oem_service_advisory", "OEM Service Advisory"),
        ("pm_optimization_note", "PM Optimization Note"),
    ]

    RCA_METHODOLOGY_CHOICES = [
        ("five_whys", "5-Why Analysis"),
        ("fishbone_ishikawa", "Fishbone / Ishikawa (6M)"),
        ("problem_cause_remedy", "Problem-Cause-Remedy"),
        ("fmea_feedback", "FMEA Feedback Loop"),
        ("fault_tree", "Fault Tree Analysis"),
        ("general_kb", "General Knowledge Base"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("peer_review", "Peer Review"),
        ("published", "Published"),
        ("retired", "Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "peer_review": "badge-amber",
        "published": "badge-green",
        "retired": "badge-muted",
    }

    SEVERITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    EDITABLE_STATUSES = {"draft", "peer_review"}
    LOCKED_STATUSES = {"published", "retired"}

    _TENANT_FK_FIELDS = (
        "author",
        "reviewed_by",
        "org_unit",
        "operational_asset",
        "fixed_asset",
        "asset_category",
        "asset_model",
        "failure_mode",
        "maintenance_request",
        "maintenance_log",
        "incident_report",
        "compliance_incident",
        "related_document",
        "recommended_procedure",
    )

    title = models.CharField(max_length=200)
    article_type = models.CharField(
        max_length=28, choices=ARTICLE_TYPE_CHOICES, default="lessons_learned"
    )
    rca_methodology = models.CharField(
        max_length=28, choices=RCA_METHODOLOGY_CHOICES, default="five_whys"
    )
    severity = models.CharField(
        max_length=16, choices=SEVERITY_CHOICES, default="medium"
    )

    symptom_problem = models.TextField()
    root_cause_summary = models.TextField(blank=True)
    five_whys = models.JSONField(default=list, blank=True)
    contributing_factors = models.JSONField(default=dict, blank=True)
    remedy_corrective_action = models.TextField(blank=True)
    preventive_lessons = models.TextField(blank=True)

    downtime_hours_impacted = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )
    recurrence_count = models.PositiveIntegerField(default=1)
    tags = models.CharField(max_length=255, blank=True)

    helpful_votes = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)

    attachment = models.FileField(
        upload_to="assets/knowledge/%Y/%m/", blank=True, null=True
    )
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    file_checksum = models.CharField(max_length=64, blank=True, editable=False)

    incident_occurred_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", editable=False
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="authored_asset_kb_articles",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="reviewed_asset_kb_articles",
    )
    published_at = models.DateTimeField(null=True, blank=True, editable=False)

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    failure_mode = models.ForeignKey(
        "assets.AssetFailureMode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    maintenance_log = models.ForeignKey(
        "assets.AssetMaintenanceLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    incident_report = models.ForeignKey(
        "assets.AssetIncidentReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    compliance_incident = models.ForeignKey(
        "assets.AssetComplianceIncident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_knowledge_articles",
    )
    related_document = models.ForeignKey(
        "assets.AssetDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_articles",
    )
    recommended_procedure = models.ForeignKey(
        "assets.AssetOperatingProcedure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_articles",
    )

    class Meta:
        ordering = ["-published_at", "-updated_at", "-number"]
        verbose_name = "Asset Knowledge Article"
        verbose_name_plural = "Asset Knowledge Articles"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_akba_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_akba_ten_stat"),
            models.Index(fields=["tenant", "article_type"], name="idx_akba_ten_type"),
            models.Index(fields=["tenant", "severity"], name="idx_akba_ten_sev"),
            models.Index(fields=["tenant", "rca_methodology"], name="idx_akba_ten_rca"),
            models.Index(fields=["tenant", "operational_asset"], name="idx_akba_ten_ast"),
            models.Index(
                fields=["tenant", "-published_at", "-updated_at"],
                name="idx_akba_ten_pub_upd",
            ),
            models.Index(fields=["tenant", "failure_mode"], name="idx_akba_ten_fm"),
        ]

    def __str__(self):
        if self.number:
            return f"{self.number} \u00b7 {self.title}"
        return self.title

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def severity_badge_class(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def tag_list(self):
        return [tag.strip() for tag in (self.tags or "").split(",") if tag.strip()]

    def sync_attachment_metadata(self):
        """Capture RCA evidence filename and SHA-256 checksum."""
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
        if (
            self.downtime_hours_impacted is not None
            and self.downtime_hours_impacted < Decimal("0.00")
        ):
            add_field_error(
                errors,
                "downtime_hours_impacted",
                "Downtime hours impacted cannot be negative.",
            )
        if self.recurrence_count is not None and self.recurrence_count < 1:
            add_field_error(
                errors,
                "recurrence_count",
                "Recurrence count must be at least 1.",
            )
        validate_dict_list_field(
            self.five_whys,
            errors,
            "five_whys",
            max_items=10,
            label="5-Why entries",
        )
        validate_contributing_factors(
            self.contributing_factors, errors, field_name="contributing_factors"
        )
        validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.sync_attachment_metadata()
        super().save(*args, **kwargs)
