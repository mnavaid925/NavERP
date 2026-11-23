# Research — Sub-module 13.6: Search & Discovery (Module 13 — Document Management System, documents)

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
  - `13.5` (Metadata & Indexing — models, forms, views, and templates built):
    - `MetadataSchema` (`apps/documents/models/MetadataIndexing/MetadataSchemas.py`, `NUMBER_PREFIX = "DSCH"`)
    - `DocumentMetadataValue` (`apps/documents/models/MetadataIndexing/DocumentMetadataValues.py`, `NUMBER_PREFIX = "DMETA"`)
    - `TaxonomyTerm` (`apps/documents/models/MetadataIndexing/TaxonomyTerms.py`, `NUMBER_PREFIX = "DTAX"`)
    - `DocumentOcrJob` (`apps/documents/models/MetadataIndexing/DocumentOcrJobs.py`, `NUMBER_PREFIX = "DOCR"`)

- **Sibling models available to FK in `apps/documents/` (verified via grep):**
  - `documents.Document` (`apps/documents/models/VersionControl/Documents.py:8`, `NUMBER_PREFIX = "DOC"`): Core logical document master containing title, slug, classification, document_type, status, owner, department, tags, version tracking.
  - `documents.DocumentVersion` (`apps/documents/models/VersionControl/DocumentVersions.py:9`, `NUMBER_PREFIX = "DVER"`): Immutable physical file revision snapshot with `extracted_text` (full-text search body), file payload, hash, size, and MIME type.
  - `documents.DocumentFolder` (`apps/documents/models/StorageRepository/DocumentFolders.py:9`, `NUMBER_PREFIX = "DFLD"`): Hierarchical folder repository tree with `path`, `default_classification`, and `default_document_type`.
  - `documents.MetadataSchema` (`apps/documents/models/MetadataIndexing/MetadataSchemas.py:14`, `NUMBER_PREFIX = "DSCH"`): Custom metadata schema definitions with typed fields.
  - `documents.DocumentMetadataValue` (`apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:14`, `NUMBER_PREFIX = "DMETA"`): Document instance metadata stored in `values_json`.
  - `documents.TaxonomyTerm` (`apps/documents/models/MetadataIndexing/TaxonomyTerms.py:14`, `NUMBER_PREFIX = "DTAX"`): Controlled vocabulary with `vocabulary_name`, `term_code`, `label`, `synonyms` JSON.

