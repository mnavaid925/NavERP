# Build Contract — Sub-module 8.15: Contract & Subscription Management (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = f64118d1453d8b4e05181cf64ba89d9a95ddb49f`.
> Research: `.claude/tasks/research-sales-8.15.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0028_contractsubscription`** (claimed).

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.15 adds 4 tenant-scoped models and 2 derived real-time computed consoles. It declares **zero duplicate customer, quote, sales order, currency, document, user, or platform subscription master**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.15's Relationship |
|---|---|---|---|
| **Customer Accounts** | **core 0** | `apps/core/models/Party.py` | `core.Party` (with customer role) is the contracting party (`CustomerContract.account`, `CustomerSubscription.account`). Zero duplicate customer/client master. |
| **Originating Quotes** | **Sales 8.5** | `apps/sales/models/QuoteProposalCPQ/CPQQuotes.py` | `sales.CPQQuote` (`CPQ-`) is linked as originating proposal and generated renewal quote (`CustomerContract.originating_quote`, `CustomerSubscription.renewal_quote`). Zero duplicate proposal table. |
| **Sales Orders** | **SCM 4.5** | `apps/scm/models/OrderManagement/SalesOrders.py` | `scm.SalesOrder` (`SO-`) is linked as originating sales order (`CustomerContract.originating_order`). Zero duplicate order table. |
| **Operating Currencies** | **Accounting 2.2** | `apps/accounting/models/GeneralLedger/Currencies.py` | `accounting.Currency` governs multi-currency TCV, ACV, MRR, and overage rates (`CustomerContract.currency`, `CustomerSubscription.currency`). Zero duplicate currency master. |
| **Contract Documents & Redlines** | **core 0** | `apps/core/models/Document.py` | `core.Document` (`DOC-`) stores binary executed PDF contracts and redlines (`CustomerContract.document`). Zero duplicate file table. |
| **Legal Document Templates** | **CRM 1.9** | `apps/crm/models/DocumentContract/DocTemplates.py` | `crm.DocTemplate` (`TPL-`) provides reusable clause/contract merge templates (`CustomerContract.template`). Zero duplicate template master. |
| **Users / Owners / Assignees** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) for contract managers, CSMs, and obligation owners. Zero duplicate user master. |
| **Platform Subscriptions (Distinction)** | **tenants 0** | `apps/tenants/models/Subscription.py` | `tenants.Subscription` owns the tenant's own subscription to the NavERP SaaS platform. Commercial customer-facing subscriptions in 8.15 are named `CustomerSubscription` (`CSB-`) to guarantee complete separation. |

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/ContractSubscriptionManagement/`.
Base: `apps.sales.models._base.TenantNumbered` (includes `tenant` FK `core.Tenant`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`).

### 1.1 `CustomerContract` (`CustomerContracts.py`) — `NUMBER_PREFIX = "CCT"`

```python
CONTRACT_TYPE_CHOICES = [
    ("subscription_agreement", "Software Subscription Agreement"),
    ("msa", "Master Services Agreement (MSA)"),
    ("sow", "Statement of Work (SOW)"),
    ("sla", "Service Level Agreement (SLA)"),
    ("nda", "Non-Disclosure Agreement (NDA)"),
    ("custom", "Custom Commercial Agreement"),
]

CONTRACT_STATUS_CHOICES = [
    ("draft", "Draft Authoring"),
    ("internal_review", "Internal Legal Review"),
    ("negotiating", "Redlining & Negotiation"),
    ("active", "Active / Executed"),
    ("amended", "Amended"),
    ("terminated", "Terminated"),
    ("expired", "Expired"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `account` | `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="customer_contracts")` | Required. Tenant guard. |
| `title` | `CharField(max_length=255)` | Required. |
| `contract_type` | `CharField(max_length=40, choices=CONTRACT_TYPE_CHOICES, default="subscription_agreement")` | Indexed. Longest value = 22 chars. |
| `status` | `CharField(max_length=30, choices=CONTRACT_STATUS_CHOICES, default="draft")` | Indexed. Longest value = 15 chars. |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_customer_contracts")` | Assigned Contract Executive. |
| `currency` | `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="+")` | Required. Default active tenant currency. |
| `total_contract_value` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | TCV across total duration. |
| `annual_contract_value` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | ACV annualized. |
| `start_date` | `DateField()` | Required. |
| `end_date` | `DateField(null=True, blank=True)` | Optional (null = perpetual). |
| `auto_renew` | `BooleanField(default=False)` | Automated renewal trigger flag. |
| `renewal_term_months` | `PositiveIntegerField(default=12)` | Renewal term in months. |
| `notice_period_days` | `PositiveIntegerField(default=30)` | Notice period before expiration. |
| `price_uplift_pct` | `DecimalField(max_digits=5, decimal_places=2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Escalation / uplift percentage. |
| `governing_law` | `CharField(max_length=120, blank=True)` | Jurisdiction venue. |
| `originating_quote` | `ForeignKey("sales.CPQQuote", on_delete=models.SET_NULL, null=True, blank=True, related_name="originated_contracts")` | Originating CPQ quote. |
| `originating_order` | `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="originated_contracts")` | Originating Sales Order. |
| `template` | `ForeignKey("crm.DocTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_contracts")` | Legal template source. |
| `document` | `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_contracts")` | Signed agreement / redline attachment. |
| `special_terms` | `TextField(blank=True)` | Custom negotiated legal clauses. |
| `redline_notes` | `TextField(blank=True)` | Collaborative negotiation and audit history. |
| `signed_at` | `DateTimeField(null=True, blank=True)` | Timestamp set upon activation. |
| `signoff_contact` | `CharField(max_length=150, blank=True)` | Signer name & title. |

