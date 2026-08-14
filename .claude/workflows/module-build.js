export const meta = {
  name: 'module-build',
  description: 'Build one NavERP sub-module with a frozen contract, per-entity backend and template agents running concurrently, then a single-writer integrate + smoke gate',
  whenToUse:
    'Phase 3 of the CLAUDE.md Module Creation Sequence — after the todo agent has written the build plan. ' +
    'Replaces building the sub-module inline or with an ad-hoc 2-agent split.',
  phases: [
    { title: 'Spec', detail: 'read-only: freeze the contract — every model field, url name and view context key' },
    { title: 'Scaffold', detail: 'brand-new app only: package skeleton + _base/_common (skipped when the app exists)' },
    { title: 'Build', detail: 'per entity, a backend agent and a template agent running CONCURRENTLY' },
    { title: 'Integrate', detail: 'single writer: re-exports, admin, seeder, navigation, migrate, commit' },
    { title: 'Smoke', detail: 'prove every new page renders; fix contract drift before the reviewers see it' },
  ],
}

// ---------------------------------------------------------------------------
// args: { slug, submodule, title, newApp?, migrationNumber?, plan? }
//   slug             app slug, e.g. "scm"
//   submodule        the N.M number, e.g. "4.17"
//   title            the NavERP.md sub-module title
//   newApp           true only on the first run for a brand-new module
//   migrationNumber  the migration number claimed in Phase 0 (concurrent sessions, L43)
//   plan             path to the build plan, defaults to .claude/tasks/todo.md
// ---------------------------------------------------------------------------

const A = args || {}
const slug = A.slug
const sub = A.submodule
const title = A.title || ''
const newApp = A.newApp === true
const plan = A.plan || '.claude/tasks/todo.md'
const claimedMigration = A.migrationNumber || ''

if (!slug || !sub) {
  throw new Error(
    'module-build needs args {slug, submodule}. ' +
    'Example: {slug:"scm", submodule:"4.17", title:"Returns Management", newApp:false, migrationNumber:"0029"}'
  )
}

const LABEL = sub + (title ? ' ' + title : '')

// Shared preamble every agent in this workflow gets.
const CONVENTIONS = [
  'NavERP conventions that are NOT negotiable (CLAUDE.md is the authority; apps/crm and apps/accounting are the',
  'converted reference apps — read them when unsure):',
  '  - Django 5.1, FUNCTION-BASED views with @login_required. No CBVs.',
  '  - Backend layers are PACKAGES: apps/' + slug + '/{models,forms,views,urls}/<SubModule>/<Entity>.py.',
  '    Imports inside them are ABSOLUTE (from apps.' + slug + '.models import X). A relative "from .models import X"',
  '    resolves one level deep to the wrong package. Pull the shared toolkit via',
  '    "from apps.' + slug + '.models._base import *" (resp. forms._common, views._common).',
  '  - Multi-tenancy: every model carries tenant = models.ForeignKey(\'core.Tenant\', on_delete=models.CASCADE,',
  '    related_name=\'<unique>\'). Every queryset filters tenant=request.tenant; every lookup is',
  '    get_object_or_404(Model, pk=pk, tenant=request.tenant). Never .objects.all() in a tenant view.',
  '  - Core spine: customers/vendors/suppliers/employees/leads/contacts are PartyRoles on core.Party — never a new',
  '    standalone table. apps/accounting owns the ledger; financial effects post balanced JournalEntry/JournalLine',
  '    inside transaction.atomic() and FK accounting.* BY STRING. Balances are DERIVED by aggregate, never stored',
  '    editable. Item/UOM/StockMove/LotSerial and SalesOrder are NOT built — verify before FK\'ing',
  '    (grep -rn "^class <Name>" apps/*/models/) and use a documented tenant-scoped stand-in when a master is missing.',
  '  - Templates: templates/' + slug + '/<submodule>/<entity>/<page>.html, extending base.html. theme.css modifier',
  '    classes are COLOUR-NAMED ONLY — badge-green/red/amber/info/muted/slate, stat-icon',
  '    blue/green/orange/purple/slate. A semantic badge-success/-danger renders UNSTYLED (L33, shipped 4x).',
  '  - Multi-line notes use {% comment %}...{% endcomment %}; a multi-line {# #} leaks as visible text (L2).',
  '  - PowerShell shell: chain with ";", never "&&". Python is venv\\Scripts\\python.exe.',
].join('\n')

