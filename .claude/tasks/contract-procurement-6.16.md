# Contract — Procurement 6.16 Supplier Performance & Evaluation (`apps/procurement`)

**Frozen 2026-09-05. Source of truth: `.claude/tasks/todo.md` §"Procurement 6.16" (lines 1600–2271).**
Where the plan and `.claude/tasks/research-procurement-6.16.md` disagree, **the plan wins** — see
§9 *Discrepancies resolved*. Anything the plan left to the builder is decided here and marked
**(contract decision)**.

App EXISTS (6.1–6.15 built) → this pass **extends**. No scaffold, no `settings.py`, no
`config/urls.py` edit. Migration **`0026` and nothing else**.

Sub-package name (all four layers): **`SupplierPerformanceEvaluation`**.
Template sub-module slug: **`performance`**. Test/function prefix: **`supplierperf`**.

---

## 0. Verified spine (grepped this pass — L28: the ERD is intent, the grep is truth)

| Thing | Verified at | What 6.16 uses |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5` — `tenant`, `kind`, `name`, `tax_id`, `created_at` | supplier master, FK'd by string |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` — `ROLE_CHOICES` includes `vendor`, `supplier`; reverse accessor on Party is **`roles`** | supplier queryset filter |
| `core.Tenant` | `apps/core/models/Tenant.py` | every model's `tenant` FK (via `TenantOwned`) |
| `scm.SupplierScorecard` | `apps/scm/models/SupplierRelationshipManagement/SupplierScorecards.py:11` | period container — **FK'd, never re-declared** |
| `scm.SupplierProfile` | `.../SupplierProfiles.py:12` — `TIER_CHOICES = strategic\|preferred\|approved\|transactional`, fields `party` (OneToOne), `tier`, `category` | tier resolver + benchmark cohort |
| `scm.SupplierRiskAssessment` | `.../SupplierRiskAssessments.py:10` — `party`, `assessment_date`, `status`, `risk_index` Decimal(4,2) `editable=False` | benchmark quadrant's second axis |
| `procurement.VendorSuspension` | `apps/procurement/models/VendorManagement/VendorSuspensions.py:27` — `TenantNumbered` [VSU-], `supplier` FK `core.Party` PROTECT, `starts_on`, `ends_on`, `status` `requested\|active\|rejected\|lifted` | PIP escalation target + `suspension_incidents` resolver |
| `procurement.ProcurementAlert` | `apps/procurement/models/DashboardPortal/ProcurementAlerts.py:26` — `TenantOwned`, `KIND_CHOICES` `deadline\|approval\|delivery\|task\|contract`, `SEVERITY_CHOICES` `info\|warning\|critical`, `link_url` **internal path only** | band-crossing alerts — **no new alert table** |
| `apps/core/crud.py` | `crud_list` → `object_list` + `page_obj` + `q`; `crud_detail`/`crud_edit` → `obj`; `crud_create`/`crud_edit` → `form` + `is_edit`; `filters=` tuples are `(get_param, orm_lookup, is_int)`; both write paths already pass `request.FILES` | every CRUD view |
| `apps/core/utils.write_audit_log` | `write_audit_log(user, obj, action, changes=None, tenant=None)` | every hand-rolled save path |
| `apps/core/decorators.tenant_admin_required` | raises `PermissionDenied` unless `is_superuser` or `is_tenant_admin`; wraps `login_required` | `supplierevaluation_generate`, `improvementplan_close` |
| `apps/core/forms._common` | `ALLOWED_DOC_EXTENSIONS` (set), `MAX_UPLOAD_BYTES = 20 * 1024 * 1024` | `SupplierImprovementPlanForm.clean_evidence()` |
| `apps/procurement/models/_base.py` | `TenantOwned` (tenant/created_at/updated_at, `related_name="+"`), `TenantNumbered` (+`number` CharField(20) `editable=False`, retry-on-collision `save()`), `ZERO`, `MAX_Q2`, `q2()`; star-import already re-exports `models`, `Decimal`, `settings`, `ValidationError`, `Min/MaxValueValidator`, `Q`, `Sum`, `F`, `transaction`, `timezone` | all four models |
| `apps/procurement/forms/_common.py` | `TenantModelForm`, `TenantUniqueMixin`, `_reject_foreign(form, cleaned, names)`, `forms`, `ValidationError` | all four forms |
| `apps/procurement/views/_common.py` | `crud_*`, `login_required`, `require_POST`, `tenant_admin_required`, `messages`, `redirect`, `render`, `get_object_or_404`, `timezone`, `write_audit_log` | all views |
| Latest migration on disk | `0025_remove_budgetmapping_prc_bmap_tnt_active_idx_and_more.py` | next is `0026` |

**Names free (grepped, zero hits anywhere in `apps/`):** `SupplierKpi`, `SupplierKpiScore`,
`SupplierFeedback`, `SupplierImprovementPlan`. **Prefixes free:** `SKP`, `SFB`, `SIP`.
**Index-name prefixes free:** `prc_skp_`, `prc_sks_`, `prc_sfb_`, `prc_sip_`.

### `scm.SupplierScorecard`, pinned as-built (this is what 6.16 writes into)

```
NUMBER_PREFIX = "SCR"                       # TenantNumbered
STATUS_CHOICES = [("draft","Draft"), ("published","Published"), ("archived","Archived")]
WEIGHTS        = {"delivery":35, "quality":35, "price":15, "responsiveness":15}
_SCORE_VALIDATORS = [MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))]

party                = FK("core.Party", CASCADE, related_name="scm_scorecards")
period_start         = DateField()
period_end           = DateField()
status               = CharField(12, choices=STATUS_CHOICES, default="draft")
delivery_score       = DecimalField(5, 2, null=True, blank=True, validators=_SCORE_VALIDATORS)
quality_score        = DecimalField(5, 2, null=True, blank=True, validators=_SCORE_VALIDATORS)
price_score          = DecimalField(5, 2, null=True, blank=True, validators=_SCORE_VALIDATORS)
responsiveness_score = DecimalField(5, 2, null=True, blank=True, validators=_SCORE_VALIDATORS)
overall_score        = DecimalField(5, 2, null=True, blank=True, editable=False)
grade                = CharField(2, blank=True, editable=False)      # A/B/C/D/F via _grade_for()
manual_override      = BooleanField(default=False)
signal_summary       = TextField(blank=True, editable=False)
notes                = TextField(blank=True)
Meta.ordering = ["-period_end", "-id"];  unique_together = ("tenant", "number")
```

* `recompute_overall(self, save=True)` — weighted blend of whichever of the four dimensions are
  non-`None`, **re-weighted over the present ones**, quantized to `0.01`; sets `grade` via
  `_grade_for` (>=90 A, >=75 B, >=60 C, >=40 D, else F); all-`None` → `overall_score=None`,
  `grade=""`. **Writes only when `(overall_score, grade)` actually changed**, via
  `save(update_fields=["overall_score","grade","updated_at"])`. 6.16 calls it with the default
  `save=True` at the end of generate.
* `recompute_from_signals(self, save=True)` — **returns immediately when `manual_override` is
  truthy**. This is the whole mechanism behind the option-(a) hand-over below.
* SCM routes that exist and may be linked to: `scm:scorecard_list`, `scm:scorecard_create`,
  `scm:scorecard_detail`, `scm:scorecard_edit`, `scm:scorecard_delete`, `scm:scorecard_recompute`,
  `scm:scorecard_publish`.

---

## 1. Models

All four live in `apps/procurement/models/SupplierPerformanceEvaluation/`.
Every module starts `from apps.procurement.models._base import *  # noqa: F401,F403`.
**Imports are ABSOLUTE.** Sibling-app reads (`scm`, `core`) happen **inside** the function that
needs them (the `CostForecasts.py` precedent) — never at module top.

Package `__init__.py` files needed (each its own commit, empty except the models one which is
empty too — the re-export block lives in `models/__init__.py`, added at Integrate):
`models/SupplierPerformanceEvaluation/__init__.py`, `forms/.../__init__.py`,
`views/.../__init__.py`, `urls/.../__init__.py`.

---

### 1.1 `SupplierKpi` — `models/SupplierPerformanceEvaluation/SupplierKpis.py`

Base **`TenantNumbered`** · `NUMBER_PREFIX = "SKP"` · `verbose_name = "Supplier KPI"`,
`verbose_name_plural = "Supplier KPIs"` **(contract decision)**.

#### CHOICES constants (module-level, re-exported through the class as `SupplierKpi.X_CHOICES` — declare them **on the class**, mirroring `VendorSuspension`) 

```python
CATEGORY_CHOICES = [
    ("delivery", "Delivery"), ("quality", "Quality"), ("cost", "Cost"),
    ("service", "Service"), ("compliance", "Compliance"), ("esg", "ESG"),
    ("innovation", "Innovation"), ("risk", "Risk"),
]
UNIT_CHOICES = [
    ("pct", "Percent (%)"), ("days", "Days"), ("count", "Count"),
    ("ppm", "Parts per million"), ("money", "Money"), ("score", "Score (0-100)"),
    ("ratio", "Ratio"),
]
DIRECTION_CHOICES = [
    ("higher_is_better", "Higher is better"), ("lower_is_better", "Lower is better"),
]
SOURCE_CHOICES = [
    ("derived", "Derived from transactions"), ("survey", "360 survey"), ("manual", "Manual entry"),
]
# CLOSED registry — one key per resolver that exists in apps/procurement/performance.py.
# NEVER add a key without a reviewed resolver (the scm.KpiTarget.metric discipline).
DERIVED_METRIC_CHOICES = [
    ("otd", "On-time delivery %"),
    ("otif", "On-time in-full (OTIF) %"),
    ("defect_rate", "Defect / reject rate %"),
    ("ncr_rate", "Discrepancy (NCR) rate %"),
    ("rtv_rate", "Return-to-vendor rate %"),
    ("invoice_accuracy", "Invoice accuracy %"),
    ("dispute_rate", "Dispute rate %"),
    ("dispute_days", "Mean days to resolve a dispute"),
    ("promise_adherence", "Delivery-promise adherence %"),
    ("backorder_rate", "Backorder rate %"),
    ("po_change_rate", "PO change rate %"),
    ("price_competitiveness", "Price competitiveness %"),
    ("quote_turnaround", "Quote turnaround days"),
    ("suspension_incidents", "Suspension incidents"),
]
SCORING_CHOICES = [
    ("band", "Band (ok / warning / critical)"), ("linear", "Linear between critical and target"),
    ("direct", "Value is the score"),
]
DIMENSION_CHOICES = [
    ("delivery", "Delivery"), ("quality", "Quality"),
    ("price", "Price"), ("responsiveness", "Responsiveness"),
]
APPLIES_CHOICES = [("all", "All suppliers"), ("tier", "One tier only")]
# LOCAL mirror. SOURCE OF TRUTH: scm.SupplierProfile.TIER_CHOICES — do NOT import scm into a
# model module just to mirror four strings (plan, line 1708).
TIER_CHOICES = [
    ("strategic", "Strategic"), ("preferred", "Preferred"),
    ("approved", "Approved"), ("transactional", "Transactional"),
]
FREQUENCY_CHOICES = [
    ("monthly", "Monthly"), ("quarterly", "Quarterly"),
    ("semiannual", "Semi-annual"), ("annual", "Annual"),
]
```

#### Fields, in declaration order

