# Build Contract — 0.18 Threat Protection & Security Operations (Module 0, `core`)

**Date:** 2026-09-26 · **Phase:** 3, step 1 (spec — read-only) · **Target app:** `apps/core` (flat, backend rule 9)
**BASE sha:** `647806805d0a07dec2921e2d3293dcc342005d64` (Phase 4 reviews `BASE...HEAD`)
**Migration:** `core.0016_*` — `apps/core/migrations/` was re-listed at contract time and ends at
`0015_alertrule_alertevent_servicecomponent_incident_and_more.py`. **Re-list again immediately before
generating (L43).** If a peer session has added a `core` model and generated its own `0016`, concede the
lower number and generate last. Never `--merge`, never renumber, never delete a peer's migration.
**Inputs:** `.claude/tasks/research-core-0.18.md` (`dacf5027`) and the `# Build Plan — Module 0 0.18` block at
the top of `.claude/tasks/todo.md` (`a0494a77`). This contract **restates** the plan; where the plan is already
exact it is quoted compactly, and the points marked **[RULING]** are the only places this document resolves
something the plan left open or got wrong.

**Dirty tree at session start is NOT mine (L45).** Do not stage, edit, or commit: the four modified
`templates/projects/reporting/*.html` files, and the untracked dirs `.commandcode/`, `.gemini/antigravity/`,
`.workbuddy-ai/`, `.zcode/`. That is a Projects Reporting (7.x) session's live work. This spec session writes
exactly one file: `.claude/tasks/contract-core-0.18.md`. No application code was touched, no migration was
generated, nothing was pushed.

**Totals: 103 model fields (17 + 27 + 25 + 34) · 33 view functions · 33 route names · 17 template files.**
See [RULING] 2 — two of those counts are misstated in the Phase 2 plan.

---

## 0. Verification of the Phase 2 plan against the as-built code (L28)

Every name below was grep-verified in the real source, not read off the plan.

| Plan name | Verdict |
|---|---|
| `core.RateLimitPolicy` @ `apps/core/models/Integration.py:114` | **exists** |
| `AlertRule.CATEGORY_CHOICES` carries `("security", "Security")` @ `Monitoring.py:225-231` | **exists** |
| `AlertRule.SEVERITY_CHOICES` @ `Monitoring.py:91`, re-exposed on the class @ `:220` | **exists** |
| `SyncSchedule.FREQUENCY_CHOICES` @ `Integration.py:223` | **exists** |
| `core.AlertEvent` / `ServiceComponent` / `Incident` @ `Monitoring.py:401` / `:98` / `~560` | **exist** |
| `core.ApiCredential` @ `Integration.py:35` | **exists** |
| `accounts.LoginAttempt` @ `apps/accounts/models.py:572`; `tenant` is **nullable** | **exists** |
| `accounts.security.RISK_STEP_UP_THRESHOLD` @ `apps/accounts/security.py:135` (= `40`) | **exists** |
| `write_audit_log(user, obj, action, changes=None, tenant=None)` @ `apps/core/utils.py:6` | **exists** |
### [RULING] 1 — `core:rate_limit_detail` DOES NOT EXIST. The plan's template contract would 500.

`.claude/tasks/todo.md:291` pins: *"the threat detail links to its `alert_event` (`core:alert_event_detail`)
and its `rate_limit_policy` (`core:rate_limit_detail`) when set"*. **That URL name does not exist.**
`core/urls.py:170-173` registers exactly four `RateLimitPolicy` routes — `rate_limit_list`,
`rate_limit_create`, `rate_limit_edit`, `rate_limit_delete` — and `views/Integration.py:110-136` defines no
`rate_limit_detail` view. Proven in a shell:

```
venv\Scripts\python.exe -c "...reverse('core:rate_limit_detail',args=[1])"
-> NoReverseMatch: Reverse for 'rate_limit_detail' not found.
```

A `{% url %}` on a missing name is a hard 500 on the threat detail page — the L7 failure mode, caught here
before the build rather than after. **Resolution, binding on the build:** the threat detail links the rate
limit to **`core:rate_limit_edit`** with the policy pk (a real per-row destination), falling back to the
policy's `str()` as plain text when `rate_limit_policy_id` is NULL. `core:rate_limit_list` is the target from
the list page. **Do not add a `rate_limit_detail` view** — that would be growing 0.13's surface from 0.18.

### [RULING] 2 — the plan's view and route counts are wrong. Both are 33, not 29 and 41.

The plan says *"all 29 view functions (5 boards + 4 CRUD sets of 5 + 8 actions)"* (`todo.md:269`) and
*"**41 route names**"* (`todo.md:267`), and the smoke gate says *"all **41 routes**"* (`todo.md:453`).
Its own arithmetic gives 5 + 20 + 8 = **33** views and 33 named routes, and the smoke list it enumerates
(4 lists + 4 details + 4 create + 4 edit + 5 boards + 8 actions + 4 delete redirects) also sums to 33. Both
numbers are transcriptions, not design. **The build ships 33 view functions and 33 named routes**, and the
`views/__init__.py` re-export block in §6.3 lists all 33 by name. Do not "make up" 8 more, and do not drop 4
to reach 29.

### [RULING] 3 — every `*_choices` key a list view passes must back a real filter dropdown.

