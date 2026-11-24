from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models._base import TenantNumbered
from apps.documents.models.VersionControl.Documents import Document


class DocumentRoutingRule(TenantNumbered):
    """Priority-ordered document routing, conditional logic, validation gate, and autofill rule."""

    NUMBER_PREFIX = "DRUL"

    RULE_TYPE_CHOICES = (
        ("routing_distribution", "Document Routing & Distribution"),
        ("conditional_branch", "Conditional Branching Rule"),
        ("metadata_autofill", "Metadata Auto-Population"),
        ("data_validation", "Data Validation Gate"),
        ("escalation_fallback", "Fallback & Escalation Routing"),
        ("lifecycle_transition", "Lifecycle Status Transition"),
    )

    TRIGGER_EVENT_CHOICES = (
        ("on_upload", "On Document Upload"),
        ("on_metadata_change", "On Metadata Updated"),
        ("on_ocr_complete", "On OCR Extraction Completed"),
        ("on_status_change", "On Document Status Changed"),
        ("on_approval_decision", "On Approval Decision"),
        ("on_manual_eval", "On Manual Rule Evaluation"),
    )

    CONDITION_LOGIC_CHOICES = (
        ("all_and", "All Conditions (AND)"),
        ("any_or", "Any Condition (OR)"),
    )

    ROUTE_ACTION_CHOICES = (
        ("move_to_folder", "File to Target Folder (Tags & Path)"),
        ("assign_role", "Route to Role Pool"),
        ("assign_user", "Assign Specific User"),
        ("assign_org_unit_head", "Route to Org Unit / Manager"),
        ("spawn_approval_workflow", "Spawn 13.3 Approval Workflow"),
        ("create_document_task", "Create 13.8 Document Task"),
        ("populate_metadata", "Auto-Populate Document & Metadata"),
        ("trigger_process", "Launch BPM Process Definition"),
        ("block_validation", "Validation Gate (Block on Fail)"),
    )

    TARGET_DOC_TYPE_CHOICES = [("", "All Document Types")] + list(Document.DOCUMENT_TYPE_CHOICES)
    TARGET_CLASSIFICATION_CHOICES = [("", "All Classifications")] + list(
        Document.CLASSIFICATION_CHOICES
    )

    SUPPORTED_OPERATORS = (
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "contains",
        "regex_match",
        "is_set",
        "is_empty",
    )

    RULE_TYPE_CSS = {
        "routing_distribution": "badge-info",
        "conditional_branch": "badge-amber",
        "metadata_autofill": "badge-green",
        "data_validation": "badge-red",
        "escalation_fallback": "badge-amber",
        "lifecycle_transition": "badge-slate",
    }

    ROUTE_ACTION_CSS = {
        "move_to_folder": "badge-info",
        "assign_role": "badge-slate",
        "assign_user": "badge-slate",
        "assign_org_unit_head": "badge-info",
        "spawn_approval_workflow": "badge-amber",
        "create_document_task": "badge-info",
        "populate_metadata": "badge-green",
        "trigger_process": "badge-green",
        "block_validation": "badge-red",
    }

    IS_ACTIVE_CSS = {
        True: "badge-green",
        False: "badge-slate",
    }

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    process_definition = models.ForeignKey(
        "documents.DocumentProcessDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    core_rule_ref = models.ForeignKey(
        "core.BusinessRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_routing_rules",
    )
    rule_type = models.CharField(
        max_length=40,
        choices=RULE_TYPE_CHOICES,
        default="routing_distribution",
        db_index=True,
    )
    trigger_event = models.CharField(
        max_length=40,
        choices=TRIGGER_EVENT_CHOICES,
        default="on_upload",
        db_index=True,
    )
    priority = models.PositiveIntegerField(default=100, db_index=True)
    source_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_routing_rules",
    )
    target_document_type = models.CharField(
        max_length=40,
        choices=TARGET_DOC_TYPE_CHOICES,
        blank=True,
    )
    target_classification = models.CharField(
        max_length=25,
        choices=TARGET_CLASSIFICATION_CHOICES,
        blank=True,
    )
    condition_logic_mode = models.CharField(
        max_length=20,
        choices=CONDITION_LOGIC_CHOICES,
        default="all_and",
    )
    conditions_json = models.JSONField(default=list, blank=True)
    else_branch_enabled = models.BooleanField(default=False)
    else_action_json = models.JSONField(default=dict, blank=True)
    validation_rules_json = models.JSONField(default=list, blank=True)
    auto_populate_json = models.JSONField(default=dict, blank=True)
    route_action = models.CharField(
        max_length=40,
        choices=ROUTE_ACTION_CHOICES,
        default="move_to_folder",
        db_index=True,
    )
    destination_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destination_routing_rules",
    )
    route_to_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_routing_rules",
    )
    route_to_role = models.ForeignKey(
        "accounts.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_routing_rules",
    )
    route_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_dms_routing_rules",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_dms_routing_rules",
    )
    execution_count = models.PositiveIntegerField(default=0, editable=False)
    match_count = models.PositiveIntegerField(default=0, editable=False)
    last_evaluated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Document Routing Rule"
        verbose_name_plural = "Document Routing Rules"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_drul_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "priority"], name="doc_drul_tnt_pri_idx"),
            models.Index(fields=["tenant", "rule_type"], name="doc_drul_tnt_typ_idx"),
            models.Index(fields=["tenant", "trigger_event"], name="doc_drul_tnt_trg_idx"),
            models.Index(fields=["tenant", "is_active"], name="doc_drul_tnt_act_idx"),
            models.Index(fields=["tenant", "process_definition"], name="doc_drul_tnt_prc_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} (P{self.priority})"

    def clean(self):
        super().clean()
        if self.priority < 1:
            raise ValidationError({"priority": "Rule priority must be >= 1."})

    @property
    def rule_type_badge(self):
        return self.RULE_TYPE_CSS.get(self.rule_type, "badge-slate")

    @property
    def route_action_badge(self):
        return self.ROUTE_ACTION_CSS.get(self.route_action, "badge-slate")

    @property
    def active_badge(self):
        return self.IS_ACTIVE_CSS.get(self.is_active, "badge-slate")

    @property
    def condition_count(self):
        return len(self.conditions_json) if isinstance(self.conditions_json, list) else 0

    @property
    def match_rate_pct(self):
        if not self.execution_count:
            return 0.0
        return round((self.match_count / self.execution_count) * 100, 1)