| # | Field | Definition |
|---|---|---|
| 1 | `code` | `CharField(max_length=32, help_text="Master identifier used to roll this KPI up across scorecards, e.g. OTIF-01")` |
| 2 | `name` | `CharField(max_length=160)` |
| 3 | `description` | `TextField(blank=True)` |
| 4 | `category` | `CharField(max_length=16, choices=CATEGORY_CHOICES, default="delivery")` |
| 5 | `unit` | `CharField(max_length=10, choices=UNIT_CHOICES, default="pct")` |
| 6 | `direction` | `CharField(max_length=16, choices=DIRECTION_CHOICES, default="higher_is_better")` |
| 7 | `source` | `CharField(max_length=8, choices=SOURCE_CHOICES, default="manual")` |
| 8 | `derived_metric` | `CharField(max_length=24, choices=DERIVED_METRIC_CHOICES, blank=True, help_text="Required when the source is derived; must be blank otherwise. The registry is CLOSED — a key here is a promise that a reviewed resolver exists for it")` |
| 9 | `weight` | `PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)], help_text="Relative weight in the composite. Weights are re-weighted over the KPIs actually scored")` |
| 10 | `target_value` | `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)` |
| 11 | `warning_threshold` | `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)` |
| 12 | `critical_threshold` | `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)` |
| 13 | `scoring_method` | `CharField(max_length=8, choices=SCORING_CHOICES, default="band")` |
| 14 | `maps_to_dimension` | `CharField(max_length=16, choices=DIMENSION_CHOICES, blank=True, help_text="Which scm.SupplierScorecard column this KPI feeds. Blank = feeds none")` |
| 15 | `applies_to` | `CharField(max_length=8, choices=APPLIES_CHOICES, default="all")` |
| 16 | `applies_to_tier` | `CharField(max_length=16, choices=TIER_CHOICES, blank=True, help_text="Required when 'applies to' is one tier; matched against scm.SupplierProfile.tier")` |
| 17 | `review_frequency` | `CharField(max_length=12, choices=FREQUENCY_CHOICES, default="quarterly", help_text="The intended cadence. Stored only — nothing schedules off it yet; scorecards are generated on demand")` |
| 18 | `industry_benchmark_value` | `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Hand-entered reference figure — there is no external benchmark feed in this system")` |
| 19 | `owner` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="procurement_supplier_kpis", help_text="The person answerable for this number")` |
| 20 | `display_order` | `PositiveSmallIntegerField(default=100)` |
| 21 | `is_active` | `BooleanField(default=True, help_text="Retire a KPI by deactivating it — never delete it out from under measured history")` |
| 22 | `notes` | `TextField(blank=True)` |

Inherited: `tenant`, `created_at`, `updated_at`, `number`.

#### Meta

```python
ordering = ["display_order", "code"]
unique_together = (("tenant", "code"), ("tenant", "number"))
indexes = [
    models.Index(fields=["tenant", "is_active"], name="prc_skp_tnt_active_idx"),
    models.Index(fields=["tenant", "category"],  name="prc_skp_tnt_cat_idx"),
    models.Index(fields=["tenant", "source"],    name="prc_skp_tnt_source_idx"),
]
verbose_name = "Supplier KPI"
verbose_name_plural = "Supplier KPIs"
```

#### Methods

| Signature | Contract |
|---|---|
| `__str__(self)` | `f"{self.code} · {self.name}"` **(contract decision — `code` is the master identifier, so it leads)** |
| `clean(self)` | `super().clean()`, collect into `errors = {}`, `raise ValidationError(errors)` at the end. Three rules — see below. |
| `score_and_band(self, measured_value)` | `-> (Decimal \| None, str)`. See the pinned algorithm below. |

**`clean()` rule 1 — band ordering by direction** (ported from `scm.KpiTarget.clean()`): build
`bands = [(field, value) for field, value in (("target_value", …), ("warning_threshold", …),
("critical_threshold", …)) if value is not None]`; `higher_is_better` ⇒ each successive set value
must be `<=` its predecessor (`target >= warning >= critical`); `lower_is_better` ⇒ each must be
`>=` its predecessor (`target <= warning <= critical`). **Only the values that are not `None` take
part.** Error key = the offending field; message names both bands
(e.g. `"The warning threshold must not be above the target for a higher-is-better KPI."`)
**(contract decision on wording)**.

**`clean()` rule 2 — the derived conjunction**: `source == "derived"` ⇒ `derived_metric` required
(`errors["derived_metric"] = "A derived KPI has to say which metric computes it."`);
`source != "derived"` ⇒ `derived_metric` must be blank
(`"Only a derived KPI carries a metric key — clear it."`).

**`clean()` rule 3 — the tier conjunction**: `applies_to == "tier"` ⇒ `applies_to_tier` required;
`applies_to == "all"` ⇒ `applies_to_tier` must be blank.

**`score_and_band(measured_value)` — the ONE scale (contract decision on the arithmetic; the plan
pins only the signature).** Generate, the manual edit form and the tests all band through this.

```
0.  measured_value is None                      -> (None, "unknown")
1.  v = Decimal(measured_value)
2.  BAND (independent of scoring_method; uses only thresholds that are set)
    higher_is_better:  v <  critical            -> "critical"
                       v <  warning             -> "warning"
                       (warning or critical set)-> "ok"
                       neither set              -> "unknown"
    lower_is_better:   v >  critical            -> "critical"
                       v >  warning             -> "warning"
                       (warning or critical set)-> "ok"
                       neither set              -> "unknown"
3.  SCORE
    scoring_method == "direct":  score = clamp(v, 0, 100)
    scoring_method == "linear":  needs target_value AND critical_threshold, and a non-zero span.
        higher_is_better and target > critical:
            score = clamp(100 * (v - critical) / (target - critical), 0, 100)
        lower_is_better and critical > target:
            score = clamp(100 * (critical - v) / (critical - target), 0, 100)
        otherwise -> FALL BACK to the band table below (documented, not an error)
    scoring_method == "band" (or the linear fallback):
            {"ok": 100, "warning": 70, "critical": 30}.get(band)   # None when band == "unknown"
4.  score, when not None, is quantized to Decimal("0.01")
5.  return (score, band)
```

`@property band_css` is **NOT** on this model — bands live on the score row (plan, line 1737).

---

### 1.2 `SupplierKpiScore` — `models/SupplierPerformanceEvaluation/ScorecardKpiScores.py`

Base **`TenantOwned`** · **NO `NUMBER_PREFIX`, no `number`** (a child fact row — the
`KpiSnapshot` / `InvoiceMatchVariance` precedent).

**The module docstring MUST carry the two CRUD exemptions verbatim** (plan, lines 1798–1807) so a
reviewer does not flag them as missing:
1. **No create form and no `supplierkpiscore_create` route.** Lines are system-written by
   `supplierevaluation_generate`; a hand-created line would be a measurement with no computation
   behind it (the `SpendReportSnapshot` / `CostForecast`-has-no-edit precedent).
2. **Edit is limited to `measured_value` + `comment`, and only when `source_at_time == "manual"`.
   The VIEW is the gate** — any other row redirects to the detail page with `messages.error`. A
   disabled widget is UX, not an authorization boundary.
   **Delete (POST-only) DOES exist** so a retired KPI's stale line can be removed.

#### CHOICES + CSS

```python
BAND_CHOICES = [
    ("ok", "On target"), ("warning", "Warning"),
    ("critical", "Critical"), ("unknown", "Not banded"),
]
# L33 — theme.css ships badge-green/-red/-amber/-info/-muted/-slate and NOTHING else.
# badge-success / badge-warning / badge-danger DO NOT EXIST and render completely unstyled.
BAND_CSS = {
    "ok": "badge-green", "warning": "badge-amber",
    "critical": "badge-red", "unknown": "badge-muted",
}
```

#### Fields, in declaration order

| # | Field | Definition |
|---|---|---|
| 1 | `scorecard` | `ForeignKey("scm.SupplierScorecard", on_delete=models.CASCADE, related_name="procurement_kpi_scores")` |
| 2 | `kpi` | `ForeignKey("procurement.SupplierKpi", on_delete=models.PROTECT, related_name="scores", help_text="PROTECT: deleting a KPI must never silently delete measured history — retire it with is_active=False")` |
| 3 | `measured_value` | `DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)` |
| 4 | `score` | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))])` |
| 5 | `weight_applied` | `PositiveSmallIntegerField(default=0, help_text="The KPI's weight FROZEN at generation — a later retune must not rewrite a closed period")` |
| 6 | `band` | `CharField(max_length=10, choices=BAND_CHOICES, default="unknown")` |
| 7 | `target_at_time` | `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, editable=False)` |
| 8 | `direction_at_time` | `CharField(max_length=16, blank=True, editable=False)` |
| 9 | `source_at_time` | `CharField(max_length=8, blank=True, editable=False)` |
| 10 | `unit_at_time` | `CharField(max_length=10, blank=True, editable=False)` |
| 11 | `kpi_name` | `CharField(max_length=160, blank=True, editable=False)` |
| 12 | `kpi_category` | `CharField(max_length=16, blank=True, editable=False)` |
| 13 | `breakdown` | `JSONField(default=dict, blank=True, editable=False, help_text="How the figure was arrived at — numerator, denominator, window, rows considered")` |
| 14 | `respondent_count` | `PositiveIntegerField(default=0, editable=False, help_text="How many 360 responses were aggregated for a survey KPI")` |
| 15 | `comment` | `TextField(blank=True)` |
| 16 | `computed_at` | `DateTimeField(default=timezone.now, editable=False)` — **`default=timezone.now`, NOT `auto_now_add`**: a re-run must re-stamp freshness |
| 17 | `computed_by` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="procurement_kpi_scores_computed")` |

`models.JSONField` is reached through the `_base` star import (`models` is exported); no extra
import line is needed.

#### Meta

```python
ordering = ["kpi_category", "kpi_name", "id"]      # the DENORMALISED columns — no JOIN per list row
unique_together = ("tenant", "scorecard", "kpi")   # THIS is what makes generate safe to press twice
indexes = [
    models.Index(fields=["tenant", "scorecard"], name="prc_sks_tnt_scr_idx"),
    models.Index(fields=["tenant", "band"],      name="prc_sks_tnt_band_idx"),
    models.Index(fields=["tenant", "kpi"],       name="prc_sks_tnt_kpi_idx"),
]
verbose_name = "Supplier KPI Score"
verbose_name_plural = "Supplier KPI Scores"
```

#### Methods

| Signature | Contract |
|---|---|
| `__str__(self)` | `f"{self.kpi_name or 'KPI'} · {self.score if self.score is not None else '—'}"` **(contract decision)** |
| `clean(self)` | Same-tenant guards on `scorecard` and `kpi`, using **`_id` guards + an explicit queryset lookup**, never a bare `self.scorecard.tenant_id` (the `VendorSuspension.clean()` precedent — the two-arg `getattr` form raised `RelatedObjectDoesNotExist` and 500'd a live add page). Skip entirely when `self.tenant_id is None`. Error keys `"scorecard"` / `"kpi"`, message `"That record belongs to another workspace."` |
| `@property band_css` | `self.BAND_CSS.get(self.band, "badge-slate")` |
| `@property contribution` | `None` when `self.score is None`; else `self.score * self.weight_applied` (Decimal). Used by the evaluation detail's composite arithmetic table. |

Concrete `clean()` shape (so the builder does not re-derive it):

```python
if self.tenant_id and self.scorecard_id:
    from apps.scm.models import SupplierScorecard          # local import — cross-app
    if not SupplierScorecard.objects.filter(pk=self.scorecard_id,
                                            tenant_id=self.tenant_id).exists():
        errors["scorecard"] = "That record belongs to another workspace."
if self.tenant_id and self.kpi_id:
    if not SupplierKpi.objects.filter(pk=self.kpi_id, tenant_id=self.tenant_id).exists():
        errors["kpi"] = "That record belongs to another workspace."
```

---

### 1.3 `SupplierFeedback` — `models/SupplierPerformanceEvaluation/SupplierFeedback.py`

Base **`TenantNumbered`** · `NUMBER_PREFIX = "SFB"`.
One row = one respondent's rating of one supplier for one period, optionally against one KPI.

#### CHOICES

```python
RESPONDENT_KIND_CHOICES = [("internal", "Internal"), ("supplier_self", "Supplier self-assessment")]
FUNCTION_CHOICES = [
    ("procurement", "Procurement"), ("quality", "Quality"), ("operations", "Operations"),
    ("finance", "Finance"), ("engineering", "Engineering"), ("logistics", "Logistics"),
    ("other", "Other"),
]
RATING_CHOICES = [
    (1, "1 — Poor"), (2, "2 — Below expectations"), (3, "3 — Meets expectations"),
    (4, "4 — Above expectations"), (5, "5 — Excellent"),
]                                                        # (contract decision on the label text)
STATUS_CHOICES = [
    ("requested", "Requested"), ("submitted", "Submitted"),
    ("declined", "Declined"), ("expired", "Expired"),
]
# L33 colour names only. (contract decision)
STATUS_CSS = {"requested": "badge-amber", "submitted": "badge-green",
              "declined": "badge-muted", "expired": "badge-slate"}
RATING_CSS = {1: "badge-red", 2: "badge-red", 3: "badge-amber",
              4: "badge-green", 5: "badge-green"}
KIND_CSS = {"internal": "badge-slate", "supplier_self": "badge-info"}
#: rating -> 0-100 for the survey aggregate.
RATING_SCORE_MAP = {1: 0, 2: 25, 3: 50, 4: 75, 5: 100}
```

#### Fields, in declaration order

| # | Field | Definition |
|---|---|---|
| 1 | `supplier` | `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="procurement_supplier_feedback")` |
| 2 | `scorecard` | `ForeignKey("scm.SupplierScorecard", on_delete=models.SET_NULL, null=True, blank=True, related_name="procurement_feedback", help_text="The period document this response belongs to. Blank = ad-hoc feedback")` |
| 3 | `kpi` | `ForeignKey("procurement.SupplierKpi", on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback", help_text="Set = this response feeds that survey KPI. Blank = general commentary")` |
| 4 | `period_start` | `DateField()` |
| 5 | `period_end` | `DateField()` |
| 6 | `respondent_kind` | `CharField(max_length=16, choices=RESPONDENT_KIND_CHOICES, default="internal")` |
| 7 | `respondent` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="procurement_feedback_given")` |
| 8 | `respondent_name` | `CharField(max_length=160, blank=True, help_text="Required for a supplier self-assessment, which has no internal user account")` |
| 9 | `respondent_function` | `CharField(max_length=16, choices=FUNCTION_CHOICES, default="procurement")` |
| 10 | `rating` | `PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)` |
| 11 | `importance` | `PositiveSmallIntegerField(default=5, validators=[MinValueValidator(0), MaxValueValidator(10)], help_text="How much this respondent's rating counts in the survey aggregate, 0-10")` |
| 12 | `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="requested")` |
| 13 | `due_date` | `DateField(null=True, blank=True)` |
| 14 | `requested_by` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="procurement_feedback_requested")` |
| 15 | `requested_at` | `DateTimeField(default=timezone.now, editable=False)` |
| 16 | `submitted_at` | `DateTimeField(null=True, blank=True, editable=False)` |
| 17 | `comment` | `TextField(blank=True)` |

