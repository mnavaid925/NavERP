# Review findings — procurement 6.18 Inventory & Warehouse Integration

**Review scope (path globs, NOT a commit range).** Four sessions committed to `main` in this one
working tree, so `56ae21a9..HEAD` interleaves 6.16/6.17/6.19 with ours and would send reviewers at
code they have no contract for. Reviewers are scoped to:

```
apps/procurement/models/InventoryWarehouseIntegration/**    (4 files)
apps/procurement/forms/InventoryWarehouseIntegration/**     (4)
apps/procurement/views/InventoryWarehouseIntegration/**     (7)
apps/procurement/urls/InventoryWarehouseIntegration/**      (7)
templates/procurement/inventorywarehouse/**                 (12)
```

Plus this sub-module's blocks **only** inside the shared files (`apps/core/navigation.py`,
`apps/procurement/{admin.py,management/commands/seed_procurement.py}`, the four app-level
`__init__.py`), isolated with:

```bash
git log --format='%H%x09%s' -- <file> | grep -E $'\t[a-z]+\\(procurement\\): 6\\.18 ' | cut -f1 \
  | xargs -I{} git show {} -- <file>
```

**Pre-flight before trusting any glob: expand it and count.** An under-matching glob makes a
reviewer report *clean* because it read nothing, which is the answer we are hoping for and
therefore the one we would believe. Expected 4/4/7/7/12.

Contract: `.claude/tasks/contract-procurement-6.18.md`. Plan: `.claude/tasks/todo.md` § 6.18-*.

---

## Phase 3.5 — smoke gate (`qa-smoke-tester`)

183 checks, 178 pass. Ledger boundary, IDOR, release semantics and every contract context key
verified clean. Two findings.

### S1 — `stock_position` silently empties the whole board on a pk of 0

**File:** `apps/procurement/views/InventoryWarehouseIntegration/StockPosition.py:220-222` (and the
`vendor_id` row filter below it).

`?item=0`, `?location=0` and `?vendor=0` each take the board from 18 rows to **0**.
`apps.core.crud.as_db_int()` deliberately passes `0` through (it is decimal and in range), and this
page then tests only `is not None`:

```python
if item_id is not None:      moves = moves.filter(item_id=item_id)
if location_id is not None:  moves = moves.filter(location_id=location_id)
```

An `AutoField` starts at 1, so `filter(item_id=0)` matches nothing and empties the register.

**Why this is a defect and not a judgement call:** contract § 6 rule 6 requires junk GET params to
narrow nothing; `apps/core/crud.py:135-141` documents this exact bug class (L11, third case) and
guards it; and **the two sibling derived pages in this same sub-module already do it correctly** —
`ReceiptBinMap.py:181-191` and `CountAccuracy.py:205-210` resolve the id to an object first and
filter only `if selected_location is not None`. One page of three diverging is drift, not a
trade-off. The fix shape already exists in-module.

**Verified:** `grep -n "is not None" StockPosition.py` → lines 220, 222 confirm the pattern;
sibling pattern confirmed at `ReceiptBinMap.py:181-191`.

### S2 — `receipt_bin_map` bins column is blank on every seeded receipt (upstream data gap)

**Not a 6.18 code defect — the join is proven correct.** Linking acme's 3 putaway tasks to
`GRN-00001` inside a rolled-back transaction made the page render bin `WH-MAIN-A1` qty `5.0000`,
`unputaway` 19→14 and `putaway_css` `badge-red`→`badge-amber`. The corrected contract join
(GRN → `PutawayTask.goods_receipt` → `to_location`) works.

The gap is upstream: **`PutawayTask.goods_receipt` is NULL on 8 of 8 rows DB-wide** (verified
directly). `apps/scm/management/commands/seed_scm.py` (~469, ~545) creates putaway tasks without
it and nothing else writes it, though `PutawayTaskForm.Meta.fields` does expose the field.
Consequence: the page's headline column is blank in every demo workspace and `stats` reads
`in_staging: 2, fully_putaway: 0`. Secondarily `grn.location` is None on both acme GRNs, so
`staging_location` renders blank too.

**Routing:** the fix belongs in `seed_scm.py`, a shared file owned by another module and another
session's build. **Out of 6.18's scope — do not fix it here.** Phase 5 should record it as
`[~] skipped — upstream` and it should be raised with whoever owns SCM seeding.

### Cleared during the sweep (recorded so they are not re-raised)

- `replenishmentrun_detail` "missing SKU note" — harness bug: the assertion used
  `StockPosition.SKU_MATCH_NOTE`, but `Runs.py:65` defines its own distinct text, rendered
  unconditionally at `replenishmentrun/detail.html:151`. PASS after correction.
- `?q=<script>` returning 0 rows — a search term that matches nothing correctly matches nothing;
  200 on all pages and the payload comes back HTML-escaped on all six.
- `tenant=None` + create → 302 — `apps/core/crud.py:174` deliberately refuses a tenant-less
  creator. Never a 500.

---

## Phase 4 — reviewers

Six reviewers run **one after another**, each appending here as it reports:
`code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester`
→ `security-reviewer`.

_(appended below as each reports; IDs assigned and sorted Critical → Important → Minor once all
six are in)_

### Pass 1 — `code-reviewer`

Scope counts verified 4/4/7/7/12 before starting. Verdict: needs rework — two Critical, one
Important, three Minor. **Both Criticals independently reproduced by the main session** before
being recorded here.

#### R1-C1 — `replenishmentrun_delete` has no status guard: a released run can be destroyed

**File:** `apps/procurement/views/InventoryWarehouseIntegration/Runs.py:234`

It calls `crud_delete` directly with nothing in front of it. A direct POST to
`/procurement/replenishment-runs/<pk>/delete/` therefore deletes a **released** run, and
`ReplenishmentSuggestion.run` is `on_delete=CASCADE` (`Runs.py:645`) — so every suggestion line goes
with it, destroying the only record of which `scm.PurchaseRequisition` came from which proposal,
while the requisition rows survive orphaned.

