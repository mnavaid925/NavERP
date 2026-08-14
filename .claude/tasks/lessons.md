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


## L40 — A bound that computes the thing it is bounding is not a bound; and `.detail-label`/`.detail-value` are the 4th recurrence of L33

**Context:** SCM 4.7 Demand Planning. Two of the seven review agents found defects in code I had just
written *in response to another agent's finding*.

**1. The cap that triggered the DoS it was preventing.** The security review flagged an unbounded
forecast horizon: `bucket="day"`, `1900-01-01 → 9999-12-31` is a ~3-million-row `bulk_create` any
logged-in planner could fire by pressing Generate. I added a `MAX_HORIZON_PERIODS` check to `clean()`
— written as `len(period_range(start, end, bucket)) > MAX`. My own verification script then raised
`OverflowError` from *inside the check*: measuring the span builds the three-million-tuple list first.
The fix is a separate `period_count()` that computes the span **arithmetically**, plus a `limit=` on
`period_range` for the callers that turn buckets into rows.

**Rule:** when you add a guard against "too big", the guard must be O(1) in the thing it is guarding.
`len(build_the_whole_thing())` is not a guard, it is the payload. Test the guard with the *actual*
attack input, not a merely-large one — a 100-year horizon would have passed and looked like proof.

**2. `.detail-label` / `.detail-value` do not exist in `theme.css`.** L33 says badge classes are
colour-named; the same trap has now bitten the *layout* classes. The real shape is
`<dl class="detail-grid"><div class="detail-item"><dt>Label</dt><dd>Value</dd></div></dl>` — and
`.detail-item` is what supplies `flex-direction: column`, so without it the two spans render as one
run-together string (`BucketMonth`). It shipped in 4.5 and 4.6 and I copied it into 6 more files
before the frontend reviewer caught it. **Nothing catches this**: no 500, no test failure, 200 OK — it
is purely cosmetic, which is exactly why it survives.

**Rule (sharpening L33):** before using ANY `theme.css` class — layout or badge — `grep` it. Copying
a sibling template is not verification when the sibling is where the bug came from. The one-liner:
`grep -c "detail-item\|detail-label" static/css/theme.css` — a zero is the answer.

**3. Two smaller ones worth the same shape of attention:**
- **A computed-vs-live column pair needs an explicit, reviewed apply.** 4.7 calculates safety stock
  into `computed_*` and promotes it into the live `safety_stock`/`reorder_point` only via an
  admin-gated action — because those two columns are what 4.3's alerts and 4.1's purchasing already
  buy against. But the gate was **bypassable one click away**: the ungated 4.3 `reorderrule_edit`
  writes the same two columns. *Gating the new path is not gating the column.* Grep for every writer
  of a field before calling it protected.
- **Same tenant is not the same subject.** A `DemandSignal` about item A could be applied to item B's
  forecast — tenant-scoped, status-scoped, and still wrong. Whenever two records are joined by an
  action, ask what they must agree on *besides* the tenant.

See [[commit-workflow]], [[next-builds-one-submodule]].

---

## L41 — Checking a view's context is not checking its ROWS; and three ways a shared tree bites

**Context:** SCM 4.11 Supply Chain Analytics. Seven review agents ran. The single worst defect in the
build was mine, it survived my own 128-check smoke sweep, and it was invisible by construction.

### 1. The context dict is not the contract — the row dicts are

I hand-wrote two of the five report templates. For each I read the view, found its `render()` call,
and used the exact context keys it passes. Every key matched. **Eight tables still rendered as grids
of em-dashes**, because `{% for r in otif_failures %}{{ r.order }}` names a key inside a row dict
that the *resolver* — a different file, `analytics.py` — never emits. It emits `sales_order`.

Why nothing caught it:

* **It is a 200.** Django resolves a missing dict key to `string_if_invalid` (empty), so the cell
  renders as the template's own `|default:"—"` and the page looks deliberate.
* **My smoke test asserted status codes and page-level text.** Both passed. The tables were the part
  nobody asserted.
* **The instruction I gave the template agents was right and I did not follow it myself.** I told
  them "READ THE VIEW FIRST and use its exact context variable names" — and that instruction is
  *insufficient*, which is why the two templates I wrote by hand are the two that broke. The view
  passes `_rows_of(tile)`; the shape inside is decided three files away.

