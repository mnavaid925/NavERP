# Contract — Sub-module 9.14: Customer Service & Support (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.14 Customer Service & Support · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-31 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0019_...`
- **Package Layout:** `CustomerSupport/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/customer_support/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `CustomerSupportTicket` (`apps/ecommerce/models/CustomerSupport/CustomerSupportTickets.py`)
- **Table:** `ecommerce_customer_support_ticket`
- **Number Prefix:** `ESTK` (`ESTK-00001`)
- **CHOICES:**
  - `CHANNEL_CHOICES = [('email', 'Email'), ('chat', 'Live Chat'), ('web_form', 'Web Contact Form'), ('portal', 'Customer Portal'), ('marketplace', 'Marketplace Message'), ('phone', 'Phone / Voice')]`
  - `CATEGORY_CHOICES = [('order_tracking_wismo', 'Order Tracking (WISMO)'), ('return_refund', 'Returns & Refunds'), ('damaged_defective', 'Damaged or Defective Item'), ('shipping_delivery', 'Shipping & Delivery Issue'), ('product_inquiry', 'Pre-Purchase Product Inquiry'), ('payment_billing', 'Payment & Billing'), ('account_access', 'Customer Account Access'), ('general', 'General Inquiries')]`
  - `PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')]`
  - `STATUS_CHOICES = [('new', 'New / Unassigned'), ('open', 'Open / In Progress'), ('pending_customer', 'Pending Customer Reply'), ('waiting_carrier', 'Waiting on Carrier / Warehouse'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('cancelled', 'Cancelled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='support_tickets')`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=SET_NULL, null=True, blank=True, related_name='support_tickets')`
  - `assigned_agent`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='assigned_ecommerce_tickets')`
  - `subject`: `CharField(max_length=255, help_text="Short summary of customer issue")`
  - `customer_name`: `CharField(max_length=150, help_text="Name of shopper or guest")`
  - `customer_email`: `EmailField(help_text="Shopper contact email")`
  - `customer_phone`: `CharField(max_length=32, blank=True)`
  - `channel`: `CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')`
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')`
  - `priority`: `CharField(max_length=15, choices=PRIORITY_CHOICES, default='medium')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='new')`
  - `initial_message`: `TextField(help_text="Customer inquiry body")`
  - `resolution_summary`: `TextField(blank=True, help_text="Agent resolution notes provided to customer")`
  - `internal_notes`: `TextField(blank=True, help_text="Private internal staff-only notes")`
  - `sla_first_response_due_at`: `DateTimeField(null=True, blank=True)`
  - `sla_resolution_due_at`: `DateTimeField(null=True, blank=True)`
  - `first_responded_at`: `DateTimeField(null=True, blank=True)`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `is_sla_breached`: `BooleanField(default=False)`
  - `is_bot_handled`: `BooleanField(default=False, help_text="Handled by conversational bot")`
  - `bot_handoff_reason`: `CharField(max_length=100, blank=True, help_text="Why bot transferred to human")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_estk_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'priority'], name='idx_estk_ten_stat_prio')`
  - `Index(fields=['tenant', 'assigned_agent', 'status'], name='idx_estk_ten_agent_stat')`
  - `Index(fields=['tenant', 'order'], name='idx_estk_ten_order')`
  - `Index(fields=['tenant', 'customer_email'], name='idx_estk_ten_cust_email')`

---

