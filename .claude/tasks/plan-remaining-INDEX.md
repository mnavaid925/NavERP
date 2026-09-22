# Remaining work for modules 0–7.13 — plan index

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Truth source:** `LIVE_LINKS`
(148 live sub-modules at authoring; **159 as of 2026-09-22**)

Five plans, one per remaining item. Each is self-contained — read only the one you are working on.
**Do them one at a time.**

> **Re-verified 2026-09-22 — four of the five are now closed.** Only **Plan 1** is real remaining work.
>
> | # | Plan | Status 2026-09-22 |
> |---|------|-------------------|
> | 1 | [`plan-remaining-1-module0-submodules.md`](plan-remaining-1-module0-submodules.md) | **OPEN** — 0.16–0.21 (6 sub-modules); the only real work left |
> | 2 | [`plan-remaining-2-land-fixed-defects.md`](plan-remaining-2-land-fixed-defects.md) | ✅ **COMPLETE** |
> | 3 | [`plan-remaining-3-readme-module6-row.md`](plan-remaining-3-readme-module6-row.md) | ✅ **COMPLETE** |
> | 4 | [`plan-remaining-4-docs-closeout-sweep.md`](plan-remaining-4-docs-closeout-sweep.md) | ✅ **COMPLETE** |
> | 5 | [`plan-remaining-5-housekeeping.md`](plan-remaining-5-housekeeping.md) | 🟨 **Item A done**; Items B + C open (small) |
>
> Commits proving 2/3/4: `c7a9eef4`, `81e7a99d`, `9248505f`, `3db5a589`, `4b088965`, `1962ae89`.
> Plan 5 Item A: `32913e28`, `3fc46276`, `33447c3a`, `5c841a3e` (dashboard tests, 15 green).

| # | Plan | Item | Size | Recommended order |
|---|------|------|------|-------------------|
| 1 | [`plan-remaining-1-module0-submodules.md`](plan-remaining-1-module0-submodules.md) | Module 0: **6 unbuilt sub-modules (0.16–0.21)** + `SKILL.md` (**now written**) | **Large** — 6 full build runs | 4th (biggest, do it when you have a long stretch) |
| 2 | [`plan-remaining-2-land-fixed-defects.md`](plan-remaining-2-land-fixed-defects.md) | 3 defect fixes sitting uncommitted in the tree | Small | ✅ done |
| 3 | [`plan-remaining-3-readme-module6-row.md`](plan-remaining-3-readme-module6-row.md) | `README.md:1199` — Module 6's row lost its leading cells | Tiny | ✅ done |
| 4 | [`plan-remaining-4-docs-closeout-sweep.md`](plan-remaining-4-docs-closeout-sweep.md) | Stale status claims **+ 7.15's skipped Phase-7 close-out** | Medium | ✅ done |
| 5 | [`plan-remaining-5-housekeeping.md`](plan-remaining-5-housekeeping.md) | `apps/dashboard/` has 0 tests; 3 stray artifacts; 14 BOM files | Small | 5th (optional) |

## Suggested sequence

**2 → 3 → 4 → 1 → 5** — **2, 3 and 4 are done**; what remains is **1** (then 5's Items B/C, which are
minutes of work).

Plan 2 first because a dirty tree blocks the "claim the tree" step of every build run (L45), and Plan 1
is a series of build runs. Plan 3 and Plan 4 both edit the README roadmap table — do them in the same
sitting, as separate commits.

## The headline finding

**Modules 1–6 and 7.1–7.13 are structurally complete.** All six integrity checks pass: every migration
applied, all 3,350 route names reverse, all 1,995 template references exist on disk, all 581 sidebar
targets resolve, and every model is referenced by its seeder (except three that legitimately are not —
`core.AuditLog`, `crm.HealthScore`, `procurement.WidgetPreference`).

**The only material gap in the range was Module 0 — 7 of 21 sub-modules built at authoring. It is now
15 of 21 (0.1–0.15); the remaining 6 are 0.16–0.21.** Everything else in these five plans was defects,
stale documentation, or housekeeping — and Plans 2, 3 and 4 have since landed.

**Two newly discovered items not in the original five:**
- **7.15's docs close-out was skipped** — a concurrent session committed 7.15's tests then moved straight
  to 7.16. Folded into **Plan 4, Item A** — **now done.**
- **Module 0's live sub-modules were only partially mapped** — 0.3, 0.7, 0.9 and 0.14 each surfaced just
  **1 of their 5** NavERP bullets. **Resolved by Plan 1 Step 0** (`.claude/tasks/plan-1-module0-reconcile.md`):
  nothing was built-but-unsurfaced; every unmapped bullet was genuinely absent or partial.

## Reusable verification

```bash
venv\Scripts\python.exe temp\audit_integrity.py
```

Six checks, all must pass. Catches the four failure modes `manage.py check` and
`makemigrations --check --dry-run` cannot see — including the one that let 7.10 ship a Live sidebar over
21 missing templates and an unapplied migration.

## House rules (apply to every plan)

- One file per commit. **Never `git push`** — the user pushes.
- `venv\Scripts\python.exe` — Django is not on system python.
- `git status` before starting: a dirty tree at session start is not yours (L45).
- A concurrent session is **mid-build on 7.18** in `apps/projects/` and `templates/projects/reporting/`
  (as of 2026-09-22 — it was 7.16 when this index was written). Re-read shared files before editing;
  never commit another session's in-flight `contract-projects-*.md` or its modified templates.
