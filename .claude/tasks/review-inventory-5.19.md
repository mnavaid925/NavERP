# Review — inventory 5.19 Third-Party Integrations & API

Date: 2026-08-25 · Base: `132a60b0` · Six lanes: code-reviewer · explorer · frontend-reviewer ·
performance-reviewer · qa-smoke-tester · security-reviewer (all returned; no dead lanes).
Scope: `apps/inventory/{models,forms,views,urls}/ThirdPartyIntegrations/`,
`templates/inventory/integration/**`, 5.19 blocks of admin.py/navigation.py/package inits,
migration 0026. Concurrent-session commits inside BASE..HEAD were excluded (L45).
Runtime state at review: migration applied, check green, partial smoke 17/17 PASS,
seeds pending (C1).

## Findings (burn-down order)

### Critical
- [~] **C1** [~] skipped — owned by main session (L45-gated shared file)
  `management/commands/seed_inventory.py` — contract §7 `_seed_integrations` hook absent
  (demo channels/listings/runs/API-clients never seed; smoke content gate cannot pass).
  NOTE: not a code defect — deliberately deferred behind the concurrent session's uncommitted
  hunks in that shared file (L43/L45); lands in THIS session the moment the file frees.

### Important
- [x] **I1** [fixed: RETRYABLE_STATUSES ("failed","pending","exhausted") gate inside the
  select_for_update+atomic block; messages.error names the status, redirects detail, no state
  change — scm webhookdelivery_retry shape] views StockSyncRuns.py:131 — `stocksyncrun_retry` has NO status guard: any run
  (success/partial/simulated) can be flipped back to pending via direct POST, rewriting recorded
  outcome. Add RETRYABLE_STATUSES gate ("failed","pending","exhausted") inside the lock, mirroring
  scm webhookdelivery_retry; messages.error + redirect otherwise.
- [x] **I2** [fixed: null=True (+migration 0027) + honest comment; form clean() also coerces ''
  → None so the UI path really stores NULL — CharField otherwise cleans to ''] models ChannelListingMaps.py:93 — `external_variant_id` CharField(blank=True, NOT NULL)
  stores `''` not NULL, so two local-only rows of one channel COLLIDE (raw IntegrityError outside
  forms); the "null-coalescing" comment + seeder plan premise fail. Fix: `null=True` (+ migration),
  keep unique_together; correct the comment wording.
- [x] **I3** [fixed: index = attempt_no, bounds `0 <= attempt_no < len` checked BEFORE indexing,
  None past the end; retry keeps "wait slot[min(attempt_no, len-1)] then attempt_no += 1"
  semantics via the property (fresh run waits slot[1]=5s, becomes attempt 2; attempt_no=8 →
  exhausted); _choices comment + field comment + view docstring all describe THIS scheme;
  template copy renders obj.next_backoff_seconds so it stays truthful] models StockSyncRuns.py:171-174 + _choices.py:115 — as-built indexes `attempt_no - 1`
  while BOTH the frozen contract ("index = attempt_no … WHD verbatim") and scm prior art index
  `attempt_no`; guard checks the wrong bound (attempt_no=0 negative-indexes silently). Realign to
  `index = attempt_no`, guard `0 <= attempt_no < len(...)`, fix retry-view stamping + comments +
  docstring to match one scheme honestly.
- [x] **I4** [fixed: listings sliced [:25], chip reads new `listings_total` count() key,
  >25 footer + header link deep-link `{% url 'inventory:listingmap_list' %}?channel={{ obj.pk }}`] views IntegrationChannels.py:100-105 + channel/detail.html:149,164 — listings panel
  renders the ENTIRE listing queryset unsliced and `{{ listings|length }}` materializes it;
  cap [:25] + count() chip + deep-link to listingmap_list?channel=<pk> (rows are high-volume by
  design).
- [x] **I5** [fixed: panel-header "Manage listings" btn-outline deep-link + per-row
  listingmap_detail/listingmap_edit btn-icon eye/pencil column] channel/detail.html:145-217 — zero links to any `listingmap_*` route anywhere in the
  UI; since §8 gives listings no sidebar key BY DESIGN, all five listings routes are orphaned.
  Add panel-header "Manage listings" link + per-row view/edit affordances.
- [x] **I6** [fixed: Edit wrapped in the existing `{% if is_admin %}` alongside Delete] apiclient/detail.html:19 — Edit link rendered unconditionally though edit is
  @tenant_admin_required → dead-end for staff. Wrap in existing `{% if is_admin %}`.
