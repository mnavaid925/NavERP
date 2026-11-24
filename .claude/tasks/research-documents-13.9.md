# Research — Sub-module 13.9: Records Management & Compliance (Module 13 — Document Management System, documents)

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
    - `Custom Metadata Schema`: `documents:metadata_schema_list` (`MetadataSchema`)
    - `Auto-Tagging & AI Classification`: `documents:document_ocr_job_list` (`DocumentOcrJob`)
    - `Full-Text Indexing & OCR`: `documents:document_ocr_job_list` (`DocumentOcrJob`)
    - `Controlled Vocabulary & Thesauri`: `documents:taxonomy_term_list` (`TaxonomyTerm`)
    - `Metadata Inheritance & Propagation`: `documents:metadata_value_list` (`DocumentMetadataValue`)
  - `13.6` (Search & Discovery):
    - `Advanced Search & Filters`: `documents:search_hub`
    - `Faceted Search Navigation`: `documents:search_hub`
    - `Saved Searches & Alerts`: `documents:document_saved_search_list` (`DocumentSavedSearch`)
    - `Natural Language Query & AI Search`: `documents:search_hub`
    - `Search Analytics & Query Optimization`: `documents:document_search_analytics` (`DocumentSearchQueryLog`)
    - `Search Alerts`: `documents:document_search_alert_list` (`DocumentSearchAlert`)
    - `Search Synonyms`: `documents:document_search_synonym_list` (`DocumentSearchSynonym`)
    - `Search Query Logs`: `documents:document_search_query_log_list` (`DocumentSearchQueryLog`)
  - `13.7` (Document Security & Access Control):
    - `Document-Level Permissions`: `documents:permission_list` (`DocumentAccessPermission`)
    - `Dynamic Watermarking`: `documents:watermark_list` (`WatermarkPolicy`)
    - `DRM & Document Protection`: `documents:drm_policy_list` (`DocumentDrmPolicy`)
    - `Data Loss Prevention (DLP)`: `documents:dlp_policy_list` (`DlpPolicy`)
    - `DLP Incidents`: `documents:dlp_incident_list` (`DlpIncident`)
    - `Secure Web Viewer`: `documents:secure_viewer`
  - `13.8` (Collaboration & Sharing):
    - `Internal & External Sharing`: `documents:collaboration_hub`
    - `Real-Time Co-Authoring`: `documents:coauthor_session_list` (`CoauthorSession`)
    - `Commenting & Annotation`: `documents:review_comment_list` (`DocumentReviewComment`)
    - `Task Assignment & Document Review`: `documents:document_task_list` (`DocumentTask`)
    - `Activity Feed & Notifications`: `documents:document_activity_list` (`DocumentActivity`)
    - `Document Shares`: `documents:document_share_list` (`DocumentShare`)

- **Sibling models available to FK in `apps/documents/` (verified via repo audit):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Logical document master entity containing title, slug, classification (`public`, `internal`, `confidential`, `restricted`), document_type, status, owner, department, tags, version tracking. Target of record declarations, legal holds, and disposition reviews.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Physical file revision snapshot with file payload, hash (SHA-256), size, and MIME type. Locked when a document is declared a formal record.
  - `documents.DocumentFolder` (`apps/documents/models/StorageRepository/DocumentFolders.py:9`, `NUMBER_PREFIX = "DFLD"`): Hierarchical folder repository tree providing default metadata, classification, and inherited retention rules.
  - `documents.DocumentApprovalWorkflow` (`apps/documents/models/ApprovalWorkflow/DocumentApprovalWorkflows.py:8`, `NUMBER_PREFIX = "DWF"`): Workflow definitions usable for disposition review and sign-off workflows.
  - `documents.MetadataSchema` & `DocumentMetadataValue` (`apps/documents/models/MetadataIndexing/`, `DSCH`, `DMETA`): Custom metadata attributes attached to documents and records.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor across all models.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): Enterprise users, records managers, legal custodians, approval authorities, and destruction certifiers.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Organizational units for department-level file plan ownership and custodian scope.
  - `core.LegalHold` (`apps/core/models/LegalHold.py:class LegalHold`): Enterprise-wide preservation order built in Module 0.16; provides system-wide matter reference, issuing authority, and schedule suspension hooks.
  - `core.RetentionPolicy` & `core.DisposalRecord` (`apps/core/models/Retention.py`): Workspace-level broad data retention policies and evidence logs built in Module 0.8.
  - `core.RegulatoryFramework` (`apps/core/models/Privacy.py:72`): Workspace-level regulatory regimes (GDPR, HIPAA, etc.) built in Module 0.8.
  - `core.ControlFramework` (`apps/core/models/Compliance.py`): Attestation frameworks (SOC 2, ISO 27001) built in Module 0.21.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:class AuditLog`): Immutable audit logging infrastructure.
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing concurrency-safe atomic sequential numbering (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DRTN` (`RetentionSchedule`): Verified free (0 matches across repo).
  - `DRCD` (`RecordDeclaration`): Verified free (0 matches across repo).
  - `DHLD` (`DocumentLegalHold`): Verified free (0 matches across repo).
  - `DDST` (`DestructionCertificate`): Verified free (0 matches across repo).
  - Note: `DISP` is used by `accounting.AssetDisposals`, `DSP` by `procurement.InvoiceDisputes`, and `RET` by `projects.SprintRetrospectives`. The chosen prefixes (`DRTN`, `DRCD`, `DHLD`, `DDST`) prevent all collisions.
  - All 33 existing prefixes in `apps/documents/` preserved cleanly: `DOC`, `DVER`, `DLOCK`, `DBRN`, `DTMPL`, `DSEC`, `DDFT`, `DCMT`, `DWF`, `DAPR`, `DSIG`, `DREV`, `DFLD`, `DSTG`, `DREL`, `DBLK`, `DSCH`, `DMETA`, `DTAX`, `DOCR`, `DSVD`, `DALT`, `DQRY`, `DSYN`, `DPRM`, `DWTR`, `DDRM`, `DDLP`, `DINC`, `DSHR`, `DCOA`, `DTSK`, `DACT`.

