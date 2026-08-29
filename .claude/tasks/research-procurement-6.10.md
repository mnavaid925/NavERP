# Research — Procurement 6.10 Purchase Order (PO) Management (2026-08-27)

## NavERP.md bullets (exact text)
1. **PO Generation** — Automated creation of POs from approved requisitions or manual entry.
2. **PO Dispatch & Acknowledgment** — Sending POs to suppliers and tracking their acceptance/acknowledgment.
3. **PO Change Order Management** — Process for modifying quantity, price, or delivery date on an active PO.
4. **PO Cancellation & Close-out** — Workflow to cancel unfulfilled POs or close fully received POs.
5. **PO Line Item Tracking** — Granular tracking of delivery status for individual line items on a PO.

## Spine verification (grep-verified, L28)

### `scm.PurchaseOrder` (apps/scm/models/ProcurementManagement/PurchaseOrders.py) — THE canonical PO
- 9-state lifecycle: draft → pending_approval → approved → sent → acknowledged → partially_received → received → cancelled | closed.
- `EDITABLE_STATUSES = ("draft", "pending_approval")` — post-dispatch edits go through amendment.
- Amendment trail: `version` + `amendment_reason` (editable=False), bumped by scm's `purchaseorder_amend` view.
- Vendor acknowledgement: `acknowledged_at` / `acknowledgement_note` / `promised_ship_date` (staff-recorded; scm `purchaseorder_acknowledge`).
- Cancellation: `cancelled_at` / `cancellation_reason` (scm `purchaseorder_cancel`, tenant-admin + reason-required); close: `purchaseorder_close`.
- Derived: `subtotal/tax_total/total` via `recalc_totals()`; received qty NEVER stored — `received_by_line()` annotates GRN aggregates in ONE query; `recompute_receipt_status()` derives partial/full.
- `PurchaseOrderLine`: item_description/sku_hint/uom_hint (L28 free-text stand-in), quantity, unit_price, tax_rate_pct, derived line_total, gl_account; `received_quantity()` memoized, `outstanding_quantity()`.

### SCM views (apps/scm/views/ProcurementManagement/PurchaseOrders.py)
submit / approve / send / acknowledge / cancel / close / amend — ALL exist. URL names `scm:purchaseorder_*` under `orders/`.

### Inventory 5.3 layer (apps/inventory/models/PurchaseOrderManagement/)
- `PurchaseOrderApprovalRule` / `PurchaseOrderApproval` [PA-] — multi-tier approval; clearing final tier performs spine approve under lock.
- `PurchaseOrderDispatch` [PD-] — dispatch log (email/edi/print, recipient, reference); FIRST dispatch of an approved order flips it to `sent` in-transaction. Routes `inventory:dispatch_*` at `po/dispatches/`. **Owns the Dispatch half of bullet 2.**

### Procurement 6.x prior art
- 6.2 `RequisitionAmendment` [RAM-] + lines: file → admin decide → atomic apply under row lock; one-open-amendment rule; lost-target tolerance. **The exact template for bullet 3.**
- 6.1 Quick Requisition Entry writes INTO `scm.PurchaseRequisition` — precedent for a procurement page writing the PO spine.

## Gap analysis (what 6.10 genuinely adds vs maps)

| Bullet | Verdict |
|---|---|
| PO Generation | **GAP**: requisition→PO exists ONLY via RFQ award (rfq.requisition.status="converted"). No direct approved-PR→PO drafting. Manual entry = scm:purchaseorder_create (exists). ADD: a generation console listing approved PRs with a one-click Generate that drafts PO+lines into the spine. |
| PO Dispatch & Acknowledgment | **MAPPED**: dispatch log = inventory 5.3 `inventory:dispatch_list`; acknowledgement recording = scm `purchaseorder_acknowledge` on the order detail. No new table (L36/L29). |
| PO Change Order Management | **GAP**: scm's `amend` is an IN-PLACE edit with version bump — no gated proposal/decide workflow for a DISPATCHED commitment. ADD: `PurchaseOrderChange` [PCO-] + `PurchaseOrderChangeLine` mirroring 6.2's RAM pattern (file → admin approve applies under PO row lock, bumps version, stamps amendment_reason). |
| PO Cancellation & Close-out | **MAPPED**: scm cancel (admin, reason) + close verbs exist on the order detail. Sidebar maps to `scm:purchaseorder_list` (verbs live on its detail page). No new table. |
| PO Line Item Tracking | **GAP (surface)**: per-line received data EXISTS (derived) but no cross-order granular tracking board. ADD: computed page over `scm.PurchaseOrderLine` annotated with received/outstanding/% — zero writes. |

## Build scope (models: 2)
- `PurchaseOrderChange` [PCO-] — FK `scm.PurchaseOrder` (PROTECT), type amend|cancel, status pending→approved/rejected, requested_by/decided_by/at, decision_note, applied_at; proposed header: new_expected_date. CHANGEABLE_STATUSES = ("sent", "acknowledged", "partially_received") — the dispatched commitments past in-place editing (draft/pending edit directly; approved can still be edited pre-dispatch via scm amend; terminal states are closed).
- `PurchaseOrderChangeLine` — action add|update|remove, target_line FK `scm.PurchaseOrderLine` SET_NULL, proposed quantity/unit_price/expected date fields (blank = keep), item_description for adds.
- Computed pages (no model): `po_generation` (approved-PR queue + Generate form → drafts scm.PurchaseOrder + copies lines + marks PR converted, all atomic), `po_line_tracking` (annotated line board).

## Excluded-from-form fields
tenant, number (auto), status (workflow-owned), requested_by/decided_by/*_at stamps, applied_at, purchase_order (pinned by URL).

## Wire-up
- Folder `PurchaseOrderManagement/` ×4 layers; urls prefixes `po-changes/`, `po-generation/`, `po-tracking/` (distinct whole components; no clash with existing procurement segments).
- Migration **0015** (0001–0014 exist).
- LIVE_LINKS["6.10"]: PO Generation → `procurement:po_generation`; PO Dispatch & Acknowledgment → `inventory:dispatch_list`; PO Change Order Management → `procurement:poc_list`; PO Cancellation & Close-out → `scm:purchaseorder_list`; PO Line Item Tracking → `procurement:po_line_tracking`.
- Seeder `_seed_po_management`: one pending change order over a seeded sent/partially_received PO + one generated PO from an approved PR (guarded, reuses existing rows).
- Admin: PCO read-only-decision posture (mirrors RequisitionAmendmentAdmin).

## Deferred / parked
- ASN / freight tracking / split delivery (bullet set of 6.11, NOT 6.10).
- Vendor-side acknowledgment portal (scm staff-recording stands in; L32).
- Auto-PO from reorder rules (inventory 5.3 owns auto-drafting).