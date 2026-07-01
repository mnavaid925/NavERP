# Research — Module 3: HRM, Sub-module 3.8 Offer Management (hrm-offer-management)

Scope: the OFFER stage of the recruiting lifecycle only — after 3.7 Interview Process, before 3.3 Employee
Onboarding. Builds on the existing 3.6 spine (`CandidateProfile`, `JobApplication`, `CandidateEmailTemplate`,
`CandidateCommunication`, `_send_candidate_email`), the 3.5 `JobRequisition` (with salary band fields), and hands
off to the existing 3.3 `OnboardingProgram`/`OnboardingTask`/`OnboardingDocument`. None of those are re-proposed.

## Leaders surveyed (with source links)

1. **Greenhouse (Recruiting)** — offer-document templates with placeholder tokens + Adobe Acrobat Sign / Dropbox
   Sign e-signature integration, configurable approval-request email content —
   [Generate and send offer document](https://support.greenhouse.io/hc/en-us/articles/200485589-Generate-and-send-offer-document),
   [Offer approvals](https://support.greenhouse.io/hc/en-us/sections/360000932811-Offer-approvals),
   [Send offers for e-Signature with Adobe Acrobat Sign](https://support.greenhouse.io/hc/en-us/articles/22869500774043-Send-offers-for-e-Signature-with-Adobe-Acrobat-Sign),
   [October 2025 Release Notes](https://support.greenhouse.io/hc/en-us/articles/42675175392283-Release-Notes-October-2025)
2. **Lever (LeverTRM)** — Dynamic Offer Approvals: sequential + parallel + conditional (comp-threshold-based)
   routing; offer-form placeholder tokens; DocuSign/HelloSign e-sign with status visible in-app —
   [Creating offers](https://help.lever.co/hc/en-us/articles/20087310413213-Creating-offers),
   [Offer generation and approvals](https://help.lever.co/hc/en-us/sections/201311225-Offer-generation-and-approvals),
   [How to Streamline Your Job Offer Approval Process](https://www.lever.co/blog/job-offer-approval-process/)
3. **Workday Recruiting** — offer letters generated from dynamic templates against the full HCM data model;
   multi-step approvals configurable by salary band / equity grant / sign-on bonus; offer feeds directly into
   onboarding tasks — [Workday-HCM: Job Requisition and Offer Letter Approval](https://su-support.atlassian.net/wiki/spaces/TSC/pages/107380800/Workday-HCM:+Job+Requisition+and+Offer+Letter+Approval),
   [A Detailed Guide to Workday Recruiting](https://www.erpcloudtraining.com/blog/workday-recruiting)
4. **iCIMS** — background-screening partner marketplace embedded in the ATS (order + view checks without leaving
   iCIMS), pre-populated candidate data flows into the screening request, live status updates surfaced back on
   the candidate record; native Onboarding module auto-collects W-4/I-9/direct-deposit/confidentiality forms pre
   start-date — [iCIMS Prime Background Screen + Cisive](https://blog.cisive.com/icims-prime-background-screen-cisive-your-icims-integration-experience-just-got-smoother),
   [iCIMS API Integration | First Advantage](https://www.sterlingcheck.com/integrations/icims/),
   [Onboarding Software Comparison for iCIMS Customers](https://integralrecruiting.com/onboarding-software-for-icims/)
5. **SAP SuccessFactors Recruiting** — "Offer Detail" data model separates the internal comp-approval object from
   the candidate-facing Offer Letter; the same Offer Detail record drives which approval chain applies (simple vs.
   complex based on comp/level) and populates the letter's merge tokens only after approval —
   [Job Offers in SAP SuccessFactors](https://help.sap.com/docs/successfactors-recruiting/setting-up-and-maintaining-sap-successfactors-recruiting/job-offers-in-sap-successfactors),
   [Prepare Offer Details and Trigger Offer Approval](https://help.sap.com/docs/successfactors-recruiting/recruiting-in-sap-successfactors-test-script/prepare-offer-details-and-trigger-offer-approval)
6. **Oracle Taleo / Recruiting Cloud** — Submit-Offer-for-Approval action with an explicit approver list +
   sequence number per approver, sequential-or-parallel path selection; offer letters built from Message
   Templates; supports email / printed-letter / "E-Offer" extension methods —
   [Offer Management](https://docs.oracle.com/cloud/18a/taleo/OTREC/_offer_user_fmx.htm),
   [Requisition and Offer Approvals](https://docs.oracle.com/cloud/18a/taleo/OTRCG/_approval_admin_fmx.htm),
   [E-Offer Process](https://docs.oracle.com/cloud/18a/taleo/OTTCG/_electronicoffers_cg.htm)
7. **Ashby** — multi-level offer approvals with conditional filtering by field (comp, level, department);
   template-usage rules restrict which offer-letter template a recruiter can even pick for a given candidate;
   tracks e-sign status for the offer + companion docs (NDA etc.) directly in-app —
   [Streamline Offer Letter generation with Template controls](https://www.ashbyhq.com/product-updates/offer-letter-template-controls),
   [Structured and Adaptable ATS](https://www.ashbyhq.com/platform/recruiting/ats)
8. **BambooHR** — offer letter templates with attachable authorization forms (background-check consent, drug
   screening); Zoho Sign / native e-signature; Checkr partnership for one-click background screening request
   export — [Product Update: Introducing Offer Letters](https://www.bamboohr.com/blog/introducing-offer-letters),
   [Documents and E-Signatures](https://help.bamboohr.com/s/topic/0TO4z000000SnFsGAK/documents-and-esignatures)
9. **Zoho Recruit** — free-form offer-letter generator tool with merge fields; Checkr integration exports
   candidate details with one click, candidate approves the check request, status flows back into Recruit;
   BambooHR hand-off connector for recruiting → HR data mapping post-hire —
   [Free Offer Letter Generator Tool](https://www.zoho.com/recruit/free-offer-letter.html),
   [Background screening with Checkr](https://www.zoho.com/recruit/checkr-integration.html)
10. **Checkr / HireRight / Sterling (background-verification vendors)** — standardized check lifecycle
    (Started/Draft → In Progress → Action Needed → Ready for Review → Completed, with an order-level result of
    Clear / Consider), typed verification categories (employment, education, professional license, criminal,
    identity), webhook/API status push back to the ATS, and a formal pre-adverse/adverse-action dispute flow when
    a "Consider" result surfaces — [Background Check API and Integrations | Checkr](https://checkr.com/our-technology/background-check-api),
    [Checkr vs HireRight vs iprospectcheck](https://iprospectcheck.com/checkr-vs-hireright-vs-iprospectcheck/),
    [My Background Check - Sterling](https://mybackgroundcheck.sterlingcheck.com/)

Plus supporting research on offer-tracking analytics conventions (acceptance-rate benchmarking, decline-reason
coding) — [Offer Acceptance Rate Explained](https://www.manatal.com/blog/offer-acceptance-rate),
[Offer Acceptance Rates | Ashby Talent Trends](https://www.ashbyhq.com/talent-trends-report/reports/2023-trends-report-offer-acceptance-rates) —
and offer compensation-component conventions (base/bonus/equity/sign-on/relocation, clawback terms) —
[Creating a Compensation Job Offer Letter](https://www.compup.io/blogs/compensation-offer-letter-template-guide),
[Free job offer letter templates | HiBob](https://www.hibob.com/hr-tools/job-offer-letter-template/) — and
pre-boarding document-collection conventions — [What is preboarding? | HiBob](https://www.hibob.com/hr-glossary/preboarding/),
[21+ essential onboarding documents](https://www.hibob.com/hr-tools/onboarding-documents/).

## Feature catalog by sub-module

### 3.8 Offer Management

#### Offer Letter Generation
- **Offer letter templates with merge/placeholder tokens** — recruiter selects a template; candidate name, job
  title, comp fields, start date, etc. auto-populate · seen in: Greenhouse, Lever, Workday, Oracle Taleo, Zoho
  Recruit, BambooHR · priority: P0 · spine: reuse pattern of `CandidateEmailTemplate` (`body_html` with
  `{{merge_fields}}`) — new `OfferLetterTemplate` model (letter body is longer-form/printable than an email, so a
  distinct template type rather than overloading `CandidateEmailTemplate`) · buildable now
- **Template-usage rules / scoping** — only templates applicable to the candidate's level/department/req are shown
  · seen in: Ashby · priority: P2 · spine: could be a simple FK/choice filter (e.g. template scoped to
  `employment_type` or `job_grade`) on `OfferLetterTemplate` · buildable now (simple filter), full rule-engine
  deferred
- **Variable compensation breakdown on the offer** — base salary, currency, bonus/incentive terms, equity/stock
  grant, sign-on bonus, relocation allowance, each with its own amount/terms text · seen in: Workday (comp bands),
  SAP SuccessFactors (Offer Detail data model), general offer-letter conventions (CompUp, HiBob, Cooley GO) ·
  priority: P0 · spine: new fields/line rows on the `Offer` model (or a small `OfferCompensationComponent` child
  table) — reuses `JobRequisition.salary_currency`/`salary_min`/`salary_max` as the budget guardrail context ·
  buildable now
- **Printable/PDF offer letter generation from template + merge data** — same "printable letter" pattern as HRM's
  existing `relieving_letter.html` · seen in: Greenhouse, Oracle Taleo (letter via Message Templates) · priority:
  P0 · spine: reuse the existing HRM printable-letter template convention (server-rendered HTML → print/PDF) ·
  buildable now
- **E-signature integration (DocuSign / Adobe Sign / Dropbox Sign / Zoho Sign)** — candidate signs the offer
  online, signed doc auto-attaches to the record · seen in: Greenhouse, Lever, Ashby, BambooHR, Zoho Recruit ·
  priority: P1 (near-universal among leaders, but is a 3rd-party integration) · spine: model a `signed_document`
  file field + `signature_status` choice now; live e-sign vendor wiring is integration/later
- **Companion-document bundling** — NDA, background-check consent form, drug-screening authorization attached
  alongside the offer letter · seen in: BambooHR, Ashby · priority: P2 · spine: could reuse `PreboardingItem`
  (document-collection) once pre-boarding exists, or an `OfferAttachment`-style file field · integration/later for
  the bundled-send workflow, buildable now as plain file attachments
- **Offer revision / re-issue** — recruiter edits comp terms and re-sends after candidate negotiation · seen in:
  Lever, Oracle Taleo ("edit offer letter after approval") · priority: P1 · spine: new table not needed — a
  `revised_at`/version counter + re-approval trigger on `Offer` covers it; buildable now

#### Offer Approval
- **Multi-level / multi-step approval chain** — sequential steps each held by a role or specific person · seen
  in: Lever, Workday, Oracle Taleo, SAP SuccessFactors, Ashby · priority: P0 · spine: mirrors the existing
  `RequisitionApproval` child-table pattern exactly — new `OfferApproval` table, same shape (`step_order`,
  `approver`, `status`, `decided_at`, `decided_by`, `comments`) · buildable now
- **Parallel approval routing** (all approvers notified at once, no waiting) · seen in: Lever, Oracle Taleo ·
  priority: P2 · spine: `RequisitionApproval`-style chain is sequential-by-`step_order`; true parallel routing
  (same `step_order` for N approvers, all-must-approve) is a larger state-machine change · integration/later —
  document as a deferred variant, ship sequential only this pass
- **Conditional / threshold-based routing** — offers above a comp threshold auto-route to an extra (e.g. VP/CFO)
  approval step · seen in: Lever, Ashby · priority: P1 · spine: no new table — a view-layer rule when creating the
  `OfferApproval` chain (e.g. append a step if `total_compensation > threshold`); can be a simple constant/setting
  this pass, a configurable rule engine later · buildable now (simple threshold), full rule engine deferred
  (config UI, per-department thresholds)
- **Approver picked from requisition's hiring team / configurable approver roles** (HR, Finance, Hiring Manager,
  Department Head) · seen in: Lever, SAP SuccessFactors, Oracle Taleo · priority: P0 · spine: reuse the
  `APPROVER_ROLE_CHOICES` pattern already defined for `RequisitionApproval` — same choice set, same
  `EmployeeProfile`/`User` FK conventions · buildable now
- **Configurable approval-request email content** (choose which offer fields appear in the notification) · seen
  in: Greenhouse (Oct 2025 release) · priority: P2 · spine: reuse `CandidateEmailTemplate`/`_send_candidate_email`
  for the notification itself; a per-tenant field-picker UI is deferred · integration/later for the picker,
  buildable now as a fixed notification body
- **Approval blocks offer extension until fully approved** — offer cannot be sent to the candidate while any step
  is pending/rejected · seen in: all surveyed (Greenhouse, Lever, Workday, SAP SuccessFactors, Oracle Taleo) ·
  priority: P0 · spine: workflow-owned `status` guard on `Offer` (mirrors `JobRequisition.status` gating posting)
  · buildable now

#### Offer Tracking
- **Offer status lifecycle** (draft → pending approval → approved → extended/sent → accepted / declined /
  rescinded / expired) · seen in: every surveyed ATS in some form (Greenhouse pipeline stage, Lever, Workday,
  JazzHR disposition, Oracle Taleo) · priority: P0 · spine: workflow-owned `status` field on `Offer`, mirrors
  `JobRequisition.status` / `JobApplication.stage` conventions (`editable=False`, set only by POST actions) ·
  buildable now
- **Expected response / expiry date** with overdue flag · seen in: general ATS convention (offer validity
  window), mirrors `JobRequisition.is_overdue` pattern · priority: P1 · spine: `expires_on` DateField +
  `is_overdue` property on `Offer`, same pattern as `JobRequisition.is_overdue` · buildable now
- **Decline/rescind reason codes** — salary, competing offer, counteroffer, role/culture fit, timing, other ·
  seen in: recruiting-metrics convention (Manatal, AIHR, Ashby Talent Trends), mirrors existing
  `REJECTION_REASON_CHOICES` on `JobApplication` · priority: P1 · spine: new `OFFER_DECLINE_REASON_CHOICES` field
  on `Offer`, same shape as `JobApplication.rejection_reason`/`rejection_notes` · buildable now
- **Offer acceptance triggers `JobApplication.stage` → hired + `hired_on` stamp**, and feeds onboarding · seen in:
  Workday (offer → onboarding tasks), iCIMS (screening → onboarding hand-off) · priority: P0 · spine: reuse
  existing `JobApplication.stage`/`hired_on` fields — the offer-accept POST action stamps them exactly like the
  interview/stage-advance actions already do; no new field needed · buildable now
- **Offer acceptance-rate / decline-reason analytics dashboard** segmented by department/recruiter/level · seen
  in: Ashby Talent Trends Report, general recruiting-metrics tooling · priority: P2 · spine: computed from
  existing `Offer.status`/`decline_reason` aggregates — no new table, a reporting view · integration/later (this
  pass ships the underlying fields; dashboard/report page is a later analytics pass)
- **Communication log entries for offer sent / reminder / accepted / declined** · seen in: every ATS (as part of
  the candidate timeline) · priority: P0 · spine: reuse `CandidateCommunication` + `_send_candidate_email` exactly
  as 3.7 Interview Process reused it for invites/reminders — no new communication model · buildable now

#### Background Verification
- **Vendor-integrated background check ordering from within the ATS** (order + view without leaving the
  platform) · seen in: iCIMS (Cisive/Verified Credentials/Pre-Employ partners), Zoho Recruit (Checkr), BambooHR
  (Checkr) · priority: P0 (as a data-model concern — vendor field + status, not live order automation) · spine:
  new `BackgroundVerification` table FK'd to `JobApplication` (or `Offer`) with a `vendor` field; live vendor API
  call is integration/later
- **Typed verification categories** — criminal, employment history, education, professional license/certification,
  identity, credit (role-dependent) · seen in: Checkr (employment/education/license verification types), HireRight
  · priority: P1 · spine: `check_type` choice field on `BackgroundVerification` (or a child line per type if
  multiple checks run in parallel — see model recommendation below) · buildable now
- **Standardized status lifecycle** — requested/initiated → in progress → action needed (candidate must supply
  more info) → ready for review → completed, with an overall result of Clear / Consider · seen in: Checkr,
  Sterling, HireRight · priority: P0 · spine: `status` + separate `result` choice fields on `BackgroundVerification`
  · buildable now
- **Pre-populated candidate data flows into the check request** (name/DOB/SSN/address reused from the candidate
  profile, not re-keyed) · seen in: iCIMS · priority: P1 · spine: reuse `CandidateProfile` contact fields when
  constructing the request (view-layer convenience, not a schema change) · buildable now
- **Webhook/API status push-back updates the ATS record automatically** · seen in: Checkr, HireRight (API-first) ·
  priority: P1 · spine: would update `BackgroundVerification.status`/`result` via webhook receiver — integration/
  later; this pass ships the fields the webhook would write to, with manual status update in the interim
- **Consent capture before initiating a check** (candidate authorization, often via e-sign) · seen in: BambooHR
  (attachable authorization form), Checkr (candidate must approve request) · priority: P1 · spine:
  `consent_given`/`consent_date` boolean+date fields on `BackgroundVerification`, or reuse the same
  `signed_document` pattern as the offer letter · buildable now
- **Formal adverse-action / dispute workflow** when a check comes back "Consider" (pre-adverse notice → candidate
  response window → final adverse notice) · seen in: Sterling, Checkr, HireRight (compliance-heavy) · priority:
  P2 (legally significant but a distinct compliance sub-flow) · spine: would need `dispute_status` +
  notice-date fields · integration/later — flag as a compliance gap to revisit, not blocking for this pass
- **Report/document attachment** (the vendor's PDF report attached to the record) · seen in: all three vendors ·
  priority: P1 · spine: `report_file` FileField on `BackgroundVerification` (manually uploaded this pass in lieu
  of live API delivery) · buildable now

#### Pre-boarding
- **Document collection before joining** (I-9/W-4-equivalent identity & tax forms, direct deposit / bank details,
  confidentiality/NDA agreement, ID proof, address proof) · seen in: iCIMS (native Onboarding), HiBob (preboarding
  document/paperwork submission) · priority: P0 · spine: new `PreboardingItem` table FK'd to `Offer` (or directly
  to `JobApplication`) — deliberately distinct from the existing 3.3 `OnboardingDocument` (that model runs
  post-hire/post-start inside `OnboardingProgram`; pre-boarding is pre-start-date, tied to the offer, and largely
  candidate-self-service) · buildable now
- **Scheduled/timed invitation to the candidate to complete pre-boarding** (e.g. "send N days before start date")
  · seen in: HiBob (schedule invite to personal email before day one) · priority: P1 · spine: reuse
  `_send_candidate_email`/`CandidateCommunication` for the invite send — no new email infra; a `send_at`/reminder
  action on `PreboardingItem` (manual-trigger this pass, scheduled dispatch deferred, mirrors 3.7's
  `reminder_sent_at` manual-action convention) · buildable now (manual action), Celery-style auto-scheduling
  integration/later
- **Checklist/completion tracking per item** (pending / submitted / verified / rejected) with an owner (candidate
  self-service vs. HR-collected) · seen in: iCIMS, HiBob · priority: P0 · spine: `status` choice field on
  `PreboardingItem`, mirrors the `OnboardingTask`/`ClearanceItem` status-child pattern already used elsewhere in
  HRM · buildable now
- **Hand-off into full onboarding once hired/joined** — pre-boarding items collected pre-start feed or gate the
  post-start `OnboardingProgram` · seen in: iCIMS, Workday (offer → onboarding tasks) · priority: P0 · spine: no
  new table — this is a process link (offer acceptance can pre-populate/trigger the existing `OnboardingProgram`
  creation on the join date; exact trigger wiring is a `todo`/build-time decision, not a new model) · buildable now
- **Welcome kit / policy acknowledgment sent alongside pre-boarding** · seen in: HiBob, general convention (also
  explicitly named in NavERP 3.3 "Welcome Kit") · priority: P2 · spine: already the job of the existing 3.3
  onboarding welcome-kit feature — do not duplicate; pre-boarding here stays scoped to document collection only ·
  deferred to 3.3 (already scoped there)

## Recommended build scope (this pass — 4 models)

- **`Offer`** [OFR-] — the offer-management hub, one row per `JobApplication` (FK, one-to-one-ish but modeled as
  FK with a uniqueness guard so a re-issued offer can supersede rather than multiply — mirrors how `Interview` FKs
  `JobApplication` without a hard 1:1). Fields justified by research: `offer_letter_template` FK (Offer Letter
  Generation — Greenhouse/Lever/Workday/Oracle Taleo template-token pattern), compensation breakdown —
  `base_salary`, `currency` (default from `JobRequisition.salary_currency`), `bonus_amount`/`bonus_terms`,
  `signing_bonus`, `equity_terms` (text — grant description/vesting, since equity plans aren't modeled yet),
  `relocation_assistance` (Workday/SAP SuccessFactors Offer Detail + general offer-letter comp-component
  convention), `benefits_summary` (text), `start_date`, `expires_on` + `is_overdue` property (mirrors
  `JobRequisition.is_overdue`), workflow-owned `status` (`draft`/`pending_approval`/`approved`/`extended`/
  `accepted`/`declined`/`rescinded`/`expired`, `editable=False`, set only by POST actions — mirrors
  `JobRequisition.status`/`JobApplication.stage` convention) (Offer Tracking — universal lifecycle pattern),
  `decline_reason` choice + `decline_notes` (mirrors `JobApplication.rejection_reason`/`rejection_notes`) (Offer
  Tracking — decline-reason-code convention), `signed_document` FileField + `signature_status` choice (E-signature
  integration — Greenhouse/Lever/Ashby/BambooHR/Zoho, modeled as a field now, live e-sign vendor wiring deferred),
  `extended_by`/`extended_at`, `accepted_at`/`declined_at`/`rescinded_at` stamps, `created_by`. Reuses
  `hrm.JobApplication` (candidate + requisition reached through it), `hrm.EmployeeProfile` for hiring-team FKs,
  and drives `JobApplication.stage`→`hired`/`hired_on` on acceptance exactly like 3.7's interview actions drive
  `stage` today.

- **`OfferApproval`** [none — child table, `TenantOwned` like `RequisitionApproval`/`InterviewPanelist`] — one
  sequential approval step on an `Offer`. Fields directly mirror `RequisitionApproval` (Offer Approval —
  Lever/Workday/SAP SuccessFactors/Oracle Taleo/Ashby all confirm this exact "one row per step" shape is the
  market norm): `offer` FK, `step_order`, `approver` (User FK), `approver_role` (reuse
  `APPROVER_ROLE_CHOICES`), workflow-owned `status` (`pending`/`approved`/`rejected`/`returned`, `editable=False`),
  `decided_at`/`decided_by`, `comments`. `unique_together = ("offer", "step_order")`. The `Offer.status` gate
  (can't extend until all steps approved) directly implements the "approval blocks extension" P0 finding shared
  across every surveyed product. Conditional/threshold-based extra-step insertion (Lever/Ashby P1 finding) is a
  view-layer rule at chain-creation time — no schema impact.

- **`BackgroundVerification`** [BGV-] — one background check on an `Offer` (or on the underlying
  `JobApplication` — proposing `Offer` FK since checks are ordered post-offer-extension in every surveyed
  workflow). Fields justified by research: `vendor` choice/free-text (Checkr/HireRight/Sterling/iCIMS-partner
  convention — vendor-integration marketplace pattern, modeled as a field since live API wiring is
  integration/later), `check_type` (`criminal`/`employment`/`education`/`professional_license`/`identity`/`credit`
  — Checkr's typed-verification-category finding), workflow-owned `status`
  (`not_started`/`consent_pending`/`initiated`/`in_progress`/`action_needed`/`ready_for_review`/`completed`,
  editable=False) and separate `result` (`clear`/`consider`/`not_applicable`) — mirrors the Checkr/Sterling
  standardized lifecycle finding, `consent_given`/`consent_date` (consent-capture P1 finding), `report_file`
  FileField (vendor-report-attachment P1 finding), `initiated_at`/`completed_at`, `initiated_by`, `notes`. Reuses
  `hrm.Offer`→`hrm.JobApplication`→`hrm.CandidateProfile` chain for candidate identity data rather than
  re-storing PII (iCIMS "pre-populated candidate data" finding — pull from `CandidateProfile`, don't duplicate).
  Adverse-action/dispute sub-flow explicitly deferred (see below).

- **`PreboardingItem`** [none — child table, `TenantOwned` like `OnboardingTask`/`ClearanceItem`] — a
  document-collection checklist line tied to an accepted `Offer`, run *before* the join/start date and
  deliberately separate from the post-start 3.3 `OnboardingDocument`/`OnboardingTask` (which continue to own
  everything from day one onward). Fields justified by research: `offer` FK, `document_type`
  (`id_proof`/`address_proof`/`tax_form`/`bank_details`/`nda`/`education_certificate`/`background_check_consent`/
  `other` — HiBob/iCIMS document-collection convention), `is_required`, workflow-owned `status`
  (`pending`/`submitted`/`verified`/`rejected`, editable=False — mirrors `OnboardingTask`/`ClearanceItem`
  status-child convention already in HRM), `uploaded_file` FileField, `submitted_at`, `verified_by`/`verified_at`,
  `reminder_sent_at` (manual-action stamp — mirrors `Interview.reminder_sent_at`; reuses
  `_send_candidate_email`/`CandidateCommunication` for the invite/reminder send, no new email model), `notes`.
  On full completion (all `is_required` items `verified`), the existing `OnboardingProgram` creation (3.3) can be
  triggered/pre-populated at build time — no new model needed for that hand-off.

`OfferLetterTemplate` was considered as a 5th model (mirrors `CandidateEmailTemplate` but for the
longer-form/printable letter body) — folded into scope as **optional/5th-if-time** rather than a hard requirement,
since the letter body could ship as a simple `body_html` TextField directly on `Offer` for a first pass; the
`todo` agent should decide based on how much templating flexibility the build calendar allows. If included:
`OfferLetterTemplate` [OLTMPL-] — `name`, `is_active`, `body_html` (merge fields:
`{{candidate_name}}, {{job_title}}, {{base_salary}}, {{start_date}}, {{company_name}}, {{hiring_manager_name}}`),
mirrors `CandidateEmailTemplate`'s shape exactly.

## Deferred (later passes / integrations)

- **Live e-signature vendor wiring** (DocuSign / Adobe Acrobat Sign / Dropbox Sign / Zoho Sign API integration) —
  `Offer.signed_document`/`signature_status` fields ship now; the actual "send for e-sign, receive webhook,
  auto-attach" flow is a 3rd-party integration, matches how 3.7 deferred live Zoom/Teams auto-link.
- **Live background-check vendor API wiring** (Checkr/HireRight/Sterling order-and-webhook automation) —
  `BackgroundVerification` ships as a manually-updated status/result record this pass; automatic ordering and
  webhook status push-back is integration/later.
- **Formal adverse-action / dispute compliance workflow** (pre-adverse notice → response window → final adverse
  notice) for "Consider" results — legally significant but a distinct compliance sub-flow; not blocking for this
  pass's 4-model scope.
- **Parallel (all-at-once) approval routing** — this pass ships sequential `step_order` chains only (matching the
  already-shipped `RequisitionApproval` pattern); true parallel/any-N-of-M routing is a state-machine expansion.
- **Configurable conditional-routing rule engine** (per-department/per-level comp thresholds editable by admins) —
  ships as a simple hardcoded/settings-level threshold check this pass if implemented at all; a full rule-builder
  UI is deferred.
- **Configurable approval-notification field picker** (Greenhouse's Oct-2025 "choose which fields show in the
  approval email") — notifications reuse `_send_candidate_email`/a fixed internal-approver notification body this
  pass.
- **Companion-document bundling** (NDA / drug-screening authorization sent alongside the offer letter as one
  package) — ships as plain file attachments if needed; a bundled multi-doc send workflow is deferred.
- **Offer acceptance-rate / decline-reason analytics dashboard** — the underlying fields (`status`,
  `decline_reason`) ship this pass; a dedicated reporting/dashboard page is a later analytics pass (would fit
  under 3.32 Analytics Dashboard).
- **Welcome kit / policy acknowledgment** — already owned by the existing 3.3 Onboarding feature set; not
  duplicated under pre-boarding.
- **Template-usage scoping rules** (Ashby-style "only show templates valid for this candidate's level") — if
  `OfferLetterTemplate` ships, a simple FK/choice filter can be added later; a full rule engine is deferred.
- **Scheduled/automated pre-boarding invite dispatch** (Celery-style "send N days before start date") — this pass
  ships a manual, audited send action (mirrors 3.7's `reminder_sent_at` manual-action convention); automated
  scheduled dispatch is deferred, consistent with 3.7's own Celery-dispatch deferral.
