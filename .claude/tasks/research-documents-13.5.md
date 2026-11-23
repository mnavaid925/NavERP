# Research — Sub-module 13.5: Metadata & Indexing (Module 13 — Document Management System, documents)

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

- **Sibling models available to FK in `apps/documents/` (verified via grep):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Core logical document master containing title, slug, classification, status, owner, department, tags, version tracking.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Immutable physical file revision snapshot with `extracted_text`, file payload, checksum, and MIME type.
  - `documents.DocumentFolder` (`apps/documents/models/StorageRepository/DocumentFolders.py:9`, `NUMBER_PREFIX = "DFLD"`): Hierarchical folder repository tree with `path`, `default_classification`, and `default_document_type`.
  - `documents.DocumentTemplate` (`apps/documents/models/DocumentAuthoring/DocumentTemplates.py:31`, `NUMBER_PREFIX = "DTMPL"`): Pre-approved document templates with tokens.
  - `documents.StorageVolume` (`apps/documents/models/StorageRepository/StorageVolumes.py:7`, `NUMBER_PREFIX = "DSTG"`): Physical and cloud storage volumes.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): System users, authors, reviewers, indexing operators.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Organizational units for department-scoped schemas.
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing atomic concurrency-safe number generation (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DSCH` (`MetadataSchema`): Verified free (0 matches in repo).
  - `DMETA` (`DocumentMetadataValue`): Verified free (0 matches in repo).
  - `DTAX` (`TaxonomyTerm`): Verified free (0 matches in repo).
  - `DOCR` (`DocumentOcrJob`): Verified free (0 matches in repo).
  - Sibling prefixes safely preserved: `DOC` (Document), `DVER` (DocumentVersion), `DLOCK` (DocumentLock), `DBRN` (DocumentBranch), `DTMPL` (DocumentTemplate), `DSEC` (TemplateSection), `DDFT` (DocumentDraft), `DCMT` (DraftCollaboration), `DWF` (DocumentApprovalWorkflow), `DAPR` (DocumentApprovalRequest), `DSIG` (DocumentSignature), `DREV` (DocumentReviewComment), `DFLD` (DocumentFolder), `DSTG` (StorageVolume), `DREL` (DocumentRelationship), `DBLK` (DocumentBatchImport).

---

## Leaders surveyed (with source links)

1. **M-Files (Metadata-First Architecture & Dynamic Value Lists)** — Pioneer in metadata-driven ECM where "What" replaces "Where". Employs Property Definitions (strongly typed metadata fields), Classes (groupings of mandatory and optional property definitions), Value Lists (controlled, reusable pick-lists, both flat and hierarchical), and automated metadata inheritance from parent classes or folder virtual views.
   - *Source:* https://www.m-files.com/product/document-management/ · https://userguide.m-files.com/user-guide/latest/eng/properties_and_property_definitions.html
2. **Microsoft SharePoint & Azure AI Document Intelligence** — Enterprise standard for taxonomy and content governance. Implements Managed Metadata Service (MMS), Term Store, hierarchical Term Sets, official Terms, and Synonyms (alternate labels with type-ahead normalization). Azure AI Document Intelligence provides automated classification, prebuilt document models, key-value pair extraction, and layout OCR.
   - *Source:* https://learn.microsoft.com/en-us/sharepoint/managed-metadata · https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/
3. **Alfresco Content Services (Hyland ECM - Aspects & SOLR Indexing)** — Leading open-standards ECM. Features Content Models composed of Types and dynamic "Aspects" (reusable bundles of properties and constraints attached cross-cuttingly to any document), regular expression validation constraints, and background SOLR/Search Services pipelines for deep full-text indexing.
   - *Source:* https://docs.alfresco.com/content-services/latest/develop/repo-ext-points/content-model/ · https://docs.alfresco.com/search-services/latest/
4. **Laserfiche (Metadata Templates, Field Definitions & Quick Fields OCR)** — Renowned public sector and enterprise ECM. Uses Metadata Templates consisting of configurable Field Definitions (Text, Date, Number, List) with pattern validation and regex. Quick Fields software automates batch OCR, zonal data capture, token replacement, and dynamic rule-based indexing into template fields.
   - *Source:* https://doc.laserfiche.com/laserfiche.documentation/en-us/subsystems/client/content/resources/templates_and_fields.htm · https://www.laserfiche.com/products/document-capture/
5. **OpenText Extended ECM / Documentum (Attribute Schemas, Taxonomies & xPlore)** — Premier high-assurance ECM for regulated industries. Uses configurable object type attribute schemas, hierarchical corporate Taxonomies, and the xPlore full-text indexing engine with Index Agents and queues to extract both structured attributes and unstructured body text simultaneously.
   - *Source:* https://www.opentext.com/products/documentum-server · https://www.opentext.com/products/extended-ecm
6. **Box (Box Metadata Templates, Cascade Policies & Box AI)** — Cloud content cloud pioneer. Provides enterprise Metadata Templates with typed fields and single/multi-select options. Features **Metadata Cascade Policies** on folders that automatically propagate template schemas and default field values to nested files and directories, complemented by Box AI for automatic field extraction.
   - *Source:* https://support.box.com/hc/en-us/articles/360044196173-Using-Metadata · https://www.box.com/ai
7. **ABBYY Vantage / FlexiCapture (Intelligent Document Processing & OCR)** — Global leader in cognitive OCR and document processing. Implements OCR Skills (text layer extraction, deskewing, noise reduction, ICR handwriting recognition), Classification Skills (machine learning document categorization), Entity Extraction (key-value parsing), and field-level Confidence Scoring with human-in-the-loop review thresholds.
   - *Source:* https://www.abbyy.com/vantage/ · https://www.abbyy.com/flexicapture/
8. **Hyland OnBase (Document Types, Keyword Types & AutoFill Sets)** — Enterprise content platform for transactional workflows. Structures indexing via Document Types and Keyword Types (metadata fields). Utilizes AutoFill Keyword Sets to propagate related metadata automatically, along with automated OCR ingestion queues that populate keyword values without manual data entry.
   - *Source:* https://www.hyland.com/en/products/onbase · https://www.hyland.com/en/solutions/document-management

---

## Feature catalog (this sub-module only)

### Custom Metadata Schema
- **Configurable Metadata Schema Builder** — Enterprise definition of reusable schemas (content types) comprising custom typed fields (`text`, `textarea`, `integer`, `decimal`, `date`, `datetime`, `boolean`, `dropdown`, `multi_select`, `currency`, `url`). · seen in: M-Files Classes, Box Metadata Templates, SharePoint Content Types · priority: **table-stakes** · spine: `MetadataSchema` (`DSCH`) · **buildable now**
- **Field Validation Rules & Constraints** — Enforces field-level integrity including `is_required`, `min_value` / `max_value`, `min_length` / `max_length`, `regex_pattern` (e.g. for tax IDs, PO formats), and custom validation error messages. · seen in: Alfresco Constraints, Laserfiche Field Rules, M-Files · priority: **table-stakes** · spine: `MetadataSchema.fields_definition` JSON schema · **buildable now**
- **Document Type & Department Binding** — Maps metadata schemas to specific document types (`contract`, `sop`, `policy`, `technical`) or organizational units (`core.OrgUnit`), ensuring appropriate schemas appear during authoring. · seen in: M-Files, OnBase, SharePoint · priority: **table-stakes** · spine: `MetadataSchema.target_document_type`, `MetadataSchema.department` · **buildable now**
- **Document Metadata Instance Storage** — Strongly typed and JSON-backed instance records storing metadata values assigned to documents, recording author, validation status, and audit timestamps. · seen in: M-Files Metadata Card, Box Metadata Instance, Alfresco · priority: **table-stakes** · spine: `DocumentMetadataValue` (`DMETA`) · **buildable now**
- **Dynamic Context-Aware Metadata Card UI** — Dynamic form rendering that inspects the active schema and displays appropriate HTML form inputs (text inputs, datepickers, checkboxes, select dropdowns) with real-time client and server validation. · seen in: M-Files Metadata Card, Box, Laserfiche · priority: **common** · spine: Dynamic HTMX/Tailwind partial rendering `MetadataSchema` · **buildable now**

### Auto-Tagging & AI Classification
- **Content-Based Automatic Tagging** — Analyzes document text content or draft bodies using term frequency and keyword extraction to generate high-relevance tag suggestions. · seen in: Box AI, Azure AI Document Intelligence, OpenText · priority: **common** · spine: `DocumentOcrJob.suggested_tags` · **buildable now**
- **AI Document Classification & Category Suggestion** — Automatically categorizes incoming documents into document types (`contract`, `policy`, `sop`, `report`, `specification`) with associated confidence scores. · seen in: ABBYY Vantage Classification Skill, Azure Document Intelligence Classifier · priority: **common** · spine: `DocumentOcrJob.detected_category`, `DocumentOcrJob.category_confidence` · **buildable now**
- **Structured Entity & Key-Value Extraction** — Extracts semantic business entities (dates, monetary amounts, organizations, counter-parties, document reference codes) from unstructured text into structured key-value JSON. · seen in: ABBYY Vantage Document Skill, Azure AI Key-Value Pairs · priority: **common** · spine: `DocumentOcrJob.extracted_entities` JSON · **buildable now**
- **One-Click Tag & Category Acceptance** — Interactive UI action enabling document custodians to review AI-generated suggestions, confirm/edit tags, and push accepted tags directly to `Document.tags` and `Document.document_type`. · seen in: ABBYY Validation Station, Box AI · priority: **table-stakes** · spine: Action view committing `DocumentOcrJob` suggestions to `Document` · **buildable now**

### Full-Text Indexing & OCR
- **Asynchronous OCR Processing Pipeline** — Asynchronous job queue managing document scanning, OCR execution, status tracking (`queued`, `processing`, `completed`, `failed`, `needs_review`), and error diagnostics. · seen in: Laserfiche Quick Fields, ABBYY Vantage, OnBase Full-Text Server · priority: **table-stakes** · spine: `DocumentOcrJob` (`DOCR`) · **buildable now**
- **Full-Text Content Layer Ingestion** — Extracts and indexes textual body layers from scanned PDFs, images, or digital files, synchronizing extracted text to `DocumentVersion.extracted_text` for downstream search. · seen in: OpenText xPlore, Alfresco SOLR, OnBase OCR · priority: **table-stakes** · spine: `DocumentOcrJob.extracted_text` $\rightarrow$ `DocumentVersion.extracted_text` · **buildable now**
- **OCR Confidence Scoring & Review Flagging** — Quantifies extraction certainty with numerical confidence scores (0.00% to 100.00%), word count, page count, and automated flagging for low-confidence scans (<85%) requiring human verification. · seen in: ABBYY Vantage Confidence Score, Azure AI Layout · priority: **table-stakes** · spine: `DocumentOcrJob.confidence_score`, `DocumentOcrJob.status="needs_review"` · **buildable now**
- **Pluggable OCR Engine Abstraction** — Extensible architecture supporting multiple OCR engines (`tesseract`, `azure_document_intelligence`, `aws_textract`, `google_vision`, `internal_heuristic`) with configurable language settings. · seen in: ABBYY, Box Skills, Laserfiche · priority: **common** · spine: `DocumentOcrJob.ocr_engine`, `DocumentOcrJob.language` · **buildable now**
- **Handwriting (ICR) & Barcode Detection Support** — Metadata markers indicating detection of handwritten annotations or embedded barcode/QR identifier strings for automated document sorting. · seen in: ABBYY Vantage ICR, Laserfiche Quick Fields · priority: **differentiator** · spine: `DocumentOcrJob.has_handwriting`, `DocumentOcrJob.detected_barcodes` · **buildable now**

### Controlled Vocabulary & Thesauri
- **Centralized Taxonomy Term Repository** — Tenant-wide controlled vocabulary manager organizing standardized business terms, industry classifications, and corporate glossaries into distinct vocabulary sets. · seen in: SharePoint Term Store, M-Files Value Lists, OpenText Taxonomies · priority: **table-stakes** · spine: `TaxonomyTerm` (`DTAX`) · **buildable now**
- **Hierarchical Taxonomy Trees** — Nested parent-child relationship support enabling deep taxonomic classification (e.g. *Jurisdiction $\rightarrow$ North America $\rightarrow$ United States $\rightarrow$ New York*). · seen in: SharePoint Term Sets, M-Files Hierarchical Lists · priority: **table-stakes** · spine: `TaxonomyTerm.parent` (self FK) · **buildable now**
- **Synonym & Alternate Label Management** — Configurable synonym lists for each standardized term (e.g. Preferred: "Human Resources", Synonyms: ["HR", "Personnel", "People Ops"]), enabling intelligent search expansion and auto-normalization during tagging. · seen in: SharePoint Synonyms, OpenText Concept Thesauri · priority: **table-stakes** · spine: `TaxonomyTerm.synonyms` (JSON array) · **buildable now**
- **Standardized Code & Cross-Reference Mapping** — Maps internal taxonomy terms to external regulatory or industry standards (ISO codes, NAICS, GL account references, legal classifications). · seen in: OpenText, SharePoint Term ID · priority: **common** · spine: `TaxonomyTerm.cross_reference_code` · **buildable now**
- **Open vs Closed Vocabulary Governance** — Designates whether non-administrative contributors can introduce new terms during tagging or whether tagging is strictly locked to approved terms. · seen in: SharePoint Open/Closed Term Sets · priority: **common** · spine: `TaxonomyTerm.is_governed` · **buildable now**

### Metadata Inheritance & Propagation
- **Folder Cascade Policies** — Binds metadata schemas and default values to folders (`DocumentFolder`), automatically propagating schema requirements and default values to all documents filed in that folder branch. · seen in: Box Metadata Cascade Policies, Alfresco Folder Inheritance · priority: **table-stakes** · spine: `MetadataSchema.target_folder`, `MetadataSchema.inherit_to_children` · **buildable now**
- **Document Template Inheritance** — Automatically populates default metadata values and schema bindings when documents are authored from a `DocumentTemplate`. · seen in: Laserfiche Template Inheritance, M-Files Class Defaults · priority: **common** · spine: `DocumentMetadataValue.source="template_inherited"` · **buildable now**
- **Bulk Metadata Updates & Batch Propagation** — Administrative utility enabling bulk metadata edits across multiple selected documents or entire folder trees with transactional safety and change auditing. · seen in: Box Bulk Edit, SharePoint Quick Edit, Laserfiche · priority: **common** · spine: Bulk update service updating `DocumentMetadataValue` · **buildable now**
- **Inheritance Provenance & Override Tracking** — Flags metadata fields to show whether a value is inherited from a parent folder, inherited from a template, extracted by AI, or manually overridden by an author. · seen in: Box, M-Files Property Source · priority: **common** · spine: `DocumentMetadataValue.source`, `DocumentMetadataValue.is_overridden` · **buildable now**

### Beyond the Bullets
- **Schema Versioning & Evolution** — Tracks schema revisions (`version=1.0`), allowing schema field changes without corrupting existing historical document metadata instances.
- **Metadata Validation Audit Status** — Explicit validation flag (`valid`, `invalid`, `pending_validation`) with error summary ensuring documents cannot be marked as "Approved" or "Published" if required metadata is missing or violates regex rules.

---

## Recommended build scope (this pass — 4 models)

1. **`MetadataSchema`** [`DSCH-`] — Custom metadata schema / content type definitions and validation rules.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `name` (CharField 150), `code` (CharField 60, e.g. `SCH-CONTRACT-01`), `description` (TextField), `target_document_type` (CharField 40, choices matching `Document.DOCUMENT_TYPE_CHOICES` or `all`), `department` (FK `core.OrgUnit`, null=True, blank=True), `target_folder` (FK `documents.DocumentFolder`, null=True, blank=True, related_name="metadata_schemas"), `inherit_to_children` (BooleanField, default True), `fields_definition` (JSONField, array of field specifications: `key`, `label`, `type`, `required`, `default`, `choices`, `regex_pattern`, `help_text`), `version` (CharField 20, default "1.0"), `is_mandatory` (BooleanField, default False), `is_active` (BooleanField, default True), `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=PROTECT).
   - **Choices**: `target_document_type` choices (`all`, `contract`, `policy`, `sop`, `report`, `specification`, `proposal`, `template`, `technical`, `general`).
   - **Justified by**: Custom Metadata Schema, Folder Cascade Policies, Field Validation Rules.
   - **FKs**: `core.Tenant`, `core.OrgUnit`, `documents.DocumentFolder`, `accounts.User`.

