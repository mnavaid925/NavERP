"""core forms package — split from apps/core/forms.py.

core is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.core.forms import X`` (and the 78+ modules that do it) is unchanged.
"""
from ._common import *  # noqa: F401,F403
from .OrgUnit import (
    OrgUnitForm,
)  # noqa: F401
from .Party import (
    PartyForm,
)  # noqa: F401
from .PartyRole import (
    PartyRoleForm,
)  # noqa: F401
from .Address import (
    AddressForm,
)  # noqa: F401
from .ContactMethod import (
    ContactMethodForm,
)  # noqa: F401
from .PartyRelationship import (
    PartyRelationshipForm,
)  # noqa: F401
from .Employment import (
    EmploymentForm,
)  # noqa: F401
from .Activity import (
    ActivityForm,
)  # noqa: F401
from .Document import (
    DocumentForm,
)  # noqa: F401
