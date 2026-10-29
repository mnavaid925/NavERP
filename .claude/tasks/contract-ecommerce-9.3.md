# Contract — Sub-module 9.3: Pricing & Promotion Engine (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.3 Pricing & Promotion Engine · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-29 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0003_...` or next available.

---

## 1. Models & CHOICES Contract

All models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `DynamicPriceRule` (`apps/ecommerce/models/PricingPromotion/DynamicPriceRules.py`)
- **Table:** `ecommerce_dynamic_price_rule`
- **Number Prefix:** `EDPR` (`EDPR-00001`)
- **CHOICES:**
  - `RULE_TYPE_CHOICES = [('percentage_discount', 'Percentage Discount'), ('fixed_discount', 'Fixed Discount Amount'), ('fixed_price_override', 'Fixed Price Override')]`
  - `SCOPE_CHOICES = [('storewide', 'Storewide'), ('category', 'Category'), ('product', 'Specific Product'), ('variant', 'Specific SKU Variant')]`
  - `CUSTOMER_SEGMENT_CHOICES = [('all', 'All Customers'), ('retail', 'Retail / Standard'), ('wholesale', 'Wholesale / B2B'), ('vip', 'VIP / Key Accounts')]`
  - `LOYALTY_TIER_CHOICES = [('none', 'No Loyalty Requirement'), ('bronze', 'Bronze Tier'), ('silver', 'Silver Tier'), ('gold', 'Gold Tier'), ('platinum', 'Platinum Tier')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_dynamic_price_rules')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255)`
  - `rule_type`: `CharField(max_length=30, choices=RULE_TYPE_CHOICES, default='percentage_discount')`
  - `adjustment_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `scope`: `CharField(max_length=20, choices=SCOPE_CHOICES, default='storewide')`
  - `category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='dynamic_price_rules')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='dynamic_price_rules')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='dynamic_price_rules')`
  - `customer_segment`: `CharField(max_length=20, choices=CUSTOMER_SEGMENT_CHOICES, default='all')`
  - `loyalty_tier`: `CharField(max_length=20, choices=LOYALTY_TIER_CHOICES, default='none')`
  - `min_quantity`: `PositiveIntegerField(default=1)`
  - `country_code`: `CharField(max_length=2, blank=True)`
  - `currency_code`: `CharField(max_length=3, default='USD')`
  - `valid_from`: `DateTimeField(default=timezone.now)`
  - `valid_to`: `DateTimeField(null=True, blank=True)`
  - `priority`: `PositiveIntegerField(default=10)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_dpr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'priority'], name='ecom_dpr_tnt_act_prio_idx')`
  - `Index(fields=['tenant', 'scope'], name='ecom_dpr_tnt_scope_idx')`
  - `Index(fields=['tenant', 'customer_segment'], name='ecom_dpr_tnt_seg_idx')`

### 1.2 `CouponPromotion` (`apps/ecommerce/models/PricingPromotion/CouponPromotions.py`)
- **Table:** `ecommerce_coupon_promotion`
- **Number Prefix:** `ECPN` (`ECPN-00001`)
- **CHOICES:**
  - `DISCOUNT_TYPE_CHOICES = [('percentage', 'Percentage Off Cart'), ('fixed_cart', 'Fixed Amount Off Cart'), ('fixed_item', 'Fixed Amount Off Item'), ('free_shipping', 'Free Shipping')]`
  - `LOYALTY_TIER_CHOICES = [('none', 'No Loyalty Requirement'), ('bronze', 'Bronze Tier'), ('silver', 'Silver Tier'), ('gold', 'Gold Tier'), ('platinum', 'Platinum Tier')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_coupon_promotions')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `code`: `CharField(max_length=50)` (stored uppercase)
  - `name`: `CharField(max_length=255)`
  - `discount_type`: `CharField(max_length=30, choices=DISCOUNT_TYPE_CHOICES, default='percentage')`
  - `discount_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `min_spend`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `max_discount_amount`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `usage_limit_total`: `PositiveIntegerField(null=True, blank=True)`
  - `usage_limit_per_customer`: `PositiveIntegerField(default=1)`
  - `used_count`: `PositiveIntegerField(default=0)`
  - `is_stackable`: `BooleanField(default=False)`
  - `loyalty_tier_required`: `CharField(max_length=20, choices=LOYALTY_TIER_CHOICES, default='none')`
  - `customer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_coupons')`
  - `valid_from`: `DateTimeField(default=timezone.now)`
  - `valid_to`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_cpn_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecom_cpn_tenant_code_uniq')`
  - `Index(fields=['tenant', 'is_active', 'code'], name='ecom_cpn_tnt_act_code_idx')`
  - `Index(fields=['tenant', 'discount_type'], name='ecom_cpn_tnt_type_idx')`

### 1.3 `FlashSale` (`apps/ecommerce/models/PricingPromotion/FlashSales.py`)
- **Table:** `ecommerce_flash_sale`
- **Number Prefix:** `EFLS` (`EFLS-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft'), ('scheduled', 'Scheduled'), ('active', 'Active'), ('paused', 'Paused'), ('ended', 'Ended')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_flash_sales')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=255)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='flash_sales')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='flash_sales')`
  - `category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='flash_sales')`
  - `discount_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))`
  - `flash_price`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `inventory_cap`: `PositiveIntegerField(default=100)`
  - `units_sold`: `PositiveIntegerField(default=0)`
  - `max_units_per_order`: `PositiveIntegerField(default=2)`
  - `start_time`: `DateTimeField(default=timezone.now)`
  - `end_time`: `DateTimeField()`
  - `badge_label`: `CharField(max_length=50, default='FLASH DEAL')`
  - `banner_bg_color`: `CharField(max_length=20, default='#ef4444')`
  - `terms_and_conditions`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_fls_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'start_time', 'end_time'], name='ecom_fls_tnt_stat_time_idx')`

### 1.4 `CompetitorPriceMonitor` (`apps/ecommerce/models/PricingPromotion/CompetitorPriceMonitors.py`)
- **Table:** `ecommerce_competitor_price_monitor`
- **Number Prefix:** `ECPM` (`ECPM-00001`)
- **CHOICES:**
  - `STRATEGY_CHOICES = [('manual', 'Manual Review Only'), ('match_exact', 'Match Competitor Exact Price'), ('beat_by_fixed', 'Beat Competitor by Fixed Amount'), ('beat_by_percent', 'Beat Competitor by Percentage')]`
  - `STATUS_CHOICES = [('active', 'Active Tracking'), ('paused', 'Paused'), ('margin_suppressed', 'Suppressed (Margin Risk)'), ('out_of_stock', 'Competitor Out of Stock')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_competitor_monitors')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `competitor_name`: `CharField(max_length=120)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='competitor_monitors')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=CASCADE, related_name='competitor_monitors')`
  - `competitor_url`: `URLField(max_length=500)`
  - `competitor_price`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `competitor_currency`: `CharField(max_length=3, default='USD')`
  - `is_in_stock`: `BooleanField(default=True)`
  - `last_scraped_at`: `DateTimeField(null=True, blank=True)`
  - `match_strategy`: `CharField(max_length=30, choices=STRATEGY_CHOICES, default='manual')`
  - `beat_by_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `min_margin_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))`
  - `floor_price`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='active')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_cpm_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'variant'], name='ecom_cpm_tnt_stat_var_idx')`

