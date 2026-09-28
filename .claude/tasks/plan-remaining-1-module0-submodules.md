# Plan 1 — Finish Module 0 (System Admin & Security): ✅ **21 of 21 BUILT** — only 0.20 close-out left

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Status:** ✅ **BUILT (21 of 21)**; 🟨 0.20 Phase 6/7 outstanding
**Scope:** `core` + `accounts` + `tenants` + `dashboard` · **Effort:** small — one test wave + one docs pass

> **Re-verified 2026-09-28 against `LIVE_LINKS` (authoritative).** The original header said "14
> unbuilt"; **all fourteen are now live**: **0.4, 0.6, 0.8, 0.10, 0.11, 0.12, 0.13, 0.15, 0.16, 0.17,
> 0.18, 0.19, 0.20, 0.21**. **Module 0 is 21 of 21 (0.1–0.21) — COMPLETE.** Steps 0 and 2 are DONE
> (reconcile file committed; `core/SKILL.md` written). **Do not run `/next-module 0.N` again.**
>
> **The last three landed between 2026-09-26 and 2026-09-28:**
> - **0.19** → `tenants`, four models + four green test lanes + `tenants/SKILL.md` section.
> - **0.20** → `core`, five models, migration `core.0017`, six reviewers run, **17 of 19 fixed**
>   (X18/X19 deferred). **Phases 6 and 7 are NOT done** — see "What is left" below.
> - **0.21** → `core`, six models, migration `core.0018`, four green test lanes + `core/SKILL.md`
>   section. Complete through Phase 7.
>
> **`temp/audit_integrity.py` passes all six checks** (re-run 2026-09-28: 482 catalogued, **171 live**,
> 3,868 route names, 2,359 template refs, 761 sidebar targets, 0 unexplained unseeded models,
> `core: 21 live sub-modules`).

---

## Goal

Module 0 was the only module in the 0–7.13 range that was materially unfinished. At authoring it was
**7 of 21 sub-modules live**; it is now **21 of 21 (0.1–0.21)**. **This plan is closed as a build plan.**
The only thing it still asks for is 0.20's close-out, written out in "What is left" below.

## What is left — 0.20 close-out only

**Not one sub-module needs building.** Three items, in order:

### 1. Phase 6 — tests (0.20) — 🟨 half-started

`.claude/tasks/test-contract-core-0.20.md` **is written** and pins the lanes
`test_adminconsole_{models,forms,views,security}.py`, every `ac0_*` fixture, the POST-only set and
the L20/L22 negative-form assertions. `apps/core/tests/conftest.py` carries a **533-line uncommitted
`ac0_*` fixture block**. What does not exist yet is any of the four lanes.

1. Commit the conftest block on its own (one file, one commit).
2. Delete `apps/core/tests/test_ac0_smoke_tmp.py` — it is a throwaway harness and its own docstring
   says so (L46). It has done its job now that the fixtures are in `conftest.py`.
3. Write the four lanes **one at a time**, one commit each: `_models` → `_forms` → `_views` →
   `_security`. Every function `test_adminconsole_*`, every helper `_adminconsole_*` (the contract
   explains why: 0.21 owns the bare `test_core_*` names).
4. Run the **full unfiltered** `apps/core` suite and fix it green. Never `-k` filter (L47) — a filter
   excludes exactly the tests a shared `conftest.py` change can break. **Use `--nomigrations`**; on
   this box a filtered/unmigrated single lane is 17s, but a full suite that replays every migration
   in a 13-app project runs for tens of minutes.
5. Fix drift against the contract, not against the current code.

### 2. Phase 7 — docs (0.20) — ⬜ not started