---

## Leaders surveyed (with source links)

1. **OpenText Records Management / Content Suite (OpenText Governance)** — The enterprise standard for electronic records management (ERM) in regulated industries and government agencies. Fully certified under DoD 5015.2 and compliant with ISO 15489. Employs a formal hierarchical File Plan with Record Series Identifiers (RSIs), automated document declaration rules that freeze records into immutable states, event-driven cutoff triggers (e.g. fiscal year close or contract expiry), multi-phase retention schedules, disposition search sweeps, defensible approval workflows, and automated Legal Hold freezing that halts disposition across all affected repositories.
   - *Source:* https://www.opentext.com/products/records-management · https://www.opentext.com/products/content-suite-platform
2. **Microsoft Purview Records Management** — Cloud-native records governance leader across Microsoft 365 environments. Implements a centralized File Plan manager with rich metadata descriptors (Business Function, Department, Legal Authority, Citation), retention labels enforcing time-based or event-based retention (e.g. employee resignation, contract conclusion), regulatory record declarations enforcing SEC 17a-4 / FINRA WORM compliance (immutable lockdown where even tenant administrators cannot delete content or shorten retention), multi-stage disposition reviews with up to 10 sequential approver groups, and proof of disposal audit logs.
   - *Source:* https://learn.microsoft.com/en-us/purview/records-management · https://learn.microsoft.com/en-us/purview/file-plan-manager
3. **Laserfiche Records Management** — DoD 5015.2 Certified (Chapters 2 and 4) electronic records management solution. Features transparent and automated records declaration directly within document repository trees, hierarchical file plan categorization, automated cutoff instructions (freezing files and starting the retention countdown at specific milestones like fiscal year end), lifecycle stage management (active, inactive/cutoff, disposition-eligible), legal holds with custodian assignment overriding disposition, and verifiable certificates of destruction.
   - *Source:* https://www.laserfiche.com/products/records-management/ · https://doc.laserfiche.com/laserfiche.documentation/en-us/Subsystems/RM/Content/Resources/CutoffInstructions.htm
4. **Box Governance** — Enterprise cloud content lifecycle and regulatory compliance module. Provides defensible retention schedules with two distinct enforcement models: Modifiable (allowing organizational schedule adjustments) and Non-Modifiable (strictly enforcing SEC 17a-4 / FINRA regulatory WORM requirements where retention periods cannot be shortened and documents cannot be removed). Supports event-based retention triggers, legal holds overriding retention schedules to prevent premature deletion during investigations, and defensible disposition reviews.
   - *Source:* https://www.box.com/governance · https://support.box.com/hc/en-us/articles/360043697414-Using-Retention-Policies
5. **Iron Mountain InSight & Policy Center** — Global leader in records management and information governance. Policy Center provides a continuous legal research database tracking statutory retention requirements across 130+ jurisdictions and industries. Delivers customizable records retention schedules (RRS) mapped to legal authorities, defensible disposition management with multi-tier sign-offs, and certified digital and physical destruction governance.
   - *Source:* https://www.ironmountain.com/services/policy-center · https://www.ironmountain.com/services/secure-shredding
