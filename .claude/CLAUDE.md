Here is the text extracted from the image:

### **Workflow Orchestration**

**1. Plan Mode Default**

* Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
* If something goes sideways, STOP and re-plan immediately – don't keep pushing
* Use plan mode for verification steps, not just building
* Write detailed specs upfront to reduce ambiguity

**2. Subagent Strategy**

* Use subagents liberally to keep main context window clean
* Offload research, exploration, and parallel analysis to subagents
* For complex problems, throw more compute at it via subagents
* One task per subagent for focused execution

**3. Self-Improvement Loop**

* After ANY correction from the user: update `.claude/tasks/lessons.md` with the pattern
* Write rules for yourself that prevent the same mistake
* Ruthlessly iterate on these lessons until mistake rate drops
* Review lessons at session start for relevant project

**4. Verification Before Done**

* Never mark a task complete without proving it works
* Diff behavior between main and your changes when relevant
* Ask yourself: "Would a staff engineer approve this?"
* Run tests, check logs, demonstrate correctness

**5. Demand Elegance (Balanced)**

* For non-trivial changes: pause and ask "is there a more elegant way?"
* If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
* Skip this for simple, obvious fixes – don't over-engineer
* Challenge your own work before presenting it

**6. Autonomous Bug Fixing**

* When given a bug report: just fix it. Don't ask for hand-holding
* Point at logs, errors, failing tests – then resolve them
* Zero context switching required from the user
* Go fix failing CI tests without being told how
* Use the monitor tool 

---

### **Module Creation Sequence (MANDATORY)**

Whenever you create a **new module or sub-module** (especially via `/next-module`), follow this exact sequence. It **starts with research and planning** (`research` → `todo`) so the build is driven by what the best products in the domain actually do, *then* writes the code, *then* runs the review agents. Each step ends with `git add` + `git commit` (one file per commit, PowerShell-safe). **Never run `git push` at any step** — the user pushes manually.

1. **Run the `research` agent** — research the ~10 leading commercial software products in the module's domain, read their feature sets, and write a deduplicated, prioritized feature catalog to `.claude/tasks/research-<slug>.md` (features grouped by NavERP.md sub-module, mapped to the unified core spine, with a recommended 4–8-model build scope). Then `git add` + `git commit` that file. Do NOT `git push`.
2. **Run the `todo` agent** — feed it the `research` output; it turns the specialized features into a checkable build plan in `.claude/tasks/todo.md` (the models + their fields/choices **driven by the researched features**, plus backend/wire-up/templates/verify/close-out items). Then `git add` + `git commit` that file. Do NOT `git push`.
3. **Write the module code** — implement the module per the `todo` plan, then `git add` + `git commit`. Do NOT `git push`.
4. **Run the `code-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
5. **Run the `explorer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
6. **Run the `frontend-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
7. **Run the `performance-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
8. **Run the `qa-smoke-tester` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
9. **Run the `security-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
10. **Run the `test-writer` agent** — apply its output, then `git add` + `git commit`. Do NOT `git push`.
11. **Create the module's Claude Code skill** — author `.claude/skills/<module-slug>/SKILL.md` documenting the new module, then `git add` + `git commit`. Do NOT `git push`. (See **Per-Module Skill (MANDATORY)** below.)

**Rules for this sequence:**

* Run the agents **in this order, one at a time** — do not skip a step and do not reorder. **`research` runs first, then `todo`, then "Write the module code", then the review agents** as listed.
* The `research` step produces `.claude/tasks/research-<slug>.md`; the `todo` step produces `.claude/tasks/todo.md` from it — commit each as its own file.
* After each agent step, commit the resulting changes before moving to the next agent (still one file per commit).
* `git push` is **never** part of this sequence — stop at `git commit` every time.
* If an agent reports no changes are needed, note that and proceed to the next step (no empty commit required).

---

### **Per-Module Skill (MANDATORY)**

Every time you finish a **new module** (a Django app under `apps/<slug>`), you MUST create a dedicated Claude Code skill for it. This makes future work on that module fast and consistent (the skill is the module's living "how to work on me" guide).

1. **Location & name:** create `.claude/skills/<module-slug>/SKILL.md` where `<module-slug>` is the app slug (e.g. `crm`, `accounting`, `inventory`). The skill `name` is the slug (or `<slug>-module`).

2. **Frontmatter** (YAML) is required:
   * `name:` — the slug.
   * `description:` — one line that states **what the skill covers and when to trigger it**, with explicit trigger phrases, e.g. *"Work on the CRM module (leads, opportunities, contacts). Use when the user asks to add/change/debug anything under apps/crm or templates/crm, or invokes /crm."*

3. **Body** must document the **as-built** module so it can be worked on without re-reading everything:
   * **Overview** — what the module does (mirror its `NavERP.md` section) and its app path.
   * **Models** — each model + key fields, choices, and which **core-spine** entities it reuses (`core.Party`, `core.Item`, `JournalEntry`, etc.) vs. adds.
   * **URLs / routes** — the `app_name` and url names (list/create/detail/edit/delete) + any custom actions.
   * **Templates** — the `templates/<slug>/` pages and the shared patterns/partials they use.
   * **Seeder** — the `seed_<slug>` command and the demo data it creates.
   * **Conventions & gotchas** — tenant scoping, the context-var contract, any module-specific rules.
   * **Common tasks** — concrete steps for "add a field", "add a new model + CRUD", "add a filter", "extend the seeder".
   * **Sidebar wiring** — the `LIVE_LINKS` entries added in `apps/core/navigation.py` for this module.

4. **Accuracy & upkeep:** the skill must reflect the real code (correct paths, url names, field names). When the module changes later, update its skill in the same change.

5. **Commit it** as its own file (one file per commit, PowerShell-safe). **Never `git push`.**

> Module 0 is the foundation; its reference skills already exist (`next-module`, `dump-module`, `sqa-review`, `manual-test`). Modules **1–13** each get their own skill via this rule.

---

### **Task Management**

1. **Plan First**: Write plan to `.claude/tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `.claude/tasks/todo.md`
6. **Capture Lessons**: Update `.claude/tasks/lessons.md` after corrections

