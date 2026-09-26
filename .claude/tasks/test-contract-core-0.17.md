# Test contract — 0.17 Monitoring, Logging & Observability

**Subslug:** `monitoring` · **App:** `core` · **Phase:** 6 · **BASE:** `320670bb`
**Lanes:** `test_monitoring_models.py` → `_forms.py` → `_views.py` → `_security.py`, one at a time.

Every test function is named `test_monitoring_*` and every module-level helper `_monitoring_*`, so the
next sub-module appending nearby cannot shadow them (the house naming rule).

---

## 1. Fixtures the conftest block adds (append-only — L43)

All names are prefixed `mon_` (not `monitoring_`) so they cannot collide with the 0.15
`localization_*` or 0.16 `bkp_*` blocks already in `apps/core/tests/conftest.py`. **Nothing above the
append point is rewritten.**

| fixture | what it returns |
|---|---|
| `_monitoring_svc` (factory) | a `ServiceComponent` for `tenant_a` with a unique `code` per call |
| `mon_service_ok_a` | a component, `current_status="operational"`, `last_status_at` stamped |
| `mon_service_unreported_a` | a component with `last_status_at = None` (never claimed) |
| `mon_service_retired_a` | a component with `is_active=False` |
| `mon_rule_one_tier_a` | a `gte` rule, `warning_threshold` only |
| `mon_rule_two_tier_a` | a `gte` rule, warning 800 / critical 1500 — correctly ordered |
| `mon_rule_floor_a` | an `lt` rule on `uptime_pct`, critical only |
| `mon_rule_inactive_a` | an inactive rule, for the `?active=` filter |
| `mon_event_firing_a` | an `AlertEvent`, state `firing`, `rule` + `service` set |
| `mon_event_ack_a` | an `acknowledged` event (also open) |
| `mon_event_resolved_a` | a `resolved` event (NOT open) |
| `mon_event_no_data_a` | a `no_data` event — the state the badge ladder missed |
| `mon_event_unmeasured_a` | a firing with `observed_value = None` |
| `mon_event_orphan_a` | a firing with `rule_id = None` (rule retired) |
| `mon_event_b` | the same in `tenant_b`, for the cross-tenant lane |
| `mon_incident_open_a` | an `Incident`, `status="investigating"` |
| `mon_incident_resolved_a` | a `Incident`, `status="resolved"` |
| `mon_incident_maintenance_a` | a `scheduled_maintenance` notice (the `is_scheduled` shape) |
| `mon_incident_b` | the same in `tenant_b` |
| `mon_component_payload` | valid `ServiceComponentForm` POST fields |
| `mon_rule_payload` | valid `AlertRuleForm` POST fields |

Reuses the pre-existing `tenant_a`, `tenant_b`, `client_a`, `client_b` fixtures. **Confirm their exact
names in `apps/core/tests/conftest.py` before use** — read the top of the file rather than assuming.

---

## 2. The model lane


## 3. The form lane

- **L22: zero editable `DateTimeField`s.** Assert `fired_at`, `first_seen_at`, `last_seen_at`,
  `acknowledged_at`, `resolved_at`, `last_status_at`, `notified_at`, `created_at` are **absent from
  every** `Meta.fields` — by inspecting the constructed form, not by reading the source.
- **Tenant escape (the security-critical one):** `TenantModelForm` narrows the choice querysets.
  Assert a `tenant_b` pk is rejected for `AlertRule.service`, `AlertEvent.rule` and
  `Incident.affected_services`, and that the same field with a `tenant_a` pk validates. This is the
  check that would catch a regression in `forms/_common.py`.
- `ServiceComponentForm.save()` stamps `last_status_at` **only when `current_status` changes**.
- `AlertEventForm.save()` writes `service_label` **only when a service is chosen** — clearing the
  service must NOT erase the snapshot (the I1 fix).
- An `lt` rule with both tiers set is a form error; a `gte` rule with a reversed pair is a form error.

## 4. The view lane — the context contract (L7/L8)

Assert the **pinned keys exist** on `response.context`, because a renamed key is the blank-page bug
and the qa pass found five such drifts:

- `service_component_list` → `kind_choices`, `status_choices`, `owner_roles`, `unreported_count`, `notes`
- `alert_rule_list` → `category_choices`, `severity_choices`, `metric_choices`, `no_data_choices`,
  `services`, `notes`
- `alert_event_list` → `state_choices`, `severity_choices`, `rules`, `services`, **`event_totals`**
  (a dict with `firing`/`open`/`total`/`unmeasured`)
- `incident_list` → `status_choices`, **`type_choices`**, `impact_choices`, **`open_count`**,
  `active_count`, `notes`
- `monitoring_overview` → **`component_total`**, **`rule_total`**, `retired_component_count`, `notes`
- `health_board` → `components`, `latest_metrics`, `status_rows`, `rollup_status`, `retired_count`,
  `notes` — and every `status_rows` entry is a **3-tuple** `(label, count, value)`
- `firing_board` → `open_events`, `open_count`, `open_total`, `state_rows`, `severity_rows`, `rule_total`
- `capacity_board` → `usage_rows`, `capacity_rules`, `rule_count`, `over_threshold_count`

Also assert: every list returns 200 and **renders a seeded name**; `?q=`, page 2 and page 99999 return
200; a junk enum value is **ignored** (the register is not emptied — `crud_list`'s `_enum_values`
guard); each delete is **405 on GET**; the four POST-only actions change state and are idempotent;
`capacity_board` computes the **right sign** for an `lt` rule and prints the comparator.

## 5. The security lane

- Cross-tenant: tenant B gets **404** on the detail, edit, delete and each POST-only action of all four
  entities, and sees none of tenant A's rows in any list or board.
- A tenant member (non-admin) gets **403** on all 28 routes; anonymous is **redirected**, not 200.
- A crafted POST carrying `tenant` / `is_active` / a system stamp does not change them.
- `resolution_note` longer than 255 is truncated server-side, not only by the widget's `maxlength`.
- Every one of the 28 routes carries `@tenant_admin_required`; exactly 8 are `@require_POST`.

---

## 6. The four lanes are written one file at a time, and each is committed on its own. Then the
**full unfiltered** `apps/core` suite is run and fixed green — never `-k` filtered, because a filter
excludes exactly the tests a shared-file change can break (L47). Note that `apps/sales` is being
built concurrently by another session; failures there are **not** ours and are reported with
provenance rather than "fixed" (L45).

- `ServiceComponent.STATUS_CHOICES` **5** values; `AlertEvent.STATE_CHOICES` **5**;
  `AlertEvent.SEVERITY_CHOICES` **3**; `AlertRule.CATEGORY_CHOICES` **5**;
  `Incident.STATUS_CHOICES` **8**; `Incident.IMPACT_CHOICES` **4**; incident type **3**.
- `AlertRule.COMPARATORS is BusinessRule.OPERATORS` and
  `AlertRule.FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES` — **reuse by reference**. Assert
  identity with `is`, because a copy would silently drift.
- **`clean()` (the I4 fix):** an active rule with no bound is refused; a `gte` rule with
  `critical <= warning` is refused; an `lt` rule with `critical >= warning` is refused; **both** tiers
  on a non-ordering comparator is refused; the correct orderings are accepted.
- `AlertEvent.is_open` is `firing`/`acknowledged`; `Incident.is_open` excludes `resolved`/`completed` —
  **two different definitions on purpose**, and the incident list depends on the difference.
- `AlertEvent.rule` is **SET_NULL**: deleting a rule leaves its firings with `rule_id = None`.
- `Incident.affected_services` is a real M2M.