Field-order note **(contract decision)**: `respondent` is declared at position 7 (next to
`respondent_kind` / `respondent_name`) even though the plan's prose lists the FKs together — the
form's `Meta.fields` order below is the authoritative render order and matches this.

#### Meta

```python
ordering = ["-period_end", "-id"]
unique_together = ("tenant", "number")
indexes = [
    models.Index(fields=["tenant", "supplier"],  name="prc_sfb_tnt_supp_idx"),
    models.Index(fields=["tenant", "status"],    name="prc_sfb_tnt_status_idx"),
    models.Index(fields=["tenant", "scorecard"], name="prc_sfb_tnt_scr_idx"),
]
verbose_name = "Supplier Feedback"
verbose_name_plural = "Supplier Feedback"
```

#### Methods

| Signature | Contract |
|---|---|
| `__str__(self)` | `f"{self.number or 'SFB'} · {self.supplier_id and self.supplier.name}"` |
| `score_value(self)` | `-> Decimal \| None`. `None` when `rating` is `None`; else `Decimal(RATING_SCORE_MAP[self.rating])` (0/25/50/75/100). |
| `@property status_css` | `self.STATUS_CSS.get(self.status, "badge-slate")` |
| `@property rating_css` | `self.RATING_CSS.get(self.rating, "badge-slate")` |
| `@property kind_css` | `self.KIND_CSS.get(self.respondent_kind, "badge-slate")` |
| `@property is_overdue` | `bool(self.due_date and self.status == "requested" and self.due_date < timezone.localdate())` **(contract decision — drives the list's `overdue` stat)** |
| `clean(self)` | Five rules — below. |

**`clean()` — five rules (plan, lines 1843–1854):**

1. **One response per `(supplier, scorecard, kpi, respondent)`** — an explicit
   `.exclude(pk=self.pk).filter(tenant_id=…, supplier_id=…, scorecard_id=…, kpi_id=…,
   respondent_id=…).exists()` check **matching NULLs by id** (pass the raw `*_id` values, `None`
   included, so Django emits `IS NULL`). **NOT `unique_together`** — `scorecard`, `kpi` and
   `respondent` are nullable and SQL NULLs compare distinct, so a naive constraint lets duplicates
   straight through (the `KpiSnapshot` blank-vs-NULL trap). Error key `"respondent"`, message
   `"This respondent has already answered for that supplier, period document and KPI."`
2. `kpi`, when set, must have `source == "survey"` — resolve with an explicit
   `SupplierKpi.objects.filter(pk=self.kpi_id, tenant_id=self.tenant_id).values_list("source", flat=True).first()`.
   Error key `"kpi"`, `"A derived KPI is not a survey question."`
3. `period_end >= period_start`. Error key `"period_end"`, `"The period ends before it starts."`
4. `rating` required when `status == "submitted"`. Error key `"rating"`,
   `"A submitted response needs a rating."`
5. Same-tenant `_id` guards on `supplier`, `scorecard`, `kpi` (explicit queryset lookups, as in
   §1.2); **and** `respondent_kind == "supplier_self"` ⇒ `respondent` must be blank
   (key `"respondent"`, `"A supplier self-assessment is not filed by an internal user."`) **and**
   `respondent_name` is required (key `"respondent_name"`,
   `"Name the person who answered on the supplier's side."`).

---

### 1.4 `SupplierImprovementPlan` — `models/SupplierPerformanceEvaluation/SupplierImprovementPlans.py`

Base **`TenantNumbered`** · `NUMBER_PREFIX = "SIP"`.
**Plan grain only this pass** — designed to accept a `SupplierImprovementAction` child later
without reshaping. Do **not** cram a fake action list into a TextField.

#### CHOICES

```python
SEVERITY_CHOICES = [("minor", "Minor"), ("major", "Major"), ("critical", "Critical")]
STATUS_CHOICES = [
    ("draft", "Draft"), ("active", "Active"), ("monitoring", "Monitoring"),
    ("closed", "Closed"), ("cancelled", "Cancelled"),
]
OUTCOME_CHOICES = [
    ("successful", "Successful"), ("extended", "Extended"),
    ("failed", "Failed"), ("escalated", "Escalated to suspension"),
]
# L33 colour names only. (contract decision)
SEVERITY_CSS = {"minor": "badge-slate", "major": "badge-amber", "critical": "badge-red"}
STATUS_CSS = {"draft": "badge-slate", "active": "badge-amber", "monitoring": "badge-info",
              "closed": "badge-green", "cancelled": "badge-muted"}
OUTCOME_CSS = {"successful": "badge-green", "extended": "badge-amber",
               "failed": "badge-red", "escalated": "badge-red"}
#: Statuses a plan is still being worked in — the list's `active`/`monitoring` stats and the
#: overdue calculation read this.
OPEN_STATUSES = ("draft", "active", "monitoring")
```

#### Fields, in declaration order

| # | Field | Definition |
|---|---|---|
| 1 | `title` | `CharField(max_length=200)` |
| 2 | `supplier` | `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="procurement_improvement_plans")` |
| 3 | `scorecard` | `ForeignKey("scm.SupplierScorecard", on_delete=models.SET_NULL, null=True, blank=True, related_name="procurement_improvement_plans", help_text="The triggering evidence — the period whose performance opened this plan")` |
| 4 | `kpi` | `ForeignKey("procurement.SupplierKpi", on_delete=models.SET_NULL, null=True, blank=True, related_name="improvement_plans", help_text="The failing KPI, when one metric drove it")` |
| 5 | `severity` | `CharField(max_length=8, choices=SEVERITY_CHOICES, default="major")` |
| 6 | `finding` | `TextField(help_text="What was observed")` |
| 7 | `root_cause` | `TextField(blank=True)` |
| 8 | `corrective_actions` | `TextField(blank=True)` |
| 9 | `support_provided` | `TextField(blank=True, help_text="What the buyer is doing to help")` |
| 10 | `success_criteria` | `TextField(blank=True, help_text="What 'fixed' looks like, in measurable terms")` |
| 11 | `start_date` | `DateField()` |
| 12 | `target_close_date` | `DateField()` |
| 13 | `next_review_date` | `DateField(null=True, blank=True, help_text="When the next check-in falls due")` |
| 14 | `extended_close_date` | `DateField(null=True, blank=True, help_text="A granted extension — must fall after the original target")` |
| 15 | `actual_close_date` | `DateField(null=True, blank=True, editable=False)` |
| 16 | `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` |
| 17 | `outcome` | `CharField(max_length=12, choices=OUTCOME_CHOICES, blank=True)` |
| 18 | `owner` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="procurement_improvement_plans", help_text="The internal owner of this plan")` |
| 19 | `supplier_owner_name` | `CharField(max_length=160, blank=True)` |
| 20 | `supplier_owner_email` | `EmailField(blank=True)` |
| 21 | `escalated_suspension` | `ForeignKey("procurement.VendorSuspension", on_delete=models.SET_NULL, null=True, blank=True, related_name="improvement_plans", help_text="The block register entry this plan escalated to — never a second blocking mechanism")` |
| 22 | `evidence` | `FileField(upload_to="procurement/improvement_evidence/%Y/%m/", null=True, blank=True)` |
| 23 | `evidence_url` | `URLField(blank=True, help_text="Link to evidence held elsewhere")` |
| 24 | `acknowledged_by` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="procurement_pip_acknowledged")` |
| 25 | `acknowledged_at` | `DateTimeField(null=True, blank=True, editable=False)` |
| 26 | `verified_by` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="procurement_pip_verified")` |
| 27 | `verified_at` | `DateTimeField(null=True, blank=True, editable=False)` |
| 28 | `closure_note` | `TextField(blank=True, editable=False)` |

#### Meta

```python
ordering = ["-start_date", "-id"]
unique_together = ("tenant", "number")
indexes = [
    models.Index(fields=["tenant", "status"],   name="prc_sip_tnt_status_idx"),
    models.Index(fields=["tenant", "supplier"], name="prc_sip_tnt_supp_idx"),
    models.Index(fields=["tenant", "severity"], name="prc_sip_tnt_sev_idx"),
]
verbose_name = "Supplier Improvement Plan"
verbose_name_plural = "Supplier Improvement Plans"
```

#### Methods

| Signature | Contract |
|---|---|
| `__str__(self)` | `f"{self.number or 'SIP'} · {self.title}"` |
| `@property has_evidence` | `bool(self.evidence) or bool(self.evidence_url)` |
| `@property effective_close_date` | `self.extended_close_date or self.target_close_date` **(contract decision — one place the overdue rule reads)** |
| `@property is_overdue` | `bool(self.effective_close_date and self.status in self.OPEN_STATUSES and self.effective_close_date < timezone.localdate())` |
| `@property severity_css` / `status_css` / `outcome_css` | `.get(value, "badge-slate")` over the three maps above |
| `clean(self)` | Five rules — below. |

**`clean()`:**

1. `target_close_date >= start_date` (key `"target_close_date"`, `"The plan closes before it starts."`).
2. `extended_close_date`, when set, must be **strictly after** `target_close_date`
   (key `"extended_close_date"`, `"An extension has to fall after the original target date."`).
3. `outcome` **required** when `status == "closed"` (key `"outcome"`,
   `"A closed plan has to record its outcome."`) and **must be blank otherwise**
   (`"Only a closed plan carries an outcome — clear it."`).
4. `escalated_suspension`, when set, must belong to the **same tenant AND the same supplier**:
   one queryset lookup
   `VendorSuspension.objects.filter(pk=self.escalated_suspension_id, tenant_id=self.tenant_id).values_list("supplier_id", flat=True).first()`
   — `None` ⇒ `"That record belongs to another workspace."`; a mismatch against `self.supplier_id`
   ⇒ `"That suspension is against a different supplier."` (key `"escalated_suspension"`).
5. Same-tenant `_id` guards on `supplier`, `scorecard`, `kpi` (explicit queryset lookups, as §1.2).

---

## 2. Forms

All in `apps/procurement/forms/SupplierPerformanceEvaluation/`. Every module starts
`from apps.procurement.forms._common import *  # noqa: F401,F403` **plus** the explicit second
line `from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign`. Models are
imported from their **entity modules** (`from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi`),
never from `apps.procurement.models`.

`TenantUniqueMixin` comes **FIRST** in the MRO on every form whose model's `clean()` compares a
chosen FK's tenant against `self.tenant_id` — i.e. **all four** — otherwise every CREATE is falsely
rejected as cross-tenant.

Cross-app querysets (`Party`, `SupplierScorecard`) are imported **inside `__init__`**.

Standard `__init__` guard on all four: when `tenant is None`, set every tenant-scoped
`ModelChoiceField.queryset` to `.none()` and return early.

### Two `TenantModelForm` behaviours the builder must NOT duplicate (verified `apps/core/forms/_common.py:25-53`)

1. **User FKs are already tenant-scoped.** `TenantModelForm.__init__` filters **every**
   `ModelChoiceField` whose target model has a `tenant` field — and `accounts.User.tenant` is a
   nullable FK (`apps/accounts/models.py:56`), so `owner` and `respondent` are auto-scoped. **Do
   not re-filter them by tenant**; narrow only to `is_active=True`, set `empty_label`, and keep
   `_reject_foreign` as the crafted-POST re-check (the `ProcurementAlert` / `InvoiceDispute`
   `assigned_to` precedent — both forms document exactly this and hand-narrow nothing).
2. **Date and Textarea widgets are already styled.** `TenantModelForm` **unconditionally replaces**
   every `DateField` widget with `forms.DateInput(attrs={"type": "date", "class": "form-input"},
   format="%Y-%m-%d")` and `setdefault`s `class="form-textarea"` on every Textarea. A
   `"period_start": forms.DateInput(attrs={"type": "date"})` entry in `Meta.widgets` is therefore
   **overwritten and is a no-op** — the date-widget rows below are listed only so the builder
   recognises them as optional. `rows=` on a Textarea **is** meaningful and must stay.

Shared supplier queryset, defined as a private module helper in each form module that needs one:

```python
def _supplier_parties(tenant):
    from apps.core.models import Party
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))
```

---

### 2.1 `SupplierKpiForm` — `forms/SupplierPerformanceEvaluation/SupplierKpis.py`

`class SupplierKpiForm(TenantUniqueMixin, TenantModelForm)`

```python
class Meta:
    model = SupplierKpi
    fields = ["code", "name", "description", "category", "unit", "direction", "source",
              "derived_metric", "weight", "target_value", "warning_threshold",
              "critical_threshold", "scoring_method", "maps_to_dimension", "applies_to",
              "applies_to_tier", "review_frequency", "industry_benchmark_value", "owner",
              "display_order", "is_active", "notes"]
    widgets = {                                              # (contract decision)
        "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
    }
```

`__init__(self, *args, tenant=None, **kwargs)` — touches **`owner`** only, and **only for the
`is_active` narrowing and the empty label**; the tenant scoping is already done by
`TenantModelForm` **(contract decision — matches the `ProcurementAlert.assigned_to` idiom)**:

```python
# ``owner`` targets accounts.User, whose nullable ``tenant`` makes it auto-scoped by
# TenantModelForm — narrow only to live accounts here.
field = self.fields["owner"]
field.queryset = field.queryset.filter(is_active=True).order_by("email")
field.empty_label = "- unassigned -"
```

`clean()` → `_reject_foreign(self, cleaned, ["owner"])`.
(`owner` is a `User`, which carries `tenant_id` — the same shape `_reject_foreign` expects.)

**Exclusions, one reason each**

| Excluded | Reason |
|---|---|
| `tenant` | Stamped by `TenantUniqueMixin` / `crud_create`. |
| `number` | Assigned once by `TenantNumbered.save()` — `SKP-#####`. |
| `created_at` / `updated_at` | Base timestamps, system-owned (L22). |

---

### 2.2 `SupplierKpiScoreEditForm` — `forms/SupplierPerformanceEvaluation/ScorecardKpiScores.py`

`class SupplierKpiScoreEditForm(TenantUniqueMixin, TenantModelForm)`

```python
class Meta:
    model = SupplierKpiScore
    fields = ["measured_value", "comment"]                   # TWO FIELDS. Nothing else, ever.
    widgets = {"comment": forms.Textarea(attrs={"class": "form-textarea", "rows": 3})}
```

`__init__` — no queryset narrowing (there are no FK fields on this form); keep the
`tenant=None` signature for `crud_edit` compatibility.

`save(self, commit=True)` — **re-derives through the KPI so a hand-typed value is banded by
exactly the same rule as a derived one:**

```python
obj = super().save(commit=False)
score, band = obj.kpi.score_and_band(obj.measured_value)
obj.score, obj.band = score, band
obj.computed_at = timezone.now()
obj.breakdown = {"source": "manual entry",
                 "measured_value": str(obj.measured_value) if obj.measured_value is not None else None,
                 "scoring_method": obj.kpi.scoring_method,
                 "direction": obj.kpi.direction,
                 "entered_at": obj.computed_at.isoformat()}
if commit:
    obj.save()
return obj
```

`timezone` arrives through the `forms/_common` star import chain; if it does not, add an explicit
`from django.utils import timezone` **(contract decision)**.

**There is NO `SupplierKpiScoreForm` (create form) and NO create route.** See §1.2's two
documented CRUD exemptions.

**Exclusions, one reason each**

| Excluded | Reason |
|---|---|
| `tenant` | System-stamped; the row is written by generate. |
| `scorecard`, `kpi` | The line's identity — changing either would be creating a different line, which `unique_together` exists to prevent. |
| `weight_applied` | Frozen at generation; a re-weight must not rewrite a closed period. |
| `target_at_time`, `direction_at_time`, `source_at_time`, `unit_at_time`, `kpi_name`, `kpi_category` | `editable=False` frozen-at-time columns — history, not input. |
| `score`, `band` | **Derived** in `save()` from `kpi.score_and_band()`; typing them would break the one-scale rule. |
| `breakdown` | `editable=False`; rewritten by `save()` to say "manual entry". |
| `respondent_count` | `editable=False`; only the survey aggregation sets it. |
| `computed_at`, `computed_by` | `editable=False` freshness/authorship stamps (L22). |

---

### 2.3 `SupplierFeedbackForm` — `forms/SupplierPerformanceEvaluation/SupplierFeedback.py`

`class SupplierFeedbackForm(TenantUniqueMixin, TenantModelForm)`

```python
class Meta:
    model = SupplierFeedback
    fields = ["supplier", "scorecard", "kpi", "period_start", "period_end", "respondent_kind",
              "respondent_function", "respondent", "respondent_name", "rating", "importance",
              "due_date", "comment"]
    widgets = {                    # (contract decision) — the three date entries are NO-OPS
        "period_start": forms.DateInput(attrs={"type": "date"}),   # overwritten by TenantModelForm
        "period_end":   forms.DateInput(attrs={"type": "date"}),   # overwritten by TenantModelForm
        "due_date":     forms.DateInput(attrs={"type": "date"}),   # overwritten by TenantModelForm
        "comment":      forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
    }
```

`__init__` queryset narrowing (all inside `__init__`, cross-app imports local):

| Field | Queryset | `empty_label` |
|---|---|---|
| `supplier` | `_supplier_parties(tenant)` | (required — no empty label) |
| `scorecard` | `SupplierScorecard.objects.filter(tenant=tenant).select_related("party").order_by("-period_end", "-id")` | `"- not tied to a period -"` |
| `kpi` | `SupplierKpi.objects.filter(tenant=tenant, is_active=True, source="survey").order_by("display_order", "code")` | `"- general commentary -"` |
| `respondent` | **already tenant-scoped by `TenantModelForm`** — narrow only with `field.queryset.filter(is_active=True).order_by("email")` | `"- external / not a system user -"` |

`clean()` → `_reject_foreign(self, cleaned, ["supplier", "scorecard", "kpi", "respondent"])`.

**Exclusions, one reason each**

| Excluded | Reason |
|---|---|
| `tenant` | Stamped by `TenantUniqueMixin` / `crud_create`. |
| `number` | Auto `SFB-#####` from `TenantNumbered.save()`. |
| `status` | Workflow-controlled by the submit / decline / expire verbs — never typed. |
| `requested_by` | Authorship stamp, taken from `request.user` on create. |
| `requested_at` | `editable=False` raise stamp (L22). |
| `submitted_at` | `editable=False`; stamped by the submit verb only. |
| `created_at` / `updated_at` | Base timestamps. |

---

### 2.4 `SupplierImprovementPlanForm` — `forms/SupplierPerformanceEvaluation/SupplierImprovementPlans.py`

`class SupplierImprovementPlanForm(TenantUniqueMixin, TenantModelForm)`

```python
class Meta:
    model = SupplierImprovementPlan
    fields = ["title", "supplier", "scorecard", "kpi", "severity", "finding", "root_cause",
              "corrective_actions", "support_provided", "success_criteria", "start_date",
              "target_close_date", "next_review_date", "extended_close_date", "owner",
              "supplier_owner_name", "supplier_owner_email", "escalated_suspension",
              "evidence", "evidence_url"]
    widgets = {                                              # (contract decision)
        "finding":            forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
        "root_cause":         forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        "corrective_actions": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
        "support_provided":   forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        "success_criteria":   forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        # The four date entries below are NO-OPS — TenantModelForm replaces every DateField widget.
        "start_date":           forms.DateInput(attrs={"type": "date"}),
        "target_close_date":    forms.DateInput(attrs={"type": "date"}),
        "next_review_date":     forms.DateInput(attrs={"type": "date"}),
        "extended_close_date":  forms.DateInput(attrs={"type": "date"}),
    }
```

`__init__` queryset narrowing:

| Field | Queryset | `empty_label` |
|---|---|---|
| `supplier` | `_supplier_parties(tenant)` | (required) |
| `scorecard` | tenant scorecards, `select_related("party")`, `-period_end`, `-id` | `"- no triggering period -"` |
| `kpi` | `SupplierKpi.objects.filter(tenant=tenant, is_active=True).order_by("display_order", "code")` | `"- not one KPI -"` |
| `owner` | **already tenant-scoped by `TenantModelForm`** — narrow only with `field.queryset.filter(is_active=True).order_by("email")` | `"- unassigned -"` |
| `escalated_suspension` | `VendorSuspension.objects.filter(tenant=tenant).select_related("supplier").order_by("-id")` | `"- not escalated -"` |

`clean()` → `_reject_foreign(self, cleaned, ["supplier", "scorecard", "kpi", "owner", "escalated_suspension"])`.

`clean_evidence(self)` — copy the **`ReceiptDiscrepancies.py:114` precedent verbatim**:
local `import os`; local
`from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES`; extension
allowlist first, then the size cap; the constants are imported **locally** and **not** re-exported
from `forms/__init__.py`.

**Exclusions, one reason each**

| Excluded | Reason |
|---|---|
| `tenant` | Stamped by `TenantUniqueMixin` / `crud_create`. |
| `number` | Auto `SIP-#####`. |
| `status` | Workflow-controlled by activate / monitor / close / cancel. |
| `outcome` | Set by the close verb from its POST body, alongside `closure_note`. |
| `actual_close_date` | `editable=False`; stamped by close. |
| `acknowledged_by` / `acknowledged_at` | `editable=False` acknowledgement stamps (L22). |
| `verified_by` / `verified_at` | `editable=False` verification stamps, written by close. |
| `closure_note` | `editable=False`; taken from the close POST body. |
| `created_at` / `updated_at` | Base timestamps. |

**The form template MUST carry `enctype="multipart/form-data"`** (evidence upload) and print the
allowed extensions plus the max MB.

---

## 3. URL names — the complete table

Namespace `procurement`. Five modules under `apps/procurement/urls/SupplierPerformanceEvaluation/`,
appended **LAST** in `urls/__init__.py` (the 6.13/6.14/6.15 belt-and-braces precedent).

**Every first path component is a literal** — `supplier-kpis/`, `supplier-evaluations/`,
`supplier-feedback/`, `improvement-plans/`, `supplier-benchmarking/`. This app's standing guarantee
is that **no route anywhere in `apps/procurement/urls/` has a converter in first position**; 6.16
must not break it. All five segments are new whole components — checked against the
`urls/__init__.py` inventory.

### 3.1 `urls/SupplierPerformanceEvaluation/SupplierKpis.py`

| # | Route | View | url name | Gates |
|---|---|---|---|---|
| 1 | `supplier-kpis/` | `views.supplierkpi_list` | `supplierkpi_list` | `@login_required` |
| 2 | `supplier-kpis/add/` | `views.supplierkpi_create` | `supplierkpi_create` | `@login_required` |
| 3 | `supplier-kpis/<int:pk>/` | `views.supplierkpi_detail` | `supplierkpi_detail` | `@login_required` |
| 4 | `supplier-kpis/<int:pk>/edit/` | `views.supplierkpi_edit` | `supplierkpi_edit` | `@login_required` |
| 5 | `supplier-kpis/<int:pk>/delete/` | `views.supplierkpi_delete` | `supplierkpi_delete` | `@login_required` + **`@require_POST`** |

Literal `add/` is declared **before** `<int:pk>/`.

### 3.2 `urls/SupplierPerformanceEvaluation/ScorecardKpiScores.py`

**Declaration order is load-bearing: the literal `scores/` block comes BEFORE
`supplier-evaluations/<int:pk>/`.**

| # | Route | View | url name | Gates |
|---|---|---|---|---|
| 1 | `supplier-evaluations/` | `views.supplierevaluation_list` | `supplierevaluation_list` | `@login_required` |
| 2 | `supplier-evaluations/scores/` | `views.supplierkpiscore_list` | `supplierkpiscore_list` | `@login_required` |
| 3 | `supplier-evaluations/scores/<int:pk>/` | `views.supplierkpiscore_detail` | `supplierkpiscore_detail` | `@login_required` |
| 4 | `supplier-evaluations/scores/<int:pk>/edit/` | `views.supplierkpiscore_edit` | `supplierkpiscore_edit` | `@login_required` |
| 5 | `supplier-evaluations/scores/<int:pk>/delete/` | `views.supplierkpiscore_delete` | `supplierkpiscore_delete` | `@login_required` + **`@require_POST`** |
| 6 | `supplier-evaluations/<int:pk>/` | `views.supplierevaluation_detail` | `supplierevaluation_detail` | `@login_required` |
| 7 | `supplier-evaluations/<int:pk>/generate/` | `views.supplierevaluation_generate` | `supplierevaluation_generate` | **`@require_POST` + `@tenant_admin_required`** |

**No procurement scorecard CREATE route** (L36). The evaluation register's "New period" button
links out to `{% url 'scm:scorecard_create' %}`.

### 3.3 `urls/SupplierPerformanceEvaluation/SupplierFeedback.py`

| # | Route | View | url name | Gates |
|---|---|---|---|---|
| 1 | `supplier-feedback/` | `views.supplierfeedback_list` | `supplierfeedback_list` | `@login_required` |
| 2 | `supplier-feedback/add/` | `views.supplierfeedback_create` | `supplierfeedback_create` | `@login_required` |
| 3 | `supplier-feedback/<int:pk>/` | `views.supplierfeedback_detail` | `supplierfeedback_detail` | `@login_required` |
| 4 | `supplier-feedback/<int:pk>/edit/` | `views.supplierfeedback_edit` | `supplierfeedback_edit` | `@login_required` |
| 5 | `supplier-feedback/<int:pk>/submit/` | `views.supplierfeedback_submit` | `supplierfeedback_submit` | `@login_required` + **`@require_POST`** |
| 6 | `supplier-feedback/<int:pk>/decline/` | `views.supplierfeedback_decline` | `supplierfeedback_decline` | `@login_required` + **`@require_POST`** |
| 7 | `supplier-feedback/<int:pk>/expire/` | `views.supplierfeedback_expire` | `supplierfeedback_expire` | `@login_required` + **`@require_POST`** |
| 8 | `supplier-feedback/<int:pk>/delete/` | `views.supplierfeedback_delete` | `supplierfeedback_delete` | `@login_required` + **`@require_POST`** |

