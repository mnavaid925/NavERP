# Contract — Sub-module 9.2: Inventory & Stock Management (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.2 Inventory & Stock Management · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-29 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0003_...`.

---

## 1. Models & CHOICES Contract

All models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `FulfillmentCenter` (`apps/ecommerce/models/InventoryStock/FulfillmentCenters.py`)
- **Table:** `ecommerce_fulfillment_center`
- **Number Prefix:** `EFC` (`EFC-00001`)
- **CHOICES:**
  - `CENTER_TYPE_CHOICES = [('internal_warehouse', 'Internal Warehouse / DC'), ('third_party_3pl', '3PL Partner (ShipBob/FBA)'), ('retail_store', 'Retail Store (Local Pickup/SFS)'), ('dropshipper', 'Drop-Ship Vendor Facility')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_fulfillment_centers')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `code`: `CharField(max_length=30)` (unique per tenant)
  - `center_type`: `CharField(max_length=30, choices=CENTER_TYPE_CHOICES, default='internal_warehouse')`
  - `location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_fulfillment_centers')`
  - `priority`: `PositiveSmallIntegerField(default=1)`
  - `is_active`: `BooleanField(default=True)`
  - `supports_pick_pack_ship`: `BooleanField(default=True)`
  - `supports_customer_pickup`: `BooleanField(default=False)`
  - `daily_cutoff_time`: `TimeField(null=True, blank=True)`
  - `address_line1`: `CharField(max_length=255, blank=True)`
  - `city`: `CharField(max_length=100, blank=True)`
  - `state`: `CharField(max_length=100, blank=True)`
  - `postal_code`: `CharField(max_length=20, blank=True)`
  - `country`: `CharField(max_length=100, default='United States')`
  - `contact_email`: `EmailField(blank=True)`
  - `contact_phone`: `CharField(max_length=30, blank=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_fc_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecom_fc_tenant_code_uniq')`
  - `Index(fields=['tenant', 'is_active', 'priority'], name='ecom_fc_tnt_act_prio_idx')`
  - `Index(fields=['tenant', 'center_type'], name='ecom_fc_tnt_type_idx')`

