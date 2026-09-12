# Review — Sub-module 7.6 Quality Management (`projects`)

> Reviewers run in sequence over `a6e2b0d3...HEAD` (contract-frozen BASE). Raw findings are
> appended per reviewer as they report; the file is deduped, sorted Critical → Important → Minor
> and assigned IDs at the end of Phase 4.

---

## 1. code-reviewer (raw findings, unmodified)

1. **Important — contract-pinned 7.6 test suite does not exist.** `.claude/tasks/contract-projects-7.6.md` §0 freezes "Tests: `test_quality_{models,forms,views,security}.py`; test names `test_quality_*`, helpers `_quality_*`". As of HEAD, `apps/projects/tests/` contains suites for 7.1–7.4 only; no `test_quality_*` file exists. → *Not a defect: the tests are Phase 6's deliverable per CLAUDE.md (models → forms → views → security, one file at a time). Recorded here so the close-out can verify they shipped; NOT a code-fixer item.*
2. **Important — seeder `_quality` crashes when the tenant has no chartered project.** `seed_projects.py` `plan(chartered, ...)`, `review(chartered, ...)`, `inspection(chartered, ...)`, `defect(chartered, ...)` pass `chartered` unconditionally, but the guard only checks `active` and `users`; `chartered` may be `None` (`_convert()` can yield None; a user can delete the chartered project). `QualityPlan(project=None).save()` raises IntegrityError inside `transaction.atomic()` and aborts the seed command. The sibling `_risk` block defends with `if chartered is not None:`. Fix: wrap the four chartered rows in the same guard.
3. **Minor — QDF `cancelled` is a live status for the resolve and raise-issue verbs.** `QualityDefect.is_locked` = `resolved`/`closed` (contract-pinned), and `qdf_resolve`/`qdf_raise_issue` gate on `is_locked` only, so a cancelled defect can be resolved or bridged; the detail template renders both buttons for a cancelled row. Fix: gate those two verbs (and the template panels) on `obj.is_open`, leaving edit/delete on `is_locked`.
4. **Minor — lessons lens contradicts the module's own definition of "closed".** `QualityImprovement.py` lessons queryset filters `status="closed"` only while the same module's maturity and trend count `resolved` or `closed` as dispositioned. Fix: `filter(status__in=_CLOSED_DEFECT_STATUSES)`.
5. **Minor — `quality_improvement` has an unbounded in-memory working set and a 12-query trend.** `all_reviews = list(reviews_qs)` materialises the whole register for the maturity average; the trend issues 2 COUNTs per month. Fix: `aggregate(Avg("maturity_score"), Count("pk"))` over scored reviews; `TruncMonth`-annotated counts for the trend.
6. **Minor — `_acceptor_parties` duplicates `_helpers.clients` byte-for-byte.** Dependency direction (views → forms) is real, but two identical copies drift. Fix: move the helper to a layer both may import (forms/_common or core), keep both callers.
7. **Minor — `parties` context key in `qci_list` is dead weight** (contract-pinned §4.3, but no template reads it; one query per render). Fix: render a party filter or amend the contract to drop the key.
8. **Minor — `QualityReview.is_improvement` is dead code and disagrees with the view's partition;** the name `_IMPROVEMENT_TYPES` also denotes two different tuples in `views/QualityManagement/QualityReviews.py` and `views/QualityManagement/QualityImprovement.py`. Fix: delete the property or rename the constants and cross-reference the contract clauses.
9. **Minor — `--flush` help text is stale** — enumerates deleted tables but omits the 7.6 quality tables (and 7.7 scope tables). Fix: extend the parenthetical.
10. **Minor — `quality_acceptance` docstring misstates the state derivation** ("latest inspection that carries a decision" vs the implemented latest-inspection-until-decided behaviour, which is correct). Fix: reword. Related: contract §4.6 "hosts the qci_accept action" vs shipped queue links to the detail page — deliberate, add a contract amendment line.

Clean categories: tenant scoping/security, conventions (L16/L29/derived-figures/badges), error handling, migration hygiene, state machines beyond #3, wire-up (re-exports, urls concat, LIVE_LINKS verbatim, overview, admin).

---

## 2. explorer (raw findings, unmodified)

*Verified clean: Rulings 1–7 respected (no QMS duplication, no second issue log, FK-not-redeclare, free text, no money, no stored score, links-out); FK graph and related_names clash-free repo-wide; migration 0009 in sync (`makemigrations --check` clean); all four re-export blocks runtime-verified complete; all 32 routes reverse with provably disjoint literal first segments; sidebar/overview/badges contract-exact.*

