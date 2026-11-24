# Research — Sub-module 13.11: Workflow Automation & BPM (Module 13 — Document Management System, documents)

## Repo state checked first

- **LIVE_LINKS built so far in module 13 (verified in `apps/core/navigation.py:3525-3619`):**
  - `13.1` (Document Creation & Authoring): `DocumentTemplate` (`DTMPL`), `TemplateSection` (`DSEC`), `DocumentDraft` (`DDFT`), `DraftCollaboration` (`DCMT`)
  - `13.2` (Version Control & Revision Management): `Document` (`DOC`), `DocumentVersion` (`DVER`), `DocumentLock` (`DLOCK`), `DocumentBranch` (`DBRN`)
  - `13.3` (Document Approval & Review Workflow): `DocumentApprovalWorkflow` (`DWF`), `DocumentApprovalRequest` (`DAPR`), `DocumentSignature` (`DSIG`), `DocumentReviewComment` (`DREV`)
  - `13.4` (Document Storage & Repository): `DocumentFolder` (`DFLD`), `StorageVolume` (`DSTG`), `DocumentRelationship` (`DREL`), `DocumentBatchImport` (`DBLK`)
  - `13.5` (Metadata & Indexing): `MetadataSchema` (`DSCH`), `DocumentMetadataValue` (`DMETA`), `TaxonomyTerm` (`DTAX`), `DocumentOcrJob` (`DOCR`)
  - `13.6` (Search & Discovery): `DocumentSavedSearch` (`DSVD`), `DocumentSearchAlert` (`DALT`), `DocumentSearchSynonym` (`DSYN`), `DocumentSearchQueryLog` (`DQRY`)
  - `13.7` (Document Security & Access Control): `DocumentAccessPermission` (`DPRM`), `WatermarkPolicy` (`DWTR`), `DocumentDrmPolicy` (`DDRM`), `DlpPolicy` (`DDLP`), `DlpIncident` (`DINC`)
  - `13.8` (Collaboration & Sharing): `DocumentShare` (`DSHR`), `CoauthorSession` (`DCOA`), `DocumentTask` (`DTSK`), `DocumentActivity` (`DACT`)
  - `13.9` (Records Management & Compliance): `RetentionSchedule` (`DRTN`), `RecordDeclaration` (`DRCD`), `DocumentLegalHold` (`DHLD`), `DestructionCertificate` (`DDST`)
  - `13.10` (Audit Trail & Reporting): `DocumentAuditTrail` (`DAUD`), `AuditReportDefinition` (`DRPT`), `DocumentSecurityAlert` (`DANM`), `ChainOfCustodyExport` (`DCOC`)

- **Sibling models available to FK in `apps/documents/` (verified via grep on `apps/documents/models/`):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Logical document container (`title`, `slug`, `document_type`, `classification`, `status`, `owner`, `department`, `tags`).
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Physical revision snapshot (`version_label`, `file_hash`, `extracted_text`, `is_official`, `status`).
  - `documents.DocumentFolder` (`apps/documents/models/StorageRepository/DocumentFolders.py:9`, `NUMBER_PREFIX = "DFLD"`): Nested repository taxonomy (`path`, `department`, `owner`, `default_classification`, `is_virtual`).
  - `documents.DocumentApprovalWorkflow` (`apps/documents/models/ApprovalWorkflow/DocumentApprovalWorkflows.py:8`, `NUMBER_PREFIX = "DWF"`): Document-bound human approval pipeline instance (`document`, `version`, `workflow_type`, `status`, `urgency`, `target_turnaround_hours`, `definition_json`).
  - `documents.DocumentApprovalRequest` (`apps/documents/models/ApprovalWorkflow/DocumentApprovalRequests.py:8`, `NUMBER_PREFIX = "DAPR"`): Individual approval step task (`workflow`, `stage_number`, `approver`, `approver_role`, `delegated_to`, `escalated_to`, `decided_at`).
  - `documents.MetadataSchema` (`apps/documents/models/MetadataIndexing/MetadataSchemas.py:11`, `NUMBER_PREFIX = "DSCH"`) and `documents.DocumentMetadataValue` (`apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:8`, `NUMBER_PREFIX = "DMETA"`): Typed metadata properties and schema validation state.
  - `documents.DocumentOcrJob` (`apps/documents/models/MetadataIndexing/DocumentOcrJobs.py:8`, `NUMBER_PREFIX = "DOCR"`): OCR full-text and structured entity extraction jobs.
  - `documents.DocumentTask` (`apps/documents/models/CollaborationSharing/DocumentTasks.py:8`, `NUMBER_PREFIX = "DTSK"`): Assignable document work items (`assigned_to`, `assigned_org_unit`, `due_date`).
  - `documents.DocumentAuditTrail` (`apps/documents/models/AuditReporting/DocumentAuditTrails.py:11`, `NUMBER_PREFIX = "DAUD"`): Append-only cryptographic audit ledger.

