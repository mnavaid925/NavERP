# Research — Sub-module 8.10: Incentive Compensation Management (Module 8 — Sales Management System, `apps/sales`)

> Phase 1 output. Target: **8.10 Incentive Compensation Management**. NavERP.md 8.10 = the five feature bullets reproduced verbatim in §2. All five are addressed in full.
> This research grounds 8.10 against verified as-built code in `apps/sales`, `apps/crm`, `apps/scm`, `apps/accounting`, and `apps/hrm`, and synthesizes specialized capabilities from 9 commercial market leaders.

---

## 1. Repo state checked first

### 1.1 Sibling sub-modules built so far in Module 8 (`apps/sales`)
Verification via `apps/core/navigation.py` `LIVE_LINKS` and model packages:
- **8.1 Lead Management** (`LIVE_LINKS["8.1"]`): `LeadScoreEvent`, `LeadQualification`, `LeadRoutingRule`, `LeadNurtureEnrollment` (`LNE-`).
- **8.2 Opportunity & Pipeline Management** (`LIVE_LINKS["8.2"]`):
  * `Pipeline` (`PIPE-`), `PipelineStage`.
  * `OpportunityPipelinePlacement`, `OpportunityTeamMember`.
  * `CompetitorProfile` (`CMP-`), `OpportunityCompetitor`.
  * `WinLossReason` (`WLR-`), `OpportunityOutcome` (`OUT-`).
- **8.3 Contact & Account Management** (`LIVE_LINKS["8.3"]`): `AccountClassification`, `AccountPlan` (`ACPL-`), `AccountStakeholder`, `PartyEnrichmentEvent`.
- **8.4 Sales Forecasting** (`LIVE_LINKS["8.4"]`): `ForecastPeriod` (`FCP-`), `ForecastSubmission` (`FCS-`), `ForecastAdjustment` (`FAD-`), `ForecastScenario` (`FSC-`).
- **8.5 Quote & Proposal Management (CPQ)** (`LIVE_LINKS["8.5"]`): `CPQQuote` (`CPQ-`), `CPQQuoteLine`, `ProductBundleOption` (`BND-`), `QuoteApprovalRule` (`QAR-`).
- **8.6 Order Management** (`LIVE_LINKS["8.6"]`): Extends `scm.SalesOrder` (`SO-`) via `OrderValidationRule` (`OVR-`), `OrderHold` (`OHD-`), `OrderAmendment` (`AMD-`), `RevenueSchedule` (`RVS-`), `PerformanceObligation`.
- **8.7 Territory & Quota Management** (`LIVE_LINKS["8.7"]`): Extends `crm.Territory` (`TER-`) and `crm.SalesQuota` (`QTA-`) via `TerritoryRule` (`TRG-`), `AccountTerritoryAssignment` (`TAS-`), `TerritoryMember` (`TMB-`), `QuotaPlan` (`QPA-`).
- **8.8 Sales Activity & Task Management** (`LIVE_LINKS["8.8"]`): Extends CRM 1.5 activity stack via `ActivityType` (`ATY-`), `ActivityLog` (`SAL-`, 1:1 required FK to `crm.CommunicationLog`), `TaskTemplate` (`TTPL-`), `SalesPlanCycle` (`SPC-`), `ActivityGoal`.
- **8.9 Sales Enablement** (`LIVE_LINKS["8.9"]`): `EnablementContent` (`ECN-`), `SalesPlaybook` (`SPB-`), `SalesCertification` (`SCTF-`), `CoachingScorecard` (`CSC-`).
- **8.10 Incentive Compensation Management**: Next unbuilt sub-module (no entry in `LIVE_LINKS` yet; next migration is `0019`).

### 1.2 Core and Sibling models available to FK (verified via codebase grep)
- **`apps/crm`**:
  * `crm.Opportunity` (`OPP-`) (`apps/crm/models/SalesForceAutomation/Opportunities.py`) — opportunity master. 8.10 attaches commission events directly to closed-won opportunities.
  * `crm.OpportunitySplit` (`apps/crm/models/SalesForceAutomation/Opportunities.py`) — sales-team credit split model (`split_type="revenue"|"overlay"`, `percentage`, `user`). 8.10 reuses this existing split table rather than declaring a duplicate deal split model.
  * `crm.SalesQuota` (`QTA-`) (`apps/crm/models/SalesForceAutomation/SalesQuotas.py`) — rep target amount per period (`period_type`, `period_year`, `period_number`, `target_amount`, `owner`). 8.10 evaluates attainment against these quotas.
- **`apps/sales`**:
  * `sales.QuotaPlan` (`QPA-`) (`apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py`) — quota derivation envelope linking `crm.SalesQuota` and `sales.ForecastPeriod`.
  * `sales.ForecastPeriod` (`FCP-`) (`apps/sales/models/SalesForecasting/ForecastPeriods.py`) — calendar window envelope (`period_type`, `period_year`, `period_number`, `start_date`, `end_date`, `reporting_currency`).
  * `sales.OrderAmendment` (`AMD-`) (`apps/sales/models/OrderManagement/OrderAmendments.py`) — post-signature changes, price reductions, and cancellations triggering clawbacks.
- **`apps/scm`**:
  * `scm.SalesOrder` (`SO-`) (`apps/scm/models/OrderManagement/SalesOrders.py`) — fulfilled and billed sales orders for companies paying commissions upon order execution or invoice generation.
- **`apps/accounting`**:
  * `accounting.Currency` (`apps/accounting/models/GeneralLedger/Currencies.py`) — ISO 4217 currency master. Global reference model (no tenant FK).
  * `accounting.ExchangeRate` (`apps/accounting/models/GeneralLedger/ExchangeRates.py`) — tenant-owned daily spot exchange rate table (`currency`, `rate_date`, `rate`, `source`) for multi-currency conversion to tenant functional currency.
  * `accounting.PayrollRun` (`PRUN-`) (`apps/accounting/models/PayrollIntegration/PayrollRuns.py`) — pay-period payroll accrual and posting engine (`gross_wages`, `employee_tax`, `employer_tax`, `net_pay`, `journal_entry`). 8.10 statements integrate directly into this model.
