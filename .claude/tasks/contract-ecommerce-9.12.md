# Contract — Sub-module 9.12: Subscription & Recurring Commerce (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.12 Subscription & Recurring Commerce · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-31 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0012_...`
- **Package Layout:** `SubscriptionCommerce/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/subscriptioncommerce/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `SubscriptionPlan` (`apps/ecommerce/models/SubscriptionCommerce/SubscriptionPlans.py`)
- **Table:** `ecommerce_subscription_plan`
- **Number Prefix:** `ESPL` (`ESPL-00001`)
- **CHOICES:**
  - `PLAN_TYPE_CHOICES = [('subscribe_save', 'Subscribe & Save (Consumable)'), ('curated_box', 'Curated Assortment Box'), ('membership_club', 'Membership Club')]`
  - `FREQUENCY_CHOICES = [('weekly', 'Weekly'), ('biweekly', 'Bi-Weekly (Every 2 Weeks)'), ('monthly', 'Monthly'), ('bimonthly', 'Bi-Monthly (Every 2 Months)'), ('quarterly', 'Quarterly (Every 3 Months)'), ('annual', 'Annual')]`
  - `DISCOUNT_TYPE_CHOICES = [('percentage', 'Percentage Discount'), ('fixed_amount', 'Fixed Price Discount'), ('none', 'No Recurring Discount')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=60)`
  - `plan_type`: `CharField(max_length=30, choices=PLAN_TYPE_CHOICES, default='subscribe_save')`
  - `frequency`: `CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')`
  - `interval_count`: `PositiveIntegerField(default=1)`
  - `discount_type`: `CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')`
  - `discount_value`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `trial_period_days`: `PositiveIntegerField(default=0)`
  - `min_commitment_cycles`: `PositiveIntegerField(default=1)`
  - `allow_pause`: `BooleanField(default=True)`
  - `allow_skip`: `BooleanField(default=True)`
  - `allow_swap`: `BooleanField(default=True)`
  - `max_pause_days`: `PositiveIntegerField(default=90)`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='subscription_plans')`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_espl_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecommerce_espl_code_uniq')`
  - `Index(fields=['tenant', 'is_active', 'plan_type'], name='idx_espl_ten_act_type')`

---

### 1.2 `CustomerSubscription` (`apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py`)
- **Table:** `ecommerce_customer_subscription`
- **Number Prefix:** `ESUB` (`ESUB-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('trialing', 'Trialing'), ('active', 'Active'), ('paused', 'Paused'), ('past_due', 'Past Due (In Dunning)'), ('pending_cancellation', 'Pending Cancellation'), ('cancelled', 'Cancelled'), ('expired', 'Expired')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=CASCADE, related_name='subscriptions')`
  - `plan`: `ForeignKey('ecommerce.SubscriptionPlan', on_delete=PROTECT, related_name='subscriptions')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=PROTECT, related_name='subscriptions')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='subscriptions')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='active')`
  - `quantity`: `PositiveIntegerField(default=1)`
  - `unit_price`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `recurring_discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `started_at`: `DateTimeField(default=timezone.now)`
  - `next_billing_date`: `DateField()`
  - `next_delivery_date`: `DateField(null=True, blank=True)`
  - `paused_until`: `DateField(null=True, blank=True)`
  - `completed_cycles_count`: `PositiveIntegerField(default=0)`
  - `consecutive_successful_cycles`: `PositiveIntegerField(default=0)`
  - `failed_payment_count`: `PositiveIntegerField(default=0)`
  - `shipping_address_line`: `CharField(max_length=255, blank=True)`
  - `payment_method_ref`: `CharField(max_length=100, blank=True)`
  - `cancellation_reason`: `CharField(max_length=255, blank=True)`
  - `cancelled_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esub_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'next_billing_date'], name='idx_esub_ten_stat_nbill')`
  - `Index(fields=['tenant', 'customer_profile', 'status'], name='idx_esub_ten_cust_stat')`

---

### 1.3 `SubscriptionBoxCuration` (`apps/ecommerce/models/SubscriptionCommerce/SubscriptionBoxCurations.py`)
- **Table:** `ecommerce_subscription_box_curation`
- **Number Prefix:** `ESBX` (`ESBX-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=60)`
  - `plan`: `ForeignKey('ecommerce.SubscriptionPlan', on_delete=CASCADE, related_name='curations')`
  - `cycle_identifier`: `CharField(max_length=50)`
  - `theme_title`: `CharField(max_length=200, blank=True)`
  - `curation_notes`: `TextField(blank=True)`
  - `primary_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='curation_primaries')`
  - `has_surprise_item`: `BooleanField(default=False)`
  - `surprise_item_description`: `CharField(max_length=255, blank=True)`
  - `preference_tag`: `CharField(max_length=100, blank=True)`
  - `start_date`: `DateField()`
  - `end_date`: `DateField()`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esbx_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'plan', 'cycle_identifier'], name='ecommerce_esbx_plan_cycle_uniq')`
  - `Index(fields=['tenant', 'is_active', 'start_date', 'end_date'], name='idx_esbx_ten_act_dates')`

