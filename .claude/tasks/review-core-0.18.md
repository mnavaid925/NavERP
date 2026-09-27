# Review — Module 0 0.18 Threat Protection & Security Operations

**Range:** `647806805d0a07dec2921e2d3293dcc342005d64…HEAD` (`apps/core`, `templates/core` — 28 files, +4,747)
**Contract:** `.claude/tasks/contract-core-0.18.md` · **Six serial reviewers, one at a time.**

This file is the record of the review. Findings are appended as each reviewer reports, then deduped,
sorted Critical → Important → Minor and given IDs. **No finding lives only in a transcript.**

---

## Pass 1 — `code-reviewer`

**Verified clean (checked, not assumed):** `manage.py check` 0 issues; no `core` migration drift; all
73 distinct `{% url %}` names across the 17 templates reverse (L7 clear); 33 view functions exported
and 33 routes registered; every filter dropdown has a backing `filters=[…]` row ([RULING] 3 honoured —
no orphaned `*_choices`); all four hard boundaries hold (`Integration.py` untouched; zero `AddField`
in `core.0016`; no second alert table/incident lifecycle/board; `SEVERITY_CHOICES` identity `True` for
both models); `regulatory_deadline` is a property; `LIVE_LINKS` keys byte-identical over 9 distinct
targets; the seeder creates zero threats/incidents/rules.

### Critical

**C1 — `status="resolved"` on the threat form is a hard 500, on a dropdown the build itself renders.**
`models/Security.py:374-377` keys two `ValidationError`s on `resolved_at` / `resolved_by`; L22 keeps
both off the form (`forms/Security.py:67-71`), and `templates/core/securitythreat/form.html:36` renders
`form.status` with the full `STATUS_CHOICES` — including "Resolved". Django 5.1's `ModelForm._post_clean`
→ `_update_errors` → `add_error` **raises** for a key with no matching field rather than dropping it.
Proven: `SecurityThreatForm(data={… "status": "resolved"}).is_valid()` → `ValueError:
'SecurityThreatForm' has no field named 'resolved_at'`. A tenant admin picking "Resolved" on
`core:securitythreat_create`/`_edit` gets a 500 on a write that never started. Swept all four models —
`IpAccessRule`, `VulnerabilityFinding` and `SecurityIncident` key only fields that exist on their forms;
**`SecurityThreat` is the only one that does not.**
*Fix:* key both messages on `status` (a real form field), or drop `"resolved"` from the form's status
widget. Add a test that POSTs every `STATUS_CHOICES` value.

**C2 — System-set stamps are admin-editable in two admins.** `IpAccessRuleAdmin` (`admin.py:655-656`)
declares **no** `readonly_fields`, so `added_by`, `added_by_label`, `created_at`, `updated_at` are
typeable — contradicting the block header at `admin.py:648-651` and contract §6.4.
`SecurityIncidentAdmin` (`admin.py:718-719`) omits `subjects_notified`, so an admin can stamp Art. 34
"told" with no `subjects_notified_at` and without the `subject_exemption` guard the POST-only action
enforces.
*Fix:* add both readonly lists.

### Important

- **I1 — The incident detail's "Record containment" button is shown exactly when the view refuses it.**
  `templates/core/securityincident/detail.html:172` → `{% if obj.status == "detected" or obj.contained_at %}`;
  the view (`views/Security.py:738-747`) refuses when `status == "detected"`. The condition is inverted.
- **I2 / I4 / I8 — the guards, the buttons and the prose live in three places and only the view is
  kept honest.** One root cause: a rule is duplicated between `views/Security.py`, the templates and a
  docstring, and the copies disagree.
- **I5 — one rule, four copies, already disagreeing at the boundary.**

### Minor

- **M2 — Dead context keys.** `state_counts` / `severity_counts` / `type_counts` (`views/Security.py:1045-1049`)
  and `band_counts` / `status_counts` / `source_counts` (`:1098-1102`), plus the `_count_list` helper,
  are built and named in the boards' `{% comment %}` headers but never rendered — both templates render
  only the `*_rows` tuples.
- **M3 — `is_notifiable`'s three-state widget shows "Not yet decided" twice.** `forms/Security.py:201-207`
  passes both `("", "Not yet decided")` and `("unknown", "Not yet decided")`, and
  `NullBooleanField.to_python` maps both to `None`. Also `field.widget = field.field.widget` (`:208`) is
  a no-op — `BoundField.widget` is a property over `.field`.
- **M4 — the honest `action_display` reaches the admin but not the pages.** `models/Security.py:206-214`
  explains why it exists; `admin.py:657` uses it, but `templates/core/ipaccessrule/list.html:84` and
  `detail.html:40` both print bare `{{ obj.get_action_display }}` — exactly the "working control"
  misread the property was written to prevent.
- **M5 — "Breach" labels count every incident class.** `breach_clock_board` and `security_overview`
  frame Art. 33 (a personal-data-breach duty) as "Open breaches", but `open_qs` includes
  `denial_of_service`, `policy_violation`, `malware`, `phishing` (`views/Security.py:1142`, `:977`).
- **M6 — the seeder hardcodes the SLA.** `seed_core.py:1209-1210` writes `first_seen + 90 days` as a
  literal instead of `REMEDIATION_SLA_DAYS["medium"]`, so the seeded row silently disagrees with the
  policy the page prints beside it if the constant moves.
