# Build Contract — Projects 7.18 Integration & API Hub (`projects`)

> Frozen 2026-09-20 against the live tree at BASE commit `9336e994` (the Phase-2 plan commit).
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.
> Phase 4 reviews `9336e994...HEAD`.

---

## 0. Scope & capability coverage

Five NavERP.md §7.18 capability bullets (`NavERP.md:1281–1286`) map to **4 owned models + 1 unnumbered
child + 3 lens pages + five domain-scoped category routes**. 7.18 is the **connector + sync-run
layer**: a project-scoped register of connections to the five outside-system families, the field
mappings, the sync jobs, and the append-only run log. **Zero outbound HTTP** — no transport, no
worker, no HTTP client; `ProjectSyncRun.status = "simulated"` is the honest status and the model
docstrings say so out loud (the 7.17 / scm 4.19 / inventory 5.19 posture).

| NavERP.md bullet (character-for-character) | What 7.18 owns | Route |
|---|---|---|
| **ERP & Financial System Sync** (SAP, Oracle, NetSuite, Workday, Dynamics) | `domain="erp"` connectors (`sap·oracle·netsuite·dynamics·workday`) | `projects:ixc_erp_list` |
| **CRM Integration** (Salesforce, HubSpot, Dynamics Sales) | `domain="crm"` connectors (`salesforce·hubspot·dynamics_sales`) | `projects:ixc_crm_list` |
| **HR & Talent Systems** (Workday, BambooHR, ADP) | `domain="hris"` connectors (`workday·bamboohr·adp`), `resources·time_entries` jobs | `projects:ixc_hris_list` |
| **Development & DevOps Tools** (Jira, GitHub, GitLab, Azure DevOps, CI/CD) | `domain="devops"` connectors (`jira·github·gitlab·azure_devops·ci_cd`), `tasks·issues·milestones` jobs | `projects:ixc_devops_list` |
| **File Storage & Collaboration** (SharePoint, Google Drive, Dropbox, Box) | `domain="storage"` connectors (`sharepoint·google_drive·dropbox·box`), `documents·folders` jobs | `projects:ixc_storage_list` |
| The hub surface every surveyed product ships | `integration_hub` + `sync_monitor` + `connector_health` boards + `Connector Register`/`Field Mappings`/`Sync Jobs`/`Sync Runs` | `projects:integration_hub` etc. |

### Non-goals & invariants
- **7.18 owns data sync; 7.17 owns event push** (`ProjectWebhookEndpoint` [`PWH-`] +
  `ProjectWebhookDelivery`). 7.18 references a 7.17 endpoint by FK (`notify_webhook`) for "notify on
  sync failure" and re-declares none of it.
- **Four integration registers coexist deliberately** (L36/L31 ruling — research §4.4, option (b)):
  scm 4.19 `IntegrationEndpoint` [`CNX-`] (supply-chain, transport-less), inventory 5.19
  `IntegrationChannel` [`INT-`] (commerce-stock), accounting 2.15 `IntegrationConfig` (finance), and
  **this** `ProjectIntegrationConnector` [`IXC-`] (project-scoped). 7.18 FKs NONE of them and
  re-declares none of their class names or columns. The ruling lands in the model docstring, a
  `navigation.py` comment, and a `lessons.md` entry.
- **No transport**: `trigger_mode`/`interval_minutes`/`next_run_at`/`next_retry_at` are recorded
  intent/stamps; nothing schedules, polls, or wakes on them. `filter_expression` is recorded, never
  evaluated (4.19 precedent).
- **Audit verbs ≤ 10 chars** (`AuditLog.action` is `varchar(10)`): `create`, `update`, `delete`,
  `toggle`, `rotate`, `test`, `run`, `retry`. Never a longer verb.
- **Badges colour-named only** (L33): `badge-green`, `badge-red`, `badge-amber`, `badge-info`,

---

## 1. Verified ground truth (read on disk 2026-09-20)

