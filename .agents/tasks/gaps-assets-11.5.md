# Gap Register: Module 11.5 — Maintenance & Repair Management

**Module**: Asset Management System (`apps/assets`)  
**Sub-module**: 11.5 Maintenance & Repair Management  
**Creation Date**: 2026-11-09  
**Review File**: `.claude/tasks/review-assets-11.5.md`  

---

### GAP-assets-11.5-01: Canonical Database Table Names (`db_table`)
- **Owner**: `apps/assets` / Schema Migration Pass
- **Waiting For / Blocked On**: Sub-module 11.5 migration `0008` was generated and applied without explicit `db_table` attributes in `Meta`, defaulting to Django's standard names (`assets_assetmaintenancerequest`, `assets_assetmaintenanceschedule`, `assets_assetservicecontract`, `assets_assetmaintenancelog`). Modifying `db_table` now requires `AlterModelTable` migrations across production databases.
- **Status**: `- [~]` Deferred / Documented as-built (contract updated to match `0008` table names)
- **Done When**: Asset module schema harmonization pass issues an explicit `AlterModelTable` migration renaming tables to `assets_maintenance_request`, `assets_maintenance_schedule`, `assets_service_contract`, and `assets_maintenance_log` if strict naming parity with 11.1–11.4 is mandated by client.

---

### GAP-assets-11.5-02: Balanced Financial General Ledger Journal Entry Posting in `AssetMaintenanceLog.post_to_gl`
- **Owner**: `apps/assets` / `apps/accounting` cross-module ledger posting
- **Waiting For / Blocked On**: General Ledger posting requires integration with `apps/accounting` AP bills or cash disbursement accounts (determining whether maintenance expenditure was settled via cash bank disbursement or vendor trade payable invoice).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: `AssetMaintenanceLog.post_to_gl()` instantiates a balanced `accounting.JournalEntry` and `JournalLine`s (debiting `expense_account` and crediting AP or Cash) when `total_cost > 0`, saves the reference in `AssetMaintenanceLog.journal_entry`, and marks status `posted`.