---

## 2. Forms Contract & Form Exclusions

Every form inherits `apps.ecommerce.forms._common.BaseEcommerceModelForm` or standard `forms.ModelForm`. Exclude non-editable system attributes.

### 2.1 `DynamicPriceRuleForm` (`apps/ecommerce/forms/PricingPromotion/DynamicPriceRules.py`)
- **Model:** `DynamicPriceRule`
- **Fields:** `['name', 'rule_type', 'adjustment_value', 'scope', 'category', 'product', 'variant', 'customer_segment', 'loyalty_tier', 'min_quantity', 'country_code', 'currency_code', 'valid_from', 'valid_to', 'priority', 'is_active', 'description']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Widgets:** Tailwind styled inputs (`form-input`, `form-select`, `form-textarea`)

### 2.2 `CouponPromotionForm` (`apps/ecommerce/forms/PricingPromotion/CouponPromotions.py`)
- **Model:** `CouponPromotion`
- **Fields:** `['code', 'name', 'discount_type', 'discount_value', 'min_spend', 'max_discount_amount', 'usage_limit_total', 'usage_limit_per_customer', 'is_stackable', 'loyalty_tier_required', 'customer', 'valid_from', 'valid_to', 'is_active']`
- **Excludes:** `['tenant', 'number', 'used_count', 'created_at', 'updated_at']`
- **Clean:** Uppercase `code.strip().upper()`

### 2.3 `FlashSaleForm` (`apps/ecommerce/forms/PricingPromotion/FlashSales.py`)
- **Model:** `FlashSale`
- **Fields:** `['title', 'status', 'product', 'variant', 'category', 'discount_percentage', 'flash_price', 'inventory_cap', 'max_units_per_order', 'start_time', 'end_time', 'badge_label', 'banner_bg_color', 'terms_and_conditions']`
- **Excludes:** `['tenant', 'number', 'units_sold', 'created_at', 'updated_at']`
- **Clean:** Validate `end_time > start_time`

### 2.4 `CompetitorPriceMonitorForm` (`apps/ecommerce/forms/PricingPromotion/CompetitorPriceMonitors.py`)
- **Model:** `CompetitorPriceMonitor`
- **Fields:** `['competitor_name', 'product', 'variant', 'competitor_url', 'competitor_price', 'competitor_currency', 'is_in_stock', 'match_strategy', 'beat_by_value', 'min_margin_pct', 'floor_price', 'status', 'notes']`
- **Excludes:** `['tenant', 'number', 'last_scraped_at', 'created_at', 'updated_at']`

---

## 3. URLs Contract (Route Names & Paths)

Namespace: `ecommerce:` (set in `apps/ecommerce/urls/__init__.py`)

| URL Name | Pattern | View Function |
|---|---|---|
| `dynamicpricerule_list` | `pricing/rules/` | `dynamicpricerule_list` |
| `dynamicpricerule_create` | `pricing/rules/create/` | `dynamicpricerule_create` |
| `dynamicpricerule_detail` | `pricing/rules/<int:pk>/` | `dynamicpricerule_detail` |
| `dynamicpricerule_edit` | `pricing/rules/<int:pk>/edit/` | `dynamicpricerule_edit` |
| `dynamicpricerule_delete` | `pricing/rules/<int:pk>/delete/` | `dynamicpricerule_delete` |
| `couponpromotion_list` | `pricing/coupons/` | `couponpromotion_list` |
| `couponpromotion_create` | `pricing/coupons/create/` | `couponpromotion_create` |
| `couponpromotion_detail` | `pricing/coupons/<int:pk>/` | `couponpromotion_detail` |
| `couponpromotion_edit` | `pricing/coupons/<int:pk>/edit/` | `couponpromotion_edit` |
| `couponpromotion_delete` | `pricing/coupons/<int:pk>/delete/` | `couponpromotion_delete` |
| `flashsale_list` | `pricing/flash-sales/` | `flashsale_list` |
| `flashsale_create` | `pricing/flash-sales/create/` | `flashsale_create` |
| `flashsale_detail` | `pricing/flash-sales/<int:pk>/` | `flashsale_detail` |
| `flashsale_edit` | `pricing/flash-sales/<int:pk>/edit/` | `flashsale_edit` |
| `flashsale_delete` | `pricing/flash-sales/<int:pk>/delete/` | `flashsale_delete` |
| `competitorpricemonitor_list` | `pricing/competitors/` | `competitorpricemonitor_list` |
| `competitorpricemonitor_create` | `pricing/competitors/create/` | `competitorpricemonitor_create` |
| `competitorpricemonitor_detail` | `pricing/competitors/<int:pk>/` | `competitorpricemonitor_detail` |
| `competitorpricemonitor_edit` | `pricing/competitors/<int:pk>/edit/` | `competitorpricemonitor_edit` |
| `competitorpricemonitor_delete` | `pricing/competitors/<int:pk>/delete/` | `competitorpricemonitor_delete` |
| `competitorpricemonitor_sync` | `pricing/competitors/<int:pk>/sync/` | `competitorpricemonitor_sync` |

---

## 4. View Context Contract

Pinning every context key across all 9.3 views:

### 4.1 DynamicPriceRule Views
- `dynamicpricerule_list`:
  - `page_obj`: paginated `DynamicPriceRule` queryset
  - `rules`: `page_obj.object_list`
  - `rule_type_choices`: `DynamicPriceRule.RULE_TYPE_CHOICES`
  - `scope_choices`: `DynamicPriceRule.SCOPE_CHOICES`
  - `segment_choices`: `DynamicPriceRule.CUSTOMER_SEGMENT_CHOICES`
  - `categories`: `StoreCategory.objects.filter(tenant=request.tenant)`
  - `current_q`: `request.GET.get('q', '')`
  - `current_type`: `request.GET.get('rule_type', '')`
  - `current_scope`: `request.GET.get('scope', '')`
  - `current_segment`: `request.GET.get('customer_segment', '')`
- `dynamicpricerule_detail`:
  - `rule`: `DynamicPriceRule` object
- `dynamicpricerule_create` / `dynamicpricerule_edit`:
  - `form`: `DynamicPriceRuleForm`
  - `rule`: `DynamicPriceRule` object (edit mode only)
  - `is_edit`: boolean

### 4.2 CouponPromotion Views
- `couponpromotion_list`:
  - `page_obj`: paginated `CouponPromotion` queryset
  - `coupons`: `page_obj.object_list`
  - `discount_type_choices`: `CouponPromotion.DISCOUNT_TYPE_CHOICES`
  - `loyalty_tier_choices`: `CouponPromotion.LOYALTY_TIER_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_type`: `request.GET.get('discount_type', '')`
  - `current_tier`: `request.GET.get('loyalty_tier', '')`
  - `current_status`: `request.GET.get('status', '')`
- `couponpromotion_detail`:
  - `coupon`: `CouponPromotion` object
- `couponpromotion_create` / `couponpromotion_edit`:
  - `form`: `CouponPromotionForm`
  - `coupon`: `CouponPromotion` object (edit mode only)
  - `is_edit`: boolean

### 4.3 FlashSale Views
- `flashsale_list`:
  - `page_obj`: paginated `FlashSale` queryset
  - `sales`: `page_obj.object_list`
  - `status_choices`: `FlashSale.STATUS_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_status`: `request.GET.get('status', '')`
- `flashsale_detail`:
  - `sale`: `FlashSale` object
- `flashsale_create` / `flashsale_edit`:
  - `form`: `FlashSaleForm`
  - `sale`: `FlashSale` object (edit mode only)
  - `is_edit`: boolean

### 4.4 CompetitorPriceMonitor Views
- `competitorpricemonitor_list`:
  - `page_obj`: paginated `CompetitorPriceMonitor` queryset
  - `monitors`: `page_obj.object_list`
  - `strategy_choices`: `CompetitorPriceMonitor.STRATEGY_CHOICES`
  - `status_choices`: `CompetitorPriceMonitor.STATUS_CHOICES`
  - `variants`: `ProductVariant.objects.filter(tenant=request.tenant)`
  - `current_q`: `request.GET.get('q', '')`
  - `current_strategy`: `request.GET.get('strategy', '')`
  - `current_status`: `request.GET.get('status', '')`
- `competitorpricemonitor_detail`:
  - `monitor`: `CompetitorPriceMonitor` object
- `competitorpricemonitor_create` / `competitorpricemonitor_edit`:
  - `form`: `CompetitorPriceMonitorForm`
  - `monitor`: `CompetitorPriceMonitor` object (edit mode only)
  - `is_edit`: boolean

---

## 5. Navigation `LIVE_LINKS` Contract

File: `apps/core/navigation.py`
Entry: `LIVE_LINKS["9.3"]`
```python
    "9.3": {
        "Dynamic Pricing Rules": "ecommerce:dynamicpricerule_list",
        "Discount & Coupon Management": "ecommerce:couponpromotion_list",
        "Flash Sales & Limited-Time Offers": "ecommerce:flashsale_list",
        "Loyalty & Rewards Pricing": "ecommerce:couponpromotion_list",
        "Price Matching & Competitive Monitoring": "ecommerce:competitorpricemonitor_list",
    },
```

---

## 6. Color-Named Badge Contract

Only use color-named badges from `static/css/theme.css`:
- `badge-green`: Active status, matched, in-stock
- `badge-red`: Expired, ended, paused, out-of-stock, margin risk
- `badge-amber`: Scheduled, draft, manual review
- `badge-info`: Storewide, percentage, VIP, platinum
- `badge-slate` / `badge-muted`: Archived, inactive
