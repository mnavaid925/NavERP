# Procurement 6.5 — Sourcing & Tendering — research (frozen contract)

Built in parallel with the in-flight 6.4 session (L45): BASE `6b02fb55`, migration
**0008 claimed for 6.5**, `0007` reserved for 6.4's vendor tables (landed + applied at ~00:12).
All 6.5 files are NEW paths; registry-visible edits (re-exports, admin, seeder, navigation)
deferred until after 0007 existed.

## Positioning vs the spine (L29/L36)

`scm.RFQ`/`RFQQuote` (4.1) own OPERATIONAL quote requests: line-by-line pricing against one RFQ.
6.5 is the STRATEGIC layer above that: sourcing events with rules and timelines, weighted
evaluation criteria, scored bids, award scenarios and post-event analytics. scm has no
evaluation/scoring concept at all, so 6.5 declares its own tables rather than stretching the RFQ.
The bid-submission PORTAL surface stays deferred to a 6.4 follow-up (it would need the
uncommitted `VendorPortalAccess` binding; coupling to another session's uncommitted work is
forbidden) — bids are staff-captured this pass, `submitted_by` recorded, portal noted as the
extension point in docstrings.

## Models (`models/SourcingTendering/`)

**SourcingEvents.py**
- `SourcingEvent` [SEV-] (TenantNumbered, NUMBER_PREFIX="SEV"): title, description,
  event_type tender/rfp/rfq, status draft/open/closed/awarded/cancelled with
  `EDITABLE_STATUSES = ("draft", "open")`; currency FK accounting.Currency SET_NULL
  (GLOBAL table — scope by is_active in forms); optional `requisition` FK
  `scm.PurchaseRequisition` SET_NULL related_name="sourcing_events" (traceability only);
  `budget_estimate` Decimal(14,2) NULLABLE (None = unknown — analytics answers None, never a
  flattering zero); opens_at/closes_at DateTimes; rules TextField; created_by editable=False;
  awarded_at editable=False. **No FK event→bid**: the award lives on the bid side
  (`status="won"`), so the two entity modules never reference each other's classes.
  Meta: ordering ["-created_at","-id"], unique ("tenant","number"), index (tenant,status).
  Helpers: `is_editable`, `bids_allowed` (status=="open"), `has_criteria`.
- `EventCriterion`: event CASCADE related_name="criteria"; name (unique per event);
  weight_pct Decimal(5,2) (0 < w ≤ 100); max_score PositiveInt default 10; description blank.
  No own tenant column (pure child, TemplateLine pattern).

**Bids.py**
- `SourcingBid` [BID-] (TenantNumbered "BID"): event CASCADE related_name="bids";
  supplier FK core.Party PROTECT related_name="procurement_sourcing_bids";
  status draft/submitted/shortlisted/disqualified/won/lost;
  `EVALUABLE_STATUSES = ("submitted", "shortlisted")`;
  total_price Decimal(14,2) ≥ 0 (whole-package header price — line pricing stays scm's);
  lead_time_days PositiveInt null; is_compliant default True + compliance_note;
  summary TextField; contact_ref Char(120); submitted_by/submitted_at editable=False.
  Meta ordering ["-created_at","-id"], unique ("tenant","number"),
  indexes (tenant,event)/(tenant,status).
  Methods: `submit(user)` (draft→submitted, guards event.bids_allowed),
  `weighted_score(criteria=None)` → Decimal 0..100 or None when no criteria; divides by TOTAL
  defined weight (partial scoring reads honestly lower), scores read via one query.
- `BidScore`: bid CASCADE related_name="scores"; criterion CASCADE related_name="scores";
  score Decimal(6,2) ≥ 0; note blank; unique ("bid","criterion");
  clean(): score ≤ criterion.max_score AND criterion.event_id == bid.event_id.

## Forms

`SourcingEventForm` (excludes tenant/number/status/awarded_at/created_by/requisition? NO —
requisition IS on the form as an optional tenant-scoped choice) +
`CriterionFormSet` = inlineformset_factory(event, EventCriterion, extra=1, can_delete=True,
max_num=20 validate_max) whose formset clean() errors when Σ weight_pct > 100.
`SourcingBidForm` — event queryset limited to non-terminal events (draft/open/closed for edit);
supplier queryset = local `_supplier_parties(tenant)` copy (roles supplier∪vendor, distinct).

## Views / URLs (names)

events: `event_list` (q number/title/description; filters status,event_type) · `event_detail`
(criteria + bid table w/ precomputed weighted scores + lifecycle buttons + award panel) ·
`event_create/edit/delete` (delete refuses when bids exist) · POST-only `event_open`,
`event_close`, `event_cancel`, `event_award` (bid pk in POST).
bids: `bid_list` (filters status,event) · `bid_detail` (+ scoring-matrix POST handler, manual
parse validated 0..max_score) · `bid_create/edit/delete` (edit locked once submitted; delete
draft-only) · POST-only `bid_submit`, `bid_shortlist`, `bid_disqualify` (reason required).
awards: `award_board` — closed+not-awarded events with ranked compliant candidates and the
recommended row highlighted.
analytics: `sourcing_analytics` — computed post-event analysis.

Shared ranking helper `evaluate_event(event)` lives in `views/_helpers.py` (two surfaces use
it). PROCUREMENT_CONTENT_MODELS += "sourcingevent", "sourcingbid".

Routes: `events/…`, `bids/…`, `awards/`, `analytics/` — all-new first segments, no shadowing.

## Templates (`templates/procurement/sourcingtendering/`)

`events/{list,detail,form}.html`, `bids/{list,detail,form}.html`, standalone sub-module-level
`awards.html`, `analytics.html`. Colour-named badges ONLY (L33).

## Seeder `_seed_sourcing(tenant)` (per-block guard, reuses approved suppliers, skips when none)

One AWARDED event (criteria 40/35/25, three scored bids: won/lost/lost), one OPEN event
(submitted + draft bids), one CANCELLED event; AuditLog baselines; --flush deletes sourcing rows.

## LIVE_LINKS["6.5"]

Event Creation & Scheduling → procurement:event_list · Bid Submission Portal →
procurement:bid_list · Bid Evaluation Matrix → procurement:event_list?status=closed ·
Award Recommendation → procurement:award_board · Sourcing Analytics → procurement:sourcing_analytics

## Tests (wave)

test_sourcing_{models,forms,views,security}.py, every test named test_sourcing_*;
conftest fixtures appended (sourcing_event_open_a + criteria, sourcing_bid_submitted_a …).
