# Gaps Register: Business Intelligence Sub-module 10.10 (Self-Service & Ad-Hoc Analytics)

> **Context**: Sub-module 10.10 delivers visual self-service query exploration, visual query composition (`AdHocQuery`), calculated metrics and dimensional formulas (`AdHocCalculatedField`), multi-source dataset blending and mashups (`DataBlendDefinition`), and interactive saved exploratory views (`SavedAnalysisView`) with fine-grained personal and team sharing permissions.
> All core CRUD workflows, visual query builder, live execution telemetry, multi-source blend previews, exploratory dashboard, formula validation, CSRF/method security guards, 19 review findings, and 56 dedicated tests (1,315 tests across `apps/bi/`) are fully completed and verified green.

---

### GAP-10.10-01: In-Browser Sandboxed SQL WASM Engine (DuckDB / SQLite WASM)
- **Owner**: `bi` / Analytics Execution Agent
- **Waiting For / Blocked On**: Client-side WASM packaging and local storage caching policies.
- **Status**: `- [~]` Deferred (Server-side sanitized visual query composition, ORM execution, and structured JSON results are fully operational).
- **Done When**: Users can execute high-velocity ad-hoc analytical queries entirely client-side using DuckDB-WASM against cached partitioned parquet or arrow datasets without hitting the central transactional database.

### GAP-10.10-02: Multi-User Real-Time Collaborative Canvas (WebSockets)
- **Owner**: `bi` / Realtime Collaboration Agent
- **Waiting For / Blocked On**: Django Channels ASGI setup, Redis pub/sub layer, and operational transformation/CRDT engine.
- **Status**: `- [~]` Deferred (Asynchronous personal and team workspace sharing, template flags, and 1-click view cloning are fully functional).
- **Done When**: Multiple authenticated team members can simultaneously edit visual query compositions and chart options with live cursor indicators and automatic conflict resolution.

---

### Summary of Completed Invariants:
- All 19 review findings (`C1`–`C2`, `I1`–`I10`, `M1`–`M7`) in `.claude/tasks/review-bi-10.10.md` are closed (`[x] fixed`).
- Zero open critical, important, or minor defects in Sub-module 10.10.
- 56 passing dedicated tests across `test_selfserviceanalytics_models.py`, `_forms.py`, `_views.py`, and `_security.py`.
- 1,315 passing tests across full `apps/bi` test suite.
