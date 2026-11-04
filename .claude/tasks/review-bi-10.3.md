# Review Findings — Sub-module 10.3: Data Warehouse & Storage (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.3 Data Warehouse & Storage
- **Module:** 10 Business Intelligence (`apps/bi`)
- **Review Date:** 2026-11-04
- **Changeset:** `0e8727a2393473bbcb65013c79c53f02c9081036...75d1a1d2f6b549c4d3df40c30afb2f99bc62bcfe`
- **Review Passes In Progress:** Pass 5/6 Completed (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`)

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

---

## Pass 2: `explorer`

### Critical Findings
*None.*

### Important Findings
- [ ] **EX-I1**: Missing filter controls for pinned context keys `active_choices`, `data_marts`, and `grain_choices` across list templates. In `warehouse_table/list.html`, add `<select>` for `data_mart`, `grain`, and `is_active`. In `data_mart/list.html`, `lakehouse_zone/list.html`, and `warehouse_storage_policy/list.html`, add `<select>` for `is_active`.
- [ ] **EX-I2**: `warehouse_overview.html` omits rendering the pinned context metric `total_compressed_bytes`. Display `total_compressed_bytes` formatted alongside `total_rows`.
- [ ] **EX-I3**: Unsupported badge class `.badge-purple` used in `data_mart/detail.html`, `lakehouse_zone/list.html`, `lakehouse_zone/detail.html`, `warehouse_storage_policy/detail.html`, `warehouse_table/list.html`, `warehouse_table/detail.html`. Replace with `.badge-info` or `.badge-slate`.
- [ ] **EX-I4**: Duplicate primary key column rendered in `warehouse_table/detail.html`. Skip `col.name == warehouse_table.primary_key_column` in the `schema_definition` loop to avoid double-rendering the PK.

### Minor Findings
- [ ] **EX-M1**: Unused context variable `show_ddl_tab` in `warehouse_table_ddl_preview` (`apps/bi/views/DataWarehouse/WarehouseTables.py:255`).
- [ ] **EX-M2**: Unscoped `owner` and `steward` User querysets in `DataMartForm.__init__`. Scope User dropdown querysets to users belonging to `self.tenant`.

---

## Pass 3: `frontend-reviewer`

### Critical Findings
*None.*

### Important Findings
- [ ] **FR-I1**: Invalid theme badge class `badge-purple` (7 occurrences across 5 templates). Replace `badge-purple` with `.badge-info` or `.badge-slate`.
- [ ] **FR-I2**: Missing `data_mart`, `grain`, and `is_active` filter dropdowns in list templates. Add `<select>` dropdowns with `|stringformat:"d"` for FKs and matching GET query persistence.
- [ ] **FR-I3**: Missing `is_active` filter dropdown across all 4 list templates (`data_mart/list.html`, `lakehouse_zone/list.html`, `warehouse_storage_policy/list.html`, `warehouse_table/list.html`).

### Minor Findings
- [ ] **FR-M1**: Undefined utility class `text-primary` for navigation links. Replace with `text-brand` or `text-blue-600`.
- [ ] **FR-M2**: Empty state heading typography: use semantic `<h3>` inside `.empty-state` container for consistency with `theme.css`.
- [ ] **FR-M3**: Native browser `alert()` in SQL DDL copy button. Replace with non-blocking feedback or label toggle.

---

## Pass 4: `performance-reviewer`

### Critical Findings
- [ ] **PF-C1**: Unbounded full-table scans and memory bloat loading all system users in `DataMartForm`. In `apps/bi/forms/DataWarehouse/DataMarts.py` (L39-L43), `owner` and `steward` User querysets are left unscoped to tenant, executing `User.objects.all()` twice across all tenants. Scope `owner` and `steward` querysets with `get_user_model().objects.filter(tenant=self.tenant).order_by("username")`.

### Important Findings
- [ ] **PF-I1**: Missing composite index on `(tenant, storage_policy)` on `WarehouseTable`. In `apps/bi/models/DataWarehouse/WarehouseTables.py` (L106-L111), add `models.Index(fields=["tenant", "storage_policy"], name="idx_bdwt_ten_policy")` to optimize reverse lookup from `WarehouseStoragePolicy`.
- [ ] **PF-I2**: Missing composite index on `(tenant, name)` on ordered models `DataMart` and `WarehouseStoragePolicy`. In `apps/bi/models/DataWarehouse/DataMarts.py` (L81-L85) and `apps/bi/models/DataWarehouse/WarehouseStoragePolicies.py` (L107-L111), add `(tenant, name)` indexes to avoid database filesorts.
- [ ] **PF-I3**: Missing composite index on `(tenant, -created_at)` on `WarehouseTable`. In `apps/bi/models/DataWarehouse/WarehouseTables.py`, add `models.Index(fields=["tenant", "-created_at"], name="idx_bdwt_ten_created")` to optimize recent tables query on overview dashboard.
- [ ] **PF-I4**: Unbounded `marts` query and DOM generation on `warehouse_overview` dashboard. In `apps/bi/views/DataWarehouse/WarehouseOverview.py` (L36-L40), slice `marts` queryset to top 8 items (`[:8]`) to avoid rendering unbounded lists.

### Minor Findings
- [ ] **PF-M1**: Redundant `SELECT COUNT(*)` query before queryset iteration in detail templates (`lakehouse_zone/detail.html:112`, `warehouse_storage_policy/detail.html:159`). Use `{{ tables|length }}` instead of `{{ tables.count }}` to leverage result cache.
- [ ] **PF-M2**: Large unused `schema_definition` JSONField loaded in list and overview queries (`WarehouseOverview.py:30-34`, `WarehouseTables.py:22-24`). Add `.defer("schema_definition")` to querysets in list and overview views.
- [ ] **PF-M3**: Non-atomic multi-table delete in `seed_bi --flush` (`apps/bi/management/commands/seed_bi.py:36-50`). Wrap deletion block in `with transaction.atomic():`.

---

## Pass 5: `qa-smoke-tester`

- **Execution Results:** 77/77 tests passed (0 failures).
- **Coverage:** All 18 routes tested with HTTP status (200/302/404), zero comment leaks (`{#` / `{% comment`), real pagination page 2 verified, junk parameters gracefully handled, and 14/14 cross-tenant IDOR endpoints returned strict HTTP 404 Not Found.
- **Protected Deletion:** Lakehouse Zone with associated Warehouse Tables caught `ProtectedError` and rendered user-facing warning without server crash.

### Critical Findings
*None.*

### Important Findings
*None.*

### Minor Findings
*None.*
