# Contract — Sub-module 9.5: Order Management System (OMS) (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.5 Order Management System (OMS) · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-29 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0005_...`

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).
Child model `EcommerceOrderLine` inherits from `apps.ecommerce.models._base.TenantOwned` (`tenant`, `created_at`, `updated_at`).

### 1.1 `EcommerceOrder` & `EcommerceOrderLine` (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py`)
- **Table:** `ecommerce_order` & `ecommerce_order_line`
- **Number Prefix:** `EORD` (`EORD-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft'), ('pending_validation', 'Pending Validation'), ('validated', 'Validated & Approved'), ('processing', 'Processing / In Fulfillment'), ('partially_fulfilled', 'Partially Fulfilled'), ('fulfilled', 'Fulfilled'), ('cancelled', 'Cancelled'), ('closed', 'Closed')]`
  - `PAYMENT_STATUS_CHOICES = [('pending', 'Pending Payment'), ('authorized', 'Payment Authorized'), ('captured', 'Payment Captured'), ('partially_refunded', 'Partially Refunded'), ('refunded', 'Fully Refunded'), ('failed', 'Payment Failed')]`
  - `FULFILLMENT_STATUS_CHOICES = [('unfulfilled', 'Unfulfilled'), ('partially_fulfilled', 'Partially Fulfilled'), ('fulfilled', 'Fulfilled'), ('returned', 'Returned')]`
  - `FRAUD_RISK_CHOICES = [('low', 'Low Risk'), ('medium', 'Medium Risk'), ('high', 'High Risk'), ('flagged', 'Fraud Flagged')]`
  - `AVS_STATUS_CHOICES = [('unverified', 'Unverified'), ('passed', 'Address Verified (Passed)'), ('failed', 'Verification Failed'), ('corrected', 'Address Corrected')]`
  - `RESERVATION_STATUS_CHOICES = [('none', 'No Reservation'), ('reserved', 'Stock Reserved'), ('allocated', 'Stock Allocated to Node'), ('released', 'Reservation Released')]`
  - `LINE_STATUS_CHOICES = [('pending', 'Pending'), ('reserved', 'Stock Reserved'), ('routing', 'Routing to Fulfillment'), ('fulfilled', 'Fulfilled'), ('cancelled', 'Cancelled'), ('returned', 'Returned')]`
- **Fields (`EcommerceOrder`):**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='ecommerce_orders')`
  - `guest_email`: `EmailField(blank=True)`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=PROTECT, related_name='ecommerce_orders')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='pending_validation')`
  - `payment_status`: `CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='pending')`
  - `fulfillment_status`: `CharField(max_length=25, choices=FULFILLMENT_STATUS_CHOICES, default='unfulfilled')`
  - `fraud_risk_level`: `CharField(max_length=15, choices=FRAUD_RISK_CHOICES, default='low')`
  - `fraud_score`: `PositiveSmallIntegerField(default=10, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `address_verification_status`: `CharField(max_length=20, choices=AVS_STATUS_CHOICES, default='unverified')`
  - `inventory_reservation_status`: `CharField(max_length=20, choices=RESERVATION_STATUS_CHOICES, default='none')`
  - `subtotal_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `discount_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `shipping_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `tax_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `total_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `applied_coupon`: `ForeignKey('ecommerce.CouponPromotion', null=True, blank=True, on_delete=SET_NULL, related_name='orders')`
  - `shipping_address`: `ForeignKey('core.Address', null=True, blank=True, on_delete=SET_NULL, related_name='shipping_orders')`
  - `shipping_name`: `CharField(max_length=150)`
  - `shipping_address_line1`: `CharField(max_length=255)`
  - `shipping_city`: `CharField(max_length=100)`
  - `shipping_state`: `CharField(max_length=100, blank=True)`
  - `shipping_postal_code`: `CharField(max_length=30)`
  - `shipping_country`: `CharField(max_length=100)`
  - `billing_address`: `ForeignKey('core.Address', null=True, blank=True, on_delete=SET_NULL, related_name='billing_orders')`
  - `billing_name`: `CharField(max_length=150, blank=True)`
  - `billing_address_line1`: `CharField(max_length=255, blank=True)`
  - `billing_city`: `CharField(max_length=100, blank=True)`
  - `billing_state`: `CharField(max_length=100, blank=True)`
  - `billing_postal_code`: `CharField(max_length=30, blank=True)`
  - `billing_country`: `CharField(max_length=100, blank=True)`
  - `cancellation_reason`: `TextField(blank=True)`
  - `cancelled_at`: `DateTimeField(null=True, blank=True)`
  - `customer_notes`: `TextField(blank=True)`
  - `internal_notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Fields (`EcommerceOrderLine`):**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=CASCADE, related_name='lines')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=PROTECT, related_name='order_lines')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', null=True, blank=True, on_delete=SET_NULL, related_name='order_lines')`
  - `sku`: `CharField(max_length=80)`
  - `product_name`: `CharField(max_length=200)`
  - `quantity`: `PositiveIntegerField(default=1)`
  - `fulfilled_quantity`: `PositiveIntegerField(default=0)`
  - `returned_quantity`: `PositiveIntegerField(default=0)`
  - `unit_price`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `unit_discount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `line_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `status`: `CharField(max_length=20, choices=LINE_STATUS_CHOICES, default='pending')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_ord_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='ecom_ord_tnt_status_idx')`
  - `Index(fields=['tenant', 'customer'], name='ecom_ord_tnt_customer_idx')`
  - `Index(fields=['tenant', 'created_at'], name='ecom_ord_tnt_created_idx')`
  - `Index(fields=['tenant', 'order'], name='ecom_oln_tnt_order_idx')`