// ---------------------------------------------------------------------------
// Phase 1 — Spec. Read-only. Freezing this contract is what makes the fan-out safe.
// ---------------------------------------------------------------------------

const CONTRACT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['submodule_folder', 'template_folder', 'entities'],
  properties: {
    submodule_folder: { type: 'string', description: 'PascalCase backend sub-module folder, e.g. ReturnsManagement' },
    template_folder: { type: 'string', description: 'lowercase template sub-module slug, e.g. returns' },
    reuses: { type: 'string', description: 'spine/sibling entities this sub-module FKs by string — each one VERIFIED to exist with a grep' },
    stand_ins: { type: 'string', description: 'documented tenant-scoped stand-ins for masters that are not built yet, and why' },
    nav_link: { type: 'string', description: 'the LIVE_LINKS["' + sub + '"] entry: each NavERP.md feature-bullet name -> url name' },
    entities: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['entity_file', 'model', 'template_slug', 'fields', 'form', 'views', 'urls', 'context_keys', 'list_page'],
        properties: {
          entity_file: { type: 'string', description: 'PascalCase file STEM, no .py — e.g. ReturnAuthorizations' },
          model: { type: 'string', description: 'the primary model class name' },
          children: { type: 'string', description: 'child models this entity file also owns (e.g. ReturnLine), or empty' },
          template_slug: { type: 'string', description: 'lowercase entity folder under the template sub-module folder, e.g. rma' },
          fields: { type: 'string', description: 'EVERY field: name, type, null/blank, default, FK target by string, and the exact CHOICES key/label pairs' },
          auto_number: { type: 'string', description: 'auto-number prefix pattern (e.g. RMA-#####) or empty' },
          form: { type: 'string', description: 'exact Meta.fields, then EXCLUDED: tenant, auto-number, owner/created_by, workflow status, secrets/hashes, system *_at, derived counters' },
          views: { type: 'string', description: 'the view function names (list/detail/create/edit/delete + any custom action) and each one\'s permission gate' },
          urls: { type: 'string', description: 'each namespaced url name -> its path and kwargs, e.g. scm:rma_list -> rmas/ , scm:rma_delete -> rmas/<int:pk>/delete/' },
          context_keys: {
            type: 'string',
            description:
              'THE CRITICAL FIELD. The EXACT context variable name each view passes: the list var, the detail object var, ' +
              'the edit-mode object var, page_obj, every *_choices, every FK queryset for a filter dropdown, every stats key. ' +
              'A name left unpinned here is a blank page region or a NoReverseMatch (L7).',
          },
          list_page: { type: 'string', description: 'the q= search fields, and each filter GET param with the context var that populates its widget' },
        },
      },
    },
  },
}

phase('Spec')
log('Freezing the build contract for ' + slug + ' ' + LABEL + (newApp ? ' (BRAND-NEW APP)' : ''))

const contract = await agent(
  [
    'Produce the frozen BUILD CONTRACT for NavERP sub-module ' + LABEL + ' in apps/' + slug + '.',
    '',
    'You are READ-ONLY. Do not create or edit any file. Your entire output is the contract.',
    '',
    'READ, in this order:',
    '  1. ' + plan + ' — the build plan for this sub-module (models, fields, pages). This is the intent.',
    '  2. The "### ' + sub + '" section of NavERP.md — the feature bullets the nav link must map.',
    '  3. apps/crm/ and apps/accounting/ — the converted reference apps. Copy their package shape exactly.',
    '  4. The sibling sub-module most like this one inside apps/' + slug + '/, so the new code matches its neighbours.',
    '  5. apps/core/navigation.py — the existing LIVE_LINKS entries, to shape yours.',
    '',
    CONVENTIONS,
    '',
    'RULES FOR THE CONTRACT ITSELF:',
    '  - 1-4 entities, no more. If the plan implies more, pick the 1-4 that make this sub-module\'s features real',
    '    and say in `stand_ins` what you deferred.',
    '  - An entity file owns its primary model PLUS its children (Invoices.py = Invoice + InvoiceLine). Do not',
    '    scatter one entity across files, and do not give a child its own entity file.',
    '  - Template folders: normally templates/' + slug + '/<template_folder>/<template_slug>/. BUT when this',
    '    sub-module has a SINGLE entity whose slug equals the sub-module folder, the sub-module folder doubles as',
    '    the entity folder — set template_slug EQUAL to template_folder and it will not be double-nested.',
    '  - Before you name a spine entity in `reuses`, VERIFY it exists: grep -rn "^class <Name>" apps/*/models/ .',
    '    Item / UOM / StockMove / LotSerial / SalesOrder are NOT built. A documented tenant-scoped stand-in is the',
    '    correct pattern for a missing master — put it in `stand_ins`, never a hard FK to something unbuilt (L28).',
    '  - Uniqueness on a tenant-scoped model is unique_together WITH tenant, never a bare global unique=True.',
    '',
    'WHY context_keys DECIDES WHETHER THIS BUILD WORKS: a backend agent and a template agent will write each',
    'entity CONCURRENTLY from this contract and never see each other\'s output. Any name you leave unpinned they',
    'will each invent independently — and a mismatched context var renders a silently blank region (200, no error)',
    'or a NoReverseMatch 500 (L7/L8). Pin every single name a template will type. Be exhaustive, not tidy.',
  ].join('\n'),
  { agentType: 'explorer', label: 'contract', phase: 'Spec', schema: CONTRACT_SCHEMA }
)

