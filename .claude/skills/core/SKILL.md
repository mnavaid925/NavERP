---
name: core
description: Work on Module 0 (System Admin & Security) — the foundation, realized across FOUR apps (`core`, `accounts`, `tenants`, `dashboard`). Covers the unified spine (Party/PartyRole/Address/ContactMethod/PartyRelationship/Employment/OrgUnit/Activity/Document/AuditLog) and the platform layer built by 0.1–0.16: tenant & subscription, IAM, RBAC, SSO/MFA, user & organization, module access scope, data security & encryption, privacy & data protection, audit trail, system configuration & settings, workflow & approval administration, notification & communication, integration & API management, master data, localization & regional settings, and backup, recovery & data lifecycle. Use when the user asks to add/change/debug anything under apps/core, apps/accounts, apps/tenants or apps/dashboard, extend seed_core/seed_accounts/seed_tenants, touch Module 0 sidebar wiring (LIVE_LINKS 0.1–0.21), or invokes /core.
---

# Module 0 — System Admin & Security (the foundation)

Module 0 is **not one app**. It is realized across four foundation apps, and this skill covers all four:

| app | path | templates | what it owns |
|---|---|---|---|
| `core` | `apps/core/` | `templates/core/` | Tenant, the unified spine, AuditLog, navigation, crud/decorators/utils, and the platform layer 0.6/0.8/0.10–0.16 |
| `accounts` | `apps/accounts/` | `templates/accounts/` | `User`, `Role`, `Permission`, `UserInvite`, auth, MFA/sessions/password policy (0.2, 0.4) |
| `tenants` | `apps/tenants/` | `templates/tenants/` | Subscription, billing, invoices, branding, encryption keys, health metrics (0.1, 0.7) |
| `dashboard` | `apps/dashboard/` | `templates/dashboard/` | the root landing page — a tenant-scoped KPI aggregation with **no models of its own** |

`core` is the **canonical reference implementation** for a tenant-scoped CRUD module; `apps/tenants` is the
reference for a foundation app with flat entity files. Read them before inventing a shape.

## As-built

**18 of 21 sub-modules are live** (`LIVE_LINKS` in `apps/core/navigation.py` is the source of truth):

`0.1` Tenant & Subscription · `0.2` Identity & Access Management · `0.3` RBAC & Permissions ·
`0.4` Authentication & SSO · `0.5` User & Organization · `0.6` Module Administration & Access Scope ·
`0.7` Data Security & Encryption · `0.8` Privacy & Data Protection · `0.9` Audit Trail & Activity Logging ·
`0.10` System Configuration & Settings · `0.11` Workflow & Approval Administration ·
`0.12` Notification & Communication · `0.13` Integration & API Management · `0.14` Master Data &
Reference Configuration · `0.15` Localization & Regional Settings ·
`0.16` Backup, Recovery & Data Lifecycle · `0.17` Monitoring, Logging & Observability ·
`0.18` Threat Protection & Security Operations.

**Unbuilt: `0.19`–`0.21`** (License Administration, Admin Console,
Compliance & Governance). They render as roadmap pills.

Migrations: `core.0005`–`core.0016`, `accounts.0003`–`accounts.0004`, `tenants.0004`.

## App layout — FOUNDATION apps keep entity files FLAT

This is the one structural rule that differs from the domain modules. `crm`/`accounting`/`hrm`/`scm` use
`models/<SubModule>/<Entity>.py`; **`core` and `tenants` do not**:

```
apps/core/
  models/  __init__.py (re-exports EVERY model)  _base.py  Party.py  PartyRole.py  Setting.py  Localization.py …
  forms/   __init__.py  _common.py (TenantModelForm)  Party.py  Settings.py  Localization.py …
  views/   __init__.py  _common.py  Party.py  Settings.py  Localization.py …
  urls.py  <- a FLAT file, not a package
  navigation.py  <- parse_catalog() + MODULE_ICONS + LIVE_LINKS
  crud.py  utils.py  decorators.py  scoping.py  privacy.py  settings_engine.py
  workflow.py  notify.py  integration.py
```

