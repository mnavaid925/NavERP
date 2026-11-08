"""Models package for apps.assets."""
from apps.assets.models._base import TenantNumbered, TenantOwned

__all__ = [
    "TenantOwned",
    "TenantNumbered",
]
