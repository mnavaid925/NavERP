# Research — Sub-module 6.17: Risk & Compliance Management (Module 6 — Procurement Management System, `procurement`)

> Phase 1 output for `/next-module`. Domain surveyed: **third-party / supplier risk + procurement compliance**
> (restricted-party screening, supplier financial-risk monitoring, procurement fraud analytics, policy
> attestation, tamper-evident audit logging) — **not** generic GRC and **not** "best procurement software".

---

## 0. Repo state checked first

* **`LIVE_LINKS` built so far in module 6** (`apps/core/navigation.py`, read at run time):
  `6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 6.14, 6.15`.
  **No `6.16` and no `6.17` key** — 6.16 Supplier Performance & Evaluation is being built by a concurrent
  session (L43: never full-rewrite `navigation.py`, add the one `"6.17"` key surgically).
* **Sibling research files consulted:** `research-procurement-6.14.md` and `research-scm-4.12.md` both
  **explicitly deferred this sub-module's content to 6.17** — that deferral list is the starting backlog:
  * `research-procurement-6.14.md:576-578` — *"Fraud-pattern detection, restricted-party screening,
    conflict-of-interest, tamper-proof audit logging → 6.17 Risk & Compliance Management. Only `split_purchase`
    (approval-threshold avoidance) stays in 6.14."*
  * `research-scm-4.12.md:398-403, 644-646` — screening **outcomes** are modellable against a `core.Party`,
    but the list content is a licensed/managed data feed: *"Model the outcome later; never ship a fake list."*
* Templates in this app are `templates/procurement/<submodulelower>/<entity>/{list,detail,form}.html`
  (`spendanalytics/`, `budgetcost/`, `invoicevouchermanagement/`…), so 6.17 → **`templates/procurement/riskcompliance/`**.
* Models package convention (6.13 `InvoiceVoucherManagement/`, 6.15 `BudgetCostManagement/`) →
  **`apps/procurement/models/RiskComplianceManagement/`** (keep "Management"; the four layers mirror it).

---

## 1. Scope statement — the five bullets restated as what a user actually does

`NavERP.md:1108-1113`:

| # | Bullet | What a user does on the page |
|---|---|---|
| 1 | **Regulatory Compliance Checks** — automated screening against restricted party lists (OFAC, SAM) | Runs (or records) a screening of a supplier against a named government list at a defined checkpoint, works the resulting potential matches one by one, and **records a documented disposition** for each — false positive or true match — so an auditor can see both the check and its resolution. |
| 2 | **Supplier Financial Risk Monitoring** — integration with third-party tools to monitor supplier credit scores | Captures dated credit/financial-health observations per supplier (D&B SER, PAYDEX, RapidRatings FHR, an internal band), sees the **trend** and the **staleness**, and gets an alert when a score deteriorates through a threshold. |
| 3 | **Audit Trail & Logging** — tamper-proof logs of every action for audit | Reads the procurement action log filtered by user/object/date, and **verifies** that the retained range has not been altered since it was sealed. |
| 4 | **Fraud Detection Rules** — algorithms to flag suspicious purchasing patterns or vendor conflicts of interest | Runs the detector over a date window, triages the alerts it raises (vendor↔employee overlap, self-approval, back-dated PO, duplicate vendor…), and dispositions each as substantiated / unsubstantiated / referred. |
| 5 | **Policy Management & Acknowledgment** — repository for procurement policies + tracking of user sign-offs | Publishes a versioned procurement policy to a target audience of users and watches the attestation rate; a buyer opens their pending policies and signs off. |

**Hard boundary for this pass.** 6.16 (KPIs, scorecards, 360 feedback, PIP, benchmarking) is a *different*
session's build; 6.4 Vendor Management (portal access, suspension register, vendor invoice submission) is
already built. Nothing scored, ranked or benchmarked about supplier **performance** belongs here.

---

## 2. Product survey (10 products/sources — object model, status vocabulary, what to steal)

### 2.1 Descartes Visual Compliance / Denied Party Screening — *the reference implementation for bullet 1*
Object model: four screening **modes** (online single lookup, **batch** across the whole master, **dynamic
re-screening** against list updates, integrated/ERP-embedded) → **match records/alerts** → **Resolution
Manager** (documented match decisions) → **Screening & Audit History** (log every step of due diligence, stay
audit-ready). Screens OFAC SDN, EU consolidated, UN, BIS lists, DDTC debarred, sector exclusion lists;
configurable sensitivity/search tuning; AI-assist to cut false positives.
**Steal:** (a) the screening **run** and the **match** are two different records; (b) the *disposition* on the
match is the artefact auditors want, not the hit; (c) **checkpoint + re-screening cadence** as first-class
fields; (d) sensitivity/threshold is configuration, not a constant.
<https://www.descartes.com/solutions/global-trade-intelligence/denied-party-screening>

### 2.2 US ITA **Consolidated Screening List (CSL)** + SAM.gov Exclusions — *the actual data*
The CSL consolidates **eleven** Commerce/State/Treasury lists (BIS DPL, Entity List, UVL, MEU; State ISN and
AECA/ITAR debarred; OFAC SDN, SSI, FSE, PLC, CAP) into one hourly-updated feed with a **free public API**.
Crucially: **the CSL does NOT include the federal procurement debarment/suspension list on SAM.gov**
(2 CFR Part 180) — a pre-award check screens **both**, because they answer different questions.
**Steal:** the `list_source` vocabulary (name the actual lists), and the honest architecture note — a real API
exists for CSL, so the model must be shaped so a future connector fills the same rows a human fills today.
<https://developer.export.gov/consolidated-screening-list.html> ·
<https://www.opensanctions.org/datasets/us_trade_csl/>

### 2.3 Sanctions-screening mechanics (sanctions.io, Facctum, OFAC FAQ) — *how a hit is judged*
Matching is **fuzzy** (phonetic + character-similarity algorithms) producing a **match score**; OFAC's own
search tool exposes a score field and users pick their own threshold (85% is the commonly cited starting
point) and are expected to **document the rationale for the threshold chosen**. Adjudication asks: is the name
an exact/near match, and does the geography line up? The **OFAC 50% rule** sanctions entities ≥50%-owned by
blocked persons even when unlisted. Disposition depends on the list hit (SDN = hard stop; Entity List = licence
application under presumption of denial; UVL = red flag to resolve). **OFAC requires 10-year retention of all
screening records** (31 CFR §501.601), including *false-positive resolutions* — a cleared false positive with
no record is indistinguishable from a check never performed. Screening happens at minimum at four checkpoints:
onboarding, order acceptance, pre-shipment, pre-payment.
**Steal:** `match_score` 0-100 + a tenant-tunable threshold; mandatory disposition note; the four checkpoints
as choices; a retention/"screened as of" list-version stamp.
<https://www.sanctions.io/blog/what-is-a-denied-party-list-dpl> ·
<https://www.facctum.com/blog/how-to-tune-fuzzy-matching-thresholds> · <https://ofac.treasury.gov/faqs/topic/1636>

### 2.4 SAP Ariba Supplier Risk — *the risk-exposure object model*
**Overall risk exposure is a 1-100 score** (100 = highest risk) combining **category exposures**; four default
risk categories — **Regulatory & Legal** (sanctions, corruption, fraud, cyber), **Environmental & Social**,
**Financial** (bankruptcy, insolvency, credit downgrades), **Operational** (disasters, disruption) — extensible
to 25 custom categories. Each category is built from **contributing factors** (news items, corporate
information, geographic disaster data, compliance records, country profiles, corporate hierarchy, custom
fields); a provider supplies raw data per factor which is compared against **High / Medium / Low thresholds**
to get that factor's intensity. Risk exposure is surfaced *in the buying flow* — guided buying shows it at
supplier selection and sourcing lets you filter invitees by risk level.
**Steal:** score-with-band (raw value + threshold-derived band), the "risk shown where the decision is made"
idea (badge the supplier on the risk pages), and category vocabulary that already matches
`scm.SupplierRiskAssessment`'s four factors.
<https://learning.sap.com/courses/getting-started-with-sap-ariba-supplier-risk/characterizing-risk-exposure>

