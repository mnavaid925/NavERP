# Module 13.3 Pre-Build Contract — Document Approval & Review Workflow (`apps/documents/`)

> Frozen in Phase 3.1 before any Phase 3.2 scaffolding or entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.3"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0005_...`)
- **Package Directories**:
  - `apps/documents/models/ApprovalWorkflow/`
  - `apps/documents/forms/ApprovalWorkflow/`
  - `apps/documents/views/ApprovalWorkflow/`
  - `apps/documents/urls/ApprovalWorkflow/`
  - `templates/documents/approval_workflow/{document_approval_workflow,document_approval_request,document_signature,document_review_comment}/{list,detail,form}.html` + `designer.html`, `manifest.html`, `verify.html`, `approval_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"submit"`, `"approve"`, `"reject"`, `"delegate"`, `"escalate"`, `"sign"`, `"resolve"`, `"bypass"`, `"cancel"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `accounts.Role`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `documents.DocumentApprovalWorkflow`, `documents.DocumentApprovalRequest`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/ApprovalWorkflow/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentApprovalWorkflow` (`DocumentApprovalWorkflows.py`)
- **`NUMBER_PREFIX`**: `"DWF"`
- **`Meta.ordering`**: `["-created_at", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Approval Workflow"` / `"Document Approval Workflows"`
- **Choices & Badge Maps**:
  - `WORKFLOW_TYPE_CHOICES` (`max_length=30`):
    - `("sequential", "Sequential (Step-by-Step)")`
    - `("parallel", "Parallel (All Reviewers Simultaneously)")`
    - `("conditional", "Conditional (Rules & Criteria Based)")`
    - `("hybrid", "Hybrid Multi-Tier")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft Definition")`
    - `("pending", "In Progress / Pending Approvals")`
    - `("approved", "Fully Approved")`
    - `("rejected", "Rejected")`
    - `("escalated", "Escalated")`
    - `("bypassed", "Emergency Bypassed")`
    - `("cancelled", "Cancelled")`
  - `URGENCY_CHOICES` (`max_length=20`):
    - `("low", "Low")`
    - `("medium", "Medium / Standard")`
    - `("high", "High")`
    - `("urgent", "Critical / Expedited")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"pending": "badge-amber"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
    - `"escalated": "badge-amber"`
    - `"bypassed": "badge-info"`
    - `"cancelled": "badge-muted"`
  - `URGENCY_CSS`:
    - `"low": "badge-muted"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"urgent": "badge-red"`
  - `WORKFLOW_TYPE_CSS`:
    - `"sequential": "badge-info"`
    - `"parallel": "badge-slate"`
    - `"conditional": "badge-amber"`
    - `"hybrid": "badge-green"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="approval_workflows", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="approval_workflows")`
  - `title`: `CharField(max_length=255)`
  - `workflow_type`: `CharField(max_length=30, choices=WORKFLOW_TYPE_CHOICES, default="sequential", db_index=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `urgency`: `CharField(max_length=20, choices=URGENCY_CHOICES, default="medium", db_index=True)`
  - `current_stage`: `PositiveIntegerField(default=1)`
  - `total_stages`: `PositiveIntegerField(default=1)`
  - `target_turnaround_hours`: `PositiveIntegerField(default=48, help_text="SLA hours allowed for complete workflow")`
  - `initiator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="initiated_document_workflows")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_approval_workflows")`
  - `due_date`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `requires_all_comments_resolved`: `BooleanField(default=True, help_text="Blocks final approval until all review comments are marked resolved")`
  - `allow_emergency_bypass`: `BooleanField(default=False, help_text="Permits authorized managers to bypass remaining approval stages")`
  - `bypass_reason`: `TextField(blank=True)`
  - `bypassed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bypassed_document_workflows")`
  - `definition_json`: `TextField(blank=True, default="{}", help_text="Visual workflow designer serialized JSON node graph")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dwf_ten_num_uniq")` (21 chars)
  - `models.Index(fields=["tenant", "status"], name="doc_dwf_tnt_stat_idx")` (20 chars)
  - `models.Index(fields=["tenant", "document", "status"], name="doc_dwf_tnt_doc_stat_idx")` (24 chars)
  - `models.Index(fields=["tenant", "initiator"], name="doc_dwf_tnt_init_idx")` (20 chars)

### 1.2 `DocumentApprovalRequest` (`DocumentApprovalRequests.py`)
- **`NUMBER_PREFIX`**: `"DAPR"`
- **`Meta.ordering`**: `["workflow", "stage_number", "order", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Approval Request"` / `"Document Approval Requests"`
- **Choices & Badge Maps**:
  - `STAGE_TYPE_CHOICES` (`max_length=30`):
    - `("sequential", "Sequential Step")`
    - `("parallel_all", "Parallel - Unanimous (All Must Approve)")`
    - `("parallel_first", "Parallel - First to Respond")`
    - `("peer_review", "Peer Review & Critique")`
    - `("final_signoff", "Final Executive Sign-Off")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("pending", "Pending Action")`
    - `("approved", "Approved")`
    - `("rejected", "Rejected")`
    - `("delegated", "Delegated to Peer")`
    - `("escalated", "Escalated on Timeout")`
    - `("bypassed", "Bypassed")`
    - `("cancelled", "Cancelled")`
  - `STATUS_CSS`:
    - `"pending": "badge-amber"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
    - `"delegated": "badge-info"`
    - `"escalated": "badge-amber"`
    - `"bypassed": "badge-slate"`
    - `"cancelled": "badge-muted"`
  - `STAGE_TYPE_CSS`:
    - `"sequential": "badge-info"`
    - `"parallel_all": "badge-slate"`
    - `"parallel_first": "badge-amber"`
    - `"peer_review": "badge-info"`
    - `"final_signoff": "badge-green"`
- **Fields (exact names & types)**:
  - `workflow`: `ForeignKey("documents.DocumentApprovalWorkflow", on_delete=models.CASCADE, related_name="approval_requests", db_index=True)`
  - `stage_number`: `PositiveIntegerField(default=1, db_index=True)`
  - `stage_name`: `CharField(max_length=120, default="Review & Approval")`
  - `stage_type`: `CharField(max_length=30, choices=STAGE_TYPE_CHOICES, default="sequential")`
  - `order`: `PositiveIntegerField(default=1)`
  - `approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_approval_requests")`
  - `approver_role`: `ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_approval_requests")`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="pending", db_index=True)`
  - `decision_comments`: `TextField(blank=True)`
  - `decided_at`: `DateTimeField(null=True, blank=True)`
  - `due_date`: `DateTimeField(null=True, blank=True)`
  - `delegated_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delegated_document_approval_requests")`
  - `delegation_reason`: `TextField(blank=True)`
  - `delegated_at`: `DateTimeField(null=True, blank=True)`
  - `is_escalated`: `BooleanField(default=False, db_index=True)`
  - `escalated_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="escalated_document_approval_requests")`
  - `escalation_reason`: `TextField(blank=True)`
  - `escalated_at`: `DateTimeField(null=True, blank=True)`
  - `reminder_sent_count`: `PositiveIntegerField(default=0)`
  - `last_reminder_at`: `DateTimeField(null=True, blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dapr_ten_num_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "status"], name="doc_dapr_tnt_stat_idx")` (21 chars)
  - `models.Index(fields=["tenant", "approver", "status"], name="doc_dapr_tnt_appr_stat_idx")` (26 chars)
  - `models.Index(fields=["tenant", "workflow", "stage_number"], name="doc_dapr_tnt_wf_stg_idx")` (24 chars)

