# Contract — Sub-module 9.4: Shopping Cart & Checkout (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.4 Shopping Cart & Checkout · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-29 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0005_...`

---

## 1. Models & CHOICES Contract

All models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `Cart` & `CartItem` (`apps/ecommerce/models/CartCheckout/Carts.py`)
- **Table:** `ecommerce_cart` (and `ecommerce_cart_item`)
- **Number Prefix:** `ECRT` (`ECRT-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('active', 'Active'), ('locked', 'Locked (In Checkout)'), ('abandoned', 'Abandoned'), ('converted', 'Converted to Order'), ('expired', 'Expired')]`
- **Fields (`Cart`):**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_carts')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_carts')`
  - `session_key`: `CharField(max_length=64, blank=True, db_index=True)`
  - `email`: `EmailField(blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)`
  - `currency`: `CharField(max_length=3, default='USD')`
  - `subtotal`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `discount_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `tax_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `shipping_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `grand_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `coupon_code`: `CharField(max_length=50, blank=True)`
  - `last_activity_at`: `DateTimeField(default=timezone.now)`
  - `abandoned_at`: `DateTimeField(null=True, blank=True)`
  - `recovery_token`: `CharField(max_length=64, blank=True, null=True)`
  - `recovery_sent_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Fields (`CartItem`):**
  - `cart`: `ForeignKey('ecommerce.Cart', on_delete=CASCADE, related_name='items')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='cart_items')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='cart_items')`
  - `quantity`: `PositiveIntegerField(default=1)`
  - `unit_price`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `total_price`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `custom_attributes`: `JSONField(default=dict, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_cart_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='ecom_cart_tnt_stat_idx')`
  - `Index(fields=['tenant', 'session_key'], name='ecom_cart_tnt_sess_idx')`
  - `Index(fields=['tenant', 'customer'], name='ecom_cart_tnt_cust_idx')`
  - `Index(fields=['cart', 'product'], name='ecom_citem_cart_prd_idx')`