- **Spine & cross-module entities verified to exist (grep evidence & L28/L29/L36/L55 boundaries):**
  - `core.Tenant` (`apps/core/models/Tenant.py`): Multi-tenant isolation anchor.
  - `accounts.User` (`apps/accounts/models.py:52`) & `accounts.Role` (`apps/accounts/models.py:35`): Users, process owners, swimlane roles, and routing assignees.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Organizational hierarchy (`company`/`branch`/`department`/`team`/`cost_center` with `parent` self-FK) used for hierarchy-based document routing.
  - `core.WorkflowDefinition` (`apps/core/models/Workflow.py:27`) & `core.BusinessRule` (`apps/core/models/BusinessRule.py:23`): **0.11 platform documentation & decision-support registries.** Per `apps/core/models/Workflow.py:3-22` and `BusinessRule.py:1-18`, 0.11 deliberately documents workflows and evaluates generic JSON predicates without executing domain mutations. 13.11 optionally references them (`core_workflow_ref`, `core_rule_ref`) and owns DMS-specific BPMN blueprints, folder/metadata mutations, process execution traces, and DMS webhook dispatch.
  - `core.ConnectorDefinition` (`apps/core/models/Integration.py:143`): **0.13 platform connector catalog**, usable as an optional nullable FK on DMS integration triggers.
  - `apps.core.crypto` (`encrypt`, `decrypt`): Fernet field encryption used for recoverable HMAC signing secrets (per `crm.Webhook` and `projects.ProjectWebhookEndpoint`).
  - **13.3 vs 13.11 boundary (L36):** 13.3 (`DocumentApprovalWorkflow`, `DocumentApprovalRequest`, `DocumentSignature`, `DocumentReviewComment`) owns **per-document human review & e-signature pipelines**. 13.11 MUST NOT re-declare approval request/signature models; instead 13.11 owns reusable **BPMN process templates** (`DocumentProcessDefinition`), **metadata/hierarchy routing & business rules** (`DocumentRoutingRule`), **process orchestration instances & process mining telemetry** (`DocumentProcessInstance`, optionally linking a spawned `DocumentApprovalWorkflow`), and **DMS event triggers & webhooks** (`DocumentWebhookTrigger`).
  - **Webhook isolation ruling (L55):** Following `crm.Webhook` (`WH`), `scm.WebhookSubscription` (`WHK`), and `projects.ProjectWebhookEndpoint` (`PWH`), `DocumentWebhookTrigger` (`DWHK`) is scoped strictly to DMS event nouns (`document.*`, `version.*`, `metadata.*`, `ocr.*`, `process.*`, `routing.*`) and is deliberately not merged into sibling webhook tables.
  - **Unbuilt spine note (L28):** `core.Item` / `inventory.StockMove` / `sales.SalesOrder` remain unbuilt and are not needed by 13.11.

- **Prefix & class collision verification (verified via `rg` across `apps/` and `.claude/tasks/contract-*.md`):**
  - `DBPM` (`DocumentProcessDefinition`): Verified free (0 matches across `apps/` and contracts).
  - `DRUL` (`DocumentRoutingRule`): Verified free (0 matches across `apps/` and contracts).
  - `DPIN` (`DocumentProcessInstance`): Verified free (0 matches across `apps/` and contracts).
  - `DWHK` (`DocumentWebhookTrigger`): Verified free (0 matches across `apps/` and contracts).
  - All four proposed class names (`DocumentProcessDefinition`, `DocumentRoutingRule`, `DocumentProcessInstance`, `DocumentWebhookTrigger`) and DMS URL stems (`process_definition_*`, `routing_rule_*`, `process_instance_*`, `webhook_trigger_*`, `process_designer`, `process_analytics_dashboard`) verified 0 collisions in `apps/documents/` and contracts.

---

## Leaders surveyed (with source links)

1. **Laserfiche (Workflow & Process Automation)** — Enterprise content services and BPM suite combining a visual drag-and-drop process designer (100+ workflow activities) with metadata- and OCR-aware document routing, organizational hierarchy escalation, conditional branching with dynamic tokens, webhook/API service calls, and step-level instance analytics.
   - *Source:* https://www.laserfiche.com/
2. **DocuWare (Workflow Manager)** — Process-centric document automation platform built around flowchart modeling, index-field and digital-stamp routing triggers, dynamic role/substitution assignment, time-based escalations, conditional decision gateways, and controller bottleneck visibility.
   - *Source:* https://www.docuware.com/
3. **M-Files (Workflow Automation & Business Rules)** — Metadata-first information management platform where state-transition workflows and event-driven business rules automatically classify, route, protect, and validate documents based on property changes and role relationships rather than rigid folder locations.
   - *Source:* https://www.m-files.com/
4. **Alfresco Process Services / Activiti (Hyland)** — Standards-based BPMN 2.0 and DMN 1.3 workflow engine tightly integrated with document repositories. Separates process orchestration diagrams from DMN decision tables, links repository document events to process starts, exposes REST/webhook tasks, and tracks full historical activity metrics.
   - *Source:* https://www.hyland.com/
5. **Hyland OnBase (Workflow & WorkView)** — High-volume enterprise content and workflow platform pairing rule-based lifecycle queues, automated document classification/distribution across departments, load-balanced work allocation, external system triggers, and operational SLA reporting.
   - *Source:* https://www.hyland.com/
6. **Nintex (Process Platform / K2 Automation)** — Visual end-to-end process modeling and automation platform featuring flowchart designers, conditional routing rules, document-generation/state triggers, third-party webhook/connector actions, and Process Manager cycle-time and compliance analytics.
   - *Source:* https://www.nintex.com/