- `.claude/skills/core/SKILL.md` has sections for 0.16, 0.17, 0.18 and 0.21 but **no 0.20 section**
  — grepping it for `JobDefinition|MaintenanceWindow|ChangeRequest|FeatureRollout` returns **0 hits**.
  Write it: five models, routes, templates, seeder rows, the `bulk_preview` sixth POST-only verb, the
  three-by-design `BULK_AFFECTED` zero lambdas, the four `NumberingScheme` prefixes, the ops-audit
  trail, and the gotchas (the two `AuditLog.action` width fixes, the `N+1` row-count-invariance
  lesson L58, the `NON_FIELD_ERRORS` keying rule from X-fixes C1/C3/C4).
- `README.md` — Module 0's row already reads `🟦 21 of 21 sub-modules built (0.1–0.21) — Module 0 is
  COMPLETE`, and it already narrates 0.21, 0.19 and 0.18. **Add the 0.20 sentence** so the row is not
  the one sub-module the roadmap does not describe.
- `todo.md` — add a 0.20 close-out note, and in the same sitting correct `todo.md:19`
  ("2 catalogued but NOT built → 0.20, 0.21") and tick the 0.21 checklist at `todo.md:12506+`, which
  is still entirely unchecked although 0.21 finished. Those are stale in a file another session may
  hold — if `git status` shows `todo.md` dirty, leave it to the owner (L43/L45).

### 3. Findings X18 + X19 — ⬜ deferred by Phase 5, on the record

`review-core-0.20.md:602-603` marks both `[~] skipped`. **X18 recommends an app-wide pass** on the
shared `crud.py` boolean map — it was skipped because `crud.py` was being used by the concurrent 0.21
session, not because the finding is wrong. **X19** (`ops_audit_trail` rendering `changes` in bulk)
was judged not a new exposure: same `@tenant_admin_required` audience, same tenant filter as 0.9's
`auditlog_detail`. Neither is a 0.20 defect. Decide explicitly whether to run the X18 sweep or accept
the deferral in writing; do not let it sit as an unexamined `[~]`.

### Also open, outside this plan

- **0.21 bullets 4 and 5** (audit/certification, data residency) were **deliberately deferred** to a
  second 0.21 pass with its own contract (`todo.md:12525`). Not a defect.
- **Module 8**: 8.1–8.5 are built; **8.6–8.19 (14 sub-modules) are not**. The next build anywhere in
  this repo is `/next-module 8.6`, not another Module 0 sub-module.
- `build-state.json` shows 7.10's Phases 3–7 as `pending` although 7.10 is built, and its last entry
  is 8.4 — the 0.19/0.20/0.21 runs were never recorded. Cosmetic, but it is why this plan's status
  was wrong for two days.

## Hard rules (do not skip)

1. ~~**Always pass the sub-module explicitly:** `/next-module 0.4`, never bare `/next-module`.~~
   **MOOT — Module 0 is complete. There is no `0.N` left to build.** The rule stands for the *next*
   module: bare `/next-module` auto-detects "the module currently in progress", which is now **module
   8**. The next build is `/next-module 8.6`, passed explicitly.
2. **`git status` first, every run.** A dirty tree at session start is not yours (L45). **The tree is
   dirty right now and this time the dirt IS 0.20's own Phase 6 work** — `apps/core/tests/conftest.py`
   modified, `test-contract-core-0.20.md` and `test_ac0_smoke_tmp.py` untracked. Finish it; it is not
   another session's.
3. **Agree the migration number** with any other live session before generating one (L43). `core` is at
   `0018_compliancecontrol_controlframework_and_more`; a 0.20 test lane should generate **no migration
   at all** — if it does, something in the contract drifted.
4. **One file per commit. Never `git push`.**
5. Run python as `venv\Scripts\python.exe` — Django is not on system python.
6. **`--nomigrations` on every pytest run on this box** (learned on 8.4: 17s vs ~40min).

---

## Step 0 — Reconcile the LIVE sub-modules before building anything new — ✅ **DONE (2026-09-19)**

> **COMPLETE — see `.claude/tasks/plan-1-module0-reconcile.md`.** Result: **nothing was built-but-unsurfaced.**
> Every unmapped bullet was genuinely absent or partial, so no bullet collapsed into a one-line nav addition
> and the remaining work stayed real work. `NavERP.md:90-96`'s claim that IAM/RBAC/User&Org/Audit are
> "substantially realized by `accounts` + `core`" is a claim, not a finding.

The table below records the state at authoring, before 0.4/0.6/0.8/0.10–0.13/0.15 were built:

| sub-module | bullets in NavERP.md | mapped in `LIVE_LINKS` | missing |
|---|---|---|---|
| 0.1 Tenant & Subscription | 5 | 4 | 1 |
| 0.2 Identity & Access Management | 5 | 2 | 3 |
| 0.3 RBAC & Permissions | 5 | 1 | **4** |
| 0.5 User & Organization | 5 | 2 | 3 |
| 0.7 Data Security & Encryption | 5 | 1 | **4** |
| 0.9 Audit Trail & Activity Logging | 5 | 1 | **4** |
| 0.14 Master Data & Reference Config | 5 | 1 | **4** |

`NavERP.md:90-96` claims IAM/RBAC/User&Org/Audit are "substantially realized by `accounts` + `core`",
so an unmapped bullet may be either **(a) built in code but never surfaced as a sidebar leaf**, or
**(b) genuinely absent**. Do not assume either. For each of the 7, and for each unmapped bullet:

1. Grep the app for the feature (`apps/accounts/`, `apps/core/`) — model, view, template.
2. Classify: *built-but-unlinked* (add the `LIVE_LINKS` leaf — cheap, one line) vs *absent* (real work).
3. Record the verdict in `.claude/tasks/plan-1-module0-reconcile.md` and commit that file alone.

**This step is cheap and it changes the size of the rest of the plan** — if several of the 24 unmapped
bullets are already built, they collapse into one-line nav additions rather than builds. **Do not start
0.4 until this is done.** It is the same discipline that caught 7.10 shipping a Live sidebar over 500s.

---

## Step 1 — The sub-modules, in build order — ✅ **all 14 built**

Numeric order was the default and is kept for history. The **two marked ★ were foundations other
sub-modules consume** — both are built. **All fourteen are done; do not rebuild any of them.**

| # | sub-module | title | status 2026-09-28 |
|---|---|---|---|
| 1 | 0.4 | Authentication & Single Sign-On (SSO) | ✅ **built** — MFA/TOTP, SAML/OIDC, password policy, session mgmt |
| 2 | 0.6 | Application Module Administration & Access Scope | ✅ **built** — the 13-bullet one |
| 3 | 0.8 | Privacy & Data Protection | ✅ **built** — consent, DSAR, retention, PII discovery |
| 4 | 0.10 ★ | System Configuration & Settings | ✅ **built** — settings, feature flags, numbering & sequences, business calendar |
| 5 | 0.11 ★ | Workflow & Approval Administration | ✅ **built** |
| 6 | 0.12 | Notification & Communication Management | ✅ **built** |
| 7 | 0.13 | Integration & API Management | ✅ **built** — API keys, webhooks/event bus, connectors |
| 8 | 0.15 | Localization & Regional Settings | ✅ **built** — language packs, RTL, multi-currency |
| 9 | 0.16 | Backup, Recovery & Data Lifecycle | ✅ **built** — 7 models, `core/migrations/0013_backup_recovery_data_lifecycle.py` |
| 10 | 0.17 | Monitoring, Logging & Observability | ✅ **built** — 4 models, `core/migrations/0015_alertrule_alertevent_servicecomponent_incident_and_more.py` |
| 11 | 0.18 | Threat Protection & Security Operations | ✅ **BUILT 2026-09-27** |
| 12 | 0.19 | License & Subscription Administration | ✅ **BUILT** — 4 models in `tenants`; 4 test lanes green; Phases 1–7 done |
| 13 | 0.20 | Admin Console & System Operations | 🟨 **BUILT, close-out open** — 5 models, `core/migrations/0017_…`; Phases 1–5 done (17/19 fixed); **Phase 6 tests + Phase 7 docs outstanding** |
| 14 | 0.21 | Compliance, Governance & Risk | ✅ **BUILT** — 6 models, `core/migrations/0018_…`; 4 test lanes green; Phases 1–7 done; bullets 4–5 deferred by design |

### What each of the last three actually shipped (so it is not re-derived)

- **0.19 — `apps/tenants`, four models.** `EntitlementFeature` [ENT-] (the commercial feature catalog
  with **typed** privileges: boolean / integer / select), `PlanEntitlement` [PE-] (a grant at a plan, or
  an **override** at one subscription that outranks the plan row), `UsageQuota` [UQ-] (the commercial
  **ceiling** — `quota_limit == 0` means UNMETERED, not "zero permitted") and `LicenseAssignment`
  [SEAT-] (the seat register; the prefix is `SEAT-`, **not** `LIC-`, which `scm.TradeLicense` already
  mints). Plus `Subscription.auto_renew` as a **three-state** column where `null` means *nobody has
  said*, and `grace_ends_on`. It **records** commercial terms and enforces **none** of them — no
  interceptor, no identity sync, no scheduler, no proration; all ten declines are stated in the page
  prose. Maps **4 of 5** bullets: bullet 4 is 0.1's `SubscriptionInvoice` + webhook, extended by
  reference rather than re-declared (L36). Tests: `test_licensing_{models,forms,views,security}.py`.
  **Two items it left open on the record:** the app-wide `aria-label` sweep beyond 0.19, and moving
  `next_number()` out of `Model.save()` so `bulk_create` becomes usable.
- **0.20 — `apps/core`, five models** across `JobScheduler.py` + `Maintenance.py` + `Change.py`.
  Numbers `JOB-` / `RUN-` / `MNTW-` / `CHG-`; `FeatureRollout` is **deliberately unnumbered** — it has
  no `number` field and no prefix, which `prefix_usage()` must say out loud rather than report a
  prefix nobody mints. Five named POST-only action verbs **plus `core:bulk_preview`** is the sixth
  POST-only view; all five `*_delete` views are `@require_POST` too, so a GET on any of the ten must
  not delete. Three of the six `BULK_AFFECTED` tools are hard `lambda t: 0` **by design** (accounting
  owns the ledger, CASCADE leaves no orphans, search has no separate index) and the board says so.
  Phase 4 produced 19 consolidated findings; Phase 5 fixed 17 and deferred X18/X19.
- **0.21 — `apps/core`, six models, all in one file** `apps/core/models/Compliance.py` (foundation-app
  flat layout — backend rule 9). `ControlFramework` [CFW-] is a **certification programme**; there is
  deliberately **no** `ComplianceFramework`, because 0.8's `RegulatoryFramework` already answers that
  question and already carries `data_residency_region` — a second framework table would give one
  workspace two answers at audit time (L36). `RiskRegister` is [GRC-] and **not** [RSK-], which is
  `projects.ProjectRisk`; two `RSK-00001`s in one tenant are indistinguishable to an operator, which
  is the exact failure `prefix_usage()` exists to catch. It **records** the posture and enforces
  **none** of it: no control gates an action, no auditor is granted access, no data is pinned to a
  region, nobody is reminded to acknowledge. `GRC_NOTES` prints this on every page. The seeder creates
  **zero** rows that assert certification, and every seeded acknowledgement carries a "DEMO DATA" note
  on the row.

### Notes carried forward (kept so the boundaries are not re-litigated)

- **0.17 declined three of five bullets** rather than faking them: centralized log aggregation (no log
  pipeline exists in this repo), distributed tracing / true APM (no tracing SDK), quota management
  (billing's). What ships is the alert-threshold vocabulary, the firings register, latency/throughput/
  slow-query thresholds, the capacity board and the incident register. **0.18 picked up from exactly
  that boundary.**
- **0.18** — `core.RateLimitPolicy` already exists (claimed by 0.2/0.4): extend, do not re-declare.
- **0.19** overlapped `tenants.Subscription` / `SubscriptionInvoice` (0.1) and `tenants.UsageRecord`:
  the boundary was stated, and `UsageQuota` became the **ceiling** half against `UsageRecord`'s
  consumption half, reusing `UsageRecord.METRIC_CHOICES` by identity.
- **0.20 / 0.6 are the natural home for console surfaces.** 0.20's models went into `core`, **not**
  `dashboard` — which keeps `dashboard` a model-less app whose test lane Plan 5 Item A already added.
  Had models landed there it would have needed its own lane.
- **0.21** reconciled against procurement 6.17's `ComplianceScreening`/`AuditSeal` and 4.12 and
  declined to re-declare either (L36). Risk→control FKs and cross-module rollup against
  `projects.ProjectRisk` were declined as a **cross-module project, not a 0.21 side effect**.
- **0.16** reused `core.DisposalRecord` as evidence of a real disposal rather than re-declaring it.

### Which app did each go in? (settled — recorded so nobody relocates them)

Module 0 spans four apps. The placement questions are all decided now:

- `tenants` — 0.1 ✅, 0.7 key management ✅, **0.19 licensing ✅** → tenant/commercial concerns.
- `accounts` — 0.2/0.3 ✅, **0.4 SSO ✅** → identity and auth.
- `core` — 0.9/0.14 ✅, **0.10, 0.11, 0.12, 0.13, 0.15, 0.16, 0.17, 0.18 ✅, 0.20 ✅, 0.21 ✅** → platform.
- `dashboard` — still only `apps.py`, `urls.py`, `views.py` (**no models**). It kept its own test lane
  from Plan 5 Item A, so a future console surface has somewhere to go, but **0.20 chose `core`**.

`0.6`'s 13 bullets are per-module access scopes for modules that mostly do not exist yet (8–23). It was
built against the modules that **are** live (1–7) with the rest as explicit no-ops.

---

## Per-sub-module procedure (identical to 7.1–7.15)

For each `N.M`, in this order, one thing at a time:

1. **Phase 0 — claim:** `git rev-parse HEAD` → save as `BASE`; `git status`; agree the migration number.
2. **Phase 1 — research agent** → `.claude/tasks/research-core-<N.M>.md` (6–10 leading commercial products
   in *this sub-module's* domain). Commit that file.
3. **Phase 2 — todo agent** → append the plan block to `.claude/tasks/todo.md`. Commit that file.
4. **Phase 3 — build:** contract → `.claude/tasks/contract-core-<N.M>.md` (pin every model field, CHOICES
   value, form `Meta.fields`, url name, and **every view context key** — L7/L8), then models → forms →
   views → urls → admin → templates → seeder → `LIVE_LINKS["N.M"]` → migration. One file per commit.
5. **Phase 4 — review:** the 6 reviewers **one after another** → `.claude/tasks/review-core-<N.M>.md`.
6. **Phase 5 — fix:** one `code-fixer` pass; re-verify each Critical with an independent probe.
7. **Phase 6 — tests:** `test-contract-core-<N.M>.md` first, then the conftest block (append-only, L43),
   then `test_<subslug>_{models,forms,views,security}.py`, one file per commit.
8. **Phase 7 — docs:** `SKILL.md`, `README.md` roadmap counter, `todo.md` close-out note.

### Verification gate after every sub-module

Run the reusable audit — it catches the four failure modes `manage.py check` cannot see:

```bash
venv\Scripts\python.exe temp\audit_integrity.py
```

All six checks must pass. A new sub-module that leaves check 3 (routes), 4 (templates) or 5 (sidebar)
failing is the 7.10 failure mode and must be finished before moving on.

---

## Step 2 — Give Module 0 a `SKILL.md` — ✅ **DONE (2026-09-22)**

> **COMPLETE.** `.claude/skills/core/SKILL.md` exists, committed as `4ce6b4a2`
> (*"docs(core): add the Module 0 SKILL.md (the only built module without one)"*). Module 0 is no longer
> the only built module without one. `accounts`/`tenants`/`dashboard` are covered by it.

---

## Done when

- [x] Step 0 reconcile file committed and every unmapped bullet classified —
      `.claude/tasks/plan-1-module0-reconcile.md`; verdict: nothing was built-but-unsurfaced.
- [x] **All 21 sub-modules have a `LIVE_LINKS["N.M"]` entry — ✅ 21 of 21 (0.1–0.21). 0.19, 0.20 and
      0.21 all landed; Module 0 is COMPLETE.** This is the item that makes the rest of this plan moot.
- [x] `temp/audit_integrity.py` passes all 6 checks — ✅ **verified 2026-09-28: all six PASS** at the
      current HEAD (482 catalogued, **171 live**, 3,868 routes, 2,359 template refs, 761 sidebar
      targets, 0 unexplained unseeded models). It reports **no** catalogued-but-unbuilt sub-module in
      Module 0, and `core: 21 live sub-modules`.
- [x] `.claude/skills/core/SKILL.md` exists with an accurate As-built line — `4ce6b4a2`; the as-built
      list now ends at `0.21`. *(One gap remains inside it: no 0.20 section — Phase 7, above.)*
- [x] `README.md` module-0 row updated — now `🟦 21 of 21 sub-modules built (0.1–0.21) — Module 0 is
      COMPLETE` (`README.md:1238`); `NavERP.md` likewise. Both corrected after 0.17 landed without a
      docs close-out, and again after 0.19–0.21. *(The 0.20 sentence is still missing — Phase 7.)*
- [ ] `.claude/tasks/todo.md` has a close-out note per sub-module — **0.1–0.19 and 0.21 done; 0.20
      outstanding**, and three stale spots to correct in the same sitting: `todo.md:19` ("2 catalogued
      but NOT built → 0.20, 0.21"), the fully-unchecked 0.21 checklist at `todo.md:12506+`, and the
      missing 0.20 note.

## Risks — carried forward, now historical for the builds

- **Auto-detect will fight you** — for the *next* module, not this one. Bare `/next-module` picks the
  lowest `N.M` in the module in progress, which is now **module 8**. The next build is
  **`/next-module 8.6`**, passed explicitly.
- **Migration collisions** — settled. `core` is at `0018_compliancecontrol_controlframework_and_more`
  (0.21); 0.19 lives in `tenants`. A 0.20 test lane should generate **no** migration.
- **0.19 and 0.21 overlapped existing registers** and both were resolved by stating the boundary, not
  by re-declaring (L36): 0.19 used `UsageQuota` as the ceiling half against `tenants.UsageRecord`'s
  consumption half; 0.21 refused to add a `ComplianceFramework` because 0.8's `RegulatoryFramework`
  already answers that question.
- **0.18 inherited three deferred 0.17 bullets** — centralized log aggregation, distributed tracing /
  true APM, and capacity quota. Those remain declined, stated in `LIVE_LINKS["0.17"]`'s comments.
- **The real risk now is documentation drift, not code.** This plan was wrong twice in three days
  (0.17 landed without a close-out; 0.19–0.21 landed and nothing recorded it), and `build-state.json`
  never saw the 0.19/0.20/0.21 runs at all. **When a sub-module lands, update the docs in the same
  sitting** — Phase 7 is not optional bookkeeping, it is the only thing that keeps the next reader from
  rebuilding a finished sub-module.
- **Dirty tree** — resolved. The dirt on 2026-09-28 is 0.20's own Phase 6 work
  (`apps/core/tests/conftest.py` + two untracked files), not another session's. Finish it.
