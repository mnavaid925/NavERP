# Contract — Sub-module 9.15: Analytics & Business Intelligence (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.15 Analytics & Business Intelligence · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-01 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0027_...`
- **Package Layout:** `AnalyticsBi/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/analytics_bi/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `DailySalesSnapshot` (`apps/ecommerce/models/AnalyticsBi/DailySalesSnapshots.py`)
- **Table:** `ecommerce_daily_sales_snapshot`
- **Number Prefix:** `EDSS` (`EDSS-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `snapshot_date`: `DateField(db_index=True, help_text="Date of sales aggregation")`
  - `currency`: `CharField(max_length=3, default="USD", help_text="Currency ISO code")`
  - `gross_sales`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `discounts_total`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `refunds_total`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `net_sales`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `shipping_collected`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `taxes_collected`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `cost_of_goods_sold`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `gross_profit`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `orders_count`: `PositiveIntegerField(default=0)`
  - `units_sold`: `PositiveIntegerField(default=0)`
  - `average_order_value`: `DecimalField(max_digits=10, decimal_places=2, default=0.00)`
  - `carts_created`: `PositiveIntegerField(default=0)`
  - `carts_abandoned`: `PositiveIntegerField(default=0)`
  - `conversion_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
  - `is_finalized`: `BooleanField(default=False, help_text="True if closed day snapshot")`
  - `notes`: `CharField(max_length=255, blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_edss_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'snapshot_date', 'currency'], name='ecommerce_edss_tenant_date_curr_uniq')`
  - `Index(fields=['tenant', 'snapshot_date'], name='idx_edss_ten_date')`
  - `Index(fields=['tenant', 'is_finalized'], name='idx_edss_ten_fin')`

---

### 1.2 `CustomerCohortMetric` (`apps/ecommerce/models/AnalyticsBi/CustomerCohortMetrics.py`)
- **Table:** `ecommerce_customer_cohort_metric`
- **Number Prefix:** `ECCM` (`ECCM-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `cohort_month`: `DateField(db_index=True, help_text="First day of acquisition month")`
  - `period_offset_months`: `PositiveSmallIntegerField(default=0, help_text="Months since acquisition (0=acquisition month, 1, 2...)")`
  - `initial_cohort_size`: `PositiveIntegerField(default=0, help_text="Total distinct customers acquired in cohort month")`
  - `active_customers`: `PositiveIntegerField(default=0, help_text="Customers from cohort making an order in offset month")`
  - `retention_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
  - `cohort_orders_count`: `PositiveIntegerField(default=0)`
  - `cumulative_gross_revenue`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `cumulative_net_revenue`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `cumulative_margin`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `cumulative_ltv_per_customer`: `DecimalField(max_digits=10, decimal_places=2, default=0.00)`
  - `churn_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
  - `acquisition_channel_tag`: `CharField(max_length=64, blank=True, default="", help_text="Optional segment or channel tag")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eccm_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'cohort_month', 'period_offset_months', 'acquisition_channel_tag'], name='ecommerce_eccm_ten_coh_off_tag_uniq')`
  - `Index(fields=['tenant', 'cohort_month'], name='idx_eccm_ten_month')`

---

### 1.3 `ProductMerchandisingMetric` (`apps/ecommerce/models/AnalyticsBi/ProductMerchandisingMetrics.py`)
- **Table:** `ecommerce_product_merchandising_metric`
- **Number Prefix:** `EPMM` (`EPMM-00001`)
- **CHOICES:**
  - `VELOCITY_TIER_CHOICES = [('best_seller', 'Best Seller (Top Velocity)'), ('core_performer', 'Core Performer'), ('slow_mover', 'Slow Mover'), ('dead_stock', 'Dead Stock / Dormant')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='merchandising_metrics')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', null=True, blank=True, on_delete=SET_NULL, related_name='merchandising_metrics')`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `velocity_tier`: `CharField(max_length=20, choices=VELOCITY_TIER_CHOICES, default='core_performer')`
  - `units_sold`: `PositiveIntegerField(default=0)`
  - `gross_revenue`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `cost_of_goods`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `gross_margin_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
  - `refunds_count`: `PositiveIntegerField(default=0)`
  - `return_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
  - `page_views_count`: `PositiveIntegerField(default=0)`
  - `add_to_cart_count`: `PositiveIntegerField(default=0)`
  - `conversion_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
  - `inventory_turnover_ratio`: `DecimalField(max_digits=6, decimal_places=2, default=0.00)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_epmm_tenant_num_uniq')`
  - `Index(fields=['tenant', 'velocity_tier'], name='idx_epmm_ten_tier')`
  - `Index(fields=['tenant', 'product', 'period_end'], name='idx_epmm_ten_prd_end')`

