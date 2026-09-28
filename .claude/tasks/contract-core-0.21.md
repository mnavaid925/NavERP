# Contract — sub-module 0.21 Compliance, Governance & Risk (`core`)

**Frozen before the first line of 0.21 code.** Source: `.claude/tasks/research-core-0.21.md`
(committed `2929520f`). `BASE` for the Phase 4 review range: **`5ab1c305`**.

**Migration: `core.0018_*`.** The leaf was `0016` when this contract was drafted, but a concurrent
session committed **0.20's** `0017_changerequest_featurerollout_jobdefinition_jobrun_and_more.py`
(`8c8c40a1`) while it was being written. **Re-read `apps/core/migrations/` immediately before
running `makemigrations`; if the leaf is no longer `0017`, the new number is whatever follows it.**
Do not hand-write a migration number into a filename.

A name left unpinned here is a silently blank region (L7) or a `NoReverseMatch`. Where this
contract and the code disagree, **this contract was reviewed and the code is wrong** — fix the
code, or record a RULING here first.

---

## 0. Four facts that decide whether this build works

1. **There is no class named `ComplianceFramework`, and that is deliberate.** 0.8's
   `core.RegulatoryFramework` (`apps/core/models/Privacy.py:72`) already answers "which regimes is
   this workspace under" and already carries `dsar_window_days` and `data_residency_region`. 0.21's
   framework record is **`ControlFramework`** — certification programmes (SOC 2, ISO 27001,
   PCI-DSS), a different fact with a different lifecycle. The research doc's §3 records the
   rejected alternative. `RegulatoryFramework` is **not** touched by this pass.
2. **`RiskRegister` is `GRC-`, NOT `RSK-`.** `RSK` is already `projects.ProjectRisk`. Verified by
   enumerating every `NUMBER_PREFIX` in the repo. The inherited plan that said otherwise was
   wrong. See RULING 2 in §7.
3. **A register, not a runtime.** Nothing here enforces a control, grants an auditor access, pins
   data to a region, or reminds anyone to acknowledge a policy. NavERP is single-region Django with
   one database, no mail dispatcher and no worker. Success messages say **"recorded"**, never
   "enforced", "granted", "reminded", "verified". Each page prints `GRC_NOTES` verbatim.
4. **`core` is a foundation app (backend rule 9): entity files sit FLAT at the package root**, all
   four 0.21 classes live in one file `apps/core/models/Compliance.py`, and `apps/core/urls.py`
   stays a flat `crud(slug, name)` factory. No `<SubModule>/` folder, no `*_advanced.py`.

---

## 1. Models — 4 top-level entities, 6 classes, all tenant-scoped

Every model: `class X(models.Model)`, a
`tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="…", db_index=True)`,
a literal-minted `number` (`editable=False`, `max_length=20`) on the four numbered models, a
`Meta.ordering`, and a `(tenant, …)` index whose name is **under 30 characters** (MariaDB's hard
limit — `grc_tenant_score_idx` is 19, `cpol_tenant_type_idx` is 19, `cfmap_fw_cov_idx` is 15).

`core` has **no `TenantNumbered` base**, so the mint is the 0.20 `EntitlementFeature` pattern
verbatim:

```python
### 1.1 `ControlFramework` — `apps/core/models/Compliance.py` — `CFW-`

| Field | Definition |
|---|---|
| `number` | `CharField(max_length=20, editable=False)` — `CFW-` |
| `code` | `CharField(max_length=30)` — unique per tenant |
| `name` | `CharField(max_length=150)` |
| `framework_type` | `CharField(max_length=20, choices=FRAMEWORK_TYPE_CHOICES, default="attestation")` |
| `version` | `CharField(max_length=30, blank=True)` |
| `authority` | `CharField(max_length=150, blank=True)` — the issuing body ("AICPA", "ISO", "PCI SSC") |
| `description` | `TextField(blank=True)` |
| `is_active` | `BooleanField(default=True)` |
| `adopted_on` | `DateField(null=True, blank=True)` |
| `review_due_on` | `DateField(null=True, blank=True)` |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

`FRAMEWORK_TYPE_CHOICES` exactly, in this order: `attestation` ("Attestation / certification"),
`regulatory` ("Regulatory regime"), `industry` ("Industry standard"), `internal`
("Internal standard"). **`attestation` is the default** because it is the case that has no home
anywhere else in `core`; `regulatory` exists only so a workspace can *point at* 0.8's regime
without re-declaring it.

`Meta`: `ordering = ["code"]`; `unique_together = ("tenant", "code")`;
indexes `(tenant, is_active)` → `cfw_tenant_active_idx`, `(tenant, framework_type)` →
`cfw_tenant_type_idx`.

`__str__` → `f"{self.code} — {self.name}"`.

### 1.2 `ComplianceControl` — same file — `CTL-`

| Field | Definition |
|---|---|
| `number` | `CharField(max_length=20, editable=False)` — `CTL-` |
| `code` | `CharField(max_length=30)` — unique per tenant |
| `title` | `CharField(max_length=200)` |
| `description` | `TextField(blank=True)` |
| `category` | `CharField(max_length=40, blank=True)` |
| `status` | `CharField(max_length=16, choices=CONTROL_STATUS_CHOICES, default="not_started")` |
| `owner` | FK `settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"` |
| `frequency` | `CharField(max_length=20, blank=True)` — **recorded**; nothing schedules it |
| `evidence_reference` | `CharField(max_length=255, blank=True)` — a **pointer**; the file itself is 0.1's `core.Document` |
| `last_reviewed_on` | `DateField(null=True, blank=True)` |
| `next_review_on` | `DateField(null=True, blank=True)` |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

