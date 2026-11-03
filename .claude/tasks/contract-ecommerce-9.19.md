# Contract — Sub-module 9.19: Integration & API Ecosystem (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.19 Integration & API Ecosystem · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-03 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0037_...`
- **Package Layout:** `IntegrationApi/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/integration_api/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `EcommerceConnector` (`apps/ecommerce/models/IntegrationApi/EcommerceConnectors.py`)
- **Table:** `ecommerce_connector`
- **Number Prefix:** `ECON` (`ECON-00001`)
- **CHOICES:**
  - `CATEGORY_CHOICES = [('erp', 'ERP & Back-Office Sync'), ('payment', 'Payment Gateway Connector'), ('shipping', 'Shipping & Logistics API'), ('marketing', 'Marketing & Analytics Tool'), ('custom', 'Custom Webhook / REST Connector')]`
  - `PROVIDER_CHOICES = [('netsuite', 'Oracle NetSuite ERP'), ('sap_s4hana', 'SAP S/4HANA ERP'), ('ms_dynamics', 'Microsoft Dynamics 365'), ('odoo', 'Odoo ERP'), ('stripe', 'Stripe Payments'), ('adyen', 'Adyen Payments'), ('paypal', 'PayPal Gateway'), ('square', 'Square Commerce'), ('fedex', 'FedEx Logistics'), ('ups', 'UPS Shipping'), ('dhl', 'DHL Express'), ('usps', 'USPS Postal Service'), ('klaviyo', 'Klaviyo Marketing Automation'), ('mailchimp', 'Mailchimp Newsletter'), ('segment', 'Twilio Segment CDP'), ('braze', 'Braze Customer Engagement'), ('google_analytics', 'Google Analytics 4 / Tag Manager'), ('generic_rest', 'Generic REST / Webhook API'), ('other', 'Other Integration Provider')]`
  - `AUTH_TYPE_CHOICES = [('api_key', 'API Key / Secret Token'), ('bearer_token', 'Bearer Auth Token'), ('oauth2', 'OAuth 2.0 Credentials'), ('basic_auth', 'HTTP Basic Authentication'), ('hmac_secret', 'HMAC Shared Secret'), ('none', 'No Authentication / Public')]`
  - `STATUS_CHOICES = [('active', 'Active & Operational'), ('inactive', 'Inactive / Paused'), ('testing', 'Sandbox / Testing'), ('error', 'Connection Error'), ('maintenance', 'Scheduled Maintenance')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="Human-readable connector name e.g. NetSuite ERP Production")`
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default='erp')`
  - `provider`: `CharField(max_length=40, choices=PROVIDER_CHOICES, default='generic_rest')`
  - `auth_type`: `CharField(max_length=30, choices=AUTH_TYPE_CHOICES, default='api_key')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `base_url`: `CharField(max_length=500, blank=True, default="", help_text="Base API endpoint URL e.g. https://api.stripe.com/v1")`
  - `api_version`: `CharField(max_length=50, blank=True, default="v1")`
  - `api_key`: `CharField(max_length=255, blank=True, default="", help_text="Stored API key or client identifier")`
  - `api_secret`: `CharField(max_length=255, blank=True, default="", help_text="Sensitive API secret or auth credential")`
  - `account_id`: `CharField(max_length=100, blank=True, default="", help_text="External merchant / account / organization ID")`
  - `is_sandbox`: `BooleanField(default=False, help_text="Whether connector targets test / sandbox environment")`
  - `timeout_seconds`: `IntegerField(default=30, help_text="HTTP request timeout in seconds")`
  - `rate_limit_per_minute`: `IntegerField(default=120, help_text="Throttling rate limit per minute")`
  - `health_status`: `CharField(max_length=30, default="healthy", help_text="healthy, degraded, down, unknown")`
  - `last_health_check_at`: `DateTimeField(null=True, blank=True)`
  - `last_error_message`: `TextField(blank=True, default="")`
  - `description`: `TextField(blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_econ_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_econ_ten_status')`
  - `Index(fields=['tenant', 'category'], name='idx_econ_ten_cat')`
  - `Index(fields=['tenant', 'provider'], name='idx_econ_ten_prov')`
- **Ordering:** `['-created_at']`

---

### 1.2 `IntegrationSyncJob` (`apps/ecommerce/models/IntegrationApi/IntegrationSyncJobs.py`)
- **Table:** `ecommerce_integration_sync_job`
- **Number Prefix:** `ESYJ` (`ESYJ-00001`)
- **CHOICES:**
  - `SYNC_ENTITY_CHOICES = [('order_to_cash', 'Order-to-Cash (Orders & Invoices)'), ('inventory_levels', 'Inventory Levels & Stock Availability'), ('catalog_products', 'Product Catalog & Pricing'), ('customer_profiles', 'Customer Profiles & Contacts'), ('shipment_tracking', 'Shipments & Tracking Numbers'), ('payment_settlement', 'Payment Settlements & Payouts'), ('marketing_events', 'Marketing Events & Triggers'), ('custom_payload', 'Custom JSON Payload Sync')]`
  - `DIRECTION_CHOICES = [('inbound', 'Inbound (External -> NavERP)'), ('outbound', 'Outbound (NavERP -> External)'), ('bidirectional', 'Bidirectional Sync')]`
  - `STATUS_CHOICES = [('pending', 'Pending / Queued'), ('running', 'Running / In-Progress'), ('completed', 'Completed Successfully'), ('failed', 'Failed'), ('partial_success', 'Partial Success with Errors'), ('cancelled', 'Cancelled')]`
  - `TRIGGER_TYPE_CHOICES = [('scheduled', 'Scheduled Polling / Cron'), ('manual', 'Manual Trigger by Staff'), ('webhook', 'Real-Time Inbound Webhook'), ('event_driven', 'Event-Driven Platform Action')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `connector`: `ForeignKey('ecommerce.EcommerceConnector', on_delete=CASCADE, related_name='sync_jobs')`
  - `sync_entity`: `CharField(max_length=40, choices=SYNC_ENTITY_CHOICES, default='order_to_cash')`
  - `direction`: `CharField(max_length=20, choices=DIRECTION_CHOICES, default='outbound')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='pending')`
  - `trigger_type`: `CharField(max_length=25, choices=TRIGGER_TYPE_CHOICES, default='manual')`
  - `batch_id`: `CharField(max_length=64, blank=True, default="", help_text="Sync execution batch UUID or correlation ID")`
  - `records_total`: `IntegerField(default=0)`
  - `records_processed`: `IntegerField(default=0)`
  - `records_succeeded`: `IntegerField(default=0)`
  - `records_failed`: `IntegerField(default=0)`
  - `started_at`: `DateTimeField(null=True, blank=True)`
  - `finished_at`: `DateTimeField(null=True, blank=True)`
  - `duration_seconds`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `error_summary`: `TextField(blank=True, default="", help_text="Detailed failure trace or diagnostic log")`
  - `payload_preview`: `TextField(blank=True, default="", help_text="Sample payload summary or request body")`
  - `retry_count`: `IntegerField(default=0)`
  - `max_retries`: `IntegerField(default=3)`
  - `parent_job`: `ForeignKey('self', null=True, blank=True, on_delete=SET_NULL, related_name='child_retries')`
  - `triggered_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='triggered_sync_jobs')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esyj_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_esyj_ten_status')`
  - `Index(fields=['tenant', 'connector'], name='idx_esyj_ten_conn')`
  - `Index(fields=['tenant', 'sync_entity'], name='idx_esyj_ten_entity')`
  - `Index(fields=['tenant', 'started_at'], name='idx_esyj_ten_started')`
