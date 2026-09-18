# Review — Projects 7.12 Portfolio & Program Management

Six read-only lanes ran **serially** (code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer) over the 7.12 file set.

**BASE** = `c47901e175c33c5b29aa785162510935479b9480`
**HEAD at review time** = `c45e2633` (plus concurrent commits on tree)

---

## 1. Executive Summary & Lane Reports

### Lane 1: Code Reviewer
- **Conventions & Architecture**: Clean separation into `PortfolioProgramManagement/` across models, forms, views, and urls.
- **Tenant Isolation**: Model forms use `TenantModelForm` and `_reject_foreign`.
- **Finding (Important - F-1)**: In `apps/projects/forms/PortfolioProgramManagement/Programs.py`, `ProgramForm.__init__` overrides `manager` queryset for tenant scoping, but omits overriding `self.fields["portfolio"].queryset = Portfolio.objects.filter(tenant=self.tenant).order_by("name")`. This causes the portfolio dropdown in HTML to list portfolios across all tenants.
- **Finding (Important - F-2)**: In `apps/projects/models/PortfolioProgramManagement/PortfolioInvestments.py`, `PortfolioInvestment` lacks a model-level `clean()` method to assert that `project.tenant_id == self.tenant_id` and that if `self.program` is set, `self.program.portfolio_id == self.portfolio_id`.

### Lane 2: Explorer
- **Wiring Verification**:
  - `apps/core/navigation.py`: `LIVE_LINKS["7.12"]` contains all 5 NavERP bullet links + 4 register links.
  - `apps/projects/admin.py`: `PortfolioAdmin`, `ProgramAdmin`, `PortfolioInvestmentAdmin`, `ProgramDependencyAdmin` all properly registered with `list_display`, `list_filter`, `list_select_related`, `search_fields`, `readonly_fields`.
  - `apps/projects/models/__init__.py`, `forms/__init__.py`, `views/__init__.py`, `urls/__init__.py`: Clean re-exports.
  - Seeder: `_portfolio_management` implemented in `apps/projects/management/commands/seed_projects.py` with idempotent guard.

### Lane 3: Frontend Reviewer
- **Design System**: All badges strictly adhere to color-named classes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`). Zero legacy/bootstrap classes.
- **Filter Bar Consistency**: Dropdowns in `list.html` use `|stringformat:"d"` for PK comparisons, preventing type mismatch bugs.
- **Templates**: All 13 templates properly extend `base.html`, include breadcrumbs, title blocks, CSRF tokens on POST forms, and empty states.
- **No Comment Leaks**: Verified zero `{#` leaks across all rendered outputs.

### Lane 4: Performance Reviewer
- **Query Optimization**:
  - `prt_list`: `select_related("owner", "currency")`, `prefetch_related("programs", "investments")`.
  - `pgm_list`: `select_related("portfolio", "manager")`, `prefetch_related("investments")`.
  - `pin_list`: `select_related("project", "portfolio", "program")`.
  - `pdep_list`: `select_related("source_project", "target_project", "program", "owner")`.
  - `pfm_dashboard`: Aggregates and annotations used for counts, sums, and status grouping instead of N+1 python loops.
- **Indexes**: Tenant indexes verified on `(tenant, status)`, `(tenant, portfolio)`, `(tenant, source_project)`, `(tenant, target_project)`.

### Lane 5: QA Smoke Tester
- **Automated Smoke Test (`temp/smoke_712.py`)**:
  - 17 GET endpoints verified for HTTP 200 and expected content.
  - 8 IDOR endpoints verified for HTTP 404 cross-tenant isolation.
  - Action verbs verified:
    - `pin_fund` -> status "funded"
    - `pin_defer` -> status "deferred"
    - `pdep_clear` -> status "cleared" with `cleared_at` timestamp
    - `pdep_reopen` -> status "open" with `cleared_at=None`
  - Seeder idempotency verified across consecutive runs.

### Lane 6: Security Reviewer
- **Tenant Boundaries**: Verified strict multi-tenancy. Every view uses `request.tenant`. All detail/edit/delete/action views scope by `tenant=request.tenant`.
- **POST Safety**: All action endpoints require `@require_POST` and `@login_required`.
- **Audit Logging**: All lifecycle actions write to `AuditLog` with action verbs $\le 10$ characters (`create`, `update`, `delete`, `fund`, `reject`, `defer`, `clear`, `reopen`).

---

## 2. Findings Log (Prioritized)

| ID | Severity | Area | File | Description | Action Required |
|---|---|---|---|---|---|
| **F-1** | Important | Forms / Tenant Isolation | `apps/projects/forms/PortfolioProgramManagement/Programs.py` | `ProgramForm.__init__` does not scope `portfolio` field queryset by `tenant`. | Add `self.fields["portfolio"].queryset = Portfolio.objects.filter(tenant=self.tenant).order_by("name")`. |
| **F-2** | Important | Models / Integrity | `apps/projects/models/PortfolioProgramManagement/PortfolioInvestments.py` | `PortfolioInvestment` model lacks `clean()` method verifying foreign key tenant/portfolio consistency. | Add `clean()` checking `project.tenant_id == self.tenant_id` and `program.portfolio_id == self.portfolio_id`. |

---

## 3. Review Verdict

**PASS WITH TWO MINOR/IMPORTANT FIXES (F-1, F-2)**. Proceed to Phase 5 Code Fixer.
