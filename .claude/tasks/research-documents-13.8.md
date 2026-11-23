# Research — Sub-module 13.8: Collaboration & Sharing (Module 13 — Document Management System, documents)

## Repo state checked first

- **LIVE_LINKS built so far in module 13 (verified in `apps/core/navigation.py`):**
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
  - `13.3` (Document Approval & Review Workflow):
    - `Visual Workflow Designer`: `documents:workflow_list` (`DocumentApprovalWorkflow`)
    - `Electronic Signature Capture`: `documents:signature_list` (`DocumentSignature`)
    - `Delegation & Escalation Rules`: `documents:approval_request_list` (`DocumentApprovalRequest`)
    - `Review Comments & Annotation`: `documents:review_comment_list` (`DocumentReviewComment`)
    - `Approval Dashboard & Status Tracking`: `documents:approval_dashboard`
  - `13.4` (Document Storage & Repository):
    - `Folder Hierarchy & Taxonomy`: `documents:folder_list` (`DocumentFolder`)
    - `Cloud & On-Premises Deployment`: `documents:storage_volume_list` (`StorageVolume`)
    - `Storage Tiering & Optimization`: `documents:storage_volume_list?tier=hot` (`StorageVolume`)
    - `Document Linking & Relationships`: `documents:relationship_list` (`DocumentRelationship`)
    - `Bulk Upload & Import`: `documents:batch_import_list` (`DocumentBatchImport`)
  - `13.5` (Metadata & Indexing):
    - `MetadataSchema` (`apps/documents/models/MetadataIndexing/MetadataSchemas.py`, `NUMBER_PREFIX = "DSCH"`)
    - `DocumentMetadataValue` (`apps/documents/models/MetadataIndexing/DocumentMetadataValues.py`, `NUMBER_PREFIX = "DMETA"`)
    - `TaxonomyTerm` (`apps/documents/models/MetadataIndexing/TaxonomyTerms.py`, `NUMBER_PREFIX = "DTAX"`)
    - `DocumentOcrJob` (`apps/documents/models/MetadataIndexing/DocumentOcrJobs.py`, `NUMBER_PREFIX = "DOCR"`)
  - `13.6` (Search & Discovery):
    - `DocumentSavedSearch` (`apps/documents/models/SearchDiscovery/DocumentSavedSearches.py`, `NUMBER_PREFIX = "DSVD"`)
    - `DocumentSearchAlert` (`apps/documents/models/SearchDiscovery/DocumentSearchAlerts.py`, `NUMBER_PREFIX = "DALT"`)
    - `DocumentSearchSynonym` (`apps/documents/models/SearchDiscovery/DocumentSearchSynonyms.py`, `NUMBER_PREFIX = "DSYN"`)
    - `DocumentSearchQueryLog` (`apps/documents/models/SearchDiscovery/DocumentSearchQueryLogs.py`, `NUMBER_PREFIX = "DQRY"`)

- **Sibling models available to FK in `apps/documents/` (verified via grep):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Logical document master record containing title, slug, classification, document_type, status, owner, department, tags, version tracking.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Physical file revision snapshot with binary file payload, hash, size, MIME type, and extracted text.
  - `documents.DocumentFolder` (`apps/documents/models/StorageRepository/DocumentFolders.py:9`, `NUMBER_PREFIX = "DFLD"`): Hierarchical folder tree for repository-scoped shares and folder-level collaboration.
  - `documents.DocumentDraft` (`apps/documents/models/DocumentAuthoring/DocumentDrafts.py:38`, `NUMBER_PREFIX = "DDFT"`): Pre-publication draft for collaborative authoring sessions.
  - `documents.DocumentReviewComment` (`apps/documents/models/ApprovalWorkflow/DocumentReviewComments.py:8`, `NUMBER_PREFIX = "DREV"`): Document review comments, highlights, sticky notes, redlines, drawing callouts with page numbers, coordinates (`coordinate_ref`), and threaded replies (`parent`).
  - `documents.DraftCollaboration` (`apps/documents/models/DocumentAuthoring/DraftCollaborations.py:21`, `NUMBER_PREFIX = "DCMT"`): Pre-publication draft-stage inline comments and suggestions on `DocumentDraft`.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): Enterprise users, share creators, link recipients, coauthor collaborators, task assignees, and activity actors.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Organizational units for department-scoped sharing and team task routing.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:class AuditLog`): System-wide immutable security audit logging.
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing atomic concurrency-safe sequential number generation (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DSHR` (`DocumentShare`): Verified free (0 matches across repo).
  - `DCOA` (`CoauthorSession`): Verified free (0 matches across repo).
  - `DTSK` (`DocumentTask`): Verified free (0 matches across repo).
  - `DACT` (`DocumentActivity`): Verified free (0 matches across repo).
  - All existing prefixes in `apps/documents/` preserved without collision: `DOC`, `DVER`, `DLOCK`, `DBRN`, `DTMPL`, `DSEC`, `DDFT`, `DCMT`, `DWF`, `DAPR`, `DSIG`, `DREV`, `DFLD`, `DSTG`, `DREL`, `DBLK`, `DSCH`, `DMETA`, `DTAX`, `DOCR`, `DSVD`, `DALT`, `DQRY`, `DSYN`.

