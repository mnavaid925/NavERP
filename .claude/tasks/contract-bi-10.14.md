# Contract — Sub-module 10.14: AI & Augmented Analytics (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.14 AI & Augmented Analytics • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-07 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.12). Incremental migration: `0030_...` (previous leaf: `0029_alter_scorecardkpiassignment_options_and_more.py`).
- **Package Layout:** `AiAugmentedAnalytics/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/ai_augmented_analytics/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AugmentedInsight` (`apps/bi/models/AiAugmentedAnalytics/AugmentedInsights.py`)
- **Table:** `bi_augmented_insight`
- **Number Prefix:** `BAIN` (`BAIN-00001`)
- **CHOICES:**
  - `INSIGHT_TYPE_CHOICES = [('key_driver', 'Key Driver Analysis'), ('anomaly', 'Statistical Anomaly'), ('trend_shift', 'Trend Direction Shift'), ('outlier', 'Distribution Outlier'), ('period_comparison', 'Period Variance Spike')]`
  - `IMPACT_DIRECTION_CHOICES = [('favorable', 'Favorable Impact'), ('unfavorable', 'Unfavorable Impact'), ('neutral', 'Neutral / Informational')]`
  - `SEVERITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')]`
  - `STATUS_CHOICES = [('new', 'New Insight'), ('bookmarked', 'Bookmarked'), ('dismissed', 'Dismissed'), ('actioned', 'Action Taken')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `insight_type`: `CharField(max_length=24, choices=INSIGHT_TYPE_CHOICES, default='key_driver')`
  - `metric_name`: `CharField(max_length=120, help_text="Analyzed metric, e.g. Gross Margin %, Total Revenue, Delivery Lead Time")`
  - `baseline_value`: `DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))`
  - `observed_value`: `DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))`
  - `variance_percentage`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `impact_direction`: `CharField(max_length=16, choices=IMPACT_DIRECTION_CHOICES, default='neutral')`
  - `severity`: `CharField(max_length=16, choices=SEVERITY_CHOICES, default='medium')`
  - `confidence_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('90.00'), help_text="Statistical confidence percentage")`
  - `narrative_summary`: `TextField(help_text="Plain-text natural language explanation of the insight")`
  - `dimension_name`: `CharField(max_length=100, blank=True, help_text="Primary dimension sliced, e.g. Region, Product Family, Customer Tier")`
  - `dimension_value`: `CharField(max_length=120, blank=True, help_text="Value of primary dimension, e.g. EMEA, High Tech, Tier 1")`
  - `driver_decomposition`: `JSONField(default=list, blank=True, help_text="Top contributing positive and negative drivers")`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='new')`
  - `action_notes`: `TextField(blank=True, help_text="Management commentary or logged follow-up steps")`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='augmented_insights')`
  - `kpi_definition`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='augmented_insights')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='augmented_insights')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_augmented_insights')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bain_tenant_num_uniq')`
  - `Index(fields=['tenant', 'insight_type'], name='idx_bain_ten_type')`
  - `Index(fields=['tenant', 'status'], name='idx_bain_ten_status')`
  - `Index(fields=['tenant', 'severity'], name='idx_bain_ten_sev')`
  - `Index(fields=['tenant', 'impact_direction'], name='idx_bain_ten_dir')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bain_ten_created')`

---

### 1.2 `SmartDataPrepSuggestion` (`apps/bi/models/AiAugmentedAnalytics/SmartDataPrepSuggestions.py`)
- **Table:** `bi_smart_data_prep_suggestion`
- **Number Prefix:** `BSDP` (`BSDP-00001`)
- **CHOICES:**
  - `SUGGESTION_TYPE_CHOICES = [('join_relationship', 'Suggested Foreign Key Join'), ('type_cast', 'Data Type Inference / Cast'), ('split_column', 'Column Extraction / Delimiter Split'), ('impute_missing', 'Missing Value Imputation'), ('deduplicate_fuzzy', 'Fuzzy Match Deduplication'), ('filter_outliers', 'Statistical Outlier Filter')]`
  - `STATUS_CHOICES = [('pending', 'Pending Review'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('applied', 'Applied')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `target_table`: `ForeignKey('bi.WarehouseTable', on_delete=models.CASCADE, related_name='target_prep_suggestions')`
  - `target_column`: `CharField(max_length=100, help_text="Column in target table being transformed or joined")`
  - `suggestion_type`: `CharField(max_length=24, choices=SUGGESTION_TYPE_CHOICES, default='join_relationship')`
  - `related_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='related_prep_suggestions', help_text="Joining table for relationship suggestions")`
  - `related_column`: `CharField(max_length=100, blank=True, help_text="Key column in related table")`
  - `confidence_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('85.00'))`
  - `rationale`: `TextField(help_text="AI rationale explaining why this preparation step or relationship is recommended")`
  - `suggested_config`: `JSONField(default=dict, blank=True, help_text="Rule parameters, join syntax, regex expressions, or imputation settings")`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='pending')`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_prep_suggestions')`
  - `reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `review_notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsdp_tenant_num_uniq')`
  - `Index(fields=['tenant', 'suggestion_type'], name='idx_bsdp_ten_type')`
  - `Index(fields=['tenant', 'status'], name='idx_bsdp_ten_stat')`
  - `Index(fields=['tenant', 'target_table'], name='idx_bsdp_ten_tbl')`

