# Contract — Sub-module 9.17: B2B & Wholesale Commerce (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.17 B2B & Wholesale Commerce · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-02 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0032_...`
- **Package Layout:** `B2bWholesale/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/b2b_wholesale/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `B2bCompanyAccount` (`apps/ecommerce/models/B2bWholesale/B2bCompanyAccounts.py`)
- **Table:** `ecommerce_b2b_company_account`
- **Number Prefix:** `EBCA` (`EBCA-00001`)
- **CHOICES:**
  - `PAYMENT_TERMS_CHOICES = [('prepaid', 'Prepaid / Advance Payment'), ('due_on_receipt', 'Due on Receipt'), ('net_15', 'Net 15 Days'), ('net_30', 'Net 30 Days'), ('net_45', 'Net 45 Days'), ('net_60', 'Net 60 Days'), ('net_90', 'Net 90 Days')]`
  - `CREDIT_STATUS_CHOICES = [('good_standing', 'Good Standing'), ('warning', 'Credit Warning'), ('exceeded_limit', 'Exceeded Limit'), ('suspended', 'Suspended'), ('revoked', 'Revoked')]`
  - `PUNCHOUT_PROTOCOL_CHOICES = [('none', 'No Punchout Configured'), ('cxml', 'cXML (Ariba / Coupa / Jaggaer)'), ('oci', 'OCI (SAP / Open Catalog Interface)')]`
  - `STATUS_CHOICES = [('pending_review', 'Pending Review'), ('active', 'Active'), ('on_hold', 'On Hold'), ('suspended', 'Suspended'), ('closed', 'Closed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `company_party`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='b2b_company_accounts')`
  - `primary_contact`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='managed_b2b_companies')`
  - `preferred_currency`: `ForeignKey('accounting.Currency', on_delete=PROTECT, related_name='b2b_companies')`
  - `company_name`: `CharField(max_length=255, help_text="Corporate entity commercial trading name")`
  - `company_tax_id`: `CharField(max_length=64, blank=True, default="", help_text="Federal Tax ID, EIN, or VAT registration number")`
  - `business_registration_number`: `CharField(max_length=64, blank=True, default="", help_text="State or national registrar business number")`
  - `website`: `URLField(blank=True, default="")`
  - `industry`: `CharField(max_length=100, blank=True, default="", help_text="Sector or industry classification (e.g. Manufacturing, Healthcare)")`
  - `credit_limit`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Approved commercial credit line limit")`
  - `available_credit`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Current remaining available credit balance")`
  - `payment_terms`: `CharField(max_length=25, choices=PAYMENT_TERMS_CHOICES, default="due_on_receipt")`
  - `credit_status`: `CharField(max_length=25, choices=CREDIT_STATUS_CHOICES, default="good_standing")`
  - `requires_po_number`: `BooleanField(default=True, help_text="Enforce customer Purchase Order (PO) number entry on checkout")`
  - `requires_order_approval`: `BooleanField(default=False, help_text="Require supervisor sign-off on orders exceeding threshold")`
  - `approval_threshold_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Orders exceeding this sum trigger mandatory approval")`
  - `default_approver`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='approver_b2b_companies')`
  - `punchout_enabled`: `BooleanField(default=False, help_text="Enable e-procurement PunchOut catalog integration")`
  - `punchout_protocol`: `CharField(max_length=20, choices=PUNCHOUT_PROTOCOL_CHOICES, default="none")`
  - `punchout_identity`: `CharField(max_length=128, blank=True, default="", help_text="cXML Buyer Identity / Network ID (e.g. DUNS or Network ID)")`
  - `punchout_shared_secret`: `CharField(max_length=128, blank=True, default="", help_text="Shared authentication credential token")`
  - `punchout_return_url`: `URLField(blank=True, default="", help_text="Procurement system return URL for punchback cart payload")`
  - `wholesale_discount_percent`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Default wholesale catalog discount percentage")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="pending_review")`
  - `notes`: `TextField(blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ebca_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ebca_ten_stat')`
  - `Index(fields=['tenant', 'credit_status'], name='idx_ebca_ten_cred')`
  - `Index(fields=['tenant', 'company_party'], name='idx_ebca_ten_party')`
- **Ordering:** `['-created_at']`
- **Key Methods:** `has_available_credit(amount)`, `calculate_discounted_price(price)`

