# Research — Sub-module 8.11: Customer Success & Account Management (Module 8 — Sales Management System, `apps/sales`)

> Phase 1 output. Target: **8.11 Customer Success & Account Management**. NavERP.md 8.11 = the five feature bullets reproduced verbatim in §2. All five are addressed in full.
> This research grounds 8.11 against verified as-built code in `apps/sales`, `apps/crm`, `apps/scm`, `apps/accounting`, and `apps/core`, and synthesizes specialized capabilities from 9 commercial market leaders.

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
- **8.10 Incentive Compensation Management** (`LIVE_LINKS["8.10"]`): `CommissionPlan` (`CMPL-`), `CommissionEarning` (`CER-`), `CommissionStatement` (`CST-`), `CommissionAdjustment` (`CADJ-`).
- **8.11 Customer Success & Account Management**: Target sub-module for this build run. Leaf migration in `apps/sales/migrations` is `0020`, so 8.11 claims migration **`0021`**.

### 1.2 Core and Sibling models available to FK (verified via codebase grep)
- **`apps/core`**:
  * `core.Party` (`apps/core/models/Party.py`) — unified spine entity. Accounts/clients are `core.Party` instances with role `customer`. 8.11 attaches health scores, onboarding plans, renewals, and QBRs directly to `core.Party`.
  * `core.Document` (`apps/core/models/Document.py`) — generic document attachment store for QBR slide decks, customer onboarding deliverables, and signed renewal contracts.
- **`apps/crm`**:
  * `crm.Opportunity` (`OPP-`) (`apps/crm/models/SalesForceAutomation/Opportunities.py`) — opportunity master. 8.11 renewal workflows generate and link expansion deals (`stage="Closed Won" / "Proposal"`) to existing opportunities.
  * `crm.Contact` / `crm.PartyRole` — primary client stakeholders, executive sponsors, and day-to-day champion contacts.
- **`apps/sales`**:
  * `sales.AccountPlan` (`ACPL-`) (`apps/sales/models/ContactAccountManagement/AccountPlans.py`) — strategic account plan master (`period_start`, `period_end`, `white_space_assessment`, `risk_summary`, `next_review_on`). 8.11 QBRs and health alerts cross-reference strategic account plans.
  * `sales.CPQQuote` (`CPQ-`) (`apps/sales/models/QuoteProposalCPQ/CPQQuotes.py`) — formal proposals for upsell/expansion contracts.
- **`apps/scm`**:
  * `scm.SalesOrder` (`SO-`) (`apps/scm/models/OrderManagement/SalesOrders.py`) — executed customer contracts/orders. 8.11 renewals link to original sales orders and track renewal subscriptions.
- **`apps/accounting`**:
  * `accounting.Currency` (`apps/accounting/models/GeneralLedger/Currencies.py`) — global ISO 4217 currency master. Used for contract ARR, MRR, renewal targets, and expansion value tracking.
- **`apps/accounts`**:
  * `accounts.User` (`settings.AUTH_USER_MODEL`) — Customer Success Managers (CSMs), Account Directors, Implementation Specialists, and Executive Reviewers.

### 1.3 Auto-Number Prefixes Swept & Confirmed Free
Checked across all 351 model classes across `apps/`:
- **`CHS`** (Customer Health Score): **FREE**
- **`CRN`** (Customer Renewal): **FREE** (also `RNW` is free)
- **`COB`** (Customer Onboarding): **FREE** (avoided `ONB`, which is used by `hrm.Program`)
- **`QBR`** (Quarterly Business Review): **FREE** (avoided `CBR`, which is used by `scm.ClientBillingRun`)

---

## 2. The five NavERP.md 8.11 bullets, verbatim

1. **Health Scoring & Risk Alerts** — Product usage, support tickets, NPS, and renewal risk composite scores.
2. **Renewal & Expansion Pipeline** — Upcoming renewal tracking, expansion opportunity creation, and churn risk flags.
3. **Onboarding & Implementation** — Customer onboarding playbooks, milestone tracking, and executive business reviews.
4. **Advocacy & Reference Management** — Customer reference programs, case study pipelines, and testimonial tracking.
5. **Quarterly Business Reviews (QBRs)** — Automated QBR scheduling, presentation templates, and outcome tracking.

