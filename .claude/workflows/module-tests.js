export const meta = {
  name: 'module-tests',
  description: 'Write a NavERP sub-module pytest suite with parallel test-writer agents over disjoint files, then prove the whole app suite green',
  whenToUse: 'Step 6 of the CLAUDE.md Module Creation Sequence — after code-fixer has burned down the review findings. Replaces the single serial test-writer agent.',
  phases: [
    { title: 'Contract', detail: 'single writer: tests package + conftest, and the pinned model/url/fixture contract' },
    { title: 'Write', detail: 'four test-writer agents in parallel, one owned file each' },
    { title: 'Green', detail: 'one FULL unfiltered pytest run over the app, fixed to green' },
  ],
}

// ---------------------------------------------------------------------------
// args: { slug, submodule, subslug, title? }
//   slug      app slug, e.g. "scm"
//   submodule the N.M number, e.g. "4.17"
//   subslug   short file-name slug for this sub-module, e.g. "returns"
//             -> apps/<slug>/tests/test_<subslug>_{models,forms,views,security}.py
//   title     the NavERP.md sub-module title
// ---------------------------------------------------------------------------

const A = args || {}
const slug = A.slug
const sub = A.submodule
const subslug = A.subslug
const title = A.title || ''

if (!slug || !sub || !subslug) {
  throw new Error(
    'module-tests needs args {slug, submodule, subslug}. ' +
    'Example: {slug:"scm", submodule:"4.17", subslug:"returns", title:"Returns Management"}'
  )
}

const TESTS_DIR = 'apps/' + slug + '/tests'
const fileFor = lane => TESTS_DIR + '/test_' + subslug + '_' + lane + '.py'

const HEADER = [
  'TARGET: NavERP sub-module ' + sub + (title ? ' ' + title : '') + ' in apps/' + slug + '.',
  '',
  'ENVIRONMENT',
  '  - Run pytest ONLY as: venv\\Scripts\\python.exe -m pytest -q <path>',
  '  - Settings resolve from pytest.ini -> config.settings_test (SQLite in-memory). Never override',
  '    DJANGO_SETTINGS_MODULE in the environment — the env var beats pytest.ini and silently runs the suite',
  '    against the shared MySQL test DB (L19).',
  '  - Because the test DB is SQLite in-memory, concurrent pytest processes are independent. Yours cannot',
  '    collide with a sibling lane\'s.',
  '  - REUSE the ROOT conftest.py fixtures: tenant_a / tenant_b, admin_user / member_user / admin_b,',
  '    client_a / client_b / member_client. Do not re-invent them.',
  '  - Tenant admin credentials in seeded data: admin_acme / admin_globex, password "password" (L34).',
  '  - Dates: derive from timezone.now().date() / timezone.localdate(), NEVER datetime.date.today() (L16).',
  '  - Backend layers are packages — import through the package root (from apps.' + slug + '.models import X);',
  '    grep recursively under apps/' + slug + '/models/ etc., there is no models.py.',
].join('\n')

// ---------------------------------------------------------------------------
// Phase 1 — contract (single writer; owns the shared files)
// ---------------------------------------------------------------------------

const CONTRACT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['models', 'urls', 'fixtures', 'ready'],
  properties: {
    ready: { type: 'boolean', description: 'true once apps/<slug>/tests/__init__.py and conftest.py exist and are final' },
    conftest_path: { type: 'string' },
    models: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'import_path', 'required_fields'],
        properties: {
          name: { type: 'string' },
          import_path: { type: 'string', description: 'e.g. from apps.scm.models import ReturnAuthorization' },
          required_fields: { type: 'string', description: 'the exact kwargs a minimal valid instance needs, tenant included' },
          choices: { type: 'string', description: 'STATUS_CHOICES / other CHOICES keys, exact values' },
          auto_number: { type: 'string', description: 'the auto-number prefix pattern if any, e.g. RMA-#####' },
          derived: { type: 'string', description: 'properties/aggregates that must be DERIVED, not stored' },
        },
      },
    },
    forms: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'fields', 'excluded'],
        properties: {
          name: { type: 'string' },
          fields: { type: 'string', description: 'exact Meta.fields' },
          excluded: { type: 'string', description: 'view-owned/system/secret fields that MUST NOT be form fields' },
        },
      },
    },
    urls: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'needs_pk'],
        properties: {
          name: { type: 'string', description: 'namespaced url name, e.g. scm:rma_list' },
          needs_pk: { type: 'boolean' },
          method: { type: 'string', description: 'GET, POST, or POST-only for deletes' },
          gate: { type: 'string', description: 'login_required / tenant_admin_required / public token' },
          context_keys: { type: 'string', description: 'the exact context variable names the view passes' },
        },
      },
    },
    fixtures: { type: 'array', items: { type: 'string' }, description: 'fixture names the lanes may use (root conftest + app conftest)' },
    page_size: { type: 'integer', description: 'list pagination page size, so the views lane can build a page-2 case' },
    notes: { type: 'string' },
  },
}

