"""Private helpers used by MORE THAN ONE sub-module's views.

A helper used by a single entity stays in that entity's module. These two are shared by 7.1's
request register and project register, so they live here rather than being copy-pasted forward.

Both return ``.none()`` for a tenant-less user instead of raising: the superuser has
``tenant=None`` and sees no module data by design, so a filter dropdown for them is empty, not an
error.
"""
from apps.core.models import OrgUnit, Party


def org_units(tenant):
    """This workspace's OrgUnits, ordered for a filter dropdown."""
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


def clients(tenant):
    """This workspace's Parties — a client is a Party with (or without) a customer role.

    Deliberately not filtered to ``PartyRole.role == "customer"``: a project's client can be any
    organisation on the spine, and a dropdown that silently omits the one you need is worse than
    one that lists everyone.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant).order_by("name")