The protection is **only in the templates, which state the opposite of the truth**:
`replenishmentrun/detail.html:268` wraps the danger zone in `{% if can_generate %}` and line 272
promises *"If the run has already been released, delete is not offered at all"*;
`replenishmentrun/list.html:146-149` asserts *"the view refuses both anyway"*. It does not.

**Confirmed by the main session** — `sed -n '232,236p' Runs.py` shows a bare `crud_delete`, while
the sibling `MaterialIssues.py:218-227` re-checks `obj.can_edit`, messages, and redirects before
delegating. The model already refuses this transition for `cancel()` (`Runs.py:595-599`), so the
rule exists and only the delete path skips it.

**Fix:** mirror `materialissue_delete` — guard on `obj.can_generate`, `messages.error`, redirect to
detail. Then the two template comments become true again.

#### R1-C2 — `count_accuracy` 500s on a half-filled date range (reachable from the filter bar)

**File:** `apps/procurement/views/InventoryWarehouseIntegration/CountAccuracy.py:180-182`

The fallback is `if date_from is None and date_to is None:`, so supplying **one** date leaves the
other `None`, and `:208` / `:231-232` then pass `None` into `scheduled_date__gte` / `__lte`.

**Reproduced by the main session against the live database as `admin_acme`:**

```
?date_from=2026-01-01&date_to=    -> ValueError: Cannot use None as a query value
?date_from=&date_to=2026-09-01    -> ValueError: Cannot use None as a query value
?date_from=2026-01-01&date_to=2026-09-01 -> 200
(no params)                        -> 200
```

Not merely a hand-edited-URL case: `count_accuracy.html:91-95` renders two independent
`<input type="date">` fields, so clearing one and pressing Apply submits `date_to=` (empty →
`None`). The in-module sibling already handles it correctly — `ReceiptBinMap.py:193-196` applies
each bound behind its own `is not None`.

**Fix:** resolve the missing half from the window, or apply each bound conditionally as
`ReceiptBinMap` does.

#### R1-I1 — `seed_procurement --flush` cannot regenerate 6.18 data

**File:** `apps/procurement/management/commands/seed_procurement.py:290`

The `--flush` block ends at `ProcurementDocument.objects.all().delete()` with no 6.18 deletes. All
three sub-blocks of `_seed_inventory_warehouse` are `exists()`-guarded (`:3669`, `:3744`, `:3789`),
so `--flush` leaves every 6.18 row in place and the re-seed prints "already present, skipping" —
the demo data can never be regenerated. This file has been patched for exactly this twice before
(`808dfccc` for 6.19, `4e9a09de` for 6.13) and the 6.13/6.15/6.16/6.19 blocks each carry a comment
saying so.

**Fix:** append children-first before line 291 — `MaterialIssueLine`, `MaterialIssue`,
`ReplenishmentSuggestion`, `ReplenishmentRun`, `ReplenishmentPolicy`.

#### R1-M1 — editing a *proposed* run's scope leaves stale lines with no prompt to re-generate

`Runs.py:222` — `replenishmentrun_edit` gates on `can_generate` (draft **or** proposed), so
re-scoping an already-proposed run leaves lines that no longer match the header's location/ABC
filter, and `crud_edit` redirects to the list with a bare "Updated successfully". `release()` then
stamps a justification naming the *new* scope onto lines computed for the *old* one
(`Runs.py:543-546`). **Fix:** on a proposed run redirect to detail with a `messages.warning` naming
Generate.

#### R1-M2 — `stock_position` truncation copy says the opposite of what the view computes

`templates/.../stock_position.html:111` claims the counters "cover those rather than the whole
workspace", but `StockPosition.py:323-329` computes `stats` **before** both the view slice and the
`ROW_CAP` slice — so they cover *more* rows than are rendered. The "(capped at {{ row_cap }})"
suffix at `:49` also sits beside a number that is not capped. **Fix:** reword to say the counters
cover the full filtered population while the table shows the first `row_cap`.

#### R1-M3 — `count_accuracy` program roll-up truncates silently

`CountAccuracy.py:317` — `programs[:ROW_CAP]` drops rows without setting `truncated`, unlike the two
roll-ups above it which both use the `[:ROW_CAP + 1]` probe (`:264`, `:291`). **Fix:** same probe
shape, or say in the card that the schedule table is capped.

#### Verified clean by this pass (recorded so later passes need not redo it)

Every `{% url %}` name and Python `reverse()` target resolves across ~30 cross-app targets in
`scm`, `inventory`, `accounting` and `procurement`; every context key in all six views matches its
template's reads; all four package `__init__.py` re-export blocks complete (5 models / 5 forms /
27 views / urls included as one unit); migration `0027` carries all five tables with indexes and
both `unique_together`s; every tenant-scoped queryset filters `tenant=request.tenant`, and both
tenant-less child models reach it through `run__tenant` / `issue__tenant`; every form excludes
`tenant`, `number`, `status` and every `editable=False` stamp; `@require_POST` +
`@tenant_admin_required` sit on `release` and `post` as contracted.

### Pass 2 — `explorer` (spine integrity + structural fit)

Scope counts re-verified 4/4/7/7/12. Three new findings, all structural. **Both Importants
independently reproduced by the main session.**

#### R2-I1 — `stock_position` re-derives the run's trigger, drops both policy toggles, and its own comment claims otherwise

**File:** `apps/procurement/views/InventoryWarehouseIntegration/StockPosition.py:276-283`

```python
ordered   = on_order.get(sku, ZERO)                 # ungated
requested = open_requisitions.get(sku, ZERO)        # ungated
# "The RUN's trigger, verbatim (Runs.py:403-409)"  <- the comment
below_point = reorder_point is not None and (on_hand + ordered + requested) <= reorder_point
```

versus the actual trigger at `models/…/Runs.py:400-401`:

```python
ordered   = on_order.get(sku, ZERO) if shaping.include_on_order else ZERO
requested = open_requisitions.get(sku, ZERO) if shaping.include_open_requisitions else ZERO
```

