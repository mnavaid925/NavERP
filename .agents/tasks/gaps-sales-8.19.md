# Gap Register — Sub-module 8.19: Master Data & Configuration (Module 8: Sales Management System)

> Tracks features, dynamic engines, and runtime infrastructure deferred to future passes or external services.
> Entries are IMMUTABLE: close by ticking `- [x]` with the resolving commit SHA or passing test —
> never delete an entry.

---

### GAP-sales-8.19-01: Live Multi-Currency Automated FX Exchange Rate Feed API Integration
- **Verbatim from plan**: Sub-module 8.19 establishes multi-currency support on price books and regional settings (`SalesPriceBookEntry.currency_code`, `SalesRegionalSetting.primary_currency_code`, `supported_currencies`). Automated scheduled retrieval of live foreign exchange rates from central banks (e.g., European Central Bank, US Federal Reserve) or external API feeds (e.g., OpenExchangeRates, Fixer.io, CurrencyLayer) with volatility hedging and automated margin recalculation is deferred to an external integration adapter.
- **Owner**: `sales:8.19` / `accounting` (General Ledger Currency & FX Engine)
- **Waiting For / Blocked On**: External commercial FX rate provider subscription, tenant API credentials, and background worker queue.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: An automated background worker connects to an external FX API on a scheduled daily cadence, updates currency conversion tables, and recomputes dynamic price book conversions with audit logs without manual intervention.

---

### GAP-sales-8.19-02: Runtime Dynamic Database DDL Schema Altering for Custom Entities
- **Verbatim from plan**: Sub-module 8.19 provides the metadata registry for custom objects, attributes, and relationships (`SalesCustomEntityDefinition`), defining field types, picklists, validation expressions, and relationship lookups. Executing live dynamic PostgreSQL/SQLite `ALTER TABLE ADD COLUMN` or dynamically synthesizing Django virtual model classes in memory at runtime is deferred for data safety, migration reproducibility, and tenant isolation integrity.
- **Owner**: `sales:8.19` (Custom Schema Engine)
- **Waiting For / Blocked On**: Sandboxed dynamic DDL execution layer or EAV / JSONField hybrid storage engine with GIN indexing support.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Registering a `SalesCustomEntityDefinition` record provisions or maps to an underlying extensible storage table or dynamic JSON attribute dictionary without requiring server restarts or database lockups.

---

### GAP-sales-8.19-03: Dynamic Formula AST Evaluation Sandboxing & Cross-Table Expression Engine
- **Verbatim from plan**: Sub-module 8.19 stores declarative formula expressions (e.g., `"{expected_arr} * {commission_rate_pct} / 100"`) and validation rule conditions. Real-time compilation of arbitrary user-defined mathematical/logical formulas into a secure, sandboxed Python AST or JavaScript interpreter capable of traversing related models and verifying syntax safety is deferred.
- **Owner**: `sales:8.19` (Formula Evaluation Engine)
- **Waiting For / Blocked On**: Sandboxed Python execution library (e.g., `RestrictedPython` or PyExecJS) and expression AST parser.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Sales administrators can enter formula expressions in the UI, preview calculated output across joined records in real time, and save validated AST expressions that execute safely during record lifecycle events.

---

### GAP-sales-8.19-04: Real-Time Localized Tax Jurisdiction Rating API (Vertex / Avalara AvaTax)
- **Verbatim from plan**: Sub-module 8.19 defines regional sales tax presentation conventions (`tax_exclusive` vs. `tax_inclusive`), regional compliance frameworks, and cooling-off periods. Live external geocoded sales tax calculation by destination street address via Avalara AvaTax, Vertex Cloud, or TaxJar is deferred.
- **Owner**: `sales:8.19` / `accounting` (Module 2 Tax Engine)
- **Waiting For / Blocked On**: Commercial AvaTax/Vertex API credentials, geocoding address verification service, and tenant tax profile configuration.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Sales quotes and orders automatically query real-time tax jurisdiction APIs based on delivery postal codes and apply multi-tier district taxes automatically.

---

### GAP-sales-8.19-05: Multilingual GNU Gettext PO/MO Translation Pack Catalog Importer & In-Place UI Translation
- **Verbatim from plan**: Sub-module 8.19 provides regional formatting (dates, numbers) and localized legal notices / quote terms. An interactive in-browser Translation Workbench for translating all sales UI strings and importing/exporting GNU gettext `.po`/`.mo` files is deferred to core internationalization.
- **Owner**: `sales:8.19` / `core` (i18n Platform)
- **Waiting For / Blocked On**: Central gettext compilation pipeline and tenant-scoped translation override table.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Sales administrators can edit label translations for custom and standard fields in multiple languages directly via a Translation Workbench web interface without server redeployment.
