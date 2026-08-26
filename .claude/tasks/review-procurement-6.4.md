# Review — procurement 6.4 Vendor Management (2026-08-26)

Six read-only reviewers ran in parallel (code · conventions · frontend · performance · qa-smoke ·
security) over the 6.4 changeset. Findings were deduped, fixed in the main integration pass the
same day, and re-proven by `temp/verify_64_fixes.py` (14/14) + `smoke_64.py` (18/18) + the
`test_vendormgmt_*` suites (52/52). BASE reviewed: `d36c160c`.

| ID | Sev | Lane | Finding | Status |
|----|-----|------|---------|--------|
| QA1 | Critical | qa | Context var `block` shadowed by Django's implicit BlockNode → suspension banner always rendered and `invoice_new` form branch never reachable | [x] fixed — renamed to `suspension` in Portal.py + both templates; comment left in `_vendor_access` |
| F1 | Critical | code | `vsu_edit` passed non-reversible `success_url="procurement:vsu_detail"` → NoReverseMatch 500 AFTER commit | [x] fixed → `procurement:vsu_list` |
| F2/VM2 | Important | code/sec | `blocking_for()` ignored `ends_on` → expired suspensions blocked forever at the portal gate | [x] fixed — date predicate added; probe proves expiry boundary |
| FE1 | Medium | fe | Reject button submitted a different form than the note textarea → decision_note silently empty | [x] fixed — one shared form, approve/reject via `formaction` buttons |
| FE2 | Medium | fe | List "lift" POST could never carry the mandatory lift_note → guaranteed server bounce with misleading copy | [x] fixed — links to `detail#act` where the reason form lives |
| P1 | Medium | perf | List-page footer aggregates built on `_scoped()` dragged 4–5 LEFT JOINs through whole-tenant COUNTs | [x] fixed — aggregates off join-free base querysets (vpa/vsu/vis) |
| VM3 | Low | sec | `vsu_edit` immutability gate was TOCTOU vs concurrent approval | [x] fixed — edit runs inside `select_for_update` atomic block around crud_edit |
| F4 | Minor | code | Decided rows deletable despite immutable-history invariant | [x] fixed — vsu_delete gate `requested` only; vis_delete gate `submitted` only (+ templates) |
| F5/VM4 | Minor | code/sec | Invalid (>2000) note on approve/reject silently discarded while deciding | [x] fixed — `_decision_note()` bounces without deciding |
| P3/P4 | Minor | perf | Detail-only FKs (`lifted_by`, `invited_by`) missing from `_scoped()` | [x] fixed |
| P2/P5/P6 | Minor | perf | Double counts on vpa_list; 3 portal stat queries; dead joins (`currency`, submissions PO) | [x] fixed — one filtered aggregate each; joins dropped |
| F6/VM5 | Minor | code/sec | `invited_by` never written outside seeder | [x] fixed — hand-rolled `vpa_create` stamps it |
| F9 | Minor | code | Seeder audit row logged against SupplierProfile; review note fabricated "BILL-1024" | [x] fixed — wrong audit line removed; honest wording |
| F7 | Minor | code | VPA docstring overclaimed what the OneToOne constrains | [x] fixed — corrected rationale (multi-login-per-supplier is deliberate) |
| FE3–FE6 | Minor | fe | Dead `#act` anchor (id added), no confirms on irreversible decisions (added), "Open orders" label overstated (→ Orders on file), AP jargon leaking into supplier page (rewritten) | [x] fixed |
| F8 | Minor | code | Whitelist entries for procurement models are no-ops (filter gates only `app_label="scm"`) | [x] removed my three entries (sibling session's entries left to them) |
| F3 | Deferred | code | Bullet says "blocked from receiving POs"; enforcement today is portal-gate only — scm owns the PO flow (L36), model docstring + banner copy now promise only what ships | [x] FIXED in follow-up — `purchaseorder_approve` AND `purchaseorder_send` consult the register via local import (`_vendor_block`); send re-checks so a block filed after approval still stops dispatch; tests prove all three paths |
| VM1 | Low | sec | No `(tenant, supplier)` uniqueness — two logins per supplier is permitted BY DESIGN (AP clerk + buyer) | [~] skipped — docstring corrected to state the intent |
| F10 | Minor | code | `MinValueValidator(ZERO)` allows 0 while clean() forbids ≤0 | [~] skipped — harmless duplicate boundary; clean() enforces on every form path |
| QA2 | Minor | qa | Audit actions outside core ACTION_CHOICES ("approve"/"review"/…) | [~] skipped — pre-existing app-wide convention (e.g. 6.3's "tier_approve"), not 6.4's to change |

No lane returned NO RESULT. Residual risk: none Critical open.

## Follow-up wave (same day) — the three "deferred by design" items shipped

| ID | What shipped | Proof |
|----|--------------|-------|
| FU1 (was F3) | PO-side enforcement: scm's approve+send verbs refuse POs to a vendor with an active VSU (`_vendor_block` lazy import, SCM reads procurement's register — never writes it); banner/list copy updated to match | `test_blocked_vendor_po_approve_refused`, `test_block_filed_after_approval_stops_dispatch`, `test_unblocked_vendor_po_approve_succeeds` |
| FU2 | Portal **Invoices & payments** panel: read-only projection of accounting.Bill rows for the bound party (number/date/due/total/balance/status badges; void excluded) — same posture as 4.16 showing invoices | `test_portal_home_lists_accounting_bills` |
| FU3 | Gated supplier **bid page** (the page 6.5's SourcingBid docstring deferred): `vendor_portal_bids` lists OWN bids only; drafts editable via `VendorBidForm` (event/supplier server-forced, non-compliant-needs-note rule); submit reuses `SourcingBid.submit()` under the bid+event double lock; blocked suppliers refused; foreign pks bounced; submitted proposals immutable | `test_portal_bids_page_lists_own_bids_only`, `test_portal_bid_edit_and_submit_round_trip`, `test_noncompliant_portal_bid_without_note_rejected`, `test_submitted_portal_bid_not_editable`, `test_blocked_supplier_cannot_submit_bid`, `test_foreign_bid_pk_never_editable` |

Scoped rerun after the wave: **63 passed / 0 failed**.

