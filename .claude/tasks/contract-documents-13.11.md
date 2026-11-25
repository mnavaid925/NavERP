# Module 13.11 Pre-Build Contract — Workflow Automation & BPM (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + exclusions, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.11"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0023_...`)
- **Package Directories**:
  - `apps/documents/models/WorkflowAutomation/`
  - `apps/documents/forms/WorkflowAutomation/`
  - `apps/documents/views/WorkflowAutomation/`
  - `apps/documents/urls/WorkflowAutomation/`
  - `apps/documents/services/workflow_automation.py`
  - `templates/documents/workflow_automation/{process_definition,routing_rule,process_instance,webhook_trigger}/{list,detail,form}.html` + `process_definition/designer.html` + `routing_rule/simulator.html` + `analytics_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"publish"`, `"deprecate"`, `"design"`, `"toggle"`, `"eval"`, `"trigger"`, `"advance"`, `"cancel"`, `"rotate"`, `"ping"`, `"inbound"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed stat-icon classes ONLY: `stat-icon blue`, `stat-icon green`, `stat-icon orange`, `stat-icon purple`, `stat-icon red`, `stat-icon slate` (NEVER `amber`).
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, 15)`).
  - Paginator guards `has_previous` / `has_next` / `paginator.num_pages` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - Every tenant-scoped queryset uses `documents_scope(Model.objects.all(), request)` or `.filter(tenant=request.tenant)`.
  - Every object fetch uses `documents_object(request, Model, pk, ...)`.
  - Forms inherit `TenantUniqueMixin, TenantModelForm`, filter all FK querysets by `tenant=self.tenant`, and enforce `reject_foreign(...)` in `clean()`.
  - List GET FK filters check `.isdigit()` before filtering (L11).
- **Reality Checks (L28/L36/L55)**:
  - `documents.Document` has NO `.folder` FK; `move_to_folder` appends `destination_folder.slug` to `document.tags`, sets `document.department = destination_folder.department` when unset, and upserts `DocumentMetadataValue` (`field_name="routed_folder_path"`, `version=None`, `source="bulk_updated"`).
  - `core.OrgUnit` has NO `.head` FK; `assign_org_unit_head` resolves active `core.Employment(tenant=tenant, org_unit=org_unit, status="active", manager__isnull=False).order_by("pk")` -> linked active `User` (`party=emp.manager`).
  - `DocumentAuditTrail` logging uses valid `DocumentAuditTrail.ACTION_TYPE_CHOICES` (`"moved"`, `"edited"`, `"created"`, `"workflow_approved"`, `"workflow_rejected"`) and stores BPM details in `details_json`.
  - Zero outbound HTTP (`requests`/`urllib`/`httpx`) in 13.11; webhooks record honest `"simulated"` delivery entries (L55).

---