### 1.2 `OrderRoutingRule` (`apps/ecommerce/models/OrderManagement/OrderRoutingRules.py`)
- **Table:** `ecommerce_order_routing_rule`
- **Number Prefix:** `EORT` (`EORT-00001`)
- **CHOICES:**
  - `ROUTING_STRATEGY_CHOICES = [('closest_location', 'Closest Fulfillment Center'), ('fewest_splits', 'Fewest Split Shipments'), ('highest_inventory', 'Highest Stock Level'), ('drop_ship_preferred', 'Drop-Ship Preferred'), ('manual', 'Manual Assignment')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `strategy`: `CharField(max_length=30, choices=ROUTING_STRATEGY_CHOICES, default='closest_location')`
  - `priority`: `PositiveIntegerField(default=10)`
  - `destination_country`: `CharField(max_length=100, blank=True)`
  - `destination_region`: `CharField(max_length=100, blank=True)`
  - `preferred_fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=SET_NULL, related_name='routing_rules')`
  - `allow_split_shipment`: `BooleanField(default=True)`
  - `enable_dropship`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_ort_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'priority'], name='ecom_ort_tnt_act_prio_idx')`

### 1.3 `OrderFulfillment` (`apps/ecommerce/models/OrderManagement/OrderFulfillments.py`)
- **Table:** `ecommerce_order_fulfillment`
- **Number Prefix:** `EFUL` (`EFUL-00001`)
- **CHOICES:**
  - `PACKAGE_STATUS_CHOICES = [('draft', 'Draft / Sourced'), ('allocated', 'Stock Allocated'), ('picking', 'Picking Items'), ('packing', 'Packing Package'), ('shipped', 'Shipped with Carrier'), ('in_transit', 'In Transit'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered to Customer'), ('failed_delivery', 'Delivery Attempt Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=CASCADE, related_name='fulfillments')`
  - `fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=SET_NULL, related_name='fulfillments')`
  - `carrier_name`: `CharField(max_length=80)`
  - `tracking_number`: `CharField(max_length=100, blank=True)`
  - `tracking_url`: `URLField(blank=True)`
  - `status`: `CharField(max_length=25, choices=PACKAGE_STATUS_CHOICES, default='allocated')`
  - `shipping_cost`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `shipped_at`: `DateTimeField(null=True, blank=True)`
  - `estimated_delivery_date`: `DateField(null=True, blank=True)`
  - `actual_delivery_date`: `DateField(null=True, blank=True)`
  - `shipping_label_url`: `URLField(blank=True)`
  - `notification_sent`: `BooleanField(default=False)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_ful_tenant_num_uniq')`
  - `Index(fields=['tenant', 'order'], name='ecom_ful_tnt_order_idx')`
  - `Index(fields=['tenant', 'status'], name='ecom_ful_tnt_status_idx')`