2. **`DocumentMetadataValue`** [`DMETA-`] — Instance values of a metadata schema assigned to a document/version.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `document` (FK `documents.Document`, on_delete=CASCADE, related_name="metadata_values"), `schema` (FK `documents.MetadataSchema`, on_delete=PROTECT, related_name="document_values"), `version` (FK `documents.DocumentVersion`, null=True, blank=True, on_delete=SET_NULL, related_name="metadata_values"), `values_json` (JSONField, dictionary of `{field_key: value}`), `source` (CharField 30, choices: `manual_entry`, `folder_inherited`, `template_inherited`, `ai_extracted`, `bulk_updated`), `is_overridden` (BooleanField, default False), `validation_status` (CharField 25, choices: `valid`, `invalid`, `pending_validation`), `validation_errors` (TextField, blank=True), `last_updated_by` (FK `settings.AUTH_USER_MODEL`, on_delete=SET_NULL, null=True, blank=True).
   - **Choices**: `SOURCE_CHOICES` (`manual_entry`, `folder_inherited`, `template_inherited`, `ai_extracted`, `bulk_updated`), `VALIDATION_STATUS_CHOICES` (`valid`, `invalid`, `pending_validation`).
   - **Constraints**: Unique constraint on `(tenant, document, schema)`.
   - **Justified by**: Metadata Instance Storage, Inheritance & Propagation, Validation status.
   - **FKs**: `core.Tenant`, `documents.Document`, `documents.MetadataSchema`, `documents.DocumentVersion`, `accounts.User`.

