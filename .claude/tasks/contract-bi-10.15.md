# Contract — Sub-module 10.15: Natural Language & Conversational BI (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.15 Natural Language & Conversational BI • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-07 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.14). Incremental migration: `0034_...` (previous leaf: `0033_smartdataprepsuggestion_idx_bsdp_ten_created.py`).
- **Package Layout:** `ConversationalBi/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/conversational_bi/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `NaturalLanguageQuery` (`apps/bi/models/ConversationalBi/NaturalLanguageQueries.py`)
- **Table:** `bi_natural_language_query`
- **Number Prefix:** `BNLQ` (`BNLQ-00001`)
- **CHOICES:**
  - `INPUT_MODALITY_CHOICES = [('text', 'Typed Text Query'), ('voice', 'Spoken Voice Query'), ('api', 'External API / Webhook')]`
  - `INTENT_TYPE_CHOICES = [('metric_lookup', 'Metric Value Lookup'), ('trend_analysis', 'Trend & Time-Series Analysis'), ('ranking_top_bottom', 'Top / Bottom Ranking'), ('comparative_analysis', 'Dimensional Comparison'), ('distribution', 'Data Distribution & Histogram'), ('correlation', 'Measure Correlation'), ('drill_down', 'Hierarchical Drill-Down')]`
  - `CHART_TYPE_CHOICES = [('metric_card', 'Single KPI Metric Card'), ('bar_chart', 'Vertical Bar Chart'), ('horizontal_bar', 'Horizontal Bar Chart'), ('line_chart', 'Time-Series Line Chart'), ('donut_chart', 'Proportional Donut Chart'), ('scatter_plot', 'Correlation Scatter Plot'), ('pivot_table', 'Multi-Level Pivot Matrix'), ('data_table', 'Tabular Record Grid')]`
  - `EXECUTION_STATUS_CHOICES = [('pending', 'Pending Execution'), ('completed', 'Completed Successfully'), ('failed', 'Execution Failed'), ('ambiguous', 'Ambiguous Query / Clarification Needed')]`
  - `USER_RATING_CHOICES = [('unrated', 'Unrated'), ('helpful', 'Helpful / Accurate'), ('unhelpful', 'Unhelpful / Inaccurate')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `query_text`: `CharField(max_length=500, help_text="Plain-language analytical question asked by user")`
  - `input_modality`: `CharField(max_length=16, choices=INPUT_MODALITY_CHOICES, default='text')`
  - `intent_type`: `CharField(max_length=24, choices=INTENT_TYPE_CHOICES, default='metric_lookup')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='nlq_queries')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='nlq_queries')`
  - `kpi_definition`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='nlq_queries')`
  - `conversation_session`: `ForeignKey('bi.BiConversationSession', null=True, blank=True, on_delete=models.SET_NULL, related_name='queries')`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='nlq_queries')`
  - `parsed_measures`: `JSONField(default=list, blank=True, help_text="List of extracted metrics / aggregations")`
  - `parsed_dimensions`: `JSONField(default=list, blank=True, help_text="List of extracted grouping dimensions")`
  - `parsed_filters`: `JSONField(default=dict, blank=True, help_text="Dictionary of extracted filter conditions")`
  - `generated_sql`: `TextField(blank=True, help_text="Executable SQL or ORM expression generated from intent")`
  - `chart_type`: `CharField(max_length=20, choices=CHART_TYPE_CHOICES, default='bar_chart')`
  - `chart_config`: `JSONField(default=dict, blank=True, help_text="Chart.js visualization payload")`
  - `result_summary`: `JSONField(default=dict, blank=True, help_text="Tabular data payload or summarized metric cards")`
  - `confidence_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('85.00'), help_text="Intent mapping confidence percentage")`
  - `execution_status`: `CharField(max_length=16, choices=EXECUTION_STATUS_CHOICES, default='completed')`
  - `execution_duration_ms`: `IntegerField(default=0, help_text="Query parsing and data retrieval latency in milliseconds")`
  - `audio_duration_seconds`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Voice audio input duration in seconds")`
  - `user_rating`: `CharField(max_length=16, choices=USER_RATING_CHOICES, default='unrated')`
  - `user_feedback_notes`: `TextField(blank=True, help_text="User explanation if rating is unhelpful")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bnlq_tenant_num_uniq')`
  - `Index(fields=['tenant', 'input_modality'], name='idx_bnlq_ten_mod')`
  - `Index(fields=['tenant', 'intent_type'], name='idx_bnlq_ten_intent')`
  - `Index(fields=['tenant', 'execution_status'], name='idx_bnlq_ten_status')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bnlq_ten_created')`