---

## Leaders surveyed (with source links)

1. **Box (Box Shared Links, Box Annotations, Tasks & Activity Stream)** — Enterprise cloud content management standard. Features secure shared links with granular access levels (People in company, People with link, Invited collaborators only), password protection, auto-expiration dates, download restrictions, in-viewer text highlights/drawing annotations with `@mentions`, file-level review/approval tasks with due dates, and a real-time web notification center/activity stream.
   - *Source:* https://support.box.com/hc/en-us/articles/360043696314-Search-for-Files-and-Folders · https://support.box.com/hc/en-us/articles/360043697554-Creating-Shared-Links
2. **Google Drive & Google Docs (Real-Time Presence, Action Items & Activity Dashboard)** — Global market leader for real-time document collaboration. Features link-based sharing with Viewer, Commenter, and Editor roles, temporary access expiration dates, live avatar and colored cursor presence tracking during simultaneous editing, `@mention` comments convertible into assigned actionable tasks with checkboxes, and an item Activity Dashboard tracking who viewed and collaborated.
   - *Source:* https://support.google.com/drive/answer/2494822 · https://support.google.com/docs/answer/65129
3. **Microsoft SharePoint & OneDrive (Anyone Links, Modern Comments & Office Co-Authoring)** — Enterprise standard across Fortune 500 organizations. Provides "Anyone" anonymous public links, internal organization links, and specific people links, mandatory tenant-wide password and expiration enforcement, real-time multi-user co-authoring in Office Online with collaborator cursor tags, Modern Comments with task assignment via `@mentions`, and item-level activity feeds.
   - *Source:* https://learn.microsoft.com/en-us/sharepoint/turn-external-sharing-on-or-off · https://support.microsoft.com/en-us/office/document-collaboration-and-co-authoring-ee1509b4-1f6e-401e-b04a-78b1a55fae16
4. **Dropbox & Dropbox Paper (Shared Links, In-Viewer Annotations & Action Items)** — Pioneer in file synchronization and cloud sharing. Offers shared links with view/edit permissions, optional password protection, link expiration dates, download disabling, in-document commenting and pinpoint visual annotations on PDFs and images, task assignment with assignees and due dates, and item activity history feeds.
   - *Source:* https://help.dropbox.com/share/share-with-others · https://help.dropbox.com/share/set-link-permissions
5. **M-Files (Secure External Sharing, Co-Authoring with Microsoft 365 & Assignment Objects)** — Metadata-first enterprise information management platform. Provides secure external link sharing with view or edit capabilities, seamless real-time co-authoring of Office documents via Microsoft 365, native Assignment objects routing document review tasks with deadlines and completion states, and an audit/social activity stream on document cards.
   - *Source:* https://userguide.m-files.com/user-guide/latest/eng/sharing_files.html · https://www.m-files.com/product/document-management/
6. **Egnyte (Public & Password-Protected Direct Links, Co-Editing & Project Workflows)** — Enterprise file services platform for architecture, life sciences, and financial services. Offers direct file and folder links with custom or auto-generated passwords, expiration by date or click count, web co-editing via Microsoft 365 and Google Workspace without local download, file task assignment with multi-step review workflows, and a centralized Links Management Dashboard.
   - *Source:* https://helpdesk.egnyte.com/hc/en-us/articles/201638244-Sharing-Links · https://helpdesk.egnyte.com/hc/en-us/articles/360029312132-Creating-Tasks-and-Workflows
7. **Nextcloud (Federated Cloud Sharing, Nextcloud Office Co-Authoring & Activity App)** — Premier open-source on-premises content collaboration platform. Features public link shares with password protection, enforced expiry dates, read/write/hide-download permissions, live collaborative editing via Nextcloud Office (Collabora / OnlyOffice), sidebar file comments with `@mentions`, integrated Deck/Tasks cards, and an Activity app providing real-time notification streams and email digests.
   - *Source:* https://docs.nextcloud.com/server/latest/user_manual/en/files/sharing.html · https://nextcloud.com/collaboraonline/
8. **OpenText Content Server & Core Share (Hybrid Cloud Sharing, Brava Annotations & Workflow Tasks)** — Premier regulated industry enterprise content platform. Implements hybrid cloud-sharing links via OpenText Core Share, mandatory enterprise link passwords and expiry schedules, real-time Office 365 co-authoring with automated check-in back to Content Server, Brava viewer annotation layers, document review tasks, and unified activity tracking.
   - *Source:* https://www.opentext.com/products/core-share · https://www.opentext.com/products/content-server