`expire/` exists so the `expired` choice is reachable — **no dead choices**.

### 3.4 `urls/SupplierPerformanceEvaluation/SupplierImprovementPlans.py`

| # | Route | View | url name | Gates |
|---|---|---|---|---|
| 1 | `improvement-plans/` | `views.improvementplan_list` | `improvementplan_list` | `@login_required` |
| 2 | `improvement-plans/add/` | `views.improvementplan_create` | `improvementplan_create` | `@login_required` |
| 3 | `improvement-plans/<int:pk>/` | `views.improvementplan_detail` | `improvementplan_detail` | `@login_required` |
| 4 | `improvement-plans/<int:pk>/edit/` | `views.improvementplan_edit` | `improvementplan_edit` | `@login_required` |
| 5 | `improvement-plans/<int:pk>/activate/` | `views.improvementplan_activate` | `improvementplan_activate` | `@login_required` + **`@require_POST`** |
| 6 | `improvement-plans/<int:pk>/monitor/` | `views.improvementplan_monitor` | `improvementplan_monitor` | `@login_required` + **`@require_POST`** |
| 7 | `improvement-plans/<int:pk>/acknowledge/` | `views.improvementplan_acknowledge` | `improvementplan_acknowledge` | `@login_required` + **`@require_POST`** |
| 8 | `improvement-plans/<int:pk>/close/` | `views.improvementplan_close` | `improvementplan_close` | **`@require_POST` + `@tenant_admin_required`** |
| 9 | `improvement-plans/<int:pk>/cancel/` | `views.improvementplan_cancel` | `improvementplan_cancel` | `@login_required` + **`@require_POST`** |
| 10 | `improvement-plans/<int:pk>/delete/` | `views.improvementplan_delete` | `improvementplan_delete` | `@login_required` + **`@require_POST`** |

The five verbs make every `status` and `outcome` value reachable.

### 3.5 `urls/SupplierPerformanceEvaluation/PerformanceBoards.py`

| # | Route | View | url name | Gates |
|---|---|---|---|---|
| 1 | `supplier-benchmarking/` | `views.supplier_benchmark_board` | `supplier_benchmark_board` | `@login_required` |
| 2 | `supplier-benchmarking/trend/` | `views.supplier_trend_board` | `supplier_trend_board` | `@login_required` |
| 3 | `supplier-benchmarking/perception-gap/` | `views.supplier_perception_gap` | `supplier_perception_gap` | `@login_required` |

No converters at all in this module. Board filters ride as query strings
(`?supplier=`, `?period=`, `?tier=`, `?category=`, `?kpi=`).

**33 routes total.** Every one of the 33 view function names must be appended to
`apps/procurement/views/__init__.py`'s re-export block and `__all__` — a view that is not
re-exported is an `AttributeError` at URLconf import.

---

## 4. Template paths

Sub-module folder `performance/`. Entity folders below it (Template-Folder rule 2); the three
boards are standalone pages at the sub-module root (rule 6).

| # | Path | Rendered by |
|---|---|---|
| 1 | `templates/procurement/performance/kpi/list.html` | `supplierkpi_list` |
| 2 | `templates/procurement/performance/kpi/detail.html` | `supplierkpi_detail` |
| 3 | `templates/procurement/performance/kpi/form.html` | `supplierkpi_create`, `supplierkpi_edit` |
| 4 | `templates/procurement/performance/evaluation/list.html` | `supplierevaluation_list` |
| 5 | `templates/procurement/performance/evaluation/detail.html` | `supplierevaluation_detail` |
| 6 | `templates/procurement/performance/kpiscore/list.html` | `supplierkpiscore_list` |
| 7 | `templates/procurement/performance/kpiscore/detail.html` | `supplierkpiscore_detail` |
| 8 | `templates/procurement/performance/kpiscore/form.html` | `supplierkpiscore_edit` (edit only — `is_edit` is always `True` here) |
| 9 | `templates/procurement/performance/feedback/list.html` | `supplierfeedback_list` |
| 10 | `templates/procurement/performance/feedback/detail.html` | `supplierfeedback_detail` |
| 11 | `templates/procurement/performance/feedback/form.html` | `supplierfeedback_create`, `supplierfeedback_edit` |
| 12 | `templates/procurement/performance/improvementplan/list.html` | `improvementplan_list` |
| 13 | `templates/procurement/performance/improvementplan/detail.html` | `improvementplan_detail` |
| 14 | `templates/procurement/performance/improvementplan/form.html` | `improvementplan_create`, `improvementplan_edit` (**`enctype="multipart/form-data"`**) |
| 15 | `templates/procurement/performance/benchmark_board.html` | `supplier_benchmark_board` |
| 16 | `templates/procurement/performance/trend_board.html` | `supplier_trend_board` |
| 17 | `templates/procurement/performance/perception_gap.html` | `supplier_perception_gap` |

Module-level template constants in each views module (the `CostForecasts.py` idiom):
`TEMPLATE_LIST`, `TEMPLATE_DETAIL`, `TEMPLATE_FORM` — the boards use `TEMPLATE_BENCHMARK`,
`TEMPLATE_TREND`, `TEMPLATE_GAP` **(contract decision)**.

All templates `{% extends "base.html" %}` and `{% include "partials/..." %}` unchanged.

---

## 5. View context keys — THE CONTRACT THAT DECIDES WHETHER THE BUILD WORKS

**An unpinned name is a silently blank region (200 + empty) or a `NoReverseMatch` (L7/L8).**
Every queryset below is `filter(tenant=request.tenant)` — never `.all()`.

Conventions used throughout:
* `*_choices` values are **the model's CHOICES list itself** (list of `(value, label)` 2-tuples),
  so templates iterate `{% for value, label in x_choices %}` and compare
  `{% if request.GET.x == value %}selected{% endif %}`.
* FK dropdown querysets are compared with `|stringformat:"d"` — **never `|slugify`**.
* `stats` is always a plain `dict` of ints; templates read `stats.<key>`.
* `ROW_CAP = 500` (module constant in `performance.py`, re-exported to the board views);
  `truncated` is a bool.

### 5.1 `supplierkpi_list` → `performance/kpi/list.html`

`crud_list(request, qs, TEMPLATE_LIST, search_fields=("code","name","description","notes"), filters=(...), extra_context={...})`

`filters = (("category","category",False), ("source","source",False), ("direction","direction",False), ("applies_to","applies_to",False), ("owner","owner_id",True), ("is_active","is_active",False))`

| Key | Type / shape |
|---|---|
| `object_list` | page of `SupplierKpi`, `select_related("owner")` |
| `page_obj` | `Page` with `.window` (from `apps.core.crud.paginate`) |
| `q` | `str` — the raw search term |
| `category_choices` | `SupplierKpi.CATEGORY_CHOICES` |
| `source_choices` | `SupplierKpi.SOURCE_CHOICES` |
| `direction_choices` | `SupplierKpi.DIRECTION_CHOICES` **(contract decision — the plan specifies a `direction` filter but does not name its context key)** |
| `applies_choices` | `SupplierKpi.APPLIES_CHOICES` **(contract decision)** |
| `active_choices` | `(("True", "Active"), ("False", "Inactive"))` — **(contract decision)**; `is_active` is a BooleanField, so `crud_list`'s non-int path maps the strings `"True"`/`"False"` to booleans |
| `owners` | `get_user_model().objects.filter(tenant=request.tenant, procurement_supplier_kpis__isnull=False).distinct().order_by("email")` — **only users who actually own a KPI**, the `_dispute_owners` precedent (`views/InvoiceVoucherManagement/InvoiceDisputes.py:128`): a dropdown of the whole directory is a page that never finishes loading on a big tenant, and an empty option list is more honest than one full of people who own nothing. `.none()` when `request.tenant is None`. |
| `stats` | `{"total": int, "active": int, "derived": int, "survey": int, "manual": int}` — ONE `aggregate()` with `Count("pk", filter=Q(...))`, not five COUNTs |

### 5.2 `supplierkpi_detail` → `performance/kpi/detail.html`

`crud_detail(..., select_related=("owner",), extra_context={...})`

| Key | Type / shape |
|---|---|
| `obj` | the `SupplierKpi` |
| `score_rows` | `list[SupplierKpiScore]` for this KPI, `select_related("scorecard","scorecard__party")`, newest period first, capped at `DETAIL_ROW_CAP = 50` **(contract decision)** |
| `plans` | `list[SupplierImprovementPlan]` citing this KPI, `select_related("supplier")`, capped 20 **(contract decision)** |
| `feedback_rows` | `list[SupplierFeedback]` against this KPI, `select_related("supplier","respondent")`, capped 20 **(contract decision)** |
| `row_cap` | `int` — `DETAIL_ROW_CAP`, printed when a list is cut |
| `truncated` | `bool` — any of the three lists hit its cap |
| `benchmark_note` | `str` — the "hand-entered reference figure; there is no external benchmark feed" sentence, ONE module constant so the three surfaces cannot describe it differently |

### 5.3 `supplierkpi_create` / `supplierkpi_edit` → `performance/kpi/form.html`

Plain `crud_create` / `crud_edit`, **no `extra_context`** (the house convention — see
`budgetmapping_create`).

| Key | Type / shape | Which view |
|---|---|---|
| `form` | `SupplierKpiForm` | both |
| `is_edit` | `False` on create, `True` on edit | both |
| `obj` | the `SupplierKpi` | **edit only** — the template must guard every `obj.*` read with `{% if is_edit %}` |

Success url for both: `"procurement:supplierkpi_list"`.

### 5.4 `supplierevaluation_list` → `performance/evaluation/list.html`

`crud_list` over `SupplierScorecard.objects.filter(tenant=request.tenant).select_related("party").annotate(line_count=Count("procurement_kpi_scores"))`.
`search_fields=("number","party__name")`.
`filters=(("supplier","party_id",True), ("status","status",False), ("year","period_end__year",True))`.

| Key | Type / shape |
|---|---|
| `object_list` | page of `scm.SupplierScorecard`, each with `.line_count` (int) |
| `page_obj` | `Page` |
| `q` | `str` |
| `status_choices` | `SupplierScorecard.STATUS_CHOICES` (`draft`/`published`/`archived`) |
| `suppliers` | `Party` queryset — `filter(tenant=…, roles__role__in=("supplier","vendor")).distinct()` |
| `year_choices` | `list[int]` — distinct `period_end__year` values in the tenant, descending **(contract decision — the plan says "period-year" without naming the key)** |
| `stats` | `{"total": int, "draft": int, "published": int, "archived": int, "generated": int}` — `generated` = scorecards with at least one 6.16 line |
| `handover_note` | `str` — the `manual_override` hand-over sentence (see §8), so the register warns before the operator opens a scorecard |

Template links "New period" to `{% url 'scm:scorecard_create' %}`; each row's period document to
`{% url 'procurement:supplierevaluation_detail' obj.pk %}` and out to
`{% url 'scm:scorecard_detail' obj.pk %}`.

### 5.5 `supplierevaluation_detail` → `performance/evaluation/detail.html`

Hand-rolled `render()` — the object is a **cross-app** model, so `crud_detail` is not used; the
lookup is `get_object_or_404(SupplierScorecard.objects.select_related("party"), pk=pk, tenant=request.tenant)`.

| Key | Type / shape |
|---|---|
| `obj` | the `scm.SupplierScorecard` (the period document) |
| `lines` | `list[SupplierKpiScore]` for this scorecard, model ordering (`kpi_category`, `kpi_name`, `id`), `select_related("kpi")` |
| `composite` | `dict`: `{"weighted_total": Decimal\|None, "weight_total": int, "scored_lines": int, "total_lines": int, "unscored_lines": int, "overall": Decimal\|None, "grade": str}` — `weighted_total` = `sum(score * weight_applied) / sum(weight_applied)` over lines with a non-`None` score, quantized `0.01`, `None` when `weight_total == 0`; `overall`/`grade` are the scorecard's own stored values, shown next to the 6.16 arithmetic |
| `dimension_map` | `dict` keyed by the four scm dimensions `delivery`/`quality`/`price`/`responsiveness`, each `{"label": str, "score": Decimal\|None (the scorecard's stored column), "kpi_count": int, "kpi_names": list[str], "weight_total": int}` |
| `can_generate` | `bool` — `obj.status == "draft"` **and** `request.tenant is not None` |
| `refusal_reason` | `str` — `""` when `can_generate`; otherwise the exact sentence the button's disabled state prints (e.g. `"A published scorecard is closed — only a draft may be generated onto."`) |
| `plans` | `list[SupplierImprovementPlan]` whose `scorecard_id == obj.pk`, `select_related("supplier","kpi")` |
| `feedback_rows` | `list[SupplierFeedback]` whose `scorecard_id == obj.pk`, `select_related("kpi","respondent")` |
| `band_choices` | `SupplierKpiScore.BAND_CHOICES` — the band legend |
| `handover_note` | `str` — the `manual_override` hand-over sentence; the page **also** re-states it as a standing note when `obj.manual_override` is already `True` |
| `row_cap` | `int` (`ROW_CAP`) |
| `truncated` | `bool` |

### 5.6 `supplierevaluation_generate` (POST-only, `@tenant_admin_required`)