- **Ordering:** `['-created_at']`

---

### 1.3 `WebhookSubscription` (`apps/ecommerce/models/IntegrationApi/WebhookSubscriptions.py`)
- **Table:** `ecommerce_webhook_subscription`
- **Number Prefix:** `EWBS` (`EWBS-00001`)
- **CHOICES:**
  - `EVENT_TOPIC_CHOICES = [('order.created', 'Order Created'), ('order.paid', 'Order Payment Captured'), ('order.fulfilled', 'Order Fulfilled / Shipped'), ('order.cancelled', 'Order Cancelled'), ('order.refunded', 'Order Refund Issued'), ('inventory.low_stock', 'Inventory Low Stock Warning'), ('inventory.updated', 'Inventory Levels Updated'), ('product.created', 'Product Created'), ('product.updated', 'Product Updated'), ('customer.registered', 'Customer Account Registered'), ('dispute.opened', 'Chargeback Dispute Opened'), ('all_events', 'All Commerce Events (* wildcard)')]`
  - `STATUS_CHOICES = [('active', 'Active & Delivering'), ('paused', 'Paused by Administrator'), ('disabled', 'Disabled / Inactive'), ('circuit_broken', 'Circuit Broken (Failure Threshold Exceeded)')]`
  - `PAYLOAD_FORMAT_CHOICES = [('json', 'application/json'), ('form_encoded', 'application/x-www-form-urlencoded')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="Friendly webhook subscriber description")`
  - `target_url`: `CharField(max_length=500, help_text="Destination HTTPS endpoint URL")`
  - `event_topic`: `CharField(max_length=50, choices=EVENT_TOPIC_CHOICES, default='order.created')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='active')`
  - `secret_key`: `CharField(max_length=255, blank=True, default="", help_text="HMAC-SHA256 signature verification key")`
  - `payload_format`: `CharField(max_length=20, choices=PAYLOAD_FORMAT_CHOICES, default='json')`
  - `custom_headers`: `TextField(blank=True, default="{}", help_text="JSON dictionary of custom HTTP request headers")`
  - `consecutive_failures`: `IntegerField(default=0)`
  - `max_consecutive_failures`: `IntegerField(default=5)`
  - `last_delivery_at`: `DateTimeField(null=True, blank=True)`
  - `last_status_code`: `IntegerField(null=True, blank=True)`
  - `last_error_message`: `TextField(blank=True, default="")`
  - `total_delivered_count`: `IntegerField(default=0)`
  - `total_failed_count`: `IntegerField(default=0)`
  - `is_verify_ssl`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ewbs_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ewbs_ten_status')`
  - `Index(fields=['tenant', 'event_topic'], name='idx_ewbs_ten_topic')`
