# Remaining work for modules 0–7.13 — plan index

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Truth source:** `LIVE_LINKS`
(148 live sub-modules at authoring; **164 as of 2026-09-26**)

Five plans, one per remaining item. Each is self-contained — read only the one you are working on.
**Do them one at a time.**

> **Re-verified 2026-09-26 — all five are now closed. Only Plan 1 is real remaining work.**
>
> | # | Plan | Status 2026-09-26 |
> |---|------|-------------------|
> | 1 | [`plan-remaining-1-module0-submodules.md`](plan-remaining-1-module0-submodules.md) | 🟨 **OPEN** — **0.18–0.21 (4 sub-modules)**; the only real work left |
> | 2 | [`plan-remaining-2-land-fixed-defects.md`](plan-remaining-2-land-fixed-defects.md) | ✅ **COMPLETE** |
> | 3 | [`plan-remaining-3-readme-module6-row.md`](plan-remaining-3-readme-module6-row.md) | ✅ **COMPLETE** |
> | 4 | [`plan-remaining-4-docs-closeout-sweep.md`](plan-remaining-4-docs-closeout-sweep.md) | ✅ **COMPLETE** |
> | 5 | [`plan-remaining-5-housekeeping.md`](plan-remaining-5-housekeeping.md) | ✅ **COMPLETE** — all three items closed |
>
> Commits proving 2/3/4: `67e0195e`, `7a4d55d3`, `7c2c446f` (plus the earlier `c7a9eef4`, `81e7a99d`,
> `9248505f`, `3db5a589`, `4b088965`, `1962ae89`). Plan 5 Item A: `32913e28`, `3fc46276`, `33447c3a`,
> `5c841a3e` (dashboard tests, 15 green). Plan 5 Item B: `2500eec1` (deleted the redundant
> `enum-guard-pass.md`; the two `.log` files were **kept on disk by user decision** — they are
> gitignored, so keeping them costs nothing and deleting them is unrecoverable). Plan 5 Item C:
> **decided — leave the 14 BOM files.**
>
> **Progress since the 2026-09-22 re-verification:** Module 0 gained **0.16 — Backup, Recovery & Data
> Lifecycle** and then **0.17 — Monitoring, Logging & Observability** (migration `core.0015`, four models,
> `LIVE_LINKS["0.17"]`), so the remaining Module 0 work is **4 sub-modules (0.18–0.21), not 6**. 0.17 landed
> without a docs close-out, so this file, `plan-remaining-1`, `README.md`, `NavERP.md`, `core/SKILL.md` and
> `todo.md` all undercounted it; corrected in one sweep.

| # | Plan | Item | Size | Recommended order |
|---|------|------|------|-------------------|
| 1 | [`plan-remaining-1-module0-submodules.md`](plan-remaining-1-module0-submodules.md) | Module 0: **4 unbuilt sub-modules (0.18–0.21)** + `SKILL.md` (**now written**) | **Large** — 4 full build runs | 4th (biggest, do it when you have a long stretch) |
| 2 | [`plan-remaining-2-land-fixed-defects.md`](plan-remaining-2-land-fixed-defects.md) | 3 defect fixes sitting uncommitted in the tree | Small | ✅ done |
| 3 | [`plan-remaining-3-readme-module6-row.md`](plan-remaining-3-readme-module6-row.md) | `README.md:1199` — Module 6's row lost its leading cells | Tiny | ✅ done |
| 4 | [`plan-remaining-4-docs-closeout-sweep.md`](plan-remaining-4-docs-closeout-sweep.md) | Stale status claims **+ 7.15's skipped Phase-7 close-out** | Medium | ✅ done |
| 5 | [`plan-remaining-5-housekeeping.md`](plan-remaining-5-housekeeping.md) | `apps/dashboard/` has 0 tests; 3 stray artifacts; 14 BOM files | Small | ✅ done |

## Suggested sequence

**2 → 3 → 4 → 1 → 5** — **all of 2, 3, 4 and 5 are done**; the only work left in the whole
`plan-remaining-*` set is **Plan 1 (Module 0, 0.17–0.21)**.

Plan 2 first because a dirty tree blocks the "claim the tree" step of every build run (L45), and Plan 1
is a series of build runs. Plan 3 and Plan 4 both edit the README roadmap table — do them in the same
sitting, as separate commits.

## The headline finding

**Modules 1–6 and 7.1–7.13 are structurally complete.** All six integrity checks pass: every migration
applied, all 3,350 route names reverse, all 1,995 template references exist on disk, all 581 sidebar
targets resolve, and every model is referenced by its seeder (except three that legitimately are not —
`core.AuditLog`, `crm.HealthScore`, `procurement.WidgetPreference`).

**The only material gap in the range was Module 0 — 7 of 21 sub-modules built at authoring. It is now
17 of 21 (0.1–0.17); the remaining 4 are 0.18–0.21.** Everything else in these five plans was defects,
stale documentation, or housekeeping — and **all five plans have now landed.**

**Integrity audit re-run 2026-09-26 — all six checks PASS** at the current HEAD: every migration
applied, **3,748** route names reverse, **2,275** template references exist on disk, **730** distinct
sidebar targets resolve, and **0 models unseeded and unexplained** in every app (each exception is
documented in the audit output — e.g. `SettingValue` and `BusinessRuleLog` are deliberately absent
because absence *is* their designed starting state). Check 1 reports
`module 0: 4 catalogued but NOT built -> 0.18, 0.19, 0.20, 0.21`; check 6 reports
`core: 17 live sub-modules`.

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
- A concurrent session is **in Module 8 (Sales)** in `apps/sales/` and `templates/sales/` — it was
  mid-build on 8.2 when this index was written, and 8.1–8.5 are now live, so it has moved on again.
  Re-read shared files before editing; never commit another session's in-flight `test-contract-*.md`
  or its modified templates. **Agree the migration number before generating one (L43).**
- `.claude/tasks/todo.md` is **clean** in the tree right now, so the stale `core is now 15 of 21` line
  at `todo.md:9313` has been corrected along with a 0.17 close-out note. If another session has that
  file dirty again, leave it to the owner (L43/L45).