6. **Alfresco Governance Services (Hyland AGS)** — DoD 5015.2 Certified (Chapters 2 & 3) open-source enterprise information governance engine. Implements file plan hierarchies (record categories and record folders), manual and rule-based record declaration, event-driven cutoffs, custom disposition schedules (review, transfer to archive, destroy), and legal freeze (hold) capability that prevents record modification or destruction across in-place enterprise repositories.
   - *Source:* https://www.hyland.com/en/products/alfresco-platform/governance-services · https://docs.alfresco.com/governance-services/latest/
7. **Hyland OnBase Records Management** — Widely adopted enterprise content governance suite for healthcare, government, and financial sectors. Features automated document declaration based on document type, event-driven retention triggers (claims settlement, policy termination), legal hold management that freezes disposition, multi-level destruction authorizations, and automated generation of destruction audit trails.
   - *Source:* https://www.hyland.com/en/products/onbase · https://www.hyland.com/en/solutions/compliance-governance
8. **Egnyte Governance & Compliance** — Cloud data security and lifecycle management platform tailored for life sciences and financial services. Provides data lifecycle policies with automated retention schedules, litigation hold preservation preventing file modification or trash purging, and out-of-the-box compliance framework mapping for GDPR (Article 5 storage limitations vs. Article 17 right to erasure), HIPAA (6-year retention), and SEC Rule 17a-4.
   - *Source:* https://www.egnyte.com/compliance-governance · https://helpdesk.egnyte.com/hc/en-us/articles/360032549211-Data-Lifecycle-Policies
9. **IBM Enterprise Records** — DoD 5015.2 certified electronic records management solution operating on FileNet Content Manager. Provides hierarchical file plans, automated declaration of content as records upon check-in or workflow completion, disposition sweeps evaluating cutoff criteria and retention periods, legal hold management with custodian association, and comprehensive disposal certificates.
   - *Source:* https://www.ibm.com/products/enterprise-records

---

## Feature catalog (this sub-module only)

