# Research — Module 3: HRM Sub-module 3.17 Payout & Reports (payout-reports)

## Scope note — the disbursement + reconciliation layer, NOT a second payroll engine
This research covers the **money-movement tracking and reporting** layer that sits on top of already-built
payroll (3.13 Salary Structure, 3.14 Payroll Processing, 3.15 Statutory Compliance, 3.16 Tax & Investment). It
explicitly does **not** re-model anything that already exists, and it explicitly does **not** post anything new
to the general ledger:

- **`hrm.PayrollCycle`** (`PRC-#####`, 3.14) — the operational pay-period run header; `status` reaches `locked`
  once approved, at which point its `Payslip`s are immutable and it already carries a
  `accounting_payroll_run` FK. A payout batch is generated **from a locked `PayrollCycle`** — never from a
  draft one.
- **`hrm.Payslip`** (`PSL-#####`, 3.14) — one per employee per cycle, already carrying the derived `net_pay`,
  the `on_hold`/`hold_reason`/`released_at` fields (held payslips are excluded from disbursement), and the FK
  to `employee`. **3.17 reuses `Payslip.net_pay` as the amount to disburse — it is never re-entered or
  re-derived.**
- **`hrm.PayslipLine`** (3.14) — the per-component snapshot; not touched by 3.17 (no new component lines are
  needed for disbursement).
- **`hrm.EmployeeProfile`** (3.1) — already has `bank_name` / `bank_account` / `bank_routing`, each with a
  `masked_*()` accessor (`masked_bank_account()`, `masked_bank_routing()`) and existing redaction in
  `AuditLog.changes` (`core.crud._SENSITIVE_AUDIT_FIELDS`). **3.17 reuses these three fields as the
  disbursement destination — no new employee/bank-master table.** A payout line SNAPSHOTS the masked/last-4
  values at generation time (mirroring the `PayslipLine` snapshot convention from 3.14), so a later profile
  edit never rewrites a historical payment record, and the full account number is never duplicated into a
  second table.
- **`accounting.PayrollRun`** (`PRUN-#####`) — the GL-side financial aggregate, already linked from
  `PayrollCycle.accounting_payroll_run`. **3.17 posts nothing new to the GL.** Per lesson L29 (already applied
  in 3.14/3.15/3.16), money-movement tracking (who got paid, how much, via which bank file, whether it
  succeeded/failed/was returned) is bookkeeping *about* a payment, not a *ledger entry* — the JournalEntry for
  the payroll expense/net-pay-payable was already posted (or will be posted) through `accounting.PayrollRun` /
  `payroll_run_post`. Reconciling a bank statement against a payout batch is a **status-matching** exercise on
  `PayoutPayment` rows, not a new Dr/Cr entry.

3.17 must therefore be a **batch-generation + payment-status-tracking + distribution-tracking + reconciliation**
layer:
1. **Bank Integration** — generate a disbursement batch (the set of net-pay amounts to be paid) from a locked
   cycle's non-held payslips, track bank-file metadata (format/bank/reference), and track direct-deposit
   status per employee (paid/failed/returned/on-hold).
2. **Payslip Generation** — track *distribution* status of the already-generated `Payslip` (sent/viewed/
   downloaded) — the PDF rendering + SMTP delivery mechanics are external/deferred, but the tenant needs to
   know who has and hasn't received/opened their payslip.
3. **Payment Register** — a report/view over the batch + its payments (headcount, total disbursed, by-status
   breakdown) — no new model, it is a read query over `PayoutBatch`/`PayoutPayment`.
4. **Reconciliation** — match a batch's expected payments against imported bank-statement lines, flagging
   mismatches/failures/returns so a re-payment cycle can be initiated.