### 1.2 `KnowledgeBaseArticle` (`apps/ecommerce/models/CustomerSupport/KnowledgeBaseArticles.py`)
- **Table:** `ecommerce_knowledge_base_article`
- **Number Prefix:** `EKBA` (`EKBA-00001`)
- **CHOICES:**
  - `CATEGORY_CHOICES = [('shipping_delivery', 'Shipping & Delivery'), ('returns_refunds', 'Returns & Refunds'), ('ordering_payment', 'Ordering & Payment'), ('product_sizing', 'Product Specs & Sizing'), ('account_security', 'Account & Security'), ('troubleshooting', 'Troubleshooting & Care'), ('promotions', 'Promotions & Loyalty')]`
  - `STATUS_CHOICES = [('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')]`
  - `AUDIENCE_CHOICES = [('all_visitors', 'All Visitors'), ('registered_customers', 'Registered Customers Only'), ('b2b_wholesale', 'B2B Wholesale Accounts Only')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=255, help_text="Article headline")`
  - `slug`: `SlugField(max_length=255, help_text="SEO URL slug")`
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default='shipping_delivery')`
  - `summary`: `TextField(max_length=500, help_text="Brief summary snippet for search results")`
  - `content`: `TextField(help_text="Full article / FAQ content")`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default='draft')`
  - `target_audience`: `CharField(max_length=25, choices=AUDIENCE_CHOICES, default='all_visitors')`
  - `is_featured`: `BooleanField(default=False, help_text="Pin to top of knowledge base")`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `helpful_votes`: `PositiveIntegerField(default=0)`
  - `unhelpful_votes`: `PositiveIntegerField(default=0)`
  - `keywords`: `CharField(max_length=255, blank=True, help_text="Comma-separated keywords for autocomplete")`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='authored_ecommerce_articles')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ekba_tenant_num_uniq')`
  - `Index(fields=['tenant', 'category', 'status'], name='idx_ekba_ten_cat_stat')`
  - `Index(fields=['tenant', 'is_featured', 'status'], name='idx_ekba_ten_feat_stat')`
  - `Index(fields=['tenant', 'slug'], name='idx_ekba_ten_slug')`

---

### 1.3 `OrderIssueClaim` (`apps/ecommerce/models/CustomerSupport/OrderIssueClaims.py`)
- **Table:** `ecommerce_order_issue_claim`
- **Number Prefix:** `ECLM` (`ECLM-00001`)
- **CHOICES:**
  - `CLAIM_TYPE_CHOICES = [('damaged_item', 'Damaged Item in Transit'), ('lost_in_transit', 'Lost in Transit / Package Not Received'), ('wrong_item', 'Wrong Item Received'), ('missing_parts', 'Missing Item / Partial Shipment'), ('defective_product', 'Defective / Malfunctioning Product'), ('late_delivery', 'Late Delivery SLA Breach')]`
  - `STATUS_CHOICES = [('submitted', 'Submitted by Customer'), ('under_review', 'Under Staff Review'), ('carrier_investigation', 'Carrier Investigation Pending'), ('approved', 'Claim Approved'), ('rejected', 'Claim Rejected'), ('completed', 'Resolution Completed')]`
  - `RESOLUTION_CHOICES = [('pending', 'Pending Review'), ('replacement_reship', 'Reship Replacement Item'), ('full_refund', 'Full Refund to Original Payment'), ('partial_refund', 'Partial Refund Adjustment'), ('store_credit', 'Store Credit / Gift Voucher'), ('repair', 'Product Repair / Service'), ('rejected', 'No Action / Claim Denied')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=CASCADE, related_name='issue_claims')`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='order_claims')`
  - `ticket`: `ForeignKey('ecommerce.CustomerSupportTicket', on_delete=SET_NULL, null=True, blank=True, related_name='order_claims')`
  - `claim_type`: `CharField(max_length=30, choices=CLAIM_TYPE_CHOICES, default='damaged_item')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='submitted')`
  - `claimed_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Amount requested by customer")`
  - `approved_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Authorized refund or credit amount")`
  - `resolution_action`: `CharField(max_length=30, choices=RESOLUTION_CHOICES, default='pending')`
  - `carrier_tracking_number`: `CharField(max_length=100, blank=True, help_text="Carrier shipment tracking number")`
  - `photo_evidence_url`: `URLField(max_length=500, blank=True, help_text="URL of customer photo upload")`
  - `customer_notes`: `TextField(help_text="Customer explanation of damage or loss")`
  - `decision_notes`: `TextField(blank=True, help_text="Staff review rationale")`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='reviewed_order_claims')`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eclm_tenant_num_uniq')`
  - `Index(fields=['tenant', 'order', 'status'], name='idx_eclm_ten_ord_stat')`
  - `Index(fields=['tenant', 'status', 'claim_type'], name='idx_eclm_ten_stat_type')`

---

