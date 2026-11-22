# Research — Sub-module 13.1: Document Creation & Authoring (Module 13 — Document Management System, `documents`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 13 so far:** None (`documents` is a brand-new app; Module 13 has 20 sub-modules, 13.1 through 13.20, starting now).
  - Modules 0 through 11 are 100% built (`0.1`–`0.21`, `1.1`–`1.12`, `2.1`–`2.15`, `3.1`–`3.41`, `4.1`–`4.19`, `5.1`–`5.20`, `6.1`–`6.19`, `7.1`–`7.19`, `8.1`–`8.19`, `9.1`–`9.20`, `10.1`–`10.19`, `11.1`–`11.19` — verified via `apps/core/navigation.py`).
  - Module 12 (Quality Management System) has 12.1–12.20 built.
  - **`13.1` is the very first sub-module of Module 13.**
- **Existing document and template models across other modules:**
  - `apps/quality/models/DocumentControl/ControlledDocuments.py` (`ControlledDocument`, prefix `QDOC`): Regulated life sciences/GxP quality procedures, 21 CFR Part 11 signatures, read-and-acknowledge sign-offs.
  - `apps/core/models/Document.py` (`Document`): Generic attachment spine linking binary uploads to any record via GenericForeignKey (`content_type`, `object_id`).
  - `apps/crm/models/DocumentContract/DocTemplates.py` (`DocTemplate`, prefix `TPL`): CRM sales quote/proposal template.
  - `apps/projects/models/DocumentKnowledgeManagement/Templates.py` (`ProjectTemplate`, prefix `DTM`): Project management methodology templates.
  - `apps/hrm/models/RequestManagement/Documentrequest.py` (`Documentrequest`, prefix `DOCREQ`): Employee HR record requests.
  - *Distinction:* Module 13 is NavERP's core enterprise Document Management System (DMS). Sub-module 13.1 provides the foundational collaborative authoring and template management infrastructure (pre-approved templates, locked sections, modular content blocks, "Version 0" working drafts, collaborative suggestions, inline comments, and promotion to official version 1.0).

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` → `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` → `class OrgUnit(models.Model)` | Departmental ownership and template scoping (`department`, `company`). |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Unified party spine for document recipient, counterparty, or vendor linkage. |
| `core.Document` exists | `apps/core/models/Document.py:5` → `class Document(models.Model)` | Generic file attachment spine. Promoted drafts graduate into or link to `core.Document`. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `apps/core/utils.py` `write_audit_log` helper | General tenant audit trail for draft promotions and template edits. |
| `core.NumberingScheme` exists | `apps/core/models/NumberingScheme.py:15` → `prefix` + `unique_together ("tenant", "prefix")` | Autonumbering schema registry using `next_number`. |
| `accounts.User` exists | `apps/accounts/models.py:52` → `class User(AbstractBaseUser, PermissionsMixin)` | Auth user model for authors, co-authors, reviewers, and commenters. |

### Spine entities verified NOT to exist

- **No DMS app or models yet:** `apps/documents/` does not exist.
- **No Document Template or Draft models:** Grep confirms zero models exist for generic DMS template libraries, modular document sections/fragments, pre-release working drafts (Version 0.x), or collaborative suggestion tracking.

### Candidate prefix collision check (repo-wide automated verification)

Automated script scanned all `NUMBER_PREFIX` declarations across the codebase:
- `DTMPL` (Document Template) → **0 collisions** (Completely free)
- `DSEC` (Document Section / Modular Content Block) → **0 collisions** (Completely free)
- `DDFT` (Document Draft / Authoring Workspace) → **0 collisions** (Completely free)
- `DCMT` (Draft Collaboration Comment & Suggestion) → **0 collisions** (Completely free)
*(Note: `DTM` is used in `projects.DocumentKnowledgeManagement.Templates`, `DSH` in `projects.CollaborationCommunication.DocumentShares`, `DOCREQ` in `hrm`. The prefixes `DTMPL`, `DSEC`, `DDFT`, and `DCMT` have zero collisions across all 12 modules).*

---

## Leaders surveyed (with source links)

1. **Microsoft SharePoint / 365 Content Services** — Enterprise cloud content management standard. Organizes document authoring around Site Content Types that bind standardized Word/Excel document templates to structured metadata. Features real-time Word co-authoring with simultaneous multi-user editing, contextual comments with @mentions, and strict minor draft versioning (`0.1`, `0.2`) for in-progress authoring prior to major version (`1.0`) publishing.
   - *Source:* https://www.microsoft.com/en-us/microsoft-365/sharepoint/collaboration · https://learn.microsoft.com/en-us/sharepoint/intro-to-content-types
2. **OpenText Content Suite / Documentum** — Enterprise content server and information governance market leader. Implements structured document authoring workflows with central template repositories. Enforces the formal "Version 0" working draft paradigm (pre-release WIP drafts isolated from general organizational view until formal promotion), dynamic injection of repository metadata into document headers/footers, and lifecycle-driven template inheritance.
   - *Source:* https://www.opentext.com/products/documentum · https://www.opentext.com/products/content-suite-platform
3. **Templafy** — The global benchmark for enterprise template management and document creation infrastructure. Provides a centralized, cloud-hosted Template Library with role- and department-based access control. Features modular Digital Asset Libraries (reusable text blocks, standard clauses, boilerplate disclosures, branding assets), dynamic Smart Templates with variable token placeholders (`[Client.Name]`, `[User.Title]`), and offline template caching.
   - *Source:* https://www.templafy.com/platform/ · https://www.templafy.com/document-creation/
4. **PandaDoc** — Modern cloud document creation and authoring platform. Blends pre-approved template repositories with a modular Content Library of reusable snippets and drag-and-drop sections. Uses dynamic variables/tokens for auto-filling ERP and CRM metadata, inline suggestion mode (propose replacement, accept/reject), threaded review comments, and draft-to-published state management.
   - *Source:* https://www.pandadoc.com/features/document-templates/ · https://www.pandadoc.com/features/content-library/
5. **Zoho Writer / Zoho WorkDrive** — Collaborative document authoring and word processing engine. Offers granular content locking (locking specific sections, clauses, or headers from modification while leaving other sections editable), full track changes with multi-state markup views (All Markup, No Markup / Clean, Original), suggestion mode, pause-collaboration locks, and browser-cached offline drafting with automatic sync upon reconnect.
   - *Source:* https://www.zoho.com/writer/ · https://www.zoho.com/writer/features.html
6. **Box Content Cloud / Box Notes** — Cloud content management and collaborative authoring workspace. Features standardized document note templates, concurrent real-time co-authoring with live presence, inline rich text comments with @mention tagging, automatic revision snapshots, and draft status management.
   - *Source:* https://www.box.com/notes · https://www.box.com/content-cloud
7. **Hyland OnBase (Document Composition & Authoring)** — Enterprise information management platform. Provides Document Composition utilizing Template Groups, modular document fragments (reusable clauses and boilerplates), dynamic keyword tags, conditional inclusion rules, and interactive user-driven generation from structured form inputs.
   - *Source:* https://www.hyland.com/en/solutions/products/onbase · https://www.hyland.com/en/capabilities/document-generation
8. **Veeva Vault (QualityDocs & Collaborative Authoring)** — Regulated cloud content management platform. Automatically initializes new documents in a Draft `0.1` lifecycle state ("Version Zero"). Seamlessly integrates collaborative multi-user editing with Microsoft 365 co-authoring while maintaining immutable audit trails, draft comparison, and formal promotion gates to steady-state release.
   - *Source:* https://www.veeva.com/products/vault-qualitydocs/ · https://veevavault.help/en/lr/48102/

---

## Feature catalog (this sub-module only)

### Bullet 1 — Template Library & Standardization (Pre-approved templates, locked formatting, SOPs, memos, contracts)

- **Pre-Approved Template Master Catalog** — Centralized tenant repository of standardized document templates for contracts, reports, executive memos, SOPs, corporate letters, technical specifications, and proposals. · seen in: All leaders · priority: **table-stakes** · spine: new model `DocumentTemplate` [DTMPL-] · **buildable now**
- **Template Categorization & Department Scoping** — Categorizes templates by document type, domain, and target department (`core.OrgUnit`), ensuring users see templates relevant to their organizational role. · seen in: Templafy, SharePoint, OnBase · priority: **table-stakes** · spine: `DocumentTemplate.template_type` + FK `core.OrgUnit` · **buildable now**
- **Locked Formatting & Brand Styling Rules** — Enforces corporate typography, margins, color palettes, and header/footer configurations (`is_locked=True`), preventing ad-hoc deformation of official corporate stationery. · seen in: Templafy, Zoho Writer · priority: **table-stakes** · spine: `DocumentTemplate.is_locked` + `styling_rules` / CSS configuration · **buildable now**
- **Modular Content Blocks & Reusable Fragments** — Central library of modular document sections (boilerplate clauses, legal disclaimers, executive summaries, signature blocks) that can be linked to templates or dynamically inserted into drafts. · seen in: Templafy (Building Blocks), PandaDoc (Content Library), OnBase (Fragments) · priority: **table-stakes** · spine: new model `TemplateSection` [DSEC-] · **buildable now**
- **Section-Level Locking & Mandatory Enforcement** — Marks critical sections as locked (read-only in derived drafts) or mandatory (cannot be removed by authors), ensuring legal boilerplate cannot be deleted or modified. · seen in: Zoho Writer, Templafy · priority: **common** · spine: `TemplateSection.is_locked` + `is_mandatory` · **buildable now**
- **Dynamic Token & Variable Placeholders** — Templated token placeholders (e.g. `{{document_title}}`, `{{author_name}}`, `{{party_name}}`, `{{effective_date}}`, `{{org_unit}}`) that automatically populate from ERP entities upon draft instantiation. · seen in: PandaDoc, Templafy, OnBase · priority: **table-stakes** · spine: `DocumentTemplate.available_tokens` + parsing utility · **buildable now**

### Bullet 2 — Rich Text & Collaborative Editing (Multi-user editing, track changes, comments, suggestion mode)

- **Rich Text HTML/Markdown Authoring Canvas** — Visual formatting interface supporting H1–H6 headings, bold, italic, underline, strike, ordered/unordered lists, blockquotes, code blocks, and horizontal rules. · seen in: All leaders · priority: **table-stakes** · spine: `DocumentDraft.content` (TextField) · **buildable now**
- **Collaborative Co-Authoring & Multi-User Assignment** — Explicit tracking of the lead author (`author`) alongside multiple designated co-authors (`co_authors` ManyToMany `accounts.User`) with shared editing access. · seen in: Box Notes, SharePoint, Zoho Writer · priority: **table-stakes** · spine: `DocumentDraft.author` + `DocumentDraft.co_authors` · **buildable now**
- **Threaded Inline Comments & Discussions** — Contextual commentary attached to specific text selections or sections, supporting threaded replies, discussion resolution, and @mentions. · seen in: Box Notes, SharePoint, PandaDoc · priority: **table-stakes** · spine: new model `DraftCollaboration` [DCMT-] (`entry_type="comment"`) · **buildable now**
- **Suggestion Mode & Track Changes** — Collaborators propose edits without directly altering original text; each suggestion stores original selected text, proposed replacement text, and reviewer rationale. · seen in: Zoho Writer, PandaDoc · priority: **table-stakes** · spine: `DraftCollaboration` (`entry_type="suggestion"` / `"track_change"`) · **buildable now**
- **Suggestion Decision Workflow (Accept / Reject)** — Document owner reviews proposed suggestions with single-click actions to accept (applying replacement to draft content) or reject (closing the suggestion record). · seen in: Zoho Writer, PandaDoc · priority: **table-stakes** · spine: `DraftCollaboration.status` (`open`, `accepted`, `rejected`, `resolved`) · **buildable now**
- **Markup Visibility Views** — Visual toggle allowing users to view the draft with All Markup (showing strikethroughs and additions), No Markup / Clean (previewing the draft as if all accepted), or Original baseline. · seen in: Zoho Writer, Word Online · priority: **common** · spine: HTMX view toggle / template rendering · **buildable now**
- **Pause Collaboration / Author Lockout** — Lead author can temporarily pause external collaboration or lock edits to consolidate feedback without live interference. · seen in: Zoho Writer ("Pause Collaboration") · priority: **differentiator** · spine: `DocumentDraft.is_collaboration_locked` (BooleanField) · **buildable now**

### Bullet 3 — Version Zero & Draft Management (Initial draft creation, auto-save, comparison, promotion)

- **"Version Zero" Pre-Release Draft Container** — Enforces pre-release working draft isolation: documents start at `0.1` and increment minor decimals (`0.2`, `0.3`) during working iterations, completely segregated from official public released records. · seen in: Veeva Vault, Documentum, SharePoint · priority: **table-stakes** · spine: `DocumentDraft.draft_version` (default `"0.1"`) · **buildable now**
- **Periodic Auto-Save Engine & Dirty-State Tracking** — Automatic periodic saving of in-progress edits with timestamp logging (`auto_save_timestamp`) and unsaved change detection. · seen in: Box Notes, Zoho Writer, Word Online · priority: **table-stakes** · spine: `DocumentDraft.auto_save_timestamp` + HTMX periodic trigger · **buildable now**
- **Draft Comparison & Pre-Release Redline** — Visual comparison comparing the active draft content against either the parent template baseline or a previous draft milestone. · seen in: Veeva Vault, SharePoint, PandaDoc · priority: **common** · spine: View diff utility comparing draft content strings · **buildable now**
- **Promotion to Official Version 1.0** — Formal action graduating an approved draft to official status: seals the draft (`status="promoted"`), timestamps promotion (`promoted_at`), assigns official release version (`"1.0"`), and instantiates/links an official `core.Document` file attachment record. · seen in: Documentum, Veeva Vault, SharePoint · priority: **table-stakes** · spine: `DocumentDraft.status` + FK `core.Document` · **buildable now**
- **Draft Abandonment / Discard Lifecycle** — Safe retirement of abandoned or superseded WIP drafts (`status="discarded"`), preventing draft repository bloat while preserving audit history. · seen in: Documentum, OpenText Content Suite · priority: **common** · spine: `DocumentDraft.status` choices · **buildable now**

### Bullet 4 — Embedded Media & Objects (Image insertion, tables, chart linking, formulas)

- **Rich Image Embedding & Storage** — Insertion of figures, diagrams, and corporate badges into document content, stored securely and referenced via standard HTML `<img>` tags. · seen in: All leaders · priority: **table-stakes** · spine: `DocumentDraft.content` + media upload handler · **buildable now**
- **Structured Table Embedding & Formatting** — WYSIWYG creation of data tables with customizable headers, alternating rows, border styling, and column alignment. · seen in: PandaDoc, Box Notes, Zoho Writer · priority: **table-stakes** · spine: Rich text HTML `<table>` rendering · **buildable now**
- **Chart & KPI Reference Embeds** — Linking external BI/ERP metric cards or chart snapshots into reports and memos via structured iframe or embed cards. · seen in: PandaDoc, Box Notes · priority: **common** · spine: Embedded media block / snippet in `TemplateSection` or `DocumentDraft` · **buildable now**
- **Formula & Metric Placeholders** — Dynamic calculation fields (e.g. sums, subtotals, tax calculations, net values) evaluated during template merge or rendering. · seen in: PandaDoc, Zoho Writer · priority: **common** · spine: Token evaluation helper in draft view · **buildable now**

### Bullet 5 — Offline Authoring & Sync (Offline editing, dirty caching, conflict resolution)

- **Offline Client-Side Cache Stamping** — Tracks local client caching timestamps and client instance identifiers (`offline_client_id`) to support disconnected drafting in browser localStorage / PWA cache. · seen in: Zoho Writer, Templafy · priority: **common** · spine: `DocumentDraft.offline_client_id` + `offline_cached_at` · **buildable now**
- **Optimistic Concurrency & Conflict Detection** — On reconnect, compares client edit hash / timestamp against the server's `updated_at`; if another co-author edited the draft while the user was offline, flags the sync state as `conflict_pending`. · seen in: Zoho Writer, SharePoint · priority: **table-stakes** · spine: `DocumentDraft.sync_status` (`synced`, `conflict_pending`, `resolved`) · **buildable now**
- **Interactive Conflict Resolution Workflow** — User-facing diff screen allowing the author to resolve conflicts by selecting "Keep My Offline Version", "Keep Server Version", or performing manual side-by-side reconciliation. · seen in: SharePoint, Zoho Writer · priority: **common** · spine: View resolution action · **buildable now**

### Beyond the bullets

- **Template Instantiation Wizard** — Guided step-by-step modal prompting authors to select a template, choose target department (`core.OrgUnit`), link recipient party (`core.Party`), and fill required tokens before generating the draft. · seen in: Templafy, OnBase, PandaDoc · priority: **common** · spine: Creation view modal · **buildable now**
- **Document Readability & Word Count Telemetry** — Automatic calculation and live display of word count, character count, and estimated reading time. · seen in: Zoho Writer, Box Notes · priority: **common** · spine: `DocumentDraft.word_count` / template property · **buildable now**
- **Dynamic Watermark Preview** — Visual overlay stamping "DRAFT — VERSION 0.X (NOT FOR OFFICIAL USE)" across active draft views until officially promoted. · seen in: Veeva Vault, MasterControl · priority: **common** · spine: Template badge / CSS watermark · **buildable now**

---

## Recommended build scope (this pass — 4 models)

To fully implement Sub-module 13.1 while adhering strictly to the NavERP architecture, we recommend exactly **4 tenant-scoped models**:

### 1. `DocumentTemplate` [PREFIX: `DTMPL`]
- **Purpose:** Central catalog of pre-approved master document templates for corporate correspondence, contracts, SOPs, reports, and memos.
- **Fields:**
  - `number`: CharField (autonumbered `DTMPL-XXXXX` via `TenantNumbered`)
  - `name`: CharField(max_length=255)
  - `template_type`: CharField(max_length=30, choices: `contract`, `report`, `memo`, `sop`, `letter`, `proposal`, `policy`, `spec`, `other`)
  - `category`: CharField(max_length=100, blank=True, help_text="e.g. Legal, Finance, Operations, Human Resources")
  - `description`: TextField(blank=True)
  - `content`: TextField(help_text="Master HTML/Markdown template content with {{token}} placeholders")
  - `is_active`: BooleanField(default=True)
  - `is_locked`: BooleanField(default=False, help_text="Lock formatting, typography, and styling to prevent author alterations")
  - `styling_rules`: TextField(blank=True, help_text="JSON or CSS styling definitions for typography, margins, headers/footers")
  - `available_tokens`: JSONField(default=list, blank=True, help_text="List of supported tokens e.g. ['party_name', 'author', 'date']")
  - `version`: CharField(max_length=20, default="1.0")
  - `target_org_unit`: ForeignKey(`core.OrgUnit`, on_delete=SET_NULL, null=True, blank=True, related_name="document_templates")
  - `owner`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="owned_templates")
- **Justified by:** Bullet 1 (Template Library & Standardization), commercial features seen in Templafy, PandaDoc, SharePoint.

### 2. `TemplateSection` [PREFIX: `DSEC`]
- **Purpose:** Modular content blocks, boilerplate clauses, standard disclaimers, and reusable layout fragments.
- **Fields:**
  - `number`: CharField (autonumbered `DSEC-XXXXX` via `TenantNumbered`)
  - `template`: ForeignKey(`DocumentTemplate`, on_delete=CASCADE, null=True, blank=True, related_name="sections", help_text="Null for global reusable content library blocks")
  - `title`: CharField(max_length=255)
  - `section_type`: CharField(max_length=30, choices: `header`, `footer`, `clause`, `disclaimer`, `signature_block`, `table_block`, `media_block`, `custom`)
  - `content`: TextField(help_text="Rich text / HTML content of this section")
  - `order`: PositiveIntegerField(default=0)
  - `is_locked`: BooleanField(default=False, help_text="If locked, authors cannot edit this boilerplate section in derived drafts")
  - `is_mandatory`: BooleanField(default=False, help_text="If mandatory, this section cannot be deleted from derived drafts")
- **Justified by:** Bullet 1 (Modular Content Blocks, Section Locking), Bullet 4 (Embedded Media/Objects), commercial features seen in Templafy, PandaDoc, Zoho Writer.

### 3. `DocumentDraft` [PREFIX: `DDFT`]
- **Purpose:** The core authoring workspace and "Version Zero" working container where authors create, auto-save, co-edit, and refine documents before promotion.
- **Fields:**
  - `number`: CharField (autonumbered `DDFT-XXXXX` via `TenantNumbered`)
  - `title`: CharField(max_length=255)
  - `document_type`: CharField(max_length=30, choices: `contract`, `report`, `memo`, `sop`, `letter`, `proposal`, `policy`, `spec`, `other`)
  - `template`: ForeignKey(`DocumentTemplate`, on_delete=SET_NULL, null=True, blank=True, related_name="derived_drafts")
  - `status`: CharField(max_length=30, choices: `draft`, `in_review`, `ready_for_promotion`, `promoted`, `discarded`, default=`draft`)
  - `draft_version`: CharField(max_length=20, default="0.1", help_text="Pre-release version string e.g. 0.1, 0.2, 0.3")
  - `content`: TextField(help_text="Active rich text / HTML document body")
  - `content_format`: CharField(max_length=20, choices: `html`, `markdown`, `json_delta`, default=`html`)
  - `author`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, related_name="authored_drafts")
  - `co_authors`: ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="coauthored_drafts")
  - `department`: ForeignKey(`core.OrgUnit`, on_delete=SET_NULL, null=True, blank=True, related_name="draft_documents")
  - `related_party`: ForeignKey(`core.Party`, on_delete=SET_NULL, null=True, blank=True, related_name="referenced_document_drafts")
  - `auto_save_timestamp`: DateTimeField(null=True, blank=True)
  - `is_collaboration_locked`: BooleanField(default=False, help_text="Lead author paused external editing")
  - `offline_client_id`: CharField(max_length=64, blank=True, help_text="Client device identifier for offline reconciliation")
  - `offline_cached_at`: DateTimeField(null=True, blank=True)
  - `sync_status`: CharField(max_length=20, choices: `synced`, `conflict_pending`, `resolved`, default=`synced`)
  - `word_count`: PositiveIntegerField(default=0)
  - `promoted_at`: DateTimeField(null=True, blank=True)
  - `promoted_version`: CharField(max_length=20, blank=True, help_text="Official version assigned upon promotion e.g. 1.0")
  - `promoted_document`: ForeignKey(`core.Document`, on_delete=SET_NULL, null=True, blank=True, related_name="source_drafts")
- **Justified by:** Bullets 2, 3, 4, 5 (Authoring Canvas, Co-authoring, Version Zero, Auto-save, Promotion, Offline Sync), seen in Veeva Vault, Documentum, SharePoint, Zoho Writer.

### 4. `DraftCollaboration` [PREFIX: `DCMT`]
- **Purpose:** Inline collaborative commentary, discussion threads, track changes, and suggestion mode entries attached to specific draft sections.
- **Fields:**
  - `number`: CharField (autonumbered `DCMT-XXXXX` via `TenantNumbered`)
  - `draft`: ForeignKey(`DocumentDraft`, on_delete=CASCADE, related_name="collaborations")
  - `entry_type`: CharField(max_length=30, choices: `comment`, `suggestion`, `track_change`, default=`comment`)
  - `status`: CharField(max_length=30, choices: `open`, `accepted`, `rejected`, `resolved`, default=`open`)
  - `author`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, related_name="draft_collaborations")
  - `selected_text`: TextField(blank=True, help_text="Target text in draft being commented on or proposed for change")
  - `replacement_text`: TextField(blank=True, help_text="Proposed replacement text in suggestion mode")
  - `comment_text`: TextField(blank=True, help_text="Discussion remarks or reviewer notes")
  - `section_anchor`: CharField(max_length=100, blank=True, help_text="HTML element ID or block reference")
  - `resolved_by`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="resolved_collaborations")
  - `resolved_at`: DateTimeField(null=True, blank=True)
- **Justified by:** Bullet 2 (Collaborative Editing, Track Changes, Suggestion Mode, Inline Comments), commercial features seen in Zoho Writer, PandaDoc, SharePoint, Box Notes.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Post-Promotion Major/Minor Versioning & Check-in / Check-out Locks** → **Sub-module 13.2 (Version Control & Revision Management)**: Sub-module 13.1 handles the pre-release "Version Zero" working draft (`0.x`) and initial promotion to `1.0`. Full enterprise check-in/out locks, multi-version branch/merge, and side-by-side historical revision diffing belong to 13.2.
- **Multi-Tier Visual Approval Workflows & Electronic Signatures** → **Sub-module 13.3 (Document Approval & Review Workflow)**: Visual approval designer, conditional routing, delegation, escalation rules, and 21 CFR Part 11 / e-signatures belong to 13.3.
- **Taxonomy, Folder Hierarchy & Physical Storage Tiering** → **Sub-module 13.4 (Document Storage & Repository)**: Nested directories, hot/cold tiering, bulk ZIP import, and repository quotas belong to 13.4.
- **Custom Metadata Schemas, Auto-Tagging & OCR** → **Sub-module 13.5 (Metadata & Indexing)**: Full OCR indexing, thesauri, and auto-tagging belong to 13.5.
- **Faceted Full-Text Search & Saved Search Alerts** → **Sub-module 13.6 (Search & Discovery)**: Search indices, query ranking, and search alerts belong to 13.6.
- **Access Control Policies, DRM & Watermark Security** → **Sub-module 13.7 (Document Security & Access Control)**: Granular document permissions, document classification enforcement, and DRM download protection belong to 13.7.
- **Interactive Electronic Forms Engine** → **Sub-module 13.15 (Electronic Forms & Data Capture)**: Dynamic web form builder and kiosk intake belong to 13.15.
- **Contract Lifecycle Management (CLM) Negotiation** → **Sub-module 13.16 (Contract Lifecycle Management)**: Clause fallback positions, redlining with external counterparties, and contract milestone obligation tracking belong to 13.16.

---

## Deferred (later passes / integrations)

- **WebSocket Real-Time Collaborative Cursor Engine (OT / CRDT)** — True Google Docs style simultaneous multi-cursor typing requires Daphne/Redis/Channels. In this Django 5.1 HTMX pass, collaborative editing is supported through optimistic concurrency, async auto-save polling, suggestion mode (propose/accept/reject), and author lockouts.
- **Microsoft 365 / Word Online WOPI Cloud Protocol Integration** — Direct web check-out to Office 365 cloud editors requires external Azure tenant setup; deferred to future external integration.
- **ServiceWorker PWA Client for Complete Offline Desktop/Mobile App** — Client-side ServiceWorker and IndexedDB offline storage shell will be layered on top in Sub-module 13.13 (Mobile Document Management).
