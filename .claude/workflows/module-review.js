export const meta = {
  name: 'module-review',
  description: 'Run the six NavERP review agents in parallel over one just-built sub-module and return one consolidated findings markdown',
  whenToUse: 'Step 4 of the CLAUDE.md Module Creation Sequence — right after the sub-module code is built, verified and committed. Replaces running code-reviewer / explorer / frontend-reviewer / performance-reviewer / qa-smoke-tester / security-reviewer one at a time.',
  phases: [
    { title: 'Review', detail: 'six specialist reviewers in parallel, read-only, structured findings' },
  ],
}

// ---------------------------------------------------------------------------
// args: { slug, submodule, title?, base, head?, date? }
//   slug      app slug, e.g. "scm"
//   submodule the N.M number, e.g. "4.17"
//   title     the NavERP.md sub-module title, e.g. "Returns Management"
//   base      sha captured BEFORE the build started (git rev-parse HEAD at Phase 0)
//   head      OPTIONAL end of the changeset, default "HEAD". Pass it when reviewing a sub-module
//             whose build is NOT the tip — e.g. resuming an interrupted review after a LATER
//             sub-module has already landed on top. Without it the wave reviews the later work
//             too, and the reviewers waste their lanes re-reporting an already-fixed changeset.
//   date      today's date string (scripts cannot call Date.now())
// ---------------------------------------------------------------------------

const A = args || {}
const slug = A.slug
const sub = A.submodule
const title = A.title || ''
const base = A.base
const head = A.head || 'HEAD'
const date = A.date || '(see git log)'

if (!slug || !sub || !base) {
  throw new Error(
    'module-review needs args {slug, submodule, base}. ' +
    'Example: {slug:"scm", submodule:"4.17", title:"Returns Management", base:"3de294ca", date:"2026-08-14"}'
  )
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'file', 'line', 'problem', 'fix'],
        properties: {
          severity: { type: 'string', enum: ['Critical', 'Important', 'Minor'] },
          file: { type: 'string', description: 'repo-relative path, e.g. apps/scm/views/Returns/Rma.py' },
          line: { type: 'integer', description: '1-indexed line the finding anchors to' },
          problem: { type: 'string', description: 'one sentence: what is wrong and what it causes' },
          fix: { type: 'string', description: 'the concrete change to make — specific enough to apply without re-deriving it' },
          lesson: { type: 'string', description: 'lessons.md id if this failure class shipped before (e.g. "L33"), else empty string' },
        },
      },
    },
    done_well: { type: 'string', description: 'one specific thing this sub-module got right' },
    notes: { type: 'string', description: 'app-wide or pre-existing observations that are NOT actionable for this sub-module' },
  },
}

const LANES = [
  {
    type: 'code-reviewer',
    lane:
      'Correctness and conventions: view/template context contract, {% url %} names, None-guards, pagination guards, ' +
      'GET-param and hand-parsed decimal validation, choice-value drift, form.save(commit=False) completeness, ' +
      'multi-tenancy on every queryset/form/aggregate, backend package structure + __init__ re-exports, ' +
      'CRUD/filter completeness, migrations matching model edits, transaction.atomic on multi-writes, seeder idempotency.',
    extra: '',
  },
  {
    type: 'security-reviewer',
    lane:
      'Security: cross-tenant IDOR on every pk lookup, @login_required / @tenant_admin_required gates, view-level ' +
      'status guards behind hidden buttons, CSRF on every POST, XSS/|safe, mass assignment, secrets or hashes in ' +
      'Meta.fields, secrets leaked through messages.success, file-upload validation, open redirects, unguessable-token surfaces.',
    extra: '',
  },
  {
    type: 'performance-reviewer',
    lane:
      'Query efficiency: N+1 in list/detail views and templates (including chained __str__ / property FK hops that need ' +
      'select_related("parent__owner")), missing prefetch_related on reverse loops, .count() vs len(), aggregates for ' +
      'derived balances instead of Python loops, pagination applied after filters, db_index on tenant-scoped ORDER BY / filter columns.',
    extra: '',
  },
  {
    type: 'frontend-reviewer',
    lane:
      'Templates: theme.css design-system fidelity (colour-named modifiers ONLY — badge-green/red/amber/info/muted/slate, ' +
      'stat-icon blue/green/orange/purple/slate; a semantic -success/-danger class renders unstyled, L33), multi-line ' +
      '{# #} comment leaks (L2), badge branches matching exact CHOICES values with a get_FIELD_display fallback, ' +
      'Actions column + detail Actions sidebar completeness, label for=/id= pairing and accessibility, empty states, ' +
      'filter widgets reflecting request.GET.',
    extra: '',
  },
  {
    type: 'explorer',
    lane:
      'Contract breaks between the layers nobody else reads end-to-end. Map the as-built sub-module (urls -> views -> ' +
      'forms -> templates -> navigation) and report each BREAK as a finding.',
    extra:
      'Do not return a tour of the code — your deliverable is findings only. Specifically hunt: a {% url %} / reverse() ' +
      'name with no matching route; a template variable that is not in the view context dict; a model/form/view/url ' +
      'module missing from its package __init__.py re-export block; a render() pointing at a template path that does not ' +
      'exist; a LIVE_LINKS["' + sub + '"] entry pointing at a dead url name; a template shipped at a banned flat path ' +
      '(templates/<app>/<submodule>/<entity>_<page>.html instead of <entity>/<page>.html).',
  },
  {
    type: 'qa-smoke-tester',
    lane:
      'Runtime truth: migrate + seed, then sweep every new url of this sub-module through the Django test client as ' +
      'admin_acme — status in (200,302) AND content assertions (no {# / {% comment leak, page title present, detail ' +
      'page contains the sampled object identifier), one filtered list, one junk-param list (?category=abc), page 2 ' +
      'where rows exceed the page size, and cross-tenant IDOR -> 404.',
    extra:
      'OVERRIDE your standard instructions in exactly one way: do NOT fix anything and do NOT edit any project file — ' +
      'report each failure as a finding instead (Critical for a 500 / leak / IDOR hole, Important for a content-assertion ' +
      'miss). You MAY still write, run and delete your throwaway script under temp/ and run migrate + the seeders — you ' +
      'are the only agent in this wave that touches the database.',
  },
]

