# Review findings — scm 4.17 Third-Party Logistics (3PL) Management

Range: `def4dd4d570fa459e0c7d8a9c41f483fcd9b7ad2...HEAD` · Generated: 2026-08-14
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 4 |
| Minor | 12 |
| **Total (deduped)** | **16** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 4 |
| security-reviewer | 1 |
| performance-reviewer | 3 |
| frontend-reviewer | 5 |
| explorer | 3 |
| qa-smoke-tester | 0 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Important

### I1 — `apps/scm/forms/ThirdPartyLogistics/LogisticsClients.py:141`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** The `parent_client` <select> queryset is built from `_tenant_qs(LogisticsClient, tenant)` with no `select_related("party")`, and `_keep_current` (line 66) rebuilds from `model._default_manager`, which would drop one anyway — so rendering the client form calls `LogisticsClient.__str__` (`f"{self.code} · {self.party}"`) once per option and fires one query per client in the workspace (1 + N on every create AND edit render of a mainline CRUD page). The three sibling 4.17 forms all guard exactly this (`ClientRateCards.py:133-134`, `ClientSlas.py:114`, `ClientBillingRuns.py:62`); this field is the one that was missed.
- **Fix:** Chain the join onto the result so it survives both `_keep_current` branches: `self.fields["parent_client"].queryset = _keep_current(parents, getattr(instance, "parent_client_id", None)).select_related("party")`. Optionally also give `_keep_current` (line 51-67) a `select_related` passthrough so the next caller cannot repeat this. Hand the test-writer a `django_assert_max_num_queries` check on GET `scm:logisticsclient_create` with ~10 seeded clients.
- **Status:** [x] fixed — perf(scm): join party onto the 3PL parent_client dropdown so the client form stops firing one query per option

### I2 — `apps/scm/views/ThirdPartyLogistics/ClientBillingRuns.py:202`

- **Found by:** code-reviewer
- **Problem:** `clientbillingrun_delete` is `@login_required` only and its sole status guard is `status == "invoiced"`, so any ordinary tenant member can hard-delete an **approved** run — destroying the `approved_by`/`approved_at` signature that `clientbillingrun_approve` requires `@tenant_admin_required` to create, plus every derived charge line — even though `ClientBillingRun.void()` explicitly refuses an approved run and `apps/scm/views/__init__.py:534` states "an approved run is not deleted".
- **Fix:** Refuse the delete outside the working states: replace the `if obj.status == "invoiced"` branch with `if obj.status not in ClientBillingRun.VOIDABLE_STATUSES:` and flash a message steering to Void (approved) / Accounting (invoiced); then change `"can_delete": obj.status != "invoiced"` at ClientBillingRuns.py:258 to `obj.status in ClientBillingRun.VOIDABLE_STATUSES` so the detail page stops offering a button its own prose at templates/scm/3pl/clientbillingrun/detail.html:469 already claims "disappears at the same moment" as Void. If deleting an approved run must stay possible, gate that case with `@tenant_admin_required` instead — but do not leave it open to a member.
- **Status:** [x] fixed — security(scm): refuse deleting an approved, invoiced or void billing run (+ fix(scm): stop the billing-run list offering Delete on approved and void runs)

### I3 — `apps/scm/views/ThirdPartyLogistics/ClientRateCards.py:206`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** The rate-card detail page's billing-run panel fetches runs with `select_related("client")` only, but `templates/scm/3pl/clientratecard/detail.html:399` renders `{% if run.invoice %}` inside the `{% for run in billing_runs %}` loop — `invoice` is an unjoined nullable FK, so every run that HAS been invoiced fires its own SELECT (1 + up to 25 queries per page at MAX_PANEL_ROWS=25, and it is the fully-billed cards — the busiest ones — that pay the whole 25).
- **Fix:** Add `invoice` to the join at line 206: `billing_runs = list(obj.billing_runs.select_related("client", "invoice").order_by("-period_end", "-id")[:MAX_PANEL_ROWS])`. (The template only needs the boolean, so `{% if run.invoice_id %}` at detail.html:399 would also be zero-query — but joining in the view is the safer fix because it also covers anything else the panel is later asked to print.) Worth a `django_assert_max_num_queries` test on `scm:clientratecard_detail` seeded with ~5 invoiced runs against one card.
- **Status:** [x] fixed — perf(scm): join invoice into the rate-card billing-run panel so the Drafted chip stops firing a query per invoiced run

### I4 — `templates/scm/overview.html:370`

- **Found by:** explorer
- **Lesson:** L43
- **Problem:** The SCM module landing page has one card per built sub-module (Procurement 4.1 through Customer Portal 4.16, 15 cards) but no card for 4.17, so every 3PL page — the client register, rate cards, billing runs, SLAs and both computed reports — is reachable only from the sidebar and not from the module's own entry point.
- **Fix:** Insert a new `<div class="card">` block immediately after the Customer Portal card's closing `</div>` (line 369) and before `{% endblock %}` (line 370), copying the Customer Portal card's exact markup: `<div class="card-header"><h2 class="card-title">Third-Party Logistics</h2></div><div class="card-body"><div class="page-actions">` containing six `<a class="btn btn-outline">` links — `{% url 'scm:logisticsclient_list' %}` (icon building-2, "Logistics Clients"), `{% url 'scm:clientratecard_list' %}` (scroll-text, "Rate Cards"), `{% url 'scm:clientbillingrun_list' %}` (receipt, "Billing Runs"), `{% url 'scm:clientsla_list' %}` (gauge, "SLAs"), `{% url 'scm:client_inventory_report' %}` (boxes, "Client Inventory"), `{% url 'scm:client_space_report' %}` (warehouse, "Warehouse Rental") — the same six links and icons already used in the header of templates/scm/3pl/logisticsclient/list.html lines 62-66. Template-only change; scm:overview needs no new context. Use a targeted Edit, never a rewrite (L43).
- **Status:** [x] fixed — feat(scm): add the 4.17 Third-Party Logistics card to the module overview

