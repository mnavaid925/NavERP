# Research — Sub-module 7.18: Integration & API Hub (Module 7 — Project Management, `projects`)

- **Sub-module:** 7.18 Integration & API Hub · **Module:** 7 Project Management · **App:** `apps/projects`
- **Base commit:** `2a654500f47b2f543ed310960c44546bf6ece533` (HEAD at research time; the working tree carries
  files from other sessions — see §1.1, none of them ours)
- **Date:** 2026-09-20 · **Phase:** 1 (research) · **Output:** this file only (read-only research agent)
- **Mission.** 7.18 is the **connector + sync-run layer** of the Project Management module: a project-scoped
  register of connections to the five families of outside systems named in NavERP.md §7.18 (ERP/finance,
  CRM, HR/talent, DevOps, file storage), the **field mappings** that teach each connection what local project
  field answers to which remote field, the **sync jobs** that scope a transfer, and the **append-only run log**
  recording what each sync did. It writes no ledger row, mirrors no file and runs no outbound HTTP (the whole
  house ships transport deferred — `scm` 4.19, `inventory` 5.19, `crm` 1.10 and 7.17 all do); it **records and
  configures**, and the model docstrings must say so out loud. 7.17 owns event *push* (webhooks); 7.18 owns
  scheduled/triggered data *sync*. Where they touch, 7.18 points at `ProjectWebhookEndpoint` by FK and
  re-declares nothing.

## 1. Repo state checked first (evidence, not docs)

### 1.1 Module 7 sidebar state (`apps/core/navigation.py`)
`Select-String '^    "7\.\d+": \{'` → keys present: **7.1–7.15** (:1787–:2023) and **7.17** (:2024–:2040).
**There is no `"7.16"` key**, while 7.16's models/routes *do* exist on disk (migration
`0024_projectdashboard_dashboardwidget_projectreport_and_more.py`, `urls/ReportingBusinessIntelligence/ReportingHome.py`)
→ **7.16 is mid-flight in a sibling session**; two 7.16 files are untracked in the working tree. Treat every
7.16 file as read-only and expect `LIVE_LINKS`, `_seed_tenant` and the `--flush` block to be hot (L43).

### 1.2 7.17 is built and is the immediate neighbour to respect
- `apps/projects/models/WorkflowAutomation/Webhooks.py` — `ProjectWebhookEndpoint` [`PWH-`] (:15) +
  `ProjectWebhookDelivery` (:107); migration `0025_projectwebhookdelivery_pwh_del_tnt_att_idx_and_more.py`.
- URLs (`apps/projects/urls/WorkflowAutomation/Webhooks.py`): `pwh_list`, `pwh_create`, `pwh_detail`,
  `pwh_edit`, `pwh_delete`, `pwh_toggle_active`, `pwh_test_ping`, `pwh_rotate_secret`, `pwh_delivery_list`,
  `pwh_delivery_detail` — first segment `webhooks/`.
- Board/lens precedent (`urls/WorkflowAutomation/AutomationBoards.py`): `automation_overview`,
  `approval_inbox`, `recurrence_calendar`, `webhook_diagnostics` — free-form names, literal paths under a
  two-word first segment (`automation/…`).
- Templates on disk: `templates/projects/WorkflowAutomation/{workflow,approvalgate,recurringtask,webhook,boards}/…`
  but the views **render lowercase**: `"projects/workflowautomation/webhook/list.html"` (see
  `apps/projects/views/WorkflowAutomation/Webhooks.py:59`, `:94`). On NTFS both spellings are the same file;
  the *render string* is the contract (see Risks §6.1).

### 1.3 Migration + prefix state
- `apps/projects/migrations/` ends at **`0025_…`** → 7.18 claims **`0026_…`** (re-check `ls` immediately before
  generating; L43).
- Prefixes taken **inside `projects`** (grep `NUMBER_PREFIX =`): PRJ PRQ PST PKO TSK DEP BSL MST RAL RSP RTE CCA
  PBL PEX BVR RSK ISS RRA ESC QPL QRV QCI QDF REQ SCI SCR SVR TBK TCL CHN CHM MTG AGI MAIT NTF DSH PFD DTM PDM
  KNE TAC OTR POT PRT PGM PIN PDEP EPC SPT IMP RET CPA CFB SOW SWA VHD PCI RTC PBR PRS PPR PDB REP RUN **PWF PAR
  RTS PWH**.
- Repo-wide (`apps/**/models`): no `IXC`, `IXM`, `SYJ`, `SYR` anywhere; `CNX`, `MSG`, `WHK`, `INT`, `SYN`, `API`,
  `WH`, `WFR` are taken by other apps. **Free and recommended: `IXC-` (connector), `SYJ-` (sync job),
  `SYR-` (sync run).** The field-mapping child is deliberately **unnumbered** (see §5.2).

### 1.4 URL-namespace check for 7.18 (run, not assumed)
`Select-String -Path apps\projects\urls\**\*.py -Pattern 'path\("(integration|sync|connector|mapping)'` → **0 hits**;
`-Pattern 'name="[a-z_]*(integration|sync|connector|mapping|ixc|syj|syr)[a-z_]*"'` → **0 hits**. The `projects:`
namespace has **no `integration*` first segment and no colliding route name**, so `integration/…` and the
`ixc_*`/`ixm_*`/`syj_*`/`syr_*` names are free. (`scm` has `integration-endpoints/` under the `/scm/` mount — a
different app and mount point; cannot collide.)

### 1.5 Seeder shape (as-built, plus one correction to the brief)
`apps/projects/management/commands/seed_projects.py` is a **monolith with per-sub-module methods**, not
`_seed_7NN_*` helpers: `handle()` (:314) → `_seed_tenant(tenant, now)` (:414) → `self._planning`, `_resourcing`,
`_cost`, `_risk`, `_quality`, `_scope`, `_taskwork`, `_collab`, `_docmgt`, `_time_attendance`,
`_portfolio_management`, `_agile_scrum`, `_client_collaboration`, `_financial_billing`,
**`_workflow_automation` (:4138)**. **There is no `_seed_717_workflow_automation`** — the brief's name does not
exist; the convention is `_<snake_case_submodule>`. 7.18's helper is therefore
**`_integration_hub(self, tenant, now)`**, called from `_seed_tenant` after `_workflow_automation`, with 7.17's
per-tenant guard (`if ProjectWorkflowRule.objects.filter(tenant=tenant).exists(): … return`).
`--flush` (:315–:412) deletes **children-first**, and 7.17's rows sit near the top
(`ProjectWebhookDelivery` → `ProjectWebhookEndpoint` → `RecurringTaskSchedule` → `ProjectApprovalGate` →
`WorkflowExecutionLog` → `ProjectWorkflowRule` → …). 7.18's deletes **must be inserted above 7.17's webhook pair**,
because the connector holds a `notify_webhook` FK into `ProjectWebhookEndpoint`.

### 1.6 As-built spine entities 7.18 links to — verified (grep `^class` + url grep)
| Entity | File | Number | URL names (from `apps/projects/urls/…`) |
|---|---|---|---|
| `Project` | `models/ProjectInitiation/Projects.py:27` | `PRJ-` | `prj_list` `prj_create` **`prj_detail`** `prj_edit` `prj_delete` (+`prj_submit_charter`, `prj_approve_charter`) |
| `ProjectTask` | `models/ProjectPlanningScheduling/ProjectTasks.py:45` | `TSK-` | `tsk_list` `tsk_create` `tsk_detail` `tsk_edit` `tsk_delete` (+`tsk_tree`) |
| `ProjectIssue` | `models/RiskManagement/ProjectIssues.py` | `ISS-` | `iss_list` `iss_create` `iss_detail` `iss_edit` `iss_delete` (+`iss_escalate`/`_resolve`/`_close`) |
| `ProjectDocument` | `models/DocumentKnowledgeManagement/Documents.py` | `PDM-` | `pdm_*` (+`pdm_checkout`/`checkin`/`archive`/`hold`/`release`/`reindex`) |
| `ProjectFolder` | `models/DocumentKnowledgeManagement/ProjectFolders.py` | `PFD-` | `pfd_*` (+`pfd_archive`) |
| `ResourceProfile` | `models/ResourceManagement/ResourceProfiles.py` | `RSP-` | `rsp_list` `rsp_create` `rsp_detail` `rsp_edit` `rsp_delete` |
| `ResourceAllocation` | `models/ResourceManagement/ResourceAllocations.py` | `RAL-` | `ral_*` (+`ral_assign`/`substitute`/`commit`/`complete`/`cancel`) |
| `ResourceTimeEntry` | `models/ResourceManagement/ResourceTimeEntries.py` | `RTE-` | `rte_*` (+`rte_submit`/`relog`/`approve`/`reject`/`approve_week`) |
| `ProjectWebhookEndpoint` | `models/WorkflowAutomation/Webhooks.py:15` | `PWH-` | `pwh_*` (see §1.2) |

- `Project` fields verified: `name`(255), `code`(30), `client → core.Party` (`related_name="delivery_projects"`),
  `project_manager`/`executive_sponsor` (`AUTH_USER_MODEL`), `org_unit → core.OrgUnit`, `status`
  (`draft·chartered·kickoff·active·on_hold·completed·cancelled`), `charter_status`, `start_date`/`end_date`.
- `ResourceProfile` **already FKs `hrm.EmployeeProfile`** (`ResourceProfiles.py:36`) and bare `core.Party`
  (`:39`), with `weekly_capacity_hours`, `utilization_target_pct`, `available_from/to`, `status` — the HR-pool
  link the HR/Talent bullet needs exists; 7.18 must not re-make it. `ResourceTimeEntry` is the time-data twin.
- Spine constants verified: `apps/core/crypto.py` (`encrypt`/`decrypt`, Fernet, `fernet.v1:` marker, idempotent,
  refuses to double-wrap, passes unmarked legacy values through); `apps/projects/models/_base.py`
  (`TenantOwned` :41, `TenantNumbered` :54, `number = CharField(20)`); `apps/projects/forms/_common.py`
  (`TenantModelForm`, `TenantUniqueMixin`, `_reject_foreign(form, cleaned, names)`);
  `apps/core/models/AuditLog.py:16` (`action = CharField(max_length=10)`) → **every audit verb ≤ 10 chars**
  (shipped verbs in `apps/projects/views` are all ≤10: `create update delete toggle rotate ping execute
  generate dispatch recognize promise contact lock skip escalate delegate approve reject resolve cancel`).

## 2. Source products researched

Scope: the **project/tool integration-hub** capability of leading project platforms, plus the connector-catalog
UX of the iPaaS class **only** where it informs a NavERP model (connector register → field mapping → sync job →
run log). Each entry says what it contributed and what was dropped as marketing fluff.

1. **Jira / Atlassian (integrations hub + Marketplace)** — `https://www.atlassian.com/software/jira/integrations`
   (read: "thousands of integrations, apps and more", Atlassian-product pairings, development-status sync,
   "automate your workflow in a few clicks", 3,000+ apps on Marketplace);
   `https://marketplace.atlassian.com/categories/integrations` **returned the Marketplace shell only (no listing
   data)** — treated as a failed fetch, not as evidence.
   *Contributed:* the concept of a **catalog of app connectors reached from one hub page**, and **development
   tooling as a first-class connector family** (bullet 4). *Rejected:* install counts, ratings, vendor tiers,
   hosting facets — marketplace merchandising, not a NavERP data model.
