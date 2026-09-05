"""6.16 Supplier Performance & Evaluation URL patterns — one module per entity/page group.

``app_name`` is set once in ``apps/procurement/urls/__init__.py``; this package only concatenates
its five modules' ``urlpatterns`` — 33 routes under 33 distinct names.

Five first segments are claimed by this sub-module, every one of them a new whole component
checked against the inventory in ``apps/procurement/urls/__init__.py``: ``supplier-kpis/``,
``supplier-evaluations/`` (with its literal ``scores/`` child block), ``supplier-feedback/``,
``improvement-plans/`` and ``supplier-benchmarking/`` (with its literal ``trend/`` and
``perception-gap/`` children). None is a prefix of any other segment in the app — Django matches
whole path components, not strings.

No route in this app uses a converter in its FIRST path component — every first segment is a
literal — so no module can shadow another's namespace, and 6.16 does not become the first to
break that. (A ``<str:token>`` converter DOES exist, at 6.8's ``contract-sign/<str:token>/``, but
it sits behind a literal first segment and shadows nothing outside it.)

**Order is behaviour, and it has to survive this concatenation.** Django resolves
first-match-wins over the flattened list, so ``ScorecardKpiScores`` is included as ONE unit with
its four literal ``supplier-evaluations/scores/`` routes already ahead of
``supplier-evaluations/<int:pk>/`` inside it. Splitting that module across two entries here, or
appending a sixth module that re-opened ``supplier-evaluations/``, would put a converter route
in front of a literal one and the whole score register would disappear behind a scorecard-detail
404. ``int`` would not swallow ``scores`` today — it rejects it and Django falls through — but
the ordering is the rule that keeps that true the day somebody widens the converter.

**All five land together or none do.** The three boards emit ``{% url %}`` tags for
``supplierkpi_detail``, ``supplierevaluation_detail``, ``supplierevaluation_list`` and
``supplierfeedback_list``, and the KPI and evaluation detail pages link to
``improvementplan_detail`` and ``supplierfeedback_list`` in turn — wiring a subset is a
``NoReverseMatch`` on a page a smoke sweep would otherwise call green.

**There is no scorecard CREATE route here** (L36, §8). ``scm.SupplierScorecard`` is SCM's model,
FK'd and never re-declared, so the evaluation register's "New period" button links straight out
to ``scm:scorecard_create``.
"""
from .SupplierKpis import urlpatterns as _spe_kpis
from .ScorecardKpiScores import urlpatterns as _spe_scores
from .SupplierFeedback import urlpatterns as _spe_feedback
from .SupplierImprovementPlans import urlpatterns as _spe_plans
from .PerformanceBoards import urlpatterns as _spe_boards


urlpatterns = [
    *_spe_kpis,      # supplier-kpis/ CRUD (5)
    *_spe_scores,    # supplier-evaluations/ register + generate, and the scores/ block (7)
    *_spe_feedback,  # supplier-feedback/ CRUD + submit / decline / expire (8)
    *_spe_plans,     # improvement-plans/ CRUD + activate / monitor / acknowledge / close /
                     #   cancel (10)
    *_spe_boards,    # supplier-benchmarking/ + trend/ + perception-gap/ (3)
]