No template. Calls `performance.generate_scorecard_lines(scorecard, request.user)`; **hand-rolled
save path ⇒ it calls `write_audit_log` itself** with
`changes={"action": "generate", "written": n, "skipped": n, "alerts": n}`.
On refusal: `messages.error(request, result["refusal_reason"])`, **zero writes**.
On success: `messages.success` naming the counts.
Always `redirect("procurement:supplierevaluation_detail", pk=pk)`.

### 5.7 `supplierkpiscore_list` → `performance/kpiscore/list.html`

`crud_list` over `SupplierKpiScore.objects.filter(tenant=request.tenant).select_related("kpi","scorecard","scorecard__party")`.
`search_fields=("kpi_name","comment","scorecard__number","scorecard__party__name")`.
`filters=(("band","band",False), ("source","source_at_time",False), ("kpi","kpi_id",True), ("scorecard","scorecard_id",True))`.

> **`source_at_time` has no `choices`**, so `crud_list`'s enum guard bails out and the raw value
> reaches `.filter()`. That is safe (it matches nothing on junk) but it means the template's
> `source_choices` dropdown is the ONLY thing keeping the values legal — pin it to
> `SupplierKpi.SOURCE_CHOICES`.

| Key | Type / shape |
|---|---|
| `object_list` | page of `SupplierKpiScore` |
| `page_obj` | `Page` |
| `q` | `str` |
| `band_choices` | `SupplierKpiScore.BAND_CHOICES` |
| `source_choices` | `SupplierKpi.SOURCE_CHOICES` |
| `kpis` | `SupplierKpi` queryset (tenant), ordered `display_order, code` |
| `scorecards` | `SupplierScorecard` queryset (tenant), `select_related("party")`, `-period_end` |
| `stats` | `{"total": int, "ok": int, "warning": int, "critical": int, "unknown": int}` |

List Actions column: **Edit shown only on rows where `obj.source_at_time == "manual"`**; Delete
(POST + `confirm()` + `{% csrf_token %}`) on all rows; bands rendered with `obj.band_css`.

### 5.8 `supplierkpiscore_detail` → `performance/kpiscore/detail.html`

`crud_detail(..., select_related=("kpi","scorecard","scorecard__party","computed_by"), extra_context={...})`

| Key | Type / shape |
|---|---|
| `obj` | the `SupplierKpiScore` |
| `breakdown_rows` | `list[dict]` — `[{"key": str, "value": str}, …]` from `obj.breakdown`, sorted by key, values `str()`-ified so the template never renders a raw dict **(contract decision)** |
| `can_edit` | `bool` — `obj.source_at_time == "manual"`; gates the Edit button in the Actions sidebar |

### 5.9 `supplierkpiscore_edit` → `performance/kpiscore/form.html`

**Gate first, then `crud_edit`.** The view fetches the row
(`get_object_or_404(SupplierKpiScore, pk=pk, tenant=request.tenant)`) and, when
`obj.source_at_time != "manual"`, emits
`messages.error(request, "Only a manual-entry line can be edited by hand — derived and survey lines are recomputed by Generate.")`
and `redirect("procurement:supplierkpiscore_detail", pk=pk)` **before** any form work.

| Key | Type / shape |
|---|---|
| `form` | `SupplierKpiScoreEditForm` (two fields) |
| `obj` | the `SupplierKpiScore` |
| `is_edit` | always `True` |

Success url: `"procurement:supplierkpiscore_detail"` — **note `crud_edit`'s `success_url` is passed
to `redirect()` without args**, so pass a resolved path instead:
`success_url=reverse("procurement:supplierkpiscore_detail", args=[pk])` **(contract decision — the
url takes a pk, so it must be reversed, not named)**.

### 5.10 `supplierfeedback_list` → `performance/feedback/list.html`

`search_fields=("number","supplier__name","respondent_name","comment")`.
`filters=(("supplier","supplier_id",True), ("status","status",False), ("kind","respondent_kind",False), ("function","respondent_function",False), ("kpi","kpi_id",True), ("scorecard","scorecard_id",True))`.

| Key | Type / shape |
|---|---|
| `object_list` | page of `SupplierFeedback`, `select_related("supplier","scorecard","kpi","respondent")` |
| `page_obj` | `Page` |
| `q` | `str` |
| `status_choices` | `SupplierFeedback.STATUS_CHOICES` |
| `kind_choices` | `SupplierFeedback.RESPONDENT_KIND_CHOICES` |
| `function_choices` | `SupplierFeedback.FUNCTION_CHOICES` |
| `rating_choices` | `SupplierFeedback.RATING_CHOICES` — the legend (ints, so **not** a `crud_list` filter) |
| `suppliers` | `Party` queryset (supplier/vendor roles, distinct) |
| `kpis` | `SupplierKpi` queryset (tenant, `source="survey"`) |
| `scorecards` | `SupplierScorecard` queryset (tenant) |
| `stats` | `{"total": int, "requested": int, "submitted": int, "declined": int, "overdue": int}` — `overdue` = `status="requested"` **and** `due_date__lt=today` |

### 5.11 `supplierfeedback_detail` → `performance/feedback/detail.html`

| Key | Type / shape |
|---|---|
| `obj` | the `SupplierFeedback` |
| `can_submit` | `bool` — `obj.status == "requested"` |
| `can_decline` | `bool` — `obj.status == "requested"` |
| `can_expire` | `bool` — `obj.status == "requested"` |

### 5.12 `supplierfeedback_create` / `_edit` → `performance/feedback/form.html`

`form`, `is_edit`, plus `obj` on edit. Create is **hand-rolled** (not `crud_create`) so
`requested_by` is stamped from `request.user` — the `costforecast_create` precedent — and it calls
`write_audit_log` itself. It therefore also passes the CostForecast-style page furniture:

| Key | Type / shape | Which view |
|---|---|---|
| `form` | `SupplierFeedbackForm` | both |
| `is_edit` | `False` / `True` | both |
| `obj` | the row | edit only |
| `title` | `str` — `"Request supplier feedback"` | create only |
| `submit_label` | `str` — `"Send request"` | create only |
| `cancel_url` | `str` — `reverse("procurement:supplierfeedback_list")` | create only |

**(contract decision: the template must fall back — `{% if title %}{{ title }}{% else %}…{% endif %}`
— or, simpler and preferred, drive its heading from `is_edit` alone and ignore `title`.)**

### 5.13 The three feedback verbs (POST-only)

No templates. Each guards the legal source status (`requested`), stamps its own columns, and calls
`write_audit_log` itself:

| View | Guard | Stamps | Message |
|---|---|---|---|
| `supplierfeedback_submit` | `status == "requested"` **and** a `rating` is present (from the row **or** `request.POST["rating"]`, validated against `dict(RATING_CHOICES)` keyed by `int`) | `status="submitted"`, `submitted_at=timezone.now()`, `rating` | success naming the number; `messages.error` + redirect when no rating |
| `supplierfeedback_decline` | `status == "requested"` | `status="declined"` | success |
| `supplierfeedback_expire` | `status == "requested"` | `status="expired"` | success |

All three `redirect("procurement:supplierfeedback_detail", pk=pk)`.

### 5.14 `improvementplan_list` → `performance/improvementplan/list.html`

`search_fields=("number","title","finding","supplier__name")`.
`filters=(("supplier","supplier_id",True), ("status","status",False), ("severity","severity",False), ("outcome","outcome",False), ("owner","owner_id",True), ("kpi","kpi_id",True))`.

| Key | Type / shape |
|---|---|
| `object_list` | page of `SupplierImprovementPlan`, `select_related("supplier","kpi","owner","scorecard","escalated_suspension")` |
| `page_obj` | `Page` |
| `q` | `str` |
| `status_choices` | `SupplierImprovementPlan.STATUS_CHOICES` |
| `severity_choices` | `SupplierImprovementPlan.SEVERITY_CHOICES` |
| `outcome_choices` | `SupplierImprovementPlan.OUTCOME_CHOICES` |
| `suppliers` | `Party` queryset (supplier/vendor roles, distinct) |
| `kpis` | `SupplierKpi` queryset (tenant) |
| `owners` | `get_user_model().objects.filter(tenant=request.tenant, procurement_improvement_plans__isnull=False).distinct().order_by("email")` — same "only users who own one" precedent as §5.1; `.none()` when `request.tenant is None` |
| `stats` | `{"total": int, "active": int, "monitoring": int, "overdue": int, "closed": int}` — `overdue` computed in the ORM: `status__in=OPEN_STATUSES` **and** `Coalesce("extended_close_date","target_close_date") < today` |

### 5.15 `improvementplan_detail` → `performance/improvementplan/detail.html`

`crud_detail(..., select_related=("supplier","kpi","owner","scorecard","escalated_suspension","acknowledged_by","verified_by"), extra_context={...})`

| Key | Type / shape |
|---|---|
| `obj` | the `SupplierImprovementPlan` |
| `outcome_choices` | `SupplierImprovementPlan.OUTCOME_CHOICES` — the close dialog's `<select name="outcome">` |
| `can_activate` | `bool` — `obj.status == "draft"` |
| `can_monitor` | `bool` — `obj.status == "active"` |
| `can_acknowledge` | `bool` — `obj.status in ("draft","active","monitoring")` **and** `obj.acknowledged_at is None` |
| `can_close` | `bool` — `obj.status in ("active","monitoring")` |
| `can_cancel` | `bool` — `obj.status in ("draft","active","monitoring")` |
| `is_overdue` | `bool` — `obj.is_overdue` (surfaced as a key so the template does not have to call the property twice) |

Detail Actions sidebar shows **only the verbs valid for the current status**, plus Edit, Delete
(POST + confirm) and Back to List.

### 5.16 The five plan verbs (POST-only; `close` is `@tenant_admin_required`)

| View | Legal source status | Stamps | Notes |
|---|---|---|---|
| `improvementplan_activate` | `draft` | `status="active"` | |
| `improvementplan_monitor` | `active` | `status="monitoring"` | |
| `improvementplan_acknowledge` | `draft`/`active`/`monitoring`, not already acknowledged | `acknowledged_by=request.user`, `acknowledged_at=timezone.now()` | status unchanged |
| `improvementplan_close` | `active`/`monitoring` | `status="closed"`, `outcome` (from `request.POST["outcome"]`, validated against `dict(OUTCOME_CHOICES)`), `closure_note` (from POST), `actual_close_date=timezone.localdate()`, `verified_by=request.user`, `verified_at=timezone.now()` | **`@tenant_admin_required`**; `messages.error` + redirect when `outcome` is missing/invalid |
| `improvementplan_cancel` | `draft`/`active`/`monitoring` | `status="cancelled"` | |

Each writes with an explicit `save(update_fields=[…, "updated_at"])`, calls `write_audit_log`
itself, and redirects to `"procurement:improvementplan_detail"`.

### 5.17 `supplier_benchmark_board` → `performance/benchmark_board.html`

Query string: `?period=<YYYY-MM-DD>&tier=<tier>&category=<text>`. Every queryset tenant-scoped and
`ROW_CAP`-bounded.

| Key | Type / shape |
|---|---|
| `rows` | `list[dict]` — one per supplier in the cohort, sorted by `composite` desc then `supplier_name`: `{"supplier_id": int, "supplier_name": str, "tier": str, "tier_label": str, "category": str, "scorecard_id": int, "scorecard_number": str, "composite": Decimal\|None, "grade": str, "rank": int, "percentile": Decimal\|None, "risk_index": Decimal\|None, "quadrant": str, "line_count": int}` |
| `periods` | `list[date]` — distinct `period_end` values across the tenant's scorecards, newest first, capped at 24 **(contract decision)** |
| `selected_period` | `date \| None` — the parsed `?period=`, defaulting to `periods[0]` when present |
| `cohort` | `dict` — `{"count": int, "average": Decimal\|None, "best": Decimal\|None, "worst": Decimal\|None, "scored": int}` over `rows` with a non-`None` composite |
| `tier_choices` | `SupplierKpi.TIER_CHOICES` (the local mirror of `scm.SupplierProfile.TIER_CHOICES`) |
| `category_choices` | `list[str]` — distinct non-blank `scm.SupplierProfile.category` values in the tenant, sorted **(contract decision)** |
| `selected_tier` | `str` — `""` when unfiltered |
| `selected_category` | `str` — `""` when unfiltered |
| `quadrant_choices` | `(("strategic","Strategic"), ("hidden","Hidden high performer"), ("development","Development"), ("underperforming","Underperforming"))` **(contract decision — the four SupplyHive segments; `row["quadrant"]` holds one of these values)** |
| `row_cap` | `int` (`ROW_CAP = 500`) |
| `truncated` | `bool` |
| `benchmark_note` | `str` — **"Benchmarks here are your own supply base only. There is no external industry feed in this system."** ONE module constant. |

Quadrant rule **(contract decision)**: composite `>= 70` and `risk_index <= 2.5` → `strategic`;
composite `>= 70` and `risk_index > 2.5` → `hidden`; composite `< 70` and `risk_index <= 2.5` →
`development`; otherwise `underperforming`. A row missing either axis gets `quadrant = ""`.

### 5.18 `supplier_trend_board` → `performance/trend_board.html`

Query string: `?supplier=<pk>&kpi=<pk>`.