### 2.5 Coupa Risk Assess / TPRM — *inherent vs residual, continuous monitoring*
Documents every third-party **relationship** (supplier, agent, distributor) with what they do and what
resources they access; an **inherent risk** questionnaire/score computed from sourcing + contracting data;
**residual risk** after mitigations and fourth-party disclosure; **continuous monitoring** replacing annual
reviews by ingesting provider feeds (BitSight, RiskRecon) and **raising alerts for review**.
**Steal:** inherent-vs-residual as an explicit pair; "annual review → continuous monitoring" is the pitch, so
the model needs an observation *stream*, not one assessment row.
<https://www.coupa.com/resources/coupa-for-third-party-risk-management/>

### 2.6 Ivalua Risk Center — *risk consolidated into the SRM workflow*
Consolidates performance evaluations, transactional/spend data, contract information **and** external
third-party data (EcoVadis, Dun & Bradstreet named) into actionable dashboards, with mitigation embedded in
the SRM workflow rather than a separate monitoring chore.
**Steal:** the risk page must join to what the workspace already has (spend, contracts, suspensions), and
**mitigation is an action with an owner**, not a text box.
<https://www.ivalua.com/press-releases/ivalua-launches-enhanced-third-party-risk-management-capabilities/>

### 2.7 JAGGAER supplier risk & intelligence — *the financial-signal catalogue*
A supplier risk scorecard aggregating financial health, operational performance, compliance status and
external signals into a composite rating; continuous monitoring instead of periodic audits; automatic
non-compliance alerts; tracks certifications/licences. Its financial-signal guide is the most concrete list
found and gives **named thresholds**: current ratio <1.0 critical / 1.0-1.5 elevated; interest coverage <2.0x;
**Altman Z < 1.81 = distress zone**; DSO > 60 days; single customer >25% of revenue; credit downgrade below
investment grade; trade-credit-insurance withdrawal; and an escalation ladder — **yellow** (DSO +15 days in a
quarter → enhanced monitoring), **amber** (credit downgrade / auditor change → senior review + contingency),
**red** (going-concern disclosure or covenant breach → immediate escalation).
**Steal:** the metric vocabulary for bullet 2, and the **yellow/amber/red escalation ladder** as the band
choices with a named trigger.
<https://www.jaggaer.com/blog/supplier-financial-risk-signals-procurement-should-monitor-in-2026> ·
<https://www.jaggaer.com/solutions/supplier-intelligence>

### 2.8 RapidRatings FHR + Dun & Bradstreet — *what a "credit score" record actually contains*
**RapidRatings FHR:** 1-100, **higher = healthier**, derived from a Core Health Score (62 ratios, medium-term)
plus 11 short-term default ratios; ~100 ⇒ default probability <0.007%, <20 ⇒ >13.3%; **the 40 line between
Medium and High risk is the workflow lever most customers use**.
**D&B:** **SER (Supplier Evaluation Risk) 1-9**, 9 = highest risk of ceasing operations in 12 months —
buyers commonly impose a *minimum SER* on suppliers; **PAYDEX 1-100** (dollar-weighted payment promptness);
**Failure/Insolvency Score**.
**Steal:** a score record is `(provider, metric, value, scale, observed_on)` — **scales differ and invert**
(FHR 100 = good, SER 9 = bad), so a single "risk score" column without provider+metric is a lie. Also the
"minimum acceptable score" as tenant policy.
<https://www.rapidratings.com/financial-health-intelligence/the-fhr> ·
<https://www.dnb.com/en-us/smb/resources/credit-scores/supplier-evaluation-rating-declined-ser-info.html>

### 2.9 SAP Business Integrity Screening — *the fraud object model*
**Detection strategy** → **detection method** (the business logic that decides whether a transaction is a
potential irregularity) → composite rule scenarios producing an **overall risk score** → **alerts** worked in
alert management with statuses (a new alert is *Not Started*; an open alert is *Not Started* or *In Process*).
Suspicious payments are **parked** for a human to release or block. Heavy emphasis on **calibration and
simulation** to keep the false-positive rate down.
**Steal:** rules are *configuration with thresholds* (not hard-coded), an alert carries a **status a human
moves**, and detection **suggests, never auto-blocks**.
<https://learning.sap.com/courses/exploring-sap-business-integrity-screening/exploring-capabilities-and-processes-of-sap-bis-solution>
· <https://www.sap.com/products/financial-management/fraud-management.html>

### 2.10 DataWalk / SAS procurement-fraud analytics — *the rule catalogue for bullet 4*
Techniques: **rules** for the clear-cut cases, **anomaly detection** for the unusual, **link analysis** for
collusion (relationships via shared static attributes — phone, address, **bank account** — or transactional
ones), and **entity resolution** to spot duplicate vendors across normalised address formats. Named patterns:
suppliers sharing an address/phone/bank account with each other or with employees, **shopping-cart stringing**
and PO modification/threshold gaming, unusual payment amounts, **vendor bank-detail changes**, a library of
predefined employee/contractor fraud indicators. Investigator surface = alerts + a case folder.
**Steal:** the exact rule list (it maps 1:1 onto `core.Party`/`Address`/`ContactMethod` joins) and the
"flag the duplicate vendor, don't merge it" posture.
<https://datawalk.com/procurement-fraud/> ·
<https://www.sas.com/en_us/insights/articles/risk-fraud/prevent-procurement-fraud.html>

### 2.11 NAVEX PolicyTech (+ COI registers) — *the reference for bullet 5*
Policy lifecycle **draft → review → rewrite → approve → publish**, then automatic distribution to the
specified audience; **automatic version control** so everyone sees the current version; employees read and
**attest** in-system; **automated reminder emails until attestation is received**; **campaigns** bundle
related documents to a custom group; attestation records for *current and previous versions* are retained for
audit-ready reporting. Adjacent COI practice (GAN Integrity, SAI360, ConvergePoint, public-sector registers):
a **conflict-of-interest register** covering employees, contractors, committee members and **evaluators**,
capturing financial holdings, outside roles, close relationships, gifts, prior employment and supplier
interests, with a reviewer decision and mitigating controls; selection-committee members must sign a COI
statement **before** participating in an evaluation.
**Steal:** version + supersession chain, per-user attestation rows raised at publish, attestation **rate** as
the headline metric, retention of attestations against the *old* version, and re-attestation on a new version.
<https://www.navex.com/en-us/platform/policy-procedure-management/> ·
<https://www.processunity.com/third-party-risk-management/inherent-risk/> (risk tiering driving review cadence)
· <https://www.ganintegrity.com/products/conflicts-of-interest/>

### 2.12 Supporting: Oracle Fusion Supplier Qualification & tamper-evident logging patterns
**Oracle** models supplier compliance as **qualification areas → questionnaire → an outcome with an effective
period and an expiration**, auto-initiating renewal/re-qualification as expiry approaches, plus "extend the end
date / assign a new outcome" shortcuts. **Steal:** every compliance artefact needs a *valid-until* and a
re-check date — the same shape as re-screening and score staleness.
<https://docs.oracle.com/en/cloud/saas/procurement/24c/oaprc/how-qualifications-and-assessments-are-evaluated.html>

**Tamper-evident logging (the engineering pattern behind bullet 3's "tamper-proof"):** each record's hash is
computed over its own canonical content **plus the previous record's hash** (`h_i = H(h_{i-1} ‖ record_i)`,
SHA-256, public genesis) so altering any record breaks every subsequent link; storage is **append-only** at
the application layer (insert + read, never update/delete) and, where supported, at the DB layer; verification
**replays** a segment and confirms each stored hash re-computes and each `prev_hash` matches the prior row.
<https://appmaster.io/blog/tamper-evident-audit-trails-postgresql> ·
<https://static.usenix.org/event/sec09/tech/full_papers/crosby.pdf>

