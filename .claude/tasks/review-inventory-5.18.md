# Review — Inventory 5.18 Accounting & Financial Integration (2026-08-25)

Two read-only reviewer lanes over the 5.18 changeset (BASE `dce1270c`), findings fixed in
the build session immediately after each wave. No Critical findings on either lane.

## Lane A — frontend + wiring QA

Verified clean: every `{% url %}` resolves (inventory + scm + accounting cross-app names);
context contract exact (`object_list/page_obj/q/register/vendors/is_admin`,
`adjustment_rule/cogs_rule/pending/pending_value/logs/last_batch/default_from/default_to`,
`obj/specificity`); pk filter compares with `|stringformat:"d"`; only color-named badges;
pagination + empty-states everywhere; LIVE_LINKS["5.18"] names all resolvable.

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| A1 | Minor | `je_automation.html` last-batch line unguarded against SET_NULL'd JE | [x] guarded `{% if last_batch.journal_entry_id %}` |
| A2 | Minor | COGS batch POST lacked confirm() parity with other money verbs | [x] confirm added |
| A3 | Minor | taxrule list "New Rule" CTA not admin-gated | [x] gated |
| A4 | Minor | pending badge understates >50 queue | [x] `+` cap indicator |
| A5 | Trivial | dead context keys (`today`, `event_type_choices`) | [x] removed |

## Lane B — backend code + security

Verified clean: tenant isolation on every path; AP/AR double-draft locks correct; balanced-entry
guarantee sound; forms exclude tenant/auto fields; CSRF/require_POST everywhere; no `|safe`;
migration matches models; `move_type="issue"` correctly scopes COGS to customer demand.

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| B1 | Important | COGS overlap check-then-act race → double-expense | [x] atomic block opens FIRST; locked GLPostRule row is the per-tenant serialization point; overlap re-checked inside |
| B2 | Important | adjustment double-post TOCTOU (contradicted docstring) | [x] StockAdjustment row locked inside atomic; log existence re-checked after lock |
| B3 | Minor | window idempotence can strand backdated moves silently | [~] skipped — disclosed in docstring instead; per-move links would need an inventory-owned join table for a rare case |
| B4 | Minor | COGS legs carried 4dp into 2dp columns; register drifted from JE by rounding residue | [x] quantized ROUND_HALF_UP per group before legs |
| B5 | Minor | AR invoices full ordered qty; days_due=0 falsy bug | [x] `is not None` guard; full-qty semantics documented in view docstring + visible note on ar_sync page |
| B6 | Minor | resolver honored rules pointing at deactivated TaxCodes | [x] resolve() skips them |
| B7 | Minor | `tax_code` missing from _reject_foreign list | [x] added |
| B8 | Minor | seeder JE demo didn't anti-join logged adjustments | [x] reuses the board's anti-join |
| B9 | Cosmetic | per-line redundant tax resolution on AP sync | [x] hoisted above loop |

## Test evidence

- `manage.py check` clean; migration 0024 applied; seed ×2 idempotent.
- MySQL smoke runner (`temp/smoke_518.py`): every page 200; sync artifacts verified end-to-end
  (draft Bill at PO prices w/ resolved tax, matched three-way state, linked draft Invoice,
  JSY→posted-JE chain incl. a 15-move COGS batch); overlap refusal polite; junk GET params safe;
  cross-tenant IDOR 404; member writes 403. GREEN after fixes.
- `apps/inventory/tests/test_finint_{models,forms,views,security}.py` (31 tests) committed for
  normal dev shells. Sandbox caveat of record (same as 5.7/5.14): this session's shell kills
  DB-backed pytest/DiscoverRunner launches while the parallel 5.15–5.17 session runs its own test
  phase — run them green in a normal dev shell before pushing.
