# Gaps Register: Business Intelligence Sub-module 10.9 (Standard & Operational Reporting)

> **Context**: Sub-module 10.9 delivers enterprise operational and standard reporting: banded document templates (`ReportDefinition`), dynamic runtime input prompt parameters (`ReportParameter`), query execution telemetry and export audit logs (`ReportExecution`), and transactional drill-through navigation paths (`ReportDrillPath`).
> All core CRUD workflows, interactive HTML grid viewer, print-ready preview with CSS `@page` styling, multi-tenant isolation, defensive CSV formula escaping, XSS sanitization, 18 review findings, and 153 dedicated tests (1,259 tests across `apps/bi/`) are fully completed and verified green.

---

### GAP-10.9-01: Native Binary Headless PDF & XLSX Rendering Engine
- **Owner**: `bi` / Document Generation Agent
- **Waiting For / Blocked On**: Server-side binary document dependencies (`weasyprint` / `cairo` or `reportlab` and `openpyxl`) in production hosting environment.
- **Status**: `- [~]` Deferred (Interactive HTML viewer, print-ready CSS `@page` layout with browser print-to-PDF, and streaming CSV/JSON exports are fully functional in this pass).
- **Done When**: Server-side headless compilation renders pixel-perfect binary PDF documents and native multi-tab `.xlsx` workbooks directly from banded report definition JSON models without client browser intervention.

### GAP-10.9-02: Automated Scheduled Report Bursting & Multi-Recipient Distribution
- **Owner**: `bi` / Scheduling & Notification Agent
- **Waiting For / Blocked On**: Asynchronous background Celery worker task runner and tenant email delivery SMTP service integration.
- **Status**: `- [~]` Deferred (On-demand execution and telemetry recording via `report_execution_run` and export routes are fully implemented in this pass).
- **Done When**: Cron-scheduled bursting tasks evaluate report definitions on automated cadences, slice data by recipient tenant/department parameters, and dispatch generated reports via secure email or SFTP destinations.

---

### Summary of Completed Invariants:
- All 18 review findings (`C1`–`C3`, `I1`–`I8`, `M1`–`M7`) in `.claude/tasks/review-bi-10.9.md` are closed (`- [x] fixed`).
- Zero open critical, important, or minor defects in Sub-module 10.9.
- 153 passing dedicated tests across `test_operationalreporting_models.py`, `_forms.py`, `_views.py`, and `_security.py`.
- 1,259 passing tests across full `apps/bi` test suite.
