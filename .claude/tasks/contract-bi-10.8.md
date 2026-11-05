# Contract — Sub-module 10.8: Dashboards & Visualization (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.8 Dashboards & Visualization · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-05 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended across 10.2, 10.3, 10.4, 10.5, 10.6). Incremental migration: `0019_...` (or next leaf)
- **Package Layout:** `Dashboards/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/dashboards/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `BiDashboard` (`apps/bi/models/Dashboards/BiDashboards.py`)
- **Table:** `bi_dashboard`
- **Number Prefix:** `BDSH` (`BDSH-00001`)
- **CHOICES:**
  - `CATEGORY_CHOICES = [('executive', 'Executive & C-Suite'), ('finance', 'Finance & Accounting'), ('sales_crm', 'Sales & CRM'), ('supply_chain', 'Supply Chain & Inventory'), ('operations', 'Plant & Operations'), ('hr', 'Human Resources & Talent'), ('custom', 'Custom Dashboard')]`
  - `LAYOUT_TYPE_CHOICES = [('grid_12', '12-Column Responsive Grid'), ('executive_summary', 'Executive Summary Blueprint'), ('operational_monitoring', 'Operational Monitoring Board'), ('freeform', 'Flexible Fluid Layout')]`
  - `THEME_CHOICES = [('slate_corporate', 'Corporate Slate (Default)'), ('indigo_modern', 'Modern Indigo'), ('emerald_growth', 'Emerald Financial'), ('amber_industrial', 'Amber Industrial / Logistics'), ('dark_observability', 'High-Contrast Dark Mode')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=100)`
  - `category`: `CharField(max_length=40, choices=CATEGORY_CHOICES, default='executive')`
  - `layout_type`: `CharField(max_length=40, choices=LAYOUT_TYPE_CHOICES, default='grid_12')`
  - `refresh_interval_seconds`: `PositiveIntegerField(default=0, help_text="0=manual, 10, 30, 60, 300, 900, 3600")`
  - `theme`: `CharField(max_length=40, choices=THEME_CHOICES, default='slate_corporate')`
  - `role_required`: `CharField(max_length=60, blank=True, default='all')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_dashboards')`
  - `is_published`: `BooleanField(default=False)`
  - `is_template`: `BooleanField(default=False)`
  - `is_default`: `BooleanField(default=False)`
  - `is_kiosk_enabled`: `BooleanField(default=False)`
  - `color_palette_json`: `JSONField(default=list)`
  - `config_json`: `JSONField(default=dict)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_bi_dashboards')`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `last_viewed_at`: `DateTimeField(null=True, blank=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bdsh_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdsh_tenant_num_uniq')`
  - `Index(fields=['tenant', 'category'], name='idx_bdsh_ten_cat')`
  - `Index(fields=['tenant', 'is_published'], name='idx_bdsh_ten_pub')`
  - `Index(fields=['tenant', 'is_default'], name='idx_bdsh_ten_def')`
  - `Index(fields=['tenant', 'org_unit'], name='idx_bdsh_ten_org')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdsh_ten_act')`

---