- **Ordering:** `['-created_at']`

---

### 1.4 `ApiCredential` (`apps/ecommerce/models/IntegrationApi/ApiCredentials.py`)
- **Table:** `ecommerce_api_credential`
- **Number Prefix:** `EAPC` (`EAPC-00001`)
- **CHOICES:**
  - `TIER_CHOICES = [('storefront_public', 'Headless Storefront API (Public Access Token)'), ('admin_server', 'Back-Office Admin API (Server-to-Server Private Key)'), ('partner_read', 'Partner / Analytics Integration (Read-Only)'), ('webhook_receiver', 'Inbound Webhook Signature Key')]`
  - `STATUS_CHOICES = [('active', 'Active & Authorized'), ('revoked', 'Revoked / Disabled'), ('expired', 'Expired'), ('rate_limited', 'Temporarily Rate-Limited')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="App / client name e.g. Next.js Headless Web Storefront")`
  - `tier`: `CharField(max_length=30, choices=TIER_CHOICES, default='storefront_public')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `client_id`: `CharField(max_length=64, unique=True, help_text="Public API client ID key")`
  - `client_secret_hash`: `CharField(max_length=128, blank=True, default="", help_text="SHA-256 hashed secret for server authentication")`
  - `secret_prefix`: `CharField(max_length=16, blank=True, default="", help_text="Masked cleartext prefix e.g. nep_live_...")`
  - `scopes`: `CharField(max_length=500, default="read_catalog,read_orders", help_text="Comma-separated permission scopes")`
  - `allowed_origins`: `TextField(blank=True, default="*", help_text="CORS allowed web origins (comma-separated or * for public)")`
  - `allowed_ips`: `TextField(blank=True, default="", help_text="IP CIDR whitelist restriction (blank for unrestricted)")`
  - `rate_limit_rpm`: `IntegerField(default=120, help_text="Requests per minute allowed")`
  - `total_requests_count`: `IntegerField(default=0)`
  - `last_used_at`: `DateTimeField(null=True, blank=True)`
  - `expires_at`: `DateTimeField(null=True, blank=True)`
  - `revoked_at`: `DateTimeField(null=True, blank=True)`
  - `description`: `TextField(blank=True, default="")`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='created_api_credentials')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eapc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_eapc_ten_status')`
  - `Index(fields=['tenant', 'tier'], name='idx_eapc_ten_tier')`
  - `Index(fields=['client_id'], name='idx_eapc_client_id')`
