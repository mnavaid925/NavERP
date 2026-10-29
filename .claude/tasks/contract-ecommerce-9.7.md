# Contract — Sub-module 9.7: Search & Product Discovery (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.7 Search & Product Discovery · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-30 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0008_...`
- **Package Layout:** `SearchDiscovery/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/searchdiscovery/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `SearchSynonym` (`apps/ecommerce/models/SearchDiscovery/SearchSynonyms.py`)
- **Table:** `ecommerce_search_synonym`
- **Number Prefix:** `ESYM` (`ESYM-00001`)
- **CHOICES:**
  - `SYNONYM_TYPE_CHOICES = [('two_way', 'Two-Way Equivalent'), ('one_way', 'One-Way Directional'), ('replacement', 'Explicit Replacement')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `synonym_type`: `CharField(max_length=20, choices=SYNONYM_TYPE_CHOICES, default='two_way')`
  - `root_term`: `CharField(max_length=120, db_index=True)`
  - `synonyms`: `TextField(help_text='Comma-separated synonym terms')`
  - `is_active`: `BooleanField(default=True)`
  - `hit_count`: `PositiveIntegerField(default=0)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esym_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'synonym_type'], name='idx_esym_ten_act_type')`
  - `Index(fields=['tenant', 'root_term'], name='idx_esym_ten_root')`

---

### 1.2 `SearchFacetConfig` (`apps/ecommerce/models/SearchDiscovery/SearchFacetConfigs.py`)
- **Table:** `ecommerce_search_facet_config`
- **Number Prefix:** `ESFC` (`ESFC-00001`)
- **CHOICES:**
  - `SOURCE_TYPE_CHOICES = [('category', 'Category Hierarchy'), ('brand', 'Product Brand'), ('price', 'Price Range'), ('variant_option', 'Variant Option / Attribute'), ('availability', 'Stock Availability'), ('rating', 'Customer Rating'), ('tag', 'Product Tag')]`
  - `WIDGET_TYPE_CHOICES = [('checkbox', 'Checkboxes (Multi-Select)'), ('color_swatch', 'Color Swatches'), ('price_slider', 'Price Range Slider'), ('rating_stars', 'Rating Star Filter'), ('toggle', 'Boolean Toggle'), ('dropdown', 'Single-Select Dropdown')]`
  - `FILTER_LOGIC_CHOICES = [('disjunctive', 'Disjunctive (OR)'), ('conjunctive', 'Conjunctive (AND)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=100)`
  - `code`: `CharField(max_length=50)`
  - `source_type`: `CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default='brand')`
  - `option_key`: `CharField(max_length=50, blank=True)`
  - `widget_type`: `CharField(max_length=20, choices=WIDGET_TYPE_CHOICES, default='checkbox')`
  - `filter_logic`: `CharField(max_length=15, choices=FILTER_LOGIC_CHOICES, default='disjunctive')`
  - `display_order`: `PositiveIntegerField(default=0)`
  - `is_collapsed_by_default`: `BooleanField(default=False)`
  - `max_values_shown`: `PositiveIntegerField(default=10)`
  - `is_searchable`: `BooleanField(default=False)`
  - `category_scope`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='scoped_facets')`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esfc_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code', 'category_scope'], name='ecommerce_esfc_code_cat_uniq')`
  - `Index(fields=['tenant', 'is_active', 'display_order'], name='idx_esfc_ten_act_disp')`

---