phase('Contract')
log('Pinning the test contract for ' + slug + ' ' + sub + ' (single writer — owns tests/__init__.py + conftest.py)')

const contract = await agent(
  [
    HEADER,
    '',
    'YOU ARE THE SINGLE WRITER for the shared test files. Four parallel lanes run straight after you and each owns',
    'exactly one test_' + subslug + '_*.py file. They are forbidden from touching anything you own, so everything',
    'shared must be final when you return.',
    '',
    'DO, in order:',
    '  1. Ensure ' + TESTS_DIR + '/__init__.py exists (create it empty if missing).',
    '  2. READ the root conftest.py and a sibling suite in ' + TESTS_DIR + ' (e.g. an existing test_*_models.py)',
    '     so the lanes mirror the established fixture and naming conventions instead of inventing new ones.',
    '  3. Ensure ' + TESTS_DIR + '/conftest.py exists. If this sub-module needs domain fixtures the root conftest',
    '     does not provide, ADD them here with a `' + subslug + '_` name prefix — surgically, via Edit. NEVER',
    '     rewrite conftest.py wholesale; other sub-modules depend on every fixture already in it (L43).',
    '  4. READ this sub-module\'s real models / forms / views / urls under apps/' + slug + '/ and build the CONTRACT:',
    '     exact model names + the kwargs a minimal valid instance needs, exact CHOICES values, auto-number patterns,',
    '     exact form Meta.fields plus what must be EXCLUDED (tenant, auto-number, owner, workflow status, secrets,',
    '     system *_at timestamps, derived counters), every namespaced url name with whether it needs a pk and its',
    '     permission gate, and the exact context-variable names each view passes.',
    '  5. Sanity-check the suite still collects: venv\\Scripts\\python.exe -m pytest -q ' + TESTS_DIR + ' --collect-only',
    '',
    'The contract you return is the ONLY spec the four lanes get — if you leave a name unpinned they will each guess',
    'a different one and the suite will drift (L7). Pin every name you expect them to type.',
    '',
    'Do NOT write any test_' + subslug + '_*.py file yourself. Do NOT run git.',
  ].join('\n'),
  { agentType: 'test-writer', label: 'contract', phase: 'Contract', schema: CONTRACT_SCHEMA }
)

if (!contract) throw new Error('module-tests: the Contract phase returned nothing — re-run before fanning out')

// ---------------------------------------------------------------------------
// Phase 2 — four lanes in parallel, disjoint files
// ---------------------------------------------------------------------------

const LANES = [
  {
    key: 'models',
    brief:
      'Model invariants: field defaults, __str__, every STATUS/type CHOICES value, per-tenant auto-numbers ' +
      '(sequence, prefix, and no collision across tenants), computed properties, unique_together WITH tenant, ' +
      'and — for anything ledger- or stock-adjacent — that balances/quantities are DERIVED via aggregate rather ' +
      'than stored as editable fields.',
  },
  {
    key: 'forms',
    brief:
      'Form validation: required fields, invalid input rejected with the right error, clean() rules, and — this is ' +
      'the one that has shipped bugs here — assert that tenant, the auto-number, owner/created_by, workflow status, ' +
      'every secret/credential/hash field, every system *_at timestamp and every derived counter are NOT in ' +
      'form.fields (L20/L22). Also assert FK ModelChoiceField querysets are tenant-scoped: a field offered to ' +
      'tenant A must not contain tenant B rows.',
  },
  {
    key: 'views',
    brief:
      'View/CRUD integration: list 200 with search, each filter, and pagination (build enough rows to force page 2 ' +
      '— page-2 guards are invisible at seed size, L9); create POST saves with request.tenant; edit; delete is ' +
      'POST-only and a GET must not delete; the right template is used and every context key from the contract is ' +
      'present AND populated (asserting the key exists but not that it has rows proves nothing, L41). Wrap at least ' +
      'one list assertion in django_assert_max_num_queries to catch N+1, including chained __str__ FK hops.',
  },
  {
    key: 'security',
    brief:
      'Isolation and hardening: logged in as tenant A, requesting a tenant B pk on detail/edit/delete returns 404; ' +
      "A's list never contains B's rows; a crafted POST carrying B's pk in an FK field is rejected; anonymous " +
      'redirects to login; @tenant_admin_required actions are blocked for a plain tenant member; CSRF enforced with ' +
      'Client(enforce_csrf_checks=True). Negative input: junk FK filter param (?x=abc) -> 200 not 500 (L11); for any ' +
      'view hand-parsing a decimal from POST, "NaN"/"Infinity"/garbage/negative/over-max_digits -> friendly error, ' +
      'never a 500, and an absent prerequisite must be REJECTED rather than falling through to approval (L35). ' +
      'Pair every negative case with the POSITIVE path that proves the guard did not just break the feature (L44).',
  },
]

