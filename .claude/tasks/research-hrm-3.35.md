# Research -- Module 3 (HRM) -- Sub-module 3.35 Travel Management (hrm)

## Scope grounding
- NavERP.md 3.35 bullets: Travel Request (domestic/international) | Booking Integration (flight/hotel/cab)
  | Travel Policy (class of travel, limits) | Travel Advance (cash advance) | Travel Settlement (post-travel
  reconciliation).
- 3.34 Expense Management (just built, apps/hrm/models.py) already provides: `ExpenseCategory` (per_claim_limit,
  monthly_limit, requires_receipt_above, gl_account_hint), `ExpenseClaim` (`ECL-`, 2-stage
  draft->submitted->manager_approved->approved->reimbursed machine, employee/title/purpose/period/currency,
  manager_approver+manager_approved_at, finance_approver+approved_at, rejection_reason, payment_method/reference,
  reimbursed_at), `ExpenseClaimLine` (category, expense_date, merchant, amount, receipt file, computed
  `policy_violation`/`violation_reason` never-stored properties). Mileage/per-diem and cash-advance were explicitly
  deferred from 3.34 to 3.35.
- Approval-workflow precedents in apps/hrm/views.py: the lean single-approver `_hr_request_*` helpers
  (`_hr_request_submit/_cancel/_approve/_reject/_edit/_delete`) shared by `AssetRequest`/`Suggestion`/similar
  3.26-3.27 request models -- status machine `draft -> pending -> approved/rejected/cancelled` (+ a fulfillment
  tail: `AssetRequest.approved -> fulfilled`, `Suggestion.approved -> implemented`), self-approval blocked via
  `_is_own_hr_request` (submitter `employee` FK must not equal reviewer), ownership-gated edit/delete/cancel via
  `_can_manage_own_child`/`_ss_scope`/`_ss_child_*`. This is lighter than ExpenseClaim's bespoke 2-stage
  manager->finance machine (`expenseclaim_manager_approve`/`expenseclaim_approve`/`expenseclaim_reject`/
  `expenseclaim_reimburse`).
- `hrm.JobGrade` (name, level_order, is_active) -- the grade catalog that travel-class/limit policies key off.
- `accounting.Currency` -- reused for all monetary FKs (estimated_cost, advance, booking cost).
- Upload pattern: `ExpenseClaimLine.receipt` FileField + `_validate_upload` (extension allowlist + size cap) is
  the precedent for any booking-document attachment (ticket/voucher/hotel confirmation).
- `crm.Expense` is sales-scoped, unrelated. `apps/hrm/` has no existing travel-related code (grep for
  `Travel`/`Trip` in models.py returned nothing) -- this is a clean 3.35 addition.

## Leaders surveyed (with source links)
1. **SAP Concur Travel** -- the incumbent enterprise T&E suite; policy-driven booking with color-coded
   in/out-of-policy indicators and rule-based approval routing.
   https://www.concur.com/products/concur-travel , https://www.concur.com/blog/article/how-concur-travel-works
2. **Navan (formerly TripActions)** -- modern all-in-one travel + expense platform; configurable policies by
   role/trip-type/cost-center, dynamic international caps, spend-threshold-based approval routing.
   https://navan.com/product/business-travel , https://navan.com/solutions/travel-managers
3. **TravelPerk** -- booking-first travel platform with an integrated "Perk" expense layer; in-policy filtering
   at search time, customizable spend-limit approvals, itinerary/trip notifications.
   https://www.travelperk.com/travel-solutions/expense-management/
4. **Zoho Expense (Trips)** -- expense-suite travel module; a Trip Request precedes booking, auto-creates a cash
   advance on approval, and the trip's actual expenses are reported/reconciled with excess-advance carry-forward.
   Per-diem rule templates by destination/duration/meals-provided.
   https://www.zoho.com/us/expense/expense-features/ , https://www.zoho.com/us/expense/per-diem/ ,
   https://www.zoho.com/de-de/expense/help/configuring-preferences/trips/
