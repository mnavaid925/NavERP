# Research — Sub-module 6.16: Supplier Performance & Evaluation (Module 6 — Procurement Management System, `procurement`)

Scope source: `NavERP.md` lines 1101–1107 (five bullets: KPI Definition & Setup · Scorecard Generation ·
360-Degree Feedback Collection · Performance Improvement Plans (PIP) · Benchmarking & Trending).

---

## Repo state checked first

### LIVE_LINKS built so far in module 6
`apps/core/navigation.py` carries `6.1 … 6.15` (grep on `^\s*"6\.\d+"`, lines 1413–1626). **`6.16` has no
entry — it is the next unbuilt sub-module.** `6.17`/`6.18`/`6.19` are also unbuilt.

### Spine entities VERIFIED to exist (grep evidence — L28: the ERD is intent, the grep is truth)

| Entity | Evidence | Relevance to 6.16 |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5` | **the supplier master.** Never a new vendor table |
| `core.PartyRole`, `core.OrgUnit`, `core.Document`, `core.Activity`, `core.Tenant` | `apps/core/models/{PartyRole,OrgUnit,Document,Activity,Tenant}.py:5` | role = supplier; OrgUnit = the rating stakeholder's department; Document = evidence pack |
| **`scm.SupplierScorecard`** | `apps/scm/models/SupplierRelationshipManagement/SupplierScorecards.py:11` | **ALREADY EXISTS — the period container. 6.16 extends it by FK, never re-declares it (L36)** |
| `scm.SupplierProfile` | `…/SupplierProfiles.py:12` | `tier` (strategic/preferred/approved/transactional) + `category` — drives which KPI set applies and at what cadence |
| `scm.SupplierRiskAssessment` | `…/SupplierRiskAssessments.py:10` | `risk_index` 1.00–5.00 — the second axis of a performance × risk quadrant |
| `scm.KpiTarget` / `scm.KpiSnapshot` | `apps/scm/models/SupplyChainAnalytics/{KpiTargets,KpiSnapshots}.py:59 / :94` | the **pattern** to copy (definition + frozen measurement), **not** the table to reuse — see "Why 6.16 does not reuse `scm.KpiTarget`" below |
| `scm.PurchaseOrder` / `PurchaseOrderLine` | `…/ProcurementManagement/PurchaseOrders.py:15 / :172` | `vendor`, `expected_date`; line `quantity` (ordered) → OTD/OTIF |
| `scm.GoodsReceiptNote` / `GoodsReceiptLine` | `…/GoodsReceiptNotes.py:15 / :166` | `receipt_date`, `status`; line `quantity_received` / `quantity_rejected`, `po_line` → OTD, OTIF, defect rate |
| `scm.RFQ` / `RFQQuote` | `…/Rfqs.py:12 / :104` | `issue_date`, `received_date`, `total` → price competitiveness, quote turnaround |
| `scm.QualityAudit`, `scm.CapaAction`, `scm.SustainabilityAssessment` | `apps/scm/models/QualityManagement/{QualityAudits,CapaActions}.py`, `ContractCompliance/SustainabilityAssessments.py` | candidate future derived sources (audit score, CAPA closure, ESG) — **not** wired this pass |
| `procurement.VendorSuspension` | `apps/procurement/models/VendorManagement/VendorSuspensions.py:27` | `REASON_CHOICES` already has `quality` / `delivery` — the escalation target for a failed PIP |
| `procurement.VendorPortalAccess`, `VendorInvoiceSubmission` | `…/VendorManagement/` | the supplier-side identity a supplier self-review would use (deferred UI) |
| `procurement.ReceiptDiscrepancy` [RDS-], `ReturnToVendor` [RTV-] | `…/GoodsReceiptInspection/` | 6.12 signals → NCR rate, RTV rate |
| `procurement.SupplierInvoice` [SIV-], `InvoiceMatchVariance`, `InvoiceDispute` [DSP-] | `…/InvoiceVoucherManagement/` | 6.13 signals → invoice accuracy, dispute rate/ageing |
| `procurement.DeliverySchedule` [DSC-], `Backorder` [BKO-], `AdvancedShipmentNotice` [ASN-] | `…/OrderFulfillment/` | 6.11 signals → promise adherence (`promised_date` vs `need_by_date`), backorder rate |
| `procurement.PurchaseOrderChange` [PCO-] | `…/PurchaseOrderManagement/` | 6.10 signal → PO change/churn rate |
| `hrm.PerformanceImprovementPlan` [PIP-] | `apps/hrm/models/PerformanceImprovement/PerformanceImprovementPlans.py:22` | **in-repo PIP precedent** (issue / expected standards / goals / support / measurement / start-end / extend / outcome / acknowledge) — mirror its shape for suppliers |

### Spine entities VERIFIED NOT to exist
`grep -rn "class (SupplierKpi|SupplierFeedback|SupplierImprovement|SupplierEvaluation|KpiDefinition|SupplierPerformance)\w*\(" apps/`
→ **No matches.** None of the four proposed model names collides anywhere in the repo.

Number-prefix scan (`grep -rn 'NUMBER_PREFIX = "\w+"' apps/`): `SKP`, `SFB`, `SIP` are all **free**.
(`PIP` is taken by `hrm.PerformanceImprovementPlan`, `SCR` by `scm.SupplierScorecard` — avoid both.)

### The as-built `scm.SupplierScorecard`, read in full — this is the gap

```
NUMBER_PREFIX = "SCR"; TenantNumbered
party FK core.Party · period_start · period_end · status draft/published/archived
delivery_score · quality_score · price_score · responsiveness_score   ← FOUR HARD-CODED COLUMNS (0-100, nullable)
WEIGHTS = {"delivery": 35, "quality": 35, "price": 15, "responsiveness": 15}   ← HARD-CODED IN PYTHON
overall_score (editable=False) · grade A–F (editable=False) · manual_override · signal_summary (editable=False) · notes
recompute_overall()      — weighted blend, re-weighted over whichever dimensions are present
recompute_from_signals() — derives delivery from GRN vs PO expected_date, quality from GRN reject qty,
                           price from RFQQuote vs best quote, responsiveness from quote turnaround days
