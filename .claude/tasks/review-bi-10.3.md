# Review Findings — Sub-module 10.3: Data Warehouse & Storage (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.3 Data Warehouse & Storage
- **Module:** 10 Business Intelligence (`apps/bi`)
- **Review Date:** 2026-11-04
- **Changeset:** `0e8727a2393473bbcb65013c79c53f02c9081036...0c6ad05187ecfc02b0c1e84fc375cbce8fa7fa34`
- **Review Status:** Complete (All 6/6 Review Passes Finished: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Consolidated & Prioritized Findings Registry

### Critical Findings

- [x] **C1**: `DataMartForm` scopes neither `owner` nor `steward` to `self.tenant` in `__init__` (triggering full `auth_user` table scans across all tenants and exposing cross-tenant user dropdowns) and omits them from `reject_foreign()` in `clean()`. In `apps/bi/forms/DataWarehouse/DataMarts.py` (L39-L43, L54-L58), filter `owner` and `steward` querysets by `get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username")` and add `"owner"` and `"steward"` to `reject_foreign(self, cleaned_data, ["org_unit", "owner", "steward"])`. fixed — fix(bi): scope owner and steward to tenant and reject foreign users in DataMartForm

---

### Important Findings

- [x] **I1**: `WarehouseTableForm` excludes inactive FK references on edit, blocking updates to existing tables. In `apps/bi/forms/DataWarehouse/WarehouseTables.py` (L62-L72), `lakehouse_zone`, `data_mart`, and `storage_policy` querysets filter strictly on `is_active=True`. When editing an existing instance, permit the currently bound foreign key ID even if inactive (`Q(is_active=True) | Q(pk=self.instance.<fk_id>)`). fixed — fix(bi): permit currently bound foreign keys on edit in WarehouseTableForm
- [x] **I2**: `lakehouse_zone_delete` writes audit log before `ProtectedError` check, leaving a phantom deletion record. In `apps/bi/views/DataWarehouse/LakehouseZones.py` (L181-L194), wrap `zone.delete()` and `write_audit_log` inside `transaction.atomic()` or log only after successful deletion. fixed — fix(bi): wrap lakehouse zone deletion and audit logging in transaction.atomic
- [x] **I3**: Key filter dropdown controls omitted from list templates despite view context support:
  - In `templates/bi/data_warehouse/warehouse_table/list.html`, add `<select>` dropdowns for `data_mart`, `grain`, and `is_active`.
  - In `templates/bi/data_warehouse/data_mart/list.html`, add `<select>` dropdown for `is_active`.
  - In `templates/bi/data_warehouse/lakehouse_zone/list.html`, add `<select>` dropdown for `is_active`.
  - In `templates/bi/data_warehouse/warehouse_storage_policy/list.html`, add `<select>` dropdown for `is_active`. fixed — feat(bi): add missing filter dropdowns across warehouse list templates
- [x] **I4**: Unsupported theme badge class `.badge-purple` used across 5 templates (`warehouse_table/detail.html`, `warehouse_table/list.html`, `lakehouse_zone/detail.html`, `lakehouse_zone/list.html`, `warehouse_storage_policy/detail.html`, `data_mart/detail.html`). Replace all `.badge-purple` occurrences with valid design system classes `.badge-info` or `.badge-slate`. fixed — fix(bi): replace badge-purple with badge-slate across warehouse templates
- [x] **I5**: `warehouse_overview.html` omits rendering the pinned context metric `total_compressed_bytes`. Display `total_compressed_bytes` formatted alongside `total_rows`. fixed — feat(bi): render total_compressed_bytes metric in warehouse_overview stat card
- [x] **I6**: Missing composite index on `(tenant, storage_policy)` on `WarehouseTable`. In `apps/bi/models/DataWarehouse/WarehouseTables.py` (L106-L111), add `models.Index(fields=["tenant", "storage_policy"], name="idx_bdwt_ten_policy")` to optimize reverse lookup from `WarehouseStoragePolicy`. fixed — perf(bi): add composite index idx_bdwt_ten_policy on WarehouseTable
- [x] **I7**: Missing composite index on `(tenant, name)` on ordered models `DataMart` and `WarehouseStoragePolicy`. In `apps/bi/models/DataWarehouse/DataMarts.py` (L81-L85) and `apps/bi/models/DataWarehouse/WarehouseStoragePolicies.py` (L107-L111), add `(tenant, name)` indexes to avoid database filesorts. fixed — perf(bi): add composite index on (tenant, name) for DataMart and WarehouseStoragePolicy
- [x] **I8**: Missing composite index on `(tenant, -created_at)` on `WarehouseTable`. In `apps/bi/models/DataWarehouse/WarehouseTables.py` (L106-L111), add `models.Index(fields=["tenant", "-created_at"], name="idx_bdwt_ten_created")` to optimize recent tables query on overview dashboard. fixed — perf(bi): add composite index idx_bdwt_ten_created on WarehouseTable
- [x] **I9**: Unbounded `marts` query and DOM generation on `warehouse_overview` dashboard. In `apps/bi/views/DataWarehouse/WarehouseOverview.py` (L36-L40), slice `marts` queryset to top 8 items (`[:8]`) to avoid rendering unbounded lists. fixed — perf(bi): limit marts query to top 8 items on warehouse_overview
- [x] **I10**: Missing SQL identifier validation in `WarehouseTableForm` for table and column metadata. In `apps/bi/forms/DataWarehouse/WarehouseTables.py`, validate `table_name` and `primary_key_column` against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`. fixed — feat(bi): validate SQL identifiers for table and column names in WarehouseTableForm

---

### Minor Findings

- [ ] **M1**: Duplicate primary key column rendered in `warehouse_table/detail.html`. Skip `col.name == warehouse_table.primary_key_column` in the `schema_definition` loop to avoid double-rendering the PK.
- [ ] **M2**: `WarehouseTable.generate_ddl_sql()` hardcodes `PARTITION BY RANGE`. In `apps/bi/models/DataWarehouse/WarehouseTables.py` (L134-L136), support matching SQL partition keywords (`HASH`, `LIST`, `RANGE`) based on `partition_strategy`.
- [ ] **M3**: `time_travel_days` lacks server-side range validation. In `apps/bi/forms/DataWarehouse/WarehouseStoragePolicies.py`, add validation in `clean()` verifying `time_travel_days <= 90`.
- [ ] **M4**: `seed_bi.py` command help string omits Sub-module 10.3. Update help text to include `& 10.3 Data Warehouse & Storage`.
- [ ] **M5**: Unused context variable `show_ddl_tab` in `warehouse_table_ddl_preview` (`apps/bi/views/DataWarehouse/WarehouseTables.py:255`). Remove unused variable from view context.
- [ ] **M6**: Undefined utility class `text-primary` used in navigation links in detail templates. Replace with `text-brand` or `text-blue-600`.
- [ ] **M7**: Empty state heading typography: use semantic `<h3>` inside `.empty-state` container for consistency with `theme.css`.
- [ ] **M8**: Native browser `alert()` in SQL DDL copy button. Replace with non-blocking feedback or label toggle.
- [ ] **M9**: Redundant `SELECT COUNT(*)` query before queryset iteration in detail templates (`lakehouse_zone/detail.html:112`, `warehouse_storage_policy/detail.html:159`). Use `{{ tables|length }}` instead of `{{ tables.count }}` to leverage result cache.
- [ ] **M10**: Large unused `schema_definition` JSONField loaded in list and overview queries (`WarehouseOverview.py:30-34`, `WarehouseTables.py:22-24`). Add `.defer("schema_definition")` to querysets in list and overview views.
- [ ] **M11**: Non-atomic multi-table delete in `seed_bi --flush` (`apps/bi/management/commands/seed_bi.py:36-50`). Wrap deletion block in `with transaction.atomic():`.
- [ ] **M12**: Validate ANSI SQL data types in `WarehouseTableForm.clean_schema_definition_raw` to restrict unsupported arbitrary type strings.
- [ ] **M13**: Unclamped search query `q` parameter string length in list filters. Clamp `q = request.GET.get("q", "").strip()[:100]` across list endpoints.

---

## Detailed Pass Logs

### Pass 1: `code-reviewer`
- `CR-I1`: Inactive FK references on edit in `WarehouseTableForm`.
- `CR-I2`: `lakehouse_zone_delete` phantom audit log on `ProtectedError`.
- `CR-I3`: Missing filter dropdowns in list templates.
- `CR-I4`: `DataMartForm` user validation in `clean()`.
- `CR-M1`: Undefined `.badge-purple`.
- `CR-M2`: Hardcoded `PARTITION BY RANGE` in `generate_ddl_sql`.
- `CR-M3`: `time_travel_days` range validation.
- `CR-M4`: `seed_bi.py` help string update.

### Pass 2: `explorer`
- `EX-I1`: Missing filter controls for pinned context keys.
- `EX-I2`: `warehouse_overview.html` omits `total_compressed_bytes`.
- `EX-I3`: Unsupported `.badge-purple` class.
- `EX-I4`: Duplicate primary key column in `warehouse_table/detail.html`.
- `EX-M1`: Unused `show_ddl_tab` variable.
- `EX-M2`: Unscoped User querysets in `DataMartForm`.

### Pass 3: `frontend-reviewer`
- `FR-I1`: Invalid theme badge class `badge-purple`.
- `FR-I2`: Missing `data_mart`, `grain`, `is_active` filter dropdowns.
- `FR-I3`: Missing `is_active` dropdown across all 4 list templates.
- `FR-M1`: Undefined utility class `text-primary`.
- `FR-M2`: Empty state heading typography.
- `FR-M3`: Native `alert()` in DDL copy button.

### Pass 4: `performance-reviewer`
- `PF-C1`: Unbounded `User.objects.all()` table scans in `DataMartForm`.
- `PF-I1`: Missing composite index `(tenant, storage_policy)` on `WarehouseTable`.
- `PF-I2`: Missing composite index `(tenant, name)` on `DataMart` and `WarehouseStoragePolicy`.
- `PF-I3`: Missing composite index `(tenant, -created_at)` on `WarehouseTable`.
- `PF-I4`: Unbounded `marts` query and DOM generation on overview dashboard.
- `PF-M1`: Redundant `COUNT(*)` in detail templates.
- `PF-M2`: Large `schema_definition` JSONField loaded in list and overview views.
- `PF-M3`: Non-atomic multi-table delete in `seed_bi --flush`.

### Pass 5: `qa-smoke-tester`
- 77/77 tests passed. 0 Critical, 0 Important, 0 Minor. All 18 routes tested with HTTP status (200/302/404), zero comment leaks (`{#` / `{% comment`), real pagination page 2 verified, junk parameters gracefully handled, and 14/14 cross-tenant IDOR endpoints returned strict HTTP 404 Not Found.

### Pass 6: `security-reviewer`
- `SEC-I1`: Audit log false-positive on protected lakehouse zone deletion.
- `SEC-I2`: Cross-tenant user FK enumeration and injection in `DataMartForm`.
- `SEC-I3`: SQL identifier injection via unsanitized table/column names in DDL generation.
- `SEC-M1`: Unvalidated SQL data types in `schema_definition_raw`.
- `SEC-M2`: Unclamped search query `q` parameter length in list filters.