### 1.2 `BiDashboardWidget` (`apps/bi/models/Dashboards/BiDashboardWidgets.py`)
- **Table:** `bi_dashboard_widget`
- **Number Prefix:** `BDWG` (`BDWG-00001`)
- **CHOICES:**
  - `WIDGET_TYPE_CHOICES = [('kpi_card', 'Headline KPI Metric Card'), ('line', 'Line Trend Chart'), ('area', 'Area / Stacked Area Chart'), ('bar', 'Horizontal Bar Chart'), ('column', 'Vertical Column Chart'), ('pie', 'Pie Chart'), ('donut', 'Donut Composition Chart'), ('gauge', 'Gauge / Target Progress'), ('heatmap', 'Matrix Heatmap'), ('funnel', 'Conversion Funnel'), ('treemap', 'Hierarchical Treemap'), ('table_pivot', 'Data / Pivot Table'), ('streaming_counter', 'Live Streaming Counter / Ticker')]`
  - `AGGREGATION_CHOICES = [('sum', 'Sum'), ('avg', 'Average'), ('count', 'Count'), ('count_distinct', 'Distinct Count'), ('min', 'Minimum'), ('max', 'Maximum'), ('last', 'Latest Non-Null Value')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `dashboard`: `ForeignKey('bi.BiDashboard', on_delete=CASCADE, related_name='widgets')`
  - `title`: `CharField(max_length=200)`
  - `subtitle`: `CharField(max_length=255, blank=True)`
  - `widget_type`: `CharField(max_length=40, choices=WIDGET_TYPE_CHOICES, default='kpi_card')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='dashboard_widgets')`
  - `calculated_measure`: `ForeignKey('bi.CalculatedMeasure', null=True, blank=True, on_delete=models.SET_NULL, related_name='dashboard_widgets')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='dashboard_widgets')`
  - `drill_hierarchy`: `ForeignKey('bi.DrillHierarchy', null=True, blank=True, on_delete=models.SET_NULL, related_name='dashboard_widgets')`
  - `aggregation_type`: `CharField(max_length=30, choices=AGGREGATION_CHOICES, default='sum')`
  - `pos_x`: `PositiveSmallIntegerField(default=0, help_text="0-11")`
  - `pos_y`: `PositiveSmallIntegerField(default=0, help_text="0-100")`
  - `width_cols`: `PositiveSmallIntegerField(default=4, help_text="1-12")`
  - `height_rows`: `PositiveSmallIntegerField(default=4, help_text="1-12")`
  - `refresh_interval_seconds`: `PositiveIntegerField(default=0)`
  - `drilldown_target_url`: `CharField(max_length=255, blank=True)`
  - `chart_config_json`: `JSONField(default=dict)`
  - `filter_overrides_json`: `JSONField(default=dict)`
  - `sort_order`: `PositiveIntegerField(default=10)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdwg_tenant_num_uniq')`
  - `Index(fields=['tenant', 'dashboard'], name='idx_bdwg_ten_dsh')`
  - `Index(fields=['tenant', 'widget_type'], name='idx_bdwg_ten_wtype')`
  - `Index(fields=['tenant', 'semantic_model'], name='idx_bdwg_ten_smdl')`
  - `Index(fields=['tenant', 'calculated_measure'], name='idx_bdwg_ten_cmsr')`
  - `Index(fields=['tenant', 'sort_order'], name='idx_bdwg_ten_sort')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdwg_ten_act')`

---

### 1.3 `BiDashboardBookmark` (`apps/bi/models/Dashboards/BiDashboardBookmarks.py`)
- **Table:** `bi_dashboard_bookmark`
- **Number Prefix:** `BDBM` (`BDBM-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `dashboard`: `ForeignKey('bi.BiDashboard', on_delete=CASCADE, related_name='bookmarks')`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='bi_dashboard_bookmarks')`
  - `name`: `CharField(max_length=150)`
  - `filter_state_json`: `JSONField(default=dict)`
  - `crossfilter_state_json`: `JSONField(default=dict)`
  - `is_default`: `BooleanField(default=False)`
  - `is_shared`: `BooleanField(default=False)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `last_viewed_at`: `DateTimeField(null=True, blank=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'dashboard', 'user', 'name'], name='bi_bdbm_ten_dsh_usr_name_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdbm_tenant_num_uniq')`
  - `Index(fields=['tenant', 'dashboard'], name='idx_bdbm_ten_dsh')`
  - `Index(fields=['tenant', 'user'], name='idx_bdbm_ten_usr')`
  - `Index(fields=['tenant', 'is_default'], name='idx_bdbm_ten_def')`
  - `Index(fields=['tenant', 'is_shared'], name='idx_bdbm_ten_shr')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdbm_ten_act')`

---

