"""HRM 3.5 Job Requisition — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


# Fields copied when a requisition is cloned (everything except workflow-owned + identity columns).
# FKs are copied by ``<name>_id`` so no extra query is needed; plain columns by attribute.
_JR_CLONE_FK_FIELDS = ["designation", "job_grade", "template", "department", "cost_center",
                       "hiring_manager", "recruiter"]


_JR_CLONE_PLAIN_FIELDS = ["title", "location", "headcount", "req_type", "employment_type",
                          "reason_for_hire", "is_replacement_for", "posting_type",
                          "target_start_date", "priority", "salary_min", "salary_max",
                          "salary_currency", "estimated_annual_cost", "hiring_cost_budget",
                          "jd_summary", "jd_responsibilities", "jd_requirements",
                          "jd_nice_to_have", "notes"]
