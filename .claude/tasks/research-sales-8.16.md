# Research — Sub-module 8.16: Mobile Sales (Module 8 — Sales Management System, sales)

**Sub-module:** `8.16 Mobile Sales` (NavERP.md, Module 8 — Sales Management System)  
**App:** `apps/sales` (existing app — this run EXTENDS it; no scaffold, no `config/` wire-up)  
**Run date:** 2026-10-22  
**Target sub-module:** `8.16`  

---

## 1. Repo state checked first

### 1.1 LIVE_LINKS built so far in Module 8
From `apps/core/navigation.py`:
- Built and active:
  - `8.1` Lead Management (`crm:formsubmission_list`, `sales:lead_score_event_list`, `sales:lead_qualification_list`, etc.)
  - `8.2` Opportunity & Pipeline Management (`sales:opportunity_pipeline_list`, `sales:opportunity_pipeline_visibility`, etc.)
  - `8.3` Contact & Account Management (`sales:account_hierarchy`, `sales:account_classification_list`, `sales:account_plan_list`, etc.)
  - `8.4` Sales Forecasting (`sales:forecast_submission_list`, `sales:forecast_board`, `sales:forecast_attainment`, etc.)
  - `8.5` Quote & Proposal Management / CPQ (`sales:cpq_quote_list`, `sales:quote_approval_queue`, `sales:product_bundle_list`, etc.)
  - `8.6` Order Management (`sales:order_capture_board`, `sales:order_amendment_list`, `sales:revenue_schedule_list`, etc.)
  - `8.7` Territory & Quota Management (`sales:territory_rule_list`, `sales:account_territory_assignment_list`, `sales:quota_plan_list`, etc.)
  - `8.8` Sales Activity & Task Management (`sales:activity_log_list`, `sales:task_template_list`, `sales:sales_plan_cycle_list`, etc.)
  - `8.9` Sales Enablement (`sales:enablement_content_hub`, `sales:sales_playbook_board`, `sales:sales_certification_list`, etc.)
  - `8.10` Incentive Compensation Management (`sales:sales_commission_plan_hub`, `sales:commission_earning_list`, `sales:commission_statement_list`, etc.)
  - `8.11` Customer Success & Account Management (`sales:customer_health_console`, `sales:customer_renewal_pipeline`, `sales:customer_onboarding_hub`, etc.)
  - `8.12` Sales Analytics & Intelligence (`sales:win_loss_console`, `sales:velocity_console`, `sales:funnel_console`, `sales:rep_scorecard_console`, etc.)
  - `8.13` Marketing Alignment & Attribution (`sales:attribution_touchpoint_list`, `sales:mql_handoff_list`, `sales:marketing_attribution_console`, etc.)
  - `8.14` Partner & Channel Management (`sales:partner_profile_list`, `sales:deal_registration_list`, `sales:joint_account_plan_list`, `sales:channel_conflict_list`, `sales:partner_performance_console`).
  - `8.15` Contract & Subscription Management (`sales:customer_contract_list`, `sales:customer_subscription_list`, `sales:renewal_automation_dashboard`, `sales:usage_meter_record_list`, `sales:contract_obligation_list`).
- **Target Sub-module 8.16 is the next unbuilt sub-module** in Module 8 (`LIVE_LINKS["8.16"]` is currently absent).