- `Meta.ordering = ["-start_date", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_cct_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_cct_ten_status_idx")` (24 chars <= 30)
  - `Index(fields=["tenant", "account"], name="sales_cct_ten_acc_idx")` (21 chars <= 30)
  - `Index(fields=["tenant", "end_date"], name="sales_cct_ten_end_idx")` (21 chars <= 30)
- `clean()`:
  - If `end_date` is set, assert `end_date >= start_date`.
  - Validate multi-tenant integrity for `account`, `owner`, `originating_quote`, `originating_order`, `template`, and `document`.

---

### 1.2 `CustomerSubscription` (`CustomerSubscriptions.py`) — `NUMBER_PREFIX = "CSB"`

```python
SUBSCRIPTION_STATUS_CHOICES = [
    ("trialing", "Trialing"),
    ("active", "Active"),
    ("paused", "Paused / Suspended"),
    ("past_due", "Past Due / Grace Period"),
    ("cancelled", "Cancelled"),
    ("expired", "Expired"),
]

PRICING_MODEL_CHOICES = [
    ("per_seat", "Per Seat / User License"),
    ("flat_fee", "Flat Recurring Fee"),
    ("usage_metered", "Usage Metered (In Arrears)"),
    ("hybrid", "Hybrid (Base Fee + Overage)"),
]

BILLING_CADENCE_CHOICES = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `contract` | `ForeignKey("sales.CustomerContract", on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions")` | Umbrella legal agreement. |
| `account` | `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="customer_subscriptions")` | Subscribing customer client. |
| `subscription_name` | `CharField(max_length=255)` | Service / plan name. |
| `plan_code` | `CharField(max_length=60)` | Product / tier SKU code. |
| `status` | `CharField(max_length=30, choices=SUBSCRIPTION_STATUS_CHOICES, default="active")` | Indexed. Longest value = 9 chars. |
| `pricing_model` | `CharField(max_length=30, choices=PRICING_MODEL_CHOICES, default="per_seat")` | Longest value = 13 chars. |
| `billing_cadence` | `CharField(max_length=20, choices=BILLING_CADENCE_CHOICES, default="monthly")` | Longest value = 11 chars. |
| `currency` | `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="+")` | Billing currency. |
| `quantity` | `PositiveIntegerField(default=1, validators=[MinValueValidator(1)])` | Licensed seats or plan units. |
| `unit_price` | `DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | Unit rate per billing cadence. |
| `mrr` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | Computed normalized monthly revenue. |
| `start_date` | `DateField()` | Initial activation date. |
| `current_term_start` | `DateField()` | Current active term start. |
| `current_term_end` | `DateField()` | Current active term end. |
| `trial_ends_at` | `DateField(null=True, blank=True)` | Trial period expiration. |
| `paused_at` | `DateTimeField(null=True, blank=True)` | Pause timestamp. |
| `resumed_at` | `DateTimeField(null=True, blank=True)` | Resume timestamp. |
| `cancelled_at` | `DateTimeField(null=True, blank=True)` | Cancellation timestamp. |
| `cancellation_reason` | `TextField(blank=True)` | Churn exit reason. Required when cancelled. |
| `auto_renew` | `BooleanField(default=True)` | Auto-renew toggle. |
| `renewal_notice_days` | `PositiveIntegerField(default=30)` | Advance notice window. |
| `renewal_quote` | `ForeignKey("sales.CPQQuote", on_delete=models.SET_NULL, null=True, blank=True, related_name="renewal_subscriptions")` | Linked draft renewal CPQ quote. |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_customer_subscriptions")` | Assigned CSM / Account Exec. |

- `Meta.ordering = ["-current_term_end", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_csb_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_csb_ten_status_idx")` (24 chars <= 30)
  - `Index(fields=["tenant", "account"], name="sales_csb_ten_acc_idx")` (21 chars <= 30)
  - `Index(fields=["tenant", "current_term_end"], name="sales_csb_ten_end_idx")` (21 chars <= 30)
- `clean()`:
  - Assert `current_term_end >= current_term_start`.
  - When `status == "cancelled"`, require non-empty `cancellation_reason`.
  - Multi-tenant checks for `contract`, `account`, `renewal_quote`, and `owner`.
  - Auto-normalize `mrr`:
    - Monthly: `quantity * unit_price`
    - Quarterly: `(quantity * unit_price) / 3`
    - Semi-Annual: `(quantity * unit_price) / 6`
    - Annual: `(quantity * unit_price) / 12`

---

### 1.3 `UsageMeterRecord` (`UsageMeterRecords.py`) — `NUMBER_PREFIX = "UMR"`

```python
USAGE_STATUS_CHOICES = [
    ("metering", "Metering in Progress"),
    ("calculated", "Charges Calculated"),
    ("invoiced", "Invoiced"),
    ("disputed", "Disputed / Adjusted"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `subscription` | `ForeignKey("sales.CustomerSubscription", on_delete=models.CASCADE, related_name="usage_records")` | Parent subscription. Required. |
| `meter_name` | `CharField(max_length=120)` | Metric name (e.g. `API Calls`, `Storage GB`). |
| `unit_of_measure` | `CharField(max_length=40, default="units")` | Unit string. |
| `billing_period_start` | `DateField()` | Usage cycle start. |
| `billing_period_end` | `DateField()` | Usage cycle end. |
| `included_allowance` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | Base included quota. |
| `reported_usage` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | Raw recorded consumption. |
| `billable_overage_units` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | `max(0, reported_usage - included_allowance)`. |
| `overage_unit_price` | `DecimalField(max_digits=10, decimal_places=4, default=0.00, validators=[MinValueValidator(0)])` | Unit price for overage. |
| `overage_total_charge` | `DecimalField(max_digits=14, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | `billable_overage_units * overage_unit_price`. |
| `status` | `CharField(max_length=20, choices=USAGE_STATUS_CHOICES, default="metering")` | Indexed. Longest value = 10 chars. |
| `invoiced_at` | `DateTimeField(null=True, blank=True)` | Invoicing execution timestamp. |
| `notes` | `TextField(blank=True)` | Audit or metric source notes. |

- `Meta.ordering = ["-billing_period_end", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_umr_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_umr_ten_status_idx")` (24 chars <= 30)
  - `Index(fields=["tenant", "subscription"], name="sales_umr_ten_sub_idx")` (21 chars <= 30)
  - `Index(fields=["tenant", "billing_period_end"], name="sales_umr_ten_period_idx")` (24 chars <= 30)
- `clean()`:
  - Assert `billing_period_end >= billing_period_start`.
  - Validate multi-tenant integrity with `subscription.tenant == self.tenant`.
  - Calculate `billable_overage_units = max(Decimal("0.00"), reported_usage - included_allowance)`.
  - Calculate `overage_total_charge = billable_overage_units * overage_unit_price`.

---

### 1.4 `ContractObligation` (`ContractObligations.py`) — `NUMBER_PREFIX = "OBL"`

```python
OBLIGATION_TYPE_CHOICES = [
    ("sla_uptime", "SLA Uptime Benchmark"),
    ("sla_response", "SLA Support Response Time"),
    ("delivery_milestone", "Project Delivery Milestone"),
    ("reporting_compliance", "Regulatory & Reporting Compliance"),
    ("warranty_support", "Warranty & Support Obligation"),
    ("security_review", "Security Assessment / Audit"),
]

OBLIGATION_STATUS_CHOICES = [
    ("pending", "Pending Fulfillment"),
    ("fulfilled", "Fulfilled"),
    ("at_risk", "At Risk"),
    ("breached", "Breached / Default"),
    ("waived", "Waived by Mutual Agreement"),
]

PENALTY_STATUS_CHOICES = [
    ("none", "No Penalty"),
    ("assessed", "Penalty Assessed"),
    ("credited", "Service Credit Issued"),
    ("waived", "Penalty Waived"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `contract` | `ForeignKey("sales.CustomerContract", on_delete=models.CASCADE, related_name="obligations")` | Parent contract. Required. |
| `subscription` | `ForeignKey("sales.CustomerSubscription", on_delete=models.SET_NULL, null=True, blank=True, related_name="obligations")` | Optional service asset link. |
| `title` | `CharField(max_length=255)` | Obligation name / commitment. |
| `obligation_type` | `CharField(max_length=40, choices=OBLIGATION_TYPE_CHOICES, default="sla_uptime")` | Indexed. Longest value = 20 chars. |
| `target_metric` | `CharField(max_length=150)` | Benchmark target (e.g. `>= 99.9% Uptime`). |
| `due_date` | `DateField(null=True, blank=True)` | Commitment deadline. |
| `status` | `CharField(max_length=20, choices=OBLIGATION_STATUS_CHOICES, default="pending")` | Indexed. Longest value = 9 chars. |
| `fulfilled_at` | `DateTimeField(null=True, blank=True)` | Fulfillment timestamp. |
| `fulfillment_evidence` | `TextField(blank=True)` | Verification evidence / tickets. Required when fulfilled. |
| `penalty_terms` | `TextField(blank=True)` | Liquidated damages or credit formula. |
| `penalty_amount` | `DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])` | Assessed damages / credit amount. |
| `penalty_status` | `CharField(max_length=20, choices=PENALTY_STATUS_CHOICES, default="none")` | Penalty settlement status. |
| `assigned_to` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_contract_obligations")` | Assigned delivery owner. |