## 1. Models & Choices Contract (`apps/documents/models/WorkflowAutomation/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentProcessDefinition` (`DocumentProcessDefinitions.py`)
- **`NUMBER_PREFIX`**: `"DBPM"`
- **`Meta.ordering`**: `["code", "-version_number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Process Definition"` / `"Document Process Definitions"`
- **Choices & Badge Maps**:
  - `PROCESS_CATEGORY_CHOICES` (`max_length=40`):
    - `("intake_triage", "Document Intake & Triage")`
    - `("lifecycle_automation", "Lifecycle Automation")`
    - `("compliance_routing", "Compliance & Policy Routing")`
    - `("contract_review", "Contract Review Orchestration")`
    - `("records_disposition", "Records & Disposition Automation")`
    - `("ocr_classification", "OCR & Auto-Classification")`
    - `("custom", "Custom BPM Process")`
  - `TRIGGER_EVENT_CHOICES` (`max_length=40`):
    - `("document_created", "Document Created")`
    - `("version_uploaded", "New Version Uploaded")`
    - `("status_changed", "Document Status Changed")`
    - `("metadata_updated", "Metadata Value Updated")`
    - `("ocr_completed", "OCR Extraction Completed")`
    - `("approval_completed", "Approval Workflow Completed")`
    - `("manual_trigger", "Manual / Operator Launch")`
    - `("webhook_inbound", "Inbound Webhook Trigger")`
  - `TARGET_DOCUMENT_TYPE_CHOICES` (`max_length=40`):
    - `[("all", "All Document Types")] + list(Document.DOCUMENT_TYPE_CHOICES)`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("published", "Published")`
    - `("deprecated", "Deprecated")`
    - `("archived", "Archived")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"published": "badge-green"`, `"deprecated": "badge-amber"`, `"archived": "badge-muted"`
  - `CATEGORY_CSS`:
    - `"intake_triage": "badge-info"`, `"lifecycle_automation": "badge-green"`, `"compliance_routing": "badge-amber"`, `"contract_review": "badge-info"`, `"records_disposition": "badge-red"`, `"ocr_classification": "badge-slate"`, `"custom": "badge-muted"`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=200)`
  - `code`: `CharField(max_length=60)` (uppercase normalized in `clean()` and `save()`)
  - `description`: `TextField(blank=True)`
  - `process_category`: `CharField(max_length=40, choices=PROCESS_CATEGORY_CHOICES, default="intake_triage", db_index=True)`
  - `trigger_event`: `CharField(max_length=40, choices=TRIGGER_EVENT_CHOICES, default="document_created", db_index=True)`
  - `target_document_type`: `CharField(max_length=40, choices=TARGET_DOCUMENT_TYPE_CHOICES, default="all", blank=True)`
  - `target_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="process_definitions")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_process_definitions")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dms_process_definitions")`
  - `core_workflow_ref`: `ForeignKey("core.WorkflowDefinition", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_process_definitions")`
  - `version_number`: `PositiveIntegerField(default=1)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `sla_target_hours`: `PositiveIntegerField(default=48)`
  - `swimlanes_json`: `JSONField(default=list, blank=True)`
  - `nodes_json`: `JSONField(default=list, blank=True)`
  - `transitions_json`: `JSONField(default=list, blank=True)`
  - `instance_count`: `PositiveIntegerField(default=0, editable=False)`
  - `published_at`: `DateTimeField(null=True, blank=True, editable=False)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dbpm_ten_num_uniq")` (21)
  - `UniqueConstraint(fields=["tenant", "code", "version_number"], name="doc_dbpm_tnt_cod_ver_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="doc_dbpm_tnt_sts_idx")` (20)
  - `Index(fields=["tenant", "trigger_event"], name="doc_dbpm_tnt_trg_idx")` (20)
  - `Index(fields=["tenant", "is_active"], name="doc_dbpm_tnt_act_idx")` (20)
  - `Index(fields=["tenant", "process_category"], name="doc_dbpm_tnt_cat_idx")` (20)
  - `Index(fields=["tenant", "department"], name="doc_dbpm_tnt_dpt_idx")` (20)
- **Properties & Helper Methods**:
  - `status_badge`, `category_badge`, `node_count`, `transition_count`, `swimlane_count`
  - `validate_graph()` -> delegates to `validate_process_graph(self.swimlanes_json, self.nodes_json, self.transitions_json)` returning `{"is_valid": bool, "errors": list[str], "warnings": list[str], "node_count": int, "transition_count": int}`.

---

