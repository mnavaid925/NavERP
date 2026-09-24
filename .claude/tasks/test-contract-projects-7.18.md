# Test contract — Projects 7.18 Integration & API Hub (`projects`)

> Frozen against the current 7.18 implementation after Phase-5 review amendments. This is the
> shared contract for the four test writers; no `test_integrationapihub_*.py` file is part of this
> step.
>
> The test database is the project’s SQLite in-memory test configuration. The `db` fixture isolates
> each test transaction. Tests must not call `seed_projects`, use the development MariaDB, or
> depend on rows left by another test.

## 1. Scope and execution order

7.18 owns the project-scoped integration registers and simulated run log. It does not perform
outbound HTTP, schedule a worker, evaluate `filter_expression`, or post an accounting row. The
project’s `Project`, 7.17’s `ProjectWebhookEndpoint`, and the existing auth/tenant middleware are
the reused spine.

The development seeder is not a test fixture. Its documented 7.18 shape is 7 connectors, 30 mappings, 10 jobs (including a Jira `milestones` synchronization job), and 45 runs; tests must continue to build independent rows and must not call the seeder or assert its counts.

The only allowed files for this contract step are this document and the narrowly prefixed 7.18
append to `apps/projects/tests/conftest.py`. The existing dirty review file, `apps/core/**`, and
`templates/projects/reporting/**` are outside this step and must not be edited.

The later test lane order is mandatory:

1. `test_integrationapihub_models.py`
2. `test_integrationapihub_forms.py`
3. `test_integrationapihub_views.py`
4. `test_integrationapihub_security.py`
5. The full unfiltered `apps/projects` suite.

Every test function is named `test_integrationapihub_*`. Every module-level helper is named
`_integrationapihub_*`. Test-module-local payload, URL, and message helpers follow the same rule;
do not introduce generic helper names that can collide with sibling sub-modules.

Use the root fixtures rather than redefining them:

- Tenant A: `tenant_a`, `admin_user`, `member_user`, `client_a`, `member_client`.
- Tenant B: `tenant_b`, `admin_b`, `client_b`.
- Anonymous/CSRF/tenantless clients: `projectinitiation_anon_client`,
  `projectinitiation_csrf_client`, and `projectinitiation_tenantless_client`.
- A 7.17 webhook can be reused as `workflowautomation_webhook_a` or `_b` when the
  connector `notify_webhook` path is under test; no second webhook model is introduced.

## 2. Shared fixture contract

The following 7.18 helpers were appended to `apps/projects/tests/conftest.py`. They are the only
new shared names from this step.

### 2.1 Module helpers and constant

| Name | Signature | As-built behavior/defaults |
|---|---|---|
| `INTEGRATIONAPIHUB_PAGE_SIZE` | constant | `25`; every 7.18 list/monitor paginator uses 25. |
| `_integrationapihub_connector` | `(tenant, project=None, **overrides)` | Constructs and saves `ProjectIntegrationConnector`; default name is the next per-tenant `Integration connector NN`, domain `erp`, provider `sap`, bidirectional, API key, sandbox, unverified, active. Number is minted by `TenantNumbered.save()`. |
| `_integrationapihub_mapping` | `(tenant, connector, **overrides)` | Constructs and saves `ConnectorFieldMapping`; default fields are `task.field_NN` / `fields.FieldNN`, bidirectional, no transform, `{}` value map, both flags false. |
| `_integrationapihub_job` | `(tenant, connector, **overrides)` | Constructs and saves `ProjectSyncJob`; default name is the next per-connector `Sync job NN`, `tasks`, bidirectional, manual, no interval, manual conflict policy, batch 100, active. |
| `_integrationapihub_run` | `(tenant, job, **overrides)` | Calls `ProjectSyncRun.record(job=job, **overrides)`, never `objects.create()` or `bulk_create()`. Defaults are simulated/manual, no user, no direction override, all counters zero, empty errors/payload, attempt 1, no finish/retry stamp, duration 0. The `tenant` argument is a consistency assertion input but the model method correctly derives the tenant from `job`; it is not passed to `record()`. |

All four factories use ordinary `.save()`. Do not replace them with `bulk_create()` for numbered
models: `TenantNumbered.save()` is the number allocator. A run factory must always use
`ProjectSyncRun.record()` because that is the model’s declared sole writer path.

### 2.2 Public fixtures added

| Fixture | Dependencies | Shape |
|---|---|---|
| `integrationapihub_project_a` | `tenant_a`, `admin_user` | Active `Project` with approved charter, code `IHA-01`, name `Integration Hub Project A`. |
| `integrationapihub_project_b` | `tenant_b`, `admin_b` | Tenant-B equivalent, code `IHB-01`. |
| `integrationapihub_connector_a` | `tenant_a`, `admin_user`, project A | Project-scoped, active, `domain="erp"`, `provider="sap"`, `status="connected"`, owner `admin_user`, name `Acme ERP connector`. |
| `integrationapihub_connector_b` | `tenant_b`, `admin_b`, project B | Tenant-B project-scoped connector, `domain="crm"`, `provider="salesforce"`, `status="error"`, owner `admin_b`. |
| `integrationapihub_connector_workspace_a` | `tenant_a`, `admin_user` | `project=None`, storage/SharePoint, disconnected; deliberately has no sync job, making the `ixc_test` jobless branch reachable. |
| `integrationapihub_connector_credential_a` | `tenant_a`, `admin_user`, project A | Jira/devops connector with raw credential `provider-secret-1234` passed once; the model saves Fernet ciphertext. |
| `integrationapihub_mapping_a` | `tenant_a`, connector A | `task.status` → `fields.status.name`, `to_remote`, uppercase, non-empty value map, key and required. |
| `integrationapihub_mapping_b` | `tenant_b`, connector B | `client.name` → `Account.Name`, `from_remote`, trim, `{"Closed Won": "active"}`, key. |
| `integrationapihub_job_a` | `tenant_a`, connector A | `Acme task sync`, tasks, outbound, scheduled/60 minutes, local-wins, batch 50, active. |
| `integrationapihub_job_b` | `tenant_b`, connector B | `Globex issue sync`, issues, inbound, event, no interval, remote-wins, batch 25, inactive. |
| `integrationapihub_run_a` | `tenant_a`, `admin_user`, job A | Simulated/manual run with read/created/updated counters, payload excerpt, no-outbound error text, duration 25. |
| `integrationapihub_run_failed_a` | `tenant_a`, `admin_user`, job A | Failed/event run with `PARTNER_TIMEOUT`, failed records, payload excerpt, finish stamp, duration 1200. Use it for retry tests. |
| `integrationapihub_run_b` | `tenant_b`, `admin_b`, job B | Tenant-B success/schedule run with three read and three updated records. |