7. **Camunda Platform 8 (BPMN / DMN / Optimize)** — High-scale BPMN 2.0 and DMN process orchestration engine featuring swimlane and gateway modeling (XOR/AND/OR), inbound/outbound HTTP webhook connectors with HMAC authentication, and Camunda Optimize heatmaps for cycle-time, SLA tracking, bottleneck detection, and process mining.
   - *Source:* https://camunda.com/
8. **Microsoft Power Automate (Cloud Flows, BPFs & Process Mining)** — Low-code automation and process intelligence suite providing staged Business Process Flows, conditional branching, HTTP webhook triggers/callbacks, automated document-processing pipelines, and process mining X-ray maps exposing variants, rework loops, and bottlenecks.
   - *Source:* https://www.microsoft.com/en-us/power-platform/products/power-automate
9. **Kissflow & ProcessMaker (Low-Code Document BPM)** — Business-led BPM platforms pairing BPMN/visual process builders with conditional decision tables, dynamic form/metadata field population, role-hierarchy routing, webhook payloads, and real-time throughput/bottleneck dashboards.
   - *Source:* https://kissflow.com/ · https://www.processmaker.com/

---

## Feature catalog (this sub-module only)

### Business Process Modeling
- **Reusable Versioned BPMN Process Definitions (`DocumentProcessDefinition` - `DBPM`)** — Stores reusable, versioned process blueprints (`draft` → `published` → `deprecated` → `archived`) independent of any single document instance, distinct from 13.3's per-document `DocumentApprovalWorkflow` (`DWF`). · seen in: Camunda 8, Alfresco Process Services, Laserfiche, ProcessMaker · priority: **table-stakes** · spine: `DocumentProcessDefinition` (`DBPM`), optional link to `core.WorkflowDefinition` · **buildable now**
- **Visual Swimlane & Gateway Designer** — Interactive visual process canvas organizing steps into role/department swimlanes (`accounts.Role`, `core.OrgUnit`) with typed BPMN nodes (`start_event`, `user_task`, `service_task`, `approval_subprocess`, `exclusive_gateway`, `parallel_gateway`, `inclusive_gateway`, `timer_event`, `webhook_task`, `end_event`) and directed edges stored in structured JSON (`swimlanes_json`, `nodes_json`, `transitions_json`). · seen in: Camunda 8, Activiti/APS, Nintex, Laserfiche, ProcessMaker · priority: **table-stakes** · spine: `DocumentProcessDefinition` + dedicated `process_designer` view · **buildable now**
- **Decision Gateways & Multi-Path Transitions** — Models Exclusive (`XOR` conditional split), Parallel (`AND` fork/join), and Inclusive (`OR` multi-branch) gateways with fallback default paths so documents branch dynamically without duplicating workflows. · seen in: Camunda 8, Alfresco Process Services, Appian, Laserfiche · priority: **table-stakes** · spine: `DocumentProcessDefinition.transitions_json` + gateway evaluation in `DocumentProcessInstance` · **buildable now**
- **Repository Event & Manual Process Triggers** — Binds process blueprints to repository lifecycle events (`document_created`, `version_uploaded`, `status_changed`, `metadata_updated`, `ocr_completed`, `approval_completed`, `manual_trigger`, `webhook_inbound`) with optional scoping to `document_type`, `DocumentFolder`, or `core.OrgUnit`. · seen in: Laserfiche, M-Files, DocuWare, Alfresco · priority: **table-stakes** · spine: `DocumentProcessDefinition.trigger_event`, `target_folder`, `department` · **buildable now**
- **Visual SVG/Canvas Workflow Validation & Dry-Run** — Validates process graphs before publishing (requires start event, end event, reachable nodes, valid gateway default edges) and lets admins preview simulated execution paths. · seen in: Camunda 8, Kissflow, ProcessMaker · priority: **common** · spine: model validation + simulator view on `DocumentProcessDefinition` · **buildable now**

### Document Routing & Distribution
- **Metadata-Driven Auto-Filing & Routing (`DocumentRoutingRule` - `DRUL`)** — Evaluates document attributes (`document_type`, `classification`, `tags`), `DocumentMetadataValue` entries, and `DocumentOcrJob` extracted fields/entities to route documents automatically into target `DocumentFolder` taxonomies or assign owners/tasks. · seen in: M-Files, Laserfiche, DocuWare, OnBase · priority: **table-stakes** · spine: `DocumentRoutingRule` (`DRUL`), FKs to `documents.DocumentFolder`, reads `Document`, `DocumentMetadataValue`, `DocumentOcrJob` · **buildable now**
- **Organizational Hierarchy & Role-Based Distribution** — Routes documents and spawned work items dynamically via `core.OrgUnit` hierarchy (department/branch/cost-center routing, parent-unit escalation) and `accounts.Role` pools rather than brittle hardcoded usernames. · seen in: Laserfiche, DocuWare, M-Files, OnBase · priority: **table-stakes** · spine: `DocumentRoutingRule` FKs to `core.OrgUnit`, `accounts.Role`, `accounts.User` · **buildable now**
- **Cross-Submodule Work Dispatch (Approval & Task Spawning)** — When a routing rule or process node requires human review or action, spawns/links a `documents.DocumentApprovalWorkflow` (`DWF`, 13.3) or `documents.DocumentTask` (`DTSK`, 13.8) instead of creating a duplicate approval table. · seen in: Alfresco Process Services, M-Files, Power Automate · priority: **common** · spine: `DocumentProcessInstance.approval_workflow` (FK `documents.DocumentApprovalWorkflow`), `DocumentRoutingRule.route_action` · **buildable now**
- **Fallback / Escalation Routing & Load Priority** — Deterministic priority ordering (`priority` integer ascending) with explicit fallback/else routing destinations when primary criteria fail or an assignee/department is unset. · seen in: DocuWare, OnBase, Laserfiche · priority: **common** · spine: `DocumentRoutingRule.priority`, `else_branch_enabled`, `else_action_json` · **buildable now**