**Confirmed by the main session** — both lines read side by side; the toggles are absent and the
comment asserts they are not.

**Consequence.** For a policy with `include_on_order=False` (point 100, on-hand 50, on-order 80):
the run computes supply 50 and proposes a line; the board computes 130 and shows the row healthy.
The buyer sees nothing below point, then the run proposes lines from nowhere — precisely the
two-definitions failure the page's own docstring says it exists to prevent. `stats.below_point`
and both the `below_point` and `no_cover` tabs undercount with it.

**Why it is invisible today:** both flags default `True` and the seeder sets them `True`, so it
surfaces only once someone uses the field the form already exposes
(`forms/…/Policies.py:59`) and the detail template already documents
(`replenishmentpolicy/detail.html:140-144`).

**Fix.** `policies.get(key)` is already resolved seven lines below at `:289` — move it above the
calculation, use the `_UNCONFIGURED = ReplenishmentPolicy()` sentinel `Runs.py:387` already
defines, and gate a separate trigger pair. Leave the **displayed** `on_order` /
`open_requisition_qty` columns ungated: those report what exists, not what is netted off.

#### R2-I2 — a pure domain rule lives in the views layer and the model imports upward to reach it

**File:** `apps/procurement/models/InventoryWarehouseIntegration/Runs.py:326`

```python
from apps.procurement.views.InventoryWarehouseIntegration.Policies import _effective_numbers
```

**Confirmed by the main session:** `grep -rn "from apps\.[a-z]*\.views" apps/*/models/` returns
**exactly one hit, repo-wide — this one.**

`_effective_numbers(policy, rule)` (`views/…/Policies.py:112-156`) takes no request, touches no
template and renders nothing. It is pure override-vs-fallback arithmetic whose first parameter is
the policy — a `ReplenishmentPolicy` method in disguise, parked in the presentation layer because
the detail page happened to need it first. The *goal* (one written-down definition so the detail
page and the run cannot disagree) is right; the placement inverts the layering to achieve it.

**Consequences.** `generate()` transitively drags the views + forms + `apps.core.crud` import graph
in at call time; promoting that import to module scope — the obvious future tidy-up, since it is
the only deferred import in `generate()` not justified by app-registry ordering — would create a
circular import. Breaks CLAUDE.md Backend Package Structure rule 5.

**Fix (one move, no behaviour change).** Move it to `models/…/Policies.py` as
`ReplenishmentPolicy.effective_numbers(self, rule)`; `views/…/Policies.py:247` becomes
`obj.effective_numbers(rule)`; delete the upward import. Every import in the sub-module is then
downward.

**Same root, other direction (noted, not a separate finding):** `StockPosition.py:63-65` imports
private `_on_order_map` / `_open_requisition_map` / `_pair_map` from a *models* module — the only
cross-layer private import in the app. Directionally fine and better than a third copy, but with
R2-I2 it shows 6.18 never settled on a home for its shared pure functions.

#### R2-M1 — the board offers "Raise requisition" on rows the run refuses to buy

`StockPosition.py:310` sets `raise_requisition_url` unconditionally, and `below_point` ignores
`source_method` entirely. `Runs.py:392-393` skips any policy whose `source_method` is not in
`REQUISITIONABLE_SOURCE_METHODS` — a discipline `models/…/Policies.py:63-68` explicitly tells
callers to read rather than hard-code. A `transfer`- or `manufacture`-sourced item therefore
renders as below point with a Buy button, inviting exactly the purchase the model prevents.

**Note: this is contract drift as much as code drift** — § 5 pins `raise_requisition_url` with no
condition. Fix the contract line too, or the next builder reintroduces it.

#### Verified clean by this pass — stated explicitly

1. **Spine reuse (L36) — clean.** Zero redeclarations of `Item`/`Location`/`StockMove`/`LotSerial`/
   `ReorderRule`/`PutawayTask`/`CycleCountTask`/`GoodsReceiptNote`/`PurchaseRequisition`/
   `StockAdjustment`; no Bin/Zone model. All 26 FKs target the spine **by string**. A grep for any
   `StockMove` write across the whole of `apps/procurement` returns **nothing** — contract § 6 rule
   1 holds app-wide, not merely in 6.18.
2. **Derived-vs-stored — clean, and the distinction is drawn correctly.** No stored aggregate
   columns in `0027`. The 11 snapshot columns are a legitimate point-in-time record (the
   `CycleCountTaskLine.expected_quantity` precedent), never a second source of truth — every live
   figure is re-read from `StockMove`.
3. **Availability formula genuinely reused verbatim** — character-identical at
   `StockPosition.py:274`, `Runs.py:434` and `inventory/…/StockLevels.py:124`. 6.18 mirrors
   `_on_order_map` locally rather than making a third copy, per contract § 6 rule 4.
4. **Package layout — clean.** 5 models / 5 forms / 27 views all re-exported (verified
   programmatically, zero missing); 27 patterns, six unique literal first segments; every import
   absolute.
5. **Structural fit — it belongs.** Template tree matches the four peers exactly;
   `TenantUniqueMixin` first in MRO on the three header forms and correctly absent from the two
   child forms whose models carry no `tenant` column; colour-named badges only.

### Pass 3 — `frontend-reviewer`

12 templates confirmed read. One Critical, four Important, six Minor. **Critical reproduced by the
main session.**

#### R3-C1 — the `count_accuracy` window dropdown is permanently inert, and R1-C2 is the only exit

**Files:** `templates/…/count_accuracy.html:91,94` with `CountAccuracy.py:180-182`.

The template renders the **resolved** dates back into the inputs
(`value="{{ date_from|date:'Y-m-d' }}"`), so after the first render both boxes are populated and
every subsequent submit carries them — at which point `if date_from is None and date_to is None:`
is False and the window is never applied. Selecting "Last 30 days" / "Last 180 days" / "Last 12
months" **changes nothing**: the dropdown shows the new label as selected, the prose prints the old
dates, and every figure stays on the first window.