```

**What it already solves:** the period rating identity, the A–F grade, the published/archived lifecycle, the
manual-override escape hatch, and four real derived signals.
**What it cannot do — the whole of 6.16's opportunity:**
1. A tenant cannot **define a KPI**. The dimension set is four Python attributes; adding "defect PPM",
   "invoice accuracy", "NCR rate", "ESG score" means editing `SupplierScorecards.py`.
2. A tenant cannot **set a weight**. `WEIGHTS` is a class attribute — every tenant, every category, every
   supplier tier gets 35/35/15/15. Every product surveyed treats weight as configuration
   (Ivalua 40/20/15/15/10, LeanLinking 40/30/20/10 with a quality-weighted pharma profile, Ariba weights
   editable at both template and scorecard level, Jaggaer "flexible rating models for individual categories,
   locations or business groups").
3. There is **no target, threshold or direction** per dimension, so nothing can be banded green/amber/red and
   nothing can trigger an action.
4. There is **no stakeholder input path at all**. Half of what the market scores is soft — LeanLinking's
   "soft metrics" 10 % block, Ariba's survey-sourced KPIs, Coupa's end-user ratings, SupplyHive's Hive360.
5. There is **no corrective-action object**. `notes` is a TextField.

### Why 6.16 does NOT reuse `scm.KpiTarget` / `scm.KpiSnapshot` (justified, not assumed)

They are the right *pattern* and the wrong *table*, for four reasons read straight out of their own files:

* **`KpiTarget.metric` is a closed registry of supply-chain metrics** whose resolvers live in
  `apps/scm/analytics.py`, and its docstring says so explicitly ("a metric key is a promise that a *reviewed*
  resolver exists for it", "No expression field… deliberately"). Adding supplier-evaluation metrics would mean
  procurement editing SCM's `SupplyChainAnalytics/_choices.py` and SCM's analytics resolvers — a cross-module
  write into another app's owned vocabulary, the exact thing L36 forbids.
* **`KpiTarget` has no `weight`.** It cannot express "delivery is 35 % of this supplier's composite"; it is a
  *goal + alert band* for one network metric, one row per goal. A scorecard KPI is a *component of a
  composite* — a different noun.
* **Its scopes are `all / category / location / carrier / vendor`** with four typed FKs, none of which is
  "supplier tier". 6.16 needs `applies_to` = all suppliers / one tier — a different axis.
* **`KpiSnapshot` is keyed `(tenant, kpi_target, period_start, dimension_key)`** and stores a network
  measurement. A 6.16 score line is keyed to a *supplier scorecard*, carries a *graded 0-100 score* and a
  *frozen weight*, and can be *survey-* or *hand-*sourced. `KpiSnapshot` deliberately has **no ModelForm**
  because "a hand-typed value would be a fabricated measurement" — 6.16's manual and survey KPIs are exactly
  the legitimate hand-entered case, which is a different contract.

**What 6.16 does borrow from them, deliberately:** the definition/measurement split, `direction` +
target/warning/critical band ordering validated in `clean()`, `*_at_time` frozen columns so a later retune
cannot rewrite history, the `breakdown` JSONField that makes a composite explainable, the colour-named
`BAND_CSS` map (L33 — `badge-green`/`badge-amber`/`badge-red`/`badge-muted` exist; `badge-success` does not),
and idempotent `unique_together` so a re-run updates instead of stacking.

### Sibling research files consulted
`research-procurement-6.11.md:267,367` · `research-procurement-6.12.md:287,517,552` ·
`research-procurement-6.14.md:575` · `research-scm-4.11.md:526` — all four explicitly **deferred to 6.16**:
supplier OTD KPI + scorecards + benchmarking, discrepancy/rejection rates as supplier KPIs, and
"supplier 360 feedback, PIPs, external industry benchmarks". That deferral list **is** this sub-module's
backlog and is fully covered below.

---

## Leaders surveyed (with source links)

1. **SAP Ariba Supplier Lifecycle & Performance (SPM projects)** — the reference architecture: a governed KPI
   library in the Sourcing Library, scorecard templates ("Master documents") that spawn periodic scorecards
   ("Period documents"), and surveys that push graded answers into KPIs —
   [creating scorecards](https://learning.sap.com/courses/sap-ariba-supplier-management-supplier-performance-management-projects/creating-scorecards) ·
   [creating surveys](https://learning.sap.com/courses/sap-ariba-supplier-management-supplier-performance-management-projects/creating-surveys) ·
   [product page](https://www.sap.com/products/spend-management/supplier-lifecycle.html)
2. **Ivalua Supplier Performance Management** — "Signal-to-Action": KPI thresholds that auto-trigger corrective
   action workflows, weighted composite scoring, Improvement Plan Assistant —
   [supplier scorecards](https://www.ivalua.com/blog/supplier-scorecards/) ·
   [vendor scorecard mechanics](https://www.ivalua.com/blog/vendor-scorecard/)
3. **Coupa Supplier Risk & Performance Management** — performance scorecards driven by *data feeds and
   end-user ratings*, used to segment partners; standard vs advanced (inherent/residual scoring) tiers —
   [product page](https://www.coupa.com/products/source-to-contract/supplier-risk-performance/)
4. **JAGGAER Supplier Management & Performance** — flexible rating models per category/location/business
   group, automated activation of development & corrective action plans when performance dips, bonus-penalty
   schemes, 360° Supplier Snapshot —
   [solution page](https://www.jaggaer.com/solutions/supplier-management)
5. **GEP SMART / Quantum Supplier Performance Management** — qualitative **and** quantitative scorecards, SLA
   monitoring, trend analysis by category/region/business unit, automated alerts, collaborative structured
   action plans —
   [product page](https://www.gep.com/software/gep-smart/procurement-software/supplier-management/supplier-performance-management)
6. **Zycus iPerform / iSupplier** — collaborative KPI design, data captured **both automatically and through
   stakeholder surveys**, benchmark management, published balanced scorecards —
   [supplier management](https://www.zycus.com/solution/supplier-management) ·
   [SPM software](https://www.zycus.com/solution/supplier-performance-management-software)
7. **HICX** — a *governed* KPI library editable no-code, survey data and transactional data combined into one
   weighted scorecard, continuously refreshed rather than compiled quarterly, configurable thresholds and
   alerts, scores visible to the supplier —
   [SPM use case](https://www.hicx.com/use-cases/supplier-performance-management/) ·
   [platform overview](https://www.hicx.com/product-overview/)
8. **Kodiak Hub kp(INSIGHT)** — OTIF / PPM / CAPA-ageing / audit-score scorecards with monthly **and
   trailing-12-month** trends, flag-vs-target, commentary fields, a CAPA register
   (finding · root cause · action · owner · due date · status · evidence · verification date), and
   share-of-business decisions at QBRs —
   [SPM process, templates & cadence](https://www.kodiakhub.com/blog/supplier-performance-management-process-templates-cadence) ·
   [top 15 SPM KPIs with formulas](https://www.kodiakhub.com/blog/supplier-performance-management-kpis)
9. **SupplyHive (Hive Scorecard + Hive360)** — multi-stakeholder 360 reviews, supplier **self-review on the
   same criteria**, **perception-gap** visualisation, trend view, segmentation matrix, NLP theme/sentiment
   extraction —
   [360 supplier view](https://supplyhive.com/why-procurement-needs-a-360-supplier-view-performance-risk-relationship-insights-in-one-system/) ·
   [segmentation](https://supplyhive.com/using-segmentation-to-build-a-high-performing-supplier-pool/)
10. **LeanLinking Supplier Performance Scorecard** — the cleanest statement of the **hard (ERP-derived) vs soft
    (stakeholder-survey) metric split**, industry weight profiles, automated survey distribution, 12-month
    history for contract decisions —
    [scorecard guide](https://leanlinking.com/guides/supplier-performance-scorecard/)
11. *(secondary, quality-regulated slice)* **MasterControl** and **ComplianceQuest PartnerQuest** — Supplier
    Scorecard + SCAR (supplier corrective action request) with automated routing and approved-vendor-list
    effects; **EcoVadis** — sustainability scorecard with Corrective Action Plans and a 12-month rating
    validity window; **Prewave** — external risk signals rather than KPI scorecards —
    [market survey](https://suplari.com/blog/best-supplier-performance-management-software)

---

## Feature catalog (this sub-module only)

Legend — priority: `table-stakes` (nearly every leader) · `common` (most) · `differentiator` (a few standouts).

### Bullet 1 — KPI Definition & Setup

- **Governed, reusable KPI library** — KPIs are authored once in a central library and referenced by many
  scorecards, never invented inside one scorecard (Ariba is emphatic: creating KPIs directly in a scorecard is
  "strongly discouraged" because it destroys cross-supplier comparability) · seen in: SAP Ariba, HICX, Zycus,
  State of Flux · priority: table-stakes · spine: **new table `SupplierKpi`** (nothing in the repo is a
  supplier-scoped, weighted KPI definition; `scm.KpiTarget` is a network metric goal — see above) ·
  buildable now
- **KPI category / dimension taxonomy** — delivery, quality, cost, service-responsiveness, compliance, ESG,
  innovation, risk · seen in: Ivalua (5 core), Kodiak (adds ESG + innovation), Zycus (balanced scorecard),
  GEP · priority: table-stakes · spine: `CATEGORY_CHOICES` on `SupplierKpi` · buildable now
- **Per-KPI weight** — the weight is configuration, not code. Ivalua's worked example is 40/20/15/15/10;
  LeanLinking's manufacturing profile 40/30/20/10 with a pharma variant that lifts quality to 40 %; Ariba
  allows weights to be overridden per scorecard · seen in: **all ten** · priority: table-stakes ·
  spine: `SupplierKpi.weight` — **this is the field that replaces the hard-coded
  `SupplierScorecard.WEIGHTS` dict** · buildable now
- **Direction (higher/lower is better)** — OTIF higher-is-better, PPM/NCR/expedite-cost lower-is-better ·
  seen in: Kodiak (an explicit direction column on all 15 KPIs), Ivalua · priority: table-stakes ·
  spine: `SupplierKpi.direction`, ported from the verified `scm.KpiTarget.direction` + its band-ordering
  `clean()` · buildable now
- **Target + amber/red thresholds** — OTIF ≥ 98 %, PPM ≤ 250, audit ≥ 90 %, expedite ≤ 0.5 % of spend;
  Ivalua bands green/yellow/red (OTD ≥ 95 % green, defect ≤ 2 % green) · seen in: Kodiak, Ivalua, HICX,
  LeanLinking · priority: table-stakes · spine: `target_value` / `warning_threshold` / `critical_threshold`
  on `SupplierKpi`, ordering validated against `direction` (direct port of `KpiTarget.clean()`) · buildable now
- **Data source per KPI: derived / survey / manual** — Ariba names exactly three (report-based, survey-based,
  and unmapped KPIs the scorecard owner types by hand); HICX "combines survey-based and transactional data
  into a single scorecard"; LeanLinking splits hard ERP metrics from soft stakeholder metrics · seen in:
  SAP Ariba, HICX, LeanLinking, Zycus, GEP · priority: table-stakes ·
  spine: `SupplierKpi.source` + a **closed** `derived_metric` registry (only metrics with a reviewed resolver
  over as-built tables — same discipline as `KpiTarget.metric`) · buildable now
- **Unit of measure** — %, days, count, PPM, money, score · seen in: Kodiak (per-KPI formulas), Ariba
  (quantitative vs qualitative) · priority: common · spine: `SupplierKpi.unit`; render via the same
  unit-formatting idea as `KpiSnapshot.format_metric_value` · buildable now
- **Scoring method: banded vs linear vs direct** — Ariba distinguishes *pre-grading* (grades declared in
  advance, calculated automatically) from *post-grading*; Ivalua computes metric-score × weight and sums ·
  seen in: SAP Ariba, Ivalua · priority: common · spine: `SupplierKpi.scoring_method` · buildable now
- **KPI applicability by supplier tier / category** — "flexible rating models for individual categories,
  locations or business groups" (Jaggaer); KPI setup by supplier tier (State of Flux); category-adjusted
  weights (Ivalua: delivery 40 % in direct materials, 10 % in SaaS) · seen in: JAGGAER, State of Flux,
  Ivalua, Kodiak · priority: common · spine: `SupplierKpi.applies_to` + `applies_to_tier`, matching the
  **verified** `scm.SupplierProfile.TIER_CHOICES` · buildable now
- **Review cadence per KPI/tier** — strategic monthly, preferred quarterly, transactional less often;
  Kodiak splits a 60-min monthly ops review from a 90–120-min QBR · seen in: Ivalua, Kodiak, LeanLinking ·
  priority: common · spine: `SupplierKpi.review_frequency` (stored now; the auto-scheduler is deferred) ·
  buildable now (field) / later (scheduling job)
- **KPI owner** — "each KPI requires an assigned owner and clear decision context" · seen in: Kodiak, HICX ·
  priority: common · spine: `SupplierKpi.owner` FK `settings.AUTH_USER_MODEL` (the `KpiTarget.owner`
  precedent) · buildable now
- **Maps-to-dimension bridge** — *NavERP-specific, no competitor equivalent:* a KPI may declare which of the
  four existing `scm.SupplierScorecard` columns it feeds, so the tenant's own KPIs keep the existing SCM
  scorecard page truthful instead of orphaning it · priority: differentiator (repo-specific) ·
  spine: `SupplierKpi.maps_to_dimension` ∈ delivery/quality/price/responsiveness/'' · buildable now
- **Master KPI identifiers for cross-project roll-up** — Ariba gives library KPIs unique IDs so scores roll up
  across scorecards · seen in: SAP Ariba · priority: common · spine: `SupplierKpi.code`,
  `unique_together (tenant, code)` · buildable now
- **No-code KPI authoring by procurement, no IT dependency** — HICX sells this explicitly · seen in: HICX,
  Ivalua · priority: differentiator · spine: it *is* the CRUD on `SupplierKpi` · buildable now

### Bullet 2 — Scorecard Generation

- **Automated composite score from weighted KPIs** — metric score × weight, summed, re-weighted over the KPIs
  actually present · seen in: **all ten** · priority: table-stakes · spine: **reuses
  `scm.SupplierScorecard`** as the period container (L36) + **new child table `SupplierKpiScore`**; the
  composite is arithmetic over frozen line values, mirroring the existing
  `SupplierScorecard.recompute_overall()` re-weighting rule · buildable now
- **Master template → period document** — a scorecard definition that recurs, producing one document per
  period; changes made on the master affect future periods, changes on a period affect only that period ·
  seen in: SAP Ariba (explicit Master/Period documents), GEP, Kodiak · priority: table-stakes ·
  spine: `SupplierKpi` (+ `applies_to_tier` + `is_active`) plays the master; `scm.SupplierScorecard` +
  `SupplierKpiScore` rows play the period document. **A separate named template model is deferred** — see
  Deferred · buildable now
- **Frozen per-period KPI values** — Kodiak keeps monthly plus trailing-12-month history; LeanLinking keeps
  12 months for contract decisions · seen in: Kodiak, LeanLinking, GEP, SupplyHive · priority: table-stakes ·
  spine: `SupplierKpiScore.measured_value` / `score` / `weight_applied` / `target_at_time`, frozen at
  generation. **This is why the score lines must be stored, not recomputed on render:** GRNs can be
  back-dated, `ReceiptDiscrepancy.status` and `InvoiceDispute.resolution` change after the fact, so
  re-deriving a closed quarter silently rewrites it — the same argument `KpiSnapshot`'s docstring makes ·
  buildable now
- **Idempotent re-run** — re-generating a period updates its rows rather than stacking duplicates ·
  seen in: HICX (continuous refresh), Ivalua · priority: common ·
  spine: `unique_together (tenant, scorecard, kpi)` on `SupplierKpiScore` (the `KpiSnapshot` precedent) ·
  buildable now
- **Explainable score / audit trail of the arithmetic** — LeanLinking sells "audit trail for rating
  decisions"; HICX ships audit trails; the existing `SupplierScorecard.signal_summary` is the same idea as
  free text · seen in: LeanLinking, HICX, Kodiak · priority: common ·
  spine: `SupplierKpiScore.breakdown` JSONField (structured version of `signal_summary`; the
  `KpiSnapshot.breakdown` precedent) · buildable now
- **Manual entry for unmapped KPIs** — Ariba's third KPI type; the scorecard owner types the value ·
  seen in: SAP Ariba, GEP ("capture unlimited information using forms and scorecards") · priority:
  table-stakes · spine: an edit form on `SupplierKpiScore` restricted to `measured_value` + `comment`, only
  for lines whose `source_at_time == 'manual'` · buildable now
- **Green/amber/red banding per KPI line** — seen in: Ivalua, Kodiak ("flags vs. target"), HICX, GEP ·
  priority: table-stakes · spine: `SupplierKpiScore.band` + a colour-named `BAND_CSS` map (L33) · buildable now
- **Commentary against a specific KPI** — Kodiak's scorecard commentary fields; Ivalua embeds comment threads
  tied to individual KPIs in the supplier portal · seen in: Kodiak, Ivalua · priority: common ·
  spine: `SupplierKpiScore.comment` · buildable now (the supplier-facing thread is deferred)
- **Derived metrics computed from transactional history** — the derived registry, and exactly what is
  computable **today** against verified as-built tables:

  | Derived metric | Formula | As-built source (verified) | Status |
  |---|---|---|---|
  | On-time delivery % | on-time receipts ÷ datable receipts | `scm.GoodsReceiptNote.receipt_date` vs `PurchaseOrder.expected_date` | already proven in `recompute_from_signals()` |
  | **OTIF %** (adds in-full) | receipts on time **and** complete ÷ receipts | + `GoodsReceiptLine.quantity_received` vs `PurchaseOrderLine.quantity` | buildable now — the OTD upgrade every leader asks for |
  | Defect / reject rate (% or PPM) | rejected ÷ (received + rejected) | `GoodsReceiptLine.quantity_rejected` | already proven |
  | NCR / discrepancy rate | discrepancies ÷ receipts in period | `procurement.ReceiptDiscrepancy` (6.12) | buildable now |
  | Return-to-vendor rate | RTVs ÷ receipts | `procurement.ReturnToVendor` (6.12) | buildable now |
  | Invoice accuracy % | invoices with no non-auto-accept variance ÷ invoices | `procurement.InvoiceMatchVariance.outcome`, `SupplierInvoice.match_status` (6.13) | buildable now — Ivalua's "invoice match accuracy" |
  | Dispute rate / mean days to resolve | disputes ÷ invoices; `resolved_at − raised_at` | `procurement.InvoiceDispute` (6.13) | buildable now |
  | Promise adherence | promised_date vs need_by_date on instalments | `procurement.DeliverySchedule` (6.11, already has a `days` delta property) | buildable now |
  | Backorder rate | backorders ÷ order lines | `procurement.Backorder` (6.11) | buildable now |
  | PO change rate | change orders ÷ POs | `procurement.PurchaseOrderChange` (6.10) | buildable now |
  | Price competitiveness | best quote ÷ this quote across shared RFQs | `scm.RFQQuote` | already proven |
  | Quote turnaround days | `received_date − RFQ.issue_date` | `scm.RFQQuote`, `scm.RFQ` | already proven |
  | Suspension incidents | active suspensions in period | `procurement.VendorSuspension` (6.4) | buildable now |

  · priority: table-stakes · spine: closed `DERIVED_METRIC_CHOICES` on `SupplierKpi`, resolvers in a
  procurement `services.py`/`analytics.py`-style module · buildable now
- **Not computable today → must be `survey` or `manual` this pass:** cost-variance-vs-should-cost and
  expedite-cost-%-of-spend (no should-cost baseline table anywhere; 6.15's `BudgetMapping`/`CostForecast` are
  budget-side, not should-cost), innovation throughput (no ideas pipeline), lead-time adherence against a
  contracted lead time (no lead-time column on the supplier), supplier financial/credit score (external).
  Audit score, CAPA closure-on-time, ESG score and certification currency have **plausible** sources
  (`scm.QualityAudit`, `scm.CapaAction`, `scm.SustainabilityAssessment`, `scm.TradeLicense`) but their field
  shapes were not verified in this pass — **do not** wire them as derived metrics without a fresh grep;
  ship them as `manual`/`survey` KPIs now. · **flagged: not buildable as derived this pass**
- **Continuous refresh instead of quarterly compilation** — HICX's central pitch; Ivalua real-time dashboards ·
  seen in: HICX, Ivalua, GEP · priority: differentiator · spine: no model change — a `generate` POST action
  that is safe to press repeatedly (idempotent lines) · buildable now (a scheduled job is deferred)
- **Two-way visibility: the supplier sees its own score** — seen in: HICX, Ivalua, SupplyHive, Kodiak ·
  priority: common · spine: would reuse the verified `procurement.VendorPortalAccess` · **deferred**
  (portal UI is 6.4's surface)

### Bullet 3 — 360-Degree Feedback Collection

- **Multi-stakeholder internal survey feeding the scorecard** — Ariba surveys push graded answers straight
  into KPIs; LeanLinking collects soft metrics from procurement/quality/operations and aggregates them into
  the scorecard; Coupa scores partly from "end-user ratings"; Zycus captures inputs "both automatically and
  through stakeholder surveys" · seen in: SAP Ariba, LeanLinking, Coupa, Zycus, GEP, SupplyHive ·
  priority: table-stakes · spine: **new table `SupplierFeedback`**, one row = one respondent's rating of one
  supplier for one period, optionally **against one `SupplierKpi`** (so a `source='survey'` KPI's scorecard
  value is the aggregate of its feedback rows) · buildable now
- **Respondent function / department** — Kodiak's RACI names Category Manager, SQE/Quality, Logistics,
  Finance, Operations, Engineering as the responsible/consulted set · seen in: Kodiak, LeanLinking,
  SupplyHive · priority: common · spine: `SupplierFeedback.respondent_function` choices (and optionally
  `core.OrgUnit`, verified to exist) · buildable now
- **Qualitative 5-point scale with labelled anchors** — Ariba's qualitative answers are 'Excellent' /
  'Meets Expectations' / 'Poor' · seen in: SAP Ariba, Ivalua, GEP · priority: table-stakes ·
  spine: `SupplierFeedback.rating` 1–5 with labelled `RATING_CHOICES`, mapped to 0/25/50/75/100 when it feeds
  a 0-100 KPI score · buildable now
- **Per-response importance/weight** — Ariba weights sections 1–100 and gives each question an *Importance*
  of 0–10 · seen in: SAP Ariba · priority: differentiator · spine: `SupplierFeedback.importance` 0–10,
  used to weight the aggregate (a category manager's rating can count more than a casual requester's) ·
  buildable now
- **Request → submit lifecycle with due dates and completion tracking** — GEP explicitly sells "issuing and
  tracking scorecards for completion"; Ariba tracks participants · seen in: GEP, SAP Ariba, Ivalua,
  LeanLinking (automated survey distribution) · priority: table-stakes ·
  spine: `SupplierFeedback.status` requested/submitted/declined/expired + `due_date`, `requested_by`,
  `submitted_at` · buildable now (the **email distribution is integration/later**)
- **Supplier self-review on the same criteria + perception gap** — SupplyHive's Hive360 prompts the supplier
  to self-score on the buyer's own KPIs and renders the delta; Jaggaer/Ariba collect a "voice of supplier"
  section · seen in: SupplyHive, SAP Ariba, JAGGAER · priority: differentiator ·
  spine: `SupplierFeedback.respondent_kind` ∈ `internal` / `supplier_self` — **one CharField buys the whole
  perception-gap board** · buildable now (data model); supplier-facing capture UI deferred
- **Free-text strengths/concerns commentary** — feeds Kodiak's commentary and SupplyHive's theme analysis ·
  seen in: SupplyHive, Kodiak, Ivalua · priority: common · spine: `SupplierFeedback.comment` · buildable now
- **NLP theme + sentiment extraction over comments; AI-generated action plans** — SupplyHive's NLP analysis,
  Ivalua's IVA auto-generating commentary and structured improvement plans · seen in: SupplyHive, Ivalua,
  ComplianceQuest · priority: differentiator · spine: no new table (reads `SupplierFeedback.comment`) ·
  **AI/later**
- **One response per stakeholder per KPI per period** — prevents one loud voice scoring twice ·
  priority: common · spine: enforce in `clean()`, **not** blindly in `unique_together` — `scorecard` and
  `kpi` are nullable and NULLs compare distinct, so a naive constraint would let duplicates through (the same
  trap `KpiSnapshot.dimension_key` documents: store `""`, never `NULL`, when a blank must be unique) ·
  buildable now

### Bullet 4 — Performance Improvement Plans (PIP)

- **A structured corrective/development plan triggered by a failing scorecard** — Jaggaer "automatically
  activates development and corrective action plans when a supplier's performance dips"; Ivalua's threshold
  rules auto-create a corrective action workflow (invoice accuracy < 95 % → corrective action; composite
  drops 1 point QoQ → QBR) · seen in: JAGGAER, Ivalua, GEP, HICX, Kodiak, MasterControl (SCAR),
  ComplianceQuest, EcoVadis · priority: table-stakes · spine: **new table `SupplierImprovementPlan`**,
  FK to the triggering `scm.SupplierScorecard` and optionally the failing `SupplierKpi` · buildable now
  (the *automatic* trigger is a later rule engine; the plan and a "create PIP from this scorecard" action are
  now)
- **Finding → root cause → action → owner → due date → status → evidence → verification date** — Kodiak's
  CAPA register columns, verbatim in structure · seen in: Kodiak, MasterControl, ComplianceQuest, HICX
  ("owner assignment and escalation tracking") · priority: table-stakes ·
  spine: `SupplierImprovementPlan` fields (`finding`, `root_cause`, `corrective_actions`, `internal_owner`,
  `supplier_owner_name`, `target_close_date`, `status`, `verified_at`/`verified_by`, `evidence`) ·
  buildable now at **plan** grain; the **multi-row action register is deferred** (see Deferred)
- **Plan lifecycle with an explicit outcome** — the verified in-repo precedent
  `hrm.PerformanceImprovementPlan` uses draft → pending approval → active → closed with outcome
  successful/extended/failed/terminated and an `extended_end_date`; EcoVadis CAPs carry a 12-month validity ·
  seen in: EcoVadis, Ivalua, Kodiak + in-repo precedent · priority: table-stakes ·
  spine: `STATUS_CHOICES` / `OUTCOME_CHOICES` on `SupplierImprovementPlan` · buildable now
- **Supplier acknowledgment of the plan** — HRM's PIP has `acknowledged_at`/`acknowledged_by`; Ivalua and
  Kodiak run plans collaboratively with the supplier · seen in: Ivalua, GEP, Kodiak + in-repo precedent ·
  priority: common · spine: `acknowledged_at` + `acknowledged_by` (editable=False system stamps) ·
  buildable now
- **Escalation to suspension / de-sourcing when the plan fails** — LeanLinking: threshold misses for 3+
  consecutive quarters trigger contract penalties and dual-sourcing; Kodiak links scorecards to
  share-of-business decisions; MasterControl updates the approved vendor list · seen in: LeanLinking, Kodiak,
  MasterControl, Ivalua · priority: common · spine: **reuses the verified
  `procurement.VendorSuspension`** (its `REASON_CHOICES` already carries `quality` and `delivery`) via a
  nullable `escalated_suspension` FK on the plan — closes the loop without a second blocking mechanism ·
  buildable now
- **Check-ins / progress reviews during the plan** — in-repo precedent `hrm.Pipcheckin`; Kodiak's monthly ops
  review tracks corrective-action status · seen in: Kodiak, Ivalua + in-repo precedent · priority: common ·
  spine: would be a child table · **deferred** (plan-level `next_review_date` covers this pass)
- **Bonus/penalty schemes tied to assessment results** — seen in: JAGGAER · priority: differentiator ·
  spine: would need a rebate/penalty hook into 6.8 contracts + accounting · **deferred**
- **8D / PPAP / APQP structured quality methodologies** — seen in: Ivalua, MasterControl · priority:
  differentiator · spine: a methodology CharField at most · **deferred** (regulated-manufacturing niche)

### Bullet 5 — Benchmarking & Trending

> **Recommendation: this bullet ships as computed boards/views, NOT as a table.** Every figure it needs is
> already stored: `SupplierKpiScore` rows are frozen per KPI per scorecard per period, and
> `scm.SupplierScorecard` already carries `party` + `period_end` + `overall_score` + `grade`. Unlike SCM
> 4.11's `KpiSnapshot` — which had to be frozen because its inputs (rolling `average_cost`, back-datable
> `StockMove`) drift under it — a 6.16 trend is pure arithmetic over numbers that are *already* frozen at
> generation (`measured_value`, `score`, `weight_applied`, `target_at_time`). There is nothing left to
> freeze, so a snapshot table here would be a second copy of the same numbers.

- **Period-over-period trend per supplier and per KPI** — Kodiak ships monthly + trailing-12-month trends;
  SupplyHive a trend view; LeanLinking a 12-month history for contract decisions · seen in: Kodiak,
  SupplyHive, LeanLinking, GEP, Ivalua · priority: table-stakes · spine: **no new table** — GROUP BY over
  `SupplierKpiScore` indexed on `(tenant, kpi, scorecard)` joined to the scorecard's `period_end` ·
  buildable now
- **Peer benchmarking across the supply base** — "performance comparable across the entire supply base"
  (LeanLinking); Ariba's "powerful comparative view to benchmark multiple suppliers"; GEP trends by category,
  region and business unit; Ivalua filters by tier/category/geography · seen in: SAP Ariba, LeanLinking, GEP,
  Ivalua, SupplyHive · priority: table-stakes · spine: **no new table** — rank/percentile of a supplier's
  composite against the tenant's own cohort for the same period, cohort = `scm.SupplierProfile.tier` or
  `category` · buildable now
- **Segmentation quadrant / matrix** — SupplyHive's four segments (Strategic · Hidden High Performers ·
  Development · Underperforming) driving differentiated engagement; Coupa segments partners from performance
  scorecards · seen in: SupplyHive, Coupa, Kodiak, HICX · priority: common · spine: **no new table** —
  a board plotting composite score against **verified** `scm.SupplierRiskAssessment.risk_index` or 6.14 spend
  (`procurement.SpendReport`) · buildable now
- **Deviation alerts when a KPI crosses a threshold** — HICX and Ivalua both fire alerts on band crossings;
  GEP alerts when performance dips · seen in: HICX, Ivalua, GEP, JAGGAER · priority: common ·
  spine: **reuses the verified `procurement.ProcurementAlert`** (6.1) rather than a new alert table ·
  buildable now (raise on generate) — a background detector is deferred
- **Comparison against external industry averages** — the second half of the NavERP bullet · seen in:
  EcoVadis (industry-benchmarked sustainability ratings), Prewave/Craft (external risk signals), Coupa
  (community-pooled feedback) · priority: differentiator ·
  spine: needs a third-party data feed — **NOT buildable against the as-built spine.** What ships instead is
  *internal* benchmarking (peer/cohort/percentile); an `industry_benchmark_value` column on `SupplierKpi`
  could hold a hand-entered external reference, and is the cheapest honest stand-in ·
  **integration/later (flagged)**
- **Share-of-business / allocation decisions driven by the scorecard** — Kodiak links scores to allocation at
  QBRs; Ivalua flags top performers for partnership expansion · seen in: Kodiak, Ivalua, SupplyHive ·
  priority: differentiator · spine: re-tiering is `scm.SupplierProfile.tier` — **belongs to 6.4**, park it

### Beyond the bullets (found in the market, not in NavERP's five bullets)

- **Scorecards embedded in the supplier portal with per-KPI comment threads** (Ivalua, HICX, SupplyHive) —
  data model is compatible (`VendorPortalAccess` verified), UI deferred.
- **Risk and performance in one shared supplier record** (Coupa, Kodiak, HICX) — NavERP already has this
  shape (`scm.SupplierRiskAssessment` + `scm.SupplierScorecard` both hang off `core.Party`); 6.16 should
  *render* both on one board, and the risk half belongs to **6.17**.
- **Two-sided review (buyer reviews supplier AND supplier reviews buyer)** (SupplyHive) — captured cheaply by
  `respondent_kind`; a buyer-scoring-buyer surface is out of scope.
- **Evidence pack export for audits** (Kodiak, HICX) — `core.Document` is verified and can be attached to a
  PIP; a packaged export is deferred.

---

## Recommended build scope (this pass — 4 models, 4 entity files)

Package: `apps/procurement/models/SupplierPerformanceEvaluation/` (+ matching `forms` / `views` / `urls`).
Templates: `templates/procurement/performance/<entity>/{list,detail,form}.html` plus standalone boards at
`templates/procurement/performance/`.

### 1. `SupplierKpi` — `SupplierPerformanceEvaluation/SupplierKpis.py` · `TenantNumbered` · **[SKP-]**
**Serves bullet 1 (KPI Definition & Setup)** — and is the single change that unlocks bullets 2 and 3.

- **Fields/choices justified by the research:** `code` (unique per tenant — Ariba master-KPI identifiers),
  `name`, `description`; `category` ∈ delivery/quality/cost/service/compliance/esg/innovation/risk (Ivalua 5
  + Kodiak ESG & innovation + Zycus balanced scorecard); `unit` ∈ pct/days/count/ppm/money/score/ratio
  (Kodiak formulas); `direction` ∈ higher_is_better/lower_is_better (Kodiak's per-KPI direction);
  `source` ∈ derived/survey/manual (**SAP Ariba's three KPI data-source types**; HICX & LeanLinking's
  transactional-plus-survey blend); `derived_metric` — **closed** choices, blank unless `source='derived'`,
  populated only from the verified-computable table above (`otd`, `otif`, `defect_rate`, `ncr_rate`,
  `rtv_rate`, `invoice_accuracy`, `dispute_rate`, `dispute_days`, `promise_adherence`, `backorder_rate`,
  `po_change_rate`, `price_competitiveness`, `quote_turnaround`, `suspension_incidents`);
  `weight` 1–100 (**the field that replaces `SupplierScorecard.WEIGHTS`** — Ivalua/LeanLinking weight
  profiles, Ariba per-scorecard overrides); `target_value` / `warning_threshold` / `critical_threshold`
  (Ivalua green-yellow-red, Kodiak OTIF ≥ 98 % / PPM ≤ 250 / audit ≥ 90 %) with band ordering validated
  against `direction` in `clean()`; `scoring_method` ∈ band/linear/direct (Ariba pre- vs post-grading);
  `maps_to_dimension` ∈ delivery/quality/price/responsiveness/'' (NavERP bridge to the existing scorecard
  columns); `applies_to` ∈ all/tier + `applies_to_tier` (Jaggaer per-category rating models, State of Flux
  tier-based setup); `review_frequency` ∈ monthly/quarterly/semiannual/annual (Ivalua/Kodiak cadence);
  `industry_benchmark_value` (hand-entered external reference — the only honest stand-in for "industry
  averages"); `owner`, `display_order`, `is_active`, `notes`.
- **FKs (all verified):** `tenant` → `core.Tenant`; `owner` → `settings.AUTH_USER_MODEL`.
- **Validation:** band ordering by direction (port of `scm.KpiTarget.clean()`); `derived_metric` required iff
  `source='derived'` and forbidden otherwise (the "conjunction that can never be true" rule);
  `applies_to_tier` required iff `applies_to='tier'`.

### 2. `SupplierKpiScore` — `SupplierPerformanceEvaluation/ScorecardKpiScores.py` · `TenantOwned` · no prefix
**Serves bullet 2 (Scorecard Generation)** — the L36 "extend the scm table by FK" move.
Child fact row, so `TenantOwned` not `TenantNumbered` (the `KpiSnapshot` / `InvoiceMatchVariance` precedent —
a per-tenant `SKS-00001` nobody would ever quote).

- **Fields:** `measured_value` Decimal(16,4) null; `score` Decimal(5,2) 0–100 null with
  `MinValueValidator(0)/MaxValueValidator(100)` (matches every 0-100 field in the codebase and stops a
  hand-entered value inflating the composite or overflowing a `width:<score>%` bar); `weight_applied`
  PositiveInteger (frozen — Ariba allows per-scorecard weight overrides, so the weight must be stored with
  the measurement); `band` ∈ ok/warning/critical/unknown + colour-named `BAND_CSS`
  (`badge-green`/`badge-amber`/`badge-red`/`badge-muted` — L33); `target_at_time`, `direction_at_time`,
  `source_at_time`, `kpi_name`/`kpi_category` denormalised (a later retune or rename must not rewrite
  history — the `KpiSnapshot.target_value_at_time` / `dimension_label` precedent); `breakdown` JSONField
  (structured `signal_summary`); `respondent_count` (how many 360 responses were aggregated for a
  survey-sourced KPI); `comment` (Kodiak commentary); `computed_at` (`default=timezone.now`, **not**
  `auto_now_add` — a re-run must re-stamp freshness), `computed_by` editable=False.
- **FKs (all verified):** `scorecard` → **`scm.SupplierScorecard`** (CASCADE,
  `related_name="procurement_kpi_scores"`); `kpi` → `procurement.SupplierKpi` (**PROTECT** — deleting a KPI
  must not silently delete measured history; retire via `is_active=False`); `tenant` → `core.Tenant`.
- **Constraint:** `unique_together (tenant, scorecard, kpi)` — a re-run **updates**, so the generate action is
  safe to press twice.
- **Forms/views:** no create form (system-written by the generate action); **edit form limited to
  `measured_value` + `comment` and only for `source_at_time='manual'`** (Ariba's manual KPI type);
  list + detail + POST-only delete.
- **Actions:** `scorecard_generate` (POST on a `scm.SupplierScorecard`) → resolve the applicable KPI set from
  the supplier's `scm.SupplierProfile.tier`, compute derived metrics, aggregate survey KPIs from
  `SupplierFeedback`, write/refresh one line per KPI, band each, and fill the four
  `scm.SupplierScorecard` dimension columns for KPIs that declare a `maps_to_dimension` before calling the
  scorecard's own `recompute_overall()`.
  > **Flag for the spec phase:** writing those four columns means also setting
  > `scm.SupplierScorecard.manual_override = True`, which **permanently disables** SCM's
  > `recompute_from_signals()` for that scorecard. Decide explicitly: either (a) set it and document that
  > 6.16 has taken over that scorecard, or (b) never touch the scm columns and show the 6.16 composite only
  > on procurement's own board. **Recommendation: (a), and only on the explicit generate action**, so the
  > two engines never fight over the same row. Refuse to generate onto a `published`/`archived` scorecard.

### 3. `SupplierFeedback` — `SupplierPerformanceEvaluation/SupplierFeedback.py` · `TenantNumbered` · **[SFB-]**
**Serves bullet 3 (360-Degree Feedback Collection)**, and feeds bullet 2 via `source='survey'` KPIs.

- **Fields:** `period_start` / `period_end`; `respondent_kind` ∈ internal/supplier_self (**SupplyHive Hive360
  perception gap** — one CharField); `respondent_function` ∈ procurement/quality/operations/finance/
  engineering/logistics/other (Kodiak RACI, LeanLinking's three functions); `rating` 1–5 with labelled
  choices (Ariba's Excellent/Meets Expectations/Poor) + a `score_value()` mapping to 0/25/50/75/100;
  `importance` 0–10 default 5 (**Ariba's per-question Importance**, weights the aggregate);
  `status` ∈ requested/submitted/declined/expired (GEP completion tracking); `due_date`, `requested_at`,
  `submitted_at` (editable=False), `comment`.
- **FKs (all verified):** `supplier` → `core.Party` (PROTECT); `scorecard` → `scm.SupplierScorecard`
  (SET_NULL, null — so ad-hoc feedback exists without a period document); `kpi` → `procurement.SupplierKpi`
  (SET_NULL, null — set means this response feeds that survey KPI, blank means general commentary);
  `respondent` and `requested_by` → `settings.AUTH_USER_MODEL`; `tenant` → `core.Tenant`.
- **Validation:** one response per `(supplier, scorecard, kpi, respondent)` enforced in `clean()`, **not** in
  `unique_together` — `scorecard`/`kpi` are nullable and NULLs compare distinct (the `KpiSnapshot`
  blank-vs-NULL trap); `kpi`, when set, must have `source='survey'`; every FK must be same-tenant
  (`_id` guards, never bare `getattr` — the `VendorSuspension.clean()` precedent, where the two-arg form
  raised `RelatedObjectDoesNotExist` and 500'd a live add page).

### 4. `SupplierImprovementPlan` — `SupplierPerformanceEvaluation/SupplierImprovementPlans.py` · `TenantNumbered` · **[SIP-]**
**Serves bullet 4 (Performance Improvement Plans)**. Modelled on the verified in-repo
`hrm.PerformanceImprovementPlan` plus Kodiak's CAPA-register columns.

- **Fields:** `title`; `finding` (what was observed), `root_cause`, `corrective_actions`,
  `support_provided`, `success_criteria` (Kodiak: finding · root cause · action; HRM PIP: performance_issue ·
  expected_standards · improvement_goals · support_provided · measurement_criteria);
  `severity` ∈ minor/major/critical; `start_date`, `target_close_date`, `next_review_date`,
  `extended_close_date`, `actual_close_date`; `status` ∈ draft/active/monitoring/closed/cancelled;
  `outcome` ∈ successful/extended/failed/escalated (HRM's OUTCOME_CHOICES shape);
  `supplier_owner_name` + `supplier_owner_email` (the supplier-side action owner — Kodiak/Ivalua run plans
  with the supplier); `acknowledged_at`/`acknowledged_by`, `verified_at`/`verified_by`,
  `closure_note` (Kodiak's verification date; EcoVadis CAP closure).
- **FKs (all verified):** `supplier` → `core.Party` (PROTECT); `scorecard` → `scm.SupplierScorecard`
  (SET_NULL, null — the triggering evidence, Jaggaer/Ivalua "performance dips → plan"); `kpi` →
  `procurement.SupplierKpi` (SET_NULL, null — the failing KPI); `owner` (internal) → `settings.AUTH_USER_MODEL`;
  `escalated_suspension` → `procurement.VendorSuspension` (SET_NULL, null — **closes the loop to the existing
  block register instead of inventing a second blocking mechanism**); `evidence` → `core.Document`
  (SET_NULL, null) or a `FileField` following the `ReceiptDiscrepancy.evidence` precedent;
  `tenant` → `core.Tenant`.

### Bullet 5 — no model. Two computed boards + one dashboard block
- **`performance_trend` board** — one supplier: composite and per-KPI series across periods, with
  period-over-period deltas and flag-vs-target (Kodiak monthly + trailing-12).
- **`performance_benchmark` board** — one period: every supplier ranked by composite, filterable by tier and
  category, with cohort average and percentile, plus a performance × risk quadrant reading the verified
  `scm.SupplierRiskAssessment.risk_index` (SupplyHive segments, Ivalua tier/category filters, Coupa
  segmentation).
- **Perception-gap panel** — internal average vs `respondent_kind='supplier_self'` average per KPI.
- Alerts on band crossings **reuse `procurement.ProcurementAlert`** (6.1); no new alert table.

**Model count: 4 (`SupplierKpi`, `SupplierKpiScore`, `SupplierFeedback`, `SupplierImprovementPlan`).**
No second scorecard, no second vendor table, no second ledger.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Supplier onboarding, qualification, due diligence, tier/segment maintenance, and the
  suspension/blacklist **workflow** → **6.4** (`scm.SupplierProfile`, `procurement.VendorSuspension` — 6.16
  only *links* to them)
- Weighted **bid** evaluation matrices and RFx question scoring/weighting → **6.5 / 6.6** (already built;
  6.16 must not rebuild a scoring engine for sourcing events)
- GRN tolerances, quality inspection checklists, quarantine, NCR and RTV **mechanics** → **6.12** (6.16
  only *reads* `ReceiptDiscrepancy` / `ReturnToVendor` as KPI signals)
- Three-way match, match variances, dispute **workflow** → **6.13** (6.16 only *reads* them)
- Spend by supplier/category, maverick spend, savings → **6.14** (a benchmark board may *read*
  `SpendReport`, not extend it)
- Contract SLAs, obligations, penalties, renewals tied to performance → **6.8**
- Supplier financial/credit risk monitoring, restricted-party screening, fraud rules, policy
  acknowledgment → **6.17** (and `scm.SupplierRiskAssessment` already exists — read it, don't clone it)
- Evidence-pack repository, version control, full-text search over performance documents → **6.19**
- Network-wide supply-chain KPI targets, snapshots, alerts and the control tower → **SCM 4.11**
  (`KpiTarget` / `KpiSnapshot` / `SupplyChainAlert` — a different subject and a closed metric registry)
- Share-of-business re-allocation and re-tiering after a review → **6.4** (writes
  `scm.SupplierProfile.tier`)
- Supplier-facing portal pages (score visibility, self-review capture, comment threads) → **6.4**
  (`VendorPortalAccess`)

---

## Deferred (later passes / integrations)

- **`SupplierImprovementAction` child** — the multi-row CAPA register (per-action owner, due date, status,
  evidence link, verification date). Kodiak/MasterControl/ComplianceQuest all have it and it is the **first
  thing the next pass should add**; this pass ships plan-grain fields only, so design
  `SupplierImprovementPlan` to accept the child without reshaping it (do not cram a fake action list into a
  TextField).
- **Named scorecard template / KPI set model** (Ariba's Master document) — this pass selects the KPI set via
  `applies_to_tier` + `is_active`, which covers the common case; a named, versioned template is the natural
  second pass.
- **PIP check-in child** (the `hrm.Pipcheckin` analogue) — `next_review_date` covers this pass.
- **Automated cadence scheduling** — `review_frequency` is stored now; the job that auto-creates the next
  period's scorecard needs a scheduler (no cron/Celery in this repo yet).
- **Survey distribution, reminders and escalation e-mails** — integration/later; the request lifecycle
  (`status`, `due_date`) is modelled now so nothing has to be reshaped when mail lands.
- **Supplier-facing self-review UI and score sharing** — needs the 6.4 portal surface; the data model
  (`respondent_kind='supplier_self'`) is ready.
- **Rule-engine auto-triggering of PIPs and alerts** (Jaggaer/Ivalua thresholds → workflows) — this pass
  ships a "create PIP from this scorecard" action and band-crossing alerts raised during generate; a
  standing detector is later.
- **External industry benchmarks** (EcoVadis, Prewave, D&B, Coupa's pooled community feedback) —
  **not buildable against the as-built spine**; `industry_benchmark_value` is a hand-entered stand-in.
- **NLP sentiment/theme extraction and AI-drafted improvement plans** (SupplyHive, Ivalua IVA) — AI/later.
- **Bonus/penalty schemes tied to scores** (Jaggaer) — needs a contract/AP hook; 6.8 + accounting.
- **8D / PPAP / APQP methodology templates** (Ivalua, MasterControl) — regulated-manufacturing niche.
- **Derived audit score, CAPA closure-on-time, certification currency and ESG KPIs** — plausible sources
  exist (`scm.QualityAudit`, `scm.CapaAction`, `scm.TradeLicense`, `scm.SustainabilityAssessment` all
  verified to exist as classes) but **their field shapes were not verified this pass**; ship them as
  `manual`/`survey` KPIs and promote them to `derived` only after a fresh grep (L28).
- **Cost-variance-vs-should-cost and expedite-cost KPIs** — no should-cost baseline exists anywhere in the
  repo; `manual` only.
- **Supplier innovation pipeline** (Kodiak's innovation throughput funnel) — no ideas table; `manual` only.