- **M7 — two lifecycle guards ignore the declared settled set.** `securityincident_contain` (`:738`)
  refuses only `status == "detected"`, so a `false_positive` incident can be stamped `contained_at`;
  `securityincident_close` (`:846`) will overwrite `status="false_positive"` with `"closed"`.
  `INCIDENT_SETTLED` is declared at `:93` and consulted by neither.
- **M8 — four unused imports.** `models/Security.py:66-67`: `RateLimitPolicy`, `AlertEvent`, `Incident`,
  `ServiceComponent` — every FK is declared by string label, so only `AlertRule` and `SyncSchedule` are
  used. Contract-pinned, so the fix is `# noqa: F401` or an amended contract, not a deletion.

### Reviewer judgement

A staff engineer would approve the **architecture** and reject the **ship state**. The boundary
discipline is the best in this repo — four hard rules held, `is`-identity reuse verified by probe, the
missing `rate_limit_detail` avoided, the orphaned-choices defect designed out rather than papered over,
the L52 ruling honoured without a single seeded breach, 73/73 URL names reversing. What stops it
shipping is that three claims the code makes in prose are false, and one is a 500 on the module's own
form. **Fix C1 first**, then C2, then I1's inverted guard.

---

## Pass 2 — `security-reviewer`

> **Run in the MAIN SESSION, not by a sub-agent.** The dedicated `security-reviewer` sub-agent
> failed twice — once on an auth error, once on a connection refusal after ~146 iterations of work.
> Rather than lose the pass, the main session ran the same hunt as an executable probe
> (`temp/probe_018_security.py`) that *attempts* each attack rather than reading for it. Every
> result below is a probe observation, not an inference. The probe is read-only apart from
> throwaway rows, which it deletes in a `finally`; the one crashed first run left orphans, and a
> follow-up `temp/probe_018_cleanup.py` removed them and re-verified the L52 zero-rule.

### What the probe PROVED clean (these are the important results)

| Hunt | Method | Result |
|---|---|---|
| Privilege escalation | member GET over 17 admin surfaces | **no 200s** — every surface refused |
| Privilege escalation | member POST over 10 lifecycle/delete actions | **all refused** |
| Cross-tenant IDOR | Globex rows fetched as `admin_acme` — 3 lists, 4 details, 7 actions | **no leaks**; every detail/action **404**; **rows unmutated** after the attempts |
| Mass assignment | every system-set stamp checked against all 4 forms | **clean** on all four |
| XSS | `\|safe` / `mark_safe` scan over all 17 templates | **none** |
| CSRF | every `method="post"` form checked for `{% csrf_token %}` | **none missing** |
| Secret leakage | `key_hash` / `.prefix` / `plaintext` / `password` scan | **none** — 0.18 links `ApiCredential` by FK and never renders a secret |
| Out-of-order transitions | contain-before-triage | **refused**, `contained_at` stayed `None` |
| Out-of-order transitions | close-while-notifiability-undecided | **refused**, status unchanged |
| Double-fire | second contain POST | stamp **identical** — no rewrite |

### Security findings

- **S1 (Important) — `securityincident_contain` will stamp a `false_positive` incident.**
  Confirmed by probe, not inferred: a `SecurityIncident(status="false_positive")` accepted
  `POST /core/security/incidents/<pk>/contain/` and had `contained_at` written. The guard at
  `views/Security.py:738` refuses only `status == "detected"`, so a closed decision is reversible
  by action. This is the same root cause as the code-reviewer's **M7**; the probe confirms the
  *contain* half reproduces. (`close`-on-a-`false_positive` did **not** reproduce — that half of
  M7 is already safe.) **Fix:** consult the `INCIDENT_SETTLED` set the module already declares at
  `views/Security.py:93` and that neither guard currently reads.

- **S2 (Minor) — the documented M2M admin-path gap is real but correctly scoped.**
  `SecurityIncident.affected_services` is an M2M, and `TenantConsistentMixin` walks only
  `ForeignKey`/`OneToOneField`, so it is not tenant-checked on the **admin** save path. This is
  inherited from 0.16/0.17 and documented in the model docstring and the SKILL. Blast radius: an
  admin user could attach another tenant's `ServiceComponent` to an incident via the changelist.
  **Do not** fix by editing `TenantModelForm` — it would break committed tests in three apps. The
  right fix, if the owner wants one, is a `SecurityIncidentAdmin.formfield_for_foreignkey`
  override scoped to this one field.

- **Duplicates, not re-reported:** the threat-form `ValueError` (code-reviewer **C1**) and the two
  admin `readonly_fields` gaps (**C2**) are both **also** security findings — C1 is a
  availability defect reachable by any tenant admin, and C2 lets a staff user stamp
  `subjects_notified` and `added_by` without the one-writer rule. They are counted once, under
  the code-reviewer's IDs, and the fixer must treat them as Critical.

### Security verdict

**The authorisation and isolation posture is sound, and that is not a low bar here.** Zero
privilege-escalation paths, zero cross-tenant leaks, zero mass-assignment surfaces, zero XSS sinks,
zero CSRF gaps, zero secret exposure, and the illegal-transition guards hold for every case probed
*except* the one in S1. The module that exists to protect the workspace does not itself leak it.
**No Critical security finding.** S1 is the one item to fix before ship.

---
