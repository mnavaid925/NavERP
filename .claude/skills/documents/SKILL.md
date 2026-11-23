---
name: documents
description: Work on the Document Management System (DMS) module (Module 13 — Document Management System). As-built = 13.1 Document Creation & Authoring (DocumentTemplate[DTMPL-], TemplateSection[DSEC-], DocumentDraft[DDFT-], DraftCollaboration[DCMT-], interactive canvas, redline diff, promotion) + 13.2 Version Control & Revision Management (Document[DOC-], DocumentVersion[DVER-], DocumentLock[DLOCK-], DocumentBranch[DBRN-], side-by-side diff comparison, check-out/check-in locking, rollback, branching/merging) + 13.3 Document Approval & Review Workflow (DocumentApprovalWorkflow[DWF-], DocumentApprovalRequest[DAPR-], DocumentSignature[DSIG-], DocumentReviewComment[DREV-], visual workflow designer, 21 CFR Part 11 manifest, token verification, approval analytics dashboard) + 13.4 Document Storage & Repository (DocumentFolder[DFLD-], StorageVolume[DSTG-], DocumentRelationship[DREL-], DocumentBatchImport[DBLK-], interactive folder tree, dependency network graph, repository dashboard, streaming archive ingestion) + 13.5 Metadata & Indexing (MetadataSchema[DSCH-], DocumentMetadataValue[DMETA-], TaxonomyTerm[DTAX-], DocumentOcrJob[DOCR-], controlled vocabularies, thesauri, full-text OCR indexing, metadata dashboard) + 13.6 Search & Discovery (DocumentSavedSearch[DSVD-], DocumentSearchAlert[DALT-], DocumentSearchSynonym[DSYN-], DocumentSearchQueryLog[DQRY-], SearchHub faceted console, natural language query parsing, automated alert monitors, search telemetry & query gap analytics) + 13.7 Document Security & Access Control (DocumentAccessPermission[DPRM-], WatermarkPolicy[DWTR-], DocumentDrmPolicy[DDRM-], DlpPolicy[DDLP-], DlpIncident[DINC-], effective permissions simulator, visual watermark studio, DRM emergency kill-switch, DLP incident triage workbench, zero-download sandboxed secure viewer) + 13.8 Collaboration & Sharing (DocumentShare[DSHR-], CoauthorSession[DCOA-], DocumentTask[DTSK-], DocumentActivity[DACT-], unified CollaborationHub, guest passcode challenge, presence telemetry & heartbeats, task action tracking, in-app notification inbox). Use when the user asks to add/change/debug anything under apps/documents or templates/documents, extend the seed_documents seeder, touch documents sidebar wiring (LIVE_LINKS 13.1/13.2/13.3/13.4/13.5/13.6/13.7/13.8), or invokes /documents.
---

# Document Management System (DMS) (Module 13)

App path: `apps/documents`. Templates: `templates/documents/`. URL prefix: `/documents/`, `app_name = "documents"`.
Mirrors `NavERP.md` "## 13. Document Management System (DMS)" (Sub-modules 13.1–13.20).

**As-built: 13.1 Document Creation & Authoring + 13.2 Version Control & Revision Management + 13.3 Document Approval & Review Workflow + 13.4 Document Storage & Repository + 13.5 Metadata & Indexing + 13.6 Search & Discovery + 13.7 Document Security & Access Control + 13.8 Collaboration & Sharing.**
Build the next sub-module with `/next-module next` — see `apps/quality`/`apps/procurement` for reference package layout and the mandatory Module Creation Sequence.

---

## Overview

Module 13 provides an enterprise document repository, authoring workspace, revision control, approval orchestration, and storage repository engine:
- **13.1 Document Authoring**: Reusable master document blueprints (`DocumentTemplate`), modular clause library (`TemplateSection`), draft lifecycle tracking (`DocumentDraft`), full-screen interactive authoring canvas (`canvas.html`), critique/feedback notes (`DraftCollaboration`), and promotion to official released documents.
- **13.2 Version Control & Revision Management**: Automatic multi-scheme version numbering (`Document`, `DocumentVersion`), exclusive check-in/check-out concurrency locking (`DocumentLock`), side-by-side visual redline diff comparison (`compare.html`), parallel scenario branching and merge-back (`DocumentBranch`), and point-in-time version restoration/rollback.
- **13.3 Document Approval & Review Workflow**: Multi-stage approval pipelines (`DocumentApprovalWorkflow`), granular participant routing with sequential/parallel/first-responder rules (`DocumentApprovalRequest`), 21 CFR Part 11 cryptographic electronic signatures and certificate manifests (`DocumentSignature`), threaded critique and blocking annotations (`DocumentReviewComment`), visual stage layout designer (`designer.html`), and bottleneck analytics cockpit (`approval_dashboard.html`).
- **13.4 Document Storage & Repository**: Hierarchical taxonomic folder trees and smart virtual query filters (`DocumentFolder`), physical and cloud tiered storage targets with quota enforcement (`StorageVolume`), multi-type document dependency and reference network graphs (`DocumentRelationship`), streaming bulk zip ingestion with archive safety thresholds (`DocumentBatchImport`), and repository command center (`repository_dashboard.html`).
- **13.5 Metadata & Indexing**: Flexible enterprise metadata schema definitions with inheritance cascade policies (`MetadataSchema`), polymorphic key-value document and revision property storage (`DocumentMetadataValue`), hierarchical controlled vocabularies and multilingual thesauri (`TaxonomyTerm`), automated OCR text extraction pipeline with confidence metrics and tag extraction (`DocumentOcrJob`), and metadata analytics command center (`metadata_indexing_dashboard.html`).
- **13.6 Search & Discovery**: Multi-faceted omni-search console (`SearchHub`), natural language search filter chip parsing (`type:`, `status:`), synonym dictionary expansion (`DocumentSearchSynonym`), saved search queries and visibility scopes (`DocumentSavedSearch`), automated notification monitors (`DocumentSearchAlert`), and organization-wide search telemetry and query gap analytics (`DocumentSearchQueryLog`).
- **13.7 Document Security & Access Control**: Document-level and folder-level ACL permissions with capability matrices and precedence inheritance (`DocumentAccessPermission`), dynamic token-interpolated visual watermarks (`WatermarkPolicy`) with live interactive studio, digital rights management policies (`DocumentDrmPolicy`) with emergency kill-switch revocation, regex-based DLP inspection engine and incident triage workbench (`DlpPolicy`, `DlpIncident`), and zero-download DOM-sandboxed secure web viewer with focus-loss blur and anti-screen capture defense (`SecureViewer`).
- **13.8 Collaboration & Sharing**: Link-based and targeted document sharing (`DocumentShare`), real-time co-author presence telemetry and cursor positions (`CoauthorSession`), workflow action item assignment and completion tracking (`DocumentTask`), granular audit feeds and targeted notification inbox (`DocumentActivity`), unified multi-tab collaboration cockpit (`collaboration_hub.html`), and secure public guest preview portal (`public_share_preview.html`).

---

## Models (`apps/documents/models/`)

Shared base in `models/_base.py`:
- `TenantOwned`: multi-tenant foreign key + timestamps.
- `TenantNumbered`: auto-number generator via `core.utils.next_number` with collision retry loop.

### 13.1 DocumentAuthoring (`apps/documents/models/DocumentAuthoring/`)

- **`DocumentTemplates.py`** — `DocumentTemplate` (`NUMBER_PREFIX = "DTMPL"`):
  - `template_type`: sop, contract, policy, report, memo, letter, specification, meeting_minutes, other.
  - `category`: legal, hr, operations, finance, it, quality, sales, executive.
  - `name`, `version`, `description`, `content`, `styling_rules`, `is_active`, `is_locked`.
  - Reuses core spine: `target_org_unit` (FK `core.OrgUnit`), `owner` (FK `settings.AUTH_USER_MODEL`).

- **`TemplateSections.py`** — `TemplateSection` (`NUMBER_PREFIX = "DSEC"`):
  - `template` (FK `DocumentTemplate`, nullable for global boilerplates).
  - `section_type`: header, boilerplate, disclaimer, signature_block, table_of_contents, body_section, appendix, footer.
  - `title`, `content`, `order`, `is_locked`, `is_mandatory`.

