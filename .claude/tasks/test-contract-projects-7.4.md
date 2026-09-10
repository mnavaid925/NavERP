# Test contract — Projects 7.4 Cost & Budget Management (`apps/projects`)

**Phase 6, step 1 (fixture layer).** The four test modules (`test_cost_models.py` →
`test_cost_forms.py` → `test_cost_views.py` → `test_cost_security.py`, written by steps 2–5)
import the `cost_*` block appended to `apps/projects/tests/conftest.py` (commit `a73e4022`).
Model/form/view behaviour is pinned by the build contract
`.claude/tasks/contract-projects-7.4.md` (§3–§9) — **this file pins the fixture names and the
computed EVM figures**; where a number below disagrees with a re-derivation, this file wins
(it was computed from the as-built properties in `apps/projects/models/CostManagement/`).

### Naming rule (mandatory — same as 7.1/7.2/7.3)

* test functions `test_cost_*`; module-level helpers `_cost_*` / `_COST_*`
* conftest fixtures `cost_*` (root-conftest names excepted); never import another lane's
  *fixtures* (`projectinitiation_*` / `planning_*` / `resource_*`); DO import their factory
  functions where they fit
* conftest is owned by step 1 alone — steps 2–5 must not edit it. Pull factories directly:

```python
from apps.projects.tests.conftest import (
    COST_PAGE_SIZE,
    _cost_today, _cost_revision, _cost_control_account, _cost_budget_line, _cost_expense,
    _cost_fill_revisions, _cost_fill_lines, _cost_fill_expenses,
)
```

`COST_PAGE_SIZE = 15` (`crud_list` default) — a pagination test needs 16 rows.

---

## 1. Factories (construct + `.save()` → BVR-/CCA-/PBL-/PEX- numbers mint; NEVER `bulk_create`)

| helper | signature | notes |
|---|---|---|
| `_cost_revision` | `(tenant, project, no=0, status="draft", activate=False, **kw)` | `no` = `revision_no`, **UNIQUE per (tenant, project)** — lifecycle fixtures occupy 0–5 on project_a, fills start at 10. `activate=True` sets `activated_at=now()` and defaults `status="approved"` (explicit `status=`/`activated_at=` kwargs still win). `currency` defaults None — pass `cost_currency` |
| `_cost_control_account` | `(tenant, project, code, **kw)` | `code` UNIQUE per (tenant, project). Defaults `status="active"`, `percent_complete=0`, `contingency=0`, no anchor. Runs `clean()` — a mis-anchored call raises at build time |
| `_cost_budget_line` | `(tenant, revision, project, category="labor", amount="100.00", **kw)` | `amount` str or Decimal; runs `clean()` (revision/wbs/CA same-project). Lines on the ACTIVE revision move `bac` |
| `_cost_expense` | `(tenant, project, control_account, entry_type="actual", amount="50.00", status="draft", **kw)` | `control_account` required non-null; `entry_date=today` (required column); runs `clean()`. Only POSTED `actual`/`accrual` → `ac`; POSTED `commitment` → `committed` |
| `_cost_fill_revisions` | `(tenant, project, count, start_no=10, **kw)` | distinct nos ≥ 10, titles "Backlog revision NN" |
| `_cost_fill_lines` | `(tenant, revision, project, count, **kw)` | 100.00 each, cycling the 7 categories → `category_totals` deterministic |
| `_cost_fill_expenses` | `(tenant, project, control_account, count, **kw)` | DRAFT (burns nothing — EVM-safe), one day apart, "Backlog expense NN" |

To test a `clean()` refusal (cross-project wbs/CA/revision), build the malformed row with the
model directly — the factories deliberately raise on it instead of seeding bad data.

---

## 2. Fixture inventory (all function-scoped)

**Root conftest reuse (never redefine):** `tenant_a` `tenant_b` `admin_user` `member_user`
`admin_b` `client_a` `client_b` `member_client`.