---

### 1.2 `BiConversationSession` (`apps/bi/models/ConversationalBi/BiConversationSessions.py`)
- **Table:** `bi_conversation_session`
- **Number Prefix:** `BCON` (`BCON-00001`)
- **CHOICES:**
  - `SESSION_STATUS_CHOICES = [('active', 'Active Chat Thread'), ('closed', 'Closed Session'), ('archived', 'Archived Conversation')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200, help_text="Conversational thread topic / headline")`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bi_conversations')`
  - `session_status`: `CharField(max_length=16, choices=SESSION_STATUS_CHOICES, default='active')`
  - `is_pinned`: `BooleanField(default=False, help_text="Pin session to top of user's conversation drawer")`
  - `primary_semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_conversations')`
  - `primary_dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_conversations')`
  - `context_state`: `JSONField(default=dict, blank=True, help_text="Active filter criteria, pinned date ranges, and dimensional anchors")`
  - `suggested_prompts`: `JSONField(default=list, blank=True, help_text="Contextual follow-up and clarification question chips")`
  - `message_count`: `PositiveIntegerField(default=0, help_text="Total number of conversational query exchanges in thread")`
  - `last_interaction_at`: `DateTimeField(auto_now=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bcon_tenant_num_uniq')`
  - `Index(fields=['tenant', 'session_status'], name='idx_bcon_ten_stat')`
  - `Index(fields=['tenant', 'user'], name='idx_bcon_ten_usr')`
  - `Index(fields=['tenant', 'is_pinned'], name='idx_bcon_ten_pin')`
  - `Index(fields=['tenant', 'last_interaction_at'], name='idx_bcon_ten_interact')`

---

### 1.3 `NarrativeExplanation` (`apps/bi/models/ConversationalBi/NarrativeExplanations.py`)
- **Table:** `bi_narrative_explanation`
- **Number Prefix:** `BNLG` (`BNLG-00001`)
- **CHOICES:**
  - `TARGET_ARTIFACT_TYPE_CHOICES = [('dashboard', 'Executive Dashboard'), ('report', 'Operational Report'), ('kpi_scorecard', 'KPI Scorecard'), ('query_result', 'Natural Language Query Result'), ('custom_dataset', 'Custom Analytical Dataset')]`
  - `NARRATIVE_STYLE_CHOICES = [('executive_briefing', 'Executive Briefing (High-Level Summary)'), ('analytical_deepdive', 'Analytical Deep Dive (Detailed Variance Analysis)'), ('bulleted_highlights', 'Bulleted Key Highlights'), ('anomaly_alert', 'Statistical Anomaly Alert'), ('spoken_voice_script', 'Spoken Voice Audio Script')]`
  - `STATUS_CHOICES = [('draft', 'Draft Narrative'), ('generated', 'Machine-Generated'), ('reviewed', 'Analyst Reviewed'), ('published', 'Published & Distributed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `headline`: `CharField(max_length=255, help_text="Attention-grabbing single-sentence executive insight")`
  - `target_artifact_type`: `CharField(max_length=24, choices=TARGET_ARTIFACT_TYPE_CHOICES, default='dashboard')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='narrative_explanations')`
  - `report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='narrative_explanations')`
  - `kpi`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='narrative_explanations')`
  - `query`: `ForeignKey('bi.NaturalLanguageQuery', null=True, blank=True, on_delete=models.SET_NULL, related_name='narrative_explanations')`
  - `insight`: `ForeignKey('bi.AugmentedInsight', null=True, blank=True, on_delete=models.SET_NULL, related_name='narrative_explanations')`
  - `narrative_style`: `CharField(max_length=24, choices=NARRATIVE_STYLE_CHOICES, default='executive_briefing')`
  - `narrative_body`: `TextField(help_text="Formatted natural language commentary with metric callouts")`
  - `key_takeaways`: `JSONField(default=list, blank=True, help_text="List of bulleted key takeaway strings")`
  - `top_positive_driver`: `CharField(max_length=150, blank=True, help_text="Primary positive contributor to variance")`
  - `top_negative_driver`: `CharField(max_length=150, blank=True, help_text="Primary drag/negative contributor to variance")`
  - `audio_ready_script`: `TextField(blank=True, help_text="Pronunciation-optimized text formatted for speech synthesis audio")`
  - `language`: `CharField(max_length=8, default='en')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='generated')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_narratives')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bnlg_tenant_num_uniq')`
  - `Index(fields=['tenant', 'target_artifact_type'], name='idx_bnlg_ten_art')`
  - `Index(fields=['tenant', 'narrative_style'], name='idx_bnlg_ten_style')`
  - `Index(fields=['tenant', 'status'], name='idx_bnlg_ten_stat')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bnlg_ten_created')`

