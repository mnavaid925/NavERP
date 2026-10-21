from apps.sales.views.PartnerChannel.ChannelConflicts import (
    channel_conflict_create,
    channel_conflict_delete,
    channel_conflict_detail,
    channel_conflict_edit,
    channel_conflict_list,
)
from apps.sales.views.PartnerChannel.DealRegistrations import (
    deal_registration_convert,
    deal_registration_create,
    deal_registration_delete,
    deal_registration_detail,
    deal_registration_edit,
    deal_registration_list,
)
from apps.sales.views.PartnerChannel.JointAccountPlans import (
    joint_account_plan_create,
    joint_account_plan_delete,
    joint_account_plan_detail,
    joint_account_plan_edit,
    joint_account_plan_list,
)
from apps.sales.views.PartnerChannel.PartnerProfiles import (
    partner_performance_console,
    partner_profile_create,
    partner_profile_delete,
    partner_profile_detail,
    partner_profile_edit,
    partner_profile_list,
)

__all__ = [
    "partner_profile_list",
    "partner_profile_create",
    "partner_profile_detail",
    "partner_profile_edit",
    "partner_profile_delete",
    "partner_performance_console",
    "deal_registration_list",
    "deal_registration_create",
    "deal_registration_detail",
    "deal_registration_edit",
    "deal_registration_delete",
    "deal_registration_convert",
    "joint_account_plan_list",
    "joint_account_plan_create",
    "joint_account_plan_detail",
    "joint_account_plan_edit",
    "joint_account_plan_delete",
    "channel_conflict_list",
    "channel_conflict_create",
    "channel_conflict_detail",
    "channel_conflict_edit",
    "channel_conflict_delete",
]
