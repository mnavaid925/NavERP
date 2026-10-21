# Gap Register: Sub-module 8.14 Partner & Channel Management

**Module**: Module 8 — Sales Management System (`apps/sales/`)  
**Sub-module**: 8.14 Partner & Channel Management  
**Status**: Core Scope Complete — Every NavERP.md bullet ships a live, tenant-scoped, CRUD-complete page. The gaps below are **external dependencies and explicitly-declined capabilities**, not unfinished work inside the built surface.  
**Updated**: 2026-10-21  
**Contract**: `.claude/tasks/contract-sales-8.14.md` · **Research**: `.claude/tasks/research-sales-8.14.md` · **Plan**: `.claude/tasks/todo.md`  

---

## 1. As-Built Core Surface Status

- **Core Models**: `PartnerProfile` (`PTR-`), `DealRegistration` (`DLR-`), `JointAccountPlan` (`JAP-`), `ChannelConflict` (`CCF-`) — 4 entity folders / 4 models, all tenant-isolated via `TenantNumbered`, with cross-tenant FK validation guards (`_reject_foreign`), composite B-tree indexes, and audit logging.
- **CRUD Surface**: 4 entity CRUD sets — 4 list pages (search + filters + pagination + Actions), 4 detail pages (header stats, detail metadata, audit timestamps, POST-only deletes), 4 create pages, 4 edit pages, plus deal registration convert action.
- **Derived Console**: 1 — `partner_performance_console` (active partners count, total partner revenue, registered deals count, pipeline value, open conflicts count, average certifications, tier distribution, top performing partners, expiring registrations, recent disputes). **Every figure on it is derived; none is stored editable.**
- **Sidebar Integration**: `LIVE_LINKS["8.14"]` fully active in `apps/core/navigation.py`.
- **Migration**: `apps/sales/migrations/0025_partnerprofile_dealregistration_jointaccountplan_channelconflict.py`.
- **Seeder**: `_seed_partner_channel` in `apps/sales/management/commands/seed_sales.py` — dedicated, idempotent, verified across consecutive runs (2 partners, 2 deal registrations, 1 joint account plan, 1 channel conflict per tenant).
- **Spine Reuse**: **Zero duplicate masters (L36/L37).** `core.Party` (with `PartyRole.role="partner"` and role `"customer"`), `crm.Opportunity` (`OPP-`), `crm.Territory` (`TER-`), `core.Document` (`DOC-`), `accounts.User`, and `accounting.Currency` are all reused by FK, never redeclared.
- **Financial Postings**: **None (L29).** Partner revenue targets and actuals are operational sales figures. Formal commission statements belong to Sales 8.10 and settlements to Module 2 Accounting.

**Gaps on the As-Built Contract**: None.

---

## 2. Deferred / External Integration Register

| Gap ID | Owner | Status | Waiting For / Blocked On | Done When |
|---|---|---|---|---|
| `GAP-sales-8.14-01` | External Integrations / Auth Infrastructure | `[~] Deferred` | External identity provider (Okta, Azure AD, SAML 2.0 / OIDC) configuration and customer portal authentication subsystem. Partner reps currently access profiles via standard authenticated tenant accounts with `portal_access_enabled=True`. | External partner contacts can authenticate via delegated SAML/OIDC SSO into an isolated partner portal workspace with restricted record visibility scoped to their partner party. |
| `GAP-sales-8.14-02` | Partner Ecosystem / Data Engineering | `[~] Deferred` | Third-party account-mapping data network API (e.g., Crossbeam, Reveal) integration. Account overlap analysis is currently performed manually using Joint Account Plans and Customer Party links. | Bi-directional API sync securely exchanges hashed account lists with partner networks to automatically discover account overlaps, ecosystem presence, and co-selling opportunities. |
| `GAP-sales-8.14-03` | Cloud Marketplace Integrations | `[~] Deferred` | Cloud hyperscaler co-sell APIs (AWS ACE - APN Customer Engagements, Microsoft Azure Partner Center Co-sell). Deal registrations are currently managed natively inside NavERP. | Approved deal registrations can be dispatched and synchronized bidirectionally with AWS ACE and Microsoft Commercial Marketplace co-sell APIs with real-time status webhooks. |
| `GAP-sales-8.14-04` | Training & Enablement / LMS Engine | `[~] Deferred` | Embedded SCORM / xAPI compliant learning management system engine. Certification counts are currently tracked as quantitative metrics (`required_certifications_count`, `active_certifications_count`) on `PartnerProfile`. | Partner reps can launch, stream, and complete interactive training courses and proctored accreditation exams with automated certification issuance upon passing. |
| `GAP-sales-8.14-05` | Legal & Compliance / E-Signature | `[~] Deferred` | Electronic signature service provider integration (DocuSign, Adobe Acrobat Sign) and inbound webhook receivers. Signed agreements are currently attached as `core.Document` rows linked to `PartnerProfile.agreement_document`. | Partnership agreement templates can be dispatched directly for digital signature from the Partner Profile, with executed PDFs and audit trails automatically ingested upon completion via webhook. |

---

## 3. Explicitly Declined (not gaps — settled decisions, recorded so they are not re-litigated)

| Declined | Reason |
|---|---|
| Duplicate Company / Partner table | L36/L37 — `core.Party` with `PartyRole(role="partner")` is the master anchor. `PartnerProfile` extends it via 1:1 FK. |
| Duplicate Deal / Opportunity table | L36/L37 — `DealRegistration` represents an exclusive, temporary claim. Approved registrations convert into `crm.Opportunity` (`OPP-`). |
| Duplicate Territory master | CRM 1.4 owns `crm.Territory` (`TER-`). Channel conflict boundary rules reference it by FK. |
| Second financial ledger | L29 — Partner revenue targets and actuals are operational sales figures. Commission statements belong to Sales 8.10 and settlements to Module 2 Accounting. |
| Duplicate Document / File storage | Core DMS owns `core.Document` (`DOC-`). Partnership agreements and collateral attach via FK. |
| Duplicate User / Rep master | `accounts.User` is the authentication and employee master. CAMs, Partner Leads, and Channel Chiefs reference it by FK. |
| Stored console rollup tables | The console is computed on read by aggregating live `PartnerProfile`, `DealRegistration`, `JointAccountPlan`, and `ChannelConflict` tables. Storing rollups creates cache drift. |

---

## 4. Close-out Note

**As-built gaps**: None. The 5 deferred items in §2 above represent external cloud provider APIs, third-party authentication protocols, and specialized partner ecosystems outside NavERP's core ERP boundary.