if (!contract) throw new Error('module-build: the Spec phase returned nothing — re-run before fanning out')

const ents = Array.isArray(contract.entities) ? contract.entities.filter(e => e && e.entity_file) : []
if (!ents.length) throw new Error('module-build: the contract has no entities — check ' + plan)
if (ents.length > 4) log('WARNING — contract has ' + ents.length + ' entities; a sub-module pass should be 1-4')

const folder = contract.submodule_folder
const tfolder = contract.template_folder

// Deterministic expected-output list — the integrator checks against THIS, not against its own memory (L21).
const tplDir = e => (e.template_slug === tfolder)
  ? 'templates/' + slug + '/' + tfolder
  : 'templates/' + slug + '/' + tfolder + '/' + e.template_slug
const backendFiles = e => ['models', 'forms', 'views', 'urls'].map(l => 'apps/' + slug + '/' + l + '/' + folder + '/' + e.entity_file + '.py')
const templateFiles = e => ['list', 'detail', 'form'].map(p => tplDir(e) + '/' + p + '.html')

const expectedFiles = []
for (const e of ents) expectedFiles.push(...backendFiles(e), ...templateFiles(e))

log('Contract frozen: ' + ents.length + ' entities (' + ents.map(e => e.model).join(', ') + ') -> ' + expectedFiles.length + ' files')

const CONTRACT_JSON = JSON.stringify(contract, null, 2)

// ---------------------------------------------------------------------------
// Phase 2 — Scaffold (brand-new app only)
// ---------------------------------------------------------------------------

if (newApp) {
  phase('Scaffold')
  log('Brand-new app — scaffolding the apps/' + slug + ' skeleton before the fan-out')
  const scaffold = await agent(
    [
      'Scaffold the skeleton for the BRAND-NEW Django app apps/' + slug + '. Entity files come next from other',
      'agents — you create only the frame they need to exist inside.',
      '',
      CONVENTIONS,
      '',
      'CREATE (clone the shapes from apps/crm/ and apps/accounting/ — do not invent them):',
      '  - apps/' + slug + '/__init__.py, apps.py (AppConfig name = \'apps.' + slug + '\'), admin.py (empty registry for now)',
      '  - apps/' + slug + '/migrations/__init__.py',
      '  - apps/' + slug + '/models/__init__.py + models/_base.py (django imports + the abstract Tenant*/TenantNumbered base,',
      '    built on apps.core.utils.next_number)',
      '  - apps/' + slug + '/forms/__init__.py + forms/_common.py (shared imports; forms inherit core.forms._common.TenantModelForm)',
      '  - apps/' + slug + '/views/__init__.py + views/_common.py (shared imports)',
      '  - apps/' + slug + '/urls/__init__.py (app_name = \'' + slug + '\'; concatenates each entity module\'s urlpatterns)',
      '  - apps/' + slug + '/models/' + folder + '/__init__.py and the same for forms/, views/, urls/',
      '  - apps/' + slug + '/management/__init__.py, management/commands/__init__.py, and management/commands/seed_' + slug + '.py',
      '    (idempotent skeleton: per-tenant exists() guard, --flush, and the tenant-admin login instructions plus the',
      '    warning that the admin superuser has tenant=None so seeded data will not appear for it)',
      '',
      'DO NOT:',
      '  - write any entity file (models/' + folder + '/<Entity>.py etc.) — four other agents own those',
      '  - touch config/settings.py or config/urls.py. The check-after-edit hook runs manage.py check and will BLOCK',
      '    on an app whose files do not exist yet (L12). The Integrate phase does that wire-up, after the fan-out.',
      '  - run makemigrations, migrate, or git.',
    ].join('\n'),
    { agentType: 'general-purpose', label: 'scaffold', phase: 'Scaffold' }
  )
  if (!scaffold) log('WARNING — scaffold returned nothing; the Integrate phase must verify the skeleton by hand')
}