| Key | Type / shape |
|---|---|
| `suppliers` | `Party` queryset (supplier/vendor roles, distinct) — the picker |
| `selected_supplier` | `Party \| None` — resolved with `as_db_int` then `.filter(pk=…).first()`, so junk yields `None` and an empty board, never a 500 |
| `periods` | `list[date]` — the `period_end` of every scorecard in the series, oldest → newest |
| `series` | `list[dict]` — the COMPOSITE series, one point per period: `{"period_end": date, "period_start": date, "scorecard_id": int, "scorecard_number": str, "composite": Decimal\|None, "overall": Decimal\|None, "grade": str, "delta": Decimal\|None, "line_count": int}` — `delta` = this point's composite minus the previous point's, `None` on the first point or when either side is `None` |
| `kpi_series` | `list[dict]` — one entry per KPI seen in the window: `{"kpi_id": int, "kpi_code": str, "kpi_name": str, "kpi_category": str, "unit": str, "direction": str, "points": [{"period_end": date, "measured_value": Decimal\|None, "score": Decimal\|None, "band": str, "band_css": str, "target_at_time": Decimal\|None, "meets_target": bool\|None, "delta": Decimal\|None}, …]}` **(contract decision on the name — the plan pins only `series`)** |
| `kpis` | `SupplierKpi` queryset (tenant, active) — the optional per-KPI filter |
| `selected_kpi` | `SupplierKpi \| None` |
| `row_cap` | `int` |
| `truncated` | `bool` |
| `benchmark_note` | `str` — same constant as §5.17 |

### 5.19 `supplier_perception_gap` → `performance/perception_gap.html`

Query string: `?supplier=<pk>&period=<YYYY-MM-DD>`.

| Key | Type / shape |
|---|---|
| `suppliers` | `Party` queryset (supplier/vendor roles, distinct) |
| `selected_supplier` | `Party \| None` |
| `periods` | `list[dict]` — the selectable windows: `{"period_end": date, "period_start": date, "label": str}`, newest first, capped 24 |
| `selected_period` | `dict \| None` — the chosen entry from `periods` (the view passes `period_start`/`period_end` from it into `perception_gap_rows`) |
| `gap_rows` | `list[dict]` — one per KPI with at least one response on either side: `{"kpi_id": int\|None, "kpi_code": str, "kpi_name": str, "internal_avg": Decimal\|None, "internal_count": int, "self_avg": Decimal\|None, "self_count": int, "delta": Decimal\|None, "delta_css": str}` — `delta = self_avg - internal_avg` (positive = the supplier rates itself higher than the buyer does); `delta_css` is `badge-red` when `delta >= 20`, `badge-amber` when `delta >= 10`, `badge-green` when `abs(delta) < 10`, `badge-info` when `delta <= -10`, `badge-slate` when `delta is None` **(contract decision)** |
| `row_cap` | `int` |
| `truncated` | `bool` |
| `gap_note` | `str` — "Ratings are converted to a 0-100 scale (1 = 0 … 5 = 100) and weighted by each respondent's importance. Only submitted responses count." **(contract decision)** |

---

## 6. `apps/procurement/performance.py` — the compute module

**NEW, FLAT at the app root** (the `analytics.py` precedent — single-purpose compute lives flat so
views stay thin and every figure is unit-testable). **Do not edit `analytics.py` — it is 6.14's.**

**Import discipline (plan, lines 1963–1968):** the four 6.16 models are imported from their
**entity modules** at module top
(`from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi`, …),
never from `apps.procurement.models`, so this module imports cleanly BEFORE the Integrate phase
adds the re-export block. Cross-app models (`scm`, `core`) come from their **package roots**, and
sibling-app reads happen **INSIDE** the function where a cycle is possible.

### Module constants

```python
ROW_CAP = 500          # every board query is bounded (the 6.15 precedent)
PERIOD_CAP = 24        # how many distinct periods a picker offers        (contract decision)
DETAIL_ROW_CAP = 50    # per-list cap on a detail page                    (contract decision)
BENCHMARK_NOTE = ("Benchmarks here are your own supply base only. "
                  "There is no external industry feed in this system.")
HANDOVER_NOTE  = (...)  # see §8 — the manual_override sentence, ONE constant
```

### Public functions

| Signature | Returns | Contract |
|---|---|---|
| `applicable_kpis(tenant, party)` | `list[SupplierKpi]` | Active KPIs for this tenant where `applies_to == "all"`, **plus** those where `applies_to == "tier"` and `applies_to_tier` equals that party's `scm.SupplierProfile.tier`. **A party with no profile gets only the `all` KPIs.** One query for the profile (local `from apps.scm.models import SupplierProfile`), one for the KPIs. Ordered `display_order, code`. |
| `resolve_derived(tenant, party, metric, start, end)` | `(Decimal \| None, dict)` | Dispatch into `DERIVED_RESOLVERS`. An unknown key returns `(None, {"error": "no resolver"})` rather than raising. |
| `survey_aggregate(tenant, party, kpi, start, end)` | `(Decimal \| None, int, dict)` | **Importance-weighted** mean of `SupplierFeedback.score_value()` over rows with `status="submitted"`, `respondent_kind="internal"`, `kpi=kpi`, `supplier=party`, and `period_end` inside `[start, end]`. Weight = `importance`; **rows with `importance == 0` contribute nothing but still count as respondents**. Returns `(None, 0, {...})` when there are no qualifying rows — never a phantom zero. Second element is the respondent count. |
| `generate_scorecard_lines(scorecard, user)` | `dict` | See below. Wrapped in `transaction.atomic`. |
| `trend_series(tenant, party, kpi=None)` | `(list[dict], list[dict], bool)` | `(composite_series, kpi_series, truncated)` — exactly the `series` / `kpi_series` shapes pinned in §5.18. Reads scorecards for `party` ordered by `period_end`, capped at `PERIOD_CAP`; joins their `SupplierKpiScore` rows in ONE query (`filter(scorecard_id__in=…)`), never per period. |
| `benchmark_rows(tenant, period_end, tier=None, category=None)` | `(list[dict], dict, bool)` | `(rows, cohort, truncated)` — exactly the `rows` / `cohort` shapes pinned in §5.17. Ranks and percentiles are computed in Python over the already-fetched rows (one pass), not with a window function. `risk_index` comes from the supplier's **most recent** `scm.SupplierRiskAssessment` at or before `period_end`, fetched in ONE query for the whole cohort. |
| `perception_gap_rows(tenant, party, start, end)` | `(list[dict], bool)` | `(gap_rows, truncated)` — exactly the shape pinned in §5.19. ONE query over `SupplierFeedback` for the window, bucketed in Python by `kpi_id` and `respondent_kind`. Rows with `kpi_id is None` are grouped under a single `{"kpi_id": None, "kpi_code": "—", "kpi_name": "General commentary"}` entry. |
| `period_choices(tenant)` | `list[date]` | Distinct `scm.SupplierScorecard.period_end` values for the tenant, newest first, capped at `PERIOD_CAP`. Used by both boards' pickers. **(contract decision)** |

### `DERIVED_RESOLVERS` — `dict[str, callable(tenant, party, start, end) -> (Decimal | None, dict)]`

Fourteen keys, one per `DERIVED_METRIC_CHOICES` value — **the two lists must stay the same length
and the same keys; a build-time `assert set(DERIVED_RESOLVERS) == {k for k, _ in DERIVED_METRIC_CHOICES}`
is the cheapest way to keep them honest (contract decision).**

**Universal rule: a metric with NO data in the period returns `(None, {...})` — never a phantom
zero** (the `recompute_from_signals()` rule). The breakdown dict always carries at least
`{"metric": key, "window": [str(start), str(end)], "rows": int}` plus the numerator/denominator it
used.

Verified join paths (grepped — these are the ONLY correct hops):

| Key | Population + hop to the supplier | Date column | Formula (Decimal, 2dp) |
|---|---|---|---|
| `otd` | `scm.GoodsReceiptNote` → `purchase_order__vendor` | `receipt_date` | receipts with `purchase_order__expected_date` set and `receipt_date <= expected_date` ÷ receipts with an expected date, ×100. Status filter `status="received"`. |
| `otif` | as `otd`, plus `scm.GoodsReceiptLine` (`goods_receipt__in=…`, `po_line__quantity`, `quantity_received`) | `receipt_date` | receipts that were on time **and** whose lines' `quantity_received` totals `>= po_line.quantity` ÷ datable receipts, ×100 |
| `defect_rate` | `scm.GoodsReceiptLine` via `goods_receipt__purchase_order__vendor` | `goods_receipt__receipt_date` | `Sum(quantity_rejected) * 100 / (Sum(quantity_received) + Sum(quantity_rejected))`; `None` when the denominator is 0 |
| `ncr_rate` | `procurement.ReceiptDiscrepancy` → **`goods_receipt__purchase_order__vendor`** (it has **no** vendor FK of its own) | **`goods_receipt__receipt_date`** (it has **no** date column of its own) | discrepancies ÷ receipts in the window, ×100 |
| `rtv_rate` | `procurement.ReturnToVendor` → `vendor` | **`created_at__date`** (contract decision — `shipped_on` is `editable=False` and often blank) | RTVs ÷ receipts in the window, ×100 |
| `invoice_accuracy` | `procurement.SupplierInvoice` → **`vendor`** (not `supplier`) | `invoice_date` | invoices whose `match_status in ("matched", "within_tolerance")` ÷ invoices whose `match_status != "not_run"`, ×100 |
| `dispute_rate` | `procurement.InvoiceDispute` → `supplier`; denominator `SupplierInvoice` → `vendor` | disputes on `raised_at__date`, invoices on `invoice_date` | disputes ÷ invoices, ×100 |
| `dispute_days` | `procurement.InvoiceDispute` → `supplier`, `resolved_at__isnull=False` | `raised_at__date` | mean `(resolved_at - raised_at).days` |
| `promise_adherence` | `procurement.DeliverySchedule` → **`po_line__purchase_order__vendor`** | `need_by_date` | instalments with a `promised_date` where `promised_date <= need_by_date` ÷ instalments with a `promised_date`, ×100 |
| `backorder_rate` | `procurement.Backorder` → **`po_line__purchase_order__vendor`**; denominator `scm.PurchaseOrderLine` → `purchase_order__vendor` | backorders on `original_promise_date`, lines on `purchase_order__order_date` | backorders ÷ PO lines, ×100 |
| `po_change_rate` | `procurement.PurchaseOrderChange` → `purchase_order__vendor`; denominator `scm.PurchaseOrder` → `vendor` | both scoped by the PO's `order_date` in the window (contract decision — the change row has no business date of its own) | changes ÷ POs, ×100 |
| `price_competitiveness` | `scm.RFQQuote` → `party` | `received_date` | mean of `min(1, best_total_for_that_rfq / this_total)` over quotes with `total > 0`, ×100. Best-per-RFQ resolved in ONE `values("rfq_id").annotate(best=Min("total"))`, never a subquery per quote (the `recompute_from_signals` precedent). |
| `quote_turnaround` | `scm.RFQQuote` → `party`, `select_related("rfq")` | `received_date` | mean `(received_date - rfq.issue_date).days` over quotes where both dates exist |
| `suspension_incidents` | `procurement.VendorSuspension` → `supplier`, `status="active"` | `starts_on` | plain count (unit `count`, `lower_is_better`). Returns `(Decimal(0), {...})` **only** when the supplier has procurement activity in the window; `(None, …)` when it has none at all — a supplier you did not buy from has no incident rate. |

Every resolver takes `tenant`, filters `tenant=tenant` on **its own** model, and takes the party by
the hop named above. No resolver ever calls `.all()`.

### `generate_scorecard_lines(scorecard, user)` — the heart of bullet 2

**Refuses (returns a refusal, writes nothing) when `scorecard.status != "draft"`.**

Return shape:

```python
{
  "refused": bool,
  "refusal_reason": str,     # "" when not refused
  "written": int,            # lines created or updated
  "skipped": int,            # applicable KPIs that produced no line (no data, no resolver)
  "dimensions": dict,        # {"delivery": Decimal|None, "quality": …, "price": …, "responsiveness": …}
  "alerts": int,             # ProcurementAlert rows raised for NEW critical crossings
}
```

Algorithm, in order, inside `transaction.atomic()`:

1. Refusal gate: `scorecard.status != "draft"` ⇒ return
   `{"refused": True, "refusal_reason": "A <status> scorecard is closed — only a draft may be generated onto.", "written": 0, "skipped": 0, "dimensions": {}, "alerts": 0}`.
2. `kpis = applicable_kpis(scorecard.tenant, scorecard.party)`.
3. Snapshot the existing bands: `previous = {kpi_id: band}` from the scorecard's current lines
   (this is what makes "NEW critical crossing" mean something).
4. Per KPI, resolve `measured_value` + `breakdown` + `respondent_count`:
   * `source == "derived"` → `resolve_derived(...)` over `[scorecard.period_start, scorecard.period_end]`.
   * `source == "survey"` → `survey_aggregate(...)`; the aggregate **is** the measured value.
   * `source == "manual"` → **leave the existing line's `measured_value` alone** (re-use it), keep
     its `comment`; a brand-new manual line is written with `measured_value=None`,
     `band="unknown"`, `breakdown={"source": "manual entry", "note": "awaiting a hand-entered value"}`.
