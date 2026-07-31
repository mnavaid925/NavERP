# Research — Sub-module 4.12: Contract & Compliance Management (Module 4 — Supply Chain Management, `scm`)

The five NavERP.md bullets (NavERP.md:810–816) researched here, verbatim:

- **Contract Repository** — Centralized storage for logistics contracts, supplier agreements, and NDAs.
- **Compliance Tracking** — Monitoring adherence to regulations (e.g., FDA, HazMat, GDPR).
- **Trade Documentation** — Generation and management of import/export documents (Bill of Lading, CI).
- **License Management** — Tracking of import/export licenses and expiration dates.
- **Sustainability Tracking** — Carbon footprint reporting and ethical sourcing compliance.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4
`apps/core/navigation.py` carries `"4.1"` … `"4.11"`. **`"4.12"` is absent — 4.12 is the next unbuilt
sub-module**, and 4.13–4.19 are also unbuilt. So 4.12 may FK anything from 4.1–4.11 and nothing later.

### Spine entities VERIFIED to exist (grep evidence — L28, "verify the spine exists")

| Entity | Verified at | Relevance to 4.12 |
|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py` | every 4.12 model is tenant-scoped |
| `core.Party` (`kind`, `name`, `tax_id`) | `apps/core/models/Party.py:5` | supplier / carrier / customer / end-user counterparty. **NO new vendor table.** |
| `core.PartyRole` (`customer/vendor/supplier/employee/lead/candidate/contact/partner`) | `apps/core/models/PartyRole.py:5` | roles, not tables |
| `core.Document` (generic FK `content_type`+`object_id`, `file`, `classification`, `version`) | `apps/core/models/Document.py:5` | **the file store for 4.12** — see the Module 13 note below |
| `core.OrgUnit`, `core.Address`, `core.AuditLog`, `core.Activity` | `apps/core/models/` | requirement owner scope / doc addresses |
| `accounting.Currency`, `PaymentTerm`, `TaxCode`, `Invoice`, `Bill`, `GLAccount`, `JournalEntry`, `FixedAsset` | `apps/accounting/models/**` | money FKs **by string only**; SCM posts no `JournalEntry` (L29) |
| **`scm.SupplierContract` [`SC-`]** | `apps/scm/models/SupplierRelationshipManagement/SupplierContracts.py:13` | **4.2 already owns the contract header — see the boundary decision below** |
| `scm.SupplierProfile` (incl. `dd_compliance_verified`, `dd_insurance_verified`, `dd_quality_cert_verified`) | `.../SupplierProfiles.py:12` | supplier due-diligence sign-offs already exist |
| `scm.SupplierRiskAssessment` (`compliance_score`, `geopolitical_score`, `risk_index`) | `.../SupplierRiskAssessments.py:10` | **compliance risk already scored here — 4.12 must not re-score it** |
| **`scm.Shipment` [`SHP-`]** + `TrackingEvent` | `apps/scm/models/TransportationManagement/Shipments.py:18,148` | **Trade Documentation FKs this — 4.6 owns the shipment** |
| `scm.Load` (`mode`, `distance_km`, `estimated_fuel_cost`) | `.../Loads.py:18,36,47,50` | **the carbon-report inputs 4.6 deliberately stored for 4.12** |
| `scm.Carrier` (`party` FK PROTECT, `scac_code`, `mc_number`, `dot_number`, `insurance_certificate_expiry`) | `.../Carriers.py:47,71,76–82` | a logistics contract's counterparty is `carrier.party`; **COI expiry already exists here** |
| `scm.PurchaseOrder`, `SalesOrder`, `GoodsReceiptNote` | `apps/scm/models/{Procurement,Order}Management/` | optional source doc on a trade document |
| `scm.Item` (`sku`, `name`, `uom`, `standard_cost`…), `scm.UOM` | `apps/scm/models/InventoryManagement/Items.py:56,34` | **exists — but has NO `hs_code`, NO `country_of_origin`, NO hazmat fields** |
| `scm.QualityAudit`, `NonConformance` (`SOURCE_CHOICES` = inspection/goods_receipt/production/supplier/audit/internal), `CapaAction` | `apps/scm/models/QualityManagement/` | 4.9's audit + finding + CAPA engine already ships |
| `scm.KpiTarget`, `KpiSnapshot`, `SupplyChainAlert` | `apps/scm/models/SupplyChainAnalytics/` | 4.11's metric/alert machinery |
| `crm.ContractDocument` [`CTR-`] + `SignerRecord` | `apps/crm/models/DocumentContract/Contracts.py:5,46` | CRM 1.9's **customer-facing** e-sign contract — a different object, not a supplier/logistics contract |

### Spine entities verified NOT to exist
- **No `apps/documents` app** — glob of `apps/*/apps.py` returns only `core, accounts, tenants, dashboard, crm,
  accounting, hrm, scm`. **Module 13 (DMS) is unbuilt.**
- **No `apps/quality` app** — Module 12 is unbuilt; SCM 4.9 QMS is in-app and is the only QMS.
- **No `core.Contract`, `core.Regulation`, `core.License`, `core.Certificate`** anywhere under `apps/`.
- **No `hs_code` / `country_of_origin` / `un_number` / hazmat field on `scm.Item`** — trade classification is
  unmodelled today.
- `NonConformance.SOURCE_CHOICES` has **no `compliance` value** (`.../NonConformances.py:33–40`).

### Auto-number prefixes already taken (grep `NUMBER_PREFIX` across `apps/`)
In `scm`: `PR RFQ QT PO GRN SC SCR SRA CAT ADJ TRF LD SHP FRT CAR SO WO WC PRD BOM DF FA DS SEA YRD PUT PIK CC
QC QA NCR CAPA RMA WTY ALR KPI`. **Free and proposed for 4.12: `CR`, `TD`, `LIC`, `ESG`.**

---

## The four as-built constraints, decided up front

### 1. `SupplierContract` (4.2) — the boundary 4.12 must respect
4.2 already ships a full contract header: `party→core.Party`, `title`, `contract_type`
(`master/purchase/service/**nda**/**sla**/framework`), `status`
(`draft/active/expiring/expired/terminated/renewed`), `start_date`/`end_date`, `contract_value`,
`currency→accounting.Currency`, `payment_terms→accounting.PaymentTerm`, `auto_renew`, `renewal_notice_days`,
`terms_summary`, `document→core.Document`, `terminated_at`/`termination_reason`, plus `days_to_expiry()`,
`is_expiring_soon()` and a date-driven `refresh_status()`.

**Decision: 4.12 does NOT create a second contract table.** The NavERP 4.12 bullet ("logistics contracts,
supplier agreements, and NDAs") is *already* satisfied by that model — a logistics contract is
`SupplierContract(party=<the carrier's `core.Party`>, …)`, and `nda`/`sla` are already `TYPE_CHOICES` values.
What 4.12 adds is the **post-execution compliance layer** every CLM leader sells separately from the repository
(Icertis *Vera Obligations*, Agiloft *Obligation Management*, Coupa "obligation and milestone tracking",
Docusign CLM "obligation tracking, reminders, reporting", SAP Ariba "obligation tracking and milestone
management"). That layer is `ComplianceRequirement`, model 1 below.

Two **thin, additive, nullable-only** columns on `SupplierContract` are recommended (no backfill, no behaviour
change) — the exact precedent is **4.4 extending 4.3's `Location` with `capacity`/`pick_sequence`/`abc_class`**
and then pointing its own "Bin/Location Management" bullet at `scm:location_list`:
- `parent_contract` (self-FK, null) — **contract hierarchy / amendments**. Docusign CLM "view agreement
  hierarchies"; Icertis "version history and relationship tracking"; every CLM treats an amendment as a child
  of the master, not a sibling row. 4.2 has no way to express this today.
- `owner` (`settings.AUTH_USER_MODEL`, null) — a named accountable owner. Agiloft/Coupa/Icertis all route
  renewals and obligations to a contract owner; 4.2 stores none.
- Add one `TYPE_CHOICES` value `("logistics", "Logistics / Carrier Agreement")` so a 3PL/carrier agreement is
  classifiable. (Choice-only change; migration is a no-op `AlterField`.)

**"Contract Repository" LIVE_LINK → `scm:contract_list`** (4.2's existing list, now with the amendment tree and
owner column). This is deliberate and precedented; it is not a gap.

### 2. Files without pre-empting Module 13
`core.Document` is the generic attachment (generic FK + `file` + `classification` + `version`) and its own
docstring says "DMS module later layers folders/versions on top". 4.2's `SupplierContract.document` is a plain
`FK("core.Document")`. **4.12 does exactly the same: every 4.12 model attaches evidence/scans via
`core.Document` (nullable FK, or the generic relation for many-per-record), and 4.12 declares NO `FileField` of
its own.** No folder tree, no check-in/check-out, no retention policy, no OCR — all of that is Module 13.

### 3. Overlap with 4.9 QMS (Module 12 unbuilt)
4.9 already owns: `QualityAudit` (incl. `audit_type="certification"` for external certification bodies and a
free-text `standard` field, e.g. "ISO 9001:2015"), the one `NonConformance` finding register, and `CapaAction`.
**4.12 must not build a second audit, finding or CAPA engine.** The 4.12 compliance register is about *standing
obligations and their periodic proof* (Intelex's "legal requirements"), which 4.9 has nothing for; the moment a
compliance check *fails* in a way that needs root-cause work, that is a 4.9 `NonConformance`/`CapaAction`.
Recommended posture: 4.12 stores the failure on its own check row and **links out** by URL/reference only —
it should NOT add a `compliance` value to `NonConformance.SOURCE_CHOICES` in this pass (refactoring a shipped
sub-module for a nice-to-have is the thing 4.11 explicitly refused to do). Park the hard FK as deferred.

### 4. Trade documents point at 4.6's `Shipment`
Verified: `scm.Shipment` [`SHP-`] carries `direction` (outbound/inbound), `carrier`, `load`, `sales_order`,
`purchase_order`, `ship_from_address`/`ship_to_address` (`core.Address`), `mode`, `weight_kg`, `volume_cbm`,
`package_count`, `carrier_tracking_number`, POD state and an append-only `TrackingEvent` log whose
`EVENT_TYPE_CHOICES` already include `customs_hold`. **`TradeDocument` FKs `scm.Shipment` (nullable) and
re-declares none of that** — no second consignment, no second carrier, no second POD.

### 5 & 6. Ledger and parties
No `JournalEntry` is written by 4.12 (L29). Money columns FK `accounting.Currency` by string. Counterparties are
`core.Party` rows (a carrier via `scm.Carrier.party`, a supplier via its supplier `PartyRole`) — 4.12 declares
no party-like table.

### Sibling research already routed TO 4.12 (this is the starting backlog)
- `research-scm-4.6.md:255–259` — carbon/sustainability reporting over the transport network, and
  import/export trade documentation (BoL, CI, HazMat), both explicitly parked for 4.12; 4.6 stored
  `Load.distance_km` + `estimated_fuel_cost` for it.
- `research-scm-4.9.md:579` — ISO/certification tracking, regulatory compliance registers and contract
  compliance clauses parked for 4.12.
- `research-scm-4.11.md:349–351, 511` — "carbon / emissions alongside cost" (Coupa, Blue Yonder) parked for
  4.12's Sustainability Tracking bullet.
- `research-scm-4.2.md:166, 179` — clause-level obligation extraction and "automated compliance monitoring
  against contract terms" (JAGGAER) deferred out of 4.2.

---

## Leaders surveyed (with source links)

This sub-module genuinely spans **four distinct product categories** (CLM · global trade management · EHS/
regulatory compliance registers · ESG & carbon), so the survey is wider than a single-category sub-module.

**Contract lifecycle management (CLM) — the post-signature/obligation half**
1. **Icertis Contract Intelligence** — enterprise CLM for global procurement & compliance; central repository
   with version history and relationship tracking, template/clause libraries, *Vera Obligations* post-execution
   governance, AI renewal intelligence — https://www.icertis.com/products/operate/contract-lifecycle-management/
   and https://www.icertis.com/learn/what-is-contract-intelligence/
2. **Agiloft CLM** — no-code-configurable CLM; searchable repository, obligation management with a **pre-built
   obligation-type library (Financial, Delivery, Service Levels, Termination, Confidentiality, Regulatory, Data,
   Insurance)**, deadline/renewal alerts, audit trail —
   https://www.agiloft.com/platform/contract-management-software and
   https://www.agiloft.com/news/agiloft-enterprise-grade-obligation-management-ai-native-era-of-contract-lifecycle-management/
3. **SAP Ariba Contracts** — procurement-native CLM; central repository with duplicate detection, clause
   library, obligation & milestone tracking, expiration-date + notification-period metadata, fixed vs perpetual
   vs auto-renewing agreements — https://www.sap.com/products/spend-management/contract-management-software.html
4. **Coupa CLM** — searchable repository with metadata tagging, clause library, obligation & milestone tracking,
   renewal alerts, risk scoring, contracts linked to POs/supplier records/spend —
   https://www.coupa.com/products/source-to-contract/contract-management/
5. **Docusign CLM** — repository searchable by keyword/concept/metadata, AI metadata extraction, **agreement
   hierarchies**, renewal & obligation tracking with milestone alerts, total-contract-value reporting —
   https://www.docusign.com/products/clm
6. **Ironclad / Sirion** (Gartner CLM Leaders alongside Icertis, Docusign, Agiloft) — surveyed for market
   context on repository/renewal/obligation expectations —
   https://www.gartner.com/reviews/market/contract-life-cycle-management

**Global trade management (GTM) — trade documentation, licences, screening**
7. **SAP Global Trade Services (GTS)** — modular Compliance Management (sanctioned-party-list screening that
   *blocks* documents into a work list, embargo checks, **Legal Control** = automated licence checks by
   product/destination/business partner), Customs Management (declarations, government filing), Trade
   Preference Management (rules of origin, preferential duty) —
   https://www.sap.com/products/financial-management/global-trade-management.html and
   https://help.sap.com/docs/SAP_GLOBAL_TRADE_SERVICES/bdb1d2fb216941a69f6300006343e977/9ebfb9b4001d4029aa74f060f81cd812.html
8. **e2open Global Trade Management** — Due Diligence Screening (900+ restricted-party/sanctions lists), Export
   Management (country controls, licence determination *and tracking*, document generation), Import Management,
   Duty Management (deferral/refund, FTZ/customs warehousing), Customs Filing, Global Knowledge trade content;
   centralised tracking of **licence usage, exemptions and end-user statements** —
   https://www.e2open.com/global-trade/ and https://www.e2open.com/global-trade/export-management
9. **Thomson Reuters ONESOURCE Global Trade** — export/import compliance, product classification, FTA
   qualification under rules of origin, and **licence management that checks availability & validity and
   decrements the remaining licence value or volume per shipment**; content covering 220+ countries, 2M+
   import/export controls, 750+ denied-party lists, 120+ country documentation requirements, 500+ FTA rules of
   origin — https://tax.thomsonreuters.com/en/onesource/global-trade-management/export-compliance and
   https://tax.thomsonreuters.com/en/products/onesource-global-trade-content
10. **Descartes Visual Compliance / Denied Party Screening** — online/batch/integrated/**dynamic (daily
    re-screening)** screening, Screening & Audit History + Resolution Manager (documented match decisions),
    ECCN/USML/Schedule B classification, **Export License Manager** (multi-authority licences from application →
    approval → usage → expiration → reporting, **real-time decrementing**, expiry alerts + balance summaries,
    provisos/conditions, sub-licensees), Forced Labor Compliance —
    https://www.visualcompliance.com/compliance-solutions/ and
    https://www.visualcompliance.com/compliance-solutions/export-automation/export-license-manager/
11. **Shipping Solutions (InterMart)** — export documentation specialist: generates 2 dozen+ standard export
    forms (commercial invoice, packing list, certificate of origin incl. chamber certification, SLI, inland/ocean
    BoL, air waybill, DG forms, BIS-711, proforma), restricted-party screening, ITAR/EAR licence determination,
    **document determination by destination**, AES/EEI filing, shipment-record archiving —
    https://shippingsolutionssoftware.com/ and
    https://shippingsolutionssoftware.com/blog/documents-required-for-international-shipping

**Regulatory compliance registers & HazMat**
12. **Intelex — Compliance Tracking / Legal Requirements Management / Permits Management** — a central register
    of "regulations, permits, policies and other compliance drivers", each with **source, domain, applicability
    status, responsible party, due date, recurrence frequency, workflow status, audit trail of changes**, plus
    past audit history, related findings and related CAPAs; compliance calendar; renewal dates and escalations —
    https://www.intelex.com/products/applications/legal-requirements-management-software/ and
    https://www.intelex.com/products/applications/compliance-tracking-software/
13. **Sphera — Chemical / Hazardous Material Management** — centralised SDS library, GHS/EU-CLP compliant
    classification & labelling, cradle-to-grave hazardous-substance tracking, **version control and audit trails
    as defensible documentation for inspections**, regulatory-change intelligence by jurisdiction —
    https://sphera.com/solutions/product-stewardship/chemical-management-software/

**ESG, ethical sourcing & carbon**
14. **EcoVadis** — supplier sustainability scorecard across **four themes (Environment · Labor & Human Rights ·
    Ethics · Sustainable Procurement)** plus a separate **Carbon** scorecard; per-theme score, **overall score
    1–100**, annually-updated **medal (bronze/silver/gold/platinum)**, maturity levels
    (insufficient/beginner/intermediate/advanced/leader), and per-theme **strengths & improvement areas** —
    https://ecovadis.com/solutions/ratings/ and
    https://support.ecovadis.com/hc/en-us/articles/115002531507-What-is-the-EcoVadis-methodology
15. **Assent Supply Chain Sustainability Platform** — auditable supplier **declarations** against REACH, RoHS,
    PFAS/TSCA, Prop 65, SCIP, **UFLPA (forced labour)**, responsible/conflict minerals, plus high/medium/low
    supplier risk drill-down — https://www.assent.com/capabilities/
16. **Sourcemap** — multi-tier supply-chain mapping & sub-supplier discovery, **chain-of-custody transaction
    traceability**, automated risk heat-map scoring against 15+ compliance databases and a 70k-entity watchlist,
    OCR classification of policies/certifications, EUDR due-diligence statements filed to the EU TRACES system —
    https://www.sourcemap.com/solutions/supply-due-diligence
17. **IntegrityNext** — standardised supplier **self-assessments** with a questionnaire library across human
    rights/environment/governance, certificate collection, continuous media monitoring, corrective-action and
    complaint/remediation tracking, documented audit trails for LkSG/CSDDD reporting —
    https://www.integritynext.com/supply-chain-due-diligence
18. **Persefoni** and **Watershed** — carbon accounting: Scope 1/2/3 per GHG Protocol, Persefoni's
    transaction-level **"Footprint Ledger"** with full data-change logs for assurance; Watershed's 500k+
    annually-updated emission factors, activity-based vs spend-based methodology, supplier engagement for
    Scope 3 collection, CSRD/CDP/ISSB report builders —
    https://www.persefoni.com/business/carbon-footprint-measurement-analytics and
    https://watershed.com/platform/measure/carbon-accounting
19. **GLEC Framework v3.2 / ISO 14083** (Smart Freight Centre — methodology, not a product) — the recognised
    way to compute freight GHG per transport chain across road/rail/ocean/air; this is the arithmetic 4.12's
    carbon report should state on screen —
    https://www.smartfreightcentre.org/en/our-programs/emissions-accounting/global-logistics-emissions-council/

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader) · **common** (most) · **differentiator** (a few standouts).

### Bullet 1 — Contract Repository
> Mostly ALREADY SHIPPED by 4.2's `SupplierContract`. Only the genuinely-missing capabilities are listed.

- **Central contract repository with typed metadata** (party, type, dates, value, currency, status, owner) —
  seen in: Icertis, Agiloft, SAP Ariba, Coupa, Docusign CLM · **table-stakes** · spine: **already
  `scm.SupplierContract`** — nothing to build · *shipped in 4.2*
- **Renewal / expiry alerting with a notice window** — seen in: all six CLMs (Ariba's "expiration date +
  notification period" metadata; Icertis renewal intelligence) · **table-stakes** · spine: already
  `SupplierContract.renewal_notice_days` + `is_expiring_soon()` + `refresh_status()` · *shipped in 4.2*
- **Contract hierarchy / amendments (parent ↔ child)** — a master agreement with amendments, SOWs and renewals
  hanging off it; Docusign CLM renders "agreement hierarchies", Icertis tracks contract relationships, Ariba
  distinguishes fixed / perpetual / auto-renewing · **table-stakes in CLM, MISSING here** · spine: **one
  nullable self-FK `parent_contract` on the existing `scm.SupplierContract`** — not a new table ·
  **buildable now**
- **Named contract owner** — the person renewals and obligations route to; Agiloft/Coupa/Icertis all require it ·
  **common, MISSING here** · spine: nullable `owner` FK to `AUTH_USER_MODEL` on `scm.SupplierContract` ·
  **buildable now**
- **Logistics / carrier agreement as a first-class contract type** — the 4.12 bullet names logistics contracts
  explicitly; 4.6's `Carrier` has a required `party` FK so the counterparty already resolves · **common** ·
  spine: one added value in `SupplierContract.TYPE_CHOICES` · **buildable now**
- **Post-execution obligation register** (see Bullet 2 — this is where the CLM leaders' obligation feature lands)
- **Clause library / template authoring / redlining / e-signature** — seen in: Icertis, Agiloft, Ariba, Coupa,
  Docusign · **table-stakes in CLM** · spine: NavERP already has this shape on the *sales* side
  (`crm.ContractDocument` + `crm.DocTemplate` + `SignerRecord`, token signing) · **DEFERRED** — a supplier-side
  authoring/e-sign stack is its own build (4.2 deferred it for the same reason)
- **AI clause extraction / risk flagging / natural-language contract Q&A** (Icertis Vera Copilot, Agiloft AI
  agents, Docusign AI metadata extraction) · **differentiator** · **integration/later** — no LLM in this repo,
  and 4.11 set the precedent that a page must not claim "AI"

### Bullet 2 — Compliance Tracking (FDA, HazMat, GDPR)
- **A single register of standing compliance obligations** — "regulations, permits, policies and other
  compliance drivers" in one searchable place, each with its **source citation, domain, applicability status,
  related documentation and audit history** · seen in: Intelex Legal Requirements Management (the canonical
  shape), Sphera (regulatory intelligence by jurisdiction) · **table-stakes** · spine: **NEW
  `ComplianceRequirement`** · **buildable now**
- **Responsible party + due date + recurrence frequency + workflow status on every requirement** — Intelex
  states exactly this quadruple; it is what turns a register into a working queue · seen in: Intelex,
  Agiloft (obligation owner/deadline), Coupa, Docusign CLM · **table-stakes** · spine: fields on
  `ComplianceRequirement` (`owner`, `next_due_date`, `frequency`, `status`) · **buildable now**
- **Periodic proof-of-compliance history (the audit trail)** — each cycle recorded with who did it, when, the
  result, and the evidence file; Sphera calls it "defensible documentation for inspections", Intelex keeps "past
  audit history / related findings" against the requirement · seen in: Intelex, Sphera, IntegrityNext,
  Persefoni (data-change logs) · **table-stakes** · spine: **NEW child `ComplianceCheck`** + evidence via
  `core.Document` · **buildable now**
- **Contract obligations live in the same queue** — Agiloft ships an obligation-type library whose categories are
  **Financial, Delivery, Service Levels, Termination, Confidentiality, Regulatory, Data, Insurance**; Icertis
  *Vera Obligations*, Coupa, Ariba and Docusign CLM all track obligations, deadlines and milestones
  post-signature · seen in: Agiloft, Icertis, Coupa, SAP Ariba, Docusign CLM · **table-stakes** · spine:
  **`ComplianceRequirement.source="contract"` + nullable FK to the verified `scm.SupplierContract`** — the 4.9
  precedent ("audit findings are `NonConformance` rows with `source='audit'`, not a second table") ·
  **buildable now**
- **Regulatory framework taxonomy** — the register is only useful filtered by regime; the leaders' own coverage
  gives the choice list: FDA/FSMA, HazMat (DOT/IATA/IMDG) + GHS/CLP (Sphera), GDPR/data privacy (Agiloft "Data"
  obligations), REACH / RoHS / PFAS-TSCA / Prop 65 / SCIP (Assent), UFLPA & forced labour (Assent, Descartes,
  Sourcemap), conflict/responsible minerals (Assent), EUDR deforestation (Sourcemap), LkSG/CSDDD (IntegrityNext),
  CSRD (Watershed), ISO 9001/14001, customs & export control (SAP GTS, ONESOURCE), insurance/COI · **common** ·
  spine: `framework` choice field on `ComplianceRequirement` · **buildable now**
- **Applicability scoping** — Intelex records "applicability status"; a requirement binds to a site, a
  department, a supplier or a product family, and non-applicable rows are kept (with a reason) rather than
  deleted · seen in: Intelex, IntegrityNext · **common** · spine: `scope` choice + nullable FKs to the verified
  `core.OrgUnit` / `core.Party` / `scm.Location` / `scm.Item` · **buildable now**
- **Permit / certificate expiry tracking with staged reminders (90/60/30 days)** — COI and ISO-certificate
  tracking products fire tiered reminders and record issuing body + certificate number + expiry · seen in:
  Intelex Permits Management, Descartes (licence expiry alerts), Sirion/COI trackers, IntegrityNext (certificate
  collection) · **table-stakes** · spine: `ComplianceRequirement` with `framework="certification"` and its
  `next_due_date`; **note 4.6 already stores `Carrier.insurance_certificate_expiry`** — the register complements
  it, does not replace it · **buildable now**
- **Compliance calendar / "what's due & overdue" dashboard** — Intelex's shared monthly calendar with escalation ·
  seen in: Intelex, Agiloft, Coupa · **common** · spine: computed over `ComplianceRequirement.next_due_date`
  (a list filter + header chips, the 4.10 `refund_queue` precedent) · **buildable now**
- **Escalation to root-cause work when a check fails** — Intelex links a requirement to "related findings and
  related CAPAs" · **common** · spine: **4.9 already owns `NonConformance` + `CapaAction`** — link out, do not
  re-model · **buildable now (link only); hard FK deferred**
- **SDS/GHS chemical library, label generation, cradle-to-grave substance tracking** (Sphera) ·
  **differentiator** · **DEFERRED** — a chemical-substance master is a product-stewardship module, not 4.12
- **Subscribed regulatory content feeds** (Intelex + Enhesa/RegScan; Sphera regulatory intelligence; ONESOURCE
  Global Trade Content) · **differentiator** · **integration/later** — the register holds a `source_reference`
  URL/citation typed by a human

### Bullet 3 — Trade Documentation (Bill of Lading, Commercial Invoice)
- **One document register covering the standard export/import document set** — commercial invoice, packing list,
  proforma invoice, certificate of origin, inland BoL, ocean BoL, air waybill, SLI, dangerous-goods declaration,
  export licence copy, insurance certificate, EEI/AES filing reference · seen in: Shipping Solutions (2 dozen+
  forms), e2open (documentation generation), ONESOURCE (centralised broker documentation), SAP GTS (customs
  documents) · **table-stakes** · spine: **NEW `TradeDocument`** with a `doc_type` choice list · **buildable now**
- **The document hangs off the shipment, not a copy of it** — every GTM product derives documents from the
  underlying consignment · seen in: e2open, ONESOURCE, Shipping Solutions ("order information imported, then
  used to create the documents") · **table-stakes** · spine: nullable FK to the **verified `scm.Shipment`**
  (+ optional `scm.PurchaseOrder` / `scm.SalesOrder` for the source order) · **buildable now**
- **Commercial-invoice header data** — shipper/consignee, order & PO references, currency, declared value,
  **Incoterms**, payment terms, marine-insurance details, country of origin & destination · seen in: Shipping
  Solutions (explicit field list), e2open, ONESOURCE · **table-stakes** · spine: fields on `TradeDocument`;
  parties are `core.Party`, currency is `accounting.Currency` · **buildable now**
- **Line-level detail with HS/HTS classification, quantity, unit value, net/gross weight and country of origin** —
  the customs-valuation payload; Shipping Solutions' packing list carries net/gross weights, dimensions and
  markings, and classification is the core of e2open/ONESOURCE/Descartes · **table-stakes** · spine: **NEW child
  `TradeDocumentLine`** with a nullable FK to the **verified `scm.Item`** + a snapshotted description/HS code ·
  **buildable now**
- **Snapshot, don't reference** — an issued customs document must not silently change when the item master is
  edited later; 4.9 already established this posture ("results are SNAPSHOTTED, so editing a plan can never
  rewrite a past certificate") · seen in: implied by every GTM product's audit posture, explicit in Descartes
  ("comprehensive documentation of every action") · **common** · spine: copy `hs_code`/`description`/`uom` onto
  `TradeDocumentLine` at issue · **buildable now**
- **Bill-of-lading transport data** — vessel/flight/voyage, port of loading & discharge, container/seal numbers,
  negotiable vs straight BoL, contract-of-carriage vs receipt-of-goods distinction · seen in: Shipping
  Solutions (ocean BoL is both contract of carriage and document of title; AWB is a non-negotiable receipt) ·
  **common** · spine: fields on `TradeDocument`; the carrier is the verified `scm.Carrier` · **buildable now**
- **Document status lifecycle** (draft → issued → submitted → accepted → amended → void) with an issue date and
  document number · seen in: e2open, ONESOURCE, SAP GTS (customs declaration lifecycle) · **table-stakes** ·
  spine: `status` choices on `TradeDocument`; `number` is the internal `TD-` and `document_number` the external
  BoL/invoice number · **buildable now**
- **Attach the signed/stamped PDF** — Shipping Solutions archives shipment records; ONESOURCE centralises broker
  documentation · **table-stakes** · spine: `core.Document` FK (Module 13 note above) · **buildable now**
- **Document determination — "which documents does this destination require?"** — Shipping Solutions determines
  required documents by destination and regulation; ONESOURCE content covers 120+ countries' documentation
  requirements · **differentiator** · spine: needs a country-requirements content set · **DEFERRED** (a manual
  checklist on the shipment is the honest v1)
- **Printable/PDF rendering of each form to the official layout** · seen in: all documentation products ·
  **common** · spine: a print template per doc type (the HRM `relieving_letter.html` precedent) · **buildable
  now — recommend ONE generic print view this pass**, per-form official layouts deferred
- **Direct customs/AES/EEI filing, EDI transmission, TRACES/broker connectivity** · seen in: Shipping Solutions
  (AESDirect), SAP GTS (government systems), e2open (self-filing), Sourcemap (EU TRACES) · **table-stakes in
  GTM** · **integration/later** — 4.12 stores the filing reference and status only
- **Duty/tariff & landed-cost calculation, FTA rules-of-origin qualification, FTZ/duty-drawback** · seen in:
  e2open Duty Management, ONESOURCE FTA (500+ rules of origin), SAP GTS Trade Preference, Thomson Reuters FTZ ·
  **table-stakes in GTM** · **PARK → 4.18** ("Landed Cost Calculation" and "Tax Management" are 4.18 bullets)

### Bullet 4 — License Management (import/export licences + expiry)
- **A licence register spanning multiple issuing authorities** — Descartes' Export License Manager manages
  "multi-authority export licenses and activities in a single, centralized system", covering licences,
  exemptions/exceptions and agreements (TAA/MLA) · seen in: Descartes, e2open, ONESOURCE, SAP GTS Legal
  Control · **table-stakes** · spine: **NEW `TradeLicense`** · **buildable now**
- **Full licence lifecycle** — Descartes: "from application through approval, usage, expiration, and reporting" ·
  seen in: Descartes, e2open · **table-stakes** · spine: `status` choices
  (draft → applied → approved → active → expiring → expired → suspended/revoked) · **buildable now**
- **Value/quantity decrementing against the licence balance** — **the signature feature of this category**:
  ONESOURCE "decrements the remaining license value or volume for export shipments over time"; Descartes does
  "real-time decrementing … to prevent overuse and maintain accurate balance visibility"; e2open centralises
  "license usage" · seen in: ONESOURCE, Descartes, e2open · **table-stakes** · spine: `authorized_value` /
  `authorized_quantity` vs `used_value` / `used_quantity` on `TradeLicense`, with derived `remaining_*` and
  `utilization_pct` — the arithmetic posture 4.6's `Load` utilization already uses · **buildable now**
- **Expiration alerts and balance summaries** — Descartes fires expiry alerts, annual status-update
  notifications and review-period tracking; the whole NavERP bullet is "…and expiration dates" · seen in:
  Descartes, ONESOURCE, e2open · **table-stakes** · spine: `expiry_date` + `renewal_notice_days` + derived
  `days_to_expiry`/`is_expiring_soon` + a date-driven `refresh_status()` — **mirror `SupplierContract`'s proven
  implementation exactly**, do not invent a second idiom · **buildable now**
- **Commodity / classification scope on the licence** — which ECCN/USML/HS codes and which destination countries
  the licence covers; e2open "maintains export and import licensing logic for all HTS/HS and ECCN/ECN numbers",
  SAP GTS Legal Control checks "products, destinations, and business relationships" · seen in: e2open, SAP GTS,
  Descartes, ONESOURCE · **common** · spine: `commodity_scope` + `eccn_or_hs` + `destination_countries` text
  fields on `TradeLicense` (free text — there is no HS/ECCN master in this repo) · **buildable now**
- **End user / consignee named on the licence** — BIS-711 "identifies the final recipient and intended use";
  Descartes tracks sub-licensees and foreign persons · seen in: Descartes, Shipping Solutions · **common** ·
  spine: nullable FK to the verified `core.Party` · **buildable now**
- **Provisos / conditions recorded against the licence** — Descartes records provisos, RWA statuses and denial
  reasons · seen in: Descartes · **common** · spine: `conditions` text + `ComplianceRequirement` rows with
  `source="license"` for conditions that need periodic proof · **buildable now**
- **Licence determination — "does this shipment need a licence?"** — SAP GTS Legal Control and e2open/Shipping
  Solutions determine licence requirements automatically from product × destination × party · seen in: SAP GTS,
  e2open, ONESOURCE, Descartes, Shipping Solutions · **table-stakes in GTM** · **DEFERRED (needs regulatory
  content)** — the honest v1 is a manual "licence applied" link from a `TradeDocument` to a `TradeLicense`
- **Restricted/denied-party & sanctions screening with match resolution and daily re-screening** — Descartes
  (online/batch/integrated/dynamic screening, Screening & Audit History, Resolution Manager), e2open (900+
  lists), ONESOURCE (750+ lists), SAP GTS (SPL screening that blocks documents into a work list) ·
  **table-stakes in GTM** · spine: the *screening result* would be a `ComplianceRequirement`/check row against a
  `core.Party`, but the **list content itself is a paid data feed** · **integration/later** — model the
  *outcome* (a screening record on the party), never fake the lists
- **Sanctioned-party ownership analysis, adverse-media search, PEP/anti-corruption screening** (Descartes Risk
  Management) · **differentiator** · **integration/later**
- **Controlled-technology access (visitor/travel risk, deemed exports)** (Descartes) · **differentiator** ·
  **out of scope** — an HR/security concern, not SCM

### Bullet 5 — Sustainability Tracking (carbon + ethical sourcing)
- **Supplier sustainability scorecard on multiple themes** — EcoVadis' four themes (Environment · Labor & Human
  Rights · Ethics · Sustainable Procurement) plus a separate Carbon scorecard, each theme scored with
  **strengths and improvement areas** · seen in: EcoVadis (the reference implementation), IntegrityNext,
  Sourcemap, Assent · **table-stakes** · spine: **NEW `SustainabilityAssessment`** on the verified `core.Party`
  · **buildable now**
- **Overall 0–100 score + a banded rating, valid for a period** — EcoVadis: overall 1–100, annually updated,
  bronze/silver/gold/platinum medals and insufficient→leader maturity levels · seen in: EcoVadis, IntegrityNext ·
  **table-stakes** · spine: derived `overall_score` + `rating` choice + `valid_until` on
  `SustainabilityAssessment` — **derive the headline, never hand-set it** (the `SupplierRiskAssessment
  .recompute_risk_level()` precedent already in this app) · **buildable now**
- **Assessment source matters** — a supplier self-assessment (IntegrityNext), a third-party rating (EcoVadis), a
  desk review, or an on-site audit are different evidentiary weights · seen in: IntegrityNext (self-assessment +
  validation services), EcoVadis (third-party), Sourcemap (corroborated against 15+ databases) · **common** ·
  spine: `source` choice on `SustainabilityAssessment` · **buildable now**
- **Ethical-sourcing declarations against named regulations** — Assent collects auditable declarations for
  REACH, RoHS, PFAS/TSCA, Prop 65, SCIP, **UFLPA/forced labour**, responsible/conflict minerals; Sourcemap files
  EUDR due-diligence statements; Descartes ships Forced Labor Compliance · seen in: Assent, Sourcemap,
  Descartes, IntegrityNext · **table-stakes** · spine: **boolean/choice declaration flags on
  `SustainabilityAssessment`** for the handful of regimes, with anything needing a recurring proof cycle
  becoming a `ComplianceRequirement` row (`framework="conflict_minerals"` etc.) · **buildable now**
- **Certifications collected and OCR-classified** (ISO 14001, FSC, Fairtrade, SA8000) · seen in: Sourcemap (OCR
  classifies "policies, certifications and more"), IntegrityNext, Assent · **common** · spine: certificate
  *files* on `core.Document`; certificate *expiry* is a `ComplianceRequirement` with
  `framework="certification"` — **do not build a third expiry mechanism** · **buildable now (OCR: later)**
- **Supplier-declared Scope 1 / 2 / 3 carbon footprint collected as part of the assessment** — Watershed and
  Persefoni both sell "supplier engagement for Scope 3 data collection"; EcoVadis added a dedicated Carbon
  scorecard in 2021 · seen in: EcoVadis, Watershed, Persefoni, IntegrityNext · **common** · spine: three nullable
  tCO2e fields + a reporting-year field on `SustainabilityAssessment` · **buildable now**
- **Our own freight carbon footprint, computed per shipment/load** — GLEC Framework v3.2 / **ISO 14083** is the
  recognised methodology across road/rail/ocean/air; Persefoni's transaction-level "Footprint Ledger" and
  Coupa/Blue Yonder's "carbon alongside cost" are the same idea · seen in: GLEC/ISO 14083, Persefoni, Watershed,
  Coupa · **differentiator** · spine: **a COMPUTED report over the verified `scm.Load.distance_km`,
  `Load.mode`/`Shipment.mode` and `Shipment.weight_kg`** — 4.6 stored those fields expressly for this, and this
  repo already ships bullets as computed pages (`valuation_report`, `mrp_report`, `safety_stock_report`,
  `coa_report`, and **all five** of 4.11's) · **buildable now — NO new table**
- **Emission-factor library (500k+ factors, annually updated)** (Watershed) · **differentiator** ·
  **integration/later** — 4.12 ships a small **closed, on-screen modal factor table** (the 4.11 "closed metric
  registry" precedent) and states the method and factor source on the page
- **Frozen, assurance-grade emissions ledger with change logs** (Persefoni Footprint Ledger) ·
  **differentiator** · **DEFERRED** — if a figure must be frozen for CSRD, 4.11's `KpiSnapshot` is the existing
  freezing mechanism; a dedicated `CarbonFootprintEntry` ledger is a later pass
- **CSRD / CDP / ISSB / SEC disclosure report builders** (Watershed, Persefoni) · **differentiator** ·
  **out of scope** — statutory disclosure is a finance/reporting concern, not SCM (L29 posture)
- **Multi-tier supplier mapping & sub-supplier discovery, chain-of-custody transaction traceability** (Sourcemap
  10–20× visibility expansion; the cascading supplier portal) · **differentiator** · spine: would need a
  supplier-of-supplier graph — `core.PartyRelationship` exists but tier-N discovery needs a supplier portal ·
  **DEFERRED**
- **Continuous adverse-media / watchlist monitoring with automatic score changes** (Sourcemap AI watchlist,
  IntegrityNext sentiment analysis) · **differentiator** · **integration/later**
- **Supplier-facing self-service portal for questionnaires and declarations** (IntegrityNext, Assent, Sourcemap,
  EcoVadis) · **table-stakes in this category** · **DEFERRED** — 4.1 and 4.2 already deferred the vendor portal
  for the same L32 reason; staff record the assessment on the supplier's behalf

### Beyond the bullets (found in the leaders, not in NavERP's five bullets)
- **Approval workflow on a compliance/licence record** (Agiloft configurable routing, Ariba workflows) ·
  **common** · spine: NavERP has no generic approval engine in `scm`; the `SupplierProfile.approved_by/
  approved_at/decision_note` triple is the in-app idiom · **buildable now as a simple two-state sign-off**
- **Contract/compliance analytics dashboard** (Coupa spend+contract analytics, Docusign CLM KPI dashboards,
  Agiloft "contracts as reportable business intelligence") · **common** · **PARK → 4.11** (Supply Chain
  Analytics is built and owns the dashboards; expiring-licence/overdue-requirement counts belong in its
  `SupplyChainAlert` inbox, not in a new 4.12 dashboard)
- **Duplicate-contract detection** (SAP Ariba) · **differentiator** · **DEFERRED**

---

## Recommended build scope (this pass — 4 models + 1 computed report + 2 thin extensions)

Every model is `TenantOwned`/`TenantNumbered` (tenant FK, per-tenant `number`), gets the full CRUD five
(list with search+filters / create / detail / edit / POST delete), and lives at
`apps/scm/{models,forms,views,urls}/ContractCompliance/<Entity>.py` with templates under
`templates/scm/compliance/<entity>/{list,detail,form}.html`.

### 1. `ComplianceRequirement` [`CR-`] + child `ComplianceCheck` — *the register*
`models/ContractCompliance/ComplianceRequirements.py`

- **Justified by:** Intelex Legal Requirements Management (source · domain · applicability · responsible party ·
  due date · recurrence · workflow status · audit trail of changes); Sphera (version control + audit trail as
  defensible inspection documentation); Agiloft's obligation-type library (Financial, Delivery, Service Levels,
  Termination, Confidentiality, Regulatory, Data, Insurance); Icertis *Vera Obligations*; Coupa/Ariba/Docusign
  obligation & milestone tracking; COI/ISO-certificate trackers' staged 90/60/30-day reminders.
- **Fields:** `title`, `source` (`regulation | contract | license | certification | customer_requirement |
  internal_policy`), `framework` (FDA/FSMA · HazMat-DOT/IATA/IMDG · GHS-CLP · GDPR/data privacy · REACH · RoHS ·
  Prop 65/SCIP · UFLPA/forced labour · conflict minerals · EUDR · CSDDD/LkSG · ISO 9001 · ISO 14001 ·
  customs & export control · insurance/COI · other), `jurisdiction`, `source_reference` (citation/URL),
  `obligation_category` (Agiloft's eight), `scope` (`tenant | org_unit | party | location | item`) with the
  matching nullable FKs, `owner` (user), `frequency` (`one_time | monthly | quarterly | semi_annual | annual |
  biennial | on_event`), `next_due_date`, `last_checked_on` *(editable=False)*, `status`
  (`applicable | not_applicable | in_progress | compliant | non_compliant | overdue | retired`),
  `criticality` (`low | medium | high | critical`), `notice_days`, `notes`, `document` FK.
- **FKs (all verified):** `core.Tenant`, `core.OrgUnit`, `core.Party`, `core.Document`,
  `scm.SupplierContract` (nullable — this is the CLM obligation link), `scm.TradeLicense` (nullable — licence
  provisos), `scm.Location`, `scm.Item`, `AUTH_USER_MODEL`.
- **Child `ComplianceCheck`** (tenant-less, reached via parent — the `TrackingEvent`/`InspectionResult`
  precedent): `due_date`, `performed_on`, `performed_by`, `result` (`pass | fail | partial | not_applicable`),
  `finding`, `evidence` → `core.Document`, `notes`. Append-only in spirit; a `fail` sets the parent
  `status="non_compliant"` and the parent recomputes `next_due_date` from `frequency` on a pass — the
  `SupplierContract.refresh_status()` / `Shipment.apply_tracking_event()` projection idiom.
- **Derived, never stored:** `days_to_due`, `is_overdue`, `is_due_soon`, `compliance_rate` (passes ÷ checks) —
  4.9's "`findings_major` must never become a column" rule.

### 2. `TradeDocument` [`TD-`] + child `TradeDocumentLine` — *the trade paperwork*
`models/ContractCompliance/TradeDocuments.py`

- **Justified by:** Shipping Solutions' document set and its explicit field lists (commercial invoice carries
  order/PO references, banking and marine-insurance details; packing list carries net/gross weight, dimensions
  and markings; proforma carries HS classifications, Incoterms, currency; ocean BoL is a document of title;
  AWB is a non-negotiable receipt); e2open & ONESOURCE documentation management and centralised broker
  documentation; SAP GTS customs documents.
- **Fields:** `doc_type` (`commercial_invoice | proforma_invoice | packing_list | certificate_of_origin |
  bill_of_lading_ocean | bill_of_lading_inland | air_waybill | shippers_letter_of_instruction |
  dangerous_goods_declaration | export_license_copy | insurance_certificate | customs_declaration | eei_aes`),
  `direction` (`export | import` — mirrors `Shipment.DIRECTION_CHOICES` semantics), `document_number` (the
  external BoL/invoice number, distinct from the internal `TD-` `number`), `issue_date`, `status`
  (`draft | issued | submitted | accepted | amended | void`), `shipper_party` / `consignee_party` /
  `notify_party` → `core.Party`, `country_of_origin`, `country_of_destination`, `incoterm` (EXW/FCA/FAS/FOB/
  CFR/CIF/CPT/CIP/DAP/DPU/DDP), `currency` → `accounting.Currency`, `declared_value`, `freight_charges`,
  `insurance_value`, `gross_weight_kg`, `net_weight_kg`, `package_count`, `vessel_or_flight`, `voyage_number`,
  `port_of_loading`, `port_of_discharge`, `container_numbers`, `is_negotiable`, `filing_reference`
  (AES/ITN/broker ref), `notes`, `document` FK.
- **FKs (all verified):** `scm.Shipment` (nullable — **4.6 owns the consignment**), `scm.Carrier`,
  `scm.PurchaseOrder`, `scm.SalesOrder`, `scm.TradeLicense` (nullable — the licence this export moves under,
  which is what decrements the balance), `core.Party`, `core.Document`, `accounting.Currency`.
- **Child `TradeDocumentLine`:** `item` → `scm.Item` (nullable), `description` *(snapshot)*, `hs_code`
  *(snapshot)*, `quantity`, `uom` → `scm.UOM` (nullable) or `uom_text`, `unit_value`, `line_value`,
  `net_weight_kg`, `country_of_origin`. Snapshot the description/HS code at issue so amending the item master
  can never rewrite an issued customs document (4.9's snapshot rule).
- **Plus one generic print view** (`templates/scm/compliance/tradedocument/print.html`, the HRM
  `relieving_letter.html` precedent). Per-form official layouts and AES/EDI filing are deferred.

### 3. `TradeLicense` [`LIC-`] — *the licence & permit register with a decrementing balance*
`models/ContractCompliance/TradeLicenses.py`

- **Justified by:** Descartes Export License Manager (multi-authority, application→approval→usage→expiration→
  reporting, real-time decrementing, expiry alerts + balance summaries, provisos/RWA, sub-licensees);
  ONESOURCE (checks availability & validity and decrements remaining licence value or volume per shipment);
  e2open (licence determination + tracking + usage, exemptions, end-user statements); SAP GTS Legal Control
  (licence checks by product × destination × partner); Shipping Solutions (ITAR/EAR determination, BIS-711
  end-user).
- **Fields:** `license_number`, `license_type` (`export_license | import_license | itar_dsp | ear_bis |
  taa_mla | import_permit | customs_authorization | hazmat_permit | fda_registration | license_exception |
  general_authorization | other`), `issuing_authority`, `issuing_country`, `holder_party` → `core.Party`
  (nullable — normally us), `end_user_party` → `core.Party` (nullable), `application_date`, `issue_date`,
  `expiry_date`, `status` (`draft | applied | approved | active | expiring | expired | suspended | revoked`,
  with `AUTO_STATUSES = ("active","expiring","expired")` — **copy `SupplierContract`'s `refresh_status()`
  contract verbatim**), `renewal_notice_days`, `authorized_value` + `used_value` *(editable=False)*,
  `authorized_quantity` + `used_quantity` *(editable=False)*, `currency` → `accounting.Currency`,
  `commodity_scope`, `eccn_or_hs`, `destination_countries`, `conditions` (provisos), `notes`, `document` FK.
- **Derived:** `days_to_expiry()`, `is_expiring_soon()`, `remaining_value`, `remaining_quantity`,
  `utilization_pct` — none stored.
- **The decrement is the feature:** posting a `TradeDocument` against a licence adds to `used_value`/
  `used_quantity` (guarded, clamped with `q2`/`q4`, and refusing to exceed the authorised amount). This is the
  one piece of real behaviour in 4.12 and is what every GTM leader charges for.

### 4. `SustainabilityAssessment` [`ESG-`] — *ethical sourcing + supplier carbon*
`models/ContractCompliance/SustainabilityAssessments.py`

- **Justified by:** EcoVadis (four themes + separate Carbon scorecard, per-theme score, overall 1–100, medals,
  maturity levels, strengths & improvement areas, annual validity); IntegrityNext (self-assessments, certificate
  collection, corrective actions, audit trail); Assent (declarations for REACH/RoHS/PFAS/Prop 65/SCIP/UFLPA/
  conflict minerals, high-medium-low risk drill-down); Sourcemap (risk score, certification review); Watershed &
  Persefoni (supplier engagement for Scope 3 collection).
- **Fields:** `party` → `core.Party` (the supplier or carrier — never a new vendor table), `assessment_date`,
  `valid_until`, `source` (`self_assessment | third_party_rating | desk_review | onsite_audit`),
  `provider` (free text, e.g. "EcoVadis"), theme scores 0–100 — `environment_score`,
  `labor_human_rights_score`, `ethics_score`, `sustainable_procurement_score`, `carbon_score`;
  `overall_score` *(editable=False, derived)*, `rating` *(editable=False, derived —
  `none|bronze|silver|gold|platinum`)*, `maturity_level` *(derived — insufficient→leader)*, `strengths`,
  `improvement_areas`, declaration flags (`conflict_minerals_declared`, `reach_declared`, `rohs_declared`,
  `forced_labor_attested`, `deforestation_declared`, `code_of_conduct_signed`),
  `scope1_tco2e` / `scope2_tco2e` / `scope3_tco2e` + `carbon_reporting_year` (supplier-declared),
  `status` (`draft | submitted | validated | expired`), `notes`, `document` FK.
- **Derive the headline, never hand-set it** — reuse the exact posture of the shipped
  `SupplierRiskAssessment.recompute_risk_level()` so two assessors cannot disagree on the medal.
- **Deliberately NOT a second risk register:** 4.2's `SupplierRiskAssessment` already scores financial /
  geopolitical / **compliance** / operational risk. 4.12 scores *sustainability*, which 4.2 does not, and the
  two are shown side by side on the supplier profile.

### 5. `scm:carbon_footprint_report` — *computed page, no table*
GLEC v3.2 / ISO 14083-style freight emissions over the **verified** `scm.Load.distance_km` × `Shipment.weight_kg`
(tonne-km) × a **closed, on-screen modal emission-factor table** keyed by the existing `MODE_CHOICES`
(`truckload/ltl/parcel/ocean/air/rail/intermodal`), aggregated by period, mode and carrier, with the supplier-
declared Scope 1/2/3 totals from model 4 shown alongside. The page must state its method, its factor source and
its limitations on screen — the 4.11 "explainable composite, and the page never says AI" precedent. Reached from
a chip in the Sustainability list header. **No new table** (a frozen `CarbonFootprintEntry` ledger is deferred).

### 6. Thin additive extensions to shipped models (nullable only, no backfill)
- `scm.SupplierContract`: `+ parent_contract` (self-FK, null) · `+ owner` (user FK, null) · `+ ("logistics",
  "Logistics / Carrier Agreement")` in `TYPE_CHOICES`. Precedent: **4.4 extending 4.3's `Location`**.
- `scm.Item`: `+ hs_code` · `+ country_of_origin` · `+ is_hazardous` · `+ un_number` (all blank-able).
  Justified by Descartes *Product Trade Manager* ("maintains tariff codes and product trade information"),
  e2open classification, Sphera hazmat classification, and the fact that the 4.12 bullet names HazMat.
  **Optional** — `TradeDocumentLine.hs_code` free text works without it; recommend it because otherwise every
  document re-types the same code. If the todo agent wants a zero-touch pass, drop this one.

### Sidebar wiring (`apps/core/navigation.py`, new `"4.12"` block)
| NavERP bullet | LIVE_LINK |
|---|---|
| Contract Repository | `scm:contract_list` — **4.2's list, now with amendment hierarchy + owner** (the 4.4→`scm:location_list` precedent) |
| Compliance Tracking | `scm:compliancerequirement_list` |
| Trade Documentation | `scm:tradedocument_list` |
| License Management | `scm:tradelicense_list` |
| Sustainability Tracking | `scm:sustainabilityassessment_list` (carbon report reached from its header chip) |

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Duty / tariff calculation, landed cost, customs duty & VAT** (e2open Duty Management, ONESOURCE FTA,
  SAP GTS Trade Preference, Thomson Reuters FTZ) → **4.18 Finance & Accounting Integration** ("Landed Cost
  Calculation", "Tax Management" are its bullets). 4.12's `TradeDocument.declared_value` is the input.
- **Contract & compliance dashboards / expiring-licence KPI tiles** (Coupa, Docusign CLM, Agiloft) → **4.11
  Supply Chain Analytics**, which is built and owns `KpiTarget`/`KpiSnapshot`/`SupplyChainAlert`.
- **Supplier ESG *risk* scoring as a risk register** (Sourcemap heat map, IntegrityNext risk) → **4.2 SRM**,
  which already ships `SupplierRiskAssessment` with a `compliance_score`. 4.12 scores sustainability
  performance, not risk.
- **Certification audits, non-conformances and CAPA** (Intelex findings/CAPAs) → **4.9 QMS**, which already
  ships `QualityAudit(audit_type="certification")`, the one `NonConformance` register and `CapaAction`.
- **Supplier/customer self-service portals for questionnaires and declarations** (IntegrityNext, Assent,
  EcoVadis, Sourcemap) → **4.16 Customer Portal** / the deferred vendor portal (4.1, 4.2 both parked it; L32
  bars a staff sidebar bullet from pointing at a login-gated portal page).
- **SLA monitoring against a logistics contract** (3PL service levels) → **4.17 Third-Party Logistics (3PL)
  Management** ("SLA Management" is its bullet). 4.12 stores the obligation; 4.17 measures the performance.
- **EDI transmission of trade documents** → **4.19 Integration & API Gateway** ("EDI Management").
- **Cold-chain / temperature compliance reporting for health & safety audits** → **4.15 Cold Chain Management**
  ("Compliance Reporting" is its bullet) — 4.12 does not model temperature excursions.
- **GDPR data-subject requests, consent, retention** → **Module 13 (documents/DMS)** and Module 0 policy;
  4.12 tracks GDPR only as a *requirement row with a proof cycle*, not a privacy engine.
- **Statutory ESG/CSRD disclosure filing and the P&L impact of carbon** → **apps/accounting** owns statutory
  reporting (L29); 4.12's carbon page says "operational estimate" on screen, as 4.11's margin page does.

---

## Deferred (later passes / integrations)

- **Restricted/denied-party & sanctions screening lists** (Descartes 500+/e2open 900+/ONESOURCE 750+ lists) —
  the screening *outcome* is modellable as a `ComplianceRequirement` check against a `core.Party`, but the lists
  themselves are a licensed data feed. Model the outcome later; never ship a fake list.
- **Licence determination and document determination from regulatory content** (SAP GTS Legal Control, e2open,
  Shipping Solutions) — needs the HS/ECCN × destination × party rule content. v1 links a `TradeDocument` to a
  `TradeLicense` manually.
- **Direct customs / AES-EEI / TRACES filing and broker connectivity** (Shipping Solutions AESDirect, SAP GTS
  government systems, e2open self-filing, Sourcemap TRACES) — 4.12 stores `filing_reference` + `status` only.
- **Per-form official PDF layouts** for each of the 13 document types — one generic print view this pass.
- **Clause library, template authoring, redlining and supplier-side e-signature** (Icertis, Agiloft, Ariba,
  Coupa, Docusign) — NavERP has the shape on the sales side (`crm.DocTemplate` + `crm.ContractDocument` +
  `SignerRecord`); a supplier-side equivalent is its own build, as 4.2 already concluded.
- **AI clause/obligation extraction, contract Q&A, adverse-media monitoring, AI-assisted screening**
  (Icertis Vera, Agiloft AI agents, Docusign metadata extraction, Sourcemap/IntegrityNext monitoring,
  Descartes AI Assist) — no LLM in this repo; 4.11 set the precedent that a page must not claim "AI".
- **Frozen assurance-grade emissions ledger** (`CarbonFootprintEntry`, Persefoni Footprint Ledger shape) and a
  large emission-factor library (Watershed's 500k factors) — this pass computes from 4.6 rows against a small
  closed factor table; 4.11's `KpiSnapshot` is the existing freezing mechanism if a number must be locked.
- **Multi-tier supplier mapping / sub-supplier discovery / chain-of-custody transactions** (Sourcemap) — needs a
  cascading supplier portal; `core.PartyRelationship` exists but tier-N discovery does not.
- **SDS/GHS chemical library, label generation, cradle-to-grave substance tracking** (Sphera) — a product-
  stewardship module. 4.12 gets only `Item.is_hazardous` + `un_number` and HazMat requirement rows.
- **Hard FK from a failed `ComplianceCheck` to `scm.NonConformance`** (adding a `compliance` value to
  `NonConformance.SOURCE_CHOICES`) — deliberately not done this pass; refactoring a shipped sub-module for a
  convenience link is what 4.11 refused to do. Link out by reference for now.
- **Duplicate-contract detection** (SAP Ariba) and **contract-value benchmarking against market norms**
  (Icertis) — differentiators with no data behind them here.
