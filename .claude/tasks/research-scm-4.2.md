# Research — Sub-module 4.2: Supplier Relationship Management (SRM) (Module 4 — Supply Chain Management, scm)

## Repo state checked first

- **LIVE_LINKS built so far in module 4:** only `"4.1"` (Purchase Requisition, RFQ, PO Management, Vendor
  Portal, Invoice Reconciliation) — `apps/core/navigation.py` lines 770–779. `4.2` has no entry yet, confirming
  it is the next unbuilt sub-module in Module 4.
- **Sibling models available to FK/aggregate from (verified in `apps/scm/models/ProcurementManagement/`):**
  - `PurchaseRequisition` [`PR-`], `PurchaseRequisitionLine`
  - `RFQ` [`RFQ-`], `RFQLine`, `RFQVendor` (`party`, `invited_at`, `has_responded`)
  - `RFQQuote` [`QT-`] (`party`, `received_date`, `lead_time_days`, `total`, `status`), `RFQQuoteLine`
  - `PurchaseOrder` [`PO-`] (`vendor→core.Party`, `order_date`, `expected_date`, `status`, `acknowledged_at`,
    `promised_ship_date`, `received_by_line()`), `PurchaseOrderLine`
  - `GoodsReceiptNote` [`GRN-`] (`receipt_date`, `match_status`, `bill→accounting.Bill`), `GoodsReceiptLine`
    (`quantity_received`, `quantity_rejected`, `rejection_reason`) — this is a **real quality signal** already
    in the data.
  - All four line tables (`PurchaseRequisitionLine`, `RFQLine`, `PurchaseOrderLine`, `GoodsReceiptLine`) use
    **free-text** `item_description`/`sku_hint`/`uom_hint` — `core.Item` is confirmed NOT built anywhere
    (grep: `^class Item` returns nothing under `apps/core/models`). 4.2's catalog lines must follow the same
    pattern.
- **Spine entities verified to exist** (`grep -rn "^class " apps/core/models/`): `Tenant`, `Party`, `PartyRole`,
  `Address`, `ContactMethod`, `PartyRelationship`, `Employment`, `OrgUnit`, `Activity`, `AuditLog`, `Document`.
  `PartyRole.ROLE_CHOICES` includes both `"vendor"` and `"supplier"` (`apps/core/models/PartyRole.py`); `scm`
  already has a shared helper `_supplier_parties(tenant)` in `apps/scm/forms/_common.py` that accepts
  **both** role spellings (`roles__role__in=("supplier","vendor")`) — 4.2 should reuse this helper, not
  re-derive the filter.
- **`core.Document`** (`apps/core/models/Document.py`) is a **generic** attachment
  (`content_type`/`object_id`/`GenericForeignKey`, `file`, `classification`, `version`) — confirmed existing.
  Supplier contracts/due-diligence files can attach to it via the generic relation with no new file field
  needed on 4.2's own models.
- **`accounting.Currency`** (`apps/accounting/models/GeneralLedger/Currencies.py`) and `accounting.PaymentTerm`
  (used as an FK by `scm.RFQQuote`/`scm.PurchaseOrder` already) are both confirmed live — 4.2 reuses them by
  string FK exactly like 4.1 does. `accounting.Bill` (AP bill) is confirmed live and already wired into the
  4.1 three-way match.