1. **Important — the contract-pinned 7.6 test suite does not exist.** Same as code-reviewer #1 → *Phase 6 deliverable, not a code-fixer item.*
2. **Important — the computed pages skip the capped single-pass idiom the app adopted for the identical page shape (M10/M13).** `QualityImprovement.py:149` `all_reviews = list(reviews_qs)` (unbounded, 3 joins) and `QualityAcceptance.py:103` `acceptance_queue = list(queue_qs)` unbounded; the cited precedents (RiskMonitoring/RiskAnalysis) cap at `_REGISTER_CAP = 2000` and derive figures DB-side; the trend runs 12 COUNT queries where one TruncMonth aggregation would do. Fix: cap + aggregate DB-side.
3. **Minor — three of the four 7.6 admins declare dead `list_select_related` joins** (QualityReviewAdmin joins wbs_node/quality_plan — not rendered; DeliverableInspectionAdmin joins quality_plan/milestone/accepted_by/accepted_by_party; QualityDefectAdmin joins quality_plan/inspection/resolved_by), contradicting the rule their own comment states and M6's a6693a88 precedent. Fix: trim to rendered FKs.
4. **Minor — `qci_list` computes a `parties` context key no template reads** (dead Party query per render; contract §4.3 pinned it — the contract line is the bug). Fix: drop the key + note the contract deviation.
5. **Minor — `_acceptor_parties` duplicates `clients()` byte-for-byte and justifies it with a factually wrong claim** (views/_helpers does not import from forms; the real cycle is via views/__init__). Fix: correct the docstring or single-source the helper.
6. **Minor — falsy-zero hides a computed maturity band the view did produce.** `score = 0.0` (defects exist, 0% closure) computes band "Initial" at view level, but the template gates on `{% if maturity.score %}` so 0.0 renders the no-data state and drops the band. Fix: gate on `maturity.score is not None` (e.g. a `has_score` key).
7. **Minor — `quality_acceptance` docstring overstates the derivation** (same as code-reviewer #10). Fix: align docstring with code.
8. **Minor — one private constant name, two different vocabularies, plus a dead model property** (same as code-reviewer #8). Fix: rename + use or drop `is_improvement`.
9. **Minor — `cancelled` defects are not frozen: `qdf_resolve` and `qdf_raise_issue` both accept them** (same as code-reviewer #3). Fix: refuse `cancelled` in the two verbs (or extend `is_locked`).
10. **Minor — `usage_decision="rework"` is a write-path-dead value and a superset of the scm 4.9 vocabulary it claims to mirror** (scm's QualityInspection has no `rework`; it exists only in NonConformance dispositions; nothing in 7.6 writes it; all consumers handle it safely). Fix: document the deliberate superset or drop the value.
11. **Minor — the contract file's two `fields.E009` widths were fixed in code but never amended in the contract** (§2.3 says 12, shipped 14; §2.4 says 8, shipped 12). Fix: patch the contract lines with the E009 rationale.

---

## 3. frontend-reviewer (raw findings, unmodified)

*Verified clean: L33 palette (badges + stat icons all colour-named, view-computed badges in palette); list-page rules (page-header/breadcrumb, GET filters with stringformat:"d", actions column, guarded pagination, empty-states); L2/L10 (comment blocks, no FK in |default:); badge-chain fallbacks; verb gates matching views incl. the supersede admin condition; cross-template consistency with risk//cost/; accessibility (labels, aria-label, submit types); overview rows/counts.*

1. **Minor — confirm dialogs attached via button `onclick` instead of form `onsubmit`** on `deliverableinspection/detail.html:76` ("Record result") and `qualitydefect/detail.html:95` ("Resolve defect"). Both forms contain text/date inputs, so pressing Enter in the date input submits the form and bypasses the confirmation (browser implicit submission fires submit, not click). Fix: move `confirm(...)` to `<form onsubmit=...>` like every other verb form.
2. **Minor — same vocabulary badged inconsistently across the four quality pages.** `observation` severity is badge-green on `qualityplan/detail.html:112` but falls through to the unbadged else on `qualitydefect/list.html:93-96`, `qualitydefect/detail.html:31` and `deliverableinspection/detail.html:114`; `quality_acceptance.html:58,86-87` omit `not_applicable`/`rework` cases that `deliverableinspection/list.html:92,99` badges. Colour-only drift (chains still have else fallbacks). Fix: replicate the full choice mappings in each chain.
3. **Minor — the acceptance board's filter bar is the only one in the module without a Reset control** (`quality_acceptance.html:18-29`). Fix: add the Reset link like the other five pages.
4. **Minor — the lessons lens renders a bare `<dl>` instead of the `.table-wrap`/`.table` idiom** every other list-like block uses (`quality_improvement.html:130-136`; cf. risk_monitoring's lessons table). Fix: render as a table inside .table-wrap.
5. **Minor — the punch list's "Inspection" filter `<select>` enumerates every tenant inspection unbounded** (`qualitydefect/list.html:70-76`, view `QualityDefects.py:62-63`), unlike the bounded FK filters elsewhere; a long-lived register degrades the page. Fix: slice (e.g. latest 100) or free-text number search.

---

## 4. performance-reviewer (raw findings, unmodified)

*Verified clean: select_related coverage on all 4 registers and all detail views; overview counts on indexed columns; InspectionAcceptanceForm's Party queryset lazy (0 queries on construction); no per-row property N+1 in templates (defect_count unreferenced); seeder query pattern acceptable.*

1. **Important — unbounded materialisation of the full review register.** `QualityImprovement.py:149` `all_reviews = list(reviews_qs)` — 4-table join, no cap, only `maturity_score` read. Fix: `reviews_qs.aggregate(n=Count("maturity_score"), avg=Avg("maturity_score"))`.
2. **Important — 12 COUNT queries per render for the defect trend, two-thirds unindexable.** `_defect_trend` 2 counts × 6 months; `resolved_at__date` wraps the column (unindexable); ~16 defect-table COUNTs per page with the maturity/counts. Fix: one capped Python pass or two TruncMonth group-bys.
3. **Important — acceptance queue materialised with no cap, tenant-wide** (`QualityAcceptance.py:103`), rendered wholesale. Fix: cap rendered rows (~100) + DB `.count()` for the header; served by `qci_tnt_decision_idx`.
4. **Important — latest-inspection-per-deliverable derived by fetching every project inspection** (`QualityAcceptance.py:80-82`, setdefault over the full ordered queryset). Fix: Subquery/OuterRef per node or narrow `values()` pass.
5. **Minor — unbounded row-dropdown on the defect register** (`QualityDefects.py:62-63`, same as frontend #5). Fix: cap or narrow window.
6. **Minor — several filter columns lack (tenant, column) indexes** (verification_method/owner on QPL, reviewer on QRV, inspection_type/inspector on QCI, defect_category/owner/inspection on QDF; the overdue-lens date columns unindexed) — second-class filters narrowed via the indexed status side; add composites if registers grow.

---

## 5. qa-smoke-tester — Phase 4 verb-flow pass (raw findings, unmodified)

*All 10 verb state-machine flows PASS through real POSTs (admin_acme + ops_acme logins, CSRF enforced, seeded MySQL DB): QPL approve→supersede→refusals + locked edit refusal; QRV report (from planned AND in_progress)→close→close refusal; QCI record (status→in_progress, row stays live)→accept (decision+status+stamps in one save, locked)→accept-refusal on pending result; QCI reject; QDF resolve (note required, root_cause optional)→close→resolve refusal; bridge refusal on already-bridged defect; raise-issue happy path (ISS-00008 minted, severity minor→medium, restored after); cross-tenant verb POSTs → 404 with no state change; missing CSRF → 403; empty resolution_note → field error. DB restored to pre-run values (verified per row).*

1. **Low / design observation — `qpl_approve` is not tenant-admin-gated.** Any authenticated member can activate a plan and become its recorded approver, while the lighter-looking `supersede` is admin-only. Consistent with the module docstring's intent (contract §2.1 pins approve as login-only), but worth a product look since approval is the weightier act. → *No code change this pass; recorded for the product owner.*
2. **Disclosure (harness, not app)** — the throwaway script's first-run session cleanup deleted all `django_session` rows (dev-server users logged out; no business data affected); fixed for subsequent runs. No pre-existing business data touched; per-row restoration verified.
3. **Info** — PermissionDenied/CSRF 403s log tracebacks to stderr under DEBUG (noise only).

---

## 6. security-reviewer (raw findings, unmodified)

*Verified clean: IDOR/tenant isolation (every fetch tenant-scoped, computed pages re-resolve ?project= against the tenant); authorization (`@tenant_admin_required` genuinely applied to supersede; the other nine verbs login-gated per contract); crafted-POST boundary (`_reject_foreign` on every tenant-scoped FK, NOT on Party; accept-form party queryset + verb re-check); mass assignment (all verb-written stamps off the forms); injection/XSS (no |safe, no raw int(), as_db_int everywhere); CSRF (zero csrf_exempt, middleware on); audit trail (both bridge sides audited in-transaction).*

1. **Minor — `qpl_supersede` decorator order: a member's GET returns 403 instead of 405.** `@tenant_admin_required` runs before `@require_POST`; move `@require_POST` above it (the reorder convention 7.7 applied as its C2 fix). No mutation possible — status-code disclosure only.
2. **Minor — `QualityDefect.is_locked` omits `cancelled`, so a cancelled defect stays fully writable.** Unlike its siblings (QRV/QCI lock cancelled), a cancelled defect can be edited, hard-deleted (evidence destruction), resolved with stamps, or bridged to an issue. Fix: add `"cancelled"` to `is_locked` (+ widen `_LOCKED_MSG`) or refuse it in the three verbs.
3. **Minor — `qdf_raise_issue` double-bridge guard is check-then-act without a lock (TOCTOU).** Two concurrent POSTs could both pass the guard and mint two issues. Mirrors the shipped 7.5 `rsk_realize` idiom (accepted project pattern). Fix: `select_for_update()` re-fetch + re-test inside the atomic block.
4. **Minor — no security tests shipped for 7.6.** → *Phase 6 deliverable (tracked there), not a code-fixer item.*

---






## Deduplicated findings (Phase 4 close-out)

Deduped across the six reviewers; sort order Critical → Important → Minor. The missing
`test_quality_*` suite (code #1 / explorer #1 / security #4) is **Phase 6's deliverable per the
build sequence**, not a code-fixer finding — tracked in Phase 6, not here.

### Critical

*(none)*

### Important

- **[ ] I1 — Seeder `_quality` crashes when the tenant has no chartered project.**
  `apps/projects/management/commands/seed_projects.py` — `plan(chartered,…)`/`review`/
  `inspection`/`defect` rows pass `chartered` unconditionally; the guard checks only
  `active`/`users`, and `_convert()` can yield no chartered project (or a user deletes it).
  `QualityPlan(project=None).save()` → IntegrityError aborts the whole seed command.
  Fix: wrap the four chartered rows in the `if chartered is not None:` guard the `_risk`
  block already uses. (code #2)
- **[ ] I2 — Computed pages ignore the app's capped single-pass idiom (unbounded lists, 12-query
  trend, O(n) latest-inspection derivation).** `QualityImprovement.py:149` materialises the
  whole review register for one average; `_defect_trend` runs 12 COUNTs (the `resolved_at__date`
  half unindexable); `QualityAcceptance.py:103` materialises the acceptance queue unbounded and
  `:80-82` evaluates the full inspection queryset to keep one row per deliverable. The cited
  precedents (RiskMonitoring/RiskAnalysis) cap at `_REGISTER_CAP = 2000` and aggregate DB-side.
  Fix: `aggregate(Avg/Count)` for maturity; capped list or TruncMonth group-by for the trend;
  cap the rendered queue + DB `.count()` for the header; narrow values()/Subquery for
  latest-per-node. (code #5, explorer #2, perf #1–#4)

### Minor

- **[ ] M1 — Cancelled defects stay fully writable.** `QualityDefect.is_locked` = resolved/closed
  only, unlike QRV/QCI which lock `cancelled`; a cancelled defect can be edited, deleted,
  resolved (stamping resolver evidence) or bridged to an issue. Fix: add `"cancelled"` to
  `is_locked`, widen `_LOCKED_MSG`, and confirm the verb/template gates follow.
  (code #3, explorer #9, security #2)
- **[ ] M2 — `qpl_supersede` decorator order: member GET returns 403 not 405.**
  `@tenant_admin_required` runs before `@require_POST`; move `@require_POST` above it (matches
  the 7.7 C2 reorder convention). (security #1)
- **[ ] M3 — `qdf_raise_issue` double-bridge guard is check-then-act without a lock (TOCTOU).**
  Re-fetch with `select_for_update` inside the atomic block and re-test `project_issue_id`
  before minting. Mirrors 7.5's shipped idiom — low practical risk, cheap to harden.
  (security #3)
- **[ ] M4 — Confirm dialogs on button `onclick` instead of form `onsubmit`.**
  `deliverableinspection/detail.html:76` (record) and `qualitydefect/detail.html:95`
  (resolve): Enter-in-input submits the form and bypasses the confirmation. Fix: move
  `confirm(...)` to the form. (frontend #1)
- **[ ] M5 — Badge chains incomplete across pages.** `observation` severity unbadged on
  qualitydefect list/detail and deliverableinspection detail (but badge-green on
  qualityplan/detail); `not_applicable`/`rework` missing from quality_acceptance chains.
  Fix: replicate the full choice mappings. (frontend #2)
- **[ ] M6 — Acceptance board filter bar lacks a Reset control** (the only one in the module).
  `quality_acceptance.html:18-29`. (frontend #3)
- **[ ] M7 — Lessons lens renders a bare `<dl>`** instead of the `.table-wrap`/`.table` idiom
  every other list-like block uses (`quality_improvement.html:130-136`). (frontend #4)
- **[ ] M8 — Unbounded row-dropdowns.** `qdf_list`'s inspection filter (`QualityDefects.py:62-63`)
  and `qci_list`'s dead `parties` key (`DeliverableInspections.py:63`) — cap the inspection
  dropdown (e.g. latest 200); drop the `parties` key (no template reads it) and note the
  contract deviation. (frontend #5, perf #5, code #7, explorer #4)
- **[ ] M9 — Falsy-zero hides a computed maturity band.** A 0.0 score (defects exist, 0% closure)
  passes the view but `{% if maturity.score %}` renders the no-data state, dropping the
  "Initial" band. Fix: add `has_score` to the maturity dict and gate on it.
  (explorer #6)
- **[ ] M10 — Dead admin joins contradict the rule their own comment states.** QualityReview/
  DeliverableInspection/QualityDefect admins `list_select_related` join FKs no changelist
  column renders. Fix: trim to rendered FKs (QualityPlanAdmin is already correct).
  (explorer #3)
- **[ ] M11 — Dead property + double-booked constant name.** `QualityReview.is_improvement` has no
  consumers; `_IMPROVEMENT_TYPES` means 3 types in `views/QualityManagement/QualityReviews.py`
  and 2 in `views/QualityManagement/QualityImprovement.py`. Fix: delete the property, rename
  the board constant `_BOARD_IMPROVEMENT_TYPES`, cross-reference the contract clauses.
  (code #8, explorer #8)
- **[ ] M12 — Docstring/code drift.** `QualityAcceptance.py:16-19` claims "latest inspection that
  carries a decision" (implemented: latest until decided — behaviour correct, docstring wrong);
  `_acceptor_parties` docstring claims views/_helpers imports from forms (it does not; the real
  cycle is via views/__init__); `DeliverableInspections.py` USAGE_DECISION docstring claims to
  mirror scm 4.9 but `rework` is a deliberate superset. Fix: reword all three. (code #10,
  explorer #5/#7/#10)
- **[ ] M13 — Stale seeder `--flush` help text** — omits the 7.6 quality (and 7.7 scope) tables
  from the deleted-tables enumeration. (code #9)
- **[ ] M14 — Contract file not amended for shipped deviations.** §2.3 `result` 12→14 and §2.4
  `severity` 8→12 (fields.E009); §4.3 `parties` key dropped (M8); §4.6 "hosts the qci_accept
  action" → queue links to the detail page (deliberate). Fix: patch
  `.claude/tasks/contract-projects-7.6.md` with the rationales. (explorer #11)
- **[ ] M15 — Second-class filter columns lack (tenant, column) indexes** (verification_method/
  owner/reviewer/inspection_type/inspector/defect_category/inspection_id; overdue-lens date
  columns) — narrowed via the indexed status side; **accepted for now** while registers are
  small, revisit if a tenant's registers grow. (perf #6)

### Design observations (no code change this pass)

- **D1 — `qpl_approve` is login-gated, not admin-gated** (qa-smoke #1): any member can activate
  a plan and be recorded as approver, while `supersede` is admin-only. Contract §2.1 pins it
  login-only; recorded for the product owner.
- **D2 — `AuditLog.ACTION_CHOICES`** covers create/update/delete only; the 7.6 verbs (and 7.5's)
  write accept/reject/resolve/close — succeeds because choices are not DB-enforced; same
  convention as 7.5. (security footnote)
- **D3 — `usage_decision="rework"` is write-path-dead** (no writer); kept as vocabulary for the
  manual rework loop; documented in M12's docstring fix.