- **`DocumentDrafts.py`** — `DocumentDraft` (`NUMBER_PREFIX = "DDFT"`):
  - `template` (FK `DocumentTemplate`, nullable).
  - `title`, `document_type`, `draft_version`, `status`, `sync_status`, `content`, `word_count`.
  - `department` (FK `core.OrgUnit`), `related_party` (FK `core.Party`), `author` (FK `settings.AUTH_USER_MODEL`).
  - `is_collaboration_locked`: gates editing and autosave mutations.
  - `promoted_document` (FK `core.Document`), `promoted_version`, `promoted_at`.

- **`DraftCollaborations.py`** — `DraftCollaboration` (`NUMBER_PREFIX = "DCMT"`):
  - `draft` (FK `DocumentDraft`).
  - `author` (FK `settings.AUTH_USER_MODEL`), `entry_type`, `comment_text`, `selected_text`, `replacement_text`.
  - `status`: open, accepted, rejected, resolved.

### 13.2 VersionControl (`apps/documents/models/VersionControl/`)

- **`Documents.py`** — `Document` (`NUMBER_PREFIX = "DOC"`):
  - `title`, `slug`, `description`, `document_type`, `classification`, `status`, `versioning_scheme`.
  - `current_version_label`, `current_version_no`.
  - `is_locked`, `locked_by` (FK `settings.AUTH_USER_MODEL`), `locked_at`.
  - `owner` (FK `settings.AUTH_USER_MODEL`), `department` (FK `core.OrgUnit`), `max_versions_retained`, `tags`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, document_type)`, `(tenant, is_locked)`.

- **`DocumentVersions.py`** — `DocumentVersion` (`NUMBER_PREFIX = "DVER"`):
  - `document` (FK `Document`, `related_name="versions"`).
  - `version_label`, `major_number`, `minor_number`, `patch_number`, `version_type` (major, minor, patch, branch_merge, rollback).
  - `file`, `file_name`, `file_size`, `file_hash` (SHA-256).
  - `extracted_text` (large text layer for search and redline diffing).
  - `is_official`, `status` (db_index=True), `author` (FK `settings.AUTH_USER_MODEL`), `branch` (FK `DocumentBranch`), `restored_from_version` (FK self).
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, document, version_label)`, indexes on `(tenant, document, is_official)`, `(tenant, status)`.

- **`DocumentLocks.py`** — `DocumentLock` (`NUMBER_PREFIX = "DLOCK"`):
  - `document` (FK `Document`), `base_version` (FK `DocumentVersion`), `locked_by` (FK `settings.AUTH_USER_MODEL`).
  - `checked_out_at`, `expires_at`, `lock_type` (exclusive, reservation), `checkout_note`, `working_copy_file`.
  - `status` (active, checked_in, discarded, force_unlocked).
  - `unlocked_at`, `unlocked_by` (FK `settings.AUTH_USER_MODEL`), `override_reason`.
  - Helper properties: `is_stale_lock`.

- **`DocumentBranches.py`** — `DocumentBranch` (`NUMBER_PREFIX = "DBRN"`):
  - `document` (FK `Document`), `name`, `description`, `base_version` (FK `DocumentVersion`).
  - `branch_type` (what_if, variant, draft_revision), `status` (active, merged, abandoned).
  - `created_by` (FK `settings.AUTH_USER_MODEL`), `merged_at`, `merged_by`, `merged_into_version`, `merge_strategy`, `merge_notes`.

### 13.3 ApprovalWorkflow (`apps/documents/models/ApprovalWorkflow/`)

- **`DocumentApprovalWorkflows.py`** — `DocumentApprovalWorkflow` (`NUMBER_PREFIX = "DWF"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `title`, `workflow_type` (sequential, parallel, conditional_rules).
  - `status` (draft, pending, approved, rejected, cancelled, bypassed), `urgency` (low, medium, high, urgent).
  - `target_turnaround_hours`, `initiator` (FK `settings.AUTH_USER_MODEL`), `department` (FK `core.OrgUnit`), `due_date`.
  - `total_stages`, `current_stage`, `requires_all_comments_resolved`, `allow_emergency_bypass`.
  - `bypassed_by` (FK `settings.AUTH_USER_MODEL`), `bypass_reason`, `definition_json`, `completed_at`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, urgency)`, `(tenant, document, status)`.

- **`DocumentApprovalRequests.py`** — `DocumentApprovalRequest` (`NUMBER_PREFIX = "DAPR"`):
  - `workflow` (FK `DocumentApprovalWorkflow`, `related_name="approval_requests"`).
  - `stage_number`, `stage_name`, `stage_type` (sequential, parallel_all, parallel_first).
  - `approver` (FK `settings.AUTH_USER_MODEL`, nullable), `approver_role` (FK `core.Role`, nullable).
  - `status` (pending, approved, rejected, delegated, escalated, bypassed).
  - `order`, `due_date`, `decided_at`, `decision_comments`.
  - `delegated_to`, `delegation_reason`, `delegated_at`.
  - `is_escalated`, `escalated_to`, `escalation_reason`, `escalated_at`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, approver, status)`, `(tenant, delegated_to, status)`, `(tenant, workflow, stage_number)`.

- **`DocumentSignatures.py`** — `DocumentSignature` (`NUMBER_PREFIX = "DSIG"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `approval_request` (FK `DocumentApprovalRequest`, nullable).
  - `signer` (FK `settings.AUTH_USER_MODEL`, nullable), `signer_name`, `signer_title`, `signer_email`.
  - `signature_type` (biometric, crypto_token, cert_x509, hmac_hash, click_to_sign).
  - `signature_meaning` (authorship, review, approval, verification, witness, receipt).
  - `signature_token` (auto UUID), `document_checksum` (SHA-256), `certificate_serial`, `signature_glyph`, `ip_address`, `user_agent`, `signed_at`, `is_valid`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `signature_token`, indexes on `(tenant, document, is_valid)`, `(tenant, signer, signed_at)`.

- **`DocumentReviewComments.py`** — `DocumentReviewComment` (`NUMBER_PREFIX = "DREV"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `workflow` (FK `DocumentApprovalWorkflow`, nullable).
  - `author` (FK `settings.AUTH_USER_MODEL`), `annotation_type` (inline_comment, highlight, redline, sticky_note, drawing_callout).
  - `page_number`, `coordinate_ref`, `selected_text`, `content`.
  - `parent` (FK self, nullable, `related_name="replies"`).
  - `is_blocking` (gates workflow approval), `status` (open, addressed, resolved, dismissed).
  - `resolved_by` (FK `settings.AUTH_USER_MODEL`), `resolved_at`, `resolution_notes`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, document, status)`, `(tenant, workflow, is_blocking)`, `(tenant, is_blocking, status)`.

### 13.4 StorageRepository (`apps/documents/models/StorageRepository/`)

- **`DocumentFolders.py`** — `DocumentFolder` (`NUMBER_PREFIX = "DFLD"`):
  - `name`, `slug`, `parent` (FK self, nullable, `related_name="children"`), `path` (materialized path).
  - `folder_type` (standard, smart_virtual, department, system, archive).
  - `classification` (public, internal, confidential, restricted), `department` (FK `core.OrgUnit`, nullable).
  - `owner` (FK `settings.AUTH_USER_MODEL`, nullable), `is_virtual`, `virtual_criteria` (JSONField).
  - `color_code`, `icon_name`, `is_active`, `is_system`.
  - Properties & Methods: `is_root` (`parent_id is None`), recursive path cascade on slug/name changes.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, parent, slug)` where parent is not null, unique `(tenant, slug)` where parent is null, indexes on `(tenant, path)`, `(tenant, is_virtual)`, `(tenant, folder_type)`.

- **`StorageVolumes.py`** — `StorageVolume` (`NUMBER_PREFIX = "DSTG"`):
  - `name`, `volume_code`, `backend_type` (local_filesystem, network_nas, s3_compatible, azure_blob, google_cloud_storage, air_gapped).
  - `base_path`, `storage_tier` (hot, warm, cold, glacier_archive).
  - `compression_algorithm` (none, gzip, zstandard), `encryption_at_rest` (none, aes_256, kms_managed).
  - `max_capacity_bytes`, `utilized_bytes`, `is_default`, `is_active`, `is_read_only`.
  - `auto_rollover_enabled`, `rollover_threshold_percent`, `rollover_volume` (FK self, nullable).
  - Invariants: single default volume per tenant (enforced atomically on save), utilized/capacity properties.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, volume_code)`, indexes on `(tenant, backend_type)`, `(tenant, storage_tier)`, `(tenant, is_default)`.