phase('Write')
log('Fanning out ' + LANES.length + ' test-writer lanes over disjoint files')

const CONTRACT_JSON = JSON.stringify(contract, null, 2)

const written = await parallel(
  LANES.map(L => () =>
    agent(
      [
        HEADER,
        '',
        'YOU OWN EXACTLY ONE FILE: ' + fileFor(L.key),
        '',
        'Three sibling lanes are writing the other three test_' + subslug + '_*.py files RIGHT NOW.',
        '  - Do NOT create, edit or delete ANY other file. ' + TESTS_DIR + '/conftest.py and __init__.py are final',
        '    and owned by the contract step — if you need a fixture they do not provide, define it inside YOUR file.',
        '  - Do NOT edit project (non-test) code. If you find a real product bug, do not paper over it and do not',
        '    assert the buggy behaviour — report it in your return text with file:line and let the Green phase fix it.',
        '  - Do NOT run git.',
        '',
        'NAMING — no exceptions:',
        '  - every test function is named  test_' + subslug + '_<what_it_asserts>',
        '  - every module-level helper, constant or fixture you define is named  _' + subslug + '_<name>',
        'Your file is new, so nothing you define can shadow a sibling lane\'s — separate test modules have separate',
        'namespaces. The prefix protects the NEXT sub-module, whose agent will append to files around yours, and it',
        'makes a failure self-identifying. The collision that genuinely DOES cross files is a conftest.py fixture,',
        'which is exactly why conftest.py is owned by the contract step and off-limits to you (L47).',
        '',
        'YOUR LANE',
        '  ' + L.brief,
        '',
        'PINNED CONTRACT — use these exact names. Do not guess a model field, CHOICES value, url name or context key',
        'that is not in here; grep the real code and, if it is genuinely missing from the contract, say so in your',
        'return text.',
        '```json',
        CONTRACT_JSON,
        '```',
        '',
        'Finish by running ONLY your own file to green:',
        '  venv\\Scripts\\python.exe -m pytest -q ' + fileFor(L.key),
        'Then return: the file you wrote, the test count, pass/fail, and any product bug you found (file:line).',
      ].join('\n'),
      { agentType: 'test-writer', label: 'tests:' + L.key, phase: 'Write' }
    )
  )
)

const lost = LANES.filter((L, i) => !written[i]).map(L => L.key)
if (lost.length) log('WARNING — no result from lane(s): ' + lost.join(', ') + ' — the Green phase must write them')

// ---------------------------------------------------------------------------
// Phase 3 — one full unfiltered run
// ---------------------------------------------------------------------------

phase('Green')

const green = await agent(
  [
    HEADER,
    '',
    'Four lanes just wrote these files in parallel, each verified only against ITSELF:',
    LANES.map(L => '  - ' + fileFor(L.key)).join('\n'),
    lost.length ? '  MISSING (its lane returned nothing — write it yourself from the contract): ' + lost.map(k => fileFor(k)).join(', ') : '',
    '',
    'YOUR JOB: make the WHOLE app suite green, and prove the fan-out did no collateral damage.',
    '',
    '  1. Run the FULL app suite, unfiltered:  venv\\Scripts\\python.exe -m pytest -q apps/' + slug,
    '     Never use -k to scope this run. A filtered run excludes exactly the tests a shared-file or conftest',
    '     change can break — the blast radius of a collision is by definition the code that used the name BEFORE',
    '     you, which is the complement of any filter selecting your work (L47). If the app has a',
    '     test_suite_hygiene.py, this full run is what makes it fire.',
    '  2. Fix every failure:',
    '     - A conftest fixture the contract step added that shadows an existing one, or any collision with an',
    '       existing sibling suite -> rename the NEW definition (prefix _' + subslug + '_ / ' + subslug + '_),',
    '       never by editing the older suite.',
    '     - A genuine product bug -> FIX the product code minimally and correctly, and report it with file:line.',
    '       Never assert the buggy behaviour to get green.',
    '     - A wrong test expectation -> fix the test.',
    '  3. Remove duplicate coverage where two lanes wrote the same assertion; keep it in the lane that owns it.',
    '  4. Re-run the full app suite until it is green, then run the whole project suite once:',
    '     venv\\Scripts\\python.exe -m pytest -q',
    '     so a collision with another app surfaces here and not in the Stop hook.',
    '',
    'Do NOT run git — the parent session commits one file per commit.',
    '',
    'Report: final test count, pass/fail, per-file counts, every product bug fixed (file:line + what it was), and',
    'any test you deleted or renamed and why.',
  ].filter(Boolean).join('\n'),
  { agentType: 'test-writer', label: 'green', phase: 'Green' }
)

return {
  files: LANES.map(L => fileFor(L.key)),
  contract: contract,
  lanes: written,
  lostLanes: lost,
  green: green,
}
