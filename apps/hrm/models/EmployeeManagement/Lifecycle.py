"""HRM 3.1 Employee Management — Lifecycle models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Module-level so the form, views and templates share one source for the event taxonomy.
LIFECYCLE_EVENT_TYPE_CHOICES = [
    ("hire", "Hire"),
    ("confirmation", "Confirmation (Probation End)"),
    ("transfer", "Transfer"),
    ("promotion", "Promotion"),
    ("demotion", "Demotion"),
    ("salary_revision", "Salary Revision"),
    ("re_designation", "Re-designation"),
    ("location_change", "Location Change"),
    ("reporting_change", "Reporting Manager Change"),
    ("suspension", "Suspension"),
    ("reinstatement", "Reinstatement"),
    ("contract_renewal", "Contract Renewal"),
    ("separation", "Separation"),
    ("other", "Other"),
]