### Records Classification & Retention
- **File Plan & Classification Taxonomy (`RetentionSchedule` - `DRTN`)** — Hierarchical record classification blueprint organizing documents into functional record categories and series codes (e.g. `CORP-LEGAL-01`, `FIN-TAX-07`, `HR-EMP-03`). Establishes standard classification labels, statutory retention periods, and disposition instructions across the tenant. · seen in: OpenText File Plan, Microsoft Purview File Plan Descriptors, Laserfiche, Alfresco AGS, IBM Enterprise Records · priority: **table-stakes** · spine: `RetentionSchedule` (`DRTN`), `core.Tenant`, `core.OrgUnit` · **buildable now**
- **Configurable Retention Duration & Time Units** — Defines mandatory retention spans in years, months, or days, or flags categories as `is_permanent` (vital historical records that must never be destroyed, such as corporate charters or board minutes). · seen in: Microsoft Purview, Box Governance, Laserfiche, OpenText · priority: **table-stakes** · spine: `RetentionSchedule.retention_period_years`, `RetentionSchedule.is_permanent` · **buildable now**
- **Lifecycle Trigger Types** — Establishes the starting event for retention calculation: `creation_date` (document created date), `last_modified` (latest revision timestamp), `event_based` (specific business milestone such as contract expiration, project close, or employee separation), or `declaration_date` (the moment the document was declared a formal record). · seen in: Microsoft Purview Event-Based Retention, OpenText RSI Triggers, Laserfiche, Box Governance · priority: **table-stakes** · spine: `RetentionSchedule.trigger_type` · **buildable now**
- **Cutoff Rules & Cutoff Frequency** — Implements the standard ISO 15489 / DoD 5015.2 cutoff mechanism that closes record folders and starts the retention countdown: `immediate` (starts immediately upon trigger event), `calendar_year_end` (end of December of trigger year), `fiscal_year_end` (end of organization's fiscal year), or `event_completion`. · seen in: Laserfiche Cutoff Instructions, OpenText RSIs, Alfresco AGS · priority: **table-stakes** · spine: `RetentionSchedule.cutoff_type` · **buildable now**
- **Retention Enforcement Modes (Modifiable vs. Regulatory WORM)** — Implements distinct governance postures: `modifiable` (standard internal corporate policy where retention rules can be adjusted by records managers) vs. `regulatory_worm` (strict compliance mode conforming to SEC Rule 17a-4 / FINRA WORM storage where retention periods cannot be shortened, declared records cannot be altered, and premature deletion is impossible). · seen in: Box Governance Non-Modifiable Policies, Microsoft Purview Regulatory Records, AWS S3 Object Lock Compliance Mode · priority: **differentiator** · spine: `RetentionSchedule.retention_mode` · **buildable now**
- **Statutory Authority & Legal Citation Reference** — Explicitly documents the legal, statutory, or regulatory basis underpinning the retention schedule (e.g. "IRS 26 CFR § 1.6001-1; Sarbanes-Oxley § 802; HIPAA 45 CFR § 164.316"). Provides defensible justification during regulatory inspections and legal audits. · seen in: Iron Mountain Policy Center Global Citations, Microsoft Purview File Plan Descriptors, Laserfiche · priority: **table-stakes** · spine: `RetentionSchedule.legal_citation` · **buildable now**

### Records Declaration & Filing
- **Official Record Declaration (`RecordDeclaration` - `DRCD`)** — Designates a `Document` (and optionally a specific immutable `DocumentVersion`) as an official enterprise record. Locks the document against further content editing, branch creation, or check-out, ensuring tamper-proof evidential integrity. · seen in: OpenText Records Declaration, Alfresco AGS, Laserfiche, Microsoft Purview Record Labels, IBM Enterprise Records · priority: **table-stakes** · spine: `RecordDeclaration` (`DRCD`), `documents.Document`, `documents.DocumentVersion`, `accounts.User` · **buildable now**
- **Declaration Triggers & Modes** — Supports declaration via three pathways: `manual` (explicit user or records manager action), `automatic_rule` (ingestion rule based on folder or metadata classification), or `workflow_trigger` (post-approval workflow transition). · seen in: OpenText, Alfresco AGS, Hyland OnBase, Microsoft Purview Auto-Apply · priority: **table-stakes** · spine: `RecordDeclaration.declaration_type` · **buildable now**
- **File Plan Assignment & Record Identifier** — Binds the declared record to its governing `RetentionSchedule` and assigns a unique tenant-scoped record identifier (`DRCD-XXXXXX`), preserving the file plan taxonomy code and classification metadata. · seen in: OpenText RSI Binding, Laserfiche File Plan, IBM Enterprise Records · priority: **table-stakes** · spine: `RecordDeclaration.retention_schedule` · **buildable now**
- **Vital Records Designation** — Boolean indicator (`is_vital_record`) identifying mission-critical records essential for emergency operational continuity, disaster recovery, or organizational legal defense (conforming to ISO 15489-1 vital records requirements). · seen in: DoD 5015.2 Chapter 2, Laserfiche Vital Records, OpenText · priority: **common** · spine: `RecordDeclaration.is_vital_record` · **buildable now**
- **Cutoff Status & Tracking** — Tracks the record's cutoff lifecycle state: `active` (open, accumulating, retention clock not yet ticking), `cutoff_met` (cutoff milestone reached, retention clock running), `disposition_pending` (retention period elapsed, queued for disposal review), or `disposed` / `archived`. Records `cutoff_date` and calculates `disposition_due_date`. · seen in: DoD 5015.2, Laserfiche Life-Cycle Timeline, OpenText · priority: **table-stakes** · spine: `RecordDeclaration.record_status`, `RecordDeclaration.cutoff_date`, `RecordDeclaration.disposition_due_date` · **buildable now**
- **WORM Tamper-Resistance Lock** — Enforces programmatic write-once-read-many protection: updates `Document.is_locked=True` and prevents new version uploads, deletion requests, or permission downgrades while the document remains an active declared record. · seen in: SEC 17a-4, DoD 5015.2, Box Governance, Purview Regulatory Records · priority: **table-stakes** · spine: `RecordDeclaration.is_locked`, `Document` · **buildable now**

### Legal Hold & eDiscovery
- **Litigation Hold Placement (`DocumentLegalHold` - `DHLD`)** — Places a formal preservation order on specific documents, declared records, or entire folders when legal action, audit, or regulatory inquiry is anticipated (*Zubulake v. UBS Warburg* doctrine). Freezes the document in place and prevents any modification, versioning, or deletion. · seen in: Microsoft Purview eDiscovery Legal Hold, OpenText Legal Hold, Box Legal Holds, Laserfiche · priority: **table-stakes** · spine: `DocumentLegalHold` (`DHLD`), `documents.Document`, `RecordDeclaration`, `accounts.User` · **buildable now**
- **Retention Suspension & Disposition Override** — Fundamental records management invariant: **an active legal hold strictly overrides all retention schedules and disposition rules**. A document whose retention schedule has expired MUST NOT be destroyed, purged, or disposed of while any active legal hold covers it. · seen in: All surveyed products (OpenText, Purview, Box, Laserfiche, Alfresco, Hyland, IBM) · priority: **table-stakes** · spine: `DocumentLegalHold.is_active`, validation hook in disposition execution · **buildable now**
- **Enterprise Legal Hold Integration (`core.LegalHold`)** — Provides optional cross-linking to Module 0.16's system-wide `core.LegalHold` (`apps/core/models/LegalHold.py`), allowing document-level holds to participate in broader enterprise litigation matters while maintaining document-specific custodian and scope details. · seen in: NavERP Core Spine Integration · priority: **table-stakes** · spine: `DocumentLegalHold.core_legal_hold` (FK to `core.LegalHold`) · **buildable now**
- **Matter Tracking & Case Reference** — Records case metadata including `matter_number` (e.g. `LIT-2026-0042`), `hold_reason` (`litigation`, `regulatory_audit`, `tax_investigation`, `internal_inquiry`), issuing authority/counsel, and detailed scope instructions. · seen in: Microsoft Purview, OpenText Legal Hold, Box Governance · priority: **table-stakes** · spine: `DocumentLegalHold.matter_number`, `DocumentLegalHold.hold_reason` · **buildable now**
- **Custodian Scoping & Tracking** — Records the designated custodian responsible for the preserved documents, supporting both named internal users (`accounts.User`) and organizational units (`core.OrgUnit`) or external parties (`core.Party`). · seen in: Microsoft Purview Custodian Management, OpenText Legal Hold, Iron Mountain · priority: **table-stakes** · spine: `DocumentLegalHold.custodian_user`, `DocumentLegalHold.custodian_name` · **buildable now**
- **Defensible Hold Release Workflow** — Ensures strict auditability when lifting a preservation order: requires authorized legal user, records `released_at` timestamp, and mandates a written `release_reason` explaining why the hold is no longer legally required, resuming standard retention counting. · seen in: OpenText Legal Hold Release, Purview, Laserfiche · priority: **table-stakes** · spine: `DocumentLegalHold.released_at`, `DocumentLegalHold.released_by`, `DocumentLegalHold.release_reason` · **buildable now**

### Disposition & Destruction
- **Defensible Disposition Review Board** — Interactive management board filtering records that have reached `disposition_due_date` where no active legal holds exist. Allows records managers and department stakeholders to evaluate eligible records and make formal disposition decisions. · seen in: Microsoft Purview Disposition Reviews, OpenText Disposition Search, Laserfiche Disposition Folders, Box Governance · priority: **table-stakes** · spine: Filtered view over `RecordDeclaration`, `DocumentLegalHold`, `RetentionSchedule` · **buildable now**
- **Multi-Stage Disposition Approval (`DestructionCertificate` - `DDST`)** — Creates a formal disposition authorization request requiring review and electronic sign-off by designated records managers before any file deletion or archive transfer occurs. Captures approval request timestamp, designated approver, approval decision (`approved`, `rejected`), and rejection justification. · seen in: Microsoft Purview Multi-Stage Review, OpenText Disposition Approvals, Hyland OnBase · priority: **table-stakes** · spine: `DestructionCertificate` (`DDST`), `accounts.User` · **buildable now**
- **Destruction Execution & Methods** — Supports four disposition actions upon approval: `secure_destruction` (electronic database and file record purge), `physical_shredding` (for paper/hybrid media tracking with certified physical shredding standards), `archival_transfer` (transfer of permanent historical records to national or corporate archives), and `de_identification` (anonymization of PII). · seen in: DoD 5015.2 Disposal Methods, Laserfiche, Iron Mountain Secure Shredding, OpenText · priority: **table-stakes** · spine: `DestructionCertificate.disposition_type`, `DestructionCertificate.destruction_method` · **buildable now**
- **Cryptographic Verification Hash (Proof of Disposal)** — Prior to executing destruction, captures and permanently archives the cryptographic SHA-256 hash digest of the document content alongside metadata snapshots (document title, number, file plan code, classification, author). Proves what exact digital artifact was destroyed without retaining sensitive content. · seen in: DoD 5015.2 Destruction Verification, Microsoft Purview Proof of Disposal, OpenText · priority: **differentiator** · spine: `DestructionCertificate.verification_hash`, `DestructionCertificate.document_title_snapshot` · **buildable now**
- **Legal Hold Pre-Destruction Clearance Check** — Automated defensive barrier: executing destruction requires strict system verification that zero active legal holds exist on the document (`legal_hold_verified_clear=True`). If an active hold is detected, destruction is programmatically blocked with an integrity exception. · seen in: Box Governance, Microsoft Purview, OpenText, Laserfiche · priority: **table-stakes** · spine: `DestructionCertificate.clean()`, `DocumentLegalHold` lookup · **buildable now**
- **Permanent Certificate of Destruction (Chain of Custody)** — Immutable certificate record that permanently survives the deletion of the underlying document. Documents the certificate number (`DDST-XXXXXX`), destruction timestamp, approving officer, executing officer, destruction method, regulatory citation, and cryptographic verification hash for external regulatory auditors. · seen in: DoD 5015.2, Iron Mountain Certificates of Destruction, Laserfiche, Purview · priority: **table-stakes** · spine: `DestructionCertificate` (`DDST`) · **buildable now**

### Compliance Framework Mapping
- **Regulatory Framework Alignment** — Tags retention schedules and destruction certificates with targeted compliance regimes: `iso_15489` (Information and documentation — Records management), `dod_5015_2` (DoD Electronic Records Management Software Criteria), `sec_17a_4` (Securities and Exchange Commission broker-dealer electronic records WORM mandate), `gdpr` (EU GDPR Article 5(1)(e) storage limitation and Article 17 right to erasure), `hipaa` (Health Insurance Portability and Accountability Act 6-year retention), or `irs_tax` (Internal Revenue Code tax retention). · seen in: Iron Mountain Policy Center, Egnyte Governance, Microsoft Purview, Box Governance · priority: **table-stakes** · spine: `RetentionSchedule.compliance_framework`, `core.RegulatoryFramework` cross-reference · **buildable now**
- **GDPR Storage Limitation vs. Legal Obligation Handling** — Provides structured compliance rationale when balancing GDPR Art. 17 right to erasure against Art. 17(3)(b) legal retention obligations: documents whether a record is retained under statutory mandate overriding customer erasure requests until retention expiration. · seen in: Egnyte GDPR Lifecycle Policies, Iron Mountain, Microsoft Purview · priority: **common** · spine: `RetentionSchedule.legal_citation`, `RecordDeclaration.notes` · **buildable now**

### Beyond the Bullets
- **Defensible Disposal Auditability** — Architectural separation between active records and the destruction certificate log: while document content and metadata rows are permanently deleted upon destruction, the `DestructionCertificate` row is immutable and never deleted, providing an unalterable defense against allegations of improper document spoliation. · seen in: OpenText, Purview, Laserfiche · priority: **table-stakes** · spine: `DestructionCertificate` · **buildable now**
- **Vital Records Disaster Recovery Register** — Dedicated reporting view filtering all active records flagged `is_vital_record=True`, enabling risk officers and emergency response planners to audit essential records inventories required for disaster recovery and operational continuity. · seen in: DoD 5015.2 Chapter 2, Laserfiche Vital Records Management · priority: **common** · spine: Filtered view over `RecordDeclaration` · **buildable now**

---

## Recommended build scope (this pass — 1–4 models)

To fully deliver the 5 feature bullets of Sub-module 13.9 while strictly adhering to NavERP's modular architecture (1–4 tenant-scoped models inheriting `TenantNumbered`), we recommend the following 4 models located in `apps/documents/models/RecordsCompliance/`:

### 1. `RetentionSchedule` (`DRTN`)
*File plan classification and retention rule master.*
- **Prefix:** `NUMBER_PREFIX = "DRTN"` (e.g. `DRTN-000001`)
- **Justified by features:** File Plan & Classification Taxonomy, Configurable Retention Duration, Lifecycle Trigger Types, Cutoff Rules, Retention Enforcement Modes (Modifiable vs. Regulatory WORM), Compliance Framework Alignment, Statutory Legal Citation.
- **Key Fields:**
  - `tenant` (FK to `core.Tenant`, CASCADE)
  - `number` (CharField 32, editable=False, unique sequence)
  - `name` (CharField 150, e.g. "Corporate Commercial Contracts Retention Schedule")
  - `file_plan_code` (CharField 64, db_index=True, e.g. "LEGAL-CONT-01")
  - `description` (TextField, blank=True)
  - `retention_period_years` (PositiveIntegerField, default=7)
  - `retention_period_months` (PositiveIntegerField, default=0)
  - `is_permanent` (BooleanField, default=False, indicates historical permanent archive)
  - `trigger_type` (CharField 24, choices: `creation_date`, `last_modified`, `event_based`, `declaration_date`, default=`creation_date`)
  - `cutoff_type` (CharField 24, choices: `immediate`, `calendar_year_end`, `fiscal_year_end`, `event_completion`, default=`calendar_year_end`)
  - `disposition_action` (CharField 24, choices: `destroy`, `permanent_archive`, `review`, `transfer`, default=`review`)
  - `retention_mode` (CharField 20, choices: `modifiable`, `regulatory_worm`, default=`modifiable`)
  - `compliance_framework` (CharField 24, choices: `iso_15489`, `dod_5015_2`, `sec_17a_4`, `gdpr`, `hipaa`, `irs_tax`, `custom`, default=`iso_15489`)
  - `legal_citation` (CharField 255, blank=True, e.g. "IRS 26 CFR § 1.6001-1; Sarbanes-Oxley § 802")
  - `owner_org_unit` (FK to `core.OrgUnit`, SET_NULL, null=True, blank=True)
  - `is_active` (BooleanField, default=True)
  - `created_by` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True)
  - `created_at`, `updated_at` (DateTimeFields)