---

### 1.2 `B2bCompanyUser` (`apps/ecommerce/models/B2bWholesale/B2bCompanyUsers.py`)
- **Table:** `ecommerce_b2b_company_user`
- **Number Prefix:** `EBCU` (`EBCU-00001`)
- **CHOICES:**
  - `ROLE_CHOICES = [('company_admin', 'Company Administrator'), ('procurement_manager', 'Procurement Manager'), ('buyer', 'Authorized Buyer'), ('approver', 'Order Approver'), ('finance_auditor', 'Finance / Auditor')]`
  - `STATUS_CHOICES = [('active', 'Active'), ('invited', 'Invitation Pending'), ('suspended', 'Suspended'), ('inactive', 'Inactive')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `company`: `ForeignKey('ecommerce.B2bCompanyAccount', on_delete=CASCADE, related_name='company_users')`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='b2b_user_memberships')`
  - `party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=SET_NULL, related_name='b2b_company_roles')`
  - `role`: `CharField(max_length=30, choices=ROLE_CHOICES, default="buyer")`
  - `job_title`: `CharField(max_length=100, blank=True, default="")`
  - `department`: `CharField(max_length=100, blank=True, default="")`
  - `order_spend_limit`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Maximum per-order spend without approval (0 for unlimited)")`
  - `monthly_spend_limit`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Maximum monthly budget (0 for unlimited)")`
  - `monthly_spend_current`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Current calendar month spend accumulated")`
  - `can_place_orders`: `BooleanField(default=True)`
  - `can_request_quotes`: `BooleanField(default=True)`
  - `can_view_invoices`: `BooleanField(default=False)`
  - `can_manage_users`: `BooleanField(default=False)`
  - `can_approve_orders`: `BooleanField(default=False)`
  - `reports_to_approver`: `ForeignKey('self', null=True, blank=True, on_delete=SET_NULL, related_name='subordinate_buyers')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ebcu_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'company', 'user'], name='ecommerce_ebcu_ten_co_usr_uniq')`
  - `Index(fields=['tenant', 'role'], name='idx_ebcu_ten_role')`
  - `Index(fields=['tenant', 'status'], name='idx_ebcu_ten_stat')`
- **Ordering:** `['company', 'user__username']`
- **Key Methods:** `can_spend(amount)`

---

### 1.3 `B2bQuoteRequest` (`apps/ecommerce/models/B2bWholesale/B2bQuoteRequests.py`)
- **Table:** `ecommerce_b2b_quote_request`
- **Number Prefix:** `EBQR` (`EBQR-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft (Preparing RFQ)'), ('submitted', 'Submitted / Pending Review'), ('under_review', 'Under Review'), ('quoted', 'Quoted / Offer Sent'), ('buyer_review', 'Buyer Review'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('expired', 'Expired'), ('converted_to_order', 'Converted to Order')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `company`: `ForeignKey('ecommerce.B2bCompanyAccount', on_delete=CASCADE, related_name='quote_requests')`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='requested_b2b_quotes')`
  - `assigned_sales_rep`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='assigned_b2b_quotes')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=PROTECT, related_name='b2b_quote_requests')`
  - `converted_order`: `ForeignKey('ecommerce.EcommerceOrder', null=True, blank=True, on_delete=SET_NULL, related_name='source_b2b_quotes')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft")`
  - `target_budget`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `original_subtotal`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `quoted_discount_percent`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `quoted_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `tax_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `shipping_estimate`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `target_delivery_date`: `DateField(null=True, blank=True)`
  - `valid_until`: `DateTimeField(null=True, blank=True)`
  - `submitted_at`: `DateTimeField(null=True, blank=True)`
  - `quoted_at`: `DateTimeField(null=True, blank=True)`
  - `accepted_at`: `DateTimeField(null=True, blank=True)`
  - `line_items_data`: `JSONField(default=list, blank=True, help_text="List of items: product_id, sku, name, requested_qty, requested_unit_price, quoted_unit_price, line_total, notes")`
  - `buyer_notes`: `TextField(blank=True, default="")`
  - `merchant_notes`: `TextField(blank=True, default="", help_text="Internal staff notes")`
  - `rejection_reason`: `TextField(blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ebqr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ebqr_ten_stat')`
  - `Index(fields=['tenant', 'company'], name='idx_ebqr_ten_co')`
  - `Index(fields=['tenant', 'valid_until'], name='idx_ebqr_ten_valid')`
