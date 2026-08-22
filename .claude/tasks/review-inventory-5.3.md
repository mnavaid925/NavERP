# Review — inventory 5.3 Purchase Order (PO) Management (2026-08-22)

Six parallel reviewer lanes over the 5.3 changeset (BASE `4842f1fd`). Scope: the PO management
layer around 4.1's `scm.PurchaseOrder` spine — approval routing rules, per-tier decisions, the
email/EDI dispatch log, reorder-point auto-drafting.

| Lane | Result |
|------|--------|
| code-reviewer | 1 Critical, craft otherwise high |
| explorer | Fully wired end-to-end; no in-scope findings |
| frontend-reviewer | 1 Important + 3 Minor |
| performance-reviewer | Clean at realistic volumes; 4 Minor N+1 shapes |
| qa-smoke-tester | **10/10 areas PASS (67 assertions)** — READY |
| security-reviewer | 1 Medium + 2 Low; tenant isolation solid |

## Findings

- [ ] **C1** (code-reviewer, models/PurchaseOrderManagement/Approvals.py) — `(tenant, purchase_order,
      tier)` uniqueness conflicts with replay-after-rejection: reject → draft → resubmit resets
      `cleared_tier_count` to 0, so `_decide` demands tier 1 again → IntegrityError 500. Also: status
      flips unlocked, no IntegrityError handling. Fix: drop the constraint; serialize `_decide` with
      `select_for_update()` on the order inside one atomic block.
- [ ] **M1** (security, views/.../Approvals.py) — intermediate tier approvals write no `core.AuditLog`
      row (only final approve / reject do). Fix: audit every decision create.
- [ ] **I1** (frontend, templates/inventory/po/approvals.html) — `item.done` branch IS reachable
      (rule edited/deactivated mid-chain) and shows a stuck "Fully cleared — finishing…" with no
      button. Fix: honest copy + admin "Confirm & approve" posting `next_tier`.
- [ ] **L1** (security) — rule-detail `obj.decisions` query and queue chain prefetch lack an explicit
      tenant filter (safe today via writers, weak tomorrow). Fix both.
- [ ] **L2** (security) — approval-rule create/edit/delete only login-required while they ARE the money
      gate. Fix: `@tenant_admin_required` on writes, reads stay open.
- [ ] **M2** (performance) — `approval_queue` resolves rules with one query per pending order. Fix:
      fetch active rules once, resolve in Python (`resolve_from()`).
- [ ] **M3** (performance) — `_draft_orders`: per-row `.first()` fetch + per-row on-hand aggregate;
      GET path already uses `on_hand_map`. Fix: batch `pk__in` + reuse the map on POST.
- [ ] **M4** (performance) — `approvalrule_list` missing `select_related("org_unit")` (15 queries/page
      worst case).
- [ ] **M5** (frontend) — approvals queue unbounded; slice to 100.
- [ ] **M6** (frontend) — icon-only action buttons rely on `title=` alone; add `aria-label`.
- [ ] **M7** (frontend) — reorderdraft submit stays enabled when the vendor roster is empty; wrap it in
      `{% if vendors %}`.
- [x] ~~Explorer I-2~~ — seeder `--flush` doesn't delete `PurchaseOrderApproval` rows. Fixed alongside
      C1's rework of decision lifecycle.
- [x] Explorer/wiring: all 13 url names ↔ views ↔ `{% url %}` ↔ templates verified green;
      LIVE_LINKS["5.3"] all five routes reverse; migration 0005 contains ONLY 5.3 models; parse_catalog
      renders sub-module 5.3 live. Concurrent-session noise (5.5/5.6/ReceivingPutaway) is out of scope.

QA note: the smoke suite passed because its reject-path never resubmitted the order — C1 hides behind
exactly that gap. The regression test added with the fix covers reject → resubmit → full re-approval.