---

### **Core Principles**

* **Simplicity First**: Make every change as simple as possible. Impact minimal code.
* **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
* **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

---

### GIT Commit Rule

* Whenever you create a new file or update a file or delete a file. You should do a git commits.
* git commit should be in details about new changes, update or add features in detail.
* eg: 
git add 'src/file.js'
git commit -m 'some example changes'.

**STRICT — ONE FILE PER COMMIT (no exceptions):**

* **Never** combine multiple files into a single `git add` / `git commit` pair, **even if they're in the same folder, share a feature, or look like a "set"** (e.g. `lead_list.html` + `lead_form.html` + `lead_detail.html` of the same module).
* **Wrong** (this is what NOT to do):
  ```
  git add 'templates/crm/lead_list.html' 'templates/crm/lead_form.html' 'templates/crm/lead_detail.html'; git commit -m 'feat(crm): lead templates'
  ```
* **Right** — one `git add` + one `git commit` per file, every time:
  ```
  git add 'templates/crm/lead_list.html'; git commit -m 'feat(crm): lead list template'
  git add 'templates/crm/lead_form.html'; git commit -m 'feat(crm): lead form template'
  git add 'templates/crm/lead_detail.html'; git commit -m 'feat(crm): lead detail template with activity timeline'
  ```
* Each commit message should be specific to that one file's content — don't reuse the same message across multiple commits.
* If a change spans 30+ files, the snippet block IS 30+ commits. Length is fine — bundling is not.
* Empty `__init__.py` files still get their own commit.

**Shell Compatibility (CRITICAL — user runs PowerShell on Windows):**

* The user's shell is **Windows PowerShell (5.x)** — `&&` is NOT a valid statement separator and WILL fail with `ParserError`.
* When combining commands on one line, use `;` as the separator, NEVER `&&`.
* When providing "all commits in one copy" / "single copy" / bulk-commit output, ALWAYS output in PowerShell-compatible form:
  * ✅ Correct: `git add 'file.py'; git commit -m 'msg'`
  * ❌ Wrong:  `git add 'file.py' && git commit -m 'msg'`
* Default to PowerShell-safe syntax for ALL shell snippets intended for the user to run directly (not just git).
* Note: `;` runs the next command even if the first fails. If stop-on-failure is required, output commands on separate lines instead of chaining.

---

### Filter Implementation Rules (Preventing Recurring Issues)

Every list page in this application MUST have working filters. When creating or modifying any list view/template, follow these mandatory steps:

1. **View must pass ALL context needed by template filters:**
   - For status dropdowns: pass `status_choices` (from `Model.STATUS_CHOICES`)
   - For FK dropdowns (categories, items, vendors, warehouses): pass the queryset to the template
   - For type/method dropdowns: pass the model's `CHOICES` constant
   - Never assume the template will get data it wasn't explicitly passed in the view context

