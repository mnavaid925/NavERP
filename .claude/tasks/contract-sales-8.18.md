# Build Contract — Sales 8.18 Integration & API Hub (`sales`)

> Frozen 2026-10-28 against the live tree at BASE commit `bbd7b52f0fb78aa15695661dfc53e7ea0d5dc2a2`.
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.
> Phase 4 reviews `bbd7b52f...HEAD`.

---

## 0. Scope & Capability Coverage

Five NavERP.md §8.18 capability bullets (`NavERP.md:1434–1440`) map to **4 owned models + 1 Hub Dashboard + 5 category lens routes + 2 action routes**:

| NavERP.md bullet (character-for-character) | What 8.18 owns | URL Name |
|---|---|---|
| **ERP Integration** — SAP, Oracle, NetSuite, and Microsoft Dynamics for order-to-cash synchronization. | `category="erp"` connectors (`sap·oracle·netsuite·dynamics_finance`), order-to-cash field mappings & sync jobs | `sales:sic_erp_list` |
| **Marketing Automation** — HubSpot, Marketo, Pardot, and Eloqua bidirectional sync. | `category="marketing"` connectors (`hubspot·marketo·pardot·eloqua`), lead/contact sync jobs | `sales:sic_marketing_list` |
| **Communication Platforms** — Slack, Microsoft Teams, Zoom, and telephony system integration. | `category="communication"` connectors (`slack·teams·zoom·telephony`), deal alert triggers & call logging | `sales:sic_communication_list` |
| **Business Intelligence** — Tableau, Power BI, Looker, and Snowflake data warehouse feeds. | `category="bi_warehouse"` connectors (`tableau·powerbi·looker·snowflake`), dataset export jobs | `sales:sic_bi_list` |
| **E-Signature & Document** — DocuSign, Adobe Sign, PandaDoc, and contract lifecycle management (CLM) connectors. | `category="esignature"` connectors (`docusign·adobesign·pandadoc·clm`), envelope status sync jobs | `sales:sic_esignature_list` |
| **Central Integration Hub & Monitoring Console** | KPI aggregation across connectors, sync jobs, and simulated execution runs | `sales:integration_hub` |

### Architectural Rulings & Invariants

1. **L55 Coexistence (5th Integration Register across NavERP):**
   - Four modules previously shipped integration registers: SCM 4.19 `IntegrationEndpoint` [`CNX-`], Inventory 5.19 `IntegrationChannel` [`INT-`], Accounting 2.15 `IntegrationConfig`, and Projects 7.18 `ProjectIntegrationConnector` [`IXC-`].
   - **Sales 8.18 ships `SalesIntegrationConnector` [`SIC-`]** specifically answering revenue operations, order-to-cash, lead sync, sales alerts, BI pipelines, and e-signature envelope tracking.
   - 8.18 FKs none of the previous registers and does not re-declare their models. Coexistence is intentional.
2. **Zero Outbound HTTP (Honest Diagnostic Status):**
   - No external HTTP requests are dispatched during model saves, views, or test runs.
   - `SalesSyncRun.status = "simulated"` is the honest diagnostic state and is asserted in tests.
3. **Secret Encryption at Rest (L20 / L25):**
   - Sensitive credentials (tokens, client secrets) are encrypted at rest using `apps.core.crypto.encrypt`.
   - Plaintext passwords are submitted via a custom form field `credential_plaintext` (which encrypts into `credential_encrypted`) and are never rendered back into forms or template HTML. Detail views display masked `••••••••`.
4. **Number Prefixes:**
   - `SalesIntegrationConnector`: `SIC-`
   - `SalesFieldMapping`: unnumbered child table (inherits `TenantOwned`)
   - `SalesSyncJob`: `SSJ-`
   - `SalesSyncRun`: `SSR-`
   - All prefixes verified 100% collision-free repo-wide.
5. **Audit Trail:**
   - Privilege writes use `write_audit_log` (`apps.core.utils`) with verbs `<= 10` characters (`create`, `update`, `delete`, `test`, `run`).
6. **Badge Classes (L33):**
   - Strictly color-named: `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`.

---

## 1. Verified Spine & Sibling Relationships