---

### 1.3 `TextSentimentAnalysis` (`apps/bi/models/AiAugmentedAnalytics/TextSentimentAnalyses.py`)
- **Table:** `bi_text_sentiment_analysis`
- **Number Prefix:** `BSNT` (`BSNT-00001`)
- **CHOICES:**
  - `SOURCE_TYPE_CHOICES = [('customer_review', 'Customer Review / Rating'), ('support_ticket', 'Customer Support Ticket'), ('survey_feedback', 'Survey Feedback / NPS'), ('crm_note', 'CRM Activity Note'), ('internal_comment', 'Internal Team Comment')]`
  - `SENTIMENT_CATEGORY_CHOICES = [('very_positive', 'Very Positive'), ('positive', 'Positive'), ('neutral', 'Neutral'), ('negative', 'Negative'), ('very_negative', 'Very Negative')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `source_type`: `CharField(max_length=24, choices=SOURCE_TYPE_CHOICES, default='customer_review')`
  - `source_reference`: `CharField(max_length=120, help_text="Identifier of source record e.g. TKT-00421, REV-9811")`
  - `text_content`: `TextField(help_text="Unstructured textual snippet analyzed")`
  - `language`: `CharField(max_length=10, default='en')`
  - `sentiment_category`: `CharField(max_length=20, choices=SENTIMENT_CATEGORY_CHOICES, default='neutral')`
  - `polarity_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Range from -1.00 (most negative) to +1.00 (most positive)")`
  - `subjectivity_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'), help_text="Range from 0.00 (objective fact) to 1.00 (pure opinion)")`
  - `thematic_tags`: `JSONField(default=list, blank=True, help_text="Extracted key themes e.g. ['billing', 'delivery_time', 'ease_of_use']")`
  - `linked_party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=models.SET_NULL, related_name='text_sentiment_records', help_text="Associated customer, vendor, or contact")`
  - `linked_org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='text_sentiment_records')`
  - `analyzed_at`: `DateTimeField(auto_now_add=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsnt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'source_type'], name='idx_bsnt_ten_src')`
  - `Index(fields=['tenant', 'sentiment_category'], name='idx_bsnt_ten_cat')`
  - `Index(fields=['tenant', 'analyzed_at'], name='idx_bsnt_ten_date')`
  - `Index(fields=['tenant', 'linked_party'], name='idx_bsnt_ten_party')`

---

### 1.4 `AnalyticsRecommendation` (`apps/bi/models/AiAugmentedAnalytics/AnalyticsRecommendations.py`)
- **Table:** `bi_analytics_recommendation`
- **Number Prefix:** `BARC` (`BARC-00001`)
- **CHOICES:**
  - `RECOMMENDATION_TYPE_CHOICES = [('dashboard', 'Interactive Dashboard'), ('report', 'Operational Report'), ('kpi', 'KPI Metric Definition'), ('dataset', 'Semantic Dataset'), ('drill_path', 'Guided Drill Path')]`
  - `REASON_CHOICES = [('peer_usage', 'Popular Among Your Peers'), ('trending_metric', 'High Metric Volatility / Trend'), ('anomaly_in_domain', 'Recent Anomaly Detected in Domain'), ('recent_search', 'Matches Recent Data Inquiries'), ('role_relevance', 'Standard for Your Organizational Role')]`
  - `STATUS_CHOICES = [('active', 'Active Recommendation'), ('clicked', 'Viewed / Clicked'), ('dismissed', 'Dismissed by User'), ('saved', 'Saved / Bookmarked')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analytics_recommendations')`
  - `recommendation_type`: `CharField(max_length=24, choices=RECOMMENDATION_TYPE_CHOICES, default='dashboard')`
  - `target_title`: `CharField(max_length=200, help_text="Title of the recommended asset")`
  - `target_url`: `CharField(max_length=255, help_text="Direct internal URL link to view the recommended asset")`
  - `reason`: `CharField(max_length=24, choices=REASON_CHOICES, default='role_relevance')`
  - `rationale_text`: `TextField(blank=True, help_text="Friendly explanation of why this asset is suggested")`
  - `affinity_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('80.00'), help_text="Match affinity score (0.00 to 100.00%)")`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='recommendations')`
  - `report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='recommendations')`
  - `kpi`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='recommendations')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='recommendations')`
  - `last_interacted_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_barc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'user', 'status'], name='idx_barc_ten_user_stat')`
  - `Index(fields=['tenant', 'recommendation_type'], name='idx_barc_ten_type')`
  - `Index(fields=['tenant', 'affinity_score'], name='idx_barc_ten_score')`