### 1.4 `CustomerSatisfactionSurvey` (`apps/ecommerce/models/CustomerSupport/CustomerSatisfactionSurveys.py`)
- **Table:** `ecommerce_customer_satisfaction_survey`
- **Number Prefix:** `ECSF` (`ECSF-00001`)
- **CHOICES:**
  - `SURVEY_TYPE_CHOICES = [('ticket_csat', 'Post-Ticket CSAT (1-5 Stars)'), ('order_delivery_csat', 'Post-Delivery Order CSAT (1-5 Stars)'), ('storefront_nps', 'Storefront NPS (0-10 Score)')]`
  - `SENTIMENT_CHOICES = [('positive', 'Positive (Promoter / Satisfied)'), ('neutral', 'Neutral (Passive)'), ('negative', 'Negative (Detractor / Dissatisfied)')]`
  - `FOLLOW_UP_CHOICES = [('not_required', 'No Follow-up Required'), ('pending_review', 'Pending Supervisor Review'), ('contacted_customer', 'Customer Contacted'), ('resolved_closed_loop', 'Issue Resolved (Closed Loop)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `ticket`: `ForeignKey('ecommerce.CustomerSupportTicket', on_delete=SET_NULL, null=True, blank=True, related_name='satisfaction_surveys')`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=SET_NULL, null=True, blank=True, related_name='satisfaction_surveys')`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='satisfaction_surveys')`
  - `survey_type`: `CharField(max_length=25, choices=SURVEY_TYPE_CHOICES, default='ticket_csat')`
  - `rating_score`: `PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], help_text="Rating 1-5 for CSAT, 1-10 for NPS")`
  - `sentiment`: `CharField(max_length=15, choices=SENTIMENT_CHOICES, default='neutral')`
  - `feedback_comment`: `TextField(blank=True, help_text="Shopper written comments")`
  - `agent_rated`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='rated_support_surveys')`
  - `follow_up_status`: `CharField(max_length=25, choices=FOLLOW_UP_CHOICES, default='not_required')`
  - `follow_up_notes`: `TextField(blank=True, help_text="Supervisor recovery and follow-up notes")`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='reviewed_support_surveys')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ecsf_tenant_num_uniq')`
  - `Index(fields=['tenant', 'survey_type', 'sentiment'], name='idx_ecsf_ten_type_snt')`
  - `Index(fields=['tenant', 'follow_up_status'], name='idx_ecsf_ten_followup')`
  - `Index(fields=['tenant', 'agent_rated'], name='idx_ecsf_ten_agent')`

---

## 2. Forms Contract

All forms inherit from `forms.ModelForm`. Form fields are explicitly listed in `Meta.fields`.

### 2.1 `CustomerSupportTicketForm` (`apps/ecommerce/forms/CustomerSupport/CustomerSupportTickets.py`)
- **Fields included:** `customer`, `order`, `assigned_agent`, `subject`, `customer_name`, `customer_email`, `customer_phone`, `channel`, `category`, `priority`, `status`, `initial_message`, `resolution_summary`, `internal_notes`, `is_bot_handled`, `bot_handoff_reason`
- **Exclusions:** `tenant`, `number`, `is_sla_breached`, `sla_first_response_due_at`, `sla_resolution_due_at`, `first_responded_at`, `resolved_at`, `created_at`, `updated_at`

### 2.2 `KnowledgeBaseArticleForm` (`apps/ecommerce/forms/CustomerSupport/KnowledgeBaseArticles.py`)
- **Fields included:** `title`, `slug`, `category`, `summary`, `content`, `status`, `target_audience`, `is_featured`, `keywords`, `author`
- **Exclusions:** `tenant`, `number`, `view_count`, `helpful_votes`, `unhelpful_votes`, `created_at`, `updated_at`

### 2.3 `OrderIssueClaimForm` (`apps/ecommerce/forms/CustomerSupport/OrderIssueClaims.py`)
- **Fields included:** `order`, `customer`, `ticket`, `claim_type`, `status`, `claimed_amount`, `approved_amount`, `resolution_action`, `carrier_tracking_number`, `photo_evidence_url`, `customer_notes`, `decision_notes`, `reviewed_by`
- **Exclusions:** `tenant`, `number`, `resolved_at`, `created_at`, `updated_at`

