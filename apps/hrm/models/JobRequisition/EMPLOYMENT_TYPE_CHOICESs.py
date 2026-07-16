"""HRM 3.5 Job Requisition — EMPLOYMENT_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Shared choice constants (module-level — reused by JobDescriptionTemplate, JobRequisition,
# RequisitionApproval, the forms' filter dropdowns, and the seeder).
EMPLOYMENT_TYPE_CHOICES = [
    ("full_time", "Full-Time"),
    ("part_time", "Part-Time"),
    ("contract", "Contract"),
    ("intern", "Intern"),
    ("consultant", "Consultant"),
]
