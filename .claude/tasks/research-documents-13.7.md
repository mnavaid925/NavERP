# Research — Sub-module 13.7: Document Security & Access Control (Module 13 — Document Management System, documents)

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

- **Sibling models available to FK in `apps/documents/` (verified via repo audit):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Core logical document master containing title, slug, classification (`public`, `internal`, `confidential`, `restricted`), document_type, status, owner, department, tags, version tracking.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Immutable physical file revision snapshot with `extracted_text`, file payload, hash, size, and MIME type.
  - `documents.DocumentFolder` (`apps/documents/models/StorageRepository/DocumentFolders.py:9`, `NUMBER_PREFIX = "DFLD"`): Hierarchical folder repository tree with `path`, `default_classification`, and `default_document_type`.
  - `documents.MetadataSchema` (`apps/documents/models/MetadataIndexing/MetadataSchemas.py:14`, `NUMBER_PREFIX = "DSCH"`): Custom metadata schema definitions.
  - `documents.DocumentMetadataValue` (`apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:14`, `NUMBER_PREFIX = "DMETA"`): Document instance metadata stored in `values_json`.
  - `documents.TaxonomyTerm` (`apps/documents/models/MetadataIndexing/TaxonomyTerms.py:14`, `NUMBER_PREFIX = "DTAX"`): Controlled vocabulary with `vocabulary_name`, `term_code`, `label`.
  - `documents.DocumentOcrJob` (`apps/documents/models/MetadataIndexing/DocumentOcrJobs.py:14`, `NUMBER_PREFIX = "DOCR"`): OCR text extraction and AI tagging jobs.
  - `documents.DocumentSavedSearch` (`apps/documents/models/SearchDiscovery/DocumentSavedSearches.py:14`, `NUMBER_PREFIX = "DSVD"`): User-defined search criteria and saved views.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): System users, document owners, permission grantees, reviewers, auditors.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Organizational units for department-level permission grants, watermark policies, and DLP scope exclusions.
  - `core.Party` & `core.PartyRole` (`apps/core/models/Party.py`, `PartyRole.py`): External third-party actors (contractors, vendors, clients).
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing atomic concurrency-safe sequential number generation (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DPRM` (`DocumentAccessPermission`): Verified free (0 matches in repo).
  - `DWTR` (`WatermarkPolicy`): Verified free (0 matches in repo).
  - `DDRM` (`DocumentDrmPolicy`): Verified free (0 matches in repo).
  - `DDLP` (`DlpPolicy`): Verified free (0 matches in repo).
  - `DINC` (`DlpIncident`): Verified free (0 matches in repo).
  - All existing prefixes in `apps/documents/` preserved without collision: `DOC`, `DVER`, `DLOCK`, `DBRN`, `DTMPL`, `DSEC`, `DDFT`, `DCMT`, `DWF`, `DAPR`, `DSIG`, `DREV`, `DFLD`, `DSTG`, `DREL`, `DBLK`, `DSCH`, `DMETA`, `DTAX`, `DOCR`, `DSVD`, `DALT`, `DSYN`, `DQRY`.

---

## Leaders surveyed (with source links)

1. **Box Shield (Smart Access, Classification & Watermarking, Threat Detection)** — Enterprise cloud content governance benchmark. Features contextual "Smart Access" policies based on classification labels, user geographical location, network IP domain, and device security posture. Provides automated classification rules that apply sensitivity badges (`Confidential`, `Restricted`, `PII`, `Internal`), dynamic on-the-fly watermarking injecting the viewer's username, email, IP address, and timestamp across previews and authorized downloads, and machine-learning threat detection detecting anomalous mass downloads or impossible travel exfiltration attempts.
   - *Source:* https://www.box.com/shield · https://support.box.com/hc/en-us/articles/360043697474-Using-Box-Shield-Smart-Access-Policies
2. **Microsoft Purview Information Protection (Sensitivity Labels, Azure Rights Management DRM, DLP)** — The de facto enterprise standard across Fortune 500 organizations. Combines Sensitivity Labels with Azure Rights Management Service (RMS) cryptographic enforcement. Enforces granular capability permissions (VIEW, EDIT, PRINT, EXTRACT/COPY, FORWARD, EXPORT), dynamic visual markings (header, footer, and diagonal body watermarks dynamically populated with user identity and classification variables), and Purview Data Loss Prevention (DLP) engines that inspect content against hundreds of prebuilt sensitive information types (PCI-DSS credit cards, SSNs, SWIFT codes, medical record numbers) and enforce block, warn, or quarantine actions.
   - *Source:* https://learn.microsoft.com/en-us/purview/information-protection · https://learn.microsoft.com/en-us/purview/dlp-learn-about-dlp
3. **OpenText Documentum Content Security / OpenText Core Trust & Security** — Premier high-assurance ECM for heavily regulated industries (defense, life sciences, banking). Implements multi-tier Access Control Lists (ACLs) supporting basic permissions (Browse, Read, Relate, Version, Write, Delete) and extended administrative rights (Change Folder Links, Change Ownership, Change State, Change Permission) with explicit inheritance hierarchies. Incorporates Documentum Stamping Server / Dynamic Watermarking injecting controlled copy metadata on rendition requests and Trusted Content Services (TCS) providing FIPS 140-2 cryptographic repository protection.
   - *Source:* https://www.opentext.com/products/documentum-server · https://www.opentext.com/products/core-share
4. **Egnyte Secure Enclaves & Data Governance (DLP, permission auditing, link controls)** — Renowned hybrid cloud ECM and content intelligence platform. Implements "Secure Enclaves" — restricted virtual project spaces where sensitive documents cannot be downloaded, synced, or copied outside the enclave boundary. Employs comprehensive permission auditing detecting stale permissions, circular group memberships, and overprivileged accounts. Includes sensitive content discovery detecting PII, HIPAA, and financial data with risk scoring and a secure web viewer disabling browser printing and clipboard context menus.
   - *Source:* https://www.egnyte.com/solutions/data-governance · https://www.egnyte.com/product/content-intelligence
5. **Adobe Document Cloud / Acrobat Security & Adobe Experience Manager DRM** — Industry pioneer in portable document security and digital rights management. Uses Adobe Rights Management Server (LiveCycle / AEM Forms Security) to issue encrypted, policy-protected documents. Enforces fine-grained rights: high vs. low resolution printing, text and image extraction prevention, screen reader accessibility toggles, form filling limits, and remote document revocation (instant remote kill switch rendering distributed PDFs unreadable even if stored on offline endpoints). Dynamically generates print and display watermarks based on server variables.
   - *Source:* https://helpx.adobe.com/acrobat/using/securing-pdfs-passwords.html · https://experienceleague.adobe.com/docs/experience-manager-65/forms/document-security/admin-help/creating-managing-policies.html
6. **Kiteworks Private Content Network (DRM, DRM viewer, zero trust content control)** — Zero Trust content protection platform certified for FedRAMP, DoD, and enterprise compliance. Features Kiteworks SafeViewer with zero-download browser viewing, dynamic anti-leak multi-line watermarking, anti-screen capture distortion overlays, time-bombed expiration, and geographical/IP geofencing. Incorporates continuous content policy inspection, anti-malware sandboxing, and automated DLP quarantine for outbound and internal document movements.
   - *Source:* https://www.kiteworks.com/platform/digital-rights-management/ · https://www.kiteworks.com/platform/safeviewer/
7. **Fasoo Enterprise DRM (FED) / Fortra Vera (dynamic watermarking, screen capture protection, print control)** — Specialized market leaders in persistent data-centric security. Protects files persistently throughout their entire lifecycle regardless of where they are copied or stored. Enforces screen capture protection (blocking PrintScreen, Windows Snipping Tool, and web conference screen captures), visible dynamic forensic watermarks (user ID, IP, date/time) combined with invisible steganographic micro-dot fingerprinting, print controls limiting print count and disabling virtual print-to-PDF drivers, and retroactive access revocation.
   - *Source:* https://en.fasoo.com/products/fasoo-enterprise-drm/ · https://www.fortra.com/products/vera-digital-rights-management
8. **Virtru Data Protection (Open TDF / Trusted Data Format & Client-Side Encryption)** — Innovator in zero-knowledge client-side encryption based on the open-standard Trusted Data Format (Open TDF). Enables granular attribute-based access control (ABAC), instant revocation of accessed content, persistent PDF/file watermarking, expiration deadlines, and real-time audit event logging tracing exactly who accessed or attempted to decrypt sensitive records.
   - *Source:* https://www.virtru.com/data-protection/ · https://www.opentdf.io/

---

## Feature catalog (this sub-module only)

### Document-Level Permissions
- **Granular Multi-Tier Access Control Lists (ACLs) (`DocumentAccessPermission` - `DPRM`)** — Fine-grained capability matrix assigning explicit permissions per document or folder to specific principals (individual `User`, organizational unit `core.OrgUnit`, or standardized role `role_name`). Governs discrete capabilities: `can_read`, `can_write`, `can_delete`, `can_download`, `can_print`, and `can_share`. · seen in: OpenText Documentum ACLs, Box Smart Access, Microsoft Purview · priority: **table-stakes** · spine: `DocumentAccessPermission` (`DPRM`), `Document`, `DocumentFolder`, `User`, `OrgUnit` · **buildable now**
- **Hierarchical Permission Inheritance & Break-Inheritance** — Documents automatically inherit access permissions defined on their parent `DocumentFolder`. Repository administrators can explicitly break inheritance on sensitive subfolders or documents, replacing inherited ACLs with custom document-specific rules or pruning inherited groups. · seen in: OpenText Documentum, SharePoint Folder Inheritance, Egnyte Permissions · priority: **table-stakes** · spine: `DocumentAccessPermission.is_inherited`, `DocumentAccessPermission.inherited_from_folder` · **buildable now**
- **Effective Permissions Calculator & Simulator** — Interactive analytical calculation engine that evaluates all active permission paths (direct user grants + department/OrgUnit memberships + role assignments - DRM policy restrictions - temporary expiration) to compute a user's net effective capabilities on a target document. · seen in: Egnyte Permission Analyzer, SharePoint Effective Access, OpenText · priority: **table-stakes** · spine: Deterministic capability resolver service and UI badge display · **buildable now**
- **Time-Bounded & Ephemeral Access Grants** — Enforces validity window bounds (`valid_from` and `valid_until`) on permission grants. Automatically expires access for external contractors, auditors, or temporary project staff without requiring manual administrative cleanup. · seen in: Box Expiring Access, Virtru Ephemeral Access, Kiteworks · priority: **table-stakes** · spine: `DocumentAccessPermission.valid_from`, `valid_until`, `is_active` · **buildable now**
- **Access Telemetry & Stale Permission Tracking** — Automatically increments `access_count` and updates `last_accessed_at` whenever a principal interacts with a document. Surfaces dormant access grants (>90 days unaccessed) to support least-privilege compliance audits. · seen in: Egnyte Permission Auditing, Box Shield Stale Access · priority: **common** · spine: `DocumentAccessPermission.access_count`, `last_accessed_at` · **buildable now**
- **Role-Based Permission Templates / Bundles** — Predefined standard capability tiers (`viewer`: read-only; `commenter`: read + comment; `editor`: read + write + download; `manager`: editor + delete + share; `owner`: full control) allowing single-click permission assignment while preserving custom granular override toggles. · seen in: Box Access Roles, Google Workspace Sharing, Microsoft Purview · priority: **table-stakes** · spine: `DocumentAccessPermission.permission_level` choices · **buildable now**

### Dynamic Watermarking
- **Classification-Driven Dynamic Watermarking Policies (`WatermarkPolicy` - `DWTR`)** — Centralized policy engine applying dynamic visual watermarks to document previews, downloads, and print renditions based on document classification level (`confidential`, `restricted`), document type (`contract`, `sop`), or owning department. · seen in: Box Shield Dynamic Watermarking, Microsoft Purview Visual Markings, Kiteworks · priority: **table-stakes** · spine: `WatermarkPolicy` (`DWTR`), `Document.classification`, `Document.document_type` · **buildable now**
- **Dynamic Variable & Token Interpolation Engine** — Template string parser supporting variable injection into watermark text: `{{user_name}}`, `{{user_email}}`, `{{ip_address}}`, `{{timestamp}}`, `{{classification}}`, `{{document_number}}`, `{{tenant_name}}`. Produces personalized forensic watermarks deterring unauthorized photographic or physical leakage. · seen in: Fasoo Enterprise DRM, Box Shield, Adobe Experience Manager · priority: **table-stakes** · spine: `WatermarkPolicy.watermark_text` token evaluator · **buildable now**
- **Visual Staging, Opacity & Layout Controls** — Configurable layout parameters: watermark position (`diagonal_center`, `center`, `header_banner`, `footer_banner`, `tiled_grid`), rotation angle (-90° to +90°), opacity percentage (1% to 100%), font size (pt), and font color (HEX). · seen in: Adobe Acrobat Watermark Engine, Fasoo DRM, OpenText Stamping Server · priority: **table-stakes** · spine: `WatermarkPolicy.position`, `opacity_percent`, `rotation_angle`, `font_color` · **buildable now**
- **Classification Banners & Header/Footer Guardrails** — Displays prominent color-coded classification banners across the top and/or bottom margins of documents (e.g. bold red banner for `RESTRICTED`, amber for `CONFIDENTIAL`, green for `PUBLIC`), clearly signaling handling sensitivity. · seen in: Microsoft Purview Classification Headers, Kiteworks Security Banners · priority: **table-stakes** · spine: `WatermarkPolicy.show_classification_banner`, `banner_position` · **buildable now**
- **Contextual Enforcement Gates** — Configurable policy toggles specifying whether watermarks are enforced on interactive browser view (`enforce_on_view`), physical PDF file download (`enforce_on_download`), or hardcopy print renditions (`enforce_on_print`). · seen in: Box Shield, Kiteworks SafeViewer · priority: **table-stakes** · spine: `WatermarkPolicy.enforce_on_view`, `enforce_on_download`, `enforce_on_print` · **buildable now**
- **Interactive Live Watermark Visualizer Preview** — Administrative design workbench featuring a real-time sample document preview rendering the watermark with current opacity, rotation, and interpolated sample tokens before policy deployment. · seen in: Adobe Acrobat Previewer, Microsoft Purview Design Studio · priority: **common** · spine: Interactive Tailwind/Canvas watermark preview widget · **buildable now**

### DRM & Document Protection
- **Document Digital Rights Management Policies (`DocumentDrmPolicy` - `DDRM`)** — Cryptographic and client-level policy definitions binding persistent protection rules to sensitive document types, classification levels, or specific critical document instances. · seen in: Microsoft Purview Rights Management, Adobe DRM, Fasoo Enterprise DRM · priority: **table-stakes** · spine: `DocumentDrmPolicy` (`DDRM`), `Document` · **buildable now**
- **Zero-Download Secure Web Viewer Enforcement** — Mandates that designated high-sensitivity documents cannot be downloaded as raw local files (`allow_download=False`). Renders documents strictly within a sandboxed browser viewer using paginated SVG/canvas elements without exposing raw binary URLs. · seen in: Kiteworks SafeViewer, Egnyte Secure Enclaves, Virtru Web Viewer · priority: **table-stakes** · spine: `DocumentDrmPolicy.allow_download`, `DocumentDrmPolicy.secure_viewer_required` · **buildable now**
- **Clipboard & Copy/Paste Prevention** — Disables text selection (`user-select: none`), right-click context menus (`contextmenu` event blocking), and clipboard copy commands (`copy`, `cut` interceptors) inside the secure viewer to block trivial exfiltration of confidential prose. · seen in: Adobe Acrobat DRM, Kiteworks SafeViewer, Fasoo DRM · priority: **table-stakes** · spine: `DocumentDrmPolicy.allow_copy_paste`, secure viewer DOM guards · **buildable now**
- **Screen Shield & Anti-Screen Capture Defense** — Implements client-side screen protection that blurs viewer canvas contents whenever browser window loses focus, blocks keyboard shortcuts (`PrintScreen`, `Ctrl+P`, `Ctrl+S`), and renders high-frequency anti-screen capture grid overlays that degrade photo clarity. · seen in: Fasoo Screen Capture Protection, Fortra Vera, Kiteworks SafeViewer · priority: **differentiator** · spine: `DocumentDrmPolicy.screen_shield_enabled` · **buildable now**
- **Print Restriction & Controlled Hardcopy Quotas** — Blocks browser and system printing (`allow_print=False`). When printing is authorized for compliance, enforces mandatory dynamic forensic watermarking and logs print telemetry. · seen in: Adobe Acrobat Rights Management, OpenText TCS, Fasoo · priority: **table-stakes** · spine: `DocumentDrmPolicy.allow_print` · **buildable now**
- **Network Geofencing & IP Allowlist Filtering** — Enforces CIDR IP block allowlists (`ip_allowlist`) and country-level geofencing restricting document decryption and viewing to verified corporate networks and authorized physical regions. · seen in: Box Shield Network Policies, Kiteworks Geo-Restrictions · priority: **common** · spine: `DocumentDrmPolicy.ip_allowlist`, client IP validation interceptor · **buildable now**
- **Offline Access Time-Bomb & Expiry Controls** — Configures maximum offline viewing duration (`max_offline_hours`) and hard document lifespan (`expiry_days`). Upon expiration, cached keys are invalidated and the document becomes inaccessible. · seen in: Adobe DRM Expiration, Microsoft Purview Offline Limits · priority: **table-stakes** · spine: `DocumentDrmPolicy.max_offline_hours`, `expiry_days` · **buildable now**
- **Emergency Kill-Switch & Retroactive Document Revocation** — Provides an administrative one-click emergency kill-switch (`is_revoked=True`) that immediately revokes all active licenses, sessions, and viewing tokens for a compromised document across all recipients and cached clients. · seen in: Adobe Document Revocation, Virtru Instant Revoke, Fortra Vera Kill Switch · priority: **table-stakes** · spine: `DocumentDrmPolicy.is_revoked`, `revoked_at`, `revocation_reason` · **buildable now**

### Data Loss Prevention (DLP)
- **Data Loss Prevention Policy Engine (`DlpPolicy` - `DDLP`)** — Tenant-scoped inspection rule engine configuring automated content scanning across document drafts, text layers, and metadata for sensitive information and compliance violations. · seen in: Microsoft Purview DLP, Egnyte Content Intelligence, Box Shield Threat Detection · priority: **table-stakes** · spine: `DlpPolicy` (`DDLP`), `core.Tenant` · **buildable now**
- **Built-in Sensitive Information Type (SIT) Pattern Library** — Prebuilt regex pattern signatures detecting standard regulated data formats: Payment Card Numbers (PCI-DSS credit cards with Luhn checksum validation), US Social Security Numbers (SSN), International Bank Account Numbers (IBAN), National Identification Numbers, API Keys/Secrets, and Email Address Harvesters. · seen in: Microsoft Purview SITs, Egnyte Sensitive Patterns, Google Cloud DLP · priority: **table-stakes** · spine: `DlpPolicy.built_in_pattern` choices and validation logic · **buildable now**
- **Proprietary Keyword & Custom Regex Pattern Matching** — Enables administrators to register custom Python-compatible regular expressions and sensitive keyword dictionaries (e.g. Project codenames, M&A terms, proprietary trade secrets, formula codes) with configurable minimum occurrence thresholds (`match_threshold`). · seen in: Microsoft Purview Custom DLP, Box Shield Custom Terms · priority: **table-stakes** · spine: `DlpPolicy.custom_regex`, `DlpPolicy.sensitive_keywords`, `match_threshold` · **buildable now**
- **Multi-Tier Automated Enforcement Actions** — Configurable automated policy actions executed upon detection of a DLP match:
  - `log_only`: Silently records audit telemetry without alerting or interrupting user workflow.
  - `warn_author`: Displays a prominent policy tip warning banner to the author with remediation suggestions.
  - `block_save`: Prevents saving drafts, uploading new versions, or checking in documents until sensitive content is sanitized.
  - `quarantine`: Instantly locks the document into an administrative quarantine state accessible only by compliance officers.
  - `force_watermark`: Automatically escalates classification to `restricted` and mandates strict DRM watermarking.
  · seen in: Microsoft Purview DLP Actions, Egnyte Enclave Quarantine, Box Shield · priority: **table-stakes** · spine: `DlpPolicy.action` choices (`log_only`, `warn_author`, `block_save`, `quarantine`, `force_watermark`) · **buildable now**
- **DLP Incident Logging & Triage Workbench (`DlpIncident` - `DINC`)** — Comprehensive audit logging of every policy violation: timestamp, violating document, user, rule triggered, severity level (`low`, `medium`, `high`, `critical`), action taken, and a redacted context snippet masking sensitive numbers (e.g., `Card: ************1234`). Provides triage statuses (`open`, `under_investigation`, `resolved_justified`, `false_positive`, `dismissed`). · seen in: Microsoft Purview DLP Incident Dashboard, Egnyte Issue Triage, Kiteworks · priority: **table-stakes** · spine: `DlpIncident` (`DINC`), `DlpPolicy`, `Document`, `User` · **buildable now**
- **Security Officer Instant Violation Alerting** — Configurable automated email and system notification dispatch triggering when high-severity or critical DLP violations are detected, including immediate containment links. · seen in: Microsoft Purview Incident Alerts, Box Shield Alerts · priority: **common** · spine: `DlpPolicy.notify_security_officer`, `DlpPolicy.notification_email` · **buildable now**

### Beyond the Bullets
- **Unified Security & Access Control Console UI** — Comprehensive administrative hub featuring four integrated tabs: Permissions Matrix, Watermark Studio, DRM Protection Center, and DLP Threat Monitor with real-time health indicators and quick policy toggles. · seen in: Box Shield Console, Microsoft Purview Compliance Portal · priority: **table-stakes** · spine: Dedicated Security Hub dashboard view and template · **buildable now**
- **Document Access Security Modal & Drawer Component** — Reusable HTMX-powered slide-over security drawer embeddable into Document Detail, Version Control, and Storage views, enabling document owners to view active ACLs, add temporary guest viewers, test effective access, or review active watermarks without leaving the document context. · seen in: Box Sharing Modal, SharePoint Access Drawer, Google Drive Sharing Dialog · priority: **common** · spine: HTMX partial component for security drawer · **buildable now**
- **Automated Quarantine Workflow & Release Verification** — Formal remediation process allowing authors to submit a justification appeal for quarantined documents, reviewed by Compliance/Legal officers who can verify remediation and approve release. · seen in: Microsoft Purview Quarantine, Egnyte Remediation Workflow · priority: **common** · spine: `DlpIncident.resolution_status`, `resolution_notes`, `resolved_by` · **buildable now**

---

## Recommended build scope (this pass — 4 models)

1. **`DocumentAccessPermission`** [`DPRM-`] — Granular multi-tier Access Control List (ACL) mapping documents or folders to users, departments, or roles with capability flags and expiration.
   - **Fields**:
     - `number` (CharField 32, unique=True, db_index=True)
     - `tenant` (FK `core.Tenant`, on_delete=CASCADE, db_index=True)
     - `document` (FK `documents.Document`, null=True, blank=True, on_delete=CASCADE, related_name="access_permissions")
     - `folder` (FK `documents.DocumentFolder`, null=True, blank=True, on_delete=CASCADE, related_name="access_permissions")
     - `grantee_type` (CharField 20, default="user", choices: `user`, `org_unit`, `role`, `tenant_wide`)
     - `user` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True, on_delete=CASCADE, related_name="document_permissions")
     - `org_unit` (FK `core.OrgUnit`, null=True, blank=True, on_delete=CASCADE, related_name="document_permissions")
     - `role_name` (CharField 50, blank=True, help_text="e.g. legal_counsel, auditor, executive, compliance_officer")
     - `permission_level` (CharField 20, default="viewer", choices: `custom`, `viewer`, `commenter`, `editor`, `manager`, `owner`)
     - Capability flags:
       - `can_read` (BooleanField, default=True)
       - `can_write` (BooleanField, default=False)
       - `can_delete` (BooleanField, default=False)
       - `can_download` (BooleanField, default=True)
       - `can_print` (BooleanField, default=True)
       - `can_share` (BooleanField, default=False)
     - Inheritance:
       - `is_inherited` (BooleanField, default=False)
       - `inherited_from_folder` (FK `documents.DocumentFolder`, null=True, blank=True, on_delete=models.SET_NULL, related_name="inherited_permissions")
     - Validity & Expiry:
       - `valid_from` (DateTimeField, null=True, blank=True)
       - `valid_until` (DateTimeField, null=True, blank=True)
       - `is_active` (BooleanField, default=True, db_index=True)
     - Telemetry:
       - `access_count` (PositiveIntegerField, default=0)
       - `last_accessed_at` (DateTimeField, null=True, blank=True)
     - Audit & Notes:
       - `notes` (CharField 255, blank=True)
       - `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="granted_document_permissions")
   - **Choices**:
     - `GRANTEE_TYPE_CHOICES` (`user`, `org_unit`, `role`, `tenant_wide`)
     - `PERMISSION_LEVEL_CHOICES` (`custom`, `viewer`, `commenter`, `editor`, `manager`, `owner`)
     - `PERMISSION_LEVEL_CSS` badge color mappings
   - **Justified by**: Document-Level Permissions, Hierarchical Inheritance, Time-Bounded Access Grants, Stale Access Tracking.
   - **FKs**: `core.Tenant`, `documents.Document`, `documents.DocumentFolder`, `accounts.User`, `core.OrgUnit`.