### 1.3 `DocumentSignature` (`DocumentSignatures.py`)
- **`NUMBER_PREFIX`**: `"DSIG"`
- **`Meta.ordering`**: `["-signed_at", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Signature"` / `"Document Signatures"`
- **Choices & Badge Maps**:
  - `SIGNATURE_TYPE_CHOICES` (`max_length=30`):
    - `("click_to_sign", "Click-to-Sign (Standard Electronic)")`
    - `("digital_cert", "Digital Certificate (X.509 / PKI)")`
    - `("biometric_pin", "Biometric / Cryptographic PIN")`
  - `SIGNATURE_MEANING_CHOICES` (`max_length=40`):
    - `("approval", "I approve this document in full (Approval)")`
    - `("authorship", "I am the author and confirm its contents (Authorship)")`
    - `("review", "I have reviewed and verified technical accuracy (Review)")`
    - `("technical_verification", "Technical & Quality Assurance Verification")`
    - `("legal_signoff", "Legal & Regulatory Compliance Sign-Off")`
    - `("witness", "I witness the execution of this document (Witness)")`
  - `SIGNATURE_TYPE_CSS`:
    - `"click_to_sign": "badge-info"`
    - `"digital_cert": "badge-green"`
    - `"biometric_pin": "badge-amber"`
  - `SIGNATURE_MEANING_CSS`:
    - `"approval": "badge-green"`
    - `"authorship": "badge-info"`
    - `"review": "badge-slate"`
    - `"technical_verification": "badge-amber"`
    - `"legal_signoff": "badge-red"`
    - `"witness": "badge-muted"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="signatures", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="signatures")`
  - `approval_request`: `ForeignKey("documents.DocumentApprovalRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="signatures")`
  - `signer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_signatures")`
  - `signer_name`: `CharField(max_length=150)`
  - `signer_title`: `CharField(max_length=120, blank=True)`
  - `signer_email`: `EmailField(blank=True)`
  - `signature_type`: `CharField(max_length=30, choices=SIGNATURE_TYPE_CHOICES, default="click_to_sign", db_index=True)`
  - `signature_meaning`: `CharField(max_length=40, choices=SIGNATURE_MEANING_CHOICES, default="approval", db_index=True)`
  - `document_checksum`: `CharField(max_length=64, help_text="SHA-256 hash of document version at signing time")`
  - `signature_token`: `CharField(max_length=128, unique=True, help_text="Cryptographic signature verification token / UUID")`
  - `signature_glyph`: `TextField(blank=True, help_text="Drawn SVG signature data or seal stamp")`
  - `certificate_serial`: `CharField(max_length=100, blank=True, help_text="Digital X.509 or eIDAS certificate identifier")`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `user_agent`: `CharField(max_length=255, blank=True)`
  - `signed_at`: `DateTimeField(auto_now_add=True)`
  - `is_valid`: `BooleanField(default=True, db_index=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dsig_ten_num_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "document", "is_valid"], name="doc_dsig_tnt_doc_val_idx")` (24 chars)
  - `models.Index(fields=["tenant", "signer", "signed_at"], name="doc_dsig_tnt_sgn_date_idx")` (25 chars)

