"""core views package — split from apps/core/views.py.

core is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.core.views import X`` (and the 78+ modules that do it) is unchanged.
"""
from ._common import *  # noqa: F401,F403
from ._common import _parties  # noqa: F401
from .OrgUnit import (
    orgunit_list,
    orgunit_create,
    orgunit_detail,
    orgunit_edit,
    orgunit_delete,
)  # noqa: F401
from .Party import (
    party_list,
    party_create,
    party_detail,
    party_edit,
    party_delete,
)  # noqa: F401
from .PartyRole import (
    partyrole_list,
    partyrole_create,
    partyrole_detail,
    partyrole_edit,
    partyrole_delete,
)  # noqa: F401
from .Address import (
    address_list,
    address_create,
    address_detail,
    address_edit,
    address_delete,
)  # noqa: F401
from .ContactMethod import (
    contactmethod_list,
    contactmethod_create,
    contactmethod_detail,
    contactmethod_edit,
    contactmethod_delete,
)  # noqa: F401
from .PartyRelationship import (
    partyrelationship_list,
    partyrelationship_create,
    partyrelationship_detail,
    partyrelationship_edit,
    partyrelationship_delete,
)  # noqa: F401
from .Employment import (
    employment_list,
    employment_create,
    employment_detail,
    employment_edit,
    employment_delete,
)  # noqa: F401
from .Activity import (
    activity_list,
    activity_create,
    activity_detail,
    activity_edit,
    activity_delete,
)  # noqa: F401
from .Document import (
    document_list,
    document_create,
    document_detail,
    document_edit,
    document_delete,
)  # noqa: F401
from .AuditLog import (
    auditlog_list,
    auditlog_detail,
)  # noqa: F401
from .Search import (
    global_search_suggest,
    global_search,
)  # noqa: F401