- `Meta.ordering = ["due_date", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_obl_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_obl_ten_status_idx")` (24 chars <= 30)
  - `Index(fields=["tenant", "obligation_type"], name="sales_obl_ten_type_idx")` (22 chars <= 30)
  - `Index(fields=["tenant", "contract"], name="sales_obl_ten_contract_idx")` (26 chars <= 30)
- `clean()`:
  - Multi-tenant checks for `contract`, `subscription`, and `assigned_to`.
  - When `subscription` is provided and has `contract`, assert `subscription.contract_id == self.contract_id`.
  - When `status == "fulfilled"`, require non-empty `fulfillment_evidence`.
  - When `penalty_status in ("assessed", "credited")`, require `penalty_amount > 0`.

---

## 2. Forms (`apps/sales/forms/ContractSubscriptionManagement/`)

All forms inherit from `apps.core.forms.TenantModelForm` (or `forms.Form` for action modals).

### 2.1 ModelForms
- `CustomerContractForm`:
  - `Meta.model = CustomerContract`
  - `Meta.fields = ["account", "title", "contract_type", "status", "owner", "currency", "total_contract_value", "annual_contract_value", "start_date", "end_date", "auto_renew", "renewal_term_months", "notice_period_days", "price_uplift_pct", "governing_law", "originating_quote", "originating_order", "template", "document", "special_terms", "redline_notes", "signoff_contact"]`
  - Excluded: `tenant`, `number`, `created_at`, `updated_at`, `signed_at`.
