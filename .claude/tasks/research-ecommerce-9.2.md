# Research — Sub-module 9.2: Inventory & Stock Management (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.2 Inventory & Stock Management
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1)
- **Research date:** 2026-10-29
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.2.md` only; no application code, migrations, settings, navigation, or git commits

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.2 is the **digital inventory allocation, multi-location fulfillment orchestration, safety stock buffering, backorder/pre-order management, and multi-channel synchronization engine** of the eCommerce Management System. 

In enterprise ERP and commerce architecture, there is a fundamental distinction between **Physical Warehouse Stock Keeping** and **Digital Storefront Available-to-Promise (ATP)**:
- **Physical Warehouse Management** (`apps/scm` and `apps/inventory`) manages physical bins, bulk pallet racks, warehouse cycle counts, physical put-away, lot/serial batches, and perpetual inventory accounting ledgers (`scm.StockMove`, `scm.StockTransfer`, `scm.StockAdjustment`).
- **eCommerce Inventory Management** (`apps/ecommerce` 9.2) manages customer-facing stock visibility across digital sales channels, virtual safety stock buffers that protect against overselling, fulfillment center routing priority, backorder/pre-order availability policies, and multi-channel synchronization feeds (Shopify, Amazon, Walmart, POS, Wholesale).

### The Decisive Ownership & Boundary Rulings (L28, L29, L36, L37):
1. **Physical Items & SKUs**: Reuses `scm.Item` (Core SCM physical master) and `ecommerce.ProductVariant` (Sub-module 9.1 purchasable SKU option). Sub-module 9.2 does NOT declare a third product or variant model.
2. **Physical Warehouses & Locations**: Reuses `scm.Location` (`apps/scm/models/InventoryManagement/Locations.py:14`, `LOC-`) as the optional physical warehouse backing entity. 9.2's `FulfillmentCenter` models the digital fulfillment node/partner (e.g. 3PL, local hub, retail store pickup node) with shipping priority, handling cutoff times, and zone routing.
3. **Physical Stock Moves, Transfers & Adjustments**: Sub-module 9.2 does NOT duplicate `StockMove`, `StockTransfer`, or `StockAdjustment` tables. Physical transfers and cycle count adjustments remain strictly owned by `apps/scm` (`scm.StockTransfer` [`TRF-`] and `scm.StockAdjustment` [`ADJ-`]). eCommerce 9.2 provides an operational dispatch console and stock adjustment bridge that records store allocation impacts while respecting physical SCM ledgers.
4. **Calculated Available-to-Promise (ATP)**: Digital stock is calculated as:
   $$\text{ATP} = \max(0, \text{On-Hand} - \text{Allocated (Reserved)} - \text{Safety Stock Buffer})$$
   Storefronts show ATP, not raw warehouse physical count, preventing race-condition overselling.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:** Checked `LIVE_LINKS`. `"9.1"` is live with 5 bullets and Catalog Overview. Sub-module 9.2 has no entry yet.
- **`apps/ecommerce/`:** Exists with `models/ProductCatalog/`, `forms/ProductCatalog/`, `views/ProductCatalog/`, `urls/ProductCatalog/`, `templates/ecommerce/productcatalog/`, `seed_ecommerce.py`, and migration `0001_initial.py`.
- **Active App Package Structure:** Sub-module 9.2 will add `models/InventoryStock/`, `forms/InventoryStock/`, `views/InventoryStock/`, `urls/InventoryStock/`, and `templates/ecommerce/inventorystock/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.2 Role |
|---|---|---|---|
| `scm.Item` | `apps/scm/models/InventoryManagement/Items.py:73` | **Present** | Canonical physical stock-keeping SKU |
| `scm.Location` | `apps/scm/models/InventoryManagement/Locations.py:14` | **Present** | Physical warehouse / location node |
| `scm.StockTransfer` | `apps/scm/models/InventoryManagement/StockTransfers.py:11` | **Present** | Physical inter-warehouse transfer header (`TRF-`) |
| `scm.StockAdjustment` | `apps/scm/models/InventoryManagement/StockAdjustments.py:11` | **Present** | Physical inventory adjustment / write-off (`ADJ-`) |
| `scm.StockMove` | `apps/scm/models/InventoryManagement/StockMoves.py:13` | **Present** | Immutable physical inventory transaction ledger |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:18` | **Present** | Merchandised product header (`EPRD-`) |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:18` | **Present** | Purchasable SKU option (`PVR-`) |
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Multi-tenant isolation boundary |
| `accounts.User` | `settings.AUTH_USER_MODEL` | **Present** | Attribution, user audit, manager assignments |

