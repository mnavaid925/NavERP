"""HRM 3.6 Candidate Management — Partys views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


def party_has_only_candidate_role(party):
    roles = set(party.roles.filter(tenant=party.tenant_id).values_list("role", flat=True))
    return roles <= {"candidate"}
