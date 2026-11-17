# Gap Register — Sub-module 12.4: Corrective & Preventive Action (CAPA)

**Module:** 12 — Quality Management System (`apps/quality/`)  
**Sub-module:** 12.4 — Corrective & Preventive Action (CAPA)  
**Status:** COMPLETE (`25 / 25` review findings closed in [review-quality-12.4.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-quality-12.4.md); `342 / 342` dedicated 12.4 tests passing on SQLite, `946 / 946` total Quality suite passing; roadmap & upstream items tracked below)

---

## Gaps & Deferred Follow-Ups Inventory

### GAP-quality-12.4-01 — Automated Non-Conformance (NCR) / Deviation Escalation to CAPA
- **Owner:** Quality Management (`apps/quality/`)
- **Waiting For / Blocked On:** Sub-module 12.5 (Non-Conformance & Deviation Management / NCR).
- **Status:** `[~]` Blocked on sibling sub-module development — `CapaInvestigation` models `source_type="ncr"` and `source_reference` (e.g. `"NCR-2026-0042"`), capturing originating non-conformance event numbers; direct 1-click promotion from an uncontained NCR ticket into a pre-populated `CapaInvestigation` will be integrated when Sub-module 12.5 lands.
- **Done When:** An approved NCR with critical risk or repeat failure pattern provides an action to spawn a pre-filled `CapaInvestigation` referencing the NCR ID and containment records.

### GAP-quality-12.4-02 — Supplier Corrective Action Request (SCAR) Bidirectional Integration
- **Owner:** Supplier Quality Management (`quality` / `scm`)
- **Waiting For / Blocked On:** Sub-module 12.6 (Supplier Quality Management).
- **Status:** `[~]` Blocked on sibling sub-module development — `CapaInvestigation` models `source_type="supplier_issue"`, and `RootCauseAnalysis` models `root_cause_category="supplier"`; bidirectional synchronization between internal CAPA action items and external vendor SCAR response tracking will be wired when Sub-module 12.6 lands.
- **Done When:** A CAPA with supplier root cause can spawn a formal SCAR tracking vendor 8D response timelines, SCAR sign-offs, and supplier audit findings.

### GAP-quality-12.4-03 — Customer Complaint & Vigilance Ingestion Bridge
- **Owner:** Quality Post-Market Surveillance (`quality`)
- **Waiting For / Blocked On:** Sub-module 12.13 (Customer Complaints & Feedback Management).
- **Status:** `[~]` Blocked on sibling sub-module development — `CapaInvestigation` models `source_type="complaint"` and links to `RiskAssessment` and `DesignProject`; automated complaint surge thresholds triggering proactive CAPA investigation intake will be bridged when Sub-module 12.13 lands.
- **Done When:** Trending complaint spikes exceeding statistical alarm thresholds automatically spawn a draft `CapaInvestigation` with attached incident logs.

---

## Completed Scope Note (`12.4` Deliverables)
- All `4` models (`CapaInvestigation` `QCAP-`, `RootCauseAnalysis` `QRCA-`, `CapaAction` `QACT-`, `CapaEffectivenessReview` `QEFF-`), `4` ModelForms, `1` interactive workbench (`capa_tracking_board`), `28` function-based views with `@login_required` and `@tenant_admin_required`, `13` templates, `LIVE_LINKS["12.4"]` (all 5 feature bullets), `apps/quality/admin.py`, `seed_quality` command extension (`_seed_submodule_12_4`), migrations `0007` & `0008`, and `342` dedicated unit/form/view/security tests (`946` total across `apps/quality/tests/`) are shipped and 100% green.
