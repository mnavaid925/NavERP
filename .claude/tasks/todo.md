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