- **`DocumentRelationships.py`** — `DocumentRelationship` (`NUMBER_PREFIX = "DREL"`):
  - `source_document` (FK `Document`, `related_name="outgoing_relationships"`).
  - `target_document` (FK `Document`, `related_name="incoming_relationships"`).
  - `relationship_type` (references, supersedes, derived_from, translates, accompanies, annexes, countersigns).
  - `description`, `is_bidirectional`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Validation: rejects self-referential links (`source_document == target_document`).
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, source_document, target_document, relationship_type)`, indexes on `(tenant, source_document)`, `(tenant, target_document)`, `(tenant, relationship_type)`.

- **`DocumentBatchImports.py`** — `DocumentBatchImport` (`NUMBER_PREFIX = "DBLK"`):
  - `title`, `source_type` (zip_archive, tar_gz, s3_bucket, local_folder, metadata_csv), `import_mode` (standard, append_version, dry_run).
  - `archive_file`, `storage_volume` (FK `StorageVolume`, nullable), `target_folder` (FK `DocumentFolder`, nullable).
  - `status` (pending, extracting, ingesting, completed, failed, cancelled).
  - `total_files`, `processed_files`, `failed_files`, `total_bytes`, `processed_bytes`.
  - `error_log`, `import_summary` (JSONField), `started_at`, `completed_at`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, storage_volume)`.

### 13.5 MetadataIndexing (`apps/documents/models/MetadataIndexing/`)

- **`MetadataSchemas.py`** — `MetadataSchema` (`NUMBER_PREFIX = "DSCH"`):
  - `name`, `code` (uppercase-normalized), `description`, `target_type` (all, contract, policy, sop, financial, technical, hr, procurement).
  - `department` (FK `core.OrgUnit`, nullable), `target_folder` (FK `DocumentFolder`, nullable).
  - `fields_definition_json`: JSON array of field definitions (`key`, `label`, `data_type`, `required`).
  - `inheritance_mode` (none, folder_default, folder_strict, template).
  - `is_required`, `allow_custom_fields`, `version_number`, `is_active`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, code)`, indexes on `(tenant, target_type, is_active)`, `(tenant, name)`.

- **`TaxonomyTerms.py`** — `TaxonomyTerm` (`NUMBER_PREFIX = "DTAX"`):
  - `name`, `term_code`, `category` (general, legal, finance, compliance, technical, hr, procurement, industry).
  - `parent` (FK self, nullable, `related_name="children"`), `description`, `synonyms_json`, `external_code`.
  - `is_governed`, `is_active`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Helper properties: `active_children`, `parsed_synonyms`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, category, term_code)`, indexes on `(tenant, category, is_active)`.

- **`DocumentMetadataValues.py`** — `DocumentMetadataValue` (`NUMBER_PREFIX = "DMETA"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `schema` (FK `MetadataSchema`, nullable).
  - `field_name`, `field_label`, `data_type` (text, textarea, integer, decimal, date, datetime, boolean, dropdown, multi_select, json).
  - Polymorphic storage columns: `value_text`, `value_number`, `value_date`, `value_boolean`, `value_json`.
  - `source` (manual_entry, folder_inherited, template_inherited, ai_extracted, bulk_updated), `is_overridden`.
  - `validation_status` (valid, invalid, pending_validation), `validation_error`, `last_validated_at`, `updated_by` (FK `settings.AUTH_USER_MODEL`).
  - Helper properties: `display_value`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, document, version, field_name)`, conditional unique `(tenant, document, field_name)` when `version__isnull=True`, indexes on `(tenant, data_type)`, `(tenant, validation_status)`, `(tenant, source)`, `(tenant, document, field_name)`.

- **`DocumentOcrJobs.py`** — `DocumentOcrJob` (`NUMBER_PREFIX = "DOCR"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `status` (queued, processing, completed, failed, reviewed).
  - `ocr_engine` (internal_heuristic, tesseract_ocr, azure_document_intelligence, aws_textract, google_vision_ocr).
  - `extracted_full_text`, `confidence_score`, `page_count`, `suggested_category`, `suggested_tags_json`, `extracted_entities_json`.
  - `has_handwriting`, `has_barcode`, `processing_duration_ms`, `error_message`, `applied_to_document`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Helper properties: `parsed_tags`, `parsed_entities`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status, created_at)`, `(tenant, document, status)`, `(tenant, -created_at)`.

### 13.6 SearchDiscovery (`apps/documents/models/SearchDiscovery/`)

- **`DocumentSavedSearches.py`** — `DocumentSavedSearch` (`NUMBER_PREFIX = "DSVD"`):
  - `name`, `slug`, `description`, `query_text`, `filters_json`, `facet_filters_json`, `sort_by`, `sort_order`.
  - `visibility` (private, shared_department, public), `department` (FK `core.OrgUnit`, nullable).
  - `owner` (FK `settings.AUTH_USER_MODEL`), `is_pinned`, `is_favorite`, `is_active`.
  - `run_count`, `total_results_last_run`, `last_run_at`.
  - Helper properties: `parsed_filters`, `parsed_facet_filters`, `get_filters_dict`, `get_facet_filters_dict`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, owner, is_pinned)`, `(tenant, visibility, is_active)`.

- **`DocumentSearchAlerts.py`** — `DocumentSearchAlert` (`NUMBER_PREFIX = "DALT"`):
  - `saved_search` (FK `DocumentSavedSearch`, `related_name="alerts"`), `subscriber` (FK `settings.AUTH_USER_MODEL`).
  - `frequency` (instant, daily, weekly), `delivery_channel` (in_app, email, webhook).
  - `is_active`, `status` (active, paused, disabled).
  - `last_notified_at`, `last_checked_at`, `new_matches_count`, `last_result_ids`.
  - Helper properties: `get_last_result_ids_list`, `increment_match_count`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, saved_search, subscriber)`, indexes on `(tenant, frequency, status)`, `(tenant, subscriber, -created_at)`.

- **`DocumentSearchSynonyms.py`** — `DocumentSearchSynonym` (`NUMBER_PREFIX = "DSYN"`):
  - `term`, `synonyms` (comma-separated expansion list), `category` (general, acronym, domain, spelling).
  - `is_bidirectional`, `language`, `is_active`, `hit_count`.
  - `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Helper properties: `get_synonym_list`, `expanded_terms_list`, `get_all_terms`, `increment_hit_count`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, term, language)`, indexes on `(tenant, category, is_active)`, `(tenant, is_active, term)`.

- **`DocumentSearchQueryLogs.py`** — `DocumentSearchQueryLog` (`NUMBER_PREFIX = "DQRY"`):
  - `query_text`, `search_source` (search_hub, omni_bar, api, saved_search_run, related_search).
  - `filters_applied_json`, `results_count`, `is_zero_result`, `execution_time_ms`.
  - `user` (FK `settings.AUTH_USER_MODEL`, nullable), `session_key` (SHA-256 pseudonymized), `ip_address`, `clicked_document` (FK `Document`, nullable), `clicked_rank`.
  - Helper properties: `parsed_filters`, `parsed_filters_applied`, `get_filters_dict`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, is_zero_result, -created_at)`, `(tenant, user, -created_at)`, `(tenant, query_text)`.

### 13.7 SecurityAccessControl (`apps/documents/models/SecurityAccessControl/`)

- **`DocumentAccessPermissions.py`** — `DocumentAccessPermission` (`NUMBER_PREFIX = "DPRM"`):
  - `document` (FK `Document`, nullable), `folder` (FK `DocumentFolder`, nullable).
  - `grantee_type`: user, org_unit, role, tenant_wide.
  - `user` (FK `settings.AUTH_USER_MODEL`, nullable), `org_unit` (FK `core.OrgUnit`, nullable), `role_name`.
  - `permission_level`: viewer, commenter, editor, manager, owner, custom.
  - Granular capabilities: `can_read`, `can_write`, `can_delete`, `can_download`, `can_print`, `can_share`.
  - Temporal boundaries: `valid_from`, `valid_until`.
  - Inheritance: `is_inherited`, `inherited_from_folder` (FK `DocumentFolder`, nullable).
  - Telemetry & status: `is_active`, `access_count`, `last_accessed_at`, `notes`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Helper properties: `is_currently_valid`, `grantee_display`, `grantee_badge`, `permission_badge`.
  - Constraints & Indexes: unique `(tenant, number)`, composite indexes on `(tenant, document, is_active)`, `(tenant, user, is_active)`, `(tenant, folder, is_active)`, `(tenant, -created_at)`.

- **`WatermarkPolicies.py`** — `WatermarkPolicy` (`NUMBER_PREFIX = "DWTR"`):
  - `name`, `slug`, `description`, `classification` (all, public, internal, confidential, restricted), `document_type`, `department` (FK `core.OrgUnit`, nullable), `apply_to_all`.
  - Overlay styling: `watermark_text` (dynamic token interpolation template), `secondary_text`, `position` (diagonal, horizontal, header_footer, tiled_grid), `rotation_angle`, `opacity_percent` (1-100), `font_size`, `font_color`, `priority`.
  - Classification banner: `show_classification_banner`, `banner_position` (top, bottom, both).
  - Enforcement gates: `enforce_on_view`, `enforce_on_download`, `enforce_on_print`.
  - Helper methods: `render_watermark(user, document, ip_address)` with dynamic token interpolation (`{{user_name}}`, `{{user_email}}`, `{{classification}}`, `{{document_number}}`, `{{tenant_name}}`, `{{ip_address}}`, `{{timestamp}}`), `classification_badge`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, slug)`, indexes on `(tenant, is_active, priority)`, `(tenant, classification)`.