### 1.3 `SearchMerchandisingRule` (`apps/ecommerce/models/SearchDiscovery/SearchMerchandisingRules.py`)
- **Table:** `ecommerce_search_merchandising_rule`
- **Number Prefix:** `ESMR` (`ESMR-00001`)
- **CHOICES:**
  - `RULE_TYPE_CHOICES = [('query', 'Search Query Trigger'), ('category', 'Category Listing Trigger'), ('global', 'Global Catalog Rule')]`
  - `MATCH_TYPE_CHOICES = [('exact', 'Exact Query Match'), ('contains', 'Contains Keyword'), ('starts_with', 'Starts With Keyword')]`
  - `ACTION_TYPE_CHOICES = [('boost', 'Boost Product Score'), ('bury', 'Bury Product Score'), ('pin', 'Pin Product to Slot'), ('block', 'Block / Exclude Product'), ('redirect', 'Query URL Redirect'), ('banner', 'Promotional Banner Injection')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `rule_type`: `CharField(max_length=20, choices=RULE_TYPE_CHOICES, default='query')`
  - `trigger_query`: `CharField(max_length=200, blank=True)`
  - `match_type`: `CharField(max_length=20, choices=MATCH_TYPE_CHOICES, default='exact')`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='merchandising_rules')`
  - `action_type`: `CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default='boost')`
  - `boosted_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, null=True, blank=True, related_name='merchandising_rules')`
  - `boost_weight`: `IntegerField(default=10, validators=[MinValueValidator(-100), MaxValueValidator(100)])`
  - `pin_position`: `PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(50)])`
  - `redirect_url`: `CharField(max_length=255, blank=True)`
  - `banner_title`: `CharField(max_length=150, blank=True)`
  - `banner_body`: `TextField(blank=True)`
  - `banner_image_url`: `URLField(blank=True)`
  - `banner_link_url`: `CharField(max_length=255, blank=True)`
  - `priority`: `PositiveIntegerField(default=10)`
  - `start_date`: `DateTimeField(null=True, blank=True)`
  - `end_date`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esmr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'rule_type'], name='idx_esmr_ten_act_type')`
  - `Index(fields=['tenant', 'trigger_query'], name='idx_esmr_ten_trig_q')`

---

### 1.4 `SearchQueryLog` (`apps/ecommerce/models/SearchDiscovery/SearchQueryLogs.py`)
- **Table:** `ecommerce_search_query_log`
- **Number Prefix:** `ESQL` (`ESQL-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `query_text`: `CharField(max_length=255, db_index=True)`
  - `normalized_query`: `CharField(max_length=255, db_index=True)`
  - `results_count`: `PositiveIntegerField(default=0)`
  - `is_zero_result`: `BooleanField(default=False, db_index=True)`
  - `execution_time_ms`: `PositiveIntegerField(default=0)`
  - `applied_filters`: `JSONField(default=dict, blank=True)`
  - `sort_order`: `CharField(max_length=30, default='relevance')`
  - `redirected_to`: `CharField(max_length=255, blank=True)`
  - `clicked_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='search_clicks')`
  - `click_position`: `PositiveIntegerField(null=True, blank=True)`
  - `session_key`: `CharField(max_length=64, blank=True, db_index=True)`
  - `customer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_search_logs')`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esql_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_zero_result', '-created_at'], name='idx_esql_ten_zr_created')`
  - `Index(fields=['tenant', 'normalized_query'], name='idx_esql_ten_norm_q')`
  - `Index(fields=['tenant', '-created_at'], name='idx_esql_ten_created')`

---

## 2. Forms Contract

### 2.1 `SearchSynonymForm` (`apps/ecommerce/forms/SearchDiscovery/SearchSynonyms.py`)
- **Model:** `SearchSynonym`
- **Fields:** `['name', 'synonym_type', 'root_term', 'synonyms', 'is_active', 'notes']`
- **Excludes:** `['tenant', 'number', 'hit_count', 'created_at', 'updated_at']`
- **Clean Validation:**
  - Lowercases & strips `root_term`.
  - Normalizes `synonyms` as comma-separated, stripped list.
  - If `synonym_type == 'replacement'`, ensures exactly one replacement term.

