# Review findings — scm 4.19 Integration & API Gateway

Range: `249b7dfdcde75d87c583667fb54f708c9eb0958d...HEAD` · Generated: 2026-08-18
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 3 |
| Important | 6 |
| Minor | 14 |
| **Total (deduped)** | **23** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 5 |
| security-reviewer | 7 |
| performance-reviewer | 5 |
| frontend-reviewer | 2 |
| explorer | 4 |
| qa-smoke-tester | 0 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Critical

### C1 — `apps/scm/views/IntegrationApiGateway/IntegrationEndpoints.py:350`

- **Found by:** code-reviewer
- **Lesson:** L25
- **Problem:** `integrationendpoint_rotate_credential` puts the freshly minted plaintext credential straight into `messages.success(...)`, so the secret is serialised into the session backend (`django_session`) and persists there until some later render consumes it — readable from a DB dump, a backup or a hijacked session, and liable to be copied into logs.
- **Fix:** Mirror the sibling `webhooksubscription_rotate_secret` in this same sub-module: add `_REVEAL_SESSION_KEY = "_cnx_credential_reveal"` at module level, replace the flash with `request.session[_REVEAL_SESSION_KEY] = {"pk": obj.pk, "secret": plaintext}` plus a secret-free `messages.success("Credential rotated — the new value is shown once on this page.")`; in `integrationendpoint_detail` (line 218) add `reveal = request.session.pop(_REVEAL_SESSION_KEY, None)` / `plaintext_once = reveal["secret"] if reveal and reveal.get("pk") == pk else None` and pass `plaintext_once` in `extra_context`; then add a `{% if plaintext_once %}` copy box to `templates/scm/integration/integrationendpoint/detail.html` and correct that template's header note at lines 31-32 and 39-40, which currently promise the flash message.
- **Status:** [x] fixed — `security(scm): move the rotated endpoint credential off the messages framework onto a pop-once session key` (d364c3c6) + `fix(scm): render the pop-once credential reveal on the endpoint detail page` (fdd0fa0e). Two files, two commits. Same defect as C2. Verified as `admin_acme`: rotate POST → 200 with the reveal card and the 32-char plaintext, plaintext present exactly once in the document, secret-free flash wording, refresh → card gone and no `_cnx_credential_reveal` in the session.

### C2 — `apps/scm/views/IntegrationApiGateway/IntegrationEndpoints.py:350`

