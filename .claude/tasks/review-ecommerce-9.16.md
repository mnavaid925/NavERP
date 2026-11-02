# Review Findings — eCommerce 9.16: Mobile Commerce

Base ref: `02c99bcf04e351e26395967561520c6e63998a7a`
Head: `HEAD`

---

## Executive Summary
Six specialized reviewers (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) conducted an in-depth review of Sub-module 9.16 Mobile Commerce across models, forms, views, URLs, navigation, seeder, and 13 templates. Runtime smoke testing verified 51/51 checks (100% pass rate) with zero 500 crashes and solid multi-tenant isolation. The findings below (C1–C2, I1–I10, M1–M7) have been identified, deduplicated, and prioritized for resolution by the `code-fixer` agent in Phase 5.

---

## Critical Findings

- [ ] **C1** — **Chained N+1 queries in `mobiledeviceregistration_list` on `customer_profile__user` and `customer_profile__customer`**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobileDeviceRegistrations.py:18-21` and `templates/ecommerce/mobile/mobile_device_registration/list.html:164-166`
  - *Problem*: In `list.html`, `{{ dev.customer_profile.user.email... }}` and `{{ dev.customer_profile.customer.name }}` dereference unjoined models on every row of the 15-row list.
  - *Fix*: Add `.select_related("customer_profile__user", "customer_profile__customer", "party")` to `mobiledeviceregistration_list`.

- [ ] **C2** — **Chained N+1 queries in `MobileDeviceRegistrationForm` customer profile dropdown (`CustomerAccountProfile.__str__`)**
  - *Location*: `apps/ecommerce/forms/MobileCommerce/MobileDeviceRegistrations.py:31`
  - *Problem*: In `MobileDeviceRegistrationForm.__init__`, `CustomerAccountProfile` dropdown evaluates `str(profile)` which touches `self.customer` (`core.Party`), causing $1 + N$ queries.
  - *Fix*: Add `.select_related("customer")` to `customer_profile` queryset in `MobileDeviceRegistrationForm.__init__`.

---

## Important Findings

- [ ] **I1** — **Unvalidated numeric input & unhandled `InvalidOperation` exception in `mobiledeviceregistration_ping` (L35)**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobileDeviceRegistrations.py:171-182`
  - *Problem*: Hand-parsed coordinates with raw `float(lat)`/`float(lng)` without `math.isfinite()` or geographic range constraints (`[-90.0, 90.0]`, `[-180.0, 180.0]`) cause `device.record_activity()` to fail with unhandled `InvalidOperation` or DB column overflow on NaN/Inf/large values.
  - *Fix*: Check `math.isfinite()` and clamp valid ranges (`-90.0 <= lat <= 90.0`, `-180.0 <= lng <= 180.0`).

- [ ] **I2** — **Coordinates parsing and math domain error in `mobilelocationrule_simulate` & `MobileLocationRule.distance_to` (L35)**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobileLocationRules.py:170-176` and `apps/ecommerce/models/MobileCommerce/MobileLocationRules.py:127-130`
  - *Problem*: `mobilelocationrule_simulate` parses `test_lat` and `test_lng` with raw `float()` without checking `math.isfinite()`. In `MobileLocationRule.distance_to()`, calculating `c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))` fails with `ValueError: math domain error` if floating-point inaccuracy or out-of-range coords causes `a > 1.0`.
  - *Fix*: In `distance_to`, clamp `a` to `[0.0, 1.0]` and clamp `1 - a` to `>= 0.0`. In `mobilelocationrule_simulate`, validate `math.isfinite()` and bounds `[-90.0, 90.0]` / `[-180.0, 180.0]`.

- [ ] **I3** — **Missing view-level status guard in `mobilepushcampaign_test_send`**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobilePushCampaigns.py:170-184`
  - *Problem*: A cancelled campaign can be dispatched via direct POST, mutating its status to `sent` and incrementing metrics.
  - *Fix*: Add a status guard `if campaign.status == "cancelled":` with error message and redirect.

- [ ] **I4** — **Mass assignment of workflow-controlled `status` in `MobilePushCampaignForm`**
  - *Location*: `apps/ecommerce/forms/MobileCommerce/MobilePushCampaigns.py:13-25, 40`
  - *Problem*: `status` is not in `Meta.exclude` and is rendered as an editable `<select>` input, allowing arbitrary modification of campaign lifecycle states.
  - *Fix*: Add `"status"` to `Meta.exclude` in `MobilePushCampaignForm`.

- [ ] **I5** — **CSS/Style Injection via unconstrained color inputs in `MobileAppConfig` (L26)**
  - *Location*: `apps/ecommerce/models/MobileCommerce/MobileAppConfigs.py:44-53`, `apps/ecommerce/forms/MobileCommerce/MobileAppConfigs.py:31-41`
  - *Problem*: `theme_color` and `background_color` lack model-level `RegexValidator(r"^#[0-9A-Fa-f]{6}$")` and are rendered directly into inline `style="background-color: {{ config.theme_color }};"`.
  - *Fix*: Add `RegexValidator(r"^#[0-9A-Fa-f]{6}$")` to model fields and validate hex in form `clean()`.

- [ ] **I6** — **Push token exposed as editable text input in `MobileDeviceRegistrationForm` (L20)**
  - *Location*: `apps/ecommerce/forms/MobileCommerce/MobileDeviceRegistrations.py:12, 21`
  - *Problem*: `push_token` is included as an editable field in `MobileDeviceRegistrationForm`, risking notification hijacking or credential overwriting.
  - *Fix*: Add `"push_token"` to `Meta.exclude` in `MobileDeviceRegistrationForm`.