2. **`WatermarkPolicy`** [`DWTR-`] — Dynamic watermarking rules and visual overlay configurations mapped by classification or document type.
   - **Fields**:
     - `number` (CharField 32, unique=True, db_index=True)
     - `tenant` (FK `core.Tenant`, on_delete=CASCADE, db_index=True)
     - `name` (CharField 150)
     - `slug` (SlugField 160, blank=True)
     - `description` (TextField, blank=True)
     - Scope & Triggers:
       - `classification` (CharField 20, default="all", choices: `all`, `public`, `internal`, `confidential`, `restricted`)
       - `document_type` (CharField 40, default="all", choices: `all` + `Document.DOCUMENT_TYPE_CHOICES`)
       - `department` (FK `core.OrgUnit`, null=True, blank=True, on_delete=models.SET_NULL, related_name="watermark_policies")
       - `apply_to_all` (BooleanField, default=False)
     - Text Template & Content:
       - `watermark_text` (CharField 255, default="{{classification}} | {{user_name}} | {{timestamp}}")
       - `secondary_text` (CharField 255, blank=True, help_text="Optional second line e.g. 'DO NOT DISTRIBUTE - STRICTLY CONFIDENTIAL'")
     - Styling & Layout:
       - `position` (CharField 20, default="diagonal_center", choices: `diagonal_center`, `center`, `header_banner`, `footer_banner`, `tiled_grid`)
       - `opacity_percent` (PositiveIntegerField, default=25, help_text="Watermark opacity from 1% to 100%")
       - `font_size` (PositiveIntegerField, default=32, help_text="Font size in points")
       - `font_color` (CharField 20, default="#94a3b8", help_text="Hex color code e.g. #94a3b8 or #dc2626")
       - `rotation_angle` (IntegerField, default=-45, help_text="Angle in degrees, typically -45")
     - Classification Banners:
       - `show_classification_banner` (BooleanField, default=True, help_text="Display prominent colored header/footer classification bar")
       - `banner_position` (CharField 20, default="top", choices: `top`, `bottom`, `both`)
     - Enforcement Contexts:
       - `enforce_on_view` (BooleanField, default=True, help_text="Overlay in web previewer")
       - `enforce_on_download` (BooleanField, default=True, help_text="Burn into downloaded PDF renditions")
       - `enforce_on_print` (BooleanField, default=True, help_text="Inject into print rendition")
     - Priority & Status:
       - `priority` (PositiveIntegerField, default=100, help_text="Evaluation priority: lowest number takes precedence")
       - `is_active` (BooleanField, default=True, db_index=True)
       - `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="created_watermark_policies")
   - **Choices**:
     - `CLASSIFICATION_CHOICES` (`all`, `public`, `internal`, `confidential`, `restricted`)
     - `POSITION_CHOICES` (`diagonal_center`, `center`, `header_banner`, `footer_banner`, `tiled_grid`)
     - `BANNER_POSITION_CHOICES` (`top`, `bottom`, `both`)
   - **Justified by**: Dynamic Watermarking, Variable & Token Interpolation, Classification Banners, Enforcement Gates.
   - **FKs**: `core.Tenant`, `core.OrgUnit`, `accounts.User`.

3. **`DocumentDrmPolicy`** [`DDRM-`] — Digital Rights Management, anti-exfiltration restrictions, secure viewer controls, and emergency revocation switch.
   - **Fields**:
     - `number` (CharField 32, unique=True, db_index=True)
     - `tenant` (FK `core.Tenant`, on_delete=CASCADE, db_index=True)
     - `name` (CharField 150)
     - `slug` (SlugField 160, blank=True)
     - `description` (TextField, blank=True)
     - Scope & Targets:
       - `classification` (CharField 20, default="confidential", choices: `all`, `public`, `internal`, `confidential`, `restricted`)
       - `document_type` (CharField 40, default="all", choices: `all` + `Document.DOCUMENT_TYPE_CHOICES`)
       - `target_document` (FK `documents.Document`, null=True, blank=True, on_delete=models.CASCADE, related_name="drm_policies")
       - `target_folder` (FK `documents.DocumentFolder`, null=True, blank=True, on_delete=models.CASCADE, related_name="drm_policies")
     - DRM Restrictions:
       - `allow_download` (BooleanField, default=False, help_text="Allow raw physical file download; False forces secure viewer only")
       - `allow_print` (BooleanField, default=False, help_text="Allow printing document")
       - `allow_copy_paste` (BooleanField, default=False, help_text="Allow selecting text and clipboard copying")
       - `screen_shield_enabled` (BooleanField, default=True, help_text="Enable blur on focus loss and anti-screen capture guards")
       - `secure_viewer_required` (BooleanField, default=True, help_text="Require sandboxed canvas/SVG viewer")
       - `require_watermark` (BooleanField, default=True, help_text="Enforce dynamic watermark overlay")
     - Temporal & Network Controls:
       - `max_offline_hours` (PositiveIntegerField, default=0, help_text="0 = offline caching prohibited")
       - `expiry_days` (PositiveIntegerField, default=30, help_text="Document access automatically expires N days after issue")
       - `ip_allowlist` (TextField, blank=True, help_text="Allowed IP addresses or CIDR ranges, comma or newline separated")
       - `geo_fencing_countries` (CharField 255, blank=True, help_text="Comma-separated ISO-2 country codes e.g. US, CA, GB")
     - Cryptographic & Emergency Revocation:
       - `is_revoked` (BooleanField, default=False, db_index=True, help_text="Emergency kill-switch: immediately invalidates access")
       - `revoked_at` (DateTimeField, null=True, blank=True)
       - `revocation_reason` (TextField, blank=True)
       - `encryption_standard` (CharField 30, default="AES_256_GCM", choices: `AES_256_GCM`, `AES_256_CBC`, `CHACHA20_POLY1305`)
     - Status & Audit:
       - `is_active` (BooleanField, default=True, db_index=True)
       - `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="created_drm_policies")
   - **Choices**:
     - `ENCRYPTION_CHOICES` (`AES_256_GCM`, `AES_256_CBC`, `CHACHA20_POLY1305`)
   - **Justified by**: DRM & Document Protection, Zero-Download Viewer Enforcement, Screen Shield Defense, Emergency Kill-Switch.
   - **FKs**: `core.Tenant`, `documents.Document`, `documents.DocumentFolder`, `accounts.User`.

