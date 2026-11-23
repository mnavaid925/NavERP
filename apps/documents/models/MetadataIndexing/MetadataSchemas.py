import json
from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class MetadataSchema(TenantNumbered):
    """
    Sub-module 13.5 Metadata & Indexing: Custom Metadata Schema
    Defines reusable metadata property specifications (content types) with typed fields,
    validation rules, and folder-level inheritance cascade policies.
    """
    NUMBER_PREFIX = "DSCH"

    TARGET_TYPE_CHOICES = [
        ("all", "All Document Types"),
        ("contract", "Legal Contracts & Agreements"),
        ("policy", "Corporate Policies & Governance"),
        ("sop", "Standard Operating Procedures (SOP)"),
        ("financial", "Financial Invoices & Reports"),
        ("technical", "Technical Specifications & Manuals"),
        ("hr", "Human Resources & Personnel Records"),
        ("procurement", "Procurement & Vendor Documents"),
    ]

    INHERITANCE_MODE_CHOICES = [
        ("none", "No Inheritance"),
        ("folder_default", "Folder Default (Optional)"),
        ("folder_strict", "Folder Cascade (Strict)"),
        ("template", "Document Template Inheritance"),
    ]

    TARGET_TYPE_CSS = {
        "all": "badge-info",
        "contract": "badge-amber",
        "policy": "badge-slate",
        "sop": "badge-green",
        "financial": "badge-green",
        "technical": "badge-info",
        "hr": "badge-amber",
        "procurement": "badge-slate",
    }

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, help_text="Unique schema code e.g. NDA_SCHEMA")
    description = models.TextField(blank=True)
    target_type = models.CharField(max_length=40, choices=TARGET_TYPE_CHOICES, default="all", db_index=True)
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="metadata_schemas",
    )
    target_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="metadata_schemas",
    )
    fields_definition_json = models.TextField(
        default="[]",
        help_text="JSON list of field definitions: [{'key': 'contract_value', 'label': 'Value', 'data_type': 'decimal', 'required': True}]",
    )
    inheritance_mode = models.CharField(
        max_length=25,
        choices=INHERITANCE_MODE_CHOICES,
        default="folder_default",
        db_index=True,
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Mandatory schema completion before document publish",
    )
    allow_custom_fields = models.BooleanField(
        default=True,
        help_text="Allow ad-hoc key-value additions",
    )
    version_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_metadata_schemas",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Metadata Schema"
        verbose_name_plural = "Metadata Schemas"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dsch_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "code"], name="doc_dsch_tnt_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "target_type", "is_active"], name="doc_dsch_tnt_tgt_act_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def target_type_badge(self):
        return self.TARGET_TYPE_CSS.get(self.target_type, "badge-info")

    @property
    def status_badge(self):
        return "badge-green" if self.is_active else "badge-slate"

    @property
    def parsed_fields(self):
        try:
            val = json.loads(self.fields_definition_json)
            return val if isinstance(val, list) else []
        except (ValueError, TypeError):
            return []