### Conditional Logic & Business Rules
- **Structured If-Then-Else Rule Builder (`all`/`any` Predicates)** — Evaluates multi-clause boolean rules (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`, `regex_match`, `is_set`, `is_empty`) against live document context (status, classification, file size/version count, folder path, metadata values, OCR confidence/entities) with explicit `else` branch behavior. · seen in: Laserfiche, Camunda DMN, Appian, ProcessMaker, `core.BusinessRule` · priority: **table-stakes** · spine: `DocumentRoutingRule.conditions_json`, `condition_logic_mode`, optional `core_rule_ref` (FK `core.BusinessRule`) · **buildable now**
- **Data Validation Gates** — Enforces pre-transition validation rules (e.g., require mandatory `DocumentMetadataValue` keys, minimum OCR confidence score, or non-draft status before entering a compliance process or moving to an official folder), blocking or flagging invalid documents with structured reasons. · seen in: Laserfiche, Power Automate BPFs, M-Files · priority: **table-stakes** · spine: `DocumentRoutingRule.validation_rules_json` + validation evaluator · **buildable now**
- **Automatic Metadata & Field Population** — Automatically populates or normalizes `Document` fields (`classification`, `status`, `tags`, `department`) and creates/updates `DocumentMetadataValue` rows (e.g., stamping `routing_tier`, `effective_quarter`, or copying OCR-extracted fields) when conditions match, logging changes to `DocumentAuditTrail`. · seen in: M-Files, DocuWare, Laserfiche, Kissflow · priority: **table-stakes** · spine: `DocumentRoutingRule.auto_populate_json` writing `Document` / `DocumentMetadataValue` + `DocumentAuditTrail` · **buildable now**
- **Interactive Rule Dry-Run / Test Bench** — Allows administrators to pick any tenant `Document` and test a `DocumentRoutingRule` (or ordered rule chain) to inspect clause-by-clause match reasons, validation pass/fail, and proposed field/folder mutations before activating or applying live. · seen in: Camunda DMN Simulator, Kissflow Solution Analyzer, `core.evaluate_rules` · priority: **differentiator** · spine: rule evaluation helper + dry-run view · **buildable now**

### Integration Triggers & Webhooks
- **DMS Event Webhook & Middleware Subscriptions (`DocumentWebhookTrigger` - `DWHK`)** — Registers inbound and outbound event triggers (`outbound_webhook`, `inbound_webhook`, `middleware_callback`) scoped exclusively to DMS events (`document.uploaded`, `document.status_changed`, `version.published`, `metadata.updated`, `ocr.completed`, `process.started`, `process.completed`, `process.sla_breached`, `routing.matched`, `approval.decided`), optionally launching a `DocumentProcessDefinition` on inbound trigger. · seen in: Camunda 8 Inbound/Outbound Connectors, Power Automate HTTP Webhooks, Nintex, Laserfiche · priority: **table-stakes** · spine: `DocumentWebhookTrigger` (`DWHK`), FKs `DocumentProcessDefinition`, optional `core.ConnectorDefinition` · **buildable now** (config, signing, & local simulated dispatch); **integration/later** (real outbound HTTP worker)
- **HMAC-SHA256 Signing & Pop-Once Secret Rotation (L20/L25)** — Stores HMAC signing keys encrypted at rest via `apps.core.crypto` (`encrypt`/`decrypt`) with `editable=False` on both ciphertext and `secret_prefix` (excluded structurally from all ModelForms per L20), rotating via dedicated POST action and displaying plaintext exactly once via pop-once session reveal (per L25, never `messages`). Computes authentic `X-NavERP-Signature-256` HMAC digests on simulated/local payloads. · seen in: Camunda 8 HMAC Webhooks, `projects.ProjectWebhookEndpoint`, `crm.Webhook` · priority: **table-stakes** · spine: `DocumentWebhookTrigger.signing_secret` + `signing_secret_prefix` · **buildable now**
- **SSRF-Hardened Target URL & Header Validation** — Validates webhook target URLs at the form/model boundary (requires `https://` or explicit non-private `http://`, rejects localhost, loopback `127.0.0.0/8`, RFC1918 private subnets, link-local `169.254.0.0/16` metadata IP, and IPv6 ULA `fc00::/7`) and enforces flat `{str: str}` custom headers free of CR/LF injection. · seen in: Enterprise iPaaS security benchmarks, `scm.WebhookSubscriptionForm` · priority: **table-stakes** · spine: `DocumentWebhookTriggerForm` / model `clean()` · **buildable now**
- **Simulated Delivery Diagnostics & Payload Inspector** — Executes honest dry-run / simulated webhook test dispatches (zero outbound HTTP in this pass, per L55), recording signed JSON envelope previews, status (`simulated`/`pending`/`failed`), and delivery history JSON on the trigger plus `DocumentAuditTrail` telemetry. · seen in: Camunda Connector Test, `projects.ProjectWebhookDelivery`, `scm.WebhookDelivery` · priority: **common** · spine: `DocumentWebhookTrigger.delivery_history_json` + `webhook_trigger_test_ping` action · **buildable now**

### Process Performance Analytics
- **Process Execution Instances & Step-Level Trace (`DocumentProcessInstance` - `DPIN`)** — Tracks each BPM execution run against a `Document` (`queued`, `running`, `waiting_approval`, `waiting_timer`, `completed`, `failed`, `cancelled`, `sla_breached`) with timestamps, SLA due dates, computed cycle time, rework count, and a structured node-by-node `step_trace_json` log. · seen in: Laserfiche Instance Tracking, Camunda Optimize, Alfresco History Services · priority: **table-stakes** · spine: `DocumentProcessInstance` (`DPIN`), FKs `DocumentProcessDefinition`, `Document`, `DocumentVersion`, `DocumentApprovalWorkflow`, `DocumentRoutingRule` · **buildable now**
- **Cycle Time, Throughput & SLA Breach Analytics** — Computed analytics board aggregating average/median/95th-percentile end-to-end cycle times, daily/weekly process throughput, active WIP backlog, and SLA breach rates segmented by process definition, document type, and `core.OrgUnit`. · seen in: Camunda Optimize, Laserfiche Process Metrics, Kissflow Dashboards · priority: **table-stakes** · spine: `process_analytics_dashboard` view querying `DocumentProcessInstance` · **buildable now**
- **Node & Role Bottleneck Heatmaps** — Aggregates `step_trace_json` stage durations and current wait states to pinpoint exact BPMN nodes, swimlane roles, or organizational units causing the longest queue delays and SLA expirations. · seen in: Camunda Optimize Heatmaps, DocuWare Workflow Monitor, Power Automate Process Mining · priority: **table-stakes** · spine: step-duration aggregator in `process_analytics_dashboard` · **buildable now**
- **Process Mining (Variant Discovery, Conformance & Rework Loops)** — Extracts normalized execution paths (`variant_signature`, e.g., `start→triage→xor_legal→approval→end`) from `DocumentProcessInstance`, measures happy-path vs. exception variant frequencies, highlights rework loops (`rework_count > 0`), and checks conformance against the published `DocumentProcessDefinition` graph. · seen in: Microsoft Power Automate Process Mining, Camunda Optimize, Appian Process Mining · priority: **differentiator** · spine: `DocumentProcessInstance.variant_signature`, `rework_count`, `step_trace_json` + process mining tab/view · **buildable now**

### Beyond the bullets
- **In-Repo BPM Execution Helper (`execute_process_for_document` / `evaluate_document_routing`)** — Synchronous, deterministic Python service functions that evaluate active `DocumentRoutingRule`s or step a `DocumentProcessInstance` forward (updating metadata, moving folders, optionally creating a 13.3 `DocumentApprovalWorkflow`, recording simulated webhook traces, and writing `DocumentAuditTrail` entries) so UI actions and tests drive real state transitions without needing Celery. · seen in: Activiti Java API, M-Files Event Handlers · priority: **common** · spine: `apps/documents/services/workflow_automation.py` (or view/model helpers) · **buildable now**
- **Process Instance Timeline & Step Progression Stepper** — Visual node progression timeline on `DocumentProcessInstance` detail showing executed nodes, durations, gateway branches taken, linked `DocumentApprovalWorkflow` (`DWF`) status, and manual "Advance Step / Simulate Next" operator controls. · seen in: Power Automate BPFs, Laserfiche Instance History · priority: **common** · spine: template component on `DocumentProcessInstance` detail · **buildable now**

---

## Recommended build scope (this pass — 1–4 models)

To cover all five `NavERP.md` 13.11 bullets deeply while respecting the 1–4-model build unit and keeping clean boundaries with `0.11`, `13.3`, `13.10`, `13.12`, and `13.15`, the recommended scope is **4 tenant-scoped `TenantNumbered` models** under `apps/documents/models/WorkflowAutomation/`:

### 1. `DocumentProcessDefinition` [`NUMBER_PREFIX = "DBPM"`]
- **File:** `apps/documents/models/WorkflowAutomation/DocumentProcessDefinitions.py`
- **Bullet covered:** Business Process Modeling (reusable BPMN 2.0–style blueprint, swimlanes, gateways, visual designer).
- **Fields & Choices justified by research:**
  - `name` (`CharField(max_length=200)`), `code` (`CharField(max_length=60)` — uppercase normalized, unique per `(tenant, code, version_number)`), `description` (`TextField(blank=True)`)
  - `process_category`: `intake_triage`, `lifecycle_automation`, `compliance_routing`, `contract_review`, `records_disposition`, `ocr_classification`, `custom`
  - `trigger_event`: `document_created`, `version_uploaded`, `status_changed`, `metadata_updated`, `ocr_completed`, `approval_completed`, `manual_trigger`, `webhook_inbound`
  - `target_document_type` (`CharField(max_length=40)`, blank=True, aligned to `Document.DOCUMENT_TYPE_CHOICES` or `"all"`)
  - `target_folder` (`ForeignKey("documents.DocumentFolder", null=True, blank=True, on_delete=models.SET_NULL, related_name="process_definitions")`)
  - `department` (`ForeignKey("core.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL, related_name="dms_process_definitions")`)
  - `owner` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dms_process_definitions")`)
  - `core_workflow_ref` (`ForeignKey("core.WorkflowDefinition", null=True, blank=True, on_delete=models.SET_NULL, related_name="dms_process_definitions")` — optional link to 0.11 registry)
  - `version_number` (`PositiveIntegerField(default=1)`), `status` (`draft`, `published`, `deprecated`, `archived`), `is_active` (`BooleanField(default=True, db_index=True)`)
  - `sla_target_hours` (`PositiveIntegerField(default=48)`)
  - `swimlanes_json` (`JSONField(default=list, blank=True)` — lanes with `id`, `name`, `role_id`/`org_unit_id`)
  - `nodes_json` (`JSONField(default=list, blank=True)` — BPMN nodes: `start_event`, `user_task`, `service_task`, `approval_subprocess`, `exclusive_gateway`, `parallel_gateway`, `inclusive_gateway`, `timer_event`, `webhook_task`, `end_event` with coordinates & SLA)
  - `transitions_json` (`JSONField(default=list, blank=True)` — directed edges with `from_node`, `to_node`, `label`, `is_default`, `condition`)
  - Derived telemetry (`editable=False`): `instance_count` (`PositiveIntegerField(default=0)`), `published_at` (`DateTimeField(null=True, blank=True)`)
- **CSS badges (L33 colour-named):** `draft` → `badge-slate`, `published` → `badge-green`, `deprecated` → `badge-amber`, `archived` → `badge-muted`.

### 2. `DocumentRoutingRule` [`NUMBER_PREFIX = "DRUL"`]
- **File:** `apps/documents/models/WorkflowAutomation/DocumentRoutingRules.py`
- **Bullets covered:** Document Routing & Distribution + Conditional Logic & Business Rules (metadata/hierarchy routing, if-then-else conditions, validation gates, automatic field population).
- **Fields & Choices justified by research:**
  - `name` (`CharField(max_length=200)`), `description` (`TextField(blank=True)`)
  - `process_definition` (`ForeignKey("documents.DocumentProcessDefinition", null=True, blank=True, on_delete=models.SET_NULL, related_name="routing_rules")`)
  - `core_rule_ref` (`ForeignKey("core.BusinessRule", null=True, blank=True, on_delete=models.SET_NULL, related_name="dms_routing_rules")` — optional link to 0.11 registry)
  - `rule_type`: `routing_distribution`, `conditional_branch`, `metadata_autofill`, `data_validation`, `escalation_fallback`, `lifecycle_transition`
  - `trigger_event`: `on_upload`, `on_metadata_change`, `on_ocr_complete`, `on_status_change`, `on_approval_decision`, `on_manual_eval`
  - `priority` (`PositiveIntegerField(default=100, db_index=True)`)
  - Scope filters: `source_folder` (`ForeignKey("documents.DocumentFolder", null=True, blank=True, related_name="source_routing_rules")`), `target_document_type` (`CharField(max_length=40, blank=True)`), `target_classification` (`CharField(max_length=20, blank=True)`)
  - Conditional logic: `condition_logic_mode` (`all_and`, `any_or`), `conditions_json` (`JSONField(default=list, blank=True)` — `[{source, field, op, value}]`), `else_branch_enabled` (`BooleanField(default=False)`), `else_action_json` (`JSONField(default=dict, blank=True)`)
  - Validation & auto-population: `validation_rules_json` (`JSONField(default=list, blank=True)` — mandatory metadata/threshold checks), `auto_populate_json` (`JSONField(default=dict, blank=True)` — `{document_fields: {...}, metadata_fields: {...}}`)
  - Distribution target & action: `route_action` (`move_to_folder`, `assign_role`, `assign_user`, `assign_org_unit_head`, `spawn_approval_workflow`, `create_document_task`, `populate_metadata`, `trigger_process`, `block_validation`), `destination_folder` (`ForeignKey("documents.DocumentFolder", null=True, blank=True, related_name="destination_routing_rules")`), `route_to_org_unit` (`ForeignKey("core.OrgUnit", null=True, blank=True, related_name="dms_routing_rules")`), `route_to_role` (`ForeignKey("accounts.Role", null=True, blank=True, related_name="dms_routing_rules")`), `route_to_user` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="assigned_dms_routing_rules")`)
  - `is_active` (`BooleanField(default=True, db_index=True)`), `owner` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dms_routing_rules")`)
  - Derived telemetry (`editable=False`): `execution_count` (`PositiveIntegerField(default=0)`), `match_count` (`PositiveIntegerField(default=0)`), `last_evaluated_at` (`DateTimeField(null=True, blank=True)`)