### 1.4 `DocumentReviewComment` (`DocumentReviewComments.py`)
- **`NUMBER_PREFIX`**: `"DREV"`
- **`Meta.ordering`**: `["page_number", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Review Comment"` / `"Document Review Comments"`
- **Choices & Badge Maps**:
  - `ANNOTATION_TYPE_CHOICES` (`max_length=30`):
    - `("inline_comment", "Inline Discussion Comment")`
    - `("highlight", "Text Highlight Annotation")`
    - `("redline", "Redline / Suggested Revision")`
    - `("sticky_note", "Sticky Note Pin")`
    - `("drawing_callout", "Geometry / Drawing Callout")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("open", "Open / Action Required")`
    - `("addressed", "Addressed / Implemented")`
    - `("resolved", "Resolved & Closed")`
    - `("dismissed", "Dismissed / Not Applicable")`
  - `STATUS_CSS`:
    - `"open": "badge-amber"`
    - `"addressed": "badge-info"`
    - `"resolved": "badge-green"`
    - `"dismissed": "badge-muted"`
  - `ANNOTATION_TYPE_CSS`:
    - `"inline_comment": "badge-info"`
    - `"highlight": "badge-amber"`
    - `"redline": "badge-red"`
    - `"sticky_note": "badge-slate"`
    - `"drawing_callout": "badge-green"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="review_comments", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_comments")`
  - `workflow`: `ForeignKey("documents.DocumentApprovalWorkflow", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_comments")`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_review_comments")`
  - `annotation_type`: `CharField(max_length=30, choices=ANNOTATION_TYPE_CHOICES, default="inline_comment", db_index=True)`
  - `page_number`: `PositiveIntegerField(default=1)`
  - `coordinate_ref`: `CharField(max_length=255, blank=True, help_text="Coordinates 'x,y,w,h' or DOM text anchor")`
  - `selected_text`: `TextField(blank=True, help_text="Highlighted or quoted snippet")`
  - `content`: `TextField()`
  - `parent`: `ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="open", db_index=True)`
  - `is_blocking`: `BooleanField(default=False, help_text="Blocks workflow approval until marked resolved")`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_document_comments")`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `resolution_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_drev_ten_num_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "document", "status"], name="doc_drev_tnt_doc_stat_idx")` (25 chars)
  - `models.Index(fields=["tenant", "workflow", "is_blocking"], name="doc_drev_tnt_wf_block_idx")` (25 chars)

