# Review Findings: Sub-module 10.17 Embedded & Mobile BI

Base commit: `a3d989bc06eda3b74ce2a67a70785992ec94fca0`
Target changeset: `a3d989bc06eda3b74ce2a67a70785992ec94fca0..HEAD`

---

## Pass 1: Code Reviewer Findings

### Critical
- **C1 (code-reviewer)**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:214-234` — Unauthenticated cross-tenant telemetry poisoning and IDOR on Kiosk Heartbeat endpoint. `kiosk_wallboard_display_heartbeat` lacks auth/tenant scoping/passcode checks. Fix: require `@require_POST`, check authentication and tenant or require `access_passcode`/token.
- **C2 (code-reviewer)**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:32` — Stored Cross-Site Scripting (XSS) via unescaped `custom_css` in Preview template. `{{ config.custom_css|safe }}` renders unescaped in `<style>`. Fix: strip/reject `</style>` and `<script>` in form clean or sanitize.

### Important
- **I1 (code-reviewer)**: `templates/bi/embedded_mobile_bi/kioskwallboarddisplay/player.html:151` — Script injection risk in Kiosk player via raw `{{ playlist_json|safe }}`. Fix: Use Django's `json_script` tag.
- **I2 (code-reviewer)**: `apps/bi/views/EmbeddedMobileBi/KioskWallboardDisplays.py:178-189` — Superuser (`tenant=None`) and authenticated cross-tenant viewing broken in Kiosk Player view. Fix: Allow superuser or fall back to passcode check.
- **I3 (code-reviewer)**: `templates/bi/embedded_mobile_bi/embedapitoken/detail.html:211`, `embeddedanalyticsconfig/detail.html:278`, `kioskwallboarddisplay/detail.html:200`, `mobilebiconfiguration/detail.html:259` — Lesson L10 violation: unguarded `default:obj.created_by.username` in filter argument crashes when `created_by=None`. Fix: Guard with `{% if obj.created_by %}`.
- **I4 (code-reviewer)**: `apps/bi/models/EmbeddedMobileBi/__init__.py:1-2` and `apps/bi/forms/EmbeddedMobileBi/__init__.py:1-2` — Missing re-exports and `__all__` in subpackage `__init__.py`. Fix: Re-export models and forms in subpackage `__init__.py`.

### Minor
- **M1 (code-reviewer)**: `apps/bi/views/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:217-220` — Race condition on view counter increment. Fix: Use `F('view_count') + 1`.
- **M2 (code-reviewer)**: `apps/bi/models/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py:126`, `KioskWallboardDisplays.py:123` — Slug generation query excludes `pk=self.pk` when `self.pk` is None. Fix: Guard `if self.pk: qs = qs.exclude(pk=self.pk)`.
- **M3 (code-reviewer)**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:8`, `kioskwallboarddisplay/player.html:8` — Public CDN dependencies in standalone templates.
- **M4 (code-reviewer)**: `apps/bi/views/EmbeddedMobileBi/MobileBiConfigurations.py:88-91` — Default mobile profile uniqueness enforced only in view. Fix: Enforce in `save()` or `clean()`.

---

## Pass 2: Explorer Contract Reviewer Findings

### Critical
- **C1 (explorer)**: `apps/bi/views/EmbeddedMobileBi/*.py` (13 call sites across all 4 view files) — Inverted `write_audit_log` call signatures. Views pass `(request, instance=..., action=..., description=...)` but `write_audit_log` expects `(user, obj, action, changes=None, tenant=None)`. Triggers `TypeError: write_audit_log() got an unexpected keyword argument 'instance'` on every POST mutation. Fix: Change to `write_audit_log(request.user, obj, action, tenant=request.tenant)`.
- **C2 (explorer)**: Corroborated C1 from code-reviewer (`kiosk_wallboard_display_heartbeat` unauthenticated IDOR/tampering).
- **C3 (explorer)**: Corroborated C2 from code-reviewer (stored XSS via unescaped `custom_css`).

### Important
- **I1 (explorer)**: Corroborated I4 from code-reviewer (missing models and forms subpackage re-exports in `apps/bi/*/EmbeddedMobileBi/__init__.py`).
- **I2 (explorer)**: Corroborated I1 from code-reviewer (raw `playlist_json|safe` script injection).
- **I3 (explorer)**: Corroborated I3 from code-reviewer (Lesson L10 `obj.created_by.username` in filter argument).
- **I4 (explorer)**: Corroborated I2 from code-reviewer (kiosk player superuser/public passcode logic).

### Contract Summary
- 100% compliance on URLs, routes, context variables, template paths, models, fields, choices, migrations, and navigation.

---

## Pass 3: Frontend Reviewer Findings

### Critical
- **C1 (frontend-reviewer)**: Corroborated C2 from code-reviewer / C3 from explorer (`preview.html:32` stored XSS via unescaped `custom_css`).

### Important
- **I1 (frontend-reviewer)**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/list.html:175` and `templates/bi/embedded_mobile_bi/mobilebiconfiguration/detail.html:232` — Non-existent `badge-purple` CSS class used (violates `theme.css` + Lesson L33). `badge-purple` does not exist in `theme.css` (only `badge-green/red/amber/info/muted/slate`). Fix: Replace with `badge-info` or `badge-slate`.
- **I2 (frontend-reviewer)**: Corroborated I3 from code-reviewer / I3 from explorer (Lesson L10 `obj.created_by.username` in filter argument crashes when `created_by=None` in all 4 detail templates).
- **I3 (frontend-reviewer)**: Corroborated I1 from code-reviewer / I2 from explorer (`player.html:151` raw `playlist_json|safe` script injection). Fix: Use Django `json_script`.

### Minor
- **M1 (frontend-reviewer)**: Corroborated M3 from code-reviewer / M3 from explorer (CDN dependencies in standalone preview and player templates).
- **M2 (frontend-reviewer)**: `templates/bi/embedded_mobile_bi/embedapitoken/detail.html:59,89,104` and `embeddedanalyticsconfig/detail.html:90,105,120` — Clipboard copy handlers lack Promise rejection handling. Fix: Use `.then().catch()`.
- **M3 (frontend-reviewer)**: `templates/bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html:15` — `primary_color` and `accent_color` injected into style/script without regex validation in form. Fix: Add hex regex validator `^#[0-9a-fA-F]{6}$` in form clean.


