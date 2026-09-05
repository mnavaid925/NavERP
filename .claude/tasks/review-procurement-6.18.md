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
