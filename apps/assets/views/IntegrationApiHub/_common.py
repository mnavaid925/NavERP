"""Shared view helpers for Integration & API Hub (11.15)."""

from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)

_MAX_BIGINT = 9_223_372_036_854_775_807


def parse_pos_int(value):
    """Parse a positive ASCII integer fitting in BigAutoField, or return None."""
    raw = (value or "").strip()
    if not raw or not raw.isascii() or not raw.isdigit():
        return None
    parsed = int(raw)
    if parsed < 1 or parsed > _MAX_BIGINT:
        return None
    return parsed


def verified_connector_initial(request):
    """Return initial dict prefilling connector only when owned by request.tenant."""
    conn_pk = parse_pos_int(request.GET.get("connector"))
    if (
        conn_pk is not None
        and getattr(request, "tenant", None) is not None
        and AssetIntegrationConnector.objects.filter(
            pk=conn_pk, tenant=request.tenant
        ).exists()
    ):
        return {"connector": conn_pk}
    return {}