### 1.4 `BiDashboardFilter` (`apps/bi/models/Dashboards/BiDashboardFilters.py`)
- **Table:** `bi_dashboard_filter`
- **Number Prefix:** `BDFL` (`BDFL-00001`)
- **CHOICES:**
  - `FILTER_TYPE_CHOICES = [('dropdown', 'Single Select Dropdown'), ('multi_select', 'Multi-Select Dropdown / Badges'), ('date_range', 'Date Range Picker (From / To)'), ('date_preset', 'Relative Date Preset (Today, MTD, QTD, YTD)'), ('number_range', 'Numeric Range Slider / Min-Max'), ('search_text', 'Search Text Input')]`
  - `OPTIONS_SOURCE_CHOICES = [('static_list', 'Static Pre-defined Choices'), ('semantic_distinct', 'Distinct Values from Semantic Model'), ('warehouse_column', 'Distinct Values from Warehouse Table')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `dashboard`: `ForeignKey('bi.BiDashboard', on_delete=CASCADE, related_name='filters')`
  - `filter_label`: `CharField(max_length=100)`
  - `filter_key`: `SlugField(max_length=60)`
  - `filter_type`: `CharField(max_length=30, choices=FILTER_TYPE_CHOICES, default='dropdown')`
  - `target_field`: `CharField(max_length=100)`
  - `default_value`: `CharField(max_length=255, blank=True)`
  - `options_source`: `CharField(max_length=30, choices=OPTIONS_SOURCE_CHOICES, default='static_list')`
  - `static_options_json`: `JSONField(default=list)`
  - `order`: `PositiveIntegerField(default=10)`
  - `is_required`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'dashboard', 'filter_key'], name='bi_bdfl_ten_dsh_fkey_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdfl_tenant_num_uniq')`
  - `Index(fields=['tenant', 'dashboard'], name='idx_bdfl_ten_dsh')`
  - `Index(fields=['tenant', 'filter_key'], name='idx_bdfl_ten_fkey')`
  - `Index(fields=['tenant', 'order'], name='idx_bdfl_ten_ord')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdfl_ten_act')`

---

## 2. Forms Contract (`apps/bi/forms/Dashboards/`)

All forms inherit from `forms.ModelForm` or `forms.Form` and apply Tailwind design system input styling classes.

### 2.1 `BiDashboardForm` (`apps/bi/forms/Dashboards/BiDashboardForms.py`)
- **Fields:** `['title', 'slug', 'category', 'layout_type', 'refresh_interval_seconds', 'theme', 'role_required', 'org_unit', 'is_published', 'is_template', 'is_default', 'is_kiosk_enabled', 'color_palette_json', 'config_json', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'created_by', 'view_count', 'last_viewed_at', 'created_at', 'updated_at']`

### 2.2 `BiDashboardDuplicateForm` (`apps/bi/forms/Dashboards/BiDashboardForms.py`)
- Non-model form for cloning a dashboard along with its widgets and filters.
- **Fields:** `['new_title', 'new_slug', 'copy_widgets', 'copy_filters']`

### 2.3 `BiDashboardWidgetForm` (`apps/bi/forms/Dashboards/BiDashboardWidgetForms.py`)
- **Fields:** `['dashboard', 'title', 'subtitle', 'widget_type', 'semantic_model', 'calculated_measure', 'warehouse_table', 'drill_hierarchy', 'aggregation_type', 'pos_x', 'pos_y', 'width_cols', 'height_rows', 'refresh_interval_seconds', 'drilldown_target_url', 'chart_config_json', 'filter_overrides_json', 'sort_order', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'created_at', 'updated_at']`

### 2.4 `BiDashboardWidgetPositionForm` (`apps/bi/forms/Dashboards/BiDashboardWidgetForms.py`)
- Non-model form for updating layout positions on the 12-column grid.
- **Fields:** `['pos_x', 'pos_y', 'width_cols', 'height_rows']`

### 2.5 `BiDashboardBookmarkForm` (`apps/bi/forms/Dashboards/BiDashboardBookmarkForms.py`)
- **Fields:** `['dashboard', 'name', 'filter_state_json', 'crossfilter_state_json', 'is_default', 'is_shared', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'user', 'view_count', 'last_viewed_at', 'created_at', 'updated_at']`

### 2.6 `BiDashboardFilterForm` (`apps/bi/forms/Dashboards/BiDashboardFilterForms.py`)
- **Fields:** `['dashboard', 'filter_label', 'filter_key', 'filter_type', 'target_field', 'default_value', 'options_source', 'static_options_json', 'order', 'is_required', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'created_at', 'updated_at']`

---

