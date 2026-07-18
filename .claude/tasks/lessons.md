# Lessons

> **Carried over from the predecessor Sales Management System project (NavSalesManagementSystem → now NavERP).** These lessons were
> learned building a multi-tenant Django 5.1 + XAMPP MariaDB 10.4 + Tailwind/HTMX app — the **identical stack**
> NavERP uses — so they apply directly. Project/DB references have been updated (`NavERP`, DB `nav_erp`,
> test DB `test_nav_erp`). A few anecdotes name Sales-era apps/models (`apps/tenants` Subscription/Invoice, the
> `compensation` reference module, "Modules 11–20") — read those as illustrative of the *pattern*, not as the
> NavERP module map (NavERP modules are 0–13; see `NavERP.md` / `NavERP-ERD.md`).

## L1 — Verify a database is actually ours (and empty) before migrating
`CREATE DATABASE IF NOT EXISTS x` is a **silent no-op** when `x` already exists. This XAMPP instance hosts many other
Nav* databases (e.g. `navpms`, `navaccounting`, `navcrm`) owned by live apps. **Rule:** before pointing `.env` at a DB
and running migrate, check `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='<db>'` and confirm it's
empty or ours. Never flush/fake-migrate a non-empty unknown DB. This project uses its own DB **`nav_erp`** (verified
empty before the first migrate).

## L2 — Django `{# … #}` comments are single-line only
Multi-line `{# … #}` comments **leak as visible text**. Use `{% comment %} … {% endcomment %}` for any
note longer than one line. (Found in `sidebar.html` + `customizer.html` during verification.)

## L3 — HTTP-200 smoke tests miss template-comment / content leaks
A page can return 200 yet render leaked comment text or wrong content. **Pair** the status-code smoke test
(Django test client over all url names) with a **rendered-HTML content check** (assert no `{#`/`{% comment`
markers, assert expected chart/script ids and tenant name present).

## L4 — XAMPP MariaDB 10.4 vs modern Django
Django 5.1 requires MariaDB ≥ 10.5; XAMPP ships 10.4.x. Either upgrade MariaDB, pin Django 4.2 LTS, or use
a documented features shim in `config/__init__.py` (we used the shim; it disables `INSERT … RETURNING` for
MariaDB < 10.5 and relaxes the version floor).

## L6 — Stale/orphaned dev servers mask code fixes (verify via a single fresh server)
A template fix can be correct on disk + clean in `render_to_string` and the test client, yet a browser still
shows the OLD output — because a **leftover server is serving a pre-fix snapshot**. On Windows, Django
`runserver` uses `SO_REUSEADDR`, so **multiple orphaned processes can all LISTEN on the same port** (e.g. a
`preview_start` server started before the fix + `runserver` children orphaned when their wrapper task was
TaskStop'd). `Get-NetTCPConnection`/`Win32_Process` filtered by name can miss them. **Rule:** when a fix "won't
show", `netstat -ano | findstr :PORT`, kill EVERY LISTENING pid in a loop until the port is empty, `preview_stop`
any preview servers (check `preview_list`), then start ONE fresh server and re-verify over real HTTP. Then the
user must hard-refresh (Ctrl+Shift+R). The in-process test client is the authoritative render check.

## L5 — User workflow preference: fan out aggressively
The user explicitly asked to "use more Agents to complete the task as soon as possible." For large builds,
prefer a parallel multi-agent Workflow (e.g. foundation+shell in parallel, then a burst of page agents)
over a 2-agent sequential pipeline. Keep critical-path/single-writer work (migrations, shared base/static)
solo; parallelize disjoint file sets (per-app templates).

## L7 — When backend & template agents are split, PIN the detail/edit context-var name
Separate agents wrote views (`models.py`/`views.py`) and templates from a shared spec. The spec pinned the
**list** context var (the plural, e.g. `subscriptions`, `invoices`, …) but NOT the **detail/edit object** var.
Result: some models drifted — the view passed e.g. `subscription_obj` while the template used `obj` → `{% url … X.pk %}`
got an empty pk → **NoReverseMatch (500)**.
**Rule:** the contract handed to parallel agents must pin EVERY context key a template consumes (detail object,
edit-mode object, every `*_choices`, every FK queryset), not just the list var. 12/16 matched only by luck
(agents independently chose the model name). The fix here was to align the view's key to the template's var.

## L8 — A GET-200 smoke test does NOT prove the page is correct (add a content assertion)
A wrong detail context var renders **blank** (Django silently swallows a missing top-level var) and still
returns 200 — only the `{% url … X.pk %}` case 500s. **Rule:** after the status-code sweep, also assert each
detail page's rendered HTML contains the object's identifier (e.g. a token from `str(obj)`); this catches the
silent-blank class. Also run the test client with `Client(raise_request_exception=False)` so one pass collects
**all** 500s instead of aborting on the first.

## L9 — Django pagination: never emit `page_obj.previous_page_number` unconditionally
`Page.previous_page_number()` / `next_page_number()` **raise `EmptyPage`** when there is no prev/next page.
Putting `…page={{ page_obj.previous_page_number }}` in a "Prev" href 500s on page 1 — but only once a list
exceeds the page size, so it's invisible with small seed data (the reference invoice list has the same latent
bug and never paginates). **Rule:** guard with `{% if page_obj.has_previous %}{{ page_obj.previous_page_number }}{% else %}1{% endif %}`
(and `has_next` / `paginator.num_pages` for Next).

## L10 — `{{ fk.get_full_name|default:fk.username|default:"—" }}` 500s when fk is None
Django swallows a failed lookup on the **main** variable, but a failed lookup in a **filter argument**
(`default:fk.username` when `fk` is None) raises `VariableDoesNotExist` and 500s. Seed data that always sets
the FK hides this. **Rule:** guard user-FK display with `{% if fk %}{{ fk.get_full_name|default:fk.username }}{% else %}—{% endif %}`.

## L11 — Integer FK list filters must validate input before `.filter(fk_id=…)`
`qs.filter(project_id=request.GET.get('project'))` raises `ValueError → 500` on non-numeric input
(`?project=abc`). Dropdowns only emit int pks, so it never shows in normal use, but a hand-edited URL hits it.
**Rule:** guard with `if value.isdigit():` (string-choice filters are immune; only int/FK params need this).