- **Verified FKs:** `core.Tenant`, `core.OrgUnit`, `accounts.User`.

### 2. `RecordDeclaration` (`DRCD`)
*Official declaration linking a Document to a RetentionSchedule, locking it as an immutable record.*
- **Prefix:** `NUMBER_PREFIX = "DRCD"` (e.g. `DRCD-000001`)
- **Justified by features:** Official Record Declaration, Declaration Triggers, File Plan Assignment, Vital Records Designation, Cutoff Status & Tracking, WORM Tamper-Resistance Lock.
- **Key Fields:**
  - `tenant` (FK to `core.Tenant`, CASCADE)
  - `number` (CharField 32, editable=False, unique sequence)
  - `document` (FK to `documents.Document`, CASCADE, related_name="record_declarations")
  - `version` (FK to `documents.DocumentVersion`, SET_NULL, null=True, blank=True, related_name="record_declarations")
  - `retention_schedule` (FK to `RetentionSchedule`, PROTECT, related_name="declared_records")
  - `declaration_type` (CharField 20, choices: `manual`, `automatic_rule`, `workflow_trigger`, default=`manual`)
  - `declared_by` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True)
  - `declared_at` (DateTimeField, default=timezone.now)
  - `record_status` (CharField 24, choices: `active`, `cutoff_met`, `disposition_pending`, `disposed`, `archived`, default=`active`)
  - `is_vital_record` (BooleanField, default=False)
  - `is_locked` (BooleanField, default=True, programmatically syncs with `Document.is_locked`)
  - `cutoff_date` (DateField, null=True, blank=True)
  - `disposition_due_date` (DateField, null=True, blank=True)
  - `notes` (TextField, blank=True)
  - `created_at`, `updated_at` (DateTimeFields)