- **`DocumentDrmPolicies.py`** — `DocumentDrmPolicy` (`NUMBER_PREFIX = "DDRM"`):
  - `name`, `slug`, `description`, `classification`, `target_document` (FK `Document`, nullable), `target_folder` (FK `DocumentFolder`, nullable).
  - Exfiltration defenses: `allow_download`, `allow_print`, `allow_copy_paste`, `screen_shield_enabled`, `secure_viewer_required`, `require_watermark`.
  - Perimeter parameters: `expiry_days`, `max_offline_hours`, `ip_allowlist`, `geo_fencing_countries`, `encryption_standard` (aes_128_gcm, aes_256_gcm, chacha20_poly1305).
  - Emergency Kill-Switch: `is_revoked`, `revoked_at`, `revoked_by` (FK `settings.AUTH_USER_MODEL`, nullable), `revocation_reason`, `revoke(user, reason)`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, slug)`, indexes on `(tenant, is_active, is_revoked)`, `(tenant, target_document, is_active, is_revoked)`.

- **`DlpPolicies.py`** — `DlpPolicy` (`NUMBER_PREFIX = "DDLP"`):
  - `name`, `slug`, `description`, `rule_type` (credit_card_pci, us_ssn, api_keys_secrets, sensitive_keywords, custom_regex).
  - Engine parameters: `built_in_pattern`, `custom_regex`, `sensitive_keywords` (JSONField), `match_threshold`, `action` (warn_user, redact_preview, quarantine, block_and_alert).
  - Target scoping: `apply_to_all_types`, `target_document_types` (JSONField), `target_classifications` (JSONField), `severity` (low, medium, high, critical).
  - Telemetry & alerting: `notify_security_officer`, `notification_email`, `incident_count`, `last_triggered_at`, `is_active`, `created_by` (FK `settings.AUTH_USER_MODEL`).
  - Core inspection engine: `inspect_text(text, filename)` detecting built-in patterns, sensitive keywords, and custom regex with redaction snippet masking.
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, slug)`, indexes on `(tenant, rule_type, is_active)`, `(tenant, severity, is_active)`.

- **`DlpIncidents.py`** — `DlpIncident` (`NUMBER_PREFIX = "DINC"`):
  - `policy` (FK `DlpPolicy`, `related_name="incidents"`), `document` (FK `Document`, nullable), `version` (FK `DocumentVersion`, nullable).
  - `triggered_by` (FK `settings.AUTH_USER_MODEL`, nullable), `incident_type`, `action_taken`, `severity`.
  - Evidence: `snippet_masked`, `context_notes`, `client_ip`.
  - Resolution triage: `resolution_status` (open, under_investigation, resolved_justified, false_positive, dismissed), `resolved_by` (FK `settings.AUTH_USER_MODEL`, nullable), `resolved_at`, `resolution_notes`, `resolve(status, user, notes)`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, policy, resolution_status)`, `(tenant, resolution_status, severity)`, `(tenant, document, -created_at)`, `(tenant, -created_at)`.

### 13.8 CollaborationSharing (`apps/documents/models/CollaborationSharing/`)

- **`DocumentShares.py`** — `DocumentShare` (`NUMBER_PREFIX = "DSHR"`):
  - `document` (FK `Document`), `folder` (FK `DocumentFolder`, nullable), `version` (FK `DocumentVersion`, nullable).
  - `share_type`: internal_user, internal_dept, external_email, public_link.
  - `access_level`: view, comment, edit, download.
  - `shared_by` (FK `settings.AUTH_USER_MODEL`), `shared_with_user` (FK `settings.AUTH_USER_MODEL`, `related_name="dms_received_document_shares"`), `shared_with_email`, `shared_with_org_unit` (FK `core.OrgUnit`).
  - `share_token` (cryptographic URL token), `require_password`, `password_hash` (PBKDF2/Argon2), `allow_download`.
  - `expires_at`, `max_uses`, `access_count`, `last_accessed_at`, `is_active`, `revoked_at`, `revoked_by`.
  - Properties & Helpers: `is_expired`, `is_exhausted`, `is_usable`, `status_label`, `status_badge`, `set_password()`, `check_password()`, `record_access()`, `revoke()`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `share_token`, indexes on `(tenant, is_active)`, `(tenant, document)`, `(tenant, shared_by)`, `(tenant, shared_with_user)`.

- **`CoauthorSessions.py`** — `CoauthorSession` (`NUMBER_PREFIX = "DCOA"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `draft` (FK `DocumentDraft`, nullable).
  - `user` (FK `settings.AUTH_USER_MODEL`, nullable), `guest_name`, `client_id`, `session_token`.
  - `status`: active, idle, disconnected.
  - `color_code` (Hex color with RegexValidator `^#[0-9A-Fa-f]{6}$`), `cursor_position_json`, `current_section_anchor`, `is_typing`.
  - `client_ip`, `user_agent`, `joined_at`, `last_heartbeat`, `disconnected_at`.
  - Properties & Helpers: `display_name`, `is_stale`, `is_timed_out`, `status_badge`, `touch_heartbeat()`, `mark_disconnected()`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, document, status)`, `(tenant, user)`, `(tenant, last_heartbeat)`, `(tenant, status)`.

- **`DocumentTasks.py`** — `DocumentTask` (`NUMBER_PREFIX = "DTSK"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `review_comment` (FK `DocumentReviewComment`, nullable).
  - `title`, `description`, `task_type` (review, revise, approve, sign, translate, verify, other), `priority` (low, medium, high, urgent).
  - `status`: pending, in_progress, completed, cancelled, overdue.
  - `assigned_to` (FK `settings.AUTH_USER_MODEL`, nullable), `assigned_org_unit` (FK `core.OrgUnit`, nullable), `assigned_by` (FK `settings.AUTH_USER_MODEL`).
  - `due_date`, `reminder_date`, `reminder_sent`, `completed_at`, `completed_by`, `completion_notes`.
  - Properties & Helpers: `is_overdue`, `effective_status`, `priority_badge`, `status_badge`, `complete()`, `reopen()`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, assigned_to, status)`, `(tenant, document)`, `(tenant, due_date)`.

- **`DocumentActivities.py`** — `DocumentActivity` (`NUMBER_PREFIX = "DACT"`):
  - `document` (FK `Document`), `share` (FK `DocumentShare`, nullable), `task` (FK `DocumentTask`, nullable), `session` (FK `CoauthorSession`, nullable).
  - `actor` (FK `settings.AUTH_USER_MODEL`, nullable), `guest_name`, `target_user` (FK `settings.AUTH_USER_MODEL`, nullable).
  - `action_type`: document_shared, share_revoked, link_accessed, file_downloaded, coauthor_joined, coauthor_left, coauthor_edit, task_assigned, task_completed, task_reopened, comment_added.
  - `title`, `description`, `details_json`, `notification_channel` (in_app, email_digest, none), `is_read`, `read_at`.
  - Properties & Helpers: `actor_display_name`, `badge_class`, `mark_as_read()`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, document, -created_at)`, `(tenant, target_user, is_read)`, `(tenant, created_at)`.



---

## URLs & Routes (`apps/documents/urls/`)

Registered under namespace `documents:`:

### 13.1 Authoring Routes
- `/documents/templates/`: `template_list`, `template_create`, `<pk>/`, `<pk>/edit/`, `<pk>/delete/`, `<pk>/instantiate/`
- `/documents/sections/`: `template_section_list`, `template_section_create`, `<pk>/`, `<pk>/edit/`, `<pk>/delete/`
- `/documents/drafts/`: `draft_list`, `draft_create`, `<pk>/`, `<pk>/edit/`, `<pk>/delete/`, `<pk>/canvas/`, `<pk>/autosave/`, `<pk>/compare/`, `<pk>/conflicts/`, `<pk>/promote/`
- `/documents/collaborations/`: `collaboration_list`, `<pk>/`, `<draft_pk>/collaborate/`, `<pk>/edit/`, `<pk>/delete/`, `<pk>/resolve/`

