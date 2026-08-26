# FROZEN BUILD CONTRACT — Procurement 6.9 Catalog Management (migration 0012)

Builders implement ONE entity stack each (model+form+views+urls+3 templates) and NOTHING else.
Shared files (`__init__.py` re-exports, admin.py, seed_procurement.py, navigation.py,
app urls/__init__.py, migrations) belong to the solo Integrator. No git, no migrate, no DB
writes by builders. Imports are ABSOLUTE. Cross-entity references import the entity MODULE
directly (`from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem`)
— never the not-yet-wired sub-package.

## Shared toolkit (verified)
- Models: `from apps.procurement.models._base import *` → TenantOwned / TenantNumbered
  (`NUMBER_PREFIX`, auto `number`, unique per (tenant,number) declared in YOUR Meta),
  q2()/MAX_Q2/ZERO, ValidationError, MinValueValidator, transaction, timezone, Q/F/Sum, secrets.
- Forms: `from apps.procurement.forms._common import *` → forms, ValidationError,
  TenantModelForm (auto-scopes tenant FK querysets), TenantUniqueMixin (mix FIRST),
  `_reject_foreign(form, cleaned, names)` crafted-POST FK re-check.
  NOTE: `accounting.Currency` is GLOBAL (no tenant column) — leave unscoped.
- Views: `from apps.procurement.views._common import *` → login_required, messages,
  get_object_or_404/redirect/render, timezone, require_POST, crud_* helpers,
  tenant_admin_required, write_audit_log.
- crud_list(request, qs, template, search_fields=[], filters=[(param, lookup, is_int)],
  extra_context={}) → ctx keys `object_list/page_obj/q`; boolean GET values map True/False;
  int filters guard junk (as_db_int). crud_detail ctx key `obj`. Form pages ctx `form`,`is_edit`
  (+`obj` on edit). Apply ALL GET filtering BEFORE pagination (crud_list does).
- URL first segments (collision-checked free): `catalog-items/`, `catalog-tiers/`,
  `punchout/`, `catalog-uploads/`.
- Templates extend `base.html` (blocks title/content/extra_css/extra_js). Badges ONLY
  badge-green/red/amber/info/muted/slate. stat-icon colours blue/green/orange/purple/slate.
  Icons: items→package, tiers→tags, endpoints→plug, uploads→file-up; row actions eye/pencil/trash-2.

## Entity 1 — CatalogItem [PCI-]  (lane A)
File set: `apps/procurement/{models,forms,views,urls}/CatalogManagement/CatalogItems.py`
+ `templates/procurement/catalogmanagement/catalogitem/{list,detail,form}.html`

MODEL `CatalogItem(TenantNumbered)`, NUMBER_PREFIX="PCI":
- source_type Char(20) choices SOURCE_TYPES=[("internal","Internal stock item"),("supplier_product","Supplier product")] default "internal"
- item FK "scm.Item" SET_NULL null blank related_name="procurement_catalog_items"
- supplier FK "core.Party" SET_NULL null blank related_name="procurement_catalog_supplier_items"
- contract FK "scm.SupplierContract" SET_NULL null blank related_name="procurement_contract_catalog_items"
- name Char(255); supplier_part_no Char(64) blank; description TextField blank; manufacturer Char(120) blank
- uom FK "scm.UOM" SET_NULL null blank related_name="procurement_catalog_item_uoms"
- currency FK "accounting.Currency" SET_NULL null blank related_name="procurement_catalog_item_currencies"
- base_price Decimal(14,2) default ZERO validators=[MinValueValidator(ZERO)]
- status Char(20) STATUS_CHOICES=[("draft","Draft"),("pending_approval","Pending approval"),("approved","Approved"),("rejected","Rejected"),("blocked","Blocked"),("archived","Archived")] default "draft"; EDITABLE_STATUSES=("draft","rejected")
- submitted_by/approved_by FK settings.AUTH_USER_MODEL SET_NULL null blank related_name="procurement_catalog_items_submitted"/"..._approved"; submitted_at/approved_at DT editable=False null blank
- rejection_reason TextField blank; created_by FK AUTH_USER_MODEL SET_NULL null blank related_name="procurement_catalog_items_created"
- is_preferred Bool default False; is_active Bool default True; category_text Char(120) blank
- clean(): internal→item required AND item.tenant_id==self.tenant_id; supplier_product→name required
- actions (return bool, stamp *_at via timezone.now(), save(update_fields=[...])): submit() draft|rejected→pending_approval(+submitted_by=user param); approve(user) pending_approval→approved; reject(user,reason) pending_approval→rejected(+rejection_reason); block() approved→blocked; archive() approved|rejected|blocked→archived
- property is_purchasable = status=="approved" and is_active
- Meta ordering ["-created_at","-id"]; unique_together [("tenant","number")]; indexes prc_catitem_tnt_status_idx (tenant,status), prc_catitem_tnt_item_idx (tenant,item)