### 2.2 `SearchFacetConfigForm` (`apps/ecommerce/forms/SearchDiscovery/SearchFacetConfigs.py`)
- **Model:** `SearchFacetConfig`
- **Fields:** `['name', 'code', 'source_type', 'option_key', 'widget_type', 'filter_logic', 'display_order', 'is_collapsed_by_default', 'max_values_shown', 'is_searchable', 'category_scope', 'is_active']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Tenant Scope:** Filters `category_scope` queryset by `tenant=request.tenant`.
- **Clean Validation:**
  - Lowercases and slug-normalizes `code`.
  - If `source_type == 'variant_option'`, requires `option_key`.

### 2.3 `SearchMerchandisingRuleForm` (`apps/ecommerce/forms/SearchDiscovery/SearchMerchandisingRules.py`)
- **Model:** `SearchMerchandisingRule`
- **Fields:** `['name', 'rule_type', 'trigger_query', 'match_type', 'target_category', 'action_type', 'boosted_product', 'boost_weight', 'pin_position', 'redirect_url', 'banner_title', 'banner_body', 'banner_image_url', 'banner_link_url', 'priority', 'start_date', 'end_date', 'is_active']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Tenant Scope:** Filters `target_category` and `boosted_product` by `tenant=request.tenant`.
- **Clean Validation:**
  - Enforces required fields per `rule_type` and `action_type`.
  - Enforces `end_date >= start_date` if both are provided.

---

## 3. URLs & Route Names Contract

All routes prefixed with `ecommerce:` in the `ecommerce` URL namespace:

| URL Pattern | View Function | URL Name |
|---|---|---|
| `search-discovery/synonyms/` | `searchsynonym_list` | `ecommerce:searchsynonym_list` |
| `search-discovery/synonyms/create/` | `searchsynonym_create` | `ecommerce:searchsynonym_create` |
| `search-discovery/synonyms/<int:pk>/` | `searchsynonym_detail` | `ecommerce:searchsynonym_detail` |
| `search-discovery/synonyms/<int:pk>/edit/` | `searchsynonym_edit` | `ecommerce:searchsynonym_edit` |
| `search-discovery/synonyms/<int:pk>/delete/` | `searchsynonym_delete` | `ecommerce:searchsynonym_delete` |
| `search-discovery/synonyms/<int:pk>/toggle/` | `searchsynonym_toggle` | `ecommerce:searchsynonym_toggle` |
| `search-discovery/facet-configs/` | `searchfacetconfig_list` | `ecommerce:searchfacetconfig_list` |
| `search-discovery/facet-configs/create/` | `searchfacetconfig_create` | `ecommerce:searchfacetconfig_create` |
| `search-discovery/facet-configs/<int:pk>/` | `searchfacetconfig_detail` | `ecommerce:searchfacetconfig_detail` |
| `search-discovery/facet-configs/<int:pk>/edit/` | `searchfacetconfig_edit` | `ecommerce:searchfacetconfig_edit` |
| `search-discovery/facet-configs/<int:pk>/delete/` | `searchfacetconfig_delete` | `ecommerce:searchfacetconfig_delete` |
| `search-discovery/facet-configs/<int:pk>/toggle/` | `searchfacetconfig_toggle` | `ecommerce:searchfacetconfig_toggle` |
| `search-discovery/merchandising-rules/` | `searchmerchandisingrule_list` | `ecommerce:searchmerchandisingrule_list` |
| `search-discovery/merchandising-rules/create/` | `searchmerchandisingrule_create` | `ecommerce:searchmerchandisingrule_create` |
| `search-discovery/merchandising-rules/<int:pk>/` | `searchmerchandisingrule_detail` | `ecommerce:searchmerchandisingrule_detail` |
| `search-discovery/merchandising-rules/<int:pk>/edit/` | `searchmerchandisingrule_edit` | `ecommerce:searchmerchandisingrule_edit` |
| `search-discovery/merchandising-rules/<int:pk>/delete/` | `searchmerchandisingrule_delete` | `ecommerce:searchmerchandisingrule_delete` |
| `search-discovery/merchandising-rules/<int:pk>/toggle/` | `searchmerchandisingrule_toggle` | `ecommerce:searchmerchandisingrule_toggle` |
| `search-discovery/query-logs/` | `searchquerylog_list` | `ecommerce:searchquerylog_list` |
| `search-discovery/query-logs/<int:pk>/` | `searchquerylog_detail` | `ecommerce:searchquerylog_detail` |
| `search-discovery/query-logs/<int:pk>/delete/` | `searchquerylog_delete` | `ecommerce:searchquerylog_delete` |
| `search-discovery/console/` | `search_console` | `ecommerce:search_console` |
| `search-discovery/autocomplete/` | `search_autocomplete` | `ecommerce:search_autocomplete` |
| `search-discovery/analytics/` | `search_analytics` | `ecommerce:search_analytics` |

