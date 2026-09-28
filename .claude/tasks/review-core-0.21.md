# Review — sub-module 0.21 "Compliance, Governance & Risk" (`core`)

> **Base:** `5ab1c305` · **Scope:** the 35 commits in `5ab1c305..HEAD` whose subject contains `0.21`
> (36 files). 0.20 commits from a concurrent session interleave in that range and are **out of scope**.
> **Contract:** `.claude/tasks/contract-core-0.21.md` (`7d96c406`).
> **Findings are hand-verified by the main session** — each was reproduced against the real files or the
> real seeded database before being written down. Reviewer claims that did not reproduce are recorded as
> retracted, not silently dropped.

## Pass 1 — `code-reviewer`

**Verified clean (checked, not assumed):**

- `makemigrations core --check --dry-run` → **"No changes detected"**; migration `0018` provably matches
  the six models and depends on the correct leaf `0017`.
- All 6 models' fields, `max_length`s, CHOICES, `related_name`s, `Meta.ordering`, `unique_together` and
  all 12 index names (≤ 30 chars) match contract §1 exactly.
- All 28 views + 2 actions filter on `tenant=request.tenant`; **no `.all()` anywhere** — no tenant leak.
- URL ordering correct: literal `compliance/` board → `crud()` groups → child literals → the 2 actions.
  No `<int:pk>` route can shadow a later literal.
- Seeder idempotency: per-entity `if not …exists()` guards, `get_or_create` on the real unique keys.
  **Proven**: re-running `seed_core` creates nothing, and rows-per-`(tenant, code)` is exactly 1 in both
  tenants (3 codes × 2 tenants = 6 rows) — not a duplicate bug.
- Seed honesty: all 3 seeded `ControlFramework` rows carry `adopted_on=None` with notes disclaiming
  certification. No row asserts compliance.
- Context-key audit, run mechanically against contract §3: **every pinned `extra_context` key is present**
  in the corresponding view. Reverse audit (template vars absent from any view) surfaced only loop
  variables, `{% for %}` choice pairs and `q` — which `crud.py:181` supplies. **No L7/L8 drift.**
- `available_controls` branching in `controlframeworkmapping/form.html` verified correct: an undefined key
  falls to the generic branch, an empty queryset to the picker.

### C1 — Critical: the seeder never computes `inherent_score`, so every seeded risk displays `0`

**`apps/core/management/commands/seed_core.py:1596-1628`**

`RiskRegister.inherent_score` is written in exactly one place — `clean()` (model line 647). `Model.save()`
does **not** call `full_clean()`, there is no `post_save` signal in `core`, and the seeder uses
`objects.create(...)`. So `clean()` never runs and all three seeded risks keep the field default `0`.

**Reproduced against the seeded database:**

```
GRC-00001 code=RSK-01 L=possible  I=major    -> inherent_score=0  band=low
GRC-00002 code=RSK-02 L=unlikely I=moderate -> inherent_score=0  band=low
GRC-00003 code=RSK-03 L=likely   I=severe   -> inherent_score=0  band=low
constructed, NOT saved: inherent_score = 0
after explicit clean():  inherent_score = 20  band = critical
does save() call full_clean? -> False
```

Consequences on a freshly seeded demo DB: `riskregister/list.html` shows `0`/"Low" for all three rows,
`Meta.ordering = ["-inherent_score", "code"]` sorts three identical zeros (inert), and the board's
`critical_risks` computes 0. The seeder's own stdout claims "all three score bands" and its comment asserts
the model recomputes the field — both false. This is the one defect that makes a shipped page state
something untrue on a register whose whole purpose is that the number is true.

Intended spread: RSK-01 3×4=12 (high), RSK-02 2×3=6 (medium), RSK-03 4×5=20 (critical).

**Fix** — call `clean()` before `save()` (not `full_clean()`: `tenant`/`number` are not valid at
construction, and this matches how the model tests exercise the guards).

```python
risk = RiskRegister(
    tenant=tenant, code=code, title=title, risk_statement=statement,
    category=category, likelihood=likelihood, impact=impact,
    treatment=treatment, treatment_plan=plan, status=status, owner=admin_user,
    reviewed_on=today - 30 * day, next_review_on=today + 335 * day,
    notes="Seeded as an EXAMPLE risk. `inherent_score` is computed by the model from "
          "likelihood x impact; this seeder never asserts a number of its own.",
)
risk.clean()      # recomputes inherent_score from the two ordinal scales
risk.save()
```

