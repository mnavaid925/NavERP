# Review — Procurement 6.3 Approval Workflow Engine

- **Changeset:** `abe1b633e3a5337b96111ab58364debea288deea..HEAD` (2026-08-25)
- **Lanes:** code+performance · security · frontend+QA smoke (three parallel read-only agents; live shell probes included)

## Summary table

| ID | Severity | Lane | Finding | Status |
|----|----------|------|---------|--------|
| F-01 | **High** | security | Self-approval: `approval_decide` never compared signer to requester — a member could sign their own chain through every tier incl. the spine flip | [x] fixed — requester≠signer refused inside the locked block |
| F-01b | High→design | security/code | scm's approve is admin-only for ALL amounts; 6.3 let members finalize standard chains | [x] fixed — three-part gate: never own request; elevated chains admin-only at every tier; the FINAL tier (the spine transition) always admin-only. Members sign intermediate tiers of standard chains only. Mirrored for display via `_queue_row(gate/may_decide)` |
| PERF-1/F-08 | Important | code/security | Commodity-match N+1 (`lines.all()` per candidate rule × rows) | [x] fixed — `_lines_map` batches page lines once; `resolve_routing(lines_by_req=)`; rules fetches `select_related("org_unit")` |
| BUG-1 | Important | code | `escalation_hours=0` ("escalate immediately") fell through to policy default | [x] fixed — engine uses `is not None`; template renders precomputed `window_is_rule` |
| ROBUST-1/F-07/F1 | Important | all lanes | Hand-rolled `?org=` filter bypassed `as_db_int` (L11) | [x] fixed |
| AUDIT-1 | Important | code | Admin could write signature rows despite its own "never from the admin" comment | [x] fixed — RequisitionApprovalAdmin is a fully read-only register (add/change/delete False) |
| F-03 | Medium | security | Seeder fabricated a signature attributed to the real admin on real data; single-tier case corrupts next decision's tier math | [x] fixed — approver=None + audit as System; signs ONLY when resolved chain ≥2 tiers; success line reports actual counts |
| RACE-2/F-04 | Medium/Low | both | EscalationPolicy singleton had no per-tenant unique; get_or_create race → MultipleObjectsReturned 500s | [x] fixed — unique_together (tenant,) via migration 0006 |
| RACE-1/F-05 | Minor | code | Concurrent Runs could double-alert ("idempotent" overclaim) | [x] fixed — Run takes `select_for_update` on the policy row = per-tenant mutex; claim now true |
| HONESTY-1 | Minor | code | Caps silently truncated stats; Run evaluated only the capped board slice | [x] fixed — real pending count via cheap `.count()` + on-page truncation notice; Run passes `limit=None` so chains beyond the cap still escalate |
| UI-1/F3 | Minor | frontend | Idle duration rendered raw seconds | [x] fixed — engine emits `idle_hours_f`; template shows hours |
| F2 | Low | frontend | stat-cards nested in form-grid + inline columns (unique in codebase) | [x] fixed — sibling `stat-grid` wrapper |
| F-06/F6 | Info | frontend | Unused `now` context var | [x] fixed |
| EDGE-1 | Minor | code | Band ceiling sentinel (10¹²) below DecimalField(18,2) domain | [x] fixed — sentinel raised to column max |
| DOC-1b/c | Minor | code | Flush help text stale; seeder hardcoded "3 routing rules" | [x] fixed |
| F5 | Info | frontend | History footer count is grand-total phrasing | [~] skipped — copy already reads "on record" (grand total), not filtered total |
| F4 | Info | frontend | Dead `?org=` GET param on rule list | [~] skipped-with-reason — harmless supported capability, mirrors crud_list filter tuples elsewhere; wiring a dropdown is cosmetic follow-up |
| F-02 | Medium | security | `--flush` deletes across all tenants unfiltered | [~] skipped-with-reason — this IS the established seeder convention app-wide (inventory/procurement flush blocks all use global deletes in a staff-only management command); help text now states the scope honestly |
| Delegations.active_for direction | High (self-caught pre-review) | main session | Authority lookup searched delegator=user instead of delegate=user | [x] fixed before review wave landed |

## Verified clean (both reviewers, explicitly)

- Rejection terminality claim TRUE against scm source (EDITABLE_STATUSES excludes rejected; submit guards draft) — the `(tenant, requisition, tier)` unique is safe.
- TOCTOU: elevation/self/final gates sit INSIDE the atomic block behind the spine row lock; denied probes leave zero rows.
- IDOR/tenancy PASS everywhere; XSS PASS (zero `|safe`; alert link_urls internal-only); CSRF/method PASS; pure ORM.
- Ladder determinism, half-open band edges, delegation window/scope precedence, tier snapshots — all traced correct.

## Smoke

`temp/verify_awe_63.py`: **35 passed, 0 failed** — includes the new gate probes (member self-approve refused, member final-tier refused, member elevated-intermediate refused→admin closes, DOA-stamped intermediate signature, idempotent double Run) plus full IDOR/gating sweeps.

**Verdict:** approve after fixes (all applied). One design change of note: final-tier decisions are now tenant-admin-only by contract, matching the spine's own approve view.
