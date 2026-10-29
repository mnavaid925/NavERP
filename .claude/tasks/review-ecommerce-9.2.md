# Review Findings — Sub-module 9.2: Inventory & Stock Management (Module 9 eCommerce, `ecommerce`)

- **Changeset under review:** `f78cf6de0a0efe5cffe7089328ce2e10964cf83b...HEAD`
- **Date:** 2026-10-29
- **Phase:** Phase 4 Review (6 serial review passes completed: code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer)

---

## Executive Summary

- **Critical:** 0
- **Important:** 7
- **Minor:** 8
- **Total Unique Findings:** 15

---

## Critical
*None.*

---

## Important

- [x] **I1**: Open redirect hardening in `channelinventorysync_trigger` view: `next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")` should be validated using `django.utils.http.url_has_allowed_host_and_scheme` to prevent arbitrary open redirects (`apps/ecommerce/views/InventoryStock/ChannelInventorySyncs.py:126`). Fixed in commit `929a5fce`.
- [x] **I2**: N+1 query prevention in `inventory_operations`: `recent_syncs` accesses `sync.variant.product.name` in `templates/ecommerce/inventorystock/overview.html:228`, but only selects `variant` and `fulfillment_center`. Add `select_related("variant__product", "fulfillment_center")` in `apps/ecommerce/views/InventoryStock/Operations.py:32`. Fixed in commit `b148ec79`.
- [x] **I3**: N+1 query prevention in `channelinventorysync_detail`: template iterates `variant.inventory_allocations.all` and accesses `alloc.fulfillment_center.name`, triggering an extra query per allocation. Preload `allocations` in the view with `.select_related("fulfillment_center")` and pass to context (`apps/ecommerce/views/InventoryStock/ChannelInventorySyncs.py:64`). Fixed in commits `929a5fce` & `eebb0ae3`.
- [x] **I4**: Guard `adjustment_quantity` in `inventoryallocation_adjust` against reducing physical on-hand to negative numbers: if `allocation.quantity_on_hand + adj_qty < 0`, raise form validation error to maintain physical inventory validity (`apps/ecommerce/views/InventoryStock/InventoryAllocations.py:165`). Fixed in commit `57547404`.
- [x] **I5**: In `inventoryallocation_create`, allow pre-selecting `product` when `?variant=pk` is provided in URL parameters so cross-navigation from variant list seamlessly sets both variant and product in `InventoryAllocationForm` (`apps/ecommerce/views/InventoryStock/InventoryAllocations.py:84`). Fixed in commit `57547404`.
- [x] **I6**: Add explicit `aria-label` attributes to all icon-only action buttons across all 9.2 templates for WCAG accessibility compliance (`fulfillmentcenter/list.html`, `inventoryallocation/list.html`, `backorderpolicy/list.html`, `channelinventorysync/list.html`, `overview.html`). Fixed in commits `2b77d23e`, `fe5aa4d1`, `fcca65ee`, `20756581`, `f5624b1d`.
- [x] **I7**: In `BackorderPolicyForm`, add non-negative validation for `max_backorder_quantity` in `clean()` so negative numbers cannot be submitted (`apps/ecommerce/forms/InventoryStock/BackorderPolicies.py:38`). Fixed in commit `91465b58`.

---

## Minor

- [x] **M1**: In `FulfillmentCenterForm`, add `help_text` to `priority` clarifying that priority 1 is highest for automatic order routing (`apps/ecommerce/forms/InventoryStock/FulfillmentCenters.py:33`). Fixed in commit `07d0bd2e`.
- [x] **M2**: In `InventoryAllocationForm`, restrict `variant` select options in `__init__` with `.select_related("product")` to prevent query amplification when rendering variant choices (`apps/ecommerce/forms/InventoryStock/InventoryAllocations.py:44`). Fixed in commit `be808335`.
- [x] **M3**: In `BackorderPolicyForm`, optimize `variant` queryset in `__init__` with `.select_related("product")` (`apps/ecommerce/forms/InventoryStock/BackorderPolicies.py:35`). Fixed in commit `91465b58`.
- [x] **M4**: In `ChannelInventorySyncForm`, optimize `variant` queryset in `__init__` with `.select_related("product")` (`apps/ecommerce/forms/InventoryStock/ChannelInventorySyncs.py:37`). Fixed in commit `7a4c2776`.
- [x] **M5**: In `overview.html`, display human-readable time format for `daily_cutoff_time` using `|time:"H:i"` filter (`templates/ecommerce/inventorystock/overview.html:190`). Fixed in commit `2b77d23e`.
- [x] **M6**: In `channelinventorysync/detail.html`, add empty state message for when `variant.inventory_allocations` has no entries (`templates/ecommerce/inventorystock/channelinventorysync/detail.html:148`). Fixed in commit `eebb0ae3`.
- [x] **M7**: In `fulfillmentcenter/detail.html`, display formatted cutoff time using `{{ center.daily_cutoff_time|time:"H:i"|default:"No cutoff set" }}` (`templates/ecommerce/inventorystock/fulfillmentcenter/detail.html:61`). Fixed in commit `d8e0a895`.
- [x] **M8**: In `inventoryallocation/detail.html`, display formatted last counted timestamp with localized standard date format (`templates/ecommerce/inventorystock/inventoryallocation/detail.html:89`). Fixed in commit `2cf16736`.