---

## 2. Forms Contract & Field Exclusions

All forms inherit from `forms.ModelForm` and exclude tenant isolation, auto-numbers, system timestamps, and internal metadata.

### 2.1 `AugmentedInsightForm` (`apps/bi/forms/AiAugmentedAnalytics/AugmentedInsights.py`)
- **Fields:** `['title', 'insight_type', 'metric_name', 'baseline_value', 'observed_value', 'variance_percentage', 'impact_direction', 'severity', 'confidence_score', 'narrative_summary', 'dimension_name', 'dimension_value', 'status', 'action_notes', 'semantic_model', 'kpi_definition', 'warehouse_table']`
- **Excludes:** `['tenant', 'number', 'driver_decomposition', 'created_by', 'created_at', 'updated_at']`

### 2.2 `SmartDataPrepSuggestionForm` (`apps/bi/forms/AiAugmentedAnalytics/SmartDataPrepSuggestions.py`)
- **Fields:** `['target_table', 'target_column', 'suggestion_type', 'related_table', 'related_column', 'confidence_score', 'rationale', 'status', 'review_notes']`
- **Excludes:** `['tenant', 'number', 'suggested_config', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at']`

### 2.3 `TextSentimentAnalysisForm` (`apps/bi/forms/AiAugmentedAnalytics/TextSentimentAnalyses.py`)
- **Fields:** `['source_type', 'source_reference', 'text_content', 'language', 'sentiment_category', 'polarity_score', 'subjectivity_score', 'linked_party', 'linked_org_unit']`
- **Excludes:** `['tenant', 'number', 'thematic_tags', 'analyzed_at', 'created_at', 'updated_at']`

### 2.4 `AnalyticsRecommendationForm` (`apps/bi/forms/AiAugmentedAnalytics/AnalyticsRecommendations.py`)
- **Fields:** `['user', 'recommendation_type', 'target_title', 'target_url', 'reason', 'rationale_text', 'affinity_score', 'status', 'dashboard', 'report', 'kpi', 'semantic_model']`
- **Excludes:** `['tenant', 'number', 'last_interacted_at', 'created_at', 'updated_at']`

---

## 3. URLs Contract & Route Names

