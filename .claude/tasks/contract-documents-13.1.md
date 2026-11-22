# Build Contract — Sub-module 13.1: Document Creation & Authoring (Module 13: Document Management System, `apps/documents`)

> Phase 3 Step 1. `BASE = 046eecb0bbea97d5200c85f8c7a5b81eae74aa9b`.
> Research: `.claude/tasks/research-documents-13.1.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0001_initial`** (brand new app `apps/documents`).

---

## 0. Ownership & Cross-Module Boundaries (L28 / L29 / L36)

Sub-module 13.1 initializes the Document Management System (DMS) module and establishes the authoring, templating, and "Version Zero" draft lifecycle. It enforces clean segregation from existing and future modules:

| Entity / Domain | Master Owner | Where It Lives | 13.1 Relationship |
|---|---|---|---|
| **Binary File Attachments** | **core 0** | `apps/core/models/Document.py` | `core.Document` is the binary storage and file upload spine. When a draft is formally promoted to version 1.0, it instantiates or links a `core.Document` record (`DocumentDraft.promoted_document`). |
| **Organization Units & Departments** | **core 0** | `apps/core/models/OrgUnit.py` | `core.OrgUnit` represents company departments/divisions scoped to templates and drafts. |
| **Parties & Business Partners** | **core 0** | `apps/core/models/Party.py` | `core.Party` is linked as the optional customer/vendor/counterparty context for document generation. |
| **Users / Authors / Reviewers** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) for authors, co-authors, resolvers, and owners. |
| **Quality Controlled Documents** | **quality 12.1** | `apps/quality/models/DocumentControl/ControlledDocuments.py` | `apps/quality` owns GxP QA-specific controlled documents (`QDOC-`). `documents` owns enterprise-wide general document authoring, corporate templates, and rich-text collaboration. |
| **Audit Trails** | **core 0** | `apps/core/models/AuditLog.py` | System-wide audit log via `write_audit_log(request.user, obj, action, tenant=request.tenant)` (L66). |

---

## 1. Models — Full Field Specifications, Choices & Constraints

All models inherit from `apps.documents.models._base.TenantNumbered` (which inherits `TenantOwned` with `tenant` FK `core.Tenant`, `created_at`, `updated_at`, and adds `number = CharField(max_length=32, editable=False)`).

### 1.1 `DocumentTemplate` (`DocumentTemplates.py`) — `NUMBER_PREFIX = "DTMPL"`

Catalog of pre-approved master document templates with formatting locks, category classification, dynamic token definitions, and department scoping.

```python
TEMPLATE_TYPE_CHOICES = [
    ("sop", "Standard Operating Procedure (SOP)"),
    ("contract", "Contract / Agreement"),
    ("policy", "Corporate Policy / Governance"),
    ("report", "Business / Technical Report"),
    ("memo", "Internal Memorandum"),
    ("letter", "Official Correspondence / Letter"),
    ("specification", "Product / Technical Specification"),
    ("meeting_minutes", "Meeting Minutes"),
    ("other", "General Document Template"),
]

CATEGORY_CHOICES = [
    ("legal", "Legal & Compliance"),
    ("hr", "Human Resources"),
    ("operations", "Operations & Manufacturing"),
    ("finance", "Finance & Accounting"),
    ("it", "Information Technology & Security"),
    ("quality", "Quality & Safety"),
    ("sales", "Sales & Marketing"),
    ("executive", "Executive & Strategy"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `name` | `CharField(max_length=200)` | Required, indexed |
| `template_type` | `CharField(max_length=40, choices=TEMPLATE_TYPE_CHOICES, default="sop")` | Indexed |
| `category` | `CharField(max_length=40, choices=CATEGORY_CHOICES, default="operations")` | Indexed |
| `description` | `TextField(blank=True)` | Template usage scope and administrative instructions |
| `content` | `TextField(blank=True)` | Master template body text with token placeholders (e.g. `{{company_name}}`, `{{author_name}}`) |
| `styling_rules` | `TextField(blank=True)` | CSS/styling constraints or locked typography rules (JSON or stylesheet) |
| `is_active` | `BooleanField(default=True)` | Active status toggle |
| `is_locked` | `BooleanField(default=False)` | True = layout, header, footer, and styling are locked against author alteration |
| `available_tokens` | `JSONField(default=dict, blank=True)` | Dictionary mapping token keys to descriptions |
| `version` | `CharField(max_length=20, default="1.0")` | Template revision number |
| `target_org_unit` | `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="doc_templates")` | Department ownership / scoping |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_doc_templates")` | Template custodian |

