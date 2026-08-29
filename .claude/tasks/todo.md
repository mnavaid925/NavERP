# Build Plan — Procurement 6.9 Catalog Management

Source of truth: `.claude/tasks/research-procurement-6.9.md` (research + frozen build
contract, committed 0a39a371). BASE = `2ab53bfe`. Migration claimed: **0012**
(0001–0011 exist; `makemigrations procurement --check` reported no pending changes at
claim time). Coexistence: parallel session is finishing 6.7/6.8 waves — builders touch
ONLY new `CatalogManagement` files; all shared-file edits, migrations and commits are
done by this session's solo Integrate.

## Models (new package `apps/procurement/models/CatalogManagement/`)
- [ ] `CatalogItems.py` — `CatalogItem` [PCI-]: source_type internal/supplier_product,
      item FK scm.Item (null when supplier), supplier FK core.Party, contract FK
      scm.SupplierContract, free-text part/name/description/manufacturer, uom/currency FKs,
      base_price q2, status machine draft→pending_approval→approved/rejected→blocked/archived,
      is_preferred/is_active flags, category_text, created_by; approve/reject/block actions.
- [ ] `Tiers.py` — `CatalogPriceTier`: catalog_item FK related_name="price_tiers",
      min_quantity/unit_price/discount_pct, valid_from/valid_until window check in clean(),
      contract FK, status draft→active→superseded/cancelled, approved_by/at;
      unique (tenant, catalog_item, min_quantity, valid_from).
- [ ] `PunchOutEndpoints.py` — `PunchOutEndpoint` [POE-]: party FK core.Party, name,
      protocol cxml/oci/manual_link, punchout_url, username, shared_secret WRITE-ONLY
      (excluded from edit form re-render), enabled, last_session_at editable=False, notes.
- [ ] `UploadBatches.py` — `CatalogUploadBatch` [CUB-]: party FK, file upload
      (csv/xls/xlsx/xml allowlist in clean()), status received→validated→published/rejected,
      rows_parsed/accepted/rejected editable=False + error_log, validate_and_stage()
      parses CSV rows into DRAFT/pending CatalogItems.

## Backend layers (mirror packages per entity)
- [ ] `forms/CatalogManagement/{CatalogItems,Tiers,PunchOutEndpoints,UploadBatches}.py`
      — ModelForms excluding tenant/number/derived/status-action stamps; secret write-only.
- [ ] `views/CatalogManagement/<Entity>.py` ×4 — @login_required, tenant-scoped CRUD +
      search/filters/pagination + POST action verbs (submit/approve/reject/block;
      tier approve/retire; endpoint test-stub; upload validate/stage), AuditLog rows.
- [ ] `urls/CatalogManagement/<Entity>.py` ×4 — `<entity>_list/_detail/_create/_update/_delete`
      + action routes; literal-before-pk ordering.

## Shared files (SOLO Integrate only — surgical Edits)
- [ ] Re-export blocks in models/forms/views `__init__.py`; urls/__init__ wiring.
- [ ] admin.py registrations ×4.
- [ ] seed_procurement.py `_seed_catalog(tenant)` block (idempotent per entity; needs
      seeded scm.Item/SupplierProfile else friendly skip).
- [ ] navigation.py LIVE_LINKS["6.9"]: Item Creation → catalog_item_list; Pricing & Tier
      → catalog_tier_list; Approval → catalog_item_list?status=pending_approval;
      Punch-out → punchout_endpoint_list; Supplier Hosting → catalog_upload_list.
- [ ] makemigrations 0012 → migrate → seed ×2 → manage.py check.

## Templates (`templates/procurement/catalogmanagement/<entity>/{list,detail,form}.html`)
- [ ] catalogitem (list w/ status+source filters, detail w/ approval panel + tier table,
      form), tier, punchoutendpoint, uploadbatch (+ error-log render on detail).
- [ ] Design system classes only (badge-green/red/amber/info/muted/slate); Actions column;
      GET filter forms; pagination; empty states.

## Verify & close
- [ ] Smoke: every new url renders 200/302 as admin_acme; content asserts; junk-param list;
      page-2; cross-tenant IDOR → 404 (admin_globex pk).
- [ ] Review wave (6 lanes) → `.claude/tasks/review-procurement-6.9.md`; code-fixer burns
      findings; test wave `test_catalogmgmt_{models,forms,views,security}.py` full suite green.
- [ ] SKILL.md (procurement) documents 6.9; README roadmap row; close-out review here.

---

## Close-out review - Procurement 6.9 Catalog Management (2026-08-26)

**Shipped:** CatalogItem [PCI-] / CatalogPriceTier / PunchOutEndpoint [POE-] /
CatalogUploadBatch [CUB-] as the governed buy-side layer over scm 4.2's SupplierCatalog
(L36). Full CRUD + lifecycle verbs per entity, tenant-scoped throughout, decision verbs
@tenant_admin_required (maker-checker), write-only punch-out secret (popped on edit +
core sensitive-fields redaction), upload staging under select_for_update with size/row caps
and formula-injection escaping, tier single-occupancy enforced in clean() AND approve().