---

## 4. View Context Keys Contract (L7 Strict Pinning)

### 4.1 Synonyms
- **List View (`searchsynonym_list`)**:
  - `page_obj`: paginated query results
  - `synonyms`: page items alias
  - `synonym_type_choices`: `SearchSynonym.SYNONYM_TYPE_CHOICES`
  - `q`: search string from GET
  - `selected_type`: `request.GET.get('synonym_type')`
  - `selected_active`: `request.GET.get('is_active')`
- **Detail View (`searchsynonym_detail`)**:
  - `synonym`: `SearchSynonym` instance
  - `synonym_list`: list of stripped synonym strings for pill rendering
- **Form Views (`searchsynonym_create`, `searchsynonym_edit`)**:
  - `form`: `SearchSynonymForm` instance
  - `synonym`: `SearchSynonym` instance (or `None` in create)
  - `is_edit`: boolean

### 4.2 Facet Configurations
- **List View (`searchfacetconfig_list`)**:
  - `page_obj`: paginated query results
  - `facet_configs`: page items alias
  - `source_type_choices`: `SearchFacetConfig.SOURCE_TYPE_CHOICES`
  - `widget_type_choices`: `SearchFacetConfig.WIDGET_TYPE_CHOICES`
  - `filter_logic_choices`: `SearchFacetConfig.FILTER_LOGIC_CHOICES`
  - `q`: search string from GET
  - `selected_source`: `request.GET.get('source_type')`
  - `selected_widget`: `request.GET.get('widget_type')`
  - `selected_logic`: `request.GET.get('filter_logic')`
  - `selected_active`: `request.GET.get('is_active')`
- **Detail View (`searchfacetconfig_detail`)**:
  - `facet_config`: `SearchFacetConfig` instance
- **Form Views (`searchfacetconfig_create`, `searchfacetconfig_edit`)**:
  - `form`: `SearchFacetConfigForm` instance
  - `facet_config`: `SearchFacetConfig` instance (or `None` in create)
  - `is_edit`: boolean

### 4.3 Merchandising Rules
- **List View (`searchmerchandisingrule_list`)**:
  - `page_obj`: paginated query results
  - `rules`: page items alias
  - `rule_type_choices`: `SearchMerchandisingRule.RULE_TYPE_CHOICES`
  - `action_type_choices`: `SearchMerchandisingRule.ACTION_TYPE_CHOICES`
  - `q`: search string from GET
  - `selected_rule_type`: `request.GET.get('rule_type')`
  - `selected_action_type`: `request.GET.get('action_type')`
  - `selected_active`: `request.GET.get('is_active')`
- **Detail View (`searchmerchandisingrule_detail`)**:
  - `rule`: `SearchMerchandisingRule` instance
- **Form Views (`searchmerchandisingrule_create`, `searchmerchandisingrule_edit`)**:
  - `form`: `SearchMerchandisingRuleForm` instance
  - `rule`: `SearchMerchandisingRule` instance (or `None` in create)
  - `is_edit`: boolean