---

## Feature catalog (this sub-module only)

### Internal & External Sharing
- **Link-Based Secure Sharing (`DocumentShare` - `DSHR`)** — Generates unique, cryptographically random, unguessable sharing tokens (URLs) allowing internal colleagues or external external third parties to access documents or folders without requiring full administrative system accounts. · seen in: Box Shared Links, Google Drive, OneDrive, Dropbox, Egnyte · priority: **table-stakes** · spine: `DocumentShare` (`DSHR`), `Document`, `DocumentFolder` · **buildable now**
- **Sharing Target Scopes** — Granular recipient targeting: `internal_user` (specific internal system user), `internal_dept` (all members of a `core.OrgUnit`), `external_email` (named external guest identified by email), or `public_link` (anyone possessing the access token). · seen in: SharePoint Sharing Scopes, Box Shared Links, Nextcloud · priority: **table-stakes** · spine: `DocumentShare`, `accounts.User`, `core.OrgUnit` · **buildable now**
- **Granular Access Permissions** — Controls capabilities granted by the share link: `view_only` (read-only browser viewing), `comment` (read-only plus ability to view and post review comments/annotations), or `edit` (collaborative editing/co-authoring permissions). · seen in: Google Drive, Box, Dropbox, Nextcloud · priority: **table-stakes** · spine: `DocumentShare.access_level` · **buildable now**
- **Download & Print Prevention Controls** — Enforces view-only security restrictions on shares: boolean flags `allow_download` and `allow_print` prevent external recipients from saving offline copies or printing document contents directly from the web viewer. · seen in: Box Link Settings, Google Drive Viewer Settings, Egnyte View-Only Links · priority: **table-stakes** · spine: `DocumentShare.allow_download`, `DocumentShare.allow_print` · **buildable now**
- **Password Protection for Shared Links** — Allows the share creator to set an optional password (stored securely as a cryptographic hash). Anyone visiting the share URL must provide the correct password before being granted document preview or download access. · seen in: Dropbox Passwords, Box Shared Links, Nextcloud, Egnyte · priority: **table-stakes** · spine: `DocumentShare.password_hash` (Django `make_password` / `check_password`) · **buildable now**
- **Expiration Date & Usage Limit Controls** — Configures automated deactivation: `expires_at` timestamp past which the link returns HTTP 410 Gone / 404 Not Found, and optional `max_uses` (click or access count quota) deactivating the share once exhausted. Tracks cumulative `access_count` and `last_accessed_at`. · seen in: Egnyte Link Expiration, Dropbox Expiration, Box Shield Policies · priority: **table-stakes** · spine: `DocumentShare.expires_at`, `DocumentShare.max_uses`, `DocumentShare.access_count` · **buildable now**
- **Instant Revocation & Lifecycle Management** — Share creators and document administrators can instantly revoke or deactivate any active share link with a single click (`is_active=False`, `revoked_at`, `revoked_by`), cutting off all external access immediately. · seen in: SharePoint Manage Access, Egnyte Links Dashboard, Box Shared Links · priority: **table-stakes** · spine: `DocumentShare.is_active`, `DocumentShare.revoked_at` · **buildable now**
- **Centralized "Shared by Me" & "Shared with Me" Views** — Dedicated management dashboards enabling users to inspect all outbound links they have generated (with active status, expiration dates, and access counts) and browse all documents shared directly with them. · seen in: Google Drive "Shared with me", OneDrive Shared View, Egnyte Links Dashboard · priority: **table-stakes** · spine: Filtered views on `DocumentShare` and `DocumentActivity` · **buildable now**

