---
name: procurement
description: Work on the Procurement module (Module 6 — Procurement Management System). As-built = 6.1 User Dashboard & Portal (personalized overview with per-user widget preferences, Task & Alert Center with acknowledge/resolve lifecycle, quick requisition entry drafting into scm.PurchaseRequisition, audit-log-derived activity feed, self-service reports + own-requisitions CSV export) and 6.2 Requisition Management (tracking register + audit-trail timeline detail over scm.PurchaseRequisition, explainable duplicate-requisition engine with ?dupes=1 deep-link, RequisitionTemplate[RQT-] recurring-order blueprints with apply-into-draft, RequisitionAmendment[RAM-] gated cancel/amend workflow) and 6.3 Approval Workflow Engine (ApprovalRoutingRule dept x commodity x half-open band -> tier count with most-specific-wins resolver, RequisitionApproval[RQA-] append-only signature register under spine row locks with self-approval/elevated/final-tier admin gates, ApprovalDelegation DOA grants stamped via_delegation, EscalationPolicy + idempotent Run engine raising 6.1 alerts, mobile approval surface) and 6.5 Sourcing & Tendering (SourcingEvent[SEV-] tender/RFP/RFQ events draft->open->closed->awarded/cancelled with verb-only transitions + EventCriterion weight<=100 matrices, SourcingBid[BID-] whole-package bids with row-locked submit/shortlist/disqualify that can never overwrite an award, BidScore matrix scored on bid detail with NaN-proof validation and ONE shared weighted_total formula, computed award board (~4 queries/20 scenarios) with admin-gated won/lost writer, None-honest sourcing analytics) and 6.4 Vendor Management (VendorPortalAccess[VPA-] login<->supplier binding behind the gated vendor-portal pages with crm-1.4-style refusal ladder, VendorSuspension[VSU-] request->decide->lift block register whose blocking_for() honours ends_on expiry and gates portal invoice submission, VendorInvoiceSubmission[VIS-] supplier-filed invoices reviewed submitted->under_review->accepted/rejected with NO GL posting; onboarding/classification/risk bullets map onto scm 4.2's existing pages). Use when the user asks to add/change/debug anything under apps/procurement or templates/procurement, extend the seed_procurement seeder, touch procurement sidebar wiring (LIVE_LINKS 6.1–6.8), or invokes /procurement.
---

# Procurement — Procurement Management System (Module 6)

App path: `apps/procurement`. Templates: `templates/procurement/`. URL prefix: `/procurement/`,
`app_name = "procurement"`. Mirrors `NavERP.md` "## 6. Procurement Management System" (19
sub-modules, 6.1–6.19).

**As-built: 6.1–6.9 built across parallel sessions — 6.4 Vendor Management lives in
`VendorManagement/` (models/forms/views/urls) + `templates/procurement/vendormanagement/`.
Build the next one with `/next-module` (it takes the lowest `6.M` without a `LIVE_LINKS["6.M"]`
entry) — see the reference apps `apps/crm`/`apps/accounting` for the package layout and the
mandatory Module Creation Sequence.**

## Overview

6.1 and 6.2 are the people/workflow layer AROUND the procurement document spine. **The spine is
SCM 4.1's** (L29/L36): `scm.PurchaseRequisition`, `scm.PurchaseOrder`, `scm.GoodsReceiptNote`,
`scm.RFQ` are OWNED by `apps/scm` and this module EXTENDS them by FK/string reference — it
declares no requisition, PO or receipt table of its own. 6.1's Quick Requisition Entry WRITES
INTO `scm.PurchaseRequisition`; 6.2 tracks/amends/templates those same documents; requisition
Creation itself stays scm's full form (`LIVE_LINKS["6.2"]` maps that bullet cross-app to
`scm:requisition_create`). The activity feed is `core.AuditLog` filtered to procurement content
types; there is no second feed table.
## Models (`apps/procurement/models/DashboardPortal/<Entity>.py`, `…/RequisitionManagement/<Entity>.py`)

Shared base in `models/_base.py`: `TenantOwned` (tenant FK + timestamps, `related_name="+"`),
**`TenantNumbered`** (per-tenant auto number via `core.utils.next_number`, collision retry —
added in 6.2; NUMBER_PREFIX constants RQT/RAM/SEV/BID), plus toolkit imports, `ZERO`,
`q2()`/`MAX_Q2`.

### 6.1 DashboardPortal

