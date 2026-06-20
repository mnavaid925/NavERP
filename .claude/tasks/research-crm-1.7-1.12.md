# Research — CRM Extension: Sub-modules 1.7 through 1.12 (slug: crm)

> **Scope:** This is an *extension* pass on the already-built `apps/crm` app (1.1–1.6 are done).
> The six sub-modules below each represent a distinct capability cluster added on top of the
> existing Lead / Opportunity / Campaign / Case / KnowledgeArticle / CrmTask / AccountProfile /
> ContactProfile models.  Research focuses exclusively on 1.7–1.12.

---

## Leaders surveyed (with source links)

1. **Vtiger All-In-One CRM** — 61-module platform unifying sales, help desk, projects, and inventory
   — [https://www.vtiger.com/features/](https://www.vtiger.com/features/)
2. **Bitrix24** — free-tier workspace combining CRM, invoicing, projects, workflow automation, and partner extranets
   — [https://www.bitrix24.com/uses/free-crm-with-invoicing.php](https://www.bitrix24.com/uses/free-crm-with-invoicing.php)
3. **Zoho CRM / Zoho One** — tightly integrated suite (CRM + Invoice + Billing + Sign + Projects + Inventory)
   — [https://www.zoho.com/us/billing/features/payments/](https://www.zoho.com/us/billing/features/payments/)
4. **Salesforce CPQ & Revenue Cloud** — configure-price-quote with advanced multi-level approval flows and quote-to-cash
   — [https://softwarefinder.com/sales-tools/salesforce-cpq-billing](https://softwarefinder.com/sales-tools/salesforce-cpq-billing)
5. **HubSpot Revenue Hub / CPQ** — quote approval routing, e-signature, payments, workflow webhooks (2025 INBOUND launch)
   — [https://vantagepoint.io/blog/hs/hubspot-quote-based-workflow-triggers](https://vantagepoint.io/blog/hs/hubspot-quote-based-workflow-triggers)
6. **Microsoft Dynamics 365 Project Operations** — post-sale resource scheduling, mobile time entry, skills-based assignment
   — [https://www.microsoft.com/en-us/dynamics-365/products/project-operations](https://www.microsoft.com/en-us/dynamics-365/products/project-operations)
7. **Insightly CRM** — one-click deal-to-project conversion, Gantt/Kanban milestones, CRM-native project delivery
   — [https://www.selecthub.com/p/crm-software/insightly/](https://www.selecthub.com/p/crm-software/insightly/)
8. **Keap (Infusionsoft)** — proposal-to-payment billing, recurring invoices, "when-then" drag-and-drop automation
   — [https://keap.com/solutions/invoices-payments](https://keap.com/solutions/invoices-payments)
9. **PandaDoc** — document generation with merge-field variables, built-in e-signature, signature-status tracking, content library
   — [https://www.pandadoc.com/document-generation/](https://www.pandadoc.com/document-generation/)
10. **Gainsight Customer Success** — health scorecard engine (weighted inputs), playbook/CTA system, NPS/CSAT surveys, renewal risk
    — [https://www.gainsight.com/customer-success/](https://www.gainsight.com/customer-success/)
11. **Chargebee** (specialist, 1.7 depth) — recurring/subscription billing, prorated charges, dunning, consolidated invoices, 30+ payment gateways
    — [https://www.chargebee.com/features/](https://www.chargebee.com/features/)
12. **Creatio / SugarCRM** — no-code BPM/workflow engine, condition-branch rules, automated approval routing
    — [https://research.com/software/reviews/creatio-review](https://research.com/software/reviews/creatio-review)

---

## Feature catalog by sub-module

---

### 1.7 Finance & Billing Management

#### Invoicing

- **Quote-to-Invoice One-Click Conversion** — Converts an accepted quote/proposal directly into a numbered
  invoice, carrying over line items, tax, discounts, and the linked party/opportunity.
  Seen in: Vtiger, Zoho Invoice, HubSpot CPQ, Keap, Chargebee.
  Priority: **MVP** (table-stakes across all leaders).
  Spine: reuses `core.Invoice` + `core.InvoiceLine` + `core.Party` + `core.Item`; the CRM layer adds
  a FK `source_opportunity` → `crm.Opportunity` on a thin CRM-side wrapper or directly on Invoice.
  Buildable now — no external integration required.

- **Recurring / Subscription Invoices** — Defines a billing schedule (weekly / monthly / quarterly /
  annual / custom) so the system auto-generates the next invoice on the due date.  Includes prorated
  charges for mid-cycle changes, advance invoices, and optional consolidated invoicing (multiple lines
  into one document).
  Seen in: Chargebee, Zoho Billing, Keap, Bitrix24.
  Priority: **MVP**.
  Spine: needs a new table `crm.RecurringInvoice` (schedule, next_run_date, frequency, cycle_count)
  linked to `core.Invoice` (template invoice) and `core.Party`.
  Buildable now (a Django management command or Celery beat job generates the next invoice).

- **Tax & Discount Logic** — Line-level percentage or fixed discount fields; tax-code selection per
  line resolved from `core.TaxCode`; automatic tax amount calculation; regional rate support through
  the existing TaxCode table.
  Seen in: Vtiger, Zoho, HubSpot CPQ, Salesforce CPQ, Keap.
  Priority: **MVP**.
  Spine: reuses `core.TaxCode`; discount fields live on `core.InvoiceLine` (already has `unit_price`
  + `qty`; add `discount_pct`, `discount_fixed`).
  Buildable now.

#### Payment Tracking

- **Payment Gateway Integration (Stripe / PayPal / Razorpay)** — Embedded "Pay Now" link on the
  invoice PDF or email; webhook listener updates invoice status to `paid` on successful charge.
  Seen in: Vtiger, Zoho, HubSpot, Keap, Chargebee.
  Priority: **MVP** (core flow); gateway webhooks are an **integration/later** concern.
  Spine: reuses `core.Payment` + `core.PaymentAllocation`; add `gateway` + `gateway_txn_id` fields
  to a CRM `PaymentRecord` wrapper or extend `core.Payment`.
  Gateway webhooks = integration/later; the data model can be built now.

- **Partial / Milestone Payments** — Records a payment that settles only part of an invoice total;
  multiple payments accumulate via `core.PaymentAllocation` until fully settled.  Milestone variant
  links a payment schedule to project milestones.
  Seen in: Zoho Billing, Chargebee, Vtiger, Bitrix24.
  Priority: **MVP**.
  Spine: fully handled by existing `core.PaymentAllocation` (each allocation row is a partial
  payment); no new table needed — the CRM UI surfaces the allocation list.
  Buildable now.

- **Automated PDF Receipt Generation** — System-generated receipt PDF after each payment, emailed
  to the customer.
  Seen in: Zoho Invoice, Keap, Chargebee, Vtiger.
  Priority: **strong**.
  Spine: no new table; PDF rendered via Django template + `weasyprint` / `reportlab` at receipt time,
  stored via `core.Document` generic relation.
  Buildable now.

#### Expense Tracking

- **Deal-Related Expense Logging** — Employees record travel, meals, software, and other costs
  linked to a specific Opportunity or Project.  Categories (travel / meals / software / other) with
  a receipt attachment.
  Seen in: Vtiger (Timelogs include cost), MS Dynamics 365 Project Operations, Zoho Expense,
  Bitrix24 (expense approval workflow).
  Priority: **MVP** (first-class feature for 1.7).
  Spine: new table `crm.Expense` (EXP-) with FK to `crm.Opportunity`, optional FK to a future
  `crm.CrmProject`; posts a debit to `core.JournalEntry` (expense account) via service function.
  Buildable now.

- **Deal Profit Margin Calculation** — Computes `deal_revenue − sum(expenses)` to show true margin
  on a closed Opportunity.  Exposed as a property or annotation on Opportunity detail page.
  Seen in: Vtiger, Insightly, MS Dynamics 365 Project Operations.
  Priority: **strong**.
  Spine: derived from existing `crm.Opportunity.amount` minus `SUM(crm.Expense.amount WHERE opp=X)`;
  no new table — a property or annotated queryset.
  Buildable now.

- **Expense Approval Workflow** — Manager must approve expenses above a threshold before they are
  posted to the GL.
  Seen in: Bitrix24 (paid plans), MS Dynamics 365.
  Priority: **nice-to-have** (can reuse the generic workflow engine from 1.10).
  Spine: status field on `crm.Expense` (`draft / submitted / approved / rejected`) + `approved_by`
  FK to User.
  Buildable now.

---

### 1.8 Project & Delivery Management (Post-Sale)

#### Projects

- **Auto Deal-to-Project Conversion** — When an Opportunity is marked `closed_won`, the system
  optionally creates a CRM Project pre-populated with the account, amount, owner, and expected
  close/start dates.
  Seen in: Insightly (signature feature), Vtiger, HubSpot (via workflow), MS Dynamics 365.
  Priority: **MVP**.
  Spine: reuses `core.Project` (already in ERD) as the anchor; the CRM adds a `crm.CrmProject`
  extension record (or reuses `core.Project` directly) with FK `source_opportunity`.
  Buildable now — triggered in the Opportunity `save()` or a view action.

- **Gantt / Kanban Milestone & Deadline Views** — Visual timeline (Gantt) and card-based (Kanban)
  views of project milestones and tasks.  Drag-to-reschedule on Gantt.
  Seen in: Vtiger, Insightly, MS Dynamics 365, Bitrix24.
  Priority: **strong**.
  Spine: milestones/tasks stored in `crm.CrmMilestone` linked to `crm.CrmProject`; Gantt rendered
  client-side (HTMX + a JS chart library such as `dhtmlxGantt` lite or `frappe-gantt`).
  Buildable now (simple Gantt via JS library; drag-to-reschedule is nice-to-have later).

- **Kanban Board per Project** — Card-per-task board view with drag-and-drop stage transitions.
  Seen in: Vtiger, Bitrix24, Insightly.
  Priority: **strong**.
  Spine: uses the same `crm.CrmMilestone` / task records; Kanban = HTMX drag-and-drop columns.
  Buildable now.

#### Time Tracking

- **Employee Timesheets Against Projects/Clients** — Employees log hours directly against a project
  (and optionally a specific milestone), with date, hours, and description.
  Seen in: Vtiger (Timelogs), MS Dynamics 365 Project Operations, Bitrix24.
  Priority: **MVP**.
  Spine: new table `crm.Timesheet` (TS-) with FK to `crm.CrmProject`, `core.Party` (client),
  `django.User` (employee); fields: `date`, `hours`, `description`, `is_billable`, `status`.
  Buildable now.

- **Billable vs. Non-Billable Hours** — Each timesheet entry is flagged `billable` or `non-billable`;
  totals feed into project billing and margin calculations.
  Seen in: Vtiger, MS Dynamics 365, Bitrix24, Insightly.
  Priority: **MVP**.
  Spine: `is_billable` boolean on `crm.Timesheet`; billable total displayed on project detail.
  Buildable now.

- **Timesheet Approval** — Manager approves or rejects employee time entries before they are locked.
  Seen in: MS Dynamics 365, Zoho Projects.
  Priority: **nice-to-have**.
  Spine: `status` field on `crm.Timesheet` (`draft / submitted / approved / rejected`) +
  `approved_by` FK.
  Buildable now.

#### Resource Allocation

- **Workload / Capacity View** — Visual view of each employee's total booked hours across all
  projects for a date range; highlights overbooked vs. available capacity.
  Seen in: MS Dynamics 365 (skills-based scheduler), Harvest, Bitrix24.
  Priority: **strong**.
  Spine: derived from `crm.Timesheet` aggregated by user + date range; rendered as a simple
  heat-map or bar-per-person table; no new table needed.
  Buildable now.

- **Skills-Based Resource Search** — Filter team members by skill tag when assigning to a project.
  Seen in: MS Dynamics 365.
  Priority: **nice-to-have**.
  Spine: new M2M `crm.ResourceSkill` (user ↔ skill tag) or extend `core.Employment`.
  Buildable now.

---

### 1.9 Document & Contract Management

#### E-Signatures

- **Built-In Digital Signing (DocuSign-Style)** — Sends a document to one or more signers by email;
  each signer sees the document in-browser, clicks to sign, and the system records the signature
  event (timestamp, IP, signer identity).
  Seen in: HubSpot CPQ (2025 launch), Zoho Sign, PandaDoc, Vtiger, Keap.
  Priority: **MVP** (strong demand across all all-in-one suites).
  Spine: new table `crm.SignatureRequest` (DOC- prefix) with FK to `crm.ContractDocument`, status
  (`draft / sent / viewed / signed / declined / expired`), and a `crm.SignerRecord` child table
  (one row per signer).
  Buildable now (simplified in-house flow); full DocuSign / Zoho Sign API = integration/later.

- **Signature Event Tracking** — Records when the document was viewed, signed, or declined; visible
  on the document detail timeline.
  Seen in: PandaDoc, Zoho Sign, HubSpot CPQ, DocuSign.
  Priority: **MVP**.
  Spine: `crm.SignerRecord` rows carry `viewed_at`, `signed_at`, `declined_at`, `ip_address`.
  Buildable now.

#### Document Generation

- **Dynamic Templates with Merge Variables** — Template author inserts `{{Account.Name}}`,
  `{{Opportunity.Amount}}`, `{{Today}}` etc.; the system resolves those fields from the linked CRM
  record and renders the final document (HTML→PDF or DOCX).
  Seen in: PandaDoc (core product), Zoho Sign (AI document generator 2025), HubSpot CPQ
  (Breeze-generated quotes), Vtiger (customizable templates), Salesforce CPQ.
  Priority: **MVP**.
  Spine: new table `crm.DocTemplate` with `body` (HTML with Jinja/Django template tags),
  `template_type` choices (nda / proposal / contract / receipt / quote); rendering via Django
  template engine + `weasyprint`.
  Buildable now.

- **Clause / Section Library** — Pre-approved reusable blocks (standard T&C, liability clause,
  payment terms) that can be inserted into templates.
  Seen in: PandaDoc (content library), Salesforce CPQ.
  Priority: **nice-to-have**.
  Spine: new table `crm.ClauseLibrary`; FK from `crm.DocTemplate`.
  Buildable now.

#### File Repository

- **Cloud File Storage Organized by Account / Deal** — Every file (PDF, DOCX, image) can be
  attached to an Account (Party), Opportunity, Project, or Contract; organized in a virtual folder
  structure.
  Seen in: PandaDoc, Vtiger, Zoho CRM, HubSpot, Bitrix24.
  Priority: **MVP**.
  Spine: reuses `core.Document` (GenericFK + FileField + classification + version); the CRM UI
  provides the "per-Account / per-Deal" folder view by filtering on `content_type` + `object_id`.
  Buildable now (S3 via `django-storages` is integration/later; local FileField is now).

- **Version Control for Contract Revisions** — When a new version of a document is uploaded, the
  old version is retained as v1, v2, etc., with the latest flagged as current.
  Seen in: PandaDoc, Zoho Sign, DocuSign, Salesforce CPQ, MS SharePoint/Dynamics.
  Priority: **strong**.
  Spine: `core.Document.version` field already exists; the CRM layer adds a `crm.ContractDocument`
  model (CTR-) that groups related `core.Document` records under one contract reference, with a
  `current_version` pointer.
  Buildable now.

---

### 1.10 Automation & Workflow Engine

#### Trigger-Based Actions (If This, Then That)

- **Visual Rule Builder** — Admin defines a rule: pick a trigger entity (Lead / Opportunity / Case /
  Invoice), pick trigger event (created / updated / status changed / field value), set conditions
  (field comparisons with AND/OR), pick actions (send email / create task / update field / fire
  webhook / start approval).
  Seen in: Zoho CRM (10-condition AND/OR rule with instant + scheduled actions), HubSpot Workflows,
  Bitrix24 Smart Process Automation, Keap (drag-and-drop "when-then" builder), Creatio (no-code
  BPM), Salesforce Flow.
  Priority: **MVP**.
  Spine: new table `crm.WorkflowRule` (WFR-) with `trigger_entity`, `trigger_event`, `conditions`
  (JSONField), `actions` (JSONField); execution engine is a Django signal + Celery task.
  Buildable now.

- **Scheduled / Time-Delayed Actions** — Run an action N hours/days after a trigger event (e.g.,
  "if no reply in 3 days, send follow-up email").
  Seen in: Zoho CRM (scheduled actions), HubSpot Workflows, Keap.
  Priority: **strong**.
  Spine: `crm.WorkflowRule` adds `delay_value` + `delay_unit` fields; a Celery beat task scans
  pending scheduled rule executions.
  Buildable now (Celery required; if no Celery, defer to a management command).

- **Action Log** — Immutable record of each workflow rule firing: which rule, which record, which
  actions were taken, success/failure.
  Seen in: Zoho CRM, HubSpot, Salesforce Flow.
  Priority: **strong**.
  Spine: new table `crm.WorkflowLog` (linked to `crm.WorkflowRule`).
  Buildable now.

#### Approval Processes

- **Quote/Discount Approval Lock** — When a discount on a Quote/Invoice exceeds a configured
  threshold, the document is locked (`pending_approval` status) and an approval request is routed
  to a designated approver; the document cannot be sent until approved.
  Seen in: Salesforce CPQ (Advanced Approval Processes), HubSpot CPQ (sequential chains), Zoho CRM
  (approval process module), Bitrix24 (RPA for approvals).
  Priority: **MVP** (differentiating feature for 1.10).
  Spine: new table `crm.ApprovalRequest` (APR-) linked generically to the record under review
  (Invoice / ContractDocument); status (`pending / approved / rejected`), `approver` FK to User,
  `threshold_value`, `reason`.
  Buildable now.

- **Multi-Level Approval Chains** — Route through approver A, then B, then C in sequence; any
  rejection short-circuits the chain.
  Seen in: Salesforce CPQ, HubSpot CPQ Enterprise, Zoho.
  Priority: **nice-to-have** (single-level is MVP; chain is v2).
  Spine: `crm.ApprovalStep` child of `crm.ApprovalRequest` (step_order, approver, status).
  Buildable now.

#### Webhooks

- **Outbound Webhook on CRM Event** — When a trigger fires, the system POSTs a JSON payload to a
  configured external URL (Slack incoming webhook, Discord bot, n8n, Zapier, ERP endpoint).
  Seen in: Zoho CRM (instant action type: webhook), HubSpot (Operations Hub Pro), Bitrix24 (REST
  API + outbound events), Salesforce Flow (HTTP Callout).
  Priority: **strong**.
  Spine: `crm.WorkflowRule` actions JSONField includes `{"type": "webhook", "url": "..."}`;
  Celery task fires the HTTP POST; no new table beyond WorkflowLog.
  Buildable now.

---

### 1.11 Customer Success & Retention

#### Onboarding Pipelines

- **Step-by-Step Client Onboarding Checklists** — Each new client gets an onboarding pipeline
  (ordered list of steps: kickoff call, training session, go-live); each step has an assignee and
  due date; overall % completion is tracked.
  Seen in: Gainsight (Playbooks / Success Plans), ChurnZero (SuccessPlays), Totango (SuccessBLOCs),
  HubSpot (Customer Portal + Workflows), Vtiger (Projects).
  Priority: **MVP**.
  Spine: new table `crm.OnboardingPlan` (CS-) with FK to `core.Party` (client); child table
  `crm.OnboardingStep` (order, title, assignee, due_date, completed_at).
  Buildable now.

- **Onboarding Plan Templates** — Reusable plan blueprints that can be applied to any new customer
  with one click (standard 30/60/90-day templates).
  Seen in: Gainsight, Totango, ChurnZero.
  Priority: **strong**.
  Spine: `crm.OnboardingTemplate` + `crm.OnboardingTemplateStep`; applying a template clones
  steps into a new `crm.OnboardingPlan`.
  Buildable now.

#### Health Scoring

- **Automated 0–100 Health Score** — A configurable formula aggregates weighted signals: invoice
  payment punctuality, open support tickets (Cases), task completion rate, survey NPS score, and
  optionally login frequency.  Score recomputed on a schedule or on signal change.
  Seen in: Gainsight (Scorecards, with configurable weights per measure), ChurnZero (ChurnScore),
  Totango (composite health), Vitally.
  Priority: **MVP** (core 1.11 feature).
  Spine: new table `crm.HealthScore` with FK to `core.Party`, fields: `score` (0–100),
  `computed_at`, `breakdown` (JSONField storing per-signal sub-scores and weights); recomputed
  by a service function that queries `core.Invoice`, `core.Payment`, `crm.Case`, `crm.Survey`.
  Buildable now.

- **Health Score Signal Weights** — Admin sets the weight of each signal (e.g. payment punctuality
  40%, open tickets 30%, NPS 20%, task completion 10%).
  Seen in: Gainsight (Scorecard measure weights), ChurnZero.
  Priority: **strong**.
  Spine: new table `crm.HealthScoreConfig` (one row per tenant, stores signal weights as JSON or
  individual decimal fields).
  Buildable now.

- **Churn Risk Alerts** — When health score drops below a configured red/yellow threshold, an alert
  is triggered: creates a CrmTask for the account owner or fires a WorkflowRule.
  Seen in: Gainsight, ChurnZero, Totango.
  Priority: **strong**.
  Spine: reuses `crm.WorkflowRule` (trigger: health_score_changed; condition: score < threshold;
  action: create task / send email).
  Buildable now.

#### Surveys & Feedback (NPS)

- **NPS Email Survey** — System sends a 0–10 Net Promoter Score survey to a customer contact at a
  configured schedule (post-close, quarterly, annual) or on a trigger; records promoter/passive/
  detractor classification.
  Seen in: Gainsight (built-in NPS/CSAT engine), ChurnZero, HubSpot Service Hub, Zoho CRM
  (integration with Zoho Survey).
  Priority: **MVP**.
  Spine: new table `crm.Survey` (NPS-) with FK to `core.Party`, `survey_type` (nps / csat / ces),
  `score` (0–10), `feedback_text`, `sent_at`, `responded_at`, `classification` (promoter /
  passive / detractor).
  Buildable now.

- **Post-Ticket CSAT Survey** — Automatically sends a satisfaction survey when a Case is closed;
  CSAT score feeds into the customer health score.
  Seen in: Gainsight, ChurnZero, HubSpot, Zoho Desk.
  Priority: **strong**.
  Spine: same `crm.Survey` table; triggered from `crm.Case.save()` when status moves to `closed`.
  Buildable now.

- **Survey Response Analytics** — Aggregate NPS trend over time (monthly average), detractor list,
  promoter/passive/detractor split.
  Seen in: Gainsight (Impact Analyzer), ChurnZero, HubSpot.
  Priority: **nice-to-have** (reporting pass).
  Spine: derived queries over `crm.Survey`; no new table.
  Buildable now.

---

### 1.12 Inventory & Vendor Management

#### Purchase Orders (POs)

- **Create POs to Order Stock from Vendors** — CRM user creates a purchase order for a supplier
  (Party with role=vendor) to restock products; PO carries line items (Item, qty, unit price).
  Seen in: Vtiger (full PO module), Zoho CRM/Inventory, Bitrix24, HubSpot (via 3rd-party only).
  Priority: **MVP**.
  Spine: reuses `core.PurchaseOrder` + `core.PurchaseOrderLine` + `core.Party` (vendor role) +
  `core.Item`; the CRM module adds a UI layer in `apps/crm` that creates POs via these existing
  spine tables.  No new model — just CRM-scoped views over `core.PurchaseOrder`.
  Buildable now.

- **Vendor Invoice (Bill) from PO** — One-click generation of a payable `core.Invoice` from a
  received PO (kind=payable).
  Seen in: Vtiger, Zoho Inventory.
  Priority: **strong**.
  Spine: reuses `core.Invoice` (kind=payable); no new table.
  Buildable now.

#### Stock Tracking

- **Auto Stock Deduction on Invoice Paid** — When a receivable Invoice is marked `paid`, the system
  posts a negative `core.StockMove` for each line item that references a stockable `core.Item`.
  Seen in: Vtiger, Zoho Inventory, Bitrix24.
  Priority: **MVP**.
  Spine: reuses `core.StockMove`; a service function in the CRM invoice payment view creates the
  move rows; no new table.
  Buildable now.

- **Low-Stock Alert** — When on-hand quantity (derived from `core.StockMove` aggregation) falls
  below a configured `reorder_point`, a CRM notification or CrmTask is created for the stock manager.
  Seen in: Vtiger, Zoho Inventory, Bitrix24.
  Priority: **strong**.
  Spine: new table `crm.StockAlert` (or extend `core.Item`) to store `reorder_point` per Item per
  tenant; check run on stock move post.
  Buildable now.

- **On-Hand Quantity Widget** — Displays current stock level on the Item detail or CRM Invoice line
  item picker.
  Seen in: Vtiger, Zoho, Bitrix24.
  Priority: **strong**.
  Spine: derived from `StockMove` aggregation; no new table.
  Buildable now.

#### Vendor/Partner Portal

- **Separate Partner Login Area** — Partners (Party with role=partner) can log in to a restricted
  portal (separate URL prefix, e.g. `/portal/partner/`) to register leads or check stock levels.
  Seen in: Zoho Inventory (Vendor Portal — view POs, upload invoices, comment, track payments),
  Bitrix24 (extranet portal), HubSpot (third-party add-on), Vtiger (customer portal, adaptable).
  Priority: **strong** (differentiating for 1.12).
  Spine: reuses Django's auth system + `core.Party` (role=partner); new table
  `crm.PartnerPortalAccess` (partner Party → portal User mapping, scoped to tenant); a separate
  URL namespace `portal/` with permission-checked views.
  Buildable now (simplified read-only portal); full self-service PO acceptance = integration/later.

- **Partner Lead Registration** — From the partner portal, a partner submits a lead they sourced;
  the CRM creates a `crm.Lead` attributed to that partner.
  Seen in: HubSpot Solutions Partner (beta feature), Zoho CRM Partner Portal, Salesforce PRM.
  Priority: **nice-to-have** (portal first, lead form second).
  Spine: `crm.Lead.source = "partner_referral"` + FK `referred_by` → `core.Party` (partner).
  Buildable now.

- **Stock Visibility for Partners** — Partners can query current on-hand levels for catalogued items
  from within the portal.
  Seen in: Zoho Inventory vendor portal, Vtiger.
  Priority: **nice-to-have**.
  Spine: derived from `core.StockMove`; portal view with restricted item list.
  Buildable now.

---

## Recommended build scope (this pass — 8 models)

All eight models are owned by `apps/crm`; each is tenant-scoped and numbered with the indicated
prefix. They cover the primary bullet of every one of the six extension sub-modules.

### 1. `crm.Expense` [EXP-]
Covers: **1.7 Expense Tracking** (primary bullet) and feeds profit-margin calculation.
Fields: `tenant`, `number` (EXP-), `opportunity` FK→`crm.Opportunity` (nullable),
`project` FK→`crm.CrmProject` (nullable), `category` choices
(travel / meals / software / accommodation / other), `amount` Decimal, `currency` FK→`core.Currency`,
`expense_date` Date, `description` text, `receipt` FileField (nullable), `status` choices
(draft / submitted / approved / rejected), `submitted_by` FK→User, `approved_by` FK→User (nullable),
`created_at`, `updated_at`.
Reuses: `crm.Opportunity`, `core.Currency`.
Justification: all leaders (Vtiger, Dynamics 365, Zoho Expense) treat deal expenses as a first-class
entity; profit-margin property on Opportunity is then `amount − SUM(expenses WHERE status=approved)`.

### 2. `crm.CrmProject` [PRJ-]
Covers: **1.8 Projects** (primary bullet) — CRM-owned project extending/wrapping `core.Project`.
Fields: `tenant`, `number` (PRJ-), `core_project` OneToOneField→`core.Project` (nullable, for
linking when the full Project module is built), `name`, `account` FK→`core.Party`,
`source_opportunity` FK→`crm.Opportunity` (nullable, set on auto-conversion),
`status` choices (planning / active / on_hold / completed / cancelled),
`start_date` Date, `end_date` Date (nullable), `budget` Decimal, `owner` FK→User,
`description` text, `created_at`, `updated_at`.
Reuses: `core.Project` (optionally), `crm.Opportunity`, `core.Party`.
Justification: Insightly's signature feature; Vtiger, Dynamics 365, Bitrix24 all auto-convert
Closed Won opportunities into projects.

### 3. `crm.CrmMilestone` [MS-]
Covers: **1.8 Gantt / Kanban milestones** and task boards.
Fields: `tenant`, `project` FK→`crm.CrmProject`, `title`, `kind` choices (milestone / task),
`status` choices (not_started / in_progress / completed / blocked),
`assignee` FK→User (nullable), `start_date` Date (nullable), `due_date` Date (nullable),
`completed_at` DateTime (nullable), `order` PositiveInt (Kanban order within status column),
`parent` FK→self (nullable, for sub-tasks), `description` text, `created_at`, `updated_at`.
Reuses: `crm.CrmProject`.
Justification: Gantt/Kanban is table-stakes across Vtiger, Insightly, Bitrix24, Dynamics 365;
Gantt rendered via lightweight JS library (frappe-gantt or dhtmlxGantt lite).

### 4. `crm.Timesheet` [TS-]
Covers: **1.8 Time Tracking** (primary bullet) — billable vs. non-billable.
Fields: `tenant`, `number` (TS-), `project` FK→`crm.CrmProject`, `milestone` FK→`crm.CrmMilestone`
(nullable), `employee` FK→User, `client` FK→`core.Party` (nullable),
`date` Date, `hours` Decimal (max_digits=5, decimal_places=2), `description` text,
`is_billable` Boolean (default True),
`status` choices (draft / submitted / approved / rejected),
`approved_by` FK→User (nullable), `created_at`, `updated_at`.
Reuses: `crm.CrmProject`, `core.Party`.
Justification: Vtiger Timelogs, Dynamics 365 mobile time entry, Bitrix24 — all treat timesheet
as a separate entity from tasks; billable flag drives project billing totals.

### 5. `crm.DocTemplate` + `crm.ContractDocument`
Two closely related models covering **1.9 Document Generation + File Repository**:

**`crm.DocTemplate`** [TPL-]
Fields: `tenant`, `number` (TPL-), `name`, `template_type` choices
(nda / proposal / contract / quote / receipt), `body` TextField (HTML + Django template syntax
for merge variables like `{{ opportunity.name }}`), `is_active` Boolean,
`owner` FK→User, `created_at`, `updated_at`.
Reuses: nothing extra beyond tenant.
Justification: PandaDoc, Zoho Sign, HubSpot CPQ all centre their document generation on
merge-field templates rendered server-side.

**`crm.ContractDocument`** [CTR-]
Fields: `tenant`, `number` (CTR-), `name`, `template` FK→`crm.DocTemplate` (nullable),
`opportunity` FK→`crm.Opportunity` (nullable), `account` FK→`core.Party` (nullable),
`current_version` PositiveSmallInt (default 1), `status` choices
(draft / sent / viewed / signed / declined / expired / archived),
`signed_at` DateTime (nullable), `expires_at` DateTime (nullable),
`owner` FK→User, `created_at`, `updated_at`.
Related child (not a separate numbered model): `crm.SignerRecord`
(contract FK, signer_party FK→`core.Party`, signer_email, token CharField, viewed_at DateTime,
signed_at DateTime, declined_at DateTime, ip_address).
Reuses: `core.Document` (each rendered PDF is attached via GenericFK), `core.Party`.
Justification: PandaDoc versioning + signature tracking; Zoho Sign; HubSpot CPQ e-signature
(2025 launch) — all treat signature as a tracked per-signer event, not a binary flag.

### 6. `crm.WorkflowRule` [WFR-]
Covers: **1.10 Automation & Workflow Engine** (primary bullet) + Approval Processes + Webhooks.
Fields: `tenant`, `number` (WFR-), `name`, `is_active` Boolean,
`trigger_entity` choices (lead / opportunity / case / invoice / expense / health_score),
`trigger_event` choices (created / updated / status_changed / field_value / date_reached),
`trigger_field` CharField (blank — the specific field to watch),
`trigger_value` CharField (blank — the value to match),
`conditions` JSONField (list of {field, operator, value} dicts, AND/OR logic),
`actions` JSONField (list of {type, params} dicts where type ∈
  create_task / send_email / update_field / webhook / start_approval / create_survey),
`delay_value` PositiveSmallInt (nullable), `delay_unit` choices (minutes / hours / days — nullable),
`owner` FK→User, `created_at`, `updated_at`.
Companion: `crm.WorkflowLog` (rule FK, record_ct + record_id GenericFK, fired_at, status, error_msg).
Companion: `crm.ApprovalRequest` (APR-) —
  rule FK (nullable), `object_ct`+`object_id` GenericFK, `approver` FK→User,
  `threshold_field` CharField, `threshold_value` Decimal (nullable),
  `status` choices (pending / approved / rejected / expired),
  `approved_at` DateTime (nullable), `rejected_at` DateTime (nullable),
  `reason` text, `created_at`.
Reuses: Django ContentTypes for GenericFK; no duplication of existing models.
Justification: Zoho CRM (10-condition rule builder), HubSpot Workflows, Salesforce Flow,
Keap "when-then", Creatio no-code BPM — trigger-based rules are table-stakes; approval locking
is table-stakes for discount/expense approval (Salesforce CPQ, HubSpot CPQ).

### 7. `crm.HealthScore` + `crm.Survey`
Two linked models covering **1.11 Customer Success & Retention**:

**`crm.HealthScore`** [HS-]
Fields: `tenant`, `account` FK→`core.Party` (unique_together with tenant),
`score` PositiveSmallInt (0–100), `tier` choices (green / yellow / red),
`breakdown` JSONField (per-signal sub-scores), `computed_at` DateTime, `updated_at`.
Config companion: `crm.HealthScoreConfig` (one row per tenant) — `weight_payments` Decimal,
`weight_tickets` Decimal, `weight_nps` Decimal, `weight_tasks` Decimal (all default 25.0,
must sum to 100).
Reuses: `core.Party`, `core.Invoice`/`Payment`, `crm.Case`, `crm.Survey` (read-only aggregations).
Justification: Gainsight Scorecards, ChurnZero ChurnScore, Totango — health scoring is the
defining feature of CS platforms; configurable weights are what separate Gainsight from simple
satisfaction flags.

**`crm.Survey`** [NPS-]
Fields: `tenant`, `number` (NPS-), `account` FK→`core.Party`, `contact` FK→`core.Party` (nullable),
`survey_type` choices (nps / csat / ces), `trigger` choices (manual / post_close / post_ticket /
scheduled), `related_case` FK→`crm.Case` (nullable), `score` PositiveSmallInt (0–10, nullable),
`feedback_text` text, `classification` choices (promoter / passive / detractor — nullable),
`sent_at` DateTime, `responded_at` DateTime (nullable), `created_at`.
Reuses: `core.Party`, `crm.Case`.
Justification: Gainsight (NPS / CSAT / CES), ChurnZero, HubSpot Service Hub — automated
post-ticket CSAT and periodic NPS are table-stakes for customer success.

### 8. `crm.PartnerPortalAccess` [PRT-]
Covers: **1.12 Vendor/Partner Portal** (primary bullet); POs and stock deduction reuse spine tables.
Fields: `tenant`, `partner_party` FK→`core.Party` (role=partner),
`portal_user` OneToOneField→`django.User` (nullable — the restricted login account),
`access_level` choices (read_only / lead_register / full),
`can_view_stock` Boolean, `can_register_leads` Boolean,
`invited_at` DateTime, `accepted_at` DateTime (nullable), `is_active` Boolean,
`created_at`, `updated_at`.
Reuses: `core.Party` (partner role), Django User.
Justification: Zoho Inventory vendor portal (PO view, invoice upload, payment tracking),
Bitrix24 extranet, Vtiger customer portal — a scoped external login is the table-stakes feature;
POs themselves use `core.PurchaseOrder`; stock display uses `StockMove` aggregation.
Note: 1.12 "PO creation" and "Stock deduction on payment" do NOT need new models — they are
CRM-scoped service functions + views over the existing `core.PurchaseOrder` / `core.StockMove`
spine tables; they are buildable now without any new entities.

---

## Deferred (later passes / integrations)

- **Payment gateway webhooks (Stripe / PayPal / Razorpay)** — Listener endpoint, signature
  verification, idempotency key storage.  Data model is ready; the HTTP handler is an
  integration/later concern.

- **External e-signature API (DocuSign / Zoho Sign / Adobe Sign)** — The CRM's in-house signature
  token flow is buildable now; delegating to a third-party API adds OAuth + webhook complexity.
  Defer API integration; keep the in-house model.

- **Multi-level approval chains (>2 levels)** — Single-approver flow is MVP; sequential chains
  (ApprovalStep child table) are a v2 enhancement.

- **Kanban drag-and-drop persistence** — HTMX drag-reorder of CrmMilestone.order is straightforward
  but requires careful CSRF/POST handling; ship a simpler status-dropdown first.

- **Gantt drag-to-reschedule** — JS Gantt chart (frappe-gantt) display is MVP; persisting
  date changes via drag is a nice-to-have follow-on.

- **Skills-based resource search (ResourceSkill M2M)** — Workload capacity view is MVP; skill
  tagging on users extends `core.Employment` and is deferred.

- **S3 / cloud file storage** — `core.Document.file` field uses Django's default storage; swap
  to `django-storages` + S3 in a later infrastructure pass.

- **AI-powered document generator** — Zoho Sign 2025 AI feature; HubSpot Breeze.  Generating
  from a template with merge fields is MVP; LLM-assisted drafting is deferred.

- **Partner portal lead form + PO acceptance** — Portal login and stock view is MVP; self-service
  lead submission and PO approval flow is a follow-on feature.

- **Survey email delivery** — SMTP integration for automated NPS/CSAT emails; in-app delivery
  (link copied to clipboard) is MVP; SMTP / SendGrid is integration/later.

- **Clause / Section Library (DocTemplate)** — Nice-to-have template component; defer to after
  core document generation is live.

- **Webhook delivery retry / dead-letter queue** — WorkflowRule webhook action is MVP; production-
  grade retry logic with exponential back-off is a Celery/infrastructure concern deferred to ops.

- **Revenue recognition (milestone billing)** — Chargebee-level prorated billing with contract
  terms and lock-in periods; deferred to the Accounting module (2.4 AR).

---

## Sources

- [Vtiger Features List](https://www.vtiger.com/features/)
- [Vtiger Inventory Management](https://www.vtiger.com/features/inventory-management/)
- [Vtiger Project Management](https://www.vtiger.com/features/project-management/)
- [Vtiger G2 Reviews](https://www.g2.com/products/vtiger-all-in-one-crm/reviews)
- [Bitrix24 CRM with Invoicing](https://www.bitrix24.com/uses/free-crm-with-invoicing.php)
- [Bitrix24 Workflow Automation](https://www.bitrix24.com/tools/crm/automation-and-integrations.php)
- [Bitrix24 Inventory: Vendors](https://helpdesk.bitrix24.com/open/16764476)
- [Zoho Billing Payments](https://www.zoho.com/us/billing/features/payments/)
- [Zoho Invoice Recurring](https://www.zoho.com/us/invoice/help/recurring-invoice/new-recurring-invoice.html)
- [Zoho Inventory Vendor Portal](https://www.zoho.com/us/inventory/help/vendor-portal/)
- [Zoho CRM Workflow Rules](https://help.zoho.com/portal/en/kb/crm/automate-business-processes/workflows/articles/configuring-workflow-rules)
- [Zoho Sign for Enterprises](https://www.zoho.com/sign/zoho-sign-for-enterprises.html)
- [Salesforce CPQ & Billing Features](https://softwarefinder.com/sales-tools/salesforce-cpq-billing)
- [Salesforce CPQ Advanced Approvals](https://www.absyz.com/salesforce-cpq-advanced-approval-processes/)
- [HubSpot Quote-Based Workflow Triggers](https://vantagepoint.io/blog/hs/hubspot-quote-based-workflow-triggers)
- [HubSpot Revenue Hub](https://www.fastslowmotion.com/hubspot-revenue-hub/)
- [HubSpot Webhooks in Workflows](https://aptitude8.com/blog/automate-smarter-using-advanced-webhook-triggers-in-hubspot-workflows)
- [MS Dynamics 365 Project Operations](https://www.microsoft.com/en-us/dynamics-365/products/project-operations)
- [MS Dynamics 365 Sales 2025 Wave 2](https://learn.microsoft.com/en-us/dynamics365/release-plan/2025wave2/sales/dynamics365-sales/)
- [Insightly CRM Review](https://www.selecthub.com/p/crm-software/insightly/)
- [Keap Invoicing & Payments](https://keap.com/solutions/invoices-payments)
- [Keap Recurring Payments](https://help.keap.com/help/recurring-payments)
- [PandaDoc Document Generation](https://www.pandadoc.com/document-generation/)
- [Gainsight Customer Success](https://www.gainsight.com/customer-success/)
- [Gainsight Features: Health Scores & Playbooks](https://www.oliv.ai/blog/gainsight-features)
- [ChurnZero vs Totango Comparison](https://www.selecthub.com/customer-success-software/totango-vs-churnzero/)
- [Chargebee Features](https://www.chargebee.com/features/)
- [Chargebee Recurring Billing](https://www.chargebee.com/recurring-billing-invoicing/)
- [Creatio Review](https://research.com/software/reviews/creatio-review)
- [CRM Automation Rules 2025](https://isitdev.com/crm-automation-rules-workflow-examples-2025/)
- [Salesforce Flow Approval Processes](https://www.salesforceben.com/salesforce-spring-25-release-new-flow-approval-process-capabilities/)
- [DocuSign vs Zoho Sign 2025](https://boostedcrm.com/docusign-vs-zoho-sign/)