## 3. URLs Contract (`apps/bi/urls/Dashboards/`)

App namespace: `bi`

| URL Pattern | View Name | View Function |
|---|---|---|
| `dashboards/` | `bi:bi_dashboard_list` | `bi_dashboard_list` |
| `dashboards/create/` | `bi:bi_dashboard_create` | `bi_dashboard_create` |
| `dashboards/<int:pk>/` | `bi:bi_dashboard_detail` | `bi_dashboard_detail` |
| `dashboards/<int:pk>/edit/` | `bi:bi_dashboard_edit` | `bi_dashboard_edit` |
| `dashboards/<int:pk>/delete/` | `bi:bi_dashboard_delete` | `bi_dashboard_delete` |
| `dashboards/<int:pk>/publish/` | `bi:bi_dashboard_publish` | `bi_dashboard_publish` |
| `dashboards/<int:pk>/duplicate/` | `bi:bi_dashboard_duplicate` | `bi_dashboard_duplicate` |
| `dashboards/<int:pk>/view/` | `bi:bi_dashboard_canvas_view` | `bi_dashboard_canvas_view` |
| `dashboards/<int:pk>/builder/` | `bi:bi_dashboard_canvas_builder` | `bi_dashboard_canvas_builder` |
| `dashboards/<int:pk>/kiosk/` | `bi:bi_dashboard_kiosk_view` | `bi_dashboard_kiosk_view` |
| `dashboards/widgets/` | `bi:bi_dashboard_widget_list` | `bi_dashboard_widget_list` |
| `dashboards/widgets/create/` | `bi:bi_dashboard_widget_create` | `bi_dashboard_widget_create` |
| `dashboards/widgets/<int:pk>/` | `bi:bi_dashboard_widget_detail` | `bi_dashboard_widget_detail` |
| `dashboards/widgets/<int:pk>/edit/` | `bi:bi_dashboard_widget_edit` | `bi_dashboard_widget_edit` |
| `dashboards/widgets/<int:pk>/delete/` | `bi:bi_dashboard_widget_delete` | `bi_dashboard_widget_delete` |
| `dashboards/widgets/<int:pk>/data/` | `bi:bi_dashboard_widget_data` | `bi_dashboard_widget_data` |
| `dashboards/bookmarks/` | `bi:bi_dashboard_bookmark_list` | `bi_dashboard_bookmark_list` |
| `dashboards/bookmarks/create/` | `bi:bi_dashboard_bookmark_create` | `bi_dashboard_bookmark_create` |
| `dashboards/bookmarks/<int:pk>/` | `bi:bi_dashboard_bookmark_detail` | `bi_dashboard_bookmark_detail` |
| `dashboards/bookmarks/<int:pk>/edit/` | `bi:bi_dashboard_bookmark_edit` | `bi_dashboard_bookmark_edit` |
| `dashboards/bookmarks/<int:pk>/delete/` | `bi:bi_dashboard_bookmark_delete` | `bi_dashboard_bookmark_delete` |
| `dashboards/bookmarks/<int:pk>/apply/` | `bi:bi_dashboard_bookmark_apply` | `bi_dashboard_bookmark_apply` |
| `dashboards/filters/` | `bi:bi_dashboard_filter_list` | `bi_dashboard_filter_list` |
| `dashboards/filters/create/` | `bi:bi_dashboard_filter_create` | `bi_dashboard_filter_create` |
| `dashboards/filters/<int:pk>/` | `bi:bi_dashboard_filter_detail` | `bi_dashboard_filter_detail` |
| `dashboards/filters/<int:pk>/edit/` | `bi:bi_dashboard_filter_edit` | `bi_dashboard_filter_edit` |
| `dashboards/filters/<int:pk>/delete/` | `bi:bi_dashboard_filter_delete` | `bi_dashboard_filter_delete` |

---

## 4. View Context Keys Contract (MANDATORY — Every Key Pinned)

