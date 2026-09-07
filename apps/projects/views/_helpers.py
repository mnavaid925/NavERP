"""Private helpers used by MORE THAN ONE sub-module's views.

A helper used by a single entity stays in that entity's module. These three are each shared by
more than one of 7.1's registers, so they live here rather than being copy-pasted forward.

Both return ``.none()`` for a tenant-less user instead of raising: the superuser has
``tenant=None`` and sees no module data by design, so a filter dropdown for them is empty, not an
error.
"""
from apps.core.models import OrgUnit, Party
from apps.projects.models import Project


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


def projects(tenant):
    """This workspace's Projects, ordered for a filter dropdown.

    Shared by the stakeholder register and the kickoff register — it was copy-pasted
    byte-identically into both entity modules, which is where two copies drift.
    """
    if tenant is None:
        return Project.objects.none()
    return Project.objects.filter(tenant=tenant).order_by("name")
