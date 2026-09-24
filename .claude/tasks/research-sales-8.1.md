# Research — Sub-module 8.1: Lead Management (Module 8 — Sales Management System, `sales`)

- **Sub-module:** 8.1 Lead Management
- **Module:** 8 Sales Management System
- **Target app:** `apps/sales` (currently absent — this is a new-app first sub-module)
- **Research date:** 2026-09-24
- **Phase:** 1 research only
- **Output boundary:** this artifact only; no application code, migrations, settings, navigation, or commits

## 1. Executive decision

8.1 should be a **Sales-owned lead-operations layer over the existing CRM lead spine**, not a second lead database and not a second conversion engine.

The decisive ownership rule is:

> `crm.Lead` remains the canonical lead, `crm.Opportunity` remains the canonical opportunity, `crm.LandingPage` / `crm.FormSubmission` remain the web-capture primitives, and `crm.EmailCampaign` remains the CRM campaign/drip primitive. Sales 8.1 adds only the explainable scoring, qualification, routing, and nurture-enrollment layer that CRM 1.1/1.2/1.3 does not already own.

### Recommended build scope — exactly four Sales-owned models

1. **`LeadScoreEvent`** — append-only, tenant-scoped behavioral/demographic score facts and corrections.
2. **`LeadQualification`** — one current BANT/MEDDIC assessment per CRM lead.
3. **`LeadRoutingRule`** — deterministic fixed-owner, territory-manager, or round-robin assignment configuration.
4. **`LeadNurtureEnrollment`** — a lead's state inside an existing CRM drip `EmailCampaign`.

No `sales.Lead`, `sales.Opportunity`, `sales.Account`, `sales.Contact`, `sales.LandingPage`, `sales.FormSubmission`, `sales.Campaign`, `sales.EmailCampaign`, or `sales.LeadConversion` model should be created.

### Intentionally deferred parts of the five bullets

- **Capture/ingestion:** web forms, landing pages, manual CRM leads, and form-to-lead conversion are already built in CRM. CSV, API, chatbot, ad-platform, email-parser, business-card OCR, and real web ingestion belong to **8.18 Integration & API Hub** (or a later CRM capture-hardening pass), not to four new Sales tables.
- **Scoring:** deterministic 0–100 fit/engagement grading is in scope. Tenant-authored multiple scoring profiles, arbitrary event-rule builders, ML training, and predictive AI are deferred to **8.12/23**.
- **Routing:** fixed owner, CRM-territory manager, and race-safe round robin are in scope. Seller calendars, capacity-aware load balancing, weighted distribution, and skill-based routing are deferred to **8.7/8.17**.
- **Nurturing:** enrollment, lifecycle, exits, consent evidence, and CRM drip-campaign linkage are in scope. A real scheduler/ESP, multi-step branching engine, dynamic-content renderer, and per-recipient open/click tracking are deferred because the as-built CRM send path is explicitly simulated and has no delivery worker.
- **Conversion/handoff:** a thin Sales orchestration action may reuse one CRM-owned conversion service. The Party/Contact/Opportunity writer stays in CRM. Actual rep-notification delivery, SLA timers, MQL-to-SQL acceptance, and conversion analytics are deferred.

## 2. NavERP scope and local as-built evidence

### 2.1 Exact 8.1 source bullets

`NavERP.md:1306-1311` defines five bullets:

1. **Lead Capture & Ingestion** — web forms, landing pages, chatbots, email parsing, CSV imports, and third-party API ingestion.
2. **Lead Scoring & Grading** — behavioral scoring and demographic/firmographic grading.
3. **Lead Qualification & Routing** — BANT/MEDDIC, territory assignment, and round robin.
4. **Lead Nurturing & Drip Campaigns** — automated sequences, personalization, and engagement tracking.
5. **Lead Conversion & Handoff** — opportunity/account/contact conversion and notification triggers.

### 2.2 New-app state

No `apps/sales/` tree exists, and there is no `LIVE_LINKS["8.1"]` entry. The later Phase 2/3 plan should therefore treat 8.1 as the first scaffold of a new app, while keeping its domain layer thin and CRM-dependent.

### 2.3 Canonical lead and conversion already exist in CRM

`apps/crm/models/CoreData/Leads.py:5-52` defines `crm.Lead` (`LEAD-`) with:

- identity: `name`, `company`, `title`, `email`, `phone`;
- provenance: `source` (`web`, `referral`, `event`, `cold_call`, `email_campaign`, `social`, `other`);
- grading: `rating` (`hot`, `warm`, `cold`) and `score` (0–100);
- lifecycle: `status` (`new`, `contacted`, `qualified`, `unqualified`, `converted`, `recycled`);
- ownership/value: `owner`, `est_value`;
- conversion pointer: `converted_party`.

`apps/crm/views/CoreData/Leads.py:58-87` already implements an atomic one-click conversion that:

- creates an organization `core.Party` + customer `PartyRole` when a company is present;
- creates a person `core.Party` + contact `PartyRole`;
- creates a `ContactMethod` for email;
- creates `crm.Opportunity(source_lead=lead)`;
- marks the lead converted and records audit rows.

Therefore 8.1 must not recreate any of those writes. At most, Sales should offer a thin readiness/handoff orchestration action around the same CRM conversion implementation.

### 2.4 CRM already owns web capture and campaign primitives

- `crm.LandingPage` (`apps/crm/models/MarketingAutomation/LandingPages.py:6-60`) is the published public form/page, with campaign, routing owner, lead source, token, and submission counter.
- `crm.FormSubmission` (`apps/crm/models/MarketingAutomation/FormSubmissions.py:5-41`) is the read-mostly web submission and already links to `crm.Lead` through `converted_lead`.
- `crm.FormSubmission` conversion (`apps/crm/views/MarketingAutomation/FormSubmissions.py:41-64`) is idempotent and creates/routs a `crm.Lead` using the landing page's routing owner.
- `crm.CampaignMember` (`apps/crm/models/MarketingAutomation/Campaigns.py:79-131`) already records per-lead campaign state including `targeted`, `sent`, `opened`, `clicked`, `responded`, `converted`, `bounced`, and `unsubscribed`.
- `crm.EmailCampaign` (`apps/crm/models/MarketingAutomation/EmailCampaigns.py:5-87`) already represents one-time, drip, and A/B sends and owns aggregate engagement counters.
- The current send action is explicitly a simulation (`apps/crm/views/MarketingAutomation/EmailCampaigns.py:57-79`): it stamps counts and member state but sends no email. Sales must not imply that an enrollment is being delivered when the platform has no sender/worker.

