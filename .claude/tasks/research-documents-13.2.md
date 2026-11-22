# Research — Sub-module 13.2: Version Control & Revision Management (Module 13 — Document Management System, `documents`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 13 so far:** None (`documents` is a brand-new app; `13.2` is the initial sub-module being scaffolded directly per user instructions).
- **Existing document models in peer modules (verified distinct boundaries):**
  - `apps/core/models/Document.py:5`: Generic attachment model (`content_type`, `object_id`, `file`, `name`, `classification`, `version`). Docstring explicitly states: *"Generic file attachment for any record (DMS module later layers folders/versions on top)"*.
  - `apps/quality/models/DocumentControl/ControlledDocuments.py:8`: `ControlledDocument` (`QDOC-`), ISO 9001/21 CFR Part 11 SOPs, change orders, training acknowledgments.
  - `apps/procurement/models/DocumentKnowledgeManagement/Documents.py:146`: `ProcurementDocument` (`PDOC-`) and `ProcurementDocumentRevision`. Notes explicitly state: *"It is also not Module 13: folder hierarchies (13.4), redlining and branching (13.2), permission matrices / watermarking / DRM (13.7) all stay there."*
  - `apps/assets/models/AssetDocumentKnowledge/AssetDocuments.py:22`: `AssetDocument` (`ADOC-`).
  - `apps/crm/models/DocumentContract/DocumentVersions.py`: CRM contract attachment versions.
  - `apps/scm/models/ContractCompliance/TradeDocuments.py`: International trade & shipping documentation.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` → `class Tenant(models.Model)` | Tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` → `class OrgUnit(models.Model)` | Department / division scoping. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Unified party spine. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `apps/core/utils.py` `write_audit_log` | Central audit logging. |
| `core.NumberingScheme` exists | `apps/core/models/NumberingScheme.py:15` | Tenant-scoped autonumbering engine. |
| `accounts.User` exists | `apps/accounts/models.py:52` → `class User(AbstractBaseUser, PermissionsMixin)` | Auth user model for authors, lock-holders, approvers. |
| `apps.documents.models._base.TenantOwned` & `TenantNumbered` exist | `apps/documents/models/_base.py:8,17` | Multi-tenant numbered abstract bases (to scaffold). |

### Spine entities verified NOT to exist

- **No DMS app tables yet:** Database and model searches confirm zero DMS tables currently exist in `apps/documents/models/`.

### Candidate prefix collision check (repo-wide automated verification)

Automated scan of all `NUMBER_PREFIX` declarations across the entire codebase confirmed:
- `DOC` (DMS Document Record) → **0 collisions** (Free)
- `DVER` (Document Version) → **0 collisions** (Free)
- `DLOCK` (Document Checkout / Lock) → **0 collisions** (Free)
- `DBRN` (Document Branch / Variant) → **0 collisions** (Free)

---

## Leaders surveyed (with source links)

1. **OpenText Documentum** — Enterprise Content Management (ECM) leader for highly regulated industries (energy, aerospace, life sciences). Enforces strict Check-Out (working copy creation and exclusive server-side lock) and Check-In (prompting user for Major `2.0` vs Minor `1.1` version increment). Supports non-linear branch versioning (e.g., checking out older version `1.0` while mainline is `2.0` automatically spins off branch `1.0.1.0`), preserving historical baselines while allowing parallel variants.
   - *Source:* https://www.opentext.com/products/documentum-server · https://support.opentext.com/
2. **Microsoft SharePoint / OneDrive for Business** — Standard enterprise document library platform. Features Major (published milestone, visible to readers) and Minor (draft work-in-progress, visible only to editors) versioning. Offers explicit Check-Out (exclusive lock preventing overwrite), Discard Check-Out (discards in-progress edits and restores previous state without incrementing version), and Check-In (prompts for minor/major choice and comments). Point-in-time restoration rolls an older version forward as a new current version. Configurable version retention limits prune older minor versions.
   - *Source:* https://support.microsoft.com/en-us/office/version-history-in-sharepoint-and-onedrive · https://learn.microsoft.com/en-us/sharepoint/governance-versioning
3. **Alfresco Content Services (Hyland)** — CMIS-compliant open-source and commercial enterprise repository. Utilizes the `cm:versionable` aspect to track linear version chains. Check-Out creates a temporary `cm:workingcopy` child node in a working space while locking the parent document. Check-In merges working copy bytes back into the parent, increments major/minor number, and deletes the temporary node. Cancel Check-Out deletes the working copy and unlocks the node.
   - *Source:* https://www.hyland.com/en/products/alfresco-content-services · https://docs.alfresco.com/content-services/latest/develop/repo/versioning/
