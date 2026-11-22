# Research — Sub-module 13.3: Document Approval & Review Workflow (Module 13 — Document Management System, documents)

## Repo state checked first

- **LIVE_LINKS built so far in module 13:**
  - `13.1` (Document Creation & Authoring):
    - `Template Library & Standardization`: `documents:template_list` (`DocumentTemplate`)
    - `Rich Text & Collaborative Editing`: `documents:draft_list` (`DocumentDraft`)
    - `Version Zero & Draft Management`: `documents:draft_list` (`DocumentDraft`)
    - `Embedded Media & Objects`: `documents:template_section_list` (`TemplateSection`)
    - `Offline Authoring & Sync`: `documents:draft_list` (`DraftCollaboration`)
  - `13.2` (Version Control & Revision Management):
    - `Automatic Version Numbering`: `documents:document_version_list` (`DocumentVersion`)
    - `Check-in / Check-out Mechanism`: `documents:document_lock_list` (`DocumentLock`)
    - `Version Comparison & Diff View`: `documents:document_version_compare` (`DocumentVersion`)
    - `Branching & Parallel Versions`: `documents:document_branch_list` (`DocumentBranch`)
    - `Version History & Rollback`: `documents:document_version_list` (`DocumentVersion`)
    - `Documents`: `documents:document_list` (`Document`)