### 1.2 `DocumentRoutingRule` (`DocumentRoutingRules.py`)
- **`NUMBER_PREFIX`**: `"DRUL"`
- **`Meta.ordering`**: `["priority", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Routing Rule"` / `"Document Routing Rules"`
- **Choices & Badge Maps**:
  - `RULE_TYPE_CHOICES` (`max_length=40`):
    - `("routing_distribution", "Document Routing & Distribution")`
    - `("conditional_branch", "Conditional Branching Rule")`
    - `("metadata_autofill", "Metadata Auto-Population")`
    - `("data_validation", "Data Validation Gate")`
    - `("escalation_fallback", "Fallback & Escalation Routing")`
    - `("lifecycle_transition", "Lifecycle Status Transition")`
  - `TRIGGER_EVENT_CHOICES` (`max_length=40`):
    - `("on_upload", "On Document Upload")`
    - `("on_metadata_change", "On Metadata Updated")`
    - `("on_ocr_complete", "On OCR Extraction Completed")`
    - `("on_status_change", "On Document Status Changed")`
    - `("on_approval_decision", "On Approval Decision")`
    - `("on_manual_eval", "On Manual Rule Evaluation")`
  - `CONDITION_LOGIC_CHOICES` (`max_length=20`):
    - `("all_and", "All Conditions (AND)")`
    - `("any_or", "Any Condition (OR)")`
  - `ROUTE_ACTION_CHOICES` (`max_length=40`):
    - `("move_to_folder", "File to Target Folder (Tags & Path)")`
    - `("assign_role", "Route to Role Pool")`
    - `("assign_user", "Assign Specific User")`
    - `("assign_org_unit_head", "Route to Org Unit / Manager")`
    - `("spawn_approval_workflow", "Spawn 13.3 Approval Workflow")`
    - `("create_document_task", "Create 13.8 Document Task")`
    - `("populate_metadata", "Auto-Populate Document & Metadata")`
    - `("trigger_process", "Launch BPM Process Definition")`
    - `("block_validation", "Validation Gate (Block on Fail)")`
  - `SUPPORTED_OPERATORS`: `("eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "regex_match", "is_set", "is_empty")`
  - `TARGET_DOC_TYPE_CHOICES` (`max_length=40`): `[("", "All Document Types")] + list(Document.DOCUMENT_TYPE_CHOICES)`
  - `TARGET_CLASSIFICATION_CHOICES` (`max_length=25`): `[("", "All Classifications")] + list(Document.CLASSIFICATION_CHOICES)`
  - `RULE_TYPE_CSS`:
    - `"routing_distribution": "badge-info"`, `"conditional_branch": "badge-amber"`, `"metadata_autofill": "badge-green"`, `"data_validation": "badge-red"`, `"escalation_fallback": "badge-amber"`, `"lifecycle_transition": "badge-slate"`
  - `ROUTE_ACTION_CSS`:
    - `"move_to_folder": "badge-info"`, `"assign_role": "badge-slate"`, `"assign_user": "badge-slate"`, `"assign_org_unit_head": "badge-info"`, `"spawn_approval_workflow": "badge-amber"`, `"create_document_task": "badge-info"`, `"populate_metadata": "badge-green"`, `"trigger_process": "badge-green"`, `"block_validation": "badge-red"`
  - `IS_ACTIVE_CSS`: `{True: "badge-green", False: "badge-slate"}`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=200)`
  - `description`: `TextField(blank=True)`
  - `process_definition`: `ForeignKey("documents.DocumentProcessDefinition", on_delete=models.SET_NULL, null=True, blank=True, related_name="routing_rules")`
  - `core_rule_ref`: `ForeignKey("core.BusinessRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_routing_rules")`
  - `rule_type`: `CharField(max_length=40, choices=RULE_TYPE_CHOICES, default="routing_distribution", db_index=True)`
  - `trigger_event`: `CharField(max_length=40, choices=TRIGGER_EVENT_CHOICES, default="on_upload", db_index=True)`
  - `priority`: `PositiveIntegerField(default=100, db_index=True)`
  - `source_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_routing_rules")`
  - `target_document_type`: `CharField(max_length=40, choices=TARGET_DOC_TYPE_CHOICES, blank=True)`
  - `target_classification`: `CharField(max_length=25, choices=TARGET_CLASSIFICATION_CHOICES, blank=True)`
  - `condition_logic_mode`: `CharField(max_length=20, choices=CONDITION_LOGIC_CHOICES, default="all_and")`
  - `conditions_json`: `JSONField(default=list, blank=True)`
  - `else_branch_enabled`: `BooleanField(default=False)`
  - `else_action_json`: `JSONField(default=dict, blank=True)`
  - `validation_rules_json`: `JSONField(default=list, blank=True)`
  - `auto_populate_json`: `JSONField(default=dict, blank=True)`
  - `route_action`: `CharField(max_length=40, choices=ROUTE_ACTION_CHOICES, default="move_to_folder", db_index=True)`
  - `destination_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="destination_routing_rules")`
  - `route_to_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_routing_rules")`
  - `route_to_role`: `ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_routing_rules")`
  - `route_to_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_dms_routing_rules")`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dms_routing_rules")`
  - `execution_count`: `PositiveIntegerField(default=0, editable=False)`
  - `match_count`: `PositiveIntegerField(default=0, editable=False)`
  - `last_evaluated_at`: `DateTimeField(null=True, blank=True, editable=False)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_drul_ten_num_uniq")` (21)
  - `Index(fields=["tenant", "priority"], name="doc_drul_tnt_pri_idx")` (20)
  - `Index(fields=["tenant", "rule_type"], name="doc_drul_tnt_typ_idx")` (20)
  - `Index(fields=["tenant", "trigger_event"], name="doc_drul_tnt_trg_idx")` (20)
  - `Index(fields=["tenant", "is_active"], name="doc_drul_tnt_act_idx")` (20)
  - `Index(fields=["tenant", "process_definition"], name="doc_drul_tnt_prc_idx")` (20)