FORM `CatalogItemForm(TenantUniqueMixin, TenantModelForm)`: fields=["source_type","item","supplier","contract","name","supplier_part_no","description","manufacturer","uom","currency","base_price","category_text","is_preferred","is_active"]; _reject_foreign(form, cleaned, ["item","supplier","contract","uom"]); clean() mirrors model rules.

VIEWS (names pinned): catalog_item_list (search ["number","name","supplier_part_no","category_text"]; filters [("status","status",False),("source_type","source_type",False),("supplier","supplier_id",True),("is_preferred","is_preferred",False)]; select_related item,supplier,uom,currency; extra_context: status_choices=STATUS_CHOICES, source_choices=SOURCE_TYPES, supplier_choices=Party.objects.filter(tenant=request.tenant).order_by("name") [import core Party], stats dict keys total/pending/approved/blocked from ONE .aggregate(Count with Q filters)); catalog_item_detail (select_related item,supplier,contract,uom,currency,created_by,submitted_by,approved_by; ctx tiers=obj.price_tiers.select_related("contract").order_by("min_quantity")); catalog_item_create/catalog_item_edit via hand-rolled `_item_form(request, instance)` (RfxEvents._event_form precedent: stamps created_by on create; edit guarded to EDITABLE_STATUSES else messages.error + redirect detail); catalog_item_delete via crud_delete; POST @require_POST verbs catalog_item_submit/approve/reject/block (reject reads request.POST.get("reason","")) each: fetch tenant-scoped, call action, on False messages.error else messages.success + write_audit_log(request.user,obj,"<verb>") ; redirect to detail.
URL names: catalog_item_list/_create/_detail/_edit/_delete/_submit/_approve/_reject/_block on paths "catalog-items/" , "catalog-items/add/", "catalog-items/<int:pk>/", ".../edit/", ".../delete/", ".../submit/", ".../approve/", ".../reject/", ".../block/". Literal routes before <int:pk> blocks within the module.

TEMPLATES: list = page-header(title+breadcrumb Procurement/Catalog Management/Catalog Items)+page-actions Add btn-primary; 4 stat-cards (total blue package, pending orange clock, approved green check-circle, blocked slate ban); card > filter GET form (q text + status/source selects + supplier pk-select using |stringformat:"d" selected-compare + preferred select True/False) + Apply/reset; table columns Number, Item(name w/ source badge), Supplier/Contract, Price(currency+base_price), Status badge map draft→badge-muted pending_approval→badge-amber approved→badge-green rejected→badge-red blocked/archived→badge-slate ({% else %}{{ obj.get_status_display }}), Preferred (star icon when is_preferred), Actions. Pagination + empty-state copied structurally from templates/procurement/rfxmanagement/events/list.html (READ IT). detail = definition grid all fields + flags + audit stamps; side panel lifecycle buttons gated by status (Submit when draft/rejected; Approve+Reject-with-reason-input when pending_approval; Block when approved) each a small POST form csrf; Price tiers table (min_quantity, unit_price/discount_pct, effective window, contract number, status badge draft→badge-muted active→badge-green superseded→badge-slate cancelled→badge-red); Back link. form = two-column form-groups; source_type toggle hint text ("Internal requires a stock item"); is_edit labels Update vs Create; Cancel back.

## Entity 2 — CatalogPriceTier  (lane B)
Files: .../CatalogManagement/Tiers.py ×4 layers + templates/procurement/catalogmanagement/tier/{list,detail,form}.html

MODEL `CatalogPriceTier(TenantOwned)`:
- catalog_item FK "procurement.CatalogItem" CASCADE related_name="price_tiers"
- min_quantity Decimal(14,2) default Decimal("1") validators=[MinValueValidator(ZERO)]
- unit_price Decimal(14,2) default ZERO validators=[MinValueValidator(ZERO)]
- discount_pct Decimal(5,2) null blank validators=[MinValueValidator(ZERO)] (cap 100 in clean)
- valid_from DateField null blank; valid_until DateField null blank
- contract FK "scm.SupplierContract" SET_NULL null blank related_name="procurement_contract_price_tiers"
- status Char(12) STATUS_CHOICES=[("draft","Proposed"),("active","Active"),("superseded","Superseded"),("cancelled","Cancelled")] default "draft"
- submitted_by FK AUTH_USER_MODEL SET_NULL null blank related_name="procurement_price_tiers_submitted"; approved_by ..._approved; approved_at DT editable=False null
- clean(): valid_until>=valid_from when both; overlapping ACTIVE tier same item+min_quantity → ValidationError (query siblings exclude self)
- method effective_price(base): unit_price if discount_pct is None else q2(base*(1-discount_pct/100))
- actions: approve(user) draft→active (+approved_by/at); retire() active→superseded; cancel() draft|superseded→cancelled
- Meta ordering ["catalog_item_id","min_quantity"]; unique_together ("tenant","catalog_item","min_quantity","valid_from"); index prc_cattier_tnt_status_idx

