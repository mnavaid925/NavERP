# Research -- HRM 3.34 Expense Management (Employee T&E / Reimbursement)

Scope: NavERP.md `### 3.34 Expense Management` -- Expense Categories, Expense Claims, Approval Workflow,
Reimbursement, Policy Compliance. This is the **employee travel & expense (T&E) reimbursement** flow, distinct
from `crm.Expense` (1.7, a deal/project cost with a billable flag, FK'd to `crm.Opportunity`/`crm.CrmProject`) and
distinct from `hrm.PayComponent(component_type="reimbursement")` / `FinalSettlement.reimbursement_amount` (3.13/3.17
payroll payout mechanics). Pushing an *approved* claim total into payroll's `reimbursement_amount` is a deferred
integration, noted below.

## Existing code studied (coordination baseline)

- `apps/crm/models.py:1559 Expense` -- sales/deal expense (category/amount/currency_code/expense_date/receipt/
  status draft-submitted-approved-rejected/submitted_by/approved_by/is_billable). Confirms the shape of a *simple*
  single-approver expense but is NOT reused -- it is opportunity/project-scoped, not employee/tenant-T&E-scoped, and
  has no multi-level approval or policy engine. HRM 3.34 is a parallel, HR-owned model family.
- `apps/hrm/models.py:4312 InvestmentProof` (3.16) -- the file-upload precedent: `FileField(upload_to="hrm/...%Y/%m/")`
  + a form-level `clean_file` calling the shared `_validate_upload(f, allowed_ext=..., max_bytes=..., label=...)`
  helper (`apps/hrm/forms.py:894`), which enforces an extension allowlist and a size cap on any freshly-uploaded
  file, plus a WARNING comment mandating `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff` in
  production. The 3.34 receipt `FileField` on `ExpenseClaimLine` should reuse this exact pattern (its own
  `ALLOWED_RECEIPT_EXTENSIONS`/`MAX_RECEIPT_BYTES`, or reuse `ALLOWED_ONBOARDING_DOC_EXTENSIONS` since receipts are
  photos/PDFs like onboarding docs).
- `apps/hrm/views.py:11036-11134 _hr_request_submit/_cancel/_approve/_reject/_edit/_delete` -- the shared
  **single-approver, single-stage** request lifecycle (`draft -> pending -> approved/rejected/cancelled`, gated by
  `OPEN_STATUSES`, `approver`/`approved_at` stamped from `request.user`, self-approval blocked by
  `_is_own_hr_request`, decisions audited via `write_audit_log`). Used verbatim by `LeaveRequest` (3.10),
  `AssetRequest` (3.26), `Suggestion` (3.27), `DocumentRequest`. This is the lean baseline for 3.34's workflow --
  see the Approval Workflow section below for how to extend it to two stages without a new step-table.
- `apps/hrm/models.py:3297 PayComponent` -- confirms a `"reimbursement"` `component_type` already exists in payroll;
  `apps/hrm/models.py:1894 reimbursement_amount` on the settlement/payslip is the payout field a future pass would
  populate from an approved `ExpenseClaim.total_amount`. **Not built this pass.**
- `apps/accounting/models.py:90 Currency` -- global (no-tenant) ISO 4217 master, already cross-app FK'd from HRM
  (`apps/hrm/models.py:6164, 7514`). `apps/accounting/models.py:126 GLAccount` -- tenant-owned CoA node, cross-app
  FK'd from `accounting.models_advanced` with `on_delete=SET_NULL` "hint" style FKs. Both are safe, precedented
  reuse targets for 3.34.
- `apps/hrm/models.py:257 EmployeeProfile` -- the canonical HRM employee FK target (never FK to `core.Party`
  directly). `core.Employment.manager` (`apps/core/models.py:175`) is the org-hierarchy manager, but 3.34's
  approver (like every other HR request) is whichever admin/manager user acts, not an auto-derived hierarchy FK --
  consistent with the existing `_hr_request_approve` pattern.

## Leaders surveyed (with source links)

1. **SAP Concur** -- enterprise T&E category leader; AI OCR receipt capture, rules-based policy enforcement,
   Detect & Audit fraud/compliance engine -- https://www.sap.com/products/financial-management/travel-and-expense-management.html
2. **Zoho Expense** -- SMB/mid-market; up to 10-level configurable approval chains, and/or rule-based routing,
   fixed/count/mileage limit rules with warn-or-block enforcement -- https://www.zoho.com/us/expense/approval-management/ ,
   https://www.zoho.com/us/expense/policies/ , https://www.zoho.com/us/expense/kb/admin/approvals/multi-stage-approvals/
3. **Expensify** -- consumer-friendly; SmartScan OCR (photo/email/SMS receipt capture), up to 10 approval tiers,
   next-day direct-deposit reimbursement -- https://use.expensify.com/receipt-scanning-app , https://use.expensify.com/expense-management
4. **Fyle (now Sage Expense Management)** -- real-time policy engine that checks *while the expense is being
   created* (block/cap/route), built-in duplicate-expense finder, audit trails for fraud detection --
   https://www.fylehq.com/product , https://www.fylehq.com/blog/detailed-audit-trails-in-fyle-how-to-detect-fraud-and-maintain-compliance
5. **Ramp** -- card-first spend management; preset card controls by vendor/category/amount, "Policy Agent"
   auto-reviews/auto-codes/routes exceptions, ERP auto-sync -- https://ramp.com/expense-management , https://ramp.com/products
6. **Rydoo** -- travel-heavy; per-diem engine (partial rates, multi-leg trip rules, official rates in 80+
   countries), map-based mileage capture -- https://www.rydoo.com/expense/per-diem-management/ , https://www.rydoo.com/local-compliance/
7. **Navan (formerly TripActions)** -- combined travel-booking + expense; policy enforced *at the point of
   booking*, approval rules by spend type/amount/department/manager hierarchy, auto-approve in-policy + flag
   exceptions -- https://navan.com/blog/navan-expense-management-review , https://navan.com/blog/new-tripactions-tool-makes-policy-intuitive-to-transactions
8. **Happay** -- India-focused; Xpendite auto-capture from bills/SMS/cards, India GST/ITC compliance automation,
   Smart Audit AI fraud+policy-violation detection -- https://happay.com/expense-management-software/ , https://happay.com/analytics/
9. **Brex** -- card + reimbursement together under one budget/policy; OCR-populated reimbursement requests,
   point-of-purchase card decline on policy breach, auto-approve under a $ threshold, local-currency payout --
   https://www.brex.com/support/expense-reimbursements , https://www.brex.com/support/expense-management
10. **Airbase** -- spend-management platform; "Advanced Approvals" configurable chains by department/category/
    amount, Guided Procurement routes pre-spend approval before commitment -- https://info.airbase.com/hubfs/LP_Download_Assets/Advanced-Approvals.pdf
11. **Pleo** -- card + "Pocket" for out-of-pocket/mileage/cash spend, per-card spend-limit thresholds with admin
    alerts, inbox-fetch receipt matching -- https://www.pleo.io/us/features , https://blog.pleo.io/en/tools-for-seamless-expense-reimbursement
12. **Emburse Certify (Emburse Professional)** -- configurable "Flexible" (choose approver) vs. "Locked"
    (fixed approver, with auto-approve-if-no-violations option) approval workflows, receipt-required-above-$X
    threshold, line-level (not just report-level) approval -- https://help.certify.com/hc/en-us/articles/15460948139917-Flexible-Approval-Workflow ,
    https://help.certify.com/hc/en-us/articles/15460949758221-View-and-Edit-Policy

## Feature catalog by NavERP.md bullet

### 3.34.1 Expense Categories
- **Category master (name/code/active)** -- the base taxonomy every product has (Travel/Meals/Accommodation/
  Software/Other, matching `crm.Expense.CATEGORY_CHOICES` verbatim for continuity) -- seen in: all 12 -- priority:
  Must -- spine: new table `ExpenseCategory` -- buildable now.
- **Per-category spend limit (fixed amount / count / mileage)** -- Zoho Expense's limit-rule builder (fixed amount,
  expense count, mileage limit) -- seen in: Zoho Expense, Fyle -- priority: Must -- spine: new fields
  `per_claim_limit`/`monthly_limit` on `ExpenseCategory` -- buildable now.