// ---------------------------------------------------------------------------
// Phase 3 — Build. Backend and templates for each entity run AT THE SAME TIME.
// The frozen contract is the only thing joining them, which is why Spec is exhaustive.
// ---------------------------------------------------------------------------

function backendPrompt(e) {
  return [
    'Write the COMPLETE backend for ONE entity of NavERP sub-module ' + LABEL + ': **' + e.model + '**.',
    '',
    'YOU OWN EXACTLY THESE FOUR FILES — and nothing else in the repository:',
    backendFiles(e).map(f => '  ' + f).join('\n'),
    '',
    CONVENTIONS,
    '',
    'DO NOT TOUCH (other agents and the Integrate phase own these — editing them corrupts a concurrent write):',
    '  - any package __init__.py, including the re-export blocks. The Integrate phase adds your entity to them.',
    '  - admin.py, the seeder, apps/core/navigation.py, config/settings.py, config/urls.py',
    '  - any other entity\'s files, and ANY template (a template agent is writing yours right now)',
    '  - Do NOT run makemigrations or migrate — the Integrate phase is the single DB writer.',
    '  - Do NOT run git.',
    '',
    'BUILD IT TO THE CONTRACT EXACTLY. Your view context dict keys are a published interface: a template agent is',
    'typing them into HTML at this moment without seeing your code. Emit the contracted names character for',
    'character — a rename renders a silently blank region or a NoReverseMatch (L7).',
    '',
    'models/' + folder + '/' + e.entity_file + '.py',
    '  - tenant FK, timestamps, STATUS_CHOICES class attrs, __str__, class Meta: ordering (+ db_index on the',
    '    columns the list ORDER BY and the tenant-scoped filters actually use), unique_together WITH tenant.',
    '  - auto-number in save() with an existence guard against collisions, using the app\'s TenantNumbered base.',
    '  - Derived values are properties/aggregates. Never a stored editable balance (L29).',
    '',
    'forms/' + folder + '/' + e.entity_file + '.py',
    '  - inherit the project TenantModelForm so FK dropdowns are tenant-scoped — an unscoped ModelChoiceField both',
    '    displays another tenant\'s rows AND accepts their pk from a crafted POST.',
    '  - Meta.fields is exactly the contract\'s list. Every excluded field stays out — a secret in Meta.fields ships',
    '    its plaintext in the edit form\'s value="" (L20); a system *_at gets silently truncated by a DateInput (L22).',
    '',
    'views/' + folder + '/' + e.entity_file + '.py',
    '  - @login_required on all; the contract\'s privileged views also get @tenant_admin_required.',
    '  - list: q search via Q(), every contracted filter parsed from request.GET and applied BEFORE pagination.',
    '    Guard int/FK params with .isdigit() — a hand-edited ?category=abc must not 500 (L11).',
    '  - Pass EVERY context key in the contract, including the *_choices and the FK querysets the filter widgets need.',
    '  - select_related/prefetch_related for every FK a row or a row\'s __str__ touches, including chained hops',
    '    (a row __str__ that walks parent.owner needs select_related("parent__owner")).',
    '  - delete is POST-only: POST -> delete -> messages.success -> redirect to list; GET -> redirect, no deletion.',
    '  - Status guards live HERE, not only in the template — hiding a button does not stop a direct POST.',
    '  - Multi-row/multi-model writes inside transaction.atomic(). Write an AuditLog row via apps.core.utils.',
    '  - Successful full-page POST ends messages.success + redirect (POST-redirect-GET).',
    '',
    'urls/' + folder + '/' + e.entity_file + '.py',
    '  - urlpatterns exactly as contracted; import views absolutely (from apps.' + slug + ' import views).',
    '  - Literal routes BEFORE <int:pk> ones — Django is first-match-wins.',
    '',
    'THE FROZEN CONTRACT (authoritative — if something you need is missing, choose the option that matches the',
    'sibling sub-module and say so in your return text; do not silently rename a contracted key):',
    '```json',
    CONTRACT_JSON,
    '```',
    '',
    'Return: the four files you wrote, any place you deviated from the contract and why, and any spine entity you',
    'expected and found missing.',
  ].join('\n')
}