---

### 1.4 `SearchDiscoveryIndex` (`apps/bi/models/ConversationalBi/SearchDiscoveryIndexes.py`)
- **Table:** `bi_search_discovery_index`
- **Number Prefix:** `BSDI` (`BSDI-00001`)
- **CHOICES:**
  - `ASSET_TYPE_CHOICES = [('dashboard', 'Dashboard View'), ('report', 'Operational Report'), ('kpi', 'KPI / Metric Definition'), ('semantic_model', 'Semantic Dataset'), ('warehouse_table', 'Data Warehouse Table'), ('glossary_term', 'Business Glossary Term'), ('ad_hoc_query', 'Saved Ad-Hoc Analysis')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `asset_name`: `CharField(max_length=200)`
  - `asset_type`: `CharField(max_length=24, choices=ASSET_TYPE_CHOICES, default='dashboard')`
  - `target_url`: `CharField(max_length=255, help_text="Route or link pointing to indexed asset")`
  - `description`: `TextField(blank=True, help_text="Brief summary of asset purpose")`
  - `category`: `CharField(max_length=64, blank=True, help_text="Functional domain e.g. Finance, Sales, Operations, HR")`
  - `synonyms`: `JSONField(default=list, blank=True, help_text="List of colloquial aliases, e.g. ['sales', 'revenue', 'turnover']")`
  - `search_keywords`: `TextField(blank=True, help_text="Space or comma-delimited tokens indexed for search discovery")`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='discovery_indexes')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='discovery_indexes')`
  - `report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='discovery_indexes')`
  - `kpi`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='discovery_indexes')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='discovery_indexes')`
  - `glossary_term`: `ForeignKey('bi.BusinessGlossaryTerm', null=True, blank=True, on_delete=models.SET_NULL, related_name='discovery_indexes')`
  - `relevance_weight`: `DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.00'), help_text="Multiplier boost for ranking relevance")`
  - `search_hit_count`: `PositiveIntegerField(default=0, help_text="Telemetry count of discovery queries matching this asset")`
  - `view_count`: `PositiveIntegerField(default=0, help_text="Telemetry count of click-throughs from search")`
  - `is_featured`: `BooleanField(default=False, help_text="Pin to curated recommended discovery cards")`
  - `is_verified`: `BooleanField(default=True, help_text="Verified enterprise asset badge")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsdi_tenant_num_uniq')`
  - `Index(fields=['tenant', 'asset_type'], name='idx_bsdi_ten_type')`
  - `Index(fields=['tenant', 'category'], name='idx_bsdi_ten_cat')`
  - `Index(fields=['tenant', 'is_featured'], name='idx_bsdi_ten_feat')`
  - `Index(fields=['tenant', 'is_verified'], name='idx_bsdi_ten_ver')`