### 4.4 Query Logs
- **List View (`searchquerylog_list`)**:
  - `page_obj`: paginated query results
  - `logs`: page items alias
  - `q`: search string from GET
  - `selected_zero_result`: `request.GET.get('is_zero_result')`
  - `selected_sort`: `request.GET.get('sort_order')`
- **Detail View (`searchquerylog_detail`)**:
  - `log`: `SearchQueryLog` instance
  - `applied_filters_items`: list of key-value tuples from `applied_filters` JSON

### 4.5 Search Console & Workbench
- **Console View (`search_console`)**:
  - `q`: query string
  - `products`: resulting list of ranked `CatalogProduct` instances
  - `total_results`: total count of matching products
  - `execution_time_ms`: latency in milliseconds
  - `facet_groups`: list of computed facet dictionaries with available option buckets and counts
  - `active_filters`: dictionary of applied filters
  - `applied_synonyms`: list of synonym rules triggered
  - `applied_merchandising_rules`: list of boost/pin/bury rules applied
  - `promotional_banners`: list of matching banner rules
  - `redirect_url`: destination URL if intercepted by redirect rule
  - `categories`: `StoreCategory` list for category dropdown filter
  - `sort_order`: selected sort order
  - `sort_choices`: `[('relevance', 'Most Relevant'), ('price_asc', 'Price: Low to High'), ('price_desc', 'Price: High to Low'), ('newest', 'Newest Arrivals'), ('rating', 'Customer Rating')]`
  - `fallback_recommendations`: recommended products when zero results occur
- **Analytics View (`search_analytics`)**:
  - `total_searches`: total queries executed
  - `zero_result_searches`: total null-result queries
  - `zero_result_rate`: null-result percentage (0.0% to 100.0%)
  - `avg_latency_ms`: average execution time in milliseconds
  - `top_queries`: queryset of top executed search terms with counts
  - `zero_result_queries`: queryset of top zero-result queries with counts
  - `top_clicked_products`: queryset of products most clicked from search

---

## 5. Templates Contract

| Path | Purpose |
|---|---|
| `templates/ecommerce/searchdiscovery/synonym/list.html` | Synonym rule directory with filter bar, search, status badge, hit counter, actions |
| `templates/ecommerce/searchdiscovery/synonym/detail.html` | Detailed synonym rule view with chips, type indicator, hit metrics |
| `templates/ecommerce/searchdiscovery/synonym/form.html` | Synonym creation/editing form with responsive layout |
| `templates/ecommerce/searchdiscovery/facetconfig/list.html` | Facet configurations table ordered by display order with widget badges |
| `templates/ecommerce/searchdiscovery/facetconfig/detail.html` | Facet config detail with widget visualization and category scope card |
| `templates/ecommerce/searchdiscovery/facetconfig/form.html` | Facet config creation/editing form |
| `templates/ecommerce/searchdiscovery/merchandisingrule/list.html` | Merchandising rules table with action badges, priority ordering, search |
| `templates/ecommerce/searchdiscovery/merchandisingrule/detail.html` | Rule detail view with preview banner, trigger & consequence breakdown |
| `templates/ecommerce/searchdiscovery/merchandisingrule/form.html` | Merchandising rule creation/editing form with dynamic input blocks |
| `templates/ecommerce/searchdiscovery/querylog/list.html` | Query telemetry audit list with latency pill, zero-result indicator |
| `templates/ecommerce/searchdiscovery/querylog/detail.html` | Query telemetry detail with JSON filter breakdown and click tracking |
| `templates/ecommerce/searchdiscovery/console/console.html` | Search Discovery Workbench: query bar, facet sidebar, product grid, banner card |
| `templates/ecommerce/searchdiscovery/console/autocomplete_results.html` | HTMX partial returning matching queries, categories, and top products |
| `templates/ecommerce/searchdiscovery/analytics/analytics.html` | Search telemetry KPI dashboard: metrics cards, top queries, null-result recovery |
