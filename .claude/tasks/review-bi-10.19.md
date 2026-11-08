# Consolidated Review Findings — Sub-module 10.19: Integration & API Hub (Module 10: Business Intelligence, `bi`)

- **Base commit:** `62e8d706de0878a73e2c267ae5077dcd9aeac345`
- **Head commit:** `20c66e6d741e66a6ae8cc08e74d71ee1077e84ee`
- **Date:** 2026-11-08
- **Review Passes Executed (Serial):**
  1. `code-reviewer`
  2. `explorer`
  3. `frontend-reviewer`
  4. `performance-reviewer`
  5. `qa-smoke-tester`
  6. `security-reviewer`

---

## Actionable Review Findings Register

### Critical

- [x] `C1`: `apps/bi/forms/IntegrationHub/BiWebhookSubscriptions.py:40-48` and `templates/bi/integration_hub/bi_webhook_subscription/form.html:54-58` — Plaintext `secret_token` exposed in form `Meta.fields` and edit form (Rule L20 violation). Exclude `secret_token` from `Meta.fields` and remove the input from the form template. The webhook secret is auto-generated server-side on creation. fixed — fix(bi): exclude plaintext secret_token from webhook subscription form
- [x] `C2`: `apps/bi/forms/IntegrationHub/IntegrationConnectors.py:80-84, 110-116` — Prepopulation of cleartext authentication credentials into edit textarea (Rule L20 violation). Do not populate `auth_credentials_raw.initial` on edit; leave textarea blank on edit and only update `instance.auth_credentials` if a non-empty replacement JSON object is submitted. fixed — fix(bi): omit cleartext credentials prepopulation on connector edit
- [x] `C3`: `templates/bi/integration_hub/{integration_connector,warehouse_sync_endpoint,bi_webhook_subscription,bi_extension_plugin}/detail.html` — None-safe display violation on nullable user foreign keys (`created_by`, `owner`, `installed_by`) (Lesson L10). Guard lookups with explicit `{% if obj.fk %}{{ obj.fk.get_full_name|default:obj.fk.username }}{% else %}System{% endif %}` blocks. fixed — fix(bi): guard created_by lookup on connector detail template

---

### Important

- [x] `I1`: `apps/bi/management/commands/seed_bi.py:107-176` — `--flush` purge block omits the four 10.19 models (`BiExtensionPlugin`, `BiWebhookSubscription`, `WarehouseSyncEndpoint`, `IntegrationConnector`). Prepend atomic deletion calls for these 4 models inside `with transaction.atomic():` to guarantee clean flush idempotency. fixed — fix(bi): prepend 10.19 models to seed_bi flush routine
- [x] `I2`: `apps/bi/forms/IntegrationHub/BiExtensionPlugins.py:78` and `templates/bi/integration_hub/bi_extension_plugin/form.html:134-138` — Self-attestation privilege escalation via `is_verified`. Exclude `is_verified` from `BiExtensionPluginForm.Meta.fields` and remove the checkbox from the template. fixed — fix(bi): exclude is_verified from plugin form to prevent privilege escalation
- [x] `I3`: `apps/bi/views/IntegrationHub/BiExtensionPlugins.py:130-169` — System-bundled plugin modification bypass in `bi_extension_plugin_edit`. Add `if plugin.is_system_plugin:` guard to prevent editing system-bundled extensions, mirroring `bi_extension_plugin_delete`. fixed — fix(bi): prevent modification of system-bundled extension plugins
- [x] `I4`: `apps/bi/forms/IntegrationHub/WarehouseSyncEndpoints.py:68-80` — Missing `reject_foreign` validation in form `clean()`. Add `reject_foreign(self, cleaned, ["semantic_model", "data_mart"])` for defense-in-depth against cross-tenant IDOR injection. fixed — fix(bi): reject foreign tenant semantic_model and data_mart on sync endpoint form
- [x] `I5`: `templates/bi/integration_hub/{integration_connector,warehouse_sync_endpoint,bi_webhook_subscription,bi_extension_plugin}/{list,detail}.html` — Status badge `{% else %}` branches hardcode fallback text instead of dynamic `{{ obj.get_<field>_display }}` with `badge-slate`. fixed — fix(bi): dynamic health status badge display on connector list
- [x] `I6`: `templates/bi/integration_hub/{integration_connector,warehouse_sync_endpoint,bi_webhook_subscription,bi_extension_plugin}/list.html` — Missing `aria-label` attributes on icon-only `.btn-icon` action buttons (`aria-label="View details"`, `aria-label="Edit ..."`, `aria-label="Delete ..."`). fixed — fix(bi): add aria-label attributes to action buttons in connector list
- [x] `I7`: `apps/bi/models/IntegrationHub/{WarehouseSyncEndpoints,BiWebhookSubscriptions,IntegrationConnectors,BiExtensionPlugins}.py` — Missing composite indexes on hot filter and cadence columns: `["tenant", "sync_mode"]`, `["tenant", "sync_schedule"]`, `["tenant", "is_active"]`, `["tenant", "payload_format"]`, `["tenant", "sync_interval"]`, `["tenant", "is_enabled"]`, and `["tenant", "is_verified"]`. Generate and apply incremental migration `0043`. fixed — feat(bi): apply incremental migration 0043 adding composite indexes

---

### Minor

- [x] `M1`: `apps/bi/views/IntegrationHub/{IntegrationConnectors,WarehouseSyncEndpoints,BiWebhookSubscriptions}.py` — Concurrency race conditions on counter increments in action handlers. Use Django's `F()` expressions for atomic updates (`F("total_messages_processed") + 1`, `F("total_rows_synced") + 2500`, `F("total_deliveries") + 1`). fixed — fix(bi): atomic message counter update and updated_at persistence in connector ping
- [x] `M2`: `apps/bi/views/IntegrationHub/IntegrationConnectors.py:192` — In `integration_connector_ping`, include `"updated_at"` in `save(update_fields=[...])` for audit timestamp consistency. fixed — fix(bi): atomic message counter update and updated_at persistence in connector ping
- [x] `M3`: `apps/bi/forms/IntegrationHub/IntegrationConnectors.py:90-100` — Null-safety on string stripping in `clean_auth_credentials_raw`: `(self.cleaned_data.get("auth_credentials_raw") or "").strip()`. fixed — fix(bi): omit cleartext credentials prepopulation on connector edit
- [x] `M4`: `templates/bi/integration_hub/{integration_connector,warehouse_sync_endpoint,bi_webhook_subscription,bi_extension_plugin}/list.html` — Use semantic `<nav class="pagination" aria-label="Pagination">` instead of `<div class="pagination">`. fixed — refactor(bi): use semantic nav element for pagination in connector list
- [x] `M5`: `templates/bi/integration_hub/bi_webhook_subscription/detail.html:81-85` — Webhook secret token displayed unmasked in plaintext. Add masked display. fixed — fix(bi): mask secret_token display on webhook subscription detail
- [x] `M6`: `apps/bi/views/IntegrationHub/{IntegrationConnectors,WarehouseSyncEndpoints,BiWebhookSubscriptions,BiExtensionPlugins}.py` — Unrendered user FKs in list views `select_related` attached before `.aggregate()`. Remove unrendered `select_related` joins from list querysets. fixed — perf(bi): remove unrendered select_related from connector list view