---

## 3. Deduplicated feature catalogue (this sub-module only)

Priority: **P0** = nearly every leader has it / the bullet is not credible without it · **P1** = most have it ·
**P2** = a standout differentiator or a cheap extra.

### Bullet 1 — Regulatory Compliance Checks (restricted-party screening)

| # | Feature | Seen in | Pri | Spine mapping / effort |
|---|---|---|---|---|
| 1.1 | **Screening run as its own record**: subject party + list source + checkpoint + date + who ran it | Descartes, SAP GTS, e2open, ONESOURCE | **P0** | New `ComplianceScreening`; FK `core.Party` (verified). Small. |
| 1.2 | **Hit/match as a child record with a match score and a mandatory disposition** (false positive / true match / cleared-with-licence), disposition note required | Descartes Resolution Manager, OFAC guidance, sanctions.io | **P0** | New child `ScreeningHit` (tenant-less, `screening.tenant` — the `scm.ComplianceCheck` / `AsnLine` precedent). Medium. |
| 1.3 | **Named list vocabulary** (OFAC SDN/SSI, BIS DPL/Entity/UVL, State ISN/ITAR-debarred, CSL consolidated, **SAM.gov Exclusions**, EU/UN consolidated, internal watchlist) | CSL API, Descartes, sanctions.io | **P0** | CHOICES on the screening; also stamp `list_as_of` (the data date the operator screened against). Trivial. |
| 1.4 | **Checkpoint vocabulary** — onboarding / pre-award / pre-PO / pre-payment / periodic re-screen / ad-hoc | sanctions.io (4 minimum checkpoints), Descartes | **P0** | CHOICES. Trivial. |
| 1.5 | **Screening status a human moves**: `pending_review → cleared | escalated | blocked`, with a guard that a screening **cannot be cleared while an undisposed hit remains** | Descartes, SAP GTS work list, SAP BIS park/release | **P0** | Verb methods + `clean()`. The single most testable rule in the sub-module. Small. |
| 1.6 | **Re-screening cadence** — `next_rescreen_on` + a "due / overdue" board over parties whose last clear screening is stale | Descartes dynamic re-screening, Oracle expiry-driven re-qualification | **P1** | Computed board over the register (the 6.8 renewals-board precedent). Small. |
| 1.7 | **Match score + tenant threshold, with the threshold rationale recorded** | OFAC search tool, Facctum, Descartes sensitivity tuning | **P1** | `match_score` 0-100 on the hit; the threshold as a documented constant/field. Small. |
| 1.8 | **Escalation of a confirmed true match into a supplier block** | Descartes escalation, SAP GTS blocking | **P1** | **Reuse `procurement.VendorSuspension`** (6.4, verified) — its `blocking_for()` is already consulted by `scm.purchaseorder_approve/_send` and the vendor portal. **Never build a second block flag.** Small. |
| 1.9 | **Screening evidence attachment** (the PDF of the search result) | Descartes audit history, GEP certificate capture | **P1** | FK `core.Document` (verified). Trivial. |
| 1.10 | **Batch screening of the whole vendor master in one pass** | Descartes batch mode | **P2** | An operator-triggered POST that mints one screening per active vendor party (bounded, `SCAN_LINE_LIMIT` precedent). Medium. |
| 1.11 | **Live list API call (CSL / SAM.gov)**, hourly list refresh, OFAC 50%-rule ownership analysis, adverse media/PEP | CSL API, Descartes, Dow Jones/LSEG | **P2** | **Integration/later.** See §5.6 — the model must be shaped so a connector fills the same rows. |

### Bullet 2 — Supplier Financial Risk Monitoring

| # | Feature | Seen in | Pri | Spine mapping / effort |
|---|---|---|---|---|
| 2.1 | **Dated score observation per (supplier, provider, metric)** — a time series, not a single "risk score" column | RapidRatings, D&B, Ariba contributing factors, Coupa continuous monitoring | **P0** | New `SupplierRiskSignal`; FK `core.Party`. Scales differ and invert (FHR 100 = good, SER 9 = bad) so provider+metric+scale must be stored. Small. |
| 2.2 | **Provider + metric vocabulary** — D&B SER (1-9), PAYDEX (1-100), Failure Score, RapidRatings FHR (1-100), Altman Z, DSO/DBT days, current ratio, credit rating, EcoVadis/ESG, cyber rating, internal | D&B, RapidRatings, JAGGAER, Coupa (BitSight/RiskRecon), Ivalua (EcoVadis, D&B) | **P0** | CHOICES. Trivial. |
| 2.3 | **Band / escalation ladder** — low / watch(yellow) / elevated(amber) / critical(red) with the trigger named | JAGGAER ladder, Ariba High/Med/Low factor thresholds, RapidRatings' 40 line | **P0** | `band` CHOICES + `STATUS_CSS` (L33: only `badge-green/red/amber/info/muted/slate` exist). Trivial. |
| 2.4 | **Trend vs the previous observation** (improved / stable / deteriorated) derived, not typed | RapidRatings ratings history, JAGGAER trending, Ariba | **P0** | Derived in `save()` from the prior row for the same `(party, provider, metric)`. Small — one indexed query. |
| 2.5 | **Deterioration raises an alert for review** | Coupa ("raising alerts for review"), GEP threshold-breach agents, JAGGAER predictive alerts | **P1** | **Reuse `procurement.ProcurementAlert`** (6.1, verified) idempotently — the `Backorder.raise_alert()` / `run_renewal_alerts()` precedent. No second alert table. Small. |
| 2.6 | **Staleness / refresh-due board** — which suppliers have no fresh score | Coupa (annual → continuous), Oracle expiry-driven renewal, GEP | **P1** | Computed board (`next_refresh_on` + last observation per party). Small. |
| 2.7 | **Minimum acceptable score as a buying policy** ("suppliers must hold SER ≤ 5") | D&B (buyers impose a minimum SER), Ariba risk-filtered sourcing invitations | **P2** | A `threshold_value` on the signal or a small policy constant; surface as a badge, **advisory only** (the `ReceiptTolerancePolicy` posture — it colours pages, it does not block). Small. |
| 2.8 | **Evidence + source reference** (the report the number came from) | Descartes audit history, GEP certificate extraction | **P1** | FK `core.Document` + `source_ref`. Trivial. |
| 2.9 | **Live credit-bureau feed / API subscription, portfolio auto-refresh, private-company financial requests** | D&B, RapidRatings FHR Exchange, Creditsafe, Coface | **P2** | **Integration/later — do not pretend.** Manual/CSV capture with an explicit "captured by, on" stamp is the honest shipped form. |
| 2.10 | **Composite multi-domain exposure score (1-100) across 4 risk categories** | Ariba, JAGGAER composite rating, ProcessUnity scoring | **P2** | **Park — 4.2's `scm.SupplierRiskAssessment` already does exactly this** (4 factors, derived `risk_index` 1.00-5.00 + `risk_level`). 6.17 links to `scm:riskassessment_list`; it must not ship a second composite. |

### Bullet 3 — Audit Trail & Logging (tamper-proof)