### 1.2 `InventoryAllocation` (`apps/ecommerce/models/InventoryStock/InventoryAllocations.py`)
- **Table:** `ecommerce_inventory_allocation`
- **Number Prefix:** `EAL` (`EAL-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_inventory_allocations')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='inventory_allocations')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=CASCADE, related_name='inventory_allocations')`
  - `fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', on_delete=CASCADE, related_name='inventory_allocations')`
  - `zone_bin`: `CharField(max_length=50, blank=True)`
  - `quantity_on_hand`: `IntegerField(default=0)`
  - `quantity_allocated`: `IntegerField(default=0)`
  - `safety_stock_buffer`: `PositiveIntegerField(default=0)`
  - `low_stock_threshold`: `PositiveIntegerField(default=5)`
  - `is_low_stock_alert`: `BooleanField(default=False)`
  - `restock_lead_time_days`: `PositiveSmallIntegerField(default=7)`
  - `last_counted_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_inv_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'variant', 'fulfillment_center'], name='ecom_inv_tnt_var_fc_uniq')`
  - `Index(fields=['tenant', 'is_low_stock_alert'], name='ecom_inv_tnt_low_alert_idx')`
  - `Index(fields=['tenant', 'fulfillment_center'], name='ecom_inv_tnt_fc_idx')`
  - `Index(fields=['tenant', 'product'], name='ecom_inv_tnt_prod_idx')`
- **Properties & Methods:**
  - `available_to_promise`: `max(0, self.quantity_on_hand - self.quantity_allocated - self.safety_stock_buffer)`
  - `is_out_of_stock`: `self.available_to_promise <= 0`
  - `clean()`: sets `is_low_stock_alert = (self.available_to_promise <= self.low_stock_threshold)`

### 1.3 `BackorderPolicy` (`apps/ecommerce/models/InventoryStock/BackorderPolicies.py`)
- **Table:** `ecommerce_backorder_policy`
- **Number Prefix:** `EBK` (`EBK-00001`)
- **CHOICES:**
  - `POLICY_TYPE_CHOICES = [('deny_when_empty', 'Deny When Out of Stock (Standard)'), ('allow_backorder_with_notice', 'Allow Backorders with Warning Notice'), ('pre_order_only', 'Pre-Order Mode (Advance Campaign)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_backorder_policies')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `variant`: `OneToOneField('ecommerce.ProductVariant', on_delete=CASCADE, related_name='backorder_policy')`
  - `policy_type`: `CharField(max_length=35, choices=POLICY_TYPE_CHOICES, default='deny_when_empty')`
  - `storefront_message`: `CharField(max_length=255, blank=True)`
  - `expected_availability_date`: `DateField(null=True, blank=True)`
  - `max_backorder_quantity`: `PositiveIntegerField(default=0)` (0 = unlimited)
  - `current_backorder_count`: `PositiveIntegerField(default=0)`
  - `auto_notify_waitlist`: `BooleanField(default=True)`
  - `is_active`: `BooleanField(default=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_bk_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'variant'], name='ecom_bk_tenant_var_uniq')`
  - `Index(fields=['tenant', 'policy_type'], name='ecom_bk_tnt_policy_idx')`
  - `Index(fields=['tenant', 'is_active'], name='ecom_bk_tnt_active_idx')`
- **Properties & Methods:**
  - `is_backorder_allowed`: `self.is_active and (self.max_backorder_quantity == 0 or self.current_backorder_count < self.max_backorder_quantity)`

### 1.4 `ChannelInventorySync` (`apps/ecommerce/models/InventoryStock/ChannelInventorySyncs.py`)
- **Table:** `ecommerce_channel_inventory_sync`
- **Number Prefix:** `ESYN` (`ESYN-00001`)
- **CHOICES:**
  - `CHANNEL_TYPE_CHOICES = [('web_storefront', 'Direct Web Storefront'), ('amazon_marketplace', 'Amazon Marketplace'), ('walmart_marketplace', 'Walmart Marketplace'), ('pos_retail', 'Retail POS Register'), ('wholesale_b2b', 'B2B Wholesale Portal')]`
  - `SYNC_MODE_CHOICES = [('real_time', 'Real-Time Event Sync'), ('scheduled_batch', 'Scheduled Batch'), ('manual', 'Manual Push Only')]`
  - `SYNC_STATUS_CHOICES = [('synced', 'In Sync'), ('pending', 'Sync Pending'), ('sync_error', 'Sync Error'), ('disabled', 'Disabled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_channel_inventory_syncs')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=CASCADE, related_name='channel_syncs')`
  - `channel_type`: `CharField(max_length=30, choices=CHANNEL_TYPE_CHOICES, default='web_storefront')`
  - `channel_name`: `CharField(max_length=100)`
  - `fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', on_delete=SET_NULL, null=True, blank=True, related_name='channel_syncs')`
  - `sync_mode`: `CharField(max_length=25, choices=SYNC_MODE_CHOICES, default='real_time')`
  - `allocation_buffer_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `last_synced_quantity`: `IntegerField(default=0)`
  - `sync_status`: `CharField(max_length=25, choices=SYNC_STATUS_CHOICES, default='synced')`
  - `last_synced_at`: `DateTimeField(null=True, blank=True)`
  - `error_message`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_sync_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'variant', 'channel_type', 'channel_name'], name='ecom_sync_tnt_var_chn_uniq')`
  - `Index(fields=['tenant', 'sync_status'], name='ecom_sync_tnt_stat_idx')`
  - `Index(fields=['tenant', 'channel_type'], name='ecom_sync_tnt_chntyp_idx')`

---

## 2. Forms Contract (`apps/ecommerce/forms/InventoryStock/`)