- **`apps/hrm`**:
  * `hrm.PayrollCycle` (`PRC-`) & `hrm.Payslip` (`PSL-`) (`apps/hrm/models/PayrollProcessing/`) — employee compensation and payslips for optional enterprise HR cross-referencing.
- **`apps/accounts`**:
  * `accounts.User` (`settings.AUTH_USER_MODEL`) — payees, managers, plan administrators, and dispute reviewers.

### 1.3 Auto-Number Prefixes Swept & Confirmed Free
Checked against all models across `apps/*/models/`:
- **`CMPL`** (Commission Plan): **FREE** (avoided `CMP`, which is used by `sales.CompetitorProfile` and `hrm.ComplianceRegister`).
- **`CER`** (Commission Earning): **FREE**.
- **`CST`** (Commission Statement): **FREE**.
- **`CADJ`** (Commission Adjustment): **FREE** (avoided `ADJ`, which is used by `scm.StockAdjustments`).

---

## 2. The five NavERP.md 8.10 bullets, verbatim

1. **Commission Plan Design** — Revenue-based, quota-based, tiered accelerators, and SPIF (Sales Performance Incentive Funds) structures.
2. **Real-Time Earnings Tracking** — Live commission dashboards, "what-if" calculators, and attainment progress.
3. **Clawbacks & Adjustments** — Chargebacks for cancellations, true-up calculations, and dispute resolution workflows.
4. **Multi-Currency & Global Plans** — Regional plan variations, currency conversion, and local tax compliance.
5. **Payout Processing & Integration** — Payroll system feeds, manual override approvals, and statement generation.

### Bullet-by-bullet verdict & boundary ruling

| Bullet | Already owned / built? | What 8.10 adds | Architectural Ruling |
|---|---|---|---|
| **1. Commission Plan Design** | CRM 1.2 owns `SalesQuota`; Sales 8.7 owns `QuotaPlan`. No plan rule or accelerator engine exists. | `CommissionPlan` (`CMPL-`) — rule master supporting flat revenue %, quota-attainment tiered accelerators (incremental vs retroactive), SPIFs, recoverable/non-recoverable draws, and regional scoping. | References `crm.SalesQuota` and `sales.QuotaPlan` for quota targets; does NOT re-declare sales quotas or territories. |
| **2. Real-Time Earnings Tracking** | CRM 1.2 owns `Opportunity` and `OpportunitySplit`. SCM 4.5 owns `SalesOrder`. | `CommissionEarning` (`CER-`) — granular deal- and order-level crediting records calculating exact earnings, split %, attainment at close, accelerator rates, and SPIFs. Live rep dashboard and "What-If" calculator. | Reuses `crm.Opportunity`, `crm.OpportunitySplit`, and `scm.SalesOrder`. Does NOT create a second deal, split, or order model. |
| **3. Clawbacks & Adjustments** | Sales 8.6 owns `OrderAmendment` and cancellations. No commission dispute or chargeback ledger exists. | `CommissionAdjustment` (`CADJ-`) — auditable resolution engine for cancellation chargebacks, churn clawbacks, draw and tier true-ups, manager overrides, and rep dispute ticket workflows with multi-state resolution. | References cancelled orders (`scm.SalesOrder`) and deals (`crm.Opportunity`). Reversible earnings maintain self-referencing `clawback_parent` links. |
| **4. Multi-Currency & Global Plans** | Accounting 2.2 owns `Currency` (global) and `ExchangeRate` (tenant spot rates). | Multi-currency plan specifications, daily spot rate translation into tenant functional currency, regional plan variations, and local tax withholding estimations. | Reuses `accounting.Currency` and `accounting.ExchangeRate`. Does NOT create a private sales currency table. |
| **5. Payout Processing & Integration** | Accounting 2.8 owns `PayrollRun` (`PRUN-`). HRM 3.14 owns `PayrollCycle`. | `CommissionStatement` (`CST-`) — formal monthly/quarterly rep statements, gross-to-net derivation (earnings minus draw recoveries minus clawbacks), manager approvals, lock mechanisms, and direct integration into `accounting.PayrollRun`. | Links directly to `accounting.PayrollRun`. Does not duplicate GL posting logic or tax tables. |

---

## 3. Leaders surveyed (with source links)