- `Meta.ordering = ["name"]`
- `Meta.constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="doc_tmpl_tnt_num_uniq")]`
- `Meta.indexes = [models.Index(fields=["tenant", "template_type", "is_active"], name="doc_tmpl_tnt_type_idx")]` (20 chars <= 30)
- `clean()`:
  - If `target_org_unit` is set, assert `target_org_unit.tenant_id == self.tenant_id`.

---

### 1.2 `TemplateSection` (`TemplateSections.py`) — `NUMBER_PREFIX = "DSEC"`

Modular content blocks, boilerplate clauses, standard disclaimers, and reusable layout fragments.

```python
SECTION_TYPE_CHOICES = [
    ("header", "Document Header / Cover"),
    ("boilerplate", "Standard Boilerplate Clause"),
    ("disclaimer", "Legal Disclaimer / Notice"),
    ("signature_block", "Signature Block"),
    ("table_of_contents", "Table of Contents"),
    ("body_section", "Numbered Body Section"),
    ("appendix", "Appendix / Exhibit"),
    ("footer", "Document Footer"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `template` | `ForeignKey("documents.DocumentTemplate", on_delete=models.CASCADE, null=True, blank=True, related_name="sections")` | Null = Global reusable block; Set = Bound to specific template |
| `title` | `CharField(max_length=200)` | Section heading / clause name |
| `section_type` | `CharField(max_length=40, choices=SECTION_TYPE_CHOICES, default="body_section")` | Indexed |
| `content` | `TextField(blank=True)` | Reusable text, table markdown, or clause content |
| `order` | `PositiveIntegerField(default=10)` | Ordering inside parent template |
| `is_locked` | `BooleanField(default=False)` | True = mandatory boilerplate that cannot be edited or removed by draft authors |
| `is_mandatory` | `BooleanField(default=False)` | True = must be included in derived drafts |

- `Meta.ordering = ["template", "order", "id"]`
- `Meta.constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="doc_sec_tnt_num_uniq")]`
- `Meta.indexes = [models.Index(fields=["tenant", "section_type"], name="doc_sec_tnt_type_idx")]` (19 chars <= 30)
- `clean()`:
  - If `template` is set, assert `template.tenant_id == self.tenant_id`.

---

### 1.3 `DocumentDraft` (`DocumentDrafts.py`) — `NUMBER_PREFIX = "DDFT"`

Authoring container and "Version Zero" working workspace (`0.1`, `0.2`) segregated from official released documents until formal promotion to `"1.0"`.

```python
DRAFT_STATUS_CHOICES = [
    ("draft", "Draft / In Authoring"),
    ("in_review", "Peer Review / Collaboration"),
    ("ready_for_promotion", "Ready for Official Release"),
    ("promoted", "Promoted to Official Document"),
    ("discarded", "Discarded / Canceled"),
]

DOCUMENT_TYPE_CHOICES = [
    ("sop", "Standard Operating Procedure"),
    ("contract", "Contract Agreement"),
    ("policy", "Company Policy"),
    ("report", "Report"),
    ("memo", "Internal Memo"),
    ("letter", "Official Letter"),
    ("other", "Other Document"),
]

CONTENT_FORMAT_CHOICES = [
    ("html", "Rich Text / HTML"),
    ("markdown", "Markdown / Plain Text"),
    ("plain", "Plain Text"),
]

