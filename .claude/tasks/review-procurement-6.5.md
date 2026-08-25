# Review — Procurement 6.5 Sourcing & Tendering (2026-08-26)

Six parallel read-only lanes over BASE `0b1b5c23..HEAD` scope. Compiled findings below;
fixer marks `[x] fixed` / `[~] skipped — reason`.

## Critical
- [ ] **C1 / SEC-I1 / FE C-01 — stored-XSS sink: interpolated `confirm()` inside inline `onsubmit`** (`events/detail.html:110`, `awards.html:33`). HTML-decoded attribute text reaches JS parsing; a Party name like `O'Brien…` breaks the confirm gate (form submits unconfirmed), a crafted name can execute script in an admin session during award. Fix: static confirm strings.
- [ ] **CONV-C1 / FE I-02 — `.btn-amber` used, not defined in theme.css** (`events/detail.html:17`). Remove (keep `btn btn-outline`).
- [ ] **CODE-C1 / CODE-I4 / CODE-M10 — evaluation verbs race the award writer**: `_decide` + `bid_submit` unlocked; stale shortlist/disqualify can overwrite a `won` bid (event left awarded with zero winners); note saved as a second non-atomic write after `decide()`; `decide()` lacks an event-status guard. Fix: atomic + `select_for_update` + under-lock status re-check; single save path carrying `decision_note`; event-status guard in `decide()`.

## Important
- [ ] **CODE-I2 — headline savings mixes populations** (`Analytics.py:51-68`): `total_awarded_price` accumulates every winner while `total_budget` only comparable events → deflated total; contradicts page footnote. Fix: accumulate price inside the budget-known branch.
- [ ] **CODE-I3 / PF-65-08 — duplicated weighted-score math drifting**: model `weighted_score()` (quantized, zero callers) vs `_helpers.weighted_from_map` (raw). Fix: delegate the model method to the helper (local import preserves one-way FK graph).
- [ ] **SEC-M2 — privilege-model inconsistency**: award is admin-gated but close/cancel (kill competition) are plain login. Fix: `@tenant_admin_required` on `event_close`/`event_cancel`; shortlist/disqualify/score stay staff-level but documented as evaluator actions (audit-attributed).
- [ ] **FE I-03 — draft-bid delete missing from event-detail Actions column** (eye+pencil only there).
- [ ] **FE I-04 — falsy-zero hides lead time 0 days** (`events/detail.html:74`, `bids/detail.html:39`) → `is not None`.
- [ ] **FE I-05 — disqualify textarea unlabeled** → `aria-label`.
- [ ] **FE I-06 — promised weight-coverage figure never shown** → badge with `total_weight` on bids/detail header; weight sum surfaced on events/detail criteria card.
- [ ] **SEC-M1 — `Decimal('NaN')` 500s the scoring POST** (comparison signals InvalidOperation outside the try). Fix: guard conversion AND range check.
- [ ] **PF-65-04 — award board costs 61 queries/render (3×20)** → batch criteria/scores/bids across page pks (~4 queries).

## Minor (accepted)
- [ ] **CODE-M5 / PF-65-01 — event_detail double fetches** → reuse `event_scores_map`'s criteria; pass them into `evaluate_event`.
- [ ] **CODE-M6 — `event_delete` TOCTOU** → atomic + row-lock + re-check bids.exists().
- [ ] **CODE-M7 — existing draft re-pointable to a closed/draft event** → form clean() requires `bids_allowed` when event CHANGES on edit.
- [ ] **CODE-M8 — analytics bids missing select_related("supplier","event")** (per-row supplier query).
- [ ] **CODE-M9 — month buckets by 30-day steps duplicate labels near month-end** → calendar-month arithmetic.
- [ ] **CODE-M11 / CONV-I5 — seeder creates "submitted" bid directly then no-op `submit()` call** → create draft, call `submit(None)`.
- [ ] **CONV-I1/I2 — seeder `help=` stale + missing 6.5 module-docstring paragraph**.
- [ ] **CONV-I3/I4 — seed awarded event fabricated outside the model path; cancelled event lacks cancel audit + atomic wrap** → drive open→close→award() with System attribution; wrap C atomically.
- [ ] **M1 (CONV) — U+FFFD mojibake in `_helpers.py` 6.5 comments** (em-dashes mangled by shell append) → restore proper characters.
- [ ] **PF-65-02 / PF-65-07 — unused `select_related("requisition")`** on award_board + event_list list QS.
- [ ] **PF-65-03 — award-board cap magic number + docstring says "every CLOSED event"** → named constant + aligned docstring.
- [ ] **FE M-07 — dead `{% empty %}` in analytics months; bare muted cell in frozen matrix** → tidy to empty-state pattern.
- [ ] **n_live dead context key** in AwardBoard.

## Skipped with reason
- [~] **QA F-01 — 7 failing AWE (6.3) tests in the app suite** (`test_awe_*`): pre-existing drift introduced by concurrent-session 6.3 behavior fixes (`52e7aaaa`, `748b0b39`, `81288c20`) landing without test updates; 6.3's owning session must reconcile. Not touched here (L45 — shared area actively owned elsewhere).
- [~] **QA F-02 — untracked migration 0007 + untracked 6.4 folders**: owned by the in-flight 6.4 session.
- [~] **CONV-M2 slice-ordering cosmetics** (6.5 before/after 6.4/6.6 in lists): churn in files the concurrent session is actively editing buys nothing.
- [~] **CONV-M3 admin editable business fields on frozen docs**: matches sibling RfxEventAdmin posture; noted.
- [~] **PF-65-05/06 — analytics O(6·(N+B)) month loop + unbounded loads**: fine at seeded/current scale; revisit if register grows (documented in code comment).
- [~] **FE M-08 `n_bids|default:0`**, **QA F-04 smoke leaves 7.50 scores**: harmless idioms/demo state.

## Lane health
code-reviewer ✅ · explorer ✅ · frontend-reviewer ✅ · performance-reviewer ✅ · qa-smoke-tester ✅ (smoke ALL PASS 26/26; probes 9/9) · security-reviewer ✅ — no dead lanes.
