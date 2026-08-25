# Review — inventory 5.16 Alerts & Notifications (2026-08-25)

Two-lane wave (backend/security/performance + frontend/conventions), read-only,
scoped to the 5.16 changeset. Findings burned down inline the same session.

## Lane A — backend / security / performance

| ID | Sev | Finding | Status |
|----|-----|---------|--------|
| A1 | Important | `NotificationDelivery` used in seed flush blocks but never imported → `--flush` NameError | [x] fixed (import added) |
| A2 | Important | expiry/PO/shipment loops rebuilt identical querysets per rule of same type | [x] fixed (hoisted above rule loop, stock-block pattern) |
| A3 | Minor | overstock message recomputed `profile.on_hand` after `quantity_utilisation` | [~] skipped-as-designed — bounded by bin count; second aggregate fires only per BREACHING bin |
| A4 | Minor | `overstock_pct` validator admitted 1000 but decimal(5,2) holds ≤999.99 | [x] fixed (cap 999.99, migration 0021) |
| A5 | Minor | zero-move item×location pairs skipped silently by stock watches | [x] fixed (intentional-skip comment at call site; no history ≠ zero, honesty rule) |
| A6 | Minor | rule detail rendered unbounded alert history | [x] fixed (view slices SQL-side `[:50]`) |
| A7 | Minor | Workflow Triggers lens hid shipment_delayed alerts behind po_approval param | [x] fixed (bare inbox link — catch-all highlight, all trigger types visible) |
| A8 | Minor | ack/resolved_by FKs editable while their _at stamps were not | [x] fixed (editable=False, migration 0021) |

## Lane B — templates / conventions

Verified clean: badge audit (colour-named only), filter bars reflect request.GET,
pagination partials + empty-states everywhere, csrf_token on every POST form,
confirm() on destructive verbs, breadcrumbs/stat-grid markup vs rfidtag sibling,
icon names all have repo precedent, related_name usage correct, overview card hrefs valid.

| ID | Sev | Finding | Status |
|----|-----|---------|--------|
| B1 | Minor | `{% if x != None %}` style vs house `is not None` | [x] fixed (list + detail) |
| B2 | Minor | duplicate crumb links on alert detail | [x] fixed (middle crumb span) |
| B3 | Minor | resolve lacked confirm(); ack inconsistent with list page | [x] fixed (confirm on resolve + detail ack) |
| B4 | Minor | lot branch printed bare `( )` when alert's item was deleted | [x] fixed (guarded) |

## Test-wave findings (found by the tests themselves)

| ID | Sev | Finding | Status |
|----|-----|---------|--------|
| T1 | Important | `_normalized_recipients()` list stored as repr string via CharField | [x] fixed (`",".join(...)` in save()) |
| T2 | Important | views referenced `ValidationError` without importing it → NameError on triage-refusal paths | [x] fixed (import added) |

Result: 0 critical · 4 important · 10 minor — none left open.