4. **Box (Enterprise & Box Governance)** — Cloud content platform emphasizing collaboration safeguards. Employs sequential automated versioning on save/upload. Provides explicit File Locking with optional timeout/duration and download prevention. Historical version panel allows preview, download, and non-destructive revert to make an older version current. Box Governance enforces enterprise version pruning and retention policies (e.g. retain last 100 versions).
   - *Source:* https://www.box.com/content-management · https://support.box.com/hc/en-us/articles/360043697054-Version-History
5. **M-Files** — Metadata-driven document management system. Replaces folder navigation with metadata cards and robust version control. Check-Out locks files against simultaneous edits, showing locked badges while permitting read-only viewing. Check-In records mandatory change descriptions. Includes built-in Document Compare / Diff View to inspect text insertions, deletions, and metadata deltas between any two historical versions. Rollback restores historical files forward as a new latest version to preserve compliance audit chains.
   - *Source:* https://www.m-files.com/product/document-management/ · https://userguide.m-files.com/user-guide/latest/eng/Version_history.html
6. **NetDocuments** — Dedicated legal and corporate DMS. Introduces the concept of "Official Version", allowing any historical version to be designated as the authoritative client-facing baseline. Supports Full Versions (v1, v2) and Subversions (v1.1, v1.2). Offers "Check Out as New Version" to branch a new draft off the official baseline while keeping the baseline untouched. Integrates redline comparison engines to view inline text changes across versions.
   - *Source:* https://www.netdocuments.com/platform/document-management · https://support.netdocuments.com/s/article/205217980
7. **Laserfiche** — Enterprise content and workflow platform. Employs electronic document check-out locking, bundling all interim modifications into a single clean check-in version. Provides a comprehensive "Compare Changes" (Diff) tool displaying file change flags, image/text additions and deletions, OCR differences, and metadata property deltas between any two versions.
   - *Source:* https://www.laserfiche.com/products/document-management/ · https://doc.laserfiche.com/laserfiche.documentation/en-us/Default.htm#Client/Version_History.htm
8. **Egnyte** — Hybrid cloud content governance system. Features automatic and manual file locking during editing sessions to prevent collisions. Includes administrative break-lock / force-unlock capabilities with reason capture to resolve orphaned check-outs. Version history logs all updates with restore points and configurable version retention limits.
   - *Source:* https://www.egnyte.com/features/content-collaboration · https://helpdesk.egnyte.com/hc/en-us/articles/201637774-File-Locking
9. **DocuWare** — Cloud and on-premise document management system. In file cabinets with version management enabled, Check-Out moves files to personal trays and locks the archived record. Check-In requires incrementing the version number (major/minor) and submitting change comments, archiving previous revisions into a permanent audit trail.
   - *Source:* https://www.docuware.com/en-us/solutions/document-management · https://help.docuware.com/en/latest/user/Version_Management.html

---

## Feature catalog (this sub-module only)

### Bullet 1 — Automatic Version Numbering
- **Major.Minor.Build Version Numbering** — Generates structured version strings (e.g., `1.0`, `1.1`, `2.0`, `2.0.1`) where major increments represent approved milestone publications and minor increments represent working drafts. · seen in: Documentum, SharePoint, DocuWare · priority: **table-stakes** · spine: `DocumentVersion` fields (`major_number`, `minor_number`, `patch_number`, `version_label`) · **buildable now**
- **Semantic Versioning (SemVer) Support** — Strict `MAJOR.MINOR.PATCH` sequence tracking breaking changes, additive changes, and bug/typo fixes. · seen in: Modern DMS / docs-as-code · priority: **common** · spine: `Document.versioning_scheme = "semantic"` · **buildable now**
- **Custom Versioning Schemas** — Supports configurable version schemes per document or tenant: `major_minor` (1.0, 1.1), `semantic` (1.0.0), `sequential` (v1, v2), and `alphanumeric` (Rev A, Rev B). · seen in: NetDocuments, Laserfiche · priority: **common** · spine: `Document.versioning_scheme` choice field · **buildable now**
- **Official / Published Version Pointer** — Explicit designation of the active/official version visible to standard readers while draft versions remain in progress. · seen in: NetDocuments, SharePoint · priority: **table-stakes** · spine: `Document.current_version_no` integer pointer + `DocumentVersion.is_official` boolean · **buildable now**
- **Auto-Calculated Version Deltas** — When checking in, user selects increment intent (`minor_edit`, `major_milestone`, `patch_fix`), automatically computing the next version label based on the active scheme. · seen in: Documentum, DocuWare, SharePoint · priority: **table-stakes** · spine: `DocumentVersion.calculate_next_label()` helper · **buildable now**