### Real-Time Co-Authoring & Presence
- **Coauthor Session Tracking (`CoauthorSession` - `DCOA`)** — Maintains active collaborative editing sessions on documents, physical versions, or drafts, recording active participant user sessions, connection times, and heartbeat pings. · seen in: Office Online Co-Authoring, Google Docs Presence, Nextcloud Office · priority: **table-stakes** · spine: `CoauthorSession` (`DCOA`), `Document`, `DocumentDraft` · **buildable now**
- **Live Collaborator Presence & Cursor Indicators** — Tracks each coauthor's real-time presence, assigning each active participant a distinctive visual color code (`color_code`, e.g. `#3B82F6`, `#10B981`, `#F59E0B`) and tracking their active section anchor, page number, or cursor location (`cursor_position` JSON). · seen in: Google Docs Presence Avatars, Microsoft Word Live Presence, Box Notes · priority: **table-stakes** · spine: `CoauthorSession.color_code`, `CoauthorSession.cursor_position` · **buildable now**
- **Session Heartbeat & Inactivity Timeout** — Client-side periodic heartbeat (via HTMX polling / AJAX ping every 30 seconds) updates `last_heartbeat`. Sessions without a heartbeat for >90 seconds automatically transition from `active` to `idle` or `disconnected`, ensuring presence lists do not display phantom users. · seen in: Google Docs Disconnect Handlers, Nextcloud Office Session Reaper · priority: **table-stakes** · spine: `CoauthorSession.last_heartbeat`, `CoauthorSession.status` · **buildable now**
- **Concurrent Editing Coordination & Section Locks** — Displays soft visual lock indicators when another collaborator is actively typing in a specific section, paragraph, or draft block, preventing accidental overwrites while maintaining real-time collaborative flow. · seen in: Box Notes Section Locks, Office 365 Paragraph Locks · priority: **common** · spine: `CoauthorSession.is_editing`, `DocumentDraft.content` · **buildable now**
- **Real-Time Change Synchronization (WebSockets/SSE Engine)** — Low-latency bidirectional synchronization of text changes across active browsers using Server-Sent Events or WebSockets. · seen in: Google Docs OT Engine, Microsoft Office FSSHTTP/WOPI · priority: **differentiator** · spine: Integration layer (ASGI / Redis Channels) building on `CoauthorSession` · **integration/later**

### Commenting & Annotation (Relationship with 13.1 and 13.3)
- **Unified Annotation Layer Architecture** — NavERP already built `DraftCollaboration` (`DCMT`) in 13.1 for draft-stage pre-publication editing and `DocumentReviewComment` (`DREV`) in 13.3 for approval workflows. In 13.8, `DocumentReviewComment` is established as the primary annotation storage engine across all document states:
  - *Annotation Types Supported:* `inline_comment` (text thread), `highlight` (text markup), `redline` (proposed revision), `sticky_note` (pin at coordinate), and `drawing_callout` (bounding box / shape).
  - *Spatial Positioning:* Uses `page_number` and `coordinate_ref` (`x,y,w,h` or DOM text anchor) to render overlay pins directly on document previews.
  - *Discussion Threading:* Supports nested replies via `parent = ForeignKey('self')`.
  · seen in: Box Annotations, Acrobat Web Viewer, Nextcloud Comments · priority: **table-stakes** · spine: Reuses `DocumentReviewComment` (`DREV`) · **buildable now**
- **Annotation Layer Visibility & External Share Filtering** — Controls whether internal annotations are exposed to external guests: `DocumentShare.include_annotations` boolean flag determines whether comments and sticky notes are rendered in the shared link viewer or suppressed for privacy. · seen in: Box Preview Annotation Toggles, Egnyte Shared View Settings, Brava Viewer Layers · priority: **common** · spine: `DocumentShare.include_annotations`, filtering `DocumentReviewComment` · **buildable now**
- **Annotation-to-Task Conversion** — Enables any collaborator or reviewer to convert an inline comment or annotation directly into an actionable `DocumentTask` with an assignee and due date with a single click (linking `DocumentTask.review_comment` to the originating `DocumentReviewComment`). · seen in: Google Docs Action Items from Comments, Box Tasks from Annotations, Dropbox Comments-to-Tasks · priority: **common** · spine: `DocumentTask.review_comment` (`DocumentReviewComment` FK) · **buildable now**
- **Collaborator `@Mentions` in Discussions** — Parses `@username` syntax within comments and replies, automatically generating in-app activity notifications and email alert triggers for the mentioned team member. · seen in: Google Docs Mentions, Microsoft Modern Comments, Box `@mentions`, Nextcloud Talk Tags · priority: **table-stakes** · spine: Parsed into `DocumentActivity` records with `action_type="user_mentioned"` · **buildable now**

