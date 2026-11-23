# Module 13.6 Pre-Build Contract — Search & Discovery (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.6"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0009_...`)
- **Package Directories**:
  - `apps/documents/models/SearchDiscovery/`
  - `apps/documents/forms/SearchDiscovery/`
  - `apps/documents/views/SearchDiscovery/`
  - `apps/documents/urls/SearchDiscovery/`
  - `templates/documents/search_discovery/{document_saved_search,document_search_alert,document_search_synonym,document_search_query_log}/{list,detail,form}.html` + `search_hub.html` + `analytics.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"execute"`, `"toggle"`, `"subscribe"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentSavedSearch`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/SearchDiscovery/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentSavedSearch` (`DocumentSavedSearches.py`)
- **`NUMBER_PREFIX`**: `"DSVD"`
- **`Meta.ordering`**: `["-is_pinned", "-updated_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Saved Search"` / `"Saved Searches"`
- **Choices & Badge Maps**:
  - `VISIBILITY_CHOICES` (`max_length=25`):
    - `("private", "Private (Only Me)")`
    - `("shared_department", "Department Shared")`
    - `("public", "Public (All Users)")`
  - `SORT_BY_CHOICES` (`max_length=30`):
    - `("relevance", "Best Match / Relevance")`
    - `("updated_at_desc", "Recently Updated")`
    - `("created_at_desc", "Recently Created")`
    - `("title_asc", "Title (A-Z)")`
    - `("size_desc", "File Size (Largest)")`
  - `SORT_ORDER_CHOICES` (`max_length=10`):
    - `("asc", "Ascending")`
    - `("desc", "Descending")`
  - `VISIBILITY_CSS`:
    - `"private": "badge-slate"`
    - `"shared_department": "badge-info"`
    - `"public": "badge-green"`
  - `STATUS_CSS`:
    - `True: "badge-green"`
    - `False: "badge-slate"`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=150)`
  - `slug`: `SlugField(max_length=160, blank=True)`
  - `description`: `TextField(blank=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_saved_searches")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="department_saved_searches")`
  - `visibility`: `CharField(max_length=25, choices=VISIBILITY_CHOICES, default="private", db_index=True)`
  - `query_text`: `CharField(max_length=500, blank=True)`
  - `filters_json`: `TextField(blank=True, default="{}")`
  - `facet_filters_json`: `TextField(blank=True, default="{}")`
  - `sort_by`: `CharField(max_length=30, choices=SORT_BY_CHOICES, default="relevance")`
  - `sort_order`: `CharField(max_length=10, choices=SORT_ORDER_CHOICES, default="desc")`
  - `is_pinned`: `BooleanField(default=False, db_index=True)`
  - `is_favorite`: `BooleanField(default=False, db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `run_count`: `PositiveIntegerField(default=0)`
  - `total_results_last_run`: `PositiveIntegerField(default=0)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dsvd_ten_num_uniq")` (21 chars)
  - `Index(fields=["tenant", "owner", "is_pinned"], name="doc_dsvd_tnt_own_pin_idx")` (24 chars)
  - `Index(fields=["tenant", "visibility", "is_active"], name="doc_dsvd_tnt_vis_act_idx")` (24 chars)

### 1.2 `DocumentSearchAlert` (`DocumentSearchAlerts.py`)
- **`NUMBER_PREFIX`**: `"DALT"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Search Alert"` / `"Search Alerts"`
- **Choices & Badge Maps**:
  - `FREQUENCY_CHOICES` (`max_length=20`):
    - `("realtime", "Immediate / Real-time")`
    - `("daily", "Daily Digest")`
    - `("weekly", "Weekly Digest")`
    - `("monthly", "Monthly Digest")`
  - `DELIVERY_CHOICES` (`max_length=20`):
    - `("in_app", "In-App Notification")`
    - `("email", "Email Notification")`
    - `("both", "In-App & Email")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("active", "Active")`
    - `("paused", "Paused")`
    - `("failed", "Delivery Failed")`
  - `FREQUENCY_CSS`:
    - `"realtime": "badge-green"`
    - `"daily": "badge-info"`
    - `"weekly": "badge-amber"`
    - `"monthly": "badge-slate"`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"paused": "badge-amber"`
    - `"failed": "badge-red"`
  - `DELIVERY_CSS`:
    - `"in_app": "badge-info"`
    - `"email": "badge-green"`
    - `"both": "badge-amber"`
- **Fields (exact names & types)**:
  - `saved_search`: `ForeignKey("documents.DocumentSavedSearch", on_delete=models.CASCADE, related_name="alerts")`
  - `subscriber`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_search_alerts")`
  - `frequency`: `CharField(max_length=20, choices=FREQUENCY_CHOICES, default="daily", db_index=True)`
  - `delivery_channel`: `CharField(max_length=20, choices=DELIVERY_CHOICES, default="in_app")`
  - `last_notified_at`: `DateTimeField(null=True, blank=True)`
  - `last_checked_at`: `DateTimeField(null=True, blank=True)`
  - `new_matches_count`: `PositiveIntegerField(default=0)`
  - `last_result_ids`: `TextField(blank=True, default="[]")`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dalt_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "saved_search", "subscriber"], name="doc_dalt_tnt_svd_sub_uniq")` (25 chars)
  - `Index(fields=["tenant", "frequency", "status"], name="doc_dalt_tnt_frq_stat_idx")` (25 chars)

### 1.3 `DocumentSearchSynonym` (`DocumentSearchSynonyms.py`)
- **`NUMBER_PREFIX`**: `"DSYN"`
- **`Meta.ordering`**: `["term"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Search Synonym"` / `"Search Synonyms"`
- **Choices & Badge Maps**:
  - `CATEGORY_CHOICES` (`max_length=25`):
    - `("general", "General Synonym")`
    - `("acronym", "Acronym / Abbreviation")`
    - `("domain", "Domain & Industry Jargon")`
    - `("spelling", "Spelling & Variant")`
  - `CATEGORY_CSS`:
    - `"general": "badge-info"`
    - `"acronym": "badge-green"`
    - `"domain": "badge-amber"`
    - `"spelling": "badge-slate"`
  - `STATUS_CSS`:
    - `True: "badge-green"`
    - `False: "badge-slate"`
- **Fields (exact names & types)**:
  - `term`: `CharField(max_length=100, db_index=True)`
  - `synonyms`: `TextField(help_text="Comma-separated synonyms or expansion words")`
  - `category`: `CharField(max_length=25, choices=CATEGORY_CHOICES, default="general", db_index=True)`
  - `is_bidirectional`: `BooleanField(default=True, help_text="True for two-way; False for one-way")`
  - `language`: `CharField(max_length=10, default="en")`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_search_synonyms")`
  - `hit_count`: `PositiveIntegerField(default=0)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dsyn_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "term", "language"], name="doc_dsyn_tnt_trm_lng_uniq")` (25 chars)
  - `Index(fields=["tenant", "category", "is_active"], name="doc_dsyn_tnt_cat_act_idx")` (24 chars)

### 1.4 `DocumentSearchQueryLog` (`DocumentSearchQueryLogs.py`)
- **`NUMBER_PREFIX`**: `"DQRY"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Search Query Log"` / `"Search Query Logs"`
- **Choices & Badge Maps**:
  - `SOURCE_CHOICES` (`max_length=25`):
    - `("search_hub", "Search & Discovery Hub")`
    - `("quick_search", "Header Quick Search")`
    - `("saved_search", "Saved Search Run")`
    - `("alert_cron", "Automated Alert Job")`
  - `SOURCE_CSS`:
    - `"search_hub": "badge-info"`
    - `"quick_search": "badge-green"`
    - `"saved_search": "badge-amber"`
    - `"alert_cron": "badge-slate"`
  - `ZERO_RESULT_CSS`:
    - `True: "badge-red"` (Zero Results)
    - `False: "badge-green"` (Matched)
- **Fields (exact names & types)**:
  - `query_text`: `CharField(max_length=500, db_index=True)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="document_search_queries")`
  - `filters_applied_json`: `TextField(blank=True, default="{}")`
  - `results_count`: `PositiveIntegerField(default=0, db_index=True)`
  - `is_zero_result`: `BooleanField(default=False, db_index=True)`
  - `execution_time_ms`: `PositiveIntegerField(default=0)`
  - `search_source`: `CharField(max_length=25, choices=SOURCE_CHOICES, default="search_hub", db_index=True)`
  - `clicked_document`: `ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="search_query_clicks")`
  - `click_rank`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `ip_address`: `CharField(max_length=45, blank=True)`
  - `session_key`: `CharField(max_length=64, blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dqry_ten_num_uniq")` (21 chars)
  - `Index(fields=["tenant", "is_zero_result", "-created_at"], name="doc_dqry_tnt_zero_crt_idx")` (25 chars)
  - `Index(fields=["tenant", "query_text"], name="doc_dqry_tnt_qry_idx")` (20 chars)

---

## 2. Forms Contract (`apps/documents/forms/SearchDiscovery/`)

### 2.1 `DocumentSavedSearchForm` (`DocumentSavedSearches.py`)
- **`Meta.model`**: `DocumentSavedSearch`
- **`Meta.fields`**: `["name", "description", "department", "visibility", "query_text", "filters_json", "facet_filters_json", "sort_by", "sort_order", "is_pinned", "is_favorite", "is_active"]`
- **Excluded Fields**: `tenant`, `number`, `owner`, `last_run_at`, `run_count`, `total_results_last_run`, `created_at`, `updated_at`.
- **Form Init**: Filters `department` queryset by `tenant=self.tenant`.
- **Form Clean**: Validates JSON formatting of `filters_json` and `facet_filters_json`, prevents cross-tenant department FK via `reject_foreign`.

### 2.2 `DocumentSearchAlertForm` (`DocumentSearchAlerts.py`)
- **`Meta.model`**: `DocumentSearchAlert`
- **`Meta.fields`**: `["saved_search", "frequency", "delivery_channel", "status", "notes", "is_active"]`
- **Excluded Fields**: `tenant`, `number`, `subscriber`, `last_notified_at`, `last_checked_at`, `new_matches_count`, `last_result_ids`, `created_at`, `updated_at`.
- **Form Init**: Filters `saved_search` queryset by `tenant=self.tenant` and (owner=request.user OR visibility in ['public', 'shared_department']).
- **Form Clean**: Validates `saved_search` tenant match via `reject_foreign`.

### 2.3 `DocumentSearchSynonymForm` (`DocumentSearchSynonyms.py`)
- **`Meta.model`**: `DocumentSearchSynonym`
- **`Meta.fields`**: `["term", "synonyms", "category", "is_bidirectional", "language", "is_active"]`
- **Excluded Fields**: `tenant`, `number`, `created_by`, `hit_count`, `created_at`, `updated_at`.
- **Form Clean**: Strips and normalizes comma-separated synonyms, removes duplicate terms, checks circular or self-synonyms.

### 2.4 `DocumentSearchQueryLogForm` (`DocumentSearchQueryLogs.py`)
- Read-only audit log form / filter representation.
- **`Meta.model`**: `DocumentSearchQueryLog`
- **`Meta.fields`**: `["query_text", "search_source", "results_count", "is_zero_result", "execution_time_ms"]`
- Model is created programmatically during searches; form is used only for administrative inspection or filter display.

---

## 3. URLs Contract (`apps/documents/urls/SearchDiscovery/`)

All URL patterns live in `apps/documents/urls/SearchDiscovery/<Entity>.py` and are imported into `apps/documents/urls/__init__.py`. Literal routes precede `<int:pk>` patterns.

### 3.1 Search Hub (`SearchHub.py`)
- `path("search/", views.search_hub, name="search_hub")`
- `path("search/click/<int:pk>/", views.search_click_track, name="search_click_track")`
- `path("search/export/", views.search_export_csv, name="search_export_csv")`

### 3.2 DocumentSavedSearch (`DocumentSavedSearches.py`)
- `path("saved-searches/", views.document_saved_search_list, name="document_saved_search_list")`
- `path("saved-searches/create/", views.document_saved_search_create, name="document_saved_search_create")`
- `path("saved-searches/<int:pk>/", views.document_saved_search_detail, name="document_saved_search_detail")`
- `path("saved-searches/<int:pk>/edit/", views.document_saved_search_edit, name="document_saved_search_edit")`
- `path("saved-searches/<int:pk>/delete/", views.document_saved_search_delete, name="document_saved_search_delete")`
- `path("saved-searches/<int:pk>/run/", views.document_saved_search_run, name="document_saved_search_run")`
- `path("saved-searches/<int:pk>/toggle-pin/", views.document_saved_search_toggle_pin, name="document_saved_search_toggle_pin")`

### 3.3 DocumentSearchAlert (`DocumentSearchAlerts.py`)
- `path("search-alerts/", views.document_search_alert_list, name="document_search_alert_list")`
- `path("search-alerts/create/", views.document_search_alert_create, name="document_search_alert_create")`
- `path("search-alerts/<int:pk>/", views.document_search_alert_detail, name="document_search_alert_detail")`
- `path("search-alerts/<int:pk>/edit/", views.document_search_alert_edit, name="document_search_alert_edit")`
- `path("search-alerts/<int:pk>/delete/", views.document_search_alert_delete, name="document_search_alert_delete")`
- `path("search-alerts/<int:pk>/toggle-active/", views.document_search_alert_toggle_active, name="document_search_alert_toggle_active")`
- `path("search-alerts/<int:pk>/run-check/", views.document_search_alert_run_check, name="document_search_alert_run_check")`

### 3.4 DocumentSearchSynonym (`DocumentSearchSynonyms.py`)
- `path("search-synonyms/", views.document_search_synonym_list, name="document_search_synonym_list")`
- `path("search-synonyms/create/", views.document_search_synonym_create, name="document_search_synonym_create")`
- `path("search-synonyms/<int:pk>/", views.document_search_synonym_detail, name="document_search_synonym_detail")`
- `path("search-synonyms/<int:pk>/edit/", views.document_search_synonym_edit, name="document_search_synonym_edit")`
- `path("search-synonyms/<int:pk>/delete/", views.document_search_synonym_delete, name="document_search_synonym_delete")`

### 3.5 DocumentSearchQueryLog (`DocumentSearchQueryLogs.py`)
- `path("search-logs/", views.document_search_query_log_list, name="document_search_query_log_list")`
- `path("search-logs/analytics/", views.document_search_analytics, name="document_search_analytics")`
- `path("search-logs/<int:pk>/", views.document_search_query_log_detail, name="document_search_query_log_detail")`
- `path("search-logs/<int:pk>/delete/", views.document_search_query_log_delete, name="document_search_query_log_delete")`

---

## 4. Views & Context Keys Contract (`apps/documents/views/SearchDiscovery/`)

Every view enforces `@login_required`, scopes queries with `tenant=request.tenant`, writes an `AuditLog` row via `write_audit_log` (`action <= 10` chars), and provides exact template context keys.

### 4.1 Search Hub (`search_hub`)
- **Template**: `templates/documents/search_discovery/search_hub.html`
- **Context Keys**:
  - `page_obj`: paginated document/version matches
  - `results_count`: int total matches
  - `query_text`: str raw query
  - `facets`: dict of facet options with counts:
    - `document_types`: list of dicts `{value, label, count, selected}`
    - `classifications`: list of dicts `{value, label, count, selected}`
    - `statuses`: list of dicts `{value, label, count, selected}`
    - `authors`: list of dicts `{id, name, count, selected}`
    - `folders`: list of dicts `{id, name, count, selected}`
    - `extensions`: list of dicts `{ext, count, selected}`
  - `active_filters`: dict of currently applied facet parameters
  - `nlp_intent_chips`: list of intent tokens parsed from natural language query
  - `popular_searches`: list of top query strings from query log
  - `saved_searches`: queryset of user's pinned/recent saved searches
  - `zero_result_suggestions`: list of suggestion strings if `results_count == 0`
  - `synonyms_applied`: list of synonyms applied in query expansion
  - `execution_time_ms`: int duration in ms
  - `sort_by`: str current sort selection

### 4.2 DocumentSavedSearch Views
- `document_saved_search_list`:
  - **Template**: `templates/documents/search_discovery/document_saved_search/list.html`
  - **Context Keys**: `saved_searches` (or `page_obj`), `visibility_choices`, `sort_by_choices`, `status_choices`, `total_count`
- `document_saved_search_detail`:
  - **Template**: `templates/documents/search_discovery/document_saved_search/detail.html`
  - **Context Keys**: `saved_search`, `alerts`, `parsed_filters`
- `document_saved_search_create` & `document_saved_search_edit`:
  - **Template**: `templates/documents/search_discovery/document_saved_search/form.html`
  - **Context Keys**: `form`, `saved_search` (None for create), `is_edit`

### 4.3 DocumentSearchAlert Views
- `document_search_alert_list`:
  - **Template**: `templates/documents/search_discovery/document_search_alert/list.html`
  - **Context Keys**: `search_alerts` (or `page_obj`), `frequency_choices`, `delivery_choices`, `status_choices`, `total_count`
- `document_search_alert_detail`:
  - **Template**: `templates/documents/search_discovery/document_search_alert/detail.html`
  - **Context Keys**: `search_alert`, `matched_documents`
- `document_search_alert_create` & `document_search_alert_edit`:
  - **Template**: `templates/documents/search_discovery/document_search_alert/form.html`
  - **Context Keys**: `form`, `search_alert` (None for create), `is_edit`

### 4.4 DocumentSearchSynonym Views
- `document_search_synonym_list`:
  - **Template**: `templates/documents/search_discovery/document_search_synonym/list.html`
  - **Context Keys**: `search_synonyms` (or `page_obj`), `category_choices`, `status_choices`, `total_count`
- `document_search_synonym_detail`:
  - **Template**: `templates/documents/search_discovery/document_search_synonym/detail.html`
  - **Context Keys**: `search_synonym`, `expanded_terms_list`
- `document_search_synonym_create` & `document_search_synonym_edit`:
  - **Template**: `templates/documents/search_discovery/document_search_synonym/form.html`
  - **Context Keys**: `form`, `search_synonym` (None for create), `is_edit`

### 4.5 DocumentSearchQueryLog Views
- `document_search_query_log_list`:
  - **Template**: `templates/documents/search_discovery/document_search_query_log/list.html`
  - **Context Keys**: `query_logs` (or `page_obj`), `source_choices`, `total_count`, `zero_result_count`
- `document_search_query_log_detail`:
  - **Template**: `templates/documents/search_discovery/document_search_query_log/detail.html`
  - **Context Keys**: `query_log`, `parsed_filters`
- `document_search_analytics`:
  - **Template**: `templates/documents/search_discovery/document_search_query_log/analytics.html`
  - **Context Keys**: `total_searches`, `zero_result_searches`, `zero_result_rate`, `avg_latency_ms`, `top_queries`, `zero_result_queries`, `source_breakdown`

---

## 5. Navigation `LIVE_LINKS["13.6"]` Contract

In `apps/core/navigation.py`:

```python
LIVE_LINKS["13.6"] = {
    "Advanced Search & Filters": "documents:search_hub",
    "Faceted Search Navigation": "documents:search_hub",
    "Saved Searches & Alerts": "documents:document_saved_search_list",
    "Natural Language Query & AI Search": "documents:search_hub",
    "Search Analytics & Query Optimization": "documents:document_search_analytics",
    # Extra live leaves:
    "Search Alerts": "documents:document_search_alert_list",
    "Search Synonyms": "documents:document_search_synonym_list",
    "Search Query Logs": "documents:document_search_query_log_list",
}
```

---

## 6. Seeder Contract (`apps/documents/management/commands/seed_documents.py`)

- Guarded by tenant `if DocumentSavedSearch.objects.filter(tenant=tenant).exists():`
- Creates realistic demonstration data for Acme Corp & Globex:
  - 4 `DocumentSavedSearch` instances (e.g. "Active Confidential Contracts", "Recent Technical SOPs", "Marketing Brand Assets", "Pending Quality Audits")
  - 4 `DocumentSearchAlert` instances across different frequencies (`daily`, `realtime`, `weekly`)
  - 6 `DocumentSearchSynonym` instances (e.g. "SOP, standard operating procedure, procedure", "NDA, non-disclosure agreement, confidentiality agreement", "PO, purchase order, procurement", "MSA, master services agreement, contract")
  - 10 `DocumentSearchQueryLog` instances simulating popular searches, zero-result queries, and latency metrics.