### 2.5 Other existing owners Sales must reuse

| Need | Existing owner | 8.1 decision |
|---|---|---|
| Canonical lead | `crm.Lead` | FK by string; never duplicate |
| Opportunity | `crm.Opportunity` | CRM owns it; conversion reuses it |
| Account/contact identity | `core.Party`, `core.PartyRole`, `core.ContactMethod` | never duplicate |
| Account/contact profiles | `crm.AccountProfile`, `crm.ContactProfile` | reuse/read only |
| Territory | `crm.Territory` (`apps/crm/models/SalesForceAutomation/Territories.py:10-33`) | `LeadRoutingRule.territory` FK; no Sales territory table |
| Activity/follow-up | `crm.CrmTask`, `crm.CommunicationLog`, `core.Activity` | create/reuse tasks/logs; no Sales activity table |
| Generic workflow | `crm.WorkflowRule` / bounded engine | does not implement assignment today; 8.1 gets a domain rule, 8.17 gets the general designer |
| Platform workflow registry | `core.WorkflowDefinition` / `WorkflowStep` | documentation only; never a second enforcement engine |
| Notification configuration | `core.NotificationRule` / `NotificationPreference` | future delivery hook; no Sales notification table |
| Audit | `core.AuditLog` | every score/qualification/routing/handoff decision writes audit evidence |
| Consent | `core.ConsentPurpose`, `core.ConsentRecord` | Party-only today; see the pre-conversion gap below |

### 2.6 Important as-built gaps and consequences

1. **CRM currently allows direct score/rating editing.** `apps/crm/forms/CoreData/Leads.py:8-12` includes both `score` and `rating` in `LeadForm`. Once Sales owns event-based scoring, those fields become cached projections and must be removed from the ordinary CRM form; otherwise a user can create score drift with no event. Manual changes should use a bounded Sales action that creates a reasoned `LeadScoreEvent`.
2. **A lead is not a `core.Party` before conversion.** The as-built CRM `Lead` is standalone, while `core.ConsentRecord` requires `party` (`apps/core/models/Consent.py:52-89`). 8.1 cannot honestly claim a full legal-consent check for email nurture without either duplicating consent or creating Parties prematurely. It should record a required consent-purpose/evidence reference and perform no outbound delivery until the platform consent gap is reconciled.
3. **The generic CRM workflow's assign action is not real assignment.** `apps/crm/views/AutomationWorkflow/_engine.py:97-144` logs alert/assign/email as a note rather than mutating ownership. `LeadRoutingRule` is therefore a real domain service, not a duplicate implementation of a working CRM assign action.
4. **The platform notification subsystem does not dispatch.** `apps/core/models/Notification.py:1-28` states that channels/rules/templates exist but nothing sends. A concrete `crm.CrmTask` is the honest 8.1 handoff artifact; actual in-app/email notification delivery is deferred.
5. **The ERD's Module 8 row is stale relative to as-built ownership.** `NavERP-ERD.md:470` lists `Opportunity`, `Quote`, `Forecast`, and `Territory` as Sales additions, but CRM 1.2 already shipped all four. L28/L36 make the code the truth: CRM shipped first and owns them. Sales 8.1 extends them by FK and must not create parallel schemas.

## 3. Commercial products researched (current 2026 web sources)

Eight leading commercial CRM/lead-management products were reviewed. Official current product/help pages were preferred; marketing metrics and unsupported claims were not used as requirements.