**Sequence:** research (0a39a371) -> todo (b747549f) -> contract freeze (9a39c545e family)
-> 4 parallel full-stack lanes (28 files) -> solo integrate (re-exports/admin/seeder/
LIVE_LINKS/migration 0013; 0012 was the parallel session's pending alert-kind alter)
-> smoke ALL PASS -> six-lane review wave -> fixer burned C1+I1-I5+M1-M15 (M16 info-only
skipped; migration 0014 for related-name prefixes) -> 4 test-writer lanes (92 tests,
functions test_catalogmgmt_*) -> FULL unfiltered procurement suite EXITCODE=0 (~576 tests)
-> SKILL.md + README roadmap (9 of 19).

**Coexistence:** built alongside an active parallel session finishing 6.4/6.7/6.8 waves -
disjoint file sets held throughout; shared-file edits only in solo integrate; their
migration 0012 left untouched for them to commit.

**Lessons of record:** (1) PowerShell Add-Content writes CP1252 - one em-dash corrupted
admin.py UTF-8 until byte-patched; use proper file tools for app sources. (2) pytest's full
~300-migration in-memory schema build now dominates test time (~15 min/process); consider a
persistent template DB before the next module. (3) Two reviewers independently caught the
tier double-approve hole (C1) - model actions must re-validate invariants, never trust the
form-path clean().

---
# Sub-module 6.11 - Order Fulfillment & Tracking (Module 6: Procurement Management System, `procurement`) - plan from research-procurement-6.11.md  (2026-08-29)

App EXISTS (`apps/procurement/`, 6.1-6.10 built) -> this pass EXTENDS it. No settings/urls
include needed. Migration **0016 is CLAIMED** (a concurrent session holds 0015 for 6.10;
0015 is on disk untouched-by-us as `0015_purchaseorderchange_purchaseorderchangeline_and_more.py`).
Sub-module package folder: **`OrderFulfillment/`** in all four backend layers.
Template sub-module folder: **`orderfulfillment/`**. Test subslug: **`fulfillment`**.

**Spine re-verified by grep this session (L28) - every FK below targets a real class:**
`scm.PurchaseOrder` (PurchaseOrders.py:15) - `scm.PurchaseOrderLine` (:172, free-text
`item_description`/`sku_hint`/`uom_hint`, `received_quantity()`, `outstanding_quantity()`) -
`scm.Carrier` (Carriers.py:47) - `scm.Shipment` (Shipments.py:22, has `direction`,
`purchase_order`, `current_status_text`, `last_known_location`, `eta`, all editable=False) -
`core.OrgUnit` (OrgUnit.py:5) - `core.Tenant` - `procurement.ProcurementAlert`
(ProcurementAlerts.py:26, `kind="delivery"` already in KIND_CHOICES).
**`core.Item` does NOT exist** (only `scm.Item`, and PO lines carry no item FK) -> ASN lines
mirror the PO line's free text, no item FK anywhere in 6.11.

**Boundaries this pass must not cross (L36):**
- [ ] NEVER re-declare `scm.PurchaseOrder`/`PurchaseOrderLine` - FK them by string only.
- [ ] NEVER write `PurchaseOrderLine.quantity`/`unit_price`/`tax_rate_pct` or
      `PurchaseOrder.expected_date`/`status` - 6.10's `PurchaseOrderChange.apply()` owns spine
      mutation under a row lock.
- [ ] NEVER book a receipt / QC / stock movement / GRN line - that is 6.12. The hand-off hook is
      `AdvancedShipmentNotice.supplier_reference` -> `scm.GoodsReceiptNote.delivery_note_ref`.
- [ ] NEVER build a second freight-tracking log - `scm.Shipment` + `scm.TrackingEvent` (SCM 4.6)
      own milestones/ETA/POD. 6.11 gets a **nullable FK** to `scm.Shipment` and READS its
      projections; it never creates a Shipment and never appends a TrackingEvent.
- [ ] NEVER add a vendor login page (L32) - ASNs are staff-recorded this pass; `source` records
      provenance for the deferred EDI 856 intake.
- [ ] No new alert table - backorder/late escalation raises into `procurement.ProcurementAlert`.

## Models (3 tables + 1 child, in 3 entity files)

- [ ] **`AdvancedShipmentNotice`** [`ASN-`] (`TenantNumbered`) - the supplier-declared notice of
      what is in the box. Drivers: Bullet 1 ASN header/packing detail/validation/cancellation,
      Bullet 2 carrier+tracking+shipment link, Bullet 3 delivery confirmation + POD.
      - Order + identity: `purchase_order` FK `"scm.PurchaseOrder"` **PROTECT**
        `related_name="procurement_asns"`; `supplier_reference` CharField(64) (the vendor's own
        ASN/delivery-note number; driver: Oracle/SupplyOn duplicate-ASN rejection + the 6.12
        `delivery_note_ref` hand-off).
      - `STATUS_CHOICES` = `draft / submitted / in_transit / delivered / cancelled`
        (`editable=False`, default `draft`; moved ONLY by the four verbs).
        `OPEN_STATUSES = ("draft", "submitted", "in_transit")`,
        `IN_FLIGHT_STATUSES = ("submitted", "in_transit")`.
      - `SOURCE_CHOICES` = `portal / email / edi / manual` (default `manual`) - driver: the
        deferred EDI 856 / cXML intake needs a provenance column to write from day one.
      - Dates: `ship_date` DateField null/blank; `expected_delivery_date` DateField null/blank;
        `delivered_at` **DateTimeField** null/blank `editable=False` (Bullet 3's literal "exact
        date and time", stamped by the confirm verb - L22).
      - Freight: `carrier` FK `"scm.Carrier"` SET_NULL null/blank
        `related_name="procurement_asns"`; `carrier_name` CharField(120) blank (fallback for a
        supplier's own courier with no TMS profile); `tracking_number` CharField(64) blank;
        `shipment` FK `"scm.Shipment"` SET_NULL null/blank `related_name="procurement_asns"`
        (queryset limited to `tenant` + `direction="inbound"`).
      - Paperwork (driver: Oracle/GEP/NetSuite freight identifiers): `bill_of_lading_ref`
        CharField(64) blank, `container_ref` CharField(64) blank, `freight_terms` CharField(20)
        blank with `FREIGHT_TERMS_CHOICES` = `prepaid / collect / third_party /
        prepaid_and_charged`.
      - Packing cube (driver: the bullet's own wording - SAP handling units, SupplyOn packaging):
        `package_count` PositiveIntegerField null/blank, `pallet_count` PositiveIntegerField
        null/blank, `gross_weight_kg` Decimal(12,2) null/blank MinValue(0), `volume_cbm`
        Decimal(12,3) null/blank MinValue(0). Deliberately FLAT - no recursive pallet->carton tree.
      - POD block, all `editable=False`, written only by `asn_confirm_delivery` (driver:
        project44/FourKites POD capture, NetSuite receive-vs-take-ownership):
        `arrival_condition` CharField(10) blank with `CONDITION_CHOICES` =
        `good / damaged / partial / refused`; `pod_reference` CharField(64) blank;
        `received_signature_name` CharField(120) blank;
        `confirmed_by` FK user SET_NULL `related_name="procurement_asns_confirmed"`.
      - Audit/system, all `editable=False`: `created_by` FK user SET_NULL
        `related_name="procurement_asns_created"`, `submitted_at`, `cancelled_at`,
        `cancellation_reason` TextField blank. Plus editable `notes` TextField blank.
      - `Meta`: `ordering=["-created_at","-id"]`, `unique_together=("tenant","number")`,
        indexes `(tenant,status)`, `(tenant,expected_delivery_date)`, `(tenant,purchase_order)`
        with `name="prc_asn_*_idx"` (<=30 chars).
      - `clean()`: duplicate non-blank `supplier_reference` within the tenant (excluding
        `cancelled` and self) -> ValidationError; `expected_delivery_date` may not precede
        `ship_date`; `shipment` (when set) must be this tenant's and `direction="inbound"`.
      - **Derived, never stored:** `is_late`, `days_late` (vs `expected_delivery_date`),
        `tracking_status_text` (`shipment.current_status_text` else `carrier_name`/carrier),
        `eta_display` (`shipment.eta` else `expected_delivery_date`), `location_display`
        (`shipment.last_known_location`), `discrepancy_verdict` (`ok/short/over/mixed` folded
        from the lines), plus `status_css`/`condition_css` badge helpers.
      - **Form excludes:** `tenant`, `number`, `status`, `delivered_at`, `arrival_condition`,
        `pod_reference`, `received_signature_name`, `confirmed_by`, `created_by`, `submitted_at`,
        `cancelled_at`, `cancellation_reason`, `created_at`, `updated_at`. `purchase_order` is on
        the CREATE form only (popped on edit - changing it would orphan the line FKs).

- [ ] **`AsnLine`** (tenant-less child in the SAME file - the `PurchaseOrderChangeLine`
      precedent). Drivers: Bullet 1 line-matched-to-PO-line + lot/serial/expiry/origin,
      e2open order-vs-shipment mismatch.
      - `asn` FK CASCADE `related_name="lines"`; `po_line` FK `"scm.PurchaseOrderLine"`
        **PROTECT** `related_name="asn_lines"`.
      - Free-text mirror (PO lines have NO item FK): `item_description` CharField(255) blank
        (auto-copied from `po_line` when blank), `sku_hint` CharField(64) blank, `uom_hint`
        CharField(32) blank.
      - `quantity_shipped` Decimal(14,4) MinValue(0.0001).
      - `package_ref` CharField(64) blank (carton/pallet/LPN - SAP HU, Oracle LPN).
      - `lot_number` CharField(64) blank, `serial_number` CharField(64) blank, `expiry_date`
        DateField null/blank, `country_of_origin` CharField(64) blank - declared BEFORE arrival;
        **no FK to `scm.LotSerial`** (that row is created at receipt = 6.12).
      - `notes` CharField(255) blank. `Meta`: `ordering=["id"]`,
        `unique_together=("asn","po_line")` (one declaration per PO line per ASN).
      - `clean()`: `po_line.purchase_order_id` must equal `asn.purchase_order_id` (a crafted POST
        must not staple another order's line on); quantity > 0. Over-shipping beyond
        `po_line.outstanding_quantity()` is a **derived warning**, not a hard block (Oracle's
        accepted-with-warnings).
      - Derived per line: `outstanding_at_declare`, `variance` (`quantity_shipped -
        outstanding`), `variance_css`.
      - **Form excludes:** nothing extra - it is an inline formset; `asn` comes from the parent
        instance and `po_line`'s queryset is narrowed to `asn.purchase_order.lines`.

- [ ] **`DeliverySchedule`** [`DSC-`] (`TenantNumbered`) - the instalment commitment on ONE PO
      line. Drivers: Bullet 5 per-line schedule rows (Dynamics 365 delivery lines), buyer-vs-
      supplier columns (Coupa), split action, over-commitment guard, per-instalment ship-to.
      - `po_line` FK `"scm.PurchaseOrderLine"` **PROTECT**
        `related_name="procurement_delivery_schedules"`; `sequence` PositiveIntegerField
        default 1.
      - Buyer side: `scheduled_quantity` Decimal(14,4) MinValue(0.0001), `need_by_date` DateField.
        Supplier side (Coupa's four columns): `promised_quantity` Decimal(14,4) null/blank,
        `promised_date` DateField null/blank.
      - `STATUS_CHOICES` = `planned / confirmed / shipped / received / cancelled` (default
        `planned`). **Editable on the form** - unlike the ASN this ladder hangs no timestamps or
        stamps off itself, so it needs no verbs; document that reasoning in the model docstring.
      - `ship_to` FK `"core.OrgUnit"` SET_NULL null/blank
        `related_name="procurement_delivery_schedules"` (same target as `PurchaseOrder.ship_to`);
        `delivery_mode` CharField(16) blank with `MODE_CHOICES` = `standard / express / courier /
        freight / collection / dropship`.
      - `asn` FK `"procurement.AdvancedShipmentNotice"` SET_NULL null/blank
        `related_name="delivery_schedules"` - which consignment fulfilled this instalment.
      - `change_reason` CharField(255) blank, `notes` TextField blank, `created_by` FK user
        SET_NULL `editable=False` `related_name="procurement_delivery_schedules_created"`.
      - `Meta`: `ordering=["po_line_id","sequence","id"]`,
        `unique_together=(("tenant","number"), ("tenant","po_line","sequence"))`,
        indexes `(tenant,status)`, `(tenant,need_by_date)` named `prc_dsc_*_idx`.
      - `clean()`: sum of non-cancelled sibling `scheduled_quantity` + this row may NOT exceed
        `po_line.quantity` -> hard ValidationError (Coupa's red); a SHORT total is a derived
        warning on the board, never an error (Coupa's orange). `asn` (when set) must be this
        tenant's AND on the same `purchase_order` as `po_line`.
      - **Derived:** `slip_days` (`promised_date - need_by_date`), `remaining_quantity` and
        `coverage_pct` for the line, `is_late`, `status_css`.
      - **Form excludes:** `tenant`, `number`, `created_by`, `created_at`, `updated_at`.

- [ ] **`Backorder`** [`BKO-`] (`TenantNumbered`) - the recorded shortfall + new commitment.
      Drivers: Bullet 4 shortfall-with-a-reason, revised promise date + reschedule history,
      lifecycle, SourceDay risk buckets, alert escalation, prefilled-from-ASN creation.
      - `po_line` FK `"scm.PurchaseOrderLine"` **PROTECT** `related_name="procurement_backorders"`;
        `delivery_schedule` FK `"procurement.DeliverySchedule"` SET_NULL null/blank
        `related_name="backorders"` (which instalment slipped); `asn` FK
        `"procurement.AdvancedShipmentNotice"` SET_NULL null/blank `related_name="backorders"`
        (the short shipment that caused it).
      - `quantity_backordered` Decimal(14,4) MinValue(0.0001).
      - `REASON_CHOICES` = `out_of_stock / production_delay / allocation / material_shortage /
        supplier_capacity / logistics / other` (driver: SourceDay's PO-exception risk types);
        `reason_note` CharField(255) blank - **required when `reason == "other"`**.
      - `original_promise_date` DateField null/blank, `revised_promise_date` DateField
        null/blank, `reschedule_count` PositiveIntegerField default 0 `editable=False`.
      - `STATUS_CHOICES` = `open / rescheduled / fulfilled / cancelled` (`editable=False`,
        default `open`); `OPEN_STATUSES = ("open", "rescheduled")`. `closed_at` DateTimeField
        null/blank `editable=False`; `closure_note` CharField(255) blank `editable=False`.
      - `alert` FK `"procurement.ProcurementAlert"` SET_NULL null/blank `editable=False`
        `related_name="+"` - the raised `kind="delivery"` row (idempotent link).
      - `created_by` FK user SET_NULL `editable=False`
        `related_name="procurement_backorders_created"`; `notes` TextField blank.
      - `Meta`: `ordering=["-created_at","-id"]`, `unique_together=("tenant","number")`,
        indexes `(tenant,status)`, `(tenant,reason)`, `(tenant,revised_promise_date)` named
        `prc_bko_*_idx`.
      - `clean()`: `quantity_backordered` may not exceed `po_line.quantity`; `reason_note`
        required for `other`; `delivery_schedule`/`asn` (when set) must be this tenant's and
        reference the SAME purchase order as `po_line`.
      - **Derived:** `days_open`, `days_late`, `risk_bucket` (`past_due` / `at_risk` (revised
        date within 7 days) / `no_commitment` (no revised date, still open) / `on_track`),
        `status_css`, `risk_css`.
      - **Form excludes:** `tenant`, `number`, `status`, `reschedule_count`, `closed_at`,
        `closure_note`, `alert`, `created_by`, `created_at`, `updated_at`.

- [ ] **Two computed pages - ZERO new state** (the 6.10 `po_line_tracking` precedent):
      `inbound_tracking` (Bullet 2 board) and `delivery_confirmation` (Bullet 3 arrivals queue).
      No models, no forms of their own; the confirmation queue POSTs to the ASN's existing
      `asn_confirm_delivery` verb rather than defining a second one.

## Backend (apps/procurement/{models,forms,views,urls}/OrderFulfillment/)

Absolute imports only (`from apps.procurement.models._base import *`, `from
apps.procurement.views._common import *`). New folders need their own `__init__.py` in each of
the four layers (each gets its own commit, even when empty of logic).

### models/OrderFulfillment/
- [ ] `__init__.py` (sub-package re-exports)
- [ ] `AdvancedShipmentNotice.py` - `AdvancedShipmentNotice` + `AsnLine` (one entity file owns
      its children), the four verb helper methods (`submit()`, `mark_in_transit()`,
      `confirm_delivery(user, ...)`, `cancel(user, reason)`) with the guards re-checked INSIDE
      the method (never trusting the form path - the 6.9 C1 lesson)
- [ ] `DeliverySchedule.py` - `DeliverySchedule` + a module-level `split_po_line(...)` helper
      (creates K evenly-spaced rows; last row absorbs the rounding remainder)
- [ ] `Backorder.py` - `Backorder` + `reschedule()/fulfil()/cancel()/raise_alert()` methods;
      `raise_alert()` is idempotent (returns the existing open alert instead of a second row)
      and builds `link_url` from `reverse("procurement:backorder_detail", ...)` - never a
      hardcoded path (ProcurementAlert.clean() rejects anything not a single-slash internal path)

### forms/OrderFulfillment/
- [ ] `__init__.py`
- [ ] `AdvancedShipmentNotice.py` - `AdvancedShipmentNoticeForm` (TenantModelForm; `purchase_order`
      queryset = tenant orders in `PurchaseOrder.RECEIVABLE_STATUSES`, popped on edit; `carrier`
      + `shipment` querysets tenant-scoped, `shipment` also `direction="inbound"`),
      `AsnLineForm` + `AsnLineFormSet` (`inlineformset_factory`, `po_line` queryset narrowed to
      `asn.purchase_order.lines`), and `AsnDeliveryConfirmForm` (plain `forms.Form`:
      `delivered_at`, `arrival_condition`, `pod_reference`, `received_signature_name`) plus
      `AsnCancelForm` (reason required)
- [ ] `DeliverySchedule.py` - `DeliveryScheduleForm` (tenant-scoped `po_line`/`ship_to`/`asn`
      querysets) + `DeliveryScheduleSplitForm` (`po_line`, `instalments` 2-12, `first_date`,
      `interval_days` 1-365)
- [ ] `Backorder.py` - `BackorderForm` (tenant-scoped `po_line`/`delivery_schedule`/`asn`;
      accepts `?po_line=`/`?asn=`/`?quantity=` GET prefill from the ASN detail page) +
      `BackorderRescheduleForm` (`revised_promise_date` required, `reason_note` required)

### views/OrderFulfillment/ (function-based, `@login_required`, tenant-scoped on EVERY query)
- [ ] `__init__.py`
- [ ] `AdvancedShipmentNotice.py` - `asn_list` (search `number`/`supplier_reference`/
      `tracking_number`/`purchase_order__number`; filters `status`, `source`, `carrier`, `po`,
      `late`; pagination; `select_related("purchase_order","carrier","shipment")`),
      `asn_detail` (lines + variance + discrepancy verdict + confirm/cancel forms + the
      "create backorder for the shortfall" prefilled link), `asn_create` (header only),
      `asn_edit` (header + `AsnLineFormSet`; blocked once `delivered`/`cancelled`),
      `asn_delete` (POST-only, **drafts only**, `@tenant_admin_required`), and the four verbs
      `asn_submit`, `asn_mark_in_transit`, `asn_confirm_delivery`, `asn_cancel` - all
      `@require_POST`, all under `transaction.atomic()` + `select_for_update()` so a
      double-submit cannot re-stamp `delivered_at`/`confirmed_by`
- [ ] `DeliverySchedule.py` - `deliveryschedule_list` (search `number`/`po_line__item_description`/
      `po_line__purchase_order__number`; filters `status`, `mode`, `po`, `late`; coverage figure
      per row; pagination), `deliveryschedule_detail`, `_create`, `_edit`, `_delete` (POST-only),
      plus `deliveryschedule_split` (GET renders `split.html`, POST creates K rows inside
      `transaction.atomic()` with `select_for_update()` over the line's existing rows, refuses
      when the line is already fully covered)
- [ ] `Backorder.py` - `backorder_list` (search `number`/`reason_note`/
      `po_line__item_description`/`po_line__purchase_order__number`; filters `status`, `reason`,
      **`risk`** applied as ORM date arithmetic BEFORE pagination - never a Python-side filter, or
      the page counts lie; pagination), `backorder_detail`, `_create`, `_edit`, `_delete`
      (POST-only, `@tenant_admin_required`), verbs `backorder_reschedule`, `backorder_fulfil`,
      `backorder_cancel`, `backorder_raise_alert` (all `@require_POST` + atomic + locked)
- [ ] `InboundTracking.py` - `inbound_tracking` computed board (no writes). Context keys pinned:
      `rows`, `page_obj`, `status_choices`, `carriers`, `stats`
      (`in_flight`/`late`/`unlinked`/`arriving_today`), and the echoed GET params.
- [ ] `DeliveryConfirmation.py` - `delivery_confirmation` arrivals queue. Buckets via `?due=`
      (`today` / `overdue` / `awaiting` / `confirmed`). Context keys pinned: `rows`, `page_obj`,
      `bucket`, `condition_choices`, `stats` (`due_today`/`overdue`/`awaiting`/`confirmed_7d`).
      Its inline confirm form POSTs to `procurement:asn_confirm_delivery`.
- [ ] `write_audit_log` on every hand-rolled save path (the verbs) - `crud_*` helpers already
      call it for list/create/edit/delete.

### urls/OrderFulfillment/ (literal routes BEFORE `<int:pk>`, first-match-wins)
- [ ] `__init__.py` concatenating the five modules' `urlpatterns`
- [ ] `AdvancedShipmentNotice.py` - `asn/` -> `asn_list`; `asn/add/` -> `asn_create`;
      `asn/<int:pk>/` -> `asn_detail`; `.../edit/` `.../delete/` `.../submit/`
      `.../in-transit/` `.../confirm-delivery/` `.../cancel/`
- [ ] `DeliverySchedule.py` - `delivery-schedules/` `-/add/` `-/split/` (literal, BEFORE pk)
      `-/<int:pk>/` `-/<int:pk>/edit/` `-/<int:pk>/delete/`
- [ ] `Backorder.py` - `backorders/` `-/add/` `-/<int:pk>/` `-/<int:pk>/edit/`
      `-/<int:pk>/delete/` `-/<int:pk>/reschedule/` `-/<int:pk>/fulfil/` `-/<int:pk>/cancel/`
      `-/<int:pk>/raise-alert/`
- [ ] `InboundTracking.py` - `inbound-tracking/` -> `inbound_tracking`
- [ ] `DeliveryConfirmation.py` - `delivery-confirmation/` -> `delivery_confirmation`
- [ ] Collision check: the five new first segments (`asn/`, `delivery-schedules/`,
      `backorders/`, `inbound-tracking/`, `delivery-confirmation/`) are distinct from every
      existing procurement segment and the app still has no greedy `<str:...>` route.

### Shared files - SOLO integrate step only, surgical `Edit` (a concurrent session is in this tree)
- [ ] `models/__init__.py` - re-export `AdvancedShipmentNotice, AsnLine, DeliverySchedule,
      Backorder` (+ `split_po_line`) and add them to `__all__`
- [ ] `forms/__init__.py` - re-export the 8 form/formset names + `__all__`
- [ ] `views/__init__.py` - re-export every new view function (missing one = `AttributeError`
      at URLconf import, not at request time)
- [ ] `urls/__init__.py` - `from .OrderFulfillment import urlpatterns as _of_orderfulfillment`
      and splat it LAST in the list; extend the module docstring's segment inventory
- [ ] `admin.py` - register `AdvancedShipmentNotice` (with an `AsnLine` inline),
      `DeliverySchedule`, `Backorder` (`list_display`/`list_filter`/`search_fields`/
      `readonly_fields` for the editable=False stamps)
- [ ] `management/commands/seed_procurement.py` - add `self._seed_order_fulfillment(tenant)`
      after `self._seed_po_management(tenant)` and the method itself: reuse an existing seeded
      `scm.PurchaseOrder` in a RECEIVABLE status (friendly skip + return when none exists),
      then idempotently create (a) one `submitted` ASN with 2 `AsnLine`s (one short-shipped) -
      keyed on `supplier_reference`, (b) one `delivered` ASN with POD for the confirmation
      queue, (c) 3 `DeliverySchedule` instalments on one PO line keyed on
      `(po_line, sequence)`, (d) one open `Backorder` with a revised date and one past-due
      `Backorder` keyed on `(po_line, reason, quantity_backordered)`. `get_or_create` /
      existence-check only - NEVER bare `.create()` on a numbered model.
- [ ] **`makemigrations procurement` LAST** -> must produce exactly
      `0016_advancedshipmentnotice_asnline_deliveryschedule_backorder...` (rename if Django
      picks a different suffix; the NUMBER 0016 is the claim). Do not touch 0015.

## Wire-up
- [ ] `apps/core/navigation.py` - ONE new `LIVE_LINKS["6.11"]` entry, bullet text copied
      EXACTLY from NavERP.md lines 1062-1066, each pointing at a STAFF page (L32):
      - `"Advanced Shipping Notice (ASN)": "procurement:asn_list"`
      - `"Real-time Freight Tracking":     "procurement:inbound_tracking"`
      - `"Delivery Confirmation":          "procurement:delivery_confirmation"`
      - `"Backorder Management":           "procurement:backorder_list"`
      - `"Split Delivery Management":      "procurement:deliveryschedule_list"`
      Insert AFTER the `"6.10"` dict, with a comment recording the 4.6-owns-freight-tracking
      decision (why "Real-time Freight Tracking" is a board over ASNs joined to `scm.Shipment`
      rather than a new tracking table).
- [ ] `config/settings.py` / `config/urls.py` - **NO CHANGE** (`procurement` is already installed
      and included; this is an existing app).

## Templates (templates/procurement/orderfulfillment/)
Every list page: filter bar reflecting `request.GET` (string fields `==` compare, FK/pk via
`|stringformat:"d"` - never `|slugify`), an Actions column (view / edit / delete-POST with
`{% csrf_token %}` + `onclick="return confirm(...)"`), pagination guarded by
`{% if page_obj.has_previous %}` / `has_next` (L9), and an empty state. Badges use ONLY
`badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate` (L33 - the
`-success`/`-danger` names do not exist in theme.css) with a `{% else %}`
`{{ obj.get_*_display }}` fallback.
- [ ] `asn/list.html` - filters: q, status, source, carrier, po, late; columns number / PO /
      supplier ref / carrier+tracking / ship + expected date / lines / status badge
- [ ] `asn/detail.html` - header cube + packing panel, line table with per-line
      shipped-vs-outstanding variance badges, the discrepancy verdict, tracking panel (linked
      `scm.Shipment` status/ETA/last-known-location with the ASN's own carrier as fallback),
      Actions sidebar (Edit / Submit / Mark in transit / Confirm delivery form / Cancel form /
      Delete for drafts / Back to list) each gated on the current status, and the
      "Record backorder for the shortfall" prefilled link
- [ ] `asn/form.html` - header form; on edit also renders `AsnLineFormSet` and shows the PO
      read-only
- [ ] `deliveryschedule/list.html` - filters: q, status, mode, po, late; columns PO line /
      seq / scheduled qty + need-by / promised qty + promised date / slip days / coverage /
      status; "Split a PO line" button
- [ ] `deliveryschedule/detail.html` - instalment detail + sibling instalments for the same PO
      line with running total / remaining / coverage warning + Actions sidebar
- [ ] `deliveryschedule/form.html`
- [ ] `deliveryschedule/split.html` - the split action page (entity-folder secondary action)
- [ ] `backorder/list.html` - filters: q, status, reason, **risk** (at-risk / past-due /
      no-commitment); columns number / PO line / qty / reason / original vs revised promise /
      reschedules / days open / status + risk badges
- [ ] `backorder/detail.html` - promise-date history block, Actions sidebar (Reschedule form /
      Fulfil / Cancel / Raise alert / Edit / Delete / Back), linked alert panel when raised
- [ ] `backorder/form.html`
- [ ] `inbound_tracking.html` - standalone board at the sub-module root (the
      `purchaseordermanagement/linetracking.html` precedent): stat tiles + filter bar +
      in-flight rows with latest milestone / ETA / last known location / days-late flag
- [ ] `delivery_confirmation.html` - standalone arrivals queue: due-today / overdue / awaiting
      / confirmed-7d buckets + the one-click confirm form posting to `asn_confirm_delivery`

## Verify
- [ ] `makemigrations procurement` (0016) then `migrate`
- [ ] `seed_procurement` run TWICE - second run creates nothing new and does not crash
- [ ] `manage.py check` clean
- [ ] `temp/` smoke script as **`admin_acme` / `password`**: every new `procurement:*` url
      renders 200/302; content assertions (page titles, a seeded ASN number `ASN-`, a `DSC-`
      row, a `BKO-` row); no `{#` or `{% comment` leaking into the HTML; junk filter params
      (`?status=nope&risk=zzz&po=abc`) still 200; `?page=2` guarded; cross-tenant IDOR - a
      `admin_globex`-owned ASN/schedule/backorder pk returns **404** on detail/edit/delete and
      on every verb; verbs reject GET (405) and a non-admin user on the admin-gated deletes
- [ ] Sidebar shows 6.11 as Live with all five bullets resolving (no `NoReverseMatch`)

## Close-out (the mandatory Module Creation Sequence, phases 4-7)
- [ ] Phase 4 review wave - `.claude/workflows/module-review.js` with the six lanes in PARALLEL
      (code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester,
      security-reviewer) -> write findings to `.claude/tasks/review-procurement-6.11.md` and
      commit that file; re-run any lane reporting NO RESULT
- [ ] Phase 5 `code-fixer` agent burns the findings down in ID order, one commit per file; no
      finding left `[ ] open`
- [ ] Phase 6 test wave - `.claude/workflows/module-tests.js` with `subslug: 'fulfillment'` ->
      `test_fulfillment_{models,forms,views,security}.py`, functions `test_fulfillment_*`,
      final run is the FULL unfiltered procurement suite (L47)
- [ ] Phase 7 - update `.claude/skills/procurement/SKILL.md` with the 6.11 models / routes /
      templates / seeder rows / LIVE_LINKS block; mark 6.11 complete in `README.md` (11 of 19)
- [ ] Mark each phase in `build_state.py`; append a Close-out review section here
- [ ] One file per commit throughout, PowerShell `;` separators, never `git push`

## Later passes / deferred (carried from research - nothing lost)
- **6.12 Goods Receipt & Inspection:** GRN created FROM a confirmed ASN with pre-populated
  lines, receipt tolerances, QC checklists, quarantine, lot/serial capture AT receipt,
  discrepancy reports with photos, RTV, barcoding/scanning, inventory posting, receipt reversal.
  Hook left in place: `AdvancedShipmentNotice.supplier_reference` ->
  `GoodsReceiptNote.delivery_note_ref`, and a `receipt_booked` ASN state is a one-line addition.
- **6.10 PO Management (concurrent):** PO generation, dispatch/acknowledgement, change orders,
  cancellation/close-out, per-line delivery tracking board.
- **6.16 Supplier Performance:** on-time-delivery KPI + scorecards fed by confirmed arrivals
  (`scm.SupplierScorecard` already recomputes from signals - 6.11 only makes its data readable).
- **SCM 4.6 TMS:** freight invoice audit, carrier rate cards, load/route planning, TrackingEvent
  entry and POD on the movement itself. **SCM 4.4 WMS:** dock/yard appointment scheduling
  (`scm.YardVisit`). **Inventory 5.x:** barcode/shipping-label generation (`inventory.BarcodeLabel`).
- **Deferred integrations:** EDI 856 / cXML ASN intake and supplier self-filing (the `source`
  column ships now, the transport does not); live carrier-API polling / predictive ETA;
  auto-creating a `scm.Shipment` on ASN submit (FK is selected, never auto-created); in-transit
  inventory / ownership accounting (touches stock + ledger, L29); multi-PO consolidated inbound
  shipment (one ASN per PO this pass; `scm.Load` is the consolidation concept if ever needed);
  landed-cost allocation across delivery lines (`scm.LandedCostVoucher`, 4.18); blanket-order
  call-offs / scheduling agreements (the spine has no blanket order); substitute-item offers on
  a backorder (PO lines carry no item FK); outbound email/SMS delay notifications (the
  `ProcurementAlert` row is the in-app notification); vendor portal self-filing of ASNs (6.4).

## Review notes
(filled in at close-out)
