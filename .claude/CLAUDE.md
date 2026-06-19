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

Whenever you create a **new module or sub-module**, follow this exact sequence. Each step ends with `git add` + `git commit` (one file per commit, PowerShell-safe). **Never run `git push` at any step** — the user pushes manually.

1. **Write the module code** — implement the module, then `git add` + `git commit`. Do NOT `git push`.
2. **Run the `code-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
3. **Run the `explorer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
4. **Run the `frontend-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
5. **Run the `performance-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
6. **Run the `qa-smoke-tester` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
7. **Run the `security-reviewer` agent** — apply its findings, then `git add` + `git commit`. Do NOT `git push`.
8. **Run the `test-writer` agent** — apply its output, then `git add` + `git commit`. Do NOT `git push`.

**Rules for this sequence:**

* Run the agents **in this order, one at a time** — do not skip a step and do not reorder.
* After each agent step, commit the resulting changes before moving to the next agent (still one file per commit).
* `git push` is **never** part of this sequence — stop at `git commit` every time.
* If an agent reports no changes are needed, note that and proceed to the next step (no empty commit required).

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