- **Sibling models available to FK in `apps/documents/` (verified via grep):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Core logical document master record containing title, slug, classification, status, owner, department, version tracking.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Immutable physical file revision snapshot with major/minor/patch numbering, SHA-256 checksum, file payload.
  - `documents.DocumentTemplate` (`apps/documents/models/DocumentAuthoring/DocumentTemplates.py:31`, `NUMBER_PREFIX = "DTMPL"`): Pre-approved document templates.
  - `documents.DocumentDraft` (`apps/documents/models/DocumentAuthoring/DocumentDrafts.py:38`, `NUMBER_PREFIX = "DDFT"`): Working authoring drafts.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): System users, initiators, approvers, signers, delegates.
  - `accounts.Role` (`apps/accounts/models.py:35`, `class Role(models.Model)`): Tenant-scoped roles used for role-based approval step routing (e.g., Legal Counsel, Quality Manager, Finance Director).
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Departmental organization units for cross-departmental approval routing.
  - `core.WorkflowDefinition` & `core.WorkflowStep` (`apps/core/models/Workflow.py:class WorkflowDefinition`, `class WorkflowStep`): Platform process metadata registry documenting workflow definitions across modules. As documented in `apps/core/models/Workflow.py`, individual modules implement their own domain-specific approval engines.
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing atomic concurrency-safe number generation (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DWF` (`DocumentApprovalWorkflow`): Verified free (0 matches in repo).
  - `DAPR` (`DocumentApprovalRequest`): Verified free (0 matches in repo).
  - `DSIG` (`DocumentSignature`): Verified free (0 matches in repo).
  - `DREV` (`DocumentReviewComment`): Verified free (0 matches in repo).
  - Sibling prefixes safely preserved: `DOC` (Document), `DVER` (DocumentVersion), `DLOCK` (DocumentLock), `DBRN` (DocumentBranch), `DTMPL` (DocumentTemplate), `DSEC` (TemplateSection), `DDFT` (DocumentDraft), `DCMT` (DraftCollaboration).

---

## Leaders surveyed (with source links)

1. **DocuSign (eSignature & IAM Agreement Workflows)** — Global market leader in electronic signature capture, agreement automation, and document approval routing. Supports sequential, parallel, and conditional envelope routing, recipient action types (Approve, Sign, View), in-flight task delegation, automated reminders/timeouts, and tamper-evident Certificates of Completion.
   - *Source:* https://www.docusign.com/products/electronic-signature · https://support.docusign.com/s/document-item?bundleId=gmg1656614452092&topicId=bcf1578456488349.html
2. **Adobe Acrobat Sign** — Premier enterprise electronic signature and document approval solution. Features multi-tier approval chains, sequential and parallel distribution ("Complete in Any Order"), reviewer-to-proxy delegation, auto-escalation triggers on expired SLAs, and cryptographically verified digital signature audit trails.
   - *Source:* https://www.adobe.com/sign/features.html · https://helpx.adobe.com/sign/using/set-up-workflows.html
3. **Veeva Vault (QualityDocs & Life Sciences Workflow)** — The benchmark standard for FDA 21 CFR Part 11 compliant document lifecycles and review routing. Enforces multi-stage approvals, mandatory credential re-authentication for electronic signatures with explicit "Signature Meaning" declarations, browser-based annotation layers with threaded discussions, out-of-office delegation with full audit tracing, and mandatory resolution of all review comments prior to approval transition.
   - *Source:* https://www.veeva.com/products/vault-qualitydocs/ · https://platform.veevavault.help/en/gr/40149/
4. **OpenText Documentum D2** — Enterprise content management standard in heavily regulated sectors. Offers configurable approval workflows, document package routing, lifecycle state interlocks (Draft → In Review → Approved → Effective), 21 CFR Part 11 e-signatures with reason-for-signing metadata, digital markup/annotation layers with resolution tracking, and task delegation for absent reviewers.
   - *Source:* https://www.opentext.com/products/documentum-d2 · https://www.opentext.com/products/documentum-life-sciences
5. **PandaDoc** — Fast-growing document automation and workflow platform. Employs template-level approval chains with multi-stage review gates, approver groups (first-to-respond or unanimous consensus), conditional triggers based on document metadata, inline review comments and rejection return loops, and visual approval tracking dashboards to uncover bottlenecks.
   - *Source:* https://www.pandadoc.com/approval-workflows/ · https://support.pandadoc.com/hc/en-us/articles/360035882674-Approval-workflow
6. **M-Files** — Metadata-driven enterprise information management system. Features workflow state transitions governed by metadata rules, electronic signature checkpoints requiring user credential re-entry, workflow assignments with out-of-office delegation and substitute approvers, and tamper-evident event logging.
   - *Source:* https://www.m-files.com/product/document-management/ · https://userguide.m-files.com/user-guide/latest/eng/Electronic_signatures.html
7. **Microsoft SharePoint & Power Automate (Approvals)** — Widely deployed enterprise workflow and document routing service. Provides sequential and parallel approval branches (Wait for all vs. Wait for first response), ISO 8601 timeout policies with automated escalation to managers, reassignment/delegation handling, reviewer response comment logging, and centralized approval status dashboards.
   - *Source:* https://learn.microsoft.com/en-us/power-automate/sequential-approvals · https://learn.microsoft.com/en-us/power-automate/modern-approvals
8. **Conga CLM (Conga Approvals & Conga Sign)** — Enterprise contract lifecycle and approval management engine. Utilizes Delegation of Authority (DOA) approval matrices, multi-tiered sequential/parallel approval steps, quorum and unanimous group policies, out-of-office delegate rerouting, SLA auto-escalation upon timeout, document annotation layers, and native tamper-evident e-signing.
   - *Source:* https://conga.com/products/contract-lifecycle-management · https://documentation.conga.com/cclm/latest/approvals-management
9. **Box (Box Relay & Box Sign)** — Cloud content management workflow automation engine. Supports metadata-driven conditional routing, sequential and parallel review/approval steps, in-previewer annotations (highlighting, sticky notes, callouts), native electronic signature capture, task delegation, and centralized task center.
   - *Source:* https://www.box.com/relay · https://www.box.com/sign

---

## Feature catalog (this sub-module only)

### Visual Workflow Designer
- **Sequential Approval Routing** — Routes documents step-by-step through an ordered chain of reviewers where each tier must complete before the next tier is unlocked (e.g. Lead Author → Peer Reviewer → Department Head → Legal Counsel). · seen in: DocuSign, Adobe Acrobat Sign, Power Automate, PandaDoc, Conga CLM · priority: **table-stakes** · spine: `DocumentApprovalWorkflow` + `DocumentApprovalRequest` (`DWF`, `DAPR`) · **buildable now**
- **Parallel Approval Routing** — Dispatches review/approval requests simultaneously to multiple participants or departments with configurable quorum rules: *Unanimous* (every assigned reviewer must approve) or *First-Response* (first affirmative response advances the step). · seen in: DocuSign, Power Automate, Adobe Sign, Box Relay · priority: **table-stakes** · spine: `DocumentApprovalRequest.routing_rule` (`unanimous_all` vs `first_response_any`) · **buildable now**
- **Conditional Approval Paths & Threshold Rules** — Evaluates document metadata (e.g., classification = `confidential` or `restricted`, document_type = `contract` or `policy`) to dynamically append specialized governance approval steps (e.g. Legal Compliance or Information Security review). · seen in: DocuSign, Conga CLM, PandaDoc, Box Relay · priority: **common** · spine: `DocumentApprovalWorkflow.workflow_type` (`conditional_matrix`) · **buildable now**
- **Multi-Stage Approval Pipelines** — Organizes complex review chains into discrete named phases or milestones (e.g., Stage 1: Technical Review, Stage 2: Quality & Compliance Review, Stage 3: Executive e-Signature). · seen in: Veeva Vault, Documentum D2, Conga CLM · priority: **table-stakes** · spine: `DocumentApprovalRequest.step_sequence` + `step_name` + `step_type` · **buildable now**
- **Visual Pipeline Progress Stepper** — UI component displaying sequential/parallel stages, indicating node states (`completed`, `active_in_progress`, `pending`, `escalated`, `bypassed`). · seen in: DocuSign, PandaDoc, Power Automate · priority: **common** · spine: template component driven by `DocumentApprovalRequest` querysets · **buildable now**

### Electronic Signature Capture
- **Click-to-Sign Electronic Signature** — Fast, legally binding electronic sign-off where an authenticated user clicks to adopt their signature, applying an unalterable timestamped approval mark. · seen in: DocuSign, Adobe Acrobat Sign, PandaDoc, signNow, Box Sign · priority: **table-stakes** · spine: `DocumentSignature.signature_type` (`click_to_sign`) (`DSIG`) · **buildable now**
- **21 CFR Part 11 / Regulatory Signature Meaning** — Regulatory standard requiring each signer to explicitly select and confirm the legal meaning of their signature (e.g. `approval` "I approve this document", `authorship` "I author and verify the technical accuracy", `review` "I have reviewed and agree", `technical_verification` "I verify technical feasibility", `legal_signoff` "I confirm legal compliance", `witness` "I witness this transaction"). · seen in: Veeva Vault, OpenText Documentum D2, M-Files · priority: **table-stakes** (critical for ERP compliance) · spine: `DocumentSignature.signature_meaning` · **buildable now**
- **Cryptographic Document Checksum Binding** — Generates and binds an immutable SHA-256 cryptographic digest of the document/version file content at the precise moment of signing, guaranteeing tamper-evident non-repudiation. · seen in: DocuSign, Adobe Sign, Veeva Vault, signNow · priority: **table-stakes** · spine: `DocumentSignature.document_checksum` + `signature_token` · **buildable now**
- **Drawn / Biometric & Security PIN Capture** — Allows signers to draw a stylus/touch signature glyph or confirm identity via security PIN re-authentication before stamping the signature manifest. · seen in: DocuSign, Adobe Sign, Veeva Vault, signNow · priority: **common** · spine: `DocumentSignature.signature_glyph` + `signature_type` (`biometric_pin`) · **buildable now**
- **Digital Certificate Verification Token** — Records public PKI / certificate serial hashes and verification tokens verifying identity authenticity. · seen in: Adobe Acrobat Sign, OpenText Documentum D2, M-Files · priority: **common** · spine: `DocumentSignature.certificate_serial` + `signature_type` (`digital_cert`) · **buildable now**
- **Comprehensive Signer Audit Metadata** — Records exact UTC timestamp, authenticated user ID, signer name, email, job title, IP address, and browser user agent with the signature record. · seen in: DocuSign, Adobe Sign, Veeva Vault, signNow · priority: **table-stakes** · spine: `DocumentSignature` model fields · **buildable now**

### Delegation & Escalation Rules
- **Task Delegation to Authorized Substitute** — Allows an assigned reviewer/approver who is unavailable or out-of-office to delegate their pending task to an authorized proxy or colleague, capturing the delegation reason, timestamp, and preserving dual audit attribution (original approver vs actual delegate). · seen in: DocuSign, Veeva Vault, Documentum D2, Power Automate, Conga CLM, Box · priority: **table-stakes** · spine: `DocumentApprovalRequest.is_delegated`, `delegated_to` (`auth.User`), `delegation_reason`, `delegated_at` · **buildable now**
- **SLA Timeout Escalation** — Defines target turnaround durations (SLA hours); when an approval sits unacted past the deadline, the workflow engine automatically flags the bottleneck, updates the request to `escalated`, and reassigns or notifies the designated supervisor/escalation contact. · seen in: Power Automate, Adobe Sign, Conga CLM, PandaDoc · priority: **table-stakes** · spine: `DocumentApprovalRequest.due_at`, `is_escalated`, `escalated_to`, `escalated_at`, `escalation_notes` · **buildable now**
- **Emergency Approval Bypass** — Controlled administrative override mechanism allowing designated compliance officers or tenant executives to bypass a stalled approval node during business-critical emergencies, with mandatory recorded justification, user identification, and permanent audit logging. · seen in: OpenText Documentum D2, Veeva Vault, Conga CLM · priority: **common** · spine: `DocumentApprovalWorkflow.emergency_bypassed`, `bypass_reason`, `bypassed_by` (`auth.User`) · **buildable now**
- **Rejection & Revision Return Loop** — When an approver rejects a document, the request captures mandatory rejection comments, transitions the workflow to `rejected`, and updates the parent `Document` / `DocumentVersion` status to allow authors to remediate issues and resubmit. · seen in: PandaDoc, Veeva Vault, Documentum D2, M-Files · priority: **table-stakes** · spine: `DocumentApprovalRequest.rejection_reason` + workflow state transition handler · **buildable now**

### Review Comments & Annotation
- **Multi-Layer Document Annotations** — Reviewers mark up documents with multiple annotation types: inline commentary, text highlights, redline suggestion strikethroughs, sticky notes, and drawing callout pins. · seen in: Veeva Vault, OpenText Documentum D2, Box, Adobe Acrobat · priority: **table-stakes** · spine: `DocumentReviewComment.annotation_type` (`DREV`) · **buildable now**
- **Page & Location Geometry Tracking** — Anchors annotations to specific document coordinates, page numbers, or highlighted text snippets for exact visual placement during review. · seen in: Veeva Vault, Documentum D2, Box, Adobe Acrobat · priority: **table-stakes** · spine: `DocumentReviewComment.page_number`, `coordinate_ref`, `selected_text` · **buildable now**
- **Threaded Review Discussions** — Hierarchical parent-child commenting allowing authors and reviewers to debate revisions, clarify requirements, and achieve consensus directly on the document version. · seen in: Veeva Vault, Box, PandaDoc, Google Docs · priority: **table-stakes** · spine: `DocumentReviewComment.parent` (self FK, `related_name="replies"`) · **buildable now**
- **Resolution Tracking & Approval Interlock** — Categorizes comment states (`open`, `addressed`, `resolved`, `dismissed`) with resolver tracking. Enables an enterprise governance rule where all blocking annotations must be marked `resolved` before the document workflow is permitted to proceed to final approval. · seen in: Veeva Vault, OpenText Documentum D2 · priority: **differentiator** (distinguishes NavERP DMS as a true enterprise-grade system) · spine: `DocumentReviewComment.is_blocking`, `status`, `resolved_by`, `resolved_at`, `resolution_notes` · **buildable now**

### Approval Dashboard & Status Tracking
- **Unified Approvals Dashboard** — Centralized dashboard displaying pending approvals assigned to the current user, awaiting my e-signature, approvals initiated by me, and recent workflow history. · seen in: DocuSign, Adobe Sign, Power Automate Approvals Center, PandaDoc · priority: **table-stakes** · spine: Filtered views on `DocumentApprovalRequest` and `DocumentApprovalWorkflow` · **buildable now**
- **Bottleneck Identification & SLA Aging Analytics** — Highlights stalled approval requests exceeding target turnaround hours, identifies chronic approval bottlenecks by role/department, and computes aging hours (`now - created_at`). · seen in: Power Automate, PandaDoc, Conga CLM, DocuSign IAM · priority: **common** · spine: Query aggregations on `DocumentApprovalRequest` (`due_at`, `turnaround_hours`) · **buildable now**
- **Cycle-Time Analytics** — Computes end-to-end duration from workflow initiation to final approval/e-signature, broken down by document type, department, and approval stage. · seen in: DocuSign, PandaDoc, Veeva Vault · priority: **common** · spine: Computed view metrics from `DocumentApprovalWorkflow` (`started_at`, `completed_at`) · **buildable now**

### Beyond the Bullets
- **Certificate of Completion / Signature Manifest** — Generated summary view and exportable manifest detailing all signers, signature meanings, UTC timestamps, IP addresses, and SHA-256 document checksums as proof of legal execution. · seen in: DocuSign, signNow, Adobe Acrobat Sign · priority: **differentiator** · spine: Dedicated view rendering `DocumentSignature` manifest for a document version · **buildable now**
- **Role-Based Approver Resolution** — Step routing assigned to an abstract organizational role (`accounts.Role`, e.g. "Legal Counsel", "Quality Assurance Lead") allowing any qualified tenant user holding that role to pick up and approve the request. · seen in: Conga CLM, M-Files, Documentum D2 · priority: **common** · spine: `DocumentApprovalRequest.assigned_role` (`accounts.Role`) · **buildable now**

---

## Recommended build scope (this pass — 1–4 models)

To fully cover the 5 feature bullets of sub-module 13.3 while respecting the strict 1–4 model build unit, the following 4 tenant-scoped models are recommended under `apps/documents/models/ApprovalWorkflow/`:

### 1. `DocumentApprovalWorkflow` [NUMBER_PREFIX = "DWF"]
- **Role:** The parent approval workflow instance governing a document revision through its multi-stage review and sign-off pipeline.
- **Fields & Choices justified by research:**
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="approval_workflows")` — root document.
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="approval_workflows")` — specific revision snapshot being reviewed.
  - `title`: `CharField(max_length=255)` — workflow title / purpose.
  - `workflow_type`: `CharField(max_length=30, choices=WORKFLOW_TYPE_CHOICES, default="sequential")` — (`sequential`, `parallel`, `conditional_matrix`).
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="in_progress", db_index=True)` — (`draft`, `in_progress`, `approved`, `rejected`, `cancelled`, `bypassed`).
  - `current_step_sequence`: `PositiveIntegerField(default=1)` — pointer to currently active stage.
  - `total_steps`: `PositiveIntegerField(default=1)` — total number of configured steps.
  - `target_sla_hours`: `PositiveIntegerField(default=48)` — target turnaround for cycle-time tracking.
  - `require_all_comments_resolved`: `BooleanField(default=True)` — interlock enforcing resolution of all blocking review comments before final approval.
  - `allow_delegation`: `BooleanField(default=True)` — flag permitting reviewers to reassign tasks.
  - `emergency_bypassed`: `BooleanField(default=False)` — flag indicating administrative bypass.
  - `bypass_reason`: `TextField(blank=True)` — mandatory justification for emergency override.
  - `bypassed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bypassed_document_workflows")` — executive who authorized bypass.
  - `initiated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="initiated_document_workflows")` — workflow initiator.
  - `started_at`: `DateTimeField(auto_now_add=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **FKs:** `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `settings.AUTH_USER_MODEL`.