- `CustomerSubscriptionForm`:
  - `Meta.model = CustomerSubscription`
  - `Meta.fields = ["contract", "account", "subscription_name", "plan_code", "status", "pricing_model", "billing_cadence", "currency", "quantity", "unit_price", "start_date", "current_term_start", "current_term_end", "trial_ends_at", "auto_renew", "renewal_notice_days", "owner"]`
  - Excluded: `tenant`, `number`, `created_at`, `updated_at`, `mrr`, `paused_at`, `resumed_at`, `cancelled_at`, `cancellation_reason`, `renewal_quote`.
- `UsageMeterRecordForm`:
  - `Meta.model = UsageMeterRecord`
  - `Meta.fields = ["subscription", "meter_name", "unit_of_measure", "billing_period_start", "billing_period_end", "included_allowance", "reported_usage", "overage_unit_price", "status", "notes"]`
  - Excluded: `tenant`, `number`, `created_at`, `updated_at`, `billable_overage_units`, `overage_total_charge`, `invoiced_at`.
- `ContractObligationForm`:
  - `Meta.model = ContractObligation`
  - `Meta.fields = ["contract", "subscription", "title", "obligation_type", "target_metric", "due_date", "status", "penalty_terms", "penalty_amount", "penalty_status", "assigned_to", "fulfillment_evidence"]`
  - Excluded: `tenant`, `number`, `created_at`, `updated_at`, `fulfilled_at`.