### 4.1 Dashboard Views
- **`bi_dashboard_list`**:
  - `page_obj`: paginated Page object of `BiDashboard`
  - `dashboards`: `page_obj` alias
  - `category_choices`: `BiDashboard.CATEGORY_CHOICES`
  - `layout_choices`: `BiDashboard.LAYOUT_TYPE_CHOICES`
  - `theme_choices`: `BiDashboard.THEME_CHOICES`
  - `total_dashboards`: count of all tenant dashboards
  - `published_count`: count of published dashboards
  - `template_count`: count of template dashboards
  - `q`: search query string
  - `category`: selected category filter
  - `layout_type`: selected layout_type filter
  - `theme`: selected theme filter
  - `is_published`: selected publication status filter
- **`bi_dashboard_detail`**:
  - `dashboard`: `BiDashboard` instance
  - `widgets`: QuerySet of active `BiDashboardWidget` ordered by `pos_y, pos_x, sort_order`
  - `filters`: QuerySet of active `BiDashboardFilter` ordered by `order`
  - `bookmarks`: QuerySet of active user/shared `BiDashboardBookmark`
  - `total_widgets`: integer widget count
  - `user_default_bookmark`: `BiDashboardBookmark` instance or `None`
  - `can_edit`: boolean permission flag
- **`bi_dashboard_create` & `bi_dashboard_edit`**:
  - `form`: `BiDashboardForm` instance
  - `dashboard`: `BiDashboard` instance (edit mode) or `None` (create mode)
  - `is_edit`: boolean flag (`True` for edit, `False` for create)

### 4.2 Interactive Canvas Views
- **`bi_dashboard_canvas_view`**:
  - `dashboard`: `BiDashboard` instance
  - `widgets`: QuerySet of active `BiDashboardWidget`
  - `filters`: QuerySet of active `BiDashboardFilter`
  - `bookmarks`: QuerySet of user/shared `BiDashboardBookmark`
  - `active_bookmark`: `BiDashboardBookmark` instance or `None`
  - `filter_values_json`: serialized active filter values dict
  - `refresh_interval`: integer seconds
  - `is_kiosk`: boolean flag (`False`)
  - `theme`: theme string identifier
- **`bi_dashboard_kiosk_view`**:
  - `dashboard`: `BiDashboard` instance
  - `widgets`: QuerySet of active `BiDashboardWidget`
  - `refresh_interval`: integer seconds
  - `is_kiosk`: boolean flag (`True`)
  - `theme`: theme string identifier
- **`bi_dashboard_canvas_builder`**:
  - `dashboard`: `BiDashboard` instance
  - `widgets`: QuerySet of active `BiDashboardWidget`
  - `filters`: QuerySet of active `BiDashboardFilter`
  - `widget_type_choices`: `BiDashboardWidget.WIDGET_TYPE_CHOICES`
  - `semantic_models`: QuerySet of tenant `SemanticModel`
  - `warehouse_tables`: QuerySet of tenant `WarehouseTable`
  - `calculated_measures`: QuerySet of tenant `CalculatedMeasure`

### 4.3 Widget Views
- **`bi_dashboard_widget_list`**:
  - `page_obj`: paginated Page object of `BiDashboardWidget`
  - `widgets`: `page_obj` alias
  - `dashboards`: QuerySet of tenant `BiDashboard`
  - `widget_type_choices`: `BiDashboardWidget.WIDGET_TYPE_CHOICES`
  - `semantic_models`: QuerySet of tenant `SemanticModel`
  - `total_widgets`: integer count
  - `q`: search query string
  - `dashboard_id`: selected dashboard filter
  - `widget_type`: selected widget_type filter
- **`bi_dashboard_widget_detail`**:
  - `widget`: `BiDashboardWidget` instance
  - `dashboard`: `BiDashboard` parent instance
  - `chart_config_pretty`: formatted JSON string of `chart_config_json`
  - `data_preview`: sample rendered dataset preview
- **`bi_dashboard_widget_create` & `bi_dashboard_widget_edit`**:
  - `form`: `BiDashboardWidgetForm` instance
  - `widget`: `BiDashboardWidget` instance or `None`
  - `is_edit`: boolean flag

### 4.4 Bookmark Views
- **`bi_dashboard_bookmark_list`**:
  - `page_obj`: paginated Page object of `BiDashboardBookmark`
  - `bookmarks`: `page_obj` alias
  - `dashboards`: QuerySet of tenant `BiDashboard`
  - `total_bookmarks`: integer count
  - `q`: search query string
  - `dashboard_id`: selected dashboard filter
  - `is_shared`: selected shared filter