### Task Assignment & Document Review
- **Document Action Items & Tasks (`DocumentTask` - `DTSK`)** — Creates structured, trackable work assignments directly tied to a specific document or version (e.g. "Review non-compete clause", "Provide updated financial exhibits", "Sign off on technical specifications"). · seen in: Box Tasks, Google Docs Action Items, Dropbox Tasks, M-Files Assignments · priority: **table-stakes** · spine: `DocumentTask` (`DTSK`), `Document`, `DocumentVersion` · **buildable now**
- **Categorized Task Types** — Classifies assignments by operational intent: `review` (content review and feedback), `approval_signoff` (informal team sign-off prior to formal workflow), `revision_requested` (author rework needed), `fact_check` (verify figures/dates), `redline_review` (inspect suggested changes), and `general_todo`. · seen in: Box Task Types, M-Files Assignment Classes, Egnyte Review Tasks · priority: **table-stakes** · spine: `DocumentTask.task_type` · **buildable now**
- **Task Scheduling & Deadlines** — Tracks temporal parameters: `due_date` (hard deadline), `reminder_date` (scheduled reminder trigger), and `reminder_sent` (boolean tracking automated reminder dispatch). Automatically flags tasks exceeding `due_date` as `overdue`. · seen in: Box Task Deadlines, Google Tasks Due Dates, Nextcloud Deck Deadlines · priority: **table-stakes** · spine: `DocumentTask.due_date`, `DocumentTask.reminder_date`, `DocumentTask.status` · **buildable now**
- **Individual & Department Task Routing** — Flexible assignment targeting: tasks can be assigned directly to an individual (`assigned_to = ForeignKey(User)`) or dispatched to an organizational team (`assigned_org_unit = ForeignKey(core.OrgUnit)`) where any qualifying department member can claim and complete it. · seen in: M-Files User Group Assignments, SharePoint Task Routing · priority: **common** · spine: `DocumentTask.assigned_to`, `DocumentTask.assigned_org_unit` · **buildable now**
- **Task Lifecycle & Completion Notes** — Complete status progression: `pending` → `in_progress` → `completed` (or `cancelled`). On completion, records `completed_at`, `completed_by`, and optional `completion_notes` summarizing actions taken. · seen in: Box Task Resolution, Google Docs Action Item Checkboxes · priority: **table-stakes** · spine: `DocumentTask.status`, `DocumentTask.completion_notes`, `DocumentTask.completed_at` · **buildable now**
- **Document Task Dashboard & Filter Strip** — Centralized task overview displaying personal to-do lists ("Assigned to Me", "Created by Me", "Overdue Tasks"), with filterable status dropdowns, priority badges (`low`, `medium`, `high`, `urgent`), and one-click quick-completion toggles. · seen in: Google Workspace Tasks Sidebar, Box Task Center, Dropbox Tasks List · priority: **table-stakes** · spine: Function-based list view + HTMX task completion toggle · **buildable now**

### Activity Feed & Notifications
- **Document Activity Stream (`DocumentActivity` - `DACT`)** — Immutable event ledger recording collaboration events on documents: share creation, external link access, coauthor joins/exits, comment additions, task assignments, task completions, and version uploads. · seen in: Google Drive Activity Stream, Dropbox Activity Feed, Box Notification Center, Nextcloud Activity · priority: **table-stakes** · spine: `DocumentActivity` (`DACT`), `Document`, `accounts.User` · **buildable now**
- **Multi-Level Feed Presentation** — Surfaces activity in three distinct contexts:
  1. *Document Detail Activity Tab:* Chronological audit of all collaborator interactions on that specific document.
  2. *Personal Collaboration Feed:* Aggregated feed of updates on documents the user owns, is collaborating on, or has been shared with.
  3. *Unread Notification Dropdown:* Live badge counter of new mentions, shares, and task assignments directed at the user.
  · seen in: Google Drive Activity Pane, Box Activity Tab, Nextcloud Activity App · priority: **table-stakes** · spine: `DocumentActivity` queryset filtering · **buildable now**
- **Direct Recipient Mentions & Notifications** — When an action targets a specific user (`target_user = ForeignKey(User)`), the record tracks `is_read` status and `read_at` timestamp. Provides one-click "Mark All as Read" HTMX actions. · seen in: Box Web Notifications, Google Docs Notification Bell, Dropbox Notifications · priority: **table-stakes** · spine: `DocumentActivity.is_read`, `DocumentActivity.read_at` · **buildable now**
- **Notification Channel Routing** — Categorizes delivery preferences: `in_app` (displayed in navigation feed), `email_digest` (flagged for inclusion in automated periodic summary digests), or `none` (silent activity logging). · seen in: Nextcloud Activity Preferences, Box Notification Settings · priority: **common** · spine: `DocumentActivity.notification_channel` · **buildable now**

### Beyond the bullets (Enterprise collaboration & sharing capabilities)
- **External Guest Self-Identification** — For public links allowing comments or co-authoring without requiring full system login, allows guest users to enter their display name and email address, attributing their comments, coauthor presence, and activity without granting internal system credentials. · seen in: Box Shared Link Guest Comments, Google Docs Anonymous Animals / Named Guest, Dropbox File Transfer · priority: **common** · spine: `DocumentShare.allow_guest_contributions`, `CoauthorSession.guest_name` · **buildable now**
- **Share Access Analytics & Geolocation Tracking** — Captures IP address, user agent, referrer URL, and access timestamps on each public link visit, exposing detailed sharing engagement metrics to document owners. · seen in: Egnyte Link Access Reports, Box Shared Link Access Stats, Dropbox Link Tracking · priority: **differentiator** · spine: `DocumentActivity` with `action_type="link_accessed"` · **buildable now**

---

## Recommended build scope (this pass — 1–4 models)