Tests that need several rows call the prefixed helpers with distinct names/local fields. They must
not make the shared fixture names generic. Tests that need a connector with no job can use
`integrationapihub_connector_workspace_a`; tests that need a jobless connector with a chosen
project can call `_integrationapihub_connector(..., project=..., name=...)`.

## 3. Models: exact as-built contract

All four models are imported from `apps.projects.models` through the 7.18 re-export block. The
sub-package `models/IntegrationApiHub/__init__.py` is intentionally empty of re-exports.

### 3.1 Common inheritance and numbering

`TenantOwned` supplies a non-null `core.Tenant` FK (`on_delete=CASCADE`, `related_name="+"`,
`db_index=True`) plus `created_at` and `updated_at`. `TenantNumbered` additionally supplies an
editable-false `number` CharField. On the first save of a numbered row, `TenantNumbered.save()`
calls `next_number(type(self), tenant, NUMBER_PREFIX)` and retries up to five times on an
`IntegrityError` collision. Numbers are per tenant and per model; a resave does not change an
existing number.

### 3.2 `ProjectIntegrationConnector` (`Connectors.py`, `IXC-`)

Inheritance: `TenantNumbered`; `NUMBER_PREFIX = "IXC"`; no project-owned `number` override.

Choices, in source order:

```text
DOMAIN_CHOICES = [
  ("erp", "ERP & Finance"), ("crm", "CRM"), ("hris", "HR & Talent"),
  ("devops", "DevOps"), ("storage", "File Storage"), ("custom", "Custom / Other"),
]
PROVIDER_CHOICES = [
  ("sap", "SAP"), ("oracle", "Oracle"), ("netsuite", "NetSuite"),
  ("dynamics", "Microsoft Dynamics"), ("workday", "Workday"),
  ("salesforce", "Salesforce"), ("hubspot", "HubSpot"),
  ("dynamics_sales", "Dynamics Sales"), ("bamboohr", "BambooHR"),
  ("adp", "ADP"), ("jira", "Jira"), ("github", "GitHub"),
  ("gitlab", "GitLab"), ("azure_devops", "Azure DevOps"),
  ("ci_cd", "CI/CD Pipeline"), ("sharepoint", "SharePoint"),
  ("google_drive", "Google Drive"), ("dropbox", "Dropbox"),
  ("box", "Box"), ("custom", "Custom / Other"),
]
DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound"),
                     ("bidirectional", "Bidirectional")]
AUTH_METHOD_CHOICES = [("none", "None"), ("api_key", "API Key"),
                       ("basic", "Basic Auth"), ("oauth2", "OAuth 2.0"),
                       ("pat", "Personal Access Token")]
TRIGGER_MODE_CHOICES = [("manual", "Manual"), ("scheduled", "Scheduled"),
                        ("event", "Event-driven")]
ENVIRONMENT_CHOICES = [("production", "Production"), ("sandbox", "Sandbox")]
STATUS_CHOICES = [("unverified", "Unverified"), ("connected", "Connected"),
                  ("error", "Error"), ("disabled", "Disabled"),
                  ("disconnected", "Disconnected")]
```

Fields:

| Field | Exact definition |
|---|---|
| `project` | FK `projects.Project`, CASCADE, nullable/blank, related name `integration_connectors`; null means workspace-wide. |
| `name` | required `CharField(max_length=120)`. |
| `domain` | `CharField(max_length=12, choices=DOMAIN_CHOICES, default="custom")`. |
| `provider` | `CharField(max_length=20, choices=PROVIDER_CHOICES, blank=True, default="custom")`. |
| `direction` | `CharField(max_length=14, choices=DIRECTION_CHOICES, default="bidirectional")`. |
| `auth_method` | `CharField(max_length=10, choices=AUTH_METHOD_CHOICES, default="api_key")`. |
| `base_url` | `CharField(max_length=500, blank=True)`; configuration reference only, never fetched. |
| `remote_scope_ref` | `CharField(max_length=200, blank=True)`. |
| `trigger_mode` | `CharField(max_length=10, choices=TRIGGER_MODE_CHOICES, default="manual")`. |
| `schedule_note` | `CharField(max_length=200, blank=True)`. |
| `environment` | `CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default="sandbox")`. |
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="unverified")`. |
| `is_active` | `BooleanField(default=True)`. |
| `credential` | `CharField(max_length=512, blank=True, editable=False)`; Fernet ciphertext at rest. |
| `last_sync_at` | nullable/blank `DateTimeField(editable=False)`. |
| `last_success_at` | nullable/blank `DateTimeField(editable=False)`. |
| `consecutive_failures` | `PositiveIntegerField(default=0, editable=False)`. |
| `notify_webhook` | nullable/blank FK `projects.ProjectWebhookEndpoint`, SET_NULL, related name `notify_connectors`. |
| `owner` | nullable/blank FK to `settings.AUTH_USER_MODEL`, SET_NULL, related name `owned_project_connectors`. |
| `notes` | `TextField(blank=True)`. |

`Meta` is `ordering = ["-created_at", "-id"]`,
`unique_together = [("tenant", "number"), ("tenant", "project", "name")]`, with these named
indexes:

- `ixc_tnt_domain_idx` on `tenant, domain`
- `ixc_tnt_status_idx` on `tenant, status`
- `ixc_tnt_prj_idx` on `tenant, project`
- `ixc_tnt_active_idx` on `tenant, is_active`

`__str__()` is `"{number} — {name} ({provider display})"`.

`clean()` calls `super().clean()` and raises a field error when either a selected `project` or
`notify_webhook` has a different `tenant_id`. Because the database `unique_together` does not bind
NULL project names, a row with `project_id is None` and a nonblank name also gets a field error if
another workspace-wide connector in the same tenant has the same name. The sibling query excludes
the current pk when editing. The model does not call `clean()` automatically from `save()`; tests
must call `clean()`/`full_clean()` explicitly for validation assertions.

Credential methods and properties:

- `set_credential(raw)` stores `encrypt(raw)` when raw is truthy and clears to `""` otherwise.
- `get_credential()` returns plaintext, or `""` when unset; a rotated-key decryption error is
  allowed to propagate.
- `credential_set` is `bool(self.credential)`.
- `credential_masked` returns `(none)` when blank, `(set — legacy plaintext)` for unmarked
  nonblank data, `(set — undecryptable with the current key)` when decryption raises, otherwise a
  bullet-mask plus the last four characters (or just four bullets for a shorter value).
- `save()` encrypts a nonblank credential through the model choke point; repeated saves are
  idempotent for marked Fernet values.
- `status_badge`: connected `badge-green`, error `badge-red`, unverified `badge-slate`, disabled
  `badge-muted`, disconnected `badge-amber`, unknown `badge-slate`.
- `domain_badge`: custom `badge-slate`; every other domain `badge-info`.
- `health_badge`: no `last_sync_at` → `badge-slate`; otherwise failures `>=3` → `badge-red`,
  failures `1..2` → `badge-amber`, zero failures → `badge-green`.

There is no `due_rotation` model property, form field, or current 7.18 view context key. The old
dead key was removed; tests must not assert it.

### 3.3 `ConnectorFieldMapping` (`FieldMappings.py`, unnumbered)

Inheritance: `TenantOwned`; deliberately no `NUMBER_PREFIX` and no `number` field. It is a child of
a connector and is identified by its row/connector rather than a document number.

Choices:

```text
DIRECTION_CHOICES = [("to_remote", "Local → Remote"),
                     ("from_remote", "Remote → Local"),
                     ("both", "Bidirectional")]
