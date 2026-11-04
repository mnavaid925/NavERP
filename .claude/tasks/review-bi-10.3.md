# Review Findings — Sub-module 10.3: Data Warehouse & Storage (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.3 Data Warehouse & Storage
- **Module:** 10 Business Intelligence (`apps/bi`)
- **Review Date:** 2026-11-04
- **Changeset:** `0e8727a2393473bbcb65013c79c53f02c9081036...75d1a1d2f6b549c4d3df40c30afb2f99bc62bcfe`
- **Review Passes In Progress:** Pass 1/6 Completed (`code-reviewer`)

---

## Pass 1: `code-reviewer`

### Critical Findings
*None.*

### Important Findings
- [ ] **CR-I1**: `WarehouseTableForm` excludes inactive FK references on edit, blocking updates to existing tables. In `apps/bi/forms/DataWarehouse/WarehouseTables.py` (L62-L72), `lakehouse_zone`, `data_mart`, and `storage_policy` querysets filter strictly on `is_active=True`. When editing an existing instance, permit the currently bound foreign key ID even if inactive (`Q(is_active=True) | Q(pk=self.instance.<fk_id>)`).
- [ ] **CR-I2**: `lakehouse_zone_delete` writes audit log before `ProtectedError` check, logging phantom deletions. In `apps/bi/views/DataWarehouse/LakehouseZones.py` (L181-L194), `write_audit_log` is called before `zone.delete()`. If `zone.delete()` raises `ProtectedError`, an immutable audit record is left. Call `write_audit_log` inside `transaction.atomic()` after `zone.delete()` or verify no protected references exist before logging.
- [ ] **CR-I3**: Key filter dropdowns omitted from list templates despite view context support. In `templates/bi/data_warehouse/warehouse_table/list.html`, `data_mart`, `grain`, and `is_active` dropdowns are missing. In `data_mart/list.html`, `lakehouse_zone/list.html`, and `warehouse_storage_policy/list.html`, the `is_active` dropdown is missing. Add the missing `<select>` filters.
- [ ] **CR-I4**: `DataMartForm` does not reject foreign `owner` and `steward` users in `clean()`. In `apps/bi/forms/DataWarehouse/DataMarts.py` (L54-L58), `reject_foreign` only checks `["org_unit"]`. Add `"owner"` and `"steward"` to `reject_foreign`.

### Minor Findings
- [ ] **CR-M1**: Undefined `.badge-purple` used in detail and overview templates (`templates/bi/data_warehouse/warehouse_table/detail.html`, `lakehouse_zone/detail.html`). Replace with design-system badge `.badge-info` or `.badge-slate`.
- [ ] **CR-M2**: `WarehouseTable.generate_ddl_sql()` hardcodes `PARTITION BY RANGE`. In `apps/bi/models/DataWarehouse/WarehouseTables.py` (L134-L136), support matching SQL partition keywords (`HASH`, `LIST`, `RANGE`) based on `partition_strategy`.
- [ ] **CR-M3**: `time_travel_days` lacks server-side range validation. In `apps/bi/forms/DataWarehouse/WarehouseStoragePolicies.py`, add validation in `clean()` verifying `time_travel_days <= 90`.
- [ ] **CR-M4**: `seed_bi.py` command help string omits Sub-module 10.3. Update help text to include `& 10.3 Data Warehouse & Storage`.