### 1.4 `ReturnMerchandiseAuthorization` (`apps/ecommerce/models/OrderManagement/ReturnMerchandiseAuthorizations.py`)
- **Table:** `ecommerce_return_merchandise_auth`
- **Number Prefix:** `ERMA` (`ERMA-00001`)
- **CHOICES:**
  - `RETURN_TYPE_CHOICES = [('refund', 'Refund to Original Payment'), ('exchange', 'Exchange for Alternate Variant'), ('store_credit', 'Store Credit / Voucher')]`
  - `RMA_STATUS_CHOICES = [('requested', 'Return Requested'), ('authorized', 'Authorized & Label Issued'), ('label_generated', 'Return Label Generated'), ('in_transit', 'In Transit back to Center'), ('received', 'Received at Center'), ('inspected', 'Inspected & Evaluated'), ('approved', 'Approved for Settlement'), ('rejected', 'Rejected / Denied'), ('completed', 'Completed & Settled')]`
  - `RETURN_REASON_CHOICES = [('damaged_defective', 'Damaged or Defective'), ('wrong_item_sent', 'Wrong Item Sent'), ('size_fit_issue', 'Size or Fit Issue'), ('not_as_described', 'Item Not as Described'), ('changed_mind', 'Customer Changed Mind'), ('late_delivery', 'Late Delivery Arrival'), ('other', 'Other Reason')]`
  - `REFUND_STATUS_CHOICES = [('pending', 'Pending Approval'), ('processed', 'Refund Processed'), ('failed', 'Refund Failed'), ('waived', 'Fee Waived / No Refund')]`
  - `RESTOCK_STATUS_CHOICES = [('pending', 'Pending Restock Inspection'), ('restocked', 'Restocked to Active Inventory'), ('scrapped', 'Damaged / Scrapped'), ('quarantined', 'Quarantined for Review')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=CASCADE, related_name='returns')`
  - `customer`: `ForeignKey('core.Party', on_delete=CASCADE, related_name='ecommerce_returns')`
  - `return_type`: `CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default='refund')`
  - `status`: `CharField(max_length=25, choices=RMA_STATUS_CHOICES, default='requested')`
  - `reason`: `CharField(max_length=30, choices=RETURN_REASON_CHOICES, default='changed_mind')`
  - `return_shipping_label_url`: `URLField(blank=True)`
  - `return_tracking_number`: `CharField(max_length=100, blank=True)`
  - `restocking_fee`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `refund_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `refund_status`: `CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')`
  - `restocking_status`: `CharField(max_length=20, choices=RESTOCK_STATUS_CHOICES, default='pending')`
  - `restocking_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=SET_NULL, related_name='rma_restocks')`
  - `customer_notes`: `TextField(blank=True)`
  - `inspection_notes`: `TextField(blank=True)`
  - `authorized_at`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_rma_tenant_num_uniq')`
  - `Index(fields=['tenant', 'order'], name='ecom_rma_tnt_order_idx')`
  - `Index(fields=['tenant', 'status'], name='ecom_rma_tnt_status_idx')`

---

## 2. Forms Contract & Form Exclusions

Every form inherits standard `forms.ModelForm` with Tailwind-styled widgets.

### 2.1 `EcommerceOrderForm` & `EcommerceOrderLineForm` (`apps/ecommerce/forms/OrderManagement/EcommerceOrders.py`)
- **Model:** `EcommerceOrder`
- **Fields:** `['customer', 'guest_email', 'currency', 'status', 'payment_status', 'fulfillment_status', 'fraud_risk_level', 'fraud_score', 'address_verification_status', 'inventory_reservation_status', 'discount_amount', 'shipping_amount', 'tax_amount', 'applied_coupon', 'shipping_name', 'shipping_address_line1', 'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country', 'billing_name', 'billing_address_line1', 'billing_city', 'billing_state', 'billing_postal_code', 'billing_country', 'customer_notes', 'internal_notes']`
- **Excludes:** `['tenant', 'number', 'subtotal_amount', 'total_amount', 'cancellation_reason', 'cancelled_at', 'created_at', 'updated_at']`
- **Child Form:** `EcommerceOrderLineForm`
  - **Model:** `EcommerceOrderLine`
  - **Fields:** `['product', 'variant', 'sku', 'product_name', 'quantity', 'unit_price', 'unit_discount', 'status']`
  - **Excludes:** `['tenant', 'order', 'fulfilled_quantity', 'returned_quantity', 'line_total', 'created_at', 'updated_at']`

### 2.2 `OrderRoutingRuleForm` (`apps/ecommerce/forms/OrderManagement/OrderRoutingRules.py`)
- **Model:** `OrderRoutingRule`
- **Fields:** `['name', 'strategy', 'priority', 'destination_country', 'destination_region', 'preferred_fulfillment_center', 'allow_split_shipment', 'enable_dropship', 'is_active', 'description']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`