### I1 — Important: `unacknowledged_count` counts acknowledgements, the opposite of its name

**`apps/core/views/Compliance.py:266-268`**

```python
"unacknowledged_count": PolicyAcknowledgement.objects.filter(
    tenant=request.tenant, policy__status="published",
    policy__requires_acknowledgement=True).count(),
```

This counts **acknowledgement rows that exist**. An unacknowledged person has no row, so they are
invisible to this query — the count rises as people comply. The name, the contract key and
`corporatepolicy/list.html:23` ("N acknowledgements recorded against published policies") describe three
different quantities. Note the template's *prose* is actually the honest one; the key name is the liar.

**Fix** — rename the key to what is counted, `acknowledgement_count`, in the view, the template and the
contract row. Computing "who has not acknowledged" needs the eligible-user population, which is
`_acknowledgeable_users(tenant)` minus distinct acknowledged users; that is a different, larger change and
is **not** taken here.
### I2 — Important: the back-fill form silently discards the note the user typed

**`apps/core/views/Compliance.py:389-410` (`policyacknowledgement_create`)**

`PolicyAcknowledgementForm` has exactly one field, `notes` (`forms/Compliance.py:106`). The form is bound
and validated, then the row is written by:

```python
acknowledgement, created = PolicyAcknowledgement.objects.get_or_create(
    tenant=request.tenant, policy=policy, user=person,
    policy_version=policy.version,
)
```

`form.cleaned_data["notes"]` is never passed. The optional note is accepted, echoed back in the form, and
thrown away — silent data loss with no error and no warning. This is the back-fill path whose entire
purpose is to capture evidence about somebody who was not at a keyboard, so the note is the payload.

**Fix** — pass it through as `defaults={"notes": form.cleaned_data.get("notes") or ""}`. Using `defaults=`
keeps `get_or_create` idempotent on a double submit (an existing row is not mutated) and avoids a
`TypeError` on the "already acknowledged" branch.

### M1 — Minor: `corporatepolicy_list` runs a second COUNT over a queryset it is about to paginate

**`apps/core/views/Compliance.py:265`** — `qs.filter(status="published").count()` is one avoidable query
per list render. Correct, and the other 0.21 lists take the same shape, so this is a note for a future
pass rather than a defect to fix now.

### M2 — Minor: the contract table lists a `controlframeworkmapping_edit` view that does not exist

**`.claude/tasks/contract-core-0.21.md` §3** — there is no such `def` in `apps/core/views/Compliance.py`,
and `controlframeworkmapping/form.html` is create-only. This is **intentional and correct** (a mapping is
a pure join row with nothing to edit; its list page is delete-only for the same reason), but the contract
should not carry a row for a view that does not exist. The contract is corrected; no view is invented.

## Retracted claims

Recorded so they are not re-raised, and so the next reviewer does not re-derive them as if they were new.

- **"The seeder creates duplicate risks."** Retracted — rows-per-`(tenant, code)` is exactly 1 in each of
  the two tenants (3 codes x 2 tenants = 6 rows). The apparent duplication was two tenants each holding
  their own `RSK-01`; numbering restarts per tenant by design.
- **"`inherent_score` is user-overridable through the form."** Retracted — the field is genuinely absent
  from `RiskRegisterForm.Meta.fields` and `clean()` overwrites whatever arrives, so a crafted
  `inherent_score=1` cannot land. The *model* is correct; only the *seeder* bypassed `clean()` (C1).
- **"Templates read context keys no view supplies."** Retracted — a mechanical audit of all 15 templates
  against all 30 view contexts found no drift. The apparent misses were `{% for %}` loop variables, the
  `(value, label)` pairs from `*_CHOICES` iteration, and `q`, which `crud.py:181` supplies to every list.

## Fix order for Phase 5

1. **C1** — seeded scores are `0` on every fresh demo DB. One file, ~6 lines, and it makes a shipped page
   state something false.
2. **I2** — silent loss of user-entered data.
3. **I1** — a key whose name says the opposite of its value; rename in three places (view, template,
   contract) or compute the real thing.
4. **M2** — contract row for a nonexistent view.
5. **M1** — deferred, no change.