---

## 2. Forms Contract (`apps/documents/forms/ApprovalWorkflow/`)

### 2.1 `DocumentApprovalWorkflowForm` (`DocumentApprovalWorkflows.py`)
- `Meta.model = DocumentApprovalWorkflow`
- `Meta.fields = ["document", "version", "title", "workflow_type", "urgency", "target_turnaround_hours", "department", "due_date", "requires_all_comments_resolved", "allow_emergency_bypass", "definition_json"]`
- Excluded: `tenant`, `number`, `status`, `current_stage`, `total_stages`, `initiator`, `completed_at`, `bypass_reason`, `bypassed_by`, `created_at`, `updated_at`.
- Tenant FK filtering in `__init__`: `document`, `version`, `department`.

### 2.2 `DocumentApprovalRequestForm` (`DocumentApprovalRequests.py`)
- `Meta.model = DocumentApprovalRequest`
- `Meta.fields = ["workflow", "stage_number", "stage_name", "stage_type", "order", "approver", "approver_role", "due_date"]`
- Excluded: `tenant`, `number`, `status`, `decision_comments`, `decided_at`, `delegated_to`, `delegation_reason`, `delegated_at`, `is_escalated`, `escalated_to`, `escalation_reason`, `escalated_at`, `reminder_sent_count`, `last_reminder_at`, `created_at`, `updated_at`.
- Tenant FK filtering in `__init__`: `workflow`, `approver`, `approver_role`.

### 2.3 `DocumentSignatureForm` (`DocumentSignatures.py`)
- `Meta.model = DocumentSignature`
- `Meta.fields = ["document", "version", "approval_request", "signer_name", "signer_title", "signer_email", "signature_type", "signature_meaning", "signature_glyph", "certificate_serial"]`
- Excluded: `tenant`, `number`, `signer`, `document_checksum`, `signature_token`, `ip_address`, `user_agent`, `signed_at`, `is_valid`, `created_at`, `updated_at`.
- Tenant FK filtering in `__init__`: `document`, `version`, `approval_request`.

### 2.4 `DocumentReviewCommentForm` (`DocumentReviewComments.py`)
- `Meta.model = DocumentReviewComment`
- `Meta.fields = ["document", "version", "workflow", "annotation_type", "page_number", "coordinate_ref", "selected_text", "content", "parent", "is_blocking"]`
- Excluded: `tenant`, `number`, `author`, `status`, `resolved_by`, `resolved_at`, `resolution_notes`, `created_at`, `updated_at`.
- Tenant FK filtering in `__init__`: `document`, `version`, `workflow`, `parent`.

---

## 3. URLs & Views Contract (`apps/documents/views/ApprovalWorkflow/` & `urls/ApprovalWorkflow/`)

All URL routes are registered in `apps/documents/urls/__init__.py` under `app_name = "documents"`.

### 3.1 Workflows (`DocumentApprovalWorkflows.py`)
- `/documents/workflows/`: `workflow_list` (Name: `workflow_list`)
- `/documents/workflows/create/`: `workflow_create` (Name: `workflow_create`)
- `/documents/workflows/<int:pk>/`: `workflow_detail` (Name: `workflow_detail`)
- `/documents/workflows/<int:pk>/edit/`: `workflow_edit` (Name: `workflow_edit`)
- `/documents/workflows/<int:pk>/delete/`: `workflow_delete` (Name: `workflow_delete`)
- `/documents/workflows/<int:pk>/designer/`: `workflow_designer` (Name: `workflow_designer`)
- `/documents/workflows/<int:pk>/submit/`: `workflow_submit` (Name: `workflow_submit`, POST-only)
- `/documents/workflows/<int:pk>/bypass/`: `workflow_bypass` (Name: `workflow_bypass`, POST-only)
- `/documents/workflows/<int:pk>/cancel/`: `workflow_cancel` (Name: `workflow_cancel`, POST-only)

