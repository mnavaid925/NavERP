# Gap Register — Sub-module 12.3: Risk Management (ISO 14971 / FMEA)

**Module:** 12 — Quality Management System (`apps/quality/`)  
**Sub-module:** 12.3 — Risk Management (ISO 14971 / FMEA)  
**Status:** COMPLETE (`32 / 32` review findings closed in [review-quality-12.3.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-quality-12.3.md); `248 / 248` dedicated 12.3 tests passing on SQLite, `604 / 604` total Quality suite passing; roadmap & upstream items tracked below)

---

## Gaps & Deferred Follow-Ups Inventory

### GAP-quality-12.3-01 — Cross-Module CAPA / NCR Hand-off on Ineffective Risk Control Measures
- **Owner:** Quality Management (`apps/quality/`)
- **Waiting For / Blocked On:** Sub-module 12.4 (Corrective & Preventive Action / CAPA) and Sub-module 12.5 (Non-Conformance & Deviation Management / NCR).
- **Status:** `[~]` Blocked on sibling sub-module development — `RiskControlMeasure` currently tracks status (`proposed` -> `in_progress` -> `implemented` -> `verified` -> `rejected`), captures objective verification evidence notes, and verifies implementation/effectiveness; automated spawning of CAPA / NCR records when mitigations fail or introduce unacceptable secondary risks will be bridged when Sub-modules 12.4 and 12.5 land.
- **Done When:** An ineffective risk control measure provides a one-click action to spawn a pre-filled `CapaAction` (12.4) or `NonConformance` (12.5) referencing the control number and parent hazard assessment.

### GAP-quality-12.3-02 — Post-Market Surveillance (PMS) Automated Signal Intake from Complaints
- **Owner:** Quality Management / Post-Market Safety (`quality`)
- **Waiting For / Blocked On:** Sub-module 12.13 (Customer Complaints Management) and adverse event telemetry feeds.
- **Status:** `[~]` Blocked on sibling sub-module development — `RiskReviewRecord` models review types including `post_market_surveillance` and `complaint_trend_trigger` with `pms_sources_reviewed` documentation fields; automated streaming aggregation of complaint frequencies and threshold surge alerts into risk assessments will be wired when Sub-module 12.13 lands.
- **Done When:** Customer complaints exceeding incident thresholds automatically flag related `RiskAssessment` records for review with updated occurrence frequency alerts.

### GAP-quality-12.3-03 — Direct Regulatory XML Submission Format (FDA eSubmitter / EUDAMED)
- **Owner:** Regulatory Affairs / Quality (`quality`)
- **Waiting For / Blocked On:** Sub-module 12.17 (Regulatory Submissions & Notified Body Filings).
- **Status:** `[~]` Deferred to Sub-module 12.17 — Full streaming CSV exports for Risk Management Plans, Hazard Assessments, Control Measures, Review Records, FMEA Matrices, and Risk Traceability Matrices are fully implemented. Specialized XML/HL7 SPL schemas for direct authority gateway submission will be integrated in Sub-module 12.17.
- **Done When:** A Risk Management Plan provides an export action producing FDA eSubmitter / EUDAMED compliant XML technical file packages.

---

## Completed Scope Note (`12.3` Deliverables)
- All `4` models (`RiskManagementPlan` `QRMP-`, `RiskAssessment` `QRSK-`, `RiskControlMeasure` `QRCM-`, `RiskReviewRecord` `QRMR-`), `4` ModelForms, `2` interactive workbenches (`fmea_matrix`, `risk_traceability_matrix`), `24` function-based views with `@login_required` and `@tenant_admin_required`, `14` templates, `LIVE_LINKS["12.3"]` (all 5 feature bullets), `apps/quality/admin.py`, `seed_quality` command extension (`_seed_submodule_12_3`), migrations `0005` & `0006`, and `248` dedicated unit/form/view/security tests (`604` total across `apps/quality/tests/`) are shipped and 100% green.