| Product | Current evidence reviewed | Useful lead-management patterns | What NavERP should not copy |
|---|---|---|---|
| **Salesforce Sales Cloud** | [Einstein Lead Scoring](https://help.salesforce.com/s/articleView?id=sf.einstein_sales_lead_insights.htm&language=en_US&type=5), [round-robin assignment](https://help.salesforce.com/s/articleView?id=xcloud.essentials_round_robin_lead_assignment.htm&language=en_US&type=5), [lead conversion considerations](https://help.salesforce.com/s/articleView?id=sales.leads_notes.htm&language=en_US&type=5), [official scoring datasheet](https://c1.sfdcstatic.com/content/dam/web/en_us/www/documents/datasheets/sales-cloud-einstein-leadscoring.pdf) | Score from conversion history; expose positive/negative factors; segment scoring models; deterministic assignment rules; duplicate-aware conversion with create-vs-existing choices | Einstein's licensed ML pipeline and Salesforce-specific objects |
| **HubSpot** | [Build lead scores](http://knowledge.hubspot.com/scoring/build-lead-scores), [customer-agent qualification/routing](https://knowledge.hubspot.com/customer-agent/set-up-customer-agent-actions-to-qualify-leads), [lifecycle stages](https://knowledge.hubspot.com/records/use-lifecycle-stages) | Separate fit/engagement/combined scores; positive and negative points; group caps; score decay; score history; threshold labels; qualified / partially qualified / not qualified outcomes; threshold workflow + round robin + rep notification | HubSpot contact/company/deal object model and proprietary credit tiers |
| **Microsoft Dynamics 365 Sales** | [predictive scoring](https://learn.microsoft.com/en-us/dynamics365/sales/digital-selling-scoring), [qualification experience](https://learn.microsoft.com/en-us/dynamics365/sales/define-lead-qualification-experience), [assignment distribution](https://learn.microsoft.com/en-us/dynamics365/sales/understand-lead-distributions-assignment-rules) | Segmented predictive models; explicit qualification/disqualification; seller-vs-system record creation; duplicate checks; round robin based on last assignment; load balancing, capacity, and availability; configurable account/contact/opportunity creation | Power Platform/Copilot dependencies and up-to-five-opportunity conversion behavior |
| **Zoho CRM** | [lead scoring/nurturing](https://www.zoho.com/crm/lead-scoring.html), [lead management](https://www.zoho.com/crm/lead-management), [web forms](https://www.zoho.com/crm/web-forms.html), [conversion API](https://www.zoho.com/crm/developer/docs/api/v8/convert-lead.html) | Fit/engagement scoring; user/role/group round robin; assignment limits and overflow; branching Cadences; web-form approval; duplicate-aware conversion; owner notification; optional deal creation | Zoho-specific Cadences, Zia, and low-code functions |
| **Pipedrive** | [lead management](https://www.pipedrive.com/en/features/manage-leads-deals), [web forms](https://www.pipedrive.com/en/features/web-forms), [Score CRM](https://www.pipedrive.com/en/products/sales/score-crm) | Activity-first Leads Inbox; simple qualification questions; immediate routing; labels; import; chatbot/live chat; convert a qualified lead to a deal; concise scoring UX | Add-on packaging and product statistics |
| **Freshsales** | [CRM features](https://www.freshworks.com/crm/features), [lead-score configuration](https://support.freshsales.io/support/solutions/articles/217948-how-to-configure-lead-score-for-a-business), [classic/smart sequences](https://crmsupport.freshworks.com/support/solutions/articles/50000002163-what-are-classic-and-smart-sequences-where-should-they-be-used-) | Score lead properties, email, application, and web activity; 1–99 hot/warm/cold thresholds; territory auto-assignment; internal notifications; ordered and behavior-branching sequences | Product/plan gates and support-portal age; NavERP must state what actually executes |
| **monday sales CRM** | [lead management board](https://support.monday.com/hc/en-us/articles/360008648359-Lead-management-with-monday-CRM), [lead management use case](https://www.monday.com/crm/use-cases/lead-management) | One operational board; owner/status/score visible together; transparent formula scoring; duplicate/existing-account indicators; forms/import/integrations; activity timeline; qualification automation | Board-column architecture and monday AI agents |
| **SugarCRM / Sugar Market** | [scoring profiles](https://support.sugarcrm.com/documentation/market/sugar_market_user_guide/scoring/creating_scoring_profiles), [lead conversion](https://support.sugarcrm.com/documentation/sugar_versions/14.0/ent/application_guide/leads), [lead-management best practices](https://sugarclub.sugarcrm.com/cfs-file/__key/articles/8ea8129c10c64ed3a405a03fed4e133c-a-6f3ea3fb4c3c4675900d55dde2fe08ed/7853.Mastering-Lead-Management_2D00_Best-Practices-for-Success.pdf) | Multiple scoring profiles; threshold stages; positive/negative points; web/email/landing/event/demographic scoring; decay; threshold actions that enroll nurture, create tasks, alert, or create an opportunity; rule-based/BANT/round-robin qualification | Separate marketing product synchronization and unbounded profile/action builder in 8.1 |

### Cross-product conclusions

1. **Fit and engagement are different signals.** Enterprise products commonly show them separately or as a combined score, not just one opaque number.
2. **Scores need explanations and history.** Positive/negative factors, score history, and threshold stages are table stakes; a bare editable integer is not credible.
3. **Qualification is structured and tri-state.** Qualified, partially qualified/nurture, and disqualified are more useful than a binary checkbox.
4. **Routing is deterministic and explainable.** Priority, explicit criteria, a named method, fallback behavior, and an audit reason matter more than an opaque AI match.
5. **Round robin needs concurrency semantics.** The cursor/state must be locked, and manual assignments should not corrupt the sequence.
6. **Conversion must be duplicate-aware.** The surveyed leaders match existing accounts/contacts before creating records. NavERP's current CRM conversion always creates new Parties; that gap belongs to CRM hardening, not a Sales duplicate.
7. **Sequence UI must be honest about execution.** Freshsales, Zoho, and HubSpot have real execution engines. NavERP currently has campaign models and a simulated send; 8.1 should expose enrollment/state, not claim delivery.

## 4. Deduplicated, prioritized feature catalog

Priority meanings:

- **P0 — build in 8.1:** necessary for a credible, coherent first slice.
- **P1 — useful next refinement:** valuable but not required for the first ownership-safe pass.
- **P2 — defer:** requires a later module, a platform worker, external transport, or materially different ownership.

### 4.1 Lead Capture & Ingestion

| ID | Feature | Product evidence | NavERP mapping | Priority / decision |
|---|---|---|---|---|
| C1 | One canonical lead intake view across web, manual, campaign, and imported sources | Pipedrive, monday, Zoho | Read `crm.Lead`; link to `crm.FormSubmission`, `crm.CampaignMember`, and source/campaign fields | P0, non-model Sales operations board |
| C2 | Published web forms and landing pages | Salesforce, HubSpot, Zoho, Pipedrive, Freshsales, monday | Reuse `crm.LandingPage` / `crm.FormSubmission` | Already built in CRM; no Sales model |
| C3 | Manual CRM lead entry | Every leader | Reuse `crm:lead_create` | Already built in CRM |
| C4 | Duplicate / existing-account warning before qualification | monday, Salesforce, Zoho, Dynamics | Normalized email/company match shown on Sales operations board; no merge/delete | P1, read-only warning |
| C5 | Source and campaign lineage | Salesforce, Zoho, monday, Freshsales | Reuse `Lead.source`, `FormSubmission.landing_page`, `LandingPage.campaign`, `CampaignMember.campaign` | Already built; expose on board |
| C6 | Consent evidence at capture | Freshsales/Sugar marketing automation patterns | Current public form captures no consent; `core.ConsentRecord` requires a Party | P0 only as an evidence reference on nurture enrollment; no delivery claim |
| C7 | CSV import | Zoho, monday, Pipedrive, Salesforce | No Sales ingestion table | P2 → 8.18 |
| C8 | Chatbot/live chat | Pipedrive, Zoho, monday, Freshsales | No Sales chat model | P2 → 8.18 / 9 |
| C9 | Email parsing and business-card OCR | NavERP 1.1 / market OCR patterns | No parser/OCR worker | P2 → 8.18 / CRM hardening |
| C10 | Third-party API/ad ingestion | Salesforce, monday, Zoho | 8.18 connector/run architecture | P2 → 8.18 |

### 4.2 Lead Scoring & Grading

| ID | Feature | Product evidence | NavERP mapping | Priority / decision |
|---|---|---|---|---|
| S1 | Combined 0–100 fit + engagement score | HubSpot, Salesforce, Freshsales, Sugar, monday | Project onto existing `crm.Lead.score` | P0 |
| S2 | Hot / warm / cold projection | CRM already has choices; every surveyed leader grades leads | `crm.Lead.rating`; fixed initial bands (cold 0–39, warm 40–69, hot 70–100) | P0 |
| S3 | Append-only event history with reason and timestamp | HubSpot score history, Salesforce factors, Sugar activity points | `LeadScoreEvent` | P0 |
| S4 | Positive and negative points | HubSpot, Freshsales, Sugar, Zoho | Signed `score_delta`; decay/unsubscribe/fit mismatch can subtract | P0 |
| S5 | Explainable matched behavior/firmographic signals | Salesforce factors, monday formula, Sugar rules | `signal_category`, `event_type`, `source_kind`, `source_ref`, `reason` | P0 |
| S6 | Correct a bad event without rewriting history | Audit/compliance requirement across leaders | Compensating event with `corrects_event`; no edit/delete | P0 |
| S7 | Idempotent replay handling | API/event-driven leaders | Tenant-scoped nullable `idempotency_key` unique key | P0 |
| S8 | Event expiry / score decay | HubSpot, Freshsales, Sugar | `effective_until`; score recomputation ignores expired facts | P1 |
| S9 | Group caps and multiple fit/engagement subscores | HubSpot, Salesforce, Sugar | Useful, but requires a separate scoring-profile model or richer event metadata | P2 → later scoring-profile pass |
| S10 | Tenant-authored scoring profiles and arbitrary property rules | HubSpot, Freshsales, Sugar | Needs configuration UI + historical versioning | P2 → 8.12 |
| S11 | Predictive/AI scoring | Salesforce, Dynamics, monday, Zoho | Needs enough labeled conversion history and an ML/AI module | P2 → 8.12/23 |

### 4.3 Lead Qualification & Routing

| ID | Feature | Product evidence | NavERP mapping | Priority / decision |
|---|---|---|---|---|
| Q1 | Structured BANT/MEDDIC assessment | NavERP bullet; Salesforce/Dynamics/Sugar qualification flows | `LeadQualification` | P0 |
| Q2 | Unassessed / partially qualified / qualified / disqualified / archived | HubSpot, Dynamics, monday, Sugar | `LeadQualification.status`; qualified/disqualified project to CRM Lead status | P0 |
| Q3 | Explicit framework and evidence | BANT/MEDDIC leaders | `framework`, fixed evidence fields, assessor, review date | P0 |
| Q4 | Eligibility guard before marking qualified | Dynamics, monday structured process | Required framework-specific fields when status becomes qualified | P0 |
| Q5 | Deterministic priority resolver | Salesforce/Dynamics assignment rules, Sugar routing | `priority`, stable `id` tie-breaker, typed conditions | P0 |
| Q6 | Fixed-owner routing | All enterprise leaders | `assignment_mode='fixed_owner'` | P0 |
| Q7 | Territory-based routing | Salesforce/Dynamics/Zoho/Freshsales | Criteria + FK to existing `crm.Territory`; territory manager assignment | P0 |
| Q8 | Round-robin distribution | Salesforce, Dynamics, Zoho, Freshsales | Eligible-owner M2M + locked cursor + last owner/time | P0 |
| Q9 | Capacity cap and explicit fallback | Zoho, Dynamics | Optional max-open-leads and fallback owner | P1 |
| Q10 | Dry-run preview and match reason | Mature admin UX | Preview against a tenant lead, no mutation | P0 |
| Q11 | Audit of every assignment decision | Security/operations requirement | `core.AuditLog` with rule, before/after owner, reason | P0 |
| Q12 | Seller availability and capacity-aware load balancing | Dynamics | Needs calendar/capacity data and 8.7 coverage | P2 → 8.7/8.17 |
| Q13 | Skill/weighted routing | CRM enterprise routing | No sales-skill/capacity spine | P2 → 8.7/8.17 |

### 4.4 Lead Nurturing & Drip Campaigns

| ID | Feature | Product evidence | NavERP mapping | Priority / decision |
|---|---|---|---|---|
| N1 | Enroll a lead in an existing drip campaign | Zoho, Freshsales, HubSpot, Sugar | `LeadNurtureEnrollment.email_campaign → crm.EmailCampaign(send_type='drip')` | P0 |
| N2 | Per-lead enrollment lifecycle and exit reason | Every sequence product | `pending/active/paused/completed/cancelled/replied/converted` | P0 |
| N3 | Stop nurture on reply, disqualification, qualification, or conversion | HubSpot/Freshsales/Sugar branching | Lifecycle verbs + compensating updates | P0 |
| N4 | Score snapshot at enrollment | HubSpot threshold workflows, Sugar threshold actions | `score_at_enrollment` and trigger kind | P0 |
| N5 | Consent-purpose/evidence gate | Freshsales/Zoho/Sugar marketing automation | FK to `core.ConsentPurpose` + evidence reference; no parallel consent log | P0, with the Party gap disclosed |
| N6 | Touch count / last touch / next touch visibility | Sequence products | Stored state, not a scheduler | P0 |
| N7 | Dynamic score-based exit/re-entry | HubSpot, Sugar | One enrollment per lead+campaign, reactive lifecycle | P1 |
| N8 | Multi-step delays, branches, and personalization | Freshsales, Zoho, HubSpot, Keap-class products | CRM `EmailCampaign` has no step model/renderer | P2 → CRM 1.3 hardening / 8.18 |
| N9 | Real email/SMS delivery and provider | Zoho/Freshsales/HubSpot | NavERP has no worker and CRM send is simulated | P2 → platform 0.12/8.18 |
| N10 | Per-recipient open/click tracking | Salesforce/HubSpot/Freshsales/Sugar | CRM counters are aggregate and modelled | P2 → 8.18 |

### 4.5 Lead Conversion & Handoff

| ID | Feature | Product evidence | NavERP mapping | Priority / decision |
|---|---|---|---|---|
| H1 | Handoff readiness panel | Salesforce/Dynamics/Pipedrive/Freshsales | Sales view over score + qualification + owner + nurture state | P0 |
| H2 | One CRM-owned conversion writer | Salesforce, Dynamics, Zoho, Pipedrive, Freshsales | Extract current CRM atomic body into a CRM service; CRM view and thin Sales handoff both call it | P0 ownership-preserving integration |
| H3 | Exit active nurture enrollments on conversion | HubSpot/Freshsales/Sugar workflows | Sales updates its enrollments after CRM service succeeds | P0 |
| H4 | Create owner follow-up task | Salesforce/Zoho/Sugar threshold actions | Reuse `crm.CrmTask`; no Sales task model | P0 |
| H5 | Assigned-rep notification | HubSpot, Zoho, Freshsales, monday | `core.NotificationRule('lead.routed')` is a future hook; actual dispatch is unavailable | P0 task + audit; P2 delivery |
| H6 | Choose existing vs new account/contact | Salesforce, Dynamics, Zoho | Current CRM conversion always creates; fixing this changes CRM identity behavior | P2 → CRM conversion hardening |
| H7 | Duplicate prevention before conversion | Salesforce, Dynamics, Zoho, monday | Operations-board warning first; safe matching/merge later | P1 warning; P2 merge |
| H8 | First-response SLA and breach alerts | Salesforce/Dynamics/Freshsales | No scheduler and 8.12 analytics not built | P2 → 8.12/8.17 |
| H9 | MQL→SQL acceptance/rejection and attribution | HubSpot, Sugar | NavERP 8.13 named MQL-to-SQL bullet | P2 → 8.13 |
| H10 | Lead-to-opportunity funnel analytics | Salesforce, Dynamics, monday, Pipedrive | NavERP 8.12 analytics | P2 → 8.12 |

## 5. Recommended model design — exactly four

All four models must carry `tenant = ForeignKey('core.Tenant', ...)` and be filtered by `tenant=request.tenant` in every view. Peer-app references use string labels such as `"crm.Lead"`, `"crm.EmailCampaign"`, and `"crm.Territory"`.

### 5.1 `LeadScoreEvent` — unnumbered, append-only score fact

**Purpose:** one explainable behavioral, demographic, qualification, decay, or manual score fact. The current `crm.Lead.score` and `crm.Lead.rating` are cached projections of this ledger, not independently editable business facts.

**Proposed fields:**

| Field | Idea / choices | Rules |
|---|---|---|
| `tenant` | `core.Tenant` | required; indexed |
| `lead` | `crm.Lead`, CASCADE | required; cross-tenant mismatch rejected |
| `signal_category` | `behavioral`, `demographic`, `qualification`, `manual`, `decay`, `correction` | closed choice list |
| `event_type` | `form_submitted`, `email_open`, `email_click`, `web_visit`, `content_download`, `event_attendance`, `meeting_booked`, `demo_request`, `call_connected`, `reply_received`, `fit_match`, `fit_mismatch`, `unsubscribe`, `manual_adjustment`, `decay`, `correction` | closed choice list; unsupported web events simply receive no rows until 8.18 |
| `score_delta` | signed small integer, bounded to a documented range such as -100..100 | system-calculated for normal events; manual action requires a reason; never directly form-editable |
| `source_kind` | `form_submission`, `campaign_member`, `communication_log`, `qualification`, `web_tracking`, `api`, `manual` | provenance, not an executable model reference |
| `source_ref` | short opaque provenance string, max 255 | no GenericForeignKey and no dereference; prevents cross-tenant object traversal |
| `reason` | required human explanation | mandatory for manual/correction events |
| `effective_until` | nullable timestamp | expired facts no longer contribute; no background decay worker required |
| `idempotency_key` | nullable 120-char hash | unique with tenant so replayed source events cannot double-score |
| `corrects_event` | nullable self-FK | a correction creates an inverse-delta event; history is never edited |
| `occurred_at` | timestamp | source event time, default now |
| `recorded_by` | nullable `accounts.User` | null only for system ingestion |
| `created_at` | timestamp | immutable receipt time |

**Indexes / constraints:**

- unique `(tenant, idempotency_key)` while allowing multiple null keys;
- `(tenant, lead, -occurred_at)`;
- `(tenant, event_type, -occurred_at)`;
- `(tenant, source_kind, source_ref)` if source-ref history is queried;
- `corrects_event` cannot point to itself or to another tenant's event.

**Why this is Sales-owned:** CRM owns the lead and campaign facts; Sales owns the normalized, replay-safe scoring interpretation and correction ledger. It does not duplicate `CampaignMember`, `CommunicationLog`, or `FormSubmission`.

**UX/CRUD:** list + detail only. A POST-only `correct` action creates the compensating event. No edit/delete route and no ordinary create form. Manual adjustment is a separate POST action with reason and audit. This is the same append-only posture used by CRM workflow logs and other event ledgers.

**Initial scoring policy:** transparent constants, not a fake AI model:

- cold = 0–39;
- warm = 40–69;
- hot = 70–100;
- sum all unexpired `score_delta` rows for the lead;
- clamp only the projection to 0–100; never truncate stored event facts;
- `rating` and `score` are updated together inside the same transaction.

A tenant-editable scoring-profile model is deferred.

### 5.2 `LeadQualification` — unnumbered One-to-One current assessment

**Purpose:** structured fit and qualification evidence for the selected BANT/MEDDIC framework, without adding another contact, account, or lead table.

**Proposed fields:**

| Field | Idea / choices | Rules |
|---|---|---|
| `tenant` | `core.Tenant` | required; indexed |
| `lead` | OneToOne `crm.Lead` | required; one current assessment per lead; same-tenant validation |
| `framework` | `bant`, `meddic`, `both` | required |
| `status` | `unassessed`, `partially_qualified`, `qualified`, `disqualified`, `archived` | required; default `unassessed` |
| `country_code` | normalized two-letter code | free normalized field; no unbuilt Country master |
| `region`, `city` | routing geography | plain fields; no duplicate Address/Party |
| `industry` | text | routing/fit input |
| `employee_count` | nullable positive integer | firmographic fit/routing input |
| `seniority` | `unknown`, `individual_contributor`, `manager`, `director`, `executive`, `owner` | explicit interpretation, not inferred silently from title |
| `budget_status` | `unknown`, `not_confirmed`, `confirmed`, `adequate`, `insufficient` | BANT state |
| `budget_amount` | nullable `DecimalField(18,2)` | zero is not used as “unknown” |
| `budget_currency` | nullable FK `accounting.Currency` | required when budget amount is set; Currency is a global reference master; no ledger effect |
| `authority_level` | `unknown`, `influencer`, `user`, `manager`, `director`, `executive`, `owner` | BANT authority |
| `need_summary` | text | BANT need |
| `expected_purchase_on` | nullable date | BANT timeline; no invented quarter bucket |
| `economic_buyer` | text | MEDDIC |
| `decision_criteria` | text | MEDDIC |
| `decision_process` | text | MEDDIC |
| `technical_requirements` | text | MEDDIC |
| `pain_points` | text | qualification context |
| `success_metrics` | text | MEDDIC/qualification outcome |
| `disqualification_reason` | text | required when status is disqualified |
| `assessed_by` | `accounts.User` | required when a terminal assessment is saved |
| `assessed_at` | timestamp | system-set on assessment |
| `next_review_on` | nullable date | stale/partially qualified follow-up |
| `notes` | text | free staff context |
| `created_at`, `updated_at` | timestamps | normal mutable assessment |

**Qualification invariants:**

- `qualified` requires the minimum evidence for the selected framework; BANT and MEDDIC both require need/timeline, while MEDDIC additionally requires economic buyer, decision criteria, and decision process.
- `disqualified` requires a reason.
- qualification changes create compensating `LeadScoreEvent` rows for changed fit signals rather than mutating score history;
- qualified/disqualified may project to `crm.Lead.status`, but `LeadQualification.status` is the richer 8.1 truth;
- archived assessments cannot be selected for new routing.

**Why this is Sales-owned:** CRM owns basic identity/lifecycle. Sales owns the advanced qualification evidence and readiness decision. Geography and firmographics live here because the current CRM Lead lacks address/industry/employee fields; they are not a second Party/Address master.

**UX/CRUD:** full list/detail/create/edit/delete. Delete is allowed only while unassessed and before lead conversion; meaningful assessments are archived. List filters: status, framework, country/region, seniority, budget status, assessor, review due. Detail actions: mark partially qualified, mark qualified, disqualify, recalculate fit score, and preview routing.

### 5.3 `LeadRoutingRule` — unnumbered tenant configuration

**Purpose:** a deterministic, explainable owner resolver. It writes only the existing `crm.Lead.owner`; it does not create a queue, territory, rep-capacity, or user table.

**Proposed fields:**

| Field | Idea / choices | Rules |
|---|---|---|
| `tenant` | `core.Tenant` | required; indexed |
| `name` | human label | unique with tenant |
| `description` | text | operator explanation |
| `is_active` | boolean | default true |
| `priority` | positive integer | lower evaluates first |
| `match_mode` | `all`, `any` | explicit condition combination |
| `conditions` | structured JSON list | only concrete allowlisted fields/operators; no Python, imports, `eval`, model traversal, or relation dereference |
| `assignment_mode` | `fixed_owner`, `territory_manager`, `round_robin` | one writer path per mode |
| `default_owner` | nullable `accounts.User` | required for fixed-owner mode |
| `territory` | nullable `crm.Territory` | required for territory-manager mode; same tenant |
| `eligible_owners` | M2M `accounts.User` | non-empty for round robin; all users must belong to tenant |
| `fallback_owner` | nullable `accounts.User` | optional explicit overflow destination |
| `max_open_leads` | nullable positive integer | optional P1 capacity ceiling |
| `cursor` | non-negative integer, `editable=False` | locked round-robin offset |
| `last_assigned_owner` | nullable `accounts.User`, `editable=False` | operational visibility |
| `last_assigned_at` | nullable timestamp, `editable=False` | operational visibility |
| `created_at`, `updated_at` | timestamps | normal mutable config |

**Condition allowlist:**

- CRM Lead concrete fields: `source`, `status`, `rating`, `score`, `est_value`, `owner_id`, `company`, `title`, `email_present`, `phone_present`;
- qualification fields: `qualification_status`, `framework`, `country_code`, `region`, `city`, `industry`, `employee_count`, `seniority`, `budget_status`, `authority_level`, `expected_purchase_on`;
- operators: `eq`, `ne`, `in`, `not_in`, `contains`, `icontains`, `gt`, `gte`, `lt`, `lte`, `is_set`, `is_empty`.

Unknown fields/operators fail closed. Empty conditions are legal only for an explicit catch-all rule and should be visibly warned about.

**Resolution invariant:**

1. load active rules for the lead tenant ordered by `priority`, then `id`;
2. evaluate the first matching rule only;
3. no match means “unrouted” and a reason, never a hidden arbitrary owner;
4. fixed owner uses `default_owner`;
5. territory mode requires the rule's territory and uses its manager;
6. round robin locks the rule row, reads eligible owner IDs in stable PK order, rotates from the cursor, skips an owner over `max_open_leads`, and updates cursor/last owner in the same transaction;
7. if all pool users are over capacity, use an explicit valid fallback or leave the lead unassigned;
8. write `crm.Lead.owner`, a `crm.CrmTask`, and `core.AuditLog` atomically.

**Why this is not a duplicate:**

- `crm.Territory` remains the territory master;
- `accounts.User` remains the rep master;
- `crm.WorkflowRule` remains the bounded generic CRM workflow; its current assign action is only logged;
- `core.WorkflowDefinition` remains documentation/monitoring, not an executor;
- 8.17 may later make the visual workflow engine call this domain resolver, but must not create a second owner decision.

**UX/CRUD:** member-readable list/detail; create/edit/delete and test/preview are tenant-admin operations. A preview against a chosen tenant lead shows matched conditions and candidate owner without mutation. A real run is POST-only, CSRF-protected, idempotent by `(lead, rule, current owner)`, and audit logged.

**Why no number:** it is configuration like `procurement.ApprovalRoutingRule`, not a business document referenced by an external number. It also avoids the already-used `LR` prefix (HRM leave request).

### 5.4 `LeadNurtureEnrollment` — `LNE-`, numbered per enrollment

**Purpose:** track a lead's participation in an existing CRM drip campaign. It does not own templates, campaign content, email bodies, or an ESP.

**Proposed fields:**

| Field | Idea / choices | Rules |
|---|---|---|
| `tenant` | `core.Tenant` | required; indexed |
| `lead` | `crm.Lead`, CASCADE | required; same tenant |
| `email_campaign` | `crm.EmailCampaign` | required; same tenant; must have `send_type='drip'` before activation |
| `number` | `LNE-#####` | per tenant; prefix verified free |
| `status` | `pending`, `active`, `paused`, `completed`, `cancelled`, `replied`, `converted` | lifecycle state |
| `trigger_kind` | `manual`, `score_threshold`, `form_source`, `qualification`, `recycled` | why the lead entered nurture |
| `score_at_enrollment` | 0–100 snapshot | immutable after activation unless a compensating re-enrollment is explicit |
| `consent_purpose` | FK `core.ConsentPurpose` | required before activation when the purpose is optional |
| `consent_evidence` | max 255 reference | required for activation; e.g. FormSubmission/reference, not a parallel consent log |
| `owner` | nullable `accounts.User` | internal owner; same tenant |
| `started_at` | timestamp | system-set on activation |
| `last_touch_at` | nullable timestamp | system-managed observation |
| `next_touch_at` | nullable timestamp | recorded target; no claim that a scheduler will send it |
| `touch_count` | non-negative integer, `editable=False` | system-managed observation |
| `completed_at` | nullable timestamp | system-set on terminal completion |
| `exit_reason` | text/choice | required for cancelled/replied/converted/disqualified exit |
| `notes` | text | staff context |
| `created_at`, `updated_at` | timestamps | normal enrollment state |

**Constraints/indexes:**

- unique `(tenant, lead, email_campaign)` — one reusable enrollment row per lead/campaign pair;
- indexes `(tenant, status, next_touch_at)` and `(tenant, email_campaign, status)`;
- activation rejects a non-drip campaign, a cross-tenant FK, or missing consent evidence for an optional purpose;
- status transitions are explicit verbs, not arbitrary form overwrites;
- converted leads cannot have active enrollments.

**Why this is Sales-owned:** CRM owns campaign/template/member/delivery concepts. Sales owns the lead-specific lifecycle and the decision that this lead is being nurtured versus ready for sales.

**UX/CRUD:** full list/detail/create/edit/delete before activation; after activation, use activate/pause/resume/complete/cancel/reply/convert verbs instead of destructive editing. The detail links to the CRM campaign and shows `next_touch_at` honestly as a recorded target, not a guaranteed send. No email body, step builder, or send button is added.

## 6. Cross-model service invariants

### 6.1 One scoring writer

A Sales service should be the only normal writer of `crm.Lead.score` and `crm.Lead.rating` after 8.1. It must:

1. lock the tenant lead row;
2. reject a duplicate `idempotency_key`;
3. append the event;
4. sum unexpired deltas;
5. clamp and map the projection;
6. update CRM Lead and audit in the same transaction.

The ordinary CRM `LeadForm` must no longer expose `score` or `rating`; a manual Sales adjustment creates an event.

### 6.2 Qualification and auto-routing

When a user marks a lead qualified, the Sales qualification action should:

1. validate BANT/MEDDIC evidence;
2. save the current assessment;
3. append compensating score facts for changed fit signals;
4. project `crm.Lead.status='qualified'`;
5. run the deterministic routing resolver;
6. create the owner follow-up task and audit rows.

This is rule-driven auto-assignment without a hidden global `post_save` signal. Direct CRM form/import paths remain CRM-owned; a Sales operations board can route an unprocessed lead explicitly, and 8.18 ingestion can call the same service later.

### 6.3 Nurture exits

- mark replied → pause/complete with `exit_reason='replied'`;
- mark disqualified → exit with `exit_reason='disqualified'`;
- mark qualified → exit or complete with `exit_reason='qualified'`, unless the tenant explicitly keeps an approved follow-up sequence;
- CRM conversion succeeds → exit with `exit_reason='converted'`;
- unsubscribe/bounce event → exit with the corresponding reason;
- no re-enrollment after a terminal exit unless an admin reactivates the same row and the audit explains why.

### 6.4 Conversion handoff without a second writer

Recommended integration:

1. extract the current atomic body of `crm.lead_convert` into a CRM-owned service that remains the only Party/Contact/Opportunity writer;
2. keep `crm:lead_convert` behavior unchanged from the user's perspective;
3. add a thin `sales:lead_handoff` POST action that requires a current qualified `LeadQualification`, calls the CRM service, and only on success exits nurture enrollments, creates the `crm.CrmTask`, and writes audit evidence;
4. never copy the Party/Opportunity creation block into Sales.

If Phase 2 chooses not to refactor CRM, the acceptable fallback is a readiness page linking to `crm:lead_convert`, not a duplicated conversion action.

## 7. UX and CRUD implications

### 7.1 Package and template layout for the later build

Models/forms/views/urls should use the mandatory new-app package layout:

- `apps/sales/models/LeadManagement/LeadScoreEvents.py`
- `apps/sales/models/LeadManagement/LeadQualifications.py`
- `apps/sales/models/LeadManagement/LeadRoutingRules.py`
- `apps/sales/models/LeadManagement/LeadNurtureEnrollments.py`
- matching files under `forms/`, `views/`, and `urls/`;
- templates under `templates/sales/leadmanagement/<entity>/`.

The append-only event gets `templates/sales/leadmanagement/leadscoreevent/{list,detail}.html`; the other three get standard `list/detail/form.html` triples.

### 7.2 Operations board

A non-model `templates/sales/overview.html` or lead-operations board should read `crm.Lead` and display:

- name/company/source/status/owner/score/rating;
- Sales qualification status/framework/assessed date;
- latest score event;
- routing rule/last assignment;
- active nurture campaign(s);
- duplicate/existing-party warning;
- links to `crm:lead_detail`, campaign/form submission, and CRM conversion.

It must not offer a second edit form for the CRM lead.

### 7.3 CRUD posture by model

| Model | List/detail | Create/edit/delete | Custom POST actions |
|---|---:|---:|---|
| `LeadScoreEvent` | yes | no edit/delete; manual action only | correct, adjust, recompute stale scores |
| `LeadQualification` | yes | full CRUD, with archive/delete guard | mark partial/qualified/disqualified, score/recalculate, preview route |
| `LeadRoutingRule` | yes | full CRUD, writes admin-only | enable/disable, dry-run preview, run on lead |
| `LeadNurtureEnrollment` | yes | CRUD only before activation; lifecycle verbs after | activate, pause, resume, complete, cancel, reply, convert-exit |

### 7.4 Required list filters and pagination

- score events: category, event type, source kind, lead, date range;
- qualifications: status, framework, country/region, seniority, budget status, assessor, review due;
- routing rules: active, assignment mode, territory, priority;
- nurture enrollments: status, trigger, email campaign, owner, next-touch due;
- every list searches before pagination and every filter select has a tenant-scoped queryset.

### 7.5 Suggested sidebar mapping

- **Lead Capture & Ingestion** → existing `crm:formsubmission_list` (clearly labeled as shared CRM intake), with the Sales board linking back;
- **Lead Scoring & Grading** → `sales:lse_list` or the operations board's score lens;
- **Lead Qualification & Routing** → `sales:lql_list` / `sales:lrr_list`;
- **Lead Nurturing & Drip Campaigns** → `sales:lne_list`, with links to CRM email campaigns;
- **Lead Conversion & Handoff** → Sales operations/qualification detail, ending in the CRM-owned conversion action.

The five bullets remain visible even though only four new models exist because capture and conversion reuse CRM surfaces.

## 8. Security, tenancy, and integrity requirements

1. **Tenant scope on every model, query, and FK.** Forms must scope lead, owner, territory, campaign, purpose, and other tenant-owned querysets; M2M owner validation must reject tenantless and foreign users.
2. **No GFK for score provenance.** `source_kind` + opaque `source_ref` is enough. A GFK would make an untrusted source id an object-traversal/IDOR risk and would be hard to tenant-filter.
3. **Closed routing language.** Validate JSON structure, field allowlist, operator allowlist, scalar value size, and condition count. Never call Python `eval`, import a model dynamically, traverse relations, or evaluate arbitrary expressions.
4. **Configuration writes are privileged.** Routing-rule writes, manual score adjustments, qualification deletion/archive after use, and nurture activation are tenant-admin operations. Routine staff can view, assess, and run approved rules.
5. **Append-only scoring.** No edit/delete route. Corrections are inverse events. The ordinary CRM Lead form cannot write score/rating after this integration.
6. **Race-safe routing.** Lock the selected rule and lead in one transaction; stable owner ordering; deterministic cursor; bounded operations; no network calls while locks are held.
7. **Idempotent score ingestion.** Tenant + idempotency key; replay returns the existing fact and does not add points twice.
8. **No hidden tenantless behavior.** `request.tenant=None` returns empty lists and cannot route. Superuser data remains invisible by design.
9. **Consent honesty.** Do not store a second `has_consent` boolean. Store the purpose and evidence reference only; no email is sent. The Party-only `core.ConsentRecord` gap must be visible on the UI.
10. **No new public endpoint.** Public landing-page rate limiting and reverse-proxy IP trust remain CRM/platform concerns. 8.1 adds no unauthenticated API.
11. **PII minimization.** List pages show only the lead number/name/company needed for triage; long qualification/notes text is deferred or truncated consistently. Logs and audit changes must not include full note bodies or secrets.
12. **Bounded preview/run.** Rule preview is read-only. A run is explicitly POST-only and may affect one lead at a time. Any future bulk run must be paginated/bounded rather than loading every lead into memory.
13. **Same-tenant subject checks.** A qualification, correction, routing assignment, and nurture enrollment must all agree on the same lead tenant, not merely on the request tenant.
14. **Audit all cross-app projections.** Score, rating, CRM Lead status, owner, qualification, nurture exits, and conversion handoff must be explainable through `core.AuditLog`.

## 9. Ownership map for adjacent NavERP work

| Area | Owner | 8.1 boundary |
|---|---|---|
| Lead master/basic lifecycle/conversion | CRM 1.1 | FK/read plus tightly controlled projections; no duplicate |
| Opportunity/pipeline/quote/territory/forecast | CRM 1.2 as built | 8.1 only references `crm.Territory`; 8.2/8.5/8.7 extend CRM rows later |
| Landing pages/forms/campaigns/email | CRM 1.3 | consume and link; no Sales duplicate |
| Tasks/calls/email/calendar | CRM 1.5 | create/reuse `crm.CrmTask` / `CommunicationLog` |
| Dedupe/merge | CRM/core identity hardening | warning only in 8.1; no destructive merge |
| Qualification analytics/funnel | Sales 8.12 | defer |
| MQL→SQL handoff/SLA/attribution | Sales 8.13 | defer |
| Territory capacity/rebalancing/quota | Sales 8.7 | current routing rule may reference CRM Territory now; advanced coverage later |
| General visual workflow/auto-assignment | Sales 8.17 | may orchestrate 8.1's resolver; must not duplicate its decision |
| API/CSV/ad/chat/email/ESP connectors | Sales 8.18 | future callers of Sales lifecycle services |
| Predictive/AI scoring | Sales 8.12 / AI 23 | defer until labeled history and governance exist |
| Notification dispatch | Core 0.12 platform | 8.1 writes task/audit and can expose a future event key; no fake send |

## 10. Recommended Phase 2 handoff checklist

The todo/contract phase should explicitly require:

- [ ] exactly four new Sales models: score event, qualification, routing rule, nurture enrollment;
- [ ] no `sales.Lead`, duplicate opportunity, duplicate campaign, duplicate territory, duplicate task, or conversion writer;
- [ ] all four models tenant-scoped and all cross-app FKs same-tenant validated;
- [ ] score/rating removed from ordinary CRM Lead editing and changed only through append-event services;
- [ ] transparent fixed 0–100 bands and no claim of predictive AI;
- [ ] route conditions use a closed allowlist and deterministic priority;
- [ ] round robin is lock-safe and has a dry-run;
- [ ] qualification requires selected-framework evidence and a reason when disqualified;
- [ ] nurture activation requires a CRM drip campaign and consent-purpose/evidence reference but sends nothing;
- [ ] CRM conversion remains the only Party/Contact/Opportunity writer, preferably via a shared CRM service;
- [ ] actual delivery, API ingestion, web tracking, load balancing, MQL/SQL analytics, and AI scoring are visibly deferred;
- [ ] CRUD posture and context/filter contracts are pinned for the three mutable models and the append-only score-event exception.

## 11. Bottom line

NavERP should implement 8.1 as **four thin operational records over CRM's already-built lead/campaign/territory spine**. The highest-value, lowest-duplication slice is an append-only score ledger, a current BANT/MEDDIC assessment, a deterministic routing-rule service, and a CRM-drip enrollment. The most important ownership decision is that **CRM remains the sole lead and conversion writer; Sales never creates a second lead or opportunity path**.