### 2.2 Filter Forms
- `CustomerContractFilterForm`: `q`, `contract_type`, `status`, `owner`, `account`.
- `CustomerSubscriptionFilterForm`: `q`, `status`, `pricing_model`, `billing_cadence`, `account`.
- `UsageMeterRecordFilterForm`: `q`, `subscription`, `status`, `meter_name`.
- `ContractObligationFilterForm`: `q`, `obligation_type`, `status`, `contract`, `assigned_to`.

### 2.3 Action Forms
- `SubscriptionPauseForm`: `notes`.
- `SubscriptionCancelForm`: `cancellation_reason` (required).
- `SubscriptionUpgradeForm`: `quantity`, `unit_price`.
- `ObligationFulfillForm`: `fulfillment_evidence` (required).
- `ObligationBreachForm`: `penalty_amount` (required), `penalty_status`, `notes`.

---

## 3. URL Names & Routes (`apps/sales/urls/ContractSubscriptionManagement/`)

All URL routes are namespaced under `sales:`.

```python
# Boards & Consoles (Literal routes first - first-match-wins)
path("contract-subscription-workspace/", views.contract_subscription_workspace, name="contract_subscription_workspace"),
path("renewal-automation-dashboard/", views.renewal_automation_dashboard, name="renewal_automation_dashboard"),

# Customer Contracts
path("contracts/", views.customer_contract_list, name="customer_contract_list"),
path("contracts/create/", views.customer_contract_create, name="customer_contract_create"),
path("contracts/<int:pk>/", views.customer_contract_detail, name="customer_contract_detail"),
path("contracts/<int:pk>/edit/", views.customer_contract_edit, name="customer_contract_edit"),
path("contracts/<int:pk>/delete/", views.customer_contract_delete, name="customer_contract_delete"),
path("contracts/<int:pk>/activate/", views.customer_contract_activate, name="customer_contract_activate"),
path("contracts/<int:pk>/generate-renewal-quote/", views.customer_contract_generate_renewal_quote, name="customer_contract_generate_renewal_quote"),
path("contracts/<int:pk>/execute-auto-renew/", views.customer_contract_execute_auto_renew, name="customer_contract_execute_auto_renew"),

# Customer Subscriptions
path("subscriptions/", views.customer_subscription_list, name="customer_subscription_list"),
path("subscriptions/create/", views.customer_subscription_create, name="customer_subscription_create"),
path("subscriptions/<int:pk>/", views.customer_subscription_detail, name="customer_subscription_detail"),
path("subscriptions/<int:pk>/edit/", views.customer_subscription_edit, name="customer_subscription_edit"),
path("subscriptions/<int:pk>/delete/", views.customer_subscription_delete, name="customer_subscription_delete"),
path("subscriptions/<int:pk>/pause/", views.customer_subscription_pause, name="customer_subscription_pause"),
path("subscriptions/<int:pk>/resume/", views.customer_subscription_resume, name="customer_subscription_resume"),
path("subscriptions/<int:pk>/cancel/", views.customer_subscription_cancel, name="customer_subscription_cancel"),
path("subscriptions/<int:pk>/upgrade/", views.customer_subscription_upgrade, name="customer_subscription_upgrade"),

# Usage Meter Records
path("usage-meters/", views.usage_meter_record_list, name="usage_meter_record_list"),
path("usage-meters/create/", views.usage_meter_record_create, name="usage_meter_record_create"),
path("usage-meters/<int:pk>/", views.usage_meter_record_detail, name="usage_meter_record_detail"),
path("usage-meters/<int:pk>/edit/", views.usage_meter_record_edit, name="usage_meter_record_edit"),
path("usage-meters/<int:pk>/delete/", views.usage_meter_record_delete, name="usage_meter_record_delete"),
path("usage-meters/<int:pk>/calculate/", views.usage_meter_record_calculate, name="usage_meter_record_calculate"),
path("usage-meters/<int:pk>/invoice/", views.usage_meter_record_invoice, name="usage_meter_record_invoice"),

# Contract Obligations
path("obligations/", views.contract_obligation_list, name="contract_obligation_list"),
path("obligations/create/", views.contract_obligation_create, name="contract_obligation_create"),
path("obligations/<int:pk>/", views.contract_obligation_detail, name="contract_obligation_detail"),
path("obligations/<int:pk>/edit/", views.contract_obligation_edit, name="contract_obligation_edit"),
path("obligations/<int:pk>/delete/", views.contract_obligation_delete, name="contract_obligation_delete"),
path("obligations/<int:pk>/fulfill/", views.contract_obligation_fulfill, name="contract_obligation_fulfill"),
path("obligations/<int:pk>/breach/", views.contract_obligation_breach, name="contract_obligation_breach"),
```