---

## 2. Forms Contract & Field Exclusions

All forms inherit from `apps.bi.forms._common.TenantModelForm` and enforce `TenantUniqueMixin` / `reject_foreign`.

### 2.1 `NaturalLanguageQueryForm`
- **Fields:** `query_text`, `input_modality`, `intent_type`, `semantic_model`, `warehouse_table`, `kpi_definition`, `conversation_session`, `chart_type`, `user_rating`, `user_feedback_notes`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `user`, `parsed_measures`, `parsed_dimensions`, `parsed_filters`, `generated_sql`, `chart_config`, `result_summary`, `confidence_score`, `execution_status`, `execution_duration_ms`, `audio_duration_seconds`

### 2.2 `BiConversationSessionForm`
- **Fields:** `title`, `session_status`, `is_pinned`, `primary_semantic_model`, `primary_dashboard`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `user`, `context_state`, `suggested_prompts`, `message_count`, `last_interaction_at`

### 2.3 `NarrativeExplanationForm`
- **Fields:** `title`, `headline`, `target_artifact_type`, `dashboard`, `report`, `kpi`, `query`, `insight`, `narrative_style`, `narrative_body`, `top_positive_driver`, `top_negative_driver`, `language`, `status`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `created_by`, `audio_ready_script`, `key_takeaways`

### 2.4 `SearchDiscoveryIndexForm`
- **Fields:** `asset_name`, `asset_type`, `target_url`, `description`, `category`, `synonyms`, `search_keywords`, `semantic_model`, `dashboard`, `report`, `kpi`, `warehouse_table`, `glossary_term`, `relevance_weight`, `is_featured`, `is_verified`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `search_hit_count`, `view_count`

---

## 3. URLs Contract

All routes defined under `apps/bi/urls/ConversationalBi/<Entity>.py` and aggregated in `apps/bi/urls/ConversationalBi/__init__.py`.

```python
# NaturalLanguageQueries
path('natural-language-queries/', views.natural_language_query_list, name='natural_language_query_list'),
path('natural-language-queries/create/', views.natural_language_query_create, name='natural_language_query_create'),
path('natural-language-queries/<int:pk>/', views.natural_language_query_detail, name='natural_language_query_detail'),
path('natural-language-queries/<int:pk>/edit/', views.natural_language_query_edit, name='natural_language_query_edit'),
path('natural-language-queries/<int:pk>/delete/', views.natural_language_query_delete, name='natural_language_query_delete'),
path('natural-language-queries/<int:pk>/rate/', views.natural_language_query_rate, name='natural_language_query_rate'),

# BiConversationSessions
path('conversations/', views.bi_conversation_session_list, name='bi_conversation_session_list'),
path('conversations/workspace/', views.bi_chat_workspace, name='bi_chat_workspace'),
path('conversations/create/', views.bi_conversation_session_create, name='bi_conversation_session_create'),
path('conversations/<int:pk>/', views.bi_conversation_session_detail, name='bi_conversation_session_detail'),
path('conversations/<int:pk>/edit/', views.bi_conversation_session_edit, name='bi_conversation_session_edit'),
path('conversations/<int:pk>/delete/', views.bi_conversation_session_delete, name='bi_conversation_session_delete'),
path('conversations/<int:pk>/toggle-pin/', views.bi_conversation_session_toggle_pin, name='bi_conversation_session_toggle_pin'),
path('conversations/<int:pk>/close/', views.bi_conversation_session_close, name='bi_conversation_session_close'),
path('conversations/<int:pk>/ask/', views.bi_conversation_session_ask, name='bi_conversation_session_ask'),
path('conversations/workspace/', views.bi_chat_workspace, name='bi_chat_workspace'),

# NarrativeExplanations
path('narratives/', views.narrative_explanation_list, name='narrative_explanation_list'),
path('narratives/create/', views.narrative_explanation_create, name='narrative_explanation_create'),
path('narratives/<int:pk>/', views.narrative_explanation_detail, name='narrative_explanation_detail'),
path('narratives/<int:pk>/edit/', views.narrative_explanation_edit, name='narrative_explanation_edit'),
path('narratives/<int:pk>/delete/', views.narrative_explanation_delete, name='narrative_explanation_delete'),
path('narratives/<int:pk>/publish/', views.narrative_explanation_publish, name='narrative_explanation_publish'),
path('narratives/<int:pk>/regenerate/', views.narrative_explanation_regenerate, name='narrative_explanation_regenerate'),

# SearchDiscoveryIndexes
path('search-discovery/', views.search_discovery_index_list, name='search_discovery_index_list'),
path('search-discovery/create/', views.search_discovery_index_create, name='search_discovery_index_create'),
path('search-discovery/<int:pk>/', views.search_discovery_index_detail, name='search_discovery_index_detail'),
path('search-discovery/<int:pk>/edit/', views.search_discovery_index_edit, name='search_discovery_index_edit'),
path('search-discovery/<int:pk>/delete/', views.search_discovery_index_delete, name='search_discovery_index_delete'),
path('search-discovery/<int:pk>/reweight/', views.search_discovery_index_reweight, name='search_discovery_index_reweight'),
path('search-discovery/hub/', views.search_discovery_hub, name='search_discovery_hub'),
```

