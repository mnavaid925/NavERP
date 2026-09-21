# Plan 4 — Documentation close-out sweep (stale status claims + the skipped 7.15 close-out)

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Status:** ✅ **COMPLETE — verified 2026-09-21**
**Scope:** `README.md`, `NavERP.md`, `.claude/skills/*/SKILL.md`, `.claude/tasks/todo.md`
**Effort:** medium — mostly mechanical, but item A is a real Phase-7 close-out

> **CLOSED 2026-09-21.** Most of this plan had already been done by the concurrent session since it was
> authored; what remained was **four stale status cells and one stale preamble**, all now corrected.
> Re-derived every number from `LIVE_LINKS` rather than from the plan's own tables, which were written at
> `0ba7f760` and were themselves stale — the plan said **148 live sub-modules** and **module 0 at 7 of 21**;
> the truth is now **157** and **14 of 21**.
>
> | item | state when I reached it | action |
> |---|---|---|
> | **A** — 7.15's skipped Phase-7 close-out | **already done**: `SKILL.md` has a 7.15 section, `README.md`'s module-7 row documents 7.15, `todo.md:8877` carries the close-out note, and **all 26 of 7.15's plan boxes are ticked** including the test wave (*28/28 passing*) | verified only |
> | **B** — README rows | module 3 already correct; **module 0 and module 7 stale** | **fixed** |
> | **C** — `NavERP.md` rows 61–68 + preamble | rows 62–67 correct; **rows 61 and 68 stale, and the module-0 preamble stale** | **fixed** |
> | **D** — `SKILL.md` As-built lines | `procurement` frontmatter already says `6.1–6.19`; `projects` already lists 7.15 + 7.17 | verified only |
> | **E** — `todo.md` | tracking-convention note already at the top; 7.15's boxes already ticked; no mass-ticking attempted | verified only |
>
> **Commits:** `4b088965` (`README.md`), `1962ae89` (`NavERP.md`).
>
> **A correction I had to make to my own first draft:** the module-0 preamble now lists each live
> sub-module's mapped-bullet count, and I first wrote `0.3 maps 4 of 5`. The computed answer is
> **1 of 5**. Every count in that sentence is now machine-derived, and two carry a caveat that matters:
> 0.4's single gap is `SSO & Federation` (deliberately unmapped) and 0.9's `User Activity Tracking` is
> realized as the `Activities` register, so it is a **label mismatch, not a gap**.

---

## Why this matters

Every claim below was checked against `apps/core/navigation.py` `LIVE_LINKS` (the source of truth), not
against other docs. **`LIVE_LINKS` is authoritative: a sub-module is built iff it has a `LIVE_LINKS["N.M"]`
entry.** Current truth: **148 live sub-modules** across modules 0–7.

The docs are the project's onboarding surface for future sessions, and a stale status table is how a
future session concludes a built module is "Roadmap" and rebuilds it.

---

## Item A — Finish 7.15's Phase-7 close-out (highest priority here)

**This was skipped.** A concurrent session committed 7.15's tests and then went straight to 7.16
(commits `906b72d3` research, `0ba7f760` todo — both 15:11/14:57 today). The Phase-7 docs step never ran.
`.claude/tasks/todo.md` lines 78–83 still show the test wave and the docs item unticked.

Evidence that 7.15 docs are absent:
- `README.md` — **no 7.15 status at all.** The only `7.15` string is a deferral reference inside line 1200's
  prose. Module 7's row still reads `🟦 7.1–7.14 built — 14 of 19 sub-modules`.
- `.claude/skills/projects/SKILL.md:62` — `**As-built: 7.1 + … + 7.14.** 7.15–7.19 are roadmap (a…`
- `.claude/tasks/todo.md` — no `### Projects 7.15 … (close-out YYYY-MM-DD)` note.

### Steps

1. **Tick the test-wave boxes** in `todo.md` lines 78–82 — the four files exist and are committed
   (`6fe88b88`, `4a9a9281`, `e65edf75`, `63d99eeb`). **Land Plan 2 first** so the suite is provably green
   before you tick them.