SYNC_STATUS_CHOICES = [
    ("synced", "Fully Synchronized"),
    ("conflict_pending", "Sync Conflict Detected"),
    ("resolved", "Conflict Resolved"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `title` | `CharField(max_length=255)` | Required document draft title, indexed |
| `document_type` | `CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, default="sop")` | Categorization |
| `template` | `ForeignKey("documents.DocumentTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="derived_drafts")` | Originating master template |
| `status` | `CharField(max_length=30, choices=DRAFT_STATUS_CHOICES, default="draft")` | Workflow status, indexed |
| `draft_version` | `CharField(max_length=20, default="0.1")` | Version zero designation (e.g. 0.1, 0.2) |
| `content` | `TextField(blank=True)` | Active authoring body content |
| `content_format` | `CharField(max_length=20, choices=CONTENT_FORMAT_CHOICES, default="html")` | Editor formatting format |
| `author` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_drafts")` | Primary creator / author |
| `department` | `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="draft_documents")` | Department context |
| `related_party` | `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="draft_documents")` | Optional party (customer, vendor) context |
| `auto_save_timestamp` | `DateTimeField(null=True, blank=True)` | Last background auto-save timestamp |
| `is_collaboration_locked` | `BooleanField(default=False)` | Lock to prevent concurrent edits during review |
| `offline_client_id` | `CharField(max_length=64, blank=True)` | UUID/Client token of last offline session |
| `offline_cached_at` | `DateTimeField(null=True, blank=True)` | Timestamp when document was pulled for offline editing |
| `sync_status` | `CharField(max_length=30, choices=SYNC_STATUS_CHOICES, default="synced")` | Conflict detection state |
| `word_count` | `PositiveIntegerField(default=0)` | Live word count derived on save |
| `promoted_at` | `DateTimeField(null=True, blank=True)` | When promoted to official version |
| `promoted_version` | `CharField(max_length=20, blank=True)` | Official version assigned on promotion (e.g. 1.0) |
| `promoted_document` | `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_drafts")` | Official linked file master |

- `Meta.ordering = ["-updated_at"]`
- `Meta.constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="doc_dft_tnt_num_uniq")]`
- `Meta.indexes = [models.Index(fields=["tenant", "status", "document_type"], name="doc_dft_tnt_stat_idx")]` (20 chars <= 30)
- `clean()`:
  - If `template` is set, assert `template.tenant_id == self.tenant_id`.
  - If `department` is set, assert `department.tenant_id == self.tenant_id`.
  - If `related_party` is set, assert `related_party.tenant_id == self.tenant_id`.
  - If `promoted_document` is set, assert `promoted_document.tenant_id == self.tenant_id`.

---

### 1.4 `DraftCollaboration` (`DraftCollaborations.py`) — `NUMBER_PREFIX = "DCMT"`

Inline collaborative commentary, discussion threads, track changes, and suggestion mode entries attached to specific draft sections.

```python
ENTRY_TYPE_CHOICES = [
    ("comment", "Inline Comment / Feedback"),
    ("suggestion", "Content Suggestion (Proposed Change)"),
    ("track_change", "Tracked Edit / Delta"),
]

STATUS_CHOICES = [
    ("open", "Open / Pending Review"),
    ("accepted", "Accepted & Applied"),
    ("rejected", "Rejected / Dismissed"),
    ("resolved", "Resolved"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `draft` | `ForeignKey("documents.DocumentDraft", on_delete=models.CASCADE, related_name="collaborations")` | Parent draft |
| `entry_type` | `CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default="comment")` | Type of contribution |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="open")` | Review resolution status |
| `author` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="draft_collaborations")` | User contributing feedback |
| `selected_text` | `TextField(blank=True)` | Highlighted original text range |
| `replacement_text` | `TextField(blank=True)` | Proposed replacement text (for suggestions / track changes) |
| `comment_text` | `TextField()` | Feedback note, critique, or discussion comment |
| `section_anchor` | `CharField(max_length=100, blank=True)` | DOM id, section heading, or paragraph index |
| `resolved_by` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_collaborations")` | Author or moderator accepting/rejecting |
| `resolved_at` | `DateTimeField(null=True, blank=True)` | Timestamp of resolution |