- `Project` [`PRJ-`] (`apps/projects/models/ProjectInitiation/Projects.py`), url `projects:prj_detail`.
- `ProjectWebhookEndpoint` [`PWH-`] (7.17, `apps/projects/models/WorkflowAutomation/Webhooks.py`):
  its `project` is a **nullable** `Project` FK (`null=True, blank=True`, "Null implies tenant-wide
  webhook") — so a 7.18 connector may FK it whether project-scoped or workspace-wide.
- `TenantOwned` / `TenantNumbered` (`apps/projects/models/_base.py`); `NUMBER_PREFIX` drives `number`
  via `next_number` in `save()` with a 5-try collision guard. `q2`/`MAX_Q2` exist but are **not used**
  (no money columns).
- `TenantModelForm`, `TenantUniqueMixin`, `_reject_foreign` (`apps/projects/forms/_common.py`).
  `_reject_foreign(form, cleaned, names)` field-errors a chosen FK whose row belongs to another
  workspace; never pass a global/no-tenant model or `owner` (a superuser may carry `tenant=None`).
- `encrypt` / `decrypt` / `is_encrypted` (`apps/core/crypto.py`): Fernet with a `fernet.v1:` marker;
  `encrypt` idempotent (no-op on a marked value, blanks pass through); `decrypt` passes an unmarked
  value through unchanged and raises `ImproperlyConfigured` on a rotated key.
- `write_audit_log(user, obj, action, changes=None, tenant=None)` (`apps/core/utils.py:6`);
  `next_number(model, tenant, prefix, width=5, field="number")` (`:34`);
  `tenant_admin_required` (`apps/core/decorators.py:13`); `login_required` for reads.
- `apps.core.crud.crud_list/crud_detail/crud_edit` inject ONLY `object_list`/`obj`/`form`+`is_edit` —
  **not** the contract's list/`connector`/`mapping`/`job`/`run` keys. **Every 7.18 view hand-rolls its
  own `Paginator` + `render(...)` dict** (7.17's `views/WorkflowAutomation/Webhooks.py` pattern); the
  context keys below are the literal dict keys.
- There is **no `TENANT_SCOPED_FKS` attribute** in `apps/projects` (grep = 0). The tenant guard is a
  model `clean()` re-check (`…/ProjectFolders.py:126`) plus `_reject_foreign(...)` at the form
  boundary. Do NOT invent the attribute.
- Re-export tails: `apps/projects/models/__init__.py` (174 lines), `forms/__init__.py` (~199),
  `views/__init__.py` (~689) each END with the 7.17 block; the 7.18 block appends after.
  `urls/__init__.py` concatenation ends with the `_wa_*` entries; the five `_ih_*` imports append
  after. `app_name = "projects"` is set once at the top.
- Migration: `apps/projects/migrations/` ends at `0025_…`; this build adds **`0026_…`** (re-list
  immediately before `makemigrations`; if a sibling took `0026`, take the next free number and amend
  THIS contract, L43).
- Seeder: `apps/projects/management/commands/seed_projects.py`; `_seed_tenant` calls
  `self._workflow_automation(tenant, now)` last; `--flush` puts 7.17's six deletes near the top.
- URL namespace: `integration/…`, `ixc_*`, `ixm_*`, `syj_*`, `syr_*` are all free in `projects`
  (grep -> 0 hits, re-verified 2026-09-20).

## 2. Models (4, under `apps/projects/models/IntegrationApiHub/`)

Every entity module does `from apps.projects.models._base import *`; `Connectors.py` also imports
`encrypt`/`decrypt` from `apps.core.crypto`. Sub-package `__init__.py`s stay EMPTY of re-exports; the
public surface is the top-level `apps/projects/models/__init__.py` block.

### 2.1 `ProjectIntegrationConnector` [`IXC-`] — `Connectors.py` — `TenantNumbered`, full CRUD

- Class: `class ProjectIntegrationConnector(TenantNumbered)`; `NUMBER_PREFIX = "IXC"`.
- **Docstring (mandatory)**: the four-register L36 ruling — scm 4.19 `IntegrationEndpoint` [`CNX-`]
  supply-chain transport-less, inventory 5.19 `IntegrationChannel` [`INT-`] commerce-stock, accounting
  2.15 `IntegrationConfig` finance, **this** the project connector register [`IXC-`]; four registers,
  four questions, deliberately not merged — plus *"7.18 performs no outbound HTTP and writes no
  accounting row."*
- Choices:
  - `DOMAIN_CHOICES = [("erp","ERP & Finance"),("crm","CRM"),("hris","HR & Talent"),("devops","DevOps"),("storage","File Storage"),("custom","Custom / Other")]`
  - `PROVIDER_CHOICES = [("sap","SAP"),("oracle","Oracle"),("netsuite","NetSuite"),("dynamics","Microsoft Dynamics"),("workday","Workday"),("salesforce","Salesforce"),("hubspot","HubSpot"),("dynamics_sales","Dynamics Sales"),("bamboohr","BambooHR"),("adp","ADP"),("jira","Jira"),("github","GitHub"),("gitlab","GitLab"),("azure_devops","Azure DevOps"),("ci_cd","CI/CD Pipeline"),("sharepoint","SharePoint"),("google_drive","Google Drive"),("dropbox","Dropbox"),("box","Box"),("custom","Custom / Other")]`
  - `DIRECTION_CHOICES = [("inbound","Inbound"),("outbound","Outbound"),("bidirectional","Bidirectional")]`
  - `AUTH_METHOD_CHOICES = [("none","None"),("api_key","API Key"),("basic","Basic Auth"),("oauth2","OAuth 2.0"),("pat","Personal Access Token")]`
  - `TRIGGER_MODE_CHOICES = [("manual","Manual"),("scheduled","Scheduled"),("event","Event-driven")]`
  - `ENVIRONMENT_CHOICES = [("production","Production"),("sandbox","Sandbox")]`
  - `STATUS_CHOICES = [("unverified","Unverified"),("connected","Connected"),("error","Error"),("disabled","Disabled"),("disconnected","Disconnected")]`
- Fields:
  - `project`: FK `"projects.Project"`, CASCADE, **null=True, blank=True**, `related_name="integration_connectors"` (null ⇒ workspace-wide — mirrors `ProjectWebhookEndpoint.project`).
  - `name`: `CharField(120)`.
  - `domain`: `CharField(12, choices=DOMAIN_CHOICES, default="custom")`.
  - `provider`: `CharField(20, choices=PROVIDER_CHOICES, blank=True, default="custom")`.
  - `direction`: `CharField(14, choices=DIRECTION_CHOICES, default="bidirectional")`.
  - `auth_method`: `CharField(10, choices=AUTH_METHOD_CHOICES, default="api_key")`.
  - `base_url`: `CharField(500, blank=True)` — **with a `# WARNING: SSRF` comment** (CharField, not URLField; git/ssh/on-prem hosts are not http). Stored for configuration reference only and **never fetched** by this app.
  - `remote_scope_ref`: `CharField(200, blank=True)` (Jira project key, `org/repo`, SharePoint site id, SAP company code, NetSuite subsidiary, Salesforce org id).
  - `trigger_mode`: `CharField(10, choices=TRIGGER_MODE_CHOICES, default="manual")`.

### 2.2 `ConnectorFieldMapping` — `FieldMappings.py` — `TenantOwned`, **unnumbered**, full CRUD

- Class: `class ConnectorFieldMapping(TenantOwned)` (no `NUMBER_PREFIX`, no `number` column).
- Choices:
  - `DIRECTION_CHOICES = [("to_remote","Local → Remote"),("from_remote","Remote → Local"),("both","Bidirectional")]`
  - `TRANSFORM_CHOICES = [("none","None"),("upper","Uppercase"),("lower","Lowercase"),("trim","Trim"),("date_iso","ISO date"),("number","Number"),("bool","Boolean")]`
- Fields:
  - `connector`: FK `ProjectIntegrationConnector`, CASCADE, `related_name="mappings"`.
  - `local_field`: `CharField(100)` (e.g. `task.status`, `client.name`, `document.title`, `time_entry.hours`).
  - `remote_field`: `CharField(100)` (e.g. `fields.status.name`, `Account.Name`, `path`, `timeSpentSeconds`).
  - `direction`: `CharField(14, choices=DIRECTION_CHOICES, default="both")`.
  - `transform`: `CharField(12, choices=TRANSFORM_CHOICES, default="none")`.
  - `value_map`: `JSONField(default=dict, blank=True)` (local value ⇒ remote value, or the reverse per `direction`).
  - `default_value`: `CharField(255, blank=True)`.
  - `is_key`: `BooleanField(default=False)` (the match/identity key for de-dupe + idempotency).
  - `is_required`: `BooleanField(default=False)`.
  - `notes`: `CharField(255, blank=True)`.
- `clean()`: tenant guard — `connector.tenant_id != tenant_id` -> `ValidationError`.
- `Meta`: `ordering = ["connector__name", "local_field", "id"]`; `unique_together = [("tenant","connector","local_field","direction")]`; `indexes` = `ixm_tnt_conn_idx (tenant,connector)`, `ixm_tnt_conn_key_idx (tenant,connector,is_key)`.
- `__str__` = `f"{self.local_field} → {self.remote_field}"`.

### 2.3 `ProjectSyncJob` [`SYJ-`] — `SyncJobs.py` — `TenantNumbered`, full CRUD

The scoped, repeatable unit of transfer (Workato *recipe* / Fusion *scenario* / Celigo *flow*).

- Class: `class ProjectSyncJob(TenantNumbered)`; `NUMBER_PREFIX = "SYJ"`.
- Choices:
  - `SYNC_ENTITY_CHOICES = [("tasks","Tasks"),("issues","Issues"),("risks","Risks"),("milestones","Milestones"),("time_entries","Time Entries"),("resources","Resources"),("documents","Documents"),("folders","Folders"),("budgets","Budgets"),("cost_lines","Cost Lines"),("journals","Journal Entries"),("custom","Custom / Other")]`
  - `DIRECTION_CHOICES` — same 3 values as the connector's (`inbound·outbound·bidirectional`).

### 2.4 `ProjectSyncRun` [`SYR-`] — `SyncRuns.py` — `TenantNumbered`, **append-only**

What each sync batch actually did — the register a PMO argues about ("last night's Jira push",
"chase SYR-00042"). Numbered for that reason, mirroring `inventory.StockSyncRun`'s explicit ruling.
Append-only: **list + detail + `syr_retry` only; no form, no create/edit/delete url.**

- Class: `class ProjectSyncRun(TenantNumbered)`; `NUMBER_PREFIX = "SYR"`.
- Module-level constant: `SYNC_BACKOFF_SECONDS = (0, 5, 300, 1800, 7200, 18000, 36000, 36000)` (Svix's
  8 slots, adopted verbatim as scm's `DELIVERY_BACKOFF_SECONDS` / inventory's `SYNC_BACKOFF_SECONDS`).
- Choices:
  - `RUN_STATUS_CHOICES = [("pending","Pending"),("running","Running"),("success","Success"),("partial","Partial"),("failed","Failed"),("skipped","Skipped"),("simulated","Simulated")]` — **`simulated` is mandatory honesty** (nothing in this build leaves the process).
  - `DIRECTION_CHOICES` — same 3 values as the job's.
  - `TRIGGER_SOURCE_CHOICES = [("manual","Manual"),("schedule","Schedule"),("event","Event")]`
- Fields:
  - `job`: FK `ProjectSyncJob`, CASCADE, `related_name="runs"`.
  - `direction`: `CharField(14, choices=DIRECTION_CHOICES, default="bidirectional")` (a snapshot of the job's at run time).
  - `status`: `CharField(10, choices=RUN_STATUS_CHOICES, default="pending")`.
  - `trigger_source`: `CharField(10, choices=TRIGGER_SOURCE_CHOICES, default="manual")`.
  - `triggered_by`: FK `settings.AUTH_USER_MODEL`, SET_NULL, null/blank, `editable=False`, `related_name="+"`.
  - `records_read`, `records_created`, `records_updated`, `records_skipped`, `records_failed`: each `PositiveIntegerField(default=0)` (**counts, never one row per record**).
  - `error_code`: `CharField(50, blank=True)`.
  - `error_message`: `TextField(blank=True)`.
  - `payload_excerpt`: `TextField(blank=True)` (**truncated** — may contain partner PII).
  - `attempt_no`: `PositiveSmallIntegerField(default=1)`.
  - `next_retry_at`: `DateTimeField(null=True, blank=True)` (a stamp; nothing wakes up and reads it).
  - `started_at`: `DateTimeField(default=timezone.now, editable=False)`.
  - `finished_at`: `DateTimeField(null=True, blank=True, editable=False)`.
  - `duration_ms`: `PositiveIntegerField(default=0, editable=False)`.
- **`record()` classmethod is the ONLY writer** (the `StockSyncRun.record()` precedent): the run verb,
  the retry verb and the seeder all go through it — the seeder must NEVER bare-`.create()` a run.
  Signature: `record(cls, *, job, status="simulated", trigger_source="manual", triggered_by=None,

---

## 3. Forms — `apps/projects/forms/IntegrationApiHub/`

Sub-package `__init__.py` is docstring-only AND carries the deliberate-absence note: `ProjectSyncRun`
is append-only and its only writer is `record()`, so **no `ProjectSyncRunForm` exists** (the
`IntegrationMessages.py:26–30` / `StockSyncRuns.py` posture).

### 3.1 `Connectors.py`
- `class ProjectIntegrationConnectorForm(TenantUniqueMixin, TenantModelForm)`:
  - `Meta.model = ProjectIntegrationConnector`;
  - `Meta.fields` **exactly** `["project","name","domain","provider","direction","auth_method","base_url","remote_scope_ref","trigger_mode","schedule_note","environment","status","is_active","notify_webhook","owner","notes"]` (`number`,`credential`,`last_sync_at`,`last_success_at`,`consecutive_failures` excluded by construction).
  - Declared extra field: `credential = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False, attrs={"class": "form-input"}), help_text="Paste the provider token/API key. Stored encrypted; leave blank on edit to keep the current one.")`.
  - `clean()` → `_reject_foreign(self, cleaned, ["project","notify_webhook"])` — **not `owner`** (a superuser row may carry `tenant=None`; the view scopes the owner queryset instead, 7.17's restraint).
  - `save()`: a blank `credential` on edit leaves the stored cipher alone; a non-blank value is encrypted once by the model's `save()` choke point. Do NOT encrypt in the form (the model owns it).
- `class ConnectorTestForm(forms.Form)` (plain, for `ixc_test`): `note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows":2,"class":"form-textarea"}))` — the simulated test carries no live payload.

### 3.2 `FieldMappings.py`
- `class ConnectorFieldMappingForm(TenantUniqueMixin, TenantModelForm)`:
  - `Meta.model = ConnectorFieldMapping`;
  - `Meta.fields` **exactly** `["connector","local_field","remote_field","direction","transform","value_map","default_value","is_key","is_required","notes"]`.
  - `clean()` → `_reject_foreign(self, cleaned, ["connector"])`.
  - `clean_value_map()` parses JSON text into a dict (7.17's `clean_custom_headers` pattern: blank→`{}`, non-dict JSON→`ValidationError`, malformed→`ValidationError`).

### 3.3 `SyncJobs.py`
- `class ProjectSyncJobForm(TenantUniqueMixin, TenantModelForm)`:
  - `Meta.model = ProjectSyncJob`;
  - `Meta.fields` **exactly** `["connector","name","entity_scope","direction","trigger_mode","interval_minutes","schedule_note","filter_expression","conflict_policy","batch_size","is_active"]` (`number`,`last_run_at`,`next_run_at`,`run_count`,`last_status` excluded by construction).
  - `clean()` → `_reject_foreign(self, cleaned, ["connector"])`.

---


## 4. URLs + view functions + context keys

First segment is the literal `integration/` everywhere (verified free). Literal routes precede
`<int:pk>` ones. **No greedy `<str:…>` converter anywhere.** 31 route names, 26 view functions (the
five `ixc_*_list` category routes share `ixc_list` via Django's extra-options dict `{"domain":"…"}`).
All views `@login_required` unless noted.

### `urls/IntegrationApiHub/Connectors.py` (`from apps.projects.views.IntegrationApiHub import Connectors as views`)
```
integration/connectors/                            ixc_list
integration/connectors/add/                        ixc_create
integration/connectors/erp/                        ixc_erp_list      (ixc_list, {"domain":"erp"})
integration/connectors/crm/                        ixc_crm_list      (ixc_list, {"domain":"crm"})
integration/connectors/hris/                       ixc_hris_list     (ixc_list, {"domain":"hris"})
integration/connectors/devops/                     ixc_devops_list   (ixc_list, {"domain":"devops"})
integration/connectors/storage/                    ixc_storage_list  (ixc_list, {"domain":"storage"})
integration/connectors/<int:pk>/                   ixc_detail
integration/connectors/<int:pk>/edit/              ixc_edit
integration/connectors/<int:pk>/delete/            ixc_delete            @require_POST + @tenant_admin_required
integration/connectors/<int:pk>/rotate-credential/ ixc_rotate_credential @require_POST + @tenant_admin_required
integration/connectors/<int:pk>/test/              ixc_test              @require_POST
integration/connectors/<int:pk>/toggle/            ixc_toggle_active     @require_POST
integration/connectors/<int:pk>/health/            connector_health      (GET lens page)
```

### `urls/IntegrationApiHub/FieldMappings.py`
`integration/mappings/` `ixm_list` · `integration/mappings/add/` `ixm_create` · `<int:pk>/` `ixm_detail` · `<int:pk>/edit/` `ixm_edit` · `<int:pk>/delete/` `ixm_delete` (@require_POST + admin).

### `urls/IntegrationApiHub/SyncJobs.py`
`integration/sync-jobs/` `syj_list` · `add/` `syj_create` · `<int:pk>/` `syj_detail` · `<int:pk>/edit/` `syj_edit` · `<int:pk>/delete/` `syj_delete` (@require_POST + admin) · `<int:pk>/run/` `syj_run` (@require_POST) · `<int:pk>/toggle/` `syj_toggle_active` (@require_POST).

### `urls/IntegrationApiHub/SyncRuns.py`
`integration/runs/` `syr_list` · `integration/runs/<int:pk>/` `syr_detail` · `integration/runs/<int:pk>/retry/` `syr_retry` (@require_POST + admin). **No create/edit/delete.**

### `urls/IntegrationApiHub/HubBoards.py`
`integration/hub/` `integration_hub` · `integration/monitor/` `sync_monitor`.

  direction=None, records_read=0, records_created=0, records_updated=0, records_skipped=0,
  records_failed=0, error_code="", error_message="", payload_excerpt="", attempt_no=1,
  next_retry_at=None, started_at=None, finished_at=None, duration_ms=0)`; it snapshots
  `direction = direction or job.direction`, sets `tenant = job.tenant`, and returns the saved run.
- Retry semantics (docstring lives here): `syr_retry` sets `status="pending"`, `attempt_no += 1`,
  stamps `next_retry_at` from `SYNC_BACKOFF_SECONDS[min(attempt_no, 7)]`, and **performs no HTTP
  request**.
- `clean()`: tenant guard — `job.tenant_id != tenant_id` -> `ValidationError`.
- `Meta`: `ordering = ["-started_at", "-id"]`; `unique_together = [("tenant","number")]`; `indexes` =
  `syr_tnt_job_stat_idx (tenant,job,status)`, `syr_tnt_stat_strt_idx (tenant,status,started_at)`,
  `syr_tnt_job_strt_idx (tenant,job,started_at)`.
- `__str__` = `f"{self.number} — {self.get_status_display()} @ {self.started_at:%Y-%m-%d %H:%M}"`.
- `status_badge`: success→`badge-green`, partial→`badge-amber`, failed→`badge-red`, simulated→`badge-info`, pending/running→`badge-slate`, skipped→`badge-muted`.

  - `TRIGGER_MODE_CHOICES` — same 3 values as the connector's.
  - `CONFLICT_POLICY_CHOICES = [("local_wins","Local Wins"),("remote_wins","Remote Wins"),("newest_wins","Newest Wins"),("manual","Manual")]`
- Fields:
  - `connector`: FK `ProjectIntegrationConnector`, CASCADE, `related_name="jobs"`. **No second
    `project` column** — the job's project scope is read THROUGH its connector (one source of truth).
  - `name`: `CharField(255)`.
  - `entity_scope`: `CharField(16, choices=SYNC_ENTITY_CHOICES, default="custom")`.
  - `direction`: `CharField(14, choices=DIRECTION_CHOICES, default="bidirectional")` (may differ from the connector's).
  - `trigger_mode`: `CharField(10, choices=TRIGGER_MODE_CHOICES, default="manual")` (intent only).
  - `interval_minutes`: `PositiveIntegerField(null=True, blank=True)` (recorded cadence; nothing schedules on it).
  - `schedule_note`: `CharField(200, blank=True)`.
  - `filter_expression`: `TextField(blank=True)` (recorded, **never evaluated** — 4.19 precedent).
  - `conflict_policy`: `CharField(12, choices=CONFLICT_POLICY_CHOICES, default="manual")`.
  - `batch_size`: `PositiveIntegerField(default=100)`.
  - `is_active`: `BooleanField(default=True)`.
  - `last_run_at`, `next_run_at`: `DateTimeField(null=True, blank=True, editable=False)` (`next_run_at` is a stamp, not a trigger).
  - `run_count`: `PositiveIntegerField(default=0, editable=False)`.
  - `last_status`: `CharField(10, blank=True, editable=False)` (mirrors the newest run's status for the list column).
- `clean()`: tenant guard — `connector.tenant_id != tenant_id` -> `ValidationError`.
- `Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = [("tenant","number"), ("tenant","connector","name")]`; `indexes` = `syj_tnt_conn_idx (tenant,connector)`, `syj_tnt_conn_act_idx (tenant,connector,is_active)`, `syj_tnt_status_idx (tenant,last_status)`, **`syj_tnt_active_idx (tenant,is_active)`** (added in Phase 5, M19 — migration `0027`).
- `__str__` = `f"{self.number} — {self.name}"`.

  - `schedule_note`: `CharField(200, blank=True)` (documentation, not a cron).
  - `environment`: `CharField(10, choices=ENVIRONMENT_CHOICES, default="sandbox")`.
  - `status`: `CharField(12, choices=STATUS_CHOICES, default="unverified")`.
  - `is_active`: `BooleanField(default=True)`.
  - `credential`: `CharField(512, blank=True, editable=False)` — **Fernet ciphertext**; write-only via the form's extra `credential` field; never rendered.
  - `last_sync_at`, `last_success_at`: `DateTimeField(null=True, blank=True, editable=False)`.
  - `consecutive_failures`: `PositiveIntegerField(default=0, editable=False)`.
  - `notify_webhook`: FK `"projects.ProjectWebhookEndpoint"`, SET_NULL, null/blank, `related_name="notify_connectors"`.
  - `owner`: FK `settings.AUTH_USER_MODEL`, SET_NULL, null/blank, `related_name="owned_project_connectors"`.
  - `notes`: `TextField(blank=True)`.
- Methods/properties: `set_credential(raw)` (encrypts; blank clears), `get_credential()` (decrypt; `""` on blank), `credential_masked` (degrades to `"(set — undecryptable with the current key)"`, never raises), `credential_set` (bool), `status_badge` (connected→`badge-green`, error→`badge-red`, unverified→`badge-slate`, disabled→`badge-muted`, disconnected→`badge-amber`), `domain_badge` (each of erp/crm/hris/devops/storage→`badge-info`, custom→`badge-slate`), `health_badge`. `save()` performs `self.credential = encrypt(self.credential or "")` as the single choke point (idempotent on a marked value — `crm.Webhook.save()`'s exact pattern).
- `clean()`: tenant guard — `project.tenant_id != tenant_id` and `notify_webhook.tenant_id != tenant_id`
  each -> `ValidationError`. **Amendment M11:** also a **`project IS NULL` name-duplicate guard** —
  `unique_together=[("tenant","project","name")]` cannot bind NULL projects, so when `project_id is
  None` and `name` is set, reject a sibling workspace-wide connector with the same name in the same
  tenant (`ValidationError({"name": …})`). This was required by `todo.md:9425/:9437` and silently
  dropped from the original freeze.
- `Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = [("tenant","number"), ("tenant","project","name")]`; `indexes` = `ixc_tnt_domain_idx (tenant,domain)`, `ixc_tnt_status_idx (tenant,status)`, `ixc_tnt_prj_idx (tenant,project)`, `ixc_tnt_active_idx (tenant,is_active)` (all ≤30 chars).
- `__str__` = `f"{self.number} — {self.name} ({self.get_provider_display()})"`.

- 7.17 templates on disk are **lowercase** (`templates/projects/workflowautomation/…`); 7.18's disk
  folders COPY that lowercase spelling and render strings stay lowercase.

---

  `badge-muted`, `badge-slate`, always paired with a `{{ obj.get_<field>_display }}` fallback.
- **No money columns** in 7.18 (numeric columns are counters + a duration only).
- **PowerShell-safe commits**: one `git add 'file'; git commit -m 'msg'` per file, `;` never `&&`.

### View context keys (pin these — a mismatched key renders 200 and blank, L8)

- `ixc_list(request, domain=None)` — `projects/integrationapihub/connector/list.html`. Context:
  `connectors` (= `page_obj.object_list`), `page_obj`, `projects` (`Project.objects.filter(tenant=…)`),
  `domain_choices` (ALL `DOMAIN_CHOICES`), `provider_choices` (ALL `PROVIDER_CHOICES`),
  `status_choices` (`STATUS_CHOICES`), `domain` (echoed from the kwarg — the template echoes `domain`,
  **never** `request.GET.domain`), `q`, `status`, `provider`, `project_id`, `is_active`, and
  `stats` = `{total, active, connected, error, unverified}`.
  **Amendment (Phase 5, M10):** the dead `due_rotation` key is **dropped** — it was hard-coded `0`,
  never rendered by any template, and `todo.md:9448` never defined its window. Do not reintroduce it
  without a defined computation.
  Filters: `q` (`name|number|remote_scope_ref` icontains), `status`, `provider`, `project` (pk,
  `.isdigit()`), `is_active` (`active`/`true`/`1`→True; `inactive`/`false`/`0`→False); when the
  `domain` kwarg is set, `qs.filter(domain=domain)`. Paginator 25.
- `ixc_detail` — `connector/detail.html`. Context: `connector`, `mappings` (first 20),
  `mappings_total` (**full COUNT**, for the header label — the 20-row slice must not be presented as
  the total), `jobs` (all for the connector), `recent_runs` (15, `select_related("job")`),
  `test_form` (`ConnectorTestForm`), `revealed_credential` (session-once, session key
  `_ixc_cred_reveal`).
- `ixc_create` / `ixc_edit` — `connector/form.html`. Context: `form` (+ `is_edit` and `connector` on edit).
- `ixc_delete`, `ixc_rotate_credential`, `ixc_test`, `ixc_toggle_active` — `@require_POST`, redirect;
  each `write_audit_log`. `ixc_rotate_credential` calls `set_credential(secrets.token_hex(32))` +
  saves +   stashes the one-time reveal in session. `ixc_test` **binds `ConnectorTestForm(request.POST)`**,
  stores the posted `note` (truncated to 500 chars) as the run's `payload_excerpt`
  (**Amendment I5**), and writes a `simulated` `ProjectSyncRun` via `record()` (no HTTP) **only when
  the connector has ≥1 sync job** — a jobless connector is warned to create a job first
  (**Amendment M9**, documented on the view docstring). `ixc_toggle_active` flips `is_active`.
- `connector_health(request, pk)` — `boards/connector_health.html`. Context: `connector`,
  `recent_runs` (15), `jobs_count` (int), `mappings_count` (int), `stats` = `{total_runs, failed_runs,
  success_rate, last_success_at}` (**Amendment M17**: one `aggregate()`; counts passed as integers, not
  querysets for `|length`).
- `ixm_list` — `mapping/list.html`. Context: `mappings` (page_obj.object_list), `page_obj`,
  `connectors` (`ProjectIntegrationConnector.objects.filter(tenant=…)`), `connector_id`,
  `direction_choices`, `transform_choices`, `q`. Filters: `q` (`local_field|remote_field` icontains),
  `connector` pk (`.isdigit()`), `direction`, `transform`. Paginator 25.
- `ixm_detail` — `mapping/detail.html`. Context: `mapping`.
- `ixm_create` / `ixm_edit` — `mapping/form.html`. Context: `form` (+ `is_edit` and `mapping` on edit).
- `ixm_delete` — `@require_POST` + admin, redirect `ixm_list`, audit.
- `syj_list` — `syncjob/list.html`. Context: `jobs` (page_obj.object_list), `page_obj`, `connectors`,
  `entity_choices` (`SYNC_ENTITY_CHOICES`), `trigger_choices` (`TRIGGER_MODE_CHOICES`),
  `conflict_choices` (`CONFLICT_POLICY_CHOICES`), `status_choices`, `q`, `connector_id`,
  `entity_scope`, `trigger_mode`, `is_active`, `stats` = `{total, active, inactive, runs_total}`.
  Filters: `q` (`name|number` icontains), `connector` pk, `entity_scope`, `trigger_mode`, `is_active`.
  Paginator 25.
- `syj_detail` — `syncjob/detail.html`. Context: `job`, `runs` (recent 20), `connector`.
- `syj_create` / `syj_edit` — `syncjob/form.html`. Context: `form` (+ `is_edit` and `job` on edit).
- `syj_delete` (@require_POST + admin), `syj_toggle_active` (@require_POST), `syj_run` (@require_POST):
  `syj_run` writes a `simulated` `ProjectSyncRun` via `record()` (no HTTP), bumps the job's
  `run_count`/`last_run_at`/`last_status`, audit `action="run"`, redirect `syj_detail`.
- `syr_list` — `syncrun/list.html`. Context: `runs` (page_obj.object_list), `page_obj`, `jobs`,
  `connectors`, `status_choices` (`RUN_STATUS_CHOICES`), `trigger_choices` (`TRIGGER_SOURCE_CHOICES`),
  `job_id`, `connector_id`, `status`, `trigger_source`, `date_from`, `date_to`, `q`,
  `stats` = `{pending, running, failed, partial, simulated, failed_today}`.
  Filters: `q` (`number|error_message` icontains), `job` pk, `connector` pk, `status`,
  `trigger_source`, `date_from`/`date_to` **widened into a datetime range** so `(tenant, started_at)`
  is usable. Paginator 25.
- `syr_detail` — `syncrun/detail.html`. Context: `run`.
- `syr_retry` — `@login_required` + `@require_POST` + `@tenant_admin_required`: `status="pending"`,
  `attempt_no += 1`, `next_retry_at` from `SYNC_BACKOFF_SECONDS`, audit `action="retry"`, **no HTTP**,
  redirect `syr_detail`.
- `integration_hub` — `boards/integration_hub.html`. Context: `stats` = `{connectors_total, by_domain,
  by_status, runs_today, failed_today, jobs_active, mappings_total, credentials_due}`, `domains`
  (list of dicts `value`/`label`/`total`/`connected`/`failing`), `connectors` (health rows),
  `recent_runs`, `projects`.
- `sync_monitor` — `boards/sync_monitor.html`. Context: `runs` (page_obj.object_list), `page_obj`,
  `jobs`, `connectors`, `status_choices`, `stats`, `q`, `status`, `job_id`, `date_from`, `date_to`.
  Filters mirror `syr_list`.

---


## 5. Templates — `templates/projects/integrationapihub/<entity>/<page>.html` (lowercase disk folders, matching 7.17's lowercase `workflowautomation/`)

Every page extends `base.html`, uses the design-system classes from `static/css/theme.css`
(colour-named badges only — L33), `<i data-lucide="NAME"></i>` icons, and a post-pagination block
guarded by `page_obj.has_previous`/`page_obj.has_next` (L9). Every list page has a GET filter card
(search `q` + the status/FK selects echoing `request.GET`; pk comparisons with `|stringformat:"d"`),
an Actions column, and an `.empty-state`. Badge conditions use the exact model choice values with a
`{{ obj.get_<field>_display }}` fallback. Never render `credential` (only `credential_set` as a
"set"/"none" chip and, on `ixc_detail`, the session-once `revealed_credential` in a "Reveal once —
stored encrypted" frame).

- `connector/{list,detail,form}.html` — see §4 context keys; the five category routes share
  `list.html` and echo the `domain` kwarg (never `request.GET.domain`) in the header + active tab.
- `mapping/{list,detail,form}.html` — `value_map` renders as a JSON textarea on the form.
- `syncjob/{list,detail,form}.html` — `filter_expression` is a read-only-intent textarea whose help
  text says "recorded, never evaluated"; per-row "Run now" POST+csrf → `syj_run`, toggle POST →
  `syj_toggle_active`.
- `syncrun/{list,detail}.html` — **no form.html** (append-only); "Retry" POST+csrf+admin →
  `syr_retry` shown only on `failed`/`partial`; `next_retry_at` labelled "recorded schedule — nothing
  runs automatically"; `payload_excerpt` labelled "may contain partner data".
- `boards/{integration_hub,sync_monitor,connector_health}.html` — standalone pages (no entity
  folder); each links back to the register it reports on.
- `templates/projects/overview.html` — 7.18 quick-link rows (Hub, Sync Monitor, Connectors, Sync
  Jobs) + stat cards reading the NEW context keys (`integration_connector_count`,
  `sync_runs_failed_today`, `sync_runs_today`).


---

## 6. Integrate (single writer, the only DB writer)

Verify every expected file landed before wiring. Sub-package `__init__.py`s stay empty of re-exports.
- `apps/projects/models/__init__.py` — append `# --- 7.18 Integration & API Hub ---` block after the
  7.17 block: the four model imports.
- `apps/projects/forms/__init__.py` — append the 7.18 block (the three forms, NOT a run form).
- `apps/projects/views/__init__.py` — append the 7.18 block (all 26 view functions).
- `apps/projects/urls/__init__.py` — append the five `from .IntegrationApiHub.X import urlpatterns as
  _ih_x` imports and add `_ih_connectors + _ih_mappings + _ih_syncjobs + _ih_syncruns + _ih_boards`
  to the concatenation AFTER the `_wa_*` entries.
- `apps/projects/admin.py` — register the four models mirroring the 7.17 block (`admin.py:850–905`);
  **never** put `credential` in any `list_display`/`fields`/`readonly_fields` that renders its value.
- `apps/projects/management/commands/seed_projects.py` — new `_integration_hub(self, tenant, now)`
  (guard `if ProjectIntegrationConnector.objects.filter(tenant=tenant).exists()`), called in
  `_seed_tenant` AFTER `self._workflow_automation(tenant, now)`; creates the rows in §8; extends the
  `--flush` block with the children-first deletes (`ProjectSyncRun` → `ProjectSyncJob` →
  `ConnectorFieldMapping` → `ProjectIntegrationConnector`) ABOVE 7.17's webhook deletes; extends the
  imports; prints a per-tenant summary line.
- `apps/core/navigation.py` — ONE `LIVE_LINKS["7.18"]` block after `"7.17"` (`:2040`): the five
  bullet keys character-for-character → `projects:ixc_erp_list`/`ixc_crm_list`/`ixc_hris_list`/
  `ixc_devops_list`/`ixc_storage_list`; extra live leaves `Integration Hub`→`projects:integration_hub`,
  `Sync Monitor`→`projects:sync_monitor`, `Connector Register`→`projects:ixc_list`, `Field
  Mappings`→`projects:ixm_list`, `Sync Jobs`→`projects:syj_list`, `Sync Runs`→`projects:syr_list`.
- `apps/projects/views/ProjectInitiation/Overview.py` — add the three 7.18 context keys the overview
  template reads, tenant-scoped, computed in Python (the `open_defect_count` shape).
- `README.md` (Phase 7) and `config/settings.py`/`config/urls.py` — the latter **NOT touched**
  (app exists).


---

## 7. Migrate + seed + verify (venv python, PowerShell-safe `;`)

`venv\Scripts\python.exe manage.py makemigrations projects` (expect `0026_…`; if a sibling took
`0026`, take the next free number and amend THIS contract) → `migrate` → `seed_projects` twice (the
2nd run must print the idempotent-skip line) → `check` → the `temp/` smoke script (every new url as
`admin_acme` asserts 200/302 + rendered content, no `{#`/`{% comment` leaks, junk params, page 2,
cross-tenant IDOR → 404 per model; `ixc_test`/`syj_run` write a `simulated` run with no HTTP;
`syr_retry` flips status + bumps `attempt_no`; `ixc_rotate_credential` re-encrypts; the session-once
reveal appears exactly once).

---

## 8. Seeder (research §5.9)

`_integration_hub(self, tenant, now)` creates, per tenant:
- **7 connectors** — one per `domain` value plus one extra, spanning **every** `status`, at least one
  `project=None` (workspace-wide), the rest split across the seeded projects; one with
  `notify_webhook=` the 7.17 seeder's first `PWH` row, one `environment="production"`, one
  `trigger_mode="event"`; realistic `remote_scope_ref` values (`NAVERP`, `acme-co/platform`,
  `Salesforce org 00D…`); one with a Fernet credential set via `set_credential()`.
- **30 mappings** across ≥5 connectors: ≥1 `is_key=True` per connector, a `value_map` on the Jira and
  Salesforce rows (`{"done":"completed"}`, `{"Closed Won":"active"}`), a `to_remote`/`from_remote`/`both`
  trio, one `transform="date_iso"`.
- **9 jobs** spanning every `entity_scope` family the five bullets use, all four `conflict_policy`
  values, `is_active` true/false, one `trigger_mode="scheduled"` with `interval_minutes=60`.
- **45 runs** (page 2 needs >25; the monitor needs heat) spanning **every** `RUN_STATUS` and every
  `trigger_source`, spread over ~10 days, `records_*` populated, ≥1 failure per connector, one long
  `error_message` to exercise truncation, one `next_retry_at` stamp. **All runs via
  `ProjectSyncRun.record()`**, never bare `.create()`; set `duration_ms`, `attempt_no`,
  `payload_excerpt` (truncated).
- Print a per-tenant summary line (connectors / mappings / jobs / runs).

---

## 9. Review / fixer / tests / close-out (Phases 4–7)

Phase 4: six reviewers one at a time read `9336e994...HEAD` and append to
`.claude/tasks/review-projects-7.18.md` (dedupe, C/I/M IDs, commit). Phase 5: `code-fixer` fixes in ID
order, one commit per file — **COMPLETE 2026-09-22**: 0 Critical, 7 Important (6 fixed, I4
`[~] skipped — process/history`), 19 Minor (17 fixed, M12/M13 `[~] skipped — process`). Contract
amendments I4/I5/M9/M10/M11/M17/M19 applied. Phase 6: test contract + `conftest.py`, then
`test_integrationapihub_{models,forms,views,security}.py` one at a time (all `test_integrationapihub_*`),
finishing with the full unfiltered `apps/projects` suite green. Phase 7: update
`.claude/skills/projects/SKILL.md` + `README.md`. One file per commit; never `git push`.