- **Spine entities verified to exist (grep evidence):**
  - `core.Tenant` (`apps/core/models/Tenant.py:class Tenant`): Multi-tenant isolation anchor.
  - `accounts.User` (`settings.AUTH_USER_MODEL` / `apps/accounts/models.py`): System users, searchers, saved search owners, alert recipients.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:class OrgUnit`): Organizational units for department-filtered queries and scoped search results.
  - Base classes: `apps.documents.models._base.TenantNumbered` and `TenantOwned` providing atomic concurrency-safe sequential number generation (`next_number`).

- **Prefix verification (all candidate prefixes verified 100% free across entire repo):**
  - `DSVD` (`DocumentSavedSearch`): Verified free (0 matches in repo).
  - `DALT` (`DocumentSearchAlert`): Verified free (0 matches in repo).
  - `DSYN` (`DocumentSearchSynonym`): Verified free (0 matches in repo).
  - `DQRY` (`DocumentSearchQueryLog`): Verified free (0 matches in repo).
  - All existing prefixes in `apps/documents/` preserved without collision: `DOC`, `DVER`, `DLOCK`, `DBRN`, `DTMPL`, `DSEC`, `DDFT`, `DCMT`, `DWF`, `DAPR`, `DSIG`, `DREV`, `DFLD`, `DSTG`, `DREL`, `DBLK`, `DSCH`, `DMETA`, `DTAX`, `DOCR`.

---

## Leaders surveyed (with source links)

1. **Elasticsearch / OpenSearch (Enterprise Search Engine & Percolator Alerting)** — Distributed search engine standard powering enterprise ECM backends. Employs Lucene inverted indexes, multi-criteria filtering, terms/range aggregations to power faceted drill-downs, search-time `synonym_graph` token filters for multi-word phrase synonyms, and percolator queries ("reverse search": matching incoming documents against registered saved queries for instant search alerts).
   - *Source:* https://opensearch.org/docs/latest/search-plugins/searching-data/aggregations/ · https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-percolate-query.html
2. **Microsoft SharePoint & Microsoft Search (Enterprise Search Analytics & Synonyms)** — Industry enterprise standard across Microsoft 365. Implements managed property schemas, search verticals, query rules, term-store synonym expansion, personal bookmarks, and search usage analytics tracking top queries and zero-result queries (abandoned searches) to identify content voids.
   - *Source:* https://learn.microsoft.com/en-us/microsoftsearch/overview-microsoft-search · https://learn.microsoft.com/en-us/sharepoint/manage-search-schema
3. **M-Files (Metadata-First Dynamic Views & Faceted Discovery)** — ECM pioneer where "What" replaces "Where". Uses dynamic metadata views (virtual saved searches without physical folders), multi-property faceted filters, 360-degree document relationship discovery, and state-based alert rules notifying users when documents match specified criteria.
   - *Source:* https://www.m-files.com/product/document-management/ · https://userguide.m-files.com/user-guide/latest/eng/views.html
4. **OpenText Content Server / Documentum (Faceted Smart View & xPlore Saved Searches)** — Leading enterprise ECM for regulated industries. Features xPlore full-text indexing, configurable faceted metadata navigation in Smart View, DQL/search templates, saved smart queries, and persistent query subscriptions with email dispatch.
   - *Source:* https://www.opentext.com/products/content-server · https://www.opentext.com/products/documentum-server
5. **Laserfiche Cloud & Federated Search (Advanced Syntax & Scheduled Search Alerts)** — Premier records and document management platform. Features visual advanced search syntax generation (`{LF:...}`), boolean operators (`AND`, `OR`, `NOT`), saved searches with shared trustee access, direct search URL sharing, and automated scheduled search workflows with email notifications.
   - *Source:* https://doc.laserfiche.com/laserfiche.documentation/en-us/subsystems/client/content/resources/search_syntax.htm · https://www.laserfiche.com/products/enterprise-content-management/
6. **Box Search & Box AI Discovery (Metadata Query API & Conversational Discovery)** — Cloud enterprise content management. Offers Boolean/attribute search, custom metadata query API (SQL-like filtering on template fields), dynamic facet refinement, and Box AI conversational search translating natural language questions into filtered views.
   - *Source:* https://support.box.com/hc/en-us/articles/360043696314-Search-for-Files-and-Folders · https://www.box.com/ai
7. **Alfresco Content Services (Alfresco Search Enterprise & ADF Facets)** — Open-standards ECM with Alfresco Search Enterprise (Elasticsearch/OpenSearch backed). Provides REST API facet queries, facet fields, and facet intervals, customizable search chips and filters in Alfresco Digital Workspace (ADF), and user-persisted saved searches.
   - *Source:* https://docs.alfresco.com/content-services/latest/using/search/ · https://docs.alfresco.com/search-services/latest/
8. **Algolia & Coveo (Enterprise Search Analytics, Relevance Tuning & Synonyms)** — World-leading cognitive search and discovery platforms. Feature real-time faceted navigation, query suggestions/autocomplete, dedicated search analytics tracking zero-result queries (abandoned searches) and popular searches, multi-way and one-way synonym dictionaries, and click-through tracking.
   - *Source:* https://www.algolia.com/doc/guides/managing-results/refine-results/facets/ · https://www.coveo.com/en/solutions/enterprise-search

---

## Feature catalog (this sub-module only)

### Advanced Search & Filters
- **Multi-Criteria Search Engine** — Comprehensive compound query execution combining free-text query string (searching across `title`, `description`, `tags`, and `DocumentVersion.extracted_text`), structured metadata attributes, date range filters (created, modified, or approved dates), author/owner filter, document type, and classification. · seen in: OpenText Content Server, Box Search, Alfresco · priority: **table-stakes** · spine: `Document`, `DocumentVersion.extracted_text`, `DocumentSavedSearch.criteria_json` · **buildable now**
- **Field-Specific Filter Matrix** — Granular filtering by exact, partial, and range criteria: file format/MIME type, file size bounds (min/max KB), folder location, version number, lifecycle status (`draft`, `in_review`, `approved`, `published`, `archived`), and organizational unit / department. · seen in: M-Files Property Filters, Laserfiche Search Syntax · priority: **table-stakes** · spine: `Document` fields, `core.OrgUnit`, `DocumentFolder` · **buildable now**
- **Search Scope & Repository Boundary Limiting** — Allows restricting queries to a specific branch of the folder tree (`DocumentFolder` including subfolders), a particular storage volume (`StorageVolume`), or searching tenant-wide across all accessible repositories. · seen in: SharePoint Search Scopes, Box Folder Search · priority: **common** · spine: `DocumentFolder.path`, `StorageVolume` · **buildable now**
- **Boolean & Exact Phrase Search Syntax** — Supports boolean operators (`AND`, `OR`, `NOT`), quoted exact phrase matching (`"vendor agreement"`), prefix wildcards (`contr*`), and exclusion terms (`-draft`). · seen in: Laserfiche Search Syntax, Elasticsearch Query DSL · priority: **table-stakes** · spine: Parsed into Django `Q` query expressions · **buildable now**
- **Metadata Value Filtering** — Dynamic querying against structured key-value attributes stored in `DocumentMetadataValue.values_json` (e.g. `contract_value__gte=50000`, `jurisdiction="US-NY"`). · seen in: Box Metadata Query API, M-Files Property Conditions · priority: **table-stakes** · spine: `DocumentMetadataValue.values_json` · **buildable now**

### Faceted Search Navigation
- **Dynamic Filter Refinement & Aggregations** — Computes live document distribution counts across categorical facets: document type (`contract`, `policy`, `sop`, etc.), classification level (`public`, `internal`, `confidential`, `restricted`), workflow status, file format (`pdf`, `docx`, `xlsx`, `image`), and department. Selecting one facet recalculates matching counts for other facets. · seen in: Alfresco ADF Facets, Algolia Faceted Search, OpenText Smart View · priority: **table-stakes** · spine: Dynamic Django ORM aggregation queries on search result sets · **buildable now**
- **Interactive Tag Clouds & Topic Clusters** — Weighted visualization of tags extracted from matching documents, displaying frequency-proportional badge sizes. Clicking any tag instantly filters results by that tag. · seen in: SharePoint Tag Clouds, Alfresco Topic Clusters · priority: **common** · spine: Aggregated string splitting and frequency tally on `Document.tags` · **buildable now**
- **Result Clustering & Temporal Bucketing** — Groups search results into contextual clusters: by document type, by department, or by temporal buckets ("Today", "This Week", "This Month", "Older") for rapid cognitive scanning. · seen in: Coveo Smart Clusters, OpenText Result Grouping · priority: **common** · spine: UI grouping and ordering of search queryset · **buildable now**
- **Active Filter Chips & One-Click Reset** — Displays all applied search filters and facets as dismissible badge chips at the top of results, enabling individual filter removal or complete query clearing. · seen in: Box Search UI, Alfresco Digital Workspace · priority: **table-stakes** · spine: HTMX/Tailwind dynamic filter strip · **buildable now**

### Saved Searches & Alerts
- **Persistent Saved Search Definitions (`DocumentSavedSearch` - `DSVD`)** — Allows users to save complex multi-criteria queries with a friendly name, description, search string, criteria JSON (all active filters and facets), sort preferences, and view layout. · seen in: M-Files Saved Views, OpenText Saved Searches, Laserfiche · priority: **table-stakes** · spine: `DocumentSavedSearch` (`DSVD`) · **buildable now**
- **Personal vs Team/Public Search Sharing** — Granular visibility controls for saved searches: `private` (visible only to creator), `shared_department` (accessible by members of the user's `core.OrgUnit`), or `public` (accessible to all tenant users). · seen in: Laserfiche Trustee Attributes, Box Shared Views · priority: **table-stakes** · spine: `DocumentSavedSearch.visibility`, `DocumentSavedSearch.shared_department` · **buildable now**
- **Pinned Searches & Quick Launch Navigation** — Enables users to pin favorite saved searches as quick-access shortcuts in the discovery navigation bar or personal dashboard for instant one-click execution. · seen in: M-Files Pinned Views, SharePoint Search Bookmarks · priority: **common** · spine: `DocumentSavedSearch.is_pinned`, `DocumentSavedSearch.sort_order` · **buildable now**
- **Automated Search Alert Subscriptions (`DocumentSearchAlert` - `DALT`)** — Configurable alert triggers on saved searches that monitor repository changes. Executes on schedule (`realtime`, `daily`, `weekly`, `monthly`) or on demand, tracking match counts and last execution timestamps. · seen in: OpenText Search Subscriptions, Laserfiche Workflow Search Activity · priority: **table-stakes** · spine: `DocumentSearchAlert` (`DALT`) · **buildable now**
- **New-Match Delta Detection & Notification** — Compares current matching documents against the previous alert execution snapshot (`last_result_ids` / `last_result_count`), surfacing only net-new matching documents to avoid notification fatigue. · seen in: Elasticsearch Percolator, Laserfiche Search Alerts · priority: **table-stakes** · spine: `DocumentSearchAlert.last_result_ids`, `DocumentSearchAlert.last_notified_at` · **buildable now**
- **Alert Delivery Channel Preferences** — Supports user-configurable notification channels: in-app notification badges, email digests, or webhook payload triggers. · seen in: OpenText Alert Routing, Alfresco Notifications · priority: **common** · spine: `DocumentSearchAlert.delivery_channel` · **buildable now**

### Natural Language Query & AI Search
- **Heuristic Intent Recognition & Query Parsing** — Translates natural language conversational search expressions (e.g., *"confidential contracts authored by Sarah last month"*, *"approved policies in HR"*) into structured filter parameters: `classification=confidential`, `document_type=contract`, `owner__username=sarah`, `date_range=last_month`, `department=HR`. · seen in: Box AI Discovery, Microsoft Search NLP · priority: **common** · spine: Rule-based regex and token intent parser mapping to Django filters · **buildable now**
- **Conversational Smart Search Chips UI** — Visual interactive interface that detects parsed query intents and presents them as interactive suggested filter pills prior to execution (e.g. *"Filtered by: Type [Contract] x Status [Approved] x Owner [Sarah]"*), allowing user review and refinement. · seen in: Box AI, Coveo Intelligent Search · priority: **common** · spine: HTMX intent badge preview strip · **buildable now**
- **Multi-Factor Semantic Result Ranking** — Relevance scoring engine that ranks search results using a multi-factor formula: exact title match (weight 1.0) + tag match (weight 0.8) + metadata attribute match (weight 0.6) + full-text body match (weight 0.4) + recency decay factor. · seen in: Coveo Automatic Relevance Tuning (ART), Algolia Ranking Criteria · priority: **differentiator** · spine: Queryset ordering with weighted annotation calculations · **buildable now**
- **Pluggable Vector / Embedding Search Interface** — Architectural hook and data schema compatibility for embedding vector similarity search, dense retrieval, and hybrid dense+sparse keyword ranking for future neural search integrations. · seen in: OpenSearch k-NN, Azure AI Search Hybrid · priority: **differentiator** · spine: Abstract query interface with extension points · **integration/later**

### Search Analytics & Query Optimization
- **Search Telemetry & Audit Query Logging (`DocumentSearchQueryLog` - `DQRY`)** — Comprehensive logging of every search execution: query string, JSON filter payload, execution time in milliseconds, total results returned, executed_by user, user IP address, and timestamp. · seen in: Algolia Insights API, Coveo Usage Analytics, Microsoft Search Reports · priority: **table-stakes** · spine: `DocumentSearchQueryLog` (`DQRY`) · **buildable now**
- **Zero-Result Query Tracking & Gap Identification** — Automatically flags queries yielding 0 results (`result_count == 0`), enabling administrators and content managers to identify content gaps, missing documents, or unmapped jargon. · seen in: Algolia `GetSearchesNoResults`, Coveo Content Gap Analytics, Microsoft Search · priority: **table-stakes** · spine: `DocumentSearchQueryLog.is_zero_result` · **buildable now**
- **Popular Searches & Trending Discovery** — Aggregates query telemetry over configurable time windows (last 7 days, 30 days) to calculate top query frequencies, generating "Popular Searches" badges and type-ahead query suggestions. · seen in: Algolia Query Suggestions, Coveo Trending Queries · priority: **common** · spine: Aggregated queries from `DocumentSearchQueryLog` · **buildable now**
- **Enterprise Synonym Dictionary (`DocumentSearchSynonym` - `DSYN`)** — Centralized tenant-wide synonym registry mapping alternative terms and jargon. Supports bidirectional (N-way equivalent: "SOP" $\leftrightarrow$ "Procedure" $\leftrightarrow$ "Standard Operating Procedure") and unidirectional (1-way expansion: "Agreement" $\rightarrow$ "NDA", "SOW", "Contract"). · seen in: Algolia Synonym Management, Coveo Synonym Dictionaries, OpenSearch `synonym_graph` · priority: **table-stakes** · spine: `DocumentSearchSynonym` (`DSYN`) · **buildable now**
- **Synonym-Expanded Search Execution** — Search engine interceptor that expands user query tokens against active synonym entries, ensuring that searching for "NDA" automatically retrieves documents tagged with "Non-Disclosure Agreement" or "Confidentiality Agreement". · seen in: Algolia AI Synonyms, SharePoint Query Rules · priority: **table-stakes** · spine: Query token expansion interceptor in search view · **buildable now**
- **Zero-Result Synonym Suggestion Workbench** — Administrative tool that presents top zero-result search strings alongside quick actions to add them directly into the synonym dictionary or link them to existing taxonomy terms. · seen in: Algolia AI Synonym Suggestions, Coveo Relevance Workbench · priority: **differentiator** · spine: Admin view linking `DocumentSearchQueryLog` to `DocumentSearchSynonym` · **buildable now**

### Beyond the Bullets
- **Unified Discovery & Search Hub Console UI** — Full-page interactive discovery workbench featuring: instant omni-search input, multi-tier facet sidebar drawer, live saved search quick-switch list, query performance badge, exportable result table with thumbnail/metadata cards, and direct document preview modal. · seen in: OpenText Smart View, M-Files Discovery Hub, Box Search · priority: **table-stakes** · spine: Dedicated Search Hub view and template · **buildable now**
- **Click-Through Tracking & Search Precision Telemetry** — Captures which document a user clicks on from a search result page, recording `clicked_document` and `click_rank` on `DocumentSearchQueryLog` to measure search relevance and abandonment rates. · seen in: Algolia Click Analytics, Coveo Click Events · priority: **common** · spine: `DocumentSearchQueryLog.clicked_document`, `click_rank` · **buildable now**
- **Search Results Export & Legal Discovery Package** — One-click export of current search result listings (including metadata, version info, checksums, and author history) to CSV or structured JSON for compliance, e-discovery, and internal audits. · seen in: Laserfiche Export Search Results, OpenText Discovery Export · priority: **common** · spine: Search results CSV streaming view · **buildable now**

---

## Recommended build scope (this pass — 4 models)

1. **`DocumentSavedSearch`** [`DSVD-`] — Persistent saved search criteria, user preferences, and query sharing.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `name` (CharField 150), `slug` (SlugField 160, blank=True), `description` (TextField, blank=True), `query_text` (CharField 255, blank=True, main search string), `criteria_json` (JSONField, default dict: dictionary of structured filters including `document_type`, `classification`, `status`, `owner_id`, `department_id`, `folder_id`, `date_range`, `metadata_filters`), `sort_by` (CharField 40, default "-created_at", choices: `relevance`, `-created_at`, `created_at`, `-updated_at`, `title`, `document_type`), `visibility` (CharField 20, default "private", choices: `private`, `shared_department`, `public`), `shared_department` (FK `core.OrgUnit`, null=True, blank=True, on_delete=models.SET_NULL, related_name="shared_saved_searches"), `is_pinned` (BooleanField, default False), `sort_order` (PositiveIntegerField, default 0), `execution_count` (PositiveIntegerField, default 0), `last_executed_at` (DateTimeField, null=True, blank=True), `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="saved_searches").
   - **Choices**: `VISIBILITY_CHOICES` (`private`, `shared_department`, `public`), `SORT_CHOICES` (`relevance`, `-created_at`, `created_at`, `-updated_at`, `title`, `document_type`).
   - **Justified by**: Persistent Saved Search Definitions, Sharing Controls, Pinned Shortcuts, Search Hub Console.
   - **FKs**: `core.Tenant`, `core.OrgUnit`, `accounts.User`.