---

### 1.4 `AttributionTouchpoint` (`apps/ecommerce/models/AnalyticsBi/AttributionTouchpoints.py`)
- **Table:** `ecommerce_attribution_touchpoint`
- **Number Prefix:** `EATT` (`EATT-00001`)
- **CHOICES:**
  - `CHANNEL_CHOICES = [('organic_search', 'Organic Search'), ('paid_search', 'Paid Search (SEM)'), ('paid_social', 'Paid Social Ads'), ('email', 'Email Marketing'), ('affiliate', 'Affiliate / Partner'), ('direct', 'Direct Storefront Traffic'), ('referral', 'Referral Traffic'), ('influencer', 'Influencer Campaign'), ('other', 'Other')]`
  - `ATTRIBUTION_MODEL_CHOICES = [('first_touch', 'First Touch (100% Acquisition)'), ('last_touch', 'Last Touch (100% Conversion)'), ('linear', 'Linear Multi-Touch'), ('time_decay', 'Time Decay')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', null=True, blank=True, on_delete=SET_NULL, related_name='attribution_touchpoints')`
  - `cart`: `ForeignKey('ecommerce.Cart', null=True, blank=True, on_delete=SET_NULL, related_name='attribution_touchpoints')`
  - `channel_type`: `CharField(max_length=32, choices=CHANNEL_CHOICES, default='direct')`
  - `attribution_model`: `CharField(max_length=20, choices=ATTRIBUTION_MODEL_CHOICES, default='last_touch')`
  - `campaign`: `ForeignKey('ecommerce.MarketingCampaign', null=True, blank=True, on_delete=SET_NULL, related_name='attribution_touchpoints')`
  - `affiliate`: `ForeignKey('ecommerce.AffiliatePartner', null=True, blank=True, on_delete=SET_NULL, related_name='attribution_touchpoints')`
  - `utm_source`: `CharField(max_length=100, blank=True, default="")`
  - `utm_medium`: `CharField(max_length=100, blank=True, default="")`
  - `utm_campaign`: `CharField(max_length=100, blank=True, default="")`
  - `touchpoint_timestamp`: `DateTimeField()`
  - `attribution_weight`: `DecimalField(max_digits=5, decimal_places=4, default=1.0000)`
  - `attributed_revenue`: `DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - `estimated_cac`: `DecimalField(max_digits=10, decimal_places=2, default=0.00)`
  - `landing_page_url`: `CharField(max_length=255, blank=True, default="")`
  - `referrer_url`: `CharField(max_length=255, blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eatt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'channel_type'], name='idx_eatt_ten_channel')`
  - `Index(fields=['tenant', 'order'], name='idx_eatt_ten_order')`
  - `Index(fields=['tenant', 'campaign'], name='idx_eatt_ten_camp')`

---

## 2. Forms Contract

All forms inherit from `apps.ecommerce.forms._common.TenantModelForm`.

### 2.1 `DailySalesSnapshotForm` (`apps/ecommerce/forms/AnalyticsBi/DailySalesSnapshots.py`)
- **Fields included:** `snapshot_date`, `currency`, `gross_sales`, `discounts_total`, `refunds_total`, `net_sales`, `shipping_collected`, `taxes_collected`, `cost_of_goods_sold`, `gross_profit`, `orders_count`, `units_sold`, `average_order_value`, `carts_created`, `carts_abandoned`, `conversion_rate_pct`, `is_finalized`, `notes`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`

### 2.2 `CustomerCohortMetricForm` (`apps/ecommerce/forms/AnalyticsBi/CustomerCohortMetrics.py`)
- **Fields included:** `cohort_month`, `period_offset_months`, `initial_cohort_size`, `active_customers`, `retention_rate_pct`, `cohort_orders_count`, `cumulative_gross_revenue`, `cumulative_net_revenue`, `cumulative_margin`, `cumulative_ltv_per_customer`, `churn_rate_pct`, `acquisition_channel_tag`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`

### 2.3 `ProductMerchandisingMetricForm` (`apps/ecommerce/forms/AnalyticsBi/ProductMerchandisingMetrics.py`)
- **Fields included:** `product`, `variant`, `period_start`, `period_end`, `velocity_tier`, `units_sold`, `gross_revenue`, `cost_of_goods`, `gross_margin_pct`, `refunds_count`, `return_rate_pct`, `page_views_count`, `add_to_cart_count`, `conversion_rate_pct`, `inventory_turnover_ratio`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`