- **Ordering:** `['-created_at']`

---

## 2. Forms Contract (`apps/ecommerce/forms/IntegrationApi/`)

### 2.1 `EcommerceConnectorForm` (`EcommerceConnectors.py`)
- **Model:** `EcommerceConnector`
- **Fields:** `['name', 'category', 'provider', 'auth_type', 'status', 'base_url', 'api_version', 'api_key', 'api_secret', 'account_id', 'is_sandbox', 'timeout_seconds', 'rate_limit_per_minute', 'description']`
- **Excluded:** `['tenant', 'number', 'health_status', 'last_health_check_at', 'last_error_message', 'created_at', 'updated_at']`
- **Widgets:**
  - `api_secret`: `PasswordInput(render_value=True, attrs={'class': 'form-input', 'placeholder': '••••••••••••••••'})`
  - `description`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea'})`

### 2.2 `IntegrationSyncJobForm` (`IntegrationSyncJobs.py`)
- **Model:** `IntegrationSyncJob`
- **Fields:** `['connector', 'sync_entity', 'direction', 'trigger_type', 'batch_id', 'payload_preview', 'max_retries', 'error_summary']`
- **Excluded:** `['tenant', 'number', 'status', 'records_total', 'records_processed', 'records_succeeded', 'records_failed', 'started_at', 'finished_at', 'duration_seconds', 'retry_count', 'parent_job', 'triggered_by', 'created_at', 'updated_at']`
- **Widgets:**
  - `payload_preview`: `Textarea(attrs={'rows': 4, 'class': 'form-textarea font-mono text-xs'})`
  - `error_summary`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea'})`

### 2.3 `WebhookSubscriptionForm` (`WebhookSubscriptions.py`)
- **Model:** `WebhookSubscription`
- **Fields:** `['name', 'target_url', 'event_topic', 'status', 'secret_key', 'payload_format', 'custom_headers', 'max_consecutive_failures', 'is_verify_ssl', 'description']`
- **Excluded:** `['tenant', 'number', 'consecutive_failures', 'last_delivery_at', 'last_status_code', 'last_error_message', 'total_delivered_count', 'total_failed_count', 'created_at', 'updated_at']`
- **Widgets:**
  - `target_url`: `URLInput(attrs={'class': 'form-input', 'placeholder': 'https://api.external.com/webhooks/orders'})`
  - `secret_key`: `PasswordInput(render_value=True, attrs={'class': 'form-input font-mono'})`
  - `custom_headers`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea font-mono text-xs'})`
  - `description`: `Textarea(attrs={'rows': 2, 'class': 'form-textarea'})`