**These two Criticals trap the user between them.** The only way to escape the inert window is to
clear a box — which is exactly R1-C2 and 500s. Fix both together.

**Fix (template-only):** pre-fill from the **raw GET** value (`{{ request.GET.date_from }}`) so the
boxes are empty unless the user typed a date, and let the prose keep printing the resolved window.
Also: the `aria-label`s say "Counted from/to" but the view filters `scheduled_date__gte/lte` — and
these inputs have no visible `<label>`, so the aria-label is the only name a screen reader gets.

#### R3-I1 — `replenishmentpolicy/detail.html:56` inactive-rule caveat is backwards

Says an inactive rule's figures "are what a run would read". `generate()` opens with
`filter(..., is_active=True)` — an inactive rule is **never read by a run at all**. A buyer told
otherwise expects the next run to propose against these numbers and gets silence.

#### R3-I2 — the "no surprise at Post" promise fails for two lines of the same item

`materialissue/detail.html:162` promises a shortfall is visible before Post. But
`MaterialIssues.py:164` flags **per line**, while `post()` sums demand **per item across the
document**. There is no `unique_together` on `(issue, item)` and the model comment says duplicates
are expected. Two lines of 6 against 10 on hand: neither row shows the `badge-red Short` chip, and
Post is refused with "only 10 available … cannot issue 12". **Fix view-side so the copy can
stand** — mirror `post()`'s per-item aggregation in the detail view.

#### R3-I3 — `stock_position.html:197` "can never disagree" is a guarantee the code does not make

The same drift as R2-I1, seen from the template. Wording must admit that a policy which turns off
either netting toggle, or sources by transfer/manufacture, makes its run disagree **on purpose**.

#### R3-I4 — recording a decision throws the buyer back to page 1

`replenishmentrun/detail.html:219` posts no `page`, and `replenishmentsuggestion_decide` redirects
without one. Lines page at 25 and a run caps at 500, so a buyer working page 8 is bounced to page 1
after **every** Save. Fix: hidden `page` field + append it on redirect.

#### R3-M1…M6 (condensed)

- `count_accuracy.html:101` — "so the ranking is intact" is true of the item table but not the
  location table, which caps on `-variance_lines` and only then re-sorts by accuracy; a 0%-accurate
  location can be cut in favour of a 95% one. Bites only above 500 counted locations.
- `count_accuracy.html:99` vs `:53` — "Cancelled counts are left out" is unqualified, but
  `tasks_total` counts them. Say "left out of the accuracy figures below".
- `materialissue/detail.html:102` vs `:75` — page reads "Document value 900.00" and two cards down
  "valued at -900.00" for the same document (`value_impact()` is signed, `total_value` is not).
  Explain inline rather than hiding the sign.
- `replenishmentpolicy/detail.html:165` — renders "the last **0** suggestions" when empty.
- `stock_position.html:175` — the only icon-only control in the 12 files with `title` but no
  `aria-label`.
- `replenishmentrun/detail.html:121` — "one per vendor, all draft" is a state claim that goes stale
  the moment one is submitted; "raised as drafts" reads correctly forever.

#### Verified clean by this pass

Zero `{#` leaks across all 12 files (every note uses `{% comment %}`). Every `badge-*` is
colour-named and every `stat-icon` variant valid — **including the ones injected from Python**
(`SOURCE_CSS`, `TRIGGER_CSS`, `STATUS_CSS`, `DECISION_CSS`, `MOVEMENT_CSS`, `PUTAWAY_TASK_CSS`,
`_CAPACITY_CSS_BANDS`, `_ACCURACY_BANDS`); no semantic variant anywhere (L33). All 20 `{% url %}`
names resolve. No `|slugify`; all six pk dropdowns use `|stringformat:"d"` and re-select on reload.
All four paginated pages delegate to the shared partial and replay every GET param except `page`.
13/13 tables in `.table-wrap`; every empty-state `colspan` matches its header count; 12/12 extend
`base.html`.

**Called out as done well:** `receipt_bin_map.html:106` is the sentence `stock_position.html:111`
should have been — same 500-row cap, same need to explain it, and its version is *provably* true of
the view's `order_by(...)[:ROW_CAP+1]` + stats-over-capped-pks pipeline. Written the same week as
R1-M2, against a harder pipeline, and correct.

### Pass 4 — `security-reviewer`

Scope counts re-verified 4/4/7/7/12 plus the 6.18 blocks in `admin.py` and `seed_procurement.py`.
**No Critical or High.** Two Medium, two Low. Both Mediums reproduced by the main session.

#### R4-I1 — `ReplenishmentPolicy` CRUD is login-only, but the config steers real spend

**File:** `views/…/Policies.py:255-273`

Any authenticated tenant member — not only a tenant admin — can create or rewrite the workspace's
replenishment configuration, and `release()` stamps it verbatim onto `scm.PurchaseRequisition`
rows: `default_org_unit` → `org_unit_id`, `default_budget` → `budget_id`, `default_gl_account` →
the line's GL, `preferred_vendor` → the grouping vendor, and the rounding fields → the quantity. So
a non-admin can pre-load the supplier, cost centre, budget and GL coding of a document the
admin-gated Release then raises **in the admin's name**.

**Confirmed by the main session, and the precedent is the model's own:** `Policies.py:26-29` names
`ReceiptTolerancePolicy` as what it is modelled on — and that one carries `@tenant_admin_required`
on all three verbs (`ReceiptTolerances.py:213,223,233`), as does `RoutingRule`. Only the
*configuration master* is ungated here; `release` and `post` are correctly gated.

**Fix:** add `@tenant_admin_required` to `replenishmentpolicy_create` / `_edit` / `_delete`.

**Pattern-clone (L28):** the same gap exists on the sibling config master `BudgetMapping`
(`views/BudgetCostManagement/BudgetMappings.py:85/91/98`) — **6.15's, not ours.** Route it, do not
fix it here.

#### R4-I2 — deleting a policy silently rewrites the provenance of *released* suggestions