### 2.4 `CustomerSatisfactionSurveyForm` (`apps/ecommerce/forms/CustomerSupport/CustomerSatisfactionSurveys.py`)
- **Fields included:** `ticket`, `order`, `customer`, `survey_type`, `rating_score`, `sentiment`, `feedback_comment`, `agent_rated`, `follow_up_status`, `follow_up_notes`, `reviewed_by`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`

---

## 3. URLs Contract

All URLs live under namespace `ecommerce:`:

```python
# CustomerSupportTicket
path('customer-support/tickets/', views.customersupportticket_list, name='customersupportticket_list'),
path('customer-support/tickets/create/', views.customersupportticket_create, name='customersupportticket_create'),
path('customer-support/tickets/<int:pk>/', views.customersupportticket_detail, name='customersupportticket_detail'),
path('customer-support/tickets/<int:pk>/edit/', views.customersupportticket_edit, name='customersupportticket_edit'),
path('customer-support/tickets/<int:pk>/delete/', views.customersupportticket_delete, name='customersupportticket_delete'),

# KnowledgeBaseArticle
path('customer-support/articles/', views.knowledgebasearticle_list, name='knowledgebasearticle_list'),
path('customer-support/articles/create/', views.knowledgebasearticle_create, name='knowledgebasearticle_create'),
path('customer-support/articles/<int:pk>/', views.knowledgebasearticle_detail, name='knowledgebasearticle_detail'),
path('customer-support/articles/<int:pk>/edit/', views.knowledgebasearticle_edit, name='knowledgebasearticle_edit'),
path('customer-support/articles/<int:pk>/delete/', views.knowledgebasearticle_delete, name='knowledgebasearticle_delete'),

# OrderIssueClaim
path('customer-support/claims/', views.orderissueclaim_list, name='orderissueclaim_list'),
path('customer-support/claims/create/', views.orderissueclaim_create, name='orderissueclaim_create'),
path('customer-support/claims/<int:pk>/', views.orderissueclaim_detail, name='orderissueclaim_detail'),
path('customer-support/claims/<int:pk>/edit/', views.orderissueclaim_edit, name='orderissueclaim_edit'),
path('customer-support/claims/<int:pk>/delete/', views.orderissueclaim_delete, name='orderissueclaim_delete'),

