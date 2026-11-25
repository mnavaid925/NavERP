from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models._base import TenantNumbered
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.services.workflow_automation import validate_process_graph


class DocumentProcessDefinition(TenantNumbered):
    """Reusable, versioned BPMN 2.0-style document workflow blueprint with swimlanes and gateways."""

    NUMBER_PREFIX = "DBPM"

    PROCESS_CATEGORY_CHOICES = (
        ("intake_triage", "Document Intake & Triage"),
        ("lifecycle_automation", "Lifecycle Automation"),
        ("compliance_routing", "Compliance & Policy Routing"),
        ("contract_review", "Contract Review Orchestration"),
        ("records_disposition", "Records & Disposition Automation"),
        ("ocr_classification", "OCR & Auto-Classification"),
        ("custom", "Custom BPM Process"),
    )

    TRIGGER_EVENT_CHOICES = (
        ("document_created", "Document Created"),
        ("version_uploaded", "New Version Uploaded"),
        ("status_changed", "Document Status Changed"),
        ("metadata_updated", "Metadata Value Updated"),
        ("ocr_completed", "OCR Extraction Completed"),
        ("approval_completed", "Approval Workflow Completed"),
        ("manual_trigger", "Manual / Operator Launch"),
        ("webhook_inbound", "Inbound Webhook Trigger"),
    )

    TARGET_DOCUMENT_TYPE_CHOICES = [("all", "All Document Types")] + list(
        Document.DOCUMENT_TYPE_CHOICES
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
        ("deprecated", "Deprecated"),
        ("archived", "Archived"),
    )

    STATUS_CSS = {
        "draft": "badge-slate",
        "published": "badge-green",
        "deprecated": "badge-amber",
        "archived": "badge-muted",
    }

    CATEGORY_CSS = {
        "intake_triage": "badge-info",
        "lifecycle_automation": "badge-green",
        "compliance_routing": "badge-amber",
        "contract_review": "badge-info",
        "records_disposition": "badge-red",
        "ocr_classification": "badge-slate",
        "custom": "badge-muted",
    }

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=60)
    description = models.TextField(blank=True)
    process_category = models.CharField(
        max_length=40,
        choices=PROCESS_CATEGORY_CHOICES,
        default="intake_triage",
        db_index=True,
    )
    trigger_event = models.CharField(
        max_length=40,
        choices=TRIGGER_EVENT_CHOICES,
        default="document_created",
        db_index=True,
    )
    target_document_type = models.CharField(
        max_length=40,
        choices=TARGET_DOCUMENT_TYPE_CHOICES,
        default="all",
        blank=True,
    )
    target_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_definitions",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_process_definitions",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_dms_process_definitions",
    )
    core_workflow_ref = models.ForeignKey(
        "core.WorkflowDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_process_definitions",
    )
    version_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sla_target_hours = models.PositiveIntegerField(default=48)
    swimlanes_json = models.JSONField(default=list, blank=True)
    nodes_json = models.JSONField(default=list, blank=True)
    transitions_json = models.JSONField(default=list, blank=True)
    instance_count = models.PositiveIntegerField(default=0, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["code", "-version_number"]
        verbose_name = "Document Process Definition"
        verbose_name_plural = "Document Process Definitions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dbpm_ten_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "code", "version_number"],
                name="doc_dbpm_tnt_cod_ver_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="doc_dbpm_tnt_sts_idx"),
            models.Index(fields=["tenant", "trigger_event"], name="doc_dbpm_tnt_trg_idx"),
            models.Index(fields=["tenant", "is_active"], name="doc_dbpm_tnt_act_idx"),
            models.Index(fields=["tenant", "process_category"], name="doc_dbpm_tnt_cat_idx"),
            models.Index(fields=["tenant", "department"], name="doc_dbpm_tnt_dpt_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} (v{self.version_number})"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
        if self.sla_target_hours is not None and self.sla_target_hours < 1:
            raise ValidationError({"sla_target_hours": "SLA target hours must be at least 1."})
        if self.version_number is not None and self.version_number < 1:
            raise ValidationError({"version_number": "Version number must be at least 1."})

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def category_badge(self):
        return self.CATEGORY_CSS.get(self.process_category, "badge-slate")

    @property
    def node_count(self):
        return len(self.nodes_json) if isinstance(self.nodes_json, list) else 0

    @property
    def transition_count(self):
        return len(self.transitions_json) if isinstance(self.transitions_json, list) else 0

    @property
    def swimlane_count(self):
        return len(self.swimlanes_json) if isinstance(self.swimlanes_json, list) else 0

    def validate_graph(self):
        return validate_process_graph(
            self.swimlanes_json or [],
            self.nodes_json or [],
            self.transitions_json or [],
        )