### 2. `DocumentApprovalRequest` [NUMBER_PREFIX = "DAPR"]
- **Role:** Individual step or participant task within an approval workflow, handling assignment, quorum rules, delegation, and escalation.
- **Fields & Choices justified by research:**
  - `workflow`: `ForeignKey("documents.DocumentApprovalWorkflow", on_delete=models.CASCADE, related_name="requests")` — parent workflow.
  - `step_sequence`: `PositiveIntegerField(default=1, db_index=True)` — stage sequence number.
  - `step_name`: `CharField(max_length=150)` — descriptive stage name (e.g., "Technical Review", "Legal Approval").
  - `step_type`: `CharField(max_length=30, choices=STEP_TYPE_CHOICES, default="approval")` — (`review`, `approval`, `e_sign`, `acknowledgement`).
  - `routing_rule`: `CharField(max_length=30, choices=ROUTING_RULE_CHOICES, default="first_response_any")` — (`unanimous_all`, `first_response_any`, `majority`).
  - `assigned_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="document_approval_requests")` — named user approver.
  - `assigned_role`: `ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_approval_requests")` — role-based assignment.
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="pending", db_index=True)` — (`pending`, `under_review`, `approved`, `rejected`, `delegated`, `escalated`, `bypassed`, `cancelled`).
  - `due_at`: `DateTimeField(null=True, blank=True)` — SLA target timestamp for timeout detection.
  - `responded_at`: `DateTimeField(null=True, blank=True)` — timestamp of decision.
  - `turnaround_hours`: `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` — computed turnaround for bottleneck analytics.
  - `decision_comments`: `TextField(blank=True)` — approval notes or feedback.
  - `rejection_reason`: `TextField(blank=True)` — required explanation upon rejection.
  - `is_delegated`: `BooleanField(default=False)` — delegation indicator.
  - `delegated_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delegated_document_approvals")` — substitute delegate user.
  - `delegation_reason`: `CharField(max_length=255, blank=True)` — reason for delegation (e.g., out-of-office).
  - `delegated_at`: `DateTimeField(null=True, blank=True)`
  - `is_escalated`: `BooleanField(default=False)` — timeout escalation indicator.
  - `escalated_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="escalated_document_approvals")` — escalation contact.
  - `escalated_at`: `DateTimeField(null=True, blank=True)`
  - `escalation_notes`: `TextField(blank=True)`