function templatePrompt(e) {
  return [
    'Write the COMPLETE template set for ONE entity of NavERP sub-module ' + LABEL + ': **' + e.model + '**.',
    '',
    'YOU OWN EXACTLY THESE THREE FILES — and nothing else in the repository:',
    templateFiles(e).map(f => '  ' + f).join('\n'),
    '(form.html is shared by create and edit.)',
    '',
    CONVENTIONS,
    '',
    'A backend agent is writing this entity\'s views RIGHT NOW and you will never see its code. The contract\'s',
    'context_keys are the interface between you: use those names EXACTLY and invent none. If you find yourself',
    'wanting a variable that is not in the contract, it does not exist — say so in your return text instead of',
    'guessing a name (L7).',
    '',
    'DO NOT TOUCH: any .py file, any other entity\'s templates, base.html, static/css/theme.css, or the module',
    'landing page. Do NOT run git.',
    '',
    'BEFORE YOU USE ANY theme.css MODIFIER CLASS, confirm it exists:',
    '  grep -oE \'\\.(badge-[a-z]+|stat-icon(\\.[a-z]+)?|text-[a-z]+)\' static/css/theme.css | sort -u',
    'or copy a sibling template\'s line verbatim. badge-success / badge-danger / badge-warning DO NOT EXIST and',
    'render as unstyled text — this exact mistake has shipped four times (L33).',
    '',
    'list.html',
    '  - .page-header with title + breadcrumb + a page-action "Add" button',
    '  - a GET filter form: q search box plus every contracted filter select, each reflecting request.GET.',
    '    String filters: {% if request.GET.status == value %}selected{% endif %}.',
    '    pk/FK filters: {% if request.GET.category == cat.pk|stringformat:"d" %} — NEVER |slugify.',
    '  - .table-wrap > .table with an Actions column: view (eye), edit (pencil), delete (trash-2). Delete is a POST',
    '    form with {% csrf_token %} and onclick="return confirm(\'...\')" — escape the apostrophe as \\\' , because',
    '    &#39; does NOT escape inside that attribute (L42). Wrap edit/delete in the contracted status condition.',
    '  - pagination guarded: {% if page_obj.has_previous %}...{% endif %} around previous_page_number and the same',
    '    for has_next — an unguarded call raises EmptyPage and 500s once the list outgrows one page (L9).',
    '  - an .empty-state for the no-rows case.',
    '',
    'detail.html',
    '  - the record\'s fields, plus an Actions sidebar: Edit link, POST-only Delete with confirm + csrf (both',
    '    status-conditional to match the view\'s gate), and a Back-to-List link.',
    '  - Guard every nullable FK display: {% if fk %}{{ fk.get_full_name|default:fk.username }}{% else %}—{% endif %}.',
    '    A None FK inside a FILTER ARGUMENT raises and 500s even though a bare lookup would not (L10).',
    '',
    'form.html',
    '  - one form for create and edit, driven by the contracted edit-mode object var; {% csrf_token %}; render',
    '    field errors; label for= paired with the input id=; Cancel returns to the list.',
    '',
    'Badges everywhere test the model\'s EXACT CHOICES keys from the contract and always end with an',
    '{% else %}{{ obj.get_<field>_display }}{% endif %} fallback.',
    '',
    'THE FROZEN CONTRACT:',
    '```json',
    CONTRACT_JSON,
    '```',
    '',
    'Return: the three files you wrote, every context key you consumed, and anything the contract left unpinned.',
  ].join('\n')
}

phase('Build')
log('Fanning out ' + (ents.length * 2) + ' agents — backend ‖ templates for each of ' + ents.length + ' entities')