| # | Feature | Seen in | Pri | Spine mapping / effort |
|---|---|---|---|---|
| 3.1 | **A procurement-scoped audit register** — who / what / when / before→after, filterable by user, object type, action and date | Every suite; Descartes "Screening & Audit History"; NAVEX audit-ready reporting | **P0** | **No new table** — computed page over `core.AuditLog` (verified: `tenant, user, content_type, object_id, target, action, changes(JSON), at`). Same substrate as `procurement:activity_list` (6.1) and `procurement:receipt_audit` (6.12), but filtered/exportable rather than a feed. Small. |
| 3.2 | **Tamper-EVIDENT sealing** — a periodic hash chain over the retained log range so alteration is detectable | Hash-chain literature; the claim every GRC vendor makes with "immutable/tamper-proof" | **P1** | New `AuditSeal` — the **only** thing that makes the word "tamper-proof" true (see §5.5). `hashlib` only, no dependency, **no `core` migration**. Medium. |
| 3.3 | **Verify-on-demand** — re-run the chain and name the first row that fails | Hash-chain replay verification | **P1** | A read-only verify view on the seal detail. Small once 3.2 exists. |
| 3.4 | **Retention statement** — how long screening/audit records are kept (OFAC: 10 years, 31 CFR §501.601) | OFAC rule, Descartes | **P2** | A stated policy on the page + `retention_note`; no purge job. Trivial. |
| 3.5 | **CSV export of a filtered audit range for an auditor** | All suites | **P1** | Reuse `_csv_safe()` from `apps/procurement/views/DashboardPortal/SelfServiceReports.py` — ⚠️ every exported cell (target, user, JSON changes) is user-authored text; Excel executes a leading `=`/`+`/`-`/`@`. Small. |
| 3.6 | **DB-enforced append-only / WORM storage, SIEM streaming, e-signature-grade 21 CFR Part 11 trails** | Enterprise GRC | **P2** | **Out of scope** — infrastructure, not a Django model. Say so on the page. |

### Bullet 4 — Fraud Detection Rules

| # | Rule / feature | Seen in | Pri | Buildable on verified data? |
|---|---|---|---|---|
| 4.1 | **Vendor↔employee overlap (conflict of interest)** — a vendor Party and an employee Party sharing `tax_id`, an address `line1+city`, or a `ContactMethod.value` | DataWalk link analysis, SAS, COI registers | **P0** | **Yes** — `core.Party.tax_id`, `core.Address.line1/city`, `core.ContactMethod.value`, `core.PartyRole.role in (employee|vendor|supplier)` all verified. This is the bullet's own words ("vendor conflicts of interest"). |
| 4.2 | **Self-approval / segregation-of-duties breach** — the approver on a signature is the requisition's own requester | SAS, IACRC, every SoD control set | **P0** | **Yes** — `procurement.RequisitionApproval.approver` vs `scm.PurchaseRequisition.requester` (both verified). Cheap, exact, zero false positives. |
| 4.3 | **Duplicate/shell vendor** — two vendor Parties sharing a normalised name, `tax_id` or address | DataWalk entity resolution, Coupa vendor fraud | **P0** | **Yes** — but **flag only, never merge**: `research-procurement-6.14.md:586` parks supplier-master dedup with 6.4/`core.Party`. |
| 4.4 | **Back-dated PO** — a purchase order raised *after* the invoice it is supposed to authorise | SAS, IACRC, audit practice | **P1** | **Yes** — `SupplierInvoice.invoice_date` vs `scm.PurchaseOrder.order_date`/`created_at`. **Distinct from 6.14's `po_less_invoice`** (which is "no PO at all"). |
| 4.5 | **Unresolved screening hit still transacting** — a supplier with an open/true-match `ScreeningHit` receiving new POs | SAP GTS blocking work list, Descartes | **P1** | **Yes** once bullet 1 ships — the cross-link that makes 6.17 one sub-module instead of five pages. |
| 4.6 | **New-vendor rush** — a vendor party created within N days already carrying spend over a threshold, or whose only activity is one large invoice | DataWalk indicators, Coupa vendor fraud | **P1** | **Yes** — `core.Party.created_at` + `SupplierInvoice`. |
| 4.7 | **Round-amount / just-under-threshold single document** — a PR/PO priced suspiciously close under an `APPROVAL_TIERS` threshold | DataWalk "threshold gaming", IACRC | **P2** | Yes, but **boundary-sensitive**: 6.14 already ships `split_purchase` (N orders in a window summing above a tier). This is the *single-document* variant; ship only with an explicit code comment naming the boundary, or defer. |
| 4.8 | **Repeated post-award price escalation** — successive `PurchaseOrderChange` rows raising value after approval | DataWalk "PO modifications" | **P2** | Yes — `procurement.PurchaseOrderChange` (6.10, verified). Cheap add-on rule. |
| 4.9 | **Vendor bank-detail change** (the single most-cited AP fraud control) | DataWalk, SAS, Coupa, every AP-fraud guide | — | **NOT BUILDABLE — no data exists.** `accounting.VendorProfile` has no bank fields and `accounting.BankAccount` is the *tenant's own* account (no party FK). Report the gap; do not fake a rule that can never fire. |
| 4.10 | **Duplicate invoice / duplicate payment** | Every AP-fraud product | — | **Already built in 6.13** — `SupplierInvoice.duplicate_of`, `DUPLICATE_WINDOW_DAYS=90`, `match_status="duplicate_suspect"`, `InvoiceMatchVariance` type `duplicate`. 6.17 **cites** those rows on the fraud board; it must not re-detect them. |
| 4.11 | **Rules are configuration with tunable thresholds + an enable switch, and calibration/simulation before go-live** | SAP BIS detection strategies/methods, DataWalk rule library | **P1** | Either a small `FraudRule` config table (the `ReceiptTolerancePolicy` precedent) **or** tunable class constants + a preview-count on the scan form. See §5.3. |
| 4.12 | **Alert with a status a human moves + idempotent re-scan** | SAP BIS (*Not Started* / *In Process*), Ivalua remediation workflow | **P0** | New `FraudAlert` with `dedupe_key` upsert — the `MaverickSpendFinding.scan(tenant, start, end, reasons=None, user=None)` + `(tenant, dedupe_key)` unique precedent, verified in-repo. |
| 4.13 | **Dismiss / false-positive escape hatch** — without it the queue is abandoned inside a month | SAP BIS false-positive focus, Ivalua, Coupa | **P0** | Terminal dispositions on the alert (`unsubstantiated`, plus `substantiated` / `referred`). Trivial. |
| 4.14 | **Detection suggests, never auto-blocks** (SAP BIS *parks* a payment for a human) | SAP BIS, 6.13's "a duplicate is a suspicion, never an auto-rejection" | **P0** | Posture, not a field: no fraud rule writes to the spine. State it in the module docstring. |
| 4.15 | **Link/network analysis charts, ML anomaly scoring, social-network collusion detection** | DataWalk, SAS, Palantir | **P2** | **Deferred** — no graph/ML layer in this repo, and 4.11/6.14 set the precedent that a page must never claim "AI". |

### Bullet 5 — Policy Management & Acknowledgment