- **FKs:** `core.Tenant`, `DocumentApprovalWorkflow`, `settings.AUTH_USER_MODEL`, `accounts.Role`.

### 3. `DocumentSignature` [NUMBER_PREFIX = "DSIG"]
- **Role:** Electronic signature record implementing 21 CFR Part 11 / ESIGN / eIDAS regulatory compliance with tamper-evident cryptographic checksums.
- **Fields & Choices justified by research:**
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="signatures")`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="signatures")`
  - `approval_request`: `ForeignKey("documents.DocumentApprovalRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="signatures")`
  - `signer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_signatures")`
  - `signer_name`: `CharField(max_length=150)` — snapshot of full legal name.
  - `signer_title`: `CharField(max_length=120, blank=True)` — job title at signing time.
  - `signer_email`: `EmailField(blank=True)` — email at signing time.
  - `signature_type`: `CharField(max_length=30, choices=SIGNATURE_TYPE_CHOICES, default="click_to_sign")` — (`click_to_sign`, `digital_cert`, `biometric_pin`).
  - `signature_meaning`: `CharField(max_length=40, choices=SIGNATURE_MEANING_CHOICES, default="approval")` — (`approval`, `authorship`, `review`, `technical_verification`, `legal_signoff`, `witness`).
  - `document_checksum`: `CharField(max_length=64, help_text="SHA-256 hash of document version at signing time")`
  - `signature_token`: `CharField(max_length=128, unique=True, help_text="Cryptographic signature verification token / UUID")`
  - `signature_glyph`: `TextField(blank=True, help_text="Drawn signature path data or SVG snippet")`
  - `certificate_serial`: `CharField(max_length=100, blank=True, help_text="Digital X.509 or eIDAS certificate identifier")`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `user_agent`: `CharField(max_length=255, blank=True)`
  - `signed_at`: `DateTimeField(auto_now_add=True)`
  - `is_valid`: `BooleanField(default=True)`