function promptFor(L) {
  const lines = [
    'You are one of six agents reviewing ONE just-built NavERP sub-module in a single parallel wave.',
    '',
    'TARGET',
    '  Sub-module: ' + sub + (title ? ' ' + title : ''),
    '  Code:       apps/' + slug + '/  and  templates/' + slug + '/',
    '  Changeset:  ' + base + '...' + head + ' — the working tree is CLEAN (the build committed one file per commit),',
    '              so review the RANGE, not the working tree:',
    '                git diff --stat ' + base + '...' + head,
    '                git diff ' + base + '...' + head,
    '  Anything outside that range is pre-existing and OUT OF SCOPE.',
    '',
    'YOUR LANE — stay inside it. Five other agents cover the rest and duplicates are merged automatically,',
    'so breadth outside your lane costs wall-clock without adding coverage.',
    '  ' + L.lane,
    '',
    'WAVE RULES',
    '  - READ-ONLY on project code. Do NOT Edit or Write any app / template / config / test file, and do NOT run',
    '    `git add` or `git commit`. A dedicated code-fixer agent applies every fix after this wave.',
    '  - Every finding cites a real repo-relative path + line number you verified by READING the file.',
    '  - One finding = one problem, one location, one concrete fix. Never bundle two problems into one item.',
    '  - The `fix` field must be specific enough for another engineer to apply without re-deriving your analysis.',
    '  - Prefer fewer certain findings over many speculative ones. An empty findings array is a valid answer.',
    '  - Severity: Critical = cross-tenant read/write, a new model with no tenant FK, authorization bypass, secret',
    '    exposure, data loss, a crash on a mainline path, a schema-affecting model change with no migration.',
    '    Important = broken secondary path (page-2 500, junk-param 500, NaN/Infinity 500), a CRUD/filter contract',
    '    gap, a missing __init__.py re-export, multi-write without transaction.atomic, a view/template context',
    '    mismatch, a banned flat template path. Minor = naming, dead code, polish, a missing badge {% else %}.',
    '  - If a failure class already shipped in this repo, put its lessons.md id (e.g. "L33") in the `lesson` field.',
  ]
  if (L.extra) {
    lines.push('', 'LANE OVERRIDE', '  ' + L.extra)
  }
  lines.push(
    '',
    'Return the structured findings object. Put app-wide or pre-existing observations in `notes` — they are recorded',
    'separately and do NOT enter the fix queue.'
  )
  return lines.join('\n')
}

phase('Review')
log('Reviewing ' + slug + ' ' + sub + ' over ' + base + '...' + head + ' with ' + LANES.length + ' agents in parallel')

const raw = await parallel(
  LANES.map(L => () =>
    agent(promptFor(L), {
      agentType: L.type,
      label: L.type,
      phase: 'Review',
      schema: FINDINGS_SCHEMA,
    })
  )
)

// --- aggregate -------------------------------------------------------------

const SEV_ORDER = { Critical: 0, Important: 1, Minor: 2 }
const PREFIX = { Critical: 'C', Important: 'I', Minor: 'M' }
const normalize = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 70)

const dead = []
const perAgent = {}
const merged = new Map()
const notes = []
const wins = []