- **`bi_dashboard_bookmark_detail`**:
  - `bookmark`: `BiDashboardBookmark` instance
  - `dashboard`: `BiDashboard` parent instance
  - `filter_state_pretty`: formatted JSON string
  - `crossfilter_state_pretty`: formatted JSON string
- **`bi_dashboard_bookmark_create` & `bi_dashboard_bookmark_edit`**:
  - `form`: `BiDashboardBookmarkForm` instance
  - `bookmark`: `BiDashboardBookmark` instance or `None`
  - `is_edit`: boolean flag

### 4.5 Filter Views
- **`bi_dashboard_filter_list`**:
  - `page_obj`: paginated Page object of `BiDashboardFilter`
  - `filters`: `page_obj` alias
  - `dashboards`: QuerySet of tenant `BiDashboard`
  - `filter_type_choices`: `BiDashboardFilter.FILTER_TYPE_CHOICES`
  - `total_filters`: integer count
  - `q`: search query string
  - `dashboard_id`: selected dashboard filter
  - `filter_type`: selected filter_type filter
- **`bi_dashboard_filter_detail`**:
  - `filter_obj`: `BiDashboardFilter` instance
  - `dashboard`: `BiDashboard` parent instance
- **`bi_dashboard_filter_create` & `bi_dashboard_filter_edit`**:
  - `form`: `BiDashboardFilterForm` instance
  - `filter_obj`: `BiDashboardFilter` instance or `None`
  - `is_edit`: boolean flag

---

## 5. Templates Contract (`templates/bi/dashboards/`)

- `templates/bi/dashboards/dashboard/list.html`: Dashboard registry with search, category/layout/theme filters, KPI summary cards, publish/kiosk shortcuts.
- `templates/bi/dashboards/dashboard/detail.html`: Dashboard detail specification, widget listing, filters inventory, bookmark gallery.
- `templates/bi/dashboards/dashboard/form.html`: Create/edit dashboard with category, layout, theme, and security settings.
- `templates/bi/dashboards/canvas/viewer.html`: Interactive 12-column grid visual canvas with Chart.js, top filter controls, bookmark selector, auto-refresh timer, and full-screen kiosk support.
- `templates/bi/dashboards/widget/list.html`: All dashboard widgets across the tenant with type and dataset filters.
- `templates/bi/dashboards/widget/detail.html`: Widget inspect view with coordinates, chart options, and data source bindings.
- `templates/bi/dashboards/widget/form.html`: Create/edit widget with 13 chart types, dataset FKs, and grid positioning.
- `templates/bi/dashboards/bookmark/list.html`: Personal and shared view bookmarks with usage counters.
- `templates/bi/dashboards/bookmark/detail.html`: Bookmark state inspector and quick-apply link.
- `templates/bi/dashboards/bookmark/form.html`: Create/edit bookmark.
- `templates/bi/dashboards/filter/list.html`: Global dashboard filter register.
- `templates/bi/dashboards/filter/detail.html`: Filter definition details and source preview.
- `templates/bi/dashboards/filter/form.html`: Create/edit dashboard filter with options source config.

---

## 6. Navigation LIVE_LINKS["10.8"] Contract

In `apps/core/navigation.py`:

```python
    # 10.8 Dashboards & Visualization
    "10.8": {
        "Interactive Dashboards": "bi:bi_dashboard_list",
        "Visualization Library": "bi:bi_dashboard_widget_list",
        "Drag-and-Drop Dashboard Builder": "bi:bi_dashboard_list",
        "Personalization & Bookmarks": "bi:bi_dashboard_bookmark_list",
        "Real-Time & Streaming Visuals": "bi:bi_dashboard_filter_list",
        # Extra live leaves
        "Dashboards": "bi:bi_dashboard_list",
        "Dashboard Widgets": "bi:bi_dashboard_widget_list",
        "View Bookmarks": "bi:bi_dashboard_bookmark_list",
        "Dashboard Filters": "bi:bi_dashboard_filter_list",
    },
```
