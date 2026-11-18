# Gap Register: Sub-module 12.6 Supplier & Vendor Quality Management (`apps/quality/`)

**Module**: Quality Management System (`quality`)  
**Sub-module**: 12.6 Supplier & Vendor Quality Management  
**Date Created**: November 18, 2026  
**Status**: Managed / Deferred to Inter-Module Integration Phase

---

### GAP-quality-12.6-01: External Supplier Portal Web Access
- **ID**: `GAP-quality-12.6-01`
- **Owner**: `apps/quality` / `apps/accounts` / Portal Team
- **Waiting For / Blocked On**: Implementation of external customer/vendor portal authentication architecture in Module 0 / Module 6 (Procurement Portal).
- **Status Checkbox**: `- [~]` Deferred (Transferred to External Vendor Portal backlog)
- **Done When**: External supplier users can authenticate with unprivileged portal roles to upload 8D containment evidence, view their quality scorecards, and submit SCN requests without consuming internal staff user seats.

---

### GAP-quality-12.6-02: EDI 856 / ASN & eCoA Automated Ingestion
- **ID**: `GAP-quality-12.6-02`
- **Owner**: `apps/quality` / `apps/scm` (Module 4) / `apps/bi` (Module 10 Ingestion)
- **Waiting For / Blocked On**: Electronic Data Interchange (EDI) infrastructure and document parser pipeline in Module 10 / Module 13.
- **Status Checkbox**: `- [~]` Deferred (Waiting for EDI pipeline)
- **Done When**: Inbound EDI 856 Advance Shipment Notices automatically ingest digital Certificates of Analysis (eCoA), check compliance limits against `SupplierQualificationAudit.requires_coa`, and flag dock-to-stock receiving exemptions.

---

### GAP-quality-12.6-03: Automated Purchase Order Block Enforcement
- **ID**: `GAP-quality-12.6-03`
- **Owner**: `apps/scm` (Module 4.1 Procurement) / `apps/procurement` (Module 6)
- **Waiting For / Blocked On**: Cross-module signal or middleware in `apps/scm/forms/ProcurementManagement/PurchaseOrders.py` and `apps/procurement/forms/` checking supplier qualification status.
- **Status Checkbox**: `- [~]` Deferred (Cross-module validation hook)
- **Done When**: SCM and Procurement purchase order creation forms prevent PO submission to vendors whose `SupplierQualificationAudit.qualification_status` is `"suspended"` or `"disqualified"`, unless an override concession deviation is linked.