2. **Add a `## 7.15` section to `.claude/skills/projects/SKILL.md`** — follow the 7.14 section's shape:
   what the sub-module owns, the models with their `[XXX-]` prefixes, routes, templates, seeder block
   (`_financial_billing` in `seed_projects.py`), tests, sidebar leaves. Then refresh:
   - the **As-built** line → `7.1 + … + 7.15.` (7.16–7.19 roadmap)
   - the `description:` frontmatter if it enumerates sub-modules
   - the Routes / Templates / Seeder / Tests / Sidebar summary blocks
3. **Update `README.md` module 7's row** → `🟦 7.1–7.15 built — 15 of 19 sub-modules.` and append a 7.15
   paragraph in the established style (it is long-form prose — mirror 7.14's: the sub-module's ruling, what
   it deliberately does *not* own, migrations `0022`, seeder, template/test counts).
4. **Add the close-out note** to `todo.md`: `### Projects 7.15 — Financial & Billing Management
   (close-out 2026-09-19)` and tick the docs box.
5. **Mark the phases done in `build-state.json`** — but note it is **gitignored local state, never commit
   it**, and it currently still points at 7.10, so it needs re-registering rather than a simple edit.

**Commits:** one per file — `SKILL.md`, `README.md`, `todo.md`.

---

## Item B — `README.md` module-table statuses (3 rows wrong)

Table header at `README.md:1191`. Verified against `LIVE_LINKS`:

| line | module | current text | truth | fix |
|---|---|---|---|---|
| 1193 | 0 | `✅ Foundation built (0.1 complete)` | **7** live: `0.1 0.2 0.3 0.5 0.7 0.9 0.14` | `🟦 7 of 21 sub-modules built (0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.14) — see Plan 1` |
| 1196 | 3 | `🟨 3.1–3.21 built — 21 of 41 sub-modules` | **41 of 41** | `✅ 3.1–3.41 built — all 41 sub-modules` |
| 1200 | 7 | `🟦 7.1–7.14 built — 14 of 19` | **15 of 19** (7.15 live) | `🟦 7.1–7.15 built — 15 of 19` — **do this as part of Item A** |

Modules 1, 2, 4, 5, 6 rows are correct. **Module 6's row is structurally broken — fix that first via
Plan 3.**

> **Edit carefully:** the module-7 row is ~40k characters. Use a narrow, unique `old_string`
> (e.g. `🟦 7.1–7.14 built — 14 of 19 sub-modules.`) and never retype the line.

---

## Item C — `NavERP.md` "Module status & app mapping" table (rows 61–68)

This table is badly stale and long known to be so:

| line | module | says | truth |
|---|---|---|---|
| 61 | 0 | `✅ Foundation built; sub-module 0.1 complete` | 7 of 21 live |
| 64 | 3 | `🟦 In progress — 3.1–3.12 built (12 of 41)` | **41 of 41** |
| 65 | 4 | `⬜ Roadmap` | **19 of 19 complete** |
| 66 | 5 | `⬜ Roadmap` | **20 of 20 complete** |
| 67 | 6 | `⬜ Roadmap` | **19 of 19 complete** |
| 68 | 7 | `⬜ Roadmap` | **15 of 19** (through 7.15) |

Also fix the module-0 preamble at `NavERP.md:90-96`, which says the remaining sub-modules "are on the
roadmap" — accurate, but it names only 0.1 as built; list all seven.

**Consider adding a maintenance note** under the table: *"This table goes stale — `LIVE_LINKS` in
`apps/core/navigation.py` is authoritative."* That is already a project lesson and would stop the next
session trusting the table.

**Commit:** `NavERP.md` alone.

---

## Item D — `SKILL.md` "As-built" lines

Most are current. Verified stale ones:

- `.claude/skills/procurement/SKILL.md:3` — the frontmatter `description` says
  `touch procurement sidebar wiring (LIVE_LINKS 6.1–6.15)` while the body's last block (line 1216) already
  reads `As-built now: 6.1–6.19`. Fix the frontmatter to `6.1–6.19`.
