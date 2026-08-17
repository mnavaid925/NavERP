# SCM 4.18 — Phase 7 DOCS accuracy audit (2026-08-17)

Scope: the two Phase-7 documents only — the `## 4.18 Finance & Accounting Integration` section of
`.claude/skills/scm/SKILL.md` (+ that file's header and `## Sidebar wiring` section) and the Module 4 row of
`README.md`'s `## Module roadmap (0–13)`. **No code defects are in scope** — 4.18's code was reviewed and fixed in
Phases 4–5 (`review-scm-4.18.md`, 15 findings, 14 fixed, M3 deferred) and its suite is green. The two exceptions are
D2/D13, which are stale *docstring prose* propagated from the same wrong sentence this audit found in the skill.

Method: 5 read-only audit lanes in one parallel Workflow (`wf_89a9de4d-78a`) over models / routes+forms /
templates+seeder / README+sidebar / completeness, deduped, then re-verified **by hand in the main session** —
every finding below was independently confirmed against the cited code before being written here.

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 6 |
| Minor | 7 |

Lane status: `models` ✅ · `routes/forms` ✅ (returned on 3rd retry) · `templates/seeder` ✅ · `README/sidebar` ✅ ·
`completeness` ⚠️ **NO RESULT** (died on all 4 attempts). Its territory is substantially covered by D5/D9/D10/D11
(which the README/sidebar and routes lanes raised independently), but it is recorded here as missing coverage
rather than as a clean bill of health.

---

## Important

### D1 — `.claude/skills/scm/SKILL.md`, `LandedCostVoucher` table cell
**Claim:** "All derived money (`estimated_total`/`actual_total`/`variance_amount`/`variance_pct`/`allocated_total`/`accrued_at`) is `editable=False`; `recalc_totals()` is their only writer."
**Wrong:** `accrued_at` is not derived money and `recalc_totals()` never writes it — its `update_fields` is exactly
the five money columns + `updated_at` (`LandedCostVouchers.py:329-330`). `accrued_at` is stamped by `accrue()`
(`:522`) and cleared by `allocate()` (`:497`). The same cell contradicts itself two sentences later ("clears
`accrued_at` when re-allocation demotes an accrued voucher").
**Fix:** split the sentence — "All derived money (`estimated_total`/`actual_total`/`variance_amount`/`variance_pct`/`allocated_total`) is `editable=False` and `recalc_totals()` is their only writer; `accrued_at` is also `editable=False` but is stamped by `accrue()` and cleared by `allocate()`."
- [ ] fixed

### D2 — `.claude/skills/scm/SKILL.md` rule 1 + five 4.18 code docstrings
**Claim:** "All **seventeen** shipped scm template folders use a short slug…"
**Wrong:** there are **eighteen** (`ls -d templates/scm/*/` → 3pl analytics assets coldchain compliance
demandplanning **finance** inventory labor manufacturing orders portal procurement quality returns srm
transportation warehouse). The count went stale the moment 4.18 shipped `finance/`, and it contradicts this file's
own header ("18 of 19"). The identical stale sentence is in **five** of 4.18's own files:
`apps/scm/models/FinanceIntegration/DutyTariffs.py:48`, `models/FinanceIntegration/LandedCostVouchers.py:11`,
`models/FinanceIntegration/Reports.py:47`, `urls/__init__.py:106`, `views/FinanceIntegration/DutyTariffs.py:10`.
**Fix:** make it **count-free** in all six places ("Every shipped scm template folder uses a short slug…" /
"…verified free against every shipped scm prefix") so it cannot go stale again at 4.19. Do **not** just bump 17→18.
One commit per file. `manage.py check` after the code-docstring edits (docstring-only, nothing executable changes).
- [ ] fixed

### D3 — `.claude/skills/scm/SKILL.md`, `LandedCostCharge` table cell
**Claim:** the field list runs "…`gl_account`, `tax_code`, `is_recoverable`…, `capitalise_to_inventory`."
**Wrong/missing:** it omits the charge's two **pointer** columns, both of which are on the form whitelist
(`forms/FinanceIntegration/LandedCostVouchers.py:134-136`) and therefore user-facing:
* `party` → **`core.Party`**, SET_NULL (`LandedCostVouchers.py:675`) — the per-line vendor. **Load-bearing:**
  `split_charges()` (`:281-301`) EXCLUDES any charge naming a party other than the voucher's payee from the drafted
  bill, and `draft_bill()` **refuses outright** when every charge is excluded (`:557-565`). Nothing in the entire
  4.18 section mentions `split_charges()` or that exclusion, so a reader debugging a refused `draft_bill()` has no
  pointer.
* `freight_invoice` → **`scm.FreightInvoice`**, SET_NULL (`:679`) — the 4.6 audited carrier invoice this charge came
  from. This is 4.18's one reuse-vs-duplicate seam left unstated: the section mentions `FreightInvoice.bill` only as
  an *AP pointer*, so a maintainer asked to "tie the carrier's freight bill to the landed cost" would conclude no
  link exists and add a second one.
**Fix:** add both columns with their target apps, add the `split_charges()` / `draft_bill()`-refuses rule, and
**app-qualify every other FK target** as the sibling 4.17/4.13 tables do (`gl_account`→`accounting.GLAccount`,
`tax_code`→`accounting.TaxCode`, voucher `currency`→`accounting.Currency`, voucher `party`→`core.Party`). Also add
the voucher's two typed columns the cell never names: required `cost_date` and free-text `notes`.
- [ ] fixed

### D4 — `.claude/skills/scm/SKILL.md`, `### Seeder — _seed_finance_tenant`
**Claim:** "**Invents no master data** — every party, item, GL account… is found among rows earlier passes seeded."
**Missing (the pass's biggest side effect):** when the chosen `received` GRN has no `receipt` StockMoves,
`_seed_finance_tenant` **posts them through the real `_post_grn_receipt` helper** inside `transaction.atomic()`
(`seed_scm.py:5548-5574`) — a genuine write into 4.3's append-only ledger plus the weighted-average roll, closing
4.1's documented gap (4.1 books that GRN `received` before the item master exists). It also **returns early,
seeding zero vouchers**, in four cases: no `received` GRN (`:5540-5546`), the post is blocked (`:5565-5568`),
nothing matched an item (`:5569-5574`), or no supplier/vendor/partner party exists (`:5589-5593`, because the
drafted bill's `party` is PROTECT and required). A reader trusting the doc assumes the pass only ever touches its
own four tables and always yields the two documented vouchers.
**Fix:** state both — the conditional `_post_grn_receipt` ledger write, and the four early-return cases.
- [ ] fixed

### D5 — `.claude/skills/scm/SKILL.md`, `## Sidebar wiring` section — **MANDATORY section missing**
**Missing:** there is **no `LIVE_LINKS["4.18"]` paragraph anywhere in the file**, and the 4.18 section names not a
single sidebar key. Sidebar wiring is a **required** per-module-skill section (`.claude/CLAUDE.md`, "Per-Module
Skill" rule 3), and siblings 4.11/4.12/4.13/4.14/4.15/4.16 all ship theirs. The mapping is **not guessable** from
the section, and the file's own header defines "built" as *having* a `LIVE_LINKS["4.M"]` entry — so a reader whose
only map is this file would conclude 4.18 has none and that `/next-module` would re-pick it.
**Fix:** append a `**LIVE_LINKS["4.18"]**` paragraph in the 4.11–4.16 house style, from `navigation.py:1126-1136`:
Accounts Payable→`scm:finance_payables`, Accounts Receivable→`scm:finance_receivables`, Landed Cost
Calculation→`scm:landedcostvoucher_list`, Budgeting→`scm:finance_budget_variance`, Tax
Management→`scm:dutytariff_list`; note that **three of the five are read-only computed registers** over
`accounting.Bill`/`Invoice`/`Budget` pointers; and record the deliberate ruling that **`scm:landed_cost_variance`,
`LandedCostCharge` and `LandedCostAllocation` take NO key** — five NavERP bullets, five keys; the charges and
allocations are panels on the voucher detail page. *(`LIVE_LINKS["4.17"]` is missing from the same section — add it
in the same pass if you can do so from `navigation.py` without guessing.)*
- [ ] fixed

### D6 — `.claude/skills/scm/SKILL.md`, rule 6 (the gating map)
**Claim:** "All four verbs are POST-only AT THE VIEW and `@tenant_admin_required`… The four report pages are
`@login_required` STAFF pages, read-only, no `@require_POST`."
**Both halves are true but the rule is the section's ONLY gating statement**, and it silently omits the three
delete routes it documents under `### Routes` — all three are `@login_required` + `@require_POST` with **no admin
gate** (`views/FinanceIntegration/LandedCostVouchers.py:298-300`, `:534-536`;
`views/FinanceIntegration/DutyTariffs.py:241-243`). That **deliberately diverges** from the sibling precedent where
`asset_delete` IS `@tenant_admin_required` (documented at SKILL.md:981/:996-997 with the exact button gate). A
template author reading only this section will either wrongly hide the three Delete buttons behind an admin check —
removing an action ordinary members legitimately have — or file their absence as a security defect.
**Fix:** state the full map: the four money-committing verbs are `@tenant_admin_required @require_POST`; the three
deletes are `@login_required @require_POST` (POST-only but **member-permitted**); charge create/edit are plain
`@login_required`; the four reports are `@login_required` read-only. **Seven POST-only routes in total** — which is
exactly what `test_finance_security.py` asserts. Say which buttons therefore need the admin `{% if %}` and which
must NOT.
- [ ] fixed

---

## Minor

### D7 — `.claude/skills/scm/SKILL.md`, `LandedCostAllocation` table cell
**Claim:** "Every column `editable=False`; **`allocate()` is the only writer.**"
**Wrong (half):** only the five *derived* columns carry `editable=False` (`quantity`, `basis_value`, `basis_used`,
`allocated_amount`, `unit_cost_uplift` — `LandedCostVouchers.py:788-796`). The four FKs `voucher`/`charge`/
`stock_move`/`item` (`:775-787`) and the inherited `tenant`/timestamps are ordinary fields; what actually keeps them
unwritten is that **no form points at the model**. "`allocate()` is the only writer" is correct. (The model's own
docstring at `:769` overstates it the same way — fix the skill; leave the docstring, or fix both consistently.)
**Fix:** "Every DERIVED column (`quantity`/`basis_value`/`basis_used`/`allocated_amount`/`unit_cost_uplift`) is
`editable=False`; the four FKs are plain fields and there is deliberately no form, view, list or url — `allocate()`
is the only writer."
- [ ] fixed

### D8 — `.claude/skills/scm/SKILL.md`, `### Templates`
**Claim:** "an unallocatable per-unit uplift renders as `None`, not `0`."
**Wrong:** `None` is the **context value**, not what the page shows. The view sets
`group["unit_cost_uplift"] = q4(...) if quantity else None`
(`views/FinanceIntegration/LandedCostVouchers.py:261-262`) and the template guards `is not None`, rendering an **em
dash** `<span class="text-muted">—</span>` in the column (`landedcostvoucher/detail.html:477`) and suppressing the
per-unit badge (`:444`). Anyone writing a smoke assertion from this sentence looks for the literal string "None".
**Fix:** "a group with no quantity to divide by gets `unit_cost_uplift = None` (never `0`), and the page renders an
em dash and drops the per-unit badge — zero is a real answer, so the guard is `is not None`, never truthiness."
- [ ] fixed

### D9 — `.claude/skills/scm/SKILL.md`, `### Seeder` (the `--flush` sentence)
**Claim:** "`--flush` deletes the whole allocation → charge → voucher tree BEFORE 4.1's `GoodsReceiptNote`
(PROTECT) and any party cleanup; there is no `JournalEntry` to unwind."
**Missing the first and last steps:** `_flush()` deletes the **DRAFT `accounting.Bill` rows** reachable through
`scm_landed_cost_vouchers` **FIRST** (`seed_scm.py:1077-1080`) — `LandedCostVoucher.bill` is SET_NULL, so deleting
vouchers first **strands a fresh set of draft bills in AP every cycle** — and it deletes the **`DutyTariff` master
last** (`:1084`). A reader rebuilding the teardown from this sentence reintroduces exactly the orphaned-bill bug the
code comment warns about.
**Fix:** "…deletes the DRAFT `accounting.Bill`s scoped through `scm_landed_cost_vouchers` FIRST (SET_NULL means
deleting vouchers first strands them in AP), then the allocation → charge → voucher tree, then `DutyTariff` — all
BEFORE 4.1's `GoodsReceiptNote` (PROTECT) and any party cleanup; there is no `JournalEntry` to unwind."
- [ ] fixed

### D10 — `.claude/skills/scm/SKILL.md` — no `### Forms` subsection
**Missing:** the section states exactly one form fact (rule 3's `rate_for()` default). Sibling 4.13 ships a
`### Forms  (forms/AssetManagement/)` subsection (SKILL.md:966-977) covering precisely the classes of fact a
maintainer cannot guess here:
* `LandedCostChargeForm.__init__(self, *args, voucher=None, **kwargs)` — the parent is a **keyword-only** argument
  (`forms/FinanceIntegration/LandedCostVouchers.py:138`); instantiate it the ordinary way and the unsaved instance
  has no voucher for `effective_basis` / `full_clean()` to walk;
* that form gets **zero automatic tenant scoping** (`LandedCostCharge` has no tenant column), so all four of its FKs
  are narrowed **by hand** and re-checked in `clean()` (`:21-25`);
* the payee dropdown **reuses `_carrier_parties(tenant)`** — roles supplier/vendor/partner — on both forms
  (`:85`, `:149`), rather than a new broker-role helper;
* `DutyTariffForm(TenantUniqueMixin, TenantModelForm)` (`DutyTariffs.py:67`) vs
  `LandedCostVoucherForm(TenantModelForm)` (`:44`) — the mixin is on the tariff deliberately and not on the voucher.
**Fix:** add a `### Forms  (forms/FinanceIntegration/)` subsection modelled on SKILL.md:966-977, naming the three
form classes, that `LandedCostAllocation` has none, and the four facts above.
- [ ] fixed

### D11 — `.claude/skills/scm/SKILL.md` — no `### Tests` line for 4.18
**Missing:** 4.18 ships four dedicated test modules totalling **431** `test_finance_*` functions and the section
names none of them, so a maintainer changing an invariant (allocate idempotency, the `rate_for` precedence ladder)
has no pointer to the regression locks. Sibling 4.14 ships `### Tests (apps/scm/tests/, ~505 for 4.14)`
(SKILL.md:1292-1303).
**Fix:** add `### Tests  (apps/scm/tests/test_finance_{models,forms,views,security}.py — 431 for 4.18)` naming what
each module locks: allocate idempotency / `_unallocate` reversal, the `rate_for` precedence ladder, the
derived/system-fields-off-every-form check, cross-tenant IDOR → 404 and the seven 405 POST-only routes.
- [ ] fixed

### D12 — `.claude/skills/scm/SKILL.md:1674`, module-level `## Common tasks` (pre-existing, unrelated to 4.18)
**Claim:** "`pytest apps/scm/tests -q` **(2,761 tests)**."
**Wrong:** `apps/scm/tests` now holds **5,967** `def test_*` functions — the figure is stale by more than half and
has been left behind by every sub-module since it was written.
**Fix:** refresh to ~5,967, or better, drop the parenthetical count entirely so it stops going stale each pass.
- [ ] fixed

### D13 — `.claude/skills/scm/SKILL.md` + `README.md` — `RMA` is not a class
**Claim (both files):** "…6 shipped models (… 4.10 `RMA.credit_note`)."
**Wrong:** there is no `RMA` class or alias anywhere in the project. 4.10's model is **`ReturnAuthorization`**
(`models/ReturnsManagement/ReturnAuthorizations.py:48`) and `RMA-` is only its number prefix; the field is
`credit_note` → `accounting.Invoice` (`:194`). The other five entries in that list are exact class names, so this
one reads as authoritative when it is not — and the mandated verification step (`grep -rn "^class <Name>"
apps/*/models/`) finds nothing. 4.18's own code spells it correctly
(`models/FinanceIntegration/Reports.py:18-19`).
**Fix:** `ReturnAuthorization.credit_note` (optionally "… [`RMA-`]") in **both** the SKILL.md 4.18 intro paragraph
and the `README.md` Module 4 roadmap row. Two files → **two commits**.
- [ ] fixed

---

## Verified accurate — no change needed

Recorded so a later pass does not re-litigate them. Each was checked against the code this session:

* the four model names, the two prefixes (`DTY-`, `LC-`), and that the two children carry none;
* `LandedCostCharge` being tenant-**less** (reached via `voucher.tenant`) and `LandedCostAllocation` carrying its
  **own** tenant, with the three `(tenant, …)` indexes that justify the exception;
* the 5 `ALLOCATION_BASIS_CHOICES`, the **11** `CHARGE_TYPE_CHOICES`, the status ladder, `EDITABLE_STATUSES`;
* `effective_from` never nullable + the MySQL-NULL-defeats-the-unique-key rationale; the `unique_together` tuples;
* `rate_for()`'s resolution order (active → window with the explicit `effective_to__isnull` leg → named origin
  beats the blank any-origin row → newest first) and that it returns `None` rather than raising;
* `is_current` as a property; `allocatable_amount`; `capitalises`; the snapshots not being a live join;
* `allocate()` idempotency, the `_unallocate()` reversal and the `accrued_at` demotion;
* **SCM posts no `JournalEntry`** — `draft_bill()` drafts an `accounting.Bill` and stops;
* the additive-over-the-append-only-ledger framing and `apply_landed_cost()` rolling `Item.average_cost`;
* every url name in `### Routes`, the nested-charge-create vs own-pk-edit/delete split, and that 4.18 adds no
  greedy `<str:…>` route;
* every file named in `### Templates` exists at exactly that path, and none is omitted;
* the five other AP/AR pointers (`GoodsReceiptNote.bill`, `FreightInvoice.bill`, `LandedCostVoucher.bill`,
  `SalesOrder.invoice`, `ClientBillingRun.invoice`);
* `LIVE_LINKS` holds exactly **18** module-4 keys, 4.1–4.18 with no gaps — so "18 of 19 / Next: 4.19" is right by
  the project's own definition of built;
* the seeder's three SKUs + only-where-NULL dimension rule, the two-tariff pair, the two vouchers with the second
  left in draft, and that it runs last in `handle()`.
