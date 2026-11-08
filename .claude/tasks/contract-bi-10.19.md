# Contract — Sub-module 10.19: Integration & API Hub (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.19 Integration & API Hub • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-08 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.18). Incremental migration: `0042_...`
- **Package Layout:** `IntegrationHub/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/integration_hub/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `IntegrationConnector` (`apps/bi/models/IntegrationHub/IntegrationConnectors.py`)
- **Table:** `bi_integration_connector`
- **Number Prefix:** `BINT` (`BINT-00001`)
- **CHOICES:**
  - `CONNECTOR_TYPE_CHOICES = [('internal_erp', 'Internal NavERP Operational Module'), ('message_broker', 'Streaming Message Queue / Event Bus'), ('saas_application', 'Third-Party SaaS Application'), ('custom_api', 'Custom REST/GraphQL Endpoint')]`
  - `TARGET_SYSTEM_CHOICES = [('erp_accounting', 'Module 2: Accounting & Financial Ledger'), ('erp_hrm', 'Module 3: Human Resource Management'), ('erp_scm', 'Module 4: Supply Chain & Procurement'), ('erp_crm', 'Module 1: CRM & Sales Management'), ('erp_inventory', 'Module 5: Inventory & Warehouse'), ('kafka', 'Apache Kafka Cluster'), ('rabbitmq', 'RabbitMQ Message Broker'), ('aws_eventbridge', 'AWS EventBridge Event Bus'), ('redis_streams', 'Redis Streams Pub/Sub'), ('generic_webhook', 'Generic HTTP/REST Gateway')]`
  - `SYNC_DIRECTION_CHOICES = [('inbound', 'Inbound (Operational Data → BI Lakehouse)'), ('outbound', 'Outbound (BI Intelligence → Operational Target)'), ('bidirectional', 'Bidirectional (Continuous Closed-Loop)')]`
  - `AUTH_TYPE_CHOICES = [('internal_session', 'Internal NavERP Direct Session'), ('api_key', 'API Key Header'), ('bearer_token', 'OAuth2 / Bearer Token'), ('basic_auth', 'HTTP Basic Authentication'), ('iam_role', 'AWS IAM Role / Cloud Identity'), ('tls_certificate', 'Mutual TLS Certificate')]`
  - `MESSAGE_FORMAT_CHOICES = [('json', 'Standard JSON'), ('avro', 'Apache Avro (Schema Governed)'), ('protobuf', 'Google Protocol Buffers'), ('cloudevents', 'CloudEvents 1.0 Specification')]`
  - `SYNC_INTERVAL_CHOICES = [('realtime_event', 'Real-Time Event Triggered'), ('every_minute', 'Every Minute'), ('every_5_minutes', 'Every 5 Minutes'), ('hourly', 'Hourly'), ('daily', 'Daily Scheduled'), ('manual', 'Manual On-Demand Only')]`
  - `STATUS_CHOICES = [('active', 'Active & Running'), ('paused', 'Paused by Administrator'), ('error', 'Failed / Error State'), ('maintenance', 'Under Maintenance')]`
  - `HEALTH_STATUS_CHOICES = [('healthy', 'Healthy (Heartbeat Normal)'), ('degraded', 'Degraded (High Latency / Intermittent)'), ('unreachable', 'Unreachable (Connection Refused)'), ('untested', 'Untested Configuration')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_integration_connectors')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120, blank=True)`
  - `description`: `TextField(blank=True)`
  - `connector_type`: `CharField(max_length=40, choices=CONNECTOR_TYPE_CHOICES, default='internal_erp')`
  - `target_system`: `CharField(max_length=50, choices=TARGET_SYSTEM_CHOICES, default='erp_accounting')`
  - `sync_direction`: `CharField(max_length=30, choices=SYNC_DIRECTION_CHOICES, default='outbound')`
  - `connection_config`: `JSONField(default=dict, blank=True)`
  - `auth_type`: `CharField(max_length=40, choices=AUTH_TYPE_CHOICES, default='internal_session')`
  - `auth_credentials`: `JSONField(default=dict, blank=True)`
  - `message_format`: `CharField(max_length=30, choices=MESSAGE_FORMAT_CHOICES, default='json')`
  - `sync_interval`: `CharField(max_length=30, choices=SYNC_INTERVAL_CHOICES, default='realtime_event')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='active')`
  - `health_status`: `CharField(max_length=30, choices=HEALTH_STATUS_CHOICES, default='healthy')`
  - `last_heartbeat_at`: `DateTimeField(null=True, blank=True)`
  - `last_sync_at`: `DateTimeField(null=True, blank=True)`
  - `total_messages_processed`: `PositiveBigIntegerField(default=0)`
  - `error_message`: `TextField(blank=True)`
  - `is_enabled`: `BooleanField(default=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_created_connectors')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bint_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bint_ten_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bint_ten_stat')`
  - `Index(fields=['tenant', 'connector_type'], name='idx_bint_ten_type')`
  - `Index(fields=['tenant', 'target_system'], name='idx_bint_ten_target')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bint_ten_created')`

---

### 1.2 `WarehouseSyncEndpoint` (`apps/bi/models/IntegrationHub/WarehouseSyncEndpoints.py`)
- **Table:** `bi_warehouse_sync_endpoint`
- **Number Prefix:** `BSNC` (`BSNC-00001`)
- **CHOICES:**
  - `TARGET_WAREHOUSE_CHOICES = [('snowflake', 'Snowflake Cloud Data Warehouse'), ('google_bigquery', 'Google BigQuery'), ('aws_redshift', 'Amazon Redshift'), ('databricks_unity', 'Databricks Unity Catalog'), ('power_bi_semantic_model', 'Microsoft Power BI Semantic Model'), ('tableau_hyper', 'Tableau Cloud / Server Hyper Extract'), ('looker_lookml', 'Google Cloud Looker (LookML Feed)')]`
  - `SYNC_MODE_CHOICES = [('incremental_merge', 'Incremental Upsert (Merge on Primary Key)'), ('full_refresh', 'Full Overwrite (Truncate & Replace)'), ('append_only', 'Append-Only (Time-Series Event Log)'), ('delta_sharing', 'Delta Sharing Open Protocol Feed'), ('direct_query_federation', 'Direct Query Virtualization View')]`
  - `AUTH_METHOD_CHOICES = [('service_account_key', 'Service Account Key (JSON / PEM)'), ('snowflake_keypair', 'Snowflake Key-Pair RSA Authentication'), ('oauth2_token', 'OAuth2 Client Credentials Grant'), ('iam_role_arn', 'AWS IAM Role ARN Delegation'), ('personal_access_token', 'Personal Access Token')]`
  - `SYNC_SCHEDULE_CHOICES = [('hourly', 'Hourly Sync'), ('every_4_hours', 'Every 4 Hours'), ('daily', 'Daily Sync (Nightly)'), ('weekly', 'Weekly Sync'), ('event_triggered', 'Triggered by ETL Pipeline Finish'), ('manual', 'Manual Execution Only')]`
  - `STATUS_CHOICES = [('idle', 'Idle (Scheduled)'), ('syncing', 'Syncing in Progress'), ('success', 'Last Sync Succeeded'), ('error', 'Last Sync Failed'), ('disabled', 'Sync Disabled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_warehouse_sync_endpoints')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120, blank=True)`
  - `target_warehouse`: `CharField(max_length=40, choices=TARGET_WAREHOUSE_CHOICES, default='snowflake')`
  - `sync_mode`: `CharField(max_length=40, choices=SYNC_MODE_CHOICES, default='incremental_merge')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='warehouse_syncs')`
  - `data_mart`: `ForeignKey('bi.DataMart', null=True, blank=True, on_delete=models.SET_NULL, related_name='warehouse_syncs')`
  - `destination_database`: `CharField(max_length=150, blank=True)`
  - `destination_schema`: `CharField(max_length=150, blank=True)`
  - `destination_table`: `CharField(max_length=150)`
  - `connection_config`: `JSONField(default=dict, blank=True)`
  - `auth_method`: `CharField(max_length=40, choices=AUTH_METHOD_CHOICES, default='service_account_key')`
  - `sync_schedule`: `CharField(max_length=30, choices=SYNC_SCHEDULE_CHOICES, default='daily')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='idle')`
  - `last_sync_at`: `DateTimeField(null=True, blank=True)`
  - `last_sync_duration_ms`: `PositiveIntegerField(default=0)`
  - `last_rows_synced`: `PositiveIntegerField(default=0)`
  - `total_rows_synced`: `PositiveBigIntegerField(default=0)`
  - `last_error_message`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_warehouse_syncs')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsnc_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bsnc_ten_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bsnc_ten_stat')`
  - `Index(fields=['tenant', 'target_warehouse'], name='idx_bsnc_ten_wh')`
  - `Index(fields=['tenant', 'semantic_model'], name='idx_bsnc_ten_sem')`
  - `Index(fields=['tenant', 'data_mart'], name='idx_bsnc_ten_mart')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bsnc_ten_created')`

