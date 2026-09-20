# Review — Projects 7.16 Reporting & Business Intelligence

> Phase 4 will run the six reviewers **serially** against `BASE...HEAD` (the sha is re-derived at the
> start of Phase 4, per Phase 0) and append each one's findings here, then dedupe and assign the final
> `C`/`I`/`M` IDs.
>
> **Section 0 is different**: these are observations made while Phase 3 was still building, written down
> immediately so they reach Phase 4 as evidence rather than as a half-remembered note. They are *not*
> reviewer findings and carry no ID yet.

---

## 0. Carry-forward from the Phase 3 build

### BF-1 — Every write verb in 7.16 is gated by **visibility**, not by ownership or role. A member can rename, un-publish and delete a tenant admin's shared board.

**Where.** `apps/projects/views/ReportingBusinessIntelligence/ProjectDashboards.py` — `pdb_edit`,
`pdb_delete`; the twin in `ProjectReports.py:237-246` — `rep_edit`, `rep_delete`; and the four tile verbs
in `DashboardWidgets.py` (B2.5, now built). Each guard-fetch is
`analytics.visible_dashboards(request)` /
`visible_reports(request)` (`apps/projects/analytics.py:209-224`), i.e. *"can this caller see the row?"*
`can_edit` is computed at `ProjectDashboards.py:315` and passed as context — it selects which buttons the
template draws and is consulted by no view.

**Why the build did it that way.** R7 and B2.4 pin that exact fetch, and B2.4's `can_edit` row is written
as an affordance rule ("Edit/Delete/tile-management affordances"). So this is **not a deviation from the
contract** — it is a gap the contract has, reproduced faithfully. That is why it is here instead of in a
commit message.

**Measured, not argued** (`temp/rbi_authz_probe.py`, `temp/rbi_unshare_probe.py`; `ops_acme`, a
non-admin member, against rows owned by `admin_acme`. Every row and audit entry the probes wrote was
deleted by primary key afterwards; all four 7.16 tables are back to 0 rows):

```
1 member GET pdb_detail of shared, admin-owned            -> 200 | is_owner=False can_edit=False
1 member GET pdb_detail of tenant template (owner=None)   -> 200 | is_owner=False can_edit=False
1 member GET pdb_detail of private, admin-owned           -> 404
2 member POST pdb_edit on an admin's SHARED board -> 302; name now 'AUTHZPROBE renamed by a member';
  layout 'three'; owner still 2
2 member POST pdb_delete on an admin's shared board  -> 302; row gone: True
2 member POST pdb_delete on a tenant template        -> 302; row gone: True
3 member POST rep_delete on an admin's shared question -> 302; row gone: True
member POST pdb_edit on a SHARED tenant template, is_shared omitted -> 302 | is_shared now False
20 BF-1 on tiles: ops_acme (a plain member) REORDERED, RENAMED, ADDED and DELETED tiles on
   admin_acme's SHARED board — all four 302. The gate is visibility, and can_edit is only a button
   rule (ProjectDashboards.py:315). Phase 4/5 owns the fix, not this slice.
```

The tile line is verbatim from `temp/rbi_wdg_probe.py` step 20; the board/report lines above it are from
the two earlier probes.

The `is_shared` line is the quiet one: an **unticked checkbox** is all it takes, so a member's ordinary
"save my layout" POST silently un-publishes a row the whole workspace resolves as its home template.
The delete of a `owner=None` template removes the board that `analytics.home_dashboard()` hands to
every user who never made one. `rep_delete` takes a shared question **and its frozen runs** with it
(CASCADE, A1.6).

**The reference app already closed this half of it, and says so.** `apps/crm/views/AnalyticsReporting/Dashboards.py:24-27`:

```python
def _can_share_dashboards(user):
    # Publishing (is_shared) / defaulting (is_default) a dashboard is a tenant-wide setting,
    # so it is restricted to tenant admins (or superuser) — security-review finding.
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))
```

crm threads the answer into the **form** (`can_share=` at lines 37 and 73), so the decision is enforced
where the field is bound rather than where the button is drawn. Note the delete route is *not* covered
there — `crm`'s own `dashboard_delete` (line 87) has no guard beyond `crud_delete`'s tenant filter, so
the destructive half is inherited from the reference app and remains wrong in both.

**What Phase 4 should decide, and Phase 5 implement.** The defensible reading is that a shared board is
a team board, so colleagues *editing its definition* may be intended — but three things still need a role
gate under that reading, and they are separable:

1. `is_shared` — publishing and un-publishing is a workspace-wide act. Mirror crm: a `can_share=` /
   `can_manage=` kwarg on `ProjectDashboardForm` and `ProjectReportForm`, ignoring the posted value when
   the caller lacks the role.
2. `owner` — already create-only on dashboards (D59) and absent from both form field lists; keep asserting it.
3. **Delete** — of a row somebody else authored, especially a tenant template and especially one that
   cascades frozen runs. A view-side check before the helper, answering **403** for a row the caller may
   see but not remove. (404 stays correct for the invisible case; a 403 here discloses nothing the 200
   detail page has not already disclosed.)

Whatever is chosen, the tile verbs in B2.5 must inherit the same rule rather than invent one — a member
who cannot delete a board can currently still add, move and delete the tiles inside it, which is the same
"shared" word doing two different jobs.

**Severity: propose Important, possibly Critical.** Left unfixed it is a same-tenant integrity problem
with a trace (`write_audit_log` does record the `update`/`delete`, so it is unauthorised rather than
invisible) and no cross-tenant leak — every one of these routes is a proven 404 across tenants.

### BF-2 — `redirect_back_or` turned a hand-typed junk `next` into a **500 on a verb whose write had already committed**. Found while building the tile verbs; fixed in Phase 3, so it is here to be confirmed, not to be re-fixed.

**Where.** `apps/projects/views/_helpers.py` — `redirect_back_or`, used by all 11 POST-only verbs (R10).

**What the probe caught** (`temp/rbi_wdg_probe.py` step 14): `url_has_allowed_host_and_scheme` answers
`True` for *any* relative reference, so `next=not a url at all` passed the gate and reached
`redirect()`, which tries such a string as a **view name** and re-raises `NoReverseMatch` when it contains
neither `/` nor `.` (`django/shortcuts.py:177-186`). The tile had already moved by then: the data write was
committed and the operator got an error page instead of the board.

**The fix taken, and the one refused.** A `looks_like_target(candidate)` gate now sits in front of the
pinned helper and sends anything that is not an absolute same-host URL or a root-relative path to the
fallback. `HttpResponseRedirect(candidate)` was the alternative — it drops the view-name lookup but turns
junk into a *silent* redirect to the wrong page (`Location: home` resolves against the current directory,
so `…/widgets/7/move/` would land on `…/widgets/home`). Contract **D63** carries the reasoning.

**What Phase 4 should check.** That this is a robustness fix and not an openness fix: `//evil.example`,
`http://evil.example/…`, `javascript:` and a control-char-prefixed host were refused before and are
re-asserted as still refused (probe step 14 covers all six shapes on a real verb). And that no other 7.16
slice regressed — all four probes (`rbi_reports`, `rbi_runs`, `rbi_dashboards`, `rbi_wdg`) were re-run green
after the change, since every one of them posts a `next`.

---

## 1. Reviewer findings

_Appended in Phase 4, one section per reviewer, in the order
`code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
`security-reviewer`._