TRANSFORM_CHOICES = [("none", "None"), ("upper", "Uppercase"),
                     ("lower", "Lowercase"), ("trim", "Trim"),
                     ("date_iso", "ISO date"), ("number", "Number"),
                     ("bool", "Boolean")]
```

Fields: required connector FK CASCADE/related name `mappings`; `local_field` and `remote_field`
required `CharField(max_length=100)`; direction default `both`; transform default `none`;
`value_map = JSONField(default=dict, blank=True)`; `default_value` blank
`CharField(max_length=255)`; `is_key` and `is_required` default false; `notes` blank
`CharField(max_length=255)`.

`Meta`: `ordering = ["connector__name", "local_field", "id"]`;
`unique_together = [("tenant", "connector", "local_field", "direction")]`; indexes
`ixm_tnt_conn_idx (tenant, connector)` and `ixm_tnt_conn_key_idx (tenant, connector, is_key)`.
`__str__()` is `"{local_field} → {remote_field}"`. `clean()` rejects a connector from another
workspace with an error on `connector`. A normal `.save()` does not invoke `clean()`.

### 3.4 `ProjectSyncJob` (`SyncJobs.py`, `SYJ-`)

Inheritance: `TenantNumbered`; `NUMBER_PREFIX = "SYJ"`. Project scope is read through
`connector.project`; there is deliberately no second `project` field.

Choices:

```text
SYNC_ENTITY_CHOICES = [("tasks", "Tasks"), ("issues", "Issues"), ("risks", "Risks"),
                       ("milestones", "Milestones"), ("time_entries", "Time Entries"),
                       ("resources", "Resources"), ("documents", "Documents"),
                       ("folders", "Folders"), ("budgets", "Budgets"),
                       ("cost_lines", "Cost Lines"), ("journals", "Journal Entries"),
                       ("custom", "Custom / Other")]
DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound"),
                     ("bidirectional", "Bidirectional")]
TRIGGER_MODE_CHOICES = [("manual", "Manual"), ("scheduled", "Scheduled"),
                        ("event", "Event-driven")]
CONFLICT_POLICY_CHOICES = [("local_wins", "Local Wins"), ("remote_wins", "Remote Wins"),
                           ("newest_wins", "Newest Wins"), ("manual", "Manual")]
```

Fields: required connector FK CASCADE/related name `jobs`; required name `CharField(255)`;
`entity_scope` default custom; direction default bidirectional; trigger mode default manual;
nullable/blank positive `interval_minutes`; blank `schedule_note(200)`; blank `filter_expression`
`TextField` recorded but never evaluated; conflict policy default manual; positive
`batch_size=100`; `is_active=True`; `last_run_at` and `next_run_at` nullable/blank and
`editable=False`; `run_count` positive default 0/editable false; blank `last_status(10)`/editable
false.

`Meta`: `ordering = ["-created_at", "-id"]`;
`unique_together = [("tenant", "number"), ("tenant", "connector", "name")]`; indexes
`syj_tnt_conn_idx (tenant, connector)`, `syj_tnt_conn_act_idx (tenant, connector, is_active)`,
`syj_tnt_status_idx (tenant, last_status)`, and `syj_tnt_active_idx (tenant, is_active)`.
`__str__()` is `"{number} — {name}"`. `clean()` rejects a connector from another workspace on
`connector`; normal save does not call clean.

There is no model lifecycle method. `last_run_at`, `next_run_at`, `run_count`, and `last_status`
are view/seeder-written system fields; the form excludes them.

### 3.5 `ProjectSyncRun` (`SyncRuns.py`, `SYR-`, append-only)

Inheritance: `TenantNumbered`; `NUMBER_PREFIX = "SYR"`. Module constant
`SYNC_BACKOFF_SECONDS = (0, 5, 300, 1800, 7200, 18000, 36000, 36000)` is the only retry schedule
constant.

Choices:

```text
RUN_STATUS_CHOICES = [("pending", "Pending"), ("running", "Running"),
                      ("success", "Success"), ("partial", "Partial"),
                      ("failed", "Failed"), ("skipped", "Skipped"),
                      ("simulated", "Simulated")]
DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound"),
                     ("bidirectional", "Bidirectional")]
TRIGGER_SOURCE_CHOICES = [("manual", "Manual"), ("schedule", "Schedule"),
                          ("event", "Event")]
```

Fields: required job FK CASCADE/related name `runs`; direction default bidirectional; status
default pending; trigger source default manual; nullable/blank `triggered_by` FK to the user,
SET_NULL and `editable=False`; five `PositiveIntegerField` counters (`records_read`,
`records_created`, `records_updated`, `records_skipped`, `records_failed`) default zero; blank
`error_code(50)`, `error_message`, and truncated `payload_excerpt` TextFields; `attempt_no`
positive-small-integer default 1; nullable/blank `next_retry_at`; `started_at` default
`timezone.now` and `editable=False`; nullable/blank `finished_at`/editable false; positive
`duration_ms=0`/editable false.

`Meta`: `ordering = ["-started_at", "-id"]`;
`unique_together = [("tenant", "number")]`; indexes
`syr_tnt_job_stat_idx (tenant, job, status)`,
`syr_tnt_stat_strt_idx (tenant, status, started_at)`, and
`syr_tnt_job_strt_idx (tenant, job, started_at)`. There is no current
`syr_tnt_started_idx`; do not assert an index that is not in the model.

`__str__()` is `"{number} — {status display} @ {started_at:%Y-%m-%d %H:%M}"`. `clean()` rejects a
job from another workspace on `job`. `status_badge` is success green, partial amber, failed red,
simulated info, pending/running slate, skipped muted, unknown slate.

Append-only behavior is a route/form/admin convention plus the sole-writer rule, not a database
trigger: there is no `ProjectSyncRunForm`, no create/edit/delete URL, and the admin disables add,
change, and delete. The model class itself does not override `delete()`.

`ProjectSyncRun.record()` is the only writer used by the views and seeder:

```python
ProjectSyncRun.record(
    *, job, status="simulated", trigger_source="manual", triggered_by=None,
    direction=None, records_read=0, records_created=0, records_updated=0,
    records_skipped=0, records_failed=0, error_code="", error_message="",
    payload_excerpt="", attempt_no=1, next_retry_at=None, started_at=None,
    finished_at=None, duration_ms=0,
)
```

It creates the row with `tenant=job.tenant`, snapshots `direction or job.direction`, and defaults
`started_at` to `timezone.now()`. It does not call HTTP, update the job, update connector counters,
or enforce a status transition. Tests and seed helpers must call this method rather than bare
`objects.create()`.

## 4. Forms: exact as-built contract

The top-level `apps.projects.forms` re-exports all three 7.18 model forms plus
`ConnectorTestForm`. There is deliberately no `ProjectSyncRunForm`.

### 4.1 `ProjectIntegrationConnectorForm`

Class bases: `TenantUniqueMixin, TenantModelForm`.

`Meta.model` is `ProjectIntegrationConnector`; `Meta.fields` is exactly, in this order:

```text
["project", "name", "domain", "provider", "direction", "auth_method",
 "base_url", "remote_scope_ref", "trigger_mode", "schedule_note",
 "environment", "status", "is_active", "notify_webhook", "owner", "notes"]