`CONTROL_STATUS_CHOICES` exactly, in this order: `not_started`, `in_progress`, `implemented`,
`effective`, `not_applicable`.

`Meta`: `ordering = ["code"]`; `unique_together = ("tenant", "code")`;
indexes `(tenant, status)` → `ctl_tenant_status_idx`, `(tenant, category)` → `ctl_tenant_cat_idx`.

`clean()` (raises `ValidationError` keyed on the offending field):
* `next_review_on` earlier than `last_reviewed_on` → `{"next_review_on": …}`.
* `status == "effective"` with no `last_reviewed_on` → `{"last_reviewed_on": …}`. A control cannot
  be declared effective without somebody having looked at it on a date.
* `status == "not_applicable"` requires a non-blank `notes` → `{"notes": …}`. "Not applicable" is
  the single most abused control state; an unexplained one is a gap, not a decision.

`@property is_overdue_review` → `bool(self.next_review_on and self.next_review_on < timezone.localdate())`.
Derived, never stored.

### 1.4 `CorporatePolicy` — same file — `CPOL-`

**Not** called `RetentionPolicy`: 0.8 owns that (`apps/core/models/Retention.py`) and it means
something else entirely. Also distinct from `hrm.HrPolicy` (3.x) — the docstring says so.

| Field | Definition |
|---|---|
| `number` | `CharField(max_length=20, editable=False)` — `CPOL-` |
| `code` | `CharField(max_length=30)` — unique per tenant |
| `title` | `CharField(max_length=200)` |
| `summary` | `TextField(blank=True)` |
| `policy_type` | `CharField(max_length=20, choices=POLICY_TYPE_CHOICES, default="security")` |
| `version` | `CharField(max_length=20, default="1.0")` |
| `status` | `CharField(max_length=12, choices=POLICY_STATUS_CHOICES, default="draft")` |
| `owner` | FK `settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"` |
| `effective_on` | `DateField(null=True, blank=True)` |
| `review_due_on` | `DateField(null=True, blank=True)` |
| `requires_acknowledgement` | `BooleanField(default=True)` |
| `body` | `TextField(blank=True)` |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` · `updated_at` `DateTimeField(auto_now=True)` |

`POLICY_TYPE_CHOICES` exactly: `security`, `acceptable_use`, `access_control`, `data_handling`,
`incident_response`, `business_continuity`, `code_of_conduct`.

`POLICY_STATUS_CHOICES` exactly: `draft`, `published`, `retired`.

**`status` IS on the form** (user-owned lifecycle, not workflow state) — contrast 0.20's
`ChangeRequest.status`, which is verb-driven and off the form. The verb-driven part here is
*acknowledgement*, which is its own child table, not a policy field.

`Meta`: `ordering = ["code"]`; `unique_together = ("tenant", "code")`;
indexes `(tenant, status)` → `cpol_tenant_status_idx`, `(tenant, policy_type)` → `cpol_tenant_type_idx`.

`clean()`:
* `status == "published"` requires `effective_on` → `{"effective_on": …}`. A published policy with
  no effective date has not been in force on any date at all.
* `review_due_on` earlier than `effective_on` → `{"review_due_on": …}`.
* `status == "retired"` with a `review_due_on` in the future → `{"review_due_on": …}` — a retired
  policy is not due a review.

`@property acknowledgement_rate` → `None` when `requires_acknowledgement` is False (so the template
renders an em dash, never a fake `100%`), else `acknowledged_count / expected_count` where
`expected_count` is the tenant's active user count. **The zero rule**: returns `None`, not `0`, when
`expected_count == 0`.


### 1.6 `RiskRegister` — same file — `GRC-` (**not** `RSK-`)

| Field | Definition |
|---|---|
| `number` | `CharField(max_length=20, editable=False)` — `GRC-` |
| `title` | `CharField(max_length=200)` |
| `risk_statement` | `TextField()` — the "if… then…" statement |
| `description` | `TextField(blank=True)` |
| `category` | `CharField(max_length=40, blank=True)` |
| `likelihood` | `CharField(max_length=14, choices=LIKELIHOOD_CHOICES, default="possible")` |
| `impact` | `CharField(max_length=12, choices=RISK_IMPACT_CHOICES, default="minor")` |
| `inherent_score` | `PositiveSmallIntegerField(default=0)` — **derived in `clean()`** |
| `residual_score` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `treatment` | `CharField(max_length=10, choices=TREATMENT_CHOICES, default="mitigate")` |
| `treatment_plan` | `TextField(blank=True)` |
| `status` | `CharField(max_length=12, choices=RISK_STATUS_CHOICES, default="identified")` |
| `owner` | FK `settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"` |
| `reviewed_on` | `DateField(null=True, blank=True)` |
| `next_review_on` | `DateField(null=True, blank=True)` |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

