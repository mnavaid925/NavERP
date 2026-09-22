# Plan 1 — Finish Module 0 (System Admin & Security): **6** unbuilt sub-modules (0.16–0.21)

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Status:** 🟨 **8 of the 14 built since authoring; 6 remain**
**Scope:** `core` + `accounts` + `tenants` + `dashboard` · **Effort:** large — 6 remaining `/next-module` runs

> **Re-verified 2026-09-22 against `LIVE_LINKS` (authoritative).** The original header said "14 unbuilt";
> **eight of those fourteen are now live**: **0.4, 0.6, 0.8, 0.10, 0.11, 0.12, 0.13, 0.15**.
> Module 0 is now **15 of 21 built (0.1–0.15)** and the remaining work is exactly **0.16–0.21**.
> Steps 0 and 2 of this plan are also **DONE** (reconcile file committed; `core/SKILL.md` written).
> The table in Step 1 is kept below with per-row status so the finished ones are not rebuilt.

---

## Goal

Module 0 is the only module in the 0–7.13 range that is materially unfinished. At authoring it was
**7 of 21 sub-modules live**; it is now **15 of 21 (0.1–0.15)**. Every other module in the range is
complete against the catalog. This plan closes the last six: **0.16–0.21**.

## Why it is the biggest item

This is **not one task — it is 14.** Each unbuilt sub-module is a full Module Creation Sequence run
(Phases 0–7 of `.claude/CLAUDE.md`): research → todo → build → 6 serial reviewers → `code-fixer` →
tests → docs. Do them **one at a time, strictly serially**, exactly like 7.1–7.15 were done.

## Hard rules (do not skip)

1. **Always pass the sub-module explicitly:** `/next-module 0.4`, never bare `/next-module`.
   With no argument the skill auto-detects "the module currently in progress" — which today is
   **module 7**, and a concurrent session is already mid-build on **7.16**. A bare run would hand you
   7.16, not module 0. (Verified: `.claude/skills/next-module/SKILL.md:148-156` picks the lowest `N.M`
   with no `LIVE_LINKS` entry of the module in progress.)
2. **`git status` first, every run.** A dirty tree at session start is not yours (L45). As of authoring
   there are 3 modified files and 1 untracked file that belong to other sessions — see Plan 2.
   Never commit them.
3. **Agree the migration number** with any other live session before generating one (L43).
4. **One file per commit. Never `git push`.**
5. Run python as `venv\Scripts\python.exe` — Django is not on system python.

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

## Step 1 — The remaining sub-modules, in this order