The plan itself forbids the opposite (`todo.md:191`: *"No `no_data_choices`-style key with no dropdown behind
it"*), then leaves five keys unbacked: `securitythreat_list` passes `waf_action_choices` and
`defense_mode_choices` with no `?waf=` / `?defense=` filter; `ipaccessrule_list` passes `scope_choices` and
`source_choices` with no `?scope=` / `?source=` filter; `securityincident_list` passes
`subject_exemption_choices` with no `?exemption=` filter. A key the template reads for nothing is a defect,
and dropping a key the plan pinned is also drift. **Resolution:** add the matching filter rows, so the
dropdown exists and the key earns its place. Exact filter specs are in §3.2. No other key is added, and no
tautological count is passed (0.8's zero-rule on a tautology).

### [RULING] 4 — `crud_list`'s own guards already satisfy the junk-param gate; do not re-implement them.

`crud.py:134-179` skips a junk enum via `_enum_values`, a non-pk or over-range int via `as_db_int`, `?pk=0`
via `_is_pk_lookup`, and a `ValidationError` raised inside `.filter()`. So `?status=nope`,
`?severity=not_a_band`, `?fix=maybe` and `?notifiable=maybe` are already ignored — the views must **not**
add their own parsing, and the gate asserts the *unfiltered* row count, not merely a 200.

---

## 1. Model contract — `apps/core/models/Security.py` (ONE flat file, four models, **103 fields**)

**Header (binding).** The file docstring states the posture in `RateLimitPolicy`'s and `Monitoring.py`'s
voice: *a row here is a report that something was observed, or a policy somebody wrote.* NavERP has **no
IDS/IPS agent, no packet capture, no anomaly engine, no scanner, no CI, no WAF, no CAPTCHA library, no SIEM
client, no log pipeline, no scheduler and no gateway** in this repository. It also records the two ownership
rulings: `RateLimitPolicy` (0.13) and `AlertRule`/`AlertEvent`/`Incident` (0.17) are **extended by FK only and
never re-declared**, and `SecurityIncident.affected_services` (an M2M) is **not** tenant-checked on the admin
path because `TenantConsistentMixin` walks only `ForeignKey`/`OneToOneField` — the 0.17 documented
limitation. Record it; **do not** "fix" it by editing `TenantModelForm` (it would break committed tests in
three other apps).

**Imports (exact, mirroring `Monitoring.py`):**

```python
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403
from apps.core.models.Backup import TenantConsistentMixin
# Reuse-by-REFERENCE (L36) — assign the object, never rebuild the tuple.
from apps.core.models.Integration import RateLimitPolicy, SyncSchedule
from apps.core.models.Monitoring import AlertEvent, AlertRule, Incident, ServiceComponent
```

`SEVERITY_CHOICES = AlertRule.SEVERITY_CHOICES` and `SCAN_FREQUENCY_CHOICES = SyncSchedule.FREQUENCY_CHOICES`
are **module-level aliases**, and each model re-exposes it on the class exactly as `AlertRule` does
(`SEVERITY_CHOICES = SEVERITY_CHOICES`). The tests assert `is` identity, so a pasted copy is the defect.
**Declare in this order:** `IpAccessRule` → `SecurityThreat` → `VulnerabilityFinding` → `SecurityIncident`
(new-to-new FKs `SecurityThreat.mitigated_by` → `IpAccessRule` and `SecurityIncident.primary_threat` →
`SecurityThreat` are why the order is what it is).

**Two module-level constants 0.18 declares** (grep-confirmed: neither exists anywhere in the repo today):

```python
#: GDPR Art. 33(1): "not later than 72 hours after having become aware of it". A RECORDED and DISPLAYED
#: deadline, never an acted-on one — NavERP runs no scheduler and files nothing with any authority.
NOTIFICATION_WINDOW_HOURS = 72

#: A remediation SLA by CVSS band. A POLICY somebody writes down; no scheduler reads it (the
#: SyncSchedule.frequency / AlertRule.frequency / BackupJob.frequency precedent — 0.20 owns the scheduler).
### 1.1 `IpAccessRule` — *an address that is allowed, or is not* — **17 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="ip_access_rules", db_index=True)` |
| 2 | `cidr` | `CharField(max_length=43, validators=[validate_ip_or_cidr])` — a `CharField`, **not** a `GenericIPAddressField`, because a single-address field cannot hold `203.0.113.0/24` |
| 3 | `direction` | `CharField(max_length=5, choices=DIRECTION_CHOICES)` |
| 4 | `action` | `CharField(max_length=28, choices=ACTION_CHOICES, default="log")` |
| 5 | `service` | `FK("core.ServiceComponent", SET_NULL, null=True, blank=True, related_name="+")` |
| 6 | `credential` | `FK("core.ApiCredential", SET_NULL, null=True, blank=True, related_name="+")` |
| 7 | `rate_limit_policy` | `FK("core.RateLimitPolicy", SET_NULL, null=True, blank=True, related_name="ip_access_rules")` |
| 8 | `scope` | `CharField(max_length=10, choices=SCOPE_CHOICES, default="workspace")` |
| 9 | `reason` | `TextField(blank=True)` — required **by `clean()`**, not by the column |
| 10 | `source` | `CharField(max_length=12, choices=SOURCE_CHOICES, default="manual")` |
| 11 | `expires_at` | `DateTimeField(null=True, blank=True)` |
| 12 | `is_active` | `BooleanField(default=True)` |
| 13 | `added_by` | `FK(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| 14 | `added_by_label` | `CharField(max_length=150, blank=True)` (snapshot) |
| 15 | `notes` | `TextField(blank=True)` |
| 16 | `created_at` | `DateTimeField(auto_now_add=True)` |
| 17 | `updated_at` | `DateTimeField(auto_now=True)` |

**CHOICES (exact).** `DIRECTION_CHOICES = [("allow", "Allow"), ("deny", "Deny")]`. `ACTION_CHOICES` —
Cloudflare's IP Access actions verbatim, with **`log` the default**, because a rule that claims to block when
nothing blocks is the exact defect L52 exists to prevent: `allow`, `block`, `challenge`, `managed_challenge`,
`non_interactive_challenge`, `interactive_challenge`, `log`. `SCOPE_CHOICES` — `workspace`, `service`,
`credential` (mirrors `RateLimitPolicy.credential`'s nullable scoping, so the two read consistently).
`SOURCE_CHOICES` — `manual`, `threat`, `rate_limit`, `import`; the docstring says **nothing in NavERP chooses
it automatically**, and `source="manual"` is the only value a view or the seeder may ever write.

**`validate_ip_or_cidr`:** a module-level validator accepting one bare IPv4/IPv6 address (treated as `/32` or
`/128`) or one address plus a prefix length, and refusing anything else. Raise `ValidationError` with a
message naming the column. It is a **field-level** validator, so it protects the admin path too.

**`Meta`:** `ordering = ["-created_at", "-id"]` (`created_at` is never NULL → the C5 MariaDB NULL-sort trap
cannot apply). `unique_together = [("tenant", "cidr", "direction")]` — the same address may sit on both lists
(a `/32` allow inside a `/24` deny is real) but not twice on the same side. Indexes: `(tenant, -created_at)`
→`iprule_tenant_created_idx`, `(tenant, direction)`→`iprule_tenant_dir_idx`, `(tenant, expires_at)`→
### 1.2 `SecurityThreat` — *a threat, as a declared finding* — **27 fields** (the centre of gravity)

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="security_threats", db_index=True)` |
| 2 | `alert_event` | `FK("core.AlertEvent", SET_NULL, null=True, blank=True, related_name="+")` — the 0.17 seam |
| 3 | `rate_limit_policy` | `FK("core.RateLimitPolicy", SET_NULL, null=True, blank=True, related_name="security_threats")` — the rate-limit seam, **by string FK** |
| 4 | `service` | `FK("core.ServiceComponent", SET_NULL, null=True, blank=True, related_name="+")` |
| 5 | `service_label` | `CharField(max_length=150, blank=True)` (snapshot, **not** a form field) |
| 6 | `target_user` | `FK(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| 7 | `target_credential` | `FK("core.ApiCredential", SET_NULL, null=True, blank=True, related_name="+")` |
| 8 | `title` | `CharField(max_length=200)` |
| 9 | `threat_type` | `CharField(max_length=30, choices=THREAT_TYPE_CHOICES, default="other")` |
| 10 | `severity` | `CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")` — **by reference** |
| 11 | `mitre_technique` | `CharField(max_length=20, blank=True)` |
| 12 | `mitre_tactic` | `CharField(max_length=50, blank=True)` |
| 13 | `rule_reference` | `CharField(max_length=120, blank=True)` |
| 14 | `waf_action` | `CharField(max_length=30, choices=WAF_ACTION_CHOICES, blank=True, default="")` |
| 15 | `defense_mode` | `CharField(max_length=20, choices=DEFENSE_MODE_CHOICES, blank=True, default="")` |
| 16 | `source_ip` | `GenericIPAddressField(null=True, blank=True)` |
| 17 | `detected_at` | `DateTimeField(default=timezone.now)` — never NULL |
| 18 | `occurrence_count` | `PositiveIntegerField(default=1, validators=[MinValueValidator(1)])` |
| 19 | `summary` | `TextField(blank=True)` |
| 20 | `detail` | `TextField(blank=True)` |
| 21 | `evidence` | `TextField(blank=True)` |
| 22 | `status` | `CharField(max_length=14, choices=STATUS_CHOICES, default="new")` |
| 23 | `mitigated_by` | `FK("core.IpAccessRule", SET_NULL, null=True, blank=True, related_name="mitigated_threats")` |
| 24 | `resolved_at` | `DateTimeField(null=True, blank=True)` — action-stamped, **off the form** (L22) |
| 25 | `resolved_by` | `FK(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| 26 | `notes` | `TextField(blank=True)` |
| 27 | `created_at` | `DateTimeField(auto_now_add=True)` |

**No `updated_at`** — the plan's field list ends at `created_at` and a finding is a point-in-time report; its
history lives in `core.AuditLog` and in the lifecycle stamps, not in a column that moves on every edit.

**CHOICES (exact).** `THREAT_TYPE_CHOICES` — a union enum covering bullets 1, 4 and 5: `brute_force`,
`credential_stuffing`, `anomalous_login`, `privilege_escalation`, `suspicious_api_activity`,
`data_exfiltration`, `malware`, `phishing`, `waf_rule_match`, `rate_limit_exceeded`, `bot_abuse`, `other`.
`STATUS_CHOICES` — `new`, `triaged`, `investigating`, `contained`, `resolved`, `false_positive`, `ignored`
(Defender for Cloud Apps' acknowledge/resolve/suppress/dismiss shape, mapped to a lifecycle NavERP can hold).
`WAF_ACTION_CHOICES` — `none`, `log`, `block`, `challenge`, `managed_challenge`, `interactive_challenge`
(**a recorded posture, not an enforcement**). `DEFENSE_MODE_CHOICES` — `none`, `captcha`, `challenge`,
### 1.3 `VulnerabilityFinding` — *a known weakness, and what was done about it* — **25 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="vulnerability_findings", db_index=True)` |
| 2 | `title` | `CharField(max_length=200)` |
| 3 | `advisory_id` | `CharField(max_length=40, db_index=True)` |
| 4 | `finding_source` | `CharField(max_length=20, choices=FINDING_SOURCE_CHOICES)` |
| 5 | `component` | `FK("core.ServiceComponent", SET_NULL, null=True, blank=True, related_name="+")` — nullable: a vulnerable *dependency* has no service |
| 6 | `package_name` | `CharField(max_length=150, blank=True)` |
| 7 | `installed_version` | `CharField(max_length=60, blank=True)` |
| 8 | `severity` | `CharField(max_length=8, choices=SEVERITY_BAND_CHOICES, default="medium")` |
| 9 | `cvss_score` | `DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])` |
| 10 | `epss_score` | `DecimalField(max_digits=6, decimal_places=5, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1)])` |
| 11 | `fix_available` | `CharField(max_length=8, choices=FIX_AVAILABLE_CHOICES, null=True, blank=True, default=None)` |
| 12 | `fixed_in_version` | `CharField(max_length=60, blank=True)` |
| 13 | `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="open")` |
| 14 | `accepted_reason` | `TextField(blank=True)` |
| 15 | `accepted_by` | `FK(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| 16 | `accepted_at` | `DateTimeField(null=True, blank=True)` — form-stamped, see §2.3 |
| 17 | `due_on` | `DateField(null=True, blank=True)` |
| 18 | `first_seen_at` | `DateTimeField(default=timezone.now)` |
| 19 | `last_seen_at` | `DateTimeField(null=True, blank=True)` |
| 20 | `remediation_note` | `TextField(blank=True)` |
| 21 | `evidence` | `TextField(blank=True)` |
| 22 | `notes` | `TextField(blank=True)` |
| 23 | `scan_frequency` | `CharField(max_length=8, choices=SCAN_FREQUENCY_CHOICES, default="manual")` — **by reference** |
| 24 | `created_at` | `DateTimeField(auto_now_add=True)` |
| 25 | `updated_at` | `DateTimeField(auto_now=True)` |

**The severity here is a CVSS band and is deliberately NOT `AlertRule.SEVERITY_CHOICES`.**
`SEVERITY_BAND_CHOICES` — `none`, `low`, `medium`, `high`, `critical`. **The file docstring must carry the
warning explicitly** — same reason `AlertRule.metric_key` overlaps `HealthMetric.METRIC_CHOICES` by string
without meaning the same thing — or the next agent will "fix" the duplication by pointing this at the alert
vocabulary. This is the ONE place a different severity list is correct, and it is a different *fact* (a CVSS
band vs a firing severity).

**CHOICES (exact).** `FINDING_SOURCE_CHOICES` — `dependency`, `operating_system`, `application`,
`configuration`, `third_party`, `misconfiguration`. `FIX_AVAILABLE_CHOICES` — `yes`, `no`, `partial` (Snyk's
`fixAvailable` made explicit: "no fix exists" and "we have not got round to it" must never render as the same
word; the NULL third state is "nobody has determined it"). `STATUS_CHOICES` — `open`, `in_progress`, `fixed`,
`risk_accepted`, `false_positive`, `not_applicable` — each terminal value is a **decision somebody made**, not
an absence of data.

**`Meta`:** `ordering = ["-first_seen_at", "-id"]`. Indexes: `(tenant, status)`→`vulfind_tenant_status_idx`,
`(tenant, severity)`→`vulfind_tenant_severity_idx`, `(tenant, advisory_id)`→`vulfind_tenant_advisory_idx`,
`(tenant, -first_seen_at)`→`vulfind_tenant_firstseen_idx`. Every name is short for MariaDB's hard name limit.

**`clean()` refusals:** (a) `status="risk_accepted"` **requires** a non-blank `accepted_reason` **and**
`accepted_by` — an accepted risk with no stated reason is an unowned risk (the Tenable-exception discipline,
and it belongs on the finding, not in a separate exclusions table); (b) `status="fixed"` with
`fix_available="no"` is refused — **a finding with no fix is not a finding that is fixed**; (c) non-blank
### 1.4 `SecurityIncident` — *the response, with a clock on it* — **34 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="security_incidents", db_index=True)` |
| 2 | `incident` | `FK("core.Incident", SET_NULL, null=True, blank=True, related_name="security_incidents")` — the 0.17 seam: one incident with two faces, not two incidents |
| 3 | `primary_threat` | `FK("core.SecurityThreat", SET_NULL, null=True, blank=True, related_name="security_incidents")` |
| 4 | `title` | `CharField(max_length=200)` |
| 5 | `incident_class` | `CharField(max_length=20, choices=INCIDENT_CLASS_CHOICES, default="security_incident")` |
| 6 | `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="detected")` |
| 7 | `severity` | `CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")` — **by reference** |
| 8 | `discovered_at` | `DateTimeField(default=timezone.now)` — **a form field**; the anchor for every legal clock |
| 9 | `contained_at` | `DateTimeField(null=True, blank=True)` — action-stamped, off the form (L22) |
| 10 | `eradicated_at` | `DateTimeField(null=True, blank=True)` — action-stamped |
| 11 | `recovered_at` | `DateTimeField(null=True, blank=True)` — action-stamped |
| 12 | `closed_at` | `DateTimeField(null=True, blank=True)` — action-stamped |
| 13 | `is_notifiable` | `BooleanField(null=True, blank=True)` — NULL = "nobody has decided yet" |
| 14 | `notifiable_reason` | `TextField(blank=True)` |
| 15 | `authority_notified_at` | `DateTimeField(null=True, blank=True)` — action-stamped, off the form |
| 16 | `authority_reference` | `CharField(max_length=150, blank=True)` — a human-typed filing reference → **form field** |
| 17 | `subjects_notified` | `BooleanField(null=True, blank=True)` — action-stamped, off the form |
| 18 | `subjects_notified_at` | `DateTimeField(null=True, blank=True)` — action-stamped |
| 19 | `subject_exemption` | `CharField(max_length=28, choices=SUBJECT_EXEMPTION_CHOICES, default="none")` |
| 20 | `data_subjects_affected` | `PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])` |
| 21 | `records_affected` | `PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])` |
| 22 | `dpo_contact` | `CharField(max_length=200, blank=True)` |
| 23 | `likely_consequences` | `TextField(blank=True)` |
| 24 | `measures_taken` | `TextField(blank=True)` |
| 25 | `measures_proposed` | `TextField(blank=True)` |
| 26 | `forensic_log` | `TextField(blank=True)` — a **narrative**, never a log pipeline |
| 27 | `root_cause` | `TextField(blank=True)` |
| 28 | `lessons_learned` | `TextField(blank=True)` |
| 29 | `owner` | `FK(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| 30 | `owner_label` | `CharField(max_length=150, blank=True)` (snapshot) |
| 31 | `affected_services` | `M2M("core.ServiceComponent", blank=True, related_name="security_incidents")` |
**CHOICES (exact).** `INCIDENT_CLASS_CHOICES` — `security_incident`, `data_breach`, `unauthorized_access`,
`malware`, `phishing`, `insider_threat`, `policy_violation`, `denial_of_service`, `other`; **`data_breach` is
the one value that switches the whole notification block on** in the detail template. `STATUS_CHOICES` — the
NIST SP 800-61r2 lifecycle: `detected`, `triage`, `investigating`, `contained`, `eradicated`, `recovered`,
`closed`, `false_positive` — **deliberately not 0.17's `Incident.status` union**, because a breach does not
pass through `scheduled` or `monitoring` and forcing it into that enum would be the L36 bug in the other
direction. `SUBJECT_EXEMPTION_CHOICES` — Art. 34(3)'s three exemptions as the Article names them: `none`,
`technical_measures`, `subsequent_measures`, `disproportionate_effort`.

**The Art. 33(3) content fields map one-to-one and each says which sub-paragraph it is:**
`data_subjects_affected` / `records_affected` = 33(3)(a) (approximate numbers, both **nullable**: an unknown
count is not a zero count); `dpo_contact` = 33(3)(b); `likely_consequences` = 33(3)(c); `measures_taken` /
`measures_proposed` = 33(3)(d). The form labels in §2.4 say so on the page.

**`regulatory_deadline` is a `@property`, never a column and never a form field.** Return
`self.discovered_at + timedelta(hours=NOTIFICATION_WINDOW_HOURS)` when `discovered_at` is set, else `None`.
The research says "derived in `save()`" in one place and "a property rather than a stored column so the anchor
and the deadline cannot drift" in another; **the property is the stronger statement and the one this contract
takes** — a stored column can drift from `discovered_at`, a property cannot. Companion read-only properties:
`hours_remaining` (`None` when there is no deadline), `is_overdue` (`hours_remaining is not None and < 0`),
`deadline_display` (`"—"` when no `discovered_at`).

**`Meta`:** `ordering = ["-discovered_at", "-id"]`. Indexes: `(tenant, -discovered_at)`→
`secinc_tenant_discovered_idx`, `(tenant, status)`→`secinc_tenant_status_idx`, `(tenant, incident_class)`→
`secinc_tenant_class_idx`, `(tenant, is_notifiable)`→`secinc_tenant_notifiable_idx`.

**`clean()` refusals:** (a) `is_notifiable is None` while `status == "closed"` is refused — **you may not
close a breach without having decided whether it is notifiable**; (b) `authority_notified_at` set while
`is_notifiable is not True` is refused; (c) `subjects_notified is True` together with a non-`none`
`subject_exemption` is refused (the exemption is the reason you did *not* notify), and `subjects_notified is
False` with `subject_exemption == "none"` is refused (a recorded "no" needs a stated reason — the exemption is
the defensible part of the record and an auditor asks for it first).

**No `save()` override. No hash, no chain, no seal column, and no FK to `core.AuditLog`** —
`procurement.AuditSeal` (6.17) already chains SHA-256 over a range of `core.AuditLog` ids, and a second
tamper-evidence mechanism is a parallel schema for the same concept. `forensic_log` is a **narrative**; the
detail page points at procurement's seal register in prose.
`__str__` = `f"{self.title} - {self.get_status_display()}"`.

## 2. Form contract — `apps/core/forms/Security.py` (flat, one file, four forms)

All four inherit `TenantModelForm` via `from apps.core.forms._common import *`, and import the models from
`apps.core.models` exactly as `forms/Monitoring.py` does.

**L22 is absolute: zero editable `DateTimeField`s for system-set stamps.** Out of every `Meta.fields`:
`SecurityThreat.resolved_at` / `resolved_by` / `service_label` / `created_at`; `IpAccessRule.added_by` /
`added_by_label` / `created_at` / `updated_at`; `VulnerabilityFinding.accepted_at` / `created_at` /
`updated_at`; `SecurityIncident.contained_at` / `eradicated_at` / `recovered_at` / `closed_at` /
`authority_notified_at` / `subjects_notified` / `subjects_notified_at` / `owner_label` / `created_at` /
`updated_at`. Also out: `regulatory_deadline` (a property, and it must never be typed).

**The deliberate exceptions**, each argued as 0.17 argued its two: `SecurityThreat.detected_at` and
`SecurityIncident.discovered_at` (facts a person is *declaring*, not stamps a system took — a finding that
cannot say when is a finding nobody can age); `IpAccessRule.expires_at` (a forward-declared block boundary a
human types, the 0.16 `BackupJob.retain_until` precedent); `VulnerabilityFinding.first_seen_at` /
`last_seen_at` / `due_on` (the remediation schedule somebody sets). `TenantModelForm.__init__` already
installs a `datetime-local` widget with matching `input_formats` for `DateTimeField`s and a `date` widget for
`DateField`s — **no widget is re-declared in these forms.**

**No form re-implements a `clean()` refusal** — the model owns every rule, so the admin path (a plain
`ModelForm`) cannot bypass it. **No form exposes a field the model refuses.**

### 2.1 `IpAccessRuleForm(TenantModelForm)`

```python
class Meta:
    model = IpAccessRule
    fields = ["cidr", "direction", "action", "scope", "service", "credential", "rate_limit_policy",
              "reason", "source", "expires_at", "is_active", "notes"]
    labels = {
        "cidr": "IP address or CIDR block",
        "reason": "Why this entry exists (required)",
        "action": "Recorded action (nothing enforces this in NavERP)",
        "scope": "Scope",
    }
```

No `clean_*` method — every refusal lives in the model's `clean()`, so the admin path is covered by the same
rule. **No `save()` override**: `added_by` / `added_by_label` are stamped by the create **view** from
`request.user` (there is no `request` in a form, and an admin-created rule honestly has no "who asked" — the
field is nullable and stays NULL on that path, which is true).

### 2.2 `SecurityThreatForm(TenantModelForm)`

```python
class Meta:
    model = SecurityThreat
    fields = ["title", "threat_type", "severity", "status", "detected_at", "alert_event",
              "rate_limit_policy", "service", "target_user", "target_credential", "mitre_technique",
              "mitre_tactic", "rule_reference", "waf_action", "defense_mode", "source_ip",
              "occurrence_count", "summary", "detail", "evidence", "mitigated_by", "notes"]
    labels = {
        "mitre_technique": "MITRE ATT&CK technique (e.g. T1110.001 - free text, not a fixed list)",
        "defense_mode": "Bot/abuse mitigation posture (recorded, not enforced)",
        "waf_action": "WAF action (reference only - NavERP runs no WAF)",
        "evidence": "Evidence (a ticket id, a pasted log line, a screenshot path - not a payload)",
    }
```

`__init__` narrows `alert_event` to `.select_related("rule").order_by("-fired_at", "-id")[:200]` and
`mitigated_by` to `.order_by("-created_at")[:200]` — the `IncidentForm.primary_alert` N+1/cap precedent,
applied **locally and not** by changing the shared `TenantModelForm` (that would put committed tests in
three other apps at risk). A local `__init__` cannot be re-filtered away by the base class's tenant-scoping
loop, which runs inside `super().__init__()` above. `save()` writes `service_label` from the chosen service,
exactly as `AlertEventForm` does, and **only** when a service IS chosen (clearing the service is a legitimate
correction; overwriting unconditionally would destroy the snapshot meant to outlive the component). No other
`save()` override.

### 2.3 `VulnerabilityFindingForm(TenantModelForm)`

```python
class Meta:
    model = VulnerabilityFinding
    fields = ["title", "advisory_id", "finding_source", "component", "package_name", "installed_version",
              "severity", "cvss_score", "epss_score", "fix_available", "fixed_in_version", "status",
              "accepted_reason", "accepted_by", "due_on", "first_seen_at", "last_seen_at", "scan_frequency",
              "remediation_note", "evidence", "notes"]
    labels = {
        "scan_frequency": "Declared scan cadence (nothing in NavERP runs a scan)",
        "due_on": "Remediation deadline (blank = none set)",
        "cvss_score": "CVSS score (blank = not scored)",
        "fix_available": "Fix available?",
    }
```

`save()` back-fills `accepted_at` **only when `accepted_by` is set and `accepted_at` is empty**, so a later
edit cannot rewrite when the risk was accepted (the `AlertEventForm.first_seen_at` back-fill precedent).
`accepted_by`'s queryset is narrowed to the tenant's **active** users in `__init__`.

### 2.4 `SecurityIncidentForm(TenantModelForm)`

```python
class Meta:
    model = SecurityIncident
    fields = ["title", "incident_class", "status", "severity", "discovered_at", "incident",
              "primary_threat", "owner", "affected_services", "is_notifiable", "notifiable_reason",
              "authority_reference", "subject_exemption", "data_subjects_affected", "records_affected",
              "dpo_contact", "likely_consequences", "measures_taken", "measures_proposed", "forensic_log",
              "root_cause", "lessons_learned", "evidence", "notes"]
    labels = {
        "is_notifiable": "Notifiable to the supervisory authority? (blank = not yet decided)",
        "forensic_log": "Forensic narrative (what was found, preserved, and still to be collected - a "
                        "narrative, not a log pipeline)",
        "data_subjects_affected": "Approx. data subjects affected (Art. 33(3)(a))",
        "records_affected": "Approx. personal data records affected (Art. 33(3)(a))",
        "dpo_contact": "DPO contact (Art. 33(3)(b))",
        "likely_consequences": "Likely consequences (Art. 33(3)(c))",
        "measures_taken": "Measures taken (Art. 33(3)(d))",
        "measures_proposed": "Measures proposed (Art. 33(3)(d))",
    }
## 3. View + context contract — `apps/core/views/Security.py` (flat, one file, **33 views**)

**This is the section that decides whether the build works. A name left unpinned here is a silently blank
region or a `NoReverseMatch` (L7/L8).**

The file preamble states the module posture in the 0.17 `views/Monitoring.py` voice and declares:

```python
#: The honest-limit lines the overview, the five boards and all sixteen register pages print VERBATIM.
#: A module-level constant so a page and its board cannot disagree about what this application can and
#: cannot do — the same reason 0.16 has BACKUP_NOTES and 0.17 has MONITORING_NOTES. No view invents prose.
SECURITY_NOTES = [ ... three lines, each carrying one of the thirteen DECLINE items ... ]
```

**Universal rules, all 33 views.** Every view is `@tenant_admin_required`. Every delete and every action is
`@require_POST` **above** the role gate — decorators apply bottom-up, so the outermost runs first; with the
role gate outermost a member's GET is answered 403 before the method check runs, and the house standard is
405 for a wrong method regardless of role. Every queryset is `Model.objects.filter(tenant=request.tenant)`,
never `.all()`. Every action's guard lives in the **view**, not only in a hidden button, so a hand-made POST
cannot reach it and the audit row is not written either. Every mutation calls
`write_audit_log(request.user, obj, "update", changes={"verb": "<name>", ...})` — `AuditLog.action` is
`varchar(10)`, so the verb goes in `changes` (the `views/Localization.py` pattern). Every success message
says **"recorded"**, never "detected", "blocked", "scanned", "enforced" or "notified". Any `request.POST`
string echoed back is truncated to its column width.

`crud_*` helpers arrive via `from apps.core.views._common import *`; they supply `object_list` /
`page_obj` / `q` (list), `form` / `obj` / `is_edit` (create & edit), and `obj` (detail). `write_audit_log`
comes from `apps.core.utils`.

### 3.1 The five boards and the landing page (computed, **no models**)

| View | Route name | Template | Every context key |
|---|---|---|---|
| `security_overview(request)` | `security_overview` | `core/securityoverview.html` | `threat_count`, `open_threat_count`, `new_threat_count`, `ip_rule_count`, `active_deny_count`, `vulnerability_count`, `open_vulnerability_count`, `overdue_vulnerability_count`, `incident_count`, `open_incident_count`, `breach_undecided_count`, `window_hours`, `notes` |
| `threat_board(request)` | `threat_board` | `core/threatboard.html` | `open_threats`, `open_count`, `open_total`, `state_rows`, `state_counts`, `severity_rows`, `severity_counts`, `type_rows`, `type_counts`, `top_source_ips`, `unmitigated_count`, `correlated_alert_count`, `notes` |
| `vulnerability_board(request)` | `vulnerability_board` | `core/vulnerabilityboard.html` | `band_rows`, `band_counts`, `status_rows`, `status_counts`, `source_rows`, `source_counts`, `open_total`, `overdue_count`, `no_fix_count`, `accepted_count`, `unscored_count`, `sla_days`, `oldest`, `notes` |
| `breach_clock_board(request)` | `breach_clock_board` | `core/breachclock.html` | `open_incidents`, `undecided`, `undecided_count`, `overdue_count`, `notifiable_count`, `not_notifiable_count`, `notified_authority_count`, `subjects_notified_count`, `window_hours`, `open_total`, `notes` |
| `brute_force_board(request)` | `brute_force_board` | `core/bruteforceboard.html` | `failed_addresses`, `failed_total`, `step_up_threshold`, `mfa_challenged_total`, `notes` |

- **Tenant guard on `security_overview`:** `if request.tenant is None: messages.info(...); return
  redirect("dashboard:home")` (the `monitoring_overview` pattern). The same guard belongs on all five
  boards, since each queries a tenant-scoped model.
- **Shapes of the bounded lists.** `open_threats` = list of dicts `{"threat": t, "age_days": t.age_days,
  "mitigation": t.mitigated_by_id}` from `status not in {resolved, false_positive, ignored}` ordered
  `-detected_at`, **capped at 200**. `open_incidents` = list of dicts `{"incident": i,
  "hours_remaining": i.hours_remaining, "deadline": i.regulatory_deadline, "overdue": i.is_overdue}` for
  non-closed incidents ordered `-discovered_at`, **capped at 200**. `failed_addresses` = list of dicts
  `{"ip": ip, "failures": n, "identifiers": n, "max_risk": n, "last_seen": dt}`, grouped **in the database**
  with `Count`/`Max` over `LoginAttempt.objects.filter(tenant=request.tenant, success=False,
  ip__isnull=False)`, **capped**. `top_source_ips` is the same grouped/capped shape over `SecurityThreat`
  with `source_ip__isnull=False`. `undecided` is the `is_notifiable is None` subset of open incidents —
  **the breach board's whole point**. `oldest` is the oldest open finding as a single bounded dict (`None`
  when there is none — never a fabricated placeholder object).
- **The zipped pairs are zipped IN THE VIEW** (`state_rows` / `state_counts`, `severity_rows` /
  `severity_counts`, `type_rows` / `type_counts`, `band_rows` / `band_counts`, `status_rows` / `status_counts`,
  `source_rows` / `source_counts`) — a template cannot index a dict by a loop variable. Each `_rows` is a
  list of `(value, label, count)` triples; each `_counts` is the parallel list of the same counts, so a
  template can read either.
- **`open_total` is the UNTRUNCATED total** on the threat and breach boards, so a truncated list is never
  mistaken for a quiet one.
- **`sla_days` is the whole `REMEDIATION_SLA_DAYS` mapping**, so the page prints the policy it is judged
  against. **`window_hours` is `NOTIFICATION_WINDOW_HOURS`.** **`step_up_threshold` is read from
  `accounts.security.RISK_STEP_UP_THRESHOLD`, never re-declared.**
- **`correlated_alert_count`** is the count of open threats with `alert_event_id` set — the 0.17 seam made
  visible. **`unmitigated_count`** is open threats with `mitigated_by_id` None.
- **`brute_force_board` declares no 0.18 table and writes no `accounts` row** — it is a *query* over
  `accounts.LoginAttempt`. The **`tenant=None` caveat is printed on the page**: `LoginAttempt.tenant` is
  nullable, so attempts against an unknown identifier are recorded with no tenant and are **excluded** from
  these figures — the board counts the attempts it can attribute, and says so. A `0` here means "no
  attributable failures recorded", not "no attacks".
- **The zero rule:** an empty board renders "no threats have been recorded" — **never "0" in
  `badge-green`**, because a quiet board here means *nobody has written anything down*, not *nothing is
### 3.2 The four list views (`crud_list` supplies `object_list`, `page_obj`, `q`)

| View | Route name | Template |
|---|---|---|
| `securitythreat_list` | `securitythreat_list` | `core/securitythreat/list.html` |
| `ipaccessrule_list` | `ipaccessrule_list` | `core/ipaccessrule/list.html` |
| `vulnerabilityfinding_list` | `vulnerabilityfinding_list` | `core/vulnerabilityfinding/list.html` |
| `securityincident_list` | `securityincident_list` | `core/securityincident/list.html` |

**`securitythreat_list`**

- queryset: `SecurityThreat.objects.filter(tenant=request.tenant).select_related("service", "alert_event",
  "rate_limit_policy")`
- `search_fields=["title", "mitre_technique", "mitre_tactic", "source_ip", "summary", "evidence", "notes"]`
- `filters=[("status", "status", False), ("type", "threat_type", False), ("severity", "severity", False),
  ("service", "service_id", True), ("waf", "waf_action", False), ("defense", "defense_mode", False)]`
  — the last two are added per **[RULING] 3** so `waf_action_choices` and `defense_mode_choices` back a real
  dropdown. **The GET param is `type`; the column is `threat_type`** — the template and the filter spec must
  both say so, exactly as the `metric` / `metric_key` pair does in 0.17.
- `extra_context`: `status_choices` = `SecurityThreat.STATUS_CHOICES`, `threat_type_choices`,
  `severity_choices` = `AlertRule.SEVERITY_CHOICES`, `waf_action_choices`, `defense_mode_choices`,
  `services` = `ServiceComponent.objects.filter(tenant=request.tenant).order_by("name")`, `notes`.

**`ipaccessrule_list`**

- queryset: `IpAccessRule.objects.filter(tenant=request.tenant).select_related("service", "credential",
  "rate_limit_policy")`
- `search_fields=["cidr", "reason", "source", "notes"]`
- `filters=[("direction", "direction", False), ("action", "action", False), ("active", "is_active", False),
  ("service", "service_id", True), ("scope", "scope", False), ("source", "source", False)]`
  — `scope` and `source` added per **[RULING] 3**.
- `extra_context`: `direction_choices`, `action_choices`, `scope_choices`, `source_choices`, `services`,
  `notes`.

**`vulnerabilityfinding_list`**

- queryset: `VulnerabilityFinding.objects.filter(tenant=request.tenant).select_related("component")`
- `search_fields=["title", "advisory_id", "package_name", "installed_version", "remediation_note",
  "evidence", "notes"]`
- `filters=[("status", "status", False), ("severity", "severity", False), ("source", "finding_source",
  False), ("component", "component_id", True), ("fix", "fix_available", False)]`
- `extra_context`: `status_choices`, `severity_choices` (**`SEVERITY_BAND_CHOICES`**),
  `finding_source_choices`, `fix_available_choices`, `components` =
  `ServiceComponent.objects.filter(tenant=request.tenant).order_by("name")`, `sla_days` =
  `REMEDIATION_SLA_DAYS`, `notes`.
  **The `severity` filter param is a DIFFERENT vocabulary from the threat list's** — the two dropdowns are
  built from two different CHOICES constants and must never share a context key by accident. The
  `?source=` param maps to `finding_source`; the `?component=` dropdown reads `components`, and its options
  compare with `|stringformat:"d"`.

**`securityincident_list`**

- queryset: `SecurityIncident.objects.filter(tenant=request.tenant).select_related("incident",
### 3.3 The sixteen create / detail / edit / delete views

All four sets share one shape. `<name>` is `securitythreat`, `ipaccessrule`, `vulnerabilityfinding`,
`securityincident`; `<entity>` is the same word. Every create/edit renders `form` (+ `obj` on edit, +
`is_edit=True`); every detail renders `obj`; every `extra_context` below adds `notes`.

| View | Route name | HTTP | Implementation and its extra context keys |
|---|---|---|---|
| `<name>_create` | `<name>_create` | GET, POST | `crud_create(request, form_class=…, template="core/<entity>/form.html", success_url="core:<name>_list", extra_context={"notes": SECURITY_NOTES})` — **plus**, for `ipaccessrule` only, a `save()` wrapper that stamps `added_by=request.user` and `added_by_label=request.user.get_username()` on create (the view is the only layer that has a `request`) |
| `<name>_detail` | `<name>_detail` | GET | `crud_detail(request, model=…, pk=pk, template="core/<entity>/detail.html", select_related=(…), extra_context={…})` — the keys are per entity, below |
| `<name>_edit` | `<name>_edit` | GET, POST | `crud_edit(…, success_url=reverse("core:<name>_detail", args=[pk]), extra_context={"notes": SECURITY_NOTES})` — **`reverse(...)` and not the bare name**: `crud_edit` calls `redirect(success_url)` with no arguments, so a pk-taking route passed as a string raises `NoReverseMatch` AFTER the row is saved and the operator sees a 500 for a write that succeeded |
| `<name>_delete` | `<name>_delete` | **POST only** | `@require_POST` ABOVE `@tenant_admin_required`, then `crud_delete(request, model=…, pk=pk, success_url="core:<name>_list")`. A GET redirects to the list without deleting (`crud_delete` is self-defending too) |

**`securitythreat_detail`** — `select_related=("service", "alert_event__rule", "rate_limit_policy",
"mitigated_by", "target_user", "target_credential")`; `extra_context` = `incident_count` (the
`SecurityIncident` count for this threat), `age_days`, `source_ip_display`, `notes`.

**`ipaccessrule_detail`** — `select_related=("service", "rate_limit_policy", "added_by")`;
`extra_context` = `mitigated_threat_count` (`SecurityThreat.objects.filter(tenant=request.tenant,
mitigated_by_id=pk).count()`), `is_expired`, `expires_display`, `notes`. **The template lists the threats it
mitigates** — that is the list these two keys exist to feed.

**`vulnerabilityfinding_detail`** — `select_related=("component", "accepted_by")`; `extra_context` =
`sla_days`, `is_overdue`, `days_overdue`, `is_fixable`, `cvss_display`, `notes`.

**`securityincident_detail`** — `select_related=("incident", "primary_threat", "owner")`; `extra_context` =
`deadline_display`, `hours_remaining`, `is_overdue`, `window_hours` (`NOTIFICATION_WINDOW_HOURS`), `notes`.
The `affected_services` M2M is read in the template via `obj.affected_services.all` (prefetched by the
queryset), so **no extra context key is added for it**. The notification block renders only when
`obj.incident_class == "data_breach"`.

All four creates redirect to their list.

### 3.4 The eight POST-only actions (the 0.17 `alertevent_acknowledge` / `_resolve` shape)

Every one: `@require_POST` above `@tenant_admin_required`; `get_object_or_404(Model, pk=pk,
tenant=request.tenant)`; guard first, message + redirect on refusal with **no write and no audit row**; on
success stamp, `write_audit_log`, message, redirect to `core:securitythreat_detail` /
`core:securityincident_detail` for that pk.

| View | Route name | Guard | Stamps |
|---|---|---|---|
| `securitythreat_triage` | `securitythreat_triage` | refuse when `status != "new"` — "only a new finding is waiting on an analyst" | `status="triaged"`; message: *"Triaged. This records that somebody looked at it - NavERP did not detect anything."* |
| `securitythreat_resolve` | `securitythreat_resolve` | refuse when `status in {resolved, false_positive, ignored}` — re-resolving would overwrite a settled history | `status="resolved"`, `resolved_at=now`, `resolved_by=request.user`, plus an optional `resolution_note` from `request.POST` **truncated to 255 chars** (an untruncated string raises `DataError` inside the driver and the operator sees a 500 for a write that half-happened). Message: *"Resolution recorded. NavERP did not fix anything - this records that somebody said it was fixed."* |
| `securityincident_contain` | `securityincident_contain` | refuse unless the legal predecessor is met (cannot contain before triage) **and** `contained_at` is unset, so a second POST cannot rewrite the first | `contained_at=now` |
| `securityincident_eradicate` | `securityincident_eradicate` | legal predecessor is `contained_at` set; refuse if `eradicated_at` already set | `eradicated_at=now` |
| `securityincident_recover` | `securityincident_recover` | legal predecessor is `eradicated_at` set; refuse if `recovered_at` already set | `recovered_at=now` |
| `securityincident_close` | `securityincident_close` | legal predecessor is `recovered_at` set, **and** refuse unless `is_notifiable is not None` — the readable version of the model's `clean()` rule that a closed undecided breach is refused; refuse if `closed_at` already set | `closed_at=now`, `status="closed"` |
| `securityincident_notify_authority` | `securityincident_notify_authority` | refuse unless `is_notifiable is True` **and** `authority_notified_at is None` | `authority_notified_at=now`; the message states NavERP **filed nothing**: *"This records that somebody says a filing was made. NavERP sends nothing to any authority."* |
| `securityincident_notify_subjects` | `securityincident_notify_subjects` | refuse unless `subject_exemption == "none"` **and** `subjects_notified is not True` | `subjects_notified=True`, `subjects_notified_at=now`; the same "NavERP notified nobody" message |

All four lifecycle messages say "recorded". These are the NIST SP 800-61r2 steps as four POST-only verbs,
one stamp each.

---

  "primary_threat", "owner").prefetch_related("affected_services")`
- `search_fields=["title", "notifiable_reason", "authority_reference", "root_cause", "lessons_learned",
  "notes"]`
## 4. URL contract — `apps/core/urls.py` (the flat `crud(slug, name)` factory; **do not restructure it**)

**Surgical `Edit` only** — another session may be in this file (L43). Append one 0.18 block at the end of
the existing `urlpatterns` tuple, **immediately after the 0.17 block** (which ends at the `incident_notify`
`path(...)` and the closing `)` on `core/urls.py:245`). The `crud()` factory generates the five standard
routes per model, so the four entities need four `crud(...)` calls and **no hand-written CRUD `path()`
lines**. The five literal board routes come **first**, in their own list, before the `crud()` groups — Django
is first-match-wins and a greedy route declared first shadows `add/` (the 0.16 and 0.17 ordering, for the
same reason).

```python
    # ===================== 0.18 Threat Protection & Security Operations =====================
    # Literal segments BEFORE the `crud()` groups below, and the POST-only action routes AFTER the
    # group that owns them — the 0.17 ordering, for the same reason.
    + [
        path("security/", views.security_overview, name="security_overview"),
        path("security/board/threats/", views.threat_board, name="threat_board"),
        path("security/board/vulnerabilities/", views.vulnerability_board, name="vulnerability_board"),
        path("security/board/breach-clock/", views.breach_clock_board, name="breach_clock_board"),
        path("security/board/brute-force/", views.brute_force_board, name="brute_force_board"),
    ]
    + crud("security/ip-rules", "ipaccessrule")
    + crud("security/threats", "securitythreat")
    + [
        # POST-only verbs, declared after the literal `add/` route above so it cannot shadow it.
        path("security/threats/<int:pk>/triage/", views.securitythreat_triage, name="securitythreat_triage"),
        path("security/threats/<int:pk>/resolve/", views.securitythreat_resolve, name="securitythreat_resolve"),
    ]
    + crud("security/vulnerabilities", "vulnerabilityfinding")
    + crud("security/incidents", "securityincident")
    + [
        path("security/incidents/<int:pk>/contain/", views.securityincident_contain, name="securityincident_contain"),
        path("security/incidents/<int:pk>/eradicate/", views.securityincident_eradicate, name="securityincident_eradicate"),
        path("security/incidents/<int:pk>/recover/", views.securityincident_recover, name="securityincident_recover"),
        path("security/incidents/<int:pk>/close/", views.securityincident_close, name="securityincident_close"),
        path("security/incidents/<int:pk>/notify-authority/", views.securityincident_notify_authority, name="securityincident_notify_authority"),
        path("security/incidents/<int:pk>/notify-subjects/", views.securityincident_notify_subjects, name="securityincident_notify_subjects"),
    ]
```

**URL-name ledger — 33 names, every one must reverse:**

`security_overview`, `threat_board`, `vulnerability_board`, `breach_clock_board`, `brute_force_board`; then
`<name>_list` / `_create` / `_detail` / `_edit` / `_delete` for each of `ipaccessrule`, `securitythreat`,
`vulnerabilityfinding`, `securityincident` (20); then `securitythreat_triage`, `securitythreat_resolve`,
`securityincident_contain`, `securityincident_eradicate`, `securityincident_recover`,
`securityincident_close`, `securityincident_notify_authority`, `securityincident_notify_subjects` (8).
5 + 20 + 8 = **33**.

## 5. Template contract — 17 files, flat at `templates/core/` (foundation rule 4)

| Path | Kind |
|---|---|
| `templates/core/securitythreat/{list,detail,form}.html` | entity triple |
| `templates/core/ipaccessrule/{list,detail,form}.html` | entity triple |
| `templates/core/vulnerabilityfinding/{list,detail,form}.html` | entity triple |
| `templates/core/securityincident/{list,detail,form}.html` | entity triple |
| `templates/core/securityoverview.html` | standalone page, app root |
| `templates/core/threatboard.html` | standalone page, app root |
| `templates/core/vulnerabilityboard.html` | standalone page, app root |
| `templates/core/breachclock.html` | standalone page, app root |
| `templates/core/bruteforceboard.html` | standalone page, app root |

The page file is the **bare** name — never a flat `securitythreat_list.html`. Every template
`{% extends "base.html" %}`, uses the house classes (`page-header`, `page-title`, `breadcrumb`,
`page-actions`, `card` / `card-body` / `card-header` / `card-title`, `filter-bar`, `table-wrap`, `table`,
`table-actions`, `btn-icon`, `empty-state`, `text-muted`, `fw-600`, `detail-item`) and the lucide icon set
(`data-lucide="…"`). Copy `templates/core/alertrule/list.html` as the list reference and
`templates/core/firingboard.html` as the board reference.
`{% include "partials/pagination.html" %}` goes after every list's table, and any shared sub-block is
`{% include %}`d rather than copy-pasted — `{% extends %}` / `{% include %}` are unaffected by the folder
rule.

**Every list has an Actions column** with all three, unconditionally (none of these four has a status gate
that would justify hiding Edit or Delete): a View button (`data-lucide="eye"`, `btn-icon`), an Edit button
(`data-lucide="pencil"`), and a **POST** delete form with `{% csrf_token %}`, `method="post"`,
`onsubmit="return confirm('…')"` and a `data-lucide="trash-2"` `btn-icon danger` button.

**Every detail has an Actions sidebar** with Edit, a POST delete form with confirm, a Back-to-list link, and
the module's honest-limit line — plus the sibling surfaces the seam implies: the threat detail links its
`alert_event` (**`core:alert_event_detail`**) and its `rate_limit_policy` (**`core:rate_limit_edit` with the
pk — see [RULING] 1**) when set; the incident detail links its `incident` (**`core:incident_detail`**) and its
`primary_threat` (**`core:securitythreat_detail`**) when set; the IP-rule detail lists the threats it
mitigates.

**Filter rules, applied exactly:** string filters compare with `{% if request.GET.status == value %}`;
**FK/pk filters use `|stringformat:"d"`, never `|slugify`**
(`{% if request.GET.service == s.pk|stringformat:"d" %}`); booleans compare against the literal strings
`"True"` / `"False"`; the three-state `notifiable` dropdown compares `request.GET.notifiable` against
`"True"` / `"False"` with a blank `Not decided` option. Every option list comes from the `*_choices` key its
view actually passed (§3.2 — every one of them backs a dropdown), and every dropdown has an "Any …" blank
option plus a Reset link back to the bare list URL.

**Badges are colour-named only**, and `static/css/theme.css` ships exactly six: `badge-info`, `badge-amber`,
`badge-red`, `badge-green`, `badge-muted`, `badge-slate` — there is **no `badge-warning`, `badge-danger` or
`badge-purple`**, and an unstyled string is the L33 defect. Every badge branch has an `{% else %}` fallback
rendering `{{ obj.get_<field>_display }}`. Severity → `info`→`badge-info`, `warning`→`badge-amber`,
`critical`→`badge-red`; the CVSS band → `none`/`low`→`badge-slate`, `medium`→`badge-amber`,
`high`/`critical`→`badge-red`. **`badge-green` appears on no board and on no security register row** (the
zero rule).

**The thirteen DECLINE items are IN the pages, not only in the docstrings** (research §3): in the same voice
0.17 uses on every register page — *this is a register of claims a person wrote. NavERP has no IDS/IPS agent,
no scanner, no WAF, no CAPTCHA, no SIEM client, no log pipeline and no scheduler, so nothing here detects,
blocks, scans, enforces, ships or notifies anything; a row is a record of what somebody reported.* Each board
additionally prints its own specific decline: the breach clock prints that NavERP files nothing with any
authority and tells no data subject anything; the brute-force board prints that it reads
`accounts.LoginAttempt` and adds no 0.18 table and no lockout. `action="block"` on `IpAccessRule` renders as
*"would block"* where the page is describing NavERP rather than the policy.

**The NULL rendering discipline on every page:** `source_ip` NULL → `"—"`; `cvss_score` / `epss_score` NULL
→ `"—"`; `fix_available` NULL → `"—"`; `due_on` NULL → `"no deadline set"` (never today's date);
`expires_at` NULL → `"permanent"`; counts the board cannot justify print the reason, never a bare `0`.

**Empty states are honest, not reassuring** — the standard `.empty-state` block saying what is missing rather
than implying all-clear: no threats → "No threats have been recorded"; no findings → "No vulnerability
findings have been recorded"; no incidents → "No security incidents have been recorded". **None of them says
"secure", "healthy" or "no action needed".**
## 6. Integration contract — the exact edit to every shared file

Every file in this section is **single-writer, surgical `Edit` only, never `Write`** (L43). Re-read each
immediately before editing, and do the wire-up only **after** the app files exist (L12).

**6.1 `apps/core/models/__init__.py`** — immediately after the `from .Monitoring import (...)` block
(currently lines 122-127, ending `)  # noqa: F401`):

```python
from .Security import (  # 0.18 Threat Protection & Security Operations
    IpAccessRule,
    SecurityThreat,
    VulnerabilityFinding,
    SecurityIncident,
)  # noqa: F401
```

**6.2 `apps/core/forms/__init__.py`** — immediately after the `from .Monitoring import (...)` block
(currently lines 95-100):

```python
from .Security import (  # 0.18 Threat Protection & Security Operations
    IpAccessRuleForm,
    SecurityThreatForm,
    VulnerabilityFindingForm,
    SecurityIncidentForm,
)  # noqa: F401
```

**6.3 `apps/core/views/__init__.py`** — immediately after the `from .Monitoring import (...)` block
(currently lines 287-316), **all 33 names** per [RULING] 2:

```python
from .Security import (  # 0.18 Threat Protection & Security Operations
    # boards and the landing page
    security_overview,
    threat_board,
    vulnerability_board,
    breach_clock_board,
**6.4 `apps/core/admin.py`** — four registrations after the 0.17 `IncidentAdmin` block (which currently ends
`admin.py:639`). The admin is the **second** path past every `clean()` rule and a different one: it uses a
plain `ModelForm`, so the refusal messages are what protect it. Add one comment per admin class saying so,
and **do not** add a `save_model()` that re-implements anything the model already refuses.

| Admin | `list_display` | `list_filter` | `search_fields` | `readonly_fields` |
|---|---|---|---|---|
| `SecurityThreatAdmin` | `["title", "threat_type", "severity", "status", "detected_at", "service", "tenant"]` | `["threat_type", "severity", "status", "tenant"]` | `["title", "mitre_technique", "source_ip", "summary", "notes"]` | `["service_label", "resolved_at", "resolved_by", "created_at"]` |
| `IpAccessRuleAdmin` | `["cidr", "direction", "action", "scope", "is_active", "expires_at", "tenant"]` | `["direction", "action", "scope", "source", "is_active", "tenant"]` | `["cidr", "reason", "notes"]` | `["added_by", "added_by_label", "created_at", "updated_at"]` |
| `VulnerabilityFindingAdmin` | `["advisory_id", "title", "severity", "status", "cvss_score", "due_on", "tenant"]` | `["severity", "status", "finding_source", "fix_available", "tenant"]` | `["advisory_id", "title", "package_name", "notes"]` | `["accepted_at", "created_at", "updated_at"]` |
| `SecurityIncidentAdmin` | `["title", "incident_class", "status", "severity", "discovered_at", "is_notifiable", "tenant"]` | `["incident_class", "status", "severity", "is_notifiable", "subject_exemption", "tenant"]` | `["title", "authority_reference", "notifiable_reason", "root_cause"]` | `["owner_label", "contained_at", "eradicated_at", "recovered_at", "closed_at", "authority_notified_at", "subjects_notified", "subjects_notified_at", "created_at", "updated_at"]` |
**6.5 `apps/core/management/commands/seed_core.py`** — add `self._seed_security(tenant)` to `handle()`
**immediately after** `self._seed_monitoring(tenant)` (currently `seed_core.py:129`), inside the per-tenant
loop, and add the `_seed_security(self, tenant)` method after `_seed_monitoring`. **Never
`seed_core --flush` on this shared checkout** — it deletes rows another session may be verifying against.
Plain idempotent re-seeding is safe from both sides.

- **SEEDED — two kinds of row only.** (a) up to two `AlertRule` rows with `category="security"` and an
  **existing** `metric_key` (never a new key — adding one would be growing 0.17's vocabulary, which the seam
  forbids), each with a real bound (`AlertRule.clean()` refuses an active rule with no bound), `is_active`
  set, and `notes` saying plainly that nothing in NavERP evaluates it. A declared threshold is a *policy
  somebody wrote* — exactly what a seeder is allowed to fabricate, the same basis on which 0.17 seeds
  `AlertRule` and 0.16 seeds `BackupJob.frequency`. (b) at most two `VulnerabilityFinding` rows clearly marked
  as **published advisory records entered by hand** — a real `advisory_id`, `finding_source="dependency"`,
  `component=None`, `evidence` saying the row was entered by a person from a published advisory and that
  NavERP ran no scanner and no dependency check, and `notes` saying it is a worked example and not a
  finding about this installation. Never present a seeded row as a scan NavERP performed.
- **NOT SEEDED — and the consequence is intended, so do not "fix" it: zero `SecurityThreat`, zero
  `SecurityIncident`, zero `IpAccessRule`.** A fabricated "we detected a brute-force attack" or "we blocked
  this address" is a **recorded event that did not happen** — the L52 defect, and worse than 0.16's, because a
  security register that lies is actively dangerous. An `IpAccessRule` is a *policy* but it is also a claim
  that an address is denied, and a seeded deny entry is indistinguishable on the page from one a person wrote
  after an incident. **Therefore a fresh seed leaves the threat board, the vulnerability board and the
  breach-clock board with nothing declared, and a naive smoke run reads that as contract drift. It is not
  drift** — it is the boards telling the truth about a system that watches nothing. The smoke script creates
  the rows it needs through the ORM and deletes them in a `finally`.
- **Per-entity guards, never a tenant-wide one** — the documented defect that left everything added to this
  command after the fact unreachable in workspaces that already existed. The `AlertRule` guard is
  **category-scoped**: `if not AlertRule.objects.filter(tenant=tenant, category="security").exists():` —
  0.17's own guard is tenant-wide, so a tenant-wide guard here would skip these two rows forever on a
  workspace that already ran 0.17, while a category-scoped guard creates them on the first run and nothing on
   the second. The `VulnerabilityFinding` guard is
   `if not VulnerabilityFinding.objects.filter(tenant=tenant).exists():`. `get_or_create` wherever a unique
   constraint applies; idempotent on a second run with no duplicate rows. **After the second run, print the
   counts of the three non-seeded models** so the operator can see the zero is deliberate.
- **Nothing in 0.18 writes to `accounts`, `tenants` or `procurement`.** The seeder creates no `LoginAttempt`
  (an attempt is evidence of an event); the brute-force board's source rows come from `seed_accounts`.

**6.6 `temp/audit_integrity.py`** — add `SecurityThreat`, `SecurityIncident` and `IpAccessRule` to
`KNOWN_OK` in `check_seeders` (currently lines 219-244), **each with its reason printed** — 0.17's
`AlertEvent` / `Incident` entries are the precedent, and an unexplained exemption is indistinguishable from
an oversight, which is the exact thing that check exists to catch. Re-read the file immediately before
editing; it is shared.
**6.7 `apps/core/navigation.py`** — add one `LIVE_LINKS["0.18"]` block **adjacent to `LIVE_LINKS["0.17"]`**
(currently lines 250-266), i.e. immediately after that block's closing `},`:

```python
    # 0.18 Threat Protection & Security Operations. The five bullet keys below are copied
    # BYTE-IDENTICALLY from `NavERP.md` section 0.18 (lines 244-248); `parse_catalog()` matches them by
    # exact string, so a one-character drift renders a fully built page as a "soon" roadmap pill with no
    # error anywhere — a silent failure behind a green build. Bullets 4 and 5 are PARTIAL, and the
    # comments say which half: b4's CAPTCHA and WAF are DECLINED (no `captcha` library in
    # `requirements.txt`, no WAF in front of the app); b5's "real-time" alerting and SIEM/SOC export are
    # DECLINED (no scheduler, no event bus, no exporter). The sidebar must never advertise a capability
    # the pages themselves decline — a pill that promises a WAF the app cannot run is the 0.16 lie one
    # level up.
    "0.18": {
        "Intrusion Detection & Prevention": "core:ipaccessrule_list",         # bullet 1 - the allow/deny lists, verbatim
        "Vulnerability & Patch Management": "core:vulnerabilityfinding_list",  # bullet 2
        "Security Incident Response": "core:securityincident_list",          # bullet 3
        "Bot & Abuse Protection": "core:securitythreat_list",                # bullet 4 - CAPTCHA and WAF DECLINED
        "Security Alerting & SIEM": "core:threat_board",                     # bullet 5 - through the 0.17 seam
        # Extra built pages that are NOT NavERP.md bullets. `resolve_nav` appends these AFTER the
        # bullets, so they read as operational leaves rather than as more promised features.
        #
        # Every label must resolve to a DISTINCT page, or the sidebar shows several labels over one page
        # and the active-link highlight lights all of them at once. 0.17 deleted two such duplicate
        # extras for exactly this reason.
        "Vulnerability Board": "core:vulnerability_board",                   # extra (the aging / overdue board)
        "Breach Clock": "core:breach_clock_board",                           # extra (the 72h Art. 33 clock)
        "Brute-Force Correlation": "core:brute_force_board",                 # extra (reads accounts.LoginAttempt)
        "Security Overview": "core:security_overview",                       # extra (landing page)
    },
```

**Two gates on this block, both programmatic, neither by eye:**

1. **Byte-identical bullet keys.** The five keys are **copied, not retyped** — take them from `NavERP.md`
   lines 244-248 character for character, including the `&` and the spacing around it, and **diff them
   against that file before committing**. A one-character drift is invisible in review and fatal in
   production: the page is fully built, the sidebar renders it as a "soon" roadmap pill, and nothing anywhere
   reports an error.
2. **Nine labels in, nine DISTINCT targets out.** `resolve_nav` renders every label in the dict, so two
   labels pointing at one page light the active-link highlight twice. Assert before committing:
   `len(set(LIVE_LINKS["0.18"].values())) == len(LIVE_LINKS["0.18"]) == 9`, and that all nine values reverse.
**6.8 The migration** — generate as the **last backend step**, after all four model files exist and are
re-exported, so Django auto-depends on anything a peer landed in the meantime. Check first that no peer has
added a model to `core` in this checkout, or you will sweep their model into your migration. **Expected
content: four `CreateModel`s, ZERO `AddField`** (no existing model is touched — that is the whole point of
the RateLimitPolicy ruling and the 0.17-seam ruling), the auto-generated
`SecurityIncident.affected_services` through table, `SecurityThreat.mitigated_by` → `IpAccessRule` (an FK
between two new models, which is why the class order is `IpAccessRule` first), and the list-ordering indexes
named exactly as pinned in §1. **If the generated migration contains an `AddField` on a 0.13 or 0.17 table,
STOP: something was edited that must not have been.** Then `migrate`, then `makemigrations --check
--dry-run` again and confirm **"No changes detected"** — a non-empty result means a model was edited after
the migration was generated.

---

## 7. Verification gate — what must be PROVEN before 0.18 is called done

All from the repo root: `venv\Scripts\python.exe manage.py …`. In this order.

1. **`manage.py check`** — zero issues.
2. **`makemigrations --check --dry-run`** — **"No changes detected"**.
3. **`migrate`** — applies `core.0016_*` cleanly, one leaf node.
4. **`seed_core` twice** (never `--flush`). The second run adds **no** duplicate rows and still reports
   **zero `SecurityThreat`**, **zero `SecurityIncident`**, **zero `IpAccessRule`** — that zero is the L52
   ruling working, not a failure.
5. **`venv\Scripts\python.exe temp\audit_integrity.py`** — all six checks PASS: 1 catalog, 2 every migration
   applied, 3 every route name reverses, 4 every template renders, 5 every `LIVE_LINKS` target reverses
   (**a failure in check 5 means a nav label drifted**), 6 seeder coverage with the three new `KNOWN_OK`
   exemptions printing their reasons.
6. **Reuse-by-reference identity:** assert `SecurityThreat.SEVERITY_CHOICES is AlertRule.SEVERITY_CHOICES`,
   `SecurityIncident.SEVERITY_CHOICES is AlertRule.SEVERITY_CHOICES`, and
   `VulnerabilityFinding.SCAN_FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES` — **identity, not
   equality**. A pasted copy is the defect.
7. **`regulatory_deadline` is a property, not a field** — assert it is absent from
   `SecurityIncident._meta.get_fields()` and that no form field exists for it. Also assert
   `VulnerabilityFinding.severity` is NOT `AlertRule.SEVERITY_CHOICES` (the CVSS band is the one deliberate
   divergence).
8. **Smoke pass (`qa-smoke-tester`) asserting CONTENT, not just status (L8).** Render as `admin_acme` and
   assert a real string from each page — the entity's own name, `str(obj)`, or a seeded title — **plus a
   `SECURITY_NOTES` line** — on all **33 routes**: 4 lists, 4 details, 4 create forms, 4 edit forms,
   5 boards/overview, 8 actions (via POST), 4 delete redirects. **A mismatched context var returns 200 and
   renders blank**, so a status-only check passes a broken page. The smoke script creates the
   `SecurityThreat` / `SecurityIncident` rows it needs through the ORM and deletes them in a `finally` (the
   seeder deliberately created none). Run the client with `Client(raise_request_exception=False)` so one pass
   collects **all** 500s instead of aborting on the first.
9. **Junk-param list** on all four list views: `?status=nope`, `?severity=not_a_band`, `?service=abc`,
   `?service=0`, `?service=999999999999999999999`, `?fix=maybe`, `?notifiable=maybe`, `?type=nope`,
   `?source=maybe`, `?exemption=maybe`, `?waf=maybe`, `?defense=maybe` — each must be **ignored** and return
   the **unfiltered row count** (200, same rows), never a 500 and never a silently emptied register (see
   [RULING] 4 — `crud_list` already does this; the views must not add a second parser).
10. **Page 2** on each of the four lists (seed enough rows to paginate, or assert `page_obj` exists and
    `?page=2` resolves) — the prev/next guards hold and no template 500s.
11. **Cross-tenant IDOR → 404:** log in as the second tenant's admin and request every detail, edit, delete
    and action URL for a row owned by the first tenant. All **404** (the tenant filter is inside
    `get_object_or_404`), and each of the eight POST actions refuses as well.
**Commit discipline for the whole build:** one file per commit, explicit paths,
`git add '<path>'; git commit -m '<specific message about that one file>'` — PowerShell `;` separators,
never `&&`. **Never `git push`, at any step.** Never stage `templates/projects/reporting/*.html` or the
untracked `.commandcode/`, `.gemini/`, `.workbuddy-ai/`, `.zcode/` directories — they belong to the other
session (L45). If a build step appears to need one of them, stop and re-plan rather than staging it.

---

## 8. The build order (one thing at a time — never interleave)

1. **Build `apps/core/models/Security.py`** in the class order `IpAccessRule` → `SecurityThreat` →
   `VulnerabilityFinding` → `SecurityIncident`. Commit that one file.
2. **Build `apps/core/forms/Security.py`** — four forms. Commit.
3. **Build `apps/core/views/Security.py`** — 33 views, `SECURITY_NOTES` first. Commit.
4. **Build the 17 templates**, four entity triples in the order above, then the five standalone pages.
   Commit each file separately.
5. **Integrate** — verify every expected file actually landed *before* wiring anything, then do §6.1-§6.8 in
   order, one file per commit, then `makemigrations` → `migrate` → `seed_core` **twice** → `manage.py check`.
6. **Smoke** against §7, then Phase 4.

**Not in this contract's scope and not touched by the build:** `settings.py` (no new app, no new setting),
`NavERP.md` / `NavERP-ERD.md` / `README.md` (Phase 7), `apps/core/tests/conftest.py` (Phase 6, append-only),
`.claude/skills/`. For Phase 7, note that L36 §2 requires reconciling **both** ERD rows in the same pass —
0.18's row and procurement 6.17's `AuditSeal` row — or the doc contradicts the code.

---

*Contract frozen 2026-09-26. Sources: research `dacf5027`, plan `a0494a77`, BASE `64780680`. Every pinned
name verified against the as-built source with grep; the name that did not exist (`core:rate_limit_detail`)
and the two miscounts are recorded as [RULING]s above rather than papered over.*

12. **Method check:** `GET` on all four delete URLs and all eight action URLs returns **405** (the
    `@require_POST` is above the role gate), and an unauthenticated request redirects to login. A non-admin
    member is refused on every one of the 33 routes.
13. **Nav distinctness gate:** `len(set(LIVE_LINKS["0.18"].values())) == 9` and all nine reverse (§6.7).
14. **Honest-claim sweep:** read every one of the 17 templates against the one question that matters most —
    *does any page imply that NavERP detected, blocked, scanned, enforced or notified anything?* A page
    headed "Blocked IP" when nothing blocks is the 0.16 lie; "Recorded block — requires an enforcing layer"
    is the same fact told honestly. Check this **before Phase 4 starts**, so the six reviewers spend their
    passes on quality rather than on a page that lies.


   `apps/core/tests/test_navigation_active.py` and `temp/audit_integrity.py` check 5 both walk `LIVE_LINKS`,
   so the active-link logic must light **exactly one** label per page.