### 3.2 Approval Requests (`DocumentApprovalRequests.py`)
- `/documents/requests/`: `approval_request_list` (Name: `approval_request_list`)
- `/documents/requests/create/`: `approval_request_create` (Name: `approval_request_create`)
- `/documents/requests/<int:pk>/`: `approval_request_detail` (Name: `approval_request_detail`)
- `/documents/requests/<int:pk>/edit/`: `approval_request_edit` (Name: `approval_request_edit`)
- `/documents/requests/<int:pk>/delete/`: `approval_request_delete` (Name: `approval_request_delete`)
- `/documents/requests/<int:pk>/decide/`: `approval_request_decide` (Name: `approval_request_decide`, POST-only approve/reject)
- `/documents/requests/<int:pk>/delegate/`: `approval_request_delegate` (Name: `approval_request_delegate`, POST-only)
- `/documents/requests/<int:pk>/escalate/`: `approval_request_escalate` (Name: `approval_request_escalate`, POST-only)

### 3.3 Signatures (`DocumentSignatures.py`)
- `/documents/signatures/`: `signature_list` (Name: `signature_list`)
- `/documents/signatures/create/`: `signature_create` (Name: `signature_create`)
- `/documents/signatures/<int:pk>/`: `signature_detail` (Name: `signature_detail`)
- `/documents/signatures/<int:pk>/edit/`: `signature_edit` (Name: `signature_edit`)
- `/documents/signatures/<int:pk>/delete/`: `signature_delete` (Name: `signature_delete`)
- `/documents/signatures/<int:pk>/manifest/`: `signature_manifest` (Name: `signature_manifest`)
- `/documents/signatures/verify/<str:token>/`: `signature_verify` (Name: `signature_verify`)

### 3.4 Review Comments (`DocumentReviewComments.py`)
- `/documents/comments/`: `review_comment_list` (Name: `review_comment_list`)
- `/documents/comments/create/`: `review_comment_create` (Name: `review_comment_create`)
- `/documents/comments/<int:pk>/`: `review_comment_detail` (Name: `review_comment_detail`)
- `/documents/comments/<int:pk>/edit/`: `review_comment_edit` (Name: `review_comment_edit`)
- `/documents/comments/<int:pk>/delete/`: `review_comment_delete` (Name: `review_comment_delete`)
- `/documents/comments/<int:pk>/resolve/`: `review_comment_resolve` (Name: `review_comment_resolve`, POST-only)

### 3.5 Approval Dashboard (`ApprovalDashboard.py`)
- `/documents/approvals/dashboard/`: `approval_dashboard` (Name: `approval_dashboard`)

---

## 4. View Context Keys Contract (L7, L8 Mandatory)

### 4.1 `workflow_list`
- `workflows`: Page object of `DocumentApprovalWorkflow` queryset
- `workflow_type_choices`: `DocumentApprovalWorkflow.WORKFLOW_TYPE_CHOICES`
- `status_choices`: `DocumentApprovalWorkflow.STATUS_CHOICES`
- `urgency_choices`: `DocumentApprovalWorkflow.URGENCY_CHOICES`
- `status_css`: `DocumentApprovalWorkflow.STATUS_CSS`
- `urgency_css`: `DocumentApprovalWorkflow.URGENCY_CSS`
- `total_count`: integer count
- `pending_count`: integer count
- `approved_count`: integer count

### 4.2 `workflow_detail`
- `workflow`: `DocumentApprovalWorkflow` instance
- `status_css`: CSS badge class
- `urgency_css`: CSS badge class
- `approval_requests`: Ordered list of `DocumentApprovalRequest` instances
- `signatures`: List of `DocumentSignature` instances
- `review_comments`: List of `DocumentReviewComment` instances
- `blocking_comments_count`: Integer count of open blocking comments

### 4.3 `workflow_form` (create / edit)
- `form`: `DocumentApprovalWorkflowForm` instance
- `workflow`: `DocumentApprovalWorkflow` instance or `None`
- `is_edit`: Boolean