**File:** `views/…/Policies.py:268-272` with `models/…/Runs.py:655-659`

`replenishmentpolicy_delete` calls `crud_delete` with no reference guard, and
`ReplenishmentSuggestion.policy` is **`on_delete=SET_NULL`** (confirmed). One POST nulls the FK on
every historical suggestion — including lines already released into real requisitions — after
which `replenishmentrun/detail.html:177-179` prints the affirmatively false *"no policy — plain
defaults, no rounding"* beside a line whose `raw_suggested_qty != suggested_qty` proves it **was**
rounded. The `AuditLog` records the policy delete and none of the N rows it mutated.

Same class as R1-C1 (a destructive verb with no guard against erasing evidence for an
already-committed document), different entity — a sibling, not a re-report.

**Fix:** refuse when `obj.suggestions.filter(requisition__isnull=False).exists()`, and steer to
deactivation — which the model already recommends at `Policies.py:152-155`.

#### R4-M1 — `post()`'s `bulk_create` bypasses SCM's own `unit_cost` cap

`models/…/MaterialIssues.py:361-371`. `bulk_create` skips `full_clean()`, so
`StockAdjustmentLine.unit_cost`'s `MaxValueValidator(999999.9999)` never runs — and SCM's comment
on that validator describes *exactly* this path: *"a tenant member drafts the line and a
tenant-admin posts it, so an absurd cost would otherwise ride a bulk approval straight into the
valuation report"*. `MaterialIssueLine.unit_cost` is `Decimal(14,4)`, ceiling ~10^10. Clamp at the
boundary.

#### R4-M2 — the two admin-gated buttons are rendered for every member (guaranteed 403)

`materialissue/detail.html:60-64` (Post) and `replenishmentrun/detail.html:53-57` (Release) gate
only on the status flags, so a non-admin sees the button, confirms the dialog and gets
`PermissionDenied`. `grep -rn "is_tenant_admin" templates/procurement/inventorywarehouse/` returns
nothing, against 178 templates repo-wide that do gate. Narrow `can_post` / `can_release` with an
`_is_admin(request)` term — the decorator stays the enforcement, the flag stops offering it.

#### Verified clean — and the two properties most at risk are enforced *by construction*

- **Cross-tenant IDOR — clean and structural, not accidental.** All three tenant-less-child routes
  resolve through the parent with all three legs present (`pk=line_id, run__pk=pk,
  run__tenant=request.tenant`, and the equivalents). `materialissueline_add` sets `issue` from the
  URL and omits it from `Meta.fields`, so it cannot be POSTed. All ~35 querysets scope by tenant or
  through a parent; `.objects.all()` appears nowhere in the sub-module.
- **Mass assignment — clean.** All five forms use explicit `Meta.fields`; every system stamp and
  all eleven snapshot columns are absent, with `editable=False` behind them and `readonly_fields`
  in admin.
- **FK re-checks complete, not partial** — every FK on every form appears in its `_reject_foreign`
  list (6/6, 5/5, 3/3, 1/1, 1/1), with each model's `clean()` as a third layer.
- **Numeric input — clean.** No `int()`/`Decimal()`/`float()` on request data anywhere; all pks via
  `as_db_int`, dates via a guarded `_as_date`, `int(selected_window)` fenced by membership.
- **XSS — clean on all 12 templates including the three dict-row pages.** Zero `|safe`,
  `mark_safe`, `autoescape off`, `innerHTML`. Every dynamic `class="badge {{ … }}"` value comes
  from a Python constant dict with a `badge-muted` default.
- **CSRF — 18 POST forms, 18 tokens.** No `@csrf_exempt`.
- **Ledger boundary holds as a security property** — no `StockMove(` anywhere in `apps/procurement`;
  `post()` is the only mint and writes `status="draft"`; `adjustment` is `editable=False`, off every
  form, and read-only in admin; the seeder calls neither `post()` nor `release()`.
- **Audit present on every mutating path.** The one gap is the collateral `SET_NULL` in R4-I2.

*Noted, not filed:* no `ModelAdmin` in the repo scopes `get_queryset` by tenant, so `/admin/` is
cross-tenant by construction — pre-existing across ~100 admin classes, `is_staff` defaults False,
**not a 6.18 regression.**

### Pass 5 — `performance-reviewer`

Told not to re-tread ground two passes had already cleared, and given six measured claims to
attack instead. **Four of the six hold as stated; one is only partly true; one exposed a real
defect.** No N+1 anywhere in the sub-module.

#### R5-I1 — `SalesOrderAllocation` is reached through a 2-table join, so its `(tenant, status)` index is unreachable

`models/…/Runs.py:364` and `views/…/StockPosition.py:232` both filter
`sales_order_line__sales_order__tenant`. But `SalesOrderAllocation` is `TenantOwned` with its own
`tenant` column **and** `scm_soa_tnt_status_idx` on exactly `(tenant, status)`
(`SalesOrderAllocations.py:44`) — **confirmed by the main session.** Measured SQL shows **no tenant
predicate on the allocation table at all**: the planner reads every workspace's
`reserved`/`released` allocations, joins each up through `scm_salesorderline` → `scm_salesorder`,
and discards the rest. At 500k allocations across 50 workspaces one `stock_position` render scans
~500k rows to keep ~10k — on a page any logged-in user can open, and again on every `generate()`.

Self-inconsistent within the same function: the two lines below it (`InventoryReservation`
`Runs.py:372`, `StockStatus` `:375`) both use the direct `tenant_id=` form.

**Fix:** `filter(tenant_id=tenant_id, status__in=…)` at both sites. Identical results, one fewer
join, lands on the index.

**Third site is NOT ours** — inherited verbatim from
`apps/inventory/views/InventoryTrackingControl/StockLevels.py:92`, which has the same defect.
**Route it; do not fix another module's file here.**

#### R5-I2 — `stock_position` applies `ROW_CAP` *after* building every row

