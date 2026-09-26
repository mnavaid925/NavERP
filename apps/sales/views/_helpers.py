"""Helpers shared by more than one 8.4 view module.

Per the backend-package rule, a helper used by two or more sub-module entities lives
here rather than in whichever module happened to need it first.
"""
from apps.sales.views._common import *  # noqa: F401,F403


def is_tenant_admin(user):
    """Whether this user may take the tenant-admin actions (lock, review, apply).

    One definition, imported by all four 8.4 view modules. It was previously
    copy-pasted into each of them and then imported by name from a sibling, so the
    boards module depended on ``ForecastPeriods``' private name -- four copies of a
    role check, each free to drift.

    ``getattr`` throughout: ``AnonymousUser`` and the seeder's unsaved users have
    neither attribute, and this must answer False rather than raise.
    """
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))
