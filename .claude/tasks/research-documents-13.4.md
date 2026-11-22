# Research — Sub-module 13.4: Document Storage & Repository (Module 13 — Document Management System, documents)

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
  - `13.3` (Document Approval & Review Workflow):
    - `Visual Workflow Designer`: `documents:workflow_list` (`DocumentApprovalWorkflow`)
    - `Electronic Signature Capture`: `documents:signature_list` (`DocumentSignature`)
    - `Delegation & Escalation Rules`: `documents:approval_request_list` (`DocumentApprovalRequest`)
    - `Review Comments & Annotation`: `documents:review_comment_list` (`DocumentReviewComment`)
    - `Approval Dashboard & Status Tracking`: `documents:approval_dashboard`

- **Sibling models available to FK in `apps/documents/` (verified via grep):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Core logical document master record containing title, slug, classification, status, owner, department, version tracking.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Immutable physical file revision snapshot with major/minor/patch numbering, SHA-256 checksum, file payload.
  - `documents.DocumentTemplate` (`apps/documents/models/DocumentAuthoring/DocumentTemplates.py:31`, `NUMBER_PREFIX = "DTMPL"`): Pre-approved document templates.
  - `documents.DocumentDraft` (`apps/documents/models/DocumentAuthoring/DocumentDrafts.py:38`, `NUMBER_PREFIX = "DDFT"`): Working authoring drafts.
  - `documents.DocumentApprovalWorkflow` (`apps/documents/models/ApprovalWorkflow/DocumentApprovalWorkflows.py:8`, `NUMBER_PREFIX = "DWF"`): Document approval lifecycle workflows.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): System users, folder owners, creators, custodians.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Departmental organization units for departmental repository folders.
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing atomic concurrency-safe number generation (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DFLD` (`DocumentFolder`): Verified free (0 matches in repo).
  - `DSTG` (`StorageVolume`): Verified free (0 matches in repo).
  - `DREL` (`DocumentRelationship`): Verified free (0 matches in repo).
  - `DBLK` (`DocumentBatchImport`): Verified free (0 matches in repo).
  - Sibling prefixes safely preserved: `DOC` (Document), `DVER` (DocumentVersion), `DLOCK` (DocumentLock), `DBRN` (DocumentBranch), `DTMPL` (DocumentTemplate), `DSEC` (TemplateSection), `DDFT` (DocumentDraft), `DCMT` (DraftCollaboration), `DWF` (DocumentApprovalWorkflow), `DAPR` (DocumentApprovalRequest), `DSIG` (DocumentSignature), `DREV` (DocumentReviewComment).

---

## Leaders surveyed (with source links)

1. **Alfresco Content Services (Hyland ECM)** — Leading enterprise open-standards content repository. Provides deeply scalable hierarchical folder structures with path-based taxonomy and "Smart Folders" (saved dynamic queries functioning as virtual folders). Features content store selectors routing files to heterogeneous storage tiers (SSD hot store, S3 warm store, Glacier cold store), native deduplication by SHA-256 digest, and high-throughput batch import tools for network drive migrations.
   - *Source:* https://www.hyland.com/en/products/alfresco-platform · https://docs.alfresco.com/content-services/latest/admin/content-stores/
2. **OpenText Extended ECM / Documentum** — Gold standard in regulated enterprise content management. Employs structured workspace folder hierarchies, physical and virtual content routing, Hierarchical Storage Management (HSM) across optical/SAN/cloud storage tiers, parent-child document assemblies and multi-directional cross-reference link graphs, with high-volume enterprise ingestion pipelines (Archive Center).
   - *Source:* https://www.opentext.com/products/extended-ecm · https://www.opentext.com/products/documentum-server
3. **Microsoft SharePoint & Azure Blob Storage** — Ubiquitous enterprise content library framework. Provides nested document libraries and folder hierarchies, metadata-driven views, Azure Blob storage tiering (Hot, Cool, Cold, Archive) with automated lifecycle management rules, document set linking, and the SharePoint Migration Tool (SPMT) for bulk ingest of legacy file shares.
   - *Source:* https://learn.microsoft.com/en-us/sharepoint/modern-experience-sharing-permissions · https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-storage-tiers
4. **Laserfiche Repository Architecture** — Renowned records and document management system. Distinguishes logical folder hierarchies seen by users from physical underlying "Volumes" (local disk, NAS, SAN, or cloud). Implements automated volume rollover when size or date quotas are reached, storage tiering to optical/cold media, and high-speed batch imports using Laserfiche Import Agent with OCR staging.
   - *Source:* https://www.laserfiche.com/products/document-management/ · https://doc.laserfiche.com/laserfiche.documentation/en-us/subsystems/server/content/resources/volumes.htm
5. **Box (Box Enterprise Storage & Box Shuttle)** — Cloud-native content repository leader. Offers structured folder taxonomies with watermarking and inherited permissions, regional storage zones (Box Zones) for hybrid/compliance hosting, parent-child folder quotas, document collection tagging, and Box Shuttle for petabyte-scale bulk file and ZIP migrations with comprehensive error reporting.
   - *Source:* https://www.box.com/cloud-content-management · https://www.box.com/shuttle
6. **M-Files (Metadata-Driven Repository & Virtual Folders)** — Pioneer in folderless/virtual-folder architecture. While presenting conventional virtual folder trees to users based on dynamic metadata facets, it stores files in centralized repositories with deduplication, handles multi-location storage targets, and manages rich bidirectional 360-degree document relationship graphs (e.g. Master Agreement ↔ Exhibits ↔ Invoices).
   - *Source:* https://www.m-files.com/product/document-management/ · https://userguide.m-files.com/user-guide/latest/eng/relationships.html
7. **Hyland OnBase (Enterprise Disk Groups & Ingestion)** — Industry-standard ECM for high-volume paperless operations. Organizes content into logical folder taxonomies while distributing physical payloads across configurable "Disk Groups", with automated rollover to archival tiers, bidirectional document cross-referencing, and bulk document batch import processors.
   - *Source:* https://www.hyland.com/en/products/onbase · https://www.hyland.com/en/solutions/document-management
8. **NetApp StorageGRID & AWS S3 Enterprise Object Storage** — Industry-leading hybrid cloud object storage management platform. Implements software-defined storage volumes, multi-tier lifecycle policies (Hot → Warm → Cold → Glacier), automated data deduplication, encryption at rest, and bulk upload staging.
   - *Source:* https://www.netapp.com/data-storage/storagegrid/ · https://aws.amazon.com/s3/storage-classes/

---

## Feature catalog (this sub-module only)

### Folder Hierarchy & Taxonomy
- **Nested Hierarchical Folders** — Multi-tier parent-child folder tree with infinite nesting depth, path generation (e.g. `/Corporate/Legal/Contracts/2026/`), breadcrumbs, and folder slugging. · seen in: SharePoint, Alfresco, Laserfiche, OpenText · priority: **table-stakes** · spine: `DocumentFolder.parent` (self FK) + `path` · **buildable now**
- **Departmental & Project Folder Ownership** — Binds root/sub-folders to specific organizational units (`core.OrgUnit`), default custodian (`accounts.User`), and access restrictions. · seen in: OpenText, Alfresco, SharePoint · priority: **table-stakes** · spine: `DocumentFolder.department`, `DocumentFolder.owner` · **buildable now**
- **Folder Inheritance & Default Metadata** — Child folders and nested documents automatically inherit default document type, classification level (`public`, `internal`, `confidential`, `restricted`), and retention flags from the parent folder. · seen in: Alfresco, Laserfiche, Box · priority: **common** · spine: `DocumentFolder.default_classification`, `DocumentFolder.default_document_type` · **buildable now**
- **Virtual Folder Views (Dynamic Smart Folders)** — Configurable saved dynamic query views that present documents matching specific filter criteria (e.g., "All Confidential Contracts in Legal", "Expired Policies") as if they were residing in a physical folder. · seen in: M-Files, Alfresco Smart Folders · priority: **common** · spine: `DocumentFolder.is_virtual` + `virtual_criteria_json` · **buildable now**
- **Folder Visual Identifiers & Status** — Configurable Lucide folder icon, color swatch, description, and active/archived status for clean visual identification. · seen in: Box, SharePoint, Google Drive · priority: **common** · spine: `DocumentFolder.color_code`, `DocumentFolder.icon_name` · **buildable now**

### Cloud & On-Premises Deployment / Storage Tiering & Optimization
- **Storage Volume Registry & Multi-Backend Abstraction** — Configurable storage repository targets abstracting storage backends (`local_filesystem`, `network_nas`, `s3_compatible`, `azure_blob`, `google_cloud_storage`, `air_gapped_onprem`). · seen in: Alfresco, Laserfiche Volumes, NetApp, OnBase Disk Groups · priority: **table-stakes** · spine: `StorageVolume.backend_type` · **buildable now**
- **Storage Tier Classification** — Explicit storage tiers (`hot` for active SSD performance, `warm` for standard online storage, `cold` for infrequent access, `glacier_archive` for immutable compliance archival). · seen in: AWS S3, Azure Blob, Alfresco, OpenText HSM · priority: **table-stakes** · spine: `StorageVolume.tier` · **buildable now**
- **Storage Quota & Utilization Monitoring** — Tenant and volume-level capacity limits (`max_capacity_bytes`, `allocated_bytes`, `utilized_bytes`, `utilized_percentage`), soft warning threshold notifications, and hard-stop quota enforcement preventing repository overflow. · seen in: Box, SharePoint, Laserfiche, NetApp · priority: **table-stakes** · spine: `StorageVolume.max_capacity_bytes`, `StorageVolume.utilized_bytes`, `StorageVolume.warning_threshold_pct` · **buildable now**
- **Automated Volume Rollover & Capacity Alerting** — Automatically directs new document uploads and revisions to the next active storage volume once the primary volume reaches its warning capacity threshold. · seen in: Laserfiche Volume Rollover, OnBase Disk Groups · priority: **common** · spine: `StorageVolume.is_default_target`, `StorageVolume.is_full`, `StorageVolume.rollover_volume` · **buildable now**
- **Storage Optimization Flags (Deduplication & Compression)** — Records repository-wide deduplication checksum rules (SHA-256 content deduplication), compression settings (`none`, `gzip`, `zstandard`), and encryption at rest standards (`aes_256`, `kms_managed`, `none`). · seen in: NetApp StorageGRID, Alfresco, AWS S3 · priority: **common** · spine: `StorageVolume.compression_type`, `StorageVolume.deduplication_enabled`, `StorageVolume.encryption_type` · **buildable now**

### Document Linking & Relationships
- **Bidirectional Document Relationships** — Explicit relationship links connecting source and target documents with semantic relationship types:
  - `parent_child` (Master document and sub-documents / appendices)
  - `supersedes` / `superseded_by` (Successor replacing legacy document)
  - `references` / `referenced_by` (Cross-document legal/technical citation)
  - `derived_from` (Draft, translation, or variant derived from root document)
  - `contract_exhibit` (Master Services Agreement ↔ Statement of Work / Exhibit)
  - `supporting_evidence` (Audit proof, lab report, or receipt attached to parent)
  - `amendment` (Official legal rider or change amendment)
  · seen in: OpenText Documentum, M-Files, Alfresco, Conga · priority: **table-stakes** · spine: `DocumentRelationship.relationship_type` (`DREL`) · **buildable now**
- **Relationship Strength & Integrity Safeguards** — Tracks relationship nature (`hard_dependency`, `informational`, `contractual`), prevents self-referential cycles, and supports automatic reverse-link visibility in both source and target document detail views. · seen in: M-Files, OpenText · priority: **common** · spine: `DocumentRelationship.is_bidirectional`, `DocumentRelationship.dependency_level` · **buildable now**
- **Document Relationship Visual Network Map** — Tabular and visual interactive network summary illustrating connected documents, related version numbers, and relation types on the document detail page. · seen in: M-Files 360-degree view, OpenText · priority: **common** · spine: Template relationship tab rendering `DocumentRelationship` records · **buildable now**

### Bulk Upload & Import
- **Batch Import Job Queue & Tracking** — Multi-file batch upload session entity tracking bulk ingestion operations with unique identifier (`DBLK-#####`), batch title, target folder, target storage volume, and status (`draft`, `queued`, `extracting`, `validating`, `processing`, `completed`, `failed`, `partially_completed`). · seen in: Box Shuttle, Laserfiche Import Agent, SharePoint Migration Tool · priority: **table-stakes** · spine: `DocumentBatchImport` model (`DBLK`) · **buildable now**
- **ZIP Archive & Batch File Ingestion** — Supports uploading compressed ZIP packages or multi-file manifests, with automated archive inspection, file count verification, total uncompressed size calculation, and folder unpack destination mapping. · seen in: Box Shuttle, Alfresco Bulk Ingest, Laserfiche · priority: **table-stakes** · spine: `DocumentBatchImport.source_type` (`zip_archive`, `file_manifest`, `direct_upload`) · **buildable now**
- **Ingestion Execution Metrics & Progress Counters** — Real-time progress counters tracking `total_files_detected`, `processed_files_count`, `success_files_count`, `failed_files_count`, `total_bytes_processed`, with percentage calculation. · seen in: Box Shuttle, SPMT, Laserfiche · priority: **table-stakes** · spine: `DocumentBatchImport` progress fields · **buildable now**
- **Granular Import Audit Log & Failure Manifest** — Captures detailed processing summary, JSON/text audit log recording individual file extraction details, and error diagnostics for corrupted or skipped files without halting the entire batch. · seen in: Box Shuttle, SPMT, Laserfiche · priority: **common** · spine: `DocumentBatchImport.log_summary`, `DocumentBatchImport.error_details` · **buildable now**

### Beyond the Bullets
- **Document Quick-Filing Action** — Quick modal/action on `Document` detail page to assign or move a document to a designated folder in the hierarchy, with automatic folder path breadcrumbs.
- **Folder Storage Consumption Aggregation** — Real-time aggregation of total files and total storage bytes contained within a folder branch (recursive roll-up).

---

## Recommended build scope (this pass — 4 models)

1. **`DocumentFolder`** [`DFLD-`] — Hierarchical folder taxonomy and virtual folder organization.
   - Fields: `number`, `tenant`, `name`, `slug`, `parent` (self FK, `null=True`, `related_name="children"`), `path` (e.g. `/Corporate/Legal/`), `description`, `color_code` (e.g. `#3B82F6`), `icon_name` (e.g. `folder`, `briefcase`, `shield`), `department` (`core.OrgUnit`, `null=True`), `owner` (`settings.AUTH_USER_MODEL`), `default_classification` (`public`, `internal`, `confidential`, `restricted`), `default_document_type`, `is_virtual` (boolean), `virtual_criteria_json` (text/json), `is_system` (boolean), `is_active` (boolean).
   - FKs: `core.Tenant`, `core.OrgUnit`, `accounts.User`.
2. **`StorageVolume`** [`DSTG-`] — Physical/cloud storage repository locations, tiering, and quota management.
   - Fields: `number`, `tenant`, `name`, `code` (e.g. `SSD-HOT-01`, `S3-STANDARD-US`), `backend_type` (`local_filesystem`, `network_nas`, `s3_compatible`, `azure_blob`, `google_cloud_storage`, `air_gapped`), `tier` (`hot`, `warm`, `cold`, `glacier_archive`), `base_path` / `bucket_name`, `region`, `endpoint_url`, `max_capacity_bytes` (big int), `utilized_bytes` (big int), `utilized_percentage` (decimal), `warning_threshold_pct` (positive int, default 85), `is_default` (boolean), `is_full` (boolean), `is_active` (boolean), `compression_type` (`none`, `gzip`, `zstd`), `deduplication_enabled` (boolean), `encryption_type` (`none`, `aes_256`, `kms_managed`).
   - FKs: `core.Tenant`.
3. **`DocumentRelationship`** [`DREL-`] — Semantic bidirectional links and cross-references between documents.
   - Fields: `number`, `tenant`, `source_document` (`documents.Document`, `related_name="outgoing_relationships"`), `target_document` (`documents.Document`, `related_name="incoming_relationships"`), `relationship_type` (`parent_child`, `supersedes`, `references`, `derived_from`, `contract_exhibit`, `supporting_evidence`, `amendment`), `is_bidirectional` (boolean, default True), `dependency_level` (`informational`, `contractual`, `strict_blocking`), `description` (char/text), `created_by` (`settings.AUTH_USER_MODEL`).
   - Constraints: Unique constraint on `(tenant, source_document, target_document, relationship_type)`.
   - FKs: `core.Tenant`, `documents.Document`, `accounts.User`.
4. **`DocumentBatchImport`** [`DBLK-`] — High-volume bulk ingestion, ZIP archive unpacking, and migration job management.
   - Fields: `number`, `tenant`, `batch_name`, `source_type` (`zip_archive`, `file_manifest`, `multi_file`, `legacy_migration`), `target_folder` (`documents.DocumentFolder`, `null=True`, `related_name="batch_imports"`), `storage_volume` (`documents.StorageVolume`, `null=True`, `related_name="batch_imports"`), `status` (`draft`, `queued`, `extracting`, `validating`, `processing`, `completed`, `partially_completed`, `failed`), `archive_file` (FileField, `upload_to="documents/bulk_imports/%Y/%m/"`, `null=True`), `total_files_detected` (positive int), `processed_files_count` (positive int), `success_files_count` (positive int), `failed_files_count` (positive int), `total_bytes_processed` (big int), `log_summary` (text), `error_details` (text), `created_by` (`settings.AUTH_USER_MODEL`), `started_at` (datetime, `null=True`), `completed_at` (datetime, `null=True`).
   - FKs: `core.Tenant`, `documents.DocumentFolder`, `documents.StorageVolume`, `accounts.User`.

---

## Belongs to sibling sub-modules (parked, not scoped here)
- **13.5 Metadata & Indexing** — Custom metadata schema builder, OCR processing pipeline, auto-tagging, entity extraction, and controlled thesauri.
- **13.6 Search & Discovery** — Faceted search filters, full-text vector index, saved searches, and natural language query.
- **13.14 Document Archival & Long-Term Preservation** — Formal retention schedules, legal hold policies, WORM write-once-read-many immutable locking, format obsolescence migration, and rehydration requests.

---

## Deferred (later passes / integrations)
- Direct cloud provider SDK streaming (boto3 / Azure Blob Storage live API upload handlers) — model abstracts storage endpoints and credentials cleanly; live execution utilizes local media/filesystem store with pluggable storage backends.
- High-performance distributed background ZIP worker (Celery/Redis worker daemons) — standard execution processes batches synchronously with progress tracking and robust exception capture.