2. **`DocumentSearchAlert`** [`DALT-`] — Automated scheduled search alert subscriptions, delta detection, and notifications.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `saved_search` (FK `documents.DocumentSavedSearch`, on_delete=models.CASCADE, related_name="alerts"), `user` (FK `settings.AUTH_USER_MODEL`, on_delete=models.CASCADE, related_name="document_search_alerts"), `title` (CharField 150), `frequency` (CharField 20, default "daily", choices: `realtime`, `daily`, `weekly`, `monthly`), `delivery_channel` (CharField 20, default "in_app", choices: `in_app`, `email`, `both`), `is_active` (BooleanField, default True), `last_checked_at` (DateTimeField, null=True, blank=True), `last_notified_at` (DateTimeField, null=True, blank=True), `last_result_count` (PositiveIntegerField, default 0), `last_result_ids` (JSONField, default list, blank=True, list of document PKs from previous run for delta match detection), `total_notifications_sent` (PositiveIntegerField, default 0), `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="created_search_alerts").
   - **Choices**: `FREQUENCY_CHOICES` (`realtime`, `daily`, `weekly`, `monthly`), `DELIVERY_CHANNEL_CHOICES` (`in_app`, `email`, `both`).
   - **Justified by**: Automated Search Alert Subscriptions, New-Match Delta Detection, Delivery Channel Preferences.
   - **FKs**: `core.Tenant`, `documents.DocumentSavedSearch`, `accounts.User`.

3. **`DocumentSearchSynonym`** [`DSYN-`] — Enterprise synonym dictionary for search-time query token expansion.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `term` (CharField 100, primary source term/keyword, db_index=True), `synonyms` (JSONField, default list: list of alternative matching strings, e.g. `["SOP", "Procedure", "Standard Operating Procedure"]`), `mapping_type` (CharField 20, default "bidirectional", choices: `bidirectional`, `unidirectional`), `category` (CharField 50, blank=True, e.g. "Legal", "Quality", "Technical", "Finance"), `is_active` (BooleanField, default True), `description` (TextField, blank=True), `hit_count` (PositiveIntegerField, default 0, tracks how often this synonym was utilized in searches), `created_by` (FK `settings.AUTH_USER_MODEL`, on_delete=models.PROTECT, related_name="document_search_synonyms").
   - **Choices**: `MAPPING_TYPE_CHOICES` (`bidirectional` - terms are mutually equivalent; `unidirectional` - term expands into synonyms but not reverse).
   - **Constraints**: Unique constraint on `(tenant, term)`.
   - **Justified by**: Enterprise Synonym Dictionary, Query Expansion, Zero-Result Synonym Workbench.
   - **FKs**: `core.Tenant`, `accounts.User`.

4. **`DocumentSearchQueryLog`** [`DQRY-`] — Search telemetry, query strings, execution duration, zero-result tracking, and click precision.
   - **Fields**: `number` (CharField), `tenant` (FK `core.Tenant`), `query_text` (CharField 255, blank=True), `filters_json` (JSONField, default dict, blank=True: captured filter criteria at execution time), `result_count` (PositiveIntegerField, default 0), `execution_time_ms` (PositiveIntegerField, default 0, execution duration in milliseconds), `is_zero_result` (BooleanField, default False, db_index=True), `clicked_document` (FK `documents.Document`, null=True, blank=True, on_delete=models.SET_NULL, related_name="search_clicks"), `click_rank` (PositiveIntegerField, null=True, blank=True, position of clicked result in list), `search_source` (CharField 30, default "search_hub", choices: `search_hub`, `omni_bar`, `saved_search`, `alert_execution`), `user` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True, on_delete=models.SET_NULL, related_name="document_search_logs"), `ip_address` (GenericIPAddressField, null=True, blank=True), `created_at` (DateTimeField, auto_now_add=True, db_index=True).
   - **Choices**: `SEARCH_SOURCE_CHOICES` (`search_hub`, `omni_bar`, `saved_search`, `alert_execution`).
   - **Justified by**: Search Telemetry & Audit Query Logging, Zero-Result Query Tracking, Popular Searches & Trending Discovery, Click-Through Tracking.
   - **FKs**: `core.Tenant`, `documents.Document`, `accounts.User`.

- **Dedicated View / UI Surface:**
  - `Search & Discovery Hub` (`documents:search_hub`): Full-featured discovery console featuring interactive multi-filter form, live facet counts, saved search quick-launcher, natural language query chip parser, query execution telemetry, and zero-result suggestions.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **13.5 Metadata & Indexing** — Metadata schema definition, custom field types, OCR extraction pipelines, and taxonomy controlled vocabulary (built in 13.5).
- **13.7 Document Security & Access Control** — Granular document-level and folder-level permission enforcement (read/write/delete/download/print), dynamic watermarking overlays, DRM encryption, and DLP content inspection.
- **13.8 Collaboration & Sharing** — External secure links, password-protected sharing, co-authoring presence.
- **13.9 Records Management & Compliance** — Automatic legal hold placement triggered by search queries, retention schedules, and disposition certification.
- **13.10 Audit Trail & Reporting** — Immutable document lifecycle event audit trail (who viewed, downloaded, printed, or exported documents).
- **13.16 Contract Lifecycle Management (CLM)** — Specialized contract clause search, contract term extraction, and contract obligation tracking.
- **13.17 Knowledge Management & Wikis** — Wiki article full-text search, FAQ indexing, and cross-wiki knowledge graph linking.

---

## Deferred (later passes / integrations)

- **Vector Database & Dense Semantic Retrieval** — External vector database integration (e.g. pgvector, Pinecone, Qdrant) with embedding models for dense semantic vector search and hybrid keyword-vector reciprocal rank fusion (RRF).
- **Conversational RAG (Retrieval-Augmented Generation) Assistant** — Generative AI question answering that synthesizes natural language answers from retrieved document passages with inline citations.
- **Real-Time WebSocket Percolator Feeds** — Live websocket push notifications that stream new document matches to open client browser tabs immediately upon document publication.
- **External Federated Search Connectors** — Federated search crawlers indexing external repositories (SharePoint Online, Google Drive, Box, network file shares) via 13.12 Integration & API Ecosystem.