2. **Asana — App integrations directory** — `https://asana.com/apps` (read: Collections, 14 categories incl.
   **Connectors, Files, Finance and HR, IT and Development, Time Tracking, Reporting, Sales and Services**,
   partner tiers, and a "building an app? learn about our API" path; named connectors: Salesforce + Asana,
   Jira Cloud, Slack, Microsoft Teams, Okta/Entra ID, Google Drive, HubSpot, Zapier/Make/Relay, and Unito
   "**2-way sync … real-time, automated updates across tasks, projects and portfolios**").
   *Contributed:* a category taxonomy that maps almost 1:1 onto the five NavERP bullets (Finance/HR → 1+3,
   Sales/Services → 2, IT & Development → 4, Files → 5), "**managed securely by your organization**" (why a
   connector row needs an owner and a scope), and two-way sync as the direction vocabulary. *Rejected:* partner
   badges.
3. **ClickUp — Integrations** — `https://clickup.com/integrations` (read: "1,000+ tools", native-vs-marketplace
   split, per-connector capability text: GitHub "**sync commits, branches, pull requests and issues**", GitLab
   and Bitbucket equivalents, HubSpot "**sync CRM data, tickets and properties**", Google Drive / OneDrive /
   **Dropbox / Box**, Everhour/Toggl/Harvest **time sync**, Zapier/Make/Relay, Webhooks, and the **Open API**).
   *Contributed:* the **entity-scope vocabulary** a project connector actually moves (issues/PRs/CRM records/
   files/time) → `ProjectSyncJob.entity_scope`; and file storage as a **connector family**, not a feature
   (bullet 5). *Rejected:* per-app blurb copy.