4. **`DlpPolicy`** [`DDLP-`] — Data Loss Prevention inspection rules, regex pattern libraries, sensitive keyword detection, and enforcement actions.
   - **Fields**:
     - `number` (CharField 32, unique=True, db_index=True)
     - `tenant` (FK `core.Tenant`, on_delete=CASCADE, db_index=True)
     - `name` (CharField 150)
     - `slug` (SlugField 160, blank=True)
     - `description` (TextField, blank=True)
     - Rule Specification:
       - `rule_type` (CharField 30, default="built_in_pattern", choices: `built_in_pattern`, `sensitive_keywords`, `custom_regex`, `classification_anomaly`)
       - `built_in_pattern` (CharField 30, default="none", choices: `none`, `credit_card_pci`, `us_ssn`, `iban_banking`, `national_id_pii`, `email_list`, `api_keys_secrets`)
       - `custom_regex` (TextField, blank=True, help_text="Python regex pattern for custom sensitive data format")
       - `sensitive_keywords` (JSONField, default=list, blank=True, help_text='JSON list of sensitive keywords e.g. ["Confidential", "M&A", "Secret"]')
       - `match_threshold` (PositiveIntegerField, default=1, help_text="Minimum number of pattern occurrences required to trigger violation")
     - Enforcement Action & Severity:
       - `action` (CharField 20, default="warn_author", choices: `log_only`, `warn_author`, `block_save`, `quarantine`, `force_watermark`)
       - `severity` (CharField 20, default="high", choices: `low`, `medium`, `high`, `critical`)
       - `notify_security_officer` (BooleanField, default=True)
       - `notification_email` (CharField 255, blank=True)
     - Scope Filters:
       - `apply_to_all_types` (BooleanField, default=True)
       - `target_document_types` (JSONField, default=list, blank=True, help_text="Specific document types to inspect")
       - `target_classifications` (JSONField, default=list, blank=True, help_text="Specific classification levels to inspect")
     - Performance & Telemetry:
       - `incident_count` (PositiveIntegerField, default=0)
       - `last_triggered_at` (DateTimeField, null=True, blank=True)
       - `is_active` (BooleanField, default=True, db_index=True)
       - `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="created_dlp_policies")
   - **Choices**:
     - `RULE_TYPE_CHOICES` (`built_in_pattern`, `sensitive_keywords`, `custom_regex`, `classification_anomaly`)
     - `BUILT_IN_PATTERN_CHOICES` (`none`, `credit_card_pci`, `us_ssn`, `iban_banking`, `national_id_pii`, `email_list`, `api_keys_secrets`)
     - `ACTION_CHOICES` (`log_only`, `warn_author`, `block_save`, `quarantine`, `force_watermark`)
     - `SEVERITY_CHOICES` (`low`, `medium`, `high`, `critical`)
     - `SEVERITY_CSS` badge styling
   - **Justified by**: Data Loss Prevention, Built-in SIT Pattern Library, Automated Enforcement Actions, Incident Alerting.
   - **FKs**: `core.Tenant`, `accounts.User`.

- **Associated Telemetry & Incident Schema — `DlpIncident` [`DINC-`]**:
  To ensure enterprise-grade DLP incident triage without exceeding the 4 primary configuration models, DLP inspection results are logged into `DlpIncident` [`DINC-`] (or recorded as JSON telemetry on `DlpPolicy`):
  - `number` (CharField 32, unique=True, prefix `DINC`)
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `policy` (FK `documents.DlpPolicy`, on_delete=models.CASCADE, related_name="incidents")
  - `document` (FK `documents.Document`, on_delete=models.CASCADE, related_name="dlp_incidents")
  - `document_version` (FK `documents.DocumentVersion`, null=True, blank=True, on_delete=models.SET_NULL)
  - `triggered_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="triggered_dlp_incidents")
  - `severity` (CharField 20, choices: `low`, `medium`, `high`, `critical`)
  - `action_taken` (CharField 20, choices: `logged`, `warned`, `blocked`, `quarantined`, `watermarked`)
  - `matches_detected_count` (PositiveIntegerField, default=1)
  - `snippet_redacted` (TextField, blank=True, help_text="Masked evidence context e.g. 'Card: ****-****-****-4242'")
  - `resolution_status` (CharField 25, default="open", choices: `open`, `under_investigation`, `resolved_justified`, `false_positive`, `dismissed`)
  - `resolved_by` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True, on_delete=models.SET_NULL)
  - `resolution_notes` (TextField, blank=True)
  - `created_at` (DateTimeField, auto_now_add=True, db_index=True)