`StockPosition.py:224-227` (`combos` — an uncapped GROUP BY over the whole tenant ledger), `:267`
(builds a 17-key dict for **every** pair), `:323-329` (`stats` over all of them), `:339` (cap
finally bites). Query count is flat — which is why the 11× measurement passed — but the *work* is
O(all item×location pairs), not O(page). At 5,000 SKUs × 20 locations with moves on 30% of pairs
that is ~30,000 dicts built to render 25, plus `item_map` loading every `Item` **including
`description`, a `TextField` this page never renders**.

The sibling page in the same sub-module already does it right — `ReceiptBinMap.py:202-204` probes
`[:ROW_CAP + 1]`, sets `truncated`, and builds nothing past the cap. Same constant, same author,
opposite order. **(Third instance of the two-of-three drift pattern.)**

#### R5-I3 — `generate()` materialises every active rule while holding the row lock

`Runs.py:342-349` inside the `atomic()` + `select_for_update()` opened at `:330-333`.
`MAX_SUGGESTIONS = 500` caps the **output**, not the input. The model's own docstring at `:176-178`
names the scenario — *"a workspace with 40,000 rules would render a page nobody can read **and hold
a row lock while it did**"* — and the cap it then introduces does not prevent the second half of
its own sentence. Fix is row *width*: `.only(...)` the nine columns the loop actually reads.

#### R5-M1…M4 (condensed)

- `Runs.py:344` — `select_related("item", "item__uom", "location")` carries **two dead joins**;
  neither `item.uom` nor `location` is read in the loop (traced attribute by attribute). Fold into
  R5-I3's `.only()`.
- `CountAccuracy.py:287-291` — the location roll-up splats `**_ROLLUP_ANNOTATIONS`, dragging a
  `scm_item` join and two aggregates (`value_sum`, `abs_sum`) the template never renders.
- `forms/…/MaterialIssues.py:161-163` — the lot dropdown is unbounded and grows with every goods
  receipt; rebuilt on every `materialissue_detail` render. At 50k available lots that is a 50k-row
  fetch and a 50k-option `<select>` on a page showing ~5 lines.
- `Runs.py:106-107` + `replenishmentrun/detail.html:228-230` — the vendor `<option>` list is
  correct on the *query* side (one QuerySet, `_result_cache` reused) but is **re-rendered inside
  all 25 row forms**: 25 × 500 parties ≈ 12,500 `<option>` elements (~0.5 MB) for a 25-row table.

#### Claim corrections (asked for verification, not restatement)

- **Claim 3 is only 3/5 true.** `received_map` (`ReceiptBinMap.py:208-213`) and `putaway_done_map`
  (`:217-223`) run over the whole 500-pk cap **before** `paginate()`, not over the page — deliberate
  and documented at `:198-201`, because the four stats are specified to cover the capped
  population. Query count genuinely flat; row volume on those two is up to 25× the page. Leave it,
  but the claim as I stated it was stronger than the code.
- **Claim 5 (templates) is clean, and closer than it looks.** Two 1+N traps are avoided *only by
  the exact phrasing chosen*: `materialissue/detail.html:191` renders `{{ line.lot_serial.number }}`
  — had it printed `{{ line.lot_serial }}`, `LotSerial.__str__` resolves `self.item.sku` and
  `_LINE_RELATIONS` does not join `lot_serial__item` → 1+N. `replenishmentrun/detail.html:176`
  renders `{{ line.policy.pk }}` — `{{ line.policy }}` would resolve `item.sku` **and**
  `location.code` → 1+2N on a 25-row page. **Anyone "tidying" either template to print the object
  silently doubles or triples the page's query count.** This is the strongest argument for the
  query-count regression tests below.
- **Claim 6 (indexes) — nothing missing.** All seven of `0027`'s indexes match real query patterns,
  and every upstream table these pages hammer is already covered. The only index problem in the
  sub-module is R5-I1: an index that exists and cannot be reached.
- **Not raised, app-wide by design:** `_run_qs`/`_issue_qs` hand `crud_list` an annotated queryset,
  so `Paginator.count` is a `COUNT(*)` over a GROUP BY subquery. 103 files repo-wide do this;
  changing it here would fork a deliberate `apps/core/crud.py` contract.

#### Requested for Phase 6

Three `django_assert_max_num_queries` regressions, all guarding behaviour that is correct **now**
and would regress silently: `replenishmentrun_detail` ≤ 12 with 30 lines across ≥3 policies/vendors
(catches the `{{ line.policy }}` regression), `materialissue_detail` ≤ 14 with 20 lot-carrying
lines, and `generate()` ≤ 15 with 40 active rules (pins the nine-query claim permanently — a lazy
`rule.item.uom.code` would take it past 40).

---

# CONSOLIDATED FIX LIST

All six passes complete. Deduped, sorted, IDs assigned. **Hand this section to `code-fixer`.**

## Critical — 3

| ID | Source | File | Issue | Status |
|---|---|---|---|---|
| **C1** | R1-C1 | `views/…/Runs.py:234` | `replenishmentrun_delete` has no status guard: a POST deletes a **released** run and CASCADE-destroys every suggestion, orphaning the requisitions it raised. Both templates claim the view refuses this. Mirror `materialissue_delete`. | **[x] fixed** — `fix(procurement): 6.18 C1 - guard replenishmentrun_delete on can_generate` |
| **C2** | R1-C2 | `views/…/CountAccuracy.py:180-182` | Half-filled date range → `ValueError: Cannot use None as a query value` → **500**. Reachable from the filter bar. | **[x] fixed** — `fix(procurement): 6.18 C2 - resolve a half-filled count-accuracy window instead of 500ing` |
| **C3** | R3-C1 | `templates/…/count_accuracy.html:91,94` | Window dropdown **permanently inert** — the resolved dates are rendered back into the inputs, so the `both are None` guard never fires. **Fix with C2: the only escape from C3 is clearing a box, which is C2.** Also fix the two `aria-label`s (say "Counted", filter is `scheduled_date`). | **[x] fixed** — `fix(procurement): 6.18 C3 - pre-fill the count-accuracy date boxes from raw GET, fix the aria-labels` |

