"""HRM 3.6 Candidate Management — EMAIL_TEMPLATE_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


EMAIL_TEMPLATE_TYPE_CHOICES = [
    ("application_received", "Application Received"),
    ("shortlisted", "Application Shortlisted"),
    ("phone_screen_invite", "Phone Screen Invitation"),
    ("interview_invite", "Interview Invitation"),
    ("interview_reminder", "Interview Reminder"),
    ("stage_advance", "Advance to Next Stage"),
    ("assessment_invite", "Assessment / Test Invitation"),
    ("rejection", "Application Rejected"),
    ("on_hold", "Application On Hold"),
    ("offer", "Offer Communication"),
    ("general", "General / Ad-hoc"),
]