- `core.Tenant` (`apps.core.models.Tenant`)
- `core.Party` (`apps.core.models.Party`)
- `accounts.User` (`settings.AUTH_USER_MODEL`)
- `crm.Opportunity` (`apps.crm.models.SalesForceAutomation.Opportunities.Opportunity`)
- `scm.SalesOrder` (`apps.scm.models.OrderManagement.SalesOrders.SalesOrder`)
- `sales.Lead` (`apps.sales.models.LeadManagement.Leads.Lead`)
- `sales.CPQQuote` (`apps.sales.models.QuoteProposalCPQ.CPQQuotes.CPQQuote`)
- `sales.CustomerContract` (`apps.sales.models.ContractSubscriptionManagement.CustomerContracts.CustomerContract`)

All relationships across modules use string references (`'core.Party'`, `'scm.SalesOrder'`, `'sales.SalesIntegrationConnector'`).

---

## 2. Model Specifications (`apps/sales/models/IntegrationApiHub/`)

### 2.1 `SalesIntegrationConnector` (`Connectors.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "SIC"`
- **Choices:**
  - `CATEGORY_CHOICES = [("erp", "ERP & Financial"), ("marketing", "Marketing Automation"), ("communication", "Communication & Telephony"), ("bi_warehouse", "BI & Data Warehouse"), ("esignature", "E-Signature & CLM"), ("custom", "Custom / Other")]`
  - `PROVIDER_CHOICES = [("sap", "SAP ERP"), ("oracle", "Oracle Fusion/EBS"), ("netsuite", "Oracle NetSuite"), ("dynamics_finance", "Microsoft Dynamics 365 Finance"), ("hubspot", "HubSpot CRM/Marketing"), ("marketo", "Adobe Marketo Engage"), ("pardot", "Salesforce Marketing Cloud Account Engagement (Pardot)"), ("eloqua", "Oracle Eloqua"), ("slack", "Slack"), ("teams", "Microsoft Teams"), ("zoom", "Zoom Phone"), ("telephony", "Telephony / PBX System"), ("tableau", "Tableau"), ("powerbi", "Microsoft Power BI"), ("looker", "Looker (Google Cloud)"), ("snowflake", "Snowflake Data Warehouse"), ("docusign", "DocuSign eSignature"), ("adobesign", "Adobe Sign"), ("pandadoc", "PandaDoc"), ("clm", "Contract Lifecycle Management (CLM)"), ("custom", "Custom REST/GraphQL Endpoint")]`
  - `ENVIRONMENT_CHOICES = [("production", "Production"), ("sandbox", "Sandbox / Staging"), ("development", "Development / Test")]`
  - `AUTH_METHOD_CHOICES = [("api_key", "API Key / Token"), ("oauth2", "OAuth 2.0 (Bearer Token)"), ("basic_auth", "HTTP Basic Auth"), ("webhook_secret", "HMAC Webhook Secret"), ("none", "None / Public")]`
  - `HEALTH_STATUS_CHOICES = [("connected", "Connected & Healthy"), ("degraded", "Degraded Performance"), ("error", "Connection Error"), ("offline", "Offline / Paused"), ("untested", "Untested / Draft")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_integration_connectors')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `category`: `CharField(max_length=20, choices=CATEGORY_CHOICES, default="erp")`
  - `provider`: `CharField(max_length=30, choices=PROVIDER_CHOICES, default="sap")`
  - `environment`: `CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="production")`
  - `base_url`: `URLField(max_length=255, blank=True, default="")`
  - `auth_method`: `CharField(max_length=20, choices=AUTH_METHOD_CHOICES, default="api_key")`
  - `credential_encrypted`: `TextField(blank=True, default="")`
  - `remote_scope_ref`: `CharField(max_length=255, blank=True, default="")`
  - `health_status`: `CharField(max_length=20, choices=HEALTH_STATUS_CHOICES, default="untested")`
  - `last_health_check_at`: `DateTimeField(null=True, blank=True)`
  - `last_error_message`: `TextField(blank=True, default="")`
  - `is_active`: `BooleanField(default=True)`
  - `notes`: `TextField(blank=True, default="")`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_sic_tenant_num_uniq")`
  - `Index(fields=["tenant", "category", "is_active"], name="sales_sic_cat_act_idx")`
  - `Index(fields=["tenant", "provider"], name="sales_sic_provider_idx")`