2. **Template filter comparison rules:**
   - For string fields: `{% if request.GET.status == value %}selected{% endif %}`
   - For FK/pk fields: use `|stringformat:"d"` — NEVER use `|slugify` for pk comparison
   - Example: `{% if request.GET.category == cat.pk|stringformat:"d" %}selected{% endif %}`

3. **View filter logic:**
   - Always parse GET params and apply to queryset BEFORE pagination
   - Search: `request.GET.get('q', '').strip()` with `Q()` lookups
   - Status: `request.GET.get('status', '')` with `qs.filter(status=value)`
   - Active/Inactive: map `'active'`/`'inactive'` to `is_active=True/False`

4. **Template variable naming must match view context:**
   - If view passes `suggestions`, template must use `{% for r in suggestions %}`
   - If model field is `suggested_quantity`, template must use `r.suggested_quantity` (not `r.suggested_qty`)
   - If view passes `stats` dict, template accesses `stats.pending` (not `pending_count`)

5. **Badge values must match model CHOICES:**
   - Template badge conditions must use exact model choice values (e.g., `'weighted_avg'` not `'weighted_average'`)
   - Always include an `{% else %}` fallback: `{{ obj.get_field_display }}`

Run the `/frontend-design` skill for the full pattern reference.

---

### CRUD Completeness Rules (Preventing Missing Actions)

Every new module MUST include all CRUD operations from the start. Never ship a module with only list/add/view — Edit and Delete are mandatory.

1. **Every model that has a list page MUST have these views:**
   - `list_view` — with search + filters
   - `create_view` — add form
   - `detail_view` — read-only detail page (for models with enough fields)
   - `edit_view` — edit form (same template as create, pre-filled)
   - `delete_view` — POST-only with confirmation, redirects to list

2. **Every list template MUST have an Actions column with:**
   - View button (eye icon) — links to detail page
   - Edit button (pencil icon) — links to edit form
   - Delete button (bin icon) — POST form with `onclick="return confirm('...')"` and `{% csrf_token %}`
   - Conditional display: wrap Edit/Delete in `{% if obj.status == 'draft' %}` when status-dependent

3. **Every detail template MUST have an Actions sidebar with:**
   - Edit button — links to edit form (conditional on status)
   - Delete button — POST form with confirm dialog (conditional on status)
   - Back to List link

4. **Delete view pattern:**
   ```python
   @login_required
   def model_delete_view(request, pk):
       obj = get_object_or_404(Model, pk=pk, tenant=request.tenant)
       if request.method == 'POST':
           obj.delete()
           messages.success(request, 'Deleted successfully.')
           return redirect('app:model_list')
       return redirect('app:model_list')
   ```

5. **Delete URL pattern:**
   - Always add: `path('models/<int:pk>/delete/', views.model_delete_view, name='model_delete')`

---

### Template Folder Structure (MANDATORY)

Templates MUST be organized **one folder per sub-module, then one folder per entity** — never flat. The page
(`list` / `detail` / `form` / a secondary action) is the **bare filename**. A model's CRUD pages live under
`templates/<app>/<submodule>/<entity>/<page>.html`, grouped by the NavERP.md sub-module that owns the model.

1. **Path shape:** `templates/<app>/<submodule>/<entity>/<page>.html` where `<page>` ∈ {`list`, `detail`, `form`,
   … a secondary action like `import`}. e.g. `templates/hrm/offboarding/clearanceitem/detail.html`,
   `templates/accounting/ledger/journal_entry/list.html`, `templates/crm/directory/lead/form.html`. The view's
   `render()` / `crud_*` `template=` argument uses that full path: `render(request,
   "hrm/offboarding/clearanceitem/detail.html", ...)`. **Never** ship a flat `<entity>_<page>.html` file inside a
   sub-module folder (the old `clearanceitem_detail.html` shape is banned).

2. **Two folder levels: sub-module → entity.** The sub-module folder uses a short slug (e.g. HRM:
   `employee/ designation/ onboarding/ offboarding/ attendance/ leave/ holiday/`; Accounting:
   `ledger/ payable/ receivable/ cash/ assets/ costing/ payroll/ projects/ intercompany/ tax/ reports/ budget/
   audit/ integration/`; CRM: `directory/ sales/ marketing/ service/ activities/ finance/ projects/ documents/
   workflow/ success/ vendor/`). **Inside it, each model/entity gets its own folder** (`offboarding/separationcase/`,
   `offboarding/exitinterview/`, `cash/bank_account/`, `cash/bank_transaction/`). The page file is just
   `list.html` / `detail.html` / `form.html`.

