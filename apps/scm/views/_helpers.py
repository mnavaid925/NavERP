"""Cross-cutting private helpers for the scm views package.

Helpers used by MORE THAN ONE sub-module/entity live here; anything used by a single entity stays in
that entity's own view module (mirrors apps/accounting/views/_helpers.py).
"""
from apps.scm.views._common import *  # noqa: F401,F403

# Defined once in the forms toolkit and re-exported here rather than duplicated: the buy-from-party
# rule (accept BOTH the `supplier` and `vendor` PartyRole spellings) is a single decision, and two
# copies would drift the day one of them is changed. Views legitimately depend on forms.
from apps.scm.forms._common import _supplier_parties  # noqa: F401


def _need_tenant(request):
    """True (and flashes) when the user has no tenant workspace.

    The superuser has ``tenant=None`` by design and every scm view filters by tenant, so creating a
    record as that user would silently produce an orphan row. Callers redirect on True.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return True
    return False