- `Meta.ordering = ["-created_at"]`
- `Meta.constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="doc_cmt_tnt_num_uniq")]`
- `Meta.indexes = [models.Index(fields=["tenant", "draft", "status"], name="doc_cmt_tnt_dft_idx")]` (18 chars <= 30)
- `clean()`:
  - Assert `draft.tenant_id == self.tenant_id`.

---

## 2. Forms (`apps/documents/forms/DocumentAuthoring/`)

All forms exclude `tenant`, `number`, system auto-calculated fields, and audit timestamps.

1. **`DocumentTemplateForm`** (`DocumentTemplates.py`):
   - Model: `DocumentTemplate`
   - Fields: `name`, `template_type`, `category`, `description`, `content`, `styling_rules`, `version`, `target_org_unit`, `owner`, `is_active`, `is_locked`
   - Scopes `target_org_unit` and `owner` to `request.tenant`.

2. **`TemplateSectionForm`** (`TemplateSections.py`):
   - Model: `TemplateSection`
   - Fields: `template`, `title`, `section_type`, `content`, `order`, `is_locked`, `is_mandatory`
   - Scopes `template` to `request.tenant`.

3. **`DocumentDraftForm`** (`DocumentDrafts.py`):
   - Model: `DocumentDraft`
   - Fields: `title`, `document_type`, `template`, `draft_version`, `content`, `content_format`, `department`, `related_party`, `is_collaboration_locked`
   - Scopes FK querysets to `request.tenant`. Excludes `promoted_*`, `offline_*`, `auto_save_timestamp`, `word_count`.

4. **`DraftCollaborationForm`** (`DraftCollaborations.py`):
   - Model: `DraftCollaboration`
   - Fields: `entry_type`, `selected_text`, `replacement_text`, `comment_text`, `section_anchor`
   - Set `draft`, `author`, `tenant` in view.

---

## 3. URLs & Routes (`apps/documents/urls/`)

`app_name = "documents"`

```python
urlpatterns = [
    # Document Templates
    path("templates/", views.template_list, name="template_list"),
    path("templates/create/", views.template_create, name="template_create"),
    path("templates/<int:pk>/", views.template_detail, name="template_detail"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("templates/<int:pk>/delete/", views.template_delete, name="template_delete"),
    path("templates/<int:pk>/instantiate/", views.template_instantiate, name="template_instantiate"),

    # Template Sections
    path("sections/", views.template_section_list, name="template_section_list"),
    path("sections/create/", views.template_section_create, name="template_section_create"),
    path("sections/<int:pk>/", views.template_section_detail, name="template_section_detail"),
    path("sections/<int:pk>/edit/", views.template_section_edit, name="template_section_edit"),
    path("sections/<int:pk>/delete/", views.template_section_delete, name="template_section_delete"),

    # Document Drafts & Authoring
    path("drafts/", views.draft_list, name="draft_list"),
    path("drafts/create/", views.draft_create, name="draft_create"),
    path("drafts/<int:pk>/", views.draft_detail, name="draft_detail"),
    path("drafts/<int:pk>/edit/", views.draft_edit, name="draft_edit"),
    path("drafts/<int:pk>/delete/", views.draft_delete, name="draft_delete"),
    path("drafts/<int:pk>/canvas/", views.draft_canvas, name="draft_canvas"),
    path("drafts/<int:pk>/autosave/", views.draft_autosave, name="draft_autosave"),
    path("drafts/<int:pk>/compare/", views.draft_compare, name="draft_compare"),
    path("drafts/<int:pk>/conflict/", views.draft_resolve_conflict, name="draft_resolve_conflict"),
    path("drafts/<int:pk>/promote/", views.draft_promote, name="draft_promote"),

    # Draft Collaboration
    path("collaborations/", views.collaboration_list, name="collaboration_list"),
    path("collaborations/create/<int:draft_pk>/", views.collaboration_create, name="collaboration_create"),
    path("collaborations/<int:pk>/", views.collaboration_detail, name="collaboration_detail"),
    path("collaborations/<int:pk>/edit/", views.collaboration_edit, name="collaboration_edit"),
    path("collaborations/<int:pk>/delete/", views.collaboration_delete, name="collaboration_delete"),
    path("collaborations/<int:pk>/resolve/", views.collaboration_resolve, name="collaboration_resolve"),
]
```