---

## 4. Views & Context Variables Contract

Every context variable is pinned.

### 4.1 `NaturalLanguageQueries`
- **List View (`natural_language_query_list`)**:
  - `queries` / `natural_language_queries`: Paginated queryset
  - `total_count`: Total queries count
  - `completed_count`: Completed queries count
  - `voice_count`: Modality voice count
  - `helpful_count`: Rated helpful count
  - `status_choices`: `NaturalLanguageQuery.EXECUTION_STATUS_CHOICES`
  - `modality_choices`: `NaturalLanguageQuery.INPUT_MODALITY_CHOICES`
  - `intent_choices`: `NaturalLanguageQuery.INTENT_TYPE_CHOICES`
  - `semantic_models`: `SemanticModel.objects.filter(tenant=request.tenant)`
- **Detail View (`natural_language_query_detail`)**:
  - `query`: `NaturalLanguageQuery` instance
  - `parsed_measures`: list
  - `parsed_dimensions`: list
  - `parsed_filters`: dict
  - `rating_choices`: `NaturalLanguageQuery.USER_RATING_CHOICES`
- **Form View (`natural_language_query_create` / `natural_language_query_edit`)**:
  - `form`: `NaturalLanguageQueryForm`
  - `query`: `NaturalLanguageQuery` instance (edit) or `None` (create)
  - `is_edit`: Boolean

### 4.2 `BiConversationSessions`
- **List View (`bi_conversation_session_list`)**:
  - `sessions` / `conversation_sessions`: Paginated queryset
  - `total_count`: Total sessions count
  - `active_count`: Active sessions count
  - `pinned_count`: Pinned sessions count
  - `status_choices`: `BiConversationSession.SESSION_STATUS_CHOICES`
  - `semantic_models`: `SemanticModel.objects.filter(tenant=request.tenant)`
  - `dashboards`: `BiDashboard.objects.filter(tenant=request.tenant)`
- **Detail View (`bi_conversation_session_detail`)**:
  - `session`: `BiConversationSession` instance
  - `turns`: Ordered queryset of `NaturalLanguageQuery` related to this session
  - `suggested_prompts`: list of strings