---

### 1.4 `SubscriptionRetentionAction` (`apps/ecommerce/models/SubscriptionCommerce/SubscriptionRetentionActions.py`)
- **Table:** `ecommerce_subscription_retention_action`
- **Number Prefix:** `ESRT` (`ESRT-00001`)
- **CHOICES:**
  - `TRIGGER_TYPE_CHOICES = [('cancel_intent', 'Cancellation Intent Intercept'), ('pause_request', 'Pause Request'), ('dunning_involuntary', 'Involuntary Dunning Decline'), ('predicted_risk', 'High Churn Risk Trigger')]`
  - `REASON_CHOICES = [('too_expensive', 'Too Expensive / Cost'), ('too_much_product', 'Too Much Backlog / Product'), ('poor_quality', 'Product Did Not Meet Expectations'), ('temporary_break', 'Temporary Break / Traveling'), ('switching_competitor', 'Switching to Competitor'), ('other', 'Other Reason')]`
  - `OFFER_CHOICES = [('discount_cycle', 'Discount Next N Cycles'), ('free_skip', 'Free Skip Next Cycle'), ('pause_duration', 'Pause for 30/60 Days'), ('product_swap', 'Swap to Alternate Item'), ('bonus_perk', 'Free Gift / Bonus Item'), ('none', 'No Offer Presented')]`
  - `OUTCOME_CHOICES = [('deflected', 'Deflected / Retained'), ('cancelled', 'Cancelled Anyway'), ('paused', 'Paused Instead'), ('accepted_swap', 'Accepted Product Swap'), ('pending', 'Pending / In Progress')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `subscription`: `ForeignKey('ecommerce.CustomerSubscription', on_delete=CASCADE, related_name='retention_actions')`
  - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=CASCADE, related_name='retention_actions')`
  - `trigger_type`: `CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES, default='cancel_intent')`
  - `cancellation_reason`: `CharField(max_length=50, choices=REASON_CHOICES, default='too_much_product')`
  - `churn_risk_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `offered_action`: `CharField(max_length=30, choices=OFFER_CHOICES, default='discount_cycle')`
  - `offer_discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `outcome`: `CharField(max_length=30, choices=OUTCOME_CHOICES, default='pending')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esrt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'outcome', 'trigger_type'], name='idx_esrt_ten_outc_trig')`
  - `Index(fields=['tenant', 'subscription', 'created_at'], name='idx_esrt_ten_sub_created')`

---

## 2. Forms Contract

All forms inherit from `django.forms.ModelForm`. Exclude `tenant`, `number`, and automated tracking fields.

| Form Class | Entity | Fields Excluded |
|---|---|---|
| `SubscriptionPlanForm` | `SubscriptionPlan` | `tenant`, `number`, `created_at`, `updated_at` |
| `CustomerSubscriptionForm` | `CustomerSubscription` | `tenant`, `number`, `completed_cycles_count`, `consecutive_successful_cycles`, `failed_payment_count`, `cancelled_at`, `created_at`, `updated_at` |
| `SubscriptionBoxCurationForm` | `SubscriptionBoxCuration` | `tenant`, `number`, `created_at`, `updated_at` |
| `SubscriptionRetentionActionForm` | `SubscriptionRetentionAction` | `tenant`, `number`, `created_at`, `updated_at` |

---

## 3. URLs & Routing Contract