### 13.2 Version Control Routes
- `/documents/`: `document_list` (main document repository)
- `/documents/create/`: `document_create`
- `/documents/<pk>/`: `document_detail`
- `/documents/<pk>/edit/`: `document_edit`
- `/documents/<pk>/delete/`: `document_delete` (POST-only, `@tenant_admin_required`)
- `/documents/versions/`: `document_version_list`
- `/documents/versions/create/`: `document_version_create`
- `/documents/versions/<pk>/`: `document_version_detail`
- `/documents/versions/<pk>/edit/`: `document_version_edit`
- `/documents/versions/<pk>/delete/`: `document_version_delete` (POST-only, `@tenant_admin_required`)
- `/documents/versions/compare/`: `document_version_compare` (visual redline diff)
- `/documents/versions/<pk>/rollback/`: `document_version_rollback` (POST-only, atomic restoration)
- `/documents/locks/`: `document_lock_list`
- `/documents/locks/<pk>/`: `document_lock_detail`
- `/documents/documents/<doc_pk>/checkout/`: `document_checkout` (row-level lock with `select_for_update`)
- `/documents/documents/<doc_pk>/checkin/`: `document_checkin` (resolves lock, creates next version)
- `/documents/locks/<pk>/force-unlock/`: `document_force_unlock` (POST-only, `@tenant_admin_required`)
- `/documents/branches/`: `document_branch_list`
- `/documents/branches/create/`: `document_branch_create`
- `/documents/branches/<pk>/`: `document_branch_detail`
- `/documents/branches/<pk>/edit/`: `document_branch_edit`
- `/documents/branches/<pk>/delete/`: `document_branch_delete` (POST-only, `@tenant_admin_required`)
- `/documents/branches/<pk>/merge/`: `document_branch_merge` (merges branch revisions into mainline)
- `/documents/branches/<pk>/abandon/`: `document_branch_abandon` (closes active branch)

### 13.3 Approval & Review Workflow Routes
- `/documents/workflows/`: `workflow_list`
- `/documents/workflows/create/`: `workflow_create`
- `/documents/workflows/<pk>/`: `workflow_detail`
- `/documents/workflows/<pk>/edit/`: `workflow_edit`
- `/documents/workflows/<pk>/delete/`: `workflow_delete` (POST-only, draft-only)
- `/documents/workflows/<pk>/designer/`: `workflow_designer` (interactive stage sequence builder)
- `/documents/workflows/<pk>/submit/`: `workflow_submit` (POST-only, initiates pending stage 1)
- `/documents/workflows/<pk>/bypass/`: `workflow_bypass` (POST-only, requires admin or initiator)
- `/documents/workflows/<pk>/cancel/`: `workflow_cancel` (POST-only)
- `/documents/approval-requests/`: `approval_request_list`
- `/documents/approval-requests/create/`: `approval_request_create`
- `/documents/approval-requests/<pk>/`: `approval_request_detail`
- `/documents/approval-requests/<pk>/edit/`: `approval_request_edit`
- `/documents/approval-requests/<pk>/delete/`: `approval_request_delete` (POST-only, pending in draft)
- `/documents/approval-requests/<pk>/decide/`: `approval_request_decide` (POST-only, atomic, checks blocking comments)
- `/documents/approval-requests/<pk>/delegate/`: `approval_request_delegate` (POST-only)
- `/documents/approval-requests/<pk>/escalate/`: `approval_request_escalate` (POST-only)
- `/documents/signatures/`: `signature_list`
- `/documents/signatures/create/`: `signature_create`
- `/documents/signatures/verify/`: `signature_verify` (lookup form)
- `/documents/signatures/verify/<str:token>/`: `signature_verify` (token verification view)
- `/documents/signatures/<int:pk>/`: `signature_detail`
- `/documents/signatures/<int:pk>/edit/`: `signature_edit` (locks immutable fields)
- `/documents/signatures/<int:pk>/delete/`: `signature_delete` (POST-only)
- `/documents/signatures/<int:pk>/manifest/`: `signature_manifest` (21 CFR Part 11 printable manifest)
- `/documents/review-comments/`: `review_comment_list`
- `/documents/review-comments/create/`: `review_comment_create`
- `/documents/review-comments/<int:pk>/`: `review_comment_detail`
- `/documents/review-comments/<int:pk>/edit/`: `review_comment_edit` (author or admin)
- `/documents/review-comments/<int:pk>/delete/`: `review_comment_delete` (POST-only, author or admin)
- `/documents/review-comments/<int:pk>/resolve/`: `review_comment_resolve` (POST-only)
- `/documents/review-comments/<int:pk>/reply/`: `review_comment_reply` (POST-only)
- `/documents/dashboard/`: `approval_dashboard` (analytics command center & bottleneck KPIs)

### 13.4 Storage Repository Routes
- `/documents/storage/dashboard/`: `repository_dashboard` (KPI command center & storage utilization overview)
- `/documents/storage/folders/`: `folder_list`, `folder_create`
- `/documents/storage/folders/tree/`: `folder_tree` (adjacency-list JSON & DOM taxonomy tree)
- `/documents/storage/folders/<int:pk>/`: `folder_detail`, `folder_edit`, `folder_delete` (POST-only)
- `/documents/storage/volumes/`: `storage_volume_list`, `storage_volume_create` (`@tenant_admin_required`)
- `/documents/storage/volumes/<int:pk>/`: `storage_volume_detail`, `storage_volume_edit` (`@tenant_admin_required`), `storage_volume_delete` (POST-only, `@tenant_admin_required`)
- `/documents/storage/relationships/`: `relationship_list`, `relationship_create`
- `/documents/storage/relationships/graph/`: `relationship_graph` (network topology visualization & nodes/edges JSON)
- `/documents/storage/relationships/<int:pk>/`: `relationship_detail`, `relationship_edit`, `relationship_delete` (POST-only)
- `/documents/storage/batch-imports/`: `batch_import_list`, `batch_import_create`
- `/documents/storage/batch-imports/<int:pk>/`: `batch_import_detail`, `batch_import_edit`, `batch_import_delete` (POST-only)
- `/documents/storage/batch-imports/<int:pk>/process/`: `batch_import_process` (POST-only streaming extraction & document ingestion)

### 13.5 Metadata & Indexing Routes
- `/documents/metadata/`: `metadata_indexing_dashboard` (KPI command center, schemas count, OCR metrics)
- `/documents/schemas/`: `metadata_schema_list`, `metadata_schema_create`
- `/documents/schemas/<int:pk>/`: `metadata_schema_detail`, `metadata_schema_edit`, `metadata_schema_delete` (POST-only, `@tenant_admin_required`)
- `/documents/taxonomies/`: `taxonomy_term_list`, `taxonomy_term_create`
- `/documents/taxonomies/tree/`: `taxonomy_term_tree` (hierarchical taxonomy tree view)
- `/documents/taxonomies/<int:pk>/`: `taxonomy_term_detail`, `taxonomy_term_edit`, `taxonomy_term_delete` (POST-only, guarded against child cascade)
- `/documents/metadata-values/`: `metadata_value_list`, `metadata_value_create`
- `/documents/metadata-values/<int:pk>/`: `metadata_value_detail`, `metadata_value_edit`, `metadata_value_delete` (POST-only)
- `/documents/metadata-values/<int:pk>/validate/`: `metadata_value_validate` (POST-only schema conformance check)
- `/documents/ocr-jobs/`: `document_ocr_job_list`, `document_ocr_job_create`
- `/documents/ocr-jobs/<int:pk>/`: `document_ocr_job_detail`
- `/documents/ocr-jobs/<int:pk>/viewer/`: `document_ocr_job_viewer` (split-screen OCR extraction inspector)
- `/documents/ocr-jobs/<int:pk>/process/`: `document_ocr_job_process` (POST-only extraction engine pipeline)
- `/documents/ocr-jobs/<int:pk>/apply/`: `document_ocr_job_apply` (POST-only commit OCR text & tags to document)
- `/documents/ocr-jobs/<int:pk>/delete/`: `document_ocr_job_delete` (POST-only)