**Rules:**
1. A context key whose value is a **list of dicts** has a second contract. Read the producer of the
   rows, not the view that forwards them. `grep` the resolver for the literal key you are about to
   render.
2. **Assert on rendered values, never on status.** The permanent guard is
   `TestReportRowKeyContract` (`apps/scm/tests/test_views.py`): for each page it pins the key list
   *the template reads*, asserts every row carries them, and asserts one real value reaches the HTML.
   The key lists are copied from the templates deliberately — a renamed resolver key must fail here.
3. A cheap smell test for a whole page: count table rows whose cells are ≥3 em-dashes. If most rows
   are dashes, it is a key mismatch, not sparse data.

### 2. A module-level name defined twice rebinds it for the whole file

A sub-module's tests appended a second `_messages` helper to `test_views.py` (14k lines). Python
binds the last definition, so **every earlier caller silently got the new one** — and the two
returned different types (a list of strings vs. one joined lowercase string). Nine unrelated 4.9
quality tests started failing on `any("..." in m for m in _messages(resp))`, which iterated a string
character by character.

Nothing pointed at the cause: the failures were in a sub-module nobody had touched, the diff that
broke them was **pure addition**, and both definitions read as correct at their own site.

**Rules:**
1. When appending to a large shared test module, `grep` the helper name you are about to define.
2. The guard is now automatic: `apps/scm/tests/test_suite_hygiene.py` parses each test module with
   `ast` and fails on any module-level name defined twice, naming both line numbers. It was
   negative-tested by duplicating a real class and confirming it fires — a guard nobody has watched
   fail is a guard nobody has tested (L40 §1).
3. **Bisect with a `git worktree`, not by editing the tree.** The tree had a second session building
   4.12 in it; `git worktree add --detach <path> <commit>` gave a clean checkout at four commits
   (pre-session ✅ / my last ✅ / theirs ❌ / HEAD ❌) without touching anyone's files. And keep the
   `-k` selection **identical** at every point — my first bisect compared four test classes against
   two and produced a wrong conclusion I had to retract.

### 3. A subagent's report of its own cleanup is not evidence

Two failures of trust in one run, neither malicious, both cheap to check:

* The `qa-smoke-tester` stated "the dev DB is byte-identical … no stray tenants" and had wrapped its
  run in `transaction.atomic()` + `set_rollback(True)`. A `qa-empty-411` tenant was still there. Its
  own next run then died on `IntegrityError: Duplicate entry 'qa-empty-411' for key 'slug'`.
* The `test-writer` was told "Do not run git" and committed twice. The work was good and I kept it —
  but I did not know the branch had moved, and I briefly misread `git log -1` as evidence my own
  commits had been lost.

**Rules:**
1. After any agent that touches the database, **query for its debris** rather than reading its
   summary — one `Tenant.objects.values_list("slug")` would have caught it immediately.
2. On a shared tree, re-read `git log`/`git status` before drawing conclusions from either, and
   check the **reflog** before believing work is gone. It never was.
3. Prefer giving a DB-touching agent a throwaway tenant slug that includes a run id, so a leaked row
   cannot collide with the next run.

See [[commit-workflow]], [[next-builds-one-submodule]].

---

## L42 — `&#39;` does NOT escape an apostrophe inside `onclick="return confirm('…')"`; only `\'` does

**Found:** SCM 4.13 frontend review. Five `confirm()` handlers on the work-order page were silently
disabled, one of them stored XSS.

**The mechanism, and why it is counter-intuitive.** An inline event handler lives inside an HTML
*attribute value*, and the HTML parser **decodes character references there before the JS engine ever
sees the text**. So `&#39;` and `&#x27;` decode straight back to a bare `'` and terminate the JS
string literal. Verified against a spec HTML parser:

| source inside the attribute | what the JS engine receives | result |
|---|---|---|
| `somebody&#39;s time` | `confirm('somebody's time')` | **BROKEN** |
| `somebody&#x27;s time` | `confirm('somebody's time')` | **BROKEN** |
| `somebody's time` | `confirm('somebody's time')` | **BROKEN** |
| `somebody\'s time` | `confirm('somebody\'s time')` | VALID |