### 1.2 `CheckoutSession` (`apps/ecommerce/models/CartCheckout/CheckoutSessions.py`)
- **Table:** `ecommerce_checkout_session`
- **Number Prefix:** `ECKS` (`ECKS-00001`)
- **CHOICES:**
  - `FLOW_TYPE_CHOICES = [('one_page', 'One-Page Checkout'), ('multi_step', 'Multi-Step Checkout')]`
  - `STEP_CHOICES = [('contact', 'Contact Details'), ('shipping_address', 'Shipping Address'), ('shipping_method', 'Shipping Method'), ('payment', 'Payment'), ('review', 'Review & Place Order'), ('completed', 'Completed')]`
  - `STATUS_CHOICES = [('in_progress', 'In Progress'), ('processing', 'Processing Payment'), ('completed', 'Completed'), ('expired', 'Expired'), ('abandoned', 'Abandoned')]`
  - `PAYMENT_STATUS_CHOICES = [('pending', 'Pending'), ('authorized', 'Authorized'), ('paid', 'Paid'), ('failed', 'Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_checkout_sessions')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `cart`: `ForeignKey('ecommerce.Cart', on_delete=CASCADE, related_name='checkout_sessions')`
  - `customer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_checkout_sessions')`
  - `email`: `EmailField()`
  - `phone`: `CharField(max_length=30, blank=True)`
  - `flow_type`: `CharField(max_length=20, choices=FLOW_TYPE_CHOICES, default='one_page')`
  - `current_step`: `CharField(max_length=20, choices=STEP_CHOICES, default='contact')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', db_index=True)`
  - `shipping_name`: `CharField(max_length=150, blank=True)`
  - `shipping_address_line1`: `CharField(max_length=255, blank=True)`
  - `shipping_address_line2`: `CharField(max_length=255, blank=True)`
  - `shipping_city`: `CharField(max_length=100, blank=True)`
  - `shipping_state`: `CharField(max_length=100, blank=True)`
  - `shipping_postal_code`: `CharField(max_length=30, blank=True)`
  - `shipping_country`: `CharField(max_length=2, default='US')`
  - `billing_same_as_shipping`: `BooleanField(default=True)`
  - `billing_name`: `CharField(max_length=150, blank=True)`
  - `billing_address_line1`: `CharField(max_length=255, blank=True)`
  - `billing_city`: `CharField(max_length=100, blank=True)`
  - `billing_state`: `CharField(max_length=100, blank=True)`
  - `billing_postal_code`: `CharField(max_length=30, blank=True)`
  - `billing_country`: `CharField(max_length=2, default='US')`
  - `shipping_method`: `ForeignKey('ecommerce.ShippingMethodConfig', on_delete=SET_NULL, null=True, blank=True, related_name='checkout_sessions')`
  - `payment_method`: `ForeignKey('ecommerce.PaymentMethodConfig', on_delete=SET_NULL, null=True, blank=True, related_name='checkout_sessions')`
  - `tax_code`: `ForeignKey('accounting.TaxCode', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_checkouts')`
  - `tax_jurisdiction`: `CharField(max_length=100, blank=True)`
  - `tax_rate`: `DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))`
  - `is_tax_exempt`: `BooleanField(default=False)`
  - `tax_exemption_number`: `CharField(max_length=50, blank=True)`
  - `tax_breakdown`: `JSONField(default=dict, blank=True)`
  - `subtotal_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `discount_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `shipping_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `tax_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `total_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `payment_status`: `CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')`
  - `payment_transaction_id`: `CharField(max_length=100, blank=True)`
  - `order_reference`: `CharField(max_length=50, blank=True)`
  - `expires_at`: `DateTimeField()`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_cks_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='ecom_cks_tnt_stat_idx')`
  - `Index(fields=['tenant', 'cart'], name='ecom_cks_tnt_cart_idx')`
  - `Index(fields=['tenant', 'customer'], name='ecom_cks_tnt_cust_idx')`

### 1.3 `ShippingMethodConfig` (`apps/ecommerce/models/CartCheckout/ShippingMethods.py`)
- **Table:** `ecommerce_shipping_method_config`
- **Number Prefix:** `ESHP` (`ESHP-00001`)
- **CHOICES:**
  - `CARRIER_CHOICES = [('custom', 'Custom / Internal Fleet'), ('fedex', 'FedEx'), ('ups', 'UPS'), ('usps', 'USPS'), ('dhl', 'DHL')]`
  - `CALC_TYPE_CHOICES = [('flat_rate', 'Flat Rate'), ('weight_tiered', 'Weight-Based Tier'), ('free_threshold', 'Free Above Subtotal Threshold'), ('local_pickup', 'Local Store Pickup / Free')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_shipping_methods')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=100)`
  - `code`: `CharField(max_length=50)`
  - `carrier`: `CharField(max_length=20, choices=CARRIER_CHOICES, default='custom')`
  - `calculation_type`: `CharField(max_length=20, choices=CALC_TYPE_CHOICES, default='flat_rate')`
  - `base_rate`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `cost_per_kg`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `free_shipping_threshold`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `estimated_days_min`: `PositiveSmallIntegerField(default=3)`
  - `estimated_days_max`: `PositiveSmallIntegerField(default=5)`
  - `destination_countries`: `CharField(max_length=255, default='US,CA')`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `sort_order`: `PositiveSmallIntegerField(default=0)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_shp_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecom_shp_tenant_code_uniq')`
  - `Index(fields=['tenant', 'is_active', 'sort_order'], name='ecom_shp_tnt_act_sort_idx')`

### 1.4 `PaymentMethodConfig` (`apps/ecommerce/models/CartCheckout/PaymentMethods.py`)
- **Table:** `ecommerce_payment_method_config`
- **Number Prefix:** `EPMC` (`EPMC-00001`)
- **CHOICES:**
  - `PROVIDER_CHOICES = [('stripe', 'Stripe Payments'), ('paypal', 'PayPal Express'), ('klarna', 'Klarna BNPL'), ('bank_transfer', 'Direct Bank Transfer / Wire'), ('cod', 'Cash on Delivery (COD)')]`
  - `CATEGORY_CHOICES = [('credit_card', 'Credit / Debit Card'), ('wallet', 'Digital Wallet'), ('bnpl', 'Buy Now Pay Later'), ('bank_transfer', 'Bank Transfer'), ('cash_on_delivery', 'Cash on Delivery')]`
  - `ENVIRONMENT_CHOICES = [('sandbox', 'Sandbox / Test Mode'), ('production', 'Live / Production')]`
  - `FEE_TYPE_CHOICES = [('none', 'No Surcharge'), ('percentage', 'Percentage Surcharge'), ('fixed', 'Fixed Fee Surcharge')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_payment_methods')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=100)`
  - `provider`: `CharField(max_length=30, choices=PROVIDER_CHOICES, default='stripe')`
  - `method_category`: `CharField(max_length=20, choices=CATEGORY_CHOICES, default='credit_card')`
  - `environment`: `CharField(max_length=15, choices=ENVIRONMENT_CHOICES, default='sandbox')`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `display_order`: `PositiveSmallIntegerField(default=0)`
  - `fee_type`: `CharField(max_length=15, choices=FEE_TYPE_CHOICES, default='none')`
  - `fee_amount`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `min_order_amount`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `max_order_amount`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `supported_currencies`: `CharField(max_length=100, default='USD,EUR,GBP')`
  - `instructions`: `TextField(blank=True)`
  - `supports_refunds`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (<= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecom_pmc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'display_order'], name='ecom_pmc_tnt_act_dsp_idx')`
  - `Index(fields=['tenant', 'provider'], name='ecom_pmc_tnt_prov_idx')`

---

## 2. Forms Contract & Form Exclusions

Every form inherits `apps.ecommerce.forms._common.BaseEcommerceModelForm` or standard `forms.ModelForm`. Exclude non-editable system attributes.

### 2.1 `CartForm` & `CartItemForm` (`apps/ecommerce/forms/CartCheckout/Carts.py`)
- **Model:** `Cart`
- **Fields:** `['customer', 'session_key', 'email', 'status', 'currency', 'coupon_code', 'notes']`
- **Excludes:** `['tenant', 'number', 'subtotal', 'discount_total', 'tax_total', 'shipping_total', 'grand_total', 'abandoned_at', 'recovery_token', 'recovery_sent_at', 'last_activity_at', 'created_at', 'updated_at']`
- **Child Form `CartItemForm`:**
  - **Model:** `CartItem`
  - **Fields:** `['product', 'variant', 'quantity', 'unit_price', 'total_price']`

### 2.2 `CheckoutSessionForm` (`apps/ecommerce/forms/CartCheckout/CheckoutSessions.py`)
- **Model:** `CheckoutSession`
- **Fields:** `['cart', 'customer', 'email', 'phone', 'flow_type', 'current_step', 'status', 'shipping_name', 'shipping_address_line1', 'shipping_address_line2', 'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country', 'billing_same_as_shipping', 'billing_name', 'billing_address_line1', 'billing_city', 'billing_state', 'billing_postal_code', 'billing_country', 'shipping_method', 'payment_method', 'tax_code', 'tax_jurisdiction', 'tax_rate', 'is_tax_exempt', 'tax_exemption_number', 'subtotal_amount', 'discount_amount', 'shipping_amount', 'tax_amount', 'total_amount', 'payment_status', 'expires_at']`
- **Excludes:** `['tenant', 'number', 'payment_transaction_id', 'order_reference', 'completed_at', 'created_at', 'updated_at']`

### 2.3 `ShippingMethodConfigForm` (`apps/ecommerce/forms/CartCheckout/ShippingMethods.py`)
- **Model:** `ShippingMethodConfig`
- **Fields:** `['name', 'code', 'carrier', 'calculation_type', 'base_rate', 'cost_per_kg', 'free_shipping_threshold', 'estimated_days_min', 'estimated_days_max', 'destination_countries', 'is_active', 'sort_order', 'description']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Clean:** Uppercase `code.strip().upper()`

