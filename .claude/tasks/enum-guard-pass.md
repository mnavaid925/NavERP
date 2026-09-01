# App-wide pass — an unrecognised enum GET param must be IGNORED, not applied

Raised by the 6.14 review wave and confirmed by survey. Carried out as ONE central change rather
than ~360 per-view edits.

## The defect

`apps.core.crud.crud_list` takes `filters=[(get_param, orm_lookup, is_int), …]` and guards the two
**parseable** failure modes:

* `is_int=True` → `as_db_int()` refuses a non-decimal or over-range value (L11).
* a `BooleanField` → `.filter(is_active="abc")` raises `ValidationError` inside `.filter()` and the
  loop skips it.

But an unrecognised **CHOICES** value is a plain string. `.filter(status="nope")` neither raises nor
narrows — it matches zero rows and **silently empties the register** for a value anyone can type into
the address bar. Stale bookmarks, hand-edited URLs and renamed choice values all land here.

## Why "ignore" is the right contract (not a judgement call)

SCM's own security suite already asserts exactly this, and says so in the test names:

* `apps/scm/tests/test_security.py:4609` — `test_every_junk_choice_filter_at_once_is_skipped_rather_than_matched`
* `apps/scm/tests/test_security.py:4614` — `test_a_junk_status_falls_back_to_the_default_view_not_to_an_empty_page`,
  which asserts `list(resp.context["object_list"]) == [alert_a]` — the row **survives**.

So the contract was already decided in the module that thought hardest about it; it was just
implemented per-view and never centralized. CLAUDE.md's Filter Implementation Rules say the same.
This pass makes the intended behaviour the default everywhere instead of a thing each view
remembers to do.

## The fix — central, not 360 edits

One guard inside `crud_list`'s non-int branch: resolve the lookup against `qs.model`, and if it is a
plain single-hop field **with choices**, skip the filter when the value is not one of them.

Deliberately narrow so it cannot change unrelated behaviour:

* `"__" in lookup` → **skipped** (a relation hop or a lookup suffix like `__in` / `__icontains` is
  out of scope; behave exactly as before).
* field not found on the model → skipped.
* field has no `choices` → skipped (this is what leaves every `BooleanField` and free-text filter
  untouched).
* choice values that are not all strings → skipped (an int-valued enum belongs on the `is_int`
  path, and `.filter()` already raises there).

A **valid** choice still filters exactly as it always did. The guard only ever suppresses a value
that could not have matched anything anyway.

## Blast radius

`filters=` appears at 361 call sites across 8 apps (hrm 120, scm 73, crm 46, inventory 38,
procurement 37, accounting 29, core 10, tenants 4). All are fixed by the single change.

Only **8** junk-enum tests exist app-wide, in 4 files. Of those, exactly **two encode the bug** and
must be corrected to assert the row survives:

* `apps/procurement/tests/test_receipt_views.py:649` — `..._discrepancy_list_junk_enum_params_never_500`, asserts `== []`
* `apps/procurement/tests/test_receipt_views.py:1156` — `..._rtv_list_junk_enum_params_never_500`, asserts `== []`

The rest assert only `status_code == 200` (tolerant of either behaviour) or already assert the
correct contract (scm).

## Already fixed per-view in 6.14 (kept, now belt-and-braces)

`spendrule_list` (bf82c4a1) and `maverickfinding_list` (7c532c37) withhold the filter spec
themselves. Once the central guard lands these are redundant but harmless, and they are proven and
tested — left in place deliberately rather than churned out late. A future cleanup may remove them
in one deliberate commit.

## Verification required

Not just the changed apps — the guard is in shared code, so the **whole** project suite must be run
unfiltered (L47). A `-k` filter would exclude exactly the tests a shared-file change can break.