| # | Feature | Seen in | Pri | Spine mapping / effort |
|---|---|---|---|---|
| 5.1 | **Versioned policy record with a supersession chain** and a `draft → published → archived` lifecycle | NAVEX (draft/review/rewrite/approve), ConvergePoint, VComply | **P0** | New `ProcurementPolicy`; mirror `hrm.HRPolicy` (verified: `version_number`, `previous_version` self-FK, `status`, `effective_from`, `published_at`, `requires_acknowledgment`). Small — a proven shape. |
| 5.2 | **Attestation row per targeted user, raised in bulk at publish**, `pending → acknowledged` | NAVEX attestation tracking, PolicyTech campaigns | **P0** | New `PolicyAttestation` — mirror `hrm.PolicyAcknowledgment`, but target **`settings.AUTH_USER_MODEL`**, not an employee profile: the bullet says *"tracking of **user** sign-offs"* and procurement's audience is buyers/approvers. Small. |
| 5.3 | **Attestation rate as the headline metric** (annotation-aware, computed) | NAVEX reporting, ConvergePoint | **P0** | Derived property; `hrm.HRPolicy.acknowledgment_rate` is the exact precedent to copy. Trivial. |
| 5.4 | **Re-attestation on a new version; old-version attestations retained** | NAVEX ("current and previous versions") | **P1** | Publishing v2 raises fresh rows; v1's rows are never rewritten. Small — a rule, not a field. |
| 5.5 | **Targeted audience** (whole workspace vs an org unit vs a named list of users) | NAVEX campaigns/custom groups, ProcessUnity tiering-driven cadence | **P1** | `applicable_org_unit` FK `core.OrgUnit` (verified) + explicit target rows. Small. |
| 5.6 | **Policy document repository with the file attached and effective dates** | NAVEX, GEP, all CLM | **P0** | `FileField` (HRM precedent) **or** FK `core.Document`. Prefer `core.Document` for consistency with 6.17's other evidence links; note 6.19 will be the *search/repository* surface. |
| 5.7 | **Due date + reminder chase until signed** | NAVEX automated reminders | **P1** | `due_on` on the attestation + an overdue board; the reminder **email** is integration/later — raise a `ProcurementAlert` instead. Small. |
| 5.8 | **Policy → control linkage** (which requisition rule enforces this policy) | JAGGAER policy control monitoring, Ivalua | **P2** | Free-text `enforced_by` reference (the `corrective_reference` precedent in `scm.ComplianceCheck`). Trivial. |
| 5.9 | **Conflict-of-interest declaration form signed by evaluators before an event** | GAN Integrity, SAI360, public-sector COI registers | **P2** | **Defer** — it is a second attestation *kind* with different fields (interest type, related party, mitigating control). Note it as the natural 6.17 second-pass entity; rule 4.1 detects the undeclared version meanwhile. |
| 5.10 | **Rich in-app policy authoring, e-signature, LMS-style quizzes, multi-language** | NAVEX PolicyTech Enterprise | **P2** | **Out of scope.** Body text + attached document only. |

---

## 4. As-built spine audit (grep evidence — the ERD is intent, the grep is truth)

### 4.1 `apps/core/models/` — all verified present
`grep -rn "^class \w+" apps/core/models/` → `Activity`, `Address`, `AuditLog`, `ContactMethod`, `Document`,
`Employment`, `OrgUnit`, `Party`, `PartyRelationship`, `PartyRole`, `Tenant`.

* **`core.Party`** (`Party.py:5`) — `tenant, kind(person|organization), name, tax_id, created_at`.
  ⇒ suppliers **and** employees are Parties; `tax_id` + `created_at` are the fields rules 4.1/4.3/4.6 need.
* **`core.PartyRole`** (`PartyRole.py:5`) — `party, role(customer|vendor|supplier|employee|lead|candidate|contact|partner), status, start_date`, `unique_together (party, role)`.
* **`core.Address`** (`Address.py:5`) — `party, kind, line1, city, country`. **`core.ContactMethod`** (`ContactMethod.py:5`) — `party, kind(email|phone|mobile), value`.
  ⇒ the vendor↔employee overlap rule is a plain join over verified columns. **No fuzzy/graph library needed.**
* **`core.Employment`** (`Employment.py:5`) — `party, org_unit, manager, job_title, hired_on, status`.
* **`core.Document`** (`Document.py:5`) — generic attachment (`content_type`/`object_id` GFK, `file`, `name`, `classification`, `version`). Use for screening evidence, risk-report evidence and the policy file.
* **`core.OrgUnit`**, **`core.Tenant`** — present.

### 4.2 `core.AuditLog` + `apps/core/utils.py` — **this decides bullet 3**
`apps/core/models/AuditLog.py:5`:

```
tenant(FK, SET_NULL, nullable)  user(FK, SET_NULL, nullable)  content_type(FK ContentType, nullable)
object_id(BigInteger, nullable)  related(GenericForeignKey)  target(CharField 255 — human label)
action(create|update|delete)  changes(JSONField)  at(auto_now_add)
Meta: ordering ["-at"], Index(tenant, at)
```

**The helper is `apps.core.utils.write_audit_log(user, obj, action, changes=None, tenant=None)` — there is
NO `log_action` anywhere in the tree** (`grep -rn "log_action" apps/` → *no matches*; `write_audit_log` →
**987 occurrences across 336 files**). It resolves the tenant from `obj.tenant` → `user.tenant`, stores
`AnonymousUser` as NULL, truncates `target` to 255, and creates one row.

**What AuditLog ALREADY gives bullet 3 (do not duplicate any of it):** who, what object (GFK), a human label,
the verb, a before→after JSON diff, the timestamp, tenant scoping, and an index that makes a
`(tenant, date-range)` register query cheap. `apps/procurement/views/DashboardPortal/` already renders it as
the 6.1 activity feed and 6.12 renders `receipt_audit` over it.

**What a tamper-evident layer must ADD (and only this):**
1. **No integrity proof.** Nothing detects an `UPDATE`/`DELETE` on `core_auditlog`; "append-only" is a
   convention (nothing but code discipline stops a writer), and `apps/procurement/models/ApprovalWorkflowEngine/Approvals.py:7`
   already *claims* the log exists "in tamper-evident shape". A hash chain makes that claim true.
2. **No sequence/`prev_hash`/digest columns**, and adding them would be a **cross-app `core` migration from a
   procurement build** — refused by precedent (`research-procurement-6.14.md:617-620`) and doubly wrong with a
   concurrent session in this checkout (L43). ⇒ **seal a RANGE from a procurement-owned table instead.**
3. **No verification surface** — nobody can answer "has this range been altered since we sealed it?".
4. **No retention statement.**

### 4.3 `apps/scm/models/ProcurementManagement/` — the document spine (L36: FK by string, never re-declare)
* `PurchaseRequisition` (`PurchaseRequisitions.py:14`) [PR-] — `title, requester(User), org_unit, budget, currency, required_by, status(draft|pending_approval|approved|rejected|converted|cancelled), justification, estimated_total(derived), approved_by/at, decision_note`; class constants `APPROVAL_TIERS = [(1000,'standard'),(10000,'manager'),(None,'executive')]`, `ELEVATED_TIERS`, `COMMITTED_STATUSES`. + `PurchaseRequisitionLine`.
* `PurchaseOrder` (`PurchaseOrders.py:15`) [PO-] — `vendor(core.Party)`, `requisition`, `quote`, `currency`, `payment_terms`, `order_date`, `expected_date`, `status(draft…closed)`, `ship_to`, `subtotal/tax_total/total(derived)`, `version`, `approved_by/at`, `acknowledged_at`, `cancelled_at`. + `PurchaseOrderLine`.
* `RFQ`/`RFQLine`/`RFQVendor`/`RFQQuote`/`RFQQuoteLine`; `GoodsReceiptNote`/`GoodsReceiptLine`.

### 4.4 `apps/accounting/models/` — the ledger (L29: link out, never restate)
`VendorProfile` (`AccountsPayable/VendorProfiles.py:5` — OneToOne `core.Party`; `payment_terms`,
`default_expense_account`, `currency`, `is_1099`, `is_active`, `notes` — **no bank fields**),
`Bill`, `Payment`, `Invoice`, `Budget`, `TaxCode`, `Currency`, `GLAccount`, `JournalEntry`.
`BankAccount` (`CashManagement/BankAccounts.py:7`) is the **tenant's own** account (`account_number_last4`,
no party FK). ⇒ **rule 4.9 (vendor bank-detail change) has no data source — report, don't build.**
6.17 posts **nothing** to the ledger.