- **Form exclusions:** `tenant`, `number`, `credential_encrypted`, `last_health_check_at`, `last_error_message`

### 2.2 `SalesFieldMapping` (`FieldMappings.py`)
- **Inheritance:** `TenantOwned`
- **Choices:**
  - `TARGET_ENTITY_CHOICES = [("lead", "Sales Lead"), ("account", "Account (core.Party)"), ("opportunity", "Opportunity"), ("quote", "CPQ Quote"), ("order", "Sales Order"), ("contract", "Customer Contract"), ("analytics", "Analytics & Snapshot")]`
  - `DIRECTION_CHOICES = [("bidirectional", "Two-Way Bidirectional (⇄)"), ("outbound", "Outbound NavERP → Remote (→)"), ("inbound", "Inbound Remote → NavERP (←)")]`
  - `TRANSFORM_CHOICES = [("none", "Direct / None"), ("uppercase", "Upper Case"), ("lowercase", "Lower Case"), ("boolean_to_int", "Boolean to Integer (0/1)"), ("json_extract", "JSON Key Extract"), ("currency_round", "Round Currency (2 decimals)"), ("value_map", "Value Map Picklist Translation")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_field_mappings')`
  - `connector`: `ForeignKey('sales.SalesIntegrationConnector', on_delete=models.CASCADE, related_name='field_mappings')`
  - `target_entity`: `CharField(max_length=30, choices=TARGET_ENTITY_CHOICES, default="order")`
  - `local_field`: `CharField(max_length=100)`
  - `remote_field`: `CharField(max_length=100)`
  - `direction`: `CharField(max_length=20, choices=DIRECTION_CHOICES, default="bidirectional")`
  - `transform_rule`: `CharField(max_length=30, choices=TRANSFORM_CHOICES, default="none")`
  - `value_map`: `JSONField(default=dict, blank=True)`
  - `default_value`: `CharField(max_length=255, blank=True, default="")`
  - `is_key`: `BooleanField(default=False)`
  - `is_required`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "connector", "target_entity", "local_field", "remote_field"], name="sales_sfm_target_fields_uniq")`
  - `Index(fields=["tenant", "connector", "target_entity"], name="sales_sfm_conn_ent_idx")`
- **Form exclusions:** `tenant`

### 2.3 `SalesSyncJob` (`SyncJobs.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "SSJ"`
- **Choices:**
  - `ENTITY_SCOPE_CHOICES = [("order_to_cash", "Order-to-Cash (ERP)"), ("lead_lifecycle", "Lead & Contact Lifecycle (Marketing)"), ("deal_alerts", "Deal & Milestone Alerts (Comms)"), ("bi_warehouse_feed", "BI & Data Warehouse Export"), ("contract_envelope_status", "E-Signature & Contract Envelopes")]`
  - `DIRECTION_CHOICES = [("bidirectional", "Two-Way Bidirectional (⇄)"), ("outbound", "Outbound NavERP → Remote (→)"), ("inbound", "Inbound Remote → NavERP (←)")]`
  - `CONFLICT_POLICY_CHOICES = [("last_updated_wins", "Last Updated Timestamp Wins"), ("local_wins", "NavERP Record Wins"), ("remote_wins", "Remote System Wins"), ("flag_manual", "Flag Conflict for Manual Review")]`
  - `CADENCE_CHOICES = [("realtime_event", "Real-time Event-Driven"), ("hourly", "Hourly Batch"), ("daily", "Daily Scheduled"), ("weekly", "Weekly Scheduled"), ("manual_only", "Manual On-Demand Only")]`
  - `STATUS_CHOICES = [("active", "Active / Scheduled"), ("paused", "Paused / Inactive"), ("error", "Execution Error")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_sync_jobs')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `connector`: `ForeignKey('sales.SalesIntegrationConnector', on_delete=models.CASCADE, related_name='sync_jobs')`
  - `entity_scope`: `CharField(max_length=30, choices=ENTITY_SCOPE_CHOICES, default="order_to_cash")`
  - `sync_direction`: `CharField(max_length=20, choices=DIRECTION_CHOICES, default="outbound")`
  - `conflict_policy`: `CharField(max_length=30, choices=CONFLICT_POLICY_CHOICES, default="last_updated_wins")`
  - `cadence`: `CharField(max_length=30, choices=CADENCE_CHOICES, default="hourly")`
  - `filter_expression`: `CharField(max_length=255, blank=True, default="")`
  - `batch_size`: `PositiveIntegerField(default=100)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active")`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `next_run_at`: `DateTimeField(null=True, blank=True)`
  - `total_runs_count`: `PositiveIntegerField(default=0)`
  - `total_records_synced`: `PositiveIntegerField(default=0)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_ssj_tenant_num_uniq")`
  - `Index(fields=["tenant", "connector", "status"], name="sales_ssj_conn_stat_idx")`
  - `Index(fields=["tenant", "entity_scope"], name="sales_ssj_scope_idx")`
- **Form exclusions:** `tenant`, `number`, `last_run_at`, `next_run_at`, `total_runs_count`, `total_records_synced`

### 2.4 `SalesSyncRun` (`SyncRuns.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "SSR"`
- **Choices:**
  - `RUN_TYPE_CHOICES = [("manual", "Manual On-Demand"), ("scheduled", "Scheduled Batch"), ("webhook", "Inbound Webhook"), ("test_ping", "Health Ping / Test")]`
  - `STATUS_CHOICES = [("simulated", "Simulated (Honest Diagnostic)"), ("completed", "Completed Successfully"), ("partial", "Completed with Warnings"), ("failed", "Execution Failed")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_sync_runs')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `connector`: `ForeignKey('sales.SalesIntegrationConnector', on_delete=models.CASCADE, related_name='sync_runs')`
  - `job`: `ForeignKey('sales.SalesSyncJob', on_delete=models.SET_NULL, null=True, blank=True, related_name='sync_runs')`
  - `run_type`: `CharField(max_length=20, choices=RUN_TYPE_CHOICES, default="manual")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="simulated")`
  - `started_at`: `DateTimeField(default=timezone.now)`
  - `finished_at`: `DateTimeField(null=True, blank=True)`
  - `records_read`: `PositiveIntegerField(default=0)`
  - `records_written`: `PositiveIntegerField(default=0)`
  - `records_failed`: `PositiveIntegerField(default=0)`
  - `records_skipped`: `PositiveIntegerField(default=0)`
  - `error_log`: `TextField(blank=True, default="")`
  - `summary_payload`: `JSONField(default=dict, blank=True)`
  - `triggered_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_sync_runs')`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_ssr_tenant_num_uniq")`
  - `Index(fields=["tenant", "connector", "status"], name="sales_ssr_conn_stat_idx")`
  - `Index(fields=["tenant", "job", "-started_at"], name="sales_ssr_job_start_idx")`