### 2.3 Prefix Collision Verification
Queried all existing `NUMBER_PREFIX` across `apps/**/*.py`.
- Checked `EFC` (FulfillmentCenter): **0 hits across repository — 100% free**
- Checked `EAL` (InventoryAllocation): **0 hits across repository — 100% free**
- Checked `EBK` (BackorderPolicy): **0 hits across repository — 100% free**
- Checked `ESYN` (ChannelInventorySync): **0 hits across repository — 100% free**

---

## 3. Commercial Product Analysis (10 Market Leaders)

1. **Shopify Plus**:
   - *Multi-Location Inventory*: Assigns inventory levels per location with fulfillment service tagging.
   - *Inventory Levels*: Tracks on-hand, committed (allocated to unfulfilled orders), and available.
   - *Backorder & Pre-order*: "Continue selling when out of stock" toggle; apps like Timesact capture pre-orders with expected ship dates.
2. **BigCommerce**:
   - *Inventory Settings*: Global and per-product out-of-stock behaviors (hide product, display out-of-stock message, allow purchase).
   - *Pre-Order Mode*: Product status "Pre-order" with custom message and auto-release on scheduled date.
   - *Multi-Location*: Multiple fulfillment locations with stock levels synced to ERP.
3. **Adobe Commerce (Magento MSI - Multi-Source Inventory)**:
   - *Sources & Stocks*: Sources are physical locations; Stocks are virtual groupings assigned to sales channels.
   - *Safety Stock*: Configurable minimum quantity threshold per source/stock that buffers inventory.
   - *Source Selection Algorithm (SSA)*: Priority and distance-based fulfillment routing.
4. **Oracle NetSuite**:
   - *Available-to-Promise (ATP)*: Real-time calculation deducting reservations and safety buffers from physical counts.
   - *Multi-Location Demand Planning*: Location-specific reorder points and automated replenishment warnings.
   - *Connector Hub*: Celigo/FarApp connectors push ATP down to external digital channels.
5. **Cin7 (Core & Omni)**:
   - *Channel Allocation Rules*: Dedicates stock percentages or minimum units to specific sales channels (e.g. 60% Web, 30% Amazon, 10% B2B).
   - *Low Stock Alerts*: Threshold notifications trigger automated purchasing or merchant alerts.
   - *Virtual Safety Buffers*: Prevents stockouts caused by marketplace sync latency.
6. **Brightpearl (by Sage)**:
   - *Automated Stock Allocation*: Reserves inventory the second an online order is placed across any channel.
   - *Backorder Fulfillment Queue*: Automatically matches inbound receipts to open customer backorders.
   - *Warehouse Routing*: Determines whether an order is routed to primary warehouse, drop-shipper, or regional 3PL.
7. **Extensiv (formerly Skubana)**:
   - *Channel Stock Buffers*: Sets absolute or percentage buffer deductions before broadcasting available stock to Amazon/eBay/Shopify.
   - *Multi-Warehouse Routing*: Intelligently splits or consolidates orders based on location stock availability.
   - *Stock Sync Engine*: Scheduled or webhook-driven synchronization preventing overselling.
8. **Katana Cloud Manufacturing**:
   - *Live Inventory Tracking*: Distinguishes Expected, In-Stock, Committed, and Missing inventory.
   - *Backorder Linkage*: Connects customer backorders directly to replenishment purchase orders.
9. **Linnworks**:
   - *Unified Channel Stock Pool*: Maintains central inventory with instant decrement across all connected sales platforms.
   - *Maximum Display Stock*: Caps advertised stock to create scarcity or avoid platform penalty limits.