## L12 — Wire-up must come AFTER the app files exist (check-after-edit hook)
A `PostToolUse:Edit` hook runs `manage.py check` after every edit. Editing `config/urls.py`/`settings.py` to
reference a new app whose files a background workflow hasn't written yet → `No module named 'apps.<x>.urls'`
and the hook BLOCKS. **Rule:** when a build Workflow is creating the app files, do the settings/urls/navigation
wire-up as the post-build single-writer step (after the workflow completes), not concurrently. (On Modules 1–3
there was no such hook so early wire-up worked; on 4–7 it didn't.) Baking the lessons into the spec up front
(L7–L11 in `temp/specs/_conventions.md`) made the 4–7 build pass all 6 verification classes on the first pass.

## L15 — The browser caches `static/js|css` (Django dev sets no Cache-Control) → version the assets
Editing `layout.js`/`theme.css` and reloading showed NO change because the browser served the OLD file from
its HTTP cache (Django's dev static handler sends only `Last-Modified`, so browsers apply *heuristic freshness*
and skip revalidation for a while). `location.reload()` did not bust it. **Fix:** version the includes —
`<script src="{% static 'js/layout.js' %}?v=2">` (bump the number when the file changes). Then a normal reload
fetches the new URL. For verification in the preview, a unique page query (`/?_cb=<ts>`) forces a fresh HTML
fetch. (Long-term: a `{% static %}`-with-mtime template tag or ManifestStaticFilesStorage auto-versions.)

## L14 — `.claude/launch.json` runs the dev server with `--noreload` → ALWAYS restart after a build
The preview server (`launch.json` config `NavERP`) starts `manage.py runserver --noreload`. `--noreload` means
**file edits are NEVER picked up** — after building/wiring a module, the running server keeps serving pre-change
code, so new sub-modules show the "On the roadmap" placeholder and edits look like they "didn't work". This is a
specific instance of [L6]. **Rule:** after finishing a module build (especially `navigation.py`/`urls.py`/
`settings.py` wiring), restart the server: find the LISTENING pid on :8000 with **`netstat -ano | Select-String
':8000\b'`** (NOT `Get-NetTCPConnection` — it false-negatived a real listener here), `Stop-Process -Id <pid>
-Force`, then `preview_start NavERP`. Then verify the live page renders (fetch `/initiation/requests/` → contains
"Project Requests", not "On the roadmap"). The disk code was already correct — only the stale process was wrong.

## L13 — Template agents reference utility CSS classes that don't exist
Agents wrote `<span class="text-danger">`/`text-red` to flag negative/over-threshold values, but theme.css only
defines `.text-muted`/`.text-brand` — so the values rendered with no emphasis (cosmetic, no error). **Rule:**
define the common utilities (`.text-danger`, `.text-red`) once in theme.css's "Utility helpers" section (mirrors
`.text-muted`), with a `.dark` variant — DRY, and fixes every occurrence at once. Better: list the available
utility classes in the spec so agents don't invent class names.

