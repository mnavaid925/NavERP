"""HRM 3.15 Statutory Compliance — INDIAN_STATE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# India's states + union territories — the choice list shared by
# ``StatutoryConfig.pt_default_state``, ``StatutoryStateRule.state``, and
# ``EmployeeStatutoryIdentifier.pt_state`` (PT/LWF are state-scoped schemes).
INDIAN_STATE_CHOICES = [
    ("Andhra Pradesh", "Andhra Pradesh"), ("Arunachal Pradesh", "Arunachal Pradesh"),
    ("Assam", "Assam"), ("Bihar", "Bihar"), ("Chhattisgarh", "Chhattisgarh"),
    ("Goa", "Goa"), ("Gujarat", "Gujarat"), ("Haryana", "Haryana"),
    ("Himachal Pradesh", "Himachal Pradesh"), ("Jharkhand", "Jharkhand"),
    ("Karnataka", "Karnataka"), ("Kerala", "Kerala"), ("Madhya Pradesh", "Madhya Pradesh"),
    ("Maharashtra", "Maharashtra"), ("Manipur", "Manipur"), ("Meghalaya", "Meghalaya"),
    ("Mizoram", "Mizoram"), ("Nagaland", "Nagaland"), ("Odisha", "Odisha"),
    ("Punjab", "Punjab"), ("Rajasthan", "Rajasthan"), ("Sikkim", "Sikkim"),
    ("Tamil Nadu", "Tamil Nadu"), ("Telangana", "Telangana"), ("Tripura", "Tripura"),
    ("Uttar Pradesh", "Uttar Pradesh"), ("Uttarakhand", "Uttarakhand"),
    ("West Bengal", "West Bengal"),
    # Union territories
    ("Andaman and Nicobar Islands", "Andaman and Nicobar Islands"),
    ("Chandigarh", "Chandigarh"),
    ("Dadra and Nagar Haveli and Daman and Diu", "Dadra and Nagar Haveli and Daman and Diu"),
    ("Delhi", "Delhi"), ("Jammu and Kashmir", "Jammu and Kashmir"), ("Ladakh", "Ladakh"),
    ("Lakshadweep", "Lakshadweep"), ("Puducherry", "Puducherry"),
]
