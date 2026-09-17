# Research — Sub-module 7.12: Portfolio & Program Management (Module 7 — `projects`)

Researched 2026-09-16 against the leading PPM products: Planview (Strategic Portfolio
Management), Planisware Orchestra, Primavera P6 EPPM, Microsoft PWA portfolio analysis
(business drivers + pairwise driver weighting + project ratings), Microsoft Project
Accelerator (Program table), Sciforma, PPM Express and AlignX (intake -> appraisal ->
prioritisation -> commitment -> governance -> delivery -> benefit).

## The five NavERP.md bullets, mapped

1. **Portfolio Dashboard & Heat Maps** — multi-project health indicators, bubble charts,
   investment balance. -> a real `Portfolio` container [PRT-] + a COMPUTED dashboard page
   (health = derived from project status/CPI/risk/quality, never stored; the 7.4 EVM ruling).
2. **Program Dependency Mapping** — cross-project dependencies, shared resources, milestone
   alignment. -> a real `Program` [PGM-] container + `ProgramDependency` [PDEP-] register
   (cross-project edges BETWEEN `projects.Project` rows, distinct from 7.2's intra-project
   `TaskDependency`) + a computed milestone-alignment lens.
3. **Strategic Alignment & Scoring** — OKR linkage, weighted scoring models, prioritisation.
   -> `PortfolioInvestment` [PIN-]: the portfolio -> project membership row carrying the
   four-criterion weighted score (strategic fit / financial return / delivery risk /
   capacity fit — the Completix/AlignX four) with derived weighted_total and computed rank.
4. **Capacity & Pipeline Planning** — resource pool across programs, demand funnel, intake
   governance. -> COMPUTED pipeline board over 7.1's `ProjectRequest` (the intake spine
   already exists) + 7.3's `ResourceAllocation` capacity, grouped by program.
5. **Portfolio Reporting & Governance** — executive summaries, steering committee packs,
   investment reviews. -> COMPUTED executive-summary section on the portfolio dashboard
   (investment mix, health distribution, scoring spread); no snapshot table (goes stale).

## Recommended scope (4 new models + 2 computed pages)

- `Portfolio` [PRT-] — the investment envelope: status, owner, budget envelope,
  strategic theme. ONE per tenant per theme.
- `Program` [PGM-] — the delivery container: portfolio FK, manager, objectives,
  status, window. A program groups projects; a portfolio groups programs + ungrouped
  investments.
- `PortfolioInvestment` [PIN-] — membership + scoring row: (portfolio, project) unique,
  program FK nullable, the four criterion scores 0-100 + four weights, derived
  weighted_total, computed rank lens, status incl. the fund/reject verbs.
- `ProgramDependency` [PDEP-] — the cross-project edge: predecessor/successor
  `projects.Project` FKs, dependency kind, criticality, owner, status (open/cleared),
  clear/reopen verbs.
- `pfm_dashboard` (computed) — the heat map + health bands + investment balance +
  executive summary + the pipeline funnel (bullet 4) over 7.1 requests.

## Rulings

1. **No health column on Portfolio/Program/Investment.** Health is derived from the
   member projects' statuses (the 7.4/7.5/7.6 boards ruling); a stored health goes stale
   the instant a project moves.
2. **No second dependency table for intra-project links.** 7.2's `TaskDependency` owns
   task edges INSIDE one project; `ProgramDependency` owns edges BETWEEN projects. The
   two are documented as disjoint by node type.
3. **No scoring recompute engine.** weighted_total = sum(criterion x weight) is a derived
   property read on render; rank is a computed lens on the register (?rank=1), not a column
   that goes stale when weights change (the 7.5 simulation ruling).
4. **Steering-committee packs are a computed page, not a table.** A stored snapshot goes
   stale; 7.16 Reporting owns persisted report snapshots if a later pass wants one.
5. **Money columns stay read-only lenses.** The budget envelope is the portfolio's own
   planning figure (a PMO input); committed/actual spend is READ from 7.4's
   `BudgetRevision`/`ProjectExpense` aggregates — 7.12 posts no JE (L29).