To deliver a production-grade, commercially competitive Collaboration & Sharing engine while adhering strictly to NavERP's 1–4 model architecture and avoiding redundant tables, the recommended build scope encompasses **4 tenant-scoped models**:

```
+----------------------------------------------------------------------------------------------------+
|                                    apps/documents/models/                                          |
|                                                                                                    |
|  1. DocumentShare (DSHR)                                                                           |
|     - Links, passwords, expirations, access levels, download/print blocks, usage quotas           |
|                                                                                                    |
|  2. CoauthorSession (DCOA)                                                                         |
|     - Live collaborator presence, color codes, cursor position, heartbeats, section locks          |
|                                                                                                    |
|  3. DocumentTask (DTSK)                                                                            |
|     - Action items, review assignments, due dates, priority, completion notes, comment links      |
|                                                                                                    |
|  4. DocumentActivity (DACT)                                                                        |
|     - Collaborative event stream, mentions, target user feeds, read status, notification routing   |
+----------------------------------------------------------------------------------------------------+
```

### 1. `DocumentShare` (`DSHR`)
- **Auto-number Prefix:** `NUMBER_PREFIX = "DSHR"`
- **Table Name / Model:** `DocumentShare` in `apps/documents/models/CollaborationSharing/DocumentShares.py`
- **Inheritance:** `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`, `created_by`, `updated_by`)
- **Key Fields & Choices:**
  - `document`: ForeignKey(`documents.Document`, on_delete=CASCADE, related_name="shares")
  - `folder`: ForeignKey(`documents.DocumentFolder`, on_delete=CASCADE, null=True, blank=True, related_name="shares", help_text="Optional folder-level share")
  - `version`: ForeignKey(`documents.DocumentVersion`, on_delete=SET_NULL, null=True, blank=True, related_name="shares", help_text="Pin to specific version")
  - `share_token`: CharField(max_length=64, unique=True, db_index=True, help_text="Cryptographically secure URL token")
  - `share_type`: CharField(max_length=20, choices=[("internal_user", "Specific Internal User"), ("internal_dept", "Internal Department / OrgUnit"), ("external_email", "Named External Guest"), ("public_link", "Public Unguessable Link")], default="public_link", db_index=True)
  - `access_level`: CharField(max_length=20, choices=[("view_only", "View Only (Preview)"), ("comment", "View & Comment / Annotate"), ("edit", "Full Co-Authoring & Edit")], default="view_only", db_index=True)
  - `allow_download`: BooleanField(default=True, help_text="Permit downloading raw binary file")
  - `allow_print`: BooleanField(default=True, help_text="Permit browser printing")
  - `include_annotations`: BooleanField(default=False, help_text="Expose internal review comments/annotations to share recipients")
  - `password_hash`: CharField(max_length=128, blank=True, help_text="Hashed password for access protection")
  - `expires_at`: DateTimeField(null=True, blank=True, db_index=True, help_text="Automatic expiration timestamp")
  - `max_uses`: PositiveIntegerField(null=True, blank=True, help_text="Maximum allowed access clicks/downloads")
  - `access_count`: PositiveIntegerField(default=0, help_text="Number of times link was accessed")
  - `last_accessed_at`: DateTimeField(null=True, blank=True)
  - `shared_by`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="created_document_shares")
  - `shared_with_user`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="received_document_shares")
  - `shared_with_email`: EmailField(blank=True, help_text="Recipient email for external shares")
  - `shared_with_org_unit`: ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="document_shares")
  - `share_message`: TextField(blank=True, help_text="Optional message or instructions for recipients")
  - `is_active`: BooleanField(default=True, db_index=True)
  - `revoked_at`: DateTimeField(null=True, blank=True)
  - `revoked_by`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="revoked_document_shares")
- **Justified by Features:** Internal & External Sharing, Link-Based Sharing, Password Protection, Expiration Controls, Download/Print Prevention, Revocation.

