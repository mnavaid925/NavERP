# Review — inventory 5.7 Stock Movement & Transfers (2026-08-23)

Read-only wave over the sub-module files (models/forms/views/urls/templates/migrations/tests +
scm additive spine edits), lanes: correctness / security / frontend / performance / tests.
DB-backed pytest was sandbox-killed during review; collect-only verified.

| Lane | Verdict | Findings |
|---|---|---|
| Code correctness | Issues | C1, M3, M4 |
| Security | Mostly clean | I1, M2 |
| Frontend | Issues | C1, I2, M5 |
| Performance | Mostly clean | M1 |
| Tests | Gaps | I3, M6 |

## Critical
- [x] fixed C1 Board scope filter dead: option values inter/intra vs view gate `scope_filter in SCOPE_CSS`
      (keys inter_warehouse/intra_warehouse) - Transfers.py:146-154 + board.html:26-27. Filter never
      applies while the option looks selected. Fix: alias map {inter: SCOPE_INTER, intra: SCOPE_INTRA}.

## Important
- [x] fixed I1 Rule/Route CRUD writes not admin-gated (mirrored 5.3 gates them) - wrap create/edit/delete
      of TransferRoutes + ApprovalRules views in @tenant_admin_required; pass is_admin to list/detail;
      gate Edit/Delete affordances in templates.
- [x] fixed I2 Board Approval column always shows 0/N once pending: template reads row.progress.decision_count,
      _progress() has no such key. Fix: add decision_count to _progress dict.
- [x] fixed I3 Test gaps: tautological OR assertion hides C1; missing covers()-refusal at submit; missing
      default-tier fallback case. Strengthen assertions single-sided + assert actual filtering.

## Minor
- [ ] M1 No index supporting queue recent-decisions query (tenant, decided_at). DEFERRED - new
      inventory migration would collide with the concurrent 5.8 session numbering; schedule with it.
- [x] fixed M2 Rule detail decisions query lacks explicit .filter(tenant=...) defense-in-depth (5.3 has it).
- [~] M3 Clamp stored tier to required on Confirm-&-approve beyond-rule path - SKIPPED: deliberate
      human-confirm exit hatch; clamping would hide that a rule shrank mid-chain.
- [x] fixed M4 transfer_submit not locked like decide/complete - wrap in atomic + select_for_update.
- [x] fixed M5 Panel ledger badge shows raw move_type code; use get_move_type_display.
- [x] fixed M6 Pin resolver tie-break determinism + covers() same-endpoint unit tests.

## Verified clean
Tenant isolation everywhere; IDOR -> 404 tested; tier verbs admin-gated + POST-only; csrf on every
form; as_db_int on crafted route param; locking + replay on decide path; complete-guard blocks
pending_approval bypass; migrations additive w/ correct deps; badges all exist in theme.css; url
names all reverse; board/queue/panel flat per render (~7-9 queries); pagination partials present.
