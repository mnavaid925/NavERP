# Review — Inventory 5.6 Inventory Tracking & Control

Changeset: `ea0add1159b52ec44e6c62971e5636485c91ae2a..78dcd18b` (+ fixes appended by the fixer).
Lanes run in parallel: code-reviewer · security-reviewer · frontend-reviewer · performance-reviewer
(qa-smoke lane executed inline during the build: all pages 200, IDOR→404, lifecycle verbs guarded,
leak-marker scan clean — recorded in temp/smoke_56.py output). Findings deduped across lanes;
IDs assigned after sort. Fix order = ID order.

## Findings

| ID | Severity | Status | File:line | Finding | Suggested fix |
|----|----------|--------|-----------|---------|---------------|
| C1 | Critical | [ ] open | apps/inventory/forms/InventoryTrackingControl/InventoryReservations.py:75-81 | Reservation-form ATP double-counts the instance's own active claim on EDIT: `_active_held` runs without `.exclude(pk=self.instance.pk)`, so saving an active row validates quantity against availability that already subtracts itself (on_hand 10, own 8 → "Only 2 … cannot reserve 8"). Contradicts StockStatusForm.clean and the SalesOrderAllocation precedent. | Add `.exclude(pk=self.instance.pk)` to the reservations queryset passed to `_active_held` in `clean()`. |
| I1 | Important | [ ] open | apps/inventory/views/InventoryTrackingControl/StockLevels.py:46-55 | `_on_order_map` sums line-level `quantity` AND child-level `receipt_lines__quantity_received` in ONE annotate — join fan-out multiplies `ordered` by receipt count whenever partial receipts exist (order 10 received 4+6 → outstanding 10 instead of 0). | Split into two grouped queries (lines-only ordered by sku_hint; received grouped via po_line__sku_hint over receivable POs), merge dicts, floor at zero. |
| I2 | Important | [ ] open | apps/inventory/views/InventoryTrackingControl/InventoryReservations.py:79-85 | `reservation_edit` never enforces `is_editable`: a crafted POST mutates released/consumed/cancelled history rows, contradicting the documented invariant and the sibling delete guard. | Fetch scoped obj first, refuse non-editable statuses with flash + redirect to detail, then delegate to crud_edit. |
| I3 | Important | [ ] open | apps/inventory/forms/InventoryTrackingControl/InventoryReservations.py:90-106 + views/.../InventoryReservations.py:154-176 | Lot-pool asymmetry: when a claim names lot L, its held/classification aggregates narrow siblings to lot L only and DROP unlotted whole-pool claims, while spine allocations are always counted lot-blind — a lot-L reservation can pass ATP on units already claimed/held by unlotted rows; the stock-levels page (whole-pool) then reports the negative the form should have caught. | In the lot-named branch, also subtract unlotted claims (`Q(lot_serial=lot) | Q(lot_serial__isnull=True)`) in `_active_held`, `_unsellable_classified` and `_other_active_qty`; document the conservative union. |
| I4 | Important | [ ] open | models/StockStatuses.py:79-86; views/StockStatuses.py:51; views/InventoryReservations.py:148-151; forms/StockStatuses.py:68-71; forms/InventoryReservations.py:71-74 | Every spot-ledger aggregate filters item+location[+lot] with NO tenant predicate, so neither scm_move_tnt_item_loc_idx nor the mirror index applies — MariaDB scans the item's entire move history across all locations on hot paths (detail pages, every reservation submit). | Add `.filter(tenant=obj.tenant_id)` / equivalent to each spot-scope query shape. |
| I5 | Important | [ ] open | templates/inventory/tracking/reservation/detail.html:18; list.html:59 | "Cancel Claim"/inline cancel gated to `status == 'reserved'` only, but the model allows cancel from released too — a released claim whose goods never ship has no UI path to be freed. | Gate cancel on `{% if obj.is_active %}` (reserved OR released) matching ACTIONABLE_STATUSES. |
| M1 | Minor | [ ] open | templates/inventory/tracking/reservation/list.html:56-62 | Actions column lacks the pinned trash-2 inline delete (eye/pencil/trash-2 MUST rule); delete exists only on the detail page. | Add `{% if obj.is_editable %}`-wrapped trash-2 POST beside cancel, mirroring crossdockorder/list.html. |
| M2 | Minor | [ ] open | templates/inventory/tracking/reservation/detail.html:56 | Inactive branch of "This claim" hardcodes "released — X no longer held"; consumed/cancelled rows mislabel themselves. | Render the real state: `{{ obj.get_status_display|lower }} — {{ obj.quantity|floatformat:"-2" }} no longer held`. |
| M3 | Minor | [ ] open | models/InventoryTrackingControl/InventoryReservations.py:120-128; StockStatuses.py:89-97 | `clean()` verifies tenancy of location/lot_serial but NOT item — non-form write paths (admin/seeder/future imports) could attach another workspace's Item. | Add the `item.tenant_id != self.tenant_id` guard alongside the existing checks in both models. |
| M4 | Minor | [ ] open | views/InventoryTrackingControl/InventoryReservations.py:90-100 | Delete TOCTOU: `is_editable` checked on one unlocked read, then crud_delete re-fetches unlocked — a concurrent consume() between the reads deletes history. | Wrap the guard+delete in transaction.atomic() with select_for_update() re-read, mirroring the model verbs. |
| M5 | Minor | [ ] open | management/commands/seed_inventory.py:_seed_tracking | Seeded reservation quantities (4+3 active) are not capped at the anchor spot's balance, unlike the status block's min(3, qty) cap — modest spots seed permanently negative availability. | Scale the three demo claims down to fit the anchor spot's ledger balance minus existing classifications; skip gracefully if no room. |
| M6 | Minor | [ ] open | models/InventoryTrackingControl/InventoryReservations.py:141-152 | `_advance` guards only ACTIONABLE_STATUSES, so release() on an already-released row re-writes resolved_at and writes a second audit entry (consume/cancel are terminal-guarded). | Also refuse when `obj.status == target` inside the locked re-read. |
| M7 | Minor | [ ] open | views/InventoryTrackingControl/StockLevels.py:143-155 | `_paginate` duplicates apps.core.crud.paginate verbatim (Paginator accepts plain lists) — dead duplication that will drift. | Delete the local copy; `from apps.core.crud import paginate`. |
| M8 | Minor | [ ] open | forms/InventoryTrackingControl/InventoryReservations.py:27 + views/StockLevels.py:97-98,137-138 | `reserved_by` is a form field whose value create silently overwrites with request.user; separately items/locations are fetched twice per stocklevels request (merge maps + dropdowns). | Drop reserved_by from Meta.fields (views own it on both paths); build dropdown lists from the maps already loaded. |
| M9 | Minor | [ ] open | models/InventoryTrackingControl/StockStatuses.py:Meta | StockStatus lacks the (tenant,item,location) mirror index that InventoryReservation got; three hot shapes probe exactly that prefix (detail siblings, reservation-form classification aggregate). | Add `models.Index(fields=["tenant","item","location"], name="inv_ss_tnt_item_loc_idx")` + migration. |

## Lane summary

| Lane | Result |
|------|--------|
| code-reviewer | 9 findings (C1, I1–I4 partially overlapping perf lanes, M5–M9) |
| performance-reviewer | 4 findings (I1 dup, I4, M7/M8 dup, M9) |
| security-reviewer | No Critical/Important; 3 minors (M3, I2-dup, M4) |
| frontend-reviewer | 3 findings (I5, M1, M2); context-var/badge/filter/pagination sweep clean |
| qa-smoke-tester | Executed during build (temp/smoke_56.py): all pages 200/302, IDOR 404s, verbs guarded, leak markers absent — PASS |

Fix rules for the fixer agent: work in ID order; **one file per git commit** (`git add 'file'; git commit -m '...'`,
PowerShell-safe, never push); never touch `apps/inventory/*/ReceivingPutaway/*`, `templates/inventory/receiving/*`
or `apps/procurement/tests/*` (concurrent session's WIP); after each model change run
`venv\Scripts\python.exe manage.py makemigrations inventory` (next free number) and after all fixes
`venv\Scripts\python.exe manage.py check` + rerun `temp/smoke_56.py` (PYTHONPATH='.') to prove green;
mark each finding `[x] fixed` or `[~] skipped — reason` in this file and commit the updated file last.
