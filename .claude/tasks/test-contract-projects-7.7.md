# Test contract — Projects 7.7 Scope & Requirements Management (`apps/projects`)

**Phase 6, step 1 (fixture layer).** The four test modules (`test_scope_models.py` →
`test_scope_forms.py` → `test_scope_views.py` → `test_scope_security.py`, written by steps 2–5)
import the `scope_*` block appended to `apps/projects/tests/conftest.py`. Model/form/view behaviour
is pinned by the build contract `.claude/tasks/contract-projects-7.7.md` (§2–§5) **as amended by the
post-fix state** — the review `.claude/tasks/review-projects-7.7.md` found C1/C2/C3/I1–I8 and the
fix pass landed before this file was written, so **this contract pins the POST-FIX code**, not the
review's "before" picture.

**This file pins the fixture names and the computed `scope_matrix` figures**; where a number below
disagrees with a re-derivation, **this file wins** (it was computed by hand from the as-built
properties in `apps/projects/models/ScopeRequirements/` and the view in
`apps/projects/views/ScopeRequirements/ScopeMatrix.py`).

### Post-fix deltas this contract depends on

* **C1 fixed** — `ScopeItem.STATUS_CHOICES` is now `open/validated/realized/retired/**violated**`
  and `is_locked = status in ("realized", "retired", "violated")`. `is_open` stays
  `open|validated`. The `violated` state **can exist** and its rows are **locked**.
* **C2 fixed** — all eight admin-gated verbs were reordered to
  `@login_required` → `@require_POST` → `@tenant_admin_required`, so a **member GET → 405** (not
  403) and a **member POST → 403**. The gates table in §3 reflects the post-fix order.
* **I3 fixed** — `sci_retire` refuses a non-`is_open` row (`realized` included) with
  `messages.error`; an already-`retired` row still returns the informational no-op.
* **I2 fixed** — `Requirement.elicitation_method` is `max_length=20` (the contract now matches the
  code). `document_analysis` is 17 characters.
* **C3 fixed** — the seeder's two negative `schedule_impact_days` values are now positive; that is
  the seeder's business, not the fixtures'. Tests never touch the seeder.

### Naming rule (mandatory — same as 7.1/7.2/7.3/7.4)

* test functions `test_scope_*`; module-level helpers `_scope_*` / `_SCOPE_*`
* conftest fixtures `scope_*` (root-conftest names excepted); never import another lane's
  *fixtures* (`projectinitiation_*` / `planning_*` / `resource_*` / `cost_*`); DO import their
  **factory functions** where they fit
* `conftest.py` is owned by **step 1 alone** — steps 2–5 must not edit it. Pull the factories and
  the page-size constant directly:

```python
from apps.projects.tests.conftest import (
    SCOPE_PAGE_SIZE,
    _scope_today, _scope_requirement, _scope_item, _scope_change, _scope_verification,
    _scope_fill_requirements, _scope_fill_items, _scope_fill_changes,
)
```