- **CSS badges (L33 colour-named):** `is_active` (`True` → `badge-green`, `False` → `badge-slate`); `rule_type` (`routing_distribution` → `badge-info`, `conditional_branch` → `badge-amber`, `metadata_autofill` → `badge-green`, `data_validation` → `badge-red`, `escalation_fallback` → `badge-amber`, `lifecycle_transition` → `badge-slate`).

### 3. `DocumentProcessInstance` [`NUMBER_PREFIX = "DPIN"`]
- **File:** `apps/documents/models/WorkflowAutomation/DocumentProcessInstances.py`
- **Bullets covered:** Business Process Modeling (execution), Document Routing & Distribution (runtime tracking), Process Performance Analytics (cycle time, throughput, bottleneck analysis, and process mining).
- **Fields & Choices justified by research:**
  - `process_definition` (`ForeignKey("documents.DocumentProcessDefinition", on_delete=models.PROTECT, related_name="instances")`)
  - `document` (`ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="process_instances")`)
  - `version` (`ForeignKey("documents.DocumentVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="process_instances")`)
  - `triggered_by_rule` (`ForeignKey("documents.DocumentRoutingRule", null=True, blank=True, on_delete=models.SET_NULL, related_name="triggered_instances")`)
  - `approval_workflow` (`ForeignKey("documents.DocumentApprovalWorkflow", null=True, blank=True, on_delete=models.SET_NULL, related_name="bpm_process_instances")` — links 13.11 BPM orchestration to 13.3 human sign-off)
  - `department` (`ForeignKey("core.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL, related_name="dms_process_instances")`)
  - `initiated_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="initiated_dms_process_instances")`)
  - `current_assignee` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_dms_process_instances")`)
  - `status`: `queued`, `running`, `waiting_approval`, `waiting_timer`, `completed`, `failed`, `cancelled`, `sla_breached`
  - `current_node_id` (`CharField(max_length=80, blank=True)`), `current_node_label` (`CharField(max_length=160, blank=True)`)
  - `started_at` (`DateTimeField(default=timezone.now, editable=False)`), `due_at` (`DateTimeField(null=True, blank=True, editable=False)`), `completed_at` (`DateTimeField(null=True, blank=True, editable=False)`)
  - `cycle_time_minutes` (`PositiveIntegerField(null=True, blank=True, editable=False)`)
  - `rework_count` (`PositiveSmallIntegerField(default=0, editable=False)`)
  - `is_sla_breached` (`BooleanField(default=False, editable=False, db_index=True)`)
  - `is_conformant` (`BooleanField(default=True, editable=False)` — process mining conformance vs published blueprint)
  - `variant_signature` (`CharField(max_length=500, blank=True, editable=False)` — normalized path key for process mining variant grouping)
  - `step_trace_json` (`JSONField(default=list, blank=True)` — chronological step entries with `node_id`, `node_type`, `lane`, `entered_at`, `exited_at`, `duration_minutes`, `outcome`)
  - `context_variables_json` (`JSONField(default=dict, blank=True)`), `error_message` (`TextField(blank=True)`)