### 2.1 `FulfillmentCenterForm`
- **Model:** `FulfillmentCenter`
- **Fields:** `['name', 'code', 'center_type', 'location', 'priority', 'is_active', 'supports_pick_pack_ship', 'supports_customer_pickup', 'daily_cutoff_time', 'address_line1', 'city', 'state', 'postal_code', 'country', 'contact_email', 'contact_phone', 'notes']`
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`
- **Validation:** Unique `code` per tenant; `priority` >= 1; location must belong to same tenant (or null).

### 2.2 `InventoryAllocationForm`
- **Model:** `InventoryAllocation`
- **Fields:** `['product', 'variant', 'fulfillment_center', 'zone_bin', 'quantity_on_hand', 'quantity_allocated', 'safety_stock_buffer', 'low_stock_threshold', 'restock_lead_time_days', 'last_counted_at', 'notes']`
- **Excludes:** `tenant`, `number`, `is_low_stock_alert`, `created_at`, `updated_at`
- **Validation:** `variant.product == product`; unique `(tenant, variant, fulfillment_center)`.

### 2.3 `StockAdjustmentActionForm` (Operational adjustment action)
- **Non-Model Form:**
  - `adjustment_type`: `ChoiceField(choices=[('cycle_count', 'Cycle Count Audit'), ('damage_write_off', 'Damage / Shrinkage Write-Off'), ('receipt_reconcile', 'Receiving Inbound Reconciliation'), ('manual_correction', 'Manual Stock Correction')])`
  - `adjustment_quantity`: `IntegerField(help_text="Units to add (positive) or deduct (negative)")`
  - `reason_notes`: `CharField(widget=forms.Textarea, required=True)`

### 2.4 `BackorderPolicyForm`
- **Model:** `BackorderPolicy`
- **Fields:** `['variant', 'policy_type', 'storefront_message', 'expected_availability_date', 'max_backorder_quantity', 'auto_notify_waitlist', 'is_active', 'notes']`
- **Excludes:** `tenant`, `number`, `current_backorder_count`, `created_at`, `updated_at`
- **Validation:** unique `(tenant, variant)`.

### 2.5 `ChannelInventorySyncForm`
- **Model:** `ChannelInventorySync`
- **Fields:** `['variant', 'channel_type', 'channel_name', 'fulfillment_center', 'sync_mode', 'allocation_buffer_pct', 'sync_status', 'error_message']`
- **Excludes:** `tenant`, `number`, `last_synced_quantity`, `last_synced_at`, `created_at`, `updated_at`
- **Validation:** unique `(tenant, variant, channel_type, channel_name)`.

---

## 3. URLs Contract (`apps/ecommerce/urls/InventoryStock/`)

All registered with `app_name = "ecommerce"`:

| Pattern | View Name | Purpose |
|---|---|---|
| `inventory/` | `inventory_operations` | Central Inventory Operations Dashboard & ATP Matrix |
| `inventory/centers/` | `fulfillmentcenter_list` | Fulfillment centers list with search/filter |
| `inventory/centers/create/` | `fulfillmentcenter_create` | Create fulfillment center |
| `inventory/centers/<int:pk>/` | `fulfillmentcenter_detail` | Fulfillment center detail with assigned inventory & syncs |
| `inventory/centers/<int:pk>/edit/` | `fulfillmentcenter_edit` | Edit fulfillment center |
| `inventory/centers/<int:pk>/delete/` | `fulfillmentcenter_delete` | Delete fulfillment center (POST only, admin required) |
| `inventory/allocations/` | `inventoryallocation_list` | Inventory allocations list with search/center filter |
| `inventory/allocations/create/` | `inventoryallocation_create` | Create stock allocation |
| `inventory/allocations/<int:pk>/` | `inventoryallocation_detail` | Allocation detail + ATP breakdown + history |
| `inventory/allocations/<int:pk>/edit/` | `inventoryallocation_edit` | Edit allocation parameters |
| `inventory/allocations/<int:pk>/delete/` | `inventoryallocation_delete` | Delete allocation (POST only, admin required) |
| `inventory/allocations/<int:pk>/adjust/` | `inventoryallocation_adjust` | Quick stock adjustment (+/- count with audit logging) |
| `inventory/backorders/` | `backorderpolicy_list` | Backorder & pre-order policies list |
| `inventory/backorders/create/` | `backorderpolicy_create` | Create backorder policy |
| `inventory/backorders/<int:pk>/` | `backorderpolicy_detail` | Backorder policy detail with queue metrics |
| `inventory/backorders/<int:pk>/edit/` | `backorderpolicy_edit` | Edit backorder policy |
| `inventory/backorders/<int:pk>/delete/` | `backorderpolicy_delete` | Delete backorder policy (POST only, admin required) |
| `inventory/sync/` | `channelinventorysync_list` | Channel inventory sync list |
| `inventory/sync/create/` | `channelinventorysync_create` | Create channel sync mapping |
| `inventory/sync/<int:pk>/` | `channelinventorysync_detail` | Channel sync detail with error diagnostics |
| `inventory/sync/<int:pk>/edit/` | `channelinventorysync_edit` | Edit channel sync |
| `inventory/sync/<int:pk>/delete/` | `channelinventorysync_delete` | Delete channel sync (POST only, admin required) |
| `inventory/sync/<int:pk>/trigger/` | `channelinventorysync_trigger` | Trigger manual sync push (POST only) |

---

## 4. View Context Keys Contract (L7 / L8 PINNED)

Every view must provide the exact pinned dictionary keys below:

### 4.1 Operations Dashboard
- **`inventory_operations`**:
  - `kpis`: dict containing `total_on_hand`, `total_allocated`, `total_atp`, `low_stock_count`, `active_backorders`, `active_centers`
  - `centers`: QuerySet of `FulfillmentCenter`
  - `low_stock_allocations`: QuerySet of `InventoryAllocation` where `is_low_stock_alert=True`
  - `recent_syncs`: QuerySet of `ChannelInventorySync`
  - `recent_backorders`: QuerySet of `BackorderPolicy`

### 4.2 `FulfillmentCenter`
- **`fulfillmentcenter_list`**:
  - `centers`: Page object containing list of centers
  - `page_obj`: paginated slice
  - `paginator`: Paginator instance
  - `is_paginated`: bool
  - `search_query`: str (`request.GET.get('q', '')`)
  - `center_type_filter`: str
  - `is_active_filter`: str
  - `center_type_choices`: `FulfillmentCenter.CENTER_TYPE_CHOICES`
- **`fulfillmentcenter_detail`**:
  - `center`: `FulfillmentCenter` instance
  - `allocations`: QuerySet of assigned `InventoryAllocation`
  - `sync_channels`: QuerySet of assigned `ChannelInventorySync`
- **`fulfillmentcenter_create`**:
  - `form`: `FulfillmentCenterForm` instance
  - `is_create`: `True`
- **`fulfillmentcenter_edit`**:
  - `form`: `FulfillmentCenterForm` instance
  - `center`: `FulfillmentCenter` instance
  - `is_create`: `False`

### 4.3 `InventoryAllocation`
- **`inventoryallocation_list`**:
  - `allocations`: Page object containing list of allocations
  - `page_obj`: paginated slice
  - `paginator`: Paginator instance
  - `is_paginated`: bool
  - `search_query`: str
  - `center_filter`: str (pk string)
  - `low_stock_filter`: str ('1' or '')
  - `centers`: QuerySet of active `FulfillmentCenter`
- **`inventoryallocation_detail`**:
  - `allocation`: `InventoryAllocation` instance
  - `variant`: `ProductVariant` instance
  - `product`: `CatalogProduct` instance
  - `center`: `FulfillmentCenter` instance
  - `backorder_policy`: `BackorderPolicy` instance or `None`
  - `channel_syncs`: QuerySet of `ChannelInventorySync`
- **`inventoryallocation_create`**:
  - `form`: `InventoryAllocationForm` instance
  - `is_create`: `True`
- **`inventoryallocation_edit`**:
  - `form`: `InventoryAllocationForm` instance
  - `allocation`: `InventoryAllocation` instance
  - `is_create`: `False`
- **`inventoryallocation_adjust`**:
  - `form`: `StockAdjustmentActionForm` instance
  - `allocation`: `InventoryAllocation` instance

### 4.4 `BackorderPolicy`
- **`backorderpolicy_list`**:
  - `policies`: Page object containing list of policies
  - `page_obj`: paginated slice
  - `paginator`: Paginator instance
  - `is_paginated`: bool
  - `search_query`: str
  - `policy_type_filter`: str
  - `active_filter`: str
  - `policy_type_choices`: `BackorderPolicy.POLICY_TYPE_CHOICES`
- **`backorderpolicy_detail`**:
  - `policy`: `BackorderPolicy` instance
  - `variant`: `ProductVariant` instance
  - `product`: `CatalogProduct` instance
  - `allocations`: QuerySet of `InventoryAllocation`
- **`backorderpolicy_create`**:
  - `form`: `BackorderPolicyForm` instance
  - `is_create`: `True`
- **`backorderpolicy_edit`**:
  - `form`: `BackorderPolicyForm` instance
  - `policy`: `BackorderPolicy` instance
  - `is_create`: `False`

### 4.5 `ChannelInventorySync`
- **`channelinventorysync_list`**:
  - `syncs`: Page object containing list of syncs
  - `page_obj`: paginated slice
  - `paginator`: Paginator instance
  - `is_paginated`: bool
  - `search_query`: str
  - `channel_type_filter`: str
  - `sync_status_filter`: str
  - `channel_type_choices`: `ChannelInventorySync.CHANNEL_TYPE_CHOICES`
  - `sync_status_choices`: `ChannelInventorySync.SYNC_STATUS_CHOICES`
- **`channelinventorysync_detail`**:
  - `sync`: `ChannelInventorySync` instance
  - `variant`: `ProductVariant` instance
  - `center`: `FulfillmentCenter` instance or `None`
- **`channelinventorysync_create`**:
  - `form`: `ChannelInventorySyncForm` instance
  - `is_create`: `True`
- **`channelinventorysync_edit`**:
  - `form`: `ChannelInventorySyncForm` instance
  - `sync`: `ChannelInventorySync` instance
  - `is_create`: `False`

---

## 5. Theme & Badge Classes Contract (L33)

Only valid color-named classes from `static/css/theme.css`:
- `.badge-green` — Active, Synced, In Stock, Low Priority
- `.badge-amber` — Pending, Warning, Backordered, Approaching Threshold
- `.badge-red` — Out of Stock, Error, Critical Low Stock, Disabled
- `.badge-info` — Real-Time, Pre-Order, Web Storefront
- `.badge-slate` — Inactive, Draft, Manual
- `.badge-muted` — Secondary / Archived

Semantic `-success`, `-warning`, `-danger` do **NOT** exist in `theme.css`.

---

## 6. Sidebar Navigation Contract (`LIVE_LINKS["9.2"]`)

Exact mapping in `apps/core/navigation.py`:
```python
"9.2": {
    "Real-Time Stock Tracking": "ecommerce:inventoryallocation_list",
    "Warehouse & Fulfillment Center Management": "ecommerce:fulfillmentcenter_list",
    "Stock Transfers & Adjustments": "ecommerce:inventory_operations",
    "Backorder & Pre-Order Management": "ecommerce:backorderpolicy_list",
    "Multi-Channel Inventory Sync": "ecommerce:channelinventorysync_list",
    # Extra live leaves
    "Inventory Operations Console": "ecommerce:inventory_operations",
},
```
