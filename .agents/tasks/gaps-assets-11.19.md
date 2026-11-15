# Gap Register — Sub-module 11.19: Fleet & Vehicle Management

**Module:** 11 — Asset Management System (`apps/assets/`)  
**Sub-module:** 11.19 — Fleet & Vehicle Management  
**Status:** COMPLETE (`25 / 25` review findings closed in [review-assets-11.19.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-assets-11.19.md); `114 / 114` dedicated 11.19 tests passing on SQLite; roadmap & upstream items tracked below)

---

## Gaps & Deferred Follow-Ups Inventory

### GAP-assets-11.19-01 — Live OBD-II / CAN-bus Telematics Daemon & GPS Geofence Streaming
- **Owner:** Fleet Telematics & IoT Infrastructure (`assets` + `core`)
- **Waiting For / Blocked On:** Outbound MQTT/HTTP telemetry receiver daemon and streaming websocket pipeline for live OBD-II / J1939 CAN-bus telemetry from hardware black boxes (Geotab, Samsara, Verizon Connect).
- **Status:** `[~]` Deferred by architecture (`contract-assets-11.19.md` & `.claude/tasks/todo.md`) — `FleetVehicle` stores coordinates, speed, heading, odometer, engine hours, and `last_telemetry_at`, updated deterministically via `ping_telemetry` and ORM fixtures without external socket dependencies.
- **Done When:** Hardware adapter daemon ingests live CAN-bus telemetry frames, updates `FleetVehicle` coordinates and odometer atomically, and pushes real-time position updates to `fleet_telematics_board`.

### GAP-assets-11.19-02 — Automated Commercial Fleet Fuel Card API (WEX / Comdata / Fleetcor)
- **Owner:** Financial Integrations / Procurement (`apps/assets/` & `apps/accounting/`)
- **Waiting For / Blocked On:** Third-party fleet fuel card API integration and webhook ingestion pipeline for automated fuel transaction clearing and fraud detection.
- **Status:** `[~]` Deferred by design — `VehicleFuelLog` tracks fuel card tokens, pump transaction details, gallons, cost, and receipts with full CSV export and manual entry validation.
- **Done When:** Automated scheduled sync fetches settled fuel card transactions from WEX/Comdata, dedupes against `receipt_reference` and `fuel_card_token`, and generates `VehicleFuelLog` records with MPG auto-calculation.

### GAP-assets-11.19-03 — Upstream Pre-existing `test_spacefacility_security.py` Failures
- **Owner:** Assets Sub-module 11.17 Maintenance Pass
- **Waiting For / Blocked On:** Sub-module 11.17 implementation pass. The untracked file `apps/assets/tests/test_spacefacility_security.py` existed in the working tree at session start and was deliberately left untouched per project rule L45.
- **Status:** `[ ]` Open (upstream 11.17 follow-up)
- **Done When:** Sub-module 11.17 is built, its models/views/urls are integrated, and `test_spacefacility_security.py` passes cleanly.

---

## Completed Scope Note (`11.19` Deliverables)
- All `4` models (`FleetVehicle` `FLT-`, `VehicleFuelLog` `VFUL-`, `VehicleDriverAssignment` `VDRV-`, `VehicleServiceSchedule` `VSRV-`), `5` ModelForms (`FleetVehicleForm`, `VehicleFuelLogForm`, `VehicleDriverAssignmentForm`, `VehicleServiceScheduleForm`, `VehicleServiceScheduleCompleteForm`), `25` FBV views across 4 entities + telematics board, `13` templates, `LIVE_LINKS["11.19"]`, `apps/assets/admin.py`, `_seed_tenant_11_19` (`seed_assets`), migrations `0026` & `0027`, and `114` dedicated unit/form/view/security tests are shipped and passing.