- **CSS badges (L33 colour-named):** `queued` → `badge-slate`, `running` → `badge-info`, `waiting_approval` → `badge-amber`, `waiting_timer` → `badge-amber`, `completed` → `badge-green`, `failed` → `badge-red`, `cancelled` → `badge-muted`, `sla_breached` → `badge-red`.

### 4. `DocumentWebhookTrigger` [`NUMBER_PREFIX = "DWHK"`]
- **File:** `apps/documents/models/WorkflowAutomation/DocumentWebhookTriggers.py`
- **Bullet covered:** Integration Triggers & Webhooks (external event triggers, API callbacks, middleware connectivity).
- **Fields & Choices justified by research:**
  - `name` (`CharField(max_length=160)`), `description` (`TextField(blank=True)`)
  - `direction`: `outbound_webhook`, `inbound_webhook`, `middleware_callback`
  - `trigger_event`: `document.uploaded`, `document.status_changed`, `version.published`, `metadata.updated`, `ocr.completed`, `routing.matched`, `process.started`, `process.completed`, `process.sla_breached`, `approval.decided`, `inbound.trigger`
  - `process_definition` (`ForeignKey("documents.DocumentProcessDefinition", null=True, blank=True, on_delete=models.SET_NULL, related_name="webhook_triggers")` — optional process launched on inbound or emitted on outbound)
  - `connector_ref` (`ForeignKey("core.ConnectorDefinition", null=True, blank=True, on_delete=models.SET_NULL, related_name="dms_webhook_triggers")` — optional 0.13 catalog link)
  - `target_url` (`URLField(max_length=500, blank=True)` — validated against SSRF on form/model `clean()`: blocks loopback, RFC1918, link-local metadata IP, IPv6 ULA)
  - `http_method`: `post`, `put`, `patch`
  - `payload_format`: `json`, `cloudevents_json`
  - `custom_headers` (`JSONField(default=dict, blank=True)` — validated flat `{str: str}`, no `\r`/`\n`)
  - `payload_template_json` (`JSONField(default=dict, blank=True)`)
  - `filter_document_type` (`CharField(max_length=40, blank=True)`), `retry_policy_max` (`PositiveSmallIntegerField(default=5)`)
  - **Secret security (L20 & L25):** `signing_secret` (`CharField(max_length=512, blank=True, editable=False)` encrypted at rest via `apps.core.crypto.encrypt/decrypt`), `signing_secret_prefix` (`CharField(max_length=16, blank=True, editable=False)`). Excluded structurally from ModelForms; rotated via dedicated POST view using pop-once session reveal.
  - `is_active` (`BooleanField(default=True, db_index=True)`), `owner` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dms_webhook_triggers")`)
  - Derived telemetry (`editable=False`): `last_status` (`never_fired`, `simulated`, `queued`, `delivered`, `failed`), `last_fired_at` (`DateTimeField(null=True, blank=True)`), `fire_count` (`PositiveIntegerField(default=0)`), `failure_count` (`PositiveIntegerField(default=0)`), `delivery_history_json` (`JSONField(default=list, blank=True)` — ring buffer of recent simulated/recorded deliveries with HMAC signature headers & payload snapshots).
