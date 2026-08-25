---
name: procurement
description: Work on the Procurement module (Module 6 — Procurement Management System). As-built = 6.1 User Dashboard & Portal (personalized overview with per-user widget preferences, Task & Alert Center with acknowledge/resolve lifecycle, quick requisition entry drafting into scm.PurchaseRequisition, audit-log-derived activity feed, self-service reports + own-requisitions CSV export) and 6.2 Requisition Management (tracking register + audit-trail timeline detail over scm.PurchaseRequisition, explainable duplicate-requisition engine with ?dupes=1 deep-link, RequisitionTemplate[RQT-] recurring-order blueprints with apply-into-draft, RequisitionAmendment[RAM-] gated cancel/amend workflow) and 6.3 Approval Workflow Engine (ApprovalRoutingRule dept x commodity x half-open band -> tier count with most-specific-wins resolver, RequisitionApproval[RQA-] append-only signature register under spine row locks with self-approval/elevated/final-tier admin gates, ApprovalDelegation DOA grants stamped via_delegation, EscalationPolicy + idempotent Run engine raising 6.1 alerts, mobile approval surface) and 6.5 Sourcing & Tendering (SourcingEvent[SEV-] tender/RFP/RFQ events draft->open->closed->awarded/cancelled with verb-only transitions + EventCriterion weight<=100 matrices, SourcingBid[BID-] whole-package bids with row-locked submit/shortlist/disqualify that can never overwrite an award, BidScore matrix scored on bid detail with NaN-proof validation and ONE shared weighted_total formula, computed award board (~4 queries/20 scenarios) with admin-gated won/lost writer, None-honest sourcing analytics). Use when the user asks to add/change/debug anything under apps/procurement or templates/procurement, extend the seed_procurement seeder, touch procurement sidebar wiring (LIVE_LINKS 6.1/6.2/6.3/6.5/6.8), or invokes /procurement.
---

# Procurement — Procurement Management System (Module 6)

App path: `apps/procurement`. Templates: `templates/procurement/`. URL prefix: `/procurement/`,
`app_name = "procurement"`. Mirrors `NavERP.md` "## 6. Procurement Management System" (19
sub-modules, 6.1–6.19).

**As-built: 6.1–6.3 + 6.5 built here; 6.4 Vendor Management & 6.6 RFx landed from their own
sessions (6 of 19).** Build the next one with `/next-module` (it takes the lowest `6.M`
without a `LIVE_LINKS["6.M"]` entry) — see the reference apps `apps/crm`/`apps/accounting`
for the package layout and the mandatory Module Creation Sequence.

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