- **Verified FKs:** `core.Tenant`, `documents.Document`, `documents.DocumentVersion`, `RetentionSchedule`, `accounts.User`.

### 3. `DocumentLegalHold` (`DHLD`)
*Litigation hold and regulatory preservation order placed on documents/records, freezing disposition.*
- **Prefix:** `NUMBER_PREFIX = "DHLD"` (e.g. `DHLD-000001`)
- **Justified by features:** Litigation Hold Placement, Retention Suspension & Disposition Override, Enterprise Legal Hold Integration (`core.LegalHold`), Matter Tracking, Custodian Scoping, Defensible Hold Release Workflow.
- **Key Fields:**
  - `tenant` (FK to `core.Tenant`, CASCADE)
  - `number` (CharField 32, editable=False, unique sequence)
  - `document` (FK to `documents.Document`, CASCADE, related_name="legal_holds")
  - `record_declaration` (FK to `RecordDeclaration`, SET_NULL, null=True, blank=True, related_name="legal_holds")
  - `core_legal_hold` (FK to `core.LegalHold`, SET_NULL, null=True, blank=True, related_name="document_holds", help_text="Optional cross-link to 0.16 enterprise preservation order")
  - `matter_number` (CharField 100, db_index=True, e.g. "LIT-2026-0042")
  - `title` (CharField 150)
  - `hold_reason` (CharField 24, choices: `litigation`, `regulatory_audit`, `tax_investigation`, `internal_inquiry`, default=`litigation`)
  - `scope_description` (TextField, blank=True)
  - `custodian_name` (CharField 200, blank=True)
  - `custodian_user` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True, related_name="custodian_legal_holds")
  - `custodian_acknowledged` (BooleanField, default=False)
  - `custodian_acknowledged_at` (DateTimeField, null=True, blank=True)
  - `is_active` (BooleanField, default=True)
  - `placed_by` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True, related_name="placed_document_holds")
  - `placed_at` (DateTimeField, default=timezone.now)
  - `released_by` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True, related_name="released_document_holds")
  - `released_at` (DateTimeField, null=True, blank=True)
  - `release_reason` (CharField 255, blank=True)
  - `notes` (TextField, blank=True)
  - `created_at`, `updated_at` (DateTimeFields)