```

`notes` is a three-row `form-textarea` Textarea widget. The model `credential` column is not in
`Meta.fields` because it is `editable=False`, but the declared extra form field is part of the
actual `form.fields` ordering is the 16 `Meta.fields` followed by the declared `credential` field:

```text
credential = forms.CharField(
    required=False,
    widget=forms.PasswordInput(render_value=False, attrs={"class": "form-input"}),
    help_text="Paste the provider token/API key. Stored encrypted; leave blank on edit to keep the current one.",
)
```

`__init__` narrows `owner` to active users in the form tenant. If `tenant is None`, the owner
queryset is explicitly `.none()`. The inherited form machinery scopes the other tenant-owned FK
choices when a tenant is supplied. `clean()` calls `_reject_foreign` for exactly `project` and
`notify_webhook`; `owner` is deliberately not passed to that helper because the explicit owner
queryset is the boundary. `save(commit=False)` leaves the form’s instance with the cleaned model
values; a nonblank extra credential calls `instance.set_credential(raw)`, while a blank edit does
not clear the stored cipher. `save(commit=True)` saves and then calls `save_m2m()`.

### 4.2 `ConnectorTestForm`

A plain `forms.Form` with one optional `note = forms.CharField()` and a two-row
`form-textarea` Textarea widget/placeholder. It is not a ModelForm and has no tenant argument.
An empty POST is accepted by the action; the action supplies a default excerpt when no note is
present.

### 4.3 `ConnectorFieldMappingForm`

Class bases: `TenantUniqueMixin, TenantModelForm`.

`Meta.model` is `ConnectorFieldMapping`; `Meta.fields` is exactly:

```text
["connector", "local_field", "remote_field", "direction", "transform",
 "value_map", "default_value", "is_key", "is_required", "notes"]
```

`value_map` is a JSON textarea. `clean_value_map()` maps blank/whitespace to `{}`, parses JSON
strings with `json.loads`, raises `ValidationError("Invalid JSON for value map: ...")` for malformed
JSON, and raises `ValidationError("Value map must be a JSON object (key-value dictionary).")` for
valid non-dict JSON. A Python dict passes through; `None` becomes `{}`. The form field is a raw-text
char field with a JSON-aware `prepare_value`, so this cleaner receives the posted text before the model
JSONField stores the resulting dict. `clean()` calls `_reject_foreign` for `connector`.

### 4.4 `ProjectSyncJobForm`

Class bases: `TenantUniqueMixin, TenantModelForm`.

`Meta.model` is `ProjectSyncJob`; `Meta.fields` is exactly:

```text
["connector", "name", "entity_scope", "direction", "trigger_mode",
 "interval_minutes", "schedule_note", "filter_expression", "conflict_policy",
 "batch_size", "is_active"]