- **Dedicated Views / UI Surfaces:**
  - `Document Security & Permissions Manager` (`documents:permission_list`, `documents:permission_create`, `documents:permission_edit`, `documents:permission_delete`): Matrix view of active ACL entries with filter by document/folder, user, role, and department. Includes dynamic effective permissions calculator badge.
  - `Dynamic Watermark Policies` (`documents:watermark_list`, `documents:watermark_create`, `documents:watermark_edit`, `documents:watermark_detail`): Policy manager with visual interactive live preview rendering sample document watermark with current opacity, angle, and token interpolation.
  - `DRM & Content Protection Console` (`documents:drm_policy_list`, `documents:drm_policy_create`, `documents:drm_policy_edit`, `documents:drm_kill_switch`): DRM governance panel with zero-download/print/clipboard protection toggles, IP allowlist manager, and emergency one-click kill-switch modal.
  - `Data Loss Prevention (DLP) Hub & Incidents` (`documents:dlp_policy_list`, `documents:dlp_policy_create`, `documents:dlp_incident_list`, `documents:dlp_incident_detail`, `documents:dlp_incident_resolve`): DLP inspection rule library with pattern toggles, incident violation triage log with redacted evidence snippets, and resolution action buttons.
  - `Secure Web Viewer Console` (`documents:secure_viewer`): Sandboxed in-browser zero-download document viewing canvas with dynamic user-specific watermark overlay, disabled context menu (`contextmenu` blocked), disabled text selection (`user-select: none`), keyboard print/save interceptor (`Ctrl+P`, `Ctrl+S`), and focus-loss screen shield blur.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **13.1 Document Creation & Authoring** — Template creation, rich text drafts, and authoring collaboration. (13.7 provides DLP hooks during draft save/publish).
