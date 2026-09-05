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

---

**Called out as done well:** `MaterialIssue.post()` implements all four properties of the
`CountProgram.generate_tasks()` precedent rather than merely citing it — `select_for_update` on the
header, the `adjustment_id` reuse branch that closes the double-mint window the status gate cannot,
a provenance marker doubling as the note `StockAdjustment.clean()` demands for `reason="other"`,
and the availability guard running *before* anything is minted so a refused post leaves no orphan
draft. The per-item demand aggregation at `:324-325` (summing two lines of the same item before
comparing to on-hand) is the kind of thing that normally ships broken.