10. **ShipBob**:
    - *Distributed Fulfillment Network*: Manages multi-location inventory across 3PL fulfillment centers with zone/bin mapping.
    - *On-Hand vs. Reservable*: Real-time stock status with automatic low-stock reorder triggers.

---

## 4. Deduplicated Feature Catalog (Mapped to 9.2 Bullets)

### Bullet 1: Real-Time Stock Tracking
- **Multi-Location Stock Visibility**: Real-time matrix of stock across physical and 3PL fulfillment centers.
- **Safety Stock Thresholds**: Configurable reserve quantity withheld from storefront availability to absorb demand spikes.
- **Low-Stock Alerting**: Automatic warning flags when available inventory falls below critical threshold.
- **Available-to-Promise (ATP) Calculation**: Automatic computation of `(on_hand - allocated - safety_stock)`.
- *Priority*: `table-stakes`. *Model*: `InventoryAllocation`.

### Bullet 2: Warehouse & Fulfillment Center Management
- **Fulfillment Node Configuration**: Identification of internal warehouses, 3PL partners (ShipBob, Amazon FBA), and retail ship-from-store hubs.
- **Zone & Bin Mapping**: Tracking primary pick zones, aisles, and storage bins for fulfillment efficiency.
- **Fulfillment Priority & Routing**: Priority ranking (1, 2, 3...) for automated order routing and nearest-center shipping.
- **Operating Hours & Daily Cutoff**: Daily order cutoff times for same-day dispatch processing.
- *Priority*: `table-stakes`. *Model*: `FulfillmentCenter`.

### Bullet 3: Stock Transfers & Adjustments
- **Inter-Warehouse Transfer Bridge**: Operational console to initiate or monitor stock redistribution between fulfillment centers, linking to `scm.StockTransfer`.
- **Damage & Shrinkage Write-Offs**: Immediate allocation adjustments for damaged, expired, or stolen items, linking to `scm.StockAdjustment`.
- **Cycle Count Reconciliation**: Reconciling digital storefront counts with physical floor audits.
- *Priority*: `common`. *Implementation*: Operational View Console + Action Workflows (reusing `scm.StockTransfer` and `scm.StockAdjustment`).

### Bullet 4: Backorder & Pre-Order Management
- **Customer Availability Policy**: Policy choice per SKU (`deny`, `allow_with_notice`, `pre_order_only`).
- **Storefront Availability Messaging**: Custom customer-facing message (e.g. "Ships by Nov 15th", "Backordered — 2 weeks delivery").
- **Waitlist & Pre-Order Capture**: Tracking current waitlist commitments, pre-order limits, and customer demand queues.
- **Release-Date Fulfillment Scheduling**: Target availability and release dates for upcoming product launches.
- *Priority*: `differentiator`. *Model*: `BackorderPolicy`.

### Bullet 5: Multi-Channel Inventory Sync
- **Multi-Channel Stock Feed**: Stock level synchronization profiles across digital channels (Web Storefront, Amazon, Walmart, POS Retail, Wholesale B2B).
- **Channel Buffer & Allocation Rules**: Channel-specific safety buffer quantity or percentage share.
- **Sync Status & Error Diagnostics**: Tracking sync timestamps, last synced quantity, connection status (`synced`, `pending`, `failed`), and error payloads.
- *Priority*: `differentiator`. *Model*: `ChannelInventorySync`.

---

## 5. Recommended Build Scope (Exactly 4 Models)

To deliver enterprise-grade inventory and fulfillment management while maintaining clean modular separation and zero duplication of the physical SCM ledger, Sub-module 9.2 introduces **exactly 4 tenant-scoped models**:

```
apps/ecommerce/models/InventoryStock/
├── __init__.py
├── FulfillmentCenters.py        # FulfillmentCenter (EFC-)
├── InventoryAllocations.py      # InventoryAllocation (EAL-)
├── BackorderPolicies.py         # BackorderPolicy (EBK-)
└── ChannelInventorySyncs.py     # ChannelInventorySync (ESYN-)
```