3. **`TaxonomyTerm`** [`DTAX-`] — Controlled vocabulary, hierarchical taxonomy terms, and synonym mapping.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `vocabulary_name` (CharField 100, e.g. "Jurisdictions", "Document Categories", "Compliance Frameworks", "Asset Classes"), `term_code` (CharField 60, e.g. `JUR-US-NY`, `ISO-27001`), `label` (CharField 150, preferred term label), `slug` (SlugField 160, blank=True), `parent` (FK `self`, null=True, blank=True, on_delete=CASCADE, related_name="children"), `description` (TextField, blank=True), `synonyms` (JSONField, list of string synonyms e.g. `["HR", "Human Resources", "People"]`), `cross_reference_code` (CharField 100, blank=True, external ISO/NAICS/ERP code), `is_governed` (BooleanField, default True, closed vocabulary), `is_active` (BooleanField, default True), `sort_order` (PositiveIntegerField, default 0), `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=PROTECT).
   - **Constraints**: Unique constraint on `(tenant, vocabulary_name, term_code)`.
   - **Justified by**: Controlled Vocabulary & Thesauri, Hierarchical Trees, Synonym Management, Cross-Reference Mapping.
   - **FKs**: `core.Tenant`, `TaxonomyTerm` (self), `accounts.User`.

4. **`DocumentOcrJob`** [`DOCR-`] — OCR processing jobs, full-text extraction, AI classification, and auto-tagging.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `document` (FK `documents.Document`, on_delete=CASCADE, related_name="ocr_jobs"), `version` (FK `documents.DocumentVersion`, null=True, blank=True, on_delete=SET_NULL, related_name="ocr_jobs"), `status` (CharField 25, choices: `queued`, `processing`, `completed`, `failed`, `needs_review`), `ocr_engine` (CharField 30, choices: `tesseract`, `azure_document_intelligence`, `aws_textract`, `google_vision`, `internal_heuristic`), `language` (CharField 10, default "eng"), `extracted_text` (TextField, blank=True), `confidence_score` (DecimalField max_digits=5, decimal_places=2, default=0.00), `word_count` (PositiveIntegerField, default=0), `page_count` (PositiveIntegerField, default=1), `has_handwriting` (BooleanField, default=False), `detected_barcodes` (JSONField, blank=True, default=list), `detected_category` (CharField 40, blank=True, AI-suggested document type), `category_confidence` (DecimalField max_digits=5, decimal_places=2, default=0.00), `suggested_tags` (JSONField, blank=True, default=list), `extracted_entities` (JSONField, blank=True, default=dict), `is_applied_to_document` (BooleanField, default=False), `error_message` (TextField, blank=True), `started_at` (DateTimeField, null=True, blank=True), `completed_at` (DateTimeField, null=True, blank=True), `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=PROTECT).
   - **Choices**: `STATUS_CHOICES` (`queued`, `processing`, `completed`, `failed`, `needs_review`), `OCR_ENGINE_CHOICES` (`tesseract`, `azure_document_intelligence`, `aws_textract`, `google_vision`, `internal_heuristic`).
   - **Justified by**: Full-Text Indexing & OCR, Auto-Tagging & AI Classification, Entity Extraction, Confidence Scoring.
   - **FKs**: `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `accounts.User`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **13.6 Search & Discovery** — Faceted search filters, vector/hybrid semantic search, saved search queries, search analytics, and query optimization.
- **13.7 Document Security & Access Control** — Granular field-level metadata access permissions (e.g. restricting access to confidential metadata fields based on user role).
- **13.9 Records Management & Compliance** — Retention schedule rules triggered by metadata date fields (e.g. disposing documents 7 years after `contract_end_date`).
- **13.15 Electronic Forms & Data Capture** — Web-based interactive form designer, external portal submissions, and dynamic e-form schemas.

---

## Deferred (later passes / integrations)

- Live third-party Cloud OCR SDK credentials (Azure AI Document Intelligence, AWS Textract, Google Vision live API calls) — model cleanly abstracts engines and fields; live execution defaults to local heuristic/Tesseract extraction pipeline with error fallbacks.
- Live Machine Learning classification models & vector embeddings (FAISS/pgvector) — document classification in 13.5 uses pattern/lexical heuristics and structured entity parsers, with vector embeddings reserved for 13.6.
- Background asynchronous daemon workers (Celery/Redis worker cluster) — jobs execute with status transitions and safe synchronous fallbacks.