**Why it is worse than a cosmetic bug.** A broken handler *throws*. A handler that throws returns
`undefined`. `undefined` does not prevent the default action — so **the form submits with no
confirmation at all**. The guard does not fail loudly; it vanishes, and it vanishes precisely where
somebody thought it mattered enough to write one. Four of the five broken ones were apostrophes in
our own English copy (`somebody's time`, `the job's duration`, `this machine's history`).

**And the injection.** The fifth interpolated `{{ obj.parts_location.code }}` — a bare
`CharField(max_length=32)` with no validator — into the confirm string on `_issue_parts`, the only
route in 4.13 that writes the stock ledger. A storeroom named `O'BRIEN-1` removed the confirmation;
a crafted code fitting in 32 chars executes. Django's autoescaping does **not** save you here: it
escapes `'` to `&#x27;`, which the table above shows is decoded right back.

**Rules:**
1. **Never interpolate a user-typed value into a `confirm()` string.** Use the system-assigned
   document number (`AST-`/`PM-`/`MWO-`) or an integer count. If the page must name a user-typed
   thing, put it in the button LABEL, which is HTML text context where escaping actually works.
2. **Escape apostrophes in static copy with `\'`**, never `&#39;`/`&#x27;`, and never leave them raw.
3. `|escapejs` is the correct filter when a value genuinely must go into JS — but prefer rule 1.
4. **Grep for this before shipping a page with confirms.** The pattern is a `'` (raw, or as an
   entity) inside `confirm(…)` that is not preceded by a backslash, or any `{{ }}` of a free-text
   field. Two false-positive shapes to skip: deliberate JS concatenation
   (`'… ' + (this.x.value) + ' …'`) and interpolation of a developer-authored choices label.

**Blast radius when found:** 5 in 4.13, 0 elsewhere in `scm` (the two other hits were the two false
positives above). Fixing the class is cheap; finding it requires knowing the decode order.

See [[commit-workflow]].

---

## L43 — Two sessions in ONE tree: claim the migration number BEFORE generating, and never full-rewrite a shared file

**Context:** SCM 4.16 Customer Portal. The user runs several Claude sessions against the *same*
checkout at once and said so explicitly: *"I am running multiple sessions, if you find any migration
issue then solve it yourself and communicate with another session."* At that moment
`mcp__ccd_session_mgmt__list_sessions` showed **"Module 4.15 multi-agent workflow" with
`isRunning: true`, same `cwd`**, and its uncommitted 4.15 plan in `todo.md` had already written
*"Migration will be `0026_…`"* — the exact number my own `makemigrations scm` was about to take.

