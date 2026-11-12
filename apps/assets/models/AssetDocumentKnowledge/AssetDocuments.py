"""Controlled Asset Document & Version/Change Management model (11.16)."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetDocumentKnowledge._validators import (
    add_field_error,
    compute_uploaded_file_metadata,
    validate_supersedes_chain,
    validate_tenant_fks,
)


class AssetDocument(TenantNumbered):
    """Controlled asset manual, drawing, certificate, transmittal, and revision record [ADOC]."""

    NUMBER_PREFIX = "ADOC"

    DOCUMENT_CLASS_CHOICES = [
        ("manual", "OEM Operation & Service Manual"),
        ("schematic_pid", "P&ID / Process Schematic"),
        ("electrical_diagram", "Electrical / Wiring Diagram"),
        ("datasheet", "Technical Datasheet / Spec"),
        ("warranty_cert", "Warranty Certificate"),
        ("calibration_cert", "Calibration Certificate"),
        ("compliance_cert", "Regulatory / Safety Certificate"),
        ("inspection_dossier", "Inspection & NDT Dossier"),
        ("vendor_transmittal", "Vendor Submittal / Transmittal"),
        ("as_built_drawing", "As-Built Engineering Drawing"),
    ]

    ACCESS_CLASSIFICATION_CHOICES = [
        ("public_floor", "Shop Floor / Public"),
        ("internal_tech", "Internal Technical"),
        ("restricted_eng", "Restricted Engineering"),
        ("confidential", "Confidential / Vendor NDA"),
    ]

    CHANGE_TYPE_CHOICES = [
        ("new_issue", "Initial Controlled Issue"),
        ("drawing_redline", "Field Drawing Redline"),
        ("spec_update", "Engineering Spec Update"),
        ("vendor_bulletin", "OEM Service Bulletin"),
        ("regulatory_update", "Regulatory Compliance Update"),
        ("as_built_reconcile", "As-Built Reconciliation"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_review", "In Review"),
        ("approved", "Approved / Released"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "approved": "badge-green",
        "superseded": "badge-muted",
        "archived": "badge-muted",
    }

    ACCESS_CLASSIFICATION_CSS = {
        "public_floor": "badge-green",
        "internal_tech": "badge-info",
        "restricted_eng": "badge-amber",
        "confidential": "badge-red",
    }

    EDITABLE_STATUSES = {"draft", "in_review"}
    LOCKED_STATUSES = {"approved", "superseded", "archived"}

    _TENANT_FK_FIELDS = (
        "supersedes",
        "checked_out_by",
        "owner",
        "reviewer",
        "approved_by",
        "org_unit",
        "operational_asset",
        "fixed_asset",
        "asset_model",
        "asset_category",
        "specification_template",
        "warranty",
        "compliance_framework",
        "vendor_party",
        "core_document",
    )

    title = models.CharField(max_length=200)
    document_class = models.CharField(
        max_length=32, choices=DOCUMENT_CLASS_CHOICES, default="manual"
    )
    access_classification = models.CharField(
        max_length=24, choices=ACCESS_CLASSIFICATION_CHOICES, default="internal_tech"
    )
    tag_code = models.CharField(max_length=80, blank=True)
    manufacturer_ref = models.CharField(max_length=120, blank=True)
    document_language = models.CharField(max_length=32, default="en")
    storage_location_ref = models.CharField(max_length=160, blank=True)

    file = models.FileField(upload_to="assets/documents/%Y/%m/", blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    file_size_bytes = models.PositiveBigIntegerField(default=0, editable=False)
    file_checksum = models.CharField(max_length=64, blank=True, editable=False)

    revision_label = models.CharField(max_length=24, default="Rev A")
    revision_sequence = models.PositiveIntegerField(default=1, editable=False)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by_revisions",
    )
    is_current_revision = models.BooleanField(default=True, editable=False)
    change_request_ref = models.CharField(max_length=64, blank=True)
    change_type = models.CharField(
        max_length=24, choices=CHANGE_TYPE_CHOICES, default="new_issue"
    )
    redline_summary = models.TextField(blank=True)
    spec_delta_notes = models.TextField(blank=True)

    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="checked_out_asset_documents",
    )
    checked_out_at = models.DateTimeField(null=True, blank=True, editable=False)

    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    retention_years = models.PositiveSmallIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", editable=False
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="owned_asset_documents",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_asset_documents",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="approved_asset_documents",
    )
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_notes = models.TextField(blank=True)
    description = models.TextField(blank=True)

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    specification_template = models.ForeignKey(
        "assets.AssetSpecificationTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    warranty = models.ForeignKey(
        "assets.AssetWarranty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    compliance_framework = models.ForeignKey(
        "assets.AssetComplianceFramework",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_documents",
    )
    vendor_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_asset_documents",
    )
    core_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_document_records",
    )

    class Meta:
        ordering = ["-updated_at", "-number"]
        verbose_name = "Asset Document"
        verbose_name_plural = "Asset Documents"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_adoc_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_adoc_ten_stat"),
            models.Index(fields=["tenant", "document_class"], name="idx_adoc_ten_cls"),
            models.Index(fields=["tenant", "operational_asset"], name="idx_adoc_ten_ast"),
            models.Index(fields=["tenant", "expiry_date"], name="idx_adoc_ten_exp"),
            models.Index(fields=["tenant", "is_current_revision"], name="idx_adoc_ten_cur"),
            models.Index(fields=["tenant", "-updated_at"], name="idx_adoc_ten_upd"),
            models.Index(
                fields=["tenant", "status", "is_current_revision"],
                name="idx_adoc_ten_st_cur",
            ),
            models.Index(
                fields=["tenant", "access_classification"], name="idx_adoc_ten_acc"
            ),
            models.Index(fields=["tenant", "change_type"], name="idx_adoc_ten_chg"),
            models.Index(fields=["tenant", "asset_category"], name="idx_adoc_ten_cat"),
            models.Index(fields=["tenant", "org_unit"], name="idx_adoc_ten_org"),
        ]

    def __str__(self):
        if self.number:
            return f"{self.number} \u00b7 {self.title} ({self.revision_label})"
        return self.title

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def access_classification_badge_class(self):
        return self.ACCESS_CLASSIFICATION_CSS.get(
            self.access_classification, "badge-slate"
        )

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.localdate()

    @property
    def is_expiring_soon(self):
        if not self.expiry_date or self.is_expired:
            return False
        return self.expiry_date <= timezone.localdate() + timedelta(days=30)

    @property
    def short_checksum(self):
        return self.file_checksum[:12] if self.file_checksum else ""

    def sync_file_metadata(self):
        """Capture filename, byte size, and SHA-256 checksum for uploaded attachments."""
        if not self.file or not getattr(self.file, "name", ""):
            self.original_filename = ""
            self.file_size_bytes = 0
            self.file_checksum = ""
            return
        if not getattr(self.file, "_committed", True) or not self.file_checksum:
            orig_name, size_bytes, checksum = compute_uploaded_file_metadata(self.file)
            if orig_name:
                self.original_filename = orig_name
            self.file_size_bytes = size_bytes
            if checksum:
                self.file_checksum = checksum

    def clean(self):
        super().clean()
        errors = {}
        validate_supersedes_chain(self, errors, field_name="supersedes")
        if self.effective_date and self.expiry_date and self.expiry_date < self.effective_date:
            add_field_error(
                errors,
                "expiry_date",
                "Expiry date cannot be earlier than the effective date.",
            )
        if self.revision_sequence is not None and self.revision_sequence < 1:
            add_field_error(
                errors,
                "revision_sequence",
                "Revision sequence must be at least 1.",
            )
        if self.retention_years is not None and self.retention_years < 1:
            add_field_error(
                errors,
                "retention_years",
                "Retention period must be at least 1 year when specified.",
            )
        validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.sync_file_metadata()
        super().save(*args, **kwargs)