## Leaders surveyed (with source links)
1. **Keka** — India HRIS/payroll; one-click salary disbursal wizard (Payroll → Settings → Payment Automation)
   that shows the disbursal account (account number/IFSC), generates bank-specific NEFT/CSV transfer files
   matching major banks' (ICICI/HDFC/Axis) upload formats, and supports bulk payslip download/print for
   employees without portal/email access — [Processing salary through payment automation](https://help.keka.com/admin/processing-salary-through-automation), [Can Keka integrate directly with corporate banks?](https://help.keka.com/hc/en-us/articles/39946832526993-Can-Keka-integrate-directly-with-corporate-banks-for-automated-salary-disbursal-or-is-manual-file-upload-always-required), [Managing employees' payslips](https://help.keka.com/admin/managing-employees-payslips), [How to manage payments and download bank statements](https://help.keka.com/admin/knowledge/how-to-manage-payments-and-download-bank-statements)
2. **greytHR** — India HRMS/payroll; a "Bank Transfer Advice" report (filterable by bank/type), a dedicated
   "Payroll Transfer Reconciliation (Payment Type-Wise)" report, and a "Payroll Reconciliation" report
   comparing current vs. prior month's processed salary for discrepancy detection; supports Direct Debit /
   Bank Transfer / Cheque / DD disbursement modes — [Access payroll payout and payroll control reports](https://admin-help.greythr.com/admin/answers/grnypev2tjg_pncoyt8bta/), [Salary Disbursement](https://www.greythr.com/hr-garden/salary-disbursement/), [Manage employees' direct salary transfer](https://admin-help.greythr.com/admin/answers/122326864/)
3. **Zoho Payroll** — SMB/India-US payroll; explicit per-payout status tracking (`Initiated` → `Pending` →
   `Successful`/`Failed`) refreshed within 30 minutes, a `Re-initiate Payment` action for failed direct-deposit
   payments (e.g. after correcting bank details), and a "record payments done through other modes" fallback
   (cash/cheque/manual bank transfer) when direct deposit itself is unavailable/fails — [Direct Deposit for Organizations](https://www.zoho.com/us/payroll/help/employer/direct-deposit/organizations.html), [Edit Payment Details](https://www.zoho.com/in/payroll/kb/direct-deposit/edit-payment-details.html), [Recording Payments done through other modes](https://www.zoho.com/in/payroll/kb/employer/direct-deposit/recording-diff-payment-mode.html)
4. **RazorpayX Payroll** — India payroll/banking; Payroll↔Current-Account integration explicitly marketed as
   making "transactions and reconciliation easier," with documented failure causes for fund transfers
   (non-working-day initiation, non-whitelisted source account, incorrect bank details) — [RazorpayX Payroll Integration with Current Account](https://razorpay.com/docs/payroll/integrations/current-account/), [RazorpayX Payroll FAQs](https://razorpay.com/docs/payroll/faqs/)
5. **Darwinbox** — enterprise HCM/payroll; banking-integration-driven disbursement (direct deposit or other
   preferred payment options) immediately followed by digital payslip generation, with automated recordkeeping/
   audit trails specifically framed as easing reconciliation, reporting, and audits — [Payroll Automation Process](https://darwinbox.com/blog/payroll-automation-process-from-attendance-to-payslips), [Darwinbox Payroll product page](https://darwinbox.com/en-us/products/payroll)
6. **Zimyo** — India (+ Middle East/WPS) HRMS; downloadable "bank sheet" Excel file with employee payment
   details + account info for submission to the bank, a dedicated "Payout" digital-disbursement feature ("a
   few clicks" to release payments), and payslip email-distribution with an explicit admin
   select-employees-then-email confirmation flow — [Payouts | Digital Salary Payment Wallet](https://help.zimyo.com/payroll/payouts/), [How to notify employees of their payslip in their mail](https://help.zimyo.com/docs/how-to-notify-employees-of-their-payslip-in-their-mail/), [Payroll Software (WPS Compliant)](https://www.zimyo.me/payroll-software/)
7. **HROne** — India payroll/HCM; a formal "salary bank advice statement" concept (employee name/ID, bank
   account number, PF details, wage amount sent to the disbursing branch), plus ESS-portal payslip publishing
   and password-protected mobile-app payslip/Form-16 access as the primary distribution channel (no manual
   handout) — [Payroll Solution](https://hrone.cloud/hr-software/payroll-solution/), [Salary Slip Generator](https://hrone.cloud/tools/salary-slip-generator/)
8. **saral PayPack** (Relyon Softech) — India payroll/statutory specialist; direct salary/reimbursement update
   against imported bank statements, one-click payslip generation emailed as a secure PDF attachment, and an
   audit-trail module explicitly positioned to support reconciliation/audit of every payroll-data change —
   [Saral PayPack](https://saralpaypack.com/), [Best Payroll Management System](https://saral.pro/payroll-software/)
9. **Gusto** — US SMB payroll; an employee-facing "pay tracker" showing real-time payment status
   (direct-deposit vs. check, expected arrival by end of payday), a payday confirmation email that explicitly
   states submission ≠ funds-arrived (managing expectations around settlement lag), and full payslip/paystub
   history retained for the employee's account lifetime — [Track your pay and troubleshoot payment issues](https://support.gusto.com/article/100010018100000/track-your-pay-and-troubleshoot-payment-issues-for-us-employees), [Direct deposit payment speeds in Gusto](https://support.gusto.com/article/999752211000000/direct-deposit-payment-speeds-in-gusto), [View paystubs and upcoming paydays](https://support.gusto.com/article/100010018100000/View-paystubs-and-upcoming-paydays-for-US-employees)
10. **ADP Workforce Now** — enterprise payroll; per-employee/per-account direct-deposit profile management
    (People → Pay → Pay Profile → Direct), bank **prenote** verification (a small test transaction validating a
    new account before real deposits begin), a documented "Bank Reconciliation" standard report, and a
    multi-year retention requirement for direct-deposit banking-authorization records — [Direct Deposit API Guide](https://marketplace-cdn.adp.com/dev-portal/pdf/protected/Direct_Deposit_API_Guide_for_ADP_Workforce_Now), [ADP Workforce Now Standard Reports Guide](https://www.minotnd.gov/AgendaCenter/ViewFile/Item/5854?fileID=19092)
11. **Deel** — global payroll/EOR; a payroll-cycle completion definition of "funding received + payslips
    published + all payouts complete," a Payment Tracker showing remaining steps to full disbursement, and
    payslips deliberately released 1–3 days AFTER payment lands (payment-first, document-after ordering) —
    [Frequently Asked Questions About Deel Payroll (Managed)](https://help.letsdeel.com/hc/en-gb/articles/9081369803153-Frequently-Asked-Questions-About-Global-Payroll), [How to Review and Approve Global Payroll Packages](https://help.letsdeel.com/hc/en-gb/articles/18940617896593-How-to-Review-and-Approve-Global-Payroll-Payroll-Packages), [When Do I Get Paid?](https://help.letsdeel.com/hc/en-gb/articles/4413976907025-When-Do-I-Get-Paid)

(General NACH/ACH banking-rail research — [NACH and Payments Glossary](https://www.terra-insight.com/insights/nach-payments-glossary-india/), [ACH (NACHA) File Format Specifications](https://www.treasurysoftware.com/ach/ach-specifications.aspx) — corroborates the return-file/UTR/trace-number reconciliation model described below; these are file-format/rail references, not a product per se, and are not counted in the ~10 product list.)

## Feature catalog by sub-module

### 3.17.a Bank Integration — bank file generation, direct deposit
- **Batch generation from a finalized/locked payroll run** — the disbursement set is derived from the
  payslips of one locked cycle, excluding on-hold employees · seen in: Keka (payment automation runs after
  payroll is closed), Darwinbox ("once the final calculation is done... payments are made"), Deel (funding
  happens after package approval) · priority: table-stakes · spine: new table `PayoutBatch`, `cycle` FK →
  `hrm.PayrollCycle` (must be `is_locked`), generated from `cycle.payslips.exclude(on_hold=True)` · buildable
  now
- **Bank-file / NEFT / NACH / ACH format generation per destination bank** — a bank-specific CSV/fixed-width
  layout (ICICI/HDFC/Axis-style templates, or a generic NACH/ACH batch) that the tenant uploads to their
  banking portal · seen in: Keka (bank-specific CSV templates matching major Indian banks), greytHR
  ("generate bank transfer statements in a specified downloadable format... simply select your bank"), Zimyo
  (downloadable "bank sheet" Excel) · priority: table-stakes (in the market) · spine:
  `PayoutBatch.bank_file_format` choice + `bank_name` + a generated/exported file reference · **buildable now
  for the DATA (batch header + per-payment rows ready to export); the actual bank-specific file-format
  writer/template is integration/later** (consistent with the "PDF rendering deferred" pattern from 3.14-3.16)
- **Disbursal/source bank-account reference shown before initiating payment** — the paying (tenant) account
  number/IFSC surfaced on the batch before disbursing · seen in: Keka (Payment Automation tab shows disbursal
  account/IFSC) · priority: common · spine: `PayoutBatch.source_bank_name` / `source_account_last4` (or a FK
  to a future tenant bank-account master — out of scope this pass, store as plain fields) · buildable now
- **Direct-deposit / API-driven payment initiation distinct from manual file upload** · seen in: Keka (FAQ:
  "does Keka integrate directly with banks, or is manual file upload always required?" — both models exist in
  market), RazorpayX (RazorpayX Current Account ↔ Payroll integration) · priority: differentiator (live API
  integration) · integration/later — this pass models the batch/payment records that either path (manual file
  or live API) would produce; the live bank-API call itself is out of a single Django pass
- **Per-employee payment status lifecycle** (`Initiated`/`Pending`/`Successful`/`Failed`, refreshed as the
  bank confirms) · seen in: Zoho Payroll (explicit Initiated→Pending→Successful/Failed states, ~30-min refresh)
  · priority: table-stakes · spine: `PayoutPayment.status` choices `pending`/`processing`/`paid`/`failed`/
  `returned`/`on_hold` · buildable now (status field + manual/API-driven transitions; the live status-refresh
  webhook/poll is integration/later)
- **Bank-account verification / prenote before first payment** — a test transaction (or an explicit
  "verification pending" state) validates a new/changed bank account before a real deposit is attempted; a
  changed account re-enters a multi-day verification window · seen in: ADP (prenote), Zoho Payroll (account
  edits trigger 2–3 business days re-verification) · priority: differentiator · spine: could be modeled as an
  additional `PayoutPayment.status` value (`pending_verification`) or left to a future prenote sub-flow —
  **recommendation: not a v1 field, note as a fast-follow status** · integration/later
  (bank-side verification handshake)
- **Failed-payment correction + re-initiation** — edit the destination bank details, then re-trigger payment
  for just the failed employee(s) rather than the whole batch · seen in: Zoho Payroll ("Re-initiate Payment"
  button after editing bank details for a failed deposit) · priority: table-stakes · spine:
  `PayoutPayment.status='failed'` → a re-payment action creates a follow-up `PayoutPayment` (or a new
  `PayoutBatch` scoped to just the failed employees) referencing the original as `retry_of` — **buildable now**
  as a status transition + optional self-referencing FK
- **Alternate/manual payment-mode recording as a fallback** (cash, cheque, manual bank transfer when direct
  deposit isn't used/available) · seen in: Zoho Payroll ("record payments done through other modes"), greytHR
  (Direct Debit / Bank Transfer / Cheque / DD as disbursement modes) · priority: common · spine:
  `PayoutPayment.payment_method` choices `bank_transfer`/`neft`/`nach`/`cheque`/`cash`/`other` · buildable now
- **Multi-day settlement-cycle awareness** (NEFT reflects in ~30-60 min; NACH credit settles T+1; a payday
  email confirms submission, not arrival) · seen in: Keka (NEFT ~30-60 min), Gusto (payday email ≠ funds
  arrived, "by end of payday" per bank), NACH-rail reference (T+1 settlement) · priority: common · spine:
  `PayoutPayment.initiated_at` vs. `paid_on`/`settled_on` — two timestamps rather than one, so the UI can show
  "submitted" distinctly from "confirmed landed" · buildable now (fields only, no scheduler/timer logic
  needed)
- **WPS/country-specific mandatory salary-file formats** (UAE Wage Protection System SIF files) · seen in:
  Zimyo (auto-generates WPS SIF files for UAE) · priority: differentiator (market-specific) · integration/later
  — out of scope for this India/NavERP-generic pass; `bank_file_format` choices leave room for a `wps_sif`
  value later without a schema change

### 3.17.b Payslip Generation — digital payslips, email distribution
- **Digital payslip generation immediately tied to the payroll run** (PDF, standardized layout) · seen in:
  HROne (auto-generated standardized-format payslips), saral PayPack (one-click payslip generation) · priority:
  table-stakes (in the market) · integration/later for the actual PDF rendering — **already explicitly
  deferred in 3.14/3.15/3.16 research**; `hrm.Payslip` (3.14) is the data source, this pass tracks
  DISTRIBUTION of that data, not the document renderer
- **Bulk email distribution to employees, with an explicit admin action/confirmation** (select employees →
  send) · seen in: Zimyo ("select employees... email payslips through a confirmation process"), saral PayPack
  ("emailed to the employee as a secure PDF attachment") · priority: table-stakes · spine: new table
  `PayslipDistribution` (1:1 or 1:many per `Payslip`), `sent_at`, `sent_to_email` (snapshotted work/personal
  email at send time) · buildable now (the tracking row + a "mark as sent" action); the actual SMTP dispatch +
  PDF attachment generation is integration/later
- **Self-service portal download as the primary channel** (no manual handout needed) · seen in: Keka ("once
  released, employees can access and download from their profile"), HROne (ESS portal publish), Gusto
  (lifetime paystub access in the employee's account) · priority: table-stakes · spine:
  `PayslipDistribution.viewed_at` / `downloaded_at` timestamps, set when the employee's own portal view/
  download action fires · buildable now (the tracking fields; the portal UI itself is a standard detail-page
  view already implied by existing `Payslip` CRUD patterns)
- **Read/download receipt tracking distinct from send** (sent vs. viewed vs. downloaded as three separate
  signals) · seen in: general pattern across Zimyo/Keka/HROne (publish → employee opens/downloads
  independently of when HR sent/released it) · priority: common · spine:
  `PayslipDistribution.status` choices `pending`/`sent`/`viewed`/`downloaded`/`failed` plus the three
  timestamp fields · buildable now
- **Bulk print/physical distribution fallback** for employees without computer/email access · seen in: Keka
  ("bulk download, print, and distribute physical copies") · priority: common · spine:
  `PayslipDistribution.delivery_channel` choices `email`/`portal`/`print` · buildable now (channel flag; the
  print/merge mechanics are integration/later)
- **Password-protected payslip access** (mobile app / secure PDF) · seen in: HROne (password-protected
  mobile-app payslip access), saral PayPack ("secure PDF attachment") · priority: differentiator ·
  integration/later — a PDF-encryption/secure-delivery concern layered on the (deferred) PDF renderer, not a
  data-model concern for this pass
- **Payslip released only after payment is confirmed, not before** — a deliberate ordering where the payslip
  document is withheld until funding/payment completes · seen in: Deel (payslips released 1–3 days AFTER
  payment lands) · priority: differentiator · spine: a soft business-rule the distribution action can enforce
  (gate `PayslipDistribution` creation/send on `PayoutPayment.status='paid'`) rather than a new field · buildable
  now as a workflow guard, not a schema element
- **Form 16 / annual tax-document distribution** — already modeled separately in 3.16 (`StatutoryReturn`
  scheme=`tds_form16`); not re-modeled here, but the same `PayslipDistribution`-style send/view/download pattern
  could extend to it in a later pass · priority: n/a to 3.17 · deferred cross-reference only

### 3.17.c Payment Register — payment summary, batch reports
- **Batch-level summary report** (headcount, total gross disbursed, count/amount by status, by bank/payment
  method) · seen in: greytHR (Bank Transfer Advice report, filterable by bank/type), Zimyo (bank-sheet Excel
  export) · priority: table-stakes · spine: **no new model** — a report/view aggregating `PayoutPayment` rows
  grouped by `PayoutBatch`, mirroring the existing `PayrollCycle._totals()` cached-aggregate convention ·
  buildable now
- **Bank-advice-style export** (one row per employee: name, account last-4, IFSC/routing, amount, reference)
  ready for upload or record-keeping · seen in: greytHR (Bank Transfer Advice), HROne (salary bank advice
  statement: employee name/ID, bank account number, wage amount) · priority: table-stakes · spine: same
  report, rendered as a downloadable table/CSV over `PayoutPayment` (masked account numbers per the existing
  `masked_bank_account()` display convention — never render the full number) · buildable now
- **Payment-type/mode-wise grouping** (bank transfer vs. cheque vs. cash subtotals) · seen in: greytHR
  ("Payroll Transfer Reconciliation (Payment Type-Wise)"), · priority: common · spine: group-by
  `PayoutPayment.payment_method` in the same report · buildable now
- **Period-over-period discrepancy view** (this month's payroll vs. last month's processed salary, flagging
  unusual deltas) · seen in: greytHR ("Payroll Reconciliation" report comparing current vs. prior month) ·
  priority: differentiator · integration/later-ish — a comparison report is buildable as a query across two
  `PayoutBatch`/`PayrollCycle` periods without a new model, but the anomaly-flagging logic is a nice-to-have,
  not core v1

### 3.17.d Reconciliation — bank reconciliation, error/exception reports
- **Import a bank statement / return file and match lines against expected payments** — the bank's actual
  debit/credit lines (with a UTR/reference number) are matched one-to-one against the batch's expected
  `PayoutPayment` rows · seen in: NACH-rail convention (presentation batch file → return file → bank-statement
  credit, three-way match), ADP (a documented "Bank Reconciliation" standard report), RazorpayX (Payroll↔
  Current-Account integration "makes... reconciliation easier") · priority: table-stakes · spine: new table
  `BankReconciliation` (`BRC-`), `batch` FK → `PayoutBatch`, holding the imported statement-line data (or a
  lightweight matched/unmatched line list) · buildable now (manual entry/CSV import of statement lines +
  matching UI); a live bank-statement-API feed is integration/later
- **Transaction reference / UTR / trace number as the match key** · seen in: NACH/ACH-rail convention (UTR /
  NACH batch reference; ACH trace number appended to every line, used to track issues) · priority:
  table-stakes · spine: `PayoutPayment.transaction_reference` (the bank-assigned UTR/trace number, populated
  once the payment is initiated/confirmed) — the field the reconciliation match runs against · buildable now
- **Return-reason / failure-reason codes on unmatched or failed lines** · seen in: NACH-rail convention (a
  return file carries a bank reason code for why a debit/credit couldn't be processed), RazorpayX (documented
  failure causes: non-working-day initiation, non-whitelisted source account, incorrect bank details) ·
  priority: common · spine: `PayoutPayment.failure_reason` (free text or a small choices list) · buildable now
- **Exception/error report** — a filtered view surfacing only failed/returned/mismatched payments for
  follow-up (re-initiate, correct bank details, escalate) · seen in: Zoho Payroll (failed-status filter feeding
  the re-initiate action), greytHR (reconciliation report exists specifically to surface discrepancies) ·
  priority: table-stakes · spine: **no new model** — a filtered report/view over `PayoutPayment` where
  `status in (failed, returned)` or over `BankReconciliation`'s unmatched lines · buildable now
- **Reconciliation status/workflow at the batch level** (draft/in-progress/reconciled/discrepancy) distinct
  from each payment's own status · seen in: general market convention (a reconciliation run is its own object
  with its own completion state, separate from each line's match result) · priority: common · spine:
  `BankReconciliation.status` choices `pending`/`in_progress`/`reconciled`/`discrepancy` · buildable now
- **Audit trail of every reconciliation action** (who imported the statement, who marked a line matched/
  resolved, when) · seen in: saral PayPack (audit-trail module explicitly framed around reconciliation/audit
  support) · priority: common · spine: reuse the existing `core.AuditLog` (already wired to all CRUD `crud_*`
  views per house convention) rather than a bespoke audit table — no new model needed · buildable now

## Recommended build scope (this pass — 4 models)

- **`PayoutBatch`** [`POB-`, `TenantNumbered`] — the disbursement-run header, generated from one locked
  `PayrollCycle`, justified by: Keka's payment-automation wizard, Darwinbox/Deel's "payment happens after
  approval" ordering, greytHR's bank-advice report needing a batch to summarize.
  - `NUMBER_PREFIX = "POB"`.
  - `cycle` — `models.ForeignKey("hrm.PayrollCycle", on_delete=models.PROTECT, related_name="payout_batches")`
    — must be `cycle.is_locked` before a batch can be generated (validated in `clean()`/the generate action).
  - `status` choices `draft` / `approved` / `disbursed` / `partially_disbursed` / `reconciled` — mirrors the
    `PayrollCycle` state-machine convention already used in 3.14; `partially_disbursed` covers the common case
    where some payments succeed and others fail/need retry.
  - `bank_file_format` choices `neft` / `nach` / `ach` / `manual` / `other` — Bank Integration (Keka's
    bank-specific templates, NACH/ACH-rail research).
  - `source_bank_name`, `source_account_last4` (CharField, masked — never store/display the full disbursing
    account) — Keka's "disbursal account" surfaced before initiating payment.
  - `generated_at`, `generated_by`, `approved_at`, `approved_by`, `disbursed_at` — audit trail mirroring the
    `PayrollCycle.submitted_by/approved_by` maker/checker pattern.
  - Derived properties: `headcount`, `total_amount`, `paid_count`/`paid_amount`, `failed_count`,
    `on_hold_count` (aggregated from `PayoutPayment`, cached per-instance like `PayrollCycle._totals()`) —
    feeds the Payment Register report directly.
  - `unique_together (tenant, cycle)` — one payout batch per cycle (regenerating replaces/updates rather than
    duplicating, matching the "regenerate while draft" convention from 3.14).

- **`PayoutPayment`** [`TenantOwned`, no own number — child of `PayoutBatch`] — one row per disbursed
  employee, justified by: Zoho Payroll's per-payment status lifecycle, HROne's bank-advice-statement line
  (employee/account/amount), the NACH/ACH UTR-matching convention.
  - `batch` — `models.ForeignKey("hrm.PayoutBatch", on_delete=models.CASCADE, related_name="payments")`.
  - `payslip` — `models.ForeignKey("hrm.Payslip", on_delete=models.PROTECT, related_name="payout_payments")`
    — the source of the amount; **`net_pay` is read from here, never re-entered.**
  - `employee` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name=
    "payout_payments")` — denormalized off `payslip.employee` for simpler list/filter queries (matches the
    `Payslip.employee` direct-FK convention already used alongside `Payslip.cycle`).
  - `net_amount` (decimal, snapshotted from `payslip.net_pay` at batch-generation time — so a later payslip
    correction in a NEW cycle never silently changes a historical payment record).
  - `bank_name_snapshot`, `bank_account_last4_snapshot`, `bank_routing_snapshot` (CharField, masked copies of
    `EmployeeProfile.bank_name` / `masked_bank_account()` / `masked_bank_routing()` at generation time) — the
    disbursement-destination snapshot; **never store/copy the full unmasked account number** (mirrors the
    existing `masked_bank_account()` house convention and the `AuditLog` redaction already in place).
  - `payment_method` choices `bank_transfer` / `neft` / `nach` / `ach` / `cheque` / `cash` / `other` — Zoho
    Payroll / greytHR's alternate-mode recording.
  - `status` choices `pending` / `processing` / `paid` / `failed` / `returned` / `on_hold` — Zoho Payroll's
    Initiated/Pending/Successful/Failed lifecycle, extended with `returned` (NACH-rail return-file concept)
    and `on_hold` (an employee whose `Payslip.on_hold=True` is included in the batch as a zero-action row for
    completeness/audit, but never actually paid).
  - `transaction_reference` (CharField, blank — the bank-assigned UTR/trace number, the reconciliation match
    key per NACH/ACH convention).
  - `initiated_at`, `paid_on` (two timestamps, not one — Gusto's "submitted ≠ arrived" distinction, NACH's T+1
    settlement lag).
  - `failure_reason` (TextField, blank) — RazorpayX's documented failure-cause list (non-working-day,
    non-whitelisted account, incorrect bank details), NACH's return-reason-code convention.
  - `retry_of` — `models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name=
    "retries")` — Zoho Payroll's "Re-initiate Payment" pattern: a corrected retry references the original
    failed attempt rather than mutating it in place, preserving the failure history.
  - `unique_together (tenant, batch, payslip)` — one payment row per payslip per batch (a retry is a new row
    via `retry_of`, not an edit of the failed one).

- **`PayslipDistribution`** [`TenantOwned`, 1:1 with `hrm.Payslip`] — payslip delivery-tracking, justified by:
  Zimyo's send-confirmation flow, Keka/HROne's portal-download-as-primary-channel, Gusto's lifetime-access
  paystub history, Deel's payment-before-payslip release ordering.
  - `payslip` — `models.OneToOneField("hrm.Payslip", on_delete=models.CASCADE, related_name="distribution")`.
  - `delivery_channel` choices `email` / `portal` / `print` — Keka's bulk-print fallback, HROne's ESS-portal
    publish, Zimyo's email flow.
  - `status` choices `pending` / `sent` / `viewed` / `downloaded` / `failed` — the sent→viewed→downloaded
    signal chain common across Keka/HROne/Zimyo.
  - `sent_to_email` (EmailField, blank — snapshot of `employee.work_email` or `personal_email` at send time,
    so a later profile email change doesn't rewrite delivery history).
  - `sent_at`, `viewed_at`, `downloaded_at` (nullable datetimes) — the three independent signals.
  - `sent_by` — `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)`
    — audit trail for the bulk-send admin action (Zimyo's "select employees → confirm → send").
  - Created lazily (get-or-create) when a `Payslip` is generated, defaulting to `status='pending'`,
    `delivery_channel='portal'` — the portal-download path needs no explicit "send" action at all (Keka/Gusto
    convention: it is simply available once released).

- **`BankReconciliation`** [`BRC-`, `TenantNumbered`] — matches a batch's payments against an imported bank
  statement, justified by: the NACH/ACH three-way-match convention (presentation file → return file → bank
  statement), ADP's "Bank Reconciliation" standard report, RazorpayX's Payroll↔Current-Account reconciliation
  framing, greytHR's dedicated reconciliation report.
  - `NUMBER_PREFIX = "BRC"`.
  - `batch` — `models.ForeignKey("hrm.PayoutBatch", on_delete=models.PROTECT, related_name="reconciliations")`.
  - `statement_date` (DateField — the bank statement's as-of date).
  - `status` choices `pending` / `in_progress` / `reconciled` / `discrepancy` — the reconciliation run's own
    lifecycle, distinct from each `PayoutPayment.status`.
  - `matched_count`, `matched_amount`, `unmatched_count`, `unmatched_amount` (derived/cached aggregates,
    recomputed when statement lines are matched — mirrors the `PayoutBatch`/`PayrollCycle._totals()`
    cached-aggregate convention).
  - `statement_reference` (CharField, blank — the bank's own statement/file reference number).
  - `reconciled_by`, `reconciled_at` — audit/sign-off fields, matching the `PayrollCycle.approved_by/
    approved_at` pattern.
  - `notes` (TextField, blank).
  - A lightweight matching mechanism: rather than a full second child-table of imported statement lines (which
    would be a 5th model), **v1 matches directly against `PayoutPayment.transaction_reference` +
    `PayoutPayment.status`** — a reconciliation "run" flips matched payments to confirm `paid`/`settled` and
    flags unmatched/mismatched ones by setting `failure_reason` and leaving `status='failed'`/`'returned'`.
    **Recommendation: do NOT add a separate `BankStatementLine` model in this pass** — store the imported
    statement rows as a simple structured note/JSON on `BankReconciliation` (or handle import as an
    ephemeral upload processed row-by-row against existing `PayoutPayment`s) rather than persisting a
    duplicate ledger of bank lines; revisit only if a later pass needs to keep the raw statement for audit
    beyond what `PayoutPayment.transaction_reference` + `BankReconciliation`'s aggregates already preserve.

**Payment Register is a report, not a model** — implemented as a view/report page aggregating `PayoutBatch` +
`PayoutPayment` (by status, by payment method, by bank), matching the "no new model" pattern already used for
the Compliance Calendar in 3.15's research.

## Deferred (later passes / integrations)
- **Bank-specific file-format writers** (the exact NEFT/NACH/ACH/WPS-SIF CSV/fixed-width layouts per bank/
  country) — Keka's bank-specific templates, Zimyo's WPS SIF generator; this pass stores the batch + payment
  rows needed to generate them, not the format writer itself.
- **Live bank-API integration for payment initiation** (RazorpayX Current Account, Keka's "direct bank
  integration" option) — external API integration, out of a single Django pass; `PayoutPayment.status`
  transitions are modeled as admin/manual actions in v1, wireable to a live API callback later without a
  schema change.
- **Bank-account prenote / multi-day verification workflow** (ADP prenote, Zoho Payroll's 2–3-day
  re-verification after an account edit) — structurally could become a `pending_verification` status value;
  not built as its own workflow in v1.
- **Payslip PDF rendering + secure/password-protected delivery** — consistent with the deferral already noted
  in 3.14/3.15/3.16 research; `PayslipDistribution` tracks the send/view/download SIGNAL, not the document
  itself.
- **Live bank-statement feed / API-based auto-reconciliation** — v1 assumes a manual/CSV-driven statement
  import matched against `PayoutPayment.transaction_reference`; a live feed is integration/later.
- **A dedicated `BankStatementLine` persistence model** — considered and explicitly NOT added in this pass (see
  `BankReconciliation` note above) to keep the build at 4 models; revisit if raw-statement audit retention
  becomes a hard requirement.
- **Period-over-period payroll-cost anomaly/discrepancy detection** (greytHR's Payroll Reconciliation
  month-over-month compare) — buildable as a query across two periods without a new model; the
  anomaly-flagging logic itself is a nice-to-have, not core v1.
- **WPS/country-specific mandatory formats beyond India** (UAE SIF, other GCC wage-protection systems) — out
  of scope for this India-centric pass; `PayoutBatch.bank_file_format` choices leave room to extend later.
- **Form 16 / annual tax-document distribution tracking** — 3.16's `StatutoryReturn` (scheme=`tds_form16`)
  already tracks that document's filing workflow; extending the `PayslipDistribution`-style send/view/download
  pattern to it is a natural future enhancement, not part of this pass.
- **Automatic re-initiation / retry scheduling** (auto-retry a failed payment after N days) — v1 supports a
  manual retry via `PayoutPayment.retry_of`; an automated retry scheduler is a fast-follow, not blocking.
