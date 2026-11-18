# Gap Register: Module 12.8 In-Process Quality Control (IPQC)

**Target Sub-module**: 12.8 In-Process Quality Control (IPQC)  
**App**: `quality` (`apps/quality/models/InProcessQuality/`)  
**Date**: 2026-11-19  
**Status**: All Review Findings Closed (4 External Cross-Module Integration Enhancements Deferred)  

---

## Review Findings Status

All 20 review findings (3 Critical, 9 Important, 8 Minor) across `.claude/tasks/review-quality-12.8.md` were resolved, verified, and individually committed in Phase 5 with zero internal gaps remaining.

---

## Cross-Module & External Architecture Gaps

### `GAP-quality-12.8-01`
- **Owner**: `apps/inventory` (Module 5) / `apps/quality` (Module 12.8)
- **Waiting For / Blocked On**: Implementation of Module 5 Inventory `StockMove` transaction ledger for scrap / WIP inventory write-offs.
- **Status Checkbox**:
  - [~] Deferred to Module 5 build
- **Done When**: When an in-process inspection with `disposition="scrap_lot"` is saved, an automated `StockMove` transaction of type `scrap` is emitted linking the scraped WIP lot to the inventory waste balance account.

### `GAP-quality-12.8-02`
- **Owner**: `apps/quality` (Module 12.8) / Industrial Telemetry Bridge
- **Waiting For / Blocked On**: Hardware IoT / OPC-UA MQTT telemetry collector gateway service.
- **Status Checkbox**:
  - [~] Deferred to External Gateway Integration
- **Done When**: Telemetry feeds from CNC / PLC controllers stream directly into `ProcessParameterLog` via an authorized background ingest endpoint rather than manual entry.

### `GAP-quality-12.8-03`
- **Owner**: `apps/quality` (Module 12.8) / Customer Portal (Module 13 / Portal)
- **Waiting For / Blocked On**: External Customer Portal authentication and digital signature infrastructure.
- **Status Checkbox**:
  - [~] Deferred to Customer Portal implementation
- **Done When**: First Article Inspections with `customer_approval_required=True` can be routed directly to customer contacts via the external portal for cryptographic approval sign-off.

### `GAP-quality-12.8-04`
- **Owner**: `apps/manufacturing` (Module 14 MES) / `apps/scm`
- **Waiting For / Blocked On**: Module 14 Manufacturing Execution System (MES) digital routing dispatch spine.
- **Status Checkbox**:
  - [~] Deferred to Module 14 MES build
- **Done When**: In-process inspection records automatically link to granular operation step sequences on MES shop-floor job routing dispatches and hold the subsequent step until inspection passes.

---

## Gaps Summary

- **Open (Internal Quality 12.8)**: 0
- **Closed (Review Findings)**: 20
- **Deferred (Cross-Module Roadmaps)**: 4 (`GAP-quality-12.8-01` through `GAP-quality-12.8-04`)