5. **Rydoo** -- expense-first platform with a strong automated per-diem engine (official country rates,
   partial-day rates for departure/arrival, deductions for provided meals) plus AI policy-violation flagging.
   https://www.rydoo.com/expense/per-diem-management/ , https://www.rydoo.com/solutions/travel-expense-software/
6. **Happay** -- India-market T&E suite; a single "book flights/hotels/trains/cabs/buses + advance request" flow,
   pre-disbursement approval gate on the advance, and a settlement dashboard showing amount-to-be-credited per trip.
   https://happay.com/travel-management-software/ , https://happay.com/blog/travel-request-approval-workflow/
7. **ITILITE** -- AI-booking-engine travel platform; policy defined by department/role/seniority, multi-tier
   sequential approval with separate paths for last-minute/high-cost/international trips, real-time in-booking
   compliance checks (spend, class, vendor).
   https://www.itilite.com/business-travel-management/ , https://www.itilite.com/blog/travel-and-expense-policy-compliance
8. **Egencia (Amex GBT)** -- enterprise TMC; in-policy-first search results with out-of-policy flagged for manager
   approval, plus duty-of-care traveler tracking/risk alerts (out of scope for this pass).
   https://www.amexglobalbusinesstravel.com/egencia/
9. **Emburse (Certify/Professional)** -- travel+expense suite; per-diem issued as cash advance or a reloadable
   card, pre-trip approval validated against budget/policy before booking.
   https://www.emburse.com/solutions/travel-management , https://www.emburse.com/solutions/travel-and-expense-management
10. **Keka HRMS -- Travel Desk / Expenses & Travel** -- an HRMS-embedded travel module (closest shape to NavERP):
    an employee's Advance Request captures mode of travel (air, with class), accommodation city, and dates; the
    Travel Desk (admin) confirms/declines the flight+hotel bookings against that request; the Advances tab tracks
    a linear pipeline -- Pending Approval -> Pending Payment -> Pending Receipt Submission -> Past/Settled Advances.
    https://help.keka.com/hc/en-us/articles/39946616084625-Overview-of-Expenses-Travel ,
    https://help.keka.com/hc/en-us/articles/39946778019217-Overview-of-Managing-Expense-and-Travel-Policies
- Also grounded against general corporate-travel-policy practice (class-of-travel-by-grade, per-night hotel caps
  varying by destination, advance-booking windows, travel-advance conditions) and travel-advance-reconciliation
  practice (net debit "recoverable from employee" vs net "payable to employee" outcomes) via Ramp/Engine/Lattice
  policy-template guidance and university/government travel-advance reconciliation procedures.
  https://ramp.com/blog/corporate-travel-policy , https://engine.com/business-travel-guide/travel-policy-template ,
  https://finance.cornell.edu/accounting/topics/traveladvances

## Feature catalog by NavERP.md bullet

### Travel Request -- Domestic/international travel
- **Trip request header (purpose, dates, origin/destination, trip type)** -- captures why/when/where before any
  booking happens. Seen in: Concur Travel, Navan, TravelPerk, Zoho Expense Trips, Happay, ITILITE, Keka.
  Priority: Must. Spine: new table `TravelRequest`, reuses `hrm.EmployeeProfile` (employee).
  Buildable now.
- **Domestic vs. international flag driving different rules** -- international trips get stricter/duty-heavier
  policy and approval paths. Seen in: Navan (dynamic international caps), ITILITE (separate international
  approval path), Concur. Priority: Must. Spine: `TravelRequest.trip_type` choice field, resolved against
  `TravelPolicy` scope. Buildable now.
- **Estimated cost / trip budget on the request** -- the number policy/advance/approval all key off. Seen in:
  Zoho Expense Trips (trip budget amount), Emburse (validate against budget before booking), ITILITE. Priority:
  Must. Spine: `TravelRequest.estimated_cost` + `currency` (reuse `accounting.Currency`). Buildable now.
