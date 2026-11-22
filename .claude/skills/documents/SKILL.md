---
name: documents
description: Work on the Document Management System (DMS) module (Module 13 — Document Management System). As-built = 13.1 Document Creation & Authoring (DocumentTemplate[DTMPL-], TemplateSection[DSEC-], DocumentDraft[DDFT-], DraftCollaboration[DCMT-], interactive authoring canvas with autosave, redline visual diff, sync conflict resolution, promotion to core.Document). Use when the user asks to add/change/debug anything under apps/documents or templates/documents, extend the seed_documents seeder, touch documents sidebar wiring (LIVE_LINKS 13.1), or invokes /documents.
---

# Document Management System (DMS) (Module 13)

App path: `apps/documents`. Templates: `templates/documents/`. URL prefix: `/documents/`, `app_name = "documents"`.
Mirrors `NavERP.md` "## 13. Document Management System (DMS)" (Sub-modules 13.1–13.20).

**As-built: 13.1 Document Creation & Authoring.**
Build the next sub-module with `/next-module next` — see `apps/quality`/`apps/procurement` for reference package layout and the mandatory Module Creation Sequence.

---

## Overview

Sub-module 13.1 provides the foundational authoring, templating, and collaborative drafting workspace for the Document Management System:
- **Modular Templates**: Reusable master document blueprints (`DocumentTemplate`) with version tracking, active/retired state, and structural locking (`is_locked`).
- **Section & Clause Library**: Reusable clauses, disclaimers, boilerplate sections, headers, and appendices (`TemplateSection`) sorted by order and linked to parent templates or global boilerplates.
- **Working Draft Workspace**: Stateful drafting register (`DocumentDraft`) supporting drafts, in-review, approved, conflict-pending, promoted, and discarded lifecycle states.
- **Interactive Authoring Canvas**: Real-time browser editing surface (`canvas.html`) with token insertion, live word count, and debounced AJAX background autosave endpoint (`draft_autosave`).
- **Visual Redline Diff**: Unified line-by-line diff engine (`compare.html`) comparing active drafts against baseline master templates.
- **Collaborative Review & Redlining**: Inline suggestions and critique notes (`DraftCollaboration`) with author/admin permissions and one-click resolution (`accept`/`reject`).
- **Official Promotion**: Controlled promotion (`draft_promote`) that publishes an approved draft as an official released `core.Document` record.

---

## Models (`apps/documents/models/DocumentAuthoring/<Entity>.py`)

Shared base in `models/_base.py`:
- `TenantOwned`: multi-tenant foreign key + timestamps.
- `TenantNumbered`: auto-number generator via `core.utils.next_number` with collision retry loop.

### 13.1 DocumentAuthoring

- **`DocumentTemplates.py`** — `DocumentTemplate` (`NUMBER_PREFIX = "DTMPL"`):
  - `template_type`: sop, contract, policy, report, memo, letter, specification, meeting_minutes, other.
  - `category`: legal, hr, operations, finance, it, quality, sales, executive.
  - `name`, `version`, `description`, `content`, `styling_rules`, `is_active`, `is_locked`.
  - Reuses core spine: `target_org_unit` (FK `core.OrgUnit`), `owner` (FK `settings.AUTH_USER_MODEL`).
  - Helper properties: `available_tokens` parsed from JSON.
  - Constraints & Indexes: unique `(tenant, number)`, composite index `(tenant, template_type, is_active)`.

- **`TemplateSections.py`** — `TemplateSection` (`NUMBER_PREFIX = "DSEC"`):
  - `template` (FK `DocumentTemplate`, nullable for global boilerplates).
  - `section_type`: header, boilerplate, disclaimer, signature_block, table_of_contents, body_section, appendix, footer.
  - `title`, `content`, `order`, `is_locked`, `is_mandatory`.
  - Ordering: `["template", "order", "id"]`.
  - Indexes: `(tenant, section_type)`, composite index `(tenant, template, order)`.

- **`DocumentDrafts.py`** — `DocumentDraft` (`NUMBER_PREFIX = "DDFT"`):
  - `template` (FK `DocumentTemplate`, nullable).
  - `title`, `document_type`, `draft_version`, `status` (draft, in_review, approved, promoted, discarded), `sync_status` (synced, dirty, conflict_pending).
  - `content`, `content_format` (html, markdown, plain), `word_count`.
  - `department` (FK `core.OrgUnit`), `related_party` (FK `core.Party`), `author` (FK `settings.AUTH_USER_MODEL`).
  - `is_collaboration_locked`: gates editing and autosave mutations.
  - `promoted_document` (FK `core.Document`), `promoted_version`, `promoted_at`.
  - Ordering: `["-updated_at"]`.
  - Indexes: `(tenant, status, document_type)`, composite index `(tenant, -updated_at)`.

- **`DraftCollaborations.py`** — `DraftCollaboration` (`NUMBER_PREFIX = "DCMT"`):
  - `draft` (FK `DocumentDraft`, `related_name="collaborations"`).
  - `author` (FK `settings.AUTH_USER_MODEL`).
  - `entry_type`: comment, suggestion, critique, approval_note.
  - `comment_text`, `selected_text`, `replacement_text`.
  - `status`: open, accepted, rejected, resolved.
  - `resolved_by` (FK `settings.AUTH_USER_MODEL`), `resolved_at`, `resolution_notes`.
  - Ordering: `["-created_at"]`.
  - Indexes: `(tenant, draft, status)`.

---

## URLs & Routes (`apps/documents/urls/DocumentAuthoring/`)