## Minor

### M1 — `apps/scm/forms/__init__.py:394`

- **Found by:** code-reviewer
- **Problem:** The 4.17 re-export comment asserts "`ClientRateCard.status` is absent — a card moves draft -> active -> superseded through the `activate` / `supersede` verbs", but `ClientRateCardForm.Meta.fields` at apps/scm/forms/ThirdPartyLogistics/ClientRateCards.py:119 DOES include `status`, and templates/scm/3pl/clientratecard/form.html:123 renders it; the comment is the stated rationale for the whole audit story, so a future engineer will either trust a false invariant or "fix" the form to match it.
- **Fix:** Correct the comment to say `status` IS on the header form (deliberately — `clientratecard_edit` refuses any card outside `EDITABLE_RATE_CARD_STATUSES` and `ClientRateCard.clean()` re-runs the overlap guard on that write path), and that only `ClientBillingRun.status` and `ClientSLA.status` are absent. The identical false claim appears at apps/scm/views/__init__.py:528 and apps/scm/management/commands/seed_scm.py:4984 and :5165 — fix all four in the same pass.
- **Status:** [x] fixed — docs(scm): corrected in all three files (forms/__init__.py, views/__init__.py, seed_scm.py) — ClientRateCard.status IS on the header form deliberately

### M2 — `apps/scm/forms/ThirdPartyLogistics/ClientSlas.py:119`

- **Found by:** code-reviewer
- **Problem:** On the unbound CREATE form `_client_id()` returns `self.instance.client_id` (None), so the `scope_location` queryset collapses to `Q(owner_client__isnull=True) | Q(owner_client_id=None)` — i.e. unowned bins only — which makes it impossible to create an SLA scoped to one of the chosen client's OWN dedicated locations in a single pass, even though `ClientSLA.clean()` explicitly permits `owner_client_id == client_id`. The option only appears after the row is saved and re-opened for edit.
- **Fix:** On the unbound create path, offer every tenant location that is either unowned or dedicated to ANY client (`Q(owner_client__isnull=True) | Q(owner_client__isnull=False)` is just "all", so simply skip the owner narrowing when `_client_id()` is None) and let `ClientSLA.clean()`'s cross-client guard reject a bin belonging to a different client — the error message it already renders names the location and the reason.
- **Status:** [x] fixed — fix(scm): let a new SLA be scoped to the client's own dedicated bin in one pass

### M3 — `apps/scm/models/InventoryManagement/Items.py:148`

- **Found by:** performance-reviewer
- **Problem:** 4.17 makes `Item.owner_client` a hot tenant-scoped filter dimension — `client_inventory_report` runs `Item.objects.filter(tenant=..., owner_client_id__in=[...])` and `filter(tenant=..., owner_client__isnull=True).count()` (Reports.py:194, 247) and `LogisticsClient.sku_count()` reads it per client — but the model's `Meta.indexes` was not extended, so the low-selectivity `owner_client IS NULL` count falls back to scanning the tenant's items. This is the same shape the app-wide reference pattern already covers on this exact model with `(tenant, is_active)` and `(tenant, category)`.
- **Fix:** Add `models.Index(fields=["tenant", "owner_client"], name="scm_item_tnt_owner_idx")` to `Item.Meta.indexes` and generate the follow-up migration (0030 — 0029 is already claimed by this build). This is an app-wide-pattern pass, not a 4.17 fork; do the identical `(tenant, owner_client)` index on `Location.Meta.indexes` (apps/scm/models/InventoryManagement/Locations.py:84) in the same migration, since `client_space_report` filters it the same way.
- **Status:** [~] skipped — real, but needs a schema migration (0030) this session was told not to claim; a concurrent session may hold the next number. See Notes.

### M4 — `apps/scm/views/ThirdPartyLogistics/ClientBillingRuns.py:577`

- **Found by:** security-reviewer
- **Problem:** `clientbillingrunline_delete` commits its `write_audit_log` row BEFORE opening the `transaction.atomic()` that actually deletes the line, so if `line.delete()` or `run.recalc_amounts()` raises, the delete rolls back but an immutable AuditLog row remains claiming a billing charge was removed — a false entry in the money trail.
- **Fix:** Move the audit call inside the atomic block, exactly as the sibling `clientratecardline_delete` (ClientRateCards.py:527-534) already does:

```python
    description, amount = line.description, line.amount
    with transaction.atomic():
        write_audit_log(request.user, line, "delete", {
            "run": run.number, "description": description, "amount": str(amount),
        }, tenant=request.tenant)
        line.delete()
        run.recalc_amounts()
```

Grep for the same shape across the family (two lessons share L28 — this is the pattern-clone one): `rg -n "write_audit_log\(.*\"delete\"" -A 4 apps/scm/views | rg -B2 "with transaction.atomic"` and, more directly, `rg -n "write_audit_log" -A 3 apps/*/views | rg "^.*-\s*with transaction.atomic"` — any hand-rolled delete where the audit line precedes the `with` needs the same swap.
- **Status:** [x] fixed — fix(scm): write the billing-run line delete audit row inside the transaction

### M5 — `apps/scm/views/ThirdPartyLogistics/ClientSlas.py:231`