```

`filter_expression` is a two-row monospaced textarea with help text
`Recorded intent only — NavERP never evaluates this expression.`. `clean()` calls
`_reject_foreign` for `connector`. Number, run stamps, counters, and `last_status` are absent from
the form.

## 5. URL and route contract

The app namespace is `projects` and `app_name` is `projects`. All 31 routes are under the literal
`integration/` segment. Literal category/list routes precede `<int:pk>` routes; there is no greedy
string converter. The five category routes all call the same `ixc_list` function with a fixed
`domain` kwarg.

| URL name | Path | View | Method/gate |
|---|---|---|---|
| `ixc_list` | `integration/connectors/` | `ixc_list` | GET, login |
| `ixc_create` | `integration/connectors/add/` | `ixc_create` | GET/POST, login |
| `ixc_erp_list` | `integration/connectors/erp/` | `ixc_list(domain="erp")` | GET, login |
| `ixc_crm_list` | `integration/connectors/crm/` | `ixc_list(domain="crm")` | GET, login |
| `ixc_hris_list` | `integration/connectors/hris/` | `ixc_list(domain="hris")` | GET, login |
| `ixc_devops_list` | `integration/connectors/devops/` | `ixc_list(domain="devops")` | GET, login |
| `ixc_storage_list` | `integration/connectors/storage/` | `ixc_list(domain="storage")` | GET, login |
| `ixc_detail` | `integration/connectors/<int:pk>/` | `ixc_detail` | GET, login |
| `ixc_edit` | `integration/connectors/<int:pk>/edit/` | `ixc_edit` | GET/POST, login |
| `ixc_delete` | `integration/connectors/<int:pk>/delete/` | `ixc_delete` | POST, login + tenant admin |
| `ixc_rotate_credential` | `integration/connectors/<int:pk>/rotate-credential/` | `ixc_rotate_credential` | POST, login + tenant admin |
| `ixc_test` | `integration/connectors/<int:pk>/test/` | `ixc_test` | POST, login |
| `ixc_toggle_active` | `integration/connectors/<int:pk>/toggle/` | `ixc_toggle_active` | POST, login |
| `connector_health` | `integration/connectors/<int:pk>/health/` | `connector_health` | GET, login |
| `ixm_list` | `integration/mappings/` | `ixm_list` | GET, login |
| `ixm_create` | `integration/mappings/add/` | `ixm_create` | GET/POST, login |
| `ixm_detail` | `integration/mappings/<int:pk>/` | `ixm_detail` | GET, login |
| `ixm_edit` | `integration/mappings/<int:pk>/edit/` | `ixm_edit` | GET/POST, login |
| `ixm_delete` | `integration/mappings/<int:pk>/delete/` | `ixm_delete` | POST, login + tenant admin |
| `syj_list` | `integration/sync-jobs/` | `syj_list` | GET, login |
| `syj_create` | `integration/sync-jobs/add/` | `syj_create` | GET/POST, login |
| `syj_detail` | `integration/sync-jobs/<int:pk>/` | `syj_detail` | GET, login |
| `syj_edit` | `integration/sync-jobs/<int:pk>/edit/` | `syj_edit` | GET/POST, login |
| `syj_delete` | `integration/sync-jobs/<int:pk>/delete/` | `syj_delete` | POST, login + tenant admin |
| `syj_run` | `integration/sync-jobs/<int:pk>/run/` | `syj_run` | POST, login |
| `syj_toggle_active` | `integration/sync-jobs/<int:pk>/toggle/` | `syj_toggle_active` | POST, login |
| `syr_list` | `integration/runs/` | `syr_list` | GET, login |
| `syr_detail` | `integration/runs/<int:pk>/` | `syr_detail` | GET, login |
| `syr_retry` | `integration/runs/<int:pk>/retry/` | `syr_retry` | POST, login + tenant admin |
| `integration_hub` | `integration/hub/` | `integration_hub` | GET, login |
| `sync_monitor` | `integration/monitor/` | `sync_monitor` | GET, login |

The unique callable set is exactly:

```text
ixc_list, ixc_detail, ixc_create, ixc_edit, ixc_delete, ixc_rotate_credential,
ixc_test, ixc_toggle_active, connector_health, ixm_list, ixm_detail, ixm_create,
ixm_edit, ixm_delete, syj_list, syj_detail, syj_create, syj_edit, syj_delete,
syj_run, syj_toggle_active, syr_list, syr_detail, syr_retry, integration_hub,
sync_monitor
```

All 26 callable view functions have `@login_required`. The five admin-gated functions are
`ixc_delete`, `ixc_rotate_credential`, `ixm_delete`, `syj_delete`, and `syr_retry`; their source
decorator order is login, `require_POST`, then `tenant_admin_required`. This order is deliberate:
a member GET is 405 before the role check, while a member POST reaches the role check and is 403.
Anonymous requests are redirected by the outer login gate.

## 6. View behavior, filters, and context contract

### 6.1 Connector views

#### `ixc_list(request, domain=None)`

The base queryset is `ProjectIntegrationConnector.objects.filter(tenant=request.tenant)` with
`select_related("project", "owner", "notify_webhook")`. A nonblank category kwarg adds
`domain=domain`; the kwarg is echoed as context `domain`, never read from `request.GET.domain`.

Filters, applied before `Paginator(qs, 25)`:

- `q`: stripped `Q(name__icontains=q) | Q(number__icontains=q) | Q(remote_scope_ref__icontains=q)`.
- `status`: exact equality.
- `provider`: exact equality.
- `project`: only applied when the raw value `.isdigit()`; then `project_id` equality.
- `is_active`: `active`, `true`, or `1` → True; `inactive`, `false`, or `0` → False; anything else
  leaves the queryset unchanged.

Stats are computed over the tenant plus category scope, not over the other active filters:
`total`, `active`, `connected`, `error`, and `unverified`. The status counts are independent of
`is_active` (an inactive connected connector still contributes to `connected`). There is no
`due_rotation` key.

Context keys supplied: `connectors` (the page object list), `page_obj`, `projects` (all projects in the request tenant),
`domain_choices`, `provider_choices`, `status_choices`, `domain`, `q`, `status`,
`provider`, `project_id`, `is_active`, and `stats`. The list template consumes all of these except
that `page_obj` is used for pagination and `projects` supplies the project filter options.

#### `ixc_detail(request, pk)`

`get_object_or_404` scopes both the base connector queryset and `tenant=request.tenant`.
`mappings` is the first 20 connector mappings; `mappings_total` is a separate full count and is
the number displayed in the heading. `jobs` is the complete tenant-scoped connector job queryset.
`recent_runs` is the newest 15 runs by `-started_at`, with `job` selected. `_ixc_cred_reveal` is
popped from the session and only revealed when its `pk` matches this connector.

Context keys: `connector`, `mappings`, `mappings_total`, `jobs`, `recent_runs`, `test_form`, and
`revealed_credential`. The detail template consumes all seven. It renders no stored credential;
only the masked helper/set state and the session-once value.

#### `ixc_create` and `ixc_edit`

Create binds `ProjectIntegrationConnectorForm(request.POST or None, tenant=request.tenant)`. On
valid POST, `_ixc_save` sets the request tenant, saves, writes audit action `create`, flashes a
numbered success message, and redirects to `ixc_detail`. Invalid/unbound POST re-renders
`connector/form.html` with status 200. Create context is only `form`; it does not pass an
`is_edit` key or connector object.

Edit first scopes the existing connector, binds the same form with `instance=connector`, and on
valid POST writes audit `update` and redirects to detail. Context is `form`, `is_edit=True`, and
`connector`. Both templates use those exact names.

#### `ixc_delete`

POST-only tenant-admin action. It deletes the connector (cascading its mappings, jobs, and runs),
writes an audit row with action `delete` and a connector-number change payload, flashes success,
and redirects to `ixc_list`.

#### `ixc_rotate_credential`

POST-only tenant-admin action. It generates a new `secrets.token_hex(32)` value, calls
`set_credential`, saves ciphertext, stores
`request.session["_ixc_cred_reveal"] = {"pk": connector.pk, "credential": new_secret}`, writes
audit action `rotate`, and redirects to detail. The raw value is not put in the flash message.
`ixc_detail` reveals it once; the next detail GET has `revealed_credential=None`.

#### `ixc_test`

POST-only login action. It binds `ConnectorTestForm(request.POST or None)`, finds the first
tenant-scoped job for the connector (the queryset’s model ordering makes `first()` the newest
job by `-created_at`, then `-id`), and follows two branches:

1. No job: flash the warning `Create a sync job for this connector before running a test.`, write
   no run, and redirect to connector detail.
2. A job exists: take the optional stripped note, truncate it to 500 characters for
   `payload_excerpt`; if blank use the exact fallback `Simulated connection test — no outbound request was made.`;
   record a `simulated`/manual run through `ProjectSyncRun.record()` with the requesting user and
   `error_message="Simulated connection test — no outbound request was made."`; update only
   connector `last_sync_at`; write audit action `test`; flash the no-request information message;
   redirect to detail.

It does not update `last_success_at`, `consecutive_failures`, job counters, or the connector status.
The optional note-to-payload behavior is mandatory and must be asserted with a nonblank note.

#### `ixc_toggle_active`

POST-only login action. It flips `is_active`, saves with `update_fields`, writes audit action
`toggle` with the new boolean, and redirects to detail. It does not alter `status`.

#### `connector_health`

GET-only login lens. It scopes the connector and all child queries by tenant, selects connector
FKs, slices the newest 15 runs, and computes one aggregate for `total_runs`, `failed_runs`, and
`success_runs`. `success_rate` is `round(success_runs / total_runs * 100)` as an integer, or `0`
when there are no runs. `jobs_count` and `mappings_count` are integer counts, not querysets.
Context keys: `connector`, `recent_runs`, `jobs_count`, `mappings_count`, and `stats` with
`total_runs`, `failed_runs`, `success_rate`, and `last_success_at`. The last-success value is the
connector field, not a recomputed run maximum.

### 6.2 Field-mapping views

`ixm_list` scopes `ConnectorFieldMapping` by tenant and selects `connector`. Filters are
`q` (`local_field`/`remote_field` icontains), `connector` (digits only), `direction`, and
`transform`, all before a 25-row paginator. Context keys are `mappings`, `page_obj`, `connectors`
(all tenant connectors), `connector_id`, `direction`, `transform`, `direction_choices`,
`transform_choices`, and `q`. The template’s direction/transform selected-state comparisons use
`request.GET`; the view still echoes the cleaned values in context.

`ixm_detail` scopes and selects the connector and returns only `mapping`. `ixm_create`/`ixm_edit`
follow the connector create/edit form pattern: create context is `form`; edit context is `form`,
`is_edit=True`, and `mapping`; valid POSTs audit `create`/`update` and redirect to detail.
`ixm_delete` is POST-only tenant-admin, deletes the mapping, audits `delete` with a local-to-remote
label, and redirects to `ixm_list`.

### 6.3 Sync-job views

`syj_list` scopes jobs by tenant and selects `connector`. Filters are `q` (name/number
icontains), `connector` (digits only), `entity_scope`, `trigger_mode`, and `is_active` with the
same active-value mapping. Job stats are over all tenant jobs, not the filtered queryset:
`total`, `active`, `inactive`; `runs_total` is a separate count of all tenant runs. Context keys:
`jobs`, `page_obj`, `connectors`, `entity_choices`, `trigger_choices`, `conflict_choices`,
`status_choices`, `q`, `connector_id`, `entity_scope`, `trigger_mode`, `is_active`, and `stats`.
`status_choices` is `ProjectSyncRun.RUN_STATUS_CHOICES`; it is supplied for the shared vocabulary,
not because a job has a status field. The current list template consumes the job/filter/stat keys;
`conflict_choices` and `status_choices` are currently not rendered in that template.

`syj_detail` scopes/selects the job, returns `job`, the newest 20 tenant runs, and `connector`.
Create/edit use the same form/redirect/audit pattern, with edit context `form`, `is_edit=True`,
and `job`. `syj_delete` is POST-only tenant-admin, cascades runs, audits `delete` with the job
number, and redirects to `syj_list`.

`syj_toggle_active` is POST-only login, flips `is_active`, audits `toggle`, and redirects to job
detail. It does not require the job to be inactive or change any run.

`syj_run` is POST-only login and has no active-state precondition in the current source. It records
one `simulated`/manual run through `ProjectSyncRun.record()` with `triggered_by=request.user`, the
same `started_at` and `finished_at` timestamp, and exact
`error_message="Simulated run — no outbound request was made."`. It increments `run_count`, sets
`last_run_at` and `last_status="simulated"`, saves those system fields with `update_fields`, audits
action `run`, flashes the no-request message, and redirects to job detail. It does not call HTTP,
alter mappings, update connector health, or make the job inactive.

### 6.4 Sync-run views

The shared `_run_filters` helper is used by both `syr_list` and `sync_monitor`. It applies
`q` (number/error icontains), `job` (digits only), `connector` (digits only through
`job__connector_id`), `status`, and `trigger_source` exact filters. `date_from` and `date_to` are
parsed with `%Y-%m-%d`; a valid from value becomes an aware midnight `started_at__gte`, and a valid
to value becomes an aware end-of-day `started_at__lte`. Malformed dates are ignored and echoed
unchanged. The returned context filter keys are `q`, `job_id`, `connector_id`, `status`,
`trigger_source`, `date_from`, and `date_to`.

`syr_list` scopes/selects `job` and `job__connector`, paginates at 25, and computes tenant-wide
stats `pending`, `running`, `failed`, `partial`, `simulated`, and `failed_today` in one aggregate.
Context also includes `runs`, `page_obj`, `jobs`, `connectors`, `status_choices`, and `trigger_choices`.
The current run-list template consumes the status/trigger/job/date/filter/stat keys. It does not
render a connector `<select>` even though `connectors` and `connector_id` are supplied; connector
filtering and `connector_id` pagination are still current view behavior.

`syr_detail` scopes and selects `job`, `job__connector`, and `triggered_by`; its only context key is
`run`.

`syr_retry` is POST-only login plus tenant-admin. The current source does not check the incoming
status: it sets `status="pending"`, increments `attempt_no`, chooses
`SYNC_BACKOFF_SECONDS[min(attempt_no, 7)]` after the increment, stamps
`timezone.now() + timedelta(seconds=slot)`, saves only those fields plus `updated_at`, audits
`retry` with the new attempt number, and redirects to run detail. It performs no HTTP. The UI only
offers retry for `failed` and `partial`, but a direct POST can requeue any tenant-scoped run.

### 6.5 Computed boards

`integration_hub` is a login-only, non-paginated tenant dashboard. It computes connector total/
active/connected/error counts, one grouped `(domain,status)` pivot used to derive `by_domain`,
`by_status`, and the per-choice `domains` rows, today’s run/failed counts, active jobs, total
mappings, and active connectors needing attention (`status` in `error` or `disconnected`). It
returns the newest 10 runs and newest 50 connectors.

Its context is `stats` with `connectors_total`, `by_domain`, `by_status`, `runs_today`,
`failed_today`, `jobs_active`, `mappings_total`, and `credentials_due`; `domains` (one dict per
DOMAIN_CHOICES value with `value`, `label`, `total`, `connected`, `failing`); `connectors`;
`recent_runs`; and `projects`. The current template consumes the stats/domain/connector/run keys;
`projects` is supplied but not currently rendered. The current code has the grouped pivot and no
per-domain count loop; it also still has the connector aggregate used for the total/active/connected
/error stats, so a query-count test should assert the no-N+1 shape rather than assume one query.

`sync_monitor` is a login-only 25-row paginated run heat table. It reuses `_run_filters`, selects
job and connector, and computes tenant-wide `total`, `failed`, `success`, `simulated`, and
`failed_today` stats in one aggregate. Context is `runs`, `page_obj`, `jobs`, `connectors`,
`status_choices`, `trigger_choices`, `stats`, and the seven filter keys. The template consumes
`runs/page_obj/status_choices/trigger_choices/stats/q/status/jobs/job_id/connector_id/trigger_source/date_from/date_to`;
it renders both connector and trigger-source controls and preserves all active filters in pagination. Tests
should assert those controls and the tenant-scoped `connectors` queryset.

## 7. Context keys consumed by each of the 14 templates

This is the template-facing contract. A key listed as “supplied only” is still part of the view
context but is not currently read by that template; tests should not confuse a present context key
with a rendered control.

| Template | Keys consumed by the template | Supplied-only or conditional keys |
|---|---|---|
| `connector/list.html` | `domain`, `domain_choices`, `connectors`, `stats.total/active/connected/error/unverified`, `q`, `status`, `status_choices`, `provider`, `provider_choices`, `projects`, `project_id`, `is_active`, `page_obj` | None material; category `domain` is a view kwarg. |
| `connector/detail.html` | `connector`, `revealed_credential`, `mappings`, `mappings_total`, `jobs`, `recent_runs`, `test_form` | None. |
| `connector/form.html` | `form`, `is_edit`, `connector` | `is_edit`/`connector` are absent on create but are guarded by the template condition. |
| `mapping/list.html` | `mappings`, `page_obj`, `connectors`, `connector_id`, `direction`, `direction_choices`, `transform`, `transform_choices`, `q` | Direction/transform selected state is also compared through `request.GET`. |
| `mapping/detail.html` | `mapping` | None. |
| `mapping/form.html` | `form`, `is_edit`, `mapping` | `is_edit`/`mapping` are conditional on edit. |
| `syncjob/list.html` | `jobs`, `page_obj`, `connectors`, `entity_choices`, `entity_scope`, `trigger_choices`, `trigger_mode`, `is_active`, `q`, `stats.total/active/inactive/runs_total` | `conflict_choices` and `status_choices` are currently supplied but not rendered. |
| `syncjob/detail.html` | `job`, `runs`, `connector` | None. |
| `syncjob/form.html` | `form`, `is_edit`, `job` | `is_edit`/`job` are conditional on edit. |
| `syncrun/list.html` | `runs`, `page_obj`, `jobs`, `connectors`, `connector_id`, `status_choices`, `status`, `trigger_choices`, `trigger_source`, `job_id`, `q`, `date_from`, `date_to`, `stats.pending/running/failed/partial/simulated/failed_today` | None material; connector and trigger controls echo their context values. |
| `syncrun/detail.html` | `run` | None. |
| `boards/integration_hub.html` | `stats.connectors_total/jobs_active/mappings_total/failed_today/credentials_due`, `domains`, `connectors`, `recent_runs` | `projects`, `by_domain`, `by_status`, and `runs_today` are supplied for the hub context but not rendered. |
| `boards/sync_monitor.html` | `stats.total/success/failed/simulated/failed_today`, `runs`, `page_obj`, `q`, `status`, `status_choices`, `trigger_choices`, `trigger_source`, `jobs`, `job_id`, `connectors`, `connector_id`, `date_from`, `date_to` | None material; connector and trigger controls echo their context values. |
| `boards/connector_health.html` | `connector`, `stats.total_runs/failed_runs/success_rate/last_success_at`, `recent_runs`, `jobs_count`, `mappings_count` | None. |

All templates extend `base.html`, use autoescaping, and include CSRF tokens on every POST form. The
five list/monitor pages have 25-row paginators and guard `previous_page_number`/`next_page_number`
with `has_previous`/`has_next`. The current templates carry query strings in hand-written pagination
links; tests should assert page-2 behavior for every active filter, not only the initial page.

## 8. POST state transitions and audit contracts

| Action | Current state change | Redirect | Audit action |
|---|---|---|---|
| `ixc_create` valid | Creates connector; system fields/tenant are set by the view. | `ixc_detail` | `create` |
| `ixc_edit` valid | Updates connector; blank credential preserves cipher. | `ixc_detail` | `update` |
| `ixc_delete` | Deletes connector and cascading children. | `ixc_list` | `delete` |
| `ixc_rotate_credential` | Replaces encrypted credential; creates session-once reveal. | `ixc_detail` | `rotate` |
| `ixc_test` with job | Creates simulated run; stamps connector `last_sync_at` only. | `ixc_detail` | `test` |
| `ixc_test` without job | No state change/run. | `ixc_detail` | none |
| `ixc_toggle_active` | Flips `is_active`; status unchanged. | `ixc_detail` | `toggle` |
| `ixm_create`/`ixm_edit` valid | Creates/updates mapping. | `ixm_detail` | `create`/`update` |
| `ixm_delete` | Deletes mapping. | `ixm_list` | `delete` |
| `syj_create`/`syj_edit` valid | Creates/updates job; run system fields remain untouched by form. | `syj_detail` | `create`/`update` |
| `syj_delete` | Deletes job and cascading runs. | `syj_list` | `delete` |
| `syj_toggle_active` | Flips `is_active`; status remains. | `syj_detail` | `toggle` |
| `syj_run` | Records simulated run; increments `run_count`; sets `last_run_at` and `last_status="simulated"`. | `syj_detail` | `run` |
| `syr_retry` | Sets pending; increments attempt; stamps backoff. | `syr_detail` | `retry` |

There is no connector/job lifecycle guard in the model. `status`, `is_active`, and system stamps are
therefore separate assertions. The action functions are the only intended state-transition writers
for their displayed system fields.

## 9. Security and tenancy assertions

1. Every list, board, detail, and object action starts with a tenant-scoped queryset or
   `get_object_or_404(..., tenant=request.tenant)`. Tenant A must never see, count, filter, or
   mutate Tenant B rows.
2. A Tenant-A **admin** accessing a Tenant-B pk must receive 404 for object detail/edit/action
   routes: connector, connector health, mapping, job, and run actions all use a tenant-filtered
   lookup before the mutation. A non-admin member’s POST to an admin-gated action is a separate
   expected 403 because the role decorator runs before the tenant lookup; do not force that case
   to 404.
3. A list/board isolation test must inspect context rows, rendered HTML, and aggregate keys. It
   must include the child chain (a Tenant-B job/run/mapping cannot leak through a Tenant-A
   connector or run list).
4. Forms must reject crafted foreign `project`, `notify_webhook`, or `connector` pks with a field
   error. The normal queryset narrowing is not the only assertion: widen the ModelChoiceField to
   all rows and call the form again to exercise `_reject_foreign`. The same applies to model
   `clean()` tests for mismatched tenant FKs.
5. The connector owner dropdown contains active users from the form tenant only and excludes
   inactive users. A tenantless connector form has an empty owner queryset.
6. The workspace-wide connector duplicate-name guard must be tested through `clean()`/form
   validation because SQL `unique_together` does not constrain NULL project names.
7. All anonymous requests redirect to login. For an authenticated user, all nine POST-only
   action names return 405 on GET.
   For the five tenant-admin actions, a non-admin member’s GET must be 405 and a non-admin
   member’s POST must be 403, preserving the decorator order. CSRF-enforced clients must get 403
   for every POST form/action without a token.
8. Credentials are never rendered raw by list/detail/form templates. Stored values are Fernet
   ciphertext, `get_credential()` round-trips the raw fixture value, rotation produces a new raw
   64-hex value, and the session reveal appears on exactly one matching detail GET. The raw value
   must not occur in audit `changes` or flash messages.
9. `base_url` is a configuration CharField and is never fetched. A test may use an invalid or
   internal-looking value; no HTTP client, worker, scheduler, or socket call is expected from
   `ixc_test` or `syj_run`.
10. The tenantless superuser shape is `request.tenant is None`. Lists/boards filter `tenant=None`
    and should be empty. The three 7.18 create views (`ixc_create`, `ixm_create`, and `syj_create`)
    now check `request.tenant` before constructing a form, flash an explanatory message, and redirect
    to `dashboard:home`; they never render unscoped project/webhook/connector choices. A tenantless
    POST must not reach a save path.

## 10. Test-lane assertion map

### `test_integrationapihub_models.py`

Required targets:

- Number prefixes `IXC-`, `SYJ-`, `SYR-`; mapping has no `number`; per-tenant sequences do not
  collide across tenants and existing numbers survive resave.
- Exact choice value sets/labels and defaults for all four models.
- Exact `unique_together`, ordering, and the named indexes listed above. Do not assert a run
  `(tenant, started_at)` index that current `Meta` does not declare.
- Connector tenant guards, workspace-wide duplicate-name guard, all badge mappings, `__str__`,
  credential encryption/round-trip/masking/clearing, and `health_badge` branches.
- Mapping/job/run tenant guards and exact `__str__` values.
- `ProjectSyncRun.record()` snapshots the job tenant/direction, defaults status to simulated,
  accepts all counters/stamps, and does not mutate the job.
- `ProjectSyncRun.status_badge` branches and the `SYNC_BACKOFF_SECONDS` tuple.

Use `ValidationError` and `transaction.atomic()` for database uniqueness assertions. Call
`clean()` explicitly for model-only guards; do not assume `save()` validates.

### `test_integrationapihub_forms.py`

Required targets:

- Exact ordered `Meta.fields` and exclusions for all three model forms; no `ProjectSyncRunForm`.
- `TenantUniqueMixin` create behavior and explicit rejection of smuggled tenant/number/system
  values.
- Connector owner queryset scoping/inactive exclusion and the tenantless `.none()` rule.
- Foreign project/webhook/connector rejection at both queryset and widened-queryset backstop.
- Connector extra credential field is a `PasswordInput`, does not render an existing value, blank
  edit preserves ciphertext, and nonblank save stores encrypted data.
- JSON `value_map` blank, object, dict, malformed, and non-dict cases.
- Positive/blank numeric fields and all valid choice values; system run fields remain absent.

### `test_integrationapihub_views.py`

Required targets:

- Every 31 URL name reverses; every current GET page returns 200, and the response contains the
  object/domain token appropriate to the template (not merely status 200).
- Create/edit GET and valid/invalid POST behavior, redirects, and exact context object names.
- All list search/filter combinations, category route domain, invalid integer/string/date/page
  params, page 1/page 2/page 999, and 25-row page size.
- `mappings_total` remains the full count when the displayed `mappings` slice is capped at 20.
- `ixc_test` note truncation and jobless warning/no-run branch; `syj_run` simulated run and job
  system-field updates; `syr_retry` pending/backoff/attempt transition.
- Toggle, rotate/session-once reveal, deletes/cascades, and audit rows.
- Health/hub/monitor aggregate keys and the current no-per-domain-query optimization. A
  `django_assert_max_num_queries` assertion is appropriate for connector detail’s selected job
  relation and the health/hub query shapes, but do not assert the stale pre-review query count.
- Current template controls: run/monitor connector filters and monitor trigger filters are rendered,
  tenant-scoped, selected from context, and preserved in pagination. The hub renders the
  `credentials_due` attention stat.

### `test_integrationapihub_security.py`

Required targets:

- Anonymous redirects for all 31 routes (GET and POST where applicable).
- Tenant-A/B list, board, detail, edit, and every action isolation matrix; the Tenant-A admin
  client gets 404 for foreign pks, while member requests to admin-gated actions are separately
  expected to get 403.
- The five admin-only action gates, including the 405-before-403 decorator-order regression.
- CSRF 403 checks for all create/edit/delete/action POST endpoints.
- Foreign FK form rejection and tenantless owner/queryset behavior.
- Credential confidentiality, encrypted-at-rest assertions, one-time session reveal, and no raw
  secret in HTML/messages/audit changes.
- Junk GET values and nonexistent pks return 200/404 rather than 500.

## 11. Commands and final gate

Run all commands from the repository root with the project virtual environment and explicitly use
`config.settings_test`; never inherit a shell `DJANGO_SETTINGS_MODULE=config.settings` pointing at
MariaDB. `pytest.ini` also names `config.settings_test`, but the explicit environment is the
safe contract.

Later test writers, serially:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings_test"
venv\Scripts\python.exe -m pytest apps\projects\tests\test_integrationapihub_models.py -q
venv\Scripts\python.exe -m pytest apps\projects\tests\test_integrationapihub_forms.py -q
venv\Scripts\python.exe -m pytest apps\projects\tests\test_integrationapihub_views.py -q
venv\Scripts\python.exe -m pytest apps\projects\tests\test_integrationapihub_security.py -q
venv\Scripts\python.exe -m pytest apps\projects\tests -q
```