`LIKELIHOOD_CHOICES` exactly (Archer's five-point scale), valued 1–5 in this order:
`rare` (1), `unlikely` (2), `possible` (3), `likely` (4), `almost_certain` (5).

`RISK_IMPACT_CHOICES` exactly, valued 1–5: `negligible` (1), `minor` (2), `moderate` (3),
`major` (4), `severe` (5).

`TREATMENT_CHOICES` exactly: `accept`, `mitigate`, `transfer`, `avoid`.

`RISK_STATUS_CHOICES` exactly: `identified`, `assessing`, `treating`, `monitoring`, `closed`.

`inherent_score` is **stored, not a property**, because it is the column an auditor reads and the
list page sorts on; computing it in a property would filesort every render. It is **recomputed in
`clean()` from the two ordinals and never trusted from a POST** — it is off the form, and `clean()`
is the real gate, so a crafted `inherent_score=1` cannot land.

`clean()`:
* `self.inherent_score = LIKELIHOOD_VALUES[self.likelihood] * RISK_IMPACT_VALUES[self.impact]`,
  with both value dicts module-level and the keys the exact choice values. An unknown value (only
  reachable by bypassing the form) falls back to 1 rather than raising `KeyError` on a POST.
* `residual_score > inherent_score` → `{"residual_score": …}`. Treatment cannot make a risk worse;
  if it has, the *inherent* number is the one that is wrong.
* `status == "closed"` with no `reviewed_on` → `{"reviewed_on": …}`.
* `next_review_on` earlier than `reviewed_on` → `{"next_review_on": …}`.


---

## 2. Forms — `apps/core/forms/Compliance.py`, all `TenantModelForm` subclasses

`TenantModelForm.__init__` takes `tenant=` and scopes every `ModelChoiceField` whose model has a
`tenant` field, so **no form overrides `__init__` for FK scoping** and none may set `Meta.fields`
to include `tenant`.

| Form | `Meta.fields`, in this exact order | Excluded and why |
|---|---|---|
| `ControlFrameworkForm` | `["code", "name", "framework_type", "version", "authority", "description", "is_active", "adopted_on", "review_due_on", "notes"]` | `tenant` (view), `number` (`editable=False`, minted in `save()`) |
| `ComplianceControlForm` | `["code", "title", "description", "category", "status", "owner", "frequency", "evidence_reference", "last_reviewed_on", "next_review_on", "notes"]` | `tenant`, `number`. **`owner` IS on the form** — it is an ownership assignment, not evidence. |
| `ControlFrameworkMappingForm` | `["framework", "control", "clause_reference", "coverage", "notes"]` | `tenant` |
| `CorporatePolicyForm` | `["code", "title", "summary", "policy_type", "version", "status", "owner", "effective_on", "review_due_on", "requires_acknowledgement", "body", "notes"]` | `tenant`, `number` |
| `RiskRegisterForm` | `["code", "title", "risk_statement", "description", "category", "likelihood", "impact", "residual_score", "treatment", "treatment_plan", "status", "owner", "reviewed_on", "next_review_on", "notes"]` | `tenant`, `number`, **`inherent_score` — recomputed in `clean()`, so exposing it would let a POST forge the score** |
| `PolicyAcknowledgementForm` | `["notes"]` | `tenant`, `policy` (set by the view from the URL), `user` (**the actor — stamped by the view**), `policy_version` (snapshotted by the view), `acknowledged_at` (`auto_now_add`) |

`RiskRegisterForm` also re-exposes `code` — it is the human key, `unique_together` per tenant.

**No form carries a verb-driven field.** `PolicyAcknowledgementForm` is the sharpest case: a form
with only `notes` is a page that asks for a note and records who pressed save — which is exactly
what an acknowledgement is.

---
| `controlframeworkmapping_list` | `core/controlframeworkmapping/list.html` | `["framework__code", "control__code", "clause_reference"]` | `("coverage", "coverage", False)`, `("framework", "framework_id", True)` | `coverage_choices`, `frameworks`, `controls`, `notes` |
| `controlframeworkmapping_create` | `core/controlframeworkmapping/form.html` | — | — | `notes` |
| ~~`controlframeworkmapping_edit`~~ | — | — | — | **DELIBERATELY ABSENT (M2).** A mapping is a pure join row — framework, control, clause, coverage, note — with nothing to edit. Correcting one is remove-and-remap, so the list is delete-only and no `edit` view, route or `detail.html` exists. No view was invented to satisfy this row. |
| `controlframeworkmapping_delete` | → `core:controlframeworkmapping_list` | — | — | — |
| `policyacknowledgement_list` | `core/policyacknowledgement/list.html` | `["policy__code", "user__username"]` | `("policy", "policy_id", True)` | `policies`, `notes` |
| `policyacknowledgement_create` | `core/policyacknowledgement/form.html` | — | — | `notes` |
| `policyacknowledgement_delete` | → `core:policyacknowledgement_list` | — | — | — |
| `grc_overview` | `core/grcoverview.html` | — | — | computed posture + `notes` |

**`controlframeworkmapping` and `policyacknowledgement` have NO `_detail`** — both are child rows,
exactly as 0.20's `jobrun` is a child with a reduced route set. `controlframeworkmapping` also has
**no `_edit`** (a mapping's two FKs and its coverage are all it is; correcting one is delete +
recreate). Both get list + create + delete only, and their URL blocks are written out longhand
rather than via `crud()` so no `detail` route is generated. **This is the L7 trap: a template folder
that exists but has no `detail.html` is a blank region waiting for a link that reverses.**

### 3.1 The two extra actions

**`policy_acknowledge(request, pk)`** — name `policy_acknowledge`, route
`compliance/policies/<int:pk>/acknowledge/`. Creates a `PolicyAcknowledgement` with
`user=request.user` and `policy_version=policy.version` (the snapshot), via
`get_or_create(policy=…, user=…, policy_version=…)` so a second press is idempotent rather than an
`IntegrityError`. **No `PolicyAcknowledgementForm` is bound** — the form's only field is `notes` and
acknowledging a policy without a note is a legitimate act. Refuses a `draft` or `retired` policy
(`messages.error`, redirect, no row). Success message: **"Acknowledgement recorded."**

**`controlframeworkmapping_add(request, pk)`** — name `controlframeworkmapping_add`, route
`compliance/frameworks/<int:pk>/add-controls/`. A **GET form page** (not POST-only) that lists this
framework's existing controls and the controls not yet mapped, and POSTs `control_id` to add one
mapping with `coverage="not_started"`. This exists because bullet 1's central operation — mapping a
control into a framework — has no other honest entry point once `ComplianceControl` is a separate
entity. Refuses a `control_id` from another tenant (404) and a control already mapped (redirect +
`messages.info`, no duplicate row).

### 3.2 The context-var contract (pinned, L7)

* list → `object_list` + `page_obj` + `q` (from `crud_list`), **plus every `extra_context` key in
  the table above**.
* detail / edit object → `obj`.
* form → `form` + `is_edit`.
* `grc_overview` → `frameworks`, `controls`, `policies`, `risks`, `open_risks`, `critical_risks`,
  `published_policies`, `unacknowledged_policies`, `overdue_reviews`, `notes`.

`GRC_NOTES` (module-level, printed verbatim on every 0.21 page so a page and its board cannot
disagree) — four lines:

1. This is a register of declared intent, not a runtime. No page here enforces a control, grants an
   auditor access, pins data to a region, or reminds anyone to acknowledge a policy.
2. `implemented` / `effective` / `covered` are statements a person made. Nothing in NavERP checks

---

## 4. URLs — `apps/core/urls.py`, appended after the 0.20 block

`app_name = "core"` is unchanged. **Order is behaviour** (Django is first-match-wins): the literal
board segment first, then the `crud()` groups, then the longhand child-row blocks, then the
actions **after** the group that owns them.

```python
# ===================== 0.21 Compliance, Governance & Risk =====================
+ [
    path("compliance/", views.grc_overview, name="grc_overview"),
]
+ crud("compliance/frameworks", "controlframework")
+ crud("compliance/controls", "compliancecontrol")
+ crud("compliance/policies", "corporatepolicy")
+ crud("compliance/risks", "riskregister")
+ [
    # Child rows: list / create / delete only. `controlframeworkmapping` deliberately has NO
    # `edit` and NEITHER has a `detail` — a mapping and an acknowledgement are only ever read
    # through their parents, and generating routes (or templates) for them would be a blank
    # region waiting for a link that reverses (L7).
    path("compliance/mappings/", views.controlframeworkmapping_list, name="controlframeworkmapping_list"),
    path("compliance/mappings/add/", views.controlframeworkmapping_create, name="controlframeworkmapping_create"),
    path("compliance/mappings/<int:pk>/delete/", views.controlframeworkmapping_delete, name="controlframeworkmapping_delete"),
    path("compliance/acknowledgements/", views.policyacknowledgement_list, name="policyacknowledgement_list"),
    path("compliance/acknowledgements/add/", views.policyacknowledgement_create, name="policyacknowledgement_create"),
    path("compliance/acknowledgements/<int:pk>/delete/", views.policyacknowledgement_delete, name="policyacknowledgement_delete"),
]
+ [
    # Actions, declared AFTER the group that owns them so a greedy `<int:pk>` cannot shadow them.
    path("compliance/policies/<int:pk>/acknowledge/", views.policy_acknowledge, name="policy_acknowledge"),
    path("compliance/frameworks/<int:pk>/add-controls/", views.controlframeworkmapping_add, name="controlframeworkmapping_add"),

---

## 6. Seeder, numbering and navigation

### 6.1 `apps/core/settings_engine.py` — `LITERAL_PREFIX_MODELS`

Add four entries to the existing dict, after the 0.20 block:

```python
# 0.21 Compliance, Governance & Risk is the fourth such case. `ControlFramework`,
# `ComplianceControl`, `CorporatePolicy` and `RiskRegister` all mint their prefix in `save()`
# through a hardcoded literal, so the `NUMBER_PREFIX` scan above cannot see them, and each
# model's docstring says so and points HERE. `ControlFrameworkMapping` and
# `PolicyAcknowledgement` are deliberately absent: both are child rows with no number column.
"CFW": ["core.ControlFramework"],
"CTL": ["core.ComplianceControl"],
"CPOL": ["core.CorporatePolicy"],
"GRC": ["core.RiskRegister"],
```

### 6.2 `apps/core/management/commands/seed_core.py`

Add a `NumberingScheme` row per prefix via the existing `schemes` list, and one guarded
`if not <Model>.objects.filter(tenant=tenant).exists():` block creating a small, honest demo set:

* 3 `ControlFramework`: `SOC2` (attestation, AICPA), `ISO27001` (attestation, ISO), `GDPR`
  (**`regulatory`**, authority "EU") — the third exists precisely to show the 0.8 boundary.
* 4 `ComplianceControl`: `CTL-A.5.1`, `CTL-A.8.15`, `CTL-CC6.1`, `CTL-CC7.2` with mixed statuses so
  the status filter and the badge set are exercised.
* 5 `ControlFrameworkMapping` rows so the many-to-many is visible on the first render.
* 2 `CorporatePolicy` (`CPOL-ACC-001` security, `CPOL-ACC-002` acceptable use) — one `published`
  with an `effective_on`, one `draft`, so `clean()`'s publish rule is exercised by the demo.
* 2 `PolicyAcknowledgement` rows (tenant admin + a second user) against the published policy.
* 3 `RiskRegister` rows spanning `low`/`high`/`critical` so the score band and the sort are visible.

**The seeder must not claim certification.** No row may say a workspace "is SOC 2 compliant", and
the seeded frameworks carry `adopted_on=None`. This mirrors `regulatory_sync`'s own refusal ("a
workspace claiming HIPAA because a seeder said so would be a compliance lie").

Idempotent: `get_or_create` on the unique keys, and the `if not …exists():` guard per model. The
command must still print the tenant-admin login hint and the superuser-has-no-tenant warning.

### 6.3 `apps/core/navigation.py` — `LIVE_LINKS["0.21"]`

One entry, the board, matching the shape of the other sub-module entries:

```python
LIVE_LINKS["0.21"] = {
    "label": "Compliance, Governance & Risk",
    "items": {
        "Posture overview": "core:grc_overview",
        "Control frameworks": "core:controlframework_list",
        "Controls": "core:compliancecontrol_list",
        "Control mapping": "core:controlframeworkmapping_list",
        "Policies": "core:corporatepolicy_list",
        "Acknowledgements": "core:policyacknowledgement_list",
        "Risk register": "core:riskregister_list",
    },
}
```

Verify the exact surrounding structure of `LIVE_LINKS` before editing — 0.20's entry is the
template, and the docstring comment above each entry is part of the house style.

---

## 7. RULINGS recorded against the inherited plan

1. **`ComplianceFramework` is not the class name.** It is `ControlFramework`. Rationale and the
   rejected alternative: research §3. 0.8's `RegulatoryFramework` is untouched.
2. **`RSK-` → `GRC-`.** `RSK` is `projects.ProjectRisk`. Verified by enumerating every
   `NUMBER_PREFIX` repo-wide. Not negotiable: two `RSK-00001`s in one tenant are indistinguishable
   to an operator, which is the exact failure `prefix_usage()` exists to catch.
3. **8 models → 4 this pass.** Bullets 4 and 5 are deferred to a second 0.21 pass with their own
   contract (research §5.2). Reason: 0.20 was still landing in this checkout and the shared files
   are single-writer.
4. **Phase 1 ran inline, not via the `research` agent** (429 daily quota). The Phase 4 reviewers
   should weigh the reconciliation in research §3 as the load-bearing evidence, not the web search.

---

## 8. Testing contract (Phase 6)

Four modules, all prefixed `test_compliance_`; every helper `_<subslug>_`; `conftest.py` is owned
by the contract step alone.

* `test_compliance_models.py` — numbering mints `CFW-/CTL-/CPOL-/GRC-` and is sequential per tenant;
  `clean()` refusals (effective-without-review, next-review-before-last-review, not-applicable
  without notes, residual > inherent, closed-without-reviewed-on, the two `not_applicable` rules);
  `inherent_score` is recomputed and a crafted value cannot survive `clean()`; `score_label`
  bands; `RiskRegister.Meta.ordering`; every index name under 30 chars; `__str__` of all six.
* `test_compliance_forms.py` — for every form, the forbidden-field set is absent from
  `form.fields`; FK querysets are tenant-scoped; `RiskRegisterForm` has **no** `inherent_score` and
  a POST carrying it does not change the stored score; a foreign-tenant `framework`/`control`/
  `policy` pk does not bind.
* `test_compliance_views.py` — every route in §4 reverses; each list renders 200 and **asserts on
  content** (`admin_acme`), not just status; junk-param lists fall back rather than empty; page 2
  renders; `acknowledgement_rate` is `None` (not `0`) with no active users.
* `test_compliance_security.py` — a foreign tenant's pk is **404 on GET and on POST** for every
  entity; `policy_acknowledge` refuses a draft/retired policy and writes no row; a crafted
  `policy_version` on a POST cannot land; `controlframeworkmapping_add` refuses a foreign
  `control_id` and a duplicate; every delete is POST-only (`GET` → 405) and CSRF-enforced.

The final run must be the **full unfiltered** `apps/core` suite, green.

]
```

The whole `urlpatterns` is one parenthesised `crud(...) + [...] + ...` expression, so the 0.21
block continues that chain rather than starting a new statement.

---

## 5. Templates — 18 files, flat under `templates/core/`

`core` is a foundation app (rule 4): no sub-module level. Each entity folder holds the bare page
names; **never** a flat `entity_page.html`.

| Folder | Files |
|---|---|
| `templates/core/controlframework/` | `list.html`, `detail.html`, `form.html` |
| `templates/core/compliancecontrol/` | `list.html`, `detail.html`, `form.html` |
| `templates/core/corporatepolicy/` | `list.html`, `detail.html`, `form.html` |
| `templates/core/riskregister/` | `list.html`, `detail.html`, `form.html` |
| `templates/core/controlframeworkmapping/` | `list.html`, `form.html` — **no `detail.html`** |
| `templates/core/policyacknowledgement/` | `list.html`, `form.html` — **no `detail.html`** |
| `templates/core/` | `grcoverview.html` (standalone board, at the app root) |

Rules every template follows:

* `{% extends "base.html" %}`; shared partials from `templates/partials/` by root-relative path.
* The Actions column carries **View / Edit / Delete**; Delete is a POST form with
  `{% csrf_token %}` and `onclick="return confirm('…')"`.
* `{% if request.GET.status == value %}selected{% endif %}` for string filters; FK pk comparison
  uses `|stringformat:"d"`, never `|slugify`.
* Badge conditions use the **exact** choice values from §1, always with an `{% else %}`
  `{{ obj.get_status_display }}` fallback.
* Every list and detail page renders `{% for n in notes %}` so `GRC_NOTES` appears verbatim.
* `acknowledgement_rate` may be `None` — templates print an em dash for a missing rate, **never
  `0`** (the zero rule).

   them, and no control gates any action.
3. NavERP is a single-region Django application with one database. A residency row would record
   where data is *declared* to live, not where it is.
4. An acknowledgement row is a record that somebody pressed save. There is no mail dispatcher, so
   nobody is reminded.


## 3. Views — `apps/core/views/Compliance.py`

`from apps.core.views._common import *  # noqa: F401,F403` (gives `tenant_admin_required`,
`crud_list`, `crud_create`, `crud_edit`, `crud_detail`, `crud_delete`, `require_POST`).

**Every list view passes its own filter choices in `extra_context`** (Filter Implementation Rules).
A template filter dropdown whose options were never passed renders empty and silently drops the
filter.

> **RULE ADDED IN PHASE 5 (C2/I11) — an `annotate()` alias must NEVER equal a model `@property` name.**
> A `property` is a data descriptor, so Django's `ModelIterable` cannot `setattr` the annotation onto
> the instance and the query raises `AttributeError: can't set attribute '<name>'` the moment a row is
> actually instantiated. `compliancecontrol_list` and `corporatepolicy_list` both shipped that way and
> 500ed on any tenant holding rows (worse, the policy list returned a **masked** 200 with a false
> "No policies recorded" whenever a filter matched nothing). The aliases are now `mapping_total` and
> `acknowledgement_total`; the properties keep their names and are used only off a single object.
> A second rule from the same defect: **a `GROUP BY` suppresses `Meta.ordering` in Django**, so any
> annotated list must also carry an explicit `.order_by(...)` or `LIMIT/OFFSET` pagination is
> non-deterministic. Both list views now do.

| View | Template | `search_fields` | `filters` (param, lookup, is_int) | `extra_context` keys |
|---|---|---|---|---|
| `controlframework_list` | `core/controlframework/list.html` | `["code", "name", "authority", "description"]` | `("type", "framework_type", False)`, `("is_active", "is_active", False)` | `type_choices`, `framework_count`, `mapping_count`, `notes` |
| `controlframework_create` | `core/controlframework/form.html` | — | — | `notes` |
| `controlframework_detail` | `core/controlframework/detail.html` | — | — | `mappings`, `control_count`, `notes` |
| `controlframework_edit` | `core/controlframework/form.html` | — | — | `notes` |
| `controlframework_delete` | → `core:controlframework_list` | — | — | — |
| `compliancecontrol_list` | `core/compliancecontrol/list.html` | `["code", "title", "description", "category"]` | `("status", "status", False)` | `status_choices`, `effective_count`, `overdue_count`, `unmapped_count`, `notes` |
| `compliancecontrol_create` | `core/compliancecontrol/form.html` | — | — | `notes` |
| `compliancecontrol_detail` | `core/compliancecontrol/detail.html` | — | — | `mappings`, `framework_count`, `notes` |
| `compliancecontrol_edit` | `core/compliancecontrol/form.html` | — | — | `notes` |
| `compliancecontrol_delete` | → `core:compliancecontrol_list` | — | — | — |
| `corporatepolicy_list` | `core/corporatepolicy/list.html` | `["code", "title", "summary"]` | `("status", "status", False)`, `("policy_type", "policy_type", False)` | `status_choices`, `type_choices`, `published_count`, `acknowledgement_count`, `notes` |

> **Renamed during Phase 5 (I1).** This key was `unacknowledged_count`, which said the *opposite* of what
> it counts: an unacknowledged person has no row, so they are invisible to the query and the figure
> **rises as people comply**. It counts acknowledgement rows that exist, so it is now
> `acknowledgement_count`. The template's prose was always the honest one; only the key name lied.
| `corporatepolicy_create` | `core/corporatepolicy/form.html` | — | — | `notes` |
| `corporatepolicy_detail` | `core/corporatepolicy/detail.html` | — | — | `acknowledgements`, `acknowledgement_rate`, `notes` |
| `corporatepolicy_edit` | `core/corporatepolicy/form.html` | — | — | `notes` |
| `corporatepolicy_delete` | → `core:corporatepolicy_list` | — | — | — |
| `riskregister_list` | `core/riskregister/list.html` | `["code", "title", "risk_statement", "category"]` | `("status", "status", False)`, `("treatment", "treatment", False)`, `("likelihood", "likelihood", False)` | `status_choices`, `treatment_choices`, `likelihood_choices`, `critical_count`, `open_count`, `notes` |
| `riskregister_create` | `core/riskregister/form.html` | — | — | `notes` |
| `riskregister_detail` | `core/riskregister/detail.html` | — | — | `notes` |
| `riskregister_edit` | `core/riskregister/form.html` | — | — | `notes` |
| `riskregister_delete` | → `core:riskregister_list` | — | — | — |

`@property score_label` → `"low"` (≤4), `"medium"` (≤9), `"high"` (≤16), `"critical"` (else).
Derived, never stored, so it cannot drift from the number.

`Meta`: `ordering = ["-inherent_score", "code"]`; `unique_together = ("tenant", "code")`;
indexes `(tenant, status)` → `grc_tenant_status_idx`, `(tenant, "-inherent_score")` →
`grc_tenant_score_idx`, `(tenant, category)` → `grc_tenant_cat_idx`.

`__str__` → `f"{self.number} {self.title}"`.

### 1.7 Module-level constants re-exported from `models/__init__.py`

`FRAMEWORK_TYPE_CHOICES`, `CONTROL_STATUS_CHOICES`, `COVERAGE_CHOICES`, `POLICY_TYPE_CHOICES`,
`POLICY_STATUS_CHOICES`, `LIKELIHOOD_CHOICES`, `LIKELIHOOD_VALUES`, `RISK_IMPACT_CHOICES`,
`RISK_IMPACT_VALUES`, `TREATMENT_CHOICES`, `RISK_STATUS_CHOICES`.

Plus the six classes. **Adding a model without adding it to the re-export block is a bug** — it
will `ImportError`/`AttributeError` at runtime.

`__str__` → `f"{self.code} v{self.version} — {self.title}"`.

### 1.5 `PolicyAcknowledgement` — same file, child, **no number, no prefix**

| Field | Definition |
|---|---|
| `tenant` | as above |
| `policy` | FK `CorporatePolicy` CASCADE `related_name="acknowledgements"` |
| `user` | FK `settings.AUTH_USER_MODEL` CASCADE `related_name="+"` |
| `policy_version` | `CharField(max_length=20)` — **snapshotted** from `policy.version` at write time |
| `acknowledged_at` | `DateTimeField(auto_now_add=True)` |
| `notes` | `TextField(blank=True)` |

`policy_version` is snapshotted because acknowledging v1 of a policy that has since been
re-versioned to v2 is a materially different act, and a row that read through to the *current*
version would silently rewrite history.

`Meta`: `ordering = ["-acknowledged_at", "-id"]`;
`unique_together = (("policy", "user", "policy_version"),)` — re-acknowledging a **new** version is
allowed; re-acknowledging the same one is not;
index `(policy, acknowledged_at)` → `ack_pol_time_idx`.

**`policy_version` is `editable=False` and is stamped by the view**, never by a form: a member
typing "I acknowledged v2.0" onto a v1 acknowledgement is exactly the forgery the 0.16 evidence
stamps exist to prevent.

`__str__` → `f"{self.user} → {self.policy.code} v{self.policy_version}"`.


`__str__` → `f"{self.code} — {self.title}"`.

### 1.3 `ControlFrameworkMapping` — same file, join row, **no number, no prefix**

Deliberately unnumbered, exactly as 0.20's `FeatureRollout`: a mapping is only ever addressed
through its two parents, so a fifth prefix would mint a number no operator ever looks up.

| Field | Definition |
|---|---|
| `tenant` | as above |
| `framework` | FK `ControlFramework` CASCADE `related_name="mappings"` |
| `control` | FK `ComplianceControl` CASCADE `related_name="mappings"` |
| `clause_reference` | `CharField(max_length=40, blank=True)` — e.g. `CC1.1`, `A.8.15`, `6.1.2` |
| `coverage` | `CharField(max_length=16, choices=COVERAGE_CHOICES, default="not_started")` |
| `notes` | `TextField(blank=True)` |

`COVERAGE_CHOICES` exactly: `not_started`, `partial`, `covered`, `not_applicable`.

`Meta`: `ordering = ["framework__code", "control__code"]`;
`unique_together = (("framework", "control"),)`;
index `(framework, coverage)` → `cfmap_fw_cov_idx`.

**This is the row that makes bullet 1 real** (Drata: "mapping multiple controls to a single
requirement is a common and accepted practice"). Without it there is no framework↔control
relationship at all and bullet 1 is a flat list.

`clean()`: `coverage == "not_applicable"` requires non-blank `notes`. Same ruling as §1.2.

`__str__` → `f"{self.framework.code} / {self.control.code}"`.

def save(self, *args, **kwargs):
    if self.number:
        return super().save(*args, **kwargs)
    for _ in range(5):
        self.number = next_number(ControlFramework, self.tenant, "CFW")
        try:
            with transaction.atomic():
                return super().save(*args, **kwargs)
        except IntegrityError:
            self.number = ""
    return super().save(*args, **kwargs)
```

Imports in `Compliance.py`: `from apps.core.models._base import *  # noqa: F401,F403`,
`from django.core.exceptions import ValidationError`,
`from django.db import IntegrityError, models, transaction`,
`from apps.core.utils import next_number`.

**Actor FKs** (`owner`) are `SET_NULL`, `null=True, blank=True, related_name="+"` — the actor-FK
convention: an ownership trail that loses its name to a deleted account is still a truthful record,
whereas a hard FK would delete the control and take its audit history with it.