### Bullet-by-bullet verdict & boundary ruling

| Bullet | Already owned / built? | What 8.11 adds | Architectural Ruling |
|---|---|---|---|
| **1. Health Scoring & Risk Alerts** | None in Sales. CRM 1.5 logs activities; Support tickets land in Helpdesk/CRM Case. | `CustomerHealthScore` (`CHS-`) — composite multidimensional health scorecard combining usage, support sentiment, NPS, and renewal risk into an automated 0-100 score, health band (Green/Yellow/Red), risk factor taxonomy, and early warning alert engine. | Reuses `core.Party` (customer). Aggregates support ticket counts and NPS sentiment; does NOT declare a duplicate account or ticket model. |
| **2. Renewal & Expansion Pipeline** | SCM 4.5 owns `SalesOrder` (`SO-`); CRM 1.2 owns `Opportunity` (`OPP-`). | `CustomerRenewal` (`CRN-`) — proactive renewal contract lifecycle manager tracking expiration dates, ARR/MRR at risk, renewal stages, churn probability, auto-renewal terms, and automated expansion deal creation into `crm.Opportunity`. | Reuses `scm.SalesOrder` for original orders and `crm.Opportunity` for expansion deals. Does NOT re-declare orders or opportunities. |
| **3. Onboarding & Implementation** | Sales 8.9 owns training `SalesCertification`; Core owns `Activity`. No customer onboarding engine exists. | `CustomerOnboarding` (`COB-`) — post-sale customer onboarding playbook executor tracking milestone checklists, kickoff, target go-live, time-to-value (TTV) metrics, progress %, and executive sponsor signoffs. | Reuses `core.Party` and `scm.SalesOrder`. Does NOT duplicate general ERP project tasks (Module 7). |
| **4. Advocacy & Reference Management** | Sales 8.9 owns enablement collateral. No customer advocacy or reference pipeline exists. | Advocacy readiness profile embedded in account health & QBRs + dedicated Advocacy Hub: referenceability status, allowable reference activities (calls, site visits, quotes), case study pipeline stages, testimonial repository, and advocate burnout protection. | Reuses `core.Party` and `core.Document` for approved case study collateral. |
| **5. Quarterly Business Reviews (QBRs)** | Sales 8.3 owns `AccountPlan` (`ACPL-`). No formal QBR/EBR scheduling or outcome tracker exists. | `CustomerBusinessReview` (`QBR-`) — automated QBR/EBR scheduling lifecycle, presentation template selection, executive attendees, value realization metrics, risk review, action items ledger, and outcome tracking. | Cross-references `sales.AccountPlan` and links to `CustomerHealthScore`. Does NOT re-declare account plans. |

---

## 3. Leaders surveyed (with source links)