- **13.2 Version Control & Revision Management** — File binary storage, version numbering, and check-in / check-out locks. (13.7 controls read/write/download access to these versions).
- **13.3 Document Approval & Review Workflow** — Multi-stage approval routing, sequential sign-off chains, and digital signatures.
- **13.4 Document Storage & Repository** — Physical storage volume tiering, folder hierarchy taxonomies, and bulk batch imports. (13.7 folder permissions attach to `DocumentFolder`).
- **13.5 Metadata & Indexing** — Metadata schemas, OCR extraction queues, and taxonomy term controlled vocabulary. (13.7 DLP engine scans OCR text output for sensitive patterns).
- **13.6 Search & Discovery** — Compound search engine, faceted navigation, saved queries, and search analytics. (13.7 ensures search result queries enforce document ACLs so unauthorized files are never leaked in search listings).
- **13.8 Collaboration & Sharing** — External public shared links, guest access tokens, password-protected shared URLs, and co-authoring presence. (13.7 handles internal tenant ACLs, watermarking, DRM policies, and DLP content inspection; 13.8 handles external sharing links and collaboration threads).
- **13.9 Records Management & Compliance** — Automatic legal hold placement, retention schedules, destruction authorization, and disposition certification.
- **13.10 Audit Trail & Reporting** — Universal tenant-wide immutable audit event stream logging every view, edit, download, and export event across the entire system.

---

## Deferred (later passes / integrations)

- **Hardware Security Module (HSM) & Cloud KMS BYOK Integration** — Dedicated hardware key storage integration with AWS KMS, Azure Key Vault, or Google Cloud KMS for Bring Your Own Key (BYOK) customer-managed encryption keys.
- **OS-Level Kernel Screen-Capture Filter Driver** — Native endpoint desktop agent blocking Windows Snipping Tool, macOS Screenshot, and third-party screen grabbers at the operating system display compositor level.
- **Steganographic Invisible Micro-Dot Fingerprinting** — High-security forensic steganography embedding invisible zero-width whitespace sequences or subtle imperceptible pixel luminance perturbations into PDF/image payloads to trace photographed document leaks back to individual user sessions.
- **Deep-Learning NLP DLP Classifier** — Fine-tuned transformer models (BERT / LLM) for nuanced contextual semantic classification of proprietary trade secrets, unreleased financial reports, and confidential source code beyond regex pattern matching.