### 13.6 Search & Discovery Routes
- `/documents/search/`: `search_hub` (faceted omni-search console)
- `/documents/search/export/`: `search_export_csv` (CSV search results export)
- `/documents/search/click/`: `search_click_track` (search click rank telemetry tracker)
- `/documents/saved-searches/`: `document_saved_search_list`, `document_saved_search_create`
- `/documents/saved-searches/<int:pk>/`: `document_saved_search_detail`, `document_saved_search_edit`, `document_saved_search_delete` (POST-only)
- `/documents/saved-searches/<int:pk>/run/`: `document_saved_search_run` (executes query, increments counters, redirects)
- `/documents/saved-searches/<int:pk>/toggle-pin/`: `document_saved_search_toggle_pin` (POST-only)
- `/documents/search-alerts/`: `document_search_alert_list`, `document_search_alert_create`
- `/documents/search-alerts/<int:pk>/`: `document_search_alert_detail`, `document_search_alert_edit`, `document_search_alert_delete` (POST-only)
- `/documents/search-alerts/<int:pk>/toggle-active/`: `document_search_alert_toggle_active` (POST-only)
- `/documents/search-alerts/<int:pk>/run-check/`: `document_search_alert_run_check` (POST-only delta check)
- `/documents/search-synonyms/`: `document_search_synonym_list`, `document_search_synonym_create`
- `/documents/search-synonyms/<int:pk>/`: `document_search_synonym_detail`, `document_search_synonym_edit`, `document_search_synonym_delete` (POST-only)
- `/documents/search-synonyms/<int:pk>/toggle-active/`: `document_search_synonym_toggle_active` (POST-only)
- `/documents/search-query-logs/`: `document_search_query_log_list` (`@tenant_admin_required`), `<int:pk>/` (`@tenant_admin_required`), `<int:pk>/delete/` (POST-only, `@tenant_admin_required`)
- `/documents/search-analytics/`: `document_search_analytics` (`@tenant_admin_required`)

### 13.7 Document Security & Access Control Routes
- `/documents/access-permissions/`: `permission_list`
- `/documents/access-permissions/create/`: `permission_create` (`@tenant_admin_required`)
- `/documents/access-permissions/simulate/`: `permission_simulate` (effective capability matrix calculation)
- `/documents/access-permissions/<int:pk>/`: `permission_detail`
- `/documents/access-permissions/<int:pk>/edit/`: `permission_edit` (`@tenant_admin_required`)
- `/documents/access-permissions/<int:pk>/delete/`: `permission_delete` (POST-only, `@tenant_admin_required`)
- `/documents/watermark-policies/`: `watermark_list`
- `/documents/watermark-policies/create/`: `watermark_create` (`@tenant_admin_required`)
- `/documents/watermark-policies/preview/`: `watermark_preview` (interactive visual canvas studio)
- `/documents/watermark-policies/<int:pk>/`: `watermark_detail`
- `/documents/watermark-policies/<int:pk>/edit/`: `watermark_edit` (`@tenant_admin_required`)
- `/documents/watermark-policies/<int:pk>/delete/`: `watermark_delete` (POST-only, `@tenant_admin_required`)
- `/documents/drm-policies/`: `drm_policy_list`
- `/documents/drm-policies/create/`: `drm_policy_create` (`@tenant_admin_required`)
- `/documents/drm-policies/<int:pk>/`: `drm_policy_detail`
- `/documents/drm-policies/<int:pk>/edit/`: `drm_policy_edit` (`@tenant_admin_required`)
- `/documents/drm-policies/<int:pk>/delete/`: `drm_policy_delete` (POST-only, `@tenant_admin_required`)
- `/documents/drm-policies/<int:pk>/kill-switch/`: `drm_kill_switch` (POST-only emergency revocation, `@tenant_admin_required`)
- `/documents/dlp-policies/`: `dlp_policy_list`
- `/documents/dlp-policies/create/`: `dlp_policy_create` (`@tenant_admin_required`)
- `/documents/dlp-policies/<int:pk>/`: `dlp_policy_detail`
- `/documents/dlp-policies/<int:pk>/edit/`: `dlp_policy_edit` (`@tenant_admin_required`)
- `/documents/dlp-policies/<int:pk>/delete/`: `dlp_policy_delete` (POST-only, `@tenant_admin_required`)
- `/documents/dlp-incidents/`: `dlp_incident_list`
- `/documents/dlp-incidents/<int:pk>/`: `dlp_incident_detail`
- `/documents/dlp-incidents/<int:pk>/resolve/`: `dlp_incident_resolve` (POST-only triage, `@tenant_admin_required`)
- `/documents/secure-viewer/`: `secure_viewer` (sandboxed zero-download console with forensic watermark & screen blur)
- `/documents/secure-viewer/<int:pk>/`: `secure_viewer_doc`
- `/documents/secure-viewer/log-event/`: `secure_viewer_log` (AJAX telemetry logger)

### 13.8 Collaboration & Sharing Routes
- `/documents/collaboration/`: `collaboration_hub` (unified multi-tab cockpit with tabs: shared_with_me, shared_by_me, my_tasks, activity)
- `/documents/shares/`: `document_share_list`, `document_share_create`
- `/documents/shares/<int:pk>/`: `document_share_detail`, `document_share_edit`, `document_share_delete` (POST-only)
- `/documents/shares/<int:pk>/revoke/`: `document_share_revoke` (POST-only)
- `/documents/p/<str:share_token>/`: `public_share_preview` (guest portal with passcode challenge)
- `/documents/p/<str:share_token>/download/`: `public_share_download` (gated attachment download)
- `/documents/sessions/`: `coauthor_session_list`, `coauthor_session_create`
- `/documents/sessions/<int:pk>/`: `coauthor_session_detail`, `coauthor_session_edit`, `coauthor_session_delete` (POST-only)
- `/documents/sessions/<int:pk>/heartbeat/`: `coauthor_session_heartbeat` (AJAX POST heartbeat & presence API)
- `/documents/tasks/`: `document_task_list`, `document_task_create`
- `/documents/tasks/<int:pk>/`: `document_task_detail`, `document_task_edit`, `document_task_delete` (POST-only)
- `/documents/tasks/<int:pk>/toggle-complete/`: `document_task_toggle_complete` (POST-only bidirectional toggle)
- `/documents/activities/`: `document_activity_list`
- `/documents/activities/mark-all-read/`: `document_activity_mark_all_read` (POST-only bulk mark read)
- `/documents/activities/<int:pk>/`: `document_activity_detail` (auto-marks read)
- `/documents/activities/<int:pk>/mark-read/`: `document_activity_mark_read` (POST-only)

---

## Templates

Located in:
- `templates/documents/document_authoring/` (13.1 templates: templates, sections, drafts, collaborations)
- `templates/documents/version_control/` (13.2 templates):
  - `document/`: `list.html`, `detail.html`, `form.html`
  - `document_version/`: `list.html`, `detail.html`, `form.html`, `compare.html`
  - `document_lock/`: `list.html`, `detail.html`, `checkout_modal.html`, `checkin_modal.html`, `force_unlock.html`
  - `document_branch/`: `list.html`, `detail.html`, `form.html`, `merge_modal.html`
- `templates/documents/approval_workflow/` (13.3 templates):
  - `document_approval_workflow/`: `list.html`, `detail.html`, `form.html`, `designer.html`
  - `document_approval_request/`: `list.html`, `detail.html`, `form.html`
  - `document_signature/`: `list.html`, `detail.html`, `form.html`, `manifest.html`, `verify.html`
  - `document_review_comment/`: `list.html`, `detail.html`, `form.html`
  - `approval_dashboard.html`: Command center & bottleneck analytics cockpit
- `templates/documents/storage_repository/` (13.4 templates):
  - `repository_dashboard.html`: Command center, storage capacity gauges, recent batch ingestions
  - `document_folder/`: `list.html`, `detail.html`, `form.html`, `tree.html`
  - `storage_volume/`: `list.html`, `detail.html`, `form.html`
  - `document_relationship/`: `list.html`, `detail.html`, `form.html`, `graph.html`
  - `document_batch_import/`: `list.html`, `detail.html`, `form.html`
- `templates/documents/metadata_indexing/` (13.5 templates):
  - `metadata_indexing_dashboard.html`: Command center, schema distribution, OCR pipeline metrics
  - `metadata_schema/`: `list.html`, `detail.html`, `form.html`
  - `taxonomy_term/`: `list.html`, `detail.html`, `form.html`, `tree.html`
  - `document_metadata_value/`: `list.html`, `detail.html`, `form.html`
  - `document_ocr_job/`: `list.html`, `detail.html`, `form.html`, `extract_viewer.html`