- **Form exclusions:** `tenant`, `number`, `started_at`, `finished_at`

---

## 3. URL Names & Routes (`apps/sales/urls/IntegrationApiHub/`)

All registered under `sales:` namespace:

```python
urlpatterns = [
    # Dashboard & Category Lenses
    path("hub/", hub_dashboard, name="integration_hub"),
    path("connectors/erp/", sic_erp_list, name="sic_erp_list"),
    path("connectors/marketing/", sic_marketing_list, name="sic_marketing_list"),
    path("connectors/communication/", sic_communication_list, name="sic_communication_list"),
    path("connectors/bi/", sic_bi_list, name="sic_bi_list"),
    path("connectors/esignature/", sic_esignature_list, name="sic_esignature_list"),

    # SalesIntegrationConnector CRUD + Action
    path("connectors/", sic_list, name="sic_list"),
    path("connectors/create/", sic_create, name="sic_create"),
    path("connectors/<int:pk>/", sic_detail, name="sic_detail"),
    path("connectors/<int:pk>/edit/", sic_edit, name="sic_edit"),
    path("connectors/<int:pk>/delete/", sic_delete, name="sic_delete"),
    path("connectors/<int:pk>/test/", sic_test, name="sic_test"),

    # SalesFieldMapping CRUD
    path("mappings/", sfm_list, name="sfm_list"),
    path("mappings/create/", sfm_create, name="sfm_create"),
    path("mappings/<int:pk>/", sfm_detail, name="sfm_detail"),
    path("mappings/<int:pk>/edit/", sfm_edit, name="sfm_edit"),
    path("mappings/<int:pk>/delete/", sfm_delete, name="sfm_delete"),

    # SalesSyncJob CRUD + Action
    path("jobs/", ssj_list, name="ssj_list"),
    path("jobs/create/", ssj_create, name="ssj_create"),
    path("jobs/<int:pk>/", ssj_detail, name="ssj_detail"),
    path("jobs/<int:pk>/edit/", ssj_edit, name="ssj_edit"),
    path("jobs/<int:pk>/delete/", ssj_delete, name="ssj_delete"),
    path("jobs/<int:pk>/trigger/", ssj_trigger, name="ssj_trigger"),

    # SalesSyncRun CRUD
    path("runs/", ssr_list, name="ssr_list"),
    path("runs/<int:pk>/", ssr_detail, name="ssr_detail"),
    path("runs/<int:pk>/delete/", ssr_delete, name="ssr_delete"),
]
```