1. **CaptivateIQ** — Modern Incentive Compensation Management (ICM) platform known for SmartGrids flexible calculation modeling, real-time payee statement portals, in-app dispute resolution workflows, clawback automation, and payroll synchronization.  
   *Source:* [https://www.captivateiq.com/platform](https://www.captivateiq.com/platform)
2. **Salesforce Spiff (Salesforce SPM)** — Enterprise commission automation platform featuring real-time calculation engines, interactive Commission Statements, What-If deal calculators for sales reps, automated clawback processing, and Salesforce CRM integration.  
   *Source:* [https://www.salesforce.com/products/spiff/](https://www.salesforce.com/products/spiff/)
3. **Performio** — Enterprise sales performance management and ICM leader featuring a robust calculation engine, plan design builder, rep mobile dashboards, participant dispute/inquiry ticketing, ASC 606 commission amortization tracking, and multi-currency payroll export.  
   *Source:* [https://www.performio.co/product](https://www.performio.co/product)
4. **Varicent** — Gartner Magic Quadrant Leader for Sales Performance Management, recognized for enterprise calculation power, complex multi-tiered accelerator matrices, draw against commission reconciliation, territory/quota integration, and audit compliance.  
   *Source:* [https://www.varicent.com/products/incentive-compensation-management](https://www.varicent.com/products/incentive-compensation-management)
5. **Xactly Incent** — Enterprise standard-bearer in sales compensation automation, providing multi-tiered accelerators, SPIF management, deal credit splits, automated clawbacks triggered by contract churn, global multi-currency conversions, and ERP/payroll integration.  
   *Source:* [https://www.xactlycorp.com/products/incent](https://www.xactlycorp.com/products/incent)
6. **Everstage** — High-growth modern SPM platform emphasizing transparent rep dashboards, pipeline-based What-If commission forecasting, structured in-app dispute workflows, and automated clawback deductions linked to CRM cancellation data.  
   *Source:* [https://www.everstage.com/product](https://www.everstage.com/product)
7. **QuotaPath** — Mid-market sales compensation software featuring a visual commission plan builder, quota accelerators, SPIFs, deal-level commission tracking, CRM sync, and payroll export feeds.  
   *Source:* [https://www.quotapath.com/features/](https://www.quotapath.com/features/)
8. **SAP SuccessFactors Incentive Management (SAP Commissions)** — Enterprise global compensation platform (formerly CallidusCloud) delivering complex formulaic tier matrices, multi-currency conversion, local tax compliance, automated liability tracking, and SAP S/4HANA payroll connectivity.  
   *Source:* [https://www.sap.com/products/hcm/incentive-management.html](https://www.sap.com/products/hcm/incentive-management.html)
9. **Forma.ai** — AI-driven sales performance management platform automating commission calculations, behavioral incentive modeling, dynamic tier and SPIF management, and consolidated compensation execution.  
   *Source:* [https://www.forma.ai/platform/](https://www.forma.ai/platform/)

---

## 4. Feature catalog (this sub-module only)

### 4.1 Commission Plan Design (NavERP.md Bullet 1)
- **Multi-Method Plan Architecture** — Support for diverse commission structures: flat revenue percentage, gross margin percentage, quota-attainment tiered accelerators, SPIF-only bonuses, and hybrid compensation plans.  
  *Seen in:* CaptivateIQ, Varicent, Xactly Incent, QuotaPath  
  *Priority:* Table-stakes  
  *Spine:* `CommissionPlan` (`CMPL-`) model with `plan_type` and calculation parameters. Buildable now.
- **Tiered Accelerators: Incremental vs Retroactive Modes** — Flexible accelerator bracket calculation:  
  * *Incremental (Marginal):* Higher commission rate applies solely to the incremental revenue crossing into the bracket (e.g. 8% up to 100%, 15% on revenue between 100% and 150%).  
  * *Retroactive (All-In):* Crossing a threshold retroactively lifts the commission rate across all revenue generated during the entire period.  
  *Seen in:* Spiff, CaptivateIQ, QuotaPath, Performio  
  *Priority:* Table-stakes  
  *Spine:* `tier_mode` (`incremental` vs `retroactive`) and `tiers_config` on `CommissionPlan`. Buildable now.
- **Sales Performance Incentive Funds (SPIF) Engine** — Short-term, tactical bonus campaigns layered on top of core compensation plans (e.g., flat dollar bonuses for selling new product lines, double commission accelerators during end-of-quarter push, or customer acquisition bounties).  
  *Seen in:* Xactly Incent, CaptivateIQ, QuotaPath, Everstage  
  *Priority:* Table-stakes  
  *Spine:* `spif_config` JSON schema on `CommissionPlan` and `spif_amount` on `CommissionEarning`. Buildable now.
- **Draw Against Commission (Recoverable vs Non-Recoverable)** — Managing guaranteed monthly draw advances for ramping reps or extended sales cycles:  
  * *Recoverable Draw:* Advance operates as a liability offset; future commission earnings are deducted to repay the draw.  
  * *Non-Recoverable Draw:* Guaranteed minimum income floor; company absorbs shortfalls without debt rollover.  
  *Seen in:* Varicent, Xactly, Performio  
  *Priority:* Common  
  *Spine:* `draw_type` and `draw_amount` on `CommissionPlan`, with draw true-up tracking on `CommissionStatement`. Buildable now.
- **Clawback Policy Configuration** — Setting policy terms for how commissions are reclaimed if deals cancel or churn prematurely: full cliff clawback vs pro-rated duration clawback, and clawback lookback window in days (e.g. 90, 180, 365 days).  
  *Seen in:* CaptivateIQ, Spiff, Everstage  
  *Priority:* Common  
  *Spine:* `clawback_window_days` and `clawback_policy` on `CommissionPlan`. Buildable now.

### 4.2 Real-Time Earnings Tracking (NavERP.md Bullet 2)
- **Live Deal-by-Deal Commission Crediting** — Immediate calculation of commission earnings upon opportunity closed-won stage or sales order booking, showing exact deal value, split share, commission rate, and calculated gross payout.  
  *Seen in:* Spiff, Everstage, QuotaPath  
  *Priority:* Table-stakes  
  *Spine:* `CommissionEarning` (`CER-`) referencing `crm.Opportunity` and `scm.SalesOrder`. Buildable now.
- **Sales Team Split Crediting** — Direct support for multi-rep team selling, co-selling, and overlay credits by consuming `crm.OpportunitySplit` percentages (e.g., 60% AE / 40% Overlay Specialist) without double-crediting bookings.  
  *Seen in:* Spiff, Xactly, CaptivateIQ  
  *Priority:* Table-stakes  
  *Spine:* `opportunity_split` FK to `crm.OpportunitySplit` on `CommissionEarning`. Buildable now.
- **Attainment Progress Speedometer** — Real-time tracking of cumulative rep sales against assigned quota targets (`crm.SalesQuota` / `sales.QuotaPlan`), showing attainment percentage, current active accelerator bracket, and distance to next tier.  
  *Seen in:* Everstage, Spiff, Performio  
  *Priority:* Common  
  *Spine:* `sales_commission_dashboard` view computing real-time quota attainment. Buildable now.
- **Interactive "What-If" Deal Calculator** — Rep-facing simulation tool enabling sales reps to model pipeline opportunities (`crm.Opportunity`), adjust deal values or closing dates, and visualize estimated commission earnings and accelerator jumps prior to closing the deal.  
  *Seen in:* Spiff, Everstage, QuotaPath  
  *Priority:* Differentiating  
  *Spine:* Read-only simulation utility on `sales_commission_dashboard`. Buildable now.
- **Mathematical Calculation Trace** — Full audit trail detailing the exact arithmetic breakdown for each earning (base rate, split factor, tier accelerator uplift, SPIF bonus addition, FX rate applied).  
  *Seen in:* Spiff, CaptivateIQ, Varicent  
  *Priority:* Common  
  *Spine:* `calculation_notes` text field on `CommissionEarning`. Buildable now.

### 4.3 Clawbacks & Adjustments (NavERP.md Bullet 3)
- **Automated Cancellation Chargebacks** — Automatic generation of debit adjustments when a closed deal or sales order is cancelled, refunded, or amended downwards (`sales.OrderAmendment`) within the clawback eligibility window.  
  *Seen in:* CaptivateIQ, Spiff, Everstage, Xactly  
  *Priority:* Table-stakes  
  *Spine:* `CommissionAdjustment` (`CADJ-`) with `adjustment_type="cancellation_clawback"`. Buildable now.
- **Clawback Parent Reversal Linking** — Explicit link between a clawback adjustment and the original historical earning record (`clawback_parent`), ensuring accurate ledger reconciliation without deleting historical transactions.  
  *Seen in:* Varicent, SAP Commissions, CaptivateIQ  
  *Priority:* Table-stakes  
  *Spine:* `clawback_parent` self-referential FK on `CommissionEarning`. Buildable now.
- **End-of-Period True-Up Calculations** — Reconciling periodic anomalies across quarters or years: settling recoverable draw balances against cumulative earnings, and retroactively truing up tiered accelerators when annual quota milestones are finalized.  
  *Seen in:* Varicent, Performio, CaptivateIQ  
  *Priority:* Common  
  *Spine:* `CommissionAdjustment` with `adjustment_type="quota_true_up"` / `"draw_reconciliation"`. Buildable now.
- **In-App Rep Dispute Resolution Workflow** — Formal dispute ticketing allowing reps to flag contested line items on their commission statement, submit documentation/reasons, and route the dispute through a structured triage workflow (`draft` -> `submitted` -> `under_review` -> `approved` -> `rejected` -> `applied`).  
  *Seen in:* Everstage, CaptivateIQ, Performio, Spiff  
  *Priority:* Table-stakes  
  *Spine:* `CommissionAdjustment` with `adjustment_type="dispute"`, `status`, and `reviewed_by`. Buildable now.
- **Manager Manual Override Approvals** — Administrative capability for sales leadership or RevOps to grant one-off discretionary bonuses, split adjustments, or goodwill credits with mandatory justification logs and reviewer stamps.  
  *Seen in:* Xactly, Performio, Varicent  
  *Priority:* Common  
  *Spine:* `CommissionAdjustment` with `adjustment_type="manual_override"` and approval audit fields. Buildable now.

### 4.4 Multi-Currency & Global Plans (NavERP.md Bullet 4)
- **Regional Plan Variations** — Ability to tailor commission structures to specific geographic territories or entities (e.g., North America vs EMEA vs APAC) reflecting different compensation mixes, base-to-variable ratios, and regional sales motions.  
  *Seen in:* SAP Commissions, Varicent, Xactly  
  *Priority:* Common  
  *Spine:* `regional_scope`, `is_global`, and `currency` on `CommissionPlan`. Buildable now.
- **Daily Spot Rate Currency Translation** — Real-time translation of deal revenue and commission earnings from transaction currency into plan functional currency using `accounting.ExchangeRate` spot rates on transaction close date.  
  *Seen in:* Varicent, Xactly, SAP Commissions  
  *Priority:* Table-stakes  
  *Spine:* `exchange_rate` and `functional_currency_amount` on `CommissionEarning`, integrating with `accounting.ExchangeRate`. Buildable now.
- **Multi-Currency Global Reporting Matrix** — Executive consolidation dashboard converting multi-national commission liabilities into corporate base currency while maintaining native local currency pay slips for international payees.  
  *Seen in:* SAP Commissions, Varicent, Performio  
  *Priority:* Differentiating  
  *Spine:* `sales_global_compensation_matrix` view. Buildable now.
- **Local Statutory Tax Withholding Estimation** — Storing regional tax withholding percentages and statutory guidelines on commission plans to estimate net take-home commission pay across diverse jurisdictions.  
  *Seen in:* SAP Commissions, Xactly Incent  
  *Priority:* Common  
  *Spine:* `local_tax_withholding_pct` on `CommissionPlan` and `tax_withholding_estimated` on `CommissionStatement`. Buildable now.

### 4.5 Payout Processing & Integration (NavERP.md Bullet 5)
- **Pay-Period Commission Statement Generation** — Automated rollup of all eligible earnings, active SPIFs, draw advances, clawback deductions, and approved adjustments for each payee into an official monthly or quarterly statement.  
  *Seen in:* CaptivateIQ, Spiff, Everstage, Performio  
  *Priority:* Table-stakes  
  *Spine:* `CommissionStatement` (`CST-`) model. Buildable now.
- **Gross-to-Net Statement Waterfall** — Transparent breakdown formula:  
  `Gross Commission (Base + Accelerators + SPIF) + Approved Adjustments - Recovered Draws - Clawbacks - Estimated Withholding = Net Commission Payout`.  
  *Seen in:* CaptivateIQ, Spiff, Everstage  
  *Priority:* Table-stakes  
  *Spine:* Stored fields and property calculations on `CommissionStatement`. Buildable now.
- **Statement Approval & Immutability Lock** — Two-step managerial workflow: statement submission, executive approval, and subsequent cryptographic lock preventing further modifications once statements are queued for payout.  
  *Seen in:* Performio, CaptivateIQ, Varicent  
  *Priority:* Table-stakes  
  *Spine:* `status="locked"` on `CommissionStatement`, freezing all attached earnings and adjustments. Buildable now.
- **Direct Hand-Off to Accounting Payroll Runs** — 1-click posting integration linking locked commission statement batches to `accounting.PayrollRun` (`PRUN-`), recording accrued commission liabilities on the general ledger.  
  *Seen in:* Xactly, SAP Commissions, Performio  
  *Priority:* Common  
  *Spine:* `payroll_run` FK to `accounting.PayrollRun` on `CommissionStatement`. Buildable now.
- **External Payroll CSV/Feed Export** — Pre-formatted payroll data exports matching standard enterprise payroll schemas (ADP Workforce Now, Workday, Gusto, Paychex) for seamless disbursement execution.  
  *Seen in:* QuotaPath, Everstage, CaptivateIQ  
  *Priority:* Common  
  *Spine:* Export handler on `sales_payout_processing_center`. Buildable now.

---

## 5. Technical Architecture & Data Model Recommendations

### Recommended Models (Exactly 4 Models)

Build **8.10 Incentive Compensation Management** with **exactly 4 tenant-scoped models** inheriting `TenantNumbered` (`apps.sales.models._base.TenantNumbered`):

```
+-------------------------------------------------------------------------------------------------+
|                                    8.10 Data Architecture                                       |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   +---------------------------------------+         +---------------------------------------+   |
|   |          CommissionPlan (CMPL)        |         |        CommissionStatement (CST)      |   |
|   |---------------------------------------|         |---------------------------------------|   |
|   | plan_type, tier_mode, currency        |         | payee, period_start, period_end       |   |
|   | tiers_config (JSON), spif_config(JSON)|         | gross_payout, draw_recovered, net_pay |   |
|   | draw_type, clawback_window_days       |         | status, payroll_run FK (PRUN)         |   |
|   +---------------------------------------+         +---------------------------------------+   |
|                       |                                                 |                       |
|                       | 1:N                                             | 1:N                   |
|                       v                                                 v                       |
|   +---------------------------------------+         +---------------------------------------+   |
|   |        CommissionEarning (CER)        | 1:N     |       CommissionAdjustment (CADJ)     |   |
|   |---------------------------------------|-------->|---------------------------------------|   |
|   | payee, opportunity (OPP), order (SO)  |         | statement (FK CST), earning (FK CER)  |   |
|   | deal_amount, split_pct, rate_pct      |         | adjustment_type (dispute|clawback|...) |   |
|   | accelerator_rate_pct, gross_commission|         | amount (signed Decimal), status       |   |
|   | currency, exchange_rate, functional_amt|         | reason_category, reviewed_by          |   |
|   +---------------------------------------+         +---------------------------------------+   |
|                                                                                                 |
+-------------------------------------------------------------------------------------------------+
```

---

### Model 1: `CommissionPlan` [PREFIX: `CMPL-`]
- **Purpose**: Master rule definition for sales compensation plans. Serves **Bullet 1** (Commission Plan Design) and **Bullet 4** (Multi-Currency & Global Plans).
- **Justified by**: CaptivateIQ Plan Designer, Spiff Commission Designer, Xactly Incent Rule Sets.
- **Fields**:
  * `number` — auto-numbered with prefix `CMPL` (TenantNumbered).
  * `name` — `CharField(max_length=160)`: plan title (e.g. "FY2026 Enterprise AE Plan - Americas").
  * `code` — `CharField(max_length=40, db_index=True)`: unique human code per tenant.
  * `description` — `TextField(blank=True)`: plan terms summary.
  * `plan_type` — `CharField(max_length=25, choices=PLAN_TYPE_CHOICES, default="quota_tiered")`:
    - `revenue_percentage` ("Flat Revenue Percentage")
    - `quota_tiered` ("Quota-Attainment Tiered Accelerators")
    - `gross_margin` ("Gross Margin Percentage")
    - `spif_only` ("Targeted SPIF Bonus Program")
    - `hybrid` ("Hybrid (Base Commission + Quota Accelerators + SPIF)")
  * `calculation_frequency` — `CharField(max_length=15, choices=FREQUENCY_CHOICES, default="monthly")`:
    - `monthly`, `quarterly`, `semi_annual`, `annual`.
  * `tier_mode` — `CharField(max_length=15, choices=TIER_MODE_CHOICES, default="incremental")`:
    - `incremental` ("Incremental / Marginal" — higher rate applies only to the bracket volume).
    - `retroactive` ("Retroactive / All-In" — higher rate applies to total volume from dollar one).
  * `currency` — `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="sales_commission_plans")`:
    ISO 4217 master currency for plan targets and thresholds (global reference, no tenant check).
  * `target_role` — `CharField(max_length=60, blank=True)` (e.g. "Account Executive", "SDR", "Sales Engineer", "Regional Director").
  * `effective_start_date` — `DateField(default=timezone.localdate)`.
  * `effective_end_date` — `DateField(null=True, blank=True)`.
  * `status` — `CharField(max_length=15, choices=STATUS_CHOICES, default="draft")`:
    `draft`, `active`, `archived`.
  * `is_global` — `BooleanField(default=False)`: whether plan spans multiple regions.
  * `regional_scope` — `CharField(max_length=60, blank=True)`: geographic region (e.g. "North America", "EMEA", "APAC", "Global").
  * `local_tax_withholding_pct` — `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])`.
  * `tiers_config` — `JSONField(default=list, blank=True)`:
    Array of bracket definitions: `[{"tier": 1, "min_attainment_pct": 0, "max_attainment_pct": 80, "rate_pct": 5.0, "accelerator_factor": 1.0}, {"tier": 2, "min_attainment_pct": 80.01, "max_attainment_pct": 100, "rate_pct": 10.0, "accelerator_factor": 1.0}, {"tier": 3, "min_attainment_pct": 100.01, "max_attainment_pct": 150, "rate_pct": 15.0, "accelerator_factor": 1.5}, {"tier": 4, "min_attainment_pct": 150.01, "max_attainment_pct": None, "rate_pct": 20.0, "accelerator_factor": 2.0}]`.
  * `spif_config` — `JSONField(default=dict, blank=True)`:
    SPIF rules configuration: `{"title": "Q3 Cloud Push", "bonus_type": "flat", "bonus_amount": 500.00, "multiplier": 1.25, "product_category": "Cloud Services", "valid_start": "2026-07-01", "valid_end": "2026-09-30"}`.
  * `draw_type` — `CharField(max_length=20, choices=DRAW_TYPE_CHOICES, default="none")`:
    - `none`, `recoverable` ("Recoverable Draw (Advanced loan against future commissions)"), `non_recoverable` ("Non-Recoverable Draw (Guaranteed minimum income floor)").
  * `draw_amount` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`.
  * `clawback_window_days` — `PositiveIntegerField(default=90, help_text="Number of days post-closing during which cancellation or refund triggers clawback")`.
  * `clawback_policy` — `CharField(max_length=20, choices=CLAWBACK_POLICY_CHOICES, default="full")`:
    - `full` ("100% Cliff Clawback"), `pro_rated` ("Pro-Rated based on unfulfilled duration"), `none` ("No Clawback").
  * `notes` — `TextField(blank=True)`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)` and Unique `(tenant, code)`.
  * Indexes: `(tenant, status)`, `(tenant, plan_type)`, `(tenant, effective_start_date)`.
- **Validation**:
  * `clean()` verifies `effective_end_date >= effective_start_date` if provided.
  * Validates JSON structure of `tiers_config` (valid numerical bounds and non-overlapping tiers).

---

### Model 2: `CommissionEarning` [PREFIX: `CER-`]
- **Purpose**: Granular, transaction-level commission crediting record connecting closed deals / sales orders to a rep and calculating the exact commission earned, tier attainment, SPIF bonus, split percentage, and multi-currency conversion. Serves **Bullet 1** and **Bullet 2** (Real-Time Earnings Tracking).
- **Justified by**: Spiff Deal Commission Lines, CaptivateIQ Earning Records, Everstage Transaction Ledger.
- **Fields**:
  * `number` — auto-numbered with prefix `CER` (TenantNumbered).
  * `plan` — `ForeignKey("CommissionPlan", on_delete=models.PROTECT, related_name="earnings")`.
  * `payee` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales_commission_earnings")`.
  * `opportunity` — `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="commission_earnings")`: CRM 1.2 closed deal.
  * `opportunity_split` — `ForeignKey("crm.OpportunitySplit", on_delete=models.SET_NULL, null=True, blank=True, related_name="commission_earnings")`: CRM 1.2 credit split if applicable.
  * `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_commission_earnings")`: SCM 4.5 order if commission is billed/order-triggered.
  * `sales_quota` — `ForeignKey("crm.SalesQuota", on_delete=models.SET_NULL, null=True, blank=True, related_name="commission_earnings")`: quota target evaluated for attainment.
  * `statement` — `ForeignKey("CommissionStatement", on_delete=models.SET_NULL, null=True, blank=True, related_name="line_items")`: statement batch rollup.
  * `earning_type` — `CharField(max_length=25, choices=EARNING_TYPE_CHOICES, default="deal_won")`:
    - `deal_won` ("Closed-Won Opportunity Commission")
    - `order_billed` ("Sales Order Execution / Billing")
    - `spif_bonus` ("SPIF Incentive Bonus")
    - `accelerator_bonus` ("Tiered Quota Accelerator Payout")
    - `manual_credit` ("Manager Approved Override Credit")
    - `draw_advance` ("Draw Advance Issued")
    - `clawback_deduction` ("Clawback / Cancellation Chargeback")
  * `deal_amount` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: total originating deal or order value.
  * `split_percentage` — `DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"), validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(100)])`: rep credit split percentage.
  * `credited_amount` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), help_text="deal_amount * (split_percentage / 100)")`.
  * `attainment_pct_at_close` — `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"), help_text="Cumulative quota attainment at time of deal")`.
  * `commission_rate_pct` — `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))`: base commission rate applied.
  * `accelerator_rate_pct` — `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))`: incremental accelerator rate applied.
  * `spif_amount` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: flat SPIF bonus amount.
  * `gross_commission` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: total commission before deductions in transaction currency.
  * `currency` — `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="commission_earnings")`: transaction currency.
  * `exchange_rate` — `DecimalField(max_digits=18, decimal_places=8, default=Decimal("1.00000000"))`: spot exchange rate to tenant functional currency.
  * `functional_currency_amount` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: gross commission converted to base functional currency.
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="accrued")`:
    - `accrued` ("Accrued / Calculated")
    - `approved` ("Manager Approved")
    - `locked` ("Locked in Statement")
    - `paid` ("Disbursed / Paid")
    - `clawed_back` ("Reversed / Clawed Back")
  * `event_date` — `DateField(default=timezone.localdate)`: deal close date or order booking date.
  * `clawback_parent` — `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="clawback_children", help_text="Original earning reversed by this clawback")`.
  * `calculation_notes` — `TextField(blank=True, help_text="Mathematical audit trace")`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`.
  * Indexes: `(tenant, payee)`, `(tenant, plan)`, `(tenant, opportunity)`, `(tenant, statement)`, `(tenant, status)`, `(tenant, event_date)`.

---

### Model 3: `CommissionStatement` [PREFIX: `CST-`]
- **Purpose**: Pay-period commission statement aggregating earnings, draws, recoveries, clawbacks, and adjustments for one rep in a specific period, supporting managerial approval, lock, and integration into `accounting.PayrollRun`. Serves **Bullet 2**, **Bullet 4**, and **Bullet 5** (Payout Processing & Integration).
- **Justified by**: Spiff Rep Statements, CaptivateIQ Payout Statements, Performio Payee Invoices.
- **Fields**:
  * `number` — auto-numbered with prefix `CST` (TenantNumbered).
  * `payee` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commission_statements")`.
  * `plan` — `ForeignKey("CommissionPlan", on_delete=models.PROTECT, related_name="statements")`.
  * `period_name` — `CharField(max_length=60)` (e.g. "October 2026", "2026-Q3", "2026-M10").
  * `period_start` — `DateField()`.
  * `period_end` — `DateField()`.
  * `currency` — `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="commission_statements")`: statement payout currency.
  * `total_deal_revenue` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: sum of credited deal volume in period.
  * `quota_target` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: period quota target.
  * `attainment_percentage` — `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`: cumulative attainment percentage for period.
  * `base_commission_total` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`.
  * `accelerator_bonus_total` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`.
  * `spif_total` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`.
  * `draw_advanced` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: draw amount advanced in this period.
  * `draw_recovered` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: prior recoverable draw deducted from this payout.
  * `clawbacks_total` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: sum of cancellation chargebacks deducted in period.
  * `adjustments_total` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`: net manual adjustments and dispute credits.
  * `gross_payout` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), help_text="base + accelerator + spif + adjustments")`.
  * `tax_withholding_estimated` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`.
  * `net_payout` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), help_text="gross_payout - draw_recovered - clawbacks - tax_withholding")`.
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`:
    - `draft`, `submitted`, `under_review`, `approved`, `locked`, `exported`, `paid`.
  * `approved_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_commission_statements")`.
  * `approved_at` — `DateTimeField(null=True, blank=True)`.
  * `payroll_run` — `ForeignKey("accounting.PayrollRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_commission_statements", help_text="Hand-off to Accounting 2.8 PayrollRun accrual")`.
  * `payment_reference` — `CharField(max_length=80, blank=True, help_text="External payroll batch ID or check ref")`.
  * `paid_at` — `DateField(null=True, blank=True)`.
  * `notes` — `TextField(blank=True)`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`.
  * Unique together: `(tenant, payee, plan, period_start, period_end)` (prevents duplicate statement per payee/plan/period).
  * Indexes: `(tenant, payee)`, `(tenant, status)`, `(tenant, period_start, period_end)`, `(tenant, payroll_run)`.

---

### Model 4: `CommissionAdjustment` [PREFIX: `CADJ-`]
- **Purpose**: Auditable resolution engine for clawbacks, cancellation chargebacks, true-up reconciliations, rep dispute tickets, and manager override approvals. Serves **Bullet 3** (Clawbacks & Adjustments) and **Bullet 5** (Manual Override Approvals).
- **Justified by**: Everstage In-App Disputes, CaptivateIQ Dispute Triage, Varicent Adjustment Logs.
- **Fields**:
  * `number` — auto-numbered with prefix `CADJ` (TenantNumbered).
  * `statement` — `ForeignKey("CommissionStatement", on_delete=models.CASCADE, related_name="adjustments")`: statement this adjustment impacts.
  * `earning` — `ForeignKey("CommissionEarning", on_delete=models.SET_NULL, null=True, blank=True, related_name="adjustments")`: contested or reversed earning line.
  * `payee` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commission_adjustments")`.
  * `adjustment_type` — `CharField(max_length=30, choices=ADJUSTMENT_TYPE_CHOICES, default="dispute")`:
    - `dispute` ("Rep-Raised Commission Dispute")
    - `cancellation_clawback` ("Customer Cancellation / Refund Clawback")
    - `churn_chargeback` ("Premature Churn Chargeback")
    - `quota_true_up` ("End-of-Period Quota / Tier True-Up")
    - `draw_reconciliation` ("Recoverable Draw Settlement True-Up")
    - `manual_override` ("Manager Goodwill / Discretionary Override")
    - `split_correction` ("Retroactive Split Percentage Correction")
  * `amount` — `DecimalField(max_digits=14, decimal_places=2, help_text="Signed decimal: positive for credit addition, negative for clawback deduction")`.
  * `currency` — `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="commission_adjustments")`.
  * `reason_category` — `CharField(max_length=40, choices=REASON_CHOICES, default="deal_discrepancy")`:
    - `deal_discrepancy`, `split_error`, `cancelled_contract`, `late_billing`, `rate_mismatch`, `goodwill_exception`, `other`.
  * `description` — `TextField(help_text="Detailed justification or rep inquiry description")`.
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`:
    - `draft`, `submitted`, `under_review`, `approved`, `rejected`, `applied`.
  * `reviewed_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_commission_adjustments")`.
  * `reviewed_at` — `DateTimeField(null=True, blank=True)`.
  * `resolution_notes` — `TextField(blank=True, help_text="Manager or Ops rationale for approving or rejecting")`.
  * `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="commission_adjustments", help_text="Referenced order for cancellations")`.
  * `opportunity` — `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="commission_adjustments", help_text="Referenced deal")`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`.
  * Indexes: `(tenant, statement)`, `(tenant, payee)`, `(tenant, status)`, `(tenant, adjustment_type)`.

---

## 6. Mathematical & Calculation Specifications

### 6.1 Incremental (Marginal) vs Retroactive (All-In) Accelerator Math
Let:
- $Q$ = Periodic Quota Target
- $R_{prev}$ = Cumulative Deal Revenue credited in period prior to current deal
- $D$ = Credited Revenue of current deal
- $R_{curr} = R_{prev} + D$
- $T_i = [\text{MinAttainment}_i, \text{MaxAttainment}_i]$ with base/accelerator rate $r_i$.

**Incremental (Marginal) Mode:**
The revenue $D$ is partitioned across tier intervals $[L_i, U_i]$ where $L_i = Q \times \text{MinAttainment}_i$ and $U_i = Q \times \text{MaxAttainment}_i$.
$$\text{Commission} = \sum_{i} \max\left(0, \min(R_{curr}, U_i) - \max(R_{prev}, L_i)\right) \times r_i$$
Only the portion of the deal revenue falling within each bracket earns that bracket's specific rate.

**Retroactive (All-In) Mode:**
Attainment percentage after the deal is $A = \frac{R_{curr}}{Q} \times 100\%$.
Find tier $k$ such that $\text{MinAttainment}_k \le A \le \text{MaxAttainment}_k$.
The rate $r_k$ applies to the entire volume, with prior earnings credited:
$$\text{Total Earned} = R_{curr} \times r_k$$
$$\text{Current Earning Payout} = (R_{curr} \times r_k) - \text{Cumulative Previously Calculated Commission}$$

### 6.2 Opportunity Split Crediting
Given originating opportunity amount $V$ and rep split share $S_{\%}$ from `crm.OpportunitySplit`:
$$\text{Credited Amount} = V \times \frac{S_{\%}}{100}$$
Overlay credits do not reduce the quota credit of the primary AE ($S_{\%}$ for revenue splits must sum $\le 100\%$, while overlay splits carry `split_type="overlay"`).

### 6.3 Draw Against Commission Reconciliation
Given advanced draw amount $W$ in statement period:
- If `draw_type == "non_recoverable"`:
  $$\text{Payout} = \max(\text{Total Earned Commissions}, W)$$
  The company absorbs any deficit; no debt balance carries forward.
- If `draw_type == "recoverable"`:
  $$\text{Net Payout} = \max(0, \text{Total Earned Commissions} - \text{Cumulative Unrecovered Draws})$$
  $$\text{Remaining Debt Balance} = \max(0, \text{Cumulative Unrecovered Draws} - \text{Total Earned Commissions})$$

### 6.4 Clawback Calculation
If deal with original commission $C_{orig}$ closes on $t_0$, customer cancels on $t_c$, and contract duration is $T_{total}$:
- **Full Cliff Clawback:**
  If $(t_c - t_0) \le \text{ClawbackWindowDays}$:
  $$\text{Clawback Amount} = -C_{orig}$$
- **Pro-Rated Clawback:**
  $$\text{Clawback Amount} = -C_{orig} \times \left(1 - \frac{\text{Elapsed Days}}{T_{total}}\right)$$

### 6.5 Multi-Currency Spot Conversion
Given transaction amount in foreign currency $V_{foreign}$ and spot exchange rate $X_{rate}$ from `accounting.ExchangeRate` on deal close date $t_{close}$ ($1 \text{ Foreign Unit} = X_{rate} \text{ Functional Units}$):
$$\text{Functional Currency Amount} = V_{foreign} \times X_{rate}$$

---

## 7. Read-only board candidates (no new models)

The 5 NavERP.md feature bullets map directly to 5 comprehensive views/boards:

1. **`sales_commission_plan_hub`** (Commission Plan Design)  
   Serves **Bullet 1**. Plan designer catalog displaying active, draft, and archived commission plans. Surfaces tier bracket visualizations, SPIF campaign schedules, participant counts, and side-by-side plan comparisons.
2. **`sales_commission_earnings_dashboard`** (Real-Time Earnings Tracking)  
   Serves **Bullet 2**. Interactive rep and manager earnings portal featuring live quota attainment speedometers, deal-by-deal credit ledgers, SPIF bonus tallies, and an interactive **"What-If" Calculator** allowing reps to test open pipeline deals (`crm.Opportunity`) to forecast payout and accelerator tier jumps.
3. **`sales_commission_adjustment_workbench`** (Clawbacks & Adjustments)  
   Serves **Bullet 3**. Operational triage workbench managing cancellation chargebacks from cancelled sales orders (`scm.SalesOrder`), contract churn alerts, draw true-up settlements, and rep dispute resolution ticketing workflows with full audit histories.
4. **`sales_global_compensation_matrix`** (Multi-Currency & Global Plans)  
   Serves **Bullet 4**. Multi-national compensation matrix displaying regional plan variations (Americas, EMEA, APAC), FX conversion audit trails (comparing transaction currency vs base functional currency via `accounting.ExchangeRate`), and estimated statutory tax withholding summaries.
5. **`sales_commission_payout_processing`** (Payout Processing & Integration)  
   Serves **Bullet 5**. Pay-period statement generation workbench supporting statement batch review, manager override approval queues, one-click statement locking, and seamless hand-off to `accounting.PayrollRun` (`PRUN-`) or pre-formatted CSV exports (ADP, Workday, Gusto).

---

## 8. Belongs to sibling sub-modules (parked, not scoped here)

- **Opportunity pipeline management & deal creation** → **CRM 1.2** and **Sales 8.2** (`OpportunityPipeline`, `OpportunityStage`). 8.10 attaches commission earnings to closed deals; does not create a deal master.
- **Opportunity team credit split registration** → **CRM 1.2** (`crm.OpportunitySplit`). 8.10 reads split percentages; does not create a duplicate split entity.
- **Sales order creation, fulfillment, and amendment tracking** → **SCM 4.5** (`scm.SalesOrder`) and **Sales 8.6** (`sales.OrderAmendment`). 8.10 reads orders for commission triggers and cancellations for clawbacks.
- **Quota setting & derivation methodologies** → **CRM 1.2** (`crm.SalesQuota`) and **Sales 8.7** (`sales.QuotaPlan`). 8.10 evaluates attainment against quotas; does not set quotas.
- **Sales forecasting calls and scenario modeling** → **Sales 8.4** (`ForecastSubmission`, `ForecastScenario`).
- **General Ledger journal entries & payroll disbursement posting** → **Accounting 2.2** (`JournalEntry`) and **Accounting 2.8** (`PayrollRun`). 8.10 links statements to `PayrollRun`.
- **Employee HR salary structure & employee master** → **HRM 3.1** (`EmployeeProfile`) and **HRM 3.14** (`PayrollCycle`, `Payslip`).

---

## 9. Deferred (later passes / external integrations)

- **Direct Banking Clearing & ACH/Wire Disbursement** — Automated bank payouts via NACHA / SEPA protocols belong in treasury integrations (Accounting Module 2). 8.10 manages commission accrual, calculation, and payroll hand-off.
- **Bi-directional Webhook Sync to External Payroll Engines** — Real-time live API sync to ADP, Workday, or Gusto via automated webhook listeners is deferred to integration gateway (Module 20). 8.10 provides standard pre-formatted payroll export feeds.
- **AI-Powered Commission Anomaly Detection** — Machine learning models flagging unexpected commission spikes or gaming behavior deferred to Sales Analytics & Intelligence (8.12).
- **ASC 606 Commission Capitalization & Amortization Schedules** — Multi-year contract commission expense capitalization ties into Revenue Recognition (8.6 `RevenueSchedule` / Accounting 2.10).

---

## 10. Verdict & Implementation Blueprint

Build **8.10 Incentive Compensation Management** with **exactly 4 tenant-scoped models**:
1. `CommissionPlan` (`CMPL-`) — Plan master, flat rates, tiered accelerators (incremental vs retroactive), SPIFs, draws, clawback terms, and regional scopes.
2. `CommissionEarning` (`CER-`) — Granular deal and order crediting records, split shares, attainment at close, accelerator rates, SPIF bonuses, and multi-currency spot conversions.
3. `CommissionStatement` (`CST-`) — Pay-period statement rollups, gross-to-net waterfall math, manager approvals, statement locks, and direct integration into `accounting.PayrollRun`.
4. `CommissionAdjustment` (`CADJ-`) — Clawbacks, cancellation chargebacks, draw and tier true-ups, rep dispute resolution workflows, and manager manual override approvals.

Plus **5 read-only boards** mapping directly to the 5 NavERP.md feature bullets, with **zero duplicate quota, deal, order, currency, or payroll masters**.