### 4.5 What SCM already owns that 6.17 must NOT duplicate
| Existing (verified) | What it is | 6.17's relationship |
|---|---|---|
| `scm.SupplierProfile` (`SupplierRelationshipManagement/SupplierProfiles.py:12`) | The SRM vendor master: `onboarding_status(draft…suspended)`, `tier`, `legal_name`, `tax_registration`, `country`, and a 5-box due-diligence checklist including **`dd_compliance_verified` ("Compliance / sanctions checked")** | The checkbox is a *claim with no evidence*. 6.17's screening register is the **evidence behind that box** — link to it from the screening detail; do not add a second flag. |
| `scm.SupplierRiskAssessment` (`…/SupplierRiskAssessments.py:10`) [SRA-] | Internal point-in-time judgement: `financial/geopolitical/compliance/operational_score` 1-5, derived `risk_index` + `risk_level`, `mitigation_plan`, `next_review_date`, `status(draft|submitted|reviewed|archived)`. Already mapped by 6.4 → `scm:riskassessment_list` | **Complementary, not duplicate.** SRA = our opinion; `SupplierRiskSignal` = an **external provider's dated measurement**. Show the party's latest SRA on the signal page and link across. **Do not ship a second composite score.** |
| `scm.ComplianceRequirement` + `ComplianceCheck` (`ContractCompliance/ComplianceRequirements.py:120,561`) [CR-] | Standing **obligations**: `source`, 16 `FRAMEWORK_CHOICES`, `SCOPE_CHOICES(tenant/org_unit/party/location/item)`, `FREQUENCY_CHOICES`, `STATUS(applicable…retired)`, `CRITICALITY`, `next_due_date`; child check with `result(pass/fail/partial/n-a)`, `performed_on/by`, `evidence(core.Document)` | **This is recurring-obligation compliance — a different thing from a screening event.** A screening is one lookup against one list at one moment with match children; it is not a cadence obligation. Say so in the module docstring and cross-link. |
| `scm.TradeLicense`, `scm.TradeDocument`, `scm.SustainabilityAssessment` | 4.12 global-trade artefacts | Out of scope here. |
| `scm.SupplierContract`, `scm.SupplierScorecard`, `scm.SupplyChainAlert` | 4.2 / 4.11 | Untouched (scorecards belong to 6.16). |

### 4.6 What 6.1-6.15 already built inside `apps/procurement` that 6.17 must reuse or avoid
| Existing (verified in `apps/procurement/models/__init__.py`) | 6.17's relationship |
|---|---|
| **`ProcurementAlert`** (6.1) — `kind(deadline|approval|delivery|task|contract)`, `severity`, `status(open|acknowledged|resolved)`, `link_url` (internal-path-only, XSS-guarded), `due_at`, `assigned_to`, acknowledge/resolve verbs | **Reuse as the notification channel** for score deterioration, re-screening due and overdue attestations. Raise idempotently (the `run_renewal_alerts` / `Backorder.raise_alert` pattern). A new `kind` value (e.g. `"risk"`) is a **one-line `core`-free choice addition on a procurement-owned model** — allowed, but must be a surgical edit. **No second alert table.** |
| **`VendorSuspension`** (6.4) [VSU-] — `supplier(core.Party)`, `kind(suspension|blacklist)`, `reason_category(quality|delivery|compliance|financial|other)`, `status(requested|active|rejected|lifted)`, `blocking_for()` already consulted by `scm.purchaseorder_approve/_send` and the vendor portal | **The escalation target** for a confirmed screening true-match or a substantiated fraud alert. 6.17 links/deep-links to `procurement:vsu_list`; it never adds a second block mechanism. |
| **`RequisitionApproval`** (6.3) [RQA-] — `requisition`, `tier/tier_count`, `decision`, `approver`, `via_delegation`, `decided_at`; `ApprovalDelegation`, `ApprovalRoutingRule`, `EscalationPolicy` | The **data source for fraud rule 4.2 (self-approval)** and for delegation abuse. Read-only from 6.17. |
| **`SupplierInvoice`** + `SupplierInvoiceLine` + **`InvoiceMatchVariance`** + `InvoiceDispute` (6.13) — `vendor`, `purchase_order`, `goods_receipt`, `invoice_number_norm`, `duplicate_of`, `DUPLICATE_WINDOW_DAYS=90`, `match_status(…|duplicate_suspect)`, variance types incl. `duplicate`, `missing_po`, `missing_receipt` | **Duplicate-invoice detection is DONE.** 6.17 surfaces/links those rows as fraud signals and never re-detects them. Invoice/PO dates feed rule 4.4 (back-dated PO). |
| **`MaverickSpendFinding`** (6.14) [MSF-] — reasons `no_contract, po_less_invoice, no_requisition, off_catalog, non_preferred_vendor, price_above_contract, suspended_vendor, split_purchase`; `severity`, `status(open→acknowledged→justified|remediated|dismissed)`, `dedupe_key` unique per tenant, `scan(tenant, start, end, reasons=None, user=None)`, `SCAN_LINE_LIMIT=20000` | **The closest neighbour — read it before writing `FraudAlert`.** MSF = *process/contract leakage* (money that bypassed sourcing). 6.17 = *integrity* (collusion, conflict of interest, SoD, fabrication). **`split_purchase` stays 6.14's**; 6.17's reason list must not restate any of the eight. Copy the `scan()`/`dedupe_key` **shape**, not the reasons. |
| `PurchaseOrderChange` (6.10), `ReceiptTolerancePolicy` (6.12), `CatalogItem`/`CatalogPriceTier` (6.9), `BudgetMapping`/`CostForecast` (6.15), `ContractClause`/`ContractMilestone`/`ContractAmendment` (6.8) | Read-only sources / precedents. `ReceiptTolerancePolicy` is the precedent for a **tunable config table with no sidebar entry**. |

### 4.7 Planned masters that do NOT exist (so the build stubs or omits them, per L28)
* **No supplier bank-account record anywhere** ⇒ no bank-detail-change rule (§3 rule 4.9).
* **No external risk-data connector, no scheduler/worker, no FX rate table** ⇒ every "monitoring" feature is a
  captured observation plus an operator-triggered refresh, never a background job.
* **No graph/ML/LLM layer** ⇒ no link-analysis charts, no anomaly scoring; the page must not say "AI"
  (the 4.11/6.14 precedent).
* **No email sender wired for reminders** ⇒ attestation chasing raises a `ProcurementAlert` instead.
* `core.Item` does exist as `scm.Item` (4.3) but 6.17 needs no item dimension.

---

## 5. Recommended build scope — 4 tenant-scoped models (+1 if the pass has room)

Package `apps/procurement/models/RiskComplianceManagement/`, templates
`templates/procurement/riskcompliance/<entity>/{list,detail,form}.html`, all four layers mirrored.
Every model is `TenantOwned`/`TenantNumbered` from `apps/procurement/models/_base.py`; every FK to another app
is **by string** (`"core.Party"`, `"scm.PurchaseOrder"`, `"procurement.SupplierInvoice"`).

### 5.1 `ComplianceScreening` [SCR-] + child `ScreeningHit` — **bullet 1**
*Entity file `Screenings.py` (primary + its child, per the backend rule).*

`ComplianceScreening(TenantNumbered)`
* `party` FK `"core.Party"` PROTECT — the screened supplier (never a second vendor master).
* `list_source` — `ofac_sdn, ofac_other, bis_dpl, bis_entity, bis_uvl, state_isn, state_debarred, csl_consolidated, sam_exclusions, eu_consolidated, un_consolidated, internal_watchlist, other`.
* `checkpoint` — `onboarding, pre_award, pre_po, pre_payment, periodic, ad_hoc`.
* `method` — `manual_lookup, file_upload, api_feed` (**`api_feed` present but never selectable this pass** — the honest shape for a future connector; see 5.6).
* `screened_on` (date), `screened_by` (User, `editable=False`), `list_as_of` (date of the list data used).
* `result` — `clear, potential_match, confirmed_match, error` (what the lookup returned).
* `status` — `pending_review → cleared | escalated | blocked` (**what a human decided**), moved by verb methods only.
  **Guard: `clear()` refuses while any child hit has `disposition="open"`.**