const thunks = []
for (const e of ents) {
  thunks.push(() => agent(backendPrompt(e), { agentType: 'general-purpose', label: 'backend:' + e.model, phase: 'Build' }))
  thunks.push(() => agent(templatePrompt(e), { agentType: 'general-purpose', label: 'templates:' + e.model, phase: 'Build' }))
}
const built = await parallel(thunks)

const deadAgents = []
built.forEach((r, i) => { if (!r) deadAgents.push(i % 2 === 0 ? 'backend:' + ents[Math.floor(i / 2)].model : 'templates:' + ents[Math.floor(i / 2)].model) })
if (deadAgents.length) log('WARNING — no result from: ' + deadAgents.join(', ') + ' — Integrate must check those files exist')

// ---------------------------------------------------------------------------
// Phase 4 — Integrate. Single writer for every shared file, and the only DB writer.
// ---------------------------------------------------------------------------

phase('Integrate')

const integrate = await agent(
  [
    'The per-entity agents for NavERP sub-module ' + LABEL + ' have finished. You are the SINGLE WRITER for every',
    'shared file and the ONLY agent allowed to touch the database. Nothing is wired up yet.',
    '',
    CONVENTIONS,
    '',
    'STEP 1 — VERIFY THE FAN-OUT ACTUALLY LANDED, before you wire anything (L21).',
    'Every one of these files must exist and be non-empty. A workflow can be cut off mid-phase, and wiring up a',
    'half-written app produces TemplateDoesNotExist / ImportError 500s that look like build bugs:',
    expectedFiles.map(f => '  ' + f).join('\n'),
    deadAgents.length ? '  !! These agents returned nothing — treat their files as suspect: ' + deadAgents.join(', ') : '',
    'If a file is missing or a stub, WRITE IT YOURSELF from the contract before continuing. Report which ones.',
    '',
    'STEP 2 — RE-EXPORTS. Add this sub-module\'s block to each of the four package __init__.py files:',
    '  apps/' + slug + '/models/__init__.py, forms/__init__.py, views/__init__.py, urls/__init__.py',
    '  (models/forms/views: from .' + folder + '.<Entity> import (...) — every model, form and view.',
    '   urls/__init__.py: concatenate each entity module\'s urlpatterns, literal routes before <int:pk> ones.)',
    'A model/form/view that is not re-exported is an ImportError or AttributeError at runtime that manage.py check',
    'may not surface until the URLconf imports it. Use surgical Edit — NEVER rewrite one of these files. Another',
    'session may be adding a different sub-module\'s block to the same file right now (L43).',
    '',
    'STEP 3 — admin.py: register the new models (from .models import ... works via the re-exports).',
    '',
    'STEP 4 — seeder: extend the EXISTING apps/' + slug + '/management/commands/seed_' + slug + '.py with this',
    'sub-module\'s demo rows. Idempotent: per-tenant exists() guard, get_or_create for unique-constrained models,',
    'an existence check before creating an auto-numbered row. REUSE existing Party / sibling rows rather than',
    'inventing duplicates, and keep the --flush wipe order consistent with the new models. Surgical Edit only.',
    '',
    'STEP 5 — navigation: add the ONE new LIVE_LINKS["' + sub + '"] entry to apps/core/navigation.py, mapping the',
    'exact NavERP.md feature-bullet names to url names per the contract\'s nav_link. Do not touch parse_catalog(),',
    'MODULE_ICONS, or any other sub-module\'s entry. Never offer a bullet whose page a user cannot reach (L32).',
    newApp
      ? 'STEP 5b — BRAND-NEW APP: add \'apps.' + slug + '\' to INSTALLED_APPS in config/settings.py and\n' +
        '  path(\'' + slug + '/\', include(\'apps.' + slug + '.urls\')) to config/urls.py. Do this NOW and not earlier —\n' +
        '  the check-after-edit hook blocks when these reference an app whose files do not exist (L12).'
      : 'STEP 5b — the app already exists: do NOT touch config/settings.py or config/urls.py.',
    '',
    'STEP 6 — MIGRATE AND SEED (you are the single DB writer):',
    '  venv\\Scripts\\python.exe manage.py makemigrations ' + slug,
    claimedMigration
      ? '  This session claimed migration number ' + claimedMigration + ' — if makemigrations produces a different\n' +
        '  number, a concurrent session took it; renumber yours and say so (L43).'
      : '  If another session may be building in this tree, check apps/' + slug + '/migrations/ for a colliding number.',
    '  venv\\Scripts\\python.exe manage.py migrate',
    '  venv\\Scripts\\python.exe manage.py seed_' + slug,
    '  venv\\Scripts\\python.exe manage.py seed_' + slug + '     (2nd run MUST be idempotent — no duplicates, no crash)',
    '  venv\\Scripts\\python.exe manage.py check',
    'Fix whatever these surface before moving on.',
    '',
    'STEP 7 — COMMIT, one file per commit, PowerShell-safe, in dependency order (models, forms, views, urls,',
    '__init__.py re-exports, admin, migration, seeder, navigation, then templates):',
    '  git add \'apps/' + slug + '/models/' + folder + '/<Entity>.py\'; git commit -m \'feat(' + slug + '): ' + sub + ' <Entity> models (...)\'',
    'Each message describes THAT ONE FILE. Never bundle. Never `git add -A` or `git add .` — name every path',
    'explicitly, because an untracked file in this tree may belong to a concurrent session (L45). NEVER git push.',
    '',
    'Return: files verified/repaired, the migration number you actually got, both seed runs\' outcome, the check',
    'result, and the commit count.',
  ].filter(Boolean).join('\n'),
  { agentType: 'general-purpose', label: 'integrate', phase: 'Integrate' }
)