- **FKs:** `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `DocumentApprovalRequest`, `settings.AUTH_USER_MODEL`.

### 4. `DocumentReviewComment` [NUMBER_PREFIX = "DREV"]
- **Role:** Rich review annotations, inline markup, threaded discussions, and resolution tracking.
- **Fields & Choices justified by research:**
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="review_comments")`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_comments")`
  - `workflow`: `ForeignKey("documents.DocumentApprovalWorkflow", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_comments")`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_review_comments")`
  - `annotation_type`: `CharField(max_length=30, choices=ANNOTATION_TYPE_CHOICES, default="inline_comment")` — (`inline_comment`, `highlight`, `redline`, `sticky_note`, `drawing_callout`).
  - `page_number`: `PositiveIntegerField(default=1)`
  - `coordinate_ref`: `CharField(max_length=255, blank=True, help_text="Coordinates 'x,y,w,h' or DOM text anchor")`
  - `selected_text`: `TextField(blank=True, help_text="Highlighted or quoted snippet")`
  - `content`: `TextField()` — comment or markup note.
  - `parent`: `ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")` — threaded replies.
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="open", db_index=True)` — (`open`, `addressed`, `resolved`, `dismissed`).
  - `is_blocking`: `BooleanField(default=False, help_text="Blocks workflow approval until marked resolved")`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_document_comments")`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `resolution_notes`: `TextField(blank=True)`