- **Properties & Helper Methods**:
  - `rule_type_badge`, `route_action_badge`, `active_badge`, `condition_count`, `match_rate_pct`.

---

### 1.3 `DocumentProcessInstance` (`DocumentProcessInstances.py`)
- **`NUMBER_PREFIX`**: `"DPIN"`
- **`Meta.ordering`**: `["-started_at", "-id"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Process Instance"` / `"Document Process Instances"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=30`):
    - `("queued", "Queued")`
    - `("running", "Running / Active")`
    - `("waiting_approval", "Waiting on Approval")`
    - `("waiting_timer", "Waiting on Timer")`
    - `("completed", "Completed")`
    - `("failed", "Failed")`
    - `("cancelled", "Cancelled")`
    - `("sla_breached", "SLA Breached")`
  - `STATUS_CSS`:
    - `"queued": "badge-slate"`, `"running": "badge-info"`, `"waiting_approval": "badge-amber"`, `"waiting_timer": "badge-amber"`, `"completed": "badge-green"`, `"failed": "badge-red"`, `"cancelled": "badge-muted"`, `"sla_breached": "badge-red"`
- **Fields (exact names & types)**:
  - `process_definition`: `ForeignKey("documents.DocumentProcessDefinition", on_delete=models.PROTECT, related_name="instances")`
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="process_instances")`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="process_instances")`
  - `triggered_by_rule`: `ForeignKey("documents.DocumentRoutingRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_instances")`
  - `approval_workflow`: `ForeignKey("documents.DocumentApprovalWorkflow", on_delete=models.SET_NULL, null=True, blank=True, related_name="bpm_process_instances")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_process_instances")`
  - `initiated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="initiated_dms_process_instances")`
  - `current_assignee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_dms_process_instances")`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="queued", db_index=True)`
  - `current_node_id`: `CharField(max_length=80, blank=True)`
  - `current_node_label`: `CharField(max_length=160, blank=True)`
  - `started_at`: `DateTimeField(default=timezone.now, editable=False)`
  - `due_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `completed_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `cycle_time_minutes`: `PositiveIntegerField(null=True, blank=True, editable=False)`
  - `rework_count`: `PositiveSmallIntegerField(default=0, editable=False)`
  - `is_sla_breached`: `BooleanField(default=False, editable=False, db_index=True)`
  - `is_conformant`: `BooleanField(default=True, editable=False)`
  - `variant_signature`: `CharField(max_length=500, blank=True, editable=False)`
  - `step_trace_json`: `JSONField(default=list, blank=True)`
  - `context_variables_json`: `JSONField(default=dict, blank=True)`
  - `error_message`: `TextField(blank=True)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dpin_ten_num_uniq")` (21)
  - `Index(fields=["tenant", "status"], name="doc_dpin_tnt_sts_idx")` (20)
  - `Index(fields=["tenant", "process_definition"], name="doc_dpin_tnt_prc_idx")` (20)
  - `Index(fields=["tenant", "document"], name="doc_dpin_tnt_doc_idx")` (20)
  - `Index(fields=["tenant", "is_sla_breached"], name="doc_dpin_tnt_sla_idx")` (20)
  - `Index(fields=["tenant", "-started_at"], name="doc_dpin_tnt_str_idx")` (20)
- **Properties & Helper Methods**:
  - `status_badge`, `sla_badge`, `conformance_badge`, `step_count`, `duration_display`.

---