The final command is the unfiltered projects test suite, not a `-k` filter. The Phase-6 handoff is
complete only when all four lanes are present, green, and the final shared-fixture change has been
rechecked against the whole suite.

## 12. As-built ambiguities the next agent must respect

- `syr_retry`’s docstring/template describe failed/partial requeue, but the callable has no status
  precondition. Test the actual pending transition and do not silently “fix” this in a test file.
- `ixc_test` and `syj_run` are named run/test operations but intentionally perform no transport;
  they are simulated run writers only.
- `due_rotation` is absent after the review amendment. Do not reintroduce it in a test or conftest.
- `mappings_total` is a full count, distinct from the 20-row `mappings` slice.
- `ProjectSyncRun` currently has three declared indexes, not a `(tenant, started_at)` index.
- `integration_hub` has a grouped pivot but still retains a connector aggregate; “query optimized”
  means no per-domain count loop/N+1, not literally one SQL query.
- The run and monitor templates render connector and trigger-source filters, and the monitor context
  supplies `trigger_choices`; the hub renders `stats.credentials_due`.
- The three 7.18 create views guard a missing tenant before form construction and redirect to the
  dashboard; no tenantless create form should render or save.
- The shared fixture `integrationapihub_run_failed_a` is intentionally a failed run for retry
  coverage; it must be created through `_integrationapihub_run`/`ProjectSyncRun.record()`.