---

## 4. Context Keys & View Contracts

| View Function | Template | Context Keys |
|---|---|---|
| `hub_dashboard` | `sales/integrationapihub/hub_dashboard.html` | `connectors_count`, `jobs_count`, `runs_count`, `healthy_count`, `active_jobs_count`, `recent_runs`, `erp_connectors`, `marketing_connectors`, `communication_connectors`, `bi_connectors`, `esignature_connectors` |
| `sic_list` | `sales/integrationapihub/connectors/list.html` | `connectors`, `page_obj`, `paginator`, `q`, `category`, `provider`, `health_status`, `category_choices`, `provider_choices`, `health_choices` |
| `sic_detail` | `sales/integrationapihub/connectors/detail.html` | `connector`, `field_mappings`, `sync_jobs`, `recent_runs` |
| `sic_create` / `sic_edit` | `sales/integrationapihub/connectors/form.html` | `form`, `is_edit`, `connector` |
| `sfm_list` | `sales/integrationapihub/fieldmappings/list.html` | `mappings`, `page_obj`, `paginator`, `q`, `connector_id`, `target_entity`, `direction`, `connectors`, `entity_choices`, `direction_choices` |
| `sfm_detail` | `sales/integrationapihub/fieldmappings/detail.html` | `mapping` |
| `sfm_create` / `sfm_edit` | `sales/integrationapihub/fieldmappings/form.html` | `form`, `is_edit`, `mapping` |
| `ssj_list` | `sales/integrationapihub/syncjobs/list.html` | `jobs`, `page_obj`, `paginator`, `q`, `connector_id`, `entity_scope`, `status`, `connectors`, `scope_choices`, `status_choices` |
| `ssj_detail` | `sales/integrationapihub/syncjobs/detail.html` | `job`, `recent_runs` |
| `ssj_create` / `ssj_edit` | `sales/integrationapihub/syncjobs/form.html` | `form`, `is_edit`, `job` |
| `ssr_list` | `sales/integrationapihub/syncruns/list.html` | `runs`, `page_obj`, `paginator`, `q`, `connector_id`, `job_id`, `status`, `run_type`, `connectors`, `jobs`, `status_choices`, `run_type_choices` |
| `ssr_detail` | `sales/integrationapihub/syncruns/detail.html` | `run` |

---

## 5. Navigation `LIVE_LINKS["8.18"]` Mapping

```python
LIVE_LINKS["8.18"] = {
    "ERP Integration": "sales:sic_erp_list",
    "Marketing Automation": "sales:sic_marketing_list",
    "Communication Platforms": "sales:sic_communication_list",
    "Business Intelligence": "sales:sic_bi_list",
    "E-Signature & Document": "sales:sic_esignature_list",
    "Integration Hub": "sales:integration_hub",
    "Connectors": "sales:sic_list",
    "Field Mappings": "sales:sfm_list",
    "Sync Jobs": "sales:ssj_list",
    "Sync Runs": "sales:ssr_list",
}
```