### 1.4 `DocumentWebhookTrigger` (`DocumentWebhookTriggers.py`)
- **`NUMBER_PREFIX`**: `"DWHK"`
- **`Meta.ordering`**: `["name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Webhook Trigger"` / `"Document Webhook Triggers"`
- **Choices & Badge Maps**:
  - `DIRECTION_CHOICES` (`max_length=30`):
    - `("outbound_webhook", "Outbound Webhook")`
    - `("inbound_webhook", "Inbound Webhook")`
    - `("middleware_callback", "Middleware Callback")`
  - `TRIGGER_EVENT_CHOICES` (`max_length=40`):
    - `("document.uploaded", "document.uploaded")`
    - `("document.status_changed", "document.status_changed")`
    - `("version.published", "version.published")`
    - `("metadata.updated", "metadata.updated")`
    - `("ocr.completed", "ocr.completed")`
    - `("routing.matched", "routing.matched")`
    - `("process.started", "process.started")`
    - `("process.completed", "process.completed")`
    - `("process.sla_breached", "process.sla_breached")`
    - `("approval.decided", "approval.decided")`
    - `("inbound.trigger", "inbound.trigger")`
  - `HTTP_METHOD_CHOICES` (`max_length=15`):
    - `("post", "POST")`, `("put", "PUT")`, `("patch", "PATCH")`
  - `PAYLOAD_FORMAT_CHOICES` (`max_length=30`):
    - `("json", "NavERP Standard JSON")`, `("cloudevents_json", "CloudEvents 1.0 JSON")`
  - `LAST_STATUS_CHOICES` (`max_length=25`):
    - `("never_fired", "Never Fired")`, `("simulated", "Simulated (Local)")`, `("queued", "Queued")`, `("delivered", "Delivered")`, `("failed", "Failed")`
  - `FILTER_DOC_TYPE_CHOICES` (`max_length=40`): `[("", "All Document Types")] + list(Document.DOCUMENT_TYPE_CHOICES)`
  - `LAST_STATUS_CSS`:
    - `"never_fired": "badge-slate"`, `"simulated": "badge-info"`, `"queued": "badge-amber"`, `"delivered": "badge-green"`, `"failed": "badge-red"`
  - `DIRECTION_CSS`:
    - `"outbound_webhook": "badge-info"`, `"inbound_webhook": "badge-amber"`, `"middleware_callback": "badge-slate"`
  - `IS_ACTIVE_CSS`: `{True: "badge-green", False: "badge-slate"}`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=160)`
  - `description`: `TextField(blank=True)`
  - `direction`: `CharField(max_length=30, choices=DIRECTION_CHOICES, default="outbound_webhook", db_index=True)`
  - `trigger_event`: `CharField(max_length=40, choices=TRIGGER_EVENT_CHOICES, default="document.uploaded", db_index=True)`
  - `process_definition`: `ForeignKey("documents.DocumentProcessDefinition", on_delete=models.SET_NULL, null=True, blank=True, related_name="webhook_triggers")`
  - `connector_ref`: `ForeignKey("core.ConnectorDefinition", on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_webhook_triggers")`
  - `target_url`: `URLField(max_length=500, blank=True)`
  - `http_method`: `CharField(max_length=15, choices=HTTP_METHOD_CHOICES, default="post")`
  - `payload_format`: `CharField(max_length=30, choices=PAYLOAD_FORMAT_CHOICES, default="json")`
  - `custom_headers`: `JSONField(default=dict, blank=True)`
  - `payload_template_json`: `JSONField(default=dict, blank=True)`
  - `filter_document_type`: `CharField(max_length=40, choices=FILTER_DOC_TYPE_CHOICES, blank=True)`
  - `retry_policy_max`: `PositiveSmallIntegerField(default=5)`
  - `signing_secret`: `CharField(max_length=512, blank=True, editable=False)`
  - `signing_secret_prefix`: `CharField(max_length=16, blank=True, editable=False)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dms_webhook_triggers")`
  - `last_status`: `CharField(max_length=25, choices=LAST_STATUS_CHOICES, default="never_fired", editable=False, db_index=True)`
  - `last_fired_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `fire_count`: `PositiveIntegerField(default=0, editable=False)`
  - `failure_count`: `PositiveIntegerField(default=0, editable=False)`
  - `delivery_history_json`: `JSONField(default=list, blank=True, editable=False)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dwhk_ten_num_uniq")` (21)
  - `Index(fields=["tenant", "trigger_event"], name="doc_dwhk_tnt_evt_idx")` (20)
  - `Index(fields=["tenant", "direction"], name="doc_dwhk_tnt_dir_idx")` (20)
  - `Index(fields=["tenant", "is_active"], name="doc_dwhk_tnt_act_idx")` (20)
  - `Index(fields=["tenant", "last_status"], name="doc_dwhk_tnt_sts_idx")` (20)
- **Properties & Helper Methods**:
  - `last_status_badge`, `direction_badge`, `active_badge`, `masked_secret`
  - `set_signing_secret(raw)`, `get_signing_secret()`, `generate_signing_secret()`
  - `compute_signature(payload_bytes)`, `verify_signature(payload_bytes, signature)`
  - `record_simulated_delivery(event_name, payload_dict)`
  - `clean()`: validates `target_url` via `validate_dms_webhook_url(...)` when `target_url` is set or `direction in ("outbound_webhook", "middleware_callback")`, and validates `custom_headers` flat `{str: str}` free of `\r`/`\n`.

---

## 2. Forms Contract (`apps/documents/forms/WorkflowAutomation/`)

All ModelForms inherit `TenantUniqueMixin, TenantModelForm` and use `reject_foreign(...)`.

### 2.1 `DocumentProcessDefinitions.py`
- **`DocumentProcessDefinitionForm`**:
  - `Meta.fields`: `["name", "code", "description", "process_category", "trigger_event", "target_document_type", "target_folder", "department", "core_workflow_ref", "version_number", "sla_target_hours", "is_active", "swimlanes_json", "nodes_json", "transitions_json"]`
  - Excluded: `tenant`, `number`, `owner`, `status`, `instance_count`, `published_at`, `created_at`, `updated_at`.
  - `__init__`: tenant-scopes `target_folder` (`DocumentFolder`), `department` (`OrgUnit`), `core_workflow_ref` (`WorkflowDefinition`); sets optional fields `required=False`.
  - `clean_code()`: strips & uppercases `code`.
  - `clean_swimlanes_json()`, `clean_nodes_json()`, `clean_transitions_json()`: accepts `list` or valid JSON list string; rejects non-list payloads cleanly.
  - `clean()`: calls `reject_foreign(self, cleaned, ["target_folder", "department", "core_workflow_ref"])` and validates uniqueness of `(tenant, code, version_number)` cleanly before DB save.
- **`ProcessDesignerForm`** (`forms.Form`):
  - `swimlanes_json`, `nodes_json`, `transitions_json` (all `CharField`/`JSON` string inputs parsed cleanly to `list` and validated).

### 2.2 `DocumentRoutingRules.py`
- **`DocumentRoutingRuleForm`**:
  - `Meta.fields`: `["name", "description", "process_definition", "core_rule_ref", "rule_type", "trigger_event", "priority", "source_folder", "target_document_type", "target_classification", "condition_logic_mode", "conditions_json", "else_branch_enabled", "else_action_json", "validation_rules_json", "auto_populate_json", "route_action", "destination_folder", "route_to_org_unit", "route_to_role", "route_to_user", "is_active"]`
  - Excluded: `tenant`, `number`, `owner`, `execution_count`, `match_count`, `last_evaluated_at`, `created_at`, `updated_at`.
  - `__init__`: tenant-scopes `process_definition`, `core_rule_ref`, `source_folder`, `destination_folder`, `route_to_org_unit`, `route_to_role`, `route_to_user`.
  - `clean()`: validates JSON field types + condition operators (`SUPPORTED_OPERATORS`) + regex syntax in `regex_match` conditions, and calls `reject_foreign(self, cleaned, ["process_definition", "core_rule_ref", "source_folder", "destination_folder", "route_to_org_unit", "route_to_role", "route_to_user"])`.
- **`RoutingRuleSimulatorForm`** (`forms.Form`):
  - `document` (`ModelChoiceField` tenant-scoped `Document`, required), `rule` (`ModelChoiceField` tenant-scoped `DocumentRoutingRule`, optional — blank evaluates active chain), `trigger_event` (`ChoiceField` optional), `apply_mutations` (`BooleanField`, `required=False`, initial `False`).

### 2.3 `DocumentProcessInstances.py`
- **`DocumentProcessInstanceForm`**:
  - `Meta.fields`: `["process_definition", "document", "version", "department", "current_assignee", "context_variables_json"]`
  - Excluded: `tenant`, `number`, `triggered_by_rule`, `approval_workflow`, `initiated_by`, `status`, `current_node_id`, `current_node_label`, `started_at`, `due_at`, `completed_at`, `cycle_time_minutes`, `rework_count`, `is_sla_breached`, `is_conformant`, `variant_signature`, `step_trace_json`, `error_message`, `created_at`, `updated_at`.
  - `__init__`: tenant-scopes `process_definition`, `document`, `version` (`.select_related("document")`), `department`, `current_assignee`.
  - `clean()`: `reject_foreign(self, cleaned, ["process_definition", "document", "version", "department", "current_assignee"])` + ensures `version.document_id == document.id` if both given + validates `context_variables_json` is a dict.
- **`ProcessAdvanceForm`** (`forms.Form`):
  - `outcome`: `ChoiceField` (`[("approved", "Proceed / Approve"), ("rejected", "Reject / Rework"), ("escalated", "Escalate / Flag SLA"), ("completed", "Force Complete")]`)
  - `notes`: `CharField(required=False)`

### 2.4 `DocumentWebhookTriggers.py`
- **`DocumentWebhookTriggerForm`**:
  - `Meta.fields`: `["name", "description", "direction", "trigger_event", "process_definition", "connector_ref", "target_url", "http_method", "payload_format", "custom_headers", "payload_template_json", "filter_document_type", "retry_policy_max", "is_active"]`
  - Excluded (L20/L22): `tenant`, `number`, `owner`, `signing_secret`, `signing_secret_prefix`, `last_status`, `last_fired_at`, `fire_count`, `failure_count`, `delivery_history_json`, `created_at`, `updated_at`.
  - `__init__`: tenant-scopes `process_definition`, `connector_ref`.
  - `clean_target_url()`: calls `validate_dms_webhook_url(...)` when `target_url` is supplied.
  - `clean_custom_headers()`: verifies JSON object `{str: str}` with no `\r`/`\n` in keys or values.
  - `clean_payload_template_json()`: verifies JSON object `dict`.
  - `clean()`: `reject_foreign(self, cleaned, ["process_definition", "connector_ref"])` + enforces `target_url` required if `direction in ("outbound_webhook", "middleware_callback")`.
- **`WebhookTestPingForm`** (`forms.Form`):
  - `event_override`: `CharField(required=False, max_length=60)`
  - `document`: `ModelChoiceField` (tenant-scoped `Document`, `required=False`)

---

## 3. Views, URLs & Context Keys Contract

### 3.1 `DocumentProcessDefinitions`
- Routes (`apps/documents/urls/WorkflowAutomation/DocumentProcessDefinitions.py`):
  - `path("bpm/processes/", views.process_definition_list, name="process_definition_list")`
  - `path("bpm/processes/create/", views.process_definition_create, name="process_definition_create")`
  - `path("bpm/processes/<int:pk>/", views.process_definition_detail, name="process_definition_detail")`
  - `path("bpm/processes/<int:pk>/edit/", views.process_definition_edit, name="process_definition_edit")`
  - `path("bpm/processes/<int:pk>/delete/", views.process_definition_delete, name="process_definition_delete")`
  - `path("bpm/processes/<int:pk>/designer/", views.process_definition_designer, name="process_definition_designer")`
  - `path("bpm/processes/<int:pk>/publish/", views.process_definition_publish, name="process_definition_publish")`
  - `path("bpm/processes/<int:pk>/deprecate/", views.process_definition_deprecate, name="process_definition_deprecate")`
- Context Keys:
  - `process_definition_list`: `process_definitions`, `page_obj`, `total_count`, `published_count`, `draft_count`, `active_count`, `status_choices`, `category_choices`, `trigger_choices`, `departments`, `q`, `status`, `category`, `trigger_event`, `department`
  - `process_definition_detail`: `process_def`, `validation_result`, `simulation_steps`, `routing_rules`, `recent_instances`, `webhooks`
  - `process_definition_create` & `process_definition_edit`: `form`, `process_def`, `is_edit`
  - `process_definition_designer`: `process_def`, `designer_form`, `swimlanes`, `nodes`, `transitions`, `validation_result`, `simulation_steps`, `roles`, `departments`

### 3.2 `DocumentRoutingRules`
- Routes (`apps/documents/urls/WorkflowAutomation/DocumentRoutingRules.py`):
  - `path("bpm/routing-rules/", views.routing_rule_list, name="routing_rule_list")`
  - `path("bpm/routing-rules/create/", views.routing_rule_create, name="routing_rule_create")`
  - `path("bpm/routing-rules/simulator/", views.routing_rule_simulator, name="routing_rule_simulator")`
  - `path("bpm/routing-rules/<int:pk>/", views.routing_rule_detail, name="routing_rule_detail")`
  - `path("bpm/routing-rules/<int:pk>/edit/", views.routing_rule_edit, name="routing_rule_edit")`
  - `path("bpm/routing-rules/<int:pk>/delete/", views.routing_rule_delete, name="routing_rule_delete")`
  - `path("bpm/routing-rules/<int:pk>/toggle/", views.routing_rule_toggle, name="routing_rule_toggle")`
- Context Keys:
  - `routing_rule_list`: `routing_rules`, `page_obj`, `total_count`, `active_count`, `total_matches`, `rule_type_choices`, `trigger_choices`, `route_action_choices`, `process_definitions`, `q`, `rule_type`, `trigger_event`, `route_action`, `status`, `process_definition`
  - `routing_rule_detail`: `rule`, `conditions`, `validation_rules`, `auto_populate`, `else_action`
  - `routing_rule_create` & `routing_rule_edit`: `form`, `rule`, `is_edit`
  - `routing_rule_simulator`: `form`, `selected_document`, `evaluation_results`, `applied_summary`

### 3.3 `DocumentProcessInstances`
- Routes (`apps/documents/urls/WorkflowAutomation/DocumentProcessInstances.py`):
  - `path("bpm/instances/", views.process_instance_list, name="process_instance_list")`
  - `path("bpm/instances/create/", views.process_instance_create, name="process_instance_create")`
  - `path("bpm/instances/<int:pk>/", views.process_instance_detail, name="process_instance_detail")`
  - `path("bpm/instances/<int:pk>/edit/", views.process_instance_edit, name="process_instance_edit")`
  - `path("bpm/instances/<int:pk>/delete/", views.process_instance_delete, name="process_instance_delete")`
  - `path("bpm/instances/<int:pk>/advance/", views.process_instance_advance, name="process_instance_advance")`
  - `path("bpm/instances/<int:pk>/cancel/", views.process_instance_cancel, name="process_instance_cancel")`
- Context Keys:
  - `process_instance_list`: `instances`, `page_obj`, `total_count`, `active_count`, `completed_count`, `sla_breached_count`, `status_choices`, `process_definitions`, `departments`, `q`, `status`, `process_definition`, `department`, `sla_breached`
  - `process_instance_detail`: `instance`, `step_trace`, `blueprint_nodes`, `advance_form`
  - `process_instance_create` & `process_instance_edit`: `form`, `instance`, `is_edit`

### 3.4 `DocumentWebhookTriggers`
- Routes (`apps/documents/urls/WorkflowAutomation/DocumentWebhookTriggers.py`):
  - `path("bpm/webhooks/", views.webhook_trigger_list, name="webhook_trigger_list")`
  - `path("bpm/webhooks/create/", views.webhook_trigger_create, name="webhook_trigger_create")`
  - `path("bpm/webhooks/<int:pk>/", views.webhook_trigger_detail, name="webhook_trigger_detail")`
  - `path("bpm/webhooks/<int:pk>/edit/", views.webhook_trigger_edit, name="webhook_trigger_edit")`
  - `path("bpm/webhooks/<int:pk>/delete/", views.webhook_trigger_delete, name="webhook_trigger_delete")`
  - `path("bpm/webhooks/<int:pk>/rotate-secret/", views.webhook_trigger_rotate_secret, name="webhook_trigger_rotate_secret")`
  - `path("bpm/webhooks/<int:pk>/test-ping/", views.webhook_trigger_test_ping, name="webhook_trigger_test_ping")`
  - `path("bpm/webhooks/<int:pk>/simulate-inbound/", views.webhook_trigger_simulate_inbound, name="webhook_trigger_simulate_inbound")`
- Context Keys:
  - `webhook_trigger_list`: `webhooks`, `page_obj`, `total_count`, `active_count`, `simulated_count`, `total_fires`, `direction_choices`, `trigger_choices`, `last_status_choices`, `q`, `direction`, `trigger_event`, `last_status`, `status`
  - `webhook_trigger_detail`: `webhook`, `revealed_secret`, `delivery_history`, `ping_form`, `tenant_documents`
  - `webhook_trigger_create` & `webhook_trigger_edit`: `form`, `webhook`, `is_edit`

### 3.5 `WorkflowAnalytics`
- Routes (`apps/documents/urls/WorkflowAutomation/WorkflowAnalytics.py`):
  - `path("bpm/analytics/", views.process_analytics_dashboard, name="process_analytics_dashboard")`
- Context Keys:
  - `process_analytics_dashboard`: `analytics`, `process_definitions`, `departments`, `selected_process_id`, `selected_department_id`, `date_from`, `date_to`

---

## 4. Navigation & `LIVE_LINKS["13.11"]` (`apps/core/navigation.py`)

```python
LIVE_LINKS["13.11"] = {
    "Business Process Modeling": "documents:process_definition_list",
    "Document Routing & Distribution": "documents:routing_rule_list",
    "Conditional Logic & Business Rules": "documents:routing_rule_simulator",
    "Integration Triggers & Webhooks": "documents:webhook_trigger_list",
    "Process Performance Analytics": "documents:process_analytics_dashboard",
    # Extra live leaf:
    "Process Execution Instances": "documents:process_instance_list",
}
```