### 2.3 `OrderFulfillmentForm` (`apps/ecommerce/forms/OrderManagement/OrderFulfillments.py`)
- **Model:** `OrderFulfillment`
- **Fields:** `['order', 'fulfillment_center', 'carrier_name', 'tracking_number', 'tracking_url', 'status', 'shipping_cost', 'estimated_delivery_date', 'shipping_label_url', 'notification_sent', 'notes']`
- **Excludes:** `['tenant', 'number', 'shipped_at', 'actual_delivery_date', 'created_at', 'updated_at']`

### 2.4 `ReturnMerchandiseAuthorizationForm` (`apps/ecommerce/forms/OrderManagement/ReturnMerchandiseAuthorizations.py`)
- **Model:** `ReturnMerchandiseAuthorization`
- **Fields:** `['order', 'customer', 'return_type', 'status', 'reason', 'return_shipping_label_url', 'return_tracking_number', 'restocking_fee', 'refund_amount', 'refund_status', 'restocking_status', 'restocking_center', 'customer_notes', 'inspection_notes']`
- **Excludes:** `['tenant', 'number', 'authorized_at', 'completed_at', 'created_at', 'updated_at']`

---

## 3. URLs Contract (Route Names & Paths)

Namespace: `ecommerce:` (set in `apps/ecommerce/urls/__init__.py`)

| URL Name | Pattern | View Function |
|---|---|---|
| `ecommerceorder_list` | `orders/` | `ecommerceorder_list` |
| `ecommerceorder_create` | `orders/create/` | `ecommerceorder_create` |
| `ecommerceorder_detail` | `orders/<int:pk>/` | `ecommerceorder_detail` |
| `ecommerceorder_edit` | `orders/<int:pk>/edit/` | `ecommerceorder_edit` |
| `ecommerceorder_delete` | `orders/<int:pk>/delete/` | `ecommerceorder_delete` |
| `ecommerceorder_cancel` | `orders/<int:pk>/cancel/` | `ecommerceorder_cancel` |
| `orderroutingrule_list` | `routing-rules/` | `orderroutingrule_list` |
| `orderroutingrule_create` | `routing-rules/create/` | `orderroutingrule_create` |
| `orderroutingrule_detail` | `routing-rules/<int:pk>/` | `orderroutingrule_detail` |
| `orderroutingrule_edit` | `routing-rules/<int:pk>/edit/` | `orderroutingrule_edit` |
| `orderroutingrule_delete` | `routing-rules/<int:pk>/delete/` | `orderroutingrule_delete` |
| `orderfulfillment_list` | `fulfillments/` | `orderfulfillment_list` |
| `orderfulfillment_create` | `fulfillments/create/` | `orderfulfillment_create` |
| `orderfulfillment_detail` | `fulfillments/<int:pk>/` | `orderfulfillment_detail` |
| `orderfulfillment_edit` | `fulfillments/<int:pk>/edit/` | `orderfulfillment_edit` |
| `orderfulfillment_delete` | `fulfillments/<int:pk>/delete/` | `orderfulfillment_delete` |
| `orderfulfillment_ship` | `fulfillments/<int:pk>/ship/` | `orderfulfillment_ship` |
| `returnmerchandiseauthorization_list` | `returns/` | `returnmerchandiseauthorization_list` |
| `returnmerchandiseauthorization_create` | `returns/create/` | `returnmerchandiseauthorization_create` |
| `returnmerchandiseauthorization_detail` | `returns/<int:pk>/` | `returnmerchandiseauthorization_detail` |
| `returnmerchandiseauthorization_edit` | `returns/<int:pk>/edit/` | `returnmerchandiseauthorization_edit` |
| `returnmerchandiseauthorization_delete` | `returns/<int:pk>/delete/` | `returnmerchandiseauthorization_delete` |
| `returnmerchandiseauthorization_complete` | `returns/<int:pk>/complete/` | `returnmerchandiseauthorization_complete` |

---

## 4. View Context Contract

Pinning every context key across all 9.5 views:

### 4.1 EcommerceOrder Views
- `ecommerceorder_list`:
  - `page_obj`: paginated `EcommerceOrder` queryset
  - `orders`: `page_obj.object_list`
  - `status_choices`: `EcommerceOrder.STATUS_CHOICES`
  - `payment_status_choices`: `EcommerceOrder.PAYMENT_STATUS_CHOICES`
  - `fulfillment_status_choices`: `EcommerceOrder.FULFILLMENT_STATUS_CHOICES`
  - `fraud_risk_choices`: `EcommerceOrder.FRAUD_RISK_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_status`: `request.GET.get('status', '')`
  - `current_payment`: `request.GET.get('payment_status', '')`
  - `current_fulfillment`: `request.GET.get('fulfillment_status', '')`
  - `current_fraud`: `request.GET.get('fraud_risk_level', '')`