---

## 4. Context Keys (MANDATORY PINNING — L7)

Every template context variable is explicitly pinned below.

### 4.1 List Views
- `customer_contract_list`:
  - `contracts` (list of contracts / page items)
  - `page_obj` (Django paginator Page)
  - `filter_form` (bound or unbound filter form)
  - `status_choices` (`CONTRACT_STATUS_CHOICES`)
  - `type_choices` (`CONTRACT_TYPE_CHOICES`)
  - `total_tcv` (sum of active contract TCV)
  - `active_count` (count of active contracts)
- `customer_subscription_list`:
  - `subscriptions` (list of subscriptions / page items)
  - `page_obj`
  - `filter_form`
  - `status_choices` (`SUBSCRIPTION_STATUS_CHOICES`)
  - `pricing_model_choices` (`PRICING_MODEL_CHOICES`)
  - `cadence_choices` (`BILLING_CADENCE_CHOICES`)
  - `total_mrr` (sum of normalized active MRR)
  - `active_count` (count of active subscriptions)
- `usage_meter_record_list`:
  - `usage_records` (list of meter records / page items)
  - `page_obj`
  - `filter_form`
  - `status_choices` (`USAGE_STATUS_CHOICES`)
  - `total_overage_charge` (sum of unbilled/calculated overage charges)
  - `unbilled_count` (count of calculated records)
- `contract_obligation_list`:
  - `obligations` (list of obligations / page items)
  - `page_obj`
  - `filter_form`
  - `status_choices` (`OBLIGATION_STATUS_CHOICES`)
  - `type_choices` (`OBLIGATION_TYPE_CHOICES`)
  - `penalty_exposure` (sum of assessed penalties)
  - `breached_count` (count of breached obligations)

### 4.2 Detail Views (MUST provide both specific name AND `obj` alias)
- `customer_contract_detail`:
  - `contract` (and alias `obj = contract`)
  - `subscriptions` (related `CustomerSubscription` queryset)
  - `obligations` (related `ContractObligation` queryset)
- `customer_subscription_detail`:
  - `subscription` (and alias `obj = subscription`)
  - `usage_records` (related `UsageMeterRecord` queryset)
  - `obligations` (related `ContractObligation` queryset)
- `usage_meter_record_detail`:
  - `usage_record` (and alias `obj = usage_record`)
- `contract_obligation_detail`:
  - `obligation` (and alias `obj = obligation`)

### 4.3 Form Views (Create / Edit)
- `customer_contract_form`:
  - `form`
  - `contract` (instance or None on create)
  - `obj = contract` (alias)
  - `is_edit` (bool)
- `customer_subscription_form`:
  - `form`
  - `subscription` (instance or None on create)
  - `obj = subscription` (alias)
  - `is_edit` (bool)
- `usage_meter_record_form`:
  - `form`
  - `usage_record` (instance or None on create)
  - `obj = usage_record` (alias)
  - `is_edit` (bool)
