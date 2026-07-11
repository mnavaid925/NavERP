# Research — Module 3: HRM — Sub-module 3.26 Request Management (Self-Service) (hrm)

**Scope grounding:** NavERP.md 3.26 bullets — Leave Requests, Attendance Regularization, Document Requests
(experience letter, salary certificate), ID Card Request (new/replacement), Asset Requests (laptop, equipment).
Leave (`LeaveRequest`, 3.10, prefix `LR`) and Attendance Regularization (`AttendanceRegularization`, 3.9, prefix
`REG`) **already exist** with full `draft → pending → approved/rejected/cancelled` maker-checker workflows — this
pass only links to them from a hub. The three **new** entities are **Document Requests**, **ID Card Requests**, and
**Asset Requests**. Existing spine to reuse: `hrm.EmployeeProfile` (anchor for every HRM row, itself 1:1 on
`core.Party`/`core.Employment`), `hrm.EmployeeDocument` (`EDOC` — the personnel-file vault where HR-verified ID/
passport/contract documents already live, distinct purpose from an employee *requesting* a generated letter), and
`hrm.AssetAllocation` (`AST` — the physical-issuance ledger, already has an `id_card` category, already the
fulfillment record used by onboarding/offboarding). The `TenantNumbered` base (`number`, `tenant`, `created_at`,
`updated_at`) and the `draft → pending → approved/rejected/cancelled` state machine (seen identically in
`LeaveRequest`, `AttendanceRegularization`, `LeaveEncashment`, `Timesheet`) is the established NavERP convention
these three new models must mirror, extended with a **fulfillment** tail state per entity (mirrors
`LeaveEncashment`'s `approved → paid` tail).

## Leaders surveyed (with source links)

1. **Workday** — HCM suite leader; "Workday Help" bundles Knowledge Management + native case-management ticketing
   inside the HCM, with business-process case creation, email ingestion and message templates —
   [Knowledge & Case Management](https://www.workday.com/en-us/products/human-capital-management/knowledge-case-management.html)
2. **SAP SuccessFactors (Employee Central Service Center)** — configurable case categories, assignment rules,
   escalation workflows and SLA tracking for HR queries, tickets routed to a Team or User —
   [Employee Central Service Center features](https://www.sap.com/denmark/products/hcm/employee-central-service-center/features.html)
3. **BambooHR** — broad-market SMB HRIS; Custom Access Levels gate which fields an employee can self-edit vs. must
   route for approval; strong "Employee Wellbeing" self-service layer —
   [Employee Self-Service glossary](https://www.bamboohr.com/resources/hr-glossary/employee-self-service)
4. **Zoho People** — native "HR Help Desk" case management: categories/sub-categories, per-category SLA +
   escalation actions, agent/department/group routing, FAQ knowledge base per category, case-progress updates —
   [HR Case Management](https://www.zoho.com/people/hr-case-management.html)
5. **Keka HR** — Employee Self-Service Document Generation (generate routine HR letters from the profile without
   a ticket), centralized document repository (offer letters, ID proofs, contracts, certificates), and an asset
   panel where an employee clicks "Request Replacement" on an assigned asset, fills requirements, and uploads
   supporting images — [Employee Helpdesk](https://www.keka.com/us/helpdesk), [Document Management](https://www.keka.com/employee-document-management)
6. **Darwinbox** — "Employee Documents" product: pre-built + customizable letter templates, self-generate and
   submit documents centrally, bulk generate/publish/download; "Employee Helpdesk" with multi-tier escalation +
   SLAs, Gen-AI assistant resolving common queries —
   [Employee Helpdesk](https://darwinbox.com/en-us/products/employee-helpdesk), [Employee Documents](https://darwinbox.com/en-us/products/employee-documents)
7. **greytHR** — **Request Hub** is the closest direct analog to 3.26: a structured **ID Card Replacement
   Request** workflow (reason for request, previous card details, optional attachment, 1–5 configurable approval
   levels, approve & forward / reject, auto-forward on inactivity, escalation, reopen, auto-close, then reviewer
   "issues the card"); separate mobile Helpdesk ticket categories (HR, Payslips, Loans, IT, Employment Information) —
   [ID card replacement workflow](https://admin-help.greythr.com/admin/answers/wqvocii-tsixu3kfxakfxq/), [Helpdesk ticket](https://support.greythr.com/hc/en-us/articles/4413774803469-How-can-employee-create-a-helpdesk-ticket-)
8. **ServiceNow HR Service Delivery** — enterprise case-management benchmark: Centers of Excellence (COE)
   categorize cases (Payroll, Benefits, Employee Relations…); **HR Document Templates** dynamically merge
   employee-profile fields into a letter; three document patterns — auto-send-no-review (e.g. NDA
   acknowledgement), multi-signature (e.g. offer letter), and **agent-reviewed-then-signed-and-sent** (the
   employment-verification-letter pattern, i.e. a subject requests it, an HR agent reviews for accuracy,
   e-signs, and sends to the requested recipient); "Fulfillment Instructions" give agents step-by-step resolution
   guidance per case type —
   [HR document generation](https://www.servicenow.com/docs/r/employee-service-management/hr-service-delivery/DocumentGeneration.html)
9. **Oracle HCM Cloud — HR Help Desk** — unified service-request/case solution; a **document of record** can be
   generated as a PDF the employee downloads for their own records, with a copy auto-attached to the ticket for
   the agent's reference; requests can be submitted via chat, email, or self-service portal —
   [HR Help Desk](https://www.oracle.com/human-capital-management/hr-help-desk/)
10. **Rippling (IT / Inventory Management)** — the leading asset/equipment-request analog outside pure-HRIS:
    employees pick a device from a **catalog** or a role-based **saved configuration**, IT approval policies gate
    "assign/order device" and "unassign/retrieve device" actions, devices ship pre-configured, and lifecycle
    (assign → in-use → replace → retrieve → reassign) is tracked end-to-end —
    [IT Inventory Management](https://www.rippling.com/inventory-management), [Device Lifecycle Management](https://www.rippling.com/solutions/it/device-lifecycle-management)
11. *(bonus, referenced for the service-catalog pattern)* **Freshservice / Freshteam** — a shared **Service
    Catalog** lists HR request types (letter of employment, proof of address, record updates…) each spawning a
    ticket with fulfillment routed to the owning team; onboarding "kits" bundle role-based hardware/software
    requests as child tickets —
    [Service catalog / onboarding](https://support.freshservice.com/support/solutions/articles/50000002364-building-onboarding-kits)

## Feature catalog by sub-module

### 3.26 Request Management (Self-Service) — Hub
- **Unified request inbox/hub** — one place listing all of an employee's requests across types (leave, attendance,
  document, ID card, asset) with status and a "raise new request" launcher · seen in: Workday Help, greytHR Request
  Hub, Freshservice Service Catalog, Zoho People Help Desk · priority: table-stakes · spine: **view-only
  aggregation** over `LeaveRequest` + `AttendanceRegularization` + the 3 new models (no new table) · buildable now
- **Request categories/sub-categories with routed ownership** — category determines who resolves it (HR generalist
  vs IT vs Payroll) · seen in: Zoho People, ServiceNow (COE), SAP SF · priority: common · spine: **implicit** —
  each new model IS its category (DocumentRequest/IdCardRequest/AssetRequest each own resolution), no separate
  `RequestCategory` table needed at this scale · buildable now
- **SLA / turnaround-time tracking per category with escalation** — target resolution date, breach alerts, auto-
  escalation to next approver · seen in: Zoho People, SAP SF, ServiceNow, general HR-service-delivery SLA tooling ·
  priority: differentiator · spine: new field (`needed_by`/target date) on each model; auto-escalation engine is
  **integration/later** (needs a scheduler) — buildable now: capture the target date field only
- **FAQ / knowledge base linkage per request type** — self-serve answers before raising a ticket · seen in: Zoho
  People, Workday Help · priority: nice-to-have · **out-of-scope this pass** (belongs with 3.27 Communication
  Hub / Help Desk, not 3.26)
- **CC / watcher on a request** — notify a second person (e.g. manager) of progress · seen in: greytHR Request Hub
  · priority: nice-to-have · integration/later (needs notification/email infra)
- **Configurable multi-level approval chain (1–5 levels)** — greytHR lets admins define how many approval stages a
  request type needs · priority: differentiator · **out-of-scope this pass** — NavERP's existing pattern (single
  `approver` + `approved_at`) is deliberately kept consistent with `LeaveRequest`/`AttendanceRegularization`;
  multi-level chains are a cross-cutting workflow-engine feature better done once, module-wide, later

### 3.26 Document Requests
- **Typed document catalog** — experience/relieving letter, salary certificate, employment verification letter,
  NOC (no-objection certificate), address proof · seen in: NavERP.md 3.26 itself, Darwinbox Employee Documents,
  Keka self-service document generation, ServiceNow document-template patterns, Freshservice service catalog
  ("letter of employment", "proof of address") · priority: table-stakes · spine: new field `document_type` (choices)
  on new table `DocumentRequest` · buildable now
- **Purpose / reason for request** — why the document is needed (visa, bank loan, higher education, address
  registration…), often required so HR can tailor wording · seen in: Docusign/AIHR verification-letter templates,
  general HRIS practice · priority: table-stakes · spine: new field `reason`/`purpose` (text) · buildable now
- **Addressed-to / recipient** — letters are frequently addressed "To Whom It May Concern" or to a named bank/
  embassy/institution · seen in: employment-verification-letter template conventions (Docusign, HR University),
  ServiceNow's "send to subject or third party" pattern · priority: common · spine: new field `addressed_to`
  (free text) · buildable now
- **HR review-then-generate-then-deliver workflow** — a subject requests → an HR agent reviews for accuracy →
  generates/signs → sends; distinct from a no-review auto-send · seen in: ServiceNow (explicit 3-pattern document
  workflow), Oracle HCM (agent-attached PDF), Keka (self-service *generation* without a ticket, for routine ones)
  · priority: table-stakes · spine: workflow states on `DocumentRequest`
  (`draft → pending → approved → generated → delivered` + `rejected`/`cancelled`) · buildable now
- **Generated document attached to the request / downloadable by employee** — the resulting PDF letter is stored
  and made available to the requester (and to the HR agent's record) · seen in: Oracle HCM ("document of record"
  PDF, downloadable + attached to ticket), Darwinbox, ServiceNow · priority: table-stakes · spine: new `file`
  FileField on `DocumentRequest` (mirrors `EmployeeDocument.file` pattern); **auto-generation from a merge-field
  template is integration/later** — v1 is HR manually uploading the signed letter after approval
- **Delivery method** — email, self-service download, physical/courier, in-person pickup · seen in: Oracle HCM
  (download + ticket copy), ServiceNow (send to subject/third party), general practice for certificates needing a
  wet signature/stamp in some geographies · priority: common · spine: new field `delivery_method` (choices) ·
  buildable now (the field/choice only; actual email/courier dispatch integration is later)
- **Digital signature / e-sign on the generated letter** · seen in: ServiceNow (multi-signature docs), Keka
  (OTP-protected e-signatures on stored documents) · priority: differentiator · **integration/later** (needs an
  e-sign provider)
- **Auto-merge employee data into a letter template** (name, designation, DOJ, salary) · seen in: ServiceNow HR
  Document Templates, Keka self-service generation, Workday · priority: differentiator · **integration/later** —
  a template-engine pass; v1 ships the *request/approval/attach* workflow, not template rendering
- **Bulk document generation/download** · seen in: Darwinbox · priority: nice-to-have · out-of-scope this pass

### 3.26 ID Card Requests
- **Request type: new vs. replacement vs. correction** — NavERP.md explicitly calls out "new/replacement"; greytHR
  and general practice add a correction path (name/photo change) · seen in: greytHR Request Hub, NavERP.md 3.26 ·
  priority: table-stakes · spine: new field `request_type` (choices) on new table `IdCardRequest` · buildable now
- **Reason for replacement (lost/damaged/stolen/details-changed)** — greytHR's "Reason for request" +
  "previous card details" fields · seen in: greytHR · priority: table-stakes · spine: new `reason_type` (choices)
  + `reason` (text) + `previous_card_number` (char) · buildable now
- **Supporting document/photo attachment** — e.g. a police report for a stolen card, or a new photo for
  reissue · seen in: greytHR (optional/mandatory attachment per config) · priority: common · spine: new `file`/
  `photo` field · buildable now
- **Configurable multi-level approval with auto-forward/escalation** · seen in: greytHR (1–5 levels, auto-forward
  on inactivity, reopen, auto-close) · priority: differentiator · **out-of-scope this pass** (single-approver
  matches existing NavERP convention; see Hub notes above)
- **Reviewer verifies details then issues/prints the card** — the approval step is followed by a distinct
  fulfillment step (printing/issuance), not just a status flip · seen in: greytHR ("Issuing the card" as the final
  reviewer action) · priority: table-stakes · spine: workflow states `draft → pending → approved → issued`
  (+ `rejected`/`cancelled`) with `issued_by`/`issued_at`/`card_number` fields · buildable now
- **Link to the physical asset register** — the ID card, once issued, is a trackable physical item (already true in
  NavERP: `AssetAllocation.ASSET_CATEGORY_CHOICES` includes `id_card`) · seen in: greytHR ("Add/edit access card
  details" against the employee record); NavERP's own `AssetAllocation` model already carries this category ·
  priority: table-stakes for NavERP specifically (avoids a duplicate card-inventory table) · spine: **reuse**
  `hrm.AssetAllocation` — on issuance, `IdCardRequest` creates/links an `AssetAllocation(asset_category="id_card")`
  row so the tag/serial-number/return-tracking lives in one place · buildable now

### 3.26 Asset / Equipment Requests
- **Typed asset/equipment catalog** — laptop, phone, peripherals (NavERP.md), plus desktop/monitor/access-card/
  software-license seen across products · seen in: Rippling (device catalog + role-based saved configurations),
  Keka (asset panel by category), NavERP's own `AssetAllocation.ASSET_CATEGORY_CHOICES` · priority: table-stakes ·
  spine: new field `asset_category` on new table `AssetRequest` — **reuse**
  `AssetAllocation.ASSET_CATEGORY_CHOICES` as the base choice set (same taxonomy as what fulfillment will
  eventually create) rather than inventing a second one · buildable now
- **Request type: new allocation vs. replacement vs. upgrade** · seen in: Keka ("Request Replacement" action on an
  assigned asset), Rippling (device replacement flow) · priority: table-stakes · spine: new field `request_type`
  (choices) · buildable now
- **Business justification / reason** · seen in: universal across all surveyed products' request forms ·
  priority: table-stakes · spine: new `reason` (text) · buildable now
- **Preferred specification / configuration** — free-text spec ask (e.g. "16GB RAM", role-based preset) · seen in:
  Rippling (role-based saved device configurations) · priority: common · spine: new `specification` (text,
  free-form this pass); **catalog/SKU picker + price list is integration/later**
- **Urgency / priority level** · seen in: Zoho People (case priority), general ticketing practice · priority:
  common · spine: new `priority` (choices: low/normal/high/urgent) · buildable now
- **Approve → procure/issue → track fulfillment as its own step** — approval is not the same event as physical
  hand-over · seen in: Rippling (assign/order → ship/configure → deliver), Keka, greytHR pattern generalized ·
  priority: table-stakes · spine: workflow states `draft → pending → approved → issued` (+ `rejected`/`cancelled`)
  · buildable now
- **Link the fulfilled request to the physical asset ledger** — once issued, the concrete item (serial number,
  asset tag, issued/return dates) is tracked · seen in: Rippling, Keka; NavERP already has this exact ledger ·
  priority: table-stakes for NavERP · spine: **reuse** `hrm.AssetAllocation` — `AssetRequest.fulfilled_by` FKs the
  `AssetAllocation` row created at issuance (same reuse pattern as ID Card Requests above) · buildable now
- **Device lifecycle / retrieval on offboarding** — automatically prompts asset return · seen in: Rippling ·
  priority: differentiator · **out-of-scope this pass** — already partially covered by 3.4 Offboarding's
  `ClearanceItem` reusing `AssetAllocation`; no new work needed for 3.26
- **App/software access request (SaaS license, VPN, system access)** · seen in: Rippling (app catalog), Freshservice
  · priority: differentiator · out-of-scope this pass (NavERP has no app/license inventory yet — would need a new
  spine entity; park for a future IT/Assets module pass, e.g. Module 11)
- **Estimated cost / budget check before approval** · seen in: Rippling, general procurement-adjacent asset tools ·
  priority: nice-to-have · spine: optional `estimated_cost` field, no budget-check logic this pass

## Recommended build scope (this pass — 3 models + hub)

- **`DocumentRequest`** `[DOCREQ-]` — `employee` FK → `hrm.EmployeeProfile`; `document_type` (choices:
  `experience_letter`, `salary_certificate`, `employment_verification`, `noc`, `address_proof`, `other` — direct
  from NavERP.md 3.26 + researched Darwinbox/Freshservice catalogs); `reason` (text, required — purpose of the
  letter); `addressed_to` (char, blank — "To Whom It May Concern" or a named recipient, per verification-letter
  convention); `delivery_method` (choices: `email`, `download`, `physical`, `pickup`); `needed_by` (date, optional
  — SLA target); `status` (`draft/pending/approved/generated/delivered/rejected/cancelled` — extends the
  established `LeaveRequest` state machine with a two-step fulfillment tail matching the ServiceNow
  review-then-generate-then-send pattern and Oracle's "document of record" download); `approver`/`approved_at`/
  `decision_note` (mirrors `LeaveRequest`); `file` (FileField — the generated/signed letter HR uploads, mirrors
  `EmployeeDocument.file`); `generated_by`/`generated_at`. Reuses `hrm.EmployeeProfile` for requester identity/
  designation/DOJ context (no duplicate employee data).

- **`IdCardRequest`** `[IDREQ-]` — `employee` FK; `request_type` (choices: `new`, `replacement`, `correction` —
  NavERP.md + greytHR correction path); `reason_type` (choices: `lost`, `damaged`, `stolen`, `details_changed`,
  `other` — greytHR's reason taxonomy, relevant mainly for `replacement`); `reason` (text); `previous_card_number`
  (char, blank — greytHR's "previous card details"); `correction_details` (text, blank — what to fix, only for
  `correction`); `attachment` (FileField, blank — supporting proof, e.g. police report or new photo); `status`
  (`draft/pending/approved/issued/rejected/cancelled` — the greytHR verify-then-issue-the-card two-step tail);
  `approver`/`approved_at`/`decision_note`; `issued_by`/`issued_at`/`card_number` (char — the new card's printed
  number). **Reuses** `hrm.AssetAllocation`: adds `fulfilled_asset` FK (nullable, `SET_NULL`) so the `issue` action
  creates/links an `AssetAllocation(asset_category="id_card")` row instead of a second card-inventory table.

- **`AssetRequest`** `[ASSETREQ-]` — `employee` FK; `asset_category` (choices — **reuse**
  `AssetAllocation.ASSET_CATEGORY_CHOICES` as-is for taxonomy consistency between "requested" and "issued"; NavERP.md's
  laptop/phone/peripherals map onto `laptop`/`phone`/`other`, or add `peripheral` if the todo/build pass wants a
  closer match); `request_type` (choices: `new_allocation`, `replacement`, `upgrade`, `additional` — Keka/Rippling
  patterns); `reason` (text, required — business justification); `specification` (text, blank — free-form spec
  ask, Rippling-style); `priority` (choices: `low`, `normal`, `high`, `urgent`); `needed_by` (date, optional);
  `estimated_cost` (decimal, optional); `status` (`draft/pending/approved/issued/rejected/cancelled`);
  `approver`/`approved_at`/`decision_note`; `fulfilled_by` FK → `hrm.AssetAllocation` (nullable, `SET_NULL` — the
  `issue` action creates/links the concrete `AssetAllocation` row, exactly mirroring the `IdCardRequest` reuse
  pattern above so both requests fulfill through the same ledger). **Reuses** `hrm.AssetAllocation` for all
  post-issuance tracking (serial number, asset tag, return date) — no parallel inventory table.

- **ESS "My Requests" hub** — not a model; a view aggregating `LeaveRequest` + `AttendanceRegularization` +
  `DocumentRequest` + `IdCardRequest` + `AssetRequest` for `request.user`'s `EmployeeProfile`, with per-type counts
  and a "raise new request" launcher into each create form — the Workday Help / greytHR Request Hub / Zoho People
  Help Desk pattern, achievable purely with querysets over the existing + 3 new models (no new table).

All three new models follow the exact `TenantNumbered` + `draft → pending → approved/rejected/cancelled` shape
already used by `LeaveRequest`/`AttendanceRegularization`/`LeaveEncashment`, extended with one fulfillment tail
state (`generated`/`delivered` for documents, `issued` for the ID card and asset requests) — consistent with the
`LeaveEncashment` `approved → paid` precedent already in the codebase.

## Deferred (later passes / integrations)

- **Multi-level configurable approval chains (1–5 stages), auto-forward-on-inactivity, reopen, auto-close** —
  greytHR Request Hub's differentiator; a cross-cutting workflow-engine feature better solved once, module-wide,
  not per sub-module.
- **SLA breach auto-escalation** — capture the `needed_by` target date now; the scheduled-job escalation/alerting
  engine is integration/later.
- **Auto-merge document generation from a template engine** (pull name/designation/DOJ/salary into a letter body) —
  v1 ships the request → approve → HR-uploads-the-signed-file workflow; template rendering is a follow-up pass.
- **Digital / e-signature on generated letters** — needs an e-sign provider integration (DocuSign-style), out of a
  single Django pass.
- **Email/courier dispatch automation for `delivery_method`** — the field is captured now; actual
  email-send/courier-tracking integration is later.
- **FAQ / knowledge-base article linkage per request type** — belongs with 3.27 Communication Hub / Help Desk, not
  3.26.
- **CC/watcher notifications, push/email alerts on status change** — needs notification infrastructure common to
  many modules; not built per sub-module.
- **App/software/license access requests (SaaS, VPN, system access)** — needs a software/license inventory entity
  NavERP doesn't have yet; candidate for a future IT/Assets module (Module 11) pass.
- **Automatic asset-retrieval prompts on offboarding** — already indirectly covered by 3.4 `SeparationCase` →
  `ClearanceItem` reusing `AssetAllocation`; no new 3.26 work needed.
- **Bulk document generation/download, catalog/SKU-level asset picker with pricing** — nice-to-have breadth
  features seen in Darwinbox/Rippling but not required for a first tenant-scoped CRUD pass.
