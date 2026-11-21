# Gap Register — Sub-module 12.17: Regulatory Compliance & Submissions

**Module:** 12 — Quality Management System (QMS) (`apps/quality/`)  
**Sub-module:** 12.17 — Regulatory Compliance & Submissions  
**Date:** 2026-11-21  
**Base Commit:** `9448e93f0d2646888e2e79a8faafd9f648805e20`  
**Status:** COMPLETE / CLEAN (`25 / 25` review findings fixed in [.claude/tasks/review-quality-12.17.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-quality-12.17.md); `29 / 29` dedicated 12.17 tests passing; `2,405 / 2,405` full Quality suite tests green; zero skipped or deferred items; 100% feature coverage against pre-build contract and research catalog).

---

## Review Findings Burn-down Summary

| Severity | Count | Open | Fixed | Skipped | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Critical** | 2 | 0 | 2 | 0 | Closed |
| **Important** | 9 | 0 | 9 | 0 | Closed |
| **Minor** | 14 | 0 | 14 | 0 | Closed |
| **Total** | 25 | 0 | 25 | 0 | **100% Resolved** |

All 25 review findings across the 6 serial review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) were resolved, verified, and committed by the `code-fixer` subagent in exact ID order (C1–C2, I1–I9, M1–M14).

---

## Upstream & Sibling Observations

### GAP-quality-12.17-U01: Upstream Sub-module 12.4 CAPA Property Assignment Defect
- **Owner**: `apps/quality/views/CapaManagement/CapaInvestigations.py` (Sub-module 12.4)
- **Waiting For / Blocked On**: Fix in Submodule 12.4 CAPA detail view.
- **Status**: `[~] Transferred / Upstream`
- **Observed In**: QA Smoke Testing and full Quality test suite audit.
- **Details**: `apps/quality/views/CapaManagement/CapaInvestigations.py:108` attempts to set `capa.actions_count = ...`, but `actions_count` is defined as a `@property` on the `CapaInvestigation` model without a setter, raising `AttributeError: can't set attribute 'actions_count'` if invoked.
- **Done When**: Submodule 12.4 view is refactored to pass `actions_count` in the template context dictionary or annotate the queryset rather than mutating the model instance attribute.

---

## Gaps & Deferred Items Inventory

**Gaps**: None

All pre-build contract requirements, four models (`RegulatorySubmission`, `ProductRegistration`, `RegulatoryCommitment`, `PostMarketSurveillanceReport`), executive command center dashboard (`regulatory_dashboard`), 21 routes, filters, pagination, CSV exports with formula injection defense and chunked streaming, multi-tenant isolation, admin registrations, idempotent seeder routines, and 29 automated test cases across `apps/quality/tests/` are fully implemented, verified, and passing without regressions.
