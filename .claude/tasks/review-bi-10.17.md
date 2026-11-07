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

- [ ] **C1: Inverted `write_audit_log` call signatures cause 100% POST mutations (create, edit, delete, revoke) to fail with TypeError / HTTP 500**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/*.py` (13 call sites: `EmbeddedAnalyticsConfigs.py:90, 172, 196`; `KioskWallboardDisplays.py:89, 141, 165`; `MobileBiConfigurations.py:93, 152, 176`; `EmbedApiTokens.py:78, 159, 183, 202`)
  - **Issue**: Views call `write_audit_log(request, action=..., instance=..., description=...)`, but `apps/core/utils.py` defines `write_audit_log(user, obj, action, changes=None, tenant=None)`. This triggers `TypeError: write_audit_log() got an unexpected keyword argument 'instance'` and crashes with HTTP 500 on every single create/edit/delete/revoke POST request.
  - **Fix**: Update all 13 call sites to `write_audit_log(request.user, obj, action, tenant=request.tenant)`.

- [ ] **C2: Unauthenticated cross-tenant telemetry poisoning, device spoofing, and IDOR on Kiosk Heartbeat endpoint**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:214-234`
  - **Issue**: `kiosk_wallboard_display_heartbeat` lacks `@require_POST`, `@login_required`, tenant scoping, and passcode checks. Any external client can query arbitrary PKs across all tenants, which discloses `display.number` and overwrites `last_heartbeat_at`, `device_ip_address`, and `device_user_agent`.
  - **Fix**: Apply `@require_POST`. If caller is authenticated, enforce tenant scoping; if unauthenticated, verify `access_passcode` matching the display via `secrets.compare_digest`. Collapse query into a single atomic `.filter(pk=pk).update(...)`.

- [ ] **C3: Stored Cross-Site Scripting (XSS) via unescaped `custom_css` in Preview template**
  - **Location**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:32` & `apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:39`
  - **Issue**: `{{ config.custom_css|safe }}` is rendered raw inside `<style>...</style>`. An attacker saving `</style><script>alert(1)</script>` into `custom_css` executes arbitrary JavaScript in viewer sessions.
  - **Fix**: In `EmbeddedAnalyticsConfigForm.clean_custom_css()`, reject or strip `</style>` and `<script>` tags, and sanitize custom CSS before rendering.

- [ ] **C4: Lesson L10 violation — Detail pages crash (HTTP 500) when `created_by` is `None`**
  - **Location**: `templates/bi/embedded_mobile_bi/embedapitoken/detail.html:211`, `embeddedanalyticsconfig/detail.html:278`, `kioskwallboarddisplay/detail.html:200`, `mobilebiconfiguration/detail.html:259`
  - **Issue**: All 4 detail templates evaluate `{{ obj.created_by.get_full_name|default:obj.created_by.username|default:"System" }}`. When `created_by` is `None`, evaluating `obj.created_by.username` in the filter argument raises `VariableDoesNotExist` and HTTP 500.
  - **Fix**: Replace with `{% if obj.created_by %}{{ obj.created_by.get_full_name|default:obj.created_by.username }}{% else %}System{% endif %}`.

---

## Important

- [ ] **I1: Script injection risk in Kiosk player via raw `{{ playlist_json|safe }}`**
  - **Location**: `templates/bi/embedded_mobile_bi/kioskwallboarddisplay/player.html:151`
  - **Issue**: `const playlist = {{ playlist_json|safe }};` executes raw JSON interpolation inside `<script>`. If a slide title contains `</script>`, it terminates the script block prematurely.
  - **Fix**: Use Django's `{{ playlist_items|json_script:"kiosk-playlist-data" }}` template tag and parse with `JSON.parse(...)`.

- [ ] **I2: Non-existent `badge-purple` CSS class used (violates `theme.css` + Lesson L33)**
  - **Location**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/list.html:175` & `templates/bi/embedded_mobile_bi/mobilebiconfiguration/detail.html:232`
  - **Issue**: In `theme.css`, badges are strictly `.badge-green/red/amber/info/muted/slate`. `.badge-purple` does not exist, causing elements to render unstyled.
  - **Fix**: Replace `badge-purple` with `badge-info` or `badge-slate`.

- [ ] **I3: Missing package `__init__.py` re-exports in models and forms subpackages**
  - **Location**: `apps/bi/models/EmbeddedMobileBi/__init__.py:1-2` & `apps/bi/forms/EmbeddedMobileBi/__init__.py:1-2`
  - **Issue**: Neither subpackage re-exports its members nor defines `__all__`. Imports such as `from apps.bi.models.EmbeddedMobileBi import EmbeddedAnalyticsConfig` fail.
  - **Fix**: Re-export all 4 models and 4 forms and declare `__all__` in both subpackage `__init__.py` files.

- [ ] **I4: Superuser (`tenant=None`) and authenticated cross-tenant viewing broken in Kiosk Player view**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:178-189`
  - **Issue**: Global staff/superusers with `tenant=None` fall into the unauthenticated branch which requires `is_public_kiosk=True`, returning 404 for private displays. Also, authenticated users from other tenants viewing a public kiosk via passcode are rejected by `bi_object`.
  - **Fix**: Allow `request.user.is_superuser` to view any display; fall back to passcode check if public kiosk.

- [ ] **I5: Non-atomic in-memory view count increment causes lost updates under concurrency**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:217-220`
  - **Issue**: `view_count=config.view_count + 1` performs a read-modify-write in Python.
  - **Fix**: Use `F('view_count') + 1` in `EmbeddedAnalyticsConfig.objects.filter(pk=config.pk).update(...)`.

- [ ] **I6: Chained N+1 query hazard in `MobileBiConfiguration.__str__` (Lesson L18)**
  - **Location**: `apps/bi/models/EmbeddedMobileBi/MobileBiConfigurations.py:123-125`
  - **Issue**: `__str__` accesses `self.target_user.username`, triggering extra SQL queries when evaluated in string contexts without `select_related('target_user')`.
  - **Fix**: Avoid dereferencing ForeignKey if not cached in `_state.fields_cache`.

- [ ] **I7: Missing database indexes on tenant-filtered columns**
  - **Location**: `apps/bi/models/EmbeddedMobileBi/KioskWallboardDisplays.py:108-113` & `MobileBiConfigurations.py:116-121`
  - **Issue**: Prominent UI filters on `display_schedule`, `touch_layout_preset`, and `push_digest_frequency` lack composite database indexes with `tenant`.
  - **Fix**: Add composite indexes in model `Meta.indexes`.

---

## Minor

- [ ] **M1: Form FK dropdown querysets load large JSON blobs without `.only()`**
  - **Location**: `apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:64-66`
  - **Fix**: Add `.only('id', 'title', 'number')` / `.only('id', 'name', 'number')`.

- [ ] **M2: Unprojected querysets for pinned dashboard/report previews in detail view**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/MobileBiConfigurations.py:123-124`
  - **Fix**: Add `.only('id', 'title', 'number')` / `.only('id', 'name', 'number')`.

- [ ] **M3: Stale timestamp returned in JsonResponse from `kiosk_wallboard_display_heartbeat`**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:232`
  - **Fix**: Pass generated `now.isoformat()` directly.

- [ ] **M4: Slug generation query excludes `pk=self.pk` when `self.pk is None`**
  - **Location**: `apps/bi/models/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:126` & `KioskWallboardDisplays.py:123`
  - **Fix**: Guard exclusion with `if self.pk: qs = qs.exclude(pk=self.pk)`.

- [ ] **M5: Public CDN dependencies in standalone preview and player templates**
  - **Location**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:8` & `kioskwallboarddisplay/player.html:8`
  - **Fix**: Note external connectivity requirement or reference local vendor static assets.

- [ ] **M6: Default mobile profile uniqueness enforced only in view**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/MobileBiConfigurations.py:88-91`
  - **Fix**: Enforce single-default profile reset logic in `MobileBiConfiguration.save()`.

- [ ] **M7: Unvalidated hex color inputs in form**
  - **Location**: `apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:55-56`
  - **Fix**: Add hex regex validator `^#[0-9a-fA-F]{6}$` in `clean_primary_color()` and `clean_accent_color()`.

- [ ] **M8: Timing attack vulnerability in kiosk passcode comparison**
  - **Location**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:182`
  - **Fix**: Use `secrets.compare_digest(display.access_passcode, passcode)`.

- [ ] **M9: Form-level validation for pinned dashboard/report IDs**
  - **Location**: `apps/bi/forms/EmbeddedMobileBi/MobileBiConfigurations.py:88-113`
  - **Fix**: Verify pinned IDs belong to `self.tenant` in form `clean()`.
