# Research — Sub-module 8.8: Sales Activity & Task Management (Module 8 — Sales, `apps/sales`)

> Phase 1 output. Target pre-resolved: **8.8 Sales Activity & Task Management**. NavERP.md 8.8 = the five
> feature bullets reproduced verbatim in §2. All five are addressed.

**Access note (differs from 8.7).** No live fetches were possible this session — the WebSearch provider
declined the model and WebFetch's page-summariser model was rejected — so this catalog is written from
product knowledge rather than from fetched primary documentation. Feature names below are the vendors'
well-known product surface names; **treat the vendor attributions as "this product is known to ship a
capability of this shape" rather than as a quoted doc line.** Anything that turns out to be a misremembered
product name is harmless here, because §4's reuse-vs-build ruling is driven by **what is already in
`apps/crm`**, which was read directly from source. The five CRM models quoted in §1 were read from disk,
not from memory. Re-verify the vendor table before quoting it in a customer-facing document.

**Products considered (10):** Salesforce Sales Cloud (Activity/Task/Event objects, Activity Timeline,
Einstein Next Best Action / Lead Scoring, Email-to-Case-free Email Application, High Velocity Sales,
Productivity Features / Call Coaching), Microsoft Dynamics 365 Sales (Activities, Microsoft Bookings +
Schedule Hub shared availability links, Dynamics 365 Sales coaching/next-best-action suggestions),
HubSpot Sales Hub (Tasks & Sequences, Meetings, Inbox conversations, Sales Hub "Suggested next step"),
Salesloft / Outreach / Clari (cadence sequences, step-level activity logging, next-best-action ranking),
Pipedrive (Activities & Next Steps), Zoho CRM (Activities, Follow-ups, Sales Insights, Zoho Meeting),
Freshsales (Activities, Territory-based selling), monday sales CRM (automations, status/activity board),
Gong / Clari conversation intelligence (call recordings feeding suggested follow-ups), LinkedIn Sales
Navigator (lead/account Alerts as auto-created activities).

---

## 1. Ownership ruling — 8.8 EXTENDS the CRM 1.5 activity stack; it declares no second Task, CommunicationLog or CalendarEvent

**The ruling.** Sub-module 8.8 adds four primary models and two child models, and *not one of them is an
activity, a task, or a calendar event master.* CRM 1.5 ("Activity & Communication Management", NavERP.md
line 468) shipped first and is **already fully live** — its three `LIVE_LINKS["1.5"]` bullets point at
`crm:task_list`, `crm:calendarevent_list` and `crm:communicationlog_list`. Every one of those three models
is a real table with real views, real forms and seeded demo rows. 8.8 is the **sales-commercial layer
above** that stack: the typed catalogue, the attribution, the playbooks, the plan.

