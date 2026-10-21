# Research — Sub-module 8.14: Partner & Channel Management (Module 8 — Sales Management System, sales)

**Sub-module:** `8.14 Partner & Channel Management` (NavERP.md, Module 8 — Sales Management System)  
**App:** `apps/sales` (existing app — this run EXTENDS it; no scaffold, no `config/` wire-up)  
**Run date:** 2026-10-21  
**Target sub-module:** `8.14`  

---

## 1. Repo state checked first

### 1.1 LIVE_LINKS built so far in Module 8
From `apps/core/navigation.py`:
- Built and active: `8.1` (Lead Management), `8.2` (Opportunity & Pipeline), `8.3` (Contact & Account), `8.4` (Opportunity Teams), `8.5` (Opportunity Outcomes), `8.6` (Quote/Proposal/CPQ), `8.7` (Territory & Quota), `8.8` (Sales Activity & Tasks), `8.9` (Sales Enablement), `8.10` (Incentive Compensation), `8.11` (Sales Forecasting), `8.12` (Sales Analytics & Intelligence), `8.13` (Marketing Alignment & Attribution).
- **Target Sub-module 8.14 is the next unbuilt sub-module** in Module 8 (`LIVE_LINKS["8.14"]` is currently absent).

### 1.2 Spine entities verified to exist / NOT exist (grep evidence)
Verified via class grep across `apps/core/models/`, `apps/crm/models/`, `apps/accounting/models/`, `apps/scm/models/`, and `apps/sales/models/`:
- `core.Party` (`apps/core/models/Party.py:5`) — Verified exists. All partners, partner contacts, and prospective/client accounts are instances of `Party`.
- `core.PartyRole` (`apps/core/models/PartyRole.py:5`) — Verified exists. `ROLE_CHOICES` includes `("partner", "Partner")`, `("customer", "Customer")`, and `("contact", "Contact")`.
- `core.PartyRelationship` (`apps/core/models/PartyRelationship.py:8`) — Verified exists. Links contacts to partner accounts and partner accounts to subsidiaries.
- `core.Document` (`apps/core/models/Document.py:5`) — Verified exists. Used for partner agreements, NDAs, and co-branded collateral attachments.
- `crm.Opportunity` (`OPP-`, `apps/crm/models/SalesForceAutomation/Opportunities.py:5`) — Verified exists. Primary opportunity master into which approved deal registrations convert.
- `crm.Lead` (`LEAD-`, `apps/crm/models/CoreData/Leads.py:5`) — Verified exists. Partner-sourced inbound leads.
- `crm.Territory` (`TER-`, `apps/crm/models/SalesForceAutomation/Territories.py:10`) — Verified exists. Geographic/segment territory master used in channel conflict detection.
- `accounting.Currency` (`apps/accounting/models/GeneralLedger/Currencies.py:6`) — Verified exists. Standard currency master for deal amounts and revenue targets.
- `scm.SalesOrder` (`SO-`, `apps/scm/models/OrderManagement/SalesOrders.py:20`) — Verified exists. Downstream order execution entity.
- `sales.TerritoryRule` (`TRG-`, `apps/sales/models/TerritoryQuotaManagement/TerritoryRules.py:117`) — Verified exists. Rules assigning accounts to territories.
- `sales.AccountPlan` (`ACPL-`, `apps/sales/models/ContactAccountManagement/AccountPlans.py:11`) — Verified exists. Enterprise account plans.
- `sales.EnablementContent` (`ECN-`, `apps/sales/models/SalesEnablement/EnablementContents.py:45`) — Verified exists. Sales collateral master.
- `sales.SalesCertification` (`SCTF-`, `apps/sales/models/SalesEnablement/SalesCertifications.py:32`) — Verified exists. Internal rep accreditation master.
- `accounts.User` (`settings.AUTH_USER_MODEL`) — Verified exists. Channel Account Managers (CAMs), Partner Managers, Direct Sales Reps, and Channel Chiefs.