### 2.4 `ApiCredentialForm` (`ApiCredentials.py`)
- **Model:** `ApiCredential`
- **Fields:** `['name', 'tier', 'status', 'scopes', 'allowed_origins', 'allowed_ips', 'rate_limit_rpm', 'expires_at', 'description']`
- **Excluded:** `['tenant', 'number', 'client_id', 'client_secret_hash', 'secret_prefix', 'total_requests_count', 'last_used_at', 'revoked_at', 'created_by', 'created_at', 'updated_at']`
- **Widgets:**
  - `scopes`: `TextInput(attrs={'class': 'form-input font-mono text-xs', 'placeholder': 'read_catalog,read_orders,write_orders'})`
  - `allowed_origins`: `Textarea(attrs={'rows': 2, 'class': 'form-textarea font-mono text-xs', 'placeholder': 'https://myshop.com, https://app.myshop.com'})`
  - `allowed_ips`: `Textarea(attrs={'rows': 2, 'class': 'form-textarea font-mono text-xs', 'placeholder': '192.168.1.0/24 (leave blank for all)'})`
  - `expires_at`: `DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})`
  - `description`: `Textarea(attrs={'rows': 2, 'class': 'form-textarea'})`

---

## 3. URLs & Routes Contract (`apps/ecommerce/urls/IntegrationApi/`)

App name: `ecommerce`

### 3.1 Hub & Overview:
- `integration-api/` → `name='integration_api_hub'`

### 3.2 `EcommerceConnector` Routes (`EcommerceConnectors.py`):
- `connectors/` → `name='ecommerceconnector_list'`
- `connectors/create/` → `name='ecommerceconnector_create'`
- `connectors/<int:pk>/` → `name='ecommerceconnector_detail'`
- `connectors/<int:pk>/edit/` → `name='ecommerceconnector_edit'`
- `connectors/<int:pk>/delete/` → `name='ecommerceconnector_delete'`
- `connectors/<int:pk>/test-connection/` → `name='ecommerceconnector_test_connection'`

### 3.3 `IntegrationSyncJob` Routes (`IntegrationSyncJobs.py`):
- `sync-jobs/` → `name='integrationsyncjob_list'`
- `sync-jobs/create/` → `name='integrationsyncjob_create'`
- `sync-jobs/<int:pk>/` → `name='integrationsyncjob_detail'`
- `sync-jobs/<int:pk>/edit/` → `name='integrationsyncjob_edit'`
- `sync-jobs/<int:pk>/delete/` → `name='integrationsyncjob_delete'`
- `sync-jobs/<int:pk>/retry/` → `name='integrationsyncjob_retry'`

### 3.4 `WebhookSubscription` Routes (`WebhookSubscriptions.py`):
- `webhooks/` → `name='webhooksubscription_list'`
- `webhooks/create/` → `name='webhooksubscription_create'`
- `webhooks/<int:pk>/` → `name='webhooksubscription_detail'`
- `webhooks/<int:pk>/edit/` → `name='webhooksubscription_edit'`
- `webhooks/<int:pk>/delete/` → `name='webhooksubscription_delete'`
- `webhooks/<int:pk>/ping/` → `name='webhooksubscription_ping'`

### 3.5 `ApiCredential` Routes (`ApiCredentials.py`):
- `api-credentials/` → `name='apicredential_list'`
- `api-credentials/create/` → `name='apicredential_create'`
- `api-credentials/<int:pk>/` → `name='apicredential_detail'`
- `api-credentials/<int:pk>/edit/` → `name='apicredential_edit'`
- `api-credentials/<int:pk>/delete/` → `name='apicredential_delete'`
- `api-credentials/<int:pk>/revoke/` → `name='apicredential_revoke'`

---

## 4. Views Context Contract (`apps/ecommerce/views/IntegrationApi/`)

### 4.1 Hub View (`integration_api_hub`):
- Template: `ecommerce/integration_api/integration_api_hub.html`
- Context keys:
  - `stats`: dict with `total_connectors`, `active_connectors`, `total_jobs`, `failed_jobs`, `total_webhooks`, `active_credentials`
  - `recent_jobs`: QuerySet of recent 5 `IntegrationSyncJob`s
  - `recent_connectors`: QuerySet of 5 `EcommerceConnector`s
  - `active_webhooks`: QuerySet of 5 `WebhookSubscription`s