All registered under `app_name = "documents"`:

| URL Name | Method | Path | Description |
|---|---|---|---|
| `documents:template_list` | GET | `/documents/templates/` | Searchable & filtered list of templates |
| `documents:template_detail` | GET | `/documents/templates/<pk>/` | Detail view with sections and drafts |
| `documents:template_create` | GET/POST | `/documents/templates/create/` | Author new master template |
| `documents:template_edit` | GET/POST | `/documents/templates/<pk>/edit/` | Edit template (admin required if locked) |
| `documents:template_delete` | POST | `/documents/templates/<pk>/delete/` | Remove template (admin required if locked) |
| `documents:template_instantiate` | POST | `/documents/templates/<pk>/instantiate/` | Clone template into new working draft |
| `documents:template_section_list` | GET | `/documents/sections/` | Reusable section & clause register |
| `documents:template_section_detail` | GET | `/documents/sections/<pk>/` | Section details and clause wording |
| `documents:template_section_create` | GET/POST | `/documents/sections/create/` | Add section or boilerplate clause |
| `documents:template_section_edit` | GET/POST | `/documents/sections/<pk>/edit/` | Edit section (admin required if locked) |
| `documents:template_section_delete` | POST | `/documents/sections/<pk>/delete/` | Delete section (admin required if locked) |
| `documents:draft_list` | GET | `/documents/drafts/` | Document draft tracking register |
| `documents:draft_detail` | GET | `/documents/drafts/<pk>/` | Draft overview and feedback notes |
| `documents:draft_create` | GET/POST | `/documents/drafts/create/` | Initialize new document draft |
| `documents:draft_edit` | GET/POST | `/documents/drafts/<pk>/edit/` | Modify draft metadata and content |
| `documents:draft_delete` | POST | `/documents/drafts/<pk>/delete/` | Remove unpromoted draft |
| `documents:draft_canvas` | GET | `/documents/drafts/<pk>/canvas/` | Full-screen interactive authoring canvas |
| `documents:draft_autosave` | POST | `/documents/drafts/<pk>/autosave/` | Debounced AJAX autosave JSON endpoint |
| `documents:draft_compare` | GET | `/documents/drafts/<pk>/compare/` | Redline visual diff vs parent template |
| `documents:draft_resolve_conflicts` | GET/POST | `/documents/drafts/<pk>/conflicts/` | Manual conflict resolution surface |
| `documents:draft_promote` | POST | `/documents/drafts/<pk>/promote/` | Promote approved draft to `core.Document` |
| `documents:collaboration_list` | GET | `/documents/collaborations/` | Multi-document feedback register |
| `documents:collaboration_detail` | GET | `/documents/collaborations/<pk>/` | Feedback details & resolution history |
| `documents:collaboration_create` | GET/POST | `/documents/drafts/<draft_pk>/collaborate/` | Add comment or suggestion |
| `documents:collaboration_edit` | GET/POST | `/documents/collaborations/<pk>/edit/` | Edit note (author or admin only) |
| `documents:collaboration_delete` | POST | `/documents/collaborations/<pk>/delete/` | Delete note (author or admin only) |
| `documents:collaboration_resolve` | POST | `/documents/collaborations/<pk>/resolve/` | Accept or reject suggestion |

---

## Templates

Located in `templates/documents/document_authoring/`:
- `document_template/{list,detail,form}.html`: Template management and token preview.
- `template_section/{list,detail,form}.html`: Section clause library.
- `document_draft/{list,detail,form,canvas,compare,conflict_resolution}.html`: Drafting surfaces.
- `draft_collaboration/{list,detail,form}.html`: Inline critiques and reviews.

**Conventions**:
- Badge classes are strictly colour-named: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- Forms use standard NavERP inputs: `form-input`, `form-select`, `form-textarea`, `form-checkbox`.
- All filter labels and input pairs are strictly coupled with `for="..."` and `id="..."`.

---

## Seeder (`apps/documents/management/commands/seed_documents.py`)

Run via:
```powershell
venv\Scripts\python.exe manage.py seed_documents
```
Idempotent command that seeds:
1. Master Document Templates across Acme, Globex, Initech (SOPs, Policies, Contracts).
2. Modular Template Sections (Standard Disclaimers, QA Clauses, Approval Signatures).
3. Active Working Drafts with word counts and sample revisions.
4. Collaboration Feedback Notes with suggestions and critiques.

---

## Conventions & Gotchas

1. **Multi-Tenancy**: All queries MUST use `documents_scope(Model.objects.all(), request)` or `documents_object(request, Model, pk)`. Never bypass tenant filtering.
2. **Promotion File Requirement**: `core.Document.file` is non-nullable. In `draft_promote`, always wrap UTF-8 encoded text in `ContentFile(draft.content.encode('utf-8'), name=f"{draft.number}.html")`.
3. **Locking Protections**:
   - `is_locked` on `DocumentTemplate` and `TemplateSection` prohibits editing/deletion unless user is a tenant administrator (`request.user.is_tenant_admin` or superuser).
   - `is_collaboration_locked` on `DocumentDraft` halts both `draft_edit` and background `draft_autosave`.
4. **Prefetch Cache Invalidation**: Avoid chaining `.filter(...)` or `.order_by(...)` on prefetched relations in views or templates. Filter in Python or rely on model `Meta.ordering`.
5. **Audit Logging**: Mandatory call `write_audit_log(request.user, obj, action.lower(), tenant=request.tenant)` inside atomic transaction blocks.