---

## 4. View Context Keys Contract (L7 / L8)

Every view must pass exactly the pinned context variables:

### 4.1 DocumentTemplate Views
- `template_list`:
  - `templates`: Queryset / Page object
  - `page_obj`: Django paginator page
  - `search_query`: `request.GET.get('q', '')`
  - `template_type_choices`: `DocumentTemplate.TEMPLATE_TYPE_CHOICES`
  - `category_choices`: `DocumentTemplate.CATEGORY_CHOICES`
  - `total_count`: integer count
- `template_detail`:
  - `template`: `DocumentTemplate` instance
  - `sections`: child `TemplateSection` queryset
  - `drafts_count`: count of derived drafts
- `template_create` / `template_edit`:
  - `form`: `DocumentTemplateForm`
  - `template`: instance (in edit mode)
  - `is_edit`: boolean

### 4.2 TemplateSection Views
- `template_section_list`:
  - `sections`: Queryset / Page object
  - `page_obj`: Django paginator page
  - `search_query`: string
  - `section_type_choices`: `TemplateSection.SECTION_TYPE_CHOICES`
  - `template_choices`: `DocumentTemplate.objects.filter(tenant=request.tenant)`
  - `total_count`: integer count
- `template_section_detail`:
  - `section`: `TemplateSection` instance
- `template_section_create` / `template_section_edit`:
  - `form`: `TemplateSectionForm`
  - `section`: instance (in edit mode)
  - `is_edit`: boolean

### 4.3 DocumentDraft Views
- `draft_list`:
  - `drafts`: Queryset / Page object
  - `page_obj`: Django paginator page
  - `search_query`: string
  - `status_choices`: `DocumentDraft.DRAFT_STATUS_CHOICES`
  - `document_type_choices`: `DocumentDraft.DOCUMENT_TYPE_CHOICES`
  - `sync_status_choices`: `DocumentDraft.SYNC_STATUS_CHOICES`
  - `total_count`: integer count
- `draft_detail`:
  - `draft`: `DocumentDraft` instance
  - `collaborations`: related `DraftCollaboration` queryset
- `draft_create` / `draft_edit`:
  - `form`: `DocumentDraftForm`
  - `draft`: instance (in edit mode)
  - `is_edit`: boolean
- `draft_canvas`:
  - `draft`: `DocumentDraft` instance
  - `collaborations`: `draft.collaborations.all()`
  - `available_tokens`: dict or list of tokens
- `draft_compare`:
  - `draft`: `DocumentDraft` instance
  - `template`: `draft.template` or None
  - `has_template`: boolean
- `draft_resolve_conflict`:
  - `draft`: `DocumentDraft` instance

### 4.4 DraftCollaboration Views
- `collaboration_list`:
  - `collaborations`: Queryset / Page object
  - `page_obj`: Django paginator page
  - `search_query`: string
  - `entry_type_choices`: `DraftCollaboration.ENTRY_TYPE_CHOICES`
  - `status_choices`: `DraftCollaboration.STATUS_CHOICES`
  - `total_count`: integer count
- `collaboration_detail`:
  - `collaboration`: `DraftCollaboration` instance
- `collaboration_create` / `collaboration_edit`:
  - `form`: `DraftCollaborationForm`
  - `draft`: parent `DocumentDraft`
  - `collaboration`: instance (in edit mode)
  - `is_edit`: boolean

---

## 5. Navigation LIVE_LINKS["13.1"]

```python
LIVE_LINKS["13.1"] = {
    "Template Library & Standardization": "documents:template_list",
    "Rich Text & Collaborative Editing": "documents:draft_list",
    "Version Zero & Draft Management": "documents:draft_list",
    "Embedded Media & Objects": "documents:template_section_list",
    "Offline Authoring & Sync": "documents:draft_list",
}
```