**One file per SUB-MODULE, not per entity** — `Localization.py` holds all five 0.15 models;
`Privacy.py` holds all five 0.8 models; `Backup.py` holds six of 0.16's seven (the seventh,
`LegalHold.py`, is separate because a hold is a peer of a retention policy, not a backup record). `tenants/` and `accounts/` follow the same flat rule
(`accounts/models.py` is a single file).

`dashboard` is deliberately minimal: `apps.py`, `urls.py`, `views.py`, `migrations/__init__.py` — **no
models**. It is the root landing page and aggregates six tables owned by `core` and `tenants`.

**Rules when working here:**
- Add the symbol to the entity file, **then add it to that package's `__init__.py` re-export block.** A
  missing re-export is an `ImportError` at URLconf import time.
- Imports inside the packages are **absolute** (`from apps.core.models import X`).
- Never create a `<SubModule>/` folder under a foundation app's `models/`.
- Never add `models_advanced.py` or any sidecar.

## The unified spine (`core`)

Customers, vendors, suppliers, employees, leads and contacts are **`PartyRole`s on `Party`** — never a
standalone customer/vendor/employee table. Also `Address`, `ContactMethod`, `PartyRelationship`,
`Employment`, `OrgUnit`, `Activity`, `Document` (a `GenericForeignKey` attachment), `AuditLog`.

**`apps/accounting` owns the financial ledger** (`Currency`, `GLAccount`, `TaxCode`, `ExchangeRate`,
`FiscalPeriod`, `JournalEntry`/`JournalLine`, `Invoice`, `Bill`, `Payment`). Other apps FK into it **by
string**. Balances are **derived**, never stored editable. **Module 0 does not re-declare any of it** —
0.15 points at `Currency`/`ExchangeRate`/`TaxCode` rather than growing a second copy (L36).

## The Module 0 recurring shape

Every platform sub-module resolves to the same three-part shape, and it is almost never a second engine:

1. **A registry** for what the platform can express (a definition table).
2. **A per-tenant profile/override** pointing at it (often a `OneToOneField` singleton).
3. **A COMPUTED board** that reads the *real* tables of other apps and stores nothing.

Examples: 0.13's `ConnectorDefinition` + `SyncSchedule` + `integration_health()`; 0.15's `Language`/
`TimeZone` registries + `LocaleProfile` + `localization_board`; 0.16's `RecoveryPosture` singleton +
the `backup_overview` / `backup_board` pair, which **store no figure at all**. When you are tempted to
build an engine, first check whether 71 approval models, per-module webhooks or
`core.SettingDefinition` already exist.

## 0.16 — Backup, Recovery & Data Lifecycle

The sub-module is a **register, not an engine**. NavERP has no scheduler, no object-storage client and
no ability to dump or restore its own database, so nothing here performs the act it describes: every row
records an act performed **out of band**, and the success messages say "recorded", never "completed".
State that plainly on any page you touch, because a backup register that reads like a backup tool is the
dishonesty this sub-module exists to avoid.