FORM `CatalogPriceTierForm(TenantUniqueMixin, TenantModelForm)`: fields=["catalog_item","min_quantity","unit_price","discount_pct","valid_from","valid_until","contract"]; _reject_foreign ["catalog_item","contract"].

VIEWS: catalog_tier_list (search ["catalog_item__name","catalog_item__number"]; filters [("status","status",False),("catalog_item","catalog_item_id",True)]; select_related catalog_item,contract; extra: status_choices, item_choices=CatalogItem.objects.filter(tenant=...).order_by("name"), stats proposed/active/superseded one-aggregate); catalog_tier_detail (ctx obj + item_tiers=obj.catalog_item.price_tiers.exclude(pk=obj.pk).order_by("min_quantity")); create/edit hand-rolled `_tier_form` (stamps submitted_by on create; edit only while status=="draft"); delete crud_delete; verbs catalog_tier_approve / catalog_tier_retire (POST-only pattern as lane A).
URL names catalog_tier_* on "catalog-tiers/", add/, <int:pk>/, edit/, delete/, approve/, retire/.

TEMPLATES: list stats (proposed amber tags, active green tags, superseded slate layers); columns Tier(item name+number link), Break(min_quantity), Pricing(unit_price or −discount_pct%), Window(valid_from–valid_until, open-end em dash), Contract(number), Status badge proposed→badge-muted active→badge-green superseded→badge-slate cancelled→badge-red, Actions. Detail shows effective price table against item base_price (call obj.effective_price(obj.catalog_item.base_price)) + sibling tiers. Form notes: leave discount_pct blank to use unit_price.

## Entity 3 — PunchOutEndpoint [POE-]  (lane C)
Files: .../CatalogManagement/PunchOutEndpoints.py ×4 + templates/procurement/catalogmanagement/punchoutendpoint/{list,detail,form}.html

MODEL `PunchOutEndpoint(TenantNumbered)` NUMBER_PREFIX="POE":
- party FK "core.Party" CASCADE related_name="punchout_endpoints"
- name Char(120); protocol Char(20) PROTOCOL_CHOICES=[("cxml","cXML"),("oci","SAP OCI"),("manual_link","Manual link")] default "cxml"
- punchout_url URLField; username Char(120) blank
- shared_secret Char(255) blank  ← # WARNING comment: demo stores verbatim; production must store prefix+SHA-256 only (tenants.EncryptionKey precedent); never logged/rendered
- enabled Bool default True; last_session_at DT editable=False null blank; notes TextField blank
- action record_session(): last_session_at=timezone.now(); save(update_fields)
- Meta ordering ["-created_at","-id"]; unique_together [("tenant","number")]; index prc_poe_tnt_enabled_idx (tenant,enabled)

FORM `PunchOutEndpointForm(TenantUniqueMixin, TenantModelForm)`: fields=["party","name","protocol","punchout_url","username","shared_secret","enabled","notes"] on CREATE; on EDIT (instance.pk) pop "shared_secret" in __init__ so the secret is NEVER rendered nor required; # WARNING comment inline.

VIEWS: punchout_endpoint_list (search ["name","party__name","punchout_url"]; filters [("protocol","protocol",False),("enabled","enabled",False)]; select_related party; extra protocol_choices, stats total/enabled); punchout_endpoint_detail (obj; secret shown as fixed "••••••••" placeholder — never value); create/edit HAND-ROLLED `_endpoint_form` (addendum: edit path passes audit changes EXCLUDING shared_secret — local `_redacted_changes(form)` helper skipping that field; create logs plain write_audit_log create); delete crud_delete; verb punchout_endpoint_test POST → record_session() + message "Handshake execution is deferred; session timestamp recorded." + audit "test".
URL names punchout_endpoint_* on "punchout/", add/, <int:pk>/, edit/, delete/, test/.

TEMPLATES: list stats (endpoints blue plug, enabled green plug-zap, cXML info); columns Number, Endpoint(name+party), Protocol badge cxml→badge-info oci→badge-amber manual_link→badge-muted, URL truncated, Enabled (green check/slate x), Last session, Actions. Detail panel + Test connection button (POST). Form: secret input type password, help text "Write-only: left blank on edit, stored for this workspace only."

