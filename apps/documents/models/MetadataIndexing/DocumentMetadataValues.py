from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentMetadataValue(TenantNumbered):
    """
    Sub-module 13.5 Metadata & Indexing: Document Metadata Value
    Stores concrete property key-value instances bound to a Document or DocumentVersion,
    supporting heterogeneous types, inheritance source tracking, and schema validation.
    """
    NUMBER_PREFIX = "DMETA"

    DATA_TYPE_CHOICES = [
        ("text", "Text / String"),
        ("textarea", "Long Text / Paragraph"),
        ("integer", "Integer Number"),
        ("decimal", "Decimal / Currency"),
        ("date", "Calendar Date"),
        ("datetime", "Date & Timestamp"),
        ("boolean", "Boolean Flag (Yes/No)"),
        ("dropdown", "Dropdown Single-Select"),
        ("multi_select", "Multi-Select Tags"),
        ("json", "Structured JSON Object"),
    ]

    SOURCE_CHOICES = [
        ("manual_entry", "Manual User Entry"),
        ("folder_inherited", "Inherited from Folder"),
        ("template_inherited", "Inherited from Template"),
        ("ai_extracted", "AI / OCR Extracted"),
        ("bulk_updated", "Bulk Batch Updated"),
    ]

    VALIDATION_STATUS_CHOICES = [
        ("valid", "Valid & Conforming"),
        ("invalid", "Validation Failed"),
        ("pending_validation", "Pending Verification"),
    ]

    DATA_TYPE_CSS = {
        "text": "badge-info",
        "textarea": "badge-info",
        "integer": "badge-slate",
        "decimal": "badge-green",
        "date": "badge-amber",
        "datetime": "badge-amber",
        "boolean": "badge-slate",
        "dropdown": "badge-info",
        "multi_select": "badge-info",
        "json": "badge-slate",
    }

    SOURCE_CSS = {
        "manual_entry": "badge-slate",
        "folder_inherited": "badge-info",
        "template_inherited": "badge-info",
        "ai_extracted": "badge-amber",
        "bulk_updated": "badge-muted",
    }

    VALIDATION_STATUS_CSS = {
        "valid": "badge-green",
        "invalid": "badge-red",
        "pending_validation": "badge-amber",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="metadata_values",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="metadata_values",
    )
    schema = models.ForeignKey(
        "documents.MetadataSchema",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="metadata_values",
    )
    field_name = models.CharField(max_length=100, db_index=True)
    field_label = models.CharField(max_length=150, blank=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default="text")
    value_text = models.TextField(blank=True)
    value_number = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_json = models.TextField(blank=True, default="")
    source = models.CharField(max_length=25, choices=SOURCE_CHOICES, default="manual_entry", db_index=True)
    is_overridden = models.BooleanField(default=False, help_text="True if inherited value was modified manually")
    validation_status = models.CharField(max_length=25, choices=VALIDATION_STATUS_CHOICES, default="valid", db_index=True)
    validation_error = models.TextField(blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_metadata_values",
    )

    class Meta:
        ordering = ["document", "field_name"]
        verbose_name = "Document Metadata Value"
        verbose_name_plural = "Document Metadata Values"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dmeta_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "document", "version", "field_name"], name="doc_dmeta_tnt_doc_fld_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "document", "field_name"],
                condition=models.Q(version__isnull=True),
                name="doc_dmeta_tnt_doc_fld_nullver_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "validation_status"], name="doc_dmeta_tnt_doc_val_idx"),
            models.Index(fields=["tenant", "field_name"], name="doc_dmeta_tnt_fld_idx"),
            models.Index(fields=["tenant", "data_type"], name="doc_dmeta_tnt_dtype_idx"),
            models.Index(fields=["tenant", "validation_status"], name="doc_dmeta_tnt_vstat_idx"),
            models.Index(fields=["tenant", "source"], name="doc_dmeta_tnt_src_idx"),
        ]

    def __str__(self):
        return f"{self.document.title} :: {self.field_name} = {self.display_value}"

    @property
    def display_value(self):
        if self.data_type in ["integer", "decimal"] and self.value_number is not None:
            return str(self.value_number)
        elif self.data_type in ["date", "datetime"] and self.value_date is not None:
            return str(self.value_date)
        elif self.data_type == "boolean" and self.value_boolean is not None:
            return "Yes" if self.value_boolean else "No"
        elif self.data_type == "json" and self.value_json:
            return self.value_json[:80] + ("..." if len(self.value_json) > 80 else "")
        return self.value_text or "—"

    @property
    def data_type_badge(self):
        return self.DATA_TYPE_CSS.get(self.data_type, "badge-info")

    @property
    def source_badge(self):
        return self.SOURCE_CSS.get(self.source, "badge-slate")

    @property
    def validation_status_badge(self):
        return self.VALIDATION_STATUS_CSS.get(self.validation_status, "badge-slate")