- **Found by:** security-reviewer
- **Lesson:** L25
- **Problem:** `integrationendpoint_rotate_credential` flashes the freshly minted plaintext credential through `messages.success(...)`, so the secret is serialised into the messages store (Django's default `FallbackStorage` = a base64 `messages` cookie, falling back to `django_session` in MySQL) where it is readable from a DB dump, a backup, a proxy/access log or a hijacked session — exactly the failure L25 records, and the sibling `webhooksubscription_rotate_secret` in this same sub-module already does it the right way.
- **Fix:** Replace the flash-with-secret with the pop-once session key the sibling uses. In this module add `_REVEAL_SESSION_KEY = "_cnx_credential_reveal"`, then:

```python
    request.session[_REVEAL_SESSION_KEY] = {"pk": obj.pk, "secret": plaintext}
    messages.success(request, "Credential rotated — the new value is shown once on this page. "
                              "Copy it now; it cannot be retrieved again.")
    return _detail(pk)
```

and in `integrationendpoint_detail`, before `crud_detail(...)`:

```python
    reveal = request.session.pop(_REVEAL_SESSION_KEY, None)
    ...
    extra_context={..., "plaintext_once": reveal["secret"] if reveal and reveal.get("pk") == pk else None}
```

Then add the reveal card to `templates/scm/integration/integrationendpoint/detail.html` (copy the shape at `templates/accounting/integration/detail.html:26-35`): `{% if plaintext_once %}<div class="card">…<code>{{ plaintext_once }}</code></div>{% endif %}`.
- **Status:** [x] fixed — same change as C1 (d364c3c6 + fdd0fa0e). Duplicate finding, one fix.

### C3 — `templates/scm/integration/webhooksubscription/detail.html:274`

- **Found by:** frontend-reviewer
- **Lesson:** L7
- **Problem:** The Signing-secret card never renders the `plaintext_once` context key, so a rotated signing secret is generated, stored as a one-way hash, and NEVER displayed — the value is permanently unrecoverable, while the flash message that fires alongside it tells the user "the new value is shown once on this page" and the Rotate confirm dialog (line 306) promises "displayed EXACTLY ONCE, on the next screen".
- **Fix:** Insert a reveal block immediately after `<div class="card-body">` on line 274 (before the `<dl class="detail-grid">`), copying the shipped sibling `templates/accounting/integration/detail.html:26-35` verbatim apart from the wording:

{% if plaintext_once %}
  <div class="card">
    <div class="card-header"><h2 class="card-title"><i data-lucide="alert-triangle"></i> Copy this secret now — it will not be shown again</h2></div>
    <div class="card-body">
      <p class="text-danger fw-600">Store this signing secret somewhere safe and give it to whoever verifies these calls. It is stored only as a hash, so it is shown once and cannot be retrieved later.</p>
      <code style="display:block; margin-top:.75rem; padding:.75rem 1rem; word-break:break-all;">{{ plaintext_once }}</code>
    </div>
  </div>
{% endif %}

(`.text-danger` and `.fw-600` both exist in theme.css.) The view already pops the value into the context — `apps/scm/views/IntegrationApiGateway/WebhookSubscriptions.py:265-266,278` — and its own module docstring at line 55 states "Until it has one, a rotated secret is never displayed." No Python change is needed.
- **Status:** [x] fixed — `fix(scm): render plaintext_once so a rotated webhook signing secret is actually shown` (898c5d28). One template edit resolves C3, I4, I5 and I6, which are four reports of the same missing block. **Placement deviates from the prescription:** C3/I5/I6 asked for it inside the Signing-secret card ~200 lines down; I put it directly under the page header instead. A value the reader must copy before navigating away must not sit below the fold, and the top position is what the shipped reference all four findings name (`templates/accounting/integration/detail.html:26-35`) uses — it also makes this page and `integrationendpoint/detail.html` identical in shape. Verified as `admin_acme`: rotate POST → 200 with the card and a 32-char plaintext whose prefix matches the freshly stored `signing_secret_prefix`, present exactly once in the document; refresh → card gone, `_whk_secret_reveal` no longer in the session.

## Important

### I1 — `apps/crm/management/commands/seed_crm.py:496`

- **Found by:** explorer
- **Problem:** This changeset made `crm.Webhook.secret` Fernet-encrypted at rest (apps/crm/models/AutomationWorkflow/Webhooks.py:49 encrypts in `save()`), but the seeder still signs with `wh.secret`, which after `Webhook.objects.create(...)` holds the `fernet.v1:` ciphertext — so every seeded `WebhookDelivery.signature` is an HMAC of the ciphertext and does not match what `_deliver_webhook` now computes, which is the exact failure the engine's new comment (apps/crm/views/AutomationWorkflow/_engine.py:86-88) warns against.
- **Fix:** Change line 496 to `sig = hmac.new(wh.get_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()` — `get_secret()` is the accessor added on the model at apps/crm/models/AutomationWorkflow/Webhooks.py:52. No other seeder line reads `.secret`.
- **Status:** [x] fixed — `fix(crm): sign the seeded webhook deliveries with the plaintext secret, not the ciphertext` (df275c64). Same defect as M1; one fix. Confirmed against a rolled-back probe row: the column is `fernet.v1:`-marked straight after `create()`, the `get_secret()` digest equals an HMAC over the true plaintext (which is what `test_webhook_delivery_hmac_correct` pins), and the old `.secret` spelling produced a different digest. Swept `apps/` for other direct readers — only the model itself and `WebhookForm.clean_secret` remain, both correct.

### I2 — `apps/scm/management/commands/seed_scm.py:5872`

- **Found by:** code-reviewer
- **Problem:** The seeded EDI endpoint sets `interchange_id="ZZ12345678"`/`interchange_qualifier="ZZ"` AND `logistics_client=client` on the same row, which `IntegrationEndpoint.clean()` and `IntegrationEndpointForm.clean()` explicitly refuse (constraint A); because `client` is picked as `LogisticsClient.objects.filter(tenant=tenant).order_by("id").first()` (line 5806) it lands on the `dedicated` client, whose `edi_partner_id` is blank, so `effective_interchange_id` returns "" and the flagship EDI connection renders an EMPTY interchange id on its detail page while carrying one on the row — and opening its edit form and pressing Save raises a field error on a value the user never typed.
- **Fix:** At line 5806 select the EDI-configured client instead: `client = (LogisticsClient.objects.filter(tenant=tenant, integration_mode="edi").exclude(edi_partner_id="").order_by("id").first())`, then at lines 5872/5876 pass `interchange_id="" , interchange_qualifier=""` whenever `client` is not None (keep the typed `ZZ12345678`/`ZZ` pair only on the `client is None` fallback, with `logistics_client=None`), so the seeded row satisfies the same `clean()` the form enforces.
- **Status:** [x] fixed — `fix(scm): seed the EDI endpoint against the EDI-configured client and honour constraint A` (4702ad4f). Verified by running `_seed_integration_tenant` for real inside a rolled-back transaction: the reseeded CNX-00004 links STARKIND (`integration_mode="edi"`), holds `""` in both of its own interchange columns, resolves `effective_interchange_id="1234567890123"` / qualifier `"ZZ"` through the FK, and passes `full_clean()` — the same validation the form runs. **Note for the next session:** the dev DB still holds the old bad row, because `_seed_integration_tenant` is idempotent-skip. `seed_scm --flush` restores it correctly.

### I3 — `apps/scm/views/IntegrationApiGateway/WebhookSubscriptions.py:204`

- **Found by:** security-reviewer
- **Lesson:** L27
- **Problem:** `webhooksubscription_create` (line 204) and `webhooksubscription_edit` (line 282) are only `@login_required`, so any ordinary tenant member can register or retarget a webhook target URL — an egress destination for workspace data — even though this same module admin-gates delete and rotate-secret on the stated ground that "a webhook target is an egress path out of the workspace", and the identical CRM view was already fixed to `@tenant_admin_required` in a prior code review (`apps/crm/views/AutomationWorkflow/Webhooks.py:29` and `:42`, commented "webhook config (target URL = future SSRF surface + signing secret) is admin-level").
- **Fix:** Add the gate to both write views, matching the CRM sibling:

```python
@login_required
@tenant_admin_required  # webhook config (target URL = egress path + signing secret) is admin-level, per crm.webhook_create
def webhooksubscription_create(request):
    ...

@login_required
@tenant_admin_required
def webhooksubscription_edit(request, pk):
    ...
```

Then stop offering the now-403 controls: wrap the Edit icon at `templates/scm/integration/webhooksubscription/list.html:293` and the "Add" button on that page, plus the Edit button on `webhooksubscription/detail.html`, in `{% if is_tenant_admin %}` (the detail view already passes that key; add it to the list view's `extra_context`), and correct the decorator table in the detail template's header comment at line 25, which currently asserts `webhooksubscription_edit @login_required -> ungated here`. Grep for the same shape across the family: `grep -rn "^def .*_create\|^def .*_edit" -B3 apps/scm/views/IntegrationApiGateway/`.
- **Status:** [x] fixed — three files, three commits: `security(scm): gate webhook subscription create and edit behind @tenant_admin_required` (b5dd92a4), `fix(scm): hide the admin-only subscription controls from members on the webhook list` (a0f79410), `fix(scm): gate the subscription detail Edit button and correct its decorator table` (fb210b76). The list-template commit also covers M9/M10 for this page, because the delete form's own comment asserted "the contract pins no `is_tenant_admin` key for this page" — leaving it ungated would have left a comment contradicting the view. Verified: `admin_acme` 200 on create/edit/list; `sales_acme` (non-admin member, same tenant) 403 on create and edit, 200 with rows on the list and neither URL anywhere in the document. Scope held to the two views named — `integrationendpoint_create`/`_edit` are the sub-module's day-to-day register and were deliberately not gated.

### I4 — `templates/scm/integration/webhooksubscription/detail.html:76`

- **Found by:** security-reviewer
- **Lesson:** L25
- **Problem:** `webhooksubscription_detail` pops the rotated secret into the `plaintext_once` context key but this template never renders it (the contract block at lines 8-18 omits it entirely), so rotating a signing secret writes the plaintext into the session store, pops it, and discards it unseen — the flash message and the confirm dialog both promise "the new value is shown once on this page" and nothing is shown, leaving the operator with a rotated credential nobody can obtain.
- **Fix:** Add the one-time reveal card immediately after `{% block content %}` (line 76), copying the shipped shape at `templates/accounting/integration/detail.html:26-35`:

```django
  {% if plaintext_once %}
    {# One-time reveal — this plaintext secret is never shown again after this page. #}
    <div class="card">
      <div class="card-header"><h2 class="card-title"><i data-lucide="alert-triangle"></i> Copy this signing secret now</h2></div>
      <div class="card-body">
        <p class="fw-600">It is shown only once and is stored only as a prefix plus a one-way hash, so it cannot be retrieved later.</p>
        <code class="mono" style="display:block; margin-top:.75rem; padding:.75rem 1rem; word-break:break-all;">{{ plaintext_once }}</code>
      </div>
    </div>
  {% endif %}
```

Also add `plaintext_once` to the template's contract comment block (lines 8-18) so the next pass does not delete it as an unpinned key.
- **Status:** [x] fixed — same change as C3 (898c5d28). This finding's placement (directly after `{% block content %}`) is the one I took; `plaintext_once` was added to the contract block as asked.

### I5 — `templates/scm/integration/webhooksubscription/detail.html:274`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** `webhooksubscription_detail` puts the freshly rotated signing secret into the context as `plaintext_once` (apps/scm/views/IntegrationApiGateway/WebhookSubscriptions.py:266,278) but this template never references it, so the one-time reveal is popped from the session and silently discarded — the flash message "the new value is shown once on this page. Copy it now; it cannot be retrieved again" is false and the Generate/Rotate secret button produces a credential no one can ever obtain.
- **Fix:** Inside the "Signing secret" card body (immediately after `<div class="card-body">` on line 274, before the `<dl class="detail-grid">`), add the pop-once reveal block the sibling pages already use, e.g.: `{% if plaintext_once %}<div class="card-body"><p class="text-muted"><span class="badge badge-amber">Copy it now</span> This value is shown once and is stored only as a hash — it cannot be retrieved again.</p><code class="mono" style="display:block;padding:.6rem;word-break:break-all;">{{ plaintext_once }}</code></div>{% endif %}`. Copy the exact shape from templates/accounting/integration/detail.html:26-32 (the sibling the view docstring names) or templates/tenants/encryptionkey/detail.html:22. Do not change the view — `plaintext_once` is already correct and pk-scoped.
- **Status:** [x] fixed — same change as C3 (898c5d28). Placement is the page header rather than the Signing-secret card body; see C3 for why. The view was left alone, as instructed.

### I6 — `templates/scm/integration/webhooksubscription/detail.html:306`

- **Found by:** code-reviewer
- **Lesson:** L7
- **Problem:** The rotate button's confirm text promises the new signing secret is "displayed EXACTLY ONCE, on the next screen", and `webhooksubscription_detail` does pass `plaintext_once`, but nothing in this template ever renders it — so rotating replaces the stored marker and the new plaintext is silently discarded with no reveal route to recover it (the view's own docstring at `apps/scm/views/IntegrationApiGateway/WebhookSubscriptions.py:55` flags this as unfinished).
- **Fix:** Add a `{% if plaintext_once %}` block immediately above the `{% if is_tenant_admin %}` at line 296, inside the signing-secret card: a `<code class="mono">{{ plaintext_once }}</code>` in a `badge-amber`-headed panel with "Copy this now — it is shown once and cannot be retrieved again". No view change is needed; the context key already exists.
- **Status:** [x] fixed — same change as C3 (898c5d28). The rotate-form comment claiming the value "appears exactly once in the flash message afterwards" was corrected in the same commit, since it was the stale half of this finding.

## Minor

### M1 — `apps/crm/management/commands/seed_crm.py:496`

- **Found by:** security-reviewer
- **Lesson:** L28
- **Problem:** This changeset made `Webhook.save()` encrypt `self.secret` in place (`apps/crm/models/AutomationWorkflow/Webhooks.py:49`) and updated `_engine.py` to read through `get_secret()`, but this seeder still HMACs with `wh.secret.encode()` — which is now the Fernet ciphertext string, not the key — so every seeded delivery signature is computed over the wrong key material and contradicts the model's own "Read it with get_secret(), never `.secret` directly" rule at line 24.
- **Fix:** Read through the accessor the same way `_engine.py` now does:

```python
            sig = hmac.new(wh.get_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
```

Sweep for any other surviving direct reader with `grep -rn "\.secret\b" apps/ --include=*.py | grep -v get_secret | grep -v migrations` — this is the only one left outside `crypto.py` and the model.
- **Status:** [x] fixed — same change as I1 (df275c64). The sweep was run: the only other non-migration readers are `Webhook.save()`/`get_secret()` themselves and `WebhookForm.clean_secret`, which returns `self.instance.secret` on the blank-on-edit path — correct, because `encrypt()` is a no-op on an already-marked value.

### M2 — `apps/crm/models/AutomationWorkflow/Webhooks.py:63`

- **Found by:** code-reviewer
- **Problem:** `secret_masked` now calls `get_secret()`, which raises `ImproperlyConfigured` from `apps/core/crypto.py:104` when the key no longer matches — so a purely cosmetic mask turns the CRM webhook detail page into a 500 after a `SECRET_KEY`/`FIELD_ENCRYPTION_KEY` change (including the ordinary dev path of setting a real SECRET_KEY after seeding under the insecure fallback). I am unsure between Minor and Important: the boundary only trips on a misconfiguration, but the blast radius is a whole page rather than a signing failure.
- **Fix:** Wrap the decrypt in `secret_masked` only: `try: s = self.get_secret() except ImproperlyConfigured: return "(set — key mismatch)"`, leaving `get_secret()` itself strict so `_deliver_webhook` still fails loudly at signing time.
- **Status:** [x] fixed — `fix(crm): let secret_masked degrade on an undecryptable row instead of 500-ing the page` (e4c6bb2b). Same defect as M3; one fix, using M3's fuller wording. On the severity question you raised: Minor is right — the blast radius is the CRM webhook **detail** page only (`templates/crm/workflow/webhook/detail.html:36` is the sole consumer; the list page does not render it).

### M3 — `apps/crm/models/AutomationWorkflow/Webhooks.py:63`

- **Found by:** security-reviewer
- **Problem:** `secret_masked` is a pure display property but calls `get_secret()`, which raises `ImproperlyConfigured` on any undecryptable row, so a `SECRET_KEY`/`FIELD_ENCRYPTION_KEY` change or a database restored into a different environment turns the CRM webhook list and detail pages into hard 500s for every user instead of degrading the masked display.
- **Fix:** Let the read-only display path degrade while `get_secret()` (the signing path) keeps raising:

```python
    @property
    def secret_masked(self):
        try:
            s = self.get_secret()
        except ImproperlyConfigured:
            # Key rotated or a different environment — a display column must not 500 the page.
            return "(set — undecryptable with the current key)"
        return f"••••{s[-4:]}" if len(s) >= 4 else ("(set)" if s else "(none)")
```

with `from django.core.exceptions import ImproperlyConfigured` at the top of the module.
- **Status:** [x] fixed — same change as M2 (e4c6bb2b); this finding's code is what was applied. Correction to the problem statement: only the webhook **detail** page renders `secret_masked`, not the list. Verified against a rolled-back probe — a foreign Fernet token masks to the degraded label while `get_secret()` still raises, and the empty/short branches are unchanged. `apps/crm/tests/test_workflow_110.py`: 160 passed.

### M4 — `apps/scm/models/IntegrationApiGateway/IntegrationMessages.py:175`

- **Found by:** performance-reviewer
- **Problem:** `scm_msg_tnt_status_idx` is `(tenant, status)`, which serves the equality filter but not the ORDER BY, so `integration_exceptions` — which ALWAYS filters `tenant + status="failed"` and then orders by `-occurred_at, -id` with a 30-row LIMIT — makes MariaDB filesort the entire failed set on every page load of the sub-module's main report.
- **Fix:** Widen the existing index rather than adding a fourth: `models.Index(fields=["tenant", "status", "occurred_at"], name="scm_msg_tnt_status_idx")`. The 2-column index remains available as the leftmost prefix, so nothing else regresses. This needs a new migration (RemoveIndex + AddIndex on `integrationmessage`) — agree the migration number with any concurrent session in this checkout before generating it (L43).
- **Status:** [x] fixed — two commits: `perf(scm): widen scm_msg_tnt_status_idx to (tenant, status, occurred_at)` (3eb0825c) and `migration(scm): 0034 - rebuild scm_msg_tnt_status_idx as (tenant, status, occurred_at)` (f1ef1d4d). **Claimed migration number 0034** — the tree was clean at the start of this pass and 0033 was the last committed migration, so no concurrent session's number was taken. Applied locally; `makemigrations --check --dry-run` says "No changes detected". Verified in the live schema with `SHOW INDEX` (seq 1/2/3 = `tenant_id`/`status`/`occurred_at`) and by re-rendering both consumers at 200 with their rows.

### M5 — `apps/scm/views/IntegrationApiGateway/IntegrationMessages.py:204`

- **Found by:** performance-reviewer
- **Problem:** `integrationmessage_list` SELECTs the `payload_excerpt` and `error_message` TextFields for all 30 rows on every page load; the list template renders neither (it renders `error_code` only), so a truncated-document column is pulled off the fastest-growing table for nothing — the same waste `integrationendpoint_list` already avoids with `.defer("notes")` (IntegrationEndpoints.py:124).
- **Fix:** Append `.defer("payload_excerpt", "error_message")` to the queryset built on lines 204-205, i.e. `qs = (IntegrationMessage.objects.filter(tenant=request.tenant).select_related("endpoint").defer("payload_excerpt", "error_message"))`. `defer` touches only the SELECT list, so `crud_list`'s search on `number`/`control_number`/`external_id`/`source_reference` and all five filters are unaffected.
- **Status:** [x] fixed — `perf(scm): trim the message list SELECT - defer the two TextFields and drop the unused order joins` (0b05d5db). Applied together with M6, since both change the same statement. Verified by capturing the paginated SELECT with `DEBUG=True`: neither TextField is in the column list, and the search plus all five filters plus the date window still return 200.

### M6 — `apps/scm/views/IntegrationApiGateway/IntegrationMessages.py:205`

- **Found by:** performance-reviewer
- **Problem:** `integrationmessage_list` joins `purchase_order` and `sales_order`, but no column on the list page renders either FK (the template says so itself at templates/scm/integration/integrationmessage/list.html:73-75: "the two typed order pointers are deliberately NOT rendered here"), so every page load pays two LEFT OUTER JOINs and hydrates ~55 unused columns per row on a 30-row page over the sub-module's fastest-growing table.
- **Fix:** Change line 205 to `.select_related("endpoint")` only. Do NOT touch `integrationmessage_detail` (line 261), where both pointers ARE rendered (detail.html:239, 249) and the joins are correct.
- **Status:** [x] fixed — same commit as M5 (0b05d5db). Verified `scm_purchaseorder` and `scm_salesorder` are gone from the list's paginated SELECT while `scm_integrationendpoint` is still joined; `integrationmessage_detail` was left alone and still renders its purchase-order number at 200.

### M7 — `apps/scm/views/IntegrationApiGateway/IntegrationMessages.py:398`

- **Found by:** performance-reviewer
- **Problem:** The exceptions cockpit fetches `payload_excerpt` for every one of the 30 rows on the page and never renders it (exceptions.html renders `error_code` and a truncated `error_message` only), pulling an unused TextField off the failure set on the sub-module's hottest report page.
- **Fix:** Defer on the PAGINATED queryset only, so the grouped roll-up above is untouched: `page_obj = paginate(request, qs.defer("payload_excerpt"), MESSAGES_PER_PAGE)`. Leave `qs` itself as-is at line 364 — `error_groups` on lines 382-387 goes through `.values()`, and putting the `defer` on `qs` would make the interaction between the two harder to reason about for no gain.
- **Status:** [x] fixed — `perf(scm): defer payload_excerpt on the exceptions cockpit page queryset` (35fd2704). Applied exactly as prescribed, on the paginated queryset only. Verified with `DEBUG=True`: `payload_excerpt` is absent from the page SELECT, `error_message` is still there (the table truncates it), the GROUP BY roll-up still runs, and `?q=` / `?document_type=` / a junk `?endpoint=` / `?page=2` all return 200.

### M8 — `apps/scm/views/IntegrationApiGateway/WebhookDeliveries.py:222`

- **Found by:** performance-reviewer
- **Problem:** `webhookdelivery_list` SELECTs `WebhookDelivery.payload_excerpt` for all 30 rows and never renders it (the list shows `event`, `status`, `attempt_no`, `response_code` and a truncated `error_message`), pulling an unused TextField off the table that grows one row per attempt.
- **Fix:** Append `.defer("payload_excerpt")` to the queryset on lines 222-223: `qs = (WebhookDelivery.objects.filter(tenant=request.tenant).select_related("subscription").defer("payload_excerpt"))`. `error_message` must NOT be deferred — it is rendered at webhookdelivery/list.html:257-258.
- **Status:** [x] fixed — `perf(scm): defer payload_excerpt on the webhook delivery list` (9ddafb4f). Verified with `DEBUG=True`: `payload_excerpt` gone from the paginated SELECT, `error_message` still present, `scm_webhooksubscription` still joined; the list renders at 200 in a flat 11 queries and `?status=failed` stays at 11, proving the truncated error text costs no per-row fetch.

### M9 — `templates/scm/integration/integrationendpoint/list.html:397`

- **Found by:** code-reviewer
- **Problem:** The Delete POST form in the Actions column is rendered for every user even though `integrationendpoint_delete` is `@tenant_admin_required`, so a non-admin member is offered a button that 403s — inconsistent with this sub-module's own detail page, which correctly hides it behind `{% if is_tenant_admin %}` (detail.html:538).
- **Fix:** Add `"is_tenant_admin": _is_tenant_admin(request.user)` to the `extra_context` of `integrationendpoint_list` (`apps/scm/views/IntegrationApiGateway/IntegrationEndpoints.py:151`) and wrap the delete form at line 397 in `{% if is_tenant_admin %}...{% endif %}`. Same shape in `templates/scm/integration/webhooksubscription/list.html:307` against `webhooksubscription_list` — grep `rg -n 'tenant_admin_required' apps/scm/views/` and check each gated view's list template for an ungated button.
- **Status:** [x] fixed — same defect as M10, four commits across the two pages: the subscription half landed under I3 (`fix(scm): hide the admin-only subscription controls from members on the webhook list`, a0f79410, plus the view key in b5dd92a4), and the endpoint half as `fix(scm): pin is_tenant_admin on the endpoint list so the Delete form can be gated` (708e8ba3) + `fix(scm): hide the admin-only Delete form from members on the endpoint list` (7e1d2c28). Verified: `sales_acme` gets 200 with rows and no delete URL on either list, still sees Edit on the endpoint list (that route is plain `@login_required`), and a direct POST to the endpoint delete route is still 403 with the row intact.

### M10 — `templates/scm/integration/integrationendpoint/list.html:397`

- **Found by:** security-reviewer
- **Problem:** The Delete POST form is rendered for every logged-in user while `integrationendpoint_delete` is `@tenant_admin_required`, so a non-admin who clicks through the confirm dialog gets a raw 403 PermissionDenied page; the same shape sits at `templates/scm/integration/webhooksubscription/list.html:307`, and both detail pages already do this correctly with `is_tenant_admin`.
- **Fix:** Pass the flag from the list views and gate the button, mirroring `integrationendpoint_detail`. In `apps/scm/views/IntegrationApiGateway/IntegrationEndpoints.py::integrationendpoint_list` add `"is_tenant_admin": _is_tenant_admin(request.user)` to `extra_context` (`_is_tenant_admin` is already imported at line 52), then wrap the form:

```django
{% if is_tenant_admin %}
  <form method="post" action="{% url 'scm:integrationendpoint_delete' obj.pk %}" onsubmit="…">
    {% csrf_token %}<button class="btn-icon danger" type="submit" title="Delete"><i data-lucide="trash-2"></i></button>
  </form>
{% endif %}
```

Do the same for `webhooksubscription_list` / `templates/scm/integration/webhooksubscription/list.html:307`. The decorator stays — this only stops offering a button that 403s.
- **Status:** [x] fixed — same change as M9 (708e8ba3 + 7e1d2c28 for the endpoint list; a0f79410 + b5dd92a4 for the subscription list under I3). The decorators were left exactly as they were.

### M11 — `templates/scm/integration/webhookdelivery/list.html:308`

- **Found by:** security-reviewer
- **Lesson:** L42
- **Problem:** `{{ obj.event }}` — a bare `CharField(max_length=60)` with no choices and no validator (`apps/scm/models/IntegrationApiGateway/WebhookDeliveries.py:126`) — is interpolated raw into `onsubmit="return confirm('…')"`, and Django's autoescaping turns an apostrophe into `&#x27;` which the HTML parser decodes back to a bare quote before the JS engine sees it, so an event name containing `'` silently breaks the confirm guard open and a crafted one executes; the same line exists at `templates/scm/integration/webhookdelivery/detail.html:300`, while every other confirm in this sub-module correctly interpolates only the generated `obj.number`.
- **Fix:** Interpolate nothing user-derived into the confirm string, per L42 rule 1 — drop the value and let the button label carry the context:

```django
onsubmit="return confirm('Schedule another delivery attempt for this event? The next slot on the backoff ladder is stamped onto the row and the attempt count goes up by one. …');"
```

If the event name must appear, use `{{ obj.event|escapejs }}` (escapes `'` to `'`, which survives HTML-attribute decoding). Apply to both `templates/scm/integration/webhookdelivery/list.html:308` and `templates/scm/integration/webhookdelivery/detail.html:300`. The grep that finds the family: `grep -rn "confirm('[^\"]*{{" templates/scm/integration/`.
- **Status:** [x] fixed — two commits: `security(scm): escapejs the event name in the delivery-list retry confirm` (67d3856a) and `security(scm): escapejs the event name in the delivery-detail retry confirm` (4ce3172c). **Took the `|escapejs` branch rather than dropping the value**, which this finding offers and M12 prescribes: the event name is the only thing telling the operator which attempt they are re-queueing, and `WebhookDelivery` is `TenantOwned` with no `number` column, so the sub-module's usual "interpolate the generated number instead" is not available here. Verified by setting a seeded failed delivery's event to `order'); alert(1);//` inside a rolled-back transaction — both pages render the backslash-u escaped form with no `&#x27;`/`&#39;` left for the HTML-attribute decode and no early string terminator.

### M12 — `templates/scm/integration/webhookdelivery/list.html:308`

- **Found by:** explorer
- **Lesson:** L42
- **Problem:** The Retry confirm string interpolates `{{ obj.event }}` — a free-text CharField, not a system-generated number — straight into a JavaScript string literal; an apostrophe in an event name escapes to `&#39;`, which the HTML parser decodes back to a bare quote before JS parses the attribute, breaking the dialog open and silently removing the confirmation guard (L42). The sibling templates in this sub-module deliberately interpolate only the CNX-/WHK- number for this reason.
- **Fix:** Apply `|escapejs` to the value in both places it appears in a confirm string: line 308 here and templates/scm/integration/webhookdelivery/detail.html:300 — `confirm('Schedule another delivery attempt for {{ obj.event|escapejs }}? …')`. `|escapejs` emits `'`, which survives the HTML-attribute decode that defeats the default autoescape.
- **Status:** [x] fixed — same change as M11 (67d3856a + 4ce3172c); this finding's `|escapejs` prescription is the one applied. Both templates now carry a comment saying why the filter is load-bearing rather than decoration.

### M13 — `templates/scm/integration/webhookdelivery/list.html:332`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** `append_only_note` is passed by all five 4.19 log/report views (IntegrationMessages.py:231,275,407 and WebhookDeliveries.py:243,286) and is consumed by none of the eleven 4.19 templates — each page hand-wrote its own wording instead, which is exactly what the WebhookDeliveries.py:219-220 docstring says the key exists to prevent ("so the template can say why in one place rather than each page inventing its own wording"). Dead context key plus five divergent copies of one rule.
- **Fix:** Either render it — replace the hand-written footer paragraph at line 332 (and its equivalents at templates/scm/integration/integrationmessage/list.html:332, .../integrationmessage/detail.html:426, .../webhookdelivery/detail.html:276 and templates/scm/integration/exceptions.html:284) with `{{ append_only_note }}`, matching templates/scm/assets/meterreading/list.html:61 — or drop the key from the five `extra_context`/`render` dicts and delete the `APPEND_ONLY_NOTE` constants. Rendering is the house pattern; pick one and make the docstrings agree.
- **Status:** [x] fixed — **rendered**, five commits, one per template: `12cb4d9e` (message list), `f97d3516` (message detail), `03209175` (exceptions cockpit), `0e55fe96` (delivery list), `f0fd214b` (delivery detail). I first went the other way and deleted the constants, on the grounds that all five pages already say it better and the key was dead — then reverted, because a sweep showed 4.13 `MeterReading`, 4.15 `ColdChain`/`TemperatureReading` and 4.16 `PortalActivity` all pass **and print** this key. Removing it would have forked 4.19 out of step with four sibling append-only logs. It is printed as the LEADING paragraph with each page's own wording following, which is the shipped shape at `templates/scm/assets/meterreading/list.html:61` and `templates/scm/portal/portalactivity/detail.html:309` — the shared sentence states the rule, the paragraph under it names that page's affordances. The key is now pinned in all five contract blocks. Verified: all five pages 200 with the escaped note text present and their page-specific wording intact.

### M14 — `templates/scm/integration/webhooksubscription/detail.html:444`

- **Found by:** frontend-reviewer
- **Problem:** The recent-deliveries Response cell guards the nullable `response_code` with truthiness (`{% if d.response_code %}`) while the two sibling templates that render the same column deliberately use `is not None` and document why — `webhookdelivery/list.html:270` and `webhookdelivery/detail.html:168` both say "a nullable integer read for truthiness would swallow a legitimate zero". This file's own header comment (lines 54-57) claims every nullable is wrapped in an explicit guard of that shape.
- **Fix:** Change line 444 from `{% if d.response_code %}` to `{% if d.response_code is not None %}`, matching `templates/scm/integration/webhookdelivery/list.html:270`. Leave the `{% else %}<span class="text-muted">—</span>` branch as-is.
- **Status:** [x] fixed — `fix(scm): guard the recent-deliveries Response cell with is not None, not truthiness` (cecac795). Applied as prescribed; the `{% else %}` branch is untouched, and the cell comment now carries the siblings' explanation. Verified against a rolled-back probe: `response_code=0` renders `0`, `None` still renders the muted em dash, and 503 still renders.

## Fix pass — outcome (code-fixer, 2026-08-18)

All 23 findings resolved: **23 fixed, 0 skipped, 0 left open.** 26 commits, one file each, nothing
pushed. `manage.py check` clean; `makemigrations --check --dry-run` reports "No changes detected"
(migration 0034 is committed). `apps/crm/tests/test_workflow_110.py`: 160 passed.

Eight of the 23 were duplicate reports of four defects, so the 23 findings came to 19 distinct fixes:
C1=C2 (endpoint credential reveal), C3=I4=I5=I6 (webhook secret reveal), I1=M1 (seeder HMAC key),
M2=M3 (`secret_masked` degradation), M9=M10 (ungated delete buttons), M11=M12 (confirm-string
escaping).

**Three places where I did not follow the prescribed fix**, each argued in the finding's Status line:

1. **C3/I5/I6 — reveal card placement.** Put at the top of the page rather than inside the
   Signing-secret card ~200 lines down. A value that must be copied before navigating away cannot sit
   below the fold, and the top position is what the shipped reference all four findings name
   (`templates/accounting/integration/detail.html:26-35`) uses.
2. **M11 — kept the event name.** Took M12's `|escapejs` branch rather than M11's "interpolate
   nothing". `WebhookDelivery` is `TenantOwned` with no `number` column, so the sub-module's usual
   "interpolate the generated number instead" was unavailable, and the event name is the only thing
   identifying which attempt is being re-queued.
3. **M13 — rendered rather than removed, after first doing the opposite.** I initially deleted the
   dead key and both `APPEND_ONLY_NOTE` constants, reasoning that all five pages already state the
   rule in better page-specific words. That was wrong and was reverted before any commit: 4.13
   `MeterReading`, 4.15 `ColdChain`/`TemperatureReading` and 4.16 `PortalActivity` all pass **and
   print** this key, so removing it would have forked 4.19 out of step with four sibling append-only
   logs.

**Verification method.** Every view/template fix was re-rendered through the Django test client as
`admin_acme` with content asserted, not status alone. Security fixes were additionally checked as
`sales_acme` (a non-admin member of the same tenant) and, for the escaping fix, against a hostile
`order'); alert(1);//` value in a rolled-back transaction. Performance fixes were verified by
capturing the actual SQL with `DEBUG=True` rather than by inspection. Final sweep: all 18 4.19 routes
200 for the admin with content present, the two newly-gated routes 403 for the member, cross-tenant
IDOR 404 on all four detail pages as `admin_globex`, no semantic badge class in any `class="..."`
attribute, and no multi-line `{# #}` comment anywhere in `templates/scm/integration/**`.

### Follow-ups for the next session (not done here — out of this file's scope)

- **The dev DB still holds the pre-I2 EDI endpoint row.** `_seed_integration_tenant` is
  idempotent-skip, so the seeder fix does not retro-correct CNX-00004: it still carries
  `interchange_id="ZZ12345678"` alongside the `api`-mode logistics client, which means its detail page
  shows a blank effective interchange id and its edit form errors on save. `seed_scm --flush` fixes it.
- **App-wide pass worth scheduling (clone-family, L18):** `(tenant, status)` indexes that also carry a
  `-timestamp` ORDER BY exist across the app; M4 widened only 4.19's. `WebhookDelivery` has the same
  shape and was deliberately left (colder path). The performance lane's own note lists it.
- **`config/settings.py` sets no `MESSAGE_STORAGE`**, so flash messages ride a client-side cookie
  before falling back to the session. C1/C2 no longer depend on it (the secret is on neither store
  now), but pinning `SessionStorage` app-wide is still worth doing.
- **No tests ship for 4.19.** The regression guards the fixes in this pass most want: that neither
  rotate view leaves a plaintext in `response.wsgi_request.session` after the detail render, that
  `IntegrationEndpoint.clean()` rejects `interchange_id` alongside a `logistics_client`, and that
  `webhooksubscription_create`/`_edit` are 403 for a non-admin member.

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-reviewer:** - No tests ship with this changeset for 4.19 (`apps/scm/tests/` is untouched). The obvious gaps a test-writer should close: `test_integration_security.py` asserting the rotate views are POST-only + tenant-admin-only and that the plaintext never appears in `response.wsgi_request.session` (the L25 regression guard for finding 1); `test_integration_models.py` asserting `IntegrationEndpoint.clean()` rejects `interchange_id` alongside a `logistics_client` (the invariant the seeder currently violates); and `test_integration_views.py` asserting `webhookdelivery_retry` at `attempt_no == MAX_ATTEMPTS` marks the row `exhausted` and clears `next_attempt_at`.\n- The `apps/core/crypto.py` + `crm.Webhook.secret` Fernet work (crypto module, migration 0025, `_engine.py`, settings, requirements) is scope creep relative to \"build 4.19\", but it is a genuine plaintext-at-rest fix and the migration is correct: it widens 128→512 before encrypting, is idempotent via the `fernet.v1:` marker, and reverses in the right order (decrypt, then narrow). No action needed beyond finding 5.\n- `_fernet()` runs a fresh HKDF derivation on every single `encrypt`/`decrypt` call. Harmless today (one webhook detail row, one signing call) but it belongs to performance-reviewer if the encrypted-column pattern spreads — an `@lru_cache`/module-level cache is the obvious fix.\n- The append-only posture on `IntegrationMessage`/`WebhookDelivery` (no create/edit/delete route, no ModelForm, admin registered read-only) is a documented ruling, not a CRUD gap — do not \"complete\" it.\n- `IntegrationEndpoint.set_credential` stores `plaintext[:8]` while the module docstring at line 32 and `admin.py` both describe a \"12-char prefix\", and two docstrings say \"last-4 display\" when it is first-8. Cosmetic doc drift only, not worth a commit on its own.
- **security-reviewer:** Tenant scoping is clean across the whole sub-module — I read every view and found no IDOR. All nine pk lookups use `get_object_or_404(..., tenant=request.tenant)` or go through the tenant-scoped `crud_detail`/`crud_edit`/`crud_delete` helpers (`apps/core/crud.py:136-172`); the detail-page side panels are keyed on `tenant=` *and* `endpoint_id=`/`subscription_id=` rather than relying on the sibling fetch's 404 (`WebhookSubscriptions.py:120-132`, `IntegrationEndpoints.py:218`); `integrationmessage_detail` re-scopes the reverse `ack_message` accessor to the request tenant instead of trusting it; and `IntegrationEndpointForm` defends its four FK dropdowns three ways — `_tenant_qs` returns `.none()` for the tenant-less superuser rather than leaving the queryset unscoped, `_reject_foreign` re-checks at the form boundary against a crafted POST, and `IntegrationEndpoint.clean()` carries the same rule for the seeder/shell, all driven off one `TENANT_SCOPED_FKS` tuple.\n\nAlso verified clean and not reported: every POST form in `templates/scm/integration/**` carries `{% csrf_token %}` (11/11); no `@csrf_exempt`, `|safe`, `mark_safe` or `{% autoescape off %}` anywhere in the new code; no `.raw()`/`.extra()`/`cursor.execute` and no f-string SQL; no `?next=` handling or user-supplied redirect target; no file-upload field (`spec_document` is an FK to an already-uploaded `core.Document`); no unguessable-token or public/unauthenticated route added (L32 holds — all five sidebar bullets target staff pages); every mutating verb is `@require_POST`; the two append-only logs correctly ship no create/edit/delete view, url, form or template and are registered read-only in `admin.py`; and `write_audit_log` on all three hand-rolled save paths records `{"credential": "rotated"}` / `{"signing_secret": "rotated"}` rather than the value.\n\nSSRF posture is deferred rather than exploitable — `endpoint_url` and `target_url` are tenant-editable URLs but there is genuinely no `requests`/`urllib`/`httpx`/`http.client` import anywhere under `apps/scm`, which I confirmed by grep, and the detail template deliberately prints the address as text rather than as a link. The next pass that adds transport must land the allow-list + RFC1918/loopback/link-local/IPv6-ULA block + rebinding re-resolution first; the existing checklist at `apps/crm/views/AutomationWorkflow/_engine.py:78-90` is the reference.\n\nPre-existing and out of scope: `config/settings.py` sets no `MESSAGE_STORAGE`, so Django's default `FallbackStorage` writes flash messages to a client-side cookie before falling back to the session — worth pinning to `django.contrib.messages.storage.session.SessionStorage` app-wide, though it does not change the fix for the Critical finding above (a one-time secret belongs in neither store). `apps/crm/migrations/0025_alter_webhook_secret.py` imports `apps.core.crypto` at module scope, which makes `cryptography==46.0.3` a hard requirement for running any migration — fine, but it needs to be installed before deploy rather than discovered at migrate time.
- **performance-reviewer:** Verified clean, no action needed: every list template loop touches only local columns or an FK the view already joined (`endpoint`, `subscription`, `partner_party`, `logistics_client`, `location` — `Party.__str__` and `Location.__str__` are both plain-column, so no second hop exists); the endpoint-detail `recent_messages` and subscription-detail `recent_deliveries` panels are DB-side slices (`[:10]`) with their FKs pre-joined and are never re-queried as `obj.messages.all` in the template; all filters (including the hand-rolled date windows and the `?status=active`->`is_active` translation) are applied before `Paginator`; both `.count()` calls (IntegrationEndpoints.py:296, WebhookSubscriptions.py:333) are SQL COUNTs; and all 12 new indexes in migration 0033 match the app-wide `(tenant, <dimension>)` reference pattern.

Out of lane / not actionable here:
- The four new `ModelAdmin`s set no `list_select_related`, but every FK in their `list_display` (`tenant`, `endpoint`, `subscription`) is non-nullable, so Django's `ChangeList.apply_select_related` applies a bare `select_related()` automatically. No N+1, and it matches every other admin class in `apps/scm/admin.py`.
- `apps/crm/migrations/0025_alter_webhook_secret.py` uses `.iterator(chunk_size=500)` + batched `bulk_update` for the re-encryption pass — exemplary, no finding.
- `apps/core/crypto.py:_fernet()` runs an HKDF derive on every `encrypt`/`decrypt` call, and `Webhook.secret_masked` now decrypts, so a CRM webhook list does one derive+decrypt per row. It is CPU-microseconds, not queries, and outside 4.19's own pages; `@functools.lru_cache(maxsize=1)` on `_fernet` would make it free if that list is ever profiled.
- `seed_scm.py` adds ~20 explicitly written rows via individual `.create()`/`.save()` calls, not a tight loop — `bulk_create` is not warranted, and the per-row `.save()` calls exist to trigger `TenantNumbered`'s number allocation.
- `WebhookDelivery` has the same `(tenant, status)` + `ORDER BY -triggered_at` shape as finding 5 describes for messages, but the delivery list is a far colder path than the exceptions cockpit; not worth a second schema change in this pass.

For the test-writer agent: a `django_assert_max_num_queries` test per list page would lock these in — endpoint list <=4 (stats, count, page, session/user), message list <=6 (stats, window count, page, endpoints dropdown), delivery list <=6, exceptions <=6 (roll-up, totals, count, page, dropdown), and endpoint detail <=5 with 10 seeded messages (object, panel, aggregate) so a later `select_related` regression on the panel fails loudly.
- **frontend-reviewer:** Verified clean, no finding raised:
- All 23 `{% url 'scm:...' %}` names plus `core:party_detail` / `core:document_detail` resolve to real routes with correct arg counts (`apps/scm/urls/IntegrationApiGateway/*.py`, `apps/core/urls.py` crud factory). No NoReverseMatch risk.
- Every filter widget reflects `request.GET` and every param the templates emit is declared in the view's filter spec (`IntegrationEndpoints.py:143-149`, `WebhookSubscriptions.py:185-190`, etc.), including the deliberate `lifecycle_choices` context key / `lifecycle_stage` GET-param asymmetry.
- All context keys read by the templates are passed by the views; `plaintext_once` (the Critical above) is the only key passed but not read.
- No raw Tailwind colour utilities (so no missing `dark:` variants), no hard-coded left/right margins or padding (RTL-safe), every table is inside `.table-wrap`, every empty list branch is `.empty-state`. No HTMX and no inline JS beyond `confirm()` in these files.
- Filter search inputs use `aria-label` rather than `<label for>`. That is the established house convention across `templates/scm/` (84 of 98 `name=\"q\"` inputs), so I did not flag it — but if the project ever wants visible/associated labels, it is an app-wide change, not a 4.19 one.
- `templates/scm/integration/webhooksubscription/detail.html:245`: the custom-headers sub-table's `{% empty %}` uses a plain `<span class=\"text-muted\">` row instead of `.empty-state`. Reasonable for a 2-column micro-table inside a card; noted, not filed.
- The endpoint list (`integrationendpoint/list.html:397`) renders the admin-only Delete form for every user while the endpoint detail page gates the same action on `is_tenant_admin`. The list's context contract genuinely carries no such key and the template documents the choice; the `@tenant_admin_required` decorator is the real control. Divergence noted for the record only.
- `apps/scm/views/IntegrationApiGateway/IntegrationEndpoints.py:350-352` surfaces the rotated endpoint credential through `messages.success` (the L25 pattern the WebhookSubscription sibling deliberately avoided via the pop-once session key). That is a view-layer/security question, not a template one — flagging it here only so the security lane's finding is not read as a duplicate of mine.
- `.text-danger`, `.text-red`, `.text-ok`, `.text-warn` are present in `static/css/theme.css`, so the suggested fix above uses only existing classes.
- **explorer:** Verified clean and NOT reported as findings: `manage.py check` passes with 0 issues; `makemigrations --check --dry-run` says "No changes detected" (migration 0033 covers all four new models); all four package `__init__.py` re-export blocks (models/forms/views/urls) list every symbol the other layers import, and the `_iag_` urls alias is free of the 18 shipped prefixes; no template ships at a banned flat `<entity>_<page>.html` path — `templates/scm/integration/exceptions.html` at the sub-module root is legal under template rule 6 (it is a report over IntegrationMessage, not any one entity's page); every badge class used is one of the six colour-named literals and every chain ends in an `{% else %}` fallback (L33 clean); all pk-param comparisons use `|stringformat:\"d\"` and no `|slugify` appears anywhere.

Design decisions I confirmed are intentional and did not flag: `IntegrationMessage` and `WebhookDelivery` ship no create/edit/delete view, form, url or template (append-only, stated in five places and matching the MeterReading/PortalActivity posture); `webhookdelivery_list` correctly takes no `LIVE_LINKS` bullet and is reached via `?subscription=<pk>` from the subscription detail page; the `IntegrationApiGateway/` (backend) vs. `integration/` (templates) folder-name asymmetry is the shipped house rule.

Out of my lane but worth another reviewer's eyes: this changeset also converts `crm.Webhook.secret` to Fernet encryption at rest via a new `apps/core/crypto.py`, a new `cryptography==46.0.3` requirement, a new `FIELD_ENCRYPTION_KEY` setting and crm migration 0025 — a cross-app change to a shipped 1.10 model that the security and code-review lanes should assess on its own terms (key-rotation story, migration reversibility, the `decrypt()` pass-through on unmarked legacy rows). My finding #2 is only the one call site the conversion left behind.

`WebhookDelivery.MAX_ATTEMPTS` is derived from `len(DELIVERY_BACKOFF_SECONDS)` (8) rather than typed, and the detail page's `can_retry` adds an `attempt_no < MAX_ATTEMPTS` term the retry view does not check — that is safe rather than a gap, because a direct POST on a spent row falls through `next_backoff_seconds is None` and is marked `exhausted` instead of scheduling a ninth attempt.
- **qa-smoke-tester:** Scope and method: swept all 20 url names of 4.19 plus the `scm:overview` landing page as `admin_acme` through the in-process test client (no dev server was started, per L6/L14). 41 GET assertions in the base pass plus 31 overflow-pagination requests, all 200/302/405 as designed, zero template-comment leaks, zero missing titles or detail identifiers.

Pagination was tested against REAL overflow rather than the seeded 4/6/3/5 rows: I temporarily created 20 endpoints, 20 subscriptions, 40 messages and 40 deliveries for Acme so page 2 and page 3 held actual rows, then verified the page-link hrefs preserve the active filters (`?status=connected&category=erp&page=2`) and that following them still renders the filtered rows. All probe rows were deleted in a `finally` block and the tenant counts verified back at 4/6/3/5.

One residual data mutation I did NOT revert: `webhooksubscription_rotate_secret` was POSTed once against the seeded `WHK-00003`, so that row's `signing_secret_prefix`/`signing_secret_hash` now hold a freshly minted marker rather than the seeder's. Harmless (both values are synthetic and nothing reads them yet), and `seed_scm` is idempotent-skip so it will not restore them; `seed_scm --flush` would. Flagging it only so the next session is not surprised by a prefix that differs from the seeder source.

Pre-existing and out of scope: `temp/` already contains ~170 throwaway scripts from earlier sessions (gitignored). `manage.py migrate` emits the standing `mysql.W002` MariaDB-strict-mode warning on this XAMPP install — unrelated to this changeset.

Also confirmed but outside the strict lane brief, since they are cheap runtime facts: non-admin `ops_acme` gets 200 on all eleven read pages and 403 (not 500, not a silent mutation) on all four `@tenant_admin_required` POSTs with rows intact; the tenant-less superuser gets 200 empty lists and a 302 out of both create views rather than an orphan-row 500; and a duplicate subscription name returns a rendered field error rather than the uncaught `IntegrityError` the form docstring warns about.

## Done well

- **code-reviewer:** Every view module pins an exhaustive per-page context-var contract in its docstring (e.g. `WebhookDeliveries.py:44-61` naming `object_list` / `subscriptions` / `status_choices` / `date_from` / `date_to` / `stats` and the exact `can_retry` / `next_backoff_seconds` / `max_attempts` keys) — and it held: I diffed every key used in all nine new templates against every view's `extra_context` and found zero mismatches, all 30 `{% url %}` names resolve to real patterns, every pk filter uses `|stringformat:"d"`, and all 28 querysets/`get_object_or_404` calls in the sub-module carry `tenant=request.tenant`.
- **security-reviewer:** The credential-marker design is structurally sound rather than promissory: `credential_prefix`/`credential_hash` and `signing_secret_prefix`/`signing_secret_hash` are `editable=False` on the models, so no `Meta.fields` list can ever pull them into a ModelForm and ship them back in an edit render's `value="..."` (L20/L22) — and the changeset went further by fixing a genuine pre-existing plaintext-at-rest leak in `crm.Webhook.secret`, adding `apps/core/crypto.py` (Fernet with an HKDF-derived fallback and a `fernet.v1:` marker that makes both the data migration and every `save()` idempotent), migration `apps/crm/migrations/0025_alter_webhook_secret.py`, and correctly reasoning that a key you must HMAC with needs encryption at rest rather than the one-way hash used where only equality matters.
- **performance-reviewer:** The chained-`__str__` FK hop was actually handled rather than missed: `integrationendpoint_list` (IntegrationEndpoints.py:122-123) select_relates `logistics_client__party` because `LogisticsClient.__str__` resolves `self.party`, and every stat block in the sub-module is one `aggregate()` with conditional `Count(..., filter=Q(...))` over the unfiltered tenant queryset instead of one query per stat card — 3-4 flat queries per list page, with no per-row FK, no `.count` on a related manager and no `len(qs)` anywhere in the loops.
- **frontend-reviewer:** Design-system fidelity is the best I've seen in this repo: every one of the 241 modifier classes across the 11 new templates is a real colour-named theme.css class (badge-amber/green/info/muted/red/slate and stat-icon blue/green/orange/purple/slate only — zero `-success`/`-danger`/`-warning`, zero `stat-icon amber|red`), so L33 is fully clean on its fourth exposure; there is not a single `{# ... #}` comment anywhere in the changeset (every note is `{% comment %}...{% endcomment %}`), so L2 is clean too; and all six status/direction/format badge chains switch on the exact strings in `apps/scm/models/IntegrationApiGateway/_choices.py` and end in an `{% else %}` that still prints `get_FIELD_display`. Pagination is the shared L9-safe `partials/pagination.html` on all four paginated pages (including the hand-rolled exceptions view, which correctly routes through `apps/core/crud.py::paginate` so `page_obj.window` exists), every `<td colspan>` matches its header count exactly, every nullable FK is wrapped in an `{% if fk %}` before anything is read off it (L10), and the one pk filter per page uses `|stringformat:\"d\"` while every vocabulary filter uses plain string equality — `|slugify` appears nowhere.
- **explorer:** The urls -> views -> templates name contract is airtight and mechanically verifiable: all 23 new `scm:` route names reverse (including the four category-pinned `integrationendpoint_*_list` bullets that share one view via Django's extra-options dict), all five `LIVE_LINKS[\"4.19\"]` targets resolve to live staff pages, all 11 templates compile, and every top-level variable each template reads (`active_category`, `lifecycle_choices` vs. the `lifecycle_stage` GET param, `error_groups`, `message_stats`, `delivery_stats`, `can_reprocess`, `can_retry`, `next_backoff_seconds`, `max_attempts`, `ack_message`, `date_from`/`date_to`) is present in its view's context dict — the deliberate `lifecycle_choices`/`lifecycle_stage` asymmetry is pinned identically on both sides.
- **qa-smoke-tester:** The context-var contract was actually honoured end-to-end, and it shows in the one place a status-only smoke test cannot see: every header stat block matched its DB aggregate exactly, including the per-category scoping on the four extra-options routes (`/integration-endpoints/{erp,ecommerce,iot,edi}/` each rendered 1/1/0/0/1-style figures for their own category rather than the tenant-wide 4/3/1/0/4), and the `lifecycle_choices` key / `lifecycle_stage` GET-param split that the view docstring explicitly pins was wired correctly on both halves rather than silently blanking the widget.