`SCOPE_PAGE_SIZE = 15` (`crud_list`'s default `per_page`). Every 7.7 register uses the default, so a
pagination test needs **`SCOPE_PAGE_SIZE + 1` = 16 rows** for a second page.

---

## 1. Factories (construct + `.save()` → REQ-/SCI-/SCR-/SVR- numbers mint; NEVER `bulk_create`)

| helper | signature | notes |
|---|---|---|
| `_scope_requirement` | `(tenant, project, status="draft", **kw)` | Defaults: `title="Requirement NN"`, `description` filled, `requirement_type="functional"`, `priority="must"`, `wbs_node=None` (**untraced** by default — the coverage gap!), `parent=None`, `owner=None`, `source_party=None`, `acceptance_criteria=""`, `version="1.0"`, `verification_method="test"`, `elicitation_method="interview"`, no stamps. Runs `clean()` so a mis-parented / cross-project `wbs_node` or `parent` raises at build time |
| `_scope_item` | `(tenant, project, item_type="assumption", status="open", **kw)` | Defaults: `statement="Scope item NN"`, `description=""`, `impact_area="scope"`, `requirement=None`, `owner=None`, `identified_date=_scope_today()`, `review_date=None` (never overdue), `outcome=""`, no `closed_at`. Runs `clean()` |
| `_scope_change` | `(tenant, project, status="draft", **kw)` | Defaults: `title="Scope change NN"`, `description` filled, `justification=""`, `source="internal"`, `priority="medium"`, `schedule_impact_days=None`, `cost_impact=Decimal("0")`, `quality_impact="none"`, `quality_note=""`, `requirement=None`, `risk=None`, no stamps. Runs `clean()` (requirement/risk same-project) |
| `_scope_verification` | `(tenant, project, acceptance_status="pending", **kw)` | Defaults: `deliverable="Deliverable NN"`, `method="inspection"`, `result="pass"`, `wbs_node=None`, `requirement=None`, `inspected_by=None`, `inspection_date=_scope_today()`, `findings=""`, no decision stamps. Runs `clean()` |
| `_scope_fill_requirements` | `(tenant, project, count, **kw)` | distinct titles `"Backlog requirement NN"`, all `draft`/untraced/`must` |
| `_scope_fill_items` | `(tenant, project, count, **kw)` | distinct statements `"Backlog item NN"`, `assumption`/`open` |
| `_scope_fill_changes` | `(tenant, project, count, **kw)` | distinct titles `"Backlog change NN"`, `draft`, zero impact (never in the creep totals) |
| `_scope_today` | `()` | `timezone.localdate()` — the **same basis** `ScopeItem.is_review_overdue` and the matrix's overdue counter read (L16) |

**Fill safety:** the fills are deliberately *inert* — untraced requirements, open items with no
review date, impact-free draft changes — so a pagination/search test that pulls 16 rows does **not**
move the pinned matrix figures of §4 unless it also pulls the matrix fixtures (which use distinct
titles that never collide with the `Backlog *` names).

To test a `clean()` refusal (cross-project `wbs_node`/`parent`/`requirement`/`risk`), build the
malformed row with the **model directly** — the factories deliberately raise on it instead of
seeding bad data (the `_cost_budget_line` precedent).

---

## 2. Fixture inventory (all function-scoped)

**Root conftest reuse (never redefine):** `tenant_a` `tenant_b` `admin_user` `member_user` `admin_b`
`client_a` `client_b` `member_client`.

**Core spine:** `scope_party_a` (tenant A org Party — `Requirement.source_party` and the change/
verification filter dropdown) · `scope_party_b` (crafted-FK tenant B Party) · `scope_project_a`
(tenant A **active** host, window today−30 .. today+150) · `scope_project_b` (tenant B twin) ·
`scope_wbs_a` / `scope_wbs_b` (a `ProjectTask` `node_type="work_package"` — the traceability target
and the matrix's column) · `scope_wbs_a2` (a **second** tenant A work package so the matrix has ≥2
columns).

> **`core.Document` is not used by 7.7.** No 7.7 model, form or view references it — the requirement
> narrative is free text and the deliverable is a string. **There is no `scope_document_a`
> fixture**; a test that wants a document builds one inline. (Recorded so a later reader does not
> assume an omission.)

**Actors/clients:** `scope_admin_client` (= root `client_a`; every admin happy path AND every
IDOR-404) · `scope_member_client` (= root `member_client`) · `scope_tenantless_client` (logs in a
`tenant=None` user; registers render empty, creates redirect to `dashboard:home`) ·
`scope_anon_client` (302 → login) · `scope_csrf_client` (`enforce_csrf_checks=True`, POST without a
token → 403). Tenant-B **admin** requests: root `client_b`.

**Requirement lifecycle (project_a unless `_b`):**
`scope_requirement_draft` · `scope_requirement_submitted` · `scope_requirement_approved` ·
`scope_requirement_implemented` · `scope_requirement_verified` · `scope_requirement_rejected` ·
`scope_requirement_b`.

**ScopeItem lifecycle:** `scope_item_open` · `scope_item_validated` · `scope_item_realized` ·
`scope_item_violated` · `scope_item_b`.

**ScopeChangeRequest lifecycle:** `scope_change_draft` · `scope_change_submitted` ·
`scope_change_under_review` · `scope_change_approved` · `scope_change_rejected` ·
`scope_change_implemented` · `scope_change_high_impact` (crosses `HIGH_COST`) ·
`scope_change_sub_threshold` (crosses none) · `scope_change_b`.

**ScopeVerification lifecycle:** `scope_verification_pending` · `scope_verification_accepted` ·
`scope_verification_rejected` · `scope_verification_waived` · `scope_verification_b`.

**The deterministic matrix set (a project of its own — see §4):** `scope_matrix_project_a` ·
`scope_wbs_m1` · `scope_wbs_m2` · `scope_matrix_req_traced_approved` ·
`scope_matrix_req_untraced_draft` · `scope_matrix_req_traced_implemented_verified` ·
`scope_matrix_req_untraced_approved` · `scope_matrix_ver_accepted` · `scope_matrix_ver_pending` ·
`scope_matrix_ver_orphan` · `scope_matrix_change_m1` · `scope_matrix_change_m2` ·
`scope_matrix_change_m3` · `scope_matrix_change_low` · `scope_matrix_item_in_scope` ·
`scope_matrix_item_out_of_scope` · `scope_matrix_item_constraint_validated_overdue` ·
`scope_matrix_item_assumption` · `scope_matrix_item_dependency_realized`.

---

## 3. GATES — the source state each verb accepts, and its role gate (POST-FIX code)

`previous = <field>` is captured **before** mutation; the audit row carries
`changes={"verb", "from", "to"}`. `AuditLog.action` is `varchar(10)` — the action literal is column 4.

| verb | allowed source state(s) | role gate | action literal | writes |
|---|---|---|---|---|
| `req_submit` | `draft`, `rejected` | login only | `submit` | `status="submitted"`, clears `rejection_reason` |
| `req_approve` | `submitted` | **admin** | `approve` | `status="approved"`, `approved_by`/`approved_at` |
| `req_reject` | `submitted` | **admin** (body: `RequirementRejectionForm.reason` required) | `reject` | `status="rejected"`, `rejection_reason`, clears the approval pair |
| `req_implement` | `approved` | login only | `implement` | `status="implemented"` |
| `req_verify` | `implemented` | **admin** (body: `RequirementVerificationForm.note` optional) | `verify` | `status="verified"`, `verified_by`/`verified_at`, note |
| `sci_validate` | `open` | login only | `submit` (verb `validate` in `changes`) | `status="validated"` |
| `sci_realize` | `open`, `validated` (`is_open`) | login only (I9 adjudication pending) | `realize` | `status="realized"`, `outcome`, `closed_at` |
| `sci_retire` | `open`, `validated` (`is_open`) — **`realized` REFUSED (I3 fix)** | login only | `retire` | `status="retired"`, `outcome`, `closed_at` |
| `scr_submit` | `draft` | login only | `submit` | `status="submitted"` |
| `scr_review` | `submitted` | **admin** | `review` | `status="under_review"` |
| `scr_approve` | `submitted`, `under_review` | **admin** | `approve` | `status="approved"`, `decided_by`/`decided_at` |
| `scr_reject` | `submitted`, `under_review` | **admin** (body: `ChangeRejectionForm.decision_note` required) | `reject` | `status="rejected"`, `decision_note`, `decided_by`/`decided_at` |
| `scr_implement` | `approved` | login only | `implement` | `status="implemented"`, `implemented_at` |
| `svr_accept` | `pending` | login only | `accept` | `acceptance_status="accepted"`, `accepted_by`/`accepted_at` |
| `svr_reject` | `pending` | **admin** (body: non-blank `note` required) | `reject` | `acceptance_status="rejected"`, `decision_note`, stamps |
| `svr_waive` | `pending` | **admin** | `waive` | `acceptance_status="waived"`, `accepted_by`/`accepted_at` |

**Method + role matrix (post-C2):** every verb is `@login_required @require_POST` with the role
check **innermost**.

| actor | GET on any verb | POST on a login-only verb (right state) | POST on an admin-gated verb (right state) |
|---|---|---|---|
| anonymous | 302 → login | 302 → login | 302 → login |
| member | **405** | 302, state moves | **403, row untouched, no audit row** |
| admin | **405** | 302, state moves | 302, state moves |
| tenant-B member on a tenant-A pk | — | **404** (scope, before role) | **404** (scope, before role) |

**Edit/delete locks** (`is_locked` on each model): Requirement locks at `verified`; ScopeItem locks
at `realized|retired|violated`; ScopeChangeRequest locks at `implemented`; ScopeVerification locks
when `acceptance_status != "pending"`. A locked row refuses bothedit and delete with
`messages.error` + redirect to detail.

**Second-POST refusals (L35):** every verb answers a wrong-source-state POST with `messages.error`,
writes nothing and never 500s. The already-done case is either `error` (req_approve, scr_*, svr_*)
or `info` (sci_retire's already-retired, svr_accept's already-decided) — assert the **state
unchanged**, not the message level.

---

## 4. THE `scope_matrix` TABLE — assert these, do not re-derive

All figures below are hand-derived from `views/ScopeRequirements/ScopeMatrix.py` scoped with
`?project=<scope_matrix_project_a.pk>`. **Zero other rows exist in that tenant for that project** —
the matrix fixtures build a dedicated project so the numbers are auditable (the `risk_sim_project` /
`risk_baseline` precedent). The other lifecycle fixtures live on `scope_project_a` and are **out of
scope** for the `?project=` query.

### 4.1 The fixture set and its columns

`scope_matrix_project_a` is a tenant A **active** project. Its work packages, ordered
`sequence, id`: `scope_wbs_m1` (sequence 0) then `scope_wbs_m2` (sequence 1) →
`work_packages` = `[m1, m2]`, **`wp_total` = 2**.

The four requirements on it (all on `scope_matrix_project_a`):

| fixture | `requirement_type` | `priority` | `wbs_node` | `status` |
|---|---|---|---|---|
| `scope_matrix_req_traced_approved` | `functional` | `must` | **m1** | `approved` |
| `scope_matrix_req_untraced_draft` | `functional` | `should` | **None** | `draft` |
| `scope_matrix_req_traced_implemented_verified` | `technical` | `must` | **m2** | `verified` |
| `scope_matrix_req_untraced_approved` | `business` | `could` | **None** | `approved` |

The three verifications on it:

| fixture | `requirement` | `acceptance_status` |
|---|---|---|
| `scope_matrix_ver_accepted` | `…_traced_implemented_verified` | `accepted` |
| `scope_matrix_ver_pending` | `…_traced_implemented_verified` | `pending` |
| `scope_matrix_ver_orphan` | **None** (no requirement) | `accepted` |

### 4.2 `coverage` (one aggregate over the 4 requirements)

`total` = 4 · `traced` = 2 (`wbs_node` set: the approved and the verified) · `untraced` =
`total − traced` = **2** · `verified` = count of `status="verified"` = **1** ·
`coverage_pct` = `round(2 / 4 × 100, 1)` = **50.0**.

### 4.3 `matrix_rows` — cell shape and per-row counts

`matrix_rows` is ordered `-created_at, -id` (newest first), so in build order the LAST-built
requirement is row 1. Each row is a dict:

```python
{"requirement": <Requirement>, "cells": [bool, bool], "traced": bool,
 "verification_count": int, "verified_count": int}
```

| row (in build order) | `cells` | `traced` | `verification_count` | `verified_count` |
|---|---|---|---|---|
| `…_req_traced_approved` (m1) | `[True, False]` | True | 0 | 0 |
| `…_req_untraced_draft` | `[False, False]` | False | 0 | 0 |
| `…_req_traced_implemented_verified` (m2) | `[False, True]` | True | **2** | **1** |
| `…_req_untraced_approved` | `[False, False]` | False | 0 | 0 |

`cells[i]` is `requirement.wbs_node_id == work_packages[i].pk`. `verification_count` counts **all**
verifications naming the requirement (the 2 on the verified row); `verified_count` counts only those
whose `acceptance_status ∈ (accepted, waived)` (1 — the accepted one; the pending one does not
count). `scope_matrix_ver_orphan` has no requirement, so it contributes to **no** row.

### 4.4 `untraced` and `unverified` (each capped at `GAP_LIMIT = 25`)

* `untraced` = the 2 untraced requirements, ordered `-created_at, -id`. **len 2.**
* `unverified` = requirements with `status ∈ (approved, implemented)` = the two `approved` rows
  (the `draft` and the `verified` are excluded). **len 2.** (The verified row is `status="verified"`,
  which is NOT in the tuple — that is the point of the panel.)

### 4.5 `creep_rows`, `creep_max`, `creep`

The creep loop reads changes with `status ∈ (approved, implemented)` and buckets them by
`decided_at or created_at` (the month of the stamp). Fixtures are built with an explicit
`decided_at=` so the month is deterministic. Four changes on `scope_matrix_project_a`:

| fixture | `status` | `decided_at` (month) | `cost_impact` | `schedule_impact_days` | `quality_impact` | high-impact? |
|---|---|---|---|---|---|---|
| `scope_matrix_change_m1` | `approved` | today − 70d | `40000.00` | 0 | `none` | no (40k < 50k) |
| `scope_matrix_change_m2` | `implemented` | today − 40d | `60000.00` | 0 | `none` | **yes** (≥ 50k) |
| `scope_matrix_change_m3` | `approved` | today − 10d | `10000.00` | **12** | `low` | **yes** (≥ 10 days) |
| `scope_matrix_change_low` | `draft` | — | `999999.00` | 99 | `high` | (in the register, **never** in creep) |

The three in-creep rows are **70 / 40 / 10 days ago** — which land in **three distinct calendar
months only if the test runs at least 10 days away from a month boundary on the early side and 40/70
aside**. **KNOWN FRAGILITY:** a run whose `today` is within 3 days of the 1st collapses two of the
three buckets. The fixtures therefore stamp `decided_at` from a **fixed month-anchored helper**:
each fixture uses the **first day of a distinct month** computed as
`today.replace(day=1)` minus 0/1/2 months — see the fixture docstrings. That makes the three
periods deterministic regardless of the run date:

| period (YYYY-MM) | label | `count` | `cost_total` | `schedule_days` | `bar_pct` |
|---|---|---|---|---|---|
| `P0` = 2 months before this month | e.g. `Jul 2026` | 1 | `40000.00` | 0 | 66.7 |
| `P1` = 1 month before this month | e.g. `Aug 2026` | 1 | `60000.00` | 0 | **100.0** |
| `P2` = this month | e.g. `Sep 2026` | 1 | `10000.00` | 12 | 16.7 |

Ordered by period ascending (`sorted` on the `(year, month)` key). `creep_max` =
`max(cost_total)` = **`60000.00`**; `bar_pct` = `round(cost_total / creep_max × 100, 1)` →
`round(40000/60000×100,1)` = **66.7**; `60000/60000` = **100.0**; `round(10000/60000×100,1)` =
**16.7**. (`bar_pct` is a **`Decimal`** — it is `round()` of the `q2()`-quantized `cost_total`
divided by the `Decimal` `creep_max`, so assert `str(row["bar_pct"]) == "66.7"` or compare against
`Decimal("66.7")`, not the float `66.7`. The 0-safe branch below returns the plain **float** `0.0`.)

`creep` = `{"count": 3, "cost_total": q2(40000+60000+10000) = 110000.00, "schedule_days": 12,
"high_impact_count": 2}` (m2 and m3; m1 misses all three thresholds).

**`scope_matrix_change_low`** is a `draft` with `cost_impact=999999.00` and `quality_impact="high"`
— it is the proof that the creep panel reads **status**, not impact: it never appears in
`creep_rows` and never moves `creep_max`, yet it IS in the `scr_list` register and IS in the
`?high_impact=1` lens (which filters on the columns, not status).

### 4.6 `type_rows` and `priority_rows`

`_rows()` restores a zero row for every choice, in `CHOICES` order:

`type_rows` (order `functional, non_functional, business, technical, regulatory, interface`):
`functional` **2**, `non_functional` 0, `business` **1**, `technical` **1**, `regulatory` 0,
`interface` 0.

`priority_rows` (order `must, should, could, wont`): `must` **2**, `should` **1**, `could` **1**,
`wont` 0.

### 4.7 `scope_summary`

Five ScopeItems on `scope_matrix_project_a`:

| fixture | `item_type` | `status` | `review_date` |
|---|---|---|---|
| `scope_matrix_item_in_scope` | `in_scope` | `open` | None |
| `scope_matrix_item_out_of_scope` | `out_of_scope` | `open` | None |
| `scope_matrix_item_constraint_validated_overdue` | `constraint` | `validated` | today − 3 |
| `scope_matrix_item_assumption` | `assumption` | `open` | None |
| `scope_matrix_item_dependency_realized` | `dependency` | `realized` | None |

`items` = **5** (all item types) · `boundaries` = `in_scope` + `out_of_scope` = **2** ·
`constraints` = **1** · `assumptions` = **1** · `open_items` = items with
`status ∈ (open, validated)` = 4 (the `realized` one is excluded) · `overdue_items` = live rows with
`review_date < today` = **1** (the validated constraint).

### 4.8 The 0-safe cases (a second, EMPTY project)

Scoped to a project with **no** rows of any kind (build one inline with `_projectinitiation_project`
and no matrix fixtures), the page must render 200 with: `coverage` = all-zero and
`coverage_pct == 0.0` (never a ZeroDivisionError), `matrix_rows == []`, `untraced == []`,
`unverified == []`, `creep_rows == []`, **`creep_max == 0`** and therefore every
`creep` figure 0/`0.00`, `bar_pct` unreachable — **the 0-safe branch is `if creep_max else 0.0`,
so a row with `cost_total == 0` still gets `bar_pct == 0.0`**. `type_rows`/`priority_rows` are the
full choice lists with every count 0. `scope_summary` is all-zero.

`?project=` edge cases: a foreign tenant-B pk → 200 with **no** tenant-B data (`project` is None →
tenant-wide); `?project=abc` → 200 tenant-wide (L11, `as_db_int`); no `?project=` at all →
tenant-wide and `work_packages == []` / `wp_total == 0`.

---

## 5. The updated `ScopeItem` status set (post-C1 — pin it)

```python
STATUS_CHOICES = [("open", …), ("validated", …), ("realized", …), ("retired", …), ("violated", …)]
is_open   == status in ("open", "validated")
is_locked == status in ("realized", "retired", "violated")
```

`max_length=12` fits `violated` (8) / `validated` (9). A `violated` row **is creatable** (the value
is in the choices, so `crud_list`'s enum allow-list keeps it), **is locked** (edit/delete refuse),
and **counts as neither `open_items` nor a boundary**. There is no verb that writes `violated` —
like 7.5's `on_hold`, it is vocabulary a test hand-builds with the factory.

---

## 6. Reminders that have bitten this repo

* **Numbers are creation-order dependent** — assert prefix + shape (`^REQ-\d{5}$` etc.), never a
  hardcoded number. Per tenant, per model (tenant B reads `REQ-00001` too).
* **L16** — dates from `timezone.localdate()`/`timezone.now()` only (`_scope_today()`). Never
  `datetime.date.today()`.
* **L11/L9** — junk enum/int GET params → 200 default page; a valid-but-FOREIGN pk filter
  (`?project=<B pk>`) → 200 EMPTY; `?page=abc` → page 1; page 2 needs `SCOPE_PAGE_SIZE + 1` rows.
* **L35** — absent prerequisites are REFUSED, not fallen through: approve on a draft, verify on an
  approved, realize on a realized, submit on a submitted, implement on a submitted, review on a
  draft, accept on a decided inspection.
* **403 vs 404 by actor**: IDOR-404s via `scope_admin_client`; a member must **403 (POST) / 405
  (GET)** before any lookup on the eight admin-gated verbs — never claim a member 404 there.
  Tenant-B member on a tenant-A pk → 404 (scope, not role).
* **Cross-tenant FK POSTs**: the narrowed queryset refuses first — assert the FIELD has an error,
  never `_reject_foreign`'s wording (unreachable second layer here). Crafted values:
  `scope_project_b`, `scope_party_b`, `scope_wbs_b`, `scope_requirement_b`, `scope_item_b`,
  `scope_change_b`, `scope_verification_b`.
* **L20/L22** — every `status`/`acceptance_status`, the approval pair, the decision pair, the
  acceptance pair, `closed_at`, `implemented_at`, `rejection_reason`, `decision_note`,
  `verification_note`, `outcome`, `created_by`, `number`, `tenant` must not be form fields; assert a
  smuggled POST value changes nothing on all four `*_edit` routes.
* **`scope_change_high_impact`** crosses `HIGH_COST` (cost 60000.00 ≥ 50000); the **companion
  boundary** is `scope_change_sub_threshold` (cost 49999.99, 9 days, `quality_impact="medium"`) —
  exactly one unit below every threshold, so `is_high_impact` is **False** while
  `?high_impact=1` excludes it. Never assert `is_high_impact` on the default `_scope_change` rows
  (cost 0 / no days / `none`).
* Tests never touch `management/commands/seed_projects.py`; peers own
  `test_{models,forms,views,security}` files of other sub-modules — 7.7 imports nothing from them.