### 4.2 `EcommerceConnector` Views:
- **List View (`ecommerceconnector_list`):**
  - Template: `ecommerce/integration_api/ecommerce_connector/list.html`
  - Context keys:
    - `page_obj`: Paginator Page object of connectors
    - `connectors`: alias of `page_obj` for template rendering
    - `category_choices`: `EcommerceConnector.CATEGORY_CHOICES`
    - `status_choices`: `EcommerceConnector.STATUS_CHOICES`
    - `provider_choices`: `EcommerceConnector.PROVIDER_CHOICES`
    - `q`: Search query string
    - `category_filter`: Selected category GET param
    - `status_filter`: Selected status GET param
- **Detail View (`ecommerceconnector_detail`):**
  - Template: `ecommerce/integration_api/ecommerce_connector/detail.html`
  - Context keys:
    - `connector`: `EcommerceConnector` object
    - `recent_jobs`: QuerySet of sync jobs belonging to this connector
- **Form View (`ecommerceconnector_create` / `ecommerceconnector_edit`):**
  - Template: `ecommerce/integration_api/ecommerce_connector/form.html`
  - Context keys:
    - `form`: `EcommerceConnectorForm`
    - `connector`: `EcommerceConnector` instance (or None if create)
    - `is_edit`: Boolean

### 4.3 `IntegrationSyncJob` Views:
- **List View (`integrationsyncjob_list`):**
  - Template: `ecommerce/integration_api/integration_sync_job/list.html`
  - Context keys:
    - `page_obj`: Paginator Page object of sync jobs
    - `sync_jobs`: alias of `page_obj`
    - `connectors`: QuerySet of active `EcommerceConnector`s
    - `entity_choices`: `IntegrationSyncJob.SYNC_ENTITY_CHOICES`
    - `status_choices`: `IntegrationSyncJob.STATUS_CHOICES`
    - `direction_choices`: `IntegrationSyncJob.DIRECTION_CHOICES`
    - `trigger_choices`: `IntegrationSyncJob.TRIGGER_TYPE_CHOICES`
    - `q`: Search query string
    - `status_filter`: Selected status
    - `entity_filter`: Selected sync_entity
    - `connector_filter`: Selected connector ID
- **Detail View (`integrationsyncjob_detail`):**
  - Template: `ecommerce/integration_api/integration_sync_job/detail.html`
  - Context keys:
    - `sync_job`: `IntegrationSyncJob` object
    - `child_retries`: QuerySet of child retries
- **Form View (`integrationsyncjob_create` / `integrationsyncjob_edit`):**
  - Template: `ecommerce/integration_api/integration_sync_job/form.html`
  - Context keys:
    - `form`: `IntegrationSyncJobForm`
    - `sync_job`: `IntegrationSyncJob` instance (or None)
    - `is_edit`: Boolean

### 4.4 `WebhookSubscription` Views:
- **List View (`webhooksubscription_list`):**
  - Template: `ecommerce/integration_api/webhook_subscription/list.html`
  - Context keys:
    - `page_obj`: Paginator Page object
    - `webhooks`: alias of `page_obj`
    - `topic_choices`: `WebhookSubscription.EVENT_TOPIC_CHOICES`
    - `status_choices`: `WebhookSubscription.STATUS_CHOICES`
    - `q`: Search query
    - `topic_filter`: Selected event_topic
    - `status_filter`: Selected status
- **Detail View (`webhooksubscription_detail`):**
  - Template: `ecommerce/integration_api/webhook_subscription/detail.html`
  - Context keys:
    - `webhook`: `WebhookSubscription` object
- **Form View (`webhooksubscription_create` / `webhooksubscription_edit`):**
  - Template: `ecommerce/integration_api/webhook_subscription/form.html`
  - Context keys:
    - `form`: `WebhookSubscriptionForm`
    - `webhook`: `WebhookSubscription` instance (or None)
    - `is_edit`: Boolean

### 4.5 `ApiCredential` Views:
- **List View (`apicredential_list`):**
  - Template: `ecommerce/integration_api/api_credential/list.html`
  - Context keys:
    - `page_obj`: Paginator Page object
    - `credentials`: alias of `page_obj`
    - `tier_choices`: `ApiCredential.TIER_CHOICES`
    - `status_choices`: `ApiCredential.STATUS_CHOICES`
    - `q`: Search query
    - `tier_filter`: Selected tier
    - `status_filter`: Selected status