### 2.4 `AttributionTouchpointForm` (`apps/ecommerce/forms/AnalyticsBi/AttributionTouchpoints.py`)
- **Fields included:** `order`, `cart`, `channel_type`, `attribution_model`, `campaign`, `affiliate`, `utm_source`, `utm_medium`, `utm_campaign`, `touchpoint_timestamp`, `attribution_weight`, `attributed_revenue`, `estimated_cac`, `landing_page_url`, `referrer_url`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`

---

## 3. URLs Contract

All routes live under namespace `ecommerce:` in `apps/ecommerce/urls/AnalyticsBi/`:

```python
# DailySalesSnapshot
path('analytics/sales-snapshots/', views.dailysalessnapshot_list, name='dailysalessnapshot_list'),
path('analytics/sales-snapshots/create/', views.dailysalessnapshot_create, name='dailysalessnapshot_create'),
path('analytics/sales-snapshots/<int:pk>/', views.dailysalessnapshot_detail, name='dailysalessnapshot_detail'),
path('analytics/sales-snapshots/<int:pk>/edit/', views.dailysalessnapshot_edit, name='dailysalessnapshot_edit'),
path('analytics/sales-snapshots/<int:pk>/delete/', views.dailysalessnapshot_delete, name='dailysalessnapshot_delete'),
path('analytics/sales-snapshots/generate/', views.dailysalessnapshot_generate, name='dailysalessnapshot_generate'),

# CustomerCohortMetric
path('analytics/cohorts/', views.customercohortmetric_list, name='customercohortmetric_list'),
path('analytics/cohorts/create/', views.customercohortmetric_create, name='customercohortmetric_create'),
path('analytics/cohorts/<int:pk>/', views.customercohortmetric_detail, name='customercohortmetric_detail'),
path('analytics/cohorts/<int:pk>/edit/', views.customercohortmetric_edit, name='customercohortmetric_edit'),
path('analytics/cohorts/<int:pk>/delete/', views.customercohortmetric_delete, name='customercohortmetric_delete'),
path('analytics/cohorts/recalculate/', views.customercohortmetric_recalculate, name='customercohortmetric_recalculate'),

# ProductMerchandisingMetric
path('analytics/merchandising/', views.productmerchandisingmetric_list, name='productmerchandisingmetric_list'),
path('analytics/merchandising/create/', views.productmerchandisingmetric_create, name='productmerchandisingmetric_create'),
path('analytics/merchandising/<int:pk>/', views.productmerchandisingmetric_detail, name='productmerchandisingmetric_detail'),
path('analytics/merchandising/<int:pk>/edit/', views.productmerchandisingmetric_edit, name='productmerchandisingmetric_edit'),
path('analytics/merchandising/<int:pk>/delete/', views.productmerchandisingmetric_delete, name='productmerchandisingmetric_delete'),
path('analytics/merchandising/reclassify/', views.productmerchandisingmetric_reclassify, name='productmerchandisingmetric_reclassify'),

# AttributionTouchpoint
path('analytics/attribution/', views.attributiontouchpoint_list, name='attributiontouchpoint_list'),
path('analytics/attribution/create/', views.attributiontouchpoint_create, name='attributiontouchpoint_create'),
path('analytics/attribution/<int:pk>/', views.attributiontouchpoint_detail, name='attributiontouchpoint_detail'),
path('analytics/attribution/<int:pk>/edit/', views.attributiontouchpoint_edit, name='attributiontouchpoint_edit'),
path('analytics/attribution/<int:pk>/delete/', views.attributiontouchpoint_delete, name='attributiontouchpoint_delete'),