### 2. `CoauthorSession` (`DCOA`)
- **Auto-number Prefix:** `NUMBER_PREFIX = "DCOA"`
- **Table Name / Model:** `CoauthorSession` in `apps/documents/models/CollaborationSharing/CoauthorSessions.py`
- **Inheritance:** `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`, `created_by`, `updated_by`)
- **Key Fields & Choices:**
  - `document`: ForeignKey(`documents.Document`, on_delete=CASCADE, related_name="coauthor_sessions", db_index=True)
  - `version`: ForeignKey(`documents.DocumentVersion`, on_delete=SET_NULL, null=True, blank=True, related_name="coauthor_sessions")
  - `draft`: ForeignKey(`documents.DocumentDraft`, on_delete=SET_NULL, null=True, blank=True, related_name="coauthor_sessions")
  - `session_token`: CharField(max_length=64, unique=True, db_index=True)
  - `user`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, null=True, blank=True, related_name="coauthor_sessions")
  - `guest_name`: CharField(max_length=100, blank=True, help_text="Display name for external guest collaborator")
  - `color_code`: CharField(max_length=7, default="#3B82F6", help_text="Hex color for collaborator cursor presence")
  - `cursor_position`: JSONField(default=dict, blank=True, help_text="Serialized cursor presence: page, section_anchor, offset")
  - `status`: CharField(max_length=20, choices=[("active", "Active Editing"), ("idle", "Idle / Inactive"), ("disconnected", "Disconnected / Closed")], default="active", db_index=True)
  - `is_editing`: BooleanField(default=False, help_text="True if user is actively typing / modifying section")
  - `current_section`: CharField(max_length=100, blank=True, help_text="Section anchor or paragraph currently focused")
  - `client_ip`: GenericIPAddressField(null=True, blank=True)
  - `user_agent`: CharField(max_length=255, blank=True)
  - `joined_at`: DateTimeField(auto_now_add=True)
  - `last_heartbeat`: DateTimeField(auto_now=True, db_index=True)
  - `disconnected_at`: DateTimeField(null=True, blank=True)
- **Justified by Features:** Real-Time Co-Authoring, Live Presence Indicators, Cursor Presence, Session Heartbeat, Section Locking.

### 3. `DocumentTask` (`DTSK`)
- **Auto-number Prefix:** `NUMBER_PREFIX = "DTSK"`
- **Table Name / Model:** `DocumentTask` in `apps/documents/models/CollaborationSharing/DocumentTasks.py`
- **Inheritance:** `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`, `created_by`, `updated_by`)
- **Key Fields & Choices:**
  - `document`: ForeignKey(`documents.Document`, on_delete=CASCADE, related_name="tasks", db_index=True)
  - `version`: ForeignKey(`documents.DocumentVersion`, on_delete=SET_NULL, null=True, blank=True, related_name="tasks")
  - `review_comment`: ForeignKey(`documents.DocumentReviewComment`, on_delete=SET_NULL, null=True, blank=True, related_name="action_items", help_text="Originating comment or annotation if converted to task")
  - `title`: CharField(max_length=255)
  - `description`: TextField(blank=True)
  - `task_type`: CharField(max_length=30, choices=[("review", "Document Review"), ("approval_signoff", "Informal Team Sign-Off"), ("revision_requested", "Author Revision Required"), ("fact_check", "Fact-Check & Verification"), ("redline_review", "Redline / Suggested Edit Review"), ("general_todo", "General Action Item")], default="review", db_index=True)
  - `priority`: CharField(max_length=20, choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent / Immediate")], default="medium", db_index=True)
  - `status`: CharField(max_length=20, choices=[("pending", "Pending"), ("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled"), ("overdue", "Overdue")], default="pending", db_index=True)
  - `assigned_to`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="assigned_document_tasks")
  - `assigned_by`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="created_document_tasks")
  - `assigned_org_unit`: ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="document_tasks")
  - `due_date`: DateField(null=True, blank=True, db_index=True)
  - `reminder_date`: DateField(null=True, blank=True)
  - `reminder_sent`: BooleanField(default=False)
  - `completed_at`: DateTimeField(null=True, blank=True)
  - `completed_by`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="completed_document_tasks")
  - `completion_notes`: TextField(blank=True)
- **Justified by Features:** Task Assignment & Document Review, Action Items, Due Dates, Reminder Scheduling, Comment-to-Task Linkage, Department Routing.

### 4. `DocumentActivity` (`DACT`)
- **Auto-number Prefix:** `NUMBER_PREFIX = "DACT"`
- **Table Name / Model:** `DocumentActivity` in `apps/documents/models/CollaborationSharing/DocumentActivities.py`
- **Inheritance:** `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`, `created_by`, `updated_by`)
- **Key Fields & Choices:**
  - `document`: ForeignKey(`documents.Document`, on_delete=CASCADE, related_name="collaboration_activities", db_index=True)
  - `actor`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="document_activities", help_text="Null if anonymous guest or automated trigger")
  - `guest_name`: CharField(max_length=100, blank=True, help_text="Guest display name if actor is external")
  - `target_user`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="targeted_document_activities", help_text="User mentioned or assigned for notification feed")
  - `action_type`: CharField(max_length=30, choices=[
      ("document_shared", "Document Shared"),
      ("share_revoked", "Share Link Revoked"),
      ("link_accessed", "Share Link Accessed"),
      ("file_downloaded", "File Downloaded"),
      ("coauthor_joined", "Collaborator Joined Session"),
      ("coauthor_left", "Collaborator Left Session"),
      ("comment_added", "Comment / Annotation Added"),
      ("task_assigned", "Task / Action Item Assigned"),
      ("task_completed", "Task Completed"),
      ("user_mentioned", "User Mentioned in Discussion"),
      ("version_created", "New Version Uploaded"),
    ], db_index=True)
  - `summary`: CharField(max_length=255, help_text="Human-readable event summary")
  - `details_json`: JSONField(default=dict, blank=True, help_text="Structured event metadata (old/new values, IP, snippet)")
  - `is_read`: BooleanField(default=False, db_index=True, help_text="Read state for target_user notification feed")
  - `read_at`: DateTimeField(null=True, blank=True)
  - `notification_channel`: CharField(max_length=20, choices=[("in_app", "In-App Notification"), ("email_digest", "Included in Email Digest"), ("none", "Silent Activity Log")], default="in_app")