### Bullet 2 — Check-in / Check-out Mechanism
- **Exclusive Editing Locks** — When a user checks out a document, an exclusive editing lock is created, restricting other users to read-only viewing or downloading until check-in. · seen in: All leaders · priority: **table-stakes** · spine: `DocumentLock` model + `Document.is_locked` flag · **buildable now**
- **Working Copy Ingestion & Draft Staging** — Check-out allows attaching an interim working copy file to the lock record, staging changes before final check-in. · seen in: Alfresco (`cm:workingcopy`), Documentum · priority: **common** · spine: `DocumentLock.working_copy_file` · **buildable now**
- **Reservation Alerts & Lock Status Banners** — Displays lock status, name of user holding lock, checkout timestamp, and intended change note to other users viewing the document. · seen in: SharePoint, M-Files, Box · priority: **table-stakes** · spine: `Document.locked_by`, `locked_at`, UI warning banner · **buildable now**
- **Administrative Force Check-in / Break-Lock Override** — Allows authorized administrators or managers to forcibly break an orphaned or stale lock with a mandatory override justification, restoring edit access while preserving audit trail. · seen in: Egnyte, SharePoint, Box · priority: **table-stakes** · spine: `DocumentLock.status = "force_unlocked"`, `override_reason` + `core.AuditLog` · **buildable now**
- **Lock Expiration & Stale Lock Timeout** — Configurable lock timeout (e.g., 24 hours) after which reservation alerts warn of stale locks or allow scheduled auto-unlock. · seen in: Box, Egnyte · priority: **common** · spine: `DocumentLock.expires_at` · **buildable now**
- **Discard / Cancel Check-out** — Unlocks the document and discards any staged working copy without creating a new version or altering the document's version number. · seen in: SharePoint, Alfresco, M-Files · priority: **table-stakes** · spine: `DocumentLock.status = "discarded"`, release lock flag · **buildable now**
- **Check-in Change Summary & Categorization** — Mandatory change summary logging upon check-in to explain the modifications. · seen in: All leaders · priority: **table-stakes** · spine: `DocumentVersion.change_summary` · **buildable now**

### Bullet 3 — Version Comparison & Diff View
- **Side-by-Side Version Comparison** — Compare any two historical versions (`version_a` vs `version_b`) or current vs immediate predecessor. · seen in: M-Files, Laserfiche, NetDocuments · priority: **table-stakes** · spine: Compare view + template · **buildable now**
- **Visual Redline & Highlighted Text Changes** — Line-by-line and token-level diff rendering with green insertion highlights (`<ins>`) and red strikethrough deletions (`<del>`) generated via Python `difflib`. · seen in: M-Files, NetDocuments, Laserfiche · priority: **table-stakes** · spine: `difflib.HtmlDiff` helper comparing `extracted_text` · **buildable now**
- **Metadata Property Deltas** — Structured comparison of metadata changes between versions (title, classification, status, file size, SHA-256 hash, author, timestamps). · seen in: Laserfiche, M-Files · priority: **table-stakes** · spine: View context dictionary `metadata_diff` · **buildable now**
- **Redline Summary Generation** — Automated statistical summary of diff (e.g. "+14 lines added, -5 lines deleted, 2 metadata fields changed"). · seen in: NetDocuments, Laserfiche · priority: **common** · spine: View helper computing diff metrics · **buildable now**

### Bullet 4 — Branching & Parallel Versions
- **Document Revision Branching** — Ability to fork a document from any historical version to create an independent parallel revision stream (e.g., "EU Compliance Variant", "What-If 2027 Expansion", "Vendor Negotiation Draft"). · seen in: Documentum (1.0.1.0 branch trees), Docs-as-code · priority: **differentiator** · spine: **new model `DocumentBranch`** (`DBRN-`) · **buildable now**
- **What-If Scenario Modeling** — Flagging branches as exploratory scenarios that can be evaluated in isolation without affecting the live mainline document. · seen in: Documentum, Accruent Meridian · priority: **differentiator** · spine: `DocumentBranch.branch_type = "what_if"` · **buildable now**
- **Merge-Back to Mainline** — Merging approved branch changes back into the primary document line as a new milestone or major version, recording branch lineage and merge notes. · seen in: Documentum, Docs-as-code · priority: **differentiator** · spine: `DocumentBranch.merge_into_version` FK to `DocumentVersion` + `DocumentBranch.status = "merged"` · **buildable now**
- **Branch Abandonment** — Closing an unneeded what-if scenario or rejected variant draft with rationale, keeping audit history. · seen in: Documentum · priority: **common** · spine: `DocumentBranch.status = "abandoned"` · **buildable now**