### 2.4 `PaymentMethodConfigForm` (`apps/ecommerce/forms/CartCheckout/PaymentMethods.py`)
- **Model:** `PaymentMethodConfig`
- **Fields:** `['name', 'provider', 'method_category', 'environment', 'is_active', 'display_order', 'fee_type', 'fee_amount', 'min_order_amount', 'max_order_amount', 'supported_currencies', 'instructions', 'supports_refunds']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`

---

## 3. URLs Contract (Route Names & Paths)

Namespace: `ecommerce:` (set in `apps/ecommerce/urls/__init__.py`)

| URL Name | Pattern | View Function |
|---|---|---|
| `cart_list` | `cart-checkout/carts/` | `cart_list` |
| `cart_create` | `cart-checkout/carts/create/` | `cart_create` |
| `cart_detail` | `cart-checkout/carts/<int:pk>/` | `cart_detail` |
| `cart_edit` | `cart-checkout/carts/<int:pk>/edit/` | `cart_edit` |
| `cart_delete` | `cart-checkout/carts/<int:pk>/delete/` | `cart_delete` |
| `cart_recover` | `cart-checkout/carts/<int:pk>/recover/` | `cart_recover` |
| `checkoutsession_list` | `cart-checkout/sessions/` | `checkoutsession_list` |
| `checkoutsession_create` | `cart-checkout/sessions/create/` | `checkoutsession_create` |
| `checkoutsession_detail` | `cart-checkout/sessions/<int:pk>/` | `checkoutsession_detail` |
| `checkoutsession_edit` | `cart-checkout/sessions/<int:pk>/edit/` | `checkoutsession_edit` |
| `checkoutsession_delete` | `cart-checkout/sessions/<int:pk>/delete/` | `checkoutsession_delete` |
| `checkoutsession_advance` | `cart-checkout/sessions/<int:pk>/advance/` | `checkoutsession_advance` |
| `shippingmethodconfig_list` | `cart-checkout/shipping-methods/` | `shippingmethodconfig_list` |
| `shippingmethodconfig_create` | `cart-checkout/shipping-methods/create/` | `shippingmethodconfig_create` |
| `shippingmethodconfig_detail` | `cart-checkout/shipping-methods/<int:pk>/` | `shippingmethodconfig_detail` |
| `shippingmethodconfig_edit` | `cart-checkout/shipping-methods/<int:pk>/edit/` | `shippingmethodconfig_edit` |
| `shippingmethodconfig_delete` | `cart-checkout/shipping-methods/<int:pk>/delete/` | `shippingmethodconfig_delete` |
| `shippingmethodconfig_toggle` | `cart-checkout/shipping-methods/<int:pk>/toggle/` | `shippingmethodconfig_toggle` |
| `paymentmethodconfig_list` | `cart-checkout/payment-methods/` | `paymentmethodconfig_list` |
| `paymentmethodconfig_create` | `cart-checkout/payment-methods/create/` | `paymentmethodconfig_create` |
| `paymentmethodconfig_detail` | `cart-checkout/payment-methods/<int:pk>/` | `paymentmethodconfig_detail` |
| `paymentmethodconfig_edit` | `cart-checkout/payment-methods/<int:pk>/edit/` | `paymentmethodconfig_edit` |
| `paymentmethodconfig_delete` | `cart-checkout/payment-methods/<int:pk>/delete/` | `paymentmethodconfig_delete` |
| `paymentmethodconfig_toggle` | `cart-checkout/payment-methods/<int:pk>/toggle/` | `paymentmethodconfig_toggle` |

