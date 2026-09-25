# Research — Sub-module 8.3: Contact & Account Management (Module 8 — Sales Management System, `sales`)

Research date: 2026-09-24

## Scope lock

This catalog covers only the five bolded bullets in `NavERP.md:1320-1325`:

1. Account Hierarchy & Parent-Child
2. Contact Profiles & Enrichment
3. Relationship Mapping
4. Account Segmentation & Tiering
5. Account Plans & Growth Strategies

It does not cover lead management, opportunity/pipeline management, forecasting, CPQ, orders, territory administration, activity management, enablement, compensation, customer-success operations, analytics, or marketing attribution. Those are sibling sub-modules and are parked below.

## Repo state checked first

- The checkout is intentionally dirty with unrelated concurrent work. This research run did not edit or stage any existing path.
- `apps/core/navigation.py:2167-2178` has a live `LIVE_LINKS["8.1"]` block only. There is no `LIVE_LINKS["8.2"]` or `LIVE_LINKS["8.3"]`, so 8.3 is currently on the roadmap.
- `apps/sales/` exists in the working tree. Its live package exports, URL conf, admin registrations, and migrations currently cover 8.1 only:
  - `apps/sales/models/__init__.py:1-10` re-exports only the four lead models.
  - `apps/sales/forms/__init__.py:1-10`, `apps/sales/views/__init__.py:1-47`, and `apps/sales/urls/__init__.py:1-15` import only Lead Management.
  - `apps/sales/admin.py:1-83` registers only the four lead models.
  - `apps/sales/migrations/0001_initial.py` creates only lead score, qualification, routing, and nurture models; migrations `0002` and `0003` only alter lead fields.
- Physical source files for an 8.2 design exist under `apps/sales/models/OpportunityPipeline`, `OpportunityTeams`, `CompetitiveIntelligence`, and `OpportunityOutcomes`, but they are not re-exported by `apps.sales.models`, imported by the live views/forms/URLs, registered in admin, or present in a Sales migration. They are therefore **not verified runtime entities** and 8.3 must not FK to them.
- `NavERP-ERD.md` is intent, not as-built truth. In particular, its Module 8 row still names Opportunity, Quote, Forecast, Territory, and CommissionPlan as Sales additions (`NavERP-ERD.md:470`), while the actual code shows CRM already owns Opportunity, Quote, and Territory and no Sales Forecast or CommissionPlan model exists.

### Verified existing entities