### 4.4 `workflow_designer`
- `workflow`: `DocumentApprovalWorkflow` instance
- `stages`: List of stages with their requests
- `definition_json`: JSON string

### 4.5 `approval_request_list`
- `requests`: Page object of `DocumentApprovalRequest` queryset
- `status_choices`: `DocumentApprovalRequest.STATUS_CHOICES`
- `stage_type_choices`: `DocumentApprovalRequest.STAGE_TYPE_CHOICES`
- `status_css`: `DocumentApprovalRequest.STATUS_CSS`
- `stage_type_css`: `DocumentApprovalRequest.STAGE_TYPE_CSS`
- `my_pending_count`: Integer count
- `total_count`: Integer count

### 4.6 `approval_request_detail`
- `request_obj`: `DocumentApprovalRequest` instance
- `status_css`: CSS badge class
- `stage_type_css`: CSS badge class
- `signature`: Associated `DocumentSignature` or `None`

### 4.7 `approval_request_form`
- `form`: `DocumentApprovalRequestForm` instance
- `request_obj`: `DocumentApprovalRequest` instance or `None`
- `is_edit`: Boolean

### 4.8 `signature_list`
- `signatures`: Page object of `DocumentSignature` queryset
- `signature_type_choices`: `DocumentSignature.SIGNATURE_TYPE_CHOICES`
- `signature_meaning_choices`: `DocumentSignature.SIGNATURE_MEANING_CHOICES`
- `signature_type_css`: `DocumentSignature.SIGNATURE_TYPE_CSS`
- `signature_meaning_css`: `DocumentSignature.SIGNATURE_MEANING_CSS`
- `total_count`: Integer count
- `valid_count`: Integer count

### 4.9 `signature_detail`
- `signature`: `DocumentSignature` instance
- `signature_type_css`: CSS badge class
- `signature_meaning_css`: CSS badge class

### 4.10 `signature_manifest`
- `signature`: `DocumentSignature` instance
- `document`: Associated `Document`
- `version`: Associated `DocumentVersion`

### 4.11 `signature_verify`
- `signature`: `DocumentSignature` instance or `None`
- `token`: String token checked
- `is_valid`: Boolean

### 4.12 `review_comment_list`
- `comments`: Page object of `DocumentReviewComment` queryset
- `status_choices`: `DocumentReviewComment.STATUS_CHOICES`
- `annotation_type_choices`: `DocumentReviewComment.ANNOTATION_TYPE_CHOICES`
- `status_css`: `DocumentReviewComment.STATUS_CSS`
- `annotation_type_css`: `DocumentReviewComment.ANNOTATION_TYPE_CSS`
- `open_blocking_count`: Integer count
- `total_count`: Integer count

### 4.13 `review_comment_detail`
- `comment`: `DocumentReviewComment` instance
- `status_css`: CSS badge class
- `annotation_type_css`: CSS badge class
- `replies`: List of reply `DocumentReviewComment` instances

### 4.14 `review_comment_form`
- `form`: `DocumentReviewCommentForm` instance
- `comment`: `DocumentReviewComment` instance or `None`
- `is_edit`: Boolean

### 4.15 `approval_dashboard`
- `pending_workflows`: List of pending `DocumentApprovalWorkflow` instances
- `urgent_requests`: List of high/urgent pending `DocumentApprovalRequest` instances
- `recent_signatures`: List of recent `DocumentSignature` instances
- `blocking_comments`: List of open blocking `DocumentReviewComment` instances
- `metrics`: Dictionary with counts (`total_active_workflows`, `avg_cycle_time_hours`, `escalation_rate_pct`, `pending_signoffs`)

---

## 5. Sidebar Navigation Wiring Contract (`apps/core/navigation.py`)

Sub-module 13.3 maps all 5 `NavERP.md` feature bullets:
```python
    # 13.3 Document Approval & Review Workflow
    "13.3": {
        "Visual Workflow Designer": "documents:workflow_list",
        "Electronic Signature Capture": "documents:signature_list",
        "Delegation & Escalation Rules": "documents:approval_request_list",
        "Review Comments & Annotation": "documents:review_comment_list",
        "Approval Dashboard & Status Tracking": "documents:approval_dashboard",
    },
```
