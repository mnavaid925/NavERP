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

---
# Sub-module 6.12 - Goods Receipt & Inspection (Module 6: Procurement Management System, `procurement`) - plan from research-procurement-6.12.md  (2026-08-30)

App EXISTS (`apps/procurement/`, 6.1-6.11 built) -> this pass EXTENDS it. **No `config/settings.py` /
`config/urls.py` change** (procurement is already installed and included).
Sub-module package folder: **`GoodsReceiptInspection/`** in all four backend layers.
Template sub-module folder: **`goodsreceiptinspection/`**. Test subslug: **`receipt`**.
Migration **0017 is CLAIMED** and generated **LAST** (0016 is 6.11's, already on disk as
`0016_advancedshipmentnotice_asnline_deliveryschedule_and_more.py` - do not touch it).
Number prefixes **`RDS`** and **`RTV`** re-verified free across `apps/` this session.

## THE HEADLINE - 6 of the 10 NavERP.md bullets are ALREADY BUILT (L36: map, do not rebuild)

This sub-module is mostly an **ownership map**. Only 4 bullets need new procurement tables/pages;
the other 6 point at pages that exist today. Every one of the "already built" claims below was
re-verified by grep this session:

| NavERP.md bullet (line 1069-1078) | Verdict | Where it already lives |
|---|---|---|
| Goods Receipt Note (GRN) Creation | NEW computed page | `scm.GoodsReceiptNote`/`GoodsReceiptLine` exist; 6.12 adds the ASN->GRN booking desk |
| Receipt Tolerances | **NEW TABLE** | nothing in the repo has a quantity tolerance |
| Quality Inspection Checklists | MAP | `inventory.QcChecklist`/`QcChecklistItem` (`QcChecklists.py:24,72`) |
| Quarantine & Inspection Hold | MAP | `inventory.QuarantineOrder` (`QuarantineOrders.py:48`) |
| Lot, Batch & Serial Capture | MAP | `scm.LotSerial` (`LotSerials.py:5`) |
| Discrepancy Reporting | **NEW TABLE** | nothing anchors a finding to a GRN line |
| Return to Vendor (RTV) Processing | **NEW TABLE** | genuinely absent - see the RTV note below |
| Item Tagging & Barcoding | MAP | `inventory.BarcodeLabel` (`BarcodeLabels.py:17`) + scan console |
| Inventory Posting | MAP | `_post_grn_receipt` (`apps/scm/views/_helpers.py:299`) |
| Receipt Reversal & Audit Trail | MAP + NEW page | `_reverse_grn_receipt` (`_helpers.py:335`) + a computed trail |

**Spine re-verified by `^class` grep this session (L28) - every FK below targets a real class:**
`scm.GoodsReceiptNote` (`ProcurementManagement/GoodsReceiptNotes.py:15`, `[GRN-]`,
`delivery_note_ref`, `status` draft/received/cancelled, `PRICE_TOLERANCE_PCT = Decimal("2")`) -
`scm.GoodsReceiptLine` (`:166`; `quantity_received`, `quantity_rejected`, `rejection_reason`;
**no item FK, no lot field, no tenant column** - scoped through the header) -
`scm.PurchaseOrder`/`PurchaseOrderLine` (`PurchaseOrders.py:15,172`; free-text
`item_description`/`sku_hint`/`uom_hint`; `received_by_line()`, `received_quantity()`,
`outstanding_quantity()`) - `scm.NonConformance` (`NonConformances.py:28`) -
`scm.QualityInspection` (`QualityInspections.py:62`) - `scm.LotSerial` (`LotSerials.py:5`,
`unique_together = ("tenant","item","number")`) - `scm.Item` (`Items.py:73`, has `sku` +
`category`) - `scm.ItemCategory` (`Items.py:34`) - `inventory.QuarantineOrder`
(`QuarantineOrders.py:48`) - `inventory.QcRoutingRule` + `resolve_qc_routing()`
(`QcRoutingRules.py:24,89`) - `core.Party` (`Party.py:5`) - `core.Tenant` (`Tenant.py:5`) -
`core.AuditLog` (`AuditLog.py:5`).
**`apps/quality` does NOT exist** (`apps/*/apps.py` = core accounts tenants dashboard crm
accounting hrm scm inventory procurement). **`core.Item` does NOT exist** - free-text mirrors only.

## Boundaries this pass must not cross (L36 - encode these in the model docstrings)

- [ ] **NEVER re-declare or add a field to** `scm.GoodsReceiptNote` / `GoodsReceiptLine` /
      `QualityInspection` / `NonConformance` / `LotSerial`, or `inventory.QuarantineOrder` /
      `QcChecklist` / `QcRoutingRule`. 6.12 EXTENDS them **by FK, by string**, nothing else.
- [ ] **NEVER post a `StockMove` and NEVER post a `JournalEntry`.** `_post_grn_receipt`
      (`apps/scm/views/_helpers.py:299`, line 319 `qty = line.quantity_received or ZERO`) posts
      **only the RECEIVED quantity** - a quantity rejected at the dock never entered the ledger
      and has nothing to remove. Stock that failed QC *after* acceptance is removed by
      `inventory.QuarantineOrder.scrap()` or `scm:stockadjustment`. `apps/accounting` owns the
      ledger (L29) and `accounting.Bill` has no `kind` for a vendor credit (already flagged to
      Modules 2/6 in `scm.WarrantyClaim`'s docstring). **Write this reasoning into
      `ReturnToVendor`'s docstring and onto the RTV detail page** so a reviewer does not "fix" it.
- [ ] **NEVER open a third quality register.** SCM 4.9 owns engineering/metrology
      (`InspectionPlan`->`QualityInspection`->`NonConformance`), inventory 5.15 owns the
      warehouse floor (`QcChecklist`, `QcRoutingRule`, `QuarantineOrder`, `DefectReport`).
      6.12 owns only the **commercial** consequence of a bad receipt (discrepancy claim + RTV).
- [ ] **NEVER block or replace `scm:goodsreceipt_receive`.** The tolerance policy is
      **ADVISORY** this pass: it colours the console, drives the exceptions board and pre-fills a
      discrepancy. Hard-blocking is an SCM change to negotiate later.
- [ ] **NEVER add a vendor login page** (L32). `vendor_notified_on` / `vendor_reference` record
      that we told the supplier; the outbound transport is integration/later.
- [ ] Writing a **DRAFT** `scm.GoodsReceiptNote` from the console **is allowed** and is the 6.1
      precedent (Quick Requisition Entry writes into `scm.PurchaseRequisition` - see
      `apps/procurement/models/_base.py:11-17`). The **stock effect** stays SCM's admin-gated
      `scm:goodsreceipt_receive`. One writer for the ledger.

## Models (3 tables + 1 child, in 3 entity files - from research, scope frozen)

- [ ] **`ReceiptTolerancePolicy`** (`TenantOwned`, **NO number prefix** - the `QcRoutingRule` /
      `ApprovalRoutingRule` / `EscalationPolicy` rule-master precedent).
      File `models/GoodsReceiptInspection/ReceiptTolerances.py`.
      Drivers: SAP under/over-delivery tolerance + unlimited-overdelivery flag; Oracle receiving
      parameters (over-receipt tolerance, days early/late receipt allowed, **action per
      tolerance**); Ariba tolerances by quantity/percentage/value; Ivalua/Precoro tolerance limits.
      - Identity + scope: `name` CharField(100); `item` FK `"scm.Item"` CASCADE null/blank
        `related_name="procurement_receipt_tolerances"`; `category` FK `"scm.ItemCategory"`
        CASCADE null/blank same related_name; `vendor` FK `"core.Party"` SET_NULL null/blank same
        related_name (blank = any vendor).
      - Quantity band (driver: Ariba's "percentage OR absolute quantity"): `over_receipt_pct`
        Decimal(6,2) null/blank MinValue(0); `under_receipt_pct` Decimal(6,2) null/blank
        MinValue(0)+MaxValue(100); `over_receipt_qty` Decimal(14,4) null/blank MinValue(0)
        (absolute alternative - when both are set the **more restrictive** wins; document it).
      - `allow_unlimited_over_receipt` BooleanField default False (driver: SAP's escape flag -
        when True the two over-* fields are ignored; say so in `help_text` AND in `clean()`).
      - Date band (driver: Oracle "days early/late receipt allowed"): `early_receipt_days`
        PositiveIntegerField null/blank; `late_receipt_days` PositiveIntegerField null/blank -
        compared against the PO line's expected/promised date, never stored.
      - `ACTION_CHOICES` = `none | warn | block_flag`, `action` CharField(11) default `warn`
        (driver: Oracle's explicit per-tolerance action; `block_flag` **flags, it does not
        block** - the docstring must say why).
      - `price_variance_pct` Decimal(6,2) null/blank - **advisory mirror** of the hardcoded
        `GoodsReceiptNote.PRICE_TOLERANCE_PCT = 2`. Wiring it into `recompute_match()` is an SCM
        write -> parked for 6.13. Say that in the `help_text`.
      - `priority` PositiveIntegerField default 10 (tie-break, lower wins); `is_active`
        BooleanField default True; `notes` CharField(255) blank.
      - `Meta`: `ordering=["priority","id"]`; indexes `(tenant,is_active,priority)` name
        `prc_rtp_tnt_act_pri_idx` and `(tenant,action)` name `prc_rtp_tnt_action_idx` (<=30 chars).
        **No `unique_together`** - overlapping rules are LEGAL, the resolver decides
        (the `QcRoutingRule` comment at `QcRoutingRules.py:14-15`).
      - `clean()`: cross-tenant guards on `item` / `category` / `vendor` (the
        `QcRoutingRule.clean()` shape at `QcRoutingRules.py:66-86`, errors keyed on the rendered
        field); refuse a rule that sets **no** band at all unless
        `allow_unlimited_over_receipt` is True; refuse `item` AND `category` both set.
      - **Form excludes:** `tenant`, `created_at`, `updated_at`. Everything else is editable -
        this is a configuration master, not a workflow document.
      - [ ] **Module-level resolver, a structural clone of `resolve_qc_routing()`
        (`apps/inventory/models/QualityControl/QcRoutingRules.py:89-146` - READ IT FIRST):**
        `resolve_receipt_tolerance(item=None, vendor=None, *, tenant=None, category=None, rules=None)`
        -> `(rule|None, reason)`. Same hierarchy: item tier 3 > category tier 2 > catch-all 1;
        a **vendor-pinned rule never fires for an unknown/other supplier**; then `priority` ASC,
        `id` ASC. A caller-supplied `rules` list is trusted for ORDER, never for TENANCY (re-filter
        it - `QcRoutingRules.py:113-116`). Every refusal string starts `"No Rule Matched"`.
      - [ ] **Second, separate function** `evaluate_receipt_tolerance(rule, *, ordered_quantity,
        received_quantity, expected_date=None, receipt_date=None)` -> `(verdict, reason)` with
        verdict in `ok | over | short | early | late | no_rule`. Split from the resolver on
        purpose: selection and judgement are independently testable, and the exceptions board
        needs the verdict for lines the resolver already picked a rule for.
      - [ ] **Item resolution helper** `resolve_line_item(tenant, po_line)` -> `scm.Item | None`,
        matching `Item.objects.filter(tenant=tenant, sku__iexact=po_line.sku_hint).first()`.
        This **MIRRORS** `apps/scm/views/_helpers.py:279 _resolve_grn_item` rather than importing
        a private cross-app symbol. GRN/PO lines are free text - there is no item FK to read.

- [ ] **`ReceiptDiscrepancy`** [`RDS-`] (`TenantNumbered`).
      File `models/GoodsReceiptInspection/ReceiptDiscrepancies.py`.
      Drivers: Ariba's accepted-vs-rejected with a mandatory replace-or-credit answer and a
      goods-return tracking number; Oracle's inspection reasons/comments/attachments; Procurify's
      per-line pass/fail with packing-slip upload; Odoo's photo check; D365's **Vendor**-type
      nonconformance sourced from the PO/receipt/lot; Ivalua's instant discrepancy detection.
      - Anchor: `goods_receipt` FK `"scm.GoodsReceiptNote"` **PROTECT**
        `related_name="procurement_discrepancies"`; `goods_receipt_line` FK
        `"scm.GoodsReceiptLine"` **PROTECT null/blank** same related_name (a header-level
        discrepancy - "the paperwork was missing" - is legal).
      - `KIND_CHOICES` = `over_shipment | short_shipment | damaged | wrong_item |
        quality_failure | documentation | late_delivery` (driver: D365's problem types + Ariba's
        rejection reasons). `SEVERITY_CHOICES` = `minor | major | critical`, default `minor`.
      - `quantity_affected` Decimal(14,4) default 0 MinValue(0).
      - Free-text item mirror (**there is no item FK on a GRN line** - the `AsnLine` rule):
        `item_description` CharField(255) blank (auto-copied from `goods_receipt_line.po_line` on
        save when blank), `sku_hint` CharField(64) blank.
      - Traceability text (partially serves bullet 5 WITHOUT a 4th table): `lot_number`
        CharField(64) blank, `serial_number` CharField(64) blank, `expiry_date` DateField
        null/blank.
      - `description` TextField.
      - **Evidence (driver: Odoo photo check / Procurify packing-slip upload / Oracle
        attachments):** `evidence` FileField(`upload_to="procurement/receipt_evidence/%Y/%m/"`,
        null/blank) + `evidence_url` URLField(blank) fallback - the
        `inventory.DefectReport.photo`/`photo_url` pattern. **Validation MUST reuse the existing
        guards, not invent new ones:** `from apps.core.forms._common import
        ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES` (`apps/core/forms/_common.py:16` - the
        allowlist incl. `.pdf .png .jpg .jpeg .gif .webp`; `:22` - 20 MB). **Do NOT re-export
        either constant from `apps/procurement/forms/__init__.py`**: this app already has a
        *different* local `MAX_UPLOAD_BYTES = 2 * 1024 * 1024` at
        `forms/CatalogManagement/UploadBatches.py:13`, and a package-level re-export would make
        which 2 MB / 20 MB applies depend on import order. Keep the import local to the form module.
      - `REMEDY_CHOICES` = `pending | replacement | credit | rtv | accept_as_is | scrap`,
        default `pending` (driver: Ariba *requires* saying replace-or-credit when rejecting).
      - `STATUS_CHOICES` = `open | vendor_notified | resolved | cancelled`, default `open`,
        **`editable=False`** - moved ONLY by the verbs (L22).
      - Vendor-notification block (data now, transmission later - L32): `vendor_notified_on`
        DateField null/blank `editable=False`, `vendor_reference` CharField(64) blank.
      - Resolution block, all `editable=False`: `resolved_at` DateTimeField null/blank,
        `resolved_by` FK user SET_NULL null/blank
        `related_name="procurement_discrepancies_resolved"`, `resolution_notes` TextField blank.
      - Escalation **pointers** (nullable - 6.12 points, it never raises the other module's row):
        `nonconformance` FK `"scm.NonConformance"` SET_NULL null/blank
        `related_name="procurement_discrepancies"` (the `inventory.DefectReport.ncr` precedent -
        the NCR is still raised in SCM); `quarantine_order` FK `"inventory.QuarantineOrder"`
        SET_NULL null/blank same related_name (**the typed link the free-text
        `QuarantineOrder.reference` cannot give**); `return_to_vendor` FK to the RTV below
        SET_NULL null/blank `related_name="source_discrepancies"`.
      - `created_by` FK user SET_NULL null/blank `editable=False`
        `related_name="procurement_discrepancies_created"`.
      - `Meta`: `ordering=["-created_at","-id"]`, `unique_together=("tenant","number")`, indexes
        `(tenant,status)` `prc_rds_tnt_status_idx`, `(tenant,kind)` `prc_rds_tnt_kind_idx`,
        `(tenant,goods_receipt)` `prc_rds_tnt_grn_idx`.
      - `clean()`: `goods_receipt_line.goods_receipt_id` must equal `goods_receipt_id` (a crafted
        POST must not staple another receipt's line on); `goods_receipt` must be this tenant's;
        `nonconformance` / `quarantine_order` / `return_to_vendor` (when set) must be this
        tenant's; `quantity_affected > 0` required for the quantity kinds
        (`over_shipment`/`short_shipment`/`damaged`/`wrong_item`).
      - **Derived, NEVER stored:** `vendor` (walk `goods_receipt.purchase_order.vendor` - do not
        duplicate it as a column), `tolerance_verdict` (resolve the policy for this line, compare
        `purchase_order.received_by_line()[po_line_id]` against `po_line.quantity`),
        `status_css` / `severity_css` / `kind_css` badge maps.
      - **Form excludes:** `tenant`, `number`, `status`, `vendor_notified_on`, `resolved_at`,
        `resolved_by`, `resolution_notes`, `created_by`, `created_at`, `updated_at`.
        `goods_receipt` is on the CREATE form only (popped on edit - changing it would orphan the
        line FK).
      - **Posts nothing to stock and nothing to the ledger.**

- [ ] **`ReturnToVendor`** [`RTV-`] (`TenantNumbered`) **+ `ReturnToVendorLine`** (tenant-less
      child in the SAME entity file - the `AsnLine` / `PurchaseOrderChangeLine` precedent).
      File `models/GoodsReceiptInspection/ReturnsToVendor.py`.
      **Genuinely absent from the repo:** `scm.ReturnAuthorization` (`ReturnAuthorizations.py:48`)
      is the **CUSTOMER** RMA (`customer` + `sales_order` FKs); `scm.WarrantyClaim`
      (`WarrantyClaims.py:34`) is a post-sale failure claim. `return_to_vendor` exists elsewhere
      only as a *disposition choice* whose comment says the document belongs somewhere else.
      Drivers: NetSuite's Vendor Return Authorization created from a failed inspection; Oracle's
      RTV transaction (+ 25D WMS integration); SAP's return delivery / supplier complaint;
      Ariba's replace-or-credit + goods-return tracking number; Fishbowl's vendor return
      reconciliation.
      - Header - parties and origin: `vendor` FK `"core.Party"` **PROTECT**
        `related_name="procurement_rtvs"` (the supplier role - never a second vendor master);
        `purchase_order` FK `"scm.PurchaseOrder"` SET_NULL null/blank same related_name;
        `goods_receipt` FK `"scm.GoodsReceiptNote"` SET_NULL null/blank same related_name;
        `discrepancy` FK `ReceiptDiscrepancy` SET_NULL null/blank `related_name="rtvs"` (the
        usual origin - the discrepancy's "raise RTV" action).
      - `REASON_CHOICES` = `damaged | defective | wrong_item | over_shipment | expired |
        not_to_spec | other`; `reason_note` CharField(255) blank (required when `other`).
      - `REMEDY_CHOICES` = `credit | replacement | repair | none`, default `credit` (driver:
        NetSuite - the disposition drives which downstream document is expected).
      - `STATUS_CHOICES` = `draft | authorized | shipped | closed | cancelled`, default `draft`,
        **`editable=False`**. Flow `draft -> authorized -> shipped -> closed`, with `cancelled`
        reachable from anything **not yet shipped**. Each transition is a **verb method that
        re-checks its own guard INSIDE itself** (the 6.9 C1 / 6.11 lesson: hiding a button does
        not stop a direct POST, and a double-submit must not re-stamp a timestamp).
      - `supplier_rma_number` CharField(64) blank + an **advisory duplicate badge** (the
        `scm.WarrantyClaim.supplier_rma_number` pattern - warn, never hard-block).
      - Return shipment, free text this pass (SCM 4.6 owns freight, L36 - a real
        `scm.Shipment(direction="outbound")` link is a later refinement): `carrier_name`
        CharField(120) blank, `tracking_number` CharField(64) blank, `shipped_on` DateField
        null/blank `editable=False` (stamped by the ship verb), `expected_return_date` DateField
        null/blank.
      - `credit_note_ref` CharField(64) blank - **FREE TEXT, NO LEDGER WRITE**; `help_text` must
        say the AP credit is blocked on the `Bill.kind` gap (L29).
      - Stamps, all `editable=False`: `authorized_by` FK user SET_NULL
        `related_name="procurement_rtvs_authorized"`, `authorized_at` DateTimeField null/blank,
        `closed_at` DateTimeField null/blank, `cancelled_at` DateTimeField null/blank,
        `cancellation_reason` TextField blank, `created_by` FK user SET_NULL
        `related_name="procurement_rtvs_created"`. Plus editable `notes` TextField blank.
      - `Meta`: `ordering=["-created_at","-id"]`, `unique_together=("tenant","number")`, indexes
        `(tenant,status)` `prc_rtv_tnt_status_idx`, `(tenant,vendor)` `prc_rtv_tnt_vendor_idx`,
        `(tenant,reason)` `prc_rtv_tnt_reason_idx`.
      - `clean()`: `purchase_order.vendor_id` must equal `vendor_id` when both are set;
        `goods_receipt.purchase_order_id` must equal `purchase_order_id` when both are set;
        `discrepancy`/`goods_receipt`/`purchase_order` must be this tenant's; `reason_note`
        required when `reason == "other"`.
      - **Derived, NEVER stored:** `expected_credit_value` = SUM(`quantity_returned` x
        `po_line.unit_price`) computed at read time; `is_editable` (`status == "draft"`);
        `status_css` / `reason_css`.
      - **Form excludes:** `tenant`, `number`, `status`, `shipped_on`, `authorized_by`,
        `authorized_at`, `closed_at`, `cancelled_at`, `cancellation_reason`, `created_by`,
        `created_at`, `updated_at`.
      - **`ReturnToVendorLine`** (tenant-less, scoped through its parent):
        `return_to_vendor` FK CASCADE `related_name="lines"`; `goods_receipt_line` FK
        `"scm.GoodsReceiptLine"` **PROTECT null/blank** `related_name="procurement_rtv_lines"`;
        `po_line` FK `"scm.PurchaseOrderLine"` **PROTECT null/blank**
        `related_name="procurement_rtv_lines"` (sizes the credit via its `unit_price`);
        free-text `item_description` CharField(255) blank / `sku_hint` CharField(64) blank /
        `uom_hint` CharField(32) blank **auto-copied from the source line in `save()` when blank**
        (the `AsnLine.save()` shape at `AdvancedShipmentNotice.py:487-496`);
        `quantity_returned` Decimal(14,4) MinValue(0.0001); `lot_number` CharField(64) blank,
        `serial_number` CharField(64) blank; `condition_note` CharField(255) blank.
        `Meta`: `ordering=["id"]`. `clean()`: quantity > 0; when both are set,
        `goods_receipt_line.po_line_id` must equal `po_line_id`; the line's receipt must be the
        header's `goods_receipt` when the header names one.
        **Form excludes:** none extra - it is an `inlineformset_factory`; `return_to_vendor` comes
        from the parent instance and `goods_receipt_line`'s queryset is narrowed to the header's
        receipt lines.
      - **DELIBERATE NON-POSTING - defend it in the docstring AND on the detail page:** an RTV
        posts **no `StockMove` and no `JournalEntry`**. Verified reason:
        `_post_grn_receipt` (`apps/scm/views/_helpers.py:299`, line 319) posts **only
        `quantity_received`**, so dock-rejected quantity never entered the ledger and there is
        nothing to remove; accepted stock that later fails QC is removed by
        `inventory.QuarantineOrder.scrap()` or `scm:stockadjustment`. Same posture
        `scm.NonConformance` already takes for its `return_to_vendor` disposition. 6.12's RTV is
        the **authorisation + tracking document**, not a second ledger writer.

- [ ] **Three computed pages - ZERO new state** (the 6.10 `po_line_tracking` / 6.11
      `inbound_tracking` precedent): `receiving_console`, `tolerance_exceptions`, `receipt_audit`.
      No models of their own; the console's booking action writes a **draft** GRN through SCM's
      own models, and the audit page reads `procurement_activity_qs()`.

## Backend (apps/procurement/{models,forms,views,urls}/GoodsReceiptInspection/)

Absolute imports only (`from apps.procurement.models._base import *`, `from
apps.procurement.views._common import *`, `from apps.procurement.forms._common import *`).
Each new folder needs its own `__init__.py` in each of the four layers (own commit, even when it
only re-exports).

### models/GoodsReceiptInspection/
- [ ] `__init__.py` - sub-package re-exports
- [ ] `ReceiptTolerances.py` - `ReceiptTolerancePolicy` + `resolve_receipt_tolerance()` +
      `evaluate_receipt_tolerance()` + `resolve_line_item()`
- [ ] `ReceiptDiscrepancies.py` - `ReceiptDiscrepancy` + verb methods `notify_vendor(user, ref)`,
      `resolve(user, notes)`, `cancel(user)` - each re-checking its own status guard inside itself
- [ ] `ReturnsToVendor.py` - `ReturnToVendor` **+ `ReturnToVendorLine`** (one entity file owns its
      children) + verb methods `authorize(user)`, `mark_shipped(user, carrier, tracking, date)`,
      `close(user, credit_note_ref)`, `cancel(user, reason)` - guards re-checked inside

### forms/GoodsReceiptInspection/
- [ ] `__init__.py`
- [ ] `ReceiptTolerances.py` - `ReceiptTolerancePolicyForm` (`TenantModelForm`; `item` /
      `category` / `vendor` querysets tenant-scoped, `vendor` narrowed to supplier-role parties
      via the existing `_supplier_parties`-style helper)
- [ ] `ReceiptDiscrepancies.py` - `ReceiptDiscrepancyForm` (`goods_receipt` queryset = tenant
      GRNs not `cancelled`, popped on edit; `goods_receipt_line` queryset narrowed to that
      receipt's lines; `nonconformance` / `quarantine_order` / `return_to_vendor` querysets
      tenant-scoped; accepts `?goods_receipt=` / `?goods_receipt_line=` / `?kind=` /
      `?quantity_affected=` GET prefill from the tolerance-exceptions board) with
      `clean_evidence()` enforcing `ALLOWED_DOC_EXTENSIONS` + `MAX_UPLOAD_BYTES` imported from
      `apps.core.forms._common`; plus `DiscrepancyNotifyForm` (`vendor_reference`,
      `vendor_notified_on`) and `DiscrepancyResolveForm` (`remedy` required, `resolution_notes`
      required)
- [ ] `ReturnsToVendor.py` - `ReturnToVendorForm` (tenant-scoped `vendor` / `purchase_order` /
      `goods_receipt` / `discrepancy`; accepts `?discrepancy=` GET prefill), `ReturnToVendorLineForm`
      + `ReturnToVendorLineFormSet` (`inlineformset_factory`, `goods_receipt_line` queryset
      narrowed to the header's receipt), `RtvShipForm` (`carrier_name`, `tracking_number`,
      `shipped_on`), `RtvCloseForm` (`credit_note_ref`), `RtvCancelForm` (reason required)
- [ ] `ReceivingConsole.py` - `ReceivingConsoleBookForm` (plain `forms.Form`: `receipt_date`,
      `location` tenant-scoped, per-line `quantity_received` - NOT a ModelForm over an SCM model)

### views/GoodsReceiptInspection/ (function-based, `@login_required`, tenant-scoped on EVERY query)
- [ ] `__init__.py`
- [ ] `ReceiptTolerances.py` - `tolerancepolicy_list` (search `name`/`notes`/`item__sku`/
      `vendor__name`; filters `action`, `active`, `item`, `vendor`, `scope`
      (item/category/catch-all); pagination; `select_related("item","category","vendor")`),
      `tolerancepolicy_detail` (shows which receipts the rule currently governs + a worked
      example of the band), `_create`, `_edit`, `_delete` (POST-only + confirm).
      **`@tenant_admin_required` on create/edit/delete** - a rule master changes what the whole
      workspace flags (the `QcRoutingRule` gating precedent).
- [ ] `ReceiptDiscrepancies.py` - `discrepancy_list` (search `number`/`description`/
      `item_description`/`sku_hint`/`goods_receipt__number`/`vendor_reference`; filters `status`,
      `kind`, `severity`, `remedy`, `grn`, `vendor` (via
      `goods_receipt__purchase_order__vendor_id`); pagination;
      `select_related("goods_receipt","goods_receipt__purchase_order",
      "goods_receipt__purchase_order__vendor","goods_receipt_line","nonconformance",
      "quarantine_order","return_to_vendor")` - without it a page of rows costs N queries),
      `discrepancy_detail` (evidence panel, the derived tolerance verdict, links out to the NCR /
      quarantine order / RTV, and a "Raise RTV from this finding" prefilled link),
      `_create`, `_edit`, `_delete` (POST-only, `@tenant_admin_required`), verbs
      `discrepancy_notify_vendor`, `discrepancy_resolve`, `discrepancy_cancel` - all
      `@require_POST` + `transaction.atomic()` + `select_for_update()` so a double-submit cannot
      re-stamp `vendor_notified_on` / `resolved_at`
- [ ] `ReturnsToVendor.py` - `rtv_list` (search `number`/`supplier_rma_number`/`tracking_number`/
      `vendor__name`/`purchase_order__number`; filters `status`, `reason`, `remedy`, `vendor`,
      `po`; pagination; `select_related("vendor","purchase_order","goods_receipt","discrepancy")`),
      `rtv_detail` (lines + derived expected credit + the duplicate-RMA advisory badge + the
      **"posts no stock and no journal, and why"** panel), `rtv_create` (header; accepts
      `?discrepancy=`), `rtv_edit` (header + `ReturnToVendorLineFormSet`, drafts only),
      `rtv_delete` (POST-only, drafts only, `@tenant_admin_required`), verbs `rtv_authorize`
      (`@tenant_admin_required`), `rtv_ship`, `rtv_close`, `rtv_cancel` - all `@require_POST` +
      atomic + row-locked
- [ ] `ReceivingConsole.py` - `receiving_console` (the ASN->GRN booking desk; the hand-off 6.11
      deferred). Lists tenant ASNs in `IN_FLIGHT_STATUSES` / `delivered` with **no GRN yet**,
      matched on `AdvancedShipmentNotice.supplier_reference` ==
      `GoodsReceiptNote.delivery_note_ref` (6.11 enforces uniqueness of `supplier_reference`
      across live ASNs precisely so this match is unambiguous). Filters: `q`, `status`, `vendor`,
      `po`, `arrival` (today/overdue/awaiting). Context keys pinned: `rows`, `page_obj`,
      `status_choices`, `vendors`, `stats` (`awaiting`/`arrived_today`/`overdue`/`booked_7d`),
      echoed GET params.
      `receiving_console_book` (`@require_POST`, `@login_required`, atomic + `select_for_update()`
      on the ASN) - creates a **DRAFT** `scm.GoodsReceiptNote` + `GoodsReceiptLine` rows from the
      ASN lines, copying `supplier_reference -> delivery_note_ref`; **idempotent** (returns the
      existing receipt if one already carries that `delivery_note_ref`); calls `write_audit_log`
      itself (hand-rolled save path); redirects to `scm:goodsreceipt_detail`. It does NOT receive
      the goods - `scm:goodsreceipt_receive` stays the single stock writer.
      `receiving_console_mint_lots` (`@require_POST`, `@tenant_admin_required`) - mints the ASN's
      declared lot/serial text into `scm.LotSerial` for lines whose `sku_hint` resolves to a
      `scm.Item`, `get_or_create` keyed on **`(tenant, item, number)`** (verified
      `unique_together` at `LotSerials.py:25`) with `kind`/`expiry_date` as defaults; reports
      unresolved SKUs as warnings rather than failing (the `_post_grn_receipt` posture).
- [ ] `ToleranceExceptions.py` - `tolerance_exceptions` board. Every non-cancelled receipt line
      whose received quantity or receipt date breaches the resolved policy, bucketed
      `over / short / early / late`. **Filter in the ORM BEFORE pagination** (the 6.11
      backorder-risk lesson - a Python-side filter makes the page counts lie): narrow to
      candidate GRN lines with ORM predicates and date arithmetic first, resolve the policy over
      the pre-fetched rule list (one query, passed as `rules=`) second. Each row carries a
      one-click **"Raise discrepancy"** link that prefills
      `procurement:discrepancy_create?goods_receipt=&goods_receipt_line=&kind=&quantity_affected=`.
      Context keys pinned: `rows`, `page_obj`, `bucket`, `bucket_choices`, `vendors`, `stats`
      (`over`/`short`/`early`/`late`/`no_policy`), echoed GET params.
- [ ] `ReceiptAudit.py` - `receipt_audit` trail. Reads `procurement_activity_qs(request.tenant)`
      (`apps/procurement/views/_helpers.py:51`) narrowed to `goodsreceiptnote` **plus this
      sub-module's own content types**, optionally scoped to one receipt via `?grn=<pk>`. Shows
      booking, reversal, re-match, discrepancies and RTVs on one page. Context keys pinned:
      `entries`, `page_obj`, `grn`, `receipts`, `action_choices`, `stats`, `ACTIVITY_FEED_NOTE`.
- [ ] `write_audit_log` (`apps/core/utils.py`) on **every hand-rolled save path** - the verbs, the
      console booking action and the lot-minting action. The `crud_*` helpers
      (`apps/core/crud.py`) already call it for list/create/edit/delete.

### urls/GoodsReceiptInspection/ (literal routes BEFORE `<int:pk>`, first-match-wins)
- [ ] `__init__.py` concatenating the six modules' `urlpatterns`
- [ ] `ReceiptTolerances.py` - `receipt-tolerances/` -> `tolerancepolicy_list`;
      `receipt-tolerances/add/` -> `tolerancepolicy_create`; then
      `receipt-tolerances/<int:pk>/` `/edit/` `/delete/`
- [ ] `ReceiptDiscrepancies.py` - `receipt-discrepancies/` `-/add/` (literal, BEFORE pk),
      `-/<int:pk>/` `/edit/` `/delete/` `/notify-vendor/` `/resolve/` `/cancel/`
- [ ] `ReturnsToVendor.py` - `returns-to-vendor/` `-/add/` `-/<int:pk>/` `/edit/` `/delete/`
      `/authorize/` `/ship/` `/close/` `/cancel/`
- [ ] `ReceivingConsole.py` - `receiving-console/` -> `receiving_console`;
      `receiving-console/<int:pk>/book/` -> `receiving_console_book`;
      `receiving-console/<int:pk>/mint-lots/` -> `receiving_console_mint_lots`
- [ ] `ToleranceExceptions.py` - `tolerance-exceptions/` -> `tolerance_exceptions`
- [ ] `ReceiptAudit.py` - `receipt-audit/` -> `receipt_audit`
- [ ] Collision check: the six new first segments (`receipt-tolerances/`,
      `receipt-discrepancies/`, `returns-to-vendor/`, `receiving-console/`,
      `tolerance-exceptions/`, `receipt-audit/`) are distinct whole components against the
      inventory in `apps/procurement/urls/__init__.py:7-15`, and the app still has **no greedy
      `<str:...>` converter**, so there is no cross-module shadowing surface.

### Shared files - SOLO integrate step only, surgical `Edit` (a concurrent session may be in this tree, L43)
- [ ] `models/__init__.py` - re-export `ReceiptTolerancePolicy, ReceiptDiscrepancy,
      ReturnToVendor, ReturnToVendorLine, resolve_receipt_tolerance, evaluate_receipt_tolerance,
      resolve_line_item` and add every name to `__all__`
- [ ] `forms/__init__.py` - re-export the form/formset names. **Do NOT re-export
      `MAX_UPLOAD_BYTES` / `ALLOWED_DOC_EXTENSIONS`** (collides with the 2 MB catalog constant).
- [ ] `views/__init__.py` - re-export EVERY new view function (a missing one is an
      `AttributeError` at URLconf import, not at request time)
- [ ] `urls/__init__.py` - `from .GoodsReceiptInspection import urlpatterns as
      _gri_goodsreceiptinspection`, splat it LAST; extend the module docstring's segment inventory
      with the six new segments
- [ ] `views/_helpers.py` - append `"receipttolerancepolicy"`, `"receiptdiscrepancy"`,
      `"returntovendor"` to `PROCUREMENT_CONTENT_MODELS`? **NO** - that tuple is the *scm*-app
      whitelist (`:60-62` already includes every `app_label="procurement"` row). Leave it
      untouched; `goodsreceiptnote` is already listed (`:29`).
- [ ] `admin.py` - register `ReceiptTolerancePolicy`, `ReceiptDiscrepancy`, `ReturnToVendor`
      (with a `ReturnToVendorLine` inline); `list_display` / `list_filter` / `search_fields` /
      `readonly_fields` covering every `editable=False` stamp
- [ ] `management/commands/seed_procurement.py` - add `self._seed_goods_receipt(tenant)` after
      `self._seed_order_fulfillment(tenant)` (`:205`) and the method itself. Idempotent, reusing
      EXISTING rows: find a seeded `scm.GoodsReceiptNote` (friendly skip + return when the tenant
      has none), then create (a) two `ReceiptTolerancePolicy` rows - one catch-all
      (`over_receipt_pct=5`, `under_receipt_pct=10`, `action="warn"`) and one vendor-pinned
      stricter rule - keyed on `(tenant, name)` via `get_or_create`; (b) one `open`
      `ReceiptDiscrepancy` of kind `damaged` and one `resolved` of kind `short_shipment`, keyed
      on `(tenant, goods_receipt, kind)` existence-check (**never bare `.create()` on a numbered
      model**); (c) one `authorized` `ReturnToVendor` with 2 lines and one `draft`, keyed on
      `(tenant, vendor, supplier_rma_number)` existence-check. No file is written for `evidence`
      (seeders must not create media).
- [ ] **`makemigrations procurement` LAST** -> must produce exactly **`0017_*`**
      (rename the generated file if Django picks a different suffix - the NUMBER 0017 is the
      claim). Do not touch 0016.

## Wire-up
- [ ] `apps/core/navigation.py` - **ONE** new `LIVE_LINKS["6.12"]` entry inserted AFTER the
      `"6.11"` dict (which ends at `:1566`), bullet text copied EXACTLY from NavERP.md
      lines 1069-1078. **Six of the ten keys are MAPS to pages that already exist** - each url
      name below was resolved by grep this session:
      ```
      "Goods Receipt Note (GRN) Creation": "procurement:receiving_console",      # NEW page
      "Receipt Tolerances":                "procurement:tolerancepolicy_list",   # NEW table
      "Quality Inspection Checklists":     "inventory:qcchecklist_list",         # MAP 5.15 (QcChecklists.py:10)
      "Quarantine & Inspection Hold":      "inventory:quarantineorder_list",     # MAP 5.15 (QuarantineOrders.py:12)
      "Lot, Batch & Serial Capture":       "scm:lotserial_list",                 # MAP 4.3 (LotSerials.py:8)
      "Discrepancy Reporting":             "procurement:discrepancy_list",       # NEW table
      "Return to Vendor (RTV) Processing": "procurement:rtv_list",               # NEW table
      "Item Tagging & Barcoding":          "inventory:barcodelabel_list",        # MAP 5.14 (BarcodeLabels.py:7)
      "Inventory Posting":                 "scm:goodsreceipt_list?status=received",  # MAP 4.1
      "Receipt Reversal & Audit Trail":    "procurement:receipt_audit",          # NEW page
      ```
      The `?status=received` query string is **verified safe**: `scm:goodsreceipt_list`
      (`apps/scm/views/ProcurementManagement/GoodsReceiptNotes.py:17-35`) passes
      `("status", "status", False)` to `crud_list` and `status_choices` to the template.
      Add a comment block above the dict recording (a) that six bullets map to existing pages and
      WHY (L36 - a second quality register / a second tolerance / a second barcode label would
      give the workspace two answers), and (b) the RTV non-posting rule.
- [ ] `config/settings.py` / `config/urls.py` - **NO CHANGE** (existing app).

## Templates (templates/procurement/goodsreceiptinspection/)
Every list page: filter bar reflecting `request.GET` (string fields `==` compare, FK/pk via
`|stringformat:"d"` - **never** `|slugify`), an Actions column (view / edit / delete-POST with
`{% csrf_token %}` + `onclick="return confirm(...)"`), pagination guarded by
`{% if page_obj.has_previous %}` / `has_next` (L9), and an empty state. Badges use ONLY
`badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate` (L33 - the
semantic `-success` / `-danger` names do NOT exist in theme.css and render unstyled) with an
`{% else %}` `{{ obj.get_*_display }}` fallback.
- [ ] `tolerancepolicy/list.html` - filters q / action / active / scope / vendor; columns name /
      scope (item|category|catch-all + vendor pin) / over band (% or qty or "unlimited") / under %
      / early-late days / action badge / priority / active
- [ ] `tolerancepolicy/detail.html` - the resolved band explained in words ("accepts up to 5%
      over on 100 ordered = 105"), the specificity tier this rule sits at, an **advisory** notice
      that it never blocks `scm:goodsreceipt_receive`, Actions sidebar (Edit / Delete / Back)
- [ ] `tolerancepolicy/form.html` - scope fieldset (item XOR category, optional vendor pin),
      band fieldset, action + priority
- [ ] `discrepancy/list.html` - filters q / status / kind / severity / remedy / grn / vendor;
      columns number / GRN + line / kind + severity badges / qty affected / remedy / vendor /
      evidence indicator / status badge
- [ ] `discrepancy/detail.html` - finding block, **evidence panel** (inline `<img>` for image
      extensions, download link otherwise, `evidence_url` fallback), the derived tolerance
      verdict, escalation panel linking out to `scm:nonconformance_detail` /
      `inventory:quarantineorder_detail` / the RTV, Actions sidebar (Notify vendor form / Resolve
      form / Raise RTV / Cancel / Edit / Delete / Back), each gated on the current status
- [ ] `discrepancy/form.html` - GRN + line selectors (line narrowed to the chosen receipt),
      kind/severity/quantity, evidence upload with the allowed extensions + 20 MB stated in the
      help text, remedy
- [ ] `rtv/list.html` - filters q / status / reason / remedy / vendor / po; columns number /
      vendor / origin (GRN or discrepancy) / reason / remedy / supplier RMA (duplicate badge) /
      expected credit / status badge
- [ ] `rtv/detail.html` - header + line table with per-line expected credit, the running
      `expected_credit_value`, shipment block (carrier / tracking / shipped on), **a standing
      note explaining that an RTV posts no StockMove and no JournalEntry and where the physical
      removal actually happens**, Actions sidebar (Authorize / Ship form / Close form / Cancel
      form / Edit / Delete / Back), each gated on status
- [ ] `rtv/form.html` - header form; on edit also renders `ReturnToVendorLineFormSet` with the
      source receipt shown read-only
- [ ] `receiving_console.html` - **standalone page at the sub-module root** (the 6.11
      `inbound_tracking.html` / 6.10 `linetracking.html` precedent): stat tiles + filter bar +
      one row per unbooked ASN showing declared vs outstanding vs already-received per line, the
      resolved tolerance verdict, the resolved `QcRoutingRule` verdict + reason, and the
      **Book receipt** POST form (+ the secondary **Mint declared lots** form)
- [ ] `tolerance_exceptions.html` - standalone board: over / short / early / late buckets, each
      row with ordered vs received vs band and a one-click **Raise discrepancy** prefill link;
      a `no_policy` tile counts lines no rule covers (so a silent gap is visible)
- [ ] `receipt_audit.html` - standalone trail: `?grn=` scope selector, action filter, one row per
      audit entry (who / what / when), the `ACTIVITY_FEED_NOTE` explanation, pagination

## Verify
- [ ] `makemigrations procurement` (**0017**) then `migrate`
- [ ] `seed_procurement` run **TWICE** - the second run creates nothing new and does not crash
- [ ] `manage.py check` clean
- [ ] `temp/` smoke script as **`admin_acme` / `password`**: every new `procurement:*` url renders
      200/302; content assertions (page titles, a seeded `RDS-` number, an `RTV-` number, a
      tolerance policy name, the receiving console's stat tiles); **no `{#` or `{% comment`
      leaking into the HTML**; junk filter params (`?status=nope&kind=zzz&vendor=abc`) still 200;
      `?page=2` guarded; **cross-tenant IDOR** - an `admin_globex`-owned discrepancy / RTV /
      policy pk returns **404** on detail/edit/delete and on every verb; verbs reject GET (405);
      a non-admin user is refused on the admin-gated routes (policy write, RTV authorize,
      discrepancy delete, mint-lots)
- [ ] Extra assertions specific to this sub-module: booking the console twice for the same ASN
      creates **one** GRN (idempotence); minting lots twice creates **one** `LotSerial` per
      `(tenant,item,number)`; an authorized RTV produces **zero** new `StockMove` and **zero** new
      `JournalEntry` rows (assert the counts - this is the rule most likely to be "fixed" wrongly)
- [ ] Sidebar shows **6.12 as Live with all ten bullets resolving** - the four
      `inventory:*`/`scm:*` maps must not `NoReverseMatch`

## Close-out (the mandatory Module Creation Sequence, phases 4-7)
- [ ] Phase 4 review wave - `.claude/workflows/module-review.js` with the six lanes in PARALLEL
      (code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester,
      security-reviewer) -> write findings to `.claude/tasks/review-procurement-6.12.md` and
      commit that file; re-run any lane reporting NO RESULT
- [ ] Phase 5 `code-fixer` agent burns the findings down in ID order, one commit per file; no
      finding left `[ ] open`. **Brief it that the RTV non-posting and the advisory-only tolerance
      are DELIBERATE** so they are not "fixed" into ledger writes or a receive-time block.
- [ ] Phase 6 test wave - `.claude/workflows/module-tests.js` with **`subslug: 'receipt'`** ->
      `test_receipt_{models,forms,views,security}.py`, every function `test_receipt_*` and every
      module-level helper `_receipt_*`; the solo contract step owns
      `apps/procurement/tests/conftest.py` (which already holds the `fulfillment_*` fixtures -
      append `receipt_*` fixtures, never rename existing ones); the final run is the **FULL
      unfiltered** procurement suite (L47)
- [ ] Phase 7 - update `.claude/skills/procurement/SKILL.md` with the 6.12 models / routes /
      templates / seeder rows / LIVE_LINKS block **and the six mapped bullets** (a future session
      must not rebuild them); mark 6.12 complete in `README.md` (**12 of 19**)
- [ ] Mark each phase in `build_state.py`; append a Close-out review section here
- [ ] One file per commit throughout, PowerShell `;` separators, **never `git push`**

## Later passes / deferred (carried from research - nothing lost)
- **`ReceiptLotCapture` as its own table** - deferred. The bullet is served by `scm:lotserial_list`
  (master + CRUD + expiry), by `AsnLine`'s declared lot/serial/expiry/country-of-origin text, by
  the lot fields on `ReceiptDiscrepancy` / `ReturnToVendorLine`, and by the console's mint verb.
  Revisit when `scm.GoodsReceiptLine` gains an item FK.
- **Hard-blocking a receipt** that breaches tolerance or has open mandatory checks -
  `goodsreceipt_receive` is SCM's verb (L36). 6.12 flags and reports.
- **GR/IR accrual journal at receipt; vendor debit memo / credit note** - `apps/accounting` owns
  the ledger (L29); `accounting.Bill` has no `kind`. Already flagged to Modules 2/6 by
  `scm.WarrantyClaim`. 6.12 records `credit_note_ref` and posts nothing.
- **Stock removal on RTV** - deliberate non-posting (see the model note). Physical removal stays
  with `inventory.QuarantineOrder.scrap()` / `scm:stockadjustment`.
- **Unordered / non-PO receipts** - `GoodsReceiptNote.purchase_order` is a non-null PROTECT FK.
- **Auto-receipt on thresholds / due date / invoice reconciliation** (Ariba, Procurify) - needs a
  scheduler. **Blind receiving**, quarantine/NCR **tag printing**, **license-plate (LPN)
  receiving** - WMS-grade; nearest homes are `inventory.BarcodeLabel` and SCM 4.4.
- **Sampling-plan master** (fixed / percentage / skip-lot / AQL) and any new inspection execution
  record -> **SCM 4.9 / future Module 12 QMS**, never a third quality register in procurement.
- **Parked for sibling sub-modules:** delivery-completed / close-short indicator -> **6.10**;
  invoice price-tolerance holds, wiring `price_variance_pct` into `recompute_match()`, the
  four-way match column, invoice disputes, delivery-note **OCR** -> **6.13**; discrepancy and
  rejection rates as supplier KPIs -> **6.16** (`scm.SupplierScorecard` already derives GRN
  signals); supplier self-service filing of inspection results -> **6.4** `VendorPortalAccess`
  (stays behind a login - a staff sidebar bullet must never point at it, L32); on-hand
  visibility, bin mapping, cycle counts -> **6.18**; evidence/document repository with versioning
  and full-text search -> **6.19**.
- **Deferred integrations:** EDI 861 receiving advice, carrier APIs, supplier quality
  notifications (SAP Ariba SCC), native handheld app - the provenance columns already exist
  (`AdvancedShipmentNotice.source` includes `edi`).

## Review notes
(filled in at close-out)

---
# Sub-module 6.13 - Invoice & Voucher Management (Module 6: Procurement Management System, `procurement`) - plan from research-procurement-6.13.md  (2026-08-30)

App EXISTS (`apps/procurement/`, 6.1-6.12 built) -> this pass EXTENDS it. **No `config/settings.py` / `config/urls.py` change** (procurement already installed + included; L31/L32).
Sub-module package folder: **`InvoiceVoucherManagement/`** in all four backend layers. Template sub-module folder: **`invoicevouchermanagement/`**. Test subslug: **`invoice`**.
Migration **0020 is CLAIMED**, generated LAST (latest on disk is `0019_returntovendor_prc_rtv_tnt_rma_idx.py`).
Number prefixes **`SIV`** (SupplierInvoice) and **`DSP`** (InvoiceDispute) re-verified free across `apps/`.
Three corrections applied to the research doc: (a) **`scm.Item` DOES exist** (`apps/scm/models/InventoryManagement/Items.py:73`) so invoice lines get an optional item FK;
(b) `accounting.Invoice` is AR - the AP ledger record is **`accounting.Bill`**; (c) the migration is 0020, not 0017.

## Scope decision
**Four models**: `SupplierInvoice`, `SupplierInvoiceLine`, `InvoiceMatchVariance`, `InvoiceDispute`.
**Five NavERP.md bullets** (lines 1081-1085, text copied verbatim into LIVE_LINKS below): Invoice Capture (OCR) / Three-Way Matching /
Dispute Resolution Workflow / Payment Schedule-Terms Management / Early Payment Discount Tracking.
- [ ] Bullet 1 ships as **"Assisted Capture", NOT OCR** - the UI must never say "OCR". Why: no OCR engine, no Tesseract, no vision API
      and no Celery worker exists in this stack; `pdfplumber`/`PyMuPDF` read a PDF's **text layer** and return `None` on a scan; an OCR job/queue table with no worker is dead
      schema. Honest behaviour = text-layer extraction -> anchor+regex heuristics -> **pre-filled form with per-field confidence badges for human review** -> human confirms.
      A scan with no text layer drops to the manual form with `source="manual"`, `extraction_confidence=0` - the designed path, not an error.
- [ ] Bullets 4 and 5 need **no new model**: `accounting.PaymentTerm` already carries `days_due`, `discount_pct`, `discount_days`
      (`models/AccountsPayable/PaymentTerms.py:6-11`, verified). Both pages are pure **derived** views over `SupplierInvoice` (L29 / L37 §2).
- [ ] Deliberately NOT built (L36 - map, do not rebuild): no `CreditMemo`/`DebitMemo` table (`invoice_type` + sign-aware totals); no stored
      `PaymentSchedule` / `DiscountOpportunity` table (projections - storing them guarantees drift); no `InvoiceMatchTolerancePolicy` (tolerances are class constants, the
      `GoodsReceiptNote.PRICE_TOLERANCE_PCT` idiom); no OCR job table; no supplier-facing portal pages (6.4 owns those - L32: a staff bullet must never point at a login-gated view).
- [ ] Do NOT re-declare `PurchaseOrder` / `GoodsReceiptNote` (L36). Two `PurchaseOrder` classes exist on purpose - `crm.PurchaseOrder` (lightweight)
      and **`scm.PurchaseOrder`** (canonical). **Use `scm.` everywhere.**

## Models (`apps/procurement/models/InvoiceVoucherManagement/`)
All FKs by **string**, never an import (app-registry cycle). `TenantOwned.tenant` already declares `related_name="+"` - do not give it a per-model related_name;
**every other FK needs one**.

### `SupplierInvoices.py` - `SupplierInvoice(TenantNumbered)`, prefix `SIV`
- [ ] CHOICES verbatim from research §3.1: `STATUS_CHOICES` (draft/parked/captured/blocked/disputed/pending_approval/approved/scheduled/paid/void/reversed); `INVOICE_TYPE_CHOICES` (standard/credit_memo/debit_memo/prepayment/service); `MATCH_BASIS_CHOICES` (quantity/amount/none); `MATCH_STATUS_CHOICES` (not_run/matched/within_tolerance/price_variance/quantity_variance/total_variance/fx_variance/no_receipt/over_invoiced/duplicate_suspect); `SOURCE_CHOICES` (manual/pdf_text_layer/e_invoice_xml/vis/ocr); `DISCOUNT_BASE_CHOICES` (net_of_tax/gross)
- [ ] FKs: `vendor` -> `'core.Party'` PROTECT; `purchase_order` -> `'scm.PurchaseOrder'` SET_NULL; `goods_receipt` -> `'scm.GoodsReceiptNote'` SET_NULL;
      `bill` -> `'accounting.Bill'` SET_NULL; `journal_entry` -> `'accounting.JournalEntry'` SET_NULL `editable=False`; `payment_term` -> `'accounting.PaymentTerm'`;
      `currency` -> `'accounting.Currency'`; `tax_code` -> `'accounting.TaxCode'`; `source_submission` -> `'procurement.VendorInvoiceSubmission'` (one-way, header-only);
      `document` -> `'core.Document'`; `duplicate_of` -> `'self'`; `approved_by` -> `AUTH_USER_MODEL` `editable=False`. Shared targets use `related_name="procurement_supplier_invoices"`.
- [ ] Scalars: `invoice_type`, `invoice_number` Char(64), `invoice_number_norm` Char(64) `editable=False` db_index (uppercased, non-alphanumerics stripped - the duplicate key),
      `external_ref`, `invoice_date`, `posting_date` null, `due_date` / `discount_date` / `discount_expiry_date` null + `editable=False`, `discount_base` (default `net_of_tax`),
      `discount_grace_days` PosSmallInt default 0, `subtotal` / `tax_total` / `total` / `amount_paid` Decimal(18,2) **`editable=False`**, `fx_rate` Decimal(14,6) null,
      `match_basis`, `match_status` + `match_notes` `editable=False`, `status` default `draft`, `source` default `manual`, `extraction_confidence` Decimal(5,2) null,
      `extraction_raw_text`, `notes`
- [ ] `Meta`: `ordering = ["-invoice_date","-id"]`, `unique_together = ("tenant","number")`, indexes `["tenant","status"]`, `["tenant","match_status"]`,
      `["tenant","vendor","invoice_number_norm"]`, `["tenant","discount_date"]`, `["tenant","due_date"]`
- [ ] Methods: `recalc_totals()`, `run_match()`, `is_locked` (status in paid/void/reversed), `cumulative_invoiced_qty(po_line)`, `cumulative_received_qty(po_line)`,
      `discount_amount()`, `annualised_pct()`, `duplicate_candidates()`

### `SupplierInvoiceLines.py` - `SupplierInvoiceLine` (plain child, scoped through the header)
- [ ] `invoice` -> `SupplierInvoice` CASCADE `related_name="lines"`; `po_line` -> `'scm.PurchaseOrderLine'` PROTECT null; `receipt_line` -> `'scm.GoodsReceiptLine'` PROTECT null;
      **`item` -> `'scm.Item'` SET_NULL null (NEW - the research doc wrongly assumed no item master; `scm.Item` exists at Items.py:73)**; `gl_account` -> `'accounting.GLAccount'` SET_NULL null;
      `tax_code` -> `'accounting.TaxCode'` SET_NULL null. All five use `related_name="procurement_invoice_lines"`.
- [ ] `description` Char(255), `sku_hint` Char(64) / `uom_hint` Char(32) blank (**kept as the non-PO fallback - the item FK is optional, never required**), `quantity` Decimal(14,4) default 1,
      `unit_price` Decimal(14,2) default 0, `tax_rate_pct` Decimal(5,2) default 0, `line_total` Decimal(18,2) `editable=False`, `matched_qty` Decimal(14,4) `editable=False`
- [ ] `cumulative_invoiced_qty` is **DERIVED by aggregation, NOT a stored column** (§5.2 - a cached counter drifts the first time a GRN is cancelled or an invoice reversed)
- [ ] `save()` recomputes `line_total` (sign-aware for credit memos) then calls `invoice.recalc_totals()`; `clean()` rejects mixing tax-inclusive and tax-exclusive
      `unit_price` across lines on one invoice

### `MatchVariances.py` - `InvoiceMatchVariance(TenantOwned)` (no number - nobody quotes one)
- [ ] CHOICES verbatim from research §3.3: `VARIANCE_TYPE_CHOICES` (price/quantity/quantity_no_receipt/over_invoice/total_amount/fx_rate/tax/duplicate/missing_po/missing_receipt); `OUTCOME_CHOICES` (auto_accept/warn/block); `RESOLUTION_CHOICES` (open/accepted/disputed/credit_memo/debit_memo/short_paid/cancelled)
- [ ] `invoice` -> `SupplierInvoice` CASCADE `related_name="variances"`; `invoice_line` -> `SupplierInvoiceLine` CASCADE **null** `related_name="variances"` (null = header-level check);
      `dispute` -> `InvoiceDispute` SET_NULL null `related_name="variances"`
- [ ] `variance_type`, `basis` (`po`/`receipt`/`header`), `expected_value` / `actual_value` Decimal(18,4), `variance_abs` + `variance_pct` `editable=False`
      (**signed**, actual − expected), `tolerance_abs_applied` / `tolerance_pct_applied` null, `outcome`, `resolution` default `open`, `message` Char(255), `detected_at` `auto_now_add`
- [ ] `Meta`: `ordering = ["-detected_at"]`, indexes `["tenant","outcome","resolution"]`, `["tenant","variance_type"]`, `["invoice"]`

### `InvoiceDisputes.py` - `InvoiceDispute(TenantNumbered)`, prefix `DSP`
- [ ] CHOICES verbatim from research §3.4: `REASON_CODE_CHOICES` (price/quantity/goods_not_received/damaged/duplicate/credit_not_processed/tax/freight/admin/other); `RESOLUTION_CHOICES` (credit_memo/debit_memo/reinvoice/short_pay/withdrawn); `STATUS_CHOICES` (open/awaiting_supplier/awaiting_internal/resolved/escalated/closed)
- [ ] `invoice` -> `SupplierInvoice` CASCADE `related_name="disputes"`; `invoice_line` -> `SupplierInvoiceLine` SET_NULL null `related_name="disputes"`; `supplier` -> `'core.Party'` PROTECT
      `related_name="procurement_invoice_disputes"`; `raised_by` + `assigned_to` -> `AUTH_USER_MODEL` SET_NULL; `credit_memo_invoice` -> `SupplierInvoice` SET_NULL null
      `related_name="resolved_disputes"`
- [ ] `reason_code`, `status` default `open`, `disputed_amount` Decimal(14,2) (**tracked separately from `total` so the undisputed balance stays payable - §8.7**), `description`,
      `supplier_contact`, `raised_at` `auto_now_add`, `due_date` null, `resolved_at` `editable=False`, `resolution` blank, `resolution_note`
- [ ] `Meta`: `ordering = ["-raised_at"]`, `unique_together = ("tenant","number")`, indexes `["tenant","status","due_date"]`, `["tenant","supplier"]`

## Status lifecycle & allowed transitions (research §4 - enforce in the VIEW, not the model)
- [ ] `draft` -> parked / captured; `parked` -> draft / captured; `captured` -> blocked / pending_approval (set by `run_match()`); `blocked` -> pending_approval (**authorised
      override only, `@tenant_admin_required`, writes an `accepted` variance resolution**) / disputed (requires >=1 open variance); `disputed` -> blocked / pending_approval / void;
      `pending_approval` -> approved / blocked (sent back); `approved` -> scheduled / void / reversed; `scheduled` -> paid / approved (run rejected); `paid` -> reversed
      (**reversing entry, never edits the original**); **any non-terminal -> void**
- [ ] **`pending_approval -> approved` is the ONLY transition that writes `accounting.Bill` + `JournalEntry`**, inside `transaction.atomic()`, guarded by
      `if invoice.journal_entry_id: return` (§8.10 - double-click / back button / re-approval)
- [ ] `is_locked` ⇔ status in `("paid","void","reversed")` - mirrors `Bill.is_locked`

## Tolerance constants & match algorithm (constants on `SupplierInvoice`, the `PRICE_TOLERANCE_PCT` idiom)
- [ ] `PRICE_TOL_PCT_UPPER = 2.00`, `PRICE_TOL_PCT_LOWER = None` (no floor - under-billing is not a risk), `PRICE_TOL_ABS_UPPER = 50.00`
- [ ] `QTY_TOL_PCT_UPPER = 0.00` (invoiced vs **received** - never pay for more than arrived), `QTY_TOL_ABS_UPPER = 0`, `QTY_TOL_PCT_UPPER_NO_GRN = 5.00`, `QTY_TOL_PCT_LOWER = 5.00`
- [ ] `TOTAL_TOL_PCT = 1.00`, `TOTAL_TOL_ABS = 25.00`, `FX_TOL_PCT = 1.00`, `TAX_TOL_ABS = 1.00`, `DATE_TOL_DAYS = 5`, `DUPLICATE_WINDOW_DAYS = 90`, `DISCOUNT_GRACE_DAYS = 0`, `DISCOUNT_ANNUALISATION_DAYS = 360`
- [ ] **Where both a % and an absolute band apply, the MORE RESTRICTIVE wins** (6.12's `ReceiptTolerancePolicy` rule)
- [ ] `run_match()` per line, this order, **FIRST BREACH WINS**: 1 `missing_po` (basis != none and no `po_line`) -> block; 2 `missing_receipt` (basis=quantity, no `receipt_line`)
      -> compare vs ordered using `QTY_TOL_PCT_UPPER_NO_GRN`; 3 `quantity` vs `receipt_line.quantity_received` **AND** cumulative invoiced vs cumulative received;
      4 `over_invoice` (cumulative invoiced > ordered + allowance) -> block; 5 `price` vs `po_line.unit_price`
- [ ] 6 Header level: `total_amount`, `fx_rate` (**only when `currency` != PO currency**), `tax` (**absolute band only, never a % - tax rounding must never block an invoice**, §8.2)
- [ ] 7 `duplicate` - flag `duplicate_suspect`, **never auto-reject** (a legitimate re-invoice after a credit memo trips every heuristic). Score: normalised number exact +
      amount ±1% + date within `DUPLICATE_WINDOW_DAYS`
- [ ] Outcomes: all inside band -> `auto_accept` -> advance to `pending_approval`; any `block` -> status `blocked` (+ exceptions board); `warn` -> advances but is listed
- [ ] `match_basis="amount"` **skips steps 2-4** (service / PO-less, 2-way against PO value); `match_basis="none"` skips matching and **requires a `gl_account` on every line**;
      credit memos (negative total) **never run a normal three-way match** and are excluded from every cumulative aggregation (§8.6)
- [ ] Cumulative qty aggregated across **all non-terminal invoices** and all `status="received"` GRNs for the same `po_line`, derived every time - not cached
- [ ] **L40 §3 "same tenant is not the same subject"**: when an invoice is matched to a PO and a GRN, validate they agree on **VENDOR**
      (`invoice.vendor_id == po.vendor_id == grn.vendor_id`), not merely on tenant - emit a `block` variance and refuse to advance on a mismatch
- [ ] **L38**: usable with ZERO stock/inventory configuration - no hard dependency on a stock location; a line with no receipt degrades to the no-GRN band, not a crash

## Discount maths (research §5.3 - exact formulas)
- [ ] `discount_date = invoice_date + payment_term.discount_days`; `due_date = invoice_date + payment_term.days_due`; `discount_expiry_date = discount_date + discount_grace_days`
- [ ] `discount_base_amount = subtotal if discount_base == "net_of_tax" else total`; `discount_amount = discount_base_amount × payment_term.discount_pct / 100`
- [ ] `payable_if_discounted = total − discount_amount`; `days_to_discount = discount_expiry_date − today`
- [ ] `capturable = days_to_discount >= 0 AND status in (approved, scheduled) AND amount_paid == 0` (**a `blocked`/`disputed` discount is noise, not opportunity - §8.9**)
- [ ] `annualised_pct = discount_pct / (100 − discount_pct) × (DISCOUNT_ANNUALISATION_DAYS / (days_due − discount_days))` - 2/10 Net 30 -> 2/98 × 360/20 = **36.7%** (asserted in tests)
- [ ] Dashboard sorted `annualised_pct` DESC then `discount_amount` DESC

## Backend package tasks (`apps/procurement/{models,forms,views,urls}/InvoiceVoucherManagement/`)
- [ ] `models/…/`: `__init__.py`, `SupplierInvoices.py`, `SupplierInvoiceLines.py`, `MatchVariances.py`, `InvoiceDisputes.py`
- [ ] `forms/…/`: `SupplierInvoices.py` (header form + `SupplierInvoiceLineFormSet`), `MatchVariances.py`, `InvoiceDisputes.py`, `Capture.py`. Every money field uses
      **`forms.DecimalField(max_digits=…, min_value=0)`** (L35 - hand-parsed Decimal needs `is_finite()`, a magnitude cap vs `max_digits`, and an explicit rejection branch)
- [ ] `views/…/`: `SupplierInvoices.py`, `MatchVariances.py`, `InvoiceDisputes.py`, `PaymentSchedule.py`, `DiscountOpportunities.py`, `Dashboard.py`
- [ ] `urls/…/`: one module per entity + `__init__.py` concatenating them, **literal routes BEFORE `<int:pk>`** (first-match-wins)
- [ ] `models/__init__.py` - re-export all four models + every CHOICES tuple the templates use, add to `__all__` (surgical `Edit` - a concurrent session may be in this tree, L43)
- [ ] `forms/__init__.py` + `views/__init__.py` - re-export **every** new name (a missing view is an `AttributeError` at URLconf import, not at request time)
- [ ] `urls/__init__.py` - `from .InvoiceVoucherManagement import urlpatterns as _ivm_invoicevoucher`, splat LAST; extend the docstring's segment inventory with the new first
      segments (`supplier-invoices/`, `match-variances/`, `invoice-disputes/`, `payment-schedule/`, `discount-opportunities/`, `capture/`, `duplicates/`, `invoice-vouchers/`)
      and collision-check each against the list at `urls/__init__.py:7-15`
- [ ] `admin.py` - register `SupplierInvoice`, `InvoiceMatchVariance`, `InvoiceDispute` (+ `SupplierInvoiceLine` inline); `readonly_fields` covering every `editable=False` stamp
      (L22: system stamps stay on the model + detail page but OUT of `Meta.fields`)

## Views & routes (namespace `procurement`) - CONTEXT KEYS ARE THE CONTRACT
Every view: `@login_required`, `filter(tenant=request.tenant)` (child tables `filter(invoice__tenant=…)`), never `.all()`. Privileged transitions (approve / post / void /
reverse / admin override) use **`@tenant_admin_required`**, not bare `@login_required` (L27). Every FK/int filter guarded with `.isdigit()` **and** unit-tested on its POSITIVE path (L11/L44).
- [ ] `supplierinvoice_list` -> `rows`, `page_obj`, `status_choices`, `match_status_choices`, `vendors`, `sources`, `stats`, echoed GET params
- [ ] `supplierinvoice_detail` -> `invoice`, `lines`, `variances`, `disputes`, `bill`, `journal_entry`, `duplicate_candidates`, `discount` (dict: `base_amount`/`amount`/`payable_if_discounted`/`days_to_discount`/`annualised_pct`), `allowed_transitions`, `is_locked`, `tolerances`
- [ ] `supplierinvoice_create` / `_update` -> `form`, `line_formset`, `invoice`, `title`, `submit_label`, `cancel_url`
- [ ] `supplierinvoice_delete` -> `invoice`, `title`, `cancel_url` (**the confirm string must use the system-assigned `SIV-` number, never `invoice_number` or the vendor name - L42**)
- [ ] `supplierinvoice_capture` (GET review + POST confirm) -> `form`, `document`, `extraction` (dict field -> `{"value","confidence"}`), `confidence`, `source`, `has_text_layer`, `warnings`, `raw_text`, `cancel_url`
- [ ] `supplierinvoice_duplicates` -> `groups`, `page_obj`, `window_days`, `stats`
- [ ] `supplierinvoice_match` (`@require_POST`) -> redirect only; `…_revalidate` (`@require_POST`, `@tenant_admin_required`) -> redirect + `messages`
- [ ] `matchvariance_list` -> `rows`, `page_obj`, `variance_type_choices`, `outcome_choices`, `resolution_choices`, `bases`, `stats`, echoed GET params
- [ ] `matchvariance_detail` -> `variance`, `invoice`, `invoice_line`, `dispute`, `explanation`, `tolerance` (`abs`/`pct`), `actions`
- [ ] `invoicedispute_list` -> `rows`, `page_obj`, `status_choices`, `reason_choices`, `suppliers`, `assignees`, `stats`, echoed GET params
- [ ] `invoicedispute_detail` -> `dispute`, `invoice`, `invoice_line`, `variances`, `resolution_choices`, `days_open`, `is_overdue`, `actions`
- [ ] `invoicedispute_create` / `_update` -> `form`, `dispute`, `invoice`, `title`, `cancel_url`
- [ ] `invoicedispute_resolve` (`@require_POST`, `@tenant_admin_required`) -> redirect + `messages`
- [ ] `invoicedispute_aging` -> `buckets`, `page_obj`, `today`, `stats`, `bucket_choices`
- [ ] `paymentschedule_list` -> `buckets`, `page_obj`, `total_payable`, `terms`, `currency`, `vendors`, `stats`, `horizon_weeks`, echoed GET params
- [ ] `discountopportunity_list` -> `rows`, `page_obj`, `totals` (`capturable`/`expiring_7d`/`missed`), `annualisation_days`, `stats`, `sort`
- [ ] `invoicevoucher_dashboard` -> `tiles`, `stats`, `recent`, `blocked`, `expiring`, `open_disputes`, `aging`

## Templates (`templates/procurement/InvoiceVoucherManagement/`)
- [ ] **PRE-WRITE GATE (L33): grep `static/css/theme.css` before writing ANY badge or layout class.** Only `badge-green`, `badge-red`, `badge-amber`, `badge-info`,
      `badge-muted`, `badge-slate` exist - `badge-success` / `-warning` / `-danger` render UNSTYLED. `stat-icon` supports only `blue/green/orange/purple/slate`.
      `.detail-label` / `.detail-value` DO NOT EXIST - the real shape is `<dl class="detail-grid"><div class="detail-item"><dt>…</dt><dd>…</dd></div></dl>`
- [ ] Pagination guarded by `{% if page_obj.has_previous %}` / `has_next` (L9) - never emit `previous_page_number` / `next_page_number()` unconditionally
- [ ] Multi-line comments use `{% comment %}…{% endcomment %}`; `{# … #}` is single-line only or it leaks as visible text (L2/L3)
- [ ] `{{ obj.approved_by.get_full_name|default:obj.approved_by.username }}` wrapped in `{% if obj.approved_by %}` - it raises when the FK is None (L10).
      Same for `assigned_to`, `raised_by`, `vendor`
- [ ] `supplierinvoice/{list,detail,form}.html` - register / header + lines + variances + disputes + attachment / header + line formset
- [ ] `invoicedispute/{list,detail,form}.html` - register + aging link / audit trail + resolve actions / raise-or-edit
- [ ] `matchvariance/{list,detail}.html` - exceptions board / one variance, expected vs actual
- [ ] Standalone: `capture.html`, `duplicates.html`, `match_board.html`, `payment_schedule.html`, `discount_opportunities.html`, `dispute_aging.html`, `dashboard.html`

## Wire-up
- [ ] `apps/core/navigation.py` - **exactly ONE** new `LIVE_LINKS["6.13"]` dict inserted after `"6.12"` (ends at `:1593`), bullet text copied EXACTLY from NavERP.md 1081-1085:
      ```
      "Invoice Capture (OCR)":               "procurement:supplierinvoice_capture",
      "Three-Way Matching":                  "procurement:matchvariance_list",
      "Dispute Resolution Workflow":         "procurement:invoicedispute_list",
      "Payment Schedule/Terms Management":   "procurement:paymentschedule_list",
      "Early Payment Discount Tracking":     "procurement:discountopportunity_list",
      ```
      plus a comment block recording (a) that bullet 1 is Assisted Capture, not OCR, and (b) that `supplierinvoice_list` and `invoicevoucher_dashboard` are reached from the
      pages above rather than getting their own bullet (L31 - one entry, five bullets)
- [ ] Every bullet lands on a page **STAFF can reach** - no login-gated vendor-portal view (L32)
- [ ] `config/settings.py` / `config/urls.py` - **NO CHANGE** (existing app)
- [ ] `views/_helpers.py` - do NOT touch `PROCUREMENT_CONTENT_MODELS` (that is the scm-app whitelist; `app_label="procurement"` rows are already covered)

## Seeder (`management/commands/seed_procurement.py` - add `_seed_invoice_voucher(tenant)`)
- [ ] 5 `accounting.PaymentTerm` (Net 30, Net 60, 2/10 Net 30, 1/15 Net 45, 3/7 Net 60) via `get_or_create(tenant=…, name=…)`
- [ ] 6 `scm.PurchaseOrder` + lines across 4 vendors (>=2 multi-line); 8 `scm.GoodsReceiptNote` + lines deliberately uneven (1 full, 1 partial 60%, 1 partial-then-completed,
      1 over-receipt 110%, 1 with `quantity_rejected > 0`, 2 POs with NO receipt)
- [ ] **14 `SupplierInvoice`** covering EVERY status (1 draft, 1 parked, 2 captured, 2 blocked, 2 disputed, 2 pending_approval, 2 approved, 1 scheduled, 1 paid)
      + 1 `credit_memo` (negative total), 1 `debit_memo`, 2 `service` (PO-less, `match_basis="amount"`), 1 `source="pdf_text_layer"` with `extraction_confidence=87.50`,
      1 with `duplicate_of` set
- [ ] **>25 `SupplierInvoiceLine`** (~38) so pagination is actually exercised (L9); non-PO lines carry a `gl_account`; >=1 line sets the new optional `item` FK
- [ ] ~16 `InvoiceMatchVariance` - **at least one of EACH `variance_type`**, outcomes mixed auto_accept / warn / block, resolutions mixed incl. 3 `credit_memo`
- [ ] 6 `InvoiceDispute` - one per distinct `reason_code` except `other`; 2 `open` past `due_date` (lights up aging), 1 `awaiting_supplier`, 1 `escalated`, 2 `resolved`
- [ ] 14 `core.Document` placeholders (**seeders write no media files**) and 2 `accounting.Bill` rows (the `paid` + one `approved`) so the ledger bridge is demonstrable
- [ ] **`invoice_date` relative to today** (`timezone.localdate() - timedelta(days=n)`; L16 - never `datetime.date.today()` and never hardcoded), else the discount dashboard
      shows zero opportunities the moment the demo ages
- [ ] Idempotent: existence-check before **every** `.create()`; run twice with no new rows

## Verification checklist
- [ ] `makemigrations procurement` -> exactly **0020** (rename the file if Django picks another suffix); then `migrate`; `manage.py check` clean; seeder runs twice clean
- [ ] Every view renders 200/302 as `admin_acme` / `password`, including **unbound** forms (L39 - check the feature's preconditions can be true simultaneously; test the GET, not just the POST)
- [ ] **Blank-page proof**: every context key listed above asserted present and non-empty - an unpinned key renders a blank page at HTTP 200
- [ ] Filters: each valid choice value returns the RIGHT rows (positive path, L11/L44) AND junk params (`?status=nope&vendor=abc&variance_type=zzz`) still 200; `?page=2` guarded
- [ ] Cross-tenant IDOR: an `admin_globex` invoice / variance / dispute pk returns **404** on detail/edit/delete and on every verb
- [ ] Verbs reject GET (405); a non-admin user is refused on approve / void / reverse / revalidate / resolve (`@tenant_admin_required`, L27)
- [ ] **L42**: a seeded invoice whose `invoice_number` contains an apostrophe deletes with the confirm dialog intact (the confirm string must be the `SIV-` number)
- [ ] **L33**: grep the rendered HTML for `badge-success|badge-warning|badge-danger|detail-label|detail-value` -> zero hits; `{#` / `{% comment` not leaking as text
- [ ] **L40 §3**: matching an invoice to a PO and a GRN from a DIFFERENT vendor blocks with a vendor-mismatch variance and does not advance
- [ ] **L38**: with zero stock locations configured, a PO-less and a no-receipt invoice both match and page without error
- [ ] **L37 §2 / L29**: approving creates exactly ONE `accounting.Bill` and ONE balanced `JournalEntry` (debits == credits); approving TWICE creates no second entry; a
      `reversed` invoice posts a reversing entry and leaves the original untouched
- [ ] `accounting.Bill` is the only ledger target - no write to `scm.GoodsReceiptNote.bill` from 6.13 (one writer per field; 6.12's `recompute_match()` owns it)
- [ ] Over-invoicing: 3 invoices of 40 against a PO of 100 are each within tolerance individually but the 3rd blocks on the cumulative check
- [ ] Credit memo: negative total, excluded from cumulative aggregation, never runs a 3-way match
- [ ] Discount maths: `2/10 Net 30` -> `annualised_pct == 36.73` (±0.01); only `approved` / `scheduled` rows with `amount_paid == 0` appear as capturable
- [ ] Tests derive dates from `timezone.now().date()` / `timezone.localdate()` (L16); iterate with `--nomigrations` but the FINAL proof run keeps migrations on and is UNFILTERED (L49)
- [ ] Sidebar shows **6.13 as Live with all five bullets resolving** - no `NoReverseMatch`

---
# Sub-module 6.14 - Spend Analytics & Reporting (Module 6: Procurement Management System, `procurement`) - plan from research-procurement-6.14.md  (2026-09-01)

App EXISTS (`apps/procurement/`, 6.1-6.13 built) -> this pass EXTENDS it. **No `config/settings.py` / `config/urls.py` change** (procurement already installed + included; L31/L32).
Sub-module package folder: **`SpendAnalyticsReporting/`** in all four backend layers (PascalCase of the NavERP.md title). Template sub-module folder: **`spendanalytics/`**
(short-slug form, permitted by Template Folder Structure rule 2 - this is FROZEN, do not "correct" it to `spendanalyticsreporting/`). Test subslug: **`spend`**.
Migration **0021 is CLAIMED**, generated LAST (latest on disk is `0020_supplierinvoice_invoicedispute_supplierinvoiceline_and_more.py`). Do not generate or assume another number.
New flat compute module **`apps/procurement/analytics.py`** (Backend Package Structure rule 8 - `analytics.py` stays at the app root, as in `apps/crm/analytics.py` / `apps/scm/analytics.py`). It does not exist today.
Number prefixes **`MSF`** (MaverickSpendFinding) and **`SPR`** (SpendReport) - re-verify free across `apps/` before the first migration (existing procurement prefixes: CUB RQA POE CMI EBID VSU PCI EAUC VPA CAM RXR VIS RFX PCO RQT RAM SEV DSC DSP BID RDS SIV ASN RTV BKO).

## Scope decision (FROZEN by Phase 1 - do not re-litigate)
**Four models in THREE entity files** + **five computed pages with NO new table**. 6.14 is an analytics pass: it READS spend that already exists and never posts to the ledger (L29).
- [ ] `SpendClassificationRule` (TenantOwned, no number) - `models/SpendAnalyticsReporting/SpendClassificationRules.py`
- [ ] `MaverickSpendFinding` [`MSF-`] (TenantNumbered) - `models/SpendAnalyticsReporting/MaverickFindings.py`
- [ ] `SpendReport` [`SPR-`] (TenantNumbered) **+ `SpendReportSnapshot`** (plain child) - **ONE file**, `models/SpendAnalyticsReporting/SpendReports.py` (Backend rule 2: an entity file owns the primary model plus its children)
- [ ] Computed pages, no table: `spend_dashboard`, `category_spend`, `classification_workbench`, `maverick_dashboard`, `spend_export`

## Spine: READ, never re-declare (every target grep-verified this pass, L28/L36)
- [ ] `scm.SupplierContract` (`apps/scm/models/SupplierRelationshipManagement/SupplierContracts.py:13`) - `party` FK (NOT `vendor`), `status` in draft/active/expiring/expired/terminated/renewed, `start_date`/`end_date`, `is_expiring_soon()`, `days_to_expiry()`.
      **There is NO `Contract` model in `apps/procurement`** - `ContractsManagement/` holds only clause links, signers, milestones and amendments hanging off `scm.SupplierContract`.
- [ ] `scm.ItemCategory` (`InventoryManagement/Items.py:34`) - `name`/`parent`/`description`/`is_active`, tenant-scoped, CRUD already at `scm:category_list`. **The ONLY taxonomy. Do NOT declare a `SpendCategory`.**
      `procurement.CatalogItem.category_text` is a free-text CharField(120) (`CatalogItems.py:81`) - never treat it as a taxonomy key.
- [ ] `procurement.SupplierInvoice` (`InvoiceVoucherManagement/SupplierInvoices.py:123`) + `SupplierInvoiceLine` (`SupplierInvoiceLines.py:56`) - the primary spend fact
- [ ] `scm.PurchaseOrder` (`ProcurementManagement/PurchaseOrders.py:15`) + `PurchaseOrderLine` (`:172`) - the committed basis
- [ ] `core.Party` (vendors are `Party` + `PartyRole` - never re-declare a vendor), `core.OrgUnit` (`kind` incl. `department`/`cost_center`), `accounting.GLAccount`, `accounting.Currency` (**GLOBAL, no tenant column - never tenant-filter it**)
- [ ] `procurement.CatalogItem` / `CatalogPriceTier` (`is_preferred`, `status`, `supplier`, `item`, `supplier_part_no`, `base_price`, `contract`; tier `min_quantity`/`unit_price`/`discount_pct`/`valid_from`/`valid_until`/`effective_price(base)`) - the maverick benchmark
- [ ] `procurement.VendorSuspension` (`supplier`, `starts_on`, `ends_on`, `status` incl. `active`) - the blocked-supplier reason
- [ ] **NO widget-preference model** - 6.1 `DashboardPortal/WidgetPreferences.py:18` already owns `WidgetPreference` and its `WIDGETS` already carries a `"spend": "Spend Summary"` key
- [ ] **NO second scheduler table** - `accounting.ScheduledReport` already models scheduled delivery and already defers its worker
- [ ] **NO FX-rate table exists** - sum per currency and raise a `mixed_currency` flag; never invent a rate

## Spend basis (FROZEN)
- [ ] **Primary = invoiced (recognised) spend**: `SupplierInvoiceLine` filtered `invoice__status__in ("approved","scheduled","paid")`. Statuses `draft/parked/captured/blocked/disputed/pending_approval/void/reversed` are EXCLUDED.
- [ ] **Secondary = committed PO spend**, a `?basis=committed` toggle: `PurchaseOrderLine` filtered `purchase_order__status__in SPEND_PO_STATUSES` = `("approved","sent","acknowledged","partially_received","received","closed")` - **copied verbatim from `scm/analytics.py:200`** so 4.11 and 6.14 can never disagree
- [ ] **Credit memos are already signed negative** (`SupplierInvoiceLines.py` has no `MinValueValidator`; `SupplierInvoices.py:407-416` signs them) - a plain `Sum("line_total")` nets. **Do NOT special-case them anywhere.**
- [ ] `PurchaseOrder.order_date` is NULLABLE - the committed basis annotates `doc_date=Coalesce("purchase_order__order_date", TruncDate("purchase_order__created_at"))` and filters on that, so an unstamped PO is never silently dropped
- [ ] **`PurchaseOrderLine` has NO `item` FK** (re-verified: it carries `item_description` Char(255) + `sku_hint` Char(64) + `gl_account` only). The category axis is therefore INVOICED-ONLY; on the committed basis
      `dimension=category` resolves through rules (vendor/gl_account/keyword/org_unit) and otherwise falls to `(Unclassified)`. Say so on the page - do not fake it.

## The department axis is WEAK - mandatory handling
- [ ] Path: `Coalesce(invoice__purchase_order__requisition__org_unit, invoice__purchase_order__ship_to)` -> `core.OrgUnit`. A 3-hop nullable chain: **NULL for every PO-less invoice**.
- [ ] **Every department breakdown MUST render an explicit `(unassigned)` bucket** (constant `UNASSIGNED_LABEL = "(unassigned)"`) rather than dropping those rows, and MUST print the caveat on the page
      (the `GL_AXIS_CAVEAT` precedent in `scm/analytics.py`). A breakdown that silently drops rows makes the totals disagree with the KPI strip - that is the bug users report first.

## Naming honesty - two BANS, enforced in code review (the 6.13 "Assisted Capture" precedent)
- [ ] **"drag and drop" is BANNED** from model help_text, views, templates, sidebar labels, docstrings and commit messages. NavERP ships a **guided Report Builder**: measure, up to two dimensions, grain,
      filters, Top-N and chart type chosen from **dropdowns**, rendered server-side. Put a one-line note on the builder page saying dimensions are **selected, not dragged**. Only Zycus names drag-and-drop; the other nine say self-service / configurable / ad-hoc.
- [ ] **PowerBI / BI-feed integration is NOT implemented.** Only CSV/XLSX download ships. `spend_export` must state that plainly on the page. **Never put "PowerBI" in a sidebar label or a button that only downloads a CSV.**
- [ ] Related: never label the rules engine "AI" or "ML" - it is explicit, readable, auditable rules (the honest Ivalua-style differentiator). The page says the rules are explicit, not learned.

## Do NOT collide with SCM 4.11 (`scm:spend_analytics`, `LIVE_LINKS["4.11"]` -> "Procurement Analytics")
- [ ] 4.11 already ships the **PO-based** cube (`apps/scm/analytics.py` §8, `:1369-1866`): `_r_spend_total`, `_r_spend_off_contract_pct`, `_r_spend_top_supplier_share_pct`, `_r_spend_tail_share_pct`, `_r_savings_negotiated`, `_r_savings_price_variance_opportunity`, cycle/lead time.
- [ ] 6.14's cube is the **INVOICED twin** plus classification and findings. Every 6.14 url name (`spend_dashboard`, `category_spend`, ...), template path (`templates/procurement/spendanalytics/...`) and sidebar label (the five NavERP.md bullets) is distinct from 4.11's.
- [ ] `spend_dashboard` **links out to `scm:spend_analytics`** for the committed-basis savings and cycle-time narrative rather than restating it. Same for tail share: 6.14 computes the invoiced twin and links across.

## Model 1 - `SpendClassificationRule` (`models/SpendAnalyticsReporting/SpendClassificationRules.py`)
`TenantOwned`, **no number** (config, not a document - the `ApprovalRoutingRule` / `ReceiptTolerancePolicy` precedent). Drivers: *spend classification into a taxonomy* (all 10 leaders), *business-managed auditable rules* (Ivalua, SAP Ariba, GEP), *% of spend classified* KPI (Sievo, SpendHQ, JAGGAER).
- [ ] `MATCH_TYPE_CHOICES = [("vendor","Supplier"), ("gl_account","GL Account"), ("keyword","Description / SKU keyword"), ("invoice_type","Invoice Type"), ("org_unit","Department / Cost Centre")]`
- [ ] `APPLIES_TO_CHOICES = [("both","Invoiced + Committed"), ("invoiced","Invoiced only"), ("committed","Committed (PO) only")]`
- [ ] Fields: `name` Char(120); `match_type` Char(20) default `vendor`; `vendor` FK `'core.Party'` SET_NULL null blank `related_name="procurement_spend_rules"`; `gl_account` FK `'accounting.GLAccount'` SET_NULL null blank
      `related_name="procurement_spend_rules"`; `org_unit` FK `'core.OrgUnit'` SET_NULL null blank `related_name="procurement_spend_rules"`; `keyword` Char(120) blank; `invoice_type` Char(20) blank
      (validated in `clean()` against `SupplierInvoice.INVOICE_TYPE_CHOICES` - standard/credit_memo/debit_memo/prepayment/service); `category` FK `'scm.ItemCategory'` **PROTECT** `related_name="procurement_spend_rules"`;
      `priority` PosSmallInt default 100 (**lower wins**, ties broken by `id` so resolution is deterministic); `applies_to` Char(10) default `both`; `is_active` Bool default True; `notes` TextField blank
- [ ] System stamps, **`editable=False`**, written only by preview/apply: `match_count` PosInt default 0; `last_matched_at` DateTime null blank
- [ ] `clean()`: (a) the field required by `match_type` must be set - a `vendor` rule with no vendor matches EVERYTHING; (b) cross-tenant guard on `vendor` / `gl_account` / `org_unit` / `category` (L40 §3 - same tenant is not the same subject)
- [ ] Methods: `matches(line, basis)` (pure, unit-testable, works on both a `SupplierInvoiceLine` and a `PurchaseOrderLine` - the keyword match reads `description`/`sku_hint` on invoice lines and `item_description`/`sku_hint` on PO lines);
      `classmethod resolve(line, basis, rules=None)` -> winning `ItemCategory` or `None` (accepts a pre-fetched rule list so a cube pass does ONE query, not one per line); `preview(start, end)` -> `{"count": n, "value": Decimal}`
- [ ] `Meta`: `ordering = ["priority", "id"]`, indexes `["tenant","is_active"]`, `["tenant","match_type"]`
- [ ] **Form `SpendClassificationRuleForm.Meta.fields`** = `["name","match_type","vendor","gl_account","org_unit","keyword","invoice_type","category","priority","applies_to","is_active","notes"]`
- [ ] **EXCLUDED from the form**: `tenant`, `match_count`, `last_matched_at`, `created_at`, `updated_at` (L22 - system stamps stay on the model and the detail page but OUT of `Meta.fields`)
- [ ] Form `__init__` narrows every FK queryset to `tenant=self.tenant`: `vendor` -> `Party` with a supplier `PartyRole`, `gl_account` -> `GLAccount.objects.filter(tenant=…, is_active=True)`, `org_unit` -> `OrgUnit.objects.filter(tenant=…)`, `category` -> `ItemCategory.objects.filter(tenant=…, is_active=True)`

## Model 2 - `MaverickSpendFinding` [`MSF-`] (`models/SpendAnalyticsReporting/MaverickFindings.py`)
`TenantNumbered`, `NUMBER_PREFIX = "MSF"`. Drivers: the umbrex maverick-spend playbook rule set, *maverick dashboards* (SAP Ariba, Coupa), *off-contract leakage* (JAGGAER), *compliance monitoring + remediation workflow* (Ivalua).
- [ ] `REASON_CHOICES` - all EIGHT, verbatim:
      `[("no_contract","No active contract"), ("po_less_invoice","Invoice with no purchase order"), ("no_requisition","PO raised with no requisition"), ("off_catalog","Item not on an approved catalogue"), ("non_preferred_vendor","Bought from a non-preferred supplier"), ("price_above_contract","Price above the contracted/catalogue price"), ("suspended_vendor","Supplier was blocked or suspended"), ("split_purchase","Orders split below an approval threshold")]`
- [ ] `SEVERITY_CHOICES = [("low","Low"),("medium","Medium"),("high","High")]` + class constant `SEVERITY_BY_REASON` default map (constants, not a policy table - the `SupplierInvoice` tolerance-band precedent)
- [ ] `STATUS_CHOICES = [("open","Open"),("acknowledged","Acknowledged"),("justified","Justified - accepted"),("remediated","Remediated"),("dismissed","Dismissed - false positive")]` default `open`
- [ ] Source pointers, all `SET_NULL` null blank, **`clean()` requires at least one**: `supplier_invoice` FK `'procurement.SupplierInvoice'` `related_name="maverick_findings"`; `invoice_line` FK `'procurement.SupplierInvoiceLine'` `related_name="maverick_findings"`; `purchase_order` FK `'scm.PurchaseOrder'` `related_name="procurement_maverick_findings"`
- [ ] Dimensions **stamped at detection** so the dashboard groups in one query with no four-way join: `vendor` FK `'core.Party'` PROTECT (**always set**) `related_name="procurement_maverick_findings"`; `category` FK `'scm.ItemCategory'` SET_NULL null blank
      `related_name="procurement_maverick_findings"`; `org_unit` FK `'core.OrgUnit'` SET_NULL null blank `related_name="procurement_maverick_findings"`; `contract` FK `'scm.SupplierContract'` SET_NULL null blank
      `related_name="procurement_maverick_findings"` ("the agreement this should have been on"); `catalog_item` FK `'procurement.CatalogItem'` SET_NULL null blank `related_name="maverick_findings"` (the preferred alternative, for `non_preferred_vendor` / `price_above_contract`)
- [ ] Money + window: `document_date` DateField **db_index** (the invoice/order date the window filters on); `amount` Decimal(18,2) default 0 - **EDITABLE** (a hand-raised finding must be able to state the spend at risk;
      the scanner overwrites it from the source document); `benchmark_amount` Decimal(18,2) null blank ("what it should have cost"); `leakage_amount` Decimal(18,2) default 0 **`editable=False`**, DERIVED in `save()` as `max(0, amount - benchmark_amount)` when a benchmark exists, else 0
- [ ] `is_addressable` Bool default True - the umbrex denominator exclusion (categories with no approved channel: taxes, utilities, payroll, pre-approved exceptions). Class constant `NON_ADDRESSABLE_GL_CODES` seeds the default at detection time.
- [ ] Governance: `dedupe_key` Char(120) **`editable=False`** with `unique_together = ("tenant","dedupe_key")` so a re-scan **UPDATES** rather than duplicates; `detail` TextField (human-readable "why", written by the detector);
      `detected_at` DateTime `auto_now_add`; `status` default `open`; `resolution_note` TextField blank; `resolved_by` FK `AUTH_USER_MODEL` SET_NULL null blank **`editable=False`** `related_name="procurement_maverick_findings_resolved"`; `resolved_at` DateTime null blank **`editable=False`**
- [ ] `dedupe_key` built deterministically in `save()` when blank: `f"{reason}:inv:{supplier_invoice_id}"` / `:line:{invoice_line_id}` / `:po:{purchase_order_id}`, and for `split_purchase` `f"split:{vendor_id}:{window_start:%Y%m%d}"`.
      `clean()` pre-checks the computed key against the tenant's rows and raises a friendly `ValidationError` instead of letting the unique constraint 500 a manual create.
- [ ] Detection constants ON THE CLASS: `PRICE_TOLERANCE_PCT = Decimal("5.00")` (umbrex), `SPLIT_WINDOW_DAYS = 30`, `SPLIT_MIN_ORDERS = 3`, `COVERING_CONTRACT_STATUSES = ("active","expiring")` (matching `scm/analytics.py:204`), `NON_ADDRESSABLE_GL_CODES = (...)`
- [ ] `classmethod scan(tenant, start, end, reasons=None, user=None)` -> `{reason: count}`. Runs the enabled checks, **upserts on `dedupe_key`**, never mints a duplicate, and never re-opens a `justified`/`dismissed`/`remediated` finding
      (it updates the amount/detail and leaves the disposition alone - without that the worklist is abandoned within a month). Wrapped in `transaction.atomic()`.
- [ ] Detector shapes (all fields verified): `no_contract` = `Exists()` on `SupplierContract` with `status__in COVERING_CONTRACT_STATUSES` whose `start_date`/`end_date` window covers the document date (the `scm/analytics.py:1461-1467` shape);
      `po_less_invoice` = `purchase_order_id IS NULL AND invoice_type != "credit_memo"`; `no_requisition` = `PurchaseOrder.requisition_id IS NULL`; `off_catalog` = no approved+active `CatalogItem` for that `item`/`supplier_part_no` at that supplier;
      `non_preferred_vendor` = an approved `CatalogItem` with `is_preferred=True` exists for the same `item`/`supplier_part_no` at a DIFFERENT supplier; `price_above_contract` = `unit_price` exceeds `CatalogPriceTier.effective_price(base)` (else `CatalogItem.base_price`) by more than `PRICE_TOLERANCE_PCT`;
      `suspended_vendor` = an `active` `VendorSuspension` whose `starts_on`/`ends_on` covers the document date; `split_purchase` = `>= SPLIT_MIN_ORDERS` POs to one vendor inside `SPLIT_WINDOW_DAYS`, each below a `PurchaseRequisition.APPROVAL_TIERS` threshold, summing above it
- [ ] **`split_purchase` is the cut line.** It is the most expensive check (a self-join over a rolling window) and the closest to 6.17's fraud-detection territory. The CHOICE ships either way (the schema must not churn later);
      if the build phase overruns, ship the other seven detectors and leave `split_purchase` detection to a follow-up. **A code comment must name the 6.17 boundary** regardless.
- [ ] Verb methods move `status` and NOTHING else moves it: `acknowledge(user)`, `justify(user, note)`, `remediate(user, note)`, `dismiss(user, note)` - each re-checks its own guard and returns a bool (the 6.13 discipline); the three terminal verbs stamp `resolved_by`/`resolved_at`
- [ ] `STATUS_CSS` / `SEVERITY_CSS` badge maps on the model - **only `badge-green|red|amber|info|muted|slate` exist** in `static/css/theme.css:286-291` (L33); `badge-success`/`-warning`/`-danger` render UNSTYLED
- [ ] `Meta`: `ordering = ["-document_date","-id"]`, `unique_together = (("tenant","number"), ("tenant","dedupe_key"))`, indexes `["tenant","status"]`, `["tenant","reason"]`, `["tenant","document_date"]`, `["tenant","vendor"]`
- [ ] **Form `MaverickSpendFindingForm.Meta.fields`** = `["reason","severity","supplier_invoice","invoice_line","purchase_order","vendor","category","org_unit","contract","catalog_item","document_date","amount","benchmark_amount","is_addressable","detail"]`
- [ ] **EXCLUDED from the form**: `tenant`, `number`, `status` (workflow-controlled - moved only by the verbs), `dedupe_key`, `leakage_amount`, `detected_at`, `resolution_note` (written by the verb POST, not the create form), `resolved_by`, `resolved_at`, `created_at`, `updated_at`
- [ ] Every FK queryset narrowed to the tenant in the form's `__init__`; `amount`/`benchmark_amount` are `forms.DecimalField(max_digits=…, decimal_places=2, min_value=0)` (L35 - never hand-parse a Decimal)

## Model 3 - `SpendReport` [`SPR-`] + `SpendReportSnapshot` (`models/SpendAnalyticsReporting/SpendReports.py`)
Shaped **field-for-field on `crm.AnalyticsReport` + `crm.ReportSnapshot`** (`apps/crm/models/AnalyticsReporting/Reports.py:6`, `Snapshots.py:5`) - read both before writing. Drivers: saved ad-hoc self-service reports (Zycus, SAP Ariba, Coupa, JAGGAER, Ivalua, Basware), pre-built report libraries (JAGGAER, Ivalua, SAP Ariba), snapshots for period-over-period comparison (Sievo, SpendHQ).
- [ ] `SpendReport(TenantNumbered)`, `NUMBER_PREFIX = "SPR"`. Fields: `name` Char(120); `description` TextField blank
- [ ] `BASIS_CHOICES = [("invoiced","Invoiced (recognised) spend"),("committed","Committed (PO) spend")]` default `invoiced`
- [ ] `MEASURE_CHOICES = [("net_spend","Net spend"),("transaction_count","Transactions"),("avg_transaction","Average transaction value"),("supplier_count","Distinct suppliers"),("maverick_spend","Maverick spend"),("maverick_pct","Maverick spend %"),("classified_pct","Classified spend %"),("leakage","Contract leakage value")]` default `net_spend`
- [ ] `DIMENSION_CHOICES = [("supplier","Supplier"),("category","Category"),("department","Department / cost centre"),("gl_account","GL account"),("currency","Currency"),("month","Month"),("quarter","Quarter"),("invoice_type","Invoice type"),("none","- none -")]`;
      `dimension_1` default `supplier`, `dimension_2` default `none`. `clean()` refuses `dimension_1 == dimension_2` unless both are `none`.
- [ ] `DATE_RANGE_CHOICES = [("last_30","Last 30 days"),("last_90","Last 90 days"),("quarter","This quarter"),("year","This year"),("all","All time"),("custom","Custom range")]` default `last_90`; `date_from` / `date_to` DateField null blank, **required only when `custom`** (checked in `clean()`, which also refuses `date_from > date_to`)
- [ ] Saved filters: `vendor` FK `'core.Party'` SET_NULL null blank `related_name="procurement_spend_reports"`; `category` FK `'scm.ItemCategory'` SET_NULL null blank `related_name="procurement_spend_reports"`; `org_unit` FK `'core.OrgUnit'` SET_NULL null blank
      `related_name="procurement_spend_reports"`; `gl_account` FK `'accounting.GLAccount'` SET_NULL null blank `related_name="procurement_spend_reports"`; `min_amount` Decimal(18,2) null blank
- [ ] `CHART_TYPE_CHOICES = [("bar","Bar"),("line","Line"),("pie","Pie"),("table","Table only")]` default `bar`; `top_n` PosSmallInt default 20 with `MinValueValidator(1)` + `MaxValueValidator(100)`
- [ ] `is_favorite` Bool default False; `is_shared` Bool default True; `owner` FK `AUTH_USER_MODEL` SET_NULL null blank `related_name="procurement_spend_reports"`; `last_run_at` DateTime null blank **`editable=False`** (system-stamped on render/snapshot - verbatim from `AnalyticsReport`)
- [ ] `Meta`: `ordering = ["-is_favorite","name"]`, `unique_together = ("tenant","number")`, indexes `["tenant","measure"]`, `["tenant","is_favorite"]`
- [ ] `SpendReportSnapshot(models.Model)` - the `crm.ReportSnapshot` shape verbatim: `tenant` FK `'core.Tenant'` CASCADE `related_name="+"` db_index; `report` FK `SpendReport` CASCADE `related_name="snapshots"`; `title` Char(160);
      `generated_by` FK `AUTH_USER_MODEL` SET_NULL null blank `related_name="procurement_spend_report_snapshots"`; `generated_at` `auto_now_add`; `summary` JSONField(default=list, blank=True) = `[{label, value}]` KPI cards;
      `data` JSONField(default=dict, blank=True) = `{columns, rows, chart_type, chart_labels, chart_data}` **rendered as-is with NO recompute**; `row_count` PosInt default 0. `Meta`: `ordering = ["-generated_at"]`, index `["tenant","report"]`
- [ ] **`SpendReportSnapshot` has NO form and NO create/edit view** - it is created ONLY by the `spendreport_snapshot` POST action. It gets a detail page, a CSV export and a POST delete, and is listed inside `spendreport_detail`.
      **Record this exemption in the view docstring** so the CRUD-completeness reviewer sees the reason rather than a gap (it has no list page of its own, so the "every model with a list page" rule does not bind).
- [ ] **Form `SpendReportForm.Meta.fields`** = `["name","description","basis","measure","dimension_1","dimension_2","date_range","date_from","date_to","vendor","category","org_unit","gl_account","min_amount","chart_type","top_n","is_favorite","is_shared"]`
- [ ] **EXCLUDED from the form**: `tenant`, `number`, `owner` (set from `request.user` in the create view), `last_run_at`, `created_at`, `updated_at`

## Compute module - `apps/procurement/analytics.py` (NEW, flat at the app root, SINGLE WRITER)
Import direction is fixed: `analytics.py` imports `models`; **`models` never imports `analytics`**. Written SOLO before the parallel build lanes start (four lanes import from it); no build lane may edit it afterwards.
- [ ] Constants: `RECOGNISED_INVOICE_STATUSES = ("approved","scheduled","paid")`; `SPEND_PO_STATUSES` (verbatim from `scm/analytics.py:200`); `COVERING_CONTRACT_STATUSES = ("active","expiring")`; `MAX_GROUP_ROWS = 25`; `MAX_EXPORT_ROWS = 5000`; `UNASSIGNED_LABEL = "(unassigned)"`; `UNCLASSIFIED_LABEL = "(Unclassified)"`
- [ ] Result contracts lifted from `crm/analytics.py:13-21`: scalar -> `{kind, value, display, max, pct}`; series -> `{kind, labels, data}`; table -> `{kind, columns, rows}`. **Every report result must be JSON-serialisable so a snapshot stores it verbatim and re-renders with no recompute.**
- [ ] `range_bounds(key, date_from=None, date_to=None)` -> `(start, end)` with **`end` EXCLUSIVE**; dates derived from `timezone.localdate()` (L16 - never `datetime.date.today()`)
- [ ] `invoiced_lines(tenant, start, end)` -> `SupplierInvoiceLine.objects.filter(invoice__tenant=tenant, invoice__status__in=RECOGNISED_INVOICE_STATUSES, invoice__invoice_date__gte=start, invoice__invoice_date__lt=end)` - **defined ONCE, used everywhere**
- [ ] `committed_lines(tenant, start, end)` -> `PurchaseOrderLine` narrowed through `purchase_order__tenant` + `purchase_order__status__in=SPEND_PO_STATUSES` + the `doc_date` Coalesce window
- [ ] `spend_cube(tenant, basis, start, end, dimension, top_n)` / `spend_kpis(...)` / `monthly_trend(...)` / `currency_split(...)` (returns `{rows, mixed_currency}` - mirrors `scm/analytics.py:1396`) / `classified_pct(...)` / `maverick_rate(tenant, start, end)` / `compute_report(report)`
- [ ] `_money(v)` / `_num(v)` / `_pct(v)` display helpers, shape lifted from `crm/analytics.py:35-97`
- [ ] Classification resolution order for every cube row: `item__category` passthrough -> else `SpendClassificationRule.resolve(line, basis, rules)` against a SINGLE pre-fetched active-rule list -> else `UNCLASSIFIED_LABEL`. **Never one query per line.**
- [ ] Move `_csv_safe` from `apps/procurement/views/DashboardPortal/SelfServiceReports.py:107` into **`apps/procurement/views/_helpers.py` as `csv_safe`** (Backend rule 5 - a helper used by more than one sub-module lives in `_helpers.py`),
      leave `_csv_safe = csv_safe` in `SelfServiceReports.py` so 6.1's call sites keep working, and import it in 6.14's export views. **Do not re-invent it.** Both edits are Integrate-phase, surgical, single-writer.

## Backend package tasks (`apps/procurement/{models,forms,views,urls}/SpendAnalyticsReporting/`)
All FKs by **string**, never an import (app-registry cycle). Imports inside these packages are **ABSOLUTE** (`from apps.procurement.models import X`). `TenantOwned.tenant` already declares `related_name="+"` - do not give it a per-model related_name; **every other FK needs one**.
- [ ] `models/SpendAnalyticsReporting/`: `__init__.py`, `SpendClassificationRules.py`, `MaverickFindings.py`, `SpendReports.py`
- [ ] `forms/SpendAnalyticsReporting/`: `__init__.py`, `SpendClassificationRules.py`, `MaverickFindings.py`, `SpendReports.py` (no snapshot form - see the exemption above)
- [ ] `views/SpendAnalyticsReporting/`: `__init__.py`, `SpendClassificationRules.py` (CRUD + preview), `MaverickFindings.py` (CRUD + the four disposition verbs), `SpendReports.py` (CRUD + run/snapshot/export/favorite + snapshot detail/export/delete),
      `ClassificationWorkbench.py`, `MaverickDashboard.py`, `Dashboard.py`, `CategorySpend.py`, `SpendExport.py`
- [ ] `urls/SpendAnalyticsReporting/`: one module per views module + `__init__.py` concatenating them, **literal routes BEFORE `<int:pk>`** (first-match-wins is behaviour, Backend rule 6)
- [ ] **Build-wave lane split** (no lane touches a shared file): **A** = SpendClassificationRules (4 layers) + ClassificationWorkbench; **B** = MaverickFindings (4 layers) + MaverickDashboard; **C** = SpendReports (4 layers, incl. the snapshot child);
      **D** = Dashboard + CategorySpend + SpendExport (views/urls only, no model). `analytics.py` is written solo BEFORE the lanes.
- [ ] `models/__init__.py` - re-export `SpendClassificationRule`, `MaverickSpendFinding`, `SpendReport`, `SpendReportSnapshot` (surgical `Edit`, never a rewrite - a concurrent session may be in this tree, L43)
- [ ] `forms/__init__.py` - re-export `SpendClassificationRuleForm`, `MaverickSpendFindingForm`, `SpendReportForm`
- [ ] `views/__init__.py` - re-export **EVERY** new view name (a missing view is an `AttributeError` at URLconf import time, not at request time)
- [ ] `urls/__init__.py` - `from .SpendAnalyticsReporting import urlpatterns as _sar_spendanalytics`, **splatted LAST**; extend the docstring's first-segment inventory with `spend/`, `spend-rules/`, `maverick-findings/`, `spend-reports/`, `spend-report-snapshots/`
      and collision-check each against the existing list at `urls/__init__.py:7-15` (all five are new whole components; this app registers no greedy `<str:…>` converter)
- [ ] `admin.py` - register `SpendClassificationRule`, `MaverickSpendFinding`, `SpendReport` (+ `SpendReportSnapshot` inline or its own ModelAdmin). **`readonly_fields` on EVERY derived stamp**:
      rule -> `match_count`, `last_matched_at`; finding -> `number`, `dedupe_key`, `leakage_amount`, `detected_at`, `resolved_by`, `resolved_at`; report -> `number`, `last_run_at`; snapshot -> `generated_at`, `generated_by`, `summary`, `data`, `row_count`
      (an admin surface that can post or desync a derived value is the same bug 6.13 fixed)

## Views & routes (namespace `procurement`) - CONTEXT KEYS ARE THE CONTRACT
Every view: `@login_required`, `filter(tenant=request.tenant)`, never `.all()`. `crud_list` supplies `object_list` / `page_obj` / `q`; `crud_edit` supplies `form` / `obj` / `is_edit`; `crud_create` supplies `form` / `is_edit`.
The `crud_*` helpers call `write_audit_log` automatically - **every hand-rolled save path (scan, disposition verbs, snapshot) must call `write_audit_log` itself**. Every FK/int GET filter guarded (`crud_list`'s `as_db_int` or an explicit `.isdecimal()`) and unit-tested on its POSITIVE path (L11/L44).
Verbs are `@require_POST`; **`maverick_scan` and every disposition verb are `@tenant_admin_required`** (L27), reached from the page they act on.
- [ ] `spendrule_list` (`spend-rules/`) -> `object_list`, `page_obj`, `q`, `match_type_choices`, `applies_to_choices`, `categories`, `vendors`, `gl_accounts`, `stats` (`total`/`active`/`inactive`/`matched_value`), echoed GET params (`q`, `match_type`, `category`, `is_active`)
- [ ] `spendrule_create` / `spendrule_edit` (`spend-rules/add/`, `spend-rules/<int:pk>/edit/`) -> `form`, `is_edit`, `obj`, `title`, `submit_label`, `cancel_url`. **Accepts prefill GET params from the workbench** (`?match_type=&vendor=&gl_account=&keyword=`) - echoed into `initial`, never trusted as a pk without `.isdecimal()`
- [ ] `spendrule_detail` (`spend-rules/<int:pk>/`) -> `obj`, `rule`, `preview` (`{"count","value","start","end"}`), `recent_matches`, `category`, `can_delete`
- [ ] `spendrule_preview` (`spend-rules/<int:pk>/preview/`, POST) -> redirect + `messages`; stamps `match_count` / `last_matched_at`
- [ ] `spendrule_delete` (`spend-rules/<int:pk>/delete/`, POST) -> redirect to `spendrule_list` (the confirm string uses `rule.name`, HTML-escaped - L42)
- [ ] `maverickfinding_list` (`maverick-findings/`) -> `object_list`, `page_obj`, `q`, `reason_choices`, `status_choices`, `severity_choices`, `vendors`, `categories`, `org_units`, `stats` (`open`/`high`/`value_at_risk`/`leakage`), echoed GET params (`q`, `reason`, `status`, `severity`, `vendor`, `category`, `org_unit`, `addressable`)
- [ ] `maverickfinding_detail` (`maverick-findings/<int:pk>/`) -> `obj`, `finding`, `supplier_invoice`, `invoice_line`, `purchase_order`, `contract`, `catalog_item`, `alternatives` (preferred `CatalogItem` rows), `benchmark` (`{"expected","actual","variance_pct"}`), `allowed_actions`, `is_resolved`, `severity_css`, `status_css`
- [ ] `maverickfinding_create` / `_edit` -> `form`, `is_edit`, `obj`, `title`, `submit_label`, `cancel_url`
- [ ] `maverickfinding_disposition` (`maverick-findings/<int:pk>/disposition/`, POST, `@tenant_admin_required`) -> redirect + `messages`; the posted `action` is validated against `("acknowledge","justify","remediate","dismiss")` and nothing else moves `status`
- [ ] `maverickfinding_delete` (POST) -> redirect to `maverickfinding_list` (confirm string uses the system-assigned `MSF-` number, never free text - L42)
- [ ] `maverick_dashboard` (`spend/maverick/`) -> `by_reason` (`[{reason, label, n, value}]`), `rate` (`{"maverick_value","addressable_value","pct","txn_pct","band"}` - band from the umbrex `<10 / 10-20 / >20` printed on the page), `by_department` (**with the `(unassigned)` bucket**),
      `by_vendor`, `by_category`, `trend` (`{labels, data}` from `TruncMonth("document_date")`), `leakage_total`, `open_findings`, `stats`, `reason_choices`, `range_key`, `start`, `end`, `scan_url`, `exclusions_note`
- [ ] `maverick_scan` (`spend/maverick/scan/`, POST, `@tenant_admin_required`) -> redirect + `messages` with the `{reason: count}` summary; idempotent (re-running updates, never duplicates); calls `write_audit_log`
- [ ] `spendreport_list` (`spend-reports/`) -> `object_list`, `page_obj`, `q`, `measure_choices`, `basis_choices`, `dimension_choices`, `chart_type_choices`, `date_range_choices`, `stats` (`total`/`favorites`/`shared`/`snapshots`), `builder_note` (the "dimensions are selected, not dragged" line), echoed GET params (`q`, `measure`, `basis`, `is_favorite`)
- [ ] `spendreport_detail` (`spend-reports/<int:pk>/`) - **runs the report live** -> `obj`, `report`, `result` (`{summary, columns, rows, chart_type, chart_labels, chart_data}`), `snapshots`, `start`, `end`, `mixed_currency`, `row_cap_note`, `last_run_at`, `export_url`, `snapshot_url`, `builder_note`
- [ ] `spendreport_create` / `_edit` -> `form`, `is_edit`, `obj`, `title`, `submit_label`, `cancel_url`, `builder_note`; create sets `owner = request.user`
- [ ] `spendreport_run` (`spend-reports/<int:pk>/run/`, POST) -> stamps `last_run_at`, redirects to detail
- [ ] `spendreport_snapshot` (`spend-reports/<int:pk>/snapshot/`, POST) -> creates ONE `SpendReportSnapshot` from the freshly computed, JSON-serialisable result; stamps `last_run_at`; `write_audit_log`; redirect + `messages`
- [ ] `spendreport_export` (`spend-reports/<int:pk>/export/`) -> `text/csv` of the report's rows, **filters applied**, every cell through `csv_safe`, capped at `MAX_EXPORT_ROWS`
- [ ] `spendreport_favorite` (POST) -> toggles `is_favorite`, redirects back
- [ ] `spendreport_delete` (POST) -> redirect to `spendreport_list` (confirm string uses the `SPR-` number)
- [ ] `spendreportsnapshot_detail` (`spend-report-snapshots/<int:pk>/`) -> `obj`, `snapshot`, `report`, `summary`, `columns`, `rows`, `chart_type`, `chart_labels`, `chart_data`, `export_url` - **renders `data` as-is, NO recompute**
- [ ] `spendreportsnapshot_export` -> CSV straight from `snapshot.data` with no recompute; `spendreportsnapshot_delete` (POST) -> back to the parent report
- [ ] `spend_dashboard` (`spend/`) -> `kpis` (`net_spend`, `invoice_count`, `supplier_count`, `avg_invoice`, `classified_pct`, `maverick_pct`, `top5_share_pct`, `po_less_share_pct`), `by_supplier`, `by_category`, `by_department` (**`(unassigned)` bucket**), `by_gl_account`,
      `trend` (`{labels, data}`), `currency_rows`, `mixed_currency`, `basis`, `basis_choices`, `range_key`, `date_range_choices`, `start`, `end`, `stats`, `scm_analytics_url` (the link across to 4.11), `department_caveat`, `drill_url_name` (`procurement:supplierinvoice_detail` - link, never re-render 6.13's page)
- [ ] `category_spend` (`spend/categories/`) -> `categories` (the filter queryset), `category` (the selected `ItemCategory` or None), `rows` (supplier league with `total`, `share_pct`, `cumulative_pct` - the **Pareto**), `hhi` (`sum(share^2) * 10000`), `trend`, `item_rows` (`{item, qty, spend, lo, hi, spread}`),
      `consolidation_opportunity`, `sole_source_count`, `tail_rows`, `tail_share_pct`, `abc_rows`, `basis`, `range_key`, `start`, `end`, `stats`, `unclassified_value`, `fallback_note` (says the per-item spread falls back to `sku_hint` when `item` is null)
- [ ] `classification_workbench` (`spend/classification/`) -> `rows` (unclassified spend grouped by `invoice__vendor` / `gl_account` / `sku_hint`, ranked by `Sum("line_total")`), `page_obj`, `classified_pct`, `unclassified_value`, `total_value`, `rules` (active rules, priority order), `group_by`, `group_by_choices`,
      `range_key`, `start`, `end`, `stats`, `create_rule_url` (each row deep-links `spendrule_create` **pre-filled** with that row's match_type + value), `engine_note` (the rules are explicit, never "AI")
- [ ] `spend_export` (`spend/export/`) - **a PAGE, not a bare download** (a sidebar bullet must land on a page) -> `reports`, `snapshots`, `basis`, `basis_choices`, `range_key`, `date_range_choices`, `dimension_choices`, `start`, `end`, `row_count`, `max_rows` (`MAX_EXPORT_ROWS`), `showing_note` ("showing N of M"),
      `download_url`, `bi_note` (**"CSV download today; a live BI / PowerBI feed is not implemented"** - verbatim honesty), `stats`
- [ ] `spend_export_download` (`spend/export/download/`) -> `text/csv`; **the SAME GET params drive the queryset and the CSV** (an export that ignores the active filters is the first bug users report); every cell through `csv_safe`; capped at `MAX_EXPORT_ROWS` with the cap stated in the response filename/notice
      **WARNING: vendor names, line descriptions and rule names are all user-authored and Excel executes a leading `=`/`+`/`-`/`@` on open. Every exported cell goes through `csv_safe`. Do not remove.**

## Templates (`templates/procurement/spendanalytics/`)
- [ ] **PRE-WRITE GATE (L33): grep `static/css/theme.css` before writing ANY badge or layout class.** Only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist (`:286-291`) - `badge-success`/`-warning`/`-danger` render UNSTYLED.
      `stat-icon` supports only `blue/green/orange/purple/slate/red` (`:260-265`). `.detail-label`/`.detail-value` DO NOT EXIST - the real shape is `<dl class="detail-grid"><div class="detail-item"><dt>…</dt><dd>…</dd></div></dl>` (`:354-357`)
- [ ] Pagination guarded by `{% if page_obj.has_previous %}` / `{% if page_obj.has_next %}` (L9) - never emit `previous_page_number` / `next_page_number` unconditionally
- [ ] Multi-line comments use `{% comment %}…{% endcomment %}`; `{# … #}` is single-line ONLY or it leaks as visible text (L2/L3)
- [ ] `{{ obj.owner.get_full_name|default:obj.owner.username }}` wrapped in `{% if obj.owner %}` - it raises when the FK is None (L10). Same for `resolved_by`, `generated_by`, `vendor`, `category`, `org_unit`, `contract`, `catalog_item`
- [ ] Filter bars reflect `request.GET`: strings `{% if request.GET.status == value %}selected{% endif %}`; FK pks `{% if request.GET.category == cat.pk|stringformat:"d" %}selected{% endif %}` (**never `|slugify`**)
- [ ] Every list page gets an Actions column: view (eye) + edit (pencil) + delete (POST form, `{% csrf_token %}`, `onclick="return confirm(...)"`); every detail page gets an Actions sidebar with Edit / Delete / Back to list
- [ ] `spendrule/{list,detail,form}.html` - rule register with a priority column and a "lower priority number wins" hint / one rule + its preview + recent matches / the guided rule form
- [ ] `maverickfinding/{list,detail,form}.html` - findings worklist (reason + severity + status badges, addressable flag) / one finding with the benchmark comparison + the four disposition POSTs / hand-raise-or-edit
- [ ] `spendreport/{list,detail,form}.html` - the saved-report library (favourites first) / live-run result + KPI cards + chart + snapshot list + export button / **the guided Report Builder form with the "dimensions are selected from dropdowns, not dragged" note**
- [ ] `spendreportsnapshot/detail.html` - a frozen snapshot rendered from `data` with no recompute + its CSV link
- [ ] Standalone pages at the sub-module root (no entity folder - Template rule 6): `dashboard.html` (`spend_dashboard`), `category_spend.html`, `classification_workbench.html`, `maverick_dashboard.html`, `export.html` (`spend_export`)
- [ ] Every page that shows a department breakdown renders the `(unassigned)` bucket AND prints `department_caveat`
- [ ] `dashboard.html` carries the explicit cross-link to `scm:spend_analytics` ("committed-basis analytics, savings and cycle time live in SCM 4.11") instead of restating those figures
- [ ] `export.html` prints `bi_note` verbatim. **No template, label, button or comment anywhere contains the phrase "drag and drop" or claims a PowerBI connector.**

## Wire-up
- [ ] `apps/core/navigation.py` - **exactly ONE** new `LIVE_LINKS["6.14"]` dict inserted after the `"6.13"` block (which ends at `:1606`), bullet text copied EXACTLY from NavERP.md lines 1088-1092:
      ```
      "Spend Dashboards":            "procurement:spend_dashboard",
      "Custom Report Builder":       "procurement:spendreport_list",
      "Category Spend Analysis":     "procurement:category_spend",
      "Maverick Spend Tracking":     "procurement:maverick_dashboard",
      "Data Export & Visualization": "procurement:spend_export",
      ```
      plus a comment block recording (a) that "Custom Report Builder" is a **guided** builder, not drag-and-drop; (b) that "Data Export & Visualization" ships **CSV only** - no BI/PowerBI feed;
      (c) that `SpendClassificationRule` CRUD is a **master with no sidebar key** (the `ReceiptTolerancePolicy` / `KpiTarget` precedent), reached from `category_spend` and `classification_workbench`;
      (d) that 4.11's `scm:spend_analytics` remains the **committed/PO** cube and is linked from `spend_dashboard`, not duplicated
- [ ] All five bullets land on **staff-reachable** pages - no login-gated portal view (L32)
- [ ] `config/settings.py` / `config/urls.py` - **NO CHANGE** (existing app)
- [ ] `apps/procurement/views/_helpers.py` - add `csv_safe` (moved from `SelfServiceReports.py`); leave the `_csv_safe` alias behind. Do NOT touch `PROCUREMENT_CONTENT_MODELS` (that is the scm-app whitelist)

## Seeder (`management/commands/seed_procurement.py` - add `_seed_spend_analytics(tenant)`, called last in `handle()` after `_seed_invoice_vouchers(tenant)`)
- [ ] ~8 `SpendClassificationRule` rows covering **every `match_type`** (>=2 vendor, >=2 gl_account, >=2 keyword, 1 invoice_type, 1 org_unit), mapped to EXISTING `scm.ItemCategory` rows (`get_or_create` on `(tenant, name)`), mixed `priority` values so ordering is visibly exercised, >=1 `is_active=False`
- [ ] ~6 `SpendReport` rows forming the pre-built library: spend by supplier, spend by category, spend by department, monthly trend, maverick by reason, unclassified spend - covering >=4 distinct `measure` values, >=1 `basis="committed"`, >=2 `is_favorite=True`
- [ ] 1-2 `SpendReportSnapshot` rows on ONE report, built by **calling the same compute path** the view uses (so the snapshot payload is genuinely re-renderable), with a real `row_count`
- [ ] `MaverickSpendFinding` rows generated by **calling `MaverickSpendFinding.scan(tenant, start, end)`** against the 6.13/6.10 seeded invoices and orders - **never hand-written** - so the seeded data proves the detector works.
      Then hand-move a few dispositions (>=1 each of `acknowledged`, `justified`, `remediated`, `dismissed`) so the worklist filters have rows; leave the rest `open`
- [ ] Verify after seeding that **>=5 of the 8 reason codes** actually fire against the seeded data; if a reason cannot fire, add the minimal source row that makes it fire (e.g. a PO-less service invoice, a suspended-vendor invoice) rather than faking a finding
- [ ] **Every date relative to NOW** (`timezone.localdate() - timedelta(days=n)`; L16 - never `datetime.date.today()`, never hardcoded), else the dashboards show an empty window the moment the demo ages
- [ ] Idempotent: existence-check before **every** `.create()` (`get_or_create` on `(tenant, name)` for rules/reports; `scan()` is already upsert-on-`dedupe_key`); run twice with no new rows and no duplicate findings

## Verification checklist
- [ ] `makemigrations procurement` -> exactly **0021** (rename the file if Django picks another suffix); then `migrate`; `manage.py check` clean; `seed_procurement` runs **twice** with zero new rows the second time
- [ ] `makemigrations --check` reports "No changes detected" after the migration lands
- [ ] Every new view renders 200/302 as `admin_acme` / **`password`**, including **unbound** forms (L39 - test the GET, not just the POST)
- [ ] **Blank-page proof**: every context key pinned above asserted present and non-empty - an unpinned key renders a blank region at HTTP 200 (L8)
- [ ] Filters: each valid choice value returns the RIGHT rows (positive path, L11/L44) AND junk params (`?reason=nope&vendor=abc&category=zzz&basis=xx&range=yy`) still 200; `?page=2` guarded
- [ ] Cross-tenant IDOR: an `admin_globex` rule / finding / report / snapshot pk returns **404** on detail, edit, delete, preview, disposition, run, snapshot and export
- [ ] Verbs reject GET (405); a non-admin user is refused on `maverick_scan` and every disposition verb (`@tenant_admin_required`, L27)
- [ ] **L33**: grep the rendered HTML for `badge-success|badge-warning|badge-danger|detail-label|detail-value` -> zero hits; `{#` / `{% comment` not leaking as visible text
- [ ] **Naming bans**: `grep -ri "drag" apps/procurement templates/procurement` -> zero hits; `grep -ri "powerbi\|power bi" ` -> only the honest "not implemented" note; no "AI"/"ML" claim on the classification pages
- [ ] **Basis parity**: for a window where every invoice has a PO, the committed and invoiced cubes list the same suppliers; the `basis` toggle changes the numbers and never 500s on an empty basis
- [ ] **Credit memos net**: adding a credit memo to the window LOWERS net spend by exactly its (negative) line total - no special-casing anywhere in the code path
- [ ] **Currency**: a window with two currencies raises `mixed_currency=True` and the page shows the per-currency split instead of one summed total
- [ ] **`(unassigned)` bucket**: a PO-less invoice appears in the department breakdown under `(unassigned)`, and the department rows sum to the KPI net spend
- [ ] **Classification**: `classified_pct` + unclassified value = total; activating a rule moves value out of `(Unclassified)` on the next render; a `vendor` rule with no vendor is rejected by `clean()`, not silently matching everything
- [ ] **Rule ordering**: two rules matching the same line resolve to the LOWER `priority`, and ties break on `id` deterministically (asserted twice in a row)
- [ ] **Maverick idempotency**: `scan()` run twice creates the same number of findings (upsert on `dedupe_key`) and does NOT re-open a `justified`/`dismissed`/`remediated` finding
- [ ] **Maverick rate**: the denominator is **addressable** spend (`is_addressable=True`), not total spend; flipping one finding to `is_addressable=False` moves the rate; the umbrex bands render
- [ ] **Export**: the CSV honours the active filters (not "everything"), caps at `MAX_EXPORT_ROWS` with the "showing N of M" notice, and a vendor named `=cmd|' /C calc'!A0` comes back prefixed with an apostrophe (`csv_safe`)
- [ ] **Snapshot**: `spendreportsnapshot_detail` renders with the query path stubbed/unavailable - proof it re-renders from `data` with NO recompute
- [ ] **Performance**: `spend_dashboard`, `category_spend` and `classification_workbench` each run a BOUNDED number of queries (assert with `assertNumQueries` or `CaptureQueriesContext`) - the rule list is pre-fetched ONCE, never per line
- [ ] **L29**: 6.14 writes NOTHING to `accounting.*` - no `Bill`, no `JournalEntry`, no `Budget`. Grep the diff to prove it
- [ ] Tests derive dates from `timezone.localdate()` / `timezone.now().date()` (L16); iterate with `--nomigrations` but the FINAL proof run keeps migrations on and is **UNFILTERED** (L47/L49)
- [ ] Sidebar shows **6.14 as Live with all five bullets resolving** - no `NoReverseMatch`; 4.11's "Procurement Analytics" bullet still resolves and still points at `scm:spend_analytics`

## Close-out
- [ ] Review wave (Phase 4): `code-reviewer · explorer · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer` in ONE parallel Workflow -> `.claude/tasks/review-procurement-6.14.md`, committed
- [ ] `code-fixer` (Phase 5) burns the findings down in ID order, one commit per file; no finding left `[ ] open`
- [ ] Test wave (Phase 6): contract/conftest solo -> 4 parallel `test-writer` lanes over `test_spend_{models,forms,views,security}.py` -> one green UNFILTERED run
- [ ] Update `.claude/skills/procurement/SKILL.md` with 6.14's models, routes, templates, `analytics.py` compute contract and seeder rows (own commit)
- [ ] Mark 6.14 complete in `README.md` (own commit)
- [ ] `build_state.py phase <n> done` at every phase boundary; `build_state.py finish` when 6.14 is documented

## Later passes / deferred (carried from the research so nothing is lost)
- **ML/NLP auto-classification and supplier normalisation** (all 10 leaders) - needs a classifier and a training corpus. The rules engine is the honest shipped equivalent. Never label it "AI".
- **Scheduled / subscribed report delivery by email** - `accounting.ScheduledReport` already models the config and already defers the worker; `SpendReport` + snapshot is the substrate it would point at.
- **Live BI / PowerBI connector, REST or SFTP feeds** - a signed, tenant-scoped read-only endpoint is its own security design.
- **Community / peer benchmarking and external category price indices** (Coupa, SpendHQ, SAP Ariba, Sievo, GEP) - needs an external corpus.
- **P-card / T&E / expense spend sources** - no card-transaction model exists in this tree; that is why the reason list omits card/MCC misuse.
- **Multi-currency normalisation** - still no FX-rate table in the repo; face-value sums per currency + `mixed_currency` is the honest answer.
- **UNSPSC codes on `scm.ItemCategory`** - a nullable `unspsc_code` is the additive one-column precedent, but it is a cross-app SCM migration from a Procurement build. Out of scope; note the future migration.
- **`split_purchase` detector** - the choice ships; the detector is the cut line if the build phase overruns (see Model 2).
- **PDF board pack / CFO-ready print export** - the `hrm/offboarding/relieving_letter.html` print precedent exists; not this pass.
- **Should-cost modelling, BOM roll-ups, what-if scenarios** - solver work, well outside a Django aggregate pass.
- **Spend-threshold / overspend alerts** - `procurement.ProcurementAlert` (6.1) already exists; if wanted later this emits an alert row, not a new table.

## Parked for a sibling sub-module (do NOT pull into 6.14)
- Budget vs actual, commitment accounting, variance analysis, spend forecasting -> **6.15 Budget & Cost Management** (link out, never restate `accounting.Budget`)
- Supplier scorecards, OTD/defect KPIs, benchmarking supplier performance -> **6.16 Supplier Performance & Evaluation** (`scm.SupplierScorecard` exists; 4.11 already trends it)
- Fraud-pattern detection, restricted-party screening, conflict-of-interest, tamper-proof audit logging -> **6.17 Risk & Compliance Management** (only `split_purchase` stays here, and the code comment names the boundary)
- Savings-initiative lifecycle (identified -> approved -> sourcing -> realised -> validated) -> **6.5 Sourcing Analytics** or a later 6.14 pass - a full workflow entity, does not fit this budget
- Early-payment-discount **worklist** -> already built in **6.13** (`invoicevoucher_dashboard#discount`); 6.14 shows only the aggregate trend and deep-links across
- Contract renewal/expiry **workflow** -> **6.8 / 4.2**; 6.14 only surfaces the spend at risk on an expiring contract
- Supplier master deduplication / normalisation -> **6.4 Vendor Management** / `core.Party`; an analytics pass must never edit the party master
- Catalogue price maintenance and preferred-supplier designation -> **6.9**; 6.14 only READS `is_preferred` / `CatalogPriceTier` as the benchmark
- PO-based spend cube, negotiated savings, cycle/lead time, committed tail share -> already **SCM 4.11** (`scm:spend_analytics`) - link, never restate
- Generic dashboard builder, formula-authored KPI library, OLAP cubes, NLQ, ML/AutoML, scheduled distribution and bursting -> **Module 10 (`bi`)** 10.8/10.10/10.11/10.12/10.13/10.15/10.16. **The most important boundary in this plan: 6.14 is a procurement analytics page, not a BI platform.**

## Review notes

### 6.15 Budget & Cost Management (built 2026-09-01)

Built by subtraction: `accounting.Budget`/`BudgetLine` is never restated (L29) and no stored
encumbrance exists anywhere - the commitment vocabulary (`OPEN_COMMITMENT_PO_STATUSES` verbatim
from scm 4.18; `COMMITTED_PR_STATUSES` excluding `converted` to avoid double-counting) and all
three computed pages derive at view time. Two models: `BudgetMapping` (config glue, PROTECT
budget FK, most-specific-wins `resolve()`, no unique_together on nullable scope columns) and
`CostForecast` [FCST-] (frozen snapshot - amounts `editable=False`, stamped once via
`compute_forecast_amounts()` in a hand-rolled create, NO edit route, arithmetic-only honesty
note on every page). Three derived pages: availability checker (mirrors scm `budget_check()`
semantics, advisory), commitment register (PO line sums unioned with approved-not-converted
requisition estimates, ROW_CAP 500), variance report (per-BudgetLine
budgeted/committed/recognised-invoiced/remaining + CSV; actuals basis is 6.13 recognised
invoices, not scm vouchers). Money via 6.14 `money()`, never `q2`. Migration 0024;
`_seed_budget_cost` idempotent (4 mappings + 2 forecasts per tenant; SMOKETEST tenant skips
gracefully without accounting data). Smoke: all 21 URL/param combos 200 incl. junk params,
cross-tenant IDOR 404, delete POST-only + really deletes (throwaway row), no `{#` leaks, five
sidebar bullets Live. One bug found during smoke and fixed before commit: missing `reverse`
import in `views/BudgetCostManagement/CostForecasts.py`. Review wave findings land in
`.claude/tasks/review-procurement-6.15.md`; tests in `tests/test_budgetcost_*.py`.

---
# Sub-module 6.17 - Risk & Compliance Management (Module 6: Procurement Management System, `procurement`) - plan from research-procurement-6.17.md  (2026-09-05)

Sub-package `RiskComplianceManagement/` in all four backend layers; templates
`templates/procurement/riskcompliance/`. Subslug for tests/helpers: **`riskcompliance`**.

## Scope decision (FROZEN - do not re-litigate)

Five NavERP.md bullets, five destinations, **5 primary models + 2 children = 7 tables**. This is
one over the todo agent's usual 1-4 ceiling and the overage is deliberate and bounded:

- [ ] Adopt research §5.1-§5.5 in full. Each bullet needs its own record; merging any two would
      make a bullet land on a page that does not answer it (L30).
- [ ] **`AuditSeal` (Entity 5) is built LAST and is the one CUTTABLE item.** Bullet 3's page
      (`audit_trail`, a filtered/exportable register over `core.AuditLog` with **no table**) ships
      regardless and is what `LIVE_LINKS["6.17"]` points at. If the pass overruns, move `AuditSeal`
      to Later passes, delete its LIVE-LINK-independent routes, and ship bullet 3 as the register
      alone - the page then states plainly that sealing is not yet available.
- [ ] `screening_batch` (research 1.10) and the two P2 fraud rules (`po_escalation`,
      `round_amount`) are the other two cut lines - see Later passes for why.
- [ ] **Nothing merged, nothing trimmed from the four core models.** No reason found to deviate.

## Spine: grep-verified this pass (L28 - the grep is the truth, not the ERD)

Every FK below was re-confirmed with `grep -rn "^class <Name>" apps/*/models/` on 2026-09-05:

| Target | Verified at | 6.17 uses it for |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5` - `tenant, kind, name, tax_id, created_at` | screened supplier, risk-signal subject, fraud vendor/related party |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` - `tenant, party, role, status, start_date`, `unique_together (party, role)` | who is a vendor vs an employee in fraud rules R1/R3 |
| `core.Address` | `apps/core/models/Address.py:5` - **has its own `tenant`**, `party, kind, line1, city, country` | R1/R3 address overlap join |
| `core.ContactMethod` | `apps/core/models/ContactMethod.py:5` - **has its own `tenant`**, `party, kind, value` | R1 contact overlap join |
| `core.Employment` | `apps/core/models/Employment.py:5` - `tenant, party, org_unit, manager, job_title, hired_on, status(active/on_leave/terminated)` | resolving a policy's `applicable_org_unit` audience |
| `core.OrgUnit`, `core.Tenant`, `core.Document` | `OrgUnit.py:5`, `Tenant.py:5`, `Document.py:5` (`tenant, content_type, object_id, file, name, classification, version, uploaded_at`) | policy scope; evidence attachments |
| `core.AuditLog` | `apps/core/models/AuditLog.py:5` - `tenant, user, content_type, object_id, target, action(create/update/delete), changes(JSON), at(auto_now_add)`, `ordering ["-at"]`, `Index(tenant, at)` | the audit trail page + the seal's hash input. **ZERO `core` migrations - do not add columns here** |
| `scm.PurchaseRequisition` | `apps/scm/models/ProcurementManagement/PurchaseRequisitions.py:14` - `title, requester(User), org_unit, status, estimated_total(derived)`, `APPROVAL_TIERS` | fraud R2 self-approval |
| `scm.PurchaseOrder` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` - `vendor(core.Party), requisition, order_date(NULLABLE), status, total(derived, editable=False)` | fraud R4/R5 |
| `accounting.VendorProfile` | `apps/accounting/models/AccountsPayable/VendorProfiles.py:5` | **NO bank fields** - see the R4.9 gap below |
| `procurement.VendorSuspension` | `apps/procurement/models/VendorManagement/VendorSuspensions.py:27` [VSU-] - `supplier(core.Party), kind, reason_category, status(requested/active/rejected/lifted), starts_on, ends_on`, `blocking_for(tenant, supplier_id, today=None)`; routes `procurement:vsu_list / vsu_create / vsu_detail` | the escalation target. **Never build a second block flag** |
| `procurement.RequisitionApproval` | `apps/procurement/models/ApprovalWorkflowEngine/Approvals.py:19` [RQA-] - `requisition, tier, tier_count, decision, approver(User), via_delegation, comment, decided_at` | fraud R2 - read-only |
| `procurement.ProcurementAlert` | `apps/procurement/models/DashboardPortal/ProcurementAlerts.py:26` - `kind(deadline/approval/delivery/task/contract), severity(info/warning/critical), status(open/acknowledged/resolved), title, message, link_url(internal-path-only, XSS-guarded in clean()), due_at, assigned_to`, `OPEN_STATUSES` | the ONLY notification channel. No second alert table |
| `procurement.SupplierInvoice` | `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:135` - `vendor, purchase_order, goods_receipt, invoice_type, invoice_number, invoice_number_norm, invoice_date, total(editable=False), status, duplicate_of, match_status` | fraud R4/R6; the duplicate panel CITES 6.13 |
| `procurement.MaverickSpendFinding` | `apps/procurement/models/SpendAnalyticsReporting/MaverickFindings.py:132` [MSF-] - `scan(tenant,start,end,reasons,user)`, `build_dedupe_key()`, `_existing_by_key()`, `_upsert()`, `_scan_context()`, `SCAN_LINE_LIMIT=20000`, `_DEDUPE_LOOKUP_CHUNK=1000`, module constants `RECOGNISED_INVOICE_STATUSES=("approved","scheduled","paid")` and `SPEND_PO_STATUSES=("approved","sent","acknowledged","partially_received","received","closed")` | **READ THIS FILE BEFORE WRITING `FraudAlert`.** Copy the scan/dedupe SHAPE, never a reason |
| `apps/procurement/models/_base.py` | `TenantOwned` (tenant FK `related_name="+"`, `created_at`, `updated_at`), `TenantNumbered` (`NUMBER_PREFIX`, `number` CharField(20, editable=False), retry-on-collision `save()` via `apps.core.utils.next_number`), `ZERO`, `q2`, `MAX_Q2` | every 6.17 model's base |
| `apps/procurement/views/_helpers.py` | `procurement_activity_qs(tenant)` (AuditLog filtered `app_label="procurement"` OR `app_label="scm" AND model IN PROCUREMENT_CONTENT_MODELS`), `ACTIVITY_FEED_NOTE`, `csv_safe(value)`, `_CSV_DANGEROUS = ("=","+","-","@","\t","\r")` | the audit trail page + every CSV cell |

- [ ] **`PROCUREMENT_CONTENT_MODELS` needs NO edit for 6.17** - that tuple whitelists `scm` model
      names only; 6.17's own rows arrive through the `app_label="procurement"` leg already. Confirm
      by rendering `audit_trail` after seeding and seeing a `compliancescreening` row.
- [ ] **NOT BUILDABLE - state it, do not fake it (research 3-R4.9):** the "vendor bank-detail
      change" fraud rule. `accounting.VendorProfile` has no bank fields and
      `accounting.BankAccount` is the **tenant's own** account (no party FK). The fraud scan page
      carries a one-line note naming the gap so an auditor sees the control is absent by DATA, not
      by oversight. It goes to Later passes as an `apps/accounting` build.
- [ ] **Already built elsewhere - CITE, never re-detect:** duplicate invoice / duplicate payment is
      6.13 (`SupplierInvoice.duplicate_of`, `match_status="duplicate_suspect"`,
      `InvoiceMatchVariance` type `duplicate`). The fraud board renders a count + a link to the
      6.13 register. **Pin the exact GET param from
      `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py` at build time.**
- [ ] **6.17 posts NOTHING to `apps.accounting`** (L29) and writes NOTHING to the spine: no
      auto-suspension, no invoice block, no PO hold. Detection suggests; a human decides
      (SAP BIS "park, don't block"). State it in every module docstring.

---

## Entity 1 - `ComplianceScreening` [SCR-] + `ScreeningHit` -- **bullet 1 Regulatory Compliance Checks**
`apps/procurement/models/RiskComplianceManagement/Screenings.py`

### CHOICES (exact value/label pairs)
- [ ] `LIST_SOURCE_CHOICES` (module-level, shared with `ScreeningHit.matched_list`) -
      `("ofac_sdn","OFAC - Specially Designated Nationals (SDN)")`,
      `("ofac_other","OFAC - other lists (SSI / FSE / PLC / CAP)")`,
      `("bis_dpl","BIS - Denied Persons List")`, `("bis_entity","BIS - Entity List")`,
      `("bis_uvl","BIS - Unverified List")`, `("state_isn","State - ISN sanctions")`,
      `("state_debarred","State - AECA/ITAR debarred parties")`,
      `("csl_consolidated","ITA Consolidated Screening List (CSL)")`,
      `("sam_exclusions","SAM.gov Exclusions (federal debarment)")`,
      `("eu_consolidated","EU consolidated sanctions list")`,
      `("un_consolidated","UN consolidated sanctions list")`,
      `("internal_watchlist","Internal watchlist")`, `("other","Other list")`
      *(driver: research 1.3 + §2.2 - CSL consolidates 11 lists and deliberately EXCLUDES SAM.gov,
      so both are separate values.)*
- [ ] `CHECKPOINT_CHOICES` - `("onboarding","Supplier onboarding")`,
      `("pre_award","Pre-award / before contract")`, `("pre_po","Before raising a purchase order")`,
      `("pre_payment","Before payment")`, `("periodic","Periodic re-screen")`, `("ad_hoc","Ad hoc")`
      *(driver: 1.4 - sanctions.io's four minimum checkpoints.)*
- [ ] `METHOD_CHOICES` - `("manual_lookup","Manual lookup on the official search page")`,
      `("file_upload","List file / CSV compared offline")`,
      `("api_feed","Automated list feed (not yet connected)")`
      plus `SELECTABLE_METHODS = ("manual_lookup", "file_upload")`.
      **`api_feed` is in the vocabulary but NOT offered by the form** - the form's method field is
      built from `SELECTABLE_METHODS` so a future connector writes the same rows with no migration
      (research §5.6). `clean()` rejects `api_feed` from a hand-crafted POST.
- [ ] `RESULT_CHOICES` - `("clear","Clear - no potential match")`,
      `("potential_match","Potential match(es) returned")`, `("confirmed_match","Confirmed match")`,
      `("error","Lookup failed / not completed")` *(what the LOOKUP returned)*
- [ ] `STATUS_CHOICES` - `("pending_review","Pending review")`, `("cleared","Cleared")`,
      `("escalated","Escalated")`, `("blocked","Blocked")` *(what a HUMAN decided)*;
      `OPEN_STATUSES = ("pending_review","escalated")`,
      `TERMINAL_STATUSES = ("cleared","blocked")`
- [ ] `STATUS_CSS = {"pending_review":"badge-amber","cleared":"badge-green","escalated":"badge-red","blocked":"badge-red"}`;
      `RESULT_CSS = {"clear":"badge-green","potential_match":"badge-amber","confirmed_match":"badge-red","error":"badge-muted"}`
      **L33: only `badge-green/red/amber/info/muted/slate` exist in theme.css.**
- [ ] Class constants: `RETENTION_YEARS = 10` (OFAC 31 CFR 501.601),
      `DEFAULT_MATCH_THRESHOLD = 85`, `DEFAULT_RESCREEN_DAYS = 365`,
      `BATCH_PARTY_LIMIT = 500`, and `RETENTION_NOTE` (one string, rendered on list + detail).

### `ComplianceScreening(TenantNumbered)` - `NUMBER_PREFIX = "SCR"`
- [ ] `party` FK `"core.Party"` PROTECT, `related_name="procurement_screenings"` - the screened supplier
- [ ] `list_source` CharField(max_length=20, choices=LIST_SOURCE_CHOICES, default="csl_consolidated")
- [ ] `checkpoint` CharField(max_length=16, choices=CHECKPOINT_CHOICES, default="onboarding")
- [ ] `method` CharField(max_length=16, choices=METHOD_CHOICES, default="manual_lookup")
- [ ] `screened_on` DateField(default=timezone.localdate)
- [ ] `list_as_of` DateField(null=True, blank=True) - the DATA date of the list screened against *(driver: 1.3, 2.12 "every compliance artefact needs a valid-until")*
- [ ] `reference` CharField(max_length=120, blank=True) - the provider's search / case id *(driver: 1.9, §5.6 - so a connector can back-fill it)*
- [ ] `result` CharField(max_length=16, choices=RESULT_CHOICES, default="clear")
- [ ] `status` CharField(max_length=16, choices=STATUS_CHOICES, default="pending_review", **editable=False**)
- [ ] `match_threshold` PositiveSmallIntegerField(default=85, validators=[MinValueValidator(1), MaxValueValidator(100)]) *(driver: 1.7 / §2.3 - OFAC's own tool exposes a score and expects you to pick a threshold)*
- [ ] `threshold_rationale` CharField(max_length=255, blank=True) *(driver: §2.3 - "document the rationale for the threshold chosen")*
- [ ] `hit_count` PositiveSmallIntegerField(default=0, **editable=False**) - **DERIVED**
- [ ] `open_hit_count` PositiveSmallIntegerField(default=0, **editable=False**) - **DERIVED**
- [ ] `next_rescreen_on` DateField(null=True, blank=True) *(driver: 1.6 - Descartes dynamic re-screening)*
- [ ] `evidence` FK `"core.Document"` SET_NULL null blank, `related_name="procurement_screenings"` *(driver: 1.9)*
- [ ] `suspension` FK `"procurement.VendorSuspension"` SET_NULL null blank **editable=False**, `related_name="screenings"` - stamped by `block()` *(driver: 1.8 - reuse 6.4, never a second block flag)*
- [ ] `screened_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_screenings_run"`
- [ ] `decided_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_screenings_decided"`
- [ ] `decided_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `decision_note` TextField(blank=True, **editable=False**)
- [ ] `notes` TextField(blank=True)
- [ ] `Meta`: `ordering = ["-screened_on", "-id"]`; `unique_together = (("tenant","number"),)`;
      indexes `(tenant,status)` **`prc_scr_tnt_status_idx`**, `(tenant,party)` **`prc_scr_tnt_party_idx`**,
      `(tenant,screened_on)` **`prc_scr_tnt_screened_idx`**, `(tenant,next_rescreen_on)` **`prc_scr_tnt_rescreen_idx`**,
      `(tenant,result)` **`prc_scr_tnt_result_idx`**
- [ ] `__str__` -> `f"{self.number or 'SCR'} · {self.party} · {self.get_list_source_display()}"`
- [ ] `save()` - inherited `TenantNumbered.save()` only; **no derivation in `save()`** (the counters
      are recomputed by `recount_hits()`, called from the hit views, so a plain `.save()` in a test
      or seeder has no hidden side effect).

### `ScreeningHit(models.Model)` - **tenant-LESS child** (`scm.ComplianceCheck` / `AsnLine` precedent)
Resolved everywhere as `get_object_or_404(ScreeningHit, pk=pk, screening__tenant=request.tenant)`.
- [ ] `DISPOSITION_CHOICES` - `("open","Open - not yet adjudicated")`,
      `("false_positive","False positive")`, `("true_match","True match")`,
      `("cleared_with_licence","Cleared under licence / authorisation")`;
      `TERMINAL_DISPOSITIONS = ("false_positive","true_match","cleared_with_licence")`
      *(driver: 1.2 + §2.3 - SDN is a hard stop, Entity List is a licence application, UVL is a
      red flag to resolve, so "cleared with licence" is a real third outcome.)*
- [ ] `DISPOSITION_CSS = {"open":"badge-red","false_positive":"badge-green","true_match":"badge-red","cleared_with_licence":"badge-info"}`
- [ ] `MATCH_TYPE_CHOICES` - `("name","Name")`, `("alias","Alias / AKA")`, `("address","Address")`,
      `("tax_id","Tax / registration ID")`, `("other","Other")`
- [ ] `screening` FK `"procurement.ComplianceScreening"` CASCADE, `related_name="hits"`
- [ ] `matched_name` CharField(max_length=255)
- [ ] `matched_list` CharField(max_length=20, choices=LIST_SOURCE_CHOICES) - a CSL search returns entries from 11 different lists, so the hit carries its own
- [ ] `match_score` PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]) *(driver: 1.7)*
- [ ] `match_type` CharField(max_length=12, choices=MATCH_TYPE_CHOICES, default="name")
- [ ] `entry_reference` CharField(max_length=120, blank=True) - the list's own entry id
- [ ] `program` CharField(max_length=120, blank=True) - the sanctions programme
- [ ] `country` CharField(max_length=120, blank=True) *(driver: §2.3 - adjudication asks "does the geography line up?")*
- [ ] `remarks` TextField(blank=True)
- [ ] `disposition` CharField(max_length=24, choices=DISPOSITION_CHOICES, default="open", **editable=False**)
- [ ] `disposition_note` TextField(blank=True, **editable=False**)
- [ ] `disposed_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_screening_hits_disposed"`
- [ ] `disposed_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `created_at` DateTimeField(auto_now_add=True)
- [ ] `Meta`: `ordering = ["-match_score", "id"]`; index `(screening, disposition)` **`prc_schit_scr_disp_idx`**
- [ ] `__str__` -> `f"{self.matched_name} ({self.match_score}%)"`
- [ ] `clean()` - `matched_name` required; `match_score` 0-100 (validators); no cross-tenant check
      needed (the parent FK IS the scope), but the VIEW must still resolve via `screening__tenant`.

---

## Entity 2 - `SupplierRiskSignal` [SRS-] -- **bullet 2 Supplier Financial Risk Monitoring**
`apps/procurement/models/RiskComplianceManagement/RiskSignals.py`

### CHOICES + the scale table (the point of the whole model)
- [ ] `PROVIDER_CHOICES` - `("dnb","Dun & Bradstreet")`, `("rapidratings","RapidRatings")`,
      `("creditsafe","Creditsafe")`, `("experian","Experian")`, `("coface","Coface")`,
      `("ecovadis","EcoVadis")`, `("bitsight","BitSight")`, `("internal","Internal assessment")`,
      `("other","Other provider")` -- max_length=16 *(driver: 2.2; BitSight/EcoVadis reserved so a
      later connector needs no migration, research §7.11)*
- [ ] `METRIC_CHOICES` - max_length=20:
      `("fhr","RapidRatings FHR (1-100, higher is healthier)")`,
      `("ser_rating","D&B Supplier Evaluation Risk (1-9, higher is riskier)")`,
      `("paydex","D&B PAYDEX (1-100, higher is prompter)")`,
      `("failure_score","D&B Failure / Insolvency score")`,
      `("credit_score","Credit score (1-100)")`, `("credit_rating","Credit rating notch (1-21)")`,
      `("altman_z","Altman Z-score")`, `("dso_days","Days sales outstanding")`,
      `("days_beyond_terms","Days beyond terms")`, `("current_ratio","Current ratio")`,
      `("esg_rating","ESG / sustainability rating")`, `("cyber_rating","Cyber security rating")`,
      `("other","Other metric")`
- [ ] **`METRIC_SCALES`** - `{metric: (scale_min, scale_max, higher_is_better)}` as `Decimal`s.
      **This is the single most important constant in the sub-module** (research 2.8: "a single
      'risk score' column without provider+metric is a lie" - FHR 100 = good, SER 9 = bad):
      `fhr (1,100,True)`, `ser_rating (1,9,False)`, `paydex (1,100,True)`,
      `failure_score (1,100,True)`, `credit_score (1,100,True)`, `credit_rating (1,21,True)`,
      `altman_z (-5,10,True)`, `dso_days (0,180,False)`, `days_beyond_terms (0,120,False)`,
      `current_ratio (0,5,True)`, `esg_rating (0,100,True)`, `cyber_rating (250,900,True)`,
      `other (None,None,True)`.
- [ ] `BAND_CHOICES` - `("low","Low")`, `("watch","Watch")`, `("elevated","Elevated")`,
      `("critical","Critical")`, `("unrated","Not banded")` -- max_length=12
      *(driver: 2.3 - JAGGAER's yellow/amber/red escalation ladder; `unrated` is the honest answer
      for `metric="other"`, which has no registered scale.)*
- [ ] `BAND_CSS = {"low":"badge-green","watch":"badge-info","elevated":"badge-amber","critical":"badge-red","unrated":"badge-muted"}`
- [ ] `BAND_THRESHOLDS = ((Decimal("25"),"low"), (Decimal("50"),"watch"), (Decimal("75"),"elevated"))`, above 75 -> `"critical"` (on the 0-100 **risk position**, 0 = safest)
- [ ] `TREND_CHOICES` - `("new","First observation")`, `("improved","Improved")`,
      `("stable","Stable")`, `("deteriorated","Deteriorated")` -- max_length=14;
      `TREND_CSS = {"new":"badge-slate","improved":"badge-green","stable":"badge-muted","deteriorated":"badge-red"}`
- [ ] `REVIEW_STATUS_CHOICES` - `("new","New")`, `("reviewed","Reviewed")`, `("actioned","Actioned")`,
      `("dismissed","Dismissed")` -- max_length=12;
      `REVIEW_CSS = {"new":"badge-red","reviewed":"badge-amber","actioned":"badge-green","dismissed":"badge-muted"}`
- [ ] `MINIMUM_ACCEPTABLE = {"ser_rating": Decimal("5"), "fhr": Decimal("40")}` *(driver: 2.7 - D&B
      buyers impose a minimum SER; RapidRatings' 40 line. **ADVISORY ONLY** - it colours a badge,
      it never blocks, exactly the `ReceiptTolerancePolicy` posture.)*
- [ ] `TREND_EPSILON = Decimal("0.50")`, `STALE_AFTER_DAYS = 180`, `SERIES_LIMIT = 12`,
      `ALERT_BANDS = ("elevated", "critical")`

### `SupplierRiskSignal(TenantNumbered)` - `NUMBER_PREFIX = "SRS"`
- [ ] `party` FK `"core.Party"` PROTECT, `related_name="procurement_risk_signals"`
- [ ] `provider` CharField(max_length=16, choices=PROVIDER_CHOICES, default="internal")
- [ ] `metric` CharField(max_length=20, choices=METRIC_CHOICES, default="other")
- [ ] `observed_on` DateField(default=timezone.localdate) - the date the PROVIDER measured it, not the capture date
- [ ] `value` DecimalField(max_digits=12, decimal_places=2)
- [ ] `scale_min` DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, **editable=False**) - **DERIVED** from `METRIC_SCALES`
- [ ] `scale_max` DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, **editable=False**) - **DERIVED**
- [ ] `higher_is_better` BooleanField(default=True, **editable=False**) - **DERIVED**
- [ ] `risk_position` DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, **editable=False**) - **DERIVED** 0.00-100.00, 0 = safest
- [ ] `band` CharField(max_length=12, choices=BAND_CHOICES, default="unrated", **editable=False**) - **DERIVED**
- [ ] `previous_value` DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, **editable=False**) - **DERIVED**
- [ ] `trend` CharField(max_length=14, choices=TREND_CHOICES, default="new", **editable=False**) - **DERIVED** *(driver: 2.4 - "derived, not typed")*
- [ ] `review_status` CharField(max_length=12, choices=REVIEW_STATUS_CHOICES, default="new", **editable=False**) - moved by verbs only
- [ ] `review_note` TextField(blank=True, **editable=False**)
- [ ] `reviewed_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_risk_signals_reviewed"`
- [ ] `reviewed_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `next_refresh_on` DateField(null=True, blank=True) *(driver: 2.6)*
- [ ] `source_ref` CharField(max_length=160, blank=True) - the report reference. **Rendered as TEXT, never as an `href`** (the `ProcurementAlert.link_url` lesson: staff-authored strings do not become links) *(driver: 2.8)*
- [ ] `evidence` FK `"core.Document"` SET_NULL null blank, `related_name="procurement_risk_signals"` *(driver: 2.8)*
- [ ] `captured_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_risk_signals_captured"` *(driver: §5.6 honesty - every row states who captured it)*
- [ ] `alert` FK `"procurement.ProcurementAlert"` SET_NULL null blank **editable=False**, `related_name="risk_signals"` - stamped when deterioration raised one *(driver: 2.5)*
- [ ] `notes` TextField(blank=True)
- [ ] `Meta`: `ordering = ["-observed_on","-id"]`; `unique_together = (("tenant","number"),)`;
      indexes `(tenant,party,observed_on)` **`prc_srs_tnt_party_obs_idx`**,
      `(tenant,band)` **`prc_srs_tnt_band_idx`**, `(tenant,review_status)` **`prc_srs_tnt_review_idx`**,
      `(tenant,next_refresh_on)` **`prc_srs_tnt_refresh_idx`**,
      `(tenant,party,provider,metric,observed_on)` **`prc_srs_series_idx`** (backs the prior-row lookup AND the detail series)
- [ ] `__str__` -> `f"{self.number or 'SRS'} · {self.party} · {self.get_metric_display()} {self.value}"`

---

## Entity 3 - `FraudAlert` [FRD-] -- **bullet 4 Fraud Detection Rules**
`apps/procurement/models/RiskComplianceManagement/FraudAlerts.py`

- [ ] **Read `apps/procurement/models/SpendAnalyticsReporting/MaverickFindings.py` end-to-end first.**
      Copy `build_dedupe_key` / `_existing_by_key` / `_upsert` / `_scan_context` / `scan` SHAPE
      verbatim in structure. **Copy none of its eight reasons.** MSF = process leakage; 6.17 =
      integrity. `split_purchase` stays 6.14's.

### CHOICES + tuning constants
- [ ] `RULE_CHOICES` (max_length=24) -
      `("vendor_employee_match","Vendor and employee share an identity attribute")`,
      `("self_approval","Requisition approved by its own requester")`,
      `("duplicate_vendor","Duplicate / shell supplier record")`,
      `("backdated_po","Purchase order raised after the invoice it authorises")`,
      `("screening_unresolved","New spend against an unresolved screening match")`,
      `("new_vendor_rush","New supplier with immediate high-value spend")`
      *(drivers: research 4.1, 4.2, 4.3, 4.4, 4.5, 4.6.)*
- [ ] `SEVERITY_CHOICES` = `[("low","Low"),("medium","Medium"),("high","High")]` (max_length=10);
      `SEVERITY_BY_RULE = {"vendor_employee_match":"high", "self_approval":"high",
      "duplicate_vendor":"medium", "backdated_po":"medium", "screening_unresolved":"high",
      "new_vendor_rush":"medium"}` - **a DEFAULT, not a verdict** (MSF precedent: `severity` stays
      on the form so a reviewer can re-grade a row the engine over-called).
- [ ] `STATUS_CHOICES` (max_length=16) - `("open","Open")`, `("investigating","Under investigation")`,
      `("substantiated","Substantiated")`, `("unsubstantiated","Unsubstantiated - false positive")`,
      `("referred","Referred for external action")`;
      `OPEN_STATUSES = ("open","investigating")`,
      `TERMINAL_STATUSES = ("substantiated","unsubstantiated","referred")`
      *(drivers: 4.12 SAP BIS alert management, 4.13 the dismiss escape hatch.)*
- [ ] `STATUS_CSS = {"open":"badge-amber","investigating":"badge-info","substantiated":"badge-red","unsubstantiated":"badge-muted","referred":"badge-slate"}`
      **Deliberate deviation from MSF's "open is red":** here the strongest colour belongs to a
      SUBSTANTIATED fraud finding, not to an untriaged one. Put the reason in the model docstring.
- [ ] `SEVERITY_CSS = {"low":"badge-slate","medium":"badge-amber","high":"badge-red"}`
- [ ] Tuning constants, **surfaced READ-ONLY on the scan page** (research 4.11 - a `FraudRule` table
      is Later passes; do NOT ship an editable rule table with no scan wired to it):
      `OVERLAP_ATTRIBUTES = ("tax_id", "address", "contact")`, `MAX_GROUP_SIZE = 25`,
      `MAX_PAIRS_PER_ATTRIBUTE = 500`, `NEW_VENDOR_DAYS = 30`,
      `NEW_VENDOR_AMOUNT = Decimal("25000.00")`, `BACKDATE_GRACE_DAYS = 1`,
      `SCAN_ROW_LIMIT = 20000`, `_DEDUPE_LOOKUP_CHUNK = 1000`,
      `NAME_SUFFIXES = ("ltd","limited","inc","llc","plc","gmbh","pvt","co","company","corp","corporation","sa","bv","pte")`

### `FraudAlert(TenantNumbered)` - `NUMBER_PREFIX = "FRD"`
Source pointers - **all SET_NULL null blank; `clean()` requires AT LEAST ONE** (MSF pattern):
- [ ] `vendor` FK `"core.Party"` SET_NULL, `related_name="procurement_fraud_alerts"`
- [ ] `related_party` FK `"core.Party"` SET_NULL, `related_name="procurement_fraud_alerts_related"` - the employee / second vendor in an overlap
- [ ] `requisition` FK `"scm.PurchaseRequisition"` SET_NULL, `related_name="procurement_fraud_alerts"`
- [ ] `purchase_order` FK `"scm.PurchaseOrder"` SET_NULL, `related_name="procurement_fraud_alerts"`
- [ ] `supplier_invoice` FK `"procurement.SupplierInvoice"` SET_NULL, `related_name="fraud_alerts"`
- [ ] `approval` FK `"procurement.RequisitionApproval"` SET_NULL, `related_name="fraud_alerts"`
- [ ] `screening` FK `"procurement.ComplianceScreening"` SET_NULL, `related_name="fraud_alerts"`

Classification + evidence:
- [ ] `rule` CharField(max_length=24, choices=RULE_CHOICES)
- [ ] `severity` CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium") - ON the form
- [ ] `document_date` DateField(db_index=True) - the date of the FACT, never the detection date
- [ ] `amount` DecimalField(max_digits=18, decimal_places=2, null=True, blank=True) - NULL is legal (a COI match has no amount)
- [ ] `detail` TextField(blank=True) - the evidence sentence the detector wrote
- [ ] `matched_on` CharField(max_length=160, blank=True) - WHICH attribute matched, **with the value MASKED**: `"tax_id ••••1234"`, `"email a••@acme.test"`, `"address 12 Mill St, Leeds"`. The unmasked comparison happens inside the scan and is never stored (L20). Auto-escaped in templates, `csv_safe()` on export.
- [ ] `dedupe_key` CharField(max_length=120, **editable=False**)
- [ ] `detected_at` DateTimeField(auto_now_add=True)
- [ ] `status` CharField(max_length=16, choices=STATUS_CHOICES, default="open", **editable=False**)
- [ ] `assigned_to` FK `settings.AUTH_USER_MODEL` SET_NULL null blank, `related_name="procurement_fraud_alerts"` - ON the form
- [ ] `resolution_note` TextField(blank=True, **editable=False**)
- [ ] `resolved_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_fraud_alerts_resolved"`
- [ ] `resolved_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `suspension` FK `"procurement.VendorSuspension"` SET_NULL null blank **editable=False**, `related_name="fraud_alerts"` - stamped by `substantiate()` when the operator links a raised block
- [ ] `Meta`: `ordering = ["-document_date","-id"]`;
      `unique_together = (("tenant","number"), ("tenant","dedupe_key"))`;
      indexes `(tenant,status)` **`prc_frd_tnt_status_idx`**, `(tenant,rule)` **`prc_frd_tnt_rule_idx`**,
      `(tenant,severity)` **`prc_frd_tnt_sev_idx`**, `(tenant,document_date)` **`prc_frd_tnt_docdate_idx`**,
      `(tenant,vendor)` **`prc_frd_tnt_vendor_idx`**
- [ ] `__str__` -> `f"{self.number or 'FRD'} · {self.get_rule_display()}"`

---

## Entity 4 - `ProcurementPolicy` [PPL-] + `PolicyAttestation` -- **bullet 5 Policy Management & Acknowledgment**
`apps/procurement/models/RiskComplianceManagement/Policies.py`
- [ ] Mirror `apps/hrm/models/ComplianceLegal/Hrpolicy.py` + `Policyacknowledgment.py` (proven,
      in-repo) with ONE deliberate change: the attestation targets **`settings.AUTH_USER_MODEL`**,
      not an employee profile - the bullet says "tracking of **user** sign-offs" and procurement's
      audience is buyers/approvers, many of whom have no HRM employee record.

### `ProcurementPolicy(TenantNumbered)` - `NUMBER_PREFIX = "PPL"`
- [ ] `CATEGORY_CHOICES` (max_length=24) - `("code_of_conduct","Supplier code of conduct")`,
      `("purchasing_limits","Purchasing limits & delegation of authority")`,
      `("sourcing","Sourcing & competitive bidding")`,
      `("supplier_selection","Supplier selection & qualification")`,
      `("conflict_of_interest","Conflict of interest")`,
      `("gifts_hospitality","Gifts & hospitality")`,
      `("anti_bribery","Anti-bribery & anti-corruption")`,
      `("data_privacy","Data privacy & confidentiality")`,
      `("sustainability","Sustainable & ethical procurement")`, `("other","Other")`
- [ ] `STATUS_CHOICES` (max_length=12) - `("draft","Draft")`, `("published","Published")`, `("archived","Archived")`;
      `STATUS_CSS = {"draft":"badge-slate","published":"badge-green","archived":"badge-muted"}`
- [ ] `title` CharField(max_length=255)
- [ ] `category` CharField(max_length=24, choices=CATEGORY_CHOICES, default="other")
- [ ] `version_number` CharField(max_length=20, default="1.0")
- [ ] `previous_version` FK `"self"` SET_NULL null blank, `related_name="superseded_by"` *(driver: 5.1 supersession chain)*
- [ ] `applicable_org_unit` FK `"core.OrgUnit"` SET_NULL null blank, `related_name="procurement_policies"` - blank = the whole workspace *(driver: 5.5 targeted audience)*
- [ ] `owner` FK `settings.AUTH_USER_MODEL` SET_NULL null blank, `related_name="procurement_policies_owned"` - ON the form
- [ ] `summary` CharField(max_length=500, blank=True)
- [ ] `body` TextField(blank=True)
- [ ] `document` FK `"core.Document"` SET_NULL null blank, `related_name="procurement_policies"` - **FK, not a `FileField`** (research 5.6: consistent with 6.17's other evidence links; 6.19 will index `core.Document`)
- [ ] `status` CharField(max_length=12, choices=STATUS_CHOICES, default="draft", **editable=False**) - publish/archive verbs only
- [ ] `effective_from` DateField(null=True, blank=True)
- [ ] `review_due_on` DateField(null=True, blank=True) *(driver: 2.12 - every compliance artefact needs a re-check date)*
- [ ] `requires_attestation` BooleanField(default=True)
- [ ] `attestation_due_days` PositiveSmallIntegerField(default=14) - drives `PolicyAttestation.due_on` at publish *(driver: 5.7)*
- [ ] `enforced_by` CharField(max_length=255, blank=True) - free-text pointer to the routing rule / tolerance policy that enforces it *(driver: 5.8, the `corrective_reference` precedent)*
- [ ] `published_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `published_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_policies_published"`
- [ ] `archived_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `Meta`: `ordering = ["-created_at"]`;
      `unique_together = (("tenant","number"), ("tenant","title","version_number"))`;
      indexes `(tenant,status)` **`prc_ppl_tnt_status_idx`**, `(tenant,category)` **`prc_ppl_tnt_cat_idx`**,
      `(tenant,"-created_at")` **`prc_ppl_tnt_created_idx`**
- [ ] `__str__` -> `f"{self.title} v{self.version_number}"`
- [ ] Derived, annotation-aware (copy `HRPolicy.acknowledgment_rate` verbatim in shape):
      `attested_count` (`_attested_count` annotation else `self.attestations.filter(status="acknowledged").count()`),
      `target_count`, `attestation_rate` (Decimal, `.quantize(Decimal("0.1"))`, 0 when nobody targeted),
      `overdue_count`. **DERIVED - never a stored column.**

### `PolicyAttestation(TenantOwned)`
`TenantOwned` (not tenant-less) per the HRM precedent - there is a cross-policy "My policies" page.
- [ ] `STATUS_CHOICES` (max_length=14) - `("pending","Pending")`, `("acknowledged","Acknowledged")`, `("exempt","Exempt")`;
      `STATUS_CSS = {"pending":"badge-amber","acknowledged":"badge-green","exempt":"badge-muted"}`
- [ ] `policy` FK `"procurement.ProcurementPolicy"` CASCADE, `related_name="attestations"`
- [ ] `user` FK `settings.AUTH_USER_MODEL` CASCADE, `related_name="procurement_policy_attestations"`
- [ ] `status` CharField(max_length=14, choices=STATUS_CHOICES, default="pending", **editable=False**)
- [ ] `due_on` DateField(null=True, blank=True) - stamped at publish from `attestation_due_days`
- [ ] `acknowledged_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `acknowledgement_note` TextField(blank=True, **editable=False**)
- [ ] `exempt_reason` CharField(max_length=255, blank=True, **editable=False**)
- [ ] `alert` FK `"procurement.ProcurementAlert"` SET_NULL null blank **editable=False**, `related_name="policy_attestations"` - the overdue chase *(driver: 5.7 - no mail sender is wired, an alert substitutes)*
- [ ] `Meta`: `ordering = ["-created_at"]`; `unique_together = ("tenant","policy","user")`;
      indexes `(tenant,policy)` **`prc_patt_tnt_policy_idx`**, `(tenant,user,status)` **`prc_patt_user_status_idx`**,
      `(tenant,status,due_on)` **`prc_patt_status_due_idx`**, `(tenant,"-created_at")` **`prc_patt_tnt_created_idx`**
- [ ] `__str__` -> `f"{self.user} — {self.policy}"` with the `_id` guard the HRM copy uses
- [ ] Derived: `is_overdue` = `status == "pending" and due_on and due_on < timezone.localdate()`

---

## Entity 5 (LAST, CUTTABLE) - `AuditSeal` [ASL-] -- **bullet 3 Audit Trail & Logging**
`apps/procurement/models/RiskComplianceManagement/AuditSeals.py`

- [ ] **Bullet 3's PAGE has no table and ships first**: `audit_trail` is a filtered, paginated,
      exportable register over `core.AuditLog` built on `procurement_activity_qs(tenant)` from
      `apps/procurement/views/_helpers.py`. **ZERO `core` migrations** - do not add a column to
      `core.AuditLog` from a procurement build (research §4.2 note 2, and L43 with a concurrent
      session in this checkout).
- [ ] **`AuditSeal` is what makes "tamper-proof" true**, and it is honest about being
      tamper-**EVIDENT**: alteration is DETECTABLE, storage is not immutable. That sentence goes on
      the page, not only in the docstring. `hashlib` + `json` only - **no new dependency**.
- [ ] **Documented CRUD deviation: NO edit route and NO delete route.** A seal whose digest can be
      edited proves nothing, and deleting a seal breaks exactly the chain it exists to protect.
      In-repo precedent: `CostForecast` (6.15) ships with no edit route; `InvoiceMatchVariance`
      (6.13) is evidence, not a record. Put the reason in the module docstring AND on the page so
      the reviewer does not flag it as a CRUD-completeness miss.

### `AuditSeal(TenantNumbered)` - `NUMBER_PREFIX = "ASL"`
- [ ] `GENESIS_DIGEST = "0" * 64`; `MAX_SEAL_ROWS = 50000`; `ALGORITHM = "sha256"`;
      `RETENTION_NOTE` (10-year OFAC statement, shared with the screening register)
- [ ] `from_log_id` BigIntegerField(**editable=False**) - lowest `core.AuditLog.id` covered
- [ ] `to_log_id` BigIntegerField(**editable=False**) - highest id covered
- [ ] `period_start` DateTimeField(**editable=False**) - **DERIVED** = `at` of the first row in the range
- [ ] `period_end` DateTimeField(**editable=False**) - **DERIVED** = `at` of the last row in the range
- [ ] `row_count` PositiveIntegerField(default=0, **editable=False**) - **DERIVED**
- [ ] `digest` CharField(max_length=64, **editable=False**) - **DERIVED**
- [ ] `prev_seal` FK `"self"` SET_NULL null blank **editable=False**, `related_name="next_seals"`
- [ ] `prev_digest` CharField(max_length=64, blank=True, **editable=False**) - `prev_seal.chain_digest` or `GENESIS_DIGEST`
- [ ] `chain_digest` CharField(max_length=64, **editable=False**) - **DERIVED**
- [ ] `algorithm` CharField(max_length=16, default="sha256", **editable=False**)
- [ ] `sealed_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**, `related_name="procurement_audit_seals"`
- [ ] `sealed_at` DateTimeField(auto_now_add=True)
- [ ] `note` CharField(max_length=255, blank=True) - the ONLY operator-supplied field, captured on the "Seal now" POST
- [ ] `last_verified_at` DateTimeField(null=True, blank=True, **editable=False**)
- [ ] `last_verify_ok` BooleanField(null=True, **editable=False**) - NULL = never verified
- [ ] `last_verify_detail` CharField(max_length=255, blank=True, **editable=False**)
- [ ] `Meta`: `ordering = ["-to_log_id","-id"]`; `unique_together = (("tenant","number"),)`;
      indexes `(tenant,to_log_id)` **`prc_asl_tnt_tolog_idx`**, `(tenant,sealed_at)` **`prc_asl_tnt_sealed_idx`**
- [ ] `__str__` -> `f"{self.number or 'ASL'} · {self.row_count} rows · {self.digest[:12]}"`

---

## Service / derivation logic - what is DERIVED (never stored editable)

### 4a. Screening disposition guard (bullet 1 - the single most testable rule here)
- [ ] `ComplianceScreening.recount_hits()` - recomputes `hit_count` = `self.hits.count()` and
      `open_hit_count` = `self.hits.filter(disposition="open").count()`, saved with
      `update_fields=["hit_count","open_hit_count","updated_at"]`. Called from
      `screeninghit_create/_edit/_delete/_dispose` views. **Display counters only.**
- [ ] `ComplianceScreening.clear(user, note="")` -> bool. Refuses when `status` is already terminal.
      **Refuses while ANY hit is undisposed, and the guard runs a LIVE query
      (`self.hits.filter(disposition="open").exists()`), never the cached counter** - a stale
      counter must not be able to unlock the gate. On success: `status="cleared"`, stamps
      `decided_by`/`decided_at`/`decision_note`, and sets `next_rescreen_on` to
      `screened_on + DEFAULT_RESCREEN_DAYS` when it is blank.
- [ ] `ComplianceScreening.escalate(user, note)` -> bool. From `pending_review` only. **Note required.**
- [ ] `ComplianceScreening.block(user, note, suspension=None)` -> bool. From `pending_review` or
      `escalated`. **Note required.** Stamps `suspension` when the operator picked one from this
      tenant's `VendorSuspension` rows for the same party. **Creates no suspension itself** - the
      detail page links to `procurement:vsu_create` and shows
      `VendorSuspension.blocking_for(tenant, party_id)` if a block is already in force (research 1.8).
- [ ] **No un-clear / no re-open verb.** A decided screening is evidence; a correction is a NEW
      screening (the `ACTIVITY_FEED_NOTE` posture).
- [ ] `ScreeningHit.dispose(user, disposition, note)` -> bool. From `open` only; `disposition` must
      be in `TERMINAL_DISPOSITIONS`; **note required for EVERY disposition including
      `false_positive`** (OFAC 31 CFR 501.601: a cleared false positive with no record is
      indistinguishable from a check never performed). Stamps `disposed_by`/`disposed_at`, then the
      view calls `screening.recount_hits()`.
- [ ] `ComplianceScreening.retention_until` - **DERIVED property**, `screened_on + RETENTION_YEARS`.
      No purge job; the page states the policy (research 3.4).
- [ ] **Re-screening due board** (`screening_rescreen_board`): supplier/vendor-role parties whose
      most recent `cleared` screening has `next_rescreen_on <= today` (or is NULL and
      `screened_on < today - DEFAULT_RESCREEN_DAYS`), PLUS parties with no screening at all. One
      grouped query over the register - **no stored "due" flag**.
- [ ] **Batch screen** (`screening_batch`, P2, CUTTABLE): a `@tenant_admin_required` `@require_POST`
      that mints one `pending_review`, `checkpoint="periodic"`, `result="clear"` screening per
      active supplier/vendor-role party that has none in `DEFAULT_RESCREEN_DAYS`, capped at
      `BATCH_PARTY_LIMIT`. Reports `{"created": n, "skipped": m, "capped": bool}`.

### 4b. Risk-signal derivation - the inverted scales (bullet 2)
All of the following happen in `SupplierRiskSignal.save()` BEFORE `super().save()`, in this order:
- [ ] 1. **Stamp the scale.** `scale_min, scale_max, higher_is_better = METRIC_SCALES.get(self.metric,
      (None, None, True))`. Always overwritten from the table - the three columns are
      `editable=False` and never operator-supplied. `metric="other"` yields `(None, None, True)`.
- [ ] 2. **Derive `risk_position`** (0 = safest, 100 = riskiest). `None` when either bound is NULL or
      `scale_max == scale_min`:
      `clamped = min(max(value, scale_min), scale_max)`;
      `position = (clamped - scale_min) / (scale_max - scale_min) * 100`;
      `risk_position = (100 - position) if higher_is_better else position`, `.quantize(Decimal("0.01"))`.
      Worked examples to assert in tests: **FHR 42 -> 58.59 (elevated)**; **SER 7 -> 75.00
      (critical)**; **PAYDEX 80 -> 20.20 (low)**; **DSO 90 days -> 50.00 (elevated)**.
- [ ] 3. **Derive `band`** from `BAND_THRESHOLDS` (`< 25 low`, `< 50 watch`, `< 75 elevated`, else
      `critical`); `"unrated"` when `risk_position is None`.
- [ ] 4. **Derive `previous_value` + `trend`.** Prior row = the same
      `(tenant, party, provider, metric)` with `observed_on <= self.observed_on`, `.exclude(pk=self.pk)`,
      `.order_by("-observed_on","-id").first()` - **one query, backed by `prc_srs_series_idx`**.
      `trend = "new"` when there is none. Otherwise compare **`risk_position`, not the raw value**
      (this is the whole point of the inverted scales): `deteriorated` when
      `risk_position - prior.risk_position > TREND_EPSILON`, `improved` when the gap is below
      `-TREND_EPSILON`, else `stable`. When either `risk_position` is NULL, fall back to the raw
      values plus `higher_is_better`; if still undecidable, `"stable"`.
- [ ] `breaches_minimum` - **DERIVED property**: `True` when `MINIMUM_ACCEPTABLE` holds a limit for
      the metric and the value is on the wrong side of it given `higher_is_better`. **Advisory
      badge only. It never blocks anything** (research 2.7 / the `ReceiptTolerancePolicy` posture).
- [ ] `raise_deterioration_alert(user=None)` -> `ProcurementAlert | None`. **Called by the create/edit
      VIEW after a successful save, NOT from `save()`** - a table write hidden inside `save()` would
      fire in every seeder and test. Guards, all four: `trend == "deteriorated"`, `band in
      ALERT_BANDS`, `self.alert_id is None`, and no existing `ProcurementAlert` for the same party+
      metric still in `OPEN_STATUSES`. Creates `kind="risk"`,
      `severity="critical" if band == "critical" else "warning"`,
      `title=f"{party} {metric_display} deteriorated to {band_display}"`,
      `link_url=f"/procurement/risk-signals/{pk}/"` (**internal path with a single leading slash** -
      `ProcurementAlert.clean()` rejects anything else), then stamps `self.alert`. Idempotent by
      construction - exactly `run_renewal_alerts` / `Backorder.raise_alert`.
- [ ] **`ProcurementAlert.KIND_CHOICES` gains `("risk", "Risk")`** - a one-line **surgical `Edit`**
      to `apps/procurement/models/DashboardPortal/ProcurementAlerts.py` plus an `AlterField` in the
      6.17 migration. `max_length=12` already fits. Precedent: `0012_alter_procurementalert_kind.py`
      added `("contract","Contract")` for 6.8. **Never full-rewrite that file (L43)** - and add
      `"risk": "badge-red"` to `kind_css` in the same edit.
- [ ] Verbs: `mark_reviewed(user, note="")` (from `new`), `mark_actioned(user, note)` (note
      required), `dismiss(user, note)` (note required). Each re-checks its guard INSIDE itself and
      returns a bool (MSF precedent).
- [ ] **Refresh-due board** (`risksignal_refresh_board`): the latest signal per
      `(party, provider, metric)` whose `next_refresh_on <= today` or whose `observed_on` is older
      than `STALE_AFTER_DAYS`, plus supplier/vendor-role parties with no signal at all. Computed,
      no stored flag.
- [ ] **Honesty, on the page and in the docstring:** there is no live bureau call anywhere in this
      repo. Every row is captured by a person or a CSV and shows `captured_by` / `observed_on` /
      `source_ref` provenance. The page links to `scm:riskassessment_list` for the internal
      4-factor composite (`scm.SupplierRiskAssessment`) and **ships no second composite score**
      (research 2.10).

### 4c. Fraud `scan()` - one bullet per rule, naming the exact source models and fields
- [ ] `FraudAlert.scan(tenant, start, end, rules=None, user=None) -> {rule: newly_raised_count}`.
      Operator-triggered POST. Returns **newly raised** counts only (a refreshed row is not a new
      find). Unknown rule names in `rules` are **IGNORED, never raised** (L11 - the list arrives
      from a POST checkbox group). Whole pass inside one `transaction.atomic()`. Shared
      `_scan_context(tenant, start, end, wanted)` prefetch; `_existing_by_key` chunked at
      `_DEDUPE_LOOKUP_CHUNK`; `_upsert` refreshes `amount` / `detail` / `document_date` /
      `matched_on` and the dimension `*_id`s but **NEVER `status` / `resolution_note` /
      `resolved_by` / `resolved_at`** - a re-scan can never re-open settled work.
- [ ] **Deferred imports inside the methods** (MSF module-docstring rule): this module is imported
      while `apps.procurement.models.__init__` is still executing.
      **`RECOGNISED_INVOICE_STATUSES` and `SPEND_PO_STATUSES` are imported from
      `apps.procurement.models.SpendAnalyticsReporting.MaverickFindings`** - do NOT make a fourth
      copy; two pages must never disagree about what counts as spend.
- [ ] **R1 `vendor_employee_match`** (research 4.1 - the bullet's own words "vendor conflicts of
      interest"). Vendor set = `core.PartyRole.objects.filter(tenant=tenant,
      role__in=("vendor","supplier"), status="active").values_list("party_id", flat=True)`;
      employee set = the same with `role="employee"`. Three attribute joins, each tenant-scoped:
      * `tax_id` - `core.Party.objects.filter(tenant=tenant).exclude(tax_id="").values_list("id","tax_id","created_at")`, key = `tax_id` upper-cased with non-alphanumerics stripped.
      * `address` - `core.Address.objects.filter(tenant=tenant).exclude(line1="").values_list("party_id","line1","city")`, key = `f"{line1}|{city}"` lower-cased with whitespace runs collapsed.
      * `contact` - `core.ContactMethod.objects.filter(tenant=tenant).exclude(value="").values_list("party_id","kind","value")`, key = `value.strip().lower()`, reduced to digits-only for `kind in ("phone","mobile")`.
      Emit one candidate per (vendor party, employee party) pair inside a key group.
      **Skip any group larger than `MAX_GROUP_SIZE`** (200 parties sharing one office address is a
      data-quality problem, not 19,900 alerts) and stop each attribute at
      `MAX_PAIRS_PER_ATTRIBUTE`; report both in the scan summary as `skipped_groups` / `capped`.
      `vendor` = the vendor-role party, `related_party` = the employee-role party,
      `document_date` = the later of the two `created_at` dates, `amount` = None,
      `matched_on` = the masked attribute string.
- [ ] **R2 `self_approval`** (4.2 - segregation of duties; **zero false positives**).
      `procurement.RequisitionApproval.objects.filter(tenant=tenant, decided_at__gte=start,
      decided_at__lt=end, approver__isnull=False).select_related("requisition")`, fires where
      `approval.approver_id == approval.requisition.requester_id`. Stamps `approval`,
      `requisition`; `document_date = approval.decided_at.date()`;
      `amount = requisition.estimated_total`; `detail` names the approver, the requisition number
      and `tier/tier_count`.
- [ ] **R3 `duplicate_vendor`** (4.3 - **flag only, never merge**; supplier-master dedup stays with
      6.4 / `core.Party`). Vendor-role parties only. Three groupings: normalised NAME (lower-cased,
      whitespace collapsed, `NAME_SUFFIXES` stripped, non-alphanumerics removed), `tax_id` and
      `address` (same normalisers as R1). Pair emission is deterministic - `vendor` = the LOWER pk,
      `related_party` = the higher - so the row and its dedupe key always agree.
      `document_date` = the later `created_at.date()`. Same `MAX_GROUP_SIZE` /
      `MAX_PAIRS_PER_ATTRIBUTE` caps. The detail page links to BOTH parties and says "flagged, not
      merged".
- [ ] **R4 `backdated_po`** (4.4 - **distinct from 6.14's `po_less_invoice`, which is "no PO at
      all"**). `procurement.SupplierInvoice.objects.filter(tenant=tenant,
      status__in=RECOGNISED_INVOICE_STATUSES, invoice_date__gte=start, invoice_date__lt=end)
      .exclude(invoice_type="credit_memo").exclude(purchase_order__isnull=True)
      .select_related("purchase_order","vendor")`. Fires when
      `Coalesce(po.order_date, po.created_at.date()) > invoice.invoice_date + BACKDATE_GRACE_DAYS`.
      Stamps `supplier_invoice`, `purchase_order`, `vendor`;
      `amount = invoice.total`; `document_date = invoice.invoice_date`. The page states the
      distinction from 6.14 in one line.
- [ ] **R5 `screening_unresolved`** (4.5 - the cross-link that makes 6.17 ONE sub-module rather than
      five pages). `scm.PurchaseOrder.objects.filter(tenant=tenant, status__in=SPEND_PO_STATUSES)`
      annotated `doc_date = Coalesce("order_date", TruncDate("created_at"))` inside the window,
      whose `vendor_id` has a `ComplianceScreening` in this tenant with `screened_on <= doc_date`
      carrying a hit whose `disposition in ("open","true_match")`. Stamps `purchase_order`,
      `vendor`, `screening`; `amount = po.total`; `document_date = doc_date`.
      *(The `TruncDate` note from `MaverickFindings._scan_context` applies verbatim: safe because
      `TIME_ZONE = "UTC"` matches the connection - re-check if that ever changes.)*
- [ ] **R6 `new_vendor_rush`** (4.6). For each vendor-role `core.Party` whose `created_at.date()`
      falls within `[start - NEW_VENDOR_DAYS, end)`, sum recognised `SupplierInvoice.total` with
      `invoice_date` between the party's creation date and `+ NEW_VENDOR_DAYS`; fire when the sum
      `>= NEW_VENDOR_AMOUNT`. Stamps `vendor`, `supplier_invoice` = the LARGEST single invoice in
      the run (so the detail page has a document to open); `amount` = the summed total;
      `document_date` = the party's creation date. One alert per vendor.
- [ ] `build_dedupe_key()` - deterministic per rule, and **order-independent for the pair rules** so
      the same fact is never two rows: `vem:{min(a,b)}:{max(a,b)}:{attr}` ·
      `selfapp:{approval_id}` · `dupven:{min(a,b)}:{max(a,b)}:{attr}` · `bdpo:{invoice_id}` ·
      `scrunres:{po_id}` · `nvrush:{vendor_id}`. Fallback for a hand-raised row with no pointer:
      `f"{rule}:manual:{secrets.token_hex(8)}"` (MSF precedent - a blank key would turn a data-entry
      mistake into an IntegrityError 500).
- [ ] `clean()` - at least one source pointer; `rule` in `RULE_CHOICES`; **a cross-tenant check on
      EVERY FK** (`vendor`, `related_party`, `requisition`, `purchase_order`, `supplier_invoice`,
      `approval`, `screening`, `assigned_to`'s tenant) using `_id` guards, never bare `getattr`
      (the `VendorSuspension.clean()` lesson - `getattr` on an unset FK raises
      `RelatedObjectDoesNotExist`); and a `dedupe_key` pre-check that renders as a field error
      instead of a unique-constraint 500.
- [ ] Verbs: `investigate(user)` (open -> investigating, no note),
      `substantiate(user, note, suspension=None)`, `unsubstantiate(user, note)`,
      `refer(user, note)` - the three terminal verbs require a note and share a `_dispose()` body
      exactly like MSF. `substantiate` optionally stamps a `VendorSuspension` the operator picked.
- [ ] **The scan writes NOTHING to the spine** - no suspension, no invoice block, no PO hold.
      State it in the module docstring and on the scan page (SAP BIS "park, don't block", 4.14).
- [ ] **The page says "rules", never "AI"/"algorithms learn"** - deterministic SQL only
      (4.15 / the 6.14 naming-honesty precedent). The scan page renders the eight tuning constants
      read-only so the thresholds are visible rather than folkloric.

### 4d. Policy versioning + attestation (bullet 5)
- [ ] `ProcurementPolicy.publish(user)` -> bool. Guard: `status == "draft"` AND `effective_from` is
      set (publishing with no effective date is what makes an attestation unanswerable). Sets
      `status="published"`, `published_at`, `published_by`, then calls `raise_attestations(user)`
      when `requires_attestation`.
- [ ] `ProcurementPolicy.raise_attestations(user)` -> int. Audience:
      `User.objects.filter(tenant=self.tenant, is_active=True, status="active")`; when
      `applicable_org_unit` is set, narrowed to users whose `party` has a
      `core.Employment` row with `tenant=self.tenant, org_unit=self.applicable_org_unit,
      status="active"` (**verified path: `accounts.User.party` -> `core.Employment.party` ->
      `core.Employment.org_unit`** - there is no direct User->OrgUnit FK). One
      `get_or_create(tenant=…, policy=self, user=u, defaults={"due_on": today + attestation_due_days})`
      per user, so a re-publish/repair is idempotent. Returns the number CREATED.
- [ ] `ProcurementPolicy.archive(user)` -> bool. From `draft` or `published`. Stamps `archived_at`.
      **Existing attestations are never rewritten** (NAVEX: retain attestations for current AND
      previous versions).
- [ ] `ProcurementPolicy.new_version(user)` -> the new DRAFT policy. Copies title/category/scope/
      body/summary/document/owner/`attestation_due_days`/`enforced_by`, sets
      `previous_version=self`, `status="draft"`, blanks `published_at`/`published_by`/`archived_at`,
      and bumps `version_number` via `_next_version(current)`: split on `"."`, increment the LAST
      numeric segment (`"1.0" -> "1.1"`, `"2" -> "3"`); a non-numeric tail appends `".1"`.
      **Guard the `("tenant","title","version_number")` unique constraint** - a clash returns a
      `messages.error` and no row, never a 500. Publishing v2 raises FRESH attestation rows and
      **v1's rows are never touched** (research 5.4).
- [ ] `PolicyAttestation.acknowledge(user, note="")` -> bool. From `pending` only. **The view
      refuses unless `request.user_id == attestation.user_id`** - a signature signed by somebody
      else is not a signature. Superusers are NOT exempt. Stamps `acknowledged_at` +
      `acknowledgement_note`.
- [ ] `PolicyAttestation.mark_exempt(user, reason)` -> bool. `@tenant_admin_required`. From
      `pending` only. **Reason required.**
- [ ] **Overdue board** (`policy_overdue_board`): pending attestations past `due_on`, grouped by
      policy, with an admin `@require_POST` that raises **one idempotent `ProcurementAlert` per
      overdue attestation** (`kind="risk"`, `severity="warning"`, `assigned_to` = the attestation's
      own user, `link_url=f"/procurement/my-policies/"`), stamping `attestation.alert` and skipping
      any row that already has one or already has an open alert. No email sender is wired anywhere -
      say so on the page (research 5.7 / §7.8).
- [ ] `attestation_rate` etc. are **DERIVED annotation-aware properties**, never stored columns; the
      list view supplies `_attested_count` / `_target_count` annotations so the register does not
      issue two queries per row.

### 4e. Audit-seal digest chain (bullet 3)
- [ ] **Ranges are keyed by `core.AuditLog.id`, NOT by time.** `id` is a monotonic autoincrement, so
      an id-keyed chain has no late-arrival hole; a time-keyed one does (a row committing with an
      `at` inside an already-sealed window would be missed by both seals). `period_start` /
      `period_end` are DERIVED metadata taken from the first/last row's `at`, for humans only.
- [ ] `AuditSeal.canonical_line(row)` - **PIN THIS EXACTLY; changing it silently invalidates every
      prior seal.** `"|".join([str(row.id), row.at.isoformat(), str(row.user_id or ""),
      str(row.content_type_id or ""), str(row.object_id or ""), row.action or "", row.target or "",
      json.dumps(row.changes, sort_keys=True, separators=(",", ":"), default=str)])`.
      `sort_keys=True` + fixed separators is what makes the JSON canonical; `default=str` stops a
      `Decimal`/`date` inside `changes` from raising.
- [ ] `AuditSeal.compute_digest(rows)` - one `hashlib.sha256()`; for each row in **ascending id
      order**, `update(canonical_line(row).encode("utf-8"))` then `update(b"\n")`. Returns
      `hexdigest()`.
- [ ] `chain_digest = sha256(f"{prev_digest}:{digest}".encode("utf-8")).hexdigest()` where
      `prev_digest = prev_seal.chain_digest or GENESIS_DIGEST`. This is `h_i = H(h_{i-1} ‖ record_i)`:
      altering any sealed row breaks every subsequent link.
- [ ] `AuditSeal.seal_now(tenant, user, note="")` -> `(seal, message)`. Inside
      `transaction.atomic()`: `prev = objects.filter(tenant=tenant).order_by("-to_log_id","-id").first()`;
      rows = `AuditLog.objects.filter(tenant=tenant, id__gt=(prev.to_log_id if prev else 0))
      .order_by("id")[:MAX_SEAL_ROWS]`. **Refuse an empty range** with
      `"No new audit rows since <prev.number>."` - an empty seal is chain spam, not evidence.
      Stamps `from_log_id`/`to_log_id`/`row_count`/`period_start`/`period_end`/`digest`/
      `prev_seal`/`prev_digest`/`chain_digest`/`sealed_by`.
- [ ] `AuditSeal.verify()` -> `(ok: bool, detail: str)`. Re-reads
      `AuditLog.objects.filter(tenant=…, id__gte=from_log_id, id__lte=to_log_id).order_by("id")`,
      re-computes the digest and the chain digest, and compares. On failure names the FIRST
      offending log id, or reports `"{n} of {row_count} sealed rows are missing"` when the count
      differs. Stamps `last_verified_at` / `last_verify_ok` / `last_verify_detail`. **Read-mostly:
      the only write is the three verify stamps.**
- [ ] `AuditSeal.verify_chain(tenant)` -> `(ok, first_broken_seal, detail)`. Walks every seal
      oldest-first; rendered on `audit_trail` as one line ("chain verified through ASL-00003").
- [ ] **State the limits on the page, verbatim:** this is tamper-**EVIDENT**, not tamper-proof
      storage; a seal proves the range is unchanged **since it was sealed** and cannot prove a row
      was never deleted before the first seal; DB-level append-only / WORM / SIEM streaming is
      infrastructure and is out of scope (research 3.6, §7.9).

---

## Backend package layout (MANDATORY - four layers, one file per entity group)

### `apps/procurement/models/RiskComplianceManagement/`
- [ ] `__init__.py` (own commit even if it only re-exports)
- [ ] `Screenings.py` - `ComplianceScreening` + `ScreeningHit` + `LIST_SOURCE_CHOICES`, `CHECKPOINT_CHOICES`, `METHOD_CHOICES`, `RESULT_CHOICES`, `STATUS_CHOICES`, `DISPOSITION_CHOICES`, `MATCH_TYPE_CHOICES`
- [ ] `RiskSignals.py` - `SupplierRiskSignal` + `PROVIDER_CHOICES`, `METRIC_CHOICES`, `METRIC_SCALES`, `BAND_CHOICES`, `TREND_CHOICES`, `REVIEW_STATUS_CHOICES`
- [ ] `FraudAlerts.py` - `FraudAlert` + `RULE_CHOICES`, `SEVERITY_CHOICES`, `STATUS_CHOICES`
- [ ] `Policies.py` - `ProcurementPolicy` + `PolicyAttestation` + `CATEGORY_CHOICES`, both `STATUS_CHOICES`
- [ ] `AuditSeals.py` - `AuditSeal` (LAST / cuttable)
- [ ] Every module starts `from apps.procurement.models._base import *  # noqa: F401,F403`;
      **absolute imports only**; every cross-app FK **by string**; sibling MODEL classes needed by
      `scan()` imported **inside the method** (MSF import-discipline rule).

### `apps/procurement/forms/RiskComplianceManagement/` - same five filenames
- [ ] Each form is `class X(TenantUniqueMixin, TenantModelForm)` - `TenantUniqueMixin` **before**
      `TenantModelForm` (stamps `instance.tenant` before `full_clean()`, which every model
      `clean()` cross-tenant check reads). Each calls `_reject_foreign(self, cleaned, [...])` for
      its own tenant-scoped FK list.

### `apps/procurement/views/RiskComplianceManagement/` - eight modules
- [ ] `Screenings.py`, `ScreeningHits.py`, `RiskSignals.py`, `FraudAlerts.py`, `FraudScan.py`
      (the scan form/POST + the triage board - separate module, the `MaverickDashboard.py`
      precedent), `Policies.py`, `Attestations.py`, `AuditTrail.py` (the register + export + the
      seal register/detail/create/verify).
- [ ] Every module starts `from apps.procurement.views._common import *  # noqa: F401,F403`.
      Sibling models imported as MODULES (`from apps.procurement.models.RiskComplianceManagement.Screenings import ComplianceScreening`),
      **never** `from apps.procurement.models import X` - that is a star-import cycle at URLconf
      import while the package is being wired.
- [ ] Every queryset `filter(tenant=request.tenant)`; **never `.all()`**. Every object
      `get_object_or_404(..., tenant=request.tenant)`, except `ScreeningHit`, which uses
      `screening__tenant=request.tenant`.
- [ ] `_need_tenant(request, what)` guard on every list/board/verb (superuser has `tenant=None`).
- [ ] `_is_admin(request)` mirrors `@tenant_admin_required` exactly so a hidden button and a refused
      POST always agree.
- [ ] Decorator order on privileged verbs: `@login_required` `@tenant_admin_required`
      `@require_POST` (L27, in that order).
- [ ] Every verb runs under `select_for_update()` inside `transaction.atomic()` and calls
      `write_audit_log(request.user, obj, "update", changes)` after the commit (the `crud_*` helpers
      audit themselves; hand-rolled save paths must not).

### `apps/procurement/urls/RiskComplianceManagement/` - same eight filenames + `__init__.py`
- [ ] Literal routes before `<int:pk>` in every module (first-match-wins IS behaviour).
- [ ] New first path segments, **all confirmed free against the list in
      `apps/procurement/urls/__init__.py`**: `screenings/`, `screening-hits/`, `rescreening-due/`,
      `risk-signals/`, `risk-refresh-due/`, `fraud-alerts/`, `fraud-scan/`, `fraud-board/`,
      `policies/`, `policy-attestations/`, `my-policies/`, `policy-overdue/`, `audit-trail/`,
      `audit-seals/`. **Re-check against 6.16's segments before committing (L43).**

### Re-export blocks - TARGETED `Edit`, never `Write` (L43: another session is in this checkout)
- [ ] `apps/procurement/models/__init__.py` - append imports (from the entity MODULES, the 6.13/6.14
      precedent) + append to `__all__`: `ComplianceScreening`, `ScreeningHit`,
      `SupplierRiskSignal`, `FraudAlert`, `ProcurementPolicy`, `PolicyAttestation`, `AuditSeal`.
- [ ] `apps/procurement/forms/__init__.py` - append the seven form classes.
- [ ] `apps/procurement/views/__init__.py` - append every view function + its `__all__` entries.
- [ ] `apps/procurement/urls/__init__.py` - `from .RiskComplianceManagement import urlpatterns as
      _rcm_riskcompliance` and splat it **LAST** in `urlpatterns`, with the same
      "every first segment it claims is new" comment 6.13/6.14/6.15 carry. Extend the docstring's
      segment list.
- [ ] **Forgetting any of these four blocks is an ImportError / `NoReverseMatch` at runtime.**

---

## Forms - `Meta.fields` and, critically, the EXCLUSIONS

- [ ] **`ComplianceScreeningForm`** - fields: `party`, `list_source`, `checkpoint`, `method`,
      `screened_on`, `list_as_of`, `reference`, `result`, `match_threshold`,
      `threshold_rationale`, `next_rescreen_on`, `evidence`, `notes`.
      **EXCLUDED:** `tenant`, `number`, `status`, `hit_count`, `open_hit_count`, `screened_by`,
      `decided_by`, `decided_at`, `decision_note`, `suspension`, `created_at`, `updated_at`.
      `method` choices narrowed to `SELECTABLE_METHODS` in `__init__`; `clean_method()` rejects
      `api_feed`. `_reject_foreign(self, cleaned, ["party", "evidence"])`.
      `screened_by` is stamped by the view from `request.user`.
- [ ] **`ScreeningHitForm`** - fields: `matched_name`, `matched_list`, `match_score`, `match_type`,
      `entry_reference`, `program`, `country`, `remarks`.
      **EXCLUDED:** `screening` (comes from the URL, never a POST field - otherwise it is an IDOR),
      `disposition`, `disposition_note`, `disposed_by`, `disposed_at`, `created_at`.
- [ ] **`ScreeningHitDispositionForm`** (plain `forms.Form`) - `disposition`
      (`TERMINAL_DISPOSITIONS` only) + `disposition_note` (**required**).
- [ ] **`SupplierRiskSignalForm`** - fields: `party`, `provider`, `metric`, `observed_on`, `value`,
      `next_refresh_on`, `source_ref`, `evidence`, `notes`.
      **EXCLUDED (all DERIVED or system):** `tenant`, `number`, `scale_min`, `scale_max`,
      `higher_is_better`, `risk_position`, `band`, `previous_value`, `trend`, `review_status`,
      `review_note`, `reviewed_by`, `reviewed_at`, `captured_by`, `alert`, `created_at`,
      `updated_at`. `_reject_foreign(self, cleaned, ["party", "evidence"])`.
      `clean()` rejects a `value` outside the metric's registered scale by more than 20% of the
      span (a typo'd SER of 70 is not a real observation) and rejects a future `observed_on`.
- [ ] **`FraudAlertForm`** (the hand-raise path, for what no detector can see) - fields: `rule`,
      `severity`, `document_date`, `amount`, `detail`, `matched_on`, `assigned_to`, `vendor`,
      `related_party`, `requisition`, `purchase_order`, `supplier_invoice`, `approval`, `screening`.
      **EXCLUDED:** `tenant`, `number`, `status`, `dedupe_key`, `detected_at`, `resolution_note`,
      `resolved_by`, `resolved_at`, `suspension`, `created_at`, `updated_at`.
      `_reject_foreign` over all seven pointer FKs.
- [ ] **`FraudScanForm`** (plain `forms.Form`) - `start` (date, required), `end` (date, required,
      `> start`), `rules` (MultipleChoiceField over `RULE_CHOICES`, `required=False` = all).
      Rejects a window longer than `MAX_SCAN_WINDOW_DAYS = 400`.
- [ ] **`FraudDispositionForm`** (plain `forms.Form`) - `action` + `resolution_note` +
      optional `suspension` (queryset narrowed to this tenant's `VendorSuspension` rows for the
      alert's vendor).
- [ ] **`ProcurementPolicyForm`** - fields: `title`, `category`, `version_number`,
      `previous_version`, `applicable_org_unit`, `owner`, `summary`, `body`, `document`,
      `effective_from`, `review_due_on`, `requires_attestation`, `attestation_due_days`,
      `enforced_by`.
      **EXCLUDED:** `tenant`, `number`, `status`, `published_at`, `published_by`, `archived_at`,
      `created_at`, `updated_at`. `previous_version` queryset excludes `self.instance.pk`
      (a policy cannot supersede itself). `_reject_foreign(self, cleaned,
      ["previous_version", "applicable_org_unit", "document"])`.
- [ ] **`PolicyAttestationForm`** - fields: `policy`, `user`, `due_on`. `user` queryset narrowed to
      `User.objects.filter(tenant=self.tenant, is_active=True)`.
      **EXCLUDED:** `tenant`, `status`, `acknowledged_at`, `acknowledgement_note`, `exempt_reason`,
      `alert`, `created_at`, `updated_at`.
- [ ] **`AuditSealForm`** - fields: `note` **ONLY**. Every other column is a computed digest, a
      derived boundary or a system stamp. There is no edit form at all.
- [ ] **Blanket rule to check at review time:** no form anywhere carries `tenant`, an auto-`number`,
      a `*_by`/`*_at` system stamp, a workflow-controlled `status`/`disposition`/`review_status`, a
      derived score/band/trend/count/digest, or a `dedupe_key` (L20/L22/L28).

---

## Views + URLs (namespace `procurement`) - the url names ARE the contract

### Screenings (`urls/RiskComplianceManagement/Screenings.py`)
- [ ] `screenings/` -> `screening_list` · search `number, party__name, reference, notes`; filters
      `party` (int), `list_source`, `checkpoint`, `result`, `status` (enum values validated against
      the CHOICES dict before the filter spec is added - L11); stat cards (`pending`,
      `open_hits`, `blocked`, `rescreen_due`); pagination via `crud_list`.
      Context: `objects`/`page_obj`, `list_source_choices`, `checkpoint_choices`, `result_choices`,
      `status_choices`, `parties`, `stats`, `is_admin`, `retention_note`.
- [ ] `screenings/add/` -> `screening_create` · `screenings/<int:pk>/` -> `screening_detail`
      (hits table + `allowed_actions` + the party's `blocking_for()` row + a link to
      `scm:riskassessment_list`) · `screenings/<int:pk>/edit/` -> `screening_edit` (refused once
      terminal) · `screenings/<int:pk>/delete/` -> `screening_delete` (`@tenant_admin_required`
      `@require_POST`; refused once terminal - it carries a recorded decision)
- [ ] `screenings/<int:pk>/clear/` -> `screening_clear` · `.../escalate/` -> `screening_escalate` ·
      `.../block/` -> `screening_block` - all `@tenant_admin_required` `@require_POST`
- [ ] `screenings/<int:pk>/hits/add/` -> `screeninghit_create`
- [ ] `rescreening-due/` -> `screening_rescreen_board`
- [ ] `screenings/batch/` -> `screening_batch` (`@tenant_admin_required` `@require_POST`, CUTTABLE)
      - **literal `batch/` must sit BEFORE `<int:pk>/`**

### Screening hits (`ScreeningHits.py`) - the Resolution Manager
- [ ] `screening-hits/` -> `screeninghit_list` (cross-screening work queue; filters `disposition`,
      `matched_list`, `match_type`, `screening`, min score) · `screening-hits/<int:pk>/` ->
      `screeninghit_detail` · `.../edit/` -> `screeninghit_edit` · `.../delete/` ->
      `screeninghit_delete` (`@require_POST`) · `.../dispose/` -> `screeninghit_dispose`
      (`@tenant_admin_required` `@require_POST`)

### Risk signals (`RiskSignals.py`)
- [ ] `risk-signals/` -> `risksignal_list` (search `number, party__name, source_ref, notes`;
      filters `party`, `provider`, `metric`, `band`, `trend`, `review_status`; stats
      `critical`, `deteriorating`, `unreviewed`, `refresh_due`) · `risk-signals/add/` ->
      `risksignal_create` · `risk-signals/<int:pk>/` -> `risksignal_detail` (the last
      `SERIES_LIMIT` observations for the same party+provider+metric, the party's latest
      `scm.SupplierRiskAssessment` with a link to `scm:riskassessment_list`, `breaches_minimum`,
      the raised alert if any) · `.../edit/` · `.../delete/` (`@tenant_admin_required`
      `@require_POST`) · `.../review/` -> `risksignal_review` (`@require_POST`, `action` +
      `review_note`)
- [ ] `risk-refresh-due/` -> `risksignal_refresh_board`

### Fraud (`FraudAlerts.py` + `FraudScan.py`)
- [ ] `fraud-alerts/` -> `fraudalert_list` (search `number, detail, matched_on, vendor__name`;
      filters `rule`, `status`, `severity`, `vendor`, `assigned_to`) · `fraud-alerts/add/` ->
      `fraudalert_create` · `fraud-alerts/<int:pk>/` -> `fraudalert_detail` (both parties, every
      source document, the 6.4 block link, `allowed_actions`) · `.../edit/` (refused once
      terminal) · `.../delete/` (`@tenant_admin_required` `@require_POST`, refused once terminal) ·
      `.../disposition/` -> `fraudalert_disposition` (`@tenant_admin_required` `@require_POST`)
- [ ] `fraud-scan/` -> `fraud_scan` (GET renders the window form + the read-only constants + the
      not-buildable bank-detail note; POST runs `FraudAlert.scan()` and reports
      `{rule: newly_raised}` + `skipped_groups` + `capped`; the POST leg is
      `@tenant_admin_required`)
- [ ] `fraud-board/` -> `fraud_board` (open alerts by rule/severity/age + the **6.13 duplicate-invoice
      citation panel** linking to `procurement:supplierinvoice_list` - pin the exact GET param at
      build time - and a link to `procurement:maverick_dashboard` for 6.14's leakage findings)

### Policies + attestations (`Policies.py`, `Attestations.py`)
- [ ] `policies/` -> `policy_list` (search `number, title, summary, enforced_by`; filters
      `category`, `status`, `applicable_org_unit`, `requires_attestation`; annotated
      `_attested_count` / `_target_count`) · `policies/add/` -> `policy_create` ·
      `policies/<int:pk>/` -> `policy_detail` (roster + rate + version chain both directions) ·
      `.../edit/` (refused once published - a published policy changes by NEW VERSION) ·
      `.../delete/` (`@tenant_admin_required` `@require_POST`; refused once published) ·
      `.../publish/` -> `policy_publish` · `.../archive/` -> `policy_archive` ·
      `.../new-version/` -> `policy_new_version` - the three verbs `@tenant_admin_required`
      `@require_POST`
- [ ] `policy-attestations/` -> `policyattestation_list` (filters `policy`, `status`, `user`,
      `overdue=1`) · `policy-attestations/add/` -> `policyattestation_create` ·
      `policy-attestations/<int:pk>/` -> `policyattestation_detail` · `.../edit/` · `.../delete/`
      (`@tenant_admin_required` `@require_POST`) · `.../sign/` -> `attestation_sign`
      (`@require_POST`, **owner-only**) · `.../exempt/` -> `attestation_exempt`
      (`@tenant_admin_required` `@require_POST`)
- [ ] `my-policies/` -> `policy_mine` - `@login_required`, **STAFF-facing, not a login-gated portal
      page** (L32): the signed-in user's pending/overdue attestations with a sign-off POST per row
- [ ] `policy-overdue/` -> `policy_overdue_board` (GET the board; POST raises the chase alerts,
      `@tenant_admin_required`)

### Audit trail + seals (`AuditTrail.py`)
- [ ] `audit-trail/` -> `audit_trail` - filters `user`, `action`, `content_type`, `date_from`,
      `date_to`, `object_id`, `q` (over `target`); pagination; the retention statement; the chain
      status line; the "tamper-evident, not tamper-proof" note
- [ ] `audit-trail/export/` -> `audit_trail_export` - CSV through **`csv_safe()` on EVERY cell**
      (`target`, the user label and the `changes` JSON are all user-authored text and Excel executes
      a leading `=`/`+`/`-`/`@`)
- [ ] `audit-seals/` -> `auditseal_list` · `audit-seals/<int:pk>/` -> `auditseal_detail` ·
      `audit-seals/seal/` -> `auditseal_create` (`@tenant_admin_required` `@require_POST`,
      **literal `seal/` BEFORE `<int:pk>/`**) · `audit-seals/<int:pk>/verify/` ->
      `auditseal_verify` (`@require_POST`)
- [ ] **No `auditseal_edit`, no `auditseal_delete`** - documented deviation, reason on the page.

---

## Templates - `templates/procurement/riskcompliance/`
Two levels, bare page filenames, never flat `<entity>_<page>.html`.
- [ ] `screening/list.html` · `screening/detail.html` · `screening/form.html`
- [ ] `screeninghit/list.html` · `screeninghit/detail.html` · `screeninghit/form.html`
- [ ] `risksignal/list.html` · `risksignal/detail.html` · `risksignal/form.html`
- [ ] `fraudalert/list.html` · `fraudalert/detail.html` · `fraudalert/form.html`
- [ ] `policy/list.html` · `policy/detail.html` · `policy/form.html`
- [ ] `attestation/list.html` · `attestation/detail.html` · `attestation/form.html`
- [ ] `auditseal/list.html` · `auditseal/detail.html` (**no `form.html`** - creation is a POST button)
- [ ] Standalone board/report pages at the SUB-MODULE root (rule 6, the `maverick_dashboard` /
      `receipt_audit` precedent): `rescreening_due.html`, `risk_refresh_due.html`,
      `fraud_scan.html`, `fraud_board.html`, `policy_overdue.html`, `my_policies.html`,
      `audit_trail.html`
- [ ] Every list page: filter bar reflecting `request.GET` (string enums
      `{% if request.GET.status == value %}selected{% endif %}`; FK pks
      `{% if request.GET.party == p.pk|stringformat:"d" %}` - **never `|slugify`**), an Actions
      column (view / edit / delete-POST + `confirm()` + `{% csrf_token %}`), pagination guarded by
      `has_previous`/`has_next` (L9), and an empty state.
- [ ] Every detail page: Actions sidebar (Edit + Delete-POST, both status-conditional, + Back to
      list) plus the verb forms.
- [ ] **Badges: `badge-green/red/amber/info/muted/slate` ONLY** (L33 - `badge-success` /
      `badge-danger` render completely unstyled). Every badge block ends with an
      `{% else %}{{ obj.get_x_display }}` fallback.
- [ ] `{% extends "base.html" %}`; `{% include "partials/..." %}` unchanged.
- [ ] **No `|safe` anywhere** on `matched_on`, `detail`, `target`, `changes` or `source_ref` - all
      of it is staff-authored text.

---

## Wire-up
- [ ] `apps/procurement/admin.py` - register `ComplianceScreening`, `ScreeningHit`,
      `SupplierRiskSignal`, `FraudAlert`, `ProcurementPolicy`, `PolicyAttestation`, `AuditSeal`
      with `list_display` / `list_filter` / `search_fields`; the seal registers `readonly_fields`
      for every digest column.
- [ ] `apps/core/navigation.py` - **ONE surgical `Edit`** adding the `"6.17"` key after `"6.16"`
      (or after `"6.15"` if 6.16 has not landed yet). **Never full-rewrite this file (L43).**
      Keys must match `NavERP.md:1109-1113` bold text CHARACTER-FOR-CHARACTER, and all five point
      at **distinct** staff pages (L30/L32):
      ```
      "6.17": {
          "Regulatory Compliance Checks":       "procurement:screening_list",
          "Supplier Financial Risk Monitoring": "procurement:risksignal_list",
          "Audit Trail & Logging":              "procurement:audit_trail",
          "Fraud Detection Rules":              "procurement:fraudalert_list",
          "Policy Management & Acknowledgment": "procurement:policy_list",
      },
      ```
      Boards (`rescreening-due`, `risk-refresh-due`, `fraud-scan`, `fraud-board`, `my-policies`,
      `policy-overdue`) and `audit-seals` get **no** sidebar key - each is reached from its
      register, the established rule.
- [ ] **NO `config/settings.py` and NO `config/urls.py` change** - `apps/procurement` already exists
      and is already included.
- [ ] `apps/procurement/models/DashboardPortal/ProcurementAlerts.py` - the one-line
      `("risk", "Risk")` addition to `KIND_CHOICES` + `"risk": "badge-red"` in `kind_css`.
      **Surgical `Edit` only.**

## Seeder - `_seed_risk_compliance(tenant)` in `apps/procurement/management/commands/seed_procurement.py`
- [ ] Called LAST in `handle()`, after `_seed_budget_cost(tenant)`. Surgical `Edit`, never a rewrite.
- [ ] Per-tenant existence guard at the top:
      `if ComplianceScreening.objects.filter(tenant=tenant).exists(): return` (print the standard
      "Data already exists. Use --flush to re-seed." warning). **Idempotent - safe to run twice.**
- [ ] Reuse existing rows only: pick supplier parties via
      `Party.objects.filter(tenant=tenant, roles__role__in=("supplier","vendor"))` and employee
      parties via `roles__role="employee"`; **never create a new vendor master**.
- [ ] Screenings: one `cleared` with `result="clear"` and no hits; one `pending_review` with
      **two hits** - one disposed `false_positive` (with a note) and one still `open` - so the
      "cannot clear while a hit is open" guard is demonstrable and the Resolution Manager has rows.
      Both carry `list_as_of`, `reference`, `match_threshold=85` and `next_rescreen_on`.
- [ ] Risk signals: **three observations across two providers for the SAME party** (e.g.
      `rapidratings/fhr` 61 -> 48 -> 39 on three dates, plus one `dnb/ser_rating` 6) so `trend`,
      `previous_value`, `band` and the deterioration alert all render on a fresh DB. Assert the
      third row lands `deteriorated` + `elevated`/`critical`.
- [ ] Fraud alerts: **call `FraudAlert.scan(tenant, start, end, user=None)`** over the seeded
      window rather than hand-writing findings (the 6.14 posture - the alerts must prove the
      detector). To make R1 fire, give one existing employee party and one existing vendor party a
      shared `core.ContactMethod` value **only if neither already has one** - `get_or_create`, and
      skip silently if the tenant has no employee-role party.
- [ ] Policies: one **published** v1.0 (`code_of_conduct`, `requires_attestation=True`,
      `effective_from` set) whose `publish()` raises attestations for the tenant's active users,
      with one of them acknowledged and one left pending-and-overdue; plus one `draft`
      (`conflict_of_interest`).
- [ ] One `AuditSeal` sealed **last**, after every other seed write, so `verify()` returns OK on a
      fresh DB. Skip gracefully when the tenant has no `AuditLog` rows.
- [ ] Handle the `SMOKETEST` tenant gracefully (no vendor/employee parties -> skip, do not crash).
- [ ] Print the standard login instructions + the "superuser `admin` has no tenant" warning.

## Migration
- [ ] Latest on disk is **`0025_remove_budgetmapping_prc_bmap_tnt_active_idx_and_more.py`**.
      **A concurrent session is building 6.16 and takes `0026_*` (L43).**
      6.17 generates **AFTER 6.16's migration has landed** and takes **`0027_*`**.
      If 6.16 has not landed when the build reaches Integrate, agree the number with that session
      before running `makemigrations` - do not just take 0026.
- [ ] One migration for all seven tables **plus** the `ProcurementAlert.kind` `AlterField`.
      If 6.16 also touches `ProcurementAlert.kind`, coordinate - two `AlterField`s on the same
      column in sibling migrations is a merge conflict waiting to happen.
- [ ] `makemigrations procurement` -> `migrate` -> `seed_procurement` **twice** -> `manage.py check`.

---

## Verify (smoke as `admin_acme` / password `password`)
- [ ] `python manage.py makemigrations procurement` then `migrate` - clean.
- [ ] `python manage.py seed_procurement` **twice** - second run creates nothing and does not raise.
- [ ] `python manage.py check` - zero issues.
- [ ] Throwaway `temp/` script, deleted after: log in as `admin_acme`, hit **every** new
      `procurement:*` route (all ~54).
- [ ] **Assert CONTENT, not just status (L8/L41):** a mismatched context var returns 200 and renders
      a blank region. For each page assert the page title AND a seeded record's identifier is
      present (`SCR-00001`, `SRS-00002`, `FRD-…`, `PPL-00001`, `ASL-00001`), and assert that
      **no `{#` and no `{% comment` leaks** into the HTML.
- [ ] **Each valid filter value returns the RIGHT ROWS (L44)**, not merely a 200: e.g.
      `?band=critical` shows the critical signal and NOT the low one; `?status=pending_review` on
      screenings hides the cleared one; `?rule=self_approval` on fraud alerts shows only that rule;
      `?overdue=1` on attestations returns exactly the overdue row.
- [ ] Junk params on every list (`?status=nope&party=abc&party=99999999999999999999&page=999`) -
      200, never a 500, and an unrecognised enum **narrows nothing** rather than emptying the page.
- [ ] Page 2 renders on at least one paginated register.
- [ ] **Cross-tenant IDOR -> 404** on every detail/edit/delete/verb route, including
      `screeninghit_*` (which scopes through `screening__tenant`, not its own column).
- [ ] Every delete is POST-only (a GET must not delete) and really removes the row.
- [ ] Guard tests that must pass by hand before the review phase:
      `screening_clear` refused while an open hit exists · `screeninghit_dispose` refused without a
      note · `attestation_sign` by a DIFFERENT user refused · `policy_edit` refused on a published
      policy · `fraudalert_delete` refused on a terminal alert · `auditseal` has no edit/delete
      route at all · `AuditSeal.verify()` returns OK on a fresh seal and FAILS after a deliberate
      `AuditLog.objects.filter(pk=…).update(target="tampered")` in the temp script (**then roll it
      back**).
- [ ] `FraudAlert.scan()` run twice over the same window raises **zero** new alerts the second time
      and does not re-open a dismissed one.
- [ ] Sidebar shows **6.17 Live** with all five bullets, each landing on its own distinct page.

## Close-out (Module Creation Sequence phases 4-7)
- [ ] Phase 4 - the six reviewers **one after another**, findings appended to
      `.claude/tasks/review-procurement-6.17.md` after each: `code-reviewer` -> `explorer` ->
      `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`.
      Dedupe, sort Critical -> Important -> Minor, assign `C#`/`I#`/`M#`, commit the file.
- [ ] Phase 5 - one `code-fixer` agent burns the findings down in ID order, one commit per file.
- [ ] Phase 6 - test contract + `conftest.py` first, then one `test-writer` per file, in order:
      `apps/procurement/tests/test_riskcompliance_models.py` -> `_forms.py` -> `_views.py` ->
      `_security.py`. Every test function `test_riskcompliance_*`, every module helper
      `_riskcompliance_*`. Finish with the **full unfiltered** app suite green (never `-k`, L47).
- [ ] Phase 7 - update `.claude/skills/procurement/SKILL.md` (models, the 14 route segments, the
      template paths, the seeder rows, the `LIVE_LINKS["6.17"]` entry, the `METRIC_SCALES` and
      canonical-digest gotchas) and mark 6.17 complete in `README.md`. One commit each.
- [ ] One file per commit throughout, PowerShell `;` separators, **never `git push`**.

## Later passes / deferred (carried from research §6-§7 so nothing is lost)
- Live **ITA CSL / SAM.gov connector** and any commercial screening feed - needs an outbound-HTTP
  design with the CRM-webhooks SSRF guard, list caching and retention. `method="api_feed"` already
  reserves the row shape so no migration is needed later.
- **OFAC 50%-rule ownership analysis, PEP / adverse media, sanctioned-ownership graphs** - licensed data.
- **`FraudRule` config table + calibration/simulation** ("how many alerts would this threshold
  raise?") - SAP BIS's strongest idea and the natural 6.17 second pass. This pass ships tunable
  class constants rendered read-only next to the scan; do **not** ship an editable rule table with
  no scan wired to it.
- **Conflict-of-interest DECLARATION register** (evaluator/committee attestations with interest
  type, related party, mitigating control) - a second attestation kind with its own fields. Rule R1
  catches the undeclared case meanwhile. Strongest candidate for the second pass.
- **Vendor bank-detail-change monitoring** - **blocked on data**: no supplier bank record exists
  anywhere. Needs an AP-owned `VendorBankAccount` with change history - an `apps/accounting` build.
- **Fraud rules `po_escalation`** (successive `procurement.PurchaseOrderChange` rows raising value
  after approval, research 4.8) and **`round_amount`** (single document priced just under an
  `APPROVAL_TIERS` threshold, 4.7) - both cheap, both cut for scope. `round_amount` is additionally
  boundary-sensitive against 6.14's `split_purchase` and must ship with an explicit code comment
  naming the boundary.
- **Batch screening of the whole vendor master** (`screening_batch`) if the pass overruns.
- **Link/network analysis, ML anomaly scoring, entity-resolution fuzzy matching** - no graph/ML
  layer; the rules stay deterministic and no page ever says "AI".
- **Scheduled/automatic re-screening and score refresh** - no worker or scheduler exists
  (`accounting.ScheduledReport` is the config-without-worker precedent). The due boards + an
  operator POST are the honest equivalent.
- **Attestation reminder emails and e-signature** - no mail sender wired; `ProcurementAlert` substitutes.
- **DB-level append-only / WORM / SIEM export / a 10-year retention purge job** - infrastructure.
  The seal proves alteration; it does not prevent it, and the page says so.
- **Inherent-vs-residual risk questionnaires and tiering-driven review cadence** (Coupa,
  ProcessUnity) - a questionnaire engine; 6.6's `RfxEvent`/`RfxQuestion` is the reusable substrate.
- **Cyber-rating and ESG feeds** (BitSight / RiskRecon / EcoVadis) - already reserved as
  `provider` / `metric` values, so a later connector needs no migration.

## Parked for a sibling sub-module (do NOT pull into 6.17)
- **KPIs, scorecards, OTD/defect metrics, 360 feedback, PIPs, benchmarking, any "risk-adjusted
  score"** -> **6.16** (being built concurrently). Nothing about supplier *performance* is in scope.
- **Vendor onboarding, qualification tiers, the portal, the suspension/blacklist register** ->
  **6.4** (built) and **SCM 4.2**. 6.17 *raises* a block; it never owns blocking.
- **The internal 4-factor composite risk assessment + mitigation plan** -> **SCM 4.2
  `SupplierRiskAssessment`**. 6.17 links to `scm:riskassessment_list` and ships no second composite.
- **Recurring regulatory obligations, frameworks, licences, trade documents, ESG assessments** ->
  **SCM 4.12** (`ComplianceRequirement`/`ComplianceCheck`, `TradeLicense`,
  `SustainabilityAssessment`). A screening is one lookup at one moment with match children - it is
  **not** a cadence obligation. Say so in the module docstring and cross-link.
- **Duplicate-invoice detection, three-way-match variances, invoice disputes** -> **6.13** (built).
  Cite those rows on the fraud board; never re-detect them.
- **Maverick/off-contract spend, `split_purchase`, contract leakage, spend cubes** -> **6.14** (built).
- **Approval routing, DOA delegation, escalation policy** -> **6.3** (built); 6.17 only READS the
  signatures.
- **Policy repository search, full-text indexing, version-controlled document library** -> **6.19**
  Document & Knowledge Management. 6.17 owns the policy record, its versions and the sign-off
  ledger; 6.19 will index them.
- **Journal postings, credit notes, payment blocks** -> `apps.accounting` (L29). 6.17 posts nothing.
- **Stock/quarantine holds for non-compliant goods** -> inventory 5.14/5.15, SCM 4.9.

## Review notes
(filled in at the end)

---

## Procurement 6.16 - Supplier Performance & Evaluation (Module 6, `apps/procurement`) - plan from research-procurement-6.16.md  (2026-09-05)

NavERP.md lines 1101-1107, five bullets: KPI Definition & Setup - Scorecard Generation -
360-Degree Feedback Collection - Performance Improvement Plans (PIP) - Benchmarking & Trending.
App EXISTS (6.1-6.15 built) -> this pass EXTENDS it. No scaffold, no `settings.py`, no
`config/urls.py` edit.

### Frozen decisions - do NOT re-litigate during the build

- [ ] **Scope is exactly the research's 4 models**: `SupplierKpi` [SKP-], `SupplierKpiScore` (no
      prefix, `TenantOwned` child fact row), `SupplierFeedback` [SFB-],
      `SupplierImprovementPlan` [SIP-]. Bullet 5 (Benchmarking & Trending) ships as **computed
      boards, no table** - every figure it needs is already frozen on the score lines.
- [ ] **L36 - `scm.SupplierScorecard` is NOT re-declared.** It stays the period container.
      `SupplierKpiScore.scorecard` FKs it **by string** `"scm.SupplierScorecard"`, `CASCADE`,
      `related_name="procurement_kpi_scores"`. No second scorecard table, no second vendor table,
      no second alert table.
- [ ] **`manual_override` = option (a), deliberately.** `supplierevaluation_generate` writes the
      four `scm.SupplierScorecard` dimension columns for KPIs declaring a `maps_to_dimension`,
      sets `manual_override = True`, then calls the scorecard's own `recompute_overall()`.
      **This permanently hands that scorecard to 6.16**: `scm`'s `recompute_from_signals()`
      returns immediately on any row with `manual_override` set, so the two engines can never
      fight over the same row. This is documented behaviour, not a side effect - it must be
      stated in the model docstring, in the view docstring, in the confirm dialog on the button,
      and on the scorecard detail page itself.
- [ ] **Generate REFUSES on a `published` or `archived` scorecard** - `messages.error` +
      redirect back to the detail page; only `draft` may be generated onto.
- [ ] **Migration number is `0026`** (agreed with three concurrent peer sessions: 6.17 takes
      0027, 6.18 takes 0028, 6.19 takes 0029). Latest on disk is `0025_remove_budgetmapping_...`.
      `makemigrations procurement` must produce `0026_*` and **nothing else** - if it also wants
      to alter a table this pass did not touch, STOP and re-read (another session's model edit
      leaked in).
- [ ] **URL first segments are reserved with the peer sessions - stay inside this set:**
      `supplier-kpis/`, `supplier-evaluations/`, `supplier-feedback/`, `improvement-plans/`,
      `supplier-benchmarking/`. Every first path component is a **literal**; this app's standing
      guarantee is that no route has a converter in first position and 6.16 must not break it.
- [ ] **The four untracked `apps/procurement/tests/test_budgetcost_*.py` files belong to another
      session (L45) - never `git add` them.**
- [ ] One file per commit, PowerShell-safe (`;` never `&&`). Never `git push`.

### Spine verified this pass (grep, not the docs - L28)

- [ ] `core.Party` `apps/core/models/Party.py:5` - the supplier master. **Never a new vendor table.**
- [ ] `core.Tenant` `apps/core/models/Tenant.py:5` - every model gets a `tenant` FK.
- [ ] `scm.SupplierScorecard` `apps/scm/models/SupplierRelationshipManagement/SupplierScorecards.py:11`
      - `TenantNumbered` [SCR-], `party`/`period_start`/`period_end`/`status` draft|published|archived,
      four nullable 0-100 dimension columns, `overall_score`+`grade` (`editable=False`),
      `manual_override`, `signal_summary`, `recompute_overall()`, `recompute_from_signals()`.
      SCM routes exist: `scm:scorecard_list/create/detail/edit/delete/recompute/publish`.
- [ ] `scm.SupplierProfile` `.../SupplierProfiles.py:12` - `TIER_CHOICES` =
      `strategic|preferred|approved|transactional`, plus `tier` and `category`.
- [ ] `scm.SupplierRiskAssessment` `.../SupplierRiskAssessments.py:10` - `risk_index`, the second
      axis of the benchmark quadrant.
- [ ] `procurement.VendorSuspension` `apps/procurement/models/VendorManagement/VendorSuspensions.py:27`
      - the PIP escalation target (its `REASON_CHOICES` already carries `quality` / `delivery`).
- [ ] `procurement.ProcurementAlert` `apps/procurement/models/DashboardPortal/ProcurementAlerts.py:26`
      - `KIND_CHOICES` = deadline|approval|delivery|task|contract, `SEVERITY_CHOICES` =
      info|warning|critical. Band-crossing alerts reuse it (`kind="task"`, severity from the band)
      - **no new alert table.**
- [ ] Toolkit verified: `apps/core/crud.py` (`crud_list/create/detail/edit/delete`, pinned context
      `object_list`+`page_obj`+`q`, detail/edit object = `obj`, form = `form`+`is_edit`;
      `filters=` tuples are `(get_param, orm_lookup, is_int)`; `crud_create`/`crud_edit` already
      pass `request.FILES`), `apps/core/utils.write_audit_log`,
      `apps/core/decorators.tenant_admin_required`,
      `apps/procurement/{models/_base.py, forms/_common.py, views/_common.py}` (`TenantOwned`,
      `TenantNumbered`, `TenantUniqueMixin`, `_reject_foreign`, `ZERO`, `q2`).
- [ ] Names free (no collision anywhere in `apps/`): `SupplierKpi`, `SupplierKpiScore`,
      `SupplierFeedback`, `SupplierImprovementPlan`. Prefixes free: `SKP`, `SFB`, `SIP`
      (`PIP` is hrm's, `SCR` is scm's - use neither).

---

### Model 1 - `SupplierKpi` [SKP-] · `TenantNumbered` · `models/SupplierPerformanceEvaluation/SupplierKpis.py`

Serves **bullet 1 (KPI Definition & Setup)** and unlocks bullets 2 and 3. Each field is here
because a surveyed leader has it; the driver is named.

- [ ] Identity: `code` CharField(32) (driver: Ariba master-KPI identifiers for cross-scorecard
      roll-up), `name` CharField(160), `description` TextField(blank).
- [ ] `category` CharField(16, choices `CATEGORY_CHOICES`) =
      `delivery|quality|cost|service|compliance|esg|innovation|risk`, default `delivery`
      (drivers: Ivalua's 5 core dimensions + Kodiak ESG/innovation + Zycus balanced scorecard).
- [ ] `unit` CharField(10, choices `UNIT_CHOICES`) = `pct|days|count|ppm|money|score|ratio`,
      default `pct` (driver: Kodiak's per-KPI formulas - PPM and days are not percentages).
- [ ] `direction` CharField(16, choices `DIRECTION_CHOICES`) =
      `higher_is_better|lower_is_better`, default `higher_is_better` (driver: Kodiak ships an
      explicit direction column on all 15 KPIs - OTIF up, PPM down).
- [ ] `source` CharField(8, choices `SOURCE_CHOICES`) = `derived|survey|manual`, default `manual`
      (driver: **Ariba's three KPI data-source types**; HICX/LeanLinking hard-vs-soft split).
- [ ] `derived_metric` CharField(24, choices `DERIVED_METRIC_CHOICES`, blank) - a **closed**
      registry, one key per resolver that exists over verified as-built tables:
      `otd, otif, defect_rate, ncr_rate, rtv_rate, invoice_accuracy, dispute_rate, dispute_days,
      promise_adherence, backorder_rate, po_change_rate, price_competitiveness, quote_turnaround,
      suspension_incidents`. **Never add a key without a reviewed resolver** (the
      `scm.KpiTarget.metric` discipline, quoted in the docstring).
- [ ] `weight` PositiveSmallIntegerField(default 10, validators Min 1 / Max 100) - **the field
      that replaces the hard-coded `SupplierScorecard.WEIGHTS` dict** (drivers: Ivalua 40/20/15/
      15/10, LeanLinking 40/30/20/10 + pharma variant, Ariba per-scorecard overrides).
- [ ] `target_value` / `warning_threshold` / `critical_threshold` Decimal(12,4) null blank
      (drivers: Ivalua green/yellow/red, Kodiak OTIF >= 98% / PPM <= 250 / audit >= 90%).
- [ ] `scoring_method` CharField(8, choices `SCORING_CHOICES`) = `band|linear|direct`, default
      `band` (driver: Ariba pre-grading vs post-grading; Ivalua metric-score x weight).
- [ ] `maps_to_dimension` CharField(16, choices `DIMENSION_CHOICES`, blank) =
      `delivery|quality|price|responsiveness` (NavERP-specific bridge: which of the four existing
      `scm.SupplierScorecard` columns this KPI feeds. Blank = feeds none).
- [ ] `applies_to` CharField(8, choices `APPLIES_CHOICES`) = `all|tier`, default `all`, +
      `applies_to_tier` CharField(16, choices, blank) = `strategic|preferred|approved|transactional`
      (drivers: Jaggaer per-category rating models, State of Flux tier-based KPI setup).
      **Declare the four tier values as a LOCAL `TIER_CHOICES` constant with a comment naming
      `scm.SupplierProfile.TIER_CHOICES` as the source of truth** - do not import scm into a
      model module just to mirror four strings.
- [ ] `review_frequency` CharField(12, choices `FREQUENCY_CHOICES`) =
      `monthly|quarterly|semiannual|annual`, default `quarterly` (drivers: Ivalua/Kodiak cadence;
      the auto-scheduler is deferred - the field is stored, nothing schedules off it yet, and the
      help_text must say so).
- [ ] `industry_benchmark_value` Decimal(12,4) null blank - the **hand-entered** external
      reference. help_text must read "hand-entered reference figure - there is no external
      benchmark feed in this system" (honesty rule, the 6.14 "Assisted Capture" precedent).
- [ ] `owner` FK `settings.AUTH_USER_MODEL` SET_NULL null blank
      `related_name="procurement_supplier_kpis"` (driver: Kodiak/HICX "each KPI has an owner").
- [ ] `display_order` PositiveSmallIntegerField(default 100), `is_active` BooleanField(default
      True) (retire a KPI by deactivating it - never delete it out from under history),
      `notes` TextField(blank).
- [ ] **Meta:** `ordering = ["display_order", "code"]`; `unique_together = (("tenant", "code"),
      ("tenant", "number"))`; indexes `(tenant, is_active)`, `(tenant, category)`,
      `(tenant, source)` - names <= 30 chars, prefix `prc_skp_`.
- [ ] **`clean()`** (three rules, all from the research):
      1. band ordering by direction - port the rule from
         `apps/scm/models/SupplyChainAnalytics/KpiTargets.py`'s `clean()`: `higher_is_better` =>
         `target >= warning >= critical`; `lower_is_better` => `target <= warning <= critical`;
         compare only the values that are not None.
      2. `derived_metric` **required iff** `source == "derived"` and **must be blank otherwise**
         (the "conjunction that can never be true" rule).
      3. `applies_to_tier` **required iff** `applies_to == "tier"`, blank otherwise.
- [ ] **Methods:** `score_and_band(measured_value)` -> `(Decimal 0-100 | None, band)` applying
      `scoring_method` + `direction` + the three thresholds. The KPI owns its own scale so the
      generate action, the manual edit form and the tests all band by one rule.
      `@property band_css` is NOT on this model (bands live on the score row).
- [ ] **Form `SupplierKpiForm`** (`TenantUniqueMixin`, `TenantModelForm`): `Meta.fields` = code,
      name, description, category, unit, direction, source, derived_metric, weight, target_value,
      warning_threshold, critical_threshold, scoring_method, maps_to_dimension, applies_to,
      applies_to_tier, review_frequency, industry_benchmark_value, owner, display_order,
      is_active, notes. **EXCLUDED: `tenant` (set by `crud_create`), `number` (auto SKP-),
      `created_at`/`updated_at` (system timestamps, L22).** `owner` queryset narrowed to
      `User.objects.filter(tenant=tenant, is_active=True)`.

### Model 2 - `SupplierKpiScore` · `TenantOwned`, NO prefix · `models/SupplierPerformanceEvaluation/ScorecardKpiScores.py`

Serves **bullet 2 (Scorecard Generation)** - the L36 "extend the scm table by FK" move. A child
fact row, so `TenantOwned` not `TenantNumbered` (the `KpiSnapshot` / `InvoiceMatchVariance`
precedent - nobody would ever quote an `SKS-00001`).

- [ ] `scorecard` FK **`"scm.SupplierScorecard"`** CASCADE
      `related_name="procurement_kpi_scores"`; `kpi` FK `"procurement.SupplierKpi"` **PROTECT**
      `related_name="scores"` (deleting a KPI must never silently delete measured history -
      retire with `is_active=False`); `tenant` from `TenantOwned`.
- [ ] Measurement: `measured_value` Decimal(16,4) null blank; `score` Decimal(5,2) null blank
      validators `MinValueValidator(0)` / `MaxValueValidator(100)` (matches every 0-100 field in
      the codebase; stops a hand-entered value inflating the composite or overflowing a
      `width:<score>%` bar); `weight_applied` PositiveSmallIntegerField(default 0) - **frozen at
      generation** because Ariba allows per-scorecard weight overrides.
- [ ] `band` CharField(10, choices `BAND_CHOICES`) = `ok|warning|critical|unknown`, default
      `unknown`, plus
      `BAND_CSS = {"ok": "badge-green", "warning": "badge-amber", "critical": "badge-red",
      "unknown": "badge-muted"}` and `@property band_css` with a `badge-slate` fallback.
      **Colour names ONLY (L33) - `badge-success`/`-warning`/`-danger` do not exist in theme.css
      and render unstyled.**
- [ ] Frozen-at-time columns, all `editable=False` (a later retune or rename must not rewrite
      history - the `KpiSnapshot.target_value_at_time` precedent): `target_at_time` Decimal(12,4)
      null, `direction_at_time` CharField(16, blank), `source_at_time` CharField(8, blank),
      `unit_at_time` CharField(10, blank), `kpi_name` CharField(160, blank),
      `kpi_category` CharField(16, blank).
- [ ] Explainability: `breakdown` JSONField(default=dict, blank, editable=False) - the structured
      version of `signal_summary` (numerator/denominator/window/rows-considered)
      (drivers: LeanLinking "audit trail for rating decisions", HICX audit trails).
- [ ] `respondent_count` PositiveIntegerField(default 0, editable=False) - how many 360 responses
      were aggregated for a `survey` KPI; `comment` TextField(blank) (driver: Kodiak per-KPI
      commentary).
- [ ] `computed_at` DateTimeField(**`default=timezone.now`, NOT `auto_now_add`** - a re-run must
      re-stamp freshness, editable=False); `computed_by` FK AUTH_USER_MODEL SET_NULL null blank
      editable=False `related_name="procurement_kpi_scores_computed"`.
- [ ] **Meta:** `unique_together = ("tenant", "scorecard", "kpi")` - **this is what makes the
      generate action safe to press twice** (a re-run UPDATES, never stacks);
      `ordering = ["kpi_category", "kpi_name", "id"]` (the denormalised columns, so no JOIN on
      every list); indexes `(tenant, scorecard)`, `(tenant, band)`, `(tenant, kpi)`, prefix
      `prc_sks_`.
- [ ] **`clean()`**: `scorecard_id` and `kpi_id` must resolve to same-tenant rows - use **`_id`
      guards and an explicit queryset lookup, never a bare `self.scorecard.tenant_id`** (the
      `VendorSuspension.clean()` precedent, where the two-arg form raised
      `RelatedObjectDoesNotExist` and 500'd a live add page).
- [ ] `@property contribution` = `score * weight_applied` (None-safe) for the detail page's
      composite arithmetic table.
- [ ] **Form `SupplierKpiScoreEditForm`**: `Meta.fields = ("measured_value", "comment")` **only**.
      `save()` re-derives `score` and `band` through `self.instance.kpi.score_and_band(...)` and
      re-stamps `computed_at` + `breakdown = {"source": "manual entry", ...}` so a hand-typed
      value is banded by exactly the same rule as a derived one. **EXCLUDED: everything else** -
      `tenant`, `scorecard`, `kpi`, `weight_applied`, every `*_at_time`, `score`, `band`,
      `breakdown`, `respondent_count`, `computed_at`, `computed_by`.
- [ ] **TWO DOCUMENTED CRUD EXEMPTIONS - write them in the module docstring so a reviewer does
      not flag them as missing:**
      1. **No create form and no `supplierkpiscore_create` route.** Lines are system-written by
         `supplierevaluation_generate`; a hand-created line would be a measurement with no
         computation behind it (the `SpendReportSnapshot` / `CostForecast`-has-no-edit precedent).
      2. **Edit is limited to `measured_value` + `comment`, and only when
         `source_at_time == "manual"`** (Ariba's third KPI type). The **view** is the gate: any
         other row redirects to the detail page with `messages.error` - a disabled widget is UX,
         not an authorization boundary.
      Delete (POST-only) DOES exist so a retired KPI's stale line can be removed.

### Model 3 - `SupplierFeedback` [SFB-] · `TenantNumbered` · `models/SupplierPerformanceEvaluation/SupplierFeedback.py`

Serves **bullet 3 (360-Degree Feedback Collection)** and feeds bullet 2 through `source='survey'`
KPIs. One row = one respondent's rating of one supplier for one period, optionally against one KPI.

- [ ] FKs: `supplier` FK `"core.Party"` PROTECT `related_name="procurement_supplier_feedback"`;
      `scorecard` FK `"scm.SupplierScorecard"` SET_NULL null blank
      `related_name="procurement_feedback"` (ad-hoc feedback exists without a period document);
      `kpi` FK `"procurement.SupplierKpi"` SET_NULL null blank `related_name="feedback"` (set =
      this response feeds that survey KPI; blank = general commentary);
      `respondent` + `requested_by` FK AUTH_USER_MODEL SET_NULL null blank
      (`related_name="procurement_feedback_given"` / `"..._requested"`).
- [ ] `period_start` / `period_end` DateField.
- [ ] `respondent_kind` CharField(16, choices) = `internal|supplier_self`, default `internal`
      (driver: **SupplyHive Hive360** - one CharField buys the whole perception-gap board) +
      `respondent_name` CharField(160, blank) for a `supplier_self` response that has no internal
      user account (without it the row is anonymous).
- [ ] `respondent_function` CharField(16, choices) =
      `procurement|quality|operations|finance|engineering|logistics|other`, default `procurement`
      (drivers: Kodiak's RACI set, LeanLinking's three functions).
- [ ] `rating` PositiveSmallIntegerField(choices `RATING_CHOICES`, null blank) = 1 Poor / 2 Below
      Expectations / 3 Meets Expectations / 4 Above Expectations / 5 Excellent (driver: Ariba's
      labelled qualitative anchors) + `score_value()` -> 0/25/50/75/100 for the 0-100 KPI scale.
- [ ] `importance` PositiveSmallIntegerField(default 5, validators Min 0 / Max 10) - **Ariba's
      per-question Importance**; it weights the survey aggregate so a category manager's rating
      can count more than a casual requester's.
- [ ] `status` CharField(12, choices) = `requested|submitted|declined|expired`, default
      `requested` (driver: GEP "issuing and tracking scorecards for completion") + `due_date`
      DateField null blank.
- [ ] System stamps, all `editable=False`: `requested_at` DateTimeField(default=timezone.now),
      `submitted_at` DateTimeField(null blank). `comment` TextField(blank) (drivers: SupplyHive
      theme analysis, Kodiak commentary).
- [ ] **Meta:** `ordering = ["-period_end", "-id"]`; `unique_together = ("tenant", "number")`;
      indexes `(tenant, supplier)`, `(tenant, status)`, `(tenant, scorecard)`, prefix `prc_sfb_`.
- [ ] **`clean()`** (five rules):
      1. **One response per `(supplier, scorecard, kpi, respondent)`** enforced with an explicit
         `.exclude(pk=self.pk).filter(...)` existence check that matches NULLs by id - **NOT
         `unique_together`**, because `scorecard` and `kpi` are nullable and SQL NULLs compare
         distinct, so a naive constraint lets duplicates straight through (the `KpiSnapshot`
         blank-vs-NULL trap).
      2. `kpi`, when set, must have `source == "survey"` - a derived KPI is not a survey question.
      3. `period_end >= period_start`.
      4. `rating` required when `status == "submitted"`.
      5. Same-tenant `_id` guards on `supplier`, `scorecard`, `kpi`; and
         `respondent_kind == "supplier_self"` => `respondent` (an internal user) must be blank and
         `respondent_name` is required.
- [ ] **Form `SupplierFeedbackForm`**: `Meta.fields` = supplier, scorecard, kpi, period_start,
      period_end, respondent_kind, respondent_function, respondent, respondent_name, rating,
      importance, due_date, comment. **EXCLUDED: `tenant`, `number` (auto SFB-), `status`
      (workflow-controlled by the submit/decline/expire verbs), `requested_by`, `requested_at`,
      `submitted_at` (system stamps, L22).** Querysets narrowed in `__init__`: `supplier` ->
      `Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).distinct()`
      (the established procurement convention); `scorecard` -> tenant scorecards; `kpi` ->
      `SupplierKpi.objects.filter(tenant=tenant, is_active=True, source="survey")`; `respondent`
      -> tenant users. `_reject_foreign` on all four FKs.

### Model 4 - `SupplierImprovementPlan` [SIP-] · `TenantNumbered` · `models/SupplierPerformanceEvaluation/SupplierImprovementPlans.py`

Serves **bullet 4 (PIP)**. Shaped on the verified in-repo `hrm.PerformanceImprovementPlan` plus
Kodiak's CAPA-register columns. **Plan grain only this pass** - design it to accept a
`SupplierImprovementAction` child later without reshaping (do NOT cram a fake action list into a
TextField).

- [ ] `title` CharField(200); `supplier` FK `"core.Party"` PROTECT
      `related_name="procurement_improvement_plans"`; `scorecard` FK `"scm.SupplierScorecard"`
      SET_NULL null blank `related_name="procurement_improvement_plans"` (the triggering evidence
      - Jaggaer/Ivalua "performance dips -> plan"); `kpi` FK `"procurement.SupplierKpi"` SET_NULL
      null blank `related_name="improvement_plans"` (the failing KPI).
- [ ] The CAPA columns, verbatim in structure from Kodiak's register: `finding` TextField (what
      was observed), `root_cause` TextField(blank), `corrective_actions` TextField(blank),
      `support_provided` TextField(blank), `success_criteria` TextField(blank).
- [ ] `severity` CharField(8, choices) = `minor|major|critical`, default `major`.
- [ ] Dates: `start_date`, `target_close_date` (both required), `next_review_date` null blank
      (stands in for the deferred check-in child), `extended_close_date` null blank (driver:
      HRM PIP `extended_end_date`, EcoVadis 12-month CAP validity), `actual_close_date` null
      blank **editable=False**.
- [ ] `status` CharField(12, choices) = `draft|active|monitoring|closed|cancelled`, default
      `draft`; `outcome` CharField(12, choices, blank) =
      `successful|extended|failed|escalated` (driver: HRM's OUTCOME_CHOICES shape).
- [ ] Owners: `owner` FK AUTH_USER_MODEL SET_NULL null blank
      `related_name="procurement_improvement_plans"` (internal);
      `supplier_owner_name` CharField(160, blank) + `supplier_owner_email` EmailField(blank)
      (drivers: Kodiak/Ivalua run plans WITH the supplier).
- [ ] `escalated_suspension` FK `"procurement.VendorSuspension"` SET_NULL null blank
      `related_name="improvement_plans"` - **closes the loop to the existing block register
      instead of inventing a second blocking mechanism** (drivers: LeanLinking 3-quarter misses,
      MasterControl AVL update).
- [ ] Evidence, mirroring the verified in-app `ReceiptDiscrepancy` precedent exactly:
      `evidence` FileField(`upload_to="procurement/improvement_evidence/%Y/%m/"`, null blank) +
      `evidence_url` URLField(blank, "Link to evidence held elsewhere") +
      `@property has_evidence`. Form `clean_evidence()` validates extension against
      `apps.core.forms.ALLOWED_DOC_EXTENSIONS` and size against `MAX_UPLOAD_BYTES`.
      **Not a `core.Document` FK** - the FileField precedent is in this app already.
- [ ] System stamps, all `editable=False`: `acknowledged_at` / `acknowledged_by`,
      `verified_at` / `verified_by` (FKs SET_NULL null blank, `related_name="procurement_pip_
      acknowledged"` / `"procurement_pip_verified"`), `closure_note` TextField(blank).
- [ ] **Meta:** `ordering = ["-start_date", "-id"]`; `unique_together = ("tenant", "number")`;
      indexes `(tenant, status)`, `(tenant, supplier)`, `(tenant, severity)`, prefix `prc_sip_`.
- [ ] **`clean()`**: `target_close_date >= start_date`; `extended_close_date > target_close_date`
      when set; `outcome` required when `status == "closed"` and must be blank otherwise;
      `escalated_suspension`, when set, must belong to the SAME supplier and the same tenant;
      same-tenant `_id` guards on supplier/scorecard/kpi/escalated_suspension.
- [ ] **Form `SupplierImprovementPlanForm`**: `Meta.fields` = title, supplier, scorecard, kpi,
      severity, finding, root_cause, corrective_actions, support_provided, success_criteria,
      start_date, target_close_date, next_review_date, extended_close_date, owner,
      supplier_owner_name, supplier_owner_email, escalated_suspension, evidence, evidence_url.
      **EXCLUDED: `tenant`, `number` (auto SIP-), `status` and `outcome` (workflow-controlled by
      the activate/monitor/close/cancel verbs), `actual_close_date`, `acknowledged_at/_by`,
      `verified_at/_by`, `closure_note` (system stamps, L22).** FK querysets narrowed to the
      tenant (supplier via the `roles__role__in=("supplier","vendor")` convention);
      `_reject_foreign` on all five FKs.

### Compute module - `apps/procurement/performance.py` (NEW, flat at the app root)

The `analytics.py` precedent (6.14): single-purpose compute lives flat, not in a views module, so
the views stay thin and every figure is unit-testable. **Do not edit `analytics.py` - it is
6.14's.** Owned by Step 3 below.

- [ ] `applicable_kpis(tenant, party)` -> active KPIs where `applies_to="all"` OR
      (`applies_to="tier"` AND the tier matches that party's `scm.SupplierProfile.tier`).
      A party with no profile gets only the `all` KPIs.
- [ ] `DERIVED_RESOLVERS` - a dict `metric key -> callable(tenant, party, start, end)` returning
      `(measured_value | None, breakdown dict)`. Fourteen keys, each reading only
      grep-verified as-built tables: `otd`/`otif`/`defect_rate` (scm GRN + GRN lines vs PO
      `expected_date` and `PurchaseOrderLine.quantity`), `ncr_rate`/`rtv_rate` (6.12
      `ReceiptDiscrepancy` / `ReturnToVendor`), `invoice_accuracy`/`dispute_rate`/`dispute_days`
      (6.13 `InvoiceMatchVariance` / `SupplierInvoice` / `InvoiceDispute`),
      `promise_adherence`/`backorder_rate` (6.11 `DeliverySchedule` / `Backorder`),
      `po_change_rate` (6.10 `PurchaseOrderChange`), `price_competitiveness`/`quote_turnaround`
      (scm `RFQQuote` / `RFQ`), `suspension_incidents` (6.4 `VendorSuspension`).
      **A metric with no data in the period returns `(None, {...})` - never a phantom zero**
      (the `recompute_from_signals()` rule).
- [ ] `survey_aggregate(tenant, party, kpi, start, end)` -> `(score 0-100 | None, respondent_count,
      breakdown)` - the **importance-weighted** mean of `SupplierFeedback.score_value()` over
      `status="submitted"`, `respondent_kind="internal"` rows for that KPI and window.
- [ ] `generate_scorecard_lines(scorecard, user)` -> a result dict
      `{"written": n, "skipped": n, "dimensions": {...}, "alerts": n}`:
      resolve the KPI set -> compute each (derived / survey / leave a `manual` line's existing
      `measured_value` alone) -> `kpi.score_and_band(...)` -> `update_or_create` one line per KPI
      on `(tenant, scorecard, kpi)` freezing weight/target/direction/source/unit/name/category ->
      fill the four `scm.SupplierScorecard` dimension columns for KPIs with a `maps_to_dimension`
      (weighted mean where several map to one column) -> **`manual_override = True`** ->
      `scorecard.recompute_overall()` -> raise a `ProcurementAlert` per NEW critical band crossing
      (`kind="task"`, `severity="critical"`, internal `link_url` only).
      **Refuses (returns a refusal, no writes) when `scorecard.status != "draft"`.**
      Wrapped in `transaction.atomic`.
- [ ] Board helpers: `trend_series(tenant, party, kpi=None)`, `benchmark_rows(tenant, period_end,
      tier=None, category=None)`, `perception_gap_rows(tenant, party, start, end)`.
      `ROW_CAP = 500` on every board query (the 6.15 precedent) so a big workspace cannot render
      an unbounded page.
- [ ] **Import discipline:** import the 6.16 models from their **entity modules**
      (`from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import
      SupplierKpi`), not from `apps.procurement.models`, so this module imports cleanly BEFORE
      the Integrate phase adds the re-export block. Cross-app models (`scm`, `core`) come from
      their package roots. Sibling-app reads happen INSIDE the functions where a cycle is
      possible (the `CostForecasts.py` precedent).

### Routes - namespace `procurement`, ALL first segments literal and reserved

- [ ] `urls/SupplierPerformanceEvaluation/SupplierKpis.py`: `supplier-kpis/` ->
      `supplierkpi_list`; `supplier-kpis/add/` -> `supplierkpi_create`;
      `supplier-kpis/<int:pk>/` -> `supplierkpi_detail`; `.../edit/` -> `supplierkpi_edit`;
      `.../delete/` -> `supplierkpi_delete` (POST-only).
- [ ] `urls/SupplierPerformanceEvaluation/ScorecardKpiScores.py` (**literal `scores/` declared
      BEFORE `<int:pk>/`**): `supplier-evaluations/` -> `supplierevaluation_list`;
      `supplier-evaluations/scores/` -> `supplierkpiscore_list`;
      `supplier-evaluations/scores/<int:pk>/` -> `supplierkpiscore_detail`;
      `.../scores/<int:pk>/edit/` -> `supplierkpiscore_edit`;
      `.../scores/<int:pk>/delete/` -> `supplierkpiscore_delete` (POST-only);
      `supplier-evaluations/<int:pk>/` -> `supplierevaluation_detail`;
      `supplier-evaluations/<int:pk>/generate/` -> `supplierevaluation_generate`
      (POST-only + `@tenant_admin_required`).
- [ ] `urls/SupplierPerformanceEvaluation/SupplierFeedback.py`: `supplier-feedback/` ->
      `supplierfeedback_list`; `.../add/` -> `supplierfeedback_create`; `.../<int:pk>/` ->
      `supplierfeedback_detail`; `.../edit/` -> `supplierfeedback_edit`; `.../submit/` ->
      `supplierfeedback_submit` (POST); `.../decline/` -> `supplierfeedback_decline` (POST);
      `.../expire/` -> `supplierfeedback_expire` (POST - this is what makes the `expired` choice
      reachable; no dead choices); `.../delete/` -> `supplierfeedback_delete` (POST).
- [ ] `urls/SupplierPerformanceEvaluation/SupplierImprovementPlans.py`: `improvement-plans/` ->
      `improvementplan_list`; `.../add/` -> `improvementplan_create`; `.../<int:pk>/` ->
      `improvementplan_detail`; `.../edit/` -> `improvementplan_edit`; `.../activate/`,
      `.../monitor/`, `.../acknowledge/`, `.../close/`, `.../cancel/` -> the five POST verbs
      (so every `status` and `outcome` value is reachable); `.../delete/` -> POST-only.
      `close` is `@tenant_admin_required`.
- [ ] `urls/SupplierPerformanceEvaluation/PerformanceBoards.py`: `supplier-benchmarking/` ->
      `supplier_benchmark_board`; `supplier-benchmarking/trend/` -> `supplier_trend_board`;
      `supplier-benchmarking/perception-gap/` -> `supplier_perception_gap`. No converters here.
- [ ] **No procurement scorecard CREATE route.** The evaluation register's "New period" button
      links out to `scm:scorecard_create` (L36 - 6.16 never declares a second scorecard form).

---

### Step 1 - Contract (freeze it before any code)

- [ ] `.claude/tasks/contract-procurement-6.16.md`: every model field + every CHOICES value from
      the four blocks above; each form's `Meta.fields` + its exclusion list; all 30-ish url names;
      the four template folder slugs; and - **the field that decides whether the build works -
      EVERY view context key.** Pin at minimum:
      list pages -> `object_list`, `page_obj`, `q` + each filter's `*_choices` and FK queryset
      (`category_choices`, `source_choices`, `band_choices`, `status_choices`, `severity_choices`,
      `tier_choices`, `function_choices`, `kind_choices`, `kpis`, `suppliers`, `scorecards`,
      `stats`); detail/edit object -> `obj`; form pages -> `form`, `is_edit`;
      evaluation detail -> `obj`, `lines`, `composite`, `dimension_map`, `can_generate`,
      `refusal_reason`, `plans`, `feedback_rows`;
      boards -> `rows`, `periods`, `series`, `cohort`, `gap_rows`, `selected_supplier`,
      `selected_period`, `row_cap`, `truncated`.
      **An unpinned name is a silently blank region or a `NoReverseMatch` (L7/L8).**
- [ ] Commit the contract file on its own.

### Step 2 - Entity 1: `SupplierKpi` (build it FIRST - the other three FK it)

- [ ] `apps/procurement/models/SupplierPerformanceEvaluation/__init__.py` (empty; still its own
      commit) - the four package folders are created by their first file.
- [ ] `models/SupplierPerformanceEvaluation/SupplierKpis.py` - `from apps.procurement.models._base
      import *`, absolute imports only.
- [ ] `forms/SupplierPerformanceEvaluation/SupplierKpis.py` (+ that package's `__init__.py`).
- [ ] `views/SupplierPerformanceEvaluation/SupplierKpis.py` - `@login_required`, every queryset
      `filter(tenant=request.tenant)`, `crud_list` with
      `search_fields=("code", "name", "description", "notes")` and
      `filters=(("category","category",False), ("source","source",False),
      ("direction","direction",False), ("applies_to","applies_to",False),
      ("owner","owner_id",True), ("is_active","is_active",False))`; `crud_detail` /
      `crud_create` / `crud_edit`; `crud_delete` under `@require_POST`. During the build import
      the model from its **entity module**, not from `apps.procurement.models` (the sub-package
      is not wired until Step 7 - the `BudgetMappings.py` comment says exactly why).
- [ ] `urls/SupplierPerformanceEvaluation/SupplierKpis.py` (+ that package's `__init__.py`).
- [ ] `templates/procurement/performance/kpi/list.html` - filter bar reflecting `request.GET`
      (string filters `{% if request.GET.x == value %}`, the owner pk filter with
      `|stringformat:"d"`), Actions column (view / edit / delete-POST + `confirm()` +
      `{% csrf_token %}`), `has_previous`/`has_next`-guarded pagination (L9), empty state,
      weight + direction + band-threshold columns, `badge-green/-muted` for active/inactive.
- [ ] `templates/procurement/performance/kpi/detail.html` - thresholds panel with the direction
      arrow, the derived-metric or survey source stated in words, the
      `industry_benchmark_value` labelled "hand-entered", scores-using-this-KPI list, Actions
      sidebar (Edit / Delete POST / Back).
- [ ] `templates/procurement/performance/kpi/form.html` - shared create+edit, `is_edit` title
      switch, band-ordering help text.
- [ ] One commit per file (7 commits).

### Step 3 - Entity 2: `SupplierKpiScore` + `performance.py` + the evaluation register

- [ ] `models/SupplierPerformanceEvaluation/ScorecardKpiScores.py` (model + `BAND_CSS` + the two
      documented CRUD exemptions in the docstring).
- [ ] `apps/procurement/performance.py` - the compute module specified above.
- [ ] `forms/SupplierPerformanceEvaluation/ScorecardKpiScores.py` - the two-field manual edit form.
- [ ] `views/SupplierPerformanceEvaluation/ScorecardKpiScores.py`:
      `supplierevaluation_list` (`crud_list` over
      `SupplierScorecard.objects.filter(tenant=request.tenant)`, search on `number` +
      `party__name`, filters supplier / status / period-year, annotate the 6.16 line count);
      `supplierevaluation_detail` (lines ordered by category, the composite arithmetic table, the
      four mapped dimensions, `can_generate` + `refusal_reason`, links to the PIPs and feedback
      for that period, a link out to `scm:scorecard_detail`);
      `supplierevaluation_generate` (`@require_POST` + `@tenant_admin_required`, calls
      `generate_scorecard_lines`, **hand-rolled save path so it must call `write_audit_log`
      itself**, `messages.success` with the counts / `messages.error` on refusal);
      `supplierkpiscore_list` (flat register: search on `kpi_name`, filters band / source /
      kpi / scorecard); `supplierkpiscore_detail` (the `breakdown` JSON rendered as a table);
      `supplierkpiscore_edit` (**redirect + `messages.error` when
      `source_at_time != "manual"`**); `supplierkpiscore_delete` (POST-only).
- [ ] `urls/SupplierPerformanceEvaluation/ScorecardKpiScores.py` - literal `scores/` before
      `<int:pk>/`.
- [ ] `templates/procurement/performance/evaluation/list.html` (register + "New period" ->
      `scm:scorecard_create`), `.../evaluation/detail.html` (**the generate button's confirm text
      must say that generating takes this scorecard over from SCM's signal engine**; the page
      states it again as a note when `manual_override` is set).
- [ ] `templates/procurement/performance/kpiscore/{list,detail,form}.html` - the list's Actions
      column shows Edit **only** on `source_at_time == "manual"` rows (the conditional-actions
      rule), Delete POST on all; bands via `obj.band_css`.
- [ ] One commit per file (10 commits).

### Step 4 - Entity 3: `SupplierFeedback`

- [ ] `models/.../SupplierFeedback.py`, `forms/.../SupplierFeedback.py`,
      `views/.../SupplierFeedback.py`, `urls/.../SupplierFeedback.py`.
- [ ] List filters: supplier (int), status, respondent_kind, respondent_function, kpi (int),
      scorecard (int); search on `number`, `supplier__name`, `respondent_name`, `comment`.
      Stats strip: requested / submitted / declined / overdue.
- [ ] The three POST verbs are hand-rolled save paths -> each calls `write_audit_log` itself;
      `submit` requires a `rating` and stamps `submitted_at`.
- [ ] `templates/procurement/performance/feedback/{list,detail,form}.html` - rating rendered with
      its label (`get_rating_display`) and a `badge-green/-amber/-red` scale, importance shown,
      `supplier_self` rows visibly marked (`badge-info`).
- [ ] One commit per file (7 commits).

### Step 5 - Entity 4: `SupplierImprovementPlan`

- [ ] `models/.../SupplierImprovementPlans.py`, `forms/.../SupplierImprovementPlans.py`
      (+ `clean_evidence()`), `views/.../SupplierImprovementPlans.py`,
      `urls/.../SupplierImprovementPlans.py`.
- [ ] List filters: supplier (int), status, severity, outcome, owner (int), kpi (int); search on
      `number`, `title`, `finding`, `supplier__name`. Stats strip: active / monitoring / overdue
      / closed.
- [ ] Five POST verbs (activate / monitor / acknowledge / close / cancel) - each guards the legal
      source status, stamps its own system columns, calls `write_audit_log`; `close` takes
      `outcome` + `closure_note` from the POST and is `@tenant_admin_required`.
- [ ] `templates/procurement/performance/improvementplan/{list,detail,form}.html` - the form
      carries **`enctype="multipart/form-data"`** (evidence upload) and shows the allowed
      extensions + max MB; the detail page shows the CAPA columns, the timeline of stamps, the
      escalation link to the suspension, and the Actions sidebar with the verbs valid for the
      current status only.
- [ ] One commit per file (7 commits).

### Step 6 - Boards for bullet 5 (NO models)

- [ ] `views/SupplierPerformanceEvaluation/PerformanceBoards.py` + the matching `urls/` module.
- [ ] `templates/procurement/performance/benchmark_board.html` - one period, every supplier
      ranked by composite, cohort average + percentile, filters tier / category / period_end,
      plus the performance x risk quadrant reading `scm.SupplierRiskAssessment.risk_index`
      (drivers: Ariba comparative view, LeanLinking cross-base comparability, SupplyHive segments).
- [ ] `templates/procurement/performance/trend_board.html` - one supplier (`?supplier=<pk>`):
      composite and per-KPI series across periods with period-over-period deltas and
      flag-vs-target (driver: Kodiak monthly + trailing-12).
- [ ] `templates/procurement/performance/perception_gap.html` - internal average vs
      `respondent_kind="supplier_self"` average per KPI, with the delta (driver: SupplyHive
      Hive360).
- [ ] All three are **standalone pages at the sub-module root** (no entity folder - the
      Template-Folder rule 6 case), every query tenant-scoped and `ROW_CAP`-bounded, every board
      states plainly that benchmarks are **internal cohort only** - there is no external
      industry feed.
- [ ] One commit per file (5 commits).

### Step 7 - Integrate (SINGLE WRITER, the only DB writer - surgical Edits only, never a rewrite)

- [ ] **Verify every expected file from Steps 2-6 actually landed** before wiring anything.
- [ ] `models/__init__.py` - append the re-export block: `SupplierKpi`, `SupplierKpiScore`,
      `SupplierFeedback`, `SupplierImprovementPlan` imported **from the entity MODULES**
      (the 6.13/6.14/6.15 comment pattern), plus the four names appended to `__all__`.
- [ ] `forms/__init__.py` - append `SupplierKpiForm`, `SupplierKpiScoreEditForm`,
      `SupplierFeedbackForm`, `SupplierImprovementPlanForm` (+ `__all__`).
- [ ] `views/__init__.py` - append **every** view function name (all ~30). A view that is not
      re-exported is an `AttributeError` at URLconf import - this is the single most commonly
      forgotten step in this repo.
- [ ] `urls/__init__.py` - import the five 6.16 url modules and append them **LAST** in
      `urlpatterns` (the 6.13/6.14/6.15 belt-and-braces precedent), and extend the module
      docstring's first-segment inventory with `supplier-kpis/`, `supplier-evaluations/`,
      `supplier-feedback/`, `improvement-plans/`, `supplier-benchmarking/`.
- [ ] `apps/procurement/admin.py` - register the four models (list_display / list_filter /
      search_fields), following the existing per-sub-module block style.
- [ ] `apps/core/navigation.py` - **exactly ONE new key**, `LIVE_LINKS["6.16"]`, placed after
      `"6.15"`, with the five NavERP.md bullet names **verbatim**:
      `"KPI Definition & Setup" -> "procurement:supplierkpi_list"`,
      `"Scorecard Generation" -> "procurement:supplierevaluation_list"`,
      `"360-Degree Feedback Collection" -> "procurement:supplierfeedback_list"`,
      `"Performance Improvement Plans (PIP)" -> "procurement:improvementplan_list"`,
      `"Benchmarking & Trending" -> "procurement:supplier_benchmark_board"`.
      All five point at STAFF-facing management pages (L32). **Touch no other key** - peer
      sessions are editing 6.17/6.18/6.19 in this same file.
- [ ] `management/commands/seed_procurement.py` - add `_seed_supplier_performance(self, tenant)`
      and its dispatch line **immediately after `self._seed_budget_cost(tenant)`** in `handle()`.
      Idempotent: per-tenant `SupplierKpi.objects.filter(tenant=tenant).exists()` guard,
      `get_or_create` / number-existence checks throughout, **never `--flush`**. It must:
      reuse the existing seeded suppliers
      (`Party.objects.filter(tenant=tenant, roles__role__in=("supplier","vendor"))`) and skip
      gracefully when there are none (the SMOKETEST-tenant case `_seed_budget_cost` already
      handles); create ~6 KPIs spanning all three `source` values and at least two
      `maps_to_dimension` values; create ONE **`draft`** `scm.SupplierScorecard` per demo
      supplier for a distinct prior period **(seed_scm's own two scorecards are left alone -
      they are `published`, and generate correctly refuses those)**; run
      `generate_scorecard_lines` on the draft ones so real banded lines exist; create ~4
      `SupplierFeedback` rows including one `supplier_self` (so the perception-gap board has
      data) and one `requested`; create 2 PIPs (one `active`, one `closed` with an outcome).
      Also add the four models to the `--flush` block, children first.
- [ ] `python manage.py makemigrations procurement` -> **must be `0026_*` and nothing else.**
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_procurement` **twice** - the second run must print the
      "already present, skipping" line and create zero rows.
- [ ] `python manage.py check` - clean.
- [ ] One commit per file, explicit paths (models/forms/views/urls `__init__.py` x4, admin.py,
      navigation.py, seed_procurement.py, the migration = 8 commits).

### Step 8 - Verify / smoke (the gate before the review phase)

- [ ] Throwaway script under `temp/`, logged in as **`admin_acme` / `password`**:
      GET every new url (list, detail, form, all three boards) -> 200; every POST verb ->
      302 + the intended state change.
- [ ] **Assert CONTENT, not just status (L8)** - a mismatched context var returns 200 and renders
      blank: page titles, a seeded KPI code, a seeded SFB-/SIP- number, a banded score line, the
      cohort table's supplier name, the perception-gap delta.
- [ ] No `{#` or `{% comment` leaks in any rendered page; no `badge-success/-warning/-danger`
      anywhere in the new templates (grep the templates, L33).
- [ ] Junk-param sweep on every list (`?status=nope`, `?supplier=abc`, `?supplier=0`,
      `?supplier=999999999999999999999`, `?page=99`) -> 200 with the register still populated,
      never a 500 and never a silently emptied page.
- [ ] Page 2 renders where seeded rows allow.
- [ ] Cross-tenant IDOR: fetch a `beta`-tenant pk as `admin_acme` on every detail/edit/delete/
      verb route -> **404**.
- [ ] Generate refusal proven: POST generate on a `published` scorecard -> redirect +
      error message, and **zero** `SupplierKpiScore` rows written.
- [ ] Generate idempotence proven: POST generate twice on a draft scorecard -> the same line
      count both times (the `unique_together` re-run rule), `computed_at` re-stamped.
- [ ] `manual_override` proven: after generate, the scorecard has `manual_override=True` and a
      subsequent `recompute_from_signals()` leaves the dimensions unchanged.
- [ ] Sidebar: all five `6.16` bullets render **Live**.
- [ ] Delete the `temp/` script before committing (never commit it).

### Step 9 - Close-out

- [ ] Phase 4 - the six reviewers **one after another**, appending to
      `.claude/tasks/review-procurement-6.16.md` after each: `code-reviewer` -> `explorer` ->
      `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`.
      Dedupe, sort Critical -> Important -> Minor, assign IDs, commit the file.
- [ ] Phase 5 - one `code-fixer` agent burns the findings down in ID order, one commit per file;
      confirm nothing is left `[ ] open` and `manage.py check` is clean.
- [ ] Phase 6 - tests, serial: contract + `conftest.py` first, then
      `test_supplierperf_models.py` -> `test_supplierperf_forms.py` ->
      `test_supplierperf_views.py` -> `test_supplierperf_security.py`, every function named
      `test_supplierperf_*` and every module helper `_supplierperf_*`. Finish with ONE **full,
      unfiltered** `apps/procurement` suite run, green (never `-k` filtered, L47).
- [ ] Phase 7 - update `.claude/skills/procurement/SKILL.md` (models, the ~30 routes, the
      `performance/` template folders, the seeder rows, the `LIVE_LINKS["6.16"]` block, and the
      `manual_override` hand-over gotcha), and mark 6.16 complete in `README.md`. One commit each.
- [ ] Fill in the Review notes block below.

### Later passes / deferred (carried from the research - nothing lost)

- **`SupplierImprovementAction` child** - the multi-row CAPA register (per-action owner, due
  date, status, evidence, verification date). Kodiak/MasterControl/ComplianceQuest all have it;
  **this is the first thing the next pass should add**, which is why the plan model must accept a
  child without reshaping.
- **Named scorecard template / KPI-set model** (Ariba's Master document) - this pass selects the
  set via `applies_to_tier` + `is_active`.
- **PIP check-in child** (the `hrm.Pipcheckin` analogue) - `next_review_date` covers this pass.
- **Automated cadence scheduling** off `review_frequency` - needs a scheduler; none in this repo.
- **Survey distribution, reminders and escalation e-mails** - integration/later; the request
  lifecycle (`status`, `due_date`, `requested_at`) is modelled now so nothing reshapes when mail
  lands.
- **Supplier-facing self-review UI and score sharing** - needs the 6.4 `VendorPortalAccess`
  portal surface; the data model (`respondent_kind="supplier_self"`) is ready today.
- **Rule-engine auto-triggering of PIPs and standing band-crossing detectors** - this pass ships
  a "create PIP from this scorecard" link and alerts raised DURING generate only.
- **External industry benchmarks** (EcoVadis, Prewave, D&B, Coupa pooled feedback) - **not
  buildable against the as-built spine**; `industry_benchmark_value` is the hand-entered stand-in
  and every board says "internal cohort only".
- **NLP sentiment/theme extraction and AI-drafted plans** (SupplyHive, Ivalua IVA) - AI/later.
- **Bonus/penalty schemes tied to scores** (Jaggaer) - needs a 6.8 contract + accounting hook.
- **8D / PPAP / APQP methodology templates** - regulated-manufacturing niche.
- **Derived audit-score / CAPA-closure / certification-currency / ESG KPIs** - the source classes
  (`scm.QualityAudit`, `scm.CapaAction`, `scm.TradeLicense`, `scm.SustainabilityAssessment`)
  exist but their FIELD SHAPES were not verified; ship them as `manual`/`survey` KPIs and promote
  to `derived` only after a fresh grep (L28).
- **Cost-variance-vs-should-cost, expedite-cost, innovation throughput, contracted-lead-time
  adherence, supplier credit score** - no source table exists anywhere; `manual` only.

### Parked for a sibling sub-module (do NOT pull into 6.16)

- Supplier onboarding, qualification, tier/segment maintenance, the suspension **workflow**, the
  supplier portal, share-of-business re-tiering -> **6.4** (6.16 only links to them).
- Weighted **bid** evaluation and RFx question scoring -> **6.5 / 6.6** (already built - do not
  rebuild a scoring engine for sourcing events).
- GRN tolerances, inspection, NCR/RTV **mechanics** -> **6.12**; three-way match and dispute
  **workflow** -> **6.13**; spend/savings -> **6.14**. 6.16 only READS all of them as KPI signals.
- Contract SLAs, obligations, penalties tied to performance -> **6.8**.
- Supplier financial/credit risk, restricted-party screening, fraud rules -> **6.17**
  (`scm.SupplierRiskAssessment` already exists - the benchmark board READS `risk_index`, never
  clones it).
- Evidence-pack repository / version control / full-text search -> **6.19**.
- Network-wide supply-chain KPI targets, snapshots and the control tower -> **SCM 4.11**
  (`KpiTarget`/`KpiSnapshot` - a closed metric registry and a different subject; 6.16 borrows the
  PATTERN, never the table).

### Review notes

(filled in at the end)

---

---

# 6.17 HANDOFF — state at 2026-09-05 12:47 (read this before resuming)

**Do NOT restart from Phase 1.** Phases 1-2 (research, plan) and Phase 3 step 1 (frozen contract) are done and
committed. Build is ~70% complete. Resume at **Entity 4, views onward**.

## Read first
`.claude/tasks/contract-procurement-6.17.md` — **including the amended §0 drift row and the new §6a "Ownership
call"**, which changed Entity 4's scope mid-build. The plan below in this file is stale where §6a contradicts it.

## Done and committed

| | state |
|---|---|
| Phase 1 research | `.claude/tasks/research-procurement-6.17.md` |
| Phase 2 plan | this file, above |
| Phase 3.1 contract | `.claude/tasks/contract-procurement-6.17.md` (amended `48b578e5`) |
| **Entity 1** `ComplianceScreening` + `ScreeningHit` | **COMPLETE** — 4 backend files + 7 templates, 15 url names |
| **Entity 2** `SupplierRiskSignal` | **COMPLETE** — 4 backend files + 4 templates, 7 url names |
| **Entity 3** `FraudAlert` | **COMPLETE** — 6 backend files + 5 templates, 8 url names; 6-rule `scan()` proven idempotent (37/37 checks, twice) |
| **Entity 4** `PolicyAttestation` | **PART-BUILT** — model (`14a6327b`) + form (`8a82980d`) committed |

## Entity 4 — what is LEFT (scope changed, read §6a)

`procurement.ProcurementPolicy` **already exists** — 6.19 shipped it (`models/DocumentKnowledgeManagement/
Policies.py:152`, prefix `[PPOL-]`). Declaring a second raises `RuntimeError: Conflicting 'procurementpolicy'
models in application 'procurement'` and breaks `manage.py check` for every session in this checkout.
**Settled with 6.19 by message and confirmed both ways: 6.19 owns the policy table, 6.17 owns the ledger.**
6.19 keeps `requires_acknowledgment` unchanged; 6.17 reads it.

Still to write:
- `views/RiskComplianceManagement/Policies.py` — `policy_list`, `policy_detail`, `policy_mine`,
  `policy_overdue_board`, `policy_raise_attestations`
- `views/RiskComplianceManagement/Attestations.py` — attestation CRUD + `attestation_sign` (**OWNER-ONLY**, a
  tenant admin signing for someone else must be refused) + `attestation_exempt`
- `urls/RiskComplianceManagement/{Policies,Attestations}.py` + the splice into that package's `__init__.py`
  (**re-read it first — 6.19 corrected its first-segment inventory, which was missing five entries**)
- 7 templates: `policy/{list,detail}.html`, `attestation/{list,detail,form}.html`, `my_policies.html`,
  `policy_overdue.html`. **No `policy/form.html`** — 6.19 owns authoring; link to their `ppolicy_*` routes.

**Do NOT build** `policy_create/_edit/_delete/_publish/_archive/_new_version`. `policy_raise_attestations` is the
6.17-owned, admin-gated, `@require_POST`, **idempotent** verb that raises the roster for an already-published
policy — it exists so "publish raises the roster" needs zero edits to 6.19's code.

## Entity 5 `AuditSeal` — NOT started, and CUTTABLE
Bullet 3 ships as the `audit_trail` register over `core.AuditLog` regardless; that page is what `LIVE_LINKS`
points at. If the next session is short, cut `AuditSeal` and ship the register alone, stating on the page that
sealing is not yet available.

## Phase 3.4 Integrate — NOT started (single writer, main session only)
1. `models/__init__.py` + `forms/` + `views/` + `urls/__init__.py` re-export blocks — **targeted `Edit`, never
   `Write`** (three other sessions append to these same four files).
2. `admin.py`, extend `seed_procurement.py` (idempotent; **never `--flush`**), append 6.17's model names to
   `PROCUREMENT_CONTENT_MODELS` in `views/_helpers.py` so the activity feed sees them.
3. `LIVE_LINKS["6.17"]` — five bullets to five **distinct** staff pages (L30/L32).
4. `makemigrations` **last**.

### Migration protocol — the reserved-number queue was WITHDRAWN
Numbers by **arrival**, not by sub-module. **Announce to the other sessions immediately before running
`makemigrations`**, then verify a single leaf:
`MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes()` filtered to `procurement`.
`makemigrations` sweeps the **whole app registry** — run `--dry-run` first and read every model it lists; if it
names one you did not write, that is a coordination event (L51 §2). 6.17's models are **not re-exported yet**, so
they are currently invisible to everyone else's sweep — that safety ends the moment step 1 above runs.

**Do not wait for 6.19's `0026`.** Confirmed by that session 2026-09-05: their `makemigrations` is refused by
their own permission classifier and needs their user, so `0026` has been free for hours and may still be. Take
the next free number when you are ready. Their models are on disk and registered, so **your** `makemigrations`
will capture 6.19's four and 6.16's four along with 6.17's — that is expected under a registry-wide sweep, but
`--dry-run` and read the list before you commit to it, and tell both sessions what you swept in.

## Phases 4-7 — NOT started
Review (6 reviewers, serial) → `code-fixer` → tests → skill + README.

**The reviewers CANNOT use `BASE...HEAD`.** Four sessions commit to `main` in this one tree, so that range
contains 6.16's, 6.18's and 6.19's work and reviewers would file findings against the wrong sub-module. Scope
them to explicit paths, and **use `**` not `*`** — `templates/procurement/riskcompliance/*` matches only the
entity directories and none of the `.html` files, so a reviewer given it reads nothing and reports clean (L51 §5):
```
apps/procurement/models/RiskComplianceManagement/**
apps/procurement/forms/RiskComplianceManagement/**
apps/procurement/views/RiskComplianceManagement/**
apps/procurement/urls/RiskComplianceManagement/**
templates/procurement/riskcompliance/**
```
Expected counts to check the glob against before trusting a clean report — **verified on disk 2026-09-05 12:47**:

| | now (Entities 1-3 + Entity 4 model/form) | after Entity 4 completes | after Entity 5 (if not cut) |
|---|---|---|---|
| `.py` under the four `RiskComplianceManagement/` dirs (incl. `__init__.py`, excl. `__pycache__`) | **22** | 26 | 30 |
| `.html` under `templates/procurement/riskcompliance/` | **16** | 23 | 25 |

If a glob returns fewer than the "now" column, the glob is wrong — not the work absent. Verify with:
`find apps/procurement -path "*RiskComplianceManagement*" -name "*.py" ! -path "*pycache*" | wc -l`

## Commit discipline in this tree
`git add 'path'; git commit --only 'path' -m 'msg'` — one file per commit. Plain `git add` + `git commit` sweeps
peers' staged files into your commit (it already happened once, `8262b645`). Never `git add -A`/`.`. Never push.


---

# 6.17 CLOSE-OUT REVIEW (2026-09-06) — supersedes the HANDOFF block above

**Delivered.** Module 6 is now **19 of 19 sub-modules** — the Procurement Management System is complete.

## What shipped

| | |
|---|---|
| Models | 6 — `ComplianceScreening` + `ScreeningHit`, `SupplierRiskSignal`, `FraudAlert`, `PolicyAttestation`, `AuditSeal` |
| Backend | 30 `.py` across `models/forms/views/urls` `RiskComplianceManagement/` |
| Templates | 26 under `templates/procurement/riskcompliance/` |
| Routes | 54 url names, 14 first path segments |
| Migrations | `0028` (tables), `0030` (review fixes + `last_verified_by`) |
| Tests | **470** — models 102, forms 113 fns/188 cases, views 117, security 63 |
| Review | 6 passes, **39 findings**: 37 fixed, 2 skipped app-wide, 1 refuted |

## The five NavERP.md bullets, and how each is actually served
1. **Regulatory Compliance Checks** → `ComplianceScreening` + `ScreeningHit`. 13 list sources (CSL and
   SAM.gov separate — the CSL excludes SAM), 4 OFAC checkpoints, dispositions mandatory even on a false
   positive (31 CFR 501.601), a true match escalating into the **existing** 6.4 `VendorSuspension`.
2. **Supplier Financial Risk Monitoring** → `SupplierRiskSignal` with `METRIC_SCALES`, the constant that
   lets FHR 100 (healthy) and SER 9 (dangerous) render honestly on one page.
3. **Audit Trail & Logging** → the `audit_trail` register plus `AuditSeal`'s SHA-256 chain.
4. **Fraud Detection Rules** → `FraudAlert.scan()`, six rules, none of them 6.14's.
5. **Policy Management & Acknowledgment** → `PolicyAttestation` over 6.19's policy library.

## Decisions worth carrying forward
- **6.19 owns `ProcurementPolicy`; 6.17 owns the ledger.** Ships-first (L36), settled by cross-session
  message, recorded in contract §6a, 6.19's docstring and the module skill. A second declaration raises
  `RuntimeError` and breaks `check` repo-wide.
- **Tamper-EVIDENT, never tamper-proof.** `core.AuditLog` has no immutability guarantee. Every surface
  says so. Over-claiming would be a security defect, not a wording nit.
- **`screening_batch` cut**, and the vendor bank-detail fraud rule declared **not buildable** on the page
  (`accounting.VendorProfile` has no bank fields) rather than faked.
- **`auditseal_verify` left un-gated deliberately** — `verify()` recomputes from live data so the stamps
  cannot be flipped to a false value, and a tamper check only an admin can run is a check nobody runs.

## What the six review passes actually caught (the case for running all six)
Each pass found something the others could not:
- **code-reviewer** — C1: a hit deletable out of a *decided* screening, erasing the match the decision
  rested on.
- **security-reviewer** — I3: `policyattestation_edit` ungated while its sibling delete was admin-only, so
  the template's `is_admin` gate was cosmetic and any member could reassign an obligation.
- **performance-reviewer** — C2: `defer()` scopes to the root model, so a `select_related("prev_seal")`
  re-pulled a 50k-pair JSON blob (~21 MB/page) **past** the defer. Invisible to any query-count test.
- **frontend-reviewer** — I10: three `confirm()` handlers HTML-escaping a Python-authored string; correct
  today, one apostrophe away from silently disarming a dialog.
- **explorer** — I11: the `kind="risk"` hand-off to 6.1 was never completed, so 6.17's alerts were
  unfilterable *and* uneditable in that inbox.
- **qa-smoke-tester** — proved by execution what the others could only reason about: the disposition gate
  survives its cached counters being zeroed by raw `UPDATE`, and the seal detects modify/delete/insert while
  naming the offending log id.

## Known gaps, stated rather than hidden
- **Three seeded fraud alerts are hand-raised** and not reproducible by the rules whose labels they carry
  (acme has no `RequisitionApproval` rows). Pressing *Run scan* over their window reports "raised nothing
  new". Recorded at `seed_procurement.py:~4419` and as finding M26.
- **`self_approval` has no seeded runtime coverage** — the model lane builds its own fixture data for it and
  for three other rules, so all six are tested; only two are exercised by the demo workspace.
- **M3 and M22 skipped as app-wide** (`PROCUREMENT_CONTENT_MODELS` entries that are inert on the
  procurement branch; `<dt>`/`<dd>` outside a `<dl>`, which renders correctly via descendant selectors and
  appears 28 more times outside this sub-module). Forking 6.17 out of step with twelve other modules would
  be worse than the defect (L18/L28).
- **I13 routed to 6.19, not fixed here** — four of their surfaces still say the ledger does not exist, one
  user-visible. Their files; message sent.

## Cross-session notes
Built alongside live 6.16, 6.18 and 6.19 sessions in one checkout. Two of their files ended up inside 6.17
commits (`8262b645`, `00b28c0e`) — nothing lost, both flagged by message, neither rebased. The migration
queue was replaced mid-build by arrival-order-plus-announce, and `0030` deliberately carried three of 6.16's
indexes because `makemigrations` reads the app registry, not a file list. See **L51** and its correction.

# Sub-module 6.19 - Document & Knowledge Management (Module 6: Procurement Management System, `procurement`) - plan from research-procurement-6.19.md  (2026-09-05)

> Built AHEAD of 6.16/6.17/6.18 (no `LIVE_LINKS` key exists for any of them). Scope is the research's
> recommended four models, unchanged - the code did not contradict it. Sub-module folder
> `DocumentKnowledgeManagement/` in all four backend packages; template folder slug **`documentknowledge`**
> (the as-built short-slug convention the two most recent siblings use: 6.14 -> `spendanalytics`,
> 6.15 -> `budgetcost` - NOT the full lowercased PascalCase name, and NOT the research's `documents/`).

## Scope decision (FROZEN by Phase 1 - do not re-litigate)

- [ ] Four models, no fifth. `ProcurementDocument` [PDOC-] + `ProcurementDocumentRevision` (child) +
      `ProcurementPolicy` [PPOL-] + `KnowledgeResource` [PKR-].
- [ ] **`core.Document` is NOT touched** - no schema change, no migration, no deprecation. It stays the generic
      GFK attachment (`core:document_*`, FK'd live by `procurement.SupplierInvoice.document`). 6.19 declares its
      own procurement-scoped repository because `core.Document` has a flat `version` CharField, no owner, no
      status, no expiry, no extracted text, and a GFK that cannot be tenant-filtered at the queryset level.
      Note the future Module 13 migration in `ProcurementDocument`'s docstring (the `RequisitionTemplate`
      `core.Item` idiom).
- [ ] **Do NOT build Module 13 early.** Out of scope, named in the model docstrings: folder hierarchies/virtual
      folders (13.4), branching/merge/redline diff (13.2), permission matrices/watermarking/DRM/DLP (13.7),
      OCR/semantic/NL search + auto-tagging (13.5/13.6), retention auto-destruction/legal hold/WORM (13.9/13.14),
      wikis (13.17), saved-search alerts (13.6).
- [ ] **Do NOT build a second one of anything that exists.** `procurement.ContractClause` (6.8) IS the clause
      library. `procurement.RequisitionTemplate` (6.2) IS the executable requisition template. `RfxEvent`/
      `RfxQuestion` (6.6) ARE the questionnaire builder. `ContractMilestone` (6.8) IS the obligation record.
      `KnowledgeResource` is **guidance content**, cross-linked, never a second engine.
- [ ] **Naming honesty - one hard ban.** The word **"OCR"** may not appear on any 6.19 page, label, help_text or
      empty state (the 6.13 contract already forbids it and a scanned PDF genuinely yields nothing). Say
      "text read from the file" / "this file has no text layer".

## Spine: grep-VERIFIED this pass (L28 - the grep is the truth, not the ERD)

| Target | Verified at | Used for |
|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:5` | every `tenant` FK (via `TenantOwned`/`TenantNumbered`) |
| `core.Party` | `apps/core/models/Party.py:5` | `ProcurementDocument.supplier` |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | `ProcurementPolicy.applies_to` |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | `ProcurementPolicy.threshold_currency` |
| `scm.SupplierContract` | `apps/scm/models/SupplierRelationshipManagement/SupplierContracts.py:13` | `ProcurementDocument.contract` |
| `scm.PurchaseOrder` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` | `ProcurementDocument.purchase_order` - **the SCM one**, NOT the legacy `crm.PurchaseOrder` at `apps/crm/models/InventoryVendor/PurchaseOrders.py:5` |
| `procurement.SourcingEvent` [SEV-] | `apps/procurement/models/SourcingTendering/SourcingEvents.py:21` | `ProcurementDocument.sourcing_event` |
| `procurement.ProcurementAlert` | `apps/procurement/models/DashboardPortal/ProcurementAlerts.py:26` | the reminder scan raises `kind="deadline"` rows here |
| `apps.core.utils.write_audit_log` / `next_number` | `apps/core/utils.py:6` / `:34` | audit rows + the three number prefixes |
| `ALLOWED_DOC_EXTENSIONS` / `MAX_UPLOAD_BYTES` | `apps/core/forms/_common.py:16` / `:22` | 14 extensions, 20 MB - the ONLY upload allow-list this sub-module uses |
| `pdfplumber==0.11.10` | `requirements.txt:14` | lazy optional import, mirroring `views/InvoiceVoucherManagement/SupplierInvoices.py:418 _pdf_text` |

- [ ] Every FK above is declared **by string** (`"core.Party"`, `"scm.PurchaseOrder"`, …) - no cross-app model
      imports at module level.
- [ ] Confirmed absent, so nothing may hope for them: no `documents` app (Module 13 unbuilt), no
      `procurement.Contract`, no `core.Item`/commodity taxonomy, no `Tag` table, no Elasticsearch/Celery/
      `SearchVector`. Search is `icontains`; **no MySQL FULLTEXT index** (prod is MySQL `settings.py:102`, tests
      are SQLite `settings_test.py:10` - a FULLTEXT index would not exist under test). State this in the model
      docstring and on the register page.

---

## Model 1 - `ProcurementDocument` [PDOC-] (`models/DocumentKnowledgeManagement/Documents.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PDOC"`. Realizes bullets **1 Central Document Repository**,
**2 Version Control (parent half)**, **5 Full-Text Search & Indexing**.

### Choices (exact machine values)
- [ ] `DOC_TYPE_CHOICES` (driver: Oracle attachment categories + Coupa contract types + Ariba main-vs-addenda):
      `quote`/Quote, `specification`/Specification, `warranty`/Warranty, `certificate`/Certificate,
      `insurance`/Certificate of Insurance, `sow`/Statement of Work, `drawing`/Drawing, `correspondence`/
      Correspondence, `policy`/Policy Document, `template`/Template, `other`/Other
- [ ] `CLASSIFICATION_CHOICES` (driver: Ariba folder ACLs / Ivalua role views / Icertis) - **first three values
      verbatim from `core.Document.CLASSIFICATION_CHOICES`** so a future Module 13 merge is a straight map:
      `public`/Public, `internal`/Internal, `confidential`/Confidential, `restricted`/Restricted
- [ ] `STATUS_CHOICES` (driver: supersede/archive lifecycle in every CLM surveyed):
      `draft`/Draft, `active`/Active, `superseded`/Superseded, `archived`/Archived
- [ ] `EXPIRY_FILTER_CHOICES` (register facet, not a column): `expiring`/Expiring soon,
      `expired`/Expired, `review_due`/Review due, `over_retention`/Past retention
- [ ] Constants: `EXPIRY_WARN_DAYS = 30`, `REMINDER_WINDOW_DAYS = 30`, `REINDEX_ROW_CAP = 200`
- [ ] `STATUS_CSS = {"draft": "badge-muted", "active": "badge-green", "superseded": "badge-amber",
      "archived": "badge-slate"}` and `CLASSIFICATION_CSS = {"public": "badge-info", "internal": "badge-slate",
      "confidential": "badge-amber", "restricted": "badge-red"}` - **colour-named theme.css classes only
      (L33); `badge-success`/`badge-danger` do not exist.**

### Fields
- [ ] `title` `CharField(max_length=200)` - driver: one tenant-wide register (Coupa/JAGGAER/GEP/Ivalua/Icertis)
- [ ] `doc_type` `CharField(max_length=16, choices=DOC_TYPE_CHOICES, default="other")`
- [ ] `description` `TextField(blank=True)`
- [ ] `tags` `CharField(max_length=255, blank=True, help_text="Comma-separated keywords")` - driver: Coupa
      metadata tagging / Icertis smart tagging. **A CharField, not a `Tag` table** (that is model #5; 13.5 owns
      controlled vocabulary). Normalized in `clean()`: lowercase, strip, dedupe, re-joined `", "`.
- [ ] `classification` `CharField(max_length=14, choices=CLASSIFICATION_CHOICES, default="internal")`
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` - **verb-driven, NOT on the
      form** (see Verbs)
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="procurement_documents_owned")`
      - driver: Procurify contract ownership / Ariba SLP primary supplier manager
- [ ] `supplier_visible` `BooleanField(default=False, help_text="Vendors may see this in the 6.4 portal when that page ships")`
      - driver: Precoro Internal/External PO attachment sections. **A field only** - the portal page is 6.4's.
- [ ] `effective_date` `DateField(null=True, blank=True)`
- [ ] `expires_on` `DateField(null=True, blank=True)` - driver: Ariba SLP Expiring/Expired certificates, Oracle
      expiration notification, Ivalua missing/expired detection
- [ ] `review_on` `DateField(null=True, blank=True)` - driver: policy re-review cadence / JAGGAER event reminders
- [ ] `retention_until` `DateField(null=True, blank=True, help_text="Hold until this date. Nothing is deleted automatically.")`
      - driver: Basware Vault 7-15 year retention. **A flag, never an action** (13.9/13.14 own destruction).
- [ ] `current_revision_no` `PositiveSmallIntegerField(default=0, editable=False)` - **an integer pointer, NOT a
      circular FK** (`crm.ContractDocument.current_version` precedent). `0` = no approved revision yet.
- [ ] `checked_out_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`
      - driver: Ariba document check-out. **Advisory** - see Verbs.
- [ ] `checked_out_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `extracted_text` `TextField(blank=True, editable=False)` - the **search index copy** of the currently
      approved revision's text. Never user-editable, never on a form, never shown as an input.
- [ ] FK `supplier` -> `"core.Party"` `SET_NULL, null=True, blank=True, related_name="procurement_documents"`
- [ ] FK `contract` -> `"scm.SupplierContract"` `SET_NULL, null=True, blank=True, related_name="procurement_documents"`
- [ ] FK `purchase_order` -> `"scm.PurchaseOrder"` `SET_NULL, null=True, blank=True, related_name="procurement_documents"`
- [ ] FK `sourcing_event` -> `"procurement.SourcingEvent"` `SET_NULL, null=True, blank=True, related_name="documents"`
      - all four drivers: Coupa contracts<->POs<->suppliers, Ivalua sourcing/POs/invoices, Precoro PR/PO/RFP,
      Procurify contract<->PO. **Four real columns, explicitly NOT a GenericForeignKey** - the register must
      facet/join on them and a GFK is not tenant-filterable at the queryset level (an IDOR surface).
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

### Meta / behaviour
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`
- [ ] `indexes`: `("tenant","status")` `prc_pdoc_tnt_status_idx`; `("tenant","doc_type")` `prc_pdoc_tnt_type_idx`;
      `("tenant","expires_on")` `prc_pdoc_tnt_expiry_idx`; `("tenant","supplier")` `prc_pdoc_tnt_sup_idx`
      (all <= 30 chars)
- [ ] `verbose_name = "Procurement Document"` / plural `"Procurement Documents"`
- [ ] `__str__` -> `f"{self.number or 'PDOC'} · {self.title}"`
- [ ] Properties: `tag_list` (split/strip/drop-empties), `status_css`, `classification_css`,
      `is_expired` (`expires_on` and `expires_on < today`), `is_expiring`
      (`today <= expires_on <= today + EXPIRY_WARN_DAYS`), `is_review_due`, `is_over_retention`,
      `is_checked_out` (`checked_out_by_id is not None`),
      `current_revision` -> `self.revisions.filter(revision_no=self.current_revision_no).first()` when
      `current_revision_no` else `None` (**reverse accessor - no import of the child model, no cycle**)
- [ ] `clean()`: normalize `tags`; cross-tenant backstop on `supplier`/`contract`/`purchase_order`/
      `sourcing_event` (`"That record belongs to another workspace."`); reject `expires_on < effective_date`

### Reminder engine (same file, module-level - NOT a fifth model)
- [ ] `expiring_documents(tenant, *, on=None)` -> list of `{"document", "days_left", "reason"}` for rows whose
      `expires_on` or `review_on` is within `REMINDER_WINDOW_DAYS` (or already past), `status__in=("draft","active")`
- [ ] `run_document_reminders(tenant, user)` -> `{"raised": n, "skipped_open": n}` - **copy
      `ContractsManagement/Renewals.py:55 run_renewal_alerts` exactly**: `transaction.atomic()` +
      `ProcurementDocument.objects.select_for_update().get(pk=...)` row lock, dedupe against an existing
      `ProcurementAlert` with the same `link_url` and `status__in=("open","acknowledged")`,
      `kind="deadline"`, `severity="critical"` when `days_left <= 7` else `"warning"`,
      `link_url = f"/procurement/documents/{pk}/"` (**internal path only** - `ProcurementAlert.clean()` rejects
      absolute/`javascript:` values)
- [ ] `@transaction.atomic run_document_reminders_audited(tenant, user)` wrapper -> runs the scan +
      `write_audit_log(user, None, "document_reminders_run", {...})`
- [ ] Docstring states plainly: **no scheduler and no mail worker exist** (the 6.3/6.8 ruling) - this is a
      user-pressed verb and the alert inbox is the channel.

### Form exclusions (`ProcurementDocumentForm`)
- [ ] `Meta.fields = ["title", "doc_type", "description", "tags", "classification", "owner",
      "supplier_visible", "effective_date", "expires_on", "review_on", "retention_until",
      "supplier", "contract", "purchase_order", "sourcing_event"]`
- [ ] **EXCLUDED, each deliberately:** `tenant` (stamped by `TenantUniqueMixin`/`crud_create`),
      `number` (`TenantNumbered.save()`), `status` (verb-driven workflow), `current_revision_no` (maintained
      by the approve verb only), `checked_out_by`/`checked_out_at` (lock verbs), `extracted_text`
      (machine-written, never typed), `created_by` (authorship stamp), `created_at`/`updated_at` (base timestamps)

---

## Model 2 - `ProcurementDocumentRevision` (`models/DocumentKnowledgeManagement/Revisions.py`)

Base `TenantOwned` (**not** numbered - it takes `revision_no` within its parent, exactly like
`crm.DocumentVersion`). Realizes bullet **2 Version Control**. Split into its own entity file rather than living
inside `Documents.py` because it has its own register page and its own url module - the as-built 6.13
`SupplierInvoices.py` / `SupplierInvoiceLines.py` precedent.

### Fields
- [ ] `document` `FK("procurement.ProcurementDocument", CASCADE, related_name="revisions")`
- [ ] `revision_no` `PositiveSmallIntegerField(default=1, editable=False)`
- [ ] `file` `FileField(upload_to="procurement/documents/%Y/%m/", help_text="Serve with Content-Disposition: attachment and keep MEDIA_ROOT outside any executable path.")`
      (the `RfxManagement/Responses.py:49` idiom, verbatim)
- [ ] `original_filename` `CharField(max_length=255, blank=True, editable=False)`
- [ ] `file_size` `PositiveIntegerField(default=0, editable=False)`
- [ ] `sha256` `CharField(max_length=64, blank=True, editable=False, help_text="Integrity checksum of the stored bytes")`
      - driver: Basware signing/timestamping, 13.14 fixity. **`hashlib` only - no dependency, and the page says
      "checksum", never "tamper-proof"/"WORM".**
- [ ] `change_note` `CharField(max_length=255, blank=True)` - the ONLY user-typed field on this model
- [ ] `is_approved` `BooleanField(default=False, editable=False)`
- [ ] `approved_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`
- [ ] `approved_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `uploaded_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`
- [ ] `extracted_text` `TextField(blank=True, editable=False)` - the text read from THIS file, capped at ingest
- [ ] `extraction_note` `CharField(max_length=255, blank=True, editable=False)` - the honest warning
      ("this file has no text layer", "text extraction is not installed on this server"). **This field is what
      makes the no-OCR contract visible on the page.**
- [ ] **No separate `uploaded_at`** - `TenantOwned.created_at` IS the upload moment; say so in the docstring
      so the templates do not invent a second name.

### Meta / behaviour
- [ ] `ordering = ["-revision_no", "-id"]`
- [ ] `unique_together = ("tenant", "document", "revision_no")` - the database backstop for the allocation race
- [ ] `indexes`: `("tenant","document")` `prc_pdrev_tnt_doc_idx`; `("tenant","is_approved")` `prc_pdrev_tnt_appr_idx`
- [ ] `__str__` -> `f"{self.document.number} r{self.revision_no}"`
- [ ] Property `is_current` -> `self.revision_no == self.document.current_revision_no`

### Module-level helpers (same file)
- [ ] `EXTRACT_MAX_CHARS = 200_000` - cap at ingest so one pathological PDF cannot bloat the row
- [ ] `PLAIN_TEXT_EXTENSIONS = {".txt", ".csv"}`
- [ ] `file_sha256(upload)` -> hex digest, streamed over `upload.chunks()`, with `upload.seek(0)` before AND
      after so the same handle can still be saved
- [ ] `extract_document_text(revision)` -> `(text, note)`. **Copy the exact posture of
      `views/InvoiceVoucherManagement/SupplierInvoices.py:418 _pdf_text`:**
      lazy `import pdfplumber` inside the function with `except ImportError: pdfplumber = None`;
      `("", "Text extraction is not installed on this server - this file is searchable by its title, description and tags only.")`
      when absent; `("", "The stored file could not be read back.")` when `file.path` is missing;
      `("", "That file could not be read.")` on a malformed PDF (broad `except Exception` - a page, not a 500);
      `("", "This file has no text layer, so there is no text to search.")` when the extract is blank;
      plain-text extensions decoded directly with `errors="replace"`; every return truncated to `EXTRACT_MAX_CHARS`.

### THE REVISION CHAIN - exact rules (the riskiest part of this sub-module)

- [ ] **Immutability is structural, not enforced by a `save()` guard.** (a) There is **no edit url, no edit view
      and no edit template** for a revision (the documented CRUD exemption `CostForecast` /
      `SpendReportSnapshot` already carry - state it in the url module docstring). (b) Every column except
      `change_note` is `editable=False`, so no `ModelForm` can ever surface it. (c) The ONLY form is
      `ProcurementDocumentRevisionUploadForm`, used on the create path only. (d) The only post-create writes are
      the approve verb's `save(update_fields=["is_approved", "approved_by", "approved_at"])`.
- [ ] **Upload** (`pdocument_revision_upload`): guards, in order -
      (1) `request.tenant is None` -> refuse (the `_need_tenant` idiom);
      (2) `document.status == "archived"` -> refuse with a message;
      (3) `document.checked_out_by_id not in (None, request.user.pk)` -> refuse, naming the holder.
      Then, inside `transaction.atomic()`:
      `locked = ProcurementDocument.objects.select_for_update().get(pk=document.pk, tenant=request.tenant)`;
      `revision_no = (locked.revisions.aggregate(m=Max("revision_no"))["m"] or 0) + 1`;
      compute `sha256`/`file_size`/`original_filename` **before** `save()`; save; then run
      `extract_document_text(revision)` and store `extracted_text` + `extraction_note` on the REVISION via
      `save(update_fields=[...])`. `unique_together` is the backstop - catch `IntegrityError` and retry once
      (the `TenantNumbered.save()` idiom), then surface an honest error.
- [ ] **Uploading NEVER moves `current_revision_no`.** A new revision lands `is_approved=False`. This is the
      literal NavERP bullet: only the latest *approved* version is the accessible one.
- [ ] **Approve** (`pdocrevision_approve`, `@require_POST` + `@tenant_admin_required`):
      (1) 404 unless `revision.tenant == request.tenant` **and** `revision.document.tenant == request.tenant`
      (double scope - never trust the child alone);
      (2) already `is_approved` -> idempotent `messages.info`, redirect, no write;
      (3) `revision.revision_no <= document.current_revision_no` -> **refuse**: "the revision chain is linear
      and only moves forward". **This single rule is what keeps the chain linear.**
      Then `transaction.atomic()` + `select_for_update()` on the PARENT:
      stamp `is_approved=True`/`approved_by=request.user`/`approved_at=timezone.now()`
      (`save(update_fields=[...])`); set `document.current_revision_no = revision.revision_no`;
      **copy** `document.extracted_text = revision.extracted_text[:EXTRACT_MAX_CHARS]`;
      if `document.status == "draft"` set `document.status = "active"`;
      `document.save(update_fields=["current_revision_no", "extracted_text", "status", "updated_at"])`;
      `write_audit_log(request.user, document, "revision_approve", {"revision_no": n, "sha256": revision.sha256[:16]})`.
- [ ] **Older approved revisions keep `is_approved=True`** - they *were* approved and rewriting history would be
      a lie. "Only the latest approved version is accessible" is expressed by `current_revision_no` pointing at
      exactly one revision; `ProcurementDocument.current_revision` is the single place that resolves it, and the
      templates badge that one `badge-green` "Current" and every earlier approved one `badge-amber` "Superseded".
- [ ] **The parent's `extracted_text` is a denormalized SEARCH COPY**, refreshed only by (a) approve and
      (b) re-index. The text of record lives on the revision. Say this in both docstrings so no later pass
      "fixes" it into a live join.
- [ ] **Delete** (`pdocrevision_delete`, `@require_POST`): allowed **only** when `is_approved is False` **and**
      `revision_no != document.current_revision_no`. Otherwise `messages.error` + redirect (never a 500). A bad
      upload that never entered the approved record can go; approved history cannot.
- [ ] `# WARNING:` in the delete view and in `pdocument_delete`: **Django does not remove the file from
      MEDIA_ROOT when the row is deleted.** The confirm text must say the record is removed but the stored file
      is not reclaimed here; disk reclamation is a deliberate later job (13.9/13.14 retention), never a silent
      `os.remove` on a path derived from user input.
- [ ] `# WARNING:` on the upload path: validate the extension against `ALLOWED_DOC_EXTENSIONS` and the size
      against `MAX_UPLOAD_BYTES` **imported explicitly from `apps.core.forms._common`, inside the clean method**
      - `apps/procurement/forms/CatalogManagement/UploadBatches.py:13` defines a DIFFERENT local
      `MAX_UPLOAD_BYTES` (2 MB), and a package-level re-export would make which limit applies depend on import
      order. This is exactly what `forms/GoodsReceiptInspection/ReceiptDiscrepancies.py:124` and
      `forms/InvoiceVoucherManagement/SupplierInvoices.py:204` already do - copy them. **Do not invent a second
      allow-list.** Never render an uploaded file inline (stored-XSS surface); link to it and let the browser decide.

### Form (`ProcurementDocumentRevisionUploadForm`)
- [ ] `Meta.fields = ["file", "change_note"]` - **that is the whole form.**
- [ ] EXCLUDED: `tenant`, `document` (comes from the url pk, never a POST field), `revision_no`,
      `original_filename`, `file_size`, `sha256`, `is_approved`, `approved_by`, `approved_at`, `uploaded_by`,
      `extracted_text`, `extraction_note`, `created_at`/`updated_at`.
- [ ] `clean_file()` - the allow-list + size check described above, message text mirroring
      `core.forms.DocumentForm.clean_file`.

---

## Model 3 - `ProcurementPolicy` [PPOL-] (`models/DocumentKnowledgeManagement/Policies.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PPOL"`. Realizes bullet **3 Procurement Policy Library**. Modelled on
the proven `hrm.HRPolicy` (`apps/hrm/models/ComplianceLegal/Hrpolicy.py:5`).

### Choices
- [ ] `POLICY_TYPE_CHOICES` (driver: Ariba guided-buying policy content, ConvergePoint/Xoralia/Sprinto category):
      `purchasing_rule`/Purchasing Rule, `approval_limit`/Approval Limit, `competitive_bidding`/Competitive
      Bidding, `sole_source`/Sole Source, `supplier_code_of_conduct`/Supplier Code of Conduct,
      `ethics_conflict`/Ethics & Conflict of Interest, `sustainability`/Sustainability, `data_security`/Data
      Security, `other`/Other
- [ ] `STATUS_CHOICES`: `draft`/Draft, `published`/Published, `archived`/Archived
- [ ] `THRESHOLD_BASIS_CHOICES` (driver: Ariba smart-policy rules, JAGGAER value/type/risk approvals, Procurify
      card limits): `per_line`/Per line, `per_requisition`/Per requisition, `per_purchase_order`/Per purchase
      order, `per_contract_year`/Per contract year, `annual_supplier_spend`/Annual spend with one supplier
- [ ] `STATUS_CSS = {"draft": "badge-muted", "published": "badge-green", "archived": "badge-slate"}`

### Fields
- [ ] `title` `CharField(max_length=200)`
- [ ] `policy_type` `CharField(max_length=26, choices=POLICY_TYPE_CHOICES, default="purchasing_rule")`
- [ ] `summary` `CharField(max_length=500, blank=True)`
- [ ] `body` `TextField(blank=True)` - the rule as written for humans
- [ ] `version_number` `CharField(max_length=20, default="1.0")` - driver: version-level attestation in the
      policy-management category
- [ ] `previous_version` `FK("self", SET_NULL, null=True, blank=True, related_name="superseded_by")` - the
      supersession chain (HRM precedent)
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` - **verb-driven, NOT on the form**
- [ ] `effective_from` `DateField(null=True, blank=True)`
- [ ] `published_at` `DateTimeField(null=True, blank=True, editable=False)` - stamped by the publish verb only
- [ ] `next_review_on` `DateField(null=True, blank=True)` - driver: re-review cadence / stale-content surfacing
- [ ] `threshold_amount` `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])`
- [ ] `threshold_basis` `CharField(max_length=22, choices=THRESHOLD_BASIS_CHOICES, blank=True)`
- [ ] `threshold_currency` `FK("accounting.Currency", SET_NULL, null=True, blank=True, related_name="procurement_policies")`
      - **a display label; no conversion, no ledger effect (L29)**
- [ ] `requires_acknowledgment` `BooleanField(default=False, help_text="A hook for 6.17 Policy Management & Acknowledgment - no sign-off ledger is built here.")`
- [ ] `applies_to` `FK("core.OrgUnit", SET_NULL, null=True, blank=True, related_name="procurement_policies", help_text="Blank = the whole workspace.")`
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="procurement_policies_owned")`
- [ ] `document` `FK("procurement.ProcurementDocument", SET_NULL, null=True, blank=True, related_name="policies", help_text="The policy PDF in the repository - so it inherits revision control and text search.")`
      - **this FK is what makes 6.19 one sub-module instead of two unrelated halves**
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

### Meta / behaviour
- [ ] `ordering = ["-created_at", "-id"]`
- [ ] `unique_together = (("tenant", "number"), ("tenant", "title", "version_number"))` (HRM precedent - a
      version of a title exists once)
- [ ] `indexes`: `("tenant","status")` `prc_ppol_tnt_status_idx`; `("tenant","policy_type")` `prc_ppol_tnt_type_idx`;
      `("tenant","next_review_on")` `prc_ppol_tnt_review_idx`
- [ ] `__str__` -> `f"{self.title} v{self.version_number}"`
- [ ] Properties: `status_css`, `is_review_due` (`next_review_on and next_review_on <= today`)
- [ ] `clean()`: cross-tenant backstop on `applies_to`/`document`/`previous_version`; `previous_version` may not
      be `self`; `threshold_amount` and `threshold_basis` must be set together (either both or neither)
- [ ] Module constant `ADVISORY_NOTE` printed on the list, form and detail pages - **ONE constant so the three
      surfaces cannot disagree**: "A policy records the rule for people to read. It enforces nothing on its own:
      approval routing is decided by the 6.3 Approval Workflow Engine's routing rules, and any threshold here is
      documentation, not a control."

### Verbs
- [ ] `ppolicy_publish` (`@require_POST` + `@tenant_admin_required`): `draft` -> `published`, stamps
      `published_at = timezone.now()`, `write_audit_log(user, obj, "policy_publish", {...})`. Already published
      -> idempotent `messages.info`. Archived -> refuse.
- [ ] `ppolicy_archive` (`@require_POST`): any -> `archived`, audit `policy_archive`.

### Form (`ProcurementPolicyForm`) exclusions
- [ ] `Meta.fields = ["title", "policy_type", "summary", "body", "version_number", "previous_version",
      "applies_to", "owner", "document", "effective_from", "next_review_on", "threshold_amount",
      "threshold_basis", "threshold_currency", "requires_acknowledgment"]`
- [ ] EXCLUDED: `tenant`, `number`, `status` (verb-driven), `published_at` (verb stamp), `created_by`,
      `created_at`/`updated_at`
- [ ] `previous_version.queryset` excludes `self.instance.pk` on edit; `document.queryset` is tenant-scoped
      (TenantModelForm does it, `_reject_foreign` re-checks it); `threshold_currency.queryset` =
      `Currency.objects.filter(is_active=True).order_by("code")` with `empty_label = "- not labelled -"`
      (**global table, no tenant column - the 6.15 `CostForecastForm` note applies verbatim**)

---

## Model 4 - `KnowledgeResource` [PKR-] (`models/DocumentKnowledgeManagement/KnowledgeResources.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PKR"`. Realizes bullet **4 Best Practices & Templates**, contributes to **5**.

### Choices
- [ ] `RESOURCE_TYPE_CHOICES` (driver: Ariba sourcing content library, JAGGAER industry templates, GEP template
      library, Zycus playbooks, Ivalua pre-approved templates): `rfp_template`/RFP Template,
      `rfq_template`/RFQ Template, `evaluation_scorecard`/Bid Evaluation Scorecard,
      `negotiation_playbook`/Negotiation Playbook, `checklist`/Checklist, `guide`/How-to Guide,
      `sample_document`/Sample Document, `training`/Training Material
- [ ] `CATEGORY_CHOICES` (**a choices field, not an FK - there is no commodity taxonomy table;
      `procurement.CatalogItem.category_text` is free text**): `general`/General, `it_software`/IT & Software,
      `facilities`/Facilities, `logistics`/Logistics & Freight,
      `professional_services`/Professional Services, `raw_materials`/Raw Materials, `capex`/Capital Equipment,
      `marketing`/Marketing, `other`/Other
- [ ] `AUDIENCE_CHOICES` (driver: Ariba persona landing pages, JAGGAER region/BU targeting): `all`/Everyone,
      `requester`/Requesters, `buyer`/Buyers, `approver`/Approvers, `legal`/Legal
- [ ] `STATUS_CHOICES`: `draft`/Draft, `published`/Published, `archived`/Archived
- [ ] `STATUS_CSS = {"draft": "badge-muted", "published": "badge-green", "archived": "badge-slate"}`
- [ ] `FEATURED_CAP = 6` (the "start here" shelf on the library page)

### Fields
- [ ] `title` `CharField(max_length=200)`
- [ ] `resource_type` `CharField(max_length=22, choices=RESOURCE_TYPE_CHOICES, default="guide")`
- [ ] `category` `CharField(max_length=22, choices=CATEGORY_CHOICES, default="general")`
- [ ] `audience` `CharField(max_length=12, choices=AUDIENCE_CHOICES, default="all")`
- [ ] `summary` `CharField(max_length=500, blank=True)`
- [ ] `body` `TextField(blank=True)` - the guidance itself, rendered on the detail page. Driver: Zycus
      playbook fallback positions ("open with / fall back to / walk away"), GEP approved language.
- [ ] `tags` `CharField(max_length=255, blank=True)` + `tag_list` property (same normalization as the document)
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` - **verb-driven, NOT on the form**
- [ ] `is_featured` `BooleanField(default=False)` - driver: Ariba guided-buying tiles / GEP portal "start here"
- [ ] `usage_count` `PositiveIntegerField(default=0, editable=False)` - driver: Ivalua clause-utilization
      analytics, GEP repository intelligence. **A click counter, never a derived metric** - say so in the docstring.
- [ ] `last_used_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `review_on` `DateField(null=True, blank=True)`
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="procurement_knowledge_owned")`
- [ ] `document` `FK("procurement.ProcurementDocument", SET_NULL, null=True, blank=True, related_name="knowledge_resources", help_text="The downloadable artifact in the repository - so it gets revisions and approval like everything else.")`
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

### Meta / behaviour
- [ ] `ordering = ["-is_featured", "-created_at", "-id"]`
- [ ] `unique_together = ("tenant", "number")`
- [ ] `indexes`: `("tenant","status")` `prc_pkr_tnt_status_idx`; `("tenant","resource_type")` `prc_pkr_tnt_type_idx`;
      `("tenant","is_featured")` `prc_pkr_tnt_feat_idx`
- [ ] `__str__` -> `f"{self.number or 'PKR'} · {self.title}"`
- [ ] `clean()`: normalize `tags`; cross-tenant backstop on `document`
- [ ] Module constant `LIBRARY_NOTE` on list/detail/form: "Guidance content, not an executable template. The
      requisition templates that actually raise a purchase live in 6.2, the RFx questionnaire builder in 6.6 and
      the pre-approved clause library in 6.8 - this library links to them, it does not replace them."

### Verbs
- [ ] `knowledgeresource_publish` / `knowledgeresource_archive` (`@require_POST`), same shape as the policy verbs
- [ ] `knowledgeresource_use` (`@require_POST`, `@login_required`): refuse on `archived`; otherwise
      `usage_count = F("usage_count") + 1`, `last_used_at = timezone.now()`,
      `save(update_fields=["usage_count", "last_used_at", "updated_at"])`, `refresh_from_db(fields=["usage_count"])`,
      `write_audit_log(user, obj, "knowledge_resource_used", {"usage_count": obj.usage_count})`, then
      **redirect back to the resource detail page** - the download link lives on that page.
      `# WARNING:` never redirect to a FileField URL from a verb; an unvalidated redirect target derived from
      stored data is an open-redirect hop, and the detail page is one extra click that removes the surface.

### Form (`KnowledgeResourceForm`) exclusions
- [ ] `Meta.fields = ["title", "resource_type", "category", "audience", "summary", "body", "tags",
      "is_featured", "owner", "document", "review_on"]`
- [ ] EXCLUDED: `tenant`, `number`, `status` (verb-driven), `usage_count`/`last_used_at` (the Use verb owns
      them), `created_by`, `created_at`/`updated_at`

---

## Backend build order (`apps/procurement/{models,forms,views,urls}/DocumentKnowledgeManagement/`)

> **One entity at a time - finish its four backend files AND its three templates before starting the next.**
> Do NOT touch any shared file here (`__init__.py`, `admin.py`, the seeder, `navigation.py`) - those all wait
> for Integrate.
>
> **Known forward reference:** `document/detail.html` links `procurement:pdocrevision_*` (step 2) and
> `revision/detail.html` links `procurement:pdocument_detail` (step 1). Neither page can render until both url
> modules exist; `manage.py check` at Integrate is the first point both are present. Expected - do not "fix" it
> by inlining a hard-coded path.

### Step 0 - sub-package inits
- [ ] `models/DocumentKnowledgeManagement/__init__.py` - **docstring only** (the 6.13/6.14/6.15 precedent:
      re-exports live in the app-level `models/__init__.py`)
- [ ] `forms/DocumentKnowledgeManagement/__init__.py` - docstring + a note that `ALLOWED_DOC_EXTENSIONS` /
      `MAX_UPLOAD_BYTES` are deliberately NOT re-exported (`forms/GoodsReceiptInspection/__init__.py:9` precedent)
- [ ] `views/DocumentKnowledgeManagement/__init__.py` - docstring only
- [ ] `urls/DocumentKnowledgeManagement/__init__.py` - concatenates the four entity `urlpatterns`

### Step 1 - `ProcurementDocument`
- [ ] `models/DocumentKnowledgeManagement/Documents.py` (model + `expiring_documents` +
      `run_document_reminders` + `run_document_reminders_audited`). `from apps.procurement.models._base import *`
- [ ] `forms/DocumentKnowledgeManagement/Documents.py` - `ProcurementDocumentForm(TenantUniqueMixin, TenantModelForm)`,
      `_reject_foreign(self, cleaned, ["supplier", "contract", "purchase_order", "sourcing_event"])`,
      `owner.queryset` scoped to tenant users
- [ ] `views/DocumentKnowledgeManagement/Documents.py`
- [ ] `urls/DocumentKnowledgeManagement/Documents.py`
- [ ] `templates/procurement/documentknowledge/document/list.html`
- [ ] `templates/procurement/documentknowledge/document/form.html`
- [ ] `templates/procurement/documentknowledge/document/detail.html`

### Step 2 - `ProcurementDocumentRevision`
- [ ] `models/DocumentKnowledgeManagement/Revisions.py` (model + `EXTRACT_MAX_CHARS` + `file_sha256` +
      `extract_document_text`)
- [ ] `forms/DocumentKnowledgeManagement/Revisions.py` - `ProcurementDocumentRevisionUploadForm`
- [ ] `views/DocumentKnowledgeManagement/Revisions.py`
- [ ] `urls/DocumentKnowledgeManagement/Revisions.py`
- [ ] `templates/procurement/documentknowledge/revision/list.html`
- [ ] `templates/procurement/documentknowledge/revision/form.html` (the upload page)
- [ ] `templates/procurement/documentknowledge/revision/detail.html`

### Step 3 - `ProcurementPolicy`
- [ ] `models/DocumentKnowledgeManagement/Policies.py`
- [ ] `forms/DocumentKnowledgeManagement/Policies.py`
- [ ] `views/DocumentKnowledgeManagement/Policies.py`
- [ ] `urls/DocumentKnowledgeManagement/Policies.py`
- [ ] `templates/procurement/documentknowledge/policy/list.html`
- [ ] `templates/procurement/documentknowledge/policy/form.html`
- [ ] `templates/procurement/documentknowledge/policy/detail.html`

### Step 4 - `KnowledgeResource`
- [ ] `models/DocumentKnowledgeManagement/KnowledgeResources.py`
- [ ] `forms/DocumentKnowledgeManagement/KnowledgeResources.py`
- [ ] `views/DocumentKnowledgeManagement/KnowledgeResources.py`
- [ ] `urls/DocumentKnowledgeManagement/KnowledgeResources.py`
- [ ] `templates/procurement/documentknowledge/knowledgeresource/list.html`
- [ ] `templates/procurement/documentknowledge/knowledgeresource/form.html`
- [ ] `templates/procurement/documentknowledge/knowledgeresource/detail.html`

### Package rules that apply to every file above
- [ ] Absolute imports only (`from apps.procurement.models import X`); entity modules pull the toolkit via
      `from apps.procurement.<layer>._base|_common import *`
- [ ] **A not-yet-wired sibling of THIS sub-module is imported from its entity MODULE**
      (`from apps.procurement.models.DocumentKnowledgeManagement.Documents import ProcurementDocument`), never
      from `apps.procurement.models` - the sub-package is not wired until Integrate and a package-level
      re-export would be a star-import cycle at URLconf import time (the 6.13/6.14/6.15 comment, verbatim)
- [ ] Every view `@login_required`; privileged writes (`pdocrevision_approve`, `pdocument_reindex`,
      `ppolicy_publish`) also `@tenant_admin_required`; every mutating verb `@require_POST`
- [ ] **Every queryset `filter(tenant=request.tenant)`** - never `.all()`
- [ ] `crud_*` helpers write the audit row automatically; every hand-rolled save path calls `write_audit_log`
      itself

---

## Views & routes - CONTEXT KEYS ARE THE CONTRACT (L7/L8: a name left unpinned renders blank at 200)

> Every list uses `crud_list` and therefore always provides `object_list`, `page_obj`, `q`. Every form template
> reads **only** `form`, `is_edit` and (edit only) `obj` plus the sub-module note constants - the 6.15
> `budgetmapping_create` / `crud_create` precedent; do NOT invent `page_title` / `submit_label` keys the
> siblings do not use. Every detail uses `crud_detail` and therefore provides `obj`.

### `ProcurementDocument` - `templates/procurement/documentknowledge/document/*.html`
- [ ] `pdocument_list` -> `procurement:pdocument_list`, `documentknowledge/document/list.html`
      - `_document_qs(request)` pre-narrows **before** `crud_list`: `?expiry=` allow-listed against
        `EXPIRY_FILTER_CHOICES` (unknown value -> filter skipped, never an empty register, L11) mapping to
        `expires_on__lt=today` / `expires_on__range` / `review_on__lte=today` / `retention_until__lt=today`;
        `?tag=` -> `tags__icontains` (stripped, ignored when blank)
      - `crud_list(search_fields=("number", "title", "description", "tags", "extracted_text"),
        filters=(("doc_type","doc_type",False), ("status","status",False),
        ("classification","classification",False), ("supplier","supplier_id",True), ("owner","owner_id",True)))`
      - `select_related("supplier", "owner", "contract", "purchase_order", "sourcing_event")`
      - **Context keys:** `object_list`, `page_obj`, `q`, `doc_type_choices`, `status_choices`,
        `classification_choices`, `expiry_choices`, `suppliers` (tenant Party queryset, supplier role, by name),
        `owners` (tenant active users, by username), `stats` (`{total, active, expiring, expired, unapproved}`
        - ONE `aggregate` with `Count(..., filter=Q(...))`, never 5 COUNTs), `search_note`
      - `SEARCH_NOTE` constant (module-level, shared with the detail page): "Search matches the title,
        description, tags and any text read from the approved file. Text is read from PDFs that carry a text
        layer and from plain-text uploads; a scanned image has no text to read."
- [ ] `pdocument_create` -> `crud_create(form_class=ProcurementDocumentForm, template=TEMPLATE_FORM,
      success_url="procurement:pdocument_list", extra_context={"search_note": SEARCH_NOTE})`
- [ ] `pdocument_detail` -> `documentknowledge/document/detail.html`, `crud_detail(select_related=("supplier",
      "contract", "purchase_order", "sourcing_event", "owner", "checked_out_by", "created_by"))`
      - **Context keys:** `obj`, `revisions` (`obj.revisions.select_related("uploaded_by","approved_by")[:50]`),
        `current_revision` (`obj.current_revision`), `policies` (`obj.policies.all()[:10]`),
        `knowledge_resources` (`obj.knowledge_resources.all()[:10]`), `can_upload` (bool: not archived and not
        locked by someone else), `lock_holder` (`obj.checked_out_by` or `None`), `search_note`
- [ ] `pdocument_edit` -> `crud_edit(model=ProcurementDocument, form_class=ProcurementDocumentForm,
      template=TEMPLATE_FORM, success_url="procurement:pdocument_list")` (context: `form`, `obj`, `is_edit`)
- [ ] `pdocument_delete` -> `crud_delete`, `@require_POST`, redirect `procurement:pdocument_list`
- [ ] Verbs (all `@require_POST`, all `write_audit_log`, all redirect to `procurement:pdocument_detail`):
      `pdocument_checkout`, `pdocument_release` (holder or tenant admin - force release),
      `pdocument_activate` (`draft`/`superseded`/`archived` -> `active`),
      `pdocument_supersede` (`active` -> `superseded`), `pdocument_archive` (any -> `archived`).
      Each rejects a disallowed transition with `messages.error` + redirect - never a 500, never a silent no-op.
- [ ] `pdocument_reindex` (`@require_POST` + `@tenant_admin_required`) -> re-runs `extract_document_text` over
      up to `REINDEX_ROW_CAP` documents whose `extracted_text` is empty and which have a current approved
      revision; `messages.success` with `{"indexed": n, "skipped": n}`; one audit row; redirect to the list
- [ ] `pdocument_run_reminders` (`@require_POST`) -> `run_document_reminders_audited`; `messages.success` with
      raised/skipped; redirect to the list

### `ProcurementDocumentRevision` - `templates/procurement/documentknowledge/revision/*.html`
- [ ] `pdocrevision_list` -> `procurement:pdocrevision_list`, `documentknowledge/revision/list.html`
      **This is the "Version Control" sidebar bullet's landing page** - every revision in the workspace,
      newest first.
      - `crud_list(search_fields=("document__number","document__title","change_note","sha256"),
        filters=(("document","document_id",True), ("approved","is_approved",False)))`,
        `select_related("document","uploaded_by","approved_by")`
      - **Context keys:** `object_list`, `page_obj`, `q`, `documents` (tenant `ProcurementDocument` queryset for
        the FK dropdown), `approval_choices` = `[("True","Approved"),("False","Pending approval")]`
        (**exactly the strings `crud_list` maps to booleans**), `stats`
        (`{total, approved, pending}`), `revision_note`
      - `REVISION_NOTE`: "A revision is immutable. Approving one makes it the document's current version;
        earlier approved revisions stay on the record as superseded. There is no edit."
- [ ] `pdocrevision_detail` -> `documentknowledge/revision/detail.html`
      - **Context keys:** `obj`, `document` (`obj.document`), `is_current` (`obj.is_current`), `revision_note`
- [ ] `pdocument_revision_upload` -> `documentknowledge/revision/form.html`, GET renders / POST creates
      - **Context keys:** `form`, `is_edit` (always `False`), `document`, `upload_note`
      - `UPLOAD_NOTE`: the allowed extensions (from `ALLOWED_DOC_EXTENSIONS`, rendered, not hard-coded twice),
        the 20 MB cap, and the honest line about text extraction. **Never the word "OCR".**
- [ ] `pdocrevision_approve` (`@require_POST` + `@tenant_admin_required`) - the rules pinned above
- [ ] `pdocrevision_delete` (`@require_POST`) - only unapproved and not current
- [ ] **No `pdocrevision_edit`** - documented exemption in the url module docstring

### `ProcurementPolicy` - `templates/procurement/documentknowledge/policy/*.html`
- [ ] `ppolicy_list` -> `procurement:ppolicy_list`
      - `crud_list(search_fields=("number","title","summary","body"),
        filters=(("policy_type","policy_type",False), ("status","status",False),
        ("org_unit","applies_to_id",True)))`, `select_related("applies_to","owner","document","threshold_currency")`
      - `?review=due` pre-narrow (`next_review_on__lte=today`) applied in `_policy_qs` before `crud_list`
      - **Context keys:** `object_list`, `page_obj`, `q`, `policy_type_choices`, `status_choices`, `org_units`
        (tenant OrgUnit queryset), `review_choices` = `[("due","Review overdue")]`, `stats`
        (`{total, published, draft, review_due}`), `advisory_note`
- [ ] `ppolicy_create` / `ppolicy_edit` -> `crud_create` / `crud_edit`, `extra_context={"advisory_note": ADVISORY_NOTE}`
- [ ] `ppolicy_detail` -> **Context keys:** `obj`, `advisory_note`, `supersedes` (`obj.previous_version`),
      `superseded_by_rows` (`obj.superseded_by.all()[:10]`), `is_review_due`
- [ ] `ppolicy_delete` (`@require_POST`), `ppolicy_publish`, `ppolicy_archive`

### `KnowledgeResource` - `templates/procurement/documentknowledge/knowledgeresource/*.html`
- [ ] `knowledgeresource_list` -> `procurement:knowledgeresource_list`
      - `crud_list(search_fields=("number","title","summary","body","tags"),
        filters=(("resource_type","resource_type",False), ("category","category",False),
        ("audience","audience",False), ("status","status",False), ("featured","is_featured",False)))`,
        `select_related("owner","document")`
      - **Context keys:** `object_list`, `page_obj`, `q`, `resource_type_choices`, `category_choices`,
        `audience_choices`, `status_choices`,
        `featured_choices` = `[("True","Featured only"),("False","Not featured")]`,
        `featured` (the "start here" shelf: `status="published", is_featured=True` capped at `FEATURED_CAP`,
        computed separately and **not** paginated), `stats` (`{total, published, featured, used}`), `library_note`
- [ ] `knowledgeresource_create` / `knowledgeresource_edit` -> `crud_create` / `crud_edit`,
      `extra_context={"library_note": LIBRARY_NOTE}`
- [ ] `knowledgeresource_detail` -> **Context keys:** `obj`, `library_note`, `document` (`obj.document`),
      `is_review_due`
- [ ] `knowledgeresource_delete` (`@require_POST`), `knowledgeresource_publish`, `knowledgeresource_archive`,
      `knowledgeresource_use`

### URL modules - first segments checked against the whole concatenated inventory in `urls/__init__.py`
- [ ] Four NEW first segments, none of which is an existing whole component: **`documents/`**,
      **`document-revisions/`**, **`procurement-policies/`**, **`knowledge/`**.
      (`templates/` is already claimed by 6.2 - that is why the library is `knowledge/`, not `templates/`.
      `contracts/`, `clauses/`, `milestones/` and `renewals/` are 6.8's.) This app registers no greedy
      `<str:…>` converter, so there is no cross-module shadowing surface.
- [ ] `urls/DocumentKnowledgeManagement/Documents.py` - **literals before `<int:pk>`**:
      `documents/` (`pdocument_list`), `documents/add/` (`pdocument_create`),
      `documents/reindex/` (`pdocument_reindex`), `documents/run-reminders/` (`pdocument_run_reminders`),
      then `documents/<int:pk>/` (`pdocument_detail`), `…/edit/`, `…/delete/`, `…/checkout/`, `…/release/`,
      `…/activate/`, `…/supersede/`, `…/archive/`,
      `documents/<int:pk>/revisions/add/` (`pdocument_revision_upload`)
- [ ] `urls/…/Revisions.py`: `document-revisions/` (`pdocrevision_list`), `document-revisions/<int:pk>/`
      (`pdocrevision_detail`), `…/approve/` (`pdocrevision_approve`), `…/delete/` (`pdocrevision_delete`)
- [ ] `urls/…/Policies.py`: `procurement-policies/` + `add/` + `<int:pk>/` + `edit/` + `delete/` + `publish/`
      + `archive/` (`ppolicy_*`)
- [ ] `urls/…/KnowledgeResources.py`: `knowledge/` + `add/` + `<int:pk>/` + `edit/` + `delete/` + `publish/`
      + `archive/` + `use/` (`knowledgeresource_*`)
- [ ] `urls/DocumentKnowledgeManagement/__init__.py` concatenates the four in the order Documents ->
      Revisions -> Policies -> KnowledgeResources, with the segment-inventory docstring

---

## Wire-up (Integrate phase ONLY - single writer, surgical `Edit`, never a full rewrite: L43)

- [ ] `apps/procurement/models/__init__.py` - append the re-export block **from the entity MODULES**
      (6.13/6.14/6.15 precedent, with the cycle comment):
      `ProcurementDocument`, `expiring_documents`, `run_document_reminders`, `run_document_reminders_audited`,
      `ProcurementDocumentRevision`, `extract_document_text`, `ProcurementPolicy`, `KnowledgeResource` -
      **and add every one of them to `__all__`**. (`EXTRACT_MAX_CHARS` and the `*_CHOICES` tuples are
      deliberately NOT hoisted - reachable as `ProcurementDocument.DOC_TYPE_CHOICES` etc., the 6.14/6.15 rule.)
- [ ] `apps/procurement/forms/__init__.py` - re-export `ProcurementDocumentForm`,
      `ProcurementDocumentRevisionUploadForm`, `ProcurementPolicyForm`, `KnowledgeResourceForm`
      (+ the "`MAX_UPLOAD_BYTES` is NOT re-exported" note already at line 82 covers this sub-module too)
- [ ] `apps/procurement/views/__init__.py` - re-export **all 30 view names** listed above (a missing one is an
      `AttributeError` at URLconf import, not a 404)
- [ ] `apps/procurement/urls/__init__.py` - `from .DocumentKnowledgeManagement import urlpatterns as
      _dkm_documentknowledge`, spliced **LAST** in `urlpatterns` (the 6.13/6.14/6.15 belt-and-braces posture),
      and the four new first segments added to the module docstring's inventory
- [ ] `apps/procurement/admin.py` - `@admin.register` for all four:
      `ProcurementDocument` (list_display number/title/doc_type/status/classification/supplier/expires_on/
      current_revision_no; list_filter status/doc_type/classification; search number/title/tags;
      readonly number/current_revision_no/extracted_text/checked_out_by/checked_out_at/created_by;
      raw_id_fields supplier/contract/purchase_order/sourcing_event),
      `ProcurementDocumentRevision` (readonly everything except `change_note`; raw_id `document`),
      `ProcurementPolicy`, `KnowledgeResource`
- [ ] `apps/core/navigation.py` - **exactly one new `LIVE_LINKS["6.19"]` block**, mapping the five NavERP.md
      bullets verbatim:
      ```
      "6.19": {
          "Central Document Repository":  "procurement:pdocument_list",
          "Version Control":              "procurement:pdocrevision_list",
          "Procurement Policy Library":   "procurement:ppolicy_list",
          "Best Practices & Templates":   "procurement:knowledgeresource_list",
          "Full-Text Search & Indexing":  "procurement:pdocument_list#search",
      },
      ```
      (`_safe_reverse` supports a `#fragment` / `?query` suffix - `apps/core/navigation.py:1838` - the 6.13
      `invoicevoucher_dashboard#discount` precedent. The register's filter-bar card must therefore carry
      `id="search"`.) **No sidebar key for the upload page or the verbs** - this dict maps bullets to pages.
- [ ] **No `config/settings.py` / `config/urls.py` change** - `apps/procurement` is long since installed and
      included. This is an EXTEND run, not a scaffold run.
- [ ] `makemigrations procurement` -> expect **`0026_procurementdocument_procurementdocumentrevision_and_more.py`**
      (latest on disk is `0025_remove_budgetmapping_...`). **Agree this number with any concurrent session
      before generating it (L43).** Review the generated file before committing - four tables, nine indexes,
      no changes to any other app.

---

## Seeder (`apps/procurement/management/commands/seed_procurement.py`)

- [ ] Add `_seed_document_knowledge(tenant)` and call it **LAST** in `handle()`, after `_seed_budget_cost(tenant)`
      - its documents link to the suppliers, contracts, orders and sourcing events every block above has created.
- [ ] Extend the module docstring and `Command.help` with the 6.19 line.
- [ ] Extend the `--flush` block, children first (and note that without these the `exists()` guards survive a
      flush): `ProcurementDocumentRevision` -> `KnowledgeResource` -> `ProcurementPolicy` ->
      `ProcurementDocument`. (`KnowledgeResource.document` / `ProcurementPolicy.document` are `SET_NULL`, so
      order is not load-bearing - children-first keeps the flush reading top-down like every block above.)
- [ ] Add the four models + `extract_document_text` to the `from apps.procurement.models import (...)` block.
- [ ] **Reuse only** - create no Party, no contract, no PO, no sourcing event, no OrgUnit, no Currency:
      first supplier `Party` (via `PartyRole`), first `scm.SupplierContract`, first `scm.PurchaseOrder`,
      first `procurement.SourcingEvent`, first non-root `OrgUnit`, first active `Currency`, workspace members.
      Skip with a `self.style.WARNING` line when no supplier Party exists (the SMOKETEST-tenant posture).
- [ ] **Idempotent, per block:** `if ProcurementDocument.objects.filter(tenant=tenant).exists(): … skipping`,
      and separately for policies and knowledge resources. Numbered models use the existence guard, never a
      bare `.create()` in a loop that could re-mint numbers.
- [ ] Documents (4): an **active warranty** (supplier + purchase_order, `expires_on = today + 45d`);
      an **expired certificate of insurance** (supplier + contract, `expires_on = today - 20d`) so the
      Expired filter and the reminder scan have an honest row; a **draft specification** (sourcing_event, no
      revision -> `current_revision_no = 0`) so the "no revision yet" empty state is real; an **archived
      correspondence pack** with `retention_until = today - 10d` so the Past-retention filter has a row.
- [ ] Revisions: 2 each on the two live documents, minted through `ContentFile` with a small **`.txt`** payload
      (a plain-text extension the extractor genuinely reads, so `extracted_text` is really populated and the
      search box is demonstrably working **without shipping a binary PDF**). r1 approved then superseded by an
      approved r2; the parent's `current_revision_no` and `extracted_text` set through the same code path the
      approve verb uses. `# WARNING:` the seeder writes real files under MEDIA_ROOT - deterministic filenames
      plus the `exists()` guard, so a second run cannot pile up `_XXXX`-suffixed duplicates.
- [ ] Policies (3): a **published** competitive-bidding rule (`threshold_amount=10000`,
      `threshold_basis="per_requisition"`, currency, `applies_to` a department, `published_at` stamped) whose
      `previous_version` is an **archived** v1.0 row, so the supersession chain renders; plus a **draft**
      sole-source policy with `next_review_on` in the past so the Review-overdue filter has a row.
- [ ] Knowledge resources (4): a **featured published RFP template** linked to a seeded `ProcurementDocument`;
      a bid-evaluation scorecard; a negotiation playbook with `usage_count=7` + `last_used_at`; a draft checklist.
- [ ] Print the usual per-tenant `SUCCESS` counts; the existing "log in as `admin_<slug>`" footer already covers
      the tenant warning.

---

## Templates (`templates/procurement/documentknowledge/<entity>/{list,detail,form}.html`)

Shape reference: `templates/procurement/budgetcost/costforecast/list.html` - copy its structure exactly.

- [ ] Every page `{% extends "base.html" %}` + a leading `{% comment %}` block naming **the view module and the
      complete context contract** (the 6.15 header idiom) - and nothing outside that contract is referenced.
- [ ] **Every list** = page-header + breadcrumb (`procurement:dashboard` › sub-module › entity) + `stat-grid` +
      a `<form method="get" class="filter-bar">` reflecting `request.GET` for **every** filter the view declares
      + a table with an **Actions column** (view eye / edit pencil / delete POST form with `{% csrf_token %}`
      and `onsubmit="return confirm(…)"`) + an `{% empty %}` empty-state with a "Clear filters" link +
      `{% include "partials/pagination.html" %}` (it guards `has_previous`/`has_next`, L9).
- [ ] **Filter comparison rules:** plain strings `{% if request.GET.status == val %}selected{% endif %}`;
      FK pks `{{ o.pk|stringformat:"d" }}` and compared the same way - **never `|slugify`**.
- [ ] **Badges use colour-named theme.css classes only** (`badge-green/red/amber/info/muted/slate`) via the
      models' `*_CSS` maps, with a `{{ obj.get_<field>_display }}` fallback. **`badge-success`/`badge-danger`
      do not exist (L33).**
- [ ] `document/list.html` - the register. Filter bar card carries `id="search"` (the sidebar's
      Full-Text Search bullet deep-links to it). Columns: number+title, type, classification badge, supplier,
      current revision (`r{{ obj.current_revision_no }}` or "none yet"), expiry with an
      `is_expired`/`is_expiring` badge, status badge, Actions. Page-actions: New document, Run reminders (POST),
      Re-index (POST). Prints `search_note` under the title - **no "OCR" anywhere.**
- [ ] `document/detail.html` - metadata panel; the four link FKs each rendered as a link to the owning module's
      page when set (`scm:*` / `procurement:*`), "—" when not; a **revision history table** (`revisions`) with
      the current one badged `badge-green` "Current", approved-but-older `badge-amber` "Superseded", unapproved
      `badge-muted` "Pending"; each row shows `change_note`, `uploaded_by`, `created_at`, `file_size`, a
      truncated `sha256`, the `extraction_note`, and a download link (plain `<a href="{{ r.file.url }}">` -
      **never an inline `<iframe>`/`<embed>` of a user-uploaded file**); an **Actions sidebar** with Edit,
      Upload revision (when `can_upload`), Check out / Release, Activate / Supersede / Archive, Delete
      (POST + confirm), Back to list; a lock banner naming `lock_holder` when checked out; the linked policies
      and knowledge resources.
- [ ] `revision/list.html` - the Version Control landing page; `approved` filter options are exactly the
      strings `True` / `False`.
- [ ] `revision/detail.html` - read-only; Approve (POST, admin only, hidden when `is_current` or approved),
      Delete (POST, only when unapproved and not current), Back to the parent document. States plainly that a
      revision is immutable and there is no edit.
- [ ] `revision/form.html` - the upload page; renders `upload_note`, the file input and `change_note` only.
      Form tag needs `enctype="multipart/form-data"` (**and so does `document/form.html`'s sibling if any file
      field is ever added there - it is not, today**).
- [ ] `policy/list.html` / `policy/detail.html` / `policy/form.html` - detail shows `body`, the threshold with
      its basis + currency, the supersession chain (`supersedes` / `superseded_by_rows`), the linked repository
      document, and prints `advisory_note` on all three. Actions: Publish (POST, admin), Archive (POST), Edit,
      Delete.
- [ ] `knowledgeresource/list.html` - a **featured shelf** rendered from `featured` above the table, then the
      filtered register. `knowledgeresource/detail.html` renders `body`, `usage_count`/`last_used_at`, the
      linked document's download link, and a "Use this resource" POST button. Both print `library_note`.
- [ ] Template-folder rule check: two levels (`documentknowledge/` then the entity folder), bare page
      filenames, **no flat `<entity>_<page>.html` anywhere**.

---

## Verify

- [ ] `python manage.py makemigrations procurement` -> one file, `0026_*`; read it before committing
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_procurement` **twice** - the second run prints "already present, skipping" for all
      three 6.19 blocks and creates no duplicate files under MEDIA_ROOT
- [ ] `python manage.py check` - clean
- [ ] `python manage.py makemigrations --check --dry-run` - "No changes detected"
- [ ] Throwaway `temp/` smoke script as **`admin_acme` / `password`**, asserting **content, not just status**
      (a mismatched context var returns 200 and renders blank, L8):
      - [ ] GET 200: `pdocument_list`, `pdocument_create`, `pdocument_detail`, `pdocument_edit`,
            `pdocrevision_list`, `pdocrevision_detail`, `pdocument_revision_upload`, `ppolicy_list`,
            `ppolicy_create`, `ppolicy_detail`, `ppolicy_edit`, `knowledgeresource_list`,
            `knowledgeresource_create`, `knowledgeresource_detail`, `knowledgeresource_edit`
      - [ ] POST 302: `pdocument_checkout`, `pdocument_release`, `pdocument_supersede`, `pdocument_activate`,
            `pdocument_archive`, `pdocument_reindex`, `pdocument_run_reminders`, `pdocrevision_approve`,
            `ppolicy_publish`, `ppolicy_archive`, `knowledgeresource_publish`, `knowledgeresource_archive`,
            `knowledgeresource_use`; every one of those on GET -> **405**
      - [ ] Content assertions: each page title present; a seeded `PDOC-`/`PPOL-`/`PKR-` number present on its
            register; the revision register shows `r1`/`r2`; the policy detail shows the threshold and the
            supersession row; the knowledge detail shows `usage_count`
      - [ ] **No `{#` and no `{% comment` leak** in any rendered body
      - [ ] Junk params on every list: `?status=nope`, `?supplier=abc`, `?supplier=0`,
            `?supplier=999999999999999999999`, `?expiry=zzz`, `?approved=maybe`, `?page=9999` -> still 200 and
            still shows rows (a junk value is skipped, never an empty register, L11)
      - [ ] `?page=2` on every list -> 200
      - [ ] **Cross-tenant IDOR -> 404** on every `<int:pk>` route for all four models, using a pk owned by
            another tenant (including `pdocrevision_approve`, which must check BOTH the revision's tenant and
            its document's tenant)
      - [ ] Revision-chain behaviour: approving r2 moves `current_revision_no` to 2 and copies
            `extracted_text`; re-approving r2 is a no-op; approving r1 afterwards is **refused**; deleting the
            current revision is **refused**; uploading while another user holds the lock is **refused**
      - [ ] Upload validation: a `.exe` is rejected by extension; an oversize file is rejected by
            `MAX_UPLOAD_BYTES` (20 MB, core's - not CatalogManagement's 2 MB)
      - [ ] `pdocument_run_reminders` twice -> the second run reports `skipped_open`, not a second alert
      - [ ] A non-admin tenant user is refused on `pdocrevision_approve` / `pdocument_reindex` / `ppolicy_publish`
- [ ] Sidebar: `6.19` shows **five Live bullets** under Module 6; every one resolves (no `NoReverseMatch`)
- [ ] Delete the `temp/` script before the review phase

---

## Close-out (the mandatory Module Creation Sequence, phases 4-7)

- [ ] Phase 4 - the six reviewers **one after another**, each appending to
      `.claude/tasks/review-procurement-6.19.md`: `code-reviewer` -> `explorer` -> `frontend-reviewer` ->
      `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`; then dedupe, sort
      Critical -> Important -> Minor, assign `C#`/`I#`/`M#` IDs, commit the file
- [ ] Phase 5 - one `code-fixer` agent burns the findings down in ID order, one commit per file; verify no
      finding is left `[ ] open` and `manage.py check` is clean
- [ ] Phase 6 - tests, serial: pin the test contract + `conftest.py`, then
      `test_docknowledge_models.py` -> `test_docknowledge_forms.py` -> `test_docknowledge_views.py` ->
      `test_docknowledge_security.py`, one at a time, each committed on its own; every test function
      `test_docknowledge_*` and every module helper `_docknowledge_*`; finish with one **full unfiltered**
      `apps/procurement` run, green (never `-k` filtered, L47)
- [ ] Phase 7 - update `.claude/skills/procurement/SKILL.md` (models, routes, templates, seeder rows, the
      revision-chain rules, the `LIVE_LINKS["6.19"]` block) and mark 6.19 complete in `README.md`; one commit each
- [ ] One file per commit throughout, PowerShell-safe (`;`, never `&&`); **never `git push`**

---

## Later passes / deferred (carried from the research so nothing is lost)

- **OCR of scanned PDFs, AI auto-tagging, clause detection, semantic / NL search** -> Module **13.5 / 13.6**.
  Needs OCR + ML infrastructure that does not exist. **The UI must never use the word "OCR".**
- **Elasticsearch / MySQL FULLTEXT relevance ranking** -> no search service, and a FULLTEXT index cannot exist
  under the SQLite test runner. `icontains` over `extracted_text` is the honest ceiling.
- **Folder hierarchy / virtual folders / metadata inheritance** -> **13.4 / 13.5**. `doc_type` + `tags` + the
  four object FKs give the same findability without a tree.
- **Version diff / redline, branching, merge-back** -> **13.2**. The chain stays linear.
- **Document-level permission matrices, watermarking, DRM, DLP, secure viewer** -> **13.7**. Tenant scoping +
  `@login_required` + the `classification` badge is this pass's honest level.
- **Automatic retention destruction, legal hold, WORM / PDF-A archival** -> **13.9 / 13.14** + a scheduler.
  6.19 stores `retention_until` and can *show* over-retention rows; it deletes nothing on a timer, and it never
  reclaims the file from MEDIA_ROOT.
- **E-mail notification of expiring documents** -> no mail worker (the 6.8 renewal scan has the same limit).
  Reminders land in `ProcurementAlert`; the run is a user-pressed verb.
- **Bulk / ZIP import and legacy migration** -> a second UX plus a zip-slip surface. 6.9's `CatalogUploadBatch`
  is the pattern when it is scheduled.
- **A `Tag` table with autocomplete and a controlled vocabulary** -> a fifth model; **13.5**.
- **File preview / thumbnails in the browser** -> inline rendering of user-uploaded files is a stored-XSS
  surface needing `Content-Disposition` / CSP work. Link out; do it deliberately later.
- **Requisition / RFQ / GRN document FKs** -> `scm.PurchaseRequisition`, `scm.RFQ`, `scm.GoodsReceiptNote` all
  exist and are one migration away; four link FKs this pass keeps the register's filters comprehensible.
- **Prevailing-terms panel per supplier** (Coupa) -> a computed panel on the supplier-filtered register (no
  table). Ship only if a later pass has room.

## Parked for a sibling sub-module (do NOT pull into 6.19)

- **Policy acknowledgement / sign-off ledger + attestation reporting** -> **6.17** (*Policy Management &
  Acknowledgment*). 6.19 ships `requires_acknowledgment` as the hook; 6.17 copies `hrm.PolicyAcknowledgment`'s
  shape (`policy` FK + `employee` FK + `status` + `acknowledged_at`, `unique_together (tenant, policy, employee)`)
  and FKs `procurement.ProcurementPolicy`.
- **Tamper-proof audit log of every document view/download** -> **6.17** (*Audit Trail & Logging*). 6.19 writes
  `core.AuditLog` rows for its own verbs only.
- **Supplier document requirements as a qualification gate** -> **6.16** / SCM 4.2 `SupplierProfile`. 6.19
  stores and expires the certificate; it does not decide whether the supplier is qualified.
- **Mandatory-attachment enforcement on requisition submit** (Precoro) -> **6.2 / 6.3**. Record it as a
  `ProcurementPolicy` row instead.
- **Vendor-facing document upload/download** -> **6.4** (`VendorPortalAccess` gates the portal). 6.19 ships the
  `supplier_visible` flag; 6.4 ships the page.
- **Clause library** -> **6.8** (`ContractClause`, built). **Executable requisition templates** -> **6.2**
  (`RequisitionTemplate`, built). **RFx questionnaires** -> **6.6** (built). **Contract obligations** -> **6.8**
  (`ContractMilestone`, built).

## Review notes

(filled in at the end)

---

## 6.18 Inventory & Warehouse Integration (Module 6: Procurement Management System, `procurement`)

Plan from `.claude/tasks/research-procurement-6.18.md` (614 lines, committed) — **2026-09-05**.
App EXISTS (6.1–6.15 built); this pass EXTENDS it. Backend package
`apps/procurement/{models,forms,views,urls}/InventoryWarehouseIntegration/`; templates
`templates/procurement/inventorywarehouse/`. Structural precedent: 6.15
`BudgetCostManagement/` across all four layers (config master + numbered document + derived
board = exactly this pass's shape).

**Scope is FROZEN: 3 entities / 5 model classes + 3 derived no-model pages.** Do not widen.
Optional research entity 4 `CountVarianceReview` is **DROPPED** — see Deferred.

### 6.18-A Concurrency gates (four sessions live on `apps/procurement` — read before touching anything shared)

- [ ] **Migration slot is `0028_*`.** `0025` is the newest on disk today. Queue: `0026`=6.16,
      `0027`=6.17, **`0028`=us (6.18)**, `0029`=6.19. **Do NOT run `makemigrations procurement`
      until `apps/procurement/migrations/0027_*.py` exists on disk.** If it does not, wait; if
      `0028` already exists when we get there, re-agree the slot with the peer session before
      generating (L43).
- [ ] **Never run `seed_procurement --flush`.** Plain idempotent `seed_procurement` only — a
      flush would delete the other three sessions' seeded rows.
- [ ] **Shared files are APPEND-ONLY via surgical `Edit`, never `Write`, never a full rewrite:**
      `apps/procurement/models/__init__.py`, `apps/procurement/forms/__init__.py`,
      `apps/procurement/views/__init__.py`, `apps/procurement/urls/__init__.py`,
      `apps/procurement/admin.py`,
      `apps/procurement/management/commands/seed_procurement.py` (our dispatch line goes
      **after** 6.17's), `apps/core/navigation.py` (**only** the `"6.18"` key), `README.md`.
- [ ] **Hands off `apps/procurement/tests/test_budgetcost_*.py`** (4 untracked files) — they
      belong to another session. Never `git add` them, never edit them, never include them in a
      commit (L45).
- [ ] One file per commit, PowerShell `;` separators, explicit paths, **never `git push`**.

### 6.18-B URL segments — FINAL LIST (send this to the peer sessions)

Collision check performed 2026-09-05 against the concatenated inventory in
`apps/procurement/urls/__init__.py:7-19` (63 existing first segments) — **all six are new whole
path components, zero collisions.** `receipt-bin-map/` is distinct from the existing
`receipt-tolerances/`, `receipt-discrepancies/`, `receipt-audit/` (Django matches components,
not string prefixes). Re-run the dump at Integrate time in case 6.16/6.17/6.19 land first.

```
stock-position/            -> procurement:stock_position        (derived, GET)
replenishment-policies/    -> procurement:replenishmentpolicy_*  (CRUD)
replenishment-runs/        -> procurement:replenishmentrun_*     (CRUD + verbs)
material-issues/           -> procurement:materialissue_*        (CRUD + verbs)
receipt-bin-map/           -> procurement:receipt_bin_map       (derived, GET)
count-accuracy/            -> procurement:count_accuracy        (derived, GET)
```

- [ ] Verify at Integrate: `grep -rhoE 'path\(\s*"[^"/]+' apps/procurement/urls/` → sort -u →
      confirm none of the six appears twice.
- [ ] **Urls docstring wording — do NOT copy the stock sentence.** "this app registers no greedy
      `<str:...>` converter anywhere" is **FALSE**: `contract-sign/<str:token>/` exists at
      `apps/procurement/urls/ContractsManagement/Contracts.py:16`. Use the accurate form:
      *"No route in this app uses a converter in its FIRST path component — every first segment
      is a literal — so nothing can shadow across modules."* (Verified: `grep 'path("<'` across
      `apps/procurement/urls/` returns zero matches.)

### 6.18-C Spine verification (grep-confirmed 2026-09-05 — every FK below targets a real entity)

| Entity | Verified at | Used by 6.18 for |
|---|---|---|
| `scm.Item` | `InventoryManagement/Items.py:73` (`sku:92`, `name:93`, `uom:96` **nullable**, `standard_cost:101`, `average_cost:105` editable=False) | policy/suggestion/issue-line FK |
| `scm.Location` | `InventoryManagement/Locations.py:14` (`LOCATION_TYPES:17-23` incl. `bin`, `path()`, `capacity:41`, `abc_class:46` **lowercase a/b/c**) | **IS the bin master — no new Bin/Zone model** |
| `scm.StockMove` | `InventoryManagement/StockMoves.py:13` (signed `quantity:43`, `reference:47`, index `(tenant, reference)` `:60`) | READ ONLY — on-hand aggregate + receipt→bin join |
| `scm.StockAdjustment` / `Line` | `InventoryManagement/StockAdjustments.py:11` / `:65` (`REASON_CHOICES:23`, `status:35`, `quantity_delta:72`, `unit_cost:76`, `value_impact():48`, `clean()` requires notes when reason=`other` `:58`) | `MaterialIssue.post()` mints a **draft** one |
| `scm.ReorderRule` | `InventoryManagement/ReorderRules.py:26` (`reorder_point:43`, `safety_stock:46`, `reorder_quantity:48`, `lead_time_days:61`, `avg_daily_demand:76`, `abc_class:78` **uppercase A/B/C**, `on_hand_map():107` staticmethod, `is_below_point():133`, `suggested_quantity():136`) | the run reads it; **never re-declare its columns** |
| `scm.PurchaseRequisition` / `Line` | `ProcurementManagement/PurchaseRequisitions.py:14` / `:151` (`title:44`, `requester:45`, `org_unit:47`, `budget:50`, `currency:53`, `required_by:55`, `status:56`, `recalc_totals():89`; line `item_description:155`, `sku_hint:156`, `uom_hint:158`, `quantity:159`, `estimated_unit_price:161`, `gl_account:164`) | `ReplenishmentRun.release()` WRITES these |
| `scm.PurchaseOrder` / `Line` | `ProcurementManagement/PurchaseOrders.py:15` / `:172` (`RECEIVABLE_STATUSES:34`, `sku_hint:177`) | on-order derivation |
| `scm.GoodsReceiptNote` / `Line` | `ProcurementManagement/GoodsReceiptNotes.py:15` / `:166` (`location:40` staging, `status:44`, `receipt_date:43`) | receipt-bin-map anchor |
| `scm.PutawayTask` | `WarehouseManagement/PutawayTasks.py:16` (`goods_receipt:38`, `from_location:44`, `to_location:47`, `quantity:49`, `status:52`) | receipt-bin-map onward hop |
| `scm.CycleCountTask` / `Line` | `WarehouseManagement/CycleCountTasks.py:16` / `:90` (`status:41`, `scheduled_date:39`, `adjustment:48`; line `expected_quantity:98` editable=False, `counted_quantity:100` nullable, `variance:108`, `has_variance:115`) | count-accuracy source |
| `scm.SalesOrderAllocation` | `OrderManagement/SalesOrderAllocations.py:15` (`ACTIVE_STATUSES`) | availability formula |
| `scm.LotSerial` | `InventoryManagement/LotSerials.py:5` | optional issue-line FK |
| `inventory.InventoryReservation` | `InventoryTrackingControl/InventoryReservations.py:37` (`ACTIVE_STATUSES:56`, `item:72`, `location:75`, `quantity`) | availability + optional issue link |
| `inventory.StockStatus` | `InventoryTrackingControl/StockStatuses.py:18` | non-sellable held qty |
| `inventory.CountProgram` | `StocktakingCycleCounting/CountPrograms.py:18` (`generate_tasks():85-125` — **the bridge pattern we copy**) | count-accuracy schedule column |
| `inventory.BinCapacity` | `WarehousingBinManagement/BinCapacities.py:26` | receipt-bin-map fullness badge |
| `core.Party` / `core.OrgUnit` / `core.Tenant` | `core/models/Party.py:5` / `OrgUnit.py:5` / `Tenant.py:5` | vendor (a `PartyRole`), cost dimension, tenancy |
| `accounting.Budget` / `GLAccount` | reached by string FK from `PurchaseRequisitions.py:50,164` | requisition defaults, expense account |
| 6.15 `REQUESTED_PR_STATUSES` / `COMMITTED_PR_STATUSES` | `apps/procurement/models/BudgetCostManagement/BudgetMappings.py:45-49` | open-requisition supply column |

- [ ] **`scm.Item`, `scm.Location`, `scm.SalesOrder*` all EXIST** (SCM 4.1/4.3/4.5 shipped) — no
      stand-in needed anywhere in this plan. Confirm again before writing the first model file.
- [ ] **Never re-declare anything owned by `scm` or `inventory` (L36).** Every cross-app FK is a
      **string** reference. No `Bin`/`Zone`/`Aisle`/`Rack`. No second on-hand column. No second
      reorder point / safety stock / lead time. No second requisition or PO model. No second
      count task / count schedule / blind-count mechanism. No second reservation or stock
      classification. No `accounting.JournalEntry` posting (L29).
- [ ] **NOTHING in `apps/procurement` writes `scm.StockMove`** — verified: only `apps/scm/views/`
      writes the ledger in production code.

### 6.18-D Models — `apps/procurement/models/InventoryWarehouseIntegration/`

All inherit `apps.procurement.models._base.TenantOwned` (`:44`) / `TenantNumbered` (`:57`) via
`from apps.procurement.models._base import *`. Every model gets a `tenant` FK (from the base),
a `clean()` with **cross-tenant rejection on every FK**, and colour-named badge maps only
(`badge-green/red/amber/info/muted/slate` — `-success/-warning/-danger` do NOT exist, L33).

#### 1. `ReplenishmentPolicy` — `Policies.py` — **no number prefix** (`TenantOwned`, plain config)

The procurement-side overlay on `scm.ReorderRule`: **who** to buy from, **how much** to round to,
**what defaults** the generated requisition carries. Unnumbered on the
`ReceiptTolerancePolicy` / `SpendClassificationRule` / `inventory.PutawayRule` precedent.

- [ ] FKs (all by string): `item` → `scm.Item` **PROTECT** · `location` → `scm.Location`
      SET_NULL null/blank (**null = "any location"**) · `preferred_vendor` → `core.Party`
      SET_NULL null/blank · `default_org_unit` → `core.OrgUnit` SET_NULL ·
      `default_budget` → `accounting.Budget` SET_NULL · `default_gl_account` →
      `accounting.GLAccount` SET_NULL. Distinct `related_name`s prefixed
      `procurement_replenishment_`.
- [ ] `SOURCE_METHOD_CHOICES = [("buy","Buy"),("transfer","Transfer"),("manufacture","Manufacture")]`
      default `buy` — *driver: Odoo "Preferred Route" / Oracle+D365 supply type / Cin7
      purchase-transfer-assemble.* **Only `buy` generates a requisition this pass**; `transfer`
      and `manufacture` render a link-out (`scm:stocktransfer_create`) and are skipped by the run.
- [ ] `TRIGGER_MODE_CHOICES = [("review","Review then release"),("auto","Automatic")]` default
      **`review`** — *driver: Odoo Trigger Auto|Manual, D365 coverage code Manual; the human gate
      on money is universal.* Mirrors `ReorderRule.apply_computed()`'s "calculate proposes, a
      person accepts" contract (`ReorderRules.py:319-322`).
- [ ] `target_level` Decimal(14,2) **null/blank** — *driver: NetSuite Preferred Stock Level,
      Precoro "Reorder To", Odoo Max Quantity.* Order-up-to **override**; null ⇒ fall back to
      `rule.reorder_point + rule.safety_stock`. Documented as an override, never a copy.
- [ ] `order_multiple` Decimal(14,2) null/blank — *driver: Odoo "Multiple Quantity".*
- [ ] `min_order_qty` Decimal(14,2) null/blank — *driver: NetSuite item-vendor minimums, Cin7
      per-supplier reorder qty.*
- [ ] `max_order_qty` Decimal(14,2) null/blank.
- [ ] `include_on_order` Bool **default True** — *driver: Oracle min-max plans on on-hand **plus
      on-order**; Precoro's On Order column exists to stop double-ordering.* Closes the real
      behavioural gap: `ReorderRule.is_below_point()` (`:133`) tests on-hand ONLY.
- [ ] `include_open_requisitions` Bool default True — *driver: SAP MD04 counts PRs as supply.*
- [ ] `lead_time_days_override` PositiveIntegerField null/blank,
      `MaxValueValidator(3650)` — *driver: Cin7 per-supplier lead time*; else
      `rule.lead_time_days`.
- [ ] `is_active` Bool default True · `notes` TextField blank.
- [ ] `Meta`: `ordering = ["item__sku", "location__code", "id"]`;
      `unique_together = ("tenant", "item", "location")` (same grain as
      `ReorderRule.Meta:90`); indexes `(tenant, is_active, item)` `prc_rpol_tnt_active_idx` and
      `(tenant, item, location)` `prc_rpol_tnt_item_loc_idx`.
- [ ] **Nullable-unique honesty:** `location` is nullable, so the DB `unique_together` does NOT
      stop a second catch-all row (NULLs compare distinct). `clean()` adds an explicit probe:
      `filter(tenant, item, location__isnull=True).exclude(pk=self.pk).exists()` → reject.
      Say so in the docstring (the `BudgetMapping` "a nullable-column unique would not be
      portable anyway" precedent, `BudgetMappings.py:14-17`).
- [ ] `clean()` also: cross-tenant rejection on **all six** FKs; `max_order_qty >= min_order_qty`
      when both set; `target_level > 0` when set; `preferred_vendor` must hold a
      `supplier`/`vendor` `PartyRole` (the 6.5/6.8 `_supplier_parties` rule).
- [ ] `round_quantity(raw)` — the **single** place rounding happens: floor at `min_order_qty`,
      round UP to the next `order_multiple`, cap at `max_order_qty`, never negative. The run
      calls it; nothing else re-implements it.
- [ ] `@classmethod resolve(tenant, item, location)` — exact `(item, location)` row wins, then
      the `(item, location=None)` catch-all, else `None`. Specificity-first, the
      `BudgetMapping.resolve()` shape (`BudgetMappings.py:186-215`).
- [ ] Badge props: `status_css`/`status_label` (is_active), `SOURCE_CSS`, `TRIGGER_CSS` — all
      colour-named.
- [ ] **Form excludes:** `tenant`, `created_at`, `updated_at`.

#### 2. `ReplenishmentRun` `[RPL-]` + `ReplenishmentSuggestion` — `Runs.py` (ONE entity file)

The batch proposal Oracle/Odoo/Cin7/D365 all produce, and the gap in NavERP:
`scm:reorder_alerts` and `inventory:reorderdraft` both compute-and-forget — **nothing in the repo
persists a proposal.**

**`ReplenishmentRun(TenantNumbered)`, `NUMBER_PREFIX = "RPL"`**

- [ ] FKs: `location` → `scm.Location` SET_NULL null/blank (**null = whole network**) ·
      `generated_by` → `settings.AUTH_USER_MODEL` SET_NULL null/blank **`editable=False`**.
- [ ] `run_date` DateField · `trigger` CHOICES `manual`|`scheduled` default `manual`
      (*driver: Oracle schedules the min-max report, NetSuite runs AIM weekly, D365 schedules
      master planning* — the **column ships, the cron does not**, same posture as
      `CountProgram.is_due()`).
- [ ] `status` CHOICES `draft`|`proposed`|`released`|`cancelled` default `draft`;
      `EDITABLE_STATUSES = ("draft",)`; `RELEASABLE_STATUSES = ("proposed",)`.
- [ ] `abc_class_filter` CharField(max_length=1) blank, choices `A`/`B`/`C` —
      *driver: D365 plans per ABC group.* **GOTCHA: filters `ReorderRule.abc_class`, which is
      UPPERCASE `A/B/C` (`ReorderRules.py:36`) — NOT `Location.abc_class`, which is lowercase
      `a/b/c` (`Locations.py:25-29`).** Put that sentence in the field's `help_text`.
- [ ] `notes` TextField blank · `generated_at` / `released_at` DateTimeField null/blank
      **`editable=False`** (L22).
- [ ] `Meta`: `ordering = ["-run_date", "-id"]`; `unique_together = ("tenant", "number")`;
      indexes `(tenant, status)` `prc_rpl_tnt_status_idx`, `(tenant, run_date)`
      `prc_rpl_tnt_date_idx`.
- [ ] `MAX_SUGGESTIONS = 500` — hard cap; when hit, stamp a truncation marker on `notes` and
      surface `truncated` on the detail page. An unbounded batch is not a feature.
- [ ] `generate(user)` — **grouped queries ONLY, never a per-row aggregate** (the perf rule
      `StockLevels.py:10-11` states outright):
      - [ ] `transaction.atomic()` + `select_for_update()` on the run row; refuse unless status
            in `("draft", "proposed")`; **delete this run's existing lines first** so re-generate
            is idempotent.
      - [ ] Q1 rules: `ReorderRule.objects.filter(tenant, is_active=True)` (+ `location` when set,
            + `abc_class` when set) `.select_related("item", "item__uom", "location")`.
      - [ ] Q2 on-hand: `ReorderRule.on_hand_map(tenant, rules)` (`ReorderRules.py:107`) — ONE
            grouped `StockMove` query, `{(item_id, location_id): qty}`.
      - [ ] Q3 allocations: `SalesOrderAllocation` `ACTIVE_STATUSES`, `.values(iid=F(...), loc=F(...))
            .annotate(s=Sum("quantity"))` — both pair keys ALIASED (the field names collide,
            `StockLevels.py:93-97`).
      - [ ] Q4 reservations: `inventory.InventoryReservation` `ACTIVE_STATUSES` grouped by
            `(item_id, location_id)`.
      - [ ] Q5 non-sellable: `inventory.StockStatus` `.exclude(status="active")` grouped by
            `(item_id, location_id)`.
      - [ ] Q6+Q7 on-order: the `_on_order_map()` **two-query** shape (`StockLevels.py:37-67`)
            mirrored **LOCALLY** in this module — ordered PO lines on `RECEIVABLE_STATUSES` minus
            accepted `GoodsReceiptLine` (cancelled GRNs excluded), keyed by exact-string
            `sku_hint` ↔ `Item.sku`, floored at zero. **Two queries, not one** — a single
            annotation fans out and multiplies `ordered` by the receipt count. Peer apps do not
            import each other's internals (the `resolve_line_item` precedent,
            `ReceiptTolerances.py:398-405`).
      - [ ] Q8 open requisitions: ONE grouped query over `scm.PurchaseRequisitionLine` where
            `requisition__status__in = REQUESTED_PR_STATUSES + COMMITTED_PR_STATUSES` (imported
            from `apps.procurement.models.BudgetCostManagement.BudgetMappings`), keyed by
            `sku_hint`.
      - [ ] Q9 policies: ONE query over `ReplenishmentPolicy` for the tenant → dict keyed
            `(item_id, location_id)` and `(item_id, None)`.
      - [ ] Then **pure Python per rule** — no further DB hits:
            `supply = on_hand + (on_order if policy.include_on_order else 0) + (open_req if
            policy.include_open_requisitions else 0)`; skip when `supply > reorder_point`; skip
            when `policy.source_method != "buy"`;
            `target = policy.target_level or (reorder_point + safety_stock)`;
            `raw = target - supply`; `suggested = policy.round_quantity(raw)`; skip when
            `suggested <= 0`.
      - [ ] `bulk_create` the suggestion rows; set `generated_at = timezone.now()`,
            `generated_by = user`, `status = "proposed"`;
            `write_audit_log(user, self, "generate", {"lines": n})`.
- [ ] `release(user)` — *driver: NavERP.md's literal wording "generation of **requisitions**";
      Oracle generates requisitions, not POs, so 6.3 approval routing / 6.15 budget check /
      6.10 `generate_po_from_requisition` all still run.* **NOT the `inventory:reorderdraft`
      draft-PO path.**
      - [ ] `transaction.atomic()` + `select_for_update()` on the run so a double-clicked Release
            cannot raise two sets of PRs; refuse unless `status == "proposed"`; refuse when no
            line is `accepted`.
      - [ ] Group `decision="accepted"` suggestions by `vendor_id` (`None` → one "unassigned"
            requisition). Per group: one `scm.PurchaseRequisition(tenant, title=f"Replenishment
            {self.number} — {vendor or 'Unassigned'}", requester=user,
            org_unit=<policy.default_org_unit>, budget=<policy.default_budget>,
            required_by=run_date + max(lead_time_days), status="draft", justification=<marker>)`.
            **Created as `draft`, never auto-approved.**
      - [ ] Per line: `PurchaseRequisitionLine(item_description=item.name, sku_hint=item.sku,
            uom_hint=item.uom.code if item.uom_id else "", quantity=suggested_qty,
            estimated_unit_price=unit_cost, gl_account=<policy.default_gl_account>)`.
            **`Item.uom` is nullable (`Items.py:96`) — guard it.**
      - [ ] `requisition.recalc_totals()` (`PurchaseRequisitions.py:89`); stamp
            `suggestion.requisition`; set `released_at`, `status="released"`;
            `write_audit_log(user, self, "release", {"requisitions": [...numbers]})`.
- [ ] `cancel(user)` — allowed from `draft`/`proposed` only; refused once `released`.
- [ ] Derived (properties, never stored): `line_count`, `accepted_count`, `total_value`,
      `is_editable`, `status_css`.

**`ReplenishmentSuggestion(models.Model)`** — child, `related_name="lines"`

- [ ] FKs: `run` → `ReplenishmentRun` CASCADE `related_name="lines"` · `item` → `scm.Item`
      PROTECT · `location` → `scm.Location` PROTECT · `reorder_rule` → `scm.ReorderRule`
      SET_NULL null/blank · `policy` → `ReplenishmentPolicy` SET_NULL null/blank · `vendor` →
      `core.Party` SET_NULL null/blank (policy's preferred vendor, **overridable per line**) ·
      `requisition` → `scm.PurchaseRequisition` SET_NULL null/blank **`editable=False`**
      (stamped on release).
- [ ] **Every snapshot `editable=False`** — the `CycleCountTaskLine.expected_quantity` precedent
      (`CycleCountTasks.py:97-98`), so the record still explains itself after stock moves:
      `on_hand_qty`, `allocated_qty`, `on_order_qty`, `open_requisition_qty`, `available_qty`,
      `reorder_point_snapshot`, `target_level_snapshot`, `raw_suggested_qty`, `suggested_qty`
      (all Decimal(16,4)), `unit_cost` Decimal(14,4) (from `Item.standard_cost`),
      `lead_time_days` PositiveIntegerField.
      *Driver: Oracle min-max report output, D365, Odoo replenishment dashboard.*
- [ ] `decision` CHOICES `pending`|`accepted`|`snoozed`|`dismissed` default `pending` —
      *driver: Odoo's explicit Snooze, D365 firming, Cin7 line-dropping.* **The only
      buyer-editable field family on this model.**
- [ ] `snooze_until` DateField null/blank · `decision_note` CharField(255) blank.
- [ ] `line_value` **property** (`suggested_qty × unit_cost`) — derived, **never stored**.
- [ ] `Meta`: `ordering = ["item__sku", "id"]`; index `(run, decision)` `prc_rsg_run_dec_idx`.
- [ ] `clean()`: cross-tenant rejection on `item`/`location`/`vendor`/`policy`/`reorder_rule`
      against `run.tenant_id`; `snooze_until` required and must be in the future when
      `decision == "snoozed"`.
- [ ] **Form excludes (run form):** `tenant`, `number`, `status`, `generated_by`, `generated_at`,
      `released_at`, `created_at`, `updated_at`.
      **Form fields (line decision form):** `decision`, `snooze_until`, `vendor`,
      `decision_note` — **every snapshot column is excluded**, as is `requisition`.

#### 3. `MaterialIssue` `[MIS-]` + `MaterialIssueLine` — `MaterialIssues.py` (ONE entity file)

SAP's 201/261 goods issue and Coupa/Precoro's inventory consumption, **plus the return-to-stock
mirror in the same document** via `movement_type` — *driver: Precoro reverses a completed
consumption into stock transfers; SAP's 202/262 reversal pair.* **There is no separate return
document.**

- [ ] **THE BRIDGE (non-negotiable):** `post()` mints a **draft `scm.StockAdjustment` + lines**
      and stores it on `adjustment` (`editable=False`). **`apps/procurement` writes ZERO
      `StockMove` rows** — SCM's own post action writes the moves. This is exactly
      `CountProgram.generate_tasks()` (`apps/inventory/models/StocktakingCycleCounting/
      CountPrograms.py:85-125`): mint the spine document, stamp a provenance marker, re-read
      `select_for_update()`, reuse rather than double-mint. Cite that file:line in the model
      docstring.
- [ ] **Reason-code mapping (pinned):** `StockAdjustment.reason = "other"` for BOTH directions —
      `write_off` would mean the stock was destroyed and `found` that it appeared from nowhere;
      neither is true of an internal consumption. Direction is carried by the **sign** of
      `quantity_delta`. `StockAdjustment.clean()` (`StockAdjustments.py:58`) requires notes when
      reason is `other`, and we always stamp the marker, so it validates:
      `f"Via material issue {self.number} ({self.get_movement_type_display()}) · {self.get_purpose_display()}"`.

**`MaterialIssue(TenantNumbered)`, `NUMBER_PREFIX = "MIS"`**

- [ ] FKs: `location` → `scm.Location` **PROTECT** (issue FROM / return TO) · `org_unit` →
      `core.OrgUnit` SET_NULL null/blank (*driver: SAP 201 requires a cost centre*) ·
      `gl_account` → `accounting.GLAccount` SET_NULL null/blank (header default expense account)
      · `requested_by` → `AUTH_USER_MODEL` SET_NULL null/blank · `issued_by` →
      `AUTH_USER_MODEL` SET_NULL null/blank **`editable=False`** (stamped at post) ·
      `adjustment` → `scm.StockAdjustment` SET_NULL null/blank **`editable=False`**
      (the `CycleCountTask.adjustment:48` provenance precedent) · `reservation` →
      `inventory.InventoryReservation` SET_NULL null/blank (*driver: SAP MB21 reservation feeds
      the MB1A issue* — **link out, never re-declare**).
- [ ] `movement_type` CHOICES `issue`|`return` default `issue`.
- [ ] `purpose` CHOICES `cost_centre`|`project`|`work_order`|`maintenance`|`sample`|`other`
      default `cost_centre` — *driver: SAP's 201 (cost centre) / 261 (order) split, generalised.*
- [ ] `reference` CharField(64) blank — free text project/job/WO number. **NO FK to
      `scm.WorkOrder`** — that is 4.8's manufacturing object and a procurement issue is not a
      production draw (which is why `StockMove` has separate `consumption`/`maintenance` types,
      `StockMoves.py:21-35`). Say so in the `help_text`.
- [ ] `issue_date` DateField · `status` CHOICES `draft`|`submitted`|`posted`|`cancelled` default
      `draft`; `EDITABLE_STATUSES = ("draft",)`; `POSTABLE_STATUSES = ("draft", "submitted")`;
      `CANCELLABLE_STATUSES = ("draft", "submitted")`.
- [ ] `posted_at` / `cancelled_at` DateTimeField null/blank **`editable=False`** (L22) ·
      `notes` TextField blank.
- [ ] `Meta`: `ordering = ["-issue_date", "-id"]`; `unique_together = ("tenant", "number")`;
      indexes `(tenant, status)` `prc_mis_tnt_status_idx`, `(tenant, issue_date)`
      `prc_mis_tnt_date_idx`, `(tenant, movement_type)` `prc_mis_tnt_mvt_idx`.
- [ ] `total_value` — **one aggregate** `Σ quantity × unit_cost` across lines (the
      `StockAdjustment.value_impact():48` shape), shown beside the minted adjustment's own
      `value_impact()`.
- [ ] `on_hand_at_location(item_ids)` — **LOCAL** mirror of `_insufficient_stock()`'s shape
      (`apps/scm/views/_helpers.py:157`): ONE grouped `Sum(StockMove.quantity)` over
      `(tenant, location, item_id__in)`. **Do NOT import `apps.scm.views._helpers`.**
- [ ] `post(user)`:
      - [ ] `transaction.atomic()` + `select_for_update()` on the header; refuse unless status in
            `POSTABLE_STATUSES`; refuse when the document has no lines.
      - [ ] **Availability guard** — for `movement_type == "issue"` only: one grouped query for
            all line items at this location; reject with a per-item `ValidationError` when any
            line exceeds on-hand. *Driver: SAP/D365/Fishbowl all refuse to issue more than the
            location holds.*
      - [ ] Duplicate protection: if `self.adjustment_id` is already set, **reuse** it instead of
            minting a second (the `generate_tasks()` "existing/created" branch).
      - [ ] Mint `scm.StockAdjustment(tenant_id, location, reason="other",
            adjustment_date=issue_date, status="draft", notes=<marker>)` + one
            `StockAdjustmentLine(item, lot_serial, quantity_delta=−qty (issue) / +qty (return),
            unit_cost=line.unit_cost)` per line.
      - [ ] Stamp `adjustment`, `status="posted"`, `posted_at`, `issued_by`;
            `write_audit_log(user, self, "post", {"adjustment": adj.number})`.
      - [ ] The detail page states plainly: **the adjustment is DRAFT; stock changes only when
            SCM posts it** — with a link to `scm:stockadjustment_detail`.
- [ ] `submit(user)` (draft → submitted) and `cancel(user)`: **cancellation after posting is
      REFUSED** — correct it with the mirror document (a `return` against the same location),
      never by deleting. *Driver: the repo's compensating-move law, `StockMoves.py:5-7`.*
- [ ] `clean()`: cross-tenant on all seven FKs; `purpose == "other"` requires `notes` (the
      `StockAdjustment.clean()` precedent); a `movement_type == "return"` with `reservation` set
      is rejected (a reservation is consumed by an issue, not by a return);
      `reservation.item`/`location` must be consistent with the header location when set.
- [ ] Badge maps `STATUS_CSS` (`draft`→muted, `submitted`→amber, `posted`→green,
      `cancelled`→slate) and `MOVEMENT_CSS` (`issue`→info, `return`→green) — colour-named only.
- [ ] **Form excludes:** `tenant`, `number`, `status`, `adjustment`, `issued_by`, `posted_at`,
      `cancelled_at`, `created_at`, `updated_at`.

**`MaterialIssueLine(models.Model)`** — child, `related_name="lines"`

- [ ] FKs: `issue` → `MaterialIssue` CASCADE `related_name="lines"` · `item` → `scm.Item`
      PROTECT · `lot_serial` → `scm.LotSerial` SET_NULL null/blank (*driver: serial/lot capture
      at issue — optional field*) · `gl_account` → `accounting.GLAccount` SET_NULL null/blank
      (per-line override of the header default).
- [ ] `quantity` Decimal(16,4) `MinValueValidator(Decimal("0.0001"))` (the
      `PutawayTask.quantity:49` shape).
- [ ] `unit_cost` Decimal(14,4) default 0 **`editable=False`** — snapshot of
      `Item.average_cost` (`Items.py:105`), stamped in `save()` when unset.
      *Driver: value the issue at moving-average cost; `StockAdjustment.value_impact()` already
      totals it.*
- [ ] `notes` CharField(255) blank · `line_value` **property** (derived, never stored).
- [ ] `Meta`: `ordering = ["item__sku", "id"]`.
- [ ] `clean()`: cross-tenant on `item`/`lot_serial`/`gl_account` against `issue.tenant_id`.
- [ ] **Line form fields:** `item`, `lot_serial`, `quantity`, `gl_account`, `notes` —
      **`unit_cost` excluded** (it is a snapshot, not an input).

### 6.18-E Forms — `apps/procurement/forms/InventoryWarehouseIntegration/`

`from apps.procurement.forms._common import *` plus `TenantUniqueMixin` and `_reject_foreign`
explicitly. `TenantUniqueMixin` comes **FIRST** in the MRO so `instance.tenant` is stamped before
`full_clean()` — otherwise every CREATE is falsely rejected as cross-tenant
(`forms/BudgetCostManagement/BudgetMappings.py:21-27`). Import each model from its **entity
module** (`apps.procurement.models.InventoryWarehouseIntegration.<Entity>`), **never** from
`apps.procurement.models`, until the Integrator wires the re-exports — a package-level re-export
is a star-import cycle at URLconf import time.

- [ ] `Policies.py` → `ReplenishmentPolicyForm`. Narrow every dropdown in `__init__(tenant=...)`
      (`item` active only by sku, `location` by code, `preferred_vendor` = supplier/vendor
      `PartyRole` only, `default_org_unit`/`default_budget`/`default_gl_account` tenant-scoped
      active); `empty_label = "- any -"` on the nullable ones; **`tenant is None` ⇒ every
      queryset `.none()`**; `clean()` calls `_reject_foreign` on all six FKs.
- [ ] `Runs.py` → `ReplenishmentRunForm` (`location`, `run_date`, `trigger`, `abc_class_filter`,
      `notes`) and `ReplenishmentSuggestionDecisionForm` (`decision`, `snooze_until`, `vendor`,
      `decision_note`) — the decision form validates `snooze_until` presence/future-ness and
      re-checks `vendor` tenancy.
- [ ] `MaterialIssues.py` → `MaterialIssueForm` (`location`, `movement_type`, `purpose`,
      `reference`, `issue_date`, `org_unit`, `gl_account`, `requested_by`, `reservation`,
      `notes`) and `MaterialIssueLineForm` (`item`, `lot_serial`, `quantity`, `gl_account`,
      `notes`). `reservation` queryset narrowed to `ACTIVE_STATUSES` rows of this tenant;
      `requested_by` narrowed to tenant users. `_reject_foreign` on every FK in both.
- [ ] A narrowed `<select>` is UX, not an authorization boundary — the `clean()` re-check is the
      boundary. Every form says so in its docstring.

### 6.18-F Views — `apps/procurement/views/InventoryWarehouseIntegration/`

`from apps.procurement.views._common import *` (gives `login_required`, `require_POST`,
`messages`, `render`, `redirect`, `get_object_or_404`, `timezone`, `crud_*`,
`tenant_admin_required`, `write_audit_log`). **Every queryset `filter(tenant=request.tenant)` —
never `.all()`.** Every view `@login_required`; every mutating verb `@require_POST`.
`crud_*` audit automatically; the hand-rolled verb paths call `write_audit_log` themselves.
Pinned `crud_*` context contract (`apps/core/crud.py:8-11`): list → `object_list` + `page_obj` +
`q`; detail/edit object → `obj`; form → `form` + `is_edit`.

#### `Policies.py` — 5 views, `TEMPLATE_LIST/DETAIL/FORM` module constants
- [ ] `replenishmentpolicy_list` — `crud_list`, `search_fields=("item__sku","item__name",
      "location__code","location__name","preferred_vendor__name","notes")`,
      `filters=(("item","item_id",True),("location","location_id",True),
      ("vendor","preferred_vendor_id",True),("source_method","source_method",False),
      ("trigger_mode","trigger_mode",False),("is_active","is_active",False))`.
      **Extra context keys: `stats` (dict: `total`, `active`, `inactive`, `auto` — ONE
      conditional aggregate), `items`, `locations`, `vendors`, `source_choices`,
      `trigger_choices`.**
- [ ] `replenishmentpolicy_detail` — `crud_detail`, `select_related` all six FKs.
      **Extra context: `rule` (the matching `scm.ReorderRule` or `None` — one query),
      `effective` (dict: `reorder_point`, `safety_stock`, `target_level`, `lead_time_days`,
      each with a `source` of `"policy override"` / `"reorder rule"`), `recent_suggestions`
      (last 10 `ReplenishmentSuggestion` rows for this item/location), `rule_url`.**
- [ ] `replenishmentpolicy_create` / `_edit` / `_delete` (`@require_POST`).

#### `Runs.py` — 9 views
- [ ] `replenishmentrun_list` — `crud_list`, `search_fields=("number","notes",
      "location__code","location__name")`,
      `filters=(("status","status",False),("trigger","trigger",False),
      ("location","location_id",True),("abc","abc_class_filter",False))`.
      **Extra context: `stats` (`total`, `draft`, `proposed`, `released`), `locations`,
      `status_choices`, `trigger_choices`, `abc_choices`.**
- [ ] `replenishmentrun_detail` — `crud_detail` + **`lines`** (the suggestions, paginated at 25
      via `paginate`, `select_related("item","item__uom","location","vendor","policy",
      "requisition")`), **`line_page_obj`**, **`decision_choices`**, **`vendors`**,
      **`totals`** (dict: `line_count`, `accepted`, `snoozed`, `dismissed`, `pending`,
      `accepted_value`), **`can_generate`**, **`can_release`**, **`can_cancel`**,
      **`requisitions`** (distinct released PRs with reversed urls), **`truncated`**,
      **`sku_match_note`**.
- [ ] `replenishmentrun_create` / `_edit` / `_delete` (`@require_POST`, draft only).
- [ ] `replenishmentrun_generate` (`@require_POST`) → `run.generate(request.user)`, catch
      `ValidationError` → `messages.error`, redirect to detail.
- [ ] `replenishmentrun_release` (`@require_POST` + **`@tenant_admin_required`** — it raises
      requisitions that commit money) → `run.release(request.user)`, redirect to detail.
- [ ] `replenishmentrun_cancel` (`@require_POST`).
- [ ] `replenishmentsuggestion_decide` (`@require_POST`) — loads the line via
      `get_object_or_404(ReplenishmentSuggestion, pk=line_id, run__pk=pk,
      run__tenant=request.tenant)` (**tenant reached through the run — the IDOR boundary**),
      binds `ReplenishmentSuggestionDecisionForm`, saves, `write_audit_log(..., "decide", ...)`.

#### `MaterialIssues.py` — 10 views
- [ ] `materialissue_list` — `crud_list`, `search_fields=("number","reference","notes",
      "location__code","location__name","org_unit__name")`,
      `filters=(("status","status",False),("movement_type","movement_type",False),
      ("purpose","purpose",False),("location","location_id",True),
      ("org_unit","org_unit_id",True))`.
      **Extra context: `stats` (`total`, `draft`, `submitted`, `posted`, `issues`, `returns`),
      `locations`, `org_units`, `status_choices`, `movement_choices`, `purpose_choices`.**
- [ ] `materialissue_detail` — `crud_detail` + **`lines`** (`select_related("item","item__uom",
      "lot_serial","gl_account")`), **`line_form`**, **`total_value`**, **`adjustment`**,
      **`adjustment_url`**, **`availability`** (dict `{item_id: on_hand}` from the ONE grouped
      query, so each line shows a shortfall flag *before* posting), **`can_submit`**,
      **`can_post`**, **`can_cancel`**, **`can_edit`**, **`boundary_note`** (verbatim: *return to
      **stock** is this document; return to **vendor** is 6.12 `ReturnToVendor` [RMA-]* — with a
      link, so nobody files one as the other), **`ledger_note`** (*posting mints a DRAFT stock
      adjustment; stock moves only when SCM posts it*).
- [ ] `materialissue_create` / `_edit` (draft only) / `_delete` (`@require_POST`, draft only).
- [ ] `materialissue_submit` / `_post` / `_cancel` — all `@require_POST`; `_post` additionally
      `@tenant_admin_required` (it changes stock). Catch `ValidationError` → `messages.error`
      with the per-item shortfall text.
- [ ] `materialissueline_add` (`@require_POST`) / `materialissueline_delete` (`@require_POST`) —
      header fetched with `tenant=request.tenant`, line via `pk=line_id, issue__pk=pk,
      issue__tenant=request.tenant`; both refuse unless the header is draft.

#### `StockPosition.py` — derived, **no model, no migration**
Bullet 1. Item-first rows. What makes it different from `inventory:stocklevels`: **the PO
expected date + vendor + PO number, the open-requisition column, and days of cover.**
- [ ] Reuse the ONE availability formula (`StockLevels.py:124`) verbatim —
      `available = on_hand − (SO allocations + reservations) − non-sellable`. **Do not invent a
      second definition.**
- [ ] Queries, each ONE grouped query, merged in Python (**never a per-row aggregate**):
      `StockMove` `.values("item_id","location_id","item__sku",…).annotate(Sum("quantity"))` ·
      `SalesOrderAllocation` (aliased pair) · `inventory.InventoryReservation` ·
      `inventory.StockStatus` · the local two-query `_on_order_map` · a PO-supply query for
      **earliest `expected_date` + vendor + number** per `sku_hint` · open-requisition qty per
      `sku_hint` · `ReorderRule` (point + `avg_daily_demand`) · `ReplenishmentPolicy`
      (preferred vendor).
- [ ] Filters parsed **before** pagination (rows are dicts, so a GROUP BY cannot paginate through
      the manager): `q`, `item`, `location`, `view` (`all`|`below_point`|`shortage`|`no_cover`),
      `vendor`.
- [ ] **Context keys: `page_obj`, `object_list`, `q`, `items`, `locations`, `vendors`,
      `view_choices`, `selected_view`, `stats` (`rows`, `below_point`, `shortage`, `no_cover`),
      `row_cap`, `truncated`, `sku_match_note`.**
      **Row dict keys: `item`, `location`, `on_hand`, `allocated`, `held`, `available`,
      `on_order`, `expected_date`, `expected_vendor`, `expected_po_number`, `expected_po_url`,
      `open_requisition_qty`, `reorder_point`, `avg_daily_demand`, `days_of_cover`,
      `below_point`, `policy_vendor`, `raise_requisition_url`.**
- [ ] `sku_match_note` states the honest limitation verbatim: on-order and open-requisition
      figures join through **exact-string `sku_hint` ↔ `Item.sku`** because the spine PO/PR lines
      carry free text, not an item FK (`StockLevels.py:38-44`) — unmatched lines are **reported,
      never guessed at**. The real fix is a spine migration, not a 6.18 one.
- [ ] `ROW_CAP = 500` with a `truncated` flag; `request.tenant is None` renders an empty page,
      never a 500; junk GET params narrow nothing and return 200; every row url is `reverse()`d
      **in Python, never in the template** (the four `CommitmentRegister.py:16-19` rules).

#### `ReceiptBinMap.py` — derived, **no model, no migration**
Bullet 4. "Where did MY received goods actually land?" — the one thing a buyer needs that no
existing NavERP page answers (the GRN detail shows the staging location, not the final bin).
- [ ] **The receipt→bin link IS `StockMove.reference == grn.number`** — posted at
      `apps/scm/views/_helpers.py:328-330` with `reason="Goods receipt"`, and indexed on
      `(tenant, reference)` (`StockMoves.py:60`). It is a **query, not a table**. A bin **IS**
      `scm.Location(location_type="bin")` (`Locations.py:17-23`) — **no Bin/Zone model.**
- [ ] Queries: page of `GoodsReceiptNote` (filtered + paginated FIRST) → then ONE grouped
      `StockMove` query `filter(tenant, reference__in=<the page's numbers>)
      .values("reference","location_id","item_id").annotate(Sum("quantity"))` → ONE
      `PutawayTask` query `filter(tenant, goods_receipt_id__in=<page pks>)` → ONE
      `inventory.BinCapacity` query for the touched locations → ONE `Location` fetch for
      `path()`. **Five queries total regardless of page size.**
- [ ] **Context keys: `page_obj`, `object_list` (row dicts), `q`, `locations`, `status_choices`,
      `selected_location`, `selected_status`, `date_from`, `date_to`, `stats` (`receipts`,
      `fully_putaway`, `partially_putaway`, `in_staging`), `row_cap`, `truncated`,
      `reference_note`, `links` (out to `scm:putawaytask_list`,
      `inventory:putawayrule_list`, `inventory:bincapacity_list`,
      `inventory:crossdockorder_list`).**
      **Row dict keys: `grn`, `grn_url`, `staging_location`, `received_qty`, `bins` (list of
      `{location, path, quantity, capacity, fullness_pct, capacity_css}`), `putaway_tasks`
      (list of `{task, url, status, status_css, to_location}`), `unputaway_qty`,
      `is_unputaway`, `putaway_css`.**
- [ ] Directed-putaway **suggestions are NOT rebuilt** — `inventory.PutawayRule` +
      `resolve_putaway_suggestion()` (`PutawayRules.py:48,150`) and `scm.PutawayTask` already
      exist. Link out only.

#### `CountAccuracy.py` — derived, **no model, no migration**
Bullet 5. The read-out over counting that is fully built in SCM 4.4 + Module 5.11.
- [ ] Queries: ONE aggregate over `CycleCountTask` for the window (counts by status) · ONE
      grouped query over `CycleCountTaskLine` for the item roll-up
      (`filter(cycle_count__tenant, cycle_count__scheduled_date range)
      .values("item_id",…).annotate(lines=Count, expected=Sum, counted=Sum)`) · ONE grouped
      query for the location roll-up · ONE `inventory.CountProgram` fetch for the schedule
      column. **Variance is computed from `Sum(counted) − Sum(expected)` in the annotation —
      `CycleCountTaskLine.variance` is a Python property and cannot be aggregated.** State that
      in a comment.
- [ ] **Context keys: `stats` (`tasks_total`, `tasks_scheduled`, `tasks_counted`,
      `tasks_reconciled`, `tasks_cancelled`, `lines_counted`, `lines_with_variance`,
      `variance_rate_pct`, `net_variance_qty`, `abs_variance_qty`, `variance_value`,
      `accuracy_pct`), `item_rows`, `location_rows`, `program_rows`, `locations`,
      `window_choices`, `selected_window`, `selected_location`, `date_from`, `date_to`,
      `row_cap`, `truncated`, `attribution_note`, `links`.**
      **`item_rows` keys: `item`, `count_lines`, `variance_lines`, `net_variance`,
      `abs_variance`, `variance_value`, `accuracy_pct`, `repeat_offender`.**
      **`location_rows` keys: `location`, `path`, `count_lines`, `variance_lines`,
      `net_variance`, `accuracy_pct`, `accuracy_css`.**
      **`program_rows` keys: `program`, `cadence_label`, `last_run_date`, `is_due`, `location`,
      `abc_class`, `url`.**
- [ ] `links` reverses out to `scm:cyclecounttask_list`, `inventory:countprogram_list`,
      `inventory:physicalinventory_list`, `scm:stockadjustment_list`.
- [ ] `attribution_note` states plainly: **root-cause attribution (receiving error / putaway
      error / picking error / supplier shortage / damage / data entry / shrinkage) is NOT
      recorded yet**, and feeding count variance into a supplier scorecard belongs to **6.16**
      (`scm.SupplierScorecard` exists). The page must not imply a capability it lacks.

### 6.18-G URLs — `apps/procurement/urls/InventoryWarehouseIntegration/`

One module per views module; `app_name` is set once in `apps/procurement/urls/__init__.py`.
**Literal routes BEFORE `<int:pk>` ones — Django is first-match-wins.**

- [ ] `StockPosition.py` — `path("stock-position/", views.stock_position, name="stock_position")`
- [ ] `Policies.py` — `replenishment-policies/` + `add/` (literal first) + `<int:pk>/` +
      `<int:pk>/edit/` + `<int:pk>/delete/` → `replenishmentpolicy_{list,create,detail,edit,delete}`
- [ ] `Runs.py` — `replenishment-runs/` + `add/` + `<int:pk>/` + `<int:pk>/edit/` +
      `<int:pk>/delete/` + `<int:pk>/generate/` + `<int:pk>/release/` + `<int:pk>/cancel/` +
      `<int:pk>/lines/<int:line_id>/decide/` → `replenishmentrun_{list,create,detail,edit,delete,
      generate,release,cancel}` + `replenishmentsuggestion_decide`
- [ ] `MaterialIssues.py` — `material-issues/` + `add/` + `<int:pk>/` + `<int:pk>/edit/` +
      `<int:pk>/delete/` + `<int:pk>/submit/` + `<int:pk>/post/` + `<int:pk>/cancel/` +
      `<int:pk>/lines/add/` + `<int:pk>/lines/<int:line_id>/delete/` →
      `materialissue_{list,create,detail,edit,delete,submit,post,cancel}` +
      `materialissueline_{add,delete}`
- [ ] `ReceiptBinMap.py` — `path("receipt-bin-map/", views.receipt_bin_map, name="receipt_bin_map")`
- [ ] `CountAccuracy.py` — `path("count-accuracy/", views.count_accuracy, name="count_accuracy")`
- [ ] `__init__.py` — concatenates the six modules' `urlpatterns`; docstring lists the six
      claimed first segments and uses the **accurate** greedy-converter sentence (6.18-B).

### 6.18-H Templates — `templates/procurement/inventorywarehouse/`

`{% extends "base.html" %}` and `{% include "partials/..." %}` are unaffected by the folders.
**Colour-named badge classes only** (`badge-green/red/amber/info/muted/slate`) — L33.

- [ ] `replenishmentpolicy/list.html` — filter bar (q + item + location + vendor + source_method
      + trigger_mode + is_active, each reflecting `request.GET`; FK selects compare with
      `|stringformat:"d"`, **never `|slugify`**), stats strip, Actions column
      (view / edit / delete POST + `onclick="return confirm(...)"` + `{% csrf_token %}`),
      pagination guarded on `page_obj.has_previous` / `has_next` (L9), empty state.
- [ ] `replenishmentpolicy/detail.html` — effective-values table (override vs. reorder-rule
      source per row), link to `scm:reorderrule_list`, recent suggestions, Actions sidebar
      (Edit / Delete POST / Back to list).
- [ ] `replenishmentpolicy/form.html` — `{% if is_edit %}` title split; `notes` textarea;
      inline field errors.
- [ ] `replenishmentrun/list.html` — filters (status, trigger, location, abc), stats, Actions,
      pagination, empty state.
- [ ] `replenishmentrun/detail.html` — header card, totals strip, the suggestion table with a
      per-row decision form (POST to `replenishmentsuggestion_decide`, csrf, vendor override
      select, snooze date), Generate / Release / Cancel POST buttons gated on
      `can_generate`/`can_release`/`can_cancel`, released-requisition links, `truncated` banner,
      `sku_match_note`, inner pagination on `line_page_obj`.
- [ ] `replenishmentrun/form.html`.
- [ ] `materialissue/list.html` — filters (status, movement_type, purpose, location, org_unit),
      stats, Actions (edit/delete conditional on `obj.is_editable`), pagination, empty state.
- [ ] `materialissue/detail.html` — header, `boundary_note` callout (**return to stock vs.
      return to vendor / 6.12**), `ledger_note` callout (**the minted adjustment is DRAFT**),
      line table with per-line shortfall flag from `availability`, add-line form, delete-line
      POST, Submit / Post / Cancel POST buttons gated on the `can_*` keys, adjustment link,
      Actions sidebar.
- [ ] `materialissue/form.html`.
- [ ] `stock_position.html` (standalone, sub-module root) — filter bar, stats, the
      on-hand/available/on-order/expected-date/vendor/open-PR/days-of-cover table, "Raise
      requisition" action per row, `sku_match_note`, `truncated` banner, pagination, empty state.
- [ ] `receipt_bin_map.html` (standalone) — per-GRN card/row with staging location, the bins its
      stock reached (`Location.path()`), qty per bin, fullness badge, putaway tasks,
      **unputaway** badge, `reference_note`, link-outs, filters, pagination, empty state.
- [ ] `count_accuracy.html` (standalone) — KPI strip, top-variance SKU table, location accuracy
      table, count-program schedule table, `attribution_note`, link-outs to
      `scm:cyclecounttask_list` / `inventory:countprogram_list`, window + location filters,
      empty state.
- [ ] **No flat `<entity>_<page>.html` anywhere.** No `{#` / `{% comment` leaks.

### 6.18-I Integrate (single writer, only DB writer — surgical `Edit` on every shared file)

- [ ] **Verify every expected file actually landed** before wiring anything.
- [ ] `apps/procurement/models/__init__.py` — append the re-export block (after 6.15's
      `CostForecast`/`compute_forecast_amounts` at `:185-186`) and extend `__all__`:
      `ReplenishmentPolicy`, `ReplenishmentRun`, `ReplenishmentSuggestion`, `MaterialIssue`,
      `MaterialIssueLine`. **Missing re-export = `ImportError` at runtime.**
- [ ] `apps/procurement/forms/__init__.py` — `ReplenishmentPolicyForm`, `ReplenishmentRunForm`,
      `ReplenishmentSuggestionDecisionForm`, `MaterialIssueForm`, `MaterialIssueLineForm`.
- [ ] `apps/procurement/views/__init__.py` — all 27 view names
      (5 policy + 9 run + 10 issue + 3 derived).
- [ ] `apps/procurement/urls/__init__.py` — `from .InventoryWarehouseIntegration import
      urlpatterns as _iwi_inventorywarehouse`, spread **LAST** in `urlpatterns` (the
      6.13/6.14/6.15 belt-and-braces precedent at `:76-98`), and extend the docstring's segment
      inventory with the six new segments — **using the corrected greedy-converter sentence.**
- [ ] `apps/procurement/admin.py` — 5 registrations with `list_display`/`list_filter`/
      `search_fields`/`raw_id_fields`, `readonly_fields` covering `number` + every
      `editable=False` snapshot (the `CostForecastAdmin:767-778` precedent). Extend the existing
      import tuple surgically.
- [ ] `apps/procurement/management/commands/seed_procurement.py` — add
      `self._seed_inventory_warehouse(tenant)` **after** 6.17's dispatch line in the tenant loop
      (currently `self._seed_budget_cost(tenant)` at `:262` is last), and add the model deletes
      to the `--flush` block for correctness. **Idempotent, `get_or_create`-based, and it must
      NEVER be run with `--flush` in this session.**
      Seeded rows per tenant (skip with a `WARNING` when `scm.Item`/`scm.Location`/
      `scm.ReorderRule` are absent — run `seed_scm` first; the SMOKETEST tenant must skip
      gracefully, the 6.15 precedent):
      - [ ] 3 `ReplenishmentPolicy` rows over existing items × locations, one with a
            `preferred_vendor` (existing supplier `Party`), one location-agnostic catch-all, one
            with `source_method="transfer"` so the link-out branch is visible.
      - [ ] 1 `ReplenishmentRun` created then `generate()`d (existence guard on
            `(tenant, run_date)` before creating; skip when there are no active reorder rules).
      - [ ] 3 `MaterialIssue` documents — one `draft` issue (2 lines), one `submitted` issue
            (2 lines), one `draft` return (1 line). **The seeder NEVER calls `post()`** — that
            would write a `scm.StockAdjustment` from a seed run and couple us to `seed_scm
            --flush`. Posting stays a user/smoke action; say so in the block's comment.
      - [ ] Number-collision guard: `filter(tenant=tenant, number=…).first()` before create for
            every `TenantNumbered` row.
- [ ] `apps/core/navigation.py` — **exactly one** new key, `"6.18"`, placed after `"6.15"`
      (`:1626-1632`), with the **exact NavERP.md `### 6.18` bullet text** (`NavERP.md:1116-1120`):
      ```
      "6.18": {
          "Stock Level Visibility":       "procurement:stock_position",
          "Reorder Point Automation":     "procurement:replenishmentrun_list",
          "Goods Issue/Return to Stock":  "procurement:materialissue_list",
          "Warehouse Location Mapping":   "procurement:receipt_bin_map",
          "Cycle Count Integration":      "procurement:count_accuracy",
      },
      ```
      Plus a comment recording that **`ReplenishmentPolicy` deliberately gets NO sidebar key** —
      configuration behind an analysis page, reached from the run list (the
      `ReceiptTolerancePolicy` / `SpendClassificationRule` / `ReorderRule` precedent documented
      at `navigation.py:1633-1648`). **Do not touch any other key.**
- [ ] `config/settings.py` / `config/urls.py` — **NO CHANGE** (`apps/procurement` is already
      installed and included).
- [ ] **Gate:** confirm `apps/procurement/migrations/0027_*.py` exists → then
      `python manage.py makemigrations procurement` → **must produce `0028_*`**. If it produces a
      different number, STOP and re-agree with the peer sessions.
- [ ] Commit **one file per commit**, explicit paths, PowerShell `;`.

### 6.18-J Verify

- [ ] `python manage.py makemigrations procurement` → `0028_*` only, no unexpected model changes
      elsewhere.
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_procurement` **twice** (NO `--flush`) — second run must create
      nothing and print the skip lines.
- [ ] `python manage.py check` — clean.
- [ ] `python manage.py makemigrations --check --dry-run` — "No changes detected".
- [ ] Throwaway `temp/` smoke script, logged in as **`admin_acme` / `password`**, asserting
      **content, not just status** (a mismatched context var returns 200 and renders blank, L8):
      - [ ] All 6 GET pages + all 3 list + 3 detail + 3 form pages → 200.
      - [ ] Every POST verb (`generate`, `release`, `cancel`, `decide`, `submit`, `post`,
            `lines/add`, `lines/<id>/delete`, all 3 `delete`) → 302, and GET on each → 405/302
            (POST-only).
      - [ ] Content assertions: page titles, a seeded `RPL-`/`MIS-` number, a seeded policy's
            item SKU, the `sku_match_note` / `boundary_note` / `attribution_note` / `ledger_note`
            strings, at least one bin `path()` on the receipt map, the variance-rate figure.
      - [ ] **No `{#` or `{% comment` leaks** in any rendered body.
      - [ ] Junk params on every list + derived page (`?status=nope&item=abc&location=²&
            vendor=999999999999999999999&page=999`) → 200, not empty-by-accident, no 500.
      - [ ] `?page=2` on every paginated page → 200.
      - [ ] **Cross-tenant IDOR → 404** on every `<int:pk>` route including the two child routes
            (`replenishmentsuggestion_decide`, `materialissueline_delete`) — a line reached via
            another tenant's run/issue must 404.
      - [ ] Post one throwaway `MaterialIssue`: assert a **draft** `scm.StockAdjustment` is minted
            with the marker note, that `quantity_delta` is negative for an issue and positive for
            a return, and that **zero `scm.StockMove` rows were created**.
      - [ ] Over-issue guard: posting a quantity above the location's on-hand is refused with the
            per-item message.
      - [ ] Release one throwaway run: assert `scm.PurchaseRequisition` rows are created in
            **`draft`**, one per vendor, with `sku_hint`/`uom_hint`/`gl_account` populated and
            `estimated_total` recalculated; assert a second Release is refused.
      - [ ] Tenant-less superuser (`admin`) sees empty pages, **never a 500**.
      - [ ] Query-count probe on `stock_position`, `receipt_bin_map`, `count_accuracy` and
            `replenishmentrun_detail` — assert the count does **not** scale with row count.
      - [ ] Delete the `temp/` script; never commit it.
- [ ] Sidebar: all **five** `6.18` bullets render **Live** and resolve.

### 6.18-K Close-out

- [ ] Phase 4 — six reviewers **one after another**, each in its own `Agent` call:
      `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
      `qa-smoke-tester` → `security-reviewer`. Append each one's findings to
      `.claude/tasks/review-procurement-6.18.md` as it reports; dedupe, sort
      Critical → Important → Minor, assign `C#`/`I#`/`M#`; commit the file.
- [ ] Phase 5 — one `code-fixer` agent burns the findings down in ID order, one commit per file;
      confirm nothing is left `[ ] open` and `manage.py check` is clean.
- [ ] Phase 6 — tests, **subslug `invwarehouse`**: contract + shared `conftest.py` first, then
      `test_invwarehouse_models.py` → `test_invwarehouse_forms.py` →
      `test_invwarehouse_views.py` → `test_invwarehouse_security.py`, one agent each, one commit
      each. Every test function `test_invwarehouse_*`, every module helper `_invwarehouse_*`.
      Finish with a **full unfiltered** `apps/procurement` suite run, green (never `-k` filtered,
      L47). **Do not touch the other session's `test_budgetcost_*.py`.**
- [ ] Phase 7 — update `.claude/skills/procurement/SKILL.md` with 6.18's models, the six routes,
      the template folder, the seeder block and the two module-specific gotchas (**never write
      `StockMove` from procurement**; **a bin is `scm.Location(location_type='bin')`**). Commit
      on its own.
- [ ] Mark 6.18 complete in `README.md`. Commit on its own.
- [ ] **Never `git push`.**

### 6.18-L Later passes / deferred (nothing here is lost — carried from the research)

**Dropped from this pass by an explicit scope decision:**
- **`CountVarianceReview` `[CVR-]`** (the research's optional entity 4 — root-cause attribution
  over `scm.CycleCountTaskLine` with `receiving_error`/`putaway_error`/`picking_error`/
  `supplier_shortage`/`damage`/`data_entry`/`shrinkage`/`unknown`, `supplier_attributable`, and
  an optional `GoodsReceiptNote` + vendor link). **Why:** bullet 5 is already served by the
  derived Count Accuracy page plus link-outs to the fully built `scm.CycleCountTask` and
  `inventory.CountProgram`; the attribution table's only consumer is the supplier scorecard,
  which is **6.16**'s (`scm.SupplierScorecard` exists). Building the producer before the
  consumer would ship a table nobody reads. Revisit as a 6.16 hand-off or a later 6.18 pass —
  the Count Accuracy page's `attribution_note` already names the gap honestly.

**Deferred (from the research's own deferred list):**
- **Journal posting for issues/returns** (issue → expense, return → credit). Accounting owns the
  ledger (L29) and `scm.StockAdjustment` posts no `JournalEntry` today. 6.18 shows the GL account
  and the value impact only; the real hand-off is co-ordinated with `inventory.GLPostRule`
  (`AccountingFinancialIntegration/GLPostRules.py:23`). **Opening a second posting path here
  would be the worst possible outcome of this sub-module.**
- **Scheduled replenishment runs (cron/Celery).** The `trigger` column ships; the scheduler and
  the management command do not — same posture as `CountProgram.is_due()`.
- **Low-stock email/notification digests** (Precoro's daily reminder). Reuse
  `procurement.ProcurementAlert` (6.1) in-app if wanted; email delivery is integration-later.
  **Never add a second alert table.**
- **Inline stock check on the requisition/PO entry form** (Coupa/Precoro/Procurify) — high value,
  but it edits 6.2/6.10 templates and 6.18 must not touch a sibling sub-module's forms this pass.
- **License plates / handling units** at receiving (D365, SAP HU) — no concept in the spine, and
  a Module 5 WMS concern rather than a buyer's.
- **Item→vendor catalogue price on the suggestion line** — should read 6.9 `CatalogItem` /
  `CatalogPriceTier` rather than `Item.standard_cost`; deferred to keep this pass's query count
  flat.
- **`sku_hint` free-text matching.** Every item-level join from a PO/PR line goes through
  exact-string `sku_hint ↔ Item.sku`. 6.18 mirrors that helper locally and **reports unmatched
  lines honestly**. The real fix is an `item` FK on the spine line models — a **spine** migration,
  not a 6.18 one.
- **Consumption-driven (pull) replenishment** from the new `MaterialIssue` history — becomes
  possible once issues have run for a period.
- **Requisition-from-stock / internal fulfilment** (Coupa, Precoro) — the requester-facing mirror
  of the issue document; needs a requester-facing flow.
- **Consigned / vendor-managed inventory** — parked here by 6.11 and still parked; needs an
  ownership dimension neither `scm.Item.owner_client` nor `StockMove` provides.
- **Count-triggered thresholds** (count when stock hits N or zero, D365) — extends
  `inventory.CountProgram`, so it belongs to **5.11**.
- **In-transit quantity column** on the stock page (`Location(location_type='transit')` +
  6.11 ASN lines) — thin, additive, easy later pass.

**Parked for a sibling sub-module (do NOT pull into 6.18):**
- Count variance → supplier scorecard / KPI / benchmarking → **6.16** (`scm.SupplierScorecard`)
- Rejection/discrepancy rates, receipt tolerances, inspection, **return to vendor** → **6.12**
  (`ReceiptDiscrepancy`, `ReceiptTolerancePolicy`, `ReturnToVendor`). *Return to **stock** (here)
  and return to **vendor** (6.12) are different documents — the MaterialIssue detail page says so.*
- Budget availability on the generated requisition, commitment accounting → **6.15**; 6.18 only
  sets the `budget`/`org_unit` defaults so 6.15's check can run.
- Requisition approval routing on the generated PR → **6.3**; PO conversion → **6.10**.
- In-transit/ASN arrival detail → **6.11**. Contract/catalogue price on the line → **6.8 / 6.9**.
- Bin capacity envelopes, cross-dock, putaway **rules**, count **programs**, physical inventory,
  stock statuses, reservations, barcode/RFID → **Module 5** (all built).
- Safety-stock calculation, ABC/XYZ classing, seasonality, demand forecasting → **SCM 4.7**.
- Putaway/pick/count **execution**, yard, slotting → **SCM 4.4**. Item/UOM/lot masters,
  adjustments, transfers, valuation → **SCM 4.3**. Landed cost → **SCM 4.18**.

### 6.18-M Review notes
(filled in at the end of the pass)

---

## Review — 6.19 Document & Knowledge Management (closed 2026-09-06)

Built across two sessions with three peer sessions (6.16/6.17/6.18) live in the same checkout.
All seven phases complete.

**Shipped:** 4 models (`ProcurementDocument` [PDOC-], `ProcurementDocumentRevision`,
`ProcurementPolicy` [PPOL-], `KnowledgeResource` [PKR-]), 33 routes over 4 first segments, 12
templates, migration `0026` (+ index changes in `0029`), seeder block, `LIVE_LINKS["6.19"]`.
**1,003 tests** across four lanes (models 247, forms 173, views 334, security 249).

### What the review phase actually bought

Six reviewers ran one after another and produced **2 Critical, 16 Important, 24 Minor**. The
`code-fixer` closed 41 of 42; the one skip (renaming `next_review_on`) was correct, because 6.17 had
already committed a template reading it.

The two Critical findings were both invisible to everything that came before them:

* **C1** — every uploaded file was readable with **no login, no session, no tenant**, confirmed by
  an anonymous `curl`. The smoke sweep's 37 route probes and its cross-tenant IDOR checks all
  passed, because they tested the HTML pages — which were correctly tenant-scoped — and never the
  object those pages linked to. Fixed with an authenticated, tenant-scoped `pdocrevision_download`.
* **C2** — the revision register hauled **59 MB in 4.87 s** at 2,000 documents against a 0.189 s
  control, because an unbounded dropdown selected full rows including the 200 KB `extracted_text`
  to render three fields.

**`classification` was enforced nowhere** (I5) — not one queryset, decorator or conditional read it,
while the UI described a tier as "for records only a named few may read". Fixing it took **three
passes**, and the second and third holes were found by later agents rather than by the reviewers:
the revision register's stat tiles were a counting oracle, and the edit form was a read of every
field it prefills.

### What worked, and is worth repeating

* **Runtime verification beat static reasoning.** Pass 5 reproduced every theorised finding and
  **refuted one**: item 3's predicted consequence (a wedged document) was wrong, and the real end
  state was worse — an *unapproved* file becoming the document of record, with a green "Current"
  badge beside "Not approved" on the same row.
* **A reviewer that rejects leads is doing its job.** Pass 3 knocked down two of pass 2's three
  handovers with evidence.
* **Strict xfail for an open finding.** The security lane encoded the `pdocument_edit` hole as a
  `strict=True` xfail rather than softening the assertion, so the defect lived in the suite instead
  of only in a report — and the marker forced its own deletion when the view was fixed.
* **Pinning a test contract before writing tests.** It caught 27 places the frozen build contract
  had gone stale, and its author found the counting oracle while measuring what to assert.

### Deliberately not done

App-wide clone families were recorded, not forked into this sub-module: **15 remaining `.file.url`
links across 13 templates** (C1's family), the tenant-editable admin on 50 of 52 ModelAdmins,
pagination-ordering indexes, and the thrice-duplicated alert-raise skeleton.

**One upstream bug found here, not fixed here:** `core.AuditLog.action` is `varchar(10)` while 6.19
writes `"document_reminders_run"` (22 chars). SQLite ignores VARCHAR length so the suite is green;
**MariaDB in strict mode would 500 the Run-reminders POST.** The fix is a `core` migration —
single-writer work, and this dev DB is not in strict mode, which is why it has stayed invisible.

---

## 7.1 Project Initiation & Charter (Module 7: Project Management, `projects`) — plan from research-projects-7.1.md (2026-09-07)

> **BRAND-NEW-APP RUN.** `apps/projects/` does not exist (`ls apps/projects` → No such file or
> directory), `apps.projects` is not in `INSTALLED_APPS`, `templates/projects/` does not exist, and
> `grep -c '"7\.' apps/core/navigation.py` → **0** (the last key is `"6.19"` at
> `apps/core/navigation.py:1690`). Module 7 is fully greenfield, so this plan carries the scaffold.
>
> Backend sub-module folder: **`ProjectInitiation/`** (all four layers). Template sub-module slug:
> **`initiation`** (`templates/projects/initiation/<entity>/{list,detail,form}.html`) — pinned by
> the research at `research-projects-7.1.md:487-488`. Do NOT use `projectinitiation/`: the
> as-built convention for a single-app namespace is the short slug (procurement ships
> `documentknowledge/`, `spendanalytics/`, `budgetcost/`).

### Scope (research's 4 models, unchanged — the repo did not contradict it)

- [ ] 4 models: `ProjectRequest` [PRQ-] + `Project` [PRJ-] + `ProjectStakeholder` [PST-] +
      `ProjectKickoff` [PKO-]. **No fifth.**
- [ ] **`Project` ships in 7.1, not 7.2** (research ruling, upheld): every surveyed tool creates
      the project at initiation, and 7.2's WBS / dependencies / milestones / frozen baseline must
      hang off an existing record. 7.2 *inherits* `Project` and adds to it.
- [ ] **Charter stays short.** No money columns on `Project` — `budget_amount`, commitments and
      actuals are 7.4's, and `accounting.Project` already carries them for the costing lens.
- [ ] **No second attachment store.** The signed charter is `charter_document` → `core.Document`
      (nullable reuse), exactly the 6.19 ruling.
- [ ] **No `BusinessCase` table and no `ProjectKickoffItem` table.** Bullet 2's economics are a
      field set on `ProjectRequest`; bullet 5's onboarding checklist is `core.Activity(kind="task")`
      rows GFK'd to the project. Both are the research's deliberate 4-model-cap trades and both are
      reversible — say so in the model docstrings.
- [ ] **If the pass runs long, `ProjectKickoff` is dropped first** (research: the only one of the
      four whose content is fully re-expressible on existing spine).

### ⚠️ The three `PRJ-` models — VERIFIED, and NOT to be "fixed" by a later session

| Model | File | Prefix | Status |
|---|---|---|---|
| `accounting.Project` | `apps/accounting/models/ProjectCosting/Projects.py:6` | `NUMBER_PREFIX = "PRJ"` (`:9`) | pre-spine stand-in — **untouched this pass** |
| `crm.CrmProject` | `apps/crm/models/ProjectDelivery/Projects.py:6` | `NUMBER_PREFIX = "PRJ"` (`:9`) | pre-spine stand-in — **untouched this pass** |
| `projects.Project` | `apps/projects/models/ProjectInitiation/Projects.py` | `NUMBER_PREFIX = "PRJ"` | **the master, added this pass** |

- [ ] `projects.Project`'s docstring MUST name both stand-ins and their paths, and state that
      numbers are unique per `(tenant, number)` **within a model**, so there is no key collision —
      but the sidebar copy and every page title must say which "project" the user is looking at.
- [ ] **Do NOT rename, migrate, deprecate or touch `accounting.Project` / `crm.CrmProject`.** No
      migration for either app this pass.

### Spine: grep-VERIFIED this pass (L28 — the grep is the truth, not the ERD)

| Target | Verified at | Used for |
|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py` | every `tenant` FK (via the abstract bases) |
| `core.Party` | `apps/core/models/Party.py:5` | `ProjectRequest.requester_party`, `Project.client`, `ProjectStakeholder.party` |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | `ProjectRequest.org_unit`, `Project.org_unit` |
| `core.Document` | `apps/core/models/Document.py:5` | `Project.charter_document` (GFK attachment, has `tenant`) |
| `core.Activity` | `apps/core/models/Activity.py:5` | kickoff meeting (`kind="meeting"`) + onboarding items (`kind="task"`), GFK to `Project`. **Has `due_at` DateTimeField, `status`, and NO `completed_at`** |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | `ProjectRequest.currency` — **GLOBAL, no `tenant` column (L29)** |
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py:5` | `ProjectRequest.source_opportunity` (`TenantNumbered`) |
| `apps.core.utils.next_number` | `apps/core/utils.py:34` | the four number prefixes |
| `apps.core.utils.write_audit_log` | `apps/core/utils.py:6` | audit rows — **see the `varchar(10)` trap below** |
| `apps.core.crud` helpers | `apps/core/crud.py:115-224` | `crud_list`/`create`/`edit`/`detail`/`delete` |
| `tenant_admin_required` | `apps/core/decorators.py:13` | gates the governance verbs |
| `scm.Item` | `apps/scm/models/InventoryManagement/Items.py:73` | **NOT used by 7.1** — recorded only so nobody hunts for `core.Item` |

- [ ] Confirmed absent, so nothing may hope for them: **no `core.Project`** (the ERD entry is
      unbuilt intent — `grep -rn "^class Project" apps/core/models/` returns nothing), no
      `core.Item` / `inventory.Item` (**`Item` is `scm.Item`** — the `/next-module` skill's "Item
      not built yet" note is **stale**), no `hrm.Department` (that shape is
      `hrm.EmployeeProfile`/`hrm.DepartmentProfile`), no `procurement.Contract`, no Celery.
- [ ] Every FK is declared **by string** (`"core.Party"`, `"crm.Opportunity"`,
      `"accounting.Currency"`, `"core.Document"`, `"projects.Project"`) — no cross-app model import
      at module level.

### 🚨 Two places this plan OVERRIDES the research (say it loudly)

1. **`ProjectStakeholder.Meta.ordering` — research says `["-influence", "party__name"]`; that is
   WRONG and must not ship.** `influence` is a `CharField` with values `high`/`medium`/`low`, so a
   descending sort is **alphabetical**: `medium`, then `low`, then `high` — the exact inverse of the
   power ranking the influence/interest grid exists to show. `party` is also nullable, so
   `party__name` sorts NULLs inconsistently between SQLite (tests) and MariaDB (prod).
   **Pinned instead:** `Meta.ordering = ["-created_at", "-id"]` (index-backed, deterministic), and
   the list view annotates a numeric rank and orders by it — see Model 3.
2. **`unique_together = ("tenant", "project", "party", "raci_scope")` is a partial constraint.**
   `party` is nullable and SQL treats every NULL as distinct, so the DB happily stores unlimited
   duplicates for stakeholder rows that carry only a `user`. **Pinned:** keep the constraint (it
   does bind the common `party`-set case) **and** add a form-level `clean()` that raises on a
   duplicate `(project, party, raci_scope)` — otherwise the register silently accepts doubles.
   `clean()` also enforces "at least one of `party` / `user` must be set".

### 🚨 `core.AuditLog.action` is `varchar(10)` — the 6.19 upstream bug, hit again

Confirmed at `apps/core/models/AuditLog.py:17`. 6.19 recorded that it writes a 22-char action and
would 500 on MariaDB in strict mode. **Every 7.1 action string is ≤ 10 characters — pinned:**
`create` / `update` / `delete` (the `crud_*` helpers), `submit`, `approve`, `reject`, `convert`,
`return`, `schedule`, `held`, `complete`, `baseline` (8). The verb itself goes in `changes`
(`{"verb": "...", "from": ..., "to": ...}`), never in `action`. Do not file the `core` migration
from this pass — it is single-writer `core` work; note it in the review file.

---

### Model 1 — `ProjectRequest` [PRQ-] (`models/ProjectInitiation/ProjectRequests.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PRQ"`. 32 declared + 4 inherited = **36 fields**.
Realizes bullets **1 Project Request & Intake** and **2 Business Case & Feasibility**.

#### Choices (exact machine values)
- [ ] `REQUEST_TYPE_CHOICES` — `new_project`/New Project, `enhancement`/Enhancement,
      `change_request`/Change Request, `defect`/Defect Repair, `idea`/Idea (ServiceNow)
- [ ] `SOURCE_CHOICES` — `portal`/Portal, `internal`/Internal, `idea`/Idea, `opportunity`/
      Opportunity, `email`/Email
- [ ] `PRIORITY_CHOICES` — `low`/Low, `medium`/Medium, `high`/High, `critical`/Critical
- [ ] `RISK_RATING_CHOICES` — `low`/Low, `medium`/Medium, `high`/High, `critical`/Critical
- [ ] `FEASIBILITY_CHOICES` — `not_assessed`/Not Assessed, `feasible`/Feasible,
      `feasible_with_constraints`/Feasible with Constraints, `not_feasible`/Not Feasible
- [ ] `STATUS_CHOICES` — `draft`/Draft, `submitted`/Submitted, `screening`/Screening,
      `assessment`/Assessment, `needs_information`/Needs Information, `approved`/Approved,
      `rejected`/Rejected, `deferred`/Deferred, `converted`/Converted (BrightWork + send-back)
- [ ] `DECISION_CHOICES` — `go`/Go, `no_go`/No-Go, `hold`/Hold, `deferred`/Deferred
- [ ] Constants: `RISK_DISCOUNT = {"low": Decimal("1.00"), "medium": Decimal("0.85"),
      "high": Decimal("0.70"), "critical": Decimal("0.50")}` — the documented flat factor behind
      "risk-adjusted return". **Explicitly not Monte Carlo** (7.5's).

#### Fields
- [ ] `title` `CharField(max_length=200)`
- [ ] `description` `TextField()`
- [ ] `request_type` `CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default="new_project")`
- [ ] `requested_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="prq_filed")`
- [ ] `requester_party` `FK("core.Party", SET_NULL, null=True, blank=True, related_name="project_requests")`
      — external submitter
- [ ] `org_unit` `FK("core.OrgUnit", SET_NULL, null=True, blank=True, related_name="project_requests")`
- [ ] `source` `CharField(max_length=20, choices=SOURCE_CHOICES, default="internal")`
- [ ] `source_opportunity` `FK("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="project_requests")`
- [ ] `assigned_reviewer` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="prq_to_review")`
- [ ] `assigned_approver` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="prq_to_approve")`
- [ ] `priority` `CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")`
- [ ] `strategic_alignment` `PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(5)])`
      — 0–5 score (ServiceNow/Planview)
- [ ] `estimated_cost` `DecimalField(max_digits=14, decimal_places=2, default=0)`
- [ ] `estimated_benefit` `DecimalField(max_digits=14, decimal_places=2, default=0)`
- [ ] `currency` `FK("accounting.Currency", SET_NULL, null=True, blank=True, related_name="project_requests")`
      — **global table, no `tenant` column**: `TenantModelForm` will NOT scope it (it only scopes
      models carrying `tenant`) and `clean()` must never compare `currency.tenant` (L29)
- [ ] `risk_rating` `CharField(max_length=10, choices=RISK_RATING_CHOICES, default="low")`
- [ ] `feasibility` `CharField(max_length=24, choices=FEASIBILITY_CHOICES, default="not_assessed")`
- [ ] `feasibility_notes` `TextField(blank=True)`
- [ ] `alternatives_considered` `TextField(blank=True)`
- [ ] `required_resources` `TextField(blank=True, help_text="Free text — real resourcing is 7.3's")`
- [ ] `target_start_date` `DateField(null=True, blank=True)`
- [ ] `target_end_date` `DateField(null=True, blank=True)`
- [ ] `status` `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")` — **verb-driven,
      NOT on the form**
- [ ] `decision` `CharField(max_length=10, choices=DECISION_CHOICES, default="", blank=True)` —
      **verb-driven, NOT on the form**
- [ ] `decided_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`
- [ ] `decided_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `decision_notes` `TextField(blank=True)`
- [ ] `rejection_reason` `TextField(blank=True)`
- [ ] `information_requested` `TextField(blank=True)`
- [ ] `submitted_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `converted_project` `FK("projects.Project", SET_NULL, null=True, blank=True, related_name="source_requests")`
      — set by the convert verb
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

#### Derived (properties, **never columns**)
- [ ] `roi_pct` — `(benefit - cost) / cost * 100` quantized 2dp; returns `None` when `cost == 0`
      (never `ZeroDivisionError`, never a stored editable value)
- [ ] `risk_adjusted_benefit` — `q2(estimated_benefit * RISK_DISCOUNT[risk_rating])`
- [ ] `risk_adjusted_roi_pct` — the same formula over `risk_adjusted_benefit`

#### Meta / behaviour
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`
- [ ] indexes (all ≤ 30 chars): `("tenant","status")` `prq_tnt_status_idx`,
      `("tenant","request_type")` `prq_tnt_type_idx`, `("tenant","org_unit")` `prq_tnt_ou_idx`
- [ ] `convert_to_project(user)` — the service method the verb calls: creates `Project` copying
      `title`→`name`, `description`, `target_start_date`→`start_date`, `target_end_date`→`end_date`,
      `org_unit`, `requester_party`→`client`, `assigned_approver`→`executive_sponsor`; sets
      `Project.request = self`, `self.converted_project = project`, `self.status = "converted"`;
      **one `transaction.atomic()`**; returns the project. Idempotent-guard: refuse if
      `self.converted_project_id` is already set.
- [ ] `form excludes:` `tenant`, `number` (auto), `status`, `decision`, `decided_by`,
      `decided_at`, `submitted_at`, `converted_project`, `created_by`

---

### Model 2 — `Project` [PRJ-] (`models/ProjectInitiation/Projects.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PRJ"`. 23 declared + 4 inherited = **27 fields**.
Realizes bullet **3 Project Charter Authoring**; the container every later `7.M` FKs into.

#### Choices (exact machine values)
- [ ] `METHODOLOGY_CHOICES` — `waterfall`/Waterfall, `agile`/Agile, `hybrid`/Hybrid (the template
      *library* behind this is 7.19's)
- [ ] `CHARTER_STATUS_CHOICES` — `draft`/Draft, `submitted`/Submitted, `approved`/Approved,
      `rejected`/Rejected
- [ ] `STATUS_CHOICES` — `draft`/Draft, `chartered`/Chartered, `kickoff`/Kickoff, `active`/Active,
      `on_hold`/On Hold, `completed`/Completed, `cancelled`/Cancelled

#### Fields
- [ ] `name` `CharField(max_length=255)`
- [ ] `code` `CharField(max_length=30, blank=True)`
- [ ] `request` `FK("projects.ProjectRequest", SET_NULL, null=True, blank=True, related_name="projects")`
      — provenance, **set by the convert verb only**
- [ ] `methodology` `CharField(max_length=12, choices=METHODOLOGY_CHOICES, default="hybrid")`
- [ ] `in_scope` `TextField(blank=True)`
- [ ] `out_of_scope` `TextField(blank=True)`
- [ ] `objectives` `TextField(blank=True)`
- [ ] `success_criteria` `TextField(blank=True, help_text="Measurable — PM²")`
- [ ] `assumptions` `TextField(blank=True)`
- [ ] `constraints` `TextField(blank=True)`
- [ ] `risk_summary` `TextField(blank=True, help_text="Charter-level; the register is 7.5's")`
- [ ] `executive_sponsor` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sponsored_projects")`
- [ ] `project_manager` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="managed_projects")`
- [ ] `org_unit` `FK("core.OrgUnit", SET_NULL, null=True, blank=True, related_name="projects")`
- [ ] `client` `FK("core.Party", SET_NULL, null=True, blank=True, related_name="delivery_projects")`
- [ ] `start_date` `DateField(null=True, blank=True, help_text="Charter target; the frozen baseline is 7.2's")`
- [ ] `end_date` `DateField(null=True, blank=True)`
- [ ] `charter_status` `CharField(max_length=12, choices=CHARTER_STATUS_CHOICES, default="draft")`
      — **verb-driven, NOT on the form**
- [ ] `charter_approved_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`
- [ ] `charter_approved_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `charter_document` `FK("core.Document", SET_NULL, null=True, blank=True, related_name="project_charters")`
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` — **verb-driven,
      NOT on the form**
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

#### Derived / Meta / behaviour
- [ ] `is_overdue` property — `end_date` set and `< timezone.localdate()` and `status not in
      ("completed","cancelled")`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`
- [ ] indexes: `("tenant","status")` `prj_tnt_status_idx`, `("tenant","charter_status")`
      `prj_tnt_charter_idx`, `("tenant","client")` `prj_tnt_client_idx`, `("tenant","org_unit")`
      `prj_tnt_ou_idx`
- [ ] Docstring MUST carry the three-`PRJ-` stand-in note (table above)
- [ ] `form excludes:` `tenant`, `number`, `request`, `charter_status`, `charter_approved_by`,
      `charter_approved_at`, `status`, `created_by`

---

### Model 3 — `ProjectStakeholder` [PST-] (`models/ProjectInitiation/ProjectStakeholders.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PST"`. 13 declared + 4 inherited = **17 fields**.
Realizes bullet **4 Stakeholder Identification & Analysis**. The register *is* the RACI matrix and
the engagement plan — no second artefact table.

#### Choices (exact machine values)
- [ ] `STAKEHOLDER_TYPE_CHOICES` — `sponsor`/Sponsor, `approver`/Approver,
      `resource_provider`/Resource Provider, `subject_matter_expert`/Subject Matter Expert,
      `affected`/Affected Party, `team_member`/Team Member, `other`/Other
- [ ] `RACI_ROLE_CHOICES` — `r`/"R (Responsible)", `a`/"A (Accountable)", `c`/"C (Consulted)",
      `i`/"I (Informed)"
- [ ] `INFLUENCE_CHOICES` — `high`/High, `medium`/Medium, `low`/Low
- [ ] `INTEREST_CHOICES` — `high`/High, `medium`/Medium, `low`/Low
- [ ] `COMMS_PREFERENCE_CHOICES` — `email`/Email, `meeting`/Meeting, `written_report`/Written
      Report, `portal`/Portal, `none`/None
- [ ] `COMMS_FREQUENCY_CHOICES` — `daily`/Daily, `weekly`/Weekly, `monthly`/Monthly,
      `at_milestone`/At Milestone, `ad_hoc`/Ad-hoc
- [ ] `ENGAGEMENT_STRATEGY_CHOICES` — `manage_closely`/Manage Closely, `keep_satisfied`/Keep
      Satisfied, `keep_informed`/Keep Informed, `monitor`/Monitor — **a derived label set, NOT a
      column** (it exists so the template has `get_…`-style labels to render)

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="stakeholders")`
- [ ] `party` `FK("core.Party", SET_NULL, null=True, blank=True, related_name="project_stakeholders")`
      — a person *or* an organisation, internal *or* external; **employees are a `PartyRole`,
      never a second person master**
- [ ] `user` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="project_stakeholders")`
- [ ] `stakeholder_type` `CharField(max_length=24, choices=STAKEHOLDER_TYPE_CHOICES, default="other")`
- [ ] `raci_role` `CharField(max_length=1, choices=RACI_ROLE_CHOICES, default="i")`
- [ ] `raci_scope` `CharField(max_length=120, blank=True, help_text="What this RACI assignment covers, e.g. 'charter approval'")`
- [ ] `influence` `CharField(max_length=8, choices=INFLUENCE_CHOICES, default="medium")`
- [ ] `interest` `CharField(max_length=8, choices=INTEREST_CHOICES, default="medium")`
- [ ] `comms_preference` `CharField(max_length=16, choices=COMMS_PREFERENCE_CHOICES, default="email")`
- [ ] `comms_frequency` `CharField(max_length=16, choices=COMMS_FREQUENCY_CHOICES, default="weekly")`
- [ ] `attending_kickoff` `BooleanField(default=False)` — the attendee list **without an M2M**
- [ ] `notes` `TextField(blank=True)`
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

#### Derived / Meta / behaviour
- [ ] `engagement_strategy` property — `hi_inf = (influence == "high")`,
      `hi_int = (interest == "high")`; high/high → `manage_closely`, high/low → `keep_satisfied`,
      low/high → `keep_informed`, else `monitor`. **Document that `medium` maps to the low side** —
      it must not be left ambiguous.
- [ ] `ordering = ["-created_at", "-id"]` — **the research's `["-influence","party__name"]` is
      overridden, see override #1**
- [ ] `unique_together = ("tenant", "number")` **and** `("tenant", "project", "party", "raci_scope")`
      — plus the form-level `clean()` from override #2
- [ ] indexes: `("tenant","project")` `pst_tnt_project_idx`, `("tenant","stakeholder_type")`
      `pst_tnt_type_idx`
- [ ] `form excludes:` `tenant`, `number`, `created_by`. `project` is an explicit, tenant-scoped
      `ModelChoiceField`.
- [ ] **`org_unit` is NOT added** (the research's optional 5th FK). Four nullables on one row is
      enough; a department-as-stakeholder is modelled as a `party` of the organisation. Recorded
      under Later passes.

---

### Model 4 — `ProjectKickoff` [PKO-] (`models/ProjectInitiation/ProjectKickoffs.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PKO"`. 13 declared + 4 inherited = **17 fields**.
Realizes bullet **5 Project Kickoff & Launch**. **First to drop if the pass runs long.**

#### Choices (exact machine values)
- [ ] `AGENDA_TEMPLATE_CHOICES` — `standard`/Standard, `agile`/Agile, `client_facing`/Client-Facing,
      `custom`/Custom (the reusable template *library* is 7.19's)
- [ ] `STATUS_CHOICES` — `planned`/Planned, `scheduled`/Scheduled, `held`/Held, `completed`/Completed

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="kickoffs")` — **plain FK +
      `unique_together`, NOT a `OneToOneField`** (a OneToOne fights a partially-created row)
- [ ] `meeting_date` `DateTimeField(null=True, blank=True)`
- [ ] `location_or_link` `CharField(max_length=255, blank=True)`
- [ ] `agenda_template` `CharField(max_length=16, choices=AGENDA_TEMPLATE_CHOICES, default="standard")`
- [ ] `agenda` `TextField(blank=True)`
- [ ] `attendee_summary` `TextField(blank=True, help_text="External attendees not on the stakeholder register")`
- [ ] `onboarding_notes` `TextField(blank=True, help_text="Individual items are core.Activity(kind='task') rows on the project")`
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="planned")` — **verb-driven,
      NOT on the form**
- [ ] `baseline_acknowledged_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `baseline_acknowledged_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`
- [ ] `completed_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `notes` `TextField(blank=True)`
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")`

#### Derived / Meta / behaviour
- [ ] `attendee_count` property — `project.stakeholders.filter(attending_kickoff=True).count()`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")` **and**
      `("tenant","project")` `pko_tnt_project_idx`
- [ ] indexes: `("tenant","project")` `pko_tnt_project_idx`, `("tenant","status")`
      `pko_tnt_status_idx`
- [ ] Docstring must state: **the baseline *record* is 7.2's** — this row attests that the ceremony
      happened.
- [ ] `form excludes:` `tenant`, `number`, `status`, `baseline_acknowledged_at`,
      `baseline_acknowledged_by`, `completed_at`, `created_by`

---

## Scaffold (brand-new app — one file per commit)

- [ ] `apps/projects/__init__.py`
- [ ] `apps/projects/apps.py` — `ProjectsConfig(AppConfig)`: `default_auto_field =
      "django.db.models.BigAutoField"`, `name = "apps.projects"`, `verbose_name = "Project
      Management"` (mirror `apps/procurement/apps.py`)
- [ ] `apps/projects/models/__init__.py` (re-export block added at Integrate),
      `apps/projects/models/_base.py` — **copy `apps/scm/models/_base.py:53-86` verbatim in shape**:
      `TenantOwned` (`tenant` FK `related_name="+"` + `created_at`/`updated_at`) and
      `TenantNumbered` (`NUMBER_PREFIX = ""`, `number = CharField(max_length=20, editable=False)`,
      `save()` minting via `next_number` with the 5-attempt `IntegrityError` retry), plus the
      `q2`/`q4`/`ZERO` money helpers and `from apps.core.utils import next_number`
- [ ] `apps/projects/forms/__init__.py` + `apps/projects/forms/_common.py` — `from
      apps.core.forms import TenantModelForm`, `TenantUniqueMixin` (stamps `instance.tenant` before
      `full_clean()`), and a `_reject_foreign` helper: a narrowed `<select>` is UX, **not an
      authorization boundary**, so every tenant-scoped FK is re-checked on POST and rendered as a
      field error. Copy the proven `apps/procurement/forms/_common.py` shape.
- [ ] `apps/projects/views/__init__.py` + `apps/projects/views/_common.py` — star-import toolkit
      (`login_required`, `messages`, `get_object_or_404`, `redirect`, `render`, `timezone`,
      `require_POST`, the five `crud_*` helpers, `tenant_admin_required`,
      `write_audit_log`) — copy `apps/procurement/views/_common.py`
- [ ] `apps/projects/urls/__init__.py` — sets `app_name = "projects"` and concatenates; docstring
      states the invariant that **every first path segment is a literal** (no converter in the
      first component), so no module can shadow another
- [ ] `apps/projects/admin.py` — `@admin.register(...)` + `ModelAdmin` per model with `list_display`
      led by `number` (the `apps/procurement/admin.py:84-91` pattern)
- [ ] `apps/projects/migrations/__init__.py`
- [ ] `apps/projects/management/__init__.py`, `apps/projects/management/commands/__init__.py`,
      `apps/projects/management/commands/seed_projects.py`
- [ ] `apps/projects/tests/__init__.py`
- [ ] **`config/settings.py`** — add `"apps.projects"` to `INSTALLED_APPS` after `"apps.procurement"`
      (line ~53) — **Integrate phase only**; the check-after-edit hook blocks adding it before the
      app files exist (L12)
- [ ] **`config/urls.py`** — add `path("projects/", include("apps.projects.urls")),` after the
      `procurement/` line (line 18) — **Integrate phase only**
- [ ] `templates/projects/` directory created (the four entity folders come with the entities)

## Backend (`apps/projects/{models,forms,views,urls}/ProjectInitiation/`)

One `<Entity>.py` per model, the four layers lining up one-to-one. Entity files:
`ProjectRequests.py`, `Projects.py`, `ProjectStakeholders.py`, `ProjectKickoffs.py`.

- [ ] `models/ProjectInitiation/ProjectRequests.py` — `ProjectRequest` + choices + `convert_to_project()`
- [ ] `models/ProjectInitiation/Projects.py` — `Project` + choices (docstring = the 3-`PRJ-` note)
- [ ] `models/ProjectInitiation/ProjectStakeholders.py` — `ProjectStakeholder` + choices + `clean()`
- [ ] `models/ProjectInitiation/ProjectKickoffs.py` — `ProjectKickoff` + choices
- [ ] `forms/ProjectInitiation/<Entity>.py` — one `TenantUniqueMixin, TenantModelForm` per model with
      the pinned `Meta.fields` and exclusions; **plus `ProjectRequestDecisionForm`**
      (`reason = CharField(widget=Textarea, required=True)`) shared by the reject and
      return-for-information verbs
- [ ] `views/ProjectInitiation/<Entity>.py` — full CRUD + the verbs below
- [ ] `urls/ProjectInitiation/<Entity>.py` — literal routes before `<int:pk>/`
- [ ] **re-export blocks added to all four `__init__.py`** (models / forms / views / urls) at
      Integrate — forgetting one is an `ImportError` at runtime
- [ ] migration: `makemigrations projects` → `0001_initial`
- [ ] extend `seed_projects` (the app is new, so the command is new — not an "extend")

## Views, routes & CONTEXT KEYS (the contract — L7/L8: an unpinned name renders blank at 200)

Entity stems are `prq_` / `prj_` / `pst_` / `pko_` (the `pdocument_list` precedent).

- [ ] **ProjectRequest** — `prq_list` (list var `object_list` + `page_obj` + `q`),
      `prq_create`, `prq_detail` (`obj`), `prq_edit` (`obj`), `prq_delete`
      Routes: `project-requests/` (+ `add/`, `<int:pk>/`, `<int:pk>/edit/`, `<int:pk>/delete/`)
      Verbs (all `@require_POST`): `project-requests/<int:pk>/submit/` `prq_submit`,
      `…/approve/` `prq_approve` (**`@tenant_admin_required`**),
      `…/reject/` `prq_reject` (**`@tenant_admin_required`**),
      `…/return/` `prq_return_for_information`,
      `…/convert/` `prq_convert` (**`@tenant_admin_required`** — the single highest-value verb in
      the sub-module)
      Extra list context: `status_choices`, `request_type_choices`, `priority_choices`,
      `risk_rating_choices`, `feasibility_choices`, `decision_choices`, `org_units`
      Extra detail context: `obj`, `decision_form`
- [ ] **Project** — `prj_list`, `prj_create`, `prj_detail` (`obj`), `prj_edit` (`obj`), `prj_delete`
      Routes: `projects/` (+ `add/`, `<int:pk>/`, `<int:pk>/edit/`, `<int:pk>/delete/`)
      Verbs: `projects/<int:pk>/submit-charter/` `prj_submit_charter`,
      `projects/<int:pk>/approve-charter/` `prj_approve_charter` (**`@tenant_admin_required`**)
      Extra list context: `status_choices`, `charter_status_choices`, `methodology_choices`,
      `org_units`, `clients`
      Extra detail context: `obj`, `stakeholders` (reverse, capped at 50), `kickoffs` (reverse),
      `source_request`
- [ ] **ProjectStakeholder** — `pst_list`, `pst_create`, `pst_detail` (`obj`), `pst_edit` (`obj`),
      `pst_delete`. Routes: `stakeholders/` (+ the four). No verbs.
      List queryset annotates `influence_rank` with
      `Case(When(influence="high", then=3), When(influence="medium", then=2), default=1)` and orders
      `("-influence_rank", "id")` — **this is how override #1 keeps the research's intent with
      correct semantics**
      Extra list context: `projects`, `stakeholder_type_choices`, `raci_role_choices`,
      `influence_choices`, `interest_choices`
- [ ] **ProjectKickoff** — `pko_list`, `pko_create`, `pko_detail` (`obj`), `pko_edit` (`obj`),
      `pko_delete`. Routes: `kickoffs/` (+ the four)
      Verbs (`@require_POST`): `kickoffs/<int:pk>/schedule/` `pko_schedule`,
      `…/mark-held/` `pko_mark_held` (sets `Project.status = "kickoff"`),
      `…/complete/` `pko_complete` (sets `completed_at` **and** `Project.status = "active"`),
      `…/baseline/` `pko_mark_baseline_set` (stamps `baseline_acknowledged_at/by`)
      Extra list context: `projects`, `status_choices`, `agenda_template_choices`
      Extra detail context: `obj`, `attending` (project stakeholders with `attending_kickoff=True`),
      `activities` (`core.Activity` rows GFK'd to the project — `kind="meeting"` and `kind="task"`,
      rendered read-only; **capture of individual items is 7.9's**)
- [ ] Every queryset is `filter(tenant=request.tenant)` — never `.all()`
- [ ] Every verb refuses a disallowed transition with a `messages.*` + redirect — never a 500,
      never a silent no-op; an action already in its target state says so and writes nothing
- [ ] Every `?enum=` filter value is allow-listed against the model's CHOICES before filtering
      (L11 — a junk value must be ignored, not silently empty the register)

## Wire-up (Integrate phase ONLY — single writer, surgical `Edit`, never a full rewrite: L43)

- [ ] One new `LIVE_LINKS["7.1"]` entry in `apps/core/navigation.py` (immediately after the
      `"6.19"` block at ~`:1701`), mapping each NavERP.md 7.1 bullet to a live route:
      - [ ] `"Project Request & Intake"` → `"projects:prq_list"`
      - [ ] `"Business Case & Feasibility"` → `"projects:prq_list?status=assessment"`
      - [ ] `"Project Charter Authoring"` → `"projects:prj_list"`
      - [ ] `"Stakeholder Identification & Analysis"` → `"projects:pst_list"`
      - [ ] `"Project Kickoff & Launch"` → `"projects:pko_list"`
- [ ] Add a comment recording the deliberate omissions, the house style: `Project` itself gets **no**
      bullet (it is the container the other four hang off, not a feature), `ProjectRequest`'s
      economics get no bullet of their own (they are bullet 2's field set), and no bullet points at
      a login-gated portal view (L32).

## Seeder (`apps/projects/management/commands/seed_projects.py`)

Idempotent, per-tenant, reusing existing rows. Guard: `if ProjectRequest.objects.filter(
tenant=tenant).exists(): print("Data already exists. Use --flush to re-seed."); continue`, and
per-row guards on `(tenant, title)` so a second run is a no-op.

- [ ] Reuse, never invent: `OrgUnit.objects.filter(tenant=tenant).order_by("id").first()`;
      a `core.Party` carrying a customer `PartyRole` (`PartyRole.objects.filter(tenant=tenant,
      role="customer")` → first, else any party); `Currency.objects.order_by("id").first()`
      (**global, no tenant — L29**); `get_user_model().objects.filter(tenant=tenant).order_by("id")`
      for requester / approver / sponsor / manager
- [ ] Skip gracefully (message, not a crash) when the tenant has no `OrgUnit`/`Party`/`Currency` —
      print "run seed_core / seed_accounting first"
- [ ] **9 `ProjectRequest` rows** covering every status, so every badge and filter facet has an
      honest row and `per_page=15` yields 2 pages: `draft`, `submitted`, `screening`,
      `assessment` (cost 120000 / benefit 260000, `risk_rating="high"`,
      `strategic_alignment=4`, `feasibility="feasible_with_constraints"`), `needs_information`
      (`information_requested` filled), **`approved` #1 — converted at seed time through the real
      `convert_to_project()` path** (so `converted_project` and `Project.request` are honest),
      **`approved` #2 — left unconverted so the Convert verb is exercisable in smoke**,
      `rejected` (`rejection_reason` + `decision="no_go"`), `deferred`
- [ ] **3 `Project` rows**: the one converted from request #6 (`status="chartered"`), one standalone
      (`status="draft"`, `charter_status="draft"`), one fully walked
      (`charter_status="approved"`, `status="active"`)
- [ ] **6 `ProjectStakeholder` rows** on the chartered project: one per RACI value (`r`/`a`/`c`/`i`),
      covering sponsor / approver / subject_matter_expert / affected / team_member, covering all
      four influence×interest quadrants at least once, mixed `comms_preference`/`comms_frequency`,
      3 with `attending_kickoff=True`
- [ ] **2 `ProjectKickoff` rows**: one `completed` (with `baseline_acknowledged_at` set, on the
      active project) and one `scheduled` (on the chartered project)
- [ ] **4 `core.Activity` rows** GFK'd to the active project: 1 `kind="meeting"` (the kickoff) + 3
      `kind="task"` onboarding items (access provisioned, tooling set up, intro to sponsor)
- [ ] `write_audit_log(user=None, …)` rows for the seeded decisions (rendered "System"), each with
      an **action ≤ 10 chars**
- [ ] Print the tenant-admin logins to use, plus the warning: *"Superuser 'admin' has no tenant —
      data won't appear when logged in as admin"*

## Templates (`templates/projects/initiation/<entity>/{list,detail,form}.html`)

- [ ] `projectrequest/{list,detail,form}.html` — list: filter bar (status, request_type, priority,
      risk_rating, feasibility, org_unit, decision) reflecting `request.GET` + Actions column
      (view / edit / delete-POST + `onclick="return confirm(...)"` + `{% csrf_token %}`) +
      pagination with `has_previous`/`has_next` guards (L9) + empty state
- [ ] `project/{list,detail,form}.html` — filters: status, charter_status, methodology, org_unit,
      client. Detail carries the stakeholder register, the kickoff list and the source request.
- [ ] `projectstakeholder/{list,detail,form}.html` — filters: project, stakeholder_type, raci_role,
      influence, interest
- [ ] `projectkickoff/{list,detail,form}.html` — filters: project, status, agenda_template.
      Detail renders the attendee list and the project's `core.Activity` rows.
- [ ] Badges use **colour-named theme.css classes only** — `badge-green` / `badge-red` /
      `badge-amber` / `badge-info` / `badge-muted` / `badge-slate`. `badge-success` /
      `badge-danger` **do not exist** (L33). Every badge block ends with an
      `{% else %}{{ obj.get_<field>_display }}{% endif %}` fallback.
- [ ] FK `<select>` comparisons use `|stringformat:"d"` for pks — never `|slugify`
- [ ] `{% extends "base.html" %}` unchanged; partials stay at the templates root

## Verify

- [ ] `python manage.py makemigrations projects` → `0001_initial`; `python manage.py migrate`
- [ ] `python manage.py check` (run it *immediately after* the `INSTALLED_APPS` edit too)
- [ ] `python manage.py seed_projects` ×2 — second run is a no-op without `--flush`
- [ ] `temp/` smoke sweep as **`admin_acme` / `password`** (NOT the tenant-less `admin`):
      - [ ] every new `projects:*` url returns 200 (or 302 for the POST-only verbs hit by GET)
      - [ ] content assertions, not just status — page titles, a seeded record's number present,
            no `{#` / `{% comment` leaks (L8: a mismatched context var returns 200 and renders blank)
      - [ ] junk-params: `?status=nope`, `?project=0`, `?project=²`, `?page=9999` → default page,
            never a 500 and never an empty register
      - [ ] page 2 of the request register (9 rows / 15 per page → 2 pages)
      - [ ] cross-tenant IDOR → 404 on every `<int:pk>` route
      - [ ] the convert verb actually creates a `Project` and links both directions
      - [ ] `admin` (superuser, `tenant=None`) sees empty lists — by design, not a bug
- [ ] Sidebar shows **7.1 Live** with all five bullets linked

## Close-out (Module Creation Sequence phases 4–7)

- [ ] Review agents, **one after another**, each appending to
      `.claude/tasks/review-projects-7.1.md`: `code-reviewer` → `explorer` → `frontend-reviewer` →
      `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`
- [ ] `code-fixer` burns the deduped, ID'd findings down (Critical → Important → Minor), one commit
      per file
- [ ] Tests: contract + `conftest.py`, then `test_initiation_models.py` →
      `test_initiation_forms.py` → `test_initiation_views.py` → `test_initiation_security.py`, one
      file per commit, then **one full unfiltered run** (never `-k`, L47)
- [ ] **Author** `.claude/skills/projects/SKILL.md` — it does **not** exist yet (`.claude/skills/`
      holds accounting, crm, hrm, inventory, procurement, scm only). Same body sections as the
      siblings: overview, models + spine reuse, urls/routes, templates, seeder, conventions &
      gotchas (tenant scoping, the context-var contract, **the three-`PRJ-` note**), common tasks,
      sidebar wiring.
- [ ] Mark 7.1 complete in `README.md`

## Later passes / deferred (carried from the research so nothing is lost)

- **7.2** — WBS, task sequencing & dependencies (FS/SS/lag/lead), critical path, duration &
  effort estimating with confidence ranges, milestone & phase-gate definition, **schedule baseline
  + baseline versions** (7.1 only attests the ceremony), what-if scenarios, fast-tracking/crashing.
  7.2 also inherits the open `crm.CrmMilestone` (1.8) vs `projects.Milestone` question.
- **7.3** — resource pool & skills inventory, allocation & leveling, team assembly & role
  assignment, resource forecasting & demand planning, timesheets (7.1's `required_resources` is
  free text only).
- **7.4** — budget planning & estimation, cost baseline & control accounts, EVM, expense tracking &
  commitments, EAC/CPI/SPI, change control. **7.1 ships no money columns on `Project`.**
- **7.5** — risk register with probability/impact matrices, **Monte Carlo**, EMV, risk response
  planning (7.1's `risk_adjusted_benefit` is a documented flat factor, deliberately not this).
- **7.6 / 7.7** — quality management; the requirements register (7.1's `in_scope`/`out_of_scope`
  are charter-level only).
- **7.9** — meeting minutes and action-item tracking (7.1's `core.Activity` rows cover the action
  items; minutes are 7.9's); stakeholder voting/reactions on ideas (JPD).
- **7.12 / 7.16 / 7.17 / 7.19** — portfolio scoring & demand-vs-capacity ranking; reporting/BI and
  dashboards; approval workflow engines and configurable intake forms; **project templates &
  methodologies** (the reusable template library behind `methodology` and `agenda_template`, the
  charter-from-template feature, intake form definitions and their submission analytics).
- **7.14 / 7.15** — the client portal, SOW and project billing (7.1 carries only the `client`
  identity).
- **Not scheduled** — `ProjectStakeholder.org_unit` (the research's optional 5th FK, for "this whole
  department is a stakeholder"); the `promoted_to` self-FK that would model ServiceNow/JPD
  idea→demand promotion inside the one register (**deliberately left out of the model this pass —
  it needs a promote verb to be meaningful, and `request_type="idea"` already carries the
  lighter-weight case**); a split-out `BusinessCase` [PBC-] table if a charter-level business case
  with its own approver and version history is ever wanted (the field names on `ProjectRequest` are
  already grouped for it).
- **Upstream, not this pass** — `core.AuditLog.action` is `varchar(10)` while the ecosystem keeps
  writing longer verbs (6.19 hit this too). 7.1 stays inside 10 chars; the fix is a `core`
  migration, which is single-writer work for a session that owns `core`.

## Review notes

**Delivered.** 7.1 Project Initiation & Charter — 4 models (`ProjectRequest` [PRQ-], `Project`
[PRJ-], `ProjectStakeholder` [PST-], `ProjectKickoff` [PKO-]), 5 forms, 32 routes / 27 views + 15
POST verbs, 13 templates, `seed_projects` (9/3/6/2 per tenant, idempotent), migrations `0001` +
`0002`, `LIVE_LINKS["7.1"]`, a new `.claude/skills/projects/SKILL.md`, and **1243 tests green on a
full unfiltered run**. `manage.py check` clean; `makemigrations --check` clean.

### What the phases actually caught

The value was not evenly distributed, and it is worth recording where it came from.

- **Smoke gate (Phase 3)** — four pages were **hard 500s** on real seeded data: a nullable FK
  dereferenced inside a `|default:` **filter argument**. Django resolves filter arguments eagerly
  and `string_if_invalid` only rescues the *main* variable, so a NULL FK in an argument takes the
  whole page down. 15 sites / 6 templates. The seeder is what exposed it — half its stakeholder rows
  deliberately leave `party` NULL.
- **Six reviewers (Phase 4)** — 60 raw findings, deduped to 36. **Three Critical, all state-machine,
  none visible to a status-code check:** `approved` was unreachable through the UI so the headline
  `prq_convert` verb was dead (the seeder pre-baked an approved row and hid it); `pko_complete`
  skipped both ceremony gates and drove a project to `active` with an unapproved charter, routing
  *around* the tenant-admin gate on `prj_approve_charter`; and `convert_to_project()` guarded the
  in-memory instance outside its atomic block, so two concurrent POSTs minted two projects.
- **Tests (Phase 6)** — found **three more real defects the six reviewers missed** (P1 user-only
  stakeholder duplicates, S1 an approved charter destroyable by any member, S2 a completed kickoff's
  minutes rewritable under its own stamp). Writing tests against the as-fixed code turned out to be
  its own review pass, not just regression insurance.

### Judgement calls worth keeping

- **S1 was closed with a state guard, not a role gate.** A role gate would have left the same
  evidence destroyable by the very tenant admin whose signature it is, and it would have broken a
  test that deliberately encodes the login-only delete house style (287 of 393 delete views
  app-wide). The state guard closes it for every actor. This matches how the codebase already
  protects attested rows (`journal_entry_delete` refuses `is_locked`; `bill_delete` refuses
  non-drafts).
- **The I1 core-forms hardening was tried, measured and reverted.** Making `TenantModelForm` fail
  closed (`.none()` when tenant is falsy) fails 10 tests in `inventory` and `procurement` that
  *encode the current contract*. The 7.1 half (hoisting the guard to the first line of the four
  create views) landed; the shared-file half needs its own pass that can run the full suite.
- **`influence_rank`'s filesort was left alone** — the `Case/When` is the correct *correctness* fix
  (`"-influence"` sorts alphabetically wrong) and is N+1-free; making it index-supported needs
  integer choice fields. Recorded as an explicit trade rather than assumed away.
- **The evidence model is the module's organising idea**, and it is what made several findings
  cohere: once a request is decided, a charter approved, or a ceremony attested, the row stops being
  editable. *You cannot forge the signature, so you must not be able to change what it signs.*

### Spun off deliberately (not silently dropped)

- The **same `|default:` FK-argument idiom exists in ~59 more sites** across procurement (28), scm
  (23), hrm (6) and crm (2) — each a 500 waiting for its FK to be NULL. Out of scope here and a
  cross-module sweep risks L43 collisions; raised as its own task.
- The **`apps/core/forms/_common.py` fail-closed hardening** and the **`ProcurementAlerts.py:82`
  guard clone** (the only other place in the tree with the misplaced-guard shape).
- **`core.AuditLog.action` is `varchar(10)`** while the ecosystem keeps writing longer verbs — a
  `core` migration, single-writer work for a session that owns `core`.
- **`TenantNumbered.save()` reads every `IntegrityError` as a number collision** — shared boilerplate
  in six apps; today nothing lands with an empty number, but the fallthrough is latent.

### Known-open, by decision

`charter_status="rejected"` is a reserved choice no verb sets (dropping it needs a second migration
and forecloses a 7.x reject-charter verb); `pko_complete`'s success message sits outside its status
guard, so an `on_hold` project is told it "is now active" — wording only, the status behaviour is
correct and pinned by a test.


---

## Projects 7.2 — Project Planning & Scheduling (build record)

**Delivered (one sub-module, per the /next-module rule):** 4 models — `ProjectTask` [TSK-]
(the WBS node and the schedulable activity in one row: `deliverable` rollups + the `1.2.3` code
are computed in the tree view, never stored; `duration_days` is a property), `TaskDependency`
[DEP-] (four link kinds, signed lag/lead, same-project clean() guard), `ProjectMilestone` [MST-]
(phase gates with entry/exit criteria; `save()` stamps `actual_date` exactly once on `achieved`
and clears it on reopen), `ScheduleBaseline` [BSL-] (frozen rows refuse edit/delete;
`freeze_snapshot()` writes the summary snapshot columns at freeze time; `bsl_activate` /
`bsl_promote` keep exactly one active baseline per project atomically — deliberately NO
conditional unique constraint, MariaDB can't enforce one).

**Surfaces:** 4 forms, 22 routes (tsk 6 incl. `tasks/tree/`, dep 5, mst 6, bsl 7), 19 views
(3 admin-gated verbs `mst_achieve` / `bsl_activate` / `bsl_promote`), 14 templates incl. the
recursive WBS tree (`_tree_node.html`), migration 0003, seeder 7.2 block (idempotent, own guard —
19 TSK / 9 DEP / 9 MST / 3 BSL per tenant, `--flush` extended), admin registrations,
`LIVE_LINKS["7.2"]` (5 bullets + extra "Task Register"), overview page counts + quick links.

**Key design decisions:** the critical path is the longest dependency chain, computed on read by
`critical_path_ids()` (memoised DFS, cycle-guarded; full CPM float is 7.16's); the tree walks
`node.kids` (decorated instances) NOT `node.children.all` — prefetch_related would fetch
children as distinct Python objects and render undecorated rows (caught in smoke); no money
columns (7.4) and no execution actuals (7.8 extends `ProjectTask` in place); baselines snapshot
summary figures only — task-level snapshots are a documented future extension.

**Verification:** migrate OK; seed x2 idempotent; `manage.py check` + `makemigrations --check`
clean; smoke script (`temp/smoke_72.py` + `temp/smoke_72_verbs.py`): all 17 GET pages 200 with
content asserts, junk params safe, page 2 works, verbs POST-only (405 on GET), frozen guards
hold, promote/achieve stamps written once, member users 403 on gated verbs, cross-tenant IDOR
404 on all four entities. 7.1 behavior untouched (stakeholder/kickoff/selection flow byte-faithful).

---

## Projects 7.3 — Resource Management (build todo)

Plan from `research-projects-7.3.md` (2026-09-10). Extends `apps/projects` — no scaffold. Package **`ResourceManagement/`** in all four layers; template sub-module slug **`templates/projects/resource/`**; entity stems **`rsp_` / `ral_` / `rte_`**. New first segments `resource-profiles/`, `allocations/`, `time-entries/`, `capacity-demand/` — disjoint from 7.1/7.2's literals. Spine re-verified (L28): `hrm.EmployeeProfile` (`EmployeeProfiles.py:8`), `hrm.EmployeeSkill` (`Employeeskill.py:5`), `core.Party`/`PartyRole`/`OrgUnit`, `projects.Project/ProjectRequest/ProjectTask` all exist; prefixes `RSP`/`RAL`/`RTE` unused repo-wide (`crm.ResourceAllocation` [RA-] and `crm.Timesheet` [TS-] stay untouched stand-ins).

### 1. Models

- [ ] Freeze `.claude/tasks/contract-projects-7.3.md` first (Phase 3 step 1): every field/CHOICES value, form `Meta.fields` + exclusions, url names, **every context key** (L7/L8).
- [ ] `models/ResourceManagement/ResourceProfiles.py` — **ResourceProfile [RSP-]** (TenantNumbered): `employee` FK `"hrm.EmployeeProfile"` SET_NULL null blank (internal staff); `party` FK `"core.Party"` SET_NULL null blank (external) — **exactly one of the two**; `resource_type` (internal/contractor/freelancer/consultant, default `internal`); `default_role` CharField(80); `org_unit` FK `"core.OrgUnit"` SET_NULL null blank; `skill_summary` CharField(255 blank) (matrix/certs stay the `hrm:employeeskill_list` lens — no skill table); `weekly_capacity_hours` Decimal(6,2) default 40, MinValueValidator 0; `utilization_target_pct` PositiveSmallInt default 80 (1–100); `available_from`/`available_to` DateField null blank (contractor window); `status` (active/inactive); `notes`. Property `name` (employee → party → number fallback). clean(): one-of employee/party + "employee already in this tenant's pool" ValidationError (deliberately NO conditional unique — 7.2 BSL/MariaDB precedent). Indexes (tenant, resource_type)/(tenant, status)/(tenant, employee)/(tenant, party). Form excludes: tenant, number, stamps.
- [ ] `models/ResourceManagement/ResourceAllocations.py` — **ResourceAllocation [RAL-]**: `project` FK `"projects.Project"` CASCADE null blank related_name=`allocations`; `project_request` FK `"projects.ProjectRequest"` SET_NULL null blank (pipeline demand); `project_task` FK `"projects.ProjectTask"` SET_NULL null blank; `resource` FK `"projects.ResourceProfile"` SET_NULL null blank (**NULL = placeholder**); `role_name` CharField(80) (the placeholder's whole identity); `skill_requirements` CharField(255 blank); `allocation_unit` (hours_per_week/pct_capacity/total_hours, default `hours_per_week`); `hours_per_week` Decimal(6,2) null blank; `pct_capacity` PositiveSmallInt null blank (1–100); `total_hours` Decimal(8,2) null blank; `start_date` DateField; `end_date` DateField null (= ongoing); `booking_status` (requested/soft/firm/completed/cancelled/released); `substitute_of` FK `"self"` SET_NULL null blank related_name=`substituted_by`; `requested_by` FK AUTH_USER_MODEL null blank; `notes`. clean(): project or project_request required; `end_date >= start_date`; exactly one magnitude matching allocation_unit. Computed: `planned_hours(win_start, win_end)` (copy proven `crm.ResourceAllocation.overlap_hours()` proration, extended to the 3 units) + `is_live` (today in window, status in soft/firm). Indexes (tenant, resource)/(tenant, project)/(tenant, project_request)/(tenant, booking_status)/(tenant, start_date). Form excludes: tenant, number, `booking_status` + `substitute_of` (verb-driven), `requested_by`.
- [ ] `models/ResourceManagement/ResourceTimeEntries.py` — **ResourceTimeEntry [RTE-]** (TenantNumbered): `resource` FK `"projects.ResourceProfile"` CASCADE; `project` FK `"projects.Project"` SET_NULL null blank (non-project time loggable); `project_task` FK `"projects.ProjectTask"` SET_NULL null blank; `entry_date` DateField; `hours` Decimal(5,2) MinValueValidator > 0; `task_description` CharField(255 blank); `status` (draft/submitted/approved/rejected); `submitted_at`/`approved_at` DateTime null **editable=False**; `approved_by` FK AUTH_USER_MODEL null blank editable=False; `decision_note` TextField blank (rejection reason); `notes` TextField blank. **No billable flag, no rates, no money columns** (7.11/7.4/7.15, L29); NOT a fourth timesheet — no header model. Guards: approval stamps written exactly once by the verbs and never rewound by edit; approved/rejected rows refuse edit/delete (7.1 evidence ruling). Indexes (tenant, resource, entry_date)/(tenant, project, entry_date)/(tenant, status). Form excludes: tenant, number, status + all stamps.

### 2. Backend (`apps/projects/{models,forms,views,urls}/ResourceManagement/`, one `<Entity>.py` per model per layer)

- [ ] **ResourceProfile**: `forms/…/ResourceProfiles.py` (TenantUniqueMixin + `_reject_foreign`; `status` stays ON the form — active/inactive is a lens toggle, not governance state), `views/…` `rsp_list/create/detail/edit/delete` (routes `resource-profiles/`; list filters: q, resource_type, status, org_unit; context `resource_type_choices`/`status_choices`/`org_units`; detail links to `hrm:employeeskill_list?employee=<pk>` lens).
- [ ] **ResourceAllocation**: forms (project/project_request/resource narrowed per tenant; `allocation_unit` drives conditional magnitude validation), views `ral_list/create/detail/edit/delete` (routes `allocations/`; filters: q, project, project_request, resource, booking_status, placeholder lens `?placeholder=True` (resource NULL), is_live; verbs all `@require_POST` + audited, audit action ≤ 10 chars): `ral_assign` (placeholder→named, **@tenant_admin_required**), `ral_substitute` (sets current → released + successor with `substitute_of`, **@tenant_admin_required**), `ral_commit` (requested→soft→firm one step), `ral_complete`, `ral_cancel`. Verbs refuse disallowed transitions with `messages.*` + redirect (never 500/silent).
- [ ] **ResourceTimeEntry**: views `rte_list/create/detail/edit/delete` (routes `time-entries/`; weekly lens grouped by resource + ISO week; filters: status, resource, project, year/week; **actuals-to-plan computed section**: approved hours vs `ResourceAllocation.planned_hours` per project/resource with variance); verbs: `rte_submit` (draft→submitted, stamps `submitted_at` once), `rte_approve` + `rte_reject` (submitted→, stamps approved_by/at + `decision_note`, **@tenant_admin_required**), `rte_approve_week` (route `time-entries/week/<int:resource>/<int:year>/w<int:week>/approve/`, bulk per person-week, **@tenant_admin_required**; literal `week/` segment precedes `<int:pk>`).
- [ ] Computed board page (no model): `views/…/CapacityDemand.py` `capacity_demand` (route `capacity-demand/`, GET) — per resource-week live `planned_hours` vs `weekly_capacity_hours` → **over-allocation alerts** (bullet 2) + section `id="demand"` splitting project-linked vs request-linked placeholders/soft bookings with a **coverage-gap lens** (bullet 4); page states the uniform-weekly-hours caveat (leave deduction is HRM 3.10's). Helpers shared by >1 register go in `views/_helpers.py` (`resource_profiles(tenant)`, `project_requests(tenant)`); every enum filter allow-listed against CHOICES (L11), parsed BEFORE pagination; every queryset `filter(tenant=request.tenant)`.
- [ ] `urls/ResourceManagement/<Entity>.py` ×3 + CapacityDemand — literal routes before `<int:pk>/`; **re-export blocks in all four `__init__.py`** at Integrate (forgetting one = ImportError).

### 3. Templates (`templates/projects/resource/<entity>/{list,detail,form}.html` — entity folders `resourceprofile/`, `resourceallocation/`, `resourcetimeentry/`)

- [ ] `resourceprofile/` — list: filter bar (q, resource_type, status, org_unit) + Actions column + pagination (`has_previous`/`has_next`, `partials/pagination.html`) + empty-state; detail: detail-grid + skills/certs lens link + edit/delete; form shared create/edit.
- [ ] `resourceallocation/` — list: filters (q, project, project_request, resource, booking_status, placeholder) + badge mapping requested/soft→muted/amber, firm→green, cancelled/released→red/slate; detail: **status-gated verb buttons** (assign on placeholders, substitute on live named rows, commit/complete/cancel per machine) POST-forms with confirm + `{% csrf_token %}`, tenant-admin-gated buttons hidden for members (mst_achieve precedent).
- [ ] `resourcetimeentry/` — list: weekly grouping + approval-queue lens (`?status=submitted`) + actuals-to-plan section; detail: submit/approve/reject buttons gated by status; form: no status/stamp fields.
- [ ] `capacity_demand.html` (standalone page at the sub-module root, rule 6) — capacity table + `id="demand"` section.
- [ ] Badges colour-named only (badge-green/red/amber/info/muted/slate — L33) with `{% else %}{{ obj.get_<field>_display }}` fallback; FK select comparisons `|stringformat:"d"`; `{% extends "base.html" %}` unchanged.

### 4. Integrate (single writer, surgical Edits, one file per commit)

- [ ] Re-export blocks in `apps/projects/{models,forms,views,urls}/__init__.py`; `urls/__init__.py` concatenates the four new modules after `_pp_baselines`.
- [ ] `admin.py`: register `ResourceProfile`/`ResourceAllocation`/`ResourceTimeEntry` (`list_display` led by `number`, `list_select_related`, readonly stamps).
- [ ] Seeder 7.3 block `_resourcing(tenant, now)` with **own guard** `ResourceProfile.objects.filter(tenant=tenant).exists()`; rows: ~5 ResourceProfiles (internal from tenant users/hrm rows if present, 1 contractor Party with engagement window, 1 part-time 24h — capacities varied so over-allocation is honest); ~10 RALs: firm named + soft named on the active project, **2 placeholders** (one project-linked, one **request-linked** on the unconverted approved request, `booking_status="requested"` + `skill_requirements` + `requested_by`), one completed past booking, one `released` + successor `substitute_of` chain; ~16 RTEs across resources/weeks covering every status (past approved, this-week submitted → approval queue, draft, rejected with `decision_note`) so page 2 is real; extend `--flush` (children first: RTE → RAL → RSP).
- [ ] `apps/core/navigation.py` — one `LIVE_LINKS["7.3"]` block (after `"7.2"` at ~`:1729`) mapping the exact NavERP.md bullets: "Resource Pool & Skills Inventory" → `projects:rsp_list`; "Resource Allocation & Leveling" → `projects:capacity_demand`; "Team Assembly & Role Assignment" → `projects:ral_list`; "Resource Forecasting & Demand Planning" → `projects:capacity_demand#demand`; "Time Tracking & Timesheets" → `projects:rte_list`; extra leaf "Time Approvals" → `projects:rte_list?status=submitted`.
- [ ] Migration **`0004`** — current highest is `0003_projecttask_projectmilestone_schedulebaseline_and_more.py`; 7.3 claims `0004_<...>.py` (makemigrations projects).
- [ ] `templates/projects/overview.html`: stat cards `resource_count`/`allocation_count`/`time_entry_count` + a 7.3 quick-links row + update the muted intro copy (line ~8).

### 5. Verify

- [ ] `makemigrations projects` → `0004`; `migrate`; `seed_projects` ×2 (second run no-op without `--flush`); `manage.py check` + `makemigrations --check`.
- [ ] `temp/smoke_73.py` as **admin_acme / password**: every new `projects:` url 200 with CONTENT asserts (titles, seeded RSP/RAL/RTE numbers, no `{#`/`{% comment` leaks); junk params (`?status=nope`, `?resource=0`, `?page=9999`) → default page, never 500; page 2 of rte register; verbs POST-only (GET → 405); member users 403 on tenant-admin verbs; cross-tenant IDOR → 404 on all `<int:pk>` routes of all three entities.
- [ ] Sidebar shows **7.3 Live** with all five bullets + Time Approvals leaf.

### 6. Close-out

- [ ] Six reviewers one after another → `.claude/tasks/review-projects-7.3.md` (code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer); `code-fixer` burns findings down.
- [ ] Tests: `apps/projects/tests/test_resource_models.py` → `test_resource_forms.py` → `test_resource_views.py` → `test_resource_security.py` (reuse `conftest.py`), one file per commit, one full unfiltered run.
- [ ] Update `.claude/skills/projects/SKILL.md` (7.3 models, routes, verbs, capacity board, stand-in notes); README row for 7.3.

### Later passes / deferred (carried from the research so nothing is lost)

- Leave-aware capacity deduction (HRM 3.10 integration); scenario/what-if planning; AI staffing optimizer; auto-filled timesheets from bookings; candidate comparison (margin is money); role rate cards (7.4/7.15); missing-timesheet nudges (7.17); equipment/meeting-room pools.
- Parked for siblings: task execution & assignment UX (7.8), money columns (7.4/7.15), deep timesheet UX + billable/overtime (7.11/HRM), portfolio capacity governance (7.12).

(Review notes: filled at close-out.)

---

## 7.4 Cost & Budget Management (Module 7: Project Management, `projects`) — plan from research-projects-7.4.md (2026-09-10)

### Concurrency notes (read first — peers are live in this tree)

- **7.2 is in review/fix** and **7.3 is building `ResourceManagement/`** in the same four layers of
  `apps/projects`. Every shared-file touch (`models/forms/views/urls __init__.py`, `admin.py`,
  `seed_projects.py`, `navigation.py`, `overview.html`, `tests/conftest.py`) is an **Integrate-step
  item**, done once, as a **surgical `Edit` with a re-read anchor** immediately before the edit.
- Commits are path-limited: `git add '<f>'; git commit -m '<msg>' -- '<f>'`.
- **Models are NOT re-exported from `models/__init__.py` until Integrate** — an early re-export
  changes the app's import surface under both peers. Entity files may be written and
  `makemigrations --dry-run`-checked, but the app must not import them until the block lands.
- The migration number is **assigned at generation time by the disk leaf** — never reserve `0004`
  (the research's guess; 7.3's plan also pins `0004`, so 7.4's is whatever the leaf says when the
  dry-run runs — likely `0005`).
- `research-projects-7.3.md` **has landed since the 7.4 research was written** (the research greps
  it as absent; 7.3's plan defers "role rate cards (7.4/7.15)" — consistent with Ruling 1).
  **Re-read it before Model 1**: 7.4 stores amounts, never rates; a 7.3 rate card may *generate*
  `amount`, it may not add rate fields to 7.4 rows.

### Scope, conventions, build order (research's 4 models — order rearranged for FK flow)

- [ ] 4 models, no fifth: `BudgetRevision` [BVR-], `CostControlAccount` [CCA-],
      `ProjectBudgetLine` [PBL-], `ProjectExpense` [PEX-]. Prefixes `PBL`/`BVR`/`CCA`/`PEX`
      verified free repo-wide; the cost baseline is the **approved `BudgetRevision`** — never a
      `CostBaseline`, never `BSL` (Ruling 2), and no `ChangeRequest` model (Ruling 3).
- [ ] **Build order: BudgetRevision → CostControlAccount → ProjectBudgetLine → ProjectExpense**
      (the research lists PBL first — catalog order, not dependency order; PBL FKs both BVR and
      CCA, PEX FKs CCA, while BVR/CCA touch only the spine, so they come first).
- [ ] All four: `TenantNumbered` subclasses, `NUMBER_PREFIX` as above, money = `DecimalField(14,2)`
      through `q2()`/`MAX_Q2` (`models/_base.py:28-38`), `MinValueValidator(0)` on every amount
      (the 0002 precedent), **rollups and ALL EVM metrics are computed properties/annotations,
      never stored columns**, audit actions ≤ 10 chars, `unique_together ("tenant","number")`.
- [ ] Layers: `apps/projects/{models,forms,views,urls}/CostManagement/<Entity>.py` (same file name
      in all four; sub-package `__init__.py` files stay EMPTY; re-exports only in the four
      top-level `__init__.py`). Files: `BudgetRevisions.py`, `CostControlAccounts.py`,
      `ProjectBudgetLines.py`, `ProjectExpenses.py` (plural, the 7.1/7.2 idiom).
- [ ] Templates: `templates/projects/cost/<entity>/{list,detail,form}.html` — **`cost/` confirmed
      consistent**: 7.1 used `initiation/`, 7.2 used `planning/` (short-slug rule; tree checked).
      Entity folders lowercase singular: `budgetrevision/`, `costcontrolaccount/`,
      `projectbudgetline/`, `projectexpense/`.
- [ ] FKs are declared **by string** (`"projects.Project"`, `"projects.ProjectTask"`,
      `"accounting.GLAccount"`, `"accounting.Currency"`, `"core.Party"`) — no cross-app model
      import at module level. `accounting.Currency` is GLOBAL, no `tenant` column (L29): form
      querysets never scope it and `clean()` never compares its tenant.

### Pinned deviations from the research sketches (each one line, said loudly)

1. **`BudgetRevision.decision_notes` is ADDED** — bullet 5's "rejection with a reason" row names
   it, but the sketch's field list omits it.
2. **`CostControlAccount.status` collapses to `planning/active/closed`** (sketch says four values
   then its own "keep it simple" parenthetical says leave it to planning/closed) — baseline
   membership is *derived* from the active revision, never a status value.
3. **`pex_edit`/`pex_delete` refuse `posted`/`void` rows** — posted cost rows are the evidence the
   EVM math reads; `pex_void` is the correction path (7.1's evidence model; the sketch only fixes
   edit refusal for approved revisions).
4. **`entry_date` pinned non-nullable and `source_kind` defaults to `manual`** — pins of values
   the sketch left unstated (a burn-trend row without a date is meaningless; manual is the only
   kind that needs no source document).
5. **Health cut-points pinned**: `over` = `cpi < 0.95` or `available < 0`, `watch` = `cpi < 1.00`
   — the sketch names the bands but not the numbers.

---

### Model 1 — `BudgetRevision` [BVR-] (`models/CostManagement/BudgetRevisions.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "BVR"`. 14 declared + 4 inherited = **18 fields**.
Realizes bullets **1 (the planning document)** and **5 (Change Control & Budget Revisions)** — one
table, both halves. The approved revision **is** the cost baseline; there is **no `is_active`
boolean**: the single row with `status="approved"` and `activated_at` set is the active baseline,
kept unique by the `bvr_activate` verb inside `transaction.atomic()` (the `ScheduleBaseline`
no-conditional-unique precedent).

#### Choices (exact machine values)
- [ ] `STATUS_CHOICES` — `draft`/Draft, `pending_approval`/Pending Approval, `approved`/Approved,
      `rejected`/Rejected, `superseded`/Superseded (machine values verbatim from the research)

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="budget_revisions")`
- [ ] `revision_no` `PositiveSmallIntegerField(default=0)` — 0 = the original plan
- [ ] `title` `CharField(max_length=255)`
- [ ] `currency` `FK("accounting.Currency", SET_NULL, null=True, blank=True)` — face-value sums,
      nothing converted
- [ ] `status` `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")` — **verb-driven,
      NOT on the form**
- [ ] `reason` `TextField()` — why this change
- [ ] `impact_note` `TextField(blank=True)` and `schedule_impact_note` `TextField(blank=True)`
      (cost impact is 7.4's; schedule-impact *ownership* stays 7.2/7.7 — 7.4 records the note)
- [ ] `requested_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True)`
- [ ] `requested_at` `DateTimeField(null=True, blank=True, editable=False)` — stamped by
      `bvr_submit`
- [ ] `decided_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`
      and `decided_at` `DateTimeField(null=True, blank=True, editable=False)` — stamped by
      approve/reject only
- [ ] `decision_notes` `TextField(blank=True)` — **the added field** (deviation #1)
- [ ] `activated_at` `DateTimeField(null=True, blank=True, editable=False)` — the re-baseline stamp
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`

#### Derived / Meta / behaviour
- [ ] `amount_delta` property — SUM(this revision's lines) − SUM(the active revision's lines),
      `q2()`-clamped; with no active revision the baseline sum is 0. The approver's headline number.
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")` **and**
      `("tenant","project","revision_no")` (two originals is a bug, not a limit)
- [ ] index: `("tenant","project","status")` `bvr_tnt_prj_status_idx`
- [ ] Verbs (POST-only, audit actions ≤ 10): `bvr_submit` (login, draft→pending_approval, stamps
      `requested_at`), `bvr_approve` (**tenant_admin**, pending_approval→approved, stamps
      `decided_by/_at`, does NOT activate), `bvr_reject` (**tenant_admin**, →rejected, stamps +
      `decision_notes`), `bvr_activate` (**tenant_admin**, approved only) — inside
      `transaction.atomic()` flips **every other** `approved` revision of the project to
      `superseded` (+ their `activated_at` kept as history) and stamps this one; audit
      `activate`/`supersede` (approve-does-not-activate means two `approved` rows can coexist, so
      the verb supersedes all, not "the" previous one)
- [ ] Approved/superseded rows **refuse edit+delete** (the frozen-row `bsl_edit` guard)
- [ ] Form: `BudgetRevisionForm` excludes `tenant`, `number`, `status`, `requested_at`,
      `decided_by`, `decided_at`, `decision_notes`, `activated_at`, `created_by`; plus
      `BudgetRevisionDecisionForm` (`decision_notes` Textarea, required) for the reject verb —
      the `ProjectRequestDecisionForm` mirror

---

### Model 2 — `CostControlAccount` [CCA-] (`models/CostManagement/CostControlAccounts.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "CCA"`. 9 declared + 4 inherited = **13 fields**.
Realizes bullets **2 (Cost Baseline & Control Accounts)** and **4 (Forecasting & EAC)** (Ruling 4:
the metrics have no other honest home).

#### Choices
- [ ] `STATUS_CHOICES` — `planning`/Planning, `active`/Active, `closed`/Closed (deviation #2)

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="control_accounts")`
- [ ] `name` `CharField(max_length=255)`; `code` `CharField(max_length=30)` (the tenant's CA id,
      e.g. "CA-1.2")
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True,
      related_name="control_accounts")` — a deliverable node or the project root; `clean()`
      same-project guard (the `anchor_task` pattern)
- [ ] `gl_account` `FK("accounting.GLAccount", PROTECT, null=True, blank=True,
      related_name="project_control_accounts")` — the ledger lens; **never posts** (Ruling 6)
- [ ] `contingency` `DecimalField(max_digits=14, decimal_places=2, default=0,
      validators=[MinValueValidator(0)])` — the CA-held reserve; **sized by 7.5, recorded here**
- [ ] `percent_complete` `DecimalField(max_digits=5, decimal_places=2, default=0,
      validators=[MinValueValidator(0), MaxValueValidator(100)])` — manually attested; **the
      docstring MUST name the 7.8 hand-off** (execution fields supersede it)
- [ ] `status` `CharField(max_length=10, choices=STATUS_CHOICES, default="planning")`
- [ ] `note` `TextField(blank=True)`

#### Derived properties (ALL guarded, ALL Decimal — never columns)
- [ ] `active_revision` — the project's approved+activated `BudgetRevision` (None when none)
- [ ] `bac` — SUM of the **active** revision's `ProjectBudgetLine.amount` mapped to this CA;
      `bac_with_contingency` adds `contingency` (PMBOK keeps them separable)
- [ ] `ev` — `bac × percent_complete / 100`
- [ ] `pv` — `bac ×` linear fraction of the anchored node's (else the project's) planned window
      elapsed at `timezone.localdate()`; 0 before start, 1 after finish; **docstring states this is
      planning-grade, not a time-phased BCWS curve** (the `critical_path_ids` honesty precedent)
- [ ] `ac` — SUM of `ProjectExpense.amount` where `control_account=self`, `status="posted"`,
      `entry_type in ("actual","accrual")`; `committed` — same aggregate with
      `entry_type="commitment"`; `available` — `q2(bac − committed − ac)`
- [ ] `cv = ev − ac`; `sv = ev − pv`; `cpi = ev/ac` (None when ac == 0); `spi = ev/pv` (None when
      pv == 0); `eac = bac/cpi` when cpi else `bac` (one documented technique, no method selector);
      `etc = eac − ac`; `tcpi = (bac − ev)/(bac − ac)` (None when denominator 0); `vac = bac − eac`
- [ ] `health` — under/watch/over (cut-points in deviation #5) → dict carrying colour-named badge
      classes `badge-green/-amber/-red` only (the semantic variants do not exist)
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")` **and**
      `("tenant","project","code")`; indexes `("tenant","project")` `cca_tnt_project_idx`,
      `("tenant","status")` `cca_tnt_status_idx`
- [ ] No verbs — the register is read + CRUD; form excludes `tenant`, `number`

---

### Model 3 — `ProjectBudgetLine` [PBL-] (`models/CostManagement/ProjectBudgetLines.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PBL"`. 9 declared + 4 inherited = **13 fields**.
Realizes bullet **1** and carries bullet 5's substance (lines belong to a revision). **The row the
whole sub-module rolls up from. No `hours`, no `rate`** (Ruling 1).

#### Choices
- [ ] `CATEGORY_CHOICES` — `labor`/Labor, `material`/Material, `equipment`/Equipment,
      `subcontract`/Subcontract, `overhead`/Overhead, `contingency`/Contingency, `other`/Other
      (`max_length=14`); **no default** — a required choice on the form

#### Fields
- [ ] `budget_revision` `FK(BudgetRevision, CASCADE, related_name="lines")` — **the line is only
      real inside a revision**
- [ ] `project` `FK("projects.Project", CASCADE, related_name="budget_lines")` — denormalised for
      filters; `clean()` requires it to equal the revision's project
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True,
      related_name="budget_lines")` — the bottom-up rollup source; `clean()` same-project guard
- [ ] `control_account` `FK(CostControlAccount, SET_NULL, null=True, blank=True,
      related_name="budget_lines")`
- [ ] `gl_account` `FK("accounting.GLAccount", PROTECT, null=True, blank=True,
      related_name="project_budget_lines")`
- [ ] `amount` `DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])`
- [ ] `note` `TextField(blank=True)`

#### Derived / Meta / behaviour
- [ ] View-level derived ONLY (annotations/`Sum`, never columns): category totals, project total,
      per-CA BAC; `clean()` also checks `wbs_node.project` / `control_account.project` == `project`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes
      `("tenant","project")` `pbl_tnt_project_idx`, `("tenant","budget_revision")`
      `pbl_tnt_rev_idx`, `("tenant","control_account")` `pbl_tnt_ca_idx`
- [ ] Form excludes `tenant`, `number`; `budget_revision`/`control_account`/`wbs_node` are
      tenant-scoped `ModelChoiceField`s (`_reject_foreign` still re-checks on POST)

---

### Model 4 — `ProjectExpense` [PEX-] (`models/CostManagement/ProjectExpenses.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "PEX"`. 13 declared + 4 inherited = **17 fields**.
Realizes bullet **3 (Expense Tracking & Commitments)**; feeds `ac`/`committed` into bullets 2/4.

#### Choices
- [ ] `ENTRY_TYPE_CHOICES` — `commitment`/Commitment, `actual`/Actual, `accrual`/Accrual
      (default `actual`); `SOURCE_KIND_CHOICES` — `purchase_order`/Purchase Order,
      `supplier_invoice`/Supplier Invoice, `contract`/Contract, `timesheet`/Timesheet,
      `manual`/Manual, `accrual`/Accrual (default `manual` — deviation #4); `STATUS_CHOICES` —
      `draft`/Draft, `posted`/Posted, `void`/Void (default `draft`, **verb-driven, NOT on form**)

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="expenses")`
- [ ] `control_account` `FK(CostControlAccount, PROTECT, related_name="expenses")` — **required,
      non-nullable**: a CA-less cost row would silently drop out of every index
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True,
      related_name="expenses")`
- [ ] `entry_type` and `source_kind` as above
- [ ] `source_number` `CharField(max_length=30, blank=True)` — e.g. `PO-00042`, `SIV-00187`; **a
      soft reference, NEVER an FK** — 4.x/6.x own those engines and neither carries a project link
      (Ruling 5)
- [ ] `vendor` `FK("core.Party", SET_NULL, null=True, blank=True,
      related_name="project_expenses")` (the `scm.PurchaseOrder.vendor` pattern)
- [ ] `gl_account` `FK("accounting.GLAccount", PROTECT, null=True, blank=True,
      related_name="project_expenses")`
- [ ] `amount` `DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])`
      — non-negative like 0002; reversals are paired void/adjustment rows, not negatives
- [ ] `currency` `FK("accounting.Currency", SET_NULL, null=True, blank=True)` — form `initial` =
      the project's active revision's currency, else the tenant's first Currency
- [ ] `entry_date` `DateField()` — required (deviation #4); the burn-trend dimension
- [ ] `status` as above; `description` `CharField(max_length=255, blank=True)`
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`

#### Derived / Meta / behaviour
- [ ] Burn trend = aggregation over `entry_date` in the views — **no snapshot table**; charts are
      7.16's
- [ ] `ordering = ["-entry_date", "-id"]` (the burn register reads chronologically; research is
      silent on ordering — pinned to the data's own axis); `unique_together = ("tenant","number")`
- [ ] indexes `("tenant","project")` `pex_tnt_project_idx`, `("tenant","control_account")`
      `pex_tnt_ca_idx`, `("tenant","entry_type")` `pex_tnt_etype_idx`, `("tenant","entry_date")`
      `pex_tnt_date_idx`
- [ ] Verbs (POST-only): `pex_post` (login, draft→posted, audit `post` — drafts never burn
      budget), `pex_void` (**tenant_admin**, posted→void, audit `void`; void rows stay visible and
      stop counting); edit/delete refuse posted+void (deviation #3)
- [ ] Form excludes `tenant`, `number`, `status`, `created_by`; `control_account`/`vendor`/
      `wbs_node`/`project` tenant-scoped; `currency` unscoped (L29)

---

## Backend (`apps/projects/{models,forms,views,urls}/CostManagement/`) — one file per entity per layer

- [ ] `models/CostManagement/<Entity>.py` ×4 as specified above; sub-package `__init__.py` files
      EMPTY; nothing added to the top-level `__init__.py` until Integrate
- [ ] `forms/CostManagement/<Entity>.py` — `BudgetRevisionForm` +
      `BudgetRevisionDecisionForm`, `CostControlAccountForm`, `ProjectBudgetLineForm`,
      `ProjectExpenseForm` (exclusions pinned per model)
- [ ] `views/CostManagement/<Entity>.py` — full CRUD via the `crud_*` helpers + the 6 verbs; every
      queryset `filter(tenant=request.tenant)`, never `.all()`; every verb refuses a disallowed
      transition with `messages.*` + redirect (an action already in its target state says so and
      writes nothing); every `?enum=` value allow-listed against CHOICES (L11); capture
      `previous = obj.status` BEFORE mutating (audit `changes` carries `{"verb", "from", "to"}`)
- [ ] `urls/CostManagement/<Entity>.py` — literal first segments `budgetlines/`, `revisions/`,
      `controlaccounts/`, `expenses/` (all disjoint from the existing inventory — re-check the
      concatenated `urls/__init__.py` at Integrate in case 7.3 added segments); literal routes
      before `<int:pk>/`

## Views, routes & CONTEXT KEYS (the contract — L7/L8: an unpinned name renders blank at 200)

- [ ] **ProjectBudgetLine** — `pbl_list` (`object_list`+`page_obj`+`q`), `pbl_create`,
      `pbl_detail` (`obj`), `pbl_edit` (`obj`), `pbl_delete`. Routes: `budgetlines/` + the four.
      No verbs. List filters: project, budget_revision, category, control_account. Extra list
      context: `projects`, `revisions`, `category_choices`, `control_accounts`; list annotates
      category/project totals read-only
- [ ] **BudgetRevision** — `bvr_{list,create,detail,edit,delete}`. Routes: `revisions/` + the four
      + `revisions/<int:pk>/submit/` `bvr_submit`, `…/approve/` `bvr_approve`
      (**tenant_admin**), `…/reject/` `bvr_reject` (**tenant_admin**), `…/activate/`
      `bvr_activate` (**tenant_admin**). List filters: project, status. Extra list context:
      `projects`, `status_choices`. Detail: `obj`, `lines` (with category totals), `amount_delta`
      rendered as the approver's headline
- [ ] **CostControlAccount** — `cca_{list,create,detail,edit,delete}`. Routes:
      `controlaccounts/` + the four. No verbs. List filters: project, status. Extra list context:
      `projects`, `status_choices`; the register renders the `health` badge + `cpi` per row.
      Detail: `obj` + the EVM panel reading `obj.bac/ev/pv/ac/committed/available/cv/sv/cpi/spi/
      eac/etc/tcpi/vac` straight off the properties (no computed context keys), the CA's
      active-revision `budget_lines`, and recent posted `expenses` (capped 25)
- [ ] **ProjectExpense** — `pex_{list,create,detail,edit,delete}`. Routes: `expenses/` + the four
      + `expenses/<int:pk>/post/` `pex_post`, `…/void/` `pex_void` (**tenant_admin**). List
      filters: project, entry_type, status, control_account. Extra list context: `projects`,
      `entry_type_choices`, `status_choices`, `source_kind_choices`, `control_accounts`

## Templates (`templates/projects/cost/<entity>/{list,detail,form}.html`)

- [ ] `budgetrevision/{list,detail,form}.html` — list: status badge incl. `superseded`, filter bar
      reflecting `request.GET`; detail: the line table with category totals + the `amount_delta`
      headline + the verb buttons gated by status
- [ ] `costcontrolaccount/{list,detail,form}.html` — list carries the health badge column
      (`badge-green/-amber/-red`); detail is the EVM panel (BAC/EV/PV/AC/committed/available/CV/
      SV/CPI/SPI/EAC/ETC/TCPI/VAC) with a documented "planning-grade PV" caption, the CA's budget
      lines and its posted expenses
- [ ] `projectbudgetline/{list,detail,form}.html`; `projectexpense/{list,detail,form}.html` —
      filters per the view contract; Actions column with delete-POST + `confirm()` +
      `{% csrf_token %}`; pagination with `has_previous`/`has_next` guards; empty states
- [ ] Colour-named badge classes only; every badge block ends `{% else %}{{ obj.get_<field>_display }}{% endif %}`
- [ ] **No nullable FK inside a `|default:` filter argument** — the 7.1 four-500 idiom; use
      `{% if %}…{% else %}—{% endif %}`. FK `<select>` comparisons use `|stringformat:"d"`.
      `{% extends "base.html" %}` unchanged

## Integrate (single writer — the ONLY shared-file step; surgical `Edit`, re-read anchors)

- [ ] Re-export blocks `# --- 7.4 Cost & Budget Management` appended to all four top-level
      `__init__.py` (models: 4 models; forms: 5 forms; views: 26 view names; urls: 4 urlpatterns
      imports + concat). A missing re-export is a runtime `ImportError`
- [ ] `admin.py` — 4 registrations appended after the 7.2 block (`list_display` led by `number`,
      `list_select_related` for every rendered FK, stamped fields readonly)
- [ ] `seed_projects.py` — `_cost` block with its OWN guard
      (`BudgetRevision.objects.filter(tenant=tenant).exists()`), called per tenant: revision 0
      (`approved` + `activated_at` stamped) per seeded project with **7–10 lines across all
      categories** anchored to the existing WBS work packages; one CA per deliverable of the
      active project with `percent_complete` values landing CPI in all three health bands; ~12
      `ProjectExpense` rows (commitments with `source_number="PO-…"` **strings only**, actuals +
      one accrual pair); one `pending_approval` revision with a visible positive `amount_delta`.
      Enough PBL rows for page 2 (3 projects × ~8 = 24 > 15). `--flush` deletes children-first:
      `ProjectExpense, ProjectBudgetLine, CostControlAccount, BudgetRevision`
- [ ] `apps/core/navigation.py` — one new `LIVE_LINKS["7.4"]` immediately after the `"7.2"` block
      (~`:1729`), verbatim from the research: Budget Planning & Estimation → `projects:pbl_list`;
      Cost Baseline & Control Accounts → `projects:cca_list`; Expense Tracking & Commitments →
      `projects:pex_list`; Forecasting & EAC → `projects:cca_list` (a lens on the CA register);
      Change Control & Budget Revisions → `projects:bvr_list`; extra leaf "Budget Register" →
      `projects:pbl_list`; comment records the deliberate lens-mapping
- [ ] `templates/projects/overview.html` — 7.4 quick links + counts (pending-approval revisions,
      posted spend), mirroring the 7.2 block
- [ ] **DB LAST**: `python manage.py makemigrations projects --dry-run` — **read every model the
      dry-run lists; if it names a model you did not write, STOP and report** (7.3 writes models
      into this same app). Then generate (number = disk leaf), `migrate`, `seed_projects` ×2
      (second run a no-op), `manage.py check`

## Verify

- [ ] `temp/` smoke sweep as `admin_acme` / `password` (NOT the tenant-less `admin`):
      - [ ] every new `projects:*` url 200 (405 for the POST-only verbs hit by GET); content
            asserts, not just status — page titles, a seeded `BVR-`/`CCA-`/`PBL-`/`PEX-` number,
            EVM figures render, no `{#` / `{% comment` leaks
      - [ ] junk params `?status=nope`, `?project=0`, `?entry_type=²`, `?page=9999` → default
            page, never a 500, never a silently emptied register (L11 allow-list)
      - [ ] page 2 of the budget-line register; cross-tenant IDOR → 404 on every `<int:pk>` route
      - [ ] state machine holds: approve-on-draft refused, activate-before-approve refused,
            posted expense refuses edit/delete, approved revision refuses edit/delete, member
            403 on the tenant_admin verbs, void stops a row counting without hiding it
      - [ ] EVM spot-check on one seeded CA: `ac`, `committed`, `available`, `cpi` arithmetic
            matches hand-computed values; one CA per health band renders its badge
- [ ] Sidebar shows **7.4 Live** with all five bullets + the register leaf

## Close-out (Module Creation Sequence phases 4–7)

- [ ] Review agents, one after another, each appending to
      `.claude/tasks/review-projects-7.4.md`: `code-reviewer` → `explorer` → `frontend-reviewer` →
      `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`
- [ ] `code-fixer` burns the deduped, ID'd findings (Critical → Important → Minor), one commit
      per file
- [ ] Tests: append `cost_*` fixtures to `conftest.py` (**owned by itself — only with a full
      unfiltered re-run**), then `test_cost_models.py` → `test_cost_forms.py` →
      `test_cost_views.py` → `test_cost_security.py`, one file per commit, tests named
      `test_cost_*`, helpers `_cost_*` (no shadowing of the `test_initiation_*` namespace), then
      **one full unfiltered run** (never `-k`, L47; iterate with `--nomigrations`)
- [ ] `.claude/skills/projects/SKILL.md` — append the 7.4 section (models + the
      baseline-is-the-approved-revision ruling, verb table, routes, seeder, gotchas incl. the
      `percent_complete` 7.8 hand-off and the property-not-annotation trap for `cpi` etc.) and
      update the frontmatter "As-built" line
- [ ] Mark 7.4 complete in `README.md`

## Later passes / deferred (carried verbatim from the research so nothing is lost)

Time-phased EVM (`EVMPeriod`, period BCWS curves) · `EACSnapshot` per CA per period · what-if
budget scenarios (`budget_type = baseline | what_if`) · `revision_kind = forecast` versions ·
rate-based labor budgeting (7.3 owns rates) · timesheet → labor-actual sync (7.3/7.11) ·
commitment change-order sub-workflow (4.x/6.x) · top-down budget target rows · management reserve
split from `contingency` · `BudgetRevision.source_change_request` FK → 7.7 · FX conversion (2.x/
7.15) · the `accounting.Project ↔ projects.Project` bridge and GL postings (2.x) · over-budget
notifications (7.17) · portfolio cost rollups (7.12).

---

## 7.5 Risk & Issue Management (Module 7: Project Management, `projects`) — plan from research-projects-7.5.md (2026-09-11)

> **CLOSE-OUT (2026-09-12, continuation session):** build + review + fixer + tests + docs are
> DONE. All 23 review findings (0C/10I/13M, `review-projects-7.5.md`) are `[x] fixed` — the
> first fixer run landed I1–I8, the continuation finished I9–M13 and migration 0008 (six named
> register indexes, I7+M11+M12). Tests: `risk_*` conftest block + `test_risk_{models,forms,
> views,security}.py` (35/23/25/24), full unfiltered app suite green; contract frozen in
> `test-contract-projects-7.5.md`. Skill section 7.5 appended; README row reads 5 of 19.
> The plan below is kept verbatim; unticked boxes follow the 7.4 precedent.

### Scope, conventions, rulings, build order (research's 4 models — order for FK flow)

- [ ] **Concurrency (read first):** 7.1–7.4 are all built and live in this tree; **no peer is writing
      `RiskManagement/`** — every shared-file touch (`models/forms/views/urls __init__.py`, `admin.py`,
      `seed_projects.py`, `navigation.py`, `overview.html`, `tests/conftest.py`) is an **Integrate-step
      item**, done once, as a **surgical `Edit` with a re-read anchor** immediately before the edit
      (**L43: never full-rewrite a shared 6400-line file**). Commits are path-limited:
      `git add '<f>'; git commit -m '<msg>' -- '<f>'`.
- [ ] **NavERP.md 7.5 bullets (verbatim — the `LIVE_LINKS["7.5"]` keys must match character-for-character,
      the sidebar maps bullet text → route):**
      1. **Risk Identification & Register** — Risk taxonomy, brainstorming tools, and checklists for
         common project types.
      2. **Qualitative & Quantitative Analysis** — Probability/impact matrices, Monte Carlo simulation,
         and expected monetary value.
      3. **Risk Response Planning** — Avoid, transfer, mitigate, accept strategies with action owners
         and triggers.
      4. **Issue Logging & Escalation** — Issue capture, severity classification, resolution tracking,
         and escalation paths.
      5. **Risk Monitoring & Reporting** — Top-risk dashboards, burn-down of risk exposure, and
         lessons learned integration.
- [ ] 4 models, **no fifth**: `ProjectRisk` [RSK-], `RiskResponseAction` [RRA-], `ProjectIssue` [ISS-],
      `IssueEscalation` [ESC-]. Prefixes `RSK`/`RRA`/`ISS`/`ESC` verified free repo-wide (`RSP` is
      7.3's; `RPL`/`RSV`/`RPT`/`RA`/`RAL`/`RAM`/`CR`/`PRJ` are the standing squats — none of the four
      touches them). **Do not add a `RiskAssessment`, `RiskSimulation`, `LessonsLearned`, `RiskCategory`
      or `EscalationPolicy` table** — Rulings 2/3/6 and Ruling 1.
- [ ] **Build order: ProjectRisk → RiskResponseAction → ProjectIssue → IssueEscalation** (RRA FKs
      ProjectRisk; ISS FKs Project + ProjectRisk; ESC FKs ProjectIssue — dependency order, not the
      research's catalog order).
- [ ] **Rulings 1–6, each restated as one-line build constraint:**
      1. **Escalation is recorded events, not a policy engine** — `IssueEscalation` rows + the current
         level denormalized on `ProjectIssue`; a tenant-configurable matrix / SLA timers are 7.17's, and
         6.3's `procurement.EscalationPolicy` (`Escalations.py:31`) already exists — **never re-declare
         it** (**L36**: the ships-first module owns the shared entity).
      2. **Monte Carlo is a computed, seeded, POST-run page over the register — never a stored table** —
         stdlib `random.Random(seed)` + `statistics` only (no numpy); `?seed=` shown for a byte-identical
         re-run; a stored simulation goes stale the instant a register row changes.
      3. **`lessons_learned` is a `TextField` on closed `ProjectRisk`/`ProjectIssue`, not a store** —
         7.10 owns the repository; a lens listing non-empty lessons + a link-out is the whole
         integration.
      4. **Contingency is *sized* by 7.5, *recorded* by 7.4** — 7.5 displays the EMV total and the
         P80−deterministic delta; the write to `CostControlAccount.contingency` stays 7.4's (one writer
         per column); `contingency_account` is a read-only lens, **no automated write verb this pass**.
      5. **Schedule risk is *recorded*, not simulated** — `schedule_impact_days` is a figure rolled into
         exposure; the WBS-network simulation waits on 7.2 activity uncertainty.
      6. **The taxonomy is a choices vocabulary** — `category` is a `CharField(choices=…)`, not a table;
         the reusable library / per-project-type checklists are 7.19's.
- [ ] **Spine verified (L28), do not re-derive:** `projects.Project` (`Projects.py:27`),
      `projects.ProjectTask` (`ProjectTasks.py:22`), `projects.ProjectMilestone` (`ProjectMilestones.py:17`
      — idiom only, not FK'd), `projects.ProjectStakeholder` (`ProjectStakeholders.py:24` — role lens
      only, not FK'd), `projects.CostControlAccount` (`CostControlAccounts.py:29`), `projects.BudgetRevision`
      (`BudgetRevisions.py:27` — read-only baseline lens), `core.Document`/`core.Activity`/`core.AuditLog`.
      **No `Risk`/`Issue`/`LessonsLearned` class exists anywhere.** 7.5 FKs only
      `Project`/`ProjectTask`/`ProjectRisk`/`ProjectIssue`/`CostControlAccount`/`AUTH_USER_MODEL` and
      re-declares none of 7.1–7.4 (**L36**).
- [ ] All four: `TenantNumbered` subclasses, `NUMBER_PREFIX` as above, money = `DecimalField(14,2)`
      through `q2()`/`MAX_Q2` (`models/_base.py:28-38`), `MinValueValidator(0)` on every amount, **all
      scores, bands, EMV and simulation figures are derived properties / computed views, NEVER stored
      columns** (the 7.1 ROI / 7.4 EVM ruling), audit actions ≤ 10 chars, `unique_together ("tenant","number")`.
- [ ] Layers: `apps/projects/{models,forms,views,urls}/RiskManagement/<Entity>.py` (same file name in all
      four; sub-package `__init__.py` files stay EMPTY; re-exports only in the four top-level
      `__init__.py`). Files: `ProjectRisks.py`, `RiskResponseActions.py`, `ProjectIssues.py`,
      `IssueEscalations.py` (plural, the 7.1/7.2 idiom).
- [ ] Templates: `templates/projects/risk/<entity>/{list,detail,form}.html`; entity folders
      lowercase-singular: `projectrisk/`, `responseaction/`, `issue/`, `escalation/`; the two computed
      pages are standalone at the sub-module level (`templates/projects/risk/risk_analysis.html`,
      `risk_monitoring.html`). `templates/projects/` verified: `cost/ initiation/ planning/ resource/
      overview.html` — **no `risk/` yet**.
- [ ] Migration is `0006_…` (7.4 shipped `0005`); **number assigned at generation by the disk leaf**,
      never reserved. Tests `test_risk_*` / `risk_*` / `_risk_*` (no collision with `test_initiation_*`,
      `test_planning_*`, `test_resource_*` or the 7.4 `cost_*` namespace).
- [ ] **L31 — one sub-module per run:** 7.5 builds its own new tables only; nothing here reaches into
      7.6 (quality/defects), 7.7 (scope change/CCB), 7.8 (task execution), 7.10 (document/knowledge
      repository), 7.12 (portfolio rollup), 7.16 (charts), 7.17 (notifications/workflow) or 7.19
      (master data).
- [ ] **L29 — no second ledger:** 7.5's `cost_impact` is a project figure; if a mitigation becomes real
      spend it is a 7.4 `ProjectExpense`, and the ledger is accounting's. No FK targets
      `accounting.Currency` this pass (sums at face value); no FK targets `core.Party` (an external risk
      owner is deferred).
- [ ] FKs declared **by string** (`"projects.Project"`, `"projects.ProjectTask"`, `"projects.ProjectRisk"`,
      `"projects.ProjectIssue"`, `"projects.CostControlAccount"`, `settings.AUTH_USER_MODEL`) — no
      cross-app model import at module level.
- [ ] **L16 — every date comparison uses `timezone.localdate()`**, never `datetime.date.today()`
      (`identified_date` default, `review_date`/`due_date` overdue flags, `age_days`).

---

### Model 1 — `ProjectRisk` [RSK-] (`models/RiskManagement/ProjectRisks.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "RSK"`. 24 declared + 4 inherited = **28 fields**. Realizes
bullets **1 (register)**, **2 (the inputs + EMV)**, **3 (strategy/trigger/contingency)** and **5
(review date + lessons field)** — the register row where four of the five bullets meet.

#### Choices (exact machine values)
- [ ] `CATEGORY_CHOICES` (`max_length=16`) — `technical`/Technical, `schedule`/Schedule, `cost`/Cost,
      `resource`/Resource, `external`/External, `organizational`/Organizational, `quality`/Quality,
      `compliance`/Compliance, `other`/Other
- [ ] `RISK_TYPE_CHOICES` (`max_length=12`) — `threat`/Threat, `opportunity`/Opportunity
- [ ] `RESPONSE_STRATEGY_CHOICES` (`max_length=12`) — `avoid`/Avoid, `mitigate`/Mitigate,
      `transfer`/Transfer, `accept`/Accept, `exploit`/Exploit, `escalate`/Escalate
- [ ] `STATUS_CHOICES` (`max_length=16`) — `identified`/Identified, `assessing`/Assessing,
      `response_planned`/Response Planned, `monitoring`/Monitoring, `realized`/Realized, `closed`/Closed
- [ ] `PROBABILITY_PCT = {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}` — **the documented constant map** (the 7.1
      `RISK_DISCOUNT` idiom, `ProjectRequests.py:78-86`); drives `emv` and the Monte Carlo Bernoulli draw
- [ ] `SEVERITY_BANDS` documented constant map — `1–3 → low`, `4–7 → medium`, `8–14 → high`,
      `15–25 → critical` (the `severity_band` property reads it)
- [ ] `TOLERANCE_BANDS` documented constant — the tolerance-exceeding set is **`{"high","critical"}`**
      (Ruling 6: a constant band map this pass, not a per-tenant config table)

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="risks")` — the container
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True, related_name="risks")`
- [ ] `title` `CharField(max_length=255)`; `description` `TextField()`; `cause` `TextField(blank=True)`;
      `effect` `TextField(blank=True)` (the "If…then" structure)
- [ ] `category` `CharField(max_length=16, choices=CATEGORY_CHOICES, default="other")`
- [ ] `risk_type` `CharField(max_length=12, choices=RISK_TYPE_CHOICES, default="threat")`
- [ ] `probability` `PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])`
- [ ] `impact` `PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])`
- [ ] `cost_impact` `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"),
      validators=[MinValueValidator(0)])` — the EMV and Monte Carlo input
- [ ] `schedule_impact_days` `PositiveIntegerField(null=True, blank=True)` — **recorded, not simulated**
      (Ruling 5)
- [ ] `response_strategy` `CharField(max_length=12, choices=RESPONSE_STRATEGY_CHOICES, default="mitigate")`
- [ ] `response_note` `TextField(blank=True)`; `trigger` `TextField(blank=True)`;
      `contingency_plan` `TextField(blank=True)`
- [ ] `status` `CharField(max_length=16, choices=STATUS_CHOICES, default="identified")` — **verb-driven,
      NOT on the form**
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_risks")`
      — the named human owner
- [ ] `identified_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
      related_name="raised_risks")`
- [ ] `identified_date` `DateField(default=timezone.localdate)`
- [ ] `review_date` `DateField(null=True, blank=True)` — the register's cadence column
- [ ] `residual_probability` / `residual_impact` `PositiveSmallIntegerField(null=True, blank=True,
      validators=[MinValueValidator(1), MaxValueValidator(5)])` — the post-response estimate
- [ ] `contingency_account` `FK("projects.CostControlAccount", SET_NULL, null=True, blank=True,
      related_name="risks")` — read-only lens; **the write to `contingency` stays 7.4's** (Ruling 4)
- [ ] `lessons_learned` `TextField(blank=True)` — the closed-row takeaway, **not a store** (Ruling 3)
- [ ] `closed_at` `DateTimeField(null=True, blank=True, editable=False)` — stamped by `rsk_close`
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`

#### Derived / Meta / behaviour
- [ ] `score` property = `probability * impact` (never stored)
- [ ] `severity_band` property → `low`/`medium`/`high`/`critical` via `SEVERITY_BANDS`; plus a
      **`get_severity_band_display()` helper** returning the label (the
      `ProjectStakeholder.get_engagement_strategy_display` precedent, `ProjectStakeholders.py:144` —
      without it the template renders an empty cell, the L7 blank-at-200 failure)
- [ ] `emv` property = `q2(cost_impact × PROBABILITY_PCT[probability] / 100)`; `exposure` property =
      `emv` (the burn-down sum term)
- [ ] `residual_score` = `residual_probability × residual_impact` (None if either is None);
      `residual_band` via `SEVERITY_BANDS`
- [ ] `is_review_overdue` property = `review_date` passed and `status not in ("realized","closed")`
      (the `ProjectMilestone.is_late` idiom, `ProjectMilestones.py:60-64`)
- [ ] `is_locked` property = `status in ("realized","closed")` — edit/delete refuse these rows (the
      `ProjectExpense.is_locked` frozen-row guard, `ProjectExpenses.py:98-101`)
- [ ] `clean()` same-project guards: `wbs_node.project_id == project_id` (the `anchor_task` pattern) and
      `contingency_account.project_id == project_id`; each raised as a field-keyed `ValidationError`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes
      `("tenant","project")` `rsk_tnt_project_idx`, `("tenant","status")` `rsk_tnt_status_idx`,
      `("tenant","category")` `rsk_tnt_category_idx`, `("tenant","risk_type")` `rsk_tnt_rtype_idx`,
      `("tenant","-created_at")` `rsk_tnt_created_idx` (serves `Meta.ordering` itself)
- [ ] Verbs (POST-only, audit actions ≤ 10 chars; each refuses a disallowed transition with `messages.*`
      + redirect, captures `previous = obj.status` BEFORE mutating, writes
      `changes={"verb","from","to"}`):
      `rsk_realize` (login; `monitoring`/`response_planned` → `realized`, **may create the linked
      `ProjectIssue`** — the risk→issue bridge; audit `realize`; **refused on a closed row**);
      `rsk_close` (login; → `closed`, stamps `closed_at`; audit `close`);
      `rsk_reopen` (**tenant_admin**; `closed` → `monitoring`, clears `closed_at`; audit `reopen`)
- [ ] Form `ProjectRiskForm` excludes `tenant`, `number`, `status`, `closed_at`, `created_by`;
      `owner`/`identified_by` tenant-scoped `ModelChoiceField`s (`_reject_foreign` re-checks);
      `contingency_account`/`wbs_node`/`project` tenant-scoped; `TenantUniqueMixin` FIRST on the form
      (its `clean()` compares FKs' project)

---

### Model 2 — `RiskResponseAction` [RRA-] (`models/RiskManagement/RiskResponseActions.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "RRA"`. 11 declared + 4 inherited = **15 fields**. Realizes
bullet **3's "action owners and triggers"** — one risk carries many actions, each with its own owner,
due date, cost and expected residual.

#### Choices
- [ ] `STRATEGY_CHOICES` (`max_length=12`) — same vocabulary as `ProjectRisk.RESPONSE_STRATEGY_CHOICES`
      (`avoid`/`mitigate`/`transfer`/`accept`/`exploit`/`escalate`)
- [ ] `STATUS_CHOICES` (`max_length=12`) — `planned`/Planned, `in_progress`/In Progress,
      `completed`/Completed, `cancelled`/Cancelled

#### Fields
- [ ] `risk` `FK("projects.ProjectRisk", CASCADE, related_name="response_actions")` — the action is only
      real inside a risk
- [ ] `title` `CharField(max_length=255)`; `description` `TextField(blank=True)`
- [ ] `strategy` `CharField(max_length=12, choices=STRATEGY_CHOICES, default="mitigate")`
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="risk_actions")`
      — the **action** owner, distinct from the risk owner
- [ ] `due_date` `DateField(null=True, blank=True)`
- [ ] `cost` `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"),
      validators=[MinValueValidator(0)])` — estimated mitigation cost (a real spend is a 7.4
      `ProjectExpense` — soft)
- [ ] `trigger` `TextField(blank=True)` — the observable event that activates THIS action
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="planned")` — **verb-driven,
      NOT on the form**
- [ ] `residual_probability` / `residual_impact` `PositiveSmallIntegerField(null=True, blank=True,
      validators=[MinValueValidator(1), MaxValueValidator(5)])`
- [ ] `completed_at` `DateTimeField(null=True, blank=True, editable=False)`;
      `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`

#### Derived / Meta / behaviour
- [ ] `is_overdue` property = `due_date` passed and `status not in ("completed","cancelled")` (the
      `is_late` idiom)
- [ ] `residual_score` property = `residual_probability × residual_impact` (None if either None)
- [ ] `is_locked` property = `status == "completed"` — a completed action refuses edit/delete
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes
      `("tenant","risk")` `rra_tnt_risk_idx`, `("tenant","status")` `rra_tnt_status_idx`,
      `("tenant","owner")` `rra_tnt_owner_idx`, `("tenant","due_date")` `rra_tnt_due_idx`
- [ ] Verb `rra_complete` (login; → `completed`, stamps `completed_at`; audit `complete`; already-completed
      says so and writes nothing)
- [ ] Form `RiskResponseActionForm` excludes `tenant`, `number`, `status`, `completed_at`, `created_by`;
      `risk`/`owner` tenant-scoped

---

### Model 3 — `ProjectIssue` [ISS-] (`models/RiskManagement/ProjectIssues.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "ISS"`. 20 declared + 4 inherited = **24 fields**. Realizes
bullet **4's capture / severity / resolution / current escalation state**.

#### Choices
- [ ] `ISSUE_TYPE_CHOICES` (`max_length=12`) — `issue`/Issue, `action_item`/Action Item,
      `decision`/Decision, `other`/Other
- [ ] `SEVERITY_CHOICES` (`max_length=8`) — `critical`/Critical, `high`/High, `medium`/Medium, `low`/Low
- [ ] `STATUS_CHOICES` (`max_length=12`) — `open`/Open, `in_progress`/In Progress, `blocked`/Blocked,
      `resolved`/Resolved, `closed`/Closed, `cancelled`/Cancelled

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="issues")`
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True, related_name="issues")`
- [ ] `risk` `FK("projects.ProjectRisk", SET_NULL, null=True, blank=True, related_name="issues")` —
      provenance, set by `rsk_realize`
- [ ] `title` `CharField(max_length=255)`; `description` `TextField()`
- [ ] `issue_type` `CharField(max_length=12, choices=ISSUE_TYPE_CHOICES, default="issue")`
- [ ] `severity` `CharField(max_length=8, choices=SEVERITY_CHOICES, default="medium")`
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="open")` — **verb-driven, NOT
      on the form**
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_issues")`
- [ ] `raised_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
      related_name="raised_issues")`
- [ ] `identified_date` `DateField(default=timezone.localdate)`; `due_date` `DateField(null=True,
      blank=True)`
- [ ] **Escalation current state (denormalized for the register lens):** `escalation_level`
      `PositiveSmallIntegerField(default=0)` (0 = not escalated, 1–4 = tier); `escalated_to`
      `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="escalated_issues")`;
      `escalated_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] **Resolution (verb-written evidence, NEVER form fields — the 7.4 `decision_notes` rule):**
      `root_cause` `TextField(blank=True)`; `resolution_note` `TextField(blank=True)`;
      `resolved_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`;
      `resolved_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `lessons_learned` `TextField(blank=True)` (Ruling 3);
      `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`

#### Derived / Meta / behaviour
- [ ] `is_overdue` = `due_date` passed and `status in ("open","in_progress","blocked")` (the `is_late`
      idiom); `age_days` = days since `identified_date` (L16: `timezone.localdate()`)
- [ ] `is_open` = `status in ("open","in_progress","blocked")`
- [ ] `severity_badge` property → dict `{"state","badge"}` using **colour-named classes only**
      (`badge-red`/`badge-amber`/`badge-green`, **L33**); `get_severity_display()` comes free from the field
- [ ] `is_locked` = `status in ("resolved","closed")` — the resolution fields refuse edit/delete
- [ ] `clean()` same-project guards: `wbs_node.project_id == project_id` and `risk.project_id == project_id`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes
      `("tenant","project")` `iss_tnt_project_idx`, `("tenant","status")` `iss_tnt_status_idx`,
      `("tenant","severity")` `iss_tnt_severity_idx`, `("tenant","escalation_level")` `iss_tnt_esc_idx`,
      `("tenant","-created_at")` `iss_tnt_created_idx`
- [ ] Verbs (POST-only, audited, `changes={"verb","from","to"}`):
      `iss_escalate` (**tenant_admin**, **L27** — appends an `IssueEscalation` row, increments
      `escalation_level`, sets `escalated_to`/`escalated_at`; audit `escalate`; **refused when the issue
      is resolved/closed**);
      `iss_resolve` (login — stamps `resolved_by`/`resolved_at`, status → `resolved`; audit `resolve`;
      **resolve-twice refused**);
      `iss_close` (login — `resolved` → `closed`; audit `close`; refused unless resolved)
- [ ] Form `ProjectIssueForm` excludes `tenant`, `number`, `status`, `root_cause`, `resolution_note`,
      `resolved_by`, `resolved_at`, `escalation_level`, `escalated_to`, `escalated_at`, `created_by`;
      `project`/`wbs_node`/`risk`/`owner`/`raised_by` tenant-scoped

---

### Model 4 — `IssueEscalation` [ESC-] (`models/RiskManagement/IssueEscalations.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "ESC"`. 9 declared + 4 inherited = **13 fields**. Realizes
bullet **4's escalation-path requirement** explicitly — one row per escalation event, recorded, **not a
configurable policy engine** (Ruling 1).

#### Fields
- [ ] `issue` `FK("projects.ProjectIssue", CASCADE, related_name="escalations")`
- [ ] `level` `PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])` —
      levels 1–4 (Team Lead → PM → Program Manager → Executive Sponsor)
- [ ] `target_role` `CharField(max_length=80, blank=True)` — the role label ("Program Manager",
      "Executive Sponsor"); grounded in the `pst_list` RACI/type register, linked as a lens
- [ ] `target_user` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
      related_name="issue_escalations")` — the named target (the practice's "primary + backup" is two
      rows, not two columns)
- [ ] `reason` `TextField()` — required (why it was escalated)
- [ ] `escalated_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
      related_name="escalations_raised")`; `escalated_at` `DateTimeField(auto_now_add=True)`
- [ ] `resolved_at` `DateTimeField(null=True, blank=True)`; `outcome` `TextField(blank=True)` (what was
      decided at this level)
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False)`

#### Meta / behaviour
- [ ] `ordering = ["issue_id", "level", "id"]` (the path reads in level order); `unique_together =
      ("tenant","number")`; indexes `("tenant","issue")` `esc_tnt_issue_idx`, `("tenant","level")`
      `esc_tnt_level_idx`
- [ ] No verbs of its own — rows are appended by `iss_escalate`; form `IssueEscalationForm` excludes
      `tenant`, `number`, `escalated_at`, `created_by`

---

## Backend (`apps/projects/{models,forms,views,urls}/RiskManagement/`) — one file per entity per layer

- [ ] `models/RiskManagement/<Entity>.py` ×4 as specified above; sub-package `__init__.py` files EMPTY;
      nothing added to the top-level `__init__.py` until Integrate
- [ ] `forms/RiskManagement/<Entity>.py` — `ProjectRiskForm`, `RiskResponseActionForm`,
      `ProjectIssueForm`, `IssueEscalationForm` (exclusions pinned per model; `TenantUniqueMixin`
      BEFORE `TenantModelForm` on every form whose `clean()` compares an FK's project)
- [ ] `views/RiskManagement/<Entity>.py` — full CRUD via the `crud_*` helpers + the 7 verbs; every
      queryset `filter(tenant=request.tenant)`, never `.all()`; `_reject_foreign(form, cleaned,
      [<tenant-scoped FK names>])` per form (never `accounting.Currency` — none this pass); every verb
      refuses a disallowed transition with `messages.*` + redirect; every `?enum=` value allow-listed
      against CHOICES (**L11**); capture `previous = obj.status` BEFORE mutating
- [ ] `urls/RiskManagement/<Entity>.py` — literal first segments `risks/`, `responses/`, `issues/`,
      `escalations/` plus the two computed `risk-analysis/`, `risk-monitoring/`; literal routes before
      `<int:pk>/` (first-match-wins)
- [ ] `views/RiskManagement/RiskAnalysis.py` + `views/RiskManagement/RiskMonitoring.py` — the two
      computed pages (no model; the 7.3 `CapacityDemand.py` precedent — a computed board, not a model);
      absolute imports only

## Views, routes & CONTEXT KEYS — the contract (L7/L8: an unpinned name renders blank at 200)

- [ ] **ProjectRisk** — `rsk_list`, `rsk_create`, `rsk_detail`, `rsk_edit`, `rsk_delete`.
      Routes (prefix `risks/`): `risks/`, `risks/add/`, `risks/<int:pk>/`, `risks/<int:pk>/edit/`,
      `risks/<int:pk>/delete/`; verbs `risks/<int:pk>/realize/` `rsk_realize`,
      `risks/<int:pk>/close/` `rsk_close`, `risks/<int:pk>/reopen/` `rsk_reopen` (**tenant_admin**).
      `rsk_list`: `search_fields=["number","title","description","cause","effect"]`;
      `filters=[("project","project_id",True), ("category","category",False),
      ("risk_type","risk_type",False), ("status","status",False), ("owner","owner_id",True)]`.
      **Derived lenses are PRE-SCOPED in the view before `crud_list` (they are Python properties, not
      model fields — `crud_list`'s `filters` are field lookups only, L11):** `?band=<low|medium|high|
      critical>` → `Q` OR of `Q(probability=p, impact=i)` pairs in that band's score range (DB-side,
      exact); `?review_due=1`/`?overdue=1` → `Q(review_date__lt=timezone.localdate(),
      status__in=("identified","assessing","response_planned","monitoring"))`; `?top=1` → order by
      `-score` then `-emv`. `extra_context`: `projects`, `category_choices`, `risk_type_choices`,
      `status_choices`, `strategy_choices`, `band_choices`, `owners`
      (`User.objects.filter(tenant=request.tenant).only("id","email","first_name","last_name")`).
      Detail: `obj` + `response_actions` (obj.response_actions `select_related("owner")`) +
      `linked_issues` (obj.issues); the derived figures render straight off `obj` (no computed context
      keys — the 7.4 CCA-detail rule)
- [ ] **RiskResponseAction** — `rra_list`, `rra_create`, `rra_detail`, `rra_edit`, `rra_delete`.
      Routes (prefix `responses/`): `responses/`, `responses/add/`, `responses/<int:pk>/`,
      `responses/<int:pk>/edit/`, `responses/<int:pk>/delete/`; verb
      `responses/<int:pk>/complete/` `rra_complete`.
      `rra_list`: `search_fields=["number","title","description","trigger"]`;
      `filters=[("risk","risk_id",True), ("strategy","strategy",False), ("status","status",False),
      ("owner","owner_id",True)]`; derived `?overdue=1` pre-scoped
      (`Q(due_date__lt=today, status__in=("planned","in_progress"))`).
      `extra_context`: `risks` (`ProjectRisk.objects.filter(tenant=…)`), `strategy_choices`,
      `status_choices`, `owners`. Detail: `obj` + `risk` (via obj.risk)
- [ ] **ProjectIssue** — `iss_list`, `iss_create`, `iss_detail`, `iss_edit`, `iss_delete`.
      Routes (prefix `issues/`): `issues/`, `issues/add/`, `issues/<int:pk>/`, `issues/<int:pk>/edit/`,
      `issues/<int:pk>/delete/`; verbs `issues/<int:pk>/escalate/` `iss_escalate` (**tenant_admin**),
      `issues/<int:pk>/resolve/` `iss_resolve`, `issues/<int:pk>/close/` `iss_close`.
      `iss_list`: `search_fields=["number","title","description"]`;
      `filters=[("project","project_id",True), ("severity","severity",False), ("status","status",False),
      ("issue_type","issue_type",False), ("owner","owner_id",True), ("risk","risk_id",True)]`; derived
      `?escalated=1` → `Q(escalation_level__gt=0)`; `?overdue=1` → `Q(due_date__lt=today,
      status__in=("open","in_progress","blocked"))` (both pre-scoped).
      `extra_context`: `projects`, `severity_choices`, `status_choices`, `issue_type_choices`,
      `owners`, `risks`. Detail: `obj` + `escalations` (obj.escalations ordered by `level`,`id`) + the
      resolution/verb panels
- [ ] **IssueEscalation** — `esc_list`, `esc_create`, `esc_detail`, `esc_edit`, `esc_delete`.
      Routes (prefix `escalations/`): `escalations/`, `escalations/add/`, `escalations/<int:pk>/`,
      `escalations/<int:pk>/edit/`, `escalations/<int:pk>/delete/`. No verbs.
      `esc_list`: `search_fields=["number","target_role","reason","outcome"]`;
      `filters=[("issue","issue_id",True), ("level","level",True), ("target_user","target_user_id",True)]`.
      `extra_context`: `issues` (`ProjectIssue.objects.filter(tenant=…)`), `level_choices`
      (`[(1,"Level 1"),(2,"Level 2"),(3,"Level 3"),(4,"Level 4")]`), `owners`. Detail: `obj` + `issue`
- [ ] **`risk_analysis`** — route `risk-analysis/`, name `risk_analysis`, template
      `projects/risk/risk_analysis.html`. GET renders the matrix + EMV tables (no simulation);
      **POST runs the seeded Monte Carlo** and re-renders. Full context:
      - `projects` (tenant `Project` queryset), `project` (the selected `Project` from `?project=`, else
        None; `as_db_int`-guarded), `baseline` (the project's approved+activated `BudgetRevision`, else None)
      - `matrix` — 5 rows (probability 5→1) × 5 cells; each cell `{"probability","impact","count",
        "badge","risks"}` where `badge` is the colour-named class for that cell's band (**L33**);
        `matrix_max` — max cell count (0-safe, for CSS bar shading)
      - `emv_rows` — per-risk `{"risk","probability_pct","cost_impact","emv"}` ordered `-emv`;
        `emv_total` — `q2(Σ emv)`; `residual_emv_total` — `q2(Σ residual emv)` when both residual
        fields are set
      - `seed` (effective int, default pinned constant `42`, shown on the page), `iterations` (effective
        int, default `1000`, clamped `100..10000`), `run` (bool — True only on a POST that ran)
      - `simulation` — None on a plain GET, else `{"mean","p10","p50","p80","p90","samples",
        "baseline_total","overrun_probability","contingency_delta"}`; `baseline_total` = the active
        revision's line total (7.4 read-only lens); `overrun_probability` = % of iterations whose sampled
        exposure exceeds `baseline_total`; `contingency_delta` = `q2(p80 − baseline_total)` (Ruling 4 —
        **displayed, never written** to the CA)
      - `?seed=`/`?iterations=` parsed through a `forms.Form` (`IntegerField`, `is_finite` + magnitude
        cap — **L35**, never raw `request.GET` parsing); junk seed → default, never a 500
- [ ] **`risk_monitoring`** — route `risk-monitoring/`, name `risk_monitoring`, template
      `projects/risk/risk_monitoring.html`, **GET-only**. Full context:
      - `projects`, `project` (from `?project=`, `as_db_int`-guarded), `open_count`, `closed_count`,
        `realized_count`
      - `top_risks` — register ordered `-score` then `-emv` (the top-risk list, cap 25)
      - `burndown_rows` — period rows `{"period","label","count","score_total","emv_total","bar_pct"}`
        aggregated by `identified_date` month over the selected project; `bar_pct` = `score_total` as %
        of the max row (0-safe, **CSS bars, no chart library — 7.16 owns charts**); `burndown_max`
      - `review_queue` — risks with `review_date` passed and status not closed, ordered `review_date`;
        `review_due_count`
      - `tolerance` — `{"threshold","band","above"}` from the documented `TOLERANCE_BANDS` constant
        (`above` = count of open risks whose `severity_band` is in `{"high","critical"}`);
        `above_tolerance_count`
      - `lessons` — closed risks/issues with non-empty `lessons_learned`, each row
        `{"kind","obj","lesson"}` (the lessons lens); `lessons_count`
      - `by_category`, `by_band` — small dicts for the summary strip
- [ ] **Four url prefixes pinned — `risks/`, `responses/`, `issues/`, `escalations/` — plus the two
      computed routes `risk-analysis/`, `risk-monitoring/`.** All six are **disjoint literals** from
      7.1–7.4's existing first segments (`""`, `project-requests/`, `projects/`, `stakeholders/`,
      `kickoffs/`, `tasks/`, `dependencies/`, `milestones/`, `baselines/`, `resource-profiles/`,
      `allocations/`, `time-entries/`, `capacity-demand/`, `budgetlines/`, `revisions/`,
      `controlaccounts/`, `expenses/`) — **re-check the concatenated `urls/__init__.py` at Integrate** in
      case a peer added a segment. No route uses a converter in its first component.

## Templates (`templates/projects/risk/`)

- [ ] `projectrisk/{list,detail,form}.html`; `responseaction/{list,detail,form}.html`;
      `issue/{list,detail,form}.html`; `escalation/{list,detail,form}.html` — list: filter bar
      reflecting `request.GET` (including the derived `?band=`/`?overdue=`/`?review_due=`/`?escalated=1`
      lenses), Actions column (view/edit/delete-POST + `confirm()` + `{% csrf_token %}`), pagination with
      `has_previous`/`has_next` guards (**L9**), empty state
- [ ] The two computed pages live at the sub-module level: `risk_analysis.html`, `risk_monitoring.html`
      (not inside an entity folder) — matrix as an HTML grid, EMV/percentile tables, burn-down as CSS
      bars, review queue + tolerance flag + lessons lens
- [ ] Colour-named badge classes only (`badge-green/-amber/-red/-info/-muted/-slate`, **L33**) — run
      `grep -n '\.badge-' static/css/theme.css` before writing them; every badge block ends
      `{% else %}{{ obj.get_<field>_display }}{% endif %}`
- [ ] **No nullable FK inside a `|default:` filter argument** (the 7.1 four-500 idiom, **L10**) — use
      `{% if fk %}…{% else %}—{% endif %}` for `owner`/`escalated_to`/`target_user`/`resolved_by`/
      `identified_by` (all nullable user FKs)
- [ ] **Multi-line notes use `{% comment %} … {% endcomment %}`** — never a multi-line `{# … #}`
      (**L2**); the analysis/monitoring pages carry long caveats (simple random sampling, planning-grade
      exposure)
- [ ] FK `<select>` comparisons use `|stringformat:"d"`; `{% extends "base.html" %}` unchanged

## Integrate (single writer — the ONLY shared-file step; surgical `Edit`, re-read anchors)

- [ ] Re-export blocks `# --- 7.5 Risk & Issue Management` appended to all four top-level
      `__init__.py` (models: 4 models; forms: 4 forms; views: 4 CRUD sets + 2 computed views + 7 verbs;
      urls: 6 urlpatterns imports + concat). A missing re-export is a runtime `ImportError`
- [ ] `admin.py` — 4 registrations appended after the 7.4 block (`list_display` led by `number`,
      `list_select_related` for every rendered FK, `closed_at`/`resolved_at`/`completed_at`/`escalated_at`
      readonly)
- [ ] `seed_projects.py` — `_risk` block with its OWN guard
      (`ProjectRisk.objects.filter(tenant=tenant).exists()`), called per tenant: 8–12 `ProjectRisk` rows
      per seeded active project spanning all `category` values and both `risk_type`s, anchored to the
      existing WBS work packages, with `probability`/`impact`/`cost_impact` chosen to populate all four
      severity bands and land the EMV total in a meaningful range; one `realized` risk linked to one
      `ProjectIssue`; 2–3 `RiskResponseAction` rows per top risk (one `completed`, one overdue); 5–7
      `ProjectIssue` rows across all severities (2 `resolved` with stamps) and one carrying an
      `IssueEscalation` at level 2 with a populated `target_role`/`reason`; one closed risk with a
      non-empty `lessons_learned`. Enough rows for page 2. `--flush` deletes children-first:
      `IssueEscalation, ProjectIssue, RiskResponseAction, ProjectRisk`
- [ ] `apps/core/navigation.py` — one new `LIVE_LINKS["7.5"]` immediately after the `"7.4"` block
      (~`:1758`), verbatim from the research: Risk Identification & Register → `projects:rsk_list`;
      Qualitative & Quantitative Analysis → `projects:risk_analysis`; Risk Response Planning →
      `projects:rra_list`; Issue Logging & Escalation → `projects:iss_list`; Risk Monitoring & Reporting
      → `projects:risk_monitoring`; extra live leaf "Issue Escalation Queue" →
      `projects:iss_list?escalated=1`; the justification comments record the deliberate computed-page
      mapping (bullet 2/5 are computations over the register). `_safe_reverse` supports both `url#frag`
      and `?query=` (`navigation.py:1964-1975` — confirmed)
- [ ] `templates/projects/overview.html` — 7.5 quick links + counts (open risks above tolerance,
      review-due, open issues), mirroring the 7.4 block
- [ ] **DB LAST**: `python manage.py makemigrations projects --dry-run` — **read every model the
      dry-run lists; if it names a model you did not write, STOP and report** (a missing re-export, or a
      peer's model). Then generate (number = disk leaf `0006_…`), `migrate`, `seed_projects` ×2 (second
      run a no-op), `manage.py check`

## Verify

- [ ] `temp/` smoke sweep as `admin_acme` / `password` (NOT the tenant-less `admin`):
      - [ ] every new `projects:*` url 200 (405 for the POST-only verbs hit by GET — `rsk_realize`,
            `rsk_close`, `rsk_reopen`, `rra_complete`, `iss_escalate`, `iss_resolve`, `iss_close`);
            content asserts, not just status — page titles, a seeded `RSK-`/`ISS-` number, the matrix
            renders, the EMV total renders, no `{#` / `{% comment` leaks (**L8**)
      - [ ] junk params `?status=nope`, `?project=0`, `?probability=²`, `?seed=abc`, `?page=9999` →
            default page, never a 500, never a silently emptied register (**L11** allow-list + **L35**
            seed parse)
      - [ ] page 2 of the risk register; cross-tenant IDOR → 404 on every `<int:pk>` route
      - [ ] state machine holds: escalate-on-closed refused, resolve-twice refused, realize-on-closed
            refused, member 403 on `iss_escalate`/`rsk_reopen` (**L27**)
      - [ ] hand-computed spot check: one seeded risk's `score`/`severity_band`/`emv` matches
            hand-computed values; the `?band=critical` lens returns exactly the critical-band rows; the
            `?overdue=`/`?review_due=` lens returns exactly the review-overdue rows
- [ ] Sidebar shows **7.5 Live** with all five bullets + the escalation-queue leaf

## Close-out (Module Creation Sequence phases 4–7)

- [ ] Review agents, one after another, each appending to
      `.claude/tasks/review-projects-7.5.md`: `code-reviewer` → `explorer` → `frontend-reviewer` →
      `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`
- [ ] `code-fixer` burns the deduped, ID'd findings (Critical → Important → Minor), one commit per file
- [ ] Tests: append `risk_*` fixtures to `conftest.py` (**owned by itself — only with a full unfiltered
      re-run**), then `test_risk_models.py` → `test_risk_forms.py` → `test_risk_views.py` →
      `test_risk_security.py`, one file per commit, tests named `test_risk_*`, helpers `_risk_*` (no
      shadowing of the `test_initiation_*`/`test_planning_*`/`test_resource_*`/`cost_*` namespaces), then
      **one full unfiltered run** (never `-k`, **L47**; iterate with `--nomigrations`)
- [ ] `.claude/skills/projects/SKILL.md` — append the 7.5 section (the four models + prefixes, the
      derived-property rulings, the verb table with gates/audit strings, the six routes, the two computed
      pages + their context contracts, the seeder `_risk` block, gotchas incl. the computed-lens
      pre-scoping and the seed-parse guard) and update the frontmatter "As-built" line
- [ ] Mark 7.5 complete in `README.md`

## Later passes / deferred (carried verbatim from the research so nothing is lost)

- [ ] `RiskSimulationSnapshot` (stored Monte Carlo runs per period) — a report cache, not the model
      (Ruling 2); add only when a tenant needs period-over-period simulation history
- [ ] Quantified schedule-risk simulation (3-point durations → P80 finish, criticality index) — needs
      7.2 activity uncertainty + a CPM engine (Ruling 5)
- [ ] Latin Hypercube sampling, risk correlation / risk-driver modeling, convergence auto-stop — simple
      random sampling is the documented simplification; correlation needs a correlation-matrix model
- [ ] Decision-tree analysis — a different object (decisions, not risks); EMV per risk is this pass's scope
- [ ] Bowtie cause-and-effect analysis (ARM) — needs a cause/control graph model; `cause`/`effect` text
      is the honest stand-in
- [ ] Automated contingency write into `CostControlAccount.contingency` — one writer per column
      (Ruling 4); a cross-sub-module write verb waits on 7.4's contract
- [ ] Reusable risk library + per-project-type risk checklists — master data / template library → 7.19;
      the repository → 7.10 (Ruling 3/6)
- [ ] Tenant-configurable escalation matrix + auto-escalation on SLA breach — 7.17; the generic engine
      already exists at 6.3 (Ruling 1)
- [ ] Risk appetite / tolerance as a per-tenant config table — a documented constant band map this pass;
      per-tenant config is 7.19
- [ ] KRI / KPI indicators (leading indicators) — KRI definitions are master data (7.19); KRI values
      need a metrics engine; 7.5's exposure figures stand in
- [ ] Cross-project / portfolio risk aggregation and enterprise heat maps — 7.12 (portfolio)
- [ ] Risk dashboards and S-curve / tornado / burn-down charts — 7.16 (BI); 7.5 renders grids, tables
      and badges
- [ ] Escalation notifications, review reminders, missing-owner alerts — no scheduler/mail worker
      (7.1/6.8/6.19); 7.17's; badges and audit rows only
- [ ] Risk → scope change request FK (7.7) and risk → budget revision linkage (7.4) — those models'
      contracts do not invite the bridge yet; one-line FKs when they land
- [ ] External ticketing / GRC sync (Jira, ServiceNow) — integration → 7.18; a `source_number`-style
      soft reference would be the pattern

---

### 7.6 Quality Management (Module 7: Project Management, `projects`) — plan from research-projects-7.6.md (2026-09-11)

> **CLOSE-OUT (2026-09-12, continuation session):** build + review + fixer + tests + docs are
> DONE. Session 1 landed the contract + `QualityPlan`/`QualityReview` (all four layers + 12
> templates); the continuation rescued the orphaned `DeliverableInspections.py`, built QCI +
> `QualityDefect` + the two computed pages, integrated (re-exports between the 7.5/7.7 blocks,
> admin, `_quality` seeder, `LIVE_LINKS["7.6"]`, overview), and generated migration **0009**
> LAST (7.7's peer took 0007, 7.5's index migration 0008). Smoke: 137/137 content assertions.
> Review: all six reviewers → `review-projects-7.6.md` deduped to 0C/2I/15M + 3 design
> observations; fixer closed everything (M15 second-class filter indexes skipped — accepted
> while registers are small). Shipped deviations folded into the contract file (E009 widths
> 14/12, `qrv_report` accepts planned, QDF `is_locked` + cancelled, maturity `has_score`,
> `parties` key dropped). Tests: `quality_*` conftest block + `test_quality_{models,forms,
> views,security}.py` (53/29/76/44 = 202), full unfiltered app suite green on the real
> migration path; contract frozen in `test-contract-projects-7.6.md`. Skill section 7.6
> appended; README row reads 6 of 19. The plan below is kept verbatim; unticked boxes follow
> the 7.4/7.5 precedent.

#### Scope, conventions, rulings, build order (research's 4 models + 2 computed pages — order for FK flow)

- [ ] **Concurrency (read first):** 7.1–7.5 are built and live; **a peer session is concurrently building a sibling `7.M` in this same checkout — the 7.7 `ScopeRequirements` models/forms/views/urls folders and `templates/projects/scope/` are already on disk**, and its `# --- 7.7` blocks already sit in the three layer `__init__.py` files + the `urls/__init__.py` concat. So `todo.md`, the **migration leaf**, and every shared file (`models/forms/views/urls __init__.py`, `admin.py`, `seed_projects.py`, `navigation.py`, `overview.html`, `tests/conftest.py`) are **contended**. Every shared-file touch is an **Integrate-step item**, done once, as a **surgical `Edit` with a re-read anchor** immediately before the edit (**L43: never full-rewrite a shared ~6,950-line file; NEVER use `Write` on `todo.md`**). Insert the 7.6 block **between the existing `# --- 7.5` and `# --- 7.7` blocks** in each layer `__init__.py`. Commits are path-limited: `git add '<f>'; git commit -m '<msg>' -- '<f>'`.
- [ ] **NavERP.md 7.6 bullets (verbatim — the `LIVE_LINKS["7.6"]` keys must match character-for-character, the sidebar maps bullet text → route):**
      1. **Quality Planning & Standards** — Acceptance criteria, regulatory requirements, and industry standard mapping.
      2. **Quality Assurance (QA)** — Process audits, compliance checklists, and methodology adherence reviews.
      3. **Quality Control (QC) & Inspections** — Testing protocols, defect tracking, and inspection result recording.
      4. **Continuous Improvement** — Kaizen events, retrospectives, and process maturity assessments.
      5. **Deliverable Acceptance & Sign-off** — Formal review gates, customer validation, and acceptance documentation.
- [ ] 4 models, **no fifth**: `QualityPlan` [QPL-], `QualityReview` [QRV-], `DeliverableInspection` [QCI-], `QualityDefect` [QDF-]. Prefixes `QPL`/`QRV`/`QCI`/`QDF` verified free repo-wide (`QA`/`QC`/`NCR`/`CAPA` are scm 4.9's; `DEF` is inventory's; `RDS`/`RTV` are procurement's — none of the four touches them). **Do not add a `QualityStandard`, `AcceptanceSignOff`, `QualityImprovement`, `QualityInspection`, `NonConformance`, `CapaAction`, `Checklist`, `TestStep` or `MaturityScore` table** — Rulings 1–7.
- [ ] **Build order: QualityPlan → QualityReview → DeliverableInspection → QualityDefect** (QRV FKs QualityPlan; QCI FKs QualityPlan + ProjectMilestone; QDF FKs QualityPlan + DeliverableInspection + ProjectIssue — dependency order, not the research's catalog order).
- [ ] **Rulings 1–7, each restated as one-line build constraint with its owner named:**
      1. **`scm` 4.9 owns the enterprise QMS** — `NonConformance[NCR-]`/`CapaAction[CAPA-]`/`QualityAudit[QA-]`/`QualityInspection[QC-]` all ship in `apps/scm/models/QualityManagement/` (`LIVE_LINKS["4.9"]` live). 7.6 builds **no NCR, no CAPA, no audit programme, no goods/lot inspection**; its four tables are **project-deliverable-scoped**. The class name `QualityInspection` is deliberately avoided (`DeliverableInspection`); a genuine enterprise nonconformance → `scm.NonConformance` bridge is **deferred** (that table has no project FK) — **flag for 12.x** (**L36**).
      2. **`inventory` owns `QcChecklist` (+ `DefectReport[DEF-]`)** — `apps/inventory/models/QualityControl/`; the warehouse-floor QC gate. 7.6 **re-declares neither** (**L36**).
      3. **`procurement` 6.12 owns receipt inspection** — `ReceiptTolerancePolicy`/`ReceiptDiscrepancy[RDS-]`/`ReturnToVendor[RTV-]`. 7.6 builds none of it.
      4. **7.5 owns `ProjectRisk`/`ProjectIssue`** — a `QualityDefect` **LINKS to** `ProjectIssue` by nullable FK + the POST-only `qdf_raise_issue` verb (the `rsk_realize` idiom); 7.6 **never duplicates** the issue register (**L36**).
      5. **7.2 owns the schedule phase gate** — `ProjectMilestone.is_phase_gate`/`entry_criteria`/`exit_criteria`/`mst_achieve` are **not re-declared**; 7.6's gate is the **deliverable acceptance decision** (`DeliverableInspection.inspection_type="acceptance"` + `usage_decision`), anchored by an optional nullable `milestone` FK.
      6. **7.7 scope change, 7.9 minutes, 7.10 document repository + lessons repository, 7.13 retrospective ceremony, 7.16 charts, 7.17 workflow/e-signature, 7.19 master data (standards/checklist/methodology libraries) are siblings'** — 7.6 links out, builds no store; `standard_reference`/`regulatory_requirement` are free text (**Ruling 3**); minutes are a `core.Activity`, the acceptance certificate a `core.Document`; the maturity assessment is a **computed page** (no stored score table).
      7. **No money and no GL (L29)** — 7.6 declares **no `DecimalField` and no journal**; a quality cost is a 7.4 `ProjectExpense` (soft note, never a write); `q2()` is imported but unused on the model layer.
- [ ] **Spine verified (L28), do not re-derive:** `projects.Project` (`Projects.py:27`), `projects.ProjectTask` (`ProjectTasks.py:22`, `node_type="deliverable"` is the inspected node), `projects.ProjectMilestone` (`ProjectMilestones.py:17`), `projects.ProjectRisk` (`ProjectRisks.py:34`), `projects.ProjectIssue` (`ProjectIssues.py:29`), `projects.ProjectStakeholder` (`ProjectStakeholders.py:24` — customer lens only, not FK'd), `core.Party`, `core.Document`, `core.Activity`, `core.AuditLog`. **No `QualityPlan`/`QualityReview`/`DeliverableInspection`/`QualityDefect` class exists anywhere.** 7.6 FKs only `Project`/`ProjectTask`/`ProjectMilestone`/`ProjectRisk`/`ProjectIssue`/`core.Party`/`AUTH_USER_MODEL` and re-declares none of 7.1–7.5 (**L36**).
- [ ] All four: `TenantNumbered` subclasses, `NUMBER_PREFIX` as above, **no money column** (Ruling 7), **every pass rate, punch-list count and maturity figure is a derived property or a computed view, NEVER stored** (the 7.1 ROI / 7.4 EVM / 7.5 Monte-Carlo ruling), audit actions ≤ 10 chars (`create/update/delete/accept/reject/resolve/close/reopen` — `AuditLog.action` is `varchar(10)`), `unique_together ("tenant","number")`.
- [ ] Layers: `apps/projects/{models,forms,views,urls}/QualityManagement/<Entity>.py` (same file name in all four; sub-package `__init__.py` files stay EMPTY; re-exports only in the four top-level `__init__.py`). Files: `QualityPlans.py`, `QualityReviews.py`, `DeliverableInspections.py`, `QualityDefects.py` (plural, the 7.1–7.5 idiom).
- [ ] Templates: `templates/projects/quality/<entity>/{list,detail,form}.html`; entity folders lowercase-singular: `qualityplan/`, `qualityreview/`, `deliverableinspection/`, `qualitydefect/`; the two computed pages are standalone at the sub-module level (`templates/projects/quality/quality_improvement.html`, `quality_acceptance.html`). `templates/projects/` verified: `cost/ initiation/ planning/ resource/ risk/ scope/ overview.html` — **no `quality/` yet**.
- [ ] Migration is `0007_…` (7.5 shipped `0006`) — **the number is the disk leaf read at generation time, never reserved**; the peer **7.7 `ScopeRequirements`** sits on the same leaf `0006`, so **verify the leaf immediately before generating** and take whatever is free (`0007` if still free, else the next). Tests `test_quality_*` / `quality_*` / `_quality_*` (no collision with `test_initiation_*`, `test_planning_*`, `test_resource_*`, `test_cost_*`, `test_risk_*`, or the peer's `test_scope_*`).
- [ ] **L31 — one sub-module per run:** 7.6 builds its own new tables only; nothing here reaches into 7.7 (scope change/CCB — in the tree), 7.9 (minutes), 7.10 (document/knowledge repository), 7.13 (retro ceremony), 7.16 (charts/PDF), 7.17 (workflow/e-signature), 7.18 (integrations) or 7.19 (master data).
- [ ] FKs declared **by string** (`"projects.Project"`, `"projects.ProjectTask"`, `"projects.ProjectMilestone"`, `"projects.ProjectRisk"`, `"projects.ProjectIssue"`, `"projects.QualityPlan"`, `"projects.DeliverableInspection"`, `"core.Party"`, `settings.AUTH_USER_MODEL`) — no cross-app model import at module level.
- [ ] **L16 — every date comparison uses `timezone.localdate()`**, never `datetime.date.today()` (`review_date`/`identified_date` defaults; `planned_review_date`/`planned_date`/`due_date` overdue flags; `age_days`).

---

### Model 1 — `QualityPlan` [QPL-] (`models/QualityManagement/QualityPlans.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "QPL"`. Realizes bullet **1 (planning + standards)** and is the criteria anchor bullets 3/5 inspect against.

#### Choices (exact machine values)
- [ ] `VERIFICATION_METHOD_CHOICES` (`max_length=16`) — `inspection`/Inspection, `testing`/Testing, `demonstration`/Demonstration, `review`/Review, `analysis`/Analysis, `audit`/Audit
- [ ] `STATUS_CHOICES` (`max_length=16`) — `draft`/Draft, `active`/Active, `superseded`/Superseded, `closed`/Closed

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="quality_plans")` — the container
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True, related_name="quality_plans")` — the deliverable; same-project `clean()` guard (the `ProjectMilestone.anchor_task` pattern)
- [ ] `source_risk` `FK("projects.ProjectRisk", SET_NULL, null=True, blank=True, related_name="quality_plans")` — the 7.5 quality-category risk this plan mitigates; same-project guard
- [ ] `title` `CharField(max_length=255)`; `description` `TextField(blank=True)`
- [ ] `acceptance_criteria` `TextField()` — **required** (bullet 1's core)
- [ ] `verification_method` `CharField(max_length=16, choices=VERIFICATION_METHOD_CHOICES, default="inspection")`
- [ ] `standard_reference` `CharField(max_length=120, blank=True)` — free text (`"ISO 9001:2015"`, `"21 CFR Part 11"`); **a standards master is 7.19's** (Ruling 3)
- [ ] `regulatory_requirement` `TextField(blank=True)` — the clause/requirement text
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_quality_plans")`
- [ ] `status` `CharField(max_length=16, choices=STATUS_CHOICES, default="draft")` — **verb-driven, NOT on the form**
- [ ] `planned_review_date` `DateField(null=True, blank=True)` — drives `is_review_overdue`
- [ ] `approved_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="approved_quality_plans")`; `approved_at` `DateTimeField(null=True, blank=True, editable=False)` — stamped by `qpl_approve`
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="qpl_created")`

#### Derived / Meta / behaviour
- [ ] `is_review_overdue` = `planned_review_date` set, `< timezone.localdate()`, and `status in ("draft","active")`
- [ ] `is_locked` = `status in ("superseded","closed")` — edit/delete refuse these rows (the 7.4 `BudgetRevision` frozen-row idiom)
- [ ] `clean()` same-project guards: `wbs_node.project_id == project_id`; `source_risk.project_id == project_id` — field-keyed `ValidationError`s
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes `("tenant","project")` `qpl_tnt_project_idx`, `("tenant","status")` `qpl_tnt_status_idx`, `("tenant","wbs_node")` `qpl_tnt_wbs_idx`, `("tenant","-created_at")` `qpl_tnt_created_idx`
- [ ] `__str__` = `f"{self.number} — {self.title}"`
- [ ] Verbs (POST-only, audited, `previous = obj.status` captured first, `changes={"verb","from","to"}`): `qpl_approve` (login; `draft` → `active`, stamps `approved_by`/`approved_at`; audit `update`); `qpl_supersede` (**`@tenant_admin_required`** — **L27**; `active` → `superseded`; audit `update`). Approved/superseded rows refuse edit/delete of the criteria.
- [ ] Form `QualityPlanForm` excludes `tenant`, `number`, `status`, `approved_by`, `approved_at`, `created_by`; `project`/`wbs_node`/`source_risk`/`owner` tenant-scoped `ModelChoiceField`s (`_reject_foreign` re-checks); `TenantUniqueMixin` FIRST (its `clean()` compares FKs' project)

---

### Model 2 — `QualityReview` [QRV-] (`models/QualityManagement/QualityReviews.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "QRV"`. Realizes bullet **2 (QA)** and bullet **4 (Continuous Improvement)**, discriminated by `review_type` (deliberate consolidation — both are "a structured quality event with a checklist, findings, an owner and actions"; the cut-order fallback is a 5th `QualityImprovement` table, **not** built).

#### Choices
- [ ] `REVIEW_TYPE_CHOICES` (`max_length=24`) — `methodology_review`/Methodology Review, `compliance_check`/Compliance Check, `gate_review`/Gate Review, `kaizen_event`/Kaizen Event, `retrospective`/Retrospective, `maturity_assessment`/Maturity Assessment
- [ ] `STATUS_CHOICES` (`max_length=12`) — `planned`/Planned, `in_progress`/In Progress, `reported`/Reported, `closed`/Closed, `cancelled`/Cancelled
- [ ] `IMPROVEMENT_STATUS_CHOICES` (`max_length=12`) — `n_a`/N/A, `planned`/Planned, `in_progress`/In Progress, `done`/Done

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="quality_reviews")`
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True, related_name="quality_reviews")` (optional anchor; same-project guard)
- [ ] `quality_plan` `FK("projects.QualityPlan", SET_NULL, null=True, blank=True, related_name="reviews")` (optional — the plan checked against; same-project guard)
- [ ] `title` `CharField(max_length=255)`; `scope` `TextField(blank=True)`
- [ ] `review_type` `CharField(max_length=24, choices=REVIEW_TYPE_CHOICES, default="methodology_review")`
- [ ] `checklist` `TextField(blank=True)` — the per-review checklist items; **a reusable checklist library is 7.19's** (no checklist table)
- [ ] `findings` `TextField(blank=True)`
- [ ] `reviewer` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="conducted_quality_reviews")`
- [ ] `review_date` `DateField(default=timezone.localdate)`
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="planned")` — **verb-driven, NOT on the form**
- [ ] `maturity_score` `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])`
- [ ] **Improvement (bullet 4):** `improvement_action` `TextField(blank=True)`; `improvement_owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_quality_reviews")`; `improvement_due_date` `DateField(null=True, blank=True)`; `improvement_status` `CharField(max_length=12, choices=IMPROVEMENT_STATUS_CHOICES, default="n_a")`
- [ ] `closed_at` `DateTimeField(null=True, blank=True, editable=False)`; `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="qrv_created")`

#### Derived / Meta / behaviour
- [ ] `is_improvement_overdue` = `improvement_due_date` set, `< today`, and `improvement_status in ("planned","in_progress")`
- [ ] `is_locked` = `status in ("closed","cancelled")`; `is_improvement` = `review_type in ("kaizen_event","retrospective")`
- [ ] `clean()` same-project guards: `wbs_node.project_id == project_id`; `quality_plan.project_id == project_id`
- [ ] `ordering = ["-review_date", "-id"]`; `unique_together = ("tenant","number")`; indexes `("tenant","project")` `qrv_tnt_project_idx`, `("tenant","review_type")` `qrv_tnt_type_idx`, `("tenant","status")` `qrv_tnt_status_idx`, `("tenant","improvement_status")` `qrv_tnt_imp_idx`, `("tenant","-review_date")` `qrv_tnt_date_idx`
- [ ] `__str__` = `f"{self.number} — {self.title}"`
- [ ] Verbs: `qrv_report` (login; `in_progress` → `reported`; audit `update`); `qrv_close` (login; `reported` → `closed`, stamps `closed_at`; audit `close`). Closed rows refuse edit/delete.
- [ ] Form `QualityReviewForm` excludes `tenant`, `number`, `status`, `closed_at`, `created_by`; `project`/`wbs_node`/`quality_plan`/`reviewer`/`improvement_owner` tenant-scoped; `TenantUniqueMixin` FIRST

---

### Model 3 — `DeliverableInspection` [QCI-] (`models/QualityManagement/DeliverableInspections.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "QCI"`. Realizes bullet **3 (QC execution + result recording)** and bullet **5 (acceptance decision + customer validation + document link)**. Named `DeliverableInspection` because `QualityInspection` is scm 4.9's (Ruling 1).

#### Choices
- [ ] `INSPECTION_TYPE_CHOICES` (`max_length=16`) — `review`/Review, `testing`/Testing, `demonstration`/Demonstration, `walkthrough`/Walkthrough, `acceptance`/Acceptance
- [ ] `RESULT_CHOICES` (`max_length=12`) — `pending`/Pending, `pass`/Pass, `fail`/Fail, `conditional`/Conditional, `not_applicable`/Not Applicable
- [ ] `USAGE_DECISION_CHOICES` (`max_length=24`) — `pending`/Pending, `accept`/Accept, `accept_with_deviation`/Accept with Deviation, `reject`/Reject, `rework`/Rework (the scm 4.9 `USAGE_DECISION_CHOICES` vocabulary; Ruling 4)
- [ ] `STATUS_CHOICES` (`max_length=12`) — `planned`/Planned, `in_progress`/In Progress, `passed`/Passed, `failed`/Failed, `on_hold`/On Hold, `cancelled`/Cancelled

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="quality_inspections")`
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True, related_name="quality_inspections")` (the deliverable; same-project guard)
- [ ] `quality_plan` `FK("projects.QualityPlan", SET_NULL, null=True, blank=True, related_name="inspections")` (criteria inspected against; same-project guard)
- [ ] `milestone` `FK("projects.ProjectMilestone", SET_NULL, null=True, blank=True, related_name="quality_inspections")` — the 7.2 gate the acceptance is reviewed at, **not re-declared** (Ruling 5)
- [ ] `title` `CharField(max_length=255)`; `description` `TextField(blank=True)` (the testing protocol / procedure)
- [ ] `inspection_type` `CharField(max_length=16, choices=INSPECTION_TYPE_CHOICES, default="review")`
- [ ] `planned_date` `DateField(null=True, blank=True)`; `inspected_date` `DateField(null=True, blank=True)` — drives `is_overdue`
- [ ] `inspector` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="conducted_inspections")`
- [ ] `result` `CharField(max_length=12, choices=RESULT_CHOICES, default="pending")`
- [ ] `usage_decision` `CharField(max_length=24, choices=USAGE_DECISION_CHOICES, default="pending")`
- [ ] `findings` `TextField(blank=True)`
- [ ] **Acceptance (bullet 5 — verb-written, NEVER form fields, the 7.4 `decision_notes` rule):** `accepted_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="accepted_inspections")`; `accepted_by_party` `FK("core.Party", SET_NULL, null=True, blank=True, related_name="accepted_inspections")` (external/customer acceptor); `accepted_at` `DateTimeField(null=True, blank=True, editable=False)`; `acceptance_note` `TextField(blank=True)` (conditions/reservations)
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="planned")` — **verb-driven, NOT on the form**
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="qci_created")`

#### Derived / Meta / behaviour
- [ ] `is_overdue` = `planned_date` set, `< today`, `inspected_date` is None, and `status in ("planned","in_progress")`
- [ ] `is_locked` = `status in ("passed","failed","cancelled")` or `usage_decision != "pending"`; `defect_count` = `self.defects.count()`; `is_acceptance` = `inspection_type == "acceptance"`
- [ ] `clean()` same-project guards: `wbs_node.project_id == project_id`; `quality_plan.project_id == project_id`; `milestone.project_id == project_id`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes `("tenant","project")` `qci_tnt_project_idx`, `("tenant","status")` `qci_tnt_status_idx`, `("tenant","result")` `qci_tnt_result_idx`, `("tenant","usage_decision")` `qci_tnt_decision_idx`, `("tenant","wbs_node")` `qci_tnt_wbs_idx`
- [ ] `__str__` = `f"{self.number} — {self.title}"`
- [ ] Verbs (POST-only, audited, `previous` captured first): `qci_record` (login; sets `result` + `inspected_date` + `status`, audit `update`); **`qci_accept`** (login; binds the plain `InspectionAcceptanceForm`; sets `usage_decision` ∈ {`accept`,`accept_with_deviation`}, `accepted_by=request.user`, `accepted_by_party`, `accepted_at=timezone.now()`, `status="passed"`, `acceptance_note`; audit `accept`); `qci_reject` (login; `usage_decision="reject"`, `status="failed"`; audit `reject`). Accepted/failed rows refuse edit/delete.
- [ ] Form `DeliverableInspectionForm` excludes `tenant`, `number`, `usage_decision`, `accepted_by`, `accepted_by_party`, `accepted_at`, `acceptance_note`, `status`, `created_by`; `project`/`wbs_node`/`quality_plan`/`milestone`/`inspector` tenant-scoped; `TenantUniqueMixin` FIRST

---

### Model 4 — `QualityDefect` [QDF-] (`models/QualityManagement/QualityDefects.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "QDF"`. Realizes bullet **3's defect tracking** and bullet **5's punch list**. NOT a second NCR (scm 4.9's) and NOT a second issue log (7.5's) — it links to `ProjectIssue` by FK (Ruling 2).

#### Choices
- [ ] `DEFECT_CATEGORY_CHOICES` (`max_length=16`) — `functional`/Functional, `performance`/Performance, `documentation`/Documentation, `compliance`/Compliance, `dimensional`/Dimensional, `workmanship`/Workmanship, `usability`/Usability, `other`/Other (deliverable-quality categories, deliberately distinct from scm 4.9's goods categories)
- [ ] `SEVERITY_CHOICES` (`max_length=8`) — `critical`/Critical, `major`/Major, `minor`/Minor, `observation`/Observation (the scm 4.9 `NonConformance.SEVERITY_CHOICES` vocabulary, reused verbatim)
- [ ] `DISPOSITION_CHOICES` (`max_length=16`) — `open`/Open, `rework`/Rework, `repair`/Repair, `resubmit`/Resubmit, `accept_as_is`/Accept As Is, `reject`/Reject, `deferred`/Deferred
- [ ] `STATUS_CHOICES` (`max_length=12`) — `open`/Open, `in_progress`/In Progress, `resolved`/Resolved, `closed`/Closed, `cancelled`/Cancelled

#### Fields
- [ ] `project` `FK("projects.Project", CASCADE, related_name="quality_defects")`
- [ ] `wbs_node` `FK("projects.ProjectTask", SET_NULL, null=True, blank=True, related_name="quality_defects")`
- [ ] `quality_plan` `FK("projects.QualityPlan", SET_NULL, null=True, blank=True, related_name="defects")` (the criterion violated; same-project guard)
- [ ] `inspection` `FK("projects.DeliverableInspection", SET_NULL, null=True, blank=True, related_name="defects")` (the inspection that found it)
- [ ] `project_issue` `FK("projects.ProjectIssue", SET_NULL, null=True, blank=True, related_name="quality_defects")` — **the bridge**, written by `qdf_raise_issue`
- [ ] `title` `CharField(max_length=255)`; `description` `TextField()`
- [ ] `defect_category` `CharField(max_length=16, choices=DEFECT_CATEGORY_CHOICES, default="other")`
- [ ] `severity` `CharField(max_length=8, choices=SEVERITY_CHOICES, default="minor")`
- [ ] `disposition` `CharField(max_length=16, choices=DISPOSITION_CHOICES, default="open")`
- [ ] `status` `CharField(max_length=12, choices=STATUS_CHOICES, default="open")` — **verb-driven, NOT on the form**
- [ ] `owner` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_quality_defects")`
- [ ] `identified_date` `DateField(default=timezone.localdate)`; `due_date` `DateField(null=True, blank=True)` — drives `is_overdue`/`age_days`
- [ ] `root_cause` `TextField(blank=True)`; `resolution_note` `TextField(blank=True)`; `resolved_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="resolved_quality_defects")`; `resolved_at` `DateTimeField(null=True, blank=True, editable=False)`
- [ ] `lessons_learned` `TextField(blank=True)` (the 7.5 Ruling-3 idiom — **the repository is 7.10's**)
- [ ] `created_by` `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="qdf_created")`

#### Derived / Meta / behaviour
- [ ] `is_overdue` = `due_date` set, `< today`, `status in ("open","in_progress")`; `age_days` = days since `identified_date`; `is_open` = `status in ("open","in_progress")`; `is_locked` = `status in ("resolved","closed")`
- [ ] `clean()` same-project guards: `wbs_node.project_id == project_id`; `quality_plan.project_id == project_id`; `inspection.project_id == project_id`
- [ ] `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number")`; indexes `("tenant","project")` `qdf_tnt_project_idx`, `("tenant","status")` `qdf_tnt_status_idx`, `("tenant","severity")` `qdf_tnt_severity_idx`, `("tenant","disposition")` `qdf_tnt_disp_idx`, `("tenant","-created_at")` `qdf_tnt_created_idx`
- [ ] `__str__` = `f"{self.number} — {self.title}"`
- [ ] Verbs (POST-only, audited): `qdf_resolve` (login; binds the plain `DefectResolutionForm`; sets `root_cause`/`resolution_note`/`resolved_by=request.user`/`resolved_at=timezone.now()`, `status="resolved"`; audit `resolve`); `qdf_close` (login; `resolved` → `closed`; audit `close`); **`qdf_raise_issue`** (login; creates a `projects.ProjectIssue` — `project`, `wbs_node`, `title`, `description`, `severity` **mapped** `critical→critical`/`major→high`/`minor→medium`/`observation→low` (ProjectIssue's vocabulary), `owner`, `raised_by=request.user`, `identified_date=timezone.localdate()`, `created_by=request.user` — sets `project_issue`, audits `create` on the issue and `update` on the defect; message names both numbers). Resolved/closed rows refuse edit/delete.
- [ ] Form `QualityDefectForm` excludes `tenant`, `number`, `project_issue`, `status`, `root_cause`, `resolution_note`, `resolved_by`, `resolved_at`, `created_by`; `project`/`wbs_node`/`quality_plan`/`inspection`/`owner` tenant-scoped; `TenantUniqueMixin` FIRST

---

### Computed pages (no model — the 7.3 `capacity_demand` / 7.5 `risk_analysis` precedent)

- [ ] **`quality_improvement`** — `views/QualityManagement/QualityImprovement.py`, route `quality-improvement/`, name `quality_improvement`, template `projects/quality/quality_improvement.html`, **GET-only**. Context keys: `projects`, `project` (from `?project=`, `as_db_int`-guarded, tenant-filtered, else None), `improvement_rows` (the project's `QualityReview` with `review_type in ("kaizen_event","retrospective")` ordered `-review_date`, rendering `improvement_status`/`improvement_owner`/`improvement_due_date`), `maturity` (dict `{"score","band","badge","reviews_scored","defects_total","defects_closed","closure_pct"}` — computed over `maturity_score` + defect closure; **no stored maturity table**, Ruling 6), `defect_trend_rows` (period rows `{"period","label","opened","closed","bar_pct"}` aggregated by `identified_date`/`resolved_at` month; CSS bars, **not a chart**, 7.16), `defect_trend_max`, `lessons` (list of `{"obj","lesson"}` over closed defects with non-empty `lessons_learned`, newest first, cap 25; the lens links to 7.10), `lessons_count`, `open_defect_count`, `improvement_open_count`.
- [ ] **`quality_acceptance`** — `views/QualityManagement/QualityAcceptance.py`, route `quality-acceptance/`, name `quality_acceptance`, template `projects/quality/quality_acceptance.html`, **GET-only**. Context keys: `projects`, `project` (from `?project=`, `as_db_int`-guarded), `deliverable_rows` (one row per WBS `deliverable` node of the selected project: `{"wbs_node","plan","plan_status","latest_inspection","result","usage_decision","open_defects","acceptance_state","badge"}` where `acceptance_state` ∈ `pending`/`conditional`/`accepted`/`rejected` and `badge` is the colour-named class — **L33**), `acceptance_queue` (inspections with `inspection_type="acceptance"` and `usage_decision="pending"`, ordered `planned_date`; hosts the `qci_accept` action), `acceptance_queue_count`, `accepted_count`, `conditional_count`, `rejected_count`, `pending_count`.

---

## Backend (`apps/projects/{models,forms,views,urls}/QualityManagement/`) — one file per entity per layer

- [ ] `models/QualityManagement/<Entity>.py` ×4 as specified above; sub-package `__init__.py` files EMPTY; nothing added to the top-level `__init__.py` until Integrate
- [ ] `forms/QualityManagement/<Entity>.py` — `QualityPlanForm`, `QualityReviewForm`, `DeliverableInspectionForm`, `QualityDefectForm` (exclusions pinned per model; `TenantUniqueMixin` BEFORE `TenantModelForm` on every form whose `clean()` compares an FK's project) plus the two **plain `forms.Form`** POST guards: `InspectionAcceptanceForm` (`usage_decision` `ChoiceField` ∈ {`accept`,`accept_with_deviation`}, `accepted_by_party` `ModelChoiceField(queryset=clients(tenant), required=False)`, `acceptance_note` `CharField(required=False, widget=Textarea)`) and `DefectResolutionForm` (`root_cause` `CharField(required=False, widget=Textarea)`, `resolution_note` `CharField(required=True, widget=Textarea)`)
- [ ] `views/QualityManagement/<Entity>.py` — full CRUD via the `crud_*` helpers + the 10 verbs; every queryset `filter(tenant=request.tenant)`, never `.all()`; `_reject_foreign(form, cleaned, [<tenant-scoped FK names>])` per form (never `accounting.Currency` — none this pass); every verb refuses a disallowed transition with `messages.*` + redirect; every `?enum=` value allow-listed against CHOICES (**L11**); capture `previous = obj.status` BEFORE mutating
- [ ] `urls/QualityManagement/<Entity>.py` — literal first segments `quality-plans/`, `quality-reviews/`, `inspections/`, `defects/` plus the two computed `quality-improvement/`, `quality-acceptance/`; literal routes before `<int:pk>/` (first-match-wins)
- [ ] `views/QualityManagement/QualityImprovement.py` + `views/QualityManagement/QualityAcceptance.py` — the two computed pages (no model; the 7.3 `CapacityDemand.py` / 7.5 `RiskAnalysis.py` precedent); absolute imports only

## Views, routes & CONTEXT KEYS — the contract (L7/L8: an unpinned name renders blank at 200)

- [ ] **QualityPlan** — `qpl_list`, `qpl_create`, `qpl_detail`, `qpl_edit`, `qpl_delete`. Routes (prefix `quality-plans/`): `quality-plans/`, `quality-plans/add/`, `quality-plans/<int:pk>/`, `quality-plans/<int:pk>/edit/`, `quality-plans/<int:pk>/delete/`; verbs `quality-plans/<int:pk>/approve/` `qpl_approve`, `quality-plans/<int:pk>/supersede/` `qpl_supersede` (**tenant_admin**). `qpl_list`: qs `QualityPlan.objects.filter(tenant=request.tenant).select_related("project","wbs_node","source_risk","owner","approved_by")`; `search_fields=["number","title","description","acceptance_criteria","standard_reference"]`; `filters=[("project","project_id",True), ("status","status",False), ("verification_method","verification_method",False), ("owner","owner_id",True)]`; derived `?review_due=1`/`?overdue=1` **pre-scoped** (`Q(planned_review_date__lt=timezone.localdate(), status__in=("draft","active"))` — a Python property is not a field lookup, **L11**). `extra_context`: `projects`, `status_choices`, `verification_method_choices`, `owners`. Detail: `obj` + `linked_reviews` (`obj.reviews.select_related("reviewer")`) + `linked_inspections` (`obj.inspections.select_related("inspector","milestone")`) + `linked_defects` (`obj.defects.select_related("owner")`)
- [ ] **QualityReview** — `qrv_list`, `qrv_create`, `qrv_detail`, `qrv_edit`, `qrv_delete`. Routes (prefix `quality-reviews/`): `quality-reviews/`, `quality-reviews/add/`, `quality-reviews/<int:pk>/`, `quality-reviews/<int:pk>/edit/`, `quality-reviews/<int:pk>/delete/`; verbs `quality-reviews/<int:pk>/report/` `qrv_report`, `quality-reviews/<int:pk>/close/` `qrv_close`. `qrv_list`: qs `.select_related("project","wbs_node","quality_plan","reviewer","improvement_owner")`; `search_fields=["number","title","scope","findings","improvement_action"]`; `filters=[("project","project_id",True), ("review_type","review_type",False), ("status","status",False), ("improvement_status","improvement_status",False), ("reviewer","reviewer_id",True)]`; derived lenses **pre-scoped**: `?kind=assurance` → `Q(review_type__in=("methodology_review","compliance_check","gate_review"))`; `?kind=improvement` → `Q(review_type__in=("kaizen_event","retrospective","maturity_assessment"))`; `?overdue=1` → `Q(improvement_due_date__lt=today, improvement_status__in=("planned","in_progress"))`. `extra_context`: `projects`, `review_type_choices`, `status_choices`, `improvement_status_choices`, `owners`. Detail: `obj` + the improvement panel read off `obj`
- [ ] **DeliverableInspection** — `qci_list`, `qci_create`, `qci_detail`, `qci_edit`, `qci_delete`. Routes (prefix `inspections/`): `inspections/`, `inspections/add/`, `inspections/<int:pk>/`, `inspections/<int:pk>/edit/`, `inspections/<int:pk>/delete/`; verbs `inspections/<int:pk>/record/` `qci_record`, `inspections/<int:pk>/accept/` `qci_accept`, `inspections/<int:pk>/reject/` `qci_reject`. `qci_list`: qs `.select_related("project","wbs_node","quality_plan","milestone","inspector","accepted_by","accepted_by_party")`; `search_fields=["number","title","description","findings"]`; `filters=[("project","project_id",True), ("inspection_type","inspection_type",False), ("result","result",False), ("usage_decision","usage_decision",False), ("status","status",False), ("inspector","inspector_id",True)]`; derived `?overdue=1` → `Q(planned_date__lt=today, inspected_date__isnull=True, status__in=("planned","in_progress"))`. `extra_context`: `projects`, `inspection_type_choices`, `result_choices`, `usage_decision_choices`, `status_choices`, `owners`, `parties` (`clients(request.tenant)`). Detail: `obj` + `defects` (`obj.defects.select_related("owner")`) + `accept_form` (unbound `InspectionAcceptanceForm(tenant=request.tenant)`)
- [ ] **QualityDefect** — `qdf_list`, `qdf_create`, `qdf_detail`, `qdf_edit`, `qdf_delete`. Routes (prefix `defects/`): `defects/`, `defects/add/`, `defects/<int:pk>/`, `defects/<int:pk>/edit/`, `defects/<int:pk>/delete/`; verbs `defects/<int:pk>/resolve/` `qdf_resolve`, `defects/<int:pk>/close/` `qdf_close`, `defects/<int:pk>/raise-issue/` `qdf_raise_issue`. `qdf_list`: qs `.select_related("project","wbs_node","quality_plan","inspection","project_issue","owner","resolved_by")`; `search_fields=["number","title","description","root_cause","resolution_note"]`; `filters=[("project","project_id",True), ("severity","severity",False), ("status","status",False), ("disposition","disposition",False), ("defect_category","defect_category",False), ("owner","owner_id",True), ("inspection","inspection_id",True)]`; derived `?overdue=1` → `Q(due_date__lt=today, status__in=("open","in_progress"))`. `extra_context`: `projects`, `severity_choices`, `status_choices`, `disposition_choices`, `defect_category_choices`, `owners`, `inspections` (`DeliverableInspection.objects.filter(tenant=…)`). Detail: `obj` + `resolution_form` (unbound `DefectResolutionForm()`)
- [ ] **Six url first segments pinned — `quality-plans/`, `quality-reviews/`, `inspections/`, `defects/`, `quality-improvement/`, `quality-acceptance/`.** All six are **disjoint literals** from 7.1–7.5's existing first segments (`""`, `project-requests/`, `projects/`, `stakeholders/`, `kickoffs/`, `tasks/`, `dependencies/`, `milestones/`, `baselines/`, `resource-profiles/`, `allocations/`, `time-entries/`, `capacity-demand/`, `budgetlines/`, `revisions/`, `controlaccounts/`, `expenses/`, `risks/`, `responses/`, `issues/`, `escalations/`, `risk-analysis/`, `risk-monitoring/`) **and from the peer 7.7's** (`requirements/`, `scope-items/`, `scope-changes/`, `scope-verifications/`, `scope-matrix/`) — **re-check the concatenated `urls/__init__.py` at Integrate** in case the peer added a segment. No route uses a converter in its first component

## Templates (`templates/projects/quality/`)

- [ ] `qualityplan/{list,detail,form}.html`; `qualityreview/{list,detail,form}.html`; `deliverableinspection/{list,detail,form}.html`; `qualitydefect/{list,detail,form}.html` — list: `.page-header` + breadcrumb, filter bar reflecting `request.GET` (including the derived `?review_due=`/`?overdue=`/`?kind=` lenses), Actions column (eye → detail, pencil → edit, delete POST form + `confirm()` + `{% csrf_token %}`), `.pagination` with `has_previous`/`has_next` guards (**L9**), `.empty-state`
- [ ] The two computed pages live at the sub-module level: `quality_improvement.html`, `quality_acceptance.html` (not inside an entity folder) — the maturity table + band, the defect-trend CSS bars, the lessons lens, the per-deliverable acceptance board
- [ ] Colour-named badge classes only (`badge-green/-amber/-red/-info/-muted/-slate`, **L33**) — run `grep -n '\.badge-' static/css/theme.css` before writing them; every badge block ends `{% else %}{{ obj.get_<field>_display }}{% endif %}`; severity/result/acceptance ternaries copy a sibling verbatim
- [ ] **No nullable FK inside a `|default:` filter argument** (the 7.1 four-500 idiom, **L10**) — use `{% if fk %}…{% else %}—{% endif %}` for `owner`/`approved_by`/`reviewer`/`improvement_owner`/`inspector`/`accepted_by`/`accepted_by_party`/`resolved_by` (all nullable FKs)
- [ ] **Multi-line notes use `{% comment %} … {% endcomment %}`** — never a multi-line `{# … #}` (**L2**); the computed pages carry long caveats (maturity is a computed lens, planning-grade)
- [ ] FK `<select>` comparisons use `|stringformat:"d"`; `{% extends "base.html" %}` unchanged

## Integrate (single writer — the ONLY shared-file step; surgical `Edit`, re-read anchors)

- [ ] Re-export blocks `# --- 7.6 Quality Management` **inserted between the existing `# --- 7.5` and `# --- 7.7` blocks** in all four top-level `__init__.py` (models: 4 models; forms: 6 forms; views: 4 CRUD sets + 2 computed views + 10 verbs; urls: 6 urlpatterns imports + concat — the `urls/__init__.py` imports + tuple concat also go **between the 7.5 and 7.7 groups**). A missing re-export is a runtime `ImportError`
- [ ] `admin.py` — 4 registrations appended after the 7.5 block (`list_display` led by `number`, `list_select_related` for every rendered FK, `approved_at`/`closed_at`/`accepted_at`/`resolved_at` readonly)
- [ ] `seed_projects.py` — `_quality` block with its OWN guard (`QualityPlan.objects.filter(tenant=tenant).exists()`), called per tenant: 3–5 `QualityPlan` rows anchored to existing WBS **deliverable** nodes spanning all `verification_method` values and both `standard_reference` populated/blank, one `approved` (stamped) and one `superseded`; 4–6 `QualityReview` rows spanning all `review_type` values (one `methodology_review` reported, one `kaizen_event` with `improvement_action`/owner/due date, one `maturity_assessment` with a `maturity_score`); 5–8 `DeliverableInspection` rows spanning all `result` and `usage_decision` values, including one **acceptance** inspection with `accepted_by`/`accepted_by_party`/`accepted_at` stamped and a `core.Document` certificate, and one `conditional` acceptance with open punch-list defects; 6–10 `QualityDefect` rows across all severities/categories/dispositions, one resolved (stamped) and linked to a `ProjectIssue` via `qdf_raise_issue`, one overdue, one with a non-empty `lessons_learned`. Enough rows for page 2. `--flush` deletes **children-first**: `QualityDefect, DeliverableInspection, QualityReview, QualityPlan`
- [ ] `views/_helpers.py` — **reuse the existing `owners(tenant)`** (added by 7.5, line 79) and `clients(tenant)` (for `accepted_by_party`); **add nothing**
- [ ] `apps/core/navigation.py` — one new `LIVE_LINKS["7.6"]` immediately after the `"7.5"` block (~`:1766`), verbatim from the research: `Quality Planning & Standards` → `projects:qpl_list`; `Quality Assurance (QA)` → `projects:qrv_list?kind=assurance`; `Quality Control (QC) & Inspections` → `projects:qci_list`; `Continuous Improvement` → `projects:quality_improvement`; `Deliverable Acceptance & Sign-off` → `projects:quality_acceptance`; extra live leaves `Quality Review Register` → `projects:qrv_list` and `Defect & Punch List` → `projects:qdf_list`; the justification comments record the deliberate computed-page mapping (bullets 4/5 are aggregations over the registers). `_safe_reverse` supports both `url#frag` and `?query=` (confirmed)
- [ ] `templates/projects/overview.html` — 7.6 quick links + counts (open defects, overdue inspections, acceptance queue), mirroring the 7.5 block
- [ ] **DB LAST**: `python manage.py makemigrations projects --dry-run` — **read every model the dry-run lists; if it names a model you did not write (or a peer's 7.7 model), STOP and report** (a missing re-export, or the concurrent session). Then generate (**number = disk leaf read now** — `0007_…` if still free, else the next free leaf; never reserve), `migrate`, `seed_projects` ×2 (second run a no-op), `manage.py check`

## Verify

- [ ] `temp/` smoke sweep as `admin_acme` / `password` (NOT the tenant-less `admin`):
      - [ ] every new `projects:*` url 200 (405 for the POST-only verbs hit by GET — `qpl_approve`, `qpl_supersede`, `qrv_report`, `qrv_close`, `qci_record`, `qci_accept`, `qci_reject`, `qdf_resolve`, `qdf_close`, `qdf_raise_issue`); content asserts, not just status — page titles, a seeded `QPL-`/`QRV-`/`QCI-`/`QDF-` number, the maturity board renders, the acceptance board renders, no `{#` / `{% comment` leaks (**L8**)
      - [ ] junk params `?status=nope`, `?project=0`, `?kind=nope`, `?page=9999`, `?inspection=abc` → default page, never a 500, never a silently emptied register (**L11** allow-list + `as_db_int`)
      - [ ] page 2 of the quality-plan and defect registers; cross-tenant IDOR → 404 on every `<int:pk>` route
      - [ ] state machine holds: approve-twice refused, supersede-on-draft refused, report-on-planned refused, accept-on-locked refused, resolve-twice refused, raise-issue-twice refused (already linked), member 403 on `qpl_supersede` (**L27**)
      - [ ] hand-computed spot check: one seeded defect's `is_overdue`/`age_days` matches; the `?kind=improvement` lens returns exactly the kaizen/retro/maturity rows; `qdf_raise_issue` maps `major→high`
- [ ] Sidebar shows **7.6 Live** with all five bullets + the review-register and defect-punch-list leaves

## Close-out (Module Creation Sequence phases 4–7)

- [ ] Review agents, one after another, each appending to `.claude/tasks/review-projects-7.6.md`: `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`
- [ ] `code-fixer` burns the deduped, ID'd findings (Critical → Important → Minor), one commit per file
- [ ] Tests: append `quality_*` fixtures to `conftest.py` (**owned by itself — only with a full unfiltered re-run**), then `test_quality_models.py` → `test_quality_forms.py` → `test_quality_views.py` → `test_quality_security.py`, one file per commit, tests named `test_quality_*`, helpers `_quality_*` (no shadowing of the `test_initiation_*`/`test_planning_*`/`test_resource_*`/`test_cost_*`/`test_risk_*` namespaces), then **one full unfiltered run** (never `-k`, **L47**; iterate with `--nomigrations`)
- [ ] `.claude/skills/projects/SKILL.md` — append the 7.6 section (the four models + prefixes, the derived-property rulings, the verb table with gates/audit strings, the six routes, the two computed pages + their context contracts, the seeder `_quality` block, gotchas incl. the computed-lens pre-scoping and the `qdf_raise_issue` severity map) and update the frontmatter "As-built" line
- [ ] Mark 7.6 complete in `README.md`

## Later passes / deferred (carried verbatim from the research so nothing is lost)

- [ ] **The enterprise NCR / CAPA / audit programme / calibration** — `scm` 4.9 owns them today; 7.6 is project-scoped (Ruling 1). A defect → `scm.NonConformance` bridge waits on a project FK on that table — **flag for the 12.x QMS session**
- [ ] **Test-step child table** (steps + expected outcomes, shared steps/parameters) — Azure Test Plans' differentiator; the protocol `description` is the honest stand-in this pass
- [ ] **Test configurations / parameterised test data** (OS/browser/data sets) — needs a configuration-matrix model; not table-stakes
- [ ] **A reusable standards / regulatory-clause library** — master data → 7.19; `standard_reference` is free text (Ruling 3)
- [ ] **A reusable checklist library + methodology templates** — master data → 7.19; the per-review checklist is a text field
- [ ] **Automated test execution / CI integration** (qTest Launch, pipelines) — integration → 7.18
- [ ] **Recurring audit schedules, auto-escalation, review reminders** — no scheduler/mail worker (7.1/6.8/6.19 recorded it); 7.17's; badges and audit rows only
- [ ] **Configurable approval ladders + electronic signature (21 CFR Part 11)** — a workflow-engine feature → 7.17; scm 4.9 parked the identical item
- [ ] **A stored process-maturity score / assessment table** — a computed page this pass (Ruling 6) — a stored score goes stale the instant an input changes
- [ ] **Acceptance-certificate PDF generation / report builder / exports** — 7.16 (BI/reporting); 7.6 renders a printable acceptance page
- [ ] **Defect escape rate / rework rate KPIs** — KPI definitions are master data (7.19) and values need a metrics engine; defect counts stand in
- [ ] **Acceptance → milestone billing / handover workflow** — 7.15 (billing) / 7.14 (handover); 7.6 records the acceptance only (no GL — Ruling 7)
- [ ] **External test-management / GRC sync** (Jira/Xray/Zephyr/TestRail, ServiceNow) — integration → 7.18; a `source_number`-style soft reference would be the pattern
- [ ] **Cross-project / portfolio quality roll-up** — 7.12 (portfolio)

### 7.2 — review, fixer and tests (closing record)

**Review pass:** six read-only lanes (code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer) appended to
`.claude/tasks/review-projects-7.2.md`, consolidated into a triage of C1 / I1–I7 / M1–M11.
Headliners: cross-project parent left a task invisible in every WBS tree (C1); verb-gated fields
(`status` on MilestoneForm, `baseline_type` on BaselineForm) were member-settable through the
ungated edit forms (I1/I2); `project.name` interpolated into an onsubmit JS string (I3, stored-XSS
shape); 403 buttons for members (I4); dead `?project=` deep-link (I5); unused select_related hops
(I6). **code-fixer** closed every finding in ID order (21 commits, one file each; I7/tests and
M11/recorded deliberately out of its scope) and re-verified: `manage.py check` clean,
`makemigrations --check` clean, both smoke scripts pass.

**Tests (Phase 6):** test contract pinned in `.claude/tasks/test-contract-projects-7.2.md`;
conftest extended with the `planning_*` fixture block (owned by that step alone);
`test_planning_{models,forms,views,security}.py` = 16/15/21/12 tests (the security file expands to
35 cases via route parametrization) — every finding from the triage is pinned by a test. One
test-side fix during bring-up: the hygiene test under-fixture'd `dep_list` (no dependency row →
empty state → its own vacuous-guard fired); it now creates the row and walks dep_detail too.
**Full unfiltered projects suite: green (exit 0)** — including the parallel session's 7.3/7.4
tests running in the same tree.

**Skill:** `.claude/skills/projects/SKILL.md` updated to as-built 7.2 (models, routes, verbs,
templates, seeder shape, four new gotchas, sidebar wiring).

---

## Projects 7.3 — Resource Management (build record)

**Delivered (one sub-module, per the /next-module rule):** 3 models — `ResourceProfile` [RSP-]
(the pool register: an internal person via `hrm.EmployeeProfile` OR an external via `core.Party`,
exactly one of the two, `weekly_capacity_hours` as the denominator of every capacity computation;
skills/certs stay HRM 3.40's lens), `ResourceAllocation` [RAL-] (the booking: NULL `resource` =
placeholder, project OR request OR refused, one magnitude matching one of three units,
`booking_status` verb-driven, `substitute_of` chains; `planned_hours()` = the crm proration
extended to all three units, cancelled AND released count zero), `ResourceTimeEntry` [RTE-] (the
thinnest project-facing time log — NOT a fourth timesheet; draft→submitted→approved/rejected via
verbs only, stamps written exactly once, `week_key` for the regroup). Plus the computed
**capacity_demand** board (no model): over-allocation cells per resource-week + the `id="demand"`
hiring-trigger section.

**Surfaces:** 3 forms, 25 routes (rsp 5, ral 10 incl. 5 verbs, rte 9 incl. `rte_approve_week`'s
literal-first week route, + capacity_demand), 21 views (9 verbs: assign/substitute/approve/reject/
approve_week tenant-admin gated; commit/complete/cancel/submit member-level), 11 templates,
migration 0004 (3 tables + 12 named indexes), seeder `_resourcing` block (own guard; 5 RSP / 10
RAL / 16 RTE per tenant exercising every status/unit/placeholder kind + a released→successor
chain; RAL-00001 at 48h/wk keeps the over-allocation alert alive), admin registrations (verb-state
columns frozen readonly), `LIVE_LINKS["7.3"]` (5 verbatim bullets + "Time Approvals" leaf),
overview counts + stat cards + quick links, 2 new `_helpers` dropdown builders.

**Key design decisions:** a NULL resource is a placeholder STATE, never a fake person row
(Float/Resource Guru norm); the request folds into the allocation (`booking_status="requested"` +
`project_request` FK — no separate booking-request table); leveling = alert + manual rebalance
via the verbs (no smoothing engine — the market norm the research found); `hrm.TimesheetEntry`
cannot join `projects.Project` (its FK points at the 2.9 `accounting.Project` stand-in), hence
the thin RTE table; the regroup weekly lens is template-side over the flat paginated register.

**Verification:** migrate OK; seed x2 idempotent + `--flush` children-first path exercised;
`manage.py check` + `makemigrations --check` clean; build smoke (`temp/smoke_73.py` + reset):
all 25 routes 200 with content, junk params, page 2, verbs POST-only, member 403s, cross-tenant
IDOR 404s, leak scan — ALL PASSED. Review: 6 serial lanes → ~32 raw findings → 0C/7I/11M + 5
no-actions; code-fixer fixed **18/18, 0 skipped** (incl. the confirm() name interpolation, the
Assign/Substitute `{% if %}` precedence bug, the firm-placeholder dead end, the substitute race
guard, and the register N+1s). Tests: `test_resource_{models,forms,views,security}.py` = 79/63/
119/106 items green (`--nomigrations` per-file); full unfiltered app gate run at close-out.


## Review notes

### Projects 7.4 — Cost & Budget Management (close-out 2026-09-12)

Six review lanes ran serial (code/explorer/frontend/performance/qa-smoke/security) into
`.claude/tasks/review-projects-7.4.md`: raw 2C/6I/19M, deduped **2C/5I/14M + N1-N2 no-actions**.
The code-fixer closed **all 21** (`[x]` in the review file; M14/N1/N2 recorded no-action) in 36
path-limited commits — headline catches: `cca_delete` would have 500'd on every seeded CA
(ProtectedError, C1) and the CCA EVM property chain made `cca_list` 75 queries / `cca_detail` 119
(C2, fixed with `cached_property`: 22 / 14). The security lane's I1 ruling froze the active
baseline through its LINES too. Tests: `cost_*` fixtures in conftest (a73e4022) +
`test_cost_{models,forms,views,security}.py` = 67/42/41/50 green, one file per commit; the smoke
harness went 297 -> 301 green across the fix pass. Full unfiltered app gate at close-out. Migration
0005 generated by disk leaf AFTER 7.3's 0004 landed; the dry-run swept in exactly the four 7.4
models, nothing of any peer's.