- **Chat Workspace View (`bi_chat_workspace`)**:
  - `sessions`: Queryset of `BiConversationSession` threads for left drawer (limit 50)
  - `active_session`: Currently selected `BiConversationSession` or first thread
  - `turns`: Ordered queryset of `NaturalLanguageQuery` for `active_session`
  - `suggested_prompts`: list of contextual prompt chip strings
- **Form View (`bi_conversation_session_create` / `bi_conversation_session_edit`)**:
  - `form`: `BiConversationSessionForm`
  - `session`: `BiConversationSession` instance (edit) or `None` (create)
  - `is_edit`: Boolean
- **Interactive Chat Assistant Workspace (`bi_chat_workspace`)**:
  - `sessions`: Top 50 sessions for left drawer (`BiConversationSession.objects.filter(tenant=request.tenant)...[:50]`)
  - `active_session`: Selected or first active `BiConversationSession` or `None`
  - `turns`: Ordered queryset of `NaturalLanguageQuery` turns with `.select_related('user')`
  - `suggested_prompts`: list of suggested analytical prompt strings

### 4.3 `NarrativeExplanations`
- **List View (`narrative_explanation_list`)**:
  - `narratives` / `narrative_explanations`: Paginated queryset
  - `total_count`: Total narratives count
  - `published_count`: Published count
  - `executive_count`: Executive briefing count
  - `audio_script_count`: Audio script count
  - `style_choices`: `NarrativeExplanation.NARRATIVE_STYLE_CHOICES`
  - `status_choices`: `NarrativeExplanation.STATUS_CHOICES`
  - `artifact_choices`: `NarrativeExplanation.TARGET_ARTIFACT_TYPE_CHOICES`
- **Detail View (`narrative_explanation_detail`)**:
  - `narrative`: `NarrativeExplanation` instance
  - `key_takeaways`: list of bullet points
- **Form View (`narrative_explanation_create` / `narrative_explanation_edit`)**:
  - `form`: `NarrativeExplanationForm`
  - `narrative`: `NarrativeExplanation` instance (edit) or `None` (create)
  - `is_edit`: Boolean

### 4.4 `SearchDiscoveryIndexes`
- **List View (`search_discovery_index_list`)**:
  - `indexes` / `search_discovery_indexes`: Paginated queryset
  - `total_count`: Total indexes count
  - `verified_count`: Verified count
  - `featured_count`: Featured count
  - `type_choices`: `SearchDiscoveryIndex.ASSET_TYPE_CHOICES`
- **Detail View (`search_discovery_index_detail`)**:
  - `index`: `SearchDiscoveryIndex` instance
  - `synonyms_list`: list of strings
- **Form View (`search_discovery_index_create` / `search_discovery_index_edit`)**:
  - `form`: `SearchDiscoveryIndexForm`
  - `index`: `SearchDiscoveryIndex` instance (edit) or `None` (create)
  - `is_edit`: Boolean
- **Hub View (`search_discovery_hub`)**:
  - `search_query`: str from `request.GET.get('q', '')`
  - `results`: List of matched `SearchDiscoveryIndex` items (sliced to 24)
  - `result_count`: Total count of matched search assets
  - `categories`: Distinct category strings
  - `featured_assets`: Queryset of featured/verified assets

---

## 5. Navigation & Sidebar Contract

In `apps/core/navigation.py`:
```python
"10.15": {
    "Natural Language Query (NLQ)": "bi:natural_language_query_list",
    "Conversational BI Assistant": "bi:bi_conversation_session_list",
    "Natural Language Generation (NLG)": "bi:narrative_explanation_list",
    "Voice-Enabled Analytics": "bi:narrative_explanation_list",
    "Search-Driven Discovery": "bi:search_discovery_index_list",
    # Plural aliases
    "Natural Language Queries": "bi:natural_language_query_list",
    "Conversational BI Sessions": "bi:bi_conversation_session_list",
    "Narrative Explanations": "bi:narrative_explanation_list",
    "Search Discovery Indexes": "bi:search_discovery_index_list",
}
```