- **Ordering:** `['-created_at']`
- **Key Methods:** `recalculate_totals()`, `convert_to_order(tenant, user)`

---

### 1.4 `B2bQuickOrderTemplate` (`apps/ecommerce/models/B2bWholesale/B2bQuickOrderTemplates.py`)
- **Table:** `ecommerce_b2b_quick_order_template`
- **Number Prefix:** `EBQT` (`EBQT-00001`)
- **CHOICES:**
  - `SCOPE_CHOICES = [('private', 'Private (Author Only)'), ('company_shared', 'Company-Wide Shared')]`
  - `CADENCE_CHOICES = [('ad_hoc', 'Ad-Hoc / As Needed'), ('weekly', 'Weekly Replenishment'), ('bi_weekly', 'Bi-Weekly'), ('monthly', 'Monthly Replenishment'), ('quarterly', 'Quarterly')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `company`: `ForeignKey('ecommerce.B2bCompanyAccount', on_delete=CASCADE, related_name='quick_order_templates')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='created_quick_order_templates')`
  - `name`: `CharField(max_length=200, help_text="Template label (e.g. Weekly Warehouse Consumables)")`
  - `description`: `TextField(blank=True, default="")`
  - `scope`: `CharField(max_length=20, choices=SCOPE_CHOICES, default="company_shared")`
  - `cadence`: `CharField(max_length=20, choices=CADENCE_CHOICES, default="ad_hoc")`
  - `items_data`: `JSONField(default=list, blank=True, help_text="List of items: product_id, sku, name, default_quantity, uom, notes")`
  - `total_items_count`: `PositiveIntegerField(default=0)`
  - `times_ordered`: `PositiveIntegerField(default=0)`
  - `last_ordered_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ebqt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'company'], name='idx_ebqt_ten_co')`
  - `Index(fields=['tenant', 'scope'], name='idx_ebqt_ten_scope')`
  - `Index(fields=['tenant', 'is_active'], name='idx_ebqt_ten_act')`
- **Ordering:** `['company', 'name']`
- **Key Methods:** `update_items_count()`

---

## 2. Forms Contract & Exclusions

All ModelForms live in `apps/ecommerce/forms/B2bWholesale/` and inherit shared Tailwind styling via `FormStyleMixin` / `forms._common`.

### 2.1 `B2bCompanyAccountForm` (`apps/ecommerce/forms/B2bWholesale/B2bCompanyAccounts.py`)
- **Model:** `B2bCompanyAccount`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at', 'available_credit']`
- **FK Querysets:**
  - `company_party`: `Party.objects.filter(tenant=request.tenant)`
  - `primary_contact`: `User.objects.filter(is_active=True)`
  - `preferred_currency`: `Currency.objects.filter(tenant=request.tenant)`
  - `default_approver`: `User.objects.filter(is_active=True)`
- **Widgets:**
  - `notes`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea'})`

### 2.2 `B2bCompanyUserForm` (`apps/ecommerce/forms/B2bWholesale/B2bCompanyUsers.py`)
- **Model:** `B2bCompanyUser`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at', 'monthly_spend_current']`
- **FK Querysets:**
  - `company`: `B2bCompanyAccount.objects.filter(tenant=request.tenant)`
  - `user`: `User.objects.filter(is_active=True)`
  - `party`: `Party.objects.filter(tenant=request.tenant)`
  - `reports_to_approver`: `B2bCompanyUser.objects.filter(tenant=request.tenant, can_approve_orders=True)`

### 2.3 `B2bQuoteRequestForm` (`apps/ecommerce/forms/B2bWholesale/B2bQuoteRequests.py`)
- **Model:** `B2bQuoteRequest`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at', 'submitted_at', 'quoted_at', 'accepted_at', 'converted_order']`
- **FK Querysets:**
  - `company`: `B2bCompanyAccount.objects.filter(tenant=request.tenant)`
  - `requested_by`: `User.objects.filter(is_active=True)`
  - `assigned_sales_rep`: `User.objects.filter(is_active=True)`
  - `currency`: `Currency.objects.filter(tenant=request.tenant)`