- **FKs:** `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `DocumentApprovalWorkflow`, `settings.AUTH_USER_MODEL`, `self`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Folder-Level Access Inheritance & Repository Storage Quotas** → **13.4 Document Storage & Repository**: Physical storage tiering, nested folder taxonomy, storage quota management belong to 13.4.
- **Custom Metadata Schemas & Automated OCR Indexing** → **13.5 Metadata & Indexing**: Document metadata field definitions, auto-tagging, OCR extraction pipelines belong to 13.5.
- **Faceted Full-Text Search & Saved Search Alerts** → **13.6 Search & Discovery**: Cross-document faceted search, search alerts belong to 13.6.
- **Dynamic Watermarking & DRM Copy/Paste Protection** → **13.7 Document Security & Access Control**: Real-time watermark stamping ("CONFIDENTIAL - APPROVED BY [USER]"), encryption-at-rest, DLP rules belong to 13.7.
- **External Guest Link Sharing & Expiration Dates** → **13.8 Collaboration & Sharing**: Public shareable links, guest reviewer portals belong to 13.8.
- **System-Wide DMS Event Audit Log & Compliance Certification** → **13.10 Audit Trail & Reporting**: Global repository activity audit logs, periodic ISO/GxP compliance reporting belong to 13.10.
- **Contract Clauses, Fallback Negotiation & Obligation Tracking** → **13.16 Contract Lifecycle Management (CLM)**: Sell-side and buy-side contract assembly, clause deviation analysis, milestone SLA tracking belong to 13.16.

---

## Deferred (later passes / integrations)

- **Hardware Security Module (HSM) PKCS#11 Integration** — Storing cryptographic signing keys on physical hardware appliances is deferred to external enterprise security integrations.
- **WebAuthn / FIDO2 Biometric Hardware Handshake** — Hardware-level biometric sensors (e.g. fingerprint scanner, Apple TouchID) are modeled via biometric confirmation tokens; direct browser WebAuthn API handshakes are deferred to future frontend enhancements.
- **Third-Party External e-Signature Cloud Gateways** — API connectors to send documents externally to DocuSign / Adobe Sign SaaS accounts are deferred to **13.12 Integration & APIs**.
- **Real-Time WebRTC / WebSocket Collaborative Annotation Sync** — Live multi-user cursor tracking and synchronous live annotations are deferred to **13.8 Collaboration & Sharing** (sub-module 13.3 builds robust HTTP/HTMX-driven asynchronous review annotations).