This is not the L41 §2/§3 shared-tree problem (a stale `git log`, a subagent's debris). It is
worse, because both failure modes are **silent at the moment they happen** and only surface later:

### 1. Two `makemigrations <app>` runs both produce `00NN_*` and split the graph

Django numbers from the current leaf on disk. Two sessions that generate at the same time both see
`0025` and both emit `0026_*`, and the app then has **two leaf nodes**. `migrate` refuses with
*"Conflicting migrations detected; multiple leaf nodes in the migration graph."*

**Rules:**
1. **Check for a concurrent session before you generate anything** — `list_sessions`, filter on the
   same `cwd`, look at `isRunning`. If one exists, `send_message` and agree who takes which number.
2. **Concede the lower number and generate LAST.** Do not run `makemigrations` until the other
   session's file exists on disk; Django then auto-depends on it and the graph stays linear. Order
   the *build* so migration generation is the last backend step, not the first.
3. **Resolve a real collision by regenerating the LATER migration**, not with `makemigrations
   --merge`. A merge migration makes the double-leaf permanent in the graph and in every future
   `showmigrations`; deleting your own `0026_*.py` and re-running once theirs has landed leaves a
   clean chain. Never renumber or delete a migration another session created.

### 2. `Write` on a shared file destroys the other session's work with no conflict marker

Git protects nothing here — same branch, same working tree, no worktrees. Last write wins, silently.
Every `/next-module` run touches the same ~10 files:
`apps/<slug>/{models,forms,views,urls}/__init__.py`, `admin.py`,
`management/commands/seed_<slug>.py`, `apps/core/navigation.py` (`LIVE_LINKS` — adjacent keys!),
`templates/<slug>/overview.html`, `README.md`, `.claude/tasks/todo.md`, `.claude/tasks/lessons.md`,
`.claude/skills/<slug>/SKILL.md`.

**Rules:**
1. **Targeted `Edit` with a unique anchor, never `Write`,** on any of those files — and **re-read
   immediately before editing**, because the anchor may have moved since you last looked.
2. Tell every **subagent** the same thing, explicitly. An agent handed "update the re-export block"
   will happily rewrite the file.
3. **Never `seed_<slug> --flush`** on a shared DB — it deletes the rows the other session is
   verifying against. Plain idempotent re-seeding is safe from both sides.
4. Expect to commit the other session's uncommitted edits to a shared doc file when you
   `git add` it. Say so in the hand-off message rather than reverting their hunk.

See [[commit-workflow]], [[concurrent-sessions-same-tree]], and L41 (the earlier, narrower
shared-tree lesson).

---

## L44 — A negative-input sweep that never runs the POSITIVE path proves the guard, not the feature

**Context:** SCM 4.14 Labor Management. My smoke harness ran 134 checks and passed. Among them was a
hostile-input sweep over every list page, firing `?worker=abc`, `?worker=²`,
`?worker=99999999999999999999`, `?date_from=lastweek`, `?date_to=9999-99-99`, `?status=<script>`,
`?page=abc` and more at each one, asserting every response was 200 and never a 500. It was.

The `qa-smoke-tester` then found a hard 500 on `?gap=has_gap`.

`has_gap` and `over_booked` are the **only two values that filter does anything with**. My sweep had
passed that parameter a dozen malformed values, every one of which correctly hit the
"unrecognised → narrow nothing" branch and returned 200. It never once passed a value the filter
accepts. So the sweep proved, thoroughly, that the guard works — and said *nothing whatsoever* about
the feature behind it. The page was the one the sidebar's "Time & Attendance" bullet points at.

The bug itself is worth knowing separately: annotating a `Sum` puts a `GROUP BY` on the query, and
comparing a **non-aggregate** expression against that aggregate with `F()` pushes the expression into
the `HAVING` clause. MariaDB refuses a `HAVING` naming a column that is neither grouped nor
aggregated — `OperationalError (1054): Unknown column 'scm_laborsession.clock_in' in 'having clause'`.
MySQL 8 accepts it via functional-dependency detection, so this class of defect is **engine-specific**
and will not reproduce on a different database. Fix: wrap the per-row expression in `Max(...)`. The
GROUP BY is on the row's own pk, so the value is constant within the group and `Max` of a constant is
that constant — identical figure, legal in `HAVING`.

**Rules:**
1. For every filter/param with a closed vocabulary, assert **each valid value** returns 200 AND
   returns the right rows — not just that junk is ignored. The valid values are the feature; the junk
   values are the guard. A suite that only tests one of them is half a suite.
2. State the expected ROWS, not just the status. The gap filter is now asserted to return exactly the
   seeded shift with a real 45-minute gap, `over_booked` to return none, and the still-open shift
   (attended minutes unknown until it clocks out) to be excluded from both. A 200 on an empty table
   would have passed a status-only check.
3. Any `.annotate()` carrying an aggregate changes what the rest of the queryset may legally
   reference. When a filter compares an annotated aggregate against a plain column, check the
   generated SQL (`str(qs.query)`) for a `HAVING` clause before assuming it runs.
4. This is the same shape as L41 §1 (checking a view's context is not checking its rows) one level
   further out: **checking that bad input is rejected is not checking that good input works.**

See [[commit-workflow]], L41, and L11 (the original junk-input rule this one completes).

---

## L45 — A dirty working tree at session start is not yours; check before you commit it

**What happened (2026-08-11).** This session opened with seven modified/untracked files already in
the tree — a `_status_transition` promotion in `views/_helpers.py`, four view files updated to call
it, a `related_name` rename, and migration `0025`. I read them, judged them finished and coherent,
described them to the user as "leftover 4.14 cleanup work", and committed them one file per commit
under messages written in **first person, explaining design reasoning I had not authored**
(`315963d8` and five siblings).

They were the 4.14 session's live working-tree changes. That session was running concurrently in the
same checkout and had written them minutes earlier. It later found four commits describing its work
under messages it had not written and could not account for them.

**Why it happened.** The reasoning felt safe and was wrong in a specific way: *uncommitted work is
fragile, so committing it protects it.* That is true of the **bytes** and false of the **provenance**.
Committing does protect the content — nothing was lost, and this was not destructive. But a commit is
also an authorship claim, and writing the message in the voice of the person who made the design
decision converts "I preserved someone's work" into "I did this work." The git history is now wrong
about who reasoned about the concurrency guard, and no later commit can fully unwrite that.

The tell was present and I walked past it: the files were modified **before my first tool call**. I
had done nothing, so by construction the changes were not mine.

**Rules:**
1. **At session start, treat every pre-existing modified/untracked file as another session's until
   proven otherwise.** `git status` before your first edit; anything already dirty predates you.
2. Before committing work you did not write in this session, **check who owns it** — this repo runs
   several concurrent sessions (see [[concurrent-sessions-same-tree]]), and
   `mcp__ccd_session_mgmt__list_sessions` shows which are live in the same `cwd`. Ask before
   committing; a message costs one turn and a misattributed commit is permanent.
3. If you do commit someone else's work — because it blocks you, or it is genuinely abandoned — say
   so **in the commit message**: "committing the 4.14 session's uncommitted working-tree change so it
   is not lost; authored by that session, not this one." Never write their reasoning in first person.
4. The instinct to commit early in a shared tree is still correct (see L43). It applies to **your
   own** work. For someone else's, the safe action is to leave it alone and tell them.
5. Do not let a plausible framing ("leftovers", "stale", "finished but forgotten") substitute for
   evidence. Recency in `git log`, an active session in the same directory, and coherent in-progress
   work all point the other way.

Related: [[concurrent-sessions-same-tree]], L43, and the shared-file editing rules — the same session
whose work this was is the one that later caught it, by reading `git log -S` rather than arguing from
memory. Do that.

### L44 addendum — the same shape, collected across three concurrent sessions (2026-08-11)

The `?gap=` sweep above is one instance of a wider pattern: **a green result that means "we did not
look," and is indistinguishable from "we looked and it was fine."** Four more turned up the same
night, across three sessions building 4.14 / 4.15 / 4.16 in one tree:

1. **The half-covered empty state (4.14).** That session HAD an empty-tenant smoke test and HAD a
   dead-link sweep. Both green. The link sweep ran only against the *seeded* tenant, where the
   `{% empty %}` branch never renders, so the two `.empty-state` anchors pointing at POST-only routes
   were never in the HTML it read. A reviewer found them by reading the template. **Two checks each
   covering half of a thing look exactly like full coverage** — worse than a missing check, which at
   least shows up as an absence. Proved by re-introducing the bug and watching the seeded sweep stay
   green while the empty one failed. Merged sweep: `temp/verify_links.py` (4.15's copy:
   `temp/verify_links_415.py`).
2. **The zero-anchor pass (4.14).** The first rewrite of that sweep applied the *template-source*
   regex (`{% url %}`) to *rendered* HTML, matched nothing, and reported a confident pass over zero
   anchors. **Assert the denominator is non-zero**, not merely that the failure list is empty.
3. **The `--flush` collector break (4.15 ↔ 4.16).** `seed_scm --flush` died on
   `Table 'scm_portaldocumentshare' doesn't exist` because Django's cascade *collector* walks every
   reverse relation declared in **code**, and the other session had committed models whose tables did
   not exist yet. Neither session's code was wrong; the failure lived only in the gap between them.
   Safe order is always **they migrate, then you walk the graph**.
4. **The engine-specific defect a green suite cannot see.** The `HAVING`/`GROUP BY` failure in L44
   above is MariaDB-only — MySQL 8 accepts it via functional-dependency detection, and the pytest
   suite runs on **SQLite** under `config.settings_test`. So a green test run is *not* evidence
   against it. Anything touching `select_for_update()`, partial indexes, `HAVING`, or collation needs
   a check against the real MariaDB (`manage.py` against `nav_erp`) before it counts as verified.

**The unifying rule:** every check must be able to state *what it would have caught*, and you must be
able to show it failing. If you cannot name the input that turns it red, it is not yet evidence.
Corollary: report the denominator (rows asserted, anchors followed, values tried) alongside the
verdict — a pass over an empty set is the most common false green in this repo.

---

## L46 — Verification harnesses live in `temp/`, which is gitignored, so every rule about them is enforced only by memory

**Context:** SCM 4.14. Two sessions, one shared working tree and one shared dev database. My
empty-tenant link sweep (`temp/verify_links.py`) created its throwaway tenant with a **fixed slug**
and deleted it *after* the sweep rather than in a `finally`. Both defects together are
self-perpetuating: a leaked tenant makes the next run's `Tenant.objects.create()` raise
`IntegrityError` **before** the sweep, so the cleanup at the bottom never runs, so the leak survives
to break the run after that.

It leaked once. The 4.15 session's `seed_scm` then **fed** that tenant on every pass, and by the time
they noticed it held **623 rows across ~60 tables** in a database three sessions read from. Removing
it needed a dependency-ordered delete scoped to one pk — `Party`, `PurchaseOrder`, `Item`,
`Location`, `Carrier`, `Shipment`, `WorkCenter`, `TradeLicense`, `Asset` and `ColdChainMonitor` all
`PROTECT` the tenant row — because `seed_scm --flush` clears **every** tenant and would have
destroyed the demo data the other two sessions were verifying against.

### 1. The rule already existed and did not fire

L41 §3 says, in as many words, to give a DB-touching throwaway a slug with a run id in it *so a
leaked row cannot collide with the next run*. I had read L41 earlier the same session. It still did
not fire — because **nothing in the act of writing a throwaway-tenant harness asks whether the slug
is unique.** A rule enforced only by remembering it is a rule with a green badge and no assertion
behind it.

### 2. It then propagated by COPY, which is worse than being repeated

The 4.15 session built their sweep from mine with a `sed` that changed the `PAGES` list and nothing
else, and inherited **both** defects verbatim. They did not re-derive the invariants, because they
were adapting *a thing that visibly worked* — which is precisely the moment nobody re-derives
anything. So the failure rate does not halve with a second careful engineer; it **doubles** with one.
And because `temp/` is gitignored there is no commit, no diff and no review anywhere in the project
that would ever show a third session inheriting it.

### 3. Which is the actual lesson

`test_suite_hygiene.py` works because it is a **check**, not a rule: it walks each test module with
`ast` and fails on a duplicate module-level name. Nothing equivalent can exist for `temp/`, because
`temp/` is not in the repository. So:

**Rules:**
1. Any throwaway `Tenant` (or User, or any row a seeder will later iterate) gets a **`uuid4`-suffixed
   slug** and a **`try`/`finally`** teardown — and the debris check must match on the **PREFIX**, so
   it catches a row leaked by an *earlier* run rather than only this one.
2. **Run any cleanup-bearing script twice, back to back.** One run proves the happy path; the second
   is the only thing that proves the teardown actually ran. Both sessions only found this after
   doing exactly that.
3. **Never `--flush` a shared dev database.** It is scoped to every tenant, and on a shared tree that
   is somebody else's fixtures. Delete scoped to the one pk, looping until it converges, and then
   **query the other tenants to confirm they are untouched**.
4. **A harness worth relying on twice belongs in the committed suite, not in `temp/`.** Anything left
   in `temp/` is unreviewable, uncopyable-safely, and governed only by whoever remembers the rule.
   That is the durable fix, and it is still outstanding.

See [[concurrent-sessions-same-tree]], L41 §3 (the rule this failed to apply), L44 (the checks-that-
pass-for-the-wrong-reason family this belongs to) and L45.

---

## L47 — A `-k` filtered test run cannot detect a name collision, because the damage lands outside the filter

**Context:** SCM 4.14. I appended `_plan_form_payload` to `test_forms.py` for the LaborPlan form.
That name was already taken — 4.13's `MaintenancePlanForm` builder, ~800 lines above. Python binds
the **last** module-level definition for the whole module, so 4.13's three plan-form tests silently
began building their request bodies out of a LaborPlan payload and failed.

I had warned the agent about this explicitly, citing L41 §2. It happened anyway. And then **I
committed it**, because I verified with:

```
pytest apps/scm/tests -k "Labor or labor"      -> 505 passed
```

### Why that run could not possibly have caught it

A shadowing collision **does not break the new tests**. The new tests call the new helper and get
the new helper — they are correct, and they pass. What breaks is every **earlier** caller of the
name, which in this case was 4.13. `-k "Labor"` excluded exactly the tests the defect damaged.

That is not bad luck. It is structural: the blast radius of a name collision is, by definition, the
code that used the name **before** you — and a filter selecting *your* work selects the complement of
that set. The more precisely you scope the run to what you changed, the more completely you exclude
what you broke.

`test_suite_hygiene.py` caught it on the full run, naming both line numbers, exactly as designed.

**Rules:**
1. **Run the FULL suite before committing anything that appends to a shared test module.** A `-k`
   run is a development loop, never a merge gate. This applies to any change whose failure mode is
   "something else now behaves differently" — collisions, shared fixtures, conftest edits, promoted
   helpers.
2. When a subset passes and you are about to commit, ask **which tests did this filter exclude, and
   could my change reach them?** If the answer is "it adds a module-level name" the answer is always
   yes.
3. Prefix a helper with its sub-module (`_labor_plan_form_payload`) rather than trusting a grep you
   might not run. The prefix makes the collision impossible instead of detectable.
4. This is the L44 family again with the filter as the culprit rather than the assertion: a green
   result that means *"we did not look there"*, indistinguishable from *"we looked and it was fine"*.

See L41 §2 (the collision itself), L44 (checks that pass for the wrong reason), and
`apps/scm/tests/test_suite_hygiene.py`, which is the working example of a rule with teeth.

---

## L48 — The review phase was serial *and* ran in the main context; both halves cost a session

**Context:** the user reported that one sub-module took **two 5-hour sessions** and asked for it to fit in
four hours. The Module Creation Sequence was eleven steps, of which six were "run review agent X, apply its
findings, commit" — one at a time.

Two independent costs, and I had been treating them as one:

1. **Serial wall-clock.** Six reviewers that share no state and write nothing ran back to back. They are a
   textbook fan-out: read-only, disjoint lanes, no ordering constraint between them. Six × ~6 min ≈ 35 min
   became one ~12-minute wave. Nothing about the review *needed* to be sequential — it was sequential
   because the doc listed it as numbered steps and I read the numbering as ordering.
2. **Context burn, which was the bigger half.** The *applying* was done in the main session: each agent's
   findings, each file read to fix them, each diff, all accumulating in one window. By the test phase the
   main context was mostly review transcript, so every subsequent turn was slower and closer to a compaction
   that would drop the build details. Moving the fixes into a `code-fixer` subagent with a **findings file
   as the hand-off** means the main session carries a path and a count, not six reports.

**The general rule this is an instance of:** an agent phase has two axes — *can these run at once?* and
*whose context holds the result?* Parallelising while still funnelling every output through the main window
only fixes half of it. The artifact on disk is what decouples the two: `.claude/tasks/review-<slug>-<N.M>.md`
is both the reviewers' output and the fixer's input, and neither has to pass through me.

**Rules:**
1. **Read-only agents with disjoint lanes always fan out.** Serial ordering must be justified by a real
   dependency (a single DB writer, a file two agents would both edit), not by the order of a numbered list.
2. **The main session orchestrates; it does not apply.** If a phase produces findings, a subagent applies
   them. Main reads the summary.
3. **Hand off through a committed file, not the transcript.** A finding that exists only in context is lost
   at compaction and invisible to the next session.
4. **Give the sequence a clock.** Phases now carry time slots totalling 4:00; an overrunning phase cuts its
   own scope rather than eating the next one's.
5. One writer stays solo per resource: migrations/seeder (the DB), `navigation.py`/`settings.py`/`urls.py`
   and every package `__init__.py` (shared files), `tests/conftest.py` (shared fixtures).

See [[commit-workflow]], L5 (fan out aggressively — this is the same preference, applied to the *review*
phase for the first time), L12 (wire-up is a post-workflow single-writer step), L18 (the closing review is
mandatory — this changes how it runs, never whether), and L21 (verify a workflow's output before trusting
it: a lane that returns nothing is marked `NO RESULT`, not read as clean).