# CustomerSatisfactionSurvey
path('customer-support/surveys/', views.customersatisfactionsurvey_list, name='customersatisfactionsurvey_list'),
path('customer-support/surveys/create/', views.customersatisfactionsurvey_create, name='customersatisfactionsurvey_create'),
path('customer-support/surveys/<int:pk>/', views.customersatisfactionsurvey_detail, name='customersatisfactionsurvey_detail'),
path('customer-support/surveys/<int:pk>/edit/', views.customersatisfactionsurvey_edit, name='customersatisfactionsurvey_edit'),
path('customer-support/surveys/<int:pk>/delete/', views.customersatisfactionsurvey_delete, name='customersatisfactionsurvey_delete'),
```

---

## 4. View Context Keys Contract (L7 Pinned)

### 4.1 `CustomerSupportTicket` Views
- `customersupportticket_list`:
  - Template: `ecommerce/customer_support/ticket/list.html`
  - Context keys:
    - `tickets`: Paged queryset of `CustomerSupportTicket`
    - `status_choices`: `CustomerSupportTicket.STATUS_CHOICES`
    - `priority_choices`: `CustomerSupportTicket.PRIORITY_CHOICES`
    - `channel_choices`: `CustomerSupportTicket.CHANNEL_CHOICES`
    - `category_choices`: `CustomerSupportTicket.CATEGORY_CHOICES`
    - `agents`: Queryset of `User`
    - `selected_status`: `request.GET.get('status', '')`
    - `selected_priority`: `request.GET.get('priority', '')`
    - `selected_channel`: `request.GET.get('channel', '')`
    - `selected_category`: `request.GET.get('category', '')`
    - `selected_agent`: `request.GET.get('agent', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `customersupportticket_detail`:
  - Template: `ecommerce/customer_support/ticket/detail.html`
  - Context keys:
    - `ticket`: Single `CustomerSupportTicket` instance
- `customersupportticket_create` / `customersupportticket_edit`:
  - Template: `ecommerce/customer_support/ticket/form.html`
  - Context keys:
    - `form`: `CustomerSupportTicketForm`
    - `ticket`: `CustomerSupportTicket` instance (edit) or `None` (create)

### 4.2 `KnowledgeBaseArticle` Views
- `knowledgebasearticle_list`:
  - Template: `ecommerce/customer_support/article/list.html`
  - Context keys:
    - `articles`: Paged queryset of `KnowledgeBaseArticle`
    - `category_choices`: `KnowledgeBaseArticle.CATEGORY_CHOICES`
    - `status_choices`: `KnowledgeBaseArticle.STATUS_CHOICES`
    - `audience_choices`: `KnowledgeBaseArticle.AUDIENCE_CHOICES`
    - `selected_category`: `request.GET.get('category', '')`
    - `selected_status`: `request.GET.get('status', '')`
    - `selected_audience`: `request.GET.get('audience', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `knowledgebasearticle_detail`:
  - Template: `ecommerce/customer_support/article/detail.html`
  - Context keys:
    - `article`: Single `KnowledgeBaseArticle` instance
- `knowledgebasearticle_create` / `knowledgebasearticle_edit`:
  - Template: `ecommerce/customer_support/article/form.html`
  - Context keys:
    - `form`: `KnowledgeBaseArticleForm`
    - `article`: `KnowledgeBaseArticle` instance (edit) or `None` (create)

### 4.3 `OrderIssueClaim` Views
- `orderissueclaim_list`:
  - Template: `ecommerce/customer_support/claim/list.html`
  - Context keys:
    - `claims`: Paged queryset of `OrderIssueClaim`
    - `claim_type_choices`: `OrderIssueClaim.CLAIM_TYPE_CHOICES`
    - `status_choices`: `OrderIssueClaim.STATUS_CHOICES`
    - `resolution_choices`: `OrderIssueClaim.RESOLUTION_CHOICES`
    - `selected_claim_type`: `request.GET.get('claim_type', '')`
    - `selected_status`: `request.GET.get('status', '')`
    - `selected_resolution`: `request.GET.get('resolution', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `orderissueclaim_detail`:
  - Template: `ecommerce/customer_support/claim/detail.html`
  - Context keys:
    - `claim`: Single `OrderIssueClaim` instance
- `orderissueclaim_create` / `orderissueclaim_edit`:
  - Template: `ecommerce/customer_support/claim/form.html`
  - Context keys:
    - `form`: `OrderIssueClaimForm`
    - `claim`: `OrderIssueClaim` instance (edit) or `None` (create)

### 4.4 `CustomerSatisfactionSurvey` Views
- `customersatisfactionsurvey_list`:
  - Template: `ecommerce/customer_support/survey/list.html`
  - Context keys:
    - `surveys`: Paged queryset of `CustomerSatisfactionSurvey`
    - `survey_type_choices`: `CustomerSatisfactionSurvey.SURVEY_TYPE_CHOICES`
    - `sentiment_choices`: `CustomerSatisfactionSurvey.SENTIMENT_CHOICES`
    - `follow_up_choices`: `CustomerSatisfactionSurvey.FOLLOW_UP_CHOICES`
    - `selected_survey_type`: `request.GET.get('survey_type', '')`
    - `selected_sentiment`: `request.GET.get('sentiment', '')`
    - `selected_follow_up`: `request.GET.get('follow_up', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `customersatisfactionsurvey_detail`:
  - Template: `ecommerce/customer_support/survey/detail.html`
  - Context keys:
    - `survey`: Single `CustomerSatisfactionSurvey` instance
- `customersatisfactionsurvey_create` / `customersatisfactionsurvey_edit`:
  - Template: `ecommerce/customer_support/survey/form.html`
  - Context keys:
    - `form`: `CustomerSatisfactionSurveyForm`
    - `survey`: `CustomerSatisfactionSurvey` instance (edit) or `None` (create)