- **Found by:** explorer
- **Problem:** `clientsla_list` passes `not_measured_note` and its own docstring (line 192) states the page MUST print it, but templates/scm/3pl/clientsla/list.html never references the key — the contracted caveat explaining why a figure is missing is silently dropped and the context entry is dead.
- **Fix:** Either render it in templates/scm/3pl/clientsla/list.html — a `<div class="form-help">{{ not_measured_note }}</div>` in the card body beside the "Not measured" cell (line 252) or inside the empty-state block (line 298) — or delete the `"not_measured_note": NOT_MEASURED_NOTE,` entry from extra_context and drop the corresponding sentence from the view docstring at line 192. Do not leave the docstring claiming a key the page ignores.
- **Status:** [x] fixed — fix(scm): print the SLA not-measured caveat on the list page

### M6 — `apps/scm/views/ThirdPartyLogistics/ClientSlas.py:380`

- **Found by:** code-reviewer
- **Problem:** `credit_note` and `not_measured_note` are passed into the SLA detail context (and `not_measured_note` into the list context at line 231) and the view docstrings say both "are prose the page must print", but neither templates/scm/3pl/clientsla/detail.html nor list.html renders either variable — each page hand-wrote its own equivalent wording, so the `CREDIT_NOTE`/`NOT_MEASURED_NOTE` constants and the on-screen text are now two copies free to drift.
- **Fix:** Render `{{ credit_note }}` inside the "Service credit implied by this SLA" card body (templates/scm/3pl/clientsla/detail.html, near line 405) and `{{ not_measured_note }}` beside the not-measured state on both the detail (near line 116) and the list; alternatively delete the two constants and their context keys and strike the "must print" claims from the docstrings. Do not leave the two out of sync.
- **Status:** [x] fixed — refactor(scm): drop the dead credit_note and not_measured_note keys from the SLA detail context (list page now prints not_measured_note; see M5)

### M7 — `apps/scm/views/ThirdPartyLogistics/ClientSlas.py:380`

- **Found by:** explorer
- **Problem:** `clientsla_detail` passes `credit_note` and `not_measured_note` (lines 380-381) as prose the page is contracted to print, but templates/scm/3pl/clientsla/detail.html references neither key, so both are dead context.
- **Fix:** In templates/scm/3pl/clientsla/detail.html add `{{ credit_note }}` to the card body of the "Service credit implied by this SLA" panel (below line 421) and `{{ not_measured_note }}` to the measurement panel's unmeasured branch; alternatively remove both keys from the render dict at lines 380-381 and their mentions from the view docstring. The template already states the equivalent meaning in its own words, so removing the keys is the smaller change — pick one and keep docstring and code in step.
- **Status:** [x] fixed — resolved together with M6: both detail keys removed and the docstring claim struck

### M8 — `templates/scm/3pl/client_space_report.html:228`

- **Found by:** frontend-reviewer
- **Problem:** `{{ row.days_to_expiry|pluralize }}` is applied to the raw NEGATIVE integer, so a contract that ended exactly one day ago renders "Ended 1 days ago" — Django's pluralize returns the plural suffix for any value != 1, and -1 != 1.
- **Fix:** Reuse the already-absolutised value for the pluralize call: change `day{{ row.days_to_expiry|pluralize }}` to `day{{ row.days_to_expiry|floatformat:0|cut:"-"|pluralize }}` (the `floatformat:0` must stay ahead of `cut`, since `cut` calls `.replace()` and would raise on a bare int).
- **Status:** [x] fixed — fix(scm): pluralize the absolutised day count on the warehouse rental report

### M9 — `templates/scm/3pl/clientratecard/detail.html:319`

- **Found by:** frontend-reviewer
- **Problem:** The per-line Delete button is `class="btn-icon"` without the `danger` modifier, so the destructive red hover state defined by `.btn-icon.danger:hover` in theme.css never applies and the control reads as a neutral action.
- **Fix:** Change `<button class="btn-icon" type="submit" title="Delete line"` to `<button class="btn-icon danger" type="submit" title="Delete line"`.
- **Status:** [x] fixed — style(scm): give the rate-card line Delete button the danger modifier

### M10 — `templates/scm/3pl/clientratecard/detail.html:345`

- **Found by:** frontend-reviewer
- **Problem:** The "Lines locked" footer is gated on `{% if not can_add_line %}`, but the view sets `can_add_line = obj.is_editable and len(lines) < MAX_RATE_CARD_LINES` — so a DRAFT card that has hit the 200-line cap prints the self-contradictory sentence "This card is draft, and lines can only be added or changed while a card is still a draft" and never explains that the real blocker is the cap.
- **Fix:** Gate the lock message on the status rule it actually describes and give the cap its own branch: change `{% if not can_add_line %}` to `{% if not can_edit %}` and add `{% elif not can_add_line %}` before the existing `{% else %}`, with copy naming the ceiling, e.g. `<span class="badge badge-amber">Line limit reached</span> This card already carries {{ line_count }} lines, the most a single tariff may hold. Remove a line, or raise a new version.`
- **Status:** [x] fixed — fix(scm): split the rate-card lines footer into a status-lock branch and a line-cap branch

### M11 — `templates/scm/3pl/clientratecard/list.html:195`

- **Found by:** frontend-reviewer
- **Problem:** The row Delete button is `class="btn-icon"` without the `danger` modifier, so it loses the red destructive hover affordance (`.btn-icon.danger:hover`) that every other delete button in the app has — it hovers brand-blue like a View or Edit action.
- **Fix:** Change `<button class="btn-icon" type="submit" title="Delete"` to `<button class="btn-icon danger" type="submit" title="Delete"`, matching `templates/scm/3pl/logisticsclient/list.html:254` and `clientbillingrun/list.html:218` (72 of the 74 delete icon buttons in templates/scm use `btn-icon danger`; the only bare ones are non-destructive verbs like Acknowledge/Release).
- **Status:** [x] fixed — style(scm): give the rate-card row Delete button the danger modifier