---

### 1.3 `BiWebhookSubscription` (`apps/bi/models/IntegrationHub/BiWebhookSubscriptions.py`)
- **Table:** `bi_webhook_subscription`
- **Number Prefix:** `BWHK` (`BWHK-00001`)
- **CHOICES:**
  - `PAYLOAD_FORMAT_CHOICES = [('standard_json', 'NavERP Standard Analytical JSON'), ('cloudevents_v1', 'CloudEvents v1.0 Standard'), ('slack_compatible', 'Slack Block Kit Compatible'), ('compact_minimal', 'Compact Minimalist Payload')]`
  - `STATUS_CHOICES = [('active', 'Active (Receiving Events)'), ('suspended', 'Suspended (Excessive Consecutive Failures)'), ('failing', 'Degraded (Intermittent 5xx Errors)'), ('disabled', 'Disabled by Administrator')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_webhook_subscriptions')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `endpoint_url`: `URLField(max_length=500)`
  - `secret_token`: `CharField(max_length=128)`
  - `event_types`: `JSONField(default=list, blank=True)`
  - `payload_format`: `CharField(max_length=30, choices=PAYLOAD_FORMAT_CHOICES, default='standard_json')`
  - `custom_headers`: `JSONField(default=dict, blank=True)`
  - `max_retries`: `PositiveIntegerField(default=3)`
  - `timeout_seconds`: `PositiveIntegerField(default=10)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='active')`
  - `consecutive_failures`: `PositiveIntegerField(default=0)`
  - `last_triggered_at`: `DateTimeField(null=True, blank=True)`
  - `last_response_code`: `PositiveIntegerField(null=True, blank=True)`
  - `last_response_time_ms`: `PositiveIntegerField(default=0)`
  - `last_error_log`: `TextField(blank=True)`
  - `total_deliveries`: `PositiveIntegerField(default=0)`
  - `is_active`: `BooleanField(default=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_created_webhooks')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bwhk_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bwhk_ten_stat')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bwhk_ten_act')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bwhk_ten_created')`

---

### 1.4 `BiExtensionPlugin` (`apps/bi/models/IntegrationHub/BiExtensionPlugins.py`)
- **Table:** `bi_extension_plugin`
- **Number Prefix:** `BEXT` (`BEXT-00001`)
- **CHOICES:**
  - `PLUGIN_TYPE_CHOICES = [('custom_visual', 'Custom Visualization Canvas Component'), ('connector_plugin', 'Third-Party Data Connector Plug-in'), ('transformation_script', 'Custom ETL Transformation Step'), ('dashboard_extension', 'Interactive Dashboard Extension Action'), ('metric_provider', 'External Metric & Benchmark Provider')]`
  - `CATEGORY_CHOICES = [('visualization', 'Charts & Visual Displays'), ('data_integration', 'Ingestion & Reverse ETL'), ('governance', 'Data Governance & Quality'), ('advanced_analytics', 'Predictive & Statistical Tools'), ('workflow_action', 'Operational Closed-Loop Actions')]`
  - `STATUS_CHOICES = [('installed', 'Installed (Not Enabled)'), ('enabled', 'Enabled & Active'), ('disabled', 'Disabled by Administrator'), ('deprecated', 'Deprecated Version'), ('quarantined', 'Quarantined (Security Flagged)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_extension_plugins')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `plugin_identifier`: `CharField(max_length=120)`
  - `version`: `CharField(max_length=30, default='1.0.0')`
  - `plugin_type`: `CharField(max_length=40, choices=PLUGIN_TYPE_CHOICES, default='custom_visual')`
  - `category`: `CharField(max_length=40, choices=CATEGORY_CHOICES, default='visualization')`
  - `description`: `TextField(blank=True)`
  - `author_name`: `CharField(max_length=150)`
  - `homepage_url`: `URLField(max_length=500, blank=True)`
  - `repository_url`: `URLField(max_length=500, blank=True)`
  - `license`: `CharField(max_length=60, default='MIT')`
  - `manifest_metadata`: `JSONField(default=dict, blank=True)`
  - `config_schema`: `JSONField(default=dict, blank=True)`
  - `current_config`: `JSONField(default=dict, blank=True)`
  - `permissions_required`: `JSONField(default=list, blank=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='installed')`
  - `is_verified`: `BooleanField(default=False)`
  - `is_system_plugin`: `BooleanField(default=False)`
  - `installed_at`: `DateTimeField(auto_now_add=True)`
  - `installed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_installed_plugins')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bext_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'plugin_identifier'], name='bi_bext_ten_ident_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bext_ten_stat')`
  - `Index(fields=['tenant', 'plugin_type'], name='idx_bext_ten_type')`
  - `Index(fields=['tenant', 'category'], name='idx_bext_ten_cat')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bext_ten_created')`

---

## 2. Form Specifications Contract

### 2.1 `IntegrationConnectorForm`
- **Model:** `IntegrationConnector`
- **Fields:** `['name', 'slug', 'description', 'connector_type', 'target_system', 'sync_direction', 'connection_config', 'auth_type', 'auth_credentials', 'message_format', 'sync_interval', 'status', 'is_enabled']`
- **Exclusions:** `['tenant', 'number', 'health_status', 'last_heartbeat_at', 'last_sync_at', 'total_messages_processed', 'error_message', 'created_by', 'created_at', 'updated_at']`

### 2.2 `WarehouseSyncEndpointForm`
- **Model:** `WarehouseSyncEndpoint`
- **Fields:** `['name', 'slug', 'target_warehouse', 'sync_mode', 'semantic_model', 'data_mart', 'destination_database', 'destination_schema', 'destination_table', 'connection_config', 'auth_method', 'sync_schedule', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'status', 'last_sync_at', 'last_sync_duration_ms', 'last_rows_synced', 'total_rows_synced', 'last_error_message', 'owner', 'created_at', 'updated_at']`
- **Querysets:** `semantic_model` and `data_mart` filtered strictly by `tenant=request.tenant`.

### 2.3 `BiWebhookSubscriptionForm`
- **Model:** `BiWebhookSubscription`
- **Fields:** `['name', 'endpoint_url', 'secret_token', 'event_types', 'payload_format', 'custom_headers', 'max_retries', 'timeout_seconds', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'status', 'consecutive_failures', 'last_triggered_at', 'last_response_code', 'last_response_time_ms', 'last_error_log', 'total_deliveries', 'created_by', 'created_at', 'updated_at']`

### 2.4 `BiExtensionPluginForm`
- **Model:** `BiExtensionPlugin`
- **Fields:** `['name', 'plugin_identifier', 'version', 'plugin_type', 'category', 'description', 'author_name', 'homepage_url', 'repository_url', 'license', 'manifest_metadata', 'config_schema', 'current_config', 'permissions_required', 'status', 'is_verified']`
- **Exclusions:** `['tenant', 'number', 'installed_at', 'installed_by', 'is_system_plugin', 'created_at', 'updated_at']`

---

## 3. Views, URLs & Context Keys Contract

### 3.1 `IntegrationConnector` Views
- `bi:integration_connector_list` (`/bi/integrations/connectors/`)
  - **Context Keys:** `connectors`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `active_count`, `error_count`, `search_query`, `connector_type`, `target_system`, `status`, `type_choices`, `target_choices`, `status_choices`
- `bi:integration_connector_detail` (`/bi/integrations/connectors/<int:pk>/`)
  - **Context Keys:** `connector`
- `bi:integration_connector_create` (`/bi/integrations/connectors/create/`)
  - **Context Keys:** `form`, `is_create`
- `bi:integration_connector_edit` (`/bi/integrations/connectors/<int:pk>/edit/`)
  - **Context Keys:** `form`, `connector`, `is_create`
- `bi:integration_connector_delete` (`/bi/integrations/connectors/<int:pk>/delete/`) — POST only
- `bi:integration_connector_ping` (`/bi/integrations/connectors/<int:pk>/ping/`) — POST only

### 3.2 `WarehouseSyncEndpoint` Views
- `bi:warehouse_sync_endpoint_list` (`/bi/integrations/warehouse-syncs/`)
  - **Context Keys:** `sync_endpoints`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `success_count`, `error_count`, `search_query`, `target_warehouse`, `sync_mode`, `status`, `warehouse_choices`, `mode_choices`, `status_choices`
- `bi:warehouse_sync_endpoint_detail` (`/bi/integrations/warehouse-syncs/<int:pk>/`)
  - **Context Keys:** `sync_endpoint`
- `bi:warehouse_sync_endpoint_create` (`/bi/integrations/warehouse-syncs/create/`)
  - **Context Keys:** `form`, `is_create`
- `bi:warehouse_sync_endpoint_edit` (`/bi/integrations/warehouse-syncs/<int:pk>/edit/`)
  - **Context Keys:** `form`, `sync_endpoint`, `is_create`
- `bi:warehouse_sync_endpoint_delete` (`/bi/integrations/warehouse-syncs/<int:pk>/delete/`) — POST only
- `bi:warehouse_sync_endpoint_trigger` (`/bi/integrations/warehouse-syncs/<int:pk>/trigger/`) — POST only

### 3.3 `BiWebhookSubscription` Views
- `bi:bi_webhook_subscription_list` (`/bi/integrations/webhooks/`)
  - **Context Keys:** `webhooks`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `active_count`, `failing_count`, `search_query`, `payload_format`, `status`, `format_choices`, `status_choices`
- `bi:bi_webhook_subscription_detail` (`/bi/integrations/webhooks/<int:pk>/`)
  - **Context Keys:** `webhook`
- `bi:bi_webhook_subscription_create` (`/bi/integrations/webhooks/create/`)
  - **Context Keys:** `form`, `is_create`
- `bi:bi_webhook_subscription_edit` (`/bi/integrations/webhooks/<int:pk>/edit/`)
  - **Context Keys:** `form`, `webhook`, `is_create`
- `bi:bi_webhook_subscription_delete` (`/bi/integrations/webhooks/<int:pk>/delete/`) — POST only
- `bi:bi_webhook_subscription_ping` (`/bi/integrations/webhooks/<int:pk>/ping/`) — POST only

### 3.4 `BiExtensionPlugin` Views
- `bi:bi_extension_plugin_list` (`/bi/integrations/plugins/`)
  - **Context Keys:** `plugins`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `enabled_count`, `verified_count`, `search_query`, `plugin_type`, `category`, `status`, `type_choices`, `category_choices`, `status_choices`
- `bi:bi_extension_plugin_detail` (`/bi/integrations/plugins/<int:pk>/`)
  - **Context Keys:** `plugin`
- `bi:bi_extension_plugin_create` (`/bi/integrations/plugins/create/`)
  - **Context Keys:** `form`, `is_create`
- `bi:bi_extension_plugin_edit` (`/bi/integrations/plugins/<int:pk>/edit/`)
  - **Context Keys:** `form`, `plugin`, `is_create`
- `bi:bi_extension_plugin_delete` (`/bi/integrations/plugins/<int:pk>/delete/`) — POST only
- `bi:bi_extension_plugin_toggle` (`/bi/integrations/plugins/<int:pk>/toggle/`) — POST only

---

## 4. Navigation LIVE_LINKS Contract

In `apps/core/navigation.py`:
```python
"10.19": {
    "ERP & Application Connectors": "bi:integration_connector_list",
    "External BI & Warehouse Sync": "bi:warehouse_sync_endpoint_list",
    "Open APIs & Webhooks": "bi:bi_webhook_subscription_list",
    "Streaming & Message Queues": "bi:integration_connector_list",
    "Marketplace & Extensions": "bi:bi_extension_plugin_list",
    # Aliases
    "Integration Connectors": "bi:integration_connector_list",
    "Warehouse Sync Endpoints": "bi:warehouse_sync_endpoint_list",
    "Webhook Subscriptions": "bi:bi_webhook_subscription_list",
    "Extension Plugins": "bi:bi_extension_plugin_list",
    "API & Integration Hub": "bi:integration_connector_list",
},
```

---

## 5. Templates Contract

Paths under `templates/bi/integration_hub/`:
1. `integration_connector/`
   - `list.html`
   - `detail.html`
   - `form.html`
2. `warehouse_sync_endpoint/`
   - `list.html`
   - `detail.html`
   - `form.html`
3. `bi_webhook_subscription/`
   - `list.html`
   - `detail.html`
   - `form.html`
4. `bi_extension_plugin/`
   - `list.html`
   - `detail.html`
   - `form.html`

Badges strictly use `theme.css` tokens: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`. No unstyled `-success` or `-danger`.

---

## 6. Security & Multi-Tenancy Invariants

1. All ORM queries filtered strictly by `tenant=request.tenant`.
2. All form saves associate instance with `request.tenant` (and `request.user` for created_by/owner).
3. Cross-tenant IDOR access (GET or POST with tenant B's PK as tenant A) MUST return 404.
4. Mutation endpoints (create, edit, delete, actions) protected by `@login_required` and audit logs written via `apps.core.utils.write_audit_log`.
