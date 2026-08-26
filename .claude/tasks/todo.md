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