- `templates/documents/search_discovery/` (13.6 templates):
  - `search_hub.html`: Multi-faceted discovery console, natural language chips, real-time filters
  - `document_saved_search/`: `list.html`, `detail.html`, `form.html`
  - `document_search_alert/`: `list.html`, `detail.html`, `form.html`
  - `document_search_synonym/`: `list.html`, `detail.html`, `form.html`
  - `document_search_query_log/`: `list.html`, `detail.html`, `analytics.html`
- `templates/documents/security_access_control/` (13.7 templates):
  - `document_access_permission/`: `list.html`, `detail.html`, `form.html`, `simulate.html` (effective capabilities matrix calculator)
  - `watermark_policy/`: `list.html`, `detail.html`, `form.html`, `preview.html` (interactive real-time visual canvas studio)
  - `document_drm_policy/`: `list.html`, `detail.html`, `form.html` (with emergency kill-switch confirmation modal)
  - `dlp_policy/`: `list.html`, `detail.html`, `form.html` (with violation incident feed)
  - `dlp_incident/`: `list.html`, `detail.html` (with triage resolution workbench)
  - `secure_viewer.html`: Sandboxed zero-download viewer console, client-side focus-loss blur shield (`screen_shield_overlay`), context-menu blocking, and forensic dynamic watermark overlay
- `templates/documents/collaboration_sharing/` (13.8 templates):
  - `collaboration_hub.html`: Unified multi-tab collaboration workspace with live coauthor presence banner and KPI stats
  - `document_share/`: `list.html`, `detail.html`, `form.html`
  - `coauthor_session/`: `list.html`, `detail.html`, `form.html`
  - `document_task/`: `list.html`, `detail.html`, `form.html`
  - `document_activity/`: `list.html`, `detail.html`, `form.html`
  - `public_share_preview.html`: Clean guest portal (`base_auth.html`), passcode challenge form, gated document preview & download


---

## Seeder (`apps/documents/management/commands/seed_documents.py`)