- **`ProcurementAlerts.py`** — `ProcurementAlert`. The Task & Alert Center inbox.
  - `kind`: deadline/approval/delivery/task; `severity`: info/warning/critical;
    `status`: open/acknowledged/resolved (`OPEN_STATUSES = ("open", "acknowledged")`).
  - Lifecycle verbs ONLY: `acknowledge(user)` (no-op off `open`, returns bool) and
    `resolve(user, note="")` (early-returns False when already resolved so who/when/note can
    never be restated). `status` is OFF the form.
  - `link_url` must be an internal path: `clean()` rejects anything not starting with a single
    `/`, any backslash (browsers canonicalize `\` → `/`, so `/\evil.com` IS protocol-relative),
    and scheme-relative forms. Rendered as href verbatim — keep that guard intact.
  - `is_overdue` = due_at past AND status still live. Badge css properties
    (`severity_css`/`status_css`/`kind_css`) return colour-named classes ONLY
    (badge-green/red/amber/info/muted/slate; L33).
  - No auto-number (not a document). Indexes: (tenant,status)/(tenant,kind)/(tenant,assigned_to)/
    (tenant,severity).
- **`WidgetPreferences.py`** — `WidgetPreference`. One row per (tenant, user, widget_key) with
  `is_visible`; **absence of a row MEANS visible** (the seeder seeds none). The widget registry
  lives on the model as `WIDGETS` (ordered dict key→label; keys: approvals/alerts/spend/deadlines/
  activity). Helpers: `hidden_keys(tenant,user)` and `save_choices(tenant,user,visible_keys)`
  (atomic upsert loop; deliberately NOT audited — personal layout pref, not business data).

### 6.2 RequisitionManagement

- **`Templates.py`** — `RequisitionTemplate` [RQT-] + `RequisitionTemplateLine`.
  - Header defaults: name, description, org_unit/currency (nullable), default_lead_days,
    justification, is_active (retire-without-delete), created_by (editable=False).
  - Lines mirror `scm.PurchaseRequisitionLine`'s editable fields free-text (item_description/
    sku_hint/uom_hint/quantity/estimated_unit_price/gl_account); NO stored total — `line_total`
    and header `estimated_total` are derived properties on read.
  - Applying COPIES (never links): see `template_apply` below; later template edits do not
    rewrite raised requisitions. No usage counters (no bullet promises them).
- **`Amendments.py`** — `RequisitionAmendment` [RAM-] + `RequisitionAmendmentLine`.
  - FK PROTECT → `scm.PurchaseRequisition` (`related_name="amendments"`); unique_together
    (tenant, number); indexes (tenant,status)/(tenant,amendment_type).
  - `AMENDABLE_STATUSES = ("pending_approval", "approved")` — drafts edit directly in scm;
    converted/cancelled are closed. `has_open_for(requisition)` enforces ONE pending amendment
    per requisition.
  - Types: amend (proposed new_required_by / new_justification + line-change rows) or cancel
    (clean() forbids carrying proposed changes). Status pending/approved/rejected; decided_by/at,
    decision_note, applied_at all editable=False (view-set only).
  - `apply(decider, note="")` is THE only writer of changes to the spine: atomic, sets status
    cancelled OR writes header+line rows then `recalc_totals()`; returns a human summary
    ("requisition cancelled", "added 'X'", "removed 'Y'", "updated 'Z' (qty)", "'Update line'
    not applied — target line no longer exists"). target_line is SET_NULL so a vanished line
    degrades to a reported skip, never a cross-app ProtectedError.
  - Line rows: action add/update/remove against optional target_line; blank quantity/price on
    update means KEEP. Decided amendments are IMMUTABLE — corrections are new filings (documented
    deviation from generic CRUD-completeness; there is deliberately no edit/delete route).

### 6.5 SourcingTendering

- **`SourcingEvents.py`** — `SourcingEvent` [SEV-] + `EventCriterion`.
  - Event: type tender/rfp/rfq; status machine draft→open→closed→awarded/cancelled with
    `EDITABLE_STATUSES=("draft","open")`, `LIVE_STATUS="open"`; optional traceability FK →
    `scm.PurchaseRequisition` (`related_name="sourcing_events"`); nullable `budget_estimate`
    (None = unknown — analytics answers None, never zero); opens_at/closes_at/rules;
    created_by/opened_at/closed_at/awarded_at all editable=False. NO FK event→bid (the award
    is a fact about a bid). `award(bid, at)` is THE won/lost writer: refuses unless closed +
    compliant evaluatable bid on this event; flips other live bids to lost. Index
    (tenant,status); unique (tenant,number).
  - Criterion: event child, name unique per event, weight_pct 0<w≤100, max_score ≥1,
    `weight_fraction` property. No own tenant column (TemplateLine pattern).
- **`Bids.py`** — `SourcingBid` [BID-] + `BidScore` + module fn `weighted_total`.
  - Bid: supplier = core.Party PROTECT (supplier∪vendor roles); statuses
    draft/submitted/shortlisted/disqualified/won/lost with EVALUABLE/COUNTED/EDITABLE/
    DECIDABLE tuples; total_price Decimal(14,2), lead_time_days, is_compliant+compliance_note,
    summary, contact_ref, evaluator decision_note; submitted_by/at stamped by `submit(user)`
    (refuses off-draft or when `not event.bids_allowed`). `decide(action)` is a PURE resolver
    (returns target or None; caller persists under lock) and refuses cancelled events.
  - BidScore: bid×criterion unique, score ≤ criterion.max_score + same-event check in clean().
  - `weighted_total(score_map_row, criteria)` is the SINGLE formula ((score/max)×weight,
    q2-quantized) — model `weighted_score()` and views' `weighted_from_map` both delegate.
- Shared evaluation helpers in `views/_helpers.py`: `event_scores_map(event)` (2 queries),
`weighted_from_map`, `candidate_sort_key` (scored-first/score-desc/price-asc/pk),
`evaluate_event(event, criteria=None, score_map=None)`, `evaluate_events_batch(events)`
(~4 queries for a whole board page).

## Views / URLs

`app_name = "procurement"`. Package layout one-to-one across models/forms/views/urls under
`DashboardPortal/` (6.1) and `RequisitionManagement/` (6.2: Requisitions.py, Templates.py,
Amendments.py). Shared builders in `views/_helpers.py`: `procurement_activity_qs(tenant)` and
the 6.2 duplicate engine (`DUPLICATE_WINDOW_DAYS=30`, `DUPLICATE_CANDIDATE_CAP=1000`,
`DUPLICATE_ACTIVE_STATUSES`, `duplicate_pk_set(tenant_id, page_rows)` for register badges,
`find_duplicate_requisitions(pr)` → [{"requisition", "reasons"}] for the detail panel).
Append new sub-modules' model table names to `PROCUREMENT_CONTENT_MODELS` as they land.

| Route | Name | Notes |
|---|---|---|
| `/procurement/` | `dashboard` | Landing = personalized overview; POSTs widget toggle back to itself |
| `/procurement/alerts/` (+ add/detail/edit/delete) | `alert_*` | Full CRUD; list floats open rows first via a Case annotation |
| `/procurement/alerts/<pk>/acknowledge/` `…/resolve/` | `alert_acknowledge`/`alert_resolve` | POST-only lifecycle verbs |
| `/procurement/quick-requisition/` | `quickreq_create` | One-screen fast track → drafts scm.PurchaseRequisition |
| `/procurement/activity/` (+ `<pk>/`) | `activity_list`/`activity_detail` | Feed over core.AuditLog; always windowed (30d default); scope=mine default; detail restricted to the SAME domain filter |
| `/procurement/reports/` (+ `export/`) | `report_index`/`report_export` | Computed personal usage/spend + 6-month TruncMonth trend; CSV of MY requisitions only |
| `/procurement/requisitions/` (+ `?dupes=1`) | `req_list` | 6.2 tracking register over scm.PR; tenant-less superuser redirected; dupe badges computed post-pagination |
| `/procurement/requisitions/<pk>/` | `req_detail` | Pipeline strip (Draft→Pending→Approved→PO raised), duplicates panel w/ reasons, amendments table, RFQs/POs, audit-trail-as-timeline history |
| `/procurement/requisitions/<pk>/request-amendment/` | `req_amendment_create` | Guards inside select_for_update on the PR: status amendable + no open amendment; cancel-with-line-rows refused |
| `/procurement/templates/` (+ add/detail/edit/delete) | `template_*` | Full CRUD; header form + line formset (max_num=50 validate_max, `_reject_foreign` gl_account) |
| `/procurement/templates/<pk>/apply/` | `template_apply` | POST-only; inactive/no-lines refused; drafts spine PR under signed-in user (individual line creates so save()-derived totals compute); duplicate warning after |
| `/procurement/amendments/` (+ detail/approve/reject) | `amendment_*` | approve+reject @tenant_admin_required POST-only under select_for_update; reject requires reason |

Context-var contract: lists use `crud_list` (`object_list`/`page_obj`/`q` + each page's
`*_choices`); overview passes `stats` dict, `widgets` (list of {key,label,visible}),
`widget_form`, `pending_requisitions`, `my_open_alerts_list`, `upcoming_alerts`,
`due_requisitions`, `recent_activity`; quickreq passes `form`+`recent`; reports passes
`stats`/`by_status` (value,label,count triples)/`trend`/`recent_of_mine`;
req_list passes `dupe_pks` (set)/`dupes_only`/`window_days`; req_detail passes `pipeline`
([{key,label,state: done/current/todo}])/`duplicates` ([{requisition,reasons}])/`open_amendment`/
`history` (AuditLog rows)/`rfqs`/`purchase_orders`; template_detail passes `lines` +
pre-computed `estimated_total` (the model property would re-query); template list rows carry
annotations `n_lines`/`est_total` (aggregation ignores Meta.ordering → explicit .order_by).
amendment detail passes `decision_form`.

### 6.5 SourcingTendering routes

| Route | Name | Notes |
|---|---|---|
| `/procurement/events/` (+ add/detail/edit/delete) | `event_*` | Full CRUD; header + criterion formset (weights ≤100 enforced by the formset); edit frozen off draft/open; delete row-locked and refused once ANY bid exists |
| `/procurement/events/<pk>/open|close|cancel/` | `event_open/close/cancel` | POST-only verbs under select_for_update with state re-check; open = member, close/cancel @tenant_admin_required (spend-affecting, like amendment decisions) |
| `/procurement/events/<pk>/award/` | `event_award` | @tenant_admin_required POST-only; bid pk in POST resolved tenant-scoped under dual row locks; exactly one won, other live bids lost |
| `/procurement/bids/` (+ add/detail/edit/delete) | `bid_*` | Register filters status+event; detail hosts the scoring matrix POST (manual parse `c_<criterion_pk>`, NaN-proof range check, blank clears); edit/delete draft-only |
| `/procurement/bids/<pk>/submit|shortlist|disqualify/` | `bid_submit/shortlist/disqualify` | POST-only; submit locks bid+event; decisions lock the bid, single save carrying decision_note, disqualify requires a reason |
| `/procurement/awards/` | `award_board` | Computed: 20 newest closed events via evaluate_events_batch (~4 queries); Award button posts to event_award |
| `/procurement/analytics/` | `sourcing_analytics` | Computed post-event analysis: savings only where budget AND award price exist ("—" otherwise), participation/cycle means, six calendar-month buckets pre-bucketed O(N+B) |

Context-var contract: event_detail passes `obj/criteria/total_weight/bids` (each bid carries
precomputed `score_value`)/`candidates/recommended` (evaluating events only); bid_detail
passes `obj/criteria/matrix` ([{criterion,current}] — no dict-lookup filter needed)/
`weighted/total_weight/can_score`; award_board passes `rows`
([{event,candidates,recommended}]); analytics passes `stats` dict + per-event `rows` +
`months` ([label,{events,bids}]).

## Templates

`templates/procurement/overview.html` (landing) +
`templates/procurement/dashboardportal/{alerts/{list,detail,form}.html, quickrequisition.html,
activity.html, activity_detail.html, reports.html}` +
`templates/procurement/requisitionmanagement/{requisitions/{list,detail}.html,
templates/{list,detail,form}.html, amendments/{list,detail,form}.html}` +
`templates/procurement/sourcingtendering/{events/{list,detail,form}.html,
bids/{list,detail,form}.html, awards.html, analytics.html}` (awards/analytics are standalone
computed pages at the sub-module level). All extend `base.html`,
use theme.css classes, colour-named badges only, `{% include "partials/pagination.html" %}` on
paginated lists.

## Seeder

`python manage.py seed_procurement` — idempotent per tenant with PER-BLOCK guards (alerts /
templates / amendment each skip independently; templates block wraps its creates in
transaction.atomic so a crash can't strand a lineless template past the guard; `--flush`
deletes alerts only). Seeds 6 alerts covering every kind/severity (two walked through the
lifecycle), 3 requisition templates ×3 lines each, and ONE pending amend-type amendment against
an existing seeded `scm.PurchaseRequisition` (skipped gracefully when seed_scm hasn't run);
writes `core.AuditLog` baselines for alerts, templates and the amendment. The 6.5
`_seed_sourcing` block (guarded on `SourcingEvent`, skips without approved suppliers) drives
its rows through the REAL model path so the feed shows honest verbs: one awarded tender walked
create→open→close→award() with three draft bids that submit()/disqualify through the models and
carry per-criterion scores, one open RFP (submitted + draft bid), one cancelled RFQ with a
cancel audit row; `--flush` deletes sourcing children-first (BidScore→Criterion→Bid→Event).

## Conventions & gotchas

- Tenant scoping everywhere; superuser (`tenant=None`) sees empty data by design — 6.2 views
  that dereference `request.tenant.pk` (req_list, template_apply, req_amendment_create) guard
  and redirect to dashboard first.
- Requisition writers NEVER trust client totals: requester hardwired to `request.user`, status
  starts `draft`, totals via `recalc_totals()` / individual line `.create()` (bulk_create skips
  save()-derived `line_total` — do not "optimize" it back). Quantity/price ceilings match the
  scm columns' Decimal(14,4)/(14,2) widths to avoid driver 500s.
- Only `apply()` mutates an approved requisition; admin can't flip amendment.status in Django
  admin either (readonly_fields pin it there deliberately).
- CSV export neutralizes formula injection (`_csv_safe` prefixes `'` on leading `=`/`+`/`-`/`@`);
  exports only `requester=request.user` rows (tenant-wide spend is 6.14's job).
- Widget saves are deliberately not audited (documented on `save_choices`).
- Tests: `apps/procurement/tests/` — `test_portal_{models,forms,views,security}.py` (6.1) and
  `test_reqmgmt_{models,forms,views,security}.py` (6.2, every function named `test_reqmgmt_*`);
  shared fixtures live in the app conftest (spine PRs approved/pending, template_with_lines_a,
  amendment_pending_a). Run with `--no-migrations` for speed, e.g.
  `venv\Scripts\python.exe -m pytest apps\procurement\tests -q --no-migrations`.
- NOTE: inline formsets here POST under prefix `lines` (both children use related_name="lines").

## Sidebar wiring

`LIVE_LINKS["6.1"]`: Personalized Overview → `procurement:dashboard`; Task & Alert Center →
`procurement:alert_list`; Quick Requisition Entry → `procurement:quickreq_create`; Recent
Activity Feed → `procurement:activity_list`; Self-Service Reporting → `procurement:report_index`.

`LIVE_LINKS["6.2"]`: Requisition Creation → `scm:requisition_create` (cross-app, the spine owns
creation); Requisition Tracking → `procurement:req_list`; Duplicate Requisition Check →
`procurement:req_list?dupes=1` (?query= deep-links are a supported nav convention);
Requisition Templates → `procurement:template_list`; Requisition Cancellation/Amendment →
`procurement:amendment_list`.

`LIVE_LINKS["6.5"]`: Event Creation & Scheduling → `procurement:event_list`; Bid Submission
Portal → `procurement:bid_list`; Bid Evaluation Matrix →
`procurement:event_list?status=closed`; Award Recommendation → `procurement:award_board`;
Sourcing Analytics → `procurement:sourcing_analytics`.

## Common tasks

- **Add a widget**: add the key to `WidgetPreference.WIDGETS` (order = render order), add the
  section to `templates/procurement/overview.html` behind `{% if w.visible and w.key == "…" %}`,
  compute its context in `Overview.dashboard`.
- **Raise alerts from a later sub-module**: import `ProcurementAlert` and create rows (optionally
  `write_audit_log`); do not fork the inbox.
- **New procurement sub-module**: new `<SubModule>` folder per layer, re-export blocks, one
  `LIVE_LINKS["6.M"]` entry, extend `seed_procurement` idempotently, extend
  `PROCUREMENT_CONTENT_MODELS` if its documents should appear in the feed.

---

## 6.3 Approval Workflow Engine (built 2026-08-25)

**As-built now: 6.1-6.3 (3 of 19).** Package folder `ApprovalWorkflowEngine/` across all four
layers; templates `templates/procurement/approvalworkflow/{routingrule,delegation}/<entity>/
{list,detail,form}.html` + page-only `queue.html`, `history.html`, `mine.html`,
`escalations.html`. The requisition DOCUMENT and its status machine stay SCM 4.1's
(`scm.PurchaseRequisition`); scm's own single-step approve remains - 6.3 adds the multi-tier
governance AROUND it (inventory 5.3's posture).

### Models

- **ApprovalRoutingRule** (`RoutingRules.py`, TenantOwned, NO numbering): optional org_unit
  (dept) + commodity KEYWORD (matched case-insensitively against line sku_hint/item_description
  - the L28 stand-in) + HALF-OPEN band min<=total<max -> required_tiers (1..5) +
  per-rule escalation_hours override. Overlapping rules legal; resolver ladder specificity DESC
  (org=2, commodity=1) -> narrowest band -> lowest id; NO match = ONE default tier never zero.
  `_BAND_CEILING` sentinel mirrors the DecimalField(18,2) max. `resolve_routing(requisition,
  *, rules=None, lines_by_req=None)` is the shared entry point - views batch-preload rules
  (select_related org_unit) and page lines ONCE (`_lines_map`) so commodity matching never
  costs a query per candidate rule.
- **RequisitionApproval** [RQA-] (`Approvals.py`, TenantNumbered "RQA"): append-only signature
  register. unique_together (tenant, requisition, tier) - SAFE because a rejected spine status
  is terminal (EDITABLE_STATUSES excludes rejected). tier_count SNAPSHOTTED per row so rule
  changes never rewrite what an approver signed; via_delegation FK stamps DOA credit;
  created ONLY through `record()` inside the deciding view's atomic block. Django admin is a
  fully read-only register (has_add/change/delete_permission False).
- **ApprovalDelegation** (`Delegations.py`, TenantOwned): dated grants delegator -> delegate,
  optional scope_org_unit, soft-recall via is_active. `active_for(tenant, user, org_unit_id)`
  answers "whose authority does USER hold" - it filters DELEGATE=user (direction matters!);
  exact-scope beats unscoped, newest wins among equals, expired/inactive never answer.
- **EscalationPolicy** (`Escalations.py`, TenantOwned singleton per tenant, tenant-unique via
  migration 0006): idle_hours (rule may override PER QUEUE where escalation_hours=0 means
  "escalate immediately" - only None falls back to policy) + escalate_to backup approver.
  Engine: `escalation_candidates(tenant, policy, *, rules, limit)` (idle anchor = last
  signature else created_at; rows carry window_is_rule / idle_hours_f / escalated) and
  `run_escalations(...)` raising kind=approval ProcurementAlerts (the 6.1 table explicitly
  anticipated this) - dedupe by open-alert-per-requisition probe, Run holds the POLICY ROW
  LOCK as the per-tenant mutex so concurrent Runs serialize, and passes limit=None so chains
  beyond the board cap still escalate.

### Decisions (views/Approvals.py)

`approval_decide` runs everything INSIDE transaction.atomic + select_for_update on the spine
row: closed-chain guard -> SELF-APPROVAL REFUSAL (requester != signer) -> resolve rule ->
elevated chains admin-only at EVERY tier -> FINAL tier always admin-only (it performs scm's own
field-for-field transition: status/approved_by/approved_at/decision_note) -> ApprovalDecisionForm
comment -> record signature (+audit tier_approve/tier_reject). Rejection flips the spine
rejected at ANY tier. Queue rows compute gate/may_decide for display via `_queue_row`.
GOTCHA: procurement forms/_common.py originally lacked TenantUniqueMixin - model clean() FK
guards falsely reject every CREATE without the instance.tenant stamp; the mixin was added to
_common and all three config forms mix it in.

### URLs / sidebar

`approvals/rules/...`, `approvals/{,history/,mine/,<pk>/approve|reject}`, `delegations/...`,
`escalations/{,run/}`. LIVE_LINKS["6.3"]: five bullets -> routingrule_list / delegation_list /
approval_history / escalation_queue / approval_mine.

### Seeder + tests

`_seed_approval_engine`: catch-all + department executive-band + commodity ("safety") rule
ladder, policy get_or_create (+escalate_to=admin), leave-cover DOA grant; records ONE real
tier-1 signature with approver=None (System) ONLY when the resolved chain has >=2 tiers -
never fabricates a completed chain over a pending spine. Tests:
test_awe_{models,forms,views,security}.py (27). Sandbox caveat: DB-backed pytest killed in
build sessions' shell (4th occurrence) - verified green via temp/verify_awe_63.py (35 checks)
+ temp/verify_awe_tests_63.py (22 checks) direct harnesses with tracked cleanup; re-run pytest
in a normal dev shell. Harness gotchas of record: MySQL tuple-startswith MATCHES NOTHING
(use Q() unions); probe PR lines must use quantity=1 or recalc_totals doubles intended bands;
purge stray probe RULES (not just requisitions) before asserting chain lengths.

---

## 6.6 RFx Management (RFI, RFP, RFQ) (built 2026-08-26)

**As-built now: 6.1-6.6 (+6.4/6.5 landing in parallel sessions).** Package folder `RfxManagement/`
across all four layers: `Events.py` = RfxEvent + RfxQuestion; `Responses.py` = RfxResponse +
RfxAnswer + the batch scoring helpers.

### Models

- **`RfxEvent` [RFX-]** (`NUMBER_PREFIX="RFX"`) — rfi/rfp/rfq (`RFX_TYPES`), title/description
  (supplier instructions), optional FK `scm.PurchaseRequisition` (`related_name="rfx_events"`,
  L36), status draft/issued/closed/cancelled, response_due, issued_at/closed_at/created_by
  (editable=False), `is_template` (True rows ARE the Template Library). `EDITABLE_STATUSES =
  ("draft",)` — issued questionnaires freeze so responses stay comparable;
  `LIVE_STATUSES = ("draft","issued")` gate new responses. Derived: `total_weight`,
  `possible_points` (=10 x scored weight). Actions return bool and are the ONLY status writers:
  `issue()` (needs >=1 question), `close()`, `cancel()`, `clone_as(user)` (copies header +
  questions via bulk_create — copies never links).
- **`RfxQuestion`** — child of event (no tenant column); section/prompt/help_text,
  `ANSWER_TYPES` text/longtext/number/date/choice, options (one per line),
  weight Decimal(5,2) >= 0, is_scored flag, `order`. `clean()` refuses choice-without-options.
- **`RfxResponse` [RXR-]** — unique `(event, supplier)`; supplier PROTECT ->
  `core.Party` (`related_name="procurement_rfx_responses"`); notes cover letter; `attachment`
  FileField `procurement/rfx/%Y/%m/`; submitted_at/recorded_by editable=False.
  `SUBMITTED_STATUSES = ("submitted","under_review","scored")`;
  `STATUS_FLOW` dict drives the ONLY legal moves through `transition(to)` (submit refused when
  event not accepting; no live transitions on a cancelled event); `is_locked` == disqualified.
  Scoring derived on read: earned_points / score_percent properties.
- **`RfxAnswer`** — unique `(response, question)`, answer_text (choice stores option verbatim),
  score 0-10 nullable; `weighted_points` None unless scored+scored-question.
- Batch helpers (module-level in Responses.py, re-exported by models/__init__):
  `earned_score_map(response_pks)`, `possible_points_map(event_pks)`,
  `weighted_percent(earned, possible)` (None when possible==0 — a None beats a flattering zero).

### Forms / Views / URLs

- Event form carries header + `RfxQuestionFormSet` (extra=2, max_num=60 validate_max;
  `save_new` appends after Max(order); set-level clean REFUSES non-draft events). Reorder is a
  POST verb `rfx_question_move` (direction up|down; draft-only; resequence-then-swap under
  select_for_update). Lifecycle verbs issue/close/cancel/delete are POST-only with guards in the
  model methods; delete allowed only for draft/cancelled events.
- Response create pre-creates ONE blank answer per question (bulk_create) so the edit workspace
  always mirrors the questionnaire exactly; `RfxAnswerFormSet` extra=0 can_delete=False
  max_num=60; per-row widget adapts to answer_type; crafted rows without id hidden fields skip
  type checks gracefully. `RfxResponseForm`: event field CREATE-only; accepts_responses checked
  on CREATE only (closed-event evaluation keeps saving); `_validate_attachment` allowlist
  (.pdf/.doc/.docx/.xls/.xlsx/.png/.jpg/.txt, 10 MB); foreign supplier rejected.
- Routes (names): `rfx_list` (+?compare=1 filter to events with n_submitted>=2), `rfx_create`,
  `rfx_detail`, `rfx_edit`, `rfx_delete`, `rfx_issue/close/cancel`, `rfx_question_move`
  (pk,q_pk), `rfx_compare`, `rfx_library`, `rfx_clone`, `rfx_scoring`;
  `rfx_response_list/detail/create/edit/delete/set_status`.
- Context contract: detail passes `questions`, `response_rows`
  ([{response,earned,possible,pct}]), `n_comparable` (drives Compare button); compare passes
  `responses` (best-first), `matrix` ([{question,cells}]), `scored_rows`; scoring passes
  paginated `object_list` of the same row dicts.

### Templates / Seeder / Tests

- `templates/procurement/rfxmanagement/{events/{list,detail,form,compare}.html,
  responses/{list,detail,form}.html, library.html, scoring.html}`.
- `_seed_rfx`: per-tenant guard; Template-Library RFI blueprint (5 typed questions) + issued
  "Managed print services RFP" (3 questions, optional spine PR attached) with Northwind fully
  scored (under_review) vs Cascade partial (submitted); audit baselines; suppliers get-or-create
  core.Party + supplier PartyRole by name (reuses seed_scm's names).
- Migration `0008_rfx_management` (RFX ops ONLY — 6.5's sourcing models ship their own 0009;
  one owner per migration, L43). Tests: `test_rfx_{models,forms,views,security}.py` (84 total,
  every function `test_rfx_*`). Sidebar: `LIVE_LINKS["6.6"]` maps all five NavERP.md bullets.



### 6.8 ContractsManagement

**6.8 Contract Management** - the CLM surface AROUND scm.SupplierContract (L36: the agreement spine,
its activate/renew/terminate verbs and SC- numbering stay scm's; procurement authors/signs/tracks).

Models (`apps/procurement/models/ContractsManagement/`, re-exported in the package __init__):
- `ContractClause` - pre-approved clause library (title/category/body/version/is_pre_approved/is_active);
  config posture, no numbering; writes tenant-admin gated.
- `ContractClauseLink` - contract x clause selection, `section_order`, `custom_text` negotiated override
  (`effective_text`); unique (contract, clause); PROTECT on clause so drafted language cannot vanish.
- `ContractSigner` - one signature slot: role internal/supplier (+optional core.Party binding),
  unique `token` = secrets.token_urlsafe(32) minted in save(); viewed/signed/declined_at + ip.
  Completion DERIVED (`all_signed` on the detail page), never written back to the spine.
- `ContractAmendment` [CAM-] - header-term proposals (end/value/auto_renew/notice_days, blank = term
  stands; form refuses nothing-to-amend); AMENDABLE_STATUSES draft/active/expiring; one OPEN per
  contract (`has_open_for`); approve -> `apply(decider, contract_locked)` writes only set terms under
  the CONTRACT row lock; reject terminal; `proposal_digest` for registers.
- `ContractMilestone` [CMI-] - deliverable/payment/penalty events with due_date/amount/status;
  complete/waive verbs stamp completed_by/at; decided rows frozen (edit/delete refused).
- Engine `Renewals.py`: `expiring_contracts(tenant)` = contracts inside their OWN notice window
  (`end_date - renewal_notice_days`, live statuses, dated ends only); `run_renewal_alerts` raises
  idempotent ProcurementAlert(kind=contract, link /scm/contracts/<pk>/).

Routes (first segments `clauses/ contracts/ contract-sign/ contract-amendments/ milestones/ renewals/`):
clause_list/_detail/_create/_edit/_delete; contract_list/_detail/_create + contract_add_link/
remove_link/add_signer/remove_signer; **contract_sign_page `contract-sign/<str:token>/` is PUBLIC**
(token = bearer credential, crm 1.9 flow; exclude token from admin); camendment_list/_detail/_create/
_approve/_reject (decisions admin-gated); milestone_list/_create/_edit/_complete/_delete;
renewals_board + renewals_run (admin).

Templates: `templates/procurement/contractsmanagement/{clauses,contracts,amendments,milestones}/`
(list/detail/form shapes) + `contracts/sign.html` (public, extends base_auth.html, escaped text only)
+ `contracts/renewals.html`.

Seeder: `_seed_contracts` (called after `_seed_eauction`) - 5-clause library, one authored master
agreement (SC- spine row + links + 2 signers + 3 milestones), one pending CAM amendment; guarded per
tenant. NOTE: until the 6.7 lane fixes `_seed_eauction`'s award step on Globex, seed_procurement aborts
the tenant loop there - call `Command()._seed_contracts(tenant)` directly if you need Globex data.
Tests: `tests/test_contracts_68.py` (12 green; run pytest with --no-migrations).

---

## 6.7 E-Auction Management (built 2026-08-26)

**As-built now: 6.1-6.8.** Package folder `EAuctionManagement/` across all four layers:
`Auctions.py` = Eauction + EaucInvite; `Bids.py` = EaucBid.

### Models
- **`Eauction` [EAUC-]** - reverse-only (`AUCTION_TYPES`; forward lands when its engine does).
  start/reserve price, `min_decrement`, anti-snipe trio (`extension_trigger_seconds`,
  `extension_seconds` >= 1, `max_extensions`) + read-only `extensions_used`. Statuses
  draft/scheduled/closed/awarded/cancelled; **live is DERIVED** (`accepts_bids` = scheduled AND
  window active) so each status has one writer. Actions return bool: `publish()` (needs invitee +
  future close), `close()` (manual early close allowed), `cancel()`, `extend_if_needed()` ->
  "extended"/"capped"/"no", `award(supplier, note)` (leader-only, once-guard, stamps
  awarded_amount/at; refusal attaches `.refusal_leader`). Derived: `best_bid()`, `rankings()`
  (one GROUP BY), `savings_vs_start()`, `time_left_display`.
- **`EaucInvite`** - unique (auction, supplier); own tenant column like RFQVendor.
- **`EaucBid` [EBID-]** - APPEND-ONLY log (admin fully read-only). `next_floor(auction, supplier)`
  is THE rule function: None when not live / not invited / ladder exhausted; first bid <= start;
  later bids <= own_best(Min aggregate) - min_decrement AND strictly below a rival-led best.
  `clean()` distinguishes not-open vs not-admitted vs too-high messages.

### Views / gating
`staff_required` decorator (tenant member or superuser) wraps EVERY eauc view EXCEPT
`eauc_bid` - vendor-portal logins (6.4 VendorPortalAccess) stay pinned to their bound supplier
there (`_bound_supplier`: any binding row, even inactive/unlinked, never widens to staff).
Routes: `eauc_list` (?state=live|closed deep-links), add/detail/edit/delete, publish/cancel/
close, `invite_add`, `invites/<i_pk>/remove`, `floor`, `rules`, `console`, `board` (HTMX
fragment polled every 5s only while live), `bid`, `results`, `award`. `_board_ctx(obj)` feeds
console/bid/board identically. Bid writes run full_clean + extend_if_needed under
select_for_update on the auction row; award re-fetches under lock.

### Templates / Seeder / Tests
`templates/procurement/eauctionmanagement/{auctions/{list,detail,form,console}.html,
bids/bid.html, floor.html, rules.html, results.html, board.html}` (board = fragment, no base).
`_seed_eauction`: per-tenant guard; an AWARDED auction with a 5-bid ladder (closes before award)
+ a LIVE auction whose closes_at already includes one extension. Flush deletes bids -> invites
-> auctions. Migration `0010_eauction_management` (e-auction ops ONLY). Tests:
`test_eauction_{models,forms,views,security}.py` (85, functions `test_eauction_*`). Sidebar:
`LIVE_LINKS["6.7"]` maps all five bullets (two via ?state= deep-links, rules page hosts the
enforcement bullet).

## 6.4 Vendor Management (built 2026-08-26)

### Models (`models/VendorManagement/`)
Three numbered rows over the scm 4.2 spine (L36: vendors ARE `core.Party`; onboarding/tier/risk
stay `scm.SupplierProfile` / `SupplierRiskAssessment` — the 6.4 sidebar bullets for those map to
the EXISTING scm pages, incl. `scm:supplierprofile_list?tier=strategic`):
- `VendorPortalAccess` [VPA-, TenantNumbered] — `supplier` FK Party SET_NULL, `portal_user`
  OneToOne user SET_NULL (one login = one vendor identity; several logins MAY share a supplier),
  `invited_by` (stamped by the hand-rolled `vpa_create`, NOT crud_create), `is_active`, `note`.
  `for_user(tenant, user)` is the single lookup every gated page makes first.
- `VendorSuspension` [VSU-] — kind suspension/blacklist, reason_category
  quality/delivery/compliance/financial/other, `po_reference` FK scm.PurchaseOrder SET_NULL,
  starts_on/ends_on, status requested→active|rejected→lifted with decided_*/lifted_* stamps.
  Properties `is_blocking/is_expired/is_current`; **`blocking_for(tenant, supplier_id)` answers
  only ACTIVE + unexpired** (`Q(ends_on__isnull=True) | Q(ends_on__gte=today)`). clean() uses
  `_id` guards — bare `getattr(self, "supplier")` raises RelatedObjectDoesNotExist on a cleared
  FK and WAS a live 500 (L-lesson: two-arg getattr does not swallow it).
- `VendorInvoiceSubmission` [VIS-] — supplier PROTECT, optional PO (clean() enforces
  po.vendor == supplier), invoice_ref/date/amount (q2-clamped in save), status
  submitted→under_review→accepted/rejected + reviewed_* stamps. NO GL posting ever; acceptance
  is a review decision, the bill stays keyed in Accounting AP.

### Views / URLs / Templates
`views/VendorManagement/{VendorPortalAccess,VendorSuspensions,VendorInvoiceSubmissions,Portal}.py`;
url names `vpa_*`, `vsu_*`, `vis_*`, plus `vendor_portal_home` / `vendor_invoice_new`.
Portal gating mirrors crm 1.4's refusal ladder in `_vendor_access()` — no row → refused,
NULL supplier → refused (never widen NULL into unlinked rows), blocked → read-only. The active
suspension rides to templates as **`suspension`, NEVER `block`** — Django pushes its own
BlockNode as context var `block`, so `{% if block %}` is always truthy and an `{% else %}` form
never renders (this exact bug shipped once; do not reintroduce it).
Lifecycle gates: vsu_edit wraps crud_edit inside `select_for_update` + status re-check (decided
rows immutable); vsu/vsu delete are pending-only ("requested" / "submitted"); invalid decision
notes bounce WITHOUT deciding (same contract as lift's mandatory reason); approve/reject share
ONE detail-page form whose buttons use `formaction` so the note travels with either decision;
the list's lift icon LINKS to detail (a bare POST could never carry the mandatory note).

**Enforcement is shared with SCM at its commitment verbs** (same-day follow-up): scm's
`purchaseorder_approve`/`purchaseorder_send` consult `blocking_for` via `_vendor_block`
(local import, read-only), so a blocked vendor cannot receive a new or dispatched PO; send
re-checks so a block filed after approval still stops dispatch. The portal also hosts
6.5's deferred gated **bid page** (`vendor_portal_bids/bid_edit/bid_submit`): own bids
only, drafts edited through `VendorBidForm` (event/supplier server-forced), submit reuses
`SourcingBid.submit()` under the bid+event double lock, blocked suppliers refused. Portal
home carries an **Invoices & payments** panel projecting accounting.Bill rows (read-only,
void excluded, balances derived) — SCM/accounting compute nothing here.
Tests: `test_vendormgmt_{models,forms,views,security}.py` (63, functions `test_vendormgmt_*`),
fixtures appended to `tests/conftest.py` (`supplier_a/b -> (profile, party)`, `po_a`, `vpa_a`,
`vsu_requested_a`, `vis_submitted_a`). Sidebar: `LIVE_LINKS["6.4"]` maps Onboarding/
Classification/Risk to the scm pages and Portal/Blacklisting to `vpa_list`/`vsu_list`.

### Seeder
`_seed_vendor_management`: per-register guards over scm APPROVED suppliers (skips without any);
access row + requested/active/lifted suspensions + accepted/submitted submissions per tenant.
Flush deletes all three registers. Migration `0007_alter_escalationpolicy_unique_together_and_more`.

## 6.9 Catalog Management (built 2026-08-26)

**As-built now: 6.1-6.9.** Package folder `CatalogManagement/` across all four layers.
The governed BUY-side layer OVER scm 4.2's simple `SupplierCatalog`/`SupplierCatalogItem`
price lists (never re-declared, L36): approval-gated catalog lines, effective-dated volume
pricing with its own propose->approve path (so price CHANGES route through the same gate as
new items), punch-out connection config, and supplier-hosted file intake.

### Models (`models/CatalogManagement/`)
- **`CatalogItem` [PCI-, `CatalogItems.py`]** - `source_type` internal/supplier_product;
  internal lines hard-FK verified `scm.Item` (+`scm.UOM`, `accounting.Currency`), supplier
  identity stays FREE TEXT (`name`/`supplier_part_no`/`description`) per L28; optional
  `scm.SupplierContract` FK = contract pricing. Status machine
  draft->pending_approval->approved/rejected->blocked/archived; EDITABLE draft/rejected only;
  actions submit/approve/reject/block/archive return bool + stamp once; `is_purchasable`
  property; `is_preferred`/`is_active`/`category_text` flags. Unique (tenant,number); indexes
  prc_catitem_tnt_status_idx / prc_catitem_tnt_item_idx.
- **`CatalogPriceTier` [no number, `Tiers.py`]** - child rows via related_name
  `price_tiers`: min_quantity/unit_price/discount_pct + valid_from/valid_until window +
  optional contract FK. Own lifecycle draft(proposed)->active->superseded/cancelled.
  **Invariant: exactly ONE active tier per (tenant,item,min_quantity)** - guarded in clean()
  AND re-checked inside approve() (review C1: two drafts could otherwise both activate).
  `effective_price(base)` q2-clamped; unique_together includes nullable valid_from.
- **`PunchOutEndpoint` [POE-, `PunchOutEndpoints.py`]** - cxml/oci/manual_link config per
  core.Party supplier. `shared_secret` is WRITE-ONLY: PasswordInput(render_value=False),
  form pops the field on edit, admin excludes it, `_redacted_changes` skips it in audit AND
  "shared_secret" now sits in `core.crud._SENSITIVE_AUDIT_FIELDS` belt-and-braces. Demo
  stores plaintext behind a WARNING - production must hash (tenants.EncryptionKey pattern).
  Live handshake DEFERRED (CRM webhooks SSRF-guard precedent); `record_session()` test verb
  stamps last_session_at only.
- **`CatalogUploadBatch` [CUB-, `UploadBatches.py`]** - supplier file intake. `.csv` ONLY
  allowlist (parser is CSV-text; xls/xml deferred with the real parsers), 2 MB cap +
  10k-row refusal (review I3). `validate_and_stage(user)` under ONE atomic block with a
  `select_for_update` status re-check (review I1): parses name,supplier_part_no,
  unit_price,uom_code,category_text -> stages items as **pending_approval** (bullet-3 gate
  holds even for malicious files), formula-injection cells prefixed `'` (M1), counters +
  line-numbered error_log editable=False.

### Views / URLs / Templates
Views `views/CatalogManagement/{CatalogItems,Tiers,PunchOutEndpoints,UploadBatches}.py`;
url first segments `catalog-items/ catalog-tiers/ punchout/ catalog-uploads/`; names
`catalog_item_* catalog_tier_* punchout_endpoint_* catalog_upload_*` (+ verbs
submit/approve/reject/block | approve/retire | test | validate/publish/reject).
**Decision verbs are @tenant_admin_required** (maker-checker, review I2) while members keep
viewing rights, item submit, tier propose and the endpoint test stamp. Hand-rolled form views
stamp created_by/submitted_by CREATE-only; edit gates honor EDITABLE_STATUSES. Templates
`templates/procurement/catalogmanagement/<entity>/{list,detail,form}.html`; tier filter
selects compare `{% if request.GET.catalog_item == it.pk|stringformat:"d" %}` (the swapped-
operand bug shipped once in review F-01/I4 - do not reintroduce).

### Seeder / Tests
`_seed_catalog(self, tenant)` in seed_procurement.py: approved+preferred internal line w/
two active tiers, pending supplier product, blocked line, two punch-out endpoints (cXML+
manual-link), one validated batch (8 parsed/6 accepted/2 rejected + error_log). Reuses
seed_scm's Item/UOM/Currency + `_catalog_supplier` alias of the shared supplier helper;
per-entity guards; friendly skip without scm.Item. Flush deletes tiers->items->batches->
endpoints. Migration `0013_catalogitem_...` (+0014 related_name prefixes).
Tests: `test_catalogmgmt_{models(27),forms(20),views(31),security(14)}.py` - functions
`test_catalogmgmt_*`, fixtures appended to conftest (uom_a/item_a/catalog_item_*_a/
tier_active_a/punchout_endpoint_a/upload_batch_received_a). Sidebar: `LIVE_LINKS["6.9"]`
maps all five bullets (approval deep-links ?status=pending_approval).

## 6.11 Order Fulfillment & Tracking (built 2026-08-29)

**As-built now: 6.1-6.11.** Package folder `OrderFulfillment/` across all four layers.
The INBOUND-visibility layer over the scm 4.1 order spine: what the supplier says is coming,
when each instalment is due, and what is short. 6.11 is **READ-ONLY against `scm.PurchaseOrder*`**
- it never writes `PurchaseOrderLine.quantity/unit_price` (6.10's `PurchaseOrderChange.apply()`
is the only spine mutator) and never books a receipt/QC/StockMove (that is 6.12).

**Why there is no tracking-event table (L36):** scm 4.6 TMS already owns inbound freight -
`scm.Shipment` (`direction="inbound"`, `purchase_order` FK) plus the append-only
`scm.TrackingEvent` and the editable=False projections `current_status_text`/
`last_known_location`/`eta`. 6.11 holds a **nullable `shipment` FK and READS those projections**
with the supplier-declared `carrier`/`carrier_name`/`tracking_number` as fallback. It never
creates a Shipment and never appends a TrackingEvent. Likewise `inventory.PurchaseOrderDispatch`
is the OPPOSITE direction (buyer->supplier transmission) - not a duplicate.

### Models (`models/OrderFulfillment/`)
- **`AdvancedShipmentNotice` [ASN-, `AdvancedShipmentNotice.py`]** - the supplier's declaration
  of what is in the box, against one `scm.PurchaseOrder` (PROTECT). Status
  draft->submitted->in_transit->delivered / cancelled; `OPEN_STATUSES`/`IN_FLIGHT_STATUSES`/
  `EDITABLE_STATUSES` class constants. Verbs `submit/mark_in_transit/confirm_delivery/cancel`
  **re-check their own guard inside the method** so a double-submit cannot re-stamp
  `delivered_at` or the POD block (all editable=False, written only by the verb). Flat packing
  cube (`package_count`/`pallet_count`/`gross_weight_kg`/`volume_cbm`) - deliberately NOT a
  recursive pallet->carton tree. `source` = portal/email/edi/manual is the provenance column
  the deferred EDI 856 intake will write. `supplier_reference` is the hand-off hook to
  `scm.GoodsReceiptNote.delivery_note_ref` in 6.12.
- **`AsnLine` [no number, same file]** - tenant-less child (the `PurchaseOrderChangeLine`
  precedent) FK'd to `scm.PurchaseOrderLine`. **No item FK - `core.Item` does not exist (L28)**,
  so it MIRRORS the PO line free text (`item_description`/`sku_hint`/`uom_hint`, auto-copied
  when blank). Lot/serial/expiry/country are the supplier's PRE-ARRIVAL declaration as plain
  text; the real `scm.LotSerial` row is created at receipt (6.12). Derived
  `outstanding_at_declare`/`variance`/`shortfall`/`is_short` feed the detail page's discrepancy
  verdict and the prefilled "record the shortfall" backorder link.
- **`DeliverySchedule` [DSC-, `DeliverySchedule.py`]** - Coupa's four columns on one row: buyer
  `scheduled_quantity`/`need_by_date` vs supplier `promised_quantity`/`promised_date`, plus
  `ship_to`->`core.OrgUnit`. **Status stays editable on the form by design** - this ladder hangs
  no timestamps off its status, so it needs no verbs. `clean()` HARD-BLOCKS over-commitment past
  the ordered quantity; under-coverage is only a derived warning. `split_po_line()` divides the
  **UNCOMMITTED remainder** into K evenly spaced rows with the last absorbing the rounding
  remainder, entirely inside `transaction.atomic()` holding `select_for_update()` over the
  line's existing rows so two buyers cannot both over-commit.
- **`Backorder` [BKO-, `Backorder.py`]** - the recorded shortfall: reason (7 choices),
  `original_`/`revised_promise_date`, and a `reschedule_count` only `reschedule()` may move.
  Verbs `reschedule/fulfil/cancel` re-validate inside themselves; `raise_alert()` is idempotent
  and builds `link_url` via `reverse("procurement:backorder_detail", ...)` because
  `ProcurementAlert.clean()` rejects anything that is not a single-slash internal path.
  Risk buckets past_due/at_risk/no_commitment/on_track are **derived, not stored**, and the
  `?risk=` filter is expressed as ORM date arithmetic BEFORE pagination (a Python-side bucket
  filter would make the page counts lie).

### Views / URLs / Templates
Views `views/OrderFulfillment/{AdvancedShipmentNotice,DeliverySchedule,Backorder,FulfillmentBoards}.py`
(26 functions). Url first segments `asn/ delivery-schedules/ backorders/ inbound-tracking/
delivery-confirmation/`; literal `add/`+`split/` declared BEFORE `<int:pk>/` (first-match-wins).
Names `asn_* deliveryschedule_* backorder_*` + the two boards `inbound_tracking` /
`delivery_confirmation`. **All mutation verbs are POST-only, atomic and row-locked; deletes are
`@tenant_admin_required` and the list/detail buttons carry the SAME gate** (review I7/I8 - a
member must not see a button the view will refuse).
`FulfillmentBoards.py` holds **two computed boards with zero new state**: `inbound_tracking`
(in-flight ASNs, soonest arrival first, reading the 4.6 projections) and `delivery_confirmation`
(today/overdue/awaiting/confirmed-7d buckets, whitelist-sanitized so `?due=zzz` still renders
200, and the inline confirm form posts to the existing `asn_confirm_delivery` verb rather than a
second confirm path). Templates
`templates/procurement/orderfulfillment/{asn,deliveryschedule,backorder}/{list,detail,form}.html`
+ `deliveryschedule/split.html`, with the two boards at the **sub-module root**
(`inbound_tracking.html`, `delivery_confirmation.html`) per the `purchaseordermanagement/
linetracking.html` precedent.

**Query traps already paid for (do not reintroduce):** `PurchaseOrderLine.outstanding_quantity()`
calls `received_quantity()`, which is ONE GRN aggregate PER LINE - `asn_detail` seeds the
per-instance cache from `purchase_order.received_by_line()` (1 query, not N). The ASN form's
`purchase_order` dropdown needs `select_related("vendor")` because `PurchaseOrder.__str__` hops
to `core.Party`. `confirmed_by` is select_related on the confirmation board ONLY (the tracking
board never renders it).

### Seeder / Tests
`_seed_order_fulfillment(self, tenant)` in seed_procurement.py: reuses a **receivable PO whose
line still has an outstanding balance** (review I2 - picking `lines[0]` blindly landed on a
fully-received line, so the shortfall folded to `over` with `shortfall == 0` and the whole
ASN->backorder hand-off was unreachable from demo data), one in-flight ASN with a deliberately
short first line, one ASN taken to delivered through the REAL `confirm_delivery` verb so the POD
block is stamped exactly as the view stamps it, a three-instalment ladder keyed on
(po_line, sequence), and two backorders with different risk shapes. Flush order:
backorders -> schedules -> ASN lines -> notices. Migration `0016_advancedshipmentnotice_...`.
Tests: `test_fulfillment_{models(202),forms(77),views(105),security(36)}.py` - functions
`test_fulfillment_*`, fixtures `fulfillment_*` appended to conftest. Sidebar: `LIVE_LINKS["6.11"]`
maps all five bullets (Real-time Freight Tracking -> the board, not a table).

## 6.12 Goods Receipt & Inspection (built 2026-08-30)

**As-built now: 6.1-6.12.** Package folder `GoodsReceiptInspection/` across all four layers.

**Read this before adding anything here: SIX of the ten NavERP.md bullets were ALREADY BUILT and are
MAPPED, not rebuilt (L36).** Grep-verified at build time:

| Bullet | Already owned by |
|---|---|
| Inventory Posting | `apps/scm/views/_helpers.py:299` `_post_grn_receipt` — real row-locked `StockMove` legs |
| Receipt Reversal & Audit Trail | `:335` `_reverse_grn_receipt` — compensating legs, refuses after putaway |
| Quality Inspection Checklists | `inventory.QcChecklist`/`QcRoutingRule`; `scm.QualityInspection` already FKs `goods_receipt` |
| Quarantine & Inspection Hold | `inventory.QuarantineOrder` [QRD-] |
| Lot, Batch & Serial Capture | `scm.LotSerial` (`unique_together = (tenant, item, number)`) |
| Item Tagging & Barcoding | `inventory:barcodelabel_list` / `scan_console` / `putaway_suggestions` |

`apps/quality` does **not** exist (Module 12 is future). SCM 4.9 owns
`InspectionPlan→QualityInspection→NonConformance`; inventory 5.15 owns the QC/quarantine registers.
**6.12 owns only the COMMERCIAL consequence** — the discrepancy claim and the vendor return — and
points at the rest through nullable `SET_NULL` FKs. Do not open a third quality register.

### Models (`models/GoodsReceiptInspection/`)
- **`ReceiptTolerancePolicy` [no number, `ReceiptTolerances.py`]** — `TenantOwned` config master, no
  status column. Over/under pct + absolute `over_receipt_qty`, `allow_unlimited_over_receipt`,
  `early_receipt_days`/`late_receipt_days`, `action` none/warn/block_flag. Scoped by `item` XOR
  `category` (clean() rejects both) plus an optional `vendor` pin. **No `unique_together` — overlapping
  rules are LEGAL by design**, which is why the resolver, not the schema, decides. Ships THREE
  module-level functions, deliberately split so selection and judgement are separately testable:
  `resolve_receipt_tolerance()` (tier 3 item > 2 category > 1 catchall → vendor-pinned beats
  vendor-agnostic → priority ASC → id ASC; a vendor-pinned rule NEVER fires for another vendor;
  refusals start `"No Rule Matched"`), `evaluate_receipt_tolerance()` (**quantity breaches outrank
  date breaches**; with both `over_receipt_pct` and `over_receipt_qty` set the MORE RESTRICTIVE wins;
  with neither, tolerance is ZERO), and `resolve_line_item()` — a LOCAL MIRROR of scm's private
  `_resolve_grn_item`, never a cross-app import. Shape cloned from `resolve_qc_routing`
  (`apps/inventory/models/QualityControl/QcRoutingRules.py:89`) — read that first.
- **`ReceiptDiscrepancy` [RDS-, `ReceiptDiscrepancies.py`]** — the claim against a receipt. FK
  `scm.GoodsReceiptNote` (PROTECT) + optional `goods_receipt_line` (**blank = a header-level
  finding**). 7 kinds, severity, `evidence` FileField + `evidence_url`, `remedy`
  pending/replacement/credit/rtv/accept_as_is/scrap. `status` is `editable=False`, moved only by
  `notify_vendor`/`resolve`/`cancel`, each re-checking its guard INSIDE so a second call returns
  False and changes nothing. Three nullable escalation POINTERS (`scm.NonConformance`,
  `inventory.QuarantineOrder` — the typed anchor its free-text `reference` cannot give — and the RTV).
  `save()` mirrors the PO line's free text only when `update_fields is None`.
- **`ReturnToVendor` [RTV-] + `ReturnToVendorLine` (`ReturnsToVendor.py`)** — genuinely absent before
  this: `scm.ReturnAuthorization` is the CUSTOMER RMA and `WarrantyClaim` is post-sale.
  `draft→authorized→shipped→closed`/`cancelled`. `expected_credit_value` is DERIVED, never stored.
  `has_duplicate_rma` is ADVISORY and never blocks.

> **An RTV posts NO `StockMove` and NO `JournalEntry`, and that is correct — do not "fix" it.**
> Defended from code, not asserted: `_post_grn_receipt` (line 319) reads
> `qty = line.quantity_received or ZERO`, so dock-rejected quantity never entered the ledger and
> there is nothing to remove. The 6.12 security test lane asserts zero new rows after an authorize.

### Views / URLs / Templates
Views `views/GoodsReceiptInspection/{ReceiptTolerances,ReceiptDiscrepancies,ReturnsToVendor,ReceiptBoards}.py`.
Names `tolerancepolicy_* discrepancy_* rtv_*` plus verbs (`discrepancy_notify_vendor/resolve/cancel`,
`rtv_authorize/ship/close/cancel`) and the three boards `receiving_console` (+`_book`, `_mint_lots`),
`tolerance_exceptions`, `receipt_audit`. Templates
`templates/procurement/goodsreceiptinspection/{tolerancepolicy,discrepancy,rtv}/{list,detail,form}.html`
with the three boards at the **sub-module root**. `receiving_console` finally closes the ASN→GRN
hand-off 6.11 deferred, keyed `AdvancedShipmentNotice.supplier_reference` →
`GoodsReceiptNote.delivery_note_ref`.

**Traps already paid for (review + fixes) — do not reintroduce:**
- A blank `supplier_reference` had no stable delivery-note key, so three book POSTs created THREE
  receipts. The key is normalized (case/padding-insensitive) and there is ONE definition of
  "same delivery note".
- An RTV line's ordered line must match the header's **order AND supplier** — a return to supplier A
  could otherwise be built on supplier B's line and quote credit off the wrong price. Enforced in
  `clean()` AND by narrowing the widget.
- Editing an RTV whose receipt was cancelled afterwards silently saved `goods_receipt = NULL`;
  the stored value is now exempted from the cancelled-receipt exclusion.
- `_item_map` must pre-filter SKUs in SQL (`Lower("sku")` + `__in`), never read the whole item master.
- The RTV line formset shares its rendered options via `_construct_form` — NOT `__init__`, which
  forces the `forms` cached_property to build eagerly and freezes rows against the pre-edit header.
- `apps/core/forms/_common.py` `MAX_UPLOAD_BYTES` is 20 MB but
  `forms/CatalogManagement/UploadBatches.py:13` defines a DIFFERENT 2 MB one. Import the core pair
  LOCALLY; **never re-export either from `forms/__init__.py`**.
- Do NOT add the new models to `PROCUREMENT_CONTENT_MODELS` — that tuple is the *scm*-app whitelist;
  `Q(content_type__app_label="procurement")` already covers them.

### Seeder / Tests
`_seed_goods_receipt(self, tenant)` in seed_procurement.py, guarded per tenant. Migrations `0017`
(+`0018` vendor SET_NULL→CASCADE fix, `0019` `(tenant, supplier_rma_number)` index).
Tests: `test_receipt_{models(234),forms(143),views(140),security(47)}.py` — functions
`test_receipt_*`, fixtures `receipt_*` in conftest. Sidebar `LIVE_LINKS["6.12"]` has 10 keys, 6 of
them pointing at the existing scm/inventory pages above.

## 6.14 Spend Analytics & Reporting (built 2026-09-01)

**As-built now: 6.1-6.14.** Package folder `SpendAnalyticsReporting/` across all four layers, plus a
new single-writer compute module `apps/procurement/analytics.py`.

**Read this first: 6.14 is the INVOICED twin of an existing cube, not a new one.** SCM 4.11 already
ships `scm:spend_analytics` (`apps/scm/analytics.py`), a **committed/PO-based** spend cube. Its own
header caveat records why it is limited: `scm.PurchaseOrderLine` has **no `Item` FK** (free-text
`item_description` + `sku_hint` only), so its category axis is GL-account-based and any per-SKU
figure is a best-effort text match. 6.13's `SupplierInvoiceLine` **does** carry real `item` and
`gl_account` FKs and sees PO-less/service spend that 4.11 structurally cannot. So:

* 6.14's default basis is **invoiced** — `SupplierInvoiceLine` filtered
  `invoice__status__in ("approved","scheduled","paid")` (`RECOGNISED_INVOICE_STATUSES`).
* Committed (PO) spend ships as a **second selectable basis** (`SPEND_PO_STATUSES`).
* `spend_dashboard` **links to** `scm:spend_analytics`; it never duplicates it. That link and 4.11's
  own "Procurement Analytics" bullet must both keep resolving after any edit here.

### Models (`models/SpendAnalyticsReporting/`)

| Model | Base / number | Notes |
|---|---|---|
| `SpendClassificationRule` | `TenantOwned` — **no number** | Config master, not a document |
| `MaverickSpendFinding` | `TenantNumbered` `MSF-#####` | The off-policy purchase register |
| `SpendReport` | `TenantNumbered` `SPR-#####` | Saved report definition |
| `SpendReportSnapshot` | plain `models.Model` child | Minted **only** by the snapshot POST |

**`SpendClassificationRule`** (`SpendClassificationRules.py:184`) is the honest, non-ML answer to
"spend classification" — a readable, auditable, priority-ordered rule ladder, which is also what
Ivalua markets as its differentiator. `MATCH_TYPE_CHOICES` = vendor / gl_account / keyword /
invoice_type / org_unit; `APPLIES_TO_CHOICES` = both / invoiced / committed. `category` (to
`scm.ItemCategory`) is the **one non-nullable FK** and is `PROTECT`; vendor/gl_account/org_unit are
`SET_NULL`. **No `unique_together` at all** — two same-shaped rules at different priorities are legal
by design. `Meta.ordering = ["priority", "id"]`, lower priority wins.

* `line_filter(basis)` returns a `Q` **or `None`**, and `None` means *"this rule can match nothing on
  this basis"* — **never** treat it as "no filter", or the rule matches everything.
* `match_count` / `last_matched_at` are `editable=False` usage stamps written **only** by
  `spendrule_preview`. They are not form fields.
* Never call this "AI" or "ML". It is a rules engine.

**`MaverickSpendFinding`** (`MaverickFindings.py:132`) has 8 `REASON_CHOICES` — `no_contract`,
`po_less_invoice`, `no_requisition`, `off_catalog`, `non_preferred_vendor`, `price_above_contract`,
`suspended_vendor`, `split_purchase` — each mapped to a default severity via `SEVERITY_BY_REASON`.
Status flow: `open`/`acknowledged` (both open) to `justified`/`remediated`/`dismissed` (terminal).

* `unique_together = (("tenant","number"), ("tenant","dedupe_key"))`. `dedupe_key` is **derived** in
  `save()` and is what makes `scan()` **idempotent** — a re-scan of an unchanged window raises zero
  new rows and preserves every existing disposition. Fixtures must vary reason *or* the source
  pointer or they collide.
* `leakage_amount` is derived as `max(0, amount - benchmark_amount)` and is `editable=False`;
  `amount` itself **is editable** (a hand-raised finding needs it, otherwise it is always 0).
* `status`, `resolution_note`, `resolved_by`, `resolved_at`, `detected_at`, `dedupe_key` and
  `leakage_amount` are all `editable=False` — moved only by the verbs, each re-checking its own guard.
* `maverickfinding_delete` is `@tenant_admin_required` **and** refuses a disposed finding. That is
  deliberate (review C1): deleting a justified/remediated row would erase the recorded decision and
  achieve exactly what the admin gate exists to prevent.

**`SpendReport` + `SpendReportSnapshot`** (`SpendReports.py:111` / `:253`) mirror
`crm.AnalyticsReport` / `crm.ReportSnapshot` field-for-field — read those before changing anything
here. **`SpendReportSnapshot` has no form and no create/edit view by design**; it is minted only by
the `spendreport_snapshot` POST. That exemption is recorded in the view module docstring so a
CRUD-completeness reviewer reads it as a decision, not a gap.

### The compute layer (`apps/procurement/analytics.py`)

Every page is computed; there is no materialized cube. Key entry points: `range_bounds()`,
`invoiced_lines()`, `spend_cube()`, `compute_report()`, `maverick_rate()`, `active_rules()`.

* `spend_cube(..., total=, rules=)` — pass both through the two-axis loop in `compute_report`, or you
  re-issue a `SUM` and a rules query **per first-axis row** (up to ~300 queries at `top_n=100`).
* `range_bounds()` clamps to `_MAX_BOUND = date(9999, 12, 30)` **before** adding the exclusive-stop
  day. Without the clamp, `?range=custom&date_to=9999-12-31` raises `OverflowError` and 500s the
  page — and the model `clean()` permits that date, so a *saved* report 500s permanently.
* `maverick_rate()` divides by a **distinct flagged-invoice** numerator, not a sum of finding
  amounts. Several findings can hit one document, so the naive sum is unbounded (it rendered 562%
  under a legend claiming 10%/20% thresholds). `maverick_value` is a different figure — the
  value-at-risk the `maverick_spend` measure returns — and deliberately keeps its own meaning.

### URLs / routes (`app_name = "procurement"`)

Computed pages: `spend_dashboard` · `category_spend` · `classification_workbench` ·
`maverick_dashboard` · `spend_export` · `spend_export_download` · `maverick_scan`.
CRUD: `spendrule_{list,detail,create,edit,delete}` + `spendrule_preview`;
`maverickfinding_{list,detail,create,edit,delete}` + `maverickfinding_disposition`;
`spendreport_{list,detail,create,edit,delete}` + `_run` / `_export` / `_favorite` / `_snapshot`;
`spendreportsnapshot_{detail,delete,export}`. Literal segments are registered **before** `<int:pk>`.

### Templates (`templates/procurement/spendanalytics/`)

Folder is `spendanalytics/`, **not** `spendanalyticsreporting/` — the short-slug precedent is
`approvalworkflow/` for `ApprovalWorkflowEngine`. Do not "correct" it.
Root pages: `dashboard.html` · `category_spend.html` · `classification_workbench.html` ·
`maverick_dashboard.html` · `export.html`. Entity folders: `spendrule/{list,detail,form}.html` ·
`maverickfinding/{list,detail,form}.html` · `spendreport/{list,detail,form}.html` ·
`spendreportsnapshot/detail.html`.

### Seeder

`_seed_spend_analytics(tenant)` seeds the rule ladder, findings across their lifecycle, saved reports
and a snapshot. `_seed_spend_baseline(tenant, categories, members)` seeds nine recognised-spend
invoices so the cube has something to aggregate. Both idempotent — a second `seed_procurement`
reports "spend baseline invoices already present" / "0 newly raised".

### Conventions & gotchas

* **No FX-rate table exists anywhere in this repo.** Money is summed **at face value per currency**;
  a window spanning more than one currency sets `mixed_currency=True` and the page renders
  `currency_rows` instead of one meaningless total. Never invent a rate.
* **`accounting.Currency` is GLOBAL — it has no tenant column. Never tenant-filter it.**
* **The department axis is weak and must say so.** There is no department column on an invoice; it is
  a 3-hop nullable chain `Coalesce("invoice__purchase_order__requisition__org_unit",
  "invoice__purchase_order__ship_to")` to `core.OrgUnit`, **NULL for every PO-less invoice**. Every
  department breakdown MUST render an explicit `UNASSIGNED_LABEL = "(unassigned)"` bucket and print
  `department_caveat` — a breakdown that silently drops rows makes the totals disagree with the KPI
  strip.
* **On the committed basis there is no item taxonomy** — category resolves through
  `SpendClassificationRule` only, else `UNCLASSIFIED_LABEL = "(Unclassified)"`. Do not fake an item join.
* **Credit-memo lines are already signed negative**, so a plain `Sum` nets correctly. Never
  special-case them.
* **6.14 writes NOTHING to `accounting.*`** — no Bill, no JournalEntry, no Payment (L29). It is a
  read-only analytics pass.
* Suppliers are `core.Party` + `core.PartyRole` role in `("supplier","vendor")`. There is no vendor
  table. The `scm.SupplierContract` FK is **`party`**, not `vendor`.
* `scm.ItemCategory` is the **only** taxonomy in the tree. `procurement.CatalogItem.category_text` is
  free text and is never a taxonomy key.

### Two contractual naming bans (both survive every edit)

1. **"drag and drop" must not appear** in code, templates, sidebar labels or commit messages. Only
   one surveyed product actually ships it; NavERP ships a **guided** builder (measure, dimensions,
   window and Top-N chosen from dropdowns). The comment in `navigation.py` that *denies* the builder
   is drag-and-drop is deliberate and must stay — it guards the label against a future session
   "correcting" it to match the aspirational NavERP.md bullet.
2. **No label may imply a BI/PowerBI connector.** Export is **CSV/XLSX download only**; the export
   page states this verbatim rather than letting the sidebar imply a live feed.

### Sidebar wiring

`LIVE_LINKS["6.14"]` in `apps/core/navigation.py` maps all five NavERP.md bullets:
`Spend Dashboards` to `spend_dashboard`; `Custom Report Builder` to `spendreport_list`;
`Category Spend Analysis` to `category_spend`; `Maverick Spend Tracking` to `maverick_dashboard`;
`Data Export & Visualization` to `spend_export`. The rule register, workbench and snapshots take **no
sidebar key** (the `ReceiptTolerancePolicy`/`KpiTarget` master precedent) — they are reached from
`category_spend` and `classification_workbench`, and snapshots from their parent report.