- **No `core.Contract`, `VendorScorecard`, `SupplierRisk*`, or `SupplierCatalog*` model exists anywhere**
  (grep: `^class Contract|^class VendorScorecard|^class SupplierRisk|^class SupplierCatalog` across `apps/`
  returns nothing under `core`/`accounting`/`scm`). The only near-namesake is
  `apps/crm/models/DocumentContract/Contracts.py` → `ContractDocument` [`CTR-`] — CRM 1.9's **customer-facing**
  e-signature sales contract (tied to `crm.Opportunity`/`core.Party` as the *customer*, with
  `SignerRecord`/token-based signing). It is a different domain (sales-side, e-sig workflow) from a
  procurement contract that needs renewal alerts and T&C tracking against a *supplier*```Party — 4.2 should
  **not** reuse it, but its shape (`TenantNumbered` + `Party` + `status` + `expires_at`) is useful internal
  precedent for how NavERP already models a "contract."
- **Existing prefixes already claimed in `scm`:** `PR`, `RFQ`, `QT`, `PO`, `GRN`. In `crm`: `CTR` (contracts).
  4.2's prefixes (`SC-` for contracts, `SRA-` for risk assessments, per the task brief) don't collide with any
  of these.
- **Module 6 (Procurement, built later) coordination flag:** the target-ERD module-coverage map also lists
  `VendorScorecard`, `Contract`, and `SupplierRisk` under Module 6. `apps/core/navigation.py`'s own comment on
  `"4.1"` already records the precedent for this exact situation: *"module that ships first owns the spine
  (...) and Module 6 will EXTEND these tables by FK (...) rather than re-declaring parallel schema"* (L29).
  4.2 ships first here too, so it should **own** `SupplierProfile`/`SupplierScorecard`/`SupplierContract`/
  `SupplierCatalog`/`SupplierRiskAssessment`; Module 6's future research/todo docs should extend these by FK
  (e.g. a richer strategic-sourcing scorecard wraps `scm.SupplierScorecard` rather than re-declaring one).

## Leaders surveyed (with source links)

1. **SAP Ariba Supplier Management / Supplier Risk / Supplier Lifecycle & Performance** — enterprise
   source-to-pay leader; deepest risk-dimension breadth (financial/operational/compliance) and weighted
   scorecard scoring — [Supplier Risk](https://www.sap.com/products/spend-management/supplier-risk.html),
   [Supplier Lifecycle and Performance](https://www.sap.com/products/spend-management/supplier-lifecycle.html),
   [Ariba Catalog](https://www.sap.com/products/spend-management/ariba-catalog.html)
2. **Coupa Supplier & Risk Management** — automated third-party risk detection (InfoSec/ABAC/GDPR), health
   scores, self-service onboarding portal —
   [Supplier Risk & Performance Management](https://www.coupa.com/products/source-to-contract/supplier-risk-performance/),
   [Optimize Supplier Onboarding](https://www.coupa.com/blog/optimize-supplier-onboarding-coupa-supplier-and-risk-management/)
3. **Ivalua Supplier Management** — 360° supplier record unifying onboarding/risk/performance/master data;
   scorecards embedded directly in supplier profiles, sourcing events, and contract records —
   [Supplier Management](https://www.ivalua.com/solutions/process/strategic-sourcing/supplier-management/),
   [Vendor Scorecards guide](https://www.ivalua.com/blog/vendor-scorecard/)
4. **JAGGAER Supplier Management & Performance** — full lifecycle (onboarding → qualification → risk scoring →
   performance) in one module; contract lifecycle management with renewal management and automated compliance
   monitoring — [Supplier Management](https://www.jaggaer.com/solutions/supplier-management)
5. **GEP SMART (GEP Quantum Intelligence)** — supplier repository with buyer- and supplier-maintained data;
   customizable qualitative+quantitative scorecards; strong ESG/diversity/sustainability scorecard layer —
   [Supplier Relationship Management](https://www.gep.com/software/gep-smart/procurement-software/supplier-management/supplier-relationship-management),
   [ESG Tracking & Reporting](https://www.gep.com/software/gep-quantum/gep-qi/esg-tracking-reporting)
6. **HICX Supplier Information Management** — master-record data governance across ERPs; automated bank-detail
   verification and tax-document validation at onboarding; standard KPI library for performance —
   [Supplier Information Management](https://www.hicx.com/modules/supplier-information-management/),
   [Supplier Performance Management](https://www.hicx.com/use-cases/supplier-performance-management/)
7. **Kodiak Hub** — modular SRM suite (onboarding, compliance, assessments, audits, performance); 360°
   scorecards with delivery/ESG/compliance metrics; `safe(SOURCE)` risk module scores suppliers on 39
   indicators (geopolitical/environmental/financial/natural-disaster); `fin(SIGHT)` financial risk ratings —
   [Supplier Scorecards](https://www.kodiakhub.com/use-cases/supplier-scorecards),
   [Supply Chain Risk & Resilience Monitoring](https://www.kodiakhub.com/platform/supply-chain-risk-and-resilience-monitoring)
8. **Graphite Connect** — supplier-onboarding specialist; AI/OCR document validation against submitted fields
   (TIN/EIN/company name), automated risk scoring at onboarding, shared network profile model —
   [Supplier Onboarding Platform](https://www.graphiteconnect.com/product/supplier-onboarding)
9. **Precoro** — mid-market supplier management with a supplier portal for catalog upload/update
   (price/description/stock), PunchOut catalog support, unified supplier document + order-status view —
   [Supplier Management Solution](https://precoro.com/solutions/supplier-management)
10. **TealBook Supplier Data Platform** — supplier master-data enrichment/cleansing (225M+ profiles), duplicate
    resolution, geopolitical/compliance/ESG risk visibility feeding other S2P suites —
    [Supplier Data Platform](https://www.tealbook.com/solutions/supplier-data-platform/)

*(10 surveyed, matching the task's suggested list — this sub-module's five bullets map cleanly onto how all
ten position their SRM/supplier-management product line, so no additional category of product was needed.)*

## Feature catalog (this sub-module only)

### Supplier Onboarding
- **Multi-stage onboarding/approval workflow** (draft → submitted → under review → approved/rejected/
  suspended) · seen in: SAP Ariba, JAGGAER, Coupa · priority: **table-stakes** · spine: new table
  `SupplierProfile` (`party→core.Party`, filtered via the existing `_supplier_parties` helper) ·
  buildable now
- **Qualification questionnaire** — a structured set of onboarding questions/checks the supplier must satisfy
  · seen in: SAP Ariba (weighted question scoring), JAGGAER (configurable questionnaire engine), GEP SMART ·
  priority: common · spine: `SupplierProfile` fields (`questionnaire_completed_at`, `questionnaire_notes`) for
  a **fixed** checklist this pass; a dynamic questionnaire *builder* (JAGGAER-grade) is differentiator/later ·
  buildable now (fixed fields), builder deferred
- **Due-diligence document checks** (tax ID/registration, business license, bank details, insurance) with a
  verified/unverified flag per item · seen in: Graphite Connect (AI/OCR field-vs-document validation), HICX
  (automated bank-detail verification, tax-document validation) · priority: **table-stakes** (the checklist) /
  differentiator (the automated verification) · spine: boolean flags on `SupplierProfile`
  (`tax_id_verified`, `business_license_verified`, `bank_details_verified`, `insurance_verified`); the actual
  files attach via **`core.Document`**'s existing generic FK (no new file field needed) · buildable now
  (manual verification); automated OCR/verification is integration/later
- **Supplier segmentation/tiering** (preferred/approved/probation/blacklisted) · seen in: Kodiak Hub, GEP SMART
  · priority: common · spine: `tier` choice field on `SupplierProfile`, a single source of truth other 4.2
  models (scorecard, risk) can read rather than re-deriving · buildable now
- **Commodity/category tagging** (what the supplier can provide) · seen in: GEP SMART, HICX · priority: common
  · spine: free-text `commodity_categories` field on `SupplierProfile` (no catalog taxonomy exists yet — see
  `core.Item` note above) · buildable now
- **Sanctions/watchlist screening at onboarding** · seen in: Coupa (InfoSec/ABAC/GDPR screening), Graphite
  Connect · priority: differentiator · spine: would be a boolean/result field, but the screening itself
  requires an external data feed · integration/later

### Supplier Scorecard
- **Periodic scorecard with weighted KPI categories: delivery, quality, price, responsiveness** (matches the
  NavERP.md bullet verbatim) · seen in: SAP Ariba (weighted scoring), Ivalua, GEP SMART, Kodiak Hub · priority:
  **table-stakes** · spine: new table `SupplierScorecard` (`vendor→core.Party`, `period_start`, `period_end`,
  four 0–100 category scores, computed `overall_score`) · buildable now
- **Auto-computed metrics from real transaction history rather than pure manual entry** · seen in: SAP Ariba
  ("objective overall scores… powered by detailed scorecards"), Ivalua ("scorecards embedded directly in
  supplier profiles… guided by current performance data") · priority: **differentiator** · spine: all four
  categories have a real 4.1 signal to derive from, verified against the actual models above —
  - *delivery*: on-time-in-full % from `GoodsReceiptNote.receipt_date` vs. the sourcing `PurchaseOrder`'s
    `expected_date`
  - *quality*: acceptance rate from `GoodsReceiptLine.quantity_received` vs. `quantity_rejected`
  - *price*: competitiveness from comparing an awarded `RFQQuote.total` against sibling quotes on the same
    `RFQ`
  - *responsiveness*: average `RFQVendor.invited_at` → `RFQQuote.received_date` turnaround
  · buildable now as a service function that pre-fills the four scores (still editable/overridable by staff,
  since not every supplier interaction runs through 4.1)
- **Scorecard trend/history across periods** · seen in: Ivalua, Kodiak Hub · priority: common · spine: multiple
  `SupplierScorecard` rows per `vendor` ordered by `period_start`, no separate history table needed ·
  buildable now
- **Issue/corrective-action flag tied to a low score** · seen in: SAP Ariba ("issue & incident management"),
  JAGGAER · priority: common · spine: `flagged_for_review` boolean + `action_notes` text field on
  `SupplierScorecard` — a full CAPA workflow belongs to Module 12 QMS (see Belongs-to-sibling below), this
  pass stays a flag · buildable now (flag), integration/later (full CAPA)
- **Cross-supplier / peer benchmarking** · seen in: Kodiak Hub · priority: differentiator · spine: read-only
  aggregation across a tenant's own `SupplierScorecard` rows — meaningful benchmarking against *other
  companies'* suppliers needs external/cross-tenant data, which is out of scope for a single-tenant ERP ·
  deferred

### Contract Management
- **Central supplier contract repository with key metadata** (dates, value, owner, status) · seen in: **all
  ten** surveyed to varying depth, clearest in SAP Ariba/Ivalua/JAGGAER · priority: **table-stakes** · spine:
  new table `SupplierContract` [`SC-`] (`vendor→core.Party`) · buildable now
- **Renewal/expiry alerts** — flag contracts nearing `end_date` so nobody lets a contract lapse silently ·
  seen in: JAGGAER ("renewal management"), SAP Ariba · priority: **table-stakes** · spine:
  `end_date`/`renewal_notice_days`/`auto_renew` fields + a derived `is_expiring_soon` property (list-view
  badge/filter); actual email/notification delivery is integration/later, the flag itself is buildable now
- **Terms & conditions / obligations tracking** · seen in: JAGGAER (contract lifecycle mgmt), Ivalua · priority:
  common · spine: `terms_summary` text field on `SupplierContract` — full clause-level extraction/obligation
  tracking is differentiator/later · buildable now (summary field)
- **Contract type classification** (master agreement, blanket PO, NDA, SLA, other) · seen generally across all
  S2P suites · priority: common · spine: `contract_type` choice field · buildable now
- **Contract value & payment terms** · seen in: SAP Ariba, Ivalua · priority: common · spine:
  `contract_value`/`currency→accounting.Currency`, `payment_terms→accounting.PaymentTerm` (both reused, not
  re-modeled) · buildable now
- **Attached contract document/file** · seen in: all · priority: table-stakes · spine: reuse **`core.Document`**
  via its generic FK — no new file field on `SupplierContract` · buildable now
- **E-signature / authoring workflow** · seen in: JAGGAER, SAP Ariba · priority: differentiator · spine: NavERP
  already has this shape for the *sales* side (`crm.ContractDocument` + `SignerRecord`, token-based signing) —
  a supplier-contract equivalent would mirror that pattern, but it is a substantial build on its own ·
  integration/later, not this pass
- **Automated compliance monitoring against contract terms** · seen in: JAGGAER · priority: differentiator ·
  spine: would need clause-level structured data this pass doesn't have · integration/later

### Supplier Catalog Management
- **Supplier-maintained catalog of items/services with price and lead time** · seen in: Precoro (vendor
  catalog upload via portal), Coupa, SAP Ariba · priority: **table-stakes** · spine: new tables
  `SupplierCatalog` (`vendor→core.Party`) + `SupplierCatalogItem` (free-text `item_description`/`sku_hint`/
  `uom_hint`, mirroring the exact pattern of 4.1's `RFQLine`/`PurchaseOrderLine` — `core.Item` still doesn't
  exist, per L28) · buildable now
- **Catalog validity window / active flag** (items effective from/to, active/inactive) · seen in: Precoro ·
  priority: table-stakes · spine: `effective_from`/`effective_to` on `SupplierCatalog`, `is_active` on
  `SupplierCatalogItem` · buildable now
- **Multi-supplier price comparison for equivalent items** · seen in: SAP Ariba ("cross-catalog searches
  across buyer, supplier, punch-out, ERP inventory") · priority: common · spine: this pairs naturally with the
  already-built `RFQQuote` comparison in 4.1 — no new model, just a read-only cross-catalog query once several
  suppliers' catalogs exist · buildable now (as a report/filter), no new table
- **PunchOut / real-time catalog integration to the supplier's own e-commerce site** (cXML/OCI-style Level 1/2
  punchout) · seen in: SAP Ariba (Ariba Network punchout), Precoro · priority: **differentiator** · spine: would
  need an external protocol integration and live pricing lookups · integration/later
- **Catalog approval workflow before items become orderable** · seen in: Coupa, SAP Ariba · priority: common ·
  spine: `status` (draft/active/inactive) on `SupplierCatalog` covers a light version; a full multi-step
  buyer-approval workflow is a later enhancement · buildable now (light), deferred (full workflow)
- **Standard commodity coding** (UNSPSC-style categorization) · seen in: SAP Ariba · priority: common · spine:
  free-text `category` field for now, deferred to a real taxonomy once `core.Item`/UOM land in Module 5 ·
  buildable now (free text), deferred (structured taxonomy)

### Risk Management
- **Multi-dimensional risk assessment: financial, geo-political, compliance** (matches the NavERP.md bullet) ·
  seen in: SAP Ariba (financial/operational/compliance dimensions), GEP SMART, Kodiak Hub (39 risk indicators
  across geopolitical/environmental/financial/natural-disaster) · priority: **table-stakes** · spine: new table
  `SupplierRiskAssessment` [`SRA-`] (`vendor→core.Party`) with `financial_risk_score`,
  `geopolitical_risk_score`, `compliance_risk_score` (0–100 or Low/Med/High each) · buildable now
- **Overall risk level / segmentation** (low/medium/high/critical) · seen in: SAP Ariba, GEP SMART, Kodiak Hub
  · priority: **table-stakes** · spine: `overall_risk_level` choice field, either hand-set or derived from the
  three category scores · buildable now
- **Operational/ESG/cybersecurity risk as a further dimension** · seen in: GEP SMART (cybersecurity, data
  privacy, business continuity), Kodiak Hub, TealBook · priority: common (beyond the bullet's named three) ·
  spine: optional `operational_risk_score` field, nullable so it doesn't force data entry this pass ·
  buildable now
- **Continuous/automated risk monitoring with change alerts** · seen in: SAP Ariba, Coupa ("instant
  notifications when a supplier's risk profile changes") · priority: **differentiator** · spine: a periodic,
  staff-triggered reassessment (`next_review_date` field + new `SupplierRiskAssessment` rows over time) is
  buildable now; true continuous monitoring needs an external data feed · integration/later
- **Third-party data enrichment** (credit ratings, sanctions lists, financial-health feeds) · seen in: Kodiak
  Hub `fin(SIGHT)`, TealBook · priority: differentiator · spine: none this pass — would be new fields fed by an
  external API · integration/later
- **Mitigation action tracking tied to an assessment** · seen in: SAP Ariba ("issue & incident management"),
  Coupa · priority: common · spine: `mitigation_actions` text field on `SupplierRiskAssessment` — a full
  issue-workflow (assignee, due date, status) is a later enhancement · buildable now (field), deferred
  (workflow)

### Beyond the bullets
- **Spend-under-management per supplier** (aggregated PO/Bill totals) · seen in: Coupa, GEP SMART · priority:
  common · spine: read-only aggregation over the already-live `scm.PurchaseOrder`/`accounting.Bill` — no new
  table; this is really a 4.11 Supply Chain Analytics concern once that sub-module exists · parked, not built
  this pass
- **Supplier self-service portal** (suppliers log in to view their own scorecard/contract/catalog/onboarding
  status) · seen in: SAP Ariba, Coupa, JAGGAER, Precoro, HICX — nearly universal at the enterprise tier ·
  priority: differentiator · spine: same L32 pattern already used for 4.1's "Vendor Portal" bullet — staff
  record the supplier-facing data (acknowledgements, catalog updates, onboarding status) on the supplier's
  behalf; a real externally-authenticated login is integration/later, not this pass
- **Single-source / concentration-risk flag** (over-dependence on one supplier for a critical item category) ·
  seen generally in SRM practice, not a single named leader feature · priority: common · spine: a derived
  query over `SupplierCatalogItem`/`PurchaseOrderLine`, not a stored field · deferred to a later analytics pass

## Recommended build scope (this pass — 5 models)

1. **`SupplierProfile`** — `tenant`, `party→core.Party` (unique_together `(tenant, party)`, filtered through
   the existing `_supplier_parties(tenant)` helper), `onboarding_status`
   (`draft/submitted/under_review/approved/rejected/suspended`), `tier`
   (`unrated/preferred/approved/probation/blacklisted`), `tax_id`, `tax_id_verified`,
   `business_license_verified`, `bank_details_verified`, `insurance_verified` (booleans),
   `questionnaire_completed_at`, `questionnaire_notes`, `commodity_categories` (free text),
   `onboarded_by`/`onboarded_at`, `reviewed_by`/`reviewed_at`, `rejection_reason`, `notes`. `TenantOwned`
   (no document number — it's a status wrapper on an existing `Party`, not a discrete transaction). Justified
   by: onboarding workflow + qualification questionnaire + due-diligence checks + segmentation (SAP Ariba,
   JAGGAER, Coupa, Graphite Connect, HICX, Kodiak Hub). FKs: `core.Party` (verified).

2. **`SupplierScorecard`** [`SCR-`] — `tenant`, `number`, `vendor→core.Party`, `period_start`, `period_end`,
   `delivery_score`, `quality_score`, `price_score`, `responsiveness_score` (0–100 each, pre-filled by a
   service function from 4.1 signals — see catalog above — and staff-editable), `overall_score` (weighted,
   recomputed), `evaluated_by`, `evaluated_at`, `flagged_for_review` (bool), `action_notes`, `status`
   (`draft/finalized`). `TenantNumbered`. Justified by: the scorecard bullet verbatim + auto-computation from
   real transaction history (SAP Ariba, Ivalua, GEP SMART, Kodiak Hub). FKs: `core.Party`; derives from
   `scm.GoodsReceiptNote`/`GoodsReceiptLine`, `scm.RFQQuote`, `scm.RFQVendor` (all verified).

3. **`SupplierContract`** [`SC-`] — `tenant`, `number`, `vendor→core.Party`, `title`, `contract_type`
   (`master_agreement/blanket_po/nda/sla/other`), `start_date`, `end_date`, `auto_renew`,
   `renewal_notice_days`, `contract_value`, `currency→accounting.Currency`,
   `payment_terms→accounting.PaymentTerm`, `terms_summary`, `status`
   (`draft/active/expired/terminated/renewed`), `owner→settings.AUTH_USER_MODEL`, `notes`. `TenantNumbered`.
   Attached files use `core.Document`'s existing generic FK — no new file field. Justified by: contract
   repository + renewal alerts + T&C tracking (matches the bullet verbatim; SAP Ariba, Ivalua, JAGGAER). FKs:
   `core.Party`, `accounting.Currency`, `accounting.PaymentTerm`, `core.Document` (all verified).

4. **`SupplierCatalog`** [`CAT-`] + **`SupplierCatalogItem`** — `SupplierCatalog`: `tenant`, `number`,
   `vendor→core.Party`, `name`, `category` (free text), `currency→accounting.Currency`, `effective_from`,
   `effective_to`, `status` (`draft/active/inactive`), `notes`. `SupplierCatalogItem` (child, no tenant FK,
   reached through parent per the scm forms `_scope_to_parent` convention): `catalog→SupplierCatalog`,
   `item_description`, `sku_hint`, `uom_hint` (free text — `core.Item` unbuilt, L28), `unit_price`,
   `lead_time_days`, `min_order_qty`, `is_active`. Justified by: supplier catalog management (matches the
   bullet verbatim; Precoro, Coupa, SAP Ariba) + validity windows (Precoro). FKs: `core.Party`,
   `accounting.Currency` (verified); mirrors the free-text-line pattern already used by
   `RFQLine`/`PurchaseOrderLine`.

5. **`SupplierRiskAssessment`** [`SRA-`] — `tenant`, `number`, `vendor→core.Party`, `assessment_date`,
   `assessed_by→settings.AUTH_USER_MODEL`, `financial_risk_score`, `geopolitical_risk_score`,
   `compliance_risk_score` (0–100 or Low/Med/High each — matches the bullet's three named dimensions
   verbatim), `operational_risk_score` (nullable — beyond-the-bullet addition seen in GEP SMART/Kodiak
   Hub/TealBook), `overall_risk_level` (`low/medium/high/critical`), `risk_notes`, `mitigation_actions`,
   `next_review_date`, `status` (`draft/finalized/superseded`). `TenantNumbered`. Justified by: the risk bullet
   verbatim + segmentation + mitigation tracking (SAP Ariba, GEP SMART, Kodiak Hub, Coupa). FKs: `core.Party`
   (verified).

*(5 top-level entities / 7 concrete tables counting the two child tables — at the top of the requested 4–5
range because 4.2 names five genuinely distinct capability clusters and, per the 4.1 precedent already set in
this codebase, child rows are what makes a catalog or a scorecard's data usable rather than a single flat row.
None of it duplicates `core.Party`/`core.Document`/`accounting.Currency`/`accounting.PaymentTerm`/
`accounting.Bill`, which are reused as-is; none of it duplicates 4.1's `PurchaseOrder`/`RFQQuote`/
`GoodsReceiptNote`, which are read from, not re-modeled.)*

## Belongs to sibling sub-modules (parked, not scoped here)

- **Spend-under-management dashboards / OTIF trend charts across all suppliers** → 4.11 Supply Chain Analytics
  (per `research-scm.md`'s existing sub-module map) — 4.2 exposes the raw `SupplierScorecard`/
  `SupplierRiskAssessment` rows that 4.11 would later aggregate.
- **Full CAPA (corrective/preventive action) workflow off a low scorecard score or a rejected-goods trend** →
  4.9 Quality Management System / Module 12 Quality (already flagged as the true owner in `research-scm.md`).
  4.2's `flagged_for_review`/`action_notes` fields are the thin hook, not a parallel CAPA system.
- **Landed-cost allocation, tax/VAT/customs on supplier goods** → 4.18 Finance & Accounting Integration
  (reuses `accounting.Bill`/`JournalEntry`, already flagged in `research-scm.md`).
- **Strategic sourcing scorecards, e-auctions, contract authoring with e-signature, weighted-scoring RFP
  builder** → Module 6 Procurement (per the target-ERD coverage map and the L29 ships-first precedent already
  recorded on `"4.1"` in `apps/core/navigation.py`) — Module 6 should extend `scm.SupplierScorecard`/
  `scm.SupplierContract`/`scm.SupplierRiskAssessment` by FK when it lands, not re-declare parallel tables.
  Carry this note into Module 6's future `research-procurement.md`.

## Deferred (later passes / integrations)

- **Supplier self-service portal (real external login)** — same L32 pattern as 4.1's Vendor Portal: staff
  record onboarding status/catalog updates/contract acknowledgements on the supplier's behalf this pass; a
  true externally-authenticated supplier login is a later, larger build (would need its own auth surface).
- **PunchOut / cXML-OCI live catalog integration** — needs an external protocol + live pricing lookups from
  the supplier's own e-commerce system (SAP Ariba, Precoro). Model the catalog as NavERP-hosted data first.
- **E-signature contract authoring workflow** — NavERP already has this shape on the sales side
  (`crm.ContractDocument` + `SignerRecord`); a supplier-contract equivalent is a legitimate future build but
  substantial enough to be its own pass, not folded into this one.
- **Automated/continuous risk monitoring with external data feeds** (sanctions screening, credit ratings,
  cybersecurity scores, geopolitical alerts) — Coupa, Kodiak Hub `fin(SIGHT)`, TealBook all lean on third-party
  data providers. `SupplierRiskAssessment.next_review_date` supports a periodic *manual* reassessment cadence
  now; continuous automated monitoring is integration/later.
- **Dynamic qualification-questionnaire builder** (configurable question sets, weighted scoring per question,
  per-category templates) — JAGGAER/SAP Ariba grade capability; this pass ships a fixed due-diligence checklist
  on `SupplierProfile` instead.
- **Structured commodity/UNSPSC-style catalog taxonomy** — waits on `core.Item`/UOM landing with Module 5;
  `SupplierCatalogItem` stays free-text until then, mirroring the exact migration note already recorded for
  4.1's line tables.
- **Full catalog buyer-approval workflow** (multi-step review before a supplier's catalog update goes live) —
  `SupplierCatalog.status` covers a light draft/active/inactive gate this pass; a formal approval chain is a
  later enhancement.
- **Single-source/concentration-risk analytics and peer-supplier benchmarking** — both need either
  cross-tenant data (benchmarking) or a broader analytics layer (concentration) that belongs with 4.11.