Run via:
```powershell
venv\Scripts\python.exe manage.py seed_documents
```
Supports `--flush` option to reset module data cleanly. Demo data seeds:
1. Master Document Templates across Acme, Globex, etc. (SOP, NDA, Policy memo).
2. Template Sections (QA clause, cGMP standards, disclaimers).
3. Document Drafts and Collaborations.
4. Core Documents (SOP Master, Mutual NDA, Cloud Infrastructure Spec).
5. Document Versions (Semantic 1.0.0->1.1.0->1.2.0, Major.Minor 1.0->2.0).
6. Active and Resolved Document Locks.
7. Document Branches (What-if scenario spike, merged variants).
8. Multi-Stage Document Approval Workflows (Draft, Pending Stage 1/2, Approved, Emergency Bypassed).
9. Granular Approval Requests (Sequential, Parallel All, Parallel First Responder, Delegated, Escalated).
10. Electronic Signatures (Biometric seal, X.509 cryptographic thumbprint, SHA-256 checksum, UUID verification token).
11. Collaborative Review Comments (Page annotations, highlighted passages, blocking critique, threaded replies).
12. Enterprise Folder Taxonomies (Corporate policies, SOP master trees, virtual query filters).
13. Tiered Storage Volumes (NVMe SSD hot tier, S3 object storage warm tier, Deep Glacier cold archive).
14. Document Relationships (Cross-document citations, superseding links, annex attachments).
15. Batch Import Ingestion Jobs (Completed bulk zip packages, processing audit logs).
16. Enterprise Metadata Schemas (NDA schema, Vendor Contract spec, Quality ISO manual schema).
17. Controlled Taxonomies & Thesauri (Legal & Contract terms, Regulatory Compliance codes, Financial terms, Industry classifications).
18. Document Metadata Values (Heterogeneous decimal amounts, dates, booleans, and JSON structured payloads).
19. Document OCR Extraction Jobs (Completed, processing, and queued OCR jobs with confidence scores, full text layers, and entity tags).
20. Saved Searches (Public policy searches, private user filters, pinned department searches).
21. Search Alerts (Daily, weekly, and instant email/in-app alert subscriptions).
22. Search Synonyms (Bidirectional terms, domain expansions, acronym mappings).
23. Search Query Logs (Telemetry logs, zero-result telemetry, click ranks).
24. Document Access Permissions (Tenant-wide public read permissions, Departmental compliance editor permissions, Individual user restricted owner grants).
25. Dynamic Watermark Policies (Confidential diagonal overlay policy, Internal footer policy, Restricted top/bottom banner policy).
26. Document DRM Policies (Executive NDA restricted DRM shield with screen-shield blur and print blocking, Revoked leak test policy with kill-switch engaged).
27. Data Loss Prevention Policies (PCI-DSS credit card shield with block-and-alert, PII social security number detector, API secret key detector).
28. DLP Incidents & Triage Log (Open critical PCI violation incident, Resolved false positive incident with security officer triage notes).
29. Document Shares (Internal user share with view access, Department share with download access, External email share, Public guest link with Argon2/PBKDF2 passcode challenge).
30. Co-Authoring Sessions (Active session with presence color #3B82F6 and JSON cursor position, Idle session, Disconnected session with telemetry).
31. Document Review & Action Tasks (Review clause compliance, Sign authorization, Revise security section, Translate SOP into French with due dates and priority badges).
32. Collaborative Document Activities (Document shared, link accessed, guest download, coauthor joined, task assigned, task completed audit event stream).

---

## Sidebar Wiring (`apps/core/navigation.py`)

```python
LIVE_LINKS["13.2"] = {
    "Automatic Version Numbering": "documents:document_version_list",
    "Check-in / Check-out Mechanism": "documents:document_lock_list",
    "Version Comparison & Diff View": "documents:document_version_compare",
    "Branching & Parallel Versions": "documents:document_branch_list",
    "Version History & Rollback": "documents:document_version_list",
    "Documents": "documents:document_list",
}
LIVE_LINKS["13.3"] = {
    "Approval Command Center": "documents:approval_dashboard",
    "Approval Workflows": "documents:workflow_list",
    "Approval Requests": "documents:approval_request_list",
    "Electronic Signatures": "documents:signature_list",
    "Review Comments": "documents:review_comment_list",
}
LIVE_LINKS["13.4"] = {
    "Folder Hierarchy & Taxonomy": "documents:folder_list",
    "Cloud & On-Premises Deployment": "documents:storage_volume_list",
    "Storage Tiering & Optimization": "documents:storage_volume_list?tier=hot",
    "Document Linking & Relationships": "documents:relationship_list",
    "Bulk Upload & Import": "documents:batch_import_list",
}
LIVE_LINKS["13.5"] = {
    "Metadata Command Center": "documents:metadata_indexing_dashboard",
    "Document Metadata Schemas": "documents:metadata_schema_list",
    "Taxonomy & Controlled Vocabularies": "documents:taxonomy_term_list",
    "Taxonomy Hierarchy Tree": "documents:taxonomy_term_tree",
    "Document Metadata Values": "documents:metadata_value_list",
    "Full-Text OCR Extraction Jobs": "documents:document_ocr_job_list",
}
LIVE_LINKS["13.6"] = {
    "Advanced Search & Filters": "documents:search_hub",
    "Faceted Search Navigation": "documents:search_hub",
    "Saved Searches & Alerts": "documents:document_saved_search_list",
    "Natural Language Query & AI Search": "documents:search_hub",
    "Search Analytics & Query Optimization": "documents:document_search_analytics",
    "Search Alerts": "documents:document_search_alert_list",
    "Search Synonyms": "documents:document_search_synonym_list",
    "Search Query Logs": "documents:document_search_query_log_list",
}
LIVE_LINKS["13.7"] = {
    "Document-Level Permissions": "documents:permission_list",
    "Dynamic Watermarking": "documents:watermark_list",
    "DRM & Document Protection": "documents:drm_policy_list",
    "Data Loss Prevention (DLP)": "documents:dlp_policy_list",
    "DLP Incidents": "documents:dlp_incident_list",
    "Secure Web Viewer": "documents:secure_viewer",
}
LIVE_LINKS["13.8"] = {
    "Collaboration Workspace": "documents:collaboration_hub",
    "Shared Documents": "documents:document_share_list",
    "Co-Authoring Sessions": "documents:coauthor_session_list",
    "Document Tasks": "documents:document_task_list",
    "Activity Feed & Alerts": "documents:document_activity_list",
}
```

---

## Conventions & Gotchas

1. **Multi-Tenancy**: All queries MUST use `documents_scope(Model.objects.all(), request)` or `documents_object(request, Model, pk)`. All forms inherit `TenantModelForm` or use `TenantUniqueMixin` with `reject_foreign(...)`.
2. **Concurrency & Row-level Locking**: `document_checkout`, `document_checkin`, `document_version_rollback`, and `document_branch_merge` acquire row-level locks on `Document` using `Document.objects.select_for_update().get(...)` inside `transaction.atomic()` to guarantee exclusive state transitions.
3. **Approval Decision Atomicity & Gate**: `approval_request_decide` multi-model updates must be wrapped in `transaction.atomic()`. If `workflow.requires_all_comments_resolved=True`, approvals are strictly blocked while any `is_blocking=True` comments remain in `status='open'`.
4. **Stage Progression Rules**: When `parallel_first` stage requests are approved, remaining sibling requests in that stage are automatically marked `status='bypassed'`. In `parallel_all`, stages advance only when no pending, delegated, or escalated requests remain.
5. **Electronic Signature Integrity**: `DocumentSignature` automatically generates a 32-character UUID token and records the document version's SHA-256 checksum. On edit, core identity and document fields are disabled. Raw SVG or signature glyphs MUST be rendered without `|safe` or sanitized to prevent stored XSS.
6. **Privilege & Emergency Bypass**: Emergency bypass on workflows requires superuser, tenant admin, or workflow initiator privileges. Deletion of workflows is restricted to `draft` status, and deletion of approval requests is restricted to pending requests in draft workflows.
7. **Performance & Text Deferral**: `DocumentVersion.extracted_text` contains massive full-text layers. Always call `.defer("extracted_text")` (or `.defer("base_version__extracted_text")`) on list views to avoid memory exhaustion and query bloat. Form dropdowns must include `.select_related("document")` on versions and `.select_related("workflow", "approver")` on approval requests.
8. **XSS Protection in Diff View**: `difflib.HtmlDiff` escapes body lines but interpolates `fromdesc` and `todesc` raw into `<th>` headers. Always escape user version labels using `django.utils.html.escape` before passing to `make_table`.
9. **File Upload Security**: All document and version uploads are validated via `validate_safe_doc_upload(f)` enforcing `ALLOWED_DOC_EXTENSIONS` and `MAX_UPLOAD_BYTES`.
10. **Privileged Operations**: `document_force_unlock`, `document_delete`, `document_version_delete`, and `document_branch_delete` require tenant administrator privileges (`@tenant_admin_required`).
11. **Storage Infrastructure Privilege Gate**: Storage volume management (`storage_volume_create`, `storage_volume_edit`, `storage_volume_delete`) strictly requires tenant administrator privileges (`@tenant_admin_required`).
12. **Streaming Archive Processing**: Batch import extraction MUST stream archives via `batch.archive_file.open("rb")` instead of accessing `.path` to remain fully compatible with S3/Azure/GCS cloud storage backends. Enforce safety thresholds: `MAX_BATCH_FILES = 500`, `MAX_BATCH_BYTES = 100MB`, `MAX_BATCH_UPLOAD_BYTES = 50MB`, and filter against `ALLOWED_DOC_EXTENSIONS`.
13. **Hierarchical Folder Performance**: `folder_tree` builds taxonomy hierarchies in Python memory using an adjacency list (`defaultdict(list)`) from a single query rather than issuing recursive database queries.
14. **Single Default Storage Volume**: `StorageVolume.save()` guarantees exactly one default storage volume per tenant by unsetting `is_default` on sibling volumes within an atomic transaction block.
15. **EAV Metadata Indexing & Polymorphic Values**: `DocumentMetadataValue` enforces strict composite unique constraints on `(tenant, document, version, field_name)` with conditional uniqueness when `version` is NULL. High-cardinality queries are indexed via compound keys `(tenant, data_type)`, `(tenant, validation_status)`, `(tenant, source)`.
16. **Checkout Lock Enforcement on Metadata Mutations**: Metadata values and OCR job text cannot be created, modified, deleted, or committed if the target `Document` is currently checked out / locked by another custodian.
17. **Taxonomy Term Governance & Anti-Cycle Traversal**: Governed taxonomy terms (`is_governed=True`) require administrator privileges to delete. Deleting a parent term with active child terms is blocked to prevent accidental destructive cascade. Ancestor traversal in `TaxonomyTermForm.clean()` detects and rejects circular parent assignments.
18. **OCR Completion Verification & Revision Fallback**: `document_ocr_job_apply` strictly verifies `job.status == 'completed'`. When `job.version` is NULL, text is committed to the document's latest revision (`doc.versions.order_by("-created_at").first()`), and suggested tags are merged cleanly into `doc.tags`.
19. **Search Telemetry & Session Token Pseudonymization**: Active Django session keys are never stored raw in `DocumentSearchQueryLog`. They are hashed via SHA-256 and redacted in detail views to prevent token harvesting.
20. **Atomic Synonym Counter Increment**: Read-path searches matching active synonyms must not execute individual synchronous `.save()` calls in a loop. Matching synonym IDs are collected and bulk-updated atomically using `.update(hit_count=F("hit_count") + 1)`.
21. **Distinct Facet Counting**: Aggregating document counts across facets (`doc_type`, `classification`, `status`) on querysets joined to `DocumentVersion` full-text layers MUST use `Count("id", distinct=True)` to prevent Cartesian product count multiplication.
22. **Public Guest Preview Isolation**: `public_share_preview.html` strictly extends `"base_auth.html"` to provide a clean, isolated guest document viewer card without leaking internal ERP navigation (`partials/sidebar.html`, `partials/topbar.html`).
23. **Public Token Gating & Post-Redirect-Get**: Access to public shares is gated by 32-byte cryptographic tokens (`share_token`). Passcode-protected shares authenticate via session tokens (`public_share_auth_<token>`) and use Post-Redirect-Get upon valid passcode submission to reliably record access telemetry without duplicate form submission risks.
24. **Open Redirect Mitigation**: Quick-action toggles and read-mark handlers (`document_task_toggle_complete`, `document_activity_mark_read`) must validate any `HTTP_REFERER` against allowed request hosts using `django.utils.http.url_has_allowed_host_and_scheme()` before issuing redirects, safely falling back to canonical named routes.
25. **Targeted Notification Privacy**: `document_activity_mark_read` strictly validates object ownership (`target_user=request.user`) to ensure tenant members cannot mark or manipulate private notifications intended for other users.
26. **Cross-Record Foreign Key Integrity**: Form validation across `DocumentShareForm`, `CoauthorSessionForm`, and `DocumentTaskForm` verifies that child relations (`version`, `draft`, `review_comment`) strictly belong to the specified parent `Document`.
27. **Administrative Authorization on Security Mutations**: Modifying security policies (`permission_create`, `permission_edit`, `permission_delete`, `watermark_create`, `watermark_edit`, `watermark_delete`, `drm_policy_create`, `drm_policy_edit`, `drm_policy_delete`, `dlp_policy_create`, `dlp_policy_edit`, `dlp_policy_delete`), resolving DLP incidents (`dlp_incident_resolve`), and engaging the emergency kill-switch (`drm_kill_switch`) strictly enforce `@tenant_admin_required`.
28. **Emergency Kill-Switch Idempotency**: `drm_kill_switch` enforces view-level status guarding. Repeated POSTs against an already revoked policy redirect gracefully without altering original audit timestamps or revocation reasons. In `secure_viewer`, revoked DRM policies immediately terminate document rendering and present an emergency revocation notice card.
29. **ReDoS Defense in Custom DLP Regular Expressions**: Custom regular expressions in `DlpPolicyForm` are validated against nested quantifiers and overlapping repetitions before saving, preventing catastrophic backtracking ReDoS denial of service.
30. **Dynamic Watermark Token Interpolation & Template Safety**: Watermark template strings interpolate tokens safely in Python memory (`render_watermark()`), avoiding server-side template injection (SSTI). Template hints in `form.html` are wrapped in `{% verbatim %}` blocks to avoid colliding with Django's template engine.
31. **Zero-Download Secure Web Viewer Sandboxing**: `secure_viewer.html` implements client-side focus-loss blur overlays (`onblur`/`onfocus`), keyboard shortcut interception (`Ctrl+P`, `Ctrl+C`, `Ctrl+S`), and context menu suppression as deterrents, backed by server-side payload access controls and active forensic watermark embedding.
