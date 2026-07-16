"""core models package — split from apps/core/models.py.

core is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.core.models import X`` (and the 78+ modules that do it) is unchanged.
"""
from ._base import *  # noqa: F401,F403
from .Tenant import (
    Tenant,
)  # noqa: F401
from .OrgUnit import (
    OrgUnit,
)  # noqa: F401
from .Party import (
    Party,
)  # noqa: F401
from .PartyRole import (
    PartyRole,
)  # noqa: F401
from .Address import (
    Address,
)  # noqa: F401
from .ContactMethod import (
    ContactMethod,
)  # noqa: F401
from .PartyRelationship import (
    PartyRelationship,
)  # noqa: F401
from .Employment import (
    Employment,
)  # noqa: F401
from .Activity import (
    Activity,
)  # noqa: F401
from .AuditLog import (
    AuditLog,
)  # noqa: F401
from .Document import (
    Document,
)  # noqa: F401