**Spine:** `cost_currency` (global USD, get_or_create — L29; same row as 7.1's) ·
`cost_gl_account_a`/`cost_gl_account_b` (expense GLAccounts; crafted-FK value for B) ·
`cost_party_a` (tenant A vendor)/`cost_party_b` (crafted vendor FK) · `cost_project_a` (ACTIVE
host, window today−30..today+150)/`cost_project_b` (DRAFT host — window starts today+30, so an
unanchored CA there has PV fraction 0) · `cost_wbs_node_a` (work package planned today−4..today+4
→ **PV fraction exactly 0.5**)/`cost_wbs_node_b`.

**Actors/clients:** `cost_member` (= `member_user`; 403 on admin-gated verbs, runs
`bvr_submit`/`pex_post`/CRUD) · `cost_member_b` (tenant B non-admin — log in with a fresh
`Client()` in-test, as 7.1 does) · `cost_tenantless_user`/`cost_tenantless_client` (creates
redirect `dashboard:home`, registers empty) · `cost_anon_client` (302 → login) ·
`cost_admin_client` (= `client_a`; admin happy paths AND every IDOR-404 — the role gate runs
before `get_object_or_404`) · `cost_member_client` (= `member_client`) · `cost_csrf_client`
(POST without token → 403). Tenant-B ADMIN requests: root `client_b`.

**BudgetRevision (project_a, distinct `revision_no` 0–5):**
`cost_revision_activated` (no 0, approved + `activated_at` now−1d — THE baseline;
`amount_delta` 0.00; locked) · `cost_revision_pending` (no 1, `requested_at` only —
approve/reject happy path) · `cost_revision_approved` (no 3, approved NOT activated — the only
`bvr_activate` happy path; locked; excluded from `active_revision` until then) ·
`cost_revision_draft` (no 2 — `bvr_submit` happy path; edit/delete OPEN) ·
`cost_revision_rejected` (no 4, `decision_notes` set; NOT locked — edit is still OPEN on it;
reject answers "already") · `cost_revision_superseded` (no 5, `activated_at` now−9d KEPT as
history — the shape `bvr_activate` leaves behind; locked; never in `active_revision`) ·
`cost_revision_b` (project_b, draft).

**CostControlAccount:** `cost_control_account_a` (code "CA-1.0", anchored to
`cost_wbs_node_a`, `percent_complete=50.00`, `contingency=25.00`, active) ·
`cost_control_account_b` (code "CA-B.1", unanchored, planning, no lines/expenses — the
all-zero/None edge).

**ProjectBudgetLine:** `cost_budget_line_a` (300.00 labor on the ACTIVATED revision → CA_a +
wbs_a — makes `bac` 300.00; parent locked → `pbl_edit`/`pbl_delete` REFUSE it, I1 ruling) ·
`cost_budget_line_draft` (100.00 material on the draft revision — the pbl edit/delete happy
path; never moves bac). No `cost_budget_line_b` — for a tenant-B line build one inline:
`_cost_budget_line(tenant_b, cost_revision_b, cost_project_b)`.

**ProjectExpense (control_account_a unless stated):** `cost_expense_posted` (100.00 actual,
today, vendor+GL+currency, `source_number="PO-00042"` — the only default row in `ac`;
`pex_void` happy path; edit/delete refuse) · `cost_expense_draft` (50.00 actual — `pex_post`
happy path AND pex edit/delete happy path) · `cost_expense_void` (75.00 actual, today−2 — stays
visible, counts nothing) · `cost_expense_b` (60.00 draft, tenant B).

---

## 3. THE EVM TABLE — assert these, do not re-derive

Two columns because fixtures are independent (a test instantiates only what its signature
requests). **A** = `cost_control_account_a` + `cost_budget_line_a` only (no expense fixtures);
**B** = full default set (+ `cost_expense_posted`; draft/void never count).

| metric | A (no posted expense) | B (full default set) |
|---|---|---|
| `bac` | 300.00 | 300.00 |
| `bac_with_contingency` | 325.00 | 325.00 |
| `ev` (300 × 50%) | 150.00 | 150.00 |
| `pv` (300 × 4/8) | 150.00 | 150.00 |
| `ac` | 0.00 | 100.00 |
| `committed` | 0.00 | 0.00 |
| `available` | 300.00 | 200.00 |
| `cv` | 150.00 | 50.00 |
| `sv` | 0.00 | 0.00 |
| `cpi` | **None** (ac == 0) | 1.50 |
| `spi` | 1.00 | 1.00 |
| `eac` (cpi None → fallback BAC) | 300.00 | 200.00 |
| `etc` | 300.00 | 100.00 |
| `tcpi` ((bac−ev)/(bac−ac)) | 0.50 | 0.75 |
| `vac` | 0.00 | 100.00 |
| `health` | `{"state": "under", "badge": "badge-green"}` | same |

`cost_control_account_b` (any signature): every money figure 0.00, `cpi`/`spi`/`tcpi` **None**,
`eac` 0.00 (fallback over bac 0), `health` still under/badge-green — the zero-rows edge.

`amount_delta` (baseline total = 300.00 **iff both** `cost_revision_activated` AND
`cost_budget_line_a` are in the signature; otherwise the project has no baseline → baseline 0):

| fixture | with baseline | without |
|---|---|---|
| `cost_revision_activated` | 0.00 (self-compare) | 0.00 |
| `cost_revision_draft` | **−200.00** (its 100 − 300) | +100.00 (its own line vs 0) |
| `cost_revision_pending` | −300.00 | 0.00 |
| `cost_revision_approved` | −300.00 | 0.00 |
| `cost_revision_rejected` | −300.00 | 0.00 |
| `cost_revision_superseded` | −300.00 | 0.00 |
| `cost_revision_b` | 0.00 (project_b never has a baseline) | 0.00 |

The 0.5 PV fraction holds only while the test runs on ONE local day (L16 — same assumption as
every lane; `cost_wbs_node_a`'s window derives from `_cost_today()`).

---

## 4. Mutation matrix — a verb on a shared fixture moves the pinned figures

`bac`/`ac`/`committed`/`active_revision` are `cached_property` — **re-fetch the CA
(`CostControlAccount.objects.get(pk=ca.pk)`) before re-reading metrics after any mutation.**

| verb on fixture | effect |
|---|---|
| `bvr_submit(cost_revision_draft)` | → pending + `requested_at`; EVM unchanged |
| `bvr_approve(cost_revision_pending)` | → approved + decided stamps; EVM unchanged (not activated) |
| `bvr_reject(cost_revision_pending)` | → rejected + `decision_notes`; EVM unchanged |
| `bvr_activate(cost_revision_approved)` | approved row becomes THE baseline; `cost_revision_activated` (if pulled) → superseded. NEW CA_a: bac 0.00, ev 0.00, pv 0.00, ac UNCHANGED, available −100.00, cpi 0.00, health **over/badge-red**; new baseline `amount_delta` 0.00 |
| `pex_post(cost_expense_draft)` | ac 150.00, cpi 1.00 (NOT watch — exactly 1.00), available 150.00, cv 0.00, eac 300.00, etc 150.00, tcpi 1.00, vac 0.00, health under |
| `pex_void(cost_expense_posted)` | ac 0.00 → column-A values (cpi None, eac 300.00, tcpi 0.50, vac 0.00) |
| `pbl_edit`/`pbl_delete` on `cost_budget_line_a` | REFUSED (parent `is_locked`) — figures safe |
| `pbl_edit`/`pbl_delete` on `cost_budget_line_draft` | allowed — bac unaffected |

Edit-lock rows: BudgetRevision refuses edit/delete on approved/activated/superseded (draft,
pending, **rejected** stay open — rejected is NOT locked); ProjectExpense refuses edit/delete on
posted/void. GET on every verb and delete route → 405.

**Health-band recipes** (only "under" ships as a fixture; build the others with the factories on
a line-300 active revision): **over/red** — posted actual 400.00 → available −100.00 (beats any
cpi), or `percent_complete=Decimal("10.00")` (ev 30) + posted 100.00 → cpi 0.30; **watch/amber**
— `percent_complete=Decimal("47.50")` (ev 142.50) + posted actual 150.00 → cpi exactly 0.95 →
NOT over (strict `< 0.95`) → watch. `cpi is None` can go over only via `available < 0`.
Committed: `_cost_expense(..., entry_type="commitment", amount="40.00", status="posted")` →
`committed` 40.00, `available` = 300 − 40 − ac.

---

## 5. Reminders that have bitten this repo

* **Numbers are creation-order dependent** — assert prefix + shape (`^BVR-\d{5}$` etc.), never a
  hardcoded number. Per tenant, per model (tenant B reads BVR-00001 too).
* **L16** — dates from `timezone.localdate()`/`timezone.now()` only (`_cost_today()`).
* **L11/L9** — junk enum/int GET params → 200 default page; a valid-but-FOREIGN pk filter
  (`?project=<B pk>`) → 200 EMPTY; `?page=abc` → page 1; page 2 needs `COST_PAGE_SIZE + 1` rows.
* **L35** — absent prerequisites are REFUSED, not fallen through: approve on a draft, activate
  on pending/rejected, submit on pending, post on posted, void on draft.
* **403 vs 404 by actor**: IDOR-404s via `cost_admin_client`; a member must 403 (admin-gated)
  before any lookup — never claim a member 404 on `bvr_approve`/`bvr_reject`/`bvr_activate`/
  `pex_void`. Tenant-B member (`cost_member_b`) on a tenant-A pk → 404 (scope, not role).
* **Cross-tenant FK POSTs**: the narrowed queryset refuses first — assert the FIELD has an
  error, never `_reject_foreign`'s wording (unreachable second layer here). Crafted values:
  `cost_project_b`, `cost_gl_account_b`, `cost_party_b`, `cost_wbs_node_b`, `cost_revision_b`,
  `cost_control_account_b`.
* `currency` is the one unscoped FK (global table, L29) — never hand it to `_reject_foreign`
  and never assert a tenant error on it.
* **L20/L22** — `status` (BVR/PEX), `requested_at`/`decided_*`/`activated_at`/`decision_notes`/
  `created_by` must not be form fields; assert a smuggled POST value changes nothing.
* Amounts: pull MORE line/expense fixtures in one test and bac/ac move — when mixing factories
  with the lifecycle fixtures, compute expectations from the pulled rows (bac = active
  revision's lines mapped to the CA; ac = posted actual+accrual).
* Tests never touch `management/commands/seed_projects.py`; peers own
  `test_planning_*`/`test_resource_*` files — 7.4 imports nothing from them.