4. **Smartsheet — Integrations** — `https://www.smartsheet.com/integrations` (read: "**over 175 integrations**",
   six working groups — *Enterprise systems & operations / AI / Messaging / Content & collaboration / Workflow
   automation / Security & governance* — featured Jira Software, Power BI, Salesforce, M365 & Google suite incl.
   OneDrive/Google Drive/Entra ID, **Bridge by Smartsheet** (low-code, "pre-built system connections, APIs and
   JavaScript"), a partner marketplace, and the FAQ that integrations "connect data across your enterprise
   systems like **CRMs, HCMs and ERPs**").
   *Contributed:* the **five-family framing (CRM · HCM · ERP · DevOps · content)** the NavERP bullets already
   use, and "some connectors are included, some are add-ons" → lifecycle/status columns, not billing.
   *Rejected:* MCP/AI-connector merchandising.

5. **Wrike — Apps & Integrations** — `https://www.wrike.com/apps/` (read: filter facets *CRM, Email, Export/
   Import, Extensions, **File storage**, Chat/Messaging, SSO, Software/IT, BI, Visual collaboration*; 60 listed
   apps; Salesforce, Tableau, Microsoft/Google collections; the **Wrike Integrate** add-on for "cloud and
   on-premises apps"; two-way sync with Miro "powered by Unito"; MCP server; API portal).
   *Contributed:* the **filter-facet model of an integrations hub** (7.18's domain filter) and the cloud/on-prem
   connector distinction. *Rejected:* "AI everywhere" framing.
6. **Workato — Integration Library** — `https://www.workato.com/integrations` (read: pre-built connectors to
   SaaS apps, databases and ERPs "**both on-prem and in the cloud**"; 18 categories incl. **Product/Project
   Management, HR, Finance and Accounting, Developer, DevOps/IT, Collaboration, Security & Compliance**; a flat
   A–Z directory with one entry per app — Asana, Jira, Workday (**and six other Workday variants**), Wrike,
   Workfront, SharePoint, ADP Workforce Now, Box/Drive/Dropbox-class storage; plus a **connector SDK**).
   *Contributed:* "one row per connector, category as the discriminator" (NavERP's house style already) and the
   fact that one app can need **several connector variants** → justify a closed `provider` list **plus**
   `remote_scope_ref`, never free text. *Rejected:* recipe-marketplace/partner economics.
7. **Adobe Workfront Fusion** — `https://experienceleague.adobe.com/en/docs/workfront-fusion/using/get-started-with-fusion/understand-workfront-fusion/workfront-fusion-overview`
   (read: "linking actions within and between apps to create a **scenario** that transfers and transforms data
   automatically"; **connections** for auth, **scenario execution history and debugging**, filters, iteration,
   data stores; dedicated connectors for Adobe/Google/Microsoft "and many others"; and a generic HTTP path for
   "any service with a public API").
   *Contributed:* the **connection → scenario → execution history** triad (7.18's three main models) and the
   "no dedicated connector → generic" fallback, which is why `provider="custom"` must exist. *Rejected:*
   operation-count metering.
8. **Fivetran — Connector directory** — `https://www.fivetran.com/connectors` (read: "**750+ sources and 200+
   destinations**"; facets by connector/activation source vs destination and by **release status** — *Private
   preview / Beta / New*; connector **types** — Standard / Lite / Partner-built / **Connector SDK**;
   "end-to-end automation with built-in **schema drift** handling"; "**reliable syncs with automated retries and
   idempotent delivery**"; "**incremental**" replication).
   *Contributed:* run-log columns a PMO would actually read (**records read vs landed vs failed, incremental vs
   full, retries, idempotency**) and the **release-status facet** → a lifecycle/stage idea, not just up/down.
   *Rejected:* ELT warehouse architecture as a NavERP feature.
9. **In-repo prior art read as a ninth "product" surface** (analysed in §4, not web-researched here):
   `scm` 4.19's `IntegrationEndpoint`/`IntegrationMessage`/`WebhookSubscription`/`WebhookDelivery`
   (`research-scm-4.19.md`), `inventory` 5.19's `IntegrationChannel`/`ChannelListingMap`/`StockSyncRun`/`ApiClient`
   (`research-inventory-5.19.md:93-131,200-330`), `accounting` 2.15's `IntegrationConfig`, `crm` 1.10's
   `Webhook`/`WebhookDelivery`, and 7.17's own `ProjectWebhookEndpoint`. These fixed the *shape* of this pass
   more than any vendor page: they are why 7.18 re-declares no webhook, no delivery log and no supply-chain
   connector.
   Fetches that **failed and are NOT used as evidence**: `monday.com/apps` (HTTP 404), `wrike.com/integrations/`
   (404 — the live page is `/apps/`), `unito.io/sync/` (404), the Atlassian Marketplace category page (shell
   only), and Adobe's own Workfront-integrations landing page (timeout).

## 3. Feature catalogue (this sub-module only, deduplicated + prioritised)

Priority key: **must** = table-stakes for a project integration hub · **should** = common in the surveyed
leaders and cheap on this spine · **later** = needs transport/scheduler/write access NavERP does not ship.

### 3.1 Bullet 1 — ERP & Financial System Sync (SAP, Oracle, NetSuite, Workday, Dynamics)

| # | Feature (seen in) | Bullet | Prio | NavERP spine mapping | Decision |
|---|---|---|---|---|---|
| 1 | **Named, typed connector register** — one row per connection to one outside system (Workato library, Workfront Fusion "connections", Smartsheet enterprise systems, Jira hub) | 1 | must | NEW `ProjectIntegrationConnector` [`IXC-`]; nullable FK `projects.Project` | build now |
| 2 | **Closed `provider` vocabulary**, not free text — SAP/Oracle/NetSuite/Workday/Dynamics + custom (Workato's 6 Workday variants; 4.19's own "SAP / sap / S.A.P. are three systems" note) | 1 | must | `provider` on IXC | build now |
| 3 | **Sandbox vs production target** per connector (Celigo/Boomi posture, 4.19) | 1 | must | `environment` on IXC | build now |
| 4 | **Auth intent recorded, incl. OAuth2 without token storage** + pasted API key where the provider allows (Workato/Workfront Fusion auth "connections") | 1 | must | `auth_method` + encrypted `credential` | build now |
| 5 | **Credential rotation with one-time reveal + masked display**; never plaintext at rest (crm 1.10, 7.17, 4.19's §"Secrets") | 1 | must | `credential` + `set_credential`/`get_credential`/`credential_masked` + POST `ixc_rotate_credential` | build now — **encrypt, do not hash** (§4.6) |
| 6 | **Remote scope identifier** (SAP company code, NetSuite subsidiary, chart-of-accounts ref) (Workato NetSuite/Workday connectors) | 1 | should | `remote_scope_ref` on IXC | build now |
| 7 | **Financial entity scopes** (journals, bills, cost lines) as a *scope name* on a sync job — **no ledger row is ever written** (Workato finance use-cases; L29) | 1 | should | `ProjectSyncJob.entity_scope` values `budgets`/`cost_lines`/`journals` | build now (names only) |
| 8 | **Connection health** — last success, consecutive failures, would-auto-disable (Fivetran "automated retries"; Svix auto-disable) | 1 | should | `last_sync_at`/`last_success_at`/`consecutive_failures` (`editable=False`) + `connector_health` lens | build now |
| 9 | **Connection test that produces evidence but sends nothing** (Fusion "debugging"; 4.19's `simulated` posture) | 1 | should | POST `ixc_test` → `ProjectSyncRun(status="simulated")` | build now (no HTTP) |
| 10 | Real SAP/Oracle/NetSuite push-pull (RFC/SOAP/OAuth refresh/token vaults) | 1 | later | none — needs transport + scheduler (platform infra) | defer |

### 3.2 Bullet 2 — CRM Integration (Salesforce, HubSpot, Microsoft Dynamics Sales)

| # | Feature (seen in) | Bullet | Prio | NavERP spine mapping | Decision |
|---|---|---|---|---|---|
| 11 | **CRM connector family** + `salesforce`/`hubspot`/`dynamics_sales` providers (Asana+Salesforce, Wrike+Salesforce, ClickUp+HubSpot, Smartsheet+Salesforce) | 2 | must | `domain="crm"` on IXC + category route `ixc_crm_list` | build now |
| 12 | **Client-project linkage** — map CRM account/contact to the project's client (Asana "client work", Wrike CRM facet) | 2 | must | mapping rows local `client.name` ↔ remote `Account.Name`, over `Project.client → core.Party` | build now (rows only) |
| 13 | **Match/identity key per mapping** (external id ↔ local id) — de-dupe + idempotency (Fivetran "idempotent delivery", 5.19 `ChannelListingMap`) | 2 | must | `ConnectorFieldMapping.is_key` | build now |
| 14 | **Direction on the mapping *and* on the job** (Asana/Unito "2-way sync"; clickup "sync … between") | 2 | must | `direction` on IXM + SYJ | build now |
| 15 | **Value translation table** (stage/status/picklist ↔ local choice) | 2 | should | `value_map` JSONField on IXM | build now |
| 16 | **Conflict policy for two-way sync** (Unito conflict handling; Fivetran idempotency) | 2 | should | `conflict_policy` on SYJ | build now |
| 17 | Deal-stage → project-status **write-back** to the CRM | 2 | later | needs CRM write verbs (`crm.Opportunity` is crm's) | defer |
| 18 | Opportunity link at project intake | 2 | — | **already built**: `ProjectRequest.opportunity → "crm.Opportunity"` string FK (`ProjectRequests.py:107`) | reuse, never rebuild |

### 3.3 Bullet 3 — HR & Talent Systems (Workday, BambooHR, ADP: resource pools + time data)

| # | Feature (seen in) | Bullet | Prio | NavERP spine mapping | Decision |
|---|---|---|---|---|---|
| 19 | **HRIS family** + `workday`/`bamboohr`/`adp` providers (Asana "Finance and HR", Workato HR & Recruiting) | 3 | must | `domain="hris"` + route `ixc_hris_list` | build now |
| 20 | **Resource-pool scope** — worker directory syncs *to/from* the pool (Workato HR; ClickUp time apps) | 3 | must | `entity_scope="resources"`; the pool is the built `ResourceProfile` (`hrm.EmployeeProfile` at `ResourceProfiles.py:36`) | build now |
| 21 | **Time-data scope** — hours/timesheets moved to/from the HRIS/payroll system (ClickUp+Everhour/Toggl/Harvest; Workato "payroll/benefits/time") | 3 | must | `entity_scope="time_entries"` over `ResourceTimeEntry` [`RTE-`] | build now |
| 22 | Capacity & availability as mapping targets (the HRIS is the source of truth for FTE/capacity) | 3 | should | mapping rows naming `weekly_capacity_hours`, `utilization_target_pct`, `available_from/to` — the columns stay `ResourceProfile`'s | build now (rows only) |
| 23 | **Worker identity as a match key, never a second person table** | 3 | must | `is_key` mapping + `remote_scope_ref`; no new person/employee model (Party/PartyRole rule) | build now |
| 24 | ADP payroll runs / pay statements written back | 3 | later | money is accounting's (`PayrollRun`), L29 | defer |

### 3.4 Bullet 4 — Development & DevOps Tools (Jira, GitHub, GitLab, Azure DevOps, CI/CD)

| # | Feature (seen in) | Bullet | Prio | NavERP spine mapping | Decision |
|---|---|---|---|---|---|
| 25 | **DevOps family** + `jira`/`github`/`gitlab`/`azure_devops` providers + a generic `ci_cd` (ClickUp GitHub/GitLab/Bitbucket, Asana+Jira Cloud, Smartsheet+Jira Software, Wrike Software/IT facet) | 4 | must | `domain="devops"` + route `ixc_devops_list` | build now |
| 26 | **Remote project key / repo slug** (a Jira project key or `org/repo` is the scope everything hangs off) | 4 | must | `remote_scope_ref` on IXC | build now |
| 27 | **Entity scopes mapped to built project records** — "sync commits, branches, pull requests and issues" (ClickUp) → NavERP issues/tasks/risks | 4 | must | `entity_scope` values `tasks`·`issues`·`risks` over `ProjectTask` [`TSK-`] / `ProjectIssue` [`ISS-`] / `ProjectRisk` [`RSK-`] | build now |
| 28 | **Status & label translation** (Jira To Do/In Progress/Done ↔ NavERP statuses) | 4 | should | `value_map` on `ConnectorFieldMapping` | build now |
| 29 | **Batch counts per run** (read / created / updated / failed) rather than one row per record (Fivetran "reliable syncs", ClickUp activity sync) | 4 | must | `ProjectSyncRun` counters | build now |
| 30 | Developer identity ↔ `ResourceProfile`/user for worklog attribution | 4 | should | mapping rows + `entity_scope="time_entries"` | build now |
| 31 | **CI/CD pipeline status arriving as an event** (build failed → task blocked) | 4 | should | **7.17 owns the push**: `ProjectWebhookEndpoint` [`PWH-`] receives it; 7.18 only records the resulting sync run | FK only — no new model (§4.8) |
| 32 | Running the pipeline / triggering a build from NavERP | 4 | later | needs transport + provider write scopes | defer |

### 3.5 Bullet 5 — File Storage & Collaboration (SharePoint, Google Drive, Dropbox, Box)

| # | Feature (seen in) | Bullet | Prio | NavERP spine mapping | Decision |
|---|---|---|---|---|---|
| 33 | **Storage family** + `sharepoint`/`google_drive`/`dropbox`/`box` providers (ClickUp native Drive/OneDrive/Dropbox/Box; Asana Files category; Smartsheet Content & collaboration; Wrike File storage facet) | 5 | must | `domain="storage"` + route `ixc_storage_list` | build now |
| 34 | **Folder & document scopes onto the built registers, no byte mirroring** | 5 | must | `entity_scope="folders"`·`"documents"` over `ProjectFolder` [`PFD-`] / `ProjectDocument` [`PDM-`] (7.10 owns the bytes under `MEDIA_ROOT`) | build now (references only) |
| 35 | **Remote path / library id per mapping** (external file id ↔ local document, Drive path ↔ folder) | 5 | must | `ConnectorFieldMapping.remote_field` + `is_key` | build now |
| 36 | **Incremental "modified-since" cursor** and sync cadence recorded as intent (Fivetran incremental; Drive/SharePoint deltas) | 5 | should | `ProjectSyncJob.interval_minutes` + `filter_expression` (recorded, never evaluated) + docstring | build now (recorded) |
| 37 | Scheduled library/Drive delta sync actually running | 5 | later | no scheduler/transport in this build | defer |
| 38 | **Permission & sharing mirroring** (who may see which document) | 5 | later | 7.9 `DocumentShare` + core ACL own permissions | defer |

### 3.6 Beyond the five bullets (the hub surfaces the surveyed products all ship)

| # | Feature (seen in) | Bullet | Prio | NavERP spine mapping | Decision |
|---|---|---|---|---|---|
| 39 | **Integration-hub cockpit** — connectors by domain/status, failures today, credentials due for rotation (4.19's exceptions cockpit, Fivetran/Smartsheet dashboards) | all | should | `integration_hub` lens page | build now |
| 40 | **Sync monitor** — the run queue, retry stamps, last success per connector (Fusion "execution history", Workato job reports, Fivetran sync logs) | all | must | `sync_monitor` lens page | build now |
| 41 | **Per-connector health page** — success rate, avg duration, mapping coverage, last error (Svix/Celigo posture) | all | should | `connector_health` lens page | build now |
| 42 | **Retry that moves only queue state + stamps a backoff slot, performing no HTTP** (Fivetran retries; 4.19's `DELIVERY_BACKOFF_SECONDS`, Svix's 8-slot tuple) | all | must | POST `syr_retry` on the run log + `next_retry_at` stamp | build now |
| 43 | **Failure alerts routed to the project's existing webhook endpoint** (Jira/Smartsheet alert-on-failure; 7.17 owns delivery) | all | should | `ProjectIntegrationConnector.notify_webhook → ProjectWebhookEndpoint` (SET_NULL) | build now (FK only) |
| 44 | **Dry-run/preview before committing a sync** (Fusion debugging; Jira rule sandbox) | all | should | `ixc_test` / `syj_run` writing `status="simulated"` rows | build now |
| 45 | Background worker / scheduler (Celery, cron) that fires jobs on a clock | all | later | platform-level infra, out of every sub-module's scope | defer |

**Out of scope, parked to siblings:** auto-provisioning users from Okta/Entra ID (SSO, Module 1 `accounts`);
document retention & legal hold (7.10 `DocumentKnowledgeManagement`); client-facing portal sync (7.14);
timesheet approval loops (7.11); master-data template/methodology import (7.19).

## 4. Boundary & ownership — decided with grep evidence

### 4.1 What already exists, file by file (every one of these was opened and read)

**(a) `apps/projects/models/WorkflowAutomation/Webhooks.py` — 7.17, the immediate sibling.**
`ProjectWebhookEndpoint(TenantNumbered)` `NUMBER_PREFIX = "PWH"` (`:15–:18`) with `project` FK **`null=True,
blank=True`** ("Null implies tenant-wide webhook"), `name`, `target_url` (`URLField(500)`), `secret`
(`CharField(512)`, Fernet ciphertext, generated server-side by `generate_secret()` in `pwh_create`);
`is_active`, `event_types` (JSON list), `custom_headers` (JSON), `last_status_code`, `last_fired_at`,
`failure_count` (all three `editable=False`); plus `get_secret()`, `set_secret()`, `generate_secret()`,
`compute_signature()` (HMAC-SHA256), `verify_signature()`, `is_active_badge`, `health_badge`. Child
`ProjectWebhookDelivery(TenantOwned)` (`:107`) with statuses `success·failed·simulated`, `payload` JSON,
`signature`, `status_code`, `response_body`, `duration_ms`, and three indexes (`pwh_del_tnt_wh_stat_idx`,
`pwh_del_tnt_att_idx`, `pwh_del_tnt_stat_att_idx`).
**Proves:** outbound endpoint config, HMAC signing and the delivery log are **7.17's**; 7.18 must not re-declare
*any* of `target_url`, `secret`, `event_types`, `custom_headers`, `compute_signature`, `ProjectWebhookDelivery`,
nor a second "delivery" table.

**(b) `apps/scm/models/IntegrationApiGateway/IntegrationEndpoints.py` — 4.19, `IntegrationEndpoint` [`CNX-`].**
A **tenant-global, transport-less** connection register: no project/business scope at all —
`TENANT_SCOPED_FKS = ("partner_party", "logistics_client", "location", "spec_document")`;
`unique_together = (("tenant", "number"), ("tenant", "name"))`; the credential is a **marker**:
`credential_prefix` (`CharField(12)`) + `credential_hash` (`CharField(64)`), both `editable=False`, written only
by `set_credential()`, displayed only through `masked`. Its own module docstring states the rule this pass must
obey: *"Hashing is NOT the general way to store an integration credential. Signing an outbound payload needs the
plaintext key, and authenticating to SAP or Shopify needs the real credential; SHA-256 is one-way … The general
fix for a key you must USE is ENCRYPTION AT REST"*, *"Prefix+hash is correct here and only here because 4.19
ships no transport"*, plus a **MIGRATION HAZARD** warning that the first transport pass cannot un-hash a digest.
**`ENDPOINT_CATEGORY_CHOICES` verbatim** (`apps/scm/models/IntegrationApiGateway/_choices.py:67-73`):
```python
ENDPOINT_CATEGORY_CHOICES = [
    ("erp", "ERP"),
    ("ecommerce", "E-commerce"),
    ("iot", "IoT"),
    ("edi", "EDI"),
    ("custom", "Custom"),
]
```
**`ENDPOINT_SYSTEM_CHOICES` verbatim** (`:81-97`): `sap, oracle, netsuite, dynamics, shopify, magento,
woocommerce, amazon, ebay, walmart, rfid_reader, barcode_scanner, sensor_gateway, edi_van, custom`.
**Proves:** 4.19's pinned vocabulary is **supply-chain only** — of §7.18's named systems it can express only
`sap`, `oracle`, `netsuite`, `dynamics`; **Jira, GitHub, GitLab, Azure DevOps, Salesforce, HubSpot, Workday,
BambooHR, ADP, SharePoint, Google Drive, Dropbox and Box have no member at all**, and the category list has no
CRM / HR / DevOps / storage discriminator.

**(c) `apps/scm/models/IntegrationApiGateway/IntegrationMessages.py` + `WebhookSubscriptions.py` +
`WebhookDeliveries.py`, and `apps/crm/models/AutomationWorkflow/Webhooks.py`.**
`IntegrationMessage` is **`MSG-`, not `INT-`** (the brief's guess is wrong): it is the **append-only** exchange
log (`IntegrationMessages.py:10-30` — "no create, edit or delete route … a wrong row is corrected by appending a
later, correct row"; **no ModelForm exists at all**), `endpoint` CASCADE, `document_type`, `control_number`,
`external_id` (de-dupe probe, deliberately **not** unique), `record_count`, `payload_excerpt`, `acknowledges`
self-FK, indexes `scm_msg_tnt_*`. `WebhookSubscription` is `WHK-`; `WebhookDelivery(TenantOwned)` is
**unnumbered** ("nobody chases WHD-04417 about the fourth retry"). In `crm`:
`Webhook` [`WH-`] draws `trigger_entity` from `crm.WorkflowRule.ENTITY_CHOICES` (a CRM vocabulary — the reason
scm shipped its own), `secret` is Fernet-encrypted in `save()` with `get_secret()` and a `secret_masked` that
**degrades** on `ImproperlyConfigured` instead of 500-ing; `WebhookDelivery(models.Model)` carries its own
`tenant` FK and statuses `pending·success·failed·simulated`.
**Proves:** the house pattern for a log is *append-only, list + detail, no form, retry/verb only*, and **the same
class name may exist twice on purpose when the vocabulary differs** — `crm.WebhookDelivery` vs
`scm.WebhookDelivery`, `crm.PurchaseOrder` vs `scm.PurchaseOrder`, and three `PRJ-` models
(`Projects.py:6-17` documents `accounting.Project` / `crm.CrmProject` / `projects.Project` coexisting).

**(d) `apps/accounting/models/Integration/IntegrationConfigs.py` — 2.15.** `IntegrationConfig(TenantOwned)`:
`PROVIDER_CHOICES` = plaid·stripe·paypal·square·avalara·vertex·shopify·woocommerce·salesforce·hubspot·
quickbooks·netsuite·workday·custom; `CATEGORY_CHOICES` = banking·payments·tax·ecommerce·crm·erp·hris·storage·
other; `STATUS_CHOICES` = disconnected·connected·error; `api_key_prefix(12)` + `api_key_hash(64)`
(`editable=False`), `last_sync`, `is_active`, `notes`, `set_secret`/`hash_secret`/`generate_secret`/`masked`;
docstring: *"Live sync against the provider is deferred."*
**Proves:** the **finance-side** connector register already exists and is accounting's; it is `TenantOwned`
(unnumbered) and deliberately finance-scoped. 7.18 must not write into it, FK it, or treat it as the project
connector.

**(e) `apps/core/crypto.py`** — `encrypt(plaintext)` / `decrypt(stored)`, Fernet, `fernet.v1:` marker,
idempotent, refuses to double-wrap, passes legacy plaintext through unchanged. Its docstring states the decision
rule 7.18 follows: *"This is deliberately NOT the prefix + SHA-256 pattern … A key used to **sign** an outbound
payload is the opposite case."*
**Proves:** the reversible store already exists in the spine and is the right tool for a credential that must be
presented to SAP/Jira.

**(f) `apps/inventory/models/ThirdPartyIntegrations/` — 5.19 (shipped).** `IntegrationChannel` [`INT-`],
`ChannelListingMap(TenantOwned)` (local SKU ↔ external id ↔ location, `TENANT_SCOPED_FKS = ("channel","item",
"location")`), `StockSyncRun` [`SYN-`] (append-only run log with `records_*` counters, a mandatory-honesty
`simulated` status, a `next_retry_at` **stamp**, the Svix backoff tuple, and `record()` as the only writer),
`ApiClient` [`API-`]. Its research file records the ruling that decides this section
(`research-inventory-5.19.md:123-131`): *"5.19 does NOT re-declare a generic gateway … Peer apps do not import
each other's internals … so 5.19 does not FK scm.IntegrationEndpoint either — it owns its own narrow register and
keeps NO EDI/IoT vocabulary. Same two-vocabularies precedent as crm.Webhook vs scm.WebhookSubscription."*
**Proves:** **two shipped sub-modules have already faced exactly this question and both answered with a narrow,
app-owned register.** 5.19 is the closest structural precedent to 7.18 in the whole repo (connector + mapping
child + numbered run log).

### 4.2 The grep the brief asked for — run, and it REFUTES the brief's assumption

```powershell
$f = (Get-ChildItem 'apps\projects\models' -Recurse -Filter *.py).FullName
Select-String -Path $f -Pattern '"(accounting|scm|crm|hrm|inventory|procurement)\.[A-Za-z]'
Select-String -Path $f -Pattern 'apps\.(accounting|scm|crm|hrm|inventory|procurement)\.'
```
**Result 1 — `projects` DOES string-FK peer apps today (21 hits, 17 of them in `models/`):**
`accounting.Currency` ×7 (`ClientInvoices.py:57`, `StatementOfWorks.py:56`, `BudgetRevisions.py:45`,
`ProjectExpenses.py:74`, `BillingRuns.py:128`, `RateCards.py:47`, `Portfolios.py:46`),
`accounting.GLAccount` ×3 (`CostControlAccounts.py:52`, `ProjectBudgetLines.py:51`, `ProjectExpenses.py:66`),
`accounting.Invoice` ×3 (`ClientInvoices.py:83`, `BillingRuns.py:144`, `PaymentRecords.py:62`),
`accounting.TaxCode` (`BillingRuns.py:104`), `accounting.FiscalPeriod` (`RevenueSchedules.py:49`),
`accounting.JournalEntry` (`RevenueSchedules.py:112`), `crm.Opportunity` (`ProjectRequests.py:107`),
`hrm.EmployeeProfile` (`ResourceProfiles.py:36`).
**Result 2 — zero hits:** `Select-String … 'apps\.(accounting|scm|crm|hrm|inventory|procurement)\.'` over
`apps/projects/models` → **0 rows**, i.e. peer models are always referenced **by string label**, never imported
(the same house rule `apps/projects/models/_base.py:8-9` states: *"peer apps deliberately don't import each
other's internals"*).
**Result 3 — the narrow claim that actually matters HOLDS:** there is **no `scm.`, `inventory.` or
`procurement.` FK anywhere in `apps/projects`** — `scm.IntegrationEndpoint` has never been pointed at from this
app, and `projects` has no SCM coupling at all. So (a) would not be "extending existing precedent", it would be
**inventing a new projects→scm edge to hang a project feature off another module's frozen vocabulary.**

### 4.3 The two options, weighed against L36/L31

> **L36/L31 rule (restated):** *ships-first owns the table; a later sub-module EXTENDS by FK, never re-declares a
> parallel schema* — but "extends" only holds where the shipped table can actually **carry** the new domain. Where
> its vocabulary and scope cannot express the new entities, the precedent (`crm.WebhookDelivery` vs
> `scm.WebhookDelivery`; `crm.PurchaseOrder` vs `scm.PurchaseOrder`; three `PRJ-` "projects") is that a
> **same-named, differently-scoped table may coexist on purpose** — provided the divergence is written down.

**(a) `projects.ProjectIntegrationConnector` FKs `scm.IntegrationEndpoint` (extend-by-FK).** Costs, all verified:
1. **Vocabulary wall.** `ENDPOINT_SYSTEM_CHOICES` (§4.1b) has no Jira/GitHub/GitLab/Azure DevOps/Salesforce/
   HubSpot/BambooHR/ADP/SharePoint/Drive/Dropbox/Box member, and `ENDPOINT_CATEGORY_CHOICES` has no
   crm/hris/devops/storage discriminator. 13 of the 16 systems §7.18 names **cannot be represented**; a Jira row
   would have to masquerade as `custom`, so **five NavERP.md bullets would collapse into one indistinguishable
   "Custom" bucket** and the five live sidebar leaves would land on the same rows.
2. **Widening 4.19's pinned choices is off the table.** `_choices.py` is documented as **one writer, three
   readers**, its values are pinned by 4.19's frozen contract and its shipped tests, and its transport/interchange
   columns exist only there. Editing a shipped sub-module's vocabulary to bolt on another module's feature is
   exactly what L36 forbids in the opposite direction.
3. **No project scope, and no per-project naming.** The register is tenant-global: no `project` FK, and
   `unique_together = (("tenant","number"),("tenant","name"))` makes a connector **name unique per tenant** — so
   "Salesforce — Acme account" and "Salesforce — Beta account" cannot both exist, and no project connector can
   exist until an SCM-owned row exists first.
4. **Wrong credential mechanics, by 4.19's own doctrine.** 4.19 stores a one-way prefix+SHA-256 **marker** because
   it ships no transport and never authenticates; its own docstring calls hashing the **MIGRATION HAZARD** for any
   later transport pass. 7.18's whole subject **is** the credential that would be presented to SAP/Jira, so it
   needs the reversible store — and 4.19 explicitly says that cannot be bolted on by hashing again.
5. **App-import rule.** `apps/projects/models/_base.py:8-9` and `research-inventory-5.19.md:127-129` both state
   peer apps do **not** import each other's internals; every existing cross-app link is a **string label** into a
   *shared spine* model (`core.Party`, `accounting.GLAccount`, `crm.Opportunity`, `hrm.EmployeeProfile`) — never
   into another app's *feature* register.
6. **Reviewer/test blast radius.** 4.19's `scm` tests and contract pin `ENDPOINT_*` values and column names;
   touching them turns a 7.18 run into a two-app changeset, which the Phase-4 reviewers would (correctly) flag.

**Could (a) still be made viable?** Only by rewriting 4.19 — adding a `category` member per bullet, ~14 `system`
values, a nullable `project` FK and a reversible credential column, and relaxing `(tenant, name)`. That is a
**shipped-sub-module migration plus a contract/test rewrite**: strictly more work and more risk than (b), and it
puts a project register behind an SCM gate. **Not viable → recommend (b).**

### 4.4 RULING — (b): 7.18 ships its own project-scoped connector register

**`projects` 7.18 owns `ProjectIntegrationConnector` [`IXC-`], project-scoped (nullable `Project` FK; null =
workspace-wide), with a provider vocabulary covering all five bullets, a reversible (Fernet) credential, and its
own hub scope. It does not FK, extend or re-declare `scm.IntegrationEndpoint`, `inventory.IntegrationChannel`,
`accounting.IntegrationConfig`, or any webhook/delivery table.**

**Where the boundary is written (L36's "documented decision, not drift") — three durable places:**
1. **Model docstring** — in `apps/projects/models/IntegrationApiHub/Connectors.py`: *scm 4.19
   `IntegrationEndpoint` = the supply-chain, transport-less register (EDI/IoT/3PL, `CNX-`); inventory 5.19
   `IntegrationChannel` = the commerce-stock register (`INT-`); accounting 2.15 `IntegrationConfig` = the
   finance-side register; **this** model = the PROJECT connector register (`IXC-`) — four registers, four
   questions, deliberately not merged*, plus the sentence *"7.18 performs no outbound HTTP and writes no
   accounting row."* (Mirrors `ChannelListingMaps.py:3-11`, `IntegrationEndpoints.py:12-27`.)
2. **`apps/core/navigation.py` comment** at the new `"7.18"` `LIVE_LINKS` entry (**main session** writes it, not
   the build agent): the five domain leaves are five category-scoped routes onto `ProjectIntegrationConnector`,
   the register is project-scoped, and 4.19/5.19/2.15 own the neighbouring registers. Precedent: the omission
   comments at `navigation.py:2044-2059`.
3. **`.claude/tasks/lessons.md`** entry (**main session** writes it): this ruling + the do-not-reuse list below,
   so a future pass does not "consolidate" the registers.

**Names and columns that must NOT be reused (so a maintainer sees the split is deliberate):**
- **Class names owned elsewhere:** `IntegrationEndpoint`, `IntegrationMessage`, `WebhookSubscription`,
  `WebhookDelivery` (scm 4.19); `Webhook`, `WebhookDelivery` (crm 1.10); `IntegrationConfig` (accounting 2.15);
  `IntegrationChannel`, `ChannelListingMap`, `StockSyncRun`, `ApiClient` (inventory 5.19);
  `ProjectWebhookEndpoint`, `ProjectWebhookDelivery` (7.17).
- **4.19 columns/constants not to copy:** `interchange_id`, `interchange_qualifier`, `device_identifier`,
  `endpoint_url`, `credential_prefix`, `credential_hash`, `hash_secret`/`generate_credential`, `masked`,
  `transport`, `lifecycle_stage`, and every `ENDPOINT_*` constant name. 7.18 uses **`domain`** (not `category`),
  **`provider`** (not `system`), **`base_url`**, and **`credential`** with
  `set_credential`/`get_credential`/`credential_masked` — so a grep for `ENDPOINT_|category|system` never lands
  in both files.
- **Prefixes not to reuse:** CNX, MSG, WHK, INT, SYN, API, WH, plus 7.17's PWH/PWF/PAR/RTS. 7.18 takes **IXC, SYJ,
  SYR** (verified free repo-wide, §1.3).

### 4.5 The 7.17 boundary (push vs sync) and the "notify on sync failure" FK

- **Split:** **7.17 owns event PUSH** — outbound endpoints, HMAC-SHA256 signing, test-ping verbs and the
  `ProjectWebhookDelivery` log. **7.18 owns scheduled/triggered DATA SYNC** — the connector registry, the field
  mappings, the sync jobs and the `ProjectSyncRun` log. Two logs for two different facts (an *event delivery* vs
  a *batch sync run*), exactly as `scm.WebhookDelivery` (per-attempt telemetry, unnumbered) sits beside
  `inventory.StockSyncRun` (per-batch, numbered).
- **Where they touch, 7.18 references by FK only:** `ProjectIntegrationConnector.notify_webhook = ForeignKey(
  "projects.ProjectWebhookEndpoint", on_delete=SET_NULL, null=True, blank=True, related_name="notify_connectors")`.
  7.18 declares **no** `target_url`, **no** `secret`, **no** `event_types`, **no** delivery row and no signing
  helper; it asks 7.17 to deliver the alert and never delivers it itself.
- **May `ProjectWebhookEndpoint` be FK'd for "notify on sync failure"? YES — read, not assumed.**
  `Webhooks.py:20-27` shows `project` is a **nullable** FK (`null=True, blank=True`, "Null implies tenant-wide
  webhook"), so an endpoint may be project-scoped or workspace-wide; the row is tenant-scoped (`TenantNumbered`),
  `is_active` exists for a soft enable/disable, and the index `pwh_tnt_prj_act_idx (tenant, project, is_active)`
  already serves "which endpoints should be notified about this connector's failures".
  `on_delete=SET_NULL` is the right 7.18-side choice: deleting a webhook must not delete an integration connector,
  and the form simply renders "Not set". **No change to 7.17 is required to point at it.**

### 4.6 Credential store ruling for 7.18 — **`apps/core/crypto.py` (Fernet), not prefix+hash**

`ProjectIntegrationConnector.credential = models.CharField(max_length=512, blank=True)` stores a **`fernet.v1:`
cipher**; `get_credential()` decrypts (strict, raises `ImproperlyConfigured` on a rotated key),
`credential_masked` degrades to `"(set — undecryptable with the current key)"` exactly like
`crm.Webhook.secret_masked`, and `set_credential()` / the rotate verb is the one writer. Reasons, in weight order:
1. **7.17 set this precedent in this app, in this sub-module family.** `ProjectWebhookEndpoint.secret` is Fernet
   (`CharField(512)` via `apps.core.crypto`), and 7.18's connector rows sit on the same hub pages. Two credential
   mechanics inside one sub-module family would be a maintenance trap and an immediate reviewer finding.
2. **A hash marker is a one-way trap for the *next* pass.** 4.19's own docstring flags the MIGRATION HAZARD: a
   digest can never become a usable credential again, so a transport pass would have to **re-issue every
   credential in every tenant**. A Fernet cipher is re-keyable and usable the day transport lands.
3. **7.18's stated ownership is authenticated sync** — the connector is the row that *would* present a credential
   to SAP/Jira; `apps/core/crypto.py`'s docstring names this exact case ("a key you must USE").
4. **Honest counter-argument, recorded for the contract phase:** while 7.18 ships no outbound HTTP, today's only
   consumers are display (`credential_masked`), rotation, and the simulated test/run verbs — for a marker-only
   register, 4.19's prefix+hash would be strictly safer. The ruling still lands on Fernet because the field's
   purpose is a credential that must stay usable, and forcing a future re-issue of every tenant's tokens is the
   more expensive mistake. **If the build decides otherwise it must take prefix+hash AND say in the docstring that
   7.18 authenticates to nothing — and then it may not claim "sync" anywhere.**
5. **No OAuth token columns.** `auth_method` includes `oauth2` purely as **recorded intent** (4.19's ruling);
   7.18 stores a pasted API key / PAT / service token, never a refresh token, and ships no token-refresh code.

### 4.7 L29 / multi-tenancy statements this pass must carry
- 7.18 **writes no `accounting` row** (no journal, no invoice, no payment) — it registers connectors *toward*
  ERP/finance packages; the ledger stays accounting's (mirrors `research-inventory-5.19.md` §4.3).
- 7.18 **mirrors no document bytes** — `ProjectDocument`/`ProjectFolder` stay 7.10's and `MEDIA_ROOT`
  (`projects/documents/`, `projects/templates/`) is untouched.
- 7.18 **declares no second person/party** — `core.Party`/`PartyRole` and `hrm.EmployeeProfile` are reached
  through the built `ResourceProfile`.
- Every model is `TenantOwned`/`TenantNumbered`; every view filters `tenant=request.tenant`; every tenant-scoped
  FK dropdown is re-checked with `_reject_foreign`.

## 5. Recommended build scope (this pass — 4 models + the mapping child)

**Compression decision (same as 4.19's `category`, 5.19's `kind`, 2.15's `CATEGORY_CHOICES`):** the five NavERP.md
bullets are **one connector table discriminated by `domain`** (`erp·crm·hris·devops·storage·custom`), reached by
**five category-scoped route names** that all resolve to the same view through Django's extra-options dict. Five
near-identical tables would be five copies of the same credential/status/scope columns, and the copy that goes
stale is the one nobody edits.

| # | Model | Base | Prefix | CRUD posture |
|---|---|---|---|---|
| 1 | `ProjectIntegrationConnector` | `TenantNumbered` | **`IXC-`** | full CRUD + rotate-credential + test + toggle |
| 2 | `ConnectorFieldMapping` | `TenantOwned` | none (plumbing; `ChannelListingMap` precedent) | full CRUD |
| 3 | `ProjectSyncJob` | `TenantNumbered` | **`SYJ-`** | full CRUD + run + toggle |
| 4 | `ProjectSyncRun` | `TenantNumbered` | **`SYR-`** | **append-only**: list + detail + `syr_retry` POST, **no form** |

### 5.0 Files, layout and migration (conventions pinned)

- **Backend packages:** `apps/projects/models/IntegrationApiHub/{Connectors.py, FieldMappings.py, SyncJobs.py,
  SyncRuns.py}` and `apps/projects/{forms,views,urls}/IntegrationApiHub/<same four names>.py`, plus
  `urls/IntegrationApiHub/HubBoards.py` (the three lens pages) — one folder per sub-module, one file per entity,
  absolute imports (`from apps.projects.models.IntegrationApiHub.Connectors import …`), each entity module doing
  `from apps.projects.models._base import *`.
- **Sub-package `__init__.py` files stay empty of re-exports** — 7.17's convention verbatim
  (`models/WorkflowAutomation/__init__.py`: *"Intentionally EMPTY of re-exports by convention: the package's
  public surface is the top-level `apps/projects/models/__init__.py` re-export block."*).
- **The top-level `apps/projects/models/__init__.py` gains the 7.18 block after line 174** (end of 7.17's block):
  `# --- 7.18 Integration & API Hub ---` + `from .IntegrationApiHub.Connectors import ProjectIntegrationConnector`,
  `.FieldMappings import ConnectorFieldMapping`, `.SyncJobs import ProjectSyncJob`,
  `.SyncRuns import ProjectSyncRun`. **Also required:** the 7.18 re-exports in `apps/projects/forms/__init__.py`
  and `apps/projects/views/__init__.py`, and in `apps/projects/urls/__init__.py` the five
  `from .IntegrationApiHub.X import urlpatterns as _ih_x` imports added to the concatenation list.
- **Templates:** render strings **lowercase** `"projects/integrationapihub/<entity>/<page>.html"` — mirroring
  7.17 exactly (`templates/projects/WorkflowAutomation/webhook/list.html` rendered as
  `"projects/workflowautomation/webhook/list.html"`, `views/WorkflowAutomation/Webhooks.py:59`). **Create the disk
  folders in that same lowercase spelling** (`templates/projects/integrationapihub/<entity>/…`) so the render path
  and the file path agree on any filesystem — see Risks §6.1 for why that small deviation from 7.17's disk casing
  is the safer choice. Entity folders: `connector/`, `mapping/`, `syncjob/`, `syncrun/`, plus `boards/` for the
  lens pages.
- **Migration:** `apps/projects/migrations/0026_…` (disk ends at `0025_…`). Re-check the directory immediately
  before `makemigrations` and take the next free number if a sibling session has taken 0026 (L43);
  `makemigrations --check` must then say "No changes detected".
- **Money:** none of these models holds money, so `DecimalField(14, 2)` appears **nowhere** in 7.18 (the only
  numeric columns are counters and a duration). State it in the contract so nobody invents a cost column.

### 5.1 `ProjectIntegrationConnector` [`IXC-`] — `TenantNumbered`, full CRUD

**Purpose:** one row per registered connection to one outside system; satisfies all five bullets through
`domain`.

| Field | Type / choices | Notes |
|---|---|---|
| `number` | base (`CharField(20)`, `editable=False`) | `IXC-00001` … |
| `tenant` | base FK `core.Tenant` | |
| `project` | FK `"projects.Project"`, **nullable**, `CASCADE`, `related_name="integration_connectors"` | null ⇒ workspace-wide (mirrors `ProjectWebhookEndpoint.project`) |
| `name` | `CharField(120)` | unique per `(tenant, project)` |
| `domain` | `CharField(12)`, `DOMAIN_CHOICES` = `erp`·`crm`·`hris`·`devops`·`storage`·`custom`, default `custom` | **the 5-bullet discriminator** |
| `provider` | `CharField(20)`, `PROVIDER_CHOICES` = `sap`·`oracle`·`netsuite`·`dynamics`·`workday`·`salesforce`·`hubspot`·`dynamics_sales`·`bamboohr`·`adp`·`jira`·`github`·`gitlab`·`azure_devops`·`ci_cd`·`sharepoint`·`google_drive`·`dropbox`·`box`·`custom`, blank, default `custom` | covers **every** system named in §7.18 |
| `direction` | `CharField(14)`, `inbound`·`outbound`·`bidirectional` (default `bidirectional`) | |
| `auth_method` | `CharField(10)`, `none`·`api_key`·`basic`·`oauth2`·`pat` (default `api_key`) | `oauth2` = recorded intent only |
| `base_url` | `CharField(500, blank=True)` **with a `# WARNING: SSRF` comment** | CharField, **not** URLField (git/ssh/on-prem hosts are not http) |
| `remote_scope_ref` | `CharField(200, blank=True)` | Jira project key, `org/repo`, SharePoint site/library id, SAP company code, NetSuite subsidiary, Salesforce org id |
| `trigger_mode` | `CharField(10)`, `manual`·`scheduled`·`event` (default `manual`) | records intent; **nothing polls** |
| `schedule_note` | `CharField(200, blank=True)` | documentation, not a cron |
| `environment` | `CharField(10)`, `production`·`sandbox` (default `sandbox`) | |
| `status` | `CharField(12)`, `unverified`·`connected`·`error`·`disabled`·`disconnected` (default `unverified`) | human-maintained marker |
| `is_active` | `BooleanField(default=True)` | |
| `credential` | `CharField(512, blank=True)` | **Fernet ciphertext** (§4.6); write-only form field; never rendered |
| `last_sync_at`, `last_success_at` | `DateTimeField(null=True, blank=True, editable=False)` | |
| `consecutive_failures` | `PositiveIntegerField(default=0, editable=False)` | |
| `notify_webhook` | FK `"projects.ProjectWebhookEndpoint"`, `SET_NULL`, null/blank, `related_name="notify_connectors"` | **7.17 owns delivery** (§4.5) |
| `owner` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, null/blank, `related_name="owned_project_connectors"` | |
| `notes` | `TextField(blank=True)` | |

**Methods/properties:** `set_credential(raw)`, `get_credential()`, `credential_masked` (degrades, never raises),
`credential_set` (bool), `status_badge`, `domain_badge`, `health_badge` — **colour-named badges only**
(`badge-green/red/amber/info/muted/slate`, L33). `save()` performs
`self.credential = encrypt(self.credential or "")` as the single choke point (idempotent on a marked value) —
`crm.Webhook.save()`'s exact pattern; `pwh_create`-style views may call `set_credential()` first.
**Meta:** `ordering = ["-created_at", "-id"]`; `unique_together = [("tenant", "number"),
("tenant", "project", "name")]`; `indexes` = `ixc_tnt_domain_idx (tenant, domain)`, `ixc_tnt_status_idx
(tenant, status)`, `ixc_tnt_prj_idx (tenant, project)`, `ixc_tnt_active_idx (tenant, is_active)` — all ≤30 chars.
`__str__` = `f"{self.number} — {self.name} ({self.get_provider_display()})"`.

### 5.2 `ConnectorFieldMapping` — `TenantOwned`, **unnumbered**, full CRUD

**Purpose:** the field-to-field map (Workato/Unito/Fusion mapping UI; 5.19 `ChannelListingMap` shape).
`TENANT_SCOPED_FKS = ("connector",)`.

| Field | Type / choices |
|---|---|
| `connector` | FK `ProjectIntegrationConnector`, `CASCADE`, `related_name="mappings"` |
| `local_field` | `CharField(100)` — e.g. `task.status`, `client.name`, `document.title`, `time_entry.hours` |
| `remote_field` | `CharField(100)` — e.g. `fields.status.name`, `Account.Name`, `path`, `timeSpentSeconds` |
| `direction` | `CharField(14)`, `to_remote`·`from_remote`·`both` (default `both`) |
| `transform` | `CharField(12)`, `none`·`upper`·`lower`·`trim`·`date_iso`·`number`·`bool` (default `none`) |
| `value_map` | `JSONField(default=dict, blank=True)` — local value ⇒ remote value (or the reverse per `direction`) |
| `default_value` | `CharField(255, blank=True)` |
| `is_key` | `BooleanField(default=False)` — the match/identity key (de-dupe + idempotency) |
| `is_required` | `BooleanField(default=False)` |
| `notes` | `CharField(255, blank=True)` |

**Meta:** `ordering = ["connector__name", "local_field", "id"]` (or `["local_field", "id"]` with the connector
filtered); `unique_together = [("tenant", "connector", "local_field", "direction")]`;
`indexes` = `ixm_tnt_conn_idx (tenant, connector)`, `ixm_tnt_conn_key_idx (tenant, connector, is_key)`.
`clean()` repeats the tenant guard for `connector` (the form repeats it at the boundary with `_reject_foreign`).
`__str__` = `f"{self.local_field} → {self.remote_field}"`.

### 5.3 `ProjectSyncJob` [`SYJ-`] — `TenantNumbered`, full CRUD

**Purpose:** the scoped, repeatable unit of transfer (Workato *recipe* / Fusion *scenario* / Celigo *flow*).
`TENANT_SCOPED_FKS = ("connector",)`.

| Field | Type / choices | Notes |
|---|---|---|
| `number` | base | `SYJ-00001` … |
| `tenant` | base | |
| `connector` | FK `ProjectIntegrationConnector`, `CASCADE`, `related_name="jobs"` | the job's project scope is read **through** the connector — **no second `project` column** (one source of truth) |
| `name` | `CharField(255)` | |
| `entity_scope` | `CharField(16)`, `SYNC_ENTITY_CHOICES` = `tasks`·`issues`·`risks`·`milestones`·`time_entries`·`resources`·`documents`·`folders`·`budgets`·`cost_lines`·`journals`·`custom` (default `custom`) | the "what moves" vocabulary (bullets 2–5) |
| `direction` | `CharField(14)`, `inbound`·`outbound`·`bidirectional` | may differ from the connector's |
| `trigger_mode` | `CharField(10)`, `manual`·`scheduled`·`event` | intent only |
| `interval_minutes` | `PositiveIntegerField(null=True, blank=True)` | recorded cadence; **nothing schedules on it** |
| `schedule_note` | `CharField(200, blank=True)` | |
| `filter_expression` | `TextField(blank=True)` | e.g. JQL or a status filter — **recorded, never evaluated** (4.19's `filter_expression` precedent) |
| `conflict_policy` | `CharField(12)`, `local_wins`·`remote_wins`·`newest_wins`·`manual` (default `manual`) | two-way conflict rule |
| `batch_size` | `PositiveIntegerField(default=100)` | |
| `is_active` | `BooleanField(default=True)` | |
| `last_run_at` / `next_run_at` | `DateTimeField(null=True, blank=True, editable=False)` | `next_run_at` is a **stamp**, not a trigger |
| `run_count` | `PositiveIntegerField(default=0, editable=False)` | |
| `last_status` | `CharField(10, blank=True, editable=False)` | mirrors the newest run's status for the list column |

**Meta:** `ordering = ["-created_at", "-id"]`; `unique_together = [("tenant", "number"), ("tenant", "connector",
"name")]`; `indexes` = `syj_tnt_conn_idx (tenant, connector)`, `syj_tnt_conn_act_idx (tenant, connector,
is_active)`, `syj_tnt_status_idx (tenant, last_status)`. `__str__` = `f"{self.number} — {self.name}"`.

### 5.4 `ProjectSyncRun` [`SYR-`] — `TenantNumbered`, **append-only** (list + detail + `syr_retry` only)

**Purpose:** what each sync batch actually did — the register a PMO argues about ("last night's Jira push",
"chase SYR-00042"). Numbered for that reason, mirroring `inventory.StockSyncRun`'s explicit ruling; per-attempt
telemetry stays unnumbered on the 7.17 side.
**No `ProjectSyncRunForm` exists** — the forms sub-package `__init__` carries the deliberate-absence comment, the
`IntegrationMessages.py:26-30` / `StockSyncRuns.py` posture. The only writer is `record()` (the run verb, the
retry verb and the seeder all go through it).

| Field | Type / choices | Notes |
|---|---|---|
| `number` | base | `SYR-00001` … |
| `tenant` | base | |
| `job` | FK `ProjectSyncJob`, `CASCADE`, `related_name="runs"` | `TENANT_SCOPED_FKS = ("job",)` |
| `direction` | `CharField(14)`, `inbound`·`outbound`·`bidirectional` | snapshot of the job's at run time |
| `status` | `CharField(10)`, `RUN_STATUS_CHOICES` = `pending`·`running`·`success`·`partial`·`failed`·`skipped`·`simulated` (default `pending`) | **`simulated` is mandatory honesty** — nothing in this build leaves the process |
| `trigger_source` | `CharField(10)`, `manual`·`schedule`·`event` (default `manual`) | |
| `triggered_by` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, null/blank, `editable=False`, `related_name="+"` | |
| `records_read` / `records_created` / `records_updated` / `records_skipped` / `records_failed` | `PositiveIntegerField(default=0)` | **counts, never one row per record** |
| `error_code` | `CharField(50, blank=True)` | |
| `error_message` | `TextField(blank=True)` | |
| `payload_excerpt` | `TextField(blank=True)` | **truncated** — may contain partner PII |
| `attempt_no` | `PositiveSmallIntegerField(default=1)` | |
| `next_retry_at` | `DateTimeField(null=True, blank=True)` | a **stamp**; nothing wakes up and reads it |
| `started_at` | `DateTimeField(default=timezone.now, editable=False)` | |
| `finished_at` | `DateTimeField(null=True, blank=True, editable=False)` | |
| `duration_ms` | `PositiveIntegerField(default=0, editable=False)` | |

**Meta:** `ordering = ["-started_at", "-id"]`; `unique_together = [("tenant", "number")]`;
`indexes` = `syr_tnt_job_stat_idx (tenant, job, status)`, `syr_tnt_stat_strt_idx (tenant, status, started_at)`,
`syr_tnt_job_strt_idx (tenant, job, started_at)`. `__str__` = `f"{self.number} — {self.get_status_display()} @
{self.started_at:%Y-%m-%d %H:%M}"`. `status_badge`: success→`badge-green`, partial→`badge-amber`,
failed→`badge-red`, simulated→`badge-info`, pending/running→`badge-slate`, skipped→`badge-muted`.
**Retry semantics:** `syr_retry` is `@require_POST` + `@tenant_admin_required`, sets `status="pending"`,
`attempt_no += 1`, stamps `next_retry_at` from the published backoff tuple
`SYNC_BACKOFF_SECONDS = (0, 5, 300, 1800, 7200, 18000, 36000, 36000)` (Svix's 8 slots, adopted verbatim exactly
as `scm` 4.19's `DELIVERY_BACKOFF_SECONDS` and `inventory` 5.19's `SYNC_BACKOFF_SECONDS`), and **performs no
HTTP request** — the docstring must say so.

### 5.5 Forms (`apps/projects/forms/IntegrationApiHub/`) — exact `Meta.fields`

1. **`ProjectIntegrationConnectorForm(TenantUniqueMixin, TenantModelForm)`**
   `Meta.fields = ["project", "name", "domain", "provider", "direction", "auth_method", "base_url",
   "remote_scope_ref", "trigger_mode", "schedule_note", "environment", "status", "is_active", "notify_webhook",
   "owner", "notes"]` — **excluded by construction:** `number`, `credential`, `last_sync_at`, `last_success_at`,
   `consecutive_failures`. Declared **extra** field
   `credential = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False,
   attrs={"class": "form-input"}), help_text="Paste the provider token/API key. Stored encrypted; leave blank on
   edit to keep the current one.")`; `clean()` calls `_reject_foreign(self, cleaned, ["project",
   "notify_webhook"])` — **not `owner`** (a superuser row may have `tenant=None`; the view scopes the owner
   queryset instead), matching 7.17's restraint. A blank `credential` on edit must leave the stored cipher alone
   (`encrypt()` is idempotent, so re-assigning the stored value is safe).
2. **`ConnectorFieldMappingForm(TenantUniqueMixin, TenantModelForm)`**
   `Meta.fields = ["connector", "local_field", "remote_field", "direction", "transform", "value_map",
   "default_value", "is_key", "is_required", "notes"]`; `clean()` → `_reject_foreign(self, cleaned, ["connector"])`;
   `clean_value_map` parses JSON text into a dict (7.17's `clean_custom_headers` pattern).
3. **`ProjectSyncJobForm(TenantUniqueMixin, TenantModelForm)`**
   `Meta.fields = ["connector", "name", "entity_scope", "direction", "trigger_mode", "interval_minutes",
   "schedule_note", "filter_expression", "conflict_policy", "batch_size", "is_active"]`; excluded:
   `number`, `last_run_at`, `next_run_at`, `run_count`, `last_status`; `clean()` →
   `_reject_foreign(self, cleaned, ["connector"])`.
4. **No `ProjectSyncRunForm`** — deliberately absent (the sub-package `__init__` says why).

### 5.6 URLs + view context keys (the contract phase must pin every one of these)

**`apps/projects/urls/IntegrationApiHub/`** — first segment literal `integration/` (verified free, §1.4);
literals before `<int:pk>`; **no greedy `<str:…>` converter anywhere**.

`Connectors.py`:
```
integration/connectors/                            ixc_list
integration/connectors/add/                        ixc_create
integration/connectors/erp/                        ixc_erp_list      (same view, {"domain": "erp"})
integration/connectors/crm/                        ixc_crm_list      ({"domain": "crm"})
integration/connectors/hris/                       ixc_hris_list     ({"domain": "hris"})
integration/connectors/devops/                     ixc_devops_list   ({"domain": "devops"})
integration/connectors/storage/                    ixc_storage_list  ({"domain": "storage"})
integration/connectors/<int:pk>/                   ixc_detail
integration/connectors/<int:pk>/edit/              ixc_edit
integration/connectors/<int:pk>/delete/            ixc_delete        @require_POST + @tenant_admin_required
integration/connectors/<int:pk>/rotate-credential/ ixc_rotate_credential  @require_POST + admin
integration/connectors/<int:pk>/test/              ixc_test          @require_POST (writes a simulated SYR row)
integration/connectors/<int:pk>/toggle/            ixc_toggle_active @require_POST
integration/connectors/<int:pk>/health/            connector_health  (GET lens page)
```
`FieldMappings.py`: `integration/mappings/` `ixm_list` · `/add/` `ixm_create` · `/<int:pk>/` `ixm_detail` ·
`/<int:pk>/edit/` `ixm_edit` · `/<int:pk>/delete/` `ixm_delete`.
`SyncJobs.py`: `integration/sync-jobs/` `syj_list` · `/add/` `syj_create` · `/<int:pk>/` `syj_detail` ·
`/<int:pk>/edit/` `syj_edit` · `/<int:pk>/delete/` `syj_delete` · `/<int:pk>/run/` `syj_run` (@require_POST) ·
`/<int:pk>/toggle/` `syj_toggle_active`.
`SyncRuns.py`: `integration/runs/` `syr_list` · `integration/runs/<int:pk>/` `syr_detail` ·
`integration/runs/<int:pk>/retry/` `syr_retry` (@require_POST) — **no create/edit/delete**.
`HubBoards.py`: `integration/hub/` `integration_hub` · `integration/monitor/` `sync_monitor`.

**View context keys (pin these; a mismatched key renders 200 and blank — L8):**
- `ixc_list` / the five category routes: `connectors` (= `page_obj.object_list`), `page_obj`, `projects`,
  `domain_choices` (**all** `DOMAIN_CHOICES`), `provider_choices` (all `PROVIDER_CHOICES`), `status_choices`,
  `domain` (echoed from the view kwarg), `q`, `status`, `provider`, `project_id`, `is_active`, and
  `stats` = `{total, active, connected, error, unverified, due_rotation}`.
  *Filters: string fields compare with `{% if request.GET.status == value %}selected{% endif %}`; FK/pk fields
  with `|stringformat:"d"`. `domain` is a **view kwarg**, so the template echoes `domain` — never
  `request.GET.domain`.*
- `ixc_detail`: `connector`, `mappings` (first 20), `jobs`, `recent_runs` (15), `test_form`
  (`ConnectorTestForm`, a plain `forms.Form`), `revealed_credential` (session-once, session key
  `_ixc_cred_reveal` — 7.17's `_whk_secret_reveal` pattern).
- `ixc_create` / `ixc_edit`: `form`; on edit also `connector`.
- `ixm_list`: `mappings`, `page_obj`, `connectors`, `connector_id`, `direction_choices`, `transform_choices`, `q`.
- `ixm_detail`: `mapping`; `ixm_create`/`ixm_edit`: `form` (+ `mapping` on edit).
- `syj_list`: `jobs`, `page_obj`, `connectors`, `entity_choices`, `trigger_choices`, `conflict_choices`,
  `status_choices`, `q`, `connector_id`, `entity_scope`, `is_active`, `stats` = `{total, active, due, failing}`.
- `syj_detail`: `job`, `runs` (15), `stats` = `{run_count, success_rate, last_status, mapping_count}`.
- `syr_list`: `runs`, `page_obj`, `jobs`, `connectors`, `status_choices`, `trigger_choices`, `job_id`,
  `connector_id`, `status`, `trigger_source`, `date_from`, `date_to`, `q`,
  `stats` = `{pending, running, failed, partial, simulated, failed_today}`; widen `date_from/date_to` into a
  **datetime range** (as `scm.IntegrationMessage`'s list does) so the `(tenant, started_at)` index is usable.
- `syr_detail`: `run`.
- `integration_hub`: `stats` = `{connectors_total, by_domain, by_status, runs_today, failed_today, jobs_active,
  mappings_total, credentials_due}`, `domains` (list of dicts `value/label/total/connected/failing`),
  `connectors` (health rows), `recent_runs`, `projects`.
- `sync_monitor`: `runs`, `page_obj`, `jobs`, `connectors`, `status_choices`, `stats`, `q`, `status`, `job_id`,
  `date_from`, `date_to`.
- `connector_health`: `connector`, `runs` (last 20), `mappings`, `jobs`,
  `stats` = `{success_rate, avg_duration_ms, failures_7d, last_success_at, mappings_count, credential_set}`.

### 5.7 Templates + the extra board/lens pages the five bullets need

Entity pages (9 files for three CRUD triples + 2 for the append-only log) — disk folders lowercase, render strings
identical:
- `templates/projects/integrationapihub/connector/{list,detail,form}.html`
- `templates/projects/integrationapihub/mapping/{list,detail,form}.html`
- `templates/projects/integrationapihub/syncjob/{list,detail,form}.html`
- `templates/projects/integrationapihub/syncrun/{list,detail}.html` (no form — append-only)

Lens/board pages (`templates/projects/integrationapihub/boards/`), mirroring 7.17's `boards/` folder:
- **`hub.html` → `integration_hub`** — the sub-module cockpit: connector counts per domain and status (one card
  per NavERP.md bullet, each linking to its category route), runs today, failures today, credentials due for
  rotation, and the "quick actions" row (register a connector, add a mapping, open the monitor). Precedent:
  7.17 `boards/overview.html`, 4.19's exceptions cockpit.
- **`monitor.html` → `sync_monitor`** — the run queue cockpit: filterable run table (status/connector/job/date),
  the pending + failed header chips, last-success per connector, and the retry queue with its `next_retry_at`
  stamps. Precedent: 7.17 `boards/webhook_diagnostics.html`.
- **`connector_health.html` → `connector_health`** — one connector's diagnostics: success rate, average duration,
  failures in 7 days, mapping coverage, last error, credential state, and deep links to its jobs, mappings and
  runs (`syr_list?job=<pk>` / `ixm_list?connector=<pk>`).

**Filter/dropdown completeness (the app's recurring bug — rules §"Filter Implementation Rules"):** every list
view passes the `*_choices` constant **and** the parent querysets it filters by, and every template compares
string choices directly and pk filters through `|stringformat:"d"`.

### 5.8 `LIVE_LINKS["7.18"]` proposal (keys character-for-character from NavERP.md §7.18)

```python
"7.18": {
    "ERP & Financial System Sync":       "projects:ixc_erp_list",
    "CRM Integration":                   "projects:ixc_crm_list",
    "HR & Talent Systems":               "projects:ixc_hris_list",
    "Development & DevOps Tools":        "projects:ixc_devops_list",
    "File Storage & Collaboration":      "projects:ixc_storage_list",
    # Extra live leaves:
    "Integration Hub":                   "projects:integration_hub",
    "Connector Register":                "projects:ixc_list",
    "Field Mappings":                    "projects:ixm_list",
    "Sync Jobs":                         "projects:syj_list",
    "Sync Run Log":                      "projects:syr_list",
    "Sync Monitor":                      "projects:sync_monitor",
    "Connector Health":                  "projects:connector_health",
}
```
The five bullet keys are copied from `NavERP.md:1282-1286` verbatim (`Sidebar` parses that file — a key that does
not match to the character renders as *not built*). 7.17's entry (`navigation.py:2024-2040`) is the shape to
mirror, including its `# Extra live leaves:` comment; the ownership comment from §4.4 goes immediately above this
entry. **`ConnectorFieldMapping` and `ProjectSyncRun` get no bullet key of their own** except the register leaves
above — the same ruling `navigation.py:2052-2059` records for scm's logs (a sidebar entry per log lists plumbing,
not features).

### 5.9 Seeder + admin (exact expectations for the later phases)

**Helper:** `_integration_hub(self, tenant, now)` in `seed_projects.py`, called from `_seed_tenant` **after**
`self._workflow_automation(tenant, now)`; guard `if ProjectIntegrationConnector.objects.filter(tenant=tenant).exists():
print "… 7.18 integration hub already seeded. Skipping."; return`.

**What it must create (enough for page 2, every choice value, and both tenants):**
- **7 connectors** — one per `domain` value (erp, crm, hris, devops, storage, custom) **plus one extra**, spanning
  **every `status`** (`unverified`, `connected`, `error`, `disabled`, `disconnected`), at least one with
  `project=None` (workspace-wide) and the rest split across the two seeded projects; **one with
  `notify_webhook=` the 7.17 seeder's first `PWH` row**, one `environment="production"`, one `trigger_mode="event"`;
  `remote_scope_ref` values that read like the real thing (`NAVERP`, `acme-co/platform`, `Salesforce org 00D…`).
- **30 mappings** (page 2 of `ixm_list` needs >25) across at least 5 connectors: at least one `is_key=True` per
  connector, a `value_map` on the Jira and Salesforce rows (`{"done": "completed"}`, `{"Closed Won": "active"}`),
  a `to_remote`/`from_remote`/`both` trio, and one `transform="date_iso"`.
- **9 jobs** spanning every `entity_scope` family used by the five bullets (`resources`, `time_entries`, `tasks`,
  `issues`, `documents`, `folders`, `cost_lines`, `journals`, `custom`), all four `conflict_policy` values,
  `is_active` true/false, one `trigger_mode="scheduled"` with `interval_minutes=60`.
- **45 runs** (page 2 needs >25; the monitor needs heat) spanning **every** `RUN_STATUS`
  (`pending`, `running`, `success`, `partial`, `failed`, `skipped`, `simulated`), every `trigger_source`, spread
  over ~10 days with `records_read/created/updated/failed` populated, at least one failure per connector, one long
  `error_message` to exercise truncation, and one `next_retry_at` stamp. **Create runs through the model's
  `record()` classmethod**, never bare `.create()` (the `StockSyncRun.record()` precedent), and set
  `duration_ms`, `attempt_no`, `payload_excerpt` (truncated).
- Print a per-tenant summary line (connectors / mappings / jobs / runs) like 7.17's.

**`--flush` additions (children first, inserted ABOVE 7.17's webhook deletes):**
`ProjectSyncRun.objects.all().delete()` → `ProjectSyncJob.objects.all().delete()` →
`ConnectorFieldMapping.objects.all().delete()` → `ProjectIntegrationConnector.objects.all().delete()`, each above
`ProjectWebhookDelivery.objects.all().delete()`. No files to purge (7.18 stores no bytes).

**`admin.py`:** register all four models (`@admin.register(...)`) with `list_display`, `list_filter`, `search_fields`
mirroring 7.17's blocks (`admin.py:850-905`) — and **never** put `credential` in a `list_display`, `fields` or
`readonly_fields` list that renders its value.

**Audit verbs (≤10 chars, from `write_audit_log`):** `create`, `update`, `delete`, `toggle`, `rotate` (credential),
`test` (simulated connection test), `run` (job execution/rehearsal), `retry` (run retry). Do **not** invent longer
verbs — `AuditLog.action` is `varchar(10)`.

## 6. Risks, open questions, and what 7.19 must not re-declare

### 6.1 Template casing (real portability risk, inherited from 7.17)
7.17 stores templates under `templates/projects/WorkflowAutomation/…` while rendering
`"projects/workflowautomation/…"`. That resolves on Windows/NTFS (case-insensitive) but would **404 on a
case-sensitive filesystem**. **Recommendation for 7.18: create the disk folders in the exact case the views
render** — `templates/projects/integrationapihub/<entity>/…` — which mirrors 7.17's *render-string* convention
byte-for-byte and removes the trap. Do **not** "fix" 7.17's folders in this pass (shared files, another session
in flight). If the contract instead mandates PascalCase on disk, mirroring 7.17 exactly, that is acceptable on
this project's Windows-only runtime — but then the render strings must keep the lowercase spelling so grep stays
consistent with 7.17.

### 6.2 The credential-store call is the one genuinely judgemental decision
§4.6 rules **Fernet encryption**; it is defensible and matches 7.17, but it is the single item a reviewer could
argue the other way (a transport-less register arguably wants 4.19's prefix+hash marker). The contract must pin it
explicitly, and the model docstring must state which way it went **and why** — either answer is acceptable only if
written down. Whichever is chosen: no plaintext, no reveal view for a hashed value, and `credential` never appears
in a template, a `list_display`, or an audit-log `changes` payload.

### 6.3 Known constraint limitations (state them, do not paper over them)
- `unique_together = ("tenant", "project", "name")` does **not** prevent two rows with `project=NULL` from sharing
  a name on MySQL/MariaDB (NULLs compare distinct in a unique index). Keep the DB constraint for the project-scoped
  case and add a **form-level** duplicate check (`clean_name` + `_reject_foreign`-style error) so the UI behaves.
- Deleting a `Project` CASCADEs its connectors → jobs → runs (7.17's `ProjectWebhookEndpoint.project` is CASCADE
  too). That is deliberate: a project's connector is project configuration. The docstring should say so, so nobody
  later "fixes" it to SET_NULL and silently promotes a deleted project's Jira connector to workspace-wide.
- `next_run_at` / `next_retry_at` are **stamps**, not triggers. `trigger_mode` / `interval_minutes` /
  `filter_expression` record intent only; no scheduler exists. Every one of these fields needs a help_text saying
  so (4.19's `trigger_mode` help_text is the model to copy).

### 6.4 Concurrency (L43) — the shared files this pass must edit carefully
A sibling session is mid-flight on **7.16** (§1.1), which also touches `apps/core/navigation.py`,
`seed_projects.py` (`_seed_tenant` + the `--flush` block), `apps/projects/models/__init__.py`, `admin.py` and
possibly `views/_helpers.py` (already dirty in the working tree). 7.18 must make **surgical `Edit` calls only** on
each shared file — never a full rewrite — and must re-read each shared file immediately before editing it.

### 6.5 What 7.19 Master Data & Configuration must NOT re-declare
- **Not** a second connector/provider register, and **not** a "custom fields for integrations" engine that
  reproduces `ConnectorFieldMapping.value_map` — field mapping belongs to 7.18.
- **Not** a project-template importer that imports *connectors* (templates may later *reference* a connector by FK;
  that would be an extend-by-FK, which is allowed).
- **Not** an organization-hierarchy model duplicating `core.OrgUnit` (`Project.org_unit` already points at it), and
  **not** a new language/timezone table that 7.18's `environment`/`status` vocabulary would have to be re-pinned
  against.
- **Not** a second "integration hub" sidebar entry: `LIVE_LINKS["7.18"]` owns those five leaves.

### 6.6 Deferred (later passes / integrations) — recorded so nothing is lost
Real transport for any provider (bus/CI/CD triggers, Drive/SharePoint deltas, OAuth code + refresh flows, token
vault, webhook *verification*), a scheduler/worker that fires `ProjectSyncJob`s (Celery/cron — platform-level),
write-back verbs into CRM/HRIS/DevOps, permission/sharing mirroring for storage connectors, cross-account
connector promotion sandbox→production, and a mapping dry-run that shows the diff before committing. All of them
land on the same four tables; **none of them requires a fifth model**.

## 7. Evidence appendix (every read/grep/fetch actually run, with what it showed)

### 7.1 Files read (in full or the cited line ranges)
- **Brief/persona/skill:** `.claude/agents/research.md`; `.claude/skills/next-module/SKILL.md` (Phase-1 contract +
  quality bar); `.claude/tasks/research-projects-7.17.md` (tone/structure + what 7.17 parked to 7.18:
  *"Deep Bidirectional System Synchronization (SAP, Oracle, Jira, GitHub, Salesforce sync) → Parked for 7.18
  Integration & API Hub"*); `.claude/tasks/research-inventory-5.19.md:91-200, 291-340`;
  `.claude/tasks/research-scm-4.19.md:38-195, 434-545`; `NavERP.md:1253-1293` (7.14–7.19 headings + the five 7.18
  bullets verbatim).
- **The boundary files:** `apps/projects/models/WorkflowAutomation/Webhooks.py` (full);
  `apps/scm/models/IntegrationApiGateway/IntegrationEndpoints.py` (docstring + fields + `clean()` + `Meta`);
  `…/IntegrationApiGateway/_choices.py:1-200`; `…/IntegrationMessages.py`; `…/__init__.py` (proved **empty**);
  `apps/crm/models/AutomationWorkflow/Webhooks.py`; `apps/accounting/models/Integration/IntegrationConfigs.py:1-56`;
  `apps/core/crypto.py` (full); `apps/inventory/models/ThirdPartyIntegrations/{IntegrationChannels.py (head),
  ChannelListingMaps.py (head), StockSyncRuns.py (head + docstring)}`;
  `apps/inventory/models/AccountingFinancialIntegration/JournalSyncLogs.py:1-60`.
- **The spine:** `apps/projects/models/_base.py` (full); `models/__init__.py:120-174`;
  `models/WorkflowAutomation/WorkflowRules.py:1-122`; `models/ProjectInitiation/Projects.py:1-115`;
  `models/ResourceManagement/ResourceProfiles.py` + `ResourceAllocations.py` (field greps);
  `forms/WorkflowAutomation/Webhooks.py:1-90`; `forms/_common.py` (full);
  `views/WorkflowAutomation/Webhooks.py:1-120`; `views/_common.py` (import list);
  `urls/WorkflowAutomation/{Webhooks.py, AutomationBoards.py, __init__.py}`; `urls/__init__.py:1-40`;
  `urls/ReportingBusinessIntelligence/{ProjectReports.py, ReportingHome.py}`; `admin.py` (7.17 greps);
  `apps/core/navigation.py:1995-2060`; `static/css/theme.css:286-291`; `apps/core/models/AuditLog.py` (grep).

### 7.2 Commands and their results
| Command (abridged) | Result |
|---|---|
| `git rev-parse HEAD` / `git status --porcelain` *(read-only queries; no add/commit/push was run)* | HEAD = `2a65450…`; dirty tree holds another session's files (`.claude/tasks/contract-projects-7.16.md`, `apps/projects/views/_helpers.py`, the untracked 7.16 `DashboardWidgets.py` pair, `apps/core/models/Workflow.py`, several `plan-remaining-*.md`) — **not ours** |
| `Select-String '^### 7\.' NavERP.md` | 7.1–7.19 at :1162–:1288; 7.18 = :1281 |
| `Select-String '^    "7\.\d+": \{' apps/core/navigation.py` | keys 7.1–7.15 + 7.17 only; **no 7.16** |
| `Get-ChildItem apps/projects/migrations` (sorted, last 4) | ends `0025_projectwebhookdelivery_…` |
| `Select-String 'NUMBER_PREFIX ='` over `apps/**/models` | projects list captured; repo-wide list captured; `IXC`/`IXM`/`SYJ`/`SYR` **absent** |
| `Select-String 'path\("(integration\|sync\|connector\|mapping)'` over `apps/projects/urls/**` | **0 hits**; the matching `name="…"` grep → **0 hits** |
| url-name greps over `urls/{ProjectInitiation,ProjectPlanningScheduling,RiskManagement,ResourceManagement,DocumentKnowledgeManagement}/*` | the `prj_*`/`tsk_*`/`iss_*`/`rsp_*`/`ral_*`/`rte_*`/`pdm_*`/`pfd_*` sets in §1.6 |
| `Select-String '"(accounting\|scm\|crm\|hrm\|inventory\|procurement)\.[A-Za-z]'` over `apps/projects/models` | 17 hits: accounting ×14, `crm.Opportunity`, `hrm.EmployeeProfile`; **no scm/inventory/procurement** |
| `Select-String 'apps\.(accounting\|scm\|crm\|hrm\|inventory\|procurement)\.'` over `apps/projects/models` | **0 hits** — string FKs only, no peer imports |
| `Select-String '^    def '` in `seed_projects.py` | `handle` :314, `_seed_tenant` :414, `_planning` … `_workflow_automation` :4138 — **no `_seed_717_*`** |
| `seed_projects.py` lines 313–462 | the `--flush` children-first delete list (7.17's rows near the top) |
| `seed_projects.py` lines 4138–4197 | `_workflow_automation(self, tenant, now)` guard + `.objects.create(...)` rows |
| `Select-String 'action="[a-z_]+"'` over `apps/projects/views/**` | 20 shipped verbs, all ≤10 chars |
| `Select-String '^class '` over the ten model files in §1.6 | confirms every class name/number cited (`class Project(TenantNumbered)`, `NUMBER_PREFIX = "PRJ"`) |
| `Select-String 'TENANT_SCOPED_FKS' -Context 0,12` on `IntegrationEndpoints.py` | `("partner_party", "logistics_client", "location", "spec_document")` |
| `Select-String 'NUMBER_PREFIX\|^class '` over scm 4.19's four files | `IntegrationEndpoint` CNX, `IntegrationMessage` **MSG**, `WebhookSubscription` WHK, `WebhookDelivery` none |
| `Get-ChildItem templates/projects -Directory` + `templates/projects/WorkflowAutomation -Recurse -File` | 16 sub-module folders; 7.17 has `workflow/ approvalgate/ recurringtask/ webhook/ boards/` + `boards/{overview,approval_inbox,recurrence_calendar,webhook_diagnostics}.html` |
| `Get-ChildItem apps/projects -File` + services probe | `admin.py analytics.py apps.py __init__.py` — **no `services/` package** (a service helper must live in `views/_helpers.py` or the entity module) |
| `Get-Date` | 2026-09-20 |

### 7.3 Web fetches (see §2 for what each contributed)
Successful: `asana.com/apps`, `clickup.com/integrations`, `smartsheet.com/integrations`, `wrike.com/apps/`,
`workato.com/integrations`, `atlassian.com/software/jira/integrations`,
`experienceleague.adobe.com/.../workfront-fusion-overview`, `fivetran.com/connectors`.
Failed and **not used as evidence**: `monday.com/apps` (404), `marketplace.atlassian.com/categories/integrations`
(shell only), `wrike.com/integrations/` (404), `unito.io/sync/` (404), Adobe's Workfront-integrations landing page
(timeout).

### 7.4 `UNVERIFIED` items (flagged, not asserted)
- Whether a **7.16** seeder helper (`_reporting_…`) exists — the `^    def ` grep shows none, consistent with a
  mid-flight session; out of scope to inspect further.
- The exact `render()` paths of 7.16's board pages (those files are untracked in another session and were not read).
- The Svix backoff tuple as re-fetched from Svix *in this run* — it is cited from the two shipped in-repo adoptions
  (`scm`'s `DELIVERY_BACKOFF_SECONDS`, `inventory`'s `SYNC_BACKOFF_SECONDS`), which agree with each other:
  `(0, 5, 300, 1800, 7200, 18000, 36000, 36000)`.
- Whether `apps/projects/forms/__init__.py` and `apps/projects/views/__init__.py` currently carry re-export blocks
  for 7.17 — **not read**; the integrator must open them before editing (§5.0 says "if those packages re-export").
- Anything about `monday.com`'s integrations UX — the fetch failed, so nothing about it is claimed in this file.

---

**Hand-off note.** This file is the whole Phase-1 deliverable. The `todo` agent should turn §3 (rows 1–45, the
"build now" set) into checkable build items and §5 into the contract skeleton; the two corrections it must carry
forward are **(i)** the seeder helper is `_integration_hub`, not `_seed_718_*`, and **(ii)** `IntegrationMessage`
is `MSG-`, not `INT-` (`INT-` is inventory 5.19's `IntegrationChannel`).