Numeric order is the default (predictable, matches the skill's lowest-numbered rule). The **two marked
★ were foundations other sub-modules consume** — both are now built. Do not interleave: finish one
before starting the next.

| # | sub-module | title | status 2026-09-22 |
|---|---|---|---|
| 1 | 0.4 | Authentication & Single Sign-On (SSO) | ✅ **built** — MFA/TOTP, SAML/OIDC, password policy, session mgmt |
| 2 | 0.6 | Application Module Administration & Access Scope | ✅ **built** — the 13-bullet one |
| 3 | 0.8 | Privacy & Data Protection | ✅ **built** — consent, DSAR, retention, PII discovery |
| 4 | 0.10 ★ | System Configuration & Settings | ✅ **built** — settings, feature flags, numbering & sequences, business calendar |
| 5 | 0.11 ★ | Workflow & Approval Administration | ✅ **built** |
| 6 | 0.12 | Notification & Communication Management | ✅ **built** |
| 7 | 0.13 | Integration & API Management | ✅ **built** — API keys, webhooks/event bus, connectors |
| 8 | 0.15 | Localization & Regional Settings | ✅ **built** — language packs, RTL, multi-currency |
| 9 | **0.16** | **Backup, Recovery & Data Lifecycle** | ⬜ **OPEN — next** |
| 10 | **0.17** | **Monitoring, Logging & Observability** | ⬜ **OPEN** |
| 11 | **0.18** | **Threat Protection & Security Operations** | ⬜ **OPEN** |
| 12 | **0.19** | **License & Subscription Administration** | ⬜ **OPEN** |
| 13 | **0.20** | **Admin Console & System Operations** | ⬜ **OPEN** |
| 14 | **0.21** | **Compliance, Governance & Risk** | ⬜ **OPEN** |

### Notes carried forward for the six still open

- **0.16** Backup schedules, restore, lifecycle/archival. `core.DisposalRecord` already exists as evidence
  of a real disposal — read it before declaring anything about retention.
- **0.17** Health checks, metrics, log aggregation, alerting. `core.AuditLog` and `core.BusinessRuleLog`
  already exist; this is the *observability* layer over them, not a second log store.
- **0.18** WAF/rate limiting, threat detection, incident response, vulnerability mgmt.
- **0.19** Entitlements, seat counting, renewals. Overlaps `tenants.Subscription` /
  `tenants.SubscriptionInvoice` (0.1) — state the boundary, do not re-declare.
- **0.20** Ops console, jobs, maintenance mode, cache control. **0.6/0.20 are the natural home for console
  surfaces**; if you put models in `dashboard` it becomes a real app and needs a test lane (Plan 5 Item A
  added one, so the lane now exists).
- **0.21** Control library, risk register, evidence, policy attestation. Overlaps procurement 6.17's
  `ComplianceScreening`/`AuditSeal` and 4.12 — reconcile before building, do not re-declare (L36).

### Which app does each go in?

Module 0 spans four apps. Decide per sub-module from the catalog bullets and the existing pattern:

- `tenants` — 0.1 (built), 0.7 key management, 0.19 licensing → tenant/commercial concerns.
- `accounts` — 0.2/0.3 (built), **0.4 SSO** → identity and auth.
- `core` — 0.9/0.14 (built), **0.10, 0.11, 0.12, 0.13, 0.15, 0.16, 0.17, 0.18, 0.20, 0.21** → platform.
- `dashboard` — currently only `apps.py`, `urls.py`, `views.py` (**no models, no tests**). **0.6/0.20**
  are the natural home for console/admin surfaces; if you put models there it becomes a real app and
  needs a test lane (see Plan 5).

`0.6`'s 13 bullets are per-module access scopes for modules that mostly do not exist yet (8–23). Build it
against the modules that **are** live (1–7) and make the rest explicit no-ops, or defer the bullet —
either is fine, but say which in the contract.

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
- [ ] All 21 sub-modules have a `LIVE_LINKS["N.M"]` entry — **15 of 21 today; 0.16–0.21 outstanding.**
- [ ] `temp/audit_integrity.py` passes all 6 checks (module 0 shows 21 built, not 7).
- [x] `.claude/skills/core/SKILL.md` exists with an accurate As-built line — `4ce6b4a2`.
- [x] `README.md` module-0 row updated — now `🟦 15 of 21 sub-modules built (0.1–0.15)`, landed by
      Plan 4 (`4b088965`); `NavERP.md` by `1962ae89`.
- [ ] `.claude/tasks/todo.md` has a close-out note per sub-module — 0.1–0.15 done; 0.16–0.21 outstanding.

## Risks

- **Auto-detect will fight you.** Bare `/next-module` picks module 7 (a concurrent session is now on
  **7.18**, not 7.16). Always pass `0.N`.
- **Migration collisions** with the concurrent session — agree the number first (L43).
- **0.19 and 0.21 overlap existing registers.** Procurement 6.17 owns `ComplianceScreening`/`AuditSeal`;
  `tenants` owns the subscription spine. The house rule is *never re-declare a sibling's spine* (L36) —
  state the boundary in the contract, as 7.6 did with `DeliverableInspection`.
- **Dirty tree.** Four modified `templates/projects/reporting/*.html` currently belong to the 7.18
  session. Leave them alone; never commit them (L45).