**Routes** — 34, all `core:`-namespaced (`0.16` accounts for 34 of the module's 240 route names):
`backup_overview` · `backup_board` · `recovery_posture_edit`, plus a five-route `crud()` set for each of
`backup_job`, `restore_record`, `data_archive`, `legal_hold`, `environment_instance`, `recovery_drill`.
`backup_job_verify` is an extra **POST-only** verb. Seven verbs are POST-only and all carry
`@require_POST` **above** `@tenant_admin_required`, so a wrong method is **405 regardless of role**.

**Templates** — `templates/core/` at the flat root: `backupoverview.html`, `backupboard.html`,
`retentionboard.html` (0.8's, which 0.16 taught about holds), `recoveryposture/form.html`, and
`<entity>/{list,detail,form}.html` for the six CRUD entities.

**Models** — `models/Backup.py` holds six (`BackupJob`, `DataArchive`, `RestoreRecord`,
`EnvironmentInstance`, `RecoveryPosture`, `RecoveryDrill`); `models/LegalHold.py` holds the seventh. All
seven inherit **`TenantConsistentMixin`**, which refuses a tenant-scoped FK pointing into another
workspace — the rule that makes the contract's "the seeder *and the admin* get it too" true, since the
admin uses a plain `ModelForm` with no queryset narrowing at all.

**Seeder** — `seed_core._seed_backup(tenant)`. Every entity has its **own** guard (never a tenant-wide
one), and the rows are chosen to exercise the states a naive seed omits: a `warning`/partial job, an
unverified `success` job, a `failed` job, a **`queued` job with `started_at=None`** (M11 — its absence is
exactly why the C5 ordering defect survived a green sweep), and an unrestorable archive
(`location=""`, `status="lost"`). Fresh-seed figures: 4 jobs / 2 archives / 1 hold / 2 environments /
2 drills / 1 posture / 1 restore.

**Tests** — `apps/core/tests/test_backup_{models,forms,views,security}.py` (**266 tests**), fixtures
appended to `apps/core/tests/conftest.py` under `bkp_*`, contract at
`.claude/tasks/test-contract-core-0.16.md`. **The test DB is SQLite** (`config.settings_test`), not
MariaDB — see contract §0 before asserting anything engine-specific.

**Sidebar** — one `LIVE_LINKS["0.16"]` entry whose bullet 4 points at the **archive catalogue**; the
landing page is `backup_overview`.

**As-built, and the two things a reader will otherwise re-litigate:**

- **C7 is ESCALATED, not fixed.** `TenantModelForm` deliberately leaves a queryset unnarrowed when
  `tenant=None`, so that `_reject_foreign` can return its precise "belongs to another workspace"
  message. Emptying it was tried and **reverted** — it broke 15 committed tests across `inventory`,
  `procurement` and `projects`. Measured latent exposure: 859 tenant-scoped fields across 618 forms.
  **Do not re-try it without the owner's decision.** A form reachable *without* a tenant must narrow
  explicitly.
- **`L5-M1` (verify idempotency) was never carried into the consolidated Minor list** and is therefore
  unfixed: a second POST to `backup_job_verify` re-dates the stamp. No test enforces either behaviour.

## 0.17 — Monitoring, Logging & Observability

Migration **core.0015** (`0015_alertrule_alertevent_servicecomponent_incident_and_more.py`). Four models
in **`models/Monitoring.py`** — `ServiceComponent`, `AlertRule`, `AlertEvent`, `Incident`, each
`TenantConsistentMixin`. Seeder block `seed_core._seed_monitoring(tenant)`.

**Routes** — `core:`-namespaced, declared in `apps/core/urls.py`: five-route `crud()` sets for
`service_component`, `alert_rule`, `alert_event` and `incident`, plus four board/landing pages
`health_board`, `firing_board`, `capacity_board`, `monitoring_overview`, and the four POST-only
actions `alertevent_acknowledge`, `alertevent_resolve`, `alertevent_recur`, `incident_notify`.
**28 url names in all** (`test_monitoring_security.py::test_monitoring_the_url_inventory_is_complete`
asserts the count, so a rename fails rather than quietly shrinking the covered surface).

> **Do not confuse `core:process_monitor` with 0.17.** It is a *0.11 Workflow* page, defined in
> `views/Workflow.py` and routed at `workflows/monitor/`. It is not one of 0.17's four boards.

**Templates** — `templates/core/` at the flat root (foundation app, so no sub-module level):
`alertrule/{list,detail,form}.html`, `alertevent/{list,detail,form}.html`,
`incident/{list,detail,form}.html`, `servicecomponent/{list,detail,form}.html`, plus the standalone
`healthboard.html`, `firingboard.html`, `capacityboard.html` and `monitoringoverview.html`.

**The URL prefix is `monitoring/…` while the template folders are flat `core/<entity>/`.** That
asymmetry is intentional and matches 0.16 (`backup/jobs` routes ↔ `templates/core/backupjob/`): the
route namespace groups the pages in the URL bar, the template folder is flat because Module 0 has no
sub-module level. **Do not "fix" it by creating `templates/core/monitoring/`.**

**Three of the five NavERP bullets are deliberately DECLINED, not partially faked** — this is the
thing a reader will otherwise re-litigate, so `LIVE_LINKS["0.17"]` says it in comments as well:

- **b2 "Centralized logs"** — no log pipeline exists anywhere in this repo. What ships is the alert
  threshold vocabulary and the register of hand-reported firings.
- **b3 "Distributed tracing"** — no tracing SDK, no OpenTelemetry. Latency/throughput/slow-query exist
  as **threshold vocabulary on `AlertRule`** plus a computed board, not as an APM product.
- **b4 "Quota management"** — billing's. 0.17 keeps only the scaling trigger.

**0.18 inherits that boundary** — it must not re-declare the observability store either, and must say
in its own contract whether it can now serve log aggregation or carries the same deferral.

**Seeder (L52) — `seed_core._seed_monitoring` creates ZERO `AlertEvent` and ZERO `Incident` rows, on
purpose.** They are evidence that a threshold was crossed and that an outage happened; NavERP observed
neither, so seeding them would fabricate operational history and make the boards lie. Only
`ServiceComponent` and `AlertRule` are seeded. **A test or smoke run that finds zero of the other two
is correct, not broken** — create them in a `try/finally` and delete them after. This is the same
ruling as 0.16's `DisposalRecord` and 0.11's `BusinessRuleLog`.

**Five bugs this sub-module actually shipped and fixed — read before "simplifying" any of it:**

- **A Django template cannot index a dict by a loop variable.** `{% for v, l in choices %}{{ counts|default_if_none:0 }}{% endfor %}` printed the *whole dict* on every row. The fix is to zip in the view (`status_rows = [(label, count, value), …]`) and loop the tuples. This is the single most 0.17-specific trap.
- **A badge ladder must name every real value in its model's `CHOICES`.** Two ladders shipped incomplete — alert events omitted `no_data` and `expired`, incidents omitted `investigating`/`identified`/`in_progress` — so a real state rendered in the same grey as an unrecognised one. An outage *in progress* must not be grey.
- **Key a badge off the stored VALUE, never the display LABEL.** One card compared `'Operational'` while four others compared `'operational'`; a single `STATUS_CHOICES` relabel would grey that one card out.
- **`is_active` and `is_open` are different questions.** `is_active` is register membership; `is_open` is a status test. Using one for the other's count made a resolved-but-unarchived incident read as "still open". They are now separate context keys with separate sentences.
- **A two-tier threshold needs a comparator-aware order check.** "Critical" is stricter *relative to the operator*: above the warning tier for `gt`/`gte`, below it for `lt`/`lte`, and meaningless for `eq`/`in`/`contains`. Without the check, a reversed pair is accepted and the capacity board then picks the looser tier as "the bound" and reports a breach as healthy.

**Performance shape to preserve.** `AlertRule.COMPARATORS is BusinessRule.OPERATORS` and
`AlertRule.FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES` are **reuse by reference** — never
paste a second copy. `_rule_event_stats()` computes its three figures with one `aggregate()`; it once
fetched a rule's whole firing history into Python (0.711 s at 20k rows against 0.031 s for the
aggregate). `firing_board`'s histograms are grouped `values().annotate(Count(...))`, its open list is
capped at 200, and `open_total` is passed so a truncated view says so. `IncidentForm.__init__` joins
`primary_alert` with `select_related("rule")` **in the form, not in `forms/_common.py`** — a `__str__`
that dereferences an FK turns every `<option>` into a query (measured 200 events → 201 queries), and
changing the shared base would put committed tests in three other apps at risk.

**Known, accepted limitation — do not fix here.** `TenantConsistentMixin` walks `ForeignKey` and
`OneToOneField` only, so the `Incident.affected_services` **M2M is not tenant-checked on the admin
path**. `TenantModelForm` narrows M2M querysets, so the form path is covered. Same posture as 0.16's
escalated C7. **Do not change `TenantModelForm`** — it would break committed tests in three apps.

**Flags for the next sub-modules.** **0.20** owns scheduling: `AlertRule.frequency` reuses the 0.13 vocabulary and is a
recorded intention nothing runs, so 0.20 will add a `schedule` FK alongside it or migrate the column.

## 0.18 — Threat Protection & Security Operations

Migration **core.0016** (four `CreateModel`s, **zero `AddField`**). Four models in
**`models/Security.py`** — `IpAccessRule` (17), `SecurityThreat` (28), `VulnerabilityFinding` (25),
`SecurityIncident` (35), each `TenantConsistentMixin`; **105 fields**, declared in dependency order
because `SecurityThreat.mitigated_by` and `SecurityIncident.primary_threat` are FKs between them.
Seeder block `seed_core._seed_security(tenant)`.

**The 0.18 seam, and it is one enum value.** `AlertRule.CATEGORY_CHOICES` already carried
`("security", "Security")` when 0.17 shipped, and `apps/core/tests/test_monitoring_models.py::
test_monitoring_security_is_the_018_seam` names it as the 0.18 seam. So **no new column on any
0.17 model** (no `threat_level`, `ip_address`, `cvss_score`, `mitre_technique` on `AlertRule` /
`AlertEvent` / `Incident` / `ServiceComponent`), **no `SecurityAlert` table**, **no second incident
lifecycle** and **no second board**. Bullet 5 is served by *writing into* 0.17's tables. Migration
`0016` is four `CreateModel`s and **zero `AddField`** — the schema-level proof of the same thing.

**One place a second incident lifecycle is deliberately ABSENT.** `SecurityIncident.status` is the
NIST SP 800-61r2 union and is **not** 0.17's `Incident.status` union, which carries `scheduled` and
`monitoring` — values a breach never passes through. The two are joined by an FK, so one incident
can carry both faces. Forcing them together would be the L36 bug pointed the other way.

**The rate-limit seam.** `core.RateLimitPolicy` (0.13) keeps the limit; 0.18 FKs it
(`SecurityThreat.rate_limit_policy`, `IpAccessRule.rate_limit_policy`) and **never edits
`Integration.py`**. `rule = configuration, event = occurrence` — the split 0.17 already made.

**Routes** — 33 `core:` names: five literal boards/overview first (first-match-wins), then four
`crud()` groups, then the eight POST-only action paths declared after the group that owns them.
**`core:rate_limit_detail` DOES NOT EXIST** — link a policy with `core:rate_limit_edit` + pk. That is
a hard 500, not a soft link break.

**Templates** — 17 files. `templates/core/<entity>/{list,detail,form}.html` for the four entities
(12), plus five standalone pages flat at the app root: `securityoverview.html`, `threatboard.html`,
`vulnerabilityboard.html`, `breachclock.html`, `bruteforceboard.html`. Foundation rule 4 — the
entity folder sits at the app root, not under a sub-module folder.

**Admin** — four `ModelAdmin`s in `apps/core/admin.py`. Every system-set stamp is in
`readonly_fields` so the admin cannot bypass the one-writer rule, and the IP-rule changelist renders
`action_display` ("would block"), never a bare "Block" that reads as a working control.
**`SecurityThreatAdmin.list_filter` deliberately omits `is_active`** — a threat has no such field, and
a filter naming a field the model lacks is an `admin.E116` crash on load.

**Tests** — `apps/core/tests/test_security_{models,forms,views,security}.py` — **52 test functions
expanding to 126 cases** (19 / 14 / 82 / 11; the views and forms lanes are heavily parametrised),
with fixtures appended to `apps/core/tests/conftest.py` under a **`sec_*`** prefix. The prefix is
not cosmetic: `apps/core/tests/test_security.py` already exists as a **pre-existing 0.9-era generic
CSRF/IDOR file** unrelated to 0.18, and `test_security_security.py` lands right beside it. The
centrepiece is `test_security_forms_every_choices_value_is_a_clean_error_or_a_pass`, the permanent
form of the sweep that found the C1 500 — a `ValidationError` keyed on a field the form does not
have makes Django *raise*, so this asserts every error is keyed on a real field.

**Two severity lists, and only the second is a duplication bug.** `SecurityThreat` and
`SecurityIncident` reuse `AlertRule.SEVERITY_CHOICES` **by reference** — identity, not equality; the
tests assert `is`. `VulnerabilityFinding.severity` is a **CVSS band** and deliberately is NOT that
list: a firing severity and a CVSS band are different facts. Do not "fix" it by pointing the finding
at the alert vocabulary.

**`SecurityIncident.regulatory_deadline` is a `@property`, never a column** — GDPR Art. 33(1)'s
72 hours derived from `discovered_at`, so the anchor and the deadline cannot drift. Displayed, never
acted on: no scheduler, and NavERP files nothing with any authority.

**The L52 seeder ruling is total and must not be "fixed".** `_seed_security` seeds exactly ONE row
(a `VulnerabilityFinding`, whose `evidence` states NavERP ran no scanner) and creates **zero**
`SecurityThreat`, `SecurityIncident` and `IpAccessRule` rows. A seeded incident would start a live
72-hour Art. 33 clock against a breach that never happened, and a past `discovered_at` renders as
**overdue** on first load — a demo database accusing its own operator of an unreported breach. All
three are in `temp/audit_integrity.py`'s `KNOWN_OK` with that reason printed. The empty registers and
their boards are the truth about a system that detects, blocks and files nothing; a test that finds
zero of them is correct, not broken.

**Honest prose is enforced, not optional.** `SECURITY_NOTES` in `views/Security.py` is printed
verbatim by the overview, all four boards and all sixteen register pages, so a page and its board can
never disagree about what this application can and cannot do.

**Known, accepted limitation — do not fix here (0.18's counterpart to 0.17's).**
`SecurityIncident.affected_services` is an **M2M**, and `TenantConsistentMixin` walks `ForeignKey` and
`OneToOneField` only, so it is **not** tenant-checked on the **admin** save path. `TenantModelForm`
narrows M2M querysets, so the form path is covered. Same posture as 0.17's `Incident.affected_services`
and 0.16's escalated C7. **Do not change `TenantModelForm`** — it would break committed tests in
three apps. If a fix is ever wanted, scope it to
`SecurityIncidentAdmin.formfield_for_foreignkey` for this one field.

## Multi-tenancy (mandatory)

Every model carries `tenant = models.ForeignKey('core.Tenant', …)` and every view filters
`Model.objects.filter(tenant=request.tenant)` — never `.all()`. `request.tenant` is set by
`apps.core.middleware.TenantMiddleware` from the logged-in user.

**Two deliberate exceptions, both documented in their model docstrings:**
- **Global masters with no `tenant` FK** — `accounting.Currency` (ISO 4217), `core.Language`,
  `core.TimeZone`. A currency, a language and an IANA zone are facts about the world, not a workspace.
  Their views are `@login_required` read-only lists with **no CRUD routes** (a write would need a
  platform-admin gate this repo does not have).
- The superuser `admin` has `tenant=None` **by design** and correctly sees no module data.

`crud_list`-based views deliberately **do not** guard `tenant is None` — an empty register *is* the correct
rendering for the superuser, and all 487 call sites behave this way. Only views that would otherwise
compute nonsense (the boards, the singletons) take the `messages.info` + redirect branch.

## Conventions & gotchas that have actually bitten here

- **Decorator order decides 405 vs 403.** Decorators apply bottom-up, so the OUTERMOST runs first. Put
  `@require_POST` **above** `@tenant_admin_required` so a wrong method is 405 regardless of role (7.7's
  ruling). `@login_required` above `require_POST` is fine.
- **`apps/core/views/_common.py` star-exports only** `get_user_model, login_required, JsonResponse,
  get_object_or_404, render, require_POST, crud_*, run_search, tenant_admin_required, Party, User`.
  It does **not** export `messages`, `redirect`, `timezone`, `Q`, `F`, `Count` or `Max` — import them
  explicitly or you get a `NameError` on a path a smoke test may not hit.
- **A `unique_together` that includes `tenant` is NOT validated by a `ModelForm`,** because `tenant` is
  never a `Meta.fields` member: `Model._get_unique_checks()` drops any `unique_together` containing an
  excluded field. The form validates, `crud_create` saves, and MySQL returns an `IntegrityError` **500**.
  Guard it in the form (`clean_<field>`, scoped to `self.tenant`, excluding `self.instance.pk`) — the shape
  is in `apps/crm/forms/CustomerSuccess/HealthScores.py` and `apps/core/forms/Localization.py`.
- **Give each entity its OWN seeder guard.** A tenant-wide guard silently strands every entity added
  later — that is exactly what happened to 0.6's module scopes.
- **`.alert` / `.alert-info` / `.alert-danger` do NOT exist in `static/css/theme.css`.** The inline-notice
  pattern is `<p class="text-muted">` (variants `.text-warn`, `.text-ok`, `.text-danger`, `.text-brand`).
  Badge palettes are colour-named only: `badge-green/red/amber/info/muted/slate`.
- **`AuditLog.action` is `varchar(10)`** and `.create()` never validates `choices` — a longer action
  truncates silently (or raises `DataError` under `STRICT_TRANS_TABLES`). Put the verb in `changes`.
- **A derived property calling `.filter()` bypasses the prefetch cache** (only `.all()` reads it). Compute
  in the view off the prefetched list and pass it as context.
- **Probe the EMPTY state and the tenant-less superuser.** A context key derived from a tenant-scoped
  variable 500s with no tenant. Always test no-param and junk-param requests.
- **Never interpolate user text into a single-quoted JS literal in `onsubmit`** — use `|escapejs` (L42).
- **No delete path erases bytes.** Django never unlinks a `FileField` on row delete, so "delete" is a UI
  claim unless something explicitly unlinks.

## Sidebar wiring

`apps/core/navigation.py` holds `parse_catalog()` (builds the 0–23 catalog from `NavERP.md`),
`MODULE_ICONS`, and **`LIVE_LINKS`** — the authoritative "is `N.M` built" map. A sub-module is Live iff it
has a `LIVE_LINKS["N.M"]` entry. Keys must be the **exact** `NavERP.md` bullet strings: `resolve_nav`
silently drops an unmatched key and silently appends an unknown one, so a typo produces a missing link
with no error.

## Common tasks

- **Add a sub-module:** build the entity file(s) → re-export in each package `__init__.py` → urls in the
  flat `apps/core/urls.py` (literals before `<int:pk>`) → templates at `templates/core/<entity>/<page>.html`
  → admin → extend `seed_core.py` → one `LIVE_LINKS["N.M"]` entry → `makemigrations core` → `migrate` →
  `seed_core` ×2 → `manage.py check`.
- **Verify a sub-module:** `venv\Scripts\python.exe temp\audit_integrity.py` — six checks, all must pass.
  It catches the four failure modes `manage.py check` cannot see (unapplied migration, unreversible route,
  missing template, broken sidebar target).
- **Run the tests:** `venv\Scripts\python.exe -m pytest apps/core/tests --nomigrations` (~84–186× faster
  than applying migrations). `--nomigrations` cannot catch an unapplied-migration defect — keep one run
  **without** it as the phase gate.
- **Module 0 is not covered by `/next-module`.** That skill's own SKILL.md says to edit the foundation
  directly; a bare run auto-detects module 7. Build Module 0 sub-modules explicitly.