- **Detail View (`apicredential_detail`):**
  - Template: `ecommerce/integration_api/api_credential/detail.html`
  - Context keys:
    - `credential`: `ApiCredential` object
    - `new_raw_secret`: One-time displayed cleartext secret (if just created/regenerated)
- **Form View (`apicredential_create` / `apicredential_edit`):**
  - Template: `ecommerce/integration_api/api_credential/form.html`
  - Context keys:
    - `form`: `ApiCredentialForm`
    - `credential`: `ApiCredential` instance (or None)
    - `is_edit`: Boolean

---

## 5. Navigation Sidebar Contract (`LIVE_LINKS["9.19"]`)

Exact mapping for all 5 `NavERP.md` feature bullets:
```python
LIVE_LINKS["9.19"] = {
    # 9.19 Integration & API Ecosystem
    "ERP & Back-Office Sync": "ecommerce:integrationsyncjob_list",               # bullet
    "Payment Gateway Connectors": "ecommerce:ecommerceconnector_list?category=payment",   # bullet
    "Shipping & Logistics APIs": "ecommerce:ecommerceconnector_list?category=shipping",  # bullet
    "Marketing Tool Integrations": "ecommerce:ecommerceconnector_list?category=marketing", # bullet
    "Headless Commerce & API-First": "ecommerce:apicredential_list",             # bullet
    # Extra live leaves
    "Integration Hub": "ecommerce:integration_api_hub",                         # extra
    "Connectors Registry": "ecommerce:ecommerceconnector_list",                 # extra
    "Sync Execution Queue": "ecommerce:integrationsyncjob_list",                # extra
    "Webhook Subscriptions": "ecommerce:webhooksubscription_list",              # extra
    "API Keys & Access Tokens": "ecommerce:apicredential_list",                  # extra
}
```

---

## 6. Templates Contract (`templates/ecommerce/integration_api/`)

- `integration_api_hub.html`: Hub dashboard with stats cards, quick launch links, recent sync jobs, connectors summary.
- `ecommerce_connector/`:
  - `list.html`: List table, category/status/provider filters, search, test connection action, create button.
  - `detail.html`: Connector credentials summary, health status badge, sync jobs log, test connection modal/button.
  - `form.html`: Create/Edit form with password masking for secrets, sandbox toggle.
- `integration_sync_job/`:
  - `list.html`: Sync jobs queue, entity/direction/status filters, duration/records counters, retry action.
  - `detail.html`: Full execution metrics, payload preview (monospaced), error stack trace, retry history.
  - `form.html`: Manual trigger / job edit form.
- `webhook_subscription/`:
  - `list.html`: Webhook endpoints list, topic badge, consecutive failures indicator, ping action.
  - `detail.html`: Endpoint details, secret key display, custom headers, delivery counters, error logs.
  - `form.html`: Create/Edit subscription form with SSL verification toggle and custom headers JSON.
- `api_credential/`:
  - `list.html`: API keys registry, tier badges, client ID, requests counter, last used timestamp, revoke action.
  - `detail.html`: Key permissions/scopes, rate limit RPM, allowed origins/IPs, revocation badge, one-time secret warning banner.
  - `form.html`: Create/Edit credential form with scopes and CORS configuration.

---

## 7. Quality & Verification Gates
1. `venv\Scripts\python.exe manage.py makemigrations ecommerce` -> produces `0037_...`
2. `venv\Scripts\python.exe manage.py migrate`
3. `venv\Scripts\python.exe manage.py seed_ecommerce` (idempotent, run twice)
4. `venv\Scripts\python.exe manage.py check` -> clean (0 issues)
5. `temp/smoke_test_9_19.py` sweep -> all endpoints return 200/302, zero leak markers, cross-tenant IDOR returns 404.