1. **Gainsight CS** — The enterprise category leader in Customer Success Management, featuring composite Health Scorecards (DEAR framework), Renewal Center revenue forecasting, automated Call-To-Action (CTA) risk alerts, Success Plans, and Journey Orchestrator playbooks.  
   *Source:* [https://www.gainsight.com/customer-success/](https://www.gainsight.com/customer-success/)
2. **Totango (Totango + Catalyst)** — Prominent enterprise customer success platform known for modular SuccessBLOCs, SuccessPlays automated playbook triggers, multidimensional account health profiles, early churn warning triggers, and renewal pipeline forecasting.  
   *Source:* [https://www.totango.com/platform](https://www.totango.com/platform)
3. **ChurnZero** — Premier customer success software for subscription and SaaS businesses, featuring ChurnScore predictive health modeling, customer journey milestone tracking, automated Plays/Playbooks, Renewal Hub, and integrated NPS/CSAT surveys.  
   *Source:* [https://churnzero.com/platform/](https://churnzero.com/platform/)
4. **Planhat** — Modern data-driven Customer Platform unifying customer lifecycle operations: Time-to-Value (TTV) onboarding tracking, configurable health scoring matrices, automated playbooks, and real-time renewal/expansion pipeline management.  
   *Source:* [https://www.planhat.com/product/](https://www.planhat.com/product/)
5. **ClientSuccess** — Dedicated customer success management platform for B2B SaaS, featuring SuccessScore™ weighted metric categories, collaborative SuccessPlans for onboarding milestones, renewal forecast dashboards, and Executive Business Review (EBR/QBR) tracking.  
   *Source:* [https://www.clientsuccess.com/product/](https://www.clientsuccess.com/product/)
6. **Vitally** — High-velocity collaborative customer success platform featuring real-time Health Indicators, automated Playbook sequences, shared onboarding project milestones, QBR notes, and customer advocacy tracking.  
   *Source:* [https://www.vitally.io/product](https://www.vitally.io/product)
7. **Custify** — Automated customer success software engineered for B2B SaaS, providing dynamic 360-degree health scoring, churn alerts, step-by-step onboarding checklists, and account lifecycle stage progression.  
   *Source:* [https://www.custify.com/features](https://www.custify.com/features)
8. **Catalyst** — Customer Growth Platform (CGP) centering on proactive churn mitigation, health scorecard weighting, automated playbooks, renewal pipeline visibility, and expansion opportunity discovery.  
   *Source:* [https://catalyst.io/product](https://catalyst.io/product)
9. **SlapFive & Influitive** — Market-leading customer advocacy and reference management platforms specializing in reference request workflows, advocate burnout prevention, customer testimonial vaults, and case study pipeline stages.  
   *Source:* [https://www.slapfive.com/](https://www.slapfive.com/) and [https://influitive.com/reference-management/](https://influitive.com/reference-management/)

---

## 4. Feature catalog (this sub-module only)

### 4.1 Health Scoring & Risk Alerts (Bullet 1)
- **Multidimensional Composite Health Score** — Calculates an overall 0-100 score weighted across product usage, support tickets, sentiment/NPS, engagement, and renewal risk. · seen in: Gainsight, Totango, ChurnZero, Planhat, ClientSuccess · priority: table-stakes · spine: new table `CustomerHealthScore` (`CHS-`) pointing to `core.Party` · buildable now.
- **Traffic-Light Health Band Categorization** — Green (Healthy: 75-100), Yellow (Needs Attention: 50-74), Red (At Risk: 0-49) with score trend tracking (improving, stable, declining). · seen in: All 9 leaders · priority: table-stakes · spine: `CustomerHealthScore.health_band` · buildable now.
- **Structured Churn Risk Taxonomy** — Categorizes root causes of account risk: low adoption, executive sponsor turnover, unresolved support escalation, commercial/budget cut, product feature gap. · seen in: Gainsight, Totango, Custify · priority: common · spine: `CustomerHealthScore.risk_reasons` (`JSONField`) · buildable now.
- **Early Warning Risk Alert Triggers** — Proactive alert messages flagged when scores drop below thresholds or critical support tickets exceed SLAs. · seen in: ChurnZero, Gainsight (CTAs), Totango · priority: table-stakes · spine: `CustomerHealthScore.active_alert_message` + `is_churn_risk` · buildable now.
- **License & Seat Utilization Tracking** — Tracks active seats versus purchased entitlement to identify shelfware risk or expansion readiness. · seen in: Planhat, Custify, Gainsight · priority: common · spine: `CustomerHealthScore.license_utilization_pct` · buildable now.

### 4.2 Renewal & Expansion Pipeline (Bullet 2)
- **Renewal Contract Lifecycle Tracking** — Tracks upcoming contract expirations (90/60/30 day countdowns), current ARR/MRR at risk, and renewal stages (Upcoming, Engagement, Proposal Sent, Negotiation, Renewed, Churned). · seen in: Gainsight Renewal Center, ChurnZero Renewal Hub, Planhat · priority: table-stakes · spine: new table `CustomerRenewal` (`CRN-`) pointing to `core.Party` and `scm.SalesOrder` · buildable now.
- **Automated Expansion Opportunity Generation** — Generates and links upsell/cross-sell opportunities directly into `crm.Opportunity` when expansion headroom is identified. · seen in: Totango, Gainsight, Catalyst · priority: common · spine: FK `CustomerRenewal.expansion_opportunity` -> `crm.Opportunity` · buildable now.
- **Predictive Churn Risk & Retention Flagging** — Classifies renewal churn risk level (Low, Medium, High, Critical) with estimated renewal probability % to calculate weighted retention forecast. · seen in: ClientSuccess, ChurnZero, Totango · priority: table-stakes · spine: `CustomerRenewal.churn_risk_flag` + `renewal_probability_pct` · buildable now.
- **Auto-Renewal & Notice Period Management** — Captures evergreen/auto-renew status and strict cancellation notice windows (e.g. 30/60 days prior) to avoid unwanted contract churn. · seen in: Planhat, Gainsight, Salesforce SPM · priority: common · spine: `CustomerRenewal.auto_renewal` + `notice_period_days` · buildable now.
- **Multi-Currency Retention Forecasting** — Stores contract values and projected ARR in contract currency, converting to tenant functional currency via accounting exchange rates. · seen in: Gainsight, Planhat · priority: common · spine: FK `CustomerRenewal.currency` -> `accounting.Currency` · buildable now.

### 4.3 Onboarding & Implementation (Bullet 3)
- **Onboarding Playbook Framework** — Standardized onboarding blueprints tailored by customer tier (Enterprise High-Touch, Mid-Market Standard, Tech-Touch Automated). · seen in: Planhat, ChurnZero, ClientSuccess, Custify · priority: table-stakes · spine: new table `CustomerOnboarding` (`COB-`) pointing to `core.Party` · buildable now.
- **Milestone & Deliverable Tracking** — Checkable milestone ledger capturing kickoff, architecture design, data migration, user training, and UAT signoff with target and actual completion dates. · seen in: Planhat, Vitally, ClientSuccess · priority: table-stakes · spine: `CustomerOnboarding.milestones_config` (`JSONField`) · buildable now.
- **Time-to-Value (TTV) Measurement** — Measures elapsed calendar days from contract signature to first value milestone and production go-live. · seen in: Planhat, Gainsight, Totango · priority: differentiator · spine: `CustomerOnboarding.time_to_value_days` + `progress_pct` · buildable now.
- **Implementation Status & Blocker Management** — Explicit status progression (Not Started, In Progress, On Track, At Risk, Blocked, Completed) with free-text root blocker logging. · seen in: All 9 leaders · priority: table-stakes · spine: `CustomerOnboarding.status` + `CustomerOnboarding.blockers` · buildable now.
- **Executive Sponsor & Lead CSM Alignment** — Explicit attribution of implementation leadership to internal CSM user and customer executive sponsor. · seen in: ClientSuccess, Vitally · priority: common · spine: `CustomerOnboarding.lead_csm` -> `accounts.User` · buildable now.

### 4.4 Advocacy & Reference Management (Bullet 4)
- **Customer Reference Program Management** — Flags accounts as verified referenceable, tracking reference activities allowed (peer sales calls, site visits, RFP quotes). · seen in: Influitive, SlapFive, Vitally · priority: table-stakes · spine: managed via `CustomerBusinessReview` advocacy attributes and dedicated Advocacy Hub · buildable now.
- **Advocate Burnout Protection** — Tracks last reference date and limits monthly reference requests to protect key client advocates from fatigue. · seen in: Influitive, SlapFive · priority: differentiator · spine: `reference_request_count` + cooldown date · buildable now.
- **Case Study Pipeline Stages** — Tracks customer story development from candidate identification, interview, drafting, executive approval, to final publication. · seen in: SlapFive, Influitive · priority: common · spine: `case_study_status` + linked `core.Document` · buildable now.
- **Customer Testimonial & Quote Vault** — Searchable repository of verified customer quotes, quantified metrics achieved, and permission levels for sales enablement. · seen in: SlapFive, Influitive, Sales Enablement · priority: table-stakes · spine: `testimonial_quote` + advocacy ledger · buildable now.

### 4.5 Quarterly Business Reviews (QBRs) (Bullet 5)
- **Automated QBR Scheduling & Cadence Tracking** — Schedules recurring QBR/EBR reviews (Q1, Q2, Q3, Q4, Mid-Year, Annual) with automated calendar countdowns and next review due tracking. · seen in: Gainsight (Success Snapshots), ClientSuccess, Vitally · priority: table-stakes · spine: new table `CustomerBusinessReview` (`QBR-`) pointing to `core.Party` · buildable now.
- **Presentation Template Catalog** — Configurable review templates: Executive Value Review, Technical Architecture Deep Dive, Renewal & Contract Alignment, Strategic Expansion. · seen in: Gainsight, Vitally, ClientSuccess · priority: common · spine: `CustomerBusinessReview.template_type` · buildable now.
- **Stakeholder & Executive Attendee Logging** — Records internal CSM/executive attendees and client executive sponsors attending the review to gauge senior relationship depth. · seen in: ClientSuccess, Gainsight · priority: table-stakes · spine: `CustomerBusinessReview.client_attendees` + `internal_attendees` + `executive_sponsor_attended` · buildable now.
- **Value Realization & Objectives Tracking** — Documents quantified business outcomes achieved since last quarter, key challenges, and mutual goals for the upcoming quarter. · seen in: Gainsight, Planhat, ClientSuccess · priority: table-stakes · spine: `CustomerBusinessReview.key_achievements` + `challenges_and_risks` · buildable now.
- **Action Items & Accountability Ledger** — Post-meeting follow-up commitments with assigned owners, deadlines, and completion statuses. · seen in: ClientSuccess, Vitally · priority: table-stakes · spine: `CustomerBusinessReview.action_items` (`JSONField`) · buildable now.

---

## 5. Recommended build scope (this pass — exactly 4 models)

To maintain rigorous architectural symmetry with existing sales sub-modules (8.1–8.10), 8.11 implements **exactly 4 tenant-scoped models** inheriting `TenantNumbered` (`_base.py`), plus **5 derived workflow consoles/boards**:

### Model 1: `CustomerHealthScore` (`CHS-`) — `CustomerHealthScores.py`
Serves **Bullet 1** (Health Scoring & Risk Alerts).
- Fields:
  * `account`: `ForeignKey('core.Party', on_delete=models.CASCADE, related_name='sales_customer_health_scores')`
  * `evaluation_date`: `DateField(default=timezone.localdate)`
  * `overall_score`: `PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `health_band`: `CharField(max_length=15, choices=[('green', 'Healthy (75-100)'), ('yellow', 'Needs Attention (50-74)'), ('red', 'At Risk (0-49)')], default='green')`
  * `previous_score`: `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `score_trend`: `CharField(max_length=15, choices=[('improving', 'Improving'), ('stable', 'Stable'), ('declining', 'Declining')], default='stable')`
  * `product_usage_score`: `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `support_ticket_score`: `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `nps_sentiment_score`: `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `relationship_score`: `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `renewal_risk_score`: `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `risk_level`: `CharField(max_length=15, choices=[('low', 'Low Risk'), ('medium', 'Medium Risk'), ('high', 'High Risk'), ('critical', 'Critical Risk')], default='low')`
  * `risk_reasons`: `JSONField(default=list, blank=True)`
  * `active_alert_message`: `CharField(max_length=255, blank=True)`
  * `is_churn_risk`: `BooleanField(default=False)`
  * `license_utilization_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('80.00'), validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `open_support_tickets`: `PositiveIntegerField(default=0)`
  * `latest_nps`: `IntegerField(null=True, blank=True, validators=[MinValueValidator(-100), MaxValueValidator(100)])`
  * `last_activity_date`: `DateField(null=True, blank=True)`
  * `notes`: `TextField(blank=True)`
- Form excludes: `tenant`, `number`.

### Model 2: `CustomerRenewal` (`CRN-`) — `CustomerRenewals.py`
Serves **Bullet 2** (Renewal & Expansion Pipeline).
- Fields:
  * `account`: `ForeignKey('core.Party', on_delete=models.CASCADE, related_name='sales_customer_renewals')`
  * `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_owned_renewals')`
  * `original_order`: `ForeignKey('scm.SalesOrder', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_renewal_records')`
  * `renewal_name`: `CharField(max_length=160)`
  * `contract_reference`: `CharField(max_length=80, blank=True)`
  * `current_arr`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])`
  * `projected_renewal_arr`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])`
  * `expansion_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])`
  * `currency`: `ForeignKey('accounting.Currency', on_delete=models.PROTECT, related_name='sales_customer_renewals')`
  * `renewal_date`: `DateField()`
  * `target_close_date`: `DateField()`
  * `stage`: `CharField(max_length=25, choices=[('upcoming', 'Upcoming (90+ Days)'), ('engagement', 'Active Engagement'), ('proposal_sent', 'Renewal Proposal Sent'), ('negotiation', 'Contract Negotiation'), ('renewed', 'Renewed (Closed-Won)'), ('expanded', 'Renewed & Expanded'), ('churned', 'Churned (Closed-Lost)'), ('contracted_down', 'Contracted Down')], default='upcoming')`
  * `churn_risk_flag`: `CharField(max_length=15, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='low')`
  * `renewal_probability_pct`: `PositiveSmallIntegerField(default=80, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `auto_renewal`: `BooleanField(default=False)`
  * `notice_period_days`: `PositiveIntegerField(default=60)`
  * `expansion_opportunity`: `ForeignKey('crm.Opportunity', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_renewal_expansions')`
  * `notes`: `TextField(blank=True)`
- Form excludes: `tenant`, `number`.

### Model 3: `CustomerOnboarding` (`COB-`) — `CustomerOnboardings.py`
Serves **Bullet 3** (Onboarding & Implementation).
- Fields:
  * `account`: `ForeignKey('core.Party', on_delete=models.CASCADE, related_name='sales_customer_onboardings')`
  * `lead_csm`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_managed_onboardings')`
  * `sales_order`: `ForeignKey('scm.SalesOrder', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_onboardings')`
  * `title`: `CharField(max_length=160)`
  * `playbook_template`: `CharField(max_length=30, choices=[('enterprise_high_touch', 'Enterprise High-Touch (90 Days)'), ('midmarket_standard', 'Mid-Market Standard (45 Days)'), ('smb_accelerated', 'SMB Accelerated (21 Days)'), ('tech_touch_automated', 'Tech-Touch Automated')], default='midmarket_standard')`
  * `stage`: `CharField(max_length=25, choices=[('kickoff', 'Kickoff & Alignment'), ('architecture_design', 'Architecture & Solution Design'), ('configuration', 'System Configuration'), ('data_migration', 'Data Migration'), ('training', 'User & Admin Training'), ('uat_testing', 'User Acceptance Testing'), ('go_live', 'Production Go-Live'), ('completed', 'Completed & Handed to CS'), ('stalled', 'Stalled / On Hold')], default='kickoff')`
  * `status`: `CharField(max_length=15, choices=[('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('on_track', 'On Track'), ('at_risk', 'At Risk'), ('blocked', 'Blocked'), ('completed', 'Completed')], default='in_progress')`
  * `kickoff_date`: `DateField(default=timezone.localdate)`
  * `target_go_live_date`: `DateField()`
  * `actual_go_live_date`: `DateField(null=True, blank=True)`
  * `time_to_value_days`: `PositiveIntegerField(null=True, blank=True)`
  * `progress_pct`: `PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `executive_sponsor_name`: `CharField(max_length=120, blank=True)`
  * `executive_sponsor_email`: `EmailField(blank=True)`
  * `milestones_config`: `JSONField(default=list, blank=True)`
  * `blockers`: `TextField(blank=True)`
  * `success_criteria`: `TextField(blank=True)`
- Form excludes: `tenant`, `number`.

### Model 4: `CustomerBusinessReview` (`QBR-`) — `CustomerBusinessReviews.py`
Serves **Bullet 5** (Quarterly Business Reviews) AND **Bullet 4** (Advocacy & Reference Management).
- Fields:
  * `account`: `ForeignKey('core.Party', on_delete=models.CASCADE, related_name='sales_customer_business_reviews')`
  * `lead_csm`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_led_qbrs')`
  * `account_plan`: `ForeignKey('sales.AccountPlan', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_qbr_reviews')`
  * `title`: `CharField(max_length=160)`
  * `review_period`: `CharField(max_length=20, choices=[('q1', 'Q1 Review'), ('q2', 'Q2 Review'), ('q3', 'Q3 Review'), ('q4', 'Q4 Review'), ('mid_year', 'Mid-Year Review'), ('annual', 'Annual Executive Review')], default='q1')`
  * `review_year`: `PositiveIntegerField(default=2026)`
  * `scheduled_date`: `DateField()`
  * `completed_date`: `DateField(null=True, blank=True)`
  * `status`: `CharField(max_length=20, choices=[('scheduled', 'Scheduled'), ('materials_prepared', 'Materials Prepared'), ('conducted', 'Conducted / Completed'), ('follow_up_sent', 'Follow-Up Action Items Sent'), ('cancelled', 'Cancelled')], default='scheduled')`
  * `template_type`: `CharField(max_length=30, choices=[('executive_value', 'Executive Value & ROI Review'), ('technical_roadmap', 'Technical Architecture & Roadmap'), ('renewal_alignment', 'Renewal & Partnership Alignment'), ('operational_cadence', 'Standard Operational Cadence')], default='executive_value')`
  * `executive_sponsor_attended`: `BooleanField(default=False)`
  * `client_attendees`: `TextField(blank=True, help_text="Client executives and stakeholders present")`
  * `internal_attendees`: `TextField(blank=True, help_text="Internal account team attendees")`
  * `health_score_at_review`: `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  * `key_achievements`: `TextField(blank=True, help_text="Quantified value delivered and milestones reached")`
  * `challenges_and_risks`: `TextField(blank=True, help_text="Obstacles, product gaps, or service concerns discussed")`
  * `action_items`: `JSONField(default=list, blank=True)`
  * `is_referenceable`: `BooleanField(default=False, help_text="Did client confirm willingness to serve as reference?")`
  * `reference_types_permitted`: `JSONField(default=list, blank=True, help_text="['calls', 'site_visits', 'quotes', 'case_study']")`
  * `case_study_status`: `CharField(max_length=25, choices=[('none', 'Not Candidate'), ('identified', 'Candidate Identified'), ('interview_scheduled', 'Interview Scheduled'), ('drafting', 'Drafting Case Study'), ('approved', 'Client Approved'), ('published', 'Published')], default='none')`
  * `testimonial_quote`: `TextField(blank=True, help_text="Direct quote approved by client for marketing/sales")`
  * `notes`: `TextField(blank=True)`
- Form excludes: `tenant`, `number`.

### 5 Derived Interactive Views / Consoles (Pure Query Projections)
1. **Customer Health Console** (`sales:customer_health_console`) — Portfolio health matrix, high-risk churn radar, adoption analytics, and live risk alerts.
2. **Renewal & Retention Pipeline** (`sales:customer_renewal_pipeline`) — 90/60/30 day countdown funnel, ARR at risk by stage, churn warnings, and expansion deal creators.
3. **Onboarding & Implementation Hub** (`sales:customer_onboarding_hub`) — Milestone timeline, playbook stage tracking, average TTV metric, and blocker escalation queue.
4. **Advocacy & Reference Center** (`sales:customer_advocacy_hub`) — Referenceable account directory, advocate cooldown/burnout tracking, testimonial quote vault, and case study pipeline.
5. **Executive QBR Studio** (`sales:customer_qbr_studio`) — Calendar review schedule, presentation templates, attendee tracking, and action item follow-up workbench.

---

## 6. Belongs to sibling sub-modules (parked, not scoped here)
- **Strategic Account Plans (SWOT / Whitespace)**: Owned by **8.3 Contact & Account Management** (`sales.AccountPlan`).
- **Support Ticket Resolution & SLA Queues**: Owned by **CRM 1.4 / Customer Service Helpdesk** (`crm.Case`).
- **Detailed Gantt Charts & Resource Allocation**: Owned by **Module 7 Project Management** (`projects.ProjectTask`).
- **Post-Sales Marketing Case Study Collateral Storage**: Generic file attachments use `core.Document`; marketing distribution belongs to **8.13 Marketing Alignment & Attribution**.

---

## 7. Deferred (later passes / integrations)
- **Direct Telemetry Ingestion (Segment / Mixpanel / Pendo)**: Real-time API event streams feed into external analytics webhooks (deferred to Module 20/23).
- **Automated Survey Email Dispatch (NPS / CSAT)**: Bi-directional email survey dispatchers defer to CRM communication engine.
- **AI Churn Prediction Neural Net**: Advanced ML churn model retraining belongs in Module 23 (AI & Intelligent Automation).