---

## 4. View Context Contract

Pinning every context key across all 9.4 views:

### 4.1 Cart Views
- `cart_list`:
  - `page_obj`: paginated `Cart` queryset
  - `carts`: `page_obj.object_list`
  - `status_choices`: `Cart.STATUS_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_status`: `request.GET.get('status', '')`
- `cart_detail`:
  - `cart`: `Cart` object
  - `items`: `cart.items.select_related('product', 'variant').all()`
- `cart_create` / `cart_edit`:
  - `form`: `CartForm`
  - `cart`: `Cart` object (edit mode only)
  - `is_edit`: boolean

### 4.2 CheckoutSession Views
- `checkoutsession_list`:
  - `page_obj`: paginated `CheckoutSession` queryset
  - `sessions`: `page_obj.object_list`
  - `status_choices`: `CheckoutSession.STATUS_CHOICES`
  - `flow_choices`: `CheckoutSession.FLOW_TYPE_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_status`: `request.GET.get('status', '')`
  - `current_flow`: `request.GET.get('flow_type', '')`
- `checkoutsession_detail`:
  - `session`: `CheckoutSession` object
  - `cart`: `session.cart`
  - `tax_codes`: `TaxCode.objects.filter(tenant=request.tenant)`
  - `shipping_methods`: `ShippingMethodConfig.objects.filter(tenant=request.tenant, is_active=True)`
  - `payment_methods`: `PaymentMethodConfig.objects.filter(tenant=request.tenant, is_active=True)`