- `.claude/skills/projects/SKILL.md:62` — see Item A.
- `.claude/skills/core/SKILL.md` — **does not exist**; create it in Plan 1.

**How to find any others** (repeatable, and the honest way to check rather than eyeballing):

```bash
venv\Scripts\python.exe -c "import os,sys,re,django; sys.path.insert(0,os.getcwd()); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from apps.core.navigation import LIVE_LINKS; from collections import defaultdict; d=defaultdict(set); [d[k.split('.')[0]].add(k) for k in LIVE_LINKS]; [print(m, len(d[m]), 'live |', f'.claude/skills/{a}/SKILL.md') for m,a in {1:'crm',2:'accounting',3:'hrm',4:'scm',5:'inventory',6:'procurement',7:'projects'}.items()]"
```

Then for each module, confirm the SKILL's As-built line enumerates up to its highest live `N.M`.

> **Caution — a heading/coverage heuristic will lie to you here.** A `^#{2,4}\s+.*(\d+\.\d+)` scan reports
> CRM as documenting only 1 of 12 sub-modules and accounting 1 of 15. Both are false: CRM uses
> `# §1.2 …` headings (single hash, `§` prefix) and accounting documents 2.6–2.15 under one
> "Advanced sub-modules" heading. **Verify any docs-coverage heuristic against one known-good module
> before believing it** — this exact false alarm was raised and cleared on 2026-09-19.

---

## Item E — `todo.md` unticked boxes

`todo.md` has 2,163 `- [ ]` lines, but **only the top two plans (7.15, 7.14) use the ticked convention.**
Older plans were never ticked and their completion lives in prose `## Close-out review` sections instead —
procurement 6.9's block, for example, has 17 unticked boxes while 6.9 is shipped, in `LIVE_LINKS`
(`navigation.py:1530`) and closed out in prose.

**Do not "tick the backlog".** That would be ~2,100 meaningless edits. Only:
1. Tick 7.15's test-wave boxes and add its close-out note (Item A).
2. Add a one-line note at the very top of `todo.md` stating the convention:
   *"Only the plans above the 6.9 block are tracked with checkboxes; older plans record completion in
   their prose `## Close-out review` section. Absence of a tick is not evidence of missing work."*
3. The `- [ ]` lines under each plan's "Later passes / deferred" heading are **deliberate parkings** onto
   other sub-modules — leave them.

---

## Done when

- [x] 7.15 has a `SKILL.md` section, a README row + paragraph, and a `todo.md` close-out note — all
      verified present on 2026-09-21 (the concurrent session had already landed them).
- [x] `README.md` rows 1193 / 1196 / 1200 are accurate; module 6's row is a valid table row (Plan 3).
      Module 0 → `14 of 21 sub-modules built (0.1–0.14)`; module 3 was already correct; module 7 →
      `7.1–7.17 built — 17 of 19`. Table re-verified: lines 1191–1216, header 5 pipes, every row starts
      with `|`, no short row, 24 module rows.
- [x] `NavERP.md` rows 61–68 are accurate and the "goes stale" maintenance note is present (line 86).
      Row 61 → `14 of 21 built — 0.1–0.14 (7 remain: 0.15–0.21)`; row 68 → `7.1–7.17 built — 17 of 19`.
      The module-0 preamble now lists all 14 and points at the reconcile file.
- [x] `procurement/SKILL.md` frontmatter says 6.1–6.19 — already correct when reached.
- [x] `todo.md` carries the tracking-convention note; 7.15's boxes are ticked (26/26).
- [x] Each file committed separately: `4b088965` (`README.md`), `1962ae89` (`NavERP.md`).
      **Never `git push`.**

## Risks

- **40k-character rows.** Edit with narrow unique anchors; never retype.
- **Concurrent 7.16 session** is editing `todo.md` and `apps/projects/` right now — re-read `todo.md`
  before editing and expect the 7.15 block to still be at the top (newest plans are prepended).
- **`build-state.json` is gitignored** — update it locally, never commit it.