## Important — 13

| ID | Source | File | Issue | Status |
|---|---|---|---|---|
| **I1** | S1 | `views/…/StockPosition.py:220-222` | `?item=0` / `?location=0` / `?vendor=0` silently empties the board. Siblings resolve the pk to an object first. | **[x] fixed** — `fix(procurement): 6.18 I1 - resolve the stock-position pk filters to real rows before filtering` |
| **I2** | R2-I1 | `views/…/StockPosition.py:276-283` | Re-derives the run's trigger but **drops both policy toggles**, while the comment claims "verbatim". Board and run disagree once either flag is off. | **[x] fixed** — `fix(procurement): 6.18 I2 - apply the policy netting toggles to the board's below-point trigger` |
| **I3** | R2-I2 | `models/…/Runs.py:326` | The **only model→views import in the repo**. Move `_effective_numbers` down as `ReplenishmentPolicy.effective_numbers()`. | **[x] fixed** — 3 commits: model method, then generate()'s upward import deleted, then the detail call site |
| **I4** | R4-I1 | `views/…/Policies.py:255-273` | Policy CRUD is login-only; the config steers vendor/GL/budget/quantity onto requisitions the admin-gated Release raises. Its own docstring names a precedent that gates all three. | **[x] fixed** — `security(procurement): 6.18 I4+I5 …` + the two policy templates stop offering writes a member cannot perform |
| **I5** | R4-I2 | `views/…/Policies.py:268-272` | Policy delete has no reference guard; `SET_NULL` erases the provenance of **released** suggestions, unaudited. | **[x] fixed** — same view commit; delete refused when any suggestion carries a requisition, steered to deactivation |
| **I6** | R5-I1 | `models/…/Runs.py:364`, `views/…/StockPosition.py:232` | `SalesOrderAllocation` reached via 2-table join; its `(tenant, status)` index unreachable. Two sites (ours only). | **[x] fixed** — both 6.18 sites now `filter(tenant…)` directly (X3 left alone) |
| **I7** | R5-I2 | `views/…/StockPosition.py:224-267,339` | `ROW_CAP` applied after building every row; `item_map` loads a `TextField` never rendered. | **[x] fixed** — `perf(procurement): 6.18 I7 - build the board's presentation keys only for the rows that survive ROW_CAP` |
| **I8** | R5-I3 | `models/…/Runs.py:342-349` | Every active rule materialised **while holding the row lock** — the docstring names this scenario and the cap does not prevent it. `.only()` it. | **[x] fixed** — `perf(procurement): 6.18 I8+M13 - narrow generate()'s rules queryset to the nine columns it reads` |
| **I9** | R3-I1 | `templates/…/replenishmentpolicy/detail.html:56` | Inactive-rule caveat is backwards — runs filter `is_active=True`, so those figures are what a run would **not** read. | **[x] fixed** — `docs(procurement): 6.18 I9 - the inactive-rule caveat said the opposite of what a run does` |
| **I10** | R3-I2 | `views/…/MaterialIssues.py:164` | Shortfall flagged **per line** while `post()` sums **per item**; two lines of one item show no warning then Post refuses. Fix view-side so the copy stands. | **[x] fixed** — view aggregates demand per item as `post()` does; template explains it |
| **I11** | R3-I3 | `templates/…/stock_position.html:197` | "can never disagree" — same drift as I2, from the template. | **[x] fixed** — `docs(procurement): 6.18 I11 - drop the 'can never disagree' guarantee the code does not make` |
| **I12** | R3-I4 | `templates/…/replenishmentrun/detail.html:219` | Decide form posts no `page`; a buyer on page 8 is bounced to page 1 on **every** save. | **[x] fixed** — hidden `page` on every decide form + `_decide_redirect()` echoes it on all four exits |
| **I13** | R1-I1 | `seed_procurement.py:290` | `--flush` misses all five 6.18 tables, so demo data can never be regenerated. This file has been patched for exactly this twice before. | **[x] fixed** — `fix(procurement): 6.18 I13 - flush the 6.18 rows so --flush can actually re-seed them` |

## Minor — 16