### Bullet 5 — Version History & Rollback
- **Immutable Version Audit Trail** — Chronological register of every version created, including version label, author, timestamp, change summary, file size, and cryptographic SHA-256 digest. · seen in: All leaders · priority: **table-stakes** · spine: `DocumentVersion` model + `core.AuditLog` · **buildable now**
- **Point-in-Time Non-Destructive Rollback** — Restoring a historical version does NOT delete newer history; instead, it copies the selected historical version's content and publishes it forward as a NEW version (e.g., restoring v1.0 creates v2.1 with "Restored from v1.0"), preserving strict regulatory audit trails. · seen in: M-Files, SharePoint, Box · priority: **table-stakes** · spine: Rollback view creating new `DocumentVersion` with `restored_from_version` FK · **buildable now**
- **Version Pruning & Retention Policies** — Document-level or tenant-level rule setting maximum versions to retain (e.g. keep all major versions, limit minor drafts to 50 versions). · seen in: Box, SharePoint · priority: **common** · spine: `Document.max_versions_retained` + pruning service method · **buildable now**

---

## Recommended build scope (this pass — 4 models)

To establish the primary DMS foundational record and deliver complete coverage of 13.2 Version Control & Revision Management, the recommended build scope comprises exactly **4 tenant-scoped models**:

### 1. `Document` (or `DocumentRecord`) [DOC-]
The root document entity in the DMS repository representing the logical document container.
- **Fields:**
  - `number`: `CharField(max_length=32)` (`NUMBER_PREFIX = "DOC"`)
  - `title`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255, blank=True)`
  - `description`: `TextField(blank=True)`
  - `document_type`: `CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, default="general")` (general, contract, policy, sop, report, specification, proposal, template, technical)
  - `classification`: `CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default="internal")` (public, internal, confidential, restricted)
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft")` (draft, in_review, approved, published, archived, superseded, deprecated)
  - `versioning_scheme`: `CharField(max_length=20, choices=VERSIONING_SCHEME_CHOICES, default="major_minor")` (major_minor, semantic, sequential, alphanumeric)
  - `current_version_label`: `CharField(max_length=32, default="1.0")` (denormalized display label)
  - `current_version_no`: `PositiveIntegerField(default=1)` (integer pointer to prevent circular FKs, resolves via `versions` reverse accessor)
  - `is_locked`: `BooleanField(default=False)`
  - `locked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="locked_documents")`
  - `locked_at`: `DateTimeField(null=True, blank=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_documents")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")`
  - `max_versions_retained`: `PositiveIntegerField(default=0, help_text="0 for unlimited, or max historical versions kept")`
  - `tags`: `CharField(max_length=500, blank=True)`
- **FKs:** `core.Tenant` (via `TenantNumbered`), `accounts.User` (`owner`, `locked_by`), `core.OrgUnit` (`department`)