| Shared entity | Owner | Where it lives (read from source) | How 8.8 uses it |
|---|---|---|---|
| `CommunicationLog` (`COM-`) | **CRM 1.5** | `apps/crm/models/ActivityManagement/CommunicationLogs.py` | `ActivityLog.communication_log` — a **required** FK, 1:1. `channel`, `direction`, `subject`, `body`, `party`, `owner`, `related_opportunity`, `related_case`, `occurred_at`, `duration_seconds`, `outcome`, `logged_via`, `email_message_id` are **read, never re-declared**. |
| `CrmTask` (`TASK-`) | **CRM 1.5** | `apps/crm/models/ActivityManagement/Tasks.py` | `TaskTemplate` generates **`crm.CrmTask`** rows. `type`, `priority`, `status`, `due_date`, `owner`, `party`, `related_opportunity`, `related_case`, `recurrence*` are **read, never re-declared**. |
| `CalendarEvent` (`EVT-`) + `EventAttendee` | **CRM 1.5** | `apps/crm/models/ActivityManagement/CalendarEvents.py` | Read-only, by the plan board and the next-best-action board. `sync_source`, `public_token`, `video_url` and the whole RSVP/ICS layer already exist — 8.8 builds **no** booking token. |
| `core.Activity` | **core 0** | `apps/core/models/Activity.py` | The generic spine activity (kind/owner/party/generic-`related`/status/`due_at`). Left alone entirely. |
| `Party` | **core 0** | `apps/core/models/Party.py` | `ActivityLog.account` FKs `core.Party` (`kind="organization"`). No new customer table (L29). |
| `Opportunity` | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `ActivityLog.opportunity` FK. Its **own** `owner`, `territory`, `next_step`, `next_step_due_date` columns are read by the suggestion board — 8.8 does not re-spell them. |
| `Territory` (`TER-`) | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Territories.py` | `ActivityLog.territory` / `TaskTemplate.territory` / `SalesPlanCycle.territory` FK. Owned here by 8.7's ruling; 8.8 follows it. |
| `User` | **accounts** | `apps/accounts/models/…` | `owner` FK on all four primaries, mirroring `CommunicationLog.owner`. |
| `ForecastPeriod` | **Sales 8.4** | `apps/sales/models/SalesForecasting/ForecastPeriods.py` | Read by the plan board for quarter framing. 8.8 does not re-spell year/quarter/month. |

**Why this is the ruling and not a preference (L29 / L36 / L37).**

- **L29** fixed the pattern at its sharpest edge: `accounting` owns the GL ledger, and every later module
  posts through *that* ledger by string FK. Ownership is decided by **who shipped it first and made it
  real**, not by which module's title sounds like it should own it.
- **L36** made it a procedure: the later module **extends by FK and never re-declares**, and reconciling
  the two plan rows is a required close-out step, not a note.
- **L37** is the direct precedent: Module 5 is literally *named* Inventory and still extended the `scm`
  spine rather than declaring its own `Item`/`StockMove`.
- **8.8 is the most tempting case of the five, because CRM 1.5's title ("Activity & Communication
  Management") and 8.8's title ("Sales Activity & Task Management") are near-synonyms.** The module with
  "Activity" in its title does **not** get to re-declare the activity. This is L37 applied to a name
  collision instead of a domain collision.

**The alternative, argued and rejected: Sales re-declares its own stack.** Suppose 8.8 ships
`sales.SalesActivity` (`SAL-`) with `channel/subject/occurred_at/duration_seconds`, plus a
`sales.SalesTask` with `due_date/priority/status/recurrence` and a `sales.SalesMeeting` with
`start/end/sync_source`. It would look locally complete against NavERP.md's five bullets. It is wrong for
six concrete reasons, in ascending order of cost:

1. **Two rows for one phone call.** A rep logs a call; 8.8's stack and 1.5's stack each want it. Nothing
   reconciles them. The activity timeline shows a gap that no amount of querying explains.
2. **The recurrence engine already exists and is tested.** `CrmTask.save()` detects the open→done
   transition and spawns the next occurrence, clamped to month end via `calendar.monthrange`, guarded
   against a duplicate at the same next due date. 8.8 re-implementing that is the exact fork 8.7's
   `TerritoryRule` docstring warns about when it imports 8.1's `ROUTING_OPERATORS` instead of writing a
   second validator.
3. **`CommunicationLog.logged_via` is the provenance column this whole bullet is about.** It already
   distinguishes `manual` / `bcc_dropbox` / `voip` / `sync`. A second stack would have a second,
   differently-spelled provenance vocabulary — and "automatic capture" (bullet 1) is precisely a question
   about provenance.
4. **Recurring-task templates are NOT owned by CRM.** `CrmTask` recurs a *single task* forward. A
   **template** that fans out to many tasks against many targets is genuinely un-owned — so the
   un-owned thing is available without touching anything CRM owns. See §4.
5. **Email open/click tracking is genuinely un-owned.** `CommunicationLog` stores `email_message_id` for
   dedup and nothing else; there is no open counter, no click counter, no reply stamp anywhere in
   `apps/crm`. The un-owned thing is again available without a conflict.
6. **The plan layer is genuinely un-owned.** Activity *goals* and plan *cycles* exist nowhere.

So the ruling costs nothing: three of the four genuinely-un-owned features (template, engagement,
planning) are all new tables, and the one that is owned (the activity itself) is read through a FK.

**This is the fifth application of L36/L37** (after inventory→`scm`, 8.6→`scm.SalesOrder`,
8.7→`crm.Territory`/`crm.SalesQuota`, 7.18's parallel `IntegrationConnector` registers). The ruling lands
in four durable places, as the 8.7 ruling did: this file, the `SalesActivityTaskManagement` package
docstring, the `LIVE_LINKS["8.8"]` comment in `apps/core/navigation.py`, and `.claude/tasks/lessons.md`.

---

## 2. The five NavERP.md 8.8 bullets, verbatim

- **Activity Logging & Tracking** — Calls made, emails sent, meetings held, and custom activity types with automatic capture.
- **Task & Follow-up Management** — To-do lists, due dates, priority flags, and recurring task templates.
- **Calendar & Meeting Scheduling** — One-click meeting booking, shared availability links, and CRM-synced calendars.
- **Email Integration & Tracking** — Gmail/Outlook sync, email open/click tracking, and template libraries.
- **Daily/Weekly Sales Planning** — Priority deal lists, activity goals, and AI-suggested next best actions.

### Bullet-by-bullet verdict

| Bullet | Already owned? | What 8.8 adds |
|---|---|---|
| 1. Activity Logging & Tracking | **Interaction record** owned (CRM 1.5). **Type catalogue** and **sales attribution** un-owned. | `ActivityType` (custom types), `ActivityLog` (attribution + auto-capture provenance). |
| 2. Task & Follow-up Management | **Task rows + single-task recurrence** owned (CRM 1.5). **Templates** un-owned. | `TaskTemplate` + `TaskTemplateStep` — a playbook that materialises `crm.CrmTask` rows. |
| 3. Calendar & Meeting Scheduling | **Almost entirely owned** (CRM 1.5 has `sync_source` for Google/Outlook/iCal, `public_token` for login-free invite/RSVP/`.ics`). | Nothing new as a table. The **board** surfaces upcoming events needing prep. One-click booking and shared-availability links are CRM's `public_token` surface — 8.8 links to it rather than duplicating it. |
| 4. Email Integration & Tracking | **Sync + dedup** owned (`logged_via`, `email_message_id`). **Open/click/reply tracking** un-owned. **Template libraries** un-owned but out of scope for 1–4 (see §6 note). | `ActivityLog.opened_at/.open_count/.clicked_at/.click_count/.replied_at`, advanced only by a POST verb; plus a rollup board. |
| 5. Daily/Weekly Sales Planning | Un-owned. | `SalesPlanCycle` + `ActivityGoal`; plus a next-best-action board. |

---

## 3. Feature catalog (deduplicated, prioritized)

Priority key: **P0** = a NavERP.md bullet cannot honestly be served without it; **P1** = the bullet is
served but weakly without it; **P2** = real product feature, out of scope for this pass.

### 3.1 Typed activity catalogue (P0)

- **Custom activity types beyond the five channels.** Every product above lets an admin define org-specific
  types ("Discovery call", "Technical validation", "Executive sponsor drop-in"). Salesforce ships custom
  `ActivityType` sObjects; HubSpot/Zoho ship custom activity types; Pipedrive ships a customisable activity
  list. **CRM 1.5 has no type catalogue** — `CommunicationLog.channel` is a closed 5-value field and
  `CrmTask.type` a closed 5-value field, neither configurable. → **BUILD NEW** `ActivityType`.
- **Per-type defaults** (default outcome, default duration, default priority, "requires an opportunity").
  Shipped as configurable defaults by Salesforce/Zoho. Only meaningful if the type exists. → fields on
  `ActivityType`.
- **Retire, don't delete.** A type referenced by historical activity must not vanish under it. → status
  field + `PROTECT` on the FK.

### 3.2 Sales attribution of an activity (P0)

- **Linking an activity to a deal and an account.** `CommunicationLog` has `related_opportunity` but
  nothing links a *call* to the territory that owns the rep or the quota it advances. → `ActivityLog`
  with `opportunity` / `account` / `territory` / `owner`.
- **Automatic capture provenance.** Bullet 1 says "with automatic capture". `logged_via` already records
  *how the interaction was captured*; what is missing is the sales-side mirror that a rep's activity feed
  can filter on without joining. → `capture_source` + `is_auto_captured`, IMPORTED vocabularies.
- **Next-best-action field on the activity.** Salesforce's Einstein and Salesloft both write a suggested
  next step back onto the deal/activity. → `next_best_action` + `next_best_action_due`.

### 3.3 Recurring task templates (P0)

- **A named playbook that spawns many tasks.** Salesforce *Process Builder*/*Flow*, HubSpot *Sequences*
  and Salesloft *Cadences* all do this; Pipedrive and Freshsales ship a lighter "activity template".
  **Nothing in `apps/crm` fans one definition out to many targets.** `CrmTask.recurrence` advances *one*
  task forward on completion — a different feature. → **BUILD NEW** `TaskTemplate` + `TaskTemplateStep`.
- **Target scope**: against an opportunity, an account, or a whole territory (e.g. "call every account in
  EMEA under £50k ARR every fortnight"). → `target_type` + `territory`.
- **Cadence + interval**, and a **generation receipt** so a re-run cannot double-spawn. → `cadence`,
  `cadence_interval`, frozen `last_generated_on` / `generated_count`.

### 3.4 Email engagement tracking (P0)

- **Open / click / reply counters.** Every product above ships this; Clari/Salesloft built businesses on
  it. `CommunicationLog.email_message_id` exists **for dedup only** — there is no counter, no timestamp,
  no reply stamp in `apps/crm`. → five fields on `ActivityLog`, all `editable=False`, advanced only by a
  POST verb. **Derived** `engagement_level` as a `@property` (L37: derived, never stored).
- **A rollup by rep / by type.** → board, §7.

### 3.5 Daily / weekly planning (P0)

- **A plan cycle with a named window** (a day or an ISO week). HubSpot's "Weekly Planning" and Zoho's
  "Sales Insights" both key on this. → `SalesPlanCycle`.
- **Activity goals per cycle** (make N calls / N emails / N meetings). → `ActivityGoal`, unique per
  (cycle, metric). **Actuals are derived** from `ActivityLog` + `crm.CrmTask` in the window — never stored
  (L37).
- **Next-best-action suggestions.** Rule-based, deterministic, scored. Salesforce Einstein, HubSpot
  "Suggested next step", Dynamics suggestions and Gong follow-ups are all this shape. → board, §7.
  **Stated honestly:** these are *rules*, not a model. The module's `suggestion_mode` records whether a
  suggestion was `manual`, `assisted` or `automatic`; nothing pretends to be an LLM.

### 3.6 Read-only boards (P0/P1)

- **"My Day" plan board** — open `crm.CrmTask` rows, upcoming `crm.CalendarEvent` rows, `ActivityGoal`
  progress. Serves bullets 3 + 5 together.
- **Engagement rollup** — opens/clicks/replies by rep and by activity type. Serves bullet 4.
- **Stale-deal sweep** — open opportunities with no logged activity in N days. Serves bullet 5 and is the
  most-used query in every product above.

### 3.7 Out of scope this pass (P2) — named so it is a decision, not an omission

- **Email template library** (bullet 4's third clause). `apps/crm` has `EmailCampaign`/`EmailTemplate`
  (reachable through `tenant_drip_campaigns()` in `apps/sales/forms/_common.py`), so a *template* master
  here would be a fork. P2.
- **One-click booking / shared availability links** (bullet 3's first two clauses). CRM 1.5's
  `CalendarEvent.public_token` already is a login-free invite surface and its `SYNC_SOURCE_CHOICES` already
  covers Google/Outlook/iCal. Building a second token is a bug. 8.8 **links** to it.
- **True cadence sequencing** (Salesloft/Outreach multi-channel steps with reply-detection branching).
  That is its own sub-module-scale feature; 8.8 ships the *template* half.
- **Conversation intelligence** (Gong call transcription → suggested follow-up).

---

## 4. Reuse-vs-build table

| Feature | Verdict | Detail |
|---|---|---|
| Calls / emails / meetings recorded | **REUSE `crm.CommunicationLog`** | Read via `ActivityLog.communication_log`. |
| Channel vocabulary | **IMPORT** `CommunicationLog.CHANNEL_CHOICES` | `ActivityType.kind` re-uses the list; it must not drift. |
| Call outcome vocabulary | **IMPORT** `CommunicationLog.OUTCOME_CHOICES` | `ActivityType.default_outcome`. |
| Capture-provenance vocabulary | **IMPORT** `CommunicationLog.LOGGED_VIA_CHOICES` | `ActivityLog.capture_source` is the sales-side mirror of it. |
| Task rows, to-do lists, due dates, priority flags | **REUSE `crm.CrmTask`** | Read; generated by `TaskTemplate`. |
| Task-type / priority vocabulary | **IMPORT** `CrmTask.TYPE_CHOICES`, `CrmTask.PRIORITY_CHOICES` | On both `TaskTemplate` and `TaskTemplateStep`. |
| Single-task recurrence | **REUSE `crm.CrmTask._spawn_next_occurrence`** | Not re-implemented. 8.8 adds only the *template → many tasks* fan-out. |
| Meetings, scheduling, Google/Outlook/iCal sync | **READ-ONLY board over `crm.CalendarEvent`** | No new calendar table, no second token. |
| Invitation / RSVP / `.ics` links | **REUSE `crm.CalendarEvent.public_token`** | 8.8 links out. |
| Email sync + dedup | **REUSE `CommunicationLog.logged_via` / `.email_message_id`** | Read. |
| Email open / click / reply tracking | **BUILD NEW** (on `ActivityLog`) | Genuinely absent from `apps/crm`. |
| Custom activity types | **BUILD NEW** `ActivityType` | Genuinely absent. |
| Sales attribution of an activity (deal/account/territory/rep) | **BUILD NEW** `ActivityLog` | `CommunicationLog.related_opportunity` alone is not the attribution layer. |
| Recurring task **templates** | **BUILD NEW** `TaskTemplate` + `TaskTemplateStep` | Absent. |
| Daily/weekly plan + goals | **BUILD NEW** `SalesPlanCycle` + `ActivityGoal` | Absent. |
| Goal **actuals** | **DERIVED on a board, never stored** | L37. |
| Next-best-action suggestions | **READ-ONLY board, deterministic scoring** | L61 — ordered, never `.first()` on an unordered qs. |
| Email template library | **P2 — REUSE `crm` email templates** | Not this pass. |
| Accounts / contacts / customers | **REUSE `core.Party` + `crm.PartyRole`** | L29. No new customer table. |
| Opportunities | **REUSE `crm.Opportunity`** | Its own `next_step`/`territory`/`owner` read, not re-spelled. |

**Anything a reviewer should grep for as a bug:** `class Activity`, `class Task`, `class Meeting`,
`class Call`, `class EmailLog`, `class SalesTask`, `class SalesActivity` **with its own
`channel`/`due_date`/`start`/`end` columns** anywhere under `apps/sales/models/`. `ActivityLog` is legal
only in the shape §6 pins: a required 1:1 FK onto `crm.CommunicationLog` plus attribution fields, with
**no `channel`, no `occurred_at`, no `duration_seconds`, no `subject`, no `body`, no `direction`, no
`outcome` of its own.**

---

## 5. Boolean combinations and preconditions (L39 / L44)

L39: *check that a feature's preconditions can ever be true at the same time.* L44: *a negative-input sweep
that never runs the positive path proves the guard, not the feature.* Every guard below is stated with
**both** its satisfying path and its violating path, so the tests can exercise each.

| # | Model | Guard | POSITIVE path (must succeed) | NEGATIVE path (must be refused) |
|---|---|---|---|---|
| G1 | `ActivityType` | `default_outcome` only applies to calls | `kind="call"`, `default_outcome="connected"` → saves | `kind="email"`, `default_outcome="connected"` → `ValidationError` on `default_outcome` |
| G2 | `ActivityType` | `default_duration_seconds` within 0–86400 | `default_duration_seconds=900` → saves | `default_duration_seconds=90000` → form/field error |
| G3 | `ActivityLog` | `is_auto_captured` **must agree** with `capture_source` | `is_auto_captured=True`, `capture_source="bcc_dropbox"` → saves; `False`+`"manual"` → saves | `True`+`"manual"`, **or** `False`+`"bcc_dropbox"` → `ValidationError` |
| G4 | `ActivityLog` | every FK must be same-tenant | `opportunity` from tenant A while `tenant=A` → saves | `opportunity` from tenant B → `ValidationError` |
| G5 | `ActivityLog` | exactly one sales log per communication log | first `SAL-00001` → saves | second with same `communication_log` → unique violation surfaced as a form error, never a 500 |
| G6 | `TaskTemplate` | `cadence="once"` ⟹ `cadence_interval == 1` | `once` + interval 1 → saves | `once` + interval 7 → `ValidationError` |
| G7 | `TaskTemplate` | `cadence_interval` in 1–12 | interval 2 → saves | interval 0 or 13 → `ValidationError` |
| G8 | `TaskTemplate` | `target_type="territory"` ⟹ `territory` set | territory set → saves | territory blank → `ValidationError` on `territory` |
| G9 | `TaskTemplate` | `target_type != "territory"` ⟹ territory blank | `target_type="opportunity"`, `territory=None` → saves | `target_type="opportunity"` **with** a territory → `ValidationError` (ambiguous target) |
| G10 | `TaskTemplateStep` | `offset_days` bounded −365…+365 | `-2` (prep before the anchor) → saves | `-400` or `400` → `ValidationError` |
| G11 | `SalesPlanCycle` | `period_end >= period_start` | weekly Mon→Sun → saves | end before start → `ValidationError` |
| G12 | `SalesPlanCycle` | **`cadence="daily"` ⟹ `period_end == period_start`** | both `2026-10-02` → saves | a "daily" cycle spanning a week → `ValidationError`. This is the L39 trap: both dates are individually valid and the pair is not. |
| G13 | `SalesPlanCycle` | one plan per (owner, period_start, cadence) | first row → saves | second with the same triple → refused |
| G14 | `SalesPlanCycle` | `closed_at` is system-set on close, cleared on reopen | `status` draft→closed stamps it; closed→draft clears it | a POST naming `closed_at` → ignored (field is not on the form at all) |
| G15 | `ActivityGoal` | one goal per (cycle, metric) | first row → saves | duplicate metric on the same cycle → refused |
| G16 | Generation verb | **idempotent** — a second run on the same cycle date creates nothing | run once → N tasks; run again same day → 0 tasks, receipt unchanged | — (the negative here is "run twice", which must be a no-op, not a refusal) |

---

## 6. Recommended build scope — 4 primary models, 2 children

### `ActivityType` — prefix **`ATY-`** (bullet 1)

`name`, `description`, `kind` (`CommunicationLog.CHANNEL_CHOICES`, default `call`), `default_outcome`
(`CommunicationLog.OUTCOME_CHOICES`, blank), `default_duration_seconds` (0–86400, nullable), `default_priority`
(`CrmTask.PRIORITY_CHOICES`, default `medium`), `requires_opportunity`, `is_billable`, `is_active`,
`display_order`. Unique `(tenant, name)`.

### `ActivityLog` — prefix **`SAL-`** — the sales attribution layer (bullets 1, 4, 5)

`communication_log` (**required** FK→`crm.CommunicationLog`, `on_delete=CASCADE`, unique per tenant),
`activity_type` (FK→`ActivityType`, **`PROTECT`**), `owner` (FK→User), `opportunity` (FK→`crm.Opportunity`),
`account` (FK→`core.Party`), `territory` (FK→`crm.Territory`), `capture_source`,
`is_auto_captured`, `next_best_action`, `next_best_action_due`.

**FROZEN (`editable=False`, L22 — auto-excluded from every form):** `occurred_on` (the `localdate()` of
`communication_log.occurred_at`, written once at create), `planned_minutes` (from the type's default
duration, else the log's duration, else 0), `opened_at` / `open_count` / `clicked_at` / `click_count` /
`replied_at`. Their **only** writers are the create view and the two POST verbs.

**Derived, never stored:** `engagement_level` — a `@property` with the precedence
`replied > clicked > opened > none`. A stored column would drift from its own five inputs (L37).

### `TaskTemplate` — prefix **`TTPL-`** (+ child `TaskTemplateStep`) (bullet 2)

`name`, `description`, `task_type` (`CrmTask.TYPE_CHOICES`), `priority` (`CrmTask.PRIORITY_CHOICES`),
`cadence` (`once/daily/weekly/biweekly/monthly/quarterly`), `cadence_interval` (1–12), `default_offset_days`,
`target_type` (`opportunity/account/territory`), `activity_type` (FK), `territory` (FK), `owner` (FK),
`is_active`. Frozen receipt: `last_generated_on`, `generated_count`.
Child `TaskTemplateStep`: `order`, `title`, `instructions`, `task_type`, `priority`, `offset_days` (−365…+365),
unique `(template, order)`.

### `SalesPlanCycle` — prefix **`SPC-`** (+ child `ActivityGoal`) (bullet 5)

`name`, `cadence` (`daily/weekly`), `period_start`, `period_end`, `owner` (FK), `territory` (FK), `status`
(`draft/active/closed`), `suggestion_mode` (`manual/assisted/automatic`), `notes`. Frozen `closed_at`.
Unique `(tenant, owner, period_start, cadence)`.
Child `ActivityGoal`: `metric` (`call/email/meeting/task/logged_total`), `target_count` (0–1000), unique
`(cycle, metric)`.

**Auto-number prefix check (L65 + collision sweep).** Every `NUMBER_PREFIX` in `apps/*/models/` was swept
before choosing. Findings: `TPL` is **taken** (`crm.DocTemplate`); `ACTP` is **taken**
(`hrm.SurveyActionPlan`) — which makes a bare `ACT` for `ActivityType` a one-character-from-a-collision
naming trap, so `ATY` is used instead even though `ACT` itself is technically free. `ATY`, `SAL`, `TTPL`
and `SPC` are all confirmed **free**. Every new `models.Index` name must be **≤ 30 characters**.

---

## 7. Board candidates (read-only, no new model)

Modelled on 8.7's `TerritoryBoards.py`, which shipped `territory_rebalance_preview`,
`territory_coverage_gap` and `territory_white_space`.

1. **`sales_activity_plan`** — *My Day / This Week.* Serves **bullets 3 + 5**. Reads `ActivityGoal`
   vs. derived actuals from `ActivityLog` in the cycle window, plus open `crm.CrmTask` rows and the next
   N `crm.CalendarEvent` rows. The board is where "shared availability / CRM-synced calendars" is
   *served* — by linking to the event, not by rebuilding it.
2. **`sales_next_best_actions`** — Serves **bullet 5**. Deterministic, scored rules over the spine:
   overdue open task → complete it; open opportunity with no `ActivityLog` in 14 days → log an activity;
   email opened, never clicked, >7 days → follow-up call; calendar event within 3 days with no prep
   activity → prep task. **L61: every ordering is explicit** (`-weight, due_date, pk`), never an
   unordered `.first()`.
3. **`sales_email_engagement`** — Serves **bullet 4**. Opens/clicks/replies by rep and by activity type,
   reading `ActivityLog`'s frozen counters with an explicit ordering.

Each board caps its scan (see §8) and states the cap on the page.

---

## 8. Guards, caps and bounds to pin in the build contract

- **Row-scan cap** on every board — a named `MAX_BOARD_*` constant, **surfaced in the template** so the
  figure reads as bounded rather than complete. House style: `TerritoryBoards.MAX_BOARD_ACCOUNTS`.
  **L40: a bound that computes the thing it is bounding is not a bound** — e.g. capping the goal board at
  "the first 200 activities" while also reporting a total over all of them is not a bound on the report.
- **JSON caps** — 8.8 stores **no** free-form JSON, so the `MAX_ROUTING_JSON_BYTES` family does not
  apply. Say so explicitly in the contract rather than leaving it ambiguous.
- **`ActivityLog` email counters** must be **monotonic**: a second "open" never decrements `open_count`,
  and `clicked_at` is never cleared by a later non-click event. Assert both directions.
- **Rate of engagement advancement** — the POST verbs advance counters; they must not accept an
  `engagement_level` from the POST body. Derived (see §6).
- **Determinism** — the "most recent activity per opportunity" query the suggestion board needs must carry
  an explicit `.order_by("-occurred_on", "-pk")`, not rely on insertion order (L61).
- **Idempotent generation** (G16) — a second `TTPL` generation run on the same calendar date must create
  **zero** tasks and must leave `last_generated_on` / `generated_count` unchanged.
- **Tenant isolation on every FK** — including `User`, which carries its own `tenant` (a user from
  another workspace is a cross-tenant pick, not a valid owner).

---

## 9. Verdict

Build **8.8** as four primaries + two children: `ActivityType` (`ATY-`), `ActivityLog` (`SAL-`),
`TaskTemplate` (`TTPL-`) + `TaskTemplateStep`, `SalesPlanCycle` (`SPC-`) + `ActivityGoal`, plus three
read-only boards. This serves all five bullets with **zero** re-declared CRM 1.5 entities, and the three
genuinely-un-owned features (templates, engagement tracking, planning) each get a real list page.