- `contract_obligation_form`:
  - `form`
  - `obligation` (instance or None on create)
  - `obj = obligation` (alias)
  - `is_edit` (bool)

### 4.4 Consoles Context
- `contract_subscription_workspace`:
  - `active_contracts_count`
  - `total_tcv`
  - `total_arr`
  - `total_mrr`
  - `expiring_30_count`
  - `expiring_60_count`
  - `unbilled_overages_total`
  - `sla_compliance_rate`
  - `urgent_contracts` (queryset)
  - `urgent_subscriptions` (queryset)
  - `at_risk_obligations` (queryset)
- `renewal_automation_dashboard`:
  - `upcoming_renewals` (queryset)
  - `auto_renew_candidates` (queryset)
  - `expiring_30_days` (count)
  - `expiring_60_days` (count)
  - `expiring_90_days` (count)
  - `projected_uplift_value` (sum)
  - `generated_quotes_count` (count)

---

## 5. Templates — Exact Folder Structure (All Lowercase on Disk)

```
templates/sales/contractsubscriptionmanagement/
├── customercontract/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── customersubscription/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── usagemeterrecord/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── contractobligation/
│   ├── list.html
│   ├── detail.html
│   └── form.html
└── boards/
    ├── contract_subscription_workspace.html
    └── renewal_automation_dashboard.html
```

---

## 6. Navigation Wire-Up: `LIVE_LINKS["8.15"]`

In `apps/core/navigation.py`:
```python
    "8.15": {
        # OWNERSHIP RULING (L36/L37)
        # Reuses core.Party for customer/client account and counterparty;
        # reuses core.Document (DOC-) for executed agreement PDFs and redline attachments;
        # reuses accounting.Currency for multi-currency contract values, MRR, and overage rates;
        # reuses accounts.User for contract owners, CSMs, and obligation assignees;
        # reuses sales.CPQQuote (CPQ-) for originating proposals and automated renewal quotes;
        # reuses scm.SalesOrder (SO-) for originating customer sales orders;
        # reuses crm.DocTemplate (TPL-) for standard contract authoring templates.
        # Zero duplicate customer/company, quote, order, user, currency, document, or platform subscription tables declared.
        "Contract Authoring & Redlining": "sales:customer_contract_list",
        "Subscription Lifecycle": "sales:customer_subscription_list",
        "Renewal Automation": "sales:renewal_automation_dashboard",
        "Usage-Based Billing": "sales:usage_meter_record_list",
        "Contract Compliance & Obligations": "sales:contract_obligation_list",
        # Extra live leaves
        "Customer Contracts": "sales:customer_contract_list",
        "Customer Subscriptions": "sales:customer_subscription_list",
        "Renewal Automation Dashboard": "sales:renewal_automation_dashboard",
        "Usage Meter Records": "sales:usage_meter_record_list",
        "Contract Obligations": "sales:contract_obligation_list",
        "Contract & Subscription Workspace": "sales:contract_subscription_workspace",
    },
```

---

## 7. Seeder Plan (`apps/sales/management/commands/seed_sales.py`)

Dedicated helper `_seed_contract_subscription_management(self, tenant, user)`:
- Guard: `if CustomerContract.objects.filter(tenant=tenant).exists(): return`
- ACME Corp & Globex:
  - 3 `CustomerContract` rows:
    - Enterprise Software Agreement (Active, annual auto-renew, 5% uplift, linked to ACME customer Party and originating CPQQuote)
    - Master Services Agreement (MSA, Active, evergreen)
    - Pilot Evaluation Agreement (Draft/Negotiating with redline notes)
  - 3 `CustomerSubscription` rows:
    - Enterprise SaaS Cloud Subscription (Annual, 50 seats, per_seat model)
    - Premium Support & SLA Add-on (Monthly, flat_fee model)
    - API Platform Metered Plan (Monthly, usage_metered model)
  - 3 `UsageMeterRecord` rows:
    - API Invocations Meter (Calculated with overage charges)
    - High-Performance Compute Hours (Metering in progress)
    - Encrypted Storage GB (Invoiced)
  - 3 `ContractObligation` rows:
    - Production Cloud 99.9% Uptime SLA (sla_uptime, Fulfilled with monitoring report evidence)
    - Priority-1 1-Hour Response SLA (sla_response, Pending)
    - Annual SOC2 Audit Deliverable (reporting_compliance, Pending)