- `checkoutsession_create` / `checkoutsession_edit`:
  - `form`: `CheckoutSessionForm`
  - `session`: `CheckoutSession` object (edit mode only)
  - `is_edit`: boolean

### 4.3 ShippingMethodConfig Views
- `shippingmethodconfig_list`:
  - `page_obj`: paginated `ShippingMethodConfig` queryset
  - `methods`: `page_obj.object_list`
  - `carrier_choices`: `ShippingMethodConfig.CARRIER_CHOICES`
  - `calc_type_choices`: `ShippingMethodConfig.CALC_TYPE_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_carrier`: `request.GET.get('carrier', '')`
  - `current_calc`: `request.GET.get('calculation_type', '')`
- `shippingmethodconfig_detail`:
  - `method`: `ShippingMethodConfig` object
- `shippingmethodconfig_create` / `shippingmethodconfig_edit`:
  - `form`: `ShippingMethodConfigForm`
  - `method`: `ShippingMethodConfig` object (edit mode only)
  - `is_edit`: boolean

### 4.4 PaymentMethodConfig Views
- `paymentmethodconfig_list`:
  - `page_obj`: paginated `PaymentMethodConfig` queryset
  - `methods`: `page_obj.object_list`
  - `provider_choices`: `PaymentMethodConfig.PROVIDER_CHOICES`
  - `category_choices`: `PaymentMethodConfig.CATEGORY_CHOICES`
  - `current_q`: `request.GET.get('q', '')`
  - `current_provider`: `request.GET.get('provider', '')`
  - `current_category`: `request.GET.get('method_category', '')`
- `paymentmethodconfig_detail`:
  - `method`: `PaymentMethodConfig` object
- `paymentmethodconfig_create` / `paymentmethodconfig_edit`:
  - `form`: `PaymentMethodConfigForm`
  - `method`: `PaymentMethodConfig` object (edit mode only)
  - `is_edit`: boolean

---

## 5. Navigation Wiring Contract (`LIVE_LINKS["9.4"]`)

In `apps/core/navigation.py`:

```python
    "9.4": {
        "Persistent & Guest Cart": "ecommerce:cart_list",
        "One-Page & Multi-Step Checkout": "ecommerce:checkoutsession_list",
        "Shipping Rate Calculation": "ecommerce:shippingmethodconfig_list",
        "Tax Calculation & Compliance": "ecommerce:checkoutsession_list",
        "Payment Method Orchestration": "ecommerce:paymentmethodconfig_list",
    },
```