- **Widgets:**
  - `target_delivery_date`: `DateInput(attrs={'type': 'date', 'class': 'form-input'})`
  - `valid_until`: `DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})`
  - `buyer_notes`, `merchant_notes`, `rejection_reason`: `Textarea(attrs={'rows': 2, 'class': 'form-textarea'})`

### 2.4 `B2bQuickOrderTemplateForm` (`apps/ecommerce/forms/B2bWholesale/B2bQuickOrderTemplates.py`)
- **Model:** `B2bQuickOrderTemplate`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at', 'total_items_count', 'times_ordered', 'last_ordered_at']`
- **FK Querysets:**
  - `company`: `B2bCompanyAccount.objects.filter(tenant=request.tenant)`
  - `created_by`: `User.objects.filter(is_active=True)`
- **Widgets:**
  - `description`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea'})`

---

## 3. URLs & View Context Keys Contract (L7 Pinned)

All views are function-based, decorated with `@login_required` (and `@tenant_admin_required` for administrative writes), and tenant-scoped via `request.tenant`.

### 3.1 URL Patterns (`apps/ecommerce/urls/B2bWholesale/`)
Concatenated in `apps/ecommerce/urls/__init__.py`:
- `path('b2b/hub/', views.b2b_wholesale_hub, name='b2b_wholesale_hub')`
- `path('b2b/companies/', views.b2bcompanyaccount_list, name='b2bcompanyaccount_list')`
- `path('b2b/companies/new/', views.b2bcompanyaccount_create, name='b2bcompanyaccount_create')`
- `path('b2b/companies/<int:pk>/', views.b2bcompanyaccount_detail, name='b2bcompanyaccount_detail')`
- `path('b2b/companies/<int:pk>/edit/', views.b2bcompanyaccount_edit, name='b2bcompanyaccount_edit')`
- `path('b2b/companies/<int:pk>/delete/', views.b2bcompanyaccount_delete, name='b2bcompanyaccount_delete')`
- `path('b2b/companies/<int:pk>/punchout-test/', views.b2bcompanyaccount_punchout_test, name='b2bcompanyaccount_punchout_test')`
- `path('b2b/users/', views.b2bcompanyuser_list, name='b2bcompanyuser_list')`
- `path('b2b/users/new/', views.b2bcompanyuser_create, name='b2bcompanyuser_create')`
- `path('b2b/users/<int:pk>/', views.b2bcompanyuser_detail, name='b2bcompanyuser_detail')`
- `path('b2b/users/<int:pk>/edit/', views.b2bcompanyuser_edit, name='b2bcompanyuser_edit')`
- `path('b2b/users/<int:pk>/delete/', views.b2bcompanyuser_delete, name='b2bcompanyuser_delete')`
- `path('b2b/quotes/', views.b2bquoterequest_list, name='b2bquoterequest_list')`
- `path('b2b/quotes/new/', views.b2bquoterequest_create, name='b2bquoterequest_create')`
- `path('b2b/quotes/<int:pk>/', views.b2bquoterequest_detail, name='b2bquoterequest_detail')`
- `path('b2b/quotes/<int:pk>/edit/', views.b2bquoterequest_edit, name='b2bquoterequest_edit')`
- `path('b2b/quotes/<int:pk>/delete/', views.b2bquoterequest_delete, name='b2bquoterequest_delete')`
- `path('b2b/quotes/<int:pk>/submit/', views.b2bquoterequest_submit, name='b2bquoterequest_submit')`
- `path('b2b/quotes/<int:pk>/quote/', views.b2bquoterequest_quote, name='b2bquoterequest_quote')`
- `path('b2b/quotes/<int:pk>/accept/', views.b2bquoterequest_accept, name='b2bquoterequest_accept')`
- `path('b2b/quotes/<int:pk>/reject/', views.b2bquoterequest_reject, name='b2bquoterequest_reject')`
- `path('b2b/quotes/<int:pk>/convert-order/', views.b2bquoterequest_convert_order, name='b2bquoterequest_convert_order')`
- `path('b2b/templates/', views.b2bquickordertemplate_list, name='b2bquickordertemplate_list')`
- `path('b2b/templates/new/', views.b2bquickordertemplate_create, name='b2bquickordertemplate_create')`
- `path('b2b/templates/<int:pk>/', views.b2bquickordertemplate_detail, name='b2bquickordertemplate_detail')`
- `path('b2b/templates/<int:pk>/edit/', views.b2bquickordertemplate_edit, name='b2bquickordertemplate_edit')`
- `path('b2b/templates/<int:pk>/delete/', views.b2bquickordertemplate_delete, name='b2bquickordertemplate_delete')`
- `path('b2b/quick-order/', views.b2b_quick_order_matrix, name='b2b_quick_order_matrix')`