### M12 — `templates/scm/3pl/clientsla/form.html:330`

- **Found by:** frontend-reviewer
- **Problem:** The read-only evidence card says "Changing the target below does not restate what was already measured", but this card is rendered AFTER the "The target and how it is judged" card (lines 105-210) — the target fields are above it, so the direction word points the reader the wrong way.
- **Fix:** Change "Changing the target below" to "Changing the target above" in the sentence at line 330.
- **Status:** [x] fixed — fix(scm): point the SLA evidence-card caveat at the target fields above it

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-fixer (fix wave, 2026-08-14):** **M3 is deferred, not dismissed — it needs an app-wide index
  pass in its own change.** The finding is real: `Item.Meta.indexes` and `Location.Meta.indexes` carry
  no `(tenant, owner_client)` entry, so `client_inventory_report`'s
  `filter(tenant=..., owner_client__isnull=True).count()` and `client_space_report`'s owner filter
  scan the tenant's rows. It is NOT applied here because it is the only finding in the file that
  changes the schema, and migration `0030` was not this session's to claim (0029 is committed; a
  concurrent session may be holding the next number). **Recommended follow-up, as one change:** add
  `models.Index(fields=["tenant", "owner_client"], name="scm_item_tnt_owner_idx")` to
  `apps/scm/models/InventoryManagement/Items.py` and
  `models.Index(fields=["tenant", "owner_client"], name="scm_loc_tnt_owner_idx")` to
  `apps/scm/models/InventoryManagement/Locations.py`, then generate ONE migration covering both after
  agreeing the number. Per L18 this is a reference-pattern pass across the two shared masters, not a
  4.17 fork — do not add it to one model only.

- **code-fixer (fix wave, 2026-08-14):** **M4's clone family was checked and 4.17 was the only
  instance.** The finding asked for a grep across the app for `write_audit_log(..., "delete")`
  preceding rather than inside a `with transaction.atomic()`. Thirteen scm view modules write a
  delete audit row; only four of them wrap the delete in an explicit transaction
  (`CustomerPortal/PortalOrderInquiries.py`, `OrderManagement/SalesOrderAllocations.py`,
  `ThirdPartyLogistics/ClientBillingRuns.py`, `ThirdPartyLogistics/ClientRateCards.py`), and of those
  only `ClientBillingRuns.py` had the audit call outside the block. No app-wide pass is needed.

- **code-fixer (fix wave, 2026-08-14):** **I2's fix extended to one file the finding did not name.**
  `templates/scm/3pl/clientbillingrun/list.html` gated its row Delete on `obj.status != 'invoiced'`,
  the same rule the view was refusing on, so tightening only the view and the detail page would have
  left the list offering a button that now bounces. The row gate and the file's header docstring were
  brought into line in a separate commit.