// ---------------------------------------------------------------------------
// Phase 5 — Smoke gate. Catches the contract drift the fan-out can introduce,
// BEFORE the review wave spends six agents on a page that 500s.
// ---------------------------------------------------------------------------

phase('Smoke')

const smoke = await agent(
  [
    'Runtime gate for NavERP sub-module ' + LABEL + ', just built by parallel agents. This is NOT the full audit',
    'sweep — the review wave runs that next. Your one job: prove every new page actually renders, and fix the',
    'contract drift that a concurrent backend/template fan-out can produce.',
    '',
    'THE FAILURE CLASS YOU ARE HUNTING: a backend agent and a template agent wrote each entity at the same time',
    'from a shared contract. Where one of them deviated, you get a context-variable mismatch that renders a',
    'silently BLANK region and still returns 200 (L8), or a NoReverseMatch 500 (L7). A status-code sweep alone',
    'will not see the first one.',
    '',
    'Sweep exactly these url names (from the frozen contract):',
    ents.map(e => '  ' + e.model + ': ' + e.urls).join('\n'),
    '',
    'Method — your standard temp/ throwaway script, as admin_acme (password "password"), with',
    'Client(raise_request_exception=False) so one pass collects ALL 500s:',
    '  - every list, detail, create and edit url -> status in (200, 302)',
    '  - each LIST page: assert the HTML contains NO \'{#\' and NO \'{% comment\' marker, contains the page title,',
    '    AND contains a seeded record — a list that renders empty against seeded data is the blank-context bug',
    '  - each DETAIL page: assert a token from str(obj) appears in the HTML',
    '  - one filtered list (?q=...&status=...), one junk-param list (?category=abc -> must not 500, L11), and',
    '    page 2 where the seeded rows exceed the page size (?page=2, L9)',
    '  - cross-tenant IDOR: still as admin_acme, request a globex-owned pk -> assert 404',
    '',
    'FIX what fails — the usual causes are a context-variable name mismatch against the contract, a wrong',
    'related_name, an unguarded previous_page_number, or a None FK inside a filter argument. Make the MINIMAL fix,',
    'prefer changing whichever side deviated FROM THE CONTRACT, and re-run to green. Delete the temp script when done.',
    '',
    'THE FROZEN CONTRACT (the arbiter of which side is wrong):',
    '```json',
    CONTRACT_JSON,
    '```',
    '',
    'Commit each fix as its own file, PowerShell-safe, explicit paths only. NEVER git push.',
    '',
    'Return a table of url name -> status + content check, and every fix you applied with file:line.',
  ].join('\n'),
  { agentType: 'qa-smoke-tester', label: 'smoke', phase: 'Smoke' }
)

return {
  contract: contract,
  entities: ents.map(e => e.model),
  expectedFiles: expectedFiles,
  deadAgents: deadAgents,
  integrate: integrate,
  smoke: smoke,
}