- **Justified by Features:** Activity Feed & Notifications, Document Updates, Collaborator Mentions, "Shared with Me" Feeds, Read State Tracking.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Pre-Publication Draft Authoring & Markdown Suggestions (`13.1 Document Creation & Authoring`)** — Rich text WYSIWYG editing, template sections (`TemplateSection`), and pre-publication inline draft suggestions (`DraftCollaboration`) remain in 13.1. 13.8 handles multi-user active presence sessions (`CoauthorSession`) and general document review.
- **Physical Versioning, Check-Out Locking & Diff View (`13.2 Version Control & Revision Management`)** — Formal physical file version snapshots (`DocumentVersion`), exclusive checkout locks (`DocumentLock`), branch forks (`DocumentBranch`), and side-by-side text diffing belong to 13.2.
- **Formal Workflow Engine & Cryptographic E-Signatures (`13.3 Document Approval & Review Workflow`)** — Structured multi-step approval routing (`DocumentApprovalWorkflow`), formal approval requests (`DocumentApprovalRequest`), and legal e-signatures (`DocumentSignature`) belong to 13.3. 13.8 provides lightweight informal team action items (`DocumentTask`) and shared links.
- **Folder Repository & Storage Volumes (`13.4 Document Storage & Repository`)** — Storage volumes (`StorageVolume`), physical folder hierarchies (`DocumentFolder`), document-to-document relationships (`DocumentRelationship`), and zip batch imports (`DocumentBatchImport`) belong to 13.4.
- **Custom Metadata Schemas & OCR (`13.5 Metadata & Indexing`)** — Metadata schemas (`MetadataSchema`), document metadata values (`DocumentMetadataValue`), taxonomy controlled vocabularies (`TaxonomyTerm`), and asynchronous OCR extraction (`DocumentOcrJob`) belong to 13.5.
- **Full-Text Indexing & Search Alerts (`13.6 Search & Discovery`)** — Full-text multi-criteria querying, faceted result aggregations, saved searches (`DocumentSavedSearch`), automated search query alerts (`DocumentSearchAlert`), and search query logs (`DocumentSearchQueryLog`) belong to 13.6.
- **Enterprise RBAC Access Control, DRM & Watermarking (`13.7 Document Security & Access Control`)** — Granular role-based permissions matrix per document, user-specific dynamic watermarking, DRM encryption, and Data Loss Prevention (DLP content inspection) belong to 13.7. 13.8 focuses on link-based sharing, password-protected guest access, and collaborator workflows.
- **Records Retention Schedules & Legal Holds (`13.9 Records Management & Compliance`)** — Retention rules, file plans, litigation hold freezes, and certificates of destruction belong to 13.9.
- **Immutable Audit Trail & Regulatory Reporting (`13.10 Audit Trail & Reporting`)** — Formal compliance audit logs, forensic chain-of-custody exports, and user anomaly analytics belong to 13.10. 13.8's `DocumentActivity` is a user-facing collaborative activity feed and notification inbox, not a regulatory compliance audit vault.

---

## Deferred (later passes / integrations)

- **WebSocket / ASGI Live Co-Authoring Synchronizer** — Real-time millisecond-level character insertion synchronization using Django Channels / Redis and Operational Transformation (OT) or CRDT algorithms. The `CoauthorSession` data model fully supports tracking active sessions and cursor coordinates; client-side synchronization runs via HTMX polling and heartbeat pings in this pass.
- **Automated SMTP / Amazon SES Email Digest Dispatcher** — Periodic background cron task (e.g. daily/weekly summary emails) reading unread `DocumentActivity` records with `notification_channel="email_digest"`. The data model tracks read states, channels, and targets; automated email dispatchers are scheduled background workers.
- **WebRTC In-Browser Audio/Video Collaboration Overlay** — Live voice or video chat overlay while co-authoring a document. Commercial leaders (Nextcloud Talk, Google Meet integration) integrate dedicated communications tools for this capability.
- **Office 365 / Google Workspace WOPI Host Integration** — Dedicated WOPI protocol implementation to allow Microsoft Office Online or Google Docs web apps to edit NavERP documents directly in cloud frames. Deferred to third-party integration pass.