- [x] **I7** [fixed: status != "active" → messages.error("Client is revoked — issue a new
  client instead."), redirect detail, no credential change, no success audit row] views ApiClients.py:118-135 — issue_token mints fresh credentials for REVOKED clients
  (revocation-bypass primitive once a gateway honors hashes). Gate: refuse unless status=="active".
- [x] **I8** [fixed: IntegrationChannelForm, ChannelListingMapForm, ApiClientForm appended to
  the `__all__` tail; import-time verified] apps/inventory/forms/__init__.py — three 5.19 forms imported but missing from
  `__all__`; star-imports omit them. Append the three names.

### Minor
- [x] **M1** [fixed: mirrored listingmap_list's validated echo — junk/foreign pk falls back to
  unfiltered with "" echoed] views StockSyncRuns.py:86 — echoes raw `?channel=` param; mirror sibling's validated echo.
- [x] **M2** [fixed: AddIndex inv_syn_tnt_started_idx (tenant, started_at) landed inside
  migration 0027 alongside I2's AlterField; migrate OK, `makemigrations --check` clean] migration — runs default landing orders `-started_at` with no `(tenant, started_at)`
  leading index (file-sort over unbounded register). Add index alongside I2's migration.
- [x] **M3** [fixed: one `channel.runs.aggregate(total=Count("id"), failed=Count("id",
  filter=Q(status="failed")))`] views IntegrationChannels.py:200-203 — `_run_stats` two COUNT round-trips; one
  grouped aggregate matches house style.
- [x] **M4** [fixed: detail view hand-rolled (scm webhookdelivery_detail shape) — panels built
  after get_object_or_404, so a 404 evaluates no panel queries at all] views IntegrationChannels.py:110 — `_run_stats` extra_context evaluates before crud_detail
  404s; make lazy/callable if trivially possible, else skip with reason.
- [x] **M5** [fixed: Access Token + Lifecycle dt/dd groups each wrapped in a `<dl>`; admin
  forms stay outside the dl] apiclient/detail.html:83+ — bare `<dt>/<dd>` without `<dl>` ancestor; wrap groups.
- [x] **M6** [fixed: confirm() on the issue/rotate POST — "Any previous token stops working
  immediately."] apiclient/detail.html:127 — Issue/Rotate Token POST lacks confirm() (rotate invalidates
  previous token silently); add like rotate-key elsewhere.
- [x] **M7** [fixed: both form.html files now use channel/form.html's styled
  `{% for e in form.non_field_errors %}` loop] apiclient/form.html:23 + listingmap/form.html:28 — raw `<ul>` non_field_errors vs
  channel/form.html styled loop; unify on the styled pattern.
- [~] **M8** [~] skipped — boolean cardinality, combined filters covered by unique prefix
  (reason as recorded in the finding: low-cardinality lens, almost always narrowed further by
  ?channel=; no dedicated index warranted)
  ChannelListingMap `?sync_enabled=` lens unindexed — boolean cardinality + usually
  combined with covered ?channel= filter; acceptable to SKIP with reason.
- [x] **M9** qa determinism byte-diff — Django CSRF rotation on every page app-wide; normalized
  compare proves determinism. No action warranted (recorded).
- [~] **M10** flash-once plaintext rides FallbackStorage (client-readable cookie until consumed)
  — DECIDED design surface; noted as future-hardening candidate (SessionStorage / copy-once
  interstitial), intentionally unchanged this pass.
- [x] **M11** [fixed: reverted to the pinned `obj.listings` / `obj.runs` related managers
  (equivalent queries) — enabled by the M4 hand-rolled fetch; I4's slicing/count kept] views IntegrationChannels.py:101-109 — panels re-keyed `filter(channel_id=pk)` instead
  of pinned `obj.listings`/`obj.runs` without a DECIDED ruling. Cheapest honesty: revert to the
  related managers (equivalent queries), or append a ruling to todo.md §4.

## Lane summary
| Lane | Findings |
|---|---|
| code-reviewer | 5 (2 Imp, 3 Min) |
| explorer | 4 (1 Crit, 2 Imp, 1 Min) |
| frontend-reviewer | 5 (1 Med, 2 Low, 2 Info) |
| performance-reviewer | 5 (1 Med, 4 Min) |
| qa-smoke-tester | 1 no-action note (all runs PASS) |
| security-reviewer | 2 (1 Low, 1 Info) |

Verified clean across lanes: tenant scoping on all 22 views; secrets prefix+SHA-256 only with
zero plaintext persistence/log/render; SSRF posture intact (no transport imports anywhere);
CSRF 11/11; mass-assignment safe (explicit Meta.fields); stats single-grouped-query convention;
pagination discipline; N+1 clean on lists; url census 22/22 resolve + literal-before-pk holds;
GET never mutates (405 on all 8 POST-only routes); cross-app canaries green.