- **code-reviewer:** VERIFIED CLEAN (no action needed): every new model carries a tenant FK except the two deliberately tenant-less child tables (`ClientRateCardLine`, `ClientBillingRunLine`), both of which are reached only through `rate_card__tenant=request.tenant` / `run__tenant=request.tenant`; every queryset, aggregate, resolver and report in the diff is tenant-scoped (I traced all nine SLA resolvers, all eight billing-quantity resolvers and both report views); migration 0029 matches the models field-for-field including the three `unique_together` tuples and five indexes, and it is purely additive (no `RemoveField`/`DeleteModel`); every `{% url %}` name in `templates/scm/3pl/**` resolves against a real `path(name=...)` (including the cross-app `accounting:invoice_detail`, `core:party_detail`, `core:document_detail`); all four list pages use the L9-safe `partials/pagination.html`; all pk filters use `|stringformat:\"d\"` and none uses `|slugify`; all GET int params go through `as_db_int`/`crud_list`'s `is_int` leg and the two date params through a `try/except ValueError` parse; every re-export block (`models`/`forms`/`views`/`urls` `__init__.py`) names every new symbol; the seeder is guarded by a per-tenant `LogisticsClient.exists()` check and its `--flush` block deletes the drafted AR invoices before the runs and the runs before the PROTECTed rate cards. I also compiled every template under `templates/scm/3pl/` with `get_template()` — zero syntax failures.\n\nPRE-EXISTING / OUT OF SCOPE: `apps/scm/models/_base.py:44` `q2()` clamps to `Decimal(\"9999999999.99\")` (a `DecimalField(14,2)` ceiling) while 4.17's `subtotal`/`minimum_adjustment`/`total`/`amount` are `(18,2)` — a run total above ~10 billion would be silently clamped rather than stored. App-wide helper behaviour, not introduced here, and unreachable in practice given `MAX_RUN_LINES=500`.\n\nSCOPE: the range also contains three `.claude/workflows/*.js` one-line fixes (`meta.whenToUse` must be a string literal) that are unrelated to 4.17 — harness repairs needed to run the wave itself, so noted rather than flagged.\n\nPHASE STATE: no tests and no `SKILL.md`/`README.md` update in this range, which is expected — Phases 6 and 7 come after this review wave.\n\nSUGGESTED TESTS (route to test-writer):\n- `apps/scm/tests/test_3pl_security.py` — POST `scm:clientbillingrun_delete` as a non-admin member against a run in `approved` status and assert the run still exists (this is finding 1's regression test); plus cross-tenant IDOR 404s on `clientratecardline_edit`/`clientbillingrunline_edit`, which are resolved only through the parent's tenant.\n- `apps/scm/tests/test_3pl_models.py` — `ClientBillingRun.calculate()` twice in a row leaves manual lines untouched and regenerates derived ones; `ClientSLA.recompute()` run twice over the same window increments `breach_count` exactly once; `recompute()` on an empty window writes `status=\"no_data\"` and leaves `last_measured_value` NULL (never 0).\n- `apps/scm/tests/test_3pl_forms.py` — `ClientRateCardForm` refuses a second `active` card whose effective range overlaps an existing one and names it; `ClientSLAForm` refuses a `pct` metric saved with `unit=\"hours\"`; `ClientBillingRunForm` refuses a rate card belonging to another client.\n\nROUTING:\n- security-reviewer: the approve/delete privilege asymmetry in finding 1 (`approve` is `@tenant_admin_required`, deleting the approval is not).\n- frontend-reviewer: finding 3 (two drifting copies of the credit / not-measured prose) and finding 4's create-form dropdown gap are as much UX as correctness.\n- performance-reviewer: nothing outstanding — the list views annotate instead of calling the per-row derived methods, and every detail panel is a DB-side slice with the reasoning written next to it.
- **security-reviewer:** Verified clean, no action needed (recorded so the fixer does not re-derive them):

- **Cross-tenant IDOR**: every one of the ~30 `.objects.` entry points across the five 4.17 view modules is tenant-scoped (`apps/scm/views/ThirdPartyLogistics/*.py`); every `get_object_or_404` passes `tenant=request.tenant`; the two report pages filter `tenant=tenant` on `LogisticsClient`/`StockMove`/`Item`/`Location`/`ItemCategory` and `?client=` narrowing happens *inside* the tenant-scoped queryset, so a foreign pk yields an empty page rather than a leak. The model-side resolvers (`ClientBillingRuns.py:414,553,564,574,585,602`, `ClientSlas.py:663,670,693,724,783`, `_client_shipments`) all carry `tenant=`/`tenant_id=`.
- **Form tenant surface**: every FK dropdown is re-scoped from the model (`_scope_to_tenant` / `_tenant_qs` / `_scope`), falls to `.none()` for a tenant-less caller instead of filtering on NULL, and — the part that actually holds against a crafted POST — is additionally re-checked in `clean()` via `_reject_foreign(self, cleaned, Model.TENANT_SCOPED_FKS)` plus the model's own `clean()`. `ClientRateCardLineForm.clean` anchors on `rate_card.tenant_id` (the route-resolved parent) rather than `form.tenant`, which is the correct authority for a tenant-less child.
- **Mass assignment**: all four `Meta.fields` are explicit whitelists. `ClientBillingRun.status/subtotal/minimum_adjustment/total/calculated_at/approved_at/approved_by/invoice` and `ClientSLA`'s eight measurement columns are `editable=False` AND off the whitelists; `LogisticsClient.onboarded_on`/`last_synced_at` likewise (L22 respected). `ClientBillingRunLine.is_manual` is FORCED in the view, not posted.
- **Secrets (L20/L25)**: no credential/token/key/hash column exists anywhere in 4.17 — `client_system`/`edi_partner_id`/`edi_qualifier` are non-secret partner identifiers, and no `messages.success` flashes a generated value.
- **CSRF / POST-only / status guards**: every `<form method="post">` in `templates/scm/3pl/` carries `{% csrf_token %}`; all eight destructive/ladder verbs are `@require_POST`; every status guard is enforced in the view (`_refuse_locked`, `EDITABLE_RUN_STATUSES`, `obj.status != "draft"`), and the templates gate the matching button on the identical `can_*` flag. `approve`/`draft_invoice` are `@tenant_admin_required` (which itself wraps `@login_required`) and the detail template wraps *both* buttons in `{% if request.user.is_superuser or request.user.is_tenant_admin %}`, so no member is shown a 403 button.
- **XSS / CSS injection / SQLi / open redirect / uploads**: no `|safe`, `mark_safe`, or `{% autoescape off %}`; no user value in an inline `style=`; the `onclick="return confirm(...)"` strings interpolate only auto-numbers, choice labels and integers; no `.raw()`/`.extra()`/`cursor.execute`; no `?next=`/`redirect(request.…)`; no `@csrf_exempt`; no new upload field. The one dynamic href (`client_inventory_report.html:253`) applies `|urlencode`.
- **Cross-record integrity**: `ClientBillingRun.clean()` refuses a `rate_card` whose `client_id` differs from the run's client — the same-counterparty leg the checklist calls for — and `draft_invoice()` builds the `accounting.Invoice` with `tenant=self.tenant`, `party=client.party`.

Observations that are NOT actionable for this sub-module:

1. `clientratecard_activate` / `_supersede` are `@login_required` only, not tenant-admin gated. Gating them alone would be theatre: `status` is deliberately on `ClientRateCardForm`, so `clientratecard_edit` is an equivalent draft→active path, and `ClientRateCard.clean()` enforces the overlap guard on both. It also matches the shipped precedent (`catalog_activate`, `contract_activate`, `laborstandard_activate`). A decision to gate tariff activation is an app-wide policy change, not a 4.17 fix.
2. The four `ClientBillingRun` verbs (`ClientBillingRuns.py:388, 418, 443, 466`) write their audit rows *after* the model method's own transaction has committed. This is the weaker direction of the same class as the reported finding (a lost trail rather than a false one) and matches how most existing scm verbs are written; folding it in would touch four call sites for no security gain.
3. `clientsla_recompute_all` (`ClientSlas.py:426`) lets any authenticated member start a 200-row measurement sweep, each row costing several aggregates over StockMove/SalesOrder/Shipment. It is POST+CSRF, capped, and per-row atomic — the same posture as 4.15's detector — so this is an app-wide throttling question, not a 4.17 defect.
4. `Item.owner_client` / `Location.owner_client` were added to `ItemForm`/`LocationForm` whitelists with no explicit `clean()` re-check. That is safe here because `TenantModelForm.__init__` (apps/core/forms/_common.py:52-55) filters the `ModelChoiceField.queryset` by tenant, and `ModelChoiceField.to_python` validates the posted pk *against that queryset* — so a foreign client pk is rejected as "Select a valid choice", not merely hidden. The `tenant is None` branch is unreachable because `crud_create` refuses tenant-less users and `crud_edit`'s `get_object_or_404(..., tenant=None)` cannot match a NOT-NULL column.
- **performance-reviewer:** App-wide / pre-existing, not in the fix queue:

1. Django admin changelists (apps/scm/admin.py:67, and the ClientBillingRun/ClientSLA registrations below it) put `client` in `list_display`. Django auto-applies a depth-1 `select_related()` when list_display holds a related field, so `client` is joined but `client__party` is not — and `LogisticsClient.__str__` walks `party`, so each changelist row costs one extra query. `list_select_related = ("client", "client__party")` fixes it. Left out of the queue: the Django admin is a staff-only fallback path here, and every other scm admin has the same shape.

2. `ClientSLA.Meta.ordering = ["client__code", "metric", "id"]` (ClientSlas.py:217) is a cross-relation default ordering: every SLA list page joins LogisticsClient and filesorts on its `code`, which no `(tenant, ...)` index can serve. Fine at demo/realistic volumes, but note that any future `.annotate(Count(...))` on that queryset will drag `client.code` into the GROUP BY.

3. Two write paths save child rows one at a time rather than `bulk_create`: `ClientBillingRun.calculate()` (ClientBillingRuns.py:328, ≤200 derived lines) and `draft_invoice()` (line 724, ≤501 InvoiceLine inserts). Both are blocked from bulking by design — `ClientBillingRunLine.save()` is the sole writer of `amount` and `InvoiceLine.save()` the sole writer of `line_total` — and both are already inside `transaction.atomic()`. Cold POST verbs, correctly left alone.

4. The report filter dropdowns (`_client_qs` / `_category_qs` / `_location_qs`, Reports.py:65-93) are unbounded querysets, so a tenant with thousands of bins renders thousands of `<option>`s on `client_inventory_report`. That is the shipped `views/_helpers.py` idiom across the whole app, not a 4.17 regression.

5. The seeder's 4.17 block (`_seed_3pl_tenant`, seed_scm.py:4995+) is a bounded fixture — three clients, three tariffs, three runs, five SLAs — behind an `exists()` guard, and it drives `calculate()`/`approve()`/`draft_invoice()`/`recompute()` through the real code paths. No tight per-row `.save()` loop worth bulking.

6. No `len(qs)` / `if qs:` misuse anywhere in the changeset: every `len()` is on an already-materialised list, and the `_panel()` fetch-N+1 idiom (LogisticsClients.py:83-93) correctly skips the COUNT round-trip when the cap did not bite.
- **frontend-reviewer:** Verified and clean, so recorded here rather than as findings: (1) no multi-line `{# #}` comments anywhere in the changeset — `{% comment %}`/`{% endcomment %}` counts balance in all 16 files; (2) every static class token used resolves against theme.css, including the compound `.stat-icon.blue/.green/.orange/.purple/.slate` (no `amber`/`red` invented — `clientsla/list.html:120` and `logisticsclient/list.html:104` correctly route both attention states to `orange` and separate them by label); (3) all four lists carry a GET filter bar reflecting `request.GET`, an eye/pencil/trash-2 Actions column, POST+`{% csrf_token %}`+confirm deletes, an `.empty-state` `{% empty %}` branch, and `{% include "partials/pagination.html" %}` (which is the L9-guarded, param-preserving partial); (4) every pk filter compares with `|stringformat:\"d\"` and no `|slugify` appears outside explanatory comments; (5) all 44 `{% url %}` names resolve against `apps/scm/urls/`, `apps/core/urls.py`'s `crud()` factory and `apps/accounting/urls/`; (6) all four detail pages carry an Edit / POST-Delete / Back-to-list Actions card; (7) every Meta.fields name on all six forms is rendered through `partials/form_field.html`, which pairs `<label for>` with `field.id_for_label`. App-wide / pre-existing, not actionable here: `.text-right` in theme.css is a physical (LTR) alignment with no logical-property or `[dir=rtl]` counterpart, so every right-aligned money/quantity column in the app — including these — will align wrongly under RTL; and list filter bars use `aria-label` on the search input and selects instead of a visible `<label for>`, which is the established house pattern across all of templates/scm and is applied consistently here (the two report pages do use proper `<label for>`+`id` pairs).
- **explorer:** Verified read-only; no files edited, no git writes. Reverse-check run under DJANGO_SETTINGS_MODULE=config.settings_test (no DB access): all five LIVE_LINKS["4.17"] names reverse, apps.scm.urls imports clean with 613 routes and zero duplicate `name=` values, and the eight new first path segments (logistics-clients, client-rate-cards, client-rate-card-lines, client-billing-runs, client-billing-run-lines, client-slas, client-inventory, client-space) collide with nothing in the concatenated urlconf — 4.11's `logistics-kpis/` is a distinct whole component. No greedy `<str:…>` converter was added. Template paths follow the mandated `<submodule>/<entity>/<page>.html` shape; the two report pages sit at the sub-module root (`templates/scm/3pl/client_inventory_report.html`, `client_space_report.html`), which is the correct standalone-report placement under the folder rule, not a banned flat entity path. The additive `owner_client` columns on ItemForm/LocationForm need no template change because templates/scm/inventory/{item,location}/form.html both loop `{% for field in form %}`. Cross-module reads were spot-checked and are sound: `draft_invoice()` matches accounting.Invoice/InvoiceLine field names, and the nine SLA resolvers match real fields on scm Shipment / SalesOrder / ReturnReason / CycleCountTaskLine / PutawayTask / StockMove including the `scm_return_authorizations` related_name. Out of my lane and unverified here: query counts, badge-class palette correctness, tenant-scoping of every write path, migration content, and the Phase 7 artifacts (`.claude/skills/scm/SKILL.md` and README) which are not in this changeset and are expected after the fix wave.
- **qa-smoke-tester:** SETUP: `manage.py migrate` (no pending migrations) + `seed_core` + `seed_accounts` + `seed_scm`, all idempotent; logged in as `admin_acme` / `password`. Seeded 4.17 data per tenant: 3 LogisticsClient, 3 ClientRateCard (15 lines), 3 ClientBillingRun (15 lines), 5 ClientSLA — identical shape for acme and globex.

RESULT: 0 findings. 350+ requests across seven passes, every one in (200, 302, 404, 405) as appropriate; no 500 anywhere.

--- PASS 1: full URL sweep as admin_acme (76 requests) ---
url name -> status / content check
scm:overview                       200 OK (module landing)
logisticsclient_list               200 OK title+rows | ?q=a&status=active 200 OK | ?category=abc&status=zzz&billing_cycle=%C2%B2 200 OK | ?page=2 200 OK
logisticsclient_create             200 OK ("New Logistics Client", fields code/party/billing_cycle present)
logisticsclient_detail             200 OK (code + party + rate-card/run/SLA panel numbers all present)
logisticsclient_edit               200 OK  | logisticsclient_delete GET 405 (POST-only, correct)
clientratecard_list                200 OK | ?filtered 200 | ?client=abc&category=abc 200 | ?page=2 200
clientratecard_create              200 OK | clientratecard_detail 200 OK (all 9 line descriptions render)
clientratecard_edit                302 on an ACTIVE card (correct refusal); 200 OK on the DRAFT card
clientratecard_delete/activate/supersede  GET 405 (POST-only, correct)
clientratecardline_create          200 OK on the draft parent (charge_category/charge_basis/rate/period render)
clientratecardline_edit            200 OK on a draft line | _delete GET 405
clientbillingrun_list              200 OK | ?filtered 200 | ?junk 200 | ?page=2 200
clientbillingrun_create            200 OK ("New billing run")
clientbillingrun_detail            200 OK (number + 824.50 total + line descriptions render)
clientbillingrun_edit              302 on the INVOICED run (correct); 200 OK on a CALCULATED run
clientbillingrun_delete/calculate/approve/draft_invoice/void  GET 405 (POST-only, correct)
clientbillingrunline_create/edit   200 OK on a calculated run (quantity+rate render; `amount` is derived, not a form field)
clientsla_list                     200 OK ("Not measured" rendered for the null-measurement rows) | ?filtered 200 | ?junk 200 | ?page=2 200
clientsla_create/detail/edit       200 OK (target 98.00 + "Meeting" on SLA-00001; "Not measured" on the no-data SLA)
clientsla_delete/recompute/recompute_all  GET 405 (POST-only, correct)
client_inventory_report            200 OK | ?client=<pk> 200 OK | ?category=abc&client=abc&location=%C2%B2&page=2 200 OK
client_space_report                200 OK | ?client=<pk>&space_model=dedicated 200 | ?junk 200 OK

--- PASS 2: cross-tenant IDOR as admin_acme against globex pks ---
12 GET detail/edit/nested-line-create URLs -> 404 (all)
11 POST verb URLs (delete/activate/supersede/calculate/approve/draft-invoice/void/recompute/line-delete) -> 404 (all)
Also: admin_globex's four list pages contain zero acme row URLs (`/scm/<segment>/<acme_pk>/` never appears).

--- PASS 3: real page 2 ---
`get_page` clamps out-of-range, so seeded 3-5 rows never exercise page 2. I inserted 20 extra rows per model inside a rolled-back transaction (23/23/23/25 rows, per_page=15) and hit ?page=1, ?page=2, ?page=99, ?page=abc on all four lists plus ?page=2 on both reports and one filtered ?page=2&status=meeting: 13/13 -> 200, no EmptyPage/`previous_page_number` 500 (the four lists delegate to `partials/pagination.html`, which guards `has_previous`/`has_next`). Rollback verified: counts back to 3/3/3/5, 0 QA parties left.

--- PASS 4: context-variable audit (the silent-blank class) ---
Captured `response.context` via `setup_test_environment()` for all 16 4.17 templates and resolved every template variable ROOT (`{{ x }}`, `{% for _ in x %}`, `{% if x %}`) against the supplied context. Only unresolved roots are `obj` on the CREATE path of logisticsclient/clientratecard/clientsla form.html — every one of those is inside an `{% if is_edit %}` guard (verified by reading templates/scm/3pl/logisticsclient/form.html:110-114 etc.), so no blank region. No view/template context mismatch anywhere in 4.17.

--- PASS 5: template-syntax leak ---
16 pages scanned for `{#`, `{% comment`, `{%comment`, `{{ ` and bare `{%` in the rendered body: zero occurrences on any page.

--- PASS 6: POST verbs (rolled back) ---
activate / supersede / calculate / approve / draft-invoice / void / recompute / recompute-all all returned 302 with no exception; DB restored on rollback.

--- PASS 7: junk-param fuzz ---
195 requests: 15 junk values (`abc`, `²`, a 21-digit over-range int, `-1`, `0`, empty, an SQLi string, `NaN`, `Infinity`, `2026-13-45`, `%00`, `1.5`, `%7B%25`, `<script>`) x 13 params (period_from/period_to/client/page/status/active/category/location/space_model). Zero non-2xx/3xx. `as_db_int` and `_as_date` hold; L11 is covered.

OUT-OF-LANE / PRE-EXISTING OBSERVATIONS (not actionable here):
- `clientbillingrun_approve` and `clientbillingrun_draft_invoice` (apps/scm/views/ThirdPartyLogistics/ClientBillingRuns.py:406, 423) carry `@tenant_admin_required` + `@require_POST` but no `@login_required`. I verified at runtime that anonymous GET and POST to all 36 4.17 routes return 302/405 and never 200 or 500, so `tenant_admin_required` does gate authentication — flagging only so the security lane can confirm the decorator stack is deliberate.
- The superuser (`tenant=None`) renders all four 4.17 lists and both reports at 200 with empty data rather than crashing — the documented by-design behaviour, confirmed at runtime.
- Seeder coverage gap (not a defect): `seed_scm` creates no `draft` ClientBillingRun for either tenant (statuses are calculated/calculated/invoiced), so the demo data never shows the draft rung of the billing ladder. Edit/add-line pages are still reachable because `EDITABLE_RUN_STATUSES` includes `calculated`.
- Template folder is `templates/scm/3pl/` while the Python package is `ThirdPartyLogistics/`; this asymmetry matches all sixteen shipped scm sub-modules and is documented in the view docstrings — not a banned flat path.

## Done well

- **code-reviewer:** The view↔template contract is genuinely airtight rather than merely documented: I checked all six 4.17 forms' `Meta.fields` against the `{% include \"partials/form_field.html\" with field=form.X %}` lines in their templates and every single field is rendered (26/26 on `LogisticsClientForm`, 13/13 on `ClientSLAForm` and `ClientRateCardLineForm`, 8/8 on `ClientRateCardForm`, 5/5 and 6/6 on the billing-run pair), so no field is silently dropped from a POST and blanked on edit — and every model `clean()` error key in the sub-module lands on a field its form actually carries, which is what keeps `add_error` from 500-ing instead of rendering.
- **security-reviewer:** The two tenant-less child models are closed against the classic child-IDOR shape from both directions: every read/write of a `ClientRateCardLine` resolves through `rate_card__tenant=request.tenant` (plus a redundant `rate_card__client__tenant=`) and every `ClientBillingRunLine` through `run__tenant=request.tenant`, while the parent pk on both create routes comes from the URL and is re-stamped in the view after `is_valid()` (`line.rate_card = rate_card`, `line.run = run`) rather than being trusted from the POST body — and neither line form carries a `rate_card`/`run` field at all.
- **performance-reviewer:** The query-shape discipline on the two computed report pages is genuinely excellent: `client_inventory_report` replaces six per-row model methods with grouped aggregates keyed on the page's client ids (Reports.py:168-204), pins `.order_by()` to stop `StockMove.Meta.ordering` from leaking `moved_at` into the GROUP BY, and carries the `qty__gt=ZERO` HAVING so the figure matches `LogisticsClient.on_hand_value()` exactly — six flat queries regardless of row count, with every cap applied as a DB slice rather than a Python truncation. The list views are equally clean: every filter runs before `crud_list`'s Paginator, all four stat blocks are single `aggregate()` calls with conditional `Count`, `line_count` is annotated rather than read off the `active_line_count` property, `logisticsclient_list` defers the one unrendered TextField, and `clientratecard_list` pins an explicit `order_by` precisely because the annotation ungroups the queryset for `Paginator`.
- **frontend-reviewer:** The L33 discipline is genuinely airtight and is the best-executed part of the sub-module: every status/category chip is a literal if/elif ladder on the exact CHOICES keys (`draft/active/superseded/expired`, `draft/calculated/approved/invoiced/void`, `meeting/at_risk/breached/no_data`, `prospect/onboarding/active/suspended/terminated`) with a colour-named theme.css class and an `{% else %}` branch that still prints `get_FIELD_display`, and the four dynamic classes (`status_css`, `category_css`) come from model properties that `.get(..., "badge-muted")` over maps containing only the six real badge classes — so even an unknown value degrades to a styled pill instead of an unstyled one. The same care shows in the `{% if x is not None %}` guards for a legitimately-measured 0.00 and a null `dedicated_capacity`, which is exactly the distinction a truthiness test would destroy.
- **explorer:** The frozen context-var contract held perfectly across the fan-out: every root variable in all 16 new templates exists in the matching view's render dict (list vars, detail/edit `obj`, every `*_choices`, every `stats.*` and `totals.*` sub-key, and the per-row dict keys of `line_groups` / `unbilled` / `sla_credits` / report `rows`), all 36 routes map one-to-one onto 36 defined and re-exported view functions with no orphans in either direction, all 33 `_choices` symbols in the models re-export block exist and collide with none of the six other scm `_choices` modules, every `{% url %}` name and arity resolves (including the cross-app `accounting:invoice_detail`, `core:party_detail`, `core:document_detail`), all 16 `render()` template paths exist, and every `Meta.fields` whitelist is rendered field-for-field by its template — including `ClientRateCardForm.status`, which is on the form deliberately and IS rendered at clientratecard/form.html:123 despite three commit messages saying otherwise.
- **qa-smoke-tester:** Every one of the 4.17 status branches renders — I forced each `ClientRateCard` status (draft/active/superseded/expired), each `ClientBillingRun` status (draft/calculated/approved/invoiced/void), each `LogisticsClient` status (prospect/onboarding/active/suspended/terminated) and each `ClientSLA` status x is_active combination onto a real seeded row inside a rolled-back transaction and re-rendered its detail + filtered list: 48/48 returned 200 with the object identifier present and no template-syntax leak. The empty-state branches (a card with no lines, a run with no lines, a client with no cards/runs, and a workspace with zero clients on both report pages and all four lists) also render cleanly, which is the branch set a seed-shaped smoke test normally never reaches.
