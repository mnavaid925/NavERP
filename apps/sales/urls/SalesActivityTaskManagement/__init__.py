"""Sales 8.8 — URL concatenation for Sales Activity & Task Management.

**FIRST-MATCH-WINS IS BEHAVIOUR, NOT STYLE.** The four entity modules are spliced in the order below
and each of them keeps its literal routes (``…/add/``) ahead of its ``<int:pk>/`` ones, because a
literal listed below its own keyed sibling loses: ``int("add")`` raises ``ValueError`` and the
register answers 500 instead of rendering.

Every prefix declared here — ``activity-types/``, ``activity-log/``, ``task-templates/``,
``plan-cycles/``, ``plan/``, ``next-best-actions/``, ``email-engagement/`` — was verified free
against the WHOLE concatenated ``sales:urlpatterns`` list, not just against this module. No greedy
``<str:token>`` route is introduced, so nothing here can swallow a sibling module's URL.

**L54's second rule applies to this file too.** Adding a url module is TWO edits: the import below,
and the ``+ _sales_activity`` concatenation line in ``apps/sales/urls/__init__.py``. An import alone
is a complete no-op that still leaves ``manage.py check`` clean and every ``reverse()`` raising
``NoReverseMatch``. Both are done in the Integrate step and both are verified by reversing every
name in the build contract.
"""
from .ActivityTypes import urlpatterns as _activity_types
from .ActivityLogs import urlpatterns as _activity_logs
from .TaskTemplates import urlpatterns as _task_templates
from .SalesPlanCycles import urlpatterns as _plan_cycles

urlpatterns = [
    *_activity_types,
    *_activity_logs,
    *_task_templates,
    *_plan_cycles,
]