- [ ] **I7** — **Unconsolidated KPI aggregates in `MobileHub.py`**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobileHub.py:19-35`
  - *Problem*: Device stats execute 4 separate COUNT queries and push campaign stats execute 2 separate queries.
  - *Fix*: Consolidate device counts into a single conditional aggregate and push campaign stats into a single aggregate.

- [ ] **I8** — **Missing composite indexes on `MobileDeviceRegistration`**
  - *Location*: `apps/ecommerce/models/MobileCommerce/MobileDeviceRegistrations.py:138-142`
  - *Problem*: High-volume telemetry table lacks composite indexes on `(tenant, -last_active_at)` (for default ordering and cockpit query) and `(tenant, is_active, push_enabled)` (for push broadcast dispatch).
  - *Fix*: Add indexes `models.Index(fields=["tenant", "-last_active_at"], name="idx_emdr_ten_last_act")` and `models.Index(fields=["tenant", "is_active", "push_enabled"], name="idx_emdr_ten_push_act")` with migration.

- [ ] **I9** — **Hardcoded fallbacks and missing status handlers in status/type badge `{% else %}` branches (L33)**
  - *Location*:
    - `templates/ecommerce/mobile/mobile_push_campaign/list.html:163-174`, `detail.html:22-32`, `mobile_hub.html:178-184`
    - `templates/ecommerce/mobile/mobile_location_rule/list.html:144-155`
    - `templates/ecommerce/mobile/mobile_device_registration/list.html:152-158`, `detail.html:22-28`, `mobile_hub.html:275-281`
  - *Problem*: Badges in `mobile_push_campaign` and `mobile_hub` fall through to hardcoded "Draft" instead of `{{ camp.get_status_display }}`; `sending` and `cancelled` statuses were omitted in `mobile_hub.html`; `rule_type` badge put `curbside_pickup` in `{% else %}` without testing explicitly; platform badge omitted `pwa_web` check.
  - *Fix*: Explicitly check each choice value and provide `{{ obj.get_FIELD_display }}` in the `{% else %}` branch.

- [ ] **I10** — **Missing label associations in Location Rule simulator form (WCAG A11y)**
  - *Location*: `templates/ecommerce/mobile/mobile_location_rule/detail.html:167-174`
  - *Problem*: Simulator inputs lack `id` attributes and labels lack `for` attributes.
  - *Fix*: Add matching `id` and `for` attributes (`sim-test-lat`, `sim-test-lng`).

---

## Minor Findings

- [ ] **M1** — **Public PWA manifest serves configuration even when PWA is disabled**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobileAppConfigs.py:157`
  - *Problem*: `pwa_manifest_json` filters only on `is_active=True` without checking `enable_pwa=True`.
  - *Fix*: Filter `MobileAppConfig.objects.filter(tenant=tenant, is_active=True, enable_pwa=True).first()`.

- [ ] **M2** — **Detail templates lack explicit secondary Back button in header action bar**
  - *Location*:
    - `templates/ecommerce/mobile/mobile_app_config/detail.html:34`
    - `templates/ecommerce/mobile/mobile_device_registration/detail.html:38`
    - `templates/ecommerce/mobile/mobile_push_campaign/detail.html:38`
    - `templates/ecommerce/mobile/mobile_location_rule/detail.html:33`
  - *Problem*: Back navigation is only present via breadcrumbs.
  - *Fix*: Add explicit secondary Back button pointing to the entity list view.

- [ ] **M3** — **Missing `aria-label` attributes on icon-only buttons (`.btn-icon`)**
  - *Location*: List templates actions column (`mobile_app_config`, `mobile_device_registration`, `mobile_push_campaign`, `mobile_location_rule`, `mobile_hub`).
  - *Problem*: Interactive controls carry `title` but lack `aria-label`.
  - *Fix*: Add matching `aria-label` to each `.btn-icon` element.

- [ ] **M4** — **Redundant SQL joins on unrendered related models in list and hub queries**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobilePushCampaigns.py:20` and `MobileHub.py:41`
  - *Problem*: `select_related` joins models not rendered in the template.
  - *Fix*: Prune unused foreign keys from `select_related`.

- [ ] **M5** — **Unconsolidated count queries in list view header stat cards**
  - *Location*: `MobileDeviceRegistrations.py:47-51`, `MobileAppConfigs.py:41-43`, `MobilePushCampaigns.py:44-48`, `MobileLocationRules.py:45-48`
  - *Problem*: Multiple individual `COUNT(*)` queries fired before pagination.
  - *Fix*: Consolidate into single `aggregate(Count(...), ...)` calls.

- [ ] **M6** — **Empty-state action buttons lack Lucide plus icon**
  - *Location*: List templates empty states.
  - *Problem*: Empty-state buttons lack `<i data-lucide="plus" ...>`.
  - *Fix*: Add `<i data-lucide="plus" class="w-4 h-4 mr-1.5 inline"></i>`.

- [ ] **M7** — **Location rule simulator default test coordinates**
  - *Location*: `apps/ecommerce/views/MobileCommerce/MobileLocationRules.py:165`
  - *Problem*: Defaulting to rule center coordinates when POST inputs are blank causes instant 0m inside match.
  - *Fix*: Reject blank simulation inputs with an informational flash message instead of auto-matching.