`app_name = 'ecommerce'` (already registered in `config/urls.py`).

| Route Pattern | Name | View Function |
|---|---|---|
| `subscription-plans/` | `subscriptionplan_list` | `subscriptionplan_list` |
| `subscription-plans/new/` | `subscriptionplan_create` | `subscriptionplan_create` |
| `subscription-plans/<int:pk>/` | `subscriptionplan_detail` | `subscriptionplan_detail` |
| `subscription-plans/<int:pk>/edit/` | `subscriptionplan_edit` | `subscriptionplan_edit` |
| `subscription-plans/<int:pk>/delete/` | `subscriptionplan_delete` | `subscriptionplan_delete` |
| `subscriptions/` | `customersubscription_list` | `customersubscription_list` |
| `subscriptions/new/` | `customersubscription_create` | `customersubscription_create` |
| `subscriptions/<int:pk>/` | `customersubscription_detail` | `customersubscription_detail` |
| `subscriptions/<int:pk>/edit/` | `customersubscription_edit` | `customersubscription_edit` |
| `subscriptions/<int:pk>/delete/` | `customersubscription_delete` | `customersubscription_delete` |
| `subscription-curations/` | `subscriptionboxcuration_list` | `subscriptionboxcuration_list` |
| `subscription-curations/new/` | `subscriptionboxcuration_create` | `subscriptionboxcuration_create` |
| `subscription-curations/<int:pk>/` | `subscriptionboxcuration_detail` | `subscriptionboxcuration_detail` |
| `subscription-curations/<int:pk>/edit/` | `subscriptionboxcuration_edit` | `subscriptionboxcuration_edit` |
| `subscription-curations/<int:pk>/delete/` | `subscriptionboxcuration_delete` | `subscriptionboxcuration_delete` |
| `subscription-retention/` | `subscriptionretentionaction_list` | `subscriptionretentionaction_list` |
| `subscription-retention/new/` | `subscriptionretentionaction_create` | `subscriptionretentionaction_create` |
| `subscription-retention/<int:pk>/` | `subscriptionretentionaction_detail` | `subscriptionretentionaction_detail` |
| `subscription-retention/<int:pk>/edit/` | `subscriptionretentionaction_edit` | `subscriptionretentionaction_edit` |
| `subscription-retention/<int:pk>/delete/` | `subscriptionretentionaction_delete` | `subscriptionretentionaction_delete` |
| `subscription-portal/` | `subscription_portal` | `subscription_portal` |
| `subscription-portal/<int:pk>/skip/` | `subscription_portal_skip` | `subscription_portal_skip` |
| `subscription-portal/<int:pk>/pause/` | `subscription_portal_pause` | `subscription_portal_pause` |
| `subscription-portal/<int:pk>/resume/` | `subscription_portal_resume` | `subscription_portal_resume` |
| `subscription-portal/<int:pk>/deflect/` | `subscription_portal_deflect` | `subscription_portal_deflect` |

---

## 4. Views Context Contract (Mandatory - Every Context Key Pinned)

### 4.1 `SubscriptionPlan` Views
- `subscriptionplan_list`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionplan/list.html`
  - Context keys:
    - `plans`: Paged queryset of `SubscriptionPlan`
    - `plan_type_choices`: `SubscriptionPlan.PLAN_TYPE_CHOICES`
    - `frequency_choices`: `SubscriptionPlan.FREQUENCY_CHOICES`
    - `selected_plan_type`: `request.GET.get('plan_type', '')`
    - `selected_frequency`: `request.GET.get('frequency', '')`
    - `selected_status`: `request.GET.get('status', '')`
    - `query`: `request.GET.get('q', '')`
- `subscriptionplan_detail`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionplan/detail.html`
  - Context keys:
    - `plan`: Single `SubscriptionPlan` instance
    - `active_subscriptions`: Queryset of `CustomerSubscription` linked to this plan
    - `active_curations`: Queryset of `SubscriptionBoxCuration` linked to this plan