* `next_rescreen_on` (date), `evidence` FK `"core.Document"` SET_NULL, `reference` (CharField — the search ID),
  `notes`, `suspension` FK `"procurement.VendorSuspension"` SET_NULL (stamped when escalation created a block).
* Indexes: `(tenant, status)`, `(tenant, party)`, `(tenant, screened_on)`, `(tenant, next_rescreen_on)`.

`ScreeningHit(models.Model)` — **tenant-less child**, resolved as
`get_object_or_404(ScreeningHit, pk=pk, screening__tenant=request.tenant)` (`scm.ComplianceCheck` / `AsnLine`
precedent): `screening` FK CASCADE, `matched_name`, `matched_list` (same CHOICES as `list_source`),
`match_score` PositiveSmallInteger 0-100 (validators), `match_type` (`name, alias, address, tax_id, other`),
`entry_reference`, `program` (e.g. the sanctions programme), `remarks`,
`disposition` (`open, false_positive, true_match, cleared_with_licence`), `disposition_note`
(**required to leave `open`** — enforced in `clean()`), `disposed_by/at` (`editable=False`).

*Pages:* register + detail with the hit formset + `clear`/`escalate`/`block` verbs; a **re-screening due**
board; a **batch screen** POST (P2). *Justified by features 1.1-1.10.*