### Model 1: `FulfillmentCenter` (`FulfillmentCenters.py`) — Prefix `EFC`
- **Purpose**: Represents an eCommerce fulfillment node (internal warehouse, 3PL partner, or retail hub).
- **Key Fields**:
  - `name`: CharField(100) — e.g. "Primary West Coast DC", "ShipBob Chicago 3PL", "Downtown Retail Hub"
  - `code`: CharField(30, unique per tenant) — e.g. "WH-WEST", "3PL-CHI"
  - `center_type`: CharField(choices: `internal_warehouse`, `third_party_3pl`, `retail_store`, `dropshipper`)
  - `location`: ForeignKey("scm.Location", null=True, blank=True, on_delete=models.SET_NULL)
  - `priority`: PositiveSmallIntegerField(default=1) — Lower number = higher fulfillment priority
  - `is_active`: BooleanField(default=True)
  - `supports_pick_pack_ship`: BooleanField(default=True)
  - `supports_customer_pickup`: BooleanField(default=False)
  - `daily_cutoff_time`: TimeField(null=True, blank=True) — Same-day shipping cutoff
  - `address_line1`, `city`, `state`, `postal_code`, `country`: Address fields
  - `contact_email`, `contact_phone`: Notification contacts

### Model 2: `InventoryAllocation` (`InventoryAllocations.py`) — Prefix `EAL`
- **Purpose**: Real-time stock level and digital reservation tracking per product variant and fulfillment center.
- **Key Fields**:
  - `variant`: ForeignKey("ecommerce.ProductVariant", on_delete=models.CASCADE, related_name="inventory_allocations")
  - `product`: ForeignKey("ecommerce.CatalogProduct", on_delete=models.CASCADE, related_name="inventory_allocations")
  - `fulfillment_center`: ForeignKey("ecommerce.FulfillmentCenter", on_delete=models.CASCADE, related_name="inventory_allocations")
  - `zone_bin`: CharField(max_length=50, blank=True) — Bin/shelf location (e.g. "Aisle 4, Bin B-12")
  - `quantity_on_hand`: IntegerField(default=0) — Physical units stored
  - `quantity_allocated`: IntegerField(default=0) — Units reserved for pending orders
  - `safety_stock_buffer`: PositiveIntegerField(default=0) — Units withheld from online channels
  - `low_stock_threshold`: PositiveIntegerField(default=5) — Threshold triggering alert
  - `is_low_stock_alert`: BooleanField(default=False) — Automated alert flag
  - `restock_lead_time_days`: PositiveSmallIntegerField(default=7) — Lead time for replenishment
  - `last_counted_at`: DateTimeField(null=True, blank=True) — Last physical audit
- **Computed Property**:
  - `available_to_promise`: `max(0, quantity_on_hand - quantity_allocated - safety_stock_buffer)`

### Model 3: `BackorderPolicy` (`BackorderPolicies.py`) — Prefix `EBK`
- **Purpose**: Controls customer-facing availability messaging, pre-order campaigns, and waitlist limits.
- **Key Fields**:
  - `variant`: OneToOneField("ecommerce.ProductVariant", on_delete=models.CASCADE, related_name="backorder_policy")
  - `policy_type`: CharField(choices: `deny_when_empty`, `allow_backorder_with_notice`, `pre_order_only`)
  - `storefront_message`: CharField(max_length=255, blank=True) — e.g. "Available for Pre-Order. Ships Dec 1st."
  - `expected_availability_date`: DateField(null=True, blank=True)
  - `max_backorder_quantity`: PositiveIntegerField(default=0) — 0 = unlimited backorders
  - `current_backorder_count`: PositiveIntegerField(default=0) — Committed pre-orders/backorders
  - `auto_notify_waitlist`: BooleanField(default=True) — Send restock alerts to waitlist
  - `is_active`: BooleanField(default=True)