- `ecommerceorder_detail`:
  - `order`: `EcommerceOrder` object
  - `lines`: `order.lines.all()`
  - `fulfillments`: `order.fulfillments.all()`
  - `returns`: `order.returns.all()`
- `ecommerceorder_create` / `ecommerceorder_edit`:
  - `form`: `EcommerceOrderForm`
  - `order`: `EcommerceOrder` object (edit mode only)
  - `is_edit`: boolean

### 4.2 OrderRoutingRule Views
- `orderroutingrule_list`:
  - `page_obj`: paginated `OrderRoutingRule` queryset
  - `rules`: `page_obj.object_list`
  - `strategy_choices`: `OrderRoutingRule.ROUTING_STRATEGY_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_strategy`: `request.GET.get('strategy', '')`
  - `current_status`: `request.GET.get('is_active', '')`
- `orderroutingrule_detail`:
  - `rule`: `OrderRoutingRule` object
- `orderroutingrule_create` / `orderroutingrule_edit`:
  - `form`: `OrderRoutingRuleForm`
  - `rule`: `OrderRoutingRule` object (edit mode only)
  - `is_edit`: boolean

### 4.3 OrderFulfillment Views
- `orderfulfillment_list`:
  - `page_obj`: paginated `OrderFulfillment` queryset
  - `fulfillments`: `page_obj.object_list`
  - `status_choices`: `OrderFulfillment.PACKAGE_STATUS_CHOICES`
  - `centers`: `FulfillmentCenter.objects.filter(tenant=request.tenant)`
  - `current_q`: `request.GET.get('q', '')`
  - `current_status`: `request.GET.get('status', '')`
  - `current_center`: `request.GET.get('center', '')`
- `orderfulfillment_detail`:
  - `fulfillment`: `OrderFulfillment` object
- `orderfulfillment_create` / `orderfulfillment_edit`:
  - `form`: `OrderFulfillmentForm`
  - `fulfillment`: `OrderFulfillment` object (edit mode only)
  - `is_edit`: boolean

### 4.4 ReturnMerchandiseAuthorization Views
- `returnmerchandiseauthorization_list`:
  - `page_obj`: paginated `ReturnMerchandiseAuthorization` queryset
  - `returns`: `page_obj.object_list`
  - `status_choices`: `ReturnMerchandiseAuthorization.RMA_STATUS_CHOICES`
  - `return_type_choices`: `ReturnMerchandiseAuthorization.RETURN_TYPE_CHOICES`
  - `reason_choices`: `ReturnMerchandiseAuthorization.RETURN_REASON_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_status`: `request.GET.get('status', '')`
  - `current_type`: `request.GET.get('return_type', '')`
- `returnmerchandiseauthorization_detail`:
  - `rma`: `ReturnMerchandiseAuthorization` object
- `returnmerchandiseauthorization_create` / `returnmerchandiseauthorization_edit`:
  - `form`: `ReturnMerchandiseAuthorizationForm`
  - `rma`: `ReturnMerchandiseAuthorization` object (edit mode only)
  - `is_edit`: boolean

---

## 5. Navigation `LIVE_LINKS` Contract

File: `apps/core/navigation.py`
Entry: `LIVE_LINKS["9.5"]`
```python
    "9.5": {
        "Order Capture & Validation": "ecommerce:ecommerceorder_list",
        "Order Routing & Splitting": "ecommerce:orderroutingrule_list",
        "Order Status & Tracking": "ecommerce:orderfulfillment_list",
        "Order Modifications & Cancellations": "ecommerce:ecommerceorder_list",
        "Returns & Exchanges (RMA)": "ecommerce:returnmerchandiseauthorization_list",
    },
```

---

## 6. Color-Named Badge Contract

Only use color-named badges from `static/css/theme.css`:
- `badge-green`: Validated, fulfilled, delivered, approved, passed, active
- `badge-red`: Cancelled, failed, rejected, high risk, flagged
- `badge-amber`: Pending, draft, allocated, in transit, requested, medium risk
- `badge-info`: Sourced, exchange, store credit, closest location, low risk
- `badge-slate` / `badge-muted`: Closed, unverified, none, quarantined, scrapped