5. `score, band = kpi.score_and_band(measured_value)`.
6. `update_or_create` **one line per KPI on `(tenant, scorecard, kpi)`** — this is what makes the
   action safe to press twice — freezing `weight_applied=kpi.weight`, `target_at_time`,
   `direction_at_time`, `source_at_time`, `unit_at_time`, `kpi_name`, `kpi_category`, plus
   `score`, `band`, `breakdown`, `respondent_count`, `computed_at=timezone.now()`,
   `computed_by=user`.
7. Fill the four `scm.SupplierScorecard` dimension columns for KPIs declaring a
   `maps_to_dimension`: **weighted mean of the lines' `score` by `weight_applied`** where several
   KPIs map to one column; a dimension whose mapped lines are all unscored is **left untouched**
   (never overwritten with a phantom zero).
8. `scorecard.manual_override = True` — **permanently hands this scorecard to 6.16.**
9. `scorecard.save()` (the four dimension columns + `manual_override`), then
   `scorecard.recompute_overall()` (default `save=True`) so `overall_score` and `grade` follow.
10. For every line whose band is `critical` **and** whose `previous.get(kpi_id)` was not
    `critical`, raise ONE `procurement.ProcurementAlert`: `tenant=scorecard.tenant`,
    `kind="task"`, `severity="critical"`, `title` naming supplier + KPI,
    `link_url=f"/procurement/supplier-evaluations/{scorecard.pk}/"` — **an internal path with a
    single leading slash, never an absolute URL** (`ProcurementAlert.clean()` enforces it).
11. Return the counts.

The **view**, not this function, calls `write_audit_log` and emits the messages.

---

## 7. Integrate-phase names (so the single writer has no decisions left)

* `models/__init__.py` re-export: `SupplierKpi`, `SupplierKpiScore`, `SupplierFeedback`,
  `SupplierImprovementPlan` — imported **from the entity modules**, appended to `__all__`.
* `forms/__init__.py` re-export: `SupplierKpiForm`, `SupplierKpiScoreEditForm`,
  `SupplierFeedbackForm`, `SupplierImprovementPlanForm`.
* `views/__init__.py` re-export: **all 33 view names** from §3.
* `urls/__init__.py`: five new imports, appended **LAST** in `urlpatterns`; extend the docstring's
  first-segment inventory with `supplier-kpis/`, `supplier-evaluations/`, `supplier-feedback/`,
  `improvement-plans/`, `supplier-benchmarking/`.
* `apps/core/navigation.py` — **exactly ONE new key**, `LIVE_LINKS["6.16"]`, placed after `"6.15"`,
  bullet names **verbatim from NavERP.md**:

```python
"6.16": {
    "KPI Definition & Setup":               "procurement:supplierkpi_list",
    "Scorecard Generation":                 "procurement:supplierevaluation_list",
    "360-Degree Feedback Collection":       "procurement:supplierfeedback_list",
    "Performance Improvement Plans (PIP)":  "procurement:improvementplan_list",
    "Benchmarking & Trending":              "procurement:supplier_benchmark_board",
},
```

  **Touch no other key** — peer sessions are editing 6.17/6.18/6.19 in this same file.
* `seed_procurement.py`: `_seed_supplier_performance(self, tenant)` + its dispatch line
  **immediately after `self._seed_budget_cost(tenant)`** (`handle()` line ~262).

---

## 8. Frozen decisions restated

### L36 — `scm.SupplierScorecard` is FK'd, never re-declared
No second scorecard table, no second vendor table, no second alert table. `SupplierKpiScore.scorecard`
FKs `"scm.SupplierScorecard"` **by string**, `CASCADE`, `related_name="procurement_kpi_scores"`.
The evaluation register's **"New period" button links out to `scm:scorecard_create`** — 6.16 ships
no scorecard form and no scorecard create route.

### `manual_override` — option (a), deliberately

**The sentence (ONE module constant, `HANDOVER_NOTE`, reused everywhere):**

> Generating this scorecard hands it permanently to Procurement 6.16. The four dimension scores are
> written from the KPI lines, `manual_override` is set, and SCM's signal engine
> (`recompute_from_signals()`) will skip this scorecard from then on. This cannot be undone from
> here.

It must appear, in these four places, and a reviewer will check all four:

1. **`ScorecardKpiScores.py` model module docstring** — as documented behaviour, not a side effect.
2. **`supplierevaluation_generate`'s view docstring.**
3. **The confirm dialog on the Generate button** —
   `onclick="return confirm('...takes this scorecard over from SCM\'s signal engine...')"`.
4. **Visibly on the page** — the evaluation detail template prints `handover_note` next to the
   button, and re-states it as a standing note when `obj.manual_override` is already `True`. The
   evaluation *list* also carries it (context key `handover_note`).

**Generate REFUSES on a `published` or `archived` scorecard** — `messages.error` + redirect back to
the detail page, **zero rows written**. Only `draft` may be generated onto.

### Migration
`python manage.py makemigrations procurement` must produce **`0026_*` and nothing else**. If it also
wants to alter a table this pass did not touch, **STOP** — another session's model edit has leaked
in. (6.17 takes 0027, 6.18 takes 0028, 6.19 takes 0029.)

### Theme classes are colour-named ONLY (L33)
`theme.css` ships exactly `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`,
`badge-slate` (verified `static/css/theme.css:286-291`) and stat-icon modifiers `blue`, `green`,
`orange`, `purple`, `red`, `slate` (`:260-265`). **`badge-success` / `badge-warning` /
`badge-danger` DO NOT EXIST and render completely unstyled.**

The band mapping, pinned:

```python
BAND_CSS = {"ok": "badge-green", "warning": "badge-amber",
            "critical": "badge-red", "unknown": "badge-muted"}
# @property band_css -> BAND_CSS.get(self.band, "badge-slate")
```

### First URL path component is always a literal
No converter in first position anywhere in `apps/procurement/urls/`. 6.16's five segments —
`supplier-kpis/`, `supplier-evaluations/`, `supplier-feedback/`, `improvement-plans/`,
`supplier-benchmarking/` — are all literals and all new whole components. Within
`ScorecardKpiScores.py`, literal `scores/` is declared **before** `supplier-evaluations/<int:pk>/`.

### Tenant scoping
Every queryset `filter(tenant=request.tenant)`, never `.all()`. Suppliers scope as:

```python
Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).distinct()
```

A tenant-less user (the superuser, `tenant=None`) gets `.none()` querysets on every board and every
form, and `crud_create`'s own guard redirects them to `dashboard:home`.

---

## 9. Discrepancies resolved

| # | What | Resolution |
|---|---|---|
| 1 | Research §Bullet 2 says the resolvers live "in a procurement `services.py`/`analytics.py`-style module"; the plan names `apps/procurement/performance.py`. | **Plan wins** — `apps/procurement/performance.py`, flat at the app root. `analytics.py` belongs to 6.14 and is not touched. |
| 2 | Research says `procurement.DeliverySchedule` "already has a `days` delta property". | The real property is **`slip_days`** (`= promised_date - need_by_date`, 0 when either is missing), plus `has_slip` / `is_late` / `days_late`. `promise_adherence` is defined over `promised_date` vs `need_by_date` accordingly (§6). |
| 3 | Plan calls `ReceiptDiscrepancy` an `ncr_rate` source without naming the hop. | `ReceiptDiscrepancy` has **no vendor FK and no date column of its own** (verified). The only correct hops are `goods_receipt__purchase_order__vendor` and `goods_receipt__receipt_date`. Pinned in §6. |
| 4 | Plan says the `invoice_accuracy` / `dispute_rate` sources are keyed by "supplier". | `SupplierInvoice`'s party FK is **`vendor`**, not `supplier`; `InvoiceDispute`'s **is** `supplier`. Both pinned in §6 — using the wrong one is a `FieldError` at first call. |
| 5 | Plan says `Backorder` / `DeliverySchedule` are supplier-scoped. | Neither carries a supplier FK; both reach it through **`po_line__purchase_order__vendor`** (verified). Pinned in §6. |
| 6 | Plan gives `PurchaseOrderChange` no date column for windowing. | It has none with business meaning (only `created_at` / `decided_at` / `applied_at`). **(contract decision)** Both numerator and denominator are scoped by the *purchase order's* `order_date` falling in the window — the change and the PO it amends are then always counted in the same period. |
| 7 | Plan names a `direction` and an `applies_to` list filter but pins no context key for either; likewise the `is_active` filter. | **(contract decision)** `direction_choices`, `applies_choices`, `active_choices` (§5.1). |
| 8 | Plan pins `series` for the trend board but describes "composite **and per-KPI** series". | **(contract decision)** `series` = the composite series; `kpi_series` = the per-KPI series. Both shapes pinned in §5.18. |
| 9 | Plan pins `selected_period` for the boards but `perception_gap_rows` takes `(start, end)`. | **(contract decision)** `periods` on the perception-gap board is a list of `{"period_start", "period_end", "label"}` dicts and `selected_period` is one of them; the benchmark board's `periods` stays a plain `list[date]` keyed on `period_end`. |
| 10 | Plan's `stats` key is pinned by name but not by contents, for five different lists. | **(contract decision)** Each list's exact `stats` keys are pinned in §5.1 / §5.4 / §5.7 / §5.10 / §5.14. A template reading `stats.pending` when the view set `stats["requested"]` renders blank (L8). |
| 11 | Plan says `SupplierKpi.score_and_band()` applies "`scoring_method` + `direction` + the three thresholds" but gives no arithmetic. | **(contract decision)** The full algorithm is pinned in §1.1, including the documented `linear`→`band` fallback when the span is missing or zero. |
| 12 | Plan pins `crud_edit`'s `success_url` for `supplierkpiscore_edit` as the detail page, which takes a `pk`. | `crud_edit` calls `redirect(success_url)` with **no args**, so a named route needing a pk would `NoReverseMatch`. **(contract decision)** Pass `reverse("procurement:supplierkpiscore_detail", args=[pk])`. |
| 13 | Plan lists `SupplierFeedback`'s FKs in one bullet, implying `respondent` sits with `requested_by`. | **(contract decision)** `respondent` is declared next to `respondent_kind` / `respondent_name`; `requested_by` sits with the other `editable=False` stamps. The form's `Meta.fields` order (§2.3) is authoritative for render order either way. |
| 14 | Plan does not name the index for `(tenant, category)` / `(tenant, source)` etc., only the prefixes. | **(contract decision)** All twelve names pinned in §1 — every one ≤30 chars and grep-verified as unused: `prc_skp_tnt_active_idx`, `prc_skp_tnt_cat_idx`, `prc_skp_tnt_source_idx`, `prc_sks_tnt_scr_idx`, `prc_sks_tnt_band_idx`, `prc_sks_tnt_kpi_idx`, `prc_sfb_tnt_supp_idx`, `prc_sfb_tnt_status_idx`, `prc_sfb_tnt_scr_idx`, `prc_sip_tnt_status_idx`, `prc_sip_tnt_supp_idx`, `prc_sip_tnt_sev_idx`. |
| 15 | Plan does not say how `SupplierFeedback.clean()` rule 1 handles a NULL `respondent`. | **(contract decision)** The uniqueness probe matches on `respondent_id` too, `None` included — an anonymous `supplier_self` response has `respondent_id IS NULL`, and two of them for the same `(supplier, scorecard, kpi)` **are** a duplicate. |
| 16 | Plan line 1744 says `owner`'s queryset is "narrowed to `User.objects.filter(tenant=tenant, is_active=True)`", and the same for `respondent` ("tenant users"). | **Half of that is already done and re-doing it introduces a new idiom.** `TenantModelForm.__init__` (`apps/core/forms/_common.py:50-53`) filters every `ModelChoiceField` whose target model has a `tenant` field, and `accounts.User.tenant` exists (`apps/accounts/models.py:56`) — so user FKs on these forms are **auto-scoped**. **(contract decision)** Forms narrow only `is_active=True` + `empty_label` off the already-scoped queryset, exactly as `ProcurementAlert.assigned_to` and `InvoiceDispute.assigned_to` document. `_reject_foreign` still covers the crafted POST. |
| 17 | Plan implies date inputs need `forms.DateInput(attrs={"type": "date"})` in `Meta.widgets`. | `TenantModelForm` **unconditionally replaces** every `DateField` widget with a `type="date"` `DateInput` and pins `input_formats = ["%Y-%m-%d"]`. Those `Meta.widgets` entries are **no-ops** — harmless (the `CostForecastForm` carries one) but not load-bearing. `rows=` on a Textarea is. Flagged so a reviewer does not read them as the mechanism. |
| 18 | Plan pins the `owners` filter dropdown as a context key but not its population. | **(contract decision)** Both `owners` dropdowns follow the in-app `_dispute_owners` precedent (`views/InvoiceVoucherManagement/InvoiceDisputes.py:128`): **only users who actually own a row** (`<reverse related_name>__isnull=False`), `.distinct().order_by("email")`, `.none()` for a tenant-less user. A whole-directory dropdown is a page that never finishes loading on a big tenant. |

**Nothing in the plan referenced a class or field that does not exist.** All fifteen spine
classes and every field named in §0 and §6 were grepped this pass and resolve as written.