All routes defined inside `apps/bi/urls/AiAugmentedAnalytics/`:
- `bi:augmented_insight_list` $\rightarrow$ `/bi/augmented-insights/`
- `bi:augmented_insight_feed` $\rightarrow$ `/bi/augmented-insights/feed/`
- `bi:augmented_insight_detail` $\rightarrow$ `/bi/augmented-insights/<int:pk>/`
- `bi:augmented_insight_create` $\rightarrow$ `/bi/augmented-insights/new/`
- `bi:augmented_insight_edit` $\rightarrow$ `/bi/augmented-insights/<int:pk>/edit/`
- `bi:augmented_insight_delete` $\rightarrow$ `/bi/augmented-insights/<int:pk>/delete/`
- `bi:augmented_insight_triage` $\rightarrow$ `/bi/augmented-insights/<int:pk>/triage/`
- `bi:smart_data_prep_suggestion_list` $\rightarrow$ `/bi/data-prep-suggestions/`
- `bi:smart_data_prep_suggestion_detail` $\rightarrow$ `/bi/data-prep-suggestions/<int:pk>/`
- `bi:smart_data_prep_suggestion_create` $\rightarrow$ `/bi/data-prep-suggestions/new/`
- `bi:smart_data_prep_suggestion_edit` $\rightarrow$ `/bi/data-prep-suggestions/<int:pk>/edit/`
- `bi:smart_data_prep_suggestion_delete` $\rightarrow$ `/bi/data-prep-suggestions/<int:pk>/delete/`
- `bi:smart_data_prep_suggestion_action` $\rightarrow$ `/bi/data-prep-suggestions/<int:pk>/action/`
- `bi:text_sentiment_analysis_list` $\rightarrow$ `/bi/sentiment-analyses/`
- `bi:text_sentiment_analysis_detail` $\rightarrow$ `/bi/sentiment-analyses/<int:pk>/`
- `bi:text_sentiment_analysis_create` $\rightarrow$ `/bi/sentiment-analyses/new/`
- `bi:text_sentiment_analysis_edit` $\rightarrow$ `/bi/sentiment-analyses/<int:pk>/edit/`
- `bi:text_sentiment_analysis_delete` $\rightarrow$ `/bi/sentiment-analyses/<int:pk>/delete/`
- `bi:text_sentiment_analysis_recalculate` $\rightarrow$ `/bi/sentiment-analyses/<int:pk>/recalculate/`
- `bi:analytics_recommendation_list` $\rightarrow$ `/bi/recommendations/`
- `bi:analytics_recommendation_detail` $\rightarrow$ `/bi/recommendations/<int:pk>/`
- `bi:analytics_recommendation_create` $\rightarrow$ `/bi/recommendations/new/`
- `bi:analytics_recommendation_edit` $\rightarrow$ `/bi/recommendations/<int:pk>/edit/`
- `bi:analytics_recommendation_delete` $\rightarrow$ `/bi/recommendations/<int:pk>/delete/`
- `bi:analytics_recommendation_interact` $\rightarrow$ `/bi/recommendations/<int:pk>/interact/`

---

## 4. View Context Keys Contract (L7 / L8 Pinned)

### 4.1 `AugmentedInsight`
- **List View (`augmented_insight_list`):**
  - Context keys: `insights` (page_obj), `insight_type_choices`, `impact_choices`, `severity_choices`, `status_choices`, `total_count`, `critical_count`
- **Feed View (`augmented_insight_feed`):**
  - Context keys: `feed_items` (page_obj), `severity_choices`, `impact_choices`, `active_tab`
- **Detail View (`augmented_insight_detail`):**
  - Context keys: `insight` (singular instance), `drivers` (parsed decomposition list)
- **Form View (`augmented_insight_form`):**
  - Context keys: `form`, `insight` (singular instance or None), `is_edit`

### 4.2 `SmartDataPrepSuggestion`
- **List View (`smart_data_prep_suggestion_list`):**
  - Context keys: `suggestions` (page_obj), `suggestion_type_choices`, `status_choices`, `tables` (WarehouseTable queryset), `pending_count`
- **Detail View (`smart_data_prep_suggestion_detail`):**
  - Context keys: `suggestion` (singular instance), `config_items` (dict or items list)
- **Form View (`smart_data_prep_suggestion_form`):**
  - Context keys: `form`, `suggestion` (singular instance or None), `is_edit`

### 4.3 `TextSentimentAnalysis`
- **List View (`text_sentiment_analysis_list`):**
  - Context keys: `analyses` (page_obj), `source_type_choices`, `sentiment_category_choices`, `positive_count`, `negative_count`, `avg_polarity`
- **Detail View (`text_sentiment_analysis_detail`):**
  - Context keys: `analysis` (singular instance), `thematic_tags_list`
- **Form View (`text_sentiment_analysis_form`):**
  - Context keys: `form`, `analysis` (singular instance or None), `is_edit`

### 4.4 `AnalyticsRecommendation`
- **List View (`analytics_recommendation_list`):**
  - Context keys: `recommendations` (page_obj), `recommendation_type_choices`, `reason_choices`, `status_choices`, `active_count`
- **Detail View (`analytics_recommendation_detail`):**
  - Context keys: `recommendation` (singular instance)
- **Form View (`analytics_recommendation_form`):**
  - Context keys: `form`, `recommendation` (singular instance or None), `is_edit`

---

## 5. Navigation Sidebar Contract (`LIVE_LINKS["10.14"]`)

The exact NavERP.md feature bullet names mapped to route names:
- `"Auto-Generated Insights"`: `'bi:augmented_insight_list'`
- `"Smart Insight Feed"`: `'bi:augmented_insight_feed'`
- `"Automated Data Preparation"`: `'bi:smart_data_prep_suggestion_list'`
- `"Text & Sentiment Analytics"`: `'bi:text_sentiment_analysis_list'`
- `"Recommendation Engine"`: `'bi:analytics_recommendation_list'`