### 5.2 `SupplierRiskSignal` [SRS-] — **bullet 2**
* `party` FK `"core.Party"` PROTECT; `provider` (`dnb, rapidratings, creditsafe, experian, coface, ecovadis, bitsight, internal, other`); `metric` (`fhr, credit_score, paydex, ser_rating, failure_score, altman_z, dso_days, days_beyond_terms, current_ratio, credit_rating, esg_rating, cyber_rating, other`).
* `observed_on` (date), `value` Decimal(9,2), `scale_min`/`scale_max` (defaulted per metric so an FHR of 42 and an SER of 7 both render honestly), `higher_is_better` Boolean.
* `band` (`low, watch, elevated, critical`) + `BAND_CSS` (L33 palette only); `trend` (`improved, stable, deteriorated, new`) and `previous_value` — **both derived** in `save()` from the prior row for the same `(party, provider, metric)`, `editable=False`.
* `review_status` (`new, reviewed, actioned, dismissed`), `review_note`, `reviewed_by/at` (`editable=False`).
* `next_refresh_on`, `source_ref`, `evidence` FK `"core.Document"`, `captured_by` (User, `editable=False`), `notes`.
* Indexes: `(tenant, party, observed_on)`, `(tenant, band)`, `(tenant, next_refresh_on)`.
* On save, a `deteriorated` + `elevated|critical` row raises **one idempotent `ProcurementAlert`** (open-alert
  guard, exactly `run_renewal_alerts`'s shape).

*Pages:* register (filters: party, provider, metric, band, trend) + detail showing the party's series and its
latest `scm.SupplierRiskAssessment`; a **refresh-due** board. *Justified by 2.1-2.8.*
**Explicitly honest:** no live bureau call. The page states that scores are captured by a person or a CSV and
shows `captured_by`/`observed_on`/`list_as_of`-style provenance on every row.

### 5.3 `FraudAlert` [FRD-] — **bullet 4**
* Source pointers, all SET_NULL, **at least one required in `clean()`** (the MSF pattern): `vendor` FK
  `"core.Party"`, `related_party` FK `"core.Party"` (the employee/second vendor in an overlap),
  `requisition` FK `"scm.PurchaseRequisition"`, `purchase_order` FK `"scm.PurchaseOrder"`,
  `supplier_invoice` FK `"procurement.SupplierInvoice"`, `approval` FK `"procurement.RequisitionApproval"`,
  `screening` FK `"procurement.ComplianceScreening"`.
* `rule` CHOICES — **`vendor_employee_match, self_approval, duplicate_vendor, backdated_po,
  screening_unresolved, new_vendor_rush`** (+ `po_escalation`, `round_amount` only if the pass has room).
  **None of 6.14's eight maverick reasons may appear here.**
* `severity` (`low, medium, high`) with a `SEVERITY_BY_RULE` default map (MSF precedent — a default, not a verdict);
  `status` (`open → investigating → substantiated | unsubstantiated | referred`), `OPEN_STATUSES` /
  `TERMINAL_STATUSES` tuples declared once.
* `detected_at` (auto), `document_date` (indexed), `amount` Decimal (nullable — a COI match has no amount),
  `detail` TextField (the evidence sentence: *"Vendor X and employee Y share tax id …"*),
  `dedupe_key` (`editable=False`, `unique_together (tenant, dedupe_key)`), `assigned_to` (User),
  `resolution_note`/`resolved_by`/`resolved_at` (`editable=False`).
* `scan(tenant, start, end, rules=None, user=None) -> {rule: newly_raised_count}` — operator-triggered POST,
  upsert on `dedupe_key`, a shared `_scan_context()` prefetch, and a bounded row cap (copy `SCAN_LINE_LIMIT`).
* **Writes nothing to the spine** — no auto-suspension, no invoice block (SAP BIS "park, don't block").

*Pages:* register + detail + the scan form (a date window + rule checkboxes) + a triage board.
**Rule tuning this pass = class constants** (`OVERLAP_FIELDS`, `NEW_VENDOR_DAYS`, `NEW_VENDOR_AMOUNT`,
`ROUND_AMOUNT_FLOOR`) surfaced read-only on the scan page; a `FraudRule` config table is the documented
follow-up (§6) if the pass has room — do **not** ship an editable rule table with no scan wired to it.

### 5.4 `ProcurementPolicy` [PPL-] + `PolicyAttestation` — **bullet 5**
*Entity file `Policies.py`.* Mirror `hrm.HRPolicy`/`hrm.PolicyAcknowledgment` (proven, in-repo).

`ProcurementPolicy(TenantNumbered)`: `title`, `category` (`code_of_conduct, purchasing_limits, sourcing,
supplier_selection, conflict_of_interest, gifts_hospitality, anti_bribery, data_privacy, sustainability, other`),
`version_number` (default "1.0"), `previous_version` self-FK SET_NULL (`related_name="superseded_by"`),
`applicable_org_unit` FK `"core.OrgUnit"` SET_NULL (blank = whole workspace), `summary`, `body`,
`document` FK `"core.Document"` SET_NULL, `status` (`draft, published, archived`), `effective_from`,
`review_due_on`, `published_at` (`editable=False`), `requires_attestation` Boolean,
`enforced_by` CharField (free-text pointer to the routing rule / tolerance policy that enforces it).
Derived: `attested_count`, `target_count`, `attestation_rate` (annotation-aware — copy HRM verbatim).
`unique_together ("tenant","number"), ("tenant","title","version_number")`.

`PolicyAttestation(TenantOwned)` (TenantOwned per the HRM precedent — there is a cross-policy
"my pending sign-offs" page): `policy` FK CASCADE, `user` FK `AUTH_USER_MODEL` CASCADE,
`status` (`pending, acknowledged, exempt`), `due_on`, `acknowledged_at` (`editable=False`),
`acknowledgement_note`, `unique_together ("tenant","policy","user")`, indexes
`(tenant, policy)`, `(tenant, user, status)`, `(tenant, -created_at)`.
**Publishing** raises one pending row per targeted user; **publishing v2 raises fresh rows and never rewrites
v1's** (NAVEX retention rule).

*Pages:* policy register + detail (attestation roster + rate) + form; **"My policies"** sign-off page;
an overdue-attestation board that raises `ProcurementAlert`s.

### 5.5 `AuditSeal` [ASL-] — **bullet 3** — *the 5th model: add it if the pass has room; it is the only thing that makes "tamper-proof" true*
Bullet 3's **page** ships regardless with **no table**: `procurement:audit_trail`, a filtered, exportable
register over `core.AuditLog` (user / action / content type / date range / object), CSV via `_csv_safe`.
The **seal** is what distinguishes it from 6.1's feed and 6.12's receipt audit:

`AuditSeal(TenantNumbered)` — `period_start`/`period_end` (datetime), `from_log_id`/`to_log_id` (BigInteger,
the id range actually covered), `row_count`, `digest` (CharField 64 — SHA-256 over the canonical
`(id, at, user_id, content_type_id, object_id, action, target, changes)` serialisation of each row in the
range, folded in id order), `prev_seal` self-FK SET_NULL, `prev_digest` (64), `chain_digest` (64 —
`H(prev_digest ‖ digest)`), `sealed_by` (User, `editable=False`), `sealed_at` (auto), `note`,
`last_verified_at`, `last_verify_ok` Boolean, `last_verify_detail`.
All hash fields `editable=False`; **no edit and no delete view** (evidence, not a record — the
`InvoiceMatchVariance` posture); creation is a single "Seal now" POST that takes everything since the last
seal. `verify()` re-computes and reports OK / the first offending log id.
**Zero `core` migrations, `hashlib` only, no new dependency, no second copy of the log.** The page states
plainly that this is *tamper-**evident*** (alteration is detectable), not tamper-proof storage.

### 5.6 Integration honesty (say this on the pages, not just in the code)
| Bullet | Real-world integration | How this pass models it honestly |
|---|---|---|
| 1 | ITA **CSL API** (11 lists, hourly, free) and **SAM.gov Exclusions** (separate); commercial feeds (Descartes, Dow Jones, LSEG) | Tenant-owned screening rows a person creates from the official search page, with `list_source`, `list_as_of`, `reference` and an evidence PDF. `method="api_feed"` exists in the vocabulary but is **not selectable**, so a future connector writes the *same rows* with no migration. Never ship a list table with fake entries. |
| 2 | D&B / RapidRatings / Creditsafe / EcoVadis subscriptions | Tenant-owned dated observations with `provider`, `captured_by`, `source_ref` and evidence. The "refresh due" board is the manual substitute for a feed. No fabricated scores in the seeder beyond clearly demo data. |
| 3 | SIEM / WORM storage / QLDB-style ledgers | In-app hash chain + verify; the page names the limitation. |
| 4 | Graph analytics / ML anomaly scoring | Deterministic SQL rules with named thresholds. The page says "rules", never "AI". |
| 5 | Reminder email, e-signature | `ProcurementAlert` + an in-app sign-off click with `acknowledged_at`; no email sender is wired. |

### 5.7 Sidebar (`LIVE_LINKS["6.17"]`) — one key per NavERP bullet, mapped to a staff-reachable page
```
"Regulatory Compliance Checks":     "procurement:screening_list"
"Supplier Financial Risk Monitoring":"procurement:risksignal_list"
"Audit Trail & Logging":            "procurement:audit_trail"
"Fraud Detection Rules":            "procurement:fraudalert_list"
"Policy Management & Acknowledgment":"procurement:policy_list"
```
(Boards — re-screening due, refresh due, overdue attestations, the fraud scan — are reached from their
register, per the established "this dict maps bullets to pages" rule. `AuditSeal` is reached from the audit
trail page.)

### 5.8 Seeder additions (`seed_procurement`, idempotent, existence-guarded)
One clear screening + one with two hits (one disposed false positive, one open true match) for an existing
vendor party; three risk signals across two providers for the same party so the trend/band render;
`FraudAlert.scan()` **called** over the seeded window so the alerts prove the detector (the 6.14 posture — do
not hand-write findings); one published policy v1.0 with attestations for the tenant's users, one draft; one
`AuditSeal` sealed after the rest of the seed so it verifies OK on a fresh DB.

---

## 6. Belongs to sibling sub-modules (parked, not scoped here)

* **KPIs, scorecards, on-time-delivery/defect metrics, 360 feedback, PIPs, benchmarking** → **6.16**
  (being built concurrently). `scm.SupplierScorecard` already exists. **Nothing about supplier *performance*
  is in scope**, including any "risk-adjusted score".
* **Vendor onboarding, qualification tiers, the portal, the suspension/blacklist register** → **6.4** (built)
  and **SCM 4.2**. 6.17 *raises* a suspension request; it does not own blocking.
* **The internal 4-factor composite risk assessment + mitigation plan** → **SCM 4.2 `SupplierRiskAssessment`**
  (already mapped by 6.4). 6.17 links to it.
* **Recurring regulatory obligations, frameworks, licences, trade documents, ESG assessments** →
  **SCM 4.12** (`ComplianceRequirement`/`ComplianceCheck`, `TradeLicense`, `SustainabilityAssessment`).
* **Duplicate-invoice detection, three-way-match variances, invoice disputes** → **6.13** (built). Cite, don't re-detect.
* **Maverick/off-contract spend, `split_purchase`, contract leakage, spend cubes** → **6.14** (built).
* **Contract clauses, obligations, renewals, e-signature** → **6.8** / **SCM 4.2**.
* **Approval routing, DOA delegation, escalation policy** → **6.3** (built) — 6.17 only *reads* the signatures.
* **Policy document repository search, version-controlled document library, full-text indexing** → **6.19
  Document & Knowledge Management** (its "Procurement Policy Library" bullet is the *find it* surface; 6.17
  owns the policy record, its versions and the sign-off ledger, and 6.19 will index them).
* **Journal postings, credit notes, payment blocks** → **`apps.accounting`** (L29). 6.17 posts nothing.
* **Stock/quarantine holds for non-compliant goods** → **inventory 5.14/5.15**, **SCM 4.9**.

---

## 7. Deferred (later passes / integrations)

1. **Live CSL / SAM.gov connector** (and any commercial screening feed) — needs an outbound-HTTP design with the
   CRM-webhooks SSRF-guard precedent, plus list caching and retention. `method="api_feed"` reserves the shape.
2. **OFAC 50%-rule ownership analysis, PEP/adverse-media, sanctioned-ownership graphs** — needs licensed data.
3. **A `FraudRule` config table + calibration/simulation ("how many alerts would this threshold raise?")** —
   SAP BIS's strongest idea and the natural 6.17 second-pass entity; this pass ships tunable constants shown
   read-only next to the scan.
4. **Conflict-of-interest *declaration* register** (evaluator/committee attestations with interest type, related
   party and mitigating control) — a second attestation kind with its own fields; rule 4.1 catches the
   undeclared case meanwhile. Strong candidate for the 6.17 second pass.
5. **Vendor bank-detail-change monitoring** — blocked on data: no supplier bank record exists anywhere
   (`accounting.VendorProfile` has none; `accounting.BankAccount` is the tenant's own). Needs an AP-owned
   `VendorBankAccount` with change history — an `apps/accounting` build, not a procurement one.
6. **Link/network analysis, ML anomaly scoring, entity-resolution fuzzy matching across vendor masters** — no
   graph/ML layer; the rules stay deterministic and the page never says "AI".
7. **Scheduled/automatic re-screening and score refresh** — no worker/scheduler in this repo
   (`accounting.ScheduledReport` already models config-without-worker). The due boards + an operator POST are
   the honest equivalent.
8. **Attestation reminder emails and e-signature on policies** — no mail sender wired; alerts substitute.
9. **DB-level append-only enforcement / WORM / SIEM export / 10-year retention purge job** — infrastructure.
   The seal proves alteration; it does not prevent it, and the page must say so.
10. **Inherent-vs-residual risk questionnaires and tiering-driven review cadence** (Coupa, ProcessUnity) — a
    questionnaire engine; 6.6's `RfxEvent`/`RfxQuestion` is the reusable substrate if this is ever built,
    and 4.2's SRA covers the scored-judgement half today.
11. **Cyber-rating and ESG feeds** (BitSight/RiskRecon/EcoVadis) — reserved as `provider`/`metric` values so a
    later connector needs no migration.