### Model 4: `ChannelInventorySync` (`ChannelInventorySyncs.py`) — Prefix `ESYN`
- **Purpose**: Multi-channel inventory synchronization configuration and health monitoring across sales channels.
- **Key Fields**:
  - `variant`: ForeignKey("ecommerce.ProductVariant", on_delete=models.CASCADE, related_name="channel_syncs")
  - `channel_type`: CharField(choices: `web_storefront`, `amazon_marketplace`, `walmart_marketplace`, `pos_retail`, `wholesale_b2b`)
  - `channel_name`: CharField(max_length=100) — e.g. "US Amazon Store", "Downtown POS Register"
  - `sync_mode`: CharField(choices: `real_time`, `scheduled_batch`, `manual`)
  - `allocation_buffer_pct`: DecimalField(max_digits=5, decimal_places=2, default=0.0) — e.g. withhold 5% on marketplaces
  - `last_synced_quantity`: IntegerField(default=0)
  - `sync_status`: CharField(choices: `synced`, `pending`, `sync_error`, `disabled`, default="synced")
  - `last_synced_at`: DateTimeField(null=True, blank=True)
  - `error_message`: TextField(blank=True)

---

## 6. Console & Operations Projections (Transfers & Adjustments)

Bullet 3 (**Stock Transfers & Adjustments**) is implemented as:
1. **Inventory Operations Console (`inventory_operations`)**: A centralized dashboard view displaying:
   - Live stock health (Total on hand, Allocated, Available to Promise across all fulfillment centers).
   - Low-stock alerts and items requiring immediate replenishment.
   - Quick links and dispatch shortcuts to `scm.StockTransfer` and `scm.StockAdjustment`.
2. **Allocation Quick-Adjust Action (`allocation_adjust`)**: An in-line action allowing warehouse managers to record cycle count adjustments or damage write-offs directly against an `InventoryAllocation`, creating an `AuditLog` row and updating on-hand quantities.

---

## 7. URL, View, & Template Topology

All URLs live under namespace `ecommerce` and URL prefix `/ecommerce/inventory/`:

```
/ecommerce/inventory/
├── overview/                      -> inventory_overview (Operational Console & ATP matrix)
├── centers/                       -> fulfillmentcenter_list
├── centers/create/                -> fulfillmentcenter_create
├── centers/<int:pk>/              -> fulfillmentcenter_detail
├── centers/<int:pk>/edit/         -> fulfillmentcenter_edit
├── centers/<int:pk>/delete/       -> fulfillmentcenter_delete
├── allocations/                   -> inventoryallocation_list
├── allocations/create/            -> inventoryallocation_create
├── allocations/<int:pk>/          -> inventoryallocation_detail
├── allocations/<int:pk>/edit/     -> inventoryallocation_edit
├── allocations/<int:pk>/delete/   -> inventoryallocation_delete
├── allocations/<int:pk>/adjust/   -> inventoryallocation_adjust
├── backorders/                    -> backorderpolicy_list
├── backorders/create/             -> backorderpolicy_create
├── backorders/<int:pk>/           -> backorderpolicy_detail
├── backorders/<int:pk>/edit/      -> backorderpolicy_edit
├── backorders/<int:pk>/delete/    -> backorderpolicy_delete
├── sync/                          -> channelinventorysync_list
├── sync/create/                   -> channelinventorysync_create
├── sync/<int:pk>/                 -> channelinventorysync_detail
├── sync/<int:pk>/edit/            -> channelinventorysync_edit
├── sync/<int:pk>/delete/          -> channelinventorysync_delete
└── sync/<int:pk>/trigger/         -> channelinventorysync_trigger
```

---

## 8. Deferred Scope & Gap Register

- **Live External Marketplace Webhook Listeners** (Amazon SP-API, Shopify Webhooks): External HTTP daemon listeners and OAuth credentials belong in 9.19 (Integration & API Ecosystem).
- **Automated Carrier Fleet Dispatch Routing**: In-depth telematics and multi-drop delivery routing belong in `scm.TransportationManagement`.
- **Automated RFID Robot Scanning**: RFID tag readers belong in `apps/inventory/models/BarcodeRfidIntegration/`.

---

## 9. Conclusion & Hand-off to `todo` Agent

Sub-module 9.2 is cleanly scoped to 4 models, full CRUD, operational ATP calculation, and rich multi-location management without duplicating physical SCM inventory tables. Handing off to Phase 2 `todo` agent.
