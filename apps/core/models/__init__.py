"""core models package — split from apps/core/models.py.

core is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.core.models import X`` (and the 78+ modules that do it) is unchanged.
"""
from ._base import *  # noqa: F401,F403
from .Tenant import (
    Tenant,
    DOMAIN,
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
from .ModuleAccessScope import (
    ModuleAccessScope,
    SensitiveFieldMask,
)  # noqa: F401
from .Consent import (
    ConsentPurpose,
    ConsentRecord,
    current_consent,
)  # noqa: F401
from .DataSubjectRequest import (
    DataSubjectRequest,
)  # noqa: F401
from .Retention import (
    RetentionPolicy,
    DisposalRecord,
)  # noqa: F401
from .Privacy import (
    PiiClassification,
    RegulatoryFramework,
)  # noqa: F401
from .Setting import (
    SettingDefinition,
    SettingValue,
)  # noqa: F401
from .FeatureFlag import (
    FeatureFlag,
)  # noqa: F401
from .NumberingScheme import (
    NumberingScheme,
)  # noqa: F401
from .Calendar import (
    BusinessCalendar,
    Holiday,
)  # noqa: F401
from .CustomField import (
    CustomFieldDefinition,
    CustomFieldValue,
)  # noqa: F401
from .Workflow import (
    WorkflowDefinition,
    WorkflowStep,
    ApprovalLimit,
    SlaRule,
)  # noqa: F401
from .BusinessRule import (
    BusinessRule,
    BusinessRuleLog,
)  # noqa: F401
from .Notification import (
    NotificationChannel,
    NotificationTemplate,
    NotificationRule,
    NotificationPreference,
    ProviderConfig,
)  # noqa: F401
from .Integration import (
    ApiCredential,
    RateLimitPolicy,
    ConnectorDefinition,
    MappingTemplate,
    SyncSchedule,
)  # noqa: F401
from .Localization import (
    Language,
    TimeZone,
    LocaleProfile,
    UserLocalePreference,
    StatutoryRule,
)  # noqa: F401
from .Backup import (
    BackupJob,
    DataArchive,
    RestoreRecord,
    EnvironmentInstance,
    RecoveryPosture,
    RecoveryDrill,
)  # noqa: F401
from .LegalHold import (
    LegalHold,
)  # noqa: F401