- `subscriptionplan_create` / `subscriptionplan_edit`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionplan/form.html`
  - Context keys:
    - `form`: `SubscriptionPlanForm`
    - `plan`: `SubscriptionPlan` instance (in edit mode) or `None` (create mode)

### 4.2 `CustomerSubscription` Views
- `customersubscription_list`:
  - Template: `ecommerce/subscriptioncommerce/customersubscription/list.html`
  - Context keys:
    - `subscriptions`: Paged queryset of `CustomerSubscription`
    - `status_choices`: `CustomerSubscription.STATUS_CHOICES`
    - `plans`: Queryset of active `SubscriptionPlan`
    - `selected_status`: `request.GET.get('status', '')`
    - `selected_plan`: `request.GET.get('plan', '')`
    - `query`: `request.GET.get('q', '')`
- `customersubscription_detail`:
  - Template: `ecommerce/subscriptioncommerce/customersubscription/detail.html`
  - Context keys:
    - `subscription`: Single `CustomerSubscription` instance
    - `retention_actions`: Queryset of `SubscriptionRetentionAction`
- `customersubscription_create` / `customersubscription_edit`:
  - Template: `ecommerce/subscriptioncommerce/customersubscription/form.html`
  - Context keys:
    - `form`: `CustomerSubscriptionForm`
    - `subscription`: `CustomerSubscription` instance (edit) or `None` (create)

### 4.3 `SubscriptionBoxCuration` Views
- `subscriptionboxcuration_list`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionboxcuration/list.html`
  - Context keys:
    - `curations`: Paged queryset of `SubscriptionBoxCuration`
    - `plans`: Queryset of `SubscriptionPlan` (curated_box type)
    - `selected_plan`: `request.GET.get('plan', '')`
    - `selected_status`: `request.GET.get('status', '')`
    - `query`: `request.GET.get('q', '')`
- `subscriptionboxcuration_detail`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionboxcuration/detail.html`
  - Context keys:
    - `curation`: Single `SubscriptionBoxCuration` instance
- `subscriptionboxcuration_create` / `subscriptionboxcuration_edit`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionboxcuration/form.html`
  - Context keys:
    - `form`: `SubscriptionBoxCurationForm`
    - `curation`: `SubscriptionBoxCuration` instance (edit) or `None` (create)

### 4.4 `SubscriptionRetentionAction` Views
- `subscriptionretentionaction_list`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionretentionaction/list.html`
  - Context keys:
    - `retention_actions`: Paged queryset of `SubscriptionRetentionAction`
    - `trigger_type_choices`: `SubscriptionRetentionAction.TRIGGER_TYPE_CHOICES`
    - `outcome_choices`: `SubscriptionRetentionAction.OUTCOME_CHOICES`
    - `reason_choices`: `SubscriptionRetentionAction.REASON_CHOICES`
    - `selected_trigger`: `request.GET.get('trigger_type', '')`
    - `selected_outcome`: `request.GET.get('outcome', '')`
    - `query`: `request.GET.get('q', '')`
- `subscriptionretentionaction_detail`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionretentionaction/detail.html`
  - Context keys:
    - `retention_action`: Single `SubscriptionRetentionAction` instance
- `subscriptionretentionaction_create` / `subscriptionretentionaction_edit`:
  - Template: `ecommerce/subscriptioncommerce/subscriptionretentionaction/form.html`
  - Context keys:
    - `form`: `SubscriptionRetentionActionForm`
    - `retention_action`: `SubscriptionRetentionAction` instance (edit) or `None` (create)

### 4.5 `SubscriptionPortals` Console View
- `subscription_portal`:
  - Template: `ecommerce/subscriptioncommerce/portal/portal.html`
  - Context keys:
    - `active_subscriptions`: Queryset of active subscriptions for current customer profile
    - `paused_subscriptions`: Queryset of paused subscriptions
    - `retention_actions`: Recent retention history
    - `total_subscribers`: Count of active subscriptions
    - `monthly_recurring_revenue`: Aggregated MRR estimate

---

## 5. Templates Contract & Color Badges

All badges must use theme.css colour-named classes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`):

| State / Choice | Badge Class |
|---|---|
| `active`, `deflected` | `badge-green` |
| `paused`, `accepted_swap` | `badge-amber` |
| `trialing`, `pending` | `badge-info` |
| `past_due`, `cancelled`, `cancelled_anyway` | `badge-red` |
| `expired`, `pending_cancellation`, `none` | `badge-muted` / `badge-slate` |

---
*End of Frozen Contract — Sub-module 9.12*
