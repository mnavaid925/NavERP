# Deduplicated Review Findings: Sub-module 10.17 Embedded & Mobile BI

**Base commit:** `a3d989bc06eda3b74ce2a67a70785992ec94fca0`  
**Target changeset:** `a3d989bc06eda3b74ce2a67a70785992ec94fca0..HEAD`  
**Review Passes:**  
1. `code-reviewer` (Django correctness, multi-tenancy, authorization, contracts)
2. `explorer` (contract adherence, view context keys, URLconf, spine reuse)
3. `frontend-reviewer` (templates, design system theme.css classes, L2, L33, L9, L10)
4. `performance-reviewer` (ORM efficiency, N+1 queries, indexes, atomic writes)
5. `qa-smoke-tester` (runtime test client verification, IDOR probes, junk parameters)
6. `security-reviewer` (auth/authz, IDOR, XSS, CSRF, secrets management)

---

## Critical

- [x] **C1: Inverted `write_audit_log` call signatures cause 100% POST mutations (create, edit, delete, revoke) to fail with TypeError / HTTP 500** — fixed in `ed9607c6`, `3a7d845d`, `8008a2d6`, `5dc2b03b` (corrected write_audit_log call signatures across all 4 view modules)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/*.py` (13 call sites: `EmbeddedAnalyticsConfigs.py:90, 172, 196`; `KioskWallboardDisplays.py:89, 141, 165`; `MobileBiConfigurations.py:93, 152, 176`; `EmbedApiTokens.py:78, 159, 183, 202`)
  - **Issue**: Views call `write_audit_log(request, action=..., instance=..., description=...)`, but `apps/core/utils.py` defines `write_audit_log(user, obj, action, changes=None, tenant=None)`. This triggers `TypeError: write_audit_log() got an unexpected keyword argument 'instance'` and crashes with HTTP 500 on every single create/edit/delete/revoke POST request.
  - **Fix**: Update all 13 call sites to `write_audit_log(request.user, obj, action, tenant=request.tenant)`.

- [x] **C2: Unauthenticated cross-tenant telemetry poisoning, device spoofing, and IDOR on Kiosk Heartbeat endpoint** — fixed in `cd70db35` (enforced @require_POST, tenant scoping for authenticated calls, constant-time passcode check, and atomic .update)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:214-234`
  - **Issue**: `kiosk_wallboard_display_heartbeat` lacks `@require_POST`, `@login_required`, tenant scoping, and passcode checks. Any external client can query arbitrary PKs across all tenants, which discloses `display.number` and overwrites `last_heartbeat_at`, `device_ip_address`, and `device_user_agent`.
  - **Fix**: Apply `@require_POST`. If caller is authenticated, enforce tenant scoping; if unauthenticated, verify `access_passcode` matching the display via `secrets.compare_digest`. Collapse query into a single atomic `.filter(pk=pk).update(...)`.

- [x] **C3: Stored Cross-Site Scripting (XSS) via unescaped `custom_css` in Preview template** — fixed in `df12e729`, `666eff5c` (added clean_custom_css rejecting script/style tags and applied striptags filter in preview template)
  - **Location**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:32` & `apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:39`
  - **Issue**: `{{ config.custom_css|safe }}` is rendered raw inside `<style>...</style>`. An attacker saving `</style><script>alert(1)</script>` into `custom_css` executes arbitrary JavaScript in viewer sessions.
  - **Fix**: In `EmbeddedAnalyticsConfigForm.clean_custom_css()`, reject or strip `</style>` and `<script>` tags, and sanitize custom CSS before rendering.

- [x] **C4: Lesson L10 violation — Detail pages crash (HTTP 500) when `created_by` is `None`** — fixed in `80a37063`, `2af20c88`, `28037d19`, `1e066095` (safely guarded created_by against None in all 4 detail templates per Lesson L10)
  - **Location**: `templates/bi/embedded_mobile_bi/embedapitoken/detail.html:211`, `embeddedanalyticsconfig/detail.html:278`, `kioskwallboarddisplay/detail.html:200`, `mobilebiconfiguration/detail.html:259`
  - **Issue**: All 4 detail templates evaluate `{{ obj.created_by.get_full_name|default:obj.created_by.username|default:"System" }}`. When `created_by` is `None`, evaluating `obj.created_by.username` in the filter argument raises `VariableDoesNotExist` and HTTP 500.
  - **Fix**: Replace with `{% if obj.created_by %}{{ obj.created_by.get_full_name|default:obj.created_by.username }}{% else %}System{% endif %}`.

---

## Important

- [x] **I1: Script injection risk in Kiosk player via raw `{{ playlist_json|safe }}`** — fixed in `503e15a9` (serialized playlist items via json_script template tag and parsed in JS)
  - **Location**: `templates/bi/embedded_mobile_bi/kioskwallboarddisplay/player.html:151`
  - **Issue**: `const playlist = {{ playlist_json|safe }};` executes raw JSON interpolation inside `<script>`. If a slide title contains `</script>`, it terminates the script block prematurely.
  - **Fix**: Use Django's `{{ playlist_items|json_script:"kiosk-playlist-data" }}` template tag and parse with `JSON.parse(...)`.

- [x] **I2: Non-existent `badge-purple` CSS class used (violates `theme.css` + Lesson L33)** — fixed in `4cc9410e`, `ef74a448` (replaced non-existent badge-purple with valid badge classes in list and detail templates)
  - **Location**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/list.html:175` & `templates/bi/embedded_mobile_bi/mobilebiconfiguration/detail.html:232`
  - **Issue**: In `theme.css`, badges are strictly `.badge-green/red/amber/info/muted/slate`. `.badge-purple` does not exist, causing elements to render unstyled.
  - **Fix**: Replace `badge-purple` with `badge-info` or `badge-slate`.

- [x] **I3: Missing package `__init__.py` re-exports in models and forms subpackages** — fixed in `4e5d2076`, `10df8f4a` (re-exported all 4 models and 4 forms and defined __all__ in both subpackage __init__.py files)
  - **Location**: `apps/bi/models/EmbeddedMobileBi/__init__.py:1-2` & `apps/bi/forms/EmbeddedMobileBi/__init__.py:1-2`
  - **Issue**: Neither subpackage re-exports its members nor defines `__all__`. Imports such as `from apps.bi.models.EmbeddedMobileBi import EmbeddedAnalyticsConfig` fail.
  - **Fix**: Re-export all 4 models and 4 forms and declare `__all__` in both subpackage `__init__.py` files.

- [x] **I4: Superuser (`tenant=None`) and authenticated cross-tenant viewing broken in Kiosk Player view** — fixed in `8ae9b5d1` (supported superuser global access and cross-tenant public kiosk passcode viewing in player view)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:178-189`
  - **Issue**: Global staff/superusers with `tenant=None` fall into the unauthenticated branch which requires `is_public_kiosk=True`, returning 404 for private displays. Also, authenticated users from other tenants viewing a public kiosk via passcode are rejected by `bi_object`.
  - **Fix**: Allow `request.user.is_superuser` to view any display; fall back to passcode check if public kiosk.

- [x] **I5: Non-atomic in-memory view count increment causes lost updates under concurrency** — fixed in `ec5c924e` (used F('view_count') + 1 for atomic in-database increment in preview view)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:217-220`
  - **Issue**: `view_count=config.view_count + 1` performs a read-modify-write in Python.
  - **Fix**: Use `F('view_count') + 1` in `EmbeddedAnalyticsConfig.objects.filter(pk=config.pk).update(...)`.

- [x] **I6: Chained N+1 query hazard in `MobileBiConfiguration.__str__` (Lesson L18)** — fixed in `27b3bf8c` (guarded foreign key dereferencing against N+1 queries by checking _state.fields_cache in MobileBiConfiguration.__str__)
  - **Location**: `apps/bi/models/EmbeddedMobileBi/MobileBiConfigurations.py:123-125`
  - **Issue**: `__str__` accesses `self.target_user.username`, triggering extra SQL queries when evaluated in string contexts without `select_related('target_user')`.
  - **Fix**: Avoid dereferencing ForeignKey if not cached in `_state.fields_cache`.

- [x] **I7: Missing database indexes on tenant-filtered columns** — fixed in `fb3fd4bb`, `bec2e804`, `5d752f8a` (added composite indexes on [tenant, display_schedule], [tenant, touch_layout_preset], and [tenant, push_digest_frequency], migrated in 0037)
  - **Location**: `apps/bi/models/EmbeddedMobileBi/KioskWallboardDisplays.py:108-113` & `MobileBiConfigurations.py:116-121`
  - **Issue**: Prominent UI filters on `display_schedule`, `touch_layout_preset`, and `push_digest_frequency` lack composite database indexes with `tenant`.
  - **Fix**: Add composite indexes in model `Meta.indexes`.

---

## Minor

- [x] **M1: Form FK dropdown querysets load large JSON blobs without `.only()`** — fixed in `13067328` (deferred unneeded fields via only() on dashboard, report, and semantic_model querysets in form)
  - **Location**: `apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:64-66`
  - **Fix**: Add `.only('id', 'title', 'number')` / `.only('id', 'name', 'number')`.

- [x] **M2: Unprojected querysets for pinned dashboard/report previews in detail view** — fixed in `38a12c2c` (projected pinned dashboard and report querysets with only() in detail view)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/MobileBiConfigurations.py:123-124`
  - **Fix**: Add `.only('id', 'title', 'number')` / `.only('id', 'name', 'number')`.

- [x] **M3: Stale timestamp returned in JsonResponse from `kiosk_wallboard_display_heartbeat`** — fixed in `cd70db35` (returned generated now.isoformat() directly in heartbeat JsonResponse)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:232`
  - **Fix**: Pass generated `now.isoformat()` directly.

- [x] **M4: Slug generation query excludes `pk=self.pk` when `self.pk is None`** — fixed in `fee56b09`, `6c846648` (guarded exclude(pk=self.pk) with if self.pk in slug generator)
  - **Location**: `apps/bi/models/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:126` & `KioskWallboardDisplays.py:123`
  - **Fix**: Guard exclusion with `if self.pk: qs = qs.exclude(pk=self.pk)`.

- [x] **M5: Public CDN dependencies in standalone preview and player templates** — fixed in `d9011054`, `ed307ddf` (added documentation notes on outbound CDN connectivity requirements in preview and player templates)
  - **Location**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:8` & `kioskwallboarddisplay/player.html:8`
  - **Fix**: Note external connectivity requirement or reference local vendor static assets.

- [x] **M6: Default mobile profile uniqueness enforced only in view** — fixed in `d9bf8509` (enforced tenant default profile uniqueness in MobileBiConfiguration.save())
  - **Location**: `apps/bi/views/EmbeddedMobileBi/MobileBiConfigurations.py:88-91`
  - **Fix**: Enforce single-default profile reset logic in `MobileBiConfiguration.save()`.

- [x] **M7: Unvalidated hex color inputs in form** — fixed in `bba4b9a6` (validated hex color format in clean_primary_color and clean_accent_color)
  - **Location**: `apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:55-56`
  - **Fix**: Add hex regex validator `^#[0-9a-fA-F]{6}$` in `clean_primary_color()` and `clean_accent_color()`.

- [x] **M8: Timing attack vulnerability in kiosk passcode comparison** — fixed in `8ae9b5d1` (used secrets.compare_digest for constant-time kiosk passcode verification)
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:182`
  - **Fix**: Use `secrets.compare_digest(display.access_passcode, passcode)`.

- [x] **M9: Form-level validation for pinned dashboard/report IDs** — fixed in `32ebd487` (validated tenant ownership of pinned dashboard and report IDs in MobileBiConfigurationForm.clean())
  - **Location**: `apps/bi/forms/EmbeddedMobileBi/MobileBiConfigurations.py:88-113`
  - **Fix**: Verify pinned IDs belong to `self.tenant` in form `clean()`.