## Entity 4 — CatalogUploadBatch [CUB-]  (lane D)
Files: .../CatalogManagement/UploadBatches.py ×4 + templates/procurement/catalogmanagement/uploadbatch/{list,detail,form}.html

MODEL `CatalogUploadBatch(TenantNumbered)` NUMBER_PREFIX="CUB":
- party FK "core.Party" SET_NULL null blank related_name="catalog_upload_batches"
- original_filename Char(255) blank (auto-stamped in save() from file.name)
- file FileField upload_to="procurement/catalog_uploads/%Y/%m/"
- ALLOWED_EXTENSIONS=(".csv",".xls",".xlsx",".xml") enforced in clean()
- status Char(12) STATUS_CHOICES=[("received","Received"),("validated","Validated"),("published","Published"),("rejected","Rejected")] default "received"; EDITABLE_STATUSES=("received",)
- validated_by FK AUTH_USER_MODEL SET_NULL null blank related_name="procurement_upload_batches_validated"; validated_at DT editable=False null
- rows_parsed/rows_accepted/rows_rejected PositiveIntegerField default 0 editable=False
- error_log TextField blank editable=False (line-numbered "row N: reason")
- notes TextField blank
- validate_and_stage(user): only from received; parse CSV utf-8-sig headers name,supplier_part_no,unit_price,uom_code,category_text (extra headers ignored); per row build CatalogItem(source_type="supplier_product", status="pending_approval", tenant, currency=None) linking uom by uom_code when found, supplier=self.party; invalid rows → error lines; counters set; batch.status="validated" (or "validated" even with rejects — error_log carries detail; fully-empty file → status stays received + False); stamp validated_by/at; wrap item creation in transaction.atomic; returns (ok, staged_count)
- publish(): validated→published; reject(): received|validated→rejected
- Meta ordering ["-created_at","-id"]; unique_together [("tenant","number")]; index prc_catupload_tnt_status_idx

FORM `CatalogUploadBatchForm(TenantUniqueMixin, TenantModelForm)`: fields=["party","file","notes"]; clean enforces extension allowlist.

VIEWS: catalog_upload_list (search ["number","original_filename","notes"]; filters [("status","status",False),("party","party_id",True)]; select_related party,validated_by; extra status_choices, party_choices, stats received/validated/published one-aggregate); catalog_upload_detail (obj; render error_log in <pre>; show counters); create/edit hand-rolled `_batch_form` (request.FILES flows through form; edit gated to received); delete crud_delete; verbs catalog_upload_validate (runs validate_and_stage, success msg shows staged count), catalog_upload_publish, catalog_upload_reject — POST-only, audit "<verb>".
URL names catalog_upload_* on "catalog-uploads/", add/, <int:pk>/, edit/, delete/, validate/, publish/, reject/.

TEMPLATES: list stats (received info file-up, validated green check-square, published purple upload — stat-icon purple allowed); columns Number, File(original_filename), Supplier(party), Rows(parsed/accepted/rejected mono trio), Status badge received→badge-info validated→badge-green published→badge-purple?? — NO: badge-purple DOES NOT exist → published→badge-green, rejected→badge-red, Actions. Detail: counters grid, error_log pre block (only when rows_rejected>0), Validate/Publish/Reject buttons gated by status, download link to file.url. Form: enctype multipart note handled by form template pattern (copy rfx form file-upload idiom if present; else standard form rendering includes file input).

## Seeder (Integrator-only) `_seed_catalog(self, tenant)`
Guard per entity `if <Model>.objects.filter(tenant=tenant).exists(): return/skip`.
Reuse existing masters: first scm.Item + its uom, Currency.objects.first(), suppliers via existing helper `_eauc_supplier(tenant, name)` pattern (read it). Rows: 1 internal approved+preferred CatalogItem (item/uom/currency set) with TWO active tiers (10/50 breaks); 1 supplier_product pending_approval; 1 blocked supplier product; 2 PunchOutEndpoints (cxml enabled "Amazon Business (sandbox)", manual_link disabled "Grainger public catalogue"); 1 CUB batch validated with rows_parsed=8 accepted=6 rejected=2 + two error_log lines. Friendly skip message when prerequisites missing ("run seed_scm first").

## LIVE_LINKS["6.9"] (Integrator-only, apps/core/navigation.py)
Comment line above matching house style, then:
{"Catalog Item Creation": "procurement:catalog_item_list",
 "Pricing & Tier Management": "procurement:catalog_tier_list",
 "Catalog Approval Workflow": "procurement:catalog_item_list?status=pending_approval",
 "Punch-out Catalog Integration": "procurement:punchout_endpoint_list",
 "Supplier Catalog Hosting": "procurement:catalog_upload_list"}