### 1.2 Spine entities verified to exist / NOT exist (grep evidence)
Verified via class grep across `apps/core/models/`, `apps/crm/models/`, `apps/accounting/models/`, `apps/scm/models/`, `apps/accounts/`, and `apps/sales/models/`:
- `core.Party` (`apps/core/models/Party.py:5`) — **Verified exists.** Master account, client firm, retail store, or contact person visited in the field.
- `core.Address` (`apps/core/models/Address.py:5`) — **Verified exists.** Stores street address, city, country; provides base location for customer destination routing.
- `core.Document` (`apps/core/models/Document.py:5`) — **Verified exists.** Used for attaching proof-of-visit photos, retail shelf audits, store condition images, and on-site signed documents.
- `accounting.Currency` (`apps/accounting/models/GeneralLedger/Currencies.py:6`) — **Verified exists.** Master currency for on-the-spot mobile quotes and orders.
- `accounts.User` (`apps/accounts/models.py:52`) — **Verified exists.** Outside sales reps, field account executives, and sales managers.
- `crm.Opportunity` (`apps/crm/models/SalesForceAutomation/Opportunities.py:5`) — **Verified exists.** Deal pipeline records advanced during field visits or triggering mobile deal alerts.
- `crm.Lead` (`apps/crm/models/CoreData/Leads.py:5`) — **Verified exists.** Inbound prospects contacted or visited in the field.
- `crm.CommunicationLog` (`apps/crm/models/ActivityManagement/CommunicationLogs.py:5`) — **Verified exists.** Unified interaction log (`COM-`) with `channel="call"`, `duration_seconds`, `outcome`, `logged_via`.
- `sales.CPQQuote` (`CPQ-`, `apps/sales/models/QuoteProposalCPQ/CPQQuotes.py:11`) — **Verified exists.** Originating quote header supporting mobile on-the-spot quoting, line items, discount approval statuses, and e-signature tokens.
- `sales.QuoteApprovalRule` (`QAR-`, `apps/sales/models/QuoteProposalCPQ/QuoteApprovalRules.py:8`) — **Verified exists.** Discount threshold rules evaluated when mobile quotes require manager sign-off.
- `sales.CustomerContract` (`CCT-`, `apps/sales/models/ContractSubscriptionManagement/CustomerContracts.py:32`) — **Verified exists.** Executed agreements signed in the field.
- `sales.ActivityLog` (`SAL-`, `apps/sales/models/SalesActivityTaskManagement/ActivityLogs.py:73`) — **Verified exists.** Sales activity rollups and rep plan attributions.
- `scm.SalesOrder` (`SO-`, `apps/scm/models/OrderManagement/SalesOrders.py:20`) — **Verified exists.** Customer sales orders submitted from the road.
- `hrm.GeoFence` (`apps/hrm/models/AttendanceManagement/Geofence.py:8`) — **Verified exists.** Demonstrates production Haversine formula calculation (`distance_to`) for GPS coordinate proximity.

### 1.3 Ownership rulings & boundaries (L29 / L36 / L37) — what 8.16 must NOT declare
1. **Never declare a duplicate Customer or Contact master:** Customer accounts and visited retail locations are `core.Party` instances. 8.16 FKs `core.Party` directly.
2. **Never declare a duplicate User or Sales Rep master:** Field reps, dispatchers, and managers are `settings.AUTH_USER_MODEL` (`accounts.User`).
3. **Never declare a duplicate Quote, Order, or Contract master:** On-the-spot quoting updates or references `sales.CPQQuote` (`CPQ-`); field order entry targets `scm.SalesOrder` (`SO-`); customer contracts reference `sales.CustomerContract` (`CCT-`).
4. **Never declare duplicate Activity or Communication log tables:** General phone/email interactions belong to `crm.CommunicationLog` (`COM-`); sales attribution belongs to `sales.ActivityLog` (`SAL-`). 8.16 creates specialized **`FieldCheckIn` (`CHK-`)** records capturing physical GPS check-ins, arrival/departure timestamps, Haversine geofence verification, and proof-of-visit attachments, optionally linking to `crm.CommunicationLog`.
5. **Never declare duplicate Geofence catalogs from other modules:** While `hrm.GeoFence` serves employee attendance clock-in, 8.16 stores visit GPS check-in coordinates directly alongside destination coordinates and calculates geofence containment via the Haversine distance formula dynamically.

---

## 2. NavERP.md scope (authoritative)

```markdown
### 8.16 Mobile Sales
- **Mobile CRM Access** — Full-featured mobile app for iOS/Android with offline capability.
- **Field Sales Tools** — Route optimization, check-in/check-out, and geo-fenced activity logging.
- **Mobile Quoting & Approvals** — On-the-spot quote generation, discount approvals, and digital signatures.
- **Voice & Call Integration** — Click-to-dial, call logging, and voicemail drop from mobile.
- **Mobile Dashboards & Alerts** — Push notifications, deal alerts, and compact performance views.
```

Five authoritative feature bullets. All five must be addressed in the architectural design and feature catalog.

---

## 3. Commercial leaders surveyed

Survey of 9 market-leading field sales, route planning, and mobile CRM platforms:

| # | Product | Positioning | Official Source / Reference | Key Contributions to Catalog |
|---|---|---|---|---|
| 1 | **Badger Maps** | Premier route planning and territory optimization software for outside sales teams | [badgermapping.com](https://www.badgermapping.com/) | Multi-stop daily route planning (up to 120 stops); lasso customer clustering; one-tap check-in with GPS timestamping; customizable visit forms; photo attachments; turn-by-turn navigation deep links (Google Maps, Apple Maps, Waze); quick stops / schedule gap filling. |
| 2 | **SPOTIO** | Mobile-first field sales engagement, territory management, and outside sales tracking | [spotio.com](https://spotio.com/) | "Download My Day" offline caching; single-tap GPS check-in/out verification; automated visit duration tracking; on-site e-contract signing; field activity leaderboards; rep travel path tracking. |
| 3 | **Zoho CRM Mobile & RouteIQ** | Native mobile CRM and location intelligence extension for outside sales and field reps | [zoho.com/routeiq](https://www.zoho.com/routeiq/) | Multi-stop route optimization; restricted check-in/check-out (enforcing physical geofence radius around customer location); automated check-in notifications; mandatory visit outcome forms before check-out; proof-of-delivery / visit photo upload; administrative force check-out override. |
| 4 | **Salesforce Mobile App & Salesforce Maps / Field Service** | Enterprise mobile CRM, location intelligence, and offline field sales execution | [salesforce.com/products/mobile](https://www.salesforce.com/products/mobile/) | Mobile Offline Priming (LWC offline caching SQLite profile); full offline record drafting with background delta sync; geolocation stamp check-in; dynamic visit surveys; on-the-spot CPQ quote creation; mobile discount approval queues; in-person mobile touch e-signatures. |
| 5 | **Repsly** | Field sales, merchandising, and retail execution platform for mobile teams | [repsly.com](https://www.repsly.com/) | Geofenced store visits; travel mileage & time recording; mobile digital product catalog & order/quote placement; retail shelf photo auditing; offline mobile work with automated background synchronization. |
| 6 | **Skynamo** | B2B field sales and mobile order taking app for distributors and manufacturers | [skynamo.com](https://www.skynamo.com/) | "Offline-first" mobile architecture; GPS location-aware customer visit logging; live ERP stock and customer pricing lookup; on-site quote and order capture; customer interaction history review prior to meetings. |
| 7 | **HubSpot Mobile App** | Mobile Smart CRM for deal management, remote calling, and sales activity | [hubspot.com/products/crm/mobile](https://www.hubspot.com/products/crm/mobile/) | Click-to-dial using native phone dialer or VoIP; automatic post-call timeline logging with duration and outcome dispositions; pre-recorded voicemail drop; mobile deal board with quick stage progression; push notifications for deal milestones. |
| 8 | **Close Mobile CRM** | High-velocity sales communication and mobile CRM platform | [close.com](https://www.close.com/) | In-app click-to-dial; incoming/outgoing call logging; SMS messaging; instant push notifications for deal updates and inbound lead interactions; unified mobile sales inbox. |
| 9 | **DealHub Mobile** | Mobile CPQ, DealRoom negotiation, and quote approval management | [dealhub.io](https://dealhub.io/) | Responsive mobile quote viewer; one-tap manager discount approval workflow; real-time mobile deal alerts; in-person digital signature capture. |

### Cross-Product Consensus (Industry Standard Best Practices)
1. **Planned Route vs. Actual Execution (The Daily Itinerary):** Outside sales reps plan their day as an ordered sequence of customer stops (`FieldSalesRoute`). Systems track planned travel distance, estimated arrival times, and calculate completion rates as stops are visited.
2. **Location-Verified Check-In & Geo-Fencing:** To ensure auditability and eliminate "fake" check-ins, modern field tools capture the device's real-time GPS coordinates upon check-in, compare them to the customer party's geocoded address using the Haversine formula, and verify whether the rep is within the authorized geofence radius (e.g. 150m). Check-ins outside the radius are flagged as `out_of_range`.
3. **Structured Check-Out & Mandatory Visit Outcomes:** Check-out records departure time and total on-site duration. Best-in-class platforms mandate that reps complete a visit outcome summary (purpose, discussion notes, next steps, photo evidence) before the check-out is finalized. Administrators are provided a "Force Check-Out" capability if a rep leaves a site without checking out.
4. **Offline Priming & Delta Sync Manifests:** Because outside reps frequently visit basements, rural sites, or industrial parks with zero cell reception, mobile apps use an offline manifest (`MobileDeviceSession`). Reps download their daily itinerary, customer records, and product price books before leaving ("Download My Day"), work offline, and queue changes locally for background delta synchronization when reconnected.
5. **On-the-Spot Quoting & In-Person Digital Signatures:** Closing in the field requires presenting proposals immediately without returning to an office. Reps draft quotes (`CPQQuote`), apply negotiated line discounts, submit for manager discount approval directly from the phone, and capture the client's signature on the touch screen.
6. **Mobile Telephony & Rapid Call Dispositions:** Click-to-dial leverages native `tel:` links to launch calls immediately. Upon completion, the rep is prompted with a quick disposition modal to select the call outcome (`connected`, `voicemail`, `busy`, `no_answer`), log duration, or execute a pre-recorded voicemail drop.
7. **Mobile Push Alerts & Urgent Notifications:** Away from their computers, reps rely on mobile push notifications (`MobileDealAlert`) for high-urgency events: discount approval requests, deal stage changes, route dispatch notices, and customer check-in reminders.

---

## 4. Deduplicated, prioritised feature catalog

### 4.1 Mobile CRM Access & Offline Capability
- **Offline Data Priming & Cache Manifest** — Local storage manifest allowing reps to download daily routes, assigned accounts, and open opportunities for offline viewing and editing · seen in: *Salesforce Mobile, SPOTIO, Skynamo* · priority: `table-stakes` · spine: new table `MobileDeviceSession` (`MDS-`) · buildable now (manifest API + local storage sync).
- **Delta Synchronization & Conflict Resolution** — Queuing offline modifications (check-ins, notes, quote drafts) and synchronizing with server timestamps upon network reconnection · seen in: *Salesforce Mobile, Repsly, Skynamo* · priority: `common` · spine: tracked via `MobileDeviceSession` sync timestamps · buildable now.
- **Mobile Device Registration & Session Trust** — Registering rep mobile devices (iOS, Android, PWA), tracking device UUID, app version, and push notification tokens · seen in: *Salesforce Mobile, HubSpot Mobile* · priority: `table-stakes` · spine: new table `MobileDeviceSession` · buildable now.
- **Responsive Mobile Workspace / PWA Shell** — Touch-first, high-contrast Tailwind UI designed specifically for smartphone viewports with bottom navigation bars and quick-action cards · seen in: *All leaders* · priority: `table-stakes` · spine: view templates + mobile layout · buildable now.
- **Selective Offline Media Cache** — Limiting photo and document downloads on mobile data to optimize storage and bandwidth · seen in: *Repsly, Skynamo* · priority: `differentiator` · spine: `core.Document` flag · integration/later.

### 4.2 Field Sales Tools & Geo-Fenced Activity Logging
- **Multi-Stop Route Planning & Itinerary Builder** — Scheduling daily customer visit sequences, tracking stop numbers, and calculating estimated travel minutes and total distance · seen in: *Badger Maps, Zoho RouteIQ, SPOTIO* · priority: `table-stakes` · spine: new table `FieldSalesRoute` (`FSR-`) · buildable now.
- **Turn-by-Turn Navigation Deep Links** — Single-tap action launching native navigation apps (Google Maps, Apple Maps, Waze) pre-populated with customer coordinates · seen in: *Badger Maps, Zoho RouteIQ* · priority: `table-stakes` · spine: template URL generator · buildable now.
- **GPS-Stamped One-Tap Check-In** — Capturing device latitude, longitude, and timestamp upon arrival at a client site · seen in: *Badger Maps, SPOTIO, Repsly, Zoho RouteIQ* · priority: `table-stakes` · spine: new table `FieldCheckIn` (`CHK-`) · buildable now.
- **Haversine Geofence Verification & Distance Auditing** — Calculating exact mathematical distance between check-in coordinates and customer party location; verifying compliance within radius (default 150m) and flagging out-of-range check-ins · seen in: *Zoho RouteIQ, Repsly, SPOTIO* · priority: `table-stakes` · spine: Haversine distance method on `FieldCheckIn` (mirrors `hrm.GeoFence.distance_to`) · buildable now.
- **Check-Out & Visit Duration Logging** — Recording departure timestamp, calculating total on-site meeting duration in minutes · seen in: *Zoho RouteIQ, SPOTIO, Skynamo* · priority: `table-stakes` · spine: `FieldCheckIn` fields · buildable now.
- **Mandatory Visit Outcome & Next Best Action** — Structured form capturing visit purpose (`prospecting`, `presentation`, `negotiation`, `order_collection`), meeting outcome (`successful`, `follow_up_needed`, `quote_requested`), notes, and next follow-up date · seen in: *Zoho RouteIQ, Badger Maps, Repsly* · priority: `table-stakes` · spine: `FieldCheckIn` choices · buildable now.
- **Proof-of-Visit Photo Attachment** — Uploading storefront photos, retail shelf displays, or equipment condition directly to the check-in record · seen in: *Badger Maps, Repsly, Zoho RouteIQ* · priority: `common` · spine: FK `core.Document` on `FieldCheckIn` · buildable now.
- **Administrative Force Check-Out Override** — Allowing dispatchers or reps to close unclosed check-ins with an audit flag if a rep moves to another stop without checking out · seen in: *Zoho RouteIQ* · priority: `common` · spine: `is_force_checkout` flag on `FieldCheckIn` · buildable now.
- **Mileage & Travel Distance Tracking** — Recording planned vs. actual mileage per sales route for reimbursement and productivity analysis · seen in: *Repsly, Badger Maps* · priority: `common` · spine: `FieldSalesRoute` fields · buildable now.

### 4.3 Mobile Quoting & Approvals
- **On-the-Spot Mobile Quote Creation** — Rapid, mobile-optimized proposal generator allowing reps to select products, specify quantities, and apply line discounts while standing with the customer · seen in: *Salesforce Mobile, Skynamo, DealHub Mobile* · priority: `table-stakes` · spine: reuses `sales.CPQQuote` (`CPQ-`) and `CPQQuoteLine`, linked to `FieldCheckIn.resulting_quote` · buildable now.
- **Mobile Discount Approval Requests & One-Tap Actions** — Submitting quote exceptions from the phone; managers receive push alerts and can approve or reject with one tap · seen in: *Salesforce Mobile, DealHub Mobile* · priority: `table-stakes` · spine: reuses `sales.QuoteApprovalRule`, notified via `MobileDealAlert` · buildable now.
- **In-Person Screen E-Signatures** — Capturing customer digital signature via touch/stylus directly on the mobile screen during the visit, embedding SVG/data in quote and contract · seen in: *SPOTIO, Salesforce Mobile, DealHub Mobile* · priority: `common` · spine: reuses `CPQQuote.signature_data` & `signing_token` · buildable now.
- **Real-Time Offline Price Book Lookup** — Caching customer-specific pricing tiers and bundle options for instant quotation without internet · seen in: *Skynamo, Salesforce Mobile* · priority: `common` · spine: reuses `crm.PriceBook` · buildable now.

### 4.4 Voice & Call Integration
- **Click-to-Dial via Native `tel:` URI & VoIP** — Initiating calls directly from account and contact cards on mobile devices · seen in: *HubSpot Mobile, Close Mobile* · priority: `table-stakes` · spine: template `tel:` URI helper · buildable now.
- **Post-Call Quick Disposition Modal** — Instant popup after call termination allowing reps to record call duration, disposition outcome (`connected`, `voicemail`, `busy`, `no_answer`), and quick notes · seen in: *HubSpot Mobile, Close Mobile* · priority: `table-stakes` · spine: creates `crm.CommunicationLog` (`COM-`) · buildable now.
- **Voicemail Drop Scripts & Audio Templates** — Quick-select library of standardized voicemail messages and follow-up scripts for field reps when leaving voicemail · seen in: *HubSpot Mobile, Close Mobile* · priority: `common` · spine: script catalog / communication log metadata · buildable now.
- **Caller Context Card** — Displaying recent open opportunities, last visit notes, and outstanding quotes when initiating or receiving a customer call · seen in: *HubSpot Mobile, Close Mobile* · priority: `common` · spine: account summary view · buildable now.

### 4.5 Mobile Dashboards & Alerts
- **Mobile Sales Execution Dashboard** — Compact, mobile-first view showing today's route progress, completed vs pending stops, daily check-in counter, and high-priority deals · seen in: *All leaders* · priority: `table-stakes` · spine: computed mobile dashboard view (`sales:mobile_sales_dashboard`) · buildable now.
- **Mobile Deal Alerts & Push Notifications** — Real-time alerts sent to field reps for deal stage transitions, quote approvals, daily route dispatches, and geofence check-in reminders · seen in: *HubSpot Mobile, Close Mobile, SPOTIO* · priority: `table-stakes` · spine: new table `MobileDealAlert` (`MDA-`) · buildable now.
- **Route Attainment & Progress Bar** — Visual indicator showing percentage of planned stops visited during the active sales day · seen in: *Zoho RouteIQ, SPOTIO* · priority: `common` · spine: computed method on `FieldSalesRoute` · buildable now.
- **Stale Deal & Urgent Task Badges** — Compact notifications on the mobile header flagging neglected accounts and urgent follow-ups due today · seen in: *Salesforce Mobile, HubSpot Mobile* · priority: `common` · spine: mobile alert queries · buildable now.

### 4.6 Beyond the Bullets (High-Value Commercial Capabilities)
- **Ad-Hoc Drop-In Check-In (Unplanned Visits)** — Allowing field reps to check in at nearby accounts without requiring a pre-scheduled route itinerary · seen in: *Badger Maps, SPOTIO* · priority: `table-stakes` · spine: `FieldCheckIn` with nullable `route` FK · buildable now.
- **Nearby Account Locator ("Schedule Gap Filler")** — Radius search finding nearby customer accounts within X kilometers when a scheduled meeting cancels · seen in: *Badger Maps, Zoho RouteIQ* · priority: `differentiator` · spine: spatial query view · buildable now.
- **Direct Traceability: Visit to Quote to Revenue** — Seamless data lineage linking the physical field visit (`FieldCheckIn`) directly to the generated quote (`CPQQuote`) and resulting order (`SalesOrder`) · seen in: *Skynamo, Salesforce Mobile* · priority: `differentiator` · spine: `FieldCheckIn.resulting_quote` FK · buildable now.

---

## 5. Recommended build scope (this pass — 1–4 models)

To fully cover the 5 NavERP.md feature bullets without architectural bloat, we recommend **four (4) tenant-scoped models** under `apps/sales/models/MobileSales/`:

### Model 1: `FieldSalesRoute` [FSR-]
- **Purpose:** Represents a planned or executed daily multi-stop itinerary and travel path for an outside sales rep.
- **Prefix:** `FSR` (e.g. `FSR-00001`) — completely unique, verified zero collisions across repo.
- **Base class:** `TenantNumbered`
- **Key Fields:**
  - `name`: `CharField(max_length=200)` (e.g. "Downtown Retail Corridor - 2026-10-24")
  - `sales_rep`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="field_routes")`
  - `route_date`: `DateField(default=timezone.now)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")`
    - Choices: `draft` (Draft), `scheduled` (Scheduled), `in_progress` (In Progress), `completed` (Completed), `cancelled` (Cancelled)
  - `start_location`: `CharField(max_length=255, blank=True)` (e.g. "HQ Office / Warehouse")
  - `end_location`: `CharField(max_length=255, blank=True)`
  - `total_stops`: `PositiveIntegerField(default=0)`
  - `completed_stops`: `PositiveIntegerField(default=0)`
  - `planned_distance_km`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))`
  - `actual_distance_km`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))`
  - `estimated_duration_minutes`: `PositiveIntegerField(default=0)`
  - `actual_duration_minutes`: `PositiveIntegerField(default=0)`
  - `optimization_status`: `CharField(max_length=20, choices=OPTIMIZATION_CHOICES, default="unoptimized")`
    - Choices: `unoptimized` (Unoptimized), `optimized` (Route Optimized), `manual_order` (Manual Sequence)
  - `notes`: `TextField(blank=True)`
- **Key Methods:** `completion_rate_pct`, `progress_display`, `generate_navigation_url`.
- **FKs to verified entities:** `accounts.User` (`settings.AUTH_USER_MODEL`).

### Model 2: `FieldCheckIn` [CHK-]
- **Purpose:** Captures the physical customer visit, GPS geofence compliance verification, on-site duration, visit outcome, and proof-of-visit attachment. Supports both scheduled route stops and ad-hoc drop-in visits.
- **Prefix:** `CHK` (e.g. `CHK-00001`) — completely unique, verified zero collisions across repo.
- **Base class:** `TenantNumbered`
- **Key Fields:**
  - `route`: `ForeignKey("sales.FieldSalesRoute", on_delete=models.SET_NULL, null=True, blank=True, related_name="check_ins")`
  - `stop_number`: `PositiveIntegerField(default=1)`
  - `party`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="field_check_ins")` (visited client/account)
  - `contact`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="contact_check_ins")`
  - `opportunity`: `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="field_check_ins")`
  - `sales_rep`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="field_check_ins")`
  - *Geofence & Check-In Tracking:*
    - `check_in_at`: `DateTimeField(default=timezone.now)`
    - `check_in_lat`: `DecimalField(max_digits=9, decimal_places=6)`
    - `check_in_lng`: `DecimalField(max_digits=9, decimal_places=6)`
    - `target_lat`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
    - `target_lng`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
    - `geofence_radius_m`: `PositiveIntegerField(default=150)` (metres)
    - `distance_from_target_m`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
    - `is_geofence_verified`: `BooleanField(default=False)`
    - `verification_status`: `CharField(max_length=20, choices=VERIFICATION_CHOICES, default="verified")`
      - Choices: `verified` (Verified On-Site), `out_of_range` (Out of Range), `gps_unavailable` (GPS Unavailable), `manual_override` (Manual Override)
  - *Check-Out & Duration Tracking:*
    - `check_out_at`: `DateTimeField(null=True, blank=True)`
    - `check_out_lat`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
    - `check_out_lng`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
    - `duration_minutes`: `PositiveIntegerField(null=True, blank=True)`
    - `is_force_checkout`: `BooleanField(default=False)`
  - *Visit Outcome & Follow-Up:*
    - `visit_purpose`: `CharField(max_length=30, choices=PURPOSE_CHOICES, default="presentation")`
      - Choices: `prospecting` (Prospecting / Cold Call), `presentation` (Product Demo / Presentation), `quote_review` (Quote Review & Negotiation), `order_collection` (Order Taking), `relationship` (Account Review / Check-In), `audit` (Merchandising / Stock Audit), `service_check` (Service / Support Follow-Up)
    - `outcome`: `CharField(max_length=30, choices=OUTCOME_CHOICES, default="successful")`
      - Choices: `successful` (Successful Visit), `follow_up_needed` (Follow-Up Required), `quote_requested` (Quote Requested), `order_placed` (Order Placed), `decision_maker_unavailable` (Decision Maker Unavailable), `rescheduled` (Rescheduled), `cancelled` (Cancelled)
    - `notes`: `TextField(blank=True)`
    - `next_step`: `CharField(max_length=255, blank=True)`
    - `next_step_due`: `DateField(null=True, blank=True)`
  - *Spine Integrations:*
    - `photo_document`: `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="check_in_photos")`
    - `resulting_quote`: `ForeignKey("sales.CPQQuote", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_check_ins")`
    - `communication_log`: `ForeignKey("crm.CommunicationLog", on_delete=models.SET_NULL, null=True, blank=True, related_name="field_check_ins")`
- **Key Methods:** `calculate_distance(lat, lng)` (Haversine formula), `calculate_duration()`, `clean()`.
- **FKs to verified entities:** `FieldSalesRoute`, `core.Party`, `crm.Opportunity`, `accounts.User`, `core.Document`, `sales.CPQQuote`, `crm.CommunicationLog`.

### Model 3: `MobileDeviceSession` [MDS-]
- **Purpose:** Registers rep mobile devices, tracks platform details, stores push tokens, and monitors offline caching manifests and synchronization health.
- **Prefix:** `MDS` (e.g. `MDS-00001`) — completely unique, verified zero collisions across repo.
- **Base class:** `TenantNumbered`
- **Key Fields:**
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_devices")`
  - `device_uuid`: `CharField(max_length=64, db_index=True)`
  - `device_name`: `CharField(max_length=120)` (e.g. "iPhone 15 Pro", "Samsung Galaxy S24")
  - `platform`: `CharField(max_length=20, choices=PLATFORM_CHOICES, default="web_pwa")`
    - Choices: `ios` (iOS Native), `android` (Android Native), `web_pwa` (Progressive Web App)
  - `app_version`: `CharField(max_length=32, blank=True)`
  - `push_token`: `CharField(max_length=255, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `is_trusted`: `BooleanField(default=True)`
  - `last_sync_at`: `DateTimeField(null=True, blank=True)`
  - `last_sync_status`: `CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default="pending")`
    - Choices: `success` (Synchronized), `partial` (Partial Sync), `failed` (Sync Failed), `pending` (Pending Sync)
  - `offline_records_cached`: `PositiveIntegerField(default=0)`
  - `pending_uploads_count`: `PositiveIntegerField(default=0)`
  - `last_ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `last_known_lat`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `last_known_lng`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
- **Key Methods:** `record_sync_event()`, `is_outdated()`.
- **FKs to verified entities:** `accounts.User` (`settings.AUTH_USER_MODEL`).

### Model 4: `MobileDealAlert` [MDA-]
- **Purpose:** Manages high-urgency notifications delivered to field reps, including discount approval requests, deal stage advances, route dispatch announcements, and stale deal alerts.
- **Prefix:** `MDA` (e.g. `MDA-00001`) — completely unique, verified zero collisions across repo.
- **Base class:** `TenantNumbered`
- **Key Fields:**
  - `recipient`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_deal_alerts")`
  - `device`: `ForeignKey("sales.MobileDeviceSession", on_delete=models.SET_NULL, null=True, blank=True, related_name="received_alerts")`
  - `alert_type`: `CharField(max_length=30, choices=ALERT_TYPE_CHOICES, default="deal_stage_changed")`
    - Choices: `deal_stage_changed` (Deal Stage Advanced), `quote_approval_required` (Quote Discount Approval Required), `route_dispatched` (Daily Route Assigned), `checkin_reminder` (Check-In Reminder), `attainment_milestone` (Quota Milestone Achieved), `contract_expiring` (Contract Expiring Soon)
  - `title`: `CharField(max_length=200)`
  - `message`: `TextField()`
  - `urgency`: `CharField(max_length=20, choices=URGENCY_CHOICES, default="normal")`
    - Choices: `low` (Low Priority), `normal` (Normal), `high` (High Priority), `urgent` (Urgent Action Required)
  - `related_opportunity`: `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_alerts")`
  - `related_quote`: `ForeignKey("sales.CPQQuote", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_alerts")`
  - `related_route`: `ForeignKey("sales.FieldSalesRoute", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_alerts")`
  - `is_read`: `BooleanField(default=False)`
  - `read_at`: `DateTimeField(null=True, blank=True)`
  - `push_status`: `CharField(max_length=20, choices=PUSH_STATUS_CHOICES, default="pending")`
    - Choices: `pending` (Pending Dispatch), `sent` (Dispatched), `delivered` (Delivered), `failed` (Failed)
  - `push_sent_at`: `DateTimeField(null=True, blank=True)`
- **Key Methods:** `mark_as_read()`, `dispatch_alert()`.
- **FKs to verified entities:** `accounts.User`, `MobileDeviceSession`, `crm.Opportunity`, `sales.CPQQuote`, `FieldSalesRoute`.

---

## 6. Belongs to sibling sub-modules (parked, not scoped here)

- **Lead Ingestion & Forms (8.1 Lead Management):** Web form submissions, lead scoring rules, and qualification criteria live in 8.1.
- **Pipeline Stages & Deal Kanban (8.2 Opportunity Management):** Master stage velocity and multi-pipeline boards belong to 8.2; 8.16 surfaces a compact mobile-friendly card view and deal alerts.
- **Master CPQ Rules & Product Bundling (8.5 Quote Proposal & CPQ):** Multi-tier pricing rules, advanced bundle dependencies, and proposal document authoring belong to 8.5. 8.16 consumes existing `CPQQuote` instances for rapid on-site quotation and manager discount approvals.
- **Order Fulfillment & Revenue Recognition (8.6 Order Management):** ASC 606 revenue schedules and warehouse fulfillment belong to 8.6.
- **Territory Alignment & Quotas (8.7 Territory & Quota Management):** Defining polygon territory boundaries and assigning annual quota plans belong to 8.7. 8.16 consumes the assigned accounts for route building.
- **General Sales Activity Goals & Task Templates (8.8 Sales Activity Management):** Broad activity goal planning cycles belong to 8.8.
- **Sales Playbooks & Coaching (8.9 Sales Enablement):** Content repositories and coaching scorecards belong to 8.9.
- **Workflow Automation Engine (8.17 Workflow & Process Automation):** Visual drag-and-drop workflow designer belongs to 8.17.
- **PBX & Telephony Hardware Connectors (8.18 Integration Hub):** Enterprise SIP trunking, live WebRTC softphone media streams, and carrier EDI gateways belong to 8.18.

---

## 7. Deferred (later passes / integrations)

1. **Native iOS (Swift) & Android (Kotlin) Compiled Mobile Apps:** Building and compiling native store binaries via Xcode/Android Studio is deferred. The Django/Tailwind/HTMX responsive mobile web app and PWA manifest ship in this pass; the backend provides JSON/REST endpoints for native client wrappers in a future release.
2. **Live WebRTC Two-Way Telephony Audio Engine:** Streaming VoIP voice packets in real time over WebRTC or Twilio Media Streams is deferred to Sub-module 8.18 (Integration Hub). In 8.16, click-to-dial launches via native `tel:` protocol and call logging records structured interaction metadata to `crm.CommunicationLog`.
3. **Apple Push Notification Service (APNs) & Firebase Cloud Messaging (FCM) Gateways:** Direct TCP push socket handshakes to Apple/Google push servers require cloud service account keys. In 8.16, the data architecture stores push tokens (`MobileDeviceSession.push_token`) and dispatches internal alert rows (`MobileDealAlert`); gateway relays wire up in Sub-module 8.18.
4. **Continuous Background GPS Breadcrumb / Fleet Tracking:** Continuous high-frequency battery-draining GPS location streams are deferred to logistics/fleet management. 8.16 implements point-of-interest check-in and check-out coordinate stamping.
5. **Ringless Voicemail Server Carrier Injection:** Automatic carrier injection of pre-recorded audio files without ringing the recipient requires specialized telecommunications gateways (e.g. Stratics, Kixie, Twilio). 8.16 provides voicemail drop scripts and call disposition tracking.
