"""Inventory 5.19 Third-Party Integrations & API — shared choice constants.

Pure data module: imports NOTHING (contract §1 header). Sibling entity modules under
``ThirdPartyIntegrations/`` import FROM IT BY NAME — never star-import a ``_choices``
module.
"""

__all__ = [
    "CHANNEL_KIND_CHOICES",
    "CHANNEL_PLATFORM_CHOICES",
    "CHANNEL_SYNC_DIRECTION_CHOICES",
    "CHANNEL_AUTH_METHOD_CHOICES",
    "ENVIRONMENT_CHOICES",
    "CHANNEL_STATUS_CHOICES",
    "CHANNEL_TRIGGER_CHOICES",
    "RUN_DIRECTION_CHOICES",
    "RUN_TRIGGER_CHOICES",
    "RUN_STATUS_CHOICES",
    "SYNC_BACKOFF_SECONDS",
    "API_PROTOCOL_CHOICES",
    "API_STATUS_CHOICES",
]

#: What KIND of external system the connection register row points at (bullets 1-3).
CHANNEL_KIND_CHOICES = [
    ("ecommerce", "E-commerce"),
    ("erp", "ERP"),
    ("accounting", "Accounting"),
    ("custom", "Custom"),
]

#: Named commercial platform the connector targets (max_length=20; longest value
#: ``amazon_sp_api`` = 13).
CHANNEL_PLATFORM_CHOICES = [
    ("shopify", "Shopify"),
    ("amazon_sp_api", "Amazon SP-API"),
    ("woocommerce", "WooCommerce"),
    ("ebay", "eBay"),
    ("walmart", "Walmart"),
    ("magento", "Magento"),
    ("bigcommerce", "BigCommerce"),
    ("sap", "SAP"),
    ("oracle_erp", "Oracle ERP"),
    ("netsuite", "NetSuite"),
    ("dynamics", "Microsoft Dynamics"),
    ("quickbooks", "QuickBooks"),
    ("xero", "Xero"),
    ("sage", "Sage"),
    ("custom", "Custom"),
]

#: Which way stock data flows across the connection (INTENT — nothing transports it).
CHANNEL_SYNC_DIRECTION_CHOICES = [
    ("push_stock", "Push Stock"),
    ("pull_orders", "Pull Orders"),
    ("bidirectional", "Bidirectional"),
]

#: How the channel authenticates — RECORDED INTENT only; no token/OAuth storage exists
#: in this build.
CHANNEL_AUTH_METHOD_CHOICES = [
    ("none", "None"),
    ("api_key", "API Key"),
    ("basic", "Basic Auth"),
    ("oauth2", "OAuth 2.0"),
    ("signature", "Signature"),
]

#: Sandbox vs production endpoint registration.
ENVIRONMENT_CHOICES = [
    ("sandbox", "Sandbox"),
    ("production", "Production"),
]

#: Human-maintained connection health marker — no transport observes anything.
CHANNEL_STATUS_CHOICES = [
    ("disconnected", "Disconnected"),
    ("connected", "Connected"),
    ("error", "Error"),
    ("disabled", "Disabled"),
]

#: When a sync WOULD fire (intent only — no scheduler exists).
CHANNEL_TRIGGER_CHOICES = [
    ("manual", "Manual"),
    ("scheduled", "Scheduled"),
    ("webhook", "Webhook"),
]

#: Direction of a recorded StockSyncRun batch.
RUN_DIRECTION_CHOICES = [
    ("outbound_push", "Outbound Push"),
    ("inbound_pull", "Inbound Pull"),
]

#: What started a recorded StockSyncRun batch.
RUN_TRIGGER_CHOICES = [
    ("manual", "Manual"),
    ("scheduled", "Scheduled"),
    ("webhook_inbound", "Webhook Inbound"),
]

#: Outcome markers for a recorded run — ``simulated`` is mandatory honesty: nothing leaves
#: the process, so recording plain "success" would fabricate evidence.
RUN_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("success", "Success"),
    ("partial", "Partial"),
    ("failed", "Failed"),
    ("exhausted", "Exhausted"),
    ("simulated", "Simulated"),
]

#: Svix-style retry ladder adopted verbatim (same posture as scm DELIVERY_BACKOFF_SECONDS);
#: indexed by ``attempt_no``, repeated tail marks the schedule spent.
SYNC_BACKOFF_SECONDS = (0, 5, 300, 1800, 7200, 18000, 36000, 36000)

#: Protocols of the REST/GraphQL surface keys are issued FOR (bullet 4).
API_PROTOCOL_CHOICES = [
    ("rest", "REST"),
    ("graphql", "GraphQL"),
]

#: ApiClient credential lifecycle — moves ONLY via the revoke POST verb.
API_STATUS_CHOICES = [
    ("active", "Active"),
    ("revoked", "Revoked"),
]