| ID | Source | Issue | Status |
|---|---|---|---|
| **M1** | R1-M1 | proposed-run scope edit leaves stale lines with no re-generate prompt | **[x] fixed** — `fix(procurement): 6.18 M1 - send a re-scoped PROPOSED run back to its detail page with a re-generate warning` |
| **M2** | R1-M2 | `stock_position.html:111`/`:49` truncation copy inverted | **[x] fixed** — `docs(procurement): 6.18 M2+M9 - the truncation copy said the counters cover LESS than they do, and label the icon-only requisition button` |
| **M3** | R1-M3 | `CountAccuracy.py:317` program roll-up truncates without setting `truncated` | **[x] fixed** — `perf(procurement): 6.18 M3+M14 - probe the programme roll-up for truncation and stop the location roll-up joining scm_item` |
| **M4** | R2-M1 | board offers "Raise requisition" on transfer/manufacture rows the run refuses — **also fix contract § 5, which pins the key unconditionally** | **[x] fixed** — 3 commits: the view reads `shaping.raises_requisitions`, the template names the source method instead of an empty href, and contract § 5 now pins the key as conditional (+ `source_label`) |
| **M5** | R3-M1 | "ranking is intact" untrue of the location table | **[x] fixed** — `docs(procurement): 6.18 M5+M6 - two window caveats that claimed more than the view does` |
| **M6** | R3-M2 | "cancelled counts left out" unqualified but `tasks_total` counts them | **[x] fixed** — same commit; scoped to "left out of every accuracy figure, still in the counts-in-window tally" |
| **M7** | R3-M3 | signed `value_impact()` vs unsigned `total_value` shown as contradictory figures | **[x] fixed** — `docs(procurement): 6.18 M7 - explain the signed adjustment value instead of leaving it contradicting the document value` |
| **M8** | R3-M4 | "the last **0** suggestions" when empty | **[x] fixed** — `docs(procurement): 6.18 M8 - stop the Recently proposed card announcing 'the last 0 suggestions'` |
| **M9** | R3-M5 | `stock_position.html:175` icon-only control missing `aria-label` | **[x] fixed** — same commit as M2; the label carries the row's SKU so 25 identical buttons are distinguishable |
| **M10** | R3-M6 | "one per vendor, all draft" is a state claim that goes stale | **[x] fixed** — `docs(procurement): 6.18 M10 - 'all draft' is a state claim that goes stale; 'raised as drafts' stays true` |
| **M11** | R4-M1 | `bulk_create` bypasses SCM's `unit_cost` `MaxValueValidator` | **[x] fixed** — `security(procurement): 6.18 M11 - clamp the minted adjustment cost at SCM's own unit_cost ceiling`; the ceiling is READ off SCM's field, not restated |
| **M12** | R4-M2 | admin-gated Post/Release buttons rendered for every member (guaranteed 403) | **[x] fixed** — 2 commits (`can_post`, then `can_release`) + the contract; `_is_admin()` local copy per the app-wide idiom, decorator still the enforcement |
| **M13** | R5-M1 | two dead joins in `generate()`'s rules queryset | **[x] fixed** — earlier in this run, folded into `perf(procurement): 6.18 I8+M13 - narrow generate()'s rules queryset to the nine columns it reads` |
| **M14** | R5-M2 | location roll-up drags `scm_item` + two unrendered aggregates | **[x] fixed** — same commit as M3; `_LOCATION_ANNOTATIONS` is derived FROM `_ROLLUP_ANNOTATIONS` by key so the two cannot drift |
| **M15** | R5-M3 | unbounded lot dropdown rebuilt every detail render | **[x] fixed** — `perf(procurement): 6.18 M15 - stop the lot dropdown offering lots no line could ever use, and stop it dragging scm_item`; narrowed to `item__is_active=True` (provably unselectable otherwise) + `.only()`, no capability lost |
| **M16** | R5-M4 | vendor `<option>` list re-rendered inside all 25 row forms (~0.5 MB) | **[x] fixed** — 3 commits (view cap + template caveat + contract); capped at 200 by name **plus every vendor already on the page**, and it bounds only what is offered, never what may be submitted. See Notes — the ceiling is a judgement call worth revisiting. |

## OUT OF SCOPE — route, do not fix here — 3

| ID | File | Owner | Status |
|---|---|---|---|
| **X1** | `apps/scm/management/commands/seed_scm.py` (~469, ~545) | `PutawayTask.goods_receipt` NULL on 8/8 rows, so `receipt_bin_map`'s bins column is blank in every demo. **The 6.18 join is proven correct.** SCM's seeder. | **[~] skipped — out of scope, routed** to whoever owns SCM seeding; file untouched |
| **X2** | `apps/procurement/views/BudgetCostManagement/BudgetMappings.py:85/91/98` | Same missing `@tenant_admin_required` as I4, on 6.15's config master. | **[~] skipped — out of scope, routed** to 6.15; file untouched |
| **X3** | `apps/inventory/views/InventoryTrackingControl/StockLevels.py:92` | Same index-bypassing join as I6. Module 5's file. | **[~] skipped — out of scope, routed** to Module 5; file untouched |

**Rule for the fixer:** X1–X3 are other modules' or other sessions' files in a shared checkout.
Mark each `[~] skipped — out of scope, routed` and do not touch them.

---

# NOTES FOR AN APP-WIDE PASS (raised by the fixer, not fixed here)

1. **Unbounded FK dropdowns are the app-wide reference pattern, not a 6.18 defect (L18).** M15 and
   M16 were fixed *in this sub-module* by narrowings that cost no capability (M15: lots of inactive
   items can never validate against the `item` field's own active-only queryset) or that keep the
   row's own selection (M16). But every form in this repo builds its FK choices as
   `Model.objects.filter(tenant=…)` with no ceiling — `MaterialIssueLineForm.item` is *every* active
   item, `gl_account` is *every* active account, and the same shape repeats across ~12 modules. The
   structural fix is a searchable/typeahead widget, which is an app-wide decision and must not be
   forked into one sub-module. **Recommend an app-wide pass.**
2. **M16's cap of 200 is a judgement call.** A workspace with more than 200 supplier/vendor parties
   cannot pick the 201st inline; the page says so and names two routes around it (the policy's
   preferred vendor, or the requisition after release). The zero-loss fix — render the option list
   once and clone it per row — needs JS/HTMX and a new endpoint, which is more than a Minor.
   Fold this into the same app-wide typeahead pass.
3. **`makemigrations --check` is NOT clean in this checkout, and it is not 6.18's.** It reports
   `procurement/0030 … prc_sks_tnt_cat_name_idx on supplierkpiscore` — the index added by
   `c468781e perf(procurement): C3 - index SupplierKpiScore on its Meta.ordering`, i.e. the **6.16**
   session's fixer, whose model file is on this session's do-not-touch list. **No migration was
   generated here.** The 6.16 session must claim `0030` (or the next free number).
4. **One stray `AuditLog` row (id 6608) in the dev database.** Verifying M12 posted MIS-00002 as
   `admin_acme` outside a transaction. The document, its `posted_at`/`issued_by` stamps and the
   minted `ADJ-00004` (draft, no stock moves) were all restored/removed immediately, but the audit
   log is append-only by design so the row was left in place. Demo data only; no schema or code
   impact.

---

**Called out as done well:** `MaterialIssue.post()` implements all four properties of the
`CountProgram.generate_tasks()` precedent rather than merely citing it — `select_for_update` on the
header, the `adjustment_id` reuse branch that closes the double-mint window the status gate cannot,
a provenance marker doubling as the note `StockAdjustment.clean()` demands for `reason="other"`,
and the availability guard running *before* anything is minted so a refused post leaves no orphan
draft. The per-item demand aggregation at `:324-325` (summing two lines of the same item before
comparing to on-hand) is the kind of thing that normally ships broken.