### 2. `DocumentVersion` [DVER-]
The immutable snapshot of a document at a specific revision step.
- **Fields:**
  - `number`: `CharField(max_length=32)` (`NUMBER_PREFIX = "DVER"`)
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="versions")`
  - `version_label`: `CharField(max_length=32)` (e.g., "1.0", "1.1", "2.0")
  - `major_number`: `PositiveIntegerField(default=1)`
  - `minor_number`: `PositiveIntegerField(default=0)`
  - `patch_number`: `PositiveIntegerField(default=0)`
  - `version_type`: `CharField(max_length=20, choices=VERSION_TYPE_CHOICES, default="minor")` (major, minor, patch, branch_merge, rollback)
  - `file`: `FileField(upload_to="documents/versions/%Y/%m/")`
  - `file_name`: `CharField(max_length=255)`
  - `file_size`: `BigIntegerField(default=0)`
  - `file_hash`: `CharField(max_length=64, blank=True, help_text="SHA-256 checksum")`
  - `mime_type`: `CharField(max_length=100, blank=True)`
  - `change_summary`: `CharField(max_length=500, blank=True)`
  - `extracted_text`: `TextField(blank=True, help_text="Text content layer for search and redline diffing")`
  - `is_official`: `BooleanField(default=False)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="approved")` (draft, pending_review, approved, superseded, archived)
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_document_versions")`
  - `branch`: `ForeignKey("documents.DocumentBranch", on_delete=models.SET_NULL, null=True, blank=True, related_name="versions")`
  - `restored_from_version`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="restorations")`
- **FKs:** `core.Tenant`, `documents.Document`, `accounts.User`, `documents.DocumentBranch`, `self`

### 3. `DocumentLock` [DLOCK-]
Exclusive check-in/check-out lock governing reservation, editing exclusivity, and forced override.
- **Fields:**
  - `number`: `CharField(max_length=32)` (`NUMBER_PREFIX = "DLOCK"`)
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="locks")`
  - `base_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.PROTECT, related_name="checked_out_locks")`
  - `locked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_locks")`
  - `checked_out_at`: `DateTimeField(auto_now_add=True)`
  - `expires_at`: `DateTimeField(null=True, blank=True)`
  - `lock_type`: `CharField(max_length=20, choices=LOCK_TYPE_CHOICES, default="exclusive")` (exclusive, reservation)
  - `checkout_note`: `CharField(max_length=500, blank=True)`
  - `working_copy_file`: `FileField(upload_to="documents/working_copies/%Y/%m/", null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active")` (active, checked_in, discarded, force_unlocked)
  - `unlocked_at`: `DateTimeField(null=True, blank=True)`
  - `unlocked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="unlocked_document_locks")`
  - `override_reason`: `TextField(blank=True, help_text="Mandatory justification for administrative override")`
- **FKs:** `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `accounts.User`

### 4. `DocumentBranch` [DBRN-]
Parallel revision stream and what-if scenario tracking with merge-back capabilities.
- **Fields:**
  - `number`: `CharField(max_length=32)` (`NUMBER_PREFIX = "DBRN"`)
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="branches")`
  - `name`: `CharField(max_length=120)` (e.g. "eu-variant", "proposal-draft-b")
  - `description`: `TextField(blank=True)`
  - `base_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.PROTECT, related_name="branched_children")`
  - `branch_type`: `CharField(max_length=20, choices=BRANCH_TYPE_CHOICES, default="what_if")` (what_if, variant, draft_revision)
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active")` (active, merged, abandoned)
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_document_branches")`
  - `merged_at`: `DateTimeField(null=True, blank=True)`
  - `merged_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="merged_document_branches")`
  - `merged_into_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_branch")`
  - `merge_strategy`: `CharField(max_length=30, choices=MERGE_STRATEGY_CHOICES, default="new_major_version")` (new_major_version, new_minor_version, replace_content)
  - `merge_notes`: `TextField(blank=True)`
- **FKs:** `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `accounts.User`

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Pre-approved template library, locked formatting, rich text collaborative editing → **13.1 Document Creation & Authoring**
- Visual workflow designer, multi-tier approval routing, 21 CFR Part 11 / e-signatures, annotation layers → **13.3 Document Approval & Review Workflow**
- Folder hierarchies, storage quotas, hot/warm/cold tiering, bulk ZIP ingestion → **13.4 Document Storage & Repository**
- Custom metadata schemas, OCR full-text pipelines, auto-tagging & categorization → **13.5 Metadata & Indexing**
- Faceted search, query optimization, conversational AI search → **13.6 Search & Discovery**
- Granular permission matrix, dynamic watermarking, DRM encryption, print/copy protection → **13.7 Document Security & Access Control**
- Secure external sharing links, guest portal, co-authoring invitations → **13.8 Document Sharing & Collaboration**
- Transmittals, distribution lists, receipt acknowledgments → **13.9 Document Routing & Distribution**
- Retention schedules, legal hold enforcement, disposition certificates → **13.10 Records Management & Retention**
- Tamper-proof audit logs, compliance reports → **13.11 Compliance & Audit Trail**
- PDF/A creation, OAIS preservation, WORM storage → **13.14 Document Archival & Long-Term Preservation**
- Contract clause library, fallback positions, DocuSign integration → **13.16 Contract Lifecycle Management (CLM)**

---

## Deferred (later passes / integrations)

- **CAD / 3D binary mesh visual redlining** — Text and document (PDF/Office) diffing is buildable now via `difflib` and text layers; 3D/CAD drawing comparison requires external WebGL engines.
- **WebSocket real-time collaborative multi-cursor locks** — Real-time Google Docs-style operational transformation belongs to future real-time services; exclusive check-out locking completely fulfills enterprise DMS requirements now.
- **AI-driven automatic three-way merge resolution** — Automatic conflict merging without human review is deferred to future AI service integrations.