3. **Single-entity sub-modules: the sub-module folder doubles as the entity folder** — do NOT double-nest. When a
   sub-module owns one main entity whose slug equals the folder (e.g. HRM `designation`, `employee`; Accounting
   `budget`, `integration`, `intercompany`), keep `designation/list.html`, `employee/form.html`, `budget/detail.html`
   — NOT `designation/designation/list.html`. A child entity added later still gets its own folder under the
   sub-module (e.g. `budget/line/form.html` alongside the page-only `budget/list.html`).

4. **Foundation apps (Module 0: core / accounts / tenants / dashboard) are flat — no sub-module level**, so the
   entity folder sits at the app root: `templates/core/party/list.html`, `templates/accounts/user/form.html`,
   `templates/tenants/subscription/detail.html`.

5. **Secondary entity-action pages go inside the entity folder** (page = the action name):
   `cash/bank_transaction/import.html` sits next to `cash/bank_transaction/list.html`. Fold a non-CRUD page into
   `<entity>/<action>.html` only when it begins with `<entity>_` for an entity that already has a CRUD triple in
   that directory (longest-entity-stem match — so `gl_account_ledger.html` is **not** folded into `glaccount/`).

6. **Standalone pages stay at the sub-module / app root** (no entity folder): module landing/overview
   (`templates/hrm/hrm_overview.html`, `templates/crm/overview.html`, `templates/accounting/dashboard.html`),
   reports (`accounting/reports/balance_sheet.html`, `accounting/ledger/trial_balance.html`,
   `accounting/payable/ap_aging.html`), print letters (`hrm/offboarding/relieving_letter.html`), wizards
   (`tenants/onboarding_wizard.html`), and other single-purpose pages that aren't an entity's list/detail/form.

7. **New modules (via `/next-module`)** MUST follow this from the start — create
   `templates/<app>/<submodule>/<entity>/{list,detail,form}.html`. Never ship flat
   `templates/<app>/<submodule>/<entity>_<page>.html` files.

8. **`{% extends %}` / `{% include %}` are unaffected** by the folders — keep `{% extends "base.html" %}` and
   `{% include "partials/..." %}` (base + partials live at the templates root, not inside a module).

---

### Seed Command Rules (Preventing Data Issues)

1. **Idempotent by default:**
   - Seed commands MUST be safe to run multiple times without `--flush`
   - Use `get_or_create` for models with unique constraints
   - For models with auto-generated numbers (PR-00001, PO-00001), check existence before creating:
     ```python
     existing = Model.objects.filter(tenant=tenant, number=number).first()
     if existing:
         results.append(existing)
         continue
     ```
   - Never use bare `.save()` or `.create()` for models with unique_together constraints

2. **Always skip if data exists:**
   - Check `if Model.objects.filter(tenant=tenant).exists()` at the start
   - Print a warning: `"Data already exists. Use --flush to re-seed."`

3. **Print login instructions:**
   - After seeding, always print which tenant admin accounts to use
   - Always warn: `"Superuser 'admin' has no tenant — data won't appear when logged in as admin"`

4. **`__init__.py` files:**
   - When creating `management/commands/` directories, ALWAYS create both:
     - `management/__init__.py`
     - `management/commands/__init__.py`

---

### Multi-Tenancy Rules (Preventing Data Visibility Issues)

1. **Superuser has no tenant:**
   - The `admin` superuser has `tenant=None`
   - All tenant-scoped module views filter by `tenant=request.tenant`
   - When `request.tenant` is `None`, queries return empty results — this is BY DESIGN
   - Always instruct users to log in as a **tenant admin** (e.g., `admin_<slug>`) to see module data

2. **Every view MUST filter by tenant:**
   - `Model.objects.filter(tenant=request.tenant)` — no exceptions
   - Never use `Model.objects.all()` in tenant-scoped views

3. **Every model MUST have a tenant FK:**
   - Except User, Role (which have it already) and pure join/through tables
   - Always include: `tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='...')`

---

### Vulnerability
When you find a security vulnerability, flag it immediately with a WARNING comment and suggest a secure alternative. Never implement insecure patterns even if asked.

---