### 3.2 View Context Keys Contract
1. **`b2b_wholesale_hub`**:
   - `total_companies_count`: integer
   - `active_companies_count`: integer
   - `pending_reviews_count`: integer
   - `total_credit_granted`: Decimal
   - `available_credit_sum`: Decimal
   - `open_rfqs_count`: integer
   - `active_templates_count`: integer
   - `recent_companies`: queryset of `B2bCompanyAccount`
   - `recent_quotes`: queryset of `B2bQuoteRequest`

2. **`B2bCompanyAccount` Views**:
   - `b2bcompanyaccount_list`: `company_accounts` (paginated), `status_choices`, `credit_status_choices`, `payment_terms_choices`, `search_query`, `selected_status`, `selected_credit_status`
   - `b2bcompanyaccount_detail`: `company_account`, `company_users`, `quote_requests`, `quick_order_templates`
   - `b2bcompanyaccount_create` / `edit`: `form`, `company_account` (edit mode only), `title`
   - `b2bcompanyaccount_delete`: `company_account`
   - `b2bcompanyaccount_punchout_test`: `company_account`, `test_payload`, `cxml_response`

3. **`B2bCompanyUser` Views**:
   - `b2bcompanyuser_list`: `company_users` (paginated), `role_choices`, `status_choices`, `companies`, `search_query`, `selected_role`, `selected_status`, `selected_company`
   - `b2bcompanyuser_detail`: `company_user`
   - `b2bcompanyuser_create` / `edit`: `form`, `company_user` (edit mode only), `title`
   - `b2bcompanyuser_delete`: `company_user`

4. **`B2bQuoteRequest` Views**:
   - `b2bquoterequest_list`: `quote_requests` (paginated), `status_choices`, `companies`, `search_query`, `selected_status`, `selected_company`
   - `b2bquoterequest_detail`: `quote_request`, `line_items`
   - `b2bquoterequest_create` / `edit`: `form`, `quote_request` (edit mode only), `title`, `products`
   - `b2bquoterequest_delete`: `quote_request`

5. **`B2bQuickOrderTemplate` Views**:
   - `b2bquickordertemplate_list`: `quick_order_templates` (paginated), `scope_choices`, `cadence_choices`, `companies`, `search_query`, `selected_scope`, `selected_cadence`, `selected_company`
   - `b2bquickordertemplate_detail`: `template_obj`, `items_data`
   - `b2bquickordertemplate_create` / `edit`: `form`, `template_obj` (edit mode only), `title`, `products`
   - `b2bquickordertemplate_delete`: `template_obj`
   - `b2b_quick_order_matrix`: `companies`, `products`, `parsed_items`, `csv_errors`, `success_message`

---

## 4. Templates Contract

Follows mandatory `templates/ecommerce/b2b_wholesale/<entity>/{list,detail,form}.html` structure + `b2b_wholesale_hub.html`.
- Uses `theme.css` colour-named badge classes exclusively (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`).
- Filters preserve query parameters via `request.GET` and compare PK filters via `|stringformat:"d"`.
- All list templates feature empty-states, action buttons, and pagination controls.

---

## 5. Seed Data Contract

`apps/ecommerce/management/commands/seed_ecommerce.py` extended with idempotent wholesale records:
- 2 B2B Company Accounts:
  - "Acme Industrial Supplies Ltd" (Credit limit $100,000, Net 30, punchout cXML enabled, active)
  - "Global Logistics Wholesale Corp" (Credit limit $250,000, Net 60, pending review)
- 3 B2B Company Users:
  - Corporate Admin, Procurement Manager, and Authorized Buyer with distinct spending limits.
- 2 B2B Quote Requests (RFQs):
  - 1 submitted bulk order RFQ with line items JSON.
  - 1 quoted offer ready for customer review and order conversion.
- 2 B2B Quick Order Templates:
  - 1 Company-wide weekly replenishment kit.
  - 1 Private ad-hoc supplies template.