| Existing entity | Verified as-built evidence | 8.3 ownership decision |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5-21`; one person or organization, tenant-scoped | Canonical account/contact identity. Never create `sales.Account` or `sales.Contact`. |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5-31`; includes `customer`, `contact`, `lead`, `partner`, etc. | Continue to express customer/contact roles. Do not duplicate them in Sales. |
| `core.Address` | `apps/core/models/Address.py:5-20` | Canonical address row. 8.3 must not add another address master. |
| `core.ContactMethod` | `apps/core/models/ContactMethod.py:5-17` | Canonical email/phone/mobile value. Enrichment may propose or apply through it, not create another per-account phone table. |
| `core.PartyRelationship` | `apps/core/models/PartyRelationship.py:5-22`; kinds `employee_of`, `contact_of`, `subsidiary_of`, `reports_to` | Reuse for generic corporate/reporting edges. It has no account-specific role, influence, sentiment, effective dates, or uniqueness constraint, so it is insufficient by itself for a buying-center map. |
| `crm.AccountProfile` | `apps/crm/models/CoreData/Accounts.py:26-58`; one-to-one `Party`, industry, website, phone/email, annual revenue, employee count, `parent_account`, owner | CRM-owned firmographic profile and the existing parent pointer. Reuse it; do not create another account master or second parent field. |
| `crm.ContactProfile` | `apps/crm/models/CoreData/Contacts.py:6-37`; one-to-one person `Party`, job/department, email/phone/mobile, one primary `account`, LinkedIn, owner | CRM-owned contact profile. Its single `account` is the current primary affiliation; additional account-specific roles need an association, not a second contact row. |
| CRM account/contact pages | `apps/crm/views/CoreData/Accounts.py:22-107`; `Contacts.py:15-93`; account detail already lists direct contacts and child accounts | Sales should add analysis/workspace pages that link to these canonical records, not parallel CRUD. |
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py:5-94`; account/contact Parties, owner, amount, stage, close date | Reuse for account-plan opportunity links, pipeline context, and revenue potential. No Sales opportunity copy. |
| `crm.Product` / `crm.Quote` | `Products.py:5-45`; `Quotes.py:5-120` | CRM quote catalog. Reuse only as existing context; CPQ/catalog ownership stays in 8.5. |
| `crm.HealthScore` / `HealthScoreHistory` | `apps/crm/models/CustomerSuccess/HealthScores.py:31-140`; one current account score plus append-only history | **Canonical account-health owner.** 8.3 must read and surface it, not create a second account-health score/history. Full post-sale health remains CRM 1.11 / Sales 8.11 scope. |
| `crm.CrmTask`, `CommunicationLog`, `CalendarEvent`, `core.Activity`, `core.AuditLog` | Verified in CRM Activity Management and core models | Reuse for plan follow-up, interaction recency, and audit. No Sales task/activity/audit model. |
| `accounting.Invoice` / `InvoiceLine` | `apps/accounting/models/AccountsReceivable/Invoices.py:6-99`; invoice points to `core.Party` and an optional `accounting.Currency` | Read-only source for realized account revenue. Never write or duplicate AR/GL. |
| `scm.SalesOrder` / `SalesOrderLine` | `apps/scm/models/OrderManagement/SalesOrders.py:20-251`; canonical customer order owned by SCM | Read-only source for commercial history. Order lifecycle remains 8.6. |
| `core.ConsentPurpose` / `ConsentRecord` | `apps/core/models/Consent.py:18-110`; lawful basis, append-only Party consent, current-consent helper | Reuse for enrichment/privacy governance. External enrichment must not invent a parallel consent log. |
| `core.CustomFieldDefinition` / `CustomFieldValue` | `apps/core/models/CustomField.py:18-85` | Optional later tenant extension point; not a reason to add open-ended account/contact fields now. |

### Important as-built gaps

1. **There is no `core.Account` or `core.Contact` model.** Accounts and contacts are `core.Party` identities plus CRM profiles. The current CRM profiles themselves duplicate some address/email/phone values, but 8.3 must not add a third copy.
2. `crm.AccountProfile.parent_account` already provides one parent per account and the account detail page already shows child accounts. `AccountForm` excludes self and limits the picker to same-tenant organizations (`apps/crm/forms/CoreData/Accounts.py:29-35`), but there is no transitive cycle guard on the model. Direct model writes can also attach a cross-tenant or non-organization parent. Hardening this CRM field is required before hierarchy rollups are trusted.
3. `crm.ContactProfile.account` permits only one primary account. Current account stakeholders are just contacts attached through that field; there are no decision-maker, champion, blocker, influence, sentiment, strength, or effective-date attributes.
4. The current 8.2 `OpportunityTeamMember` source is not live and concerns internal opportunity collaboration, not external account buying-center stakeholders.
5. `crm.Product` and `scm.Item` are different catalogs with no reliable cross-catalog mapping. `SalesOrderLine` explicitly says quote-converted CRM products are not mapped to inventory items and can remain unmapped (`SalesOrders.py:185-205`). Exact product-level white-space cannot yet be claimed as complete data.
6. `crm.AccountProfile.annual_revenue` has no currency. It is firmographic metadata and must not be summed with `accounting.Invoice.total` or `crm.Opportunity.amount` as if it were realized revenue.

## Leaders surveyed (current official sources)

Eight leading commercial CRM/sales/account-management products were reviewed. The product set is deliberately limited to account/contact management; general pipeline, lead, and forecasting features were excluded.

1. **Salesforce Sales Cloud** — account hierarchies, primary and indirect contact relationships, contact-to-multiple-accounts roles, account plans, objectives, tactics, and Data 360 enrichment. Sources: [Account/contact relationships](https://trailhead.salesforce.com/content/learn/modules/accounts_contacts_lightning_experience/understand-account-and-contact-relationships-lightning), [Account Plan data model](https://developer.salesforce.com/docs/platform/data-models/guide/key-account-management-account-plan.html), [Copy-field enrichment](https://help.salesforce.com/s/articleView?id=sf.c360_a_create_a_copy_field_enrichment.htm&language=en_US&type=5).
2. **Microsoft Dynamics 365 Sales** — account hierarchies, editable account org charts, primary/assistant/decision-maker/influencer/blocker labels, LinkedIn employment-change review, interaction analytics, and relationship health. Sources: [Hierarchy visualizations](https://learn.microsoft.com/en-us/dynamics365/sales/create-activate-hierarchy-visualizations), [Manage org charts](https://learn.microsoft.com/en-us/dynamics365/sales/manage-org-charts), [LinkedIn Sales Navigator](https://learn.microsoft.com/en-us/dynamics365/sales/linkedin/install-sales-navigator), [Relationship analytics](https://learn.microsoft.com/en-us/dynamics365/sales/relationship-analytics-overview).
3. **HubSpot CRM / Sales Hub** — many-to-many contact/company associations, one required primary company, custom association labels, lifecycle stages, target accounts, configurable enrichment, overwrite policy, and an enrichment activity log. Sources: [Associations](https://knowledge.hubspot.com/records/associate-records), [Lifecycle stages](https://knowledge.hubspot.com/records/use-lifecycle-stages), [Enrichment settings](https://knowledge.hubspot.com/records/manage-data-enrichment-settings).
4. **Zoho CRM** — parent/member accounts, contact roles and reporting managers, Zia enrichment, configurable field mapping, and account segmentation/classification. Sources: [Account FAQ](https://help.zoho.com/portal/en/kb/crm/faqs/sales-force-automation/account-management/articles/account-management), [Contact roles/reporting fields](https://help.zoho.com/portal/en/kb/crm/customize-crm-account/customizing-fields/articles/modify-special-fields), [Zia data enrichment](https://help.zoho.com/portal/en/kb/crm/faqs/zia/articles/faqs-data-enrichment).
5. **Oracle Fusion Cloud Sales** — one-parent account hierarchy, hierarchy revenue rollups, contact purposes and address/email/phone verification, classifications, and structured business/account plans with objectives, SWOT, teams, activities, and linked opportunities. Sources: [Account hierarchies](https://docs.oracle.com/en/cloud/saas/sales/faimp/account-hierarchies.html), [Account plans](https://docs.oracle.com/en/cloud/saas/sales/fasqa/what-are-business-plans-in-oracle-sales.html), [Territory account assignment](https://docs.oracle.com/en/cloud/saas/sales/faswa/overview-of-territory-account-assignment.html).
6. **SAP Sales Cloud** — account/party relationships, buying centers, account hierarchy, ABC classification, target groups, social profiles, and account plans with plan types, SWOT topics, wallet category, business figures, sales planning, and action plans. Sources: [Maintain account data](https://help.sap.com/docs/sap-cloud-for-customer/solution-guide-for-sap-sales-cloud/maintain-account-data), [SAP Sales Cloud Solution Guide](https://help.sap.com/doc/300d71dc3d2141fb8941453f95b85541/CSS_SHIP/en-US/CX_NG_CSS_SalesSolGuide.pdf), [Account Planning setup guide](https://help.sap.com/doc/21aeb6bd07ae450cbd8e0427487dfe4a/CSS_SHIP/en-US/df80fae25b4c4132b2643a50a3fdfee9.pdf).
7. **Pipedrive** — parent/daughter/related organization relationships, organization/contact enrichment, field-level preview, fill-empty-only behavior, and bulk enrichment. Sources: [Related organizations](https://support.pipedrive.com/en/article/related-organizations), [Data enrichment](https://support.pipedrive.com/en/article/data-enrichment).
8. **Freshsales / Freshsuccess** — multi-tier account hierarchy, hierarchy rollups for activity/financials/deals/health/NPS, auto-profile enrichment, and tier/lifecycle/dynamic account segmentation. Sources: [Account hierarchy](https://crmsupport.freshworks.com/support/solutions/articles/50000008694-account-hierarchy), [Account segmentation](https://crmsupport.freshworks.com/support/solutions/articles/50000008699-account-segmentation), [Enrichment](https://support.freshsales.io/support/solutions/articles/217625-does-freshsales-enrich-lead-contact-and-account-information-).

### Product support matrix

A dash means the reviewed official source did not establish that capability; it does not mean the product definitely lacks it.

| Product | Parent/global account model | Enrichment and validation | Stakeholder/org mapping | Segmentation | Account plan / health |
|---|---|---|---|---|---|
| Salesforce | Parent tree; global vs location-specific enterprise model | Data 360 copy/related-list enrichment | Contact-to-multiple-accounts, roles, reporting structure, account teams | Custom account tier and Salesforce segmentation | Structured account plan/objectives/tactics; related object analyses |
| Dynamics 365 | Parent account and visual hierarchies | LinkedIn sync/change review; address suggestions | Org chart, reporting lines, primary, assistant, decision maker, influencer, blocker | Segments and territory/assignment dimensions | Relationship KPIs and health; no structured account-plan object established in reviewed sources |
| HubSpot | Association-based company hierarchy | Automatic/continuous/manual enrichment, field mapping, overwrite rules, log | Primary plus multiple companies, association labels, contact-to-contact manager | Lifecycle, target accounts, saved segments, ABM | Buying groups and target-account workspace; no native objective-bearing account-plan object established |
| Zoho | Parent account with member accounts | Zia public-data/email-signature enrichment and mapping | Contact roles, reporting manager, contact hierarchy | Account tags/custom fields/territories | Contact purposes; no comparable structured account-plan object established |
| Oracle | One parent per account, hierarchy rollups | Address/email/phone verification and party data | Contact purposes and account teams | Account type/size/industry/named-account classifications | Business plan with objectives, strategies, SWOT, teams, actions, opportunities |
| SAP | Account hierarchy and party relationships | Social profiles, LinkedIn, address services | Buying center, contact relationships, account teams | ABC class, target groups, classifications | Account plan types, SWOT, wallet, business figures, sales planning, actions |
| Pipedrive | Parent/daughter/related organizations | Provider-backed single/bulk enrichment, empty-field policy | Organizations/people lists; no deep org-chart source established | Labels and enriched firmographics | Account/deal context; no structured account-plan object established |
| Freshworks | Multi-tier parent hierarchy and rollups | Automatic social/public profile enrichment | Contacts/key stakeholders in Account 360 | Tier, lifecycle, hierarchy labels, dynamic smart segments | Health/NPS rollups and Freshsuccess goals; account-plan detail not established |

## Feature catalog (8.3 only)

Priority meanings:

- **table-stakes** — nearly every credible leader supports it, or it is necessary for trustworthy account/contact data.
- **common** — most mature products support it or it is a normal enterprise B2B requirement.
- **differentiator** — only some leaders provide the advanced form.

### 1. Account Hierarchy & Parent-Child

- **One canonical account per legal/operating entity with at most one parent** — supports subsidiaries, divisions, branches, and locations without copying account identities. Seen in Salesforce, Zoho, Oracle, SAP, Pipedrive, and Freshworks. **Priority: table-stakes.** **Spine:** reuse `crm.AccountProfile.parent_account -> core.Party`. **Build now as a hardened CRM field plus an 8.3 hierarchy explorer; no hierarchy table.**
- **Cycle-, tenant-, and kind-safe parent assignment** — parent must be a different same-tenant organization, and no descendant may become an ancestor of the account. Current CRM form prevents only self-parenting. Seen as an integrity requirement across hierarchical products. **Priority: table-stakes.** **Spine:** validate `crm.AccountProfile` in its model/service and every write path. **Build now.**
- **Root/global account rollup** — a parent shows child accounts, contacts, opportunities, orders, invoices, and other commercial facts; a location-specific account remains the operational record. Seen in Salesforce, Oracle, and Freshworks. **Priority: common.** **Spine:** derive descendants from `AccountProfile.parent_account`; aggregate `crm.Opportunity`, `scm.SalesOrder`, and `accounting.Invoice` by Party. **Build now; no stored rollup counters.**
- **Currency-safe hierarchy reporting** — show realized, open, weighted, and potential values grouped by `accounting.Currency`; never sum unlike currencies or mix CRM `annual_revenue` with ledger revenue. Seen in enterprise hierarchy/revenue reporting products. **Priority: common.** **Spine:** verified `accounting.Currency`, `accounting.Invoice`, `crm.Opportunity`. **Build now.**
- **Root, leaf, parent, child, and descendant filters** — let staff pivot between legal entity and global account without moving records. Seen in Freshworks and standard hierarchy UX. **Priority: common.** **Spine:** derived metadata over `AccountProfile.parent_account`. **Build now.**
- **Non-hierarchical account relations such as affiliate, partner, joint venture, or preferred supplier** — useful but outside the first corporate-family-tree scope. Seen in Pipedrive's related organizations. **Priority: differentiator.** **Spine:** `core.PartyRelationship` currently has only four fixed kinds; do not overload or silently expand a shared CHOICES list in 8.3. **Defer a governed relationship-type pass.**
- **Hierarchy-driven authorization** — commercial suites often support it, but Salesforce explicitly documents that an account hierarchy does not itself grant parent access. **Priority: table-stakes security constraint.** **Spine:** every query still filters `tenant=request.tenant`; parent rollup must never widen access. **Never infer permissions from hierarchy.**

### 2. Contact Profiles & Enrichment

- **One shared contact identity and rich CRM profile** — account/contact pages must show the same person and not create a Sales clone. Seen in every leader. **Priority: table-stakes.** **Spine:** `core.Party` + `crm.ContactProfile`; link to existing CRM pages. **Reuse; no Sales CRUD master.**
- **Business-only enrichment fields with field-level preview and overwrite policy** — staff select proposed values, protected/manual values are not silently replaced, and accepted values can be traced. Seen especially in HubSpot and Pipedrive; Zoho supports field mapping. **Priority: common.** **Spine:** new append-only `PartyEnrichmentEvent`; accepted values route through one apply service. **Build the data contract and manual/proposal flow now; provider calls later.**
- **Email and phone validation** — distinguish syntactically valid from deliverable/reachable; do not treat a regex check as a successful email send. Oracle explicitly offers verification; HubSpot/Pipedrive enrich these fields. **Priority: common.** **Spine:** proposed values in `PartyEnrichmentEvent`, canonical accepted values in `core.ContactMethod` with CRM-profile compatibility updates in the same transaction. **Build local status/proposal support now; external verification later.**
- **Social profile linking and employment-change review** — LinkedIn/social URLs support identity context; a changed employer should create a review, not silently move a contact. Seen in Dynamics, HubSpot, Zoho, SAP, and Pipedrive. **Priority: common.** **Spine:** existing `crm.ContactProfile.linkedin`; `PartyEnrichmentEvent.kind='employment_change'`. **Build review state now; LinkedIn sync later.**
- **Source, confidence, requester, reviewer, timestamp, and error evidence** — staff must know where a value came from and whether it was merely proposed or applied. Seen in HubSpot's enrichment log and provider products. **Priority: table-stakes for trust/governance.** **Spine:** fields on `PartyEnrichmentEvent` plus `core.AuditLog`; no raw provider payload. **Build now.**
- **Automatic, continuous, and bulk enrichment** — mature products schedule refreshes and bulk runs. Seen in HubSpot, Pipedrive, and Zoho. **Priority: differentiator.** **Spine:** no verified Sales provider, connector, worker, or outbound-HTTP layer. **Integration/later; never add a background-run table in 8.3.**
- **Duplicate detection, merge review, and provider opt-out propagation** — important but identity governance is broader than this sub-module. Seen in Dynamics, Freshworks, and provider-based enrichment. **Priority: differentiator/security.** **Spine:** no canonical merge service was verified. **Defer to CRM identity hardening; do not merge Parties in 8.3.**
- **Lawful-basis and permission gate** — business identifiers may be sent to an enrichment provider only under a tenant-approved basis and purpose. HubSpot gates permissions; Pipedrive assigns controller/processor duties; Microsoft warns about monitoring/privacy. **Priority: table-stakes.** **Spine:** verified `core.ConsentPurpose`, `core.ConsentRecord`, and `current_consent()`. **Build metadata now; outbound processing later and tenant-admin gated.**

### 3. Relationship Mapping

- **Account-specific stakeholder roles** — a contact's meaning changes by account: decision maker, economic buyer, champion, influencer, blocker, technical evaluator, procurement, end user, or advisor. Seen in Dynamics, Salesforce, HubSpot, Zoho, and SAP buying centers. **Priority: table-stakes/common.** **Spine:** new `AccountStakeholder` linking two verified `core.Party` rows. **Build now.**
- **Primary and indirect account affiliations** — one contact may work across several organizations, but one account remains primary. Seen in Salesforce and HubSpot. **Priority: common.** **Spine:** `crm.ContactProfile.account` remains the primary account; additional affiliations and their account-specific roles live in `AccountStakeholder`. **Build now; no duplicate contact.**
- **Influence, attitude, relationship strength, status, and effective dates** — “stakeholder” alone cannot tell staff who can approve, support, or block. Seen most clearly in Dynamics and SAP. **Priority: common.** **Spine:** `AccountStakeholder`; interaction recency is derived, not manually maintained. **Build now.**
- **Account coverage matrix** — answer whether decision maker, champion, influencer, and blocker roles are present and whether one primary contact exists. Seen in Dynamics' default labels and enterprise buying-center tools. **Priority: common.** **Spine:** derived from `AccountStakeholder` plus `ContactProfile.account`. **Build now as a board.**
- **Customer organization/reporting-line chart** — visualize contacts, manager, direct reports, assistants, and reporting paths. Seen in Dynamics, Zoho, Salesforce reporting structures, and SAP. **Priority: common.** **Spine:** `core.PartyRelationship(kind='reports_to')` for the graph plus `AccountStakeholder` for account-specific role. **Build now as a derived view; no second org-chart model.**
- **Interaction recency, response, and relationship-strength indicators** — derive last/next interaction, response ratio, and communication balance from existing activity. Seen in Dynamics and SAP. **Priority: common.** **Spine:** `crm.CommunicationLog`, `crm.CalendarEvent`, `crm.CrmTask`, `core.Activity`; no second activity store. **Build an explainable local view; Microsoft Exchange integration later.**
- **Who-knows-whom introductions and inferred relationship networks** — Dynamics and SAP infer internal connectors from communication history. **Priority: differentiator.** **Spine:** no verified Exchange/email graph or staff-connection model. **Integration/later; do not present inferred connections as verified org-chart facts.**

### 4. Account Segmentation & Tiering

- **Current tier plus lifecycle stage** — classify accounts consistently enough to prioritize coverage and service intensity. Freshworks explicitly recommends tier + lifecycle as the starting point; HubSpot supplies ordered company lifecycle stages. **Priority: table-stakes.** **Spine:** one current `AccountClassification` per account. **Build now.**
- **Strategic importance, revenue-potential band, and wallet category** — combine human intent with firmographics and pipeline rather than relying on revenue alone. Oracle/SAP expose account classifications and wallet/business figures. **Priority: common.** **Spine:** `AccountClassification`; open pipeline and realized revenue remain derived from verified CRM/accounting/scm records. **Build now.**
- **Classification rationale, effective date, review date, and accountable classifier** — tier changes need business context and periodic review. Seen as governance across enterprise account programs. **Priority: common.** **Spine:** fields on `AccountClassification`; `core.AuditLog` for history. **Build now.**
- **Hierarchy-level segmentation and rollup** — a global account can inherit a deliberately chosen tier/label while child entities retain local lifecycle values. Seen in Freshworks. **Priority: common.** **Spine:** explicit classification plus derived hierarchy views; never overwrite children automatically. **Build now.**
- **Dynamic multi-condition segments and automation** — HubSpot and Freshworks save reusable rules over usage, revenue, renewal, interaction, and other metrics. **Priority: differentiator.** **Spine:** the first-pass `AccountClassification` is a single reviewed state, not a rule engine. **Defer reusable segment definitions; provide saved filters and deterministic boards now.**
- **Stored score that silently combines tier, lifecycle, and health** — rejected. Classification is human-governed intent; health is a separate canonical CRM fact; derived boards should expose their factors. **Priority: architecture constraint.** **Spine:** no combined score in 8.3.

### 5. Account Plans & Growth Strategies

- **One plan per account and planning period** — supports strategy history and avoids one never-ending account note. Seen in Salesforce, Oracle, and SAP account-plan objects. **Priority: common; table-stakes for strategic-account motions.** **Spine:** new numbered `AccountPlan`. **Build now.**
- **Business drivers, measurable objectives, strategy, and SWOT** — capture why the account matters, what must change, and how success is assessed. Seen directly in Oracle, SAP, and Salesforce. **Priority: common.** **Spine:** structured text fields on `AccountPlan`; `core.AuditLog` for changes. **Build now.**
- **Account-specific growth initiatives and white-space notes** — record cross-sell, upsell, new-business, or whitespace plays and their rationale. Seen in SAP/Oracle account planning and Freshworks expansion segments. **Priority: common.** **Spine:** `AccountPlan` fields and linked `crm.Opportunity`; do not add a product master. **Build now, but label automated product coverage as incomplete until `crm.Product` and `scm.Item` mapping exists.**
- **Plan-linked opportunities** — connect the long-term strategy to concrete deals while `crm.Opportunity` remains the deal. Seen in Oracle. **Priority: common.** **Spine:** many-to-many link to verified `crm.Opportunity`, constrained to the same tenant and account. **Build now; no plan-opportunity child model in the first pass.**
- **Risk and health context without duplicate health** — show the current `crm.HealthScore`, trend, open cases, stale activity, and other explainable factors. Seen in Oracle/SAP and already implemented for CRM 1.11. **Priority: common.** **Spine:** read `crm.HealthScore`/`HealthScoreHistory` and existing signals; no Sales health score or history. **Build now for customers; derived pre-sale relationship indicators for prospects.**
- **Owner, next review, and task follow-through** — a plan without accountability and cadence is a document dump. Seen in Oracle/SAP account planning. **Priority: common.** **Spine:** plan owner/review fields plus existing `crm.CrmTask`; no Sales task model. **Build now.**
- **Plan templates, benchmark plans, and AI-generated goals/SWOT** — Oracle, SAP, Salesforce, and HubSpot offer more assisted forms. **Priority: differentiator.** **Spine:** no verified approved template, document-generation, or AI-governance workflow for this domain. **Defer; never let generated text become a committed plan without human review.**
- **QBRs, onboarding plans, renewal workflow, advocacy, and churn tasks** — commercially common but explicitly owned by NavERP 8.11 and already partially represented by CRM 1.11. **Parked below.**

## Recommended build scope (exactly four new models)

Recommended count: **four tenant-scoped models**. The account hierarchy and health features are deliberately model-free extensions over verified existing state.

### 1. `ContactAccountManagement/PartyEnrichment.py` — `PartyEnrichmentEvent` (unnumbered, append-evidence)

**Purpose:** record an enrichment or validation attempt, its source and confidence, proposed field changes, privacy basis, and whether staff accepted or rejected them. It is not a second contact/account profile and does not store raw provider payloads or credentials.

**Key fields/choices:**

- `tenant -> core.Tenant`.
- `party -> core.Party`; any same-tenant person or organization.
- `kind`: `firmographic`, `contact`, `email_validation`, `phone_validation`, `social`, `employment_change`, `duplicate_check`.
- `source_kind`: `manual`, `provider`, `email_signature`, `linkedin`, `import`, `api`.
- `source_name`, `source_reference`; no secret or access token.
- `status`: `proposed`, `applied`, `rejected`, `no_match`, `failed`.
- `match_confidence` nullable decimal constrained to 0..1.
- `changes` structured JSON: only an allowlisted key/value/confidence shape for concrete business fields such as job title, department, LinkedIn URL, work email, phone/mobile, website, industry, employee count, and annual revenue. Never model paths, Python, URLs to arbitrary fetches, or free-form secret values.
- `legal_basis_purpose -> core.ConsentPurpose`; required when `source_kind='provider'`, `linkedin`, or another external transfer occurs.
- `requested_by`, `reviewed_by -> AUTH_USER_MODEL`; timestamps `occurred_at`, `applied_at`, `created_at`.
- `idempotency_key` optional but unique with tenant for replayed provider events.
- `error_code` short stable code; sanitized failure summary only, never a raw response that may contain unrelated personal data.

**Lifecycle/invariants:** list/detail plus POST-only request/apply/reject actions; no ordinary edit/delete. Applying a value routes through one service that validates the allowlist, tenant, Party kind, overwrite policy, and update target, writes `core.ContactMethod` plus the CRM compatibility projection in one transaction, and writes `core.AuditLog`. Local/manual proposals and validation results are buildable now; no outbound HTTP ships in 8.3.

### 2. `ContactAccountManagement/AccountStakeholders.py` — `AccountStakeholder` (unnumbered)

**Purpose:** one account-specific buying-center relationship. It reuses Parties and adds only the contextual role/influence facts that generic `PartyRelationship` cannot store.

**Key fields/choices:**

- `tenant -> core.Tenant`.
- `account -> core.Party`, required same-tenant `kind='organization'`.
- `contact -> core.Party`, required same-tenant `kind='person'`, never equal to `account`.
- `role`: `decision_maker`, `economic_buyer`, `champion`, `influencer`, `blocker`, `technical_evaluator`, `procurement`, `end_user`, `advisor`, `other`.
- `influence`: `high`, `medium`, `low`, `unknown`.
- `attitude`: `positive`, `neutral`, `negative`, `unknown`.
- `relationship_strength`: `strong`, `moderate`, `weak`, `unknown`.
- `status`: `active`, `former`.
- `valid_from`, `valid_to`; `notes`; inherited timestamps.
- Unique `(tenant, account, contact, role)`; indexes `(tenant, account, status)`, `(tenant, contact, status)`, and `(tenant, role, attitude)`.

**Invariants:** `crm.ContactProfile.account` remains the one primary account; no `is_primary` or duplicate primary-account field here. A contact can hold several roles at one account and different roles at different accounts. `core.PartyRelationship(kind='reports_to')` remains the reporting-line source; this model is not projected into it and does not create a second org chart. Interaction recency/strength indicators are derived from existing activity; `relationship_strength` is a human assessment, not an auto-computed number.

### 3. `ContactAccountManagement/AccountClassifications.py` — `AccountClassification` (unnumbered, one current row per account)

**Purpose:** current, human-governed Sales segmentation for prioritization. It stores intent, not a second health score or financial aggregate.

**Key fields/choices:**

- `tenant -> core.Tenant`.
- `account` **OneToOne** -> same-tenant `core.Party` with `kind='organization'`.
- `tier`: `strategic`, `key`, `growth`, `nurture`.
- `lifecycle_stage`: `prospect`, `active_customer`, `expansion_candidate`, `dormant`, `former_customer`. At-risk health remains `crm.HealthScore`, not this field.
- `strategic_priority`: `high`, `medium`, `low`.
- `revenue_potential`: `very_high`, `high`, `medium`, `low`, `unknown`.
- `wallet_category`: `none`, `small`, `medium`, `large`, `full_wallet`.
- `rationale`, `effective_on`, `review_due_on`, `classified_by -> AUTH_USER_MODEL`; timestamps.
- Unique `account`; indexes `(tenant, tier, lifecycle_stage)` and `(tenant, strategic_priority, review_due_on)`.

**Invariants:** no `annual_revenue`, open-pipeline amount, invoice total, health score, or hierarchy rollup is copied here. Those are read from `crm.AccountProfile`, `crm.Opportunity`, `accounting.Invoice`, and `crm.HealthScore`. Changes use normal audited edit/upsert; this is not a dynamic segment-rule table.

### 4. `ContactAccountManagement/AccountPlans.py` — `AccountPlan` [ACPL-]

**Purpose:** a time-bounded strategic growth plan for an account, distinct from CRM onboarding plans and from a sales opportunity.

**Key fields/choices:**

- Sales `TenantNumbered` equivalent, `NUMBER_PREFIX = "ACPL"` (the proposed prefix was checked against current `NUMBER_PREFIX` declarations and is free).
- `account -> core.Party`, required same-tenant organization.
- `title`; `period_start`, `period_end` with a valid ordered range.
- `status`: `draft`, `active`, `review_due`, `completed`, `archived`.
- `owner -> AUTH_USER_MODEL`, required same-tenant active user; this is the plan owner, while `crm.AccountProfile.owner` remains the account owner.
- `business_drivers`, `objectives`, `strategy`; `strengths`, `weaknesses`, `opportunities`, `threats`.
- `white_space_assessment`, `growth_initiatives`, `risk_summary`.
- `next_review_on`; inherited `number`, `created_at`, `updated_at`.
- `related_opportunities` ManyToMany to verified `crm.Opportunity`; every selected opportunity must be same-tenant and belong to the same account. No copied deal fields.
- Unique `(tenant, number)`; index `(tenant, account, status)` and `(tenant, owner, next_review_on)`.

**Invariants:** no stored revenue, weighted pipeline, product holdings, product gaps, account-health score, tasks, QBR, onboarding plan, or renewal workflow. Those are derived or linked from existing owners. White-space is explicitly an assessment in this first pass; automated product coverage is marked incomplete until CRM `Product` and SCM `Item` have a governed mapping. Plan follow-up creates/reuses `crm.CrmTask`.

### Reused/hardened features with no new model

1. **Account hierarchy explorer and rollup** — `crm.AccountProfile.parent_account` plus a cycle-safe recursive service. No `AccountHierarchy`, `GlobalAccount`, or second parent field.
2. **Account/contact enrichment apply service** — accepted values update the verified CRM/core fields through one writer. No new email/phone/social/address tables.
3. **Account 360 / growth workspace** — aggregate over the canonical Party, CRM profile, opportunities, stakeholders, classification, plans, orders, invoices, activity, documents, and health. No `Account360` table.
4. **White-space and coverage boards** — derive facts and label missing product mapping/health inputs honestly. No stored counters or fake zero.
5. **Hierarchy segmentation and currency-safe rollups** — read-only services over existing records.

## NavERP 8.3 bullet coverage

| NavERP bullet | Concrete 8.3 implementation | Honest limit |
|---|---|---|
| Account Hierarchy & Parent-Child | Harden existing `AccountProfile.parent_account`; cycle/tenant/kind checks; tree/root/descendant explorer; currency-safe global-account rollup | Non-hierarchical affiliate/JV relation types and hierarchy-based authorization are not added |
| Contact Profiles & Enrichment | Reuse Party/ContactProfile/ContactMethod; `PartyEnrichmentEvent`; source/confidence/overwrite/review/lawful-basis evidence; local validation | Provider APIs, LinkedIn sync, bulk/continuous workers, and merge are deferred |
| Relationship Mapping | `AccountStakeholder`; multi-account indirect affiliations; role/influence/attitude/strength/status; existing `reports_to` for org chart; coverage and activity views | Who-knows-whom and inferred email networks are deferred |
| Account Segmentation & Tiering | `AccountClassification`; tier, lifecycle, strategic priority, potential band, wallet category, rationale/review; hierarchy and pipeline views | Dynamic reusable segment-rule engine is deferred; health remains separate |
| Account Plans & Growth Strategies | `AccountPlan`; objectives, business drivers, strategy, SWOT, whitespace/growth/risk, owner/review, linked opportunities, existing tasks and health | Exact product whitespace awaits catalog mapping; AI plans, QBRs, onboarding, renewal, and advocacy are deferred/parked |

## Belongs to sibling sub-modules (parked, not scoped)

- **8.1 Lead Management** — lead capture, behavioral scoring, qualification, routing, nurture, and lead-to-account/contact/opportunity conversion orchestration. Reuse the CRM-owned conversion path; do not create Sales Party writers.
- **8.2 Opportunity & Pipeline Management** — opportunity stages, pipeline configuration, team selling, competitive intelligence, and closure outcomes. Reuse `crm.Opportunity`; do not depend on unregistered 8.2 source classes.
- **8.4 Sales Forecasting** — commit/best-case scenarios, manager overrides, quota attainment, forecast accuracy, and AI prediction. 8.3 only supplies read-only account rollups.
- **8.5 Quote & Proposal Management** — CPQ, product catalog authority, price books, quote versions, proposals, approvals, and quote-to-order. CRM `Product`/`Quote` remain context only.
- **8.6 Order Management** — order capture, amendments, cancellations, fulfillment, reorder, and revenue recognition. Read `scm.SalesOrder`; do not add a Sales order.
- **8.7 Territory & Quota Management** — territory assignment/rebalancing, named-account coverage rules, and quotas. Existing `crm.Territory` is read-only context in 8.3.
- **8.8 Sales Activity & Task Management** — universal task/calendar/call/email capture and planning. Reuse CRM/core activity models.
- **8.9 Sales Enablement** — playbooks, content, training, call recording, coaching, and the governed battle-card library.
- **8.11 Customer Success & Account Management** — post-sale health scoring, renewal/expansion, onboarding, advocacy, and QBRs. Existing CRM 1.11 already owns the health ledger and onboarding plan; 8.3 surfaces it.
- **8.12 Sales Analytics & Intelligence** — cross-account dashboards, benchmark cohorts, velocity, and predictive account scoring. 8.3 supplies deterministic account facts only.
- **8.13 Marketing Alignment & Attribution** — campaign influence, ABM program operations, intent signals, and multi-touch attribution.
- **8.18 Integration & API Hub** — outbound provider connectors, enrichment jobs, LinkedIn/Microsoft/email synchronization, webhooks, and scheduled refresh workers.

## Deferred / later integrations

- **Third-party enrichment, email/phone verification, and deduplication providers** — requires tenant-configured credentials, privacy/legal-basis checks, egress controls, timeouts, response-size limits, replay-safe jobs, and sanitized errors. Store the `PartyEnrichmentEvent` contract now; perform no outbound HTTP in 8.3.
- **LinkedIn and Microsoft relationship intelligence** — employment-change alerts, who-knows-whom, interaction analytics, and internal introducer suggestions depend on licensed integrations and verified staff identities.
- **Automatic/continuous enrichment** — scheduler/worker infrastructure and bulk-run operational state are not present as verified Sales entities.
- **Exact product white-space** — `crm.Product` and `scm.Item` lack a governed mapping, and accounting invoice lines are free text. Do not report complete coverage until that ownership gap is reconciled.
- **Dynamic segment definitions and automations** — start with the one current reviewed classification, saved filters, and deterministic boards. A reusable segment-rule model/editor can follow if real use requires it.
- **AI-generated account plans, summaries, and SWOT** — useful differentiator, but needs Module 23 governance, approved sources, review-before-save, and audit. Do not present generated text as committed strategy.
- **Record-level account hierarchy access** — never infer authorization from parentage. A future sharing/ACL design is platform security work, not an account-management side effect.
- **Non-hierarchical corporate relations and account merges** — require governed relationship types and identity-resolution/merge semantics beyond this pass.
- **QBRs, onboarding, renewal/expansion pipeline, and advocacy** — owned by 8.11 / CRM 1.11.

## Build handoff guardrails

- Do not create `sales.Account`, `sales.Contact`, a second email/phone/address table, a second parent pointer, a second account-health score/history, a second opportunity, or a second order/product/financial ledger.
- All four recommended models carry `tenant`; all FK/M2M selections and every list/detail/edit query must be tenant-scoped. Cross-tenant IDs must return 404 on staff pages.
- `AccountStakeholder.account` must be a same-tenant organization; `contact` a different same-tenant person. `AccountClassification`/`AccountPlan` accounts and `PartyEnrichmentEvent.party` must be same-tenant and use the correct Party kind.
- Add transitive cycle prevention to the existing CRM account-parent write path before computing roots, descendants, or rollups. Hierarchy visibility is not authorization.
- `crm.ContactProfile.account` remains the primary account; `core.PartyRelationship(reports_to)` remains the reporting graph. Do not create parallel primary-account, org-chart, or relationship projections.
- `crm.HealthScore`/`HealthScoreHistory` remain the only stored account health truth. Pre-sales relationship indicators must be clearly labeled derived and explainable.
- Never sum `AccountProfile.annual_revenue`, `crm.Opportunity.amount`, and `accounting.Invoice.total`. Group actual/opportunity values by verified currency and show missing currency data honestly.
- Enrichment events store bounded, allowlisted business-field proposals and provenance, not raw provider payloads, credentials, sensitive consumer data, or arbitrary fetch/model instructions.
- Sales pages link to `crm:account_detail` and `crm:contact_detail` for identity/profile edits rather than offering parallel account/contact CRUD.
- The 8.2 physical source classes are not runtime dependencies; verify their later re-export, migration, URL, admin, and navigation integration before any 8.3 FK is considered.