- **Pre-trip / pre-booking approval (single or staged)** -- a trip must be authorized before booking/advance.
  Seen in: all 10. Priority: Must. Spine: `TravelRequest.status` machine + `approver`/`approved_at` (reuse the
  lean `_hr_request_*` single-approver pattern, not 3.34's 2-stage). Buildable now.
- **Self-approval block** -- a submitter cannot approve their own trip. Seen in: implied by every enterprise tool's
  role-separated approval routing (Concur, ITILITE routing rules); directly matches NavERP's own
  `_is_own_hr_request` precedent. Priority: Must. Spine: reuse `_is_own_hr_request` verbatim. Buildable now.
- **Multi-tier / spend-threshold / trip-type-specific approval routing** -- e.g. high-cost or international trips
  route to a different/second approver. Seen in: Navan, ITILITE, Egencia. Priority: Should (a stretch beyond the
  lean single-approver default -- flag as an easy future upgrade, do not build a routing engine this pass).
  Spine: none new required now (single `approver`); differentiator, defer the *routing logic* only.
  Buildable now for a manual re-assign, integration/later for automatic routing.
- **Trip completion / closure state** -- a trip needs a terminal state once travel is done and expenses are
  reconciled, separate from "approved". Seen in: Keka (Past Advances = closed), Zoho Expense Trips (trip closes
  once its expense report is filed), Happay (settlement dashboard closes the loop). Priority: Must. Spine:
  `TravelRequest.status` gains `completed` after `approved` (mirrors `AssetRequest.approved -> fulfilled` /
  `Suggestion.approved -> implemented`). Buildable now.
- **AI conversational booking assistant ("book me a flight to Paris Tuesday")** -- Concur Booking Agent, Egencia AI.
  Priority: Later (differentiator). Integration/later (LLM + live GDS).
- **Real-time itinerary notifications (delays, gate changes)** -- TravelPerk, Egencia. Priority: Later.
  Integration/later (live flight-status feed).

### Booking Integration -- Flight, hotel, cab booking
- **Record bookings against a trip (flight/hotel/cab/rail/other), one row per booking** -- Keka Travel Desk
  confirms flight+hotel bookings individually against one Advance Request; Happay books "flights, hotels, trains,
  cabs, buses" from one place. Priority: Must. Spine: new table `TravelBooking` (FK to `TravelRequest`).
  Buildable now (record-keeping only, not live search/purchase).
- **Vendor + confirmation/PNR reference number** -- every product's booking record includes the airline/hotel/cab
  vendor and a booking reference. Priority: Must. Spine: `TravelBooking.vendor` + `.reference`. Buildable now.
- **Travel class per booking (economy/premium/business/first)** -- the field policy compliance is checked
  against. Seen in: Concur (class in the fare table), Keka (class of travel dropdown), ITILITE (class checked
  real-time). Priority: Must. Spine: `TravelBooking.travel_class` (choices shared with `TravelPolicy`).
  Buildable now.
- **Depart/return (or check-in/check-out) dates + cost per booking** -- lets a trip have several bookings summing
  to the actual travel spend. Priority: Must. Spine: `TravelBooking.depart_date/return_date/cost/currency`.
  Buildable now.
- **In-policy / out-of-policy flag on the booking (color-coded)** -- Concur's caution icon, Navan's "clearly
  marked" out-of-policy options, ITILITE's real-time compliance check on class/vendor/spend. Priority: Should.
  Spine: computed property on `TravelBooking` comparing `travel_class` (and cost) against the resolved
  `TravelPolicy` -- never stored, mirrors `ExpenseClaimLine.policy_violation`. Buildable now.
- **Attach the ticket/voucher/confirmation document** -- mirrors the 3.34 receipt pattern. Priority: Should.
  Spine: `TravelBooking.document` FileField + `_validate_upload`. Buildable now.
- **Live GDS/API flight & hotel search, price comparison, negotiated-fare display, direct purchase** -- Concur,
  Navan, TravelPerk, Egencia's core booking engines. Priority: Must-have-eventually but explicitly OUT of this
  pass per the module's own framing. Integration/later (external GDS/OTA APIs).
- **Self-booking tool (employee books directly in-app against policy guardrails)** -- Happay, ITILITE, TravelPerk.
  Priority: Later. Integration/later (depends on live booking APIs above).
- **Group/multi-traveler bookings, visa/passport management, travel insurance** -- Egencia, Navan enterprise
  tiers. Priority: Later (differentiator). Integration/later.

### Travel Policy -- Class of travel, limits
- **Policy scoped by employee grade/band** -- "class-of-travel by grade" is the single most common policy
  template element (Ramp/Engine/Lattice templates; Navan "policies based on role"; ITILITE "policies by
  department, role, seniority"). Priority: Must. Spine: `TravelPolicy.job_grade` FK to `hrm.JobGrade`
  (null = applies to all grades). Buildable now.
- **Allowed travel class (economy/premium/business/first) by policy** -- Concur's rule engine, template guidance
  ("business class permitted for international flights >= 6-8 hrs"), Keka's class dropdown. Priority: Must.
  Spine: `TravelPolicy.travel_class` choice field. Buildable now.
- **Domestic vs. international scope on the policy** -- most templates and Navan/ITILITE split rules by trip
  type (and international is where dynamic/higher caps apply). Priority: Must. Spine: `TravelPolicy.trip_type`
  choice (`domestic`/`international`/`both`). Buildable now.
- **Daily allowance / per-diem cap** -- Rydoo's automated official per-diem rates, Zoho Expense per-diem rule
  templates, general policy-template "daily allowances for meals and incidentals". Priority: Must (stored cap;
  NOT an auto-calc engine this pass). Spine: `TravelPolicy.daily_allowance_limit`. Buildable now (a static
  number the settlement/booking check against); the full per-diem *generation* engine (destination-aware,
  partial-day, meals-provided deductions) is deferred.
- **Hotel spend cap per night, varying by destination** -- explicit in policy-template guidance ("$200/night...
  doesn't work in NYC or SF"). Priority: Should. Spine: `TravelPolicy.hotel_limit_per_night` (destination-type
  variance deferred -- one cap per policy row, create multiple policy rows per destination tier if needed).
  Buildable now.
- **Advance-booking window requirement (e.g. book >=14 days ahead)** -- Engine/Ramp templates, ITILITE
  ("last-minute trips have their own approval path"). Priority: Later (differentiator). Integration/later
  (needs a booking-date-vs-departure-date rule check the domain doesn't require day-one).
- **Advance percentage cap (max % of estimated cost advanceable)** -- implied by every advance-approval flow
  needing a ceiling; explicit in policy-template "conditions under which advances will be granted." Priority:
  Must. Spine: `TravelPolicy.advance_percent_limit`. Buildable now.
- **Dynamic/context-aware policy thresholds by real-time market pricing** -- Navan's differentiator. Priority:
  Later. Integration/later (real-time fare data).
- **Preferred-vendor lists, negotiated-rate display** -- Concur, Navan, TravelPerk. Priority: Later. Integration/
  later (vendor-rate feeds).

### Travel Advance -- Cash advance for travel
- **Request an advance amount tied to the trip (often auto-suggested from estimated cost)** -- Zoho Expense
  Trips ("create an advance for the trip's budget amount... when it is approved"), Keka (Advance Request IS the
  travel request), Happay ("raising VISA and advance requests from the same tool"). Priority: Must. Spine:
  `TravelRequest.advance_requested` (no separate advance model -- folded into the request, per the deferred-item
  framing that mileage/cash-advance land in 3.35 as part of the trip). Buildable now.
- **Approval gate before disbursement** -- Happay explicit ("approval system before advance money is credited"),
  Keka's Pending Approval stage. Priority: Must. Spine: the SAME `TravelRequest.approve` action also sets
  `advance_approved` (capped by `TravelPolicy.advance_percent_limit x estimated_cost`) -- no second approval
  stage. Buildable now.
- **Disbursement/payment tracking (pending payment -> paid)** -- Keka's explicit "Pending Payments" stage before
  "Pending Receipt Submission". Priority: Must. Spine: `TravelRequest.advance_paid_at` timestamp (record-keeping
  only, mirrors `ExpenseClaim.reimbursed_at` -- no GL/payroll posting this pass). Buildable now.
- **Excess-advance carry-forward to a future trip** -- Zoho Expense Trips differentiator ("choose to carry
  forward the excess amount... created as a new advance"). Priority: Later (differentiator -- valuable but not
  needed for a first settlement pass; net_recoverable can simply be tracked as an amount owed rather than
  auto-rolled into a new advance). Integration/later.
- **Advance issued as a reloadable card vs. cash** -- Emburse differentiator. Priority: Later. Integration/later
  (payment-instrument integration).
- **Multiple advances per trip (e.g. topped-up mid-trip)** -- implied by Keka's ongoing Advances tab per
  employee. Priority: Later (one advance per `TravelRequest` is sufficient for this pass; a true multi-advance
  ledger is a future extension). Deferred.

### Travel Settlement -- Expense settlement post-travel
- **Actual expenses reconciled against the advance after the trip** -- universal: Concur (advance applied to
  expense report, "credit to Travel Advance account, debits against expenses"), Zoho Expense Trips (trip's
  expense report reconciled against its advance), Happay ("settlement dashboard shows amount to be credited"),
  Keka (Past/Settled Advances). Priority: Must. Spine: **reuse `hrm.ExpenseClaim`** as the actual-expense
  container (see Recommended build scope below) rather than a parallel expense-capture model.
- **Net payable (to employee) vs. net recoverable (from employee)** -- explicit two-outcome pattern in
  university/government travel-advance procedures ("debit to Travel Advance Return account" when recoverable vs.
  "reimbursement of the excess" when payable) and mirrored by every commercial tool's settlement dashboard.
  Priority: Must. Spine: a computed property comparing the linked `ExpenseClaim.total_amount` to
  `TravelRequest.advance_approved` -- never stored (mirrors `ExpenseClaimLine.policy_violation`'s
  computed-not-stored convention). Buildable now.
- **Receipts attached to each actual-expense line** -- universal (Concur, Rydoo, Happay's smart audit, Zoho).
  Priority: Must. Spine: already exists on `ExpenseClaimLine.receipt` -- reuse, do not rebuild. Buildable now.
- **Per-category policy-limit checks on settlement lines** -- Rydoo (AI-driven out-of-policy detection), Happay
  Smart Audit (auto-flag inflated/false/duplicate claims), Concur. Priority: Must. Spine: already exists as
  `ExpenseClaimLine.policy_violation` against `ExpenseCategory` -- reuse. Buildable now.
- **Settlement-stage approval (finance sign-off before payout)** -- Concur, Happay, ITILITE all route settlement
  through a finance/audit step. Priority: Must. Spine: already exists as `ExpenseClaim`'s
  `manager_approved -> approved -> reimbursed` stages -- reuse verbatim by routing the trip's settlement through
  the existing `ExpenseClaim` workflow instead of inventing a parallel one. Buildable now.
- **A trip-level settlement summary view (advance vs. actual vs. net, one screen)** -- Happay's settlement
  dashboard, Keka's Advances tab summary. Priority: Should. Spine: a `TravelRequest` detail-page section built
  from `advance_approved` + the linked `ExpenseClaim.total_amount` + the computed net property -- no new table.
  Buildable now.
- **Automatic per-diem line generation from trip duration x daily rate** -- Rydoo/Zoho differentiator (auto-
  generate per-diem expense lines from destination + duration + meals-provided rules). Priority: Later. This
  pass only stores the daily cap on `TravelPolicy`; auto-generating per-diem `ExpenseClaimLine` rows from it is
  deferred.
- **Mileage-based reimbursement (rate x distance) as an expense category** -- deferred from 3.34, and still
  deferred here: recommend it land as a plain `ExpenseCategory` row ("Mileage") on the settlement `ExpenseClaim`
  rather than a bespoke distance-calculation model. Priority: Later.
- **GL posting / payroll-integrated payout of the net settlement amount and the advance disbursement** -- Zoho
  Expense ("syncs settlements with payroll and ERP software"), Concur's Travel Advance GL accounts. Priority:
  Later -- explicitly out of scope this pass (record-keeping only, matching the 3.34 precedent of no GL posting;
  `advance_paid_at` and `settlement_claim.reimbursed_at` remain plain timestamps until Module 2 Accounting or
  3.30 payroll integration picks this up). Integration/later.

## Recommended 3.35 build scope (3 new models + reuse 3.34/3.2/accounting)

**Settlement approach -- RECOMMENDED: reuse 3.34's `ExpenseClaim`, do not build a parallel settlement/expense
model.** Rationale: `ExpenseClaim` + `ExpenseClaimLine` already provide exactly what "post-travel settlement"
needs -- a header with a 2-stage manager->finance approval machine, categorized lines with amount/merchant/
receipt, and a computed (never-stale) `policy_violation` check against `ExpenseCategory` limits. Zoho Expense's
own Trips feature validates this shape in the market: a trip's post-travel reconciliation IS an expense report
against the same expense-report engine the product already has, not a separate settlement construct. Building a
second parallel expense-capture-and-approval model for 3.35 would duplicate `ExpenseCategory`/receipt-upload/
approval-machine logic for zero product benefit and violate the "reuse the spine" principle at the app-internal
level. Instead: `TravelRequest` gets a nullable `settlement_claim` FK to `hrm.ExpenseClaim`; a "Generate
Settlement" action (available once the request is `approved`, gated like the other fulfillment tails) creates an
`ExpenseClaim` pre-filled from the trip (employee, title=f"Travel settlement - {destination}", purpose=trip
purpose, period_start/end=trip dates, currency=trip currency) and links it back. The settlement then flows
through 3.34's existing submit/manager_approve/approve/reimburse actions unchanged. Net payable/recoverable is a
**computed property** on `TravelRequest` (`settlement_claim.total_amount - (advance_approved or 0)`), never
stored -- positive = recoverable from employee, negative = payable to employee -- exactly mirroring
`ExpenseClaimLine.policy_violation`'s compute-don't-store convention.

**Approval-workflow design -- RECOMMENDED: the lean single-approver `_hr_request_*` pattern (like
`AssetRequest`/`Suggestion`), NOT a bespoke 2-stage machine like `ExpenseClaim`.** Rationale: `TravelRequest` is
an *authorization to travel and to receive an advance*, not itself a payment claim -- it is analogous in shape to
`AssetRequest` (ask -> single admin decision -> a fulfillment tail), not to `ExpenseClaim` (a claim needing
sequential manager-then-finance sign-off on money already spent). Using `_hr_request_submit/_cancel/_approve/
_reject` verbatim means zero new workflow plumbing; the advance-approval decision (setting `advance_approved`,
capped by the resolved `TravelPolicy.advance_percent_limit`) piggybacks on the SAME `approve` action rather than
a second stage. The real finance-grade rigor (multi-level sign-off, receipts, policy checks) already lives
downstream in the reused `ExpenseClaim` settlement -- so the trip-authorization step staying lean does not weaken
overall control. Status machine: `draft -> pending -> approved/rejected/cancelled`, then `approved -> completed`
(closes the loop once travel is done and a settlement is generated) -- mirrors `AssetRequest.approved ->
fulfilled` / `Suggestion.approved -> implemented`.

1. **`TravelPolicy`** [config master, no number prefix -- small per-tenant catalog like `ExpenseCategory`]
   - `name` (CharField), `job_grade` (FK `hrm.JobGrade`, null=True blank=True -- null = all grades)
   - `trip_type` (choices: `domestic`/`international`/`both`)
   - `travel_class` (choices: `economy`/`premium_economy`/`business`/`first`)
   - `daily_allowance_limit` (Decimal, null/blank) -- per-diem cap
   - `hotel_limit_per_night` (Decimal, null/blank)
   - `advance_percent_limit` (Decimal, null/blank -- e.g. 80.00 = max 80% of estimated cost advanceable)
   - `is_active` (Boolean, default True)
   - Justified by: Travel Policy bullet + Rydoo/Concur/ITILITE/Navan grade-and-class-scoped policy features +
     template guidance on class-by-grade, per-diem, hotel caps, advance conditions.
   - Reuses: `hrm.JobGrade`.

2. **`TravelRequest`** [`TRV-`, `TenantNumbered`, the trip authorization + advance header]
   - `employee` (FK `hrm.EmployeeProfile`)
   - `trip_type` (choices `domestic`/`international`)
   - `origin` (CharField), `destination` (CharField), `purpose` (TextField)
   - `start_date` / `end_date` (DateField)
   - `policy` (FK `hrm.TravelPolicy`, null/blank -- resolved by grade+trip_type at creation, admin-overridable)
   - `estimated_cost` (Decimal), `currency` (FK `accounting.Currency`)
   - `status` (choices: `draft`/`pending`/`approved`/`rejected`/`cancelled`/`completed`;
     `OPEN_STATUSES = ("draft", "pending")`)
   - `approver` (FK user, null/blank), `approved_at` (DateTime, null/blank), `decision_note` (TextField, blank)
     -- matches `AssetRequest`/`Suggestion` field names exactly so `_hr_request_*` helpers apply verbatim
   - `advance_requested` (Decimal, null/blank -- employee's ask)
   - `advance_approved` (Decimal, null/blank -- set at approval, capped by policy `advance_percent_limit`)
   - `advance_paid_at` (DateTime, null/blank -- disbursement recorded, no GL posting)
   - `settlement_claim` (FK `hrm.ExpenseClaim`, null/blank, `on_delete=SET_NULL`, related_name
     `travel_settlements` -- generated by a "Generate Settlement" action once `approved`)
   - `settled_at` (DateTime, null/blank -- stamped once `settlement_claim` reaches `reimbursed`)
   - Computed properties: `net_settlement` (from `settlement_claim.total_amount - (advance_approved or 0)`,
     `None` if no settlement yet), `is_international` (shortcut on `trip_type`).
   - Justified by: Travel Request bullet (domestic/international, purpose, dates, pre-trip approval -- Concur/
     Navan/TravelPerk/Zoho/ITILITE/Keka) + Travel Advance bullet (advance_requested/approved/paid_at -- Zoho
     Expense Trips auto-advance-on-approval, Happay approval-gated disbursement, Keka's Pending
     Approval->Payment pipeline) + Travel Settlement bullet (settlement_claim link + net_settlement -- universal
     advance-vs-actual reconciliation pattern).
   - Reuses: `hrm.EmployeeProfile`, `hrm.TravelPolicy`, `accounting.Currency`, `hrm.ExpenseClaim` (settlement),
     the `_hr_request_*` view helpers, `_is_own_hr_request` self-approval guard.

3. **`TravelBooking`** [child rows under a `TravelRequest`, no number prefix -- like `ExpenseClaimLine`]
   - `request` (FK `hrm.TravelRequest`, related_name `bookings`)
   - `booking_type` (choices: `flight`/`hotel`/`cab`/`rail`/`other`)
   - `vendor` (CharField)
   - `reference` (CharField -- PNR/confirmation number)
   - `depart_date` (DateField, null/blank), `return_date` (DateField, null/blank -- checkout/drop-off)
   - `travel_class` (choices shared with `TravelPolicy.travel_class` -- economy/premium_economy/business/first;
     blank for hotel/cab rows)
   - `cost` (Decimal), `currency` (FK `accounting.Currency`, null/blank -- defaults to request currency)
   - `notes` (TextField, blank)
   - `document` (FileField, null/blank, `upload_to="hrm/travel_bookings/%Y/%m/"`, validated by
     `_validate_upload` -- ticket/voucher/confirmation attachment, mirrors `ExpenseClaimLine.receipt`)
   - Computed property: `out_of_policy` (bool, never stored -- compares `travel_class` against
     `request.policy.travel_class` and `cost` against `request.policy.hotel_limit_per_night` for hotel rows;
     mirrors `ExpenseClaimLine.policy_violation`'s pattern exactly)
   - Justified by: Booking Integration bullet (flight/hotel/cab recording with vendor/PNR/dates/class/cost --
     Keka Travel Desk, Happay's single booking-recording flow, Concur/Navan/ITILITE's class-and-vendor policy
     checks at booking time).
   - Reuses: `accounting.Currency`, `_validate_upload`.

## Deferred (later passes / integrations)
- **Live GDS/OTA booking APIs, real-time flight/hotel search & price comparison, direct purchase/self-booking
  tool** -- this pass is record-keeping only (bookings are entered after the fact); every leader's core booking
  engine depends on live supplier connections out of scope for a single Django pass.
- **Automatic per-diem expense-line generation** (destination-aware daily rate x trip duration, partial-day
  departure/arrival rates, meals-provided deductions) -- `TravelPolicy.daily_allowance_limit` is stored as a
  static cap this pass; Rydoo/Zoho's full per-diem calculation engine is deferred.
- **Mileage reimbursement (rate x distance)** -- still deferred from 3.34; recommend a plain "Mileage"
  `ExpenseCategory` row on the settlement `ExpenseClaim` when it's eventually built, not a bespoke model.
- **Multi-tier / automatic approval routing** (spend-threshold, international, last-minute paths; Navan/ITILITE/
  Egencia) -- this pass keeps a single `approver`; routing logic is a future upgrade to the same field.
- **Excess-advance carry-forward to a future trip's advance** (Zoho Expense Trips differentiator) -- this pass
  tracks `net_settlement` as an amount owed/payable only; auto-rolling it into a new advance is deferred.
- **Multiple/topped-up advances per trip** -- one advance per `TravelRequest` this pass; a true advance ledger
  (Keka's per-employee Advances tab across trips) is a future extension.
- **Duty-of-care / traveler safety tracking, risk alerts, real-time location** -- Egencia's differentiator, not
  an ERP data-model concern this pass.
- **Carbon/sustainability tracking, travel insurance, visa/passport management, group/multi-traveler bookings** --
  differentiator features seen in enterprise tiers (Navan, Egencia); no immediate NavERP data-model need.
  Group/multi-traveler bookings are what a family of `TravelRequest` rows under one shared reference would
  eventually cover -- design not requested this pass.
- **Multi-currency FX conversion** across request/booking/settlement currencies -- amounts are recorded in their
  stated currency without conversion this pass (same limitation `ExpenseClaim.currency` already carries).
- **Dynamic/context-aware policy thresholds from real-time market pricing** (Navan) -- `TravelPolicy` limits are
  static per-tenant config this pass.
- **AI conversational booking assistants** (Concur Booking Agent, Egencia AI) -- LLM+GDS integration, out of
  scope.
- **Advance-booking-window enforcement** (e.g. must book >=14 days ahead) -- a rule-engine feature not needed for
  the first pass; `TravelBooking.depart_date` vs. `TravelRequest.created_at` is available data for a future check.