raw.forEach((res, i) => {
  const who = LANES[i].type
  if (!res) {
    dead.push(who)
    perAgent[who] = null
    return
  }
  const list = Array.isArray(res.findings) ? res.findings : []
  perAgent[who] = list.length
  if (res.notes && String(res.notes).trim()) notes.push({ who: who, text: String(res.notes).trim() })
  if (res.done_well && String(res.done_well).trim()) wins.push({ who: who, text: String(res.done_well).trim() })

  for (const f of list) {
    if (!f || !f.file) continue
    const severity = SEV_ORDER[f.severity] === undefined ? 'Important' : f.severity
    const line = Number.isInteger(f.line) ? f.line : 0
    const key = f.file + ':' + line + ':' + normalize(f.problem)
    const hit = merged.get(key)
    const fix = String(f.fix || '').trim()
    if (hit) {
      if (hit.agents.indexOf(who) === -1) hit.agents.push(who)
      // keep the strictest severity of the agents that flagged it
      if (SEV_ORDER[severity] < SEV_ORDER[hit.severity]) hit.severity = severity
      if (!hit.lesson && f.lesson) hit.lesson = f.lesson
      // two agents can agree on the defect but suggest materially different fixes — keep both
      if (fix && normalize(fix) !== normalize(hit.fix) && hit.altFixes.indexOf(fix) === -1) {
        hit.altFixes.push(fix)
      }
    } else {
      merged.set(key, {
        severity: severity,
        file: f.file,
        line: line,
        problem: String(f.problem || '').trim(),
        fix: fix,
        altFixes: [],
        lesson: String(f.lesson || '').trim(),
        agents: [who],
      })
    }
  }
})

const all = Array.from(merged.values()).sort((a, b) =>
  (SEV_ORDER[a.severity] - SEV_ORDER[b.severity]) ||
  a.file.localeCompare(b.file) ||
  (a.line - b.line)
)

const counters = { Critical: 0, Important: 0, Minor: 0 }
for (const f of all) {
  counters[f.severity] += 1
  f.id = PREFIX[f.severity] + counters[f.severity]
}

if (dead.length) log('WARNING — no result from: ' + dead.join(', ') + ' (re-run those lanes before trusting coverage)')
log('Findings: ' + counters.Critical + ' Critical, ' + counters.Important + ' Important, ' + counters.Minor + ' Minor (' + all.length + ' after dedupe)')

// --- render the findings file ----------------------------------------------

const out = []
out.push('# Review findings — ' + slug + ' ' + sub + (title ? ' ' + title : ''))
out.push('')
out.push('Range: `' + base + '...' + head + '` · Generated: ' + date)
out.push('Wave (parallel): ' + LANES.map(L => L.type).join(' · '))
out.push('')
out.push('## Summary')
out.push('')
out.push('| Severity | Count |')
out.push('|---|---|')
out.push('| Critical | ' + counters.Critical + ' |')
out.push('| Important | ' + counters.Important + ' |')
out.push('| Minor | ' + counters.Minor + ' |')
out.push('| **Total (deduped)** | **' + all.length + '** |')
out.push('')
out.push('| Agent | Raw findings |')
out.push('|---|---|')
for (const L of LANES) {
  const n = perAgent[L.type]
  out.push('| ' + L.type + ' | ' + (n === null || n === undefined ? '**NO RESULT — re-run this lane**' : n) + ' |')
}
out.push('')
out.push('## How to work this file (code-fixer)')
out.push('')
out.push('Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one')
out.push('`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`')
out.push('as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.')
out.push('')

if (!all.length) {
  out.push('## No findings')
  out.push('')
  out.push('All six lanes returned clean. Verify the per-agent table above shows no `NO RESULT` lane before trusting this.')
  out.push('')
}

for (const sev of ['Critical', 'Important', 'Minor']) {
  const group = all.filter(f => f.severity === sev)
  if (!group.length) continue
  out.push('## ' + sev)
  out.push('')
  for (const f of group) {
    out.push('### ' + f.id + ' — `' + f.file + ':' + f.line + '`')
    out.push('')
    out.push('- **Found by:** ' + f.agents.join(', '))
    if (f.lesson) out.push('- **Lesson:** ' + f.lesson)
    out.push('- **Problem:** ' + f.problem)
    out.push('- **Fix:** ' + f.fix)
    for (const alt of f.altFixes) out.push('- **Also suggested:** ' + alt)
    out.push('- **Status:** [ ] open')
    out.push('')
  }
}

if (notes.length) {
  out.push('## Notes — app-wide / pre-existing (NOT in the fix queue)')
  out.push('')
  for (const n of notes) out.push('- **' + n.who + ':** ' + n.text)
  out.push('')
}

if (wins.length) {
  out.push('## Done well')
  out.push('')
  for (const w of wins) out.push('- **' + w.who + ':** ' + w.text)
  out.push('')
}

return {
  path: '.claude/tasks/review-' + slug + '-' + sub + '.md',
  counts: counters,
  total: all.length,
  deadLanes: dead,
  markdown: out.join('\n'),
}