## L16 — Date-equality tests flake on the UTC-offset window (use Django's `timezone`, not `datetime.date.today()`)
With `USE_TZ=True` + `TIME_ZONE='UTC'`, model/view code computes "today" as `timezone.now().date()` (the **UTC**
date). Tests that build a reference date with `datetime.date.today()` use the **local** machine date. The user is
UTC+5, so for the ~5h each morning after local midnight (local date has rolled, UTC hasn't), the two differ by
one day and any exact date-equality assertion fails — e.g. `Subscription.days_left()` returned 8 vs expected 7, and
`Invoice.paid_at == datetime.date.today()` saw UTC `06-14` vs local `06-15`. The on_stop hook (`pytest -x`) then
blocks the turn. These are **pre-existing flakes**, invisible most of the day, surfaced only by the date rollover.
**Rule:** in tests, derive the reference date from the SAME basis the code under test uses — `timezone.now().date()`
(or `timezone.localdate()`), never `datetime.date.today()` — whenever you assert exact equality against a
model/view-set date. (Two such assertions existed in `apps/tenants/tests`; fixed both.)

## L17 — A stale/half-created `test_<db>` blocks the whole suite (drop it, don't reuse)
An interrupted pytest run left `test_nav_erp` existing but without its `django_migrations` table; the next run
(reuse-db) reused the broken DB → `ProgrammingError: Table 'test_nav_erp.django_migrations' doesn't exist` /
`(1007, Can't create database 'test_nav_erp'; database exists')` in setUp, failing every test before it ran.
**Rule:** when pytest errors on the test DB itself (not an assertion), drop it and let pytest recreate clean:
`& "C:\xampp\mysql\bin\mysql.exe" -u root -h 127.0.0.1 -P 3306 -e "DROP DATABASE IF EXISTS test_nav_erp;"`
(root / no password on this XAMPP). Unrelated to app code — it's an environment reset.

## L18 — Close every module build with the specialist review agents, not just self-checks
On Modules 8-11 I verified with my own smoke test + pytest + IDOR but did NOT run the project's specialist review
agents — the user had to ask "did you run the agents?". A parallel 5-agent review (code-reviewer, security-reviewer,
performance-reviewer, frontend-reviewer, qa-smoke-tester) + adversarial verification of each finding then caught real
issues a GET-200 + content sweep CANNOT, by design: chained N+1s (a parent `__str__` resolving a 2nd FK not in
`select_related` — e.g. a child list whose row `__str__` hits an owner FK needs the chained
`select_related('parent__owner')`), a counter field left writable in a ModelForm, redundant
all-one-color badge branches, and missing `<label for=>`/`id=`. None of those 500 or leak. **Rule:** the module-build
quality bar INCLUDES a closing multi-agent adversarial review as the LAST phase, run by default — not on request.
Separate the wheat from the chaff: fix defects specific to the new module; for findings that are faithful copies of
the app-wide reference pattern (non-atomic auto-numbering, global-unique numbers, missing `db_index`, filter-label
`for=`), flag an app-wide pass instead of forking one module out of step with the other ~12.

## L19 — The on_stop hook ran pytest against MySQL (shared test_nav_erp), not the SQLite test settings
This was the ROOT CAUSE of the recurring "Table 'test_nav_erp.X' doesn't exist" Stop-hook failures (the [L17]
drop-the-DB step was only a band-aid). `.claude/hooks/on_stop.py` does
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")` for its step-1 `manage.py check`, then spawned
`pytest` as a subprocess that INHERITED that env var. pytest-django honours the env var over `pytest.ini`, so the
hook ran the suite under `config.settings` (MySQL `nav_erp` → `test_nav_erp`) instead of the project's
`pytest.ini` default `config.settings_test` (SQLite `:memory:`). Effects: slow, MariaDB-10.4-fragile, and — when a
second session ran its suite at the same time — collisions on the shared `test_nav_erp` (half-migrated → missing
tables). My OWN `venv\Scripts\python.exe -m pytest` runs used `pytest.ini` (SQLite) and always passed, which masked
it. **Root-cause fix:** pass an explicit `env` to the pytest subprocess with
`DJANGO_SETTINGS_MODULE=config.settings_test`. Verified end-to-end: `'{}' | python .claude/hooks/on_stop.py` →
exit 0 ("manage.py check OK - tests OK") in ~70s. **Rule:** when a hook/CI runs Django tests, confirm WHICH settings
module actually resolves (env var beats `pytest.ini`); test runs must use the isolated SQLite test settings, never
the shared dev DB.

## L20 — A "masked-in-template" secret is still leaked via the edit form — EXCLUDE it from the ModelForm
Building Modules 16–20, the spec told the AutomationHook/ApiKey agents to "mask the secret in templates" AND
exclude it from the form, but the Webhook agent was only told to "mask in templates" — so `WebhookForm.fields`
kept `'secret'`. A `CharField` with no widget override renders as `<input type="text" value="{{ stored_secret }}">`
on the EDIT page, so the plaintext secret ships to the browser for any user who can open the edit form — even
though the detail page masked it with bullets. Three independent reviewers caught it; AutomationHookForm/ApiKeyForm
(same module family) already did it right by EXCLUDING the field. **Rule:** for any secret/credential/hash field,
the fix is to leave it OUT of `Meta.fields` (rotate via a dedicated write-only flow), not merely to mask it in the
detail template. Masking the read view does nothing for the bound edit form. When writing module specs, state
"exclude from the ModelForm" explicitly for every sensitive field, not "mask it".

## L21 — Verify per-module file counts after a build Workflow BEFORE wiring/migrating (workflows can be cut off mid-phase)
The 30-agent build workflow for Modules 16–20 was terminated mid-frontend-phase (parent turn interrupted), leaving
`automation` at 3/15 templates and `administration` at 14/15 while backend was 11/11 for all apps and the other three
modules were complete. A naive "workflow done → migrate + smoke test" would have hit `TemplateDoesNotExist` 500s.
**Rule:** after a code-gen Workflow, assert the expected file count per unit (e.g. `find templates/<slug> -name '*.html' | wc -l`
== 15) before relying on the output; regenerate only the missing pieces with a focused follow-up workflow. Backend
(single-writer, DB) and template (per-file) work are independent, so wiring + migrate + seed can proceed on the
complete backend while the missing templates are regenerated in parallel. Blocking on the workflow task
(`TaskOutput block=true`) also keeps a short follow-up run alive through turn boundaries.

## L22 — System-set timestamps (`*_at`) don't belong on manual edit forms (mirror apps/tenants: zero editable DateTimeFields on forms)
The template agents put nullable `DateTimeField` columns (`last_run_at`, `last_sync_at`, `started_at`, `recorded_at`,
`completed_at`, `last_triggered_at`) onto ModelForms with a `DateInput(type=date)` widget. That date-only widget
silently truncates the time component on every edit-save (and `datetime-local` would need matching widget+field
`input_formats` to round-trip correctly — fiddly). The `apps/tenants` (Module 0) reference puts ZERO editable
DateTimeFields on its forms — its only DateTimeFields are `auto_now`/`auto_now_add` audit columns or system-set
fields (`paid_at`, `completed_at`, `recorded_at`, `last_rotated_at`), never in `Meta.fields`; its date widgets sit
only on real user-set `DateField`s (issued_on/due_on/started_on/renews_on). **Rule:** treat observed/system timestamps as read-only —
keep them on the model + detail page but OUT of the form. Reserve `DateInput(type=date)` for genuine user-set
`DateField`s. This is the root-cause fix, not swapping in a `datetime-local` widget.

## L23 — MariaDB 10.4 shim: lowering the version floor is NOT enough — also force RETURNING off (refines L4)
Bootstrapping NavERP (Django 5.1 on XAMPP MariaDB 10.4), the shim only set
`DatabaseFeatures.minimum_database_version=(10,4)` + a no-op `check_database_version_supported`. `migrate` still
died on the very first `INSERT … RETURNING django_migrations.id` (`pymysql.err.ProgrammingError 1064`). Root cause:
because 10.5 is Django 5.1's *minimum* supported MariaDB, the backend no longer version-gates RETURNING — it enables
it for **any** MariaDB. The old "`mysql_version >= (10,5)`" sub-check is gone, so on 10.4 it wrongly returns True.
**Rule:** the 10.4 shim in `config/__init__.py` MUST also force the feature flags off explicitly —
`DatabaseFeatures.can_return_columns_from_insert = False` and `...can_return_rows_from_bulk_insert = False`
(assigning a plain value overrides the cached_property descriptor). Then migrate runs clean. A half-migrated DB from
the first failure had tables but an empty `django_migrations`; recover by DROP+CREATE the (fresh, ours) `nav_erp` DB.

## L24 — Greenfield bootstrap with the auto-verify hook: write ALL backend before config/settings.py
On an empty repo the `PostToolUse:Edit` hook (`on_edit.py`) does `django.setup()` under `config.settings`; while
`config/settings.py` does **not** exist yet it raises ModuleNotFoundError → caught → "skipped" (exit 0). So you can
write every app file (models/views/urls/forms/admin) freely with the hook no-opping, then write `config/settings.py`
**last** — that single write is the first real `manage.py check`, validating the whole backend (INSTALLED_APPS +
URLConf import) in one pass. Custom `AUTH_USER_MODEL` only needs to exist before the first *migrate*, not *check*.
(Generalises L12: wire-up after files exist.)

## L25 — A one-time secret must NOT be surfaced via the messages framework (it persists in the session store)
The EncryptionKey create/rotate views first flashed the plaintext with `messages.success(f"...{plaintext}")`. The
messages framework serialises to the session backend (DB sessions here), so the secret lingered in `django_session`
until the next render consumed it — readable from a DB dump/backup or a hijacked session, and it can land in logs.
**Rule:** reveal a generated secret exactly once via a **pop-once session key** rendered on the redirect target:
`request.session["_key_reveal"] = {"pk":obj.pk,"secret":plaintext}` in the create/rotate view, then in the detail
view `reveal = request.session.pop("_key_reveal", None)` and pass `plaintext_once` to the template (a copy box shown
only when set). Verified: reveal box present on the post-create view, absent on refresh; hash never rendered. Extends
L20 (store prefix+hash, exclude secret from the form) — masking the read view is not enough; don't flash the secret.

## L26 — Validate any user value rendered into an inline `style=` attribute (CSS/style injection)
BrandingSetting `primary_color`/`accent_color` were free `CharField`s rendered as `style="background:{{ color }}"`.
Django's attribute auto-escaping blocks closing the attribute, but a value like `red;...` is still valid CSS
injection, and a future `<style>`/`|safe` use would become stored XSS. **Rule:** constrain such fields with a
`RegexValidator(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")` on the model so only `#RGB`/`#RRGGBB` can be saved.

## L28 — When modules are pattern-clones, a confirmed per-module defect must trigger a sweep of ALL siblings
Building Modules 11-20 (10 near-identical clones of the compensation reference), the per-module adversarial review
confirmed exactly one defect: `automation` `EnrichmentRuleForm` left the run-history counters `records_processed` +
`success_rate` editable (system-derived, seeded as fake history, sitting next to the correctly-excluded `last_run`).
But the **per-module** reviewer for `integrations` returned zero findings and MISSED the identical-class defect there:
`SyncJobForm` left `records_synced` editable (same shape — a run-history counter on a job-config form, next to the
excluded `last_run`). Per-module reviewers are blind to cross-module repetition by construction. **Rule:** when a
review confirms a defect in one clone, grep the whole family for the same shape before fixing
(`grep -n "records_synced\|records_processed\|success_rate\|failure_count" apps/*/forms.py`) and fix every instance in
one pass. Distinguish a true run-history counter on a CONFIG/JOB model (exclude from the form) from a metric that IS
the record's data on a reporting model (e.g. analytics ConversionFunnel.entered_count — keep on the form). Financial
amounts the reference itself exposes (PayoutForm.net_amount, EarningForm.commission_amount, marketing roi) are an
app-wide pattern, not a per-module fix — leave them or change app-wide.

## L27 — Gate Module-0 (tenant administration) writes behind tenant-admin, not just @login_required
Billing, encryption-key rotation, branding and health writes were initially `@login_required`, so any Sales Rep in
the tenant could mutate them. **Rule:** privileged/workspace-config writes use `@tenant_admin_required` (shared in
`apps/core/decorators.py`); keep list/detail as `@login_required` if read access is fine for all roles. Also: the
`{{ debug }}` built-in context var needs `INTERNAL_IPS`; to gate template content on DEBUG, expose `settings.DEBUG`
explicitly via a context processor. Deferred (production hardening, not built): login rate-limiting/lockout
(django-axes) — note it in the README rather than ship it in the foundation.

## L28 — Verify the core spine actually EXISTS before a module plan reuses it; re-plan at build time if not
Building CRM 1.7–1.12, the `research` and `todo` agents both wrote plans that reused unified-core masters
(`core.Item`, `core.Currency`, `core.Invoice`/`Payment` AR-AP ledger, `core.PurchaseOrder`/`PurchaseOrderLine`,
`core.StockMove`) as if they were built — they are NOT. The foundation only built
`Party/PartyRole/Address/ContactMethod/PartyRelationship/Employment/Activity/AuditLog/Document/OrgUnit/Tenant`
(core) + `Subscription/SubscriptionInvoice/BrandingSetting/EncryptionKey/HealthMetric` (tenants). Those masters
belong to still-unbuilt Modules 2/5/6. Had I coded the plan verbatim, the 1.12 PO/stock views would have raised
`ImportError`/`FieldError` at first request. **Rule:** before writing any code that FKs into or queries a spine
entity, confirm it exists — `grep -n "^class <Name>" apps/core/models.py apps/tenants/models.py` (the agents'
`NavERP-ERD.md`/`NavERP.md` describe the *intended* spine, not the *built* one). When a planned entity is missing,
STOP and re-plan (CLAUDE.md): build a self-contained CRM-owned stand-in (e.g. CRM `PurchaseOrder`/`ProductStock`,
`Expense.currency_code` CharField, health from existing CRM signals), document the adaptation in `todo.md`, and note
the future migration onto the spine. The research/todo agent prompts should be told to verify entity existence, not
trust the ERD doc.

## L29 — Module 2 (`accounting`) now OWNS the financial ledger spine — later modules FK into `accounting.*`
Resolving the L28 gap for the domain it belongs to: **Module 2 (`apps/accounting`) builds and owns the GL ledger**
the foundation never built. As-built (`grep -n "^class" apps/accounting/models.py`): `Currency` (GLOBAL — no tenant
FK), `ExchangeRate`, `GLAccount` (Chart of Accounts; balance is DERIVED, no stored field), `FiscalPeriod`,
`JournalEntry`/`JournalLine` (append-only; immutable once posted — correct via a reversal), `PaymentTerm`,
`VendorProfile`/`CustomerProfile` (OneToOne on `core.Party` — vendors/customers stay PartyRoles), `Invoice`/
`InvoiceLine`, `Bill`/`BillLine`, `Payment`/`PaymentAllocation`, `BankAccount`, `BankTransaction`,
`ReconciliationMatch`. **Rule for future modules:** the AR/AP ledger, journal posting, multi-currency, and bank
masters are REAL now — when HRM payroll, Inventory costing, Procurement POs, Sales orders, or Assets depreciation
need to post financial effects, FK into `accounting.*` **by string** (e.g. `models.ForeignKey('accounting.JournalEntry', ...)`,
`('accounting.GLAccount', ...)`, `('accounting.Currency', ...)`) and post through a balanced `JournalEntry`/
`JournalLine` inside `transaction.atomic()` — do NOT build a second ledger or a stand-in (that was only justified in
CRM 1.7–1.12 because accounting didn't exist yet). Still UNBUILT spine masters (verify before reuse, per L28):
`Item`/`UOM`/`StockMove`/`LotSerial` (Inventory, Module 5), `PurchaseOrder`/`GoodsReceipt` (Procurement, Module 6),
`SalesOrder` (Sales, Module 8). Two deliberate accounting shortcuts to migrate later: the auto-posting heuristic
picks the first `1100`/`2000`-prefixed GL account (should be per-tenant configurable control accounts), and there is
no invoice/bill **void** action yet (only JE/payment void).

**Update (2026-06-21): Module 2 is now FULLY built, 2.1–2.15.** The advanced pass added accounting-OWNED *financial*
models in `apps/accounting/models_advanced.py` that post balanced JEs and reuse `core.OrgUnit` as the entity/
cost-centre dimension: `FixedAsset`/`AssetDisposal` (depreciation/disposal), `PayrollRun` (payroll journal),
`Project`/`JobCostEntry` (job costing), `IntercompanyTransaction`, `CostAllocation`, `TaxCode`/`TaxReturn`, `Budget`/
`BudgetLine`, `InternalControl`, `IntegrationConfig`, plus Balance Sheet / P&L / budget-variance report views.
**Coordination rule for future modules:** these are the *financial/GL* views — when **Module 11 (Assets)** builds the
operational asset register, **Module 3 (HRM)** builds payroll/employee masters, or **Module 7 (Projects)** builds the
operational project/WBS, those modules own the operational lifecycle and should FK to (or be FK'd by) the accounting
financial model rather than duplicating the depreciation/payroll-journal/job-cost posting — keep the *posting* in
accounting (it owns the ledger). Do NOT build a second FixedAsset/Payroll/Project posting path.

---

## L30 — Review/test agents verify *correctness*, not *UX/information-architecture* or *scope* — do a human sidebar pass per module
User reported two Accounting 2.1 issues the review/test agents (code-reviewer, explorer, frontend-reviewer,
qa-smoke-tester, test-writer) never flagged: (1) four sub-module 2.1 feature bullets (Executive Summary / Cash Flow
Widget / Alert Center / Quick Actions) all pointed at the *same* `accounting:accounting_dashboard` URL; (2)
"Forecasting" rendered "Soon". **Why the agents missed them — both were correct-by-spec, not defects:** the
qa-smoke-tester asserts every built route reverses + returns 200/302 (all four links DID work); the explorer checks
LIVE_LINKS route names *exist* (no typo), not that sibling features resolve to *distinct* destinations; "Soon" is the
intended render for any NavERP.md bullet with no LIVE_LINKS entry, and forecasting was an explicitly *deferred*
feature, so there was no route to sweep and no failing assertion possible. A blanket "no two bullets may share a URL"
test would be WRONG — many bullets legitimately share a page (Bill Capture + Bill Processing → bill_list; Payment
Collection under both AP and AR). **Rules:** (a) functional agents can't catch UX/IA quality or product-scope gaps —
budget a short *human/product pass on the sidebar* when finishing a module: for each built sub-module, confirm its
bullets land on *meaningfully distinct* destinations (if several are widgets on one page, give them anchor deep-links,
not the same bare URL), and review which bullets are still "Soon" to confirm each deferral is *intended*, not
forgotten. (b) The nav now supports `name#fragment` hrefs (`apps/core/navigation.py` `_safe_reverse`/`_is_active`
strip the fragment) — use `"app:view#section"` to deep-link dashboard/one-page widget groups, with matching `id=`
anchors (+ `scroll-margin-top`) in the template. (c) When a deferred feature is later requested, it's a normal
build (view + url + template + LIVE_LINKS entry + tests), not a "bug fix".

## L31 — "next"/`/next-module` builds ONE SUB-MODULE per run, not a whole module (auto-detect at the N.M level)
The `next-module` skill auto-detected the next *whole module* ("lowest `N` in 1..13 whose app slug doesn't exist
under `apps/`"), so once an app folder existed it jumped to the *next module entirely*. The user wants "next" to
advance **one sub-module at a time within the current module** — "if 3.1 and 3.2 are done, 'next' should build 3.3,"
not re-scaffold a whole new module. **Root cause:** the build unit was the module, but NavERP modules are huge (HRM
41 sub-modules) and are meant to grow sub-module-by-sub-module across many runs. **Fix (in
`.claude/skills/next-module/SKILL.md`):** the build unit is now a sub-module `N.M`. Auto-detect = (1) **active
module** = highest-numbered module whose `apps/<slug>` already exists (the one under construction; if none exist →
Module 1); (2) **next sub-module** = lowest-numbered `### N.M` in `NavERP.md` order with **no** `LIVE_LINKS["N.M"]`
entry in `apps/core/navigation.py` (that dict, keyed `"N.M"`, IS the built-vs-roadmap signal); (3) **rollover** to
the next module's `N.1` only once every sub-module of the active one is wired. An existing app is **extended** (append
models/views/urls, new incremental migration, extend `seed_<slug>`, add ONE `LIVE_LINKS["N.M"]` entry) — do NOT
re-touch `INSTALLED_APPS`/`config/urls.py` or re-create `apps.py`, and **update** the module's existing skill rather
than authoring a new one. Explicit args still win: `N.M` (e.g. `3.4`) → that exact sub-module; a sub-module name
(`payroll`/`offboarding`) → its `N.M`; a bare module number/name → that module's *next unbuilt* sub-module. **Rule:**
the unit of "next" is the sub-module; CLAUDE.md's Module Creation Sequence (research→todo→code→reviews→skill) runs
per sub-module, scoped to that one `N.M`.

## L32 — A staff sidebar bullet must point to a STAFF-reachable page, never a login-gated customer/partner portal page
User clicked the CRM 1.4 sidebar bullet "Customer Self-Service Portal" and got bounced to the dashboard. **Root
cause:** `LIVE_LINKS["1.4"]["Customer Self-Service Portal"]` pointed at `crm:portal_case_list`, the *customer-facing*
portal view, which is gated by `_customer_portal_access(request)` (a `CustomerPortalAccess` row with
`portal_user=request.user`). Internal staff (tenant admins/agents) are NOT portal customers, so `access is None` →
`redirect("dashboard:home")` with a "You don't have customer portal access" message. The sidebar is the *staff*
navigation, so every staff click on that bullet redirects. The review/test agents didn't catch it (per L30): the
route reverses + the gated redirect returns 302 (a valid "200/302" status), and the IDOR/portal tests assert exactly
that a non-portal user is bounced — the redirect is correct *behavior*, just wrong as a *sidebar destination*. **Fix
(`apps/core/navigation.py`):** point the NavERP *bullet* at the **staff-facing access-management** page
(`crm:customerportalaccess_list`) and demote the gated customer page to a secondary "Customer Portal" extra. This
mirrors the **already-correct 1.12 wiring**: the "Vendor/Partner Portal" bullet → `crm:partnerportalaccess_list`
(staff mgmt), with "Partner Portal" → `crm:portal_dashboard` (gated) as the extra. **Rule:** any portal/self-service
sub-module exposes TWO surfaces — a staff-facing management list (cases/access mgmt) and a login-gated
customer/partner entry. The sidebar bullet (and any staff-prominent link) MUST target the staff-facing one; the
gated portal entry, if linked at all, is a clearly-labelled secondary link that staff are expected to be redirected
from. Add this to the L30 human sidebar pass: for each portal-style bullet, click it as a *plain tenant admin* and
confirm it lands on a 200 staff page, not a redirect.

## L33 — Badge colour classes are COLOUR-named in theme.css (`badge-green/red/amber`), NOT semantic (`badge-success/danger/warning`)
Building HRM 3.12 I used `badge-success`/`badge-danger`/`badge-warning` for status/category badges, trusting the class
list quoted in the `next-module` skill + CLAUDE.md ("`.badge-success/.warning/.danger/.info/.muted`"). Those semantic
names **do not exist** in `static/css/theme.css` — it defines `.badge-green` / `.badge-red` / `.badge-amber` /
`.badge-info` / `.badge-muted` / `.badge-slate` (theme.css:284-289). A badge with a non-existent class renders as an
unstyled pill (no background/colour) — passes every GET-200/smoke/IDOR check (it's cosmetic), so only the
frontend-reviewer caught it (8 occurrences across 6 templates). The sibling reference
`templates/hrm/leave/request/detail.html:37` already shows the correct mapping:
`pending→amber, approved→green, rejected→red, cancelled/other→muted, draft→info`. **Rule:** for any status/category
badge, use the colour-named classes and mirror an existing sibling template's exact ternary — do NOT trust the
skill/CLAUDE.md's semantic-name list (it's stale). Quick check before shipping badges:
`grep -n '\.badge-' static/css/theme.css` to confirm the real class names. (The skill/CLAUDE.md class list should be
corrected to the colour names in a docs pass.) Related: L13 (agents invent utility classes that don't exist) — same
root cause, verify the class exists in theme.css before using it.
**RECURRED in HRM 3.31 (2026-07-12):** shipped `badge-success`/`-danger`/`-warning` again across
tax/salary_register/statutory report templates — frontend-reviewer caught 11 occurrences. The lesson existed but
the `grep -n '\.badge-' static/css/theme.css` check was NOT run before writing the templates. **Hardened rule:
before writing ANY new template with status/category badges, FIRST run that grep (or copy a badge line verbatim
from a sibling template) — treat it as a mandatory pre-write step, not a pre-ship check.** The stale
skill/CLAUDE.md semantic-name list is the trap; muscle-memory of "success/danger/warning" from other frameworks is
the second trap.
**RECURRED AGAIN in HRM 3.32 (2026-07-12), different class FAMILY:** shipped `<div class="stat-icon amber">` in
`predictive.html` — `.stat-icon` only defines `blue/green/orange/purple/slate` (NO `amber`/`red`), so the icon
rendered unstyled. **Generalized rule — this applies to EVERY theme.css modifier family, not just badges:** the
design system uses a FIXED, colour-named palette per component and there is NO semantic/danger variant to fall back
on. Before using any `badge-*`, `stat-icon <x>`, `text-*`, or other theme.css modifier in a new template, run
`grep -oE '\.(badge|stat-icon|text)-?[a-z]+' static/css/theme.css | sort -u` (or copy the exact class off a sibling
template) to confirm the class exists. Known-good sets: badges `badge-green/red/amber/info/muted/slate`; stat-icon
`blue/green/orange/purple/slate`. Never invent `-success/-danger/-warning/-amber/-red` for a component family that
doesn't define it.

## L34 — Tenant-admin seed password is `password` (NOT `password123` — the skills are stale) + persist sidebar scroll/expand across full-page nav
Two things from a user-reported sidebar UX fix. **(a) Credentials:** the tenant admins (`admin_acme`/`admin_globex`)
are seeded with password **`password`** — `apps/accounts/management/commands/seed_accounts.py:72`
(`create_user(..., password="password")`), and every seeder's stdout prints "admin_acme / password". The
`next-module` skill's Step 3 (and `manual-test`) say `password123`, which is **wrong** and cost a wasted preview
login. **Rule:** for any browser/`Client` login in this project use `admin_acme` / **`password`** (superuser
`admin`/`admin`, but it has `tenant=None` → sees no module data). **(b) Sidebar state:** the sidebar
(`templates/partials/sidebar.html`) is server-rendered every full-page load — `resolve_nav` correctly marks the
ACTIVE module/submodule `open` + highlights the active feature, BUT a plain `<a href>` sidebar link does a full
navigation, so the sidebar's **scroll position resets to top and any manually-expanded groups collapse** (HRM has
20+ submodules, so the active item lands far down and the user "loses their place"). Fix WITHOUT going SPA/HTMX
(which would risk breaking every page's `{% block extra_js %}` charts): persist `.sidebar` `scrollTop` + the set of
open `.nav-group`/`.nav-subgroup` (keyed by a new `data-nav-key="{{ label }}"`) to **sessionStorage** on
toggle/`beforeunload`/`pagehide`, and restore at end-of-body (pre-paint) + again in a `requestAnimationFrame` (after
Lucide icons render and shift heights); only ever ADD `.open` (never collapse the server-active group), and leave the
active `.active` highlight server-rendered so it's always fresh. First-visit fallback: center the active link in the
sidebar. Lives in `static/js/app.js` (bump the `?v=` cache-buster in `base.html`, L15). Verified in the preview:
scroll (500px) + a manually-opened extra module both survived navigating between 3.20 pages, active highlight moved
correctly, zero console errors.

## L35 — A hand-parsed POSTed `Decimal` amount needs a FULL guard chain, not just try/except-around-the-parse + an elif-with-`else`-fallthrough
Found by the code-reviewer + security-reviewer on the SAME action — HRM 3.35 `travelrequest_approve_advance`
(`apps/hrm/views.py`), which reads `advance_approved` straight from `request.POST`, `Decimal(raw)`, then validates.
Two independent bug classes hid in the "parse then compare" shape, and both recur any time a view manually parses a
numeric decision/approval input (advance approval, manual price override, ad-hoc quantity, discount %, etc.) instead
of going through a `forms.DecimalField`:
- **(a) `try/except (InvalidOperation, ...)` only guards the PARSE, not the later comparisons.** `Decimal("NaN")`,
  `"nan"`, `"sNaN"` all parse **successfully** — then the very next `if amount < 0:` raises `decimal.InvalidOperation`
  (NaN is unordered), producing an **unhandled 500**. `Decimal("Infinity")` parses too. **Rule:** immediately after a
  successful `Decimal(raw)`, reject non-finite values before ANY ordering comparison:
  `if not amount.is_finite(): <friendly error>; return`. Also cap magnitude against the field's `max_digits` ceiling
  (e.g. `>= Decimal("10000000000")` for `max_digits=12, decimal_places=2`) so an oversized value hits a friendly
  message, not a DB `DataError` on `save()`.
- **(b) A validation `elif` chain whose bounds are all conditional on optional data silently APPROVES when every
  bound is None.** The cap was `elif obj.advance_requested is not None and amount > obj.advance_requested: ...` then
  `elif obj.policy and ... and amount > cap: ...` → when `advance_requested is None` AND no policy cap applied, both
  elifs were false, so control fell to the `else` and approved **any** typed amount, unbounded. **Rule:** when a
  numeric input is only meaningful given some prerequisite (a requested amount, a configured cap), make the missing
  prerequisite an EXPLICIT rejection branch (`elif obj.advance_requested is None: <error "nothing was requested">`),
  never let it fall through to the success `else`. Think "what does each guard do when its data is absent?"
**Best fix long-term:** prefer a `forms.DecimalField(max_digits=..., decimal_places=..., min_value=0)` (which rejects
NaN/Inf/overflow for free) over hand-parsing `request.POST`; when a bespoke action truly needs raw parsing, apply the
`is_finite()` + magnitude-cap + explicit-None-branch trio. Covered now by `test_travel.py` (NaN/Infinity/garbage →
no 500; %-cap boundary 800.00 vs 800.01; `advance_requested is None` → rejected; `>= 1e10` → rejected).

## L36 — When a module ships a spine entity the ERD assigned to a LATER module, reconcile the ERD for BOTH modules in the same pass (don't just note the conflict)
Building SCM 4.1 Procurement Management, the `research` agent recommended (and I agreed) that `apps/scm` OWN the
procure-to-pay transaction tables — `PurchaseRequisition`, `RFQ`/`RFQQuote`, `PurchaseOrder`, `GoodsReceiptNote` —
even though **`NavERP-ERD.md` line 468 explicitly listed all four under Module 6 (Procurement)** and gave Module 4
only the logistics set (Shipment/Carrier/RoutePlan/…). This is the same shape as **L29**: the module that ships
FIRST owns the shared entity (that is exactly how `accounting` ended up owning the GL ledger the foundation never
built, and how CRM built its own stand-in `PurchaseOrder` for 1.12). Skipping to a later SCM sub-module just to
honour the ERD would have violated the "build the lowest unbuilt `N.M`" rule (**L31**) and left 4.1 dark for two more
modules; the ERD is a *plan* doc that has been wrong about the *as-built* spine before (that is what L28 warns about).

**Rule — the reconciliation is a required close-out step, not an optional note:**
1. **Make the ownership call explicitly** (ships-first owns it; the later module EXTENDS by FK, never re-declares —
   a second parallel schema for the same concept is the bug L29 forbids). Decide it before writing code, not after.
2. **Edit the ERD/plan rows for BOTH modules in the same change** so the doc stops contradicting the code: the
   owning module's "Adds" column gains the entities (mark them *as-built*), and the later module's row is rewritten
   to say it *extends* them by FK (its own "Adds" becomes only its genuinely-new layer — for Module 6 that is
   VendorScorecard / strategic-sourcing / e-auction / supplier-risk, not another PO). Leaving only the owning row
   updated re-creates the exact contradiction a future run will trip on.
3. **Encode the call in three durable places** so it survives context loss: a `LIVE_LINKS`/navigation comment, the
   owning model's docstring, and this lesson. SCM did all three (`apps/core/navigation.py` "4.1" banner,
   `apps/scm/models/ProcurementManagement/PurchaseOrders.py` header, here).
4. **Two `PurchaseOrder` classes now coexist on purpose** — `crm.PurchaseOrder` (1.12 lightweight quick-order,
   free-text items, no approval) and `scm.PurchaseOrder` (canonical: lifecycle + approval + amendment trail +
   3-way match). Different app_labels/tables, no collision. A future maintainer grepping `class PurchaseOrder` will
   find both; that is documented, not an accident — do NOT "dedupe" them.
Also reaffirmed by this build: line items stayed free-text (`item_description`/`sku_hint`/`uom_hint`) because
`core.Item` still does not exist (**L28** — grep-verified, not trusted from the ERD), with the future migration onto
`core.Item` recorded in each line model's docstring for when Module 5 Inventory ships. See [[next-builds-one-submodule]].

## L37 — SCM 4.3 owns the INVENTORY SPINE (`Item`/`UOM`/`Location`/`LotSerial`/`StockMove`); on-hand is derived, never stored
Applying **L36** to the biggest spine claim so far. Building SCM 4.3 Inventory Management, `core.Item`, `UOM`,
`Location`, `StockMove` and `LotSerial` still did not exist (grep-verified, per **L28**) — and unlike 4.1's free-text
line items, a *stock-control* sub-module genuinely cannot be stubbed: you cannot compute on-hand, transfers or
valuation over free text. So 4.3 built them, in `apps/scm`, per the ships-first rule.

**Placement — why `apps/scm` and not `apps/core`.** The strongest as-built precedent is the ledger (**L29**):
`accounting` owns `Currency`/`GLAccount`/`JournalEntry` — equally cross-cutting masters that every module FKs into
by string (`'accounting.Currency'`) — rather than those being retrofitted into the Module 0 foundation. Adding
models to `core` is a *foundation* change and outside a `/next-module` run's remit. So the inventory masters live in
`scm` and later modules FK `'scm.Item'`/`'scm.Location'`/`'scm.StockMove'` by string. **Module 5 (Inventory IMS) —
which is literally named for this domain — therefore EXTENDS the `scm` spine by FK and adds the operations layer
(cycle-count programs, putaway/pick, serial genealogy); it must NOT re-declare Item/Location/StockMove.**
`NavERP-ERD.md` rows 466/467 were rewritten to say exactly that (L36 step 2: reconcile BOTH rows, not just the owner).

**The invariant that makes the spine safe — copy it for any future stock/ledger work:**
1. `StockMove` is **append-only**: signed quantity (+into / −out of a location), no ModelForm, no edit/delete view,
   and `has_add/change/delete_permission → False` in the admin. A mistake is corrected by a **compensating move**,
   exactly like the `JournalEntry` reversal rule.
2. **On-hand and valuation are ALWAYS aggregates** over that ledger (`Item.on_hand()`, `_item_valuation()`), never a
   stored editable quantity — so nothing can drift from the ledger. `Item.average_cost` is a *cached display* figure
   maintained by `apply_receipt()`, explicitly NOT the source of truth for quantity.
3. `StockMove.unit_cost` **IS** the FIFO/LIFO/WAC cost layer — no separate cost-layer table is needed; the valuation
   report walks the inbound layers and consumes them by total outbound (oldest-first for FIFO, newest-first for LIFO).
4. Every stock movement goes through ONE posting service (`views/_helpers.py` `_post_stock_move`/`_post_transfer`/
   `_post_adjustment`) inside the caller's `transaction.atomic()`, with an insufficient-stock guard that reads the
   **live** aggregate so it sees moves posted by earlier lines in the same transaction. A shortfall raises
   `ValidationError` and rolls the whole post back — never a partial move.

**Two bugs this shape actually caught during the build, both invisible to a "does the page load" check:** the
happy-path transfer worked while the *guard* path 500'd (`ValidationError` wasn't imported into the views toolkit),
and the overview's stock-value aggregate needed `F`/`models` imports. **Rule:** when a feature's whole value is a
guard, test the guard, not just the happy path — and re-run the derived-quantity math after every posting change
(`on_hand` before/after, expecting an exact delta). See [[next-builds-one-submodule]].

---

## L38 — Apply the review finding, not the biggest hammer that silences it

SCM 4.4's code-reviewer flagged: a goods receipt booked in a workspace with **no stock location** transitions to
`received` (a one-way status) having posted zero moves, and the systemic failure is reported with the same wording
as an ordinary per-line SKU miss. Both halves were true.

I fixed it by making `_post_grn_receipt` **raise** when no location exists. That silenced the finding and broke
something real: 4.1 Procurement shipped standalone and is legitimately usable without the 4.3 inventory spine — a
tenant tracking orders and three-way matching against bills has nothing to post and no reason to be stopped. My
change made 4.1 hard-depend on 4.3 *configuration*. **The existing test suite caught it** (four 4.1 GRN tests went
red), not my own reasoning.

The actual complaint was *"these two failures are indistinguishable to the user"*. The right fix was to return a
separate `blocked` reason and message it separately — three lines, no behaviour change.

**Rules:**
1. Before applying a review fix, state the finding's *harm* in one sentence. If your fix prevents more than that
   harm, you have changed the product, not fixed a bug. "Refuse the operation" is the most tempting over-correction.
2. A reviewer describes a symptom from inside one sub-module. **You** own the cross-module contract they can't see —
   an agent reviewing 4.4 has no reason to know 4.1 must stand alone.
3. When a fix turns previously-green tests red, the default assumption is that **the fix is wrong**, not the tests.
   Only conclude the test was stale after naming exactly which contract changed and why deliberately (that was the
   *other* failure in this batch: `test_member_can_receive_goods_receipt` encoded the pre-4.4 rule, and receiving
   really had become a stock-moving action — so there the test was genuinely obsolete). Both look identical from
   the failure output; only the reasoning tells them apart.

**Corroborating signal is worth acting on fast.** Two agents reviewing 4.4 independently (code + security) reported
the same two ledger holes — the unguarded `_reverse_grn_receipt` and the un-frozen cycle-count sheet. Convergence
from different prompts is much stronger evidence than either report alone; both were real and both were reachable
by *ordinary* sequences (receive→putaway→cancel; start→add a row→reconcile), not crafted attacks. See
[[next-builds-one-submodule]].

---

## L39 — Check that a feature's preconditions can ever be true at the same time

SCM 4.5's review turned up two defects with one root cause. Both were mine, both passed every test I
had written, and both made a shipped feature **completely unreachable** rather than merely wrong.

1. **`salesorder_mark_invoiced` could never run.** `invoice` was a field on the order form; the form
   is editable only while `status == "draft"`; the action requires `status == "fulfilled"`. To set the
   invoice you had to be draft, to use it you had to be fulfilled — and in reality the invoice doesn't
   exist until after fulfillment anyway. Every individual rule was defensible. Their conjunction was
   empty.
2. **`ship_to_address` could never be chosen on a new order.** I narrowed the queryset to the selected
   customer's addresses (a real privacy concern — one customer's addresses shouldn't be visible while
   ordering for another). But on a *create* form no customer is selected yet, so the queryset was
   always `.none()`. The field rendered, looked fine, and was permanently empty.

**Why my tests missed both.** They exercised each rule in isolation and each rule was correct. The
write-path script drove the lifecycle but never asserted that a *fresh* form could reach every field,
and it set `invoice` directly on the model rather than through the UI. Both bugs live in the gap
*between* correct rules — which is exactly where a happy-path walk-through doesn't look.

**Rules:**
1. When a field is gated by one condition and the action consuming it is gated by another, write the
   conjunction down and ask whether anything satisfies it. If the answer is "only if the user does X
   before Y", check that X is actually possible before Y in the real workflow.
2. **A restrictive queryset is UX; validation is the guard.** Narrowing choices to prevent a bad
   selection breaks the moment the narrowing key isn't known yet. Offer the full tenant-scoped set and
   reject the invalid combination in `clean()` — that also holds against a crafted POST, which a
   narrowed dropdown never did.
3. Test forms *unbound* as well as bound. `SalesOrderForm(tenant=t).fields[f].queryset.count() > 0` is
   one line and would have caught defect 2 immediately.
4. A dead end is the failure mode this project keeps producing — `crm.Quote.quote_accept()` created
   nothing downstream for twelve CRM sub-modules before 4.5 finally wired it. When adding an action,
   ask what it *hands off to* and whether that recipient can be reached.

Also worth keeping: this round ran five reviewers with an adversarial verify pass, and the verifiers
**refuted 8 of 17 findings** — including two that were really "no problem here" written up as
findings, and one that was real but whose query-count arithmetic was ~2x overstated (the verifier
corrected the number while confirming the defect). Single-reviewer output is not a work list; making
each finding survive a skeptic is what turns it into one. See [[next-builds-one-submodule]].
