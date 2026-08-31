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
(filled in at the end)