- **Receipt-required-above threshold per category/type** -- report doesn't progress to approval until a required
  receipt is attached; Emburse lets admins set the $ threshold per policy -- seen in: SAP Concur, Emburse Certify --
  priority: Must -- spine: new field `requires_receipt_above` on `ExpenseCategory` -- buildable now.
- **Category-level GL/cost coding hint** -- Ramp auto-codes transactions and syncs to ERP GL by category; Concur/
  Zoho map categories to expense accounts for accounting export -- seen in: Ramp, SAP Concur, Zoho Expense --
  priority: Should -- spine: reuse `accounting.GLAccount` (optional `SET_NULL` "hint" FK, precedented in
  `accounting/models_advanced.py`) -- buildable now (hint only, no posting).
- **Department/branch/cost-center-specific policy variants** -- Zoho Expense lets policies differ per branch/
  department/cost-center -- seen in: Zoho Expense -- priority: Should/Later -- spine: would reuse `core.OrgUnit`
  scoping -- deferred (v1 ships one limit-set per category, tenant-wide).
- **Mileage rate / per-diem rate as a category variant** -- Rydoo computes reimbursement from official per-country
  mileage/per-diem rates -- seen in: Rydoo, Zoho Expense (mileage limit) -- priority: Later/differentiator -- new
  table(s) if built -- deferred (belongs with 3.35 Travel Management's per-diem/mileage scope, not 3.34 v1).

### 3.34.2 Expense Claims
- **Claim/report header + line items** -- a header (employee, title/purpose, period) with N expense lines --
  seen in: all 12 -- priority: Must -- spine: new tables `ExpenseClaim` (header) + `ExpenseClaimLine` (lines) --
  buildable now.
- **Receipt attachment per line** -- one file per expense line -- seen in: all 12 -- priority: Must -- spine:
  `ExpenseClaimLine.receipt` `FileField`, reusing the `InvestmentProof`/`_validate_upload` pattern (extension
  allowlist + size cap; MEDIA served with `Content-Disposition: attachment`) -- buildable now.
- **Draft / save-before-submit** -- universal -- priority: Must -- spine: `status="draft"` default, matches the
  `_hr_request_*` `OPEN_STATUSES` convention -- buildable now.
- **Split one receipt into multiple category lines (itemization)** -- SAP Concur, Expensify let one hotel folio
  become room + tax + parking lines -- priority: Should -- spine: already achievable with multiple
  `ExpenseClaimLine` rows -- buildable now (no extra field needed, just UX -- add-line-from-same-receipt).
- **Multiple receipts / itemized split of a single bill** -- as above -- priority: Should -- buildable now (same
  mechanism).
- **Foreign-currency line with home-currency conversion** -- Expensify auto-converts any-currency receipts;
  Zoho Expense and SAP Concur support multi-currency reports -- seen in: Expensify, Zoho Expense, SAP Concur --
  priority: Common -- spine: reuse `accounting.Currency`, an FX-conversion engine is new logic -- deferred (v1:
  optional currency FK for record-keeping only, no live conversion).
- **Receipt OCR / auto-extraction (merchant, date, amount, category)** -- Expensify SmartScan, SAP Concur AI OCR,
  Happay Xpendite, Pleo, Brex -- priority: Differentiator -- integration/later (external OCR/AI service).
- **Submit via mobile photo / email-forward / SMS / Slack-Teams** -- Expensify (email/SMS), Ramp (SMS/Slack/Teams),
  Rydoo, Pleo mobile -- priority: Differentiator -- integration/later (no mobile client or messaging integration
  this pass; web file-upload covers the same end state).
- **Corporate-card transaction feed & auto-matching to a claim line** -- Ramp, Brex, Pleo, Airbase, Concur --
  priority: Differentiator -- integration/later (needs a card-issuer feed).
- **Cash advance linked to / offset against a claim** -- SAP Concur, Rydoo, Happay -- priority: Common in T&E --
  spine: would be a new `ExpenseAdvance`-style table -- deferred (NavERP.md scopes this to 3.35 Travel Management's
  "Travel Advance"/"Travel Settlement" bullets, not 3.34 -- note as a cross-sub-module coordination point).

### 3.34.3 Approval Workflow
- **Multi-level / hierarchical approval chain** -- Zoho Expense and Expensify both cap at 10 configurable tiers;
  Airbase's Advanced Approvals and Navan route by amount/department/manager-hierarchy -- seen in: Zoho Expense,
  Expensify, Airbase, Navan, SAP Concur -- priority: Must -- design decision below.
- **Rule-based/conditional routing (amount, department, category, violation-count thresholds)** -- Navan, Airbase,
  Ramp, Zoho Expense (and/or logic) -- priority: Should/Differentiator -- deferred (a full rule engine is out of
  scope; the 2-stage status machine below is the lean v1 substitute).
- **Auto-approve small / fully in-policy claims** -- Brex (auto-approve under $ threshold), Emburse ("Auto Approve
  If No Policy Violations"), Ramp Policy Agent -- priority: Differentiator -- deferred (policy-engine automation;
  v1 always routes to a human).
- **Approver edits/approves individual lines, not just the whole report** -- Emburse Certify -- priority:
  Differentiator -- deferred.
- **Delegate / backup approver** -- SAP Concur, Zoho Expense -- priority: Common (enterprise) -- deferred.
- **Full audit trail of every approval action** -- SAP Concur Detect & Audit, Fyle audit trails -- priority: Must --
  spine: reuse the existing `write_audit_log` call already wired into every `_hr_request_*` action -- buildable now.

**Multi-level design decision (recommended):** extend the existing single-approver `_hr_request_*` pattern to a
**lean two-stage status machine** rather than building a generic N-step approval-chain model. NavERP.md's own
wording ("submit -> manager -> finance, etc.") maps cleanly onto
`draft -> submitted -> manager_approved -> approved (finance) -> reimbursed`, with `rejected`/`cancelled` reachable
from either open stage. This needs only **two** approver/timestamp pairs
(`manager_approver`/`manager_approved_at`, `finance_approver`/`finance_approved_at` -- or a single reused
`approver`/`approved_at` pair stamped twice, once per stage, mirroring how `LeaveRequest` already reuses one
`approver` field) plus one extra status value -- no new step/table is needed. This matches how leading products
actually implement *simple* multi-level approval (Emburse's "Locked Workflow" is exactly a fixed N-stage chain, not
a dynamic engine) while keeping the build inside this repo's established convention. A true N-level/rule-based
approval-step model (Zoho/Airbase style) is explicitly deferred -- flagged below.

### 3.34.4 Reimbursement
- **Mark reimbursed + payment method/reference/date** -- every product exposes this once a claim/report is
  approved (Zoho via CSG Forte bank transfer, Brex/Expensify direct deposit, SAP Concur "often within 48 hours") --
  seen in: all 12 -- priority: Must -- spine: new fields on `ExpenseClaim` (`payment_method`,
  `payment_reference`, `reimbursed_at`) -- buildable now.
- **Employee self-service reimbursement-status visibility** -- universal (claim detail page shows current stage) --
  priority: Must -- buildable now (status/detail page, no new model).
- **Reimbursement batch/run (bundle multiple approved claims into one payment)** -- SAP Concur, Zoho Expense --
  priority: Should -- deferred (a batch-payment-run model is a later AP-integration pass).
- **Sync approved claim total into payroll / AP for actual payout** -- Zoho Expense ("sync settlements with
  payroll and ERP"), Ramp (auto-coded + synced to ERP) -- priority: Must eventually, **deferred this pass** --
  this is exactly the coordination point flagged in the brief: push `ExpenseClaim.total_amount` into
  `PayComponent(component_type="reimbursement")` / `FinalSettlement.reimbursement_amount` in a later payroll-
  integration pass; v1 only tracks `payment_reference`/`reimbursed_at` on the claim itself.
- **Direct bank-transfer / local-currency payout integration** -- Brex, Zoho (CSG Forte), Expensify -- priority:
  Differentiator -- integration/later (a real payment-rail integration).

### 3.34.5 Policy Compliance
- **Per-category / per-claim amount-limit check** -- Zoho Expense's fixed-amount limit rules, Fyle's spend caps --
  seen in: Zoho Expense, Fyle -- priority: Must -- spine: derived check comparing `ExpenseClaimLine.amount` to
  `category.per_claim_limit`, and a claim-period rollup against `category.monthly_limit` -- buildable now.
- **Receipt-required-threshold enforcement** -- flag a line whose amount exceeds `category.requires_receipt_above`
  and has no `receipt` attached -- seen in: SAP Concur, Emburse Certify -- priority: Must -- buildable now.
- **Real-time policy check at entry (before submission)** -- Fyle checks while the expense is being created and
  can block/cap/route; Navan enforces policy at the point of booking -- priority: Should -- spine: a
  `ExpenseClaimLine.clean()`/`save()` check that sets a `policy_violation` boolean (soft flag, not a hard block, for
  v1) -- buildable now.
- **Warn vs. hard-block on violation (admin-configurable enforcement mode)** -- Zoho Expense lets admins choose
  warn-only or fully block submission -- priority: Differentiator -- deferred (v1 always warns/flags; a
  configurable block mode is a later refinement).
- **Claim-level violation rollup (count/flag surfaced to the approver)** -- Zoho Expense routes approval based on
  violation count -- priority: Should -- spine: a derived `has_violations`/`violation_count` on `ExpenseClaim`
  (computed from its lines, not stored authoritative data) -- buildable now.
- **Duplicate-expense detection** -- Fyle's built-in duplicate finder (same employee/date/amount/merchant), Ramp's
  fraud flagging -- priority: Should/Differentiator -- deferred (needs a cross-claim matching query; a simple
  same-employee+date+amount+merchant check could be added in a later pass).
- **AI/OCR-based fraud & policy audit** -- SAP Concur Detect & Audit, Ramp Policy Agent, Happay Smart Audit --
  priority: Differentiator -- integration/later (external AI service).
- **Cost-center/department-specific policy overrides** -- Zoho Expense -- priority: Later -- deferred (see
  3.34.1 above; v1 keeps one tenant-wide limit set per category).
- **Mileage / per-diem policy rates** -- Rydoo -- priority: Later -- deferred, coordinate with 3.35 Travel
  Management rather than duplicating in 3.34.

## Recommended 3.34 build scope (3 new models)

1. **`ExpenseCategory`** (`TenantOwned`, no numbering needed -- a small config master like `LeaveType`/
   `PayComponent`)
   - `name` (CharField), `code` (CharField, short, unique per tenant)
   - `description` (TextField, blank)
   - `per_claim_limit` (Decimal, null/blank) -- Zoho Expense / Fyle limit-rule research
   - `monthly_limit` (Decimal, null/blank) -- Zoho Expense limit-rule research
   - `requires_receipt_above` (Decimal, null/blank) -- SAP Concur / Emburse receipt-threshold research
   - `gl_account_hint` (FK `accounting.GLAccount`, `on_delete=SET_NULL`, null/blank) -- Ramp/Concur/Zoho GL-coding
     research; reuses the accounting spine as a hint, no posting logic
   - `is_active` (Boolean, default True)
   - Justified by: 3.34.1 Expense Categories bullet + the policy-limit inputs consumed by 3.34.5.

2. **`ExpenseClaim`** (`TenantNumbered`, `NUMBER_PREFIX = "ECL"` -- deliberately distinct from `crm.Expense`'s
   existing `"EXP"` prefix so the two number series never look interchangeable in the UI, even though
   `next_number()` is scoped per-model-per-tenant and would not actually collide)
   - `employee` (FK `hrm.EmployeeProfile`)
   - `title` (CharField) -- purpose/trip name
   - `period_start` / `period_end` (DateField, optional) -- claim period
   - `total_amount` (Decimal, `editable=False`) -- derived/recomputed from its lines' `amount` sum
   - `currency` (FK `accounting.Currency`, `SET_NULL`, null/blank) -- Expensify/Zoho/Concur multi-currency research
     (record-keeping only, no FX conversion this pass)
   - `status` (choices: `draft`, `submitted`, `manager_approved`, `approved`, `rejected`, `cancelled`,
     `reimbursed`) -- the two-stage approval design from 3.34.3
   - `manager_approver` / `manager_approved_at` -- stage-1 stamp (mirrors `_hr_request_approve`'s
     `approver`/`approved_at`)
   - `finance_approver` / `finance_approved_at` -- stage-2 stamp
   - `decision_note` (TextField, blank) -- rejection/cancellation reason, mirrors `LeaveRequest`/`AssetRequest`
   - `payment_method` (CharField choices, e.g. bank_transfer/payroll/cash/cheque), `payment_reference`
     (CharField, blank), `reimbursed_at` (DateTimeField, null/blank) -- 3.34.4 Reimbursement bullet
   - `has_violations` (Boolean, `editable=False`, derived rollup) -- 3.34.5 Policy Compliance bullet
   - `OPEN_STATUSES = ("draft", "submitted", "manager_approved")` for the shared edit/cancel/delete gating
   - Justified by: 3.34.2 Claims header, 3.34.3 Approval Workflow, 3.34.4 Reimbursement.

3. **`ExpenseClaimLine`** (`TenantOwned`, FK'd to `ExpenseClaim`)
   - `claim` (FK `ExpenseClaim`, `related_name="lines"`)
   - `category` (FK `ExpenseCategory`)
   - `expense_date` (DateField)
   - `merchant` (CharField, blank)
   - `description` (TextField, blank)
   - `amount` (Decimal)
   - `receipt` (FileField, `upload_to="hrm/expense_receipts/%Y/%m/"`) -- reuses the `InvestmentProof`/
     `_validate_upload` pattern (its own allowlist constants or reuse `ALLOWED_ONBOARDING_DOC_EXTENSIONS`/
     `MAX_ONBOARDING_DOC_BYTES`), with the same WARNING re: `Content-Disposition: attachment` +
     `X-Content-Type-Options: nosniff`
   - `policy_violation` (Boolean, `editable=False`) -- set by `clean()`/`save()` comparing `amount` against
     `category.per_claim_limit` and checking `receipt` presence against `category.requires_receipt_above`
   - `violation_reason` (CharField, blank, `editable=False`) -- short human-readable reason (e.g. "Exceeds
     per-claim limit", "Receipt required above $X")
   - Justified by: 3.34.2 line items + receipts, 3.34.5 Policy Compliance (the actual per-line check).

**Approval workflow implementation note:** extend the existing `_hr_request_submit/_cancel/_edit/_delete` helpers
as-is (they're status-agnostic beyond `OPEN_STATUSES`); add two new view actions
(`expenseclaim_manager_approve`, `expenseclaim_finance_approve`) modeled directly on `_hr_request_approve`/
`_hr_request_reject`, each self-approval-gated via `_is_own_hr_request`, each calling `write_audit_log`. A
`expenseclaim_mark_reimbursed` action (finance-only, requires `status="approved"`) stamps `payment_method`/
`payment_reference`/`reimbursed_at` and flips `status="reimbursed"`.

**Policy-check implementation note:** compute `policy_violation`/`violation_reason` in
`ExpenseClaimLine.save()` (or the form's `clean()`) on every save so the flag is always current; recompute
`ExpenseClaim.has_violations` as `any(line.policy_violation for line in self.lines.all())` alongside the existing
`total_amount` recompute. This is a **soft flag surfaced to the approver**, not a submission-blocking hard rule --
matches the "warn" mode most leaders default to, while leaving "block" mode as a deferred admin-configurable
enhancement.

## Deferred (later passes / integrations)

- **Receipt OCR / SmartScan-style auto-extraction** -- external AI/OCR service (Expensify, SAP Concur, Happay,
  Pleo, Brex all lead here) -- integration, not a single Django pass.
- **Corporate-card transaction feed + auto-reconciliation** -- Ramp, Brex, Pleo, Airbase, Concur -- requires a
  card-issuer API integration.
- **Mileage auto-calculation (map-based) and a dedicated per-diem engine** -- Rydoo's core differentiator --
  belongs with 3.35 Travel Management, not duplicated in 3.34.
- **Cash advance against a claim** -- SAP Concur, Rydoo, Happay -- NavERP.md scopes "Travel Advance"/"Travel
  Settlement" to 3.35, not 3.34; flagged as a cross-sub-module coordination point, not built here.
- **Duplicate-expense detection** -- Fyle's duplicate finder -- deferred; a same-employee/date/amount/merchant
  query could be added in a later refinement.
- **Multi-currency FX conversion** -- Expensify/Zoho/Concur auto-convert to home currency -- v1 only stores a
  `currency` FK for record-keeping; live conversion is deferred.
- **Configurable warn-vs-block enforcement mode** -- Zoho Expense's admin toggle -- v1 always soft-flags.
- **Rule-based / N-level / conditional approval routing** (by amount, department, violation count, and/or logic) --
  Zoho Expense, Airbase, Navan, Ramp Policy Agent -- v1 ships the lean fixed 2-stage
  manager-then-finance machine described above; a dynamic approval-step model is a later enhancement if a tenant
  needs more than 2 levels.
- **Auto-approve in-policy / under-threshold claims** -- Brex, Emburse, Ramp Policy Agent -- deferred automation;
  v1 always routes to a human.
- **Reimbursement batch/payment-run bundling** -- SAP Concur, Zoho Expense -- deferred AP-style batching.
- **Payroll-payout integration** -- pushing `ExpenseClaim.total_amount` into
  `PayComponent(component_type="reimbursement")` / `FinalSettlement.reimbursement_amount` -- explicitly deferred
  per the brief; 3.34 only tracks the claim's own `payment_reference`/`reimbursed_at`.
- **AI/OCR fraud & policy audit (Concur Detect & Audit, Ramp Policy Agent, Happay Smart Audit)** -- integration/
  later.
- **Department/branch/cost-center-specific policy limit overrides** -- Zoho Expense -- v1 ships one tenant-wide
  limit set per category.
- **GL posting / journal entry creation from a reimbursed claim** -- `gl_account_hint` is stored on
  `ExpenseCategory` as a coding hint only; actual `JournalEntry`/`JournalLine` posting is an accounting-module
  integration, not built in 3.34.