### 1.3 Ownership rulings (L29 / L36 / L37) — what 8.14 must NOT declare
1. **Never declare a duplicate Partner, Company, or Account table:** Partners and partner contacts are `core.Party` instances with `core.PartyRole` (`role="partner"`). 8.14 extends the partner record with a tenant-scoped `PartnerProfile` (`PTR-`) holding channel-specific metadata, tiers, and certification targets.
2. **Never declare a duplicate Opportunity table:** Deal registrations are temporary opportunity claims that convert into `crm.Opportunity` (`OPP-`).
3. **Never declare a duplicate Territory master:** Territory rules and channel boundaries reference `crm.Territory` (`TER-`).
4. **Never declare a second financial ledger (L29):** Partner revenue and commission figures represent sales operational rollups. Financial settlements and commissions defer to Module 2 Accounting and Module 8.10 Incentive Compensation.

---

## 2. NavERP.md scope (authoritative)

```markdown
### 8.14 Partner & Channel Management
- **Partner Recruitment & Onboarding** — Application workflows, certification requirements, and partner portal setup.
- **Deal Registration & Protection** — Partner-submitted opportunities, approval workflows, and conflict resolution.
- **Partner Portal & Collaboration** — Shared pipeline views, co-branded collateral, and joint account planning.
- **Partner Performance Tracking** — Revenue by partner, certification status, and tier progression (bronze/silver/gold/platinum).
- **Channel Conflict Management** — Direct vs. indirect deal detection, territory rules, and escalation protocols.
```

Five feature bullets. Every bullet must be fully represented in the data architecture and navigable interfaces.

---

## 3. Commercial leaders surveyed

Survey of 10 market-leading Partner Relationship Management (PRM) and Channel Ecosystem platforms:

| # | Product | Positioning | Official Source / Reference | Key Contributions to Catalog |
|---|---|---|---|---|
| 1 | **Salesforce PRM** (Experience Cloud for Partners) | Enterprise CRM-integrated partner portal | [salesforce.com – PRM](https://www.salesforce.com/products/sales-cloud/tools/partner-relationship-management/) | Automated CRM deduplication check on deal submit; time-bound exclusivity locks; lead distribution with SLA; partner tiering driving margin discounts; unified direct/indirect pipeline visibility. |
| 2 | **Impartner PRM** | Pure-play enterprise PRM platform | [impartner.com](https://impartner.com/) | Automated onboarding journey workflows; rules-driven tier promotion/demotion engine; multi-tier approval matrices; deal expiration & exclusivity clocks; automated duplicate conflict checks. |
| 3 | **Channeltivity** | Mid-market & tech channel PRM | [channeltivity.com](https://www.channeltivity.com/) | High-adoption deal registration; automated conflict avoidance rules of engagement; Joint Business Planning (JBP) modules; partner tier compliance audits; margin protection guarantees. |
| 4 | **Allbound PRM** | Partner enablement and co-selling | [allbound.com](https://allbound.com/) | Co-branded collateral generator and asset distribution; deal registration with margin protection; partner playbooks; tier progression gamification and badges. |
| 5 | **Magentrix PRM** | Channel partner management & portal | [magentrix.com](https://www.magentrix.com/) | Strict rules of engagement enforcement; automated domain/account conflict detection; multi-level approval workflows; partner certification and training compliance tracking. |
| 6 | **Zift Solutions (ZiftONE / Unifyr)** | Enterprise PRM & through-channel marketing | [ziftsolutions.com](https://ziftsolutions.com/) | Milestone-driven onboarding pathways; multi-criteria tier progression (revenue + training + marketing actions); deal protection; time-to-first-deal velocity metrics. |
| 7 | **PartnerStack** | B2B SaaS partnership platform | [partnerstack.com](https://partnerstack.com/) | Partner recruitment pipelines; structured tier progressions; automated link/lead attribution; partner performance leaderboards; automated email reminders on expiring deals. |
| 8 | **WorkSpan** | Ecosystem Cloud & Co-selling | [workspan.com](https://www.workspan.com/) | Joint account planning (JBP) pairing partner with target accounts; co-sell motions (`partner_led`, `joint_pursuit`); shared pipeline views; multi-enterprise revenue attribution. |
| 9 | **Crossbeam** | Ecosystem account mapping & overlap network | [crossbeam.com](https://crossbeam.com/) | Pre-deal account mapping; partner-to-direct overlap detection; automated conflict alerts prior to deal registration; secure pipeline collaboration. |
| 10 | **ZINFI Unified Channel Management** | Global channel management suite | [zinfi.com](https://www.zinfi.com/) | Multi-tier escalation workflows (CAM -> Channel Chief -> CRO); contract sign-off tracking; territory-based partner distribution rules; compliance scoring. |

### Cross-Product Consensus (Industry Standard PRM Mechanics)
1. **Deal Registration as the Primary Conflict Firewall:** Deal registration is the bedrock of channel trust. Partners submit prospective deals to lock in margin protection (typically 10%–20% higher margin) and exclusivity for 90–180 days.
2. **Instant Conflict Detection:** The PRM cross-references the submitted customer domain, company name, and territory against existing CRM opportunities and prior partner registrations before granting approval.
3. **Multi-Level Escalation Protocols:** Disputes (direct vs. indirect rep collisions, or two partners claiming the same account) follow a formal 3-level escalation ladder: Level 1 Channel Account Manager (CAM) -> Level 2 Channel Director/Chief -> Level 3 Executive Adjudication (VP Sales/CRO).
4. **Multi-Metric Tier Progression:** Tiers (`Bronze`, `Silver`, `Gold`, `Platinum`) are determined not merely by revenue, but by a balanced scorecard: annual closed revenue + active certified personnel count + deals registered.
5. **Joint Business & Account Planning (JBP):** Strategic co-selling moves beyond ad-hoc registrations into structured Joint Account Plans that document target enterprise clients, joint value propositions, co-sell motions, and mutual revenue goals.

---

## 4. Deduplicated, prioritised feature catalog

Priority definitions:
- **`table-stakes`**: Present in almost all surveyed PRMs; core to baseline channel operations.
- **`common`**: Present in the majority of leaders; standard for mature channel programs.
- **`differentiator`**: Specialized capability that distinguishes top-tier enterprise platforms.

---

### 4.1 Partner Recruitment & Onboarding

| # | Feature | Description | Seen In | Priority | Spine Mapping | Feasibility |
|---|---|---|---|---|---|---|
| R1 | **Partner Application Intake** | Web/portal application capturing company details, partner type, target markets, business model, and expected annual volume. | Impartner, Channeltivity, PartnerStack | `table-stakes` | New `PartnerProfile.onboarding_status` + `core.Party` | Buildable now |
| R2 | **Application Review & Approval Workflow** | Multi-state review (`applied` -> `under_review` -> `approved` -> `rejected`), capturing rejection reasons, reviewer, and approval timestamps. | Impartner, Salesforce PRM, ZiftONE | `table-stakes` | Fields on `PartnerProfile` + `accounts.User` FK | Buildable now |
| R3 | **Partner Role Assignment & Spine Integration** | Automatic assignment of `core.PartyRole` (`role="partner"`) upon application approval, linking contact persons via `PartyRelationship`. | Standard NavERP spine | `table-stakes` | Reuses `core.PartyRole` and `core.PartyRelationship` | Buildable now |
| R4 | **Onboarding Milestone Checklist** | Step-by-step progress tracker: Application approved -> Agreement/NDA signed -> Portal access activated -> Initial certification completed -> First deal registered. | Impartner, ZiftONE, Magentrix | `common` | Fields on `PartnerProfile` | Buildable now |
| R5 | **Partner Agreement & NDA Tracking** | Records agreement signing date, agreement version, and links to executed PDF document. | Impartner, ZINFI | `common` | Reuses `core.Document` (`DOC-`) via FK on `PartnerProfile` | Buildable now |
| R6 | **Self-Service External Partner Portal Authentication** | Dedicated external customer/partner identity provider login (SAML/OAuth). | Salesforce PRM, Magentrix | `common` | External auth provider | Deferred (Integration) |
| R7 | **Automated SCORM LMS Courseware Delivery** | Embedded interactive video/exam LMS for partner training. | Impartner, ZiftONE | `differentiator` | External LMS | Deferred (Integration) |

---

### 4.2 Deal Registration & Protection

| # | Feature | Description | Seen In | Priority | Spine Mapping | Feasibility |
|---|---|---|---|---|---|---|
| D1 | **Partner Opportunity Registration** | Structured submission form: end-customer company, deal title, estimated deal value, currency, close date, partner rep contacts, solution area. | All surveyed leaders | `table-stakes` | New `DealRegistration` (`DLR-`) | Buildable now |
| D2 | **Registration Approval SLA Workflow** | Formal workflow (`submitted` -> `under_review` -> `approved` -> `rejected` -> `expired` -> `converted`) with review timestamp and SLA tracking. | Salesforce PRM, Impartner, Channeltivity | `table-stakes` | Fields on `DealRegistration` + `accounts.User` FK | Buildable now |
| D3 | **Automated Conflict / Duplicate Detection Flag** | Automatic cross-check against active `crm.Opportunity` and other `DealRegistration` records matching the customer account or name. | Salesforce PRM, Channeltivity, Magentrix | `table-stakes` | Model validation / probe logic on `DealRegistration` | Buildable now |
| D4 | **Time-Bound Protection Exclusivity Window** | Exclusivity clock setting protection start and end dates (e.g. 90, 120, or 180 days). Closes deal to other partners and direct reps. | Impartner, Channeltivity, Magentrix | `table-stakes` | `DealRegistration.protection_start_date` / `protection_end_date` / `exclusivity_status` | Buildable now |
| D5 | **Margin / Pricing Protection** | Guaranteed partner margin percentage (e.g. 15.00% or 20.00%) locked in upon deal registration approval. | Impartner, Channeltivity, Allbound | `table-stakes` | `DealRegistration.protected_margin_pct` | Buildable now |
| D6 | **Exclusivity Extension Workflow** | Allows partner to request a 30-day or 60-day protection extension if proof of active customer evaluation is provided. | Impartner, Channeltivity | `common` | `DealRegistration.extension_count` + extension action | Buildable now |
| D7 | **One-Click Opportunity Conversion** | Approved deal registration converts directly into an active `crm.Opportunity` (`OPP-`), preserving partner attribution and margin terms. | Salesforce PRM, Channeltivity | `table-stakes` | FK `DealRegistration.opportunity` (`crm.Opportunity`) | Buildable now |
| D8 | **Hyperscaler Cloud Marketplace Co-Sell Sync** | Automated push to AWS ACE / Azure Partner Center / Google Cloud Co-sell. | Impartner, WorkSpan | `differentiator` | Hyperscaler API connector | Deferred (Integration) |

---

### 4.3 Partner Portal & Collaboration

| # | Feature | Description | Seen In | Priority | Spine Mapping | Feasibility |
|---|---|---|---|---|---|---|
| C1 | **Shared Partner Pipeline View** | Dedicated pipeline view showing all deal registrations and active co-sold opportunities for the partner organization. | Salesforce PRM, WorkSpan, Allbound | `table-stakes` | Filtered view on `DealRegistration` + `crm.Opportunity` | Buildable now |
| C2 | **Joint Account Planning (JBP)** | Documented strategic account plan between vendor and partner for a specific client account: target revenue, co-sell motions, and milestones. | WorkSpan, Channeltivity, Crossbeam | `common` | New `JointAccountPlan` (`JAP-`) | Buildable now |
| C3 | **Co-Sell Motion Specification** | Categorizes joint engagement model: `partner_led`, `vendor_led`, `joint_pursuit`, or `services_only`. | WorkSpan, Crossbeam | `common` | `JointAccountPlan.co_sell_motion` | Buildable now |
| C4 | **Co-Branded Collateral Association** | Links partner-accessible sales collateral, battlecards, and co-branded solution briefs to joint plans and partner profiles. | Allbound, ZiftONE, Impartner | `common` | Reuses `sales.EnablementContent` (`ECN-`) and `core.Document` (`DOC-`) | Buildable now |
| C5 | **Real-Time Crossbeam Overlap Synchronization** | Secure escrow-based account mapping API that calculates pipeline overlap without exposing account details. | Crossbeam, WorkSpan | `differentiator` | Third-party data mesh | Deferred (Integration) |

---

### 4.4 Partner Performance Tracking

| # | Feature | Description | Seen In | Priority | Spine Mapping | Feasibility |
|---|---|---|---|---|---|---|
| P1 | **Tier Progression System (Bronze/Silver/Gold/Platinum)** | Four-tier hierarchy directly implementing NavERP.md specification (`bronze`, `silver`, `gold`, `platinum`) with effective and review dates. | All surveyed leaders; explicit in NavERP.md | `table-stakes` | `PartnerProfile.tier` | Buildable now |
| P2 | **Revenue by Partner Tracking** | Tracks annual revenue target vs. actual closed-won revenue year-to-date across all partner-attributed deals and orders. | Impartner, Salesforce PRM, PartnerStack | `table-stakes` | `PartnerProfile.annual_revenue_target` / `actual_revenue_ytd` | Buildable now |
| P3 | **Certification Compliance Tracking** | Compares active certified staff count against the mandatory tier requirement (e.g. Gold requires 5 certified reps). | Impartner, ZiftONE, Magentrix | `table-stakes` | `PartnerProfile.required_certifications_count` / `active_certifications_count` | Buildable now |
| P4 | **Tier-Based Commercial Incentives** | Automatic assignment of base discount % and deal registration margin boost based on current tier. | Impartner, Channeltivity, Salesforce PRM | `common` | `PartnerProfile.base_discount_pct` / `deal_reg_margin_pct` | Buildable now |
| P5 | **Partner Performance Console & Leaderboard** | Aggregated executive console summarizing revenue by partner, deal registration win rate, tier distribution, and SLA adherence. | Impartner, PartnerStack, Salesforce PRM | `table-stakes` | Derived dashboard view (`partner_performance_console`) | Buildable now |
| P6 | **Market Development Funds (MDF) Request & Budget Ledger** | Sub-ledger managing marketing fund allocations, claim receipts, and reimbursements. | Impartner, Channeltivity, ZiftONE | `common` | Sibling expansion / MDF ledger | Deferred (Belongs to 8.10 / Marketing) |

---

### 4.5 Channel Conflict Management

| # | Feature | Description | Seen In | Priority | Spine Mapping | Feasibility |
|---|---|---|---|---|---|---|
| X1 | **Direct vs. Indirect Conflict Detection** | Detects collision between direct sales reps and channel partners pursuing the same prospect account or territory. | Salesforce PRM, Magentrix, Channeltivity | `table-stakes` | New `ChannelConflict` (`CCF-`) | Buildable now |
| X2 | **Partner vs. Partner Duplicate Dispute** | Identifies competing deal registrations submitted by different partners for the same prospective account. | Channeltivity, Magentrix | `table-stakes` | `ChannelConflict.conflict_type` | Buildable now |
| X3 | **Territory Rules Enforcement** | Enforces authorized partner geographic and segment territories, flagging out-of-territory deals. | ZINFI, Salesforce PRM | `table-stakes` | Reuses `crm.Territory` (`TER-`) via FK | Buildable now |
| X4 | **Multi-Tier Escalation Protocol** | Formal 3-stage escalation ladder: Level 1 Channel Account Manager (CAM) -> Level 2 Channel Chief -> Level 3 Executive (VP Sales / CRO). | ZINFI, ShareCRM, Channeltivity | `common` | `ChannelConflict.escalation_level` + `escalated_to` FK | Buildable now |
| X5 | **Conflict Adjudication & Revenue Split Resolution** | Enforces dispute resolutions: partner protected, direct awarded, revenue/commission split % (e.g. 50/50), or joint co-sell mandate. | Channeltivity, Salesforce PRM | `table-stakes` | `ChannelConflict.resolution_outcome` / `split_percentage` | Buildable now |
| X6 | **Conflict Audit Log & Resolution Precedent** | Durable documentation of adjudication rationale, evidence examined, and precedent notes to prevent repeat disputes. | Magentrix, ShareCRM | `common` | `ChannelConflict.resolution_rationale` | Buildable now |

---

## 5. Recommended build scope (1–4 model budget)

To cleanly satisfy all five NavERP feature bullets within the standard 1–4 model budget, Sub-module 8.14 is scoped as **4 tenant-scoped models** plus **1 derived console**, with verified spine reuse across `core.Party`, `core.PartyRole`, `crm.Opportunity`, `crm.Territory`, `accounting.Currency`, `core.Document`, and `accounts.User`:

| Entity / Model | Class Name | Number Prefix | NavERP 8.14 Feature Bullets Satisfied | Key Fields & Justification |
|---|---|---|---|---|
| **Partner Profiles** | `PartnerProfile` | `PTR` | **Partner Recruitment & Onboarding** & **Partner Performance Tracking** | Tenant FK, `partner` FK (`core.Party`), `partner_type` (reseller/var/si/msp/distributor/isv/referral), `onboarding_status` (applied/under_review/onboarding/active/suspended), `tier` (bronze/silver/gold/platinum), `tier_effective_date`, `tier_review_date`, `application_date`, `agreement_signed_at`, `agreement_document` FK (`core.Document`), `channel_manager` FK (`User`), `authorized_territory` FK (`crm.Territory`), `annual_revenue_target`, `actual_revenue_ytd`, `required_certifications_count`, `active_certifications_count`, `base_discount_pct`, `deal_reg_margin_pct`, `portal_access_enabled`. |
| **Deal Registrations** | `DealRegistration` | `DLR` | **Deal Registration & Protection** | Tenant FK, `partner` FK (`core.Party`), `customer_account` FK (`core.Party`), `deal_name`, `estimated_value`, `currency` FK (`Currency`), `expected_close_date`, `status` (submitted/under_review/approved/rejected/expired/converted/conflicted), `protection_start_date`, `protection_end_date`, `exclusivity_status` (pending/active/extended/expired/released), `protected_margin_pct`, `extension_count`, `is_conflicted`, `conflict_summary`, `opportunity` FK (`crm.Opportunity`), `reviewed_by` FK (`User`), `reviewed_at`. |
| **Joint Account Plans** | `JointAccountPlan` | `JAP` | **Partner Portal & Collaboration** (Joint Account Planning) | Tenant FK, `partner` FK (`core.Party`), `client_account` FK (`core.Party`), `plan_name`, `plan_year`, `period_start`, `period_end`, `status` (draft/active/in_review/achieved/abandoned), `target_revenue`, `actual_revenue`, `currency` FK (`Currency`), `vendor_lead` FK (`User`), `partner_lead_name`, `partner_lead_email`, `co_sell_motion` (partner_led/vendor_led/joint_pursuit/services_only), `strategic_objectives`, `joint_value_proposition`, `action_items`, `collateral_document` FK (`core.Document`). |
| **Channel Conflicts** | `ChannelConflict` | `CCF` | **Channel Conflict Management** | Tenant FK, `conflict_type` (direct_vs_indirect/partner_vs_partner/territory_overlap/named_account_infringement), `severity` (low/medium/high/critical), `status` (detected/under_investigation/escalated_l1/escalated_l2/escalated_l3/resolved/dismissed), `deal_registration` FK (`DealRegistration`), `opportunity` FK (`crm.Opportunity`), `claimant_partner` FK (`core.Party`), `competing_partner` FK (`core.Party`), `direct_sales_rep` FK (`User`), `client_account` FK (`core.Party`), `territory` FK (`crm.Territory`), `escalation_level` (l1_cam/l2_channel_chief/l3_executive_cro), `escalated_to` FK (`User`), `resolution_outcome` (pending/partner_favored/direct_favored/split_commission/co_sell_mandate/deal_cancelled), `split_percentage`, `resolution_rationale`, `resolved_by` FK (`User`), `resolved_at`. |
| *(Derived Console)* | `partner_performance_console` | — | **Partner Performance Tracking** & **Shared Pipeline Views** | Real-time computed dashboard: total partner revenue, deal registrations by status, tier breakdown (bronze/silver/gold/platinum), active conflict count, and certification compliance gauge. |

### 5.1 Prefix Collision Verification
Repository-wide regex check confirms that none of the chosen prefixes are currently in use anywhere in NavERP:
- `PTR` (Partner Profile) — **FREE** (0 matches)
- `DLR` (Deal Registration) — **FREE** (0 matches)
- `JAP` (Joint Account Plan) — **FREE** (0 matches)
- `CCF` (Channel Conflict) — **FREE** (0 matches)

---

## 6. Belongs to sibling sub-modules (parked, not scoped here)

1. **Lead Qualification & Inbound Routing** (`ROUT-`, `LNE-`): Lead scoring, qualification, and rep routing belong to Sales 8.1 (`apps/sales/models/LeadManagement/`). Partner-sourced leads route into `crm.Lead`.
2. **Direct Territory & Quota Modeling** (`TRG-`, `QPA-`, `TAS-`): Territory quota allocation and general rep assignments belong to Sales 8.7 (`apps/sales/models/TerritoryQuotaManagement/`). 8.14 references existing `crm.Territory` models for boundary rules.
3. **Internal Rep Enablement Content Authoring** (`ECN-`, `SPB-`): Authoring master sales collateral and playbooks belongs to Sales 8.9 (`apps/sales/models/SalesEnablement/`). 8.14 links partner collateral to existing `ECN-` and `core.Document` records.
4. **Partner Sales Commission Disbursements** (`CMPL-`, `CER-`, `CST-`): Formal financial commission compensation statements and plan calculations belong to Sales 8.10 (`apps/sales/models/IncentiveCompensation/`).
5. **Contract Lifecycle Management & Signatures** (`CTR-`, `SLA-`): Complex multi-party legal contract authoring, clause redlining, and digital signatures belong to Sales 8.15 (`apps/sales/models/ContractSubscription/`).
6. **Market Development Funds (MDF) Accounting**: Dedicated marketing co-op budgets, claim review vouchers, and accounting ledger disbursements belong to Marketing & Accounting integration.

---

## 7. Deferred (later passes / external integrations)

1. **External Partner Portal SAML/SSO Authentication**: Self-service portal access for external partner reps using identity providers (Okta, Azure AD B2B). (GAP)
2. **Third-Party Ecosystem Account Mapping Network (Crossbeam API)**: Automated real-time secure data escrow and overlap calculation. (GAP)
3. **Hyperscaler Marketplace Co-Sell Sync (AWS ACE / Microsoft Azure Partner Center)**: Automatic two-way synchronization of deal registrations to public cloud marketplace co-sell portals. (GAP)
4. **Embedded SCORM LMS Training & Video Exam Engine**: Interactive online video training courses and automated quiz scoring. (GAP)
5. **Electronic Signature API Integration (DocuSign / Adobe Sign)**: Automated webhook capture for partner agreement signature execution. (GAP)