- **Verified FKs:** `core.Tenant`, `documents.Document`, `RecordDeclaration`, `core.LegalHold`, `accounts.User`.

### 4. `DestructionCertificate` (`DDST`)
*Certificate of Destruction and Defensible Disposition record.*
- **Prefix:** `NUMBER_PREFIX = "DDST"` (e.g. `DDST-000001`)
- **Justified by features:** Defensible Disposition Review Board, Multi-Stage Disposition Approval, Destruction Execution & Methods, Cryptographic Verification Hash (Proof of Disposal), Legal Hold Pre-Destruction Clearance Check, Permanent Certificate of Destruction (Chain of Custody).
- **Key Fields:**
  - `tenant` (FK to `core.Tenant`, CASCADE)
  - `number` (CharField 32, editable=False, unique sequence)
  - `record_declaration` (FK to `RecordDeclaration`, SET_NULL, null=True, blank=True, related_name="destruction_certificates")
  - `document_title_snapshot` (CharField 255, preserves title after document deletion)
  - `document_number_snapshot` (CharField 64, preserves DOC-XXXXXX number)
  - `file_plan_code_snapshot` (CharField 64, preserves file plan code)
  - `disposition_type` (CharField 24, choices: `secure_destruction`, `physical_shredding`, `archival_transfer`, `de_identification`, default=`secure_destruction`)
  - `status` (CharField 20, choices: `draft`, `pending_approval`, `approved`, `executed`, `rejected`, default=`pending_approval`)
  - `approval_requested_at` (DateTimeField, default=timezone.now)
  - `approved_by` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True, related_name="approved_destruction_certificates")
  - `approved_at` (DateTimeField, null=True, blank=True)
  - `rejection_reason` (CharField 255, blank=True)
  - `executed_by` (FK to `settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True, related_name="executed_destruction_certificates")
  - `executed_at` (DateTimeField, null=True, blank=True)
  - `destruction_method` (CharField 24, choices: `cryptographic_erase`, `dod_5220_22m`, `database_purge`, `physical_crosscut`, `nara_transfer`, default=`database_purge`)
  - `verification_hash` (CharField 64, blank=True, help_text="SHA-256 content digest snapshot verifying destroyed item")
  - `legal_hold_verified_clear` (BooleanField, default=False, affirmative check that no active holds exist)
  - `notes` (TextField, blank=True)
  - `created_at`, `updated_at` (DateTimeFields)
- **Verified FKs:** `core.Tenant`, `RecordDeclaration`, `accounts.User`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **System-wide Immutable Activity Logs & User Behavior Analytics** → Parked for **13.10 Audit Trail & Reporting**. (13.9 captures disposition certificates and declaration events; system event ingestion and analytics belong to 13.10).
- **Long-term Preservation Formats (PDF/A, TIFF), Bit-rot Integrity Sweeps & Cold Tier Archiving** → Parked for **13.14 Document Archival & Long-Term Preservation**. (13.9 determines retention schedule expiry and triggers the archive transfer action; media transcoding and archival storage volume migration belong to 13.14).
- **Electronic Form Submissions & Data Capture Retention** → Parked for **13.15 Electronic Forms & Data Capture**.
- **Contract Milestone-Based Retention Triggers (Execution, Expiration, Renewal)** → Parked for **13.16 Contract Lifecycle Management (CLM)**.

---

## Deferred (later passes / integrations)

- **Automated Background Scheduler / Daemon Worker** — NavERP operates as a synchronous single-process web application without a daemon background runner (see 0.8/0.16 precedent). Automated cron-based deletion is deferred; disposition is managed through the interactive Disposition Review Board and authorized manually by records managers.
- **External eDiscovery EDRM / Relativity Export** — Direct API integration with commercial legal review platforms (Relativity, Disco, Exterro) deferred; legal hold and record metadata can be exported via CSV/JSON.
- **Physical Warehouse Barcode & RFID Box Tracking** — Physical box location tracking for off-site paper archives (e.g. Iron Mountain physical depot integration) deferred to physical records management extension.
- **Machine Learning Auto-Classification Engine** — Automated ML classification of unstructured documents into file plan categories deferred; classification uses rule-based matching and folder defaults.