- **CSS badges (L33 colour-named):** `never_fired` → `badge-slate`, `simulated` → `badge-info`, `queued` → `badge-amber`, `delivered` → `badge-green`, `failed` → `badge-red`.

### Computed & Interactive Surfaces (Views)
1. **Visual BPMN Swimlane & Gateway Designer (`process_designer`)** — Interactive UI for `DocumentProcessDefinition` (`DBPM`) showing swimlanes, BPMN nodes, gateways, and transitions, plus graph validation & live SVG/flow diagram.
2. **Routing & Business Rule Simulator (`routing_rule_simulator`)** — Interactive test bench evaluating ordered `DocumentRoutingRule` (`DRUL`) conditions, validation checks, and metadata auto-fills against any tenant `Document` (`dry-run` or `apply`).
3. **Process Performance & Process Mining Dashboard (`process_analytics_dashboard`)** — Computed board over `DocumentProcessInstance` (`DPIN`) computing cycle time (avg/median/p95), throughput, SLA breach rate, node/role bottleneck latency, variant frequency table, conformance %, and rework hotspots.
4. **Webhook Diagnostics & Simulated Dispatch (`webhook_trigger_test_ping`, `webhook_trigger_rotate_secret`)** — Generates real HMAC-SHA256 signed payload previews (`status="simulated"`), records delivery history + `DocumentAuditTrail` entries, and safely rotates secrets with pop-once reveal.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Per-document review comments, 21 CFR Part 11 e-signatures, approval delegation/bypass** → **13.3 Document Approval & Review Workflow** (already built: `DocumentApprovalWorkflow`, `DocumentApprovalRequest`, `DocumentSignature`, `DocumentReviewComment`).
- **OCR extraction pipelines & custom metadata schema definitions** → **13.5 Metadata & Indexing** (already built: `MetadataSchema`, `DocumentMetadataValue`, `DocumentOcrJob`).
- **Retention clocks, cutoff rules, legal holds & destruction certificates** → **13.9 Records Management & Compliance** (already built).
- **System-wide immutable audit log & forensic UBA alerts** → **13.10 Audit Trail & Reporting** (already built; 13.11 writes events into `DocumentAuditTrail`).
- **Enterprise ERP/CRM connectors (SAP, NetSuite, Salesforce), Outlook/Gmail capture, OneDrive/Box sync, GraphQL & developer SDK** → **13.12 Integration & API Ecosystem**.
- **Mobile push approvals & biometric signing** → **13.13 Mobile Document Access**.
- **Long-term OAIS/PREMIS archival & format migration (PDF/A)** → **13.14 Document Archival & Long-Term Preservation**.
- **Drag-and-drop end-user Electronic Form Builder, kiosk intake & form-driven doc assembly** → **13.15 Electronic Forms & Data Capture**.
- **Contract clause negotiation, fallback positions & obligation alerts** → **13.16 Contract Lifecycle Management (CLM)**.
- **Translation workflows & localization memory** → **13.18 Document Translation & Localization**.

---

## Deferred (later passes / integrations)

- **Outbound HTTP Transport & Retry Worker (Celery / RQ)** — Consistent with **L55** (`scm` 4.19 / `projects` 7.18) and `core.Integration`, this pass performs **zero outbound HTTP** (`requests`/`urllib`/`httpx`). Webhook triggers store SSRF-validated endpoints, encrypted HMAC secrets, and run honest `simulated` dispatches until an asynchronous worker transport pass is enabled.
- **Background Cron / Timer Event Scheduler** — Consistent with `core.SlaRule`, there is no background scheduler process; timer nodes and SLA due timestamps (`due_at`) are stamped and evaluated dynamically on views and explicit advance/sweep actions rather than via background polling daemons.
- **LLM / Natural-Language Text-to-BPMN Process Generation** — Generative AI workflow drafting (seen in Kissflow, ProcessMaker, OpenText Aviator) is deferred until an AI gateway integration pass.
- **External Middleware SaaS OAuth Flows (Zapier / Make / MuleSoft / Boomi)** — Multi-step OAuth2 token exchange and external iPaaS marketplace adapters are deferred to **13.12 Integration & API Ecosystem**.