# Real-Time Operational Cockpit
path('analytics/cockpit/', views.analytics_cockpit, name='analytics_cockpit'),
```

---

## 4. View Context Keys Contract (L7 Pinned)

### 4.1 `DailySalesSnapshot` Views
- `dailysalessnapshot_list`:
  - Template: `ecommerce/analytics_bi/daily_sales_snapshot/list.html`
  - Context keys:
    - `snapshots`: Paged queryset of `DailySalesSnapshot`
    - `selected_currency`: `request.GET.get('currency', '')`
    - `selected_finalized`: `request.GET.get('is_finalized', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `dailysalessnapshot_detail`:
  - Template: `ecommerce/analytics_bi/daily_sales_snapshot/detail.html`
  - Context keys:
    - `snapshot`: Single `DailySalesSnapshot` instance
- `dailysalessnapshot_create` / `dailysalessnapshot_edit`:
  - Template: `ecommerce/analytics_bi/daily_sales_snapshot/form.html`
  - Context keys:
    - `form`: `DailySalesSnapshotForm`
    - `snapshot`: `DailySalesSnapshot` instance (edit) or `None` (create)

### 4.2 `CustomerCohortMetric` Views
- `customercohortmetric_list`:
  - Template: `ecommerce/analytics_bi/customer_cohort_metric/list.html`
  - Context keys:
    - `cohort_metrics`: Paged queryset of `CustomerCohortMetric`
    - `selected_channel`: `request.GET.get('channel', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `customercohortmetric_detail`:
  - Template: `ecommerce/analytics_bi/customer_cohort_metric/detail.html`
  - Context keys:
    - `cohort_metric`: Single `CustomerCohortMetric` instance
- `customercohortmetric_create` / `customercohortmetric_edit`:
  - Template: `ecommerce/analytics_bi/customer_cohort_metric/form.html`
  - Context keys:
    - `form`: `CustomerCohortMetricForm`
    - `cohort_metric`: `CustomerCohortMetric` instance (edit) or `None` (create)

### 4.3 `ProductMerchandisingMetric` Views
- `productmerchandisingmetric_list`:
  - Template: `ecommerce/analytics_bi/product_merchandising_metric/list.html`
  - Context keys:
    - `metrics`: Paged queryset of `ProductMerchandisingMetric`
    - `velocity_tier_choices`: `ProductMerchandisingMetric.VELOCITY_TIER_CHOICES`
    - `selected_velocity_tier`: `request.GET.get('velocity_tier', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `productmerchandisingmetric_detail`:
  - Template: `ecommerce/analytics_bi/product_merchandising_metric/detail.html`
  - Context keys:
    - `metric`: Single `ProductMerchandisingMetric` instance
- `productmerchandisingmetric_create` / `productmerchandisingmetric_edit`:
  - Template: `ecommerce/analytics_bi/product_merchandising_metric/form.html`
  - Context keys:
    - `form`: `ProductMerchandisingMetricForm`
    - `metric`: `ProductMerchandisingMetric` instance (edit) or `None` (create)

### 4.4 `AttributionTouchpoint` Views
- `attributiontouchpoint_list`:
  - Template: `ecommerce/analytics_bi/attribution_touchpoint/list.html`
  - Context keys:
    - `touchpoints`: Paged queryset of `AttributionTouchpoint`
    - `channel_choices`: `AttributionTouchpoint.CHANNEL_CHOICES`
    - `attribution_model_choices`: `AttributionTouchpoint.ATTRIBUTION_MODEL_CHOICES`
    - `selected_channel`: `request.GET.get('channel', '')`
    - `selected_model`: `request.GET.get('model', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `attributiontouchpoint_detail`:
  - Template: `ecommerce/analytics_bi/attribution_touchpoint/detail.html`
  - Context keys:
    - `touchpoint`: Single `AttributionTouchpoint` instance
- `attributiontouchpoint_create` / `attributiontouchpoint_edit`:
  - Template: `ecommerce/analytics_bi/attribution_touchpoint/form.html`
  - Context keys:
    - `form`: `AttributionTouchpointForm`
    - `touchpoint`: `AttributionTouchpoint` instance (edit) or `None` (create)

### 4.5 `AnalyticsCockpit` View
- `analytics_cockpit`:
  - Template: `ecommerce/analytics_bi/cockpit/cockpit.html`
  - Context keys:
    - `today_revenue`: Decimal
    - `today_orders_count`: Int
    - `today_aov`: Decimal
    - `active_carts_count`: Int
    - `abandoned_carts_count`: Int
    - `cart_recovery_rate_pct`: Decimal
    - `funnel_stages`: List of dicts `[{"stage": str, "count": int, "pct": float}]`
    - `recent_snapshots`: Queryset of 7 recent `DailySalesSnapshot`
    - `top_best_sellers`: Queryset of top 5 `ProductMerchandisingMetric`
    - `channel_attribution_summary`: List of dicts `[{"channel": str, "revenue": Decimal, "orders": int}]`
    - `trend_labels_json`: JSON string of dates
    - `trend_revenue_json`: JSON string of revenue numbers

---

## 5. Design System & Badge Class Contract (L33)

Only use colour-named classes from `static/css/theme.css`:
- `badge-green`: `best_seller`, `finalized`, `first_touch`, `high_retention`
- `badge-red`: `dead_stock`, `high_churn`, `abandoned`
- `badge-amber`: `slow_mover`, `pending`, `medium_churn`
- `badge-info`: `core_performer`, `linear`, `last_touch`, `paid_search`, `paid_social`
- `badge-slate` / `badge-muted`: `draft`, `direct`, `other`
