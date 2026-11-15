# Module 11.18 IT Asset Management (ITAM) — Gap Register

> **File**: `.agents/tasks/gaps-assets-11.18.md`
> **Sub-module**: Module 11.18 IT Asset Management (ITAM) (`apps/assets`)
> **Created**: 2026-11-15
> **Invariant**: Never delete a gap entry. Close with `- [x]` + commit SHA/test verification, or mark `- [~]` with justification.

---

### GAP-ASSETS-11.18-01: Agentless Network & Endpoint Discovery Scanners
- **Owner**: `apps/assets` / `apps/integrations`
- **Waiting For / Blocked On**: Integration with Module 11.15 `AssetIntegrationConnector` background worker pipelines and MDM webhooks (Intune, Jamf, Kandji, SNMP/SSH/WMI subnet sweepers).
- **Status**: `- [~]` Deferred / Transferred to Module 11.15 integration pass
- **Done When**: Scheduled background worker imports discovered IP/MAC/host entries into `ItHardwareAsset` staging queue and matches on `mac_address`/`serial_number` without overwriting tenant assets.

---

### GAP-ASSETS-11.18-02: Automated Cloud Billing & SCIM User Sync
- **Owner**: `apps/assets` / FinOps & Identity team
- **Waiting For / Blocked On**: Automated AWS Cost & Usage Reports (CUR), Azure Enterprise Agreement / Cost Management API, and GCP BigQuery billing export pipelines; Okta/Entra ID SCIM active user synchronization.
- **Status**: `- [~]` Deferred to Module 11.15 FinOps connector and Module 0.4 IAM pass
- **Done When**: Billing ingestion cron updates `CloudAssetSubscription.monthly_recurring_cost` and SCIM sync auto-populates `active_seats_30d` from identity provider login activity logs.

---

### GAP-ASSETS-11.18-03: Interactive CMDB Topology Canvas & ITSM Change Gating
- **Owner**: Module 18 (`apps/itsm`) / `apps/assets`
- **Waiting For / Blocked On**: Module 18 IT Service Management (ITSM) Incident, Problem, and Change Management models.
- **Status**: `- [~]` Deferred to Module 18 build
- **Done When**: Interactive WebGL/SVG dependency graph visualizer renders multi-tier blast radiuses with drag-and-drop relationship authoring, and ITSM Change Requests enforce automated CAB approval gates based on `compute_cmdb_impact()` blast radius criticality.

---

### GAP-ASSETS-11.18-04: ITAD Certified Recycler EDI & Automated CoD Ingestion
- **Owner**: `apps/assets` / `apps/scm`
- **Waiting For / Blocked On**: Module 4.19 EDI/B2B interchange integration with IT Asset Disposition (ITAD) recycling partners.
- **Status**: `- [~]` Deferred to SCM/ITAD EDI pipeline pass
- **Done When**: EDI 856 / customized destruction message ingestion automatically attaches Certificate of Destruction (CoD) reference, updates `sanitization_status="certificate_on_file"`, and retires hardware asset to `sanitized_retired`.
